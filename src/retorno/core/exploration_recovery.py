from __future__ import annotations

import math

from retorno.config.balance import Balance
from retorno.core.lore import (
    _pending_node_files_count,
    write_local_intel,
)
from retorno.model.events import Event, SourceRef
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, information_capabilities, is_hop_within_cap, reachable_from


def _state_rank(state: SystemState) -> int:
    order = {
        SystemState.OFFLINE: 0,
        SystemState.CRITICAL: 1,
        SystemState.DAMAGED: 2,
        SystemState.LIMITED: 3,
        SystemState.NOMINAL: 4,
        SystemState.UPGRADED: 5,
    }
    return order[state]


def is_exploration_capable(state) -> bool:
    if not bool(getattr(Balance, "EXPLORATION_RECOVERY_ENABLED", True)):
        return False
    if state.ship.in_transit or state.ship.is_hibernating:
        return False
    if state.os.terminal_lock:
        return False
    if state.ship.power.brownout:
        return False
    if state.ship.power.power_quality < float(Balance.POWER_QUALITY_BLOCK_THRESHOLD):
        return False

    current_id = state.world.current_node_id
    current = state.world.space.nodes.get(current_id)
    if not current or current.kind == "transit":
        return False

    core_os = state.ship.systems.get("core_os")
    sensors = state.ship.systems.get("sensors")
    if not core_os or _state_rank(core_os.state) < _state_rank(SystemState.NOMINAL):
        return False
    if not sensors or _state_rank(sensors.state) < _state_rank(SystemState.LIMITED):
        return False
    if not sensors.service or sensors.service.service_name != "sensord" or not sensors.service.is_running:
        return False
    return True


def _uplink_system_blocked_reason(state) -> str | None:
    if state.ship.in_transit:
        return "in_transit"
    if state.ship.power.brownout:
        return "brownout_active"
    q = state.ship.power.power_quality
    if q < Balance.POWER_QUALITY_COLLAPSE_THRESHOLD:
        return "power_quality_collapse"
    if q < Balance.POWER_QUALITY_BLOCK_THRESHOLD:
        return "power_quality_low"
    system = state.ship.systems.get("data_core")
    if not system:
        return "missing_data_core"
    if system.forced_offline and state.ship.op_mode == "CRUISE":
        return "data_core_shed"
    if system.state == SystemState.OFFLINE:
        return "data_core_offline"
    if not system.service or system.service.service_name != "datad" or not system.service.is_installed:
        return "datad_not_installed"
    if not system.service.is_running:
        return "datad_not_running"
    if _state_rank(system.state) < _state_rank(SystemState.LIMITED):
        return "data_core_degraded"
    return None


def uplink_blocked_reason(state) -> str | None:
    reason = _uplink_system_blocked_reason(state)
    if reason:
        return reason
    if state.ship.docked_node_id != state.world.current_node_id:
        return "not_docked"
    node = state.world.space.nodes.get(state.world.current_node_id)
    if not node or "uplink" not in information_capabilities(node.kind):
        return "not_relay"
    return None


def _distance_ly(left: SpaceNode, right: SpaceNode) -> float:
    dx = left.x_ly - right.x_ly
    dy = left.y_ly - right.y_ly
    dz = left.z_ly - right.z_ly
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _known_node_ids(state) -> set[str]:
    return set(getattr(state.world, "known_nodes", set()) or set()) | set(getattr(state.world, "known_contacts", set()) or set())


def _has_known_route_frontier(state, reachable: set[str]) -> bool:
    visited = set(getattr(state.world, "visited_nodes", set()) or set())
    for node_id in reachable:
        for dest_id in reachable_from(state.world, node_id):
            if dest_id not in visited:
                return True
    return False


def _has_route_solve_frontier(state, reachable: set[str]) -> bool:
    known = _known_node_ids(state)
    visited = set(getattr(state.world, "visited_nodes", set()) or set())
    nodes = state.world.space.nodes
    sensors_range = float(state.ship.sensors_range_ly)
    if sensors_range <= 0.0:
        return False

    for from_id in reachable:
        origin = nodes.get(from_id)
        if not origin:
            continue
        routes = reachable_from(state.world, from_id)
        for dest_id in known:
            if dest_id == from_id or dest_id in visited:
                continue
            if dest_id in routes:
                continue
            dest = nodes.get(dest_id)
            if not dest:
                continue
            dist = _distance_ly(origin, dest)
            if dist <= sensors_range and is_hop_within_cap(state.world, from_id, dest_id):
                return True
    return False


def _has_non_uplink_data_frontier(state, reachable: set[str]) -> bool:
    for node_id in reachable:
        pool = state.world.node_pools.get(node_id)
        if not pool:
            from retorno.core.lore import _collect_base_files_for_node
            node = state.world.space.nodes.get(node_id)
            if (node and "salvage_data" in information_capabilities(node.kind)
                    and _collect_base_files_for_node(state, node_id, node)):
                return True
            continue
        if _pending_node_files_count(state, node_id, pool) > 0:
            return True
        for piece_key in sorted(pool.pending_push_piece_ids):
            if piece_key in pool.delivered_piece_ids:
                continue
            channel = state.world.lore_placements.piece_channel_bindings.get(piece_key, "")
            if channel and channel != "uplink_only":
                return True
    return False


def _node_has_pending_uplink_payload(state, node_id: str) -> bool:
    pool = state.world.node_pools.get(node_id)
    if not pool or pool.uplink_data_consumed:
        return False
    if any(dest for dest in pool.uplink_route_pool if dest and dest != node_id):
        return True
    for piece_key in sorted(pool.pending_push_piece_ids):
        if piece_key in pool.delivered_piece_ids:
            continue
        channel = state.world.lore_placements.piece_channel_bindings.get(piece_key, "")
        if channel == "uplink_only":
            return True
    return False


