"""Causal engine-integrity cuts through the productive physical Engine path."""
from copy import deepcopy
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
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, MotionState, brake_to_stop,
                                      metres_to_light_years, proper_time_in_segment, sample_segment)
from retorno.core.nav_radiation import (RadiationProfile, first_integrated_wear_at,
                                        integrate_segment_radiation, integrated_system_wear)
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
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
    game.world.space.nodes["NOMINAL_B"] = SpaceNode(
        "NOMINAL_B", "Nominal destination", "station",
        radiation_rad_per_s=.0002,
        x_ly=origin.x_ly + metres_to_light_years(distance_m),
        y_ly=origin.y_ly, z_ly=origin.z_ly,
    )
    game.world.known_nodes.add("NOMINAL_B")
    assert add_known_link(game.world, origin.node_id, "NOMINAL_B")
    return game


def ready_game(beta=.5):
    game = nominal_game(LIGHT_SPEED_M_S * .5 * 500)
    game.ship.transit_from = game.ship.current_node_id
    return game, MotionState(0, 0, beta, 0)


def prepared(game, segment, intent):
    return Engine().prepare_physical_segment(
        game, segment, "NOMINAL_B", intent, pricing_speed=.5)


def prepare(game, acceleration=1e7):
    return Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=acceleration)


def _profile(game, destination_id):
    origin = game.world.space.nodes[game.ship.transit_from]
    destination = game.world.space.nodes[destination_id]
    segment = game.ship.physical_transit.active_segment
    return RadiationProfile(0, game.ship.physical_transit.nominal_plan.profile.distance_m
                            if game.ship.physical_transit.nominal_plan else
                            math.dist((origin.x_ly, origin.y_ly, origin.z_ly),
                                      (destination.x_ly, destination.y_ly, destination.z_ly)) * 9.4607304725808e15,
                            origin.radiation_rad_per_s, destination.radiation_rad_per_s)


def _cut_time(game, threshold, horizon):
    physical = game.ship.physical_transit
    engine = game.ship.systems["engines"]
    return first_integrated_wear_at(
        engine, _profile(game, physical.original_destination_id), physical.active_segment,
        physical.elapsed_galactic_s, horizon, game.ship.hull_integrity,
        threshold, in_transit=True, op_mode=game.ship.op_mode,
        hibernating=game.ship.is_hibernating,
        quality_proper_s_at=lambda exposure: exposure.proper_s,
    )


def _critical_nominal(distance_m=1e9):
    game = nominal_game(distance_m)
    physical = prepare(game, acceleration=1e7)
    engine = game.ship.systems["engines"]
    engine.health = .36
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    return game, physical


def test_acceleration_cut_matches_independent_constant_wear_reference_and_is_atomic():
    game, physical = _critical_nominal()
    segment = physical.active_segment
    # With k_rad=0 and quality=1, the independent constant-rate reference is
    # delta-health / (base decay * existing transit multiplier) proper seconds.
    expected_proper = (.36 - .35) / (.001 * Balance.TRANSIT_WEAR_MULT_NORMAL)
    cut = _cut_time(game, .35, segment.duration_galactic_s)
    assert cut > expected_proper
    assert proper_time_in_segment(segment, cut) == pytest.approx(expected_proper, rel=1e-8)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut + .1)
    assert pickle.dumps(game) == before
    fuel = game.ship.antimatter_capsules
    owners = [game.ship, game.clock, game.world, game.events, game.meta]
    events = GameLoop(Engine(), game).step(cut)
    motion = game.ship.physical_transit.motion
    assert motion.distance_m == pytest.approx(sample_segment(segment, cut).distance_m)
    assert motion.beta == pytest.approx(sample_segment(segment, cut).beta)
    assert game.clock.t == pytest.approx(cut)
    assert game.clock.ship_elapsed_s == pytest.approx(expected_proper)
    assert game.clock.bio_elapsed_s == pytest.approx(expected_proper)
    assert game.ship.systems["engines"].health == .35
    assert game.ship.systems["engines"].state == SystemState.DAMAGED
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    assert not game.ship.physical_transit.safety_braking
    assert not game.ship.physical_transit.braking_started
    assert game.ship.physical_transit.replan_required
    assert game.ship.physical_transit.nominal_plan.invalidated
    assert game.ship.physical_transit.original_destination_id == "NOMINAL_B"
    assert game.ship.antimatter_capsules == fuel
    assert not any(event.type == EventType.ARRIVED for event in events)
    assert all(current is original for current, original in zip(
        (game.ship, game.clock, game.world, game.events, game.meta), owners))
    Engine().tick(game, 1)
    assert game.ship.physical_transit.safety_braking
    assert game.ship.physical_transit.nominal_plan.invalidated
    assert game.ship.antimatter_capsules == fuel


