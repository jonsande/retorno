# Updated report — 4D-3e5: structural first reception

[Español](structural-recovery-review.es.md). Focused correction for external review, 2026-11-06.

## Reproduced defect

Before editing production, group 28 placed the ship at wreck `A`, with a known
directed `A -> REMOTE` route, historical relay REMOTE and valid physical chain
to T. Search returned `validated / complete_in_examined_scope` instead of the
required `conditional`. Local radio could not receive REMOTE from A. Navigable
access was incorrectly treated as informational access; former group 5 accepted
that equivalence too. The prepared active plan prevented another selection.

The unpublished initial delivery and Tweaks are preserved. Initial/final HEAD:
`ba705e73d958334ca2e5dfa8d57d6a1f3644b89a`, branch `main`, upstream `origin/main`.
There are **34 cumulative modified/new files**, empty index, no stage/commit/push.
All 34 files were copied before this correction.

## Solution and future physical coverage

`communications.radio_spatial_block_reason` extracts existing physical-source,
current-node, broadcast-kind and required-docking checks. It ignores receiver
health, supply and radiod. No range, power, attenuation, latency or delivery mode
was added.

Selection uses this predicate to admit first-reception origins. Eligible origins
retain directed-distance ranking, tie breaks and physical detours. With only
remote origins, search may return a diagnostic physical proposal as
`conditional / first_reception_outside_coverage`. `request_recovery` confirms only
`validated`; a proposal alone is not authorization. `confirm_recovery` independently
rechecks coverage before copying/materializing, rejecting direct confirmation of
a remote conditional proposal as well.

| Aspect | Check |
| --- | --- |
| Physical history | Manifest certificates, original identities/kinds/positions/hops. |
| Access to emitter | Known directed navigation path; not evidence of reception. |
| Spatial first reception | Shared communications predicate; currently local context. |
| Operational receiver | Existing comms/radiod/supply gates, reevaluated at capture. |

An off/damaged receiver at the correct location can prepare pending reception.
Without coverage, search creates no plan, radio ledger entry, file, knowledge or
attempt/cooldown/counter. No omniscient source guidance, free internal mail or
invented transmitter. Conditional search never enters `recovery_plans`, so it
cannot block another selection as an active-plan frontier. Cursors/retries remain
and location/context changes permit a new selection.

Selection, confirmation and capture call one predicate; F-DEAD-01 embeds no
independent node-equality coverage rule. Group 34 substitutes only that predicate
in an isolated test and verifies all three consumers follow it. Future 4D-3e5b
coverage replaces this boundary without rewriting selection. Pending-count UI
remains 4D-3e5a work.

Save/load of an uncaptured plan also checks its original `access.path[0]` context
through the same predicate with an explicit receiver. The player need not remain
there: legitimate pending plans can leave and return. Earlier invalid remote-first
saves are explicitly rejected without deleting or rewriting files; no corrective
migration or invented guidance is introduced. Schema, resources, pools, scheduler
and thresholds/cooldowns remain unchanged.

## Current tests and results

**36 structural groups pass**: the original 27 (group 5 now expects conditional)
and nine new groups. **20 narrative** and **18 radio groups** were rerun, together
with navigation, worldgen, intel, saves, lore, energy/systems, planners, Textual and
all remaining smoke scripts.

| New group | Coverage |
| --- | --- |
| 28 | Remote reproduction, direct confirmation rejection, no consumed progress. |
| 29 | Eligible local origin over shorter remote chain (90 ly versus a longer detour). |
| 30 | Spatial eligibility with receiver off/damaged, independent docking context. |
| 31 | Public repair/boot, pending reception and exactly one capture. |
| 32 | Conditional search, widening, relocation, EN/ES save/load and idempotency. |
| 33 | Public conditional search, travel on an already known route, local capture and reading. |
| 34 | One spatial boundary for selection/confirmation/capture; isolated test, no range implementation. |
| 35 | Primary protection and generic diagnostics without source/destination disclosure. |
| 36 | Recorded preparation context, legitimate departure/return and incompatible-save preservation. |

New public flows use declared historical scenes without state edits to solve the
journey after commands start, separately from the installed prologue journey and
failure fixtures:

```text
PUBLIC FIRST RECEPTION REPAIR: power off security -> drone deploy D1 BRG-01 -> drone repair D1 comms -> power on comms -> boot radiod ; one capture
PUBLIC FIRST RECEPTION FLOW: scan -> nav REMOTE -> power off security -> power on comms -> boot radiod -> cat received file; one capture
```

Final global run: **63/64 scripts pass**. Only failure:
`radiation_hull_smoke.py:183`, `AssertionError: []`, CARNAVAL_34. The trace exactly
matches the initial delivery; it was neither fixed nor hidden. Textual passes.
EN/ES manuals and `git diff --check`: PASS. The first correction run (35 groups,
before the additional persistence guard) also returned 63/64; final evidence uses
36 groups.

