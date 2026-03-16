from __future__ import annotations

import os
import re
from dataclasses import dataclass

from rich.text import Text


DEFAULT_THEME_PRESET = "linux"


@dataclass(slots=True, frozen=True)
class ThemePalette:
    name: str
    background: str
    panel_background: str
    foreground: str
    muted: str
    accent: str
    info: str
    warn: str
    error: str
    critical: str
    ok: str
    prompt: str
    header_background: str
    header_foreground: str
    power_background: str
    power_foreground: str
    scrollbar: str


_PALETTES: dict[str, ThemePalette] = {
    "linux": ThemePalette(
        name="linux",
        background="#10110c",
        panel_background="#15110f",
        foreground="#d7e3d8",
        muted="#7f9184",
        accent="#7bd389",
        info="#6bc7ff",
        warn="#f0c674",
        error="#ff7a7a",
        critical="#ff4d4d",
        ok="#7bd389",
        prompt="#6ee7d2",
        #header_background="#13201b",
        header_background="#13201b",
        header_foreground="#eef6ee",
        #power_background="#13201b",
        power_background="#13201b",
        power_foreground="#eef6ee",
        scrollbar="#4e6355",
    ),
    "amber": ThemePalette(
        name="amber",
        background="#151008",
        panel_background="#1a130a",
        foreground="#f3dfb3",
        muted="#aa8f63",
        accent="#ffc06b",
        info="#ffd79c",
        warn="#ffbf5f",
        error="#ff8c69",
        critical="#ff5b4d",
        ok="#ffd17d",
        prompt="#ffd17d",
        header_background="#2a1c0c",
        header_foreground="#fff4da",
        power_background="#2a1c0c",
        power_foreground="#fff4da",
        scrollbar="#7a5e39",
    ),
    "green": ThemePalette(
        name="green",
        background="#071009",
        panel_background="#0a140d",
        foreground="#a8f4b0",
        muted="#5f9365",
        accent="#59e36b",
        info="#77d9bf",
        warn="#d5f06f",
        error="#ff857a",
        critical="#ff5252",
        ok="#59e36b",
        prompt="#7af0b0",
        header_background="#0f2113",
        header_foreground="#e9fff0",
        power_background="#0f2113",
        power_foreground="#e9fff0",
        scrollbar="#3b6841",
    ),
    "ice": ThemePalette(
        name="ice",
        background="#091119",
        panel_background="#0d1721",
        foreground="#d7e2eb",
        muted="#8497aa",
        accent="#89b7d8",
        info="#76cfff",
        warn="#f2ca6b",
        error="#ff8f8f",
        critical="#ff6464",
        ok="#8fd3aa",
        prompt="#98d8ff",
        header_background="#12202b",
        header_foreground="#f3f8fc",
        power_background="#12202b",
        power_foreground="#f3f8fc",
        scrollbar="#53687c",
    ),
}


_TAG_STYLES = {
    "INFO": "info",
    "WARN": "warn",
    "ERROR": "error",
    "DEBUG": "muted",
    "AUTO": "accent",
    "OK": "ok",
    "CRITICAL": "critical",
}

_WORD_STYLES = {
    "offline": "error",
    "critical": "critical",
    "limited": "warn",
    "damaged": "warn",
    "nominal": "ok",
    "upgraded": "ok",
    "on": "ok",
    "true": "ok",
    "off": "muted",
    "false": "muted",
}

_ORIGIN_TAG_RE = re.compile(r"\[(cmd|auto|step|scan|nav|log)\]", re.IGNORECASE)
_LEVEL_TAG_RE = re.compile(r"\[(INFO|WARN|ERROR|DEBUG|AUTO|OK|CRITICAL)\]")
_LEVEL_WORD_RE = re.compile(r"\b(INFO|WARN|ERROR|DEBUG|OK|CRITICAL)\b")
_STATE_WORD_RE = re.compile(
    r"\b(offline|critical|limited|damaged|nominal|upgraded|on|off|true|false)\b",
    re.IGNORECASE,
)
_KEY_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*=)")
_PATH_RE = re.compile(r"(?<!\w)(/(?:[A-Za-z0-9._-]+/?)+)")
_QUOTED_RE = re.compile(r"'[^']+'")
_TIP_RE = re.compile(r"^(Tip:|Consejo:)")
_LABEL_RE = re.compile(r"^(\s*(?:- |\* )?)([A-Za-z_][A-Za-z0-9_ /()\-]*:)")


