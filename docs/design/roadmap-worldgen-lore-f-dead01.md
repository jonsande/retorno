## 4D-3e5c-B2 — implemented for external review

[historical-radio-v1](../systems/historical-radio.md) separates original hardware, conservation, energy, emission programs and propagating waves. It reuses the manifest, B1, radio physics and reception ledger; authored declarations override whole hosts. Local lazy discovery, persistence and certified F-DEAD-01 sources are implemented. Exceptional physical repair and prolonged e6 validation remain future work. Previous B2-pending statements below describe earlier phases.

## 4D-3e5c-B1 — implemented for external review

New games use [historical-information-v1](../systems/historical-information.md),
with stable finite archives and navigation records, typed historical connections
and calculated routes, protected delivery, strict additive schema-3 validation
and whole-save legacy information rules. B0 physical capabilities remain.
Physical worldgen, scheduler policy, radio, resources and audio are unchanged.
This update supersedes the earlier e5c editorial-only scope below. Version 1.6
retains D01–D24 literally. B2 remains pending: procedural transmitters/emissions
and any exceptional reactivation require original hardware, preservation, energy,
repair capability, historical payload, actual start time, propagation and a
persisted intervention trail. No retroactive emission or repair is implemented.
Extended e6 Textual/audio play validation remains separate.

## 4D-3e5b — implemented for external review

The [physical spatial/temporal model](../systems/radio-spacetime.md) implements
A2, B, C2, D and E: three profiles, power/sensitivity, propagation at c, automatic
passive radio and validated optional transmitter data. F-DEAD-01 shares the
boundary without inventing historical emissions. Provisional parameters; no
changes to density, navigation, complete clocks or production content. e5c keeps
editorial review; e6 extended Textual/audio validation. D01–D24 remain unchanged.
[Report](../testing/radio-spacetime-review.md).


# RETORNO — Procedural preexistence, lore and F-DEAD-01 roadmap

**Version:** 1.6 — 2026-11-06. [Español](roadmap-worldgen-lore-f-dead01.es.md).
**Status:** 4D-3e5c-B1 implemented on `445217e` for external review; B2/e6 pending.

This roadmap preserves agreed design decisions and a bounded stabilization
sequence so development can return to playing RETORNO with Textual/sound, then
to new arcs, singles and content. It records product/coordination decisions;
it does not replace [canon](../canon/universo.md), coherence guidelines, technical
contracts or tested code. Report discrepancies for developer decision.

## Approved and implemented intervention v1.5 — 4D-3e5a

After F-DEAD-01 published at `343829e`, add `C-DATA-004`, the AGENTS operational
rule and “How does the ship know this?”. Remove disclosures from `status`/`diag
comms` and `ship survey`; explicit debug retains internal access. Comparative
negative EN/ES tests, CLI/Textual and acquired information preservation:
[review](../testing/knowledge-boundary-review.md).
Selector, world, ledger, RNG, persistence, audio and D01–D24 are unchanged.
**4D-3e5b** remains separate: physical range, emitter types, power, sensitivity
and simplified temporal propagation. It is not implemented in e5a.
e6, extended playable validation with Textual and sound, remains pending.

## Implemented status v1.4 — 4D-3e5

Baseline `ba705e7` (Tweaks preserved). F-DEAD-01 is implemented for external review: bounded historical selection, widening, atomic preparation and progressive radio/salvage clues. See [contract](../systems/structural-recovery.md) and [report](../testing/structural-recovery-review.md). D01–D24 remain literally unchanged. Earlier coordination sections and audits retain their historical context; e5 supersedes their references to deferred activation. e6, playable Textual/sound validation, remains pending.

## Explicit additional agreement v1.3

The developer authorizes **4D-3e4b — passive communications** before 4D-3e5.
This bounded extra intervention does not consume the defect-correction reserve
or declare F-DEAD-01 complete. It implements comms/radiod, persistent opportunities,
local capture and reading, notices, save compatibility and EN/ES tests/docs.
Authorized provisional nominal consumption is 0.15 kW. See the
[contract](../systems/passive-communications.md) and
[report](../testing/passive-communications-review.md).

