# C2a — relative lore-placement filters

**STATUS: IMPLEMENTED in C2a, based on HEAD 0bd02fa (2026-11-07).** Runtime ownership: `src/retorno/core/lore.py`; focused verification: `tests/lore_relative_placement_integration.py`. C2b prepares AMANECER in the working-tree catalogue; [exploratory access remains under review](../testing/amanecer-productive-review.md).

## Goal and optional syntax
Support deterministic, bounded 3D Euclidean distance constraints on lore **host placement** relative to physical historical identities, including per-seed authored positions and lazy sites, without changing existing origin-based `min_dist_ly`, `max_dist_ly`, `regions_any`, candidate, channel or temporal rules:

```json
"constraints": {"max_dist_ly": 30, "anchor_distances": [{"anchor": "LIRIA", "min_ly": 0, "max_ly": 15}]}
```

Anchors are canonical IDs or unambiguous authored aliases. Bounds are finite, non-negative, inclusive, and at least one bound must be present; omitted minimum defaults to zero. Multiple anchor constraints combine by **AND**. No OR, graph-distance expressions or general constraint language in v1. This is separate from `world_requirements.relations.near`, which constrains physical entity placement rather than document hosting.

## Engineering contract
- Resolve historical anchors from the compiled, seed-locked manifest/snapshot without requiring player knowledge, materialization or visits. Reject unknown, ambiguous, unresolvable or geometry-less anchors before starting, with actionable provenance.
- Strictly reject empty lists, unknown object keys, NaN/inf, booleans, negatives, reversed bounds, and missing both bounds. Preserve behavior without the new field.
- Share eligibility across historical host search, essential validation/reservation, forced/non-forced placement, and singles. No knowledge leaks to status/map/completion. Keep bounded searches and incomplete/not_evaluated semantics. No fabrication of history.
- Preserve catalog fingerprints, save/load and locale parity.

## Optional essential-host choice

```json
"placement_rules": {"primary": {"host_selection": "seeded"}}
```

Default essential reservation uses the first sorted viable host. The opt-in seeded mode deterministically selects among the **certified viable witnesses within the inspected domain** using run seed, piece key and ordered historical identities. It does not promise uniform galactic sampling or a distinct host in every seed. Runtime selection honors the reserved host, including when another candidate is already materialized. Unavailable reservations remain pending. Unknown selection modes are rejected; this option belongs to primary rules only.

Validation runs during bootstrap for all pieces, before essential reservation, using the compiled snapshot and authored manifest geometry. Procedural anchors and the player ship are excluded. Queries use the existing finite host-search domain; relative bounds do not expand that domain. Catalogue fingerprints and saved reservations use existing persistence, without a new schema. No commands, help or diegetic manual text change because these are authoring fields.

## Focused tests
Within/outside/boundary; moving authored anchor across seeds; multiple AND; invalid configs before startup; candidate type/region/time combined; forced/singles/non-forced paths; deterministic reservation across catalogue order and save/load; multiple viable hosts can vary by seed; no leaks; C1 and narrative-world integration regressions. Do not change balance or productive catalog.
