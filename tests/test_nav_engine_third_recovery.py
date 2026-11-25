"""C3B1: one new, manually paid recovery after a productive second repair."""
from copy import deepcopy
import math
import pickle

import pytest

from retorno.core.engine import Engine
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, braking_profile,
                                      light_years_to_metres, sample_segment)
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.model.events import EventType
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_repair_inertia import enqueue_repair
from tests.test_nav_engine_second_inertia_repair import second_inertia
from tests.test_nav_engine_safety_brake import save_and_load, wear_cut


def repaired_second(origin):
    game = save_and_load(second_inertia(origin))
    job = enqueue_repair(game)
    game = save_and_load(game)
    GameLoop(Engine(), game).step(job.eta_s / 2)
    game = save_and_load(game)
    GameLoop(Engine(), game).step(game.jobs.jobs[job.internal_id].eta_s)
    assert game.jobs.jobs[job.internal_id].status.value == "completed"
    assert game.ship.physical_transit.recovery_execution is None
    return save_and_load(game)


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_complete_third_recovery_after_real_second_repair(origin):
    game = repaired_second(origin)
    engine = Engine()
    before = game.ship.physical_transit
    original_fuel = game.ship.antimatter_capsules
    known_nodes = set(game.world.space.nodes)
    old_receipt = (before.recovery_interruption or before.recovery_coast_interruption).execution.authorization
    owners = tuple(getattr(game, name) for name in
                   ("ship", "clock", "world", "jobs", "events", "meta"))
    with pytest.raises(RuntimeError, match="manual authorization"):
        engine.prepare_inertial_recovery(game)
    assert game.ship.antimatter_capsules == original_fuel
    intent = engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    assert all(getattr(game, name) is owner for name, owner in zip(
        ("ship", "clock", "world", "jobs", "events", "meta"), owners))
    assert intent.attempt_id > 1 and intent.status == "pending"
    assert game.ship.antimatter_capsules == original_fuel
    game = save_and_load(game)
    plan = plan_inertial_recovery(game)
    assert plan.decision == ("emergency_brake" if origin == "brake" else "coast_then_brake")
    start = game.ship.physical_transit.motion
    state = engine.prepare_inertial_recovery(game, plan)
    prepared_owners = tuple(getattr(game, name) for name in
                            ("ship", "clock", "world", "jobs", "events", "meta"))
    assert state.motion == start
    assert state.recovery_lineage.attempt_count == 2
    assert state.recovery_lineage.interruption_count == 1
    assert len(state.recovery_lineage.recent) == 2
    assert state.recovery_lineage.recent[0].authorization == old_receipt
    assert state.recovery_lineage.recent[0].outcome == (
        "interrupted_brake" if origin == "brake" else "interrupted_coast")
    if origin == "coast":
        assert state.recovery_lineage.recent[0].demonstrated_deceleration_m_s2 is None
    assert state.recovery_lineage.recent[1].authorization == state.recovery_execution.authorization
    assert state.recovery_lineage.spent_through_authorization_id == intent.attempt_id
    new_price = state.recovery_execution.authorization.capsules_paid
    assert game.ship.antimatter_capsules == pytest.approx(original_fuel - new_price)
    game = save_and_load(game)
    prepared_owners = tuple(getattr(game, name) for name in
                            ("ship", "clock", "world", "jobs", "events", "meta"))
    with pytest.raises(RuntimeError):
        engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    for segment in plan.segments:
        endpoint = sample_segment(segment, segment.duration_galactic_s)
        due = endpoint.galactic_s - game.clock.t
        if segment.proper_acceleration_m_s2 < 0:
            GameLoop(engine, game).step(due / 2)
            assert all(getattr(game, name) is owner for name, owner in zip(
                ("ship", "clock", "world", "jobs", "events", "meta"), prepared_owners))
            assert game.ship.physical_transit.motion.beta < segment.start.beta
            game = save_and_load(game)
            prepared_owners = tuple(getattr(game, name) for name in
                                    ("ship", "clock", "world", "jobs", "events", "meta"))
            due = endpoint.galactic_s - game.clock.t
        GameLoop(engine, game).step(due)
        assert all(getattr(game, name) is owner for name, owner in zip(
            ("ship", "clock", "world", "jobs", "events", "meta"), prepared_owners))
        if endpoint.beta > 0:
            assert game.ship.physical_transit.motion.distance_m == pytest.approx(endpoint.distance_m)
        else:
            assert game.ship.physical_transit is None
        game = save_and_load(game)
        prepared_owners = tuple(getattr(game, name) for name in
                                ("ship", "clock", "world", "jobs", "events", "meta"))
    assert game.ship.physical_transit is None
    brake = plan.braking_segment
    gamma = 1 / math.sqrt(1 - brake.start.beta ** 2)
    magnitude = abs(brake.proper_acceleration_m_s2)
    reference_distance = (brake.start.distance_m
                          + LIGHT_SPEED_M_S ** 2 / magnitude * (gamma - 1))
    reference_galactic = (brake.start.galactic_s
                          + LIGHT_SPEED_M_S / magnitude * brake.start.beta * gamma)
    reference_proper = (brake.start.proper_s
                        + LIGHT_SPEED_M_S / magnitude * math.atanh(brake.start.beta))
    endpoint = sample_segment(brake, brake.duration_galactic_s)
    assert endpoint.distance_m == pytest.approx(reference_distance, abs=.001)
    assert game.clock.t == pytest.approx(reference_galactic, abs=1e-9)
    assert game.clock.ship_elapsed_s == pytest.approx(reference_proper, abs=1e-9)
    assert game.ship.antimatter_capsules == pytest.approx(original_fuel - new_price)
    assert game.world.current_node_id in {before.original_destination_id, game.world.active_tmp_node_id}
    assert game.world.current_node_id in game.world.space.nodes
    assert game.world.active_tmp_node_id is None or game.world.active_tmp_node_id in game.world.space.nodes


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_third_rejection_is_atomic_and_permission_is_one_use(origin):
    game = repaired_second(origin)
    engine = Engine()
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        engine.prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before
    with pytest.raises(ValueError):
        engine.authorize_manual_inertial_recovery(game, max_capsules=0)
    assert pickle.dumps(game) == before
    intent = engine.authorize_manual_inertial_recovery(game, max_capsules=1e-9)
    armed = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="spending limit"):
        engine.prepare_inertial_recovery(game)
    assert pickle.dumps(game) == armed
    engine.cancel_manual_inertial_recovery(game)
    new = engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    assert new.attempt_id > intent.attempt_id
    assert new.paid_predecessor_id == intent.paid_predecessor_id
    old_plan = plan_inertial_recovery(game)
    engine.tick(game, 1)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="stale"):
        engine.prepare_inertial_recovery(game, old_plan)
    assert pickle.dumps(game) == before
    game.ship.antimatter_capsules = 0
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="antimatter"):
        engine.prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_third_integrity_boundary_creates_current_interruption(origin):
    game = repaired_second(origin)
    engine = Engine()
    engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    engine.prepare_inertial_recovery(game)
    game = save_and_load(game)
    if origin == "coast":
        game.ship.systems["engines"].health = .15
        game.ship.systems["engines"].base_decay_per_s = .001
        before = game.ship.physical_transit.motion
        fuel = game.ship.antimatter_capsules
        engine.tick(game, 1)
        physical = game.ship.physical_transit
        assert physical.recovery_coast_interruption is not None
        assert physical.recovery_coast_interruption.cut_motion == before
        assert physical.inertial_continuation is not None
    else:
        game.ship.systems["engines"].health = .15001
        game.ship.systems["engines"].base_decay_per_s = .001
        cut = wear_cut(game, .15)
        assert cut is not None
        fuel = game.ship.antimatter_capsules
        engine.tick(game, cut)
        physical = game.ship.physical_transit
        assert physical.recovery_interruption is not None
        assert physical.recovery_interruption.cut_motion == physical.motion
        engine.tick(game, 1)
        physical = game.ship.physical_transit
        assert physical.inertial_continuation is not None
    assert physical.second_repair_evidence is None
    assert physical.recovery_lineage.attempt_count == 2
    assert physical.recovery_lineage.interruption_count == 2
    assert physical.recovery_lineage.recent[-1].outcome == (
        "interrupted_brake" if origin == "brake" else "interrupted_coast")
    assert physical.motion.beta > 0
    assert game.ship.antimatter_capsules == fuel


