from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.lore import sync_node_pools_for_known_nodes
from retorno.model.world import SpaceNode


def _assert_authored_uplink_table_is_applied() -> None:
    state = create_initial_state_sandbox()
    node_id = "HARBOR_12"
    state.world.known_nodes.add(node_id)
    state.world.known_contacts.add(node_id)
    sync_node_pools_for_known_nodes(state)

    pool = state.world.node_pools.get(node_id)
    assert pool is not None, "Expected node pool for HARBOR_12"
    authored_candidates = {"ANCORA", "MOURN_ANCHOR", "VEIL_GARDEN", "SABLE_CHAPEL", "GLASSHOLLOW"}
    assert any(dest in authored_candidates for dest in pool.uplink_route_pool), (
        f"Expected at least one authored uplink route in HARBOR_12 pool, got: {pool.uplink_route_pool}"
    )


def _assert_mobility_failsafe_reenabled() -> None:
    state = create_initial_state_sandbox()
    current_id = state.world.current_node_id
    current = state.world.space.nodes[current_id]
    state.ship.docked_node_id = current_id
    sync_node_pools_for_known_nodes(state)

    failsafe_dest = "FAILSAFE_HUB_TEST"
    state.world.space.nodes[failsafe_dest] = SpaceNode(
        node_id=failsafe_dest,
        name="Failsafe Hub Test",
        kind="station",
        region=current.region or "disk",
        x_ly=current.x_ly + 1.0,
        y_ly=current.y_ly,
        z_ly=current.z_ly,
        is_hub=True,
    )
    state.world.known_links = {current_id: set()}
    state.world.known_nodes.add(failsafe_dest)
    state.world.known_contacts.add(failsafe_dest)

    pool = state.world.node_pools.get(current_id)
    assert pool is not None, "Expected node pool at current node"
    pool.uplink_route_pool = []
    pool.uplink_data_consumed = False

    state.world.mobility_no_new_uplink_count = max(0, int(Balance.UPLINK_FAILSAFE_N) - 1)
    before_failsafe = int(state.world.mobility_failsafe_count)
    before_uplink_count = int(state.world.lore.counters.get("uplink_count", 0))

    out = io.StringIO()
    with redirect_stdout(out):
        repl._handle_uplink(state)
    text = out.getvalue().lower()

    assert failsafe_dest in state.world.known_links.get(current_id, set()), (
        "Expected mobility failsafe to inject a bridge route on empty uplink result"
    )
    assert int(state.world.mobility_failsafe_count) == before_failsafe + 1, (
        "Expected mobility_failsafe_count to increment after fallback route injection"
    )
    assert int(state.world.mobility_no_new_uplink_count) == 0, (
        "Expected mobility_no_new_uplink_count reset after fallback route injection"
    )
    assert int(state.world.lore.counters.get("uplink_count", 0)) == before_uplink_count + 1, (
        "Expected uplink_count +1 when fallback injected new route intel"
    )
    assert "routes added" in text or "rutas añadidas" in text, (
        f"Expected uplink output to report added routes after fallback, got: {text}"
    )


def main() -> None:
    _assert_authored_uplink_table_is_applied()
    _assert_mobility_failsafe_reenabled()
    print("UPLINK AUTHORED+FAILSAFE SMOKE PASSED")


if __name__ == "__main__":
    main()
