"""4D-3e5b: physics, installed declarations and public passive reception.

Fixtures install into an isolated data root. Public flow uses an ordinary
sandbox and commands with no gameplay edits after bootstrap. Pure probes and
controlled integration setup are deliberately identified separately.
"""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
import math
from pathlib import Path
import pickle
import random
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core import communications as radio, lore, structural_recovery as rec
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot, SaveLoadError
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import RadioEmitter, DeadNodeState
from retorno.runtime import data_loader as data
from retorno.ui_textual import presenter
from retorno.worldgen import generator as gen, manifest
from retorno.worldgen.narrative import collect_catalog, compile_catalog
from retorno.worldgen.radio import query_emitters
from passive_communications_smoke import command, capture_output

E = Engine()
YEAR = Balance.YEAR_S
FIXTURE = Path(__file__).parent / 'fixtures/radio_world/scene.json'


@contextmanager
def installed(mutate=None, singles=None):
    with TemporaryDirectory(prefix='retorno-radio-') as directory:
        root = Path(directory) / 'data'
        shutil.copytree(data._DATA_ROOT, root)
        scene = json.loads(FIXTURE.read_text())
        if mutate:
            mutate(scene)
        (root/'locations/radio_scene.json').write_text(json.dumps(scene))
        for locale in ('en','es'):
            shutil.copyfile(FIXTURE.parent/f'piece.{locale}.txt',root/f'lore/radio_piece.{locale}.txt')
        (root/'lore/singles/index.json').write_text(json.dumps(singles or []))
        with patch.object(data, '_DATA_ROOT', root):
            yield root


def emitter(scene):
    return scene['radio_emitters']['emitters'][0]


def emission(scene):
    return emitter(scene)['emissions'][0]


def state(*, online=True):
    s = create_initial_state_sandbox()
    # This matrix isolates authored signals. B2 coexistence is exercised by
    # historical_radio_smoke; production/new-game defaults remain procedural.
    s.world.radio_history_version = "legacy-radio-v0"
    s.world.radio_definition = None
    # Controlled integration setup; the public journey below does not use this.
    for ident in ('power_core', 'energy_distribution', 'core_os', 'comms'):
        system = s.ship.systems[ident]
        system.state = SystemState.NOMINAL
        system.health = .95
        system.forced_offline = system.state_locked = False
    s.ship.systems['comms'].service.is_running = online
    s.ship.power.e_batt_kwh = s.ship.power.e_batt_max_kwh
    s.ship.power.power_quality = 1
    s.ship.power.brownout = False
    return s


def specs(s):
    snap = s.world.narrative_snapshot
    return snap['radio_emitters']['fixture-relay'], snap['radio_emissions']['fixture-history']


def prepare(s):
    tx, signal = specs(s)
    return radio.prepare_radio_opportunity(s, 'radio:fixture-history', signal.channel,
        signal.content_by_locale, node_id=tx.host_id, trigger='fixture_preparation', emission_id=signal.emission_id)


def reject(callback, field=None):
    try:
        callback()
    except (ValueError, SaveLoadError, TypeError) as exc:
        if field:
            assert field in str(exc), str(exc)
        return str(exc)
    raise AssertionError('Expected explicit rejection')


def relocate(s, ident):
    gen.ensure_historical_node(s, ident)
    n = s.world.space.nodes[ident]
    s.world.current_node_id = s.ship.current_node_id = ident
    s.world.current_pos_ly = (n.x_ly, n.y_ly, n.z_ly)
    s.ship.docked_node_id = None


def test_01_pure_inverse_square_zero_small_and_3d():
    for distance in (0., 1e-14, .1, .5, 1., 5.999999, 6., 6.000001, 100.):
        result = radio.radio_link_budget(36., 1., distance)
        assert math.isfinite(result['received_strength'])
        assert result['decodable'] == (distance <= 6.)
    assert radio.radio_link_budget(36., 1., 2)['received_strength'] == 4 * radio.radio_link_budget(36., 1., 4)['received_strength']
    assert radio.radio_link_budget(36., 1., math.dist((0,0,0), (2,3,6)))['distance_ly'] == 7


def test_02_profiles_power_sensitivity_and_navigation_independence():
    for category, radius in [('emergency', .5), ('station', 6.), ('interstellar_relay', 20.)]:
        power = Balance.RADIO_POWER_BY_CATEGORY[category]
        for sensitivity, factor in ((.25, .5), (1., 1.), (2.25, 1.5)):
            assert radio.radio_link_budget(power, sensitivity, 0)['range_ly'] == radius*factor
        assert radio.radio_link_budget(power/4, 1, 0)['range_ly'] == radius/2
        assert radio.radio_link_budget(power*4, 1, 0)['range_ly'] == radius*2
    with patch.object(Balance, 'MAX_ROUTE_HOP_LY', 1):
        assert radio.radio_link_budget(400., 1., 20)['decodable']
    assert radio.radio_link_budget(10000., 1., 46)['decodable']


