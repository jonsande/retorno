"""4D-3d: forty contextual cases, synthetic states and temporary saves only."""
from __future__ import annotations

from dataclasses import replace
import copy
import json
import math
import os
from pathlib import Path
import pickle
import random
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from retorno.config.balance import Balance
from retorno.core import lore
from retorno.core.actions import Travel, TravelAbort
from retorno.core.deadnode_planner import PlanningContext, Viability, propose_deadnode_chain
from retorno.core.deadnode_opportunities import (
    EstimateStatus, OpportunityBudget, OpportunityStatus, _OpportunityContext,
    compare_deadnode_opportunities, compare_opportunities, evaluate_deadnode_opportunity,
)
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.os import AccessLevel, FSNode, FSNodeType
from retorno.model.world import SectorGenState, add_known_link, sector_id_for_pos

if __package__:
    from tests.deadnode_chain_planner_smoke import _add, _node, _pool, _state
else:
    from deadnode_chain_planner_smoke import _add, _node, _pool, _state


NO_NEW = PlanningContext(allow_new_nodes=False)


def _target(state, nid, x, y=25, *, known=True, visited=False):
    state.world.space.nodes[nid] = _node(nid, x, y)
    state.world.node_pools[nid] = _pool()
    if known:
        state.world.known_contacts.add(nid)
        state.world.known_nodes.add(nid)
    else:
        state.world.forced_hidden_nodes.add(nid)
    if visited:
        state.world.visited_nodes.add(nid)


def _checked(state, targets=("D",), context=NO_NEW, budget=OpportunityBudget()):
    before = pickle.dumps(state)
    rng = random.getstate()
    result = compare_deadnode_opportunities(state, targets, context, budget)
    assert pickle.dumps(state) == before and random.getstate() == rng
    assert result == compare_deadnode_opportunities(state, reversed(tuple(targets)), context, budget)
    assert pickle.dumps(state) == before
    for e in result.evaluations:
        if e.access_valid:
            assert e.access_path[0] == state.world.current_node_id
            assert e.access_path[-1] == e.origin_id
            assert e.total_hops == e.access_hops + e.chain_hops
            assert math.isclose(e.total_distance_ly, e.access_distance_ly + e.chain_distance_ly)
        if e.status != OpportunityStatus.UNUSABLE:
            assert all(0 < h.distance_ly <= 45 for h in e.proposal.hops)
        assert e.costs.economic_feasibility == EstimateStatus.UNKNOWN
        assert e.costs.future_repair_scrap.value is None
    return result


def _evaluation(state):
    before = pickle.dumps(state)
    result = evaluate_deadnode_opportunity(state, propose_deadnode_chain(state, "D", NO_NEW))
    assert pickle.dumps(state) == before
    return result


def _backtrack():
    state = _state(40)
    previous = "A"
    for i in range(1, 21):
        nid = f"OLD{i:02d}"
        _target(state, nid, -30*i, visited=True)
        add_known_link(state.world, previous, nid)
        previous = nid
    state.world.space.nodes["D"].x_ly = -630
    _target(state, "NEAR", 0, 65)
    return state


def _preferred_targets(selection):
    return {e.proposal.target_id for e in selection.evaluations if e.evaluation_id in selection.preferred_ids}


def _diamond():
    state = _state(90)
    _target(state, "B", 10)
    _target(state, "FAR", 20, 55)
    _target(state, "O", 50)
    for a,b in (("A","B"),("B","O"),("A","FAR"),("FAR","O")):
        add_known_link(state.world,a,b)
    return state


def test_01_origin_at_current_node():
    e = _evaluation(_state(40))
    assert e.origin_id == "A" and e.access_path == ("A",)
    assert e.access_distance_ly == e.access_hops == 0
    assert e.total_distance_ly == 40 and e.total_hops == 1


def test_02_multiple_known_access_hops():
    state = _backtrack()
    e = _evaluation(state)
    assert e.access_hops == 20 and e.access_distance_ly == 600
    assert e.chain_distance_ly == 30 and e.total_distance_ly == 630
    assert e.total_hops == 21


def test_03_close_origin_wrong_direction():
    state = _state(70)
    _target(state, "B", 30)
    add_known_link(state.world,"B","A")
    result = _checked(state)
    assert all(e.origin_id != "B" for e in result.evaluations)


