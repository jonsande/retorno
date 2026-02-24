from __future__ import annotations

import hashlib
import random
from retorno.core.gamestate import GameState
from retorno.model.world import SpaceNode, SECTOR_SIZE_LY, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_modules, load_worldgen_templates


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
    region = region_for_pos(cx, cy, cz)
    templates = load_worldgen_templates()
    tmpl = templates.get(region) or templates.get("disk") or {}

    count = rng.randint(int(tmpl.get("node_count_min", 0)), int(tmpl.get("node_count_max", 0)))
    modules = load_modules()
    module_ids = list(modules.keys())

    # Ensure fixed hub if the origin sector is generated and hub not present.
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    if sector_id == origin_sector and "ECHO_7" not in state.world.space.nodes:
        hub = SpaceNode(
            node_id="ECHO_7",
            name="ECHO-7 Relay Station",
            kind="relay",
            radiation_rad_per_s=0.002,
            radiation_base=_radiation_for_region(region),
            region=region,
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
        node_id = f"{sector_id}:{rng.getrandbits(24):06X}"
        while node_id in state.world.space.nodes:
            node_id = f"{sector_id}:{rng.getrandbits(24):06X}"
        if node_id in state.world.space.nodes:
            continue
        name = _generate_name(rng, kind)
        node = SpaceNode(
            node_id=node_id,
            name=name,
            kind=kind,
            radiation_rad_per_s=0.0,
            radiation_base=float(tmpl.get("radiation_base", 0.0)),
            region=region,
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
        node.links.add(hub.node_id)
        hub.links.add(node.node_id)

    # Optional extra links inside sector
    for node in nodes:
        if node.node_id == hub.node_id:
            continue
        if rng.random() < 0.10:
            target = rng.choice(nodes)
            if target.node_id != node.node_id:
                node.links.add(target.node_id)
                target.links.add(node.node_id)

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
        hub.links.add(neighbor.node_id)
        neighbor.links.add(hub.node_id)


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
