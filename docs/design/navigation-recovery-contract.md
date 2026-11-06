> **4D-3e5 — current implementation (2026-11-06).** Historical selection, transactional confirmation and common-ledger reception/progression are implemented. The [production contract](../systems/structural-recovery.md) and its report supersede historical audits below: no corrective bridges, entries or gateways are fabricated. The 3b/3c/3d core remains diagnostic and cannot authorize materialization. No universal exit is guaranteed.

# Navigation and recovery design contract

## Update 4D-3e5a — 2026-11-06

`C-DATA-004` establishes provenance and limited knowledge. Public radio/recovery
queries are independent of hidden opportunities/plans, including in debug mode;
guarded `debug radio` and `debug recovery` are shared by CLI/Textual. `ship survey`
requires prior knowledge. No simulation or save changes. See the current
communications, recovery and discovery contracts and
[tests/review](../testing/knowledge-boundary-review.md). 4D-3e5b retains its separate
future physical scope; `A-COM-001` remains open.


Spanish version: [navigation-recovery-contract.es.md](navigation-recovery-contract.es.md)

## Implemented 4D-3e4b update — 2026-11-06

Physical `comms` in BRG-01, nominal 0.15 kW, initially powered off;
`radiod` service independent of sensors/data. Persistent opportunities,
legitimate local capture and subsequent reading/import are implemented, with
idempotent retries and model-derived service notices. [Technical contract](../systems/passive-communications.md)
and [tests/report](../testing/passive-communications-review.md).
Section 3 audit paragraphs describe the state **before** this correction;
this update and the technical contract take precedence where they differ.

Legacy activations requiring fabricated entry/gateway/bridge nodes are
explicitly deferred without success/cooldown commits. Existing stages use the
common ledger. F-DEAD-01 and structural selection remain e5 work. Degradation
uses deterministic LIMITED/NOMINAL/UPGRADED reception; interference, reduced
range, latency and probabilistic restarts are not implemented. There is no
galactic network or promise of a universal exit.

## 1. Status and scope

This document records developer-approved decisions for stabilization after
Phase 4. It does not replace the canonical references for
[navigation](../systems/discovery-navigation-intel.md),
[failsafes](../systems/exploration-failsafes.md),
[lore](../systems/lore-scheduler.md), or
[worldgen](../systems/world-generation.md). It specifies the design outcome
that future corrections must preserve.

The investigation used `320d06c` and the Phase 4A/4B documentation worktree.
These phases changed documentation and tests only. Later corrections are
explicitly marked complete; other proposals must not be read as implemented
behavior.

Labels used below:

- **Approved:** binding design decision for future implementation.
- **Implemented:** observed behavior that already matches the decision.
- **Divergence:** observed behavior that contradicts or does not guarantee the
  contract.
- **Technical proposal:** possible way to satisfy the contract, not yet an
  approved architecture or implementation.
- **To measure:** insufficient evidence exists to change policy or balance.

## 2. Approved contract

### 2.1 Existence, knowledge, and routes

**Approved:** these facts must remain separate:

1. a location physically exists in `space.nodes` or is a materializable
   procedural reference;
2. the player knows the location or retains a clue about it;
3. an operational route has been published.

An unverifiable narrative reference may persist as a historical clue or pending
contact, but it does not count as a route. An operational route requires valid
physical endpoints, a hop no longer than `MAX_ROUTE_HOP_LY` (45 ly), and
coherence with navigation rules. Structural validity and the ship's current
ability to travel are separate questions.

Published routes do not all need a matching `SpaceNode.links` edge: `route
solve` and intel maintain their own operational graph in `known_links`. A
procedural id also cannot be declared invalid merely because its sector has not
yet been materialized; future validation must distinguish a materializable
reference from a nonexistent id.

**Implemented:** `route solve <node_id>` can solve an undiscovered physical
node when its exact id is known, it is within sensor range and the hop cap, and
`sensord` is running. This is deliberate. The target becomes known and is
published in `known_links` without changing `SpaceNode.links`. Missing nodes
and out-of-range hops are rejected.

**Implemented in 4D-1:** F-ROUTE-01 was corrected with the shared physical-hop
criterion and operational known-graph projection. Dangling/over-cap edges no
longer connect components or count as frontier; their historical clues remain.
Producer/consumer, lazy-generation, and persistence details are in the canonical
navigation reference.

