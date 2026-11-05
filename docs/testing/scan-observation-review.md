# Technical review — RETORNO 4D-3e3

Spanish: [scan-observation-review.es.md](scan-observation-review.es.md).
Status: **implemented, pending external review**. Work stops with this delivery;
no git add, commit or push.

## Audit, Git and scope

Initial/final branch main, upstream origin/main. Initial/final SHA:
`590a3e87dc0e5f0e472652ce7a6d0b3d55f79bd3`. Initial tree was clean, with no unrelated local changes pending.
`git ls-remote origin refs/heads/main` confirmed the reference SHA after an
authorized retry for sandbox DNS failure. AGENTS, canon v0.3, coherence guide,
roadmap v1.2, historical contract, discovery reference, scan consumers, jobs/events,
persistence and tests were reviewed. Applicable principles: C-WORLD-001,
C-DATA-002, D02/D05/D14/D16, with D21–D24 explicitly pending e4.

Final status: 14 modified/new files, unstaged; git diff --cached empty.
`git diff --check` clean, no output. No narrative/amanecer, narrative content,
canon, balance configuration, generator/manifest or save/load code changes.
Narrative tree integrity was checked with hashes during packaging.

## Implementation and data model

The existing `_perform_scan` kernel is the sole scan implementation. At the end
of a successful sweep it appends a frozen ScanObservation: monotonic SCAN00001…
ID, exact ClockState.t (seconds since start), actual origin position/optional
physical node ID, range, sensor/service snapshot, factor and near/far probabilities,
detected/new ID tuples, actually guaranteed recovery detections, outcome, RNG
counter and optional internal job key. Conditions reflect execution, including
legitimate range/position/sensor changes after enqueueing, not an enqueue snapshot.

WorldState.scan_observations retains the latest **128** completed observations,
oldest to newest. next_scan_observation_seq persists and is never reset by pruning.
Equal-time ordering, repeated saves and later scans retain IDs/order. Retention
does not forget contacts, intel or pools. Frozen records contain no mutable node
or list references. Removed origin IDs may remain as historical provenance.

scan_observation_history(world) returns an immutable tuple without generation
or writes. There was no suitable existing public history surface, so the requested
domain API is provided without a new command/panel. The technical reference lists
all fields.

Timed jobs call the same kernel and retain params['scan_observation_id']. This
marker and terminal state prevent reapplication or more RNG consumption even
after the record ages out. Distinct jobs completing simultaneously produce two
ordered observations, not duplicate effects of one sweep.

_scan_and_discover retains gates/return shape and records once. Direct private
kernel calls retain their former unchecked semantics, including tested fallback
sensor factors; no public scanning access is expanded.

## Negative evidence, knowledge and presentation

| Outcome | Meaning |
| --- | --- |
| no_signals | No signals detected in this observation/position/conditions; no empty-space certificate. |
| known_contacts_only | Actual detections, all previously known under the existing known_nodes criterion; no new discoveries. |
| new_contacts | Newly detected contacts are separated from all detections. |

EN/ES negative feedback explicitly denies confirmation that space is empty.
Known-only feedback is distinct. CLI and Textual share existing event rendering;
tests compare both outputs. Syntax/panels are unchanged. EN/ES manuals are updated;
help's existing “perform local sensor scan” remains accurate. No sound events/cues
are added.

No omitted candidates, secret manifest inventory, sector certificates or absence
inferences are stored. Negative results erase no intel and cannot prevent a later
legitimate discovery. History publishes no known_links. The deliberate natural
scan exception for protected primaries remains: only an actual detection enters
history, never internal query enumeration. Reading manifest/history causes no
observation or disclosure.

Blocked/cancelled/interrupted scans record no completed result. Worldgen/evaluation
exceptions fail the job with scan_evaluation_incomplete and EN/ES incomplete-result
feedback, never a successful empty scan; no observation ID is consumed. Direct
calls propagate errors. Previously valid physical materializations may remain,
without becoming negative evidence. No global rollback of arbitrary engine
exceptions is promised.

SCAN_TIME_S, probabilities/factors, range, sensord gates, live-transit/stopped-
waypoint rules, draws/counter, recovery-entry exception, record_intel, fine ranges,
routes and narrative protection are unchanged. Memory changes no probabilities,
coverage requirements or repetition obligations.

## Persistence

