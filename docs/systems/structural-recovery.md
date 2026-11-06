# Structural recovery F-DEAD-01 — 4D-3e5

[Español](structural-recovery.es.md). Implementation for external review, 2026-11-06.
Authority: `core/structural_recovery.py`; tests: `tests/structural_recovery_smoke.py`.

## Authority and scope

Every site is certified against the game's pinned `historical-world-v1`, including
e4 authored narrative requirements. Queries neither materialize nor consume RNG,
knowledge, resources, pools, radio or scheduler state. Confirmation materializes
only certified sites with their original identities, positions, kinds, provenance
and historical edges. It uses neither corrective samples nor conditional capacity.
`_create_bridge_node`, `_sample_anchor_offset`, `_ensure_entry_node` and
`_ensure_gateway_node` were removed. Already saved legacy chains retain delivery
when their stages remain valid.

Selection addresses structure without filtering by scrap, electricity, damage,
drones, radiation, repairs or survival. Action and reception gates still apply.
Neither a universal exit nor survival along a route is guaranteed.

## Selection and examined scope

Directed access from the ship uses legitimate travel knowledge and the shared
`is_hop_within_cap` kernel. Among reachable historical emitters with spatially eligible first reception, search minimizes
complete access-plus-chain distance within the examined inventory; ties prefer
less materialization uncertainty, fewer hops and ordered IDs. Detours are examined:
Euclidean origin-to-target distance cannot replace directed access. There is no
claim of galactic optimality.

The inventory includes certified materialized sites, retained certificates,
generated/observed sectors and inverse physical manifest queries including Z
spill. A deadnode target ID is resolved even while lazy. Initial queries prioritize
relevant sectors and probes of an explicit target corridor; subsequent cursor
positions enumerate cubic 3D sector shells. Probes choose sectors, never invented
installation positions.

Default per-selection budget: 16 physical sectors (API allows 0–64), 2048 sites,
4096 expansions, 65536 edge checks and a rolling window of 1024 retained
certificates. `RecoveryBudget` rejects settings outside its explicit limits.
Known access also obeys inventory and edge limits. Manifest sessions are local.
The cursor advances even when initial priorities fill the query. There is no
fixed gameplay search radius. Retained evidence is finite: a chain that does not
fit can remain unproven, which cannot establish universal absence. Truncating
certificates without finding a chain returns `incomplete`. Changing anchor
restarts nearby scope; otherwise retry advances the cursor, including after load.

| Result | Evidence |
| --- | --- |
| `search_pending` | Evaluation requested; no result yet. |
| `validated` | Complete chain with spatially eligible first reception; not yet confirmed. |
| `conditional` | No admissible emitter or first reception outside coverage; may include a physical proposal for diagnostics only. Nothing is confirmed or invented. |
| `none_in_scope` | No complete chain found in that bounded inventory. |
| `incomplete` | Budget, retention or numerical domain prevents completing evaluation. |
| `invalid` | Invalid narrative protection, certificate, identity or preparation. |

Search is not exhaustive. Manifest closure/materialization/domain limits still
apply and are not balance rules. Each query has finite work and no mutable global
cache.

## Focused correction: first-clue accessibility

`communications.radio_spatial_block_reason` is the reusable physical coverage/context
predicate used by selection, confirmation and capture. Current node comparisons
belong to communications, not F-DEAD-01. Today it requires a physical source at
the current node, an admissible kind and docking when required. It checks neither
health, power nor comms/radiod operation; those gates remain in `radio_block_reason`
and are reevaluated on capture. An off or damaged receiver in the correct location
still allows a `receipt_pending` plan.

When spatially eligible emitters exist, only those originate confirmable proposals;
directed distance and detours still rank chains within that set. Otherwise search
may return the best examined remote chain as `conditional`, with reason
`first_reception_outside_coverage`. A `proposal` is not confirmation authority.
`request_recovery` confirms only `validated`; `confirm_recovery` checks coverage
again before copying/materializing. Conditional search creates no plan, radio
opportunity, file, route or counter, and cannot act as an active-plan frontier
blocking later selection. Its cursor can continue; a new location permits a new
selection.

Player diagnostics retain generic states, revealing neither remote source nor
destination. No internal mail, local transmitter, omniscient guidance, second
queue or new range rules are added. Future physical coverage replaces the shared
predicate; power, attenuation and latency remain 4D-3e5b. Pending-count presentation
remains 4D-3e5a. Saving/loading an uncaptured plan also validates its original
preparation context (`access.path[0]`) through the same spatial predicate. A player
can leave a legitimate source and return later with pending reception intact.
An earlier save with invalid remote-first reception is explicitly rejected without
deleting or rewriting it; no migration or invented guidance makes it valid. Tests 28–36 reproduce and cover this correction; group 5 retains
remote directed comparison with a conditional rather than confirmable result.

