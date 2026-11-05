"""4D-3e3 observation memory: execution, negative evidence and schema-3 saves."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, asdict, fields
import hashlib
import io
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core import engine as engine_mod, lore
from retorno.core.actions import Scan, JobCancel
from retorno.core.engine import Engine
from retorno.io import save_load
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import (
    SCAN_OBSERVATION_LIMIT, NodePoolState, ScanOutcome, WorldState, scan_observation_history,
)
from retorno.ui_textual import presenter
from retorno.worldgen import generator as gen, manifest
from tests.sensor_detection_factor_smoke import _scan_state, ORIGIN_ID, TARGET_ID
from tests.fixtures.scan_590a3e8 import perform_scan as baseline_scan


def _state():
    s = _scan_state(SystemState.NOMINAL)
    # A real unconsumed data frontier keeps the existing recovery system from
    # adding its exceptional guaranteed contact between controlled test sweeps.
    s.world.node_pools[ORIGIN_ID] = NodePoolState(
        base_files=[{'path':'/logs/observation-fixture.txt','content':'pending survey'}])
    return s


def _queue(s,e):
    result=e.apply_action(s,Scan())
    assert any(v.type == EventType.JOB_QUEUED for v in result),result
    return s.jobs.jobs[s.jobs.active_job_ids[-1]]


def _rolls(s,detected_ids=(), *, completion_t=None):
    # Replace only scan's RNG factory, not worldgen's RNG or any balance value.
    t = s.clock.t if completion_t is None else completion_t
    seeds={Engine()._hash64(s.meta.rng_seed+s.meta.rng_counter+1,f'scan:{nid}:{int(t)}')
           for nid in detected_ids}
    return SimpleNamespace(Random=lambda seed: SimpleNamespace(random=lambda:0.0 if seed in seeds else 1.0))


def _complete(s,e,job,detected_ids=()):
    dt=job.eta_s+.01
    with patch.object(engine_mod,'random',_rolls(s,detected_ids,completion_t=s.clock.t+dt)):
        events=e.tick(s,dt)
    assert job.status == JobStatus.COMPLETED,(job,events)
    event=next(v for v in events if v.data.get('message_key')=='job_completed_scan')
    observation=scan_observation_history(s.world)[-1]
    assert event.data['observation_id'] == observation.observation_id
    assert tuple(event.data['seen_ids']) == observation.detected_ids
    assert tuple(event.data['new_ids']) == observation.new_ids
    assert event.data['scan_outcome'] == observation.outcome.value
    return observation,events


def test_01_successful_job_new_contact_and_exact_event_results():
    s,e=_state(),Engine()
    job=_queue(s,e)
    assert not scan_observation_history(s.world)
    observation,events=_complete(s,e,job,(TARGET_ID,))
    assert len(s.world.scan_observations)==1
    assert observation.detected_ids == observation.new_ids == (TARGET_ID,)
    assert observation.outcome == ScanOutcome.NEW_CONTACTS
    assert observation.t == s.clock.t and isinstance(observation.t,float)
    assert observation.position_ly == (0.0,0.0,0.0)
    assert observation.origin_node_id == ORIGIN_ID
    assert observation.job_key == job.internal_id
    assert any(v.type == EventType.SIGNAL_DETECTED and v.data['contact_id']==TARGET_ID for v in events)
    assert any(v.to_id==TARGET_ID and v.source_kind=='scan' for v in s.world.intel)


def test_02_known_contact_only_is_not_no_signals():
    s,e=_state(),Engine()
    s.world.known_nodes.add(TARGET_ID)
    s.world.known_contacts.add(TARGET_ID)
    observation,events=_complete(s,e,_queue(s,e),(TARGET_ID,))
    assert observation.detected_ids == (TARGET_ID,) and not observation.new_ids
    assert observation.outcome == ScanOutcome.KNOWN_CONTACTS_ONLY
    assert not any(v.type == EventType.SIGNAL_DETECTED for v in events)


def test_03_negative_observation_retains_legitimate_intel_and_later_discovery():
    s,e=_state(),Engine()
    s.world.known_intel['PENDING']={'source':'existing clue'}
    links=copy.deepcopy(s.world.known_links)
    known_intel=copy.deepcopy(s.world.known_intel)
    observation,_=_complete(s,e,_queue(s,e))
    assert observation.outcome == ScanOutcome.NO_SIGNALS
    assert not observation.detected_ids and not observation.new_ids
    assert TARGET_ID in s.world.space.nodes and TARGET_ID not in s.world.known_nodes
    assert s.world.known_intel == known_intel and s.world.known_links == links
    observed,_=_complete(s,e,_queue(s,e),(TARGET_ID,))
    assert observed.new_ids == (TARGET_ID,) and TARGET_ID in s.world.known_nodes
    assert observation.detected_ids == ()


def test_04_blocked_sensors_and_sensord_produce_no_observation():
    for unavailable in ('state','service'):
        s,e=_state(),Engine()
        sensors=s.ship.systems['sensors']
        if unavailable=='state':sensors.state=SystemState.OFFLINE
        else:sensors.service.is_running=False
        counter=s.meta.rng_counter
        events=e.apply_action(s,Scan())
        assert any(v.type == EventType.BOOT_BLOCKED for v in events)
        assert not s.jobs.active_job_ids and not scan_observation_history(s.world)
        assert s.meta.rng_counter == counter and s.world.next_scan_observation_seq==1


def test_05_context_and_sensor_interruptions_do_not_record():
    for changed in ('origin','sensors','service'):
        s,e=_state(),Engine()
        job=_queue(s,e)
        if changed=='origin':s.world.current_node_id=TARGET_ID
        elif changed=='sensors':s.ship.systems['sensors'].state=SystemState.OFFLINE
        else:s.ship.systems['sensors'].service.is_running=False
        counter=s.meta.rng_counter
        events=e.tick(s,job.eta_s+.01)
        assert job.status == JobStatus.FAILED
        assert any(v.type == EventType.JOB_FAILED for v in events)
        assert not s.world.scan_observations and s.world.next_scan_observation_seq==1
        assert counter == s.meta.rng_counter


def test_06_cancel_before_and_during_work_does_not_record():
    for started in (False,True):
        s,e=_state(),Engine()
        job=_queue(s,e)
        if started:e.tick(s,1.0)
        counter=s.meta.rng_counter
        e.apply_action(s,JobCancel(job_id=job.job_id))
        e.tick(s,Balance.SCAN_TIME_S+1)
        assert job.status == JobStatus.CANCELLED
        assert not s.world.scan_observations and counter == s.meta.rng_counter
        assert e._apply_job_effect(s,job)==[]


def test_07_repeated_ticks_effects_and_compatibility_do_not_duplicate():
    s,e=_state(),Engine()
    job=_queue(s,e)
    _complete(s,e,job,(TARGET_ID,))
    snapshot=scan_observation_history(s.world)
    counter=s.meta.rng_counter
    for _ in range(3):
        assert e._apply_job_effect(s,job)==[]
        e.tick(s,.01)
    assert scan_observation_history(s.world)==snapshot and counter == s.meta.rng_counter
    with patch.object(engine_mod,'random',_rolls(s)):
        seen,new,_,_,error=repl._scan_and_discover(s)
    assert error is None and not seen and not new
    assert len(s.world.scan_observations)==2 and s.world.scan_observations[-1].job_key is None
    s.ship.systems['sensors'].service.is_running=False
    assert repl._scan_and_discover(s)[-1]
    assert len(s.world.scan_observations)==2
    # Two separate jobs may finish at the same engine time. Both are sweeps,
    # while replaying either completed effect must remain inert.
    s,e=_state(),Engine()
    jobs=(_queue(s,e),_queue(s,e))
    with patch.object(engine_mod,'random',_rolls(s,completion_t=8.01)):
        events=e.tick(s,8.01)
    history=scan_observation_history(s.world)
    assert [o.observation_id for o in history]==['SCAN00001','SCAN00002']
    assert [o.job_key for o in history]==[j.internal_id for j in jobs]
    assert history[0].t==history[1].t==8.01
    assert [o.rng_counter for o in history]==[1,2]
    assert sum(v.data.get('message_key')=='job_completed_scan' for v in events)==2
    assert all(e._apply_job_effect(s,j)==[] for j in jobs)
    assert scan_observation_history(s.world)==history


def test_08_execution_conditions_not_queue_snapshot():
    s,e=_state(),Engine()
    job=_queue(s,e)
    s.ship.systems['sensors'].state=SystemState.LIMITED
    s.ship.sensors_range_ly=1.25
    origin=s.world.space.nodes[ORIGIN_ID]
    origin.x_ly=.1
    observation,_=_complete(s,e,job,(TARGET_ID,))
    assert observation.position_ly == (.1,0.0,0.0)
    assert observation.radius_ly == 1.25
    assert observation.sensors_state == SystemState.LIMITED
    assert observation.detection_factor == Balance.SENSORS_DETECT_P_LIMITED
    assert observation.sensord_running and not observation.sensors_forced_offline
    assert (observation.near_probability,observation.far_probability)==(
        Balance.SENSORS_DETECT_P_NEAR,Balance.SENSORS_DETECT_P_FAR)


def test_09_worldgen_failure_is_failed_job_not_negative_observation():
    s,e=_state(),Engine()
    job=_queue(s,e)
    counter=s.meta.rng_counter
    with patch.object(engine_mod,'ensure_sector_generated',side_effect=ValueError('budget incomplete')):
        events=e.tick(s,job.eta_s+.01)
    assert job.status == JobStatus.FAILED and not s.jobs.active_job_ids
    assert not s.world.scan_observations and counter == s.meta.rng_counter
    assert 'scan_observation_id' not in job.params
    failure=next(v for v in events if v.data.get('reason')=='scan_evaluation_incomplete')
    assert failure.type == EventType.JOB_FAILED
    assert not any(v.data.get('message_key')=='job_completed_scan' for v in events)
    with patch.object(engine_mod,'ensure_sector_generated',side_effect=ValueError('incomplete')):
        try:repl._scan_and_discover(s)
        except ValueError:pass
        else:raise AssertionError('Compatibility call disguised incomplete query as success')
    assert not s.world.scan_observations


def test_10_exception_after_some_materialization_leaves_no_absence_evidence():
    s,e=_state(),Engine()
    job=_queue(s,e)
    original=engine_mod.ensure_sector_generated
    calls=[]
    def partial(state,sid):
        calls.append(sid)
        if len(calls)==2:raise RuntimeError('later sector failed')
        return original(state,sid)
    known=set(s.world.known_nodes)
    with patch.object(engine_mod,'ensure_sector_generated',side_effect=partial):
        events=e.tick(s,job.eta_s+.01)
    assert len(calls)==2 and s.world.generated_sectors
    assert job.status == JobStatus.FAILED and not s.world.scan_observations
    assert known == s.world.known_nodes
    assert any(v.type == EventType.JOB_FAILED for v in events)


def test_11_multiple_save_load_cycles_and_scanning_after_load():
    s,e=_state(),Engine()
    _complete(s,e,_queue(s,e),(TARGET_ID,))
    _complete(s,e,_queue(s,e),(TARGET_ID,))
    _complete(s,e,_queue(s,e))
    history=scan_observation_history(s.world)
    assert [o.outcome for o in history]==[ScanOutcome.NEW_CONTACTS,ScanOutcome.KNOWN_CONTACTS_ONLY,ScanOutcome.NO_SIGNALS]
    with TemporaryDirectory() as tmp:
        slot=Path(tmp)/'memory.dat'
        for _ in range(3):
            save_load.save_single_slot(s,slot)
            loaded=save_load.load_single_slot(slot)
            assert loaded and loaded.source=='primary'
            s=loaded.state
            assert s.meta.save_version==3 and scan_observation_history(s.world)==history
            assert s.world.next_scan_observation_seq==4
        old_job=next(j for j in s.jobs.jobs.values() if j.params.get('scan_observation_id'))
        assert e._apply_job_effect(s,old_job)==[]
        observation,_=_complete(s,e,_queue(s,e))
        assert observation.observation_id=='SCAN00004'
        assert history==scan_observation_history(s.world)[:3]


def test_12_retention_ids_and_completed_job_replay_after_pruning():
    s,e=_state(),Engine()
    job=_queue(s,e)
    first,_=_complete(s,e,job)
    s.ship.sensors_range_ly=0.0
    knowledge=(set(s.world.known_nodes),set(s.world.known_contacts),copy.deepcopy(s.world.known_links),
               copy.deepcopy(s.world.known_intel),copy.deepcopy(s.world.intel),copy.deepcopy(s.world.node_pools))
    for _ in range(SCAN_OBSERVATION_LIMIT+5):
        s.clock.t+=1
        with patch.object(engine_mod,'random',_rolls(s)):
            e._perform_scan(s)
    history=scan_observation_history(s.world)
    assert len(history)==128 and first not in history
    assert len({v.observation_id for v in history})==128
    assert [v.t for v in history]==sorted(v.t for v in history)
    assert history[0].observation_id=='SCAN00007' and history[-1].observation_id=='SCAN00134'
    assert s.world.next_scan_observation_seq==135
    assert knowledge==(s.world.known_nodes,s.world.known_contacts,s.world.known_links,
                       s.world.known_intel,s.world.intel,s.world.node_pools)
    counter=s.meta.rng_counter
    assert e._apply_job_effect(s,job)==[] and s.meta.rng_counter==counter
    assert scan_observation_history(s.world)==history
    with TemporaryDirectory() as tmp:
        slot=Path(tmp)/'retained.dat'
        save_load.save_single_slot(s,slot)
        s=save_load.load_single_slot(slot).state
        assert scan_observation_history(s.world)==history
        with patch.object(engine_mod,'random',_rolls(s)):e._perform_scan(s)
        assert s.world.scan_observations[-1].observation_id=='SCAN00135'
        assert len(s.world.scan_observations)==128


def test_13_genuine_schema3_slot_shape_without_history_loads_safely():
    s=_state()
    _queue(s,Engine())
    gen.pin_universe(s)
    # Emit the exact former WorldState pickle slot representation: no new slots.
    old_slots={f.name:getattr(s.world,f.name) for f in fields(s.world)
               if f.name not in {'scan_observations','next_scan_observation_seq'}}
    with patch.object(WorldState,'__getstate__',lambda self:(None,old_slots)):
        blob=pickle.dumps(s,protocol=pickle.HIGHEST_PROTOCOL)
    raw=save_load._SAVE_MAGIC+b'\n'+hashlib.sha256(blob).hexdigest().encode()+b'\n'+blob
    with TemporaryDirectory() as tmp:
        slot=Path(tmp)/'existing-schema3.dat'
        slot.write_bytes(raw)
        loaded=save_load.load_single_slot(slot)
        assert loaded and loaded.source=='primary' and loaded.state.meta.save_version==3
        assert slot.read_bytes()==raw
        s=loaded.state
        assert scan_observation_history(s.world)==() and s.world.next_scan_observation_seq==1
        resumed_job=s.jobs.jobs[s.jobs.active_job_ids[-1]]
        observation,_=_complete(s,Engine(),resumed_job,(TARGET_ID,))
        assert observation.observation_id=='SCAN00001'


def test_14_immutable_read_api_and_no_retroactive_aliases():
    s,e=_state(),Engine()
    with patch.object(engine_mod,'random',_rolls(s,(TARGET_ID,))):
        seen,new,_=e._perform_scan(s)
    observation=s.world.scan_observations[-1]
    seen.clear();new.clear()
    snapshot=pickle.dumps(s)
    with patch.object(gen,'ensure_sector_generated',side_effect=AssertionError('writer')):
        history=scan_observation_history(s.world)
        assert isinstance(history,tuple) and history[0].detected_ids==(TARGET_ID,)
    assert pickle.dumps(s)==snapshot
    try:observation.radius_ly=999
    except FrozenInstanceError:pass
    else:raise AssertionError('Mutable observation')
    s.world.space.nodes[TARGET_ID].name='Changed later'
    assert observation.detected_ids==(TARGET_ID,)


def test_15_hidden_and_protected_manifest_sites_never_leak_from_query():
    s,e=_state(),Engine()
    gen.ensure_sector_generated(s,'S+000_+000_+000')
    s.world.forced_hidden_nodes.add(TARGET_ID)
    before_known=set(s.world.known_nodes)
    with patch.object(lore,'_locked_primary_targets',return_value={TARGET_ID}):
        with patch.object(engine_mod,'random',_rolls(s)):
            e._perform_scan(s)
        assert TARGET_ID not in s.world.scan_observations[-1].detected_ids
        assert set(s.world.known_nodes)==before_known
        assert not s.world.scan_observations[-1].new_ids
        # Existing deliberate natural-scan exception remains: an actual detected
        # protected contact may be recorded, with no free route publication.
        links=copy.deepcopy(s.world.known_links)
        with patch.object(engine_mod,'random',_rolls(s,(TARGET_ID,))):e._perform_scan(s)
        assert s.world.scan_observations[-1].new_ids==(TARGET_ID,)
        assert s.world.known_links==links
    definition=gen.universe_definition(s)
    snapshot=pickle.dumps(s)
    manifest.query_physical_sectors(definition,('S+000_+000_+000',))
    assert pickle.dumps(s)==snapshot
    all_recorded={nid for o in s.world.scan_observations for nid in o.detected_ids}
    assert all_recorded=={TARGET_ID}


def test_16_physical_z_spill_observed_from_actual_position():
    s=create_initial_state_prologue()
    s.meta.rng_seed=271828
    d=gen.universe_definition(s)
    target=next(t for t in manifest.query_physical_sectors(d,('S+15126_+000_+001',)).sites
                if t.generation_sector_id=='S+15126_+000_+000')
    nid=manifest.operative_id(d,target)
    s.world.current_node_id=s.ship.current_node_id='NO_PHYSICAL_ORIGIN'
    s.world.current_pos_ly=target.position_ly
    s.ship.sensors_range_ly=.001
    with patch.object(engine_mod,'random',_rolls(s,(nid,))):
        seen,_,_=Engine()._perform_scan(s)
    observation=s.world.scan_observations[-1]
    assert nid in seen and observation.new_ids==(nid,)
    assert observation.position_ly==target.position_ly and observation.origin_node_id is None
    assert s.world.space.nodes[nid].generation_sector_id=='S+15126_+000_+000'
    assert nid in s.world.sector_states['S+15126_+000_+001'].node_ids
    gen.validate_universe_state(s)


def test_17_exact_prechange_rng_and_world_results_across_seeds_conditions():
    for seed in (0,1,2,29,271828):
        for sensor_state in (SystemState.NOMINAL,SystemState.LIMITED,SystemState.DAMAGED):
            s=_state()
            s.meta.rng_seed=seed
            s.clock.t=23.125
            s.ship.systems['sensors'].state=sensor_state
            old=copy.deepcopy(s)
            rng_before=engine_mod.random.getstate()
            expected=baseline_scan(Engine(),old)
            actual=Engine()._perform_scan(s)
            assert actual==expected,(seed,sensor_state)
            assert old.meta.rng_counter==s.meta.rng_counter==1
            assert engine_mod.random.getstate()==rng_before
            descriptor=asdict(s)
            descriptor['world']['scan_observations']=[]
            descriptor['world']['next_scan_observation_seq']=1
            assert descriptor==asdict(old),(seed,sensor_state)


def test_18_recovery_entry_exception_keeps_single_rng_increment():
    s,e=_state(),Engine()
    s.world.exploration_recovery.entry_node_id=TARGET_ID
    before=s.meta.rng_counter
    with patch.object(engine_mod,'random',_rolls(s)):
        seen,_,_=e._perform_scan(s)
    observation=s.world.scan_observations[-1]
    assert seen==[TARGET_ID] and observation.guaranteed_ids==(TARGET_ID,)
    assert observation.rng_counter==before+1==s.meta.rng_counter
    assert not s.world.known_links


def test_19_bilingual_public_event_presentation_shared_by_textual():
    cases=[]
    for known,detected,outcome in ((False,(),ScanOutcome.NO_SIGNALS),
            (True,(TARGET_ID,),ScanOutcome.KNOWN_CONTACTS_ONLY),(False,(TARGET_ID,),ScanOutcome.NEW_CONTACTS)):
        s,e=_state(),Engine()
        if known:s.world.known_nodes.add(TARGET_ID);s.world.known_contacts.add(TARGET_ID)
        observation,events=_complete(s,e,_queue(s,e),detected)
        assert observation.outcome==outcome
        cases.append((s,events,outcome))
    for s,events,outcome in cases:
        tagged=[('cmd',v) for v in events]
        for locale in (Locale.EN,Locale.ES):
            s.os.locale=locale
            output=io.StringIO()
            with redirect_stdout(output):repl.render_events(s,tagged)
            text=output.getvalue()
            assert '\n'.join(presenter.format_event_lines(s,tagged))==text.rstrip('\n')
            if outcome==ScanOutcome.NO_SIGNALS:
                assert ('does not confirm' if locale==Locale.EN else 'no confirma') in text
                assert TARGET_ID not in text
            elif outcome==ScanOutcome.KNOWN_CONTACTS_ONLY:
                assert ('already known' if locale==Locale.EN else 'ya eran conocidos') in text
                assert 'does not confirm' not in text and 'no confirma' not in text
            else:assert TARGET_ID in text and '(scan) new:' in text
    s,e=_state(),Engine()
    job=_queue(s,e)
    with patch.object(engine_mod,'ensure_sector_generated',side_effect=ValueError('incomplete')):
        events=e.tick(s,job.eta_s+.01)
    for locale in (Locale.EN,Locale.ES):
        s.os.locale=locale
        text='\n'.join(presenter.format_event_lines(s,[('cmd',v) for v in events]))
        assert ('no result recorded' if locale==Locale.EN else 'no se registró un resultado') in text
        assert '=== SCAN ===' not in text


def test_20_stopped_waypoint_and_live_transit_keep_existing_gates():
    from tests.nav_abort_waypoint_cleanup_smoke import _stopped
    e,s,tmp=_stopped()
    assert 'scan_in_transit' not in s.ship.installed_modules
    observation,_=_complete(s,e,_queue(s,e))
    assert observation.origin_node_id==tmp
    assert observation.position_ly==s.world.current_pos_ly
    s=_state()
    s.ship.in_transit=True
    assert any(v.type==EventType.BOOT_BLOCKED for v in Engine().apply_action(s,Scan()))
    assert not s.world.scan_observations


def main():
    tests=[f for name,f in sorted(globals().items()) if name.startswith('test_')]
    for test in tests:
        test()
        print('PASS',test.__name__,flush=True)
    print(f'SCAN OBSERVATION MEMORY SMOKE PASSED ({len(tests)} groups)')


if __name__=='__main__':main()
