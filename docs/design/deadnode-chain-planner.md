# Deadnode chain proposal kernel — Phases 4D-3b/3c

Spanish version: [deadnode-chain-planner.es.md](deadnode-chain-planner.es.md).

Implemented API: `propose_deadnode_chain(state, target_id, PlanningContext())`
in [`core/deadnode_planner.py`](../../src/retorno/core/deadnode_planner.py).
It computes an immutable, unconfirmed value. It is not called by
`evaluate_dead_nodes`; no nodes, links, files, plans or reception are activated.
**F-DEAD-01 remains open.** The [navigation/recovery contract](navigation-recovery-contract.md)
is authoritative; worldgen remains governed by [its canonical reference](../systems/world-generation.md).

## Approved decision and previous limitations

**Search regionally coherent alternatives and detours before giving up; do not
guarantee escape or create exceptions to the universe's rules.** A longer trip
through another region can be appropriate. An unrecoverable branch can also be
valid gameplay. No resources, drones, power or repairs are supplied.

4D-3b already searched arbitrary existing-node detours and mixed connectors via
existing endpoints. It did not require alignment. Its new intermediaries were
only equal subdivisions of straight connectors; failed slots were not moved.
Labels carried slot reservations, but unbounded all-pairs expansion could grow
combinatorially. `conditional` meant supported type/capacity with insertion,
pools and topology still unresolved, never permission to create a node.

Pre-change isolated probes at seed `271828` confirmed:

- A=(0,25,1), B=(20,55,1), C=(50,55,1), D=(70,25,1) already gave an existing
  detour: 36.0555 + 30 + 36.0555 ly.
- A=(0,1,1), D=(100,1,1) gave two untyped straight intermediaries and an
  incomplete witness: the corresponding straight sectors have no slots.
- Existing-only disconnected probes with 0/100/1000 background nodes took
  approximately 1.25/1.75/8.60 ms; these were sparse probes, not worst-case bounds.

## Independent representation

Frozen dataclasses `RecoveryProposal`, `Stage`, `ProposedNode`, `Hop`, `Hint`,
`Dependency`, `MaterializationCheck`, `SearchReport`, `SearchBudget` and
`PlanningContext` hold only independent values/tuples. `origin_access_path`
records the directed known trip to the selected origin; it does not move the ship.

| Field | Meaning |
| --- | --- |
| `geometry_valid` | Complete witness with every segment greater than zero and at most 45 ly. |
| `physical_chain_valid` | Existing endpoints or proposed types/canonical slots; insertion is still conditional. |
| `information_status` | `verified` mechanics, `future_required` reception, or `unavailable` indispensable source. |
| `materialization` | `existing`, `conditional`, or `unavailable`. |
| `viability` | `verified`, `conditional`, `incomplete`, or candidate `rejected`; never a confirmed rescue. |
| `checks` | Per-node evidence marked `checked`, `conditional` or `inadmissible`. |
| `search` | Deterministic work counts, sampled sectors, domain and exhausted budgets; no wall-clock data. |

`ready_with_existing_mechanics` assesses the proposal only. A readable stored
LINK can avoid new reception; a new first signal still needs future `comms`,
`radiod` and progressive capture/import. No active-plan save fields are added.

## Search domain, ordering and technical limits

Origins retain contact/forced-hidden, clean-pool and base sensor-range candidate
gates. `reachable_known_nodes` plus directed `reachable_from` and normal travel
knowledge reject reversed/stale edges and unknown intermediate origins. A stopped
waypoint is eligible; active transit is rejected. Threshold timing belongs to
the caller and is unchanged.

1. Search the physical existing-node graph first. A spatial hash with 45 ly
   cells enumerates neighboring endpoints, including off-line and other-region
   locations; information feasibility is checked before retaining an edge.
2. If needed, search an augmented graph. Retain straight subdivisions to the
   target and to the nearest 16 existing endpoints in the surrounding five-cell
   cube. Add conditional sector probes from corridors around every origin-target
   segment. The reuse preference is new-node count first, then hop count, total
   distance and the complete ordered ids. Existing-only success skips generation
   of candidate probes entirely. Mixed chains with fewer new nodes beat all-new
   chains even when longer. Equal counts use the remaining criteria.