```sh
# Canonical environment; temporary runner executes every tests/*smoke*.py serially,
# with PYTHONPATH=src:repo and isolated save directories.
/home/jon/prog/retorno_case/retorno_venv/bin/python /tmp/retorno_e4_regression.py e5-first-reception-final 1
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/manuals_style_check.py
git diff --check
```

The individual structural command ran before group 36; the final global run
reexecuted all 36. [Accumulated evidence](structural-recovery-test-results.json)
contains current per-script results/logs/metrics and separately preserves initial
delivery results. Procedural generation was unchanged; its tests were rerun.

## Scope, files and delivery

This correction changes **12 of the 34 cumulative files**; the remaining
**22** are byte-identical to the initial delivery. Textual/audio, AMANECER,
stories, generation, comms balance/health/load, radiod, intel grammar, pools/salvage
and thresholds/cooldowns were not changed. EN/ES comms manuals and selection/radio
contracts updated. Public commands/help require no syntax change.

- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/structural-recovery-review.es.md`
- `docs/testing/structural-recovery-review.md`
- `docs/testing/structural-recovery-test-results.json`
- `src/retorno/core/communications.py`
- `src/retorno/core/structural_recovery.py`
- `tests/structural_recovery_smoke.py`

New complete archive with every cumulative file and relative paths:
`retorno-4D-3e5-first-reception-review-20261106.zip`. Exact inventory, bytes, CRC and external SHA-256 are verified;
checksum is delivered in the companion `.sha256` and response, avoiding a circular
reference inside the ZIP. Original `retorno-4D-3e5-review-20261106.zip` stays intact.
Index empty; HEAD preserved. Work stops for external review.

Current cumulative inventory:

- `data/manuals/concepts/navigation.en.txt`
- `data/manuals/concepts/navigation.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/design/deadnode-chain-planner.es.md`
- `docs/design/deadnode-chain-planner.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/systems/discovery-navigation-intel.es.md`
- `docs/systems/discovery-navigation-intel.md`
- `docs/systems/exploration-failsafes.es.md`
- `docs/systems/exploration-failsafes.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/structural-recovery-review.es.md`
- `docs/testing/structural-recovery-review.md`
- `docs/testing/structural-recovery-test-results.json`
- `src/retorno/core/communications.py`
- `src/retorno/core/deadnodes.py`
- `src/retorno/core/engine.py`
- `src/retorno/core/exploration_recovery.py`
- `src/retorno/core/lore.py`
- `src/retorno/core/structural_recovery.py`
- `src/retorno/io/save_load.py`
- `src/retorno/model/world.py`
- `tests/exploration_recovery_smoke.py`
- `tests/known_routes_integrity_smoke.py`
- `tests/passive_communications_smoke.py`
- `tests/structural_recovery_smoke.py`
- `tests/uplink_authored_and_failsafe_smoke.py`

## Initial delivery report — historical record

The following original report is retained. Its group counts and ZIP name refer
to that historical delivery; the current results, contract and package above
supersede them for this correction.


[Español](structural-recovery-review.es.md). Date: 2026-11-06. External review delivery; no commit.

## Result and audited baseline

F-DEAD-01 uses certified historical sites, bounded directed search with widening
and transactional preparation. The first clue uses the common radio ledger;
later clues require reading and exploring each stage. No stations, bridges or
gateways are fabricated. There is no universal exit guarantee.

Initial and final HEAD: `ba705e73d958334ca2e5dfa8d57d6a1f3644b89a`. Branch `main`, upstream
`origin/main`, matching local refs. The starting remote SHA was developer-confirmed;
this delivery does not claim a new commit. Initially clean; finally 34 modified/new
files listed below, empty index. No `git add`, commit or push was executed.

AGENTS, canon/coherence, roadmap 1.3 and requested contracts were read, together
with models, planners, worldgen, lore, radio, persistence, engine, CLI and Textual
presenters. Approved D01–D24, advisory 3b/3c/3d and implemented e4b deferral are
separated. Historical corrective-node descriptions are explicitly superseded.
Tweaks remains intact: comms OFFLINE 0.72 and zero disconnected load, LIMITED when
powered with dependencies; localized service hints, deploy defaults to actual bay,
and radio excluded from the Textual systems panel. No balance, world data, canon,
audio, UI, AMANECER drafts or arc/single content changed.

## Architecture and legacy comparison

The [production contract](../systems/structural-recovery.md) owns the algorithm
and limits. `select_recovery` is pure, without RNG or materialization, using the
pinned manifest, inverse physical queries including Z, present/lazy/authored
certificates and stable ordering. Dijkstra prioritizes full ship-to-origin-plus-chain
distance, then materialization uncertainty, hops and ID. It considers detours and
physical scales using previously known directed routes.

The adapter reuses `AccessRoute`, planner intel-source reading, delivery
capabilities, primary policy and hop kernels. Proposed coordinates from
`propose_deadnode_chain` are not authority; `evaluate_deadnode_opportunity` and
`compare_deadnode_opportunities` remain diagnostics with economic analysis.
Those economic filters do not determine structural eligibility.
`_create_bridge_node`, `_sample_anchor_offset`, `_ensure_entry_node` and
`_ensure_gateway_node` and retrospective preparation were removed. Valid existing
legacy chains remain consumable. `recovery_activation_deferred` is a compatible
field without creation authority; diagnostics read actual searches and plans.

Defaults: 16 sectors/query, 2048 sites, 4096 expansions, 65536 edges and 1024 retained
certificates. The 3D shell cursor follows initial generated/observed sectors and
explicit-target corridor probes. Deterministic retries widen without a fixed
gameplay radius. Finite memory/closure/domain/materialization budgets can leave a
chain unproven, never establish universal absence. Outcomes distinguish
`search_pending`, `validated`, `conditional`, `none_in_scope`, `incomplete`, `invalid`.
No optimality outside examined inventory is claimed.

Confirmation revalidates scope/version, structural fingerprint (including trackers),
identity, position, kind, provenance, access, all hops, sources and protection.
Joint materialization and source/ledger preparation occur on a disposable copy
before publication. Failure discards it. Publication preserves existing node/pool
references. No resources, files, intel, RNG, scheduler rolls or narrative assignment
are consumed. Reconfirmation reuses the opportunity.

## States and delivery

| State | Meaning / transition |
| --- | --- |
| Search pending/incomplete | No demonstrated proposal yet; retry consumes no delivery. |
| `prepared` | Internal transactional preparation. |
| `receipt_pending` | Source in ledger; capture awaits gates/context. |
| `active` | Actual capture or enabled salvage stage. |
| `stage_consumed` | Reading/import published the link; arrival remains. |
| `complete` | Last clue consumed and final destination reached. |
| `invalid` | Physical, source or identity revalidation failed. |

The first source is a reachable historical hub with locally supported emission.
There is no fictitious emitter or second queue. Each clue contains one positive
LINK ≤45 ly, preserving the real parser's bidirectional semantics. Selection,
confirmation and capture reveal neither chain nor operational routes. Reading
and arrival enable the next source. Existing routes need no added document.
Salvage is prepared before visit in an open window; pools/files/resources never
reopen or refill. Reserved hosts are excluded; unsupported primaries fail closed.
Natural scan and exact manual solve remain exceptions.

Frontiers include directed routes, pending uplink independent of repair state,
unconsumed data, readable recovered LINK/NODE and active plans. Structural existence
ignores electricity, health, drones, scrap, radiation and repairs. Capture checks
comms/radiod, supply, transit/hibernation and current local source. Tests preserve
sensord/datad independence, internal mail, salvage and uplink-specific gates.

Only the first actual capture increments deadnode attempts/last_action_t, or global
counter/generation. Preparation, failure, budgets, blocked reception and staleness
do not count; later stages add no attempt. Seeded thresholds, triggers and cooldown
remain. Resolved legacy trackers may be removed; plan/ledger retain history.
Pinned manifest, versioned plan, stage, sources, captures/reads, cursor/certificates,
counters, pools and intel persist. Incompatibility rejects without deleting saves;
no complex historical migration was added.

## Validation and public journeys

Baseline: **62/63** smoke scripts pass. Final: **63/64** pass including the new
script. The only failure in both is `radiation_hull_smoke.py:183`, `AssertionError: []`,
CARNAVAL_34 fixture; traces are literally identical. Radiation was neither changed
nor reported as passing.

New integration: **27 groups** covering present/lazy/authored, empty/isolated/Z,
seeds/orders/processes, directed distance/detours, 45/>45/zero, missing endpoints,
budgets/widening, economic invariance, gates/source return, capture/read/stages,
visited/cleaned/closed pools, preparation before consumption, primaries/scan/manual,
save boundaries, collisions, stale snapshots, injected failure after clone
materialization, counters/cooldown, known-route scales, UI/localization and stored
NODE frontiers. Narrative integration: **20 groups**; radio: **18 groups**.
Worldgen/manifest, navigation, 3b/3c/3d planners, lore/intel, scan, energy/systems,
salvage/pools, saves and Textual regressions pass. An intermediate Textual theme
run failed with `NoMatches` in a teardown callback for `#header`; Textual was
unchanged and subsequent full runs, including the final run, pass. Evidence
retains the intermediate trace.

