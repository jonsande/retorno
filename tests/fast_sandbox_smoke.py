from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_fast_sandbox, create_initial_state_sandbox
from retorno.cli.parser import parse_command
from retorno.cli import repl
from retorno.cli.repl import _handle_uplink
from retorno.core.actions import Travel
from retorno.core.engine import Engine
from retorno.core.lore import collect_node_salvage_data_files
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneStatus, compute_drone_effective_profile
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode
from retorno.runtime.data_loader import load_modules


def assert_ready(state) -> None:
    assert state.world.current_node_id == state.ship.current_node_id == "ECHO_7"
    assert state.ship.orbit_status(state.world, "ECHO_7") == "orbit"
    assert not state.ship.in_transit and not state.jobs.active_job_ids
    assert not state.os.debug_enabled
    assert all(s.health == s.health_max_effective and s.state == SystemState.NOMINAL
               and not s.forced_offline and not s.state_locked
               and (not s.service or s.service.is_running) for s in state.ship.systems.values())
    assert state.ship.power.p_gen_kw >= state.ship.power.p_load_kw
    assert state.ship.power.e_batt_kwh == state.ship.power.e_batt_max_kwh
    assert not any(alert.is_active for alert in state.events.alerts.values())
    node = state.world.space.nodes["ECHO_7"]
    assert state.world.current_pos_ly == (node.x_ly, node.y_ly, node.z_ly)
    assert node.salvage_scrap_available == node.recoverable_drones_count == 0
    assert not node.salvage_modules_available
    pool = state.world.node_pools["ECHO_7"]
    assert pool.uplink_data_consumed and pool.node_cleaned
    assert set(pool.uplink_route_pool) <= state.world.known_links["ECHO_7"]
    for file in collect_node_salvage_data_files(state, "ECHO_7"):
        assert state.os.fs[f'/remote/ECHO_7/{file["path"].lstrip("/")}'].content == file["content"]
    assert any(p.startswith("/logs/nav/uplink_ECHO_7_") for p in state.os.fs)
    assert state.ship.manifest_scrap == state.ship.cargo_scrap
    assert state.ship.manifest_modules == state.ship.cargo_modules
    assert not state.ship.manifest_dirty
    for drone in state.ship.drones.values():
        profile = compute_drone_effective_profile(drone, load_modules())
        assert drone.status == DroneStatus.DOCKED
        assert drone.location.kind == "ship_sector"
        assert drone.location.id == state.ship.systems["drone_bay"].sector_id
        assert drone.integrity == profile.integrity_max_effective
        assert drone.battery == profile.battery_max_effective
        assert drone.dose_rad == 0


def main() -> None:
    assert parse_command("debug scenario fast_sandbox") == ("DEBUG_SCENARIO", "fast_sandbox")
    for seed in (0, 1, 7):
        original = create_initial_state_sandbox(seed=seed)
        echo = original.world.space.nodes["ECHO_7"]
        output = StringIO()
        with redirect_stdout(output):
            state = create_initial_state_fast_sandbox(seed=seed)
        assert not output.getvalue()
        assert_ready(state)
        assert len(state.ship.drones) == len(original.ship.drones) + echo.recoverable_drones_count
        assert state.ship.cargo_scrap == original.ship.cargo_scrap + echo.salvage_scrap_available
        assert state.ship.cargo_modules == original.ship.cargo_modules + echo.salvage_modules_available
        assert state.clock.t == 0

        # An exhausted uplink cannot duplicate recovered information or rewards.
        state.ship.docked_node_id = "ECHO_7"
        known = set(state.world.known_nodes)
        cargo = list(state.ship.cargo_modules)
        with redirect_stdout(StringIO()):
            _handle_uplink(state)
        assert state.world.known_nodes == known
        assert state.ship.cargo_modules == cargo
        state.ship.docked_node_id = None

        with TemporaryDirectory() as directory:
            path = Path(directory) / "slot.dat"
            save_single_slot(state, path)
            loaded = load_single_slot(path)
            assert loaded is not None
            assert_ready(loaded.state)

        engine = Engine()
        engine.tick(state, 1.0)
        assert not state.ship.power.brownout
        assert all(s.state == SystemState.NOMINAL for s in state.ship.systems.values())
        destination = sorted(state.world.known_links["ECHO_7"])[0]
        engine.apply_action(state, Travel(node_id=destination))
        assert state.ship.in_transit and state.ship.transit_to == destination

    # Exercise the optional fleet recovery branch regardless of salvage rolls.
    original = create_initial_state_sandbox(seed=0)
    original.world.space.nodes["ECHO_7"].recoverable_drones_count = 2
    with patch("retorno.bootstrap.create_initial_state_sandbox", return_value=original):
        recovered = create_initial_state_fast_sandbox(seed=0)
    assert len(recovered.ship.drones) == 3
    assert_ready(recovered)

    # Changing unobserved physical contents must not reveal another location.
    base = create_initial_state_sandbox(seed=0)
    hidden = deepcopy(base)
    hidden.world.space.nodes["SECRET_TEST_NODE"] = SpaceNode(
        node_id="SECRET_TEST_NODE", name="Secret", kind="station",
        x_ly=9000, y_ly=9000, z_ly=9000,
    )
    results = []
    for source in (base, hidden):
        with patch("retorno.bootstrap.create_initial_state_sandbox", return_value=source):
            state = create_initial_state_fast_sandbox(seed=0)
        public = StringIO()
        with redirect_stdout(public):
            repl.render_status(state)
        results.append((state.world.known_nodes, state.world.known_contacts,
                        state.world.known_links, state.os.fs, public.getvalue()))
    assert results[0] == results[1]

    # Verify both entry points select the uppercase environment preset without
    # loading a save, stopping before they launch interactive loops or audio.
    from retorno.ui_textual.app import RetornoTextualApp

    class SelectedScenario(Exception):
        pass

    def inspect_loop(engine, state, **kwargs):
        assert_ready(state)
        raise SelectedScenario

    for target in ("retorno.cli.repl", "retorno.ui_textual.app"):
        with patch.dict("os.environ", {"RETORNO_SCENARIO": "FAST_SANDBOX"}), \
             patch(f"{target}.load_single_slot", side_effect=AssertionError("Save must be bypassed")), \
             patch(f"{target}.GameLoop", side_effect=inspect_loop), \
             patch("retorno.cli.repl.AudioManager"), \
             patch("sys.argv", ["retorno"]):
            try:
                if target.endswith("repl"):
                    repl.main()
                else:
                    RetornoTextualApp()
            except SelectedScenario:
                pass
            else:
                raise AssertionError("Expected scenario selection")
    print("FAST SANDBOX SMOKE PASSED")


if __name__ == "__main__":
    main()
