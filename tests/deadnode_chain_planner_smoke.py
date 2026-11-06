from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict
import copy
import math
import pickle
import random
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox
from retorno.core import lore
from retorno.core.actions import SalvageData, Travel, TravelAbort
from retorno.core.deadnode_planner import (
    InformationStatus, Materialization, Mechanism, PlanningContext, Role,
    Viability, information_capabilities, propose_deadnode_chain,
)
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.os import AccessLevel, FSNode, FSNodeType
from retorno.model.world import (
    DeadNodeState, ExplorationRecoveryState, NodePoolState, SectorGenState, SpaceNode,
    add_known_link, is_hop_within_cap, record_intel, region_for_pos, sector_id_for_pos,
)
from retorno.runtime.data_loader import load_worldgen_archetypes, load_worldgen_templates


def _node(nid, x, y=25.0, kind="derelict"):
    return SpaceNode(nid, nid, kind, region=region_for_pos(x, y, 1.0),
                     x_ly=x, y_ly=y, z_ly=1.0, salvage_scrap_available=1)


def _state(distance=100.0, y=25.0):
    state = create_initial_state_sandbox()
    state.meta.rng_seed = state.world.rng_seed = 271828
    state.meta.rng_counter = 17
    world = state.world
    # This diagnostic fixture installs pre-contract synthetic archives, not a
    # certified historical-information-v1 universe. Retain its legacy rules.
    world.information_version = "legacy-information-v0"
    world.information_definition = None
    world.space.nodes = {"A": _node("A", 0, y), "D": _node("D", distance, y)}
    world.space.edges = {}
    world.current_node_id = state.ship.current_node_id = "A"
    world.current_pos_ly = (0, y, 1.0)
    state.ship.docked_node_id = None
    state.ship.in_transit = False
    state.ship.sensors_range_ly = 2.5
    world.known_nodes = {"A", "D"}
    world.known_contacts = {"A", "D"}
    world.known_links = {}
    world.known_intel = {}
    world.intel = []
    world.visited_nodes = {"A"}
    world.forced_hidden_nodes = set()
    world.generated_sectors = set()
    world.sector_states = {}
    world.intersector_link_pairs = set()
    world.sparse_guardrail_done = True
    world.dead_nodes = {"D": DeadNodeState(stuck_since_t=0.0, dead_since_t=0.0)}
    world.exploration_recovery = ExplorationRecoveryState()
    world.node_pools = {nid: _pool() for nid in world.space.nodes}
    return state


def _pool():
    return NodePoolState(base_files=[{"path": "/logs/survey.txt", "access": "guest", "content": "survey"}])


def _add(state, nid, x, kind="derelict"):
    state.world.space.nodes[nid] = _node(nid, x, state.world.current_pos_ly[1], kind)
    state.world.node_pools[nid] = _pool()


def _plan(state, allow_new=True):
    # Full serialized state, not just navigation fields, must remain identical.
    before = pickle.dumps(state)
    global_rng = random.getstate()
    result = propose_deadnode_chain(state, "D", PlanningContext(allow_new_nodes=allow_new))
    assert pickle.dumps(state) == before
    assert random.getstate() == global_rng
    assert result == propose_deadnode_chain(state, "D", PlanningContext(allow_new_nodes=allow_new))
    assert pickle.dumps(state) == before
    return result


def _assert_hops(result):
    nodes = {stage.node.node_id: stage.node for stage in result.stages}
    for hop in result.hops:
        assert 0 < hop.distance_ly <= 45.0
        assert math.isclose(hop.distance_ly, math.dist(nodes[hop.from_id].position_ly,
                                                      nodes[hop.to_id].position_ly), abs_tol=1e-10)
    assert len(result.stages) == len(result.hops) + 1


def test_direct_and_inclusive_cap():
    for distance in (40.0, 45.0):
        state = _state(distance)
        result = _plan(state)
        assert result.physical_chain_valid and result.geometry_valid
        assert [h.distance_ly for h in result.hops] == [distance]
        assert not result.new_nodes
        assert result.information_status == InformationStatus.FUTURE_REQUIRED
        assert result.materialization == Materialization.EXISTING
        assert result.viability == Viability.CONDITIONAL and not result.ready_with_existing_mechanics
        assert result.hops[0].hint.mechanism == Mechanism.RECOVERY_SIGNAL
        assert {d.code for d in result.hops[0].hint.dependencies} >= {"comms", "radiod"}
        assert not state.world.known_links


