from __future__ import annotations

import hashlib
import random

from retorno.config.balance import Balance
from retorno.core.gamestate import GameState
from retorno.model.world import SECTOR_SIZE_LY, SectorGenState, SpaceNode, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_modules, load_worldgen_archetypes, load_worldgen_templates

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
    try:
        sx, sy, sz = sector_id[1:].split("_")
        return int(sx), int(sy), int(sz)
    except Exception:
        return 0, 0, 0


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
    pool_map: dict[str, list[str]] = {"common": [], "rare": [], "tech": []}
    for mid in module_ids:
        tag = modules.get(mid, {}).get("pool", "common")
        pool_map.setdefault(tag, []).append(mid)
    if isinstance(pool, list) and pool:
        candidates = [m for m in pool if m in module_ids]
    elif isinstance(pool, str) and pool in pool_map:
        candidates = pool_map[pool]
    else:
        candidates = module_ids
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


def _ensure_fixed_origin_hub(state: GameState, sector_id: str) -> None:
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    if sector_id != origin_sector or "ECHO_7" in state.world.space.nodes:
        return
    hub_region = region_for_pos(0.0, 0.0, 0.0)
    hub = SpaceNode(
        node_id="ECHO_7",
        name="ECHO-7 Relay Station",
        kind="station",
        radiation_rad_per_s=procedural_radiation_for_node(state.meta.rng_seed, "ECHO_7", "station", hub_region),
        radiation_base=_radiation_for_region(hub_region),
        region=hub_region,
        x_ly=0.0,
        y_ly=0.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )
    state.world.space.nodes[hub.node_id] = hub


def _pick_topology_hub(nodes: list[SpaceNode]) -> SpaceNode | None:
    if not nodes:
        return None
    playable = [node for node in nodes if node.is_hub]
    if playable:
        return sorted(playable, key=lambda item: item.node_id)[0]
    return sorted(nodes, key=lambda item: item.node_id)[0]


def _refresh_sector_metadata(state: GameState, sector_id: str) -> None:
    sector_state = _sector_state(state, sector_id)
    nodes = sorted(_sector_nodes(state, sector_id), key=lambda node: node.node_id)
    sector_state.node_ids = [node.node_id for node in nodes]
    if not sector_state.region and nodes:
        sector_state.region = nodes[0].region or region_for_pos(nodes[0].x_ly, nodes[0].y_ly, nodes[0].z_ly)
    sector_state.playable_hub_node_id = next((node.node_id for node in nodes if node.is_hub), None)
    sector_state.topology_hub_node_id = next((node.node_id for node in nodes if node.is_topology_hub), None)


def _build_internal_links_for_sector(state: GameState, sector_id: str, archetype_cfg: dict) -> None:
    sector_state = _sector_state(state, sector_id)
    if sector_state.internal_links_built:
        return
    nodes = sorted(_sector_nodes(state, sector_id), key=lambda node: node.node_id)
    if not nodes:
        sector_state.internal_links_built = True
        sector_state.internal_link_count = 0
        return
    hub = _pick_topology_hub(nodes)
    if not hub:
        sector_state.internal_links_built = True
        sector_state.internal_link_count = 0
        return
    hub.is_topology_hub = True
    if hub.kind in _PLAYABLE_HUB_KINDS:
        hub.is_hub = True
    sector_state.topology_hub_node_id = hub.node_id
    if hub.is_hub:
        sector_state.playable_hub_node_id = hub.node_id

    internal_added = 0
    for node in nodes:
        if node.node_id == hub.node_id:
            continue
        if _link_with_cap(node, hub):
            internal_added += 1

    extra_prob = max(0.0, min(1.0, float(archetype_cfg.get("extra_internal_link_prob", 0.0) or 0.0)))
    extra_rng = random.Random(_hash64(state.meta.rng_seed, f"sector_internal_links:{sector_id}:{sector_state.archetype}"))
    for node in nodes:
        if node.node_id == hub.node_id:
            continue
        if extra_rng.random() > extra_prob:
            continue
        candidates = [item for item in nodes if item.node_id not in {node.node_id, hub.node_id}]
        if not candidates:
            continue
        target = candidates[extra_rng.randrange(len(candidates))]
        if _link_with_cap(node, target):
            internal_added += 1

    sector_state.internal_links_built = True
    sector_state.internal_link_count = internal_added
    _refresh_sector_metadata(state, sector_id)


def _evaluate_intersector_pair(
    state: GameState,
    left_sector_id: str,
    right_sector_id: str,
    archetypes: dict[str, dict],
) -> None:
    # Sparse topology is intentional: most sectors should expose 0-1 exits and
    # local dead ends are valid outcomes. This pass only links already
    # materialized neighbors when both archetype budgets allow it.
    key = _pair_key(left_sector_id, right_sector_id)
    if key in state.world.intersector_link_pairs:
        return
    state.world.intersector_link_pairs.add(key)

    left_state = state.world.sector_states.get(left_sector_id)
    right_state = state.world.sector_states.get(right_sector_id)
    if not left_state or not right_state:
        return
    left_cfg = archetypes.get(left_state.archetype, {})
    right_cfg = archetypes.get(right_state.archetype, {})
    left_max = int(left_cfg.get("intersector_link_max", 0) or 0)
    right_max = int(right_cfg.get("intersector_link_max", 0) or 0)
    if left_state.intersector_link_count >= left_max or right_state.intersector_link_count >= right_max:
        return

    left_hub = state.world.space.nodes.get(left_state.topology_hub_node_id or "")
    right_hub = state.world.space.nodes.get(right_state.topology_hub_node_id or "")
    if not left_hub or not right_hub:
        return

    prob = min(
        max(0.0, min(1.0, float(left_cfg.get("intersector_link_prob", 0.0) or 0.0))),
        max(0.0, min(1.0, float(right_cfg.get("intersector_link_prob", 0.0) or 0.0))),
    )
    if prob <= 0.0:
        return
    rng = random.Random(
        _hash64(
            state.meta.rng_seed,
            f"sector_pair:{key}:{left_state.archetype}:{right_state.archetype}",
        )
    )
    if rng.random() > prob:
        return
    if _link_with_cap(left_hub, right_hub):
        left_state.intersector_link_count += 1
        right_state.intersector_link_count += 1


