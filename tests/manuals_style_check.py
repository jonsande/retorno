from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANUALS = ROOT / "data" / "manuals"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _check_pairing() -> list[str]:
    errors: list[str] = []
    for folder in (MANUALS / "commands", MANUALS / "systems", MANUALS / "concepts", MANUALS / "alerts", MANUALS / "modules"):
        en = sorted(folder.glob("*.en.txt"))
        es = sorted(folder.glob("*.es.txt"))
        en_stems = {p.name[:-7] for p in en}  # remove .en.txt
        es_stems = {p.name[:-7] for p in es}  # remove .es.txt
        missing_es = sorted(en_stems - es_stems)
        missing_en = sorted(es_stems - en_stems)
        for stem in missing_es:
            errors.append(f"{folder}: missing ES pair for {stem}.en.txt")
        for stem in missing_en:
            errors.append(f"{folder}: missing EN pair for {stem}.es.txt")
    return errors


def _check_banned_markers() -> list[str]:
    errors: list[str] = []
    for path in MANUALS.rglob("*.txt"):
        text = _read(path)
        # Detect explicit TODO markers, not normal Spanish word "todo".
        if re.search(r"(?m)(^|\s)\[?TODO[\]:\s]", text):
            errors.append(f"{path}: contains TODO marker")
        if "(mvp)" in text.lower():
            errors.append(f"{path}: contains MVP marker")
    return errors


def _check_systems() -> list[str]:
    errors: list[str] = []
    for path in (MANUALS / "systems").glob("*.txt"):
        text = _read(path)
        first = text.splitlines()[0] if text.splitlines() else ""
        if not (first.startswith("SYSTEM SUMMARY —") or first.startswith("RESUMEN DE SISTEMA —")):
            errors.append(f"{path}: first line must start with SYSTEM/RESUMEN DE SISTEMA")
        if not _has_any(text, ("Function", "Función")):
            errors.append(f"{path}: missing Function/Función section")
        if not _has_any(
            text,
            (
                "Command impact by state",
                "Impacto en comandos por estado",
                "Impacto por estado",
                "Output profile by state",
                "Impacto en la salida (por estado)",
            ),
        ):
            errors.append(f"{path}: missing state-impact section")
        if not _has_any(text, ("Related commands", "Comandos relacionados")):
            errors.append(f"{path}: missing related-commands section")
    return errors


def _check_alerts() -> list[str]:
    errors: list[str] = []
    for path in (MANUALS / "alerts").glob("*.txt"):
        text = _read(path)
        first = text.splitlines()[0] if text.splitlines() else ""
        if not (first.startswith("ALERT —") or first.startswith("ALERTA —")):
            errors.append(f"{path}: first line must start with ALERT/ALERTA")
        if not _has_any(text, ("Meaning", "Significado")):
            errors.append(f"{path}: missing Meaning/Significado section")
        if not _has_any(text, ("Immediate response", "Respuesta inmediata")):
            errors.append(f"{path}: missing Immediate response/Respuesta inmediata section")
    return errors


def _check_modules() -> list[str]:
    errors: list[str] = []
    for path in (MANUALS / "modules").glob("*.txt"):
        text = _read(path)
        first = text.splitlines()[0] if text.splitlines() else ""
        if not (first.startswith("MODULE DOSSIER —") or first.startswith("DOSSIER DE MÓDULO —")):
            errors.append(f"{path}: first line must start with MODULE/DOSSIER DE MÓDULO")
        if not _has_any(text, ("Role", "Rol")):
            errors.append(f"{path}: missing Role/Rol section")
        if not _has_any(text, ("Operational effect", "Efecto operativo")):
            errors.append(f"{path}: missing Operational effect/Efecto operativo section")
    return errors


def _check_commands() -> list[str]:
    errors: list[str] = []
    accepted_primary = (
        "Purpose",
        "Propósito",
        "Summary",
        "Resumen",
        "Description",
        "Descripción",
        "Command status",
        "Estado del comando",
    )
    accepted_related = ("Related commands", "Comandos relacionados", "Related")
    for path in (MANUALS / "commands").glob("*.txt"):
        text = _read(path)
        if not _has_any(text, accepted_primary):
            errors.append(f"{path}: missing primary section (Purpose/Summary/Command status)")
        if not _has_any(text, accepted_related):
            errors.append(f"{path}: missing related section")
    return errors


def _check_concepts() -> list[str]:
    errors: list[str] = []
    for path in (MANUALS / "concepts").glob("*.txt"):
        text = _read(path)
        first = text.splitlines()[0] if text.splitlines() else ""
        if not first.startswith("SHIP OS —"):
            errors.append(f"{path}: first line should start with 'SHIP OS —'")
    return errors


def main() -> int:
    checks = [
        _check_pairing,
        _check_banned_markers,
        _check_systems,
        _check_alerts,
        _check_modules,
        _check_commands,
        _check_concepts,
    ]
    errors: list[str] = []
    for check in checks:
        errors.extend(check())

    if errors:
        print("MANUAL STYLE CHECK FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("MANUAL STYLE CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
