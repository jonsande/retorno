from __future__ import annotations

import sys
import termios
import tty
from pathlib import Path


def load_lore_sequence_lines(group: str, name: str, locale: str) -> list[str]:
    data_root = Path(__file__).resolve().parents[3] / "data"
    base_dir = data_root / "lore" / group
    locale = (locale or "en").lower()
    candidates = [
        base_dir / f"{name}.{locale}.txt",
        base_dir / f"{name}.en.txt",
        base_dir / f"{name}.es.txt",
    ]
    for path in candidates:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
    return []


def load_startup_sequence_lines(locale: str) -> list[str]:
    return load_lore_sequence_lines("startup", "startup_sequence", locale)


def load_hibernate_start_sequence_lines(locale: str) -> list[str]:
    return load_lore_sequence_lines("hibernate", "hibernate_start_sequence", locale)


def load_hibernate_wake_sequence_lines(locale: str, *, emergency: bool) -> list[str]:
    name = "hibernate_wake_sequence_emergency" if emergency else "hibernate_wake_sequence_normal"
    return load_lore_sequence_lines("hibernate", name, locale)


def clear_terminal_screen() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")


def _console_continue_prompt(locale: str) -> str:
    prompts = {
        "en": "Press any key to continue...",
        "es": "Pulsa una tecla para continuar...",
    }
    return prompts.get(locale, prompts["en"])


def wait_for_console_continue(locale: str) -> None:
    prompt = _console_continue_prompt(locale)
    if not sys.stdin.isatty():
        print(prompt)
        return
    fd = sys.stdin.fileno()
    old = None
    try:
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        sys.stdout.write(prompt)
        sys.stdout.flush()
        sys.stdin.read(1)
        sys.stdout.write("\n")
        sys.stdout.flush()
    except Exception:
        try:
            input(f"{prompt} ")
        except EOFError:
            print()
    finally:
        if old is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass


def run_console_entry_gate(messages: list[str], locale: str, *, clear_after: bool = False) -> None:
    visible = [msg for msg in messages if msg]
    if not visible:
        return
    for msg in visible:
        print(msg)
    wait_for_console_continue(locale)
    if clear_after:
        clear_terminal_screen()
