from __future__ import annotations

import io
import json
import math
import pickle
import re
import shutil
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import retorno.core.lore as lore_mod
from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.runtime import data_loader as data
from retorno.worldgen import generator, manifest
from retorno.worldgen.narrative import records_for


ARC_ID = "smoke_debug"
PRIMARY_ID = "smoke_primary"
SECONDARY_ID = "smoke_secondary"
PRIMARY_KEY = f"arc:{ARC_ID}:{PRIMARY_ID}"
SECONDARY_KEY = f"arc:{ARC_ID}:{SECONDARY_ID}"


def _render_diagnostics(state) -> tuple[str, str]:
    before = pickle.dumps(state)
    lore_out = io.StringIO()
    with redirect_stdout(lore_out):
        repl.render_debug_lore(state)
    assert pickle.dumps(state) == before, "render_debug_lore changed the game state"
    arcs_out = io.StringIO()
    with redirect_stdout(arcs_out):
        repl.render_debug_arcs(state)
    assert pickle.dumps(state) == before, "render_debug_arcs changed the game state"
    return lore_out.getvalue(), arcs_out.getvalue()


def _assert_scheduler_and_counts(state, lore_text: str, arcs_text: str) -> None:
    placements = state.world.lore_placements
    scheduler = f"scheduler: eval_seq={placements.eval_seq} "
    assert scheduler in lore_text and scheduler in arcs_text
    assert f"placements_count: {len(placements.piece_to_node)}" in lore_text
    assert f"delivered_count: {len(state.world.lore.delivered)}" in lore_text


def _arc_ids_in_diagnostic(arcs_text: str) -> set[str]:
    return set(re.findall(r"^- ([^:\n]+):$", arcs_text, flags=re.MULTILINE))


def _arc_signature(arc: dict) -> tuple:
    primary = arc.get("primary_intel") or {}
    return (arc["arc_id"], primary.get("id"), primary.get("line"),
            tuple(doc.get("id") for doc in arc.get("secondary_lore_docs", [])))


def _run_initial_diagnostic() -> None:
    installed = data.load_arcs()
    assert installed, "The installed catalog is expected to include its active arcs"
    state = create_initial_state_sandbox()
    snapshot_arcs = records_for(state, "arcs", data.load_arcs)
    assert {_arc_signature(arc) for arc in snapshot_arcs} == {
        _arc_signature(arc) for arc in installed
    }
    installed_ids = {arc["arc_id"] for arc in installed}
    assert len(installed_ids) == len(installed)
    installed_keys = {entry["piece_key"] for entry in lore_mod.list_lore_piece_entries()
                      if entry["arc_id"] in installed_ids}
    snapshot_keys = {entry["piece_key"] for entry in lore_mod._iter_all_pieces(state)
                     if entry["arc_id"] in installed_ids}
    assert installed_keys == snapshot_keys
    assert not state.world.lore_placements.piece_to_node
    assert not state.world.lore.delivered

    lore_text, arcs_text = _render_diagnostics(state)
    _assert_scheduler_and_counts(state, lore_text, arcs_text)
    assert _arc_ids_in_diagnostic(arcs_text) == installed_ids
    assert arcs_text.count("  primary: (unplaced)") == sum(
        bool(arc.get("primary_intel")) for arc in installed
    )
    assert "- assigned_recent:" not in lore_text
    assert "  delivered:" not in lore_text
    assert PRIMARY_KEY not in lore_text and ARC_ID not in arcs_text
    for entry in lore_mod._iter_all_pieces(state):
        if entry["force"] and entry["piece"].get("force_policy", "none") != "none":
            assert entry["piece_key"] in lore_text


def _synthetic_arc() -> dict:
    return {
        "arc_id": ARC_ID,
        "primary_intel": {
            "id": PRIMARY_ID,
            "kind": "link",
            "line": "LINK: ECHO_7 -> ARCHIVE_01",
            "allowed_channels": ["uplink_only"],
        },
        "secondary_lore_docs": [{
            "id": SECONDARY_ID,
            "line": "Diagnostic secondary document.",
            "allowed_channels": ["ship_os_mail"],
        }],
        "placement_rules": {"primary": {}, "secondary": {}},
    }


