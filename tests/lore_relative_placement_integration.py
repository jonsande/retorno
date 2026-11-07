"""C2a: temporary AMANECER catalogue and focused relative-placement checks."""
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

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.core import lore
from retorno.core.engine import Engine
from retorno.io.save_load import save_single_slot, load_single_slot, SaveLoadError
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.runtime import data_loader as data
from retorno.worldgen import generator
from retorno.worldgen.narrative import ContentError, collect_catalog, compile_catalog

DRAFT = Path(__file__).resolve().parents[1] / "narrative/amanecer/integration/01_elena_varela"
PREFIX = "arc:amanecer_elena_01:"
PRIMARY = PREFIX + "liria_navigation_index"


@contextmanager
def installed(mutate=None):
    with TemporaryDirectory(prefix="retorno-c2a-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        arc = json.loads((DRAFT / "amanecer_elena_01.draft.json").read_text())
        if mutate:
            mutate(arc, root)
        (root / "arcs/amanecer_elena_01.json").write_text(json.dumps(arc))
        shutil.copytree(DRAFT / "textos", root / "lore/packs/amanecer_elena_01")
        with patch.object(data, "_DATA_ROOT", root):
            yield root


def public_view(state):
    stream = io.StringIO()
    with redirect_stdout(stream):
        repl.render_status(state)
        repl.render_diag(state, "comms")
        repl.render_nav_contacts(state)
        repl.render_map_graph(state)
    return stream.getvalue()


def salvage(state, ident):
    # Same service fixture as narrative_world_integration_smoke: exercise jobs,
    # delivery and reading without claiming a complete prologue journey.
    node = state.world.space.nodes[ident]
    state.world.current_node_id = state.ship.current_node_id = ident
    state.world.current_pos_ly = (node.x_ly, node.y_ly, node.z_ly)
    state.world.known_nodes.add(ident)
    state.world.known_contacts.add(ident)
    state.ship.docked_node_id = ident
    for system in state.ship.systems.values():
        system.state, system.health, system.state_locked = SystemState.NOMINAL, 1.0, False
        if system.service:
            system.service.is_running = True
    state.ship.power.p_gen_kw = state.ship.power.p_gen_base_kw = 20
    engine = Engine()
    engine.apply_action(state, parse_command("drone deploy D1 " + ident))
    engine.tick(state, 30)
    engine.apply_action(state, parse_command("drone salvage data D1"))
    engine.tick(state, 60)
    engine.apply_action(state, parse_command("drone recall D1"))
    engine.tick(state, 60)


def test_amanecer():
    hosts = set()
    positions = set()
    for seed in (1, 29, 701):
        with installed() as root:
            state = create_initial_state_prologue(seed=seed)
            snap = state.world.narrative_snapshot
            catalog = collect_catalog()
            definition, compiled = compile_catalog(seed, catalog)
            catalog["records"].reverse()
            assert (definition, compiled) == compile_catalog(seed, catalog)
            twin = deepcopy(state)
            twin.world.narrative_snapshot = compiled
            lore.validate_essential_opportunities(twin, definition)
            assert twin.world.narrative_snapshot["reservations"] == snap["reservations"]
            positions.add(tuple(snap["positions"]["LIRIA"]))
            assert "LIRIA" not in state.world.space.nodes
            assert "LIRIA" not in state.world.known_nodes
            assert math.dist(snap["positions"]["HARBOR_12"], snap["positions"]["LIRIA"]) <= 45
            before = pickle.dumps(state)
            visible = public_view(state)
            assert pickle.dumps(state) == before
            twin = deepcopy(state)
            twin.world.narrative_snapshot = {}
            assert visible == public_view(twin)
            entries = {e["piece_key"]: e for e in lore._iter_all_pieces(state)}
            entry = entries[PRIMARY]
            before = pickle.dumps(state)
            candidates, nodes = lore._historical_candidates(state, entry, definition)
            assert pickle.dumps(state) == before
            host = snap["reservations"][PRIMARY]["node_id"]
            hosts.add(host)
            assert candidates == [host]
            unreserved = deepcopy(state)
            unreserved.world.narrative_snapshot["reservations"] = {}
            eligible, _ = lore._historical_candidates(unreserved, entry, definition)
            assert len(eligible) > 1
            assert math.dist((nodes[host].x_ly, nodes[host].y_ly, nodes[host].z_ly), snap["positions"]["LIRIA"]) <= 15
            assert lore.piece_constraints_ok(entry["piece"], lore.build_lore_context(twin, host)) is False
            lore.run_lore_scheduler_tick(state)
            assert public_view(state) == visible
            assert state.world.lore_placements.piece_to_node[PRIMARY] == host
            assert lore.build_lore_context(state, host).dist_from_origin_ly <= 30
            assert lore.piece_constraints_ok(entry["piece"], lore.build_lore_context(state, host))
            secondary = [k for k in entries if k.startswith(PREFIX) and k != PRIMARY]
            assert len(secondary) == 4
            assert all(state.world.lore_placements.piece_to_node[k] == "LIRIA" for k in secondary)
            assert tuple((state.world.space.nodes["LIRIA"].x_ly, state.world.space.nodes["LIRIA"].y_ly, state.world.space.nodes["LIRIA"].z_ly)) == tuple(snap["positions"]["LIRIA"])
            slot = root.parent / "test.dat"
            save_single_slot(state, slot)
            loaded = load_single_slot(slot).state
            assert loaded.world.narrative_snapshot == snap
            assert loaded.world.lore_placements == state.world.lore_placements
            for locale in (Locale.EN, Locale.ES):
                s = deepcopy(loaded)
                s.os.locale = locale
                # Scheduler-created files retain the locale at assignment.
                s.world.lore_placements.piece_to_node.clear()
                s.world.arc_placements.clear()
                for pool in s.world.node_pools.values():
                    pool.injected_files.clear()
                lore.run_lore_scheduler_tick(s)
                salvage(s, host)
                path = f"/remote/{host}/logs/navigation/amanecer_liria_route.{locale.value}.txt"
                assert path in s.os.fs
                assert "LIRIA" not in s.world.known_nodes
                with redirect_stdout(io.StringIO()):
                    repl.render_cat(s, path)
                assert "LIRIA" in s.world.known_links["HARBOR_12"]
                salvage(s, "LIRIA")
                for key in secondary:
                    piece = entries[key]["piece"]
                    path = "/remote/LIRIA" + piece["path_template"].format(lang=locale.value)
                    assert path in s.os.fs
                    expected = lore._content_from_ref(piece["content_ref_" + locale.value], s)
                    assert s.os.fs[path].content == expected
                    with redirect_stdout(io.StringIO()):
                        repl.render_cat(s, path)
                assert set(secondary + [PRIMARY]) <= s.world.lore.delivered
                save_single_slot(s, slot)
                assert load_single_slot(slot).state.world.lore.delivered == s.world.lore.delivered
            arc_path = root / "arcs/amanecer_elena_01.json"
            arc_path.write_text(arc_path.read_text() + " ")
            # Whitespace is immaterial; a semantic catalogue change is rejected.
            value = json.loads(arc_path.read_text())
            value["primary_intel"]["constraints"]["anchor_distances"][0]["max_ly"] = 14
            arc_path.write_text(json.dumps(value))
            try:
                load_single_slot(slot)
            except SaveLoadError:
                pass
            else:
                raise AssertionError("changed catalogue accepted")
    assert len(positions) == 3
    assert len(hosts) > 1, hosts
    print("AMANECER hosts", sorted(hosts))


def test_validation_and_geometry():
    bad = [None, {}, [], True, "LIRIA", [None], [{}], [{"anchor": "LIRIA"}],
           [{"anchor": "NO_SUCH_ID", "max_ly": 1}],
           [{"anchor": "procedural_station", "max_ly": 1}],
           [{"anchor": "RETORNO_SHIP", "max_ly": 1}],
           [{"anchor": [], "max_ly": 1}]]
    for bound in (True, -1, "1", None, float("nan"), float("inf")):
        bad.append([{"anchor": "LIRIA", "max_ly": bound}])
    bad += [[{"anchor": "LIRIA", "min_ly": 2, "max_ly": 1}],
            [{"anchor": "LIRIA", "max_ly": 1, "typo": 0}]]
    for value in bad:
        def mutate(arc, root):
            arc["primary_intel"]["constraints"]["anchor_distances"] = value
            arc["primary_intel"]["force"] = False
        with installed(mutate):
            try:
                create_initial_state_prologue(seed=1)
            except ContentError as exc:
                assert "anchor_distances" in str(exc)
            else:
                raise AssertionError(value)
    for mode in (None, "unknown", True, []):
        with installed(lambda arc, root: arc["placement_rules"]["primary"].update(host_selection=mode)):
            try:
                create_initial_state_prologue(seed=1)
            except ContentError as exc:
                assert "host_selection" in str(exc)
            else:
                raise AssertionError(mode)
    with installed():
        state = create_initial_state_prologue(seed=1)
        xyz = state.world.narrative_snapshot["positions"]["LIRIA"]
        node = state.world.space.nodes["HARBOR_12"]
        node.x_ly, node.y_ly, node.z_ly = xyz[0], xyz[1], xyz[2] + 5
        ctx = lore.build_lore_context(state, "HARBOR_12")
        rule = {"anchor": "Liria Civil Station", "min_ly": 5, "max_ly": 5}
        piece = {"constraints": {"anchor_distances": [rule]}}
        assert lore.piece_constraints_ok(piece, ctx)
        piece["constraints"]["anchor_distances"].append({"anchor": "HARBOR_12", "max_ly": ctx.anchor_distances["harbor_12"] + 10})
        assert lore.piece_constraints_ok(piece, ctx)
        for distance, expected in ((4, False), (5, True), (6, False)):
            node.z_ly = xyz[2] + distance
            assert lore.piece_constraints_ok(piece, lore.build_lore_context(state, "HARBOR_12")) == expected
        piece["constraints"]["anchor_distances"].append({"anchor": "LIRIA", "max_ly": 4})
        assert not lore.piece_constraints_ok(piece, ctx)


def test_optional_single_default_and_reservation():
    def mutate(arc, root):
        arc["placement_rules"]["primary"].pop("host_selection")
        arc["placement_rules"]["primary"]["candidates"] = ["HARBOR_12", "ECHO_7"]
        arc["primary_intel"].pop("constraints")
        doc = arc["secondary_lore_docs"][0]
        doc["force"] = False
        doc["constraints"] = {"anchor_distances": [{"anchor": "liria civil station", "max_ly": 0}]}
        index = root / "lore/singles/index.json"
        singles = json.loads(index.read_text())
        singles.append(dict(single_id="c2a_optional", channels=["salvage_data"],
                            constraints=deepcopy(doc["constraints"]),
                            path_template="/data/c2a_optional.{lang}.txt",
                            content_ref_en="lore/packs/amanecer_elena_01/elena_01_escotilla_h3.en.txt",
                            content_ref_es="lore/packs/amanecer_elena_01/elena_01_escotilla_h3.es.txt"))
        index.write_text(json.dumps(singles))
    with installed(mutate):
        state = create_initial_state_prologue(seed=1)
        snap = state.world.narrative_snapshot
        assert snap["reservations"][PRIMARY]["node_id"] == "ECHO_7"
        entries = {e["piece_key"]: e for e in lore._iter_all_pieces(state)}
        lore._evaluate_forced_pieces(state, [entries[PREFIX + "elena_02_diecinueve_personas"]])
        generator.ensure_historical_node(state, "HARBOR_12")
        generator.ensure_historical_node(state, "ECHO_7")
        lore.sync_node_pools_for_known_nodes(state)
        assert not lore._assign_piece_to_node(state, entries[PRIMARY], "HARBOR_12")
        state.world.node_pools.setdefault("ECHO_7", lore.NodePoolState()).window_open = False
        lore._evaluate_forced_pieces(state, [entries[PRIMARY]])
        assert PRIMARY not in state.world.lore_placements.piece_to_node
        optional = [entries[PREFIX + "elena_01_escotilla_h3"], entries["single:c2a_optional"]]
        before = pickle.dumps(state)
        for entry in optional:
            assert lore._candidate_nodes_for_piece(state, entry) == ["LIRIA"]
        assert pickle.dumps(state) == before
        with patch.object(lore, "_non_forced_piece_probability", return_value=1):
            lore._evaluate_non_forced_pieces(state, optional)
        assert all(state.world.lore_placements.piece_to_node[e["piece_key"]] == "LIRIA" for e in optional)
    def bad_single(arc, root):
        index = root / "lore/singles/index.json"
        values = json.loads(index.read_text())
        values[0]["constraints"] = {"anchor_distances": []}
        index.write_text(json.dumps(values))
    with installed(bad_single):
        try:
            create_initial_state_prologue(seed=1)
        except ContentError as exc:
            assert "single:" in str(exc) and "anchor_distances" in str(exc)
        else:
            raise AssertionError("invalid optional single accepted")


if __name__ == "__main__":
    original_catalog = collect_catalog()
    test_validation_and_geometry()
    test_optional_single_default_and_reservation()
    test_amanecer()
    assert collect_catalog() == original_catalog
    print("RELATIVE PLACEMENT PASSED")
