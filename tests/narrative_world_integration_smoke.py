"""4D-3e4: optional on-disk packages through real bootstrap/runtime/save paths."""
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

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core import lore
from retorno.io.save_load import SaveLoadError, load_single_slot, save_single_slot
from retorno.model.os import FSNode, FSNodeType, AccessLevel, Locale
from retorno.model.systems import SystemState
from retorno.model.world import sector_id_for_pos, region_for_pos
from retorno.runtime import data_loader as data
from retorno.worldgen import generator as gen, manifest as m
from retorno.worldgen.narrative import ContentError, collect_catalog, compile_catalog

FIXTURES = Path(__file__).parent / "fixtures/narrative_world"
KEY = "arc:synthetic_alpha:primary"


def _radio_at_host(state, node_id):
    """e4b fixture: push delivery now requires a real local, powered receiver."""
    state.world.current_node_id = state.ship.current_node_id = node_id
    state.ship.docked_node_id = node_id
    state.ship.power.power_quality = 1
    state.ship.power.brownout = False
    for ident in ("comms", "energy_distribution"):
        system = state.ship.systems[ident]
        system.state = SystemState.NOMINAL
        system.health = .9
        system.forced_offline = False
    state.ship.systems["comms"].service.is_running = True


@contextmanager
def installed(*, reverse=False, mutate=None):
    with TemporaryDirectory(prefix="retorno-narrative-") as directory:
        root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, root)
        alpha = json.loads((FIXTURES / "alpha.json").read_text())
        beta = json.loads((FIXTURES / "beta.json").read_text())
        if mutate:
            mutate(alpha, beta)
        arc_path = root / "arcs" / ("z_alpha.json" if reverse else "a_alpha.json")
        arc_path.write_text(json.dumps(alpha))
        index = root / "lore/singles/index.json"
        # Keep only the two optional synthetic packages; production singles
        # are verified separately with the untouched catalogue.
        index.write_text(json.dumps([beta]))
        for package in ("alpha", "beta"):
            for lang in ("en", "es"):
                shutil.copyfile(FIXTURES / f"{package}.{lang}.txt", root / "lore" / f"synthetic_{package}.{lang}.txt")
        with patch.object(data, "_DATA_ROOT", root):
            yield root


def import_text(state, text, *, explicit=False):
    path = "/logs/nav/narrative_test.txt"
    state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=text, access=AccessLevel.GUEST)
    with redirect_stdout(io.StringIO()):
        if explicit:
            repl._handle_intel_import(state, path)
        else:
            repl.render_cat(state, path)


def expect_error(callback, status=None, field=None):
    try:
        callback()
    except ContentError as exc:
        if status:
            assert exc.status == status, str(exc)
        if field:
            assert field in str(exc), str(exc)
        return str(exc)
    raise AssertionError("Expected an actionable content diagnostic")


def test_01_bootstrap_identity_and_no_secret_revelation():
    with installed():
        s = create_initial_state_prologue(seed=1)
        snap = s.world.narrative_snapshot
        assert s.world.manifest_definition.narrative_key == snap["catalog_key"]
        assert snap["reservations"][KEY]["node_id"] == "TEST_HOST"
        for ident in ("TEST_HOST", "TEST_STATION", "TEST_WRECK", "TEST_RELAY"):
            assert ident not in s.world.space.nodes
            assert ident not in s.world.known_nodes | s.world.known_contacts
            assert sum(a.raw_id == ident for a in s.world.manifest_definition.authored) == 1
        assert "NEVER_EXISTED" not in snap["positions"]
        assert "RETORNO_SHIP" not in {a.raw_id for a in s.world.manifest_definition.authored}
        assert {"UNKNOWN", "ECHO_7", "HARBOR_12", "ARCHIVE_01"} <= set(s.world.space.nodes)


