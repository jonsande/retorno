from __future__ import annotations

import hashlib
import random

from retorno.config.balance import Balance
from retorno.core.gamestate import GameState
from retorno.model.world import SECTOR_SIZE_LY, SectorGenState, SpaceNode, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_modules, load_worldgen_archetypes, load_worldgen_templates, load_locations

_PLAYABLE_HUB_KINDS = {"relay", "station", "waystation"}
_EARLY_PROGRESS_ARCHETYPES = {"relay_corridor", "isolated_station"}


def _hash64(seed: int, text: str) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode("utf-8"))
    h.update(text.encode("utf-8"))
    return int.from_bytes(h.digest(), "big", signed=False)


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str | None:
    items = [(k, max(0.0, float(v))) for k, v in weights.items() if max(0.0, float(v)) > 0.0]
    if not items:
        return None
    total = sum(weight for _, weight in items)
    if total <= 0.0:
        return None
    roll = rng.random() * total
    upto = 0.0
    for key, weight in items:
        upto += weight
        if roll <= upto:
            return key
    return items[-1][0]


def _parse_sector_id(sector_id: str) -> tuple[int, int, int]:
    if not isinstance(sector_id, str) or not sector_id.startswith("S"):
        raise ValueError(f"Invalid sector id: {sector_id!r}")

    parts = sector_id[1:].split("_")
    if len(parts) != 3:
        raise ValueError(f"Invalid sector id: {sector_id!r}")

    coordinates: list[int] = []
    for part in parts:
        try:
            coordinate = int(part)
        except ValueError:
            raise ValueError(f"Invalid sector id: {sector_id!r}") from None
        if part != f"{coordinate:+04d}":
            raise ValueError(f"Invalid sector id: {sector_id!r}")
        coordinates.append(coordinate)

    return coordinates[0], coordinates[1], coordinates[2]


def _neighbor_sector_ids_2d(sector_id: str, radius: int = 1, include_self: bool = True) -> list[str]:
    sx, sy, sz = _parse_sector_id(sector_id)
    out: list[str] = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if not include_self and dx == 0 and dy == 0:
                continue
            out.append(f"S{sx+dx:+04d}_{sy+dy:+04d}_{sz:+04d}")
    return out


def _sector_bounds(sector_id: str) -> tuple[float, float, float]:
    sx_i, sy_i, sz_i = _parse_sector_id(sector_id)
    return (
        sx_i * SECTOR_SIZE_LY,
        sy_i * SECTOR_SIZE_LY,
        sz_i * SECTOR_SIZE_LY,
    )


def _sector_center(sector_id: str) -> tuple[float, float, float]:
    x0, y0, z0 = _sector_bounds(sector_id)
    return (
        x0 + SECTOR_SIZE_LY / 2.0,
        y0 + SECTOR_SIZE_LY / 2.0,
        z0 + SECTOR_SIZE_LY / 2.0,
    )


def _sample_sector_node(
    seed: int, sector_id: str, archetype: str, index: int, kind: str, z_sigma: float,
) -> tuple[tuple[float, float, float], random.Random]:
    """Canonical slot sample and its local RNG, continued by id allocation.

    Sampling alone establishes no slot existence or insertion permission.
    Keep the draw order identical for catalog inspection and materialization.
    """
    rng = random.Random(_hash64(seed, f"sector_node:{sector_id}:{archetype}:{index}:{kind}"))
    x0, y0, z0 = _sector_bounds(sector_id)
    position = (x0 + rng.random() * SECTOR_SIZE_LY,
                y0 + rng.random() * SECTOR_SIZE_LY,
                rng.gauss(z0 + SECTOR_SIZE_LY / 2.0, z_sigma))
    return position, rng


