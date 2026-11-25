"""D1 terminal transitions through productive physical ticks."""
import math
import pickle
from unittest.mock import patch

import pytest

from retorno.core.engine import Engine
from retorno.cli.repl import render_events
from retorno.config.balance import Balance
from retorno.core.nav_physics import light_years_to_metres, metres_to_light_years, sample_segment
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.core.nav_radiation import integrate_segment_radiation
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import NodePoolState, distance_between_nodes_ly, is_hop_within_cap
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_nominal import nominal_game, prepare, durations
from tests.test_nav_engine_recovery_execution import repaired_ship
from tests.test_nav_engine_safety_brake import (pending_acceleration, pending_coast,
                                                profile, save_and_load, wear_cut)


def _terminal(game):
    active = game.ship.physical_transit
    segment = active.active_segment
    endpoint = sample_segment(segment, segment.duration_galactic_s)
    events = GameLoop(Engine(), game).step(segment.duration_galactic_s - active.elapsed_galactic_s)
    return endpoint, events


def test_nominal_arrival_is_unique_and_restores_ordinary_time():
    game = nominal_game()
    prepared = prepare(game)
    owners = tuple(getattr(game, name) for name in ("ship", "clock", "world", "events", "meta"))
    fuel = game.ship.antimatter_capsules
    before = save_and_load(game)
    assert before.ship.physical_transit == game.ship.physical_transit
    events = GameLoop(Engine(), game).step(sum(durations(prepared)))
    assert game.ship.physical_transit is None
    assert game.ship.current_node_id == game.world.current_node_id == "NOMINAL_B"
    assert game.world.current_node_id in game.world.visited_nodes
    assert game.ship.docked_node_id is None
    assert game.ship.antimatter_capsules == fuel
    assert sum(e.type == EventType.ARRIVED for e in events) == 1
    assert all(getattr(game, name) is owner for name, owner in zip(
        ("ship", "clock", "world", "events", "meta"), owners))
    rested = save_and_load(game)
    assert rested.ship.physical_transit is None
    Engine().tick(rested, 1)
    assert sum(e.type == EventType.ARRIVED for e in rested.events.recent) == 1


def test_safety_stop_before_destination_creates_empty_legal_waypoint():
    game = pending_acceleration()
    Engine().tick(game, .5)
    fuel = game.ship.antimatter_capsules
    endpoint, events = _terminal(game)
    waypoint = game.world.active_tmp_node_id
    assert waypoint and waypoint.startswith("NAV_PT_")
    assert game.ship.physical_transit is None
    assert game.ship.current_node_id == game.world.current_node_id == waypoint
    assert game.world.space.nodes[waypoint].kind == "transit"
    assert game.world.space.nodes[waypoint].salvage_scrap_available == 0
    assert game.world.space.nodes[waypoint].salvage_modules_available == []
    assert game.world.current_pos_ly == tuple(getattr(game.world.space.nodes[waypoint], axis)
                                               for axis in ("x_ly", "y_ly", "z_ly"))
    assert endpoint.distance_m < light_years_to_metres(distance_between_nodes_ly(
        game.world, game.world.active_tmp_from, "NOMINAL_B"))
    assert game.ship.antimatter_capsules == fuel
    assert sum(e.type == EventType.PHYSICAL_STOPPED for e in events) == 1
    assert not any(e.type == EventType.ARRIVED for e in events)
    for target in game.world.known_links.get(waypoint, set()):
        assert target in game.world.space.nodes
        assert is_hop_within_cap(game.world, waypoint, target)
    loaded = save_and_load(game)
    assert loaded.world.current_pos_ly == game.world.current_pos_ly
    assert loaded.world.active_tmp_node_id == waypoint
    Engine().tick(loaded, 1)
    assert sum(e.type == EventType.PHYSICAL_STOPPED for e in loaded.events.recent) == 1


def test_overshoot_crossing_retains_motion_then_stops_beyond_without_arrival():
    game = pending_coast()
    active = game.ship.physical_transit
    Engine().tick(game, .1)  # Activate the already paid safety brake.
    active = game.ship.physical_transit
    brake = active.active_segment
    origin = game.world.space.nodes[game.ship.transit_from]
    dest = game.world.space.nodes["NOMINAL_B"]
    crossing_m = active.motion.distance_m + (sample_segment(brake, brake.duration_galactic_s).distance_m
                                              - active.motion.distance_m) * .25
    dest.x_ly = origin.x_ly + metres_to_light_years(crossing_m)
    Engine().tick(game, (brake.duration_galactic_s - active.elapsed_galactic_s) * .5)
    assert game.ship.physical_transit.motion.beta > 0
    assert game.ship.physical_transit.motion.distance_m > crossing_m
    assert game.world.active_tmp_node_id is None
    assert "NOMINAL_B" not in game.world.visited_nodes
    assert not any(e.type == EventType.ARRIVED for e in game.events.recent)
    endpoint, events = _terminal(game)
    assert endpoint.distance_m > crossing_m
    assert game.ship.physical_transit is None
    assert game.world.active_tmp_node_id == game.world.current_node_id
    assert game.world.current_pos_ly[0] > dest.x_ly
    assert sum(e.type == EventType.PHYSICAL_STOPPED for e in events) == 1
    assert "NOMINAL_B" not in game.world.visited_nodes
    assert save_and_load(game).world.current_pos_ly == game.world.current_pos_ly


