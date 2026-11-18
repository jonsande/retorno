"""Internal paid physical maneuvers through the real Engine and GameLoop."""
from copy import deepcopy
from dataclasses import replace
import math
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, MotionState, accelerate_to,
                                       brake_to_stop, coast_for, metres_to_light_years)
from retorno.core.nav_state import PhysicalTransitState
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode
from retorno.runtime.loop import GameLoop
from retorno.io.save_load import load_single_slot, save_single_slot


def ready_game(beta=0.0):
    game = create_initial_state_sandbox(seed=341)
    game.ship.drones.clear()
    game.ship.docked_node_id = None
    game.ship.systems["power_core"].state = SystemState.NOMINAL
    game.ship.systems["energy_distribution"].state = SystemState.NOMINAL
    game.ship.power.p_gen_base_kw = 12.0
    game.ship.power.p_gen_kw = 12.0
    game.ship.power.e_batt_kwh = 3.0
    game.ship.power.power_quality = 1.0
    game.world.lore_placements.next_non_forced_eval_t = 1e9
    origin = game.world.space.nodes[game.world.current_node_id]
    origin.radiation_rad_per_s = .0001
    destination_ly = metres_to_light_years(LIGHT_SPEED_M_S * .5 * 500)
    game.world.space.nodes["COAST_DEST"] = SpaceNode(
        "COAST_DEST", "Coast destination", "station",
        radiation_rad_per_s=.0002, x_ly=origin.x_ly + destination_ly,
        y_ly=origin.y_ly, z_ly=origin.z_ly,
    )
    game.ship.transit_from = origin.node_id
    return game, MotionState(0, 0, beta, 0)


def prepared(game, segment, intent, speed=0.5):
    return Engine().prepare_physical_segment(
        game, segment, "COAST_DEST", intent, pricing_speed=speed)


def test_acceleration_from_rest_has_independent_relativistic_reference():
    game, start = ready_game()
    segment = accelerate_to(start, .1, 1e6)
    before = game.ship.antimatter_capsules
    prepared(game, segment, "accelerate")
    paid = before - game.ship.antimatter_capsules
    assert paid == pytest.approx(Engine().engine_fuel_cost(game, .5 * 500 * LIGHT_SPEED_M_S / 9.4607304725808e15, .5))
    loop = GameLoop(Engine(), game)
    owners = tuple(getattr(game, name) for name in ("ship", "clock", "world", "events", "meta"))
    loop.step(10)
    p = 1e6 * 10 / LIGHT_SPEED_M_S
    expected_beta = p / math.hypot(1, p)
    expected_x = (LIGHT_SPEED_M_S ** 2 / 1e6) * (math.hypot(1, p) - 1)
    expected_tau = (LIGHT_SPEED_M_S / 1e6) * math.asinh(p)
    motion = game.ship.physical_transit.motion
    assert motion.beta == pytest.approx(expected_beta)
    assert motion.distance_m == pytest.approx(expected_x, rel=1e-12)
    assert game.clock.ship_elapsed_s == pytest.approx(expected_tau)
    assert game.clock.bio_elapsed_s == pytest.approx(expected_tau)
    assert game.ship.antimatter_capsules == before - paid
    assert all(getattr(game, name) is owner for name, owner in
               zip(("ship", "clock", "world", "events", "meta"), owners))
    assert game.ship.power.e_batt_kwh > 3.0
    assert game.ship.hull_integrity < 1.0
    assert game.ship.systems["life_support"].health < 1.0


def test_acceleration_from_positive_beta_and_partition_are_continuous():
    game, start = ready_game(.2)
    segment = accelerate_to(start, .3, 1e6)
    prepared(game, segment, "accelerate")
    whole = deepcopy(game)
    Engine().tick(whole, 20)
    Engine().tick(game, 7)
    Engine().tick(game, 13)
    assert game.ship.physical_transit.motion == whole.ship.physical_transit.motion
    assert game.clock.ship_elapsed_s == whole.clock.ship_elapsed_s
    assert game.ship.hull_integrity == pytest.approx(whole.ship.hull_integrity)
    assert game.ship.systems["life_support"].health == pytest.approx(whole.ship.systems["life_support"].health)
    p0 = .2 / math.sqrt(1 - .2 ** 2)
    p1 = p0 + 1e6 * 20 / LIGHT_SPEED_M_S
    assert game.ship.physical_transit.motion.beta == pytest.approx(p1 / math.hypot(1, p1))
    assert game.ship.physical_transit.motion.distance_m == pytest.approx(
        LIGHT_SPEED_M_S ** 2 / 1e6 * (math.hypot(1, p1) - math.hypot(1, p0)))


