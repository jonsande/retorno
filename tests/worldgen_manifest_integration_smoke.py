"""4D-3e2 productive integration, including finite inverse physical inventory."""
from __future__ import annotations

import copy
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue
from retorno.io import save_load
from retorno.model.os import Locale
from retorno.model.world import SpaceNode, NodePoolState, sector_id_for_pos
from retorno.worldgen import generator as gen, manifest as m, catalog
from tests.sector_intel_validation_smoke import _run_intel_import

IDS = ('S+020_+020_+000', 'S+022_+020_+000', 'S+020_+022_+000',
       'S+15126_+000_+000', 'S+15126_+000_+001', 'S+000_+000_+000')


def state(seed=271828):
    return create_initial_state_prologue(seed=seed)


def generate(s, ids):
    for sid in ids:
        gen.ensure_sector_generated(s, sid)


def unchanged(s):
    return pickle.dumps(s)


def test_01_orders_grouping_later_neighbors_and_witness_seeds():
    for seed in (2, 29, 271828):
        a = state(seed)
        b, c = copy.deepcopy(a), copy.deepcopy(a)
        generate(a, IDS)
        generate(b, reversed(IDS))
        gen._ensure_sector_cluster_generated(c, list(IDS))
        assert a.world == b.world == c.world, seed
        before = unchanged(a)
        generate(a, IDS)
        assert unchanged(a) == before
        gen.validate_universe_state(a)
        for sid in a.world.generated_sectors:
            info = a.world.sector_states[sid]
            assert info.physical_inventory_complete
            assert set(info.node_ids) == {n.node_id for n in a.world.space.nodes.values()
                if sector_id_for_pos(n.x_ly,n.y_ly,n.z_ly) == sid}


def test_02_partial_inventory_save_load_and_consumption():
    a = state()
    untouched = copy.deepcopy(a)
    gen._ensure_sector_generated_core(a, (IDS[4],))
    node = next(n for n in a.world.space.nodes.values() if n.historical_key and n.kind != 'unknown')
    node.salvage_scrap_available = 0
    node.salvage_modules_available.clear()
    node.recoverable_drones_count = 0
    node.salvage_dry = True
    # Prepare the actual versioned pool before recording its consumed state.
    from retorno.core.lore import initialize_node_pool, recompute_node_completion
    initialize_node_pool(a, node.node_id)
    a.world.node_pools[node.node_id].uplink_data_consumed = True
    recompute_node_completion(a, node.node_id)
    with TemporaryDirectory() as tmp:
        slot = Path(tmp)/'new.dat'
        for _ in range(3):
            save_load.save_single_slot(a,slot)
            b = save_load.load_single_slot(slot).state
            assert a.world == b.world
            assert b.world.node_pools[node.node_id].uplink_data_consumed
            a = b
        generate(a,IDS)
        generate(untouched,reversed(IDS))
        expected = untouched.world.space.nodes[node.node_id]
        expected.salvage_scrap_available = 0
        expected.salvage_modules_available.clear()
        expected.recoverable_drones_count = 0
        expected.salvage_dry = True
        untouched.world.node_pools = copy.deepcopy(a.world.node_pools)
        assert a.world == untouched.world
        save_load.save_single_slot(a,slot)
        assert save_load.load_single_slot(slot).state.world == a.world


def test_03_pure_queries_do_not_touch_game_rng_knowledge_or_pools():
    s = state()
    s.world.node_pools['ECHO_7'] = NodePoolState(uplink_data_consumed=True)
    before, rng = unchanged(s), random.getstate()
    definition = gen.universe_definition(s)
    m.query_manifest(definition,IDS)
    physical = m.query_physical_sectors(definition,IDS)
    evidence = catalog.catalog_sectors(s,IDS)
    assert physical.complete and any(r.status == catalog.SiteStatus.VERIFIED
        for sector in evidence.sectors for r in sector.sites)
    assert unchanged(s) == before and random.getstate() == rng
    known = (copy.deepcopy(s.world.known_links),set(s.world.known_nodes),set(s.world.known_contacts),
             copy.deepcopy(s.world.node_pools),copy.deepcopy(s.os.fs),s.meta.rng_counter)
    generate(s,IDS)
    assert known == (s.world.known_links,s.world.known_nodes,s.world.known_contacts,
                     s.world.node_pools,s.os.fs,s.meta.rng_counter)
    assert random.getstate() == rng


