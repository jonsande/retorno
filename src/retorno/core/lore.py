from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random
import re
from pathlib import Path

from retorno.config.balance import Balance
from retorno.model.events import Event, EventType, Severity, SourceRef
from retorno.model.os import AccessLevel, FSNode, FSNodeType, normalize_path, register_mail
from retorno.model.world import (
    SECTOR_SIZE_LY,
    NodePoolState,
    SpaceNode,
    add_known_link,
    record_intel,
    region_for_pos,
    sector_id_for_pos,
)
from retorno.runtime.data_loader import load_arcs, load_locations, load_singles
from retorno.worldgen.generator import _generate_node_id, _name_from_node_id, ensure_sector_generated


@dataclass(slots=True)
class LoreContext:
    node_id: str
    region: str
    dist_from_origin_ly: float
    year_since_wake: float


@dataclass(slots=True)
class LoreDelivery:
    files: list[dict]
    events: list[Event]


def _stable_seed64(*parts: object) -> int:
    h = hashlib.blake2b(digest_size=8)
    for part in parts:
        h.update(b"\x1f")
        h.update(str(part).encode("utf-8"))
    return int.from_bytes(h.digest(), "big", signed=False)


def _lore_seed(*parts: object) -> int:
    if Balance.DETERMINISTIC_LORE_INTEL:
        return _stable_seed64(*parts)
    return hash(tuple(parts))


def _content_from_ref(content_ref: str | None) -> str:
    if not content_ref:
        return ""
    path = Path(__file__).resolve().parents[3] / "data" / content_ref
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _sanitize_piece_path_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")
    return safe or "piece"


def _ensure_dir(fs: dict, path: str) -> None:
    if path not in fs:
        fs[path] = FSNode(path=path, node_type=FSNodeType.DIR, access=AccessLevel.GUEST)


def deliver_ship_mail(state, content_ref: str, lang: str) -> str:
    _ensure_dir(state.os.fs, "/mail")
    _ensure_dir(state.os.fs, "/mail/inbox")
    seq = state.events.next_event_seq
    path = normalize_path(f"/mail/inbox/{seq:04d}.{lang}.txt")
    content = _content_from_ref(content_ref)
    state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
    register_mail(state.os, path, state.clock.t)
    return path


def deliver_captured_signal(state, content_ref: str, lang: str) -> str:
    _ensure_dir(state.os.fs, "/logs")
    _ensure_dir(state.os.fs, "/logs/signals")
    seq = state.events.next_event_seq
    path = normalize_path(f"/logs/signals/{seq:04d}.{lang}.txt")
    content = _content_from_ref(content_ref)
    state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
    return path


def deliver_station_broadcast(state, node_id: str, content_ref: str, lang: str) -> str:
    _ensure_dir(state.os.fs, "/logs")
    _ensure_dir(state.os.fs, "/logs/broadcasts")
    seq = state.events.next_event_seq
    path = normalize_path(f"/logs/broadcasts/{node_id}_{seq:04d}.{lang}.txt")
    content = _content_from_ref(content_ref)
    state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
    return path


def _known_node_ids(state) -> list[str]:
    known_nodes = set(getattr(state.world, "known_nodes", set()) or set())
    known_contacts = set(getattr(state.world, "known_contacts", set()) or set())
    return sorted(known_nodes | known_contacts)


def _pool_seed_node_ids(state) -> list[str]:
    known = set(_known_node_ids(state))
    hidden = set(getattr(state.world, "forced_hidden_nodes", set()) or set())
    return sorted(known | hidden)


def _location_node_ids() -> set[str]:
    out: set[str] = set()
    for loc in load_locations():
        node_cfg = loc.get("node", {})
        nid = str(node_cfg.get("node_id", "")).strip()
        if nid:
            out.add(nid)
    return out


def _location_fs_files(node_id: str) -> list[dict]:
    for loc in load_locations():
        node_cfg = loc.get("node", {})
        if node_cfg.get("node_id") == node_id:
            return list(loc.get("fs_files") or [])
    return []


def _primary_link_pair(primary: dict) -> tuple[str, str] | None:
    line = str(primary.get("line", "")).strip()
    if "->" not in line:
        return None
    try:
        left, right = [p.strip() for p in line.split(":", 1)[1].split("->", 1)]
    except Exception:
        return None
    if not left or not right:
        return None
    return left, right


def _primary_target_node_id(primary: dict) -> str | None:
    kind = str(primary.get("kind", "")).strip().lower()
    if kind == "link":
        pair = _primary_link_pair(primary)
        return pair[1] if pair else None
    if kind == "node":
        line = str(primary.get("line", "")).strip()
        if not line:
            return None
        if ":" in line:
            head, payload = line.split(":", 1)
            if head.strip().upper() == "NODE":
                node_id = payload.strip()
                return node_id or None
        return line
    return None


def _locked_primary_targets(state) -> set[str]:
    locked: set[str] = set()
    for arc in load_arcs():
        arc_id = arc.get("arc_id", "")
        if not arc_id:
            continue
        primary = arc.get("primary_intel") or {}
        target = _primary_target_node_id(primary)
        if not target:
            continue
        pid = primary.get("id", "primary")
        arc_state = state.world.arc_placements.get(arc_id) or {}
        discovered = arc_state.get("discovered")
        if not isinstance(discovered, set):
            discovered = set(discovered or [])
        primary_state = arc_state.get("primary")
        if not isinstance(primary_state, dict):
            primary_state = {}
        unlocked = bool(primary_state.get("unlocked")) or pid in discovered
        if not unlocked:
            locked.add(target)
    return locked


