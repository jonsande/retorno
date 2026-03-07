from __future__ import annotations

import random
import hashlib
from typing import Iterable
import difflib
import math

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
    DroneSurvey,
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
    SalvageDrone,
    RouteSolve,
    SalvageModule,
    SalvageScrap,
    Status,
    Travel,
    TravelAbort,
    JobCancel,
)
from retorno.core.gamestate import GameState
from retorno.core.lore import (
    LoreContext,
    build_procedural_salvage_mail_content,
    build_lore_context,
    close_window_on_orbit_entry,
    collect_node_salvage_data_files,
    maybe_deliver_lore,
    mount_projection_breakdown,
    project_mountable_data_paths,
    recompute_node_completion,
    run_lore_scheduler_tick,
    survey_recoverable_data_count,
    survey_reports_data_signatures,
)
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.power_policy import (
    is_action_allowed_in_critical_state,
    is_critical_power_state,
    is_critical_system_id,
)
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import AlertState, Event, EventManagerState, EventType, Severity, SourceRef
from retorno.model.jobs import Job, JobManagerState, JobStatus, JobType, RiskProfile, TargetRef
from retorno.model.world import add_known_link, is_hop_within_cap, SpaceNode, sector_id_for_pos
from retorno.runtime.data_loader import load_locations, load_modules
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
                    close_window_on_orbit_entry(state, node.node_id)
            self._clear_tmp_node(state)
            self._drop_initial_unknown_node(state)
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
        run_lore_scheduler_tick(state)

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
        env_rad = self._compute_env_radiation_rad_per_s(state)
        state.ship.radiation_env_rad_per_s = env_rad
        internal_rad = self._compute_internal_radiation_rad_per_s(state, env_rad)
        events.extend(self._update_ship_radiation_level_alerts(state, env_rad, internal_rad))
        self._apply_hull_degradation(state, dt, env_rad)
        events.extend(self._apply_degradation(state, dt, power_quality, brownout_sustained, internal_rad))
        self._apply_radiation(state, dt, env_rad)
        self._update_drone_maintenance(state, dt)
        events.extend(self._update_drone_radiation_level_alerts(state))
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
            if state.ship.docked_node_id:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Travel blocked: ship is docked. Undock before starting travel.",
                    data={"message_key": "boot_blocked", "reason": "ship_docked", "node_id": state.ship.docked_node_id},
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
            if distance_ly > float(Balance.MAX_ROUTE_HOP_LY):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Travel blocked: route hop exceeds cap ({distance_ly:.2f}ly > {Balance.MAX_ROUTE_HOP_LY:.1f}ly)",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "hop_cap_exceeded",
                        "node_id": action.node_id,
                        "distance_ly": distance_ly,
                        "max_hop_ly": float(Balance.MAX_ROUTE_HOP_LY),
                    },
                )
                self._record_event(state.events, event)
                return [event]
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
            transit_env_rad = self._compute_env_radiation_rad_per_s(state)
            tmp_node = SpaceNode(
                node_id=tmp_id,
                name="Nav Point",
                kind="transit",
                radiation_rad_per_s=max(Balance.PROCEDURAL_RAD_MIN, transit_env_rad),
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
            if distance_ly > float(Balance.MAX_ROUTE_HOP_LY):
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=action.node_id),
                    f"Route solve blocked: hop exceeds cap ({distance_ly:.2f}ly > {Balance.MAX_ROUTE_HOP_LY:.1f}ly)",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "hop_cap_exceeded",
                        "node_id": action.node_id,
                        "distance_ly": distance_ly,
                        "max_hop_ly": float(Balance.MAX_ROUTE_HOP_LY),
                    },
                )
                self._record_event(state.events, event)
                return [event]
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
            if target_id == state.ship.ship_id:
                # Alias to bring the drone back to the ship via bay sector.
                bay_sector_id = next(
                    (
                        sid
                        for sid, sector in state.ship.sectors.items()
                        if "bay" in getattr(sector, "tags", set())
                    ),
                    "DRN-BAY",
                )
                target_id = bay_sector_id
            if target_id in state.ship.sectors:
                if drone.location.kind == "world_node":
                    if state.ship.docked_node_id != drone.location.id:
                        event = self._make_event(
                            state,
                            EventType.BOOT_BLOCKED,
                            Severity.WARN,
                            SourceRef(kind="drone", id=drone.drone_id),
                            f"Drone move blocked: ship not docked at {drone.location.id}",
                            data={"message_key": "boot_blocked", "reason": "not_docked", "node_id": drone.location.id},
                        )
                        self._record_event(state.events, event)
                        return [event]
                elif drone.location.kind != "ship_sector":
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

        if isinstance(action, DroneSurvey):
            drone = state.ship.drones.get(action.drone_id)
            if not drone:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="drone", id=action.drone_id),
                    f"Survey blocked: drone {action.drone_id} not found",
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
                    f"Survey blocked: {drone.drone_id} not deployed",
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
                    f"Survey blocked: {drone.drone_id} battery too low",
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
                    f"Survey blocked: {drone.drone_id} not at a node",
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
                    f"Survey blocked: node {node_id} not found",
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
                    f"Survey blocked: {drone.drone_id} not at node {node_id} (current {loc})",
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
                    f"Survey blocked: ship not docked at {node_id}",
                    data={"message_key": "boot_blocked", "reason": "ship_not_docked", "node_id": node_id},
                )
                self._record_event(state.events, event)
                return [event]
            return self._enqueue_job(
                state,
                JobType.SURVEY_DRONE,
                TargetRef(kind="world_node", id=node_id),
                owner_id=action.drone_id,
                eta_s=Balance.DRONE_SURVEY_TIME_S,
                params={"node_id": node_id, "drone_id": action.drone_id},
            )

        if isinstance(action, SalvageDrone):
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
            if node.recoverable_drones_count <= 0:
                event = self._make_event(
                    state,
                    EventType.BOOT_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="world", id=node_id),
                    "No recoverable drones available",
                    data={
                        "message_key": "boot_blocked",
                        "reason": "recoverable_drones_empty",
                        "node_id": node_id,
                    },
                )
                self._record_event(state.events, event)
                return [event]
            available = int(node.recoverable_drones_count)
            eta = Balance.DRONE_SALVAGE_DRONE_BASE_TIME_S + Balance.DRONE_SALVAGE_DRONE_PER_UNIT_S * available
            return self._enqueue_job(
                state,
                JobType.SALVAGE_DRONE,
                TargetRef(kind="world_node", id=node_id),
                owner_id=action.drone_id,
                eta_s=eta,
                params={
                    "node_id": node_id,
                    "drone_id": action.drone_id,
                    "available_at_enqueue": available,
                },
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
        route_solve_running = False

        for job_id in list(jobs_state.active_job_ids):
            job = jobs_state.jobs.get(job_id)
            if not job:
                continue
            if job.status == JobStatus.RUNNING and job.owner_id:
                running_by_owner.add(job.owner_id)
            if job.status == JobStatus.RUNNING and job.job_type == JobType.ROUTE_SOLVE:
                route_solve_running = True

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
                if job.job_type == JobType.ROUTE_SOLVE and route_solve_running:
                    continue
                job.status = JobStatus.RUNNING
                if job.owner_id:
                    running_by_owner.add(job.owner_id)
                if job.job_type == JobType.ROUTE_SOLVE:
                    route_solve_running = True
            if job.params.get("emergency"):
                failed_event = self._maybe_fail_emergency_job(state, job, dt)
                if failed_event:
                    events.append(failed_event)
                    completed.append(job_id)
                    continue

            job.eta_s -= dt
            if job.eta_s <= 0:
                failed_event = self._maybe_fail_repair_job(state, job)
                if failed_event is not None:
                    job.status = JobStatus.FAILED
                    events.append(failed_event)
                    completed.append(job_id)
                    continue
                job.status = JobStatus.COMPLETED
                completed.append(job_id)
                events.extend(self._apply_job_effect(state, job))

        for job_id in completed:
            if job_id in jobs_state.active_job_ids:
                jobs_state.active_job_ids.remove(job_id)

        return events

    def _check_job_interruption(self, state: GameState, job: Job) -> Event | None:
        if job.job_type == JobType.ROUTE_SOLVE:
            node_id = job.params.get("node_id", job.target.id if job.target else "")
            system = state.ship.systems.get("sensors")
            if not system or self._state_rank(system.state) < self._state_rank(SystemState.LIMITED):
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="sensors"),
                    f"Route solve interrupted: sensors unavailable for {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_route_sensors_unavailable",
                        "reason": "sensors_offline",
                    },
                )
                self._record_event(state.events, event)
                return event
            if not system.service or system.service.service_name != "sensord" or not system.service.is_running:
                event = self._make_event(
                    state,
                    EventType.JOB_FAILED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="sensors"),
                    f"Route solve interrupted: sensord stopped during solve for {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "message_key": "job_failed_route_sensord_stopped",
                        "reason": "sensord_not_running",
                    },
                )
                self._record_event(state.events, event)
                return event
            return None

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

    def _drain_repair_operator_battery(self, state: GameState, job: Job) -> None:
        drone_id = str(job.params.get("drone_id", "") or "")
        if not drone_id:
            return
        drone = state.ship.drones.get(drone_id)
        if drone:
            drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_REPAIR)

    def _maybe_fail_repair_job(self, state: GameState, job: Job) -> Event | None:
        if job.job_type not in {JobType.REPAIR_SYSTEM, JobType.REPAIR_DRONE, JobType.SELFTEST_REPAIR}:
            return None
        fail_p = max(0.0, min(1.0, float(Balance.REPAIR_JOB_FAIL_P_BASE)))
        if fail_p <= 0.0 or self._rng(state).random() >= fail_p:
            return None

        consume_fraction = max(0.0, min(1.0, float(Balance.REPAIR_JOB_FAIL_SCRAP_CONSUME_FRACTION)))
        repair_scrap = int(round(float(job.params.get("repair_scrap", 0) or 0)))
        repair_scrap = max(0, repair_scrap)
        scrap_consumed = int(round(repair_scrap * consume_fraction))
        scrap_consumed = max(0, min(repair_scrap, scrap_consumed))
        scrap_refunded = max(0, repair_scrap - scrap_consumed)
        if scrap_refunded > 0:
            state.ship.cargo_scrap += scrap_refunded

        if job.job_type in {JobType.REPAIR_SYSTEM, JobType.REPAIR_DRONE}:
            self._drain_repair_operator_battery(state, job)

        target_kind = "ship"
        target_id = state.ship.ship_id
        if job.target and job.target.kind == "drone":
            target_kind = "drone"
            target_id = job.target.id
        elif job.target and job.target.kind == "ship_system":
            target_kind = "ship_system"
            target_id = job.target.id

        event = self._make_event(
            state,
            EventType.JOB_FAILED,
            Severity.WARN,
            SourceRef(kind=target_kind, id=target_id),
            (
                f"Repair failed for {target_id}. "
                f"Consumed {scrap_consumed}/{repair_scrap} scrap and refunded {scrap_refunded}."
            ),
            data={
                "job_id": job.job_id,
                "job_type": job.job_type.value,
                "message_key": "job_failed_repair_attempt",
                "target_id": target_id,
                "scrap_required": repair_scrap,
                "scrap_consumed": scrap_consumed,
                "scrap_refunded": scrap_refunded,
                "consume_fraction": consume_fraction,
            },
        )
        self._record_event(state.events, event)
        return event

    def _location_fs_files(self, node_id: str) -> list[dict]:
        for loc in load_locations():
            node_cfg = loc.get("node", {})
            if node_cfg.get("node_id") == node_id:
                return list(loc.get("fs_files") or [])
        return []

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
        has_link_intel = False

        # Nav log (common)
        p_log = Balance.SALVAGE_DATA_LOG_P_STATION_SHIP if node.kind in {"station", "ship"} else Balance.SALVAGE_DATA_LOG_P_OTHER
        if rng.random() < p_log:
            content = link_line or f"NODE: {node.node_id}\n"
            _add("/logs/nav.log", content)
            if "LINK:" in content:
                has_link_intel = True

        # Mail (occasional)
        p_mail = Balance.SALVAGE_DATA_MAIL_P_STATION_SHIP if node.kind in {"station", "ship"} else Balance.SALVAGE_DATA_MAIL_P_OTHER
        if rng.random() < p_mail:
            lang = state.os.locale.value
            content = build_procedural_salvage_mail_content(state, node)
            _add(f"/mail/inbox/0001.{lang}.txt", content)

        # Nav fragment (rare)
        p_frag = (
            Balance.SALVAGE_DATA_FRAG_P_STATION_DERELICT
            if node.kind in {"station", "derelict"}
            else Balance.SALVAGE_DATA_FRAG_P_OTHER
        )
        if rng.random() < p_frag:
            frag_id = f"{rng.getrandbits(16):04x}"
            if link_line and has_link_intel:
                # Avoid semantic duplication when nav.log already carries this route intel.
                content = f"NODE: {node.node_id}\n"
            else:
                content = link_line or f"NODE: {node.node_id}\n"
            _add(f"/data/nav/fragments/frag_{frag_id}.txt", content)
            if "LINK:" in content:
                has_link_intel = True

        # Guarantee at least one LINK if links exist.
        if link_line and not has_link_intel:
            frag_id = f"{rng.getrandbits(16):04x}"
            _add(f"/data/nav/fragments/frag_{frag_id}.txt", link_line)

        return files

    def _build_lore_context(self, state: GameState, node_id: str) -> LoreContext:
        return build_lore_context(state, node_id)

    def _collect_salvage_data_files(self, state: GameState, node_id: str) -> list[dict]:
        return collect_node_salvage_data_files(state, node_id)

    def _project_mountable_data_paths(self, fs: dict[str, FSNode], mount_root: str, files: list[dict]) -> list[str]:
        return project_mountable_data_paths(fs, mount_root, files)

    def _survey_recoverable_data_count(self, state: GameState, node_id: str) -> int:
        return survey_recoverable_data_count(state, node_id)

    def _survey_reports_data_signatures(self, state: GameState, node_id: str, job_id: str, data_available: bool) -> bool:
        return survey_reports_data_signatures(state, node_id, job_id, data_available)

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

    def _drop_initial_unknown_node(self, state: GameState) -> None:
        unknown_id = "UNKNOWN_00"
        if state.world.current_node_id == unknown_id:
            return
        state.world.space.nodes.pop(unknown_id, None)
        state.world.known_contacts.discard(unknown_id)
        if hasattr(state.world, "known_nodes"):
            state.world.known_nodes.discard(unknown_id)
        state.world.visited_nodes.discard(unknown_id)
        state.world.fine_ranges_km.pop(unknown_id, None)
        state.world.known_links.pop(unknown_id, None)
        for links in state.world.known_links.values():
            links.discard(unknown_id)
        if hasattr(state.world, "dead_nodes"):
            state.world.dead_nodes.pop(unknown_id, None)

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
                self._drain_repair_operator_battery(state, job)
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
                self._drain_repair_operator_battery(state, job)
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
            recompute_node_completion(state, node_id)
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
                    close_window_on_orbit_entry(state, node.node_id)
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
            recompute_node_completion(state, job.target.id)
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
            recompute_node_completion(state, node_id)
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
            recompute_node_completion(state, node_id)
            return events

        if job.job_type == JobType.SALVAGE_DATA and job.target:
            node_id = job.params.get("node_id", job.target.id)
            files = self._collect_salvage_data_files(state, node_id)
            mount_root = normalize_path(f"/remote/{node_id}")
            if "/remote" not in state.os.fs:
                state.os.fs["/remote"] = FSNode(path="/remote", node_type=FSNodeType.DIR, access=AccessLevel.GUEST)
            if mount_root not in state.os.fs:
                state.os.fs[mount_root] = FSNode(path=mount_root, node_type=FSNodeType.DIR, access=AccessLevel.GUEST)
            mounted_paths_new, mounted_paths_existing, mounted_paths_total = mount_projection_breakdown(
                state.os.fs,
                mount_root,
                files,
            )
            count = mount_files(state.os.fs, mount_root, files)
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_SALVAGE)
            lore_ctx = self._build_lore_context(state, node_id)
            lore_result = maybe_deliver_lore(state, "salvage_data", lore_ctx, count_trigger=False)
            if count > 0 or lore_result.files or lore_result.events:
                counters = state.world.lore.counters
                counters["salvage_data_count"] = counters.get("salvage_data_count", 0) + 1
            recompute_node_completion(state, node_id)
            events.append(
                self._make_event(
                    state,
                    EventType.DATA_SALVAGED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    (
                        f"Data salvaged at {mount_root}/: "
                        f"new={count}, already_mounted={len(mounted_paths_existing)}, total={len(mounted_paths_total)}"
                    ),
                    data={
                        "node_id": node_id,
                        "files_count": count,
                        "files_new_count": count,
                        "files_already_mounted_count": len(mounted_paths_existing),
                        "files_total_eligible_count": len(mounted_paths_total),
                        "mount_root": mount_root,
                        "mounted_paths": mounted_paths_new,
                        "mounted_paths_new": mounted_paths_new,
                        "mounted_paths_existing": mounted_paths_existing,
                        "tip_key": "data_salvaged_cat",
                    },
                )
            )
            events.extend(lore_result.events)
            events.extend(evaluate_dead_nodes(state, "salvage_data", debug=state.os.debug_enabled))
            return events

        if job.job_type == JobType.SURVEY_DRONE and job.target:
            node_id = job.params.get("node_id", job.target.id)
            node = state.world.space.nodes.get(node_id)
            scrap_available = int(node.salvage_scrap_available) if node else 0
            modules_detected = bool(node.salvage_modules_available) if node else False
            recoverable_drones = int(node.recoverable_drones_count) if node else 0
            recoverable_data_files = self._survey_recoverable_data_count(state, node_id)
            data_signatures_detected = self._survey_reports_data_signatures(
                state,
                node_id,
                job.job_id,
                recoverable_data_files > 0,
            )
            uplink_detected = bool(node and node.kind in {"relay", "station", "waystation"})
            recompute_node_completion(state, node_id)
            pool = state.world.node_pools.get(node_id)
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_SALVAGE)
            events.append(
                self._make_event(
                    state,
                    EventType.JOB_COMPLETED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    f"Survey complete: {node_id}",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "scrap_available": scrap_available,
                        "modules_detected": modules_detected,
                        "recoverable_drones_count": recoverable_drones,
                        "data_recoverable_files_count": recoverable_data_files,
                        "data_signatures_detected": data_signatures_detected,
                        "scrap_complete": bool(pool.scrap_complete) if pool else False,
                        "data_complete": bool(pool.data_complete) if pool else False,
                        "extras_complete": bool(pool.extras_complete) if pool else False,
                        "node_cleaned": bool(pool.node_cleaned) if pool else False,
                        "uplink_detected": uplink_detected,
                        "message_key": "job_completed_drone_survey",
                    },
                )
            )
            return events

        if job.job_type == JobType.SALVAGE_DRONE and job.target:
            node_id = job.params.get("node_id", job.target.id)
            node = state.world.space.nodes.get(node_id)
            recovered_ids: list[str] = []
            recovered_count = 0
            if node and node.recoverable_drones_count > 0:
                recovered_count = int(node.recoverable_drones_count)
                node.recoverable_drones_count = 0
                for _ in range(recovered_count):
                    drone_id = self._next_fleet_drone_id(state)
                    integrity, battery, dose = self._roll_salvaged_drone_stats(state)
                    state.ship.drones[drone_id] = DroneState(
                        drone_id=drone_id,
                        name=f"Drone-{drone_id[1:].zfill(2)}",
                        status=DroneStatus.DOCKED,
                        location=DroneLocation(kind="ship_sector", id="drone_bay"),
                        integrity=integrity,
                        battery=battery,
                        dose_rad=dose,
                        radiation_level=self._drone_dose_level(dose),
                    )
                    recovered_ids.append(drone_id)
            drone_id = job.params.get("drone_id")
            drone = state.ship.drones.get(drone_id) if drone_id else None
            if drone:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_DRAIN_SALVAGE)
            events.append(
                self._make_event(
                    state,
                    EventType.JOB_COMPLETED,
                    Severity.INFO,
                    SourceRef(kind="world", id=node_id),
                    f"Drone salvage complete: recovered {recovered_count} drone(s)",
                    data={
                        "job_id": job.job_id,
                        "job_type": job.job_type.value,
                        "node_id": node_id,
                        "recovered_count": recovered_count,
                        "recovered_ids": recovered_ids,
                        "message_key": "job_completed_drone_salvage",
                    },
                )
            )
            return events

        if job.job_type == JobType.ROUTE_SOLVE and job.target:
            node_id = job.params.get("node_id", job.target.id)
            from_id = job.params.get("from_id", state.world.current_node_id)
            link_added = False
            if is_hop_within_cap(state.world, from_id, node_id, float(Balance.MAX_ROUTE_HOP_LY)):
                link_added = add_known_link(state.world, from_id, node_id, bidirectional=True)
            else:
                events.append(
                    self._make_event(
                        state,
                        EventType.BOOT_BLOCKED,
                        Severity.WARN,
                        SourceRef(kind="world", id=node_id),
                        (
                            f"Route solve rejected: hop exceeds cap "
                            f"({float(job.params.get('distance_ly', 0.0)):.2f}ly > {Balance.MAX_ROUTE_HOP_LY:.1f}ly)"
                        ),
                        data={
                            "message_key": "boot_blocked",
                            "reason": "hop_cap_exceeded",
                            "from_id": from_id,
                            "node_id": node_id,
                            "distance_ly": float(job.params.get("distance_ly", 0.0)),
                            "max_hop_ly": float(Balance.MAX_ROUTE_HOP_LY),
                        },
                    )
                )
            if link_added:
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
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.POWER_NET_DEFICIT,
                    Severity.CRITICAL,
                    SourceRef(kind="ship", id=state.ship.ship_id),
                    "Capacity exceeded, vital systems at risk",
                    data={
                        "message_key": "power_net_deficit",
                        "reason": "capacity_exceeded",
                        "p_load_kw": p_load,
                        "p_capacity_kw": p_capacity,
                    },
                )
            )
        return events

    def _apply_degradation(
        self,
        state: GameState,
        dt: float,
        power_quality: float,
        brownout_sustained: bool,
        internal_rad: float,
    ) -> list[Event]:
        internal_rad_norm = self._clamp(internal_rad / Balance.R_REF)
        events: list[Event] = []
        wear_mult = 1.0
        if state.ship.in_transit and state.ship.op_mode != "CRUISE":
            wear_mult = Balance.TRANSIT_WEAR_MULT_NORMAL
        for system in state.ship.systems.values():
            s_factor = 1.0 + system.k_power * (1.0 - power_quality) + system.k_rad * internal_rad_norm
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

    def _apply_radiation(self, state: GameState, dt: float, env_rad: float) -> None:
        for drone in state.ship.drones.values():
            if drone.status == DroneStatus.DOCKED:
                continue
            drone.dose_rad += env_rad * drone.shield_factor * dt

    def _update_drone_maintenance(self, state: GameState, dt: float) -> None:
        for drone in state.ship.drones.values():
            if drone.status == DroneStatus.DEPLOYED:
                drone.battery = max(0.0, drone.battery - Balance.DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S * dt)
            if drone.status != DroneStatus.DOCKED:
                decay_mult = self._drone_rad_decay_mult(drone.dose_rad)
                drone.integrity = max(
                    0.0,
                    drone.integrity - Balance.DRONE_BASE_DECAY_PER_S * decay_mult * dt,
                )
        support = self._drone_bay_support_snapshot(state)
        charge_rate = float(support["charge_rate"])
        decon_rate = float(support["decon_rate"])
        repair_rate_mult = float(support["repair_rate_mult"])
        repair_scrap_cost = int(support["repair_scrap_cost"])
        repair_fail_p = float(support["repair_fail_p"])
        repair_fail_hit = float(support["repair_fail_hit"])
        for drone in state.ship.drones.values():
            if drone.status == DroneStatus.DOCKED:
                # charge battery
                if charge_rate > 0.0:
                    drone.battery = min(1.0, drone.battery + charge_rate * dt)
                if decon_rate > 0.0:
                    drone.dose_rad = max(0.0, drone.dose_rad - decon_rate * dt)
                # passive bay repair profile depends on drone_bay state
                if drone.integrity < 1.0:
                    if repair_rate_mult <= 0.0:
                        continue
                    if state.ship.cargo_scrap < repair_scrap_cost:
                        continue
                    state.ship.cargo_scrap = max(0, state.ship.cargo_scrap - repair_scrap_cost)
                    state.ship.manifest_dirty = True
                    if repair_fail_p > 0.0 and self._rng(state).random() < repair_fail_p:
                        drone.integrity = max(0.0, drone.integrity - repair_fail_hit)
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
            if (
                drone.status == DroneStatus.DEPLOYED
                and drone.autorecall_enabled
                and drone.battery <= max(0.0, min(1.0, drone.autorecall_threshold))
                and not self._drone_has_active_job(state, drone.drone_id, JobType.RECALL_DRONE)
            ):
                auto_recall_events = self._enqueue_drone_autorecall(state, drone)
                events.extend(auto_recall_events)
        return events

    def _drone_has_active_job(self, state: GameState, drone_id: str, job_type: JobType) -> bool:
        for job_id in state.jobs.active_job_ids:
            job = state.jobs.jobs.get(job_id)
            if not job:
                continue
            if job.owner_id != drone_id:
                continue
            if job.job_type != job_type:
                continue
            if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                return True
        return False

    def _enqueue_drone_autorecall(self, state: GameState, drone) -> list[Event]:
        if drone.integrity < Balance.DRONE_RECALL_MIN_INTEGRITY:
            return []
        if drone.battery < Balance.DRONE_MIN_BATTERY_FOR_RECALL:
            return []
        if drone.location.kind == "world_node" and state.ship.docked_node_id != drone.location.id:
            return []
        pre_events: list[Event] = []
        support_warning = self._emit_drone_bay_support_warning(state, DroneRecall(drone_id=drone.drone_id))
        if support_warning:
            pre_events.append(support_warning)
        bay_state = self._drone_bay_state(state)
        eta = Balance.RECALL_TIME_S * self._drone_bay_eta_mult(state)
        job_id = f"J{state.jobs.next_job_seq}"
        state.jobs.next_job_seq += 1
        job = Job(
            job_id=job_id,
            job_type=JobType.RECALL_DRONE,
            status=JobStatus.QUEUED,
            eta_s=eta,
            owner_id=drone.drone_id,
            target=TargetRef(kind="drone", id=drone.drone_id),
            params={"drone_id": drone.drone_id, "bay_state_at_start": bay_state.value if bay_state else ""},
        )
        state.jobs.jobs[job_id] = job
        state.jobs.active_job_ids.append(job_id)
        queued_event = self._make_event(
            state,
            EventType.JOB_QUEUED,
            Severity.INFO,
            SourceRef(kind="drone", id=drone.drone_id),
            f"Job queued: recall_drone -> drone:{drone.drone_id} (ETA {int(eta)}s)",
            data={
                "job_id": job_id,
                "job_type": JobType.RECALL_DRONE.value,
                "eta_s": eta,
                "target": {"kind": "drone", "id": drone.drone_id},
                "owner_id": drone.drone_id,
                "message_key": "job_queued",
                "reason": "drone_autorecall",
            },
        )
        return pre_events + [queued_event]

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
        elif soc < 0.25 and p_load > p_gen:
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

        maintenance_block_data = self._drone_bay_maintenance_block_data(state)
        if maintenance_block_data:
            events.extend(
                self._ensure_alert(
                    state,
                    EventType.DRONE_BAY_MAINTENANCE_BLOCKED,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="drone_bay"),
                    "Drone bay maintenance blocked: docked drones cannot recover battery or integrity",
                    data=maintenance_block_data,
                )
            )
            active_keys.add(EventType.DRONE_BAY_MAINTENANCE_BLOCKED.value)

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

    def _next_fleet_drone_id(self, state: GameState) -> str:
        max_idx = 0
        for drone_id in state.ship.drones.keys():
            if not drone_id.startswith("D"):
                continue
            suffix = drone_id[1:]
            if not suffix.isdigit():
                continue
            max_idx = max(max_idx, int(suffix))
        candidate = max_idx + 1
        while f"D{candidate}" in state.ship.drones:
            candidate += 1
        return f"D{candidate}"

    def _roll_salvaged_drone_stats(self, state: GameState) -> tuple[float, float, float]:
        rng = self._rng(state)
        integrity_min = self._clamp(Balance.SALVAGED_DRONE_INTEGRITY_MIN)
        integrity_max = self._clamp(Balance.SALVAGED_DRONE_INTEGRITY_MAX)
        if integrity_max < integrity_min:
            integrity_max = integrity_min
        battery_min = self._clamp(Balance.SALVAGED_DRONE_BATTERY_MIN)
        battery_max = self._clamp(Balance.SALVAGED_DRONE_BATTERY_MAX)
        if battery_max < battery_min:
            battery_max = battery_min
        dose_min = max(0.0, float(Balance.SALVAGED_DRONE_DOSE_MIN))
        dose_max = max(0.0, float(Balance.SALVAGED_DRONE_DOSE_MAX))
        if dose_max < dose_min:
            dose_max = dose_min
        integrity = rng.uniform(integrity_min, integrity_max)
        battery = rng.uniform(battery_min, battery_max)
        dose = rng.uniform(dose_min, dose_max)
        return integrity, battery, dose

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

    def _drone_bay_support_snapshot(self, state: GameState) -> dict[str, float | bool | int | SystemState]:
        bay_state = self._drone_bay_state(state)
        distribution = state.ship.systems.get("energy_distribution")
        distribution_offline = bool(distribution and distribution.state == SystemState.OFFLINE)
        net_kw = state.ship.power.p_gen_kw - state.ship.power.p_load_kw
        soc = (
            state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh
            if state.ship.power.e_batt_max_kwh > 0.0
            else 0.0
        )
        bay_mult = self._drone_bay_charge_rate_mult(state)
        charge_rate = 0.0
        decon_rate = 0.0
        repair_rate_mult = 0.0
        repair_scrap_mult = 0.0
        repair_fail_p = 0.0
        repair_fail_hit = 0.0

        if bay_state != SystemState.OFFLINE and not distribution_offline:
            if net_kw >= Balance.DRONE_CHARGE_KW:
                charge_rate = Balance.DRONE_BATTERY_CHARGE_PER_S
            elif soc > 0.0 and net_kw >= Balance.DRONE_CHARGE_NET_MIN_KW:
                charge_rate = Balance.DRONE_BATTERY_CHARGE_PER_S * Balance.DRONE_BATTERY_CHARGE_LOW_MULT
            charge_rate *= bay_mult
            decon_rate = Balance.DRONE_DECON_RAD_PER_S * bay_mult
            repair_rate_mult, repair_scrap_mult, repair_fail_p, repair_fail_hit = self._drone_bay_repair_profile(state)

        repair_scrap_cost = max(1, int(round(repair_scrap_mult))) if repair_rate_mult > 0.0 else 0
        return {
            "bay_state": bay_state,
            "distribution_offline": distribution_offline,
            "net_kw": net_kw,
            "soc": soc,
            "bay_mult": bay_mult,
            "charge_rate": charge_rate,
            "decon_rate": decon_rate,
            "repair_rate_mult": repair_rate_mult,
            "repair_scrap_cost": repair_scrap_cost,
            "repair_fail_p": repair_fail_p,
            "repair_fail_hit": repair_fail_hit,
        }

    def _drone_bay_maintenance_block_data(self, state: GameState) -> dict[str, object] | None:
        support = self._drone_bay_support_snapshot(state)
        docked_in_bay = [
            drone
            for drone in state.ship.drones.values()
            if drone.status == DroneStatus.DOCKED
            and drone.location.kind == "ship_sector"
            and drone.location.id == "drone_bay"
        ]
        needs_charge_count = sum(1 for drone in docked_in_bay if drone.battery < 1.0)
        needs_repair_count = sum(1 for drone in docked_in_bay if drone.integrity < 1.0)
        if needs_charge_count <= 0 and needs_repair_count <= 0:
            return None

        charge_possible = float(support["charge_rate"]) > 0.0
        repair_scrap_cost = int(support["repair_scrap_cost"])
        repair_possible = float(support["repair_rate_mult"]) > 0.0 and state.ship.cargo_scrap >= repair_scrap_cost
        charge_blocked = needs_charge_count > 0 and not charge_possible
        repair_blocked = needs_repair_count > 0 and not repair_possible
        if not charge_blocked and not repair_blocked:
            return None

        charge_block_reason = ""
        if charge_blocked:
            bay_state = support["bay_state"]
            if bay_state == SystemState.OFFLINE:
                charge_block_reason = "drone_bay_offline"
            elif bool(support["distribution_offline"]):
                charge_block_reason = "energy_distribution_offline"
            else:
                charge_block_reason = "insufficient_net_power"

        repair_block_reason = ""
        if repair_blocked:
            bay_state = support["bay_state"]
            if bay_state == SystemState.OFFLINE:
                repair_block_reason = "drone_bay_offline"
            elif bool(support["distribution_offline"]):
                repair_block_reason = "energy_distribution_offline"
            else:
                repair_block_reason = "insufficient_scrap"

        bay_state = support["bay_state"]
        return {
            "message_key": "drone_bay_maintenance_blocked",
            "docked_in_bay": len(docked_in_bay),
            "needs_charge_count": needs_charge_count,
            "needs_repair_count": needs_repair_count,
            "charge_possible": charge_possible,
            "repair_possible": repair_possible,
            "decon_possible": float(support["decon_rate"]) > 0.0,
            "charge_block_reason": charge_block_reason,
            "repair_block_reason": repair_block_reason,
            "bay_state": bay_state.value if isinstance(bay_state, SystemState) else str(bay_state),
            "distribution_offline": bool(support["distribution_offline"]),
            "net_kw": float(support["net_kw"]),
            "soc": float(support["soc"]),
            "scrap_available": int(state.ship.cargo_scrap),
            "scrap_required_per_tick": repair_scrap_cost,
            "charge_kw_required": Balance.DRONE_CHARGE_KW,
            "charge_net_min_kw": Balance.DRONE_CHARGE_NET_MIN_KW,
        }

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

    def _compute_env_radiation_rad_per_s(self, state: GameState) -> float:
        fallback = max(0.0, float(state.ship.radiation_env_rad_per_s))
        nodes = state.world.space.nodes
        if state.ship.in_transit:
            from_node = nodes.get(state.ship.transit_from)
            to_node = nodes.get(state.ship.transit_to)
            if from_node and to_node:
                from_rad = max(0.0, float(from_node.radiation_rad_per_s))
                to_rad = max(0.0, float(to_node.radiation_rad_per_s))
                start_t = float(state.ship.transit_start_t)
                end_t = float(state.ship.arrival_t)
                if end_t > start_t:
                    progress = self._clamp((state.clock.t - start_t) / (end_t - start_t))
                else:
                    progress = 1.0
                return max(0.0, from_rad + (to_rad - from_rad) * progress)
            if from_node:
                return max(0.0, float(from_node.radiation_rad_per_s))
            if to_node:
                return max(0.0, float(to_node.radiation_rad_per_s))
            return fallback
        current_id = state.world.current_node_id or state.ship.current_node_id
        node = nodes.get(current_id) if current_id else None
        if node:
            return max(0.0, float(node.radiation_rad_per_s))
        return fallback

    def _compute_internal_radiation_rad_per_s(self, state: GameState, env_rad: float) -> float:
        hull = self._clamp(state.ship.hull_integrity)
        ingress = (
            Balance.HULL_INTERNAL_RAD_MIN_INGRESS
            + (1.0 - hull) * (Balance.HULL_INTERNAL_RAD_MAX_INGRESS - Balance.HULL_INTERNAL_RAD_MIN_INGRESS)
        )
        ingress = self._clamp(
            ingress,
            Balance.HULL_INTERNAL_RAD_MIN_INGRESS,
            Balance.HULL_INTERNAL_RAD_MAX_INGRESS,
        )
        return max(0.0, env_rad) * ingress

    def _apply_hull_degradation(self, state: GameState, dt: float, env_rad: float) -> None:
        env_norm = self._clamp(env_rad / Balance.HULL_RAD_REF) if Balance.HULL_RAD_REF > 0 else 0.0
        env_mult = 1.0 + env_norm * (Balance.HULL_RAD_DECAY_MULT_MAX - 1.0)
        if state.ship.in_transit or state.ship.is_hibernating:
            env_mult *= Balance.HULL_TRANSIT_DECAY_MULT
        amount = Balance.HULL_BASE_DECAY_PER_S * env_mult * dt
        self._damage_hull(state, amount)

    def _damage_hull(self, state: GameState, amount: float) -> None:
        if amount <= 0.0:
            return
        state.ship.hull_integrity = self._clamp(state.ship.hull_integrity - amount)

    def _radiation_level(self, value: float, elevated: float, high: float, extreme: float) -> str:
        v = max(0.0, float(value))
        if v >= extreme:
            return "extreme"
        if v >= high:
            return "high"
        if v >= elevated:
            return "elevated"
        return "low"

    def _env_radiation_level(self, env_rad: float) -> str:
        return self._radiation_level(
            env_rad,
            Balance.RAD_LEVEL_ENV_ELEVATED,
            Balance.RAD_LEVEL_ENV_HIGH,
            Balance.RAD_LEVEL_ENV_EXTREME,
        )

    def _internal_radiation_level(self, internal_rad: float) -> str:
        return self._radiation_level(
            internal_rad,
            Balance.RAD_LEVEL_INTERNAL_ELEVATED,
            Balance.RAD_LEVEL_INTERNAL_HIGH,
            Balance.RAD_LEVEL_INTERNAL_EXTREME,
        )

    def _drone_dose_level(self, dose: float) -> str:
        return self._radiation_level(
            dose,
            Balance.RAD_LEVEL_DRONE_DOSE_ELEVATED,
            Balance.RAD_LEVEL_DRONE_DOSE_HIGH,
            Balance.RAD_LEVEL_DRONE_DOSE_EXTREME,
        )

    def _radiation_alert_severity(self, level: str) -> Severity:
        if level == "extreme":
            return Severity.CRITICAL
        if level in {"high", "elevated"}:
            return Severity.WARN
        return Severity.INFO

    def _emit_radiation_level_change_alert(
        self,
        state: GameState,
        *,
        source: SourceRef,
        target_kind: str,
        target_id: str,
        metric: str,
        from_level: str,
        to_level: str,
        value: float,
    ) -> Event | None:
        if not from_level or from_level == "unknown" or from_level == to_level:
            return None
        severity = self._radiation_alert_severity(to_level)
        message = f"Radiation level changed ({metric}) {from_level} -> {to_level}"
        return self._make_event(
            state,
            EventType.ACTION_WARNING,
            severity,
            source,
            message,
            data={
                "message_key": "radiation_level_changed",
                "metric": metric,
                "target_kind": target_kind,
                "target_id": target_id,
                "from_level": from_level,
                "to_level": to_level,
                "value": max(0.0, float(value)),
            },
        )

    def _update_ship_radiation_level_alerts(self, state: GameState, env_rad: float, internal_rad: float) -> list[Event]:
        events: list[Event] = []
        ship = state.ship

        env_level = self._env_radiation_level(env_rad)
        env_event = self._emit_radiation_level_change_alert(
            state,
            source=SourceRef(kind="ship", id=ship.ship_id),
            target_kind="ship",
            target_id=ship.ship_id,
            metric="env",
            from_level=ship.radiation_env_level,
            to_level=env_level,
            value=env_rad,
        )
        ship.radiation_env_level = env_level
        if env_event:
            events.append(env_event)

        internal_level = self._internal_radiation_level(internal_rad)
        internal_event = self._emit_radiation_level_change_alert(
            state,
            source=SourceRef(kind="ship", id=ship.ship_id),
            target_kind="ship",
            target_id=ship.ship_id,
            metric="internal",
            from_level=ship.radiation_internal_level,
            to_level=internal_level,
            value=internal_rad,
        )
        ship.radiation_internal_level = internal_level
        if internal_event:
            events.append(internal_event)

        return events

    def _update_drone_radiation_level_alerts(self, state: GameState) -> list[Event]:
        events: list[Event] = []
        for drone in state.ship.drones.values():
            current = self._drone_dose_level(drone.dose_rad)
            alert = self._emit_radiation_level_change_alert(
                state,
                source=SourceRef(kind="drone", id=drone.drone_id),
                target_kind="drone",
                target_id=drone.drone_id,
                metric="drone_dose",
                from_level=drone.radiation_level,
                to_level=current,
                value=drone.dose_rad,
            )
            drone.radiation_level = current
            if alert:
                events.append(alert)
        return events

    def _drone_rad_decay_mult(self, dose: float) -> float:
        if dose >= Balance.DRONE_RAD_DOSE_CRITICAL:
            return Balance.DRONE_RAD_DECAY_MULT_CRITICAL
        if dose >= Balance.DRONE_RAD_DOSE_HIGH:
            return Balance.DRONE_RAD_DECAY_MULT_HIGH
        if dose >= Balance.DRONE_RAD_DOSE_WARN:
            return Balance.DRONE_RAD_DECAY_MULT_WARN
        return 1.0

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

        entered_life_support_offline = (
            life_support is not None
            and life_support.state == SystemState.OFFLINE
            and state.ship.life_support_offline_s <= 0.0
        )

        if life_support and life_support.state == SystemState.OFFLINE:
            state.ship.life_support_offline_s += dt
        else:
            state.ship.life_support_offline_s = 0.0

        # Compatibility: old saves may carry a lock reason based on CRITICAL state.
        # Under current rules, lock is tied to OFFLINE grace expiry.
        if (
            state.os.terminal_lock
            and state.os.terminal_reason == "life_support_critical"
            and (not life_support or life_support.state != SystemState.OFFLINE)
        ):
            state.os.terminal_lock = False
            state.os.terminal_reason = None

        if entered_life_support_offline:
            events.append(
                self._make_event(
                    state,
                    EventType.ACTION_WARNING,
                    Severity.WARN,
                    SourceRef(kind="ship_system", id="life_support"),
                    f"Life support offline: viability grace countdown started ({int(Balance.LIFE_SUPPORT_CRITICAL_GRACE_S)}s)",
                    data={
                        "message_key": "life_support_offline_grace_started",
                        "grace_s": Balance.LIFE_SUPPORT_CRITICAL_GRACE_S,
                    },
                )
            )

        if not state.os.terminal_lock:
            if core_os and core_os.state == SystemState.OFFLINE:
                state.os.terminal_lock = True
                state.os.terminal_reason = "core_os_offline"
            elif (
                life_support
                and life_support.state == SystemState.OFFLINE
                and state.ship.life_support_offline_s >= Balance.LIFE_SUPPORT_CRITICAL_GRACE_S
            ):
                state.os.terminal_lock = True
                state.os.terminal_reason = "life_support_offline"

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
