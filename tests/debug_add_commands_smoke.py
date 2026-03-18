from __future__ import annotations

import contextlib
import io

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.model.drones import DroneStatus
from retorno.runtime.data_loader import load_modules


def _module_ids_by_scope() -> tuple[str, str]:
    modules = load_modules()
    ship_module_id = ""
    drone_module_id = ""
    for module_id, info in modules.items():
        scope = str(info.get("scope", "ship"))
        if scope == "ship" and not ship_module_id:
            ship_module_id = module_id
        if scope == "drone" and not drone_module_id:
            drone_module_id = module_id
        if ship_module_id and drone_module_id:
            break
    assert ship_module_id, "Expected at least one ship module in catalog"
    assert drone_module_id, "Expected at least one drone module in catalog"
    return ship_module_id, drone_module_id


def main() -> None:
    assert parse_command("debug add scrap 50") == ("DEBUG_ADD_SCRAP", 50)
    assert parse_command("debug add module utility_cargo_frame") == (
        "DEBUG_ADD_MODULE",
        "utility_cargo_frame",
        1,
    )
    assert parse_command("debug add module utility_cargo_frame 3") == (
        "DEBUG_ADD_MODULE",
        "utility_cargo_frame",
        3,
    )
    assert parse_command("debug add drone") == ("DEBUG_ADD_DRONE", 1)
    assert parse_command("debug add drones 2") == ("DEBUG_ADD_DRONE", 2)

    state = create_initial_state_sandbox()
    ship_module_id, drone_module_id = _module_ids_by_scope()

    with contextlib.redirect_stdout(io.StringIO()):
        repl.debug_add_scrap(state, 42)
    assert state.ship.cargo_scrap >= 42, state.ship.cargo_scrap
    assert state.ship.manifest_dirty is True

    with contextlib.redirect_stdout(io.StringIO()):
        repl.debug_add_module(state, ship_module_id, 2)
        repl.debug_add_module(state, drone_module_id, 1)
    assert state.ship.cargo_modules.count(ship_module_id) >= 2, state.ship.cargo_modules
    assert state.ship.cargo_modules.count(drone_module_id) >= 1, state.ship.cargo_modules

    before_ids = set(state.ship.drones.keys())
    with contextlib.redirect_stdout(io.StringIO()):
        repl.debug_add_drones(state, 3)
    after_ids = set(state.ship.drones.keys())
    created = sorted(after_ids - before_ids)
    assert len(created) == 3, created
    for drone_id in created:
        drone = state.ship.drones[drone_id]
        assert drone.status == DroneStatus.DOCKED, (drone_id, drone.status)
        assert drone.location.kind == "ship_sector", (drone_id, drone.location)
        assert drone.location.id == "DRN-BAY", (drone_id, drone.location)

    print("DEBUG ADD COMMANDS SMOKE PASSED")


if __name__ == "__main__":
    main()