def _parse_sector_id(sector_id: str) -> tuple[int, int, int]:
    try:
        _, sx, sy, sz = sector_id[1:].split("_")
        return int(sx), int(sy), int(sz)
    except Exception:
        return 0, 0, 0


def _precompute_uplink_route_pool_for_node(state, node_id: str, max_new: int = 3) -> list[str]:
    node = state.world.space.nodes.get(node_id)
    if not node or node.kind not in {"relay", "station", "waystation"}:
        return []
    if max_new <= 0:
        return []

    current_sector = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
    sx, sy, sz = _parse_sector_id(current_sector)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            ensure_sector_generated(state, f"S{sx+dx:+04d}_{sy+dy:+04d}_{sz:+04d}")

    routes = set(state.world.known_links.get(node_id, set()))
    locked_primary_targets = _locked_primary_targets(state)
    authored_ids = _location_node_ids()
    hub_kinds = {"relay", "station", "waystation"}
    deterministic = Balance.DETERMINISTIC_LORE_INTEL
    candidates: dict[str, int] = {}

    def _add_candidate(nid: str, weight: int) -> None:
        if nid == node_id or nid in routes or nid in locked_primary_targets:
            return
        prev = candidates.get(nid, 0)
        if weight > prev:
            candidates[nid] = weight

    known_nodes_iter = sorted(state.world.known_nodes) if deterministic else state.world.known_nodes
    for nid in known_nodes_iter:
        if nid == node_id or nid in routes:
            continue
        n = state.world.space.nodes.get(nid)
        if n and n.kind in hub_kinds:
            _add_candidate(nid, 10)
        elif n and n.kind in {"ship", "derelict"}:
            _add_candidate(nid, 2)
        else:
            _add_candidate(nid, 1)

    neighbor_sectors: list[str] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            neighbor_sectors.append(f"S{sx+dx:+04d}_{sy+dy:+04d}_{sz:+04d}")

    space_nodes_iter = sorted(state.world.space.nodes) if deterministic else state.world.space.nodes
    for nid in space_nodes_iter:
        n = state.world.space.nodes[nid]
        sid = sector_id_for_pos(n.x_ly, n.y_ly, n.z_ly)
        if n.is_hub and sid == current_sector:
            _add_candidate(nid, 6)
        if n.is_hub and sid in neighbor_sectors:
            _add_candidate(nid, 5)
        if n.kind == "derelict":
            _add_candidate(nid, 1)
        if nid not in authored_ids and n.kind in hub_kinds and sid in neighbor_sectors:
            _add_candidate(nid, 4)

    if not candidates:
        return []

    seed = _stable_seed64(state.meta.rng_seed, "uplink_pool", node_id, int(state.clock.t), len(candidates))
    rng = random.Random(seed)
    pool = sorted(candidates.items()) if deterministic else list(candidates.items())
    selected: list[str] = []
    while pool and len(selected) < max_new:
        total = sum(weight for _, weight in pool)
        if total <= 0:
            break
        roll = rng.uniform(0, total)
        upto = 0.0
        picked_index = 0
        for i, (_, weight) in enumerate(pool):
            upto += weight
            if roll <= upto:
                picked_index = i
                break
        dest, _weight = pool.pop(picked_index)
        if dest in selected or dest == node_id:
            continue
        selected.append(dest)

    return selected


def _procedural_fs_files(state, node: SpaceNode) -> list[dict]:
    seed = _stable_seed64(state.meta.rng_seed, node.node_id)
    rng = random.Random(seed)
    files: list[dict] = []

    def _add(path: str, content: str) -> None:
        files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})

    link_line = ""
    if node.links:
        link = sorted(node.links)[0]
        link_line = f"LINK: {node.node_id} -> {link}\n"

    p_log = (
        Balance.SALVAGE_DATA_LOG_P_STATION_SHIP
        if node.kind in {"station", "ship"}
        else Balance.SALVAGE_DATA_LOG_P_OTHER
    )
    if rng.random() < p_log:
        content = link_line or f"NODE: {node.node_id}\n"
        _add("/logs/nav.log", content)

    p_mail = (
        Balance.SALVAGE_DATA_MAIL_P_STATION_SHIP
        if node.kind in {"station", "ship"}
        else Balance.SALVAGE_DATA_MAIL_P_OTHER
    )
    if rng.random() < p_mail:
        lang = state.os.locale.value
        content = (
            f"FROM: {node.name}\n"
            "SUBJ: Recovered Data Cache\n\n"
            f"Automated report from {node.name} ({node.kind}).\n"
            f"Region: {node.region}\n"
        )
        _add(f"/mail/inbox/0001.{lang}.txt", content)

    p_frag = (
        Balance.SALVAGE_DATA_FRAG_P_STATION_DERELICT
        if node.kind in {"station", "derelict"}
        else Balance.SALVAGE_DATA_FRAG_P_OTHER
    )
    if rng.random() < p_frag:
        frag_id = f"{rng.getrandbits(16):04x}"
        content = link_line or f"NODE: {node.node_id}\n"
        _add(f"/data/nav/fragments/frag_{frag_id}.txt", content)

    if link_line and not any("LINK:" in f.get("content", "") for f in files):
        frag_id = f"{rng.getrandbits(16):04x}"
        _add(f"/data/nav/fragments/frag_{frag_id}.txt", link_line)

    return files


