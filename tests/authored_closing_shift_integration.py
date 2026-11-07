"""C1 experimental authored story: temporary catalogue, public journey, no debug."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import io
import json
import math
from pathlib import Path
import pickle
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core import communications as radio, lore
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.os import Locale
from retorno.runtime import data_loader as data
from retorno.worldgen import generator, manifest
from retorno.worldgen.narrative import collect_catalog, compile_catalog

FIXTURE = Path(__file__).parent / "fixtures/authored_closing_shift"
ARC = "arc:experimental_closing_shift:"
SINGLE = "single:experimental_left_inventory"
STATION, RELAY, WRECK = "CLOSING_STATION", "CLOSING_RELAY", "CLOSING_WRECK"
ENGINE = Engine()


@contextmanager
def installed():
    """Append to a disposable copy; preserve all five production singles."""
    with TemporaryDirectory(prefix="retorno-c1-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        shutil.copyfile(FIXTURE / "arc.json", root / "arcs/experimental_closing_shift.json")
        index = root / "lore/singles/index.json"
        singles = json.loads(index.read_text())
        singles.append(json.loads((FIXTURE / "single.json").read_text()))
        index.write_text(json.dumps(singles), encoding="utf-8")
        texts = root / "lore/experimental_closing_shift"
        texts.mkdir()
        for path in FIXTURE.glob("*.txt"):
            shutil.copyfile(path, texts / path.name)
        with patch.object(data, "_DATA_ROOT", root):
            yield root.parent


def output(callback, *args):
    stream = io.StringIO()
    with redirect_stdout(stream):
        callback(*args)
    return stream.getvalue()


def public(state, line):
    """Use the same parser/actions and CLI handlers as the public REPL."""
    action = parse_command(line)
    if action == "UPLINK":
        return output(repl._handle_uplink, state)
    if isinstance(action, tuple):
        if action[0] == "WAIT":
            return ENGINE.tick(state, action[1])
        if action[0] == "CAT":
            return output(repl.render_cat, state, action[1])
        if action[0] == "INTEL_IMPORT":
            return output(repl._handle_intel_import, state, action[1])
        raise AssertionError(action)
    return ENGINE.apply_action(state, action)


def test_compilation_and_hidden_knowledge():
    rows = []
    with installed():
        for seed in (1, 29, 701):
            catalog = collect_catalog()
            definition, snap = compile_catalog(seed, catalog)
            catalog["records"].reverse()
            assert (definition, snap) == compile_catalog(seed, catalog)
            state = create_initial_state_prologue(seed=seed)
            assert state.world.manifest_definition == definition
            assert all(result["status"] == "certified" for result in snap["relation_results"])
            positions = snap["positions"]
            assert math.isclose(math.dist(positions[STATION], positions[RELAY]), .002)
            assert .002 <= math.dist(positions[RELAY], positions[WRECK]) <= .0031
            for ident in (STATION, RELAY, WRECK):
                assert sum(a.raw_id == ident for a in definition.authored) == 1
                assert ident not in state.world.known_nodes | state.world.known_contacts
                assert ident not in state.world.space.nodes
            frozen = pickle.dumps(state)
            def public_view(s):
                return (output(repl.render_nav_contacts, s) + output(repl.render_status, s)
                        + output(repl.render_diag, s, "comms") + output(repl.render_map_graph, s))

            public_before = public_view(state)
            assert pickle.dumps(state) == frozen
            # Hold observations constant; remove the hidden experimental data.
            twin = deepcopy(state)
            twin.world.narrative_snapshot = {}
            assert public_before == public_view(twin)
            for ident in (STATION, RELAY, WRECK):
                assert ident not in public_before
            lore.run_lore_scheduler_tick(state)
            placements = state.world.lore_placements.piece_to_node
            assert placements[ARC + "primary"] == "ECHO_7"
            assert placements[ARC + "closure"] == STATION
            assert placements[ARC + "repetition"] == RELAY
            assert placements[SINGLE] == WRECK
            # Secondary assignments precede primary delivery: no implicit gate.
            assert ARC + "primary" not in state.world.lore.delivered
            assert not any(key.startswith("lore:" + ARC) for key in state.world.radio_opportunities)
            assert not {STATION, RELAY, WRECK} & state.world.known_nodes
            assert public_before == public_view(state)
            emitter = snap["radio_emitters"]["closing-relay-archive"]
            emission = snap["radio_emissions"]["closing-archive-loop"]
            frozen = pickle.dumps(state)
            metrics = radio.radio_link_metrics(state, emitter, emission)
            assert math.isclose(metrics["distance_ly"], math.hypot(.004, .002))
            assert metrics["propagation_s"] == metrics["distance_ly"] * Balance.YEAR_S
            arrival = emission.start_t + metrics["propagation_s"]
            assert radio.radio_temporal_block_reason(state, emitter, emission, at_t=emission.start_t) == "signal_not_arrived"
            assert radio.radio_temporal_block_reason(state, emitter, emission, at_t=arrival - 1) == "signal_not_arrived"
            assert radio.radio_temporal_block_reason(state, emitter, emission, at_t=arrival) is None
            assert pickle.dumps(state) == frozen
            for entry in lore._iter_all_pieces(state):
                if entry["piece_key"] not in {ARC + "closure", ARC + "repetition", SINGLE}:
                    continue
                for lang in ("en", "es"):
                    text = lore._content_from_ref(entry["piece"]["content_ref_" + lang], state)
                    assert text.strip() and "{{" not in text
                    if entry["piece_key"] == ARC + "repetition":
                        assert "NODE: " + WRECK in text
                        assert str(positions[WRECK][0]) in text
            for ident in (STATION, RELAY, WRECK):
                generator.ensure_historical_node(state, ident)
            assert RELAY in state.world.space.nodes[STATION].links
            for ident, node in state.world.space.nodes.items():
                assert manifest.resolve_operative_id(definition, ident), ident
                for target in node.links:
                    assert manifest.resolve_operative_id(definition, target), target
            rows.append({"seed": seed, "wreck": positions[WRECK], "placements": {
                key: placements[key] for key in (ARC + "primary", ARC + "closure", ARC + "repetition", SINGLE)}})
    assert len({tuple(row["wreck"]) for row in rows}) == 3
    return rows


def test_public_journey():
    rows = []
    for locale in (Locale.EN, Locale.ES):
        with installed() as directory:
            state = create_initial_state_sandbox()
            state.os.locale = locale
            assert not state.os.debug_enabled
            transcript = []

            def do(line):
                transcript.append(line)
                result = public(state, line)
                print(line, [e.message for e in result] if isinstance(result, list) else result, flush=True)
                return result

            # From here onwards no relocation, repair, RNG, balance or pool edits.
            do("power off security")
            do("dock ECHO_7")
            do("wait 60")
            assert state.ship.docked_node_id == "ECHO_7"
            assert STATION not in state.world.known_nodes
            do("uplink")
            assert ARC + "primary" in state.world.lore.delivered
            assert STATION in state.world.known_links["ECHO_7"]
            before_repeat = deepcopy(state.world.lore.delivered)
            do("uplink")
            assert state.world.lore.delivered == before_repeat
            # B1's legitimate uplink may also disclose the nearby relay hub.
            assert WRECK not in state.world.known_nodes

            def travel(ident):
                if state.ship.docked_node_id:
                    do("undock")
                    do("wait 60")
                do("nav " + ident)
                assert state.ship.in_transit
                do(f"wait {state.ship.arrival_t - state.clock.t + 1}")
                assert state.world.current_node_id == ident

            travel(STATION)
            do("dock " + STATION)
            do("wait 60")
            do("power on drone_bay")
            do("drone deploy D1 " + STATION)
            do("wait 30")
            do("drone salvage data D1")
            do("wait 60")
            path = f"/remote/{STATION}/logs/records/closing_shift.{locale.value}.txt"
            assert path in state.os.fs
            assert ARC + "closure" in state.world.lore.delivered
            assert RELAY not in state.world.known_links.get(STATION, set())
            text = do("cat " + path)
            assert ("último turno" if locale == Locale.ES else "last shift") in text
            assert RELAY in state.world.known_links[STATION]
            do("drone recall D1")
            do("wait 60")
            do("power off data_core")
            do("power on comms")
            do("boot radiod")
            do("wait 5")
            assert not any(key.startswith("lore:" + ARC) for key in state.world.radio_opportunities)
            travel(RELAY)
            assert "lore:" + ARC + "repetition" not in state.world.radio_opportunities
            do("dock " + RELAY)
            do("wait 60")
            do("power on comms")
            do("boot radiod")
            do("wait 5")
            key = "lore:" + ARC + "repetition"
            op = state.world.radio_opportunities[key]
            assert op.status == "received", op
            assert op.emission.start_t == -Balance.YEAR_S
            metrics = radio.radio_link_metrics(state, op.emitter, op.emission)
            assert metrics["temporally_available"]
            assert op.received_t >= op.emission.start_t + metrics["propagation_s"]
            assert WRECK not in state.world.known_nodes
            slot = directory / "journey.dat"
            save_single_slot(state, slot)
            state = load_single_slot(slot).state
            assert state.world.radio_opportunities[key] == op
            do("intel import " + op.path)
            assert WRECK in state.world.known_links[RELAY]
            text = do("cat " + op.path)
            assert ("mensaje almacenado" if locale == Locale.ES else "stored message") in text
            assert state.world.radio_opportunities[key].status == "read_imported"
            travel(WRECK)
            do("dock " + WRECK)
            do("wait 60")
            do("power on drone_bay")
            do("drone deploy D1 " + WRECK)
            do("wait 30")
            do("drone salvage data D1")
            do("wait 60")
            inventory = f"/remote/{WRECK}/logs/records/left_inventory.{locale.value}.txt"
            assert inventory in state.os.fs
            text = do("cat " + inventory)
            assert ("hervidor" if locale == Locale.ES else "kettle") in text
            assert SINGLE in state.world.lore.delivered
            delivered = deepcopy(state.world.lore.delivered)
            paths = set(state.os.fs)
            do("drone salvage data D1")
            do("wait 60")
            do("cat " + inventory)
            save_single_slot(state, slot)
            state = load_single_slot(slot).state
            do("wait 5")
            assert state.world.lore.delivered == delivered
            assert {ARC + "primary", ARC + "closure", ARC + "repetition", SINGLE} <= delivered
            assert len([op for op in state.world.radio_opportunities.values()
                        if op.emission and op.emission.emission_id == "closing-archive-loop"]) == 1
            assert len([p for p in state.os.fs if p.endswith("left_inventory." + locale.value + ".txt")]) == 1
            assert set(state.os.fs) == paths
            assert not state.os.debug_enabled
            generator.validate_universe_state(state)
            for ident, node in state.world.space.nodes.items():
                assert manifest.resolve_operative_id(state.world.manifest_definition, ident)
            for origin, targets in state.world.known_links.items():
                for target in targets:
                    assert manifest.resolve_operative_id(state.world.manifest_definition, origin)
                    assert manifest.resolve_operative_id(state.world.manifest_definition, target)
                    a, b = state.world.space.nodes[origin], state.world.space.nodes[target]
                    assert math.dist((a.x_ly, a.y_ly, a.z_ly), (b.x_ly, b.y_ly, b.z_ly)) <= Balance.MAX_ROUTE_HOP_LY
            rows.append({"locale": locale.value, "seed": state.meta.rng_seed, "commands": transcript, "received_t": op.received_t,
                         "emitted_t": op.emission.start_t, "delivered": sorted(delivered)})
    return rows


def main():
    original = collect_catalog()
    assert [a["arc_id"] for a in data.load_arcs()] == ["amanecer_elena_01"] and len(data.load_singles()) == 5 and len(data.load_locations()) == 5
    evidence = {"compilation": test_compilation_and_hidden_knowledge(), "public": test_public_journey()}
    assert collect_catalog() == original
    target = Path("/tmp/retorno-c1-evidence.json")
    target.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("AUTHORED CLOSING SHIFT PASSED", target)


if __name__ == "__main__":
    main()
