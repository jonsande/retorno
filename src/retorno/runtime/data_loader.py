from __future__ import annotations

import json
from pathlib import Path

_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def _node_to_filename(node_id: str) -> str:
    return node_id.lower().replace("-", "_") + ".json"


def load_loot(node_id: str) -> dict:
    path = _DATA_ROOT / "loot" / _node_to_filename(node_id)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_modules() -> dict:
    path = _DATA_ROOT / "modules.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_locations() -> list[dict]:
    path = _DATA_ROOT / "locations"
    if not path.exists():
        return []
    locations: list[dict] = []
    for file in sorted(path.glob("*.json")):
        with file.open("r", encoding="utf-8") as fh:
            locations.append(json.load(fh))
    return locations


def load_worldgen_templates() -> dict[str, dict]:
    path = _DATA_ROOT / "worldgen" / "templates"
    if not path.exists():
        return {}
    templates: dict[str, dict] = {}
    for file in sorted(path.glob("*.json")):
        with file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        region = data.get("region")
        if region:
            templates[region] = data
    return templates
