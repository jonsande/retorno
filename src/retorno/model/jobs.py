from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobType(str, Enum):
    REPAIR_SYSTEM = "repair_system"
    SELFTEST_REPAIR = "selftest_repair"
    BOOT_SERVICE = "boot_service"
    DEPLOY_DRONE = "deploy_drone"
    MOVE_DRONE = "move_drone"
    DOCK = "dock"
    SALVAGE = "salvage"
    INSTALL_MODULE = "install_module"
    REBOOT_DRONE = "reboot_drone"
    SALVAGE_SCRAP = "salvage_scrap"
    SALVAGE_MODULE = "salvage_module"
    SALVAGE_DATA = "salvage_data"
    ROUTE_SOLVE = "route_solve"
    RECALL_DRONE = "recall_drone"
    CARGO_AUDIT = "cargo_audit"
    RECOVER_AUTH = "recover_auth"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class TargetRef:
    kind: str  # "ship_system", "ship_sector", "service"
    id: str


@dataclass(slots=True)
class RiskProfile:
    p_glitch_per_s: float = 0.0
    p_fail_per_s: float = 0.0


@dataclass(slots=True)
class Job:
    job_id: str
    job_type: JobType
    status: JobStatus
    eta_s: float
    progress: float = 0.0
    owner_id: str | None = None
    target: TargetRef | None = None
    params: dict[str, Any] = field(default_factory=dict)
    risk: RiskProfile = field(default_factory=RiskProfile)
    power_draw_kw: float = 0.0


@dataclass(slots=True)
class JobManagerState:
    jobs: dict[str, Job] = field(default_factory=dict)
    active_job_ids: list[str] = field(default_factory=list)
    next_job_seq: int = 1
