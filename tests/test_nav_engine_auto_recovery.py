"""C2B2A: one authorized repair may install a fresh physical recovery."""
from copy import deepcopy
from dataclasses import replace
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.actions import Repair
from retorno.core.engine import Engine
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_repair_inertia import enqueue_repair, repairable_inertia


def armed(max_capsules=10):
    game = repairable_inertia()
    job = enqueue_repair(game)
    Engine().arm_inertial_recovery(game, job.internal_id, max_capsules=max_capsules)
    return game, job


def test_explicit_arming_changes_only_authorization_and_rejects_reuse():
    game = repairable_inertia()
    job = enqueue_repair(game)
    prior = deepcopy(game)
    intent = Engine().arm_inertial_recovery(game, job.internal_id, max_capsules=2)
    assert intent.job_id == job.internal_id and intent.status == "pending"
    assert game.ship.physical_transit.recovery_intent == intent
    game.ship.physical_transit = replace(game.ship.physical_transit, recovery_intent=None)
    assert game == prior
    game.ship.physical_transit = replace(game.ship.physical_transit, recovery_intent=intent)
    with pytest.raises(RuntimeError):
        Engine().arm_inertial_recovery(game, job.internal_id, max_capsules=2)
    with pytest.raises(RuntimeError):
        Engine().arm_inertial_recovery(game, "MISSING", max_capsules=2)


@pytest.mark.parametrize("limit", [0, -1, float("inf"), float("nan")])
def test_invalid_limit_rejects_without_state_change(limit):
    game = repairable_inertia()
    job = enqueue_repair(game)
    before = pickle.dumps(game)
    with pytest.raises(ValueError):
        Engine().arm_inertial_recovery(game, job.internal_id, max_capsules=limit)
    assert pickle.dumps(game) == before


def test_real_repair_installs_fresh_paid_recovery_at_exact_boundary():
    game, job = armed()
    game = pickle.loads(pickle.dumps(game))
    fuel = game.ship.antimatter_capsules
    start = game.ship.physical_transit.motion
    history = game.ship.physical_transit.inertial_continuation
    owners = tuple(getattr(game, name) for name in
                   ("ship", "clock", "world", "jobs", "events", "meta"))
    seen = []
    original = plan_inertial_recovery

    def fresh_plan(state, **kwargs):
        seen.append((state.jobs.jobs[job.internal_id].status,
                     state.ship.physical_transit.motion,
                     state.ship.systems["engines"].health))
        return original(state, **kwargs)

    with patch("retorno.core.engine.plan_inertial_recovery", side_effect=fresh_plan):
        GameLoop(Engine(), game).step(job.eta_s)
    physical = game.ship.physical_transit
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert seen and all(status == JobStatus.COMPLETED for status, _, _ in seen)
    assert all(motion == seen[0][1] for _, motion, _ in seen)
    assert seen[0][1].distance_m > start.distance_m
    assert physical.motion == seen[0][1]
    assert physical.motion.beta == start.beta
    assert physical.recovery_execution is not None
    assert physical.recovery_execution.inertial_history.interrupted_segment == history.interrupted_segment
    assert physical.recovery_execution.inertial_history.braking_substitution == history.braking_substitution
    assert physical.recovery_intent.status == "used"
    assert game.ship.antimatter_capsules == pytest.approx(
        fuel - physical.recovery_execution.authorization.capsules_paid)
    assert all(getattr(game, name) is owner for name, owner in zip(
        ("ship", "clock", "world", "jobs", "events", "meta"), owners))
    assert len([e for e in game.events.recent if e.type == EventType.JOB_COMPLETED]) == 1
    saved = pickle.loads(pickle.dumps(game))
    assert saved.ship.physical_transit.recovery_intent.status == "used"
    assert saved.ship.antimatter_capsules == game.ship.antimatter_capsules
    GameLoop(Engine(), saved).step(1)
    assert saved.ship.physical_transit.motion.distance_m > physical.motion.distance_m
    assert saved.ship.antimatter_capsules == game.ship.antimatter_capsules
    with pytest.raises(RuntimeError):
        Engine().prepare_inertial_recovery(saved)


def test_later_tick_reaches_physical_brake_without_second_charge():
    game, job = armed()
    Engine().tick(game, job.eta_s)
    fuel = game.ship.antimatter_capsules
    active = game.ship.physical_transit
    execution = active.recovery_execution
    assert execution is not None
    if active.intent == "coast":
        Engine().tick(game, active.active_segment.duration_galactic_s)
    assert game.ship.physical_transit.intent == "brake"
    beta = game.ship.physical_transit.motion.beta
    Engine().tick(game, game.ship.physical_transit.active_segment.duration_galactic_s / 2)
    assert 0 < game.ship.physical_transit.motion.beta < beta
    assert game.ship.antimatter_capsules == fuel
    assert game.ship.physical_transit.recovery_intent.status == "used"


