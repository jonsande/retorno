"""F-DEAD-01: bounded historical selection, transactional preparation and stages.

The manifest is the only physical authority. Search is read-only; confirmation
uses a disposable copy. Radio uses the common ledger, never a private queue.
The pre-manifest planner remains a diagnostic API for conditional geometry.
"""
from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import asdict, dataclass, fields, is_dataclass
import hashlib
import heapq
import itertools
import json
import math

from retorno.core.deadnode_opportunities import AccessRoute
from retorno.core import communications
from retorno.model.world import SpaceGraph, SpaceNode, WorldState, information_capabilities, is_hop_within_cap, sector_id_for_pos
from retorno.worldgen import manifest
from retorno.worldgen.generator import universe_definition, _ensure_sector_cluster_generated, validate_universe_state

LEGACY_VERSION = "historical-recovery-v1"
VERSION = "historical-recovery-v2"
HUBS = {"station", "relay", "waystation"}
ACTIVE = {"prepared", "receipt_pending", "active", "stage_consumed"}


@dataclass(frozen=True, slots=True)
class RecoveryBudget:
    sectors: int = 16
    sites: int = 2048
    expansions: int = 4096
    edges: int = 65536
    # A rolling certificate window, not a maximum distance from the ship.
    retained_sites: int = 1024
    information_hosts: int = 128

    def __post_init__(self):
        if not (0 <= self.sectors <= 64 and 0 < self.sites <= 4096
                and 0 <= self.expansions <= 65536 and 0 <= self.edges <= 262144
                and 0 < self.retained_sites <= self.sites
                and type(self.information_hosts) is int and 0 <= self.information_hosts <= 512):
            raise ValueError("Invalid recovery technical budget")


@dataclass(frozen=True, slots=True)
class StageSource:
    reference: str
    payload_key: str


@dataclass(frozen=True, slots=True)
class RecoveryProposal:
    block: str
    scope: str
    snapshot: str
    sites: tuple[manifest.HistoricalSite, ...]
    access: AccessRoute
    mechanisms: tuple[str, ...]
    first_emission_id: str | None = None
    first_reception_sensitivity: float = 1.0
    stage_sources: tuple[StageSource | None, ...] | None = None

    def __setstate__(self, state):
        # Frozen slot dataclasses used a positional list in previous schema 3.
        for index, spec in enumerate(fields(self)):
            object.__setattr__(self, spec.name, state[index] if index < len(state) else spec.default)


@dataclass(frozen=True, slots=True)
class SearchResult:
    status: str
    proposal: RecoveryProposal | None
    reason: str
    cursor: int
    retained: tuple[manifest.HistoricalSite, ...]
    sectors: tuple[str, ...]
    examined_cohorts: int
    expansions: int
    edges: int


@dataclass(slots=True)
class RecoveryPlan:
    plan_id: str
    proposal: RecoveryProposal
    prepared_t: float
    status: str = "prepared"
    stage: int = 0
    captured: tuple[int, ...] = ()
    consumed: tuple[int, ...] = ()
    version: str = VERSION
    dead_attempt: int | None = None
    invalidation: tuple[str, str] | None = None
    source_contract: str | None = None

    def __setstate__(self, state):
        # Additive slots for genuine older schema-3 plans; strict validation is
        # still run by load_single_slot before exposing the loaded state.
        values = state[1]
        for spec in fields(self):
            setattr(self, spec.name, values.get(spec.name, spec.default))
        if "source_contract" not in values:
            self.source_contract = _source_contract_key(self)


def _canonical(value):
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(v) for v in value), key=repr)
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(_canonical(value), sort_keys=True, allow_nan=False).encode()).hexdigest()


def protection(state):
    """Fail closed for primary references the existing policy cannot resolve."""
    from retorno.core import lore
    from retorno.worldgen.narrative import records_for
    locked = lore._locked_primary_targets(state)
    complete = True
    for arc in records_for(state, "arcs", lore.load_arcs):
        primary = arc.get("primary_intel") or {}
        placement = state.world.arc_placements.get(arc.get("arc_id", ""), {})
        primary_state = placement.get("primary")
        unlocked = (isinstance(primary_state, dict) and primary_state.get("unlocked")) or primary.get("id", "primary") in (placement.get("discovered") or ())
        if primary and not unlocked and lore._primary_target_node_id(primary) is None:
            complete = False
    reserved = {v.get("node_id") for v in state.world.narrative_snapshot.get("reservations", {}).values()}
    return locked, reserved, complete


def snapshot_key(state):
    """Structural inputs only: no electricity, drones, repairs or resources."""
    w = state.world
    nodes = [(k, n.kind, (n.x_ly, n.y_ly, n.z_ly), n.historical_key, n.generation_sector_id)
             for k, n in sorted(w.space.nodes.items()) if n.kind != "transit"]
    pools = [(k, p.window_open, p.node_cleaned, p.base_files, p.injected_files,
              p.uplink_data_consumed, p.delivered_piece_ids) for k, p in sorted(w.node_pools.items())]
    return _digest((universe_definition(state), w.current_node_id, w.current_pos_ly,
                    nodes, w.known_nodes, w.known_contacts, w.known_intel, w.known_links,
                    w.visited_nodes, pools, protection(state), w.arc_placements,
                    w.narrative_snapshot, w.dead_nodes, sorted(state.os.fs),
                    w.information_version, w.information_definition))