def _roll_recoverable_drones_for_node(seed: int, node_id: str, node_kind: str) -> int:
    cfg = Balance.SALVAGE_DRONES_BY_KIND.get(node_kind or "", {"prob": 0.0, "min": 0, "max": 0})
    min_count = int(cfg.get("min", 0) or 0)
    max_count = int(cfg.get("max", 0) or 0)
    if max_count < min_count:
        max_count = min_count
    if max_count <= 0:
        return 0
    prob = float(cfg.get("prob", 0.0) or 0.0)
    prob = max(0.0, min(1.0, prob))
    node_rng = random.Random(_hash64(seed, f"salvage_drones:{node_id}"))
    if node_rng.random() > prob:
        return 0
    return node_rng.randint(max(0, min_count), max(0, max_count))


def _procedural_radiation_base_for_region(region: str) -> float:
    base = max(0.0, float(Balance.PROCEDURAL_RAD_BASE))
    mult = float(Balance.PROCEDURAL_RAD_REGION_MULT.get(region or "", 1.0))
    return max(0.0, base * max(0.0, mult))


def procedural_radiation_for_node(seed: int, node_id: str, node_kind: str, region: str) -> float:
    rng = random.Random(_hash64(seed, f"proc_rad:{node_id}:{node_kind}:{region}"))
    region_base = _procedural_radiation_base_for_region(region)
    kind_mult = float(Balance.PROCEDURAL_RAD_KIND_MULT.get(node_kind or "", 1.0))
    var_min = float(Balance.PROCEDURAL_RAD_VARIATION_MIN)
    var_max = float(Balance.PROCEDURAL_RAD_VARIATION_MAX)
    if var_max < var_min:
        var_min, var_max = var_max, var_min
    variation = rng.uniform(var_min, var_max)
    spike_mult = 1.0
    spike_p = max(0.0, min(1.0, float(Balance.PROCEDURAL_RAD_SPIKE_CHANCE)))
    if rng.random() < spike_p:
        spike_min = float(Balance.PROCEDURAL_RAD_SPIKE_MULT_MIN)
        spike_max = float(Balance.PROCEDURAL_RAD_SPIKE_MULT_MAX)
        if spike_max < spike_min:
            spike_min, spike_max = spike_max, spike_min
        spike_mult = rng.uniform(spike_min, spike_max)
    value = region_base * max(0.0, kind_mult) * max(0.0, variation) * max(0.0, spike_mult)
    return max(float(Balance.PROCEDURAL_RAD_MIN), value)


def _radiation_for_region(region: str) -> float:
    return _procedural_radiation_base_for_region(region)


def _sector_nodes(state: GameState, sector_id: str) -> list[SpaceNode]:
    return [
        node
        for node in state.world.space.nodes.values()
        if sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly) == sector_id
    ]


def _pair_key(left: str, right: str) -> str:
    a, b = sorted([left, right])
    return f"{a}|{b}"


def _link_with_cap(left: SpaceNode, right: SpaceNode) -> bool:
    dx = left.x_ly - right.x_ly
    dy = left.y_ly - right.y_ly
    dz = left.z_ly - right.z_ly
    dist = (dx * dx + dy * dy + dz * dz) ** 0.5
    if dist > float(Balance.MAX_ROUTE_HOP_LY):
        return False
    before = len(left.links) + len(right.links)
    left.links.add(right.node_id)
    right.links.add(left.node_id)
    return (len(left.links) + len(right.links)) > before


def _sector_state(state: GameState, sector_id: str) -> SectorGenState:
    return state.world.sector_states.setdefault(
        sector_id,
        SectorGenState(sector_id=sector_id),
    )


def sync_sector_state_for_node(state: GameState, node_id: str) -> None:
    node = state.world.space.nodes.get(node_id)
    if not node:
        return
    sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
    if sector_id not in state.world.generated_sectors and sector_id not in state.world.sector_states:
        return
    sector_state = _sector_state(state, sector_id)
    if node_id not in sector_state.node_ids:
        sector_state.node_ids.append(node_id)
        sector_state.node_ids.sort()
    if node.is_hub and sector_state.playable_hub_node_id is None:
        sector_state.playable_hub_node_id = node_id
    if node.is_topology_hub and sector_state.topology_hub_node_id is None:
        sector_state.topology_hub_node_id = node_id
    if not sector_state.region:
        sector_state.region = node.region or region_for_pos(node.x_ly, node.y_ly, node.z_ly)


