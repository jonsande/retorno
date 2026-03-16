from __future__ import annotations

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