def directed_access(state) -> dict[str, AccessRoute]:
    """Normal directed travel knowledge, with the shared physical hop check."""
    w = state.world
    allowed = set(w.known_nodes) | set(w.known_intel) | {w.current_node_id}
    start = w.current_node_id
    if start not in w.space.nodes or w.space.nodes[start].kind == "transit":
        return {}
    best = {start: (0.0, 0, (start,))}
    queue = [(0.0, 0, (start,), start)]
    while queue:
        dist, hops, path, nid = heapq.heappop(queue)
        if best.get(nid) != (dist, hops, path):
            continue
        for dest in sorted(w.known_links.get(nid, ())):
            if dest not in allowed or not is_hop_within_cap(w, nid, dest):
                continue
            d = math.dist(_pos(w.space.nodes[nid]), _pos(w.space.nodes[dest]))
            if d <= 0:
                continue
            cost = (dist+d, hops+1, path+(dest,))
            if dest not in best or cost < best[dest]:
                best[dest] = cost
                heapq.heappush(queue, (*cost, dest))
    return {k: AccessRoute(p, d, None, "directed_distance") for k, (d, _, p) in best.items()}


def _pos(node):
    return node.x_ly, node.y_ly, node.z_ly


def _physical_view(sites):
    return WorldState(space=SpaceGraph(nodes={nid: SpaceNode(nid, nid, s.kind,
        x_ly=s.position_ly[0], y_ly=s.position_ly[1], z_ly=s.position_ly[2]) for nid,s in sites.items()}))


def _shell_offset(index):
    """Unrank a cubic shell in O(log radius); no walk through previous shells."""
    if index == 0:
        return 0, 0, 0
    lo, hi = 1, 1
    while (2*hi+1)**3 <= index:
        hi *= 2
    while lo < hi:
        mid = (lo+hi)//2
        if (2*mid+1)**3 > index:
            hi = mid
        else:
            lo = mid+1
    r = lo
    n = index-(2*r-1)**3
    side = 2*r+1
    # Two full X faces, then Y faces without X edges, then Z interiors.
    if n < 2*side*side:
        face, rem = divmod(n, side*side)
        a, b = divmod(rem, side)
        return (-r if face == 0 else r), a-r, b-r
    n -= 2*side*side
    width = 2*r-1
    if n < 2*width*side:
        face, rem = divmod(n, width*side)
        a, b = divmod(rem, side)
        return a-r+1, (-r if face == 0 else r), b-r
    n -= 2*width*side
    face, rem = divmod(n, width*width)
    a, b = divmod(rem, width)
    return a-r+1, b-r+1, (-r if face == 0 else r)


def _navigation_emissions(state):
    """Bounded installed activity, never inferred from installation kind."""
    snapshot = state.world.narrative_snapshot
    result = {}
    entries = sorted(snapshot.get("radio_emissions", {}).items())
    for eid, emission in entries[:4096]:
        emitter = snapshot.get("radio_emitters", {}).get(emission.emitter_id)
        if (emitter is None or emission.channel != "station_broadcast" or emission.piece_key
                or emission.mode != "continuous" or emission.end_t is not None
                or not emission.navigation_link_to):
            continue
        source, dest = emitter.host_id, emission.navigation_link_to
        if emission.content_by_locale != _hint(source, dest):
            continue
        op = state.world.radio_opportunities.get(f"radio:{eid}")
        if op and (op.status != "pending" or op.delivery.get("kind") != "declared_radio"):
            continue
        result.setdefault((source, dest), []).append(eid)
    return result, len(entries) <= 4096


def _first_reception(state, source, emission_id=None, *, receiver_node_id=None,
                     sensitivity=None, at_t=None, legacy=False):
    emitter = emission = None
    if emission_id:
        snapshot = state.world.narrative_snapshot
        emission = snapshot.get("radio_emissions", {}).get(emission_id)
        if (emission is None or emission.mode != "continuous" or emission.end_t is not None
                or emission.channel != "station_broadcast" or emission.piece_key
                or not emission.navigation_link_to):
            return "first_emission_unavailable"
        emitter = snapshot["radio_emitters"][emission.emitter_id]
        if emitter.host_id != source or emission.content_by_locale != _hint(source, emission.navigation_link_to):
            return "first_emission_unavailable"
    elif not legacy:
        return "first_emission_undeclared"
    return (communications.radio_spatial_block_reason(state, source, channel="station_broadcast",
                emitter=emitter, receiver_node_id=receiver_node_id, sensitivity=sensitivity)
            or communications.radio_temporal_block_reason(state, emitter, emission,
                receiver_node_id=receiver_node_id, at_t=at_t))


def _at_site(state, source, site):
    # A private stationary probe for future stages, including lazy certificates.
    probe = copy(state)
    probe.world = copy(state.world)
    probe.world.current_node_id = source
    probe.world.current_pos_ly = site.position_ly
    return probe


def _salvage_source(state, source, dest, site, *, eligible=True, expected=None,
                    archive_cache=None, archive_limit=128):
    from retorno.core import lore
    from retorno.model.os import normalize_path
    if "salvage_data" not in information_capabilities(site.kind):
        return None
    pool = state.world.node_pools.get(source)
    if eligible and (source in state.world.visited_nodes or (pool and (pool.node_cleaned or not pool.window_open))):
        return None
    if pool:
        files = pool.base_files + pool.injected_files
    elif lore.historical_information_enabled(state):
        # A v1 record is pre-existing even before lazy preparation. This pure
        # projection neither initializes a pool nor manufactures the sought LINK.
        if archive_cache is not None and source in archive_cache:
            files = archive_cache[source]
        else:
            if archive_cache is not None and len(archive_cache) >= archive_limit:
                raise ValueError("historical_information_host_budget; source evaluation incomplete")
            information = lore.historical_information_for_node(state, source)
            files = information.files if information else []
            if archive_cache is not None:
                archive_cache[source] = files
    else:
        # Legacy histories cannot acquire retrospective procedural provenance.
        files = lore._location_fs_files(source, state)
    files = lore.disclosable_data_files(state, files)
    matches, seen_paths = [], set()
    aliases = state.world.narrative_snapshot.get("aliases", {})
    for entry in files:
        path = normalize_path(str(entry.get("path", "")))
        # Match the existing mount collector's base-before-injected precedence.
        if path in seen_paths:
            continue
        seen_paths.add(path)
        if not path.startswith(("/logs/", "/data/", "/mail/")) or entry.get("access", "guest") != "guest":
            continue
        if eligible and f"/remote/{source}{path}" in state.os.fs:
            continue
        for line in str(entry.get("content", "")).splitlines():
            pair = lore._primary_link_pair({"line": line})
            if pair and tuple(aliases.get(v.casefold(), v) for v in pair) == (source, dest):
                matches.append(StageSource(path, _digest(entry)))
                break
    if expected is not None:
        return expected if expected in matches else None
    return min(matches, key=lambda s: (s.reference, s.payload_key)) if matches else None


