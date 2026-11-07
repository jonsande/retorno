"""P3: bounded construction, fallback, public acquisition and persistence."""
from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_fast_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.io.save_load import save_single_slot, load_single_slot
from retorno.model.os import Locale
from retorno.runtime.loop import GameLoop
from retorno.worldgen import manifest as m, information as info, historical_radio as radio
from retorno.worldgen.generator import ensure_historical_node, validate_universe_state
from prologue_navigation_policy_smoke import (
    command, output, test_public_seed_1,
    test_reusable_policy_files_radio_and_invalid_authoring,
    test_subtraction_and_other_hosts, test_normal_29_and_persistence,
)


def base_definition(d):
    return replace(d, prologue_version="", prologue_identity=None,
                   prologue_fallback=None, prologue_excluded=())


def check(s):
    frozen = pickle.dumps(s)
    chain = info.certify_prologue(s)
    d, definition = s.world.manifest_definition, s.world.information_definition
    site = m.validate_prologue(d)
    host = chain["host_id"]
    assert host != "ARCHIVE_01" and site.identity.namespace == "procedural"
    for anchor in ("ECHO_7", "HARBOR_12"):
        target = m.resolve_operative_id(d, anchor)
        assert 0 < math.dist(site.position_ly, target.position_ly) <= 45
    ordinary = info.query_information(d, definition, "ECHO_7", include_prologue=False)
    actual = info.query_information(d, definition, "ECHO_7")
    routes = [r.destination_id for r in actual.uplink]
    old_routes = [r.destination_id for r in ordinary.uplink]
    assert host in routes and "HARBOR_12" not in routes and len(routes) <= 3
    assert set(old_routes[:-1]) <= set(routes)
    assert actual.files == ordinary.files
    # Changes to hidden reservation data cannot reach public query surfaces.
    hidden = deepcopy(s)
    hidden.world.narrative_snapshot["prologue_chain"]["host_id"] = "UNOBSERVED"
    hidden.world.manifest_definition = replace(d, prologue_identity=None)
    assert output(repl.render_status, hidden) == output(repl.render_status, deepcopy(s))
    assert pickle.dumps(s) == frozen
    # Neither the additional archive nor reserved uplink enters the B2 pool.
    snap = deepcopy(s.world.narrative_snapshot)
    snap.pop("prologue_chain")
    old_info = info.define_information(snap)
    old_radio = radio.define_radio(snap, old_info)
    for nid in ("ECHO_7", host, "HARBOR_12"):
        before = radio.query_host(d, old_radio, old_info, nid)
        after = radio.query_host(d, s.world.radio_definition, definition, nid)
        assert (after is None) if before is None else replace(after, rules_key=before.rules_key) == before
    # Exercise a navigation emission even when these seeds' natural radio is
    # silent/ambient. The new salvage archive must still not change its payload.
    def draw(world, key, site, domain):
        return 0.0 if domain in {"program_exists", "navigation"} else .5
    with patch.object(radio, "_draw", side_effect=draw):
        before = radio.query_host(d, old_radio, old_info, host)
        after = radio.query_host(d, s.world.radio_definition, definition, host)
        assert (after is None) if before is None else replace(after, rules_key=before.rules_key) == before
    assert pickle.dumps(s) == frozen
    # New history changes neither ordinary sites nor ordinary topology.
    base = base_definition(d)
    for sid in m._neighbor_sector_ids_2d("S+000_+000_+000"):
        before = m.new_session(base).sector(sid)
        after = m.new_session(d).sector(sid)
        assert after.internal_edges == before.internal_edges
        assert tuple(x for x in after.sites if x != d.prologue_fallback) == before.sites
    return dict(seed=s.meta.rng_seed, host=host, position=site.position_ly,
                fallback=d.prologue_fallback is not None, routes=routes)


