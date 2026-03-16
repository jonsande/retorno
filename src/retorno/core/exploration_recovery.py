from __future__ import annotations

import math
import random

from retorno.config.balance import Balance
from retorno.core.lore import (
    _location_node_ids,
    _pending_node_files_count,
    _stable_seed64,
    register_hidden_anchored_node,
    recompute_node_completion,
    sync_node_pools_for_known_nodes,
    write_local_intel,
)
from retorno.model.events import Event, SourceRef
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, sector_id_for_pos
from retorno.worldgen.generator import ensure_sector_generated


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
    if not system.service or system.service.service_name != "datad":
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
    if not node or node.kind not in {"relay", "station", "waystation"}:
        return "not_relay"
    return None


def _reachable_component(known_links: dict[str, set[str]], start_id: str) -> set[str]:
    visited = {start_id}
    queue = [start_id]
    while queue:
        current = queue.pop(0)
        for dest in known_links.get(current, set()):
            if dest in visited:
                continue
            visited.add(dest)
            queue.append(dest)
    return visited


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
        for dest_id in state.world.known_links.get(node_id, set()):
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
        for dest_id in known:
            if dest_id == from_id or dest_id in visited:
                continue
            if dest_id in state.world.known_links.get(from_id, set()):
                continue
            dest = nodes.get(dest_id)
            if not dest:
                continue
            dist = _distance_ly(origin, dest)
            if dist <= sensors_range and dist <= float(Balance.MAX_ROUTE_HOP_LY):
                return True
    return False


def _has_non_uplink_data_frontier(state, reachable: set[str]) -> bool:
    for node_id in reachable:
        pool = state.world.node_pools.get(node_id)
        if not pool:
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
    if _uplink_system_blocked_reason(state):
        return False
    nodes = state.world.space.nodes
    for node_id in reachable:
        node = nodes.get(node_id)
        if not node or node.kind not in {"relay", "station", "waystation"}:
            continue
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


def has_exploration_frontier(state) -> bool:
    current_id = state.world.current_node_id
    reachable = _reachable_component(state.world.known_links, current_id)
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


def _sample_anchor_offset(
    seed_key: str,
    *,
    seed: int,
    anchor: SpaceNode,
    min_dist_ly: float,
    max_dist_ly: float,
    require_new_sector: bool = False,
    attempts: int = 64,
) -> tuple[float, float, float] | None:
    if max_dist_ly < min_dist_ly or max_dist_ly <= 0.0:
        return None
    rng = random.Random(_stable_seed64(seed, "recovery_offset", seed_key, anchor.node_id))
    anchor_sector = sector_id_for_pos(anchor.x_ly, anchor.y_ly, anchor.z_ly)
    for _ in range(attempts):
        dist = rng.uniform(min_dist_ly, max_dist_ly)
        theta = rng.uniform(0.0, math.tau)
        dz = rng.uniform(-0.25, 0.25)
        planar_sq = max(0.0, dist * dist - dz * dz)
        planar = math.sqrt(planar_sq)
        x = anchor.x_ly + math.cos(theta) * planar
        y = anchor.y_ly + math.sin(theta) * planar
        z = anchor.z_ly + dz
        if require_new_sector and sector_id_for_pos(x, y, z) == anchor_sector:
            continue
        return x, y, z
    return None


