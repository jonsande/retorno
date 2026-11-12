from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

import retorno.core.lore as lore_mod
from retorno.runtime import data_loader as data
from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.lore import run_lore_scheduler_tick, sync_node_pools_for_known_nodes
from retorno.model.world import SpaceNode, region_for_pos
from retorno.worldgen import generator, manifest
from retorno.worldgen.narrative import ContentError


@contextmanager
def _legacy_catalog(state, *, arcs=(), singles=()):
    """Expose loader fixtures only in a scoped pre-contract scheduler scene."""
    world = state.world
    original = (world.narrative_snapshot, world.information_version,
                world.information_definition, world.radio_history_version,
                world.radio_definition)
    world.narrative_snapshot = {}
    world.information_version = "legacy-information-v0"
    world.information_definition = None
    world.radio_history_version = "legacy-radio-v0"
    world.radio_definition = None
    try:
        with patch.object(lore_mod, "load_arcs", return_value=list(arcs)), \
             patch.object(lore_mod, "load_singles", return_value=list(singles)):
            yield
    finally:
        (world.narrative_snapshot, world.information_version,
         world.information_definition, world.radio_history_version,
         world.radio_definition) = original


@contextmanager
def _non_forced_scheduler():
    with patch.object(Balance, "LORE_SCHEDULER_ENABLED", True), \
         patch.object(Balance, "LORE_NON_FORCED_INJECT_P", 1.0), \
         patch.object(Balance, "LORE_NON_FORCED_INTERVAL_YEARS", 0.0):
        yield


