from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time

from textual.app import App, ComposeResult
from textual import events
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Input, RichLog

from retorno.audio.config import AudioConfigError, load_audio_config
from retorno.audio.manager import AudioManager
from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli.parser import ParseError, parse_command, format_parse_error
from retorno.cli import repl
from retorno.core.engine import Engine
from retorno.core.actions import Hibernate
from retorno.config.balance import Balance
from retorno.model.events import EventType, Severity
from retorno.model.drones import DroneStatus
from retorno.model.jobs import active_job_display_ids
from retorno.model.os import Locale, list_dir, normalize_path
from retorno.runtime.data_loader import load_modules
from retorno.runtime.loop import GameLoop
from retorno.runtime.operator_config import (
    apply_config_value,
    audio_flags,
    config_keys,
    config_show_lines,
    config_value_choices,
    resolve_help_verbose,
)
from retorno.runtime.startup import (
    load_hibernate_start_sequence_lines,
    load_hibernate_wake_sequence_lines,
    load_startup_sequence_lines,
)
from retorno.ui_theme import get_theme_palette, normalize_theme_preset, render_rich_block, render_rich_line
from retorno.ui_textual import presenter
from retorno.io.save_load import (
    LoadGameResult,
    SaveLoadError,
    load_single_slot,
    normalize_user_id,
    resolve_save_path,
    save_exists,
    save_single_slot,
)


class CommandInput(Input):
    def key_tab(self) -> None:
        # Reserve TAB for completion.
        self.app.action_complete()
        return

    def key_up(self) -> None:
        self.app.action_history_prev()
        return

    def key_down(self) -> None:
        self.app.action_history_next()
        return


class RetornoTextualApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: $background;
        overflow: hidden;
        scrollbar-size-vertical: 0;
        scrollbar-size-horizontal: 0;
        scrollbar-background: transparent;
        scrollbar-background-hover: transparent;
        scrollbar-background-active: transparent;
        scrollbar-corner-color: transparent;
    }
    #header {
        height: 1;
        padding: 0 2;
        background: #002F69;
        color: #f2f2f2;
    }
    #main {
        height: 1fr;
    }
    #status {
        width: 1.1fr;
        padding: 1 2;
        border: none;
        background: $background;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
        scrollbar-color: #666666;
        scrollbar-color-hover: #777777;
        scrollbar-color-active: #888888;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
        scrollbar-corner-color: $background;
    }
    #right {
        width: 1.9fr;
    }
    #sep_header_right {
        height: 1;
        background: $background;
    }
    #alerts {
        height: 1fr;
        padding: 0 2;
        border: none;
        background: $background;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 0;
        scrollbar-color: #666666;
        scrollbar-color-hover: #777777;
        scrollbar-color-active: #888888;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
        scrollbar-corner-color: $background;
    }
    #jobs {
        height: 1fr;
        padding: 0 2;
        border: none;
        background: $background;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 0;
        scrollbar-color: #666666;
        scrollbar-color-hover: #777777;
        scrollbar-color-active: #888888;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
        scrollbar-corner-color: $background;
    }
    #log {
        height: 16;
        border: none;
        margin: 1 0;
        padding: 0 2;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
        background: $background;
        scrollbar-color: #666666;
        scrollbar-color-hover: #777777;
        scrollbar-color-active: #888888;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
        scrollbar-corner-color: $background;
    }
    #input {
        height: 1;
        background: $background;
        border: none;
    }
    #power {
        height: 1;
        padding: 0 2;
        background: #002F69;
        color: #f2f2f2;
    }
    """

    BINDINGS = [
        #Binding("ctrl+c", "quit", "Quit"),
        # Binding("q", "quit", "Quit"),
        # Binding("f1", "help", "Help"),
        Binding("ctrl+l", "clear_log", "Clear log"),
        Binding("tab", "complete", "Complete", priority=True),
        Binding("alt+1", "toggle_status", "Toggle status", priority=True),
        Binding("alt+2", "toggle_alerts", "Toggle alerts", priority=True),
        Binding("alt+3", "toggle_jobs", "Toggle jobs", priority=True),
        Binding("alt+0", "toggle_panels", "Toggle panels", priority=True),
        Binding("f2", "toggle_status", "Toggle status", priority=True),
        Binding("f3", "toggle_alerts", "Toggle alerts", priority=True),
        Binding("f4", "toggle_jobs", "Toggle jobs", priority=True),
        Binding("f5", "toggle_panels", "Toggle panels", priority=True),
        Binding("alt+j", "focus_next", "Next panel", priority=True),
        Binding("alt+k", "focus_previous", "Prev panel", priority=True),
        Binding("k", "scroll_up", "Scroll up", priority=True),
        Binding("j", "scroll_down", "Scroll down", priority=True),
        Binding("escape", "startup_skip", "", priority=True, show=False),
        #Binding("ctrl+n", "focus_next", "Next panel"),
        # Binding("pageup", "scroll_up", "Scroll up"),
        # Binding("pagedown", "scroll_down", "Scroll down"),
        # Binding("[", "scroll_up", "Scroll up"),
        # Binding("]", "scroll_down", "Scroll down"),
        # Binding("alt+[", "scroll_up", "Scroll up"),
        # Binding("alt+]", "scroll_down", "Scroll down"),
    ]

    def __init__(self, force_new_game: bool = False, save_path: str | None = None, user: str | None = None) -> None:
        self._save_path = save_path
        self._user = user
        self._exit_persist_done = False
        self._play_startup_sequence = False
        self._startup_notice = ""
        self._startup_audio_context = "load_game"
        scenario = os.getenv("RETORNO_SCENARIO", "prologue").lower()
        if scenario in {"sandbox", "dev"}:
            state = create_initial_state_sandbox()
            self._play_startup_sequence = True
            self._startup_audio_context = "new_game"
            self._startup_notice = f"[INFO] Scenario '{scenario}' started as new game (save slot bypassed)."
        elif force_new_game:
            state = create_initial_state_prologue()
            self._play_startup_sequence = True
            self._startup_audio_context = "new_game"
            self._startup_notice = "[INFO] Started new game (save slot ignored by --new-game/RETORNO_NEW_GAME)."
        else:
            try:
                loaded: LoadGameResult | None = load_single_slot(save_path, user=self._user)
            except SaveLoadError as exc:
                state = create_initial_state_prologue()
                self._play_startup_sequence = True
                self._startup_audio_context = "new_game"
                self._startup_notice = f"[WARN] Could not load saved game ({exc}). Starting new game."
            else:
                if loaded is None:
                    state = create_initial_state_prologue()
                    self._play_startup_sequence = True
                    self._startup_audio_context = "new_game"
                    self._startup_notice = "[INFO] No saved game found. Starting new game."
                else:
                    state = loaded.state
                    self._startup_audio_context = "load_game"
                    if loaded.source == "backup":
                        self._startup_notice = f"[WARN] Main save unreadable. Loaded backup: {loaded.path}"
                    else:
                        self._startup_notice = f"[INFO] Loaded saved game: {loaded.path}"
        engine = Engine()
        self.loop = GameLoop(engine, state, tick_s=1.0)
        self._theme_preset = normalize_theme_preset(getattr(state.os, "theme_preset", "linux"))
        self._history: list[str] = []
        self._history_index: int = 0
        self._history_current: str = ""
        self._pending_confirm_action = None
        self._pending_confirm_prompt = ""
        self._pending_confirm_locale = "en"
        self._pending_years: float = 0.0
        self._pending_hibernate_parsed = None
        self._pending_wake_on_low_battery: bool = False
        self._pending_hibernate_requires_non_cruise: bool = False
        self._last_complete_key: str = ""
        self._last_complete_at: float = 0.0
        self._last_complete_candidates: list[str] = []
        self._log_buffer: list[str] = []
        self._startup_sequence_running = False
        self._startup_sequence_skip = False
        self._hibernate_sequence_running = False
        self._hibernate_panel_blackout = False
        self._audio_notice = ""
        try:
            self._audio_manager = AudioManager(load_audio_config())
        except AudioConfigError as exc:
            self._audio_manager = None
            self._audio_notice = f"[WARN] Audio disabled: {exc}"
        else:
            self._audio_notice = self._audio_manager.notice or ""
            audio_enabled, ambient_enabled = audio_flags(self.loop.state.os)
            self._audio_manager.prepare_session(
                audio_enabled,
                ambient_enabled,
                self._startup_audio_context,
            )
        self._panel_visible = {
            "status": True,
            "alerts": True,
            "jobs": True,
        }
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static(id="header", markup=False)
        with Horizontal(id="main"):
            yield RichLog(id="status", wrap=True, highlight=False, min_width=0)
            with Vertical(id="right"):
                yield Static(id="sep_header_right")
                yield RichLog(id="alerts", wrap=True, highlight=False, min_width=0)
                yield RichLog(id="jobs", wrap=True, highlight=False, min_width=0)
        yield RichLog(id="log", wrap=True, highlight=False)
        yield CommandInput(id="input", placeholder="Enter command…")
        yield Static(id="power")

    def on_mount(self) -> None:
        self._apply_theme(self._theme_preset)
        if self._audio_manager is not None:
            audio_enabled, ambient_enabled = audio_flags(self.loop.state.os)
            self._audio_manager.start(audio_enabled, ambient_enabled)
            self._audio_manager.play_startup(audio_enabled, self._startup_audio_context)
            notice = self._audio_manager.consume_notice()
            if notice:
                self._log_line(notice)
        self.loop.step(1.0)
        if self._startup_notice:
            self._log_line(self._startup_notice)
        if self._audio_notice:
            self._log_line(self._audio_notice)
        if not self.loop.state.os.debug_enabled:
            self.loop.set_auto_tick(True)
            self.loop.start()
        else:
            self.loop.set_auto_tick(False)
        # Prevent auto-scroll in alerts/jobs so manual scroll doesn't jump on refresh.
        self.query_one("#alerts", RichLog).auto_scroll = False
        self.query_one("#jobs", RichLog).auto_scroll = False
        # Status should never auto-scroll; user controls position.
        self.query_one("#status", RichLog).auto_scroll = False
        self.set_interval(0.25, self.refresh_panels)
        self.refresh_panels()
        self._apply_panel_layout()
        # Ensure input is focused on start.
        self.call_later(lambda: self.query_one("#input", Input).focus())
        self.call_after_refresh(self._start_startup_sequence)

    def _start_startup_sequence(self) -> None:
        if not self._play_startup_sequence:
            return
        if not Balance.STARTUP_SEQUENCE_ENABLED:
            return
        if self._startup_sequence_running:
            return
        asyncio.create_task(self._run_startup_sequence())

    async def _run_startup_sequence(self) -> None:
        self._startup_sequence_running = True
        self._startup_sequence_skip = False
        locale = self.loop.state.os.locale.value
        lines = load_startup_sequence_lines(locale)
        if not lines:
            self._startup_sequence_running = False
            return
        typewriter = Balance.STARTUP_SEQUENCE_TYPEWRITER
        cps = max(1, int(Balance.STARTUP_SEQUENCE_TYPEWRITER_CPS))
        line_delay_s = max(0.0, float(Balance.STARTUP_SEQUENCE_LINE_DELAY_S))
        base_lines = list(self._log_buffer)
        rendered_lines: list[str] = []
        log = self.query_one("#log", RichLog)
        skip_index: int | None = None

        async def _sleep_with_skip(seconds: float) -> bool:
            end = time.time() + seconds
            while time.time() < end:
                if self._startup_sequence_skip and Balance.STARTUP_SEQUENCE_SKIPPABLE:
                    return True
                await asyncio.sleep(0.05)
            return False

        def _render_snapshot(current_line: str | None) -> None:
            log.clear()
            for line in base_lines:
                self._write_rich_line(log, line)
            for line in rendered_lines:
                self._write_rich_line(log, line)
            if current_line is not None:
                self._write_rich_line(log, current_line)

        for idx, line in enumerate(lines):
            if self._startup_sequence_skip and Balance.STARTUP_SEQUENCE_SKIPPABLE:
                skip_index = idx
                break
            if typewriter:
                current = ""
                for ch in line:
                    if self._startup_sequence_skip and Balance.STARTUP_SEQUENCE_SKIPPABLE:
                        skip_index = idx
                        break
                    current += ch
                    _render_snapshot(current)
                    await asyncio.sleep(1.0 / cps)
                if self._startup_sequence_skip and Balance.STARTUP_SEQUENCE_SKIPPABLE:
                    if skip_index is None:
                        skip_index = idx
                    break
                rendered_lines.append(line)
                _render_snapshot(None)
            else:
                rendered_lines.append(line)
                _render_snapshot(None)
            self._log_buffer.append(line)
            if len(self._log_buffer) > 2000:
                self._log_buffer = self._log_buffer[-2000:]
            if line_delay_s > 0.0 and await _sleep_with_skip(line_delay_s):
                skip_index = idx + 1
                break

        if skip_index is not None and Balance.STARTUP_SEQUENCE_SKIPPABLE:
            remaining = lines[skip_index:]
            if remaining:
                rendered_lines.extend(remaining)
                for line in remaining:
                    self._log_buffer.append(line)
                if len(self._log_buffer) > 2000:
                    self._log_buffer = self._log_buffer[-2000:]
                _render_snapshot(None)

        self._startup_sequence_running = False
        self._log_lines(self._startup_tips(locale))
        self._drain_auto_to_log()
        self.refresh_panels()
        self.call_later(lambda: self.query_one("#input", Input).focus())

    def _clear_log_widget(self, *, clear_buffer: bool = False) -> None:
        self.query_one("#log", RichLog).clear()
        if clear_buffer:
            self._log_buffer.clear()

    def _render_panel_blackout(self) -> None:
        self.query_one("#header", Static).update("")
        self.query_one("#power", Static).update("")
        for widget_id in ("status", "alerts", "jobs", "log"):
            self.query_one(f"#{widget_id}", RichLog).clear()

    async def _run_hibernate_start_sequence(self, years: float, wake_on_low_battery: bool) -> None:
        if self._hibernate_sequence_running:
            return
        self._hibernate_sequence_running = True
        input_widget = self.query_one("#input", Input)
        input_widget.disabled = True
        try:
            with self.loop.with_lock() as state:
                locale = state.os.locale.value
            start_lines = load_hibernate_start_sequence_lines(locale)
            start_typewriter = Balance.HIBERNATE_SEQUENCE_TYPEWRITER
            start_cps = max(1, int(Balance.HIBERNATE_SEQUENCE_TYPEWRITER_CPS))
            start_line_delay_s = max(0.0, float(Balance.HIBERNATE_SEQUENCE_LINE_DELAY_S))
            countdown_s = max(0, int(Balance.HIBERNATE_SEQUENCE_COUNTDOWN_S))
            wake_blackout_s = max(0.0, float(Balance.HIBERNATE_WAKE_PANEL_BLACKOUT_S))
            wake_typewriter = Balance.HIBERNATE_WAKE_SEQUENCE_TYPEWRITER
            wake_cps = max(1, int(Balance.HIBERNATE_WAKE_SEQUENCE_TYPEWRITER_CPS))
            wake_line_delay_s = max(0.0, float(Balance.HIBERNATE_WAKE_SEQUENCE_LINE_DELAY_S))
            log = self.query_one("#log", RichLog)

            async def _play_log_sequence(
                lines: list[str],
                *,
                typewriter: bool,
                cps: int,
                line_delay_s: float,
                persist_to_buffer: bool,
            ) -> None:
                base_lines = list(self._log_buffer)
                rendered_lines: list[str] = []

                def _render_snapshot(current_line: str | None) -> None:
                    log.clear()
                    for line in base_lines:
                        self._write_rich_line(log, line)
                    for line in rendered_lines:
                        self._write_rich_line(log, line)
                    if current_line is not None:
                        self._write_rich_line(log, current_line)

                for line in lines:
                    if typewriter:
                        current = ""
                        for ch in line:
                            current += ch
                            _render_snapshot(current)
                            await asyncio.sleep(1.0 / cps)
                        rendered_lines.append(line)
                        _render_snapshot(None)
                    else:
                        rendered_lines.append(line)
                        _render_snapshot(None)
                    if persist_to_buffer:
                        self._log_buffer.append(line)
                        if len(self._log_buffer) > 2000:
                            self._log_buffer = self._log_buffer[-2000:]
                    if line_delay_s > 0.0:
                        await asyncio.sleep(line_delay_s)

            await _play_log_sequence(
                start_lines,
                typewriter=start_typewriter,
                cps=start_cps,
                line_delay_s=start_line_delay_s,
                persist_to_buffer=False,
            )

            base_lines = list(self._log_buffer)
            rendered_lines = list(start_lines)

            def _render_countdown_snapshot(current_line: str | None) -> None:
                log.clear()
                for line in base_lines:
                    self._write_rich_line(log, line)
                for line in rendered_lines:
                    self._write_rich_line(log, line)
                if current_line is not None:
                    self._write_rich_line(log, current_line)

            for remaining in range(countdown_s, -1, -1):
                _render_countdown_snapshot(repl._hibernate_countdown_line(locale, remaining))
                if remaining > 0:
                    await asyncio.sleep(1.0)

            self._clear_log_widget(clear_buffer=True)
            result = repl._execute_hibernate(
                self.loop,
                years,
                wake_on_low_battery=wake_on_low_battery,
            )
            self._hibernate_panel_blackout = True
            self._render_panel_blackout()
            if wake_blackout_s > 0.0:
                await asyncio.sleep(wake_blackout_s)
            self._hibernate_panel_blackout = False
            self.refresh_panels()
            wake_lines = load_hibernate_wake_sequence_lines(
                locale,
                emergency=repl._hibernate_wake_is_emergency(result),
            )
            await _play_log_sequence(
                wake_lines,
                typewriter=wake_typewriter,
                cps=wake_cps,
                line_delay_s=wake_line_delay_s,
                persist_to_buffer=True,
            )
            lines = presenter.build_command_output(
                repl._render_hibernate_result,
                self.loop,
                result,
            )
            self._log_lines(lines)
        except Exception as e:
            self._log_line(f"[ERROR] hibernate failed: {e}")
        finally:
            self._hibernate_panel_blackout = False
            input_widget.disabled = False
            self._hibernate_sequence_running = False
            self.refresh_panels()
            self.call_later(input_widget.focus)

    def action_startup_skip(self) -> None:
        if not self._startup_sequence_running:
            return
        if not Balance.STARTUP_SEQUENCE_SKIPPABLE:
            return
        self._startup_sequence_skip = True

    def on_key(self, event: events.Key) -> None:
        if event.key == "pageup":
            self.action_scroll_up()
            event.stop()
        if event.key == "pagedown":
            self.action_scroll_down()
            event.stop()
        return

    def on_shutdown(self) -> None:
        self._persist_game_on_exit()

    def _persist_game_on_exit(self) -> None:
        if self._exit_persist_done:
            return
        if self._audio_manager is not None:
            self._audio_manager.shutdown()
        self.loop.stop()
        try:
            with self.loop.with_lock() as state:
                saved_path = save_single_slot(state, self._save_path, user=self._user)
            print(f"[INFO] Game saved: {saved_path}")
        except SaveLoadError as exc:
            print(f"[WARN] Failed to save game: {exc}", file=sys.stderr)
        self._exit_persist_done = True

    def action_clear_log(self) -> None:
        self._clear_log_widget()

    def action_help(self) -> None:
        with self.loop.with_lock() as state:
            self._log_lines(presenter.build_help_lines(state, verbose=resolve_help_verbose(state.os)))

    def action_help_verbose(self) -> None:
        with self.loop.with_lock() as state:
            self._log_lines(presenter.build_help_lines(state, verbose=True))

    def action_toggle_status(self) -> None:
        self._panel_visible["status"] = not self._panel_visible["status"]
        self._apply_panel_layout()

    def action_toggle_alerts(self) -> None:
        self._panel_visible["alerts"] = not self._panel_visible["alerts"]
        self._apply_panel_layout()

    def action_toggle_jobs(self) -> None:
        self._panel_visible["jobs"] = not self._panel_visible["jobs"]
        self._apply_panel_layout()

    def action_toggle_panels(self) -> None:
        any_visible = any(self._panel_visible.values())
        next_state = not any_visible
        for key in self._panel_visible:
            self._panel_visible[key] = next_state
        self._apply_panel_layout()

    def _apply_panel_layout(self) -> None:
        status_widget = self.query_one("#status", RichLog)
        alerts_widget = self.query_one("#alerts", RichLog)
        jobs_widget = self.query_one("#jobs", RichLog)
        right_widget = self.query_one("#right", Vertical)
        main_widget = self.query_one("#main", Horizontal)
        log_widget = self.query_one("#log", RichLog)

        status_widget.display = self._panel_visible["status"]
        alerts_widget.display = self._panel_visible["alerts"]
        jobs_widget.display = self._panel_visible["jobs"]
        right_widget.display = self._panel_visible["alerts"] or self._panel_visible["jobs"]
        main_widget.display = self._panel_visible["status"] or right_widget.display

        if not main_widget.display:
            log_widget.styles.height = "1fr"
            log_widget.styles.margin = (0, 0)
        else:
            log_widget.styles.height = 16
            log_widget.styles.margin = (1, 0)

    def action_history_prev(self) -> None:
        input_widget = self.query_one("#input", Input)
        if not self._history:
            return
        if self._history_index >= len(self._history):
            self._history_current = input_widget.value
        if self._history_index > 0:
            self._history_index -= 1
        input_widget.value = self._history[self._history_index]
        input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        input_widget = self.query_one("#input", Input)
        if not self._history:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            input_widget.value = self._history[self._history_index]
        else:
            self._history_index = len(self._history)
            input_widget.value = self._history_current
        input_widget.cursor_position = len(input_widget.value)

    def action_scroll_up(self) -> None:
        focused = self.focused
        if focused and hasattr(focused, "scroll_up"):
            focused.scroll_up()
            return
        self.query_one("#log", RichLog).scroll_up()

    def action_scroll_down(self) -> None:
        focused = self.focused
        if focused and hasattr(focused, "scroll_down"):
            focused.scroll_down()
            return
        self.query_one("#log", RichLog).scroll_down()

    def action_complete(self) -> None:
        focused = self.focused
        if not isinstance(focused, Input):
            return
        buf = focused.value
        ends_with_space = buf.endswith(" ")
        tokens = buf.strip().split() if buf.strip() else []
        if ends_with_space:
            token = ""
            base = buf
        else:
            token = tokens[-1] if tokens else ""
            base = buf[:-len(token)] if token else buf

        with self.loop.with_lock() as state:
            candidates = self._get_completion_candidates(state, buf, token)

        if not candidates:
            return
        candidates = sorted(set(candidates))

        common_prefix = candidates[0]
        for c in candidates[1:]:
            while not c.startswith(common_prefix) and common_prefix:
                common_prefix = common_prefix[:-1]
        if common_prefix and len(common_prefix) > len(token):
            new_value = base + common_prefix
            focused.value = new_value
            focused.cursor_position = len(new_value)
            self._last_complete_key = ""
            return

        # If multiple options with no new common prefix, require double-tab to list.
        key = f"{base}|{token}"
        now = time.time()
        if (
            key == self._last_complete_key
            and now - self._last_complete_at < 1.5
            and candidates == self._last_complete_candidates
        ):
            self._log_line("completions: " + " ".join(candidates))
            self._last_complete_key = ""
            self._last_complete_candidates = []
            return
        self._last_complete_key = key
        self._last_complete_at = now
        self._last_complete_candidates = candidates
        return

    def _get_completion_candidates(self, state, buf: str, text: str) -> list[str]:
        tokens = buf.split()
        if buf.endswith(" "):
            tokens.append("")
        token = ""
        if buf and not buf.endswith(" ") and tokens:
            token = tokens[-1]
        cmd = tokens[0] if tokens else ""
        candidates: list[str] = []
        base_commands = [
            "help",
            "clear",
            "status",
            "jobs",
            "alerts",
            "diag",
            "about",
            "man",
            "auth",
            "config",
            "mail",
            "intel",
            "ls",
            "cat",
            "scan",
            "map",
            "routes",
            "graph",
            "path",
            "locate",
            "ship",
            "dock",
            "undock",
            "nav",
            "navigation",
            "travel",
            "uplink",
            "relay",
            "salvage",
            "route",
            "drone",
            "repair",
            "inventory",
            "cargo",
            "boot",
            "job",
            "system",
            "hibernate",
            "wait",
            "debug",
            "power",
            "logs",
            "log",
            "module",
            "modules",
            "exit",
            "quit",
        ]

        systems = list(state.ship.systems.keys())
        drones = list(state.ship.drones.keys())
        contacts = repl._known_contact_ids_for_completion(state)
        dock_targets = repl._dock_targets_for_completion(state)
        route_solve_targets = repl._route_solve_targets_for_completion(state)
        travel_targets = repl._travel_targets_for_completion(state)
        drone_local_world_targets = repl._drone_local_world_node_targets_for_completion(state)
        drone_move_targets = repl._drone_move_targets_for_completion(state)
        drone_deploy_targets = repl._drone_deploy_targets_for_completion(state)
        modules_catalog = sorted(load_modules().keys())
        modules = list(set(state.ship.cargo_modules or state.ship.manifest_modules))
        services = []
        for sys in state.ship.systems.values():
            if sys.service and sys.service.is_installed:
                services.append(sys.service.service_name)
        fs_paths = list(state.os.fs.keys())

        if not tokens:
            return [c for c in base_commands if c.startswith(text)]
        if len(tokens) == 1:
            return [c for c in base_commands if c.startswith(text)]
        if cmd == "help":
            if len(tokens) == 2:
                return [c for c in ["--verbose", "-v", "--no-verbose"] if c.startswith(text)]
        if cmd in {"diag", "about", "locate"}:
            return [s for s in systems if s.startswith(text)]
        if cmd == "boot":
            return [s for s in services if s.startswith(text)]
        if cmd in {"ls", "cat"}:
            path_text = token or text
            if "/" in path_text:
                dir_part, base_part = path_text.rsplit("/", 1)
                dir_path = normalize_path(dir_part or "/")
                prefix = base_part
            else:
                dir_path = "/"
                prefix = path_text
            try:
                entries = list_dir(state.os.fs, dir_path)
            except Exception:
                entries = []
            for name in entries:
                if not name.startswith(prefix):
                    continue
                if "/" in path_text:
                    if path_text.startswith("/"):
                        full = normalize_path(f"{dir_path}/{name}")
                    else:
                        full = f"{dir_part}/{name}" if dir_part else name
                    candidates.append(full)
                else:
                    candidates.append(name)
            return candidates
        if cmd == "repair":
            if len(tokens) == 2:
                return [d for d in drones if d.startswith(text)] + [s for s in systems if s.startswith(text)]
            if len(tokens) == 3:
                if tokens[1] in systems:
                    return [c for c in ["--selftest"] if c.startswith(text)]
                return [s for s in systems if s.startswith(text)]
        if cmd in {"dock"}:
            return [c for c in dock_targets if c.startswith(text)]
        if cmd == "undock":
            return []
        if cmd in {"nav", "navigation", "travel"}:
            def _travel_targets(prefix: str) -> list[str]:
                return [c for c in travel_targets if c.startswith(prefix)]

            if len(tokens) == 2:
                base_opts = ["map", "abort", "--no-cruise"]
                if cmd == "nav":
                    base_opts.extend(["sectors", "routes", "contacts", "graph", "galaxy"])
                return [c for c in base_opts if c.startswith(text)] + _travel_targets(text)
            if len(tokens) == 3 and tokens[1] == "map":
                return [c for c in ["sectors", "graph", "path", "routes", "contacts", "galaxy"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "map" and tokens[2] == "galaxy":
                return [c for c in ["sector", "local", "regional", "global"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "map" and tokens[2] in {"graph", "path"}:
                return _travel_targets(text)
            if len(tokens) == 3 and tokens[1] == "--no-cruise":
                return _travel_targets(text)
            if len(tokens) == 3 and tokens[1] == "graph":
                return _travel_targets(text)
            if len(tokens) == 3 and tokens[1] == "galaxy":
                return [c for c in ["sector", "local", "regional", "global"] if c.startswith(text)]
            return _travel_targets(text)
        if cmd == "map":
            if len(tokens) == 2:
                return [c for c in ["path"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "path":
                return [c for c in contacts if c.startswith(text)]
        if cmd == "ship":
            if len(tokens) == 2:
                return [c for c in ["sectors", "survey", "map"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "survey":
                ship_aliases = [state.ship.ship_id] if state.ship.ship_id.startswith(text) else []
                ship_aliases += [s for s in ["RETORNO_SHIP"] if s.startswith(text)]
                return [c for c in contacts if c.startswith(text)] + ship_aliases
        if cmd == "graph":
            if len(tokens) == 2:
                return [c for c in contacts if c.startswith(text)]
        if cmd == "path":
            if len(tokens) == 2:
                return [c for c in contacts if c.startswith(text)]
        if cmd == "power":
            if len(tokens) == 2:
                return [c for c in ["status", "plan", "on", "off"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] in {"off", "on"}:
                return [s for s in systems if s.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "plan":
                return [c for c in ["cruise", "normal"] if c.startswith(text)]
        if cmd == "system":
            if len(tokens) == 2:
                return [c for c in ["off", "on"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] in {"off", "on"}:
                return [s for s in systems if s.startswith(text)]
        if cmd == "job":
            if len(tokens) == 2:
                return [c for c in ["cancel"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "cancel":
                return [jid for jid in active_job_display_ids(state.jobs) if jid.startswith(text)]
        if cmd == "log":
            if len(tokens) == 2:
                return [c for c in ["copy"] if c.startswith(text)]
        if cmd == "jobs":
            if len(tokens) == 2:
                return [c for c in ["all", "5", "10", "20", "50"] if c.startswith(text)]
        if cmd == "debug":
            if len(tokens) == 2:
                return [
                    c
                    for c in [
                        "on",
                        "off",
                        "status",
                        "scenario",
                        "seed",
                        "deadnodes",
                        "arcs",
                        "lore",
                        "modules",
                        "galaxy",
                        "add",
                    ]
                    if c.startswith(text)
                ]
            if len(tokens) == 3 and tokens[1] == "scenario":
                return [c for c in ["prologue", "sandbox", "dev"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "add":
                return [c for c in ["scrap", "module", "drone", "drones"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "add" and tokens[2] == "module":
                return [m for m in modules_catalog if m.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "add" and tokens[2] in {"scrap", "drone", "drones"}:
                return [c for c in ["1", "5", "10", "50", "100"] if c.startswith(text)]
            if len(tokens) == 5 and tokens[1] == "add" and tokens[2] == "module":
                return [c for c in ["1", "2", "5", "10"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "galaxy":
                return [c for c in ["map"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "galaxy" and tokens[2] == "map":
                return [c for c in ["sector", "local", "regional", "global"] if c.startswith(text)]
        if cmd == "module":
            if len(tokens) == 2:
                return [c for c in ["inspect"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "inspect":
                return [m for m in modules_catalog if m.startswith(text)]
        if cmd == "modules":
            return []
        if cmd == "inventory":
            if len(tokens) == 2:
                return [c for c in ["audit"] if c.startswith(text)]
        if cmd == "cargo":
            if len(tokens) == 2:
                return [c for c in ["audit"] if c.startswith(text)]
        if cmd == "shutdown":
            if len(tokens) == 2:
                return [s for s in systems if s.startswith(text)]
        if cmd == "system":
            if len(tokens) == 2:
                return [c for c in ["off", "on"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] in {"off", "on"}:
                return [s for s in systems if s.startswith(text)]
        if cmd == "hibernate":
            if len(tokens) == 2:
                return [c for c in ["until_arrival"] if c.startswith(text)]
        if cmd == "man":
            topics: set[str] = set()
            for path in fs_paths:
                if (
                    path.startswith("/manuals/commands/")
                    or path.startswith("/manuals/systems/")
                    or path.startswith("/manuals/alerts/")
                    or path.startswith("/manuals/modules/")
                    or path.startswith("/manuals/concepts/")
                ):
                    name = path.rsplit("/", 1)[-1]
                    if name.endswith(".txt"):
                        name = name[:-4]
                    if name.endswith(".en") or name.endswith(".es"):
                        name = name[:-3]
                    topics.add(name)
            return [t for t in sorted(topics) if t.startswith(text)]
        if cmd == "about":
            topics = set(systems)
            topics.update(state.events.alerts.keys())
            for path in fs_paths:
                if path.startswith("/manuals/alerts/"):
                    name = path.rsplit("/", 1)[-1]
                    if name.endswith(".txt"):
                        name = name[:-4]
                    if name.endswith(".en") or name.endswith(".es"):
                        name = name[:-3]
                    topics.add(name)
                if path.startswith("/manuals/modules/"):
                    name = path.rsplit("/", 1)[-1]
                    if name.endswith(".txt"):
                        name = name[:-4]
                    if name.endswith(".en") or name.endswith(".es"):
                        name = name[:-3]
                    topics.add(name)
            return [t for t in sorted(topics) if t.startswith(text)]
        if cmd == "alerts":
            if len(tokens) == 2:
                return [c for c in ["explain"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "explain":
                return [k for k in state.events.alerts.keys() if k.startswith(text)]
        if cmd == "uplink":
            return []
        if cmd == "relay":
            if len(tokens) == 2:
                return [c for c in ["uplink"] if c.startswith(text)]
            return []
        if cmd == "drone":
            if len(tokens) == 2:
                return [c for c in ["status", "deploy", "deploy!", "move", "survey", "reboot", "recall", "autorecall", "repair", "install", "uninstall", "salvage"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] in {"status", "deploy", "deploy!", "reboot", "autorecall", "repair", "move", "install", "uninstall", "survey"}:
                return [d for d in drones if d.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "recall":
                recall_targets = [c for c in ["all"] if c.startswith(text)]
                recall_targets += [d for d in drones if d.startswith(text)]
                return recall_targets
            if len(tokens) == 4 and tokens[1] in {"deploy", "deploy!"}:
                return [t for t in drone_deploy_targets if t.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "move":
                ship_aliases = [state.ship.ship_id] if state.ship.ship_id.startswith(text) else []
                local_targets = [t for t in drone_move_targets if t.startswith(text)]
                return list(dict.fromkeys(local_targets + ship_aliases))
            if len(tokens) == 4 and tokens[1] == "autorecall":
                return [c for c in ["on", "off", "10"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "install":
                return [m for m in modules if m.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "uninstall":
                target_id = tokens[2]
                target_drone = state.ship.drones.get(target_id)
                ship_installed = sorted(set(state.ship.installed_modules or []))
                if not target_drone:
                    return [m for m in ship_installed if m.startswith(text)]
                installed = sorted(set(target_drone.installed_modules or []))
                all_candidates = list(dict.fromkeys(ship_installed + installed))
                return [m for m in all_candidates if m.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "repair":
                return [x for x in sorted(set(systems) | set(drones)) if x.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "survey":
                return [c for c in drone_local_world_targets if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "salvage":
                return [c for c in ["scrap", "module", "modules", "drone", "drones", "data"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "salvage":
                return [d for d in drones if d.startswith(text)]
            if len(tokens) == 5 and tokens[1] == "salvage":
                return [c for c in drone_local_world_targets if c.startswith(text)]
        if cmd == "salvage":
            if len(tokens) == 2:
                return [c for c in ["scrap", "module", "modules", "drone", "drones", "data"] if c.startswith(text)]
            if len(tokens) == 3:
                return [d for d in drones if d.startswith(text)]
            if len(tokens) == 4:
                return [c for c in drone_local_world_targets if c.startswith(text)]
        if cmd == "route":
            if len(tokens) == 2:
                return [c for c in ["solve"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "solve":
                return [c for c in route_solve_targets if c.startswith(text)]
        if cmd == "config":
            if len(tokens) == 2:
                return [c for c in ["set", "show"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "set":
                return [c for c in config_keys() if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "set":
                return [c for c in config_value_choices(tokens[2]) if c.startswith(text)]
        if cmd == "auth":
            if len(tokens) == 2:
                return [c for c in ["status", "recover"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "recover":
                return [c for c in ["med", "eng", "ops", "sec"] if c.startswith(text)]
        if cmd == "mail":
            if len(tokens) == 2:
                return [c for c in ["inbox", "read"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "read":
                mail_ids = repl._list_mail_ids(state, "inbox")
                return [c for c in ["latest"] + mail_ids if c.startswith(text)]
        if cmd == "intel":
            if len(tokens) == 2:
                return [c for c in ["show", "import", "export", "all"] if c.startswith(text)] + [t for t in ["10", "20", "50"] if t.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "show":
                return [i.intel_id for i in state.world.intel if i.intel_id.startswith(text.upper())]
            if len(tokens) == 3 and tokens[1] in {"import", "export"}:
                path_text = token or text
                if "/" in path_text:
                    dir_part, base_part = path_text.rsplit("/", 1)
                    dir_path = normalize_path(dir_part or "/")
                    prefix = base_part
                else:
                    dir_path = "/"
                    prefix = path_text
                try:
                    entries = list_dir(state.os.fs, dir_path)
                except Exception:
                    entries = []
                for name in entries:
                    if not name.startswith(prefix):
                        continue
                    if "/" in path_text:
                        if path_text.startswith("/"):
                            full = normalize_path(f"{dir_path}/{name}")
                        else:
                            full = f"{dir_part}/{name}" if dir_part else name
                        candidates.append(full)
                    else:
                        candidates.append(name)
                return candidates
        return candidates

    def _log_line(self, line: str, *, separate: bool = False) -> None:
        if line is None:
            return
        if separate and self._log_buffer and self._log_buffer[-1] != "":
            self.query_one("#log", RichLog).write("")
            self._log_buffer.append("")
        self._write_rich_line(self.query_one("#log", RichLog), line)
        self._log_buffer.append(line)
        if len(self._log_buffer) > 2000:
            self._log_buffer = self._log_buffer[-2000:]

    def _fatal_error(self) -> None:
        # Override Textual's rich traceback with standard Python traceback.
        import sys
        import traceback
        self.bell()
        exc = getattr(self, "_exception", None)
        if exc is not None:
            traceback.print_exception(exc.__class__, exc, exc.__traceback__, file=sys.stderr)
        else:
            traceback.print_exc()
        self._close_messages_no_wait()

    def _log_lines(self, lines: list[str]) -> None:
        for line in lines:
            self._log_line(line)

    def _confirm_abandon_drones_needed(self, state, action) -> bool:
        current_node = state.world.current_node_id
        out = []
        for d in state.ship.drones.values():
            if d.status in {DroneStatus.DEPLOYED, DroneStatus.DISABLED} and d.location.kind == "world_node":
                out.append(d)
        if not out:
            return False
        locale = state.os.locale.value
        drone_ids = ", ".join(d.drone_id for d in out)
        prompts = {
            "en": f"WARNING: drones not aboard ({drone_ids}). Leaving {current_node} will abandon them. Continue? [y/N]",
            "es": f"ADVERTENCIA: drones fuera de la nave ({drone_ids}). Al salir de {current_node} quedarán abandonados. ¿Continuar? [s/N]",
        }
        self._pending_confirm_action = action
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)
        return True

    def _confirm_nav_needed(self, state, action) -> bool:
        locale = state.os.locale.value
        current_node = state.world.current_node_id
        dest = getattr(action, "node_id", "?")
        out = []
        for d in state.ship.drones.values():
            if d.status in {DroneStatus.DEPLOYED, DroneStatus.DISABLED} and d.location.kind == "world_node":
                out.append(d)
        if out:
            drone_ids = ", ".join(d.drone_id for d in out)
            prompts = {
                "en": (
                    f"WARNING: confirm nav to {dest}? "
                    f"Drones not aboard ({drone_ids}) will be abandoned when leaving {current_node}. Continue? [y/N]"
                ),
                "es": (
                    f"ADVERTENCIA: ¿confirmar nav a {dest}? "
                    f"Los drones fuera de la nave ({drone_ids}) quedarán abandonados al salir de {current_node}. "
                    "¿Continuar? [s/N]"
                ),
            }
        else:
            prompts = {
                "en": f"WARNING: confirm nav to {dest}. Continue? [y/N]",
                "es": f"ADVERTENCIA: confirmar nav a {dest}. ¿Continuar? [s/N]",
            }
        self._pending_confirm_action = action
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)
        return True

    def _confirm_travel_abort_needed(self, state) -> bool:
        locale = state.os.locale.value
        prompts = {
            "en": "WARNING: aborting travel. Continue? [y/N]",
            "es": "ADVERTENCIA: abortar el viaje. ¿Continuar? [s/N]",
        }
        self._pending_confirm_action = "TRAVEL_ABORT"
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)
        return True

    def _confirm_hibernate_non_cruise_needed(self, state) -> bool:
        locale = state.os.locale.value
        prompts = {
            "en": "WARNING: hibernating while not in CRUISE may increase wear. Continue? [y/N]",
            "es": "ADVERTENCIA: hibernar fuera de CRUISE puede aumentar el desgaste. ¿Continuar? [s/N]",
        }
        self._pending_confirm_action = "HIBERNATE_NON_CRUISE"
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)
        return True

    def _confirm_hibernate_drones_needed(self, state) -> bool:
        deployed = [
            d for d in state.ship.drones.values()
            if d.status in {DroneStatus.DEPLOYED, DroneStatus.DISABLED}
            and d.location.kind in {"world_node", "ship_sector"}
        ]
        if not deployed:
            return False
        locale = state.os.locale.value
        drone_ids = ", ".join(d.drone_id for d in deployed)
        prompts = {
            "en": f"WARNING: drones deployed ({drone_ids}) may drain batteries during hibernation. Continue? [y/N]",
            "es": f"ADVERTENCIA: drones desplegados ({drone_ids}) pueden agotar batería durante la hibernación. ¿Continuar? [s/N]",
        }
        self._pending_confirm_action = "HIBERNATE_DRONES"
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)
        return True

    def _confirm_hibernate_wake_needed(self, state) -> None:
        locale = state.os.locale.value
        prompts = {
            "en": "Wake if any drone reaches low battery threshold? [y/N]",
            "es": "¿Despertar si algún dron alcanza batería baja? [s/N]",
        }
        self._pending_confirm_action = "HIBERNATE_WAKE"
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)

    def _confirm_hibernate_start_needed(self, state, parsed: Hibernate) -> bool:
        locale = state.os.locale.value
        if parsed.mode == "until_arrival":
            prompts = {
                "en": "WARNING: confirm hibernation until arrival. Continue? [y/N]",
                "es": "ADVERTENCIA: confirmar hibernación hasta la llegada. ¿Continuar? [s/N]",
            }
        else:
            prompts = {
                "en": f"WARNING: confirm hibernation for {parsed.years:g}y. Continue? [y/N]",
                "es": f"ADVERTENCIA: confirmar hibernación durante {parsed.years:g} años. ¿Continuar? [s/N]",
            }
        self._pending_confirm_action = "HIBERNATE_START"
        self._pending_confirm_prompt = prompts.get(locale, prompts["en"])
        self._pending_confirm_locale = locale
        self._log_line(self._pending_confirm_prompt)
        return True

    def _continue_hibernate(self, parsed: Hibernate, wake_on_low_battery: bool) -> None:
        try:
            with self.loop.with_lock() as state:
                block_msg = repl._hibernate_blocked_message(state)
                warn_msg = repl._hibernate_soc_warning(state)
                if block_msg:
                    self._log_line(block_msg)
                    self._pending_hibernate_parsed = None
                    self._pending_hibernate_requires_non_cruise = False
                    self._pending_wake_on_low_battery = False
                    return
                if warn_msg:
                    self._log_line(warn_msg)
                if parsed.mode == "until_arrival":
                    if not state.ship.in_transit:
                        self._log_line("hibernate: not in transit")
                        self._pending_hibernate_parsed = None
                        return
                    remaining_s = max(0.0, state.ship.arrival_t - state.clock.t)
                    years = remaining_s / repl.Balance.YEAR_S if repl.Balance.YEAR_S else 0.0
                    if state.ship.op_mode != "CRUISE":
                        self._pending_years = years
                        self._pending_wake_on_low_battery = wake_on_low_battery
                        self._pending_hibernate_requires_non_cruise = True
                        self._confirm_hibernate_non_cruise_needed(state)
                        return
                else:
                    years = parsed.years
            asyncio.create_task(self._run_hibernate_start_sequence(years, wake_on_low_battery))
        except Exception as e:
            self._log_line(f"[ERROR] hibernate failed: {e}")
        self._pending_hibernate_parsed = None
        self._pending_hibernate_requires_non_cruise = False
        self._pending_wake_on_low_battery = False

    def _set_log_content(self, widget: RichLog, lines: list[str], preserve_scroll: bool = False, follow_end: bool = False) -> None:
        scroll_y = widget.scroll_y if preserve_scroll else None
        prev_auto = widget.auto_scroll
        if preserve_scroll:
            widget.auto_scroll = False
        widget.clear()
        for line in lines:
            self._write_rich_line(widget, line)
        if follow_end:
            widget.scroll_end(animate=False)
        elif preserve_scroll and scroll_y is not None:
            widget.scroll_y = min(scroll_y, widget.max_scroll_y)
        if preserve_scroll:
            widget.auto_scroll = prev_auto

    def _write_rich_line(self, widget: RichLog, line: str) -> None:
        if line == "":
            widget.write("")
            return
        widget.write(render_rich_line(line, self._theme_preset))

    def _apply_theme(self, preset: str | None) -> None:
        palette = get_theme_palette(preset)
        self._theme_preset = palette.name

        self.screen.styles.background = palette.background
        self.screen.styles.color = palette.foreground

        panel_ids = ("status", "alerts", "jobs", "log", "input", "sep_header_right")
        for widget_id in panel_ids:
            widget = self.query_one(f"#{widget_id}")
            widget.styles.background = palette.panel_background
            widget.styles.color = palette.foreground

        for widget_id in ("status", "alerts", "jobs", "log"):
            widget = self.query_one(f"#{widget_id}", RichLog)
            widget.styles.scrollbar_color = palette.scrollbar
            widget.styles.scrollbar_color_hover = palette.accent
            widget.styles.scrollbar_color_active = palette.info
            widget.styles.scrollbar_background = palette.panel_background

        header = self.query_one("#header", Static)
        header.styles.background = palette.header_background
        header.styles.color = palette.header_foreground

        power = self.query_one("#power", Static)
        power.styles.background = palette.power_background
        power.styles.color = palette.power_foreground

        input_widget = self.query_one("#input", Input)
        input_widget.styles.background = palette.panel_background
        input_widget.styles.color = palette.foreground

    def refresh_panels(self) -> None:
        if self._hibernate_panel_blackout:
            self._render_panel_blackout()
            return
        with self.loop.with_lock() as state:
            theme_preset = normalize_theme_preset(getattr(state.os, "theme_preset", "linux"))
            header = presenter.build_header(state)
            status_lines = presenter.build_status_lines(state)
            alerts_lines = presenter.build_alerts_lines(state)
            jobs_lines = presenter.build_jobs_lines(state)
            power_lines = presenter.build_power_lines(state)
        if theme_preset != self._theme_preset:
            self._apply_theme(theme_preset)
        self.query_one("#header", Static).update(render_rich_line(header, self._theme_preset))
        status_widget = self.query_one("#status", RichLog)
        if status_widget.display:
            self._set_log_content(
                status_widget,
                status_lines,
                preserve_scroll=True,
                follow_end=False,
            )
        alerts_widget = self.query_one("#alerts", RichLog)
        jobs_widget = self.query_one("#jobs", RichLog)
        if alerts_widget.display:
            self._set_log_content(
                alerts_widget,
                alerts_lines,
                preserve_scroll=(self.focused is alerts_widget),
                follow_end=(self.focused is not alerts_widget),
            )
        if jobs_widget.display:
            self._set_log_content(
                jobs_widget,
                jobs_lines,
                preserve_scroll=(self.focused is jobs_widget),
                follow_end=(self.focused is not jobs_widget),
            )
        self.query_one("#power", Static).update(render_rich_block(power_lines, self._theme_preset))
        if self._startup_sequence_running or self._hibernate_sequence_running:
            return
        auto_events = self.loop.drain_events()
        if auto_events:
            audio_enabled = False
            with self.loop.with_lock() as state:
                lines = presenter.format_event_lines(state, auto_events)
                audio_enabled = state.os.audio.enabled
            self._log_lines(lines)
            if self._audio_manager is not None:
                self._audio_manager.handle_event_batch(audio_enabled, auto_events)
                notice = self._audio_manager.consume_notice()
                if notice:
                    self._log_line(notice)

    def _startup_tips(self, locale: str) -> list[str]:
        tips = {
            "en": [
                "\n[INFO] new mail detected.",
                "Tip: use 'mail inbox' to list messages.",
                "Tip: use 'mail read <id|latest>' or 'cat <path>' to read.",
                "Tip: if you still don't remember the command instructions, manuals are under /manuals (try: ls /manuals/commands, man <topic>).",
                "Tip: use 'config set lang' to change ship_os languaje",
                "Tip: use 'help' to see available commands.",
                "Tip: use TAB key for list and autocomplete available commands, id's, paths, etc.",
            ],
            "es": [
                "\n[INFO] new mail detected.",
                "Consejo: use 'mail inbox' to list messages.",
                "Consejo: use 'mail read <id|latest>' or 'cat <path>' to read.",
                "Consejo: if you still don't remember the command instructions, manuals are under /manuals (try: ls /manuals/commands, man <topic>).",
                "Consejo: use 'config set lang' to change ship_os languaje",
                "Consejo: use 'help' to see available commands.",
                "Consejo: usa la tecla TAB para listar y/o completar automáticamente comandos disponibles, identificaciones, rutas, etc.",
            ],
        }
        return tips.get(locale, tips["en"])

    def _drain_auto_to_log(self) -> None:
        auto_events = self.loop.drain_events()
        if not auto_events:
            return
        audio_enabled = False
        with self.loop.with_lock() as state:
            lines = presenter.format_event_lines(state, auto_events)
            audio_enabled = state.os.audio.enabled
        self._log_lines(lines)
        if self._audio_manager is not None:
            self._audio_manager.handle_event_batch(audio_enabled, auto_events)
            notice = self._audio_manager.consume_notice()
            if notice:
                self._log_line(notice)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if self._hibernate_sequence_running:
            return
        if self._pending_confirm_action is not None:
            reply = text.lower()
            locale = self._pending_confirm_locale
            yes = {"y", "yes"}
            if locale == "es":
                yes = {"s", "si", "sí", "y", "yes"}
            action = self._pending_confirm_action
            self._pending_confirm_action = None
            self._pending_confirm_prompt = ""
            if action == "HIBERNATE_WAKE":
                wake = reply in yes
                self._pending_wake_on_low_battery = wake
                if self._pending_hibernate_requires_non_cruise:
                    with self.loop.with_lock() as state:
                        self._confirm_hibernate_non_cruise_needed(state)
                    return
                if self._pending_hibernate_parsed is not None:
                    self._continue_hibernate(self._pending_hibernate_parsed, wake)
                return
            if action == "HIBERNATE_START":
                if reply in yes:
                    with self.loop.with_lock() as state:
                        if self._confirm_hibernate_drones_needed(state):
                            return
                    if self._pending_hibernate_parsed is not None:
                        self._continue_hibernate(self._pending_hibernate_parsed, wake_on_low_battery=False)
                else:
                    self._pending_hibernate_parsed = None
                    self._pending_hibernate_requires_non_cruise = False
                    self._pending_wake_on_low_battery = False
                    self._log_line("(cancelled)")
                return
            if reply in yes:
                if action == "TRAVEL_ABORT":
                    from retorno.core.actions import TravelAbort
                    self._log_line("> nav abort", separate=True)
                    ev = self.loop.apply_action(TravelAbort())
                    if ev:
                        audio_enabled = False
                        with self.loop.with_lock() as state:
                            lines = presenter.format_event_lines(state, [("cmd", e) for e in ev])
                            audio_enabled = state.os.audio.enabled
                        self._log_lines(lines)
                        if self._audio_manager is not None:
                            self._audio_manager.handle_event_batch(audio_enabled, ev)
                            notice = self._audio_manager.consume_notice()
                            if notice:
                                self._log_line(notice)
                elif action == "HIBERNATE_DRONES":
                    with self.loop.with_lock() as state:
                        self._confirm_hibernate_wake_needed(state)
                    return
                elif action == "HIBERNATE_NON_CRUISE":
                    self._log_line("> hibernate until_arrival", separate=True)
                    asyncio.create_task(
                        self._run_hibernate_start_sequence(
                            self._pending_years,
                            self._pending_wake_on_low_battery,
                        )
                    )
                    self._pending_hibernate_parsed = None
                    self._pending_hibernate_requires_non_cruise = False
                    self._pending_wake_on_low_battery = False
                else:
                    if action.__class__.__name__ == "Travel":
                        self._log_line(f"> nav {getattr(action, 'node_id', '?')}", separate=True)
                    else:
                        self._log_line(f"> {action.__class__.__name__.lower()}", separate=True)
                    ev = self.loop.apply_action(action)
                    if ev:
                        audio_enabled = False
                        with self.loop.with_lock() as state:
                            lines = presenter.format_event_lines(state, [("cmd", e) for e in ev])
                            audio_enabled = state.os.audio.enabled
                            if action.__class__.__name__ == "Travel":
                                for e in ev:
                                    if e.type == "travel_started" or e.type == repl.EventType.TRAVEL_STARTED:
                                        dest = e.data.get("to", getattr(action, "node_id", "?"))
                                        msg = {
                                            "en": f"(nav) confirmed: en route to {dest}",
                                            "es": f"(nav) confirmado: rumbo a {dest}",
                                        }
                                        lines.append(msg.get(state.os.locale.value, msg["en"]))
                                        break
                        self._log_lines(lines)
                        if self._audio_manager is not None:
                            self._audio_manager.handle_event_batch(audio_enabled, ev)
                            notice = self._audio_manager.consume_notice()
                            if notice:
                                self._log_line(notice)
            else:
                if isinstance(action, str) and action in {"HIBERNATE_DRONES", "HIBERNATE_WAKE", "HIBERNATE_NON_CRUISE"}:
                    self._pending_hibernate_parsed = None
                    self._pending_hibernate_requires_non_cruise = False
                    self._pending_wake_on_low_battery = False
                self._log_line("(cancelled)")
            return
        if not self._history or self._history[-1] != text:
            self._history.append(text)
        self._history_index = len(self._history)
        self._history_current = ""
        self._log_line(f"> {text}", separate=True)
        try:
            parsed = parse_command(text)
        except ParseError as e:
            locale = self.loop.state.os.locale.value
            self._log_line(f"[ERROR] {format_parse_error(e, locale)}")
            return
        if parsed is None:
            return
        if parsed == "EXIT":
            self._persist_game_on_exit()
            self.exit()
            return
        if parsed == "HELP":
            self.action_help()
            return
        if parsed == "HELP_VERBOSE":
            self.action_help_verbose()
            return
        if parsed == "HELP_NO_VERBOSE":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_help_lines(state, verbose=False))
            return
        if parsed == "CLEAR":
            self._clear_log_widget(clear_buffer=True)
            return

        with self.loop.with_lock() as state:
            block_msg = repl._command_blocked_message(state, parsed)
            audio_enabled = state.os.audio.enabled
        if block_msg:
            self._log_line(block_msg)
            if self._audio_manager is not None:
                severity = Severity.WARN if "Action blocked" in block_msg or "Acción bloqueada" in block_msg else Severity.INFO
                self._audio_manager.play_event(audio_enabled, EventType.BOOT_BLOCKED, severity)
                notice = self._audio_manager.consume_notice()
                if notice:
                    self._log_line(notice)
            return

        # Informational commands (drain AUTO first to avoid mixing)
        info_tokens = {
            "JOBS",
            "UPLINK",
            "ALERTS",
            "LOGS",
            "INVENTORY",
            "MODULES",
            "MODULE_INSPECT",
            "SHIP_SECTORS",
            "DRONE_STATUS",
            "POWER_STATUS",
            "CONFIG_SHOW",
            "AUTH_STATUS",
        }
        if (isinstance(parsed, str) and parsed in info_tokens) or (
            isinstance(parsed, tuple)
            and parsed[0] in {
                "LS",
                "CAT",
                "ABOUT",
                "MAN",
                "LOCATE",
                "ALERTS_EXPLAIN",
                "MAIL_LIST",
                "MAIL_READ",
                "JOBS",
                "DEBUG_MODULES",
                "DEBUG_GALAXY_MAP",
                "DEBUG_WORLDGEN_SECTOR",
                "DEBUG_GRAPH_ALL",
                "NAV_MAP",
                "SHIP_SURVEY",
                "DRONE_STATUS",
                "DRONE_AUTORECALL_ENABLED",
                "DRONE_AUTORECALL_THRESHOLD",
            }
        ):
            self._drain_auto_to_log()

        if parsed == "JOBS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_jobs, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "MODULE_INSPECT":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_module_inspect, state, parsed[1]))
            return
        if parsed == "AUTH_STATUS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_auth_status, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "JOBS":
            with self.loop.with_lock() as state:
                limit = None if parsed[1] == "all" else int(parsed[1])
                self._log_lines(presenter.build_command_output(repl.render_jobs, state, limit=limit))
            return
        if isinstance(parsed, tuple) and parsed[0] == "NAV_MAP":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_nav_map, state, parsed[1], parsed[2]))
            return
        if isinstance(parsed, repl.RouteSolve):
            ev = self.loop.apply_action(parsed)
            if ev:
                audio_enabled = False
                with self.loop.with_lock() as state:
                    lines = presenter.format_event_lines(state, [("cmd", e) for e in ev])
                    audio_enabled = state.os.audio.enabled
                self._log_lines(lines)
                if self._audio_manager is not None:
                    self._audio_manager.handle_event_batch(audio_enabled, ev)
                    notice = self._audio_manager.consume_notice()
                    if notice:
                        self._log_line(notice)
            auto_ev = self.loop.drain_events()
            if auto_ev:
                audio_enabled = False
                with self.loop.with_lock() as state:
                    lines = presenter.format_event_lines(state, auto_ev)
                    audio_enabled = state.os.audio.enabled
                self._log_lines(lines)
                if self._audio_manager is not None:
                    self._audio_manager.handle_event_batch(audio_enabled, auto_ev)
                    notice = self._audio_manager.consume_notice()
                    if notice:
                        self._log_line(notice)
            return
        if parsed == "UPLINK":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl._handle_uplink, state))
            return
        if parsed.__class__.__name__ == "TravelAbort":
            with self.loop.with_lock() as state:
                self._confirm_travel_abort_needed(state)
            return
        if parsed == "ALERTS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_alerts, state))
            return
        if parsed == "LOGS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_logs, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "LOG_COPY":
            amount = parsed[1]
            if amount is None:
                amount = min(50, len(self._log_buffer))
            slice_lines = self._log_buffer[-amount:] if amount else []
            content = "\n".join(slice_lines)
            ok = repl._copy_to_clipboard(content)
            locale = self.loop.state.os.locale.value
            if ok:
                msg = {
                    "en": f"(log) copied {len(slice_lines)} lines to clipboard",
                    "es": f"(log) copiadas {len(slice_lines)} líneas al portapapeles",
                }
                self._log_line(msg.get(locale, msg["en"]))
            else:
                path = repl._write_log_copy_file(content)
                msg = {
                    "en": f"(log) clipboard unavailable; wrote {len(slice_lines)} lines to {path}",
                    "es": f"(log) portapapeles no disponible; escrito {len(slice_lines)} líneas en {path}",
                }
                self._log_line(msg.get(locale, msg["en"]))
            return
        if parsed == "INVENTORY":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_inventory, state))
            return
        if parsed == "MODULES":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_modules_installed, state))
            return
        if parsed == "SHIP_SECTORS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_ship_sectors, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "SHIP_SURVEY":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_ship_survey, state, parsed[1]))
            return
        if parsed == "DRONE_STATUS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_drone_status, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DRONE_STATUS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_drone_status, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DRONE_AUTORECALL_ENABLED":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl._set_drone_autorecall, state, parsed[1], bool(parsed[2]), None))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DRONE_AUTORECALL_THRESHOLD":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl._set_drone_autorecall, state, parsed[1], None, float(parsed[2])))
            return
        if parsed == "POWER_STATUS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_power_status, state))
            return
        if parsed == "CONFIG_SHOW":
            backend_name = self._audio_manager.backend.name if self._audio_manager is not None else None
            runtime_status = None
            if self._audio_manager is None:
                runtime_status = "disabled"
            elif self._audio_manager.notice:
                runtime_status = "degraded"
            with self.loop.with_lock() as state:
                self._log_lines(
                    config_show_lines(
                        state.os,
                        audio_backend=backend_name,
                        audio_runtime_status=runtime_status,
                    )
                )
            return
        if isinstance(parsed, tuple) and parsed[0] == "CONFIG_SET":
            key, value = parsed[1], parsed[2]
            with self.loop.with_lock() as state:
                message = apply_config_value(state.os, key, value)
                next_theme = normalize_theme_preset(getattr(state.os, "theme_preset", "linux"))
                audio_enabled, ambient_enabled = audio_flags(state.os)
                self._log_line(message)
            if key == "theme":
                self._apply_theme(next_theme)
                self.refresh_panels()
            if self._audio_manager is not None and key in {"audio", "ambientsound"}:
                self._audio_manager.apply_preferences(audio_enabled, ambient_enabled)
                notice = self._audio_manager.consume_notice()
                if notice:
                    self._log_line(notice)
            return
        if isinstance(parsed, tuple) and parsed[0] == "MAIL_LIST":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_mailbox, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "MAIL_READ":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_mail_read, state, parsed[1]))
            return
        if parsed == "INTEL_LIST":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_intel_list, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_LIST":
            with self.loop.with_lock() as state:
                limit = None if parsed[1] == "all" else int(parsed[1])
                self._log_lines(presenter.build_command_output(repl.render_intel_list, state, limit=limit))
            return
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_IMPORT":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl._handle_intel_import, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_SHOW":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_intel_show, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_EXPORT":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl._handle_intel_export, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "LS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_ls, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "CAT":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_cat, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "ABOUT":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_about, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "MAN":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_man, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "ALERTS_EXPLAIN":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_alert_explain, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "LOCATE":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_locate, state, parsed[1]))
            return

        if parsed.__class__.__name__ in {"Dock", "Travel", "Undock"}:
            with self.loop.with_lock() as state:
                if parsed.__class__.__name__ == "Dock":
                    resolved = repl._resolve_node_id_from_input(state, parsed.node_id)
                    if resolved:
                        parsed.node_id = resolved
                if parsed.__class__.__name__ == "Travel":
                    if self._confirm_nav_needed(state, parsed):
                        return
                elif self._confirm_abandon_drones_needed(state, parsed):
                    return

        if isinstance(parsed, tuple) and parsed[0] == "DEBUG":
            mode = parsed[1]
            if mode == "status":
                with self.loop.with_lock() as state:
                    self._log_line("DEBUG" if state.os.debug_enabled else "NORMAL")
                return
            if mode == "on":
                with self.loop.with_lock() as state:
                    state.os.debug_enabled = True
                self.loop.set_auto_tick(False)
                self._log_line("DEBUG mode enabled")
                return
            if mode == "off":
                with self.loop.with_lock() as state:
                    state.os.debug_enabled = False
                self.loop.set_auto_tick(True)
                self.loop.start()
                self._log_line("DEBUG mode disabled")
                return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ARCS":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug arcs: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(presenter.build_command_output(repl.render_debug_arcs, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_LORE":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug lore: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(presenter.build_command_output(repl.render_debug_lore, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_DEADNODES":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug deadnodes: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(presenter.build_command_output(repl.render_debug_deadnodes, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_MODULES":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug modules: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(presenter.build_command_output(repl.render_modules_catalog, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_GALAXY":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug galaxy: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(presenter.build_command_output(repl.render_debug_galaxy, state))
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_GALAXY_MAP":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug galaxy map: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(
                    presenter.build_command_output(repl.render_debug_galaxy_map, state, parsed[1])
                )
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_WORLDGEN_SECTOR":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug worldgen sector: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(
                    presenter.build_command_output(repl.render_debug_worldgen_sector, state, str(parsed[1]))
                )
            return
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_GRAPH_ALL":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug graph all: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(presenter.build_command_output(repl.render_debug_graph_all, state))
            return

        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_SEED":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug seed: available only in DEBUG mode. Use: debug on")
                    return
                seed = parsed[1]
                state.meta.rng_seed = seed
                state.meta.rng_counter = 0
                self.loop._rng = random.Random(seed)
                self._log_line(f"Seed set to {seed}")
            return

        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ADD_SCRAP":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug add scrap: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(
                    presenter.build_command_output(repl.debug_add_scrap, state, int(parsed[1]))
                )
            return

        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ADD_MODULE":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug add module: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(
                    presenter.build_command_output(repl.debug_add_module, state, str(parsed[1]), int(parsed[2]))
                )
            return

        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ADD_DRONE":
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("debug add drone: available only in DEBUG mode. Use: debug on")
                    return
                self._log_lines(
                    presenter.build_command_output(repl.debug_add_drones, state, int(parsed[1]))
                )
            return

        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_SCENARIO":
            scenario = parsed[1]
            self.loop.set_auto_tick(False)
            self.loop.stop()
            with self.loop.with_lock() as state:
                keep_debug = state.os.debug_enabled
            if scenario in {"sandbox", "dev"}:
                new_state = create_initial_state_sandbox()
            else:
                new_state = create_initial_state_prologue()
            new_state.os.debug_enabled = keep_debug
            with self.loop.with_lock() as state:
                self.loop.state = new_state
                self.loop._events_auto.clear()
                self.loop._rng = random.Random(new_state.meta.rng_seed)
            self.loop.step(1.0)
            if not keep_debug:
                self.loop.set_auto_tick(True)
                self.loop.start()
            self._log_line(f"Scenario set to {scenario}")
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_status, state))
            return

        if isinstance(parsed, tuple) and parsed[0] == "WAIT":
            seconds = parsed[1]
            with self.loop.with_lock() as state:
                if not state.os.debug_enabled:
                    self._log_line("wait is available only in DEBUG mode. Use: debug on")
                    return
            step_events = self.loop.step_many(seconds, dt=1.0)
            step_pairs = [("step", e) for e in step_events]
            audio_enabled = False
            with self.loop.with_lock() as state:
                lines = presenter.format_event_lines(state, step_pairs)
                audio_enabled = state.os.audio.enabled
            self._log_lines(lines)
            if self._audio_manager is not None:
                self._audio_manager.handle_event_batch(audio_enabled, step_events)
                notice = self._audio_manager.consume_notice()
                if notice:
                    self._log_line(notice)
            return

        if isinstance(parsed, Hibernate):
            # Reuse CLI hibernate logic for now.
            self._drain_auto_to_log()
            self._pending_hibernate_parsed = parsed
            self._pending_hibernate_requires_non_cruise = False
            with self.loop.with_lock() as state:
                if self._confirm_hibernate_start_needed(state, parsed):
                    return
            return

        if parsed.__class__.__name__ == "Status":
            self._drain_auto_to_log()
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_status, state))
            return
        if parsed.__class__.__name__ == "Diag":
            self._drain_auto_to_log()
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_diag, state, parsed.system_id))
            return

        # Engine actions
        ev = self.loop.apply_action(parsed)
        if ev:
            audio_enabled = False
            with self.loop.with_lock() as state:
                lines = presenter.format_event_lines(state, [("cmd", e) for e in ev])
                audio_enabled = state.os.audio.enabled
                if parsed.__class__.__name__ == "Travel":
                    for e in ev:
                        if e.type == "travel_started" or e.type == repl.EventType.TRAVEL_STARTED:
                            dest = e.data.get("to", getattr(parsed, "node_id", "?"))
                            msg = {
                                "en": f"(nav) confirmed: en route to {dest}",
                                "es": f"(nav) confirmado: rumbo a {dest}",
                            }
                            lines.append(msg.get(state.os.locale.value, msg["en"]))
                            break
            self._log_lines(lines)
            if self._audio_manager is not None:
                self._audio_manager.handle_event_batch(audio_enabled, ev)
                notice = self._audio_manager.consume_notice()
                if notice:
                    self._log_line(notice)
        else:
            # No immediate events; still ok.
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="RETORNO (Textual UI)")
    parser.add_argument(
        "--new-game",
        "--new",
        action="store_true",
        help="Start a new game and ignore existing save slot.",
    )
    parser.add_argument(
        "--save-path",
        default=None,
        help="Override save slot path (default: ~/.retorno/savegame.dat).",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Save profile name (stored under ~/.retorno/users/<user>/savegame.dat).",
    )
    args = parser.parse_args()

    env_force_new = os.environ.get("RETORNO_NEW_GAME", "").strip().lower() in {"1", "true", "yes", "on"}
    force_new_game = args.new_game or env_force_new
    try:
        profile_user = normalize_user_id(args.user)
    except SaveLoadError as exc:
        print(f"[ERROR] {exc}")
        return
    if force_new_game and save_exists(args.save_path, user=profile_user):
        save_path = resolve_save_path(args.save_path, user=profile_user)
        try:
            reply = input(f"[WARN] Existing save found at {save_path}. Start a new game anyway? [y/N]: ").strip().lower()
        except EOFError:
            reply = ""
        if reply not in {"y", "yes", "s", "si", "sí"}:
            print("Cancelled.")
            return
    RetornoTextualApp(force_new_game=force_new_game, save_path=args.save_path, user=profile_user).run()


if __name__ == "__main__":
    main()
