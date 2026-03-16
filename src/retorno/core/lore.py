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
    is_hop_within_cap,
    record_intel,
    region_for_pos,
    sector_id_for_pos,
)
from retorno.runtime.data_loader import load_arcs, load_locations, load_singles
from retorno.worldgen.generator import (
    _generate_node_id,
    _name_from_node_id,
    ensure_sector_generated,
    procedural_radiation_for_node,
    sync_sector_state_for_node,
)


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


def _mail_envelope_content(
    content: str,
    *,
    mail_from: str | None = None,
    mail_subject: str | None = None,
) -> str:
    lines = content.splitlines()
    probe = [ln.strip() for ln in lines[:12]]
    has_from = any(ln.upper().startswith("FROM:") for ln in probe)
    has_subj = any(ln.upper().startswith("SUBJ:") for ln in probe)

    headers: list[str] = []
    if mail_from and not has_from:
        headers.append(f"FROM: {mail_from}")
    if mail_subject and not has_subj:
        headers.append(f"SUBJ: {mail_subject}")
    if not headers:
        return content
    body = content.lstrip("\n")
    if body:
        return "\n".join(headers) + "\n\n" + body
    return "\n".join(headers) + "\n"


def deliver_ship_mail(
    state,
    content_ref: str,
    lang: str,
    *,
    mail_from: str | None = None,
    mail_subject: str | None = None,
) -> str:
    _ensure_dir(state.os.fs, "/mail")
    _ensure_dir(state.os.fs, "/mail/inbox")
    seq = state.events.next_event_seq
    path = normalize_path(f"/mail/inbox/{seq:04d}.{lang}.txt")
    content = _content_from_ref(content_ref)
    content = _mail_envelope_content(
        content,
        mail_from=mail_from,
        mail_subject=mail_subject,
    )
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


def write_local_intel(
    state,
    channel: str,
    content: str,
    *,
    node_id: str | None = None,
    source: SourceRef | None = None,
    mail_from: str | None = None,
    mail_subject: str | None = None,
) -> tuple[str, Event]:
    seq = state.events.next_event_seq
    locale = state.os.locale.value
    source = source or SourceRef(kind="world", id=node_id or state.world.current_node_id)

    if channel == "captured_signal":
        _ensure_dir(state.os.fs, "/logs")
        _ensure_dir(state.os.fs, "/logs/signals")
        path = normalize_path(f"/logs/signals/{seq:04d}.{locale}.txt")
        state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
        msg = {
            "en": f"signal_captured :: Signal captured: {path} (hint: cat {path})",
            "es": f"signal_captured :: Señal capturada: {path} (pista: cat {path})",
        }.get(locale, f"signal_captured :: Signal captured: {path}")
        event = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=EventType.SIGNAL_CAPTURED,
            severity=Severity.INFO,
            source=source,
            message=msg,
            data={"path": path},
        )
        state.events.next_event_seq += 1
        return path, event

    if channel == "station_broadcast":
        _ensure_dir(state.os.fs, "/logs")
        _ensure_dir(state.os.fs, "/logs/broadcasts")
        base_node_id = node_id or state.world.current_node_id
        path = normalize_path(f"/logs/broadcasts/{base_node_id}_{seq:04d}.{locale}.txt")
        state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
        msg = {
            "en": f"broadcast_received :: Station broadcast: {path}",
            "es": f"broadcast_received :: Emisión recibida: {path}",
        }.get(locale, f"broadcast_received :: Station broadcast: {path}")
        event = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=EventType.BROADCAST_RECEIVED,
            severity=Severity.INFO,
            source=source,
            message=msg,
            data={"path": path},
        )
        state.events.next_event_seq += 1
        return path, event

    if channel == "ship_os_mail":
        _ensure_dir(state.os.fs, "/mail")
        _ensure_dir(state.os.fs, "/mail/inbox")
        path = normalize_path(f"/mail/inbox/{seq:04d}.{locale}.txt")
        body = _mail_envelope_content(content, mail_from=mail_from, mail_subject=mail_subject)
        state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=body, access=AccessLevel.GUEST)
        register_mail(state.os, path, state.clock.t)
        msg = {
            "en": f"mail_received :: New internal memo queued: {path}",
            "es": f"mail_received :: Nuevo memo interno en cola: {path}",
        }.get(locale, f"mail_received :: New mail received: {path}")
        event = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=EventType.MAIL_RECEIVED,
            severity=Severity.INFO,
            source=source,
            message=msg,
            data={"path": path},
        )
        state.events.next_event_seq += 1
        return path, event

    if channel == "uplink_trace":
        _ensure_dir(state.os.fs, "/logs")
        _ensure_dir(state.os.fs, "/logs/nav")
        base_node_id = node_id or state.world.current_node_id
        path = normalize_path(f"/logs/nav/uplink_trace_{base_node_id}_{seq:05d}.txt")
        state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.GUEST)
        msg = {
            "en": f"uplink_trace :: Degraded route table recovered: {path} (hint: cat {path})",
            "es": f"uplink_trace :: Tabla degradada recuperada: {path} (pista: cat {path})",
        }.get(locale, f"uplink_trace :: Degraded route table recovered: {path}")
        event = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=EventType.UPLINK_TRACE_RECEIVED,
            severity=Severity.INFO,
            source=source,
            message=msg,
            data={"path": path},
        )
        state.events.next_event_seq += 1
        return path, event

    raise ValueError(f"Unsupported local intel channel: {channel}")


