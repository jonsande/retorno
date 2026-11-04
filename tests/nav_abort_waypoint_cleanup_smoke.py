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
from retorno.core.actions import Dock, RouteSolve, Scan, Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus
from retorno.model.systems import SystemState
from retorno.model.world import (
    DeadNodeState, ExplorationRecoveryState, NodePoolState, SectorGenState, SpaceNode, add_known_link,
    is_hop_within_cap, reachable_from, record_intel,
)
from retorno.ui_textual.app import RetornoTextualApp
from retorno.ui_textual import presenter


def _state():
    state = create_initial_state_sandbox()
    state.meta.rng_seed = state.world.rng_seed = 314159
    state.meta.rng_counter = 0
    world = state.world
    positions = {
        "A": (0.0, 0.0, 0.0), "B": (8.0, 4.0, 2.0),
        "C": (2.0, 1.1, 0.5), "D": (2.0, 5.0, 0.5),
        "FAR": (60.0, 0.0, 0.0), "OUTSIDE_T": (-2.5, 0.0, 0.0),
    }
    world.space.nodes = {
        nid: SpaceNode(nid, nid, "derelict", x_ly=x, y_ly=y, z_ly=z,
                       region="disk", salvage_scrap_available=5)
        for nid, (x, y, z) in positions.items()
    }
    world.space.edges = {}
    world.current_node_id = state.ship.current_node_id = "A"
    world.current_pos_ly = positions["A"]
    state.ship.docked_node_id = None
    state.ship.sensors_range_ly = 3.0
    # Short real journeys avoid testing decades of degradation in this fixture.
    state.ship.cruise_speed_ly_per_year = 10_000_000.0
    world.known_nodes = {"A", "B"}
    world.known_contacts = set(world.known_nodes)
    world.known_links = {}
    world.known_intel = {}
    world.intel = []
    world.forced_hidden_nodes = set()
    world.visited_nodes = {"A"}
    world.fine_ranges_km = {}
    # Pending salvage data supplies a real exploration frontier on arrival.
    world.node_pools = {
        nid: NodePoolState(base_files=[{"path": "/logs/survey.txt", "content": "survey"}])
        for nid in positions
    }
    world.dead_nodes = {}
    world.sector_states = {}
    world.exploration_recovery = ExplorationRecoveryState()
    # Controlled, already generated sectors: no worldgen or probability patches.
    world.generated_sectors = {
        f"S{x:+04d}_{y:+04d}_{z:+04d}"
        for x in range(-1, 2) for y in range(-1, 2) for z in range(-1, 2)
    }
    state.ship.installed_modules = []
    state.ship.power.p_gen_base_kw = 20.0
    _sensors_on(state)
    assert add_known_link(world, "A", "B", bidirectional=True)
    return state


def _sensors_on(state):
    sensors = state.ship.systems["sensors"]
    sensors.state = SystemState.NOMINAL
    sensors.forced_offline = False
    assert sensors.service
    sensors.service.is_running = True
    state.ship.power.power_quality = 0.95


def _has(events, event_type):
    assert any(e.type == event_type for e in events), events


def _travel(engine, state, target):
    before = state.clock.t
    origin = state.world.current_node_id
    events = engine.apply_action(state, Travel(node_id=target, no_cruise=True))
    _has(events, EventType.TRAVEL_STARTED)
    assert state.clock.t == before
    assert state.ship.in_transit and state.ship.transit_from == origin
    assert state.ship.arrival_t > before
    return events


