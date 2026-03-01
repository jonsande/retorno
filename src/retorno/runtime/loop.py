from __future__ import annotations

import threading
import random
import time
from contextlib import contextmanager

from retorno.core.actions import Action
from retorno.core.engine import Engine
from retorno.core.gamestate import GameState
from retorno.model.events import Event


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
        with self._lock:
            events = self.engine.tick(self.state, dt)
            return events

    def step_many(self, total_s: float, dt: float = 1.0) -> list[Event]:
        events: list[Event] = []
        remaining = total_s
        while remaining > 0:
            step_dt = dt if remaining >= dt else remaining
            events.extend(self.step(step_dt))
            remaining -= step_dt
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
            with self._lock:
                events = self.engine.tick(self.state, self.tick_s)
                self._events_auto.extend(events)
