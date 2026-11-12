"""B1: stable historical facts, real boundaries, finite actions and old slots."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import random
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli import repl
from retorno.core import lore, structural_recovery as recovery
from retorno.core.engine import Engine
from retorno.io import save_load
from retorno.model.os import Locale, mount_files
from retorno.runtime import data_loader as data
from retorno.worldgen import information as info, manifest
from retorno.worldgen.generator import ensure_sector_generated, universe_definition, ensure_historical_node
from retorno.worldgen.narrative import canonical, collect_catalog, fingerprint
from information_capabilities_smoke import scene as ready_scene
from knowledge_boundary_smoke import public

SEEDS = (0, 1, 2, 7, 42, 137, 2026, 65535, 271828, 314159, 8675309, 2147483647)
FIXTURE = Path(__file__).parent / "fixtures/historical_information_legacy"


def signature(result):
    return fingerprint(asdict(result))


def output(func, *args):
    with redirect_stdout(io.StringIO()) as stream:
        func(*args)
    return stream.getvalue()


def query(state, nid="ECHO_7"):
    return lore.historical_information_for_node(state, nid)


def prepared(pool):
    return pool.base_files, pool.uplink_route_pool, pool.uplink_records, pool.information_version, pool.information_rules_key


def test_01_time_knowledge_routes_counters_locale_and_game_rng_do_not_select_history():
    for seed in (0, 42, 271828):
        base = create_initial_state_prologue(seed=seed)
        expected = signature(query(base))
        for clock, locale in ((0, Locale.EN), (1, Locale.ES), (86400, Locale.EN), (1e10, Locale.ES)):
            state = deepcopy(base)
            state.clock.t, state.os.locale = clock, locale
            state.meta.rng_counter += 173
            state.world.lore.counters["uplink_count"] = 987
            state.world.known_nodes.update(("UNRELATED", "HARBOR_12"))
            state.world.known_contacts.update(state.world.space.nodes)
            state.world.known_links = {"ECHO_7": {r.destination_id for r in query(base).uplink}}
            state.world.recovery_searches["global"] = dict(status="search_pending", cursor=1000)
            before, rng = pickle.dumps(state), random.getstate()
            assert signature(query(state)) == expected
            assert pickle.dumps(state) == before and random.getstate() == rng


def test_02_partial_materialization_and_opposite_pool_orders_produce_identical_records():
    base = create_initial_state_prologue(seed=0)
    definition = universe_definition(base)
    historical = manifest.query_physical_sectors(definition,
        ("S+000_+000_+000", "S+000_-001_+000", "S-001_-001_+000"))
    hosts = [manifest.operative_id(definition, s) for s in historical.sites
        if s.kind in {"station", "relay", "ship", "derelict", "waystation"}][:8]
    assert len(hosts) >= 4
    left, right = deepcopy(base), deepcopy(base)
    before = {nid: signature(query(base, nid)) for nid in hosts}
    sectors = ("S+000_+000_+000", "S+000_+000_+001", "S+020_+000_+000")
    for sid in sectors:
        ensure_sector_generated(left, sid)
    for sid in reversed(sectors):
        ensure_sector_generated(right, sid)
    for nid in hosts:
        lore.initialize_node_pool(left, nid)
    right.clock.t = 987654321
    for nid in reversed(hosts):
        lore.initialize_node_pool(right, nid)
    for nid in hosts:
        assert signature(query(left, nid)) == signature(query(right, nid)) == before[nid]
        assert prepared(left.world.node_pools[nid]) == prepared(right.world.node_pools[nid])


def test_03_processes_hash_seeds_and_prior_queries_do_not_change_identity():
    code = """
import json
from dataclasses import asdict
from retorno.bootstrap import create_initial_state_prologue
from retorno.core import lore
from retorno.worldgen.generator import universe_definition
from retorno.worldgen.manifest import query_manifest
from retorno.worldgen.narrative import fingerprint
rows=[]
for seed in (0,1,2,7,42,137,2026,65535,271828,314159,8675309,2147483647):
 s=create_initial_state_prologue(seed=seed)
 query_manifest(universe_definition(s),('S+020_+000_+000',))
 rows.append(fingerprint(asdict(lore.historical_information_for_node(s,'ECHO_7'))))
