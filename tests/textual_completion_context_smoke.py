from __future__ import annotations

import os

from retorno.ui_textual.app import RetornoTextualApp


def main() -> None:
    old_scenario = os.environ.get("RETORNO_SCENARIO")
    try:
        os.environ["RETORNO_SCENARIO"] = "sandbox"
        app = RetornoTextualApp(force_new_game=True)
        state = app.loop.state

        state.world.current_node_id = "ECHO_7"
        state.ship.current_node_id = "ECHO_7"
        state.ship.docked_node_id = None
        state.world.known_nodes.update({"ECHO_7", "CURL_12", "WRECK_B0C2BC"})
        state.world.known_contacts.update({"ECHO_7", "CURL_12", "WRECK_B0C2BC"})

        deploy_candidates = set(app._get_completion_candidates(state, "drone deploy D1 ", ""))
        assert "BRG-01" in deploy_candidates, deploy_candidates
        assert "CRG-01" in deploy_candidates, deploy_candidates
        assert "DRN-BAY" in deploy_candidates, deploy_candidates
        assert "PWR-A2" in deploy_candidates, deploy_candidates
        assert "ECHO_7" in deploy_candidates, deploy_candidates
        assert "CURL_12" not in deploy_candidates, deploy_candidates
        assert "WRECK_B0C2BC" not in deploy_candidates, deploy_candidates

        salvage_candidates = set(app._get_completion_candidates(state, "drone salvage data D1 ", ""))
        assert salvage_candidates == {"ECHO_7"}, salvage_candidates

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
    finally:
        if old_scenario is None:
            os.environ.pop("RETORNO_SCENARIO", None)
        else:
            os.environ["RETORNO_SCENARIO"] = old_scenario

    print("TEXTUAL COMPLETION CONTEXT SMOKE PASSED")


if __name__ == "__main__":
    main()
