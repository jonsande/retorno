from __future__ import annotations

from retorno.config.balance import Balance
from retorno.core.actions import (
    Action,
    Boot,
    Diag,
    DroneDeploy,
    DroneMove,
    DroneRecall,
    DroneReboot,
    Install,
    PowerPlan,
    PowerShed,
    Repair,
    SalvageData,
    SalvageModule,
    SalvageScrap,
    Status,
    SystemOn,
)
from retorno.model.systems import SystemState

CRITICAL_SYSTEM_IDS = {"energy_distribution", "power_core", "core_os", "life_support"}

_CRITICAL_REPL_STRINGS = {
    "HELP",
    "EXIT",
    "ALERTS",
    "LOGS",
    "JOBS",
    "POWER_STATUS",
    "DRONE_STATUS",
}

_CRITICAL_REPL_TUPLES = {
    "ALERTS_EXPLAIN",
    "LOG_COPY",
    "JOBS",
}


def is_critical_system_id(system_id: str) -> bool:
    return system_id in CRITICAL_SYSTEM_IDS


def is_critical_power_state(state) -> bool:
    q = state.ship.power.power_quality
    if q < Balance.POWER_QUALITY_COLLAPSE_THRESHOLD:
        return True
    if state.ship.power.brownout:
        return True
    core_os = state.ship.systems.get("core_os")
    if core_os and core_os.state == SystemState.CRITICAL:
        return True
    distribution = state.ship.systems.get("energy_distribution")
    if distribution and distribution.state == SystemState.OFFLINE:
        return True
    return False


def is_critical_service(state, service_name: str) -> bool:
    for system in state.ship.systems.values():
        if not system.service:
            continue
        if system.service.service_name != service_name:
            continue
        return is_critical_system_id(system.system_id)
    return False


def is_action_allowed_in_critical_state(state, action: Action) -> bool:
    if isinstance(action, (Status, Diag)):
        return True
    if isinstance(action, (PowerShed, SystemOn, PowerPlan)):
        return True
    if isinstance(action, DroneDeploy):
        return action.emergency
    if isinstance(
        action,
        (
            DroneMove,
            Repair,
            DroneRecall,
            DroneReboot,
            SalvageScrap,
            SalvageModule,
            SalvageData,
            Install,
        ),
    ):
        return True
    if isinstance(action, Boot):
        return is_critical_service(state, action.service_name)
    return False


def is_parsed_command_allowed_in_core_os_critical(parsed) -> bool:
    if parsed in _CRITICAL_REPL_STRINGS:
        return True
    if isinstance(parsed, tuple):
        return parsed[0] in _CRITICAL_REPL_TUPLES
    if isinstance(parsed, (Status, Diag)):
        return True
    return False
