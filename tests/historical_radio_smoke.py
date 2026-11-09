"""B2 contracts, bounded discovery, receipt evidence and real UI parity.

Synthetic probes are labelled and never used as public gameplay evidence.
The delivered public walkthrough starts from the unmodified prologue.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import asdict, replace
from functools import lru_cache
import itertools
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

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core import communications as comms, lore, structural_recovery as recovery
from retorno.io import save_load
from retorno.model.os import Locale
from retorno.worldgen import historical_radio as hr, information, manifest
from retorno.worldgen.generator import universe_definition, ensure_sector_generated, ensure_historical_node
from retorno.worldgen.narrative import fingerprint
from structural_recovery_smoke import ready, scene, at, SMALL, read
from knowledge_boundary_smoke import public
from passive_communications_smoke import capture_output

SEEDS = (0, 1, 2, 7, 42, 137, 2026, 65535, 271828, 314159, 8675309, 2147483647)
SECTORS = tuple('S'+'_'.join(f'{v:+04d}' for v in offset) for offset in itertools.product(range(-1, 2), repeat=3))


def host(state, ident):
    return hr.query_host(universe_definition(state), state.world.radio_definition, state.world.information_definition, ident)


@lru_cache(maxsize=12)
def samples(seed=0):
    s = create_initial_state_prologue(seed=seed)
    w = universe_definition(s)
    inventory = manifest.query_physical_sectors(w, SECTORS)
    records = tuple(hr.query_host(w, s.world.radio_definition, s.world.information_definition,
        manifest.operative_id(w, site)) for site in inventory.sites if site.kind in hr.KINDS)
    return s, records


def chosen(predicate, seeds=SEEDS):
    for seed in seeds:
        s, rows = samples(seed)
        for row in rows:
            if predicate(row):
                return deepcopy(s), row
    raise AssertionError('Required deterministic witness missing')


def prepare(s, record):
    signal = record.emissions[0]
    return comms.prepare_radio_opportunity(s, 'radio:'+signal.emission_id, signal.channel,
        signal.content_by_locale, node_id=record.emitter.host_id, trigger='contract_probe',
        emission_id=signal.emission_id, delivery={'kind': 'declared_radio'})


def reject(callback):
    try:
        callback()
    except (ValueError, save_load.SaveLoadError):
        return
    raise AssertionError('Expected explicit contract rejection')


def test_01_original_equipment_all_classes_and_three_conservation_states():
    s, rows = samples()
    assert {r.host.kind for r in rows} == set(hr.KINDS)
    assert {r.equipment_at(0).hardware for r in rows} == {'serviceable', 'damaged', 'destroyed'}
    for row in rows:
        assert row.equipment_at(0).installed
        assert not row.equipment_at(row.installed_t-1).installed
        assert row.equipment_at(row.installed_t).operational
        if row.failure_t is not None:
            assert row.equipment_at(row.failure_t-1).hardware == 'serviceable'
            assert row.equipment_at(row.failure_t).hardware == row.final_hardware


def test_02_energy_capability_and_program_are_separate():
    _, rows = samples()
    assert any(r.final_hardware == 'serviceable' and not r.equipment_at(0).powered for r in rows)
    assert any(r.equipment_at(0).operational and not r.emissions for r in rows)
    assert any(not r.equipment_at(0).operational and r.emissions for r in rows)
    for kind, target in dict(station=.4, relay=.65, waystation=.5, ship=.1, derelict=.05).items():
        assert math.isclose(Balance.HISTORICAL_RADIO_SERVICEABLE[kind]*Balance.HISTORICAL_RADIO_POWERED[kind], target)


def test_03_destruction_after_distress_and_archives_survive_radio():
    s, row = chosen(lambda r: r.final_hardware == 'destroyed' and r.message_kind == 'distress')
    signal = row.emissions[0]
    assert signal.end_t <= row.failure_t and row.equipment_at(signal.start_t).operational
    archive = information.query_information(universe_definition(s), s.world.information_definition, row.emitter.host_id)
    assert archive and archive.files and not row.equipment_at(0).operational


def test_04_continuous_and_finite_traffic_with_silent_hosts():
    _, rows = samples()
    assert {e.mode for r in rows for e in r.emissions} == {'continuous', 'finite'}
    assert any(not r.emissions for r in rows)
    assert any(e.end_t is None for r in rows for e in r.emissions)
    assert any(e.end_t is not None for r in rows for e in r.emissions)
    for row in rows:
        for e in row.emissions:
            assert row.equipment_at(e.start_t).operational
            assert row.installed_t <= e.start_t
            if row.failure_t is not None:
                assert e.end_t is not None and e.end_t <= row.failure_t
            if row.energy_end_t is not None:
                assert e.end_t is not None and e.end_t <= row.energy_end_t


def test_05_navigation_only_from_b1_and_bilingual_non_navigation_payloads():
    s, rows = samples()
    for row in rows:
        for e in row.emissions:
            assert e.piece_key is None and set(e.content_by_locale) == {'en', 'es'}
            assert e.time_reference == 'game-coordinate-seconds-v1'
            assert all(row.source_record_id in text for text in e.content_by_locale.values())
            if row.navigation_record:
                archive = information.query_information(universe_definition(s), s.world.information_definition, row.emitter.host_id)
                records = list(archive.uplink)+[information.NavigationRecord(**f['navigation_record']) for f in archive.files if f.get('navigation_record')]
                assert row.navigation_record in records
                target = manifest.resolve_operative_id(universe_definition(s), e.navigation_link_to)
                assert target and 0 < math.dist(row.host.position_ly, target.position_ly) <= 45
                for text in e.content_by_locale.values():
                    assert f'LINK: {row.emitter.host_id} -> {e.navigation_link_to}' in text
            else:
                assert not e.navigation_link_to
                assert all('LINK:' not in text and row.emitter.host_id not in text for text in e.content_by_locale.values())


def test_06_light_delay_finite_window_and_post_destruction_wave():
    s, row = chosen(lambda r: r.emissions and r.final_hardware == 'destroyed' and r.emitter.category == 'interstellar_relay')
    e = row.emissions[0]
    s.world.current_pos_ly = tuple(v+(2 if i == 0 else 0) for i,v in enumerate(row.host.position_ly))
    delay = 2*Balance.YEAR_S
    for t, reason in ((e.start_t+delay-1,'signal_not_arrived'), (e.start_t+delay,None), (e.end_t+delay,'signal_passed')):
        s.clock.t = t
        assert comms.radio_temporal_block_reason(s, row.emitter, e) == reason
    s.clock.t = e.end_t+delay-1
    assert s.clock.t > row.failure_t or e.end_t < row.failure_t
    assert comms.radio_temporal_block_reason(s, row.emitter, e) is None


def test_07_power_sensitivity_three_dimensions_and_movement():
    s, row = chosen(lambda r: r.emissions and r.emissions[0].end_t is None)
    for sensitivity in (.25, 1., 2.25):
        radius = math.sqrt(row.emitter.power*sensitivity)
        for d, decodable in ((radius,True),(radius+.0001,False)):
            assert comms.radio_link_budget(row.emitter.power,sensitivity,d)['decodable'] == decodable
    s.clock.t = 0
    s.world.current_pos_ly = row.host.position_ly
    assert comms.radio_link_metrics(s,row.emitter,row.emissions[0])['temporally_available']
    s.world.current_pos_ly = tuple(v+100 for v in row.host.position_ly)
    assert not comms.radio_link_metrics(s,row.emitter,row.emissions[0])['decodable']


def test_08_pure_lazy_time_knowledge_locale_rng_and_no_physical_changes():
    s, rows = samples()
    row = next(r for r in rows if r.host.identity.namespace == 'procedural')
    baseline = host(s,row.emitter.host_id)
    assert row.emitter.host_id not in s.world.space.nodes
    for t, locale in ((0,Locale.EN),(123,Locale.ES),(1e12,Locale.EN)):
        variant = deepcopy(s)
        variant.clock.t, variant.os.locale = t, locale
        variant.world.known_nodes.update(('HIDDEN','HARBOR_12'))
        variant.world.known_links = {'INVENTED': {'UNRELATED'}}
        variant.meta.rng_counter += 900
        variant.world.recovery_searches['global'] = {'cursor': 777}
        before, rng = pickle.dumps(variant), random.getstate()
        assert host(variant,row.emitter.host_id) == baseline
        assert pickle.dumps(variant) == before and random.getstate() == rng


def test_09_materialization_and_query_order_preserve_radio_and_b1():
    s, rows = samples()
    targets = [r.emitter.host_id for r in rows[:6]]
    before = {nid: (host(s,nid), lore.historical_information_for_node(s,nid)) for nid in targets}
    a,b = deepcopy(s),deepcopy(s)
    for sid in SECTORS[:3]: ensure_sector_generated(a,sid)
    for sid in reversed(SECTORS[:3]): ensure_sector_generated(b,sid)
    for target in reversed(targets):
        assert (host(a,target),lore.historical_information_for_node(a,target)) == before[target]
        assert (host(b,target),lore.historical_information_for_node(b,target)) == before[target]


def test_10_hash_seeds_twelve_universes():
    code = '''
from retorno.bootstrap import create_initial_state_prologue
from retorno.worldgen.historical_radio import query_host
from retorno.worldgen.generator import universe_definition
from retorno.worldgen.narrative import fingerprint
from dataclasses import asdict
print([fingerprint(asdict(query_host(universe_definition(s),s.world.radio_definition,s.world.information_definition,'ECHO_7'))) for s in [create_initial_state_prologue(seed=x) for x in (0,1,2,7,42,137,2026,65535,271828,314159,8675309,2147483647)]])
'''
    outputs = [subprocess.check_output([sys.executable,'-c',code],env=dict(os.environ,PYTHONHASHSEED=value),text=True) for value in ('0','137','987654321')]
    assert outputs[0] == outputs[1] == outputs[2]


def test_11_authored_precedence_including_silent_explicit_hardware():
    from radio_spacetime_smoke import installed
    with installed() as _:
        s = create_initial_state_sandbox()
        assert host(s,'RADIO_REMOTE') is None
        assert hr.resolve_emission(s,'fixture-history')[1].emission_id == 'fixture-history'
    s = scene(radio_links=())
    s.world.information_version = information.VERSION
    s.world.information_definition = information.define_information(s.world.narrative_snapshot)
    s.world.radio_history_version = hr.VERSION
    s.world.radio_definition = hr.define_radio(s.world.narrative_snapshot,s.world.information_definition)
    assert host(s,'A') is not None
    from retorno.worldgen.radio import compile_radio
    s.world.narrative_snapshot['locations'][0]['radio_emitters']['emitters'] = [dict(id='silent',host='A',category='station',emissions=[])]
    compile_radio(universe_definition(s),s.world.narrative_snapshot)
    s.world.radio_definition = hr.define_radio(s.world.narrative_snapshot,s.world.information_definition)
    assert host(s,'A') is None and not s.world.narrative_snapshot['radio_emissions']


def dense():
    spec = [('A' if i == 0 else f'H{i:03}', 'relay', (1000.+i*.001,1000.,1000.)) for i in range(300)]
    s = scene(spec,radio_links=(),known=('A',),clean=False)
    s.world.information_version = information.VERSION
    s.world.information_definition = information.define_information(s.world.narrative_snapshot)
    s.world.radio_history_version = hr.VERSION
    s.world.radio_definition = hr.define_radio(s.world.narrative_snapshot,s.world.information_definition)
    return s


def test_12_crowded_cell_resume_no_loss_over_128_and_finite_pages():
    s = dense(); w = universe_definition(s); cursor = None; found = {}; counts=[]
    before = pickle.dumps(s)
    for _ in range(10):
        p = hr.query_local(w,s.world.radio_definition,s.world.information_definition,s.world.current_pos_ly,
            cursor=cursor,limit=32,sector_budget=1)
        assert p.examined_sites <= 32 and p.examined_sectors <= 1 and not p.complete
        for r in p.histories:
            assert r.emitter.host_id not in found
            found[r.emitter.host_id] = r
        counts.append(p.examined_sites);cursor=p.cursor
        if cursor['cell'] > 0: break
    ids = ['A' if i == 0 else f'H{i:03}' for i in range(300)]
    expected = {nid for nid in ids if host(s,nid).emissions}
    assert set(found) == expected and len(counts) > 4 and len(found) > 128
    assert pickle.dumps(s) == before
    reject(lambda: hr.query_local(w,s.world.radio_definition,s.world.information_definition,s.world.current_pos_ly,limit=0))


def test_13_local_domain_complete_and_completed_search_never_rebuilds_inventory():
    s = create_initial_state_prologue(seed=0);w=universe_definition(s)
    cursor=None;found={};pages=0
    while True:
        page=hr.query_local(w,s.world.radio_definition,s.world.information_definition,(0.,0.,0.),cursor=cursor,limit=128,sector_budget=32)
        pages+=1
        for row in page.histories:
            assert row.emitter.host_id not in found
            found[row.emitter.host_id]=row
        cursor=page.cursor
        if page.complete: break
        assert pages < 40
    anchor,sectors=hr.local_domain((0.,0.,0.),s.world.radio_definition)
    session=manifest.new_session(w)
    expected={}
    for offset in range(0,len(sectors),64):
        inventory=manifest._physical_inventory(session,sectors[offset:offset+64])
        for site in inventory.sites:
            row=hr.query_host(w,s.world.radio_definition,s.world.information_definition,manifest.operative_id(w,site),session=session)
            if row and row.emissions: expected[row.emitter.host_id]=row
    assert expected == found
    with patch.object(manifest,'_physical_inventory',side_effect=AssertionError('Unnecessary rescan')):
        again=hr.query_local(w,s.world.radio_definition,s.world.information_definition,(9.,9.,9.),cursor=cursor)
    assert again.complete and not again.histories and again.examined_sectors == 0


def test_14_capture_uses_common_ledger_radiod_and_no_implicit_intel():
    s,row=chosen(lambda r: r.emissions and r.emissions[0].end_t is None and r.message_kind != 'navigation')
    ready(s);s.world.current_pos_ly=row.host.position_ly
    op=prepare(s,row);history=host(s,row.emitter.host_id)
    s.ship.systems['comms'].service.is_running=False
    assert comms.capture_radio_opportunity(s,op) is None
    assert host(s,row.emitter.host_id)==history
    s.ship.systems['comms'].service.is_running=True
    knowledge=deepcopy((s.world.known_nodes,s.world.known_links,s.world.intel))
    event=comms.capture_radio_opportunity(s,op)
    assert event and op.status=='received' and comms.capture_radio_opportunity(s,op) is None
    assert prepare(s,row) is op
    assert (s.world.known_nodes,s.world.known_links,s.world.intel)==knowledge
    assert row.emitter.host_id not in str(event) and row.emitter.host_id not in op.path
    assert 'opportunity_id' not in event.data
    comms.mark_radio_read(s,op.path)
    assert op.status=='read_imported'


def test_15_live_primary_filter_and_hidden_outputs_en_es():
    s,row=chosen(lambda r: r.emissions and r.emissions[0].end_t is None and r.message_kind=='navigation')
    ready(s);s.world.current_pos_ly=row.host.position_ly
    e=row.emissions[0];op=prepare(s,row)
    arc=dict(arc_id='protected_b2',primary_intel=dict(kind='link',line=f'LINK: {row.emitter.host_id} -> {e.navigation_link_to}'))
    before=host(s,row.emitter.host_id)
    with patch.object(lore,'load_arcs',return_value=[arc]), patch.dict(s.world.narrative_snapshot, arcs=[arc]):
        assert comms.capture_radio_opportunity(s,op) is None
        assert host(s,row.emitter.host_id)==before
    for locale in Locale:
        s.os.locale=locale
        observed=public(s)
        hidden=deepcopy(s)
        hidden.world.procedural_radio_search={'SECRET':'UNKNOWN'}
        hidden.world.radio_definition=replace(s.world.radio_definition,rules_key='SECRET')
        assert public(hidden)==observed


def test_16_save_before_arrival_after_capture_and_read_no_duplicate():
    s,row=chosen(lambda r: r.emissions and r.emissions[0].end_t is None)
    ready(s);s.world.current_pos_ly=row.host.position_ly
    op=prepare(s,row);s.clock.t=row.emissions[0].start_t-1
    # Controlled negative historical clock probes the propagation boundary.
    op.prepared_t=s.clock.t
    with TemporaryDirectory() as folder:
        p=Path(folder)/'radio.dat'
        save_load.save_single_slot(s,p);s=save_load.load_single_slot(p).state
        op=s.world.radio_opportunities[op.opportunity_id]
        assert comms.capture_radio_opportunity(s,op) is None
        s.clock.t=0
        assert comms.capture_radio_opportunity(s,op)
        save_load.save_single_slot(s,p);s=save_load.load_single_slot(p).state
        op=s.world.radio_opportunities[op.opportunity_id]
        assert comms.capture_radio_opportunity(s,op) is None
        comms.mark_radio_read(s,op.path)
        save_load.save_single_slot(s,p);loaded=save_load.load_single_slot(p).state
        assert loaded.world.radio_opportunities==s.world.radio_opportunities


def test_17_saved_cursor_cache_and_receipt_forgery_rejected_nondestructively():
    s=create_initial_state_prologue(seed=0);ready(s)
    comms.discover_historical_radio(s,set(),budget=3)
    with TemporaryDirectory() as folder:
        p=save_load.save_single_slot(s,Path(folder)/'cursor.dat');original=p.read_bytes()
        again=save_load.load_single_slot(p).state
        assert again.world.procedural_radio_search==s.world.procedural_radio_search
        comms.discover_historical_radio(s,set(),budget=3)
        comms.discover_historical_radio(again,set(),budget=3)
        assert again.world.procedural_radio_search==s.world.procedural_radio_search
        bad=deepcopy(again);bad.world.procedural_radio_search['cursor']['offset']=999999
        reject(lambda: save_load.save_single_slot(bad,p));assert p.read_bytes()==original
    s,row=chosen(lambda r: r.emissions and r.emissions[0].end_t is None)
    ready(s);s.world.current_pos_ly=row.host.position_ly;op=prepare(s,row)
    assert comms.capture_radio_opportunity(s,op)
    op.received_position_ly=tuple(v+1000 for v in row.host.position_ly)
    reject(lambda: comms.validate_radio_state(s))


def test_18_recovery_certified_procedural_notice_no_fabrication():
    locked = lore._locked_primary_targets(create_initial_state_prologue(seed=SEEDS[0]))
    s,row=chosen(lambda r: r.host.kind in recovery.HUBS and r.message_kind=='navigation'
                 and r.emissions[0].end_t is None and r.emitter.host_id not in locked
                 and r.emissions[0].navigation_link_to not in locked)
    nid=row.emitter.host_id;dest=row.emissions[0].navigation_link_to
    ensure_historical_node(s,nid);ensure_historical_node(s,dest);at(s,nid)
    s.world.known_nodes={nid};s.world.known_contacts={nid};s.world.known_links={};s.world.visited_nodes={nid}
    history=host(s,nid);physical=fingerprint(asdict(universe_definition(s)))
    result=recovery.select_recovery(s,'b2',dest,budget=SMALL)
    assert result.status=='validated',(result.status,result.reason)
    assert result.proposal.first_emission_id==row.emissions[0].emission_id
    plan=recovery.confirm_recovery(s,result.proposal)
    op=s.world.radio_opportunities['radio:'+row.emissions[0].emission_id]
    ready(s);assert comms.capture_radio_opportunity(s,op)
    assert plan.captured==(0,) and not s.world.known_links
    read(s,op.path)
    assert dest in s.world.known_links[nid] and plan.status=='stage_consumed'
    at(s,dest);recovery.advance_recovery_plans(s)
    assert plan.status=='complete'
    assert host(s,nid)==history and fingerprint(asdict(universe_definition(s)))==physical
    with TemporaryDirectory() as folder:
        p=save_load.save_single_slot(s,Path(folder)/'recovery.dat')
        again=save_load.load_single_slot(p).state
        assert again.world.recovery_plans==s.world.recovery_plans


def test_19_recovery_environmental_silent_and_budget_are_not_navigation_authority():
    s,row=chosen(lambda r: r.host.kind in recovery.HUBS and r.emissions and r.message_kind != 'navigation')
    ensure_historical_node(s,row.emitter.host_id);at(s,row.emitter.host_id)
    s.world.known_nodes={row.emitter.host_id};s.world.known_contacts={row.emitter.host_id};s.world.known_links={}
    before=pickle.dumps(s)
    result=recovery.select_recovery(s,'b2',budget=replace(SMALL,radio_hosts=0))
    assert result.status in {'conditional','incomplete'} and not s.world.recovery_plans
    assert pickle.dumps(s)==before and host(s,row.emitter.host_id)==row
    entries,complete=recovery._navigation_emissions(s,{row.emitter.host_id:row.host},host_budget=0)
    assert not complete and not entries


def test_20_profiles_share_equipment_and_nested_emission_history():
    s,rows=samples();physical=universe_definition(s)
    definitions=[hr.define_radio(s.world.narrative_snapshot,s.world.information_definition,profile=p) for p in ('sparse','intermediate','abundant')]
    counts=[]
    for definition in definitions:
        count=0
        for r in rows:
            record=hr.query_host(physical,definition,s.world.information_definition,r.emitter.host_id)
            assert record.equipment_at(0)==r.equipment_at(0)
            count+=bool(record.emissions)
        counts.append(count)
    assert counts[0] < counts[1] < counts[2]
    with patch.object(Balance,'HISTORICAL_RADIO_SERVICEABLE',{k:0 for k in hr.KINDS}):
        assert host(s,'ECHO_7')==next(r for r in rows if r.emitter.host_id=='ECHO_7')
        reject(lambda: hr.validate_definition(s.world.radio_definition,s.world.information_definition,current=True))


def test_21_bilingual_textual_input_reads_real_procedural_capture():
    from retorno.ui_textual.app import RetornoTextualApp
    from textual.widgets import Input
    async def run(locale):
        with patch.dict(os.environ,{'RETORNO_SCENARIO':'sandbox'}):
            app=RetornoTextualApp(force_new_game=True)
        s=app.loop.state
        # Controlled integration: the separate public walkthrough owns repairs.
        ready(s);s.os.locale=locale;s.os.audio.enabled=s.os.audio.ambient_enabled=False
        w=universe_definition(s)
        sites=manifest.query_physical_sectors(w,SECTORS).sites
        rows=[hr.query_host(w,s.world.radio_definition,s.world.information_definition,manifest.operative_id(w,x)) for x in sites if x.kind in hr.KINDS]
        row=next(r for r in rows if r and r.emissions and r.emissions[0].end_t is None)
        s.world.current_pos_ly=row.host.position_ly
        op=prepare(s,row);assert comms.capture_radio_opportunity(s,op)
        app._play_startup_sequence=app._startup_panel_blackout=False
        async with app.run_test() as pilot:
            app.loop.set_auto_tick(False)
            widget=app.query_one('#input',Input);widget.value='cat '+op.path
            await pilot.press('enter');await pilot.pause()
            assert op.status=='read_imported'
            assert any(row.emissions[0].content_by_locale[locale.value].splitlines()[0] in line for line in app._log_buffer)
    for locale in Locale: asyncio.run(run(locale))


def test_22_reuse_procedural_later_receipt_without_rewriting_file():
    # Synthetic fixed geography; histories remain generated before activation.
    selected=None
    for seed in range(128):
        s=scene([('A','station',(1000.,1000.,1000.)),('B','relay',(1003.,1000.,1000.)),
            ('C','ship',(1006.,1000.,1000.))],seed=seed,radio_links=(('A','B'),),clean=False)
        s.world.information_version=information.VERSION
        s.world.information_definition=information.define_information(s.world.narrative_snapshot)
        s.world.radio_history_version=hr.VERSION
        s.world.radio_definition=hr.define_radio(s.world.narrative_snapshot,s.world.information_definition)
        row=host(s,'B')
        if row.emissions and row.emissions[0].end_t is None and row.emissions[0].navigation_link_to=='C':
            selected=(s,row);break
    assert selected is not None
    s,row=selected;ready(s)
    op=prepare(s,row);assert comms.capture_radio_opportunity(s,op)
    original_path,original_t=op.path,op.received_t
    plan_result=recovery.select_recovery(s,'reuse','C',budget=SMALL)
    assert plan_result.status=='validated',(plan_result.status,plan_result.reason)
    assert plan_result.proposal.mechanisms==('radio','radio')
    plan=recovery.confirm_recovery(s,plan_result.proposal)
    first=s.world.radio_opportunities[recovery._radio_id(plan,0)]
    assert comms.capture_radio_opportunity(s,first);read(s,first.path)
    files=deepcopy(s.os.fs)
    at(s,'B');recovery.advance_recovery_plans(s)
    assert plan.captured==(0,1) and op.path==original_path and op.received_t==original_t
    assert s.os.fs==files and comms.capture_radio_opportunity(s,op) is None
    read(s,op.path);at(s,'C');recovery.advance_recovery_plans(s)
    assert plan.status=='complete'


def test_23_authored_and_procedural_listening_share_capture_ledger():
    from radio_spacetime_smoke import installed
    with installed():
        # Module catalogue additions change the universe fingerprint. Select a
        # certified overlap witness instead of assuming seed 1 always has one.
        row = None
        for seed in SEEDS:
            s=create_initial_state_sandbox(seed=seed);ready(s);w=universe_definition(s)
            tx,authored=hr.resolve_emission(s,'fixture-history')
            source=manifest.resolve_operative_id(w,tx.host_id)
            sites=manifest.query_physical_sectors(w,SECTORS).sites
            rows=[hr.query_host(w,s.world.radio_definition,s.world.information_definition,manifest.operative_id(w,x)) for x in sites if x.kind in hr.KINDS]
            row=next((r for r in rows if r and r.emissions and r.emissions[0].end_t is None
                and math.dist(r.host.position_ly,source.position_ly)<9+math.sqrt(r.emitter.power)), None)
            if row is not None:
                break
        assert row is not None, 'No certified radio overlap witness'
        distance=math.dist(row.host.position_ly,source.position_ly)
        fraction=min(1.,9/distance) if distance else 0.
        s.world.current_pos_ly=tuple(a+(b-a)*fraction for a,b in zip(source.position_ly,row.host.position_ly))
        for _ in range(130): comms.retry_radio_opportunities(s)
        assert s.world.radio_opportunities['radio:fixture-history'].status=='received'
        op=s.world.radio_opportunities['radio:'+row.emissions[0].emission_id]
        assert op.status=='received' and op.emission.piece_key is None
        assert len({o.emission.emission_id for o in s.world.radio_opportunities.values() if o.emission})==len(s.world.radio_opportunities)
        assert not s.world.lore.delivered


def test_24_finished_wave_captured_after_hardware_destruction_save_and_passage():
    s,row=chosen(lambda r: r.final_hardware=='destroyed' and r.emissions
        and r.emissions[0].end_t is not None and -r.emissions[0].end_t/Balance.YEAR_S < math.sqrt(r.emitter.power)-.01)
    e=row.emissions[0];d=-e.end_t/Balance.YEAR_S+.005
    s.world.current_pos_ly=tuple(v+(d if i==0 else 0) for i,v in enumerate(row.host.position_ly))
    ready(s);s.clock.t=0;op=prepare(s,row)
    assert not row.equipment_at(0).operational and comms.capture_radio_opportunity(s,op)
    assert op.received_t>row.failure_t
    with TemporaryDirectory() as folder:
        p=save_load.save_single_slot(s,Path(folder)/'after-destruction.dat');again=save_load.load_single_slot(p).state
        assert again.world.radio_opportunities==s.world.radio_opportunities
        again.clock.t=e.end_t+d*Balance.YEAR_S+1
        assert comms.radio_temporal_block_reason(again,row.emitter,e)=='signal_passed'
        assert comms.capture_radio_opportunity(again,again.world.radio_opportunities[op.opportunity_id]) is None


def test_25_debug_local_history_remains_explicit_and_read_only_en_es():
    from retorno.cli import repl
    s=create_initial_state_prologue(seed=0);ready(s)
    comms.discover_historical_radio(s,set(),budget=8)
    for locale in Locale:
        s.os.locale=locale;s.os.debug_enabled=False
        denied=capture_output(repl.render_debug_radio,s)
        assert 'historical_radio_cached_hosts' not in denied
        s.os.debug_enabled=True
        before,rng=pickle.dumps(s),random.getstate()
        observed=capture_output(repl.render_debug_radio,s)
        assert 'historical_radio_cached_hosts=' in observed
        assert pickle.dumps(s)==before and random.getstate()==rng


def test_26_authored_testimony_cannot_forge_b1_radio_navigation_provenance():
    # An authored file may be testimony; metadata names do not certify a LINK.
    s=scene([('A','station',(1000.,1000.,1000.)),('B','ship',(1003.,1000.,1000.))],radio_links=())
    snapshot=deepcopy(s.world.narrative_snapshot)
    file=dict(path='/logs/false.txt',content='LINK: B -> NONEXISTENT',
        information_version=information.VERSION,navigation_record=dict(record_id='forged',source_id='B',
            destination_id='NONEXISTENT',kind='navigation_solution',distance_ly=1.,relation=None))
    snapshot['locations'][1]['fs_files']=[file]
    definition=information.define_information(snapshot)
    radio=hr.define_radio(snapshot,definition)
    for seed in range(10):
        probe=scene([('A','station',(1000.,1000.,1000.)),('B','ship',(1003.,1000.,1000.))],seed=seed,radio_links=())
        physical=universe_definition(probe)
        row=hr.query_host(physical,radio,definition,'B')
        assert row.navigation_record is None
        assert all(e.navigation_link_to is None and 'LINK:' not in e.content_by_locale['en'] for e in row.emissions)


def test_27_cache_capacity_rotates_without_permanent_cell_bias_and_roundtrips():
    s=create_initial_state_prologue(seed=42);ready(s);physical=universe_definition(s)
    expected=set();cursor=None
    while True:
        page=hr.query_local(physical,s.world.radio_definition,s.world.information_definition,(0.,0.,0.),
            cursor=cursor,limit=128,sector_budget=64)
        expected.update(r.emitter.host_id for r in page.histories);cursor=page.cursor
        if page.complete: break
    seen=set();saved=False
    with patch.object(Balance,'HISTORICAL_RADIO_LOCAL_HOST_LIMIT',3), TemporaryDirectory() as folder:
        for tick in range(1600):
            comms.discover_historical_radio(s,set(),budget=64)
            search=s.world.procedural_radio_search
            assert len(search['histories'])<=3
            seen.update(search['histories'])
            if not saved and 'window_start' in search and search['window_start']['cell']>0:
                p=save_load.save_single_slot(s,Path(folder)/'overflow.dat')
                again=save_load.load_single_slot(p).state
                assert again.world.procedural_radio_search==search
                for _ in range(3):
                    comms.discover_historical_radio(s,set(),budget=64)
                    comms.discover_historical_radio(again,set(),budget=64)
                    assert again.world.procedural_radio_search==s.world.procedural_radio_search
                    seen.update(s.world.procedural_radio_search['histories'])
                bad=deepcopy(again);bad.world.procedural_radio_search['window_remaining']=-1
                reject(lambda: hr.validate_state(bad))
                saved=True
            if seen==expected: break
        assert saved and seen==expected,(len(seen),len(expected),tick)
        # Reach a new lap rather than permanently staying on the final cell.
        last=(s.world.procedural_radio_search['cursor']['cell'],s.world.procedural_radio_search['cursor']['offset'])
        wrapped=False
        for _ in range(100):
            comms.discover_historical_radio(s,set(),budget=64)
            current=(s.world.procedural_radio_search['cursor']['cell'],s.world.procedural_radio_search['cursor']['offset'])
            if current<last: wrapped=True;break
            last=current
        assert wrapped


def main():
    for name, fn in sorted(globals().copy().items()):
        if name.startswith('test_'):
            fn();print('PASS',name,flush=True)
    print('HISTORICAL RADIO: 27 GROUPS PASS')


if __name__=='__main__': main()