def _abort(engine, state, fraction=0.25):
    a = state.world.space.nodes[state.ship.transit_from]
    b = state.world.space.nodes[state.ship.transit_to]
    start = (a.x_ly, a.y_ly, a.z_ly)
    end = (b.x_ly, b.y_ly, b.z_ly)
    expected_radiation = a.radiation_rad_per_s + (b.radiation_rad_per_s - a.radiation_rad_per_s) * fraction
    expected = tuple(x + (y - x) * fraction for x, y in zip(start, end))
    events = engine.tick(state, (state.ship.arrival_t - state.clock.t) * fraction)
    assert not any(e.type == EventType.ARRIVED for e in events)
    before = state.clock.t
    events = engine.apply_action(state, TravelAbort())
    _has(events, EventType.TRAVEL_ABORTED)
    assert not any(e.type == EventType.ARRIVED for e in events)
    assert state.clock.t == before and not state.ship.in_transit
    tmp = state.world.active_tmp_node_id
    assert tmp == state.ship.current_node_id == state.world.current_node_id
    node = state.world.space.nodes[tmp]
    actual = (node.x_ly, node.y_ly, node.z_ly)
    assert all(abs(x - y) < 1e-10 for x, y in zip(actual, expected))
    assert actual == state.world.current_pos_ly
    assert actual != start and actual != end
    assert abs(node.radiation_rad_per_s - max(Balance.PROCEDURAL_RAD_MIN, expected_radiation)) < 1e-10
    return tmp


def _stopped():
    engine, state = Engine(), _state()
    _travel(engine, state, "B")
    tmp = _abort(engine, state)
    return engine, state, tmp


def _solve(engine, state, target="C"):
    origin = state.world.current_node_id
    _has(engine.apply_action(state, RouteSolve(node_id=target)), EventType.JOB_QUEUED)
    job = state.jobs.jobs[state.jobs.active_job_ids[-1]]
    engine.tick(state, job.eta_s + 0.01)
    assert job.status == JobStatus.COMPLETED
    assert is_hop_within_cap(state.world, origin, target)
    assert target in reachable_from(state.world, origin)
    assert origin in reachable_from(state.world, target)


def _arrive(engine, state, target):
    _has(engine.tick(state, state.ship.arrival_t - state.clock.t + 0.01), EventType.ARRIVED)
    assert not state.ship.in_transit
    assert state.world.current_node_id == state.ship.current_node_id == target
    node = state.world.space.nodes[target]
    assert state.world.current_pos_ly == (node.x_ly, node.y_ly, node.z_ly)
    assert target in state.world.visited_nodes


def _clean(state, tmp):
    world = state.world
    assert tmp not in world.space.nodes
    assert tmp not in world.known_links
    assert all(tmp not in links for links in world.known_links.values()), "Reverse known route survived"
    assert all(tmp not in node.links for node in world.space.nodes.values())
    assert tmp not in world.space.edges
    assert all(tmp not in links for links in world.space.edges.values())
    assert all(tmp not in pool.uplink_route_pool for pool in world.node_pools.values())
    assert all(tmp not in sector.node_ids and tmp != sector.topology_hub_node_id
               and tmp != sector.playable_hub_node_id for sector in world.sector_states.values())
    for values in (world.known_nodes, world.known_contacts, world.known_intel,
                   world.visited_nodes, world.fine_ranges_km, world.node_pools,
                   world.dead_nodes, world.forced_hidden_nodes, world.salvage_tip_nodes):
        assert tmp not in values
    assert world.active_tmp_node_id is None
    assert world.active_tmp_from is None and world.active_tmp_to is None
    assert world.active_tmp_progress is None
    assert state.ship.transit_from != tmp and state.ship.transit_to != tmp


def _roundtrip(state):
    with TemporaryDirectory(prefix="retorno-waypoint-") as directory:
        path = Path(directory) / "save.dat"
        snapshot = asdict(state.world), asdict(state.ship), asdict(state.jobs), state.clock.t
        for _ in range(3):
            save_single_slot(state, path)
            loaded = load_single_slot(path)
            assert loaded and loaded.source == "primary"
            state = loaded.state
            assert (asdict(state.world), asdict(state.ship), asdict(state.jobs), state.clock.t) == snapshot
        return state


def test_abort_position_and_inactive_abort():
    engine, state, tmp = _stopped()
    assert state.world.current_pos_ly == (2.0, 1.0, 0.5)
    snapshot = asdict(state.world)
    _has(engine.apply_action(state, TravelAbort()), EventType.BOOT_BLOCKED)
    assert asdict(state.world) == snapshot and tmp in state.world.space.nodes


