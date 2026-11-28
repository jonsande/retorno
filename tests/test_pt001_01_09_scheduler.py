"""PT001-01/09-B: automatic-time debt and worker lifecycle."""
from __future__ import annotations

from pathlib import Path
from threading import Event, Lock, Thread
import time
from types import SimpleNamespace

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.actions import EngineSpeed, Travel
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import Event as GameEvent, EventType, Severity, SourceRef
import retorno.runtime.loop as loop_module
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from tests.test_nav_public_physical import public_game


class VirtualTime:
    def __init__(self):
        self.now = 0.0
        self.waits = []
        self.stopped = False

    def monotonic(self):
        return self.now

    def wait(self, seconds):
        self.waits.append(seconds)
        if self.stopped:
            return True
        self.now += max(0.0, seconds)
        return False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True


def virtual_run(monkeypatch, work, ticks):
    clock = VirtualTime()
    monkeypatch.setattr(loop_module, "time", SimpleNamespace(monotonic=clock.monotonic))
    state = create_initial_state_sandbox(seed=29)
    loop = GameLoop(Engine(), state)
    loop._stop = clock
    starts, debts = [], []

    def advance(requested):
        starts.append(clock.now)
        debts.append(loop.auto_debt_s())
        clock.now += work[len(starts) - 1]
        with loop.with_lock() as current:
            current.clock.t += requested
            current.clock.ship_elapsed_s += requested
        if len(starts) >= ticks:
            clock.set()
        return []

    loop.advance_interval = advance
    loop._run()
    return loop, clock, starts, debts


def test_nominal_cadence_has_no_unexpected_catchup(monkeypatch):
    loop, clock, starts, debts = virtual_run(monkeypatch, [.1] * 4, 4)
    assert starts == pytest.approx([1, 2, 3, 4])
    assert loop.state.clock.t == 4
    assert loop.state.clock.ship_elapsed_s == 4
    assert all(debt == pytest.approx(1) for debt in debts)
    assert loop.auto_debt_s() == 0
    assert clock.now == pytest.approx(4.1)


def test_one_overrun_is_recovered_without_losing_elapsed_time(monkeypatch):
    loop, clock, starts, debts = virtual_run(monkeypatch, [1.4, .05, .05, .05, .05], 5)
    assert starts[0] == pytest.approx(1)
    assert starts[1] == pytest.approx(2.45)  # the overdue tick is recovered
    assert starts[-1] < 5.5
    assert loop.state.clock.t == 5
    assert clock.now - loop.state.clock.t < .5
    assert max(debts) > 1
    assert loop.auto_debt_s() == 0


def test_sustained_overrun_keeps_debt_and_yields(monkeypatch):
    loop, clock, starts, debts = virtual_run(monkeypatch, [1.25] * 5, 5)
    assert loop.state.clock.t == 5
    assert clock.now > 7
    assert debts[-1] > debts[1] > debts[0]
    assert sum(wait == pytest.approx(loop._AUTO_CATCHUP_YIELD_S)
               for wait in clock.waits) >= 4
    assert all(1.2 < right - left < 1.4 for left, right in zip(starts, starts[1:]))
    assert loop.auto_debt_s() == 0  # stopping deliberately discards pending debt


def test_scheduler_subtracts_committed_advance_not_requested_interval(monkeypatch):
    clock = VirtualTime()
    monkeypatch.setattr(loop_module, "time", SimpleNamespace(monotonic=clock.monotonic))
    state = create_initial_state_sandbox(seed=34)
    loop = GameLoop(Engine(), state)
    loop._stop = clock
    starts = []

    def short_advance(_requested):
        starts.append(clock.now)
        with loop.with_lock() as current:
            current.clock.t += .4
            current.clock.ship_elapsed_s += .4
        if len(starts) == 2:
            clock.set()
        return []

    loop.advance_interval = short_advance
    loop._run()
    assert starts == pytest.approx([1.0, 1.4])
    assert state.clock.t == pytest.approx(.8)


def test_partial_causal_advance_pauses_and_keeps_committed_time_and_events(monkeypatch):
    clock = VirtualTime()
    monkeypatch.setattr(loop_module, "time", SimpleNamespace(monotonic=clock.monotonic))
    state = create_initial_state_sandbox(seed=30)
    loop = GameLoop(Engine(), state)
    loop._stop = clock
    committed = GameEvent("TEST", 0, EventType.SYSTEM_STATE_CHANGED, Severity.WARN,
                          SourceRef("ship", state.ship.ship_id), "committed", {})

    def partial(_requested):
        with loop.with_lock() as current:
            current.clock.t += .4
            current.clock.ship_elapsed_s += .4
        raise NavigationAdvanceBlocked("synthetic causal cut", .4, [committed])

    loop.advance_interval = partial
    loop._run()
    assert state.clock.t == pytest.approx(.4)
    assert state.clock.ship_elapsed_s == pytest.approx(.4)
    events = [event for _, event in loop.drain_events()]
    assert events[0] is committed
    assert events[-1].data["reason"] == "physical_advance_blocked"
    assert events[-1].data["elapsed_s"] == .4
    assert events[-1].data["remaining_s"] == pytest.approx(.6)
    assert not loop._auto_tick_enabled
    assert loop.auto_debt_s() == 0


class ClockEngine:
    def tick(self, state, dt):
        state.clock.t += dt
        state.clock.ship_elapsed_s += dt
        return []