def test_03_invalid_physical_values_and_types():
    for value in (-1., 0., float('nan'), float('inf'), -float('inf'), True, '36', 1e20):
        reject(lambda: radio.radio_link_budget(value, 1, 1))
        reject(lambda: RadioEmitter('e', 'host', 'station', value))
    for value in (-1., float('nan'), float('inf'), True, '1'):
        reject(lambda: radio.radio_link_budget(1, value, 1))
        reject(lambda: radio.radio_link_budget(1, 1, value))
    assert not radio.radio_link_budget(1, 0, 0)['decodable']


def test_04_declared_alias_lazy_source_and_pure_metrics():
    with installed():
        s = state(); tx, sig = specs(s)
        assert tx.host_id == 'RADIO_REMOTE' and 'RADIO_REMOTE' not in s.world.space.nodes
        before = pickle.dumps(s); rng = random.getstate()
        metrics = radio.radio_link_metrics(s, tx, sig)
        assert metrics['distance_ly'] == 5 and metrics['range_ly'] == 20
        assert metrics['propagation_s'] == 5*YEAR and metrics['temporally_available']
        assert radio.radio_spatial_block_reason(s, tx.host_id, channel=sig.channel, emitter=tx) is None
        assert pickle.dumps(s) == before and random.getstate() == rng


def test_05_new_finite_signal_exact_arrival_and_passage():
    def finite(scene):
        emission(scene).update(mode='finite', start_t=0, end_t=10)
    with installed(finite):
        s = state(); op = prepare(s)
        assert op.prepared_t == 0 and op.emission.start_t == 0
        assert radio.radio_block_reason(s, op) == 'signal_not_arrived'
        s.clock.t = 5*YEAR-1
        assert radio.retry_radio_opportunities(s) == []
        s.clock.t = 5*YEAR
        assert len(radio.retry_radio_opportunities(s)) == 1
        assert op.received_t == 5*YEAR
        t = state(); pending = prepare(t); t.clock.t = 5*YEAR+10
        assert radio.radio_block_reason(t, pending) == 'signal_passed'
        assert radio.retry_radio_opportunities(t) == [] and pending.status == 'pending'


def test_06_continuous_future_start_and_end():
    def finite_continuous(scene):
        emission(scene).update(start_t=2*YEAR, end_t=3*YEAR)
    with installed(finite_continuous):
        s=state(); op=prepare(s)
        for now, reason in ((0,'signal_not_arrived'), (7*YEAR-1,'signal_not_arrived'), (7*YEAR,None), (8*YEAR,'signal_passed')):
            s.clock.t = now
            assert radio.radio_block_reason(s, op) == reason


def test_07_preparation_is_not_physical_emission_or_delivery():
    with installed():
        s=state(online=False); s.clock.t=123
        before = deepcopy((s.os, s.world.known_nodes, s.world.known_links, s.world.lore, s.events))
        op=prepare(s)
        assert op.prepared_t == 123 and op.emission.start_t == -10*YEAR
        assert before == (s.os,s.world.known_nodes,s.world.known_links,s.world.lore,s.events)
        assert op.status == 'pending' and not op.path
        s.ship.systems['comms'].service.is_running=True
        assert len(radio.retry_radio_opportunities(s))==1 and op.received_t==123


def test_08_live_receiver_sensitivity_and_repair():
    def station(scene): emitter(scene)['category']='station'
    with installed(station):
        s=state(); op=prepare(s); comms=s.ship.systems['comms']
        for condition in (SystemState.OFFLINE,SystemState.CRITICAL,SystemState.DAMAGED,SystemState.LIMITED):
            comms.state=condition
            assert radio.capture_radio_opportunity(s,op) is None
        comms.state=SystemState.NOMINAL; comms.health=.5
        assert radio.capture_radio_opportunity(s,op) is None
        comms.health=.95
        assert radio.capture_radio_opportunity(s,op) is not None
        # Capture never freezes preparation-time sensitivity.
        t=state(); t.ship.systems['comms'].state=SystemState.LIMITED; pending=prepare(t)
        t.ship.systems['comms'].state=SystemState.UPGRADED
        assert radio.capture_radio_opportunity(t,pending) is not None


def test_09_upgraded_reach_and_position_revalidation():
    def station(scene):
        emitter(scene)['category']='station'
        scene['world_requirements']['entities'][0]['position']['fixed_ly']=[-7,0,0]
    with installed(station):
        s=state(); op=prepare(s)
        assert radio.radio_block_reason(s,op)=='outside_radio_range'
        s.ship.systems['comms'].state=SystemState.UPGRADED
        assert radio.capture_radio_opportunity(s,op)
        t=state(); p=prepare(t); relocate(t,'RADIO_FAR')
        assert radio.capture_radio_opportunity(t,p) is None
        relocate(t,'RADIO_REMOTE')
        assert radio.capture_radio_opportunity(t,p)