def test_scan_from_stopped_waypoint():
    engine, state, tmp = _stopped()
    assert "scan_in_transit" not in state.ship.installed_modules
    _has(engine.apply_action(state, Scan()), EventType.JOB_QUEUED)
    job = state.jobs.jobs[state.jobs.active_job_ids[-1]]
    assert job.params["origin_node_id"] == tmp and job.target.id == tmp
    events = engine.tick(state, job.eta_s + 0.01)
    assert job.status == JobStatus.COMPLETED
    assert "C" in state.world.known_nodes, "Seeded nearby third contact was not detected"
    assert "OUTSIDE_T" not in state.world.known_nodes, "Scan used A instead of T"
    assert any(e.type == EventType.SIGNAL_DETECTED and e.data.get("contact_id") == "C" for e in events)
    assert any(i.to_id == "C" and i.source_ref == tmp for i in state.world.intel)
    assert "C" not in reachable_from(state.world, tmp), "Scan granted a free route"
    _solve(engine, state)
    _travel(engine, state, "C")
    _arrive(engine, state, "C")
    _clean(state, tmp)


def test_scan_gates_and_real_transit():
    engine, state, tmp = _stopped()
    for gate, reason in (("sensors", "scan_sensors_offline"),
                         ("service", "scan_sensord_not_running"), ("power", "power_quality_low")):
        _sensors_on(state)
        if gate == "sensors":
            state.ship.systems["sensors"].state = SystemState.OFFLINE
        elif gate == "service":
            state.ship.systems["sensors"].service.is_running = False
        else:
            state.ship.power.power_quality = 0.4
        events = engine.apply_action(state, Scan())
        assert any(e.data.get("reason") == reason for e in events), events
    _sensors_on(state)
    _travel(engine, state, "B")
    for modules in ([], ["transit_sensor_pack"]):
        state.ship.installed_modules = modules
        # Current public action gate blocks active-transit scans even with unlock.
        events = engine.apply_action(state, Scan())
        assert any(e.data.get("reason") == "in_transit" for e in events), events
    # A queued scan must also retain the unlock check during a real journey.
    state.ship.installed_modules = []
    assert engine._scan_block_details(state)[2]["reason"] == "scan_locked_in_transit"
    state.ship.installed_modules = ["transit_sensor_pack"]
    assert engine._scan_block_details(state) is None
    assert tmp in state.world.space.nodes


def test_third_destination_completion_and_arrival():
    engine, state, tmp = _stopped()
    _solve(engine, state)
    assert "C" in repl._travel_targets_for_completion(state), "CLI hides operational third destination"
    # Completion is read-only and needs no running Textual application or save slot.
    app = RetornoTextualApp.__new__(RetornoTextualApp)
    app._audio_manager = None
    assert "C" in app._get_completion_candidates(state, "nav ", ""), "Textual hides C"
    out = io.StringIO()
    with redirect_stdout(out):
        repl.render_nav_routes(state)
    assert "C" in out.getvalue()
    _travel(engine, state, "C")
    assert tmp in state.world.space.nodes, "Journey still needs its physical origin"
    _arrive(engine, state, "C")
    _clean(state, tmp)
    assert state.world.known_links["A"] == {"B"}
    assert state.world.known_links["B"] == {"A"}


def test_travel_to_third_destination():
    engine, state, _ = _stopped()
    _solve(engine, state)
    _travel(engine, state, "C")