def _known_node_ids(state) -> list[str]:
    known_nodes = set(getattr(state.world, "known_nodes", set()) or set())
    known_contacts = set(getattr(state.world, "known_contacts", set()) or set())
    return sorted(known_nodes | known_contacts)


def _pool_seed_node_ids(state) -> list[str]:
    known = set(_known_node_ids(state))
    hidden = set(getattr(state.world, "forced_hidden_nodes", set()) or set())
    anchors = {
        str(getattr(state.world, "current_node_id", "") or "").strip(),
        str(getattr(state.ship, "current_node_id", "") or "").strip(),
        str(getattr(state.ship, "docked_node_id", "") or "").strip(),
    }
    anchors.discard("")
    return sorted(known | hidden | anchors)


def _is_hidden_origin_placeholder(node_id: str) -> bool:
    return node_id == "UNKNOWN" or node_id.startswith("UNKNOWN_")


def _location_node_ids() -> set[str]:
    out: set[str] = set()
    for loc in load_locations():
        node_cfg = loc.get("node", {})
        nid = str(node_cfg.get("node_id", "")).strip()
        if nid:
            out.add(nid)
    return out


def _location_uplink_table(node_id: str) -> dict | None:
    for loc in load_locations():
        node_cfg = loc.get("node", {})
        if str(node_cfg.get("node_id", "")).strip() != node_id:
            continue
        uplink_table = loc.get("uplink_table")
        if isinstance(uplink_table, dict):
            return uplink_table
        return None
    return None


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
        sx, sy, sz = sector_id[1:].split("_")
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
    ensure_sector_generated(state, current_sector)

    routes = set(state.world.known_links.get(node_id, set()))
    locked_primary_targets = _locked_primary_targets(state)
    authored_ids = _location_node_ids()
    hub_kinds = {"relay", "station", "waystation"}
    deterministic = Balance.DETERMINISTIC_LORE_INTEL
    candidates: dict[str, int] = {}
    selected: list[str] = []
    uplink_cfg = _location_uplink_table(node_id) or {}
    authored_pool = uplink_cfg.get("authored_candidates") or []
    try:
        min_authored = int(uplink_cfg.get("min_authored", 0) or 0)
    except Exception:
        min_authored = 0
    try:
        max_authored = int(uplink_cfg.get("max_authored", 0) or 0)
    except Exception:
        max_authored = 0

    def _add_candidate(nid: str, weight: int) -> None:
        if _is_hidden_origin_placeholder(nid):
            return
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
        if n and n.is_hub:
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

    max_authored = max(0, min(max_new, max_authored))
    min_authored = max(0, min(max_new, min_authored))
    if max_authored < min_authored:
        max_authored = min_authored

    authored_weights: list[tuple[str, int]] = []
    for entry in authored_pool:
        if not isinstance(entry, dict):
            continue
        dest = str(entry.get("node_id", "")).strip()
        if (
            not dest
            or _is_hidden_origin_placeholder(dest)
            or dest == node_id
            or dest in routes
            or dest in locked_primary_targets
        ):
            continue
        if dest not in authored_ids or dest not in state.world.space.nodes:
            continue
        try:
            weight = int(entry.get("weight", 1))
        except Exception:
            weight = 1
        authored_weights.append((dest, max(1, weight)))

    if not candidates and not authored_weights:
        return []

    seed = _stable_seed64(
        state.meta.rng_seed,
        "uplink_pool",
        node_id,
        int(state.clock.t),
        len(candidates),
        len(authored_weights),
    )
    rng = random.Random(seed)

    authored_pick_count = min(max_authored, len(authored_weights))
    authored_pool_weighted = sorted(authored_weights) if deterministic else list(authored_weights)
    while authored_pool_weighted and len(selected) < authored_pick_count:
        total = sum(weight for _, weight in authored_pool_weighted)
        if total <= 0:
            break
        roll = rng.uniform(0, total)
        upto = 0.0
        picked_index = 0
        for i, (_, weight) in enumerate(authored_pool_weighted):
            upto += weight
            if roll <= upto:
                picked_index = i
                break
        dest, _weight = authored_pool_weighted.pop(picked_index)
        if dest in selected or dest == node_id:
            continue
        selected.append(dest)

    if min_authored > 0 and len(selected) < min_authored:
        for dest, _weight in authored_pool_weighted:
            if dest in selected or dest == node_id:
                continue
            selected.append(dest)
            if len(selected) >= min_authored:
                break

    for dest in selected:
        candidates.pop(dest, None)

    pool = sorted(candidates.items()) if deterministic else list(candidates.items())
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
    has_link_intel = False

    p_log = (
        Balance.SALVAGE_DATA_LOG_P_STATION_SHIP
        if node.kind in {"station", "ship"}
        else Balance.SALVAGE_DATA_LOG_P_OTHER
    )
    if link_line and rng.random() < p_log:
        _add("/logs/nav.log", link_line)
        has_link_intel = True

    p_mail = (
        Balance.SALVAGE_DATA_MAIL_P_STATION_SHIP
        if node.kind in {"station", "ship"}
        else Balance.SALVAGE_DATA_MAIL_P_OTHER
    )
    if rng.random() < p_mail:
        lang = state.os.locale.value
        content = build_procedural_salvage_mail_content(state, node)
        _add(f"/mail/inbox/0001.{lang}.txt", content)

    p_frag = (
        Balance.SALVAGE_DATA_FRAG_P_STATION_DERELICT
        if node.kind in {"station", "derelict"}
        else Balance.SALVAGE_DATA_FRAG_P_OTHER
    )
    if link_line and rng.random() < p_frag:
        frag_id = f"{rng.getrandbits(16):04x}"
        if not has_link_intel:
            _add(f"/data/nav/fragments/frag_{frag_id}.txt", link_line)
            has_link_intel = True

    if link_line and not has_link_intel:
        frag_id = f"{rng.getrandbits(16):04x}"
        _add(f"/data/nav/fragments/frag_{frag_id}.txt", link_line)

    return files


