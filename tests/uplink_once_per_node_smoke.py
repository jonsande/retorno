from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.core.lore import sync_node_pools_for_known_nodes
from retorno.model.world import SpaceNode


def _uplink_logs(fs: dict) -> list[str]:
    return sorted(
        path for path in fs.keys() if path.startswith("/logs/nav/uplink_") and path.endswith(".txt")
    )


def main() -> None:
    state = create_initial_state_sandbox()
    state.ship.docked_node_id = state.world.current_node_id
    sync_node_pools_for_known_nodes(state)

    node_id = state.world.current_node_id
    frozen_pool = list(state.world.node_pools.get(node_id).uplink_route_pool)

    # Add a brand-new candidate *after* first contact; strict mode must ignore it.
    late_node_id = "LATE_HUB_TEST"
    state.world.space.nodes[late_node_id] = SpaceNode(
        node_id=late_node_id,
        name="Late Hub Test",
        kind="station",
        region="disk",
        x_ly=0.15,
        y_ly=0.10,
        z_ly=0.0,
    )
    assert late_node_id not in frozen_pool, "Late node must not be part of frozen uplink pool"

    before_count = int(state.world.lore.counters.get("uplink_count", 0))
    before_routes = len(state.world.known_links.get(node_id, set()))
    before_logs = _uplink_logs(state.os.fs)

    out1 = io.StringIO()
    with redirect_stdout(out1):
        repl._handle_uplink(state)

    after_first_count = int(state.world.lore.counters.get("uplink_count", 0))
    after_first_routes = len(state.world.known_links.get(node_id, set()))
    after_first_logs = _uplink_logs(state.os.fs)

    assert after_first_count == before_count + 1, (
        f"Expected uplink_count +1 on first successful uplink; got {before_count} -> {after_first_count}"
    )
    assert after_first_routes >= before_routes, "First uplink should not reduce known routes"
    assert len(after_first_logs) == len(before_logs) + 1, "First uplink should write exactly one nav uplink log"
    assert late_node_id not in state.world.known_links.get(node_id, set()), (
        "Strict first-contact pool should ignore nodes introduced after pool initialization"
    )

    out2 = io.StringIO()
    with redirect_stdout(out2):
        repl._handle_uplink(state)

    text2 = out2.getvalue().lower()
    after_second_count = int(state.world.lore.counters.get("uplink_count", 0))
    after_second_routes = len(state.world.known_links.get(node_id, set()))
    after_second_logs = _uplink_logs(state.os.fs)

    assert "exhaust" in text2 or "agotad" in text2, f"Expected exhausted message on second uplink, got: {text2}"
    assert after_second_count == after_first_count, "Repeated uplink on same node must not increment uplink_count"
    assert after_second_routes == after_first_routes, "Repeated uplink on same node must not add routes"
    assert after_second_logs == after_first_logs, "Repeated uplink on same node must not create extra uplink logs"

    print("UPLINK ONCE PER NODE SMOKE PASSED")


if __name__ == "__main__":
    main()
