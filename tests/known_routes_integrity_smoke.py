from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.actions import RouteSolve, Travel, TravelAbort
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.engine import Engine
from retorno.core.exploration_recovery import ensure_exploration_recovery, has_exploration_frontier
from retorno.io.save_load import SaveLoadError, load_single_slot, save_single_slot
from retorno.model.os import AccessLevel, FSNode, FSNodeType, Locale
from retorno.model.world import (
    ExplorationRecoveryState,
    NodePoolState,
    SpaceNode,
    add_known_link,
    is_hop_within_cap,
    reachable_from,
    record_intel,
)
from retorno.model.events import EventType
from retorno.ui_textual import presenter
from retorno.worldgen.generator import ensure_sector_generated, pin_universe


_SEED = 271828
_IMPORT_PATH = "/logs/nav/route-integrity.txt"


def _state():
    state = create_initial_state_sandbox()
    state.meta.rng_seed = _SEED
    # Fix this synthetic world's definition before persistence snapshots.
    pin_universe(state)
    world = state.world
    # Synthetic navigation pools carry legacy data, without historical claims.
    world.information_version = "legacy-information-v0"
    world.information_definition = None
    world.space.nodes = {
        nid: SpaceNode(node_id=nid, name=nid, kind="derelict", region="disk", x_ly=x)
        for nid, x in (("A", 0.0), ("B", 10.0), ("LIMIT", 45.0), ("FAR", 80.0), ("TAIL", 81.0))
    }
    world.space.edges = {}
    world.current_node_id = state.ship.current_node_id = "A"
    world.current_pos_ly = (0.0, 0.0, 0.0)
    state.ship.docked_node_id = None
    world.known_nodes = set(world.space.nodes)
    world.known_contacts = set(world.known_nodes)
    world.known_intel = {}
    world.intel = []
    world.next_intel_seq = 1
    world.known_links = {}
    world.visited_nodes = {"A", "B", "LIMIT"}
    world.forced_hidden_nodes = set()
    world.generated_sectors = set()
    world.sector_states = {}
    world.intersector_link_pairs = set()
    world.node_pools = {nid: NodePoolState(uplink_data_consumed=True) for nid in world.known_nodes}
    world.dead_nodes = {}
    world.exploration_recovery = ExplorationRecoveryState()
    return state


def _mixed_state():
    state = _state()
    # Inject invalid current-version state directly, bypassing publication.
    # FAR -> TAIL and MISSING -> TAIL must not contaminate A's component.
    state.world.known_links = {
        "A": {"B", "FAR", "MISSING"}, "B": {"A"},
        "FAR": {"TAIL"}, "MISSING": {"TAIL"},
    }
    state.world.known_contacts.add("MISSING")
    record_intel(
        state.world, t=0.0, kind="link", from_id="A", to_id="FAR",
        confidence=0.8, source_kind="log", source_ref=_IMPORT_PATH,
    )
    record_intel(
        state.world, t=0.0, kind="link", from_id="A", to_id="MISSING",
        confidence=0.8, source_kind="log", source_ref=_IMPORT_PATH,
    )
    return state


def _capture(func, *args):
    output = io.StringIO()
    with redirect_stdout(output):
        func(*args)
    return output.getvalue()


def _import(state, text, mode="import"):
    state.os.fs[_IMPORT_PATH] = FSNode(
        path=_IMPORT_PATH, node_type=FSNodeType.FILE, access=AccessLevel.GUEST, content=text,
    )
    if mode == "cat":
        return _capture(repl.render_cat, state, _IMPORT_PATH)
    if mode == "auto":
        return "\n".join(repl._auto_import_intel_from_text(state, text, _IMPORT_PATH))
    return _capture(repl._handle_intel_import, state, _IMPORT_PATH)


