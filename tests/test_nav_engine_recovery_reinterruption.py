"""A paid recovery brake may suffer another physical 15% engine cut."""
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


def recovery_brake_at_risk():
    game, job = armed()
    Engine().tick(game, job.eta_s)
    coast = game.ship.physical_transit.active_segment
    Engine().tick(game, coast.duration_galactic_s)
    assert game.ship.physical_transit.intent == "brake"
    game.ship.systems["engines"].base_decay_per_s = .02
    cut = wear_cut(game, .15)
    assert cut is not None
    return game, cut


def test_recovery_brake_reaches_second_cut_and_then_coasts():
    game, cut = recovery_brake_at_risk()
    game = save_and_load(game)
    active = game.ship.physical_transit
    payment = active.recovery_execution.authorization
    first_history = active.recovery_execution.inertial_history
    start = active.motion
    clock = deepcopy(game.clock)
    fuel = game.ship.antimatter_capsules
    rng = game.meta.rng_counter
    node = game.world.current_node_id
    links = deepcopy(game.world.known_links)
    owners = tuple(getattr(game, key) for key in
                   ("ship", "clock", "world", "jobs", "events", "meta"))
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="causal boundary"):
        Engine().tick(game, cut + .1)
    assert pickle.dumps(game) == before
    GameLoop(Engine(), game).step(cut)
    pending = game.ship.physical_transit
    expected = sample_segment(active.active_segment, cut)
    interrupted = pending.recovery_interruption
    assert pending.pending_transition == "inertia"
    assert pending.motion == expected == interrupted.cut_motion
    assert pending.motion.beta > 0 and pending.motion.beta < start.beta
    assert pending.motion.distance_m > start.distance_m
    assert game.clock.t == expected.galactic_s
    assert game.clock.ship_elapsed_s == expected.proper_s
    assert game.clock.bio_elapsed_s > clock.bio_elapsed_s
    assert game.ship.systems["engines"].health == Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    assert pending.recovery_execution.invalidated
    assert interrupted.execution == pending.recovery_execution
    assert interrupted.execution.authorization == payment
    assert interrupted.execution.inertial_history == first_history
    assert interrupted.interrupted_elapsed_galactic_s == cut
    assert interrupted.cause == "engine_integrity_15"
    assert pending.recovery_intent.status == "used"
    assert game.ship.antimatter_capsules == fuel
    assert game.meta.rng_counter == rng
    assert all(getattr(game, key) is owner for key, owner in zip(
        ("ship", "clock", "world", "jobs", "events", "meta"), owners))
    assert not any(e.type == EventType.ARRIVED for e in game.events.recent)
    pending = save_and_load(game)
    assert pending.ship.physical_transit.recovery_interruption == interrupted
    assert pending.ship.physical_transit.recovery_execution.invalidated
    with pytest.raises(RuntimeError, match="invalidated"):
        Engine()._tick_recovery(pending, 1)
    GameLoop(Engine(), pending).step(1)
    coast = pending.ship.physical_transit
    assert coast.inertial_continuation is not None
    assert coast.recovery_execution is None
    assert coast.recovery_interruption == interrupted
    assert coast.inertial_continuation.interrupted_segment == active.active_segment
    assert coast.inertial_continuation.propulsion_receipt == payment
    assert coast.active_segment.start == expected
    assert coast.motion.beta == expected.beta
    assert coast.motion.distance_m == pytest.approx(
        expected.distance_m + LIGHT_SPEED_M_S * expected.beta)
    assert pending.ship.antimatter_capsules == fuel
    pending = save_and_load(pending)
    assert pending.ship.physical_transit.recovery_interruption == interrupted
    GameLoop(Engine(), pending).step(2)
    coast = pending.ship.physical_transit
    assert coast.motion.beta == expected.beta
    assert coast.motion.distance_m > expected.distance_m
    pending.ship.systems["engines"].base_decay_per_s = 0
    origin_id = pending.ship.transit_from or pending.ship.current_node_id
    route_m = light_years_to_metres(distance_between_nodes_ly(
        pending.world, origin_id, coast.original_destination_id))
    to_b = (route_m - coast.motion.distance_m) / (LIGHT_SPEED_M_S * coast.motion.beta)
    assert to_b > 0
    GameLoop(Engine(), pending).step(to_b + 1)
    beyond = pending.ship.physical_transit
    assert beyond.motion.distance_m > route_m
    assert beyond.motion.beta == expected.beta
    assert pending.world.current_node_id == node
    assert pending.world.known_links == links
    assert pending.ship.antimatter_capsules == fuel
    assert not any(e.type == EventType.ARRIVED for e in pending.events.recent)
    saved_beyond = save_and_load(pending)
    assert saved_beyond.ship.physical_transit.recovery_interruption == interrupted
    assert saved_beyond.ship.physical_transit.motion == beyond.motion


