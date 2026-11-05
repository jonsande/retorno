"""Characterize legacy order dependencies, without changing its contract."""
from __future__ import annotations

import copy

from retorno.bootstrap import create_initial_state_prologue
from retorno.model.world import SpaceNode, sector_id_for_pos
from tests.fixtures import worldgen_legacy_5cdde28 as gen
from tests.fixtures.worldgen_catalog_5cdde28 import SiteStatus, catalog_sector


def _state(seed=271828):
    state = create_initial_state_prologue()
    state.meta.rng_seed = seed
    return state


def _physical(state):
    return tuple(sorted((n.node_id, n.kind, n.x_ly, n.y_ly, n.z_ly)
                        for n in state.world.space.nodes.values()))


def _edges(state):
    return {(nid, other) for nid, node in state.world.space.nodes.items() for other in node.links}


def _generate(state, ids):
    for sid in ids:
        gen.ensure_sector_generated(state, sid)


def test_same_seed_and_sequence_reproduce_nodes_metadata_and_links():
    a = _state()
    b = copy.deepcopy(a)
    ids = ("S+020_+020_+000", "S+022_+020_+000", "S+020_+022_+000")
    _generate(a, ids)
    _generate(b, ids)
    assert _physical(a) == _physical(b) and _edges(a) == _edges(b)
    assert a.world.sector_states == b.world.sector_states
    assert a.world.intersector_link_pairs == b.world.intersector_link_pairs


def test_same_nodes_different_topology_with_reversed_materialization():
    a = _state(2)
    b = copy.deepcopy(a)
    ids = ("S+020_+020_+000", "S+022_+020_+000", "S+020_+022_+000")
    _generate(a, ids)
    _generate(b, reversed(ids))
    assert a.world.generated_sectors == b.world.generated_sectors
    assert _physical(a) == _physical(b)
    assert len(_edges(a) ^ _edges(b)) == 4  # Two undirected edges differ.
    assert a.world.intersector_link_pairs == b.world.intersector_link_pairs


def test_guardrail_changes_shared_sector_identity_by_request_order():
    a = _state(29)
    b = copy.deepcopy(a)
    ids = ("S+001_+000_+000", "S-001_+000_+000")
    _generate(a, ids)
    _generate(b, reversed(ids))
    sid = "S+000_+001_+000"
    assert a.world.generated_sectors == b.world.generated_sectors
    assert a.world.sector_states[sid].archetype == "empty"
    assert b.world.sector_states[sid].archetype == "relay_corridor"
    assert a.world.sector_states[sid].node_ids != b.world.sector_states[sid].node_ids
    assert a.world.sparse_guardrail_done and b.world.sparse_guardrail_done


def test_z_spill_changes_later_sector_quota_and_legacy_provenance_is_lost():
    a = _state()
    a.world.sparse_guardrail_done = True
    b = copy.deepcopy(a)
    source, destination = "S+15126_+000_+000", "S+15126_+000_+001"
    forecast = catalog_sector(a, source)
    sample = next(p for p in forecast.sites if p.generation_sector_id == source)
    assert sample.position_ly == (151266.79157885376, 9.329097599582711, 10.057691279289713)
    assert sample.physical_sector_id == destination
    assert sample.status == SiteStatus.CONDITIONAL
    _generate(a, (source, destination))
    _generate(b, (destination, source))
    assert len(catalog_sector(a, destination).sites) == 1
    assert len(catalog_sector(b, destination).sites) == 2
    assert "WRECK_E39D3C" in a.world.space.nodes
    assert a.world.sector_states[source].node_ids == []  # Not generation provenance.
    assert _physical(a) != _physical(b)


