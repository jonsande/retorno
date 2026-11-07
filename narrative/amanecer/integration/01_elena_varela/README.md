# AMANECER — Elena Varela arc: C2 integration draft

**Not installed; validated in a temporary C2a catalogue.** The JSON in `narrative/` remains editorial working material. `constraints.anchor_distances` and `placement_rules.primary.host_selection` are implemented for review. `tests/lore_relative_placement_integration.py` verifies seeds 1, 29 and 701, distinct eligible clue hosts, stable Liria positions, the LINK below 45 ly, exclusive Elena placement, public knowledge boundaries, EN/ES salvage/reading and save/load. The service fixture moves the ship to hosts; a complete playable journey from the prologue remains unverified. Do not install into production during this review.

## Approved editorial decisions
- Liria is a pre-existing abandoned, explorable authored station. Its per-seed coordinates are defined relative to HARBOR_12 and fixed for the run.
- All four original Elena Varela records remain on Liria, including her unsent private draft. They can be read out of order and do not resolve the seven missing persons.
- The first clue is a replicated pre-collapse civil navigation index from a legitimate host (HARBOR_12 or a qualifying procedural station/relay). It offers an operative LINK from HARBOR_12 to LIRIA, not evidence of historic travel or present life.
- `world_requirements` declares LIRIA once and references HARBOR_12. The host is within 15 ly of LIRIA and 30 ly of the starting location; seed-based host selection is opt-in. Four forced salvage secondary documents are hosted exclusively on LIRIA.

## Future promotion
After implementing and testing C2a, put `amanecer_elena_01.draft.json` into `data/arcs/amanecer_elena_01.json` and the ten text files in `data/lore/packs/amanecer_elena_01/`. Test in a temporary catalogue before activating the arc: multiple seeds, EN/ES, physics, acquisition, drone salvage, save/load, and absence of early disclosure. No engine or active catalogue changes are included here.

The nav clue is an operative route solution, not a certified historical physical edge. Other AMANECER arcs, VAELOR, the Tábano and the Bruma are out of scope. Canon: `narrative/amanecer/CANON.md`. Update the previous Liria-undecided entry in `LOCATIONS.md` once installation is approved.
