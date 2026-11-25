"""Nominal rest-to-rest physical travel through the real engine state."""
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
from retorno.core.actions import RouteSolve, Travel
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, MotionState, coast_for,
                                       metres_to_light_years, sample_segment)
from retorno.core.nav_state import PhysicalTransitState
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.runtime.loop import GameLoop


def nominal_game(distance_m=LIGHT_SPEED_M_S * .5 * 500):
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
    game.world.space.nodes["NOMINAL_B"] = SpaceNode(
        "NOMINAL_B", "Nominal destination", "station",
        radiation_rad_per_s=.0002,
        x_ly=origin.x_ly + metres_to_light_years(distance_m),
        y_ly=origin.y_ly, z_ly=origin.z_ly,
    )
    game.world.known_nodes.add("NOMINAL_B")
    assert add_known_link(game.world, origin.node_id, "NOMINAL_B")
    return game


def prepare(game, acceleration=1e7):
    return Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=acceleration)


def durations(physical):
    return tuple(segment.duration_galactic_s for segment in physical.nominal_plan.segments)


def test_three_phase_one_tick_reaches_b_and_pays_once():
    game = nominal_game()
    initial_fuel = game.ship.antimatter_capsules
    initial_engine_health = game.ship.systems["engines"].health
    physical = prepare(game)
    nominal = physical.nominal_plan
    assert nominal is not None
    assert len(nominal.segments) == 3
    assert [seg.proper_acceleration_m_s2 for seg in nominal.segments] == [1e7, 0, -1e7]
    assert game.ship.antimatter_capsules == pytest.approx(initial_fuel - nominal.capsules_paid)
    assert nominal.capsules_paid == pytest.approx(
        Engine().engine_fuel_cost(game, metres_to_light_years(nominal.profile.distance_m), nominal.pricing_speed),
        rel=1e-3)
    loop = GameLoop(Engine(), game)
    root = loop.get_state_snapshot()
    owners = {key: getattr(root, key) for key in ("ship", "clock", "world", "events", "meta")}
    total = sum(durations(physical))
    events = loop.step(total)
    motion = sample_segment(nominal.segments[-1], nominal.segments[-1].duration_galactic_s)
    assert game.ship.physical_transit is None
    assert motion.beta == 0
    assert motion.distance_m == pytest.approx(nominal.profile.distance_m, abs=Engine._nominal_distance_tolerance(nominal.profile.distance_m))
    expected_tau = (2 * LIGHT_SPEED_M_S / 1e7 * math.atanh(nominal.profile.peak_beta)
                    + nominal.profile.cruise_galactic_s * math.sqrt(1 - nominal.profile.peak_beta ** 2))
    assert game.clock.ship_elapsed_s == pytest.approx(expected_tau)
    assert game.clock.bio_elapsed_s == pytest.approx(expected_tau)
    assert game.clock.t == pytest.approx(total)
    assert game.clock.last_dt == total
    assert game.world.current_pos_ly[0] == pytest.approx(game.world.space.nodes["NOMINAL_B"].x_ly)
    assert game.ship.antimatter_capsules == initial_fuel - nominal.capsules_paid
    assert game.ship.systems["engines"].health < initial_engine_health
    assert game.ship.hull_integrity < 1
    assert game.ship.power.e_batt_kwh > 3
    assert all(getattr(root, key) is value for key, value in owners.items())
    assert game.world.current_node_id == "NOMINAL_B"
    assert sum(event.type == EventType.ARRIVED for event in events) == 1
    Engine().tick(game, 1)
    assert sum(event.type == EventType.ARRIVED for event in game.events.recent) == 1


def test_short_route_has_direct_acceleration_to_braking_transition():
    game = nominal_game(distance_m=1e9)
    physical = prepare(game)
    nominal = physical.nominal_plan
    assert nominal is not None and not nominal.profile.has_cruise
    assert len(nominal.segments) == 2
    first, second = durations(physical)
    fuel = game.ship.antimatter_capsules
    Engine().tick(game, first)
    assert game.ship.physical_transit.intent == "brake"
    assert game.ship.physical_transit.motion == nominal.segments[1].start
    assert game.ship.antimatter_capsules == fuel
    Engine().tick(game, second)
    assert game.ship.physical_transit is None
    assert game.world.current_node_id == "NOMINAL_B"