def test_70_and_100_with_valid_canonical_slots():
    for distance, count in ((70.0, 1), (100.0, 2)):
        result = _plan(_state(distance))
        _assert_hops(result)
        assert len(result.new_nodes) == count
        assert result.physical_chain_valid and result.materialization == Materialization.CONDITIONAL
        assert all(n.materialization == Materialization.CONDITIONAL for n in result.new_nodes)
        assert not result.ready_with_existing_mechanics
    assert {node.kind for node in result.new_nodes} == {"relay", "station"}
    assert all(math.isclose(h.distance_ly, 100/3, abs_tol=1e-10) for h in result.hops)


def test_existing_chain_preferred_and_revealed_progressively():
    state = _state()
    _add(state, "E1", 35)
    _add(state, "E2", 70)
    result = _plan(state)
    assert result.reused_nodes == ("A", "E1", "E2", "D")
    assert [h.distance_ly for h in result.hops] == [35.0, 35.0, 30.0]
    assert not result.new_nodes
    assert [h.hint.mechanism for h in result.hops] == [Mechanism.RECOVERY_SIGNAL,
                                                      Mechanism.SALVAGE_DATA, Mechanism.SALVAGE_DATA]
    assert result.stages[1].role == result.stages[2].role == Role.BOTH
    assert result.stages[-1].next_hint is None
    assert not {"E1", "E2"} & state.world.known_nodes
    assert all(h.hint.requires_preparation for h in result.hops)


def test_mixed_existing_and_new():
    state = _state()
    _add(state, "E", 70, "ship")
    result = _plan(state)
    _assert_hops(result)
    assert "E" in result.reused_nodes and len(result.new_nodes) == 1
    assert len(result.hops) == 3
    assert result.stages[-2].node.kind == "ship"


def test_alternative_directed_origin_and_disconnected_impostor():
    state = _state(70)
    _add(state, "B", 30)
    state.world.known_nodes.add("B")
    state.world.known_contacts.add("B")
    assert add_known_link(state.world, "A", "B")
    result = _plan(state)
    assert result.origin_id == "B" and [h.distance_ly for h in result.hops] == [40.0]
    assert result.origin_access_path == ("A", "B")
    assert result.hops[0].hint.source_id == state.ship.ship_id
    assert result.hops[0].hint.source_ref == "A"
    state.world.known_links = {"B": {"A"}}
    result = _plan(state)
    assert result.origin_id == "A", "A reverse route must not authorize B as origin"
    # A physically close B is still usable only after a proposed, disclosed hop.
    assert result.reused_nodes == ("A", "B", "D")
    assert result.hops[0].hint.mechanism == Mechanism.RECOVERY_SIGNAL


def test_invalid_origin_and_endpoints():
    state = _state()
    del state.world.space.nodes["D"]
    result = _plan(state)
    assert result.viability == Viability.REJECTED
    state = _state()
    del state.world.space.nodes["A"]
    assert _plan(state).reasons == ("no_operational_origin",)
    state = _state()
    state.world.space.nodes["D"].x_ly = float("inf")
    assert _plan(state).viability == Viability.REJECTED


def test_known_route_projection_does_not_accept_stale_edges():
    state = _state()
    state.world.known_links = {"A": {"D", "MISSING"}}
    assert not is_hop_within_cap(state.world, "A", "D")
    result = _plan(state)
    assert all(h.hint.mechanism != Mechanism.KNOWN_ROUTE for h in result.hops)
    _assert_hops(result)


def test_types_follow_real_region_archetype_and_slot_rules():
    catalogs = load_worldgen_archetypes()
    templates = load_worldgen_templates()
    observed = set()
    for y in (25.0, 35.0, 45.0, 55.0):
        result = _plan(_state(y=y))
        assert result.physical_chain_valid
        for node in result.new_nodes:
            observed.add(node.kind)
            cfg = catalogs[node.archetype]
            assert node.kind not in cfg["forbidden_kinds"]
            assert cfg["kind_caps"][node.kind] > 0
            assert templates[node.region]["archetype_weights"][node.archetype] > 0
            assert node.region == region_for_pos(*node.position_ly)
            assert node.sector_id == sector_id_for_pos(*node.position_ly)
            assert node.slot_index is not None
            assert any(reason.startswith("canonical_slot:") for reason in node.selection_reasons)
    assert {"relay", "station", "ship", "derelict"} <= observed


def test_waystation_has_uplink_but_not_salvage_data():
    assert information_capabilities("waystation") == (Mechanism.UPLINK,)
    state = _state()
    _add(state, "E1", 35, "waystation")
    _add(state, "E2", 70, "ship")
    result = _plan(state, False)
    assert result.hops[1].hint.mechanism == Mechanism.UPLINK
    state.world.current_node_id = state.ship.current_node_id = "E1"
    state.ship.docked_node_id = "E1"
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="world_node", id="E1")
    drone.battery = 1.0
    events = Engine().apply_action(state, SalvageData(drone_id="D1", node_id="E1"))
    assert any(e.data.get("reason") == "node_invalid" for e in events), events