def test_10_finite_window_missed_while_off_is_not_cached():
    def short(scene): emission(scene).update(mode='finite', start_t=-5*YEAR, end_t=-5*YEAR+10)
    with installed(short):
        s=state(online=False); op=prepare(s)
        E.tick(s,20)
        s.ship.systems['comms'].service.is_running=True
        assert radio.retry_radio_opportunities(s)==[] and op.status=='pending'


def test_11_large_tick_crosses_continuous_arrival_but_not_expired_window():
    for finite in (False,True):
        def future(scene):
            emission(scene).update(start_t=-5*YEAR+10)
            if finite: emission(scene).update(mode='finite',end_t=-5*YEAR+20)
        with installed(future):
            s=state(); prepare(s)
            receipts=[e for e in E.tick(s,100) if e.type==EventType.SIGNAL_CAPTURED]
            assert len(receipts)==int(not finite)
            assert radio.retry_radio_opportunities(s)==[]


def test_12_hibernation_and_transit_do_not_capture_retrospectively():
    for context in ('is_hibernating','in_transit'):
        with installed():
            s=state(); op=prepare(s); setattr(s.ship,context,True)
            if context=='in_transit': s.ship.arrival_t=1000
            assert not [e for e in E.tick(s,30) if e.type==EventType.SIGNAL_CAPTURED]
            assert op.status=='pending'
            setattr(s.ship,context,False)
            assert len([e for e in E.tick(s,1) if e.type==EventType.SIGNAL_CAPTURED])==1
    def ended(scene): emission(scene).update(mode='finite',start_t=-5*YEAR,end_t=-5*YEAR+10)
    with installed(ended):
        s=state();op=prepare(s);s.ship.is_hibernating=True;E.tick(s,30);s.ship.is_hibernating=False
        assert radio.retry_radio_opportunities(s)==[] and op.status=='pending'


def test_13_all_operational_gates_are_still_live():
    for gate in ('service','uninstalled','off','dependency','power','core','lock','supply'):
        with installed():
            s=state();op=prepare(s)
            if gate=='service':s.ship.systems['comms'].service.is_running=False
            if gate=='uninstalled':s.ship.systems['comms'].service.is_installed=False
            if gate=='off':s.ship.systems['comms'].forced_offline=True
            if gate=='dependency':s.ship.systems['energy_distribution'].forced_offline=True
            if gate=='power':s.ship.power.power_quality=.1
            if gate=='core':s.ship.systems['core_os'].state=SystemState.CRITICAL
            if gate=='lock':s.os.terminal_lock=True
            if gate=='supply':
                s.ship.power.e_batt_kwh=0;s.ship.systems['power_core'].state=SystemState.OFFLINE
            before=deepcopy((s.os,s.events,s.world.lore))
            assert radio.retry_radio_opportunities(s)==[] and op.status=='pending',gate
            assert before==(s.os,s.events,s.world.lore),gate


def test_14_no_emitter_or_no_activity_produces_no_signal():
    for mode in ('absent','inactive'):
        def change(scene):
            if mode=='absent':scene.pop('radio_emitters')
            else:emitter(scene)['emissions']=[]
        with installed(change):
            s=state();E.tick(s,1)
            assert not s.world.radio_opportunities


def test_15_public_remote_capture_read_import_and_repeated_load():
    for locale in (Locale.EN,Locale.ES):
        with installed(),TemporaryDirectory() as directory:
            s=create_initial_state_sandbox();s.os.locale=locale
            twin=deepcopy(s)
            twin.world.narrative_snapshot.update(radio_emitters={},radio_emissions={},radio_index={})
            # From here on: only public commands, ordinary engine steps and slot IO.
            origin=s.world.current_node_id;before_nodes=set(s.world.space.nodes)
            assert 'RADIO_REMOTE' not in before_nodes
            events=[]
            for text in ('power off data_core','power on comms','boot radiod'):
                events.extend(command(s,text))
                command(twin,text)
            events.extend(E.tick(s,5))
            E.tick(twin,5)
            captures=[e for e in events if e.type==EventType.SIGNAL_CAPTURED]
            assert len(captures)==1,events
            op=s.world.radio_opportunities['radio:fixture-history']
            assert op.origin_node_id!=origin and op.origin_node_id=='RADIO_REMOTE'
            assert op.received_t==5 and op.emission.start_t==-10*YEAR
            assert 'RADIO_TARGET' not in s.world.known_nodes and not s.world.known_links.get('RADIO_REMOTE')
            # The pre-existing lore pool initializer may generate sectors in any
            # tick. Radio adds no materialization beyond that identical control.
            assert s.world.space==twin.world.space and not s.world.scan_observations
            file=op.path
            slot=Path(directory)/'radio.dat';save_single_slot(s,slot)
            s=load_single_slot(slot).state
            assert radio.retry_radio_opportunities(s)==[]
            text=capture_output(repl.render_cat,s,file)
            assert 'RADIO_TARGET' in text and 'RADIO_TARGET' in s.world.known_nodes
            assert 'RADIO_TARGET' in s.world.known_links['RADIO_REMOTE']
            assert s.world.radio_opportunities['radio:fixture-history'].status=='read_imported'
            save_single_slot(s,slot);s=load_single_slot(slot).state
            assert not [e for e in E.tick(s,1) if e.type==EventType.SIGNAL_CAPTURED]
            print('PUBLIC REMOTE FLOW',locale.value,origin,'<- RADIO_REMOTE; distance=5ly; emitted=-10yr; captured=5s;',
                  'power off data_core -> power on comms -> boot radiod -> wait 5s -> save/load -> cat',file,
                  '; LINK imported only after reading',flush=True)