def build_lore_context(state, node_id: str) -> LoreContext:
    node = state.world.space.nodes.get(node_id)
    if node:
        region = node.region or region_for_pos(node.x_ly, node.y_ly, node.z_ly)
        dist = math.sqrt(node.x_ly * node.x_ly + node.y_ly * node.y_ly + node.z_ly * node.z_ly)
    else:
        region = ""
        dist = 0.0
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    return LoreContext(node_id=node_id, region=region, dist_from_origin_ly=dist, year_since_wake=year)


def _collect_base_files_for_node(state, node_id: str, node: SpaceNode | None) -> list[dict]:
    base = _location_fs_files(node_id)
    if base:
        return list(base)
    if node is None:
        return []
    return _procedural_fs_files(state, node)


def collect_node_salvage_data_files(state, node_id: str) -> list[dict]:
    sync_node_pools_for_known_nodes(state)
    pool = state.world.node_pools.get(node_id)
    if not pool:
        return []
    merged: dict[str, dict] = {}
    for entry in list(pool.base_files) + list(pool.injected_files):
        src = normalize_path(str(entry.get("path", "")))
        if not src:
            continue
        if src not in merged:
            merged[src] = dict(entry)
    return list(merged.values())


def project_mountable_data_paths(fs: dict[str, FSNode], mount_root: str, files: list[dict]) -> list[str]:
    return _project_mount_paths(fs, mount_root, files, include_existing=False)


def _project_mount_paths(
    fs: dict[str, FSNode], mount_root: str, files: list[dict], *, include_existing: bool
) -> list[str]:
    projected: set[str] = set()
    mount_root = normalize_path(mount_root)
    for entry in files:
        src_path = normalize_path(str(entry.get("path", "")))
        if not src_path:
            continue
        if not (src_path.startswith("/mail") or src_path.startswith("/logs") or src_path.startswith("/data")):
            continue
        dest_path = normalize_path(mount_root + src_path)
        if not include_existing and dest_path in fs:
            continue
        projected.add(dest_path)
    return sorted(projected)


def mount_projection_breakdown(fs: dict[str, FSNode], mount_root: str, files: list[dict]) -> tuple[list[str], list[str], list[str]]:
    mount_root = normalize_path(mount_root)
    seen: set[str] = set()
    new_paths: list[str] = []
    existing_paths: list[str] = []
    for entry in files:
        src_path = normalize_path(str(entry.get("path", "")))
        if not src_path:
            continue
        if not (src_path.startswith("/mail") or src_path.startswith("/logs") or src_path.startswith("/data")):
            continue
        dest_path = normalize_path(mount_root + src_path)
        if dest_path in seen:
            continue
        seen.add(dest_path)
        if dest_path in fs:
            existing_paths.append(dest_path)
        else:
            new_paths.append(dest_path)
    total_paths = sorted(seen)
    return sorted(new_paths), sorted(existing_paths), total_paths


def survey_recoverable_data_count(state, node_id: str) -> int:
    files = collect_node_salvage_data_files(state, node_id)
    mount_root = normalize_path(f"/remote/{node_id}")
    return len(_project_mount_paths(state.os.fs, mount_root, files, include_existing=False))


def survey_reports_data_signatures(state, node_id: str, job_id: str, data_available: bool) -> bool:
    if not data_available:
        return False
    miss_p = max(0.0, min(1.0, float(Balance.DRONE_SURVEY_DATA_FALSE_NEGATIVE_P)))
    if miss_p <= 0.0:
        return True
    if miss_p >= 1.0:
        return False
    seed = _stable_seed64(state.meta.rng_seed, f"survey_data:{node_id}:{job_id}:{int(state.clock.t)}")
    return random.Random(seed).random() >= miss_p


def sync_node_pools_for_known_nodes(state) -> None:
    for node_id in _pool_seed_node_ids(state):
        if node_id in state.world.node_pools:
            continue
        node = state.world.space.nodes.get(node_id)
        pool = NodePoolState(initialized_t=float(state.clock.t), window_open=True)
        pool.base_files = _collect_base_files_for_node(state, node_id, node)
        pool.uplink_route_pool = _precompute_uplink_route_pool_for_node(state, node_id, max_new=3)
        state.world.node_pools[node_id] = pool
        recompute_node_completion(state, node_id)
        if node_id in state.world.visited_nodes:
            close_window_on_orbit_entry(state, node_id, reason="already_visited")


def close_window_on_orbit_entry(state, node_id: str, *, reason: str = "orbit_entry") -> None:
    pool = state.world.node_pools.get(node_id)
    if not pool or not pool.window_open:
        return
    pool.window_open = False
    pool.window_closed_t = float(state.clock.t)
    pool.window_closed_reason = reason


def close_windows_for_visited_nodes(state) -> None:
    for node_id in sorted(state.world.visited_nodes):
        close_window_on_orbit_entry(state, node_id)


def _pending_node_files_count(state, node_id: str, pool: NodePoolState) -> int:
    mount_root = normalize_path(f"/remote/{node_id}")
    files = list(pool.base_files) + list(pool.injected_files)
    return len(_project_mount_paths(state.os.fs, mount_root, files, include_existing=False))


