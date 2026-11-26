"""Safe startup at a physical survival boundary, using synthetic and private saves."""
from __future__ import annotations

from pathlib import Path
import asyncio
import os
import pickle
import shutil
import sys

import pytest

from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.core.actions import PowerShed, SystemOn
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from retorno.ui_textual.app import RetornoTextualApp
from textual.widgets import Input
from tests.test_nav_public_causal import departed


EVIDENCE = Path(os.environ.get(
    "RETORNO_PT001_06_EVIDENCE",
    Path(__file__).resolve().parents[2] / "PT001-06-core-os-offline.dat",
))


@pytest.fixture
def synthetic_save(tmp_path):
    state, _ = departed()
    core_os = state.ship.systems["core_os"]
    core_os.state = SystemState.OFFLINE
    core_os.forced_offline = True
    path = tmp_path / "pt001-06-synthetic.dat"
    save_single_slot(state, path)
    return path


@pytest.fixture
def real_save(tmp_path):
    if not EVIDENCE.exists():
        pytest.skip("PT001-06 real save evidence unavailable")
    path = tmp_path / "pt001-06.dat"
    shutil.copy2(EVIDENCE, path)
    return path


@pytest.fixture(params=["synthetic_save", "real_save"], ids=["synthetic", "real"])
def private_save(request):
    return request.getfixturevalue(request.param)


def test_save_rejected_tick_is_atomic_and_initial_step_pauses(private_save):
    state = load_single_slot(private_save).state
    assert state.ship.physical_transit is not None
    assert state.ship.systems["core_os"].state == SystemState.OFFLINE
    before = pickle.dumps(state)
    loop = GameLoop(Engine(), state)
    with pytest.raises(NavigationAdvanceBlocked, match="critical survival transitions"):
        loop.step(1.0)
    assert pickle.dumps(state) == before
    assert not loop.step_initial()
    assert state.clock.t == load_single_slot(private_save).state.clock.t
    assert loop.last_auto_error == "Physical segment with critical survival transitions needs causal cuts"
    assert not loop._auto_tick_enabled
    warning = loop.drain_events()[-1][1]
    assert warning.type == EventType.BOOT_BLOCKED
    assert warning.data["reason"] == "physical_advance_blocked"
    assert repl._command_blocked_message(state, parse_command("power on core_os"))
    assert repl._command_blocked_message(state, parse_command("status")) is None


def test_textual_loads_private_save_and_reports_paused_time(private_save, monkeypatch):
    monkeypatch.delenv("RETORNO_SCENARIO", raising=False)
    app = RetornoTextualApp(save_path=str(private_save))
    app._audio_manager = None
    original_t = app.loop.state.clock.t
    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.loop.state.clock.t == original_t
            assert not app.loop._auto_tick_enabled
            assert any("time advance" in line.lower() or "avance" in line.lower()
                       for line in app._log_buffer)
            input_widget = app.query_one("#input", Input)
            input_widget.value = "power on core_os"
            await pilot.press("enter")
            await pilot.pause()
            assert app.loop.state.ship.systems["core_os"].state == SystemState.OFFLINE
            assert any("Terminal control lost" in line or "Control de terminal perdido" in line
                       for line in app._log_buffer)
    asyncio.run(run())


def test_cli_loads_private_save_and_reports_paused_time(private_save, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["retorno", "--save-path", str(private_save)])
    monkeypatch.setattr(repl, "run_console_entry_gate", lambda *a, **k: None)
    monkeypatch.setattr(repl, "save_single_slot", lambda *a, **k: None)
    def no_audio(*_args, **_kwargs):
        raise repl.AudioConfigError("disabled in test")
    monkeypatch.setattr(repl, "AudioManager", no_audio)
    commands = iter(["power on core_os", "status", "exit"])
    monkeypatch.setattr("builtins.input", lambda *_: next(commands))
    original = private_save.read_bytes()
    repl.main()
    assert private_save.read_bytes() == original
    output = capsys.readouterr().out
    assert "Automatic physical advance stopped" in output
    assert "critical" in output.lower() or "crític" in output.lower()
    assert "Terminal control lost" in output or "Control de terminal perdido" in output


@pytest.mark.parametrize("system_id", ["core_os", "life_support"])
def test_public_shutdown_of_survival_system_is_rejected_during_motion(system_id):
    state, loop = departed()
    action = parse_command(f"power off {system_id}")
    assert isinstance(action, PowerShed)
    before = pickle.dumps(state.ship)
    events = loop.apply_action(action)
    assert events[0].type == EventType.BOOT_BLOCKED
    assert events[0].data["reason"] == "physical_critical_shutdown_blocked"
    assert pickle.dumps(state.ship) == before
    assert loop.step_initial()


def test_power_commands_preserve_existing_recovery_and_terminal_rules():
    state, loop = departed()
    assert isinstance(parse_command("power on engines"), SystemOn)
    loop.apply_action(parse_command("power off engines"))
    assert state.ship.systems["engines"].state == SystemState.OFFLINE
    loop.apply_action(parse_command("power on engines"))
    assert state.ship.systems["engines"].state != SystemState.OFFLINE
    assert loop.step_initial()


def test_normal_startup_still_advances():
    state, loop = departed()
    t = state.clock.t
    assert loop.step_initial()
    assert state.clock.t == t + 1.0
    assert loop.last_auto_error is None