def test_04_z_outlier_inverse_completeness_against_wider_sources():
    d = m.define_manifest(271828)
    target = IDS[4]
    result = m.query_physical_sectors(d,(target,))
    spill = next(s for s in result.sites if s.generation_sector_id == IDS[3])
    assert spill.position_ly == (151266.79157885376,9.329097599582711,10.057691279289713)
    session = m._Session(d)
    expected = {s.identity for x in range(15123,15130) for y in range(-3,4) for z in range(-3,6)
        for s in session.sector(f'S{x:+04d}_{y:+04d}_{z:+04d}').sites
        if s.physical_sector_id == target}
    assert expected == {s.identity for s in result.sites}
    a, b = state(), state()
    generate(a,(IDS[3],target))
    generate(b,(target,IDS[3]))
    assert a.world == b.world
    nid = m.operative_id(d,spill)
    assert a.world.space.nodes[nid].generation_sector_id == IDS[3]
    assert nid in a.world.sector_states[target].node_ids
    assert nid not in a.world.sector_states[IDS[3]].node_ids


def test_05_numerical_bound_extreme_uniform_and_rounding():
    # Maximum finite radius of this exact fresh CPython gauss implementation.
    upper = 1.0 - 2.0**-53
    bound = math.sqrt(-2.0*math.log(1.0-upper))
    assert 8.57 < bound < 8.58 < 9
    for angle in (0,.25,.5,.75,upper):
        rng = random.Random(0)
        with patch.object(rng,'random',side_effect=(angle,upper)):
            assert abs(rng.gauss(0,1)) < 9
    for index in (-m.MAX_SECTOR_INDEX,-1,0,1,m.MAX_SECTOR_INDEX):
        start = float(index*10)
        assert start == index*10 and start+5 == index*10+5
        for u in (0,2**-53,0.5,upper):
            value = start + 10*u
            assert index <= math.floor(value/10) <= index+1
            for sigma in (.3,.8,2):
                z = start+5 + sigma*bound
                assert abs(z-(start+5)) <= 9*sigma+2
    # At high coordinates a value below the mathematical upper boundary can
    # round into the next physical X/Y sector; inverse lookup includes it.
    index = m.MAX_SECTOR_INDEX-10
    assert float(index*10)+upper*10 == float((index+1)*10)
    edge = f'S{index:+04d}_+000_+000'
    assert m.query_physical_sectors(m.define_manifest(1),(edge,)).complete


def test_06_domain_work_bounds_and_atomic_failure():
    s = state()
    before = unchanged(s)
    for action in (
        lambda: gen.ensure_sector_generated(s,f'S{m.MAX_SECTOR_INDEX:+04d}_+000_+000'),
        lambda: gen._ensure_sector_cluster_generated(s,list(IDS)*11),
        lambda: m.query_physical_sectors(gen.universe_definition(s),list(IDS),max_sectors=1),
    ):
        try:
            action()
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid bound accepted')
        assert unchanged(s) == before
    with patch.object(gen,'_apply_salvage_profile',side_effect=ValueError('prepare failure')):
        try:
            gen.ensure_sector_generated(s,IDS[0])
        except ValueError:
            pass
        else:
            raise AssertionError('Materializer failed to exercise preparation')
    assert unchanged(s) == before
    session = m._Session(gen.universe_definition(s))
    session.sectors = dict.fromkeys(range(32768))
    try:
        session.sector(IDS[0])
    except ValueError:
        pass
    else:
        raise AssertionError('Work exhaustion returned an inventory')


def test_07_matching_reciprocity_maximality_budgets_and_hop_cap():
    d = m.define_manifest(29)
    session = m.new_session(d)
    for x in range(-5,6):
        for y in range(-5,6):
            sid = f'S{x:+04d}_{y:+04d}_+000'
            selected = session.ranked(sid)
            cap = session.archetypes[session.sector(sid).archetype]['intersector_link_max']
            assert len(selected) <= cap
            for phase in range(8):
                other = session.partner(sid,phase)
                assert session.partner(other,phase) == sid
                if session.candidate(sid,other):
                    assert sid in session.ranked(other) if other in selected else (
                        len(selected) == cap or len(session.ranked(other)) ==
                        session.archetypes[session.sector(other).archetype]['intersector_link_max'])
    result = m.query_manifest(d,IDS)
    assert all(e.left != e.right and e.distance_ly <= 45 for e in result.edges)
    assert result == m.query_manifest(d,tuple(reversed(IDS)))


