from __future__ import annotations

import contextlib
import io

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.model.world import SpaceNode


def _enable_ship_survey(state) -> None:
    sensors = state.ship.systems["sensors"]
    sensors.state = sensors.state.NOMINAL
    sensors.forced_offline = False
    sensors.service.is_running = True
    sensors.service.is_installed = True

    data_core = state.ship.systems["data_core"]
    data_core.state = data_core.state.NOMINAL
    data_core.forced_offline = False
    data_core.service.is_running = True
    data_core.service.is_installed = True


def _render(state, target_id: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        repl.render_ship_survey(state, target_id)
    return out.getvalue()


def main() -> None:
    state = create_initial_state_sandbox()
    _enable_ship_survey(state)

    state.world.current_node_id = "ECHO_7"
    state.ship.current_node_id = "ECHO_7"
    current = state.world.space.nodes["ECHO_7"]
    current.radiation_rad_per_s = 0.0032
    state.world.visited_nodes.add("ECHO_7")
    state.ship.sensors_range_ly = 0.01

    known_text = _render(state, "ECHO_7")
    assert "node_radiation: 0.0032rad/s" in known_text, known_text

    target = SpaceNode(
        node_id="RAD_UNKNOWN",
        name="Remote Radiation Contact",
        kind="station",
        radiation_rad_per_s=0.0087,
        x_ly=current.x_ly + 5.0,
        y_ly=current.y_ly,
        z_ly=current.z_ly,
    )
    state.world.space.nodes[target.node_id] = target
    target.radiation_rad_per_s = 0.0087
    state.world.known_nodes.add(target.node_id)
    state.world.known_contacts.add(target.node_id)
    state.world.visited_nodes.discard(target.node_id)

    unknown_text = _render(state, target.node_id)
    assert "node_radiation: unknown" in unknown_text, unknown_text

    print("SHIP SURVEY RADIATION SMOKE PASSED")


if __name__ == "__main__":
    main()
