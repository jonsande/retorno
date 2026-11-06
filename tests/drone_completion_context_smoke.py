from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command, ParseError
from retorno.core.engine import Engine
from retorno.model.drones import DroneStatus
from retorno.model.events import EventType
from retorno.model.ship import ShipSector
from retorno.model.world import SpaceNode, add_known_link


def main() -> None:
    state = create_initial_state_sandbox()
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    state.ship.docked_node_id = None

    # Use an explicit physical fixture outside sensors and within the hop cap.
    state.world.space.nodes["COMPLETION_REMOTE"] = SpaceNode(
        node_id="COMPLETION_REMOTE", name="Completion Remote", kind="station", x_ly=10.0,
    )
    # Keep a remote contact known to ensure completion remains local-only.
    state.world.known_nodes.update({"ECHO_7", "COMPLETION_REMOTE"})
    state.world.known_contacts.update({"ECHO_7", "COMPLETION_REMOTE"})

    dock_targets = repl._dock_targets_for_completion(state)
    assert dock_targets == ["ECHO_7"], f"Expected only current node for dock completion in orbit, got {dock_targets!r}"

    route_solve_targets = repl._route_solve_targets_for_completion(state)
    assert route_solve_targets == ["ECHO_7"], (
        f"Expected in-range unresolved route-solve targets from current node, got {route_solve_targets!r}"
    )

    add_known_link(state.world, "ECHO_7", "COMPLETION_REMOTE", bidirectional=True)
    travel_targets = repl._travel_targets_for_completion(state)
    assert travel_targets == ["COMPLETION_REMOTE"], (
        f"Expected only known-route travel targets from current node, got {travel_targets!r}"
    )

    world_targets = repl._drone_local_world_node_targets_for_completion(state)
    assert world_targets == ["ECHO_7"], f"Expected only current node while in orbit, got {world_targets!r}"

    move_targets = repl._drone_move_targets_for_completion(state)
    expected_ship_sectors = {
        "DCK-A1",
        "STS-BAY",
        "LFS-01",
        "PWR-A1",
        "BUS-A2",
        "ENG-R1",
        "BRG-01",
        "SNS-R1",
        "DRN-BAY",
        "CRG-01",
    }
    assert expected_ship_sectors.issubset(set(move_targets)), move_targets
    assert "ECHO_7" in move_targets, move_targets
    assert "COMPLETION_REMOTE" not in move_targets, move_targets
    assert "DRN-BAY" in move_targets, move_targets

    deploy_targets = repl._drone_deploy_targets_for_completion(state)
    assert expected_ship_sectors.issubset(set(deploy_targets)), deploy_targets
    assert "ECHO_7" in deploy_targets, deploy_targets
    assert "COMPLETION_REMOTE" not in deploy_targets, deploy_targets
    assert "DRN-BAY" in deploy_targets, deploy_targets

    state.ship.docked_node_id = "ECHO_7"
    docked_dock_targets = repl._dock_targets_for_completion(state)
    assert docked_dock_targets == ["ECHO_7"], f"Expected current node for dock completion while docked, got {docked_dock_targets!r}"

    docked_targets = repl._drone_local_world_node_targets_for_completion(state)
    assert docked_targets == ["ECHO_7"], f"Expected deduped local dock target, got {docked_targets!r}"

    docked_deploy_targets = repl._drone_deploy_targets_for_completion(state)
    assert docked_deploy_targets.count("ECHO_7") == 1, docked_deploy_targets

    engine = Engine()
    # Omitted destination is resolved from the current ship, not baked into parsing.
    for bay_id in ("DRN-BAY", "AUX-BAY"):
        deployed = create_initial_state_sandbox()
        deployed.ship.sectors[bay_id] = ShipSector(sector_id=bay_id, name="Drone bay", tags={"drone", "bay"})
        deployed.ship.systems["drone_bay"].sector_id = bay_id
        deployed.world.space.nodes[bay_id] = SpaceNode(bay_id, "Same-named world node", "station")
        action = parse_command("drone deploy D1")
        assert action.sector_id is None and not action.emergency
        events = engine.apply_action(deployed, action)
        assert any(event.type == EventType.JOB_QUEUED for event in events), events
        job = deployed.jobs.jobs[deployed.jobs.active_job_ids[-1]]
        assert job.target.kind == "ship_sector" and job.target.id == bay_id
        engine.tick(deployed, job.eta_s + 1)
        drone = deployed.ship.drones["D1"]
        assert drone.status == DroneStatus.DEPLOYED
        assert drone.location.kind == "ship_sector" and drone.location.id == bay_id

    assert parse_command("drone deploy D1 PWR-A1").sector_id == "PWR-A1"
    assert parse_command("drone deploy! D1").emergency
    assert parse_command("drone deploy --emergency D1").sector_id is None
    for invalid in ("drone deploy", "drone deploy D1 PWR-A1 extra"):
        try:
            parse_command(invalid)
        except ParseError as error:
            assert error.key == "usage_drone_deploy"
        else:
            raise AssertionError(f"Invalid deployment accepted: {invalid}")

    blocked = create_initial_state_sandbox()
    engine.apply_action(blocked, parse_command("power off drone_bay"))
    assert engine.apply_action(blocked, parse_command("drone deploy D1"))[0].type == EventType.BOOT_BLOCKED

    print("DRONE COMPLETION CONTEXT SMOKE PASSED")


if __name__ == "__main__":
    main()