def test_04_different_access_hops_preserved():
    state = _diamond()
    ctx = _OpportunityContext(state, NO_NEW, OpportunityBudget())
    assert ctx.access_maps["hops"]["B"].hops == 1
    assert ctx.access_maps["hops"]["O"].hops == 2


def test_05_equal_hops_different_distances():
    ctx = _OpportunityContext(_diamond(), NO_NEW, OpportunityBudget())
    path = ctx.access_maps["distance"]["O"]
    assert path.path == ("A","B","O") and path.distance_ly == 50
    assert ctx.access_maps["hops"]["O"].path == path.path
    # Legacy BFS chooses the lexically earlier, longer equal-hop branch.
    state = _state(90)
    for nid,x,y in (("A_LONG",20,55),("Z_SHORT",10,25),("O",50,25)):
        _target(state,nid,x,y)
    for a,b in (("A","A_LONG"),("A_LONG","O"),("A","Z_SHORT"),("Z_SHORT","O")):
        add_known_link(state.world,a,b)
    ctx = _OpportunityContext(state,NO_NEW,OpportunityBudget())
    assert ctx.session.origin_paths["O"] == ("A","A_LONG","O")
    assert ctx.access_maps["distance"]["O"].path == ("A","Z_SHORT","O")


def test_06_short_chain_long_backtrack_counted():
    state = _backtrack()
    e = _evaluation(state)
    assert e.euclidean_to_target_ly == 630
    assert e.chain_distance_ly < e.access_distance_ly
    assert e.costs.nominal_transit_s.value == 630 / state.ship.effective_cruise_speed() * Balance.YEAR_S


def test_07_longer_chain_nearer_origin():
    s = _backtrack()
    result = _checked(s,("D","NEAR"))
    assert _preferred_targets(result) == {"NEAR"}
    near = next(e for e in result.evaluations if e.proposal.target_id == "NEAR")
    assert near.chain_distance_ly == 40 and near.access_hops == 0


def test_08_no_free_repositioning():
    state = _backtrack()
    e = _evaluation(state)
    assert e.access_path[0] == e.current_node_id == "A"
    assert e.total_distance_ly > e.chain_distance_ly
    assert state.ship.current_node_id == "A" and not state.ship.in_transit


def test_09_near_unidentified_opportunity():
    state = _state(40)
    _target(state,"NEW",0,65,known=False)
    result = _checked(state,("NEW",))
    e = result.evaluations[0]
    assert "unidentified_stage" in e.frontier_signals
    assert not next(t for t in e.territory if t.node_id == "NEW").contact_detected


def test_10_near_visited_region_allowed():
    state = _state(40)
    state.world.visited_nodes.add("D")
    e = _evaluation(state)
    assert e.status == OpportunityStatus.CONDITIONAL
    assert next(t for t in e.territory if t.node_id == "D").region_has_visited_node


def test_11_far_old_region_not_forbidden_by_threshold():
    result = _checked(_backtrack())
    assert result.preferred_ids
    assert any(e.total_distance_ly >= 630 for e in result.evaluations if e.total_distance_ly)


def test_12_generated_is_not_visited_or_known_sector():
    state = _state(40)
    sid = sector_id_for_pos(40,25,1)
    state.world.generated_sectors.add(sid)
    e = _evaluation(state)
    t = next(t for t in e.territory if t.node_id == "D")
    assert t.sector_generated and not t.visited and not t.sector_intel_known
    assert t.sensor_coverage == "not_recorded"


def test_13_visited_not_completed():
    state = _state(40);state.world.visited_nodes.add("D")
    t = next(t for t in _evaluation(state).territory if t.node_id == "D")
    assert t.visited and t.completed is False


def test_14_completed_remains_completed():
    state = _state(40);state.world.visited_nodes.add("D")
    p = propose_deadnode_chain(state,"D",NO_NEW)
    state.world.node_pools["D"].node_cleaned = True
    e = evaluate_deadnode_opportunity(state,p)
    assert e.status == OpportunityStatus.UNUSABLE
    assert next(t for t in e.territory if t.node_id == "D").completed is True
    assert state.world.node_pools["D"].node_cleaned


def test_15_sensor_coverage_remains_unknown():
    state = _state(40)
    e = _evaluation(state)
    assert all(t.sensor_coverage == "not_recorded" for t in e.territory)
    assert "sensor_coverage_not_recorded" in e.reasons
    assert not hasattr(state.world,"sensor_coverage")


