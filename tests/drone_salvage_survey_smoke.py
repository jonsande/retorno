from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_sandbox, create_initial_state_prologue
from retorno.cli.parser import parse_command
from retorno.core.actions import DroneDeploy, DroneSurvey, SalvageDrone
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneStatus
from retorno.worldgen.generator import ensure_sector_generated


def _assert_any_event(events, key: str) -> dict:
    for e in events:
        if isinstance(e.data, dict) and e.data.get("message_key") == key:
            return e.data
    raise AssertionError(f"Expected event with message_key={key}; got {[getattr(e, 'data', {}) for e in events]}")


def _recoverable_map_for_sector(state, sector_id: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for node_id, node in state.world.space.nodes.items():
        if node_id.startswith("UNKNOWN"):
            continue
        from retorno.model.world import sector_id_for_pos
        if sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly) == sector_id:
            out[node_id] = int(getattr(node, "recoverable_drones_count", 0))
    return out


def main() -> None:
    engine = Engine()
    state = create_initial_state_sandbox()
    state.ship.docked_node_id = "ECHO_7"

    # Force predictable survey payload in sandbox node.
    node = state.world.space.nodes["ECHO_7"]
    node.salvage_scrap_available = 17
    node.salvage_modules_available = ["bus_stabilizer"]
    node.recoverable_drones_count = 2

    deploy_events = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="ECHO_7"))
    assert deploy_events, "Expected deploy job queued"
    tick_events = engine.tick(state, 30.0)
    _assert_any_event(tick_events, "job_completed_deploy")

    survey_action = parse_command("drone survey D1 ECHO_7")
    assert isinstance(survey_action, DroneSurvey), f"Unexpected survey parse: {survey_action!r}"
    survey_queue_events = engine.apply_action(state, survey_action)
    assert survey_queue_events, "Expected survey job queued"
    survey_tick_events = engine.tick(state, 30.0)
    survey_data = _assert_any_event(survey_tick_events, "job_completed_drone_survey")
    assert survey_data.get("node_id") == "ECHO_7"
    assert int(survey_data.get("scrap_available", -1)) == 17
    assert bool(survey_data.get("modules_detected", False)) is True
    assert int(survey_data.get("recoverable_drones_count", -1)) == 2
    assert node.recoverable_drones_count == 2, "Survey must not consume recoverable drones"

    parsed_singular = parse_command("drone salvage drone D1 ECHO_7")
    parsed_plural = parse_command("drone salvage drones D1 ECHO_7")
    assert isinstance(parsed_singular, SalvageDrone), f"Unexpected singular parse: {parsed_singular!r}"
    assert isinstance(parsed_plural, SalvageDrone), f"Unexpected plural parse: {parsed_plural!r}"

    salvage_queue_events = engine.apply_action(state, parsed_singular)
    assert salvage_queue_events, "Expected salvage drone job queued"
    salvage_tick_events = engine.tick(state, 30.0)
    salvage_data = _assert_any_event(salvage_tick_events, "job_completed_drone_salvage")
    assert int(salvage_data.get("recovered_count", -1)) == 2
    recovered_ids = salvage_data.get("recovered_ids", [])
    assert recovered_ids == ["D2", "D3"], f"Expected sequential IDs ['D2','D3']; got {recovered_ids}"
    assert node.recoverable_drones_count == 0, "Node drones must be depleted after salvage"

    for did in ["D2", "D3"]:
        d = state.ship.drones.get(did)
        assert d is not None, f"Missing salvaged drone {did}"
        assert d.status == DroneStatus.DOCKED, f"Salvaged drone {did} should be docked"
        assert d.location.kind == "ship_sector" and d.location.id == "drone_bay", (
            f"Unexpected location for {did}: {d.location.kind}:{d.location.id}"
        )

    # Save/load persistence for recovered drones and depleted node state.
    with TemporaryDirectory() as tmp_dir:
        save_path = Path(tmp_dir) / "slot.dat"
        save_single_slot(state, save_path)
        loaded = load_single_slot(save_path)
        assert loaded is not None, "Expected load after save"
        loaded_state = loaded.state
        loaded_node = loaded_state.world.space.nodes["ECHO_7"]
        assert loaded_node.recoverable_drones_count == 0, "Depleted drone count must persist"
        assert "D2" in loaded_state.ship.drones and "D3" in loaded_state.ship.drones, (
            "Recovered drones must persist in fleet"
        )

    # Procedural determinism check (same seed => same recoverable drones distribution).
    state_a = create_initial_state_prologue()
    state_b = create_initial_state_prologue()
    sector_id = "S+000_+001_+000"
    ensure_sector_generated(state_a, sector_id)
    ensure_sector_generated(state_b, sector_id)
    map_a = _recoverable_map_for_sector(state_a, sector_id)
    map_b = _recoverable_map_for_sector(state_b, sector_id)
    assert map_a == map_b, "Procedural recoverable drones must be deterministic for same seed"

    print("DRONE SALVAGE/SURVEY SMOKE PASSED")


if __name__ == "__main__":
    main()
