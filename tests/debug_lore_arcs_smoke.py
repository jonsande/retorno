from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.core.lore import sync_node_pools_for_known_nodes


def main() -> None:
    state = create_initial_state_sandbox()
    sync_node_pools_for_known_nodes(state)

    lore_out = io.StringIO()
    with redirect_stdout(lore_out):
        repl.render_debug_lore(state)
    lore_text = lore_out.getvalue()

    # Debug lore should use canonical piece keys from scheduler model.
    assert "forced_pending_unplaced" in lore_text or "forced_pending: (none)" in lore_text, (
        f"Unexpected debug lore output: {lore_text}"
    )
    if "forced_pending_unplaced" in lore_text:
        assert "arc:carnaval_cache_01:" in lore_text or "arc:corridor_01:" in lore_text, (
            "Expected canonical arc piece_key format in forced pending output"
        )
    assert "placements_count:" in lore_text, "Debug lore should expose scheduler placements_count"

    arcs_out = io.StringIO()
    with redirect_stdout(arcs_out):
        repl.render_debug_arcs(state)
    arcs_text = arcs_out.getvalue()

    assert "primary:" in arcs_text, "Debug arcs should render primary status"
    assert "status=" in arcs_text or "(unplaced)" in arcs_text, (
        "Debug arcs should include delivery status or explicit unplaced state"
    )
    assert "scheduler: eval_seq=" in arcs_text, "Debug arcs should expose scheduler status"

    print("DEBUG LORE/ARCS SMOKE PASSED")


if __name__ == "__main__":
    main()