D01–D24 and e5/e6 acceptance criteria remain intact. Legacy activations requiring
fabricated corrective nodes are explicitly deferred; structural recovery and
selection remain e5 work. References below to e2 being in progress and the
v1.1→v1.2 procedure retain their historical coordination context, rather than
describing today's checkout. The implementation table includes the intervention.

## 1. Starting point and verifiable status

- Previously confirmed: 4D-1 operational routes/physical cap, 4D-2 abort
  waypoints, 4D-3b pure planner, 4D-3c physical detours and 4D-3d contextual
  comparison. At the earlier review, production `core/deadnodes.py` did not use
  the new planner; inspect current code before making claims.
- 4D-3e1 advisory catalog delivered `worldgen/catalog.py`, shared sampling,
  characterization and EN/ES docs. It was approved for commit; that final SHA
  was not recorded in v1.2.
- 4D-3e1b was planned earlier; this historical roadmap did not certify its
  approval/integration. Verify implementation reports/history.
- At v1.2 approval, Codex was already executing 4D-3e2. Do not retroactively
  rewrite that order: review its actual delivery and schedule only necessary
  adaptation for additional decisions.
- Earlier worldgen had generation-order dependence in its initial guardrail,
  Z overflow/quotas, ID collisions and intersector links. The e1 catalog
  distinguished physical facts from conditional samples; verify e2's changes.
- `dd5b471` (audio), `6ae813e` (canon) and `10a092f` (e3d) are historical
  references, not an assumed current HEAD. Inspect Git state every time.
- The added v1.2 decision requires structured spatial requirements from all
  installed narrative packages as new-world inputs. Approval was an
  architectural objective, not proof that it was already implemented.

## 2. Approved decisions — product contract