def _dominant_peer_kind(state, node: SpaceNode) -> str:
    counts: dict[str, int] = {}
    for peer_id in sorted(node.links):
        peer = state.world.space.nodes.get(peer_id)
        kind = str(getattr(peer, "kind", "") or "unknown").strip().lower() or "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    if not counts:
        return "none"
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def build_procedural_salvage_mail_content(state, node: SpaceNode) -> str:
    lang = str(getattr(state.os.locale, "value", "en") or "en").lower()
    seed = _stable_seed64(getattr(state.meta, "rng_seed", 0), node.node_id, "salvage_mail_v1")
    rng = random.Random(seed)

    subject_by_kind = {
        "station": {"en": "Recovered Waystation Cache", "es": "Cache recuperada de estación"},
        "ship": {"en": "Recovered Vessel Cache", "es": "Cache recuperada de nave"},
        "derelict": {"en": "Recovered Derelict Cache", "es": "Cache recuperada de derrelicto"},
    }
    subject = subject_by_kind.get(node.kind, {"en": "Recovered Data Cache", "es": "Cache de datos recuperada"})
    report_id = f"{node.node_id}-{rng.getrandbits(20):05X}"
    cache_integrity = int(rng.uniform(58.0, 98.0))
    sync_lag_h = int(rng.uniform(2.0, 180.0))
    clock_drift_ms = rng.randint(-420, 420)
    peers_total = len(node.links)
    peers_responsive = min(peers_total, int(round(peers_total * rng.uniform(0.35, 0.90))))
    handshake_age_h = int(rng.uniform(1.0, 72.0))
    route_fragments = 1 if peers_total > 0 else 0
    signal_quality = rng.choice(["low", "degraded", "nominal", "strong"])
    signal_quality_es = {
        "low": "baja",
        "degraded": "degradada",
        "nominal": "nominal",
        "strong": "alta",
    }[signal_quality]
    dominant_peer_kind = _dominant_peer_kind(state, node)
    dominant_peer_kind_es = {
        "station": "estación",
        "ship": "nave",
        "relay": "relé",
        "waystation": "estación intermedia",
        "derelict": "derrelicto",
        "none": "ninguna",
        "unknown": "desconocida",
    }.get(dominant_peer_kind, dominant_peer_kind)

    if node.radiation_rad_per_s < 0.002:
        rad_band_en, rad_band_es = "low", "baja"
    elif node.radiation_rad_per_s < 0.01:
        rad_band_en, rad_band_es = "elevated", "elevada"
    else:
        rad_band_en, rad_band_es = "high", "alta"

    traffic_bias = rng.choice(["inbound", "outbound", "mixed"])
    traffic_bias_es = {"inbound": "entrante", "outbound": "saliente", "mixed": "mixto"}[traffic_bias]
    intro_by_kind_en = {
        "station": "Maintenance relay resumed from cold storage; publishing cached telemetry snapshot.",
        "ship": "Vessel bus came online in degraded mode; exporting retained bridge telemetry.",
        "derelict": "Passive recorder woke on salvage power; partial black-box telemetry attached.",
    }
    intro_by_kind_es = {
        "station": "Relé de mantenimiento reanudado desde frío; publicando instantánea de telemetría en caché.",
        "ship": "Bus de nave reactivado en modo degradado; exportando telemetría retenida de puente.",
        "derelict": "Registrador pasivo reactivado por energía de salvage; telemetría parcial de caja negra adjunta.",
    }
    closure_by_kind_en = {
        "station": "Advisory: prioritize relay-class contacts for faster route reconstruction.",
        "ship": "Advisory: cross-check nav fragments before committing long-burn transfer windows.",
        "derelict": "Advisory: expect stale beacons and broken timing; validate routes incrementally.",
    }
    closure_by_kind_es = {
        "station": "Aviso: prioriza contactos tipo relé para reconstruir rutas más rápido.",
        "ship": "Aviso: contrasta fragmentos nav antes de comprometer ventanas de transferencia largas.",
        "derelict": "Aviso: espera balizas obsoletas y tiempos rotos; valida rutas de forma incremental.",
    }
    region_hints_en = {
        "bulge": [
            "Traffic cadence trends coreward; short-hop relays are likely nearby.",
            "Beacon drift suggests an inner-lane handoff window.",
        ],
        "disk": [
            "Lane timing looks cyclical; check adjacent sectors after fresh survey pings.",
            "Transit rhythm matches regular corridor traffic rather than deep-space drift.",
        ],
        "halo": [
            "Sparse beacons; long silent intervals likely mask viable links.",
            "Outer-lane packets arrive bursty; repeated salvage passes may reveal more.",
        ],
    }
    region_hints_es = {
        "bulge": [
            "La cadencia del tráfico apunta hacia el núcleo; es probable que haya relés de salto corto cerca.",
            "La deriva de balizas sugiere una ventana de relevo en carriles internos.",
        ],
        "disk": [
            "El patrón de carriles parece cíclico; revisa sectores adyacentes tras nuevos sondeos.",
            "El ritmo de tránsito encaja con tráfico regular de corredor, no con deriva profunda.",
        ],
        "halo": [
            "Balizas escasas; intervalos largos de silencio pueden ocultar enlaces viables.",
            "Los paquetes de carriles externos llegan en ráfagas; repetir salvage puede revelar más.",
        ],
    }
    generic_hint_en = "Telemetry confidence is moderate; corroborate with logs/fragments before committing route fuel."
    generic_hint_es = "La confianza de telemetría es moderada; contrástala con logs/fragmentos antes de gastar ruta."
    hints_en = region_hints_en.get(node.region or "", region_hints_en["disk"])
    hints_es = region_hints_es.get(node.region or "", region_hints_es["disk"])
    soft_hint_en = rng.choice(hints_en)
    soft_hint_es = rng.choice(hints_es)
    intro_en = intro_by_kind_en.get(node.kind, "Automated subsystem resumed; exporting cached telemetry.")
    intro_es = intro_by_kind_es.get(node.kind, "Subsistema automático reanudado; exportando telemetría en caché.")
    close_en = closure_by_kind_en.get(node.kind, "Advisory: corroborate cache output with independent scans.")
    close_es = closure_by_kind_es.get(node.kind, "Aviso: corrobora la salida de caché con escaneos independientes.")
    corruption_line_en = ""
    corruption_line_es = ""
    if cache_integrity < 70:
        corruption_line_en = "Integrity flags: segment loss detected; checksum repaired with parity gaps.\n"
        corruption_line_es = "Banderas de integridad: pérdida de segmentos detectada; checksum reparado con huecos de paridad.\n"
    elif cache_integrity < 82:
        corruption_line_en = "Integrity flags: minor frame jitter detected; packet order reconstructed.\n"
        corruption_line_es = "Banderas de integridad: jitter leve de tramas detectado; orden de paquetes reconstruido.\n"

    def _maybe_truncate_line(text: str, chance: float = 0.12) -> str:
        if not text or rng.random() >= chance:
            return text
        clean = text.rstrip("\n")
        if len(clean) < 36:
            return text
        keep = rng.randint(20, max(20, len(clean) - 8))
        return clean[:keep].rstrip() + " [...]\n"

    soft_hint_en = _maybe_truncate_line(soft_hint_en + "\n").rstrip("\n")
    soft_hint_es = _maybe_truncate_line(soft_hint_es + "\n").rstrip("\n")
    generic_hint_en = _maybe_truncate_line(generic_hint_en + "\n", chance=0.08).rstrip("\n")
    generic_hint_es = _maybe_truncate_line(generic_hint_es + "\n", chance=0.08).rstrip("\n")

    if lang == "es":
        return (
            f"FROM: {node.name}\n"
            f"SUBJ: {subject['es']}\n\n"
            f"Informe automático de telemetría desde {node.name} ({node.kind}).\n"
            f"{intro_es}\n"
            f"Región: {node.region}\n"
            f"ID de informe: {report_id}\n"
            f"Integridad de caché: {cache_integrity}%\n"
            f"Retardo de sincronización: {sync_lag_h}h\n"
            f"Deriva de reloj: {clock_drift_ms:+d} ms\n"
            f"Banda de radiación: {rad_band_es} ({node.radiation_rad_per_s:.3f} rad/s)\n"
            f"Calidad de señal: {signal_quality_es}\n\n"
            f"{corruption_line_es}"
            "Estado de red resumido:\n"
            f"- peers indexados: {peers_total}\n"
            f"- peers con respuesta: {peers_responsive}\n"
            f"- fragmentos de ruta en caché: {route_fragments}\n"
            f"- último handshake válido: hace {handshake_age_h}h\n"
            f"- clase de peer dominante: {dominant_peer_kind_es}\n"
            f"- sesgo de tráfico observado: {traffic_bias_es}\n\n"
            f"Pista: {soft_hint_es}\n"
            f"Nota: {generic_hint_es}\n"
            f"{close_es}\n"
        )

    return (
        f"FROM: {node.name}\n"
        f"SUBJ: {subject['en']}\n\n"
        f"Automated telemetry report from {node.name} ({node.kind}).\n"
        f"{intro_en}\n"
        f"Region: {node.region}\n"
        f"Report ID: {report_id}\n"
        f"Cache integrity: {cache_integrity}%\n"
        f"Sync lag: {sync_lag_h}h\n"
        f"Clock drift: {clock_drift_ms:+d} ms\n"
        f"Radiation envelope: {rad_band_en} ({node.radiation_rad_per_s:.3f} rad/s)\n"
        f"Signal quality: {signal_quality}\n\n"
        f"{corruption_line_en}"
        "Network summary:\n"
        f"- indexed peers: {peers_total}\n"
        f"- responsive peers: {peers_responsive}\n"
        f"- route fragments in cache: {route_fragments}\n"
        f"- last successful handshake: {handshake_age_h}h ago\n"
        f"- dominant peer class: {dominant_peer_kind}\n"
        f"- observed traffic bias: {traffic_bias}\n\n"
        f"Hint: {soft_hint_en}\n"
        f"Note: {generic_hint_en}\n"
        f"{close_en}\n"
    )


