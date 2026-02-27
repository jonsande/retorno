from __future__ import annotations

from pathlib import Path


def load_startup_sequence_lines(locale: str) -> list[str]:
    data_root = Path(__file__).resolve().parents[3] / "data"
    base_dir = data_root / "lore" / "startup"
    locale = (locale or "en").lower()
    candidates = [
        base_dir / f"startup_sequence.{locale}.txt",
        base_dir / "startup_sequence.en.txt",
        base_dir / "startup_sequence.es.txt",
    ]
    for path in candidates:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
    return []
