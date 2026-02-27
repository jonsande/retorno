from __future__ import annotations

import math
import random

from retorno.config.balance import Balance
from retorno.model.events import Event, EventType, Severity, SourceRef
from retorno.model.os import AccessLevel, FSNode, FSNodeType, normalize_path, register_mail
from retorno.model.world import DeadNodeState, SpaceNode
from retorno.worldgen.generator import _generate_node_id, _name_from_node_id


def _hash_rng(seed: int, *parts: str) -> random.Random:
    h = 1469598103934665603
    for part in parts:
        for ch in part:
            h ^= ord(ch)
            h *= 1099511628211
            h &= 0xFFFFFFFFFFFFFFFF
    h ^= seed & 0xFFFFFFFFFFFFFFFF
    return random.Random(h)


def _ensure_dir(fs: dict, path: str) -> None:
    if path not in fs:
        fs[path] = FSNode(path=path, node_type=FSNodeType.DIR, access=AccessLevel.GUEST)


def _reachable_nodes(known_links: dict[str, set[str]], start_id: str) -> set[str]:
    if start_id not in known_links:
        return {start_id}
    visited = {start_id}
    queue = [start_id]
    while queue:
        cur = queue.pop(0)
        for nxt in known_links.get(cur, set()):
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append(nxt)
    return visited


def _distance_ly(a: SpaceNode, b: SpaceNode) -> float:
    dx = a.x_ly - b.x_ly
    dy = a.y_ly - b.y_ly
    dz = a.z_ly - b.z_ly
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _node_has_known_route(known_links: dict[str, set[str]], reachable: set[str], node_id: str) -> bool:
    for src in reachable:
        if node_id in known_links.get(src, set()):
            return True
    return False


def _is_within_route_range(state, reachable: set[str], node_id: str) -> bool:
    target = state.world.space.nodes.get(node_id)
    if not target:
        return False
    max_dist = Balance.SENSORS_RANGE_LY
    for src_id in reachable:
        src = state.world.space.nodes.get(src_id)
        if not src:
            continue
        if _distance_ly(src, target) <= max_dist:
            return True
    return False


def _thresholds_for_node(state, node_id: str) -> tuple[int, int, float, float]:
    rng = _hash_rng(state.meta.rng_seed, "deadnode", node_id)
    stuck_uplinks = rng.randint(Balance.DEADNODE_STUCK_UPLINKS_MIN, Balance.DEADNODE_STUCK_UPLINKS_MAX)
    dead_uplinks = rng.randint(Balance.DEADNODE_DEAD_UPLINKS_MIN, Balance.DEADNODE_DEAD_UPLINKS_MAX)
    stuck_years = rng.uniform(Balance.DEADNODE_STUCK_YEARS_MIN, Balance.DEADNODE_STUCK_YEARS_MAX)
    dead_years = rng.uniform(Balance.DEADNODE_DEAD_YEARS_MIN, Balance.DEADNODE_DEAD_YEARS_MAX)
    return stuck_uplinks, dead_uplinks, stuck_years, dead_years


def _write_local_intel(state, channel: str, content: str) -> tuple[str, Event]:
    seq = state.events.next_event_seq
    state.events.next_event_seq += 1
    if channel == "captured_signal":
        _ensure_dir(state.os.fs, "/logs")
        _ensure_dir(state.os.fs, "/logs/signals")
        path = normalize_path(f"/logs/signals/{seq:04d}.{state.os.locale.value}.txt")
        state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
        msg = {
            "en": f"signal_captured :: Narrowband capture stored at {path}",
            "es": f"signal_captured :: Captura de banda estrecha guardada en {path}",
        }.get(state.os.locale.value, f"signal_captured :: Signal captured: {path}")
        ev = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=EventType.SIGNAL_CAPTURED,
            severity=Severity.INFO,
            source=SourceRef(kind="world", id=state.world.current_node_id),
            message=msg,
            data={"path": path},
        )
        return path, ev
    if channel == "station_broadcast":
        _ensure_dir(state.os.fs, "/logs")
        _ensure_dir(state.os.fs, "/logs/broadcasts")
        path = normalize_path(f"/logs/broadcasts/{state.world.current_node_id}_{seq:04d}.{state.os.locale.value}.txt")
        state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
        msg = {
            "en": f"broadcast_received :: Station bulletin recorded at {path}",
            "es": f"broadcast_received :: Boletín de estación registrado en {path}",
        }.get(state.os.locale.value, f"broadcast_received :: Station broadcast: {path}")
        ev = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=EventType.BROADCAST_RECEIVED,
            severity=Severity.INFO,
            source=SourceRef(kind="world", id=state.world.current_node_id),
            message=msg,
            data={"path": path},
        )
        return path, ev
    _ensure_dir(state.os.fs, "/mail")
    _ensure_dir(state.os.fs, "/mail/inbox")
    path = normalize_path(f"/mail/inbox/{seq:04d}.{state.os.locale.value}.txt")
    state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
    register_mail(state.os, path, state.clock.t)
    msg = {
        "en": f"mail_received :: New internal memo queued: {path}",
        "es": f"mail_received :: Nuevo memo interno en cola: {path}",
    }.get(state.os.locale.value, f"mail_received :: New mail received: {path}")
    ev = Event(
        event_id=f"E{seq:05d}",
        t=int(state.clock.t),
        type=EventType.MAIL_RECEIVED,
        severity=Severity.INFO,
        source=SourceRef(kind="world", id=state.world.current_node_id),
        message=msg,
        data={"path": path},
    )
    return path, ev