def test_return_and_resume_cleanup():
    for target in ("A", "B"):
        engine, state, tmp = _stopped()
        # Scan legitimately makes the temporary node itself known too.
        state.world.known_nodes.add(tmp)
        state.world.known_contacts.add(tmp)
        state.world.known_intel[tmp] = {"confidence": 0.6}
        state.world.fine_ranges_km[tmp] = 100.0
        state.world.node_pools[tmp] = NodePoolState()
        state.world.dead_nodes[tmp] = DeadNodeState()
        state.world.forced_hidden_nodes.add(tmp)
        state.world.visited_nodes.add(tmp)
        state.world.salvage_tip_nodes.add(tmp)
        state.world.node_pools["A"].uplink_route_pool = [tmp, "C"]
        state.world.sector_states["S+000_+000_+000"] = SectorGenState(
            node_ids=["A", tmp], topology_hub_node_id=tmp,
            playable_hub_node_id="B", internal_link_count=1,
        )
        state.world.space.nodes["A"].links.update({"B", tmp})
        state.world.space.edges["A"] = ["B", tmp]
        state.world.space.edges[tmp] = ["A"]
        historical = record_intel(state.world, t=state.clock.t, kind="node", to_id="C",
                                  source_kind="scan", source_ref=tmp, confidence=0.6)
        _travel(engine, state, target)
        _arrive(engine, state, target)
        _clean(state, tmp)
        assert state.world.space.nodes["A"].links == {"B"}
        assert state.world.space.edges["A"] == ["B"]
        assert state.world.node_pools["A"].uplink_route_pool == ["C"]
        sector = state.world.sector_states["S+000_+000_+000"]
        assert sector.node_ids == ["A"] and sector.playable_hub_node_id == "B"
        assert sector.internal_link_count == 1
        assert historical in state.world.intel and historical.source_ref == tmp
        snapshot = copy.deepcopy(asdict(state.world))
        engine._clear_tmp_node(state)
        assert asdict(state.world) == snapshot
        _clean(_roundtrip(state), tmp)


def test_save_load_at_all_phases():
    engine, state = Engine(), _state()
    _travel(engine, state, "B")
    state = _roundtrip(state)
    tmp = _abort(engine, state)
    state = _roundtrip(state)
    _solve(engine, state)
    state = _roundtrip(state)
    assert "C" in reachable_from(state.world, tmp)
    _travel(engine, state, "C")
    state = _roundtrip(state)
    _arrive(engine, state, "C")
    _clean(_roundtrip(state), tmp)


def test_repeated_aborts():
    engine, state, t1 = _stopped()
    _solve(engine, state)
    state.world.space.nodes[t1].radiation_rad_per_s = 0.001
    state.world.space.nodes["C"].radiation_rad_per_s = 0.009
    _travel(engine, state, "C")
    t2 = _abort(engine, state, 0.5)
    assert t2 != t1
    assert all(abs(x - y) < 1e-10 for x, y in zip(state.world.current_pos_ly, (2.0, 1.05, 0.5)))
    assert t1 not in state.world.space.nodes
    assert all(t1 not in links for links in state.world.known_links.values())
    assert state.world.active_tmp_from is None, "Deleted T1 remains an operational origin"
    assert state.world.active_tmp_to == "C"
    assert reachable_from(state.world, t2) == {"C"}
    state = _roundtrip(state)
    _has(engine.apply_action(state, Scan()), EventType.JOB_QUEUED)
    engine.tick(state, Balance.SCAN_TIME_S + 0.01)
    _solve(engine, state, "A")
    _travel(engine, state, "A")
    _arrive(engine, state, "A")
    _clean(state, t2)


def test_repeated_abort_drops_deleted_origin_metadata():
    engine, state, t1 = _stopped()
    _travel(engine, state, "B")
    t2 = _abort(engine, state, 0.5)
    assert t2 != t1 and t1 not in state.world.space.nodes
    assert state.world.active_tmp_from is None, "Deleted T1 remains in active_tmp_from"


def test_pending_waypoint_jobs_become_history():
    engine, state, t1 = _stopped()
    _solve(engine, state)
    # C is very close: we can leave while a different route is still computing.
    state.world.known_links[t1].discard("A")
    _has(engine.apply_action(state, RouteSolve(node_id="A")), EventType.JOB_QUEUED)
    job = state.jobs.jobs[state.jobs.active_job_ids[-1]]
    _travel(engine, state, "C")
    t2 = _abort(engine, state, 0.5)
    assert t1 not in state.world.space.nodes and t2 in state.world.space.nodes
    assert job.internal_id not in state.jobs.active_job_ids, "Job still operates from deleted waypoint"
    assert job.status in {JobStatus.CANCELLED, JobStatus.FAILED}
    state = _roundtrip(state)
    engine.tick(state, Balance.ROUTE_SOLVE_MAX_S + 1.0)
    assert all(t1 not in routes for routes in state.world.known_links.values())


