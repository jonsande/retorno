"""4D-3e1b: experimental invariants, never production materialization."""
from __future__ import annotations

from dataclasses import replace
import math
import os
import pickle
import random
import subprocess
import sys
from unittest.mock import patch

from retorno.config.balance import Balance
from retorno.worldgen import catalog, generator as gen, manifest_prototype as manifest
from retorno.worldgen.manifest_prototype import (
    AuthoredSite, EvidenceStatus as Status, SiteIdentity, authored_base,
    define_manifest, lookup_site, query_manifest,
)
from retorno.model.world import region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_locations, load_worldgen_templates
if __package__:
    from tests.worldgen_preexistence_characterization_smoke import _state, _generate
else:
    from worldgen_preexistence_characterization_smoke import _state, _generate


FAMILY = tuple(f"S{x:+04d}_{y:+04d}_+000" for x in range(20, 28) for y in range(20, 28))


def _sites(result):
    return {site.identity: site for sector in result.sectors for site in sector.sites} | {
        s.identity: s for s in result.boundary_sites}


def _checked(definition, ids=FAMILY):
    before, rng = pickle.dumps(definition), random.getstate()
    result = query_manifest(definition, ids)
    assert pickle.dumps(definition) == before and random.getstate() == rng
    assert result == query_manifest(definition, tuple(reversed(ids)))
    assert pickle.dumps(definition) == before and random.getstate() == rng
    assert result.historical_data.status == Status.CERTIFIED
    assert result.materialization.status == Status.CONDITIONAL
    assert result.physical_inventory.status == result.resources.status == result.environment.status == Status.NOT_EVALUATED
    sites = _sites(result)
    assert len(sites) == sum(len(c.sites) for c in result.sectors) + len(result.boundary_sites)
    for site in sites.values():
        assert all(math.isfinite(v) for v in site.position_ly)
        assert site.region == region_for_pos(*site.position_ly)
        assert site.physical_sector_id == sector_id_for_pos(*site.position_ly)
    for edge in result.edges:
        assert edge.left in sites and edge.right in sites and edge.left != edge.right
        assert 0 <= edge.distance_ly <= Balance.MAX_ROUTE_HOP_LY
        assert edge.distance_ly == math.dist(sites[edge.left].position_ly, sites[edge.right].position_ly)
    assert len(result.evaluated_generation_sectors) <= 25*len(set(ids))
    return result


def test_01_same_definition_repeat_reverse_duplicate_and_separate_sessions():
    a = define_manifest(271828)
    assert a == define_manifest(271828)
    result = _checked(a)
    assert query_manifest(a, (FAMILY[0], FAMILY[0])) == query_manifest(a, (FAMILY[0],))
    for sector in result.sectors:
        single = _checked(a, (sector.sector_id,))
        assert single.sectors == (sector,)
        family_incident = {e for e in result.edges if any(
            _sites(result)[nid].generation_sector_id == sector.sector_id for nid in (e.left, e.right))}
        assert set(single.edges) == family_incident


def test_02_process_hash_seeds_and_unordered_source_collections():
    script = '''
import json
from dataclasses import asdict
from retorno.worldgen.manifest_prototype import define_manifest, query_manifest
ids=tuple(set(('S+020_+020_+000','S+022_+020_+000','S+000_+001_+000','S+15126_+000_+000')))
print(json.dumps(asdict(query_manifest(define_manifest(29),ids)),sort_keys=True))
'''
    values = [subprocess.check_output([sys.executable, "-c", script],text=True,
              env={**os.environ, "PYTHONHASHSEED": seed}) for seed in ("1", "7", "99")]
    assert len(set(values)) == 1