3. Corridor probes use longitudinal spacing at most 22.5 ly and reproducible
   orthogonal bases in 3D (least-aligned axis, stable axis ties). Widths 10/20/40 ly
   sample the center and eight surrounding offsets. Streams are interleaved
   across origins and widths, with duplicate sectors removed. Sector centers are
   **geometric probes**, not approved procedural coordinates. A positive slot
   forecast permits a conditional candidate, never confirmed insertion.
4. A* uses admissible lower bounds from distance and the target's existing
   physical component, ignoring information only in the heuristic. At each edge
   the actual information mechanism and shared `is_hop_within_cap` are mandatory.
   Labels retain reserved slots; cheaper labels using a subset dominate more
   expensive labels at the same endpoint. Cycles and repeated positions are
   excluded. Hint, intel, slot and heuristic caches are call-local.

Default `SearchBudget`: 512 expansions, 1024 evaluated edges, 512 labels per
pass; 256 raw corridor samples and 256 intermediaries per straight connector.
These are configurable technical work bounds, **not a gameplay maximum of
stages**. The twelve-hop regression remains valid. Counting raw samples also
bounds overlapping corridors. A bounded reverse-component heuristic prepass
falls back to a conservative bound for large components.

An exhausted budget is exposed in `search.exhausted` and
`search_budget_exhausted`. A complete chain already found can be returned with
that warning; its selection is not proven optimal. Otherwise the result is
`incomplete`, possibly with a diagnostic geometric witness whose unavailable
sources/slots are explicit. The optional existing-only geometric diagnostic is
skipped after budget exhaustion. No result proves universal spatial impossibility.
The finite corridors, nearest-endpoint sampling and canonical first-free slot
policy also mean that even an unexhausted search is not exhaustive over space.
No arbitrary-position, all-slot-order or all-regional-detour optimality is claimed.

World indexing and readable intel parsing happen once per call. Canonical
`_plan_sector_kinds` runs on a detached sector-indexed read view with the same
seed and physical nodes, avoiding a full-world scan per forecast. It and
`_select_archetype` still own all type weights, caps, counts and randomness.
The detached view is needed because the existing pure query accepts a state,
not a sector-node collection; worldgen itself is unchanged.

## Information and narrative

Each directed hop considers: known operational route, stored link intel or
readable uncorrupted ship file, ordinary route solve to a known destination
within effective sensors, first recovery signal, then fresh local source.
These checks publish no `known_links`. Existing route/intel/solving stages can
be navigation-only; a new mandatory file is not required at every stop. A
shorter path with an unusable receiver loses to a longer feasible alternative.

The first new signal is captured aboard the ship, including when the selected
origin is another reachable node. Later mandatory sources require an unvisited
node, open window and non-clean pool. Completed salvage data and consumed
uplink remain independent, unavailable sources; no pool is reopened. Sources
must be prepared before revelation/first visit. An uplink hint reservation is
still an unresolved policy, not authority to rewrite a frozen pool. Normal
hardware, docking, drone and operator gates remain explicit dependencies.

| Kind | Actual local information capability |
| --- | --- |
| `relay` | `salvage_data`, `uplink` |
| `station` | `salvage_data`, `uplink` |
| `waystation` | `uplink`; Engine rejects `SalvageData` |
| `derelict` | `salvage_data` |
| `ship` | `salvage_data` |

No existing kind is converted. Unknown/forbidden kinds and unavailable canonical
capacity are never replaced with convenient infrastructure. Protection reuses
`_locked_primary_targets` for NODE/LINK primaries, final and intermediate.
A protected shortcut is excluded while alternatives remain searchable.
Unsupported locked formats fail closed with `primary_protection_query_incomplete`.
A `forced_hidden_nodes` host alone is not prohibited. Natural scan and manual
route solve keep their approved exceptions.

## Materialization preflight and late insertion

For each new node the value describes identity, coordinates, actual region,
sector/archetype, kind and canonical first-free slot. It checks live and local
identity collisions, exact coordinate collisions, regional eligibility, capacity
and shared proposal reservations. Id collisions use deterministic local nonces,
without allocating game ids. Pending ids in knowledge, pools, topology, sector
indexes and historical intel are also claimed. Slot eligibility is not sampled-coordinate validity.

