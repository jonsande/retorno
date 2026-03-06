from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.lore import run_lore_scheduler_tick
import retorno.core.lore as lore_mod
from retorno.model.world import region_for_pos


def _run_secondary_count_case() -> None:
    state = create_initial_state_sandbox()
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
    lore_mod.load_arcs = lambda: arcs
    lore_mod.load_singles = lambda: []
    run_lore_scheduler_tick(state)
    assigned = [
        key
        for key in state.world.lore_placements.piece_to_node
        if key.startswith("arc:smoke_secondary_count:")
    ]
    assert len(assigned) == 1, f"Expected exactly one secondary assignment due to count=1, got {assigned}"


def _run_single_weight_case() -> None:
    state = create_initial_state_sandbox()
    lore_mod.load_arcs = lambda: []
    lore_mod.load_singles = lambda: [
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
    run_lore_scheduler_tick(state)
    keys = set(state.world.lore_placements.piece_to_node.keys())
    assert "single:single_weight_zero" not in keys, "weight=0 single should never be assigned"
    assert "single:single_weight_one" in keys, "weight=1 single should be eligible and assigned with inject_p=1"


def _run_hard_force_case() -> None:
    state = create_initial_state_sandbox()
    arcs = [
        {
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
    ]
    lore_mod.load_arcs = lambda: arcs
    lore_mod.load_singles = lambda: []
    run_lore_scheduler_tick(state)
    piece_key = "arc:smoke_hard_force:hard_primary"
    assert piece_key in state.world.lore_placements.piece_to_node, "hard force piece should be placed immediately"
    node_id = state.world.lore_placements.piece_to_node[piece_key]
    assert node_id in state.world.forced_hidden_nodes, "hard force fallback should use hidden ad-hoc candidate when needed"


def _run_hard_force_constraints_and_no_relax_case() -> None:
    state = create_initial_state_sandbox()
    arcs = [
        {
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
                    "regions_any": ["halo"],
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
    ]
    lore_mod.load_arcs = lambda: arcs
    lore_mod.load_singles = lambda: []
    run_lore_scheduler_tick(state)
    piece_key = "arc:smoke_hard_force_strict:hard_strict_primary"
    assert piece_key in state.world.lore_placements.piece_to_node, "strict hard piece should still place via legal ad-hoc"
    node_id = state.world.lore_placements.piece_to_node[piece_key]
    node = state.world.space.nodes.get(node_id)
    assert node is not None, "strict hard piece node should exist"
    dist = (node.x_ly * node.x_ly + node.y_ly * node.y_ly + node.z_ly * node.z_ly) ** 0.5
    assert 20.0 <= dist <= 22.0, f"ad-hoc node must respect dist constraints, got dist={dist}"
    assert region_for_pos(node.x_ly, node.y_ly, node.z_ly) == "halo", "ad-hoc node must respect region constraints"

    # No-relax guard: when only explicit non-procedural candidates are configured and no
    # candidate is available, strict ad-hoc generation must not override those rules.
    state_no_relax = create_initial_state_sandbox()
    arcs_no_relax = [
        {
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
    ]
    lore_mod.load_arcs = lambda: arcs_no_relax
    lore_mod.load_singles = lambda: []
    run_lore_scheduler_tick(state_no_relax)
    no_relax_key = "arc:smoke_hard_force_no_relax:hard_no_relax_primary"
    assert no_relax_key not in state_no_relax.world.lore_placements.piece_to_node, (
        "ad-hoc fallback should not relax explicit non-procedural candidates"
    )


def main() -> None:
    original_arcs_loader = lore_mod.load_arcs
    original_singles_loader = lore_mod.load_singles
    original_inject = Balance.LORE_NON_FORCED_INJECT_P
    original_interval = Balance.LORE_NON_FORCED_INTERVAL_YEARS
    original_scheduler = Balance.LORE_SCHEDULER_ENABLED
    try:
        Balance.LORE_SCHEDULER_ENABLED = True
        Balance.LORE_NON_FORCED_INJECT_P = 1.0
        Balance.LORE_NON_FORCED_INTERVAL_YEARS = 0.0
        _run_secondary_count_case()
        _run_single_weight_case()
        _run_hard_force_case()
        _run_hard_force_constraints_and_no_relax_case()
    finally:
        lore_mod.load_arcs = original_arcs_loader
        lore_mod.load_singles = original_singles_loader
        Balance.LORE_NON_FORCED_INJECT_P = original_inject
        Balance.LORE_NON_FORCED_INTERVAL_YEARS = original_interval
        Balance.LORE_SCHEDULER_ENABLED = original_scheduler

    print("LORE SECONDARY COUNT + SINGLE WEIGHTS + HARD FORCE SMOKE PASSED")


if __name__ == "__main__":
    main()
