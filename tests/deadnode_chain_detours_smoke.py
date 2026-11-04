"""4D-3c companion to deadnode_chain_planner_smoke; isolated states only.

Run directly for regression, or with --benchmark for the reproducible timings.
The 35-case contract matrix is mapped in docs/design/deadnode-chain-planner.md.
"""
from __future__ import annotations

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

from retorno.core import deadnode_planner as planner, lore
from retorno.core.deadnode_planner import (
    InformationStatus, Materialization, Mechanism, PlanningContext, Role,
    SearchBudget, Viability, propose_deadnode_chain,
)
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.world import SectorGenState, add_known_link, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_worldgen_archetypes
if __package__:
    from tests.deadnode_chain_planner_smoke import _add, _assert_hops, _node, _pool, _state
else:
    from deadnode_chain_planner_smoke import _add, _assert_hops, _node, _pool, _state


def _at(state, nid, x, y, z=1.0, kind="derelict"):
    node = _node(nid, x, y, kind)
    node.z_ly = z
    node.region = region_for_pos(x, y, z)
    state.world.space.nodes[nid] = node
    state.world.node_pools[nid] = _pool()


def _detour():
    state = _state(70)
    _at(state, "B", 20, 55)
    _at(state, "C", 50, 55)
    return state


def _checked(state, context=PlanningContext()):
    before = pickle.dumps(state)
    rng = random.getstate()
    result = propose_deadnode_chain(state, "D", context)
    assert before == pickle.dumps(state)
    assert rng == random.getstate()
    assert result == propose_deadnode_chain(state, "D", context)
    assert before == pickle.dumps(state)
    if result.stages:
        _assert_hops(result)
        assert len({s.node.position_ly for s in result.stages}) == len(result.stages)
        slots = [(n.sector_id, n.slot_index) for n in result.new_nodes if n.procedural_eligible]
        assert len(slots) == len(set(slots))
    return result


def test_direct_viable_is_retained():
    p = _checked(_state())
    assert all(math.isclose(n.position_ly[0], x) and n.position_ly[1:] == (25, 1)
               for n, x in zip(p.new_nodes, (100/3, 200/3)))
    assert all(math.isclose(h.distance_ly, 100/3) for h in p.hops)
    state = _state(45)
    _add(state, "ZERO", 0)
    p = _checked(state)
    assert p.reused_nodes == ("A", "D") and p.hops[0].distance_ly == 45


def test_reference_seed_empty_straight_slots_find_offline_nodes():
    state = _state(y=1)
    query = planner._Planner(state, "PROBE", SearchBudget())
    assert not query.sector_slots("S+003_+000_+000")[2]
    assert not query.sector_slots("S+006_+000_+000")[2]
    p = _checked(state)
    assert p.physical_chain_valid and p.viability == Viability.CONDITIONAL
    assert len(p.new_nodes) == 2
    assert all(n.position_ly[1:] != (1, 1.0) for n in p.new_nodes)
    assert math.fsum(h.distance_ly for h in p.hops) > 100
    assert p.materialization == Materialization.CONDITIONAL
    assert not p.search.exhausted


def test_existing_detour_preferred_over_shorter_all_new():
    p = _checked(_detour())
    assert p.reused_nodes == ("A", "B", "C", "D")
    assert not p.new_nodes and not p.search.candidate_sectors
    assert math.fsum(h.distance_ly for h in p.hops) > 70


def test_mixed_detour_minimizes_new_nodes():
    state = _state(y=1)
    _add(state, "E", 65)
    p = _checked(state)
    assert p.reused_nodes == ("A", "E", "D")
    assert len(p.new_nodes) == 1
    assert p.new_nodes[0].position_ly[1:] != (1, 1.0)


def test_real_regional_boundary_with_existing_detour():
    state = _state(70)
    # Actual disk/halo boundary at operational x=150000, no patched balance.
    _at(state, "A", 149970, 1)
    _at(state, "D", 150040, 1)
    _at(state, "B", 149990, 31)
    _at(state, "C", 150020, 31)
    state.world.current_pos_ly = (149970, 1, 1)
    p = _checked(state)
    assert p.reused_nodes == ("A", "B", "C", "D")
    assert {s.node.region for s in p.stages} == {"disk", "halo"}