def _source(state, nid, site, dest, *, emissions=None, archive_cache=None, archive_limit=128):
    emissions = _navigation_emissions(state)[0] if emissions is None else emissions
    probe = _at_site(state, nid, site)
    for eid in emissions.get((nid, dest), ()):
        if _first_reception(probe, nid, eid) is None:
            emission = state.world.narrative_snapshot["radio_emissions"][eid]
            return "radio", StageSource(eid, _digest(emission.content_by_locale))
    salvage = _salvage_source(state, nid, dest, site, archive_cache=archive_cache, archive_limit=archive_limit)
    return ("salvage", salvage) if salvage else None


def _edge_source(state, source, dest, site, *, emissions=None, archive_cache=None, archive_limit=128):
    w = state.world
    if (dest in w.known_links.get(source, ()) and dest in (set(w.known_nodes) | set(w.known_intel))
            and is_hop_within_cap(w, source, dest)):
        return "known_route", None
    return _source(state, source, site, dest, emissions=emissions,
        archive_cache=archive_cache, archive_limit=archive_limit)


def select_recovery(state, block="global", target_id=None, *, cursor=0, retained=(), budget=None):
    """Pure, deterministic bounded search. Exhaustion is never global absence.

    Cursor advances through 3D physical sectors. Existing/observed sectors and
    explicit-target corridor probes are prioritized initially. Retained facts
    are certificates revalidated against the manifest, not a physical registry.
    """
    budget = budget or RecoveryBudget()
    if type(cursor) is not int or cursor < 0:
        raise ValueError("Invalid recovery cursor")
    sites = {}
    sectors = []
    cohorts = expansions = edges = 0
    def result(status, reason, proposal=None):
        # Retain sites near the current connected search, bounded independently
        # of distance. Later calls can re-query discarded sectors explicitly.
        keep = tuple(sites[k] for k in sorted(sites, key=lambda k: (math.dist(sites[k].position_ly, state.world.current_pos_ly), k))[:budget.retained_sites])
        return SearchResult(status, proposal, reason, cursor, keep, tuple(sectors), cohorts, expansions, edges)
    try:
        if len(state.world.space.nodes) > budget.sites:
            return result("incomplete", "materialized_inventory_budget")
        if sum(len(v) for v in state.world.known_links.values()) > budget.edges:
            return result("incomplete", "access_edge_budget")
        definition = universe_definition(state)
        locked, reserved, complete = protection(state)
        if not complete or target_id in locked:
            return result("invalid", "narrative_protection")
        session = manifest.new_session(definition)
        def add(site):
            nid = manifest.operative_id(definition, site)
            if nid not in locked and nid not in reserved:
                sites[nid] = site
        for site in retained:
            if site.identity.scope != definition.scope or site not in session.sector(site.generation_sector_id).sites:
                return result("invalid", "stale_certificate")
            add(site)
        # Certify present nodes without querying or materializing their topology.
        authored = {a.raw_id: a for a in definition.authored}
        for nid, node in sorted(state.world.space.nodes.items()):
            sid = node.generation_sector_id
            if nid in authored:
                sid = sector_id_for_pos(*authored[nid].position_ly)
            if sid:
                for site in session.sector(sid).sites:
                    if manifest.operative_id(definition, site) == nid:
                        if _pos(node) != site.position_ly or node.kind != site.kind:
                            return result("invalid", "physical_collision")
                        add(site)
                        break
        if target_id and target_id not in sites:
            site = manifest.resolve_operative_id(definition, target_id)
            if site is None:
                return result("invalid", "missing_target")
            add(site)
        anchor = tuple(math.floor(v/10) for v in state.world.current_pos_ly)
        priority = set()
        if cursor == 0:
            priority.update(state.world.generated_sectors)
            priority.update(state.world.sector_states)
            priority.update(sector_id_for_pos(*o.position_ly) for o in state.world.scan_observations)
            priority.add(sector_id_for_pos(*state.world.current_pos_ly))
            if target_id in sites:
                end = sites[target_id].position_ly
                distance = math.dist(state.world.current_pos_ly, end)
                steps = max(1, min(64, math.ceil(distance/10)))
                priority.update(sector_id_for_pos(*(a+(b-a)*i/steps for a,b in zip(state.world.current_pos_ly,end))) for i in range(steps+1))
        sectors = sorted(priority, key=lambda s: (math.dist(tuple(int(v)*10+5 for v in s[1:].split("_")), state.world.current_pos_ly), s))[:budget.sectors]
        # Initial priorities must not freeze the widening cursor when full.
        if sectors:
            cursor = max(1, cursor)
        while len(sectors) < budget.sectors:
            offset = _shell_offset(cursor)
            cursor += 1
            sid = "S"+"_".join(f"{a+b:+04d}" for a,b in zip(anchor, offset))
            if sid not in sectors:
                sectors.append(sid)
        inventory = manifest._physical_inventory(session, sectors)
        cohorts = len(inventory.examined_generation_sectors)
        for site in inventory.sites:
            add(site)
        if len(sites) > budget.sites:
            return result("incomplete", "site_budget")
        access = directed_access(state)
        origins = sorted(nid for nid in access if nid in sites and sites[nid].kind in HUBS)
        if not origins:
            return result("conditional", "no_reachable_local_emitter")
        emissions, radio_complete = _navigation_emissions(state)
        receiving_links = {}
        for (source, dest), ids in emissions.items():
            if source in origins:
                for eid in ids:
                    if _first_reception(state, source, eid) is None:
                        receiving_links[(source,dest)] = eid
                        break
        first_reception_eligible = bool(receiving_links)
        if receiving_links:
            origins = sorted({source for source, dest in receiving_links})
        # Shared hop kernel on a private, physical-only view. No gameplay writes.
        view = _physical_view(sites)
        best, queue, path_sources = {}, [], {}
        archive_cache = {}
        for nid in origins:
            cost = (access[nid].distance_ly, 0, access[nid].hops, (nid,))
            best[nid] = cost
            path_sources[nid] = ()
            heapq.heappush(queue, (*cost, nid, nid))
        # Spatial buckets bound edge work for large materialized inventories.
        buckets = {}
        for nid, site in sorted(sites.items()):
            cell = tuple(math.floor(v/45) for v in site.position_ly)
            buckets.setdefault(cell, []).append(nid)
        while queue:
            distance, uncertainty, hops, path, nid, origin = heapq.heappop(queue)
            if best.get(nid) != (distance, uncertainty, hops, path):
                continue
            if expansions >= budget.expansions:
                return result("incomplete", "expansion_budget")
            expansions += 1
            pool = state.world.node_pools.get(nid)
            goal = (nid == target_id) if target_id else (nid not in access and nid not in state.world.visited_nodes and not (pool and pool.node_cleaned))
            if goal and len(path) > 1:
                chain = tuple(sites[p] for p in path)
                evidence = path_sources[nid]
                mechanisms = tuple(value[0] for value in evidence)
                sources = tuple(value[1] for value in evidence)
                emission_id = sources[0].reference
                proposal = RecoveryProposal(block, definition.scope, snapshot_key(state), chain, access[origin], mechanisms,
                    emission_id, communications.receiver_sensitivity(state, reference_when_unavailable=True), sources)
                if not first_reception_eligible:
                    return result("conditional", "first_reception_outside_coverage", proposal)
                return result("validated", "complete_in_examined_scope", proposal)
            cell = tuple(math.floor(v/45) for v in sites[nid].position_ly)
            neighbors = []
            for off in itertools.product((-1,0,1), repeat=3):
                neighbors.extend(buckets.get(tuple(a+b for a,b in zip(cell,off)), ()))
            for dest in sorted(neighbors):
                if dest == nid or dest in path:
                    continue
                if nid == origin and first_reception_eligible and (nid, dest) not in receiving_links:
                    continue
                if edges >= budget.edges:
                    return result("incomplete", "edge_budget")
                edges += 1
                d = math.dist(sites[nid].position_ly, sites[dest].position_ly)
                if d <= 0 or not is_hop_within_cap(view, nid, dest):
                    continue
                evidence = (_source(state, nid, sites[nid], dest, emissions=emissions,
                                archive_cache=archive_cache, archive_limit=budget.information_hosts) if nid == origin
                            else _edge_source(state, nid, dest, sites[nid], emissions=emissions,
                                archive_cache=archive_cache, archive_limit=budget.information_hosts))
                if nid == origin and first_reception_eligible:
                    eid = receiving_links[(nid,dest)]
                    emission = state.world.narrative_snapshot["radio_emissions"][eid]
                    evidence = ("radio", StageSource(eid, _digest(emission.content_by_locale)))
                if evidence is None or (nid == origin and evidence[0] != "radio"):
                    continue
                cost = (distance+d, uncertainty+int(dest not in state.world.space.nodes), hops+1, path+(dest,))
                if dest not in best or cost < best[dest]:
                    best[dest] = cost
                    path_sources[dest] = path_sources[nid] + (evidence,)
                    heapq.heappush(queue, (*cost, dest, origin))
        if not radio_complete:
            return result("incomplete", "radio_candidate_budget")
        if len(sites) > budget.retained_sites:
            return result("incomplete", "retention_budget")
        return result("conditional", "no_complete_chain_with_preexisting_sources")
    except (ValueError, OverflowError) as exc:
        return result("incomplete", "manifest_domain_or_budget:"+str(exc))