def structural():
    evidence = []
    for seed in (1, 29, 701):
        s = create_initial_state_prologue(seed=seed)
        evidence.append(check(s))
        fast = create_initial_state_fast_sandbox(seed=seed)
        assert fast.world.manifest_definition == s.world.manifest_definition
        assert fast.world.information_definition == s.world.information_definition
        host = evidence[-1]["host"]
        assert host in fast.world.known_links["ECHO_7"]
        assert "HARBOR_12" not in fast.world.known_links["ECHO_7"]
        assert not fast.os.debug_enabled
        # Certificate rejects broken channels, narrative conflicts and tampering.
        for failure in ("archive", "uplink", "reservation", "identity"):
            twin = deepcopy(s)
            if failure == "reservation":
                twin.world.narrative_snapshot["reservations"]["test"] = dict(node_id=host)
            elif failure == "identity":
                twin.world.manifest_definition = replace(twin.world.manifest_definition, prologue_identity=None)
            else:
                original = info.query_information
                def broken(world, definition, node_id, **kw):
                    result = original(world, definition, node_id, **kw)
                    if failure == "archive" and node_id == host:
                        return replace(result, files_json="[]")
                    if failure == "uplink" and node_id == "ECHO_7":
                        return replace(result, uplink=())
                    return result
            try:
                if failure in {"archive", "uplink"}:
                    with patch.object(info, "query_information", side_effect=broken):
                        info.certify_prologue(twin)
                else:
                    info.certify_prologue(twin)
            except (ValueError, AttributeError):
                pass
            else:
                raise AssertionError(failure)
    return evidence


def fallback():
    reserve = m.reserve_prologue
    def no_candidates(d, excluded=()):
        base = base_definition(d)
        session = m.new_session(base)
        excluded = set(excluded)
        excluded.update(m.operative_id(base, site)
                        for sid in m._neighbor_sector_ids_2d("S+000_+000_+000")
                        for site in session.sector(sid).sites if site.identity.namespace == "procedural")
        return reserve(d, excluded)
    with patch.object(m, "reserve_prologue", side_effect=no_candidates):
        s = create_initial_state_prologue(seed=29)
    evidence = check(s)
    d = s.world.manifest_definition
    assert d.prologue_fallback is not None
    site = m.validate_prologue(d)
    assert radio.query_host(d, s.world.radio_definition, s.world.information_definition, evidence["host"]) is None
    original_info = info.query_information(base_definition(d), s.world.information_definition,
                                           "ECHO_7", include_prologue=False)
    new_info = info.query_information(d, s.world.information_definition, "ECHO_7", include_prologue=False)
    assert replace(new_info, examined_generation_cohorts=original_info.examined_generation_cohorts) == original_info
    inventory = m.query_physical_sectors(d, [site.physical_sector_id])
    assert sum(x == site for x in inventory.sites) == 1
    assert ensure_historical_node(s, evidence["host"])
    assert ensure_historical_node(s, evidence["host"])
    assert s.world.space.nodes[evidence["host"]].historical_key == site.identity.encoded
    validate_universe_state(s)
    with TemporaryDirectory() as folder:
        slot = Path(folder) / "fallback.dat"
        save_single_slot(s, slot)
        loaded = load_single_slot(slot).state
        assert loaded.world.manifest_definition == d
    return evidence


