# Deadnode chain proposal kernel — Phase 4D-3b

Spanish version: [deadnode-chain-planner.es.md](deadnode-chain-planner.es.md).

Implemented API: `propose_deadnode_chain(state, target_id, PlanningContext())`
in [`core/deadnode_planner.py`](../../src/retorno/core/deadnode_planner.py).
This computes an immutable, unconfirmed proposal. It is not called by
`evaluate_dead_nodes`, does not fix F-DEAD-01, and changes neither live state
nor the save schema. The [navigation/recovery contract](navigation-recovery-contract.md)
remains authoritative.

## Representation and viability

Frozen dataclasses `RecoveryProposal`, `Stage`, `ProposedNode`, `Hop`, `Hint`,
`Dependency` and `PlanningContext` contain only independent values and tuples.
They describe opportunity/endpoint identities, ordered nodes and hops, exact
positions/distances, physical region, sector/archetype/slot, information sources,
roles, restrictions, preparation requirements and capability dependencies.
`origin_access_path` records the already known directed path to the selected
origin; selecting that origin does not move the ship.

The result distinguishes these separate questions:

| Field | Meaning |
| --- | --- |
| `geometry_valid` | A complete geometric witness has segments inside the inclusive 45 ly cap. |
| `physical_chain_valid` | Its endpoints exist or have supported proposed kinds and canonical procedural slots. This is not a materialization guarantee. |
| `information_status` | `verified` uses existing mechanics; `future_required` includes unimplemented reception; `unavailable` lacks an indispensable eligible source. |
| `materialization` | `existing`, `conditional` for proposed insertion, or `unavailable` for unresolved placement/type. |
| `viability` | `verified`, `conditional`, `incomplete`, or `rejected`. A verified proposal is still unconfirmed. |

`ready_with_existing_mechanics` is only a proposal assessment. It does not
publish a route or confirm a recovery. A readable, already stored valid LINK
can be assessed without inventing another signal; a new first recovery signal
always depends on future `comms`, `radiod` and progressive capture/import.

## Origins, search and information

The caller owns threshold/cooldown timing. Candidate filters retain the existing
contact/forced-hidden, clean-pool and base sensor-range semantics; they do not
silently switch detection to the ship's effective range. Active transit is not
a planning origin; a stopped waypoint is. Origins come from
`reachable_known_nodes`, refined with `reachable_from` and normal destination
knowledge so stale/reversed edges or paths through unknown nodes do not grant
an origin.

Search first attempts an existing-node chain. The second pass admits equal
straight-line subdivisions between existing endpoints. Each connector uses the
minimum geometric number of segments for the cap; there is no arbitrary stage
limit. Search ranks by new-node count, hop count, distance, and complete ordered
ids. Labels retain procedural-slot reservations, so two connectors cannot
allocate the same forecast slot. Reservations and all caches are call-local.
Every segment is checked with `is_hop_within_cap` on detached endpoint records.

Each edge needs an information mechanism. In order, it considers an existing
directed known route, legitimate stored link intel/readable uncorrupted ship
file, ordinary route solve for a known destination inside effective sensor
range, first recovery signal, and a fresh local source. These alternatives do
not mutate knowledge. Existing routes, stored intel and ordinary solving allow
a visited node to be a navigation-only stop without a retroactive file.

The first signal is captured aboard the ship, even when the hop originates at
another reachable node. A later mandatory local source requires an unvisited
node, open window and non-clean pool. Salvage data cannot reuse a completed
data source; uplink cannot reuse a consumed uplink. The channels remain separate.
Reserving a new indispensable uplink hint is an explicit future policy
dependency; the planner does not assume it may rewrite a frozen route pool.
New sources require preparation before revelation/first visit. Navigation-only
stops need no source or new file. Ordinary hardware/operator gates remain
explicit dependencies; the proposal supplies no drone, power or repair.

## Kinds and procedural context

The actual Engine data-interface gate is stricter than lore's generic channel
predicate. The kernel records this distinction:

| Kind | Possible local information mechanisms |
| --- | --- |
| `relay` | `salvage_data`, `uplink` |
| `station` | `salvage_data`, `uplink` |
| `waystation` | `uplink`; Engine rejects `SalvageData` here |
| `derelict` | `salvage_data` |
| `ship` | `salvage_data` |

New kinds come from the existing pure `_select_archetype` and
`_plan_sector_kinds` queries, using regional templates and archetype weights,
kind caps, forbidden kinds, current physical counts and deterministic slot
order. No new appearance weights, extra hub roll, or aesthetic type distribution
is introduced. Existing appropriate nodes are reused regardless of which kind
would be selected for a new slot. Unknown regional policy or no slot produces
an incomplete witness with `kind=None`, not an invented valid node type.

At seed `271828`, with `A=(0,25,1)` and `D=(100,25,1)`, slots in
`S+003_+002_+000` / `S+006_+002_+000` admit a `relay` / `station` chain with
three approximately 33.33 ly hops. A 70 ly destination needs one intermediary;
40 and exactly 45 ly need none. Other fixtures with the same seed select
`ship` and `derelict`. At `y=1`, the corresponding 100 ly subdivision sectors
have no slots: the kernel reports incompleteness rather than changing worldgen.

## Boundaries and pending decisions

Proposed equal-spacing coordinates are not promised to be worldgen's sampled
coordinates. A forecast kind/slot establishes a supported context, not permission
to override generation. Every new node therefore records unresolved coordinate
insertion, atomic/idempotent registration, pool preparation and either lazy-slot
reservation or late-sector topology. An unexecuted initial guardrail is another
explicit context dependency. No sector is generated or rebuilt, no budget is
spent, and no physical link or known route is added.

Proposed ids use a stable digest of seed, opportunity context and node context;
local deterministic collision resolution never allocates a game id. This does
not make future confirmation idempotent. Confirmation must revalidate the
snapshot, reserve slots and identities, prepare sources atomically, then commit
and deliver progressively. Attempts/cooldowns, active-plan persistence,
communications and reception queues are outside this phase.

Protection reuses `_locked_primary_targets` for NODE/LINK primaries. Both final
targets and intermediaries are excluded. Unresolved locked primary formats
fail closed with `primary_protection_query_incomplete`; the kernel introduces
no new progression system. A forced-hidden narrative host is not automatically
protected. Natural scan and manual solving remain unchanged.

The search is complete only within its connector/slot family, not over arbitrary
coordinates, region detours or every possible procedural allocation. An exhausted
search returns `incomplete`, not a claim that the universe has no solution.

## Verification

[`deadnode_chain_planner_smoke.py`](../../tests/deadnode_chain_planner_smoke.py)
covers direct/cap/70/100 ly, 35+35+30 ly reuse, mixed chains, directed alternative
origins, stale edges, diverse canonical kinds and capability rejection, consumed
receivers, navigation-only visited stops, readable intel, NODE/LINK protection,
unsupported protection formats, lazy/late contexts, collisions, twelve-hop
chains, stopped waypoints and negative results. Every planning fixture compares
the entire serialized game state and global RNG before/after repeated calls.
Reordered containers and three temporary save/load cycles reproduce proposals.
No production writer, node registrar or world generator is invoked.