def recompute_node_completion(state, node_id: str) -> None:
    node = state.world.space.nodes.get(node_id)
    pool = state.world.node_pools.get(node_id)
    if not pool:
        return

    scrap_complete = True
    extras_complete = True
    if node:
        scrap_complete = int(getattr(node, "salvage_scrap_available", 0) or 0) <= 0
        modules_left = bool(getattr(node, "salvage_modules_available", []) or [])
        drones_left = int(getattr(node, "recoverable_drones_count", 0) or 0) > 0
        extras_complete = not modules_left and not drones_left

    pending_files = _pending_node_files_count(state, node_id, pool)
    pending_push = [
        pid
        for pid in pool.pending_push_piece_ids
        if pid not in pool.delivered_piece_ids
    ]
    uplink_needed = bool(node and node.kind in {"relay", "station", "waystation"})
    uplink_complete = (not uplink_needed) or bool(pool.uplink_data_consumed)
    data_complete = pending_files == 0 and len(pending_push) == 0 and uplink_complete

    pool.scrap_complete = scrap_complete
    pool.extras_complete = extras_complete
    pool.data_complete = data_complete
    pool.node_cleaned = scrap_complete and extras_complete and data_complete


def recompute_all_node_completion(state) -> None:
    for node_id in sorted(state.world.node_pools.keys()):
        recompute_node_completion(state, node_id)


def piece_constraints_ok(piece: dict, ctx: LoreContext) -> bool:
    cons = piece.get("constraints") or {}
    min_year = cons.get("min_year")
    max_year = cons.get("max_year")
    min_dist = cons.get("min_dist_ly")
    max_dist = cons.get("max_dist_ly")
    regions_any = cons.get("regions_any") or []
    if min_year is not None and ctx.year_since_wake < float(min_year):
        return False
    if max_year is not None and ctx.year_since_wake > float(max_year):
        return False
    if min_dist is not None and ctx.dist_from_origin_ly < float(min_dist):
        return False
    if max_dist is not None and ctx.dist_from_origin_ly > float(max_dist):
        return False
    if regions_any and ctx.region not in regions_any:
        return False
    return True


def _deadline_reached(state, piece: dict) -> bool:
    deadline = piece.get("force_deadline") or {}
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    counters = state.world.lore.counters
    near = 0.9
    if deadline.get("max_year") is not None and year >= float(deadline.get("max_year")):
        return True
    if deadline.get("max_year") is not None and year >= float(deadline.get("max_year")) * near:
        return True
    if deadline.get("max_events") is not None:
        total = sum(counters.values())
        if total >= int(deadline.get("max_events")):
            return True
        if total >= int(deadline.get("max_events")) * near:
            return True
    if deadline.get("max_docks") is not None and counters.get("dock_count", 0) >= int(deadline.get("max_docks")):
        return True
    if deadline.get("max_docks") is not None and counters.get("dock_count", 0) >= int(deadline.get("max_docks")) * near:
        return True
    if deadline.get("max_uplinks") is not None and counters.get("uplink_count", 0) >= int(deadline.get("max_uplinks")):
        return True
    if deadline.get("max_uplinks") is not None and counters.get("uplink_count", 0) >= int(deadline.get("max_uplinks")) * near:
        return True
    if deadline.get("max_salvage_data") is not None and counters.get("salvage_data_count", 0) >= int(
        deadline.get("max_salvage_data")
    ):
        return True
    if deadline.get("max_salvage_data") is not None and counters.get("salvage_data_count", 0) >= int(
        deadline.get("max_salvage_data")
    ) * near:
        return True
    return False


def _soft_force_roll(state, piece: dict, seq: int) -> bool:
    counters = state.world.lore.counters
    total = sum(counters.values())
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    p = min(0.5, 0.1 + total * 0.02 + year * 0.02)
    seed = _lore_seed(state.meta.rng_seed, "lore_soft", piece.get("id"), total, seq)
    return random.Random(seed).random() < p


def _default_channels_for_piece(piece: dict, *, single: bool) -> list[str]:
    if single:
        allowed = piece.get("channels") or ["captured_signal"]
    else:
        allowed = piece.get("allowed_channels") or [
            "salvage_data",
            "ship_os_mail",
            "captured_signal",
            "station_broadcast",
            "uplink_only",
        ]
    if "uplink" in allowed and "uplink_only" not in allowed:
        allowed = list(allowed) + ["uplink_only"]
    return list(allowed)


def _iter_all_pieces() -> list[dict]:
    pieces: list[dict] = []
    for arc in load_arcs():
        arc_id = str(arc.get("arc_id", "")).strip()
        if not arc_id:
            continue
        primary = arc.get("primary_intel") or {}
        if primary:
            pid = primary.get("id") or "primary"
            pieces.append(
                {
                    "piece_key": f"arc:{arc_id}:{pid}",
                    "piece_id": str(pid),
                    "piece": primary,
                    "arc_id": arc_id,
                    "role": "primary",
                    "force": bool(primary.get("force", False)),
                    "channels": _default_channels_for_piece(primary, single=False),
                    "placement_rules": (arc.get("placement_rules", {}) or {}).get("primary", {}) or {},
                }
            )
        for doc in arc.get("secondary_lore_docs", []) or []:
            pid = doc.get("id") or "secondary"
            pieces.append(
                {
                    "piece_key": f"arc:{arc_id}:{pid}",
                    "piece_id": str(pid),
                    "piece": doc,
                    "arc_id": arc_id,
                    "role": "secondary",
                    "force": bool(doc.get("force", False)),
                    "channels": _default_channels_for_piece(doc, single=False),
                    "placement_rules": (arc.get("placement_rules", {}) or {}).get("secondary", {}) or {},
                }
            )

    for single in load_singles() or []:
        sid = str(single.get("single_id", "")).strip()
        if not sid:
            continue
        pieces.append(
            {
                "piece_key": f"single:{sid}",
                "piece_id": sid,
                "piece": single,
                "arc_id": "",
                "role": "single",
                "force": bool(single.get("force", False)),
                "channels": _default_channels_for_piece(single, single=True),
                "placement_rules": {},
            }
        )

    return pieces


