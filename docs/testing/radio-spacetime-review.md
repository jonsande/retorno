# RETORNO — Technical report 4D-3e5b

Date: 2026-11-06. Implemented and stopped for external review.
[Español: complete report](radio-spacetime-review.es.md).
[Physical contract](../systems/radio-spacetime.md).
[Complete machine-readable evidence](radio-spacetime-results.json).

## Final correction — persisting invalidations

Current delivery: **46 complete files**, the previous 45 plus
`tests/recovery_invalidation_smoke.py`. **Legitimate invalidation now supports
save/load without loss of progress.** HEAD remains
`4c4318502e83de9fae66be78f0baeb882c7d69d8`, main → origin/main, no staging/commit/push.

### Reproduction and diagnosis

Before changing the core, provenance case 12 was extended: load the real v1 slot,
capture once, read/import A → B, arrive at B and advance to the second stage.
The plan became `invalid`, stage=1, captured=consumed=(0,), with only one opportunity
and no manufactured transmission. `save_single_slot()` raised
`SaveLoadError (... Recovery stage ledger mismatch)`: validation required the very
opportunity that `_radio_stage()` had refused to create. The full original traceback
is preserved in the evidence JSON.

The other two scenarios were reproduced separately using the unchanged core module
from the previous 45-file ZIP in an isolated process. Controlled withdrawal of
future emission B → C after confirmation/capture/import of A → B invalidated v2
at stage=0; saving failed with `Recovery declared stage emission unavailable`.
Passively receiving B → C before stage activation produced a real receipt, but
advancement treated it as a collision: invalid, stage=1, two opportunities, and
saving failed with `Recovery stage ledger mismatch`. Neither created a slot.
The complete reproduction script/output is in the JSON; the previous ZIP retains
SHA-256 `c11b4e57d6f09a404a8bd00f4043dbd0cde65300c7d087d9879dc6712c8c6e84`.

### Corrected validation and continuity

Only `src/retorno/core/structural_recovery.py` changes in the game core. It reuses
existing validators with a confirmed `source_contract`, explicit progress checks
and `invalidation=(reason, fingerprint)`, recorded by the engine after checking
physical integrity, proposal, version and earlier ledger. These are consistency
fingerprints, not signatures. Merely setting `status` to `invalid` is insufficient;
passing an adulterated proposal through engine advancement cannot certify it.

| State | Save/load requirements |
| --- | --- |
| Active | Valid sources and all already prepared opportunities; coherent progress. |
| Complete | Every stage consumed, intact contract and ledger. |
| Legitimately invalidated | Checkpoint bound to contract/progress; earlier ledger mandatory; future availability and the current never-prepared opportunity are not required. |
| Adulterated/incompatible | Reject without deleting/rewriting the slot for incoherent version, certificates, proposal, progress, checkpoint or ledger. |

The fields are additive for schema 3: the real v1 fixture and older-shaped active
v2 slots load. v1 still consumes only previously prepared opportunities, retaining
its meaning without fictional transmitters. Roundtrips compare the complete world,
ship, OS, clock and meta: routes, intel, files, resources, receipts, attempts and
cooldowns remain intact. Ordinary passive listening can move its technical search
cursor after relocation; this is neither progress nor cooldown. The plan remains
outside ACTIVE, does not advance and cannot duplicate its first receipt. A future
search for the same blockage can confirm a genuinely available new first source at
B; the old A receipt is not recycled. Both global and deadnode paths are tested.

The early-receipt defect was reproduced and receives a local fix: the v2 stage
reuses the canonical received/imported record with exact emission, emitter,
content and LINK. It does not recapture, generate another event, increment
attempts/cooldowns or write another file. An unread receipt still requires
reading/import; an already imported LINK consumes the stage when reached. Both
cases support save/load and completion of the chain.

Explicit limit: recovery accepts continuous open-ended emissions; no dynamic
transmitter shutdown is added. Future-source withdrawal is a controlled fixture
change recompiled through the existing compiler, not an authoring/scheduler/worldgen
change. Deleting a declaration backing an already persisted receipt remains an
incompatible radio ledger, not a legitimate invalidation to accept. Uncertified
invalid saves are not automatically repaired; the previous delivery could not
produce the reproduced invalid slot through the productive save API.