def test_unknown_type_cannot_provide_mandatory_data():
    state = _state(70)
    _add(state, "E", 35, "transponder")
    result = _plan(state, False)
    assert result.physical_chain_valid
    assert result.information_status == InformationStatus.UNAVAILABLE
    assert result.hops[-1].hint.mechanism == Mechanism.UNAVAILABLE
    assert result.viability == Viability.INCOMPLETE


def test_unavailable_receivers_are_not_reopened():
    for condition in ("visited", "closed", "clean", "data_complete", "no_pool"):
        state = _state(70)
        _add(state, "E", 35)
        pool = state.world.node_pools["E"]
        if condition == "visited":
            state.world.visited_nodes.add("E")
        elif condition == "closed":
            pool.window_open = False
        elif condition == "clean":
            pool.node_cleaned = True
        elif condition == "data_complete":
            pool.data_complete = True
        else:
            del state.world.node_pools["E"]
        result = _plan(state, False)
        assert result.physical_chain_valid and result.geometry_valid
        assert result.information_status == InformationStatus.UNAVAILABLE, condition
        assert result.viability == Viability.INCOMPLETE


def test_consumed_uplink_not_reused_but_other_sources_independent():
    state = _state(70)
    _add(state, "E", 35, "waystation")
    state.world.node_pools["E"].uplink_data_consumed = True
    result = _plan(state, False)
    assert result.information_status == InformationStatus.UNAVAILABLE
    state.world.space.nodes["E"].kind = "station"
    result = _plan(state, False)
    assert result.hops[-1].hint.mechanism == Mechanism.SALVAGE_DATA
    assert result.hops[-1].hint.requires_preparation


def test_visited_scale_can_use_known_route_without_new_information():
    state = _state(70)
    _add(state, "E", 35, "waystation")
    state.world.visited_nodes.add("E")
    state.world.node_pools["E"].window_open = False
    state.world.node_pools["E"].uplink_data_consumed = True
    assert add_known_link(state.world, "E", "D")
    result = _plan(state, False)
    assert result.information_status == InformationStatus.FUTURE_REQUIRED
    assert result.hops[-1].hint.mechanism == Mechanism.KNOWN_ROUTE
    assert result.stages[1].role == Role.NAVIGATION
    assert not result.stages[1].next_hint.requires_preparation


def test_existing_intel_and_normal_solve_are_distinct_from_recovery_signal():
    state = _state(70)
    _add(state, "E", 35, "waystation")
    state.world.visited_nodes.add("E")
    state.world.node_pools["E"].uplink_data_consumed = True
    item = record_intel(state.world, t=state.clock.t, kind="link", from_id="E", to_id="D",
                        confidence=0.9, source_kind="log")
    result = _plan(state, False)
    assert result.hops[-1].hint.mechanism == Mechanism.EXISTING_INTEL
    assert result.hops[-1].hint.source_ref == item.intel_id
    state.world.intel = []
    state.ship.sensors_range_ly = 40.0
    result = _plan(state, False)
    assert result.hops[-1].hint.mechanism == Mechanism.ROUTE_SOLVE
    assert result.stages[1].role == Role.NAVIGATION


def test_file_intel_must_be_readable_and_uncorrupted():
    state = _state(45)
    state.os.fs["/logs/nav/source.txt"] = FSNode("/logs/nav/source.txt", FSNodeType.FILE,
                                                "LINK: A -> D\n", AccessLevel.SEC)
    state.os.auth_levels = {"GUEST"}
    assert _plan(state).hops[0].hint.mechanism == Mechanism.RECOVERY_SIGNAL
    state.os.auth_levels.add("SEC")
    result = _plan(state)
    assert result.hops[0].hint.mechanism == Mechanism.EXISTING_INTEL
    assert result.information_status == InformationStatus.VERIFIED
    assert result.ready_with_existing_mechanics  # No future reception, still unconfirmed.
    assert not state.world.known_links, "Verified proposal must not publish its clue"
    state.os.fs["/logs/nav/source.txt"].is_corrupted = True
    assert _plan(state).hops[0].hint.mechanism == Mechanism.RECOVERY_SIGNAL


