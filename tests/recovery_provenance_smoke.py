"""Focused e5b correction: existing content, never retrospective rescue messages."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory

from retorno.core import communications as radio, structural_recovery as rec, lore
from retorno.io import save_load
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.world import DeadNodeState, NodePoolState
from retorno.ui_textual import presenter
from retorno.cli import repl
from retorno.worldgen.radio import compile_radio
from structural_recovery_smoke import scene, ready, at, read, pure, SMALL, reject
from passive_communications_smoke import capture_output
from radio_spacetime_smoke import installed, nav_emission, emission, recovery_state, select

LEGACY = Path(__file__).parent/'fixtures/recovery_legacy/pending-v1.dat'


def result(s,target='B'):
    return pure(s,'provenance',target,budget=SMALL)


def unchanged_failure(s,target='B'):
    before=deepcopy((s.ship,s.os,s.events,s.world.space,s.world.known_nodes,s.world.known_links,
        s.world.intel,s.world.node_pools,s.world.dead_nodes,s.world.mobility_failsafe_count))
    rec.request_recovery(s,'provenance',target)
    assert not s.world.recovery_plans and not s.world.radio_opportunities
    assert s.world.recovery_searches['provenance']['status'] in {'conditional','incomplete','none_in_scope','invalid'}
    assert before==(s.ship,s.os,s.events,s.world.space,s.world.known_nodes,s.world.known_links,
        s.world.intel,s.world.node_pools,s.world.dead_nodes,s.world.mobility_failsafe_count)


def test_01_historical_hub_is_not_transmitter_or_payload():
    for kind in ('station','relay','waystation'):
        s=scene([('A',kind,(1000.,1000.,1000.)),('B','ship',(1003.,1000.,1000.))],radio_links=())
        assert result(s).status=='conditional'
        assert rec._first_reception(s,'A')=='first_emission_undeclared'
        unchanged_failure(s)


def test_02_declared_transmitter_without_activity_cannot_start_recovery():
    s=scene();s.world.narrative_snapshot['locations'][0]['radio_emitters']['emitters'][0]['emissions']=[]
    compile_radio(s.world.manifest_definition,s.world.narrative_snapshot)
    assert s.world.narrative_snapshot['radio_emitters'] and not s.world.narrative_snapshot['radio_emissions']
    unchanged_failure(s)


def test_03_unrelated_notice_cannot_be_replaced_by_requested_link():
    s=scene([('A','station',(1000.,1000.,1000.)),('B','ship',(1003.,1000.,1000.)),
        ('C','ship',(1060.,1000.,1000.))],radio_links=(('A','B'),))
    before=deepcopy(s.world.narrative_snapshot['radio_emissions'])
    unchanged_failure(s,'C')
    assert s.world.narrative_snapshot['radio_emissions']==before


def test_04_local_declared_continuous_notice_and_live_gates():
    s=scene();p=result(s).proposal
    assert p.first_emission_id=='fixture-A-B' and p.stage_sources[0].reference==p.first_emission_id
    plan=rec.confirm_recovery(s,p);op=s.world.radio_opportunities[rec._radio_id(plan,0)]
    assert op.emission is not None and op.emitter.host_id=='A' and op.status=='pending'
    assert radio.retry_radio_opportunities(s)==[] and s.world.mobility_failsafe_count==0
    ready(s);assert len(radio.retry_radio_opportunities(s))==1
    assert op.content_by_locale==s.world.narrative_snapshot['radio_emissions']['fixture-A-B'].content_by_locale
    assert not s.world.known_links


def test_05_remote_declared_source_keeps_spatial_recovery():
    with installed(nav_emission):
        s=recovery_state();r=select(s)
        assert r.status=='validated' and r.proposal.first_emission_id=='fixture-history'
        plan=rec.confirm_recovery(s,r.proposal);ready(s)
        assert len(radio.retry_radio_opportunities(s))==1 and plan.captured==(0,)
        assert s.world.current_node_id!='RADIO_REMOTE'


def test_06_not_arrived_emission_is_not_authority():
    def future(raw):nav_emission(raw);emission(raw)['start_t']=0
    with installed(future):
        s=recovery_state();r=select(s)
        assert r.status=='conditional' and not s.world.recovery_plans
        before=pickle.dumps(s)
        if r.proposal:reject(lambda:rec.confirm_recovery(s,r.proposal))
        assert pickle.dumps(s)==before


def test_07_finite_expired_emission_has_no_local_fallback():
    def expired(raw):
        nav_emission(raw);emission(raw).update(mode='finite',start_t=-1000,end_t=-1)
    with installed(expired):
        s=recovery_state();at(s,'RADIO_REMOTE')
        assert select(s).status=='conditional'
        unchanged_failure(s,'RADIO_TARGET')


def chain(*,second=True,salvage=False,known=False):
    links=(('A','B'),('B','C')) if second else (('A','B'),)
    return scene([('A','station',(1000.,1000.,1000.)),('B','ship' if salvage or known else 'relay',(1040.,1000.,1000.)),
        ('C','ship',(1080.,1000.,1000.))],radio_links=links,
        archives=(('B','C'),) if salvage else ())


def test_08_every_radio_stage_has_its_own_exact_preexisting_emission():
    s=chain();r=result(s,'C');assert r.proposal.mechanisms==('radio','radio')
    plan=rec.confirm_recovery(s,r.proposal)
    assert tuple(v.reference for v in plan.proposal.stage_sources)==('fixture-A-B','fixture-B-C')
    assert len(s.world.radio_opportunities)==1
    ready(s);radio.retry_radio_opportunities(s);read(s,s.world.radio_opportunities[rec._radio_id(plan,0)].path)
    at(s,'B');rec.advance_recovery_plans(s)
    op=s.world.radio_opportunities[rec._radio_id(plan,1)]
    assert op.emission.emission_id=='fixture-B-C' and op.content_by_locale==rec._hint('B','C')
    assert len(radio.retry_radio_opportunities(s))==1


def test_09_missing_intermediate_source_prevents_whole_chain_confirmation():
    s=chain(second=False)
    assert result(s,'C').status=='conditional'
    unchanged_failure(s,'C')
    # An injected duplicate hidden by a base file is not mountable evidence.
    s=chain(second=False,salvage=True)
    file='/logs/nav/fixture_B_C.txt'
    s.world.node_pools['B']=NodePoolState(base_files=[{'path':file,'access':'guest','content':'No route / Sin ruta'}],
        injected_files=[{'path':file,'access':'guest','content':'LINK: B -> C\n'}])
    assert result(s,'C').status=='conditional'


def test_10_existing_salvage_archive_is_reused_without_injection():
    s=chain(second=False,salvage=True)
    original=deepcopy(s.world.node_pools);archives=deepcopy(lore._location_fs_files('B',s))
    p=result(s,'C').proposal;assert p.mechanisms==('radio','salvage')
    plan=rec.confirm_recovery(s,p)
    assert s.world.node_pools==original and lore._location_fs_files('B',s)==archives
    assert plan.proposal.stage_sources[1].reference=='/logs/nav/fixture_B_C.txt'
    assert all(not pool.injected_files for pool in s.world.node_pools.values())


def test_11_missing_emitters_do_not_consume_attempts_or_reveal_candidates():
    s=scene(radio_links=());s.world.dead_nodes['B']=DeadNodeState(dead_since_t=0)
    unchanged_failure(s)
    for _ in range(3):rec.request_recovery(s,'deadnode:B','B')
    assert s.world.dead_nodes['B'].attempts==0 and s.world.dead_nodes['B'].last_action_t==0
    assert not s.world.mobility_hints and not s.world.known_links


def test_12_pre_engines_legacy_slot_is_rejected_without_rewrite():
    # Pre-engines saves are disposable; no player-ship migration is supported.
    raw = LEGACY.read_bytes()
    reject(lambda: save_load.load_single_slot(LEGACY))
    assert LEGACY.read_bytes() == raw


def test_13_declared_stage_provenance_persists_through_save_load():
    s=chain();plan=rec.confirm_recovery(s,result(s,'C').proposal)
    frozen=deepcopy(plan)
    with TemporaryDirectory() as directory:
        path=Path(directory)/'sources.dat';save_load.save_single_slot(s,path)
        s=save_load.load_single_slot(path).state
        assert s.world.recovery_plans[plan.plan_id]==frozen
        ready(s);assert len(radio.retry_radio_opportunities(s))==1
        save_load.save_single_slot(s,path);s=save_load.load_single_slot(path).state
        assert radio.retry_radio_opportunities(s)==[]


def test_14_protected_primary_never_becomes_automatic_notice():
    s=scene();s.world.narrative_snapshot['arcs']=[{'arc_id':'locked','primary_intel':{'kind':'node','line':'NODE: B'}}]
    assert result(s).status=='invalid'
    unchanged_failure(s)


def test_15_cli_textual_and_debug_keep_knowledge_boundary():
    for locale in (Locale.EN,Locale.ES):
        s=scene();s.os.locale=locale;t=deepcopy(s)
        rec.confirm_recovery(s,result(s).proposal)
        for renderer,args in ((repl.render_status,()),(repl.render_diag,('comms',))):
            assert capture_output(renderer,s,*args)==capture_output(renderer,t,*args)
            assert capture_output(renderer,s,*args).strip().splitlines()==presenter.build_command_output(renderer,s,*args)
        s.os.debug_enabled=True;before=pickle.dumps(s)
        output=capture_output(repl.render_debug_recovery,s)
        assert 'fixture-A-B' in output and 'stage_sources' in output
        assert pickle.dumps(s)==before


def test_16_confirm_and_capture_revalidate_payload_provenance():
    s=scene();p=result(s).proposal
    key='fixture-A-B';em=s.world.narrative_snapshot['radio_emissions'][key]
    s.world.narrative_snapshot['radio_emissions'][key]=replace(em,content_by_locale={'en':'different','es':'distinto'})
    p=replace(p,snapshot=rec.snapshot_key(s));before=pickle.dumps(s)
    reject(lambda:rec.confirm_recovery(s,p));assert pickle.dumps(s)==before
    s=scene();plan=rec.confirm_recovery(s,result(s).proposal);ready(s)
    s.world.narrative_snapshot['radio_emissions'][key]=replace(s.world.narrative_snapshot['radio_emissions'][key],content_by_locale={'en':'different','es':'distinto'})
    assert radio.retry_radio_opportunities(s)==[] and not plan.captured


def test_17_known_directed_route_remains_legitimate_later_stage():
    s=chain(second=False,known=True);s.world.known_links={'B':{'C'}};s.world.known_nodes.update({'B','C'})
    s.world.visited_nodes.add('B')
    p=result(s,'C').proposal;assert p.mechanisms==('radio','known_route') and p.stage_sources[1] is None
    plan=rec.confirm_recovery(s,p)
    assert len(s.world.radio_opportunities)==1
    ready(s);radio.retry_radio_opportunities(s);read(s,s.world.radio_opportunities[rec._radio_id(plan,0)].path)
    at(s,'B');rec.advance_recovery_plans(s)
    assert plan.consumed==(0,1)
    path,_=lore.write_local_intel(s,'ship_os_mail','Internal fixture memo / Nota interna de prueba')
    read(s,path)
    assert plan.consumed==(0,1)  # Reading unrelated files does not recapture a route.


def test_18_forged_missing_stage_sources_cannot_claim_legacy_compatibility():
    s=scene();p=result(s).proposal
    for bad in (replace(p,stage_sources=None),replace(p,first_emission_id=None),replace(p,stage_sources=(None,))):
        before=pickle.dumps(s);reject(lambda:rec.confirm_recovery(s,bad));assert pickle.dumps(s)==before
    s=chain(second=False,salvage=True);p=result(s,'C').proposal
    reject(lambda:rec.confirm_recovery(s,replace(p,stage_sources=(p.stage_sources[0],None))))


def main():
    tests=[(name,fn) for name,fn in sorted(globals().items()) if name.startswith('test_')]
    for name,fn in tests:fn();print('PASS',name,flush=True)
    print(f'RECOVERY PROVENANCE: {len(tests)} GROUPS PASS')


if __name__=='__main__':main()