### Final validation and delivery

**68/69 scripts PASS**, with only the same historical `CARNAVAL_34` failure in
`radiation_hull_smoke.py:183`. Its log matches the previous delivery and baseline
byte-for-byte: SHA-256 `e54ccf0ca0e8da2081a1c8a338d71c8489f84a37c99f4a9c7eb9946dc582195b`.
Passing groups: **8 new** invalidation, **18** provenance (extended case 12),
**43** spacetime, **36** structural, **19** knowledge, **20** narrative and **18**
prior radio, plus general persistence, CLI/Textual/audio and manuals. The 8+18
focused groups were rerun after bilingual diagnostics and expanded deadnode
coverage: PASS. Commands, timings, codes and logs are in the JSON. EN/ES manuals
were reviewed: no new instructions are needed because standard saving is restored
without exposing internal plans; style checker PASS. Technical contracts and
diagnosis are updated in both languages.

Power/range, propagation, production emitters/emissions, authoring contract,
worldgen, scheduler, navigation, primary protection, procedural information,
resources/survival, CLI/Textual/audio and AMANECER remain unchanged. Every other
source module from the previous ZIP is byte-identical. `git diff --check` and
empty-index verification: PASS.

Current ZIP: `deliverables/retorno-4D-3e5b-final.zip`, with a full 46-file manifest
and external SHA-256 to avoid circularity. Previous ZIPs are preserved. Stopped
for external review; no staging, commit or push.

## Integrated focused correction — provenance of every F-DEAD-01 clue

This section preserves the provenance correction before the final persistence fix.
That delivery retained all original 40 files/work; **45 accumulated files** were
unstaged, without commit/push. HEAD remains 4c4318502e83de9fae66be78f0baeb882c7d69d8,
main → origin/main.

Before behavior changed, the original certified A → B scene returned validated,
first_emission_id=None, no declared radio emitter, then manufactured LINK: A -> B.
The A → B → C scene manufactured another undeclared broadcast at relay B; a ship
intermediate received an injected salvage archive during confirmation. All three
original payloads are retained in the report JSON.

A real pre-correction slot was saved first: tests/fixtures/recovery_legacy/pending-v1.dat,
SHA-256 `384481e72ef383dcf4c4a1966d2dcceccbf824cd17e63020df58aecd074a0612`. Its prepared first message still loads/captures once;
its unprepared second radio stage cannot be manufactured. The original is not rewritten.

New plans use historical-recovery-v2. RecoveryProposal.stage_sources stores stable
reference and payload SHA-256 for every informative stage. first_emission_id is
mandatory for local and remote starts. Plan identity includes sources to distinguish
retries with different declarations. _source/_edge_source no longer infer radio
from installation kind. Selected-path evidence is kept with that path across origins.

Selection requires an installed exact navigation_link_to station_broadcast,
open-ended continuous repetition and no scheduler-gated narrative piece. First
reception checks coverage/arrival at the ship. Later radio stages require certified
activity already available at their host; open-ended repetition remains valid on
arrival. Confirmation revalidates sources/coverage/time before publication, and
capture revalidates payload/current gates. _radio_stage copies declared content
under radio:<id>, never a replacement clue calculated during blockage.

Salvage stages require an existing pool or installed authored archive containing
the exact LINK. File path/fingerprint persist; mount base-before-injected precedence
is respected. Confirmation injects no archive and initializes no pool to create a
clue. Known directed routes keep their own mechanism. Closed/cleaned/inspected
sources receive no new documents; previously reserved existing archives remain
readable on arrival without reopening them.

| Source | New plan | Compatibility/condition |
| --- | --- | --- |
| Station/relay without equipment | No | Physical kind proves no transmission. |
| Equipment with empty emissions | No | Equipment does not imply activity. |
| Unrelated destination/payload | No | No calculated replacement LINK. |
| Local historical continuous exact LINK | Yes | Certificate, coverage, arrival and current gates. |
| Equivalent remote emission | Yes | Same e5b spatial/temporal boundary. |
| Not-arrived or expired signal | No | No legitimate current reception. |
| Intermediate without source | No | Incomplete chain cannot confirm. |
| Existing exact-LINK archive | Yes, salvage stage | Eligible/mountable source and verified fingerprint; no injection. |
| Known operational directed route | Yes, route stage | No messages/files generated. |
| Persisted v1 opportunity | Retained | Original local reception, no fictional transmitter metadata. |
| Authorized legacy narrative interaction | Retained | Existing triggers/gates, not a new recovery plan. |
| Unprepared v1 radio stage | Never created | Continuation becomes invalid, permitting alternatives. |