def test_protected_target_intermediary_and_unlocked_host():
    state = _state()
    _add(state, "E1", 35)
    _add(state, "E2", 70)
    for kind in ("node", "link"):
        for protected in ("D", "E1"):
            line = f"NODE: {protected}" if kind == "node" else f"LINK: A -> {protected}"
            arc = {"arc_id": "PROBE", "primary_intel": {"kind": kind, "line": line}}
            with patch.object(lore, "load_arcs", return_value=[arc]):
                result = _plan(state, False)
                assert protected not in result.reused_nodes
                if protected == "D":
                    assert result.reasons == ("protected_primary_target",)
    state.world.forced_hidden_nodes.add("E1")
    state.world.lore_placements.piece_to_node["mandatory_receiver"] = "E1"
    result = _plan(state, False)
    assert "E1" in result.reused_nodes, "A narrative host is not automatically a protected primary"


def test_unresolved_primary_protection_fails_closed():
    arc = {"arc_id": "COORD_PRIMARY", "primary_intel": {"kind": "coord", "coord": [100, 25, 1]}}
    state = _state()
    with patch.object(lore, "load_arcs", return_value=[arc]):
        result = _plan(state)
        assert result.reasons == ("primary_protection_query_incomplete",)
        state.world.arc_placements["COORD_PRIMARY"] = {"primary": {"unlocked": True}}
        assert _plan(state).physical_chain_valid


def test_generated_and_lazy_sectors_are_explicit_dependencies():
    state = _state()
    result = _plan(state)
    assert all("lazy_sector_slot_reservation" in {d.code for d in n.dependencies} for n in result.new_nodes)
    for node in result.new_nodes:
        state.world.generated_sectors.add(node.sector_id)
        state.world.sector_states[node.sector_id] = SectorGenState(
            sector_id=node.sector_id, region=node.region, archetype=node.archetype,
            internal_links_built=True)
    result = _plan(state)
    assert result.physical_chain_valid
    assert all("late_sector_topology" in {d.code for d in n.dependencies} for n in result.new_nodes)
    assert result.materialization == Materialization.CONDITIONAL


def test_no_policy_or_procedural_slot_is_not_fabricated():
    # The straight slots at y=1 are empty; 4D-3c may now find a real detour.
    result = _plan(_state(y=1))
    assert result.geometry_valid and result.physical_chain_valid
    assert result.materialization == Materialization.CONDITIONAL
    assert any(n.position_ly[1:] != (1, 1.0) for n in result.new_nodes)
    state = _state()
    with patch("retorno.core.deadnode_planner.load_worldgen_templates", return_value={}):
        result = _plan(state)
        assert not result.physical_chain_valid
        assert all(n.kind is None for n in result.new_nodes)


def test_identity_collision_is_avoided_without_allocating_ids():
    state = _state()
    result = _plan(state)
    node = result.new_nodes[0]
    # An unrelated physical id collision must not create or overwrite anything.
    state.world.space.nodes[node.node_id] = _node(node.node_id, -500)
    result2 = _plan(state)
    assert result2.opportunity_id == result.opportunity_id
    assert result2.new_nodes[0].node_id != node.node_id
    assert all(n.node_id not in state.world.space.nodes for n in result2.new_nodes)
    assert len({n.node_id for n in result2.new_nodes}) == len(result2.new_nodes)


def test_complete_no_mutation_and_no_production_helpers():
    state = _state()
    state.world.dead_nodes["D"].attempts = 1
    state.world.dead_nodes["D"].last_action_t = 123
    state.world.intel = []
    def forbidden(*args, **kwargs):
        raise AssertionError("Planner called a mutating production helper")
    original_open = Path.open
    def read_only_open(path, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), mode
        return original_open(path, mode, *args, **kwargs)
    with patch.object(lore, "register_hidden_anchored_node", forbidden), \
         patch.object(lore, "write_local_intel", forbidden), \
         patch("retorno.worldgen.generator.ensure_sector_generated", forbidden), \
         patch("retorno.core.deadnodes.evaluate_dead_nodes", forbidden), \
         patch.object(Path, "open", read_only_open):
        result = _plan(state)
    try:
        result.target_id = "OTHER"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Proposal is mutable")
    assert state.world.dead_nodes["D"].attempts == 1
    assert state.world.dead_nodes["D"].last_action_t == 123


def test_order_determinism_and_save_load_without_proposal_persistence():
    state = _state()
    _add(state, "E1", 35)
    _add(state, "E2", 70)
    result = _plan(state)
    reordered = copy.deepcopy(state)
    reordered.world.space.nodes = dict(reversed(list(reordered.world.space.nodes.items())))
    reordered.world.node_pools = dict(reversed(list(reordered.world.node_pools.items())))
    assert _plan(reordered) == result
    with TemporaryDirectory(prefix="retorno-chain-planner-") as directory:
        path = Path(directory) / "state.dat"
        for _ in range(3):
            save_single_slot(state, path)
            state = load_single_slot(path).state
            assert _plan(state) == result
    assert not hasattr(state.world.dead_nodes["D"], "plan")