def test_02_order_and_pure_queries():
    with installed():
        c = collect_catalog()
        a, sa = compile_catalog(29, c)
        c["records"].reverse()
        b, sb = compile_catalog(29, c)
        assert a == b and sa == sb
        s = create_initial_state_prologue(seed=29)
        before = pickle.dumps(s)
        for pos in sa["positions"].values():
            m.query_manifest(a, [sector_id_for_pos(*pos)])
        assert pickle.dumps(s) == before
        first, second = deepcopy(s), deepcopy(s)
        ids = ["TEST_STATION", "TEST_WRECK", "TEST_HOST", "TEST_RELAY"]
        for ident in ids:
            assert gen.ensure_historical_node(first, ident)
        for ident in reversed(ids):
            assert gen.ensure_historical_node(second, ident)
        assert first.world == second.world


def test_03_seed_variability_and_bound_clues():
    rows = []
    with installed():
        for seed in range(8):
            s = create_initial_state_prologue(seed=seed)
            snap = s.world.narrative_snapshot
            station, wreck = (snap["positions"][i] for i in ("TEST_STATION", "TEST_WRECK"))
            distance = math.dist(station, wreck)
            assert 0.5 <= distance <= 1.2
            piece = lore._iter_all_pieces(s)[0]["piece"]
            text = lore._content_from_ref(piece["content_ref_en"], s)
            assert f"SECTOR: {sector_id_for_pos(*wreck)}" in text
            assert "{{" not in text and "NODE: TEST_WRECK" in text
            assert "TEST_WRECK" not in s.world.known_nodes
            rows.append(dict(seed=seed, station=station, wreck=wreck, distance_ly=distance,
                sector=sector_id_for_pos(*station), region=region_for_pos(*station)))
        assert len({tuple(r["station"]) for r in rows}) == 8
        assert {r["region"] for r in rows} == {"disk", "halo"}
    return rows


def test_04_forced_host_delivery_salvage_and_reading():
    for locale in (Locale.EN, Locale.ES):
        with installed():
            s = create_initial_state_prologue(seed=2)
            s.os.locale = locale
            original = s.world.manifest_definition
            with patch.object(lore, "register_hidden_anchored_node", side_effect=AssertionError("historical fabrication")):
                lore.run_lore_scheduler_tick(s)
            assert s.world.manifest_definition == original
            assert s.world.lore_placements.piece_to_node[KEY] == "TEST_HOST"
            host = s.world.space.nodes["TEST_HOST"]
            assert host.historical_key == s.world.narrative_snapshot["reservations"][KEY]["historical_key"]
            assert "TEST_HOST" not in s.world.known_nodes
            assert "TEST_WRECK" not in s.world.space.nodes
            # Prepare ship service gates; exercise real salvage jobs and parser.
            s.world.current_node_id = s.ship.current_node_id = "TEST_HOST"
            s.world.current_pos_ly = (host.x_ly, host.y_ly, host.z_ly)
            s.world.known_nodes.add("TEST_HOST")
            s.world.known_contacts.add("TEST_HOST")
            s.ship.docked_node_id = "TEST_HOST"
            for system in s.ship.systems.values():
                system.state, system.health, system.state_locked = SystemState.NOMINAL, 1.0, False
                if system.service:
                    system.service.is_running = True
            s.ship.power.p_gen_kw = s.ship.power.p_gen_base_kw = 20
            engine = Engine()
            engine.apply_action(s, parse_command("drone deploy D1 TEST_HOST"))
            engine.tick(s, 30)
            engine.apply_action(s, parse_command("drone salvage data D1"))
            events = engine.tick(s, 60)
            path = f"/remote/TEST_HOST/logs/records/synthetic_alpha.{locale.value}.txt"
            assert path in s.os.fs, [e.message for e in events]
            assert KEY in s.world.lore.delivered
            assert "TEST_WRECK" not in s.world.known_nodes
            with redirect_stdout(io.StringIO()):
                repl.render_cat(s, path)
            assert "TEST_WRECK" in s.world.known_nodes
            assert "TEST_RELAY" in s.world.known_links["TEST_HOST"]
            assert "NEVER_EXISTED" not in s.world.known_nodes | set(s.world.space.nodes)
            gen.validate_universe_state(s)


