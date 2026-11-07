"""historical-information-v1: bounded, pure projection of certified history.

No GameState, registry, player knowledge, clock, scheduler or mutable RNG enters
the kernel. Sessions/caches belong to one query. Operational adapters live in lore.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import random
import re

from retorno.config.balance import Balance
from retorno.model.world import information_capabilities
from retorno.worldgen import manifest
from retorno.worldgen.generator import _parse_sector_id
from retorno.worldgen.narrative import ContentError, canonical, fingerprint

VERSION = "historical-information-v1"
LEGACY_VERSION = "legacy-information-v0"
NAVIGATION_POLICY_VERSION = "host-navigation-exclusions-v1"
PROBABILITIES = (
    "SALVAGE_DATA_LOG_P_STATION_SHIP", "SALVAGE_DATA_LOG_P_OTHER",
    "SALVAGE_DATA_MAIL_P_STATION_SHIP", "SALVAGE_DATA_MAIL_P_OTHER",
    "SALVAGE_DATA_FRAG_P_STATION_DERELICT", "SALVAGE_DATA_FRAG_P_OTHER",
)
# Version v0 identifies the approved B0 parameters as well as its runtime
# selection algorithm. Old saves had no probability snapshot to reinterpret.
LEGACY_PROBABILITIES = (0.70, 0.50, 0.50, 0.30, 0.25, 0.15)


class InformationIncomplete(ValueError):
    """No complete result; callers must not freeze an empty substitute."""


@dataclass(frozen=True, slots=True)
class InformationBudget:
    physical_sectors: int = 27
    sites: int = 4096
    generation_cohorts: int = 4096

    def __post_init__(self):
        if not (type(self.physical_sectors) is int and 0 < self.physical_sectors <= 27
                and type(self.sites) is int and 0 < self.sites <= 4096
                and type(self.generation_cohorts) is int and 0 < self.generation_cohorts <= 32768):
            raise ValueError("Invalid historical information query budget")


@dataclass(frozen=True, slots=True)
class InformationDefinition:
    version: str
    rules_json: str
    authored_json: str
    rules_key: str
    prologue_json: str = ""


@dataclass(frozen=True, slots=True)
class NavigationRecord:
    record_id: str
    source_id: str
    destination_id: str
    kind: str
    distance_ly: float
    relation: str | None


@dataclass(frozen=True, slots=True)
class HistoricalInformation:
    host: manifest.HistoricalSite
    source_id: str
    rules_key: str
    uplink: tuple[NavigationRecord, ...]
    files_json: str
    mail_by_locale: tuple[str, str]
    examined_physical_sectors: tuple[str, ...]
    examined_generation_cohorts: int

    @property
    def files(self):
        # Return an independent projection, never a mutable shared cache.
        return json.loads(self.files_json)


def _rules():
    return dict(kernel="cube-1-weighted-1-archives-1", candidate_radius_sectors=1,
        max_destinations=3, hop_cap_ly=45.0,
        weights=dict(connection=8, hub=5, installation=4, vessel=1),
        probabilities={name: float(getattr(Balance, name)) for name in PROBABILITIES})


def define_information(snapshot):
    """Capture authored data and the initial prologue contract, never radio."""
    authored = {}
    for location in snapshot["locations"]:
        node = location["node"]
        if node["node_id"] == "RETORNO_SHIP":
            continue
        files = []
        for entry in location.get("fs_files", []):
            entry = dict(entry)
            if entry.get("content_ref") and "content" not in entry:
                entry["content"] = snapshot["texts"][entry["content_ref"]]
            files.append(entry)
        authored[node["node_id"]] = dict(name=node.get("name", node["node_id"]),
            radiation=float(node.get("radiation_rad_per_s", 0)), files=files,
            uplink_table=location.get("uplink_table", {}))
        if "navigation_policy" in location:
            policy = location["navigation_policy"]
            source = snapshot.get("sources", {}).get("location:" + node["node_id"], "locations")
            def invalid(cause):
                raise ContentError(source, node["node_id"], "navigation_policy", cause)
            if (not isinstance(policy, dict) or set(policy) != {"version", "exclude_destinations"}
                    or policy.get("version") != NAVIGATION_POLICY_VERSION):
                invalid("expected host-navigation-exclusions-v1 object / objeto de exclusiones requerido")
            excluded = policy["exclude_destinations"]
            if not isinstance(excluded, list) or not excluded:
                invalid("nonempty destination list required / lista no vacía de destinos requerida")
            normalized = []
            aliases = snapshot.get("aliases", {})
            for token in excluded:
                ident = aliases.get(token.casefold()) if isinstance(token, str) else None
                if ident is None or ident == node["node_id"] or ident == "RETORNO_SHIP":
                    invalid("distinct authored destination required / destino authored distinto requerido")
                if ident in normalized:
                    invalid("duplicate destination / destino duplicado")
                normalized.append(ident)
            # Authored testimony is never silently rewritten. Reject a conflicting
            # operative LINK, including reverse links and explicit INTEL blocks.
            for entry in files:
                text = entry.get("content", "")
                for match in re.finditer(r"(?:^|\[INTEL\])\s*LINK:\s*(.*?)\s*(?=\[/INTEL\]|$)", text, re.M | re.I):
                    payload = match[1]
                    endpoints = payload.split("->", 1) if "->" in payload else (node["node_id"], payload)
                    pair = [aliases.get(v.strip().casefold(), v.strip()) for v in endpoints]
                    if any(set(pair) == {node["node_id"], dest} for dest in normalized):
                        invalid("authored LINK conflicts with exclusion / LINK authored contradice la exclusión")
            authored[node["node_id"]]["navigation_policy"] = dict(
                version=NAVIGATION_POLICY_VERSION, exclude_destinations=sorted(normalized))
    rules_json, authored_json = canonical(_rules()), canonical(authored)
    prologue = canonical(snapshot["prologue_chain"]) if snapshot.get("prologue_chain") else ""
    key = fingerprint((VERSION, rules_json, authored_json, prologue)) if prologue else fingerprint((VERSION, rules_json, authored_json))
    return InformationDefinition(VERSION, rules_json, authored_json, key, prologue)


def validate_definition(definition, *, current=False):
    parts = (VERSION, definition.rules_json, definition.authored_json) if isinstance(definition, InformationDefinition) else ()
    if isinstance(definition, InformationDefinition) and definition.prologue_json:
        parts += (definition.prologue_json,)
    if (not isinstance(definition, InformationDefinition) or definition.version != VERSION
            or definition.rules_key != fingerprint(parts)):
        raise ValueError("Historical information definition mismatch / Definición de información histórica incompatible")
    if definition.prologue_json:
        chain = json.loads(definition.prologue_json)
        if (not isinstance(chain, dict) or set(chain) != {"version", "host_id"}
                or chain["version"] != manifest.PROLOGUE_VERSION
                or not isinstance(chain["host_id"], str) or not chain["host_id"]
                or canonical(chain) != definition.prologue_json):
            raise ValueError("Invalid prologue contract / Contrato del prólogo no válido")
    rules, authored = json.loads(definition.rules_json), json.loads(definition.authored_json)
    fixed = _rules()
    if (not isinstance(rules, dict) or set(rules) != set(fixed)
            or any(rules[key] != fixed[key] for key in fixed if key != "probabilities")
            or set(rules.get("probabilities", {})) != set(PROBABILITIES)
            or any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
                   for value in rules["probabilities"].values())
            or not isinstance(authored, dict)
            or definition.rules_json != canonical(rules) or definition.authored_json != canonical(authored)):
        raise ValueError("Invalid historical information rules / Reglas de información histórica no válidas")
    if current and definition.rules_json != canonical(fixed):
        raise ValueError("Historical information rules changed / Reglas de información histórica modificadas")
    return rules, authored


def _seed(*parts):
    return int(fingerprint(parts), 16)


def sampling_definition(definition):
    """Keep pre-policy records/draws stable; full definition still pins policy.

    Policies are subtractive, not a new random-history input. No-policy inputs
    retain exactly the original v1 fingerprint and algorithms.
    """
    authored = json.loads(definition.authored_json)
    if not definition.prologue_json and not any("navigation_policy" in host for host in authored.values()):
        return definition
    for host in authored.values():
        host.pop("navigation_policy", None)
    raw = canonical(authored)
    return InformationDefinition(definition.version, definition.rules_json, raw,
        fingerprint((VERSION, definition.rules_json, raw)))


def navigation_excluded(definition, host_id, destination_id):
    host = json.loads(definition.authored_json).get(host_id, {})
    return destination_id in host.get("navigation_policy", {}).get("exclude_destinations", ())


def _record(world, rules, host, destination, edge):
    source, dest = manifest.operative_id(world, host), manifest.operative_id(world, destination)
    kind = "historical_connection" if edge else "navigation_solution"
    ident = "HI1:" + fingerprint((VERSION, rules.rules_key, host.identity.encoded,
        "navigation", destination.identity.encoded, kind))
    return NavigationRecord(ident, source, dest, kind,
        math.dist(host.position_ly, destination.position_ly), edge)


def _select(rng, weighted, count):
    remaining = sorted(weighted.items())
    selected = []
    while remaining and len(selected) < count:
        roll = rng.random() * sum(weight for _, weight in remaining)
        cumulative = 0
        index = len(remaining) - 1
        for i, (_, weight) in enumerate(remaining):
            cumulative += weight
            if roll < cumulative:
                index = i
                break
        selected.append(remaining.pop(index)[0])
    return selected


def navigation_content(record):
    """One stable bilingual archive: LINK syntax remains shared with the parser."""
    explanation = {
        "historical_connection": "Documented historical physical connection. / Conexión física histórica documentada.",
        "navigation_solution": "Calculated navigation solution; no evidence of historical traffic. / Solución navegacional calculada; no acredita tráfico histórico.",
    }[record.kind]
    return (f"Record / Registro: {record.record_id}\n{explanation}\n"
        f"LINK: {record.source_id} -> {record.destination_id}\n")


def render_mail(world, definition, host, neighbors, *, locale):
    """A retained, undated record; never a claim of current activity or life."""
    _, authored = validate_definition(definition)
    source = manifest.operative_id(world, host)
    name = authored.get(source, {}).get("name", f"{host.kind.title()} {host.legacy_id_hint}")
    rng = random.Random(_seed(VERSION, definition.rules_key, host.identity.encoded, "telemetry"))
    integrity = rng.randint(58, 98)
    drift = rng.randint(-420, 420)
    record_id = "HI1:" + fingerprint((definition.rules_key, host.identity.encoded, "telemetry"))
    counts = {}
    for site in neighbors:
        counts[site.kind] = counts.get(site.kind, 0) + 1
    dominant = min(counts, key=lambda kind: (-counts[kind], kind)) if counts else "none"
    if locale == "es":
        kinds = dict(station="estación", relay="relé", waystation="estación intermedia",
            ship="nave", derelict="derrelicto", none="ninguna", unknown="desconocida")
        return (f"FROM: {name}\nSUBJ: Archivo de telemetría conservado\n\n"
            "Copia histórica sin fecha absoluta verificable. No es una medición actual de la nave.\n"
            f"ID de informe: {record_id}\nRegión registrada: {host.region}\n"
            f"Integridad declarada de caché: {integrity}%\nDeriva de reloj registrada: {drift:+d} ms\n"
            f"Referencias de conexión histórica: {len(neighbors)}\n"
            f"Clase de extremo predominante: {kinds.get(dominant, dominant)}\n"
            "No constan comprobaciones actuales de respuesta, tráfico ni supervivientes.\n"
            "El estado operativo presente y la antigüedad del registro son desconocidos.\n"
            "Contrasta los registros navegacionales con observaciones independientes.\n")
    return (f"FROM: {name}\nSUBJ: Retained telemetry archive\n\n"
        "Historical copy without a verified absolute date. This is not a current ship measurement.\n"
        f"Report ID: {record_id}\nRecorded region: {host.region}\n"
        f"Declared cache integrity: {integrity}%\nRecorded clock drift: {drift:+d} ms\n"
        f"Historical connection references: {len(neighbors)}\nPredominant endpoint class: {dominant}\n"
        "No current response, traffic or survivor checks are recorded.\n"
        "Present operational status and record age are unknown.\n"
        "Corroborate navigation records with independent observations.\n")


def _files(world, definition, host, records, neighbors, authored, rules):
    source = manifest.operative_id(world, host)
    mail = tuple(render_mail(world, definition, host, neighbors, locale=locale) for locale in ("en", "es"))
    base = authored.get(source, {}).get("files", [])
    if base:
        return base, mail
    rng = random.Random(_seed(VERSION, definition.rules_key, host.identity.encoded, "archive-files"))
    files = []
    def add(path, content, family, record=None):
        identity = record.record_id if record else "HI1:" + fingerprint((definition.rules_key, host.identity.encoded, family))
        entry = dict(path=path, access="guest", content=content, information_version=VERSION,
            information_rules_key=definition.rules_key, historical_record_id=identity)
        if record:
            entry["navigation_record"] = asdict(record)
        files.append(entry)
    # All incident historical edges were resolved, not just materialized links.
    documented = [r for r in records if r.kind == "historical_connection"]
    candidates = documented or records
    nav = min(candidates, key=lambda r: r.destination_id) if candidates else None
    p = rules["probabilities"]
    log_p = p["SALVAGE_DATA_LOG_P_STATION_SHIP" if host.kind in {"station", "ship"} else "SALVAGE_DATA_LOG_P_OTHER"]
    mail_p = p["SALVAGE_DATA_MAIL_P_STATION_SHIP" if host.kind in {"station", "ship"} else "SALVAGE_DATA_MAIL_P_OTHER"]
    frag_p = p["SALVAGE_DATA_FRAG_P_STATION_DERELICT" if host.kind in {"station", "derelict"} else "SALVAGE_DATA_FRAG_P_OTHER"]
    has_link = False
    if nav and rng.random() < log_p:
        add("/logs/nav.log", navigation_content(nav), "navigation", nav)
        has_link = True
    if rng.random() < mail_p:
        for locale, content in zip(("en", "es"), mail):
            add(f"/mail/inbox/0001.{locale}.txt", content, "telemetry")
    if nav and rng.random() < frag_p:
        fragment = f"{rng.getrandbits(16):04x}"
        if not has_link:
            add(f"/data/nav/fragments/frag_{fragment}.txt", navigation_content(nav), "navigation", nav)
            has_link = True
    if nav and not has_link:
        add(f"/data/nav/fragments/frag_{rng.getrandbits(16):04x}.txt", navigation_content(nav), "navigation", nav)
    return files, mail


def query_information(world, definition, node_id, *, budget=None, include_prologue=True):
    """Complete fixed 3x3x3 physical domain + all incident historical edges.

    This is a historical record rule, not a claim about all sites within 45 ly.
    Budget/domain exceptions propagate; a caller must retry, never persist [].
    """
    budget = budget or InformationBudget()
    rules, authored = validate_definition(definition)
    sampling = sampling_definition(definition)
    if world.algorithm_version != manifest.ALGORITHM_VERSION:
        raise ValueError("Historical information requires the certified production manifest")
    session = manifest.new_session(world)
    host = manifest.resolve_operative_id(world, node_id, session=session)
    if host is None or not information_capabilities(host.kind):
        return None
    sx, sy, sz = _parse_sector_id(host.physical_sector_id)
    sectors = tuple(f"S{sx+x:+04d}_{sy+y:+04d}_{sz+z:+04d}"
        for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1))
    if len(sectors) > budget.physical_sectors:
        raise InformationIncomplete("Historical information physical-sector budget; no complete result")
    inventory = manifest._physical_inventory(session, sectors, max_sectors=budget.physical_sectors)
    eligible = {s.identity for s in inventory.sites}
    topology = manifest._query_session(session, (host.generation_sector_id,))
    sites = {s.identity: s for s in inventory.sites}
    sites.update((s.identity, s) for cohort in topology.sectors for s in cohort.sites)
    sites.update((s.identity, s) for s in topology.boundary_sites)
    connections = {}
    for edge in topology.edges:
        if host.identity in (edge.left, edge.right):
            other = edge.right if edge.left == host.identity else edge.left
            connections[other] = edge.kind
            eligible.add(other)
    table = authored.get(node_id, {}).get("uplink_table", {}) or {}
    # An explicit authored candidate is still a certified destination, not a
    # declaration of traffic. It may lie outside the fixed local window.
    authored_weights = {}
    if len(table.get("authored_candidates", [])) > budget.sites:
        raise InformationIncomplete("Historical information authored-candidate budget; no complete result")
    for entry in table.get("authored_candidates", []):
        dest = entry.get("node_id", "")
        target = manifest.resolve_operative_id(world, dest, session=session)
        if target and target.identity.namespace == "authored":
            sites[target.identity] = target
            eligible.add(target.identity)
            authored_weights[dest] = max(1, int(entry.get("weight", 1)))
        if len(session.sectors) > budget.generation_cohorts:
            raise InformationIncomplete("Historical information authored lookup budget; no complete result")
    if len(sites) > budget.sites or len(session.sectors) > budget.generation_cohorts:
        raise InformationIncomplete("Historical information site/cohort budget; no complete result")
    records, weights = {}, {}
    for site in sorted(sites.values(), key=lambda s: s.identity):
        # An additive guardrail slot must not perturb existing weighted pools.
        # Its incoming acquisition record is reserved explicitly below.
        if world.prologue_fallback is not None and site.identity == world.prologue_fallback.identity:
            continue
        if site.identity not in eligible or site.identity == host.identity or not information_capabilities(site.kind):
            continue
        distance = math.dist(host.position_ly, site.position_ly)
        if not 0 < distance <= world.hop_cap_ly:
            continue
        record = _record(world, sampling, host, site, connections.get(site.identity))
        records[record.destination_id] = record
        weights[record.destination_id] = (rules["weights"]["connection"] if record.relation
            else rules["weights"]["hub"] if site.is_hub
            else rules["weights"]["installation"] if "uplink" in information_capabilities(site.kind)
            else rules["weights"]["vessel"])
    selected = []
    maximum = rules["max_destinations"]
    rng = random.Random(_seed(VERSION, sampling.rules_key, host.identity.encoded, "uplink"))
    authored_weights = {nid: weight for nid, weight in authored_weights.items() if nid in records}
    count = max(int(table.get("min_authored", 0) or 0), int(table.get("max_authored", 0) or 0))
    selected.extend(_select(rng, authored_weights, min(maximum, max(0, count))))
    selected.extend(_select(rng, {nid: weight for nid, weight in weights.items() if nid not in selected}, maximum-len(selected)))
    uplink = tuple(records[nid] for nid in selected) if "uplink" in information_capabilities(host.kind) else ()
    neighbors = tuple(sites[i] for i in sorted(connections))
    files, mail = _files(world, sampling, host, list(records.values()), neighbors, authored, rules)
    # Remove only selected records/files. Never re-roll or fill a vacated slot.
    excluded = set(authored.get(node_id, {}).get("navigation_policy", {}).get("exclude_destinations", ()))
    uplink = tuple(record for record in uplink if record.destination_id not in excluded)
    files = [entry for entry in files if entry.get("navigation_record", {}).get("destination_id") not in excluded]
    if include_prologue and definition.prologue_json:
        chain = json.loads(definition.prologue_json)
        if chain["version"] != manifest.PROLOGUE_VERSION or world.prologue_version != chain["version"]:
            raise ValueError("Incompatible prologue information contract / Contrato informativo del prólogo incompatible")
        witness = manifest.lookup_site(world, world.prologue_identity, session=session).site
        if witness is None or manifest.operative_id(world, witness) != chain["host_id"]:
            raise ValueError("Prologue information/physical identity mismatch / Identidad física e informativa del prólogo incompatible")
        if node_id == "ECHO_7":
            dest = chain["host_id"]
            if navigation_excluded(definition, node_id, dest):
                raise ValueError("Prologue uplink excluded by host policy / Política del host excluye el uplink del prólogo")
            if not any(r.destination_id == dest for r in uplink):
                record = records.get(dest) or _record(world, sampling, host, witness, connections.get(witness.identity))
                uplink = uplink[:maximum-1] + (record,) if len(uplink) >= maximum else uplink + (record,)
        elif node_id == chain["host_id"]:
            target = manifest.resolve_operative_id(world, "HARBOR_12", session=session)
            record = records.get("HARBOR_12") or _record(world, sampling, host, target, connections.get(target.identity))
            if navigation_excluded(definition, node_id, "HARBOR_12"):
                raise ValueError("Prologue archive excluded by host policy / Política del host excluye el archivo del prólogo")
            files.append(dict(path="/data/nav/waystation_solution.txt", access="guest",
                content=navigation_content(record), navigation_record=asdict(record),
                information_version=VERSION, information_rules_key=definition.rules_key,
                historical_record_id=record.record_id, reservation_version=chain["version"]))
    return HistoricalInformation(host, node_id, definition.rules_key, uplink, canonical(files), mail,
        sectors, len(session.sectors))


def validate_information_state(state):
    """Save/load boundary: validate immutable preparation, never consumed flags."""
    world = state.world
    if world.information_version == LEGACY_VERSION:
        if (tuple(float(getattr(Balance, name)) for name in PROBABILITIES) != LEGACY_PROBABILITIES
                or Balance.DETERMINISTIC_LORE_INTEL is not True):
            raise ValueError("Legacy information rules changed / Reglas legacy de información modificadas")
        if world.information_definition is not None or any(
                pool.information_version != LEGACY_VERSION or pool.information_rules_key or pool.uplink_records
                for pool in world.node_pools.values()):
            raise ValueError("Mixed legacy/historical information / Información legacy e histórica mezclada")
        return
    if world.information_version != VERSION:
        raise ValueError("Unsupported historical information version / Versión de información histórica no admitida")
    validate_definition(world.information_definition, current=True)
    if world.information_definition != define_information(world.narrative_snapshot):
        raise ValueError("Authored information snapshot changed / Snapshot authored de información modificado")
    from retorno.worldgen.generator import universe_definition
    physical = universe_definition(state)
    anchors = {a.raw_id for a in physical.authored}
    if {"ECHO_7", "HARBOR_12"} <= anchors or physical.prologue_version or world.information_definition.prologue_json:
        certify_prologue(state)
    authored = json.loads(world.information_definition.authored_json)
    for nid, pool in world.node_pools.items():
        if pool.information_version != VERSION or pool.information_rules_key != world.information_definition.rules_key:
            raise ValueError("Pool information contract mismatch / Contrato de información del pool incompatible")
        expected = query_information(physical, world.information_definition, nid)
        files = expected.files if expected else authored.get(nid, {}).get("files", [])
        routes = [asdict(r) for r in expected.uplink] if expected else []
        if (pool.base_files != files or pool.uplink_records != routes
                or pool.uplink_route_pool != [r["destination_id"] for r in routes]):
            raise ValueError("Historical pool preparation changed / Preparación histórica del pool modificada")
        # Injected narrative pieces remain scheduler-owned, without invented
        # historical-information-v1 attribution.
        if any(entry.get("information_version") for entry in pool.injected_files):
            raise ValueError("Injected file claims historical provenance / Archivo inyectado atribuye procedencia histórica")


def certify_prologue(state):
    """Certify acquisition edges, not merely an existing physical path.

    Runs before exploration and at save/load. No knowledge, pools, time or RNG
    are changed. B2 explicitly uses the projection without these reservations.
    """
    from retorno.core.lore import disclosable_data_files, _locked_primary_targets
    world = state.world.manifest_definition
    witness = manifest.validate_prologue(world)
    nid = manifest.operative_id(world, witness)
    chain = dict(version=manifest.PROLOGUE_VERSION, host_id=nid)
    definition = state.world.information_definition
    if json.loads(definition.prologue_json) != chain:
        raise ValueError("Invalid prologue information reservation / Reserva informativa del prólogo no válida")
    reserved = {v["node_id"] for v in state.world.narrative_snapshot.get("reservations", {}).values()}
    locked = _locked_primary_targets(state)
    if nid in reserved | locked or "HARBOR_12" in locked:
        raise ValueError("Prologue conflicts with narrative protection / El prólogo contradice una protección narrativa")
    echo = query_information(world, definition, "ECHO_7")
    archive = query_information(world, definition, nid)
    if ("uplink" not in information_capabilities(echo.host.kind)
            or "salvage_data" not in information_capabilities(witness.kind)
            or not 1 <= len(echo.uplink) <= 3
            or nid not in {r.destination_id for r in echo.uplink}
            or "HARBOR_12" in {r.destination_id for r in echo.uplink}):
        raise ValueError("Invalid public prologue acquisition chain / Cadena pública de adquisición del prólogo no válida")
    files = [f for f in disclosable_data_files(state, archive.files)
             if f.get("reservation_version") == manifest.PROLOGUE_VERSION]
    if (len(files) != 1 or files[0]["access"] != "guest"
            or files[0]["path"] != "/data/nav/waystation_solution.txt"
            or files[0]["content"] != navigation_content(NavigationRecord(**files[0]["navigation_record"]))
            or files[0]["navigation_record"]["destination_id"] != "HARBOR_12"):
        raise ValueError("Prologue archive unavailable / Archivo del prólogo no disponible")
    return chain
