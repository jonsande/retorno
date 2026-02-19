from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from retorno.core.actions import (
    Action,
    Boot,
    Diag,
    DroneDeploy,
    PowerShed,
    Repair,
    Status,
)
from retorno.core.gamestate import GameState
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import AlertState, Event, EventManagerState, EventType, Severity, SourceRef
from retorno.model.jobs import Job, JobManagerState, JobStatus, JobType, TargetRef
from retorno.model.systems import Dependency, ShipSystem, SystemState


class Engine:
    _BUS_INSTABILITY_AFTER_S = 120
    _LOW_POWER_QUALITY_THRESHOLD = 0.7
    _R_REF = 0.05
    _MAX_RECENT_EVENTS = 50

    _REPAIR_TIME_S = 25.0
    _DEPLOY_TIME_S = 6.0

    def tick(self, state: GameState, dt: float) -> list[Event]:
        if dt <= 0:
            return []

        state.clock.last_dt = dt
        state.clock.t += int(dt)

        events: list[Event] = []

        events.extend(self._process_jobs(state, dt))

        p_load = self._compute_load_kw(state.ship.systems.values())
        state.ship.power.p_load_kw = p_load

        p_gen = state.ship.power.p_gen_kw
        p_discharge_max = state.ship.power.p_discharge_max_kw
        p_charge_max = state.ship.power.p_charge_max_kw

        deficit_ratio = 0.0
        net = p_gen - p_load
        if net >= 0:
            charge_kw = min(net, p_charge_max)
            delta_e = (charge_kw * dt / 3600.0) * state.ship.power.eta_charge
            state.ship.power.e_batt_kwh = min(
                state.ship.power.e_batt_max_kwh,
                state.ship.power.e_batt_kwh + delta_e,
            )
        else:
            discharge_kw = min(-net, p_discharge_max)
            delta_e = (discharge_kw * dt / 3600.0) / max(state.ship.power.eta_discharge, 1e-6)
            state.ship.power.e_batt_kwh = max(
                0.0,
                state.ship.power.e_batt_kwh - delta_e,
            )
            if -net > p_discharge_max and p_load > 0:
                deficit_ratio = min(1.0, (-net - p_discharge_max) / p_load)

        state.ship.power.deficit_ratio = deficit_ratio
        soc = (
            state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh
            if state.ship.power.e_batt_max_kwh > 0
            else 0.0
        )
        q_soc = self._clamp(soc)
        q_def = self._clamp(1.0 - deficit_ratio)
        power_quality = 0.6 * q_soc + 0.4 * q_def

        distribution = state.ship.systems.get("energy_distribution")
        if distribution and distribution.state in (SystemState.DAMAGED, SystemState.CRITICAL):
            power_quality -= 0.10

        power_quality = self._clamp(power_quality)
        state.ship.power.power_quality = power_quality

        if p_load > p_gen + p_discharge_max:
            events.extend(self._auto_load_shed(state, p_gen + p_discharge_max, p_load))
            p_load = self._compute_load_kw(state.ship.systems.values())
            state.ship.power.p_load_kw = p_load

        self._apply_degradation(state, dt, power_quality)
        self._apply_radiation(state, dt)

        events.extend(self._update_alerts(state, p_load, p_gen, power_quality))

        for event in events:
            self._record_event(state.events, event)

        self._update_alert_timers(state.events, dt)

        return events

    def apply_action(self, state: GameState, action: Action) -> list[Event]:
        if isinstance(action, Status):
            return []

        if isinstance(action, Diag):
            return []

        if isinstance(action, PowerShed):
            system = state.ship.systems.get(action.system_id)
            if not system:
                return []
            if system.state != SystemState.OFFLINE:
                old_state = system.state
                system.state = SystemState.OFFLINE
                event = self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Manual power shed: {system.system_id} -> OFFLINE",
                    data={"from": old_state.value, "to": system.state.value},
                )
                self._record_event(state.events, event)
                return [event]
            return []

        if isinstance(action, DroneDeploy):
            return self._enqueue_job(
                state,
                JobType.DEPLOY_DRONE,
                TargetRef(kind="ship_sector", id=action.sector_id),
                owner_id=action.drone_id,
                eta_s=self._DEPLOY_TIME_S,
                params={"drone_id": action.drone_id},
            )

        if isinstance(action, Repair):
            return self._enqueue_job(
                state,
                JobType.REPAIR_SYSTEM,
                TargetRef(kind="ship_system", id=action.system_id),
                owner_id=action.drone_id,
                eta_s=self._REPAIR_TIME_S,
                params={"drone_id": action.drone_id},
            )

        if isinstance(action, Boot):
            system = self._find_system_by_service(state.ship.systems.values(), action.service_name)
            if not system or not system.service or not system.service.is_installed:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Boot blocked: service {action.service_name} not installed",
                )
                self._record_event(state.events, event)
                return [event]
            if system.service.is_running:
                return []
            if self._dependencies_blocked(state.ship.systems, system.dependencies):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Boot blocked: unmet dependencies for {action.service_name}",
                )
                self._record_event(state.events, event)
                return [event]

            return self._enqueue_job(
                state,
                JobType.BOOT_SERVICE,
                TargetRef(kind="service", id=action.service_name),
                owner_id=None,
                eta_s=system.service.boot_time_s,
                params={"system_id": system.system_id},
            )

        return []

    def _process_jobs(self, state: GameState, dt: float) -> list[Event]:
        events: list[Event] = []
        jobs_state = state.jobs
        completed: list[str] = []

        for job_id in list(jobs_state.active_job_ids):
            job = jobs_state.jobs.get(job_id)
            if not job or job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED):
                completed.append(job_id)
                continue
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.RUNNING

            job.eta_s -= dt
            if job.eta_s <= 0:
                job.status = JobStatus.COMPLETED
                completed.append(job_id)
                events.extend(self._apply_job_effect(state, job))

        for job_id in completed:
            if job_id in jobs_state.active_job_ids:
                jobs_state.active_job_ids.remove(job_id)

        return events

    def _apply_job_effect(self, state: GameState, job: Job) -> list[Event]:
        events: list[Event] = []
        if job.job_type == JobType.REPAIR_SYSTEM and job.target:
            system = state.ship.systems.get(job.target.id)
            if system:
                system.health = 1.0
                if system.state in (SystemState.DAMAGED, SystemState.CRITICAL):
                    system.state = SystemState.NOMINAL
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="ship_system", id=system.system_id),
                        f"Repair completed for {system.system_id}",
                        data={"job_id": job.job_id},
                    )
                )
            return events

        if job.job_type == JobType.BOOT_SERVICE and job.target:
            system_id = job.params.get("system_id")
            system = state.ship.systems.get(system_id) if system_id else None
            if system and system.service:
                system.service.is_running = True
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="ship_system", id=system.system_id),
                        f"Service booted: {system.service.service_name}",
                        data={"job_id": job.job_id},
                    )
                )
            return events

        if job.job_type == JobType.DEPLOY_DRONE and job.target:
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.status = DroneStatus.DEPLOYED
                drone.location = DroneLocation(kind="ship_sector", id=job.target.id)
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Drone deployed to {job.target.id}",
                        data={"job_id": job.job_id},
                    )
                )
            return events

        return events

    def _compute_load_kw(self, systems: Iterable[ShipSystem]) -> float:
        return sum(system.p_effective_kw() for system in systems if system.state != SystemState.OFFLINE)

    def _auto_load_shed(self, state: GameState, p_capacity: float, p_load: float) -> list[Event]:
        events: list[Event] = []
        systems_sorted = sorted(
            state.ship.systems.values(),
            key=lambda s: s.priority,
            reverse=True,
        )
        for system in systems_sorted:
            if p_load <= p_capacity:
                break
            if system.state == SystemState.OFFLINE:
                continue
            prev_load = system.p_effective_kw()
            old_state = system.state
            system.state = SystemState.OFFLINE
            p_load -= prev_load
            events.append(
                self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Load shedding: {system.system_id} -> OFFLINE",
                    data={"from": old_state.value, "to": system.state.value},
                )
            )
        return events

    def _apply_degradation(self, state: GameState, dt: float, power_quality: float) -> None:
        r_env = state.ship.radiation_env_rad_per_s
        r_env_norm = self._clamp(r_env / self._R_REF)
        for system in state.ship.systems.values():
            s_factor = 1.0 + system.k_power * (1.0 - power_quality) + system.k_rad * r_env_norm
            system.health = max(0.0, system.health - system.base_decay_per_s * s_factor * dt)

    def _apply_radiation(self, state: GameState, dt: float) -> None:
        r_env = state.ship.radiation_env_rad_per_s
        for drone in state.ship.drones.values():
            drone.dose_rad += r_env * drone.shield_factor * dt

    def _update_alerts(self, state: GameState, p_load: float, p_gen: float, power_quality: float) -> list[Event]:
        events: list[Event] = []
        active_keys: set[str] = set()

        if p_load > p_gen:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.POWER_NET_DEFICIT,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Power deficit detected",
                )
            )
            active_keys.add(EventType.POWER_NET_DEFICIT.value)

        power_core = state.ship.systems.get("power_core")
        if power_core and power_core.state in (SystemState.DAMAGED, SystemState.CRITICAL):
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.POWER_CORE_DEGRADED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=power_core.system_id),
                    "Power core degraded",
                )
            )
            active_keys.add(EventType.POWER_CORE_DEGRADED.value)

        distribution = state.ship.systems.get("energy_distribution")
        if (
            distribution
            and distribution.state in (SystemState.DAMAGED, SystemState.CRITICAL)
            and state.clock.t >= self._BUS_INSTABILITY_AFTER_S
        ):
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.POWER_BUS_INSTABILITY,
                    Severity.CRITICAL,
                    SourceRef(kind="ship_system", id=distribution.system_id),
                    "Power bus instability due to damaged distribution",
                )
            )
            active_keys.add(EventType.POWER_BUS_INSTABILITY.value)

        if power_quality < self._LOW_POWER_QUALITY_THRESHOLD:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.LOW_POWER_QUALITY,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Low power quality",
                    data={"power_quality": power_quality},
                )
            )
            active_keys.add(EventType.LOW_POWER_QUALITY.value)

        for alert in state.events.alerts.values():
            if alert.alert_key not in active_keys:
                alert.is_active = False

        return events

    def _ensure_alert(
        self,
        state: GameState,
        event_type: EventType,
        severity: Severity,
        source: SourceRef,
        message: str,
        data: dict | None = None,
    ) -> list[Event]:
        events: list[Event] = []
        key = event_type.value
        alert = state.events.alerts.get(key)
        if alert and alert.is_active:
            alert.last_seen_t = state.clock.t
            if severity == Severity.CRITICAL:
                alert.severity = Severity.CRITICAL
            if data:
                alert.data.update(data)
            return events

        event = self._make_event(state, event_type, severity, source, message, data=data)
        events.append(event)

        state.events.alerts[key] = AlertState(
            alert_key=key,
            severity=severity,
            first_seen_t=state.clock.t,
            last_seen_t=state.clock.t,
            data=data or {},
            is_active=True,
        )
        return events

    def _update_alert_timers(self, events: EventManagerState, dt: float) -> None:
        inc = int(dt)
        if inc <= 0:
            return
        for alert in events.alerts.values():
            if alert.is_active and not alert.data.get("acknowledged", False):
                alert.unacked_s += inc

    def _record_event(self, events: EventManagerState, event: Event) -> None:
        events.recent.append(event)
        if len(events.recent) > self._MAX_RECENT_EVENTS:
            events.recent.pop(0)

    def _make_event(
        self,
        state: GameState,
        event_type: EventType,
        severity: Severity,
        source: SourceRef,
        message: str,
        data: dict | None = None,
    ) -> Event:
        seq = state.events.next_event_seq
        state.events.next_event_seq += 1
        return Event(
            event_id=f"E{seq:05d}",
            t=state.clock.t,
            type=event_type,
            severity=severity,
            source=source,
            message=message,
            data=data or {},
        )

    def _enqueue_job(
        self,
        state: GameState,
        job_type: JobType,
        target: TargetRef,
        owner_id: str | None,
        eta_s: float,
        params: dict,
    ) -> list[Event]:
        job_id = f"J{state.jobs.next_job_seq:05d}"
        state.jobs.next_job_seq += 1
        job = Job(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            eta_s=eta_s,
            owner_id=owner_id,
            target=target,
            params=params,
        )
        state.jobs.jobs[job_id] = job
        state.jobs.active_job_ids.append(job_id)
        return []

    def _find_system_by_service(
        self, systems: Iterable[ShipSystem], service_name: str
    ) -> ShipSystem | None:
        for system in systems:
            if system.service and system.service.service_name == service_name:
                return system
        return None

    def _dependencies_blocked(
        self, systems: dict[str, ShipSystem], dependencies: list[Dependency]
    ) -> bool:
        for dep in dependencies:
            if dep.dep_type != "system_state_at_least":
                continue
            target = systems.get(dep.target_id)
            if not target:
                return True
            required = self._state_rank(SystemState(dep.value))
            if self._state_rank(target.state) < required:
                return True
        return False

    def _state_rank(self, state: SystemState) -> int:
        order = {
            SystemState.OFFLINE: 0,
            SystemState.CRITICAL: 1,
            SystemState.DAMAGED: 2,
            SystemState.LIMITED: 3,
            SystemState.NOMINAL: 4,
            SystemState.UPGRADED: 5,
        }
        return order[state]

    def _clamp(self, value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value