def test_16_pending_future_survives_save_without_emission_retiming():
    def future(scene):emission(scene)['start_t']=-5*YEAR+100
    with installed(future),TemporaryDirectory() as directory:
        s=state();op=prepare(s);path=Path(directory)/'pending.dat';save_single_slot(s,path)
        s=load_single_slot(path).state;assert s.world.radio_opportunities[op.opportunity_id]==op
        E.tick(s,99);assert radio.retry_radio_opportunities(s)==[]
        assert len([e for e in E.tick(s,1) if e.type==EventType.SIGNAL_CAPTURED])==1


def test_17_legacy_opportunity_migration_remains_local():
    with installed(),TemporaryDirectory() as directory:
        s=state(online=False)
        local=radio.prepare_radio_opportunity(s,'legacy','captured_signal',{'en':'local'},node_id='ECHO_7',trigger='local')
        del local.emitter;del local.emission
        blob=pickle.dumps(s,pickle.HIGHEST_PROTOCOL)
        raw=b'RETORNO_SAVE_V2\n'+hashlib.sha256(blob).hexdigest().encode()+b'\n'+blob
        path=Path(directory)/'legacy.dat';path.write_bytes(raw)
        s=load_single_slot(path).state;local=s.world.radio_opportunities['legacy']
        assert local.emitter is local.emission is None and path.read_bytes()==raw
        relocate(s,'RADIO_REMOTE');s.ship.systems['comms'].service.is_running=True
        assert radio.capture_radio_opportunity(s,local) is None


def test_18_invalid_contracts_report_source_and_field():
    changes=[
        (lambda x:emitter(x).update(power=-1),'power'),
        (lambda x:emitter(x).update(power=float('nan')),'power'),
        (lambda x:emitter(x).update(power=float('inf')),'power'),
        (lambda x:emitter(x).update(power=True),'power'),
        (lambda x:emitter(x).update(power='4'),'power'),
        (lambda x:emitter(x).update(category='unknown'),'category'),
        (lambda x:emitter(x).update(host='MISSING_HOST'),'host'),
        (lambda x:emitter(x).update(host='RETORNO_SHIP'),'host'),
        (lambda x:emitter(x).update(unknown=1),'unsupported'),
        (lambda x:emission(x).update(unknown=1),'unsupported'),
        (lambda x:emission(x).update(start_t=None),'start_t'),
        (lambda x:emission(x).update(mode='finite',end_t=-11*YEAR),'end_t'),
        (lambda x:emission(x).update(mode='finite'),'end_t'),
        (lambda x:emission(x).update(mode='instant'),'mode'),
        (lambda x:emission(x).update(time_reference='absolute-date'),'time_reference'),
        (lambda x:emission(x).update(navigation_link_to='RADIO_TARGET'),'content'),
        (lambda x:emission(x).update(content_by_locale={'en':'only EN'}),'content_by_locale'),
        (lambda x:emission(x).update(content_by_locale={'en':'{{pending}}','es':'{{pending}}'}),'content_by_locale'),
        (lambda x:emitter(x).update(category=['station']),'category'),
        (lambda x:x.update(radio_emitters=None),'radio_emitters'),
        (lambda x:emission(x).update(piece_key='single:missing',content_by_locale=None),'content'),
    ]
    for change,field in changes:
        with installed(change):
            error=reject(lambda:compile_catalog(1),field)
            assert 'locations' in error or 'catalog' in error,error
    def duplicate(scene):scene['radio_emitters']['emitters'].append(deepcopy(emitter(scene)))
    with installed(duplicate):reject(lambda:compile_catalog(1),'duplicate')


def test_19_radio_metadata_changes_catalog_but_not_physical_manifest():
    with installed():
        catalog=collect_catalog();d,a=compile_catalog(1,catalog)
        changed=deepcopy(catalog)
        record=next(r for r in changed['records'] if r['id']=='RADIO_RECEIVER')
        emitter(record['value'])['power']=100.
        e,b=compile_catalog(1,changed)
        assert d==e and a['physical_catalog_key']==b['physical_catalog_key']
        assert a['catalog_key']!=b['catalog_key'] and a['radio_emitters']!=b['radio_emitters']
        changed['records'].reverse();f,c=compile_catalog(1,changed)
        assert e==f and b==c


