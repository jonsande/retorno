"""Read-only preexistence evidence, independent of recovery or ship capability.

The legacy generator cannot certify unmaterialized sites independently of
materialization order. Its current slot forecast is therefore CONDITIONAL,
even when the canonical sample is reproducible. No result permits insertion,
publishes knowledge, or establishes a route/information source.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from types import SimpleNamespace

from retorno.config.balance import Balance
from retorno.core.gamestate import GameState
from retorno.model.world import SECTOR_SIZE_LY, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_worldgen_archetypes, load_worldgen_templates
from retorno.worldgen.generator import (
    _parse_sector_id, _plan_sector_kinds, _sample_sector_node, _sector_center,
    _select_archetype,
)


class SiteStatus(str, Enum):
    PHYSICAL = "physical"
    VERIFIED = "verified_procedural"  # Reserved: never emitted by this version.
    CONDITIONAL = "conditional"
    INADMISSIBLE = "inadmissible"


@dataclass(frozen=True, slots=True)
class SiteRecord:
    """Internal evidence, not player intel or recovery eligibility.

    A procedural key identifies a conditional sample, NOT a reserved location.
    node_id is supplied only for an already physical node. Its original
    procedural address cannot be reconstructed reliably from legacy saves.
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
    """Inspect one generation sector without expanding its neighborhood."""
    return catalog_sectors(state, (sector_id,)).sectors[0]


def catalog_sectors(
    state: GameState, sector_ids: Sequence[str], *, max_sectors: int = 64,
) -> CatalogResult:
    """Inspect an explicit bounded family on a coherent, read-only snapshot.

    Exceeding the technical request bound raises ValueError before inspection;
    it never means that no sites exist. Input order/duplicates do not affect
    results. Work is O(physical nodes + requested sectors + returned records),
    apart from sorting. No galaxy walk, generation, topology or global cache.
    """
    if type(max_sectors) is not int or max_sectors <= 0:
        raise ValueError("max_sectors must be a positive integer")
    if isinstance(sector_ids, (str, bytes)) or not isinstance(sector_ids, Sequence):
        raise TypeError("sector_ids must be a bounded sequence of canonical sector ids")
    if len(sector_ids) > max_sectors:
        raise ValueError("sector request exceeds technical bound; split into bounded families")
    for sid in sector_ids:
        _parse_sector_id(sid)
    ordered = sorted(set(sector_ids))
    templates = load_worldgen_templates()
    archetypes = load_worldgen_archetypes()
    configuration = _configuration_key(templates, archetypes)
    members: dict[str, dict] = {sid: {} for sid in ordered}
    occupied = set()
    for nid, node in state.world.space.nodes.items():
        pos = (node.x_ly, node.y_ly, node.z_ly)
        if not all(math.isfinite(v) for v in pos):
            # Nonfinite nodes have no spatial sector; never pretend to place them.
            raise ValueError(f"Physical node has nonfinite coordinates: {nid}")
        occupied.add(pos)
        sid = sector_id_for_pos(*pos)
        if sid in members:
            members[sid][nid] = node

    sectors = []
    for sid in ordered:
        region = region_for_pos(*_sector_center(sid))
        archetype = _select_archetype(state, sid, region, templates)
        recorded = state.world.sector_states.get(sid)
        generated = sid in state.world.generated_sectors
        sites = [SiteRecord(
            key="physical:" + _digest((state.meta.rng_seed, nid)),
            status=SiteStatus.PHYSICAL, generation_sector_id=None,
            physical_sector_id=sid, position_ly=(node.x_ly, node.y_ly, node.z_ly),
            kind=node.kind, region=region_for_pos(node.x_ly, node.y_ly, node.z_ly),
            node_id=nid,
        ) for nid, node in sorted(members[sid].items())]
        limitations = ["existence_is_not_recovery_eligibility", "narrative_protection_not_assessed",
                       "no_routes_or_information_sources_assessed", "not_a_complete_spatial_inventory"]
        if generated:
            limitations.append("generated_sector_no_new_slots_forecast")
        else:
            template = templates.get(region) or templates.get("disk")
            cfg = archetypes.get(archetype)
            if template is None or cfg is None:
                limitations.append("missing_canonical_configuration")
            else:
                # Same indexed read view as the existing pure chain planner;
                # _plan_sector_kinds only needs meta and this sector's nodes.
                view = SimpleNamespace(meta=state.meta, world=SimpleNamespace(
                    space=SimpleNamespace(nodes=members[sid])))
                kinds, _ = _plan_sector_kinds(view, sid, archetype, region, template, cfg)
                conditions = ("current_occupancy_not_reserved", "future_z_inflow_unresolved",
                              "node_id_allocation_unresolved", "no_materialization_permission")
                if not state.world.sparse_guardrail_done:
                    conditions += ("initial_guardrail_unresolved",)
                if sid == sector_id_for_pos(0.0, 0.0, 0.0) and "ECHO_7" not in state.world.space.nodes:
                    conditions += ("fixed_origin_hub_not_applied",)
                for index, kind in enumerate(kinds):
                    pos, _ = _sample_sector_node(state.meta.rng_seed, sid, archetype, index,
                                                kind, float(template.get("z_sigma", 0.3) or 0.3))
                    physical_sid = sector_id_for_pos(*pos)
                    reasons = conditions
                    if physical_sid != sid:
                        reasons += ("sample_outside_generation_sector",)
                    node_region = region_for_pos(*pos)
                    if node_region != region:
                        reasons += ("sample_region_differs_from_template_region",)
                    status = SiteStatus.CONDITIONAL
                    if pos in occupied:
                        status = SiteStatus.INADMISSIBLE
                        reasons += ("sample_position_occupied",)
                    sites.append(SiteRecord(
                        key="procedural:" + _digest((configuration, state.meta.rng_seed,
                                                     sid, archetype, index, kind)),
                        status=status, generation_sector_id=sid, physical_sector_id=physical_sid,
                        position_ly=pos, kind=kind, region=node_region,
                        archetype=archetype, slot_index=index, conditions=reasons,
                    ))
                if not kinds:
                    limitations.append("no_remaining_slots_in_current_snapshot")
                limitations.append("legacy_worldgen_cannot_verify_latent_existence")
        sectors.append(SectorCatalog(sid, region, archetype, recorded.archetype if recorded else None,
                                     generated, tuple(sites), tuple(limitations)))
    return CatalogResult(configuration, tuple(sectors), len(state.world.space.nodes))
