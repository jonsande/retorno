from __future__ import annotations

import contextlib
import io

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.actions import DroneDeploy, DroneRecall, DroneUninstall, Install, SalvageDrone, SalvageScrap
from retorno.core.engine import Engine
from retorno.model.drones import DroneLocation, DroneStatus, compute_drone_effective_profile
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.runtime.data_loader import load_modules


def _set_bay_ready(state) -> None:
    bay = state.ship.systems["drone_bay"]
    bay.state = SystemState.NOMINAL
    bay.forced_offline = False
    dist = state.ship.systems["energy_distribution"]
    dist.state = SystemState.NOMINAL
    dist.forced_offline = False


def _assert_blocked_reason(events, reason: str) -> None:
    for event in events:
        data = getattr(event, "data", {}) or {}
        if data.get("message_key") == "boot_blocked" and data.get("reason") == reason:
            return
    raise AssertionError(f"Missing blocked reason '{reason}'. Events={[(getattr(e, 'type', None), getattr(e, 'data', {})) for e in events]}")


def _queued_job_type(events) -> str:
    for event in events:
        if getattr(event, "type", None) == EventType.JOB_QUEUED:
            return str((getattr(event, "data", {}) or {}).get("job_type", ""))
    raise AssertionError(f"No JOB_QUEUED in events: {events}")


def _queued_eta(events) -> float:
    for event in events:
        if getattr(event, "type", None) == EventType.JOB_QUEUED:
            return float((getattr(event, "data", {}) or {}).get("eta_s", 0.0))
    raise AssertionError(f"No JOB_QUEUED in events: {events}")


def _salvage_eta_with_modules(installed_modules: list[str]) -> float:
    engine = Engine()
    state = create_initial_state_sandbox()
    _set_bay_ready(state)
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="world_node", id="ECHO_7")
    drone.battery = 1.0
    drone.installed_modules = list(installed_modules)
    state.ship.docked_node_id = "ECHO_7"
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    node = state.world.space.nodes["ECHO_7"]
    node.salvage_scrap_available = 100
    events = engine.apply_action(state, SalvageScrap(drone_id="D1", node_id="ECHO_7", amount=10))
    return _queued_eta(events)


def _recall_eta_with_modules(installed_modules: list[str]) -> float:
    engine = Engine()
    state = create_initial_state_sandbox()
    _set_bay_ready(state)
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="ship_sector", id="PWR-A2")
    drone.battery = 1.0
    drone.integrity = 1.0
    drone.installed_modules = list(installed_modules)
    events = engine.apply_action(state, DroneRecall(drone_id="D1"))
    return _queued_eta(events)


def _salvage_recovered_signature() -> dict[str, tuple[str, ...]]:
    engine = Engine()
    state = create_initial_state_sandbox()
    _set_bay_ready(state)
    node = state.world.space.nodes["ECHO_7"]
    node.recoverable_drones_count = 10
    state.ship.docked_node_id = "ECHO_7"
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    deploy_events = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="ECHO_7"))
    assert _queued_job_type(deploy_events) == "deploy_drone"
    engine.tick(state, 60.0)

    salvage_events = engine.apply_action(state, SalvageDrone(drone_id="D1", node_id="ECHO_7"))
    assert _queued_job_type(salvage_events) == "salvage_drone"
    done_events = engine.tick(state, 200.0)
    recovered_ids: list[str] = []
    for event in done_events:
        data = getattr(event, "data", {}) or {}
        if data.get("message_key") == "job_completed_drone_salvage":
            recovered_ids = list(data.get("recovered_ids", []) or [])
            break
    assert recovered_ids, "Expected recovered drone ids"

    modules = load_modules()
    signature: dict[str, tuple[str, ...]] = {}
    has_preinstalled = False
    for drone_id in recovered_ids:
        drone = state.ship.drones[drone_id]
        mids = tuple(drone.installed_modules or [])
        if mids:
            has_preinstalled = True
        assert len(mids) <= 2, (drone_id, mids)
        assert len(mids) <= int(drone.module_slots_max), (drone_id, mids, drone.module_slots_max)
        for mid in mids:
            assert modules.get(mid, {}).get("scope") == "drone", (drone_id, mid)
        signature[drone_id] = mids
    assert has_preinstalled, f"Expected at least one preinstalled module, got {signature}"
    return signature


