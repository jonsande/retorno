"""Real repair, authorization and physical recovery through Engine and GameLoop."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_physics import LIGHT_SPEED_M_S, accelerate_to, sample_segment
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.model.events import EventType
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_repair_inertia import enqueue_repair, repairable_inertia
from tests.test_nav_engine_safety_brake import save_and_load


def repaired_ship():
    game = repairable_inertia()
    job = enqueue_repair(game)
    GameLoop(Engine(), game).step(job.eta_s)
    assert game.ship.physical_transit.inertial_continuation is not None
    return game


def _owners(game):
    return tuple(getattr(game, name) for name in
                 ("ship", "clock", "world", "jobs", "events", "meta"))


def test_repair_to_destination_executes_paid_coast_and_brake_with_saves():
    game = repaired_ship()
    game = save_and_load(game)
    loop = GameLoop(Engine(), game)
    plan = plan_inertial_recovery(game)
    assert plan.decision == "coast_then_brake"
    old_history = game.ship.physical_transit.inertial_continuation
    old_fuel = game.ship.antimatter_capsules
    old_node = game.world.current_node_id
    old_links = deepcopy(game.world.known_links)
    old_rng = game.meta.rng_counter
    owners = _owners(game)
    active = Engine().prepare_inertial_recovery(game, plan)
    receipt = active.recovery_execution.authorization
    assert game.ship.antimatter_capsules == pytest.approx(old_fuel - receipt.capsules_paid)
    assert active.recovery_execution.inertial_history == old_history
    assert active.propulsion_authorization is None and active.nominal_plan is None
    assert active.recovery_execution.inertial_history.nominal_plan.invalidated
    assert active.recovery_execution.inertial_history.braking_substitution is not None
    assert _owners(game) == owners
    game = save_and_load(game)
    loop = GameLoop(Engine(), game)
    owners = _owners(game)
    coast = plan.coast_segment
    assert coast is not None
    start = game.ship.physical_transit.motion
    old_health = game.ship.systems["engines"].health
    old_hull = game.ship.hull_integrity
    old_battery = game.ship.drones["D1"].battery
    loop.step(coast.duration_galactic_s / 2)
    assert _owners(game) == owners
    current = game.ship.physical_transit.motion
    assert current.beta == start.beta
    assert current.distance_m == pytest.approx(
        start.distance_m + LIGHT_SPEED_M_S * start.beta * coast.duration_galactic_s / 2)
    assert game.clock.t == current.galactic_s
    assert game.clock.ship_elapsed_s == current.proper_s
    assert game.ship.systems["engines"].health < old_health
    assert game.ship.hull_integrity < old_hull
    assert game.ship.drones["D1"].battery < old_battery
    game = save_and_load(game)
    loop = GameLoop(Engine(), game)
    owners = _owners(game)
    loop.step(coast.duration_galactic_s / 2)
    assert _owners(game) == owners
    assert game.ship.physical_transit.intent == "brake"
    assert game.ship.physical_transit.motion == plan.braking_segment.start
    assert game.ship.antimatter_capsules == pytest.approx(old_fuel - receipt.capsules_paid)
    game = save_and_load(game)
    loop = GameLoop(Engine(), game)
    owners = _owners(game)
    brake = plan.braking_segment
    loop.step(brake.duration_galactic_s / 2)
    assert _owners(game) == owners
    middle = game.ship.physical_transit.motion
    assert 0 < middle.beta < start.beta
    assert middle.distance_m > plan.braking_segment.start.distance_m
    expected = sample_segment(brake, brake.duration_galactic_s / 2)
    assert middle.distance_m == pytest.approx(expected.distance_m, abs=1e-4)
    assert middle.beta == pytest.approx(expected.beta, abs=1e-14)
    game = save_and_load(game)
    loop = GameLoop(Engine(), game)
    owners = _owners(game)
    loop.step(brake.duration_galactic_s / 2)
    assert _owners(game) == owners
    assert game.ship.physical_transit is None
    assert sample_segment(brake, brake.duration_galactic_s).distance_m == pytest.approx(plan.destination_distance_m, abs=1)
    assert game.world.current_node_id == "NOMINAL_B"
    assert game.world.known_links == old_links
    assert game.ship.antimatter_capsules == pytest.approx(old_fuel - receipt.capsules_paid)
    assert game.meta.rng_counter == old_rng
    assert sum(e.type == EventType.ARRIVED for e in game.events.recent) == 1
    game = save_and_load(game)
    owners = _owners(game)
    Engine().tick(game, 1)
    assert sum(e.type == EventType.ARRIVED for e in game.events.recent) == 1
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="interrupted physical brake"):
        Engine().prepare_inertial_recovery(game)
    with pytest.raises((RuntimeError, ValueError)):
        Engine().prepare_physical_segment(
            game, accelerate_to(sample_segment(brake, brake.duration_galactic_s), .1, 1e7), "NOMINAL_B",
            "accelerate", pricing_speed=.1)
    assert pickle.dumps(game) == before
    assert _owners(game) == owners


def test_late_real_repair_recovery_brakes_through_destination_and_stops_beyond():
    game = repaired_ship()
    first = plan_inertial_recovery(game)
    assert first.decision == "coast_then_brake"
    # Continue unpowered beyond the last braking point. No geometry or health edits.
    GameLoop(Engine(), game).step(first.coast_segment.duration_galactic_s + 3)
    plan = plan_inertial_recovery(game)
    assert plan.decision == "emergency_brake"
    assert plan.start.distance_m < plan.destination_distance_m
    fuel = game.ship.antimatter_capsules
    node = game.world.current_node_id
    Engine().prepare_inertial_recovery(game, plan)
    receipt = game.ship.physical_transit.recovery_execution.authorization
    brake = plan.braking_segment
    assert brake.start == plan.start
    assert game.ship.antimatter_capsules == pytest.approx(fuel - receipt.capsules_paid)
    game = save_and_load(game)
    loop = GameLoop(Engine(), game)
    # The destination is crossed while beta remains strictly positive.
    lo, hi = 0.0, brake.duration_galactic_s
    for _ in range(50):
        mid = (lo + hi) / 2
        if sample_segment(brake, mid).distance_m < plan.destination_distance_m:
            lo = mid
        else:
            hi = mid
    crossing_step = hi + 1e-6
    loop.step(crossing_step)
    assert game.ship.physical_transit.motion.distance_m >= plan.destination_distance_m
    assert game.ship.physical_transit.motion.beta > 0
    assert game.world.current_node_id == node
    game = save_and_load(game)
    GameLoop(Engine(), game).step(brake.duration_galactic_s - crossing_step)
    assert game.ship.physical_transit is None
    assert sample_segment(brake, brake.duration_galactic_s).distance_m > plan.destination_distance_m
    assert game.world.current_node_id == game.world.active_tmp_node_id
    assert game.world.current_node_id != node
    assert game.ship.antimatter_capsules == pytest.approx(fuel - receipt.capsules_paid)


def test_one_tick_crosses_recovery_transition_atomically():
    game = repaired_ship()
    plan = plan_inertial_recovery(game)
    Engine().prepare_inertial_recovery(game, plan)
    before = game.ship.physical_transit.motion
    GameLoop(Engine(), game).step(plan.coast_segment.duration_galactic_s + 1)
    current = game.ship.physical_transit.motion
    assert current.beta < before.beta
    assert current.distance_m > plan.braking_segment.start.distance_m
    assert game.ship.physical_transit.intent == "brake"
    other = repaired_ship()
    full = plan_inertial_recovery(other)
    Engine().prepare_inertial_recovery(other, full)
    last = full.segments[-1]
    GameLoop(Engine(), other).step(last.start.galactic_s + last.duration_galactic_s - other.clock.t)
    assert other.ship.physical_transit is None
    assert other.world.current_node_id == "NOMINAL_B"


def test_exact_boundary_starts_brake_now_without_an_inertial_leg():
    game = repaired_ship()
    from retorno.core.nav_physics import braking_profile
    from tests.test_nav_recovery import _route_at, _synthetic_inertia
    # An exactly representable remaining distance requires a zero origin in
    # the floating-point strict comparison used by the pure planner.
    _synthetic_inertia(game, .4, distance_m=0.0, acceleration=1e7)
    current = game.ship.physical_transit.motion
    deceleration = abs(game.ship.physical_transit.inertial_continuation.interrupted_segment.proper_acceleration_m_s2)
    exact_destination = current.distance_m + braking_profile(current.beta, deceleration).distance_m
    _route_at(game, exact_destination)
    # Keep the pure geometry conversion on the exact boundary while the
    # subsequent Engine tick still integrates the real physical segment.
    with patch("retorno.core.nav_recovery.light_years_to_metres", return_value=exact_destination):
        plan = plan_inertial_recovery(game)
        assert plan.decision == "brake_now"
        Engine().prepare_inertial_recovery(game, plan)
    assert game.ship.physical_transit.intent == "brake"
    assert len(game.ship.physical_transit.recovery_execution.segments) == 1
    GameLoop(Engine(), game).step(plan.braking_segment.duration_galactic_s)
    assert game.ship.physical_transit is None
    assert game.world.current_node_id == "NOMINAL_B"


def test_recovery_preparation_rejects_stale_external_capacity_and_fuel_atomically():
    game = repaired_ship()
    plan = plan_inertial_recovery(game)
    Engine().tick(game, 1)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="stale"):
        Engine().prepare_inertial_recovery(game, plan)
    assert pickle.dumps(game) == before
    external = plan_inertial_recovery(game, proper_deceleration_m_s2=1e7)
    for kwargs in ({}, {"proper_deceleration_m_s2": 2e7}):
        before = pickle.dumps(game)
        with pytest.raises(RuntimeError, match="stale"):
            Engine().prepare_inertial_recovery(game, external, **kwargs)
        assert pickle.dumps(game) == before
    game.ship.antimatter_capsules = 0
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="antimatter"):
        Engine().prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before


def test_recovery_preparation_rejects_missing_capacity_or_electricity_without_payment():
    for obstacle in ("engine", "power_path", "quality"):
        game = repaired_ship()
        if obstacle == "engine":
            game.ship.systems["engines"].health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH - 1e-6
        elif obstacle == "power_path":
            game.ship.systems["energy_distribution"].forced_offline = True
        else:
            game.ship.power.power_quality = .5
        before = pickle.dumps(game)
        with pytest.raises(RuntimeError):
            Engine().prepare_inertial_recovery(game)
        assert pickle.dumps(game) == before


def test_recovery_tick_rolls_back_later_electrical_radiological_and_engine_cuts():
    for obstacle in ("electrical", "radiological", "engine"):
        game = repaired_ship()
        plan = plan_inertial_recovery(game)
        Engine().prepare_inertial_recovery(game, plan)
        if obstacle == "electrical":
            game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
            patcher = None
        elif obstacle == "radiological":
            from retorno.core.nav_boundaries import TemporalLimit
            patcher = patch("retorno.core.engine.radiation_limits", return_value=(
                TemporalLimit("deferred_radiation", "proper", 1, validity="deferred"),))
        else:
            game.ship.systems["engines"].health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH + 1e-5
            patcher = None
        before = pickle.dumps(game)
        if patcher is None:
            with pytest.raises(RuntimeError):
                Engine().tick(game, plan.coast_segment.duration_galactic_s + 2)
        else:
            with patcher, pytest.raises(RuntimeError):
                Engine().tick(game, plan.coast_segment.duration_galactic_s + 2)
        assert pickle.dumps(game) == before