def test_05_optional_probability_delivery_and_no_physical_dependency():
    with installed():
        s = create_initial_state_prologue(seed=3)
        lore.run_lore_scheduler_tick(s)
        single = next(p for p in lore._iter_all_pieces(s) if p["role"] == "single")
        assert math.isclose(lore._non_forced_piece_probability(single), 0.02)
        with patch.object(Balance, "LORE_NON_FORCED_INJECT_P", 0):
            for seq in range(10):
                s.world.lore_placements.eval_seq = seq
                lore._evaluate_non_forced_pieces(s, [single])
        assert "single:synthetic_beta" not in s.world.lore_placements.piece_to_node
        assert m.resolve_operative_id(s.world.manifest_definition, "TEST_WRECK")
        initial_positions = deepcopy(s.world.narrative_snapshot["positions"])
        # A controlled successful roll tests the normal binding/delivery path;
        # the default probability itself is checked above, without changing data.
        with patch.object(Balance, "LORE_NON_FORCED_INJECT_P", 1):
            single["piece"]["weight"] = 1
            lore._evaluate_non_forced_pieces(s, [single])
        key = "single:synthetic_beta"
        node_id = s.world.lore_placements.piece_to_node[key]
        _radio_at_host(s, node_id)
        delivery = lore.maybe_deliver_lore(s, "dock", lore.build_lore_context(s, node_id))
        assert delivery.applied and delivery.events
        signal_path = delivery.events[0].data["path"]
        before = set(s.world.known_nodes)
        with redirect_stdout(io.StringIO()):
            repl.render_cat(s, signal_path)
        assert before == s.world.known_nodes
        assert s.world.narrative_snapshot["positions"] == initial_positions


def test_06_pool_exhaustion_and_deadline_never_reopen():
    def deadline(alpha, beta):
        alpha["primary_intel"].update(force_policy="deadline", force_deadline={"max_docks": 4})
    with installed(mutate=deadline):
        s = create_initial_state_prologue(seed=5)
        gen.ensure_historical_node(s, "TEST_HOST")
        s.world.known_nodes.add("TEST_HOST")
        lore.sync_node_pools_for_known_nodes(s)
        pool = s.world.node_pools["TEST_HOST"]
        pool.window_open = False
        pool.uplink_data_consumed = True
        pool.base_files.clear()
        lore.recompute_node_completion(s, "TEST_HOST")
        assert pool.node_cleaned
        saved_pool = pickle.dumps(pool)
        s.world.lore.counters["dock_count"] = 4
        for _ in range(3):
            lore.run_lore_scheduler_tick(s)
        assert KEY not in s.world.lore_placements.piece_to_node
        assert pickle.dumps(pool) == saved_pool


def test_07_intel_public_formats_and_pending_references():
    for explicit in (False, True):
        with installed():
            s = create_initial_state_prologue(seed=6)
            before = deepcopy(s.world)
            import_text(s, "A rumour mentions Horizon, Test Wreck and NEVER_EXISTED.", explicit=explicit)
            assert s.world == before
            import_text(s, "NODE: Lost Test Ship\nNODE: FALSE_SITE\nNODE: PENDING_SITE", explicit=explicit)
            assert "TEST_WRECK" in s.world.known_nodes and "TEST_WRECK" in s.world.space.nodes
            assert "FALSE_SITE" not in s.world.space.nodes and "PENDING_SITE" not in s.world.space.nodes
            import_text(s, "LINK: TEST_HOST -> TEST_RELAY\nLINK: TEST_HOST -> FALSE_SITE\nLINK: TEST_HOST -> TEST_STATION", explicit=explicit)
            assert "TEST_RELAY" in s.world.known_links["TEST_HOST"]
            assert not {"FALSE_SITE", "TEST_STATION"} & s.world.known_links["TEST_HOST"]
            assert any(i.kind == "link" and i.to_id == "FALSE_SITE" for i in s.world.intel)
            sector = "S+030_+040_+000"
            before_nodes = set(s.world.known_nodes)
            import_text(s, f"SECTOR: {sector}\nCOORD: 13, 14, 15", explicit=explicit)
            new = s.world.known_nodes - before_nodes
            assert len(new) == 1 and s.world.space.nodes[next(iter(new))].kind == "nav_point"
            assert s.world.known_intel[sector]["sector"]
            import_text(s, "[INTEL]Horizon[/INTEL]", explicit=explicit)
            assert "TEST_STATION" in s.world.known_nodes
            counter = s.meta.rng_counter
            import_text(s, "[INTEL]\nNODE: TEST_RELAY\nCOORD: 14, 15, 16\nSECTOR: S+030_+041_+000\n[/INTEL]", explicit=explicit)
            assert s.meta.rng_counter == counter
            assert "TEST_RELAY" in s.world.known_nodes