def _path(state, proposal):
    d = universe_definition(state)
    return tuple(manifest.operative_id(d, s) for s in proposal.sites)


def _hint(source, dest):
    from retorno.worldgen.radio import navigation_content
    return navigation_content(source, dest)


def _radio_id(plan, index):
    if plan.proposal.stage_sources is not None:
        return f"radio:{plan.proposal.stage_sources[index].reference}"
    if index == 0 and plan.proposal.first_emission_id:
        return f"radio:{plan.proposal.first_emission_id}"
    return f"{plan.plan_id}:{index}"


def _radio_stage(state, plan, index):
    from retorno.core.communications import prepare_radio_opportunity
    path = _path(state, plan.proposal)
    ident = _radio_id(plan, index)
    existing = state.world.radio_opportunities.get(ident)
    metadata = {"kind": "structural_recovery", "plan": plan.plan_id, "stage": index}
    declared = existing and existing.delivery == {"kind": "declared_radio"}
    if existing and (existing.origin_node_id != path[index]
                     or (existing.delivery != metadata and not declared)
                     or existing.channel != "station_broadcast"
                     or existing.content_by_locale != _hint(path[index],path[index+1])):
        raise ValueError("Recovery stage ledger collision")
    if plan.version == LEGACY_VERSION:
        if existing is None or declared:
            raise ValueError("Legacy recovery cannot create an undeclared radio stage")
        return existing
    reference = plan.proposal.stage_sources[index]
    emission = state.world.narrative_snapshot.get("radio_emissions", {}).get(reference.reference)
    if emission is None or _digest(emission.content_by_locale) != reference.payload_key:
        raise ValueError("Recovery emission payload changed")
    if existing and (existing.emission != emission or existing.emitter !=
                     state.world.narrative_snapshot["radio_emitters"][emission.emitter_id]):
        raise ValueError("Recovery stage emission identity mismatch / Identidad de emisión de etapa incompatible")
    if existing and existing.status in {"received", "read_imported"}:
        existing.delivery = metadata
        return existing  # Reuse the real receipt, without another capture.
    if _first_reception(state, path[index], emission.emission_id):
        raise ValueError("Recovery stage signal is not available")
    if declared:
        existing.delivery = metadata
    return prepare_radio_opportunity(state, ident, "station_broadcast",
        emission.content_by_locale, node_id=path[index], trigger="recovery_stage",
        delivery=metadata, emission_id=emission.emission_id)