| ID | Binding decision |
| --- | --- |
| **D01 — Preexisting world** | Historical stations, relays, wrecks and installations have existence/identity independent of failsafes, narrative scheduling and exploration order. Calculation/materialization may be lazy; the past cannot be fabricated retrospectively. |
| **D02 — Four layers** | Separate universe placement, materialized physical node, player knowledge/intel and published operational route. Knowing a station does not imply a usable route. |
| **D03 — Manifest** | Target a stable procedural manifest from seed, version/rules and authored base, queryable by sectors without activating thousands of objects initially. Prove the concrete form through tests. |
| **D04 — Coherent topology** | Identity, position, kind, hub rules and historical connections must not depend arbitrarily on query order. Preserve the 45 ly hop cap and physical/known graph separation. Do not impose universal connectivity. |
| **D05 — Uncertain exploration** | A negative scan does not prove absence. Degraded sensors may miss sites. Repetition/cumulative evidence may be supported without requiring endless scans. Save observation history. |
| **D06 — F-DEAD-01 scope** | Resolve structural exploration blockage: existence, topology and discoverability, rather than survival. Scrap, energy, fuel, repair, ship wear and survival prospects must not reject candidates. |
| **D07 — Progressive search** | Prioritize opportunities near the current position through complete directed paths; widen distance/search progressively when needed. No rigid distance limit may permanently discard the only legitimate exit. Budget exhaustion means incomplete search, never no exit. |
| **D08 — No guaranteed rescue** | No teleportation, free items, invented stations, impossible routes or favorable-ending guarantee. Resource defeat is valid and distinct from structural errors. |
| **D09 — Lore sources** | The scheduler may decide content, assignment and delivery timing/channel, but cannot create historical installations to host it. Placement may be dynamic; physical existence may not. |
| **D10 — Arcs and singles** | Preserve primary_intel, secondary_lore_docs, rules, force, constraints, channels, weights and single cycles where possible. Essential pieces require verifiable legitimate opportunities; optional pieces may never appear. Availability does not guarantee discovery. |
| **D11 — Completed nodes** | Never reopen node_pools, rebuild consumed files or add historical hints to exhausted stations. Prepare/reserve before the first relevant inspection. Do not require repeated backtracking to cleared places. |
| **D12 — Intel** | NODE refers to a valid site; LINK needs physical/operational validation; SECTOR provides regional information; COORD denotes coordinates, not a station. Incomplete/false intel may exist without becoming an impossible operational link. |
| **D13 — Ad hoc** | Replace corrective historical creation for forced lore/failsafes with preexisting sites or legitimate narrative channels. Future physically justified dynamic events are not prohibited but must be explicit and distinct from ancient installations. |
| **D14 — Narrative protection** | Preserve protected primaries and deliberate natural-scan/manual-solve exceptions. Internal catalog or recovery queries must not leak secrets. |
| **D15 — Diegetic delivery** | Separate preparation, reception/capture and reading/import. Finding a candidate grants no hidden intel. comms/radiod require their own real gates; absent implementation cannot justify free reception. |
| **D16 — Performance and saves** | Finite budgets, bounded queries, lazy generation, persistence and idempotence. Old prealpha saves are disposable tests, but never deleted automatically. Avoid complex historical migrations; version new-world rules. |
| **D17 — Scope** | Do not expand stabilization into exhaustive balance, station classes, new UI/audio or a full dynamic-events platform. Consult on significant design decisions. Codex does not commit or push. |
| **D18 — Authorship and meaning** | Preserve expressly designed stations, wrecks and locations for arcs/singles, authored into the physical universe before exposure. Mentioning a place is not declaring it, and declaring it is not revealing it. Replacing ad hoc must preserve that capability. |
| **D19 — Syntax compatibility** | Preserve NODE, LINK, SECTOR, COORD, intel blocks and recognized authored references where technically coherent. Do not pretend they all create stations. Verify compatibility through tests; no silent new syntax or authoring format changes. |
| **D20 — Essential stories** | Define/verify eligible sites/channels before source consumption; reserve or bind preexisting hosts without reopening pools or guaranteeing discovery. Report impossible constraints in content validation, never improvise a station during play. |
| **D21 — Lore-conditioned worldgen** | Collect binding spatial requirements from all installed arcs, singles and narrative packages before a new game. Incorporate canonical entities/relations in the manifest with procedural generation so clues lead to real, stable, coherent places. Reading, activation or sector generation must not retroactively decide existence. |
| **D22 — Structured declarations** | Do not infer physical facts from all prose. Separate explicit canonical facts, references, uncertain/misleading claims and revealed intel. Resolve IDs/aliases, kinds, location, region, proximity, routes, chronology and contradictions before play; report actionable authoring errors without runtime fabrication. |
| **D23 — Extensible authorship** | Designers add stories and physical requirements through data, without generator code per story. Reuse formats/guides where viable; any declarative schema must be compatible/versionable and reviewed before mandatory adoption. Inclusion does not reveal secrets or guarantee every document appears. |
| **D24 — Verifiable relationships** | Names alone are insufficient: declared proximity, provenance, coordinates and spatial constraints must be satisfiable under topology, physical limits and discovery rules. Distinguish historical association, possible physical route, player-known route and approximate/false clue. |

## 3. Content distribution rules

### 3.1 Worldgen and manifest

Authored locations form the explicit base, with validated identity/occupancy
precedence. New-world inputs are seed, version/rules, authored universe and
installed narrative catalog/versions with structured physical requirements.
Compile/validate before exploration; physical realization may remain lazy.
Requirements cover singular entities and declared identity, position,
proximity, region, chronology and connectivity. A mentioned ship is not
automatically an explorable wreck.

An optional document need not appear, while included canonical physical facts
remain consistent. Manifest definition cannot depend on loading, activation,
sector exploration or intel-reading order. Define stable IDs and explicit
conflict policy. Historical procedural sites depend on seed/rules/version,
not exploration order. Sector centers and e1 conditional samples are not
certified stations. Coordinate 10 ly sectors, physical regions, Z overflow,
quotas and hub connections without intuitive density changes.

### 3.2 Lore, arcs and singles

Placement may remain probabilistic under region/distance/time/kind/windows,
weights and channels. Installed canonical requirements and runtime document
selection are separate. Authors express verifiable relationships without
Python changes; validation detects unresolved references, incompatible kinds,
impossible geometry and contradictions before play.