@contextmanager
def _installed_arc(arc):
    """Compile the synthetic hard opportunity with the historical universe."""
    with TemporaryDirectory(prefix="retorno-n1b1-lore-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        (root / "arcs" / f"{arc['arc_id']}.json").write_text(json.dumps(arc), encoding="utf-8")
        with patch.object(data, "_DATA_ROOT", root):
            yield


def _certified_host(state, piece_key):
    node_id = state.world.lore_placements.piece_to_node[piece_key]
    definition = generator.universe_definition(state)
    site = manifest.resolve_operative_id(definition, node_id)
    node = state.world.space.nodes[node_id]
    assert site is not None and site.identity.scope == definition.scope
    assert node.historical_key == site.identity.encoded
    assert node.generation_sector_id == site.generation_sector_id
    assert (node.x_ly, node.y_ly, node.z_ly) == site.position_ly
    assert node.kind == site.kind and node.region == site.region
    return node_id, node


def _add_open_receiver(state, receiver_id: str) -> None:
    current = state.world.space.nodes[state.world.current_node_id]
    state.world.space.nodes[receiver_id] = SpaceNode(
        node_id=receiver_id,
        name=f"Synthetic Receiver {receiver_id}",
        kind="station",
        radiation_rad_per_s=0.001,
        region=current.region,
        x_ly=current.x_ly + 0.25,
        y_ly=current.y_ly,
        z_ly=current.z_ly,
    )
    state.world.known_nodes.add(receiver_id)
    state.world.known_contacts.add(receiver_id)
    state.world.visited_nodes.discard(receiver_id)
    sync_node_pools_for_known_nodes(state)
    for node_id, pool in state.world.node_pools.items():
        pool.node_cleaned = node_id != receiver_id
        pool.window_open = node_id == receiver_id
    receiver_pool = state.world.node_pools.get(receiver_id)
    assert receiver_pool is not None
    assert receiver_id not in state.world.visited_nodes
    assert receiver_pool.window_open and not receiver_pool.node_cleaned


def _run_secondary_count_case() -> None:
    state = create_initial_state_sandbox()
    receiver_id = "SECONDARY_COUNT_RECEIVER"
    _add_open_receiver(state, receiver_id)

    arcs = [
        {
            "arc_id": "smoke_secondary_count",
            "primary_intel": {},
            "secondary_lore_docs": [
                {
                    "id": "doc_01",
                    "path_template": "/logs/records/smoke_doc_01.{lang}.txt",
                    "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
                    "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
                    "force": False,
                    "allowed_channels": ["salvage_data"],
                    "constraints": {},
                },
                {
                    "id": "doc_02",
                    "path_template": "/logs/records/smoke_doc_02.{lang}.txt",
                    "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
                    "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
                    "force": False,
                    "allowed_channels": ["salvage_data"],
                    "constraints": {},
                },
                {
                    "id": "doc_03",
                    "path_template": "/logs/records/smoke_doc_03.{lang}.txt",
                    "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
                    "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
                    "force": False,
                    "allowed_channels": ["salvage_data"],
                    "constraints": {},
                },
            ],
            "placement_rules": {
                "secondary": {"count": 1},
            },
        }
    ]
    with _legacy_catalog(state, arcs=arcs), _non_forced_scheduler():
        assert any(piece["piece_key"] == "arc:smoke_secondary_count:doc_01"
                   for piece in lore_mod._iter_all_pieces(state))
        run_lore_scheduler_tick(state)
    assigned = [
        key
        for key in state.world.lore_placements.piece_to_node
        if key.startswith("arc:smoke_secondary_count:")
    ]
    assert len(assigned) == 1, f"Expected exactly one secondary assignment due to count=1, got {assigned}"
    assert state.world.lore_placements.piece_to_node[assigned[0]] == receiver_id, (
        "The count fixture must place on its explicit eligible receiver"
    )


def _run_single_weight_case() -> None:
    state = create_initial_state_sandbox()
    _add_open_receiver(state, "SINGLE_WEIGHT_RECEIVER")
    singles = [
        {
            "single_id": "single_weight_zero",
            "weight": 0.0,
            "channels": ["captured_signal"],
            "constraints": {},
            "files": [
                {
                    "path_template": "/logs/signals/single_weight_zero.{lang}.txt",
                    "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
                    "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
                }
            ],
        },
        {
            "single_id": "single_weight_one",
            "weight": 1.0,
            "channels": ["captured_signal"],
            "constraints": {},
            "files": [
                {
                    "path_template": "/logs/signals/single_weight_one.{lang}.txt",
                    "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
                    "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
                }
            ],
        },
    ]
    with _legacy_catalog(state, singles=singles), _non_forced_scheduler():
        assert {piece["piece_key"] for piece in lore_mod._iter_all_pieces(state)} == {
            "single:single_weight_zero", "single:single_weight_one"}
        run_lore_scheduler_tick(state)
    keys = set(state.world.lore_placements.piece_to_node.keys())
    assert "single:single_weight_zero" not in keys, "weight=0 single should never be assigned"
    assert "single:single_weight_one" in keys, "weight=1 single should be eligible and assigned with inject_p=1"


def _run_hard_force_case() -> None:
    arc = {
            "arc_id": "smoke_hard_force",
            "primary_intel": {
                "id": "hard_primary",
                "kind": "link",
                "line": "LINK: ECHO_7 -> SMOKE_TARGET",
                "force": True,
                "force_policy": "hard",
                "allowed_channels": ["salvage_data"],
                "constraints": {},
            },
            "secondary_lore_docs": [],
            "placement_rules": {
                "primary": {
                    "candidates": ["procedural_station"],
                    "require_kind_any": ["station"],
                    "avoid_node_ids": [],
                }
            },
        }
    with _installed_arc(arc):
        state = create_initial_state_sandbox()
        piece_key = "arc:smoke_hard_force:hard_primary"
        assert arc in state.world.narrative_snapshot["arcs"]
        reservation = state.world.narrative_snapshot["reservations"][piece_key]
        assert reservation["node_id"] not in state.world.space.nodes
        run_lore_scheduler_tick(state)
        assert piece_key in state.world.lore_placements.piece_to_node
        node_id, _ = _certified_host(state, piece_key)
        assert node_id == reservation["node_id"]
        assert state.world.space.nodes[node_id].historical_key == reservation["historical_key"]
        assert node_id in state.world.forced_hidden_nodes
        assert node_id not in state.world.known_nodes | state.world.known_contacts


def _run_hard_force_constraints_and_no_relax_case() -> None:
    arc = {
        "arc_id": "smoke_hard_force_strict",
        "primary_intel": {
            "id": "hard_strict_primary",
            "kind": "link",
            "line": "LINK: ECHO_7 -> STRICT_TARGET",
            "force": True,
            "force_policy": "hard",
            "allowed_channels": ["salvage_data"],
            "constraints": {
                "min_dist_ly": 20.0,
                "max_dist_ly": 22.0,
                "regions_any": ["disk"],
            },
        },
        "secondary_lore_docs": [],
        "placement_rules": {
            "primary": {
                "candidates": ["procedural_station"],
                "require_kind_any": ["station"],
            }
        },
    }
    with _installed_arc(arc):
        state = create_initial_state_sandbox()
        start_node = state.world.space.nodes["UNKNOWN"]
        assert (start_node.x_ly, start_node.y_ly, start_node.z_ly) == (0.0, 0.0, 0.0)
        piece_key = "arc:smoke_hard_force_strict:hard_strict_primary"
        reservation = state.world.narrative_snapshot["reservations"][piece_key]
        assert reservation["node_id"] not in state.world.space.nodes
        run_lore_scheduler_tick(state)
        node_id, node = _certified_host(state, piece_key)
        assert node_id == reservation["node_id"]
        assert node.historical_key == reservation["historical_key"]
        distance = math.dist((node.x_ly, node.y_ly, node.z_ly),
                             (start_node.x_ly, start_node.y_ly, start_node.z_ly))
        assert 20.0 <= distance <= 22.0
        assert node.kind == "station"
        assert region_for_pos(node.x_ly, node.y_ly, node.z_ly) == node.region == "disk"

    # A closed explicit list with no historical host is rejected at bootstrap.
    no_relax = {
        "arc_id": "smoke_hard_force_no_relax",
        "primary_intel": {
            "id": "hard_no_relax_primary",
            "kind": "link",
            "line": "LINK: ECHO_7 -> NO_RELAX_TARGET",
            "force": True,
            "force_policy": "hard",
            "allowed_channels": ["salvage_data"],
            "constraints": {},
        },
        "secondary_lore_docs": [],
        "placement_rules": {
            "primary": {
                "candidates": ["NON_EXISTENT_EXPLICIT_ID"],
                "require_kind_any": [],
            }
        },
    }
    with _installed_arc(no_relax):
        try:
            create_initial_state_sandbox()
        except ContentError as exc:
            assert exc.status == "unsatisfiable"
            assert "host/channels" in str(exc)
        else:
            raise AssertionError("A closed list of missing hosts was accepted")


def main() -> None:
    failures: list[str] = []
    cases = [
        ("secondary_count", _run_secondary_count_case),
        ("single_weights", _run_single_weight_case),
        ("hard_force", _run_hard_force_case),
        ("hard_force_constraints_and_no_relax", _run_hard_force_constraints_and_no_relax_case),
    ]
    for name, case in cases:
        try:
            case()
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    assert not failures, "Independent lore fixture failures:\n- " + "\n- ".join(failures)

    print("LORE SECONDARY COUNT + SINGLE WEIGHTS + HARD FORCE SMOKE PASSED")


if __name__ == "__main__":
    main()
