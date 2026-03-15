from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.core.engine import Engine
from retorno.model.jobs import JobStatus, JobType, RiskProfile, TargetRef


def main() -> None:
    engine = Engine()
    state = create_initial_state_prologue()

    queued_1 = engine._enqueue_job(
        state,
        JobType.CARGO_AUDIT,
        TargetRef(kind="ship", id=state.ship.ship_id),
        owner_id=None,
        eta_s=1.0,
        params={},
    )
    queued_2 = engine._enqueue_job(
        state,
        JobType.CARGO_AUDIT,
        TargetRef(kind="ship", id=state.ship.ship_id),
        owner_id=None,
        eta_s=100.0,
        params={},
    )

    first_key = queued_1[0].data["job_key"]
    second_key = queued_2[0].data["job_key"]
    assert queued_1[0].data["job_id"] == "J1", queued_1[0].data
    assert queued_2[0].data["job_id"] == "J2", queued_2[0].data

    engine.tick(state, 2.0)
    assert state.jobs.jobs[first_key].status == JobStatus.COMPLETED
    assert state.jobs.jobs[first_key].job_id == "CJ1", state.jobs.jobs[first_key]
    assert state.jobs.jobs[second_key].job_id == "J2", state.jobs.jobs[second_key]

    queued_3 = engine._enqueue_job(
        state,
        JobType.CARGO_AUDIT,
        TargetRef(kind="ship", id=state.ship.ship_id),
        owner_id=None,
        eta_s=100.0,
        params={},
    )
    queued_4 = engine._enqueue_job(
        state,
        JobType.CARGO_AUDIT,
        TargetRef(kind="ship", id=state.ship.ship_id),
        owner_id=None,
        eta_s=100.0,
        params={"emergency": True},
        risk=RiskProfile(p_fail_per_s=1.0),
    )

    third_key = queued_3[0].data["job_key"]
    fourth_key = queued_4[0].data["job_key"]
    assert queued_3[0].data["job_id"] == "J3", queued_3[0].data
    assert queued_4[0].data["job_id"] == "J4", queued_4[0].data

    engine.tick(state, 1.0)
    assert state.jobs.jobs[fourth_key].status == JobStatus.FAILED
    assert state.jobs.jobs[fourth_key].job_id == "FJ2", state.jobs.jobs[fourth_key]
    assert state.jobs.jobs[second_key].job_id == "J2", state.jobs.jobs[second_key]
    assert state.jobs.jobs[third_key].job_id == "J3", state.jobs.jobs[third_key]

    engine.tick(state, 200.0)
    assert state.jobs.jobs[second_key].job_id == "CJ3", state.jobs.jobs[second_key]
    assert state.jobs.jobs[third_key].job_id == "CJ4", state.jobs.jobs[third_key]
    assert not state.jobs.active_job_ids, state.jobs.active_job_ids
    assert state.jobs.next_active_job_seq == 1, state.jobs.next_active_job_seq

    queued_5 = engine._enqueue_job(
        state,
        JobType.CARGO_AUDIT,
        TargetRef(kind="ship", id=state.ship.ship_id),
        owner_id=None,
        eta_s=10.0,
        params={},
    )
    assert queued_5[0].data["job_id"] == "J1", queued_5[0].data

    print("JOB ID NUMBERING SMOKE PASSED")


if __name__ == "__main__":
    main()