def test_03_no_state_resources_knowledge_files_or_global_rng_writers():
    a = _state()
    definition = define_manifest(271828)
    before, rng = pickle.dumps(a), random.getstate()
    def forbidden(*args, **kwargs):
        raise AssertionError("Prototype called a productive writer, loader or global RNG")
    from retorno.core import lore
    from retorno.io import save_load
    with patch.object(gen, "ensure_sector_generated", forbidden), \
         patch.object(gen, "_ensure_sector_generated_core", forbidden), \
         patch.object(gen, "_apply_salvage_profile", forbidden), \
         patch.object(gen, "_generate_node_id", forbidden), \
         patch.object(catalog, "catalog_sectors", forbidden), \
         patch.object(lore, "register_hidden_anchored_node", forbidden), \
         patch.object(lore, "sync_node_pools_for_known_nodes", forbidden), \
         patch.object(save_load, "save_single_slot", forbidden), \
         patch.object(manifest, "load_locations", forbidden), \
         patch.object(manifest, "load_worldgen_templates", forbidden), \
         patch.object(random, "random", forbidden), patch.object(random, "seed", forbidden):
        _checked(definition)
    assert pickle.dumps(a) == before and random.getstate() == rng


def test_04_materialized_registry_and_exploration_never_determine_manifest():
    definition = define_manifest(271828)
    ids = ("S+020_+020_+000", "S+022_+020_+000", "S+15126_+000_+000", "S+15126_+000_+001")
    expected = _checked(definition, ids)
    for order in (ids, tuple(reversed(ids))):
        state = _state()
        for sid in order:
            _generate(state, (sid,))
            state.world.known_nodes.update(state.world.space.nodes)
            state.world.visited_nodes.update(state.world.space.nodes)
            state.meta.rng_counter += 100
            state.ship.cargo_scrap = 0
            state.clock.t += 1000000
            assert _checked(definition, ids) == expected


def test_05_known_legacy_witnesses_remain_and_new_model_contrasts_them():
    if __package__:
        from tests import worldgen_preexistence_characterization_smoke as legacy
    else:
        import worldgen_preexistence_characterization_smoke as legacy
    legacy.test_same_nodes_different_topology_with_reversed_materialization()
    legacy.test_guardrail_changes_shared_sector_identity_by_request_order()
    legacy.test_z_spill_changes_later_sector_quota_and_legacy_provenance_is_lost()
    for seed, ids in ((2, ("S+020_+020_+000", "S+022_+020_+000", "S+020_+022_+000")),
                      (29, ("S+001_+000_+000", "S-001_+000_+000")),
                      (271828, ("S+15126_+000_+000", "S+15126_+000_+001"))):
        _checked(define_manifest(seed), ids)


def test_06_authored_base_matches_bootstrap_and_is_order_independent():
    sites = authored_base(load_locations())
    state = _state()
    assert {a.raw_id for a in sites} == set(state.world.space.nodes)
    for a in sites:
        node = state.world.space.nodes[a.raw_id]
        assert (a.kind, a.position_ly, a.is_hub) == (node.kind, (node.x_ly,node.y_ly,node.z_ly), node.is_hub)
    assert define_manifest(29, authored=sites) == define_manifest(29, authored=tuple(reversed(sites)))
    one = AuthoredSite("AUTHORED_TEST", "station", (201,201,1), True)
    before = _checked(define_manifest(271828), (FAMILY[0],)).sectors[0]
    after = _checked(define_manifest(271828, authored=sites+(one,)), (FAMILY[0],)).sectors[0]
    assert len(before.sites) == len(after.sites) == 2
    assert sum(s.identity.namespace == "procedural" for s in before.sites) == 2
    assert sum(s.identity.namespace == "procedural" for s in after.sites) == 1
    assert all(s.kind != "station" for s in after.sites if s.identity.namespace == "procedural")


def test_07_namespace_collisions_and_duplicate_authored_ids():
    definition = define_manifest(271828)
    original = _checked(definition, (FAMILY[0],)).sectors[0].sites[0]
    # Both a legacy short-id collision and a raw-id that looks like a manifest address.
    base = definition.authored + (
        AuthoredSite(original.legacy_id_hint, "station", (-1000,0,0), True),
        AuthoredSite(original.identity.encoded, "derelict", (-1000,0,1)),)
    changed = define_manifest(271828, authored=base)
    result = _checked(changed, (FAMILY[0], "S-100_+000_+000"))
    at = next(s for s in result.sectors[0].sites if s.position_ly == original.position_ly)
    assert at.identity.namespace == "procedural" and at.legacy_id_hint == original.legacy_id_hint
    # Address encoding is injective across namespaces even for identical local strings.
    p = SiteIdentity(changed.scope, "procedural", original.identity.local_id)
    a = SiteIdentity(changed.scope, "authored", p.encoded)
    special = SiteIdentity(changed.scope, "special", p.local_id)
    assert len({p, a, special}) == len({p.encoded, a.encoded, special.encoded}) == 3
    try:
        define_manifest(1, authored=base+(base[0],))
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate authored ids must fail closed")


