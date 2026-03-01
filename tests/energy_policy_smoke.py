from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli.parser import ParseError, parse_command
from retorno.config.balance import Balance
from retorno.core.actions import (
    AuthRecover,
    Dock,
    DroneDeploy,
    DroneMove,
    DroneRecall,
    DroneReboot,
    Install,
    Repair,
    SystemOn,
    Undock,
)
from retorno.core.engine import Engine
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import EventType
from retorno.model.jobs import JobType
from retorno.model.systems import SystemState


def _fresh_state():
    state = create_initial_state_prologue()
    state.ship.power.power_quality = 0.9
    state.ship.power.brownout = False
    state.ship.systems["core_os"].state = SystemState.NOMINAL
    state.ship.systems["energy_distribution"].state = SystemState.NOMINAL
    state.ship.systems["drone_bay"].state = SystemState.NOMINAL
    state.ship.systems["drone_bay"].forced_offline = False
    state.ship.power.e_batt_kwh = state.ship.power.e_batt_max_kwh * 0.8
    return state


def _assert_blocked_reason(events, reason: str) -> None:
    assert events, "Expected at least one event"
    assert events[0].type == EventType.BOOT_BLOCKED, f"Expected BOOT_BLOCKED, got: {events[0].type.value}"
    assert events[0].data.get("reason") == reason, (
        f"Expected reason '{reason}', got '{events[0].data.get('reason')}'"
    )


def _active_job_eta(state, job_type: JobType) -> float:
    for job_id in reversed(state.jobs.active_job_ids):
        job = state.jobs.jobs[job_id]
        if job.job_type == job_type:
            return float(job.eta_s)
    raise AssertionError(f"Active job {job_type.value} not found")


def _prepare_deployed_drone(state, drone_id: str = "D1") -> None:
    drone = state.ship.drones[drone_id]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="ship_sector", id="DRN-BAY")
    drone.battery = 1.0
    drone.integrity = 1.0


def _prepare_docked_drone(state, drone_id: str = "D1") -> None:
    drone = state.ship.drones[drone_id]
    drone.status = DroneStatus.DOCKED
    drone.location = DroneLocation(kind="ship_sector", id="drone_bay")
    drone.battery = 0.0
    drone.integrity = 1.0


def _add_d2(state) -> None:
    state.ship.drones["D2"] = DroneState(
        drone_id="D2",
        name="Drone-02",
        status=DroneStatus.DOCKED,
        location=DroneLocation(kind="ship_sector", id="drone_bay"),
        battery=1.0,
        integrity=0.5,
    )


