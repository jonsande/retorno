"""Real scheduler phases for a future causal physical-navigation consumer."""
from copy import deepcopy

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.model.jobs import Job, JobStatus, JobType, RiskProfile, TargetRef


def game():
    state = create_initial_state_sandbox(seed=731)
    state.ship.drones.clear()
    state.jobs.jobs.clear()
    state.jobs.active_job_ids.clear()
    return state


def add_job(state, key, kind, target, eta, *, status=JobStatus.RUNNING, owner=None,
            amount=0.2, params=None, draw=0.0):
    values = {"repair_amount": amount, "repair_scrap": 0}
    values.update(params or {})
    job = Job(key, kind, status, eta, owner_id=owner,
              target=TargetRef("ship_system", target), params=values,
              power_draw_kw=draw)
    state.jobs.jobs[key] = job
    state.jobs.active_job_ids.append(key)
    return job


def test_repair_applies_only_after_prior_wear(monkeypatch):
    monkeypatch.setattr(Balance, "REPAIR_JOB_FAIL_P_BASE", 0.0)
    state = game()
    engine = Engine()
    motors = state.ship.systems["engines"]
    motors.health = 0.4
    motors.base_decay_per_s = 0.02
    job = add_job(state, "J1", JobType.REPAIR_SYSTEM, "engines", 5.0)

    interval, start_events = engine._begin_job_interval(state)
    assert start_events == []
    assert engine._next_job_completion_s(state, interval) == 5.0
    assert engine._next_job_completion_s(state, interval) == 5.0
    assert state.meta.rng_counter == 0
    assert engine._compute_load_kw(state) >= job.power_draw_kw

    engine._advance_job_timers(state, interval, 5.0)
    assert job.eta_s == 0
    assert motors.health == 0.4
    engine._apply_degradation(state, 5.0, 1.0, False, 0.0,
                              in_transit=False, op_mode="CRUISE")
    assert motors.health == pytest.approx(0.3)
    state.clock.t = 5.0
    events, finished = engine._resolve_job_interval(state, interval)
    assert finished == ("J1",)
    assert motors.health == pytest.approx(0.5)
    assert job.status == JobStatus.COMPLETED
    assert [event.type for event in events].count(EventType.JOB_COMPLETED) == 1
    assert all(event.t == 5 for event in events)
    with pytest.raises(ValueError, match="already resolved"):
        engine._resolve_job_interval(state, interval)


def test_two_repairs_and_module_finish_in_scheduler_order(monkeypatch):
    monkeypatch.setattr(Balance, "REPAIR_JOB_FAIL_P_BASE", 0.0)
    state = game()
    motors = state.ship.systems["engines"]
    motors.health = 0.2
    add_job(state, "J1", JobType.REPAIR_SYSTEM, "engines", 3.0, amount=0.2)
    add_job(state, "J2", JobType.INSTALL_MODULE, "engines", 3.0,
            params={"module_id": "engine_speed_upgrade_01"})
    add_job(state, "J3", JobType.REPAIR_SYSTEM, "engines", 3.0, amount=0.2)
    state.ship.cargo_modules.append("engine_speed_upgrade_01")
    engine = Engine()
    interval, _ = engine._begin_job_interval(state)
    assert engine._next_job_completion_s(state, interval) == 3.0
    engine._advance_job_timers(state, interval, 3.0)
    state.clock.t = 3.0
    events, finished = engine._resolve_job_interval(state, interval)
    assert finished == ("J1", "J2", "J3")
    assert motors.health == pytest.approx(0.6)
    assert "engine_speed_upgrade_01" in state.ship.installed_modules
    assert [event.data["job_key"] for event in events if event.type == EventType.JOB_COMPLETED] == ["J1", "J2", "J3"]
    assert state.jobs.active_job_ids == []


def test_owner_is_released_and_queued_job_starts_at_same_instant(monkeypatch):
    monkeypatch.setattr(Balance, "REPAIR_JOB_FAIL_P_BASE", 0.0)
    state = game()
    state.ship.systems["engines"].health = 0.2
    add_job(state, "J1", JobType.SELFTEST_REPAIR, "engines", 2.0, owner="worker")
    queued = add_job(state, "J2", JobType.SELFTEST_REPAIR, "engines", 0.0,
                     status=JobStatus.QUEUED, owner="worker")
    engine = Engine()
    first, _ = engine._begin_job_interval(state)
    assert first.job_keys == ("J1",)
    assert queued.status == JobStatus.QUEUED
    engine._advance_job_timers(state, first, 2.0)
    state.clock.t = 2.0
    events, finished = engine._resolve_job_interval(state, first)
    assert finished == ("J1",)
    second, _ = engine._begin_job_interval(state)
    assert second.job_keys == ("J2",)
    assert queued.status == JobStatus.RUNNING
    assert engine._next_job_completion_s(state, second) == 0.0
    engine._advance_job_timers(state, second, 0.0)
    more, finished = engine._resolve_job_interval(state, second)
    assert finished == ("J2",)
    assert state.clock.t == 2.0
    assert [event.data["job_key"] for event in events + more if event.type == EventType.JOB_COMPLETED] == ["J1", "J2"]