def test_16_new_in_generated_sector_stays_conditional():
    state = _state()
    p = propose_deadnode_chain(state,"D")
    for n in p.new_nodes:
        state.world.generated_sectors.add(n.sector_id)
        state.world.sector_states[n.sector_id] = SectorGenState(
            sector_id=n.sector_id,region=n.region,archetype=n.archetype,internal_links_built=True)
    result = _checked(state,context=PlanningContext())
    assert any("generated_sector_insertion_policy" in e.pending_dependencies for e in result.evaluations)
    assert all(e.status != OpportunityStatus.VERIFIED_MECHANICS for e in result.evaluations)
    # A formerly free procedural slot may be consumed by later physical state.
    fresh = _state()
    proposal = propose_deadnode_chain(fresh,"D")
    first = proposal.new_nodes[0]
    from retorno.runtime.data_loader import load_worldgen_archetypes
    cap = load_worldgen_archetypes()[first.archetype]["node_count_max"]
    for i in range(cap): _target(fresh,f"FILL{i}",30.1+i*.1)
    assert evaluate_deadnode_opportunity(fresh,proposal).status == OpportunityStatus.UNUSABLE
    fresh = _state(40)
    proposal = propose_deadnode_chain(fresh,"D",NO_NEW)
    inconsistent = replace(proposal, hops=(replace(proposal.hops[0],from_id="OTHER"),))
    assert evaluate_deadnode_opportunity(fresh,inconsistent).status == OpportunityStatus.UNUSABLE


def test_17_canonical_travel_time_and_power():
    state = _state(40);state.ship.cruise_speed_ly_per_year = 2
    e = _evaluation(state)
    trial = copy.deepcopy(state)
    add_known_link(trial.world,"A","D")
    Engine().apply_action(trial,Travel(node_id="D"))
    assert e.costs.nominal_transit_s.value == trial.ship.arrival_t-state.clock.t
    engine = Engine()
    assert e.costs.steady_cruise_load_kwh.value == engine._compute_load_kw(trial)*e.costs.nominal_transit_s.value/3600
    assert e.costs.steady_cruise_generation_kwh.value == engine._compute_p_gen(trial)*e.costs.nominal_transit_s.value/3600
    assert e.costs.steady_cruise_load_kwh.status == EstimateStatus.CONDITIONAL
    assert e.costs.direct_travel_scrap.value == 0 and trial.ship.cargo_scrap == state.ship.cargo_scrap
    # Real local timing, including the canonical deterministic fine-range helper.
    local = _state(.005);local.ship.sensors_range_ly=0
    ctx = _OpportunityContext(local,NO_NEW,OpportunityBudget())
    a,b=ctx.session.nodes["A"],ctx.session.nodes["D"]
    seconds = ctx.duration(a,b)
    add_known_link(local.world,"A","D")
    Engine().apply_action(local,Travel(node_id="D"))
    assert seconds == local.ship.arrival_t-local.clock.t
    # Actual local timing can favor the longer geometric route.
    state = _state(40)
    for n,x,y in (("P",.001,25.003),("Q",.006,25),("O",.009,25)):
        _target(state,n,x,y)
    for a,b in (("A","P"),("P","O"),("A","Q"),("Q","O")):
        add_known_link(state.world,a,b)
    ctx = _OpportunityContext(state,NO_NEW,OpportunityBudget())
    short,fast=ctx.access_maps["distance"]["O"],ctx.access_maps["time"]["O"]
    assert short.distance_ly < fast.distance_ly
    assert short.nominal_transit_s > fast.nominal_transit_s


def test_18_wear_and_repair_not_predicted_as_exact():
    e = _evaluation(_state(40))
    assert "radiation_and_system_wear" in e.costs.unknown_risks
    assert e.costs.future_repair_scrap.status == EstimateStatus.UNKNOWN