def test_braking_to_rest_does_not_arrive_or_reverse():
    game, start = ready_game(.5)
    segment = brake_to_stop(start, 1e7)
    prepared(game, segment, "brake")
    fuel = game.ship.antimatter_capsules
    duration = segment.duration_galactic_s
    events = Engine().tick(game, duration)
    motion = game.ship.physical_transit.motion
    assert motion.beta == 0
    assert motion.distance_m > 0
    p0 = .5 / math.sqrt(1 - .5 ** 2)
    expected_x = LIGHT_SPEED_M_S ** 2 / 1e7 * (math.hypot(1, p0) - 1)
    expected_tau = LIGHT_SPEED_M_S / 1e7 * math.asinh(p0)
    assert motion.distance_m == pytest.approx(expected_x, rel=1e-12)
    assert game.clock.ship_elapsed_s == pytest.approx(expected_tau)
    assert game.ship.antimatter_capsules == fuel
    assert game.ship.physical_transit.braking_started
    assert game.world.current_node_id != "COAST_DEST"
    assert not any(event.type == EventType.ARRIVED for event in events)
    with pytest.raises(RuntimeError, match="beyond this segment"):
        Engine().tick(game, 1)


def test_coast_then_brake_uses_exact_endpoint_and_new_paid_leg():
    game, start = ready_game(.5)
    coast = coast_for(start, 10)
    Engine().prepare_physical_segment(game, coast, "COAST_DEST", "coast")
    initial_fuel = game.ship.antimatter_capsules
    Engine().tick(game, 10)
    endpoint = game.ship.physical_transit.motion
    brake = brake_to_stop(endpoint, 1e7)
    prepared(game, brake, "brake")
    assert game.ship.antimatter_capsules < initial_fuel
    assert game.ship.physical_transit.motion == endpoint
    Engine().tick(game, 5)
    assert game.ship.physical_transit.motion.distance_m > endpoint.distance_m
    assert game.ship.physical_transit.motion.beta < endpoint.beta


def test_accelerate_coast_brake_chain_preserves_pose_and_charges_each_powered_leg():
    game, start = ready_game()
    acceleration = accelerate_to(start, .1, 1e6)
    initial_fuel = game.ship.antimatter_capsules
    prepared(game, acceleration, "accelerate")
    after_accel_payment = game.ship.antimatter_capsules
    Engine().tick(game, acceleration.duration_galactic_s)
    a_end = game.ship.physical_transit.motion
    coast = coast_for(a_end, 2)
    Engine().prepare_physical_segment(game, coast, "COAST_DEST", "coast")
    assert game.ship.physical_transit.motion == a_end
    assert game.ship.antimatter_capsules == after_accel_payment
    Engine().tick(game, 2)
    coast_end = game.ship.physical_transit.motion
    brake = brake_to_stop(coast_end, 1e7)
    prepared(game, brake, "brake")
    assert game.ship.physical_transit.motion == coast_end
    assert game.ship.antimatter_capsules < after_accel_payment < initial_fuel
    Engine().tick(game, brake.duration_galactic_s)
    assert game.ship.physical_transit.motion.beta == 0
    with pytest.raises(RuntimeError, match="cannot resume acceleration"):
        Engine().prepare_physical_segment(
            game, accelerate_to(game.ship.physical_transit.motion, .1, 1e6),
            "COAST_DEST", "accelerate", pricing_speed=.5)


def test_unpaid_and_insufficiently_funded_maneuvers_are_atomic():
    game, start = ready_game(.5)
    segment = brake_to_stop(start, 1e7)
    game.ship.physical_transit = PhysicalTransitState(segment, 0, "COAST_DEST", "brake", braking_started=True)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="authorization"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before
    game.ship.physical_transit = None
    game.ship.antimatter_capsules = 0
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="prepaid antimatter"):
        prepared(game, segment, "brake")
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("health,intent,allowed", [
    (.3500001, "accelerate", True), (.35, "accelerate", False),
    (.3499999, "accelerate", False),
    (.2, "brake", True), (.15, "brake", True),
    (.1499999, "brake", False),
])
def test_engine_integrity_capabilities(health, intent, allowed):
    game, start = ready_game(.5 if intent == "brake" else 0)
    engine = game.ship.systems["engines"]
    engine.health = health
    engine.state = (SystemState.DAMAGED if health >= .35 else SystemState.CRITICAL)
    engine.base_decay_per_s = 0
    engine.k_rad = 0
    segment = (brake_to_stop(start, 1e7) if intent == "brake"
               else accelerate_to(start, .1, 1e6))
    if allowed:
        prepared(game, segment, intent)
        Engine().tick(game, 1)
    else:
        before = pickle.dumps(game)
        with pytest.raises(RuntimeError, match="unavailable|35%"):
            prepared(game, segment, intent)
        assert pickle.dumps(game) == before