## Sources and progression

The first clue is a new communication from a reachable historical station, relay
or waystation within reception coverage at confirmation. A known route to a remote
emitter does not demonstrate informational access to its first clue. Their local broadcast capability is already part of the current
model; no interstellar network is simulated. Preparation creates a
`RadioOpportunity` in the common ledger. Retry preserves origin, EN/ES content
and identity. There is no second queue. An unverified emitter produces a recorded
limitation, not a fictitious message or consumed attempt.

Each clue contains one `LINK` between physical endpoints, strictly positive and
at most 45 ly. Reading/importing uses the real parser with its existing
bidirectional semantics, without changing historical edges. Preparation/capture
publishes no `known_links` and reveals no remaining chain. `NODE`, `SECTOR`,
`COORD`, scan and manual resolution keep their existing semantics.

A physical scale may reuse an already known directed operational link, without
adding clues or sources. Arriving there enables that existing leg.
Intermediate sources offer another local broadcast or a salvage document prepared
before first inspection. Closed/cleaned pools and already visited wrecks cannot
receive new documents. An exhausted hub may emit a legitimate new communication;
its pool and resources remain exhausted. Reserved narrative hosts are excluded;
content is not displaced and optional singles are not forced. Existing primary
protection fails closed for unsupported references. Natural scan and exact manual
`route solve` remain deliberate exceptions.

| Plan state | Transition |
| --- | --- |
| `prepared` | Internal transactional preparation. |
| `receipt_pending` | Source prepared; capture awaits gates and local context. |
| `active` | Actual capture or enabled salvage stage. |
| `stage_consumed` | File read/imported and the link actually published. |
| `complete` | Last clue consumed and ship arrived at final destination. |
| `invalid` | Revalidation found an invalid physical stage. |

The next stage requires reading/importing the previous clue and reaching its
source. Later documents reside at their hosts, not preloaded on the ship.
Leaving a radio source retains the pending opportunity until a legitimate return.
Capture checks `comms`, `radiod`, supply, transit, hibernation and local context.
Neither `sensord` nor `datad` enables radio.

## Activation, attempts and persistence

Global recovery checks directed routes, resolvable contacts, uplink/salvage sources,
readable recovered intel and pending plans before searching. Required repairs do
not erase a structural frontier. Existing deadnode triggers, seeded thresholds,
years/uplinks and cooldown remain unchanged. Bridge creation is never called.
There is one active plan per blockage.

The first actually captured message increments deadnode `attempts` once and sets
`last_action_t`; global capture increments the recovery counter/generation.
Time zero is a valid timestamp. Searching, preparing, exhausting a budget,
blocked reception and failed confirmation consume neither delivery nor cooldown.
Later stages do not increment attempts. Resolving a contact may remove its legacy
tracker; plan and ledger retain the history.

Proposals carry scope and structural fingerprint. Confirmation revalidates all
stages, directed access, sources, protection and identities on a disposable copy.
It uses one bounded joint materialization query and prepares sources before
publishing the write set. Failure discards the copy. Publication preserves node
and pool references held by running commands. It performs no scheduler rolls and
consumes neither files nor resources. Reconfirmation reuses the plan.

Versioned plans, current stage, captured/read stages, sources, ledger, search
certificates/cursor and the pinned universe persist. Save/load validates manifest
and plans; incompatible versions are rejected without deleting the file. No
complex migration of old universes is implemented. Empty additive defaults admit
older schema 3 saves that were already compatible.

## Relationship to the earlier core and limitations

`propose_deadnode_chain`, `evaluate_deadnode_opportunity` and
`compare_deadnode_opportunities` remain pure geometry/capacity/economy diagnostics.
Their proposed nodes are not physical authority. The production adapter reuses
`AccessRoute`, intel-source reading, delivery capabilities, primary policy and
navigation kernels, separating structural Dijkstra from those APIs' economic
filters.

Search runs synchronously with finite budgets under the existing engine lock;
there are no new workers or panels. Time/memory measurements are in the
[report](../testing/structural-recovery-review.md). Budgets can stop search before
a long chain is demonstrated, and the retained window is not exhaustive search.
Emitter, sources, connectable sites, numerical domain or travel resources may be
unavailable. These limitations are acknowledged, never repaired by inventing
history.