def test_subdivided_second_cut_matches_single_tick():
    whole, cut = recovery_brake_at_risk()
    split = deepcopy(whole)
    Engine().tick(whole, cut)
    half = cut / 2
    Engine().tick(split, half)
    assert split.ship.physical_transit.recovery_execution is not None
    assert not split.ship.physical_transit.recovery_execution.invalidated
    Engine().tick(split, cut - half)
    assert split.ship.physical_transit.motion == whole.ship.physical_transit.motion
    assert split.ship.systems["engines"].health == whole.ship.systems["engines"].health
    assert split.ship.power.e_batt_kwh == pytest.approx(whole.ship.power.e_batt_kwh, abs=1e-12)
    assert split.ship.hull_integrity == pytest.approx(whole.ship.hull_integrity, abs=1e-12)
    assert split.ship.radiation_env_rad_per_s == pytest.approx(
        whole.ship.radiation_env_rad_per_s, abs=1e-12)
    assert split.clock.t == pytest.approx(whole.clock.t, abs=1e-12)
    assert split.clock.ship_elapsed_s == pytest.approx(whole.clock.ship_elapsed_s, abs=1e-12)
    assert split.clock.bio_elapsed_s == pytest.approx(whole.clock.bio_elapsed_s, abs=1e-12)
    assert split.ship.antimatter_capsules == whole.ship.antimatter_capsules
    assert split.meta.rng_counter == whole.meta.rng_counter


@pytest.mark.parametrize("obstacle", ["electrical", "radiological", "job"])
def test_other_unresolved_limits_still_reject_atomically(obstacle):
    game, cut = recovery_brake_at_risk()
    if obstacle == "electrical":
        game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
        context = None
    elif obstacle == "radiological":
        context = patch("retorno.core.engine.radiation_limits", return_value=(
            TemporalLimit("deferred_radiation", "proper", 1, validity="deferred"),))
    else:
        enqueue_repair(game)
        context = None
    before = pickle.dumps(game)
    if context is None:
        with pytest.raises(RuntimeError):
            Engine().tick(game, cut)
    else:
        with context, pytest.raises(RuntimeError):
            Engine().tick(game, cut)
    assert pickle.dumps(game) == before


def test_second_cut_blocks_third_authorization_and_new_repair_slice():
    game, cut = recovery_brake_at_risk()
    Engine().tick(game, cut)
    Engine().tick(game, 1)
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


def test_interrupted_state_validation_rejects_reactivation_and_lost_history():
    game, cut = recovery_brake_at_risk()
    Engine().tick(game, cut)
    pending = game.ship.physical_transit
    with pytest.raises(ValueError):
        replace(pending, pending_transition=None)
    with pytest.raises(ValueError):
        replace(pending, recovery_interruption=None)
    with pytest.raises(ValueError):
        replace(pending, elapsed_galactic_s=cut / 2)
    Engine().tick(game, 1)
    coast = game.ship.physical_transit
    with pytest.raises(ValueError):
        replace(coast, recovery_execution=pending.recovery_execution)
    with pytest.raises(ValueError):
        replace(coast, recovery_interruption=None)


def test_previous_physical_pickle_layout_defaults_to_no_second_interruption():
    game, _ = recovery_brake_at_risk()
    from retorno.core.nav_state import PhysicalTransitState
    getstate = PhysicalTransitState.__getstate__
    with patch.object(PhysicalTransitState, "__getstate__",
                      lambda self: getstate(self)[:14]):
        payload = pickle.dumps(game)
    loaded = pickle.loads(payload)
    assert loaded.ship.physical_transit.recovery_execution is not None
    assert loaded.ship.physical_transit.recovery_interruption is None