def test_whole_and_phase_split_have_same_physical_and_subsystem_state():
    whole = nominal_game()
    physical = prepare(whole)
    split = deepcopy(whole)
    phase_times = durations(physical)
    Engine().tick(whole, sum(phase_times))
    for length in phase_times:
        Engine().tick(split, length)
    assert split.ship.physical_transit is whole.ship.physical_transit is None
    assert split.world.current_pos_ly == whole.world.current_pos_ly
    assert split.clock.t == whole.clock.t
    assert split.clock.ship_elapsed_s == whole.clock.ship_elapsed_s
    assert split.clock.bio_elapsed_s == whole.clock.bio_elapsed_s
    assert split.ship.antimatter_capsules == whole.ship.antimatter_capsules
    assert split.ship.power.e_batt_kwh == pytest.approx(whole.ship.power.e_batt_kwh)
    assert split.ship.hull_integrity == pytest.approx(whole.ship.hull_integrity)
    for key in whole.ship.systems:
        assert split.ship.systems[key].health == pytest.approx(whole.ship.systems[key].health)


def test_one_tick_crosses_first_and_second_phase_without_recharging():
    game = nominal_game()
    physical = prepare(game)
    first, coast, _ = durations(physical)
    paid_balance = game.ship.antimatter_capsules
    Engine().tick(game, first + coast + 1)
    assert game.ship.physical_transit.intent == "brake"
    assert 0 < game.ship.physical_transit.elapsed_galactic_s < game.ship.physical_transit.active_segment.duration_galactic_s
    assert game.ship.antimatter_capsules == paid_balance


@pytest.mark.parametrize("phase", ["accelerate", "coast", "brake", "complete"])
def test_nominal_state_round_trips_through_save_in_every_phase(phase):
    game = nominal_game()
    physical = prepare(game)
    first, coast, brake = durations(physical)
    if phase == "accelerate":
        Engine().tick(game, first / 2)
    elif phase == "coast":
        Engine().tick(game, first + coast / 2)
    elif phase == "brake":
        Engine().tick(game, first + coast + brake / 2)
    else:
        Engine().tick(game, sum((first, coast, brake)))
    with TemporaryDirectory() as folder:
        path = Path(folder) / "slot.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        restored = loaded.state
    assert restored.ship.physical_transit == game.ship.physical_transit
    assert restored.ship.antimatter_capsules == game.ship.antimatter_capsules
    if phase != "complete":
        remaining = (restored.ship.physical_transit.nominal_plan.segments[-1].start.galactic_s
                     + restored.ship.physical_transit.nominal_plan.segments[-1].duration_galactic_s
                     - restored.clock.t)
        Engine().tick(restored, remaining)
        assert restored.ship.physical_transit is None
        assert restored.world.current_node_id == "NOMINAL_B"


def test_preparation_rejects_unknown_route_and_insufficient_fuel_atomically():
    game = nominal_game()
    game.world.known_links.clear()
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="known linked"):
        prepare(game)
    assert pickle.dumps(game) == before
    add_known_link(game.world, game.ship.current_node_id, "NOMINAL_B")
    game.ship.antimatter_capsules = 0
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="prepaid antimatter"):
        prepare(game)
    assert pickle.dumps(game) == before


def test_nominal_authorization_cannot_change_destination_or_active_phase():
    game = nominal_game()
    physical = prepare(game)
    nominal = physical.nominal_plan
    assert nominal is not None
    with pytest.raises(ValueError, match="authorize"):
        replace(physical, original_destination_id="OTHER")
    with pytest.raises(ValueError, match="authorize"):
        replace(physical, nominal_plan=replace(nominal, phase_index=1))
    bad_future = coast_for(nominal.segments[1].start,
                           nominal.segments[1].duration_galactic_s + 1)
    with pytest.raises(ValueError, match="plan|cruise|continuous"):
        replace(nominal, segments=(nominal.segments[0], bad_future, nominal.segments[2]))
    assert game.ship.physical_transit == physical