def test_08_repeated_saves_and_catalog_changes():
    with installed() as root:
        s = create_initial_state_prologue(seed=7)
        lore.run_lore_scheduler_tick(s)
        import_text(s, "NODE: TEST_HOST\nLINK: TEST_HOST -> TEST_RELAY")
        slot = root.parent / "save.dat"
        for _ in range(3):
            before = deepcopy(s.world)
            save_single_slot(s, slot)
            s = load_single_slot(slot).state
            assert s.world == before
        original = slot.read_bytes()
        content = root / "lore/synthetic_alpha.en.txt"
        previous = content.read_text()
        content.write_text("A different identity.")
        try:
            load_single_slot(slot)
        except SaveLoadError as exc:
            assert "catalog" in str(exc)
        else:
            raise AssertionError("Changed package must not reinterpret the save")
        assert slot.read_bytes() == original
        # Already running games still read their frozen compiled text.
        piece = lore._iter_all_pieces(s)[0]["piece"]
        assert "A different identity" not in lore._content_from_ref(piece["content_ref_en"], s)
        content.write_text(previous)
        assert load_single_slot(slot)
        (root / "arcs/a_alpha.json").unlink()
        try:
            load_single_slot(slot)
        except SaveLoadError:
            pass
        else:
            raise AssertionError("Removed package accepted")


def test_09_negative_declarations():
    cases = []
    def duplicate(a, b):
        b["world_requirements"]["entities"].append(deepcopy(a["world_requirements"]["entities"][0]))
    cases.append((duplicate, "invalid", "duplicate physical"))
    def ambiguous(a, b):
        b["world_requirements"]["entities"][0]["aliases"] = ["Horizon"]
    cases.append((ambiguous, "invalid", "ambiguous"))
    def absent(a, b):
        a["world_requirements"]["references"].append("MISSING_ENTITY")
    cases.append((absent, "invalid", "references"))
    def wrong_kind(a, b):
        b["world_requirements"]["relations"][1]["to_kind"] = "ship"
    cases.append((wrong_kind, "invalid", "to_kind"))
    def impossible(a, b):
        b["world_requirements"]["relations"][0].update(min_ly=4, max_ly=2)
    cases.append((impossible, "unsatisfiable", "distance"))
    def route_cap(a, b):
        b["world_requirements"]["relations"][1]["to"] = "TEST_STATION"
        b["world_requirements"]["relations"][1]["to_kind"] = "station"
    cases.append((route_cap, "not_evaluated", "relations"))
    def no_host(a, b):
        a["placement_rules"]["primary"]["candidates"] = ["NO_SUCH_HOST"]
    cases.append((no_host, "unsatisfiable", "host/channels"))
    def no_channel(a, b):
        a["primary_intel"]["allowed_channels"] = ["radiod"]
    cases.append((no_channel, "unsatisfiable", "host/channels"))
    def missing_text(a, b):
        a["primary_intel"]["content_ref_en"] = "lore/missing.txt"
    cases.append((missing_text, "invalid", "content_ref_en"))
    diagnostics = []
    for mutate, status, field in cases:
        with installed(mutate=mutate):
            diagnostics.append(expect_error(lambda: create_initial_state_prologue(seed=1), status, field))
    with installed():
        diagnostics.append(expect_error(lambda: compile_catalog(1, search_budget=0), "not_evaluated", "budget"))
    return diagnostics