def _validate_physical(state, proposal):
    d = universe_definition(state)
    if d.scope != proposal.scope or d.algorithm_version != manifest.ALGORITHM_VERSION:
        raise ValueError("Recovery manifest mismatch")
    locked, reserved, complete = protection(state)
    path = _path(state, proposal)
    if not complete or len(path) < 2 or len(set(path)) != len(path) or len(proposal.mechanisms) != len(path)-1:
        raise ValueError("Invalid recovery chain")
    if proposal.first_emission_id:
        emission = state.world.narrative_snapshot.get("radio_emissions", {}).get(proposal.first_emission_id)
        if (not emission or emission.navigation_link_to != path[1] or emission.channel != "station_broadcast"
                or state.world.narrative_snapshot["radio_emitters"][emission.emitter_id].host_id != path[0]):
            raise ValueError("Recovery first emission does not carry this navigation notice")
    session = manifest.new_session(d)
    for nid, site in zip(path, proposal.sites):
        if nid in locked or nid in reserved or site not in session.sector(site.generation_sector_id).sites:
            raise ValueError("Recovery protection or certificate mismatch")
        node = state.world.space.nodes.get(nid)
        if node and (_pos(node) != site.position_ly or node.kind != site.kind
                     or node.historical_key not in (None, site.identity.encoded)):
            raise ValueError("Recovery physical collision")
    view = _physical_view(dict(zip(path,proposal.sites)))
    for a,b in zip(path,path[1:]):
        if math.dist(_pos(view.space.nodes[a]),_pos(view.space.nodes[b])) <= 0 or not is_hop_within_cap(view,a,b):
            raise ValueError("Recovery hop outside navigation cap")
    return path


def _validate_stage_sources(state, proposal, path, *, at_t=None, archival=False):
    if not isinstance(proposal.stage_sources, tuple) or len(proposal.stage_sources) != len(proposal.mechanisms):
        raise ValueError("New recovery requires pre-existing source evidence for every stage")
    if (proposal.mechanisms[0] != "radio" or not isinstance(proposal.stage_sources[0], StageSource)
            or proposal.first_emission_id != proposal.stage_sources[0].reference):
        raise ValueError("Recovery first emission identity mismatch")
    for i, (mechanism, reference) in enumerate(zip(proposal.mechanisms, proposal.stage_sources)):
        source, dest = path[i:i+2]
        if mechanism in {"radio", "salvage"} and (not isinstance(reference, StageSource)
                or not reference.reference or len(reference.payload_key) != 64
                or any(c not in "0123456789abcdef" for c in reference.payload_key)):
            raise ValueError("Recovery stage lacks stable source and payload evidence")
        if mechanism == "radio":
            emission = state.world.narrative_snapshot.get("radio_emissions", {}).get(reference.reference) if isinstance(reference, StageSource) else None
            if emission is not None and (emission.navigation_link_to != dest
                    or reference.payload_key != _digest(emission.content_by_locale)
                    or emission.channel != "station_broadcast" or emission.piece_key
                    or emission.mode != "continuous" or emission.end_t is not None
                    or state.world.narrative_snapshot.get("radio_emitters", {}).get(emission.emitter_id) is None
                    or state.world.narrative_snapshot["radio_emitters"][emission.emitter_id].host_id != source):
                raise ValueError("Recovery declared stage emission identity mismatch / Identidad de emisión declarada incompatible")
            if not archival and (emission is None or _first_reception(
                    _at_site(state, source, proposal.sites[i]), source, reference.reference, at_t=at_t)):
                raise ValueError("Recovery declared stage emission unavailable")
        elif mechanism == "salvage":
            if not archival and _salvage_source(state, source, dest, proposal.sites[i], eligible=False, expected=reference) != reference:
                raise ValueError("Recovery pre-existing archive unavailable")
        elif mechanism == "known_route":
            if reference is not None or _edge_source(state, source, dest, proposal.sites[i]) != ("known_route", None):
                raise ValueError("Recovery known route unavailable")
        else:
            raise ValueError("Unknown recovery delivery mechanism")