def _piece_index() -> dict[str, dict]:
    return {entry["piece_key"]: entry for entry in _iter_all_pieces()}


def _start_node_for_hops(state) -> str:
    if "UNKNOWN_00" in state.world.space.nodes:
        return "UNKNOWN_00"
    return state.world.current_node_id


def _hop_distance_from_start(state, target_id: str, max_hops: int) -> int | None:
    start_id = _start_node_for_hops(state)
    if start_id not in state.world.space.nodes or target_id not in state.world.space.nodes:
        return None
    visited = {start_id}
    queue = [(start_id, 0)]
    while queue:
        nid, dist = queue.pop(0)
        if nid == target_id:
            return dist
        if dist >= max_hops:
            continue
        node = state.world.space.nodes.get(nid)
        if not node:
            continue
        for nxt in sorted(node.links):
            if nxt in visited:
                continue
            if nxt not in state.world.space.nodes:
                continue
            visited.add(nxt)
            queue.append((nxt, dist + 1))
    return None


def _node_matches_candidates(node_id: str, node: SpaceNode, candidates: set[str], authored: set[str]) -> bool:
    if not candidates:
        return True
    if node_id in candidates or node_id.lower() in candidates:
        return True
    is_procedural = node_id not in authored
    if not is_procedural:
        return False
    if node.kind == "station" and "procedural_station" in candidates:
        return True
    if node.kind == "relay" and "procedural_relay" in candidates:
        return True
    if node.kind == "derelict" and "procedural_derelict" in candidates:
        return True
    if node.kind == "ship" and "procedural_ship" in candidates:
        return True
    return False


def _channel_feasible_for_node(channel: str, node: SpaceNode | None) -> bool:
    if channel == "uplink_only":
        return bool(node and node.kind in {"relay", "station", "waystation"})
    if channel == "station_broadcast":
        return bool(node and node.kind in {"relay", "station", "waystation"})
    if channel in {"salvage_data", "ship_os_mail", "captured_signal"}:
        return True
    return False


def _trigger_matches_channel(trigger: str, channel: str) -> bool:
    if channel == "salvage_data":
        return trigger == "salvage_data"
    if channel == "station_broadcast":
        return trigger == "dock"
    if channel == "uplink_only":
        return trigger == "uplink"
    if channel in {"ship_os_mail", "captured_signal"}:
        return trigger in {"dock", "uplink", "salvage_data"}
    return False


def _candidate_nodes_for_piece(state, piece_entry: dict) -> list[str]:
    authored = _location_node_ids()
    piece = piece_entry["piece"]
    rules = piece_entry.get("placement_rules") or {}
    avoid_ids = set(str(x) for x in (rules.get("avoid_node_ids") or []))
    require_kinds = set(str(x) for x in (rules.get("require_kind_any") or []))
    candidates_cfg = set(str(x) for x in (rules.get("candidates") or []))
    max_hops = int(rules.get("max_hops_from_start", 0) or 0)

    out: list[str] = []
    for node_id, pool in sorted(state.world.node_pools.items()):
        if not pool.window_open or pool.node_cleaned:
            continue
        node = state.world.space.nodes.get(node_id)
        if node_id in avoid_ids:
            continue
        if node is None:
            continue
        if require_kinds and node.kind not in require_kinds:
            continue
        if not _node_matches_candidates(node_id, node, candidates_cfg, authored):
            continue
        if max_hops > 0:
            hop = _hop_distance_from_start(state, node_id, max_hops)
            if hop is None or hop > max_hops:
                continue
        ctx = build_lore_context(state, node_id)
        if not piece_constraints_ok(piece, ctx):
            continue
        if not any(_channel_feasible_for_node(ch, node) for ch in piece_entry.get("channels", [])):
            continue
        out.append(node_id)
    return out


def _pick_channel_for_node(piece_entry: dict, node: SpaceNode | None) -> str | None:
    for channel in piece_entry.get("channels", []):
        if _channel_feasible_for_node(channel, node):
            return channel
    return None


def _content_ref_for_piece(piece: dict, lang: str) -> str | None:
    if piece.get(f"content_ref_{lang}"):
        return piece.get(f"content_ref_{lang}")
    if piece.get("content_ref_en"):
        return piece.get("content_ref_en")
    if piece.get("files"):
        entry = (piece.get("files") or [{}])[0]
        if entry.get(f"content_ref_{lang}"):
            return entry.get(f"content_ref_{lang}")
        if entry.get("content_ref_en"):
            return entry.get("content_ref_en")
    return None


def _path_template_for_piece(piece: dict) -> str:
    if piece.get("path_template"):
        return str(piece.get("path_template"))
    if piece.get("files"):
        entry = (piece.get("files") or [{}])[0]
        if entry.get("path_template"):
            return str(entry.get("path_template"))
    return ""


def _file_for_salvage_piece(piece_entry: dict, lang: str) -> dict | None:
    piece_key = piece_entry["piece_key"]
    piece = piece_entry["piece"]
    path_template = _path_template_for_piece(piece)
    if path_template:
        path = path_template.replace("{lang}", lang)
        if "02xx" in path:
            path = path.replace("02xx", f"02{_stable_seed64(piece_key) % 100:02d}")
    else:
        safe = _sanitize_piece_path_id(piece_key)
        path = f"/logs/records/{safe}.{lang}.txt"

    content_ref = _content_ref_for_piece(piece, lang)
    content = _content_from_ref(content_ref)
    if not content and piece.get("line"):
        content = str(piece.get("line")) + "\n"

    return {"path": path, "access": AccessLevel.GUEST.value, "content": content}