def test_20_materialization_order_and_rng_independence():
    with installed():
        s=state();t=deepcopy(s);before=random.getstate();counter=s.meta.rng_counter
        for nid in ('RADIO_REMOTE','RADIO_TARGET','RADIO_FAR'):gen.ensure_historical_node(s,nid)
        for nid in ('RADIO_FAR','RADIO_TARGET','RADIO_REMOTE'):gen.ensure_historical_node(t,nid)
        assert s.world.space==t.world.space
        assert radio.radio_link_metrics(s,*specs(s))==radio.radio_link_metrics(t,*specs(t))
        assert len(radio.retry_radio_opportunities(s))==len(radio.retry_radio_opportunities(t))==1
        assert s.meta.rng_counter==t.meta.rng_counter==counter and random.getstate()==before


def test_21_procedural_host_is_certified_without_materialization():
    with installed():
        c=collect_catalog();d,_=compile_catalog(1,c)
        sites=manifest.new_session(d).sector('S+001_+001_+000').sites
        host=next(p for p in sites if p.identity.namespace=='procedural')
        raw=next(r['value'] for r in c['records'] if r['id']=='RADIO_RECEIVER')
        emitter(raw)['host']=manifest.operative_id(d,host)
        e,snapshot=compile_catalog(1,c)
        assert d==e and snapshot['radio_emitters']['fixture-relay'].host_id==manifest.operative_id(d,host)
        emitter(raw)['host']='S+001_+001_+000:WG1_'+d.scope+'_99999'
        reject(lambda:compile_catalog(1,c),'host')


def test_22_bounded_index_budget_progress_and_no_materialization():
    def crowded(scene):
        original=emitter(scene)
        scene['radio_emitters']['emitters']=[dict(original,id=f'e{i}',emissions=[]) for i in range(12)]
    with installed(crowded):
        s=state();seen=set();cursor={};before=pickle.dumps(s)
        for _ in range(4):
            page,cursor,complete=query_emitters(s,cursor=cursor,limit=3)
            assert len(page)==3 and not complete;seen.update(page)
        assert len(seen)==12 and pickle.dumps(s)==before
        assert query_emitters(s,limit=12)[2]
        reject(lambda:query_emitters(s,limit=0))


def test_23_no_public_disclosure_and_debug_is_read_only_en_es():
    with installed():
        for locale in (Locale.EN,Locale.ES):
            s=state();s.os.locale=locale;t=deepcopy(s)
            t.world.narrative_snapshot['radio_emitters']={};t.world.narrative_snapshot['radio_emissions']={}
            prepare(s)
            for renderer,args in ((repl.render_status,()),(repl.render_diag,('comms',))):
                assert capture_output(renderer,s,*args)==capture_output(renderer,t,*args)
                assert capture_output(renderer,s,*args).strip().splitlines()==presenter.build_command_output(renderer,s,*args)
            s.os.debug_enabled=True
            before=pickle.dumps(s);rng=random.getstate()
            output=capture_output(repl.render_debug_radio,s)
            assert all(k in output for k in ('fixture-relay','distance_ly','range_ly','arrival_start_t','power','sensitivity'))
            assert pickle.dumps(s)==before and random.getstate()==rng
            assert not s.world.known_nodes.intersection({'RADIO_REMOTE','RADIO_TARGET'})


def recovery_state():
    s=state(online=False);relocate(s,'RADIO_RECEIVER');gen.ensure_historical_node(s,'RADIO_REMOTE')
    gen.ensure_historical_node(s,'RADIO_TARGET')
    s.world.known_nodes={'RADIO_RECEIVER','RADIO_REMOTE'}
    s.world.known_contacts=set(s.world.known_nodes)
    s.world.known_links={'RADIO_RECEIVER':{'RADIO_REMOTE'}}
    s.world.visited_nodes={'RADIO_RECEIVER','RADIO_REMOTE'}
    return s


def nav_emission(scene):
    raw=emission(scene);raw.pop('content_by_locale');raw.update(channel='station_broadcast',navigation_link_to='RADIO_TARGET')


def select(s):
    return rec.select_recovery(s,'fixture-recovery','RADIO_TARGET',budget=rec.RecoveryBudget(sectors=0))


def test_24_recovery_remote_arrived_continuous_and_common_ledger():
    with installed(nav_emission):
        s=recovery_state();r=select(s)
        assert r.status=='validated' and r.proposal.first_emission_id=='fixture-history',(r.status,r.reason)
        before=deepcopy(s.world.space);plan=rec.confirm_recovery(s,r.proposal)
        assert plan.status=='receipt_pending' and not plan.captured and s.world.space==before
        assert set(s.world.radio_opportunities)=={'radio:fixture-history'}
        s.os.debug_enabled=True;frozen=pickle.dumps(s)
        diagnostics=capture_output(repl.render_debug_recovery,s)
        assert 'fixture-history' in diagnostics and 'arrival_start_t' in diagnostics
        assert pickle.dumps(s)==frozen
        assert radio.retry_radio_opportunities(s)==[]
        s.ship.systems['comms'].service.is_running=True
        assert len(radio.retry_radio_opportunities(s))==1 and plan.captured==(0,)
        assert s.world.mobility_failsafe_count==1
        assert radio.retry_radio_opportunities(s)==[]
        op=s.world.radio_opportunities['radio:fixture-history']
        assert 'RADIO_TARGET' not in s.world.known_links.get('RADIO_REMOTE',())
        capture_output(repl.render_cat,s,op.path)
        assert plan.consumed==(0,) and 'RADIO_TARGET' in s.world.known_links['RADIO_REMOTE']