def test_08_gaussian_spill_keeps_provenance_and_no_foreign_quota_consumption():
    result = _checked(define_manifest(271828), ("S+15126_+000_+000", "S+15126_+000_+001"))
    source, destination = result.sectors
    assert len(source.sites) == len(destination.sites) == 1
    outlier = source.sites[0]
    assert outlier.position_ly == (151266.79157885376, 9.329097599582711, 10.057691279289713)
    assert outlier.generation_sector_id == source.sector_id
    assert outlier.physical_sector_id == destination.sector_id
    assert len([s for c in result.sectors for s in c.sites if s.physical_sector_id == destination.sector_id]) == 2
    assert result.physical_inventory.status == Status.NOT_EVALUATED


def test_09_guardrail_is_a_fixed_origin_neighborhood_not_a_first_query_effect():
    definition = define_manifest(29)
    a = _checked(definition, ("S+001_+000_+000", "S-001_+000_+000"))
    query_manifest(definition, ("S+100_+100_+100",))
    assert _checked(definition, ("S-001_+000_+000", "S+001_+000_+000")) == a
    source = manifest._Session(definition)
    assert source.overrides == manifest._Session(define_manifest(29)).overrides


def test_10_topology_caps_complete_incident_edges_and_reciprocity():
    from retorno.runtime.data_loader import load_worldgen_archetypes
    cfg = load_worldgen_archetypes()
    for seed in (2,29,271828):
        result = _checked(define_manifest(seed))
        sites = _sites(result)
        for sector in result.sectors:
            assert sum(s.is_topology_hub for s in sector.sites) == bool(sector.sites)
            degree = sum(e.kind == "intersector" and any(sites[n].generation_sector_id == sector.sector_id
                         for n in (e.left,e.right)) for e in result.edges)
            assert degree <= cfg[sector.archetype]["intersector_link_max"]
            for edge in result.edges:
                if edge.kind == "intersector" and sector.topology_hub in (edge.left, edge.right):
                    other = sites[edge.left if edge.right == sector.topology_hub else edge.right].generation_sector_id
                    reverse = query_manifest(define_manifest(seed),(other,))
                    assert edge in reverse.edges
        assert any(not s.sites for s in result.sectors)
        assert any(s.sites and not any(e.kind == "intersector" and s.topology_hub in (e.left,e.right)
                                      for e in result.edges) for s in result.sectors)


def test_11_regional_archetypes_types_and_actual_boundary_regions():
    from retorno.runtime.data_loader import load_worldgen_archetypes
    cfg = load_worldgen_archetypes()
    for base in (20,-25000,15123):
        ids = tuple(f"S{base+x:+04d}_{y:+04d}_+000" for x in range(8) for y in range(8))
        for sector in _checked(define_manifest(2),ids).sectors:
            kinds=[s.kind for s in sector.sites]
            assert not set(kinds)&set(cfg[sector.archetype]['forbidden_kinds'])
            assert cfg[sector.archetype]['node_count_min'] <= len(kinds) <= cfg[sector.archetype]['node_count_max']
            for kind, cap in cfg[sector.archetype]['kind_caps'].items():
                assert kinds.count(kind)<=cap
    boundary=_checked(define_manifest(2),("S+14999_+199_+000",)).sectors[0]
    assert boundary.template_region == "disk" and {s.region for s in boundary.sites} == {"disk","halo"}