def test_nominal_cut_save_load_and_phase_end_simultaneity():
    game, physical = _critical_nominal()
    segment = physical.active_segment
    # Place the first 35% equality at the exact end of the acceleration phase.
    exposure = integrate_segment_radiation(
        _profile(game, "NOMINAL_B"), segment, 0, segment.duration_galactic_s,
        game.ship.hull_integrity,
    )
    engine = game.ship.systems["engines"]
    engine.base_decay_per_s = .01 / (Balance.TRANSIT_WEAR_MULT_NORMAL * exposure.proper_s)
    for _ in range(32):
        if _cut_time(game, .35, segment.duration_galactic_s) == segment.duration_galactic_s:
            break
        engine.base_decay_per_s = math.nextafter(engine.base_decay_per_s, 0)
    else:
        pytest.fail("could not place the representable wear limit at phase end")
    Engine().tick(game, segment.duration_galactic_s)
    physical = game.ship.physical_transit
    assert physical.pending_transition == "safety_brake"
    assert physical.nominal_plan.phase_index == 0
    assert physical.nominal_plan.invalidated
    assert physical.motion == sample_segment(segment, segment.duration_galactic_s)
    with TemporaryDirectory() as folder:
        path = Path(folder) / "slot.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        restored = loaded.state
    assert restored.ship.physical_transit == physical
    assert restored.ship.antimatter_capsules == game.ship.antimatter_capsules
    Engine().tick(restored, 1)
    assert restored.ship.physical_transit.safety_braking
    assert restored.ship.physical_transit.nominal_plan.invalidated


def test_safe_acceleration_before_cut_survives_save_and_reforecast():
    game, physical = _critical_nominal()
    initial_fuel = game.ship.antimatter_capsules
    cut = _cut_time(game, .35, physical.active_segment.duration_galactic_s)
    Engine().tick(game, cut / 2)
    assert game.ship.physical_transit.pending_transition is None
    assert not game.ship.physical_transit.nominal_plan.invalidated
    assert game.ship.systems["engines"].health > .35
    with TemporaryDirectory() as folder:
        path = Path(folder) / "before.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        resumed = loaded.state
    next_cut = _cut_time(resumed, .35, physical.active_segment.duration_galactic_s)
    assert next_cut == pytest.approx(cut, abs=1e-12)
    Engine().tick(resumed, next_cut - resumed.clock.t)
    assert resumed.ship.physical_transit.pending_transition == "safety_brake"
    assert resumed.ship.antimatter_capsules == initial_fuel


def test_braking_cut_at_15_percent_preserves_motion_and_rejects_extension():
    game, start = ready_game(.5)
    engine = game.ship.systems["engines"]
    engine.health = .16
    engine.state = SystemState.CRITICAL
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    segment = brake_to_stop(start, 1e7)
    prepared(game, segment, "brake")
    cut = _cut_time(game, .15, segment.duration_galactic_s)
    assert proper_time_in_segment(segment, cut) == pytest.approx(
        (.16 - .15) / (.001 * Balance.TRANSIT_WEAR_MULT_NORMAL), rel=1e-8)
    original = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut + .1)
    assert pickle.dumps(game) == original
    GameLoop(Engine(), game).step(cut)
    assert game.ship.systems["engines"].health == .15
    assert game.ship.physical_transit.pending_transition == "inertia"
    assert game.ship.physical_transit.motion.beta == pytest.approx(sample_segment(segment, cut).beta)
    assert game.ship.physical_transit.motion.beta > 0
    assert game.ship.physical_transit.braking_started
    assert not game.ship.physical_transit.safety_braking
    assert game.clock.ship_elapsed_s == pytest.approx(proper_time_in_segment(segment, cut))
    with TemporaryDirectory() as folder:
        path = Path(folder) / "braking.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        restored = loaded.state
    assert restored.ship.physical_transit.pending_transition == "inertia"
    assert restored.ship.physical_transit.motion == game.ship.physical_transit.motion
    prior = restored.ship.physical_transit.motion
    Engine().tick(restored, 1)
    assert restored.ship.physical_transit.intent == "coast"
    assert restored.ship.physical_transit.motion.beta == prior.beta
    assert restored.ship.physical_transit.motion.distance_m > prior.distance_m


def test_nominal_braking_cut_invalidates_prepaid_plan_without_recharging():
    game = nominal_game()
    physical = prepare(game)
    Engine().tick(game, physical.active_segment.duration_galactic_s)
    assert game.ship.physical_transit.intent == "brake"
    engine = game.ship.systems["engines"]
    engine.health = .16
    engine.state = SystemState.CRITICAL
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    fuel = game.ship.antimatter_capsules
    segment = game.ship.physical_transit.active_segment
    cut = _cut_time(game, .15, segment.duration_galactic_s)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut - game.ship.physical_transit.elapsed_galactic_s + .1)
    assert pickle.dumps(game) == before
    Engine().tick(game, cut - game.ship.physical_transit.elapsed_galactic_s)
    assert game.ship.physical_transit.pending_transition == "inertia"
    assert game.ship.physical_transit.nominal_plan.invalidated
    assert game.ship.physical_transit.original_destination_id == "NOMINAL_B"
    assert game.ship.antimatter_capsules == fuel