def _select_archetype(
    state: GameState,
    sector_id: str,
    sector_region: str,
    templates: dict[str, dict],
    overrides: dict[str, str] | None = None,
) -> str:
    if overrides and sector_id in overrides:
        return overrides[sector_id]
    template = templates.get(sector_region) or templates.get("disk") or {}
    archetype_weights = template.get("archetype_weights", {}) or {}
    rng = random.Random(_hash64(state.meta.rng_seed, f"sector_archetype:{sector_id}:{sector_region}"))
    choice = _weighted_choice(rng, archetype_weights)
    if choice:
        return choice
    if archetype_weights:
        return sorted(archetype_weights.keys())[0]
    return "empty"


def _choose_playable_hub_kind(
    state: GameState,
    sector_id: str,
    archetype: str,
    archetype_cfg: dict,
    counts: dict[str, int],
    force_playable_hub: bool,
) -> str | None:
    hub_weights = dict(archetype_cfg.get("playable_hub_kind_weights", {}) or {})
    if not hub_weights:
        return None
    if not force_playable_hub:
        prob = max(0.0, min(1.0, float(archetype_cfg.get("playable_hub_prob", 0.0) or 0.0)))
        rng = random.Random(_hash64(state.meta.rng_seed, f"sector_hub_roll:{sector_id}:{archetype}"))
        if rng.random() > prob:
            return None
    caps = archetype_cfg.get("kind_caps", {}) or {}
    forbidden = {str(item) for item in (archetype_cfg.get("forbidden_kinds", []) or [])}
    filtered: dict[str, float] = {}
    for kind, weight in hub_weights.items():
        if kind not in _PLAYABLE_HUB_KINDS:
            continue
        if kind in forbidden:
            continue
        cap = caps.get(kind)
        if cap is not None and int(cap) <= counts.get(kind, 0):
            continue
        filtered[kind] = float(weight)
    if not filtered:
        return None
    rng = random.Random(_hash64(state.meta.rng_seed, f"sector_hub_kind:{sector_id}:{archetype}"))
    return _weighted_choice(rng, filtered)


def _plan_sector_kinds(
    state: GameState,
    sector_id: str,
    archetype: str,
    sector_region: str,
    region_template: dict,
    archetype_cfg: dict,
    *,
    force_playable_hub: bool = False,
) -> tuple[list[str], str | None]:
    existing_nodes = _sector_nodes(state, sector_id)
    counts: dict[str, int] = {}
    existing_playable_hub = None
    for node in existing_nodes:
        counts[node.kind] = counts.get(node.kind, 0) + 1
        if node.is_hub and existing_playable_hub is None:
            existing_playable_hub = node.node_id

    count_rng = random.Random(_hash64(state.meta.rng_seed, f"sector_node_count:{sector_id}:{archetype}:{sector_region}"))
    min_count = int(archetype_cfg.get("node_count_min", 0) or 0)
    max_count = int(archetype_cfg.get("node_count_max", 0) or 0)
    if max_count < min_count:
        max_count = min_count
    target_total = count_rng.randint(max(0, min_count), max(0, max_count))
    remaining_slots = max(0, target_total - len(existing_nodes))

    planned: list[str] = []
    playable_hub_kind = None
    if existing_playable_hub is None and remaining_slots > 0:
        playable_hub_kind = _choose_playable_hub_kind(
            state,
            sector_id,
            archetype,
            archetype_cfg,
            counts,
            force_playable_hub,
        )
        if playable_hub_kind:
            planned.append(playable_hub_kind)
            counts[playable_hub_kind] = counts.get(playable_hub_kind, 0) + 1
            remaining_slots -= 1

    kind_weights = dict(archetype_cfg.get("kind_weights", {}) or {})
    caps = archetype_cfg.get("kind_caps", {}) or {}
    forbidden = {str(item) for item in (archetype_cfg.get("forbidden_kinds", []) or [])}
    for _ in range(remaining_slots):
        candidates: dict[str, float] = {}
        for kind, weight in kind_weights.items():
            if kind in forbidden:
                continue
            cap = caps.get(kind)
            if cap is not None and int(cap) <= counts.get(kind, 0):
                continue
            candidates[kind] = float(weight)
        rng = random.Random(_hash64(state.meta.rng_seed, f"sector_kind_pick:{sector_id}:{archetype}:{len(planned)}"))
        choice = _weighted_choice(rng, candidates)
        if not choice:
            break
        planned.append(choice)
        counts[choice] = counts.get(choice, 0) + 1
    return planned, playable_hub_kind


