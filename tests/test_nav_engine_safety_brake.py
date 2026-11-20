"""Paid safety-brake substitution through real GameState, Engine and GameLoop."""
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
                                      brake_to_stop, light_years_to_metres,
                                      metres_to_light_years, sample_segment)
from retorno.core.nav_radiation import (RadiationProfile, first_integrated_wear_at,
                                        integrate_segment_radiation)
from retorno.core.nav_state import NominalBrakingSubstitution
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link, distance_between_nodes_ly
from retorno.runtime.loop import GameLoop


def nominal_game(distance_m=1e9):
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
    destination = "NOMINAL_B"
    game.world.space.nodes[destination] = SpaceNode(
        destination, "Nominal destination", "station", radiation_rad_per_s=.0002,
        x_ly=origin.x_ly + metres_to_light_years(distance_m),
        y_ly=origin.y_ly, z_ly=origin.z_ly,
    )
    game.world.known_nodes.add(destination)
    assert add_known_link(game.world, origin.node_id, destination)
    return game


def profile(game):
    origin = game.world.space.nodes[game.ship.transit_from]
    destination = game.world.space.nodes["NOMINAL_B"]
    length = light_years_to_metres(distance_between_nodes_ly(
        game.world, origin.node_id, destination.node_id))
    return RadiationProfile(0, length, origin.radiation_rad_per_s,
                            destination.radiation_rad_per_s)


def wear_cut(game, threshold):
    physical = game.ship.physical_transit
    segment = physical.active_segment
    return first_integrated_wear_at(
        game.ship.systems["engines"], profile(game), segment,
        physical.elapsed_galactic_s, segment.duration_galactic_s,
        game.ship.hull_integrity, threshold,
        in_transit=True, op_mode=game.ship.op_mode,
        hibernating=game.ship.is_hibernating,
        quality_proper_s_at=lambda exposure: exposure.proper_s,
    )


def pending_acceleration(distance_m=1e9):
    game = nominal_game(distance_m)
    initial_fuel = game.ship.antimatter_capsules
    prepared = Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=1e7)
    nominal = prepared.nominal_plan
    assert nominal is not None
    assert game.ship.antimatter_capsules == initial_fuel - nominal.capsules_paid
    engine = game.ship.systems["engines"]
    engine.health = .36
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    cut = wear_cut(game, .35)
    assert cut is not None
    GameLoop(Engine(), game).step(cut)
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    return game


def pending_coast():
    game = nominal_game(LIGHT_SPEED_M_S * .5 * 500)
    prepared = Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=1e7)
    assert len(prepared.nominal_plan.segments) == 3
    Engine().tick(game, prepared.active_segment.duration_galactic_s)
    engine = game.ship.systems["engines"]
    engine.health = .36
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    cut = wear_cut(game, .35)
    assert cut is not None
    Engine().tick(game, cut)
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    return game


def save_and_load(game):
    with TemporaryDirectory() as folder:
        path = Path(folder) / "slot.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        return loaded.state


