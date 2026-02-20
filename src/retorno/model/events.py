from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class EventType(str, Enum):
    POWER_NET_DEFICIT = "power_net_deficit"
    POWER_CORE_DEGRADED = "power_core_degraded"
    POWER_BUS_INSTABILITY = "power_bus_instability"
    LOW_POWER_QUALITY = "low_power_quality"
    SYSTEM_STATE_CHANGED = "system_state_changed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    BOOT_BLOCKED = "boot_blocked"
    SIGNAL_DETECTED = "signal_detected"
    JOB_QUEUED = "job_queued"
    DOCKED = "docked"
    SALVAGE_SCRAP_GAINED = "salvage_scrap_gained"
    SALVAGE_MODULE_FOUND = "salvage_module_found"
    MODULE_INSTALLED = "module_installed"
    DRONE_DISABLED = "drone_disabled"


@dataclass(slots=True)
class SourceRef:
    # Referencias simples; ampliable
    kind: str  # "ship_system", "drone", "ship", "world"
    id: str    # system_id, drone_id, etc.


@dataclass(slots=True)
class Event:
    event_id: str
    t: int
    type: EventType
    severity: Severity
    source: SourceRef
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass(slots=True)
class AlertState:
    alert_key: str                 # normalmente EventType.value
    severity: Severity
    first_seen_t: int
    last_seen_t: int
    unacked_s: int = 0
    acknowledged: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass(slots=True)
class EventManagerState:
    # Mantén esto pequeño al principio; no necesitas persistir histórico infinito.
    recent: list[Event] = field(default_factory=list)
    alerts: dict[str, AlertState] = field(default_factory=dict)
    next_event_seq: int = 1