def test_18a_cruise_power_uses_engine_in_normal_and_god_modes_without_mutation():
    for god_active in (False, True):
        state = _state(40)
        if god_active:
            state.os.set_debug(True)
            state.os.debug_god_enabled = True
        before, rng = pickle.dumps(state), random.getstate()
        evaluation = _evaluation(state)
        assert pickle.dumps(state) == before and random.getstate() == rng
        trial = copy.deepcopy(state)
        add_known_link(trial.world, "A", "D")
        Engine().apply_action(trial, Travel(node_id="D"))
        assert trial.ship.in_transit
        duration = evaluation.costs.nominal_transit_s.value
        assert duration is not None
        engine = Engine()
        assert evaluation.costs.steady_cruise_load_kwh.value == engine._compute_load_kw(trial) * duration / 3600
        assert evaluation.costs.steady_cruise_generation_kwh.value == engine._compute_p_gen(trial) * duration / 3600


def test_19_future_scrap_unknown_not_zero():
    e = _evaluation(_state(40))
    assert e.costs.future_salvage_scrap.value is None
    assert e.costs.future_repair_scrap.value is None


    state = _state(40)
    _target(state,"OTHER",-40)
    state.ship.cruise_speed_ly_per_year = float("nan")
    r = _checked(state,("D","OTHER"))
    assert all(e.costs.nominal_transit_s.value is None for e in r.evaluations)
    assert _preferred_targets(r) == {"D","OTHER"}
    assert any(c.reasons == ("insufficient_practical_cost_data",) for c in r.comparisons)


def test_20_cannibalization_unavailable():
    e = _evaluation(_state(40))
    assert "cannibalization_not_implemented" in e.costs.unknown_risks
    assert not any("cannibal" in d.code for d in e.dependencies)


def test_21_no_resources_or_consumptions_changed():
    state = _state(40);state.ship.cargo_scrap = 0
    result = _checked(state)
    assert result.evaluations and state.ship.cargo_scrap == 0


def test_22_physical_validity_does_not_prove_economy():
    e = _evaluation(_state(40))
    assert e.proposal.physical_chain_valid
    assert e.costs.economic_feasibility == EstimateStatus.UNKNOWN


def test_23_near_beats_disproportionate_backtrack():
    r = _checked(_backtrack(),("D","NEAR"))
    assert _preferred_targets(r) == {"NEAR"}
    assert any(c.reasons == ("lower_complete_journey_burden",) for c in r.comparisons)


def test_24_known_near_beats_new_very_far():
    state = _state(40);state.world.visited_nodes.add("D")
    _target(state,"NEW",500,known=False)
    r = _checked(state,("D","NEW"),PlanningContext())
    assert "D" in _preferred_targets(r) and "NEW" not in _preferred_targets(r)


def test_25_frontier_only_after_comparable_access():
    state = _state(40);state.world.visited_nodes.add("D")
    _target(state,"NEW",-40,known=False)
    r = _checked(state,("D","NEW"))
    assert _preferred_targets(r) == {"NEW"}
    assert any(c.reasons == ("frontier_evidence_after_equal_accessibility",) for c in r.comparisons)


def test_26_short_but_unusable_information_excluded():
    state = _state(70);_target(state,"STOP",35,visited=True)
    _target(state,"VALID",0,65)
    r = _checked(state,("D","VALID"))
    assert any(e.status == OpportunityStatus.UNUSABLE for e in r.evaluations if e.proposal.target_id == "D")
    assert _preferred_targets(r) == {"VALID"}


def test_27_longer_valid_progression_retained():
    state = _state(70);_target(state,"BAD",35,visited=True)
    _target(state,"B",20,55);_target(state,"C",50,55)
    r = _checked(state)
    assert r.preferred_ids
    assert any(e.chain_distance_ly > 70 and e.status != OpportunityStatus.UNUSABLE for e in r.evaluations)


def test_28_primary_target_protected():
    state = _state(40)
    arc={"arc_id":"LOCK","primary_intel":{"kind":"node","line":"NODE: D"}}
    with patch.object(lore,"load_arcs",return_value=[arc]):
        r = _checked(state)
    assert not r.preferred_ids
    assert all(e.status == OpportunityStatus.UNUSABLE for e in r.evaluations)


def test_29_future_reception_not_provisional():
    e = _evaluation(_state(40))
    assert {"comms","radiod"} <= set(e.pending_dependencies)
    assert e.status == OpportunityStatus.CONDITIONAL