def test_request_past_nominal_endpoint_is_atomic():
    game = nominal_game()
    physical = prepare(game)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="exceeds the nominal journey endpoint"):
        Engine().tick(game, sum(durations(physical)) + 1)
    assert pickle.dumps(game) == before


def test_invalidated_or_changed_route_cannot_spend_nominal_authorization():
    game = nominal_game()
    physical = prepare(game)
    game.ship.physical_transit = replace(
        physical, nominal_plan=replace(physical.nominal_plan, invalidated=True))
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="invalidated"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before
    game.ship.physical_transit = physical
    game.world.space.nodes["NOMINAL_B"].x_ly += .001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="route geometry"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_second_phase_failure_rejects_whole_tick_without_events_or_rng_changes():
    game = nominal_game()
    physical = prepare(game)
    first, _, _ = durations(physical)
    before = pickle.dumps(game)
    original = Engine._tick_physical_segment
    def fail_on_coast(self, staged, dt):
        if staged.ship.physical_transit.nominal_plan.phase_index == 1:
            raise RuntimeError("second phase failed")
        return original(self, staged, dt)
    with patch.object(Engine, "_tick_physical_segment", new=fail_on_coast):
        with pytest.raises(RuntimeError, match="second phase failed"):
            Engine().tick(game, first + 1)
    assert pickle.dumps(game) == before


def test_deferred_radiation_and_health_boundary_reject_whole_operation():
    game = nominal_game()
    prepare(game)
    before = pickle.dumps(game)
    deferred = TemporalLimit("internal_high", "proper", None,
                             validity="numerical_isolation_unresolved")
    with patch("retorno.core.engine.radiation_limits", return_value=(deferred,)):
        with pytest.raises(RuntimeError, match="causal boundary"):
            Engine().tick(game, 10)
    assert pickle.dumps(game) == before
    engine = game.ship.systems["engines"]
    engine.health = .36
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .0001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="35%|causal boundary"):
        Engine().tick(game, sum(durations(game.ship.physical_transit)))
    assert pickle.dumps(game) == before


def test_electrical_internal_cut_rejects_nominal_tick_atomically():
    game = nominal_game()
    prepare(game)
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, 100)
    assert pickle.dumps(game) == before


def test_one_metre_per_second_squared_accepts_short_route_and_rejects_long_cut():
    short = nominal_game(distance_m=1e5)
    physical = prepare(short, acceleration=1.0)
    assert len(physical.nominal_plan.segments) == 2
    Engine().tick(short, sum(durations(physical)))
    assert short.ship.physical_transit is None
    assert short.world.current_node_id == "NOMINAL_B"
    long = nominal_game(distance_m=LIGHT_SPEED_M_S * .5 * 500)
    physical = prepare(long, acceleration=1.0)
    before = pickle.dumps(long)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(long, sum(durations(physical)))
    assert pickle.dumps(long) == before


def test_nominal_hibernation_and_public_action_block():
    game = nominal_game()
    game.ship.is_hibernating = True
    physical = prepare(game)
    loop = GameLoop(Engine(), game)
    fuel = game.ship.antimatter_capsules
    for action in (Travel("NOMINAL_B"), RouteSolve("NOMINAL_B")):
        events = loop.apply_action(action)
        assert len(events) == 1 and events[0].data["reason"] == "physical_in_transit"
    loop.step(sum(durations(physical)))
    assert game.clock.bio_elapsed_s == pytest.approx(
        game.clock.ship_elapsed_s * Balance.HIBERNATION_BIO_AGE_RATE_NOMINAL)
    assert game.ship.antimatter_capsules == fuel


def test_old_physical_slot_pickle_payload_defaults_to_no_nominal_plan():
    segment = coast_for(MotionState(0, 0, .5, 0), 10)
    current = PhysicalTransitState(segment, 0, "NOMINAL_B", "coast")
    old_payload = current.__getstate__()[:-1]
    restored = object.__new__(PhysicalTransitState)
    restored.__setstate__(old_payload)
    assert restored == current