def _validate_prepared_sources(state, plan, path, *, archival=False, unprepared=False):
    if any(nid not in state.world.space.nodes for nid in path):
        raise ValueError("Recovery site disappeared")
    if plan.version == VERSION:
        _validate_stage_sources(state, plan.proposal, path, at_t=plan.prepared_t, archival=archival)
    elif plan.version != LEGACY_VERSION or plan.proposal.stage_sources is not None:
        raise ValueError("Incompatible recovery source contract")
    for i, mechanism in enumerate(plan.proposal.mechanisms):
        if mechanism not in {"radio", "salvage", "known_route"}:
            raise ValueError("Unknown recovery delivery mechanism")
        if mechanism == "radio" and i <= plan.stage:
            op = state.world.radio_opportunities.get(_radio_id(plan, i))
            if unprepared and i == plan.stage and op is None:
                continue
            if (op is None or op.origin_node_id != path[i] or op.channel != "station_broadcast"
                    or op.delivery != {"kind": "structural_recovery", "plan": plan.plan_id, "stage": i}
                    or op.content_by_locale != _hint(path[i],path[i+1])):
                raise ValueError("Recovery stage ledger mismatch")
            if plan.version == VERSION and (op.emission is None
                    or op.emission.emission_id != plan.proposal.stage_sources[i].reference):
                raise ValueError("Recovery stage emission identity mismatch")
            if ((i in plan.captured) != (op.status in {"received", "read_imported"})
                    or (i in plan.consumed and op.status != "read_imported")):
                raise ValueError("Recovery receipt progress mismatch / Progreso de recepción incompatible")
        elif mechanism == "salvage" and plan.version == LEGACY_VERSION:
            pool = state.world.node_pools.get(path[i])
            file = f"/logs/nav/{plan.plan_id.replace(':','_')}_{i}.txt"
            if not pool or not any(f.get("path") == file and f"LINK: {path[i]} -> {path[i+1]}" in f.get("content", "") for f in pool.injected_files):
                raise ValueError("Recovery prepared legacy document unavailable")
        elif mechanism == "known_route" and _edge_source(state, path[i], path[i+1], plan.proposal.sites[i]) != ("known_route", None):
            raise ValueError("Recovery known route unavailable")


def _invalidation_key(plan, reason):
    # A consistency checkpoint, not a security signature. Merely setting status
    # to invalid must never turn an incoherent proposal into an accepted save.
    return _digest((reason, plan.plan_id, plan.version, plan.proposal, plan.prepared_t,
                    plan.stage, plan.captured, plan.consumed, plan.dead_attempt))


def _source_contract_key(plan):
    return _digest((plan.plan_id, plan.version, plan.proposal, plan.prepared_t, plan.dead_attempt))


def _validate_progress(plan, path):
    count = len(path)-1
    if (plan.source_contract != _source_contract_key(plan)
            or plan.status not in ACTIVE | {"complete", "invalid"}
            or not math.isfinite(plan.prepared_t) or not isinstance(plan.stage, int)
            or not 0 <= plan.stage < count
            or not isinstance(plan.captured, tuple) or not isinstance(plan.consumed, tuple)
            or any(type(i) is not int or not 0 <= i <= plan.stage for i in plan.captured+plan.consumed)
            or plan.captured != tuple(sorted(set(plan.captured)))
            or plan.consumed != tuple(range(len(plan.consumed)))
            or any(i not in plan.consumed for i in range(plan.stage))
            or any(plan.proposal.mechanisms[i] != "radio" for i in plan.captured)
            or any(plan.proposal.mechanisms[i] == "radio" and i not in plan.captured for i in plan.consumed)):
        raise ValueError("Invalid recovery progress / Progreso de recuperación no válido")
    if plan.status == "complete" and (plan.stage != count-1 or len(plan.consumed) != count):
        raise ValueError("Incomplete recovery marked complete / Recuperación incompleta marcada como completa")
    if plan.status == "stage_consumed" and plan.stage not in plan.consumed:
        raise ValueError("Unconsumed recovery stage / Etapa de recuperación sin consumir")
    if plan.status in {"prepared", "receipt_pending"} and (plan.stage in plan.captured or plan.stage in plan.consumed):
        raise ValueError("Pending recovery already consumed / Recuperación pendiente ya consumida")


def _invalidate_plan(state, plan, *, unprepared=False):
    plan.status = "invalid"
    plan.invalidation = None
    reason = "stage_unprepared" if unprepared else "sources_unavailable"
    try:
        path = _validate_physical(state, plan.proposal)
        _validate_progress(plan, path)
        _validate_prepared_sources(state, plan, path, archival=True, unprepared=unprepared)
        if unprepared and (plan.stage == 0 or plan.stage in plan.captured or plan.stage in plan.consumed
                           or plan.proposal.mechanisms[plan.stage] != "radio"
                           or _radio_id(plan, plan.stage) in state.world.radio_opportunities):
            raise ValueError("Invalid unprepared recovery boundary / Límite de etapa no preparada no válido")
    except ValueError:
        return  # Corrupt physical/ledger/proposal state remains unsaveable.
    plan.invalidation = (reason, _invalidation_key(plan, reason))