def test_25_recovery_no_false_plan_before_arrival_or_outside_coverage():
    for mode in ('future','far','no-emission','finite'):
        def change(scene):
            nav_emission(scene)
            if mode=='future':emission(scene)['start_t']=0
            if mode=='far':emitter(scene).update(category='emergency')
            if mode=='no-emission':emitter(scene)['emissions']=[]
            if mode=='finite':emission(scene).update(mode='finite',end_t=YEAR)
        with installed(change):
            s=recovery_state();before=deepcopy(s.world.space)
            r=select(s)
            assert r.status!='validated',(mode,r)
            rec.request_recovery(s,'fixture-recovery','RADIO_TARGET')
            assert not s.world.recovery_plans and not s.world.radio_opportunities
            assert s.world.space==before and s.world.mobility_failsafe_count==0


def test_26_recovery_live_position_change_and_attempts_after_capture_only():
    def short(scene):nav_emission(scene);emitter(scene)['category']='emergency'
    with installed(short):
        s=recovery_state();assert select(s).status=='conditional'
        relocate(s,'RADIO_REMOTE')
        r=select(s);assert r.status=='validated' and r.proposal.first_emission_id=='fixture-history'
    with installed(nav_emission):
        s=recovery_state();s.world.dead_nodes['RADIO_TARGET']=DeadNodeState(dead_since_t=0)
        r=rec.select_recovery(s,'deadnode:RADIO_TARGET','RADIO_TARGET',budget=rec.RecoveryBudget(sectors=0))
        plan=rec.confirm_recovery(s,r.proposal)
        for _ in range(3):assert radio.retry_radio_opportunities(s)==[]
        assert s.world.dead_nodes['RADIO_TARGET'].attempts==0
        s.ship.systems['comms'].service.is_running=True;assert len(radio.retry_radio_opportunities(s))==1
        assert s.world.dead_nodes['RADIO_TARGET'].attempts==1 and plan.captured==(0,)


def test_27_recovery_provenance_survives_health_change_and_load():
    def station(scene):nav_emission(scene);emitter(scene)['category']='station'
    with installed(station),TemporaryDirectory() as directory:
        s=recovery_state();plan=rec.confirm_recovery(s,select(s).proposal)
        s.ship.systems['comms'].state=SystemState.LIMITED;s.ship.systems['comms'].health=.72
        path=Path(directory)/'recovery.dat';save_single_slot(s,path);s=load_single_slot(path).state
        assert radio.retry_radio_opportunities(s)==[]
        s.ship.systems['comms'].health=.95;s.ship.systems['comms'].state=SystemState.NOMINAL
        s.ship.systems['comms'].service.is_running=True
        assert len(radio.retry_radio_opportunities(s))==1


def test_28_corrupt_radio_save_is_rejected_without_rewrite():
    with installed(),TemporaryDirectory() as directory:
        s=state();op=prepare(s);op.emitter=replace(op.emitter,power=9)
        path=Path(directory)/'corrupt.dat'
        reject(lambda:save_single_slot(s,path),'Radio')
        assert not path.exists()
        blob=pickle.dumps(s,pickle.HIGHEST_PROTOCOL);raw=b'RETORNO_SAVE_V2\n'+hashlib.sha256(blob).hexdigest().encode()+b'\n'+blob
        path.write_bytes(raw)
        reject(lambda:load_single_slot(path),'Radio')
        assert path.read_bytes()==raw


def test_29_installed_radio_change_rejects_old_slot_but_not_physical_scope():
    with installed() as root,TemporaryDirectory() as directory:
        s=state();prepare(s);path=Path(directory)/'catalog.dat';save_single_slot(s,path);raw=path.read_bytes()
        scene=json.loads((root/'locations/radio_scene.json').read_text());emitter(scene)['power']=100
        (root/'locations/radio_scene.json').write_text(json.dumps(scene))
        reject(lambda:load_single_slot(path),'catalog')
        assert path.read_bytes()==raw


def test_30_signal_identity_cannot_be_captured_twice_through_another_id():
    with installed():
        s=state();tx,sig=specs(s)
        reject(lambda:radio.prepare_radio_opportunity(s,'second-copy',sig.channel,sig.content_by_locale,
            node_id=tx.host_id,trigger='test',emission_id=sig.emission_id),'identity')
        op=prepare(s);assert len(radio.retry_radio_opportunities(s))==1
        assert prepare(s) is op and radio.retry_radio_opportunities(s)==[]


