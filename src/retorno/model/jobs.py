from __future__ import annotations

import re
from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from typing import Any


class JobType(str, Enum):
    REPAIR_SYSTEM = "repair_system"
    REPAIR_DRONE = "repair_drone"
    SELFTEST_REPAIR = "selftest_repair"
    BOOT_SERVICE = "boot_service"
    DEPLOY_DRONE = "deploy_drone"
    MOVE_DRONE = "move_drone"
    DOCK = "dock"
    UNDOCK = "undock"
    SALVAGE = "salvage"
    INSTALL_MODULE = "install_module"
    UNINSTALL_MODULE = "uninstall_module"
    DRONE_INSTALL_MODULE = "drone_install_module"
    DRONE_UNINSTALL_MODULE = "drone_uninstall_module"
    REBOOT_DRONE = "reboot_drone"
    SALVAGE_SCRAP = "salvage_scrap"
    SALVAGE_MODULE = "salvage_module"
    SALVAGE_DATA = "salvage_data"
    SURVEY_DRONE = "survey_drone"
    SALVAGE_DRONE = "salvage_drone"
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


def is_terminal_job_status(status: JobStatus) -> bool:
    return status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}


def format_active_job_id(seq: int) -> str:
    return f"J{max(1, int(seq))}"


def format_terminal_job_id(status: JobStatus, seq: int) -> str:
    prefix = {
        JobStatus.COMPLETED: "CJ",
        JobStatus.FAILED: "FJ",
        JobStatus.CANCELLED: "XJ",
    }.get(status, "J")
    return f"{prefix}{max(1, int(seq))}"


def job_id_numeric_suffix(value: str) -> int:
    match = re.search(r"(\d+)$", str(value or ""))
    return int(match.group(1)) if match else 0


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
    internal_id: str | None = None
    terminal_seq: int | None = None

    def __post_init__(self) -> None:
        if self.internal_id is None:
            object.__setattr__(self, "internal_id", self.job_id)

    def __setstate__(self, state) -> None:
        slot_state = state
        if isinstance(state, tuple):
            if len(state) == 2 and isinstance(state[1], dict):
                slot_state = state[1]
            elif len(state) == 2 and isinstance(state[0], dict):
                slot_state = state[0]
        if not isinstance(slot_state, dict):
            raise TypeError(f"Unsupported Job pickle payload: {type(state)!r}")

        data = dict(slot_state)
        if "internal_id" not in data:
            data["internal_id"] = str(data.get("job_id", ""))
        if "terminal_seq" not in data:
            raw_status = data.get("status")
            status = raw_status if isinstance(raw_status, JobStatus) else JobStatus(str(raw_status or JobStatus.QUEUED.value))
            data["terminal_seq"] = job_id_numeric_suffix(data.get("job_id", "")) if is_terminal_job_status(status) else None

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


@dataclass(slots=True)
class JobManagerState:
    jobs: dict[str, Job] = field(default_factory=dict)
    active_job_ids: list[str] = field(default_factory=list)
    next_job_seq: int = 1
    next_active_job_seq: int = 1
    next_terminal_job_seq: int = 1

    def __setstate__(self, state) -> None:
        slot_state = state
        if isinstance(state, tuple):
            if len(state) == 2 and isinstance(state[1], dict):
                slot_state = state[1]
            elif len(state) == 2 and isinstance(state[0], dict):
                slot_state = state[0]
        if not isinstance(slot_state, dict):
            raise TypeError(f"Unsupported JobManagerState pickle payload: {type(state)!r}")

        data = dict(slot_state)
        legacy_ids = "next_active_job_seq" not in data or "next_terminal_job_seq" not in data

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

        normalize_job_manager_state(self, migrate_legacy_ids=legacy_ids)