def _seed_hidden_forced_breadcrumb(state, hidden_node_id: str, piece_key: str) -> None:
    known = _known_node_ids(state)
    candidates = [
        nid
        for nid in known
        if nid in state.world.node_pools
        and not bool(state.world.node_pools[nid].node_cleaned)
    ]
    if not candidates:
        return

    seed = _stable_seed64(state.meta.rng_seed, "forced_hidden_breadcrumb", hidden_node_id, piece_key)
    reveal_node_id = sorted(candidates)[seed % len(candidates)]
    reveal_pool = state.world.node_pools.get(reveal_node_id)
    if not reveal_pool:
        return

    suffix = _sanitize_piece_path_id(hidden_node_id.lower())
    path = f"/logs/nav/forced_hint_{suffix}.txt"
    existing_paths = {
        normalize_path(str(f.get("path", "")))
        for f in list(reveal_pool.base_files) + list(reveal_pool.injected_files)
    }
    if normalize_path(path) in existing_paths:
        return

    content = (
        "NAV NOTE\n\n"
        f"LINK: {reveal_node_id} -> {hidden_node_id}\n"
    )
    reveal_pool.injected_files.append(
        {
            "path": path,
            "access": AccessLevel.GUEST.value,
            "content": content,
        }
    )
    recompute_node_completion(state, reveal_node_id)


def _spawn_ad_hoc_candidate_for_forced_piece(state, piece_entry: dict) -> str | None:
    anchor_id = state.world.current_node_id
    anchor = state.world.space.nodes.get(anchor_id)
    if not anchor and state.world.space.nodes:
        anchor_id = sorted(state.world.space.nodes.keys())[0]
        anchor = state.world.space.nodes.get(anchor_id)
    if not anchor:
        return None

    rules = piece_entry.get("placement_rules") or {}
    require_kinds = [str(x) for x in (rules.get("require_kind_any") or []) if str(x)]
    allowed_kinds = [k for k in require_kinds if k in {"station", "relay", "derelict", "ship", "waystation"}]
    if not allowed_kinds:
        candidates_cfg = set(str(x) for x in (rules.get("candidates") or []))
        if "procedural_relay" in candidates_cfg:
            allowed_kinds = ["relay"]
        elif "procedural_derelict" in candidates_cfg:
            allowed_kinds = ["derelict"]
        else:
            allowed_kinds = ["station"]

    seed = _stable_seed64(
        state.meta.rng_seed,
        "forced_ad_hoc",
        piece_entry["piece_key"],
        state.world.lore_placements.eval_seq,
    )
    rng = random.Random(seed)
    kind = allowed_kinds[int(seed % len(allowed_kinds))]
    node_id = _generate_node_id(state, kind, rng)
    theta = rng.uniform(0.0, math.tau)
    dist = rng.uniform(0.4, 2.0)
    dx = math.cos(theta) * dist
    dy = math.sin(theta) * dist
    dz = rng.uniform(-0.1, 0.1)
    node = SpaceNode(
        node_id=node_id,
        name=_name_from_node_id(node_id, kind),
        kind=kind,
        radiation_rad_per_s=0.0,
        radiation_base=0.0,
        region=anchor.region or region_for_pos(anchor.x_ly, anchor.y_ly, anchor.z_ly),
        x_ly=anchor.x_ly + dx,
        y_ly=anchor.y_ly + dy,
        z_ly=anchor.z_ly + dz,
    )
    node.links.add(anchor.node_id)
    anchor.links.add(node.node_id)
    state.world.space.nodes[node_id] = node
    state.world.forced_hidden_nodes.add(node_id)
    sync_node_pools_for_known_nodes(state)
    _seed_hidden_forced_breadcrumb(state, node_id, piece_entry["piece_key"])
    return node_id


def _register_arc_placement(state, piece_entry: dict, node_id: str, file_path: str | None) -> None:
    arc_id = piece_entry.get("arc_id")
    if not arc_id:
        return
    role = piece_entry.get("role", "")
    arc_state = state.world.arc_placements.setdefault(
        arc_id,
        {
            "primary": {"placed": False, "node_id": None, "path": None, "source": None},
            "secondary": {},
            "counters": {"uplink_attempts": 0, "procedural_candidates": 0},
            "discovered": set(),
        },
    )
    discovered = arc_state.get("discovered")
    if not isinstance(discovered, set):
        arc_state["discovered"] = set(discovered or [])
    if role == "primary":
        primary = arc_state.setdefault("primary", {})
        primary["placed"] = True
        primary["node_id"] = node_id
        if file_path:
            primary["path"] = file_path
    else:
        sec = arc_state.setdefault("secondary", {})
        sec[piece_entry.get("piece_id", "secondary")] = {"node_id": node_id, "path": file_path}


