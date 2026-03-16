from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.core.lore import build_lore_context
from retorno.model.world import SpaceNode, region_for_pos


def main() -> None:
    state = create_initial_state_sandbox()
    start = state.world.space.nodes.get("UNKNOWN")
    assert start is not None, "UNKNOWN must exist"
    start.x_ly = 100.0
    start.y_ly = -25.0
    start.z_ly = 3.0

    node_id = "SMOKE_LORE_DIST"
    x = 118.0
    y = -25.0
    z = 3.0
    state.world.space.nodes[node_id] = SpaceNode(
        node_id=node_id,
        name="Lore Dist Node",
        kind="station",
        radiation_rad_per_s=0.001,
        region=region_for_pos(x, y, z),
        x_ly=x,
        y_ly=y,
        z_ly=z,
    )

    ctx = build_lore_context(state, node_id)
    assert abs(ctx.dist_from_origin_ly - 18.0) < 1e-6, ctx
    print("LORE DISTANCE FROM START SMOKE PASSED")


if __name__ == "__main__":
    main()