def _assert_hops_and_publication():
    world = _state().world
    assert float(Balance.MAX_ROUTE_HOP_LY) == 45.0
    assert is_hop_within_cap(world, "A", "B")
    assert is_hop_within_cap(world, "A", "LIMIT"), "Exactly 45 ly is valid"
    assert not is_hop_within_cap(world, "A", "FAR")
    assert not is_hop_within_cap(world, "A", "MISSING"), "Missing endpoint passed the hop criterion"
    assert not is_hop_within_cap(world, "MISSING", "B")
    assert add_known_link(world, "A", "B", bidirectional=True)
    assert add_known_link(world, "A", "LIMIT", bidirectional=True)
    assert not add_known_link(world, "A", "FAR")
    assert not add_known_link(world, "A", "MISSING")
    assert not add_known_link(world, "A", "A")
    assert reachable_from(world, "A") == {"B", "LIMIT"}
    assert reachable_from(world, "B") == {"A"}, "Bidirectional publication lost the reverse route"
    assert add_known_link(world, "B", "LIMIT")
    assert "LIMIT" in reachable_from(world, "B") and "B" not in reachable_from(world, "LIMIT")
    for locale in (Locale.EN, Locale.ES):
        state = _state()
        state.os.locale = locale
        state.world.space.nodes["A"].kind = "station"
        state.ship.docked_node_id = "A"
        pool = state.world.node_pools["A"]
        pool.uplink_route_pool = ["B", "FAR", "MISSING"]
        pool.uplink_data_consumed = False
        output = _capture(repl._handle_uplink, state)
        assert reachable_from(state.world, "A") == {"B"}
        marker = "descartadas 1" if locale == Locale.ES else "discarded 1"
        assert marker in output, "A missing endpoint must not be reported as an over-cap hop"


def _assert_import_history_and_locales():
    text = "LINK: A -> B\nLINK: LIMIT\nLINK: A -> FAR\nLINK: A -> MISSING\n"
    for locale in (Locale.EN, Locale.ES):
        for mode in ("import", "cat", "auto"):
            for blocked in (False, True):
                state = _state()
                state.os.locale = locale
                content = f"[INTEL]\n{text}[/INTEL]\n" if blocked else text
                output = _import(state, content, mode)
                assert state.world.known_links.get("A") == {"B", "LIMIT"}, (locale, mode, output)
                assert reachable_from(state.world, "B") == {"A"}
                assert {"A", "B", "LIMIT", "FAR", "MISSING"} <= state.world.known_contacts
                links = {(item.from_id, item.to_id) for item in state.world.intel if item.kind == "link"}
                assert links == {("A", dest) for dest in ("B", "LIMIT", "FAR", "MISSING")}, links
                marker = "extremo ausente" if locale == Locale.ES else "missing endpoint"
                assert marker in output, (locale, mode, output)
                before = asdict(state.world)
                _import(state, content, mode)
                assert asdict(state.world) == before, "Repeated import mutated deduplicated intel"
                export_path = "/logs/nav/route-integrity-export.txt"
                _capture(repl._handle_intel_export, state, export_path)
                exported = state.os.fs[export_path].content
                assert "LINK: A -> FAR" in exported and "LINK: A -> MISSING" in exported
                _import(state, exported, mode)
                assert asdict(state.world) == before, "Export/reimport promoted a historical clue"


def _assert_components_and_views():
    for locale in (Locale.EN, Locale.ES):
        state = _mixed_state()
        state.os.locale = locale
        before = asdict(state.world)
        adj = repl._map_known_adjacency(state, repl._map_known_nodes(state))
        assert repl._map_reachable_nodes(adj, "A") == {"A", "B"}, "Invalid edge contaminated reachable component"
        assert repl._map_bfs_path(adj, "A", "TAIL")[0] is None
        assert reachable_from(state.world, "A") == {"B"}
        routes = _capture(repl.render_nav_routes, state)
        operative = routes.split("Nearby contacts without known route:", 1)[0]
        assert "id=B" in operative and "FAR" not in operative and "MISSING" not in operative
        assert repl._travel_targets_for_completion(state) == ["B"]
        flags = {entry["cid"]: entry["route_flag"] for entry in repl._collect_known_contact_entries(state)}
        assert flags["FAR"] == "no_route" and flags["B"] == "route"
        for func, args in ((repl.render_nav_routes, ()), (repl.render_nav_map, ("routes", None)),
                           (repl.render_map_path, ("TAIL",))):
            cli = _capture(func, state, *args).strip().splitlines()
            textual = presenter.build_command_output(func, state, *args)
            assert [line.rstrip() for line in cli] == textual
        assert asdict(state.world) == before, "Navigation views must be read-only"


