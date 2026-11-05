"""4D-3e1 regression; in-memory fixtures and temporary save slots only."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import pickle
import random
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc
from unittest.mock import patch

from retorno.core import lore
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.world import NodePoolState, SpaceNode, sector_id_for_pos
from retorno.runtime.data_loader import load_worldgen_archetypes, load_worldgen_templates
from retorno.worldgen import generator as gen
from tests.fixtures import worldgen_catalog_5cdde28 as catalog
from tests.fixtures.worldgen_catalog_5cdde28 import SiteStatus, catalog_sector, catalog_sectors
if __package__:
    from tests.worldgen_preexistence_characterization_smoke import _state
else:
    from worldgen_preexistence_characterization_smoke import _state


SID = "S+020_+020_+000"
FAMILY = tuple(f"S{x:+04d}_{y:+04d}_+000" for x in range(20, 28) for y in range(20, 28))


def _checked(state, ids=(SID,)):
    before, rng = pickle.dumps(state), random.getstate()
    result = catalog_sectors(state, ids)
    assert pickle.dumps(state) == before and random.getstate() == rng
    assert result == catalog_sectors(state, ids)
    assert pickle.dumps(state) == before and random.getstate() == rng
    return result


def test_01_repeatable_identity_and_real_coordinates_with_frozen_results():
    a = _checked(_state()).sectors[0]
    b = _checked(_state()).sectors[0]
    assert a == b and len(a.sites) == 2
    assert a.sites[0].position_ly == (205.04909961494286, 207.116870031816, 4.97869392003561)
    assert a.sites[0].key.startswith("procedural:")
    assert all(p.node_id is None and p.status == SiteStatus.CONDITIONAL for p in a.sites)
    try:
        a.sites[0].kind = "station"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Catalog records must be immutable")


def test_02_query_order_duplicates_and_state_dictionary_order():
    a = _state()
    before = _checked(a, FAMILY)
    assert before == _checked(a, tuple(reversed(FAMILY)))
    # Duplicates are permitted within the technical raw request bound.
    assert catalog_sectors(a, (SID, SID)) == catalog_sectors(a, (SID,))
    a.world.space.nodes = dict(reversed(list(a.world.space.nodes.items())))
    assert before == _checked(a, FAMILY)
    for sid in reversed(FAMILY):
        assert catalog_sector(a, sid) == next(c for c in before.sectors if c.sector_id == sid)


def test_03_whole_state_rng_pools_and_resources_stay_identical():
    a = _state()
    a.meta.rng_counter = 937
    a.world.node_pools["ECHO_7"] = NodePoolState(
        window_open=False, node_cleaned=True, uplink_data_consumed=True,
        injected_files=[{"path": "/logs/consumed.txt", "content": "historical"}])
    a.world.visited_nodes.add("ECHO_7")
    a.world.space.nodes["ECHO_7"].salvage_scrap_available = 0
    _checked(a, FAMILY)


def test_04_writers_and_global_rng_are_forbidden():
    a = _state()
    def forbidden(*args, **kwargs):
        raise AssertionError("A read-only catalog called a writer or global RNG")
    with patch.object(gen, "ensure_sector_generated", forbidden), \
         patch.object(gen, "_ensure_sector_generated_core", forbidden), \
         patch.object(gen, "_apply_salvage_profile", forbidden), \
         patch.object(gen, "_generate_node_id", forbidden), \
         patch.object(lore, "sync_node_pools_for_known_nodes", forbidden), \
         patch.object(lore, "register_hidden_anchored_node", forbidden), \
         patch.object(random, "random", forbidden), patch.object(random, "seed", forbidden):
        _checked(a, FAMILY)


def test_05_all_archetypes_empty_sparse_dense_and_regional_caps():
    a = _state()
    configs, templates = load_worldgen_archetypes(), load_worldgen_templates()
    seen, counts, regions = set(), set(), set()
    for base in (20, -25000, 15010):
        ids = tuple(f"S{base+x:+04d}_{y:+04d}_+000" for x in range(8) for y in range(8))
        result = _checked(a, ids)
        for sector in result.sectors:
            seen.add(sector.baseline_archetype)
            regions.add(sector.region)
            cfg = configs[sector.baseline_archetype]
            kinds = [p.kind for p in sector.sites]
            counts.add(len(kinds))
            assert cfg["node_count_min"] <= len(kinds) <= cfg["node_count_max"]
            assert not set(kinds) & set(cfg["forbidden_kinds"])
            assert templates[sector.region]["archetype_weights"][sector.baseline_archetype] > 0
            for kind, cap in cfg["kind_caps"].items():
                assert kinds.count(kind) <= cap
    assert seen == set(configs) and counts >= {0, 1, 2, 3} and regions == set(templates)


def test_06_generated_and_authored_are_physical_not_reconstructed_slots():
    a = _state()
    origin = catalog_sector(a, "S+000_+000_+000")
    assert {p.node_id for p in origin.sites if p.status == SiteStatus.PHYSICAL} == {"UNKNOWN", "ECHO_7"}
    assert all(p.generation_sector_id is None for p in origin.sites if p.node_id)
    gen.ensure_sector_generated(a, SID)
    result = _checked(a).sectors[0]
    assert result.generated and result.recorded_archetype == "isolated_station"
    assert all(p.status == SiteStatus.PHYSICAL and p.slot_index is None for p in result.sites)
    assert "generated_sector_no_new_slots_forecast" in result.limitations


def test_07_no_verified_latent_sites_and_guardrail_conditions_are_explicit():
    a = _state(29)
    result = _checked(a, ("S+000_+001_+000", "S+000_+000_+000", SID))
    assert all(p.status != SiteStatus.VERIFIED for c in result.sectors for p in c.sites)
    samples = [p for c in result.sectors for p in c.sites if p.node_id is None]
    assert samples and all("initial_guardrail_unresolved" in p.conditions for p in samples)
    a.world.space.nodes.pop("ECHO_7")
    a.meta.rng_seed = 271828
    # A missing ECHO_7 fallback is not silently applied to the snapshot.
    origin = catalog_sector(a, "S+000_+000_+000")
    samples = [p for p in origin.sites if p.node_id is None]
    assert samples and all("fixed_origin_hub_not_applied" in p.conditions for p in samples)


def test_08_discovery_visits_ship_position_and_survival_do_not_change_catalog():
    a = _state()
    before = _checked(a)
    a.world.known_nodes.clear()
    a.world.known_contacts.clear()
    a.world.known_intel = {SID: {"sector": True}}
    a.world.visited_nodes.update(a.world.space.nodes)
    a.world.current_pos_ly = (1000.0, -2000.0, 50.0)
    a.ship.power.e_batt_kwh = 0
    a.ship.cargo_scrap = 0
    for system in a.ship.systems.values():
        system.health = 0
    a.meta.rng_counter += 100
    assert before == _checked(a)


def test_09_protected_primary_is_not_revealed_or_approved_for_recovery():
    a = _state()
    nid = "HARBOR_12"
    arc = {"arc_id": "test", "primary_intel": {"id": "primary", "kind": "node", "line": f"NODE: {nid}"}}
    with patch.object(lore, "load_arcs", return_value=[arc]):
        assert nid in lore._locked_primary_targets(a)
        # This is an internal physical inventory, deliberately NOT a selector.
        pos = a.world.space.nodes[nid]
        sid = sector_id_for_pos(pos.x_ly, pos.y_ly, pos.z_ly)
        result = _checked(a, (sid,)).sectors[0]
        assert "narrative_protection_not_assessed" in result.limitations
        assert nid not in a.world.known_nodes | a.world.known_contacts
        assert all(p.status != SiteStatus.VERIFIED for p in result.sites)


def test_10_z_outflow_and_region_boundaries_keep_both_spatial_frames():
    a = _state()
    result = _checked(a, ("S+15126_+000_+000", "S+14999_+000_+000", "S+15000_+000_+000",
                           "S-24001_+000_+000", "S-24000_+000_+000"))
    assert {c.region for c in result.sectors} == {"halo", "disk", "bulge"}
    spill = next(c for c in result.sectors if c.sector_id == "S+15126_+000_+000").sites[0]
    assert spill.generation_sector_id == "S+15126_+000_+000"
    assert spill.physical_sector_id == "S+15126_+000_+001"
    assert "sample_outside_generation_sector" in spill.conditions


def test_11_save_load_keeps_state_and_catalog_without_new_schema():
    a = _state()
    gen.ensure_sector_generated(a, SID)
    ids = (SID, "S+15126_+000_+000", "S+000_+000_+000")
    expected = _checked(a, ids)
    with TemporaryDirectory(prefix="retorno-preexistence-") as directory:
        path = Path(directory) / "isolated.dat"
        for _ in range(3):
            save_single_slot(a, path)
            a = load_single_slot(path).state
            assert _checked(a, ids) == expected


def test_12_python_hash_seeds_and_processes_reproduce_results():
    script = """