Essential arcs need at least one legitimate channel/placement in relevant
configurations, not guaranteed discovery. Optional pieces may appear late or
remain absent. Never inject historical content into an exhausted source;
later communications require legitimate emission, channel and reception.
Keep placement, preparation/reservation and delivery separate.

### 3.3 Intel and routes

Physical existence reveals neither known_nodes nor known_links. Valid imports
may materialize preexisting sites and record provenance. Prepare indispensable
clues in usable sources or legitimate new channels without exhaustive revisits.
Materializing an existing station must not duplicate salvage/files or reopen pools.

### 3.4 Explicit authorship, reference and intel contract

There are three distinct operations:

1. Declare an authored station/wreck/installation, establishing stable identity
   and physical position before discovery. Preserve specifically named story
   sites independently of procedural luck. Audit existing formats; this
   decision alone does not approve new syntax.
2. Mention it narratively. Prose such as “Némesis disappeared” neither creates
   a site nor reveals coordinates/IDs. Preserve/test existing authored
   recognizers in explicit intel blocks.
3. Reveal operational information through recognized intel and physical
   validation. Lazy materialization is not historical creation from nothing.

Existing syntax to characterize and preserve:

```text
NODE: NEMESIS_STATION
LINK: RELAY_08 -> NEMESIS_STATION
SECTOR: S+003_+002_+000
COORD: 35.2, 12.0, 0.5
```

These illustrative IDs do not declare real content. Historically NODE could
add a reference without a physical node; the target contract resolves valid
authored/manifest references or preserves explicitly pending/erroneous clues.
LINK publication requires physical endpoints and <=45 ly, preserving incomplete
or false historical records. SECTOR supplies regional intel and legitimate lazy
generation without revealing every node. COORD may create a NAV point, never
a historical station. Audit authored ID/name/alias resolution in INTEL blocks
separately from ordinary prose; never promise unregistered name recognition.

Preserve primary/secondary definitions, placement rules, constraints, channels,
weights and force policies unless they contradict approved decisions. Story
geography is fixed before exploration even if document assignment/delivery is
late. Forced pieces reserve legitimate hosts rather than fabricate them;
optional singles need no appearance guarantee.

Before closing e4, run an end-to-end regression covering authored identity and
secret initial location; prose versus explicit intel; valid/invalid/pending and
protected NODE imports; valid/invalid LINK geometry and publication; distinct
SECTOR/COORD effects; forced arc and procedural single over existing hosts;
no retrospective stations/reopened pools; repeated save/load of geography,
knowledge/routes/progress; and compatibility with actual authoring procedures.
Update guides with real executable examples after implementation, not as if
future functions already existed.

### 3.5 Additional v1.2 contract: narrative content conditions the universe

The guiding example is a designer's abandoned Némesis station, nearby Ícaro
wreck, relay and spatial clues. New games with that installed content must
contain the declared canonical physical facts with coherent identities and
relationships. Later reading discovers rather than creates them.

The proposed data interface, a requirement rather than already approved syntax:
retain free literary text/current intel instructions; add structured physical
requirements per package or referenced registry; compile all installed
declarations before fixing a new manifest; reuse shared authored entities and
reject/report ambiguity or contradiction under explicit tested positioning
policy; combine deterministic procedural/authored sites without silently
changing density, routes, hop cap or secrets; keep reference, declaration,
materialization, knowledge and operational route separate; bind catalog
identity/version to the save rather than reinterpret existing geography when
stories or mods change.

Illustrative intentions, not executable declarations: NEMESIS_STATION is an
existing initially unknown station; ICARO_WRECK is physical only if declared
explorable and must satisfy declared proximity; RELAY_08's historical signal
still needs an implemented legitimate receiving channel. “Ícaro disappeared”
does not necessarily imply a localizable wreck; false reports cannot force the
manifest to match their falsehoods.

