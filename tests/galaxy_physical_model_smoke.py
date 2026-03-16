from __future__ import annotations

import math

from retorno.bootstrap import create_initial_state_prologue
from retorno.config.balance import Balance
from retorno.model.galaxy import (
    galactic_margins_for_op_pos,
    galactic_radius,
    galactic_region_for_op_pos,
    op_to_galactic_coords,
)


def main() -> None:
    assert math.isclose(float(Balance.GALAXY_OP_TO_PHYSICAL_SCALE), 1.0)
    assert math.isclose(float(Balance.GALAXY_PHYSICAL_RADIUS_LY), 500000.0)
    assert math.isclose(float(Balance.GALAXY_PHYSICAL_BULGE_RADIUS_LY), 10000.0)
    assert math.isclose(float(Balance.GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY), 400000.0)

    gx0, gy0, gz0 = op_to_galactic_coords(0.0, 0.0, 0.0)
    assert math.isclose(gx0, float(Balance.GALAXY_OP_ORIGIN_PHYSICAL_X_LY))
    assert math.isclose(gy0, float(Balance.GALAXY_OP_ORIGIN_PHYSICAL_Y_LY))
    assert math.isclose(gz0, float(Balance.GALAXY_OP_ORIGIN_PHYSICAL_Z_LY))

    state = create_initial_state_prologue()
    start = state.world.space.nodes.get("UNKNOWN")
    assert start is not None, "UNKNOWN must exist"
    sx, sy, sz = start.x_ly, start.y_ly, start.z_ly

    region = galactic_region_for_op_pos(sx, sy, sz)
    margins = galactic_margins_for_op_pos(sx, sy, sz)
    radius = galactic_radius(*op_to_galactic_coords(sx, sy, sz))

    assert region == "disk", region
    assert float(margins["distance_to_bulge_ly"]) >= 100000.0, margins
    assert float(margins["distance_to_halo_ly"]) >= 100000.0, margins
    assert float(margins["distance_to_galaxy_edge_ly"]) >= 0.0, margins
    assert bool(margins["inside_galaxy"]), margins
    assert math.isclose(radius, float(margins["r_gc_ly"]), rel_tol=1e-9), (radius, margins)

    print("GALAXY PHYSICAL MODEL SMOKE PASSED")


if __name__ == "__main__":
    main()