def test_30_no_verified_solution_is_explicit():
    r = _checked(_state(40))
    assert r.preferred_ids
    assert not any(e.status == OpportunityStatus.VERIFIED_MECHANICS for e in r.evaluations)
    broken = _checked(_state(1000))
    assert not broken.preferred_ids
    assert all(e.status == OpportunityStatus.UNUSABLE for e in broken.evaluations)
    ready = _state(40)
    ready.os.fs["/logs/ready.txt"] = FSNode("/logs/ready.txt", FSNodeType.FILE, "LINK: A -> D", AccessLevel.GUEST)
    e = _evaluation(ready)
    assert e.status == OpportunityStatus.VERIFIED_MECHANICS
    assert e.costs.economic_feasibility == EstimateStatus.UNKNOWN


def test_31_ties_and_tradeoffs_preserved():
    state = _state(40);_target(state,"OTHER",-40)
    r = _checked(state,("D","OTHER"))
    assert _preferred_targets(r) == {"D","OTHER"}
    assert any(c.reasons == ("equivalent_context",) for c in r.comparisons)
    # Different genuine directed access witnesses: fewer hops vs shorter network.
    state = _state(80)
    _target(state,"P",20,50);_target(state,"O",40)
    _target(state,"S1",10);_target(state,"S2",20);_target(state,"S3",30)
    for a,b in (("A","P"),("P","O"),("A","S1"),("S1","S2"),("S2","S3"),("S3","O")):
        add_known_link(state.world,a,b)
    ctx = _OpportunityContext(state,NO_NEW,OpportunityBudget())
    paths=ctx.access_alternatives("O")
    assert len(paths)>=2
    assert min(p.hops for p in paths) < max(p.hops for p in paths)
    assert min(p.distance_ly for p in paths) < max(p.distance_ly for p in paths)
    p = propose_deadnode_chain(state,"D",NO_NEW)
    assert p.origin_id == "O"
    alternatives=[ctx.evaluate(replace(p,origin_access_path=route.path)) for route in paths]
    conflict=compare_opportunities(alternatives[0],alternatives[1])
    assert conflict.preferred_id is None and conflict.reasons == ("practical_or_dependency_tradeoff",)


def test_32_ordering_without_random_weights():
    state = _backtrack()
    r = _checked(state,("D","NEAR"))
    other=copy.deepcopy(state)
    other.world.space.nodes=dict(reversed(list(other.world.space.nodes.items())))
    other.world.known_links=dict(reversed(list(other.world.known_links.items())))
    assert _checked(other,("NEAR","D")) == r


def test_33_whole_state_unchanged_and_no_live_helpers():
    def forbidden(*args,**kwargs): raise AssertionError("Live writer called")
    with patch.object(Engine,"tick",forbidden),patch.object(Engine,"apply_action",forbidden), \
         patch.object(lore,"write_local_intel",forbidden),patch.object(lore,"register_hidden_anchored_node",forbidden), \
         patch("retorno.worldgen.generator.ensure_sector_generated",forbidden):
        _checked(_state(),context=PlanningContext())


def test_34_rng_counters_and_attempts_unchanged():
    state=_state(40);state.world.dead_nodes["D"].attempts=1;state.world.dead_nodes["D"].last_action_t=123
    _checked(state)
    assert state.meta.rng_counter==17 and state.world.dead_nodes["D"].last_action_t==123


def test_35_no_knowledge_or_route_publication():
    state=_state(40);before=pickle.dumps((state.world.known_nodes,state.world.known_links,state.world.intel))
    _checked(state)
    assert before==pickle.dumps((state.world.known_nodes,state.world.known_links,state.world.intel))


def test_36_hash_seed_determinism():
    script=("import json;from dataclasses import asdict;"
            "from tests.deadnode_opportunity_selection_smoke import _backtrack;"
            "from retorno.core.deadnode_opportunities import compare_deadnode_opportunities;"
            "from retorno.core.deadnode_planner import PlanningContext;"
            "print(json.dumps(asdict(compare_deadnode_opportunities(_backtrack(),['D','NEAR'],PlanningContext(allow_new_nodes=False))),sort_keys=True))")
    outputs=[subprocess.run([sys.executable,"-B","-c",script],cwd=Path(__file__).resolve().parents[1],
                           env=dict(os.environ,PYTHONHASHSEED=seed),capture_output=True,text=True,check=True,timeout=30).stdout
             for seed in ("11","113")]
    assert outputs[0]==outputs[1]


