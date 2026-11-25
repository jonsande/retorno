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
    def __init__(self, engine: Engine, state: GameState, tick_s: float = 1.0) -> None:
        self.engine = engine
        self.state = state
        self.tick_s = tick_s
        self._lock = threading.Lock()
        self._events_auto: list[Event] = []
        self._events_cmd: list[Event] = []
        self._rng = random.Random(state.meta.rng_seed)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._auto_tick_enabled = True

    def start(self) -> None:
        if not self._auto_tick_enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def set_auto_tick(self, enabled: bool) -> None:
        if self._auto_tick_enabled == enabled:
            return
        self._auto_tick_enabled = enabled
        if not enabled:
            self.stop()
        else:
            self.start()

    def apply_action(self, action: Action) -> list[Event]:
        with self._lock:
            return self.engine.apply_action(self.state, action)

    def step(self, dt: float) -> list[Event]:
        events = self.advance_interval(dt)
        with self._lock:
            if dt > 0:
                self.state.clock.last_dt = dt
        return events

    def step_many(self, total_s: float, dt: float = 1.0) -> list[Event]:
        events: list[Event] = []
        remaining = total_s
        while remaining > 0:
            step_dt = dt if remaining >= dt else remaining
            events.extend(self.step(step_dt))
            remaining -= step_dt
        return events

    def advance_interval(self, total_s: float, *, stop_at_arrival: bool = False,
                         stop_when: Callable[[GameState, list[Event]], bool] | None = None) -> list[Event]:
        """Advance at known physical phase ends; leave direct Engine.tick atomic.

        A fixed wait continues with ordinary rest time after a physical stop.
        An until-arrival wait stops there. Unsupported causal cuts report the
        amount already committed, while the failing tick changes no state.
        """
        if total_s < 0:
            raise ValueError("advance duration must be nonnegative")
        events: list[Event] = []
        elapsed = 0.0
        with self._lock:
            start_t = self.state.clock.t
            requested_end = start_t + total_s
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
                if step <= 0:
                    break
                clock_resolution = 16 * math.ulp(max(1.0, self.state.clock.t))
                if step <= clock_resolution:
                    if elapsed > 0 and abs(requested_end - self.state.clock.t) <= clock_resolution:
                        break
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
            if interrupted or (arrived and stop_at_arrival):
                break
        return events

    def drain_events(self) -> list[tuple[str, Event]]:
        with self._lock:
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

    def _run(self) -> None:
        while not self._stop.is_set():
            time.sleep(self.tick_s)
            try:
                events = self.advance_interval(self.tick_s)
            except NavigationAdvanceBlocked as exc:
                with self._lock:
                    seq = self.state.events.next_event_seq
                    self.state.events.next_event_seq += 1
                    warning = Event(
                        event_id=f"E{seq:05d}", t=int(self.state.clock.t),
                        type=EventType.BOOT_BLOCKED, severity=Severity.WARN,
                        source=SourceRef(kind="ship", id=self.state.ship.ship_id),
                        message="Automatic physical time advance stopped",
                        data={"message_key": "boot_blocked",
                              "reason": "physical_advance_blocked", "detail": str(exc),
                              "elapsed_s": exc.elapsed_s,
                              "remaining_s": max(0.0, self.tick_s - exc.elapsed_s)},
                    )
                    self.state.events.recent.append(warning)
                    self._events_auto.extend(exc.events)
                    self._events_auto.append(warning)
                    self._auto_tick_enabled = False
                    self._stop.set()
                break
            with self._lock:
                self._events_auto.extend(events)