Without complete sources, conditional/incomplete results create no active plan,
attempt, cooldown or candidate disclosure. Widening/retries still react to position,
time and knowledge. Installed content may lack legitimate recovery because no
general historical transmission catalogue exists. None is added to rescue tests;
that possible dependency remains an explicit future decision, potentially in e5c.

Eighteen new recovery_provenance groups cover equipment/activity absence, unrelated
content, valid local/remote sources, arrival/expiry, multistage evidence, missing
intermediates, existing salvage, no counters/disclosure, genuine v1 slot, v2 saves,
primaries, pure CLI/Textual/debug and missing-evidence rejection. They also cover
mount collisions and unrelated reading after a known-route stage is consumed.
All 36 structural groups remain, with successful scenes explicitly declaring prior
emissions/archives before search. No procedural kind-based transmitters are added.
Spatial test 26 now requires fixture-history even when at its host.

All 43 spatial, 36 structural, 19 knowledge, 20 narrative and 18 prior radio groups
pass. That delivery's global regression: **67/68 PASS**, only pre-existing radiation_hull_smoke.py:183,
CARNAVAL_34; its log matches both earlier references. EN/ES manuals and diff check
pass. Formula, profiles, power/sensitivity, propagation, comms/radiod, energy,
navigation/topology/density, narrative probabilities, survival, protection, knowledge,
Textual/audio and AMANECER remain unchanged.

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/recovery_provenance_smoke.py
/home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_validation.py /tmp/retorno-radio-correction-release
```

The accumulated deliverables/retorno-4D-3e5b-corrected.zip includes all 45
complete files with adjacent SHA-256/manifest. The previous archive is preserved
unchanged (`c0270639b2aba5f3cf39cf81786397021994515739aeb35e9af733b4674f0ba4`). Stopped for external review.

## Reference and audit

Initial/final HEAD `4c4318502e83de9fae66be78f0baeb882c7d69d8`, branch main, upstream origin/main. The original e5b started clean;
the focused correction started with its 40 unpublished modified/new files.
46 changed/new files remain unstaged. No git add, commit or push.
The external deliverables/retorno-4D-3e5b-final.zip contains every file below at repository
relative paths, verified with CRC and byte comparisons. Adjacent SHA-256/manifest
avoid a circular hash in this report.

AGENTS, canon/coherence, temporal design, communications/recovery/scheduler,
narrative, navigation and roadmap contracts were read. communications,
structural_recovery, lore, engine, world/ship/gamestate, balance, manifest/narrative/
generator, data_loader, save_load, CLI/parser and Textual renderers were audited.

Receiver position is world.current_pos_ly; arrival/abort synchronize it. Certified
sources use ManifestDefinition/HistoricalSite and resolve_operative_id, including
lazy hosts without materialization. Legacy reception matched node/kind/docking;
electrical, comms/radiod, health, Core OS, quality and context gates already existed.
Lore prepares after compatible dock/uplink/salvage; recovery prepares on confirmation
and progression. Tick advances clock.t first, then arrival/jobs/scheduler, power,
wear/consequences, finally radio retry. Hibernation runs chunks with its flag set;
wake clears it and evaluates recovery. Seconds since start and the 365-day year
already serve jobs, events, travel, lore and cooldowns. V2/schema 3 persists a
catalogue snapshot, checksums and backups. No second ledger/service/sensor/generator
was needed. Engine/parser entry points are unchanged.

## Geography and provisional balance

Before selecting numbers, four starting-area seeds showed 43–52 sites per 27
10-ly sectors and 3.85–4.70 ly nearest medians including authored co-location.
The reproducible extended measurement excludes zero separations for positive
nearest distances, adding bulge/halo: 12 samples, 324 queried physical sectors,
no materialization or density/topology changes.

| Seed | Region | Sites / 27 sectors | Sites/sector | Positive nearest median ly | Positive edge median ly |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | disk | 52 | 1.93 | 4.110 | 5.240 |
| 1 | bulge | 40 | 1.48 | 4.508 | 4.873 |
| 1 | halo | 37 | 1.37 | 4.805 | 5.796 |
| 8 | disk | 43 | 1.59 | 3.950 | 6.087 |
| 8 | bulge | 45 | 1.67 | 4.891 | 5.708 |
| 8 | halo | 41 | 1.52 | 4.648 | 4.965 |
| 701 | disk | 45 | 1.67 | 4.447 | 4.412 |
| 701 | bulge | 39 | 1.44 | 3.693 | 5.651 |
| 701 | halo | 41 | 1.52 | 5.685 | 6.048 |
| 271828 | disk | 47 | 1.74 | 4.769 | 5.445 |
| 271828 | bulge | 38 | 1.41 | 4.363 | 4.786 |
| 271828 | halo | 34 | 1.26 | 6.683 | 7.068 |

Sensors remain 2.5 ly. Starting-area next hubs after co-located ECHO_7 are
5.448–8.495 ly away; HARBOR_12 is 12.649 ly and ARCHIVE_01 15.455 ly. Radius 6
contains 1–2 geometric hubs including local; radius 20 contains 8–17, implying
no transmitters/activity. Bulge/halo nearest hubs can be 7.47–15.96 ly away.
These are physical recovery-inventory candidates, not proofs of reception or
directed access. New recovery fixtures use a first source at 5 ly and a 12-ly LINK.

| Family | Normalized P | Provisional nominal range | Reason |
| --- | ---: | ---: | --- |
| emergency | 0.25 | 0.5 ly | Short neighborhood relative to typical separation. |
| station | 36 | 6 ly | Covers some normal neighbors, exceeds sensors without covering the whole area. |
| interstellar_relay | 400 | 20 ly | Spans multiple sectors only with declared specialized activity. |

LIMITED/NOMINAL/UPGRADED sensitivity is 0.25/1/2.25, multiplying range by
0.5/1/1.5. Explicit valid power can adjust profiles. Values are provisional,
uncalibrated gameplay budgets, not canonical watts/dBm. Playability is shown at
5 ly with declared activity; missing sources are never manufactured. The 45-ly
navigation cap does not set radio range.

## Architecture, time and data

RadioEmitter separates equipment identity/host/category/power; RadioEmission
separates emission identity, activity, payload and temporal reference. Stations
without declarations do not automatically emit. Euclidean d=math.dist(certified
host,current_pos_ly), normalized I=P/max(d,1e-9)^2 and R=sqrt(P*S), inclusive
d<=R with S>0. P bounds are 10^-8..10^4; values/types are validated. Coverage is
deterministic, monotonic and independent of gameplay RNG/materialization order.

Light delay is d×YEAR_S. Reception window is [start_t+delay,end_t+delay).
continuous allows repetition with optional end; finite requires positive duration.
Pulses do not persist forever. Final-state tick checks retain continuous arrivals
but never reconstruct expired finite windows. Transit/hibernation block capture;
arrival/wake allow revalidation. radio_coordinate_time provisionally adapts clock.t
as galactic coordinate seconds; game-coordinate-seconds-v1 persists the reference.
Negative offsets precede game t=0. Preparation does not reset physical start.
Source/receiver are stationary per check. Existing time consumers do not change;
separate proper time/biological ageing, relativity and moving sources are not
implemented. Pre-existing default cruise 1.0 ly/year remains technical debt against
subluminal canon, explicitly outside this phase's propulsion/travel scope.

Optional root radio_emitters in installed locations/arcs/singles reuses existing
host IDs/aliases/certificates, including exact procedural IDs. Each emission has
mode/start/end/channel and exactly one payload: inline EN/ES content, installed
piece_key or certified navigation_link_to. Valid complete JSON and finite examples
are in the physical contract and scene.json. piece_key requires reciprocal
radio_emission and one unambiguous radio channel; external mail keeps its marker.
Host binding retains candidates, constraints, weights, rolls, windows, deadlines
and interaction triggers. No proximity activation or incompatible guide rewrite;
general editorial review remains e5c.

Compiler errors identify file/entity/field for duplicate/absent/ambiguous IDs,
uncertified hosts, types, categories, versions, unknown fields, nonfinite/negative
power, inverted windows, ambiguous content and unbound tokens. Maximum 128
emissions per transmitter; offsets within ±10 million years. A derived power-tier
index visits up to 27 cells per tier and 128 candidates per tick, resuming with
persisted cursor. Incomplete is never absence. Budget-1 pagination survives load.
No galaxy walk, listening-induced generation or mutable global cache exists.
Pre-existing lore pool initialization can generate in normal ticks; a twin run
without radio proves listening adds none.

## Gameplay, lore and recovery

The shared spatial/operational, prepare/capture/retry/read APIs remain. Opportunity
metadata freezes without freezing sensitivity/range. Capture revalidates current
distance, time, health, electricity, dependencies, quality, Core OS, radiod and
context. Consumption/wear remain unchanged. pending produces no file/event/intel/
unlock/consumption; capture creates one file/event and commits the producer;
later reading/import applies intel. Canonical radio:<emission>/lore:<piece> IDs
prevent duplicate signals and a second queue.

Automatic retry listens to legitimate independent declarations. Piece references
still need scheduler preparation and dock/uplink/salvage; required docking remains
even with remote range. Non-radio channels retain gates/effects. Tests cover
unselected optional pieces and selected pieces waiting on each original trigger.

Every new local or remote F-DEAD-01 first reception requires an already declared navigation_link_to
notice, coverage and actual arrival. Conservatively only open-ended repetition
can confirm a plan awaiting repair/power activation. No retrospective activity,
corrective transmitter/station or false future rescue is created. Protected
primaries, reservations, directed access, widening and source rules remain.
The stage reuses radio:<id>, can bind pending content and cannot recapture a
received emission. Attempts/cooldowns commit only on capture. Saved emission,
sensitivity/context and preparation time validate original evidence without
confusing current location/health with original eligibility.

## Public demonstration and knowledge boundary

Group 15 installs only the isolated fixture in temporary data, then uses an
ordinary sandbox with public commands and no post-bootstrap resource/system/
position edits. ECHO_7 (0,0,0) receives RADIO_REMOTE (-3,4,0), 5 ly away. The
continuous signal started -315360000 s (-10 game-relative years); its delay is
157680000 s (5 years), arriving from -157680000 s. Commands power off security,
power off data_core, power on comms, boot radiod and five ordinary engine seconds
produce one SIGNAL_CAPTURED without scan. cat /logs/signals/0010.en.txt (or es)
then imports NODE/LINK. Save/load before/after does not duplicate. Both languages
run. Group 43 uses public drone repairs: LIMITED misses the station signal at
5 ly; NOMINAL captures it once during continuous listening, without another scan.
Pure formula probes are distinguished from these actual gameplay paths.

status/diag comms remain receiver-only. Negative tests vary hidden host/distance/
time/absence/pending content and protected arcs with observations constant.
CLI/Textual share EN/ES renderers. debug radio exposes budgets, distance, range,
emission/arrival and reasons; debug recovery includes first-emission metrics.
State pickle/RNG remain unchanged by both. C-DATA-004 is preserved.

## Persistence, validation and remaining decisions

V2/schema 3, checksums and backups remain. Safe unpickle defaults keep older
prepared opportunities local, without retroactive interstellar equipment or new undeclared stages.
Capture/read/timestamps persist. Save/load validates declarations/windows/index/
identity/ledger/plans; incompatible catalogue/configuration fails without rewriting.
Full content hash includes radio. physical_catalog_key strips only radio_emitters/
radio_emission from physical scope; without new data it matches the old hash.
Power changes catalogue/snapshot without changing manifest/IDs/stations/routes,
including requirement-bearing catalogues. Older snapshots fall back to catalog_key.
manifest.py, density and active narrative data remain untouched; AMANECER/templates
stay inactive.

Baseline **65/66 PASS**, e5b release **66/67 PASS**, provenance **67/68 PASS**, final persistence **68/69 PASS**; no new breakage. New invalidation checks have **8 groups**, provenance **18 groups**; radio has
**43 groups**; knowledge boundary **19**, F-DEAD-01 **36**, narrative **20**, prior
radio **18**. Manifest/worldgen, authored/catalogue, saves, navigation/intel,
CLI/REPL, Textual, audio and manuals pass. Internal paths and EN/ES pairing are
verified. git diff --check passes. The sole failure is radiation_hull_smoke.py:183,
AssertionError: [], CARNAVAL_34. Initial/final logs match byte-for-byte, SHA-256
`e54ccf0ca0e8da2081a1c8a338d71c8489f84a37c99f4a9c7eb9946dc582195b`. Neither its test nor physical code changes.
The serial runner retains failure exit status, never masking it. Full return codes,
durations and logs are in the evidence JSON. Baseline used the equivalent temporary
serial runner before changes; the versioned runner reproduces the release.

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/recovery_invalidation_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/recovery_provenance_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/knowledge_boundary_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/passive_communications_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_geography.py /tmp/retorno-radio-geography.json
/home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_validation.py /tmp/retorno-invalidation-release
git diff --check
```