def confirm_recovery(state, proposal):
    """All fallible work on a clone; publish a prepared write set afterwards.

    Preserve existing node/pool object identities: uplink and engine callers can
    retain references across the trigger. No file, intel or counter is consumed.
    """
    existing = next((p for p in state.world.recovery_plans.values() if p.proposal.block == proposal.block and p.status in ACTIVE), None)
    if existing:
        _validate_physical(state, existing.proposal)
        return existing
    if snapshot_key(state) != proposal.snapshot:
        raise ValueError("Stale recovery snapshot")
    path = _validate_physical(state, proposal)
    _validate_stage_sources(state, proposal, path)
    access = directed_access(state).get(path[0])
    if access != proposal.access or proposal.sites[0].kind not in HUBS or proposal.mechanisms[0] != "radio":
        raise ValueError("Recovery origin is not accessible")
    if _first_reception(state, path[0], proposal.first_emission_id):
        raise ValueError("Recovery first reception is outside physical coverage")
    staged = deepcopy(state)
    sectors = {site.physical_sector_id for nid,site in zip(path,proposal.sites)
               if nid not in staged.world.space.nodes or not staged.world.space.nodes[nid].historical_key}
    if sectors:
        _ensure_sector_cluster_generated(staged, sorted(sectors))
    if any(nid not in staged.world.space.nodes for nid in path):
        raise ValueError("Recovery endpoint could not be materialized")
    _validate_physical(staged, proposal)
    _validate_stage_sources(staged, proposal, path)
    for i, mechanism in enumerate(proposal.mechanisms[1:], 1):
        if mechanism == "salvage" and _salvage_source(staged, path[i], path[i+1], proposal.sites[i]) != proposal.stage_sources[i]:
            raise ValueError("Recovery salvage source is stale")
    ident = "structural:"+_digest((VERSION, proposal.scope, proposal.block, path, proposal.stage_sources,
        state.world.dead_nodes.get(proposal.block.removeprefix("deadnode:"))))
    if ident in state.world.recovery_plans:
        return state.world.recovery_plans[ident]
    if any(key.startswith(ident+":") for key in state.world.radio_opportunities):
        raise ValueError("Recovery ledger identity collision")
    plan = RecoveryPlan(ident, proposal, float(state.clock.t))
    if proposal.block.startswith("deadnode:"):
        tracker = state.world.dead_nodes.get(proposal.block[len("deadnode:"):])
        if tracker is None:
            raise ValueError("Missing deadnode tracker")
        plan.dead_attempt = tracker.attempts
    plan.source_contract = _source_contract_key(plan)
    staged.world.recovery_plans[ident] = plan
    _radio_stage(staged, plan, 0)
    plan.status = "receipt_pending"
    validate_universe_state(staged)
    # Recovery must not run a scheduler roll or modify gameplay state while
    # preparing a source. The shared initializer only finalizes reserved hosts;
    # those are excluded from recovery selection.
    if (staged.world.lore != state.world.lore or staged.world.lore_placements != state.world.lore_placements
            or staged.world.arc_placements != state.world.arc_placements
            or staged.world.known_links != state.world.known_links
            or staged.os != state.os or staged.meta != state.meta or staged.ship != state.ship):
        raise ValueError("Unexpected side effect during recovery preparation")
    if snapshot_key(state) != proposal.snapshot:
        raise ValueError("Recovery state changed during preparation")
    # Materialization and pool initialization have finished successfully. Their
    # existing invariants are checked before this non-fallible publication.
    for nid, node in staged.world.space.nodes.items():
        old = state.world.space.nodes.get(nid)
        if old is None:
            state.world.space.nodes[nid] = node
        else:
            for field in fields(node):
                setattr(old, field.name, getattr(node, field.name))
    state.world.space.edges = staged.world.space.edges
    for name in ("manifest_definition", "universe_rules_key", "generated_sectors", "sector_states", "intersector_link_pairs", "sparse_guardrail_done"):
        setattr(state.world, name, getattr(staged.world, name))
    for nid in path:
        if nid not in staged.world.node_pools:
            continue
        pool = staged.world.node_pools[nid]
        old = state.world.node_pools.get(nid)
        if old is None:
            state.world.node_pools[nid] = pool
        else:
            for field in fields(pool):
                setattr(old, field.name, getattr(pool, field.name))
    state.world.recovery_plans[ident] = plan
    radio_id = _radio_id(plan, 0)
    state.world.radio_opportunities[radio_id] = staged.world.radio_opportunities[radio_id]
    state.world.recovery_activation_deferred = False
    return plan


def request_recovery(state, block="global", target_id=None):
    if any(p.proposal.block == block and p.status in ACTIVE for p in state.world.recovery_plans.values()):
        return
    prior = state.world.recovery_searches.get(block, {})
    if prior.get("anchor") != state.world.current_node_id:
        prior = {}
    state.world.recovery_searches[block] = {**prior, "status": "search_pending"}
    result = select_recovery(state, block, target_id, cursor=prior.get("cursor",0), retained=prior.get("retained",()))
    if result.status == "validated" and result.proposal:
        try:
            confirm_recovery(state, result.proposal)
        except (ValueError, RuntimeError) as exc:
            result = SearchResult("invalid", None, "preparation:"+str(exc), result.cursor, result.retained, result.sectors, result.examined_cohorts, result.expansions, result.edges)
    state.world.recovery_searches[block] = {"status": result.status, "reason": result.reason, "cursor": result.cursor,
        "retained": result.retained, "sectors": result.sectors, "expansions": result.expansions, "edges": result.edges,
        "anchor": state.world.current_node_id}


def delivery_valid(state, opportunity):
    delivery = opportunity.delivery
    plan = state.world.recovery_plans.get(delivery.get("plan"))
    if not plan or plan.version not in {VERSION, LEGACY_VERSION} or plan.status not in ACTIVE:
        return False
    index = delivery.get("stage")
    if index != plan.stage or index in plan.captured or (index and index-1 not in plan.consumed):
        return False
    try:
        path = _validate_physical(state, plan.proposal)
        _validate_prepared_sources(state,plan,path)
        if opportunity.origin_node_id != path[index] or plan.proposal.mechanisms[index] != "radio":
            return False
        if index == 0 and not plan.captured:
            if path[0] not in directed_access(state):
                return False
            if plan.dead_attempt is not None:
                tracker = state.world.dead_nodes.get(plan.proposal.block[len("deadnode:"):])
                if tracker is None or tracker.attempts != plan.dead_attempt:
                    return False
        return True
    except (ValueError, IndexError):
        return False


