from __future__ import annotations

import hashlib
import random
from retorno.core.gamestate import GameState
from retorno.model.world import SpaceNode, SECTOR_SIZE_LY, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_modules, load_worldgen_templates
from retorno.config.balance import Balance


def _hash64(seed: int, text: str) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode("utf-8"))
    h.update(text.encode("utf-8"))
    return int.from_bytes(h.digest(), "big", signed=False)


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    total = sum(weights.values())
    r = rng.random() * total
    upto = 0.0
    for k, w in weights.items():
        upto += w
        if r <= upto:
            return k
    return next(iter(weights.keys()))


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
    # Legacy compatibility for existing callers that set SpaceNode.radiation_base.
    return _procedural_radiation_base_for_region(region)


def ensure_sector_generated(state: GameState, sector_id: str) -> None:
    if sector_id in state.world.generated_sectors:
        return
    seed = _hash64(state.meta.rng_seed, sector_id)
    rng = random.Random(seed)

    # Decode sector indices from id
    try:
        _, sx, sy, sz = sector_id[1:].split("_")
        sx_i = int(sx)
        sy_i = int(sy)
        sz_i = int(sz)
    except Exception:
        sx_i = sy_i = sz_i = 0

    # Sector bounds
    x0 = sx_i * SECTOR_SIZE_LY
    y0 = sy_i * SECTOR_SIZE_LY
    z0 = sz_i * SECTOR_SIZE_LY

    # Pick region using sector center
    cx = x0 + SECTOR_SIZE_LY / 2.0
    cy = y0 + SECTOR_SIZE_LY / 2.0
    cz = z0 + SECTOR_SIZE_LY / 2.0
    sector_region = region_for_pos(cx, cy, cz)
    templates = load_worldgen_templates()
    tmpl = templates.get(sector_region) or templates.get("disk") or {}

    count = rng.randint(int(tmpl.get("node_count_min", 0)), int(tmpl.get("node_count_max", 0)))
    modules = load_modules()
    module_ids = list(modules.keys())

    # Ensure fixed hub if the origin sector is generated and hub not present.
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    if sector_id == origin_sector and "ECHO_7" not in state.world.space.nodes:
        hub_region = region_for_pos(0.0, 0.0, 0.0)
        hub_rad = procedural_radiation_for_node(state.meta.rng_seed, "ECHO_7", "relay", hub_region)
        hub = SpaceNode(
            node_id="ECHO_7",
            name="ECHO-7 Relay Station",
            kind="relay",
            radiation_rad_per_s=hub_rad,
            radiation_base=_radiation_for_region(hub_region),
            region=hub_region,
            x_ly=0.0,
            y_ly=0.0,
            z_ly=0.0,
        )
        state.world.space.nodes[hub.node_id] = hub

    for _i in range(count):
        x = x0 + rng.random() * SECTOR_SIZE_LY
        y = y0 + rng.random() * SECTOR_SIZE_LY
        z_sigma = float(tmpl.get("z_sigma", 0.3))
        z = z0 + rng.gauss(0.0, z_sigma)
        kind = _weighted_choice(rng, tmpl.get("kind_weights", {}))
        node_id = _generate_node_id(state, kind, rng)
        name = _name_from_node_id(node_id, kind)
        node_region = region_for_pos(x, y, z)
        rad_base = _radiation_for_region(node_region)
        rad = procedural_radiation_for_node(state.meta.rng_seed, node_id, kind, node_region)
        node = SpaceNode(
            node_id=node_id,
            name=name,
            kind=kind,
            radiation_rad_per_s=rad,
            radiation_base=rad_base,
            region=node_region,
            x_ly=x,
            y_ly=y,
            z_ly=z,
        )
        if kind in {"station", "derelict", "ship", "relay"}:
            salvage = tmpl.get("salvage", {})
            scrap_min = int(salvage.get("scrap_min", 0))
            scrap_max = int(salvage.get("scrap_max", 0))
            if scrap_max > 0:
                node.salvage_scrap_available = rng.randint(scrap_min, scrap_max)
            node.salvage_modules_available = _pick_modules(
                rng,
                module_ids,
                int(salvage.get("modules_min", 0)),
                int(salvage.get("modules_max", 0)),
                salvage.get("modules_pool"),
            )
        node.recoverable_drones_count = _roll_recoverable_drones_for_node(
            state.meta.rng_seed,
            node.node_id,
            node.kind,
        )
        state.world.space.nodes[node_id] = node

    _generate_links_for_sector(state, sector_id, rng)
    state.world.generated_sectors.add(sector_id)