def public_chain():
    # FAST_SANDBOX only skips ship preparation. Every chain action below uses
    # public commands; no debug, teleport, resource or knowledge edits.
    s, engine = create_initial_state_fast_sandbox(seed=1), Engine()
    assert not create_initial_state_prologue(seed=1).meta.prologue_complete
    assert not s.meta.prologue_complete
    output(repl.render_cat, s, "/remote/ECHO_7/logs/echo_cache.en.txt")
    assert "HARBOR_12" in s.world.known_nodes and not s.meta.prologue_complete
    debug = deepcopy(s)
    debug.os.debug_enabled = True
    output(repl.render_debug_graph_all, debug)
    assert not debug.meta.prologue_complete
    loop = GameLoop(engine, s)
    loop.set_auto_tick(False)
    paths = [p for p in s.os.fs if p.startswith("/logs/nav/uplink_ECHO_7_")]
    output(repl.render_cat, s, paths[0])
    text = s.os.fs[paths[0]].content  # Canonical tokens behind display aliases.
    # The reserved destination is last when it was not already ordinary.
    host = [line.split(" -> ")[1] for line in text.splitlines() if line.startswith("LINK: ECHO_7 -> ")][-1]
    assert host == s.world.narrative_snapshot["prologue_chain"]["host_id"]
    journal = []
    def run(text):
        result = command(s, engine, text)
        journal.append(result)
        assert not any("blocked" in line.lower() for line in result["output"]), result
    def travel(target):
        run("nav " + target)
        assert s.ship.in_transit and repl._hibernate_blocked_message(s) is None
        assert not s.meta.prologue_complete  # Starting either leg is insufficient.
        if target == "HARBOR_12":
            # Same legitimate journey, ordinary tick arrival instead of the
            # hibernation driver. Two large ticks avoid a survival simulation.
            ordinary = deepcopy(s)
            remaining = ordinary.ship.arrival_t - ordinary.clock.t
            engine.tick(ordinary, remaining / 2)
            assert ordinary.ship.in_transit and not ordinary.meta.prologue_complete
            arrived = engine.tick(ordinary, ordinary.ship.arrival_t - ordinary.clock.t)
            assert sum(e.type == EventType.ARRIVED for e in arrived) == 1
            assert ordinary.world.current_node_id == "HARBOR_12" and ordinary.ship.docked_node_id is None
            assert ordinary.meta.prologue_complete
            assert not any(e.type == EventType.ARRIVED for e in engine.tick(ordinary, 1))
            assert ordinary.meta.prologue_complete
        result = repl._execute_hibernate(loop, (s.ship.arrival_t-s.clock.t+1)/Balance.YEAR_S)
        journal.append(dict(command="hibernate until_arrival", years=result.actual_years))
        assert not s.ship.in_transit and s.world.current_node_id == target
        assert s.meta.prologue_complete == (target == "HARBOR_12")
    travel(host)
    run("dock " + host)
    run("power plan normal")
    run("power on drone_bay")
    run("drone deploy D1 " + host)
    run("drone salvage data D1")
    run("drone recall D1")
    path = "/remote/" + host + "/data/nav/waystation_solution.txt"
    assert path in s.os.fs
    assert "HARBOR_12" not in s.world.known_links.get(host, ())
    with TemporaryDirectory() as folder:
        slot = Path(folder) / "recovered.dat"
        save_single_slot(s, slot)
        loaded = load_single_slot(slot).state
        assert loaded.world.manifest_definition == s.world.manifest_definition
        assert loaded.os.fs[path] == s.os.fs[path]
        assert not loaded.meta.prologue_complete
        for locale in (Locale.EN, Locale.ES):
            twin = deepcopy(loaded)
            twin.os.locale = locale
            imported = output(repl.render_cat, twin, path)
            assert "LINK:" in imported and "HARBOR_12" in twin.world.known_links[host]
            assert not twin.meta.prologue_complete  # Route knowledge is insufficient.
            files, links = deepcopy(twin.os.fs), deepcopy(twin.world.known_links)
            output(repl.render_cat, twin, path)
            assert twin.os.fs == files and twin.world.known_links == links
        s = loaded
        loop = GameLoop(engine, s)
        loop.set_auto_tick(False)
        journal.append(dict(command="cat " + path, output=output(repl.render_cat, s, path)))
        assert not s.meta.prologue_complete
        run("undock")
        travel("HARBOR_12")
        assert s.ship.docked_node_id is None  # Completion does not require docking.
        for _ in range(3):
            assert not any(e.type == EventType.ARRIVED for e in engine.tick(s, 1))
            assert s.meta.prologue_complete
        save_single_slot(s, slot)
        assert load_single_slot(slot).state.meta.prologue_complete
        run("nav " + host)
        assert s.ship.in_transit and s.meta.prologue_complete
        save_single_slot(s, slot)
        departing = load_single_slot(slot).state
        assert departing.ship.in_transit and departing.meta.prologue_complete
        arrived = engine.tick(departing, departing.ship.arrival_t - departing.clock.t + 1)
        assert sum(e.type == EventType.ARRIVED for e in arrived) == 1
        assert departing.world.current_node_id == host and departing.meta.prologue_complete
        save_single_slot(departing, slot)
        assert load_single_slot(slot).state.meta.prologue_complete
    assert not s.os.debug_enabled and not s.os.god_active
    return journal


def main():
    evidence = dict(structural=structural())
    print("PASS structural certificate, seeds 1/29/701, FAST_SANDBOX, negative cases, B2 ordinary pool")
    evidence["fallback"] = fallback()
    print("PASS controlled no-candidate fallback, physical inventory/materialization, save/load")
    evidence["public_chain"] = public_chain()
    print("PASS public reserved chain, salvage/read/import EN/ES, save/load, no debug")
    evidence["alternative_seed1"] = test_public_seed_1()
    print("PASS original seed 1 two-uplink alternative preserved")
    test_reusable_policy_files_radio_and_invalid_authoring()
    print("PASS focused P1 authored exclusions and B2 subtraction")
    test_subtraction_and_other_hosts()
    print("PASS focused P1 ordinary projection, physical stability, seeds 1/29/701")
    evidence["normal29"] = test_normal_29_and_persistence()
    print("PASS normal prologue 29, persistence and incompatible catalogue rejection")
    Path("/tmp/retorno-p3-evidence.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