def on_capture(state, opportunity):
    plan = state.world.recovery_plans[opportunity.delivery["plan"]]
    index = opportunity.delivery["stage"]
    if not plan.captured:
        if plan.dead_attempt is not None:
            tracker = state.world.dead_nodes[plan.proposal.block[len("deadnode:"):]]
            tracker.attempts += 1
            tracker.last_action_t = state.clock.t
        else:
            state.world.mobility_failsafe_count += 1
            state.world.exploration_recovery.generation += 1
            state.world.mobility_hints.append({"plan": plan.plan_id, "path": opportunity.path, "t": state.clock.t})
    plan.captured += (index,)
    plan.status = "active"


def mark_stage_read(state, file_path):
    for plan in state.world.recovery_plans.values():
        if plan.status not in ACTIVE:
            continue
        path = _path(state, plan.proposal)
        index = plan.stage
        source, dest = path[index:index+2]
        if dest not in state.world.known_links.get(source, ()):
            continue
        if plan.proposal.mechanisms[index] == "radio":
            op = state.world.radio_opportunities.get(_radio_id(plan, index))
            matches = op and op.status == "read_imported" and op.path == file_path
        elif plan.proposal.mechanisms[index] == "salvage":
            archive = (plan.proposal.stage_sources[index].reference if plan.version == VERSION
                       else f"/logs/nav/{plan.plan_id.replace(':','_')}_{index}.txt")
            matches = file_path == f"/remote/{source}{archive}"
        else:
            continue
        if matches and index not in plan.consumed:
            plan.consumed += (index,)
            plan.status = "stage_consumed"


def advance_recovery_plans(state):
    for plan in state.world.recovery_plans.values():
        if plan.status not in ACTIVE:
            continue
        try:
            path = _validate_physical(state, plan.proposal)
            _validate_progress(plan, path)
            _validate_prepared_sources(state,plan,path)
        except ValueError:
            _invalidate_plan(state, plan)
            continue
        index = plan.stage
        if index not in plan.consumed or state.world.current_node_id != path[index+1]:
            continue
        if index+1 == len(path)-1:
            plan.status = "complete"
            continue
        plan.stage += 1
        if plan.proposal.mechanisms[plan.stage] == "radio":
            try:
                op = _radio_stage(state, plan, plan.stage)
                if op.status in {"received", "read_imported"}:
                    plan.captured += (plan.stage,)
                    plan.status = "active"
                    if (op.status == "read_imported" and
                            path[plan.stage+1] in state.world.known_links.get(path[plan.stage], ())):
                        plan.consumed += (plan.stage,)
                        plan.status = "stage_consumed"
                else:
                    plan.status = "receipt_pending"
            except ValueError:
                _invalidate_plan(state, plan, unprepared=True)
        elif plan.proposal.mechanisms[plan.stage] == "known_route":
            if path[plan.stage+1] not in state.world.known_links.get(path[plan.stage], ()):
                _invalidate_plan(state, plan)
            else:
                plan.consumed += (plan.stage,)
                plan.status = "stage_consumed"
        else:
            plan.status = "active"


def validate_recovery_state(state):
    """Reject incompatible plans; never rewrite or delete a save file."""
    for key, plan in state.world.recovery_plans.items():
        if not isinstance(plan, RecoveryPlan) or key != plan.plan_id or plan.version not in {VERSION, LEGACY_VERSION}:
            raise ValueError("Incompatible structural recovery / Recuperación estructural incompatible")
        path = _validate_physical(state, plan.proposal)
        _validate_progress(plan, path)
        invalidation = getattr(plan, "invalidation", None)  # Pre-correction slots.
        if plan.status == "invalid":
            if (not isinstance(invalidation, tuple) or len(invalidation) != 2
                    or invalidation[0] not in {"sources_unavailable", "stage_unprepared"}
                    or invalidation[1] != _invalidation_key(plan, invalidation[0])):
                raise ValueError("Uncertified recovery invalidation / Invalidación de recuperación sin constancia válida")
            unprepared = invalidation[0] == "stage_unprepared"
            if unprepared and (plan.stage == 0 or plan.stage in plan.captured or plan.stage in plan.consumed
                               or plan.proposal.mechanisms[plan.stage] != "radio"
                               or _radio_id(plan, plan.stage) in state.world.radio_opportunities):
                raise ValueError("Invalid unprepared recovery boundary / Límite de etapa no preparada no válido")
            _validate_prepared_sources(state, plan, path, archival=True, unprepared=unprepared)
        else:
            if invalidation is not None:
                raise ValueError("Active recovery carries invalidation checkpoint / Recuperación activa con constancia de invalidación")
            _validate_prepared_sources(state,plan,path)
        if not plan.captured and (not plan.proposal.access.path or _first_reception(
                state, path[0], plan.proposal.first_emission_id, receiver_node_id=plan.proposal.access.path[0],
                sensitivity=plan.proposal.first_reception_sensitivity, at_t=plan.prepared_t,
                legacy=plan.version == LEGACY_VERSION)):
            raise ValueError("Invalid initial reception context / Contexto inicial de recepción no válido")
        if not 0 <= plan.stage < len(path)-1 or any(i < 0 or i >= len(path)-1 for i in plan.captured+plan.consumed):
            raise ValueError("Invalid structural recovery stage / Etapa de recuperación no válida")
        if any(nid not in state.world.space.nodes for nid in path):
            raise ValueError("Missing structural recovery site / Falta un emplazamiento de recuperación")