def piece_fixture(*, forced):
    return dict(single_id='radio-piece',channels=['captured_signal'],weight=0,
        force=forced,force_policy='hard' if forced else 'none',radio_emission='fixture-history',
        content_ref_en='lore/radio_piece.en.txt',
        content_ref_es='lore/radio_piece.es.txt')


def piece_emission(scene):
    raw=emission(scene);raw.pop('content_by_locale');raw['piece_key']='single:radio-piece'


def test_31_unselected_optional_piece_does_not_appear_by_proximity():
    with installed(piece_emission,singles=[piece_fixture(forced=False)]):
        s=state();lore.run_lore_scheduler_tick(s)
        # Installed hard arc pieces may be placed; this optional radio piece must not be.
        assert 'single:radio-piece' not in s.world.lore_placements.piece_to_node
        for _ in range(3):E.tick(s,1)
        assert not any(op.emission and op.emission.piece_key for op in s.world.radio_opportunities.values())
        assert not s.world.lore.delivered


def test_32_selected_piece_still_waits_for_dock_uplink_or_salvage_trigger():
    for trigger in ('dock','uplink','salvage_data'):
        with installed(piece_emission,singles=[piece_fixture(forced=True)]):
            s=state();lore.run_lore_scheduler_tick(s)
            assert s.world.lore_placements.piece_to_node['single:radio-piece']=='RADIO_REMOTE'
            assert radio.retry_radio_opportunities(s)==[] and not s.world.radio_opportunities
            relocate(s,'RADIO_REMOTE')
            # An invalid interaction may prepare, but cannot bypass dock context.
            result=lore.maybe_deliver_lore(s,trigger,lore.build_lore_context(s,'RADIO_REMOTE'),count_trigger=False)
            assert not result.applied
            op=s.world.radio_opportunities['lore:single:radio-piece']
            assert op.emission.emission_id=='fixture-history' and op.require_docked
            relocate(s,'ECHO_7');assert radio.retry_radio_opportunities(s)==[]
            relocate(s,'RADIO_REMOTE');s.ship.docked_node_id='RADIO_REMOTE'
            assert len(radio.retry_radio_opportunities(s))==1
            assert 'single:radio-piece' in s.world.lore.delivered
            assert s.world.lore.counters['signal_count']==1
            assert radio.retry_radio_opportunities(s)==[]


def test_33_reference_validation_missing_piece_emission_or_channel():
    with installed(piece_emission):reject(lambda:compile_catalog(1),'piece_key')
    bad=piece_fixture(forced=False);bad['radio_emission']='MISSING'
    with installed(piece_emission,singles=[bad]):reject(lambda:compile_catalog(1),'piece_key')
    bad=piece_fixture(forced=False);bad['channels']=['salvage_data']
    with installed(piece_emission,singles=[bad]):reject(lambda:compile_catalog(1),'channel')


def test_34_automatic_budget_resumes_across_ticks_and_save():
    def crowded(scene):
        original=deepcopy(emitter(scene));items=[]
        for i in range(4):
            item=deepcopy(original);item['id']=f'e{i}';item['emissions'][0]['id']=f'sig{i}';items.append(item)
        scene['radio_emitters']['emitters']=items
    with installed(crowded),patch.object(Balance,'RADIO_CANDIDATES_PER_TICK',1),TemporaryDirectory() as directory:
        s=state();slot=Path(directory)/'cursor.dat'
        for index in range(4):
            assert len(radio.retry_radio_opportunities(s))==1
            if index==1:save_single_slot(s,slot);s=load_single_slot(slot).state
        assert len(s.world.radio_opportunities)==4
        assert radio.retry_radio_opportunities(s)==[]


def test_35_hidden_time_position_and_outside_emitter_never_change_public_telemetry():
    with installed():
        for locale in (Locale.EN,Locale.ES):
            s=state();s.os.locale=locale;baseline=(capture_output(repl.render_status,s),capture_output(repl.render_diag,s,'comms'))
            for position in ('RADIO_REMOTE','RADIO_FAR'):
                for start in (-100*YEAR,100*YEAR):
                    tx,sig=specs(s)
                    s.world.narrative_snapshot['radio_emitters'][tx.emitter_id]=replace(tx,host_id=position)
                    s.world.narrative_snapshot['radio_emissions'][sig.emission_id]=replace(sig,start_t=start)
                    assert baseline==(capture_output(repl.render_status,s),capture_output(repl.render_diag,s,'comms'))


def test_36_3d_certified_distance_changes_propagation_and_coverage():
    def xyz(scene):
        scene['world_requirements']['entities'][0]['position']['fixed_ly']=[-2,3,6]
        emitter(scene)['category']='station'
    with installed(xyz):
        s=state();tx,sig=specs(s);m=radio.radio_link_metrics(s,tx,sig)
        assert m['distance_ly']==7 and m['propagation_s']==7*YEAR and not m['decodable']
        s.ship.systems['comms'].state=SystemState.UPGRADED
        assert radio.radio_link_metrics(s,tx,sig)['decodable']