def test_full_sequence_from_nominal_acceleration_to_real_safety_stop():
    game = pending_acceleration()
    suspended = game.ship.physical_transit
    before_motion = suspended.motion
    before_clock = deepcopy(game.clock)
    before_fuel = game.ship.antimatter_capsules
    before_rng = game.meta.rng_counter
    before_events = pickle.dumps(game.events)
    assert Engine().tick(game, 0) == []
    assert game.ship.physical_transit is suspended
    staged = deepcopy(game)
    Engine()._activate_safety_braking(staged)
    active = staged.ship.physical_transit
    assert active.motion == before_motion
    assert staged.clock == before_clock
    assert staged.ship.antimatter_capsules == before_fuel
    assert staged.meta.rng_counter == before_rng
    assert pickle.dumps(staged.events) == before_events
    assert active.safety_braking and active.braking_started
    assert active.pending_transition is None and active.replan_required
    assert active.nominal_plan.invalidated and not active.nominal_plan.completed
    assert active.nominal_braking_substitution.paid_plan == active.nominal_plan
    assert active.nominal_braking_substitution.braking_segment.start == before_motion
    assert active.nominal_braking_substitution.destination_id == "NOMINAL_B"
    assert active.nominal_braking_substitution.cause == "engine_integrity_35"
    assert active.propulsion_authorization is None
    owners = tuple(getattr(game, key) for key in ("ship", "clock", "world", "events", "meta"))
    events = GameLoop(Engine(), game).step(.5)
    physical = game.ship.physical_transit
    assert physical.active_segment == active.active_segment
    assert physical.intent == "brake"
    assert physical.motion.beta < before_motion.beta
    assert physical.motion.distance_m > before_motion.distance_m
    assert physical.motion.distance_m == pytest.approx(sample_segment(active.active_segment, .5).distance_m)
    assert game.clock.t == pytest.approx(before_clock.t + .5)
    assert game.ship.systems["engines"].state == SystemState.CRITICAL
    assert len([event for event in events if event.type == EventType.SYSTEM_STATE_CHANGED]) == 1
    assert game.meta.rng_counter == before_rng
    assert game.ship.antimatter_capsules == before_fuel
    assert all(getattr(game, key) is owner for key, owner in zip(
        ("ship", "clock", "world", "events", "meta"), owners))
    rest = physical.active_segment.duration_galactic_s - physical.elapsed_galactic_s
    GameLoop(Engine(), game).step(rest)
    stopped = game.ship.physical_transit
    assert stopped.motion.beta == 0
    assert stopped.nominal_braking_substitution.completed
    assert stopped.motion.distance_m < stopped.nominal_plan.profile.distance_m
    assert game.ship.antimatter_capsules == before_fuel
    assert game.world.current_node_id != "NOMINAL_B"
    assert not any(event.type == EventType.ARRIVED for event in game.events.recent)
    saved = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="already complete"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == saved


def test_coast_interruption_and_persistence_across_safety_braking():
    game = pending_coast()
    prior = game.ship.physical_transit.motion
    paid = game.ship.antimatter_capsules
    loaded = save_and_load(game)
    Engine().tick(loaded, 1)
    active = loaded.ship.physical_transit
    assert active.nominal_braking_substitution.interrupted_segment.proper_acceleration_m_s2 == 0
    assert active.nominal_braking_substitution.braking_segment.start == prior
    assert active.motion.beta < prior.beta
    assert active.nominal_plan.invalidated
    assert loaded.ship.antimatter_capsules == paid
    midway = save_and_load(loaded)
    assert midway.ship.physical_transit == active
    Engine().tick(midway, 1)
    assert midway.ship.physical_transit.motion.beta < active.motion.beta
    assert midway.ship.antimatter_capsules == paid
    remaining = (midway.ship.physical_transit.active_segment.duration_galactic_s
                 - midway.ship.physical_transit.elapsed_galactic_s)
    Engine().tick(midway, remaining)
    stopped = save_and_load(midway)
    assert stopped.ship.physical_transit.nominal_braking_substitution.completed
    assert stopped.ship.physical_transit.motion.beta == 0
    assert stopped.ship.antimatter_capsules == paid