def build_lore_context(state, node_id: str) -> LoreContext:
    node = state.world.space.nodes.get(node_id)
    if node:
        region = node.region or region_for_pos(node.x_ly, node.y_ly, node.z_ly)
        dist = _distance_from_start_ly(state, node.x_ly, node.y_ly, node.z_ly)
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


def _hard_force_ready(state, piece: dict) -> bool:
    cons = piece.get("constraints") or {}
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    min_year = cons.get("min_year")
    max_year = cons.get("max_year")
    if min_year is not None and year < float(min_year):
        return False
    if max_year is not None and year > float(max_year):
        return False
    return True


def _secondary_count_limit(piece_entry: dict) -> int | None:
    if piece_entry.get("role") != "secondary":
        return None
    rules = piece_entry.get("placement_rules") or {}
    raw = rules.get("count")
    if raw is None:
        return None
    try:
        return max(0, int(raw))
    except Exception:
        return None


def _secondary_assigned_count(state, arc_id: str) -> int:
    if not arc_id:
        return 0
    arc_state = state.world.arc_placements.get(arc_id, {})
    secondary = arc_state.get("secondary")
    if isinstance(secondary, dict):
        return len(secondary)
    return 0


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


def list_lore_piece_entries() -> list[dict]:
    """Public helper for debug/inspection views.

    Returns normalized piece entries with canonical `piece_key` values.
    """
    return _iter_all_pieces()


