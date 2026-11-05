from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from typing import Any


class SystemState(str, Enum):
    OFFLINE = "offline"
    CRITICAL = "critical"
    DAMAGED = "damaged"
    LIMITED = "limited"
    NOMINAL = "nominal"
    UPGRADED = "upgraded"


@dataclass(slots=True)
class Dependency:
    # gating formal (v0: solo sistema>=estado)
    dep_type: str  # "system_state_at_least"
    target_id: str
    value: str     # SystemState.value


@dataclass(slots=True)
class ServiceState:
    service_name: str
    is_installed: bool = True
    is_running: bool = False
    boot_time_s: int = 5
    last_boot_error: str | None = None
    requires_active_owner: bool = False

    def __setstate__(self, state) -> None:
        data = state[1] if isinstance(state, tuple) else state
        for spec in fields(self):
            value = data.get(spec.name, spec.default)
            if value is MISSING:
                raise ValueError(f"Service field missing: {spec.name}")
            object.__setattr__(self, spec.name, value)


def power_multiplier(state: SystemState) -> float:
    return {
        SystemState.OFFLINE: 0.00,
        SystemState.CRITICAL: 1.35,
        SystemState.DAMAGED: 1.20,
        SystemState.LIMITED: 0.80,
        SystemState.NOMINAL: 1.00,
        SystemState.UPGRADED: 1.10,
    }[state]


@dataclass(slots=True)
class ShipSystem:
    system_id: str
    name: str
    state: SystemState
    health: float  # 0..health_max_effective

    p_nom_kw: float
    priority: int  # 1..5

    base_decay_per_s: float
    k_power: float
    k_rad: float

    health_max_effective: float = 1.0
    sector_id: str = "UNKNOWN"
    state_locked: bool = False
    forced_offline: bool = False
    auto_offline_reason: str | None = None

    dependencies: list[Dependency] = field(default_factory=list)
    service: ServiceState | None = None
    tags: set[str] = field(default_factory=set)

    def p_effective_kw(self) -> float:
        return self.p_nom_kw * power_multiplier(self.state)


def build_communications_system() -> ShipSystem:
    """Shared new-game and additive schema-3 default; never starts the receiver."""
    return ShipSystem(
        system_id="comms", name="Communications System", sector_id="BRG-01",
        state=SystemState.OFFLINE, forced_offline=True, health=0.90,
        p_nom_kw=0.15, priority=4, base_decay_per_s=8.5e-11,
        k_power=0.30, k_rad=0.10,
        dependencies=[Dependency("system_state_at_least", "energy_distribution", "nominal")],
        service=ServiceState("radiod", boot_time_s=5, requires_active_owner=True),
    )


def system_name_for_locale(system: ShipSystem, locale: str) -> str:
    if system.system_id == "comms" and locale == "es":
        return "Sistema de comunicaciones"
    return system.name


def service_name_for_locale(service: ServiceState, locale: str) -> str:
    names = {
        "radiod": ("Radio Communications Service", "Servicio de comunicaciones por radio"),
        "sensord": ("Sensor Service", "Servicio de sensores"),
        "datad": ("Data Service", "Servicio de datos"),
        "securityd": ("Security Service", "Servicio de seguridad"),
        "core_os": ("Core OS", "Sistema operativo central"),
    }
    return names.get(service.service_name, (service.service_name, service.service_name))[locale == "es"]
