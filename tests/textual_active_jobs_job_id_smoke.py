from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.core.engine import Engine
from retorno.model.jobs import JobStatus, JobType, TargetRef
from retorno.ui_textual import presenter


def main() -> None:
    engine = Engine()
    state = create_initial_state_prologue()

    engine._enqueue_job(
        state,
        JobType.RECALL_DRONE,
        TargetRef(kind="drone", id="D1"),
        owner_id="D1",
        eta_s=30.0,
        params={"drone_id": "D1"},
    )
    engine._enqueue_job(
        state,
        JobType.RECALL_DRONE,
        TargetRef(kind="drone", id="D1"),
        owner_id="D1",
        eta_s=40.0,
        params={"drone_id": "D1"},
    )

    engine.tick(state, 1.0)

    jobs = [state.jobs.jobs[job_key] for job_key in state.jobs.active_job_ids]
    assert [job.job_id for job in jobs] == ["J1", "J2"], jobs
    assert [job.status for job in jobs] == [JobStatus.RUNNING, JobStatus.QUEUED], jobs

    lines = presenter.build_jobs_lines(state)
    assert lines[0] == "Active jobs (queued/running):", lines
    assert any(line.startswith("- J1:") and "owner=D1" in line for line in lines), lines
    assert any(line.startswith("- J2:") and "owner=D1" in line for line in lines), lines
    assert not any(line.startswith("- D1:") for line in lines), lines

    print("TEXTUAL ACTIVE JOBS JOB ID SMOKE PASSED")


if __name__ == "__main__":
    main()
