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
        raw = json.load(fh)
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict] = {}
    for module_id, info in raw.items():
        if not isinstance(info, dict):
            continue
        item = dict(info)
        scope = str(item.get("scope", "ship")).strip().lower() or "ship"
        if scope not in {"ship", "drone"}:
            scope = "ship"
        item["scope"] = scope
        if scope == "drone":
            slot_cost = int(item.get("slot_cost", 1) or 1)
            item["slot_cost"] = max(1, slot_cost)
            if "drone_effects" not in item and isinstance(item.get("effects"), dict):
                item["drone_effects"] = dict(item.get("effects", {}))
        normalized[module_id] = item
    return normalized


def load_locations() -> list[dict]:
    path = _DATA_ROOT / "locations"
    if not path.exists():
        return []
    locations: list[dict] = []
    for file in sorted(path.glob("*.json")):
        with file.open("r", encoding="utf-8") as fh:
            locations.append(json.load(fh))
    for loc in locations:
        files = loc.get("fs_files") or []
        for entry in files:
            content_ref = entry.get("content_ref")
            if content_ref and "content" not in entry:
                ref_path = _DATA_ROOT / content_ref
                try:
                    entry["content"] = ref_path.read_text(encoding="utf-8")
                except Exception:
                    entry["content"] = ""
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


def load_worldgen_archetypes() -> dict[str, dict]:
    path = _DATA_ROOT / "worldgen" / "archetypes"
    if not path.exists():
        return {}
    archetypes: dict[str, dict] = {}
    for file in sorted(path.glob("*.json")):
        with file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        archetype = str(data.get("archetype", "") or "").strip()
        if archetype:
            archetypes[archetype] = data
    return archetypes



def load_arcs() -> list[dict]:
    path = _DATA_ROOT / "arcs"
    if not path.exists():
        return []
    arcs: list[dict] = []
    for file in sorted(path.glob("*.json")):
        with file.open("r", encoding="utf-8") as fh:
            arcs.append(json.load(fh))
    return arcs


def load_singles() -> list[dict]:
    path = _DATA_ROOT / "lore" / "singles" / "index.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    return []
