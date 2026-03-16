from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli.parser import parse_command
from retorno.core.actions import DroneRecall
from retorno.core.engine import Engine
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import EventType


def main() -> None:
    parsed_empty = parse_command("drone recall")
    parsed_all = parse_command("drone recall all")
    parsed_one = parse_command("drone recall D1")

    assert parsed_empty == DroneRecall(all_drones=True), parsed_empty
    assert parsed_all == DroneRecall(all_drones=True), parsed_all
    assert parsed_one == DroneRecall(drone_id="D1"), parsed_one

    engine = Engine()
    state = create_initial_state_sandbox()

    state.ship.drones["D1"].status = DroneStatus.DEPLOYED
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="PWR-A2")
    state.ship.drones["D1"].battery = 1.0
    state.ship.drones["D1"].integrity = 1.0
    state.ship.drones["D2"] = DroneState(
        drone_id="D2",
        name="Drone-02",
        status=DroneStatus.DEPLOYED,
        location=DroneLocation(kind="world_node", id="ECHO_7"),
        battery=1.0,
        integrity=1.0,
    )
    state.ship.drones["D3"] = DroneState(
        drone_id="D3",
        name="Drone-03",
        status=DroneStatus.DOCKED,
        location=DroneLocation(kind="ship_sector", id="drone_bay"),
    )
    state.ship.docked_node_id = "ECHO_7"
    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"

    events = engine.apply_action(state, parsed_empty)
    queued = [event for event in events if event.type == EventType.JOB_QUEUED]
    assert len(queued) == 2, events
    assert {event.data.get("owner_id") for event in queued} == {"D1", "D2"}, queued
    assert len(state.jobs.active_job_ids) == 2, state.jobs.active_job_ids

    idle_state = create_initial_state_sandbox()
    blocked = engine.apply_action(idle_state, parsed_all)
    assert any(
        event.type == EventType.BOOT_BLOCKED and (event.data or {}).get("reason") == "no_deployed_drones"
        for event in blocked
    ), blocked

    print("DRONE RECALL ALL SMOKE PASSED")


if __name__ == "__main__":
    main()
