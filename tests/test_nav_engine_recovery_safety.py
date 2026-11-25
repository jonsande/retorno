"""C2B1-R1: jobs cannot be skipped and external braking has a physical cap."""
import pickle

import pytest

from retorno.core.actions import Repair
from retorno.core.engine import Engine
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus, JobType
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from tests.test_nav_engine_recovery_execution import repaired_ship
from tests.test_nav_engine_repair_inertia import enqueue_repair
from tests.test_nav_engine_safety_brake import save_and_load


def _owners(game):
    return tuple(getattr(game, name) for name in
                 ("ship", "clock", "world", "jobs", "events", "meta"))


def _same_owners(game, owners):
    return all(current is original for current, original in zip(_owners(game), owners))


@pytest.mark.parametrize("kind", ("queued", "running", "other_system"))
def test_productive_job_after_recovery_preparation_blocks_tick_atomically(kind):
    game = repaired_ship()
    plan = plan_inertial_recovery(game)
    Engine().prepare_inertial_recovery(game, plan)
    fuel = game.ship.antimatter_capsules
    battery = game.ship.drones["D1"].battery
    if kind == "other_system":
        # A real auto-move and repair order exercises another target and its
        # productive queue, not a hand-edited Job.status.
        game.ship.systems["power_core"].health = .8
        events = Engine().apply_action(game, Repair("D1", "power_core", auto_move=True))
        assert any(event.type == EventType.JOB_QUEUED for event in events)
        assert any(job.job_type == JobType.REPAIR_SYSTEM
                   and job.target and job.target.id == "power_core"
                   for job in game.jobs.jobs.values())
    else:
        job = enqueue_repair(game)
        assert job.status == JobStatus.QUEUED
        if kind == "running":
            interval, events = Engine()._begin_job_interval(game)
            assert interval.job_keys == (job.internal_id,)
            assert events == []
            assert game.jobs.jobs[job.internal_id].status == JobStatus.RUNNING
    assert game.jobs.active_job_ids
    assert game.ship.antimatter_capsules == fuel
    assert game.ship.drones["D1"].battery == battery
    before = pickle.dumps(game)
    owners = _owners(game)
    etas = {key: job.eta_s for key, job in game.jobs.jobs.items()}
    event_count = len(game.events.recent)
    rng = game.meta.rng_counter
    with pytest.raises(RuntimeError, match="pending physical jobs"):
        GameLoop(Engine(), game).step(1)
    assert pickle.dumps(game) == before
    assert _same_owners(game, owners)
    assert {key: job.eta_s for key, job in game.jobs.jobs.items()} == etas
    assert len(game.events.recent) == event_count
    assert game.meta.rng_counter == rng


@pytest.mark.parametrize("corruption", ("orphan_queued", "stale_active_id"))
def test_recovery_tick_rejects_inconsistent_job_index(corruption):
    game = repaired_ship()
    Engine().prepare_inertial_recovery(game)
    job = enqueue_repair(game)
    if corruption == "orphan_queued":
        game.jobs.active_job_ids.clear()
        assert job.status == JobStatus.QUEUED
    else:
        game.jobs.active_job_ids.append("missing-job")
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="pending physical jobs"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_deployed_drone_without_jobs_still_advances_recovery():
    game = repaired_ship()
    assert game.ship.drones and not game.jobs.active_job_ids
    plan = plan_inertial_recovery(game)
    Engine().prepare_inertial_recovery(game, plan)
    initial_motion = game.ship.physical_transit.motion
    battery = game.ship.drones["D1"].battery
    GameLoop(Engine(), game).step(1)
    assert game.ship.physical_transit.motion.distance_m > initial_motion.distance_m
    assert game.ship.drones["D1"].battery < battery


@pytest.mark.parametrize("deceleration", (5e6, 1e7))
def test_verified_external_deceleration_executes_once(deceleration):
    game = repaired_ship()
    plan = plan_inertial_recovery(game, proper_deceleration_m_s2=deceleration)
    assert plan.is_current(game, proper_deceleration_m_s2=deceleration)
    assert plan.decision == "coast_then_brake"
    fuel = game.ship.antimatter_capsules
    owners = _owners(game)
    Engine().prepare_inertial_recovery(
        game, plan, proper_deceleration_m_s2=deceleration)
    receipt = game.ship.physical_transit.recovery_execution.authorization
    assert game.ship.antimatter_capsules == pytest.approx(fuel - receipt.capsules_paid)
    assert _same_owners(game, owners)
    game = save_and_load(game)
    last = plan.segments[-1]
    GameLoop(Engine(), game).step(last.start.galactic_s + last.duration_galactic_s - game.clock.t)
    assert game.ship.physical_transit is None
    assert game.world.current_node_id in {"NOMINAL_B", game.world.active_tmp_node_id}
    assert game.ship.antimatter_capsules == pytest.approx(fuel - receipt.capsules_paid)


@pytest.mark.parametrize("deceleration", (2e7, 1e12))
def test_external_deceleration_above_historical_cap_rejects_before_payment(deceleration):
    game = repaired_ship()
    plan = plan_inertial_recovery(game, proper_deceleration_m_s2=deceleration)
    assert plan.decision == "coast_then_brake"  # Mathematical proposal only.
    assert plan.is_current(game, proper_deceleration_m_s2=deceleration)
    before = pickle.dumps(game)
    owners = _owners(game)
    with pytest.raises(RuntimeError, match="exceeds verified physical capacity"):
        Engine().prepare_inertial_recovery(
            game, plan, proper_deceleration_m_s2=deceleration)
    assert pickle.dumps(game) == before
    assert _same_owners(game, owners)


def test_changed_capacity_and_omitted_external_value_reject_without_payment():
    game = repaired_ship()
    plan = plan_inertial_recovery(game, proper_deceleration_m_s2=5e6)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="stale"):
        Engine().prepare_inertial_recovery(game, plan)
    assert pickle.dumps(game) == before
    game.ship.systems["engines"].forced_offline = True
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="stale"):
        Engine().prepare_inertial_recovery(
            game, plan, proper_deceleration_m_s2=5e6)
    assert pickle.dumps(game) == before


def test_operational_loss_before_recovery_braking_preserves_direct_atomicity_and_public_elapsed():
    game = repaired_ship()
    plan = plan_inertial_recovery(game)
    Engine().prepare_inertial_recovery(game, plan)
    # The operational loss is already present before the requested advance.
    # Direct and public paths reject it without recording fictitious time.
    game.ship.systems["engines"].forced_offline = True
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="braking point"):
        Engine().tick(game, plan.coast_segment.duration_galactic_s + 1)
    assert pickle.dumps(game) == before
    with pytest.raises(NavigationAdvanceBlocked, match="braking point") as blocked:
        GameLoop(Engine(), game).step(plan.coast_segment.duration_galactic_s + 1)
    assert blocked.value.elapsed_s == 0
    assert pickle.dumps(game) == before


def test_c1_inertial_repair_scheduler_still_completes_productive_job():
    from tests.test_nav_engine_repair_inertia import repairable_inertia
    game = repairable_inertia()
    job = enqueue_repair(game)
    GameLoop(Engine(), game).step(job.eta_s)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.inertial_continuation is not None
