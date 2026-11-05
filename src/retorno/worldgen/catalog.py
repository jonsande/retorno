"""Read-only preexistence evidence, independent of recovery or ship capability.

Queries certify versioned historical generation cohorts. Legacy conditional
addresses are never upgraded into manifest sites. No result permits
insertion, publishes knowledge, or establishes a route/information source.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from retorno.config.balance import Balance
from retorno.core.gamestate import GameState
from retorno.model.world import SECTOR_SIZE_LY
from retorno.worldgen.generator import _parse_sector_id


class SiteStatus(str, Enum):
    PHYSICAL = "physical"
    VERIFIED = "verified_procedural"
    CONDITIONAL = "conditional"
    INADMISSIBLE = "inadmissible"


@dataclass(frozen=True, slots=True)
class SiteRecord:
    """Internal evidence, not player intel or recovery eligibility.

    Public keys identify historical sites; legacy fixture keys remain conditional.
    node_id is supplied only for an already physical node. Historical existence
    does not establish narrative eligibility or authorize materialization.
    """
    key: str
    status: SiteStatus
    generation_sector_id: str | None
    physical_sector_id: str
    position_ly: tuple[float, float, float]
    kind: str
    region: str
    archetype: str | None = None
    slot_index: int | None = None
    node_id: str | None = None
    conditions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectorCatalog:
    sector_id: str
    region: str
    baseline_archetype: str
    recorded_archetype: str | None
    generated: bool
    sites: tuple[SiteRecord, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CatalogResult:
    """Bounded requested family only; no exhaustive-empty-space assertion."""
    configuration_key: str
    sectors: tuple[SectorCatalog, ...]
    physical_nodes_examined: int


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


def _configuration_key(templates: dict, archetypes: dict) -> str:
    # Weighted-choice iteration order is part of today's generator semantics.
    # Encode it explicitly, rather than confusing it with arbitrary map order.
    ordered_weights = {
        "regions": {k: list(v.get("archetype_weights", {}).items()) for k, v in templates.items()},
        "kinds": {k: list(v.get("kind_weights", {}).items()) for k, v in archetypes.items()},
        "hubs": {k: list(v.get("playable_hub_kind_weights", {}).items()) for k, v in archetypes.items()},
    }
    mapping = {name: getattr(Balance, name) for name in (
        "GALAXY_OP_TO_PHYSICAL_SCALE", "GALAXY_OP_ORIGIN_PHYSICAL_X_LY",
        "GALAXY_OP_ORIGIN_PHYSICAL_Y_LY", "GALAXY_OP_ORIGIN_PHYSICAL_Z_LY",
        "GALAXY_PHYSICAL_CENTER_X_LY", "GALAXY_PHYSICAL_CENTER_Y_LY",
        "GALAXY_PHYSICAL_CENTER_Z_LY", "GALAXY_PHYSICAL_BULGE_RADIUS_LY",
        "GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY",
    )}
    return _digest(("legacy_site_sample_v1", SECTOR_SIZE_LY, templates, archetypes,
                    ordered_weights, mapping))


def catalog_sector(state: GameState, sector_id: str) -> SectorCatalog:
    return catalog_sectors(state,(sector_id,)).sectors[0]


def catalog_sectors(state: GameState, sector_ids: Sequence[str], *, max_sectors=64) -> CatalogResult:
    """Historical generation-cohort evidence; physical reverse lookup is separate.

    VERIFIED comes from the versioned manifest, never from upgrading a legacy
    conditional sample. Discovery, source eligibility and routes remain separate.
    """
    if (type(max_sectors) is not int or max_sectors <= 0 or isinstance(sector_ids,(str,bytes))
        or not isinstance(sector_ids,Sequence)):
        raise ValueError("Invalid bounded historical catalog request")
    if len(sector_ids) > max_sectors:
        raise ValueError("Historical catalog technical budget exceeded")
    for sid in sector_ids:
        _parse_sector_id(sid)
    from retorno.worldgen.generator import universe_definition
    from retorno.worldgen.manifest import _Session,operative_id
    definition = universe_definition(state)
    session = _Session(definition)
    sectors = []
    for sid in sorted(set(sector_ids)):
        cohort = session.sector(sid)
        sites = []
        for site in cohort.sites:
            nid = operative_id(definition,site)
            node = state.world.space.nodes.get(nid)
            valid = node is None or (node.kind == site.kind and
                (node.x_ly,node.y_ly,node.z_ly) == site.position_ly)
            status = SiteStatus.INADMISSIBLE if not valid else SiteStatus.PHYSICAL if node else SiteStatus.VERIFIED
            sites.append(SiteRecord(site.identity.encoded,status,sid,site.physical_sector_id,
                site.position_ly,site.kind,site.region,cohort.archetype,
                int(json.loads(site.identity.local_id)[1]) if site.identity.namespace=='procedural' else None,
                nid if node else None,('historical_manifest_v1','no_materialization_permission')))
        recorded = state.world.sector_states.get(sid)
        sectors.append(SectorCatalog(sid,cohort.template_region,cohort.archetype,
            recorded.archetype if recorded else None,sid in state.world.generated_sectors,tuple(sites),
            ('existence_is_not_recovery_eligibility','narrative_protection_not_assessed',
             'no_routes_or_information_sources_assessed','generation_inventory_not_physical_inventory')))
    return CatalogResult(definition.scope,tuple(sectors),0)