| Release script | Result | Seconds |
| --- | --- | ---: |
| `audio_config_smoke.py` | PASS | 0.916 |
| `audio_runtime_notice_smoke.py` | PASS | 0.095 |
| `config_audio_smoke.py` | PASS | 0.270 |
| `contacts_sector_smoke.py` | PASS | 0.219 |
| `contacts_smoke.py` | PASS | 0.281 |
| `deadnode_chain_detours_smoke.py` | PASS | 4.383 |
| `deadnode_chain_planner_smoke.py` | PASS | 5.543 |
| `deadnode_cooldown_zero_smoke.py` | PASS | 0.687 |
| `deadnode_opportunity_selection_smoke.py` | PASS | 6.927 |
| `debug_add_commands_smoke.py` | PASS | 0.271 |
| `debug_galaxy_smoke.py` | PASS | 0.334 |
| `debug_lore_arcs_smoke.py` | PASS | 0.328 |
| `debug_worldgen_graph_smoke.py` | PASS | 0.304 |
| `drone_completion_context_smoke.py` | PASS | 0.634 |
| `drone_modular_v1_smoke.py` | PASS | 1.312 |
| `drone_recall_all_smoke.py` | PASS | 0.373 |
| `drone_salvage_survey_smoke.py` | PASS | 0.935 |
| `energy_policy_smoke.py` | PASS | 4.084 |
| `exploration_recovery_smoke.py` | PASS | 0.783 |
| `forced_hidden_ad_hoc_smoke.py` | PASS | 0.369 |
| `galaxy_physical_model_smoke.py` | PASS | 0.186 |
| `hibernate_radiation_wake_smoke.py` | PASS | 0.383 |
| `hibernate_sequence_assets_smoke.py` | PASS | 0.032 |
| `intel_recent_order_smoke.py` | PASS | 0.514 |
| `job_id_numbering_smoke.py` | PASS | 0.284 |
| `knowledge_boundary_smoke.py` | PASS | 12.786 |
| `known_routes_integrity_smoke.py` | PASS | 3.106 |
| `lore_channel_preference_and_unlock_smoke.py` | PASS | 0.250 |
| `lore_distance_from_start_smoke.py` | PASS | 0.188 |
| `lore_secondary_count_weights_hard_smoke.py` | PASS | 1.362 |
| `lore_smoke.py` | PASS | 0.206 |
| `mail_metadata_and_log_header_smoke.py` | PASS | 0.270 |
| `manuals_style_check.py` | PASS | 0.056 |
| `narrative_world_integration_smoke.py` | PASS | 23.473 |
| `nav_abort_waypoint_cleanup_smoke.py` | PASS | 4.685 |
| `nav_map_galaxy_dependencies_smoke.py` | PASS | 0.275 |
| `nav_map_galaxy_determinism_smoke.py` | PASS | 0.340 |
| `nav_map_galaxy_smoke.py` | PASS | 0.319 |
| `passive_communications_smoke.py` | PASS | 12.435 |
| `procedural_radiation_smoke.py` | PASS | 0.200 |
| `radiation_hull_smoke.py` | FAIL (historical) | 1.480 |
| `radio_spacetime_smoke.py` | PASS | 15.010 |
| `recovery_invalidation_smoke.py` | PASS | 10.397 |
| `recovery_provenance_smoke.py` | PASS | 6.520 |
| `route_hop_cap_smoke.py` | PASS | 0.302 |
| `route_solve_out_of_range_origins_smoke.py` | PASS | 0.475 |
| `save_load_smoke.py` | PASS | 0.408 |
| `scan_job_smoke.py` | PASS | 0.569 |
| `scan_observation_memory_smoke.py` | PASS | 13.335 |
| `sector_intel_validation_smoke.py` | PASS | 1.032 |
| `sensor_detection_factor_smoke.py` | PASS | 4.418 |
| `ship_layout_output_smoke.py` | PASS | 0.269 |
| `ship_survey_radiation_smoke.py` | PASS | 0.269 |
| `smoke_test.py` | PASS | 0.500 |
| `structural_recovery_smoke.py` | PASS | 38.653 |
| `textual_active_jobs_job_id_smoke.py` | PASS | 0.358 |
| `textual_command_spacing_smoke.py` | PASS | 3.580 |
| `textual_completion_context_smoke.py` | PASS | 1.745 |
| `textual_theme_smoke.py` | PASS | 3.754 |
| `transit_radiation_progression_smoke.py` | PASS | 0.205 |
| `uplink_authored_and_failsafe_smoke.py` | PASS | 0.742 |
| `uplink_once_per_node_smoke.py` | PASS | 0.463 |
| `uplink_only_delivery_retry_smoke.py` | PASS | 2.246 |
| `worldgen_manifest_integration_smoke.py` | PASS | 6.240 |
| `worldgen_manifest_prototype_smoke.py` | PASS | 3.314 |
| `worldgen_modules_pool_smoke.py` | PASS | 2.268 |
| `worldgen_preexistence_catalog_smoke.py` | PASS | 3.457 |
| `worldgen_preexistence_characterization_smoke.py` | PASS | 1.544 |
| `worldgen_sparse_archetypes_smoke.py` | PASS | 14.045 |