def test_10_current_catalogue_and_impact_measurement():
    assert data.load_arcs() == [] and len(data.load_singles()) == 5
    assert len(data.load_locations()) == 5
    baseline = {seed: m.define_manifest(seed) for seed in range(4)}
    rows = []
    with installed():
        for seed in range(4):
            definition, snap = compile_catalog(seed)
            sectors = sorted({sector_id_for_pos(*p) for i, p in snap["positions"].items() if i.startswith("TEST_")})
            def stats(d):
                r = m.query_manifest(d, sectors)
                ids = {s.identity for c in r.sectors for s in c.sites}
                adjacency = {i: set() for i in ids}
                for e in r.edges:
                    if e.left in ids and e.right in ids:
                        adjacency[e.left].add(e.right)
                        adjacency[e.right].add(e.left)
                components, seen = 0, set()
                for ident in sorted(ids):
                    if ident in seen:
                        continue
                    components += 1
                    pending = [ident]
                    while pending:
                        current = pending.pop()
                        if current not in seen:
                            seen.add(current)
                            pending.extend(adjacency[current] - seen)
                return dict(sites=sum(len(c.sites) for c in r.sectors),
                    procedural=sum(s.identity.namespace == "procedural" for c in r.sectors for s in c.sites),
                    hubs=sum(s.is_hub for c in r.sectors for s in c.sites), edges=len(r.edges),
                    sectors=len(sectors), components_induced=components,
                    isolated_sites_induced=sum(not neighbors for neighbors in adjacency.values()),
                    edges_induced=sum(len(neighbors) for neighbors in adjacency.values()) // 2)
            rows.append(dict(seed=seed, baseline=stats(baseline[seed]), installed=stats(definition)))
    return rows


def test_11_near_is_not_a_connection_and_required_link_rejected():
    def vertical(alpha, beta):
        beta["world_requirements"]["entities"][0]["position"] = {"fixed_ly": [26, 27, 11]}
        beta["world_requirements"]["relations"][0].update(**{"from": "TEST_HOST", "min_ly": 10, "max_ly": 10})
    with installed(mutate=vertical):
        s = create_initial_state_prologue(seed=0)
        gen.ensure_historical_node(s, "TEST_WRECK")
        gen.ensure_historical_node(s, "TEST_HOST")
        assert "TEST_WRECK" not in s.world.space.nodes["TEST_HOST"].links
        assert math.dist(s.world.narrative_snapshot["positions"]["TEST_HOST"], s.world.narrative_snapshot["positions"]["TEST_WRECK"]) == 10
        assert "TEST_WRECK" not in s.world.known_nodes
    def demand(alpha, beta):
        vertical(alpha, beta)
        beta["world_requirements"]["relations"].append({"type": "physical_link", "from": "TEST_HOST", "to": "TEST_WRECK"})
    with installed(mutate=demand):
        expect_error(lambda: create_initial_state_prologue(seed=0), "not_evaluated", "relations")
    def fixed_cap(alpha, beta):
        beta["world_requirements"]["entities"][1]["position"] = {"fixed_ly": [90, 27, 1]}
    with installed(mutate=fixed_cap):
        expect_error(lambda: create_initial_state_prologue(seed=0), "unsatisfiable", "physical_link")


def test_12_corrupt_intel_is_uncertain_and_never_fabricates():
    with installed():
        s = create_initial_state_prologue(seed=0)
        definition = s.world.manifest_definition
        with patch.object(lore, "register_hidden_anchored_node", side_effect=AssertionError("fabrication")):
            import_text(s, "[INTEL]UNRESOLVED_RUMOR[/INTEL]")
        assert s.world.manifest_definition == definition
        assert "UNRESOLVED_RUMOR" not in s.world.space.nodes
        assert any(i.to_id == "UNRESOLVED_RUMOR" and i.confidence == 0 for i in s.world.intel)
        for nid, node in s.world.space.nodes.items():
            assert m.resolve_operative_id(definition, nid), nid


def test_13_local_file_bindings_and_compilation_failures():
    with installed() as root:
        loc = {"node": {"node_id": "TEST_FILE_HOST", "name": "File Host", "kind": "derelict", "x_ly": 33},
            "fs_files": [{"path": "/logs/coords.txt", "content_ref": "lore/local.txt", "spatial_bindings": {
                "version": "narrative-world-v1", "values": {"dest": {"entity": "TEST_WRECK", "field": "sector"}}}}]}
        (root / "locations/file_host.json").write_text(json.dumps(loc))
        (root / "lore/local.txt").write_text("SECTOR: {{dest}}")
        s = create_initial_state_prologue(seed=0)
        files = lore._location_fs_files("TEST_FILE_HOST", s)
        assert files[0]["content"] == "SECTOR: " + sector_id_for_pos(*s.world.narrative_snapshot["positions"]["TEST_WRECK"])
    def bad_version(a, b):
        a["world_requirements"]["version"] = "future-version"
    with installed(mutate=bad_version):
        expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "version")
    def bad_binding(a, b):
        a["primary_intel"]["spatial_bindings"]["values"]["wreck_sector"]["entity"] = "ABSENT"
    with installed(mutate=bad_binding):
        expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "binding.entity")
    def cyclic(a, b):
        a["world_requirements"]["entities"][1]["position"] = {"offset_from": "TEST_WRECK", "offset_box_ly": [[0, 1], [0, 1], [0, 1]]}
    with installed(mutate=cyclic):
        expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "cyclic")