**Implemented in 4D-2 (F-NAV-01):** abort stops at the exact interpolated
position. A stopped waypoint supports normal scan and route solve; a valid
route permits real travel to a third destination without returning first.
Arrival or replacement cleans live temporary references, preserving history.
The [canonical inventory](../systems/discovery-navigation-intel.md#abort-and-temporary-node)
details lifetime, jobs, repeated aborts, and persistence.

### 2.2 Progressive recovery

**Approved:** universal connectivity is not required. Optional regions, nodes,
and documents may be inaccessible. A recovery mechanism must offer a usable
opportunity, not guarantee that the player notices, reads, or understands it.

When deadnodes declares successful recovery for a remote target, a complete
plan of navigable hops must exist. Stages are revealed progressively. Existing
physical locations are preferred when suitable. Under the 4D-3e1 clarification,
lazy materialization must refer to universe-determined preexisting sites;
recovery need alone never establishes historical existence. If no valid chain
exists, the target remains pending: no impossible route is published and no
attempt, cooldown, or other state is consumed as if a rescue had occurred.

**Approved in 4D-3c:** when the direct chain is infeasible, search regionally
coherent alternatives and detours before giving up. Prefer suitable physical
locations; do not guarantee escape or invent exceptions to procedural rules.
A longer usable journey can take precedence over a shorter unusable one.

**Approved in 4D-3d:** prefer reasonably nearby recovery opportunities using
the complete directed trip from the ship, including access to the chain origin.
Frontier evidence is secondary; nearby known regions remain legitimate and can
beat distant unknown ones. Avoid disproportionate backtracking without adding a
fixed rejection threshold. These failsafe criteria do not constrain general
worldgen, lore, arcs or singles. Scan, documents, salvage, applicable uplink and
future captured communications remain discovery channels; indiscriminate returns
to old nodes for rescans are not required. Completed sources stay completed and
no resources or successful journey are guaranteed. Sensor coverage is not
recorded well enough to authorize retroactive appearances.

**Partially implemented:** global recovery creates an entry within range,
reuses a suitable existing gateway or creates one under the cap, and prepares a
later clue in the entry pool. It neither grants the routes directly nor forces
the player to import the files.

**Divergence:** deadnodes creates its bridge near the target and publishes the
first link from the current node without validating the whole hop. It does not
construct a chain or guarantee usable topology/pool state, and it counts the
attempt when the clue is written. The audit reproduced a bridge 99.38 ly away.

**Phase 4D-3b:** the independent [proposal kernel](deadnode-chain-planner.md)
now calculates immutable, non-mutating chains with explicit information and
materialization dependencies. Production deadnodes does not call it; F-DEAD-01
remains open, including confirmation, active-plan persistence and delivery.

**Phase 4D-3c:** the pure kernel adds deterministic sampled 3D detours,
technical search budgets and explicit per-node materialization checks. Budget
exhaustion reports incomplete search, never universal impossibility. New nodes
in generated/explored sectors remain conditional on an approved appearance and
insertion policy; no such policy or production activation is introduced here.
See the kernel design for the domain, measurements and future atomic write set.

**Phase 4D-3d:** the pure contextual API compares complete journeys and retains
practical conflicts as alternatives. Nominal travel time and steady-profile
energy are conditional; future repair/salvage costs and economic feasibility
remain unknown. Generated/visited sectors still need an approved insertion and
appearance policy. This assessment neither activates recovery nor changes the
save schema, detector, resources, reception or UI; F-DEAD-01 remains open.

This contract does not change thresholds, probabilities, or balance limits.
Those require a separate evaluation.

### 2.2.1 Procedural preexistence and structural eligibility — 4D-3e1

**Approved:** distinguish a universe-determined site, its physical node, player
knowledge and an operational route. Negative scans do not prove absence;
observation reliability and persistent history belong to 4D-3e2. Recovery must
not accept/reject candidates by scrap, energy, damage, repairs, fuel availability
or survival. Economic estimates may remain independent advisory tools. Prioritize
complete directed access from the ship and widen regional search progressively,
without a permanent distance cutoff or treating exhausted budgets as absence.
No rescue or universal connectivity is guaranteed.

**Implemented safely in part:** the [preexistence catalog](procedural-preexistence.md)
returns physical evidence and explicitly conditional canonical samples with stable
sample keys. It certifies **no latent site**: guardrails, quota occupancy, Z
outflow and id allocation prevent the stronger guarantee. Pure queries change no
world, resources, knowledge, RNG or counters. Current 4D-3d capability/dependency
ranking differs from the approved structural contract and remains unchanged.
Worldgen redesign/density decisions, planner integration and atomic materialization
are pending; the evidence and alternatives are documented in the catalog design.

### 2.3 Visited locations

**Approved:** new mandatory recovery clues will not be added to local files or
resources at already visited nodes when doing so would force a return visit to
find them.

- A visited node may remain a reference or navigation stop.
- An existing unvisited node may serve as a recovery stage.
- An indispensable clue must be prepared before the first visit and before its
  source can be consumed.
- `visited_nodes`, `window_open`, and `node_cleaned` express different facts.
- Pools will not be reopened and optional content will not be altered to force
  the chain.
- Repetitive backtracking should be avoided without prohibiting every return.

**Implemented:** the scheduler closes windows on visit, and the repaired
fixtures use known but unvisited synthetic receivers; they do not reopen a
visited pool.

**Pending:** the future chain planner must filter receivers and prepare each
stage atomically before exposing it.

### 2.4 Reception, capture, and reading

**Approved:** the first recovery clue is a new ship signal or communication,
not a retroactive file at an old station. It counts as received only when the
appropriate physical and operational capabilities exist. If they are missing,
it remains pending and retryable without loss or duplication.

The implementation must explicitly distinguish:

1. **pending:** the opportunity exists but has not been received;
2. **captured/received:** the ship stored it under valid conditions;
3. **read/imported:** the player opened it and any valid intel was incorporated
   into operational state.

There is no universal `datad` dependency. Each channel must use the capabilities
appropriate to its architecture. Later clues are found by exploring each new
stage, and every indispensable clue must lead to a navigable possibility rather
than merely mention an out-of-range destination.

**Implemented in 4D-3e4b within the limits above:** `captured_signal` and
`station_broadcast` require an operational physical `comms` system and an
active `radiod` service, in addition to emitter-specific conditions. A
broadcast may be received upon entering coverage without docking when its
physical emitter model allows it; this does not advance lore pieces whose
current trigger is `dock`. `ship_os_mail` distinguishes internal operating-
system messages from external mail or communications. `uplink_trace` keeps the
current uplink and `datad` gates without imposing `comms` on every uplink.
`salvage_data` does not depend on `radiod`. Reception and later reading remain
separate operations.

### 2.5 Narrative protection

**Approved:** automatic recovery must not reveal protected primary targets too
early. Two deliberate exceptions remain: natural discovery by `scan` and
manual exact-id resolution through `route solve`, under their normal
requirements.

A protected primary target is not the same thing as a procedural node created
as a mandatory content receiver. Future implementation must identify that
difference without activating arcs under `data/arcs/templates/` or changing the
five active singles.

**Divergence:** deadnodes and global recovery do not currently apply a shared
narrative-protection barrier. No active arc exists with which to measure the
runtime impact, but the code path is present.

### 2.6 Persistence

**Approved for pre-alpha:** backward save compatibility across old versions is
not required. Existing saves are private test artifacts and may be discarded;
unnecessary historical migrations will not be developed. The current version
must still preserve internal integrity, applicable determinism, and save/load
coverage. An incompatible save must be rejected explicitly, never loaded
silently as valid or deleted automatically. This policy must be reviewed before
a public alpha or beta.

Within one version, invalid routes must not remain operational or count as
frontiers. A reference to an ungenerated procedural sector is not invalid merely
because it has not been materialized. Filesystem data, intel, routes, pools,
lore, recovery, and deadnode state are serialized; future tests must establish
consistency and idempotence only where the current version performs
normalization.

### 2.7 The `comms` system and `radiod` service

**Implemented in 4D-3e4b:** an independent physical system is added, named
`comms`. Its player-visible names are **Communications System** in English and
**Sistema de comunicaciones** in Spanish. Passive reception consumes
relatively less power than exploration sensors: a provisional nominal 0.15 kW
subject to balance review, and its model will support future services without redesigning the system.

`radiod` depends directly on `comms`, not on `sensors`, `sensord`, `data_core`,
or `datad`. Its visible names are **Radio Communications Service** and
**Servicio de comunicaciones por radio**. It handles radio reception and
capture; `radiod` and `sensord` can run independently. This decision does not
authorize active transmission, a transponder, or combat mechanics.

A degraded `comms` may retain limited capability—for example reduced range,
interference, intermittent reception, or `radiod` instability—but exact
probabilities, consumption, and automatic restarts remain balance questions. A
temporary inability to receive must not consume an opportunity as received.

### 2.8 Recovery coherence, not survival

**Approved:** failsafes guarantee the coherence of opportunities they create;
they do not guarantee survival, universal connectivity, or the ability to
repair the ship. An irreversible block caused by player decisions can be
legitimate and end in game over. Recovery will not grant free drones, scrap,
energy, or repairs.

**Verified implemented facts:** active repair requires an existing deployed
drone, minimum battery, a valid co-located target, and reserved scrap before the
job. Drone-to-drone repair cannot target the operator itself. `repair
<system_id> --selftest` requires the `selftest_repair` unlock provided by
`selftest_rig` and also consumes scrap. `drone deploy! <drone_id>
<sector_id|node_id>` bypasses some bay/distribution blocks and is allowed in a
critical state, but still requires a docked drone with minimum integrity and a
valid destination; it also uses failure/glitch risk. It creates no resources
and does not guarantee that later repair is possible.

## 3. Historical dependency audit before e4b

In the current implementation, `write_local_intel` directly writes a `guest`
file, constructs an event, and advances the sequence. It does not validate
sensors, power, services, transit, or hibernation. Those requirements depend on
the caller. “The file was created” and “the ship could receive it” are therefore
the same technical commit today, although the approved contract requires them
to be separate.

| Channel | Current activation | Current reception | Reading/import | If a system is unavailable | Missing for reliable deferred delivery |
| --- | --- | --- | --- | --- | --- |
| `captured_signal` | Global recovery for triggers that do not select mail/broadcast/uplink; lore push on `dock`, `uplink`, or `salvage_data`; deadnodes outside `dock`. | The writer does not check a receiver. Global recovery reaches it only after `is_exploration_capable`; lore and deadnodes do not apply that channel gate. | `cat` on `/logs/signals/...`; because it is under `/logs`, recognized intel is auto-imported. `intel import` also works. The file is `guest`; reading requires neither `datad` nor sensors. | Global recovery does not activate without nominal Core OS, limited sensors with `sensord`, valid power, and a ship outside transit/hibernation, so a later trigger can retry. Lore/deadnodes may write and consume state while the equivalent receiver is off. | Persistent pending record with a stable id, future `comms`+`radiod` gate, commit only after capture, and retry deduplication. |
| `ship_os_mail` | Global recovery at hibernation end; lore push on `dock`, `uplink`, or `salvage_data`. | `write_local_intel`/`deliver_ship_mail` register mail without a communication gate. Global recovery has passed `is_exploration_capable`; lore depends only on its calling trigger. | `mail read` delegates to `render_cat`, so it reads and auto-imports intel from `/mail`. `cat` and `intel import` have equivalent intel effects. There is no universal `datad` dependency. | Global recovery is not generated while the ship lacks capability; lore may mark delivery and create mail without checking sensors/receiver. | Separate internal mail from external communications, pending/received state, and idempotent retries; assign gates only after classifying the source. |
| `station_broadcast` | Lore and deadnodes on `dock`; the second global-recovery step while at the entry. | The writer does not validate a receiver. `_deliver_gateway_broadcast_if_needed` also runs before `is_exploration_capable` and during arrival evaluation; it does not require a new dock. It sets `dock_hint_delivered`. | `cat` on `/logs/broadcasts/...` auto-imports; `intel import` also works. Access is `guest`. | The gateway broadcast can be written and marked even when global capability is blocked. Lore/deadnode broadcasts inherit dock conditions, not a receiver-specific gate. | Apply `comms`+`radiod` and coverage, keep pending until reception, and do not advance lore triggers that require dock. |
| `uplink_trace` | Only global recovery requested from an uplink after the no-new-route threshold. | Uplink requires docking at a hub, valid power, `data_core >= LIMITED`, and active `datad`; recovery then also requires nominal Core OS, sensors/`sensord`, and no transit/hibernation. The writer does not revalidate them. | `cat` on `/logs/nav/uplink_trace_...` auto-imports; `intel import` also works. Reading an already stored file does not require `datad`. | If uplink fails, recovery is not called. If exploration capability fails, it does not activate and a later trigger may retry; there is no explicit pending-attempt queue. | Persist the opportunity before reception, record the exact satisfied requirements, and deduplicate retries across save/load. |

### 3.1 Systems and states involved

`is_exploration_capable` requires: enabled feature flag; no transit or
hibernation; no `terminal_lock` or brownout; power quality above the blocking
threshold; a physical current node; `core_os >= NOMINAL`; `sensors >= LIMITED`;
and an installed, running `sensord` service.

Uplink adds its own contract: no transit/brownout, valid power, `data_core >=
LIMITED`, no incompatible shed, installed and running `datad`, ship docked at
the current node, and a relay/station/waystation node. This justifies `datad`
for `uplink_trace`, not for every channel.

A shell blocked by `terminal_lock` limits the practical ability to read or
import, but writer functions do not inspect it. `cat`, `mail read`, and `intel
import` apply filesystem permissions; all four channels write `guest` files.
`mail read` calls `render_cat`, and therefore does auto-import recognized intel.

### 3.2 Persistence and duplicates

Files, mail metadata, the event sequence, and recovery/lore state are serialized
with the save. Callers commonly prevent duplicates with specific flags
(`dock_hint_delivered`, membership in `delivered`, stored hint paths), but there
is no shared pending-reception queue or cross-system idempotency key such as
`(opportunity, stage, channel)`. Deadnodes advances `attempts` and cooldown when
writing; lore channels mark the piece delivered after the trigger. Future
implementation must defer those commits when valid reception did not occur.

### 3.3 Stopped-service notices

**Approved interface requirement:** when a physical system is activated, the
game will issue one notice per transition for installed services that depend on
it, remain stopped, and can be started. The localized notice will show the id,
player-visible description, and the real public command `boot <service_name>`.
It will distinguish stopped, not installed, and blocked-by-damage/dependency
states. Relationships will be derived dynamically from `ShipSystem.service`
and `dependencies`, not duplicated lists. When an action fails for a missing or
stopped service, it should name that service and explain how to boot it when
possible.

**Current state:** `power on <system_id>` is the canonical physical command
(`system on` is compatibility syntax), while `boot <service_name>` starts
daemons. The model supports only one `ServiceState` per system, visible service
descriptions are not centralized, and `SYSTEM_POWER_RESTORED` does not list
stopped services. Block events expose reusable ids/reasons, but not every path
offers a localized `boot` instruction.

### 3.4 Observed localization infrastructure

Runtime localization uses `Locale.EN/ES`, local `{"en", "es"}` dictionaries,
paired `.en.txt`/`.es.txt` assets, fields such as `desc_en`/`desc_es`, and
English fallbacks. CLI and Textual share much of their rendering, but strings
are still assembled in several modules and there is no central catalog that can
prove global completeness.

Existing automated controls:

- `tests/manuals_style_check.py` checks EN/ES pairs and structure for diegetic
  commands, systems, concepts, alerts, and modules;
- `tests/hibernate_sequence_assets_smoke.py` checks specific EN/ES assets;
- focused tests exercise selected renderers in both locales.

There are no general checks for Markdown documentation pairs, every CLI/Textual
key or dictionary, `desc_en`/`desc_es` metadata, narrative
`content_ref_en`/`content_ref_es` references, or newly hardcoded player-visible
text in only one language. The mandatory `AGENTS.md` rule now governs the
process; automating these gaps belongs in a separate intervention, without
creating a second localization infrastructure now.

## 4. Regression coverage

### 4.1 Decisions already characterized

| Decision/behavior | Coverage |
| --- | --- |
| Scan materializes and discovers a contact | `scan_job_smoke.py` |
| Sensor-state detection factors and guaranteed recovery-entry detection | `sensor_detection_factor_smoke.py` |
| `route solve` accepts an undiscovered exact physical id within sensors/cap and does not mutate `SpaceNode.links` | `route_solve_out_of_range_origins_smoke.py` |
| Rejection above 45 ly and worldgen links under the cap | `route_hop_cap_smoke.py` |
| Frozen, single-use uplink pool | `uplink_once_per_node_smoke.py` |
| Current global-recovery chain and progressive import | `exploration_recovery_smoke.py` and `uplink_authored_and_failsafe_smoke.py` |
| Channel preference and primary unlock through valid preexisting `uplink_only` | `lore_channel_preference_and_unlock_smoke.py` |
| `uplink_only` integrity, public retry, and persistence | `uplink_only_delivery_retry_smoke.py` |
| Strict canonical `SECTOR` ids, lazy materialization, and localized non-mutating rejection | `sector_intel_validation_smoke.py` |
| Newest-first intel listing, limits, stable timestamp ties, and unchanged show/export | `intel_recent_order_smoke.py` |
| Deadnode cooldown at zero/positive timestamps, exact expiry, candidate independence, and save/load | `deadnode_cooldown_zero_smoke.py` |
| General world/job/worldgen persistence | `save_load_smoke.py` |
| Ad hoc breadcrumb with an explicit known, unvisited host | `forced_hidden_ad_hoc_smoke.py` |
| `secondary.count`, weights, and hard force on synthetic content | `lore_secondary_count_weights_hard_smoke.py` |
| Debug with zero active arcs and with a synthetic arc | `debug_lore_arcs_smoke.py` |

The synthetic lore fixtures do not activate template arcs. The weight case
forces probability 1 and interval 0 inside `try/finally`; it is not a
representation of real balance. The eleven preexisting rows passed on the Phase
4C-1 worktree on 2026-11-03; the sensor-factor row passed on the Phase 4C-2a
worktree on the same date.

### 4.2 Covered and prepared cases

The route-integrity portion of IT-01/IT-06 is covered in 4D-1; the remaining
criteria and their current coverage are:

- **IT-01/IT-06:** import or construct a dangling/over-cap LINK in the current
  version; retain the historical clue, exclude it from routes/frontiers, and
  demonstrate stable state after save/load. Include a valid, not-yet-
  materialized procedural reference. This does not require migrating a save
  from another version.
- **IT-09 — covered in 4D-2:** abort at an interpolated position, scan, solve
  and travel to C or either endpoint; clean all live references, retain history,
  repeat aborts, and round-trip all five phases with temporary saves.
- **IT-04/IT-07:** reach a remote deadnode; each clue is confirmed only if its
  hop is valid and the complete chain terminates at the target. With the
  receiver off, no chain, or a protected target, attempts/cooldown do not
  advance. The focused zero-timestamp regression now covers cooldown persistence,
  but not this route/receiver contract.
- **Protection:** a synthetic arc with a primary protected from gateway,
  deadnodes, and automatic breadcrumb; natural scan and manual route solve keep
  their approved exceptions.
- **Reception:** each channel with requirements on, off, later restored, a
  save/load between attempts, and no duplicates.

The remaining criteria are future corrections; IT-05 and route integrity are
implemented and covered without
freezing any former defect as desired behavior.

### 4.3 Items to measure

Before changing policy or balance, measure: the impact of frozen uplink pools
after lazy expansion; opportunities lost between scheduler cycles; the real
frequency of the five singles; use of `stuck` thresholds; determinism across
generation order; obsolete-route frequency in saves; and the proportion of
existing receivers/stages that the planner can reuse without creating nodes.

### 4.4 Assigned early defects

| Defect | Priority | Regression before correction | Acceptance criterion | Proposed phase |
| --- | --- | --- | --- | --- |
| F-ROUTE-01 — known-route integrity | **Fixed** | `known_routes_integrity_smoke.py`: ten groups for validation/publication, EN/ES import, components, frontier, deadnodes, lazy, travel/jobs, inert waypoint, and save/load | No phantom frontier; contacts/history retained and no invalid operational route after save/load | **4D-1 complete** |
| F-NAV-01 — stopped waypoint and cleanup | **Fixed** | `nav_abort_waypoint_cleanup_smoke.py`, seed 314159 | Normal exploration/navigation at T; targeted idempotent cleanup, history preserved, repeated aborts and save/load | **4D-2 complete** |
| `uplink_only` consumes a primary without a valid effect | **Fixed** | Synthetic malformed, missing-endpoint, over-cap, valid-new-LINK, and valid-preexisting-LINK cases | Only valid new/preexisting links set `delivered` and unlock; failures remain pending and retryable | **4C-1 complete** |
| `UPGRADED` sensors fell back to the `CRITICAL` factor | **Fixed** | `sensor_detection_factor_smoke.py`: deterministic factor/detection matrix for every `SystemState` | `UPGRADED` uses the nominal factor; other states, range, energy, and duration are unchanged | **4C-2a complete** |
| Malformed `SECTOR` materializes origin | **Fixed** | `sector_intel_validation_smoke.py`: canonical existing/lazy/wide ids and invalid formats through public imports | Localized rejection without mutation; canonical formats still materialize | **4C-2b complete** |
| `intel N` returns the oldest records | **Fixed** | `intel_recent_order_smoke.py`: empty/single/large histories, limits, timestamp ties, EN/ES, CLI/Textual, show/export, and read-only state | Shows the N newest in stable order and preserves `intel show/export` | **4C-2c complete** |
| Deadnode cooldown is skipped at `t=0` | **Fixed** | `deadnode_cooldown_zero_smoke.py`: zero/positive timestamps, immediate/pre-limit/exact-limit evaluations, independent candidates, and save/load | `attempts > 0` identifies a prior action; zero remains a valid persisted timestamp and blocked evaluations do not mutate effects | **4C-2d complete** |
| Regional `modules_pool` treated categories as ids | **Fixed** | `worldgen_modules_pool_smoke.py`: real loader, seeds 1/2, selection and disk/bulge/halo clusters, legitimate zeros, empty/unknown filters, save/load, and normal salvage | Catalog `pool` categories filter real ids; counts, candidate order, replacement, and RNG preserved; same-sequence determinism and authored/unrelated-state integrity | **4C-3 complete** |

Single frequency, uplink snapshots, `radiation_base`, generation-order
dependence, and general balance remain independent studies.

No separate `UPGRADED` detection multiplier was configured or approved. Phase
4C-2a therefore uses `SENSORS_DETECT_P_NOMINAL` (1.00) conservatively; deciding
whether an upgrade deserves a larger bonus remains balance work, not part of
the defect correction.

## 5. Later implementation plan

Each intervention requires its own change, documentation, and authorization.
The order prevents recovery or lore from inventing parallel validators again.

| Intervention | Change and supporting decision | Modules to review | Risks | Tests and save/load | Possible additional decisions |
| --- | --- | --- | --- | --- | --- |
| 0. `uplink_only` integrity — implemented | Do not consume one-shot primary content without an effect; distinguish success, failure, and retry. | `core/lore.py`, `cli/repl.py`, and delivery state. | Double unlock, duplicate retries, or accidental changes to singles. | 4C-1 matrix; current-version save/load with pending and delivered pieces. | Closed: narrative retry is separate from the one-shot route pool. |
| 1. Route and intel integrity | Separate clue/contact/operational route; exclude dangling and over-cap edges; clean waypoint references. | `model/world.py`, `core/engine.py`, `cli/repl.py`, `known_links` consumers. | Erasing historical knowledge, invalidating lazy procedural references, or changing UI. | IT-01, IT-06, IT-09, cap and route solve; invalid current state → stable sanitation → save/load. | Visible representation of an unverifiable clue and protocol for materializing procedural ids. |
| 2. Current-save integrity | Version/reject incompatible formats explicitly and preserve invariants within a version, without pre-alpha historical migrations. | `io/save_load.py`, model/versioning, shared validators. | Accepting corruption or deleting/replacing user data. | Current save/load, backup/checksum, incompatible-version rejection, and proof the file is not deleted. | Review policy before public alpha/beta. |
| 3. Chain planner | Calculate every hop before publication; prefer existing unvisited nodes and create only what is needed. | `core/deadnodes.py`, `core/exploration_recovery.py`, worldgen/topology model, and pools. | Revealing content, late islands, using visited nodes, or changing determinism. | IT-04/07 with near/far targets, lazy sectors, no solution, and protection; save/load mid-chain. | New-node topology/pool and stage limit, without changing thresholds yet. |
| 4. Progressive persistent delivery | Persist opportunity and stage before emission; reveal one stage at a time with an idempotency key. | Recovery/deadnode/lore states, `write_local_intel`, save/load. | Duplicates, loss during upgrade, stuck clues. | Repeated retries, save before/after capture, changed trigger/channel, deduplication. | Queue schema/version and expiration policy, if any. |
| 5. `comms`, `radiod`, and reception — implemented e4b | Add localized system/service; gate signal/broadcast and do not mark delivery with an off receiver; keep `datad` uplink-specific. | System bootstrap/model, power, engine/repl, channels, and EN/ES help/manuals. | Blocking current content, circular dependency, untranslated strings, or premature balance. | `comms` states × `radiod`, physical coverage, retry/save-load/dedup, and `manuals_style_check`. | Exact degraded penalties and consumption; no active transmission. |
| 6. Narrative protection and receivers | Exclude protected primaries from automation without blocking scan/manual route solve; distinguish mandatory procedural receivers. | `core/lore.py`, recovery, deadnodes, locks/placements. | Impossible primary or accidental bypass. | Synthetic arcs by channel, protected target, forced ad hoc with/without host; persisted lock/unlock. | Canonical protection marker/query and policy when no host is eligible. |
| 7. Integration, notices, and localization | Exercise the full journey, dynamic service notices, and every observable string in EN/ES. | Tests, docs, manuals, help, and modules touched in 0–6. | A green suite missing player decisions; CLI/Textual divergence or incomplete translation. | IT-01–IT-10, full suite, EN/ES locales, links, manuals, and saves at each boundary. | Success metrics, acceptable frequency, and any later rebalancing. |

### Completed first corrective intervention: Phase 4C-1

`LoreDelivery.applied` distinguishes an attempt from an effect. A malformed,
missing-physical-endpoint, or over-cap LINK keeps its assignment, channel, and
pending state; a valid new or preexisting LINK records and unlocks exactly once.
After the route pool is consumed, another `uplink` command reevaluates only
pending `uplink_only`: it does not repeat routes, logs, rewards, recovery, or
counters. The fixture covers all five cases, repeated failure, later condition
change, save/load before and after success, and absence of duplicates. No
templates, singles, UI, or balance were changed.

### Completed strict sector-id correction: Phase 4C-2b

The former parser discarded the first character, passed the remaining three
components to `int()`, and returned `(0, 0, 0)` on every error. Consequently,
an invalid public `SECTOR:` line could generate the origin cluster and then
record the invalid literal as sector intel. The canonical parser now requires
capital `S` and three underscore-separated signed decimal components, each
equal to its `{value:+04d}` representation. Width may expand beyond four
characters. `ensure_sector_generated` validates before mutation; both public
import paths share localized rejection and continue with other valid lines.
Valid imports retain lazy generation, deterministic behavior, and hidden
sector contacts. A block containing only explicit `SECTOR:` lines is delegated
directly to that line parser, so it neither consumes RNG nor enters corrupt
recovery. Blocks mixing explicit directives with unknown narrative text retain
their prior general block semantics.

### Completed recent-intel correction: Phase 4C-2c

The list renderer formerly sorted by ascending timestamp and then sliced from
the beginning, contradicting the public “latest” contract. It now orders a
temporary indexed view by descending `(timestamp, insertion_index)` before
applying the default 20 or explicit N limit. Thus `intel`, `intel N`, and
`intel all` are newest-first, and the later-appended record wins equal timestamp
ties without using textual ids as chronology. The stored history is untouched;
`intel show` and `intel export` retain their previous lookup and export order,
and Textual inherits the same renderer.

### Completed zero-time deadnode cooldown correction: Phase 4C-2d

`last_action_t == 0` formerly meant both “no previous action” and “the previous
action happened at time zero,” so the latter bypassed the five-year cooldown.
`attempts` already records every successfully written deadnode hint and has no
other writer, so `attempts > 0` is now the prior-action indicator without a
schema change. `last_action_t` therefore remains an ordinary persisted timestamp,
including zero. The focused regression proves no mutation before expiry, a new
action exactly at the boundary, independence between candidates, unchanged
positive-time behavior, and the same semantics after save/load. It does not
resolve deadnode route validity or bridge topology (F-DEAD-01).

### Completed regional category correction: Phase 4C-3

F-WGEN-01 was reproduced before correction in both compound selection and real
generation. The inventory confirmed sufficient `pool` metadata and no used
explicit-id lists. Only procedural `_pick_modules` changed; authored state,
counts/zeros, replacement, order, and RNG calls are preserved.
`worldgen_modules_pool_smoke.py` covers seeds `1`/`2`, regional clusters,
same-sequence determinism, temporary save/load, and normal module recovery
with D1, including cargo and depletion persistence. The
[inventory and seeds](../systems/world-generation.md#regional-module-categories-f-wgen-01-fixed-in-4c-3)
are recorded in the canonical worldgen reference. No data or balance changed.

### Completed known-route integrity: Phase 4D-1

`known_routes_integrity_smoke.py` reproduced nine failing assertion groups
before production changed and now passes all ten groups with seed `271828`.
The shared criterion requires physical endpoints and the inclusive cap;
publication, components, frontiers, deadnode candidates, views, and completion
reuse it. Import retains contacts and historical records of unverifiable clues.
The read-only projection leaves persisted invalid records inert without pruning
pending references, mutating the world, or materializing on load. Lazy SECTOR
and the existing prefix helper still run before checking; no id aliases are
invented. Repeated save/load and incompatible files are covered with temporary
directories. The [canonical inventory](../systems/discovery-navigation-intel.md#operational-routes-and-historical-clues-4d-1)
details every consumer. F-NAV-01 was subsequently fixed in 4D-2; F-DEAD-01 remains pending.

## 6. Current risks and boundaries

- Since 4D-1, `is_hop_within_cap` rejects missing endpoints. Operational
  producers and consumers share the criterion without destroying history.
- `SECTOR` now has a strict canonical format and rejects malformed references.
  The broader route/node contract still cannot validate procedural references
  merely by looking them up in `space.nodes`; that remains separate work.
- Preparing clues before a visit requires a coherent operation across planner,
  pool, and persistence; writing first and completing later can expose partial
  stages.
- `comms`, `radiod`, EN/ES names, idempotent pending reception and transition
  notices are implemented in e4b. Interstellar communications, deterioration
  balance and full F-DEAD-01 structural reception remain pending.
- Since 4C-3, `modules_pool` categories filter the catalog's actual `pool` field.
  `radiation_base`, generation-order independence, single frequency, final
  uplink-pool policy, and balance remain open.

## 7. Result of this phase

The contract incorporates the Phase 4B decisions and records 4C-1 as the first
completed production correction. `uplink_only` no longer consumes pieces
without an effect and has a public retry compatible with the one-shot pool.
The matrix also records 4C-2a/b/c/d, 4C-3, and 4D-1/2 as complete; F-WGEN-01 now respects
regional categories. Other interventions, communications work, and defects
remain pending.

### Phase 4D-2: stopped waypoints and F-NAV-01

`nav_abort_waypoint_cleanup_smoke.py` fixes the contract with seed `314159`:
abort preserves interpolated coordinates and stops the ship; scan uses T as
its origin without a transit unlock; route solve and real travel support C
or the previous endpoints under normal gates and the inclusive 45 ly cap.
Cleanup is targeted and idempotent, preserving permanent routes, contacts and
historical intel. Repeated aborts replace the old waypoint without an invalid
operational origin; its pending scan/solve jobs are cancelled using the existing
finalizer. Three temporary save/load cycles cover each of five travel phases.
The [audit closure](../testing/stabilization-audit.md#phase-4d-2-stopped-waypoints-and-f-nav-01)
records the red tests, coordinates and full validation. F-DEAD-01 remains open.
