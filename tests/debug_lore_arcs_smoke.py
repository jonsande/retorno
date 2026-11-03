from __future__ import annotations

import io
from contextlib import redirect_stdout

import retorno.core.lore as lore_mod
from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.core.lore import sync_node_pools_for_known_nodes


def main() -> None:
    state = create_initial_state_sandbox()
    sync_node_pools_for_known_nodes(state)

    # Template arcs are intentionally outside the active runtime data tree.
    assert lore_mod.load_arcs() == [], "Active runtime data must not load template arcs"

    lore_out = io.StringIO()
    with redirect_stdout(lore_out):
        repl.render_debug_lore(state)
    lore_text = lore_out.getvalue()

    # Debug lore should use canonical piece keys from scheduler model.
    assert "forced_pending: (none)" in lore_text, f"Unexpected debug lore output: {lore_text}"
    assert "placements_count:" in lore_text, "Debug lore should expose scheduler placements_count"
    assert "scheduler: eval_seq=" in lore_text, "Debug lore should expose scheduler status"

    arcs_out = io.StringIO()
    with redirect_stdout(arcs_out):
        repl.render_debug_arcs(state)
    arcs_text = arcs_out.getvalue()

    assert "(none)" in arcs_text, "Debug arcs should report the empty active arc set"
    assert "primary:" not in arcs_text, "Empty active arc data must not fabricate a primary"

    synthetic_arcs = [
        {
            "arc_id": "smoke_debug",
            "primary_intel": {
                "id": "smoke_primary",
                "kind": "link",
                "line": "LINK: DEBUG_LEFT -> DEBUG_RIGHT",
                "force": True,
                "force_policy": "hard",
                "allowed_channels": ["captured_signal"],
                "constraints": {},
            },
            "secondary_lore_docs": [],
        }
    ]
    primary_key = "arc:smoke_debug:smoke_primary"
    state.world.lore_placements.piece_to_node[primary_key] = state.world.current_node_id
    state.world.lore_placements.piece_channel_bindings[primary_key] = "captured_signal"
    state.world.lore.delivered.add(primary_key)

    original_repl_loader = repl.load_arcs
    original_lore_loader = lore_mod.load_arcs
    try:
        repl.load_arcs = lambda: synthetic_arcs
        lore_mod.load_arcs = lambda: synthetic_arcs

        synthetic_arcs_out = io.StringIO()
        with redirect_stdout(synthetic_arcs_out):
            repl.render_debug_arcs(state)
        synthetic_arcs_text = synthetic_arcs_out.getvalue()
        assert "primary:" in synthetic_arcs_text, "Synthetic arc should render primary status"
        assert "status=delivered" in synthetic_arcs_text, synthetic_arcs_text
        assert "scheduler: eval_seq=" in synthetic_arcs_text, synthetic_arcs_text

        synthetic_lore_out = io.StringIO()
        with redirect_stdout(synthetic_lore_out):
            repl.render_debug_lore(state)
        synthetic_lore_text = synthetic_lore_out.getvalue()
        assert primary_key in synthetic_lore_text, "Debug lore must use the canonical arc piece key"
    finally:
        repl.load_arcs = original_repl_loader
        lore_mod.load_arcs = original_lore_loader

    print("DEBUG LORE/ARCS SMOKE PASSED")


if __name__ == "__main__":
    main()