def normalize_job_manager_state(jobs_state: JobManagerState, *, migrate_legacy_ids: bool = False) -> None:
    jobs = dict(jobs_state.jobs or {})
    remap: dict[str, str] = {}

    for key, job in list(jobs.items()):
        internal_id = str(job.internal_id or key or job.job_id)
        if key != internal_id and internal_id not in jobs:
            remap[key] = internal_id
            jobs[internal_id] = jobs.pop(key)
            key = internal_id
        object.__setattr__(job, "internal_id", key)

    active_ids: list[str] = []
    seen: set[str] = set()
    for key in list(jobs_state.active_job_ids or []):
        mapped = remap.get(key, key)
        if mapped in jobs and mapped not in seen:
            active_ids.append(mapped)
            seen.add(mapped)
    object.__setattr__(jobs_state, "jobs", jobs)
    object.__setattr__(jobs_state, "active_job_ids", active_ids)

    active_set = set(active_ids)
    terminal_jobs = [
        (job_id_numeric_suffix(job.internal_id or key), key, job)
        for key, job in jobs.items()
        if key not in active_set and is_terminal_job_status(job.status)
    ]
    terminal_jobs.sort(key=lambda item: (item[0], item[1]))

    if migrate_legacy_ids:
        for index, key in enumerate(active_ids, start=1):
            job = jobs.get(key)
            if not job:
                continue
            object.__setattr__(job, "job_id", format_active_job_id(index))
            object.__setattr__(job, "terminal_seq", None)
        next_terminal = 1
        for _, _, job in terminal_jobs:
            object.__setattr__(job, "terminal_seq", next_terminal)
            object.__setattr__(job, "job_id", format_terminal_job_id(job.status, next_terminal))
            next_terminal += 1
        object.__setattr__(jobs_state, "next_active_job_seq", len(active_ids) + 1 if active_ids else 1)
        object.__setattr__(jobs_state, "next_terminal_job_seq", next_terminal)
        return

    max_active = 0
    for index, key in enumerate(active_ids, start=1):
        job = jobs.get(key)
        if not job:
            continue
        seq = job_id_numeric_suffix(job.job_id)
        if not str(job.job_id).startswith("J") or seq <= 0:
            seq = index
            object.__setattr__(job, "job_id", format_active_job_id(seq))
        object.__setattr__(job, "terminal_seq", None)
        max_active = max(max_active, seq)

    max_terminal = 0
    for _, _, job in terminal_jobs:
        seq = int(job.terminal_seq or 0)
        if seq <= 0:
            seq = job_id_numeric_suffix(job.job_id)
        if seq <= 0:
            seq = max_terminal + 1
        object.__setattr__(job, "terminal_seq", seq)
        object.__setattr__(job, "job_id", format_terminal_job_id(job.status, seq))
        max_terminal = max(max_terminal, seq)

    object.__setattr__(
        jobs_state,
        "next_active_job_seq",
        1 if not active_ids else max(int(jobs_state.next_active_job_seq or 1), max_active + 1),
    )
    object.__setattr__(
        jobs_state,
        "next_terminal_job_seq",
        max(int(jobs_state.next_terminal_job_seq or 1), max_terminal + 1),
    )


def allocate_job_ids(jobs_state: JobManagerState) -> tuple[str, str]:
    if not jobs_state.active_job_ids:
        jobs_state.next_active_job_seq = 1

    internal_seq = max(1, int(jobs_state.next_job_seq or 1))
    internal_id = f"JOB{internal_seq}"
    while internal_id in jobs_state.jobs:
        internal_seq += 1
        internal_id = f"JOB{internal_seq}"
    jobs_state.next_job_seq = internal_seq + 1

    display_seq = max(1, int(jobs_state.next_active_job_seq or 1))
    jobs_state.next_active_job_seq = display_seq + 1
    return internal_id, format_active_job_id(display_seq)


def finalize_job(jobs_state: JobManagerState, job_key: str, status: JobStatus) -> Job | None:
    job = jobs_state.jobs.get(job_key)
    if not job:
        return None
    object.__setattr__(job, "status", status)
    seq = max(1, int(jobs_state.next_terminal_job_seq or 1))
    jobs_state.next_terminal_job_seq = seq + 1
    object.__setattr__(job, "terminal_seq", seq)
    object.__setattr__(job, "job_id", format_terminal_job_id(status, seq))
    if job_key in jobs_state.active_job_ids:
        jobs_state.active_job_ids.remove(job_key)
    if not jobs_state.active_job_ids:
        jobs_state.next_active_job_seq = 1
    return job


def find_job_key(jobs_state: JobManagerState, job_ref: str) -> str | None:
    ref = str(job_ref or "").strip()
    if not ref:
        return None
    if ref in jobs_state.jobs:
        return ref
    for key in jobs_state.active_job_ids:
        job = jobs_state.jobs.get(key)
        if job and job.job_id == ref:
            return key
    for key, job in jobs_state.jobs.items():
        if job.job_id == ref:
            return key
    return None


def active_job_display_ids(jobs_state: JobManagerState) -> list[str]:
    ids: list[str] = []
    for key in jobs_state.active_job_ids:
        job = jobs_state.jobs.get(key)
        if job:
            ids.append(job.job_id)
    return ids