def test_37_passive_reception_does_not_add_distance_load():
    with installed():
        s=state();load=E._compute_load_kw(s);prepare(s);radio.retry_radio_opportunities(s)
        assert E._compute_load_kw(s)==load
        relocate(s,'RADIO_REMOTE')
        assert E._compute_load_kw(s)==load


def test_38_capture_on_arrival_and_stop_listening_on_departure():
    with installed():
        s=state();gen.ensure_historical_node(s,'RADIO_REMOTE')
        s.ship.in_transit=True;s.ship.transit_to='RADIO_REMOTE';s.ship.arrival_t=10;s.ship.transit_from='ECHO_7'
        assert not [e for e in E.tick(s,9) if e.type==EventType.SIGNAL_CAPTURED]
        assert len([e for e in E.tick(s,1) if e.type==EventType.SIGNAL_CAPTURED])==1
        assert s.world.current_node_id=='RADIO_REMOTE'
        t=state();op=prepare(t);t.ship.in_transit=True;t.ship.arrival_t=1000
        assert radio.capture_radio_opportunity(t,op) is None


def test_39_preexisting_finite_historical_signal_can_still_be_in_flight():
    def old(scene):emission(scene).update(mode='finite',start_t=-5*YEAR,end_t=-5*YEAR+10)
    with installed(old):
        s=state();assert len(radio.retry_radio_opportunities(s))==1
        op=s.world.radio_opportunities['radio:fixture-history']
        assert op.emission.end_t<0 and op.received_t==0


def test_40_old_recovery_proposal_and_radio_slots_have_safe_defaults():
    from retorno.model.world import RadioOpportunity
    # Genuine old slot payloads: new defaults must not invent a transmitter.
    op=RadioOpportunity.__new__(RadioOpportunity)
    op.__setstate__((None,dict(opportunity_id='old',channel='captured_signal',source_kind='world',source_id='ECHO_7',
        origin_node_id='ECHO_7',trigger='dock',require_docked=True,content_by_locale={'en':'old'},prepared_t=0)))
    assert op.emitter is op.emission is None and op.status=='pending'
    proposal=rec.RecoveryProposal.__new__(rec.RecoveryProposal)
    proposal.__setstate__(['old','scope','snapshot',(),None,()])
    assert proposal.first_emission_id is None and proposal.first_reception_sensitivity==1


def test_41_remote_navigation_emission_cannot_reveal_protected_primary():
    with installed(nav_emission) as root:
        arc=dict(arc_id='radio-protected',primary_intel=dict(id='primary',kind='node',line='NODE: RADIO_TARGET',
            allowed_channels=['captured_signal'],content_ref_en='lore/radio_piece.en.txt',content_ref_es='lore/radio_piece.es.txt'))
        (root/'arcs/radio_protected.json').write_text(json.dumps(arc))
        s=recovery_state();assert 'RADIO_TARGET' in lore._locked_primary_targets(s)
        assert select(s).status=='invalid'
        s.ship.systems['comms'].service.is_running=True
        assert radio.retry_radio_opportunities(s)==[] and not s.world.radio_opportunities
        assert 'RADIO_TARGET' not in s.world.known_nodes


def test_42_radio_configuration_change_rejects_slot_without_rewrite():
    with installed(),TemporaryDirectory() as directory:
        s=state();prepare(s);slot=Path(directory)/'configuration.dat';save_single_slot(s,slot);raw=slot.read_bytes()
        with patch.object(Balance,'RADIO_DISTANCE_FLOOR_LY',1e-8):
            reject(lambda:load_single_slot(slot),'configur')
        assert slot.read_bytes()==raw


def test_43_public_repair_improves_remote_sensitivity_during_continuous_emission():
    def station(scene):emitter(scene)['category']='station'
    with installed(station):
        s=create_initial_state_sandbox();events=[]
        for text in ('power off data_core','power on comms','boot radiod'):
            events.extend(command(s,text))
        events.extend(E.tick(s,5))
        assert s.ship.systems['comms'].state==SystemState.LIMITED and not s.world.radio_opportunities
        events.extend(command(s,'drone deploy D1 BRG-01'))
        for _ in range(200):
            if not s.jobs.active_job_ids:break
            events.extend(E.tick(s,1))
        for _ in range(6):
            if s.ship.systems['comms'].health>=.85:break
            events.extend(command(s,'drone repair D1 comms'))
            for _ in range(200):
                if not s.jobs.active_job_ids:break
                events.extend(E.tick(s,1))
        assert s.ship.systems['comms'].state==SystemState.NOMINAL
        assert len([e for e in events if e.type==EventType.SIGNAL_CAPTURED])==1
        assert radio.retry_radio_opportunities(s)==[]


def main():
    tests=[(name,value) for name,value in sorted(globals().items()) if name.startswith('test_')]
    for name,test in tests:
        test();print('PASS',name,flush=True)
    print(f'RADIO SPACETIME: {len(tests)} GROUPS PASS',flush=True)


if __name__=='__main__':main()
