from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.core.lore import _spawn_ad_hoc_candidate_for_forced_piece, sync_node_pools_for_known_nodes
from retorno.model.world import SpaceNode


def main() -> None:
    state = create_initial_state_sandbox()
    host_id = "BREADCRUMB_HOST"
    current = state.world.space.nodes[state.world.current_node_id]
    state.world.space.nodes[host_id] = SpaceNode(
        node_id=host_id,
        name="Synthetic Breadcrumb Host",
        kind="station",
        radiation_rad_per_s=0.001,
        region=current.region,
        x_ly=current.x_ly + 0.25,
        y_ly=current.y_ly,
        z_ly=current.z_ly,
    )
    state.world.known_nodes.add(host_id)
    state.world.known_contacts.add(host_id)
    state.world.visited_nodes.discard(host_id)
    sync_node_pools_for_known_nodes(state)

    # Keep exactly one explicit, known, unvisited, open pool eligible for the
    # breadcrumb. Do not rely on authored locations being known in this fixture.
    for nid, pool in state.world.node_pools.items():
        pool.node_cleaned = nid != host_id
        pool.window_open = nid == host_id

    host_pool = state.world.node_pools.get(host_id)
    assert host_pool is not None, "Expected synthetic breadcrumb host pool"
    assert host_id not in state.world.visited_nodes, "Breadcrumb host must remain unvisited"
    assert host_pool.window_open and not host_pool.node_cleaned, "Breadcrumb host must be eligible"

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

    # Breadcrumb must be injected only in the explicit eligible host.
    host_hint = [f for f in host_pool.injected_files if hidden_id in str(f.get("content", ""))]
    assert len(host_hint) == 1, f"Expected exactly one breadcrumb in {host_id}, got {host_hint}"

    for nid, pool in state.world.node_pools.items():
        if nid == host_id:
            continue
        leaked = [
            entry
            for entry in pool.injected_files
            if str(entry.get("path", "")).startswith("/logs/nav/forced_hint_")
            and hidden_id in str(entry.get("content", ""))
        ]
        assert not leaked, f"Breadcrumb must not be injected outside the eligible host: {nid}"

    print("FORCED HIDDEN AD-HOC SMOKE PASSED")


if __name__ == "__main__":
    main()