def _ensure_intersector_links_for_new_sectors(
    state: GameState,
    new_sector_ids: list[str],
    archetypes: dict[str, dict],
) -> None:
    candidate_pairs: set[str] = set()
    for sector_id in new_sector_ids:
        for neighbor_id in _neighbor_sector_ids_2d(sector_id, radius=1, include_self=False):
            if neighbor_id not in state.world.generated_sectors:
                continue
            candidate_pairs.add(_pair_key(sector_id, neighbor_id))

    for key in sorted(candidate_pairs):
        left_sector_id, right_sector_id = key.split("|", 1)
        _evaluate_intersector_pair(state, left_sector_id, right_sector_id, archetypes)


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


def _ensure_sector_generated_core(
    state: GameState,
    sector_id: str,
    templates: dict[str, dict],
    archetypes: dict[str, dict],
    overrides: dict[str, str] | None = None,
    force_playable_hub: set[str] | None = None,
) -> bool:
    if sector_id in state.world.generated_sectors:
        return False

    _ensure_fixed_origin_hub(state, sector_id)
    force_playable_hub = force_playable_hub or set()
    sector_region = region_for_pos(*_sector_center(sector_id))
    region_template = templates.get(sector_region) or templates.get("disk") or {}
    archetype = _select_archetype(state, sector_id, sector_region, templates, overrides)
    archetype_cfg = archetypes.get(archetype) or archetypes.get("empty") or {}
    sector_state = _sector_state(state, sector_id)
    sector_state.region = sector_region
    sector_state.archetype = archetype
    sector_state.internal_link_count = 0
    sector_state.intersector_link_count = 0

    modules = load_modules()
    module_ids = list(modules.keys())
    planned_kinds, playable_hub_kind = _plan_sector_kinds(
        state,
        sector_id,
        archetype,
        sector_region,
        region_template,
        archetype_cfg,
        force_playable_hub=sector_id in force_playable_hub,
    )
    x0, y0, z0 = _sector_bounds(sector_id)
    z_sigma = float(region_template.get("z_sigma", 0.3) or 0.3)
    salvage_cfg = dict(region_template.get("salvage", {}) or {})

    for index, kind in enumerate(planned_kinds):
        rng = random.Random(_hash64(state.meta.rng_seed, f"sector_node:{sector_id}:{archetype}:{index}:{kind}"))
        x = x0 + rng.random() * SECTOR_SIZE_LY
        y = y0 + rng.random() * SECTOR_SIZE_LY
        z = z0 + rng.gauss(0.0, z_sigma)
        node_region = region_for_pos(x, y, z)
        node_id = _generate_node_id(state, kind, rng)
        node = SpaceNode(
            node_id=node_id,
            name=_name_from_node_id(node_id, kind),
            kind=kind,
            radiation_rad_per_s=procedural_radiation_for_node(state.meta.rng_seed, node_id, kind, node_region),
            radiation_base=_radiation_for_region(node_region),
            region=node_region,
            x_ly=x,
            y_ly=y,
            z_ly=z,
            is_hub=kind == playable_hub_kind and kind in _PLAYABLE_HUB_KINDS,
            is_topology_hub=False,
        )
        _apply_salvage_profile(state, node, salvage_cfg, module_ids)
        state.world.space.nodes[node_id] = node

    _refresh_sector_metadata(state, sector_id)
    state.world.generated_sectors.add(sector_id)
    return True


def _ensure_sector_cluster_generated(state: GameState, sector_ids: list[str]) -> None:
    templates = load_worldgen_templates()
    archetypes = load_worldgen_archetypes()
    cluster_ids: set[str] = set()
    for sector_id in sector_ids:
        cluster_ids.update(_neighbor_sector_ids_2d(sector_id, radius=1, include_self=True))
    ordered_cluster = sorted(cluster_ids)
    overrides, force_playable_hub = _maybe_apply_sparse_guardrail(state, ordered_cluster, templates)

    newly_generated: list[str] = []
    for sector_id in ordered_cluster:
        if _ensure_sector_generated_core(
            state,
            sector_id,
            templates,
            archetypes,
            overrides,
            force_playable_hub,
        ):
            newly_generated.append(sector_id)

    for sector_id in ordered_cluster:
        sector_state = state.world.sector_states.get(sector_id)
        if not sector_state:
            continue
        archetype_cfg = archetypes.get(sector_state.archetype, {})
        _build_internal_links_for_sector(state, sector_id, archetype_cfg)

    _ensure_intersector_links_for_new_sectors(state, newly_generated, archetypes)


def ensure_sector_generated(state: GameState, sector_id: str) -> None:
    _ensure_sector_cluster_generated(state, [sector_id])


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
