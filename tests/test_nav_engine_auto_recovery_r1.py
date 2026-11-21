"""A cancelled recovery cannot bar a separately authorized later attempt."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.core.nav_state import RecoveryIntent
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_repair_inertia import enqueue_repair
from tests.test_nav_engine_auto_recovery import armed


def test_cancelled_spending_limit_allows_a_new_productive_repair_authorization():
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    assert game.ship.physical_transit.recovery_intent.status == "cancelled"
    second = enqueue_repair(game)
    intent = Engine().arm_inertial_recovery(game, second.internal_id, max_capsules=10)
    assert intent.job_id == second.internal_id
    assert intent.attempt_id == 2
    assert intent.previous_cancelled == (1, first.internal_id, "authorization_unavailable")
    assert game.jobs.jobs[first.internal_id].status == JobStatus.COMPLETED
    before = pickle.dumps(game)
    Engine()._settle_recovery_intent(game, (first.internal_id,))
    assert pickle.dumps(game) == before
    fuel = game.ship.antimatter_capsules
    GameLoop(Engine(), game).step(second.eta_s)
    active = game.ship.physical_transit
    assert game.jobs.jobs[second.internal_id].status == JobStatus.COMPLETED
    assert active.recovery_execution is not None
    assert active.recovery_intent.attempt_id == 2
    assert active.recovery_intent.status == "used"
    assert game.ship.antimatter_capsules == pytest.approx(
        fuel - active.recovery_execution.authorization.capsules_paid)
    saved = pickle.loads(pickle.dumps(game))
    assert saved.ship.physical_transit.recovery_intent == active.recovery_intent
    assert saved.ship.antimatter_capsules == game.ship.antimatter_capsules
    GameLoop(Engine(), saved).step(1)
    assert saved.jobs.jobs[first.internal_id].status == JobStatus.COMPLETED
    assert saved.jobs.jobs[second.internal_id].status == JobStatus.COMPLETED
    assert saved.ship.antimatter_capsules == game.ship.antimatter_capsules


def test_cancelled_limit_allows_manual_authorization_without_second_repair():
    game, first = armed(max_capsules=.01)
    GameLoop(Engine(), game).step(first.eta_s)
    cancelled = game.ship.physical_transit.recovery_intent
    assert cancelled.status == "cancelled"
    initial_fuel = game.ship.antimatter_capsules
    initial_motion = game.ship.physical_transit.motion
    initial_clocks = deepcopy(game.clock)
    initial_events = deepcopy(game.events)
    initial_rng = game.meta.rng_counter
    game = pickle.loads(pickle.dumps(game))
    new = Engine().authorize_manual_inertial_recovery(game, max_capsules=10)
    assert new.job_id is None and new.attempt_id == cancelled.attempt_id + 1
    assert new.previous_cancelled == (cancelled.attempt_id, cancelled.job_id, cancelled.outcome)
    assert new.status == "pending" and cancelled.status == "cancelled"
    assert game.ship.physical_transit.motion == initial_motion
    assert game.clock == initial_clocks and game.events == initial_events
    assert game.meta.rng_counter == initial_rng
    assert game.ship.antimatter_capsules == initial_fuel
    with pytest.raises(RuntimeError):
        Engine().authorize_manual_inertial_recovery(game, max_capsules=10)
    current_plan = plan_inertial_recovery(game)
    prepared_owners = tuple(getattr(game, name) for name in
                            ("ship", "clock", "world", "jobs", "events", "meta"))
    Engine().prepare_inertial_recovery(game, current_plan)
    active = game.ship.physical_transit
    assert active.motion == initial_motion
    assert active.recovery_execution is not None
    assert active.recovery_intent.status == "used"
    assert active.recovery_execution.inertial_history.braking_substitution is not None
    assert game.ship.antimatter_capsules == pytest.approx(
        initial_fuel - active.recovery_execution.authorization.capsules_paid)
    assert all(getattr(game, name) is owner for name, owner in zip(
        ("ship", "clock", "world", "jobs", "events", "meta"), prepared_owners))
    saved = pickle.loads(pickle.dumps(game))
    assert saved.ship.physical_transit.recovery_intent == active.recovery_intent
    assert saved.ship.antimatter_capsules == game.ship.antimatter_capsules
    GameLoop(Engine(), saved).step(1)
    assert saved.ship.physical_transit.motion.distance_m > initial_motion.distance_m
    assert saved.ship.antimatter_capsules == game.ship.antimatter_capsules
    with pytest.raises(RuntimeError):
        Engine().authorize_manual_inertial_recovery(saved, max_capsules=10)
    with pytest.raises(RuntimeError):
        Engine().prepare_inertial_recovery(saved)
    assert saved.jobs.jobs[first.internal_id].status == JobStatus.COMPLETED
    assert len([e for e in saved.events.recent if e.type == EventType.JOB_COMPLETED]) == 1


def test_cancelled_intent_blocks_unapproved_manual_preparation():
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    with pytest.raises(RuntimeError):
        Engine().prepare_inertial_recovery(game)


def test_failed_repair_can_authorize_a_later_real_repair():
    game, first = armed()
    with patch.object(Balance, "REPAIR_JOB_FAIL_P_BASE", 1.0):
        Engine().tick(game, first.eta_s)
    assert game.jobs.jobs[first.internal_id].status == JobStatus.FAILED
    old = game.ship.physical_transit.recovery_intent
    assert old.status == "cancelled"
    second = enqueue_repair(game)
    new = Engine().arm_inertial_recovery(game, second.internal_id, max_capsules=10)
    assert new.attempt_id == 2 and new.job_id != old.job_id
    Engine().tick(game, second.eta_s)
    assert game.jobs.jobs[second.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.recovery_execution is not None
    assert len([e for e in game.events.recent if e.type == EventType.JOB_FAILED]) == 1


@pytest.mark.parametrize("mode", ["fuel", "insufficient", "power"])
def test_new_manual_authorization_still_revalidates_current_conditions(mode):
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    if mode == "fuel":
        game.ship.antimatter_capsules = .01
    elif mode == "insufficient":
        game.ship.systems["engines"].forced_offline = True
        Engine()._apply_health_state(game.ship.systems["engines"], game, [], cause="test")
    else:
        game.ship.systems["energy_distribution"].forced_offline = True
        Engine()._apply_health_state(game.ship.systems["energy_distribution"], game, [], cause="test")
    Engine().authorize_manual_inertial_recovery(game, max_capsules=10)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        Engine().prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before


def test_stale_plan_after_inertial_motion_cannot_spend_new_authorization():
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    Engine().authorize_manual_inertial_recovery(game, max_capsules=10)
    stale = plan_inertial_recovery(game)
    Engine().tick(game, 1)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="stale"):
        Engine().prepare_inertial_recovery(game, stale)
    assert pickle.dumps(game) == before
    Engine().prepare_inertial_recovery(game)
    assert game.ship.physical_transit.recovery_intent.status == "used"


def test_old_seven_field_intent_payload_loads_without_reactivation():
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    old = game.ship.physical_transit.recovery_intent
    legacy_values = old.__getstate__()[:7]
    restored = object.__new__(RecoveryIntent)
    restored.__setstate__(legacy_values)
    assert restored.status == "cancelled"
    assert restored.attempt_id == 1 and restored.previous_cancelled is None
    assert pickle.loads(pickle.dumps(restored)) == restored
    current_getstate = RecoveryIntent.__getstate__
    with patch.object(RecoveryIntent, "__getstate__",
                      lambda self: current_getstate(self)[:7]):
        legacy_save = pickle.dumps(game)
    loaded = pickle.loads(legacy_save)
    assert loaded.ship.physical_transit.recovery_intent == restored
    with pytest.raises(RuntimeError):
        Engine().prepare_inertial_recovery(loaded)


def test_new_authorization_rejects_invalid_limit_without_replacing_cancellation():
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    before = pickle.dumps(game)
    with pytest.raises(ValueError):
        Engine().authorize_manual_inertial_recovery(game, max_capsules=float("inf"))
    assert pickle.dumps(game) == before


def test_explicit_manual_cancellation_allows_a_larger_new_limit():
    game, first = armed(max_capsules=.01)
    Engine().tick(game, first.eta_s)
    first_cancelled = game.ship.physical_transit.recovery_intent
    fuel = game.ship.antimatter_capsules
    motion = game.ship.physical_transit.motion
    Engine().authorize_manual_inertial_recovery(game, max_capsules=.01)
    with pytest.raises(RuntimeError, match="spending limit"):
        Engine().prepare_inertial_recovery(game)
    assert game.ship.physical_transit.recovery_intent.status == "pending"
    assert game.ship.antimatter_capsules == fuel
    second_cancelled = Engine().cancel_manual_inertial_recovery(game)
    assert second_cancelled.attempt_id == 2
    assert second_cancelled.status == "cancelled"
    assert game.ship.physical_transit.motion == motion
    assert game.ship.antimatter_capsules == fuel
    third = Engine().authorize_manual_inertial_recovery(game, max_capsules=10)
    assert third.attempt_id == 3
    assert third.previous_cancelled == (2, None, "manual_cancelled")
    assert first_cancelled.status == "cancelled"
    Engine().prepare_inertial_recovery(game)
    assert game.ship.physical_transit.recovery_intent.attempt_id == 3
    assert game.ship.physical_transit.recovery_intent.status == "used"
    with pytest.raises(RuntimeError):
        Engine().cancel_manual_inertial_recovery(game)