from dataclasses import asdict
import json
from tests.worldgen_preexistence_characterization_smoke import _state
from tests.fixtures.worldgen_catalog_5cdde28 import catalog_sectors
ids = tuple(set(('S+020_+020_+000','S+15126_+000_+000','S+000_+000_+000')))
print(json.dumps(asdict(catalog_sectors(_state(), ids)), sort_keys=True))
"""
    results = [subprocess.check_output([sys.executable, "-c", script], text=True,
               env={**os.environ, "PYTHONHASHSEED": seed}) for seed in ("1", "7", "99")]
    assert len(set(results)) == 1


def test_13_bounds_validation_and_missing_config_are_not_empty_space_proofs():
    a = _state()
    for ids, bound, error in ((FAMILY, 1, ValueError), (("S0_0_0",), 64, ValueError),
                               ((SID,), 0, ValueError), (SID, 64, TypeError),
                               (iter((SID,)), 64, TypeError)):
        before = pickle.dumps(a)
        try:
            catalog_sectors(a, ids, max_sectors=bound)
        except error:
            pass
        else:
            raise AssertionError("Expected invalid request to be rejected")
        assert pickle.dumps(a) == before
    with patch.object(catalog, "load_worldgen_archetypes", return_value={}):
        sector = _checked(a).sectors[0]
        assert not sector.sites and "missing_canonical_configuration" in sector.limitations
    assert catalog_sectors(a, ()).sectors == ()


def test_14_configuration_scope_keys_track_weight_order_but_not_map_storage_order():
    a = _state()
    expected = _checked(a)
    templates = load_worldgen_templates()
    with patch.object(catalog, "load_worldgen_templates", return_value=dict(reversed(list(templates.items())))):
        assert _checked(a) == expected
    changed = copy.deepcopy(templates)
    changed["disk"]["archetype_weights"] = dict(reversed(list(changed["disk"]["archetype_weights"].items())))
    with patch.object(catalog, "load_worldgen_templates", return_value=changed):
        assert _checked(a).configuration_key != expected.configuration_key


def test_15_inadmissible_duplicate_sample_and_nonfinite_state():
    a = _state()
    pos = (0.0, 0.0, 0.0)
    with patch.object(catalog, "_sample_sector_node", return_value=(pos, random.Random(0))):
        result = _checked(a).sectors[0]
        assert result.sites and all(p.status == SiteStatus.INADMISSIBLE for p in result.sites)
        assert all("sample_position_occupied" in p.conditions for p in result.sites)
    a.world.space.nodes["UNKNOWN"].x_ly = float("nan")
    before = pickle.dumps(a)
    try:
        catalog_sector(a, SID)
    except ValueError:
        pass
    else:
        raise AssertionError("Nonfinite state must not masquerade as empty space")
    assert pickle.dumps(a) == before


def test_16_single_sector_scope_and_indexed_forecasts_match_full_world_helpers():
    a = _state()
    result = _checked(a, FAMILY)
    templates, configs = load_worldgen_templates(), load_worldgen_archetypes()
    for sector in result.sectors:
        kinds, _ = gen._plan_sector_kinds(a, sector.sector_id, sector.baseline_archetype,
                                         sector.region, templates[sector.region], configs[sector.baseline_archetype])
        assert [p.kind for p in sector.sites] == kinds
    calls = []
    plan = catalog._plan_sector_kinds
    def indexed(view, sid, *args, **kwargs):
        calls.append(sid)
        assert all(sector_id_for_pos(n.x_ly, n.y_ly, n.z_ly) == sid for n in view.world.space.nodes.values())
        return plan(view, sid, *args, **kwargs)
    with patch.object(catalog, "_plan_sector_kinds", side_effect=indexed):
        assert _checked(a).sectors[0].sector_id == SID
    assert set(calls) == {SID}  # No implicit 3×3 neighborhood.


def test_17_canonical_template_and_actual_node_regions_are_not_conflated():
    a = _state(2)
    sid = "S+14999_+199_+000"
    sector = _checked(a, (sid,)).sectors[0]
    assert sector.region == "disk" and {p.region for p in sector.sites} == {"disk", "halo"}
    assert all("sample_region_differs_from_template_region" in p.conditions
               for p in sector.sites if p.region == "halo")
    gen.ensure_sector_generated(a, sid)
    actual = {(p.kind, p.position_ly, p.region) for p in catalog_sector(a, sid).sites}
    assert actual == {(p.kind, p.position_ly, p.region) for p in sector.sites}


def benchmark():
    print("background,sectors,median_ms,max_ms,peak_kib,physical_nodes_examined")
    for count in (0, 1000, 3000):
        a = _state()
        for i in range(count):
            nid = f"BACKGROUND_{i}"
            a.world.space.nodes[nid] = SpaceNode(nid, nid, "derelict", x_ly=-10000-i, y_ly=-10000)
        for size in (1, 9, 64):
            ids = FAMILY[:size]
            durations = []
            for _ in range(3):
                start = perf_counter()
                result = catalog_sectors(a, ids)
                durations.append((perf_counter()-start)*1000)
            tracemalloc.start()
            catalog_sectors(a, ids)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert result.physical_nodes_examined == len(a.world.space.nodes)
            print(f"{count},{size},{statistics.median(durations):.3f},{max(durations):.3f},"
                  f"{peak/1024:.1f},{result.physical_nodes_examined}")


def main():
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"WORLDGEN PREEXISTENCE CATALOG SMOKE PASSED ({len(tests)} groups)")
    if "--benchmark" in sys.argv:
        benchmark()


if __name__ == "__main__":
    main()
