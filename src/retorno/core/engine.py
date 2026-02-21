from __future__ import annotations

import random
from typing import Iterable
import difflib
import math

from retorno.core.actions import (
    Action,
    Boot,
    Diag,
    Dock,
    DroneDeploy,
    DroneMove,
    DroneReboot,
    DroneRecall,
    Hibernate,
    CargoAudit,
    Install,
    PowerPlan,
    PowerShed,
    SystemOn,
    Repair,
    SelfTestRepair,
    Salvage,
    SalvageModule,
    SalvageScrap,
    Status,
    Travel,
)
from retorno.core.gamestate import GameState
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import AlertState, Event, EventManagerState, EventType, Severity, SourceRef
from retorno.model.jobs import Job, JobManagerState, JobStatus, JobType, RiskProfile, TargetRef
from retorno.runtime.data_loader import load_modules
from retorno.model.systems import Dependency, ShipSystem, SystemState
from retorno.config.balance import Balance


class Engine:
    _MAX_RECENT_EVENTS = 50

    def tick(self, state: GameState, dt: float) -> list[Event]:
        if dt <= 0:
            return []

        state.clock.last_dt = dt
        state.clock.t += dt

        events: list[Event] = []

        if state.ship.in_transit and state.clock.t >= state.ship.arrival_t:
            state.ship.in_transit = False
            state.ship.current_node_id = state.ship.transit_to or state.ship.current_node_id
            state.world.current_node_id = state.ship.current_node_id
            events.append(
                self._make_event(
                    state,
                    EventType.ARRIVED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Arrived at {state.ship.current_node_id}",
                    data={
                        "from": state.ship.transit_from,
                        "to": state.ship.transit_to,
                        "distance_ly": state.ship.last_travel_distance_ly,
                    },
                )
            )

        events.extend(self._process_jobs(state, dt))

        p_load = self._compute_load_kw(state)
        p_gen = state.ship.power.p_gen_kw
        p_discharge_max = state.ship.power.p_discharge_max_kw

        if p_load > p_gen + p_discharge_max:
            events.extend(self._auto_load_shed(state, p_gen + p_discharge_max, p_load))
            p_load = self._compute_load_kw(state.ship.systems.values())

        state.ship.power.p_load_kw = p_load

        self._update_battery(state, dt, p_gen, p_load)
        power_quality = self._compute_power_quality(state, p_gen, p_load)
        state.ship.power.power_quality = power_quality

        events.extend(self._apply_degradation(state, dt, power_quality))
        self._apply_radiation(state, dt)
        self._update_drone_maintenance(state, dt)

        events.extend(self._update_alerts(state, p_load, p_gen, power_quality))

        for event in events:
            self._record_event(state.events, event)

        self._update_alert_timers(state.events, dt)

        return events

    def apply_action(self, state: GameState, action: Action) -> list[Event]:
        if isinstance(action, Status):
            return []

        if isinstance(action, Diag):
            if state.ship.in_transit:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Action blocked: ship in transit",
                    data={"message_key": "boot_blocked", "reason": "in_transit"},
                )
                self._record_event(state.events, event)
                return [event]
            return []

        if isinstance(action, Travel):
            if state.ship.in_transit:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel blocked: ship already in transit",
                    data={"message_key": "boot_blocked", "reason": "in_transit"},
                )
                self._record_event(state.events, event)
                return [event]
            target = state.world.space.nodes.get(action.node_id)
            if not target:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Travel blocked: node {action.node_id} not found",
                    data={"message_key": "boot_blocked", "reason": "node_missing", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            current_id = state.world.current_node_id
            if action.node_id == current_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel blocked: already at destination",
                    data={"message_key": "boot_blocked", "reason": "already_at_target", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            distance_ly = self._distance_between_nodes(state, current_id, action.node_id)
            speed = max(0.001, state.ship.cruise_speed_ly_per_year)
            years = distance_ly / speed
            travel_s = years * Balance.YEAR_S
            state.ship.in_transit = True
            state.ship.transit_from = current_id
            state.ship.transit_to = action.node_id
            state.ship.arrival_t = state.clock.t + travel_s
            state.ship.last_travel_distance_ly = distance_ly
            state.world.known_contacts.add(action.node_id)
            state.ship.op_mode = "CRUISE"
            event = self._make_event(
                state,
                EventType.TRAVEL_STARTED,
                Severity.INFO,
                SourceRef(kind="ship", id=state.ship.ship_id),
                f"Travel started to {action.node_id} ETA {years:.2f}y",
                data={
                    "from": current_id,
                    "to": action.node_id,
                    "distance_ly": distance_ly,
                    "eta_years": years,
                    "arrival_t": state.ship.arrival_t,
                },
            )
            self._record_event(state.events, event)
            return [event]

        if isinstance(action, Hibernate):
            return []

        if isinstance(action, PowerPlan):
            events: list[Event] = []
            targets = ["sensors", "security", "data_core", "drone_bay"]
            if action.mode == "cruise":
                state.ship.op_mode = "CRUISE"
                for sid in targets:
                    sys = state.ship.systems.get(sid)
                    if not sys:
                        continue
                    old_state = sys.state
                    sys.forced_offline = True
                    if sys.state != SystemState.OFFLINE:
                        sys.state = SystemState.OFFLINE
                        if sys.service:
                            sys.service.is_running = False
                        events.append(
                            self._make_event(
                                state,
                                EventType.SYSTEM_STATE_CHANGED,
                                Severity.WARN,
                                SourceRef(kind="ship_system", id=sys.system_id),
                                f"Power plan cruise: {sys.system_id} -> OFFLINE",
                                data={"from": old_state.value, "to": sys.state.value, "cause": "manual_shed"},
                            )
                        )
                return events
            if action.mode == "normal":
                state.ship.op_mode = "NORMAL"
                for sid in targets:
                    sys = state.ship.systems.get(sid)
                    if not sys:
                        continue
                    sys.forced_offline = False
                for sid in targets:
                    sys = state.ship.systems.get(sid)
                    if not sys:
                        continue
                    self._apply_health_state(sys, state, events, cause="plan_normal")
                return events
            return []

        if state.ship.in_transit:
            event = self._make_event(
                state,
                EventType.BOOT_BLOCKED,
                Severity.WARN,
                SourceRef(kind="ship", id=state.ship.ship_id),
                "Action blocked: ship in transit",
                data={"message_key": "boot_blocked", "reason": "in_transit"},
            )
            self._record_event(state.events, event)
            return [event]

        if isinstance(action, Dock):
            node = state.world.space.nodes.get(action.node_id)
            if not node:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Dock blocked: node {action.node_id} not found",
                    data={"message_key": "boot_blocked", "reason": "node_missing", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if action.node_id != state.world.current_node_id and action.node_id not in state.world.known_contacts:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Dock blocked: unknown contact {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "unknown_contact", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            events = self._enqueue_job(
                state,
                JobType.DOCK,
                TargetRef(kind="world_node", id=action.node_id),
                owner_id=None,
                eta_s=Balance.DOCK_TIME_S,
                params={"node_id": action.node_id},
            )
            return events

        if isinstance(action, Install):
            if action.module_id not in state.ship.cargo_modules:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Install blocked: module {action.module_id} not in inventory",
                    data={"message_key": "boot_blocked", "reason": "module_missing", "module_id": action.module_id},
                )
                self._record_event(state.events, event)
                return [event]
            modules = load_modules()
            if action.module_id not in modules:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Install blocked: unknown module {action.module_id}",
                    data={"message_key": "boot_blocked", "reason": "module_unknown", "module_id": action.module_id},
                )
                self._record_event(state.events, event)
                return [event]
            scrap_cost = int(modules[action.module_id].get("scrap_cost", 0))
            if state.ship.cargo_scrap < scrap_cost:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Install blocked: insufficient scrap ({state.ship.cargo_scrap}/{scrap_cost})",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "scrap_insufficient",
                        "module_id": action.module_id,
                        "scrap_cost": scrap_cost,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.INSTALL_MODULE,
                TargetRef(kind="ship", id=state.ship.ship_id),
                owner_id=None,
                eta_s=Balance.INSTALL_TIME_S,
                params={"module_id": action.module_id, "scrap_cost": scrap_cost},
            )

        if isinstance(action, CargoAudit):
            system = state.ship.systems.get("data_core")
            if not system:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="data_core"),
                    "Cargo audit blocked: data_core missing",
                    data={"message_key": "boot_blocked", "reason": "cargo_audit_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if system.forced_offline or system.state == SystemState.OFFLINE:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Cargo audit blocked: data_core offline (CRUISE plan may have shed it). Try: power plan normal",
                    data={"message_key": "boot_blocked", "reason": "cargo_audit_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if not system.service or system.service.service_name != "datad":
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Cargo audit blocked: datad not installed",
                    data={"message_key": "boot_blocked", "reason": "cargo_audit_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if not system.service.is_running:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Cargo audit blocked: datad not running. Try: boot datad",
                    data={"message_key": "boot_blocked", "reason": "cargo_audit_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if self._state_rank(system.state) < self._state_rank(SystemState.LIMITED):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Cargo audit blocked: data_core degraded (requires >= limited).",
                    data={"message_key": "boot_blocked", "reason": "cargo_audit_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.CARGO_AUDIT,
                TargetRef(kind="ship", id=state.ship.ship_id),
                owner_id=None,
                eta_s=Balance.CARGO_AUDIT_TIME_S,
                params={},
            )

        if isinstance(action, PowerShed):
            system = state.ship.systems.get(action.system_id)
            if not system:
                return []
            if system.state != SystemState.OFFLINE:
                old_state = system.state
                system.state = SystemState.OFFLINE
                system.forced_offline = True
                event = self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Manual power shed: {system.system_id} -> OFFLINE",
                    data={"from": old_state.value, "to": system.state.value, "cause": "manual_shed"},
                )
                self._record_event(state.events, event)
                return [event]
            system.forced_offline = True
            return []

        if isinstance(action, SystemOn):
            system = state.ship.systems.get(action.system_id)
            if not system:
                return []
            if system.health <= 0.0 or (system.state == SystemState.OFFLINE and not system.forced_offline):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"System on blocked: {system.system_id} too damaged",
                    data={"message_key": "boot_blocked", "reason": "system_too_damaged"},
                )
                self._record_event(state.events, event)
                return [event]
            if system.forced_offline:
                system.forced_offline = False
                events: list[Event] = []
                self._apply_health_state(system, state, events, cause="manual_restore")
                for event in events:
                    self._record_event(state.events, event)
                restored = self._make_event(
                    state,
                    EventType.SYSTEM_POWER_RESTORED,
                    Severity.INFO,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Manual power restored: {system.system_id}",
                    data={
                        "from": SystemState.OFFLINE.value,
                        "to": system.state.value,
                        "cause": "manual_restore",
                        "health": system.health,
                        "message_key": "system_power_restored",
                    },
                )
                self._record_event(state.events, restored)
                events.append(restored)
                return events
            return []

        if isinstance(action, DroneDeploy):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Drone deploy blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status == DroneStatus.DEPLOYED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone deploy blocked: {drone.drone_id} already deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_already_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status == DroneStatus.DISABLED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone deploy blocked: {drone.drone_id} disabled",
                    data={"message_key": "boot_blocked", "reason": "drone_disabled", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.integrity < Balance.DRONE_DEPLOY_MIN_INTEGRITY:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone deploy blocked: {drone.drone_id} integrity too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_too_damaged",
                        "drone_id": drone.drone_id,
                        "integrity": drone.integrity,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DOCKED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone deploy blocked: {drone.drone_id} not docked",
                    data={"message_key": "boot_blocked", "reason": "drone_not_docked", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            target_kind = "ship_sector"
            target_id = action.sector_id
            if action.sector_id in state.world.space.nodes:
                if state.world.current_node_id != action.sector_id:
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="world", id=action.sector_id),
                        f"Drone deploy blocked: ship not docked at {action.sector_id}",
                        data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": action.sector_id},
                    )
                    self._record_event(state.events, event)
                    return [event]
                target_kind = "world_node"
                target_id = action.sector_id
            drone_bay = state.ship.systems.get("drone_bay")
            if not drone_bay or drone_bay.state == SystemState.OFFLINE or drone_bay.forced_offline:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="drone_bay"),
                    "Drone deploy blocked: drone bay offline",
                    data={"message_key": "boot_blocked", "reason": "drone_bay_offline"},
                )
                self._record_event(state.events, event)
                return [event]
            if self._dependencies_blocked(state.ship.systems, drone_bay.dependencies):
                if not action.emergency:
                    dep_detail = self._first_unmet_dependency(state.ship.systems, drone_bay.dependencies)
                    if dep_detail:
                        dep_target, dep_required, dep_current = dep_detail
                        msg = (
                            f"Drone deploy blocked: drone_bay requires {dep_target}>={dep_required} "
                            f"(current={dep_current}). Use deploy! for emergency override."
                        )
                        data = {
                            "message_key": "boot_blocked",
                            "reason": "drone_bay_deps_unmet",
                            "system_id": "drone_bay",
                            "dep_target": dep_target,
                            "dep_required": dep_required,
                            "dep_current": dep_current,
                        }
                    else:
                        msg = "Drone deploy blocked: drone bay dependencies unmet"
                        data = {"message_key": "boot_blocked", "reason": "drone_bay_deps_unmet", "system_id": "drone_bay"}
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="ship_system", id="drone_bay"),
                        msg,
                        data=data,
                    )
                    self._record_event(state.events, event)
                    return [event]
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="drone_bay"),
                    "Emergency override: deploying despite unmet dependencies. Risk of failure and drone damage.",
                    data={"emergency": True, "message_key": "boot_blocked", "reason": "emergency_override"},
                )
                self._record_event(state.events, event)
                return self._enqueue_job(
                    state,
                    JobType.DEPLOY_DRONE,
                    TargetRef(kind=target_kind, id=target_id),
                    owner_id=action.drone_id,
                    eta_s=Balance.DEPLOY_TIME_S,
                    params={"drone_id": action.drone_id, "emergency": True},
                    risk=RiskProfile(
                        p_glitch_per_s=Balance.EMERGENCY_DEPLOY_P_GLITCH_PER_S,
                        p_fail_per_s=Balance.EMERGENCY_DEPLOY_P_FAIL_PER_S,
                    ),
                )

            return self._enqueue_job(
                state,
                JobType.DEPLOY_DRONE,
                TargetRef(kind=target_kind, id=target_id),
                owner_id=action.drone_id,
                eta_s=Balance.DEPLOY_TIME_S,
                params={"drone_id": action.drone_id},
            )

        if isinstance(action, DroneMove):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Drone move blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DEPLOYED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone move blocked: {drone.drone_id} not deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_not_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.integrity < Balance.DRONE_MOVE_MIN_INTEGRITY:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone move blocked: {drone.drone_id} integrity too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_too_damaged",
                        "drone_id": drone.drone_id,
                        "integrity": drone.integrity,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            target_kind = None
            target_id = action.target_id
            if target_id in state.ship.sectors:
                if drone.location.kind != "ship_sector":
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Drone move blocked: {drone.drone_id} not on ship",
                        data={"message_key": "boot_blocked", "reason": "not_on_ship", "drone_id": drone.drone_id},
                    )
                    self._record_event(state.events, event)
                    return [event]
                target_kind = "ship_sector"
            elif target_id in state.world.space.nodes:
                if state.world.current_node_id != target_id:
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="world", id=target_id),
                        f"Drone move blocked: ship not docked at {target_id}",
                        data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": target_id},
                    )
                    self._record_event(state.events, event)
                    return [event]
                target_kind = "world_node"
            else:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Drone move blocked: target {target_id} not found",
                    data={"message_key": "boot_blocked", "reason": "target_missing", "target_id": target_id},
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.MOVE_DRONE,
                TargetRef(kind=target_kind, id=target_id),
                owner_id=drone.drone_id,
                eta_s=Balance.DEPLOY_TIME_S,
                params={"drone_id": drone.drone_id},
            )

        if isinstance(action, DroneReboot):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Reboot blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DISABLED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Reboot blocked: drone {drone.drone_id} not disabled",
                    data={"message_key": "boot_blocked", "reason": "drone_not_disabled", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.REBOOT_DRONE,
                TargetRef(kind="drone", id=drone.drone_id),
                owner_id=drone.drone_id,
                eta_s=Balance.REBOOT_TIME_S,
                params={"drone_id": drone.drone_id},
            )

        if isinstance(action, DroneRecall):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Recall blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DEPLOYED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Recall blocked: {drone.drone_id} not deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_not_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.integrity < Balance.DRONE_RECALL_MIN_INTEGRITY:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Recall blocked: {drone.drone_id} integrity too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_too_damaged",
                        "drone_id": drone.drone_id,
                        "integrity": drone.integrity,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if drone.location.kind == "world_node":
                if state.world.current_node_id != drone.location.id:
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Recall blocked: ship not docked at {drone.location.id}",
                        data={"message_key": "boot_blocked", "reason": "recall_not_docked", "node_id": drone.location.id},
                    )
                    self._record_event(state.events, event)
                return [event]
            if drone.integrity < Balance.DRONE_RECALL_MIN_INTEGRITY:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Recall blocked: {drone.drone_id} integrity too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_too_damaged",
                        "drone_id": drone.drone_id,
                        "integrity": drone.integrity,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.RECALL_DRONE,
                TargetRef(kind="drone", id=drone.drone_id),
                owner_id=drone.drone_id,
                eta_s=Balance.RECALL_TIME_S,
                params={"drone_id": drone.drone_id},
            )

        if isinstance(action, Repair):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Repair blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DEPLOYED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Repair blocked: {drone.drone_id} not deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_not_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            target_system = state.ship.systems.get(action.system_id)
            if not target_system:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=action.system_id),
                    f"Repair blocked: system {action.system_id} not found",
                    data={"message_key": "boot_blocked", "reason": "system_missing", "system_id": action.system_id},
                )
                self._record_event(state.events, event)
                return [event]

            params = {"drone_id": action.drone_id}
            if action.system_id == "energy_distribution":
                params["repair_amount"] = 0.25
            return self._enqueue_job(
                state,
                JobType.REPAIR_SYSTEM,
                TargetRef(kind="ship_system", id=action.system_id),
                owner_id=action.drone_id,
                eta_s=Balance.REPAIR_TIME_S,
                params=params,
            )

        if isinstance(action, SelfTestRepair):
            system = state.ship.systems.get(action.system_id)
            if not system:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=action.system_id),
                    f"Repair blocked: system {action.system_id} not found",
                    data={"message_key": "boot_blocked", "reason": "system_missing", "system_id": action.system_id},
                )
                self._record_event(state.events, event)
                return [event]
            if not self._has_unlock(state, "selftest_repair"):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Repair blocked: self-test rig not installed",
                    data={"message_key": "boot_blocked", "reason": "selftest_not_available"},
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.SELFTEST_REPAIR,
                TargetRef(kind="ship_system", id=action.system_id),
                owner_id=None,
                eta_s=Balance.SELFTEST_REPAIR_TIME_S,
                params={"system_id": action.system_id},
            )

        if isinstance(action, SalvageScrap):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Salvage blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DEPLOYED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_not_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            node_id = action.node_id or self._drone_world_node(drone)
            if not node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not at a node",
                    data={"message_key": "boot_blocked", "reason": "not_docked", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            node = state.world.space.nodes.get(node_id)
            if not node:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: node {node_id} not found",
                    data={"message_key": "boot_blocked", "reason": "node_missing", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.location.kind != "world_node" or drone.location.id != node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not at node {node_id}",
                    data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if state.world.current_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: ship not docked at {node_id}",
                    data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if action.amount <= 0:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    "Salvage blocked: amount must be > 0",
                    data={"message_key": "boot_blocked", "reason": "invalid_amount", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            effective = min(action.amount, node.salvage_scrap_available)
            if effective <= 0:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    "No scrap available",
                    data={"message_key": "boot_blocked", "reason": "scrap_empty", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            eta = Balance.SALVAGE_SCRAP_BASE_S + Balance.SALVAGE_SCRAP_PER_UNIT_S * effective
            return self._enqueue_job(
                state,
                JobType.SALVAGE_SCRAP,
                TargetRef(kind="world_node", id=node_id),
                owner_id=action.drone_id,
                eta_s=eta,
                params={
                    "node_id": node_id,
                    "requested": action.amount,
                    "effective": effective,
                    "available": node.salvage_scrap_available,
                    "drone_id": action.drone_id,
                },
            )

        if isinstance(action, SalvageModule):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Salvage blocked: drone {action.drone_id} not found",
                    data={"message_key": "boot_blocked", "reason": "drone_missing", "drone_id": action.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.status != DroneStatus.DEPLOYED:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_not_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            node_id = action.node_id or self._drone_world_node(drone)
            if not node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not at a node",
                    data={"message_key": "boot_blocked", "reason": "not_docked", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            node = state.world.space.nodes.get(node_id)
            if not node:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: node {node_id} not found",
                    data={"message_key": "boot_blocked", "reason": "node_missing", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.location.kind != "world_node" or drone.location.id != node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not at node {node_id}",
                    data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if state.world.current_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: ship not docked at {node_id}",
                    data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            eta = Balance.SALVAGE_MODULE_TIME_S
            return self._enqueue_job(
                state,
                JobType.SALVAGE_MODULE,
                TargetRef(kind="world_node", id=node_id),
                owner_id=action.drone_id,
                eta_s=eta,
                params={"node_id": node_id, "drone_id": action.drone_id},
            )

        if isinstance(action, Boot):
            service_name = action.service_name
            if service_name == "sensors":
                service_name = "sensord"
            system = self._find_system_by_service(state.ship.systems.values(), service_name)
            if not system or not system.service or not system.service.is_installed:
                available_list = self._available_services(state)
                available = ", ".join(available_list)
                suggestion = self._suggest_service(service_name, available_list)
                suffix = f" Did you mean '{suggestion}'?" if suggestion else ""
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Unknown service '{action.service_name}'. Available: {available}.{suffix}",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "service_missing",
                        "service": action.service_name,
                        "available": available,
                        "suggestion": suggestion or "",
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if system.service.is_running:
                return []
            if self._dependencies_blocked(state.ship.systems, system.dependencies):
                dep_detail = self._first_unmet_dependency(state.ship.systems, system.dependencies)
                if dep_detail:
                    dep_target, dep_required, dep_current = dep_detail
                    msg = (
                        f"Boot blocked: {service_name} requires {dep_target}>={dep_required} "
                        f"(current={dep_current})"
                    )
                    data = {
                        "message_key": "boot_blocked",
                        "reason": "deps_unmet",
                        "service": service_name,
                        "dep_target": dep_target,
                        "dep_required": dep_required,
                        "dep_current": dep_current,
                    }
                else:
                    msg = f"Boot blocked: unmet dependencies for {service_name}"
                    data = {
                        "message_key": "boot_blocked",
                        "reason": "deps_unmet",
                        "service": service_name,
                        "dep_target": "unknown",
                        "dep_required": "unknown",
                        "dep_current": "unknown",
                    }
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    msg,
                    data=data,
                )
                self._record_event(state.events, event)
                return [event]

            return self._enqueue_job(
                state,
                JobType.BOOT_SERVICE,
                TargetRef(kind="service", id=service_name),
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
            if job.params.get("emergency"):
                failed_event = self._maybe_fail_emergency_job(state, job, dt)
                if failed_event:
                    events.append(failed_event)
                    completed.append(job_id)
                    continue

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
        if job.job_type == JobType.SELFTEST_REPAIR and job.target:
            system = state.ship.systems.get(job.target.id)
            if system:
                system.health = min(1.0, system.health + Balance.SELFTEST_REPAIR_AMOUNT)
                self._apply_health_state(system, state, events, cause="selftest")
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="ship_system", id=system.system_id),
                        f"Self-test repair completed: {system.system_id}",
                        data={
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "message_key": "job_completed_selftest",
                        },
                    )
                )
            return events
        if job.job_type == JobType.REPAIR_SYSTEM and job.target:
            system = state.ship.systems.get(job.target.id)
            if system:
                drone_id = job.params.get("drone_id")
                drone = state.ship.drones.get(drone_id) if drone_id else None
                if drone:
                    drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_REPAIR)
                default_repair = 0.25 if system.system_id == "energy_distribution" else 0.15
                repair_amount = float(job.params.get("repair_amount", default_repair))
                system.health = min(1.0, system.health + repair_amount)
                if system.system_id == "energy_distribution":
                    system.state_locked = False
                self._apply_health_state(system, state, events, cause="repair")
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="ship_system", id=system.system_id),
                        f"Repair completed for {system.system_id}",
                        data={
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "system_id": system.system_id,
                            "message_key": "job_completed_repair",
                        },
                    )
                )
            return events

        if job.job_type == JobType.BOOT_SERVICE and job.target:
            system_id = job.params.get("system_id")
            system = state.ship.systems.get(system_id) if system_id else None
            if system and system.service:
                system.service.is_running = True
                if system.state_locked:
                    system.state_locked = False
                if not system.forced_offline:
                    self._apply_health_state(system, state, events, cause="boot")
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="ship_system", id=system.system_id),
                        f"Service booted: {system.service.service_name}",
                        data={
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "service": system.service.service_name,
                            "message_key": "job_completed_boot",
                        },
                    )
                )
                if system.service.service_name == "sensord":
                    if "ECHO_7" not in state.world.known_contacts:
                        state.world.known_contacts.add("ECHO_7")
                        events.append(
                            self._make_event(
                                state,
                                EventType.SIGNAL_DETECTED,
                                Severity.INFO,
                                SourceRef(kind="ship_system", id=system.system_id),
                                "Signal detected: ECHO-7",
                                data={"contact_id": "ECHO_7", "message_key": "signal_detected"},
                            )
                        )
            return events

        if job.job_type == JobType.DEPLOY_DRONE and job.target:
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.status = DroneStatus.DEPLOYED
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_DEPLOY)
                if job.target.kind == "world_node":
                    drone.location = DroneLocation(kind="world_node", id=job.target.id)
                else:
                    drone.location = DroneLocation(kind="ship_sector", id=job.target.id)
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Drone deployed to {job.target.id}",
                        data={
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "drone_id": drone.drone_id,
                            "sector_id": job.target.id,
                            "message_key": "job_completed_deploy",
                        },
                    )
                )
            return events

        if job.job_type == JobType.MOVE_DRONE and job.target:
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                if job.target.kind == "world_node":
                    drone.location = DroneLocation(kind="world_node", id=job.target.id)
                else:
                    drone.location = DroneLocation(kind="ship_sector", id=job.target.id)
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_MOVE)
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Drone moved to {job.target.id}",
                        data={
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "drone_id": drone.drone_id,
                            "sector_id": job.target.id,
                            "message_key": "job_completed_move",
                        },
                    )
                )
            return events

        if job.job_type == JobType.REBOOT_DRONE and job.target:
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                rng = self._job_rng(state, job)
                integrity = drone.integrity
                p_success = self._clamp(integrity, Balance.DRONE_REBOOT_P_MIN, Balance.DRONE_REBOOT_P_MAX)
                if rng.random() < p_success:
                    drone.status = DroneStatus.DOCKED
                    drone.location = DroneLocation(kind="ship_sector", id="drone_bay")
                    drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_RECALL)
                    drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_REBOOT)
                    events.append(
                        self._make_event(
                            state,
                            EventType.JOB_COMPLETED,
                            Severity.INFO,
                            SourceRef(kind="drone", id=drone.drone_id),
                            f"Drone rebooted: {drone.drone_id}",
                            data={
                                "job_id": job.job_id,
                                "job_type": job.job_type.value,
                                "drone_id": drone.drone_id,
                                "message_key": "job_completed_reboot",
                            },
                        )
                    )
                else:
                    job.status = JobStatus.FAILED
                    events.append(
                        self._make_event(
                            state,
                            EventType.JOB_FAILED,
                            Severity.WARN,
                            SourceRef(kind="drone", id=drone.drone_id),
                            f"Drone reboot failed: {drone.drone_id}",
                            data={
                                "job_id": job.job_id,
                                "job_type": job.job_type.value,
                                "drone_id": drone.drone_id,
                                "message_key": "job_failed_reboot",
                            },
                        )
                    )
            return events

        if job.job_type == JobType.RECALL_DRONE and job.target:
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                rng = self._rng(state)
                p_success = self._clamp(drone.integrity, Balance.DRONE_RECALL_P_MIN, Balance.DRONE_RECALL_P_MAX)
                if rng.random() < p_success:
                    drone.status = DroneStatus.DOCKED
                    drone.location = DroneLocation(kind="ship_sector", id="drone_bay")
                    events.append(
                        self._make_event(
                            state,
                            EventType.JOB_COMPLETED,
                            Severity.INFO,
                            SourceRef(kind="drone", id=drone.drone_id),
                            f"Drone recalled: {drone.drone_id}",
                            data={
                                "job_id": job.job_id,
                                "job_type": job.job_type.value,
                                "drone_id": drone.drone_id,
                                "message_key": "job_completed_recall",
                            },
                        )
                    )
                else:
                    job.status = JobStatus.FAILED
                    events.append(
                        self._make_event(
                            state,
                            EventType.JOB_FAILED,
                            Severity.WARN,
                            SourceRef(kind="drone", id=drone.drone_id),
                            f"Drone recall failed: {drone.drone_id}",
                            data={
                                "job_id": job.job_id,
                                "job_type": job.job_type.value,
                                "drone_id": drone.drone_id,
                                "message_key": "job_failed_recall",
                            },
                        )
                    )
            return events

        if job.job_type == JobType.DOCK and job.target:
            state.world.current_node_id = job.target.id
            state.ship.current_node_id = job.target.id
            events.append(
                self._make_event(
                    state,
                    EventType.DOCKED,
                    Severity.INFO,
                    SourceRef(kind="world", id=job.target.id),
                    f"Docked at {job.target.id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": job.target.id,
                        "message_key": "docked",
                    },
                )
            )
            return events

        if job.job_type == JobType.SALVAGE_SCRAP and job.target:
            node_id = job.params.get("node_id", job.target.id)
            node = state.world.space.nodes.get(node_id)
            requested = int(job.params.get("requested", 0))
            effective = int(job.params.get("effective", 0))
            recovered = 0
            if node:
                recovered = min(effective, node.salvage_scrap_available)
                node.salvage_scrap_available = max(0, node.salvage_scrap_available - recovered)
            state.ship.cargo_scrap += recovered
            state.ship.manifest_dirty = True
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_SALVAGE)
            events.append(
                self._make_event(
                    state,
                    EventType.SALVAGE_SCRAP_GAINED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage gained: +{recovered} scrap",
                    data={
                        "amount": recovered,
                        "requested": requested,
                        "remaining": node.salvage_scrap_available if node else 0,
                        "node_id": node_id,
                        "message_key": "salvage_scrap_gained",
                    },
                )
            )
            if requested > recovered:
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="world", id=node_id),
                        f"Only {recovered} scrap available; recovered {recovered}",
                        data={"message_key": "salvage_partial", "recovered": recovered, "node_id": node_id},
                    )
                )
            if node and node.salvage_scrap_available == 0 and not node.salvage_dry:
                node.salvage_dry = True
                events.append(
                    self._make_event(
                        state,
                        EventType.NODE_DEPLETED,
                        Severity.INFO,
                        SourceRef(kind="world", id=node_id),
                        "Node depleted",
                        data={"message_key": "salvage_depleted", "node_id": node_id},
                    )
                )
            if node and node.salvage_modules_available:
                rng = self._rng(state)
                if rng.random() < Balance.SALVAGE_SCRAP_FIND_MODULE_P:
                    module_id = rng.choice(node.salvage_modules_available)
                    node.salvage_modules_available.remove(module_id)
                    state.ship.cargo_modules.append(module_id)
                    state.ship.manifest_dirty = True
                    events.append(
                        self._make_event(
                            state,
                            EventType.SALVAGE_MODULE_FOUND,
                            Severity.INFO,
                            SourceRef(kind="world", id=node_id),
                            f"Module found: {module_id}",
                            data={
                                "module_id": module_id,
                                "node_id": node_id,
                                "message_key": "salvage_module_found",
                            },
                        )
                    )
            return events

        if job.job_type == JobType.SALVAGE_MODULE and job.target:
            node_id = job.params.get("node_id", job.target.id)
            node = state.world.space.nodes.get(node_id)
            found = False
            if node and node.salvage_modules_available:
                rng = self._rng(state)
                if rng.random() < Balance.SALVAGE_MODULE_FIND_P:
                    module_id = rng.choice(node.salvage_modules_available)
                    node.salvage_modules_available.remove(module_id)
                    state.ship.cargo_modules.append(module_id)
                    state.ship.manifest_dirty = True
                    events.append(
                        self._make_event(
                            state,
                            EventType.SALVAGE_MODULE_FOUND,
                            Severity.INFO,
                            SourceRef(kind="world", id=node_id),
                            f"Module found: {module_id}",
                            data={
                                "module_id": module_id,
                                "node_id": node_id,
                                "message_key": "salvage_module_found",
                            },
                        )
                    )
                    found = True
            if not found:
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="world", id=node_id),
                        "No modules found",
                        data={"message_key": "salvage_none", "node_id": node_id},
                    )
                )
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_SALVAGE)
            return events

        if job.job_type == JobType.INSTALL_MODULE and job.target:
            module_id = job.params.get("module_id")
            if module_id and module_id in state.ship.cargo_modules:
                modules = load_modules()
                mod = modules.get(module_id, {})
                effects = mod.get("effects", {})
                if "power_quality_offset" in effects:
                    state.ship.power.quality_offset += float(effects["power_quality_offset"])
                if "e_batt_bonus_kwh" in effects:
                    state.ship.power.e_batt_max_kwh += float(effects["e_batt_bonus_kwh"])
                if "p_gen_bonus_kw" in effects:
                    state.ship.power.p_gen_kw += float(effects["p_gen_bonus_kw"])
                scrap_cost = int(job.params.get("scrap_cost", mod.get("scrap_cost", 0)))
                state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - scrap_cost)
                state.ship.cargo_modules.remove(module_id)
                state.ship.manifest_dirty = True
                state.ship.installed_modules.append(module_id)
            events.append(
                self._make_event(
                    state,
                    EventType.JOB_COMPLETED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Module installed: {module_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "module_id": module_id,
                        "message_key": "job_completed_install",
                    },
                )
            )
            events.append(
                self._make_event(
                    state,
                    EventType.MODULE_INSTALLED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Module installed: {module_id}",
                    data={"module_id": module_id, "effects": effects},
                )
            )
            return events

        if job.job_type == JobType.CARGO_AUDIT:
            ship = state.ship
            ship.manifest_scrap = ship.cargo_scrap
            ship.manifest_modules = list(ship.cargo_modules)
            ship.manifest_dirty = False
            ship.manifest_last_sync_t = state.clock.t
            events.append(
                self._make_event(
                    state,
                    EventType.JOB_COMPLETED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=ship.ship_id),
                    "Inventory synchronized",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "message_key": "job_completed_cargo_audit",
                    },
                )
            )
            return events

        return events

    def _compute_load_kw(self, state: GameState) -> float:
        systems = state.ship.systems.values()
        if state.ship.op_mode == "CRUISE":
            cruise_zero = {"sensors", "security", "data_core", "drone_bay"}
            def _factor(sys: ShipSystem) -> float:
                if sys.state == SystemState.OFFLINE:
                    return 0.0
                if "critical" in sys.tags or sys.system_id in {"energy_distribution"}:
                    return 1.0
                if sys.system_id in cruise_zero:
                    return 0.0
                return 0.1
            return sum(sys.p_effective_kw() * _factor(sys) for sys in systems)
        return sum(system.p_effective_kw() for system in systems if system.state != SystemState.OFFLINE)

    def _distance_between_nodes(self, state: GameState, from_id: str, to_id: str) -> float:
        nodes = state.world.space.nodes
        a = nodes.get(from_id)
        b = nodes.get(to_id)
        if not a or not b:
            return 0.0
        dx = float(a.x_ly) - float(b.x_ly)
        dy = float(a.y_ly) - float(b.y_ly)
        dz = float(a.z_ly) - float(b.z_ly)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

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
            if system.state == SystemState.OFFLINE or system.priority == 1:
                continue
            prev_load = system.p_effective_kw()
            old_state = system.state
            system.state = SystemState.OFFLINE
            # Auto-shed is reversible; do not mark forced_offline.
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
        if p_load > p_capacity:
            state.ship.power.brownout = True
            events.append(
                self._make_event(
                    state,
                    EventType.POWER_NET_DEFICIT,
                    Severity.CRITICAL,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Capacity exceeded, vital systems at risk",
                    data={"p_load_kw": p_load, "p_capacity_kw": p_capacity},
                )
            )
        return events

    def _apply_degradation(self, state: GameState, dt: float, power_quality: float) -> list[Event]:
        r_env = state.ship.radiation_env_rad_per_s
        r_env_norm = self._clamp(r_env / Balance.R_REF)
        events: list[Event] = []
        for system in state.ship.systems.values():
            s_factor = 1.0 + system.k_power * (1.0 - power_quality) + system.k_rad * r_env_norm
            system.health = max(0.0, system.health - system.base_decay_per_s * s_factor * dt)
            self._apply_health_state(system, state, events, cause="degradation")
        return events

    def _apply_radiation(self, state: GameState, dt: float) -> None:
        r_env = state.ship.radiation_env_rad_per_s
        for drone in state.ship.drones.values():
            drone.dose_rad += r_env * drone.shield_factor * dt

    def _update_drone_maintenance(self, state: GameState, dt: float) -> None:
        drone_bay = state.ship.systems.get("drone_bay")
        if not drone_bay or drone_bay.state == SystemState.OFFLINE:
            return
        if self._state_rank(drone_bay.state) < self._state_rank(SystemState.LIMITED):
            return
        for drone in state.ship.drones.values():
            if drone.status == DroneStatus.DOCKED:
                # charge battery
                drone.battery = min(1.0, drone.battery + Balance.DRONE_BATTERY_CHARGE_PER_S * dt)
                # repair integrity slowly using scrap
                if drone.integrity < 1.0 and state.ship.cargo_scrap > 0:
                    state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - 1)
                    state.ship.manifest_dirty = True
                    drone.integrity = min(1.0, drone.integrity + Balance.DRONE_REPAIR_INTEGRITY_PER_SCRAP)
            elif drone.status == DroneStatus.DEPLOYED:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S * dt)

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
                    data={"message_key": "power_net_deficit"},
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
                    data={"message_key": "power_core_degraded"},
                )
            )
            active_keys.add(EventType.POWER_CORE_DEGRADED.value)

        distribution = state.ship.systems.get("energy_distribution")
        if (
            distribution
            and distribution.state in (SystemState.DAMAGED, SystemState.CRITICAL)
            and state.clock.t >= Balance.BUS_INSTABILITY_AFTER_S
        ):
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.POWER_BUS_INSTABILITY,
                    Severity.CRITICAL,
                    SourceRef(kind="ship_system", id=distribution.system_id),
                    "Power bus instability due to damaged distribution",
                    data={"message_key": "power_bus_instability"},
                )
            )
            active_keys.add(EventType.POWER_BUS_INSTABILITY.value)

        if power_quality < Balance.LOW_POWER_QUALITY_THRESHOLD:
            existing = state.events.alerts.get(EventType.LOW_POWER_QUALITY.value)
            if not existing or not existing.is_active:
                events.extend(
                    self._ensure_alert(
                        state,
                        EventType.LOW_POWER_QUALITY,
                        Severity.WARN,
                        SourceRef(kind="ship", id=state.ship.ship_id),
                        "Low power quality",
                        data={"power_quality": power_quality, "message_key": "low_power_quality"},
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
            alert.last_seen_t = int(state.clock.t)
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
            first_seen_t=int(state.clock.t),
            last_seen_t=int(state.clock.t),
            data=data or {},
            is_active=True,
        )
        return events

    def _update_alert_timers(self, events: EventManagerState, dt: float) -> None:
        inc = int(dt)
        if inc <= 0:
            return
        for alert in events.alerts.values():
            if alert.is_active and not alert.acknowledged:
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
            t=int(state.clock.t),
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
        risk: RiskProfile | None = None,
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
        if risk is not None:
            job.risk = risk
        state.jobs.jobs[job_id] = job
        state.jobs.active_job_ids.append(job_id)
        source = self._job_source(state, target, owner_id, params)
        data = {
            "job_id": job_id,
            "job_type": job_type.value,
            "eta_s": eta_s,
            "target": {"kind": target.kind, "id": target.id},
            "owner_id": owner_id,
            "message_key": "job_queued",
        }
        if params.get("emergency"):
            data["emergency"] = True
        message = f"Job queued: {job_type.value} -> {target.kind}:{target.id} (ETA {int(eta_s)}s)"
        if job_type == JobType.SALVAGE_SCRAP:
            requested = params.get("requested")
            available = params.get("available")
            effective = params.get("effective")
            if requested is not None:
                data["requested"] = requested
            if available is not None:
                data["available"] = available
            if effective is not None:
                data["effective"] = effective
            message = (
                f"Job queued: salvage_scrap requested={requested} available={available} "
                f"will_recover={effective} (ETA {int(eta_s)}s)"
            )
        event = self._make_event(
            state,
            EventType.JOB_QUEUED,
            Severity.INFO,
            source,
            message,
            data=data,
        )
        self._record_event(state.events, event)
        return [event]

    def _job_source(
        self,
        state: GameState,
        target: TargetRef,
        owner_id: str | None,
        params: dict,
    ) -> SourceRef:
        if owner_id and owner_id in state.ship.drones:
            return SourceRef(kind="drone", id=owner_id)
        if target.kind == "ship_system":
            return SourceRef(kind="ship_system", id=target.id)
        if target.kind == "service":
            system_id = params.get("system_id")
            if system_id:
                return SourceRef(kind="ship_system", id=system_id)
            return SourceRef(kind="ship", id=state.ship.ship_id)
        if target.kind == "world_node":
            return SourceRef(kind="world", id=target.id)
        return SourceRef(kind="ship", id=state.ship.ship_id)

    def _drone_world_node(self, drone) -> str | None:
        if drone.location.kind == "world_node":
            return drone.location.id
        return None

    def _find_system_by_service(
        self, systems: Iterable[ShipSystem], service_name: str
    ) -> ShipSystem | None:
        for system in systems:
            if system.service and system.service.service_name == service_name:
                return system
        return None

    def _available_services(self, state: GameState) -> list[str]:
        services = []
        for system in state.ship.systems.values():
            if system.service and system.service.is_installed:
                services.append(system.service.service_name)
        services.sort()
        return services

    def _has_unlock(self, state: GameState, command_key: str) -> bool:
        modules = load_modules()
        for mod_id in state.ship.installed_modules:
            mod = modules.get(mod_id, {})
            effects = mod.get("effects", {})
            unlocks = effects.get("unlock_commands", [])
            if command_key in unlocks:
                return True
        return False

    def _suggest_service(self, service_name: str, candidates: list[str]) -> str | None:
        if not candidates:
            return None
        matches = difflib.get_close_matches(service_name, candidates, n=1, cutoff=0.6)
        return matches[0] if matches else None

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

    def _first_unmet_dependency(
        self, systems: dict[str, ShipSystem], dependencies: list[Dependency]
    ) -> tuple[str, str, str] | None:
        for dep in dependencies:
            if dep.dep_type != "system_state_at_least":
                continue
            target = systems.get(dep.target_id)
            if not target:
                return (dep.target_id, str(dep.value), "missing")
            required = SystemState(dep.value)
            if self._state_rank(target.state) < self._state_rank(required):
                return (dep.target_id, required.value, target.state.value)
        return None

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

    def _update_battery(self, state: GameState, dt: float, p_gen: float, p_load: float) -> None:
        p_charge_max = state.ship.power.p_charge_max_kw
        p_discharge_max = state.ship.power.p_discharge_max_kw
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

    def _compute_power_quality(self, state: GameState, p_gen: float, p_load: float) -> float:
        if state.ship.power.e_batt_max_kwh > 0:
            soc = state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh
        else:
            soc = 0.0
        q_soc = self._clamp((soc - 0.10) / (0.50 - 0.10))
        p_deficit = max(0.0, p_load - p_gen)
        p_deficit_ratio = (
            self._clamp(p_deficit / state.ship.power.p_discharge_max_kw)
            if state.ship.power.p_discharge_max_kw > 0
            else 1.0
        )
        state.ship.power.deficit_ratio = p_deficit_ratio
        q_def = 1.0 - 0.7 * p_deficit_ratio
        power_quality = 0.6 * q_soc + 0.4 * q_def

        distribution = state.ship.systems.get("energy_distribution")
        if distribution and distribution.state in (SystemState.DAMAGED, SystemState.CRITICAL):
            power_quality -= 0.10

        power_quality += state.ship.power.quality_offset
        return self._clamp(power_quality)

    def _apply_health_state(
        self,
        system: ShipSystem,
        state: GameState,
        events: list[Event],
        cause: str,
    ) -> None:
        if system.forced_offline:
            if system.service:
                system.service.is_running = False
            system.state = SystemState.OFFLINE
            return
        if system.state_locked:
            return
        old_state = system.state
        h = system.health
        if h <= 0.0:
            new_state = SystemState.OFFLINE
        elif h < 0.35:
            new_state = SystemState.CRITICAL
        elif h < 0.60:
            new_state = SystemState.DAMAGED
        elif h < 0.85:
            new_state = SystemState.LIMITED
        else:
            new_state = SystemState.NOMINAL

        if new_state != old_state:
            system.state = new_state
            events.append(
                self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"System state changed: {system.system_id}",
                    data={
                        "from": old_state.value,
                        "to": new_state.value,
                        "cause": cause,
                        "health": system.health,
                        "message_key": "system_state_changed",
                    },
                )
            )
        if system.state == SystemState.OFFLINE or system.health <= 0.0:
            if system.service:
                system.service.is_running = False

    def _maybe_fail_emergency_job(self, state: GameState, job: Job, dt: float) -> Event | None:
        p_fail = self._clamp(job.risk.p_fail_per_s * dt)
        if p_fail <= 0:
            return None
        rng = self._job_rng(state, job)
        if rng.random() >= p_fail:
            return None

        job.status = JobStatus.FAILED
        source = SourceRef(kind="ship", id=state.ship.ship_id)
        if job.owner_id:
            drone = state.ship.drones.get(job.owner_id)
            if drone:
                drone.status = DroneStatus.DISABLED
                drone.integrity = max(0.0, drone.integrity - 0.25)
                source = SourceRef(kind="drone", id=drone.drone_id)
                damaged_event = self._make_event(
                    state,
                    EventType.DRONE_DAMAGED,
                    Severity.WARN,
                    source,
                    f"Drone damaged: {drone.drone_id}",
                    data={"drone_id": drone.drone_id, "message_key": "drone_damaged"},
                )
                self._record_event(state.events, damaged_event)
                disabled_event = self._make_event(
                    state,
                    EventType.DRONE_DISABLED,
                    Severity.WARN,
                    source,
                    f"Drone disabled: {drone.drone_id}",
                    data={"drone_id": drone.drone_id, "message_key": "drone_disabled"},
                )
                self._record_event(state.events, disabled_event)
        return self._make_event(
            state,
            EventType.JOB_FAILED,
            Severity.WARN,
            source,
            f"Emergency job failed: {job.job_type.value}",
            data={
                "job_id": job.job_id,
                "emergency": True,
                "job_type": job.job_type.value,
                "message_key": "job_failed",
            },
        )

    def _job_rng(self, state: GameState, job: Job) -> random.Random:
        job_num = int(job.job_id[1:]) if job.job_id.startswith("J") else 0
        seed = state.meta.rng_seed + int(state.clock.t * 1000.0) + job_num
        return random.Random(seed)

    def _rng(self, state: GameState) -> random.Random:
        r = random.Random(state.meta.rng_seed + state.meta.rng_counter)
        state.meta.rng_counter += 1
        return r

    def _weighted_choice(self, rng: random.Random, items: list[dict]) -> str | None:
        total = sum(float(i.get("weight", 0)) for i in items)
        if total <= 0:
            return None
        r = rng.random() * total
        upto = 0.0
        for item in items:
            w = float(item.get("weight", 0))
            upto += w
            if r <= upto:
                return item.get("id")
        return None
