from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SpaceNode:
    node_id: str
    name: str
    kind: str  # "ship", "station", "derelict"
    radiation_rad_per_s: float = 0.0
    radiation_base: float = 0.0
    region: str = ""
    x_ly: float = 0.0
    y_ly: float = 0.0
    z_ly: float = 0.0
    salvage_scrap_available: int = 0
    salvage_modules_available: list[str] = field(default_factory=list)
    salvage_dry: bool = False


@dataclass(slots=True)
class SpaceGraph:
    nodes: dict[str, SpaceNode] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)  # adjacency


@dataclass(slots=True)
class WorldState:
    space: SpaceGraph = field(default_factory=SpaceGraph)
    known_contacts: set[str] = field(default_factory=set)
    known_nodes: set[str] = field(default_factory=set)
    known_intel: dict[str, dict] = field(default_factory=dict)
    generated_sectors: set[str] = field(default_factory=set)
    current_node_id: str = "SHIP_1"
    current_pos_ly: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rng_seed: int = 0


SECTOR_SIZE_LY = 10.0


def sector_id_for_pos(x_ly: float, y_ly: float, z_ly: float) -> str:
    import math
    sx = math.floor(x_ly / SECTOR_SIZE_LY)
    sy = math.floor(y_ly / SECTOR_SIZE_LY)
    sz = math.floor(z_ly / SECTOR_SIZE_LY)
    return f"S{sx:+04d}_{sy:+04d}_{sz:+04d}"


def region_for_pos(x_ly: float, y_ly: float, z_ly: float) -> str:
    # Simple radial split for v0: bulge (inner), disk (mid), halo (outer)
    import math
    r = math.sqrt(x_ly * x_ly + y_ly * y_ly + z_ly * z_ly)
    if r < 5.0:
        return "bulge"
    if r < 15.0:
        return "disk"
    return "halo"
