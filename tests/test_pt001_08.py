"""PT001-08: hibernation presentation without changing simulation work."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from threading import Event as ThreadEvent
import sys

import pytest
from textual.widgets import Input, Static

from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import Event, EventType, Severity, SourceRef
from retorno.model.os import Locale
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from retorno.ui_textual.app import RetornoTextualApp
import retorno.ui_textual.app as app_module


def _result() -> repl.HibernateRunResult:
    recorded = Event(
        event_id="pt001-08-event", t=100, type=EventType.HIBERNATION_STARTED,
        severity=Severity.INFO, source=SourceRef("ship", "ship"),
        message="recorded hibernation event", data={"years": 1.0},
    )
    return repl.HibernateRunResult(
        actual_years=1.0, start_soc=.8, end_soc=.7,
        start_health={"core_os": 1.0}, end_health={"core_os": .9},
        events_to_render=[("cmd", recorded)], recovery_events=[],
        woke_early=False, wake_reason=None,
    )


def _fast_sequences(monkeypatch):
    for name in (
        "HIBERNATE_SEQUENCE_TYPEWRITER", "HIBERNATE_WAKE_SEQUENCE_TYPEWRITER",
    ):
        monkeypatch.setattr(Balance, name, False)
    for name in (
        "HIBERNATE_SEQUENCE_LINE_DELAY_S", "HIBERNATE_WAKE_SEQUENCE_LINE_DELAY_S",
        "HIBERNATE_WAKE_PANEL_BLACKOUT_S", "HIBERNATE_SEQUENCE_COUNTDOWN_S",
    ):
        monkeypatch.setattr(Balance, name, 0)
    monkeypatch.setattr(app_module, "load_hibernate_start_sequence_lines",
                        lambda _locale: ["CRYOSTASIS ENTRY"])
    monkeypatch.setattr(app_module, "load_hibernate_wake_sequence_lines",
                        lambda _locale, *, emergency: ["CRYOSTASIS WAKE"])


def _run_textual(coro):
    # R2's Textual smoke joins the default executor directly: this Python
    # version can otherwise stall during asyncio.run's executor shutdown.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        if loop._default_executor is not None:
            loop._default_executor.shutdown(wait=True)
        loop.close()
        asyncio.set_event_loop(None)


@pytest.mark.parametrize("debug", [False, True])
def test_textual_blackout_or_debug_progress_then_wake(monkeypatch, tmp_path: Path, debug: bool):
    monkeypatch.setenv("RETORNO_SCENARIO", "sandbox")
    _fast_sequences(monkeypatch)
    started = ThreadEvent()
    release = ThreadEvent()
    callbacks = []

    def execute(loop, years, *, on_progress, **_kwargs):
        callbacks.append(on_progress)
        with loop.with_lock() as state:
            state.clock.t += Balance.YEAR_S
        if on_progress is not None:
            on_progress(Balance.YEAR_S / 2, Balance.YEAR_S)
        started.set()
        if not release.wait(5):
            raise RuntimeError("test worker timeout")
        return _result()

    monkeypatch.setattr(repl, "_execute_hibernate", execute)
    app = RetornoTextualApp(force_new_game=True, save_path=str(tmp_path / "pt001-08.sav"))
    app._audio_manager = None
    app._play_startup_sequence = False
    app._startup_panel_blackout = False
    app.loop.state.os.debug_enabled = debug

    async def run():
        async with app.run_test() as pilot:
            app.loop.set_auto_tick(False)
            task = asyncio.create_task(app._run_hibernate_start_sequence(1, False))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(.01)
                assert started.is_set()
                await asyncio.wait_for(pilot.pause(.3), 2)
                assert not task.done()  # the UI loop kept running during worker work
                field = app.query_one("#input", Input)
                assert field.disabled
                if debug:
                    assert callbacks[0] is not None
                    assert not app._hibernate_panel_blackout
                    assert field.display
                    assert any("Simulating journey" in line for line in app._log_buffer)
                    assert any("Simulating:" in line for line in app._log_buffer)
                else:
                    assert callbacks[0] is None
                    assert app._hibernate_panel_blackout
                    assert not field.display
                    assert app.query_one("#header", Static).content == ""
                    assert not app._log_buffer
                release.set()
                await asyncio.wait_for(task, 3)
                assert field.display and not field.disabled
                assert not app._hibernate_panel_blackout
                assert "CRYOSTASIS WAKE" in app._log_buffer
                assert any("hibernation_started" in line for line in app._log_buffer)
                assert any("Hibernate digest" in line for line in app._log_buffer)
                if not debug:
                    assert not any("Simulating" in line for line in app._log_buffer)
            finally:
                release.set()
                if not task.done():
                    await task

    _run_textual(run())


@pytest.mark.parametrize("locale,expected", [
    (Locale.EN, "Technical hibernation failure"),
    (Locale.ES, "Fallo técnico de hibernación"),
])
def test_textual_error_breaks_blackout_without_false_wake(monkeypatch, tmp_path: Path,
                                                         locale: Locale, expected: str):
    monkeypatch.setenv("RETORNO_SCENARIO", "sandbox")
    _fast_sequences(monkeypatch)

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic engine fault")

    monkeypatch.setattr(repl, "_execute_hibernate", fail)
    app = RetornoTextualApp(force_new_game=True, save_path=str(tmp_path / "error.sav"))
    app._audio_manager = None
    app._play_startup_sequence = False
    app._startup_panel_blackout = False
    app.loop.state.os.locale = locale

    async def run():
        async with app.run_test():
            app.loop.set_auto_tick(False)
            await app._run_hibernate_start_sequence(1, False)
            field = app.query_one("#input", Input)
            assert field.display and not field.disabled
            assert not app._hibernate_panel_blackout
            assert any(f"[ERROR] {expected}: synthetic engine fault" in line
                       for line in app._log_buffer)
            assert not app.loop._auto_tick_enabled
            assert any("0.0 days" in line or "0.0 días" in line
                       for line in app._log_buffer)
            assert "CRYOSTASIS WAKE" not in app._log_buffer
            assert not any("Hibernate digest" in line for line in app._log_buffer)

    _run_textual(run())


@pytest.mark.parametrize("reason,expected_wake", [
    ("causal_boundary:synthetic physical cut", False),
    ("emergency:synthetic propulsion loss", True),
])
def test_textual_returned_outcome_distinguishes_fault_from_emergency(
        monkeypatch, tmp_path: Path, reason: str, expected_wake: bool):
    monkeypatch.setenv("RETORNO_SCENARIO", "sandbox")
    _fast_sequences(monkeypatch)
    wake_requests = []
    monkeypatch.setattr(app_module, "load_hibernate_wake_sequence_lines",
                        lambda _locale, *, emergency: wake_requests.append(emergency) or ["CRYOSTASIS WAKE"])

    def execute(loop, *_args, **_kwargs):
        with loop.with_lock() as state:
            state.clock.t += Balance.YEAR_S / 4
        loop.set_auto_tick(True)
        return replace(_result(), actual_years=.25, woke_early=True, wake_reason=reason)

    monkeypatch.setattr(repl, "_execute_hibernate", execute)
    app = RetornoTextualApp(force_new_game=True, save_path=str(tmp_path / "outcome.sav"))
    app._audio_manager = None
    app._play_startup_sequence = False
    app._startup_panel_blackout = False

    async def run():
        async with app.run_test():
            app.loop.set_auto_tick(False)
            await app._run_hibernate_start_sequence(1, False)
            field = app.query_one("#input", Input)
            assert field.display and not field.disabled
            assert not app._hibernate_panel_blackout
            assert any("Advanced time by 0.25 years" in line for line in app._log_buffer)
            assert ("CRYOSTASIS WAKE" in app._log_buffer) == expected_wake
            assert wake_requests == ([True] if expected_wake else [])
            if expected_wake:
                assert app.loop._auto_tick_enabled
                assert any("propulsion emergency" in line for line in app._log_buffer)
            else:
                assert not app.loop._auto_tick_enabled
                assert any("[ERROR] Hibernation stopped at unresolved physical boundary"
                           in line for line in app._log_buffer)

    _run_textual(run())


@pytest.mark.parametrize("mode,locale", [
    ("exception", Locale.EN), ("exception", Locale.ES),
    ("causal", Locale.EN), ("emergency", Locale.EN),
])
def test_cli_fault_stays_in_repl_and_emergency_still_wakes(
        monkeypatch, tmp_path: Path, capsys, mode: str, locale: Locale):
    monkeypatch.setenv("RETORNO_SCENARIO", "sandbox")
    monkeypatch.setattr(sys, "argv", ["retorno", "--save-path", str(tmp_path / "cli.sav")])
    original_create = repl.create_initial_state_sandbox

    def create():
        state = original_create()
        state.os.locale = locale
        return state

    executed_loops = []

    def execute(loop, *_args, **_kwargs):
        executed_loops.append(loop)
        with loop.with_lock() as state:
            state.clock.t += Balance.YEAR_S / 4
        loop.set_auto_tick(True)
        if mode == "exception":
            raise RuntimeError("synthetic engine fault")
        reason = ("causal_boundary:synthetic physical cut" if mode == "causal"
                  else "emergency:synthetic propulsion loss")
        return replace(_result(), actual_years=.25, woke_early=True, wake_reason=reason)

    saved = []

    def save(state, *_args, **_kwargs):
        saved.append(state.clock.t)
        return tmp_path / "cli.sav"

    monkeypatch.setattr(repl, "create_initial_state_sandbox", create)
    def no_audio(*_args, **_kwargs):
        raise repl.AudioConfigError("disabled in test")

    monkeypatch.setattr(repl, "AudioManager", no_audio)
    monkeypatch.setattr(repl, "run_console_entry_gate", lambda *_a, **_k: None)
    monkeypatch.setattr(repl, "_maybe_run_startup_sequence", lambda *_a: None)
    monkeypatch.setattr(repl, "_play_hibernate_start_sequence", lambda *_a: None)
    wake_calls = []
    monkeypatch.setattr(repl, "_play_hibernate_wake_sequence",
                        lambda *_a: wake_calls.append(True) or print("CRYOSTASIS WAKE"))
    monkeypatch.setattr(repl, "_execute_hibernate", execute)
    monkeypatch.setattr(repl, "save_single_slot", save)
    monkeypatch.setattr(repl.GameLoop, "start", lambda _loop: None)
    commands = iter(["hibernate 1", "y", "exit"])
    monkeypatch.setattr("builtins.input", lambda *_a: next(commands))
    stdout = sys.stdout
    try:
        repl.main()
    finally:
        sys.stdout = stdout
    output = capsys.readouterr().out
    assert len(saved) == 1
    assert saved[0] == pytest.approx(Balance.YEAR_S / 4)
    if mode != "emergency":
        assert not executed_loops[0]._auto_tick_enabled
    assert ("CRYOSTASIS WAKE" in output) == (mode == "emergency")
    assert len(wake_calls) == int(mode == "emergency")
    if mode == "exception":
        assert "synthetic engine fault" in output
        assert ("Time actually advanced: 0.25 years" if locale == Locale.EN
                else "Tiempo avanzado realmente: 0.25 años") in output
    elif mode == "causal":
        assert "[ERROR] Hibernation stopped at unresolved physical boundary" in output
        assert "Advanced time by 0.25 years" in output
    else:
        assert "[WARN] Hibernation interrupted by a propulsion emergency" in output


def test_shared_debug_progress_is_localized():
    assert repl._hibernate_progress_line("en", Balance.YEAR_S / 2, Balance.YEAR_S) == (
        "[DEBUG] Simulating: 0.50/1.00 y")
    assert repl._hibernate_progress_line("es", Balance.YEAR_S / 2, Balance.YEAR_S) == (
        "[DEBUG] Simulando: 0.50/1.00 años")


@pytest.mark.parametrize("locale,stopped,woke", [
    (Locale.EN, "Hibernation stopped after", "Woke up after"),
    (Locale.ES, "Hibernación detenida tras", "Despertaste tras"),
])
def test_recorded_technical_end_never_renders_as_wake(
        monkeypatch, tmp_path: Path, capsys, locale: Locale, stopped: str, woke: str):
    state = repl.create_initial_state_sandbox()
    state.os.locale = locale
    loop = GameLoop(Engine(), state)

    def blocked(*_args, **_kwargs):
        raise NavigationAdvanceBlocked("synthetic physical cut", 0, [])

    monkeypatch.setattr(loop, "advance_interval", blocked)
    result = repl._execute_hibernate(loop, 1)
    recorded = [event for event in state.events.recent
                if event.type == EventType.HIBERNATION_ENDED]
    assert len(recorded) == 1
    event = recorded[0]
    assert any(rendered is event for _, rendered in result.events_to_render)
    assert event.data["end_reason"] == "causal_boundary"

    repl._render_hibernate_result(loop, result)
    immediate = capsys.readouterr().out
    assert stopped in immediate
    assert woke not in immediate

    saved = save_single_slot(state, tmp_path / "technical-end.sav")
    restored = load_single_slot(saved).state
    repl.render_logs(restored)
    consulted = capsys.readouterr().out
    assert stopped in consulted
    assert woke not in consulted

    ordinary = replace(event, data={"years": event.data["years"]})
    repl.render_events(state, [("cmd", ordinary)])
    assert woke in capsys.readouterr().out


@pytest.mark.parametrize("debug", [False, True])
def test_cli_progress_uses_existing_debug_mode(monkeypatch, tmp_path: Path,
                                               capsys, debug: bool):
    monkeypatch.setenv("RETORNO_SCENARIO", "sandbox")
    monkeypatch.setattr(sys, "argv", ["retorno", "--save-path", str(tmp_path / "cli.sav")])
    original_create = repl.create_initial_state_sandbox

    def create():
        state = original_create()
        state.os.debug_enabled = debug
        return state

    def no_audio(*_args, **_kwargs):
        raise repl.AudioConfigError("disabled in test")

    def execute(_loop, _years, *, on_progress, **_kwargs):
        if on_progress is not None:
            on_progress(Balance.YEAR_S / 2, Balance.YEAR_S)
            on_progress(Balance.YEAR_S, Balance.YEAR_S)
        return _result()

    monkeypatch.setattr(repl, "create_initial_state_sandbox", create)
    monkeypatch.setattr(repl, "AudioManager", no_audio)
    monkeypatch.setattr(repl, "run_console_entry_gate", lambda *_a, **_k: None)
    monkeypatch.setattr(repl, "_maybe_run_startup_sequence", lambda *_a: None)
    monkeypatch.setattr(repl, "_play_hibernate_start_sequence", lambda *_a: None)
    monkeypatch.setattr(repl, "_play_hibernate_wake_sequence", lambda *_a: print("CRYOSTASIS WAKE"))
    monkeypatch.setattr(repl, "_render_hibernate_result", lambda *_a: print("HIBERNATION DIGEST"))
    monkeypatch.setattr(repl, "_execute_hibernate", execute)
    monkeypatch.setattr(repl, "save_single_slot", lambda *_a, **_k: tmp_path / "cli.sav")
    monkeypatch.setattr(repl.GameLoop, "start", lambda _loop: None)
    commands = iter(["hibernate 1", "y", "exit"])
    monkeypatch.setattr("builtins.input", lambda *_a: next(commands))
    stdout = sys.stdout
    try:
        repl.main()
    finally:
        sys.stdout = stdout
    output = capsys.readouterr().out
    assert "CRYOSTASIS WAKE" in output
    assert "HIBERNATION DIGEST" in output
    if debug:
        assert "[DEBUG] Simulating: 0.50/1.00 y" in output
    else:
        assert "Simulating:" not in output