**Schema 3** and the V2 checksum container remain. Existing WorldState.__setstate__
already defaults added slots; loader changes were unnecessary. Older schema-3
saves load empty history and sequence 1, without fabricating past sweeps from
intel. Previously queued jobs can resume and record a new observation. No complex
migration or deletion.

Besides the exact former slot representation test, a clean copy of `590a3e8`
created a real save which the new implementation loaded successfully: schema 3,
empty history, sequence 1. Repeated saves preserve order/IDs/records/job markers,
contacts and depletion. Scans after loading continue the sequence; retention
never resets it.

## Tests executed

Canonical `/home/jon/prog/retorno_case/retorno_venv/bin/python`, PYTHONPATH=src,
existing executables, no dependency installation. **32 checks: 31 pass, one
confirmed existing failure.** The focused suite passes **20 groups**, including
all requested cases and simultaneous jobs. Differential verification uses five
seeds and three sensor states: 15 exact comparisons against the frozen 590a3e8
kernel. Returns, complete state except new fields, fine ranges, intel and RNG
consumption match; global RNG remains unchanged too.

| Test | Result |
| --- | --- |
| [tests/contacts_sector_smoke.py](../../tests/contacts_sector_smoke.py) | PASS |
| [tests/deadnode_chain_detours_smoke.py](../../tests/deadnode_chain_detours_smoke.py) | PASS |
| [tests/deadnode_chain_planner_smoke.py](../../tests/deadnode_chain_planner_smoke.py) | PASS |
| [tests/deadnode_cooldown_zero_smoke.py](../../tests/deadnode_cooldown_zero_smoke.py) | PASS |
| [tests/deadnode_opportunity_selection_smoke.py](../../tests/deadnode_opportunity_selection_smoke.py) | PASS |
| [tests/exploration_recovery_smoke.py](../../tests/exploration_recovery_smoke.py) | PASS |
| [tests/forced_hidden_ad_hoc_smoke.py](../../tests/forced_hidden_ad_hoc_smoke.py) | PASS |
| [tests/intel_recent_order_smoke.py](../../tests/intel_recent_order_smoke.py) | PASS |
| [tests/known_routes_integrity_smoke.py](../../tests/known_routes_integrity_smoke.py) | PASS |
| [tests/lore_channel_preference_and_unlock_smoke.py](../../tests/lore_channel_preference_and_unlock_smoke.py) | PASS |
| [tests/lore_secondary_count_weights_hard_smoke.py](../../tests/lore_secondary_count_weights_hard_smoke.py) | PASS |
| [tests/lore_smoke.py](../../tests/lore_smoke.py) | PASS |
| [tests/manuals_style_check.py](../../tests/manuals_style_check.py) | PASS |
| [tests/nav_abort_waypoint_cleanup_smoke.py](../../tests/nav_abort_waypoint_cleanup_smoke.py) | PASS |
| [tests/nav_map_galaxy_determinism_smoke.py](../../tests/nav_map_galaxy_determinism_smoke.py) | PASS |
| [tests/nav_map_galaxy_smoke.py](../../tests/nav_map_galaxy_smoke.py) | PASS |
| [tests/procedural_radiation_smoke.py](../../tests/procedural_radiation_smoke.py) | PASS |
| [tests/radiation_hull_smoke.py](../../tests/radiation_hull_smoke.py) | EXISTING FAILURE |
| [tests/route_hop_cap_smoke.py](../../tests/route_hop_cap_smoke.py) | PASS |
| [tests/route_solve_out_of_range_origins_smoke.py](../../tests/route_solve_out_of_range_origins_smoke.py) | PASS |
| [tests/save_load_smoke.py](../../tests/save_load_smoke.py) | PASS |
| [tests/scan_job_smoke.py](../../tests/scan_job_smoke.py) | PASS |
| [tests/scan_observation_memory_smoke.py](../../tests/scan_observation_memory_smoke.py) | PASS |
| [tests/sector_intel_validation_smoke.py](../../tests/sector_intel_validation_smoke.py) | PASS |
| [tests/sensor_detection_factor_smoke.py](../../tests/sensor_detection_factor_smoke.py) | PASS |
| [tests/textual_completion_context_smoke.py](../../tests/textual_completion_context_smoke.py) | PASS |
| [tests/uplink_authored_and_failsafe_smoke.py](../../tests/uplink_authored_and_failsafe_smoke.py) | PASS |
| [tests/uplink_once_per_node_smoke.py](../../tests/uplink_once_per_node_smoke.py) | PASS |
| [tests/uplink_only_delivery_retry_smoke.py](../../tests/uplink_only_delivery_retry_smoke.py) | PASS |
| [tests/worldgen_manifest_integration_smoke.py](../../tests/worldgen_manifest_integration_smoke.py) | PASS |
| [tests/worldgen_modules_pool_smoke.py](../../tests/worldgen_modules_pool_smoke.py) | PASS |
| [tests/worldgen_sparse_archetypes_smoke.py](../../tests/worldgen_sparse_archetypes_smoke.py) | PASS |