def _pending_waypoint_solve():
    engine, state, tmp = _stopped()
    _solve(engine, state)
    state.world.known_links[tmp].discard("A")
    _has(engine.apply_action(state, RouteSolve(node_id="A")), EventType.JOB_QUEUED)
    job = state.jobs.jobs[state.jobs.active_job_ids[-1]]
    assert job.params["from_id"] == tmp
    assert job.status == JobStatus.QUEUED
    return engine, state, tmp, job


def _assert_single_cleanup_cancellation(engine, state, events, job, terminal_seq, terminal_count):
    cancellations = [event for event in events if event.data.get("message_key") == "job_cancelled"
                     and event.data.get("job_key") == job.internal_id]
    assert len(cancellations) == 1, cancellations
    event = cancellations[0]
    assert job.status == JobStatus.CANCELLED
    assert job.internal_id not in state.jobs.active_job_ids
    assert state.jobs.jobs[job.internal_id] is job
    assert job.terminal_seq == terminal_seq
    assert state.jobs.next_terminal_job_seq == terminal_seq + terminal_count
    assert event.type == EventType.JOB_FAILED
    assert event.data["job_id"] == job.job_id == f"XJ{terminal_seq}"
    matches = [item for item in state.events.recent if item.event_id == event.event_id]
    assert len(matches) == 1, f"{event.event_id}: {len(matches)} history entries for one cancellation"
    assert matches[0] is event
    assert sum(item.data.get("message_key") == "job_cancelled"
               and item.data.get("job_key") == job.internal_id for item in state.events.recent) == 1

    from retorno.model.os import Locale

    for locale, message in ((Locale.EN, "Job cancelled:"), (Locale.ES, "Trabajo cancelado:")):
        state.os.locale = locale
        output = io.StringIO()
        with redirect_stdout(output):
            repl.render_events(state, events)
        cli_text = output.getvalue()
        textual_text = "\n".join(presenter.format_event_lines(state, events))
        for text in (cli_text, textual_text):
            assert text.count(f"{message} {job.job_id}") == 1, text

    # No repeated finalization/event on a later tick or three save/load cycles.
    terminal_job = asdict(job)
    expected_next_seq = state.jobs.next_terminal_job_seq
    engine.tick(state, 0.01)
    with TemporaryDirectory(prefix="retorno-cleanup-events-") as directory:
        path = Path(directory) / "save.dat"
        for _ in range(3):
            recent = [asdict(item) for item in state.events.recent]
            save_single_slot(state, path)
            loaded = load_single_slot(path)
            assert loaded and loaded.source == "primary"
            state = loaded.state
            assert [asdict(item) for item in state.events.recent] == recent
            assert asdict(state.jobs.jobs[job.internal_id]) == terminal_job
            assert state.jobs.next_terminal_job_seq == expected_next_seq
            assert job.internal_id not in state.jobs.active_job_ids
            assert sum(item.event_id == event.event_id for item in state.events.recent) == 1
            returned = engine.tick(state, 0.01)
            assert not any(item.data.get("message_key") == "job_cancelled"
                           and item.data.get("job_key") == job.internal_id for item in returned)


def test_cleanup_cancellation_event_once_on_arrival():
    engine, state, tmp, job = _pending_waypoint_solve()
    _travel(engine, state, "C")
    dt = state.ship.arrival_t - state.clock.t + 0.01
    assert job.eta_s > dt and job.internal_id in state.jobs.active_job_ids
    terminal_seq = state.jobs.next_terminal_job_seq
    events = engine.tick(state, dt)
    _has(events, EventType.ARRIVED)
    assert state.world.current_node_id == "C" and not state.ship.in_transit
    _clean(state, tmp)
    _assert_single_cleanup_cancellation(engine, state, events, job, terminal_seq, 1)


