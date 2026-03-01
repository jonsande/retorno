from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path

from retorno.config.balance import Balance
from retorno.model.events import Event, EventType, Severity, SourceRef
from retorno.model.os import AccessLevel, FSNode, FSNodeType, normalize_path, register_mail
from retorno.model.world import add_known_link, record_intel, sector_id_for_pos
from retorno.runtime.data_loader import load_arcs, load_singles


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


def _content_from_ref(content_ref: str | None) -> str:
    if not content_ref:
        return ""
    path = Path(__file__).resolve().parents[3] / "data" / content_ref
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


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


def _delivery_channel_for_trigger(allowed: list[str], trigger: str) -> str | None:
    if "uplink" in allowed and "uplink_only" not in allowed:
        allowed = list(allowed) + ["uplink_only"]
    prefs = {
        "uplink": ["uplink_only", "captured_signal", "ship_os_mail"],
        "dock": ["station_broadcast", "ship_os_mail", "captured_signal"],
        "salvage_data": ["salvage_data", "ship_os_mail", "captured_signal"],
    }.get(trigger, [])
    for channel in prefs:
        if channel in allowed:
            return channel
    return None


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
    if deadline.get("max_salvage_data") is not None and counters.get("salvage_data_count", 0) >= int(deadline.get("max_salvage_data")):
        return True
    if deadline.get("max_salvage_data") is not None and counters.get("salvage_data_count", 0) >= int(deadline.get("max_salvage_data")) * near:
        return True
    return False


def _soft_force_roll(state, piece: dict) -> bool:
    counters = state.world.lore.counters
    total = sum(counters.values())
    year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
    p = min(0.5, 0.1 + total * 0.02 + year * 0.02)
    seed = hash((state.meta.rng_seed, "lore_soft", piece.get("id"), total))
    return random.Random(seed).random() < p


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
        line = piece.get("line", "")
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
    if channel == "ship_os_mail":
        path = deliver_ship_mail(state, piece.get(f"content_ref_{lang}") or piece.get("content_ref_en"), lang)
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
        path = deliver_captured_signal(state, piece.get(f"content_ref_{lang}") or piece.get("content_ref_en"), lang)
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
        path = deliver_station_broadcast(state, ctx.node_id, piece.get(f"content_ref_{lang}") or piece.get("content_ref_en"), lang)
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
        path_template = piece.get("path_template", "")
        path = path_template.replace("{lang}", lang)
        content = _content_from_ref(piece.get(f"content_ref_{lang}") or piece.get("content_ref_en"))
        if path:
            delivered_files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})
        return LoreDelivery(delivered_files, events)
    return LoreDelivery(delivered_files, events)


def maybe_deliver_lore(state, trigger: str, ctx: LoreContext) -> LoreDelivery:
    delivered_files: list[dict] = []
    events: list[Event] = []
    counters = state.world.lore.counters
    if trigger == "uplink":
        counters["uplink_count"] = counters.get("uplink_count", 0) + 1
    if trigger == "dock":
        counters["dock_count"] = counters.get("dock_count", 0) + 1
    if trigger == "salvage_data":
        counters["salvage_data_count"] = counters.get("salvage_data_count", 0) + 1

    arcs = load_arcs()
    # Forced pieces first
    for arc in arcs:
        arc_id = arc.get("arc_id", "")
        if not arc_id:
            continue
        primary = arc.get("primary_intel", {})
        pieces = []
        if primary:
            pieces.append(("primary", primary))
        for doc in arc.get("secondary_lore_docs", []) or []:
            pieces.append((doc.get("id", "secondary"), doc))
        for piece_key, piece in pieces:
            pid = piece.get("id") or f"{arc_id}:{piece_key}"
            key = f"{arc_id}:{pid}"
            if key in state.world.lore.delivered:
                continue
            if not piece.get("force"):
                continue
            if not piece_constraints_ok(piece, ctx):
                continue
            policy = piece.get("force_policy", "none")
            if policy == "none":
                continue
            if policy == "deadline" and not _deadline_reached(state, piece):
                continue
            if policy == "soft" and not _soft_force_roll(state, piece):
                continue
            allowed = piece.get("allowed_channels") or ["salvage_data", "ship_os_mail", "captured_signal", "station_broadcast", "uplink_only"]
            channel = _delivery_channel_for_trigger(allowed, trigger)
            if not channel:
                continue
            result = _deliver_piece(state, arc_id, pid, piece, channel, ctx, is_primary=(piece_key == "primary"))
            delivered_files.extend(result.files)
            events.extend(result.events)
            state.world.lore.delivered.add(key)
            state.world.lore.last_delivery_t = state.clock.t
            return LoreDelivery(delivered_files, events)

    # Singles (weighted, low probability)
    singles = load_singles()
    if singles:
        seed = hash((state.meta.rng_seed, "singles", trigger, int(state.clock.t)))
        rng = random.Random(seed)
        if rng.random() < Balance.LORE_SINGLES_BASE_P:
            pool = [(s.get("single_id"), float(s.get("weight", 1.0)), s) for s in singles]
            total = sum(w for _sid, w, _s in pool if w > 0)
            if total > 0:
                roll = rng.uniform(0, total)
                upto = 0.0
                picked = None
                for sid, w, s in pool:
                    if w <= 0:
                        continue
                    upto += w
                    if roll <= upto:
                        picked = s
                        break
                if picked:
                    single_id = picked.get("single_id")
                    if single_id and single_id not in state.world.lore.delivered:
                        if not piece_constraints_ok(picked, ctx):
                            return delivered_files
                        allowed = picked.get("channels") or ["captured_signal"]
                        channel = _delivery_channel_for_trigger(allowed, trigger)
                        if not channel:
                            return LoreDelivery(delivered_files, events)
                        # singles use first file entry
                        file_entry = (picked.get("files") or [{}])[0]
                        piece = {
                            "id": single_id,
                            "path_template": file_entry.get("path_template", ""),
                            "content_ref_en": file_entry.get("content_ref_en"),
                            "content_ref_es": file_entry.get("content_ref_es"),
                        }
                        result = _deliver_piece(state, "", single_id, piece, channel, ctx, is_primary=False)
                        delivered_files.extend(result.files)
                        events.extend(result.events)
                        state.world.lore.delivered.add(single_id)
                        state.world.lore.last_delivery_t = state.clock.t
    return LoreDelivery(delivered_files, events)
