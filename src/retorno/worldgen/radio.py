"""Opt-in transmitter declarations and a derived, bounded spatial index.

Hosts are resolved by the historical manifest. This module owns no geography,
gameplay ledger or mutable process cache. Narrative references remain gated by
the existing scheduler and interaction triggers.
"""
from __future__ import annotations

from dataclasses import asdict
import itertools
import math
import re

from retorno.config.balance import Balance
from retorno.model.world import RadioEmitter, RadioEmission
from retorno.worldgen import manifest
from retorno.worldgen.narrative import ContentError, _fields, _list, fingerprint

VERSION = "radio-emitters-v1"


def physical_catalog(catalog):
    """Strip only the additive radio contract before hashing physical content.

    For pre-radio catalogues this is byte-for-byte the old canonical input.
    Emission changes still participate in the full installed catalogue hash.
    """
    def strip(value):
        if isinstance(value, list):
            return [strip(v) for v in value]
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in {"radio_emitters", "radio_emission"}}
        return value
    return strip(catalog)


def rules_key():
    return fingerprint({k: v for k, v in vars(Balance).items() if k.startswith("RADIO_") and k != "RADIO_CANDIDATES_PER_TICK"})


def navigation_content(source, target):
    return {"en": f"LOCAL NAVIGATION NOTICE\n\nLINK: {source} -> {target}\n",
            "es": f"AVISO LOCAL DE NAVEGACIÓN\n\nLINK: {source} -> {target}\n"}


def certified_host(definition, host_id):
    site = manifest.resolve_operative_id(definition, host_id)
    if site is None or site.kind not in {"station", "relay", "waystation", "ship", "derelict"}:
        raise ValueError("host: certified historical installation required")
    return site


def build_index(definition, emitters):
    """One cell per emitter at a power tier covering UPGRADED sensitivity.

    Each query touches at most 27 cells per occupied tier. The cell size is at
    least the largest receivable radius; emitter coordinates remain manifest-owned.
    """
    index = {}
    maximum = max(Balance.RADIO_SENSITIVITY.values())
    for ident, emitter in sorted(emitters.items()):
        site = certified_host(definition, emitter.host_id)
        tier = math.ceil(math.log2(math.sqrt(emitter.power * maximum)))
        cell = tuple(math.floor(v / (2.0**tier)) for v in site.position_ly)
        index.setdefault(tier, {}).setdefault(cell, []).append(ident)
    return {tier: {cell: tuple(ids) for cell, ids in cells.items()} for tier, cells in index.items()}


