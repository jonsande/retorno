"""B0: real procedural hosts, physical interfaces and public knowledge boundaries."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.core import lore, structural_recovery
from retorno.core.deadnode_planner import information_capabilities as planner_capabilities
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.engine import Engine
from retorno.core.exploration_recovery import (
    _has_non_uplink_data_frontier, _has_uplink_frontier,
    ensure_exploration_recovery, has_exploration_frontier, uplink_blocked_reason,
)
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.os import Locale, mount_files
from retorno.model.systems import SystemState
from retorno.model.world import information_capabilities
from retorno.ui_textual import presenter
from retorno.worldgen.generator import ensure_sector_generated
from knowledge_boundary_smoke import public


def output(func, *args):
    with redirect_stdout(io.StringIO()) as stream:
        func(*args)
    return stream.getvalue().strip().splitlines()


def scene(kind="waystation"):
    """Instrumented starting fixture; hosts and archives come from real worldgen."""
    state = create_initial_state_prologue(seed=0)
    ensure_sector_generated(state, "S+000_+000_+000")
    target = next(nid for nid, n in state.world.space.nodes.items()
                  if n.kind == kind and ":WG1" in nid)
    state.ship.current_node_id = state.world.current_node_id = state.ship.docked_node_id = target
    state.world.known_nodes = {target}
    state.world.known_contacts = {target}
    state.world.visited_nodes = {target}
    state.world.known_links = {target: set()}
    for system in state.ship.systems.values():
        system.state = SystemState.NOMINAL
        system.health = 1.0
        system.forced_offline = False
        if system.service:
            system.service.is_installed = system.service.is_running = True
    state.ship.power.brownout = False
    state.ship.power.power_quality = 1.0
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="world_node", id=target)
    lore.initialize_node_pool(state, target)
    assert state.world.node_pools[target].base_files
    return state, target


def exhaust_other_opportunities(state, target):
    node = state.world.space.nodes[target]
    node.salvage_scrap_available = node.recoverable_drones_count = 0
    node.salvage_modules_available = []
    state.world.node_pools[target].uplink_data_consumed = True
    lore.recompute_node_completion(state, target)


def test_01_real_waystation_archives_are_preserved_without_false_frontier():
    state, target = scene()
    pool = state.world.node_pools[target]
    archives = deepcopy(pool.base_files)
    exhaust_other_opportunities(state, target)
    assert lore.collect_node_salvage_data_files(state, target) == []
    assert lore.survey_recoverable_data_count(state, target) == 0
    assert pool.data_complete and pool.node_cleaned
    before = pickle.dumps(state)
    assert not _has_non_uplink_data_frontier(state, {target})
    assert not has_exploration_frontier(state)
    assert pickle.dumps(state) == before, "Frontier queries must remain pure"
    assert pool.base_files == archives
    # The uninitialized fallback must apply exactly the same physical gate.
    del state.world.node_pools[target]
    before = pickle.dumps(state)
    assert not _has_non_uplink_data_frontier(state, {target})
    assert pickle.dumps(state) == before
    assert _has_uplink_frontier(state, {target}), "Uninspected legitimate uplink remains potential"


def test_02_public_commands_reject_salvage_but_uplink_works_once():
    state, target = scene()
    pool = state.world.node_pools[target]
    archives = deepcopy(pool.base_files)
    assert uplink_blocked_reason(state) is None
    assert _has_uplink_frontier(state, {target})
    rejected = Engine().apply_action(state, parse_command("drone salvage data D1"))
    assert any(e.data.get("reason") == "node_invalid" for e in rejected)
    assert not pool.uplink_data_consumed and not pool.data_complete
    assert not any(path.startswith(f"/remote/{target}/") for path in state.os.fs)
    count = state.world.lore.counters.get("uplink_count", 0)
    text = output(repl._handle_uplink, state)
    assert any("uplink_complete" in line for line in text), text
    assert pool.uplink_data_consumed and pool.data_complete
    assert state.world.lore.counters.get("uplink_count", 0) == count + 1
    assert state.world.known_links[target], "Actual frozen routes must still publish"
    assert not _has_uplink_frontier(state, {target})
    fs, routes = deepcopy(state.os.fs), deepcopy(state.world.known_links)
    repeat = output(repl._handle_uplink, state)
    assert any("exhaust" in line or "agotad" in line for line in repeat)
    assert state.world.lore.counters.get("uplink_count", 0) == count + 1
    assert state.os.fs == fs and state.world.known_links == routes
    assert pool.base_files == archives


def test_03_all_legitimate_salvage_hosts_still_mount_and_preserve_files():
    for kind in ("station", "relay", "ship", "derelict"):
        state, target = scene(kind)
        pool = state.world.node_pools[target]
        archives = deepcopy(pool.base_files)
        pool.injected_files.append(dict(path="/data/eligible.txt", access="guest", content="Retained assigned data"))
        injected = deepcopy(pool.injected_files)
        exhaust_other_opportunities(state, target)
        files = lore.collect_node_salvage_data_files(state, target)
        assert files and not pool.data_complete and not pool.node_cleaned, kind
        assert _has_non_uplink_data_frontier(state, {target})
        before = lore.survey_recoverable_data_count(state, target)
        engine = Engine()
        engine.apply_action(state, parse_command("drone salvage data D1"))
        assert lore.survey_recoverable_data_count(state, target) == before, "Queueing must not consume"
        events = engine.tick(state, 60.0)
        data = next(e.data for e in events if e.type == EventType.DATA_SALVAGED)
        assert data["files_new_count"] == before > 0, (kind, data)
        assert lore.survey_recoverable_data_count(state, target) == 0
        assert pool.data_complete and pool.node_cleaned
        assert pool.base_files == archives and pool.injected_files == injected and not pool.delivered_piece_ids
        mounted = {path: node for path, node in state.os.fs.items() if path.startswith(f"/remote/{target}/")}
        assert mounted
        lore.recompute_node_completion(state, target)
        assert all(state.os.fs[path] == node for path, node in mounted.items())


def test_04_completion_keeps_uplink_pushes_and_physical_resources_independent():
    state, target = scene()
    pool = state.world.node_pools[target]
    exhaust_other_opportunities(state, target)
    pool.uplink_data_consumed = False
    lore.recompute_node_completion(state, target)
    assert not pool.data_complete and not pool.node_cleaned
    pool.uplink_data_consumed = True
    pool.injected_files.append({"path": "/data/retained.txt", "content": "internal archive"})
    pool.pending_push_piece_ids.add("real_push")
    state.world.lore_placements.piece_channel_bindings["real_push"] = "ship_os_mail"
    lore.recompute_node_completion(state, target)
    assert not pool.data_complete and _has_non_uplink_data_frontier(state, {target})
    pool.delivered_piece_ids.add("real_push")
    node = state.world.space.nodes[target]
    for attr, value in (("salvage_scrap_available", 1), ("salvage_modules_available", ["bus_stabilizer"]),
                        ("recoverable_drones_count", 1)):
        original = getattr(node, attr)
        setattr(node, attr, value)
        lore.recompute_node_completion(state, target)
        assert pool.data_complete and not pool.node_cleaned, attr
        setattr(node, attr, original)
    lore.recompute_node_completion(state, target)
    assert pool.node_cleaned and pool.injected_files and "real_push" in pool.delivered_piece_ids


def test_05_deadnodes_global_and_structural_recovery_share_effective_potential():
    state, target = scene()
    exhaust_other_opportunities(state, target)
    with patch.object(structural_recovery, "request_recovery") as request:
        ensure_exploration_recovery(state, "test")
        request.assert_called_once_with(state)
    # Real far contact: cleaned caches must not keep a deadnode candidate alive.
    ensure_sector_generated(state, "S+020_+000_+000")
    target = next(nid for nid, n in state.world.space.nodes.items()
                  if n.kind == "waystation" and n.x_ly > 100)
    state.world.known_nodes = {"ECHO_7", target}
    state.world.known_contacts = {target}
    state.world.visited_nodes = {target}
    lore.initialize_node_pool(state, target)
    exhaust_other_opportunities(state, target)
    state.world.current_node_id = state.ship.current_node_id = "ECHO_7"
    state.world.known_links = {"ECHO_7": set()}
    evaluate_dead_nodes(state, "test")
    assert target not in state.world.dead_nodes
    state.world.node_pools[target].uplink_data_consumed = False
    lore.recompute_node_completion(state, target)
    evaluate_dead_nodes(state, "test")
    assert target in state.world.dead_nodes, "A real pending uplink must remain eligible"
    site = SimpleNamespace(kind="waystation")
    assert structural_recovery._salvage_source(state, target, "ECHO_7", site, eligible=False) is None
    # A prepared eligible LINK on a real station retains its existing interface.
    legitimate, host = scene("station")
    # Materialized links can be partial. Use the actually prepared record,
    # whose endpoints B1 obtains from the certified historical query.
    dest = next(pair[1] for entry in legitimate.world.node_pools[host].base_files
        for line in entry.get("content", "").splitlines()
        if (pair := lore._primary_link_pair({"line": line})) and pair[0] == host)
    legitimate.world.node_pools[host].injected_files.append(dict(
        path="/data/source.txt", access="guest", content=f"LINK: {host} -> {dest}\n"))
    before = pickle.dumps(legitimate)
    assert structural_recovery._salvage_source(legitimate, host, dest,
        legitimate.world.space.nodes[host], eligible=False) is not None
    assert pickle.dumps(legitimate) == before


def test_06_schema3_load_refreshes_old_flags_without_erasing_information():
    for consumed in (False, True):
        state, target = scene()
        exhaust_other_opportunities(state, target)
        pool = state.world.node_pools[target]
        pool.uplink_data_consumed = consumed
        pool.injected_files.append({"path": "/data/retained.txt", "content": "retained history"})
        # Already recovered information stays readable even on a non-salvage host.
        mount_files(state.os.fs, f"/remote/{target}", pool.base_files)
        archives, injected, fs = deepcopy(pool.base_files), deepcopy(pool.injected_files), deepcopy(state.os.fs)
        pool.data_complete = pool.node_cleaned = False  # Pre-B0 persisted cache.
        with TemporaryDirectory() as folder:
            path = save_single_slot(state, Path(folder) / "old.dat")
            raw = path.read_bytes()
            loaded = load_single_slot(path).state
            assert path.read_bytes() == raw, "Loading must not rewrite the historical save"
            restored = loaded.world.node_pools[target]
            assert restored.data_complete == restored.node_cleaned == consumed
            assert restored.base_files == archives and restored.injected_files == injected
            assert restored.uplink_data_consumed == consumed and loaded.os.fs == fs
            save_single_slot(loaded, Path(folder) / "current.dat")
            again = load_single_slot(Path(folder) / "current.dat").state
            assert again.world.node_pools[target] == restored


def test_07_cli_textual_survey_and_negative_hidden_archive_disclosure():
    for locale in Locale:
        state, target = scene()
        state.os.locale = locale
        other = deepcopy(state)
        other.world.node_pools[target].base_files = [
            {"path": "/data/SECRET.txt", "content": "LINK: SECRET_HOST -> SECRET_DEST"}]
        other.world.node_pools[target].injected_files = [
            {"path": "/mail/SECRET.txt", "content": "secret prepared narrative"}]
        before = pickle.dumps(state)
        assert public(state) == public(other)
        assert pickle.dumps(state) == before, "Public diagnostics must remain pure"
        survey_lines = []
        for variant in (state, other):
            engine = Engine()
            engine.apply_action(variant, parse_command("drone survey D1"))
            events = engine.tick(variant, 30.0)
            event = next(e for e in events if e.data.get("message_key") == "job_completed_drone_survey")
            assert event.data["data_recoverable_files_count"] == 0
            assert not event.data["data_signatures_detected"] and event.data["uplink_detected"]
            cli = output(repl.render_events, variant, [event])
            assert cli == presenter.format_event_lines(variant, [event])
            assert not any("SECRET" in line or "secret prepared" in line for line in cli)
            survey_lines.append(cli)
        assert survey_lines[0] == survey_lines[1]


def test_08_capability_matrix_and_other_non_salvage_kinds():
    expected = {
        "station": ("salvage_data", "uplink"), "relay": ("salvage_data", "uplink"),
        "ship": ("salvage_data",), "derelict": ("salvage_data",), "waystation": ("uplink",),
        "origin": (), "unknown": (), "nav_point": (), "transit": (), "future_unknown_kind": (),
    }
    for kind, capabilities in expected.items():
        assert information_capabilities(kind) == capabilities
        assert tuple(value.value for value in planner_capabilities(kind)) == capabilities
        if capabilities:
            continue
        state, target = scene()
        state.world.space.nodes[target].kind = kind  # Deliberate capability-negative fixture.
        exhaust_other_opportunities(state, target)
        pool = state.world.node_pools[target]
        assert pool.data_complete and pool.node_cleaned
        assert not lore.collect_node_salvage_data_files(state, target)
        assert not _has_non_uplink_data_frontier(state, {target})
        assert not _has_uplink_frontier(state, {target})


def main():
    for name, func in sorted(globals().copy().items()):
        if name.startswith("test_"):
            func()
            print("PASS", name)
    print("INFORMATION CAPABILITIES SMOKE PASSED")


if __name__ == "__main__":
    main()