def test_effective_isolation_and_internal_35_percent_cut_reject_atomically():
    game, start = ready_game()
    segment = accelerate_to(start, .1, 1e6)
    game.ship.systems["engines"].forced_offline = True
    with pytest.raises(RuntimeError, match="unavailable"):
        prepared(game, segment, "accelerate")
    game.ship.systems["engines"].forced_offline = False
    prepared(game, segment, "accelerate")
    engine = game.ship.systems["engines"]
    engine.health = .350001
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .00001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="35%|causal boundary"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_electrical_and_deferred_radiation_cuts_preserve_state():
    game, start = ready_game(.5)
    prepared(game, brake_to_stop(start, 1e7), "brake")
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, 10)
    assert pickle.dumps(game) == before
    game.ship.power.e_batt_kwh = 3
    before = pickle.dumps(game)
    deferred = TemporalLimit("internal_high", "proper", None,
                             validity="numerical_isolation_unresolved")
    with patch("retorno.core.engine.radiation_limits", return_value=(deferred,)):
        with pytest.raises(RuntimeError, match="causal boundary"):
            Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_exact_15_percent_with_positive_wear_cannot_brake_past_capacity():
    game, start = ready_game(.5)
    engine = game.ship.systems["engines"]
    engine.health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    engine.state = SystemState.CRITICAL
    engine.base_decay_per_s = .001
    prepared(game, brake_to_stop(start, 1e7), "brake")
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="15%"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_paid_receipt_survives_save_and_does_not_charge_each_tick():
    game, start = ready_game()
    segment = accelerate_to(start, .1, 1e6)
    receipt = prepared(game, segment, "accelerate").propulsion_authorization
    assert receipt is not None and receipt.segment == segment
    paid_balance = game.ship.antimatter_capsules
    Engine().tick(game, 3)
    with TemporaryDirectory() as folder:
        path = Path(folder) / "slot.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        game = loaded.state
    assert game.ship.physical_transit.propulsion_authorization == receipt
    Engine().tick(game, 2)
    assert game.ship.antimatter_capsules == paid_balance
    with pytest.raises(ValueError, match="bound"):
        replace(game.ship.physical_transit, active_segment=accelerate_to(start, .2, 1e6))


def test_hibernation_and_overshoot_do_not_create_arrival():
    game, start = ready_game(.5)
    game.ship.is_hibernating = True
    coast = coast_for(start, 501)
    Engine().prepare_physical_segment(game, coast, "COAST_DEST", "coast")
    Engine().tick(game, 501)
    assert game.ship.physical_transit.motion.distance_m > LIGHT_SPEED_M_S * .5 * 500
    segment = brake_to_stop(game.ship.physical_transit.motion, 1e7)
    prepared(game, segment, "brake")
    prior_bio = game.clock.bio_elapsed_s
    prior_proper = game.clock.ship_elapsed_s
    events = Engine().tick(game, 1)
    assert game.clock.bio_elapsed_s - prior_bio == pytest.approx(
        (game.clock.ship_elapsed_s - prior_proper) * Balance.HIBERNATION_BIO_AGE_RATE_NOMINAL)
    assert game.world.current_node_id != "COAST_DEST"
    assert not any(event.type == EventType.ARRIVED for event in events)


def test_late_propulsive_failure_keeps_paid_state_events_and_rng():
    game, start = ready_game(.5)
    prepared(game, brake_to_stop(start, 1e7), "brake")
    before = pickle.dumps(game)
    with patch.object(Engine, "_integrate_power_interval", side_effect=RuntimeError("staged failure")):
        with pytest.raises(RuntimeError, match="staged failure"):
            Engine().tick(game, 1)
    assert pickle.dumps(game) == before
