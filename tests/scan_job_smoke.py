from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.config.balance import Balance
from retorno.cli import repl
from retorno.core.actions import Scan
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus, JobType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, region_for_pos


def _make_node(node_id: str, x_ly: float) -> SpaceNode:
    return SpaceNode(
        node_id=node_id,
        name=node_id,
        kind="station",
        radiation_rad_per_s=0.001,
        region=region_for_pos(x_ly, 0.0, 0.0),
        x_ly=x_ly,
        y_ly=0.0,
        z_ly=0.0,
    )


def test_scan_queues_job_and_detects_new_contact() -> None:
    state = create_initial_state_prologue()
    engine = Engine()

    state.ship.power.power_quality = 0.90
    state.ship.systems["core_os"].state = SystemState.NOMINAL
    state.ship.systems["energy_distribution"].state = SystemState.NOMINAL

    sensors = state.ship.systems["sensors"]
    sensors.state = SystemState.NOMINAL
    assert sensors.service is not None
    sensors.service.is_running = True

    origin_id = "SCAN_ORIGIN"
    target_id = "SCAN_TARGET"
    state.world.space.nodes[origin_id] = _make_node(origin_id, 0.0)
    state.world.space.nodes[target_id] = _make_node(target_id, 0.001)
    state.world.current_node_id = origin_id
    state.ship.current_node_id = origin_id
    state.world.current_pos_ly = (0.0, 0.0, 0.0)
    state.world.known_nodes = {origin_id}
    state.world.known_contacts = {origin_id}
    state.world.exploration_recovery.entry_node_id = target_id

    queued = engine.apply_action(state, Scan())
    assert any(e.type == EventType.JOB_QUEUED for e in queued), queued
    active_job = state.jobs.jobs[state.jobs.active_job_ids[-1]]
    assert active_job.job_type == JobType.SCAN
    assert abs(active_job.eta_s - Balance.SCAN_TIME_S) < 1e-6

    completed = engine.tick(state, Balance.SCAN_TIME_S + 1.0)
    assert target_id in state.world.known_nodes
    assert any(e.type == EventType.SIGNAL_DETECTED and e.data.get("contact_id") == target_id for e in completed), completed
    assert any(
        e.type == EventType.JOB_COMPLETED and e.data.get("message_key") == "job_completed_scan"
        for e in completed
    ), completed
    assert active_job.status == JobStatus.COMPLETED

    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_events(state, [("cmd", e) for e in completed])
    text = buf.getvalue()

    assert "=== SCAN ===" in text, text
    assert target_id in text, text
    assert "(scan) new:" in text, text


if __name__ == "__main__":
    test_scan_queues_job_and_detects_new_contact()
    print("SCAN JOB SMOKE PASSED")