def _pick_modules(
    rng: random.Random,
    module_ids: list[str],
    min_count: int,
    max_count: int,
    pool: str | list[str] | None = None,
) -> list[str]:
    if not module_ids or max_count <= 0:
        return []
    count = rng.randint(min_count, max_count)
    modules = load_modules()
    # Regional pools are category filters; keep candidates in catalog order.
    categories = pool if isinstance(pool, list) else [pool]
    candidates = [
        mid
        for mid in module_ids
        if mid in modules and (pool is None or modules[mid].get("pool", "common") in categories)
    ]
    if not candidates:
        return []
    return [rng.choice(candidates) for _ in range(count)]


def _apply_salvage_profile(
    state: GameState,
    node: SpaceNode,
    salvage_cfg: dict,
    module_ids: list[str],
) -> None:
    if node.kind not in {"station", "derelict", "ship", "relay", "waystation"}:
        return
    seed = _hash64(state.meta.rng_seed, f"sector_salvage:{node.node_id}")
    rng = random.Random(seed)
    scrap_min = int(salvage_cfg.get("scrap_min", 0) or 0)
    scrap_max = int(salvage_cfg.get("scrap_max", 0) or 0)
    if scrap_max > 0:
        node.salvage_scrap_available = rng.randint(max(0, scrap_min), max(0, scrap_max))
    node.salvage_modules_available = _pick_modules(
        rng,
        module_ids,
        int(salvage_cfg.get("modules_min", 0) or 0),
        int(salvage_cfg.get("modules_max", 0) or 0),
        salvage_cfg.get("modules_pool"),
    )
    node.recoverable_drones_count = _roll_recoverable_drones_for_node(
        state.meta.rng_seed,
        node.node_id,
        node.kind,
    )


def _has_early_progression_neighbor(
    state: GameState,
    cluster_sector_ids: list[str],
    templates: dict[str, dict],
    overrides: dict[str, str],
) -> bool:
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    for sector_id in cluster_sector_ids:
        if sector_id == origin_sector:
            continue
        region = region_for_pos(*_sector_center(sector_id))
        archetype = _select_archetype(
            state=state,
            sector_id=sector_id,
            sector_region=region,
            templates=templates,
            overrides=overrides,
        )
        if archetype in _EARLY_PROGRESS_ARCHETYPES:
            return True
    return False