def test_nominal_coast_reaching_35_percent_suspends_before_any_new_thrust():
    game = nominal_game(LIGHT_SPEED_M_S * .5 * 500)
    physical = prepare(game)
    assert len(physical.nominal_plan.segments) == 3
    Engine().tick(game, physical.active_segment.duration_galactic_s)
    assert game.ship.physical_transit.intent == "coast"
    engine = game.ship.systems["engines"]
    engine.health = .36
    engine.state = SystemState.DAMAGED
    engine.base_decay_per_s = .001
    engine.k_rad = 0
    fuel = game.ship.antimatter_capsules
    segment = game.ship.physical_transit.active_segment
    cut = _cut_time(game, .35, segment.duration_galactic_s)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut + 1)
    assert pickle.dumps(game) == before
    Engine().tick(game, cut)
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    assert game.ship.physical_transit.nominal_plan.invalidated
    assert game.ship.physical_transit.motion.beta == segment.start.beta
    assert not game.ship.physical_transit.braking_started
    assert game.ship.antimatter_capsules == fuel


def test_variable_radiation_wear_cut_and_safe_subdivision():
    game, physical = _critical_nominal(distance_m=1e9)
    destination = game.world.space.nodes["NOMINAL_B"]
    destination.radiation_rad_per_s = .0009
    engine = game.ship.systems["engines"]
    engine.k_rad = 100
    segment = physical.active_segment
    profile = _profile(game, "NOMINAL_B")
    expected_at = min(3.0, segment.duration_galactic_s / 2)
    exposure = integrate_segment_radiation(profile, segment, 0, expected_at, game.ship.hull_integrity)
    target = integrated_system_wear(engine, exposure, exposure.proper_s,
                                    in_transit=True, op_mode=game.ship.op_mode)
    engine.health = .35 + target
    cut = _cut_time(game, .35, segment.duration_galactic_s)
    assert cut == pytest.approx(expected_at, abs=1e-8)
    whole = deepcopy(game)
    Engine().tick(whole, cut)
    Engine().tick(game, cut / 2)
    split_cut = _cut_time(game, .35, segment.duration_galactic_s)
    assert split_cut == pytest.approx(cut, abs=1e-8)
    Engine().tick(game, split_cut - game.clock.t)
    assert game.ship.physical_transit.pending_transition == "safety_brake"
    assert whole.ship.physical_transit.motion.distance_m == pytest.approx(
        game.ship.physical_transit.motion.distance_m, abs=.02)
    assert game.ship.systems["engines"].health == .35
    assert game.ship.hull_integrity == pytest.approx(whole.ship.hull_integrity)


def test_earlier_electrical_or_deferred_radiation_limit_rejects_entire_cut():
    game, physical = _critical_nominal()
    cut = _cut_time(game, .35, physical.active_segment.duration_galactic_s)
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut)
    assert pickle.dumps(game) == before
    game.ship.power.e_batt_kwh = 3.0
    before = pickle.dumps(game)
    with patch("retorno.core.engine.radiation_limits", return_value=(
        TemporalLimit("internal_high", "proper", None,
                      validity="numerical_isolation_unresolved"),
    )):
        with pytest.raises(RuntimeError, match="causal boundary"):
            Engine().tick(game, cut)
    assert pickle.dumps(game) == before


def test_simultaneous_unresolved_electrical_limit_rejects_engine_cut():
    game, physical = _critical_nominal()
    cut = _cut_time(game, .35, physical.active_segment.duration_galactic_s)
    proper = proper_time_in_segment(physical.active_segment, cut)
    before = pickle.dumps(game)
    with patch("retorno.core.engine.power_limits", return_value=(
        TemporalLimit("battery_full", "proper", proper,
                      validity="fixed_electrical_conditions"),
    )):
        with pytest.raises(RuntimeError, match="causal boundary"):
            Engine().tick(game, cut)
    assert pickle.dumps(game) == before


def test_close_but_earlier_electrical_limit_is_not_merged_with_engine_cut():
    game, physical = _critical_nominal()
    cut = _cut_time(game, .35, physical.active_segment.duration_galactic_s)
    proper = proper_time_in_segment(physical.active_segment, cut)
    before = pickle.dumps(game)
    with patch("retorno.core.engine.power_limits", return_value=(
        TemporalLimit("battery_full", "proper", proper - 1e-6,
                      validity="fixed_electrical_conditions"),
    )):
        with pytest.raises(RuntimeError, match="causal boundary"):
            Engine().tick(game, cut)
    assert pickle.dumps(game) == before


def test_engine_isolation_during_prepared_travel_rejects_without_advancement():
    game, _ = _critical_nominal()
    game.ship.systems["engines"].forced_offline = True
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="unavailable"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before
