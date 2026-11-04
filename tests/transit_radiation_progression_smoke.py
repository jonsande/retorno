from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.core.engine import Engine
from retorno.model.world import SpaceNode


def main() -> None:
    state = create_initial_state_sandbox()
    engine = Engine()

    # Synthetic endpoints keep this interpolation check independent of which
    # authored locations are active in the current world.
    from_id = "RADIATION_FROM"
    to_id = "RADIATION_TO"
    state.world.space.nodes[from_id] = SpaceNode(from_id, from_id, "derelict")
    state.world.space.nodes[to_id] = SpaceNode(to_id, to_id, "derelict", x_ly=10.0)
    from_node = state.world.space.nodes[from_id]
    to_node = state.world.space.nodes[to_id]
    from_node.radiation_rad_per_s = 0.001
    to_node.radiation_rad_per_s = 0.009

    state.ship.in_transit = True
    state.ship.transit_from = from_id
    state.ship.transit_to = to_id
    state.ship.transit_start_t = 0.0
    state.ship.arrival_t = 100.0

    state.clock.t = 0.0
    env_start = engine._compute_env_radiation_rad_per_s(state)  # noqa: SLF001
    assert abs(env_start - 0.001) < 1e-9, env_start

    state.clock.t = 50.0
    env_mid = engine._compute_env_radiation_rad_per_s(state)  # noqa: SLF001
    assert abs(env_mid - 0.005) < 1e-9, env_mid

    state.clock.t = 100.0
    env_end = engine._compute_env_radiation_rad_per_s(state)  # noqa: SLF001
    assert abs(env_end - 0.009) < 1e-9, env_end

    print("TRANSIT RADIATION PROGRESSION SMOKE PASSED")


if __name__ == "__main__":
    main()
