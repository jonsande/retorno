from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SpaceNode:
    node_id: str
    name: str
    kind: str  # "ship", "station", "derelict"
    radiation_rad_per_s: float = 0.0
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
    current_node_id: str = "SHIP_1"
    rng_seed: int = 0