Additional e4 acceptance requires compatible simultaneous packages with identical
manifest under seed/config/content and changed load/activation/exploration order;
data-only new stories with verified relationships or validation failure;
actionable pregame missing-ID, ambiguous-alias and contradictory-spatial errors;
correct prose/rumor/false-claim versus NODE/LINK/SECTOR/COORD/INTEL semantics;
stable included canonical facts even when optional documents do not appear;
save/content version integrity under changed catalogs; and measured authored
effects on density/collisions/hubs/navigation over multiple seeds. Do not promise
arbitrary contradictory content can be integrated. No visual editor, free-prose
parser or universal mod manager belongs in this milestone.

### 3.6 F-DEAD-01

Search nearby physically existing or certified manifest candidates first, then
widen. Measure complete directed access and resulting chain, not only Euclidean
distance; never claim navigability without a valid route. Economic costs from
e3d may remain external reports but must not reject structurally valid candidates.
Without a candidate, retain pending work without resource/success/cooldown
consumption. Receipt requires a real channel; do not leak primaries or publish
links longer than 45 ly.

## 4. Short implementation program

The original coordination target was six Codex orders after e1, with a seventh
reserved for blocking defects. This was a scope target, not permission to trade
integrity for an exact order count. v1.3 explicitly adds the bounded e4b
intervention independently of that reserve.

| Order | Identifier | Required delivery | Exit criterion |
| --- | --- | --- | --- |
| 1 | 4D-3e1b — Manifest contract | Pure design/prototype for identity, generation versus physical sectors, authored sites, guardrail, collisions, Z and stable connections; preserve authored stories and declare/mention/reveal separation; compare seeds/orders/distributions without replacing worldgen. | Specify/prove order independence; record pending balance decisions. |
| 2 | 4D-3e2 — Worldgen integration (in progress at v1.2) | Production manifest, lazy materialization, identity/topology, authored coexistence, algorithm versioning, bounds, saves and map statistics. Review declarative narrative extensibility on delivery rather than change the running prompt. | Same seed/config yields historical geography/topology independent of exploration order, without leaks or silent balance changes. Full lore compilation was not presumed complete in this order. |
| 3 | 4D-3e3 — Scan memory | Bounded persistent observations of position/range/sensors/results/time and honest negative evidence without compulsive repetition; retain current degraded-sensor contract absent approval. | Scan/history survive saves; negative observations do not certify emptiness. |
| 4 | 4D-3e4 — Lore/intel/ad hoc | Minimal data contract and pregame compilation/validation of installed story physical requirements, hosts/reservations/authored declarations, preserved intel syntax and no retrospective creation; execute §3.4/3.5 and update authoring guides. | Data-only new entities/relations, contradiction diagnostics, stable worlds matching canonical clues, no reopened pools or late fabricated stations; existing intel syntax works. |
| Additional 4b | 4D-3e4b — Passive communications (v1.3 agreement) | Physical comms, radiod, persistent/idempotent local reception and reading/import, real gates, notices, EN/ES tests/docs. Defer corrective-node legacy activation; do not rewrite F-DEAD-01. | Actual receiver/service, no free captures or blocked consumption; pending entries survive saves. External review before e5. |
| 5 | 4D-3e5 — F-DEAD-01 | Contextual selector with manifest, progressively widening nearby search, structural rather than economic eligibility, atomic/idempotent clue preparation, pending/received distinction, navigation validation and protection. | No >45 ly hop, free rescue or retrospective station; failed attempts unconsumed, exhausted search incomplete, reception respects real channels. |
| 6 | 4D-3e6 — Playable validation and closure | Integrated regression, multiple seeds/worlds, repeated saves, failures, public controls in Textual with sound, experience report and defects. | Stable playable flow; close F-DEAD-01 only on evidence, then return to content after fixing serious blockers. |

Optional order 7 addresses blocking defects found in 2–6, not endless polishing.
If e5 needs a safety split between materialization/reception, use that reserve
and adjust closure. At v1.2, e2 was already running: do not add retrospective
requirements; review extensibility and schedule only indispensable adaptation
within e4 or an approved bounded correction. Conditional e1 catalog samples
must not become certified historical sites before manifest work. Do not migrate
scan prematurely. Lore and deadnodes must share physical preexistence semantics.

## 5. Minimum checks before closing each order