def _maybe_apply_sparse_guardrail(
    state: GameState,
    cluster_sector_ids: list[str],
    templates: dict[str, dict],
) -> tuple[dict[str, str], set[str]]:
    overrides: dict[str, str] = {}
    force_playable_hub: set[str] = set()
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    if state.world.sparse_guardrail_done or origin_sector not in cluster_sector_ids:
        return overrides, force_playable_hub

    origin_region = region_for_pos(*_sector_center(origin_sector))
    origin_archetype = _select_archetype(state, origin_sector, origin_region, templates)
    if origin_archetype not in {"relay_corridor", "isolated_station", "ruin_field"}:
        overrides[origin_sector] = "relay_corridor"

    # Keep the world sparse while ensuring the very first neighborhood is not a
    # trivial hard-stop. This is a one-time early-game guardrail, not a general
    # promise that every branch can always progress forward.
    if not _has_early_progression_neighbor(state, cluster_sector_ids, templates, overrides):
        neighbors = [sector_id for sector_id in cluster_sector_ids if sector_id != origin_sector]
        if neighbors:
            neighbors = sorted(neighbors)
            rng = random.Random(_hash64(state.meta.rng_seed, "sparse_guardrail_neighbor"))
            promoted_sector = neighbors[rng.randrange(len(neighbors))]
            promoted_archetype = "relay_corridor" if rng.random() < 0.5 else "isolated_station"
            overrides[promoted_sector] = promoted_archetype
            force_playable_hub.add(promoted_sector)

    state.world.sparse_guardrail_done = True
    return overrides, force_playable_hub


_GREEK_SUFFIXES = [
    "ALFA",
    "BETA",
    "GAMMA",
    "DELTA",
    "EPSILON",
    "ZETA",
    "ETA",
    "THETA",
    "IOTA",
    "KAPPA",
    "LAMBDA",
    "MU",
    "NU",
    "XI",
    "OMICRON",
    "PI",
    "RHO",
    "SIGMA",
    "TAU",
    "UPSILON",
    "PHI",
    "CHI",
    "PSI",
    "OMEGA",
]


def _generate_node_id(state: GameState, kind: str, rng: random.Random) -> str:
    prefix = "WRECK" if kind == "ship" else (kind or "node").upper()
    while True:
        base = f"{prefix}_{rng.getrandbits(24):06X}"
        if base not in state.world.space.nodes:
            return base
        for suffix in _GREEK_SUFFIXES:
            candidate = f"{base}_{suffix}"
            if candidate not in state.world.space.nodes:
                return candidate


def _name_from_node_id(node_id: str, kind: str) -> str:
    parts = node_id.split("_")
    if not parts:
        return _generate_name(random.Random(0), kind)
    prefix = parts[0]
    if prefix == "WRECK":
        name_prefix = "Wreck"
    elif prefix == "DERELICT":
        name_prefix = "Derelict"
    elif prefix == "STATION":
        name_prefix = "Station"
    elif prefix == "RELAY":
        name_prefix = "Relay"
    elif prefix == "WAYSTATION":
        name_prefix = "Waystation"
    elif prefix == "NODE":
        name_prefix = "Node"
    else:
        name_prefix = prefix.title()
    suffix = " ".join(parts[1:]) if len(parts) > 1 else ""
    return f"{name_prefix} {suffix}".strip()


def _generate_name(rng: random.Random, kind: str) -> str:
    if kind == "relay":
        return f"Relay-{rng.randint(1, 99)}"
    if kind == "station":
        return f"Station-{rng.randint(1, 99)}"
    if kind == "waystation":
        return f"Waystation-{rng.randint(1, 99)}"
    if kind == "derelict":
        return f"Derelict-{rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}-{rng.randint(1, 9)}"
    if kind == "ship":
        return f"Wreck-{rng.randint(1, 99)}"
    return f"Node-{rng.randint(1, 999)}"


def universe_definition(state: GameState):
    """Read-only resolution; a new game's rules are pinned before first use."""
    from retorno.worldgen.manifest import ALGORITHM_VERSION, define_manifest, physical_rules_key
    if state.world.universe_version != ALGORITHM_VERSION:
        raise ValueError("Incompatible historical universe version")
    definition = state.world.manifest_definition
    snapshot = state.world.narrative_snapshot
    if snapshot and snapshot.get("declarations"):
        if definition is None or definition.narrative_key != snapshot["catalog_key"]:
            raise ValueError("Historical narrative definition missing or changed")
    if definition is not None:
        if definition.seed != state.meta.rng_seed or definition.algorithm_version != ALGORITHM_VERSION:
            raise ValueError("Historical universe seed/version changed")
        if (definition.rules_key != physical_rules_key()
            or definition.rules_key != state.world.universe_rules_key):
            raise ValueError("Historical universe configuration changed")
        return definition
    rules = physical_rules_key()
    if state.world.universe_rules_key and state.world.universe_rules_key != rules:
        raise ValueError("Historical universe configuration changed before materialization")
    return define_manifest(state.meta.rng_seed)