@contextmanager
def _installed_synthetic_arc():
    with TemporaryDirectory(prefix="retorno-debug-lore-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        (root / "arcs" / f"{ARC_ID}.json").write_text(
            json.dumps(_synthetic_arc()), encoding="utf-8"
        )
        with patch.object(data, "_DATA_ROOT", root):
            yield


def _run_synthetic_diagnostic() -> None:
    original_root = data._DATA_ROOT
    original_ids = {arc["arc_id"] for arc in data.load_arcs()}
    with _installed_synthetic_arc():
        state = create_initial_state_sandbox()
        snapshot_arcs = records_for(state, "arcs", data.load_arcs)
        assert _synthetic_arc() in snapshot_arcs
        assert {arc["arc_id"] for arc in snapshot_arcs} == original_ids | {ARC_ID}
        assert {entry["piece_key"] for entry in lore_mod._iter_all_pieces(state)
                if entry["arc_id"] == ARC_ID} == {PRIMARY_KEY, SECONDARY_KEY}
        definition = generator.universe_definition(state)
        left = manifest.resolve_operative_id(definition, "ECHO_7")
        right = manifest.resolve_operative_id(definition, "ARCHIVE_01")
        assert left is not None and right is not None
        assert left.identity.scope == right.identity.scope == definition.scope
        assert math.dist(left.position_ly, right.position_ly) <= Balance.MAX_ROUTE_HOP_LY

        lore_before, arcs_before = _render_diagnostics(state)
        _assert_scheduler_and_counts(state, lore_before, arcs_before)
        assert _arc_ids_in_diagnostic(arcs_before) == original_ids | {ARC_ID}
        assert f"- {ARC_ID}:\n  primary: (unplaced)" in arcs_before
        assert f"  secondary: {SECONDARY_ID} -> (unplaced)" in arcs_before
        assert PRIMARY_KEY not in state.world.lore_placements.piece_to_node
        assert SECONDARY_KEY not in state.world.lore.delivered

        # These are diagnostic state markers, not a simulated playable delivery.
        node_id = state.world.current_node_id
        placements = state.world.lore_placements
        placements.piece_to_node[PRIMARY_KEY] = node_id
        placements.piece_channel_bindings[PRIMARY_KEY] = "uplink_only"
        placements.piece_to_node[SECONDARY_KEY] = node_id
        placements.piece_channel_bindings[SECONDARY_KEY] = "ship_os_mail"
        placements.eval_seq = 7
        state.world.lore.delivered.add(SECONDARY_KEY)
        assert PRIMARY_KEY not in state.world.lore.delivered

        lore_text, arcs_text = _render_diagnostics(state)
        _assert_scheduler_and_counts(state, lore_text, arcs_text)
        assert "placements_count: 2" in lore_text
        assert "delivered_count: 1" in lore_text
        assert f"{PRIMARY_KEY} -> {node_id} channel=uplink_only status=pending" in lore_text
        assert f"{SECONDARY_KEY} -> {node_id} channel=ship_os_mail status=delivered" in lore_text
        assert f"  delivered: {SECONDARY_KEY}" in lore_text
        assert f"  primary: {node_id} channel=uplink_only status=assigned" in arcs_text
        assert f"  secondary: {SECONDARY_ID} -> {node_id} channel=ship_os_mail status=delivered" in arcs_text
        assert _arc_ids_in_diagnostic(arcs_text) == original_ids | {ARC_ID}
        assert state.world.lore_placements.piece_to_node == {
            PRIMARY_KEY: node_id, SECONDARY_KEY: node_id,
        }
        assert state.world.lore.delivered == {SECONDARY_KEY}

    assert data._DATA_ROOT == original_root
    assert {arc["arc_id"] for arc in data.load_arcs()} == original_ids


def main() -> None:
    _run_initial_diagnostic()
    _run_synthetic_diagnostic()
    print("DEBUG LORE/ARCS SMOKE PASSED")


if __name__ == "__main__":
    main()
