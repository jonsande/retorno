from __future__ import annotations

import threading
import random
import time
import math
from typing import Callable
from contextlib import contextmanager

from retorno.core.actions import Action
from retorno.core.engine import Engine
from retorno.core.gamestate import GameState
from retorno.model.events import Event, EventType, Severity, SourceRef


class NavigationAdvanceBlocked(RuntimeError):
    """A supported public advance stopped at a causal boundary without losing time."""

    def __init__(self, reason: str, elapsed_s: float, events: list[Event]) -> None:
        super().__init__(reason)
        self.elapsed_s = elapsed_s
        self.events = events


class GameLoop:
    _AUTO_CATCHUP_STEPS = 2
    _AUTO_CATCHUP_YIELD_S = 0.05

    def __init__(self, engine: Engine, state: GameState, tick_s: float = 1.0) -> None:
        if not math.isfinite(tick_s) or tick_s <= 0:
            raise ValueError("automatic tick duration must be positive and finite")
        self.engine = engine
        self.state = state
        self.tick_s = tick_s
        self._lock = threading.Lock()
        self._events_auto: list[Event] = []
        self._events_cmd: list[Event] = []
        self._rng = random.Random(state.meta.rng_seed)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lifecycle_lock = threading.RLock()
        self._timing_lock = threading.Lock()
        self._auto_debt_s = 0.0
        self._auto_thread_id: int | None = None
        self._closed = False
        self._auto_tick_enabled = True
        self.last_auto_error: str | None = None

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._closed or not self._auto_tick_enabled:
                return
            if self._thread and self._thread.is_alive():
                if not self._stop.is_set():
                    return
                self._thread.join()
                if not self._auto_tick_enabled:
                    return
            self._set_auto_debt(0.0)
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop.set()
            worker = self._thread
            if worker is not None and worker is not threading.current_thread():
                worker.join()
                if self._thread is worker:
                    self._thread = None
            self._set_auto_debt(0.0)

    def set_auto_tick(self, enabled: bool) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            self._auto_tick_enabled = enabled
            if enabled:
                self.start()
            else:
                self.stop()

    def close(self) -> None:
        """Join the worker and permanently prevent automatic writes."""
        with self._lifecycle_lock:
            self._closed = True
            self._auto_tick_enabled = False
            self.stop()

    def auto_debt_s(self) -> float:
        """Read-only pending active time, including its fractional next tick."""
        with self._timing_lock:
            return self._auto_debt_s

    def _set_auto_debt(self, seconds: float) -> None:
        with self._timing_lock:
            self._auto_debt_s = max(0.0, seconds)

    def apply_action(self, action: Action) -> list[Event]:
        with self._lock:
            return self.engine.apply_action(self.state, action)

    def step(self, dt: float) -> list[Event]:
        events = self.advance_interval(dt)
        with self._lock:
            if dt > 0:
                self.state.clock.last_dt = dt
        return events

    def step_initial(self) -> bool:
        """Attempt the opening tick; keep a loadable session at a known causal limit."""
        try:
            self.step(self.tick_s)
        except NavigationAdvanceBlocked as exc:
            self._pause_auto_after_error(
                "physical_advance_blocked", str(exc), exc.events, exc.elapsed_s)
            return False
        return True

    def step_many(self, total_s: float, dt: float = 1.0) -> list[Event]:
        events: list[Event] = []
        remaining = total_s
        while remaining > 0:
            step_dt = dt if remaining >= dt else remaining
            events.extend(self.step(step_dt))
            remaining -= step_dt
        return events

    def advance_interval(self, total_s: float, *, stop_at_arrival: bool = False,
                         stop_when: Callable[[GameState, list[Event]], bool] | None = None,
                         single_causal_step: bool = False) -> list[Event]:
        """Advance at known physical phase ends; leave direct Engine.tick atomic.

        A fixed wait continues with ordinary rest time after a physical stop.
        An until-arrival wait stops there. Unsupported causal cuts report the
        amount already committed, while the failing tick changes no state.
        """
        if total_s < 0:
            raise ValueError("advance duration must be nonnegative")
        if threading.get_ident() != self._auto_thread_id:
            # Manual waits and hibernation start a fresh automatic-time epoch.
            # Join any active worker before touching the same state.
            self.stop()
        events: list[Event] = []
        elapsed = 0.0
        with self._lock:
            start_t = self.state.clock.t
            requested_end = start_t + total_s
            if total_s > 0 and requested_end == start_t:
                raise NavigationAdvanceBlocked(
                    "Physical phase cannot advance at clock resolution", 0.0, [])
            snapped_to_endpoint = False
            physical = self.state.ship.physical_transit
            if physical is not None and physical.nominal_plan is not None:
                final = physical.nominal_plan.segments[-1]
                endpoint = final.start.galactic_s + final.duration_galactic_s
                if abs(requested_end - endpoint) <= 16 * math.ulp(max(1.0, endpoint)):
                    requested_end = endpoint
                    snapped_to_endpoint = True
        while True:
            with self._lock:
                physical = self.state.ship.physical_transit
                step = requested_end - self.state.clock.t
                if not snapped_to_endpoint:
                    step = min(step, total_s - elapsed)
                if (elapsed > 0 and step > 0
                        and step <= 4 * math.ulp(max(1.0, requested_end))):
                    break
                if step <= 0:
                    break
                if self.state.clock.t + step == self.state.clock.t:
                    raise NavigationAdvanceBlocked(
                        "Physical phase cannot advance at clock resolution", elapsed, events)
                if physical is None and stop_at_arrival and self.state.ship.in_transit:
                    step = min(step, max(0.0, self.state.ship.arrival_t - self.state.clock.t))
                try:
                    if physical is not None:
                        step = self.engine.next_physical_step(self.state, step)
                    if step <= 0:
                        raise NavigationAdvanceBlocked("Physical phase cannot advance at clock resolution", elapsed, events)
                    batch = self.engine.tick(self.state, step)
                except RuntimeError as exc:
                    if physical is None or str(exc) not in self.engine._EXPECTED_PHYSICAL_LIMIT_REASONS:
                        raise
                    raise NavigationAdvanceBlocked(str(exc), elapsed, events) from exc
                events.extend(batch)
                elapsed = self.state.clock.t - start_t
                arrived = ((physical is not None and self.state.ship.physical_transit is None)
                           or (stop_at_arrival and not self.state.ship.in_transit
                               and physical is None))
                interrupted = stop_when(self.state, batch) if stop_when is not None else False
            if interrupted or (arrived and stop_at_arrival) or single_causal_step:
                break
        return events

    def drain_events(self) -> list[tuple[str, Event]]:
        with self._lock:
            return self._drain_events_locked()

    def _drain_events_locked(self) -> list[tuple[str, Event]]:
        """Drain automatic events while the caller owns the state lock."""
        events = [("auto", e) for e in self._events_auto]
        self._events_auto.clear()
        return events

    def get_state_snapshot(self) -> GameState:
        return self.state

    def get_rng(self) -> random.Random:
        return self._rng

    @contextmanager
    def with_lock(self):
        self._lock.acquire()
        try:
            yield self.state
        finally:
            self._lock.release()

    @contextmanager
    def with_lock_if_available(self):
        """Permit presentation to skip a busy engine frame without blocking UI."""
        if not self._lock.acquire(blocking=False):
            yield None
            return
        try:
            yield self.state
        finally:
            self._lock.release()

    def _pause_auto_after_error(self, reason: str, detail: str,
                                events: list[Event], elapsed_s: float) -> None:
        with self._lock:
            seq = self.state.events.next_event_seq
            self.state.events.next_event_seq += 1
            warning = Event(
                event_id=f"E{seq:05d}", t=int(self.state.clock.t),
                type=EventType.BOOT_BLOCKED, severity=Severity.WARN,
                source=SourceRef(kind="ship", id=self.state.ship.ship_id),
                message="Automatic physical time advance stopped",
                data={"message_key": "boot_blocked", "reason": reason,
                      "detail": detail, "elapsed_s": elapsed_s,
                      "remaining_s": max(0.0, self.tick_s - elapsed_s)},
            )
            self.state.events.recent.append(warning)
            self._events_auto.extend(events)
            self._events_auto.append(warning)
            self.last_auto_error = detail
            self._auto_tick_enabled = False
            self._stop.set()
        self._set_auto_debt(0.0)

    def _run(self) -> None:
        self._auto_thread_id = threading.get_ident()
        last = time.monotonic()
        pending = 0.0
        due_tolerance = min(1e-9, self.tick_s * 1e-6)
        try:
            while not self._stop.is_set():
                if self._stop.wait(max(0.0, self.tick_s - pending)):
                    break
                now = time.monotonic()
                pending += max(0.0, now - last)
                last = now
                self._set_auto_debt(pending)
                steps = 0
                while pending + due_tolerance >= self.tick_s and steps < self._AUTO_CATCHUP_STEPS:
                    if self._stop.is_set():
                        break
                    with self._lock:
                        before_t = self.state.clock.t
                    try:
                        events = self.advance_interval(self.tick_s)
                    except NavigationAdvanceBlocked as exc:
                        self._pause_auto_after_error(
                            "physical_advance_blocked", str(exc), exc.events, exc.elapsed_s)
                        return
                    except Exception as exc:
                        self._pause_auto_after_error(
                            "automatic_internal_error", f"{type(exc).__name__}: {exc}", [], 0.0)
                        return
                    with self._lock:
                        committed = self.state.clock.t - before_t
                        self._events_auto.extend(events)
                    if committed <= 0:
                        self._pause_auto_after_error(
                            "physical_advance_blocked",
                            "Automatic advance committed no galactic time", [], 0.0)
                        return
                    now = time.monotonic()
                    pending = max(0.0, pending + max(0.0, now - last) - committed)
                    last = now
                    self._set_auto_debt(pending)
                    steps += 1
                    if (pending + due_tolerance >= self.tick_s
                            and self._stop.wait(self._AUTO_CATCHUP_YIELD_S)):
                        break
        finally:
            self._auto_thread_id = None
            self._set_auto_debt(0.0)
