"""Causal unpowered continuation after the 15% braking cut."""
from copy import deepcopy
from dataclasses import replace
import math
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.actions import RouteSolve, Travel
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import LIGHT_SPEED_M_S, brake_to_stop, light_years_to_metres
from retorno.core.nav_state import InertialContinuation
from retorno.model.events import EventType
from retorno.model.jobs import Job, JobStatus, JobType
from retorno.model.systems import SystemState
from retorno.model.world import distance_between_nodes_ly
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_safety_brake import (
    nominal_game, pending_coast, save_and_load, wear_cut,
)


def safety_cut():
    game = pending_coast()
    game.ship.systems["engines"].base_decay_per_s = .04
    Engine().tick(game, 1)
    active = game.ship.physical_transit
    cut = wear_cut(game, .15)
    assert cut is not None and cut < active.active_segment.duration_galactic_s
    Engine().tick(game, cut - active.elapsed_galactic_s)
    assert game.ship.physical_transit.pending_transition == "inertia"
    assert game.ship.physical_transit.motion.beta > 0
    return game


def nominal_cut():
    game = nominal_game()
    prepared = Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=1e7)
    Engine().tick(game, prepared.active_segment.duration_galactic_s)
    engine = game.ship.systems["engines"]
    engine.health = .16
    engine.state = SystemState.CRITICAL
    engine.base_decay_per_s = .04
    engine.k_rad = 0
    cut = wear_cut(game, .15)
    assert cut is not None
    Engine().tick(game, cut)
    assert game.ship.physical_transit.pending_transition == "inertia"
    return game


def assert_coast_from_cut(game, duration):
    prior = game.ship.physical_transit
    motion = prior.motion
    fuel = game.ship.antimatter_capsules
    clock = deepcopy(game.clock)
    rng = game.meta.rng_counter
    owners = tuple(getattr(game, key) for key in ("ship", "clock", "world", "events", "meta"))
    assert Engine().tick(game, 0) == []
    assert game.ship.physical_transit is prior
    GameLoop(Engine(), game).step(duration)
    active = game.ship.physical_transit
    assert isinstance(active.inertial_continuation, InertialContinuation)
    assert active.inertial_continuation.interrupted_segment == prior.active_segment
    assert active.inertial_continuation.interrupted_elapsed_galactic_s == prior.elapsed_galactic_s
    assert active.inertial_continuation.current_segment == active.active_segment
    assert active.nominal_braking_substitution is None
    assert active.propulsion_authorization is None
    assert active.pending_transition is None
    assert active.intent == "coast" and active.replan_required and active.braking_started
    assert active.active_segment.start == motion
    assert active.motion.beta == motion.beta
    assert active.motion.distance_m == pytest.approx(
        motion.distance_m + LIGHT_SPEED_M_S * motion.beta * duration)
    assert game.clock.t == pytest.approx(clock.t + duration)
    assert game.clock.ship_elapsed_s == pytest.approx(
        clock.ship_elapsed_s + duration * math.sqrt(1 - motion.beta * motion.beta))
    assert game.clock.bio_elapsed_s > clock.bio_elapsed_s
    assert game.ship.antimatter_capsules == fuel
    assert game.meta.rng_counter == rng
    assert all(getattr(game, key) is owner for key, owner in zip(
        ("ship", "clock", "world", "events", "meta"), owners))
    return prior, active


