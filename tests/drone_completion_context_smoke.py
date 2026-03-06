from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl


def main() -> None:
    state = create_initial_state_sandbox()
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    state.ship.docked_node_id = None

    # Keep a remote contact known to ensure completion remains local-only.
    state.world.known_nodes.update({"ECHO_7", "CURL_12"})
    state.world.known_contacts.update({"ECHO_7", "CURL_12"})

    world_targets = repl._drone_local_world_node_targets_for_completion(state)
    assert world_targets == ["ECHO_7"], f"Expected only current node while in orbit, got {world_targets!r}"

    move_targets = repl._drone_move_targets_for_completion(state)
    assert "ECHO_7" in move_targets, move_targets
    assert "CURL_12" not in move_targets, move_targets
    assert "DRN-BAY" in move_targets, move_targets

    deploy_targets = repl._drone_deploy_targets_for_completion(state)
    assert "ECHO_7" in deploy_targets, deploy_targets
    assert "CURL_12" not in deploy_targets, deploy_targets
    assert "DRN-BAY" in deploy_targets, deploy_targets

    state.ship.docked_node_id = "ECHO_7"
    docked_targets = repl._drone_local_world_node_targets_for_completion(state)
    assert docked_targets == ["ECHO_7"], f"Expected deduped local dock target, got {docked_targets!r}"

    docked_deploy_targets = repl._drone_deploy_targets_for_completion(state)
    assert docked_deploy_targets.count("ECHO_7") == 1, docked_deploy_targets

    print("DRONE COMPLETION CONTEXT SMOKE PASSED")


if __name__ == "__main__":
    main()