def test_08_authored_declaration_is_not_revelation_or_prose():
    from retorno.bootstrap import load_locations
    locations = copy.deepcopy(load_locations())
    locations.append({'node':{'node_id':'ARC_STATION_FIXED','name':'Arc Station','kind':'station',
        'x_ly':207.0,'y_ly':208.0,'z_ly':5.0,'is_hub':True}, 'salvage':{}})
    with patch('retorno.bootstrap.load_locations',return_value=locations), \
         patch('retorno.worldgen.manifest.load_locations',return_value=locations), \
         patch('retorno.worldgen.generator.load_locations',return_value=locations):
        s = state()
        assert 'ARC_STATION_FIXED' in s.world.space.nodes
        assert 'ARC_STATION_FIXED' not in s.world.known_nodes | s.world.known_contacts
        before = (set(s.world.known_nodes),set(s.world.known_contacts),copy.deepcopy(s.world.known_links))
        gen.ensure_sector_generated(s,IDS[0])
        assert before == (s.world.known_nodes,s.world.known_contacts,s.world.known_links)
        assert m.resolve_operative_id(gen.universe_definition(s),'ARC_STATION_FIXED')
    s = state()
    before = copy.deepcopy(s.world)
    _run_intel_import(s,'A rumour mentions ARC_STATION_FIXED and a far station.\n')
    assert s.world == before
    assert 'RETORNO_SHIP' not in {a.raw_id for a in gen.universe_definition(s).authored}


def test_09_new_ids_intel_blocks_authored_links_and_coord_semantics():
    s = state()
    d = gen.universe_definition(s)
    site = next(t for c in m.query_manifest(d,(IDS[3],)).sectors for t in c.sites
                if t.physical_sector_id == IDS[4])
    nid = m.operative_id(d,site)
    assert nid not in s.world.space.nodes
    _run_intel_import(s,f'NODE: {nid}\n')
    assert nid in s.world.space.nodes and nid in s.world.known_contacts
    assert s.world.space.nodes[nid].generation_sector_id == IDS[3]
    assert IDS[4] in s.world.generated_sectors
    assert m.resolve_operative_id(d,nid) == site
    _run_intel_import(s,'LINK: ECHO_7 -> HARBOR_12\nSECTOR: S+030_+030_+000\nCOORD: 305, 305, 5\n')
    assert 'HARBOR_12' in s.world.known_contacts
    assert 'S+030_+030_+000' in s.world.generated_sectors
    coord = next(n for n in s.world.space.nodes.values() if n.kind == 'nav_point')
    assert coord.historical_key is None and coord.generation_sector_id is None
    from tests.sector_intel_validation_smoke import _assert_sector_blocks_bypass_corrupt_recovery
    _assert_sector_blocks_bypass_corrupt_recovery()


def test_10_collision_namespace_and_special_nodes_do_not_consume_quotas():
    s = state(2)
    d = gen.universe_definition(s)
    pure = m.query_manifest(d,(IDS[0],))
    s.world.space.nodes['SPECIAL'] = SpaceNode('SPECIAL','Special','station',x_ly=205,y_ly=205,z_ly=5)
    assert m.query_manifest(gen.universe_definition(s),(IDS[0],)) == pure
    gen.ensure_sector_generated(s,IDS[0])
    assert s.world.space.nodes['SPECIAL'].historical_key is None
    class Collide(random.Random):
        def getrandbits(self,k):
            return 7
    original = m._sample_sector_node
    def sample(*args):
        pos, _ = original(*args)
        return pos, Collide(1)
    with patch.object(m,'_sample_sector_node',side_effect=sample):
        sites = [t for c in m.query_manifest(d,(IDS[0],IDS[1],IDS[2])).sectors for t in c.sites]
        assert len({m.operative_id(d,t) for t in sites}) == len(sites)
    proc = next(t for c in pure.sectors for t in c.sites if t.identity.namespace == 'procedural')
    nid = m.operative_id(d,proc)
    # Operative allocation consults the immutable authored set only.
    fake = replace(d,authored=d.authored+(m.AuthoredSite(nid,'station',(0,0,0)),))
    assert m.operative_id(fake,proc) != nid
    assert m.operative_id(fake,proc) == m.operative_id(fake,proc)
    blocked = state(2)
    blocked.world.space.nodes[nid] = SpaceNode(nid,'Collision','station',x_ly=-1000)
    before = unchanged(blocked)
    try:
        gen.ensure_sector_generated(blocked,IDS[0])
    except ValueError:
        pass
    else:
        raise AssertionError('Occupied historical ID was silently reassigned')
    assert unchanged(blocked) == before


