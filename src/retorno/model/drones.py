from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DroneStatus(str, Enum):
    DOCKED = "docked"
    DEPLOYED = "deployed"
    DISABLED = "disabled"
    LOST = "lost"


@dataclass(slots=True)
class DroneLocation:
    kind: str  # "ship_sector" / "world_node"
    id: str


@dataclass(slots=True)
class Inventory:
    scrap: int = 0
    components: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class DroneState:
    drone_id: str
    name: str
    status: DroneStatus
    location: DroneLocation

    integrity: float = 1.0
    battery: float = 1.0
    low_battery_warned: bool = False

    shield_factor: float = 1.0
    dose_rad: float = 0.0
    link_quality: float = 1.0

    cargo: Inventory = field(default_factory=Inventory)
    tools: list[str] = field(default_factory=list)