def _assign_piece_to_node(state, piece_entry: dict, node_id: str) -> bool:
    piece_key = piece_entry["piece_key"]
    if piece_key in state.world.lore_placements.piece_to_node:
        return False

    pool = state.world.node_pools.get(node_id)
    node = state.world.space.nodes.get(node_id)
    if not pool or not node:
        return False

    channel = _pick_channel_for_node(piece_entry, node)
    if not channel:
        return False

    state.world.lore_placements.piece_to_node[piece_key] = node_id
    state.world.lore_placements.piece_channel_bindings[piece_key] = channel

    file_path: str | None = None
    if channel == "salvage_data":
        entry = _file_for_salvage_piece(piece_entry, state.os.locale.value)
        if entry:
            pool.injected_files.append(entry)
            file_path = str(entry.get("path", ""))
    else:
        pool.pending_push_piece_ids.add(piece_key)

    _register_arc_placement(state, piece_entry, node_id, file_path)
    recompute_node_completion(state, node_id)
    return True


def _mark_primary_unlocked(state, arc_id: str, piece: dict) -> None:
    if not arc_id:
        return
    arc_state = state.world.arc_placements.setdefault(arc_id, {})
    primary_state = arc_state.setdefault("primary", {})
    primary_state["unlocked"] = True
    discovered = arc_state.get("discovered")
    if not isinstance(discovered, set):
        discovered = set(discovered or [])
    discovered.add(piece.get("id", "primary"))
    arc_state["discovered"] = discovered


def _deliver_piece(
    state,
    arc_id: str,
    piece_id: str,
    piece: dict,
    channel: str,
    ctx: LoreContext,
    *,
    is_primary: bool = False,
) -> LoreDelivery:
    delivered_files: list[dict] = []
    events: list[Event] = []
    lang = state.os.locale.value

    if channel == "uplink_only":
        line = str(piece.get("line", "") or "")
        if "->" in line:
            try:
                left, right = [p.strip() for p in line.split(":", 1)[1].split("->", 1)]
            except Exception:
                left = right = ""
            if left and right:
                if add_known_link(state.world, left, right, bidirectional=True):
                    state.world.known_nodes.add(left)
                    state.world.known_nodes.add(right)
                    state.world.known_contacts.add(left)
                    state.world.known_contacts.add(right)
                    record_intel(
                        state.world,
                        t=state.clock.t,
                        kind="link",
                        from_id=left,
                        to_id=right,
                        confidence=float(piece.get("confidence", 0.6)),
                        source_kind="uplink_only",
                        source_ref=ctx.node_id,
                    )
                    if is_primary:
                        _mark_primary_unlocked(state, arc_id, piece)
        return LoreDelivery(delivered_files, events)

    content_ref = _content_ref_for_piece(piece, lang)

    if channel == "ship_os_mail":
        path = deliver_ship_mail(state, content_ref or "", lang)
        state.world.lore.delivery_log.append(f"mail:{piece_id}:{path}")
        msg = {
            "en": f"mail_received :: New mail received: {path}",
            "es": f"mail_received :: Nuevo correo recibido: {path}",
        }.get(lang, f"mail_received :: New mail received: {path}")
        events.append(
            Event(
                event_id=f"E{state.events.next_event_seq:05d}",
                t=int(state.clock.t),
                type=EventType.MAIL_RECEIVED,
                severity=Severity.INFO,
                source=SourceRef(kind="world", id=ctx.node_id),
                message=msg,
                data={"path": path},
            )
        )
        state.events.next_event_seq += 1
        return LoreDelivery(delivered_files, events)

    if channel == "captured_signal":
        path = deliver_captured_signal(state, content_ref or "", lang)
        state.world.lore.delivery_log.append(f"signal:{piece_id}:{path}")
        state.world.lore.counters["signal_count"] = state.world.lore.counters.get("signal_count", 0) + 1
        msg = {
            "en": f"signal_captured :: Signal captured: {path} (hint: cat {path})",
            "es": f"signal_captured :: Señal capturada: {path} (pista: cat {path})",
        }.get(lang, f"signal_captured :: Signal captured: {path}")
        events.append(
            Event(
                event_id=f"E{state.events.next_event_seq:05d}",
                t=int(state.clock.t),
                type=EventType.SIGNAL_CAPTURED,
                severity=Severity.INFO,
                source=SourceRef(kind="world", id=ctx.node_id),
                message=msg,
                data={"path": path},
            )
        )
        state.events.next_event_seq += 1
        return LoreDelivery(delivered_files, events)

    if channel == "station_broadcast":
        path = deliver_station_broadcast(state, ctx.node_id, content_ref or "", lang)
        state.world.lore.delivery_log.append(f"broadcast:{piece_id}:{path}")
        msg = {
            "en": f"broadcast_received :: Station broadcast: {path}",
            "es": f"broadcast_received :: Emisión recibida: {path}",
        }.get(lang, f"broadcast_received :: Station broadcast: {path}")
        events.append(
            Event(
                event_id=f"E{state.events.next_event_seq:05d}",
                t=int(state.clock.t),
                type=EventType.BROADCAST_RECEIVED,
                severity=Severity.INFO,
                source=SourceRef(kind="world", id=ctx.node_id),
                message=msg,
                data={"path": path},
            )
        )
        state.events.next_event_seq += 1
        return LoreDelivery(delivered_files, events)

    if channel == "salvage_data":
        entry = _file_for_salvage_piece({"piece_key": piece_id, "piece": piece}, lang)
        if entry:
            delivered_files.append(entry)
        return LoreDelivery(delivered_files, events)

    return LoreDelivery(delivered_files, events)