def test_37_save_load_selection():
    state=_backtrack();before=_checked(state,("D","NEAR"))
    with TemporaryDirectory(prefix="retorno-opportunities-") as directory:
        path=Path(directory)/"isolated.dat"
        for _ in range(3):
            save_single_slot(state,path);state=load_single_slot(path).state
            assert _checked(state,("D","NEAR"))==before


def _populated(count):
    state=_state(40)
    rng=random.Random(271828)
    for i in range(count):
        _target(state,f"POP{i:05d}",1000+rng.random()*300,1000+rng.random()*300)
    return state


def test_38_thousands_of_nodes():
    state=_populated(2000)
    r=_checked(state)
    assert r.preferred_ids and r.access_expansions==3


def test_39_multiple_targets_bounded_shared_queries():
    state=_populated(1000)
    for i in range(12): _target(state,f"C{i:02d}",0,30+i)
    with patch("retorno.core.deadnode_planner.load_worldgen_templates",wraps=__import__("retorno.runtime.data_loader",fromlist=["load_worldgen_templates"]).load_worldgen_templates) as loader:
        r=_checked(state,tuple(f"C{i:02d}" for i in range(12)))
    assert len(r.omitted_targets)==4 and not r.complete_within_sampled_family
    assert len(r.evaluations)<=8*9 and len(r.comparisons)<=4096
    assert loader.call_count==2  # one shared query context for each pure repeat
    limited=_checked(state,("D",),budget=OpportunityBudget(access_edges=1,access_expansions=1,comparisons=1))
    assert not limited.complete_within_sampled_family


def test_40_navigation_cap_and_stopped_waypoint():
    state=_state(40);_target(state,"B",8);add_known_link(state.world,"A","B",bidirectional=True)
    engine=Engine();engine.apply_action(state,Travel(node_id="B"))
    engine.tick(state,(state.ship.arrival_t-state.clock.t)/2)
    engine.apply_action(state,TravelAbort())
    waypoint=state.world.active_tmp_node_id
    # A local opportunity from the actual stopped physical waypoint.
    _target(state,"D",state.world.current_pos_ly[0],state.world.current_pos_ly[1]+40)
    r=_checked(state)
    assert r.preferred_ids
    assert all(e.current_node_id==waypoint for e in r.evaluations)
    assert all(0<h.distance_ly<=45 for e in r.evaluations for h in e.proposal.hops)


def benchmark():
    for count in (0,1000,3000):
        for targets in (1,4,8):
            state=_populated(count)
            ids=[]
            for i in range(targets):
                nid=f"C{i:02d}";_target(state,nid,0,35+i);ids.append(nid)
            times=[]
            for _ in range(3):
                start=perf_counter();r=compare_deadnode_opportunities(state,ids)
                times.append((perf_counter()-start)*1000)
            print(json.dumps({"population":len(state.world.space.nodes),"targets":targets,
                "median_ms":round(statistics.median(times),2),"max_ms":round(max(times),2),
                "evaluations":len(r.evaluations),"access_edges":r.access_edges,"comparisons":len(r.comparisons),
                "complete":r.complete_within_sampled_family}),flush=True)

    for count in (1000,3000):
        state=_state(40)
        previous="A"
        for i in range(count):
            nid=f"KNOWN{i:05d}";_target(state,nid,30*(i+1),visited=True)
            add_known_link(state.world,previous,nid);previous=nid
        for i,n in enumerate(("N1","N2","N3")): _target(state,n,0,35+i)
        times=[]
        for _ in range(3):
            start=perf_counter();r=compare_deadnode_opportunities(state,["D","N1","N2","N3"],NO_NEW)
            times.append((perf_counter()-start)*1000)
        print(json.dumps({"mode":"known_network","population":len(state.world.space.nodes),"targets":4,
            "median_ms":round(statistics.median(times),2),"max_ms":round(max(times),2),
            "evaluations":len(r.evaluations),"access_edges":r.access_edges,"comparisons":len(r.comparisons),
            "complete":r.complete_within_sampled_family}),flush=True)


if __name__=="__main__":
    if "--benchmark" in sys.argv: benchmark()
    else:
        for name,check in list(globals().items()):
            if name.startswith("test_"):
                check();print(f"PASS {name}",flush=True)
        print("DEADNODE OPPORTUNITY SELECTION SMOKE PASSED")
