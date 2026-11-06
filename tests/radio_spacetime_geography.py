"""Reproducible read-only geography samples used for provisional radio balance.

Run with PYTHONPATH=src using the project interpreter; optional JSON output path.
Sites count physical inventory, including co-located authored sites. Positive
nearest distances exclude co-location; no density or generation knobs change.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
from statistics import median
import sys

from retorno.bootstrap import create_initial_state_prologue
from retorno.config.balance import Balance
from retorno.model.world import region_for_pos
from retorno.worldgen import manifest
from retorno.worldgen.generator import universe_definition


def samples():
    rows=[]
    for seed in (1,8,701,271828):
        state=create_initial_state_prologue(seed=seed)
        definition=universe_definition(state)
        for name,anchor in (('start-disk',(0,0,0)),('bulge',(-25000,0,0)),('halo',(20000,0,0))):
            session=manifest.new_session(definition)
            sectors=['S'+'_'.join(f'{a+b:+04d}' for a,b in zip(anchor,offset))
                for offset in itertools.product(range(-1,2),repeat=3)]
            sites=manifest._physical_inventory(session,sectors).sites
            positions=[s.position_ly for s in sites]
            nearest=[min(distances) for a in positions if (distances:=[math.dist(a,b) for b in positions if math.dist(a,b)>0])]
            edges=[edge.distance_ly for sid in sectors for edge in session.sector(sid).internal_edges if edge.distance_ly>0]
            origin=tuple(a*10.0 for a in anchor)
            hubs=[s for s in sites if s.kind in {'station','relay','waystation'}]
            distances=sorted(math.dist(origin,s.position_ly) for s in hubs)
            rows.append(dict(seed=seed,sample=name,region=region_for_pos(*origin),sectors=len(sectors),sites=len(sites),
                sites_per_sector=len(sites)/len(sectors),
                nearest_min=min(nearest) if nearest else None,nearest_median=median(nearest) if nearest else None,
                nearest_max=max(nearest) if nearest else None,
                edge_median=median(edges) if edges else None,hubs=len(hubs),nearest_hubs_ly=distances[:5],
                hubs_in_geometric_radius={str(r):sum(d<=r for d in distances) for r in (.5,2.5,6,20)},
                sensors_range_ly=Balance.SENSORS_RANGE_LY))
    return rows


def main():
    output=json.dumps(samples(),indent=2)+'\n'
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(output)
    print(output,end='')


if __name__=='__main__':main()