def test_lineage_has_bounded_recent_window_and_digest():
    game = repaired_second("brake")
    engine = Engine()
    engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    state = engine.prepare_inertial_recovery(game)
    lineage = state.recovery_lineage
    record = deepcopy(lineage.recent[-1])
    from dataclasses import replace
    lineage = lineage.replace_last(replace(record, outcome="completed"))
    next_lineage = lineage.append(replace(record, attempt_id=3, authorization_id=3))
    assert len(next_lineage.recent) == 2
    assert next_lineage.attempt_count == 3
    assert next_lineage.prefix_digest != "0" * 64
    assert len(pickle.dumps(next_lineage)) < 4000
    for attempt in range(4, 24):
        next_lineage = next_lineage.replace_last(
            replace(next_lineage.recent[-1], outcome="completed"))
        next_lineage = next_lineage.append(
            replace(record, attempt_id=attempt, authorization_id=attempt))
        assert len(next_lineage.recent) == 2
        assert len(pickle.dumps(next_lineage)) < 4000
    with pytest.raises(ValueError):
        lineage.append(replace(record, attempt_id=2, authorization_id=2))


@pytest.mark.parametrize("origin,deceleration", [
    ("brake", 8_950_000.0), ("coast", 9_950_000.0)])
def test_third_exact_braking_boundary_uses_brake_now(origin, deceleration):
    game = repaired_second(origin)
    physical = game.ship.physical_transit
    start = physical.motion
    distance = (start.distance_m
                + braking_profile(start.beta, deceleration).distance_m)
    # Set a self-consistent destination geometry on the exact representable
    # boundary. The voyage identity and actual motion remain unchanged.
    origin_node = game.world.space.nodes[game.ship.transit_from]
    destination = game.world.space.nodes[physical.original_destination_id]
    destination.x_ly = origin_node.x_ly + distance / light_years_to_metres(1)
    destination.y_ly = origin_node.y_ly
    destination.z_ly = origin_node.z_ly
    fraction = start.distance_m / distance
    game.world.current_pos_ly = (
        origin_node.x_ly + fraction * (destination.x_ly - origin_node.x_ly),
        origin_node.y_ly, origin_node.z_ly)
    game = save_and_load(game)
    Engine().authorize_manual_inertial_recovery(game, max_capsules=100)
    plan = plan_inertial_recovery(game, proper_deceleration_m_s2=deceleration)
    assert plan.decision == "brake_now"
    Engine().prepare_inertial_recovery(
        game, plan, proper_deceleration_m_s2=deceleration)
    assert len(game.ship.physical_transit.recovery_execution.segments) == 1
    GameLoop(Engine(), game).step(plan.braking_segment.duration_galactic_s)
    assert game.ship.physical_transit is None
    assert game.world.current_node_id in game.world.space.nodes


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_third_deceleration_cannot_exceed_demonstrated_brake(origin):
    game = repaired_second(origin)
    physical = game.ship.physical_transit
    historical = physical.inertial_continuation.interrupted_segment
    maximum = abs(historical.proper_acceleration_m_s2)
    Engine().authorize_manual_inertial_recovery(game, max_capsules=100)
    plan = plan_inertial_recovery(game, proper_deceleration_m_s2=maximum * 1.01)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="verified physical capacity"):
        Engine().prepare_inertial_recovery(
            game, plan, proper_deceleration_m_s2=maximum * 1.01)
    assert pickle.dumps(game) == before


def test_third_coast_and_brake_can_share_one_atomic_tick():
    game = repaired_second("coast")
    Engine().authorize_manual_inertial_recovery(game, max_capsules=100)
    plan = plan_inertial_recovery(game)
    Engine().prepare_inertial_recovery(game, plan)
    initial = deepcopy(game)
    due = plan.coast_segment.duration_galactic_s + 1
    GameLoop(Engine(), game).step(due)
    assert game.ship.physical_transit.intent == "brake"
    assert game.ship.physical_transit.motion.beta < initial.ship.physical_transit.motion.beta
    assert game.ship.physical_transit.recovery_lineage.recent[-1].outcome == "active"
    blocked = deepcopy(initial)
    blocked.world.lore_placements.next_non_forced_eval_t = blocked.clock.t + due - .5
    before = pickle.dumps(blocked)
    with pytest.raises(RuntimeError):
        Engine().tick(blocked, due)
    assert pickle.dumps(blocked) == before
