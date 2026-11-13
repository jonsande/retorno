from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import ParseError, parse_command
from retorno.core.actions import DroneRecall, JobCancel, Repair, RepairAutoMoveDecision
from retorno.core.engine import Engine
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.jobs import JobStatus, JobType
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
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="ship_sector", id="STS-BAY")
    drone.battery = 1.0
    drone.integrity = 1.0
    return state


def _add_deployed_drone(state, drone_id: str, sector_id: str) -> None:
    state.ship.drones[drone_id] = DroneState(
        drone_id=drone_id,
        name=f"Drone-{drone_id}",
        status=DroneStatus.DEPLOYED,
        location=DroneLocation(kind="ship_sector", id=sector_id),
        battery=1.0,
        integrity=1.0,
    )


def _enter_transit(state) -> None:
    state.ship.in_transit = True
    state.ship.transit_from = state.world.current_node_id
    state.ship.transit_to = "ECHO_7"
    state.ship.arrival_t = state.clock.t + 3600.0


def _active_jobs_for(state, drone_id: str) -> list:
    out = []
    for key in state.jobs.active_job_ids:
        job = state.jobs.jobs.get(key)
        if job and job.owner_id == drone_id:
            out.append(job)
    return out


def _awaiting_repair_job(state):
    for key in state.jobs.active_job_ids:
        job = state.jobs.jobs.get(key)
        if job and job.job_type == JobType.REPAIR_SYSTEM and job.params.get("awaiting_auto_move_confirmation"):
            return job
    raise AssertionError("No repair job awaiting auto-move confirmation")


def _active_job_eta(state, job_type: JobType) -> float:
    for job_id in reversed(state.jobs.active_job_ids):
        job = state.jobs.jobs[job_id]
        if job.job_type == job_type:
            return float(job.eta_s)
    raise AssertionError(f"Active job {job_type.value} not found")


def _reach_awaiting_repair(state, engine: Engine) -> None:
    state.ship.systems["energy_distribution"].health = 0.4
    state.ship.systems["power_core"].health = 0.4
    state.ship.cargo_scrap = 100
    engine.apply_action(state, Repair(drone_id="D1", system_id="energy_distribution", auto_move=True))
    engine.apply_action(state, Repair(drone_id="D1", system_id="power_core"))
    for _ in range(6):
        events = engine.tick(state, 1.0)
        if any(e.data.get("reason") == "repair_auto_move_confirmation_required" for e in events):
            return
        engine.tick(state, _active_job_eta(state, JobType.MOVE_DRONE) + 1.0)
        engine.tick(state, _active_job_eta(state, JobType.REPAIR_SYSTEM) + 1.0)
    raise AssertionError("Deferred repair confirmation was never emitted")


