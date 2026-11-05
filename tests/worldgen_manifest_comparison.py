"""Reproducible bounded 4D-3e1b comparison; no real saves or runtime wiring.

Run with --output docs/testing/manifest-prototype-measurements.json to retain
the measured artifact. Fixtures, graph metrics and ownership tracking are test
infrastructure, not another productive generator.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
import statistics
import sys
from time import perf_counter
import tracemalloc
from unittest.mock import patch

from retorno.model.world import sector_id_for_pos
from retorno.worldgen import generator as gen
from retorno.worldgen.manifest_prototype import define_manifest, query_manifest, ALGORITHM_VERSION
if __package__:
    from tests.worldgen_preexistence_characterization_smoke import _state
else:
    from worldgen_preexistence_characterization_smoke import _state


SEEDS = tuple(range(8)) + (29, 271828)
ORIGIN = "S+000_+000_+000"
PATCHES = {
    name: tuple(f"S{base_x+x:+04d}_{base_y+y:+04d}_{z:+04d}"
                for z in (0,1) for x in range(8) for y in range(4))
    for name,base_x,base_y in (("disk",20,20),("bulge",-25004,-2),("halo",15123,-1))
}
PATCHES["initial"] = (ORIGIN,) + tuple(s for s in sorted(gen._neighbor_sector_ids_2d(ORIGIN)) if s != ORIGIN)


def _components(nodes, edges):
    adjacency = {n:set() for n in nodes}
    for a,b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    sizes = []
    component_of = {}
    for start in sorted(nodes):
        if start in component_of:
            continue
        pending = [start]
        component = {start}
        component_of[start] = len(sizes)
        for node in pending:
            for other in sorted(adjacency[node]):
                if other not in component:
                    component.add(other)
                    component_of[other] = len(sizes)
                    pending.append(other)
        sizes.append(len(component))
    echo = next((n for n,v in nodes.items() if v["raw_id"] == "ECHO_7"),None)
    return {"components":len(sizes), "singleton_components":sizes.count(1),
            "largest_component":max(sizes,default=0),
            "echo_component_nodes":sizes[component_of[echo]] if echo is not None else 0,
            "nodes_without_any_link":sum(not v for v in adjacency.values())}


def _metrics(nodes, edges, archetypes, focus):
    focus = set(focus)
    owned = {nid:v for nid,v in nodes.items() if v["source"] in focus}
    physical = {nid:v for nid,v in nodes.items() if v["physical"] in focus}
    counts = Counter(v["source"] for v in owned.values())
    occupied = Counter(v["physical"] for v in physical.values())
    induced = {(a,b) for a,b in edges if a in owned and b in owned}
    internal = sum(edges[a,b] == "internal" for a,b in induced)
    sector_adjacency = {sid:set() for sid in focus}
    for a,b in induced:
        left,right=owned[a]["source"],owned[b]["source"]
        if left != right:
            sector_adjacency[left].add(right)
            sector_adjacency[right].add(left)
    outliers = [v for v in owned.values() if v['source']!=v['physical']]
    return {
        "sectors":len(focus), "nodes":len(owned),
        "generation_count_histogram":dict(sorted(Counter(counts.get(s,0) for s in focus).items())),
        "physical_count_histogram":dict(sorted(Counter(occupied.get(s,0) for s in focus).items())),
        "empty_generation_sectors":sum(counts.get(s,0)==0 for s in focus),
        "empty_physical_sectors_observed":sum(occupied.get(s,0)==0 for s in focus),
        "observed_physical_nodes":len(physical),
        "archetypes":dict(sorted(Counter(archetypes[s] for s in focus).items())),
        "kinds":dict(sorted(Counter(v['kind'] for v in owned.values()).items())),
        "actual_regions":dict(sorted(Counter(v['region'] for v in owned.values()).items())),
        "playable_hubs":sum(v['playable'] for v in owned.values()),
        "topological_hubs":sum(v['topological'] for v in owned.values()),
        "internal_edges_induced":internal, "intersector_edges_induced":len(induced)-internal,
        "isolated_generation_sectors_induced":sum(not n for n in sector_adjacency.values()),
        "degree_one_generation_sectors_induced":sum(len(n)==1 for n in sector_adjacency.values()),
        "z_outliers":len(outliers),
        "foreign_physical_inflow_observed":sum(v['source'] not in focus for v in physical.values()),
        "outlier_destinations":dict(sorted(Counter(v['physical'] for v in outliers).items())),
        **_components(owned,induced),
    }


def _legacy(seed, ids):
    state = _state(seed)
    owners = {nid:sector_id_for_pos(n.x_ly,n.y_ly,n.z_ly) for nid,n in state.world.space.nodes.items()}
    original = gen._ensure_sector_generated_core
    original_internal = gen._build_internal_links_for_sector
    original_pair = gen._evaluate_intersector_pair
    original_link = gen._link_with_cap
    phase = [None]
    edge_kinds = {}
    def tracked(s,sid,*args,**kwargs):
        before=set(s.world.space.nodes)
        result=original(s,sid,*args,**kwargs)
        for nid in set(s.world.space.nodes)-before:
            owners[nid]=sid
        return result
    def internal(*args,**kwargs):
        phase[0]='internal'
        try:
            return original_internal(*args,**kwargs)
        finally:
            phase[0]=None
    def pair(*args,**kwargs):
        phase[0]='intersector'
        try:
            return original_pair(*args,**kwargs)
        finally:
            phase[0]=None
    def link(a,b):
        added=original_link(a,b)
        if added:
            assert phase[0] is not None
            edge_kinds[tuple(sorted((a.node_id,b.node_id)))]=phase[0]
        return added
    with patch.object(gen,'_ensure_sector_generated_core',side_effect=tracked), \
         patch.object(gen,'_build_internal_links_for_sector',side_effect=internal), \
         patch.object(gen,'_evaluate_intersector_pair',side_effect=pair), \
         patch.object(gen,'_link_with_cap',side_effect=link):
        for sid in ids:
            gen.ensure_sector_generated(state,sid)
    coverage=state.world.generated_sectors
    nodes={nid:{"source":owners[nid],"physical":sector_id_for_pos(n.x_ly,n.y_ly,n.z_ly),
                "kind":n.kind,"region":n.region,"playable":n.is_hub,"topological":n.is_topology_hub,
                "raw_id":nid,"position":(n.x_ly,n.y_ly,n.z_ly)}
           for nid,n in state.world.space.nodes.items() if owners[nid] in coverage}
    edges={key:kind for key,kind in edge_kinds.items() if key[0] in nodes and key[1] in nodes}
    archetypes={sid:s.archetype for sid,s in state.world.sector_states.items() if sid in coverage}
    return nodes,edges,archetypes,coverage


def _prototype(definition,coverage):
    result=query_manifest(definition,tuple(sorted(coverage)),max_sectors=len(coverage))
    nodes={s.identity.encoded:{"source":s.generation_sector_id,"physical":s.physical_sector_id,
            "kind":s.kind,"region":s.region,"playable":s.is_hub,"topological":s.is_topology_hub,
            "raw_id":s.identity.local_id if s.identity.namespace=='authored' else s.legacy_id_hint,
            "position":s.position_ly}
           for c in result.sectors for s in c.sites}
    edges={tuple(sorted((e.left.encoded,e.right.encoded))):e.kind for e in result.edges
           if e.left.encoded in nodes and e.right.encoded in nodes}
    return nodes,edges,{c.sector_id:c.archetype for c in result.sectors}


def benchmark():
    definition=define_manifest(271828)
    rows=[]
    for count in (1,9,64):
        ids=PATCHES['disk'][:count]
        times=[]
        for _ in range(3):
            start=perf_counter()
            result=query_manifest(definition,ids)
            times.append((perf_counter()-start)*1000)
        tracemalloc.start()
        query_manifest(definition,ids)
        _,peak=tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append({"requested_sectors":count,"evaluated_generation_sectors":len(result.evaluated_generation_sectors),
                     "median_ms":round(statistics.median(times),3),"max_ms":round(max(times),3),
                     "peak_kib":round(peak/1024,1)})
    return rows


def compare():
    rows=[]
    for seed in SEEDS:
        definition=define_manifest(seed)
        for region,ids in PATCHES.items():
            forward=_legacy(seed,ids)
            reverse=_legacy(seed,tuple(reversed(ids)))
            assert forward[3] == reverse[3]
            proposed=_prototype(definition,forward[3])
            # The comparison also asserts query-order independence of the whole
            # historical dependency closure, not just matching aggregate counts.
            check=query_manifest(definition,tuple(reversed(sorted(forward[3]))),max_sectors=len(forward[3]))
            assert asdict(check)==asdict(query_manifest(definition,tuple(sorted(forward[3])),max_sectors=len(forward[3])))
            rows.append({"seed":seed,"region_patch":region,"coverage_sectors":len(forward[3]),
                         "legacy_forward":_metrics(*forward[:3],ids),
                         "legacy_reverse":_metrics(*reverse[:3],ids),
                         "prototype":_metrics(*proposed,ids),
                         "changed_archetype_sectors_forward_reverse":sum(forward[2][sid]!=reverse[2][sid] for sid in ids),
                         "changed_archetype_sectors_forward_prototype":sum(forward[2][sid]!=proposed[2][sid] for sid in ids)})
        print(f"Measured seed {seed}",file=sys.stderr,flush=True)
    aggregate={}
    for region in PATCHES:
        models={}
        for model in ('legacy_forward','legacy_reverse','prototype'):
            values=[row[model] for row in rows if row['region_patch']==region]
            total={key:sum(v[key] for v in values) for key in values[0] if isinstance(values[0][key],int)}
            for key in ('archetypes','kinds','actual_regions','generation_count_histogram','physical_count_histogram'):
                merged=Counter()
                for v in values:merged.update(v[key])
                total[key]=dict(sorted(merged.items()))
            total['nodes_per_sector']=round(total['nodes']/total['sectors'],6)
            total['empty_generation_fraction']=round(total['empty_generation_sectors']/total['sectors'],6)
            models[model]=total
        aggregate[region]=models
    return {"algorithm_version":ALGORITHM_VERSION,"seeds":SEEDS,"patches":PATCHES,
            "python_version":sys.version.split()[0],"python_implementation":sys.implementation.name,
            "configuration_key":define_manifest(0).configuration_key,
            "method":"forward_public_requests_and_reverse_same_union; generation_provenance_tracked_at_creation; edge_kind_tracked_in_original_link_pass; induced_focus_graph; physical_counts_from_finite_generation_coverage_not_global_inventory",
            "rows":rows,"aggregate":aggregate,
            "ideal_gaussian_outflow_probability":{region:math.erfc(5/(sigma*math.sqrt(2)))
                 for region,sigma in (('disk',.3),('bulge',.8),('halo',2))},
            "benchmark":benchmark()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=compare()
    content=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.write_text(content,encoding='utf-8')
        print(f"Measurements written to {args.output}")
    else:
        print(content,end='')


if __name__=='__main__':
    main()