def test_full_sequence_crosses_real_destination_and_continues_beyond():
    game = save_and_load(safety_cut())
    cut, active = assert_coast_from_cut(game, 1)
    assert active.inertial_continuation.braking_substitution == cut.nominal_braking_substitution
    assert active.nominal_plan.invalidated
    assert game.ship.systems["engines"].health < .15
    saved = save_and_load(game)
    assert saved.ship.physical_transit == active
    # Keep the later, unrelated engine health floor out of this supported interval.
    saved.ship.systems["engines"].base_decay_per_s = 0
    origin_id = saved.ship.transit_from
    route_m = light_years_to_metres(distance_between_nodes_ly(
        saved.world, origin_id, "NOMINAL_B"))
    now = saved.ship.physical_transit.motion
    to_b = (route_m - now.distance_m) / (LIGHT_SPEED_M_S * now.beta)
    assert to_b > 0
    nodes = set(saved.world.space.nodes)
    known = set(saved.world.known_nodes)
    GameLoop(Engine(), saved).step(to_b)
    crossing = saved.ship.physical_transit.motion
    assert crossing.beta == now.beta
    assert crossing.distance_m == pytest.approx(route_m, abs=1)
    assert not any(event.type == EventType.ARRIVED for event in saved.events.recent)
    GameLoop(Engine(), saved).step(10)
    beyond = saved.ship.physical_transit.motion
    assert beyond.distance_m > route_m
    assert beyond.beta == crossing.beta
    assert saved.world.current_pos_ly[0] > saved.world.space.nodes["NOMINAL_B"].x_ly
    assert saved.ship.radiation_env_rad_per_s == saved.world.space.nodes["NOMINAL_B"].radiation_rad_per_s
    assert saved.world.current_node_id != "NOMINAL_B"
    assert set(saved.world.space.nodes) == nodes
    assert saved.world.known_nodes == known
    assert not any(event.type == EventType.ARRIVED for event in saved.events.recent)
    assert save_and_load(saved).ship.physical_transit == saved.ship.physical_transit


def test_nominal_braking_cut_preserves_paid_history_and_renews_coast():
    game = nominal_cut()
    fuel = game.ship.antimatter_capsules
    cut, active = assert_coast_from_cut(game, 1)
    assert active.nominal_plan == cut.nominal_plan
    assert active.inertial_continuation.nominal_plan == cut.nominal_plan
    assert active.inertial_continuation.braking_substitution is None
    first_end = active.motion
    Engine().tick(game, .5)
    assert game.ship.physical_transit.active_segment.start == first_end
    assert game.ship.physical_transit.motion.beta == first_end.beta
    assert game.ship.antimatter_capsules == fuel
    with pytest.raises(RuntimeError, match="inertial motion cannot prepare"):
        Engine().prepare_physical_segment(
            game, brake_to_stop(game.ship.physical_transit.motion, 1e7),
            "NOMINAL_B", "brake", pricing_speed=.5)
    assert save_and_load(game).ship.physical_transit == game.ship.physical_transit


def test_independent_braking_receipt_is_spent_history_not_new_propulsion():
    from tests.test_nav_engine_wear_cut import ready_game, prepared, _cut_time
    game, start = ready_game(.5)
    engine = game.ship.systems["engines"]
    engine.health = .16
    engine.state = SystemState.CRITICAL
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    segment = brake_to_stop(start, 1e7)
    receipt = prepared(game, segment, "brake").propulsion_authorization
    cut = _cut_time(game, .15, segment.duration_galactic_s)
    Engine().tick(game, cut)
    fuel = game.ship.antimatter_capsules
    _, active = assert_coast_from_cut(game, 1)
    assert active.inertial_continuation.propulsion_receipt == receipt
    assert active.propulsion_authorization is None
    assert game.ship.antimatter_capsules == fuel


@pytest.mark.parametrize("condition", ["exact_15", "below_15", "isolated", "offline"])
def test_inertia_ignores_engine_propulsion_capacity(condition):
    game = safety_cut()
    engine = game.ship.systems["engines"]
    engine.base_decay_per_s = 0
    engine.k_rad = 0
    if condition == "below_15":
        engine.health = .14
    if condition in {"isolated", "offline"}:
        engine.forced_offline = True
        engine.state = SystemState.OFFLINE
    before = game.ship.physical_transit.motion
    Engine().tick(game, 1)
    assert game.ship.physical_transit.motion.beta == before.beta
    assert game.ship.physical_transit.motion.distance_m > before.distance_m