def test_other_system_repair_cannot_arm_engine_recovery():
    game = repairable_inertia()
    game.ship.systems["power_core"].health = .8
    Engine().apply_action(game, Repair("D1", "power_core", auto_move=True))
    job = next(j for j in game.jobs.jobs.values()
               if j.target and j.target.id == "power_core")
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="engine repair"):
        Engine().arm_inertial_recovery(game, job.internal_id, max_capsules=10)
    assert pickle.dumps(game) == before


def test_tick_crossing_repair_matches_subdivided_recovery():
    game, job = armed()
    split = deepcopy(game)
    GameLoop(Engine(), game).step(job.eta_s + 2)
    GameLoop(Engine(), split).step(job.eta_s)
    GameLoop(Engine(), split).step(2)
    assert game.ship.physical_transit.motion == split.ship.physical_transit.motion
    assert game.ship.antimatter_capsules == split.ship.antimatter_capsules
    assert game.meta.rng_counter == split.meta.rng_counter
    assert game.ship.physical_transit.recovery_execution == split.ship.physical_transit.recovery_execution


@pytest.mark.parametrize("mode", ["limit", "fuel", "failed", "insufficient", "isolated", "power"])
def test_unavailable_recovery_keeps_productive_result_and_coasts(mode):
    game, job = armed(max_capsules=.01 if mode == "limit" else 10)
    if mode == "fuel":
        game.ship.antimatter_capsules = .01
    elif mode == "insufficient":
        game.jobs.jobs[job.internal_id].params["repair_amount"] = .001
    elif mode == "isolated":
        game.ship.systems["engines"].forced_offline = True
        Engine()._apply_health_state(game.ship.systems["engines"], game, [], cause="test")
    elif mode == "power":
        game.ship.systems["energy_distribution"].forced_offline = True
        Engine()._apply_health_state(game.ship.systems["energy_distribution"], game, [], cause="test")
    fuel = game.ship.antimatter_capsules
    before = game.ship.physical_transit.motion
    if mode == "failed":
        with patch.object(Balance, "REPAIR_JOB_FAIL_P_BASE", 1.0):
            Engine().tick(game, job.eta_s)
    else:
        Engine().tick(game, job.eta_s)
    physical = game.ship.physical_transit
    assert game.jobs.jobs[job.internal_id].status in {JobStatus.COMPLETED, JobStatus.FAILED}
    assert physical.inertial_continuation is not None
    assert physical.recovery_execution is None
    assert physical.recovery_intent.status == "cancelled"
    assert physical.motion.distance_m > before.distance_m
    assert physical.motion.beta == before.beta
    assert game.ship.antimatter_capsules == fuel
    saved = pickle.loads(pickle.dumps(game))
    Engine().tick(saved, 1)
    assert saved.ship.physical_transit.recovery_intent.status == "cancelled"
    assert saved.ship.antimatter_capsules == fuel


def test_without_intent_repair_stays_inertial_and_manual_api_remains_available():
    game = repairable_inertia()
    job = enqueue_repair(game)
    Engine().tick(game, job.eta_s)
    assert game.ship.physical_transit.inertial_continuation is not None
    assert game.ship.physical_transit.recovery_execution is None
    Engine().prepare_inertial_recovery(game)
    assert game.ship.physical_transit.recovery_execution is not None


def test_unsupported_post_repair_horizon_rolls_back_everything():
    game, job = armed()
    game.world.lore_placements.next_non_forced_eval_t = game.clock.t + job.eta_s + 1
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        Engine().tick(game, job.eta_s + 2)
    assert pickle.dumps(game) == before


def test_preexisting_concurrent_job_rejects_atomically():
    game, job = armed()
    other = deepcopy(job)
    other.internal_id = "JOB2"
    other.job_id = "J2"
    other.status = JobStatus.RUNNING
    game.jobs.jobs[job.internal_id].status = JobStatus.RUNNING
    game.jobs.jobs[other.internal_id] = other
    game.jobs.active_job_ids.append(other.internal_id)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="one eligible repair interval"):
        Engine().tick(game, job.eta_s)
    assert pickle.dumps(game) == before


def test_job_pending_at_completion_cancels_intent_but_keeps_repair():
    game, job = armed()
    original = Engine._resolve_job_interval

    def finish_with_new_pending(engine, state, interval, **kwargs):
        events, resolved = original(engine, state, interval, **kwargs)
        if job.internal_id in resolved:
            pending = deepcopy(state.jobs.jobs[job.internal_id])
            pending.internal_id = "JOB2"
            pending.job_id = "J2"
            pending.status = JobStatus.QUEUED
            state.jobs.jobs[pending.internal_id] = pending
            state.jobs.active_job_ids.append(pending.internal_id)
        return events, resolved

    with patch.object(Engine, "_resolve_job_interval", finish_with_new_pending):
        Engine().tick(game, job.eta_s)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.inertial_continuation is not None
    assert game.ship.physical_transit.recovery_intent.outcome == "concurrent_jobs"
    assert game.ship.physical_transit.recovery_execution is None