def test_11_incompatible_saves_rules_seed_and_corruption_preserve_files():
    for locale in (Locale.EN,Locale.ES):
        s = state()
        s.os.locale = locale
        generate(s,IDS[:2])
        with TemporaryDirectory() as tmp:
            slot = Path(tmp)/'old.dat'
            old = copy.deepcopy(s)
            old.meta.save_version = 2
            blob = pickle.dumps(old)
            raw = save_load._SAVE_MAGIC+b'\n'+hashlib.sha256(blob).hexdigest().encode()+b'\n'+blob
            slot.write_bytes(raw)
            try:
                save_load.load_single_slot(slot)
            except save_load.SaveLoadError as exc:
                assert ('Partida incompatible' if locale == Locale.ES else 'Save incompatible') in str(exc)
            else:
                raise AssertionError('Legacy schema silently interpreted')
            assert slot.read_bytes() == raw
            for mutate in (
                lambda v: setattr(v.meta,'rng_seed',1),
                lambda v: setattr(v.world,'universe_version','future'),
                lambda v: v.world.space.nodes.pop(next(k for k,n in v.world.space.nodes.items() if n.historical_key)),
                lambda v: setattr(next(n for n in v.world.space.nodes.values() if n.historical_key),'is_hub',not next(n for n in v.world.space.nodes.values() if n.historical_key).is_hub),
                lambda v: setattr(next(n for n in v.world.space.nodes.values() if n.historical_key),'x_ly',-1000),
            ):
                bad = copy.deepcopy(s)
                mutate(bad)
                try:
                    save_load.save_single_slot(bad,slot)
                except save_load.SaveLoadError:
                    pass
                else:
                    raise AssertionError('Incoherent universe saved')
                assert slot.read_bytes() == raw
            with patch.object(m,'physical_rules_key',return_value='different'):
                try:
                    save_load.save_single_slot(s,slot)
                except save_load.SaveLoadError:
                    pass
                else:
                    raise AssertionError('Changed physical configuration accepted')


def test_12_unknown_cleanup_and_authored_properties_preserved():
    s = state()
    base = {nid:asdict(n) for nid,n in s.world.space.nodes.items()}
    generate(s,IDS)
    for nid,before in base.items():
        after = asdict(s.world.space.nodes[nid])
        for key in before.keys()-{'links','is_hub','is_topology_hub','historical_key','generation_sector_id'}:
            assert before[key] == after[key], (nid,key)
    del s.world.space.nodes['UNKNOWN']
    gen.ensure_sector_generated(s,'S+001_+001_+000')
    assert 'UNKNOWN' not in s.world.space.nodes


def test_13_hashseed_process_determinism():
    code = '''import hashlib,pickle,json
from tests.worldgen_manifest_integration_smoke import state, generate, IDS
from dataclasses import asdict
s=state(29)
generate(s, IDS)
def normalize(v):
 if isinstance(v,dict): return {k:normalize(v[k]) for k in sorted(v)}
 if isinstance(v,(set,frozenset)): return sorted(normalize(x) for x in v)
 if isinstance(v,(tuple,list)): return [normalize(x) for x in v]
 return v
print(hashlib.sha256(json.dumps(normalize(asdict(s.world)),sort_keys=True).encode()).hexdigest())'''
    results = [subprocess.check_output([sys.executable,'-c',code],env=dict(os.environ,PYTHONHASHSEED=str(seed)),text=True)
               for seed in (1,19,971)]
    assert len(set(results)) == 1, results


def test_14_seed_command_compatibility_and_localization():
    from retorno.cli import repl
    from retorno.cli.parser import parse_command
    assert parse_command('debug seed 29') == ('DEBUG_SEED',29)
    s = state(29)
    assert repl.debug_seed_block_reason(s,29) is None
    assert 'blocked' in repl.debug_seed_block_reason(s,2)
    gen.pin_universe(s)
    before = unchanged(s)
    for locale,word in ((Locale.EN,'blocked'),(Locale.ES,'bloqueado')):
        s.os.locale = locale
        assert word in repl.debug_seed_block_reason(s,2)
        assert repl.debug_seed_block_reason(s,29) is None
    s.os.locale = Locale.EN
    assert unchanged(s) == before
    tampered = copy.deepcopy(s)
    tampered.meta.rng_seed = 2
    try:
        gen.universe_definition(tampered)
    except ValueError as exc:
        assert "seed/version changed" in str(exc)
    else:
        raise AssertionError("A pinned universe accepted a different seed")
    assert unchanged(s) == before


def main():
    tests = [v for k,v in sorted(globals().items()) if k.startswith('test_')]
    for test in tests:
        test()
        print('PASS',test.__name__,flush=True)
    print(f'WORLDGEN MANIFEST INTEGRATION SMOKE PASSED ({len(tests)} groups)')


if __name__ == '__main__':
    main()
