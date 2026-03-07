from __future__ import annotations

import math

from retorno.config.balance import Balance


def op_to_galactic_coords(x_ly: float, y_ly: float, z_ly: float) -> tuple[float, float, float]:
    scale = float(Balance.GALAXY_OP_TO_PHYSICAL_SCALE)
    ox = float(Balance.GALAXY_OP_ORIGIN_PHYSICAL_X_LY)
    oy = float(Balance.GALAXY_OP_ORIGIN_PHYSICAL_Y_LY)
    oz = float(Balance.GALAXY_OP_ORIGIN_PHYSICAL_Z_LY)
    return (ox + x_ly * scale, oy + y_ly * scale, oz + z_ly * scale)


def galactic_radius(gx_ly: float, gy_ly: float, gz_ly: float) -> float:
    cx = float(Balance.GALAXY_PHYSICAL_CENTER_X_LY)
    cy = float(Balance.GALAXY_PHYSICAL_CENTER_Y_LY)
    cz = float(Balance.GALAXY_PHYSICAL_CENTER_Z_LY)
    dx = gx_ly - cx
    dy = gy_ly - cy
    dz = gz_ly - cz
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def galactic_region_for_op_pos(x_ly: float, y_ly: float, z_ly: float) -> str:
    gx, gy, gz = op_to_galactic_coords(x_ly, y_ly, z_ly)
    r = galactic_radius(gx, gy, gz)
    bulge_r = float(Balance.GALAXY_PHYSICAL_BULGE_RADIUS_LY)
    disk_r = float(Balance.GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY)
    if r < bulge_r:
        return "bulge"
    if r < disk_r:
        return "disk"
    return "halo"


def galactic_margins_for_op_pos(x_ly: float, y_ly: float, z_ly: float) -> dict[str, float | bool]:
    gx, gy, gz = op_to_galactic_coords(x_ly, y_ly, z_ly)
    r = galactic_radius(gx, gy, gz)
    bulge_r = float(Balance.GALAXY_PHYSICAL_BULGE_RADIUS_LY)
    disk_r = float(Balance.GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY)
    galaxy_r = float(Balance.GALAXY_PHYSICAL_RADIUS_LY)
    return {
        "r_gc_ly": r,
        "distance_to_bulge_ly": max(0.0, r - bulge_r),
        "distance_to_halo_ly": max(0.0, disk_r - r),
        "distance_to_galaxy_edge_ly": max(0.0, galaxy_r - r),
        "inside_galaxy": r <= galaxy_r,
    }


def legacy_operational_region_for_pos(x_ly: float, y_ly: float, z_ly: float) -> str:
    cx = float(Balance.GALAXY_OP_REGION_CENTER_X_LY)
    cy = float(Balance.GALAXY_OP_REGION_CENTER_Y_LY)
    cz = float(Balance.GALAXY_OP_REGION_CENTER_Z_LY)
    dx = x_ly - cx
    dy = y_ly - cy
    dz = z_ly - cz
    r = math.sqrt(dx * dx + dy * dy + dz * dz)
    if r < float(Balance.GALAXY_OP_BULGE_RADIUS_LY):
        return "bulge"
    if r < float(Balance.GALAXY_OP_DISK_OUTER_RADIUS_LY):
        return "disk"
    return "halo"
