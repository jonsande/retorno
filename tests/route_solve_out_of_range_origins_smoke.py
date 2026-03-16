from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.core.actions import RouteSolve
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link, region_for_pos


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


def test_route_solve_out_of_range_origins() -> None:
    state = create_initial_state_prologue()
    engine = Engine()

    sensors = state.ship.systems["sensors"]
    sensors.state = SystemState.NOMINAL
    assert sensors.service is not None
    sensors.service.is_running = True

    sensor_range = float(state.ship.sensors_range_ly)
    current_id = "TEST_CUR"
    reachable_id = "TEST_REACHABLE"
    remote_id = "TEST_REMOTE"
    target_id = "TEST_TARGET"

    target_x = sensor_range + 20.0
    reachable_dist = max(0.1, sensor_range * 0.6)
    remote_dist = max(0.1, sensor_range * 0.3)
    reachable_x = target_x - reachable_dist
    remote_x = target_x - remote_dist

    state.world.space.nodes[current_id] = _make_node(current_id, 0.0)
    state.world.space.nodes[reachable_id] = _make_node(reachable_id, reachable_x)
    state.world.space.nodes[remote_id] = _make_node(remote_id, remote_x)
    state.world.space.nodes[target_id] = _make_node(target_id, target_x)

    state.world.current_node_id = current_id
    state.ship.current_node_id = current_id
    state.world.known_nodes = {current_id, reachable_id, remote_id, target_id}
    state.world.known_contacts = set(state.world.known_nodes)
    state.world.known_links = {}
    add_known_link(state.world, current_id, reachable_id, bidirectional=True)
    add_known_link(state.world, remote_id, target_id, bidirectional=True)

    events = engine.apply_action(state, RouteSolve(node_id=target_id))
    assert any(e.type == EventType.BOOT_BLOCKED for e in events), events
    assert any((e.data or {}).get("reason") == "out_of_range" for e in events), events

    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_events(state, events)
    text = buf.getvalue()

    assert f"target out of sensor range ({target_id})" in text, text
    assert f"Known nodes from which {target_id} is within route-solve range:" in text, text
    assert f"- {reachable_id} (reachable, route solve possible, {reachable_dist:.2f}ly)" in text, text
    assert f"- {remote_id} (no known path from current, route already known, {remote_dist:.2f}ly)" in text, text

    print("ROUTE SOLVE OUT OF RANGE ORIGINS SMOKE PASSED")


if __name__ == "__main__":
    test_route_solve_out_of_range_origins()