def pin_universe(state: GameState):
    definition = universe_definition(state)
    state.world.manifest_definition = definition
    state.world.universe_rules_key = definition.rules_key
    return definition


def _ensure_sector_generated_core(state, physical_sector_ids):
    """Prepare all nodes/edges before a bounded, idempotent in-memory commit."""
    from dataclasses import replace
    from retorno.worldgen.manifest import new_session, _physical_inventory, _query_session, operative_id
    definition = universe_definition(state)
    import math
    if any(not all(math.isfinite(v) for v in (n.x_ly,n.y_ly,n.z_ly)) for n in state.world.space.nodes.values()):
        raise ValueError("Nonfinite materialized coordinate")
    targets = tuple(sorted(set(physical_sector_ids)))
    if not targets or all(sid in state.world.generated_sectors and
        state.world.sector_states.get(sid) and state.world.sector_states[sid].physical_inventory_complete
        for sid in targets):
        return
    session = new_session(definition)
    inventory = _physical_inventory(session, targets, max_sectors=576)
    sources = tuple(sorted({site.generation_sector_id for site in inventory.sites}))
    topology = _query_session(session, sources)
    nodes = state.world.space.nodes
    staged = {}
    historical = {}
    module_ids = list(load_modules())
    for site in inventory.sites:
        nid = operative_id(definition, site)
        historical[nid] = site
        if nid == "UNKNOWN" and nid not in nodes:
            continue  # The disposable bootstrap marker is never resurrected.
        if nid in nodes:
            node = nodes[nid]
            if (node.kind != site.kind or (node.x_ly,node.y_ly,node.z_ly) != site.position_ly
                or (node.historical_key is not None and node.historical_key != site.identity.encoded)):
                raise ValueError("Historical id occupied by a different physical node")
            continue
        node = SpaceNode(nid, _name_from_node_id(site.legacy_id_hint,site.kind), site.kind,
                         region=site.region, x_ly=site.position_ly[0], y_ly=site.position_ly[1], z_ly=site.position_ly[2],
                         is_hub=site.is_hub, is_topology_hub=site.is_topology_hub,
                         historical_key=site.identity.encoded, generation_sector_id=site.generation_sector_id)
        if site.identity.namespace == "authored":
            # Normally present from bootstrap. A physically declared authored
            # site remains distinct from prose/content references.
            from retorno.worldgen.narrative import records_for
            cfg = next(loc for loc in records_for(state, "locations", load_locations)
                       if loc.get('node',{}).get('node_id') == nid)
            raw = cfg['node']
            node.name = raw.get('name',nid)
            node.radiation_rad_per_s = float(raw.get('radiation_rad_per_s',0))
            node.radiation_base = float(raw.get('radiation_base',0))
        else:
            # Reuse the existing profiles/functions with a full historical seed
            # key, independent of operative ids and registry collisions.
            resource_node = replace(node,node_id=site.identity.encoded)
            resource_node.radiation_rad_per_s = procedural_radiation_for_node(
                definition.seed, resource_node.node_id,site.kind,site.region)
            resource_node.radiation_base = _radiation_for_region(site.region)
            template = session.templates[session.sector(site.generation_sector_id).template_region]
            _apply_salvage_profile(state,resource_node,template.get('salvage',{}),module_ids)
            node.radiation_rad_per_s = resource_node.radiation_rad_per_s
            node.radiation_base = resource_node.radiation_base
            node.salvage_scrap_available = resource_node.salvage_scrap_available
            node.salvage_modules_available = resource_node.salvage_modules_available
            node.recoverable_drones_count = resource_node.recoverable_drones_count
        staged[nid] = node
    if len(staged) > 2048:
        raise ValueError("Materialization node budget exhausted; no world changes applied")
    available = set(nodes) | set(staged)
    site_ids = {site.identity: operative_id(definition,site)
                for sector in topology.sectors for site in sector.sites}
    site_ids.update((site.identity,operative_id(definition,site)) for site in topology.boundary_sites)
    edges = [(site_ids[e.left],site_ids[e.right]) for e in topology.edges
             if site_ids[e.left] in available and site_ids[e.right] in available]

    # All fallible sampling/collision/budget checks precede this commit.
    nodes.update(staged)
    state.world.manifest_definition = definition
    state.world.universe_rules_key = definition.rules_key
    for nid,site in historical.items():
        if nid in nodes:
            node = nodes[nid]
            node.historical_key = site.identity.encoded
            node.generation_sector_id = site.generation_sector_id
            node.is_hub, node.is_topology_hub = site.is_hub, site.is_topology_hub
    for a,b in edges:
        nodes[a].links.add(b)
        nodes[b].links.add(a)
    state.world.generated_sectors.update(targets)
    state.world.sparse_guardrail_done = True
    affected = set(targets)
    affected.update(site.generation_sector_id for site in inventory.sites
                    if site.generation_sector_id in state.world.sector_states)
    for a,b in edges:
        for nid in (a,b):
            if nodes[nid].generation_sector_id in state.world.sector_states:
                affected.add(nodes[nid].generation_sector_id)
    physical, generation = {}, {}
    for nid,node in nodes.items():
        physical.setdefault(sector_id_for_pos(node.x_ly,node.y_ly,node.z_ly),[]).append(nid)
        if node.historical_key:
            generation.setdefault(node.generation_sector_id,[]).append(nid)
    for sid in sorted(affected):
        info = _sector_state(state,sid)
        cohort = session.sector(sid)
        info.region, info.archetype = cohort.template_region, cohort.archetype
        info.node_ids = sorted(physical.get(sid,()))
        info.generation_node_ids = sorted(generation.get(sid,()))
        hub = next((site for site in cohort.sites if site.is_topology_hub),None)
        hub_id = operative_id(definition,hub) if hub else None
        info.topology_hub_node_id = hub_id if hub_id in nodes else None
        info.playable_hub_node_id = next((nid for nid in info.generation_node_ids if nodes[nid].is_hub),None)
        internal = {tuple(sorted((nid,d))) for nid in info.generation_node_ids for d in nodes[nid].links
                    if d in nodes and nodes[d].historical_key and nodes[d].generation_sector_id == sid}
        info.internal_link_count = len(internal)
        info.intersector_link_count = sum(d in nodes and bool(nodes[d].historical_key) and
            nodes[d].generation_sector_id != sid for d in nodes[hub_id].links) if hub_id in nodes else 0
        info.internal_links_built = True
        info.physical_inventory_complete = sid in state.world.generated_sectors


