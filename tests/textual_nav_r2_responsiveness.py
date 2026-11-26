"""Measure the normal Textual hibernation presentation on a real save copy.

Run with: PYTHONPATH=.:src:tests ../retorno_venv/bin/python tests/textual_nav_r2_responsiveness.py
The original save is read only; the application writes only to a temporary slot.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from textual.widgets import Input

from retorno.cli import repl
from retorno.io.save_load import load_single_slot
from retorno.ui_textual.app import RetornoTextualApp
import retorno.ui_textual.app as app_module


async def run() -> dict:
    original_scenario = os.environ.get("RETORNO_SCENARIO")
    os.environ["RETORNO_SCENARIO"] = "sandbox"
    original = Path(__file__).resolve().parents[2] / "PT001-05-proper-limit.dat"
    if not original.exists():
        raise FileNotFoundError(original)
    try:
        with TemporaryDirectory() as directory:
            app = RetornoTextualApp(force_new_game=True,
                                    save_path=str(Path(directory) / "textual-r2.sav"))
            app.loop.state = load_single_slot(original).state
            app._play_startup_sequence = False
            app._startup_panel_blackout = False
            marks: dict[str, float] = {}
            refreshes: list[float] = []
            gaps: list[float] = []
            original_refresh = app.refresh_panels
            original_execute = repl._execute_hibernate
            original_countdown = repl._hibernate_countdown_line
            original_wake = app_module.load_hibernate_wake_sequence_lines

            def refresh() -> None:
                refreshes.append(time.perf_counter())
                original_refresh()

            def execute(*args, **kwargs):
                marks["processing_start"] = time.perf_counter()
                try:
                    return original_execute(*args, **kwargs)
                finally:
                    marks["processing_end"] = time.perf_counter()

            def countdown(*args, **kwargs):
                marks.setdefault("countdown_start", time.perf_counter())
                return original_countdown(*args, **kwargs)

            def wake(*args, **kwargs):
                marks["wake_start"] = time.perf_counter()
                return original_wake(*args, **kwargs)

            app.refresh_panels = refresh
            repl._execute_hibernate = execute
            repl._hibernate_countdown_line = countdown
            app_module.load_hibernate_wake_sequence_lines = wake
            try:
                async with app.run_test() as pilot:
                    field = app.query_one("#input", Input)
                    field.value = "status"
                    input_start = time.perf_counter()
                    await pilot.press("enter")
                    await pilot.pause()
                    input_latency = time.perf_counter() - input_start
                    assert any("status" in line.lower() for line in app._log_buffer)

                    marks["sequence_start"] = time.perf_counter()
                    task = asyncio.create_task(app._run_hibernate_start_sequence(
                        60, wake_on_low_battery=False, until_arrival=True))
                    last = time.perf_counter()
                    while not task.done():
                        await asyncio.wait_for(asyncio.sleep(.05), 120)
                        now = time.perf_counter()
                        gaps.append(now - last)
                        last = now
                    await task
                    marks["sequence_end"] = time.perf_counter()
                    assert app.loop.state.ship.physical_transit is None
                    assert any("simulating" in line.lower() or "simulando" in line.lower()
                               for line in app._log_buffer)
                    assert not any("hibernate failed" in line for line in app._log_buffer)
                    wake_clock_t = app.loop.state.clock.t
                    await pilot.pause(1.5)
                    resumed_clock = app.loop.state.clock.t > wake_clock_t
                    assert resumed_clock
                    app._persist_game_on_exit()
                    app.exit()
            finally:
                repl._execute_hibernate = original_execute
                repl._hibernate_countdown_line = original_countdown
                app_module.load_hibernate_wake_sequence_lines = original_wake
            return {
                "save": original.name,
                "headless_textual": True,
                "default_hibernate_narrative_and_audio_flags": True,
                "input_latency_s": input_latency,
                "start_narrative_s": marks["countdown_start"] - marks["sequence_start"],
                "countdown_s": marks["processing_start"] - marks["countdown_start"],
                "processing_s": marks["processing_end"] - marks["processing_start"],
                "wake_blackout_s": marks["wake_start"] - marks["processing_end"],
                "wake_narrative_s": marks["sequence_end"] - marks["wake_start"],
                "event_loop_gap_max_s": max(gaps),
                "event_loop_gap_p95_s": sorted(gaps)[int(.95 * (len(gaps) - 1))],
                "panel_refresh_calls": len(refreshes),
                "progress_messages": sum("simulating:" in line.lower() or "simulando:" in line.lower()
                                         for line in app._log_buffer),
                "arrived": app.loop.state.ship.physical_transit is None,
                "auto_clock_resumed_after_wake": resumed_clock,
            }
    finally:
        if original_scenario is None:
            os.environ.pop("RETORNO_SCENARIO", None)
        else:
            os.environ["RETORNO_SCENARIO"] = original_scenario


if __name__ == "__main__":
    # Textual's run_test leaves an idle default-executor thread on this Python
    # version. A direct executor join avoids an intermittent hang in
    # asyncio.run's asynchronous shutdown helper after all tasks are done.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run())
        loop.run_until_complete(loop.shutdown_asyncgens())
        if loop._default_executor is not None:
            loop._default_executor.shutdown(wait=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        loop.close()