def theme_presets() -> tuple[str, ...]:
    return tuple(_PALETTES.keys())


def normalize_theme_preset(value: str | None) -> str:
    if not value:
        return DEFAULT_THEME_PRESET
    key = str(value).strip().lower()
    return key if key in _PALETTES else DEFAULT_THEME_PRESET


def get_theme_palette(value: str | None) -> ThemePalette:
    return _PALETTES[normalize_theme_preset(value)]


def render_rich_line(line: str, preset: str | None) -> Text:
    palette = get_theme_palette(preset)
    text = Text(line, style=palette.foreground)
    for start, end, role in _line_spans(line):
        text.stylize(_rich_style(palette, role), start, end)
    return text


def render_rich_block(lines: list[str], preset: str | None) -> Text:
    block = Text()
    for index, line in enumerate(lines):
        if index:
            block.append("\n")
        block.append(render_rich_line(line, preset))
    return block


def style_ansi_line(line: str, preset: str | None, *, enabled: bool = True) -> str:
    if not enabled or not line:
        return line
    palette = get_theme_palette(preset)
    spans = _line_spans(line)
    if not spans:
        return _ansi_open(palette.foreground) + line + _ansi_reset()

    marks: list[str | None] = [None] * len(line)
    for start, end, role in spans:
        for index in range(start, min(end, len(line))):
            marks[index] = role

    out: list[str] = []
    current: str | None = None
    chunk: list[str] = []
    for index, ch in enumerate(line):
        mark = marks[index]
        if mark != current:
            if chunk:
                out.append(_ansi_segment("".join(chunk), palette, current))
                chunk = []
            current = mark
        chunk.append(ch)
    if chunk:
        out.append(_ansi_segment("".join(chunk), palette, current))
    return "".join(out)


class ThemedStdout:
    def __init__(self, stream, get_theme_preset) -> None:
        self._stream = stream
        self._get_theme_preset = get_theme_preset
        self._pending = ""

    def write(self, s: str) -> int:
        if not s:
            return 0
        if not self._colors_enabled():
            self._stream.write(s)
            return len(s)
        if "\x1b" in s:
            self._flush_pending()
            self._stream.write(s)
            return len(s)
        if "\n" not in s:
            if len(s) == 1 and not self._pending:
                self._stream.write(s)
                return len(s)
            self._pending += s
            if self._should_emit_immediately(self._pending):
                self._emit_styled(self._pending)
                self._pending = ""
            return len(s)

        parts = s.split("\n")
        for part in parts[:-1]:
            line = self._pending + part
            self._pending = ""
            if line:
                self._emit_styled(line)
            self._stream.write("\n")
        tail = parts[-1]
        if tail:
            self._pending += tail
            if self._should_emit_immediately(self._pending):
                self._emit_styled(self._pending)
                self._pending = ""
        return len(s)

    def flush(self) -> None:
        self._flush_pending()
        self._stream.flush()

    def isatty(self) -> bool:
        try:
            return self._stream.isatty()
        except Exception:
            return False

    def fileno(self) -> int:
        return self._stream.fileno()

    @property
    def encoding(self):
        return getattr(self._stream, "encoding", None)

    def __getattr__(self, name: str):
        return getattr(self._stream, name)

    def _emit_styled(self, line: str) -> None:
        self._stream.write(style_ansi_line(line, self._get_theme_preset(), enabled=True))

    def _flush_pending(self) -> None:
        if not self._pending:
            return
        self._emit_styled(self._pending)
        self._pending = ""

    def _colors_enabled(self) -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        return self.isatty()

    @staticmethod
    def _should_emit_immediately(text: str) -> bool:
        stripped = text.lstrip("\n")
        if not stripped:
            return False
        if stripped.startswith("> "):
            return True
        if stripped.startswith("["):
            return True
        if stripped.startswith(("WARNING:", "ADVERTENCIA:", "Wake ", "¿")):
            return True
        if stripped.endswith(": "):
            return True
        if stripped.endswith("? [y/N]") or stripped.endswith("? [s/N]"):
            return True
        return False


