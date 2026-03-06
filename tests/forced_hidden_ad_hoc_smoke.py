from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.core.lore import _spawn_ad_hoc_candidate_for_forced_piece, sync_node_pools_for_known_nodes


def _all_pool_files(pool) -> list[dict]:
    return list(pool.base_files) + list(pool.injected_files)


def main() -> None:
    state = create_initial_state_sandbox()
    sync_node_pools_for_known_nodes(state)

    # Force breadcrumb target set: only HARBOR_12 remains non-clean candidate.
    for nid, pool in state.world.node_pools.items():
        pool.node_cleaned = nid != "HARBOR_12"

    piece_entry = {
        "piece_key": "arc:smoke:forced_hidden",
        "placement_rules": {
            "require_kind_any": ["station"],
            "candidates": ["procedural_station"],
        },
    }

    hidden_id = _spawn_ad_hoc_candidate_for_forced_piece(state, piece_entry)
    assert hidden_id, "Expected hidden ad-hoc node id"

    assert hidden_id in state.world.space.nodes, "Hidden node must exist in space graph"
    assert hidden_id in state.world.forced_hidden_nodes, "Hidden node must be tracked as forced hidden"
    assert hidden_id not in state.world.known_contacts, "Hidden node must NOT be auto-known contact"
    assert hidden_id not in state.world.known_nodes, "Hidden node must NOT be auto-known node"
    assert hidden_id in state.world.node_pools, "Hidden node must have node pool state"

    # Breadcrumb must be injected in known non-clean node pool, not in cleaned ones.
    harbor_pool = state.world.node_pools.get("HARBOR_12")
    assert harbor_pool is not None, "Expected HARBOR_12 pool"
    harbor_hint = [f for f in harbor_pool.injected_files if hidden_id in str(f.get("content", ""))]
    assert harbor_hint, "Expected breadcrumb hint in HARBOR_12 injected files"

    for nid, pool in state.world.node_pools.items():
        if nid == "HARBOR_12":
            continue
        if not pool.node_cleaned:
            continue
        leaked = [f for f in _all_pool_files(pool) if hidden_id in str(f.get("content", ""))]
        assert not leaked, f"Breadcrumb must not be injected into cleaned node pool: {nid}"

    print("FORCED HIDDEN AD-HOC SMOKE PASSED")


if __name__ == "__main__":
    main()