def test_14_all_existing_push_channels_keep_reading_separate():
    for channel, trigger in (("captured_signal", "dock"), ("ship_os_mail", "dock"), ("station_broadcast", "dock"), ("uplink_only", "uplink")):
        def configure(alpha, beta):
            alpha["primary_intel"]["allowed_channels"] = [channel]
        with installed(mutate=configure):
            s = create_initial_state_prologue(seed=0)
            lore.run_lore_scheduler_tick(s)
            _radio_at_host(s, "TEST_HOST")
            delivery = lore.maybe_deliver_lore(s, trigger, lore.build_lore_context(s, "TEST_HOST"))
            assert delivery.applied and KEY in s.world.lore.delivered
            if channel == "uplink_only":
                assert "TEST_RELAY" in s.world.known_links["TEST_HOST"]
            else:
                assert "TEST_WRECK" not in s.world.known_nodes
                with redirect_stdout(io.StringIO()):
                    repl.render_cat(s, delivery.events[0].data["path"])
                assert "TEST_WRECK" in s.world.known_nodes


def test_15_essential_document_reserved_on_empty_wreck():
    def wreck_host(alpha, beta):
        alpha["placement_rules"]["primary"] = {"candidates": ["TEST_WRECK"], "require_kind_any": ["ship"]}
    with installed(mutate=wreck_host):
        s = create_initial_state_prologue(seed=0)
        lore.run_lore_scheduler_tick(s)
        assert s.world.lore_placements.piece_to_node[KEY] == "TEST_WRECK"
        pool = s.world.node_pools["TEST_WRECK"]
        assert pool.injected_files and not pool.node_cleaned
        assert "TEST_WRECK" not in s.world.known_nodes


def test_16_protected_alias_and_natural_discovery_exceptions():
    def alias_target(alpha, beta):
        alpha["primary_intel"].update(kind="node", line="NODE: Lost Test Ship")
    with installed(mutate=alias_target):
        s = create_initial_state_prologue(seed=0)
        assert "TEST_WRECK" in lore._locked_primary_targets(s)
        assert "TEST_WRECK" in repl._locked_primary_targets(s)
        # Explicit valid intel remains a deliberate protection bypass.
        import_text(s, "NODE: Lost Test Ship")
        assert "TEST_WRECK" in s.world.known_nodes


def test_17_unbound_tokens_and_legacy_save_rejection():
    with installed() as root:
        text = root / "lore/synthetic_alpha.en.txt"
        text.write_text(text.read_text() + "\n{{not_bound}}")
        expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "unbound")
    with installed() as root:
        s = create_initial_state_prologue(seed=0)
        s.world.narrative_snapshot = {}
        slot = root.parent / "old.dat"
        try:
            save_single_slot(s, slot)
        except SaveLoadError as exc:
            assert "snapshot" in str(exc)
        else:
            raise AssertionError("Unpinned narrative save was written")
        assert not slot.exists()


def test_18_essential_file_path_must_be_recoverable():
    def outside_mount(alpha, beta):
        alpha["primary_intel"]["path_template"] = "/unmounted/piece.{lang}.txt"
    with installed(mutate=outside_mount):
        expect_error(lambda: create_initial_state_prologue(seed=0), "unsatisfiable", "file paths")