def _assert_recovery_frontier():
    state = _mixed_state()
    assert not has_exploration_frontier(state), "Invalid route created a phantom recovery frontier"
    events = ensure_exploration_recovery(state, "scan")
    assert events == [] and state.world.exploration_recovery.generation == 0
    assert state.world.recovery_searches["global"]["status"] == "conditional"
    assert state.world.exploration_recovery.entry_node_id is None
    valid = _state()
    valid.world.known_links = {"A": {"B"}}
    valid.world.visited_nodes.discard("B")
    assert has_exploration_frontier(valid), "Valid unvisited route lost its frontier"
    assert ensure_exploration_recovery(valid, "scan") == []


def _assert_deadnode_candidates():
    state = _mixed_state()
    before_links = copy.deepcopy(state.world.known_links)
    events = evaluate_dead_nodes(state, "scan")
    assert events == [], "Characterization must not reach dead thresholds/create bridges"
    assert {"FAR", "TAIL", "MISSING"} <= set(state.world.dead_nodes), "Invalid route excluded a deadnode candidate"
    assert all(item.attempts == 0 for item in state.world.dead_nodes.values())
    assert state.world.known_links == before_links


def _assert_lazy_sector():
    state = _state()
    state.world.space.nodes["A"].x_ly = 205.0
    state.world.current_pos_ly = (205.0, 0.0, 0.0)
    state.world.known_nodes = {"A"}
    state.world.known_contacts = {"A"}
    sector = "S+020_+000_+000"
    oracle = copy.deepcopy(state)
    ensure_sector_generated(oracle, sector)
    targets = set(oracle.world.space.nodes) - set(state.world.space.nodes)
    target = sorted(targets)[0]
    assert target not in state.world.space.nodes and sector not in state.world.generated_sectors
    _import(state, f"SECTOR: {sector}\nLINK: A -> {target}\n")
    assert sector in state.world.generated_sectors and target in state.world.space.nodes
    assert target in reachable_from(state.world, "A"), "Lazy sector was rejected before materialization"
    assert target in state.world.known_nodes
    assert (targets - {target}).isdisjoint(state.world.known_nodes), "SECTOR must not reveal the cluster"

    # Existing S...:... handling materializes the sector, but does not define
    # aliases for the KIND_HEX ids generated by worldgen. Keep unresolved intel.
    pending = _state()
    ref = "S+030_+000_+000:UNRESOLVED"
    _import(pending, f"LINK: A -> {ref}\n")
    assert "S+030_+000_+000" in pending.world.generated_sectors
    assert ref in pending.world.known_contacts and ref not in reachable_from(pending.world, "A")


def _assert_solve_and_travel():
    state = _state()
    state.world.space.nodes["HIDDEN"] = SpaceNode(node_id="HIDDEN", name="Hidden", kind="derelict", x_ly=1.0)
    engine = Engine()
    events = engine.apply_action(state, RouteSolve(node_id="HIDDEN"))
    assert any(event.type == EventType.JOB_QUEUED for event in events)
    eta = max(state.jobs.jobs[jid].eta_s for jid in state.jobs.active_job_ids)
    engine.tick(state, eta + 1.0)
    assert "HIDDEN" in reachable_from(state.world, "A") and "HIDDEN" in state.world.known_nodes
    assert "HIDDEN" not in state.world.space.nodes["A"].links
    for target in ("MISSING", "FAR"):
        invalid = _mixed_state()
        invalid.world.known_nodes.add(target)
        events = Engine().apply_action(invalid, Travel(node_id=target, no_cruise=True))
        assert not invalid.ship.in_transit and any(event.type == EventType.BOOT_BLOCKED for event in events)
    boundary = _state()
    add_known_link(boundary.world, "A", "LIMIT", bidirectional=True)
    Engine().apply_action(boundary, Travel(node_id="LIMIT", no_cruise=True))
    assert boundary.ship.in_transit, "Exactly-45-ly published route must remain travelable"
    missing_origin = _state()
    missing_origin.world.current_node_id = "MISSING"
    missing_origin.world.known_links = {"MISSING": {"B"}}
    events = Engine().apply_action(missing_origin, Travel(node_id="B", no_cruise=True))
    assert not missing_origin.ship.in_transit
    assert any(event.data.get("reason") == "node_missing" for event in events)