def _sector_nodes(state: GameState, sector_id: str) -> list[SpaceNode]:
    return [
        n
        for n in state.world.space.nodes.values()
        if sector_id_for_pos(n.x_ly, n.y_ly, n.z_ly) == sector_id
    ]


def _pick_hub(nodes: list[SpaceNode]) -> SpaceNode | None:
    if not nodes:
        return None
    preferred = [n for n in nodes if n.kind in {"station", "relay", "waystation"}]
    if preferred:
        return sorted(preferred, key=lambda n: n.node_id)[0]
    return sorted(nodes, key=lambda n: n.node_id)[0]


def _generate_links_for_sector(state: GameState, sector_id: str, rng: random.Random) -> None:
    max_hop = float(Balance.MAX_ROUTE_HOP_LY)

    def _link_with_cap(a: SpaceNode, b: SpaceNode) -> bool:
        dx = a.x_ly - b.x_ly
        dy = a.y_ly - b.y_ly
        dz = a.z_ly - b.z_ly
        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
        if dist > max_hop:
            return False
        a.links.add(b.node_id)
        b.links.add(a.node_id)
        return True

    nodes = _sector_nodes(state, sector_id)
    if not nodes:
        return
    hub = _pick_hub(nodes)
    if not hub:
        return
    hub.is_hub = True
    for node in nodes:
        if node.node_id == hub.node_id:
            continue
        _link_with_cap(node, hub)

    # Optional extra links inside sector
    for node in nodes:
        if node.node_id == hub.node_id:
            continue
        if rng.random() < 0.10:
            target = rng.choice(nodes)
            if target.node_id != node.node_id:
                _link_with_cap(node, target)

    # Link hub to neighbor sector hubs (2D neighbors only)
    try:
        _, sx, sy, sz = sector_id[1:].split("_")
        sx_i = int(sx)
        sy_i = int(sy)
        sz_i = int(sz)
    except Exception:
        sx_i = sy_i = sz_i = 0
    neighbors = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            neighbor_id = f"S{sx_i+dx:+04d}_{sy_i+dy:+04d}_{sz_i:+04d}"
            if neighbor_id in state.world.generated_sectors:
                neighbor_nodes = _sector_nodes(state, neighbor_id)
                neighbor_hub = _pick_hub(neighbor_nodes)
                if neighbor_hub:
                    neighbors.append(neighbor_hub)
    neighbors = sorted(neighbors, key=lambda n: (n.x_ly - hub.x_ly) ** 2 + (n.y_ly - hub.y_ly) ** 2)
    for neighbor in neighbors[:2]:
        _link_with_cap(hub, neighbor)


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
    if kind == "ship":
        prefix = "WRECK"
    else:
        prefix = (kind or "node").upper()
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


def _generate_name(rng: random.Random, kind: str) -> str:
    if kind == "relay":
        return f"Relay-{rng.randint(1, 99)}"
    if kind == "station":
        return f"Station-{rng.randint(1, 99)}"
    if kind == "derelict":
        return f"Derelict-{rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}-{rng.randint(1, 9)}"
    if kind == "ship":
        return f"Wreck-{rng.randint(1, 99)}"
    return f"Node-{rng.randint(1, 999)}"
