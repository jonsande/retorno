"""A paid recovery may lose braking capacity before its brake begins."""
from copy import deepcopy
from dataclasses import replace
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import LIGHT_SPEED_M_S, light_years_to_metres, sample_segment
from retorno.model.events import EventType
from retorno.model.world import distance_between_nodes_ly
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_auto_recovery import armed, enqueue_repair
from tests.test_nav_engine_safety_brake import save_and_load, wear_cut


def paid_coast(*, above_35=False):
    game, job = armed()
    if above_35:
        job.params["repair_amount"] = .35
    fuel = game.ship.antimatter_capsules
    Engine().tick(game, job.eta_s)
    active = game.ship.physical_transit
    assert active.intent == "coast" and len(active.recovery_execution.segments) == 2
    assert game.ship.antimatter_capsules == pytest.approx(
        fuel - active.recovery_execution.authorization.capsules_paid)
    game.ship.systems["engines"].base_decay_per_s = .02
    return game


def test_paid_wait_loses_braking_at_15_then_coasts_beyond_destination():
    game = paid_coast(above_35=True)
    game = save_and_load(game)
    initial = game.ship.physical_transit
    receipt = initial.recovery_execution.authorization
    first_history = initial.recovery_execution.inertial_history
    fuel = game.ship.antimatter_capsules
    node = game.world.current_node_id
    links = deepcopy(game.world.known_links)
    c35 = wear_cut(game, .35)
    assert c35 is not None and c35 > 0
    GameLoop(Engine(), game).step(c35)
    at_35 = game.ship.physical_transit
    assert game.ship.systems["engines"].health == Balance.SYSTEM_HEALTH_CRITICAL
    assert at_35.recovery_execution == initial.recovery_execution
    assert at_35.pending_transition is None
    assert at_35.motion.beta == initial.motion.beta
    assert at_35.motion.distance_m > initial.motion.distance_m
    game = save_and_load(game)
    owners = tuple(getattr(game, name) for name in
                   ("ship", "clock", "world", "jobs", "events", "meta"))
    c15_local = wear_cut(game, .15)
    assert c15_local is not None
    c15 = c15_local - game.ship.physical_transit.elapsed_galactic_s
    assert c15 > 0
    at_35 = game.ship.physical_transit
    start_clock = deepcopy(game.clock)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, c15 + .1)
    assert pickle.dumps(game) == before
    GameLoop(Engine(), game).step(c15)
    pending = game.ship.physical_transit
    expected = sample_segment(at_35.active_segment, at_35.elapsed_galactic_s + c15)
    lost = pending.recovery_coast_interruption
    assert lost is not None and pending.recovery_interruption is None
    assert pending.pending_transition == "inertia" and pending.intent == "coast"
    assert pending.motion == expected == lost.cut_motion
    assert pending.motion.beta == initial.motion.beta
    assert game.clock.t == expected.galactic_s
    assert game.clock.ship_elapsed_s == expected.proper_s
    assert game.clock.bio_elapsed_s > start_clock.bio_elapsed_s
    assert game.ship.systems["engines"].health == Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    assert pending.recovery_execution.invalidated
    assert pending.recovery_execution.phase_index == 0
    assert lost.execution == pending.recovery_execution
    assert lost.execution.authorization == receipt
    assert lost.execution.inertial_history == first_history
    assert lost.interrupted_elapsed_galactic_s == pending.elapsed_galactic_s
    assert lost.cause == "engine_integrity_15"
    assert pending.recovery_intent.status == "used"
    assert game.ship.antimatter_capsules == fuel
    assert all(getattr(game, name) is owner for name, owner in zip(
        ("ship", "clock", "world", "jobs", "events", "meta"), owners))
    assert not any(e.type == EventType.ARRIVED for e in game.events.recent)
    game = save_and_load(game)
    assert game.ship.physical_transit.recovery_coast_interruption == lost
    with pytest.raises(RuntimeError, match="invalidated"):
        Engine()._tick_recovery(game, 1)
    GameLoop(Engine(), game).step(1)
    coast = game.ship.physical_transit
    assert coast.recovery_execution is None
    assert coast.recovery_coast_interruption == lost
    assert coast.inertial_continuation.interrupted_segment == first_history.interrupted_segment
    assert coast.inertial_continuation.propulsion_receipt == first_history.propulsion_receipt
    assert coast.active_segment.start == expected
    assert coast.motion.beta == expected.beta
    assert coast.motion.distance_m == pytest.approx(
        expected.distance_m + LIGHT_SPEED_M_S * expected.beta)
    assert game.ship.antimatter_capsules == fuel
    game = save_and_load(game)
    GameLoop(Engine(), game).step(2)
    assert game.ship.physical_transit.motion.beta == expected.beta
    game.ship.systems["engines"].base_decay_per_s = 0
    origin_id = game.ship.transit_from or game.ship.current_node_id
    route_m = light_years_to_metres(distance_between_nodes_ly(
        game.world, origin_id, coast.original_destination_id))
    to_b = (route_m - game.ship.physical_transit.motion.distance_m) / (
        LIGHT_SPEED_M_S * expected.beta)
    assert to_b > 0
    GameLoop(Engine(), game).step(to_b + 1)
    beyond = game.ship.physical_transit
    assert beyond.motion.distance_m > route_m and beyond.motion.beta == expected.beta
    assert game.world.current_node_id == node and game.world.known_links == links
    assert game.ship.antimatter_capsules == fuel
    assert not any(e.type == EventType.ARRIVED for e in game.events.recent)
    loaded = save_and_load(game)
    assert loaded.ship.physical_transit.recovery_coast_interruption == lost
    assert loaded.ship.physical_transit.motion == beyond.motion


