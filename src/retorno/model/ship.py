from __future__ import annotations

from dataclasses import dataclass, field

from retorno.model.drones import DroneState, Inventory
from retorno.model.systems import ShipSystem


@dataclass(slots=True)
class ShedPolicyState:
    low_soc_threshold: float = 0.15


@dataclass(slots=True)
class PowerNetworkState:
    p_gen_kw: float
    e_batt_kwh: float
    e_batt_max_kwh: float
    p_charge_max_kw: float
    p_discharge_max_kw: float
    eta_charge: float = 1.0
    eta_discharge: float = 1.0

    p_load_kw: float = 0.0
    deficit_ratio: float = 0.0
    power_quality: float = 1.0
    quality_offset: float = 0.0

    brownout: bool = False
    shed_policy: ShedPolicyState = field(default_factory=ShedPolicyState)


@dataclass(slots=True)
class ShipLocation:
    # simplificado para v0
    sector_id: str = "UNKNOWN"


@dataclass(slots=True)
class ShipState:
    ship_id: str
    name: str

    op_mode: str = "NORMAL"  # NORMAL, CRUISE
    current_node_id: str = ""
    in_transit: bool = False
    transit_from: str = ""
    transit_to: str = ""
    arrival_t: float = 0.0
    cruise_speed_ly_per_year: float = 1.0
    last_travel_distance_ly: float = 0.0

    location: ShipLocation = field(default_factory=ShipLocation)
    hull_integrity: float = 1.0

    # radiación interior base (luego por sectores/nodos)
    radiation_env_rad_per_s: float = 0.001

    power: PowerNetworkState = field(default_factory=lambda: PowerNetworkState(
        p_gen_kw=0.0, e_batt_kwh=0.0, e_batt_max_kwh=1.0, p_charge_max_kw=1.0, p_discharge_max_kw=1.0
    ))

    systems: dict[str, ShipSystem] = field(default_factory=dict)
    drones: dict[str, DroneState] = field(default_factory=dict)
    sectors: dict[str, "ShipSector"] = field(default_factory=dict)

    # Cargo (truth)
    cargo_scrap: int = 0
    cargo_modules: list[str] = field(default_factory=list)

    # Manifest (record)
    manifest_scrap: int = 0
    manifest_modules: list[str] = field(default_factory=list)
    manifest_dirty: bool = False
    manifest_last_sync_t: float = 0.0

    # Installed modules (active effects)
    installed_modules: list[str] = field(default_factory=list)

    inventory: Inventory = field(default_factory=Inventory)


@dataclass(slots=True)
class ShipSector:
    sector_id: str
    name: str
    tags: set[str] = field(default_factory=set)
    notes: str = ""
