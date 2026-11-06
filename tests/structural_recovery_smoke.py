"""4D-3e5: real manifest, radio, public commands, transactions and persistence.

Synthetic physical definitions exercise difficult geometry without mocking any
navigation, delivery or gameplay kernel. Public journey performs no state edits
after loading its declared scene. Installed-content regressions run separately.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
import math
import os
from pathlib import Path
import pickle
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import tracemalloc
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox, create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core import structural_recovery as rec, lore, communications
from retorno.core.communications import retry_radio_opportunities, mark_radio_read, radio_diagnostic_lines
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.engine import Engine
from retorno.core.exploration_recovery import ensure_exploration_recovery, has_exploration_frontier
from retorno.io import save_load
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import WorldState, NodePoolState, DeadNodeState, SpaceNode, sector_id_for_pos
from retorno.runtime.data_loader import load_worldgen_templates, load_worldgen_archetypes
from retorno.ui_textual import presenter
from retorno.worldgen import generator as gen, manifest as m

E = Engine()
SMALL = rec.RecoveryBudget(sectors=0)


def scene(spec=None, *, present=None, known=("A",), clean=True, seed=271828):
    spec = spec or [("A","station",(1000.,1000.,1000.)),("B","ship",(1003.,1000.,1000.))]
    s = create_initial_state_sandbox()
    s.meta.rng_seed = seed
    snap = deepcopy(s.world.narrative_snapshot)
    snap.update(declarations=[{"test_scene": True}], arcs=[], singles=[], reservations={}, aliases={},
        locations=[{"node": {"node_id": nid, "kind": kind, "is_hub": kind in rec.HUBS,
            **dict(zip(("x_ly","y_ly","z_ly"),pos))}} for nid,kind,pos in spec])
    templates, archetypes = deepcopy(load_worldgen_templates()), deepcopy(load_worldgen_archetypes())
    for cfg in archetypes.values():
        cfg.update(node_count_min=0, node_count_max=0)
    authored = tuple(m.AuthoredSite(nid, kind, pos, kind in rec.HUBS) for nid,kind,pos in spec)
    definition = m.define_manifest(seed, templates=templates, archetypes=archetypes,
        authored=authored, narrative_key=snap["catalog_key"])
    s.world = WorldState(manifest_definition=definition, narrative_snapshot=snap,
        universe_rules_key=definition.rules_key, rng_seed=seed)
    present = {nid for nid,_,_ in spec} if present is None else set(present)
    sectors = {sector_id_for_pos(*p) for nid,_,p in spec if nid in present}
    gen._ensure_sector_generated_core(s, sorted(sectors))
    at(s, "A")
    s.world.known_nodes = set(known)
    s.world.known_contacts = set(known)
    s.world.visited_nodes = {"A"}
    if clean:
        s.world.node_pools["A"] = NodePoolState(window_open=False, node_cleaned=True, uplink_data_consumed=True)
    return s


def at(s, nid):
    n = s.world.space.nodes[nid]
    s.world.current_node_id = s.ship.current_node_id = nid
    s.world.current_pos_ly = (n.x_ly,n.y_ly,n.z_ly)
    s.ship.docked_node_id = None


def ready(s):
    s.ship.power.e_batt_kwh = s.ship.power.e_batt_max_kwh
    s.ship.power.power_quality = 1
    s.ship.power.brownout = False
    for sysid in ("power_core","energy_distribution","core_os","comms"):
        system = s.ship.systems[sysid]
        system.health = .95
        system.state = SystemState.NOMINAL
        system.forced_offline = system.state_locked = False
    s.ship.systems["comms"].service.is_running = True


def pure(s, *args, **kwargs):
    before, rng = pickle.dumps(s), random.getstate()
    result = rec.select_recovery(s,*args,**kwargs)
    assert pickle.dumps(s) == before and random.getstate() == rng
    return result


def proposal(s, target=None, **kwargs):
    r = pure(s, "deadnode:"+target if target else "global", target, budget=SMALL, **kwargs)
    assert r.status == "validated", (r.status,r.reason)
    return r.proposal


def path(s,p):
    return rec._path(s,p)


def reject(callback):
    try:
        callback()
    except (ValueError,save_load.SaveLoadError):
        return
    raise AssertionError("Expected explicit rejection")


def read(s, file):
    with redirect_stdout(io.StringIO()):
        repl.render_cat(s,file)


def test_01_existing_certified_and_no_physical_invention():
    s=scene(); p=proposal(s)
    assert path(s,p)==("A","B")
    before=deepcopy((s.world.known_nodes,s.world.known_links,s.world.intel,s.world.node_pools))
    pool=s.world.node_pools["A"]; node=s.world.space.nodes["A"]
    plan=rec.confirm_recovery(s,p)
    assert pool is s.world.node_pools["A"] and node is s.world.space.nodes["A"]
    assert before==(s.world.known_nodes,s.world.known_links,s.world.intel,s.world.node_pools)
    assert plan.status=="receipt_pending" and not plan.captured
    assert rec.confirm_recovery(s,p) is plan
    gen.validate_universe_state(s)


def test_02_lazy_target_and_authored_narrative_identity():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1045.,1000.,1000.))],present={"A"})
    assert "B" not in s.world.space.nodes
    p=proposal(s,"B"); s.world.dead_nodes["B"]=DeadNodeState(dead_since_t=0)
    # Tracker belongs to the confirmation snapshot.
    p=proposal(s,"B")
    rec.confirm_recovery(s,p)
    assert s.world.space.nodes["B"].historical_key==p.sites[-1].identity.encoded
    assert s.world.space.nodes["B"].x_ly==1045
    gen.validate_universe_state(s)
    # Actual e4 authored integration, not a reference interpreted from prose.
    from narrative_world_integration_smoke import installed
    with installed():
        n=create_initial_state_prologue(seed=1)
        site=m.resolve_operative_id(gen.universe_definition(n),"TEST_STATION")
        assert site is not None and site.identity.namespace=="authored"


def test_03_positive_inclusive_cap_and_missing_endpoint():
    for distance, status in ((45.,"validated"),(45.00000001,"none_in_scope"),(0.,"none_in_scope")):
        s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1000.+distance,1000.,1000.))])
        r=pure(s,"case","B",budget=SMALL)
        assert r.status==status,(distance,r.status)
    assert pure(scene(),"case","ABSENT",budget=SMALL).status=="invalid"


def test_04_multi_stage_and_detour():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","relay",(1030.,1020.,1000.)),
             ("C","ship",(1060.,1000.,1000.))])
    p=proposal(s,"C")
    assert path(s,p)==("A","B","C") and p.mechanisms==("radio","radio")
    assert sum(math.dist(a.position_ly,b.position_ly) for a,b in zip(p.sites,p.sites[1:]))>60


def test_05_directed_complete_distance_beats_euclidean_origin():
    # NEAR is close to target, but costs a 3-edge directed detour to access.
    s=scene([("A","ship",(1000.,1000.,1000.)),("X","ship",(1020.,1030.,1000.)),
        ("Y","ship",(1040.,1030.,1000.)),("NEAR","relay",(1030.,1000.,1000.)),
        ("GOOD","station",(1000.,1010.,1000.)),("T","ship",(1031.,1000.,1000.))],known=("A","X","Y","NEAR","GOOD"))
    s.world.known_links={"A":{"X","GOOD"},"X":{"Y"},"Y":{"NEAR"}}
    r=pure(s,"directed_case","T",budget=SMALL)
    assert r.status=="conditional" and r.reason=="first_reception_outside_coverage"
    p=r.proposal
    assert p is not None
    assert path(s,p)==("GOOD","T") and p.access.path==("A","GOOD")
    s.world.known_links={"GOOD":{"A"},"NEAR":{"A"}}
    assert pure(s,"x","T",budget=SMALL).status=="conditional"


def test_06_pure_economy_hardware_radiation_independence():
    s=scene(); expected=proposal(s)
    for scrap,energy,health in ((0,0,.01),(99999,5,.99)):
        t=deepcopy(s);t.ship.cargo_scrap=scrap;t.ship.power.e_batt_kwh=energy
        for system in t.ship.systems.values():
            system.health=health;system.state=SystemState.OFFLINE;system.forced_offline=True
        t.ship.drones.clear();t.ship.power.brownout=True
        t.world.space.nodes["A"].radiation_rad_per_s=99
        assert proposal(t)==expected


def test_07_empty_isolated_and_no_emitter():
    s=scene([("A","station",(1000.,1000.,1000.))])
    r=pure(s,budget=rec.RecoveryBudget(sectors=4))
    assert r.status=="none_in_scope" and not r.retained[0].kind=="ship"
    s=scene([("A","ship",(1000.,1000.,1000.)),("B","ship",(1003.,1000.,1000.))])
    before=pickle.dumps(s)
    assert pure(s,budget=SMALL).status=="conditional"
    assert pickle.dumps(s)==before
    ensure_exploration_recovery(s,"scan")
    assert not s.world.radio_opportunities and not s.world.recovery_plans


def test_08_budgets_and_widening_without_maximum_distance():
    s=scene([("A","station",(1000.,1000.,1000.))])
    assert pure(s,budget=rec.RecoveryBudget(expansions=0)).status=="incomplete"
    assert pure(scene(),budget=rec.RecoveryBudget(edges=0)).status=="incomplete"
    cursor=0;seen=set()
    for _ in range(5):
        r=pure(s,cursor=cursor,budget=rec.RecoveryBudget(sectors=8))
        assert r.cursor>cursor and set(r.sectors)-seen
        cursor=r.cursor;seen.update(r.sectors)
    # Unranking permits a distant later scope without replaying millions of queries.
    r=pure(s,cursor=(2*1000+1)**3,budget=rec.RecoveryBudget(sectors=1))
    assert abs(int(r.sectors[0][1:].split("_")[0])-100)>999
    # A real lazy opportunity outside the first query is found by widening.
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1040.,1000.,1000.))],present={"A"})
    cursor=0;retained=();statuses=[]
    for _ in range(60):
        r=pure(s,cursor=cursor,retained=retained,budget=rec.RecoveryBudget(sectors=16))
        statuses.append(r.status)
        if r.proposal:
            assert path(s,r.proposal)==("A","B");break
        cursor,retained=r.cursor,r.retained
    assert statuses[0]=="none_in_scope" and statuses[-1]=="validated",statuses


def test_09_transaction_stale_collision_and_injected_failure():
    s=scene();p=proposal(s);s.world.space.nodes["B"].x_ly+=.1
    before=pickle.dumps(s);reject(lambda:rec.confirm_recovery(s,p));assert pickle.dumps(s)==before
    s=scene();p=proposal(s);s.world.visited_nodes.add("B")
    before=pickle.dumps(s);reject(lambda:rec.confirm_recovery(s,p));assert pickle.dumps(s)==before
    s=scene();p=proposal(s);before=pickle.dumps(s)
    # Failure after physical preparation, before publication.
    with patch.object(rec,"_radio_stage",side_effect=ValueError("injected preparation failure")):
        reject(lambda:rec.confirm_recovery(s,p))
    assert pickle.dumps(s)==before


def test_10_gates_capture_read_no_full_chain():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","relay",(1040.,1000.,1000.)),("C","ship",(1080.,1000.,1000.))])
    s.world.dead_nodes["C"]=DeadNodeState(dead_since_t=0)
    plan=rec.confirm_recovery(s,proposal(s,"C"))
    assert retry_radio_opportunities(s)==[] and not plan.captured
    assert s.world.dead_nodes["C"].attempts==0 and s.world.dead_nodes["C"].last_action_t==0
    ready(s);s.ship.systems["comms"].service.is_running=False
    assert retry_radio_opportunities(s)==[]
    s.ship.systems["comms"].service.is_running=True
    s.ship.in_transit=True;assert retry_radio_opportunities(s)==[];s.ship.in_transit=False
    s.ship.is_hibernating=True;assert retry_radio_opportunities(s)==[];s.ship.is_hibernating=False
    assert len(retry_radio_opportunities(s))==1 and plan.captured==(0,)
    assert s.world.dead_nodes["C"].attempts==1 and s.world.dead_nodes["C"].last_action_t==0
    op=s.world.radio_opportunities[plan.plan_id+":0"]
    assert "C" not in s.world.known_nodes and "LINK: B -> C" not in s.os.fs[op.path].content
    assert not s.world.known_links
    assert retry_radio_opportunities(s)==[]
    at(s,"B");rec.advance_recovery_plans(s)
    assert len(s.world.radio_opportunities)==1  # Visiting is insufficient without reading.
    at(s,"A");read(s,op.path);assert plan.consumed==(0,)
    assert s.world.known_links=={"A":{"B"},"B":{"A"}}
    rec.advance_recovery_plans(s);assert plan.stage==0
    at(s,"B");rec.advance_recovery_plans(s)
    assert plan.stage==1 and len(retry_radio_opportunities(s))==1
    read(s,s.world.radio_opportunities[plan.plan_id+":1"].path)
    assert s.world.dead_nodes["C"].attempts==1
    at(s,"C");rec.advance_recovery_plans(s);assert plan.status=="complete"


def test_11_leave_return_and_invalid_source_at_capture():
    s=scene();plan=rec.confirm_recovery(s,proposal(s));ready(s)
    at(s,"B");assert retry_radio_opportunities(s)==[]
    at(s,"A");assert len(retry_radio_opportunities(s))==1
    assert s.world.mobility_failsafe_count==1
    t=scene();plan=rec.confirm_recovery(t,proposal(t));ready(t)
    t.world.space.nodes.pop("B")
    assert retry_radio_opportunities(t)==[] and not plan.captured
    assert t.world.mobility_failsafe_count==0


def test_12_closed_pools_and_salvage_preparation():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1040.,1000.,1000.)),("C","ship",(1080.,1000.,1000.))])
    s.world.dead_nodes["C"]=DeadNodeState(dead_since_t=0)
    p=proposal(s,"C");assert p.mechanisms==("radio","salvage")
    pool_before=deepcopy(s.world.node_pools["A"])
    plan=rec.confirm_recovery(s,p)
    assert s.world.node_pools["A"]==pool_before
    pool=s.world.node_pools["B"]
    assert pool.window_open and len(pool.injected_files)==1 and not s.os.fs.get("/remote/B")
    rec.confirm_recovery(s,p);assert len(pool.injected_files)==1
    for visited,closed,cleaned in ((True,False,False),(False,True,False),(False,False,True)):
        t=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1040.,1000.,1000.)),("C","ship",(1080.,1000.,1000.))])
        t.world.node_pools["B"]=NodePoolState(window_open=not closed,node_cleaned=cleaned)
        if visited:t.world.visited_nodes.add("B")
        before=pickle.dumps(t)
        assert pure(t,"x","C",budget=SMALL).status=="none_in_scope"
        assert pickle.dumps(t)==before


def test_13_protected_primary_reserved_host_and_unsupported_reference():
    s=scene();s.world.narrative_snapshot["arcs"]=[{"arc_id":"protect","primary_intel":{"kind":"node","line":"NODE: B"}}]
    assert pure(s,"x","B",budget=SMALL).status=="invalid"
    s.world.narrative_snapshot["arcs"][0]["primary_intel"]={"kind":"unrecognized","id":"p"}
    assert pure(s,budget=SMALL).status=="invalid"
    s=scene();s.world.narrative_snapshot["reservations"]={"optional":{"node_id":"B"}}
    assert pure(s,budget=SMALL).status=="none_in_scope"
    assert not s.world.lore.delivered


def test_14_persist_all_boundaries_and_reject_incompatible():
    s=scene();p=proposal(s)
    with TemporaryDirectory() as tmp:
        slot=Path(tmp)/"slot.dat"
        save_load.save_single_slot(s,slot);s=save_load.load_single_slot(slot).state
        assert proposal(s)==p
        plan=rec.confirm_recovery(s,p)
        for phase in ("pending","captured","read","complete"):
            if phase=="captured":ready(s);retry_radio_opportunities(s)
            if phase=="read":read(s,s.world.radio_opportunities[plan.plan_id+":0"].path)
            if phase=="complete":at(s,"B");rec.advance_recovery_plans(s)
            before=deepcopy(s.world)
            save_load.save_single_slot(s,slot);s=save_load.load_single_slot(slot).state
            plan=s.world.recovery_plans[plan.plan_id]
            assert s.world==before
            assert retry_radio_opportunities(s)==[]
        data=slot.read_bytes();plan.version="incompatible"
        reject(lambda:save_load.save_single_slot(s,slot));assert slot.read_bytes()==data


def test_15_real_world_multiseed_order_z_and_topology():
    for seed in (2,29,271828):
        a=create_initial_state_prologue(seed=seed)
        b=deepcopy(a)
        ids=("S+020_+020_+000","S+021_+020_+000")
        for sid in ids:gen.ensure_sector_generated(a,sid)
        for sid in reversed(ids):gen.ensure_sector_generated(b,sid)
        assert a.world==b.world
        ra,rb=pure(a),pure(b)
        assert ra==rb
    d=m.define_manifest(271828)
    spill=m.query_physical_sectors(d,("S+15126_+000_+001",))
    assert any(x.generation_sector_id=="S+15126_+000_+000" for x in spill.sites)
    # Selection includes the same certified spill inventory without materializing.
    s=create_initial_state_prologue(seed=271828)
    s.world.current_pos_ly=(151265.,5.,15.)
    r=pure(s,budget=rec.RecoveryBudget(sectors=1))
    assert any(x.identity in {p.identity for p in spill.sites} for x in r.retained)


def test_16_runtime_global_frontier_and_deadnode_counters():
    s=scene();assert not has_exploration_frontier(s)
    before=deepcopy(s.world.node_pools)
    ensure_exploration_recovery(s,"scan")
    assert len(s.world.recovery_plans)==1 and len(s.world.radio_opportunities)==1
    assert s.world.mobility_failsafe_count==0 and s.world.node_pools==before
    for _ in range(3):ensure_exploration_recovery(s,"scan")
    assert len(s.world.recovery_plans)==1 and len(s.world.radio_opportunities)==1
    s=scene();s.world.known_links={"A":{"B"}};s.world.known_nodes.add("B")
    assert has_exploration_frontier(s)
    ensure_exploration_recovery(s,"scan");assert not s.world.recovery_plans
    # Structural frontier remains real with the receiver and all hardware off.
    s.ship.systems["data_core"].state=SystemState.OFFLINE
    assert has_exploration_frontier(s)
    s=scene();s.world.known_contacts.add("B")
    s.world.dead_nodes["B"]=DeadNodeState(dead_since_t=0,dead_threshold_uplinks=20,dead_threshold_years=50)
    assert evaluate_dead_nodes(s,"scan")==[]
    assert s.world.dead_nodes["B"].attempts==0
    ready(s);assert len(retry_radio_opportunities(s))==1
    assert s.world.dead_nodes["B"].attempts==1
    assert evaluate_dead_nodes(s,"scan")==[]


def test_17_en_es_diagnostics_cli_textual_and_no_leaks():
    for locale in (Locale.EN,Locale.ES):
        s=scene();s.os.locale=locale
        rec.confirm_recovery(s,proposal(s))
        lines=radio_diagnostic_lines(s)
        assert all("pending=" not in line and "pendientes=" not in line and "Structural recovery" not in line and "Recuperación estructural" not in line for line in lines)
        assert all(next(iter(s.world.recovery_plans)) not in line and "LINK:" not in line for line in lines)
        with redirect_stdout(io.StringIO()) as out:repl.render_status(s)
        assert out.getvalue().strip().splitlines()==presenter.build_command_output(repl.render_status,s)
        ready(s);retry_radio_opportunities(s)
        op=next(iter(s.world.radio_opportunities.values()))
        assert ("AVISO LOCAL" if locale==Locale.ES else "LOCAL NAVIGATION") in s.os.fs[op.path].content


def test_18_process_determinism_and_input_order():
    s=scene();expected=pure(s,budget=SMALL)
    s.world.space.nodes=dict(reversed(list(s.world.space.nodes.items())))
    assert pure(s,budget=SMALL)==expected
    code="from tests.structural_recovery_smoke import scene, proposal, rec; s=scene(); print(rec._digest(proposal(s)))"
    results=[]
    for seed in ("1","987"):
        p=subprocess.run([sys.executable,"-c",code],env=dict(os.environ,PYTHONHASHSEED=seed),capture_output=True,text=True,check=True)
        results.append(p.stdout)
    assert results[0]==results[1]


def public_command(s,text):
    if text.startswith("cat "):
        read(s,text[4:]);return
    if text=="uplink":
        with redirect_stdout(io.StringIO()):repl._handle_uplink(s)
        return
    events=E.apply_action(s,parse_command(text))
    assert events or text.startswith("power "),(text,events)
    for _ in range(1000):
        if not s.jobs.active_job_ids:break
        E.tick(s,10 if text.startswith("route solve ") else 1)
    assert not s.jobs.active_job_ids,text


def test_19_public_commands_from_declared_scene_without_gameplay_edits():
    # Scene setup supplies only physical/content inputs and current location.
    # From here, every receiver transition, trigger, read and travel is public.
    # This declared saved scene starts at an exhausted host. It contains no
    # manufactured gameplay resources or prepared recovery. No edits follow.
    s=scene(clean=True)
    transcript=[]
    for command in ("power off security","power on comms","boot radiod","scan"):
        public_command(s,command);transcript.append(command)
    plans=list(s.world.recovery_plans.values())
    assert plans,"Public scan must trigger recovery after verifying empty sources"
    plan=plans[0];op=s.world.radio_opportunities[plan.plan_id+":0"]
    assert op.status=="received" and not s.world.known_links
    public_command(s,"cat "+op.path);transcript.append("cat "+op.path)
    assert "B" in s.world.known_links["A"]
    # The full travel uses the public navigation job and ordinary simulation.
    events=E.apply_action(s,parse_command("nav B"))
    assert any(e.type==EventType.TRAVEL_STARTED for e in events),events
    transcript.append("nav B")
    assert s.ship.in_transit
    E.tick(s,s.ship.arrival_t-s.clock.t+1)
    assert s.world.current_node_id=="B" and plan.status=="complete"
    print("PUBLIC SCENE FLOW:"," -> ".join(transcript),"; resources and systems use ordinary rules")


def test_20_metrics_and_technical_limits():
    samples=[]
    dense=create_initial_state_sandbox()
    gen._ensure_sector_cluster_generated(dense,[f"S{x:+04d}_{y:+04d}_+000" for x in range(20,24) for y in range(20,24)])
    for name,s in (("installed",create_initial_state_sandbox()),("chain",scene([
        ("A","station",(1000.,1000.,1000.)),("B","relay",(1040.,1000.,1000.)),("C","ship",(1080.,1000.,1000.))])),("materialized",dense)):
        tracemalloc.start();t=time.perf_counter()
        r=pure(s,"metric","C" if name=="chain" else None)
        elapsed=time.perf_counter()-t;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        samples.append(dict(case=name,status=r.status,seconds=round(elapsed,6),peak_bytes=peak,
            sectors=len(r.sectors),cohorts=r.examined_cohorts,expansions=r.expansions,edges=r.edges))
    print("SEARCH METRICS",json.dumps(samples,sort_keys=True))


def test_21_real_salvage_consumption_between_stages_and_load():
    for locale in (Locale.EN,Locale.ES):
        s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1040.,1000.,1000.)),("C","ship",(1080.,1000.,1000.))])
        s.os.locale=locale;s.world.dead_nodes["C"]=DeadNodeState(dead_since_t=0)
        s.world.known_contacts.add("C")
        plan=rec.confirm_recovery(s,proposal(s,"C"));ready(s);retry_radio_opportunities(s)
        read(s,s.world.radio_opportunities[plan.plan_id+":0"].path)
        at(s,"B");s.world.known_nodes.add("B");s.world.visited_nodes.add("B")
        lore.close_window_on_orbit_entry(s,"B");rec.advance_recovery_plans(s)
        assert plan.stage==1 and not plan.consumed==(0,1)
        with TemporaryDirectory() as tmp:
            slot=Path(tmp)/"slot.dat";save_load.save_single_slot(s,slot)
            s=save_load.load_single_slot(slot).state;plan=s.world.recovery_plans[plan.plan_id]
            public_command(s,"dock B")
            public_command(s,"drone deploy D1 B")
            public_command(s,"drone salvage data D1")
            remote=f"/remote/B/logs/nav/{plan.plan_id.replace(':','_')}_1.txt"
            assert remote in s.os.fs
            assert "C" not in s.world.known_nodes
            read(s,remote);assert plan.consumed==(0,1)
            assert s.world.dead_nodes["C"].attempts==1
            before=deepcopy(s.world.node_pools["B"])
            public_command(s,"drone salvage data D1")
            assert s.world.node_pools["B"]==before
            at(s,"C");rec.advance_recovery_plans(s);assert plan.status=="complete"
            assert plan.captured==(0,)  # Completed target may leave the legacy tracker set.


def test_22_failed_materialization_and_identity_collisions_are_atomic():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1045.,1000.,1000.))],present={"A"})
    s.world.dead_nodes["B"]=DeadNodeState(dead_since_t=0);p=proposal(s,"B")
    before=pickle.dumps(s)
    original=rec._ensure_sector_cluster_generated
    def fail_after_materialization(staged,sectors):
        original(staged,sectors)
        raise ValueError("failed after real lazy materialization")
    with patch.object(rec,"_ensure_sector_cluster_generated",side_effect=fail_after_materialization):
        reject(lambda:rec.confirm_recovery(s,p))
    assert pickle.dumps(s)==before and "B" not in s.world.space.nodes
    s=scene();p=proposal(s)
    ident="structural:"+rec._digest((rec.VERSION,p.scope,p.block,path(s,p),None))
    from retorno.core.communications import prepare_radio_opportunity
    prepare_radio_opportunity(s,ident+":0","station_broadcast",{"en":"collision"},node_id="A",trigger="test")
    p=proposal(s);before=pickle.dumps(s)
    reject(lambda:rec.confirm_recovery(s,p));assert pickle.dumps(s)==before


def test_23_primary_natural_scan_and_exact_manual_solve_remain_legal():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1001.,1000.,1000.))])
    s.world.narrative_snapshot["arcs"]=[{"arc_id":"protect","primary_intel":{"id":"p","kind":"node","line":"NODE: B"}}]
    assert "B" in lore._locked_primary_targets(s)
    assert pure(s,"x","B",budget=SMALL).status=="invalid"
    public_command(s,"scan")
    assert "B" in s.world.known_contacts
    t=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1001.,1000.,1000.))])
    t.world.narrative_snapshot["arcs"]=deepcopy(s.world.narrative_snapshot["arcs"])
    assert "B" not in t.world.known_nodes
    public_command(t,"route solve B")
    assert "B" in t.world.known_links.get("A",())


def test_24_domain_and_loaded_search_resume_are_explicit():
    s=scene([("A","station",(1000.,1000.,1000.))])
    s.world.current_pos_ly=(float(m.MAX_SECTOR_INDEX*10),0.,0.)
    assert pure(s,budget=rec.RecoveryBudget(sectors=1)).status=="incomplete"
    s=scene([("A","ship",(1000.,1000.,1000.))])
    rec.request_recovery(s)
    old=s.world.recovery_searches["global"]["cursor"]
    with TemporaryDirectory() as tmp:
        slot=Path(tmp)/"slot.dat";save_load.save_single_slot(s,slot)
        s=save_load.load_single_slot(slot).state
        rec.request_recovery(s)
        assert s.world.recovery_searches["global"]["cursor"]>old
        assert not s.world.radio_opportunities


def test_25_visited_physical_scale_uses_only_preexisting_known_route():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1040.,1000.,1000.)),("C","ship",(1080.,1000.,1000.))],known=("A","B","C"))
    s.world.visited_nodes.add("B")
    s.world.node_pools["B"]=NodePoolState(window_open=False,node_cleaned=True)
    s.world.known_links={"B":{"C"}}
    s.world.dead_nodes["C"]=DeadNodeState(dead_since_t=0)
    p=proposal(s,"C");assert p.mechanisms==("radio","known_route")
    pool=deepcopy(s.world.node_pools["B"])
    plan=rec.confirm_recovery(s,p);ready(s);retry_radio_opportunities(s)
    read(s,s.world.radio_opportunities[plan.plan_id+":0"].path)
    at(s,"B");rec.advance_recovery_plans(s)
    assert plan.consumed==(0,1) and s.world.node_pools["B"]==pool
    assert len(s.world.radio_opportunities)==1
    at(s,"C");rec.advance_recovery_plans(s);assert plan.status=="complete"


def test_26_installed_prologue_public_journey_without_fixture_or_overrides():
    # Separate from synthetic geometry: shipping content, new-game seed and
    # public commands only. Existing frontiers must suppress unnecessary rescue.
    s=create_initial_state_prologue(seed=701)
    script=["power off security","power off data_core","drone deploy D1 PWR-A1",
        "drone repair D1 power_core","drone repair D1 power_core","drone repair D1 power_core",
        "drone move D1 BUS-A2","drone repair D1 energy_distribution","drone repair D1 energy_distribution",
        "drone move D1 BRG-01","drone repair D1 comms","power on comms","boot radiod",
        "power on sensors","boot sensord","scan","route solve ECHO_7"]
    for command in script:public_command(s,command)
    assert "ECHO_7" in s.world.known_links.get(s.world.current_node_id,())
    events=E.apply_action(s,parse_command("nav ECHO_7"))
    assert any(e.type==EventType.TRAVEL_STARTED for e in events),events
    E.tick(s,s.ship.arrival_t-s.clock.t+1)
    public_command(s,"dock ECHO_7")
    assert s.ship.docked_node_id=="ECHO_7"
    assert s.ship.systems["comms"].service.is_running
    assert has_exploration_frontier(s) and not s.world.recovery_plans
    print("PUBLIC INSTALLED FLOW:"," -> ".join(script+["nav ECHO_7","dock ECHO_7"]),
          f"; t={s.clock.t}s scrap={s.ship.cargo_scrap}; existing frontier preserved")


def test_27_stored_node_frontier_and_stale_deadnode_counter():
    s=scene([("A","station",(1000.,1000.,1000.)),("B","ship",(1001.,1000.,1000.))])
    assert not has_exploration_frontier(s)
    lore.write_local_intel(s,"ship_os_mail","NODE: B\n")
    before=pickle.dumps(s);assert has_exploration_frontier(s);assert pickle.dumps(s)==before
    ensure_exploration_recovery(s,"scan");assert not s.world.recovery_plans
    s=scene();s.world.dead_nodes["B"]=DeadNodeState(dead_since_t=0)
    p=proposal(s,"B");s.world.dead_nodes["B"].attempts+=1
    before=pickle.dumps(s);reject(lambda:rec.confirm_recovery(s,p));assert pickle.dumps(s)==before


def test_28_remote_navigation_access_does_not_prove_first_reception():
    s=scene([("A","ship",(1000.,1000.,1000.)),("REMOTE","relay",(1010.,1000.,1000.)),
             ("T","ship",(1040.,1000.,1000.))],known=("A","REMOTE"))
    s.world.known_links={"A":{"REMOTE"}}
    r=pure(s,"remote_case","T",budget=SMALL)
    assert r.status=="conditional",(r.status,r.reason)
    assert r.proposal is not None and r.proposal.access.path==("A","REMOTE")
    before=pickle.dumps(s)
    reject(lambda:rec.confirm_recovery(s,r.proposal))
    assert pickle.dumps(s)==before
    rec.request_recovery(s,"remote_case","T")
    assert s.world.recovery_searches["remote_case"]["status"]=="conditional"
    assert not s.world.recovery_plans and not s.world.radio_opportunities
    assert s.world.mobility_failsafe_count==0 and s.world.exploration_recovery.generation==0


def test_29_local_first_reception_overrides_more_attractive_remote_chain():
    s=scene([("A","station",(1000.,1000.,1000.)),("L","relay",(1030.,1030.,1000.)),
        ("M","relay",(1060.,1030.,1000.)),("REMOTE","relay",(1060.,1000.,1000.)),
        ("T","ship",(1090.,1000.,1000.))],known=("A","POINT","REMOTE"))
    # A genuine navigation point is not a historical installation/source.
    s.world.space.nodes["POINT"]=SpaceNode("POINT","Point","nav_point",x_ly=1030,y_ly=1000,z_ly=1000)
    s.world.known_links={"A":{"POINT"},"POINT":{"REMOTE"}}
    access=rec.directed_access(s)["REMOTE"]
    assert access.distance_ly==60
    r=pure(s,"local_choice","T",budget=SMALL)
    assert r.status=="validated" and path(s,r.proposal)[0]=="A"
    distance=sum(math.dist(a.position_ly,b.position_ly) for a,b in zip(r.proposal.sites,r.proposal.sites[1:]))
    assert distance>access.distance_ly+30  # Remote 90 ly chain is informationally ineligible.
    p=rec.confirm_recovery(s,r.proposal)
    assert p.status=="receipt_pending" and not p.captured
    assert next(iter(s.world.radio_opportunities.values())).origin_node_id=="A"


def test_30_spatial_eligibility_is_independent_of_receiver_operation():
    s=scene()
    for state,health,forced in ((SystemState.OFFLINE,.72,True),(SystemState.DAMAGED,.3,False)):
        system=s.ship.systems["comms"]
        system.state,system.health,system.forced_offline=state,health,forced
        system.service.is_running=False
        before=pickle.dumps(s)
        assert communications.radio_spatial_block_reason(s,"A",channel="station_broadcast") is None
        assert pickle.dumps(s)==before
        assert pure(s,budget=SMALL).status=="validated"
    assert communications.radio_spatial_block_reason(s,"B",channel="station_broadcast")=="source_unavailable"
    assert communications.radio_spatial_block_reason(s,"A",channel="station_broadcast",require_docked=True)=="source_requires_dock"


def test_31_public_repair_and_boot_capture_local_pending_exactly_once():
    s=scene();s.ship.systems["comms"].health=.5
    rec.request_recovery(s)
    p=next(iter(s.world.recovery_plans.values()))
    op=next(iter(s.world.radio_opportunities.values()))
    assert retry_radio_opportunities(s)==[] and op.status=="pending" and not p.captured
    assert s.world.mobility_failsafe_count==0
    script=["power off security","drone deploy D1 BRG-01"]
    for command in script:public_command(s,command)
    for _ in range(6):
        if s.ship.systems["comms"].health>=Balance.SYSTEM_HEALTH_DAMAGED:break
        public_command(s,"drone repair D1 comms");script.append("drone repair D1 comms")
    assert s.ship.systems["comms"].health>=Balance.SYSTEM_HEALTH_DAMAGED
    assert op.status=="pending"
    for command in ("power on comms","boot radiod"):
        public_command(s,command);script.append(command)
    assert op.status=="received" and p.captured==(0,) and s.world.mobility_failsafe_count==1
    before=deepcopy((s.os.fs,s.world.mobility_failsafe_count,s.events.next_event_seq))
    assert retry_radio_opportunities(s)==[]
    assert before==(s.os.fs,s.world.mobility_failsafe_count,s.events.next_event_seq)
    print("PUBLIC FIRST RECEPTION REPAIR:"," -> ".join(script),"; one capture")


def test_32_conditional_search_retries_at_new_location_and_survives_load():
    for locale in (Locale.EN,Locale.ES):
        s=scene([("A","ship",(1000.,1000.,1000.)),("REMOTE","relay",(1010.,1000.,1000.)),
                 ("T","ship",(1040.,1000.,1000.))],known=("A","REMOTE"))
        s.os.locale=locale;s.world.known_links={"A":{"REMOTE"}}
        s.world.dead_nodes["T"]=DeadNodeState(dead_since_t=0)
        rec.request_recovery(s,"deadnode:T","T")
        first=s.world.recovery_searches["deadnode:T"]["cursor"]
        assert s.world.recovery_searches["deadnode:T"]["status"]=="conditional"
        assert s.world.dead_nodes["T"].attempts==0 and s.world.dead_nodes["T"].last_action_t==0
        with TemporaryDirectory() as tmp:
            slot=Path(tmp)/"slot.dat"
            save_load.save_single_slot(s,slot);s=save_load.load_single_slot(slot).state
            assert not s.world.recovery_plans and not s.world.radio_opportunities
            rec.request_recovery(s,"deadnode:T","T")
            assert s.world.recovery_searches["deadnode:T"]["cursor"]>first
            at(s,"REMOTE")
            rec.request_recovery(s,"deadnode:T","T")
            assert len(s.world.recovery_plans)==len(s.world.radio_opportunities)==1
            save_load.save_single_slot(s,slot);s=save_load.load_single_slot(slot).state
            for _ in range(3):rec.request_recovery(s,"deadnode:T","T")
            assert len(s.world.recovery_plans)==len(s.world.radio_opportunities)==1
            assert s.world.dead_nodes["T"].attempts==0
            ready(s);assert len(retry_radio_opportunities(s))==1
            assert retry_radio_opportunities(s)==[] and s.world.dead_nodes["T"].attempts==1


def test_33_public_travel_changes_conditional_search_into_local_reception():
    s=scene([("A","ship",(1000.,1000.,1000.)),("REMOTE","relay",(1000.1,1000.,1000.)),
             ("T","ship",(1003.1,1000.,1000.))],known=("A","REMOTE"))
    s.world.known_links={"A":{"REMOTE"}}
    s.world.visited_nodes.add("REMOTE")
    s.world.node_pools["REMOTE"]=NodePoolState(window_open=False,node_cleaned=True,uplink_data_consumed=True)
    # Initial scene is fixed; all transitions below use public commands/ticks.
    public_command(s,"scan")
    assert s.world.recovery_searches["global"]["status"]=="conditional"
    assert not s.world.recovery_plans and not s.world.radio_opportunities
    events=E.apply_action(s,parse_command("nav REMOTE"))
    assert any(e.type==EventType.TRAVEL_STARTED for e in events),events
    E.tick(s,s.ship.arrival_t-s.clock.t+1)
    assert s.world.current_node_id=="REMOTE"
    assert len(s.world.recovery_plans)==1
    op=next(iter(s.world.radio_opportunities.values()))
    assert op.origin_node_id=="REMOTE" and op.status=="pending"
    for command in ("power off security","power on comms","boot radiod"):public_command(s,command)
    assert op.status=="received" and s.world.mobility_failsafe_count==1
    public_command(s,"cat "+op.path)
    assert "T" in s.world.known_links["REMOTE"] and retry_radio_opportunities(s)==[]
    print("PUBLIC FIRST RECEPTION FLOW: scan -> nav REMOTE -> power off security -> power on comms -> boot radiod -> cat received file; one capture")


def test_34_selector_confirmation_and_capture_share_spatial_boundary():
    s=scene([("A","ship",(1000.,1000.,1000.)),("REMOTE","relay",(1010.,1000.,1000.)),
             ("T","ship",(1040.,1000.,1000.))],known=("A","REMOTE"))
    s.world.known_links={"A":{"REMOTE"}}
    assert pure(s,"boundary","T",budget=SMALL).status=="conditional"
    # Substitute only the shared spatial policy, not navigation/delivery or a
    # range simulation. F-DEAD-01 contains no independent node-equality gate.
    with patch.object(communications,"radio_spatial_block_reason",return_value=None) as spatial:
        r=pure(s,"boundary","T",budget=SMALL)
        assert r.status=="validated" and r.proposal.access.path==("A","REMOTE")
        rec.confirm_recovery(s,r.proposal)
        ready(s);assert len(retry_radio_opportunities(s))==1
        assert spatial.call_count>=3


def test_35_remote_condition_does_not_reveal_primaries_or_emitters():
    for locale in (Locale.EN,Locale.ES):
        s=scene([("A","ship",(1000.,1000.,1000.)),("REMOTE","relay",(1010.,1000.,1000.)),
                 ("T","ship",(1040.,1000.,1000.))],known=("A","REMOTE"))
        s.os.locale=locale;s.world.known_links={"A":{"REMOTE"}}
        rec.request_recovery(s,"remote_case","T")
        assert all("REMOTE" not in line and "T ->" not in line and "LINK:" not in line for line in radio_diagnostic_lines(s))
        assert not s.world.known_intel and not s.world.intel
        s.world.narrative_snapshot["arcs"]=[{"arc_id":"protected","primary_intel":{"kind":"node","line":"NODE: T"}}]
        assert pure(s,"protected","T",budget=SMALL).status=="invalid"
        rec.request_recovery(s,"protected","T")
        assert not s.world.recovery_plans and not s.world.radio_opportunities


def test_36_load_checks_original_reception_context_without_requiring_current_coverage():
    with TemporaryDirectory() as tmp:
        slot=Path(tmp)/"slot.dat"
        s=scene();rec.confirm_recovery(s,proposal(s))
        at(s,"B")  # Legitimately prepared at A, then left with receiver off.
        save_load.save_single_slot(s,slot)
        loaded=save_load.load_single_slot(slot).state
        assert next(iter(loaded.world.radio_opportunities.values())).status=="pending"
        at(loaded,"A");ready(loaded);assert len(retry_radio_opportunities(loaded))==1
        # Recreate a pre-correction remote-first plan only as a hard save fixture.
        s=scene([("A","ship",(1000.,1000.,1000.)),("REMOTE","relay",(1010.,1000.,1000.)),
                 ("T","ship",(1040.,1000.,1000.))],known=("A","REMOTE"))
        s.world.known_links={"A":{"REMOTE"}}
        with patch.object(communications,"radio_spatial_block_reason",return_value=None):
            r=pure(s,"old_remote","T",budget=SMALL);rec.confirm_recovery(s,r.proposal)
            blob=save_load._pack_state(s)
        slot=Path(tmp)/"old-invalid.dat";slot.write_bytes(blob)
        reject(lambda:save_load.load_single_slot(slot))
        assert slot.exists() and slot.read_bytes()==blob


def main():
    for name,func in sorted(globals().copy().items()):
        if name.startswith("test_"):
            func();print("PASS",name,flush=True)
    print("STRUCTURAL RECOVERY: 36 GROUPS PASSED")


if __name__=="__main__":main()