def test_cleanup_cancellation_event_once_on_repeated_abort():
    engine, state, tmp, job = _pending_waypoint_solve()
    _travel(engine, state, "C")
    engine.tick(state, (state.ship.arrival_t - state.clock.t) * 0.5)
    assert job.internal_id in state.jobs.active_job_ids and job.eta_s > 0
    terminal_seq = state.jobs.next_terminal_job_seq
    events = engine.apply_action(state, TravelAbort())
    _has(events, EventType.TRAVEL_ABORTED)
    assert tmp not in state.world.space.nodes
    assert state.world.active_tmp_node_id == state.world.current_node_id != tmp
    assert not state.ship.in_transit
    assert all(abs(x - y) < 1e-10 for x, y in zip(state.world.current_pos_ly, (2.0, 1.05, 0.5)))
    _assert_single_cleanup_cancellation(engine, state, events, job, terminal_seq, 1)


def test_cleanup_cancellation_event_once_on_docking_completion():
    engine, state, tmp, job = _pending_waypoint_solve()
    # Exercise the defensive docking cleanup branch with a controlled retained
    # departure waypoint. Ordinary travel already cleans it before docking.
    state.world.current_node_id = state.ship.current_node_id = "C"
    node = state.world.space.nodes["C"]
    state.world.current_pos_ly = (node.x_ly, node.y_ly, node.z_ly)
    _has(engine.apply_action(state, Dock(node_id="C")), EventType.JOB_QUEUED)
    dock_job = state.jobs.jobs[state.jobs.active_job_ids[-1]]
    assert job.eta_s > dock_job.eta_s + 0.01
    terminal_seq = state.jobs.next_terminal_job_seq
    events = engine.tick(state, dock_job.eta_s + 0.01)
    _has(events, EventType.DOCKED)
    assert dock_job.status == JobStatus.COMPLETED
    assert state.ship.docked_node_id == state.world.current_node_id == "C"
    _clean(state, tmp)
    _assert_single_cleanup_cancellation(engine, state, events, job, terminal_seq, 2)


def test_bilingual_status_and_help():
    _, state, _ = _stopped()
    from retorno.model.os import Locale

    for locale, phrase, help_phrase in ((Locale.EN, "waypoint: stopped", "stop at current position"),
                                         (Locale.ES, "waypoint: detenido", "detente en la posición actual")):
        state.os.locale = locale
        out = io.StringIO()
        with redirect_stdout(out):
            repl.render_status(state)
            repl.print_help(locale.value, verbose=True)
        text = out.getvalue()
        assert phrase in text and help_phrase in text
        assert "transit: between" not in text and "transit: entre" not in text


def test_rejections_direction_and_ordinary_arrival():
    engine, state, tmp = _stopped()
    state.world.known_nodes.update({"D", "FAR"})
    state.world.known_contacts.update({"D", "FAR"})
    for target in ("D", "FAR", "MISSING"):
        before = asdict(state.world)
        _has(engine.apply_action(state, Travel(node_id=target)), EventType.BOOT_BLOCKED)
        assert asdict(state.world) == before
    for target, reason in (("D", "out_of_range"), ("FAR", "hop_cap_exceeded")):
        assert any(e.data.get("reason") == reason for e in engine.apply_action(state, RouteSolve(node_id=target)))
    assert not add_known_link(state.world, tmp, "FAR")
    assert add_known_link(state.world, "D", tmp)  # Direction must not be reversed.
    _has(engine.apply_action(state, Travel(node_id="D")), EventType.BOOT_BLOCKED)
    assert "C" not in state.world.known_nodes
    engine, state = Engine(), _state()
    before = copy.deepcopy(state.world.known_links)
    _travel(engine, state, "B")
    _arrive(engine, state, "B")
    assert state.world.known_links == before


if __name__ == "__main__":
    for name, check in list(globals().items()):
        if name.startswith("test_"):
            check()
            print(f"PASS {name}")
    print("NAV ABORT WAYPOINT CLEANUP SMOKE PASSED")