def _has_uplink_frontier(state, reachable: set[str]) -> bool:
    nodes = state.world.space.nodes
    for node_id in reachable:
        node = nodes.get(node_id)
        if not node or "uplink" not in information_capabilities(node.kind):
            continue
        if node_id not in state.world.node_pools:
            from retorno.worldgen.generator import universe_definition
            from retorno.worldgen.manifest import resolve_operative_id
            if resolve_operative_id(universe_definition(state), node_id):
                return True  # An uninspected legitimate uplink remains potential.
        if _node_has_pending_uplink_payload(state, node_id):
            return True
    return False


def _is_known_or_intel(state, node_id: str | None) -> bool:
    if not node_id:
        return False
    if node_id in _known_node_ids(state):
        return True
    return node_id in (getattr(state.world, "known_intel", {}) or {})


def _has_passive_recovery_frontier(state) -> bool:
    recovery = state.world.exploration_recovery
    if recovery.passive_hint_path and recovery.passive_hint_path in state.os.fs and not _is_known_or_intel(state, recovery.entry_node_id):
        return True
    if recovery.dock_hint_path and recovery.dock_hint_path in state.os.fs and not _is_known_or_intel(state, recovery.gateway_node_id):
        return True
    return False


def _has_stored_node_frontier(state, reachable: set[str]) -> bool:
    """An unread NODE can still enable local solving; inspect without import."""
    from retorno.model.os import read_file
    from retorno.worldgen.generator import universe_definition
    from retorno.worldgen.manifest import resolve_operative_id
    definition = None
    for path, file in sorted(state.os.fs.items()):
        if file.is_corrupted:
            continue
        try:
            text = read_file(state.os.fs,path,state.os.auth_levels)
        except (PermissionError, IsADirectoryError):
            continue
        for line in text.splitlines():
            if not line.strip().upper().startswith("NODE:"):
                continue
            nid = line.split(":",1)[1].strip()
            nid = state.world.narrative_snapshot.get("aliases",{}).get(nid.casefold(),nid)
            if nid in state.world.visited_nodes:
                continue
            node = state.world.space.nodes.get(nid)
            if node:
                pos = (node.x_ly,node.y_ly,node.z_ly)
            else:
                definition = definition or universe_definition(state)
                site = resolve_operative_id(definition,nid)
                if site is None:
                    continue
                pos = site.position_ly
            for source in reachable:
                origin = state.world.space.nodes[source]
                if math.dist((origin.x_ly,origin.y_ly,origin.z_ly),pos) <= min(state.ship.sensors_range_ly,Balance.MAX_ROUTE_HOP_LY):
                    return True
    return False


def has_exploration_frontier(state) -> bool:
    from retorno.core.structural_recovery import ACTIVE, directed_access
    if any(p.status in ACTIVE for p in state.world.recovery_plans.values()):
        return True
    reachable = set(directed_access(state))
    from retorno.core.deadnode_planner import _intel_sources
    # Already recovered, readable intel is an existing opportunity too. Reuse
    # the planner's source reader; do not import it while assessing a frontier.
    for source, dest in _intel_sources(state):
        if (source in reachable and dest not in state.world.visited_nodes
                and is_hop_within_cap(state.world, source, dest)):
            return True
    if _has_stored_node_frontier(state,reachable):
        return True
    if _has_known_route_frontier(state, reachable):
        return True
    if _has_route_solve_frontier(state, reachable):
        return True
    if _has_uplink_frontier(state, reachable):
        return True
    if _has_non_uplink_data_frontier(state, reachable):
        return True
    if _has_passive_recovery_frontier(state):
        return True
    return False


def _gateway_hint_content(entry_node_id: str, gateway_node_id: str) -> str:
    return (
        "NAV NOTE\n\n"
        f"LINK: {entry_node_id} -> {gateway_node_id}\n"
    )


def _deliver_gateway_broadcast_if_needed(state) -> list[Event]:
    recovery = state.world.exploration_recovery
    if recovery.dock_hint_delivered:
        return []
    entry_node_id = recovery.entry_node_id
    gateway_node_id = recovery.gateway_node_id
    if not entry_node_id or not gateway_node_id:
        return []
    if state.world.current_node_id != entry_node_id:
        return []
    path, event = write_local_intel(
        state,
        "station_broadcast",
        _gateway_hint_content(entry_node_id, gateway_node_id),
        node_id=entry_node_id,
        source=SourceRef(kind="world", id=entry_node_id),
        opportunity_id=f"recovery:{recovery.generation}:gateway",
        trigger="arrival", delivery={"kind": "recovery_gateway", "generation": recovery.generation, "gateway": gateway_node_id},
    )
    return [event] if event is not None else []


def ensure_exploration_recovery(state, trigger: str) -> list[Event]:
    from retorno.core.structural_recovery import advance_recovery_plans, request_recovery
    from retorno.core.communications import retry_radio_opportunities
    advance_recovery_plans(state)
    events = _deliver_gateway_broadcast_if_needed(state)
    if not Balance.EXPLORATION_RECOVERY_ENABLED:
        return events
    node = state.world.space.nodes.get(state.world.current_node_id)
    if not node or node.kind == "transit":
        return events
    if has_exploration_frontier(state):
        return events + retry_radio_opportunities(state)
    request_recovery(state)
    return events + retry_radio_opportunities(state)