def test_19_reserved_tokens_are_validated_without_bindings():
    cases = ("line", "content", "content_ref_en", "content_ref_es",
             "files.content", "files.content_ref_en", "authored.content", "authored.content_ref")
    for field in cases:
        with installed() as root:
            path = root / "arcs/a_alpha.json"
            alpha = json.loads(path.read_text())
            piece = alpha["primary_intel"]
            piece.pop("spatial_bindings")
            piece["force"] = False  # Optional content must also reject unbound tokens.
            for lang in ("en", "es"):
                (root / f"lore/synthetic_alpha.{lang}.txt").write_text("Ordinary prose.")
            expected_source, expected_field = "arcs/a_alpha.json", "primary_intel." + field
            if field.startswith("authored."):
                key = field.split(".", 1)[1]
                file_entry = {"path": "/logs/token.txt", key: "{{missing_9}}"}
                if key == "content_ref":
                    (root / "lore/token.txt").write_text("{{missing_9}}")
                    file_entry[key] = "lore/token.txt"
                location = {"node": {"node_id": "TOKEN_HOST", "kind": "derelict"}, "fs_files": [file_entry]}
                (root / "locations/token_host.json").write_text(json.dumps(location))
                expected_source, expected_field = "locations/token_host.json", "fs_files[0]." + key
            elif field.startswith("files."):
                key = field.split(".", 1)[1]
                entry = {key: "{{missing_9}}"}
                if key == "content_ref_en":
                    (root / "lore/token.txt").write_text("{{missing_9}}")
                    entry[key] = "lore/token.txt"
                piece["files"] = [entry]
                expected_field = "primary_intel.files[0]." + key
            elif field.startswith("content_ref_"):
                (root / piece[field]).write_text("{{missing_9}}")
            else:
                piece[field] = "{{missing_9}}"
            path.write_text(json.dumps(alpha))
            try:
                create_initial_state_prologue(seed=0)
            except ContentError as exc:
                assert exc.status == "invalid"
                assert expected_source in exc.source, str(exc)
                assert expected_field in exc.field, str(exc)
                assert "missing_9" in str(exc)
                if "content_ref" in field:
                    expected_ref = "lore/token.txt" if "." in field else piece[field]
                    assert expected_ref in str(exc), str(exc)
            else:
                raise AssertionError(f"Unbound token accepted in {field}")

    # Existing bindings reject unknown tokens; valid bindings compile normally.
    with installed() as root:
        text = root / "lore/synthetic_alpha.en.txt"
        text.write_text("{{unknown_token}}")
        expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "unknown_token")
    with installed():
        s = create_initial_state_prologue(seed=0)
        piece = lore._iter_all_pieces(s)[0]["piece"]
        content = lore._content_from_ref(piece["content_ref_en"], s)
        assert "{{" not in content and "NODE: TEST_WRECK" in content

    # This is the same reserved grammar, not a general parser for literal braces.
    literal = "Horizon {lang} {{UPPER}} {{two words}} {{hyphen-name}} {{9start}} {{}} [SECTOR_VAELOR]"
    def no_binding(alpha, beta):
        alpha["primary_intel"].pop("spatial_bindings")
    with installed(mutate=no_binding) as root:
        for lang in ("en", "es"):
            (root / f"lore/synthetic_alpha.{lang}.txt").write_text(literal)
        s = create_initial_state_prologue(seed=0)
        assert literal == lore._content_from_ref("lore/synthetic_alpha.en.txt", s)
        assert "TEST_STATION" not in s.world.known_nodes
        # The check also runs with no physical declarations anywhere.
        (root / "arcs/a_alpha.json").write_text(json.dumps({"arc_id": "legacy_token", "primary_intel": {"line": "{{missing}}"}}))
        (root / "lore/singles/index.json").write_text("[]")
        expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "primary_intel.line")