def test_future_slice_cannot_skip_a_completion_or_resolve_twice():
    state = game()
    add_job(state, "J1", JobType.SELFTEST_REPAIR, "engines", 1.0)
    engine = Engine()
    interval, _ = engine._begin_job_interval(state)
    with pytest.raises(ValueError, match="pass a completion boundary"):
        engine._advance_job_timers(state, interval, 2.0)
    assert state.jobs.jobs["J1"].eta_s == 1.0
    engine._advance_job_timers(state, interval, 0.5)
    with pytest.raises(ValueError, match="stale"):
        engine._next_job_completion_s(state, interval)
    engine._resolve_job_interval(state, interval)
    assert state.jobs.jobs["J1"].eta_s == 0.5
    with pytest.raises(ValueError, match="already resolved"):
        engine._resolve_job_interval(state, interval)


def test_historical_entry_remains_deterministic_and_applies_effect_once(monkeypatch):
    monkeypatch.setattr(Balance, "REPAIR_JOB_FAIL_P_BASE", 0.0)
    before = game()
    before.ship.systems["engines"].health = 0.2
    add_job(before, "J1", JobType.REPAIR_SYSTEM, "engines", 3.0)
    first = deepcopy(before)
    second = deepcopy(before)
    engine = Engine()
    a = engine._process_jobs(first, 3.0)
    b = engine._process_jobs(second, 3.0)
    assert first.ship.systems["engines"].health == pytest.approx(0.4)
    assert first.jobs.jobs["J1"].status == JobStatus.COMPLETED
    assert [(e.type, e.data) for e in a] == [(e.type, e.data) for e in b]
    assert first.ship.systems["engines"].health == second.ship.systems["engines"].health
    assert engine._process_jobs(first, 1.0) == []
    assert first.ship.systems["engines"].health == pytest.approx(0.4)


def test_confirmation_and_terminal_jobs_do_not_advance():
    state = game()
    engine = Engine()
    baseline_load = engine._compute_load_kw(state)
    waiting = add_job(state, "J1", JobType.REPAIR_SYSTEM, "engines", 4.0,
                      status=JobStatus.QUEUED,
                      params={"awaiting_auto_move_confirmation": True}, draw=2.0)
    cancelled = add_job(state, "J2", JobType.SELFTEST_REPAIR, "engines", 0.0,
                        status=JobStatus.CANCELLED)
    interval, _ = engine._begin_job_interval(state)
    assert interval.job_keys == ()
    assert waiting.status == JobStatus.RUNNING
    assert waiting.eta_s == 4.0
    assert engine._compute_load_kw(state) == pytest.approx(baseline_load + 2.0)
    assert cancelled.job_id not in state.jobs.active_job_ids
    assert engine._next_job_completion_s(state, interval) is None
    engine._advance_job_timers(state, interval, 0.0)
    assert engine._resolve_job_interval(state, interval) == ([], ())


def test_activation_changes_real_load_only_while_running(monkeypatch):
    monkeypatch.setattr(Balance, "REPAIR_JOB_FAIL_P_BASE", 0.0)
    state = game()
    state.ship.systems["engines"].health = 0.2
    engine = Engine()
    baseline = engine._compute_load_kw(state)
    add_job(state, "J1", JobType.SELFTEST_REPAIR, "engines", 1.0,
            status=JobStatus.QUEUED, draw=3.0)
    assert engine._compute_load_kw(state) == pytest.approx(baseline)
    interval, _ = engine._begin_job_interval(state)
    assert engine._compute_load_kw(state) == pytest.approx(baseline + 3.0)
    engine._advance_job_timers(state, interval, 1.0)
    state.clock.t = 1.0
    engine._resolve_job_interval(state, interval)
    assert engine._compute_load_kw(state) == pytest.approx(
        sum(system.p_effective_kw() for system in state.ship.systems.values()
            if system.state.value != "offline"))


def test_risk_is_sampled_only_at_resolution_and_once():
    state = game()
    motors = state.ship.systems["engines"]
    motors.health = 0.2
    job = add_job(state, "J1", JobType.SELFTEST_REPAIR, "engines", 2.0,
                  params={"emergency": True}, amount=0.2)
    job.risk = RiskProfile(p_fail_per_s=1.0)
    engine = Engine()
    interval, _ = engine._begin_job_interval(state)
    assert engine._next_job_completion_s(state, interval) == 2.0
    assert engine._next_job_completion_s(state, interval) == 2.0
    assert state.meta.rng_counter == 0
    engine._advance_job_timers(state, interval, 2.0)
    assert motors.health == 0.2
    state.clock.t = 2.0
    events, finished = engine._resolve_job_interval(state, interval)
    assert finished == ("J1",)
    assert job.status == JobStatus.FAILED
    assert job.eta_s == 2.0  # Historical failure leaves ETA unchanged.
    assert motors.health == 0.2
    assert len([e for e in events if e.type == EventType.JOB_FAILED]) == 1
    with pytest.raises(ValueError, match="already resolved"):
        engine._resolve_job_interval(state, interval)