def _deliver_assigned_for_trigger(state, trigger: str, ctx: LoreContext) -> LoreDelivery:
    delivered_files: list[dict] = []
    events: list[Event] = []
    node_id = ctx.node_id
    piece_by_key = _piece_index()
    pool = state.world.node_pools.get(node_id)

    for piece_key, placed_node in sorted(state.world.lore_placements.piece_to_node.items()):
        if placed_node != node_id:
            continue
        channel = state.world.lore_placements.piece_channel_bindings.get(piece_key, "")
        if not _trigger_matches_channel(trigger, channel):
            continue
        if piece_key in state.world.lore.delivered:
            continue

        piece_entry = piece_by_key.get(piece_key)
        if not piece_entry:
            continue

        piece = piece_entry["piece"]
        arc_id = piece_entry.get("arc_id", "")
        piece_id = piece_entry.get("piece_id", piece_key)

        if channel != "salvage_data":
            result = _deliver_piece(
                state,
                arc_id,
                piece_id,
                piece,
                channel,
                ctx,
                is_primary=(piece_entry.get("role") == "primary"),
            )
            delivered_files.extend(result.files)
            events.extend(result.events)

        state.world.lore.delivered.add(piece_key)
        state.world.lore.last_delivery_t = state.clock.t
        if pool:
            pool.delivered_piece_ids.add(piece_key)
            pool.pending_push_piece_ids.discard(piece_key)

    if pool:
        recompute_node_completion(state, node_id)
    return LoreDelivery(delivered_files, events)


def _evaluate_forced_pieces(state, piece_entries: list[dict]) -> None:
    for piece_entry in piece_entries:
        if not piece_entry.get("force", False):
            continue
        piece_key = piece_entry["piece_key"]
        if piece_key in state.world.lore_placements.piece_to_node:
            continue

        piece = piece_entry["piece"]
        policy = str(piece.get("force_policy", "none") or "none")
        should_place = False
        if policy == "deadline":
            should_place = _deadline_reached(state, piece)
        elif policy == "soft":
            should_place = _soft_force_roll(state, piece, state.world.lore_placements.eval_seq)

        if not should_place:
            continue

        candidates = _candidate_nodes_for_piece(state, piece_entry)
        if not candidates:
            generated_id = _spawn_ad_hoc_candidate_for_forced_piece(state, piece_entry)
            if generated_id:
                candidates = [generated_id]

        if not candidates:
            continue

        candidates = sorted(candidates)
        seed = _stable_seed64(
            state.meta.rng_seed,
            "forced_place",
            piece_key,
            state.world.lore_placements.eval_seq,
            int(state.clock.t),
        )
        selected = random.Random(seed).choice(candidates)
        _assign_piece_to_node(state, piece_entry, selected)


def _evaluate_non_forced_pieces(state, piece_entries: list[dict]) -> None:
    inject_p = max(0.0, min(1.0, float(getattr(Balance, "LORE_NON_FORCED_INJECT_P", Balance.LORE_SINGLES_BASE_P))))
    for piece_entry in piece_entries:
        if piece_entry.get("force", False):
            continue
        piece_key = piece_entry["piece_key"]
        if piece_key in state.world.lore_placements.piece_to_node:
            continue

        roll_seed = _stable_seed64(
            state.meta.rng_seed,
            "non_forced_eval",
            piece_key,
            state.world.lore_placements.eval_seq,
            int(state.clock.t),
        )
        if random.Random(roll_seed).random() >= inject_p:
            continue

        candidates = _candidate_nodes_for_piece(state, piece_entry)
        if not candidates:
            continue
        candidates = sorted(candidates)
        pick_seed = _stable_seed64(
            state.meta.rng_seed,
            "non_forced_pick",
            piece_key,
            state.world.lore_placements.eval_seq,
            int(state.clock.t),
        )
        selected = random.Random(pick_seed).choice(candidates)
        _assign_piece_to_node(state, piece_entry, selected)


def run_lore_scheduler_tick(state) -> None:
    sync_node_pools_for_known_nodes(state)
    close_windows_for_visited_nodes(state)
    recompute_all_node_completion(state)

    pieces = _iter_all_pieces()
    _evaluate_forced_pieces(state, pieces)

    if not getattr(Balance, "LORE_SCHEDULER_ENABLED", True):
        return

    interval_years = max(0.0, float(getattr(Balance, "LORE_NON_FORCED_INTERVAL_YEARS", 1.0)))
    interval_s = interval_years * Balance.YEAR_S

    placements = state.world.lore_placements
    if placements.next_non_forced_eval_t <= 0.0:
        placements.next_non_forced_eval_t = state.clock.t

    if interval_s <= 0.0:
        placements.eval_seq += 1
        _evaluate_non_forced_pieces(state, pieces)
        placements.next_non_forced_eval_t = state.clock.t
        recompute_all_node_completion(state)
        return

    while state.clock.t >= placements.next_non_forced_eval_t:
        placements.eval_seq += 1
        _evaluate_non_forced_pieces(state, pieces)
        placements.next_non_forced_eval_t += interval_s

    recompute_all_node_completion(state)


def maybe_deliver_lore(state, trigger: str, ctx: LoreContext, *, count_trigger: bool = True) -> LoreDelivery:
    counters = state.world.lore.counters
    if trigger == "uplink" and count_trigger:
        counters["uplink_count"] = counters.get("uplink_count", 0) + 1
    if trigger == "dock" and count_trigger:
        counters["dock_count"] = counters.get("dock_count", 0) + 1
    if trigger == "salvage_data" and count_trigger:
        counters["salvage_data_count"] = counters.get("salvage_data_count", 0) + 1

    sync_node_pools_for_known_nodes(state)
    result = _deliver_assigned_for_trigger(state, trigger, ctx)
    recompute_all_node_completion(state)
    return result