def _pick_existing_gateway_candidate(state, entry_node_id: str) -> str | None:
    entry = state.world.space.nodes.get(entry_node_id)
    if not entry:
        return None
    authored = _location_node_ids()
    known = _known_node_ids(state)
    candidates: list[tuple[float, str]] = []
    for node in state.world.space.nodes.values():
        if node.node_id in {entry_node_id, state.world.current_node_id}:
            continue
        if not node.is_hub or node.node_id in known or node.node_id in authored:
            continue
        dist = _distance_ly(entry, node)
        if dist < float(Balance.EXPLORATION_RECOVERY_GATEWAY_MIN_DIST_LY):
            continue
        if dist > float(Balance.MAX_ROUTE_HOP_LY):
            continue
        candidates.append((dist, node.node_id))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def _drop_hidden_node(state, node_id: str) -> None:
    node = state.world.space.nodes.pop(node_id, None)
    if node is None:
        return
    for other in state.world.space.nodes.values():
        other.links.discard(node_id)
    state.world.forced_hidden_nodes.discard(node_id)
    state.world.node_pools.pop(node_id, None)
    state.world.dead_nodes.pop(node_id, None)
    state.world.known_links.pop(node_id, None)
    for links in state.world.known_links.values():
        links.discard(node_id)
    for sector_state in state.world.sector_states.values():
        if node_id in sector_state.node_ids:
            sector_state.node_ids = [existing for existing in sector_state.node_ids if existing != node_id]
        if sector_state.playable_hub_node_id == node_id:
            sector_state.playable_hub_node_id = None
        if sector_state.topology_hub_node_id == node_id:
            sector_state.topology_hub_node_id = None


def _ensure_entry_node(state, generation: int) -> str | None:
    anchor = state.world.space.nodes.get(state.world.current_node_id)
    if not anchor:
        return None
    coords = _sample_anchor_offset(
        f"entry:{generation}",
        seed=state.meta.rng_seed,
        anchor=anchor,
        min_dist_ly=float(Balance.EXPLORATION_RECOVERY_ENTRY_MIN_DIST_LY),
        max_dist_ly=min(float(Balance.EXPLORATION_RECOVERY_ENTRY_MAX_DIST_LY), float(state.ship.sensors_range_ly) * 0.85),
        require_new_sector=False,
    )
    if not coords:
        return None
    return register_hidden_anchored_node(
        state,
        seed_key=f"exploration_recovery_entry:{generation}",
        kind="station",
        anchor_node_id=anchor.node_id,
        x_ly=coords[0],
        y_ly=coords[1],
        z_ly=coords[2],
        force_hub=True,
    )


def _ensure_gateway_node(state, generation: int, entry_node_id: str) -> str | None:
    existing = _pick_existing_gateway_candidate(state, entry_node_id)
    if existing:
        return existing

    entry = state.world.space.nodes.get(entry_node_id)
    if not entry:
        return None
    coords = _sample_anchor_offset(
        f"gateway:{generation}",
        seed=state.meta.rng_seed,
        anchor=entry,
        min_dist_ly=float(Balance.EXPLORATION_RECOVERY_GATEWAY_MIN_DIST_LY),
        max_dist_ly=float(Balance.EXPLORATION_RECOVERY_GATEWAY_MAX_DIST_LY),
        require_new_sector=True,
    )
    if not coords:
        return None
    gateway_id = register_hidden_anchored_node(
        state,
        seed_key=f"exploration_recovery_gateway:{generation}",
        kind="station",
        anchor_node_id=entry.node_id,
        x_ly=coords[0],
        y_ly=coords[1],
        z_ly=coords[2],
        force_hub=True,
    )
    if not gateway_id:
        return None
    gateway = state.world.space.nodes.get(gateway_id)
    if gateway:
        ensure_sector_generated(state, sector_id_for_pos(gateway.x_ly, gateway.y_ly, gateway.z_ly))
    return gateway_id


def _entry_hint_content(state, entry_node_id: str, trigger: str) -> str:
    entry = state.world.space.nodes.get(entry_node_id)
    if not entry:
        return f"NAV NOTE\n\nNODE: {entry_node_id}\n"
    prefix = {
        "hibernate_end": "AUTONOMOUS MAIL\n\nPassive capture retained during hibernation review.",
        "dock": "STATION ADVISORY\n\nDeferred beacon replay recovered from dockside cache.",
        "uplink": "SIGNAL TRACE\n\nWeak nav echo recovered during route table maintenance.",
    }.get(trigger, "SIGNAL TRACE\n\nWeak nav echo resolved from background sweep.")
    return (
        f"{prefix}\n\n"
        f"NODE: {entry_node_id}\n"
        f"COORD: {entry.x_ly:.3f}, {entry.y_ly:.3f}, {entry.z_ly:.3f}\n"
    )