def compile_radio(definition, snapshot):
    emitters, emissions, pieces, references = {}, {}, {}, {}
    for arc in snapshot["arcs"]:
        if arc.get("primary_intel"):
            piece = arc["primary_intel"]
            pieces[f"arc:{arc['arc_id']}:{piece.get('id', 'primary')}"] = piece
        for piece in arc.get("secondary_lore_docs", []):
            pieces[f"arc:{arc['arc_id']}:{piece.get('id', 'secondary')}"] = piece
    for piece in snapshot["singles"]:
        pieces[f"single:{piece['single_id']}"] = piece
    for key, piece in pieces.items():
        if "radio_emission" in piece:
            ref = piece["radio_emission"]
            if not isinstance(ref, str) or not ref:
                raise ContentError("catalog", key, "radio_emission", "emission ID required")
            if ref in references:
                raise ContentError("catalog", key, "radio_emission", "emission already bound to another piece")
            references[ref] = key

    def resolve(token, source, entity, field):
        if not isinstance(token, str) or not token:
            raise ContentError(source, entity, field, "host ID or alias required")
        ident = snapshot["aliases"].get(token.casefold(), token)
        try:
            certified_host(definition, ident)
        except ValueError as exc:
            raise ContentError(source, entity, field, str(exc)) from exc
        return ident

    def identity(value, source, entity, field):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", value):
            raise ContentError(source, entity, field, "stable ASCII ID required (1–128 characters)")
        return value

    for kind in ("locations", "arcs", "singles"):
        for package in snapshot[kind]:
            if "radio_emitters" not in package:
                continue
            raw = package["radio_emitters"]
            package_id = package["node"]["node_id"] if kind == "locations" else package["arc_id" if kind == "arcs" else "single_id"]
            prefix = {"locations": "location", "arcs": "arc", "singles": "single"}[kind]
            source = f"{kind}:{package_id} ({snapshot['sources'].get(f'{prefix}:{package_id}', 'catalog')})"
            _fields(raw, {"version", "emitters"}, source, package_id, "radio_emitters")
            if raw.get("version") != VERSION:
                raise ContentError(source, package_id, "radio_emitters.version", "unsupported version")
            for entry in _list(raw.get("emitters"), source, package_id, "radio_emitters.emitters"):
                _fields(entry, {"id", "host", "category", "power", "emissions"}, source, package_id, "radio_emitters.emitters")
                ident = identity(entry.get("id"), source, package_id, "emitter.id")
                if ident in emitters:
                    raise ContentError(source, ident, "emitter.id", "duplicate transmitter")
                host = resolve(entry.get("host"), source, ident, "emitter.host")
                category = entry.get("category")
                if not isinstance(category, str) or category not in Balance.RADIO_POWER_BY_CATEGORY:
                    raise ContentError(source, ident, "emitter.category", "unsupported transmitter category")
                try:
                    emitter = RadioEmitter(ident, host, category, entry.get("power", Balance.RADIO_POWER_BY_CATEGORY.get(category)))
                except (ValueError, TypeError) as exc:
                    raise ContentError(source, ident, "emitter", str(exc)) from exc
                emitters[ident] = emitter
                declared = _list(entry.get("emissions", []), source, ident, "emissions")
                if len(declared) > Balance.RADIO_MAX_EMISSIONS_PER_EMITTER:
                    raise ContentError(source, ident, "emissions", "transmitter emission budget exceeded")
                for item in declared:
                    _fields(item, {"id", "mode", "start_t", "end_t", "channel", "content_by_locale", "piece_key", "navigation_link_to", "time_reference"}, source, ident, "emissions")
                    eid = identity(item.get("id"), source, ident, "emission.id")
                    if eid in emissions:
                        raise ContentError(source, eid, "emission.id", "duplicate emission")
                    payloads = set(item) & {"content_by_locale", "piece_key", "navigation_link_to"}
                    if len(payloads) != 1:
                        raise ContentError(source, eid, "emission.content", "exactly one content, piece reference or navigation link required")
                    content = item.get("content_by_locale", {})
                    target = item.get("navigation_link_to")
                    piece_key = item.get("piece_key")
                    if "content_by_locale" in item:
                        if (not isinstance(content, dict) or set(content) != {"en", "es"}
                                or not all(isinstance(v, str) and v.strip() for v in content.values())):
                            raise ContentError(source, eid, "content_by_locale", "nonempty EN/ES text required")
                        if any(re.search(r"\{\{[a-z][a-z0-9_]*\}\}", value) for value in content.values()):
                            raise ContentError(source, eid, "content_by_locale", "unbound spatial token in radio payload")
                    if "navigation_link_to" in item:
                        target = resolve(target, source, eid, "navigation_link_to")
                        if target == host:
                            raise ContentError(source, eid, "navigation_link_to", "self link")
                        distance = math.dist(certified_host(definition, host).position_ly, certified_host(definition, target).position_ly)
                        if not 0 < distance <= Balance.MAX_ROUTE_HOP_LY:
                            raise ContentError(source, eid, "navigation_link_to", "link outside navigation cap")
                        content = navigation_content(host, target)
                    if "piece_key" in item:
                        if not isinstance(piece_key, str) or piece_key not in pieces or references.get(eid) != piece_key:
                            raise ContentError(source, eid, "piece_key", "matching installed piece.radio_emission required")
                        piece = pieces[piece_key]
                        channels = piece.get("channels", piece.get("allowed_channels", []))
                        channel = item.get("channel", "captured_signal")
                        if channels != [channel] or (channel == "ship_os_mail" and piece.get("mail_origin") != "external"):
                            raise ContentError(source, eid, "channel", "opt-in piece reference requires exactly this radio channel")
                    try:
                        emission = RadioEmission(eid, ident, item.get("mode"), item.get("start_t"), item.get("end_t"),
                            item.get("channel", "captured_signal"), content, piece_key, target,
                            item.get("time_reference", "game-coordinate-seconds-v1"))
                    except (ValueError, TypeError) as exc:
                        raise ContentError(source, eid, "emission", str(exc)) from exc
                    if emission.channel == "station_broadcast" and certified_host(definition, host).kind not in {"station", "relay", "waystation"}:
                        raise ContentError(source, eid, "channel", "station broadcast needs an installation host")
                    emissions[eid] = emission
    if any(ref not in emissions or emissions[ref].piece_key != key for ref, key in references.items()):
        raise ContentError("catalog", "radio", "radio_emission", "unresolved emission reference")
    by_emitter = {ident: tuple(eid for eid, emission in sorted(emissions.items()) if emission.emitter_id == ident) for ident in emitters}
    snapshot.update(radio_emitters=emitters, radio_emissions=emissions, radio_emissions_by_emitter=by_emitter,
        radio_index=build_index(definition, emitters), radio_rules_key=rules_key() if emitters else "")