def _create_bridge_node(state, dead_node_id: str, attempt: int) -> SpaceNode | None:
    dead_node = state.world.space.nodes.get(dead_node_id)
    if not dead_node:
        return None
    rng = _hash_rng(state.meta.rng_seed, "bridge", dead_node_id, str(attempt))
    dist = Balance.SENSORS_RANGE_LY * 0.6
    theta = rng.uniform(0, math.tau)
    phi = rng.uniform(-math.pi / 2, math.pi / 2)
    dx = dist * math.cos(phi) * math.cos(theta)
    dy = dist * math.cos(phi) * math.sin(theta)
    dz = dist * math.sin(phi)
    node_id = _generate_node_id(state, "relay", rng)
    node = SpaceNode(
        node_id=node_id,
        name=_name_from_node_id(node_id, "relay"),
        kind="relay",
        radiation_rad_per_s=0.001,
        x_ly=dead_node.x_ly + dx,
        y_ly=dead_node.y_ly + dy,
        z_ly=dead_node.z_ly + dz,
        is_hub=True,
    )
    state.world.space.nodes[node_id] = node
    return node


def evaluate_dead_nodes(state, trigger: str, debug: bool = False) -> list[Event]:
    if not Balance.DEADNODE_FAILSAFE_ENABLED:
        return []
    events: list[Event] = []
    uplinks_total = state.world.lore.counters.get("uplink_count", 0)
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    reachable = _reachable_nodes(state.world.known_links, state.world.current_node_id)

    candidates = []
    for node_id in state.world.known_contacts:
        if _node_has_known_route(state.world.known_links, reachable, node_id):
            continue
        if _is_within_route_range(state, reachable, node_id):
            continue
        candidates.append(node_id)

    tracked = state.world.dead_nodes
    for node_id in list(tracked.keys()):
        if node_id not in candidates:
            tracked.pop(node_id, None)

    for node_id in candidates:
        st = tracked.get(node_id)
        if not st:
            st = DeadNodeState()
            su, du, sy, dy = _thresholds_for_node(state, node_id)
            st.stuck_threshold_uplinks = su
            st.dead_threshold_uplinks = du
            st.stuck_threshold_years = sy
            st.dead_threshold_years = dy
            st.stuck_since_t = state.clock.t
            st.stuck_since_uplinks = uplinks_total
            tracked[node_id] = st
            if debug:
                state.world.deadnode_log.append(f"stuck_start {node_id}")
        elapsed_uplinks = uplinks_total - st.stuck_since_uplinks
        elapsed_years = year - (st.stuck_since_t or 0.0) / Balance.YEAR_S if Balance.YEAR_S else 0.0
        if st.dead_since_t is None:
            if elapsed_uplinks >= st.dead_threshold_uplinks or elapsed_years >= st.dead_threshold_years:
                st.dead_since_t = state.clock.t
                st.dead_since_uplinks = uplinks_total
                if debug:
                    state.world.deadnode_log.append(f"dead_start {node_id}")

        if st.dead_since_t is None:
            continue

        years_since_action = (state.clock.t - st.last_action_t) / Balance.YEAR_S if Balance.YEAR_S else 0.0
        if st.last_action_t > 0 and years_since_action < Balance.DEADNODE_ACTION_COOLDOWN_YEARS:
            continue

        # Indirect strategy: create a bridge node near the dead node, then deliver link to it.
        if st.attempts < Balance.DEADNODE_MAX_INDIRECT_ATTEMPTS:
            bridge = None
            if st.bridge_node_id and st.bridge_node_id in state.world.space.nodes:
                bridge = state.world.space.nodes[st.bridge_node_id]
            else:
                bridge = _create_bridge_node(state, node_id, st.attempts)
                if bridge:
                    st.bridge_node_id = bridge.node_id
            if bridge:
                content = (
                    "NAV NOTE\n\n"
                    f"LINK: {state.world.current_node_id} -> {bridge.node_id}\n"
                )
                channel = "captured_signal" if trigger != "dock" else "station_broadcast"
                _path, ev = _write_local_intel(state, channel, content)
                events.append(ev)
                st.attempts += 1
                st.last_action_t = state.clock.t
                if debug:
                    state.world.deadnode_log.append(f"indirect {node_id} -> {bridge.node_id}")
                continue

        # Direct strategy: deliver a link to the dead node.
        content = (
            "NAV NOTE\n\n"
            f"LINK: {state.world.current_node_id} -> {node_id}\n"
        )
        channel = "captured_signal" if trigger != "dock" else "station_broadcast"
        _path, ev = _write_local_intel(state, channel, content)
        events.append(ev)
        st.attempts += 1
        st.last_action_t = state.clock.t
        if debug:
            state.world.deadnode_log.append(f"direct {state.world.current_node_id} -> {node_id}")

    return events
