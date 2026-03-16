from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.exploration_recovery import has_exploration_frontier
from retorno.core.actions import Dock, RouteSolve, Travel
from retorno.core.engine import Engine
from retorno.core.lore import sync_node_pools_for_known_nodes
from retorno.model.world import ExplorationRecoveryState, SpaceNode


def _job_eta_s(state) -> float:
    active = list(state.jobs.active_job_ids)
    assert active, "Expected an active job"
    return max(float(state.jobs.jobs[job_id].eta_s) for job_id in active)


def _make_blocked_state(*, docked: bool, node_kind: str = "derelict") -> tuple[object, str]:
    state = create_initial_state_sandbox()
    current_id = "RECOVERY_ANCHOR_TEST"
    current = SpaceNode(
        node_id=current_id,
        name="Recovery Anchor",
        kind=node_kind,
        region="disk",
        x_ly=0.0,
        y_ly=0.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    state.world.space.nodes = {current_id: current}
    state.world.current_node_id = current_id
    state.ship.current_node_id = current_id
    state.world.current_pos_ly = (0.0, 0.0, 0.0)
    state.ship.docked_node_id = current_id if docked else None
    state.ship.cruise_speed_ly_per_year = 1000.0
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
    return state, current_id


def _assert_diegetic_recovery_chain_is_consumable() -> None:
    state, current_id = _make_blocked_state(docked=False)
    engine = Engine()

    recovery_events = repl.ensure_exploration_recovery(state, "scan")
    assert recovery_events, "Expected recovery activation on blocked exploration state"

    recovery = state.world.exploration_recovery
    entry_id = recovery.entry_node_id
    gateway_id = recovery.gateway_node_id
    assert entry_id and gateway_id, "Expected both recovery entry and gateway nodes"
    assert entry_id not in state.world.known_nodes, "Recovery entry must not become known before intel import"
    assert gateway_id not in state.world.known_nodes, "Recovery gateway must stay hidden before intel import"
    assert gateway_id not in state.world.known_links.get(current_id, set()), "Gateway link must not be granted directly"
    assert recovery.passive_hint_path in state.os.fs, "Passive hint path must exist"
    entry_pool = state.world.node_pools.get(entry_id)
    assert entry_pool is not None, "Recovery entry must have a node pool"
    assert any(
        str(gateway_id) in str(entry.get("content", ""))
        for entry in entry_pool.injected_files
    ), "Recovery entry must contain salvageable intel for the gateway"

    passive_text = state.os.fs[recovery.passive_hint_path].content
    passive_msgs = repl._auto_import_intel_from_text(state, passive_text, recovery.passive_hint_path)
    assert entry_id in state.world.known_nodes, "Passive hint import must reveal recovery entry"
    assert any(entry_id in msg for msg in passive_msgs), passive_msgs

    route_events = engine.apply_action(state, RouteSolve(node_id=entry_id))
    assert route_events, "Route solve should queue after recovery entry becomes known"
    engine.tick(state, _job_eta_s(state) + 1.0)
    assert entry_id in state.world.known_links.get(current_id, set()), "Route solve must open a route to recovery entry"

    travel_events = engine.apply_action(state, Travel(node_id=entry_id))
    assert travel_events, "Travel should start once route is known"
    assert state.ship.in_transit is True, "Ship should enter transit toward recovery entry"
    engine.tick(state, max(0.0, state.ship.arrival_t - state.clock.t) + 1.0)
    assert state.ship.in_transit is False, "Ship should arrive at recovery entry"
    assert state.world.current_node_id == entry_id, "Current node must advance to recovery entry"
    assert gateway_id not in state.world.known_links.get(entry_id, set()), "Gateway must still be locked before dock intel"

    dock_events = engine.apply_action(state, Dock(node_id=entry_id))
    assert dock_events, "Dock should queue at recovery entry"
    engine.tick(state, float(Balance.DOCK_TIME_S) + 1.0)

    recovery = state.world.exploration_recovery
    assert recovery.dock_hint_delivered is True, "Docking at recovery entry must emit gateway broadcast"
    assert recovery.dock_hint_path in state.os.fs, "Gateway broadcast path must exist after docking"

    broadcast_text = state.os.fs[recovery.dock_hint_path].content
    broadcast_msgs = repl._auto_import_intel_from_text(state, broadcast_text, recovery.dock_hint_path)
    assert gateway_id in state.world.known_links.get(entry_id, set()), "Broadcast import must unlock route from entry to gateway"
    assert any(gateway_id in msg for msg in broadcast_msgs), broadcast_msgs


def _assert_hibernate_recovery_uses_mail_channel() -> None:
    state, _ = _make_blocked_state(docked=False)
    recovery_events = repl.ensure_exploration_recovery(state, "hibernate_end")
    assert recovery_events, "Expected recovery activation for hibernate-end trigger"
    recovery = state.world.exploration_recovery
    assert recovery.passive_hint_channel == "ship_os_mail", recovery.passive_hint_channel
    assert recovery.passive_hint_path is not None and recovery.passive_hint_path.startswith("/mail/inbox/"), (
        recovery.passive_hint_path
    )


def _assert_uplink_frontier_blocks_recovery_activation() -> None:
    state, current_id = _make_blocked_state(docked=True, node_kind="station")
    uplink_dest_id = "UPLINK_FRONTIER_DEST"
    state.world.space.nodes[uplink_dest_id] = SpaceNode(
        node_id=uplink_dest_id,
        name="Uplink Frontier Dest",
        kind="station",
        region="disk",
        x_ly=1.0,
        y_ly=0.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    sync_node_pools_for_known_nodes(state)
    pool = state.world.node_pools.get(current_id)
    assert pool is not None, "Expected uplink-capable pool at current node"
    pool.base_files = []
    pool.injected_files = []
    pool.pending_push_piece_ids.clear()
    pool.uplink_route_pool = [uplink_dest_id]
    pool.uplink_data_consumed = False
    pool.data_complete = True
    pool.extras_complete = True
    pool.node_cleaned = True

    assert has_exploration_frontier(state) is True, "A live uplink payload must count as a frontier"
    recovery_events = repl.ensure_exploration_recovery(state, "scan")
    assert recovery_events == [], "Recovery must stay inactive while an uplink frontier is still available"
    assert state.world.exploration_recovery.entry_node_id is None, (
        "Frontier-backed state must not spawn diegetic recovery nodes"
    )


def main() -> None:
    _assert_diegetic_recovery_chain_is_consumable()
    _assert_hibernate_recovery_uses_mail_channel()
    _assert_uplink_frontier_blocks_recovery_activation()
    print("EXPLORATION RECOVERY SMOKE PASSED")


if __name__ == "__main__":
    main()