def _gateway_hint_content(entry_node_id: str, gateway_node_id: str) -> str:
    return (
        "NAV NOTE\n\n"
        f"LINK: {entry_node_id} -> {gateway_node_id}\n"
    )


def _seed_entry_salvage_hint(state, entry_node_id: str, gateway_node_id: str, generation: int) -> bool:
    pool = state.world.node_pools.get(entry_node_id)
    if not pool:
        return False
    path = f"/logs/nav/recovery_gateway_{generation:03d}.txt"
    for entry in list(pool.base_files) + list(pool.injected_files):
        if entry.get("path") == path:
            return False
    pool.injected_files.append(
        {
            "path": path,
            "access": "guest",
            "content": _gateway_hint_content(entry_node_id, gateway_node_id),
        }
    )
    recompute_node_completion(state, entry_node_id)
    return True


def _passive_channel_for_trigger(trigger: str) -> str:
    if trigger == "hibernate_end":
        return "ship_os_mail"
    if trigger == "dock":
        return "station_broadcast"
    if trigger == "uplink":
        return "uplink_trace"
    return "captured_signal"


def _activation_source(state, trigger: str) -> SourceRef:
    if trigger == "hibernate_end":
        return SourceRef(kind="ship", id=state.ship.ship_id)
    return SourceRef(kind="world", id=state.world.current_node_id)


def _activate_recovery(state, trigger: str) -> list[Event]:
    recovery = state.world.exploration_recovery
    generation = int(recovery.generation) + 1
    entry_node_id = _ensure_entry_node(state, generation)
    if not entry_node_id:
        return []
    gateway_node_id = _ensure_gateway_node(state, generation, entry_node_id)
    if not gateway_node_id:
        _drop_hidden_node(state, entry_node_id)
        return []

    sync_node_pools_for_known_nodes(state)
    salvage_seeded = _seed_entry_salvage_hint(state, entry_node_id, gateway_node_id, generation)
    channel = _passive_channel_for_trigger(trigger)
    mail_from = "CORE.OS / passive relay cache" if channel == "ship_os_mail" else None
    mail_subject = "Recovered navigation trace" if channel == "ship_os_mail" else None
    path, event = write_local_intel(
        state,
        channel,
        _entry_hint_content(state, entry_node_id, trigger),
        node_id=state.world.current_node_id,
        source=_activation_source(state, trigger),
        mail_from=mail_from,
        mail_subject=mail_subject,
    )
    recovery.generation = generation
    recovery.anchor_node_id = state.world.current_node_id
    recovery.entry_node_id = entry_node_id
    recovery.gateway_node_id = gateway_node_id
    recovery.passive_hint_path = path
    recovery.passive_hint_channel = channel
    recovery.passive_hint_t = float(state.clock.t)
    recovery.dock_hint_path = None
    recovery.dock_hint_delivered = False
    recovery.salvage_hint_seeded = salvage_seeded

    state.world.mobility_failsafe_count += 1
    state.world.mobility_hints.append(
        {
            "t": state.clock.t,
            "trigger": trigger,
            "entry": entry_node_id,
            "gateway": gateway_node_id,
            "channel": channel,
        }
    )
    return [event]


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
    )
    recovery.dock_hint_path = path
    recovery.dock_hint_delivered = True
    return [event]


def ensure_exploration_recovery(state, trigger: str) -> list[Event]:
    sync_node_pools_for_known_nodes(state)
    events = _deliver_gateway_broadcast_if_needed(state)
    if not is_exploration_capable(state):
        return events
    if has_exploration_frontier(state):
        return events
    return events + _activate_recovery(state, trigger)