def test_short_unusable_receiver_loses_to_longer_information_path():
    for unavailable in ("visited", "consumed", "missing_pool"):
        state = _detour()
        _add(state, "SHORT", 35)
        if unavailable == "visited":
            state.world.visited_nodes.add("SHORT")
        elif unavailable == "consumed":
            state.world.node_pools["SHORT"].data_complete = True
        else:
            del state.world.node_pools["SHORT"]
        p = _checked(state)
        assert p.reused_nodes == ("A", "B", "C", "D"), unavailable
        assert p.information_status == InformationStatus.FUTURE_REQUIRED


def test_equal_alternatives_have_stable_tie_breaks():
    state = _state(70)
    _at(state, "NORTH", 35, 45)
    _at(state, "SOUTH", 35, 5)
    a = _checked(state)
    reordered = copy.deepcopy(state)
    reordered.world.space.nodes = dict(reversed(list(state.world.space.nodes.items())))
    reordered.world.node_pools = dict(reversed(list(state.world.node_pools.items())))
    assert _checked(reordered) == a
    assert a.reused_nodes == ("A", "NORTH", "D")


def test_no_procedural_context_is_not_a_permission():
    with patch.object(planner, "load_worldgen_templates", return_value={}):
        p = _checked(_state(y=1))
    assert p.viability == Viability.INCOMPLETE
    assert not p.physical_chain_valid and p.geometry_valid
    assert p.materialization == Materialization.UNAVAILABLE
    assert all(n.kind is None for n in p.new_nodes)
    assert p.search.candidate_sectors
    assert all(any(c.status == "inadmissible" for c in n.checks) for n in p.new_nodes)


def test_regional_kind_restrictions_not_overridden():
    state = _state(y=1)
    # Synthetic catalog isolates an inadmissible context; it is not a new rule.
    catalogs = copy.deepcopy(load_worldgen_archetypes())
    for cfg in catalogs.values():
        cfg["forbidden_kinds"] = ["relay", "station", "waystation", "ship", "derelict"]
    with patch.object(planner, "load_worldgen_archetypes", return_value=catalogs):
        p = _checked(state)
    assert not p.physical_chain_valid
    assert not any(n.kind for n in p.new_nodes)


def test_shared_slot_reservations_and_coordinate_collision():
    state = _state()
    query = planner._Planner(state, "SHARED", SearchBudget())
    sid = "S+003_+002_+000"
    slots = query.sector_slots(sid)[2]
    assert len(slots) >= 2
    used = ()
    ids = set()
    occupied = set(query.occupied)
    for i in range(len(slots)):
        pos = (31+i*.1, 25.0, 1.0)
        node = query.new_node(pos, ("A", "D"), i, used, occupied, ids)
        assert node.procedural_eligible and node.kind == slots[i]
        used += ((sid, node.slot_index),)
        ids.add(node.node_id)
        occupied.add(pos)
    full = query.new_node((32, 25, 1), ("A", "D"), 10, used, occupied, ids)
    assert full.materialization == Materialization.UNAVAILABLE
    collision = query.new_node((31, 25, 1), ("A", "D"), 11, (), occupied, ids)
    assert not collision.procedural_eligible
    assert "position_already_occupied" in collision.selection_reasons


def test_navigation_only_exhausted_stop_and_direction_preserved():
    state = _detour()
    state.world.visited_nodes.add("B")
    state.world.node_pools["B"].window_open = False
    state.world.node_pools["B"].data_complete = True
    state.world.known_nodes.add("C")
    add_known_link(state.world, "B", "C")
    p = _checked(state, PlanningContext(allow_new_nodes=False))
    assert p.reused_nodes == ("A", "B", "C", "D")
    assert p.stages[1].role == Role.NAVIGATION
    assert p.hops[1].hint.mechanism == Mechanism.KNOWN_ROUTE
    state.world.known_links = {"C": {"B"}}
    p = _checked(state, PlanningContext(allow_new_nodes=False))
    assert p.information_status == InformationStatus.UNAVAILABLE


def test_protected_shortcut_excluded_alternative_retained():
    state = _detour()
    _add(state, "PRIMARY", 35)
    arc = {"arc_id": "LOCK", "primary_intel": {"kind": "node", "line": "NODE: PRIMARY"}}
    with patch.object(lore, "load_arcs", return_value=[arc]):
        p = _checked(state)
    assert p.reused_nodes == ("A", "B", "C", "D")
    assert "PRIMARY" not in p.reused_nodes
    state.world.forced_hidden_nodes.add("B")
    state.world.lore_placements.piece_to_node["narrative_host"] = "B"
    with patch.object(lore, "load_arcs", return_value=[arc]):
        assert _checked(state) == p