def test_12_certified_invalid_conditional_and_not_evaluated_are_distinct():
    definition=define_manifest(2)
    site=_checked(definition,(FAMILY[0],)).sectors[0].sites[0]
    assert lookup_site(definition,site.identity).site == site
    assert lookup_site(definition,replace(site.identity,scope="foreign")).assessment.status == Status.INVALID
    assert lookup_site(definition,SiteIdentity(definition.scope,"procedural",'["S+020_+020_+000",999]')).assessment.status == Status.INVALID
    assert lookup_site(definition,SiteIdentity(definition.scope,"procedural","malformed")).assessment.status == Status.INVALID
    assert lookup_site(definition,SiteIdentity(definition.scope,"special","dynamic")).assessment.status == Status.NOT_EVALUATED
    assert lookup_site(definition,SiteIdentity(definition.scope,"authored","absent")).assessment.status == Status.INVALID
    # A legacy conditional key is not a manifest address or certification.
    old = catalog.catalog_sector(_state(),FAMILY[0]).sites[0]
    assert old.status == catalog.SiteStatus.CONDITIONAL
    assert lookup_site(definition,SiteIdentity(definition.scope,"procedural",old.key)).assessment.status == Status.INVALID


def test_13_snapshot_version_configuration_and_environment_validation():
    templates=load_worldgen_templates()
    definition=define_manifest(2,templates=templates)
    expected=_checked(definition)
    templates['disk']['z_sigma']=9000
    assert _checked(definition)==expected
    assert define_manifest(3).scope != definition.scope
    with patch.object(Balance,'GALAXY_OP_TO_PHYSICAL_SCALE',2):
        try:
            query_manifest(definition,FAMILY)
        except ValueError:
            pass
        else:
            raise AssertionError("Changed environment must not silently reinterpret a definition")
    for bad in (replace(definition,algorithm_version='future'),replace(definition,scope='forged')):
        try:
            query_manifest(bad,FAMILY)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid definition must be rejected")


def test_14_technical_bounds_not_absence_and_invalid_authored_data():
    definition=define_manifest(1)
    for ids,cap in ((FAMILY,1),(('S0_0_0',),64),(FAMILY,0)):
        try:
            query_manifest(definition,ids,max_sectors=cap)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected explicit request rejection")
    assert not query_manifest(definition,()).sectors
    for base in ((AuthoredSite('BAD','station',(float('nan'),0,0)),),):
        try:
            define_manifest(1,authored=base)
        except ValueError:
            pass
        else:
            raise AssertionError("Nonfinite authored position must fail")


def test_15_authored_over_capacity_is_preserved_without_extra_slots():
    base=tuple(AuthoredSite(f'EXPLICIT_{i}','station',(201+i,201,1),True) for i in range(4))
    result=_checked(define_manifest(271828,authored=base),(FAMILY[0],))
    assert len(result.sectors[0].sites)==4
    assert all(s.identity.namespace=='authored' for s in result.sectors[0].sites)
    assert sum(s.is_topology_hub for s in result.sectors[0].sites)==1


def test_16_invalid_configuration_never_receives_certification():
    from retorno.runtime.data_loader import load_worldgen_archetypes
    for field,value in (('intersector_link_max',-1),('intersector_link_prob',1.1),
                        ('node_count_min',-1)):
        cfg=load_worldgen_archetypes()
        cfg['empty'][field]=value
        try:
            define_manifest(1,archetypes=cfg)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid rules must fail before a certified query')


def test_17_forced_procedural_short_id_collisions_do_not_change_identity_uniqueness():
    sample=manifest._sample_sector_node
    class Bits:
        def getrandbits(self,count):
            return 0
    def collide(*args):
        position,_=sample(*args)
        return position,Bits()
    with patch.object(manifest,'_sample_sector_node',side_effect=collide):
        result=_checked(define_manifest(271828))
    sites=[s for c in result.sectors for s in c.sites]
    assert len({s.legacy_id_hint for s in sites}) < len(sites)
    assert len({s.identity for s in sites}) == len({s.identity.encoded for s in sites}) == len(sites)


def main():
    tests=[f for name,f in sorted(globals().items()) if name.startswith('test_')]
    for test in tests:
        test()
    print(f"WORLDGEN MANIFEST PROTOTYPE SMOKE PASSED ({len(tests)} groups)")


if __name__ == '__main__':
    main()