def main() -> None:
    # Parser: emergency recall is explicit and requires a target.
    assert parse_command("drone recall! D1") == DroneRecall(drone_id="D1", emergency=True)
    assert parse_command("drone recall! all") == DroneRecall(all_drones=True, emergency=True)
    try:
        parse_command("drone recall!")
    except ParseError as err:
        assert err.key == "usage_drone_recall_emergency", err.key
    else:
        raise AssertionError("drone recall! without a target must be rejected")

    engine = Engine()

    # The deferred repair decision is usable while the ship is in transit.
    state = _fresh_state()
    _reach_awaiting_repair(state, engine)
    waiting = _awaiting_repair_job(state)
    _enter_transit(state)
    events = engine.apply_action(state, RepairAutoMoveDecision(job_id=waiting.job_id, auto_move=True))
    assert all(not (e.type.value == "boot_blocked" and e.data.get("reason") == "in_transit") for e in events), events
    assert not state.jobs.jobs[waiting.internal_id].params.get("awaiting_auto_move_confirmation")

    # Active jobs can be cancelled during transit.
    state = _fresh_state()
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="BUS-A2")
    state.ship.systems["energy_distribution"].health = 0.4
    state.ship.cargo_scrap = 100
    engine.apply_action(state, Repair(drone_id="D1", system_id="energy_distribution"))
    active = _active_jobs_for(state, "D1")[0]
    _enter_transit(state)
    events = engine.apply_action(state, JobCancel(job_id=active.job_id))
    assert any(e.type.value == "job_failed" for e in events), events
    assert state.jobs.jobs[active.internal_id].status == JobStatus.CANCELLED

    # Emergency recall cancels every active job for the drone, refunds scrap
    # and inserts the return at the front of the queue.
    state = _fresh_state()
    _reach_awaiting_repair(state, engine)
    _enter_transit(state)
    scrap_before = state.ship.cargo_scrap
    cancelled_before = {
        key for key in state.jobs.active_job_ids if state.jobs.jobs[key].owner_id == "D1"
    }
    events = engine.apply_action(state, DroneRecall(drone_id="D1", emergency=True))
    assert all(not (e.type.value == "boot_blocked" and e.data.get("reason") == "in_transit") for e in events), events
    for key in cancelled_before:
        assert state.jobs.jobs[key].status == JobStatus.CANCELLED, state.jobs.jobs[key]
    active = _active_jobs_for(state, "D1")
    assert len(active) == 1 and active[0].job_type == JobType.RECALL_DRONE, active
    assert state.jobs.active_job_ids[0] == active[0].internal_id, state.jobs.active_job_ids
    assert state.ship.cargo_scrap >= scrap_before, (scrap_before, state.ship.cargo_scrap)
    assert any(e.data.get("message_key") == "job_cancelled_emergency_recall" for e in events), events

    # A blocked emergency recall must not destroy the drone's work.
    state = _fresh_state()
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="BUS-A2")
    state.ship.systems["energy_distribution"].health = 0.4
    state.ship.cargo_scrap = 100
    engine.apply_action(state, Repair(drone_id="D1", system_id="energy_distribution"))
    state.ship.drones["D1"].battery = 0.01
    before = list(state.jobs.active_job_ids)
    events = engine.apply_action(state, DroneRecall(drone_id="D1", emergency=True))
    assert any(e.data.get("reason") == "drone_low_battery" for e in events), events
    assert state.jobs.active_job_ids == before, state.jobs.active_job_ids
    assert not any(state.jobs.jobs[k].job_type == JobType.RECALL_DRONE for k in before)

    # recall! all covers deployed drones and leaves docked drones untouched.
    state = _fresh_state()
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="BUS-A2")
    _add_deployed_drone(state, "D2", "BRG-01")
    state.ship.drones["D3"] = DroneState(
        drone_id="D3",
        name="Drone-03",
        status=DroneStatus.DOCKED,
        location=DroneLocation(kind="ship_sector", id="DRN-BAY"),
        battery=1.0,
        integrity=1.0,
    )
    state.ship.systems["energy_distribution"].health = 0.4
    state.ship.systems["power_core"].health = 0.4
    state.ship.cargo_scrap = 200
    engine.apply_action(state, Repair(drone_id="D1", system_id="energy_distribution"))
    engine.apply_action(state, Repair(drone_id="D2", system_id="power_core"))
    events = engine.apply_action(state, DroneRecall(all_drones=True, emergency=True))
    recalls = [e for e in events if e.type.value == "job_queued" and e.data.get("job_type") == "recall_drone"]
    assert {e.data.get("owner_id") for e in recalls} == {"D1", "D2"}, recalls
    assert not _active_jobs_for(state, "D3")

    # A job still waiting for confirmation can re-arm its prompt from state.
    state = _fresh_state()
    _reach_awaiting_repair(state, engine)
    awaiting = _awaiting_repair_job(state)
    prompts = repl._pending_repair_auto_move_prompts(state)
    assert any(prompt.job_id == str(awaiting.internal_id) for prompt in prompts), prompts

    print("DRONE EMERGENCY RECALL SMOKE PASSED")


if __name__ == "__main__":
    main()