Conditional dependencies cover `atomic_idempotent_materialization`,
`coordinate_slot_insertion_policy`, `pool_preparation_before_revelation`, and
`lazy_sector_slot_reservation` or `late_sector_topology`. Already generated/stateful
sectors add `generated_sector_insertion_policy`; a sector containing a visited
physical node adds `explored_sector_appearance_policy`. A center/position region
mismatch adds `sector_boundary_region_policy` and still requires an admitted
archetype at the actual position. Inconsistent sector metadata adds `sector_metadata_reconciliation`; it is not
silently repaired. An unexecuted initial guardrail is explicit.
Pool/source work is also described by the stage's `Hint` and its restrictions.

Current `sync_sector_state_for_node` can update existing indexes, but does not
rebuild closed internal topology; evaluated intersector pairs are not retried.
Lazy generation consumes physical counts and may change the remaining forecast.
The current anchored registrar creates live state, links and pools, can invoke
further generation, and is not idempotent; the clue writer also produces new
files/events on repetition. Neither is a transaction or called here.

Existing physical stops, directed routes and usable sources need no appearance
policy. A new proposed stop in a generated/visited sector remains conditional.
In player terms: **may a previously explored area later contain a previously
unseen recovery location, and how would the player discover that fact?** This
phase does not decide that policy. A sector center, spare capacity or an open
pool alone does not answer it.

## Future atomic confirmation — design only

A later implementation should prepare a detached transaction keyed by
opportunity id and a snapshot fingerprint. Resolve every pending insertion
policy first. Revalidate protection, origins, hops, receivers, current physical
counts and all proposed identities/coordinates/slot reservations against the
latest state. Prepare the entire chain, never just the first bridge.

The transaction's write set must include physical nodes and identities,
coordinates and slot claims, sector indexes/hubs, permitted physical links and
budgets/pair bookkeeping, initialized pools and exact source files/reservations,
active-plan identity, stage state and pending reception dependencies. Validate
that no visited/consumed source receives mandatory content and that topology
caps remain valid. Do not rebuild topology or add route knowledge implicitly.

Build and validate this write set on a detached snapshot; publish the coherent
world/plan state in one engine-owned commit boundary with no delivery visible
before it. A failed/stale preparation discards the detached result, consumes no
attempt and starts no cooldown. Repeated confirmation by the same identity must
return the same active plan, not call allocating registrars again. Durable save
publication must use the existing save boundary only after the state is coherent;
active-plan schema/version and atomic-boundary details belong to that later phase.

Receipt, capture and import remain distinct persisted stage transitions, with
idempotency keys. A pending receiver is not a successful rescue. Exactly when an
attempt/cooldown starts relative to preparation and capture still requires an
explicit integration decision; no present counters change. No part of this
transaction, communications or persistence is implemented in 4D-3c.

## Measurements and verification

Reproduce with the canonical Python:
`tests/deadnode_chain_detours_smoke.py --benchmark`. It uses seed `271828`, three
calls per cell, isolated synthetic states, excludes fixture construction, and
reports median/max milliseconds and deterministic work counts. Backgrounds of
0/300/1200/3000 physical nodes occupy a 300×300×60 ly volume away from the route;
the exhausted case instead packs them near the origin, marks their data consumed
and uses a 2000 ly target. Densities and outcomes are synthetic, not gameplay rates.

Median / maximum, ms:

| Background nodes | Existing only | Straight new | Detour | Budget exhausted |
| --- | --- | --- | --- | --- |
| 0 | 3.51 / 4.93 | 16.39 / 16.78 | 30.22 / 31.28 | 131.64 / 153.79 |
| 300 | 6.55 / 6.57 | 20.20 / 21.33 | 46.33 / 49.59 | 87.70 / 101.72 |
| 1200 | 15.81 / 16.37 | 32.83 / 39.09 | 47.67 / 48.75 | 80.20 / 89.52 |
| 3000 | 37.86 / 48.93 | 54.18 / 54.23 | 68.13 / 68.53 | 107.76 / 110.47 |