def query_emitters(state, *, cursor=None, limit=None):
    """Return one bounded page, next cursor and completeness; pure query.

    An incomplete page never asserts absence. Cursor identifies bucket layout
    and advances over tuple slices without copying/scanning whole buckets.
    """
    limit = Balance.RADIO_CANDIDATES_PER_TICK if limit is None else limit
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError("Invalid radio query budget")
    position = state.world.current_pos_ly
    if len(position) != 3 or not all(math.isfinite(v) for v in position):
        raise ValueError("Invalid receiver coordinates")
    index = state.world.narrative_snapshot.get("radio_index", {})
    groups, anchor = [], []
    for tier, cells in sorted(index.items()):
        cell = tuple(math.floor(v / (2.0**tier)) for v in position)
        anchor.append((tier, cell))
        for offset in itertools.product((-1, 0, 1), repeat=3):
            group = cells.get(tuple(a+b for a,b in zip(cell, offset)), ())
            if group:
                groups.append(group)
    total = sum(map(len, groups))
    key = tuple(anchor)
    cursor = cursor or {}
    start = cursor.get("offset", 0) if cursor.get("anchor") == key else 0
    start = start % total if total else 0
    size = min(total, limit)
    result = []
    for left, right in ((start, min(total, start+size)), (0, max(0, start+size-total))):
        base = 0
        for group in groups:
            low, high = max(0, left-base), min(len(group), right-base)
            if high > low:
                result.extend(group[low:high])
            base += len(group)
    return tuple(result), {"anchor": key, "offset": (start+size) % total if total else 0}, total <= limit


def validate_radio_catalog(state):
    snapshot = state.world.narrative_snapshot
    emitters = snapshot.get("radio_emitters", {})
    if not emitters and not snapshot.get("radio_emissions"):
        return  # Safe additive default for schema 3 before radio declarations.
    if snapshot.get("radio_rules_key") != rules_key():
        raise ValueError("Radio configuration changed / Configuración de radio modificada")
    from retorno.worldgen.generator import universe_definition
    definition = universe_definition(state)
    for ident, emitter in emitters.items():
        if not isinstance(emitter, RadioEmitter) or ident != emitter.emitter_id:
            raise ValueError("Invalid radio emitter identity / Identidad de emisor no válida")
        RadioEmitter(**asdict(emitter))
        certified_host(definition, emitter.host_id)
    for ident, emission in snapshot.get("radio_emissions", {}).items():
        if not isinstance(emission, RadioEmission) or ident != emission.emission_id or emission.emitter_id not in emitters:
            raise ValueError("Invalid radio emission identity / Identidad de emisión no válida")
        RadioEmission(**asdict(emission))
    if snapshot.get("radio_index") != build_index(definition, emitters):
        raise ValueError("Radio index contradicts manifest / Índice de radio incompatible con manifiesto")
    by_emitter = {ident: tuple(eid for eid, emission in sorted(snapshot["radio_emissions"].items()) if emission.emitter_id == ident) for ident in emitters}
    if snapshot.get("radio_emissions_by_emitter") != by_emitter:
        raise ValueError("Radio emission index mismatch / Índice de emisiones incompatible")