## Complete delivery inventory

- `data/manuals/commands/boot.en.txt`
- `data/manuals/commands/boot.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/canon/universo.md`
- `docs/design/modelo_temporal_hibernacion.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/narrative-world-contract.es.md`
- `docs/narrative-world-contract.md`
- `docs/systems/lore-scheduler.es.md`
- `docs/systems/lore-scheduler.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/radio-spacetime.es.md`
- `docs/systems/radio-spacetime.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/radio-spacetime-results.json`
- `docs/testing/radio-spacetime-review.es.md`
- `docs/testing/radio-spacetime-review.md`
- `src/retorno/cli/repl.py`
- `src/retorno/config/balance.py`
- `src/retorno/core/communications.py`
- `src/retorno/core/gamestate.py`
- `src/retorno/core/lore.py`
- `src/retorno/core/structural_recovery.py`
- `src/retorno/io/save_load.py`
- `src/retorno/model/world.py`
- `src/retorno/worldgen/generator.py`
- `src/retorno/worldgen/narrative.py`
- `src/retorno/worldgen/radio.py`
- `tests/fixtures/radio_world/piece.en.txt`
- `tests/fixtures/radio_world/piece.es.txt`
- `tests/fixtures/radio_world/scene.json`
- `tests/fixtures/recovery_legacy/README.es.md`
- `tests/fixtures/recovery_legacy/README.md`
- `tests/fixtures/recovery_legacy/pending-v1.dat`
- `tests/radio_spacetime_geography.py`
- `tests/radio_spacetime_smoke.py`
- `tests/radio_spacetime_validation.py`
- `tests/recovery_invalidation_smoke.py`
- `tests/recovery_provenance_smoke.py`
- `tests/structural_recovery_smoke.py`

ZIP/SHA-256 and per-file hash manifest accompany this report externally. No stage,
commit or push. Stopped for external review.
