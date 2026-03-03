from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields

from retorno.model.drones import DroneState, Inventory
from retorno.model.systems import ShipSystem
from retorno.config.balance import Balance


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
    p_gen_base_kw: float = 0.0
    p_gen_bonus_kw: float = 0.0
    eta_charge: float = 1.0
    eta_discharge: float = 1.0

    p_load_kw: float = 0.0
    deficit_ratio: float = 0.0
    power_quality: float = 1.0
    quality_offset: float = 0.0

    brownout: bool = False
    brownout_sustained_s: float = 0.0
    low_q_shed_timer_s: float = 0.0
    battery_reserve_warned: bool = False
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
    op_mode_source: str = "manual"  # manual | auto
    current_node_id: str = ""
    in_transit: bool = False
    transit_from: str = ""
    transit_to: str = ""
    arrival_t: float = 0.0
    transit_start_t: float = 0.0
    cruise_speed_ly_per_year: float = 1.0
    last_travel_distance_ly: float = 0.0
    last_travel_distance_km: float = 0.0
    last_travel_is_local: bool = False
    transit_prev_op_mode: str = ""
    transit_prev_op_mode_source: str = ""
    docked_node_id: str | None = None

    location: ShipLocation = field(default_factory=ShipLocation)
    hull_integrity: float = 1.0
    is_hibernating: bool = False
    radiation_env_level: str = "unknown"
    radiation_internal_level: str = "unknown"

    # Radiación ambiental efectiva del entorno actual.
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
    sensors_range_ly: float = Balance.SENSORS_RANGE_LY
    # Time elapsed while life_support remains OFFLINE (used for viability grace countdown).
    life_support_offline_s: float = 0.0

    def __setstate__(self, state) -> None:
        """Backward-compatible unpickle for renamed fields.

        Older saves may contain `life_support_critical_s`; map it to
        `life_support_offline_s` during load.
        """
        slot_state = state
        if isinstance(state, tuple):
            # Typical slots payload: (dict_or_none, slots_dict)
            if len(state) == 2 and isinstance(state[1], dict):
                slot_state = state[1]
            elif len(state) == 2 and isinstance(state[0], dict):
                slot_state = state[0]
        if not isinstance(slot_state, dict):
            raise TypeError(f"Unsupported ShipState pickle payload: {type(state)!r}")

        data = dict(slot_state)
        if "life_support_offline_s" not in data and "life_support_critical_s" in data:
            data["life_support_offline_s"] = float(data.get("life_support_critical_s", 0.0) or 0.0)
        data.pop("life_support_critical_s", None)

        for f in fields(self):
            if f.name in data:
                value = data[f.name]
            elif f.default is not MISSING:
                value = f.default
            elif f.default_factory is not MISSING:
                value = f.default_factory()
            else:
                continue
            object.__setattr__(self, f.name, value)

        # Keep the OFFLINE grace timer only when life_support is actually OFFLINE.
        life_support = self.systems.get("life_support") if isinstance(self.systems, dict) else None
        if not life_support or getattr(getattr(life_support, "state", None), "value", "") != "offline":
            object.__setattr__(self, "life_support_offline_s", 0.0)

    def orbit_status(self, world: "SpaceGraph | object", current_node_id: str) -> str:
        """Return 'docked', 'orbit', or 'adrift' based on ship + world state."""
        if self.docked_node_id == current_node_id:
            return "docked"
        node = getattr(world, "space", world).nodes.get(current_node_id) if hasattr(world, "space") else world.nodes.get(current_node_id)
        active_tmp = getattr(world, "active_tmp_node_id", None)
        if not node or node.kind == "transit" or current_node_id == "UNKNOWN_00" or active_tmp == current_node_id:
            return "adrift"
        return "orbit"


@dataclass(slots=True)
class ShipSector:
    sector_id: str
    name: str
    tags: set[str] = field(default_factory=set)
    notes: str = ""