def test_existing_authored_nodes_reduce_quota_and_change_slot_kind():
    a = _state()
    sid = "S+020_+020_+000"
    original = catalog_sector(a, sid)
    assert [p.kind for p in original.sites] == ["station", "derelict"]
    a.world.space.nodes["AUTHORED_TEST"] = SpaceNode(
        "AUTHORED_TEST", "fixture", "station", x_ly=201, y_ly=201, z_ly=1, is_hub=True)
    changed = catalog_sector(a, sid)
    samples = [p for p in changed.sites if p.node_id is None]
    assert len(samples) == 1 and samples[0].kind != "station"
    gen.ensure_sector_generated(a, sid)
    assert len(catalog_sector(a, sid).sites) == 2
    assert a.world.space.nodes["AUTHORED_TEST"].x_ly == 201


def test_node_id_collisions_change_allocation_but_not_the_sample():
    a = _state()
    sid = "S+020_+020_+000"
    p = catalog_sector(a, sid).sites[0]
    _, rng = gen._sample_sector_node(a.meta.rng_seed, sid, p.archetype, p.slot_index, p.kind, 0.3)
    base_id = f"STATION_{rng.getrandbits(24):06X}"
    b = copy.deepcopy(a)
    b.world.space.nodes[base_id] = SpaceNode(base_id, "collision fixture", "station", x_ly=-1000)
    # Fill every suffix to exercise the second-base branch as well.
    c = copy.deepcopy(b)
    for suffix in gen._GREEK_SUFFIXES:
        nid = f"{base_id}_{suffix}"
        c.world.space.nodes[nid] = SpaceNode(nid, nid, "station", x_ly=-1000)
    for state in (a, b, c):
        gen.ensure_sector_generated(state, sid)
    def at_sample(state):
        return next(n for n in state.world.space.nodes.values()
                    if (n.x_ly, n.y_ly, n.z_ly) == p.position_ly)
    assert at_sample(a).node_id == base_id
    assert at_sample(b).node_id == base_id + "_ALFA"
    assert at_sample(c).node_id not in {base_id, base_id + "_ALFA"}
    assert len({at_sample(s).radiation_rad_per_s for s in (a, b, c)}) > 1


def test_inspection_then_same_snapshot_materialization_matches_samples():
    a = _state()
    sid = "S+020_+020_+000"
    forecast = catalog_sector(a, sid)
    assert sid not in a.world.generated_sectors
    gen.ensure_sector_generated(a, sid)
    actual = {(n.kind, (n.x_ly, n.y_ly, n.z_ly)) for n in a.world.space.nodes.values()
              if sector_id_for_pos(n.x_ly, n.y_ly, n.z_ly) == sid}
    assert {(p.kind, p.position_ly) for p in forecast.sites} == actual
    assert all(p.status == SiteStatus.CONDITIONAL for p in forecast.sites)
    assert all(p.status == SiteStatus.PHYSICAL for p in catalog_sector(a, sid).sites)


def test_existing_generated_sector_does_not_regenerate_after_node_removal():
    a = _state()
    sid = "S+020_+020_+000"
    gen.ensure_sector_generated(a, sid)
    for p in catalog_sector(a, sid).sites:
        del a.world.space.nodes[p.node_id]
    gen.ensure_sector_generated(a, sid)
    assert catalog_sector(a, sid).sites == ()


def test_evaluated_pair_is_not_retried_after_hub_or_budget_change():
    a = _state()
    gen.ensure_sector_generated(a, "S+020_+020_+000")
    key = next(iter(sorted(a.world.intersector_link_pairs)))
    left, right = key.split("|")
    for sid in (left, right):
        a.world.sector_states[sid].intersector_link_count = 0
    before = _edges(a)
    gen._evaluate_intersector_pair(a, left, right, {s.archetype: {
        "intersector_link_max": 100, "intersector_link_prob": 1.0,
    } for s in a.world.sector_states.values()})
    assert _edges(a) == before
    assert a.world.sector_states[left].intersector_link_count == 0


def main():
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"WORLDGEN PREEXISTENCE CHARACTERIZATION SMOKE PASSED ({len(tests)} groups)")


if __name__ == "__main__":
    main()
