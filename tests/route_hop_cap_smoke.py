from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.actions import Travel
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.model.world import SpaceNode, add_known_link, region_for_pos, sector_id_for_pos
from retorno.worldgen.generator import ensure_sector_generated


def _assert_travel_cap_blocks_long_hop() -> None:
    state = create_initial_state_sandbox()
    engine = Engine()

    current_id = state.world.current_node_id
    current = state.world.space.nodes[current_id]
    far_id = "SMOKE_FAR_HOP"
    far_x = current.x_ly + (float(Balance.MAX_ROUTE_HOP_LY) + 15.0)
    far_y = current.y_ly
    far_z = current.z_ly
    state.world.space.nodes[far_id] = SpaceNode(
        node_id=far_id,
        name="Far Hop",
        kind="station",
        radiation_rad_per_s=0.001,
        region=region_for_pos(far_x, far_y, far_z),
        x_ly=far_x,
        y_ly=far_y,
        z_ly=far_z,
    )
    state.world.known_nodes.add(far_id)
    state.world.known_contacts.add(far_id)
    add_known_link(state.world, current_id, far_id, bidirectional=True)

    events = engine.apply_action(state, Travel(node_id=far_id))
    assert events, "travel should be blocked by hop cap"
    assert not state.ship.in_transit, "ship must remain out of transit when cap blocks hop"
    reasons = [
        str((ev.data or {}).get("reason"))
        for ev in events
        if ev.type in {EventType.BOOT_BLOCKED, EventType.TRAVEL_STARTED}
    ]
    assert "hop_cap_exceeded" in reasons, reasons


def _assert_worldgen_links_respect_cap() -> None:
    state = create_initial_state_sandbox()
    current = state.world.space.nodes[state.world.current_node_id]
    base_sid = sector_id_for_pos(current.x_ly, current.y_ly, current.z_ly)
    sx, sy, sz = [int(p) for p in base_sid[1:].split("_")]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            ensure_sector_generated(state, f"S{sx+dx:+04d}_{sy+dy:+04d}_{sz:+04d}")

    cap = float(Balance.MAX_ROUTE_HOP_LY)
    for node in state.world.space.nodes.values():
        for dst_id in node.links:
            if node.node_id >= dst_id:
                continue
            dst = state.world.space.nodes.get(dst_id)
            if not dst:
                continue
            dx = node.x_ly - dst.x_ly
            dy = node.y_ly - dst.y_ly
            dz = node.z_ly - dst.z_ly
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            assert dist <= cap, (node.node_id, dst_id, dist, cap)


def main() -> None:
    _assert_travel_cap_blocks_long_hop()
    _assert_worldgen_links_respect_cap()
    print("ROUTE HOP CAP SMOKE PASSED")


if __name__ == "__main__":
    main()