Indexing scales with the physical world and stored intel. Search work is bounded
by technical budgets, not an unlimited combination of slot histories; dense
local neighborhoods and copies still cost more. Measurements are not hard
latency guarantees. Future Textual integration **must run on an immutable snapshot
in a worker**, validate staleness before confirmation, and may tune technical
budgets/caching. No UI worker or integration is introduced here.

At seed `271828`, the valid straight 100 ly fixture retains two nodes at y=25
and three approximately 33.3333 ly hops. At y=1, the new detour proposes
(25,-5,5) and (65,-5,5): approximately 26.0192 + 40 + 35.7351 ly. Both have
canonical slots; insertion and first reception remain conditional. An existing
node at (65,1,1) reduces this to one new intermediary. The real disk/halo
boundary fixture crosses regions without changing balance or region definitions.

The original [28-group regression](../../tests/deadnode_chain_planner_smoke.py)
and [4D-3c companion](../../tests/deadnode_chain_detours_smoke.py) jointly cover
the requested matrix (numbers follow the 4D-3c request):

| Cases | Executable coverage |
| --- | --- |
| 1 | `test_direct_viable_is_retained`, original direct/45/70/100 |
| 2, 4 | `test_reference_seed_empty_straight_slots_find_offline_nodes` |
| 3 | `test_existing_detour_preferred_over_shorter_all_new` |
| 5 | `test_mixed_detour_minimizes_new_nodes` |
| 6 | `test_real_regional_boundary_with_existing_detour` |
| 7, 21 | `test_short_unusable_receiver_loses_to_longer_information_path` |
| 8 | `test_equal_alternatives_have_stable_tie_breaks` |
| 9, 18 | `test_regional_kind_restrictions_not_overridden` |
| 10 | `test_no_procedural_context_is_not_a_permission` |
| 11–15, 30–31 | `_checked`/original `_plan` compare full pickled state/global RNG, exact positive cap via `_assert_hops`; original inclusive-cap tests |
| 16, 20 | `test_navigation_only_exhausted_stop_and_direction_preserved`, original directed origins |
| 17 | Original canonical-kind and real Engine waystation capability tests |
| 19 | `test_shared_slot_reservations_and_coordinate_collision`; each proposal also asserts unique slot reservations |
| 22–23 | `test_protected_shortcut_excluded_alternative_retained`, original NODE/LINK/unsupported-primary cases |
| 24–25 | `test_sources_and_first_reception_remain_pending` |
| 26–27, 29 | `test_generated_explored_and_lazy_insertion_are_distinct` |
| 28 | `test_collision_safe_detour_identities`, original id collision and `test_pending_identity_references_are_not_reused` |
| 32–33 | `test_detour_save_load_hash_seeds_and_all_state_purity`, original ordering/save/hash tests |
| 34 | `test_budget_exhaustion_is_incomplete_not_universal_impossibility` |
| 35 | `test_populated_world_has_bounded_search_and_preserves_state`, benchmark |

Whole-state comparisons cover world, sector topology, knowledge/intel, pools,
filesystem, counters/cooldown, RNG/sequences, events, ship/resources, recovery
and time. Three temporary save/load cycles and hash-seed subprocesses preserve
the proposals. The indexed forecast is compared against the canonical full-world query in
`test_indexed_forecasts_match_the_canonical_full_world_query`. No real saves are opened. Writer/generator calls are forbidden
in dedicated tests. Manuals/help need no changes: no player command changes.

## Product decisions still required

- Whether and how the player can discover new recovery locations in previously
  generated/explored areas; which such sectors must instead be excluded.
- How conditional coordinates/slots coexist with normal lazy sampling,
  initial guardrails and cross-boundary regions without inflating density.
- How late physical links/hubs obey closed topology and intersector budgets.
- How to reserve indispensable uplink data without reopening frozen/consumed
  pools, and which source preparation operation can be confirmed atomically.
- When preparation/capture makes a rescue count for attempts/cooldown, and the
  active-plan/reception schema and invalidation/retry semantics.

The approved detour rule needs no further approval. No new type, weight,
probability, gameplay hop limit or universal survival guarantee is proposed.
