"""Short read-only automatic-cadence probe; run explicitly, outside pytest discovery.

Example: PYTHONPATH=src:. ../retorno_venv/bin/python tests/nav_auto_cadence_probe.py
    --phase cruise --ticks 4 --textual
Use --save PATH to read a private copy of a real save. No input save is written.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
import threading
import time

from textual.widgets import Input, Static

from retorno.core.actions import EngineSpeed, Travel
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot
from retorno.runtime.loop import GameLoop
from retorno.ui_textual.app import RetornoTextualApp
from tests.nav_r2_benchmark import MeasuredLock
from tests.test_nav_public_physical import public_game


def private_clone(state):
    return pickle.loads(pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL))


def synthetic_phase(phase):
    state = public_game(.11)
    if phase == "rest":
        return state
    engine = Engine()
    engine.apply_action(state, EngineSpeed(.1))
    engine.apply_action(state, Travel("NOMINAL_B"))
    if phase == "accelerate":
        return state
    plan = state.ship.physical_transit.nominal_plan
    index = 1 if phase == "cruise" else 2
    GameLoop(engine, state).advance_interval(plan.segments[index].start.galactic_s + 100)
    assert state.ship.physical_transit.nominal_plan.phase_index == index
    return state


def automatic_sample(source, ticks, delay_s, delay_ticks):
    state = private_clone(source)
    loop = GameLoop(Engine(), state)
    lock = MeasuredLock(loop._lock)
    loop._lock = lock
    original = loop.advance_interval
    started, durations, pending_at_start = [], [], []
    done = threading.Event()

    def observed(dt):
        began = time.monotonic()
        started.append(began)
        pending_at_start.append(loop.auto_debt_s())
        if delay_s and len(started) <= delay_ticks:
            time.sleep(delay_s)  # controlled scheduler load, outside the state lock
        try:
            return original(dt)
        finally:
            durations.append(time.monotonic() - began)
            if len(durations) >= ticks:
                done.set()

    loop.advance_interval = observed
    galactic = state.clock.t
    proper = state.clock.ship_elapsed_s
    wall_start = time.monotonic()
    busy, polls, max_debt = 0, 0, 0.0
    loop.start()
    try:
        while not done.is_set() and time.monotonic() - wall_start < max(10, ticks * (delay_s + 2)):
            with loop.with_lock_if_available() as snapshot:
                polls += 1
                busy += snapshot is None
            max_debt = max(max_debt, loop.auto_debt_s())
            time.sleep(.02)
    finally:
        loop.stop()
    return {
        "wall_s": time.monotonic() - wall_start,
        "galactic_s": state.clock.t - galactic,
        "proper_s": state.clock.ship_elapsed_s - proper,
        "tick_starts_s": [start - wall_start for start in started],
        "tick_durations_s": durations,
        "pending_at_tick_start_s": pending_at_start,
        "max_pending_s": max_debt,
        "lock_held_s": lock.held_s,
        "lock_wait_s": lock.wait_s,
        "busy_lock_polls": busy,
        "lock_polls": polls,
        "auto_error": loop.last_auto_error,
    }


async def textual_sample(source):
    with TemporaryDirectory() as directory:
        os.environ["RETORNO_SCENARIO"] = "sandbox"
        app = RetornoTextualApp(force_new_game=True,
                                save_path=str(Path(directory) / "probe.sav"))
        app.loop.state = private_clone(source)
        app.loop.state.os.audio.enabled = False
        app.loop.state.os.audio.ambient_enabled = False
        app._play_startup_sequence = False
        app._startup_panel_blackout = False
        original_refresh = app.refresh_panels
        original_lock = app.loop.with_lock_if_available
        refreshes, headers, busy_reads = [], [], 0

        @contextmanager
        def observed_lock():
            nonlocal busy_reads
            with original_lock() as snapshot:
                if snapshot is None:
                    busy_reads += 1
                yield snapshot

        def observed_refresh():
            refreshes.append(time.monotonic())
            original_refresh()
            headers.append(str(app.query_one("#header", Static).render()))

        app.loop.with_lock_if_available = observed_lock
        app.refresh_panels = observed_refresh
        async with app.run_test() as pilot:
            began = time.monotonic()
            galactic = app.loop.state.clock.t
            proper = app.loop.state.clock.ship_elapsed_s
            await asyncio.sleep(2.7)
            field = app.query_one("#input", Input)
            previous_lines = len(app._log_buffer)
            field.value = "status"
            field.focus()
            input_start = time.monotonic()
            await pilot.press("enter")
            while len(app._log_buffer) == previous_lines and time.monotonic() - input_start < 2:
                await asyncio.sleep(.01)
            latency = time.monotonic() - input_start
            result = {
                "wall_s": time.monotonic() - began,
                "galactic_s": app.loop.state.clock.t - galactic,
                "proper_s": app.loop.state.clock.ship_elapsed_s - proper,
                "refresh_gaps_s": [b - a for a, b in zip(refreshes, refreshes[1:])],
                "header_changes": sum(a != b for a, b in zip(headers, headers[1:])),
                "busy_lock_reads": busy_reads,
                "status_response_s": latency,
                "status_visible": len(app._log_buffer) > previous_lines,
            }
            app.exit()
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rest", "accelerate", "cruise", "brake"),
                        default="cruise")
    parser.add_argument("--save", type=Path, help="read-only save path; overrides --phase")
    parser.add_argument("--ticks", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.0,
                        help="artificial wall seconds per tick outside the state lock")
    parser.add_argument("--delay-ticks", type=int,
                        help="number of initial ticks to delay (default: all)")
    parser.add_argument("--textual", action="store_true")
    args = parser.parse_args()
    if args.ticks < 1 or args.delay < 0 or (args.delay_ticks is not None and args.delay_ticks < 0):
        parser.error("ticks must be positive; delay and delay-ticks nonnegative")
    state = load_single_slot(args.save).state if args.save else synthetic_phase(args.phase)
    output = {"source": str(args.save) if args.save else args.phase,
              "automatic": automatic_sample(
                  state, args.ticks, args.delay,
                  args.ticks if args.delay_ticks is None else args.delay_ticks)}
    if args.textual:
        output["textual"] = asyncio.run(textual_sample(state))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