def _piece_index() -> dict[str, dict]:
    return {entry["piece_key"]: entry for entry in _iter_all_pieces()}


def _start_node_for_hops(state) -> str:
    if "UNKNOWN" in state.world.space.nodes:
        return "UNKNOWN"
    return state.world.current_node_id


def _start_node_for_distance(state) -> SpaceNode | None:
    start_id = _start_node_for_hops(state)
    return state.world.space.nodes.get(start_id)


def _distance_from_start_ly(state, x_ly: float, y_ly: float, z_ly: float) -> float:
    start = _start_node_for_distance(state)
    if not start:
        return math.sqrt(x_ly * x_ly + y_ly * y_ly + z_ly * z_ly)
    dx = x_ly - start.x_ly
    dy = y_ly - start.y_ly
    dz = z_ly - start.z_ly
    return math.sqrt(dx * dx + dy * dy + dz * dz)


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
    channels = [ch for ch in piece_entry.get("channels", []) if _channel_feasible_for_node(ch, node)]
    if not channels:
        return None

    piece = piece_entry.get("piece") or {}
    preferred_sources = piece.get("preferred_sources") or []
    if isinstance(preferred_sources, str):
        preferred_sources = [preferred_sources]
    preferred_sources = [str(src).strip().lower() for src in preferred_sources if str(src).strip()]

    source_to_channels = {
        "mail": ["ship_os_mail"],
        "ship_os_mail": ["ship_os_mail"],
        "log": ["salvage_data"],
        "salvage": ["salvage_data"],
        "salvage_data": ["salvage_data"],
        "signal": ["captured_signal"],
        "captured_signal": ["captured_signal"],
        "broadcast": ["station_broadcast"],
        "station_broadcast": ["station_broadcast"],
        "uplink": ["uplink_only"],
        "uplink_only": ["uplink_only"],
    }
    for source in preferred_sources:
        for preferred_channel in source_to_channels.get(source, []):
            if preferred_channel in channels:
                return preferred_channel

    # Fallback to configured channel order when no preferred source can be honored.
    return channels[0]


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
    log_header = str(piece.get("log_header", "") or "").strip()
    if log_header and normalize_path(path).startswith("/logs/"):
        first_lines = [ln.strip() for ln in content.splitlines()[:8]]
        has_header = any(ln == log_header for ln in first_lines)
        if not has_header:
            body = content.lstrip("\n")
            content = f"{log_header}\n\n{body}" if body else f"{log_header}\n"

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


