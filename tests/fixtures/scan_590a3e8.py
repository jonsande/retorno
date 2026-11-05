"""Frozen scan kernel from 590a3e8 for exact RNG/output comparison only.

Never imported by production. No alternate scanning workflow is installed.
"""
from __future__ import annotations
from retorno.core.engine import (GameState, SystemState, Balance, SECTOR_SIZE_LY,
    ensure_sector_generated, record_intel, random, math)


def perform_scan(self, state: GameState) -> tuple[list[str], list[str], list[dict[str, object]]]:
    current_id = state.world.current_node_id
    node = state.world.space.nodes.get(current_id)
    if node:
        x, y, z = node.x_ly, node.y_ly, node.z_ly
    else:
        x, y, z = state.world.current_pos_ly

    radius_ly = float(state.ship.sensors_range_ly)
    min_sx = math.floor((x - radius_ly) / SECTOR_SIZE_LY)
    max_sx = math.floor((x + radius_ly) / SECTOR_SIZE_LY)
    min_sy = math.floor((y - radius_ly) / SECTOR_SIZE_LY)
    max_sy = math.floor((y + radius_ly) / SECTOR_SIZE_LY)
    min_sz = math.floor((z - radius_ly) / SECTOR_SIZE_LY)
    max_sz = math.floor((z + radius_ly) / SECTOR_SIZE_LY)
    for sx in range(min_sx, max_sx + 1):
        for sy in range(min_sy, max_sy + 1):
            for sz in range(min_sz, max_sz + 1):
                ensure_sector_generated(state, f"S{sx:+04d}_{sy:+04d}_{sz:+04d}")

    system = state.ship.systems.get("sensors")
    state_p = {
        SystemState.UPGRADED: Balance.SENSORS_DETECT_P_NOMINAL,
        SystemState.NOMINAL: Balance.SENSORS_DETECT_P_NOMINAL,
        SystemState.LIMITED: Balance.SENSORS_DETECT_P_LIMITED,
        SystemState.DAMAGED: Balance.SENSORS_DETECT_P_DAMAGED,
        SystemState.CRITICAL: Balance.SENSORS_DETECT_P_CRITICAL,
    }.get(system.state if system else SystemState.CRITICAL, Balance.SENSORS_DETECT_P_CRITICAL)

    def _chance_for(dist_ly: float) -> float:
        if radius_ly <= 0:
            return 0.0
        t = min(1.0, max(0.0, dist_ly / radius_ly))
        return Balance.SENSORS_DETECT_P_NEAR + (Balance.SENSORS_DETECT_P_FAR - Balance.SENSORS_DETECT_P_NEAR) * t

    seen: list[str] = []
    discovered: list[str] = []
    fine_range_updates: list[dict[str, object]] = []
    recovery_entry_id = getattr(state.world.exploration_recovery, "entry_node_id", None)
    state.meta.rng_counter += 1

    for node_id, target in state.world.space.nodes.items():
        dx = target.x_ly - x
        dy = target.y_ly - y
        dz = target.z_ly - z
        dist2 = dx * dx + dy * dy + dz * dz
        if dist2 > radius_ly * radius_ly:
            continue

        dist_ly = dist2 ** 0.5
        guaranteed_recovery_detect = node_id == recovery_entry_id and node_id not in state.world.known_nodes
        if not guaranteed_recovery_detect:
            detect_p = max(0.0, min(1.0, _chance_for(dist_ly) * state_p))
            seed = self._hash64(state.meta.rng_seed + state.meta.rng_counter, f"scan:{node_id}:{int(state.clock.t)}")
            rng = random.Random(seed)
            if rng.random() > detect_p:
                continue

        seen.append(node_id)
        is_new = node_id not in state.world.known_nodes
        if is_new:
            discovered.append(node_id)
        state.world.known_nodes.add(node_id)
        state.world.known_contacts.add(node_id)

        if is_new:
            record_intel(
                state.world,
                t=state.clock.t,
                kind="node",
                to_id=node_id,
                confidence=0.6,
                source_kind="scan",
                source_ref=current_id,
            )

        if (
            dist2 <= Balance.LOCAL_TRAVEL_RADIUS_LY ** 2
            and target.kind in {"relay", "station", "waystation", "ship", "derelict"}
            and current_id != node_id
        ):
            fine_km = self._maybe_set_fine_range(state, current_id, node_id)
            if fine_km is not None:
                fine_range_updates.append({"node_id": node_id, "distance_km": fine_km})

    seen.sort()
    discovered.sort()
    fine_range_updates.sort(key=lambda item: str(item.get("node_id", "")))
    return seen, discovered, fine_range_updates

