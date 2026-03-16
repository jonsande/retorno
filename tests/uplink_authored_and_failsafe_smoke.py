from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core import lore as lore_module
from retorno.core.lore import sync_node_pools_for_known_nodes
from retorno.model.world import ExplorationRecoveryState, SpaceNode


def _assert_current_anchor_node_seeds_pool() -> None:
    state = create_initial_state_sandbox()
    assert "ECHO_7" not in state.world.known_nodes
    assert "ECHO_7" not in state.world.known_contacts

    sync_node_pools_for_known_nodes(state)

    pool = state.world.node_pools.get("ECHO_7")
    assert pool is not None, "Expected current anchor node to seed a node pool"
    assert {entry.get("path") for entry in pool.base_files} >= {
        "/logs/echo_cache.en.txt",
        "/logs/echo_cache.es.txt",
    }, f"Expected authored ECHO_7 files in pool, got: {pool.base_files!r}"
    assert pool.uplink_route_pool, "Expected ECHO_7 uplink pool to be precomputed for current anchor node"
    assert "UNKNOWN" not in pool.uplink_route_pool, (
        f"Expected hidden origin placeholder excluded from uplink pool, got: {pool.uplink_route_pool!r}"
    )


def _assert_authored_uplink_table_is_applied() -> None:
    state = create_initial_state_sandbox()
    node_id = "AUTH_HUB_TEST"
    authored_candidates = {"AUTH_RELAY_A", "AUTH_STATION_B"}
    state.world.space.nodes[node_id] = SpaceNode(
        node_id=node_id,
        name="Authored Hub Test",
        kind="station",
        region="disk",
        x_ly=40.0,
        y_ly=10.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    state.world.space.nodes["AUTH_RELAY_A"] = SpaceNode(
        node_id="AUTH_RELAY_A",
        name="Authored Relay A",
        kind="relay",
        region="disk",
        x_ly=42.0,
        y_ly=10.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    state.world.space.nodes["AUTH_STATION_B"] = SpaceNode(
        node_id="AUTH_STATION_B",
        name="Authored Station B",
        kind="station",
        region="disk",
        x_ly=44.0,
        y_ly=10.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    state.world.known_nodes.update({node_id, "AUTH_RELAY_A", "AUTH_STATION_B"})
    state.world.known_contacts.update({node_id, "AUTH_RELAY_A", "AUTH_STATION_B"})

    original_load_locations = lore_module.load_locations
    lore_module.load_locations = lambda: [
        {
            "node": {"node_id": node_id, "kind": "station"},
            "uplink_table": {
                "min_authored": 1,
                "max_authored": 2,
                "authored_candidates": [
                    {"node_id": "AUTH_RELAY_A", "weight": 5},
                    {"node_id": "AUTH_STATION_B", "weight": 3},
                ],
            },
        },
        {"node": {"node_id": "AUTH_RELAY_A", "kind": "relay"}},
        {"node": {"node_id": "AUTH_STATION_B", "kind": "station"}},
    ]
    try:
        sync_node_pools_for_known_nodes(state)
    finally:
        lore_module.load_locations = original_load_locations

    pool = state.world.node_pools.get(node_id)
    assert pool is not None, "Expected node pool for authored uplink test"
    assert any(dest in authored_candidates for dest in pool.uplink_route_pool), (
        f"Expected at least one authored uplink route in synthetic authored pool, got: {pool.uplink_route_pool}"
    )


def _reset_to_single_anchor_state() -> tuple[object, str]:
    state = create_initial_state_sandbox()
    current_id = "FAILSAFE_CURRENT_TEST"
    current = SpaceNode(
        node_id=current_id,
        name="Failsafe Current Test",
        kind="station",
        region="disk",
        x_ly=200.0,
        y_ly=200.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    state.world.space.nodes = {current_id: current}
    state.world.current_node_id = current_id
    state.ship.current_node_id = current_id
    state.world.current_pos_ly = (current.x_ly, current.y_ly, current.z_ly)
    state.ship.docked_node_id = current_id
    state.world.known_nodes = {current_id}
    state.world.known_contacts = {current_id}
    state.world.known_intel = {}
    state.world.known_links = {current_id: set()}
    state.world.visited_nodes = {current_id}
    state.world.forced_hidden_nodes = set()
    state.world.generated_sectors = set()
    state.world.sector_states = {}
    state.world.intersector_link_pairs = set()
    state.world.node_pools = {}
    state.world.dead_nodes = {}
    state.world.exploration_recovery = ExplorationRecoveryState()
    state.world.mobility_hints = []
    state.world.mobility_failsafe_count = 0
    state.world.mobility_no_new_uplink_count = 0
    sync_node_pools_for_known_nodes(state)
    return state, current_id


def _assert_uplink_activates_diegetic_recovery() -> None:
    state, current_id = _reset_to_single_anchor_state()

    pool = state.world.node_pools.get(current_id)
    assert pool is not None, "Expected node pool at current node"
    pool.base_files = []
    pool.injected_files = []
    pool.pending_push_piece_ids.clear()
    pool.uplink_route_pool = []
    pool.uplink_data_consumed = False
    pool.data_complete = True
    pool.extras_complete = True
    pool.node_cleaned = True

    state.world.mobility_no_new_uplink_count = max(0, int(Balance.UPLINK_FAILSAFE_N) - 1)
    before_failsafe = int(state.world.mobility_failsafe_count)
    before_uplink_count = int(state.world.lore.counters.get("uplink_count", 0))

    out = io.StringIO()
    with redirect_stdout(out):
        repl._handle_uplink(state)
    text = out.getvalue().lower()

    recovery = state.world.exploration_recovery
    assert state.world.known_links.get(current_id, set()) == set(), (
        "Uplink rescue must not inject a known_link directly into the reachable graph"
    )
    assert recovery.entry_node_id, "Expected a recovery entry node after empty uplink fallback"
    assert recovery.gateway_node_id, "Expected a recovery gateway node after empty uplink fallback"
    assert recovery.entry_node_id in state.world.forced_hidden_nodes, "Recovery entry must remain hidden until discovered"
    assert recovery.passive_hint_channel == "uplink_trace", recovery.passive_hint_channel
    assert recovery.passive_hint_path in state.os.fs, "Expected passive recovery hint to be written to local FS"
    assert recovery.passive_hint_path.startswith("/logs/nav/"), recovery.passive_hint_path
    entry_pool = state.world.node_pools.get(recovery.entry_node_id)
    assert entry_pool is not None, "Expected recovery entry node pool"
    assert any(
        str(recovery.gateway_node_id) in str(entry.get("content", ""))
        for entry in entry_pool.injected_files
    ), "Expected salvageable gateway hint in recovery entry node pool"
    assert int(state.world.mobility_failsafe_count) == before_failsafe + 1, (
        "Expected mobility_failsafe_count to increment after diegetic rescue activation"
    )
    assert int(state.world.mobility_no_new_uplink_count) == 0, (
        "Expected mobility_no_new_uplink_count reset after diegetic rescue activation"
    )
    assert int(state.world.lore.counters.get("uplink_count", 0)) == before_uplink_count + 1, (
        "Expected uplink_count +1 when empty uplink activates recovery intel"
    )
    assert "no new routes found" in text or "no se encontraron rutas nuevas" in text, text


def main() -> None:
    _assert_current_anchor_node_seeds_pool()
    _assert_authored_uplink_table_is_applied()
    _assert_uplink_activates_diegetic_recovery()
    print("UPLINK AUTHORED+FAILSAFE SMOKE PASSED")


if __name__ == "__main__":
    main()
