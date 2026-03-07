from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from enum import Enum

from retorno.config.balance import Balance


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
class DroneEffectiveProfile:
    integrity_max_effective: float = 1.0
    battery_max_effective: float = 1.0
    move_time_mult_effective: float = 1.0
    deploy_time_mult_effective: float = 1.0
    survey_time_mult_effective: float = 1.0
    repair_time_mult_effective: float = 1.0
    repair_fail_p_mult_effective: float = 1.0
    repair_scrap_cost_mult_effective: float = 1.0
    cargo_capacity_effective: float = Balance.DRONE_CARGO_CAPACITY_BASE


@dataclass(slots=True)
class DroneState:
    drone_id: str
    name: str
    status: DroneStatus
    location: DroneLocation

    integrity: float = 1.0
    battery: float = 1.0
    low_battery_warned: bool = False
    autorecall_enabled: bool = True
    autorecall_threshold: float = 0.10

    shield_factor: float = 1.0
    dose_rad: float = 0.0
    radiation_level: str = "unknown"
    link_quality: float = 1.0

    installed_modules: list[str] = field(default_factory=list)
    module_slots_max: int = 2
    cargo_capacity_base: float = Balance.DRONE_CARGO_CAPACITY_BASE

    cargo: Inventory = field(default_factory=Inventory)
    tools: list[str] = field(default_factory=list)

    def __setstate__(self, state) -> None:
        """Backward-compatible unpickle for slot additions."""
        slot_state = state
        if isinstance(state, tuple):
            if len(state) == 2 and isinstance(state[1], dict):
                slot_state = state[1]
            elif len(state) == 2 and isinstance(state[0], dict):
                slot_state = state[0]
        if not isinstance(slot_state, dict):
            raise TypeError(f"Unsupported DroneState pickle payload: {type(state)!r}")

        data = dict(slot_state)
        if "installed_modules" not in data:
            data["installed_modules"] = []
        if "module_slots_max" not in data:
            data["module_slots_max"] = 2
        if "cargo_capacity_base" not in data:
            data["cargo_capacity_base"] = Balance.DRONE_CARGO_CAPACITY_BASE

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


def compute_drone_effective_profile(drone: DroneState, modules_catalog: dict[str, dict]) -> DroneEffectiveProfile:
    """Compute non-persistent effective drone profile from base + installed modules."""
    profile = DroneEffectiveProfile(cargo_capacity_effective=max(1.0, float(drone.cargo_capacity_base or 0.0)))
    integrity_add = 0.0
    battery_add = 0.0
    cargo_add = 0.0

    for mod_id in list(drone.installed_modules or []):
        info = modules_catalog.get(mod_id, {})
        if str(info.get("scope", "ship")) != "drone":
            continue
        effects = info.get("drone_effects", {}) or {}
        integrity_add += float(effects.get("integrity_max_add", 0.0) or 0.0)
        battery_add += float(effects.get("battery_max_add", 0.0) or 0.0)
        cargo_add += float(effects.get("cargo_capacity_add", 0.0) or 0.0)
        profile.move_time_mult_effective *= float(effects.get("move_time_mult", 1.0) or 1.0)
        profile.deploy_time_mult_effective *= float(effects.get("deploy_time_mult", 1.0) or 1.0)
        profile.survey_time_mult_effective *= float(effects.get("survey_time_mult", 1.0) or 1.0)
        profile.repair_time_mult_effective *= float(effects.get("repair_time_mult", 1.0) or 1.0)
        profile.repair_fail_p_mult_effective *= float(effects.get("repair_fail_p_mult", 1.0) or 1.0)
        profile.repair_scrap_cost_mult_effective *= float(effects.get("repair_scrap_cost_mult", 1.0) or 1.0)

    profile.integrity_max_effective = _clamp(1.0 + integrity_add, 0.4, 2.5)
    profile.battery_max_effective = _clamp(1.0 + battery_add, 0.4, 2.5)
    profile.cargo_capacity_effective = _clamp(profile.cargo_capacity_effective + cargo_add, 1.0, 200.0)
    profile.move_time_mult_effective = _clamp(profile.move_time_mult_effective, 0.35, 3.0)
    profile.deploy_time_mult_effective = _clamp(profile.deploy_time_mult_effective, 0.35, 3.0)
    profile.survey_time_mult_effective = _clamp(profile.survey_time_mult_effective, 0.35, 3.0)
    profile.repair_time_mult_effective = _clamp(profile.repair_time_mult_effective, 0.35, 3.0)
    profile.repair_fail_p_mult_effective = _clamp(profile.repair_fail_p_mult_effective, 0.2, 3.0)
    profile.repair_scrap_cost_mult_effective = _clamp(profile.repair_scrap_cost_mult_effective, 0.2, 4.0)
    return profile


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value