def test_15_percent_during_safety_brake_defers_inertia_without_stopping():
    game = pending_acceleration()
    engine = game.ship.systems["engines"]
    engine.base_decay_per_s = .04
    Engine().tick(game, .1)
    assert engine is not game.ship.systems["engines"]  # Staged commit replaces nested systems.
    assert game.ship.systems["engines"].state == SystemState.CRITICAL
    cut = wear_cut(game, .15)
    assert cut is not None
    active = game.ship.physical_transit
    assert cut < active.active_segment.duration_galactic_s
    original = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut - active.elapsed_galactic_s + .1)
    assert pickle.dumps(game) == original
    Engine().tick(game, cut - active.elapsed_galactic_s)
    stopped = game.ship.physical_transit
    assert stopped.pending_transition == "inertia"
    assert stopped.nominal_braking_substitution is not None
    assert not stopped.nominal_braking_substitution.completed
    assert stopped.motion.beta > 0
    assert game.ship.systems["engines"].health == .15
    loaded = save_and_load(game)
    prior = loaded.ship.physical_transit.motion
    Engine().tick(loaded, 1)
    assert loaded.ship.physical_transit.intent == "coast"
    assert loaded.ship.physical_transit.motion.beta == prior.beta
    assert loaded.ship.physical_transit.motion.distance_m > prior.distance_m


def test_exact_15_percent_allows_safety_braking_when_wear_is_zero():
    game = pending_acceleration()
    engine = game.ship.systems["engines"]
    engine.health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    engine.state = SystemState.CRITICAL
    engine.base_decay_per_s = 0
    engine.k_rad = 0
    Engine().tick(game, .5)
    assert game.ship.physical_transit.safety_braking
    assert game.ship.physical_transit.motion.beta > 0
    assert game.ship.systems["engines"].health == .15


def test_exact_nominal_destination_still_has_no_public_arrival():
    game = nominal_game()
    prepared = Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=1e7)
    segment = prepared.active_segment
    exposure = integrate_segment_radiation(profile(game), segment, 0,
                                            segment.duration_galactic_s, game.ship.hull_integrity)
    engine = game.ship.systems["engines"]
    engine.health = .36
    engine.state = SystemState.DAMAGED
    engine.k_rad = 0
    engine.base_decay_per_s = .01 / (Balance.TRANSIT_WEAR_MULT_NORMAL * exposure.proper_s)
    for _ in range(32):
        if wear_cut(game, .35) == segment.duration_galactic_s:
            break
        engine.base_decay_per_s = math.nextafter(engine.base_decay_per_s, 0)
    else:
        pytest.fail("no representable limit at the phase end")
    Engine().tick(game, segment.duration_galactic_s)
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    paid = game.ship.antimatter_capsules
    Engine().tick(game, prepared.nominal_plan.segments[-1].duration_galactic_s)
    physical = game.ship.physical_transit
    assert physical.nominal_braking_substitution.completed
    assert physical.motion.beta == 0
    assert physical.motion.distance_m == pytest.approx(physical.nominal_plan.profile.distance_m, abs=1.0)
    assert game.ship.antimatter_capsules == paid
    assert not any(event.type == EventType.ARRIVED for event in game.events.recent)


def test_overshoot_with_shifted_endpoint_preserves_real_motion_and_radiation():
    # A valid fixed nominal geometry cannot overshoot under the same braking
    # acceleration. Shift the destination node after the cut to exercise the
    # provisional spatial policy past the *current* endpoint.
    game = pending_coast()
    motion = game.ship.physical_transit.motion
    brake = brake_to_stop(motion, game.ship.physical_transit.nominal_plan.profile.proper_acceleration_m_s2)
    target_distance_m = motion.distance_m + .25 * (sample_segment(brake, brake.duration_galactic_s).distance_m
                                                    - motion.distance_m)
    origin = game.world.space.nodes[game.ship.transit_from]
    destination = game.world.space.nodes["NOMINAL_B"]
    destination.x_ly = origin.x_ly + metres_to_light_years(target_distance_m)
    paid = game.ship.antimatter_capsules
    Engine().tick(game, brake.duration_galactic_s)
    physical = game.ship.physical_transit
    assert physical.nominal_braking_substitution.completed
    assert physical.motion.distance_m > light_years_to_metres(
        distance_between_nodes_ly(game.world, origin.node_id, destination.node_id))
    assert game.ship.radiation_env_rad_per_s == destination.radiation_rad_per_s
    assert game.world.current_pos_ly[0] > destination.x_ly
    assert game.ship.antimatter_capsules == paid
    assert game.world.current_node_id != "NOMINAL_B"
    assert not any(event.type == EventType.ARRIVED for event in game.events.recent)


