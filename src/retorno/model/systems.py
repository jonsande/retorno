from __future__ import annotations

from dataclasses import dataclass, field
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
    health: float  # 0..1

    p_nom_kw: float
    priority: int  # 1..5

    base_decay_per_s: float
    k_power: float
    k_rad: float

    state_locked: bool = False
    forced_offline: bool = False

    dependencies: list[Dependency] = field(default_factory=list)
    service: ServiceState | None = None
    tags: set[str] = field(default_factory=set)

    def p_effective_kw(self) -> float:
        return self.p_nom_kw * power_multiplier(self.state)
