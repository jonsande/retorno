"""Versioned, read-only historical universe. Materialization lives in generator.

The prototype entrypoint retains its original version and matching policy for
comparison. Production uses fixed-origin priority and eight colored rounds.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import math
import random
import inspect
import sys
from types import SimpleNamespace

from retorno.config.balance import Balance
from retorno.model.world import region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_locations, load_worldgen_archetypes, load_worldgen_templates
from retorno.worldgen.catalog import _configuration_key
from retorno.worldgen.generator import (
    _hash64, _maybe_apply_sparse_guardrail, _neighbor_sector_ids_2d,
    _pair_key, _parse_sector_id, _plan_sector_kinds, _PLAYABLE_HUB_KINDS,
    _sample_sector_node, _sector_center, _select_archetype,
)

PROTOTYPE_VERSION = "prototype-4d3e1b-v1"
ALGORITHM_VERSION = "historical-world-v1"
MAX_SECTOR_INDEX = 2**48 - 32


class EvidenceStatus(str, Enum):
    CERTIFIED = "certified"
    CONDITIONAL = "conditional"
    INVALID = "invalid"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True, slots=True)
class Assessment:
    status: EvidenceStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True, order=True)
class SiteIdentity:
    """Injective addresses within one scope; never legacy node_id allocation.

    The namespace is part of identity, including when an authored raw id exactly
    equals another site's encoded address. SPECIAL is reserved, not generated.
    """
    scope: str
    namespace: str
    local_id: str

    @property
    def encoded(self) -> str:
        return json.dumps((self.scope, self.namespace, self.local_id), separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class AuthoredSite:
    raw_id: str
    kind: str
    position_ly: tuple[float, float, float]
    is_hub: bool = False


@dataclass(frozen=True, slots=True)
class ManifestDefinition:
    seed: int
    algorithm_version: str
    configuration_json: str
    authored: tuple[AuthoredSite, ...]
    configuration_key: str
    hop_cap_ly: float
    scope: str
    rules_key: str = ""


@dataclass(frozen=True, slots=True)
class HistoricalSite:
    identity: SiteIdentity
    generation_sector_id: str
    physical_sector_id: str
    position_ly: tuple[float, float, float]
    kind: str
    region: str
    is_hub: bool
    is_topology_hub: bool
    legacy_id_hint: str  # Sorting/diagnostic only, NOT a collision-safe node id.


@dataclass(frozen=True, slots=True)
class HistoricalEdge:
    left: SiteIdentity
    right: SiteIdentity
    distance_ly: float
    kind: str


@dataclass(frozen=True, slots=True)
class SectorManifest:
    sector_id: str
    template_region: str
    archetype: str
    sites: tuple[HistoricalSite, ...]
    topology_hub: SiteIdentity | None
    internal_edges: tuple[HistoricalEdge, ...]


@dataclass(frozen=True, slots=True)
class ManifestResult:
    scope: str
    sectors: tuple[SectorManifest, ...]
    edges: tuple[HistoricalEdge, ...]
    boundary_sites: tuple[HistoricalSite, ...]
    evaluated_generation_sectors: tuple[str, ...]
    historical_data: Assessment = Assessment(EvidenceStatus.CERTIFIED, ("experimental_versioned_rules_only",))
    physical_inventory: Assessment = Assessment(EvidenceStatus.NOT_EVALUATED, ("untruncated_z_reverse_inventory_not_implemented",))
    materialization: Assessment = Assessment(EvidenceStatus.CONDITIONAL, ("production_integration_not_authorized",))
    resources: Assessment = Assessment(EvidenceStatus.NOT_EVALUATED, ("no_salvage_pools_or_files_evaluated",))
    environment: Assessment = Assessment(EvidenceStatus.NOT_EVALUATED, ("radiation_and_historical_age_not_prototyped",))


@dataclass(frozen=True, slots=True)
class SiteLookup:
    assessment: Assessment
    site: HistoricalSite | None = None


def authored_base(locations: Sequence[dict]) -> tuple[AuthoredSite, ...]:
    """Match bootstrap's physical base, excluding the player-ship definition.

    Duplicate ids fail explicitly instead of inheriting legacy first-file-wins.
    Names, knowledge, files and loot do not participate in this physical base.
    """
    sites = []
    for location in locations:
        cfg = location.get("node", {})
        nid = cfg.get("node_id")
        if not nid or nid == "RETORNO_SHIP":
            continue
        kind = cfg.get("kind", "unknown")
        sites.append(AuthoredSite(nid, kind,
            tuple(float(cfg.get(f"{axis}_ly", 0.0)) for axis in "xyz"),
            bool(cfg.get("is_hub", kind in _PLAYABLE_HUB_KINDS))))
    return tuple(sites)


def _scope(seed, version, configuration, authored, cap, rules_key=""):
    payload = (seed, version, configuration, cap,
               tuple((a.raw_id, a.kind, a.position_ly, a.is_hub) for a in authored))
    if rules_key:
        payload += (rules_key,)
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def physical_rules_key():
    """Reject reinterpretation after configuration/kernel changes, including loot."""
    from retorno.runtime.data_loader import load_modules
    if (sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 12)
        or sys.float_info.radix != 2 or sys.float_info.mant_dig != 53 or sys.float_info.rounds != 1):
        raise ValueError("Unsupported historical sampling kernel")
    if hashlib.sha256(inspect.getsource(random.Random.gauss).encode()).hexdigest() != "805d06bf35a66766531570b7642daeeda36359953ab37584ca7097b0ca7dde2a":
        raise ValueError("Historical Gaussian kernel changed")
    from retorno.worldgen.catalog import _configuration_key
    balance = {key: value for key, value in vars(Balance).items()
               if key.startswith("PROCEDURAL_RAD") or key == "SALVAGE_DRONES_BY_KIND"}
    authored = [(loc.get("node"), loc.get("salvage")) for loc in load_locations()]
    payload = (_configuration_key(load_worldgen_templates(), load_worldgen_archetypes()),
               list(load_modules().items()), balance, authored,
               inspect.getsource(random.Random.gauss), "cpython-3.12-binary64")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def define_manifest(
    seed: int, *, templates: dict | None = None, archetypes: dict | None = None,
    authored: Sequence[AuthoredSite] | None = None, algorithm_version: str = ALGORITHM_VERSION,
) -> ManifestDefinition:
    """Capture a fixed definition; all subsequent queries use this snapshot.

    No GameState accepted. Configuration/file loading occurs only at this boundary.
    Weighted choice order is preserved, as it is a legacy configuration semantic.
    """
    if type(seed) is not int or algorithm_version not in {ALGORITHM_VERSION, PROTOTYPE_VERSION}:
        raise ValueError("Invalid seed or unsupported prototype algorithm version")
    templates = load_worldgen_templates() if templates is None else templates
    archetypes = load_worldgen_archetypes() if archetypes is None else archetypes
    base = authored_base(load_locations()) if authored is None else tuple(authored)
    for a in base:
        if (not isinstance(a, AuthoredSite) or not isinstance(a.raw_id, str)
            or not isinstance(a.kind, str) or type(a.is_hub) is not bool):
            raise ValueError("Invalid authored identity or hub flag")
    base = tuple(sorted((AuthoredSite(a.raw_id, a.kind, tuple(a.position_ly), a.is_hub)
                         for a in base), key=lambda a: a.raw_id))
    if len({a.raw_id for a in base}) != len(base):
        raise ValueError("Duplicate authored identity in immutable base")
    for a in base:
        if not a.raw_id or not a.kind or len(a.position_ly) != 3 or not all(math.isfinite(v) for v in a.position_ly):
            raise ValueError("Invalid authored physical definition")
    if set(templates) != {"disk", "bulge", "halo"} or not archetypes:
        raise ValueError("Complete canonical regional/archetype configuration required")
    if not {"empty", "ruin_field", "relay_corridor", "isolated_station"} <= set(archetypes):
        raise ValueError("Initial guardrail requires its canonical archetypes")
    for cfg in archetypes.values():
        low, high = cfg.get("node_count_min"), cfg.get("node_count_max")
        cap = cfg.get("intersector_link_max")
        if (type(low) is not int or type(high) is not int or low < 0 or high < low
            or type(cap) is not int or cap < 0):
            raise ValueError("Invalid canonical count or topology budget")
        for field in ("intersector_link_prob", "playable_hub_prob", "extra_internal_link_prob"):
            value = float(cfg.get(field, 0.0))
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Invalid canonical probability")
        for field in ("kind_weights", "playable_hub_kind_weights"):
            if any(not math.isfinite(float(w)) or float(w) < 0 for w in cfg.get(field, {}).values()):
                raise ValueError("Invalid canonical kind weight")
        if any(type(c) is not int or c < 0 for c in cfg.get("kind_caps", {}).values()):
            raise ValueError("Invalid canonical kind cap")
    for template in templates.values():
        if not set(template.get("archetype_weights", {})) <= set(archetypes):
            raise ValueError("Unknown archetype in regional template")
        if any(not math.isfinite(float(w)) or float(w) < 0 for w in template.get("archetype_weights", {}).values()):
            raise ValueError("Invalid canonical archetype weight")
        sigma = float(template.get("z_sigma", 0.3) or 0.3)
        if not math.isfinite(sigma) or sigma <= 0:
            raise ValueError("Invalid Z dispersion")
    configuration = _configuration_key(templates, archetypes)
    cap = float(Balance.MAX_ROUTE_HOP_LY)
    if cap != 45.0:
        raise ValueError("Prototype requires the approved 45 ly cap")
    frozen = json.dumps((templates, archetypes), separators=(",", ":"), allow_nan=False)
    rules_key = physical_rules_key() if algorithm_version == ALGORITHM_VERSION else ""
    if rules_key and any(float(t.get("z_sigma", .3) or .3) > 2 for t in templates.values()):
        raise ValueError("Z dispersion outside certified historical kernel domain")
    return ManifestDefinition(seed, algorithm_version, frozen, base, configuration, cap,
                              _scope(seed, algorithm_version, configuration, base, cap, rules_key), rules_key)


class _Session:
    """Call-local finite dependency closure; no persistent or global cache."""
    def __init__(self, definition: ManifestDefinition):
        self.d = definition
        self.templates, self.archetypes = json.loads(definition.configuration_json)
        if (definition.algorithm_version not in {ALGORITHM_VERSION, PROTOTYPE_VERSION}
            or _configuration_key(self.templates, self.archetypes) != definition.configuration_key
            or float(Balance.MAX_ROUTE_HOP_LY) != definition.hop_cap_ly
            or _scope(definition.seed, definition.algorithm_version, definition.configuration_key,
                      definition.authored, definition.hop_cap_ly, definition.rules_key) != definition.scope
            or (definition.algorithm_version == ALGORITHM_VERSION and definition.rules_key != physical_rules_key())):
            raise ValueError("Definition/environment changed; define a new manifest explicitly")
        self.view = SimpleNamespace(meta=SimpleNamespace(rng_seed=definition.seed),
                                    world=SimpleNamespace(sparse_guardrail_done=False))
        origin = sector_id_for_pos(0.0, 0.0, 0.0)
        self.overrides, self.forced = _maybe_apply_sparse_guardrail(
            self.view, sorted(_neighbor_sector_ids_2d(origin)), self.templates)
        self.authored_by_sector: dict[str, list[AuthoredSite]] = {}
        for a in definition.authored:
            self.authored_by_sector.setdefault(sector_id_for_pos(*a.position_ly), []).append(a)
        self.sectors: dict[str, SectorManifest] = {}
        self.rankings: dict[str, tuple[str, ...]] = {}

    def _identity(self, namespace, local_id):
        return SiteIdentity(self.d.scope, namespace, local_id)

    def sector(self, sid: str) -> SectorManifest:
        if sid in self.sectors:
            return self.sectors[sid]
        if len(self.sectors) >= 32768:
            raise ValueError("Historical query work budget exhausted; inventory incomplete")
        if self.d.algorithm_version == ALGORITHM_VERSION and any(abs(v) > MAX_SECTOR_INDEX for v in _parse_sector_id(sid)):
            raise ValueError("Sector outside certified binary64 coordinate domain")
        region = region_for_pos(*_sector_center(sid))
        archetype = _select_archetype(self.view, sid, region, self.templates, self.overrides)
        cfg, template = self.archetypes[archetype], self.templates[region]
        base = self.authored_by_sector.get(sid, ())
        nodes = {a.raw_id: SimpleNamespace(node_id=a.raw_id, kind=a.kind, is_hub=a.is_hub,
                    x_ly=a.position_ly[0], y_ly=a.position_ly[1], z_ly=a.position_ly[2]) for a in base}
        view = SimpleNamespace(meta=self.view.meta, world=SimpleNamespace(space=SimpleNamespace(nodes=nodes)))
        kinds, hub_kind = _plan_sector_kinds(view, sid, archetype, region, template, cfg,
                                           force_playable_hub=sid in self.forced)
        sites = [HistoricalSite(self._identity("authored", a.raw_id), sid, sid, a.position_ly,
                                a.kind, region_for_pos(*a.position_ly), a.is_hub, False, a.raw_id) for a in base]
        for index, kind in enumerate(kinds):
            pos, rng = _sample_sector_node(self.d.seed, sid, archetype, index, kind,
                                          float(template.get("z_sigma", 0.3) or 0.3))
            if not all(math.isfinite(v) for v in pos):
                raise ValueError("Nonfinite sample outside representable coordinate domain")
            identity = self._identity("procedural", json.dumps((sid, index), separators=(",", ":")))
            hint = f"{'WRECK' if kind == 'ship' else kind.upper()}_{rng.getrandbits(24):06X}"
            sites.append(HistoricalSite(identity, sid, sector_id_for_pos(*pos), pos, kind,
                         region_for_pos(*pos), kind == hub_kind and kind in _PLAYABLE_HUB_KINDS, False, hint))
        sites.sort(key=lambda s: (s.legacy_id_hint, s.identity))
        hub = next((s for s in sites if s.is_hub), sites[0] if sites else None)
        if hub:
            sites = [replace(s, is_topology_hub=s.identity == hub.identity,
                             is_hub=s.is_hub or (s.identity == hub.identity and s.kind in _PLAYABLE_HUB_KINDS))
                     for s in sites]
            hub = next(s for s in sites if s.is_topology_hub)
        edges = {}
        if hub:
            for site in sites:
                if site != hub:
                    self._add_edge(edges, site, hub, "internal")
            rng = random.Random(_hash64(self.d.seed, f"sector_internal_links:{sid}:{archetype}"))
            for site in sites:
                if site == hub or rng.random() > float(cfg.get("extra_internal_link_prob", 0.0)):
                    continue
                others = [s for s in sites if s.identity not in {hub.identity, site.identity}]
                if others:
                    self._add_edge(edges, site, others[rng.randrange(len(others))], "internal")
        result = SectorManifest(sid, region, archetype, tuple(sites), hub.identity if hub else None,
                                tuple(edges[k] for k in sorted(edges)))
        self.sectors[sid] = result
        return result

    def _add_edge(self, edges, left, right, kind):
        distance = math.dist(left.position_ly, right.position_ly)
        if left.identity != right.identity and distance <= self.d.hop_cap_ly:
            a, b = sorted((left.identity, right.identity))
            edges[a, b] = HistoricalEdge(a, b, distance, kind)

    def hub(self, sid):
        sector = self.sector(sid)
        return next((s for s in sector.sites if s.identity == sector.topology_hub), None)

    def candidate(self, left_sid, right_sid):
        a, b = sorted((left_sid, right_sid))
        left, right = self.sector(a), self.sector(b)
        lcfg, rcfg = self.archetypes[left.archetype], self.archetypes[right.archetype]
        if min(int(lcfg["intersector_link_max"]), int(rcfg["intersector_link_max"])) <= 0:
            return None
        lh, rh = self.hub(a), self.hub(b)
        if not lh or not rh or math.dist(lh.position_ly, rh.position_ly) > self.d.hop_cap_ly:
            return None
        prob = min(float(lcfg["intersector_link_prob"]), float(rcfg["intersector_link_prob"]))
        rng = random.Random(_hash64(self.d.seed, f"sector_pair:{_pair_key(a,b)}:{left.archetype}:{right.archetype}"))
        return (lh, rh) if prob > 0 and rng.random() <= prob else None

    def ranked(self, sid):
        if sid not in self.rankings:
            viable = [other for other in _neighbor_sector_ids_2d(sid, include_self=False)
                      if self.candidate(sid, other)]
            viable.sort(key=lambda other: (_hash64(self.d.seed, f"manifest_pair_priority:{_pair_key(sid, other)}"), other))
            cap = int(self.archetypes[self.sector(sid).archetype]["intersector_link_max"])
            self.rankings[sid] = tuple(viable[:cap])
        return self.rankings[sid]


def query_manifest(
    definition: ManifestDefinition, sector_ids: Sequence[str], *, max_sectors: int = 64,
) -> ManifestResult:
    """Complete generation cohorts and incident edges, with bounded work.

    Production uses eight matching rounds; the frozen prototype uses mutual
    top-k. Neither result is an inverse physical inventory: use
    query_physical_sectors for that distinct question.
    """
    if type(max_sectors) is not int or max_sectors <= 0:
        raise ValueError("Positive technical sector bound required")
    if isinstance(sector_ids, (str, bytes)) or not isinstance(sector_ids, Sequence):
        raise TypeError("An explicit bounded sequence of generation sectors is required")
    if len(sector_ids) > max_sectors:
        raise ValueError("Technical query budget exceeded; no absence conclusion")
    for sid in sector_ids:
        _parse_sector_id(sid)
        if not all(math.isfinite(v) for v in _sector_center(sid)):
            raise ValueError("Sector coordinates outside representable domain")
    return _query_session(new_session(definition), sector_ids)


def new_session(definition):
    if definition.algorithm_version == ALGORITHM_VERSION:
        from retorno.worldgen.topology import ColoredSession
        return ColoredSession(definition)
    return _Session(definition)


def _query_session(session, sector_ids):
    """Shared bounded result assembly for versioned topology sessions."""
    definition = session.d
    requested = sorted(set(sector_ids))
    sectors = tuple(session.sector(sid) for sid in requested)
    edges = {(e.left, e.right): e for sector in sectors for e in sector.internal_edges}
    boundary = {}
    for sid in requested:
        for other in session.ranked(sid):
            if sid in session.ranked(other):
                left, right = session.candidate(sid, other)
                session._add_edge(edges, left, right, "intersector")
                for site in (left, right):
                    if site.generation_sector_id not in requested:
                        boundary[site.identity] = site
    result = ManifestResult(definition.scope, sectors, tuple(edges[k] for k in sorted(edges)),
                            tuple(boundary[k] for k in sorted(boundary)), tuple(sorted(session.sectors)))
    if definition.algorithm_version == ALGORITHM_VERSION:
        result = replace(result,
            historical_data=Assessment(EvidenceStatus.CERTIFIED, ("versioned_historical_definition",)),
            physical_inventory=Assessment(EvidenceStatus.NOT_EVALUATED, ("use_inverse_physical_query",)),
            materialization=Assessment(EvidenceStatus.CONDITIONAL, ("bounded_runtime_materializer_required",)),
            environment=Assessment(EvidenceStatus.NOT_EVALUATED, ("properties_evaluated_at_materialization",)))
    return result


def lookup_site(definition: ManifestDefinition, identity: SiteIdentity) -> SiteLookup:
    """Validate typed addresses without converting legacy conditional samples."""
    session = _Session(definition)
    if identity.scope != definition.scope:
        return SiteLookup(Assessment(EvidenceStatus.INVALID, ("different_universe_scope",)))
    if identity.namespace == "special":
        return SiteLookup(Assessment(EvidenceStatus.NOT_EVALUATED, ("dynamic_special_sites_outside_historical_manifest",)))
    sid = None
    if identity.namespace == "authored":
        base = next((a for a in definition.authored if a.raw_id == identity.local_id), None)
        if base:
            sid = sector_id_for_pos(*base.position_ly)
    elif identity.namespace == "procedural":
        try:
            candidate, index = json.loads(identity.local_id)
            _parse_sector_id(candidate)
            if type(index) is int and index >= 0:
                sid = candidate
        except (ValueError, TypeError):
            pass
    if sid is not None:
        site = next((s for s in session.sector(sid).sites if s.identity == identity), None)
        if site:
            return SiteLookup(Assessment(EvidenceStatus.CERTIFIED, ("fixed_definition_site",)), site)
    return SiteLookup(Assessment(EvidenceStatus.INVALID, ("no_site_at_canonical_address",)))


@dataclass(frozen=True, slots=True)
class PhysicalInventory:
    sector_ids: tuple[str, ...]
    sites: tuple[HistoricalSite, ...]
    examined_generation_sectors: tuple[str, ...]
    complete: bool = True


def _physical_inventory(session, sector_ids, max_sectors=64):
    if isinstance(sector_ids, (str, bytes)) or not isinstance(sector_ids, Sequence):
        raise TypeError("A bounded sequence of physical sectors is required")
    if type(max_sectors) is not int or max_sectors <= 0 or len(sector_ids) > max_sectors:
        raise ValueError("Physical inventory request exceeds technical budget")
    if session.d.algorithm_version != ALGORITHM_VERSION:
        raise ValueError("Prototype samples cannot certify a physical inventory")
    requested = tuple(sorted(set(sector_ids)))
    candidates = set()
    for sid in requested:
        x, y, z = _parse_sector_id(sid)
        if any(abs(v) > MAX_SECTOR_INDEX-4 for v in (x,y,z)):
            raise ValueError("Physical sector outside certified binary64 domain")
        # random() has 53 bits. Current fresh gauss has |standard Z| < 8.58.
        # Use 9*sigma plus TWO ly rounding margin at |index| <= 2**48-32.
        # X/Y round monotonically into [10*i,10*i+10], inclusive at the top:
        # only the current or immediately preceding source index can contribute.
        for sx in (x-1,x):
            for sy in (y-1,y):
                for sz in range(z-2,z+3):
                    source = f"S{sx:+04d}_{sy:+04d}_{sz:+04d}"
                    center = _sector_center(source)
                    template = session.templates[region_for_pos(*center)]
                    radius = 9*float(template.get("z_sigma", .3) or .3)+2
                    if center[2]+radius >= z*10 and center[2]-radius < (z+1)*10:
                        candidates.add(source)
    sites = {}
    for source in sorted(candidates):
        for site in session.sector(source).sites:
            if site.physical_sector_id in requested:
                sites[site.identity] = site
    return PhysicalInventory(requested, tuple(sites[k] for k in sorted(sites)), tuple(sorted(candidates)))


def query_physical_sectors(definition, sector_ids, *, max_sectors=64):
    """Complete inverse inventory in the explicitly certified numeric domain.

    The unmodified Gaussian is not truncated. Request/domain/work exhaustion
    raises before returning a result, never a successful partial empty inventory.
    """
    return _physical_inventory(new_session(definition), sector_ids, max_sectors)


def operative_id(definition, site):
    if site.identity.namespace == "authored":
        return site.identity.local_id
    sid, index = json.loads(site.identity.local_id)
    reserved = {a.raw_id for a in definition.authored}
    suffix = ""
    attempt = 0
    while True:
        candidate = f"{sid}:WG1{suffix}_{definition.scope}_{index}"
        if candidate not in reserved:
            return candidate
        attempt += 1
        suffix = f"C{attempt}"


def resolve_operative_id(definition, node_id):
    """Exact deterministic lookup; no arbitrary suffix or registry allocation."""
    for a in definition.authored:
        if a.raw_id == node_id:
            return lookup_site(definition, SiteIdentity(definition.scope,"authored",node_id)).site
    import re
    match = re.fullmatch(r"(S[^:]+):WG1(?:C[1-9][0-9]*)?_([0-9a-f]{64})_([0-9]+)", node_id)
    if not match or match[2] != definition.scope:
        return None
    try:
        identity = SiteIdentity(definition.scope,"procedural",json.dumps((match[1],int(match[3])),separators=(",",":")))
        result = lookup_site(definition,identity)
        if result.site and operative_id(definition,result.site) == node_id:
            return result.site
    except (ValueError,TypeError):
        pass
    return None