Group 26 starts shipping prologue seed 701, without fixtures or editing geography,
resources or systems: ordinary repair, radio, sensors, scan, solve, travel and
docking at ECHO_7. Existing exploration remains and no rescue is manufactured.
Separately, group 19 follows positive recovery through public commands from a
synthetic exhausted historical scene, with no edits to solve it. Difficult chains
and failures use separate fixtures. The prologue is not claimed to need recovery.

```text
PUBLIC SCENE FLOW: power off security -> power on comms -> boot radiod -> scan -> cat /logs/broadcasts/A_0011.en.txt -> nav B ; resources and systems use ordinary rules
PUBLIC INSTALLED FLOW: power off security -> power off data_core -> drone deploy D1 PWR-A1 -> drone repair D1 power_core -> drone repair D1 power_core -> drone repair D1 power_core -> drone move D1 BUS-A2 -> drone repair D1 energy_distribution -> drone repair D1 energy_distribution -> drone move D1 BRG-01 -> drone repair D1 comms -> power on comms -> boot radiod -> power on sensors -> boot sensord -> scan -> route solve ECHO_7 -> nav ECHO_7 -> dock ECHO_7 ; t=2153.115s scrap=49; existing frontier preserved
```

Main commands executed; temporary runner uses the canonical interpreter,
PYTHONPATH=src:repo, temporary saves and a per-script timeout:

