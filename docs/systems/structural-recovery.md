> **Pending investigation (2026-11-07).** [Exploration continuity and deadlocks](../design/exploration-softlock-research.md): the objective of avoiding unintended structural deadlocks in every viable game is not proven. F-DEAD-01 level 2 is deferred; this file remains the current implementation contract.

> **B2 update.** [Historical radio](historical-radio.md) supplies certified procedural emissions through the same resolver, selector and ledger. Existing first-stage, open-ended continuous, coverage, payload and protection requirements remain. Later stages can reuse prior procedural receipts. Selection has an additional bounded radio-host budget; no transmitter repair is implemented.

> **4D-3e5c-B1 — historical archive sources.** F-DEAD-01 can inspect a fixed [v1 procedural archive](historical-information.md) before pool preparation, with exact file/payload evidence and no materialization, injection or disclosure. Per-search information host queries have an explicit budget. Legacy source/plan provenance and the first declared radio-emission requirement remain unchanged.

# Structural recovery F-DEAD-01 — 4D-3e5

## Presentation and development — 4D-3e5a

Internal selection is not ship knowledge (`C-DATA-004`). `status` and `diag comms`
do not inspect `recovery_searches` or `recovery_plans` or show generic states
derived from them, even in debug mode. Preparing a chain before first capture
reveals nothing. Legitimate capture, received files, reading and intel retain
existing progression.

`debug on` enables `debug recovery` in CLI and Textual: stored searches,
result/reason, retained candidate certificates, sectors, expansions/edges,
cursor and anchor; plans with state, stage, access, sites and source mechanisms,
captured/consumed stages and version. Default technical budgets are shown as
current configuration, not historical measurements. It neither invents a rejected
candidate history nor reruns selection to reconstruct it: only already retained
reasons and evidence are available. `debug radio` relates plans to deliveries and
current blocking reasons. `debug off` blocks both queries again. Queries add no
logging or simulation mutations. The e5a C-DATA-004 boundary remains as 4D-3e5b
extends range and propagation; the new physical metadata does persist.
Test: `tests/knowledge_boundary_smoke.py`.


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

## First-clue coverage — 4D-3e5b

`radio_spatial_block_reason` and `radio_temporal_block_reason` are shared selection,
confirmation and capture boundaries. New local and remote plans need a
certified transmitter, specific emission, enough power/sensitivity and an arrived
wave. Local compatibility only preserves previously persisted legacy opportunities
and authorized narrative interactions.
A known route to its host or newly prepared message is insufficient.

Every new plan starts only with `navigation_link_to` declared before blockage detection,
with fixed content for that LINK. Open-ended continuous emission is required,
allowing later capture after repair/power activation. Historical activity,
corrective relays and stations are not manufactured. Recovery declaration evaluation is
bounded to 4096 emissions; exhaustion is not absence.

Selection retains directed access, detours, budgets, widening, protected primaries
and reservations. Only spatially/temporally eligible first sources can confirm;
otherwise the result remains conditional without a plan, opportunity, file,
route or consumed attempt. Current useful sensitivity determines coverage;
unavailable equipment uses NOMINAL reference without resource/survival filters.
Receiver off can legitimately leave receipt_pending.

Proposals persist first_emission_id, first_reception_sensitivity and
stage_sources: the identity and payload fingerprint of every informative stage. Confirmation
rechecks current arrival/coverage before chain materialization. The sole ledger
uses radio:<emission_id>, optionally binding an independent pending opportunity
without duplication. Received emissions cannot produce another capture. Saving
validates original position/context (access.path[0]), sensitivity and preparation
time without requiring current health/location; capture revalidates current state.
New plans use historical-recovery-v2 and reject missing source evidence.
Compatible v1 saves preserve already prepared opportunities without fictional
transmitters. Advancing v1 cannot create an unprepared radio stage; that continuation
becomes invalid so alternatives can be evaluated. Invalid remote saves fail without
rewriting. Tests 28–36, radio_spacetime and recovery_provenance exercise this.

status/diag comms still disclose no internal data. debug recovery shows emission,
coverage/time parameters and blocking reason; debug radio reads declarations and
ledger without mutation. [Physical contract](radio-spacetime.md).

## Sources and progression

The first clue comes from a reachable historical station, relay or waystation
within coverage at confirmation, through a previously declared local or remote
notice whose wave has arrived. Presence at the host proves no activity, and a
known route alone proves no reception.
No interstellar network is simulated. Preparation creates a
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
Intermediate sources need a declared emission for the exact LINK or an existing
recoverable physical archive containing that clue. Selection reads existing pools
and installed authored archives. In historical-information-v1 it can also query
the fixed pre-existing procedural archive before lazy pool preparation; legacy
saves retain their existing-only source rule. The query never creates or adapts
a document to a blockage. File reference/fingerprint persist without injection
or reopening pools. Up to 128 distinct historical information hosts are queried
per selection by default; exhaustion produces `incomplete`.
Closed/cleaned/already inspected pools gain no new clues. Previously reserved
source files retain legitimate reading on arrival. Exhausted hubs can only supply
their declared emissions; installation kind implies no activity. Resources remain
exhausted. Reserved narrative hosts are excluded;
content is not displaced and optional singles are not forced. Existing primary
protection fails closed for unsupported references. Natural scan and exact manual
`route solve` remain deliberate exceptions.

| Plan state | Transition |
| --- | --- |
| `prepared` | Internal transactional preparation. |
| `receipt_pending` | Source prepared; capture awaits gates, coverage and legitimate timing. |
| `active` | Actual capture or enabled salvage stage. |
| `stage_consumed` | File read/imported and the link actually published. |
| `complete` | Last clue consumed and ship arrived at final destination. |
| `invalid` | Revalidation found an invalid physical stage. |

The next stage requires reading/importing the previous clue and reaching its
source. Later documents reside at their hosts, not preloaded on the ship.
Leaving coverage retains the pending opportunity until availability is legitimate again for its emission mode.
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

A legitimately invalidated plan can also be saved and loaded: it retains its
proposal, stage and earlier receipts/imports and stays outside `ACTIVE`. The engine
records `invalidation` with a reason and progress fingerprint; `source_contract`
binds the confirmed proposal, version, time and attempt. Merely changing `status`
to `invalid` does not validate a plan. Physical certificates, protection, source
structure, contract integrity and ledger/progress correspondence remain mandatory.
An unprepared radio continuation may lack only its current opportunity; earlier
opportunities remain required. Archival validation of invalidated plans does not
require future sources to remain available. Active plans retain full validation;
complete plans require every stage to be consumed. These are additive schema-3
fields: older slots obtain the fingerprint on deserialization and pass the normal
validators; v1/v2 meanings do not change and no legacy sources are created.

If a later v2 stage's emission was already received through passive listening,
`_radio_stage` reuses that canonical receipt with exact provenance and content.
It neither recaptures nor increments attempts/cooldowns: unread messages still
require reading/import; an already imported LINK consumes the stage when it is
reached. Invalidated plans do not block legitimate new searches for the same
blockage. Tests: `tests/recovery_invalidation_smoke.py` and case 12 in
`tests/recovery_provenance_smoke.py`.

## Relationship to the earlier core and limitations

`propose_deadnode_chain`, `evaluate_deadnode_opportunity` and
`compare_deadnode_opportunities` remain pure geometry/capacity/economy diagnostics.
Their proposed nodes are not physical authority. Without enough declared emissions or existing archives, search remains
conditional without confirmation, attempts or cooldown. No historical procedural
transmission catalogue is added. Its possible need is a later design decision
that may be considered during e5c editorial review.

The production adapter reuses
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