def test_manual_advance_pauses_worker_and_restart_starts_new_epoch():
    state = create_initial_state_sandbox(seed=31)
    loop = GameLoop(ClockEngine(), state, tick_s=.05)
    try:
        loop.start()
        time.sleep(.12)
        loop.advance_interval(2.0)
        assert not loop._thread or not loop._thread.is_alive()
        assert loop.auto_debt_s() == 0
        committed = state.clock.t
        time.sleep(.07)
        assert state.clock.t == committed
        loop.start()
        time.sleep(.015)
        assert state.clock.t == committed  # no old debt burst
        time.sleep(.06)
        assert state.clock.t > committed
    finally:
        loop.stop()


def test_deliberate_pause_discards_debt_and_resume_waits_a_full_period():
    state = create_initial_state_sandbox(seed=35)
    loop = GameLoop(ClockEngine(), state, tick_s=.05)
    try:
        loop.start()
        time.sleep(.07)
        loop.set_auto_tick(False)
        paused = state.clock.t
        assert loop.auto_debt_s() == 0
        time.sleep(.07)
        assert state.clock.t == paused
        loop.set_auto_tick(True)
        time.sleep(.01)
        assert state.clock.t == paused
        time.sleep(.06)
        assert state.clock.t > paused
    finally:
        loop.stop()


def test_stop_joins_inflight_tick_and_serializes_restart(tmp_path: Path):
    state = create_initial_state_sandbox(seed=32)
    loop = GameLoop(ClockEngine(), state, tick_s=.01)
    entered, release, second = Event(), Event(), Event()
    guard = Lock()
    active = maximum = calls = 0
    original = loop.advance_interval

    def gated(dt):
        nonlocal active, maximum, calls
        with guard:
            active += 1
            maximum = max(maximum, active)
            calls += 1
            if calls == 1:
                entered.set()
            else:
                second.set()
        assert release.wait(3)
        try:
            return original(dt)
        finally:
            with guard:
                active -= 1

    loop.advance_interval = gated
    loop.start()
    try:
        assert entered.wait(2)
        stopper = Thread(target=loop.stop)
        stopper.start()
        time.sleep(.03)
        assert stopper.is_alive()  # cannot save until the tick has finished
        restarter = Thread(target=loop.start)
        restarter.start()
        release.set()
        stopper.join(3)
        restarter.join(3)
        assert not stopper.is_alive() and not restarter.is_alive()
        assert second.wait(2)
        loop.stop()
        saved_clock = state.clock.t
        slot = tmp_path / "stopped.sav"
        with loop.with_lock() as current:
            save_single_slot(current, slot)
        time.sleep(.03)
        assert state.clock.t == saved_clock
        assert load_single_slot(slot).state.clock.t == saved_clock
        assert maximum == 1
    finally:
        release.set()
        loop.stop()


def test_close_prevents_automatic_writes_after_save(tmp_path: Path):
    state = create_initial_state_sandbox(seed=36)
    loop = GameLoop(ClockEngine(), state, tick_s=.01)
    loop.start()
    time.sleep(.025)
    loop.close()
    saved_clock = state.clock.t
    slot = tmp_path / "closed.sav"
    with loop.with_lock() as current:
        save_single_slot(current, slot)
    loop.start()
    loop.set_auto_tick(True)
    time.sleep(.03)
    assert state.clock.t == saved_clock
    assert load_single_slot(slot).state.clock.t == saved_clock
    assert loop._thread is None
    assert loop.auto_debt_s() == 0


def test_hibernation_and_resume_do_not_replay_old_debt():
    state = create_initial_state_sandbox(seed=33)
    loop = GameLoop(Engine(), state, tick_s=.05)
    loop.set_auto_tick(False)
    loop._set_auto_debt(3.0)
    start = state.clock.t
    result = repl._execute_hibernate(loop, 1 / Balance.YEAR_S)
    assert result.wake_reason is None
    assert state.clock.t - start == pytest.approx(1.0)
    assert loop.auto_debt_s() == 0
    assert not loop._auto_tick_enabled
    loop.set_auto_tick(True)
    try:
        before = state.clock.t
        time.sleep(.01)
        assert state.clock.t == before
    finally:
        loop.stop()


def test_auto_cruise_retains_relativistic_proper_time(monkeypatch):
    state = public_game(.11)
    engine = Engine()
    engine.apply_action(state, EngineSpeed(.1))
    engine.apply_action(state, Travel("NOMINAL_B"))
    coast = state.ship.physical_transit.nominal_plan.segments[1].start.galactic_s
    GameLoop(engine, state).advance_interval(coast + 100)
    clock = VirtualTime()
    monkeypatch.setattr(loop_module, "time", SimpleNamespace(monotonic=clock.monotonic))
    loop = GameLoop(Engine(), state)
    original = loop.advance_interval
    calls = 0

    def advance(dt):
        nonlocal calls
        events = original(dt)
        calls += 1
        if calls == 3:
            clock.set()
        return events

    loop.advance_interval = advance
    galactic, proper = state.clock.t, state.clock.ship_elapsed_s
    loop._stop = clock
    loop._run()
    assert state.clock.t - galactic == pytest.approx(3)
    assert state.clock.ship_elapsed_s - proper == pytest.approx(3 * (1 - .1**2) ** .5)