def test_stopped_waypoint_is_an_origin():
    state = _state()
    _add(state, "B", 8)
    state.world.known_nodes.add("B")
    state.world.known_contacts.add("B")
    add_known_link(state.world, "A", "B", bidirectional=True)
    state.ship.cruise_speed_ly_per_year = 10_000_000.0
    engine = Engine()
    started = engine.apply_action(state, Travel(node_id="B", no_cruise=True))
    assert any(e.type == EventType.TRAVEL_STARTED for e in started)
    assert _plan(state).reasons == ("ship_in_transit",)
    engine.tick(state, (state.ship.arrival_t - state.clock.t) / 2)
    engine.apply_action(state, TravelAbort())
    state.world.space.nodes["D"].x_ly = state.world.current_pos_ly[0]
    state.world.space.nodes["D"].y_ly = state.world.current_pos_ly[1] + 40
    result = _plan(state)
    assert result.physical_chain_valid
    assert result.origin_id == state.world.active_tmp_node_id
    assert not state.ship.in_transit


def test_no_arbitrary_stage_limit():
    state = _state(420)
    for index in range(1, 12):
        _add(state, f"E{index:02d}", index * 35)
    result = _plan(state, False)
    assert len(result.hops) == 12
    assert result.physical_chain_valid and not result.new_nodes
    _assert_hops(result)


def test_unknown_record_does_not_make_an_origin_operational():
    state = _state(80)
    _add(state, "HIDDEN", 20)
    _add(state, "B", 40)
    state.world.known_nodes.add("B")
    state.world.known_links = {"A": {"HIDDEN"}, "HIDDEN": {"B"}}
    assert _plan(state).origin_id == "A"
    state.world.known_contacts.add("HIDDEN")
    assert _plan(state).origin_id == "A", "Travel does not accept contacts-only knowledge"


def test_candidate_gates_and_missing_drone_dependency():
    state = _state()
    state.world.known_contacts.discard("D")
    assert _plan(state).reasons == ("not_a_deadnode_contact",)
    state.world.forced_hidden_nodes.add("D")
    state.world.known_nodes.discard("D")
    assert _plan(state).physical_chain_valid
    state.world.node_pools["D"].node_cleaned = True
    assert _plan(state).reasons == ("deadnode_clean_pool_gate",)
    state = _state()
    state.world.node_pools["A"].node_cleaned = True
    assert _plan(state).reasons == ("deadnode_clean_pool_gate",)
    state = _state(70)
    _add(state, "E", 35)
    state.ship.drones = {}
    result = _plan(state, False)
    assert any(d.code == "drone_available_for_deployment" and d.available_now is False
               for d in result.hops[-1].hint.dependencies)
    assert not result.ready_with_existing_mechanics


def test_full_sector_cannot_supply_extra_slots_or_forbidden_types():
    state = _state()
    first = _plan(state).new_nodes[0]
    cfg = load_worldgen_archetypes()[first.archetype]
    for index in range(cfg["node_count_max"]):
        _add(state, f"FULL_{index}", 30.1 + index * 0.1)
    # Mark actual sector as closed: neither planning nor future id selection
    # may mint a capacity increase. Existing physical nodes can still be reused.
    state.world.sector_states[first.sector_id] = SectorGenState(
        sector_id=first.sector_id, archetype=first.archetype, internal_links_built=True)
    result = _plan(state)
    assert not any(n.sector_id == first.sector_id for n in result.new_nodes)
    assert all(n.kind not in cfg["forbidden_kinds"] for n in result.new_nodes
               if n.sector_id == first.sector_id)


def test_determinism_across_hash_seeds():
    script = (
        "import json; from dataclasses import asdict; "
        "from tests.deadnode_chain_planner_smoke import _state, _plan; "
        "print(json.dumps(asdict(_plan(_state())),sort_keys=True))"
    )
    outputs = []
    for hash_seed in ("1", "97"):
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                env=dict(os.environ, PYTHONHASHSEED=hash_seed),
                                capture_output=True, text=True, check=True,
                                cwd=Path(__file__).resolve().parents[1], timeout=30)
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]


if __name__ == "__main__":
    for name, check in list(globals().items()):
        if name.startswith("test_"):
            check()
            print(f"PASS {name}")
    print("DEADNODE CHAIN PLANNER SMOKE PASSED")