def main() -> None:
    modules = load_modules()

    # Install / uninstall drone module in bay.
    engine = Engine()
    state = create_initial_state_sandbox()
    _set_bay_ready(state)
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DOCKED
    drone.location = DroneLocation(kind="ship_sector", id="drone_bay")
    state.ship.cargo_modules = ["utility_cargo_frame"]

    queued = engine.apply_action(state, Install(drone_id="D1", module_id="utility_cargo_frame"))
    assert _queued_job_type(queued) == "drone_install_module", queued
    engine.tick(state, Balance.DRONE_INSTALL_TIME_S + 2.0)
    assert "utility_cargo_frame" in drone.installed_modules, drone.installed_modules
    assert "utility_cargo_frame" not in state.ship.cargo_modules, state.ship.cargo_modules

    queued_un = engine.apply_action(state, DroneUninstall(drone_id="D1", module_id="utility_cargo_frame"))
    assert _queued_job_type(queued_un) == "drone_uninstall_module", queued_un
    engine.tick(state, Balance.DRONE_UNINSTALL_TIME_S + 2.0)
    assert "utility_cargo_frame" not in drone.installed_modules, drone.installed_modules
    assert "utility_cargo_frame" in state.ship.cargo_modules, state.ship.cargo_modules

    # Slots limit (2 max).
    drone.installed_modules = ["field_service_rig", "high_density_cell"]
    state.ship.cargo_modules = ["utility_cargo_frame"]
    blocked_slots = engine.apply_action(state, Install(drone_id="D1", module_id="utility_cargo_frame"))
    _assert_blocked_reason(blocked_slots, "module_slots_full")

    # Bay/distribution blocks for drone module operations.
    state.ship.cargo_modules = ["utility_cargo_frame"]
    state.ship.systems["drone_bay"].state = SystemState.LIMITED
    blocked_bay = engine.apply_action(state, Install(drone_id="D1", module_id="utility_cargo_frame"))
    _assert_blocked_reason(blocked_bay, "drone_bay_not_nominal")

    _set_bay_ready(state)
    state.ship.systems["energy_distribution"].state = SystemState.OFFLINE
    blocked_dist = engine.apply_action(state, Install(drone_id="D1", module_id="utility_cargo_frame"))
    _assert_blocked_reason(blocked_dist, "energy_distribution_offline")

    _set_bay_ready(state)
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="world_node", id="ECHO_7")
    blocked_not_bay = engine.apply_action(state, Install(drone_id="D1", module_id="utility_cargo_frame"))
    _assert_blocked_reason(blocked_not_bay, "drone_not_in_bay")

    # Scope separation: ship module stays in ship install flow.
    scope_state = create_initial_state_sandbox()
    _set_bay_ready(scope_state)
    d1 = scope_state.ship.drones["D1"]
    d1.status = DroneStatus.DEPLOYED
    d1.location = DroneLocation(kind="ship_sector", id="DRN-BAY")
    d1.battery = 1.0
    scope_state.ship.cargo_scrap = 999
    scope_state.ship.cargo_modules = ["bus_stabilizer"]
    scope_events = engine.apply_action(scope_state, Install(drone_id="D1", module_id="bus_stabilizer"))
    assert _queued_job_type(scope_events) == "install_module", scope_events
    engine.tick(scope_state, Balance.INSTALL_TIME_S + 2.0)
    assert "bus_stabilizer" in scope_state.ship.installed_modules
    assert "bus_stabilizer" not in d1.installed_modules

    scope_uninstall = engine.apply_action(scope_state, DroneUninstall(drone_id="D1", module_id="bus_stabilizer"))
    assert _queued_job_type(scope_uninstall) == "uninstall_module", scope_uninstall
    engine.tick(scope_state, Balance.UNINSTALL_TIME_S + 2.0)
    assert "bus_stabilizer" not in scope_state.ship.installed_modules
    assert "bus_stabilizer" in scope_state.ship.cargo_modules

    # Stacking profile.
    d1.installed_modules = ["rapid_maneuver_module", "reinforced_frame"]
    profile = compute_drone_effective_profile(d1, modules)
    assert abs(profile.integrity_max_effective - 1.10) < 1e-6, profile
    assert profile.move_time_mult_effective < 1.0, profile
    assert profile.deploy_time_mult_effective < 1.0, profile
    assert profile.survey_time_mult_effective < 1.0, profile

    # Salvage ETA scales with effective cargo capacity.
    eta_base = _salvage_eta_with_modules([])
    eta_cargo = _salvage_eta_with_modules(["utility_cargo_frame"])
    assert eta_cargo < eta_base, (eta_base, eta_cargo)

    # Recall ETA scales with mobility modules too.
    eta_recall_base = _recall_eta_with_modules([])
    eta_recall_fast = _recall_eta_with_modules(["rapid_maneuver_module"])
    assert eta_recall_fast < eta_recall_base, (eta_recall_base, eta_recall_fast)

    # Bay charge/passive repair reach effective maxima.
    maint_state = create_initial_state_sandbox()
    _set_bay_ready(maint_state)
    mdrone = maint_state.ship.drones["D1"]
    mdrone.status = DroneStatus.DOCKED
    mdrone.location = DroneLocation(kind="ship_sector", id="drone_bay")
    mdrone.installed_modules = ["high_density_cell", "reinforced_frame"]
    mdrone.battery = 1.0
    mdrone.integrity = 1.0
    maint_state.ship.cargo_scrap = 200
    maint_state.ship.power.p_gen_kw = 8.0
    maint_state.ship.power.p_load_kw = 0.0
    maint_state.ship.power.e_batt_kwh = 2.0
    maint_state.ship.power.e_batt_max_kwh = 2.0
    engine._update_drone_maintenance(maint_state, 120.0)
    mprofile = compute_drone_effective_profile(mdrone, modules)
    assert mdrone.battery <= mprofile.battery_max_effective + 1e-6
    assert mdrone.integrity <= mprofile.integrity_max_effective + 1e-6
    assert mdrone.battery > 1.0, (mdrone.battery, mprofile.battery_max_effective)
    assert mdrone.integrity > 1.0, (mdrone.integrity, mprofile.integrity_max_effective)

    # Recovered drones with deterministic preinstalled modules.
    sig_a = _salvage_recovered_signature()
    sig_b = _salvage_recovered_signature()
    assert sig_a == sig_b, (sig_a, sig_b)

    # Modules/module inspect output smoke.
    text_state = create_initial_state_sandbox()
    _set_bay_ready(text_state)
    text_state.ship.drones["D1"].installed_modules = ["field_service_rig"]
    text_state.ship.cargo_modules = ["bus_stabilizer", "utility_cargo_frame"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        repl.render_modules_installed(text_state)
        repl.render_module_inspect(text_state, "field_service_rig")
        repl.render_drone_status(text_state, "D1")
    rendered = out.getvalue()
    assert "scope: drone" in rendered, rendered
    assert "slots:" in rendered, rendered
    assert "mods=1 (field_service_rig)" in rendered, rendered

    print("DRONE MODULAR V1 SMOKE PASSED")


if __name__ == "__main__":
    main()
