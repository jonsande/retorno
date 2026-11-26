"""Targeted closure regressions for R2 hibernation."""
from __future__ import annotations

import math

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.jobs import Job, JobStatus, JobType, TargetRef
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from tests.test_nav_public_causal import departed


def test_extended_hibernation_requires_stable_nominal_coast():
    state, loop = departed(distance_ly=30)
    assert state.ship.physical_transit.intent == "accelerate"
    assert not repl._hibernate_extended_chunk_safe(state, loop.engine)

    loop.advance_interval(state.ship.physical_transit.active_segment.duration_galactic_s)
    assert state.ship.physical_transit.intent == "coast"
    assert repl._hibernate_extended_chunk_safe(state, loop.engine)

    power = state.ship.power
    power.e_batt_kwh = power.e_batt_max_kwh - .01
    assert not repl._hibernate_extended_chunk_safe(state, loop.engine)
    power.e_batt_kwh = power.e_batt_max_kwh
    power.p_gen_base_kw = 0
    assert not repl._hibernate_extended_chunk_safe(state, loop.engine)
    power.p_gen_base_kw = 12
    assert repl._hibernate_extended_chunk_safe(state, loop.engine)

    job = Job("J-R2-F", JobType.SELFTEST_REPAIR, JobStatus.RUNNING, 100,
              target=TargetRef("ship_system", "sensors"),
              params={"repair_amount": .05, "repair_scrap": 0})
    state.jobs.jobs[job.internal_id] = job
    state.jobs.active_job_ids.append(job.internal_id)
    assert not repl._hibernate_extended_chunk_safe(state, loop.engine)
    state.jobs.active_job_ids.remove(job.internal_id)

    loop.advance_interval(state.ship.physical_transit.active_segment.duration_galactic_s)
    assert state.ship.physical_transit.intent == "brake"
    assert not repl._hibernate_extended_chunk_safe(state, loop.engine)


def _rest_at_large_clock():
    state = create_initial_state_sandbox(seed=414)
    state.clock.t = 1e9
    state.clock.ship_elapsed_s = 1e9
    loop = GameLoop(Engine(), state)
    loop._auto_tick_enabled = False
    return state, loop


def test_representational_final_remainder_does_not_repeat_or_count_time(monkeypatch):
    state, loop = _rest_at_large_clock()
    requested_s = 1.0 + math.ulp(state.clock.t) / 4
    years = requested_s / Balance.YEAR_S
    requested_s = years * Balance.YEAR_S
    assert state.clock.t + requested_s == state.clock.t + 1.0
    assert requested_s > 1.0
    original = loop.advance_interval
    calls = []

    def bounded_advance(*args, **kwargs):
        calls.append(args[0])
        assert len(calls) <= 2, "hibernation repeated an unrepresentable remainder"
        return original(*args, **kwargs)

    monkeypatch.setattr(loop, "advance_interval", bounded_advance)
    result = repl._execute_hibernate(loop, years)
    assert not result.woke_early
    assert state.clock.t == 1e9 + 1.0
    assert result.actual_years == (state.clock.t - 1e9) / Balance.YEAR_S


def test_no_progress_before_any_tick_wakes_with_technical_boundary():
    state, loop = _rest_at_large_clock()
    before = state.clock.t
    tiny = math.ulp(before) / 4
    with pytest.raises(NavigationAdvanceBlocked, match="clock resolution"):
        loop.advance_interval(tiny)
    result = repl._execute_hibernate(loop, tiny / Balance.YEAR_S)
    assert result.woke_early
    assert result.wake_reason.startswith("causal_boundary:")
    assert result.actual_years == 0
    assert state.clock.t == before


def test_real_pending_causal_boundary_is_not_discarded(monkeypatch):
    state, loop = departed()
    before = state.clock.t
    monkeypatch.setattr(loop.engine, "next_physical_step", lambda *_: 0.0)
    result = repl._execute_hibernate(loop, 1 / Balance.YEAR_S)
    loop.stop()
    assert result.woke_early
    assert result.wake_reason.startswith("causal_boundary:")
    assert result.actual_years == 0
    assert state.clock.t == before