def _ensure_sector_cluster_generated(state: GameState, sector_ids: list[str]) -> None:
    if len(sector_ids) > 64:
        raise ValueError("Sector request exceeds technical materialization budget")
    for sid in sector_ids:
        _parse_sector_id(sid)
    targets = {neighbor for sid in sector_ids for neighbor in _neighbor_sector_ids_2d(sid)}
    _ensure_sector_generated_core(state,targets)


def ensure_sector_generated(state: GameState, sector_id: str) -> None:
    _parse_sector_id(sector_id)
    _ensure_sector_cluster_generated(state,[sector_id])


def ensure_historical_node(state: GameState, node_id: str) -> bool:
    """Compatibility resolution for exact manifest ids; never publishes intel."""
    from retorno.worldgen.manifest import resolve_operative_id
    site = resolve_operative_id(universe_definition(state),node_id)
    if site is None:
        return False
    ensure_sector_generated(state,site.physical_sector_id)
    return node_id in state.world.space.nodes


def validate_universe_state(state):
    """Read-only save validation; consumed resources and knowledge are untouched."""
    import math
    from retorno.worldgen.manifest import new_session, operative_id, _physical_inventory
    definition = universe_definition(state)
    if state.world.manifest_definition is None:
        raise ValueError("Historical universe is not pinned in the save")
    session = new_session(definition)
    nodes = state.world.space.nodes
    for authored in definition.authored:
        node = nodes.get(authored.raw_id)
        if node and (node.kind != authored.kind or
            (node.x_ly,node.y_ly,node.z_ly) != authored.position_ly):
            raise ValueError("Authored physical definition changed")
    for nid,node in state.world.space.nodes.items():
        if not all(math.isfinite(v) for v in (node.x_ly,node.y_ly,node.z_ly)):
            raise ValueError("Nonfinite physical coordinate")
        if not node.historical_key:
            if ":WG1_" in nid or ":WG1C" in nid:
                raise ValueError("Historical operative id lost its provenance")
            continue
        if len(session.sectors) > 16000:
            session = new_session(definition)
        if not node.generation_sector_id:
            raise ValueError("Historical node has no generation provenance")
        cohort = session.sector(node.generation_sector_id)
        site = next((s for s in cohort.sites if s.identity.encoded == node.historical_key),None)
        if (not site or operative_id(definition,site) != nid or site.kind != node.kind
            or site.position_ly != (node.x_ly,node.y_ly,node.z_ly)
            or (node.is_hub,node.is_topology_hub,node.region) !=
               (site.is_hub,site.is_topology_hub,site.region)):
            raise ValueError("Materialized node contradicts the historical manifest")
        for dest in node.links:
            other = state.world.space.nodes.get(dest)
            if other and other.historical_key:
                if nid not in other.links or not is_historical_edge(session,site,other):
                    raise ValueError("Physical edge contradicts the historical manifest")
        expected = [e for e in cohort.internal_edges if site.identity in (e.left,e.right)]
        if site.is_topology_hub:
            for sid in session.ranked(site.generation_sector_id):
                hub = session.hub(sid)
                dest = operative_id(definition,hub)
                if dest in nodes and dest not in node.links:
                    raise ValueError("Missing materialized historical edge")
        for edge in expected:
            other_identity = edge.right if edge.left == site.identity else edge.left
            other_site = next(s for s in cohort.sites if s.identity == other_identity)
            dest = operative_id(definition,other_site)
            if dest in nodes and dest not in node.links:
                raise ValueError("Missing materialized historical internal edge")
    # A complete physical-sector marker must actually contain its inventory.
    ids = sorted(sid for sid in state.world.generated_sectors
                 if state.world.sector_states.get(sid) and
                 state.world.sector_states[sid].physical_inventory_complete)
    for offset in range(0,len(ids),64):
        inventory = _physical_inventory(new_session(definition),ids[offset:offset+64])
        for site in inventory.sites:
            nid = operative_id(definition,site)
            if nid == "UNKNOWN" and nid not in nodes:
                continue
            if nid not in nodes or nodes[nid].historical_key != site.identity.encoded:
                raise ValueError("Complete physical inventory is missing a historical site")


def is_historical_edge(session,site,other):
    if other.generation_sector_id == site.generation_sector_id:
        return any(site.identity in (e.left,e.right) and other.historical_key in (e.left.encoded,e.right.encoded)
                   for e in session.sector(site.generation_sector_id).internal_edges)
    if not site.is_topology_hub or not other.is_topology_hub:
        return False
    cohort = session.sector(other.generation_sector_id)
    hub = next((s for s in cohort.sites if s.is_topology_hub),None)
    return bool(hub and hub.identity.encoded == other.historical_key and
                other.generation_sector_id in session.ranked(site.generation_sector_id))