1. Read AGENTS, canon and relevant technical docs; verify Git branch/status/SHA.
2. Bound scope. Density/probability/resource/guardrail/arc-format/channel changes
   require developer decision before substantial implementation.
3. Run new tests and worldgen/lore/intel/route/deadnode/save regressions,
   including authored sites, INTEL and four existing instructions, forced
   placements and structured entities/relations/contradictions/load order.
4. Verify cross-process/order determinism, no illegitimate knowledge writes,
   exhausted-source handling and protected targets.
5. Distinguish verified, conditional, not evaluated within budget, pending
   delivery and invalid results.
6. Provide changes/tests/limits, ZIP of changed/new relative paths and diff check.
   Codex must not add, commit or push.
7. External ChatGPT review precedes the developer's manual commit/push.

## 6. Deliberate exclusions

No full new arcs/singles during stabilization (design may proceed separately),
visual content editor, free-language parser, universal mod manager or automatic
historical-world migration after installing stories. No unmeasured station
classes/density/loot/resource balance, complex triangulation or new sensor modes,
full dynamic-events/combat system, or unrelated legacy-content overhaul.
Interstellar communications beyond e4b's authorized passive minimum remain out
of scope. If missing communications block diegetic F-DEAD-01 delivery, do not
simulate receipt or declare closure: use a real implemented channel or elevate
the minimum dependency for developer decision. Do not delete old test saves.

## 7. Risks and stop signals

Require many-seed distribution/tail/isolation/playable-origin comparisons before
worldgen changes; determinism alone is insufficient. Do not change authored
occupancy or Z overflow for convenience. Preserve historical links independently
of query order. Essential arcs need legitimate validated hosts, not improvised
stations. Detect incompatible story declarations before play. Newly installed
catalogs must not silently reinterpret saved geography.

Stop closure if authoring compatibility breaks: inability to declare a story
station, unrecognized established intel, prose causing disclosure, or COORD
becoming a station. Separate structural legitimacy from action execution gates
such as travel/reception hardware. Avoid mandatory scan repetition; reconsider
feedback before adding complexity. Budget exhaustion is neither no-exit proof
nor game-over justification.

## 8. Exit back to content

After e6, play a real new game in Textual with sound through public controls.
Record reproducible defects. Fix progress blockers, corruption, secret leaks
and physical-rule violations first; backlog other improvements. Resume arcs,
singles, authored locations and narrative content rather than indefinitely
refining the generator.

## 9. Use in new conversations

Attach/link this roadmap with the last executed order, approved commit and
Codex delivery. Distinguish approval from implementation and never invent
missing decisions. Use one order per cycle: prompt → execution → report/ZIP →
review → developer commit/push → next order. Verify e1's actual Git confirmation
before assuming it. Preserve prior agreements, increment documentary versions
and prefer a separate developer documentation commit after review.

Historical v1.1→v1.2 procedure: do not stop/rewrite the running e2 order or
replace its report/ZIP. Review its original criteria separately from v1.2's
new content-compilation dependency. Prefer documenting the update after e2 is
reviewed/committed; if urgent, share it as an attachment rather than staging
the mixed worktree. Before any developer commit, inspect branch/status, changed
names and diff check; after selective staging inspect cached names. Never
assume main/master for push: verify branch/upstream/remote first. Put new
requirements in the next unsent prompt and verify them especially in e4; a
genuine incompatibility calls for an approved bounded fix, not default worldgen
replacement. The historical next step at v1.2 was to review e2 and record its
approved commit before e3; this is not today's checkout status.

Document history: v1.0 manifest/scan/lore/F-DEAD-01 sequence; v1.1 preserved
authored sites and declare/mention/reveal/intel distinctions; v1.2 installed
narrative inputs, structured requirements/prevalidation and safe coordination
with e2 already running; v1.3 explicit insertion of e4b before e5, passive
comms/radiod, persistent local reception and safe deferral of corrective legacy
activation, preserving D01–D24 and F-DEAD-01 criteria.

- **v1.5 — 2026-11-06:** 4D-3e5a, limited knowledge and explicit development diagnostics; e5b and e6 remain separate.
