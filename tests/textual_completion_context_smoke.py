from __future__ import annotations

import os

from retorno.ui_textual.app import RetornoTextualApp
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


def main() -> None:
    old_scenario = os.environ.get("RETORNO_SCENARIO")
    try:
        os.environ["RETORNO_SCENARIO"] = "sandbox"
        app = RetornoTextualApp(force_new_game=True)
        state = app.loop.state

        state.world.current_node_id = "ECHO_7"
        state.ship.current_node_id = "ECHO_7"
        state.ship.docked_node_id = None
        sensor_range = float(state.ship.sensors_range_ly)
        current = state.world.space.nodes["ECHO_7"]
        in_range_id = "WRECK_B0C2BC"
        out_of_range_id = "WRECK_FAR_TEST"
        state.world.space.nodes[in_range_id] = _make_node(in_range_id, current.x_ly + max(0.1, sensor_range * 0.5))
        state.world.space.nodes[out_of_range_id] = _make_node(out_of_range_id, current.x_ly + sensor_range + 5.0)

        sensors = state.ship.systems["sensors"]
        sensors.state = SystemState.OFFLINE

        state.world.known_nodes.update({"ECHO_7", "CURL_12"})
        state.world.known_contacts.update({"ECHO_7", "CURL_12", in_range_id, out_of_range_id})
        add_known_link(state.world, "ECHO_7", "CURL_12", bidirectional=True)

        dock_candidates = set(app._get_completion_candidates(state, "dock ", ""))
        assert dock_candidates == {"ECHO_7"}, dock_candidates

        route_candidates = set(app._get_completion_candidates(state, "route solve ", ""))
        assert route_candidates == {"ECHO_7", in_range_id}, route_candidates

        nav_candidates = set(app._get_completion_candidates(state, "nav ", ""))
        assert "CURL_12" in nav_candidates, nav_candidates
        assert in_range_id not in nav_candidates, nav_candidates
        assert out_of_range_id not in nav_candidates, nav_candidates

        deploy_candidates = set(app._get_completion_candidates(state, "drone deploy D1 ", ""))
        assert "BRG-01" in deploy_candidates, deploy_candidates
        assert "CRG-01" in deploy_candidates, deploy_candidates
        assert "DRN-BAY" in deploy_candidates, deploy_candidates
        assert "PWR-A2" in deploy_candidates, deploy_candidates
        assert "ECHO_7" in deploy_candidates, deploy_candidates
        assert "CURL_12" not in deploy_candidates, deploy_candidates
        assert in_range_id not in deploy_candidates, deploy_candidates
        assert out_of_range_id not in deploy_candidates, deploy_candidates

        salvage_candidates = set(app._get_completion_candidates(state, "drone salvage data D1 ", ""))
        assert salvage_candidates == {"ECHO_7"}, salvage_candidates

        recall_candidates = set(app._get_completion_candidates(state, "drone recall ", ""))
        assert "D1" in recall_candidates, recall_candidates
        assert "all" in recall_candidates, recall_candidates

        # module inspect should complete from full catalog, not only inventory.
        state.ship.cargo_modules = []
        state.ship.manifest_modules = []
        module_candidates = set(app._get_completion_candidates(state, "module inspect b", "b"))
        assert "bus_stabilizer" in module_candidates, module_candidates

        debug_add_candidates = set(app._get_completion_candidates(state, "debug ", ""))
        assert "add" in debug_add_candidates, debug_add_candidates

        debug_add_kind_candidates = set(app._get_completion_candidates(state, "debug add ", ""))
        assert {"scrap", "module", "drone", "drones"}.issubset(debug_add_kind_candidates), debug_add_kind_candidates

        debug_add_module_candidates = set(app._get_completion_candidates(state, "debug add module u", "u"))
        assert "utility_cargo_frame" in debug_add_module_candidates, debug_add_module_candidates

        # drone uninstall should suggest installed modules in target drone.
        state.ship.drones["D1"].installed_modules = ["field_service_rig"]
        state.ship.installed_modules = ["bus_stabilizer"]
        uninstall_candidates = set(app._get_completion_candidates(state, "drone uninstall D1 ", ""))
        assert uninstall_candidates == {"field_service_rig", "bus_stabilizer"}, uninstall_candidates

        state.world.current_node_id = "UNKNOWN"
        state.ship.current_node_id = "UNKNOWN"
        state.world.known_nodes = {"ECHO_7", "UNKNOWN"}
        state.world.known_contacts = {"ECHO_7", "UNKNOWN"}
        state.world.known_links = {"UNKNOWN": {"ECHO_7"}}

        route_unknown_origin_candidates = set(app._get_completion_candidates(state, "route solve ", ""))
        assert route_unknown_origin_candidates == set(), route_unknown_origin_candidates

        nav_unknown_origin_candidates = set(app._get_completion_candidates(state, "nav ", ""))
        assert "ECHO_7" in nav_unknown_origin_candidates, nav_unknown_origin_candidates
    finally:
        if old_scenario is None:
            os.environ.pop("RETORNO_SCENARIO", None)
        else:
            os.environ["RETORNO_SCENARIO"] = old_scenario

    print("TEXTUAL COMPLETION CONTEXT SMOKE PASSED")


if __name__ == "__main__":
    main()
