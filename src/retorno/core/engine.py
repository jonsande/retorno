from __future__ import annotations

import random
import hashlib
from typing import Iterable
import difflib
import math
from pathlib import Path

from retorno.core.actions import (
    Action,
    AuthRecover,
    Boot,
    Diag,
    Dock,
    Undock,
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
    SalvageData,
    RouteSolve,
    SalvageModule,
    SalvageScrap,
    Status,
    Travel,
    TravelAbort,
    JobCancel,
)
from retorno.core.gamestate import GameState
from retorno.core.lore import LoreContext, maybe_deliver_lore, piece_constraints_ok
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.power_policy import (
    is_action_allowed_in_critical_state,
    is_critical_power_state,
    is_critical_system_id,
)
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import AlertState, Event, EventManagerState, EventType, Severity, SourceRef
from retorno.model.jobs import Job, JobManagerState, JobStatus, JobType, RiskProfile, TargetRef
from retorno.model.world import add_known_link, SpaceNode, sector_id_for_pos, region_for_pos
from retorno.runtime.data_loader import load_locations, load_modules, load_arcs
from retorno.model.os import AccessLevel, FSNode, FSNodeType, normalize_path, mount_files
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

        # Update effective generation based on power_core state.
        state.ship.power.p_gen_kw = self._compute_p_gen(state)

        if state.ship.in_transit and state.clock.t >= state.ship.arrival_t:
            state.ship.in_transit = False
            state.ship.current_node_id = state.ship.transit_to or state.ship.current_node_id
            state.world.current_node_id = state.ship.current_node_id
            state.ship.docked_node_id = None
            node = state.world.space.nodes.get(state.world.current_node_id)
            if node:
                state.world.current_pos_ly = (node.x_ly, node.y_ly, node.z_ly)
                if node.kind != "transit":
                    state.world.visited_nodes.add(node.node_id)
            self._clear_tmp_node(state)
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

        events.extend(self._enforce_distribution_collapse(state))

        p_load = self._compute_load_kw(state)
        p_gen = state.ship.power.p_gen_kw
        p_discharge_max = state.ship.power.p_discharge_max_kw
        soc = self._soc(state)
        available_discharge_kw = p_discharge_max if soc > 0.0 else 0.0
        p_capacity = p_gen + available_discharge_kw

        if p_load > p_capacity:
            events.extend(self._auto_load_shed(state, p_capacity, p_load))
            p_load = self._compute_load_kw(state)

        if 0.0 < soc < 0.10 and p_load > p_gen:
            events.extend(self._auto_load_shed(state, p_gen, p_load))
            p_load = self._compute_load_kw(state)

        power_quality_pre = self._compute_power_quality(state, p_gen, p_load)
        if power_quality_pre < Balance.POWER_QUALITY_COLLAPSE_THRESHOLD:
            events.extend(self._shed_all_noncritical(state))
            p_load = self._compute_load_kw(state)
            power_quality_pre = self._compute_power_quality(state, p_gen, p_load)
        if power_quality_pre < Balance.POWER_QUALITY_CRITICAL_THRESHOLD:
            if p_load > p_gen or p_load > p_capacity:
                state.ship.power.low_q_shed_timer_s += dt
            else:
                state.ship.power.low_q_shed_timer_s = 0.0
            if state.ship.power.low_q_shed_timer_s >= Balance.POWER_QUALITY_SHED_INTERVAL_S:
                events.extend(self._auto_shed_one_noncritical(state))
                state.ship.power.low_q_shed_timer_s = 0.0
                p_load = self._compute_load_kw(state)
        else:
            state.ship.power.low_q_shed_timer_s = 0.0

        state.ship.power.p_load_kw = p_load

        self._update_battery(state, dt, p_gen, p_load)
        power_quality = self._compute_power_quality(state, p_gen, p_load)
        state.ship.power.power_quality = power_quality
        soc = self._soc(state)
        available_discharge_kw = p_discharge_max if soc > 0.0 else 0.0
        state.ship.power.brownout = p_load > (p_gen + available_discharge_kw)
        if state.ship.power.brownout:
            state.ship.power.brownout_sustained_s += dt
        else:
            state.ship.power.brownout_sustained_s = 0.0

        brownout_sustained = (
            state.ship.power.brownout
            and state.ship.power.brownout_sustained_s >= Balance.BROWNOUT_SUSTAINED_AFTER_S
        )
        events.extend(self._apply_degradation(state, dt, power_quality, brownout_sustained))
        self._apply_radiation(state, dt)
        self._update_drone_maintenance(state, dt)
        events.extend(self._update_drone_battery_alerts(state))

        events.extend(self._apply_critical_system_consequences(state, dt))
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

        blocked = self._check_power_action_block(state, action)
        if blocked:
            return [blocked]

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
            known = state.world.known_nodes if hasattr(state.world, "known_nodes") else state.world.known_contacts
            intel = state.world.known_intel if hasattr(state.world, "known_intel") else {}
            if action.node_id not in known and action.node_id not in intel:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Route solve blocked: unknown contact {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "unknown_contact", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            current_id = state.world.current_node_id
            if (
                state.world.active_tmp_node_id
                and current_id == state.world.active_tmp_node_id
                and action.node_id not in {state.world.active_tmp_from, state.world.active_tmp_to}
            ):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel blocked: temporary waypoint allows only origin/destination",
                    data={"message_key": "boot_blocked", "reason": "no_route", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
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
            known = state.world.known_nodes if hasattr(state.world, "known_nodes") else state.world.known_contacts
            intel = state.world.known_intel if hasattr(state.world, "known_intel") else {}
            if action.node_id not in known and action.node_id not in intel:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Travel blocked: unknown destination {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "unknown_contact", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            links = state.world.known_links.get(current_id, set()) if hasattr(state.world, "known_links") else set()
            if action.node_id not in links:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Travel blocked: no known route to {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "no_route", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            distance_ly = self._distance_between_nodes(state, current_id, action.node_id)
            fine_km = state.world.fine_ranges_km.get(action.node_id)
            same_sector = False
            from_node = state.world.space.nodes.get(current_id)
            to_node = state.world.space.nodes.get(action.node_id)
            if from_node and to_node:
                same_sector = sector_id_for_pos(from_node.x_ly, from_node.y_ly, from_node.z_ly) == sector_id_for_pos(
                    to_node.x_ly, to_node.y_ly, to_node.z_ly
                )
                if fine_km is None and same_sector and distance_ly <= Balance.LOCAL_TRAVEL_RADIUS_LY:
                    fine_km = self._compute_fine_range_km(state, current_id, action.node_id)
                    state.world.fine_ranges_km[action.node_id] = fine_km
            is_local = bool(
                fine_km is not None
                and same_sector
                and distance_ly <= Balance.LOCAL_TRAVEL_RADIUS_LY
            )
            if is_local:
                travel_s = fine_km / max(0.1, Balance.LOCAL_TRAVEL_SPEED_KM_S)
                years = travel_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
            else:
                speed = max(0.001, state.ship.cruise_speed_ly_per_year)
                years = distance_ly / speed
                travel_s = years * Balance.YEAR_S
            state.ship.in_transit = True
            state.ship.transit_from = current_id
            state.ship.transit_to = action.node_id
            state.ship.arrival_t = state.clock.t + travel_s
            state.ship.transit_start_t = state.clock.t
            state.ship.last_travel_distance_ly = distance_ly
            state.ship.last_travel_distance_km = fine_km or 0.0
            state.ship.last_travel_is_local = is_local
            state.ship.transit_prev_op_mode = state.ship.op_mode
            state.ship.transit_prev_op_mode_source = state.ship.op_mode_source
            state.ship.docked_node_id = None
            if hasattr(state.world, "known_nodes"):
                state.world.known_nodes.add(action.node_id)
            state.world.known_contacts.add(action.node_id)
            events: list[Event] = []
            if not action.no_cruise:
                state.ship.op_mode = "CRUISE"
                state.ship.op_mode_source = "auto"
                # Apply the cruise power plan behavior (auto-shed systems).
                targets = ["sensors", "security", "data_core", "drone_bay"]
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
                        self._record_event(
                            state.events,
                            self._make_event(
                                state,
                                EventType.SYSTEM_STATE_CHANGED,
                                Severity.WARN,
                                SourceRef(kind="ship_system", id=sys.system_id),
                                f"Power plan cruise: {sys.system_id} -> OFFLINE",
                                data={"from": old_state.value, "to": sys.state.value, "cause": "manual_shed"},
                            ),
                        )
                profile = self._make_event(
                    state,
                    EventType.TRAVEL_PROFILE_SET,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel profile set: CRUISE (auto). Use 'nav --no-cruise <dest>' to override.",
                    data={"message_key": "travel_profile_auto"},
                )
                self._record_event(state.events, profile)
                events.append(profile)
            else:
                warn = self._make_event(
                    state,
                    EventType.TRAVEL_PROFILE_SET,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel override: CRUISE disabled. Increased wear expected.",
                    data={"message_key": "travel_profile_manual"},
                )
                self._record_event(state.events, warn)
                events.append(warn)
                if state.ship.op_mode != "CRUISE" and years > Balance.TRANSIT_WARN_YEARS:
                    warn2 = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="ship", id=state.ship.ship_id),
                        "Travel initiated in NORMAL mode. Consider CRUISE for long trips.",
                        data={"message_key": "travel_warn", "mode": state.ship.op_mode, "eta_years": years},
                    )
                    self._record_event(state.events, warn2)
                    events.append(warn2)
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
                    "local": is_local,
                    "distance_km": fine_km,
                    "eta_s": travel_s,
                },
            )
            self._record_event(state.events, event)
            events.append(event)
            return events

        if isinstance(action, TravelAbort):
            if not state.ship.in_transit:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel abort blocked: not in transit",
                    data={"message_key": "boot_blocked", "reason": "not_in_transit"},
                )
                self._record_event(state.events, event)
                return [event]
            from_id = state.ship.transit_from
            to_id = state.ship.transit_to
            start_t = state.ship.transit_start_t
            end_t = state.ship.arrival_t
            if end_t > start_t:
                progress = self._clamp((state.clock.t - start_t) / (end_t - start_t))
            else:
                progress = 0.0
            from_node = state.world.space.nodes.get(from_id)
            to_node = state.world.space.nodes.get(to_id)
            if from_node and to_node:
                x = from_node.x_ly + (to_node.x_ly - from_node.x_ly) * progress
                y = from_node.y_ly + (to_node.y_ly - from_node.y_ly) * progress
                z = from_node.z_ly + (to_node.z_ly - from_node.z_ly) * progress
            else:
                x, y, z = state.world.current_pos_ly

            self._clear_tmp_node(state)
            rng = self._rng(state)
            tmp_id = f"NAV_PT_{rng.getrandbits(16):04X}"
            while tmp_id in state.world.space.nodes:
                tmp_id = f"NAV_PT_{rng.getrandbits(16):04X}"
            tmp_node = SpaceNode(
                node_id=tmp_id,
                name="Nav Point",
                kind="transit",
                radiation_rad_per_s=0.0,
                x_ly=x,
                y_ly=y,
                z_ly=z,
            )
            state.world.space.nodes[tmp_id] = tmp_node
            state.world.current_node_id = tmp_id
            state.ship.current_node_id = tmp_id
            state.world.current_pos_ly = (x, y, z)
            state.world.active_tmp_node_id = tmp_id
            state.world.active_tmp_from = from_id
            state.world.active_tmp_to = to_id
            state.world.active_tmp_progress = progress
            state.ship.docked_node_id = None
            if from_id:
                add_known_link(state.world, tmp_id, from_id, bidirectional=True)
            if to_id:
                add_known_link(state.world, tmp_id, to_id, bidirectional=True)
            state.ship.in_transit = False
            state.ship.arrival_t = 0.0
            state.ship.transit_to = ""
            state.ship.transit_from = ""
            state.ship.transit_start_t = 0.0
            if state.ship.transit_prev_op_mode:
                state.ship.op_mode = state.ship.transit_prev_op_mode
                state.ship.op_mode_source = state.ship.transit_prev_op_mode_source or "manual"
            state.ship.transit_prev_op_mode = ""
            state.ship.transit_prev_op_mode_source = ""
            event = self._make_event(
                state,
                EventType.TRAVEL_ABORTED,
                Severity.WARN,
                SourceRef(kind="ship", id=state.ship.ship_id),
                "Travel aborted",
                data={
                    "message_key": "travel_aborted",
                    "from": from_id,
                    "to": to_id,
                    "progress": progress,
                    "tmp_id": tmp_id,
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
                state.ship.op_mode_source = "manual"
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
                state.ship.op_mode_source = "manual"
                for sid in targets:
                    sys = state.ship.systems.get(sid)
                    if not sys:
                        continue
                    sys.forced_offline = False
                    if sys.auto_offline_reason == "load_shed":
                        sys.auto_offline_reason = None
                for sid in targets:
                    sys = state.ship.systems.get(sid)
                    if not sys:
                        continue
                    self._apply_health_state(sys, state, events, cause="plan_normal")
                return events
            return []

        allowed_in_transit = (
            PowerShed,
            SystemOn,
            PowerPlan,
            Boot,
            DroneDeploy,
            DroneMove,
            DroneRecall,
            DroneReboot,
            Repair,
            SelfTestRepair,
            Install,
            CargoAudit,
            AuthRecover,
        )
        if state.ship.in_transit and not isinstance(action, allowed_in_transit):
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
            if action.node_id != state.world.current_node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Dock blocked: not at {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "not_at_node", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
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
            if node.kind == "origin":
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Dock blocked: docking not allowed at {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "dock_not_allowed", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            known = state.world.known_nodes if hasattr(state.world, "known_nodes") else state.world.known_contacts
            intel = state.world.known_intel if hasattr(state.world, "known_intel") else {}
            if action.node_id != state.world.current_node_id and action.node_id not in known and action.node_id not in intel:
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

        if isinstance(action, Undock):
            if state.ship.in_transit:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Undock blocked: ship in transit",
                    data={"message_key": "boot_blocked", "reason": "in_transit"},
                )
                self._record_event(state.events, event)
                return [event]
            if state.ship.docked_node_id != state.world.current_node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Undock blocked: not docked at {state.world.current_node_id}",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "not_docked",
                        "node_id": state.world.current_node_id,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            node_id = state.world.current_node_id
            return self._enqueue_job(
                state,
                JobType.UNDOCK,
                TargetRef(kind="world_node", id=node_id),
                owner_id=None,
                eta_s=Balance.UNDOCK_TIME_S,
                params={"node_id": node_id},
            )

        if isinstance(action, Install):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Install blocked: drone {action.drone_id} not found",
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
                    f"Install blocked: {drone.drone_id} not deployed",
                    data={"message_key": "boot_blocked", "reason": "drone_not_deployed", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.location.kind != "ship_sector":
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Install blocked: {drone.drone_id} not on ship",
                    data={"message_key": "boot_blocked", "reason": "not_on_ship", "drone_id": drone.drone_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_TASK:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Install blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_TASK,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            bay_state = self._drone_bay_state(state)
            if bay_state == SystemState.OFFLINE:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="drone_bay"),
                    "Action blocked: drone bay offline; module installation requires bay support",
                    data={"message_key": "boot_blocked", "reason": "drone_bay_install_offline"},
                )
                self._record_event(state.events, event)
                return [event]
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
            pre_events: list[Event] = []
            support_warning = self._emit_drone_bay_support_warning(state, action)
            if support_warning:
                self._record_event(state.events, support_warning)
                pre_events.append(support_warning)
            eta = Balance.INSTALL_TIME_S * self._drone_bay_eta_mult(state)
            return pre_events + self._enqueue_job(
                state,
                JobType.INSTALL_MODULE,
                TargetRef(kind="ship", id=state.ship.ship_id),
                owner_id=action.drone_id,
                eta_s=eta,
                params={
                    "module_id": action.module_id,
                    "scrap_cost": scrap_cost,
                    "drone_id": action.drone_id,
                    "bay_state_at_start": bay_state.value if bay_state else "",
                },
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
                    "Cargo audit blocked: data_core offline. Try: power on data_core",
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

        if isinstance(action, AuthRecover):
            level = action.level.upper()
            if level in state.os.auth_levels:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"{level} already available",
                    data={"message_key": "boot_blocked", "reason": "auth_already_available"},
                )
                self._record_event(state.events, event)
                return [event]
            system = state.ship.systems.get("data_core")
            if not system:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="data_core"),
                    "Auth recover blocked: data_core missing",
                    data={"message_key": "boot_blocked", "reason": "auth_recover_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if system.forced_offline or system.state == SystemState.OFFLINE:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Auth recover blocked: data_core offline",
                    data={"message_key": "boot_blocked", "reason": "auth_recover_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if not system.service or system.service.service_name != "datad":
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Auth recover blocked: datad not installed",
                    data={"message_key": "boot_blocked", "reason": "auth_recover_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if not system.service.is_running:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Auth recover blocked: datad not running. Try: boot datad",
                    data={"message_key": "boot_blocked", "reason": "auth_recover_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if self._state_rank(system.state) < self._state_rank(SystemState.LIMITED):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    "Auth recover blocked: data_core degraded (requires >= limited).",
                    data={"message_key": "boot_blocked", "reason": "auth_recover_blocked"},
                )
                self._record_event(state.events, event)
                return [event]
            if level == "MED":
                eta_s = Balance.AUTH_RECOVER_MED_TIME_S
                power_kw = Balance.AUTH_RECOVER_MED_POWER_KW
            elif level == "ENG":
                eta_s = Balance.AUTH_RECOVER_ENG_TIME_S
                power_kw = Balance.AUTH_RECOVER_ENG_POWER_KW
            elif level == "OPS":
                eta_s = Balance.AUTH_RECOVER_OPS_TIME_S
                power_kw = Balance.AUTH_RECOVER_OPS_POWER_KW
            elif level == "SEC":
                eta_s = Balance.AUTH_RECOVER_SEC_TIME_S
                power_kw = Balance.AUTH_RECOVER_SEC_POWER_KW
            else:
                eta_s = Balance.AUTH_RECOVER_MED_TIME_S
                power_kw = Balance.AUTH_RECOVER_MED_POWER_KW
            return self._enqueue_job(
                state,
                JobType.RECOVER_AUTH,
                TargetRef(kind="auth", id=level),
                owner_id=None,
                eta_s=eta_s,
                params={"level": level},
                power_draw_kw=power_kw,
            )

        if isinstance(action, JobCancel):
            job = state.jobs.jobs.get(action.job_id)
            if not job:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Job cancel blocked: job {action.job_id} not found",
                    data={"message_key": "boot_blocked", "reason": "job_missing", "job_id": action.job_id},
                )
                self._record_event(state.events, event)
                return [event]
            if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED}:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Job cancel blocked: job {action.job_id} already {job.status.value}",
                    data={"message_key": "boot_blocked", "reason": "job_not_active", "job_id": action.job_id},
                )
                self._record_event(state.events, event)
                return [event]
            job.status = JobStatus.CANCELLED
            if action.job_id in state.jobs.active_job_ids:
                state.jobs.active_job_ids.remove(action.job_id)
            event = self._make_event(
                state,
                EventType.JOB_FAILED,
                Severity.INFO,
                SourceRef(kind="ship", id=state.ship.ship_id),
                f"Job cancelled: {action.job_id}",
                data={
                    "job_id": action.job_id,
                    "job_type": job.job_type.value,
                    "message_key": "job_cancelled",
                },
            )
            self._record_event(state.events, event)
            return [event]

        if isinstance(action, RouteSolve):
            current_id = state.world.current_node_id
            if action.node_id in state.world.known_links.get(current_id, set()):
                fine_km = self._maybe_set_fine_range(state, current_id, action.node_id)
                if fine_km is not None:
                    event = self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="world", id=action.node_id),
                        f"Route refined: fine range fixed for {action.node_id}",
                        data={
                            "job_id": "-",
                            "job_type": "route_refine",
                            "node_id": action.node_id,
                            "distance_km": fine_km,
                            "message_key": "route_refined",
                        },
                    )
                    self._record_event(state.events, event)
                    return [event]
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.INFO,
                    SourceRef(kind="world", id=action.node_id),
                    f"Route solve skipped: already known route to {action.node_id}",
                    data={"message_key": "boot_blocked", "reason": "route_known", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            system = state.ship.systems.get("sensors")
            if not system or self._state_rank(system.state) < self._state_rank(SystemState.LIMITED):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="sensors"),
                    "Route solve blocked: sensors offline",
                    data={"message_key": "boot_blocked", "reason": "sensors_offline"},
                )
                self._record_event(state.events, event)
                return [event]
            if not system.service or system.service.service_name != "sensord" or not system.service.is_running:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="sensors"),
                    "Route solve blocked: sensord not running",
                    data={"message_key": "boot_blocked", "reason": "sensord_not_running"},
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
                    f"Route solve blocked: node {action.node_id} not found",
                    data={"message_key": "boot_blocked", "reason": "node_missing", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            current_id = state.world.current_node_id
            current = state.world.space.nodes.get(current_id)
            if not current:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=current_id),
                    f"Route solve blocked: current node {current_id} not found",
                    data={"message_key": "boot_blocked", "reason": "node_missing", "node_id": current_id},
                )
                self._record_event(state.events, event)
                return [event]
            distance_ly = self._distance_between_nodes(state, current_id, action.node_id)
            if distance_ly > state.ship.sensors_range_ly:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Route solve blocked: target out of sensor range ({distance_ly:.2f}ly)",
                    data={"message_key": "boot_blocked", "reason": "out_of_range", "node_id": action.node_id},
                )
                self._record_event(state.events, event)
                return [event]
            t = distance_ly / state.ship.sensors_range_ly if state.ship.sensors_range_ly > 0 else 1.0
            t = max(0.0, min(1.0, t))
            eta = Balance.ROUTE_SOLVE_MIN_S + (Balance.ROUTE_SOLVE_MAX_S - Balance.ROUTE_SOLVE_MIN_S) * t
            return self._enqueue_job(
                state,
                JobType.ROUTE_SOLVE,
                TargetRef(kind="world_node", id=action.node_id),
                owner_id=None,
                eta_s=eta,
                params={"node_id": action.node_id, "from_id": current_id, "distance_ly": distance_ly},
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
            if system.health <= Balance.SYSTEM_HEALTH_MIN_ON:
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
            effective_deps = self._system_dependencies_for_gating(system)
            if self._dependencies_blocked(state.ship.systems, effective_deps):
                dep_detail = self._first_unmet_dependency(state.ship.systems, effective_deps)
                dep_target, dep_required, dep_current = dep_detail if dep_detail else ("?", "?", "?")
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"System on blocked: {system.system_id} requires {dep_target}>={dep_required} (current={dep_current})",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "deps_unmet",
                        "service": system.system_id,
                        "dep_target": dep_target,
                        "dep_required": dep_required,
                        "dep_current": dep_current,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if system.forced_offline or system.state == SystemState.OFFLINE:
                system.forced_offline = False
                if system.auto_offline_reason == "load_shed":
                    system.auto_offline_reason = None
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
                if state.ship.docked_node_id != action.sector_id:
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
            elif action.sector_id not in state.ship.sectors:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Drone deploy blocked: ship sector {action.sector_id} not found",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "ship_sector_missing",
                        "sector_id": action.sector_id,
                        "hint_key": "deploy_target_hint",
                    },
                )
                self._record_event(state.events, event)
                return [event]
            drone_bay = state.ship.systems.get("drone_bay")
            distribution = state.ship.systems.get("energy_distribution")
            emergency_maintenance_bypass = bool(
                action.emergency and distribution and distribution.state == SystemState.OFFLINE
            )
            if (
                not action.emergency
                and (not drone_bay or drone_bay.state == SystemState.OFFLINE or drone_bay.forced_offline)
            ):
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
            bay_state = self._drone_bay_state(state)
            if bay_state == SystemState.OFFLINE and not action.emergency:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="drone_bay"),
                    "Action blocked: drone bay offline; use 'drone deploy!' for emergency launch",
                    data={"message_key": "boot_blocked", "reason": "drone_bay_deploy_offline"},
                )
                self._record_event(state.events, event)
                return [event]

            pre_events: list[Event] = []
            support_warning = self._emit_drone_bay_support_warning(state, action)
            if support_warning:
                self._record_event(state.events, support_warning)
                pre_events.append(support_warning)

            eta = Balance.DEPLOY_TIME_S * self._drone_bay_eta_mult(state)
            params = {
                "drone_id": action.drone_id,
                "bay_state_at_start": bay_state.value if bay_state else "",
            }
            if emergency_maintenance_bypass:
                warn = self._make_event(
                    state,
                    EventType.ACTION_WARNING,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="energy_distribution"),
                    "Emergency maintenance bypass active: deploying emergency drone while energy_distribution remains offline",
                    data={"message_key": "emergency_maintenance_bypass", "drone_id": action.drone_id},
                )
                self._record_event(state.events, warn)
                deploy_events = self._enqueue_job(
                    state,
                    JobType.DEPLOY_DRONE,
                    TargetRef(kind=target_kind, id=target_id),
                    owner_id=action.drone_id,
                    eta_s=eta,
                    params={
                        **params,
                        "emergency": True,
                        "maintenance_bypass": True,
                    },
                    risk=RiskProfile(
                        p_glitch_per_s=Balance.EMERGENCY_DEPLOY_P_GLITCH_PER_S,
                        p_fail_per_s=Balance.EMERGENCY_DEPLOY_P_FAIL_PER_S,
                    ),
                )
                return pre_events + [warn] + deploy_events

            if action.emergency:
                return pre_events + self._enqueue_job(
                    state,
                    JobType.DEPLOY_DRONE,
                    TargetRef(kind=target_kind, id=target_id),
                    owner_id=action.drone_id,
                    eta_s=eta,
                    params={**params, "emergency": True},
                    risk=RiskProfile(
                        p_glitch_per_s=Balance.EMERGENCY_DEPLOY_P_GLITCH_PER_S,
                        p_fail_per_s=Balance.EMERGENCY_DEPLOY_P_FAIL_PER_S,
                    ),
                )

            return pre_events + self._enqueue_job(
                state,
                JobType.DEPLOY_DRONE,
                TargetRef(kind=target_kind, id=target_id),
                owner_id=action.drone_id,
                eta_s=eta,
                params=params,
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
                if state.ship.docked_node_id != target_id:
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
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_TASK:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Move blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_TASK,
                    },
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
            pre_events: list[Event] = []
            support_warning = self._emit_drone_bay_support_warning(state, action)
            if support_warning:
                self._record_event(state.events, support_warning)
                pre_events.append(support_warning)
            bay_state = self._drone_bay_state(state)
            eta = Balance.REBOOT_TIME_S * self._drone_bay_eta_mult(state)
            return pre_events + self._enqueue_job(
                state,
                JobType.REBOOT_DRONE,
                TargetRef(kind="drone", id=drone.drone_id),
                owner_id=drone.drone_id,
                eta_s=eta,
                params={"drone_id": drone.drone_id, "bay_state_at_start": bay_state.value if bay_state else ""},
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
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_RECALL:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Recall blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_RECALL,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if drone.location.kind == "world_node":
                if state.ship.docked_node_id != drone.location.id:
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
            pre_events: list[Event] = []
            support_warning = self._emit_drone_bay_support_warning(state, action)
            if support_warning:
                self._record_event(state.events, support_warning)
                pre_events.append(support_warning)
            bay_state = self._drone_bay_state(state)
            eta = Balance.RECALL_TIME_S * self._drone_bay_eta_mult(state)
            return pre_events + self._enqueue_job(
                state,
                JobType.RECALL_DRONE,
                TargetRef(kind="drone", id=drone.drone_id),
                owner_id=drone.drone_id,
                eta_s=eta,
                params={"drone_id": drone.drone_id, "bay_state_at_start": bay_state.value if bay_state else ""},
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
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_TASK:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Repair blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_TASK,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            target_drone = state.ship.drones.get(action.system_id)
            if target_drone:
                if target_drone.drone_id == drone.drone_id:
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Repair blocked: {drone.drone_id} cannot repair itself",
                        data={"message_key": "boot_blocked", "reason": "invalid_target", "drone_id": drone.drone_id},
                    )
                    self._record_event(state.events, event)
                    return [event]
                if (
                    drone.location.kind != target_drone.location.kind
                    or drone.location.id != target_drone.location.id
                ):
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="drone", id=target_drone.drone_id),
                        f"Repair blocked: target drone {target_drone.drone_id} not at operator location",
                        data={
                            "message_key": "boot_blocked",
                            "reason": "drone_target_not_co_located",
                            "drone_id": target_drone.drone_id,
                        },
                    )
                    self._record_event(state.events, event)
                    return [event]
                if target_drone.integrity >= 1.0:
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.INFO,
                        SourceRef(kind="drone", id=target_drone.drone_id),
                        f"Repair skipped: {target_drone.drone_id} already at full integrity",
                        data={"message_key": "boot_blocked", "reason": "already_nominal", "drone_id": target_drone.drone_id},
                    )
                    self._record_event(state.events, event)
                    return [event]
                repair_amount = 0.15
                repair_scrap = max(1, int(round(repair_amount * Balance.REPAIR_SCRAP_PER_HEALTH)))
                if state.ship.cargo_scrap < repair_scrap:
                    event = self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="ship", id=state.ship.ship_id),
                        f"Repair blocked: insufficient scrap ({state.ship.cargo_scrap}/{repair_scrap})",
                        data={
                            "message_key": "boot_blocked",
                            "reason": "scrap_insufficient_repair",
                            "scrap_cost": repair_scrap,
                        },
                    )
                    self._record_event(state.events, event)
                    return [event]
                state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - repair_scrap)
                state.ship.manifest_dirty = True
                return self._enqueue_job(
                    state,
                    JobType.REPAIR_DRONE,
                    TargetRef(kind="drone", id=target_drone.drone_id),
                    owner_id=action.drone_id,
                    eta_s=Balance.REPAIR_TIME_S,
                    params={
                        "drone_id": action.drone_id,
                        "target_drone_id": target_drone.drone_id,
                        "repair_amount": repair_amount,
                        "repair_scrap": repair_scrap,
                    },
                )

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

            pre_events: list[Event] = []
            if is_critical_power_state(state):
                if is_critical_system_id(target_system.system_id):
                    info = self._make_event(
                        state,
                        EventType.ACTION_WARNING,
                        Severity.INFO,
                        SourceRef(kind="ship_system", id=target_system.system_id),
                        "Emergency recovery override: critical repair authorized",
                        data={
                            "message_key": "critical_repair_override",
                            "system_id": target_system.system_id,
                            "drone_id": action.drone_id,
                        },
                    )
                    self._record_event(state.events, info)
                    pre_events.append(info)
                else:
                    warn = self._make_event(
                        state,
                        EventType.ACTION_WARNING,
                        Severity.WARN,
                        SourceRef(kind="ship_system", id=target_system.system_id),
                        "Warning: repairing non-critical systems during critical power state may worsen survival odds",
                        data={
                            "message_key": "noncritical_repair_warning",
                            "system_id": target_system.system_id,
                            "drone_id": action.drone_id,
                        },
                    )
                    self._record_event(state.events, warn)
                    pre_events.append(warn)

            default_repair = 0.25 if action.system_id == "energy_distribution" else 0.15
            repair_amount = float(default_repair)
            repair_scrap = max(1, int(round(repair_amount * Balance.REPAIR_SCRAP_PER_HEALTH)))
            if state.ship.cargo_scrap < repair_scrap:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Repair blocked: insufficient scrap ({state.ship.cargo_scrap}/{repair_scrap})",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "scrap_insufficient_repair",
                        "scrap_cost": repair_scrap,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - repair_scrap)
            state.ship.manifest_dirty = True
            params = {"drone_id": action.drone_id, "repair_amount": repair_amount, "repair_scrap": repair_scrap}
            if action.system_id == "energy_distribution":
                params["repair_amount"] = 0.25
            return pre_events + self._enqueue_job(
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
            repair_scrap = max(1, int(round(Balance.SELFTEST_REPAIR_AMOUNT * Balance.SELFTEST_REPAIR_SCRAP_PER_HEALTH)))
            if state.ship.cargo_scrap < repair_scrap:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Repair blocked: insufficient scrap ({state.ship.cargo_scrap}/{repair_scrap})",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "scrap_insufficient_repair",
                        "scrap_cost": repair_scrap,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - repair_scrap)
            state.ship.manifest_dirty = True
            return self._enqueue_job(
                state,
                JobType.SELFTEST_REPAIR,
                TargetRef(kind="ship_system", id=action.system_id),
                owner_id=None,
                eta_s=Balance.SELFTEST_REPAIR_TIME_S,
                params={"system_id": action.system_id, "repair_scrap": repair_scrap},
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
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_TASK:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_TASK,
                    },
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
                loc = f"{drone.location.kind}:{drone.location.id}"
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not at node {node_id} (current {loc})",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_not_at_node",
                        "node_id": node_id,
                        "drone_loc": loc,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if state.ship.docked_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: ship not docked at {node_id}",
                    data={"message_key": "boot_blocked", "reason": "ship_not_docked", "node_id": node_id},
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
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_TASK:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_TASK,
                    },
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
            if state.ship.docked_node_id != node_id:
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

        if isinstance(action, SalvageData):
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
            if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_TASK:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} battery too low",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_low_battery",
                        "drone_id": drone.drone_id,
                        "battery": drone.battery,
                        "threshold": Balance.DRONE_MIN_BATTERY_FOR_TASK,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            node_id = action.node_id
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
            if node.kind not in {"station", "ship", "derelict", "relay"}:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: node {node_id} has no data interfaces",
                    data={"message_key": "boot_blocked", "reason": "node_invalid", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            if drone.location.kind != "world_node" or drone.location.id != node_id:
                loc = f"{drone.location.kind}:{drone.location.id}"
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=drone.drone_id),
                    f"Salvage blocked: {drone.drone_id} not at node {node_id} (current {loc})",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "drone_not_at_node",
                        "node_id": node_id,
                        "drone_loc": loc,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            if state.ship.docked_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    f"Salvage blocked: ship not docked at {node_id}",
                    data={"message_key": "boot_blocked", "reason": "ship_not_docked", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            eta = Balance.SALVAGE_DATA_TIME_S
            return self._enqueue_job(
                state,
                JobType.SALVAGE_DATA,
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
                event = self._make_event(
                    state,
                    EventType.SERVICE_ALREADY_RUNNING,
                    Severity.INFO,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Service already running: {service_name}",
                    data={
                        "message_key": "service_already_running",
                        "service": service_name,
                        "system_id": system.system_id,
                    },
                )
                self._record_event(state.events, event)
                return [event]
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
        running_by_owner: set[str] = set()

        for job_id in list(jobs_state.active_job_ids):
            job = jobs_state.jobs.get(job_id)
            if not job:
                continue
            if job.status == JobStatus.RUNNING and job.owner_id:
                running_by_owner.add(job.owner_id)

        for job_id in list(jobs_state.active_job_ids):
            job = jobs_state.jobs.get(job_id)
            if not job or job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED):
                completed.append(job_id)
                continue
            interrupted = self._check_job_interruption(state, job)
            if interrupted is not None:
                job.status = JobStatus.FAILED
                events.append(interrupted)
                completed.append(job_id)
                continue
            if job.status == JobStatus.QUEUED:
                if job.owner_id and job.owner_id in running_by_owner:
                    continue
                job.status = JobStatus.RUNNING
                if job.owner_id:
                    running_by_owner.add(job.owner_id)
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

    def _check_job_interruption(self, state: GameState, job: Job) -> Event | None:
        if job.job_type == JobType.DOCK:
            node_id = job.params.get("node_id", job.target.id if job.target else "")
            if state.ship.in_transit:
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Dock interrupted: ship entered transit before docking at {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_dock_interrupted",
                    },
                )
                self._record_event(state.events, event)
                return event
            if node_id and state.world.current_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Dock interrupted: ship left {node_id} before docking completed",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_dock_interrupted",
                    },
                )
                self._record_event(state.events, event)
                return event
            return None

        if job.job_type == JobType.UNDOCK:
            node_id = job.params.get("node_id", job.target.id if job.target else "")
            if state.ship.in_transit:
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Undock interrupted: ship entered transit before undocking from {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_undock_interrupted",
                    },
                )
                self._record_event(state.events, event)
                return event
            if node_id and state.world.current_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Undock interrupted: ship left {node_id} before undocking completed",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_undock_interrupted",
                    },
                )
                self._record_event(state.events, event)
                return event
            if node_id and state.ship.docked_node_id != node_id:
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Undock interrupted: ship no longer docked at {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_undock_interrupted",
                    },
                )
                self._record_event(state.events, event)
                return event
            return None

        return None

    def _location_fs_files(self, node_id: str) -> list[dict]:
        for loc in load_locations():
            node_cfg = loc.get("node", {})
            if node_cfg.get("node_id") == node_id:
                return list(loc.get("fs_files") or [])
        return []

    def _is_location_node(self, node_id: str) -> bool:
        for loc in load_locations():
            node_cfg = loc.get("node", {})
            if node_cfg.get("node_id") == node_id:
                return True
        return False

    def _get_arc_state(self, state: GameState, arc_id: str) -> dict:
        arc_state = state.world.arc_placements.get(arc_id)
        if not arc_state:
            arc_state = {
                "primary": {"placed": False, "node_id": None, "path": None, "source": None},
                "secondary": {},  # doc_id -> {node_id, path}
                "counters": {"uplink_attempts": 0, "procedural_candidates": 0},
                "discovered": set(),
            }
            state.world.arc_placements[arc_id] = arc_state
        if not isinstance(arc_state.get("discovered"), set):
            arc_state["discovered"] = set(arc_state.get("discovered") or [])
        return arc_state

    def _hash64(self, seed: int, text: str) -> int:
        h = hashlib.blake2b(digest_size=8)
        h.update(str(seed).encode("utf-8"))
        h.update(text.encode("utf-8"))
        return int.from_bytes(h.digest(), "big", signed=False)

    def _compute_fine_range_km(self, state: GameState, from_id: str, to_id: str) -> float:
        a, b = sorted([from_id, to_id])
        seed = self._hash64(state.meta.rng_seed, f"fine:{a}:{b}")
        t = (seed % 10_000) / 10_000.0
        return Balance.LOCAL_TRAVEL_MIN_KM + (Balance.LOCAL_TRAVEL_MAX_KM - Balance.LOCAL_TRAVEL_MIN_KM) * t

    def _maybe_set_fine_range(self, state: GameState, from_id: str, to_id: str) -> float | None:
        if to_id in state.world.fine_ranges_km:
            return None
        from_node = state.world.space.nodes.get(from_id)
        to_node = state.world.space.nodes.get(to_id)
        if not from_node or not to_node:
            return None
        if sector_id_for_pos(from_node.x_ly, from_node.y_ly, from_node.z_ly) != sector_id_for_pos(
            to_node.x_ly, to_node.y_ly, to_node.z_ly
        ):
            return None
        dist_ly = self._distance_between_nodes(state, from_id, to_id)
        if dist_ly > Balance.LOCAL_TRAVEL_RADIUS_LY:
            return None
        fine_km = self._compute_fine_range_km(state, from_id, to_id)
        state.world.fine_ranges_km[to_id] = fine_km
        return fine_km

    def _hop_distance_from_start(self, state: GameState, target_id: str, max_hops: int) -> int | None:
        start_id = "UNKNOWN_00" if "UNKNOWN_00" in state.world.space.nodes else state.world.current_node_id
        if start_id not in state.world.space.nodes or target_id not in state.world.space.nodes:
            return None
        visited = {start_id}
        queue = [(start_id, 0)]
        while queue:
            nid, dist = queue.pop(0)
            if nid == target_id:
                return dist
            if dist >= max_hops:
                continue
            node = state.world.space.nodes.get(nid)
            if not node:
                continue
            for nxt in node.links:
                if nxt in visited:
                    continue
                if nxt not in state.world.space.nodes:
                    continue
                visited.add(nxt)
                queue.append((nxt, dist + 1))
        return None

    def _maybe_inject_arc_content(
        self,
        state: GameState,
        node_id: str,
        node: SpaceNode | None,
        base_files: list[dict],
        is_procedural: bool,
    ) -> list[dict]:
        files = list(base_files)
        existing_paths = {f.get("path") for f in files}
        arcs = load_arcs()
        if not arcs or not node:
            return files
        arc_ctx = self._build_lore_context(state, node_id)
        for arc in arcs:
            arc_id = arc.get("arc_id")
            if not arc_id:
                continue
            arc_state = self._get_arc_state(state, arc_id)
            primary = arc.get("primary_intel", {})
            category = primary.get("category", "lore_intel")
            if category not in {"lore_intel", ""}:
                continue
            rules = arc.get("placement_rules", {}).get("primary", {})
            avoid_ids = set(rules.get("avoid_node_ids", []))
            require_kinds = set(rules.get("require_kind_any", []))
            max_hops = int(rules.get("max_hops_from_start", 0) or 0)
            candidates = set(rules.get("candidates", []))
            is_candidate = False
            if node_id in avoid_ids:
                is_candidate = False
            elif node_id == "HARBOR_12" and "harbor_12" in candidates:
                is_candidate = True
            elif is_procedural:
                if node.kind == "station" and "procedural_station" in candidates:
                    is_candidate = True
                if node.kind == "relay" and "procedural_relay" in candidates:
                    is_candidate = True
                if node.kind == "derelict" and "procedural_derelict" in candidates:
                    is_candidate = True
            if require_kinds and node.kind not in require_kinds:
                is_candidate = False
            if is_candidate and max_hops > 0:
                hop = self._hop_distance_from_start(state, node_id, max_hops)
                if hop is None:
                    start = state.world.space.nodes.get("UNKNOWN_00")
                    if start:
                        dx = node.x_ly - start.x_ly
                        dy = node.y_ly - start.y_ly
                        dz = node.z_ly - start.z_ly
                        if (dx * dx + dy * dy + dz * dz) ** 0.5 > 20.0:
                            is_candidate = False
                elif hop > max_hops:
                    is_candidate = False

            primary_state = arc_state["primary"]
            primary_id = primary.get("id", "primary")
            primary_key = f"{arc_id}:{primary_id}"
            if primary_state.get("placed") and primary_state.get("node_id") == node_id:
                path = primary_state.get("path")
                content = primary_state.get("content")
                if path and path not in existing_paths and content:
                    files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})
                    existing_paths.add(path)
                if primary_key not in state.world.lore.delivered:
                    state.world.lore.delivered.add(primary_key)
            elif is_candidate and not primary_state.get("placed") and piece_constraints_ok(primary, arc_ctx):
                if is_procedural:
                    arc_state["counters"]["procedural_candidates"] += 1
                seed = self._hash64(state.meta.rng_seed, f"arc:{arc_id}:{node_id}:primary")
                rng = random.Random(seed)
                chance = 0.25
                if rng.random() < chance:
                    pref_sources = primary.get("preferred_sources", ["mail", "log"])
                    source = rng.choice(pref_sources) if pref_sources else "log"
                    if source == "mail":
                        suffix = seed % 100
                        path = f"/mail/inbox/02{suffix:02d}.corridor.{state.os.locale.value}.txt"
                        content = (
                            "FROM: Network Ops\n"
                            "SUBJ: Corridor attachment\n\n"
                            "NAV:\n"
                            "[NAV ATTACHMENT BEGIN]\n"
                            f"{primary.get('line')}\n"
                            "[NAV ATTACHMENT END]\n"
                        )
                    else:
                        path = f"/logs/records/corridor_01.{state.os.locale.value}.txt"
                        content = (
                            "CORRIDOR LOG // attachment\n\n"
                            "[NAV ATTACHMENT BEGIN]\n"
                            f"{primary.get('line')}\n"
                            "[NAV ATTACHMENT END]\n"
                        )
                    files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})
                    existing_paths.add(path)
                    primary_state.update({"placed": True, "node_id": node_id, "path": path, "source": source, "content": content})
                    if primary_key not in state.world.lore.delivered:
                        state.world.lore.delivered.add(primary_key)

            sec_rules = arc.get("placement_rules", {}).get("secondary", {})
            sec_candidates = set(sec_rules.get("candidates", []))
            sec_count = int(sec_rules.get("count", 0) or 0)
            if is_procedural and sec_count > 0:
                sec_is_candidate = False
                if node.kind == "station" and "procedural_station" in sec_candidates:
                    sec_is_candidate = True
                if node.kind == "derelict" and "procedural_derelict" in sec_candidates:
                    sec_is_candidate = True
                if sec_is_candidate:
                    placed_count = len(arc_state["secondary"])
                    for doc in arc.get("secondary_lore_docs", []):
                        doc_id = doc.get("id")
                        if not doc_id or placed_count >= sec_count:
                            break
                        if doc_id in arc_state["secondary"]:
                            continue
                        if not piece_constraints_ok(doc, arc_ctx):
                            continue
                        seed = self._hash64(state.meta.rng_seed, f"arc:{arc_id}:{node_id}:{doc_id}")
                        rng = random.Random(seed)
                        if rng.random() < 0.30:
                            lang = state.os.locale.value
                            template = doc.get("path_template", "")
                            path = template.replace("{lang}", lang)
                            if "02xx" in path:
                                path = path.replace("02xx", f"02{seed % 100:02d}")
                            content_ref = doc.get(f"content_ref_{lang}") or doc.get("content_ref_en")
                            content = ""
                            if content_ref:
                                try:
                                    content = (Path(__file__).resolve().parents[3] / "data" / content_ref).read_text(encoding="utf-8")
                                except Exception:
                                    content = ""
                            if path and path not in existing_paths:
                                files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})
                                existing_paths.add(path)
                                arc_state["secondary"][doc_id] = {"node_id": node_id, "path": path, "content": content}
                                placed_count += 1
                                sec_key = f"{arc_id}:{doc_id}"
                                if sec_key not in state.world.lore.delivered:
                                    state.world.lore.delivered.add(sec_key)
                    for doc_id, info in arc_state["secondary"].items():
                        if info.get("node_id") == node_id:
                            path = info.get("path")
                            content = info.get("content")
                            if path and path not in existing_paths and content:
                                files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})
                                existing_paths.add(path)
                            sec_key = f"{arc_id}:{doc_id}"
                            if sec_key not in state.world.lore.delivered:
                                state.world.lore.delivered.add(sec_key)
        return files

    def _procedural_fs_files(self, state: GameState, node) -> list[dict]:
        h = hashlib.blake2b(digest_size=8)
        h.update(str(state.meta.rng_seed).encode("utf-8"))
        h.update(node.node_id.encode("utf-8"))
        seed = int.from_bytes(h.digest(), "big", signed=False)
        rng = random.Random(seed)
        files: list[dict] = []

        def _add(path: str, content: str) -> None:
            files.append({"path": path, "access": AccessLevel.GUEST.value, "content": content})

        link_line = ""
        if node.links:
            link = sorted(node.links)[0]
            link_line = f"LINK: {node.node_id} -> {link}\n"

        # Nav log (common)
        p_log = Balance.SALVAGE_DATA_LOG_P_STATION_SHIP if node.kind in {"station", "ship"} else Balance.SALVAGE_DATA_LOG_P_OTHER
        if rng.random() < p_log:
            content = link_line or f"NODE: {node.node_id}\n"
            _add("/logs/nav.log", content)

        # Mail (occasional)
        p_mail = Balance.SALVAGE_DATA_MAIL_P_STATION_SHIP if node.kind in {"station", "ship"} else Balance.SALVAGE_DATA_MAIL_P_OTHER
        if rng.random() < p_mail:
            lang = state.os.locale.value
            content = (
                f"FROM: {node.name}\n"
                "SUBJ: Recovered Data Cache\n\n"
                f"Automated report from {node.name} ({node.kind}).\n"
                f"Region: {node.region}\n"
            )
            _add(f"/mail/inbox/0001.{lang}.txt", content)

        # Nav fragment (rare)
        p_frag = (
            Balance.SALVAGE_DATA_FRAG_P_STATION_DERELICT
            if node.kind in {"station", "derelict"}
            else Balance.SALVAGE_DATA_FRAG_P_OTHER
        )
        if rng.random() < p_frag:
            frag_id = f"{rng.getrandbits(16):04x}"
            content = link_line or f"NODE: {node.node_id}\n"
            _add(f"/data/nav/fragments/frag_{frag_id}.txt", content)

        # Guarantee at least one LINK if links exist.
        if link_line and not any("LINK:" in f.get("content", "") for f in files):
            frag_id = f"{rng.getrandbits(16):04x}"
            _add(f"/data/nav/fragments/frag_{frag_id}.txt", link_line)

        return files

    def _build_lore_context(self, state: GameState, node_id: str) -> LoreContext:
        node = state.world.space.nodes.get(node_id)
        if node:
            region = node.region or region_for_pos(node.x_ly, node.y_ly, node.z_ly)
            dist = math.sqrt(node.x_ly * node.x_ly + node.y_ly * node.y_ly + node.z_ly * node.z_ly)
        else:
            region = ""
            dist = 0.0
        year = state.clock.t / Balance.YEAR_S if Balance.YEAR_S else 0.0
        return LoreContext(node_id=node_id, region=region, dist_from_origin_ly=dist, year_since_wake=year)

    def _clear_tmp_node(self, state: GameState) -> None:
        tmp_id = state.world.active_tmp_node_id
        if not tmp_id:
            return
        state.world.space.nodes.pop(tmp_id, None)
        state.world.known_links.pop(tmp_id, None)
        state.world.active_tmp_node_id = None
        state.world.active_tmp_from = None
        state.world.active_tmp_to = None
        state.world.active_tmp_progress = None

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
        if job.job_type == JobType.REPAIR_DRONE and job.target:
            target_drone = state.ship.drones.get(job.target.id)
            if target_drone:
                drone_id = job.params.get("drone_id")
                operator = state.ship.drones.get(drone_id) if drone_id else None
                if operator:
                    operator.battery = max(0.0, operator.battery - Balance.DRONE_BATTERY_DRAIN_REPAIR)
                repair_amount = float(job.params.get("repair_amount", 0.15))
                target_drone.integrity = min(1.0, target_drone.integrity + repair_amount)
                events.append(
                    self._make_event(
                        state,
                        EventType.JOB_COMPLETED,
                        Severity.INFO,
                        SourceRef(kind="drone", id=target_drone.drone_id),
                        f"Drone repair completed for {target_drone.drone_id}",
                        data={
                            "job_id": job.job_id,
                            "job_type": job.job_type.value,
                            "drone_id": target_drone.drone_id,
                            "message_key": "job_completed_drone_repair",
                        },
                    )
                )
            return events

        if job.job_type == JobType.RECOVER_AUTH:
            level = str(job.params.get("level", "")).upper()
            if not level:
                return events
            already = level in state.os.auth_levels
            if not already:
                state.os.auth_levels.add(level)
            message = f"Credential cache restored: {level}" if not already else f"{level} already available"
            events.append(
                self._make_event(
                    state,
                    EventType.JOB_COMPLETED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    message,
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "level": level,
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
                    if "ECHO_7" not in state.world.known_contacts and (
                        not hasattr(state.world, "known_nodes") or "ECHO_7" not in state.world.known_nodes
                    ):
                        state.world.known_contacts.add("ECHO_7")
                        if hasattr(state.world, "known_nodes"):
                            state.world.known_nodes.add("ECHO_7")
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
                events.extend(self._apply_drone_bay_damaged_integrity_risk(state, job, drone, "deploy"))
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
                    events.extend(self._apply_drone_bay_damaged_integrity_risk(state, job, drone, "recall"))
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
            state.ship.docked_node_id = job.target.id
            node = state.world.space.nodes.get(job.target.id)
            if node:
                state.world.current_pos_ly = (node.x_ly, node.y_ly, node.z_ly)
                if node.kind != "transit":
                    state.world.visited_nodes.add(node.node_id)
            if state.world.active_tmp_node_id and job.target.id != state.world.active_tmp_node_id:
                self._clear_tmp_node(state)
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
            lore_ctx = self._build_lore_context(state, job.target.id)
            lore_result = maybe_deliver_lore(state, "dock", lore_ctx)
            events.extend(lore_result.events)
            events.extend(evaluate_dead_nodes(state, "dock", debug=state.os.debug_enabled))
            return events

        if job.job_type == JobType.UNDOCK and job.target:
            node_id = job.params.get("node_id", job.target.id)
            state.ship.docked_node_id = None
            events.append(
                self._make_event(
                    state,
                    EventType.UNDOCKED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    f"Undocked from {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "undocked",
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

        if job.job_type == JobType.SALVAGE_DATA and job.target:
            node_id = job.params.get("node_id", job.target.id)
            node = state.world.space.nodes.get(node_id)
            files = self._location_fs_files(node_id)
            is_location = self._is_location_node(node_id)
            is_procedural = not is_location
            if not files and node and is_procedural:
                files = self._procedural_fs_files(state, node)
            files = self._maybe_inject_arc_content(state, node_id, node, files, is_procedural)
            lore_ctx = self._build_lore_context(state, node_id)
            lore_result = maybe_deliver_lore(state, "salvage_data", lore_ctx)
            files.extend(lore_result.files)
            mount_root = normalize_path(f"/remote/{node_id}")
            if "/remote" not in state.os.fs:
                state.os.fs["/remote"] = FSNode(path="/remote", node_type=FSNodeType.DIR, access=AccessLevel.GUEST)
            if mount_root not in state.os.fs:
                state.os.fs[mount_root] = FSNode(path=mount_root, node_type=FSNodeType.DIR, access=AccessLevel.GUEST)
            count = mount_files(state.os.fs, mount_root, files)
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_SALVAGE)
            tip = None
            if node_id not in state.world.salvage_tip_nodes:
                state.world.salvage_tip_nodes.add(node_id)
                tip = f"Tip: ls /remote/{node_id}/mail or /remote/{node_id}/logs"
            events.append(
                self._make_event(
                    state,
                    EventType.DATA_SALVAGED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    f"Data salvaged: {count} files mounted at {mount_root}/",
                    data={"node_id": node_id, "files_count": count, "mount_root": mount_root, "tip": tip},
                )
            )
            events.extend(lore_result.events)
            events.extend(evaluate_dead_nodes(state, "salvage_data", debug=state.os.debug_enabled))
            return events

        if job.job_type == JobType.ROUTE_SOLVE and job.target:
            node_id = job.params.get("node_id", job.target.id)
            from_id = job.params.get("from_id", state.world.current_node_id)
            if add_known_link(state.world, from_id, node_id, bidirectional=True):
                state.world.known_nodes.add(node_id)
                state.world.known_contacts.add(node_id)
            self._maybe_set_fine_range(state, from_id, node_id)
            events.append(
                self._make_event(
                    state,
                    EventType.JOB_COMPLETED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    f"Route solved: {from_id} -> {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "from_id": from_id,
                        "node_id": node_id,
                        "message_key": "job_completed_route",
                    },
                )
            )
            events.extend(evaluate_dead_nodes(state, "route", debug=state.os.debug_enabled))
            return events

        if job.job_type == JobType.INSTALL_MODULE and job.target:
            module_id = job.params.get("module_id")
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_REPAIR)
            if module_id and module_id in state.ship.cargo_modules:
                modules = load_modules()
                mod = modules.get(module_id, {})
                effects = mod.get("effects", {})
                if "power_quality_offset" in effects:
                    state.ship.power.quality_offset += float(effects["power_quality_offset"])
                if "e_batt_bonus_kwh" in effects:
                    state.ship.power.e_batt_max_kwh += float(effects["e_batt_bonus_kwh"])
                if "p_gen_bonus_kw" in effects:
                    state.ship.power.p_gen_bonus_kw += float(effects["p_gen_bonus_kw"])
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
        job_load_kw = 0.0
        for job in state.jobs.jobs.values():
            if job.status == JobStatus.RUNNING and job.power_draw_kw > 0.0:
                job_load_kw += job.power_draw_kw
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
            return sum(sys.p_effective_kw() * _factor(sys) for sys in systems) + job_load_kw
        return sum(system.p_effective_kw() for system in systems if system.state != SystemState.OFFLINE) + job_load_kw

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
            system.forced_offline = True
            system.auto_offline_reason = "load_shed"
            p_load -= prev_load
            events.append(
                self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Load shedding: {system.system_id} -> OFFLINE",
                    data={
                        "from": old_state.value,
                        "to": system.state.value,
                        "cause": "load_shed",
                        "health": system.health,
                    },
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

    def _apply_degradation(
        self,
        state: GameState,
        dt: float,
        power_quality: float,
        brownout_sustained: bool,
    ) -> list[Event]:
        r_env = state.ship.radiation_env_rad_per_s
        r_env_norm = self._clamp(r_env / Balance.R_REF)
        events: list[Event] = []
        wear_mult = 1.0
        if state.ship.in_transit and state.ship.op_mode != "CRUISE":
            wear_mult = Balance.TRANSIT_WEAR_MULT_NORMAL
        for system in state.ship.systems.values():
            s_factor = 1.0 + system.k_power * (1.0 - power_quality) + system.k_rad * r_env_norm
            if brownout_sustained:
                if system.system_id == "energy_distribution":
                    s_factor *= Balance.BROWNOUT_DEGRADE_MULT_DISTRIBUTION
                elif system.system_id == "power_core":
                    s_factor *= Balance.BROWNOUT_DEGRADE_MULT_POWER_CORE
            system.health = max(
                0.0,
                system.health - system.base_decay_per_s * s_factor * wear_mult * dt,
            )
            self._apply_health_state(system, state, events, cause="degradation")
        return events

    def _apply_radiation(self, state: GameState, dt: float) -> None:
        r_env = state.ship.radiation_env_rad_per_s
        for drone in state.ship.drones.values():
            drone.dose_rad += r_env * drone.shield_factor * dt

    def _update_drone_maintenance(self, state: GameState, dt: float) -> None:
        for drone in state.ship.drones.values():
            if drone.status == DroneStatus.DEPLOYED:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S * dt)
        bay_state = self._drone_bay_state(state)
        if bay_state == SystemState.OFFLINE:
            return
        distribution = state.ship.systems.get("energy_distribution")
        if distribution and distribution.state == SystemState.OFFLINE:
            return
        net_kw = state.ship.power.p_gen_kw - state.ship.power.p_load_kw
        soc = (
            state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh
            if state.ship.power.e_batt_max_kwh > 0
            else 0.0
        )
        charge_rate = 0.0
        if net_kw >= Balance.DRONE_CHARGE_KW:
            charge_rate = Balance.DRONE_BATTERY_CHARGE_PER_S
        elif soc > 0.0 and net_kw >= Balance.DRONE_CHARGE_NET_MIN_KW:
            charge_rate = Balance.DRONE_BATTERY_CHARGE_PER_S * Balance.DRONE_BATTERY_CHARGE_LOW_MULT
        charge_rate *= self._drone_bay_charge_rate_mult(state)
        for drone in state.ship.drones.values():
            if drone.status == DroneStatus.DOCKED:
                # charge battery
                if charge_rate > 0.0:
                    drone.battery = min(1.0, drone.battery + charge_rate * dt)
                # passive bay repair profile depends on drone_bay state
                if drone.integrity < 1.0:
                    repair_rate_mult, repair_scrap_mult, fail_p, fail_hit = self._drone_bay_repair_profile(state)
                    if repair_rate_mult <= 0.0:
                        continue
                    scrap_cost = max(1, int(round(repair_scrap_mult)))
                    if state.ship.cargo_scrap < scrap_cost:
                        continue
                    state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - scrap_cost)
                    state.ship.manifest_dirty = True
                    if fail_p > 0.0 and self._rng(state).random() < fail_p:
                        drone.integrity = max(0.0, drone.integrity - fail_hit)
                        continue
                    repair_gain = Balance.DRONE_REPAIR_INTEGRITY_PER_SCRAP * repair_rate_mult
                    drone.integrity = min(1.0, drone.integrity + repair_gain)

    def _update_drone_battery_alerts(self, state: GameState) -> list[Event]:
        events: list[Event] = []
        threshold = Balance.DRONE_LOW_BATTERY_THRESHOLD
        for drone in state.ship.drones.values():
            if drone.battery <= threshold:
                if not drone.low_battery_warned:
                    event = self._make_event(
                        state,
                        EventType.DRONE_LOW_BATTERY,
                        Severity.WARN,
                        SourceRef(kind="drone", id=drone.drone_id),
                        f"Drone low battery: {drone.drone_id}",
                        data={
                            "message_key": "drone_low_battery",
                            "drone_id": drone.drone_id,
                            "battery": drone.battery,
                            "threshold": threshold,
                        },
                    )
                    events.append(event)
                    drone.low_battery_warned = True
                if drone.status == DroneStatus.DEPLOYED and drone.battery <= 0.0:
                    drone.status = DroneStatus.DISABLED
                    events.append(
                        self._make_event(
                            state,
                            EventType.DRONE_DISABLED,
                            Severity.WARN,
                            SourceRef(kind="drone", id=drone.drone_id),
                            f"Drone disabled: {drone.drone_id}",
                            data={
                                "message_key": "drone_disabled",
                                "reason": "battery_depleted",
                                "drone_id": drone.drone_id,
                            },
                        )
                    )
            else:
                if drone.low_battery_warned:
                    drone.low_battery_warned = False
        return events

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
            severity = Severity.CRITICAL if power_quality < Balance.POWER_QUALITY_COLLAPSE_THRESHOLD else Severity.WARN
            message = "Power quality critical" if severity == Severity.CRITICAL else "Low power quality"
            existing = state.events.alerts.get(EventType.LOW_POWER_QUALITY.value)
            if not existing or not existing.is_active:
                events.extend(
                    self._ensure_alert(
                        state,
                        EventType.LOW_POWER_QUALITY,
                        severity,
                        SourceRef(kind="ship", id=state.ship.ship_id),
                        message,
                        data={"power_quality": power_quality, "message_key": "low_power_quality"},
                    )
                )
            active_keys.add(EventType.LOW_POWER_QUALITY.value)

        soc = self._soc(state)
        if soc <= 0.0 and p_load <= p_gen:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.BATTERY_RESERVE_EXHAUSTED,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Battery reserve exhausted",
                    data={"message_key": "battery_reserve_exhausted"},
                )
            )
            active_keys.add(EventType.BATTERY_RESERVE_EXHAUSTED.value)

        if soc < 0.10:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.LOW_SOC_WARNING,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Battery critical: SoC={soc:.2f}. Heavy action may be unsafe.",
                    data={"soc": soc, "message_key": "low_soc_warning"},
                )
            )
            active_keys.add(EventType.LOW_SOC_WARNING.value)
        elif soc < 0.25:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.LOW_SOC_NOTICE,
                    Severity.INFO,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    f"Battery low: SoC={soc:.2f}. Consider reducing load.",
                    data={"soc": soc, "message_key": "low_soc_notice"},
                )
            )
            active_keys.add(EventType.LOW_SOC_NOTICE.value)

        if distribution and distribution.state == SystemState.OFFLINE:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.DRONE_BAY_CHARGING_UNAVAILABLE,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="drone_bay"),
                    "Warning: drone bay charging unavailable while energy_distribution remains offline",
                    data={"message_key": "drone_bay_charging_unavailable"},
                )
            )
            active_keys.add(EventType.DRONE_BAY_CHARGING_UNAVAILABLE.value)

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
        power_draw_kw: float = 0.0,
    ) -> list[Event]:
        job_id = f"J{state.jobs.next_job_seq}"
        state.jobs.next_job_seq += 1
        job = Job(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            eta_s=eta_s,
            owner_id=owner_id,
            target=target,
            params=params,
            power_draw_kw=power_draw_kw,
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

    def _system_dependencies_for_gating(self, system: ShipSystem) -> list[Dependency]:
        deps = list(system.dependencies or [])
        if system.system_id != "drone_bay":
            return deps
        # Backward-compat with old saves/configs: drone_bay no longer depends on distribution nominal.
        filtered: list[Dependency] = []
        for dep in deps:
            if dep.dep_type == "system_state_at_least" and dep.target_id == "energy_distribution":
                continue
            filtered.append(dep)
        return filtered

    def _drone_bay_state(self, state: GameState) -> SystemState:
        drone_bay = state.ship.systems.get("drone_bay")
        if not drone_bay:
            return SystemState.OFFLINE
        if drone_bay.forced_offline or drone_bay.state == SystemState.OFFLINE:
            return SystemState.OFFLINE
        return drone_bay.state

    def _drone_bay_charge_rate_mult(self, state: GameState) -> float:
        bay_state = self._drone_bay_state(state)
        if bay_state == SystemState.LIMITED:
            return Balance.DRONE_BAY_LIMITED_CHARGE_RATE_MULT
        if bay_state in {SystemState.DAMAGED, SystemState.CRITICAL}:
            return Balance.DRONE_BAY_DAMAGED_CHARGE_RATE_MULT
        if bay_state == SystemState.OFFLINE:
            return 0.0
        return 1.0

    def _drone_bay_eta_mult(self, state: GameState) -> float:
        bay_state = self._drone_bay_state(state)
        if bay_state == SystemState.LIMITED:
            return Balance.DRONE_BAY_LIMITED_ETA_MULT
        if bay_state in {SystemState.DAMAGED, SystemState.CRITICAL}:
            return Balance.DRONE_BAY_DAMAGED_ETA_MULT
        return 1.0

    def _drone_bay_repair_profile(self, state: GameState) -> tuple[float, float, float, float]:
        bay_state = self._drone_bay_state(state)
        if bay_state == SystemState.OFFLINE:
            return (0.0, 0.0, 0.0, 0.0)
        if bay_state == SystemState.LIMITED:
            return (Balance.DRONE_BAY_LIMITED_REPAIR_RATE_MULT, 1.0, 0.0, 0.0)
        if bay_state == SystemState.DAMAGED:
            return (
                Balance.DRONE_BAY_DAMAGED_REPAIR_RATE_MULT,
                Balance.DRONE_BAY_DAMAGED_REPAIR_SCRAP_MULT,
                0.0,
                0.0,
            )
        if bay_state == SystemState.CRITICAL:
            return (
                Balance.DRONE_BAY_CRITICAL_REPAIR_RATE_MULT,
                Balance.DRONE_BAY_CRITICAL_REPAIR_SCRAP_MULT,
                Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_P,
                Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_HIT,
            )
        return (1.0, 1.0, 0.0, 0.0)

    def _is_drone_bay_support_required(self, action: Action) -> bool:
        return isinstance(action, (DroneDeploy, DroneRecall, Install, DroneReboot))

    def _emit_drone_bay_support_warning(self, state: GameState, action: Action) -> Event | None:
        if not self._is_drone_bay_support_required(action):
            return None
        bay_state = self._drone_bay_state(state)
        if bay_state == SystemState.LIMITED:
            return self._make_event(
                state,
                EventType.ACTION_WARNING,
                Severity.WARN,
                SourceRef(kind="ship_system", id="drone_bay"),
                "Warning: drone bay degraded; operation will be slower",
                data={"message_key": "drone_bay_degraded_slow"},
            )
        if bay_state in {SystemState.DAMAGED, SystemState.CRITICAL}:
            return self._make_event(
                state,
                EventType.ACTION_WARNING,
                Severity.WARN,
                SourceRef(kind="ship_system", id="drone_bay"),
                "Warning: drone bay damaged; operation will be slower and may cause minor drone integrity loss",
                data={"message_key": "drone_bay_damaged_risk"},
            )
        return None

    def _apply_drone_bay_damaged_integrity_risk(
        self, state: GameState, job: Job, drone, operation: str
    ) -> list[Event]:
        bay_state = str(job.params.get("bay_state_at_start") or "").lower()
        if bay_state not in {SystemState.DAMAGED.value, SystemState.CRITICAL.value}:
            return []
        rng = self._rng(state)
        if rng.random() >= Balance.DRONE_BAY_DAMAGED_INTEGRITY_RISK_P:
            return []
        old_integrity = drone.integrity
        drone.integrity = max(0.0, drone.integrity - Balance.DRONE_BAY_DAMAGED_INTEGRITY_HIT)
        return [
            self._make_event(
                state,
                EventType.DRONE_DAMAGED,
                Severity.WARN,
                SourceRef(kind="drone", id=drone.drone_id),
                f"Drone integrity impacted during bay {operation}: {drone.drone_id} ({old_integrity:.2f}->{drone.integrity:.2f})",
                data={
                    "message_key": "drone_bay_damaged_integrity_hit",
                    "drone_id": drone.drone_id,
                    "operation": operation,
                    "integrity_before": old_integrity,
                    "integrity_after": drone.integrity,
                },
            )
        ]

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

    def _soc(self, state: GameState) -> float:
        if state.ship.power.e_batt_max_kwh > 0:
            return state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh
        return 0.0

    def _is_noncritical_system(self, system: ShipSystem) -> bool:
        if "critical" in system.tags:
            return False
        if system.system_id in {"core_os", "life_support", "power_core", "energy_distribution"}:
            return False
        return True

    def _auto_shed_one_noncritical(self, state: GameState) -> list[Event]:
        events: list[Event] = []
        systems_sorted = sorted(
            state.ship.systems.values(),
            key=lambda s: s.priority,
            reverse=True,
        )
        for system in systems_sorted:
            if system.state == SystemState.OFFLINE:
                continue
            if not self._is_noncritical_system(system):
                continue
            prev_load = system.p_effective_kw()
            old_state = system.state
            system.state = SystemState.OFFLINE
            system.forced_offline = True
            system.auto_offline_reason = "load_shed"
            events.append(
                self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Load shedding: {system.system_id} -> OFFLINE",
                    data={
                        "from": old_state.value,
                        "to": system.state.value,
                        "cause": "load_shed",
                        "health": system.health,
                    },
                )
            )
            state.ship.power.p_load_kw = max(0.0, state.ship.power.p_load_kw - prev_load)
            break
        return events

    def _shed_all_noncritical(self, state: GameState) -> list[Event]:
        events: list[Event] = []
        systems_sorted = sorted(
            state.ship.systems.values(),
            key=lambda s: s.priority,
            reverse=True,
        )
        for system in systems_sorted:
            if system.state == SystemState.OFFLINE:
                continue
            if not self._is_noncritical_system(system):
                continue
            old_state = system.state
            system.state = SystemState.OFFLINE
            system.forced_offline = True
            system.auto_offline_reason = "load_shed"
            if system.service:
                system.service.is_running = False
            events.append(
                self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Load shedding: {system.system_id} -> OFFLINE",
                    data={
                        "from": old_state.value,
                        "to": system.state.value,
                        "cause": "load_shed",
                        "health": system.health,
                    },
                )
            )
        return events

    def _apply_critical_system_consequences(self, state: GameState, dt: float) -> list[Event]:
        events: list[Event] = []
        core_os = state.ship.systems.get("core_os")
        life_support = state.ship.systems.get("life_support")

        if life_support and life_support.state == SystemState.CRITICAL:
            state.ship.life_support_critical_s += dt
        else:
            state.ship.life_support_critical_s = 0.0

        if not state.os.terminal_lock:
            if core_os and core_os.state == SystemState.OFFLINE:
                state.os.terminal_lock = True
                state.os.terminal_reason = "core_os_offline"
            elif life_support and life_support.state == SystemState.OFFLINE:
                state.os.terminal_lock = True
                state.os.terminal_reason = "life_support_offline"
            elif (
                life_support
                and life_support.state == SystemState.CRITICAL
                and state.ship.life_support_critical_s >= Balance.LIFE_SUPPORT_CRITICAL_GRACE_S
            ):
                state.os.terminal_lock = True
                state.os.terminal_reason = "life_support_critical"

        return events

    def _enforce_distribution_collapse(self, state: GameState) -> list[Event]:
        events: list[Event] = []
        distribution = state.ship.systems.get("energy_distribution")
        if not distribution or distribution.state != SystemState.OFFLINE:
            for system in state.ship.systems.values():
                if system.auto_offline_reason != "energy_distribution_offline":
                    continue
                system.auto_offline_reason = None
                system.forced_offline = False
                # Restore only if health allows.
                self._apply_health_state(system, state, events, cause="distribution_restored")
            return events

        for system in state.ship.systems.values():
            if not self._is_noncritical_system(system):
                continue
            if system.forced_offline and system.auto_offline_reason is None:
                continue
            if system.state == SystemState.OFFLINE and system.auto_offline_reason == "energy_distribution_offline":
                continue
            old_state = system.state
            system.state = SystemState.OFFLINE
            system.forced_offline = True
            system.auto_offline_reason = "energy_distribution_offline"
            if system.service:
                system.service.is_running = False
            events.append(
                self._make_event(
                    state,
                    EventType.SYSTEM_STATE_CHANGED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id=system.system_id),
                    f"Power collapse: {system.system_id} -> OFFLINE",
                    data={
                        "from": old_state.value,
                        "to": system.state.value,
                        "cause": "energy_distribution_offline",
                        "health": system.health,
                    },
                )
            )
        return events

    def _power_blocked_event(
        self,
        state: GameState,
        message: str,
        reason: str,
        data: dict | None = None,
    ) -> Event:
        payload = {"message_key": "boot_blocked", "reason": reason}
        if data:
            payload.update(data)
        event = self._make_event(
            state,
            EventType.BOOT_BLOCKED,
            Severity.WARN,
            SourceRef(kind="ship", id=state.ship.ship_id),
            message,
            data=payload,
        )
        self._record_event(state.events, event)
        return event

    def _check_power_action_block(self, state: GameState, action: Action) -> Event | None:
        power_quality = state.ship.power.power_quality

        if state.os.terminal_lock:
            return self._power_blocked_event(
                state,
                "Action blocked: terminal state active",
                "terminal_state",
            )

        if isinstance(action, AuthRecover) and power_quality < Balance.POWER_QUALITY_BLOCK_THRESHOLD:
            return self._power_blocked_event(
                state,
                f"Action blocked: power quality too low (requires Q >= {Balance.POWER_QUALITY_BLOCK_THRESHOLD:.2f})",
                "power_quality_low",
                data={"q": power_quality, "required": Balance.POWER_QUALITY_BLOCK_THRESHOLD},
            )

        if (
            isinstance(action, DroneDeploy)
            and not action.emergency
            and self._drone_bay_state(state) == SystemState.OFFLINE
        ):
            return self._power_blocked_event(
                state,
                "Action blocked: drone bay offline; use 'drone deploy!' for emergency launch",
                "drone_bay_deploy_offline",
            )

        if is_critical_power_state(state) and not is_action_allowed_in_critical_state(state, action):
            return self._power_blocked_event(
                state,
                "Action blocked: non-essential operations disabled during critical power state",
                "critical_power_state",
            )

        if power_quality < Balance.POWER_QUALITY_CRITICAL_THRESHOLD:
            if isinstance(action, Hibernate):
                return self._power_blocked_event(
                    state,
                    "Hibernate blocked: power quality too low",
                    "power_quality_critical",
                    data={"q": power_quality, "required": Balance.POWER_QUALITY_CRITICAL_THRESHOLD},
                )
            if isinstance(action, Boot):
                system = self._find_system_by_service(state.ship.systems.values(), action.service_name)
                if system and self._is_noncritical_system(system):
                    return self._power_blocked_event(
                        state,
                        "Boot blocked: power quality too low",
                        "power_quality_critical",
                        data={
                            "q": power_quality,
                            "required": Balance.POWER_QUALITY_CRITICAL_THRESHOLD,
                            "service": action.service_name,
                        },
                    )

        if power_quality < Balance.POWER_QUALITY_BLOCK_THRESHOLD:
            if isinstance(action, RouteSolve):
                return self._power_blocked_event(
                    state,
                    "Action blocked: power quality too low",
                    "power_quality_low",
                    data={"q": power_quality, "required": Balance.POWER_QUALITY_BLOCK_THRESHOLD},
                )

        return None

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
        if distribution:
            if distribution.state == SystemState.CRITICAL:
                power_quality -= 0.20
            elif distribution.state in (SystemState.DAMAGED, SystemState.LIMITED):
                power_quality -= 0.10

        power_quality += state.ship.power.quality_offset
        return self._clamp(power_quality)

    def _compute_p_gen(self, state: GameState) -> float:
        base = state.ship.power.p_gen_base_kw + state.ship.power.p_gen_bonus_kw
        core = state.ship.systems.get("power_core")
        if not core or core.forced_offline or core.state == SystemState.OFFLINE:
            mult = Balance.POWER_CORE_MULT_OFFLINE
        elif core.state == SystemState.CRITICAL:
            mult = Balance.POWER_CORE_MULT_CRITICAL
        elif core.state == SystemState.DAMAGED:
            mult = Balance.POWER_CORE_MULT_DAMAGED
        elif core.state == SystemState.LIMITED:
            mult = Balance.POWER_CORE_MULT_LIMITED
        else:
            mult = Balance.POWER_CORE_MULT_NOMINAL
        return max(0.0, base * mult)

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
        if h <= Balance.SYSTEM_HEALTH_OFFLINE:
            new_state = SystemState.OFFLINE
        elif h < Balance.SYSTEM_HEALTH_CRITICAL:
            new_state = SystemState.CRITICAL
        elif h < Balance.SYSTEM_HEALTH_DAMAGED:
            new_state = SystemState.DAMAGED
        elif h < Balance.SYSTEM_HEALTH_LIMITED:
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