def test_20_essential_payload_matches_real_delivery_and_language_fallback():
    channels = ("salvage_data", "ship_os_mail", "captured_signal", "station_broadcast")
    scenarios = ("absent", "empty", "whitespace", "headers_only", "empty_es", "valid", "en_fallback", "es_only", "line_only", "empty_with_line", "whitespace_with_line", "missing_file")
    for channel in channels:
        for scenario in scenarios:
            def configure(alpha, beta):
                piece = alpha["primary_intel"]
                piece.pop("spatial_bindings")
                piece.pop("line")
                piece["allowed_channels"] = [channel]
                if scenario in {"absent", "headers_only", "line_only"}:
                    piece.pop("content_ref_en")
                    piece.pop("content_ref_es")
                if scenario == "headers_only":
                    piece.update(log_header="LOG HEADER", mail_from="Archive", mail_subject="Header only")
                if scenario in {"line_only", "empty_with_line", "whitespace_with_line"}:
                    piece["line"] = "NODE: TEST_RELAY"
                if scenario == "en_fallback":
                    piece.pop("content_ref_es")
                if scenario == "es_only":
                    piece.pop("content_ref_en")
                if scenario == "missing_file":
                    piece["content_ref_en"] = "lore/absent.txt"
            with installed(mutate=configure) as root:
                for lang in ("en", "es"):
                    text = {"en": "Recovered archive.", "es": "Archivo recuperado."}[lang]
                    if scenario in {"empty", "empty_with_line"} or (scenario == "empty_es" and lang == "es"):
                        text = ""
                    elif scenario in {"whitespace", "whitespace_with_line"}:
                        text = " \t\n"
                    (root / f"lore/synthetic_alpha.{lang}.txt").write_text(text)
                valid = scenario in {"valid", "en_fallback"} or (channel == "salvage_data" and scenario in {"line_only", "empty_with_line"})
                if not valid:
                    expect_error(lambda: create_initial_state_prologue(seed=0), "invalid", "content_ref_en" if scenario == "missing_file" else "content")
                    continue
                for locale in (Locale.EN, Locale.ES):
                    s = create_initial_state_prologue(seed=0)
                    s.os.locale = locale
                    lore.run_lore_scheduler_tick(s)
                    assert s.world.lore_placements.piece_channel_bindings[KEY] == channel
                    if channel == "salvage_data":
                        content = s.world.node_pools["TEST_HOST"].injected_files[0]["content"]
                    else:
                        _radio_at_host(s, "TEST_HOST")
                        delivery = lore.maybe_deliver_lore(s, "dock", lore.build_lore_context(s, "TEST_HOST"))
                        assert delivery.applied
                        content = s.os.fs[delivery.events[0].data["path"]].content
                    expected = "NODE: TEST_RELAY" if scenario in {"line_only", "empty_with_line"} else (
                        "Recovered archive." if locale == Locale.EN or scenario == "en_fallback" else "Archivo recuperado.")
                    assert content.strip() == expected, (channel, scenario, locale, content)

    # The existing reference precedence also applies to legacy `files` entries.
    def files_fallback(alpha, beta):
        piece = alpha["primary_intel"]
        piece.pop("spatial_bindings")
        piece.pop("line")
        piece["files"] = [{"content_ref_en": piece.pop("content_ref_en")}]
        piece.pop("content_ref_es")
    with installed(mutate=files_fallback) as root:
        (root / "lore/synthetic_alpha.en.txt").write_text("Fallback through files.")
        s = create_initial_state_prologue(seed=0)
        piece = lore._iter_all_pieces(s)[0]
        assert lore._file_for_salvage_piece(piece, "es", s)["content"].strip() == "Fallback through files."

    def optional_empty(alpha, beta):
        piece = alpha["primary_intel"]
        piece.pop("spatial_bindings")
        piece.pop("line")
        piece["force"] = False
    with installed(mutate=optional_empty) as root:
        for lang in ("en", "es"):
            (root / f"lore/synthetic_alpha.{lang}.txt").write_text("")
        s = create_initial_state_prologue(seed=0)
        piece = lore._iter_all_pieces(s)[0]
        assert lore._file_for_salvage_piece(piece, "en", s)["content"] == ""


def main():
    evidence = {}
    for name, check in sorted(globals().copy().items()):
        if name.startswith("test_"):
            result = check()
            if result is not None:
                evidence[name] = result
            print("PASS", name)
    target = Path("/tmp/retorno-e4-narrative-evidence.json")
    target.write_text(json.dumps(evidence, indent=2))
    print("NARRATIVE WORLD INTEGRATION PASSED", target)


if __name__ == "__main__":
    main()