def test_authorization_cannot_be_rebound_or_reused():
    game = pending_coast()
    Engine().tick(game, .1)
    physical = game.ship.physical_transit
    auth = physical.nominal_braking_substitution
    assert isinstance(auth, NominalBrakingSubstitution)
    with pytest.raises(ValueError, match="substitution|authorize"):
        replace(physical, nominal_braking_substitution=None)
    with pytest.raises(ValueError, match="substitut"):
        replace(physical, original_destination_id="OTHER")
    with pytest.raises(ValueError, match="substitut"):
        replace(physical, active_segment=brake_to_stop(physical.motion, 1e7))
    with pytest.raises(ValueError, match="interrupted paid nominal"):
        replace(auth, destination_id="OTHER")
    with pytest.raises(ValueError, match="original interruption"):
        replace(auth, braking_segment=brake_to_stop(auth.braking_segment.start, 2e7))
    assert physical.motion.beta > 0
    with pytest.raises(RuntimeError, match="safety braking cannot prepare"):
        Engine().prepare_physical_segment(
            game, accelerate_to(physical.motion, .99, 1e7),
            "NOMINAL_B", "accelerate", pricing_speed=.5)
    Engine().tick(game, physical.active_segment.duration_galactic_s - physical.elapsed_galactic_s)
    with pytest.raises(RuntimeError, match="safety braking cannot prepare"):
        Engine().prepare_physical_segment(
            game, brake_to_stop(MotionState(game.clock.t, physical.motion.distance_m, .1,
                                             game.clock.ship_elapsed_s), 1e7),
            "NOMINAL_B", "brake", pricing_speed=.5)


def test_independent_paid_segment_cannot_claim_nominal_braking():
    game = nominal_game()
    start = MotionState(0, 0, 0, 0)
    acceleration = accelerate_to(start, .1, 1e6)
    Engine().prepare_physical_segment(game, acceleration, "NOMINAL_B", "accelerate", pricing_speed=.5)
    engine = game.ship.systems["engines"]
    engine.health = .350001
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .00001
    engine.k_rad = 0
    cut = wear_cut(game, .35)
    assert cut is not None
    Engine().tick(game, cut)
    assert game.ship.physical_transit.nominal_plan is None
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="paid nominal journey"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("obstacle", ["engines", "power_core", "energy_distribution", "battery", "radiation", "health"])
def test_unresolved_cuts_or_missing_power_reject_transition_atomically(obstacle):
    game = pending_acceleration()
    if obstacle in {"engines", "power_core", "energy_distribution"}:
        game.ship.systems[obstacle].forced_offline = True
    elif obstacle == "battery":
        game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
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


def test_safe_subdivision_matches_whole_brake_and_preserves_nominal_behavior():
    game = pending_acceleration()
    whole = deepcopy(game)
    paid = game.ship.antimatter_capsules
    Engine().tick(whole, 2)
    Engine().tick(game, .5)
    Engine().tick(game, 1.5)
    assert game.ship.physical_transit.motion == whole.ship.physical_transit.motion
    assert game.ship.antimatter_capsules == whole.ship.antimatter_capsules == paid
    assert game.ship.systems["engines"].health == pytest.approx(whole.ship.systems["engines"].health)
    ordinary = nominal_game()
    physical = Engine().prepare_nominal_physical_travel(
        ordinary, "NOMINAL_B", proper_acceleration_m_s2=1e7)
    for segment in physical.nominal_plan.segments:
        Engine().tick(ordinary, segment.duration_galactic_s)
    assert ordinary.ship.physical_transit.nominal_plan.completed
    assert ordinary.ship.physical_transit.motion.beta == 0