def _float_constraint(value, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _sample_ad_hoc_coords(
    state,
    rng: random.Random,
    piece: dict,
    anchor: SpaceNode,
) -> tuple[float, float, float] | None:
    cons = piece.get("constraints") or {}
    min_dist = max(0.0, _float_constraint(cons.get("min_dist_ly"), 0.0) or 0.0)
    max_dist = _float_constraint(cons.get("max_dist_ly"))
    regions_any = [str(r).strip() for r in (cons.get("regions_any") or []) if str(r).strip()]

    if max_dist is not None and max_dist < min_dist:
        return None

    # If piece declares spatial constraints, sample around start-node reference so
    # min/max lore distances remain semantically tied to run start.
    has_global_constraints = bool(regions_any) or (cons.get("min_dist_ly") is not None) or (cons.get("max_dist_ly") is not None)
    if has_global_constraints:
        hi = max_dist if max_dist is not None else max(min_dist + 20.0, 40.0)
        if hi < min_dist:
            return None
        start = _start_node_for_distance(state)
        sx = start.x_ly if start else 0.0
        sy = start.y_ly if start else 0.0
        sz = start.z_ly if start else 0.0
        for _ in range(128):
            dist = rng.uniform(min_dist, hi)
            theta = rng.uniform(0.0, math.tau)
            z_span = max(0.2, min(5.0, dist * 0.2))
            dz = rng.uniform(-z_span, z_span)
            z = sz + dz
            planar_sq = max(0.0, dist * dist - dz * dz)
            planar = math.sqrt(planar_sq)
            x = sx + math.cos(theta) * planar
            y = sy + math.sin(theta) * planar
            region = region_for_pos(x, y, z)
            if regions_any and region not in regions_any:
                continue
            return (x, y, z)
        return None

    # No global constraints: keep ad-hoc node near the selected anchor.
    theta = rng.uniform(0.0, math.tau)
    dist = rng.uniform(0.4, 2.0)
    dx = math.cos(theta) * dist
    dy = math.sin(theta) * dist
    dz = rng.uniform(-0.1, 0.1)
    return (anchor.x_ly + dx, anchor.y_ly + dy, anchor.z_ly + dz)


def _eligible_ad_hoc_anchors(state, max_hops: int) -> list[SpaceNode]:
    out: list[SpaceNode] = []
    for node_id in sorted(state.world.space.nodes.keys()):
        node = state.world.space.nodes.get(node_id)
        if not node:
            continue
        if max_hops > 0:
            hop = _hop_distance_from_start(state, node_id, max_hops)
            if hop is None or (hop + 1) > max_hops:
                continue
        out.append(node)
    return out


def _pick_anchor_for_coords(anchors: list[SpaceNode], x: float, y: float, z: float) -> SpaceNode | None:
    if not anchors:
        return None
    ranked = sorted(
        anchors,
        key=lambda a: ((a.x_ly - x) ** 2 + (a.y_ly - y) ** 2 + (a.z_ly - z) ** 2, a.node_id),
    )
    return ranked[0] if ranked else None


def register_hidden_anchored_node(
    state,
    *,
    seed_key: str,
    kind: str,
    anchor_node_id: str,
    x_ly: float,
    y_ly: float,
    z_ly: float,
    force_hub: bool | None = None,
) -> str | None:
    anchor = state.world.space.nodes.get(anchor_node_id)
    if not anchor:
        return None
    dx = anchor.x_ly - x_ly
    dy = anchor.y_ly - y_ly
    dz = anchor.z_ly - z_ly
    if (dx * dx + dy * dy + dz * dz) ** 0.5 > float(Balance.MAX_ROUTE_HOP_LY):
        return None

    region = region_for_pos(x_ly, y_ly, z_ly)
    seed = _stable_seed64(state.meta.rng_seed, "hidden_anchored_node", seed_key, anchor_node_id, kind, x_ly, y_ly, z_ly)
    rng = random.Random(seed)
    is_hub = force_hub if force_hub is not None else kind in {"relay", "station", "waystation"}
    node_id = _generate_node_id(state, kind, rng)
    node = SpaceNode(
        node_id=node_id,
        name=_name_from_node_id(node_id, kind),
        kind=kind,
        radiation_rad_per_s=procedural_radiation_for_node(state.meta.rng_seed, node_id, kind, region),
        radiation_base=0.0,
        region=region,
        x_ly=x_ly,
        y_ly=y_ly,
        z_ly=z_ly,
        is_hub=is_hub,
        is_topology_hub=is_hub,
    )
    node.links.add(anchor.node_id)
    anchor.links.add(node.node_id)
    state.world.space.nodes[node_id] = node
    sync_sector_state_for_node(state, node_id)
    sync_sector_state_for_node(state, anchor.node_id)
    state.world.forced_hidden_nodes.add(node_id)
    sync_node_pools_for_known_nodes(state)
    return node_id


def _spawn_ad_hoc_candidate_for_forced_piece(state, piece_entry: dict) -> str | None:
    if not state.world.space.nodes:
        return None

    piece = piece_entry.get("piece") or {}
    rules = piece_entry.get("placement_rules") or {}
    candidates_cfg = set(str(x) for x in (rules.get("candidates") or []))
    max_hops = int(rules.get("max_hops_from_start", 0) or 0)
    require_kinds = [str(x) for x in (rules.get("require_kind_any") or []) if str(x)]
    allowed_kinds = [k for k in require_kinds if k in {"station", "relay", "derelict", "ship", "waystation"}]
    if not allowed_kinds:
        token_to_kind = {
            "procedural_station": "station",
            "procedural_relay": "relay",
            "procedural_derelict": "derelict",
            "procedural_ship": "ship",
        }
        derived = [token_to_kind[tok] for tok in sorted(candidates_cfg) if tok in token_to_kind]
        allowed_kinds = sorted(set(derived)) if derived else ["station"]

    anchors = _eligible_ad_hoc_anchors(state, max_hops)
    if not anchors:
        return None
    default_anchor = state.world.space.nodes.get(state.world.current_node_id) or anchors[0]

    seed = _stable_seed64(
        state.meta.rng_seed,
        "forced_ad_hoc",
        piece_entry["piece_key"],
        state.world.lore_placements.eval_seq,
    )
    rng = random.Random(seed)

    authored = _location_node_ids()
    kind = allowed_kinds[int(seed % len(allowed_kinds))]
    x_y_z = _sample_ad_hoc_coords(state, rng, piece, default_anchor)
    if not x_y_z:
        return None
    x, y, z = x_y_z
    region = region_for_pos(x, y, z)
    dist_from_origin = _distance_from_start_ly(state, x, y, z)
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    temp_node = SpaceNode(
        node_id="__ADHOC_CANDIDATE__",
        name="",
        kind=kind,
        radiation_rad_per_s=procedural_radiation_for_node(
            state.meta.rng_seed, "__ADHOC_CANDIDATE__", kind, region
        ),
        radiation_base=0.0,
        region=region,
        x_ly=x,
        y_ly=y,
        z_ly=z,
    )
    if not _node_matches_candidates(temp_node.node_id, temp_node, candidates_cfg, authored):
        return None
    if not piece_constraints_ok(
        piece,
        LoreContext(
            node_id=temp_node.node_id,
            region=region,
            dist_from_origin_ly=dist_from_origin,
            year_since_wake=year,
        ),
    ):
        return None

    anchor = _pick_anchor_for_coords(anchors, x, y, z)
    if not anchor:
        return None

    node_id = register_hidden_anchored_node(
        state,
        seed_key=piece_entry["piece_key"],
        kind=kind,
        anchor_node_id=anchor.node_id,
        x_ly=x,
        y_ly=y,
        z_ly=z,
    )
    if not node_id:
        return None
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

    sec_limit = _secondary_count_limit(piece_entry)
    arc_id = str(piece_entry.get("arc_id") or "")
    if sec_limit is not None and _secondary_assigned_count(state, arc_id) >= sec_limit:
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
                if is_hop_within_cap(state.world, left, right, float(Balance.MAX_ROUTE_HOP_LY)):
                    add_known_link(state.world, left, right, bidirectional=True)
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
                        # Unlock primary even when LINK was already known beforehand.
                        _mark_primary_unlocked(state, arc_id, piece)
        return LoreDelivery(delivered_files, events)

    content_ref = _content_ref_for_piece(piece, lang)

    if channel == "ship_os_mail":
        mail_from = str(piece.get("mail_from", "") or "").strip() or None
        mail_subject = str(piece.get("mail_subject", "") or "").strip() or None
        path = deliver_ship_mail(
            state,
            content_ref or "",
            lang,
            mail_from=mail_from,
            mail_subject=mail_subject,
        )
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
        elif policy == "hard":
            should_place = _hard_force_ready(state, piece)

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


def _non_forced_piece_probability(piece_entry: dict) -> float:
    base = max(0.0, min(1.0, float(getattr(Balance, "LORE_NON_FORCED_INJECT_P", Balance.LORE_SINGLES_BASE_P))))
    if piece_entry.get("role") != "single":
        return base
    piece = piece_entry.get("piece") or {}
    try:
        weight = float(piece.get("weight", 1.0))
    except Exception:
        weight = 1.0
    weight = max(0.0, weight)
    return max(0.0, min(1.0, base * weight))


def _evaluate_non_forced_pieces(state, piece_entries: list[dict]) -> None:
    for piece_entry in piece_entries:
        if piece_entry.get("force", False):
            continue
        piece_key = piece_entry["piece_key"]
        if piece_key in state.world.lore_placements.piece_to_node:
            continue

        inject_p = _non_forced_piece_probability(piece_entry)
        if inject_p <= 0.0:
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