def test_sources_and_first_reception_remain_pending():
    p = _checked(_detour())
    first = p.hops[0].hint
    assert first.mechanism == Mechanism.RECOVERY_SIGNAL
    assert first.source_id != "A" and first.source_ref == "A"
    assert {d.code for d in first.dependencies if not d.implemented} >= {"comms", "radiod"}
    assert "no_retroactive_file_at_origin" in first.restrictions
    assert all(h.hint.requires_preparation for h in p.hops)
    assert all("prepare_before_first_visit" in h.hint.restrictions for h in p.hops[1:])
    assert p.viability == Viability.CONDITIONAL


def test_generated_explored_and_lazy_insertion_are_distinct():
    state = _state()
    initial = _checked(state)
    for n in initial.new_nodes:
        checks = {c.code: c.status for c in n.checks}
        assert checks["canonical_kind_capacity"] == checks["identity_unique"] == "checked"
        assert checks["coordinate_slot_insertion_policy"] == "conditional"
        assert checks["lazy_sector_slot_reservation"] == "conditional"
    first = initial.new_nodes[0]
    state.world.generated_sectors.add(first.sector_id)
    state.world.sector_states[first.sector_id] = SectorGenState(
        sector_id=first.sector_id, region=first.region, archetype=first.archetype,
        internal_links_built=True)
    _at(state, "VISITED", 30.01, 20.01, kind="ship")
    state.world.visited_nodes.add("VISITED")
    state.world.node_pools["VISITED"].window_open = False
    p = _checked(state)
    generated = [n for n in p.new_nodes if n.sector_id == first.sector_id]
    # If the added physical node consumes the chosen slot, a different valid
    # path is allowed. Check late placement directly on the remaining slot too.
    q = planner._Planner(state, "GENERATED", SearchBudget())
    n = q.new_node((33, 25, 1), ("A", "D"), 0, (), q.occupied, set())
    assert n.procedural_eligible
    generated.append(n)
    for n in generated:
        codes = {d.code for d in n.dependencies}
        assert {"late_sector_topology", "generated_sector_insertion_policy",
                "explored_sector_appearance_policy"} <= codes
        assert n.materialization == Materialization.CONDITIONAL


def test_collision_safe_detour_identities():
    state = _state(y=1)
    p = _checked(state)
    first = p.new_nodes[0]
    _at(state, first.node_id, -500, -500)
    q = _checked(state)
    assert q.opportunity_id == p.opportunity_id
    assert all(n.node_id not in state.world.space.nodes for n in q.new_nodes)
    assert len({n.node_id for n in q.new_nodes}) == len(q.new_nodes)
    assert first.node_id not in {n.node_id for n in q.new_nodes}


def test_pending_identity_references_are_not_reused():
    state = _state(y=1)
    first = _checked(state).new_nodes[0]
    # A not-yet-physical identity in an index/pool is still claimed.
    state.world.known_contacts.add(first.node_id)
    state.world.node_pools[first.node_id] = _pool()
    p = _checked(state)
    assert first.node_id not in {n.node_id for n in p.new_nodes}
    assert first.node_id not in state.world.space.nodes


def test_indexed_forecasts_match_the_canonical_full_world_query():
    from retorno.worldgen.generator import _plan_sector_kinds
    state = _state()
    _at(state, "COUNTED", 31, 25, kind="ship")
    q = planner._Planner(state, "CANONICAL", SearchBudget())
    for sid in ("S+003_+002_+000", "S+006_+002_+000", "S+002_+000_+000"):
        region, archetype, forecast = q.sector_slots(sid)
        canonical, _ = _plan_sector_kinds(state, sid, archetype, region,
                                          q.templates[region], q.archetypes[archetype])
        assert forecast == tuple(canonical)


def test_budget_exhaustion_is_incomplete_not_universal_impossibility():
    state = _detour()
    budget = SearchBudget(expansions=1, edges=1, sector_samples=1, connector_nodes=1, labels=2)
    p = _checked(state, PlanningContext(allow_new_nodes=False, budget=budget))
    assert p.viability == Viability.INCOMPLETE
    assert p.search.exhausted
    assert "search_budget_exhausted" in p.reasons
    assert "no_chain_in_sampled_domain" in p.reasons
    # More technical work recovers a real route without changing gameplay.
    assert _checked(state).physical_chain_valid
    for args in ({"edges": 0}, {"labels": -1}, {"expansions": float("nan")}, {"edges": True}):
        try:
            SearchBudget(**args)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid technical budget accepted")