def test_inertial_wear_electricity_and_biological_time_continue():
    game = safety_cut()
    game.ship.is_hibernating = True
    game.ship.systems["engines"].base_decay_per_s = .00001
    old_health = game.ship.systems["engines"].health
    old_battery = game.ship.power.e_batt_kwh
    old_hull = game.ship.hull_integrity
    old_bio = game.clock.bio_elapsed_s
    Engine().tick(game, 1)
    assert game.ship.systems["engines"].health < old_health
    assert game.ship.power.e_batt_kwh != old_battery
    assert game.ship.hull_integrity < old_hull
    assert game.clock.bio_elapsed_s > old_bio
    assert game.ship.physical_transit.motion.beta > 0


@pytest.mark.parametrize("obstacle", ["battery", "radiation", "jobs", "health"])
def test_inertial_activation_rejects_unresolved_cut_atomically(obstacle):
    game = safety_cut()
    if obstacle == "battery":
        game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    elif obstacle == "jobs":
        game.jobs.jobs["UNRESOLVED"] = Job("UNRESOLVED", JobType.REPAIR_SYSTEM,
                                           JobStatus.RUNNING, 10)
        game.jobs.active_job_ids.append("UNRESOLVED")
    elif obstacle == "health":
        system = game.ship.systems["life_support"]
        system.health = Balance.SYSTEM_HEALTH_DAMAGED + .000001
        system.state = SystemState.DAMAGED
        system.base_decay_per_s = .001
    before = pickle.dumps(game)
    if obstacle == "radiation":
        with patch("retorno.core.engine.radiation_limits", return_value=(
            TemporalLimit("internal_high", "proper", None,
                          validity="numerical_isolation_unresolved"),
        )):
            with pytest.raises(RuntimeError):
                Engine().tick(game, 1)
    else:
        with pytest.raises(RuntimeError):
            Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_safe_subdivision_agrees_with_one_unpowered_interval():
    game = safety_cut()
    game.ship.systems["engines"].base_decay_per_s = 0
    whole = deepcopy(game)
    Engine().tick(whole, 3)
    Engine().tick(game, 1)
    Engine().tick(game, 2)
    assert game.ship.physical_transit.motion.beta == whole.ship.physical_transit.motion.beta
    assert game.ship.physical_transit.motion.distance_m == pytest.approx(
        whole.ship.physical_transit.motion.distance_m)
    assert game.clock.ship_elapsed_s == pytest.approx(whole.clock.ship_elapsed_s)
    assert game.ship.hull_integrity == pytest.approx(whole.ship.hull_integrity)


def test_invalid_inertial_history_cannot_reauthorize_braking():
    game = safety_cut()
    Engine().tick(game, 1)
    physical = game.ship.physical_transit
    with pytest.raises(ValueError, match="inertial motion"):
        replace(physical, nominal_braking_substitution=physical.inertial_continuation.braking_substitution)
    with pytest.raises(ValueError, match="physical navigation intent|inertial motion"):
        replace(physical, intent="brake")
    shifted = replace(physical.active_segment.start,
                      distance_m=physical.active_segment.start.distance_m + 100)
    with pytest.raises(ValueError, match="discontinuous"):
        replace(physical.inertial_continuation,
                current_segment=replace(physical.active_segment, start=shifted))


def test_public_travel_and_route_solve_remain_blocked_during_inertia():
    game = safety_cut()
    Engine().tick(game, 1)
    before = game.ship.physical_transit.motion
    known = set(game.world.known_nodes)
    for action in (Travel("NOMINAL_B"), RouteSolve("NOMINAL_B")):
        events = Engine().apply_action(game, action)
        assert len(events) == 1 and events[0].type == EventType.BOOT_BLOCKED
        assert game.ship.physical_transit.motion == before
        assert game.world.known_nodes == known
