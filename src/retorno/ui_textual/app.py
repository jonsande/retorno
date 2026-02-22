from __future__ import annotations

import os
import random

from textual.app import App, ComposeResult
from textual import events
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Input, RichLog

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli.parser import ParseError, parse_command
from retorno.cli import repl
from retorno.core.engine import Engine
from retorno.core.actions import Hibernate
from retorno.model.events import Severity
from retorno.model.os import Locale, list_dir, normalize_path
from retorno.runtime.loop import GameLoop
from retorno.ui_textual import presenter


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
        height: 12;
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
        Binding("alt+j", "focus_next", "Next panel", priority=True),
        Binding("alt+k", "focus_previous", "Prev panel", priority=True),
        Binding("k", "scroll_up", "Scroll up", priority=True),
        Binding("j", "scroll_down", "Scroll down", priority=True),
        #Binding("ctrl+n", "focus_next", "Next panel"),
        # Binding("pageup", "scroll_up", "Scroll up"),
        # Binding("pagedown", "scroll_down", "Scroll down"),
        # Binding("[", "scroll_up", "Scroll up"),
        # Binding("]", "scroll_down", "Scroll down"),
        # Binding("alt+[", "scroll_up", "Scroll up"),
        # Binding("alt+]", "scroll_down", "Scroll down"),
    ]

    def __init__(self) -> None:
        scenario = os.getenv("RETORNO_SCENARIO", "prologue").lower()
        if scenario in {"sandbox", "dev"}:
            state = create_initial_state_sandbox()
        else:
            state = create_initial_state_prologue()
        engine = Engine()
        self.loop = GameLoop(engine, state, tick_s=1.0)
        self._history: list[str] = []
        self._history_index: int = 0
        self._history_current: str = ""
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static(id="header")
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
        self.loop.step(1.0)
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
        # Ensure input is focused on start.
        self.call_later(lambda: self.query_one("#input", Input).focus())

    def on_key(self, event: events.Key) -> None:
        if event.key == "pageup":
            self.action_scroll_up()
            event.stop()
        if event.key == "pagedown":
            self.action_scroll_down()
            event.stop()
        return

    def on_shutdown(self) -> None:
        self.loop.stop()

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_help(self) -> None:
        self._log_lines(presenter.build_help_lines())

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
            return

        # No longer prefix; show options in log and complete first.
        self._log_line("completions: " + " ".join(candidates))
        new_value = base + candidates[0]
        focused.value = new_value
        focused.cursor_position = len(new_value)

    def _get_completion_candidates(self, state, buf: str, text: str) -> list[str]:
        tokens = buf.strip().split()
        token = ""
        if buf and not buf.endswith(" ") and tokens:
            token = tokens[-1]
        cmd = tokens[0] if tokens else ""
        candidates: list[str] = []
        base_commands = [
            "help",
            "status",
            "jobs",
            "alerts",
            "diag",
            "about",
            "man",
            "config",
            "mail",
            "intel",
            "ls",
            "cat",
            "contacts",
            "scan",
            "sectors",
            "map",
            "locate",
            "dock",
            "travel",
            "salvage",
            "drone",
            "repair",
            "inventory",
            "cargo",
            "boot",
            "hibernate",
            "wait",
            "debug",
            "power",
            "logs",
            "exit",
            "quit",
        ]

        systems = list(state.ship.systems.keys())
        drones = list(state.ship.drones.keys())
        sectors = list(state.ship.sectors.keys())
        contacts = sorted(state.world.known_nodes if hasattr(state.world, "known_nodes") and state.world.known_nodes else state.world.known_contacts)
        modules = list(set(state.ship.cargo_modules))
        services = []
        for sys in state.ship.systems.values():
            if sys.service and sys.service.is_installed:
                services.append(sys.service.service_name)
        fs_paths = list(state.os.fs.keys())

        if not tokens:
            return [c for c in base_commands if c.startswith(text)]
        if len(tokens) == 1:
            return [c for c in base_commands if c.startswith(text)]
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
                entries = list_dir(state.os.fs, dir_path, state.os.access_level)
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
        if cmd in {"dock", "travel"}:
            return [c for c in contacts if c.startswith(text)]
        if cmd == "power":
            if len(tokens) == 2:
                return [c for c in ["status", "shed", "off", "on", "plan"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] in {"shed", "off", "on"}:
                return [s for s in systems if s.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "plan":
                return [c for c in ["cruise", "normal"] if c.startswith(text)]
        if cmd == "debug":
            if len(tokens) == 2:
                return [c for c in ["on", "off", "status", "scenario"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "scenario":
                return [c for c in ["prologue", "sandbox", "dev"] if c.startswith(text)]
        if cmd == "install":
            return [m for m in modules if m.startswith(text)]
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
                if path.startswith("/manuals/commands/") or path.startswith("/manuals/systems/") or path.startswith("/manuals/alerts/") or path.startswith("/manuals/modules/"):
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
        if cmd == "drone":
            if len(tokens) == 2:
                return [c for c in ["status", "deploy", "deploy!", "move", "reboot", "recall", "repair", "salvage"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] in {"deploy", "deploy!", "reboot", "recall", "repair", "move"}:
                return [d for d in drones if d.startswith(text)]
            if len(tokens) == 4 and tokens[1] in {"deploy", "deploy!"}:
                return [s for s in sectors if s.startswith(text)] + [c for c in contacts if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "move":
                return [s for s in sectors if s.startswith(text)] + [c for c in contacts if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "salvage":
                return [c for c in ["scrap", "module", "modules"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "salvage":
                return [d for d in drones if d.startswith(text)]
            if len(tokens) == 5 and tokens[1] == "salvage":
                return [c for c in contacts if c.startswith(text)]
        if cmd == "salvage":
            if len(tokens) == 2:
                return [c for c in ["scrap", "module", "modules"] if c.startswith(text)]
            if len(tokens) == 3:
                return [d for d in drones if d.startswith(text)]
            if len(tokens) == 4:
                return [c for c in contacts if c.startswith(text)]
        if cmd == "config":
            if len(tokens) == 2:
                return [c for c in ["set", "show"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "set":
                return [c for c in ["lang"] if c.startswith(text)]
            if len(tokens) == 4 and tokens[1] == "set" and tokens[2] == "lang":
                return [c for c in ["en", "es"] if c.startswith(text)]
        if cmd == "mail":
            if len(tokens) == 2:
                return [c for c in ["inbox", "read"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "read":
                return [c for c in ["latest"] if c.startswith(text)]
        if cmd == "intel":
            if len(tokens) == 2:
                return [c for c in ["import"] if c.startswith(text)]
            if len(tokens) == 3 and tokens[1] == "import":
                path_text = token or text
                if "/" in path_text:
                    dir_part, base_part = path_text.rsplit("/", 1)
                    dir_path = normalize_path(dir_part or "/")
                    prefix = base_part
                else:
                    dir_path = "/"
                    prefix = path_text
                try:
                    entries = list_dir(state.os.fs, dir_path, state.os.access_level)
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

    def _log_line(self, line: str) -> None:
        if not line:
            return
        self.query_one("#log", RichLog).write(line)

    def _log_lines(self, lines: list[str]) -> None:
        for line in lines:
            self._log_line(line)

    def _set_log_content(self, widget: RichLog, lines: list[str], preserve_scroll: bool = False, follow_end: bool = False) -> None:
        scroll_y = widget.scroll_y if preserve_scroll else None
        prev_auto = widget.auto_scroll
        if preserve_scroll:
            widget.auto_scroll = False
        widget.clear()
        for line in lines:
            widget.write(line)
        if follow_end:
            widget.scroll_end(animate=False)
        elif preserve_scroll and scroll_y is not None:
            widget.scroll_y = min(scroll_y, widget.max_scroll_y)
        if preserve_scroll:
            widget.auto_scroll = prev_auto

    def refresh_panels(self) -> None:
        with self.loop.with_lock() as state:
            header = presenter.build_header(state)
            status_lines = presenter.build_status_lines(state)
            alerts_lines = presenter.build_alerts_lines(state)
            jobs_lines = presenter.build_jobs_lines(state)
            power_lines = presenter.build_power_lines(state)
        self.query_one("#header", Static).update(header)
        status_widget = self.query_one("#status", RichLog)
        self._set_log_content(
            status_widget,
            status_lines,
            preserve_scroll=True,
            follow_end=False,
        )
        alerts_widget = self.query_one("#alerts", RichLog)
        jobs_widget = self.query_one("#jobs", RichLog)
        self._set_log_content(
            alerts_widget,
            alerts_lines,
            preserve_scroll=(self.focused is alerts_widget),
            follow_end=(self.focused is not alerts_widget),
        )
        self._set_log_content(
            jobs_widget,
            jobs_lines,
            preserve_scroll=(self.focused is jobs_widget),
            follow_end=(self.focused is not jobs_widget),
        )
        self.query_one("#power", Static).update("\n".join(power_lines))
        auto_events = self.loop.drain_events()
        if auto_events:
            with self.loop.with_lock() as state:
                lines = presenter.format_event_lines(state, auto_events)
            self._log_lines(lines)

    def _drain_auto_to_log(self) -> None:
        auto_events = self.loop.drain_events()
        if not auto_events:
            return
        with self.loop.with_lock() as state:
            lines = presenter.format_event_lines(state, auto_events)
        self._log_lines(lines)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if not self._history or self._history[-1] != text:
            self._history.append(text)
        self._history_index = len(self._history)
        self._history_current = ""
        self._log_line(f"> {text}")
        try:
            parsed = parse_command(text)
        except ParseError as e:
            self._log_line(f"[ERROR] {e.message}")
            return
        if parsed is None:
            return
        if parsed == "EXIT":
            self.exit()
            return
        if parsed == "HELP":
            self.action_help()
            return

        # Informational commands (drain AUTO first to avoid mixing)
        info_tokens = {
            "CONTACTS",
            "SCAN",
            "JOBS",
            "ALERTS",
            "LOGS",
            "INVENTORY",
            "MODULES",
            "SECTORS",
            "DRONE_STATUS",
            "POWER_STATUS",
            "CONFIG_SHOW",
        }
        if (isinstance(parsed, str) and parsed in info_tokens) or (
            isinstance(parsed, tuple) and parsed[0] in {"LS", "CAT", "ABOUT", "MAN", "LOCATE", "ALERTS_EXPLAIN", "MAIL_LIST", "MAIL_READ"}
        ):
            self._drain_auto_to_log()

        if parsed == "CONTACTS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_contacts, state))
            return
        if parsed == "SCAN":
            with self.loop.with_lock() as state:
                seen, discovered = repl._scan_and_discover(state)
                self._log_lines(presenter.build_command_output(repl.render_scan_results, state, seen))
                if discovered:
                    self._log_line(f"(scan) new: {', '.join(sorted(discovered))}")
            return
        if parsed == "JOBS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_jobs, state))
            return
        if parsed == "ALERTS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_alerts, state))
            return
        if parsed == "LOGS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_logs, state))
            return
        if parsed == "INVENTORY":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_inventory, state))
            return
        if parsed == "MODULES":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_modules_catalog, state))
            return
        if parsed == "SECTORS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_sectors, state))
            return
        if parsed == "DRONE_STATUS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_drone_status, state))
            return
        if parsed == "POWER_STATUS":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_power_status, state))
            return
        if parsed == "CONFIG_SHOW":
            with self.loop.with_lock() as state:
                self._log_line(f"language: {state.os.locale.value}")
            return
        if isinstance(parsed, tuple) and parsed[0] == "CONFIG_SET_LANG":
            lang = parsed[1]
            with self.loop.with_lock() as state:
                state.os.locale = Locale(lang)
                self._log_line(f"Language set to {state.os.locale.value}")
            return
        if isinstance(parsed, tuple) and parsed[0] == "MAIL_LIST":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_mailbox, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "MAIL_READ":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl.render_mail_read, state, parsed[1]))
            return
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_IMPORT":
            with self.loop.with_lock() as state:
                self._log_lines(presenter.build_command_output(repl._handle_intel_import, state, parsed[1]))
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
            with self.loop.with_lock() as state:
                lines = presenter.format_event_lines(state, step_pairs)
            self._log_lines(lines)
            return

        if isinstance(parsed, Hibernate):
            # Reuse CLI hibernate logic for now.
            self._drain_auto_to_log()
            try:
                with self.loop.with_lock() as state:
                    if parsed.mode == "until_arrival":
                        if not state.ship.in_transit:
                            self._log_line("hibernate: not in transit")
                            return
                        remaining_s = max(0.0, state.ship.arrival_t - state.clock.t)
                        years = remaining_s / repl.Balance.YEAR_S if repl.Balance.YEAR_S else 0.0
                    else:
                        years = parsed.years
                lines = presenter.build_command_output(repl._run_hibernate, self.loop, years)
                self._log_lines(lines)
            except Exception as e:
                self._log_line(f"[ERROR] hibernate failed: {e}")
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
            with self.loop.with_lock() as state:
                lines = presenter.format_event_lines(state, [("cmd", e) for e in ev])
            self._log_lines(lines)
        else:
            # No immediate events; still ok.
            pass


if __name__ == "__main__":
    RetornoTextualApp().run()