def main() -> None:
    engine = Engine()

    # Parser migration still holds.
    assert parse_command("drone install D1 aux_battery_cell").__class__.__name__ == "Install"
    assert parse_command("undock").__class__.__name__ == "Undock"
    for cmd in ("module install aux_battery_cell", "install aux_battery_cell"):
        try:
            parse_command(cmd)
        except ParseError as err:
            assert err.key == "module_install_migrated", f"Unexpected parse error key: {err.key}"
        else:
            raise AssertionError(f"{cmd} should be rejected")

    # Auth recover blocked for any level when Q < 0.55.
    state = _fresh_state()
    state.ship.power.power_quality = 0.54
    for level in ("MED", "ENG", "OPS", "SEC", "SCI"):
        events = engine.apply_action(state, AuthRecover(level=level))
        _assert_blocked_reason(events, "power_quality_low")

    # Drone-to-drone repair: deployed operator can repair co-located target drone.
    state = _fresh_state()
    _add_d2(state)
    _prepare_deployed_drone(state, "D1")
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="drone_bay")
    state.ship.drones["D2"].status = DroneStatus.DOCKED
    state.ship.drones["D2"].location = DroneLocation(kind="ship_sector", id="drone_bay")
    state.ship.drones["D2"].integrity = 0.5
    state.ship.cargo_scrap = 999
    events = engine.apply_action(state, Repair(drone_id="D1", system_id="D2"))
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    assert _active_job_eta(state, JobType.REPAIR_DRONE) == Balance.REPAIR_TIME_S
    engine.tick(state, Balance.REPAIR_TIME_S + 1.0)
    assert state.ship.drones["D2"].integrity > 0.5, "Expected D2 integrity increase from drone-to-drone repair"

    # Drone-to-drone repair blocked if target not co-located.
    state = _fresh_state()
    _add_d2(state)
    _prepare_deployed_drone(state, "D1")
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="PWR-A2")
    state.ship.drones["D2"].location = DroneLocation(kind="ship_sector", id="drone_bay")
    blocked = engine.apply_action(state, Repair(drone_id="D1", system_id="D2"))
    _assert_blocked_reason(blocked, "drone_target_not_co_located")

    # No circular lock: power on drone_bay does not require distribution nominal.
    state = _fresh_state()
    state.ship.systems["energy_distribution"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].forced_offline = True
    events = engine.apply_action(state, SystemOn(system_id="drone_bay"))
    assert not any(e.type == EventType.BOOT_BLOCKED and e.data.get("reason") == "deps_unmet" for e in events), events

    # LIMITED eta multipliers for bay-assisted actions.
    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.LIMITED
    events = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2", emergency=False))
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    assert abs(_active_job_eta(state, JobType.DEPLOY_DRONE) - Balance.DEPLOY_TIME_S * 1.5) < 1e-6

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.LIMITED
    _prepare_deployed_drone(state)
    events = engine.apply_action(state, DroneRecall(drone_id="D1"))
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    assert abs(_active_job_eta(state, JobType.RECALL_DRONE) - Balance.RECALL_TIME_S * 1.5) < 1e-6

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.LIMITED
    _prepare_deployed_drone(state)
    state.ship.cargo_modules = ["aux_battery_cell"]
    state.ship.cargo_scrap = 999
    events = engine.apply_action(state, Install(drone_id="D1", module_id="aux_battery_cell"))
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    assert abs(_active_job_eta(state, JobType.INSTALL_MODULE) - Balance.INSTALL_TIME_S * 1.5) < 1e-6

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.LIMITED
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DISABLED
    drone.battery = 1.0
    events = engine.apply_action(state, DroneReboot(drone_id="D1"))
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    assert abs(_active_job_eta(state, JobType.REBOOT_DRONE) - Balance.REBOOT_TIME_S * 1.5) < 1e-6

    # LIMITED charge rate multiplier.
    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.LIMITED
    _prepare_docked_drone(state)
    state.ship.power.p_gen_kw = 5.0
    state.ship.power.p_load_kw = 0.0
    engine._update_drone_maintenance(state, 10.0)  # noqa: SLF001 - intentional policy smoke
    assert abs(state.ship.drones["D1"].battery - (Balance.DRONE_BATTERY_CHARGE_PER_S * 0.5 * 10.0)) < 1e-6

    # Passive docked repair profile by bay state.
    old_cfg = (
        Balance.DRONE_REPAIR_INTEGRITY_PER_SCRAP,
        Balance.DRONE_BAY_LIMITED_REPAIR_RATE_MULT,
        Balance.DRONE_BAY_DAMAGED_REPAIR_RATE_MULT,
        Balance.DRONE_BAY_CRITICAL_REPAIR_RATE_MULT,
        Balance.DRONE_BAY_DAMAGED_REPAIR_SCRAP_MULT,
        Balance.DRONE_BAY_CRITICAL_REPAIR_SCRAP_MULT,
        Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_P,
        Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_HIT,
    )
    try:
        Balance.DRONE_REPAIR_INTEGRITY_PER_SCRAP = 0.10
        Balance.DRONE_BAY_LIMITED_REPAIR_RATE_MULT = 0.5
        Balance.DRONE_BAY_DAMAGED_REPAIR_RATE_MULT = 0.5
        Balance.DRONE_BAY_CRITICAL_REPAIR_RATE_MULT = 0.25
        Balance.DRONE_BAY_DAMAGED_REPAIR_SCRAP_MULT = 2.0
        Balance.DRONE_BAY_CRITICAL_REPAIR_SCRAP_MULT = 2.0
        Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_P = 0.0
        Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_HIT = 0.01

        state = _fresh_state()
        _prepare_docked_drone(state)
        state.ship.drones["D1"].integrity = 0.0
        state.ship.cargo_scrap = 10
        state.ship.systems["drone_bay"].state = SystemState.LIMITED
        engine._update_drone_maintenance(state, 1.0)  # noqa: SLF001
        limited_integrity = state.ship.drones["D1"].integrity
        limited_scrap_left = state.ship.cargo_scrap

        state = _fresh_state()
        _prepare_docked_drone(state)
        state.ship.drones["D1"].integrity = 0.0
        state.ship.cargo_scrap = 10
        state.ship.systems["drone_bay"].state = SystemState.DAMAGED
        engine._update_drone_maintenance(state, 1.0)  # noqa: SLF001
        damaged_integrity = state.ship.drones["D1"].integrity
        damaged_scrap_left = state.ship.cargo_scrap

        state = _fresh_state()
        _prepare_docked_drone(state)
        state.ship.drones["D1"].integrity = 0.0
        state.ship.cargo_scrap = 10
        state.ship.systems["drone_bay"].state = SystemState.CRITICAL
        engine._update_drone_maintenance(state, 1.0)  # noqa: SLF001
        critical_integrity = state.ship.drones["D1"].integrity
        critical_scrap_left = state.ship.cargo_scrap

        assert abs(limited_integrity - damaged_integrity) < 1e-6
        assert critical_integrity < limited_integrity
        assert damaged_scrap_left < limited_scrap_left
        assert critical_scrap_left <= damaged_scrap_left

        # CRITICAL failure can damage integrity.
        state = _fresh_state()
        _prepare_docked_drone(state)
        state.ship.drones["D1"].integrity = 0.5
        state.ship.cargo_scrap = 10
        state.ship.systems["drone_bay"].state = SystemState.CRITICAL
        Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_P = 1.0
        engine._update_drone_maintenance(state, 1.0)  # noqa: SLF001
        assert state.ship.drones["D1"].integrity < 0.5

        # No passive repair when distribution is OFFLINE.
        state = _fresh_state()
        _prepare_docked_drone(state)
        state.ship.drones["D1"].integrity = 0.5
        state.ship.cargo_scrap = 10
        state.ship.systems["drone_bay"].state = SystemState.NOMINAL
        state.ship.systems["energy_distribution"].state = SystemState.OFFLINE
        engine._update_drone_maintenance(state, 1.0)  # noqa: SLF001
        assert state.ship.drones["D1"].integrity == 0.5
    finally:
        (
            Balance.DRONE_REPAIR_INTEGRITY_PER_SCRAP,
            Balance.DRONE_BAY_LIMITED_REPAIR_RATE_MULT,
            Balance.DRONE_BAY_DAMAGED_REPAIR_RATE_MULT,
            Balance.DRONE_BAY_CRITICAL_REPAIR_RATE_MULT,
            Balance.DRONE_BAY_DAMAGED_REPAIR_SCRAP_MULT,
            Balance.DRONE_BAY_CRITICAL_REPAIR_SCRAP_MULT,
            Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_P,
            Balance.DRONE_BAY_CRITICAL_REPAIR_FAIL_HIT,
        ) = old_cfg

    # DAMAGED eta multipliers + charge multiplier.
    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.DAMAGED
    events = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2", emergency=False))
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    assert abs(_active_job_eta(state, JobType.DEPLOY_DRONE) - Balance.DEPLOY_TIME_S * 2.0) < 1e-6

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.DAMAGED
    _prepare_docked_drone(state)
    state.ship.power.p_gen_kw = 5.0
    state.ship.power.p_load_kw = 0.0
    engine._update_drone_maintenance(state, 10.0)  # noqa: SLF001 - intentional policy smoke
    assert abs(state.ship.drones["D1"].battery - (Balance.DRONE_BATTERY_CHARGE_PER_S * 0.25 * 10.0)) < 1e-6

    # DAMAGED integrity risk on deploy when configured deterministic.
    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.DAMAGED
    state.ship.drones["D1"].integrity = 1.0
    old_p = Balance.DRONE_BAY_DAMAGED_INTEGRITY_RISK_P
    try:
        Balance.DRONE_BAY_DAMAGED_INTEGRITY_RISK_P = 1.0
        events = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2", emergency=False))
        assert any(e.type == EventType.JOB_QUEUED for e in events), events
        engine.tick(state, 120.0)
        assert state.ship.drones["D1"].integrity <= 1.0 - Balance.DRONE_BAY_DAMAGED_INTEGRITY_HIT
        assert any(e.type == EventType.DRONE_DAMAGED for e in state.events.recent), "Expected drone damaged event"
    finally:
        Balance.DRONE_BAY_DAMAGED_INTEGRITY_RISK_P = old_p

    # OFFLINE behavior: normal deploy blocked, deploy! allowed, install blocked, recall allowed, no charging.
    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].forced_offline = True
    normal = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2", emergency=False))
    _assert_blocked_reason(normal, "drone_bay_deploy_offline")
    emergency = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2", emergency=True))
    assert any(e.type == EventType.JOB_QUEUED for e in emergency), emergency

    # Precedence check: in critical power state, normal deploy should still return drone_bay-specific reason.
    state = _fresh_state()
    state.ship.power.power_quality = 0.20  # critical
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].forced_offline = True
    critical_normal = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2", emergency=False))
    _assert_blocked_reason(critical_normal, "drone_bay_deploy_offline")

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].forced_offline = True
    _prepare_deployed_drone(state)
    state.ship.cargo_modules = ["aux_battery_cell"]
    state.ship.cargo_scrap = 999
    blocked_install = engine.apply_action(state, Install(drone_id="D1", module_id="aux_battery_cell"))
    _assert_blocked_reason(blocked_install, "drone_bay_install_offline")
    recall = engine.apply_action(state, DroneRecall(drone_id="D1"))
    assert any(e.type == EventType.JOB_QUEUED for e in recall), recall

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].forced_offline = True
    _prepare_deployed_drone(state)
    moved = engine.apply_action(state, DroneMove(drone_id="D1", target_id="PWR-A2"))
    assert any(e.type == EventType.JOB_QUEUED for e in moved), moved
    repaired = engine.apply_action(state, Repair(drone_id="D1", system_id="sensors"))
    assert any(e.type == EventType.JOB_QUEUED for e in repaired), repaired

    state = _fresh_state()
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    state.ship.systems["drone_bay"].forced_offline = True
    _prepare_docked_drone(state)
    state.ship.power.p_gen_kw = 5.0
    state.ship.power.p_load_kw = 0.0
    engine._update_drone_maintenance(state, 10.0)  # noqa: SLF001 - intentional policy smoke
    assert state.ship.drones["D1"].battery == 0.0

    # Critical-state consistency: route blocked, repair allowed.
    state = _fresh_state()
    state.ship.power.power_quality = 0.24
    _prepare_deployed_drone(state)
    route_events = engine.apply_action(state, parse_command("route solve ECHO_7"))
    _assert_blocked_reason(route_events, "critical_power_state")
    repair_events = engine.apply_action(state, Repair(drone_id="D1", system_id="sensors"))
    assert any(e.type == EventType.ACTION_WARNING for e in repair_events), "Missing non-critical repair warning"
    assert any(e.type == EventType.JOB_QUEUED for e in repair_events), "Repair should still enqueue"

    # Undock behavior: blocked if not docked, queues job if docked, blocked in critical power state.
    state = _fresh_state()
    not_docked = engine.apply_action(state, Undock())
    _assert_blocked_reason(not_docked, "not_docked")

    state = _fresh_state()
    state.ship.docked_node_id = state.world.current_node_id
    undock_job = engine.apply_action(state, Undock())
    assert any(e.type == EventType.JOB_QUEUED for e in undock_job), undock_job
    assert abs(_active_job_eta(state, JobType.UNDOCK) - Balance.UNDOCK_TIME_S) < 1e-6
    events = engine.tick(state, Balance.UNDOCK_TIME_S + 1.0)
    assert any(e.type == EventType.UNDOCKED for e in events), events
    assert state.ship.docked_node_id is None, "Undock should clear docked_node_id"

    state = _fresh_state()
    state.ship.docked_node_id = state.world.current_node_id
    state.ship.power.power_quality = 0.24
    critical_undock = engine.apply_action(state, Undock())
    _assert_blocked_reason(critical_undock, "critical_power_state")

    # Dock/undock interruption behavior.
    state = _fresh_state()
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    dock_job = engine.apply_action(state, Dock(node_id="ECHO_7"))
    assert any(e.type == EventType.JOB_QUEUED for e in dock_job), dock_job
    state.world.current_node_id = "CURL_12"
    state.ship.current_node_id = "CURL_12"
    interrupted = engine.tick(state, Balance.DOCK_TIME_S + 1.0)
    assert any(e.type == EventType.JOB_FAILED and e.data.get("message_key") == "job_failed_dock_interrupted" for e in interrupted), interrupted

    state = _fresh_state()
    state.ship.docked_node_id = state.world.current_node_id
    undock_job = engine.apply_action(state, Undock())
    assert any(e.type == EventType.JOB_QUEUED for e in undock_job), undock_job
    state.ship.docked_node_id = None
    interrupted = engine.tick(state, Balance.UNDOCK_TIME_S + 1.0)
    assert any(
        e.type == EventType.JOB_FAILED and e.data.get("message_key") == "job_failed_undock_interrupted"
        for e in interrupted
    ), interrupted

    print("ENERGY POLICY SMOKE PASSED")


if __name__ == "__main__":
    main()