radiation_hull_smoke.py retains its line-183 CARNAVAL_34 failure: no expected
radiation event. The same assertion reproduces with the clean initial HEAD and
same venv. Unrelated code was left unchanged; this is not an e3 regression.

Iterations are explicit: the first new focused run failed group 3 because its
controlled fixture lacked an information frontier and existing recovery added
a guaranteed entry between sweeps. A legitimate unconsumed data source was added
to the fixture without changing recovery or probabilities; all 20 groups then
passed. The focused suite was rerun after adding simultaneous-job assertions;
manual style was rerun after manual updates, both passing. Scan, sensors and
save/load also passed initial checks and full regression. Initial output,
follow-ups and baseline checks are in
[scan-observation-test-results.json](scan-observation-test-results.json).

## Limits and next work

Memory records observation, not physical inventory, negative certainty or an
F-DEAD-01 solution. Retention discards older detail without deleting knowledge;
there is no UI history browser yet. No cumulative reliability, triangulation,
Bayesian simulation or mandatory repetition. Recovery planning does not consume
this history.

E2 lazy materialization, inverse inventory and budgets remain. The seed-271828 Z
witness is observed at its actual position with distinct source/physical sectors.
Installed narrative requirements are not compiled: D21–D24 and lore/intel/ad hoc
adaptation remain e4, F-DEAD-01 integration e5. No narrative/arc/single/authoring-
guide changes. No incompatibility required extending scope or another decision.

## Files and ZIP

retorno-4D-3e3-review.zip, beside the repository directory: only these 14
modified/new files with relative paths. Entry list, CRC and bytes verified; no
.git, caches, saves, narrative or recursive ZIP. EN/ES references/manuals are
synchronized and internal links checked. Work stops for external review without
stage, commit or push.

| File | Responsibility |
| --- | --- |
| [data/manuals/commands/scan.en.txt](../../data/manuals/commands/scan.en.txt) | Updated EN/ES scan manual. |
| [data/manuals/commands/scan.es.txt](../../data/manuals/commands/scan.es.txt) | Updated EN/ES scan manual. |
| [docs/README.es.md](../../docs/README.es.md) | EN/ES index of implemented memory and pending phases. |
| [docs/README.md](../../docs/README.md) | EN/ES index of implemented memory and pending phases. |
| [docs/systems/discovery-navigation-intel.es.md](../../docs/systems/discovery-navigation-intel.es.md) | EN/ES technical reference: structure, semantics, persistence and compatibility. |
| [docs/systems/discovery-navigation-intel.md](../../docs/systems/discovery-navigation-intel.md) | EN/ES technical reference: structure, semantics, persistence and compatibility. |
| [docs/testing/scan-observation-review.es.md](../../docs/testing/scan-observation-review.es.md) | EN/ES review report and file inventory. |
| [docs/testing/scan-observation-review.md](../../docs/testing/scan-observation-review.md) | EN/ES review report and file inventory. |
| [docs/testing/scan-observation-test-results.json](../../docs/testing/scan-observation-test-results.json) | All outputs from 32 checks, follow-ups and baseline. |
| [src/retorno/cli/repl.py](../../src/retorno/cli/repl.py) | EN/ES negative, known-only and failure feedback; renderer shared with Textual. |
| [src/retorno/core/engine.py](../../src/retorno/core/engine.py) | Single post-detection recording point; idempotent job marker and explicit incomplete-evaluation failure. |
| [src/retorno/model/world.py](../../src/retorno/model/world.py) | Immutable ScanObservation, ScanOutcome, 128-record retention, sequence and read API. |
| [tests/fixtures/scan_590a3e8.py](../../tests/fixtures/scan_590a3e8.py) | Frozen former kernel for differential tests only. |
| [tests/scan_observation_memory_smoke.py](../../tests/scan_observation_memory_smoke.py) | 20 new groups: real flow, persistence, secrets, limits and RNG equivalence. |
