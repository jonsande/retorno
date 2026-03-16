from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.world import SpaceNode
from retorno.runtime.loop import GameLoop


def main() -> None:
    state = create_initial_state_sandbox()
    engine = Engine()
    loop = GameLoop(engine, state)

    from_id = state.world.current_node_id
    to_id = "HIBERNATE_WAKE_TARGET"
    from_node = state.world.space.nodes[from_id]
    to_node = SpaceNode(
        node_id=to_id,
        name="Hibernate Wake Target",
        kind="station",
        region=from_node.region or "disk",
        x_ly=from_node.x_ly + 1.0,
        y_ly=from_node.y_ly,
        z_ly=from_node.z_ly,
    )
    state.world.space.nodes[to_id] = to_node
    from_node.radiation_rad_per_s = 0.001
    to_node.radiation_rad_per_s = 0.009

    state.ship.in_transit = True
    state.ship.transit_from = from_id
    state.ship.transit_to = to_id
    state.ship.transit_start_t = 0.0
    state.ship.arrival_t = 1000.0
    state.world.current_node_id = from_id
    state.ship.current_node_id = from_id
    state.world.current_pos_ly = (from_node.x_ly, from_node.y_ly, from_node.z_ly)

    threshold = max(0.0, float(Balance.HIBERNATE_WAKE_ENV_RAD_THRESHOLD_RAD_PER_S))
    expected_progress = (threshold - from_node.radiation_rad_per_s) / (
        to_node.radiation_rad_per_s - from_node.radiation_rad_per_s
    )
    expected_wake_t = state.ship.transit_start_t + expected_progress * (
        state.ship.arrival_t - state.ship.transit_start_t
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        repl._run_hibernate(loop, years=0.01, wake_on_low_battery=False)
    out = buf.getvalue()

    assert "ambient radiation reached threshold" in out, out
    assert state.ship.in_transit is True, "ship should wake before arrival when threshold is crossed"
    assert abs(state.clock.t - expected_wake_t) < 1e-3, (state.clock.t, expected_wake_t)

    print("HIBERNATE RADIATION WAKE SMOKE PASSED")


if __name__ == "__main__":
    main()