def _line_spans(line: str) -> list[tuple[int, int, str]]:
    if not line:
        return []
    if line.lstrip().startswith("> "):
        start = line.index("> ")
        return [(start, len(line), "prompt")]
    if line.strip().startswith("===") and line.strip().endswith("==="):
        return [(0, len(line), "accent")]
    if line.startswith(("WARNING:", "ADVERTENCIA:")):
        return [(0, len(line), "warn")]

    claims = [False] * len(line)
    spans: list[tuple[int, int, str]] = []

    def claim(start: int, end: int, role: str) -> None:
        if start < 0 or end <= start or start >= len(line):
            return
        end = min(end, len(line))
        for index in range(start, end):
            if claims[index]:
                return
        for index in range(start, end):
            claims[index] = True
        spans.append((start, end, role))

    label_match = _LABEL_RE.match(line)
    if label_match:
        claim(label_match.start(2), label_match.end(2), "accent")

    tip_match = _TIP_RE.match(line)
    if tip_match:
        claim(tip_match.start(1), tip_match.end(1), "accent")

    for match in _LEVEL_TAG_RE.finditer(line):
        claim(match.start(), match.end(), _TAG_STYLES.get(match.group(1), "accent"))
    for match in _ORIGIN_TAG_RE.finditer(line):
        claim(match.start(), match.end(), "muted")
    for match in _LEVEL_WORD_RE.finditer(line):
        claim(match.start(), match.end(), _TAG_STYLES.get(match.group(1), "accent"))
    for match in _STATE_WORD_RE.finditer(line):
        role = _WORD_STYLES.get(match.group(1).lower())
        if role:
            claim(match.start(), match.end(), role)
    for match in _KEY_RE.finditer(line):
        claim(match.start(1), match.end(1), "muted")
    for match in _PATH_RE.finditer(line):
        claim(match.start(1), match.end(1), "accent")
    for match in _QUOTED_RE.finditer(line):
        claim(match.start(), match.end(), "accent")

    spans.sort(key=lambda item: item[0])
    return spans


def _rich_style(palette: ThemePalette, role: str) -> str:
    if role == "accent":
        return f"bold {palette.accent}"
    if role == "muted":
        return palette.muted
    if role == "info":
        return f"bold {palette.info}"
    if role == "warn":
        return f"bold {palette.warn}"
    if role == "error":
        return f"bold {palette.error}"
    if role == "critical":
        return f"bold {palette.critical}"
    if role == "ok":
        return f"bold {palette.ok}"
    if role == "prompt":
        return f"bold {palette.prompt}"
    return palette.foreground


def _ansi_segment(text: str, palette: ThemePalette, role: str | None) -> str:
    if not text:
        return ""
    color, bold = _ansi_style(palette, role)
    return _ansi_open(color, bold=bold) + text + _ansi_reset()


def _ansi_style(palette: ThemePalette, role: str | None) -> tuple[str, bool]:
    if role == "accent":
        return palette.accent, True
    if role == "muted":
        return palette.muted, False
    if role == "info":
        return palette.info, True
    if role == "warn":
        return palette.warn, True
    if role == "error":
        return palette.error, True
    if role == "critical":
        return palette.critical, True
    if role == "ok":
        return palette.ok, True
    if role == "prompt":
        return palette.prompt, True
    return palette.foreground, False


def _ansi_open(color: str, *, bold: bool = False) -> str:
    red, green, blue = _hex_to_rgb(color)
    prefix = "\x1b[1;" if bold else "\x1b["
    return f"{prefix}38;2;{red};{green};{blue}m"


def _ansi_reset() -> str:
    return "\x1b[0m"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
