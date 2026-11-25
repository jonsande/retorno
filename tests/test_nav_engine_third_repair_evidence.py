"""C3B1-R1: a completed engine job must follow the second physical cut."""
from copy import deepcopy
from dataclasses import replace
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.jobs import JobStatus, TargetRef, allocate_job_ids, finalize_job
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_repair_inertia import enqueue_repair
from tests.test_nav_engine_recovery_reinterruption import recovery_brake_at_risk
from tests.test_nav_engine_second_inertia_repair import second_inertia
from tests.test_nav_engine_safety_brake import save_and_load


def _old_engine_repairs_before_second_cut():
    game, cut = recovery_brake_at_risk()
    old = next(job for job in game.jobs.jobs.values()
               if job.status == JobStatus.COMPLETED
               and job.target is not None and job.target.id == "engines")
    historical = deepcopy(old)
    key, display = allocate_job_ids(game.jobs)
    historical.internal_id = key
    historical.job_id = display
    historical.terminal_seq = None
    game.jobs.jobs[key] = historical
    finalize_job(game.jobs, key, JobStatus.COMPLETED)
    assert len([job for job in game.jobs.jobs.values()
                if job.status == JobStatus.COMPLETED
                and job.target is not None and job.target.id == "engines"]) == 2
    game = save_and_load(game)
    Engine().tick(game, cut)
    game.ship.systems["engines"].base_decay_per_s = 0
    game = save_and_load(game)
    Engine().tick(game, 1)
    return save_and_load(game)


def test_two_old_engine_repairs_cannot_authorize_after_second_cut():
    game = _old_engine_repairs_before_second_cut()
    physical = game.ship.physical_transit
    assert physical.recovery_interruption is not None
    assert physical.inertial_continuation is not None
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="repair after its current cut"):
        Engine().authorize_manual_inertial_recovery(game, max_capsules=100)
    assert pickle.dumps(game) == before
    with pytest.raises(RuntimeError, match="manual authorization"):
        Engine().prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before


def _assert_no_third_payment(game):
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="repair after its current cut"):
        Engine().authorize_manual_inertial_recovery(game, max_capsules=100)
    with pytest.raises(RuntimeError, match="manual authorization and repair"):
        Engine().prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_productive_completion_after_cut_persists_and_enables_manual_recovery(origin):
    game = save_and_load(second_inertia(origin, activate=False))
    cut = (game.ship.physical_transit.recovery_interruption
           or game.ship.physical_transit.recovery_coast_interruption).cut_motion
    assert game.ship.physical_transit.second_repair_evidence is None
    Engine().tick(game, 1)
    game = save_and_load(game)
    _assert_no_third_payment(game)
    job = enqueue_repair(game)
    GameLoop(Engine(), game).step(job.eta_s / 2)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.RUNNING
    assert game.ship.physical_transit.second_repair_evidence is None
    game = save_and_load(game)
    _assert_no_third_payment(game)
    GameLoop(Engine(), game).step(game.jobs.jobs[job.internal_id].eta_s)
    game = save_and_load(game)
    evidence = game.ship.physical_transit.second_repair_evidence
    assert evidence is not None
    assert evidence.cut_motion == cut
    assert evidence.interruption_kind == origin
    assert evidence.job_internal_id == job.internal_id
    assert evidence.terminal_seq == game.jobs.jobs[job.internal_id].terminal_seq
    assert evidence.completed_galactic_s == game.clock.t > cut.galactic_s
    assert evidence.engine_health_after > evidence.engine_health_before
    assert game.ship.physical_transit.inertial_continuation is not None
    fuel = game.ship.antimatter_capsules
    intent = Engine().authorize_manual_inertial_recovery(game, max_capsules=100)
    assert intent.status == "pending" and game.ship.antimatter_capsules == fuel
    state = Engine().prepare_inertial_recovery(game)
    assert state.second_repair_evidence is None
    assert state.recovery_lineage is not None
    assert len(state.recovery_lineage.recent) == 2
    assert game.ship.antimatter_capsules < fuel
    paid = game.ship.antimatter_capsules
    game = save_and_load(game)
    Engine().tick(game, 1)
    assert game.ship.antimatter_capsules == paid


@pytest.mark.parametrize(
    "outcome", ["failed", "cancelled", "queued", "running", "other_system"])
def test_nonqualifying_job_outcomes_do_not_create_evidence(outcome):
    game = second_inertia("brake")
    if outcome == "other_system":
        old = next(job for job in game.jobs.jobs.values()
                   if job.status == JobStatus.COMPLETED
                   and job.target is not None and job.target.id == "engines")
        unrelated = deepcopy(old)
        key, display = allocate_job_ids(game.jobs)
        unrelated.internal_id = key
        unrelated.job_id = display
        unrelated.terminal_seq = None
        unrelated.target = TargetRef("ship_system", "core_os")
        game.jobs.jobs[key] = unrelated
        finalize_job(game.jobs, key, JobStatus.COMPLETED)
    else:
        job = enqueue_repair(game)
        if outcome == "failed":
            with patch.object(Balance, "REPAIR_JOB_FAIL_P_BASE", 1.0):
                Engine().tick(game, job.eta_s)
            assert game.jobs.jobs[job.internal_id].status == JobStatus.FAILED
        elif outcome == "cancelled":
            finalize_job(game.jobs, job.internal_id, JobStatus.CANCELLED)
        elif outcome == "queued":
            assert game.jobs.jobs[job.internal_id].status == JobStatus.QUEUED
        else:
            Engine().tick(game, job.eta_s / 2)
            assert game.jobs.jobs[job.internal_id].status == JobStatus.RUNNING
    assert game.ship.physical_transit.second_repair_evidence is None
    _assert_no_third_payment(save_and_load(game))


def test_repair_evidence_cannot_be_attached_to_another_interruption():
    game = second_inertia("brake")
    job = enqueue_repair(game)
    Engine().tick(game, job.eta_s)
    evidence = game.ship.physical_transit.second_repair_evidence
    assert evidence is not None
    other = second_inertia("coast")
    with pytest.raises(ValueError, match="another interruption"):
        replace(other.ship.physical_transit, second_repair_evidence=evidence)