def test_detour_save_load_hash_seeds_and_all_state_purity():
    state = _state(y=1)
    state.world.dead_nodes["D"].attempts = 1
    state.world.dead_nodes["D"].last_action_t = 123
    state.world.intersector_link_pairs.add("existing_pair")
    p = _checked(state)
    reordered = copy.deepcopy(state)
    for field in ("space",):
        graph = getattr(reordered.world, field)
        graph.nodes = dict(reversed(list(graph.nodes.items())))
    reordered.os.fs = dict(reversed(list(reordered.os.fs.items())))
    assert _checked(reordered) == p
    with TemporaryDirectory(prefix="retorno-detours-") as directory:
        path = Path(directory) / "isolated.dat"
        for _ in range(3):
            save_single_slot(state, path)
            state = load_single_slot(path).state
            assert _checked(state) == p
    script = ("import json;from dataclasses import asdict;"
              "from tests.deadnode_chain_detours_smoke import _checked,_state;"
              "print(json.dumps(asdict(_checked(_state(y=1))),sort_keys=True))")
    outputs = [subprocess.run([sys.executable, "-B", "-c", script],
                             cwd=Path(__file__).resolve().parents[1],
                             env=dict(os.environ, PYTHONHASHSEED=seed),
                             capture_output=True, text=True, check=True, timeout=30).stdout
               for seed in ("7", "101")]
    assert outputs[0] == outputs[1]


def test_detour_never_calls_live_writers():
    state = _state(y=1)
    def forbidden(*args, **kwargs):
        raise AssertionError("Live mutation called")
    with patch.object(lore, "register_hidden_anchored_node", forbidden), \
         patch.object(lore, "write_local_intel", forbidden), \
         patch("retorno.worldgen.generator.ensure_sector_generated", forbidden), \
         patch("retorno.core.deadnodes.evaluate_dead_nodes", forbidden):
        assert _checked(state).physical_chain_valid


def _populate(state, count, dense=False):
    rng = random.Random(271828)
    for i in range(count):
        if dense:
            pos = (rng.uniform(0, 35), rng.uniform(1, 35), rng.uniform(1, 10))
        else:
            pos = (1000+rng.uniform(0, 300), rng.uniform(-150, 150), rng.uniform(-30, 30))
        _at(state, f"POP_{i:05d}", *pos)


def test_populated_world_has_bounded_search_and_preserves_state():
    state = _state(2000, y=1)
    _populate(state, 1200, dense=True)
    for nid in state.world.space.nodes:
        if nid != "D":
            state.world.visited_nodes.add(nid)
            state.world.node_pools[nid].data_complete = True
    budget = SearchBudget(expansions=32, edges=256, sector_samples=64, labels=512)
    p = _checked(state, PlanningContext(budget=budget))
    assert p.viability == Viability.INCOMPLETE
    assert p.search.exhausted
    assert p.search.edges <= 3*budget.edges
    assert p.search.expansions <= 3*budget.expansions
    assert len(p.search.candidate_sectors) <= budget.sector_samples


def benchmark():
    """No wall-clock assertions: measurements include pure queries, not fixtures."""
    rows = []
    for population in (0, 300, 1200, 3000):
        for mode in ("existing", "direct", "detour", "budget"):
            state = _state(2000 if mode == "budget" else 100, y=1 if mode in {"detour", "budget"} else 25)
            _populate(state, population, dense=mode == "budget")
            if mode == "existing":
                _add(state, "E1", 35)
                _add(state, "E2", 70)
            if mode == "budget":
                for nid in state.world.space.nodes:
                    if nid != "D":
                        state.world.visited_nodes.add(nid)
                        state.world.node_pools[nid].data_complete = True
            times = []
            for _ in range(3):
                t = perf_counter()
                p = propose_deadnode_chain(state, "D")
                times.append((perf_counter()-t)*1000)
            rows.append({"population": len(state.world.space.nodes), "mode": mode,
                         "median_ms": round(statistics.median(times), 2),
                         "max_ms": round(max(times), 2), "viability": p.viability.value,
                         "new": len(p.new_nodes), "expansions": p.search.expansions,
                         "edges": p.search.edges, "exhausted": p.search.exhausted})
            print(json.dumps(rows[-1]), flush=True)
    return rows


if __name__ == "__main__":
    if "--benchmark" in sys.argv:
        benchmark()
    else:
        for name, check in list(globals().items()):
            if name.startswith("test_"):
                check()
                print(f"PASS {name}", flush=True)
        print("DEADNODE CHAIN DETOURS SMOKE PASSED")