```sh
# Baseline and final global runs, canonical venv; serial runner invokes every tests/*smoke*.py.
/home/jon/prog/retorno_case/retorno_venv/bin/python /tmp/retorno_e4_regression.py e5-baseline 1
/home/jon/prog/retorno_case/retorno_venv/bin/python /tmp/retorno_e4_regression.py e5-release 1
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/worldgen_manifest_comparison.py --production --output /tmp/retorno-e5-manifest-comparison.json
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/manuals_style_check.py
git diff --check
```

The runner also executed e5-first/e5-final/e5-delivery during integration; release
evidence is e5-release. Every smoke script can be reproduced individually with
the same interpreter/PYTHONPATH.

Full physical comparison on seeds 0–7,29,271828 matches
`manifest-integration-measurements.json` for physical/components/identity/distribution
and resource metrics, excluding benchmarks/timings. EN/ES manuals PASS; both
roadmaps' D01–D24 are byte-equivalent. AST/JSON, new links and language pairs checked.
`git diff --check`: PASS.

## Measured cost and limitations

Instrumented time includes tracemalloc and purity checks on this machine; these
are measurements, not performance thresholds or real-time promises.

| Case | Result | Seconds | Peak bytes | Sectors / cohorts | Expansions / edges |
| --- | --- | ---: | ---: | ---: | ---: |
| installed | validated | 0.249722 | 853771 | 16 / 42 | 2 / 25 |
| chain | validated | 0.068067 | 837338 | 16 / 38 | 3 / 2 |
| materialized | validated | 0.228007 | 955502 | 16 / 30 | 2 / 4 |

Search is synchronous under the existing engine lock, bounded by work rather
than wall-clock deadline. Large inventories or long chains can exhaust budgets
or the retained window; widening cannot promise retaining every earlier chain.
No exhaustive search or universal connectivity. A local emitter, usable source,
connectable site, numerical domain or travel resources may be unavailable. Results
remain conditional/incomplete/none in that scope; no exit is fabricated. Extended
playable Textual/sound validation remains e6. No balance or delivery modes expanded.

## Files and package

All 34 complete modified/new files below are included with relative paths.
No .git, venv, caches or user saves. External per-file SHA-256 inventory, exact
archive inventory/bytes, CRC and final SHA-256 are verified. ZIP beside the repo:
`retorno-4D-3e5-review-20261106.zip`, checksum in its `.sha256` companion and delivery.
The ZIP's hash is external to its own contents to avoid a circular reference.
[Complete results](structural-recovery-test-results.json).

- `data/manuals/concepts/navigation.en.txt`
- `data/manuals/concepts/navigation.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/design/deadnode-chain-planner.es.md`
- `docs/design/deadnode-chain-planner.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/systems/discovery-navigation-intel.es.md`
- `docs/systems/discovery-navigation-intel.md`
- `docs/systems/exploration-failsafes.es.md`
- `docs/systems/exploration-failsafes.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/structural-recovery-review.es.md`
- `docs/testing/structural-recovery-review.md`
- `docs/testing/structural-recovery-test-results.json`
- `src/retorno/core/communications.py`
- `src/retorno/core/deadnodes.py`
- `src/retorno/core/engine.py`
- `src/retorno/core/exploration_recovery.py`
- `src/retorno/core/lore.py`
- `src/retorno/core/structural_recovery.py`
- `src/retorno/io/save_load.py`
- `src/retorno/model/world.py`
- `tests/exploration_recovery_smoke.py`
- `tests/known_routes_integrity_smoke.py`
- `tests/passive_communications_smoke.py`
- `tests/structural_recovery_smoke.py`
- `tests/uplink_authored_and_failsafe_smoke.py`