def test_horizon_past_nominal_stop_rejects_without_partial_time():
    game = nominal_game()
    prepared = prepare(game)
    prior = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="endpoint"):
        Engine().tick(game, sum(durations(prepared)) + 1)
    assert pickle.dumps(game) == prior


def test_horizon_past_recovery_stop_rejects_without_partial_time():
    game = repaired_ship()
    plan = plan_inertial_recovery(game)
    Engine().prepare_inertial_recovery(game, plan)
    last = plan.segments[-1]
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="physical horizon"):
        Engine().tick(game, last.start.galactic_s + last.duration_galactic_s - game.clock.t + 1)
    assert pickle.dumps(game) == before


def test_failed_waypoint_consolidation_rolls_back_motion_and_world():
    game = pending_acceleration()
    Engine().tick(game, .5)
    before = pickle.dumps(game)
    with patch("retorno.core.engine.add_known_link", side_effect=RuntimeError("link failed")):
        with pytest.raises(RuntimeError, match="link failed"):
            _terminal(game)
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("offset", [-0.9, 0.9, -1.1, 1.1])
def test_stop_tolerance_uses_physical_metres(offset):
    game = pending_coast()
    Engine().tick(game, .1)
    active = game.ship.physical_transit
    stop = sample_segment(active.active_segment, active.active_segment.duration_galactic_s)
    tolerance = Engine._nominal_distance_tolerance(stop.distance_m)
    origin = game.world.space.nodes[game.ship.transit_from]
    dest = game.world.space.nodes["NOMINAL_B"]
    dest.x_ly = origin.x_ly + metres_to_light_years(stop.distance_m + offset * tolerance)
    _terminal(game)
    assert (game.world.current_node_id == "NOMINAL_B") == (abs(offset) < 1)


def test_old_waypoint_is_removed_only_after_next_physical_journey_finishes():
    game = pending_acceleration()
    Engine().tick(game, .5)
    _terminal(game)
    previous = game.world.active_tmp_node_id
    assert previous in game.world.space.nodes
    game.ship.systems["engines"].health = .9
    game.ship.systems["engines"].state = SystemState.NOMINAL
    game.ship.systems["engines"].base_decay_per_s = 0
    next_plan = Engine().prepare_nominal_physical_travel(
        game, "NOMINAL_B", proper_acceleration_m_s2=1e7)
    assert previous in game.world.space.nodes
    GameLoop(Engine(), game).step(sum(durations(next_plan)))
    assert previous not in game.world.space.nodes
    assert previous not in game.world.known_links
    assert all(previous not in links for links in game.world.known_links.values())
    assert game.world.current_node_id == "NOMINAL_B"


def test_braking_wear_boundary_at_zero_beta_finishes_without_inertia():
    game = pending_acceleration()
    Engine().tick(game, .1)
    active = game.ship.physical_transit
    segment = active.active_segment
    engine = game.ship.systems["engines"]
    engine.health = .16
    engine.state = SystemState.CRITICAL
    engine.k_rad = 0
    exposure = integrate_segment_radiation(
        profile(game), segment, active.elapsed_galactic_s,
        segment.duration_galactic_s, game.ship.hull_integrity)
    engine.base_decay_per_s = .01 / (Balance.TRANSIT_WEAR_MULT_NORMAL * exposure.proper_s)
    for _ in range(64):
        cut = wear_cut(game, .15)
        if cut == segment.duration_galactic_s:
            break
        engine.base_decay_per_s = math.nextafter(engine.base_decay_per_s, 0)
    else:
        pytest.fail("no representable wear cut at physical stop")
    _terminal(game)
    assert game.ship.physical_transit is None
    assert game.world.active_tmp_node_id == game.world.current_node_id
    assert game.ship.systems["engines"].health == .15


def test_physical_stop_event_renders_in_both_locales(capsys):
    game = pending_acceleration()
    Engine().tick(game, .5)
    _, events = _terminal(game)
    stopped = [event for event in events if event.type == EventType.PHYSICAL_STOPPED]
    assert len(stopped) == 1
    for locale, phrase in ((Locale.EN, "Stopped outside"),
                           (Locale.ES, "Detenido fuera")):
        game.os.locale = locale
        render_events(game, stopped)
        assert phrase in capsys.readouterr().out


def test_orbit_lore_window_closes_only_on_effective_arrival():
    stopped = pending_acceleration()
    stopped.world.node_pools["NOMINAL_B"] = NodePoolState()
    Engine().tick(stopped, .5)
    _terminal(stopped)
    assert stopped.world.node_pools["NOMINAL_B"].window_open
    arrived = nominal_game()
    arrived.world.node_pools["NOMINAL_B"] = NodePoolState()
    prepared = prepare(arrived)
    GameLoop(Engine(), arrived).step(sum(durations(prepared)))
    assert arrived.world.node_pools["NOMINAL_B"].window_closed_reason == "orbit_entry"