print(json.dumps(rows))
"""
    results = [subprocess.check_output([sys.executable, "-c", code],
        env=dict(os.environ, PYTHONHASHSEED=value), text=True).strip()
        for value in ("0", "137", "987654321")]
    assert results[0] == results[1] == results[2]


def test_04_every_destination_and_connection_is_certified_and_capped():
    seen = set()
    for seed in SEEDS:
        state = create_initial_state_prologue(seed=seed)
        world = universe_definition(state)
        result = query(state)
        topology = manifest.query_manifest(world, (result.host.generation_sector_id,))
        edges = {frozenset((e.left, e.right)): e.kind for e in topology.edges}
        assert len(result.uplink) <= 3 and len({r.destination_id for r in result.uplink}) == len(result.uplink)
        for record in result.uplink:
            target = manifest.resolve_operative_id(world, record.destination_id)
            assert target is not None and 0 < record.distance_ly <= 45
            edge = edges.get(frozenset((result.host.identity, target.identity)))
            assert (record.kind == "historical_connection") == bool(edge)
            assert record.relation == edge
            seen.add(record.kind)
            text = info.navigation_content(record)
            assert f"LINK: ECHO_7 -> {record.destination_id}" in text
            if not edge:
                assert "no evidence of historical traffic" in text and "no acredita tráfico histórico" in text
    assert seen == {"historical_connection", "navigation_solution"}


def test_05_incomplete_queries_never_freeze_an_empty_pool():
    state = create_initial_state_prologue(seed=0)
    before = pickle.dumps(state)
    try:
        lore.historical_information_for_node(state, "ECHO_7", budget=info.InformationBudget(physical_sectors=1))
    except info.InformationIncomplete:
        pass
    else:
        raise AssertionError("A truncated domain must not be reported as absence")
    assert pickle.dumps(state) == before
    with patch.object(lore, "historical_information_for_node", side_effect=info.InformationIncomplete("test budget")):
        try:
            lore.initialize_node_pool(state, "ECHO_7")
        except info.InformationIncomplete:
            pass
        else:
            raise AssertionError("Initialization must propagate incomplete history")
    assert pickle.dumps(state) == before and "ECHO_7" not in state.world.node_pools
    lore.initialize_node_pool(state, "ECHO_7")
    assert state.world.node_pools["ECHO_7"].uplink_route_pool


def test_06_primary_disclosure_filters_delivery_without_rewriting_or_replacement():
    state, host = ready_scene("station")
    pool = state.world.node_pools[host]
    historical = signature(query(state, host))
    immutable = deepcopy(prepared(pool))
    nav_targets = {entry["navigation_record"]["destination_id"] for entry in pool.base_files
        if entry.get("navigation_record")}
    assert nav_targets
    targets = set(pool.uplink_route_pool) | nav_targets
    arcs = [dict(arc_id=f"locked_{i}", primary_intel=dict(id="primary", kind="link", line=f"LINK: {host} -> {dest}"))
        for i, dest in enumerate(sorted(targets))]
    with patch.object(lore, "load_arcs", return_value=arcs), patch.dict(state.world.narrative_snapshot, arcs=arcs):
        assert signature(query(state, host)) == historical
        assert not lore.disclosable_uplink_destinations(state, pool)
        assert not any(f.get("navigation_record") for f in lore.collect_node_salvage_data_files(state, host))
        output(repl._handle_uplink, state)
        assert pool.uplink_data_consumed and not state.world.known_links.get(host)
        # History stays intact. First consumption cannot become unlimited retries.
        for arc in arcs:
            state.world.arc_placements[arc["arc_id"]] = {"primary": {"unlocked": True}}
        assert any(f.get("navigation_record") for f in lore.collect_node_salvage_data_files(state, host))
        output(repl._handle_uplink, state)
        assert not state.world.known_links.get(host)
        assert signature(query(state, host)) == historical and prepared(pool) == immutable


def test_07_primary_protection_does_not_ban_natural_sensor_discovery():
    state = create_initial_state_sandbox()
    state.world.current_node_id = state.ship.current_node_id = "UNKNOWN"
    state.world.known_nodes.clear()
    state.world.known_contacts.clear()
    arc = dict(arc_id="sensor_exception", primary_intel=dict(kind="node", line="NODE: ECHO_7"))
    with patch.object(lore, "load_arcs", return_value=[arc]), \
         patch.dict(state.world.narrative_snapshot, arcs=[arc]), \
         patch("retorno.config.balance.Balance.SENSORS_DETECT_P_NEAR", 1.0), \
         patch("retorno.config.balance.Balance.SENSORS_DETECT_P_FAR", 1.0):
        assert "ECHO_7" in lore._locked_primary_targets(state)
        seen, discovered, _ = Engine()._perform_scan(state)
        assert "ECHO_7" in seen and "ECHO_7" in discovered


def test_08_recovery_queries_preexisting_lazy_archives_without_creating_them():
    state = create_initial_state_prologue(seed=0)
    world = universe_definition(state)
    inventory = manifest.query_physical_sectors(world, ("S-001_-001_+000", "S+000_+000_+000"))
    site = next(site for site in inventory.sites if site.kind in {"station", "ship", "derelict", "relay"}
        and site.identity.namespace == "procedural")
    host = manifest.operative_id(world, site)
    result = query(state, host)
    entry = next(entry for entry in result.files if entry.get("navigation_record"))
    destination = entry["navigation_record"]["destination_id"]
    before, rng = pickle.dumps(state), random.getstate()
    source = recovery._salvage_source(state, host, destination, site)
    assert source == recovery.StageSource(entry["path"], recovery._digest(entry))
    assert recovery._salvage_source(state, host, "UNRELATED", site) is None
    assert pickle.dumps(state) == before and random.getstate() == rng
    assert host not in state.world.node_pools
    assert not state.world.narrative_snapshot["radio_emitters"]
    selected = recovery.select_recovery(state)
    assert selected.status in {"conditional", "incomplete"} and not state.world.recovery_plans
    assert pickle.dumps(state) == before
    try:
        recovery._salvage_source(state, host, destination, site, archive_cache={}, archive_limit=0)
    except ValueError as exc:
        assert "budget" in str(exc)
    else:
        raise AssertionError("Recovery source evaluation must retain incomplete status")


@contextmanager
def pre_b1_catalogue():
    """The genuine save requires its original installed catalogue, not C2b/P1."""
    with TemporaryDirectory(prefix="retorno-pre-b1-") as folder:
        root = Path(folder) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        (root / "arcs/amanecer_elena_01.json").unlink()
        echo = root / "locations/echo_7.json"
        value = json.loads(echo.read_text())
        value.pop("navigation_policy", None)
        echo.write_text(json.dumps(value))
        with patch.object(data, "_DATA_ROOT", root):
            yield


@pre_b1_catalogue()
def test_09_pre_engine_slot_is_rejected_and_current_legacy_rules_remain_testable():
    path = FIXTURE / "B0-schema3.dat"
    expected = json.loads((FIXTURE / "B0-schema3.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]
    original = path.read_bytes()
    files_before = {item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in FIXTURE.iterdir() if item.is_file()}
    catalog_before = fingerprint(collect_catalog())
    try:
        save_load.load_single_slot(path)
    except save_load.SaveLoadError as exc:
        assert "Incompatible engines/fuel state" in str(exc), str(exc)
    else:
        raise AssertionError("The pre-engine slot was accepted without an explicit migration")
    assert path.read_bytes() == original
    assert {item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in FIXTURE.iterdir() if item.is_file()} == files_before
    assert fingerprint(collect_catalog()) == catalog_before

    # Separate synthetic current-architecture scene: exercises the permitted
    # legacy information algorithm, not migration of the genuine B0 slot.
    state = create_initial_state_sandbox(seed=expected["seed"])
    state.world.information_version = info.LEGACY_VERSION
    state.world.information_definition = None
    state.world.radio_history_version = "legacy-radio-v0"
    state.world.radio_definition = None
    world = universe_definition(state)
    sites = manifest.query_physical_sectors(world, ("S+000_-001_+000",)).sites
    site = next(site for site in sites if site.identity.namespace == "procedural"
        and site.kind in {"waystation", "station", "relay"})
    host = manifest.operative_id(world, site)
    assert ensure_historical_node(state, host)
    assert host not in state.world.node_pools
    for clock in (0, 86400):
        variant = deepcopy(state)
        variant.clock.t = clock
        assert lore._precompute_uplink_route_pool_for_node(variant, host) == lore._legacy_precompute_uplink_route_pool_for_node(deepcopy(variant), host)
        lore.initialize_node_pool(variant, host)
        pool = variant.world.node_pools[host]
        assert pool.information_version == info.LEGACY_VERSION and not pool.uplink_records
        assert all("information_version" not in file for file in pool.base_files)
        assert pool.uplink_route_pool
    lore.initialize_node_pool(state, host)
    original_pools, original_fs = deepcopy(state.world.node_pools), deepcopy(state.os.fs)
    with TemporaryDirectory() as folder:
        saved = save_load.save_single_slot(state, Path(folder) / "legacy.dat")
        again = save_load.load_single_slot(saved).state
        assert again.world.node_pools == original_pools and again.os.fs == original_fs
        assert again.world.information_version == info.LEGACY_VERSION
        assert again.world.information_definition is None
    assert path.read_bytes() == original
    assert fingerprint(collect_catalog()) == catalog_before


def test_10_new_save_load_and_incompatible_metadata_are_nondestructive():
    state = create_initial_state_sandbox()
    lore.sync_node_pools_for_known_nodes(state)
    expected = deepcopy(state.world.node_pools)
    with TemporaryDirectory() as folder:
        path = save_load.save_single_slot(state, Path(folder) / "new.dat")
        original = path.read_bytes()
        loaded = save_load.load_single_slot(path).state
        assert loaded.world.node_pools == expected and signature(query(loaded)) == signature(query(state))
        bad_states = []
        wrong = deepcopy(state)
        wrong.world.information_definition = replace(wrong.world.information_definition, rules_key="0" * 64)
        bad_states.append(wrong)
        wrong = deepcopy(state)
        wrong.world.information_version = "historical-information-v999"
        bad_states.append(wrong)
        wrong = deepcopy(state)
        wrong.world.node_pools["ECHO_7"].uplink_route_pool.append("NONEXISTENT")
        bad_states.append(wrong)
        wrong = deepcopy(state)
        wrong.world.node_pools["ECHO_7"].base_files[0]["content"] += "\nforged history"
        bad_states.append(wrong)
        for bad in bad_states:
            try:
                save_load.save_single_slot(bad, path)
            except save_load.SaveLoadError:
                pass
            else:
                raise AssertionError("Incompatible history must be rejected")
            assert path.read_bytes() == original
            blob = pickle.dumps(bad, protocol=pickle.HIGHEST_PROTOCOL)
            encoded = save_load._SAVE_MAGIC + b"\n" + hashlib.sha256(blob).hexdigest().encode() + b"\n" + blob
            invalid = Path(folder) / "invalid.dat"
            invalid.write_bytes(encoded)
            try:
                save_load.load_single_slot(invalid)
            except save_load.SaveLoadError:
                pass
            else:
                raise AssertionError("Load must validate contract, not only checksum")
            assert invalid.read_bytes() == encoded


def test_11_bilingual_archives_and_safe_environmental_claims_share_facts():
    state, host = ready_scene("station")
    baseline = query(state, host)
    state.os.locale = Locale.EN
    english = lore.build_procedural_salvage_mail_content(state, state.world.space.nodes[host])
    state.os.locale = Locale.ES
    spanish = lore.build_procedural_salvage_mail_content(state, state.world.space.nodes[host])
    assert signature(query(state, host)) == signature(baseline)
    assert "not a current ship measurement" in english and "No es una medición actual" in spanish
    assert "No current response, traffic or survivor checks" in english
    assert "No constan comprobaciones actuales de respuesta, tráfico ni supervivientes" in spanish
    ident = english.split("Report ID: ")[1].splitlines()[0]
    assert f"ID de informe: {ident}" in spanish
    # Frozen probabilities control a history; temporary gameplay configuration
    # changes cannot reinterpret it. Save validation rejects changed rules.
    with patch("retorno.config.balance.Balance.SALVAGE_DATA_MAIL_P_STATION_SHIP", 0.0):
        assert signature(query(state, host)) == signature(baseline)
        try:
            info.validate_definition(state.world.information_definition, current=True)
        except ValueError:
            pass
        else:
            raise AssertionError("Changed generation probabilities must not silently load old history")


def test_12_hidden_queries_preserve_public_cli_textual_and_acquired_information():
    for locale in Locale:
        state = create_initial_state_sandbox()
        state.os.locale = locale
        lore.sync_node_pools_for_known_nodes(state)
        mount_files(state.os.fs, "/remote/ECHO_7", state.world.node_pools["ECHO_7"].base_files)
        observed, before, rng = public(state), pickle.dumps(state), random.getstate()
        world = universe_definition(state)
        unseen = manifest.query_physical_sectors(world, ("S+020_+000_+000",))
        for site in unseen.sites[:5]:
            query(state, manifest.operative_id(world, site))
        assert public(state) == observed
        assert pickle.dumps(state) == before and random.getstate() == rng
        other = deepcopy(state)
        other.world.node_pools["HIDDEN_ARCHIVE"] = type(state.world.node_pools["ECHO_7"])(
            base_files=[dict(path="/data/SECRET.txt", content="LINK: SECRET_A -> SECRET_B")])
        assert public(other) == observed


def test_13_known_routes_do_not_replenish_fixed_uplink_or_duplicate_after_load():
    state = create_initial_state_sandbox()
    state.ship.docked_node_id = "ECHO_7"
    lore.sync_node_pools_for_known_nodes(state)
    pool = state.world.node_pools["ECHO_7"]
    original = deepcopy(prepared(pool))
    dest = pool.uplink_route_pool[0]
    ensure_historical_node(state, dest)
    from retorno.model.world import add_known_link
    add_known_link(state.world, "ECHO_7", dest, bidirectional=True)
    state.world.known_nodes.add(dest)
    output(repl._handle_uplink, state)
    assert prepared(pool) == original and pool.uplink_data_consumed
    assert set(pool.uplink_route_pool) <= state.world.known_links["ECHO_7"]
    assert any(dest in file.content for path, file in state.os.fs.items() if path.startswith("/logs/nav/uplink_"))
    with TemporaryDirectory() as folder:
        path = save_load.save_single_slot(state, Path(folder) / "consumed.dat")
        loaded = save_load.load_single_slot(path).state
        fs, links, counters = deepcopy(loaded.os.fs), deepcopy(loaded.world.known_links), deepcopy(loaded.world.lore.counters)
        loaded.clock.t += 987654321
        output(repl._handle_uplink, loaded)
        assert loaded.os.fs == fs and loaded.world.known_links == links and loaded.world.lore.counters == counters


def test_14_authored_tables_select_certified_destinations_before_player_state():
    state = create_initial_state_prologue(seed=0)
    snapshot = deepcopy(state.world.narrative_snapshot)
    table = dict(min_authored=1, max_authored=1, authored_candidates=[dict(node_id="HARBOR_12", weight=5)])
    # Quota fixture without the production host's subtractive puzzle policy.
    next(loc for loc in snapshot["locations"] if loc["node"]["node_id"] == "ECHO_7").pop("navigation_policy", None)
    next(loc for loc in snapshot["locations"] if loc["node"]["node_id"] == "ECHO_7")["uplink_table"] = table
    definition = info.define_information(snapshot)
    result = info.query_information(universe_definition(state), definition, "ECHO_7")
    assert result.uplink[0].destination_id == "HARBOR_12"
    assert all(r.distance_ly <= 45 for r in result.uplink)
    state.world.known_links["ECHO_7"] = {"HARBOR_12"}
    assert result == info.query_information(universe_definition(state), definition, "ECHO_7")


def test_15_textual_public_uplink_dispatch_uses_the_same_finite_records():
    from textual.widgets import Input
    from retorno.ui_textual.app import RetornoTextualApp
    async def run(locale):
        with patch.dict(os.environ, {"RETORNO_SCENARIO": "sandbox"}):
            app = RetornoTextualApp(force_new_game=True)
        state = app.loop.state
        state.os.locale = locale
        state.os.audio.enabled = state.os.audio.ambient_enabled = False
        state.ship.docked_node_id = "ECHO_7"
        app._play_startup_sequence = app._startup_panel_blackout = False
        async with app.run_test() as pilot:
            app.loop.set_auto_tick(False)
            lore.sync_node_pools_for_known_nodes(state)
            pool = state.world.node_pools["ECHO_7"]
            fixed = deepcopy(prepared(pool))
            widget = app.query_one("#input", Input)
            widget.value = "uplink"
            await pilot.press("enter")
            await pilot.pause()
            assert pool.uplink_data_consumed and prepared(pool) == fixed
            links = deepcopy(state.world.known_links)
            widget.value = "uplink"
            await pilot.press("enter")
            await pilot.pause()
            assert state.world.known_links == links and prepared(pool) == fixed
            assert any("uplink_complete" in line for line in app._log_buffer)
    for locale in Locale:
        asyncio.run(run(locale))


def test_16_authorized_scheduler_primary_delivers_without_rewriting_historical_records():
    dest = "ARCHIVE_01"
    piece = dict(id="primary", kind="link", line=f"LINK: ECHO_7 -> {dest}", allowed_channels=["uplink_only"])
    arc = dict(arc_id="authorized_fixture", primary_intel=piece)
    key = "arc:authorized_fixture:primary"
    with TemporaryDirectory(prefix="retorno-h1-primary-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        (root / "arcs/authorized_fixture.json").write_text(json.dumps(arc), encoding="utf-8")
        with patch.object(data, "_DATA_ROOT", root):
            state = create_initial_state_sandbox()
            state.ship.docked_node_id = "ECHO_7"
            lore.sync_node_pools_for_known_nodes(state)
            pool = state.world.node_pools["ECHO_7"]
            history = deepcopy(prepared(pool))
            assert any(item["arc_id"] == "authorized_fixture" for item in state.world.narrative_snapshot["arcs"])
            entry = next(item for item in lore._iter_all_pieces(state) if item["piece_key"] == key)
            assert entry["channels"] == ["uplink_only"]
            assert manifest.resolve_operative_id(universe_definition(state), dest) is not None
            assert pool.uplink_route_pool
            assert lore._assign_piece_to_node(state, entry, "ECHO_7")
            output(repl._handle_uplink, state)
            assert key in state.world.lore.delivered and key in pool.delivered_piece_ids
            assert key not in pool.pending_push_piece_ids
            assert state.world.arc_placements["authorized_fixture"]["primary"]["unlocked"]
            assert dest in state.world.known_links["ECHO_7"] and prepared(pool) == history
            narrative_intel = [item for item in state.world.intel if item.source_kind == "uplink_only"]
            assert len(narrative_intel) == 1
            assert (narrative_intel[0].from_id, narrative_intel[0].to_id) == ("ECHO_7", dest)
            with TemporaryDirectory() as folder:
                slot = save_load.save_single_slot(state, Path(folder) / "primary.dat")
                loaded = save_load.load_single_slot(slot).state
                assert key in loaded.world.lore.delivered
                assert loaded.world.arc_placements["authorized_fixture"]["primary"]["unlocked"]
                assert prepared(loaded.world.node_pools["ECHO_7"]) == history
                counters, fs, links, intel = (deepcopy(loaded.world.lore.counters),
                    deepcopy(loaded.os.fs), deepcopy(loaded.world.known_links), deepcopy(loaded.world.intel))
                output(repl._handle_uplink, loaded)
                assert (loaded.world.lore.counters == counters and loaded.os.fs == fs
                    and loaded.world.known_links == links and loaded.world.intel == intel)
                assert prepared(loaded.world.node_pools["ECHO_7"]) == history


def main():
    for name, function in sorted(globals().copy().items()):
        if name.startswith("test_"):
            function()
            print("PASS", name, flush=True)
    print("HISTORICAL INFORMATION SMOKE PASSED")


if __name__ == "__main__":
    main()