def _assert_job_endpoint_disappears():
    state = _state()
    state.world.space.nodes["B"].x_ly = 1.0
    engine = Engine()
    events = engine.apply_action(state, RouteSolve(node_id="B"))
    assert any(event.type == EventType.JOB_QUEUED for event in events)
    eta = max(state.jobs.jobs[jid].eta_s for jid in state.jobs.active_job_ids)
    state.world.space.nodes.pop("B")
    events = engine.tick(state, eta + 1.0)
    assert "B" not in state.world.known_links.get("A", set()), "Completed job published a missing endpoint"
    assert any(event.data.get("reason") == "node_missing" for event in events)
    assert not any(event.data.get("message_key") == "job_completed_route" for event in events)


def _assert_waypoint_is_inert_after_removal():
    state = _state()
    add_known_link(state.world, "A", "B", bidirectional=True)
    engine = Engine()
    engine.apply_action(state, Travel(node_id="B", no_cruise=True))
    assert state.ship.in_transit
    state.clock.t += (state.ship.arrival_t - state.clock.t) / 2.0
    engine.apply_action(state, TravelAbort())
    tmp_id = state.world.active_tmp_node_id
    assert tmp_id in state.world.space.nodes
    state.world.current_node_id = state.ship.current_node_id = "A"
    engine._clear_tmp_node(state)
    assert tmp_id not in reachable_from(state.world, "A"), "Removed F-NAV-01 waypoint remained operational"


def _assert_persistence():
    state = _mixed_state()
    pending = "S+030_+000_+000:PENDING"
    state.world.known_links["A"].add(pending)
    state.world.known_contacts.add(pending)
    before = asdict(state.world)
    contacts = set(state.world.known_contacts)
    with TemporaryDirectory() as tmp_dir:
        slot = Path(tmp_dir) / "current.dat"
        save_single_slot(state, slot)
        loaded = load_single_slot(slot)
        assert loaded is not None and loaded.source == "primary"
        assert reachable_from(loaded.state.world, "A") == {"B"}, "Loaded invalid edge remained operational"
        assert asdict(loaded.state.world) == before, "Load altered pending references/history"
        assert loaded.state.world.known_contacts == contacts
        for _ in range(2):
            save_single_slot(loaded.state, slot)
            loaded = load_single_slot(slot)
            assert loaded is not None and asdict(loaded.state.world) == before
            assert not has_exploration_frontier(loaded.state)
        incompatible = Path(tmp_dir) / "incompatible.dat"
        original = slot.read_bytes().replace(b"RETORNO_SAVE_V2", b"RETORNO_SAVE_V1", 1)
        incompatible.write_bytes(original)
        try:
            load_single_slot(incompatible)
        except SaveLoadError:
            pass
        else:
            raise AssertionError("Incompatible file was silently accepted")
        assert incompatible.read_bytes() == original, "Rejected incompatible file was changed/deleted"


def main():
    failures = []
    for check in (
        _assert_hops_and_publication, _assert_import_history_and_locales,
        _assert_components_and_views, _assert_recovery_frontier, _assert_deadnode_candidates,
        _assert_lazy_sector, _assert_solve_and_travel, _assert_job_endpoint_disappears,
        _assert_waypoint_is_inert_after_removal, _assert_persistence,
    ):
        try:
            check()
        except AssertionError as exc:
            failures.append(check.__name__)
            print(f"FAIL {check.__name__}: {exc}")
        else:
            print(f"PASS {check.__name__}")
    assert not failures, failures
    print(f"KNOWN ROUTES INTEGRITY SMOKE PASSED (seed={_SEED})")


if __name__ == "__main__":
    main()