def test_single_and_split_wait_cut_have_equivalent_physics():
    whole = paid_coast(above_35=True)
    split = deepcopy(whole)
    c15 = wear_cut(whole, .15)
    assert c15 is not None
    Engine().tick(whole, c15)
    c35 = wear_cut(split, .35)
    assert c35 is not None
    Engine().tick(split, c35)
    c15_local = wear_cut(split, .15)
    assert c15_local is not None
    Engine().tick(split, c15_local - split.ship.physical_transit.elapsed_galactic_s)
    assert whole.ship.physical_transit.motion == split.ship.physical_transit.motion
    assert whole.ship.systems["engines"].health == split.ship.systems["engines"].health
    assert whole.ship.antimatter_capsules == split.ship.antimatter_capsules
    assert whole.meta.rng_counter == split.meta.rng_counter
    assert whole.ship.power.e_batt_kwh == pytest.approx(split.ship.power.e_batt_kwh, abs=1e-12)
    assert whole.ship.hull_integrity == pytest.approx(split.ship.hull_integrity, abs=1e-12)


def test_paid_wait_starting_at_inclusive_15_threshold_moves_by_inertia():
    game = paid_coast()
    game.ship.systems["engines"].health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    start = game.ship.physical_transit.motion
    payment = game.ship.physical_transit.recovery_execution.authorization
    fuel = game.ship.antimatter_capsules
    Engine().tick(game, 1)
    physical = game.ship.physical_transit
    assert physical.recovery_execution is None
    assert physical.recovery_coast_interruption.cut_motion == start
    assert physical.recovery_coast_interruption.execution.authorization == payment
    assert physical.recovery_coast_interruption.interrupted_elapsed_galactic_s == 0
    assert physical.active_segment.start == start
    assert physical.motion.beta == start.beta
    assert physical.motion.distance_m > start.distance_m
    assert game.ship.antimatter_capsules == fuel


def test_inclusive_15_threshold_without_engine_wear_keeps_paid_wait():
    game = paid_coast()
    game.ship.systems["engines"].health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    game.ship.systems["engines"].base_decay_per_s = 0
    Engine().tick(game, 1)
    physical = game.ship.physical_transit
    assert physical.intent == "coast"
    assert physical.recovery_execution is not None
    assert not physical.recovery_execution.invalidated
    assert physical.recovery_coast_interruption is None
    assert game.ship.systems["engines"].health == Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH


@pytest.mark.parametrize("obstacle", ["electrical", "radiological", "job", "isolation", "power"])
def test_unsupported_wait_limit_rejects_atomically(obstacle):
    game = paid_coast()
    c15 = wear_cut(game, .15)
    assert c15 is not None
    context = None
    if obstacle == "electrical":
        game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    elif obstacle == "radiological":
        context = patch("retorno.core.engine.radiation_limits", return_value=(
            TemporalLimit("deferred_radiation", "proper", 1, validity="deferred"),))
    elif obstacle == "job":
        enqueue_repair(game)
    elif obstacle == "isolation":
        game.ship.systems["engines"].forced_offline = True
        game.ship.systems["engines"].base_decay_per_s = 0
    else:
        game.ship.systems["energy_distribution"].forced_offline = True
        game.ship.systems["engines"].base_decay_per_s = 0
    interval = (game.ship.physical_transit.active_segment.duration_galactic_s
                if obstacle in {"isolation", "power"} else c15)
    before = pickle.dumps(game)
    if context is None:
        with pytest.raises(RuntimeError):
            Engine().tick(game, interval)
    else:
        with context, pytest.raises(RuntimeError):
            Engine().tick(game, interval)
    assert pickle.dumps(game) == before


def test_coast_interruption_blocks_reuse_and_keeps_history_distinct():
    game = paid_coast()
    cut = wear_cut(game, .15)
    assert cut is not None
    Engine().tick(game, cut)
    pending = game.ship.physical_transit
    with pytest.raises(ValueError):
        replace(pending, recovery_coast_interruption=None)
    with pytest.raises(ValueError):
        replace(pending, recovery_interruption=pending.recovery_coast_interruption)
    Engine().tick(game, 1)
    coast = game.ship.physical_transit
    with pytest.raises(ValueError):
        replace(coast, recovery_coast_interruption=None)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="second interrupted recovery"):
        Engine().prepare_inertial_recovery(game)
    with pytest.raises(RuntimeError):
        Engine().authorize_manual_inertial_recovery(game, max_capsules=10)
    assert pickle.dumps(game) == before
    enqueue_repair(game)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="second inertial continuation"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_old_fifteen_field_physical_pickle_retains_brake_history():
    from retorno.core.nav_state import PhysicalTransitState
    from tests.test_nav_engine_recovery_reinterruption import recovery_brake_at_risk
    game, cut = recovery_brake_at_risk()
    Engine().tick(game, cut)
    getstate = PhysicalTransitState.__getstate__
    with patch.object(PhysicalTransitState, "__getstate__",
                      lambda self: getstate(self)[:15]):
        payload = pickle.dumps(game)
    loaded = pickle.loads(payload)
    assert loaded.ship.physical_transit.recovery_interruption == (
        game.ship.physical_transit.recovery_interruption)
    assert loaded.ship.physical_transit.recovery_coast_interruption is None
