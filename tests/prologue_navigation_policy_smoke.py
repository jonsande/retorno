"""P1: subtractive authored B1/B2 policy, normal prologue and public seed 1."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import pickle
import re
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_fast_sandbox, create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot, SaveLoadError
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.runtime import data_loader as data
from retorno.runtime.loop import GameLoop
from retorno.worldgen import information as info, historical_radio as radio
from retorno.worldgen.narrative import collect_catalog, compile_catalog, ContentError
from structural_recovery_smoke import scene

POLICY = dict(version=info.NAVIGATION_POLICY_VERSION, exclude_destinations=["HARBOR_12"])


def output(fn, *args):
    with redirect_stdout(io.StringIO()) as stream:
        fn(*args)
    return stream.getvalue()


def unconfigured(snapshot):
    snapshot = deepcopy(snapshot)
    snapshot.pop("prologue_chain", None)  # Compare the ordinary P1 projection.
    for loc in snapshot["locations"]:
        loc.pop("navigation_policy", None)
    return info.define_information(snapshot)


def test_subtraction_and_other_hosts():
    for seed in (1, 29, 701):
        s = create_initial_state_fast_sandbox(seed=seed)
        d, definition = s.world.manifest_definition, s.world.information_definition
        original = unconfigured(s.world.narrative_snapshot)
        assert info.sampling_definition(definition) == original
        catalog = collect_catalog()
        for record in catalog["records"]:
            if record["kind"] == "locations":
                record["value"].pop("navigation_policy", None)
        assert compile_catalog(seed, catalog)[0] == replace(d, prologue_version="", prologue_identity=None,
            prologue_fallback=None, prologue_excluded=())  # Ordinary physical history unchanged.
        baseline = info.query_information(d, original, "ECHO_7")
        hosts = ["ECHO_7", "HARBOR_12", baseline.uplink[0].destination_id]
        if seed == 701:
            hosts.append(f"S+001_-001_+000:WG1_{d.scope}_0")
        frozen = pickle.dumps(s)
        for host in hosts:
            old = info.query_information(d, original, host)
            new = info.query_information(d, definition, host, include_prologue=False)
            if host == "ECHO_7":
                assert new.uplink == tuple(r for r in old.uplink if r.destination_id != "HARBOR_12")
                assert new.files == old.files  # Authored testimony/contact stays intact.
            else:
                assert replace(new, rules_key=old.rules_key) == old
            old_radio = radio.define_radio(s.world.narrative_snapshot, original)
            before = radio.query_host(d, old_radio, original, host)
            after = radio.query_host(d, s.world.radio_definition, definition, host)
            assert replace(after, rules_key=before.rules_key) == before
        assert pickle.dumps(s) == frozen
        for locale in (Locale.EN, Locale.ES):
            twin = deepcopy(s)
            twin.os.locale = locale
            output(repl.render_cat, twin, f"/remote/ECHO_7/logs/echo_cache.{locale.value}.txt")
            assert "HARBOR_12" in twin.world.known_nodes
            assert "HARBOR_12" not in twin.world.known_links["ECHO_7"]


def test_reusable_policy_files_radio_and_invalid_authoring():
    # Instrumented authored scene: no new gameplay content or seed sweep.
    s = scene([("A", "station", (1000.,1000.,1000.)), ("B", "relay", (1001.,1000.,1000.))], radio_links=())
    snap = deepcopy(s.world.narrative_snapshot)
    snap["aliases"] = {"a": "A", "b": "B", "destination": "B"}
    raw = info.define_information(snap)
    snap["locations"][0]["navigation_policy"] = dict(version=info.NAVIGATION_POLICY_VERSION, exclude_destinations=["destination"])
    filtered = info.define_information(snap)
    d = s.world.manifest_definition
    old = info.query_information(d, raw, "A")
    new = info.query_information(d, filtered, "A")
    assert [r.destination_id for r in old.uplink] == ["B"] and new.uplink == ()
    assert any(f.get("navigation_record", {}).get("destination_id") == "B" for f in old.files)
    assert new.files == [f for f in old.files if not f.get("navigation_record")]
    assert new.mail_by_locale == old.mail_by_locale
    # Force a navigation program, preserving real B1 selection/record certification.
    def draw(world, key, host, domain):
        return 0.0 if domain in {"program_exists", "navigation", "navigation_slot"} else .5
    with patch.object(radio, "_draw", side_effect=draw):
        before = radio.query_host(d, radio.define_radio(snap, raw), raw, "A")
        after = radio.query_host(d, radio.define_radio(snap, filtered), filtered, "A")
    assert before.emissions and before.navigation_record.destination_id == "B"
    assert after.emissions == () and after.navigation_record is None
    assert after.installed_t == before.installed_t and after.final_hardware == before.final_hardware
    assert after.energy_end_t == before.energy_end_t and after.failure_t == before.failure_t
    bad = [None, {}, {**POLICY, "version": "unknown"}, {**POLICY, "typo": 1},
           {**POLICY, "exclude_destinations": []}, {**POLICY, "exclude_destinations": "B"},
           {**POLICY, "exclude_destinations": [True]}, {**POLICY, "exclude_destinations": ["MISSING"]},
           {**POLICY, "exclude_destinations": ["A"]}, {**POLICY, "exclude_destinations": ["B", "destination"]}]
    for policy in bad:
        snap["locations"][0]["navigation_policy"] = policy
        try:
            info.define_information(snap)
        except ContentError as exc:
            assert "navigation_policy" in str(exc)
        else:
            raise AssertionError(policy)
    snap["locations"][0]["navigation_policy"] = dict(version=info.NAVIGATION_POLICY_VERSION, exclude_destinations=["B"])
    for text in ("LINK: A -> B", "LINK: B -> A", "LINK: B", "[INTEL] LINK: B -> A [/INTEL]"):
        snap["locations"][0]["fs_files"] = [dict(path="/logs/conflict.txt", content=text)]
        try:
            info.define_information(snap)
        except ContentError:
            pass
        else:
            raise AssertionError(text)


def command(s, engine, text):
    events = engine.apply_action(s, parse_command(text))
    elapsed = 0
    while s.jobs.active_job_ids and elapsed < 1000:
        events += engine.tick(s, 1)
        elapsed += 1
    assert not s.jobs.active_job_ids, text
    return dict(command=text, wait_seconds=elapsed, output=[e.message for e in events])


def test_normal_29_and_persistence():
    s, engine = create_initial_state_prologue(seed=29), Engine()
    journal = []
    for text in ("power off data_core", "drone deploy D1 PWR-A1"):
        journal.append(command(s, engine, text))
    for system, sector in (("power_core", "PWR-A1"), ("energy_distribution", "BUS-A2")):
        if sector != "PWR-A1":
            journal.append(command(s, engine, "drone move D1 " + sector))
        for _ in range(6):
            if s.ship.systems[system].state == SystemState.NOMINAL:
                break
            journal.append(command(s, engine, "drone repair D1 " + system))
        assert s.ship.systems[system].state == SystemState.NOMINAL
    for text in ("drone recall D1", "power on sensors", "boot sensord", "scan", "route solve ECHO_7", "nav ECHO_7"):
        journal.append(command(s, engine, text))
    assert s.ship.in_transit
    while s.ship.in_transit:
        engine.tick(s, 1)  # Controlled ordinary elapsed time, no state edits.
    for text in ("dock ECHO_7", "power plan normal", "power on data_core", "boot datad"):
        journal.append(command(s, engine, text))
    journal.append(dict(command="uplink", output=output(repl._handle_uplink, s)))
    assert "HARBOR_12" not in s.world.known_links["ECHO_7"]
    journal.append(command(s, engine, "power on drone_bay"))
    for text in ("drone deploy D1 ECHO_7", "drone salvage data D1", "drone recall D1"):
        journal.append(command(s, engine, text))
    output(repl.render_cat, s, "/remote/ECHO_7/logs/echo_cache.en.txt")
    assert "HARBOR_12" in s.world.known_nodes
    assert "HARBOR_12" not in s.world.known_links["ECHO_7"]
    with TemporaryDirectory(prefix="retorno-p1-") as folder:
        slot = Path(folder) / "new.dat"
        save_single_slot(s, slot)
        loaded = load_single_slot(slot).state
        assert loaded.world.known_links == s.world.known_links
        assert loaded.world.information_definition == s.world.information_definition
        files, links = deepcopy(loaded.os.fs), deepcopy(loaded.world.known_links)
        output(repl._handle_uplink, loaded)
        assert loaded.os.fs == files and loaded.world.known_links == links
        old_root = Path(folder) / "old-data"
        shutil.copytree(data._DATA_ROOT, old_root)
        path = old_root / "locations/echo_7.json"
        value = json.loads(path.read_text()); value["catalog_test_revision"] = "different catalogue"
        path.write_text(json.dumps(value))
        old_slot = Path(folder) / "old.dat"
        with patch.object(data, "_DATA_ROOT", old_root):
            old_state = create_initial_state_fast_sandbox(seed=29)
            assert "HARBOR_12" not in old_state.world.known_links["ECHO_7"]
            save_single_slot(old_state, old_slot)
            assert load_single_slot(old_slot).state.world.known_links == old_state.world.known_links
        content = old_slot.read_bytes()
        try:
            load_single_slot(old_slot)
        except SaveLoadError as exc:
            assert "catalog" in str(exc)
        else:
            raise AssertionError("incompatible old catalogue accepted")
        assert old_slot.read_bytes() == content
    return journal


def test_public_seed_1():
    # The historical two-uplink example is tied to the module catalogue's
    # physical fingerprint. Keep that characterization explicit while the
    # productive reserved-chain journey uses the current catalogue below.
    with TemporaryDirectory(prefix="retorno-p1-modules-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        modules = root / "modules.json"
        catalog = json.loads(modules.read_text())
        catalog.pop("engine_efficiency_upgrade_01", None)
        modules.write_text(json.dumps(catalog))
        with patch.object(data, "_DATA_ROOT", root):
            return _public_seed_1_historical_catalogue()


def _public_seed_1_historical_catalogue():
    s, engine = create_initial_state_fast_sandbox(seed=1), Engine()
    loop = GameLoop(engine, s); loop.set_auto_tick(False)
    journal = []
    assert "HARBOR_12" not in s.world.known_links["ECHO_7"]
    output(repl.render_cat, s, "/remote/ECHO_7/logs/echo_cache.en.txt")
    path = next(p for p in s.os.fs if p.startswith("/logs/nav/uplink_ECHO_7_"))
    output(repl.render_cat, s, path)
    # First destination of the acquired record, never a secret scheduler choice.
    destination = re.search(r"LINK: ECHO_7 -> (\S+)", s.os.fs[path].content)[1]
    assert destination in s.world.known_links["ECHO_7"]
    for target in (destination, "HARBOR_12"):
        journal.append(command(s, engine, "nav " + target))
        assert s.ship.in_transit
        assert repl._hibernate_blocked_message(s) is None
        result = repl._execute_hibernate(loop, (s.ship.arrival_t-s.clock.t+1)/Balance.YEAR_S)
        journal.append(dict(command="hibernate until_arrival", years=result.actual_years, wake=result.wake_reason))
        assert not s.ship.in_transit and s.world.current_node_id == target
        if target == destination:
            for text in ("dock " + target, "power plan normal", "power on data_core", "boot datad"):
                journal.append(command(s, engine, text))
            journal.append(dict(command="uplink", output=output(repl._handle_uplink, s)))
            assert "HARBOR_12" in s.world.known_links[target]
            journal.append(command(s, engine, "undock"))
    assert not s.os.debug_enabled
    return journal


def main():
    test_subtraction_and_other_hosts(); print("PASS subtraction, physical invariance, seeds 1/29/701")
    test_reusable_policy_files_radio_and_invalid_authoring(); print("PASS authored validation, files and B2 no replacement")
    normal = test_normal_29_and_persistence(); print("PASS normal 29, contact, save/load and old-catalogue rejection")
    journey = test_public_seed_1(); print("PASS public seed 1: ECHO_7 -> intermediate -> HARBOR_12")
    Path("/tmp/retorno-p1-evidence.json").write_text(json.dumps(dict(normal29=normal, public1=journey), indent=2))


if __name__ == "__main__":
    main()
