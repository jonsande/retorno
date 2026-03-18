from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.model.world import add_known_link


def main() -> None:
    state = create_initial_state_sandbox()
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    state.ship.docked_node_id = None

    # Keep a remote contact known to ensure completion remains local-only.
    state.world.known_nodes.update({"ECHO_7", "CURL_12"})
    state.world.known_contacts.update({"ECHO_7", "CURL_12"})

    dock_targets = repl._dock_targets_for_completion(state)
    assert dock_targets == ["ECHO_7"], f"Expected only current node for dock completion in orbit, got {dock_targets!r}"

    route_solve_targets = repl._route_solve_targets_for_completion(state)
    assert route_solve_targets == ["ECHO_7"], (
        f"Expected in-range unresolved route-solve targets from current node, got {route_solve_targets!r}"
    )

    add_known_link(state.world, "ECHO_7", "CURL_12", bidirectional=True)
    travel_targets = repl._travel_targets_for_completion(state)
    assert travel_targets == ["CURL_12"], (
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
        "PWR-A2",
        "PRP-R1",
        "BRG-01",
        "SNS-R1",
        "DRN-BAY",
        "CRG-01",
    }
    assert expected_ship_sectors.issubset(set(move_targets)), move_targets
    assert "ECHO_7" in move_targets, move_targets
    assert "CURL_12" not in move_targets, move_targets
    assert "DRN-BAY" in move_targets, move_targets

    deploy_targets = repl._drone_deploy_targets_for_completion(state)
    assert expected_ship_sectors.issubset(set(deploy_targets)), deploy_targets
    assert "ECHO_7" in deploy_targets, deploy_targets
    assert "CURL_12" not in deploy_targets, deploy_targets
    assert "DRN-BAY" in deploy_targets, deploy_targets

    state.ship.docked_node_id = "ECHO_7"
    docked_dock_targets = repl._dock_targets_for_completion(state)
    assert docked_dock_targets == ["ECHO_7"], f"Expected current node for dock completion while docked, got {docked_dock_targets!r}"

    docked_targets = repl._drone_local_world_node_targets_for_completion(state)
    assert docked_targets == ["ECHO_7"], f"Expected deduped local dock target, got {docked_targets!r}"

    docked_deploy_targets = repl._drone_deploy_targets_for_completion(state)
    assert docked_deploy_targets.count("ECHO_7") == 1, docked_deploy_targets

    print("DRONE COMPLETION CONTEXT SMOKE PASSED")


if __name__ == "__main__":
    main()
