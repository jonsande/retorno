# RETORNO — 4D-3e4b technical review report

Date: 2026-11-06, Europe/Madrid. [Español](passive-communications-review.es.md).
Implemented for **external review**, without staging, commit or push.

## Baseline and scope

Initial/final HEAD: `78676dbfce5e7b98db36b2e241a427a19b0632fe`; branch main, upstream origin/main.
Remote was queried and matched at the start. Initial worktree was clean; e4 was
already integrated. The ZIP includes all changed/new files of this e4b phase,
not the previous delivery. Nothing is staged; files remain local for review.

AGENTS, navigation/recovery contract, roadmap v1.2, canon, scheduler, failsafes,
discovery/intel and e4 report were read. Bootstrap, models, dependencies, power,
deterioration, jobs, repair, events, REPL, Textual adapter, audio and saves were
audited. General balance, worldgen, five active singles, inactive templates,
AMANECER and audio are unchanged. Textual changes only display shared status lines.

## Audited defects and correction

Previously deliver_captured_signal, deliver_station_broadcast and write_local_intel
wrote without a receiver. _deliver_piece counted signals, and assigned delivery
consumed piece/pool on success. Gateway set dock_hint_delivered on writing;
deadnodes immediately advanced attempts/last_action_t. Recovery created nodes,
seeded files and advanced generation/counters before distinguishing reception.

A single persistent radio opportunity now separates these transitions. Public
writers prepare/capture through the common predicate; raw file writing is private
to capture and non-radio channels. Lore, pool, applicable signal_count, gateway
flag and deadnode attempt/cooldown commit only after actual capture. Blocked
reception creates no successful file/event, intel, unlock or consumption.
Reading/import remains a separate transition.

Old boot completion could mark a daemon running after its owner was powered off.
Installation, identity, health, forced power-off, dependencies and electrical
gates are now revalidated during execution and when applying the result.
Power-off stops the owning service immediately. Legacy sensord boot may still
activate initially OFFLINE sensors without forced shutdown; radiod requires
active hardware. Existing cancellation/failure finalizers are reused.

## Hardware, service and gates

comms is a ShipSystem in existing BRG-01, initial health 0.90, forced OFFLINE,
priority 4. It requires effectively powered NOMINAL energy_distribution.
Nominal load is 0.15 kW, LIMITED 0.12, UPGRADED 0.165; CRUISE retains the full
state load. The actual battery difference is tested. Deterioration reuses
data_core coefficients: base 8.5e-11/s, k_power 0.30, k_rad 0.10, with normal
global wear factors and ordinary drone repair. There are no free repairs or
changes to another system's load.

radiod is comms' installed, initially stopped ServiceState, with a 5 s boot.
It depends on neither sensors/sensord nor data_core/datad. requires_active_owner
expresses the gate within the existing daemon infrastructure. Power/repair do
not start the service. LIMITED/NOMINAL/UPGRADED receive deterministically;
lower states cannot. Health, dependencies, Core OS, terminal, Q>=0.55,
brownout, actual electrical capacity and no transit/hibernation are checked.
No RNG, random interference or automatic restart is introduced.

## Persistent ledger, source and commit

RadioOpportunity persists identity, channel, source, host, original trigger,
dock requirement, frozen EN/ES content, minimal producer metadata, preparation
time, status, path, received language/time and read time. IDs are
lore:<piece_key>, recovery:<generation>:gateway and deadnode:<target>:<attempt>;
the local API accepts explicit IDs or stable digests. Recovery has no second queue.

States are pending → received → read_imported. The last means the player
accessed content, not necessarily useful intel. Available content is retained
even when a legacy API froze only ES and capture occurs in EN, or vice versa;
lore freezes both languages with existing fallback semantics.

Ticks retry after power/wear/consequences. The host must still exist and be
current. Lore prepared by dock/uplink/salvage retains docking there; proximity
or arrival does not manufacture its trigger. Existing gateway broadcasts allow
local arrival without a new dock. Legacy stage identity, protection and physical
hint hops are rechecked. Travel suspends capture; return allows retry. No emitter
or galactic coverage is invented. Persistent local availability is the current
minimum, without emitter energy evolution or electromagnetic expiry simulation.

Capture and bookkeeping are synchronous in memory. Repeated triggers/ticks or
loading received entries cannot duplicate files/events/signal_count/logs/unlocks.
Action counters retain their prior semantics; retries count no extra dock/uplink/
salvage. Legacy signals acquire no new counter that would change deadlines.
File primaries remain locked until valid reading/import.

## Reviewed producers and consumers

| Producer/consumer | Before | After and commit point |
| --- | --- | --- |
| Lore captured_signal | Direct file/event/signal_count at trigger. | Frozen opportunity, radio plus host/dock; commit_radio_delivery updates log/counter/pool/delivered after capture. |
| Lore station_broadcast | Direct file/event at dock. | Common opportunity, radio, local hub and docking; no proximity shortcut. |
| deliver_captured_signal / deliver_station_broadcast | Ungated writers. | Delegate to gated write_local_intel; blocked calls return empty paths without files. |
| Radio write_local_intel | Always wrote. | Stable opportunity/capture; None/None while pending. |
| Internal lore mail / internal deliver_ship_mail | Internal delivery without radio. | Preserved channel/envelope/consumption. |
| Explicit external mail | No active marker or specific gate. | Piece mail_origin=external, API external_origin or external SourceRef use radio while retaining mail; no inference from prose/senders. |
| Initial recovery hint: scan/route/dock/uplink/hibernate | Created entry/gateway and delivered according to trigger. | Deferred before node fabrication, without generation, success counters, files or fictitious receipt. |
| Legacy external hibernation cache | Presented as CORE.OS mail after chain creation. | Also deferred; never treated as free internal mail. |
| Existing-chain gateway | Wrote/committed at arrival without a receiver. | Local generation/gateway opportunity; dock_hint_path/delivered committed only on capture. |
| New indirect deadnode | Created bridge and counted attempt. | Deferred without existing bridge; tracker can observe thresholds without consuming delivery. |
| Existing bridge/direct deadnode stage | Immediate file and attempt/cooldown. | Frozen origin/stage, cap/protection/radio; attempt/timestamp only after capture. |
| Salvage piece/pool and drone job | Mounting distinct from reading. | Preserved without radiod; actual e4/drone regressions. |
| Public uplink / uplink_only | data_core/datad, docking, power and valid LINK. | Preserved without radio; deferred recovery is not counted as success. |
| Uplink_trace local writer | Its writer boundary did not validate the channel. | Checks uplink_blocked_reason, including installed/running datad; no radio. |
| cat / mail read / intel import | Parser applied valid intel after access. | Preserved; marks read_imported once after successful access. |
| status / diag / help / Textual | No receiver or pending entries. | EN/ES names, gates and counts, without secret source/target/content or new intel. |
| Bootstrap and mounted authored files | Initial local files or physical archive recovery. | Preserved; not reinterpreted as live external radio reception. |

## Legacy recovery and e5 boundary

The order authorizes deferral when reception preparation requires inseparable
physical mutation. Global activation needed fabricated entry and possibly
gateway; deadnodes created its first bridge. New activations no longer invoke
those creators. recovery_activation_deferred persists, with generic diagnostics.
Legacy helpers and structural selection/policies remain for subsequent work;
no new planner integration or corrective historical stations were introduced.

**Material consequence:** structural blockage may lack automatic rescue until
e5. Previously prepared chains remain consumable through valid channels.
F-DEAD-01 is neither implemented nor validated and no universal exit is promised.
Old tests demanding node creation were explicitly adapted to the new contract,
without silently granting a running receiver.

## Persistence and compatibility

V2/schema 3 remain. WorldState supplies empty ledger/flag defaults; ServiceState
restores the new flag as false for old services. After catalog/universe
validation, earlier saves lacking comms receive the same installed, OFFLINE
bootstrap system. No energy, resources, repairs, activation or intel are granted.
Original and backup bytes remain identical when loading. Tests cover genuinely
absent old slot fields, pending, boot in progress, received/read_imported,
repetition after load and EN↔ES changes. The e4 snapshot remains mandatory.

## Public experience and localization

Existing power/boot/jobs/repair machinery is used. Notices inspect live service
ownership/dependencies and distinguish stopped/uninstalled/blocked, with localized
name, ID and effective boot command or diag. They do not repeat every tick or on
power on of already active hardware. EN/ES help/manuals are updated. CLI and
Textual share renderers/state; no new panel or sound. Existing receipt event
types remain.

Real prologue, seed 701, without health/scrap/power/RNG overrides:

```text
power off security
power off data_core
drone deploy D1 PWR-A1
drone repair D1 power_core   (three ordinary attempts)
drone move D1 BUS-A2
drone repair D1 energy_distribution   (two ordinary attempts)
power on comms
boot radiod
```

Outcome: t=256 s, scrap=52, Q≈0.711, comms NOMINAL and running radiod.
Ordinary repair can fail under its unchanged policy; failure is neither removed
nor replaced by free success. The flow reaches reception with resources left.
New groups also exercise cat, mail read, intel import, power off and cancellation
through public parsers/actions. No manual audiovisual e6 session was performed;
Textual regressions run headlessly.

## Tests and results

Canonical interpreter only: /home/jon/prog/retorno_case/retorno_venv/bin/python;
PYTHONPATH=src:repo, temporary saves and project script runners, no pytest.
Baseline: **61/62 PASS**. Final serial: **62/63 PASS**, including **18 new groups**
and **20 e4 groups** (18 originals plus the two focal corrections).
Manual style, EN/ES pairs, added links, AST/JSON and git diff --check: PASS.

The 18 new groups cover hardware/prologue/load/battery; boot loss/removal/
uninstallation/dependency/brownout/cancellation/health; state and service
independence; pending/captured/read lore; local coverage and no early dock;
repair; non-radio and external mail; saves/old defaults; deferral/existing gateway;
deadnode cooldown; CLI/Textual/notices; RNG/physics invariance; public flow without
overrides; frozen bilingual content; live blocked gates; external lore mail
read via mail read; protected/physical target rechecks; boot persistence.

The production comparator ran seeds 0–7,29,271828. Aggregate, rows,
resource_totals, configuration_key, method, algorithm, patches and seeds match
docs/testing/manifest-integration-measurements.json exactly. Benchmark times/
memory are observational; the witness was not rewritten. This complements scan,
observation memory, sensors, topology and resource regressions.

The sole failure is radiation_hull_smoke.py:183, AssertionError: [], fixture
CARNAVAL_34, also present at baseline. No unrelated radiation fix was made.
Textual, service/power/repair, lore/intel, recovery/deadnode and save regressions
pass. The theme test passes in the serial delivery run.

| Script | Result | Seconds |
| --- | --- | --- |
| `audio_config_smoke.py` | PASS | 1.24 |
| `audio_runtime_notice_smoke.py` | PASS | 0.07 |
| `config_audio_smoke.py` | PASS | 0.21 |
| `contacts_sector_smoke.py` | PASS | 0.18 |
| `contacts_smoke.py` | PASS | 0.29 |
| `deadnode_chain_detours_smoke.py` | PASS | 3.47 |
| `deadnode_chain_planner_smoke.py` | PASS | 4.26 |
| `deadnode_cooldown_zero_smoke.py` | PASS | 0.52 |
| `deadnode_opportunity_selection_smoke.py` | PASS | 4.95 |
| `debug_add_commands_smoke.py` | PASS | 0.22 |
| `debug_galaxy_smoke.py` | PASS | 0.27 |
| `debug_lore_arcs_smoke.py` | PASS | 0.27 |
| `debug_worldgen_graph_smoke.py` | PASS | 0.25 |
| `drone_completion_context_smoke.py` | PASS | 0.21 |
| `drone_modular_v1_smoke.py` | PASS | 1.0 |
| `drone_recall_all_smoke.py` | PASS | 0.24 |
| `drone_salvage_survey_smoke.py` | PASS | 0.7 |
| `energy_policy_smoke.py` | PASS | 3.12 |
| `exploration_recovery_smoke.py` | PASS | 0.5 |
| `forced_hidden_ad_hoc_smoke.py` | PASS | 0.29 |
| `galaxy_physical_model_smoke.py` | PASS | 0.15 |
| `hibernate_radiation_wake_smoke.py` | PASS | 0.29 |
| `hibernate_sequence_assets_smoke.py` | PASS | 0.03 |
| `intel_recent_order_smoke.py` | PASS | 0.43 |
| `job_id_numbering_smoke.py` | PASS | 0.21 |
| `known_routes_integrity_smoke.py` | PASS | 2.25 |
| `lore_channel_preference_and_unlock_smoke.py` | PASS | 0.2 |
| `lore_distance_from_start_smoke.py` | PASS | 0.15 |
| `lore_secondary_count_weights_hard_smoke.py` | PASS | 1.08 |
| `lore_smoke.py` | PASS | 0.17 |
| `mail_metadata_and_log_header_smoke.py` | PASS | 0.22 |
| `narrative_world_integration_smoke.py` | PASS | 18.86 |
| `nav_abort_waypoint_cleanup_smoke.py` | PASS | 3.61 |
| `nav_map_galaxy_dependencies_smoke.py` | PASS | 0.22 |
| `nav_map_galaxy_determinism_smoke.py` | PASS | 0.27 |
| `nav_map_galaxy_smoke.py` | PASS | 0.26 |
| `passive_communications_smoke.py` | PASS | 8.16 |
| `procedural_radiation_smoke.py` | PASS | 0.17 |
| `radiation_hull_smoke.py` | FAIL previo / preexisting | 1.09 |
| `route_hop_cap_smoke.py` | PASS | 0.24 |
| `route_solve_out_of_range_origins_smoke.py` | PASS | 0.35 |
| `save_load_smoke.py` | PASS | 0.32 |
| `scan_job_smoke.py` | PASS | 0.44 |
| `scan_observation_memory_smoke.py` | PASS | 10.66 |
| `sector_intel_validation_smoke.py` | PASS | 0.79 |
| `sensor_detection_factor_smoke.py` | PASS | 3.56 |
| `ship_layout_output_smoke.py` | PASS | 0.23 |
| `ship_survey_radiation_smoke.py` | PASS | 0.23 |
| `smoke_test.py` | PASS | 0.34 |
| `textual_active_jobs_job_id_smoke.py` | PASS | 0.24 |
| `textual_command_spacing_smoke.py` | PASS | 3.65 |
| `textual_completion_context_smoke.py` | PASS | 1.95 |
| `textual_theme_smoke.py` | PASS | 3.77 |
| `transit_radiation_progression_smoke.py` | PASS | 0.17 |
| `uplink_authored_and_failsafe_smoke.py` | PASS | 0.53 |
| `uplink_once_per_node_smoke.py` | PASS | 0.36 |
| `uplink_only_delivery_retry_smoke.py` | PASS | 1.71 |
| `worldgen_manifest_integration_smoke.py` | PASS | 5.1 |
| `worldgen_manifest_prototype_smoke.py` | PASS | 2.84 |
| `worldgen_modules_pool_smoke.py` | PASS | 1.68 |
| `worldgen_preexistence_catalog_smoke.py` | PASS | 1.99 |
| `worldgen_preexistence_characterization_smoke.py` | PASS | 0.71 |
| `worldgen_sparse_archetypes_smoke.py` | PASS | 10.12 |

## Documentation, pending decisions and delivery

New EN/ES technical contract and comms manual; updated boot/power manuals/help.
Navigation-recovery separates implemented behavior from historical audit;
scheduler/failsafes/discovery references record reception/deferral. Roadmap v1.3
records the explicit e4b-before-e5 agreement; all 24 Spanish D01–D24 rows remain
byte-identical to HEAD. Its English counterpart is added. Canon is untouched.

Pending: final load/wear/upgraded-state balance, reduced range, emitter expiry/
windows, latency, interference/intermittency, interstellar communications and
e5 structural recovery. No transmission, chat, transponder, combat or universal
event manager was developed.

Review ZIP: ../RETORNO-4D-3e4b-review.zip, all 39 changed/new files of this
phase, relative paths, without saves, .git, temporary or unchanged files.
Exact inventory, bytes and each member's CRC are verified. SHA-256 is in the
adjacent .zip.sha256 and handoff. ZIP remains outside the repository; reports
and JSON evidence are included.

## File inventory

| File | Purpose |
| --- | --- |
| `data/manuals/commands/boot.en.txt` | Updated EN/ES diegetic manual. |
| `data/manuals/commands/boot.es.txt` | Updated EN/ES diegetic manual. |
| `data/manuals/commands/power.en.txt` | Updated EN/ES diegetic manual. |
| `data/manuals/commands/power.es.txt` | Updated EN/ES diegetic manual. |
| `data/manuals/systems/comms.en.txt` | Updated EN/ES diegetic manual. |
| `data/manuals/systems/comms.es.txt` | Updated EN/ES diegetic manual. |
| `docs/design/navigation-recovery-contract.es.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/design/navigation-recovery-contract.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/design/roadmap-worldgen-lore-f-dead01.es.md` | EN/ES roadmap v1.3; e4b before e5, D01–D24 preserved. |
| `docs/design/roadmap-worldgen-lore-f-dead01.md` | EN/ES roadmap v1.3; e4b before e5, D01–D24 preserved. |
| `docs/systems/discovery-navigation-intel.es.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/systems/discovery-navigation-intel.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/systems/exploration-failsafes.es.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/systems/exploration-failsafes.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/systems/lore-scheduler.es.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/systems/lore-scheduler.md` | EN/ES update distinguishing implemented, historical and pending behavior. |
| `docs/systems/passive-communications.es.md` | Implemented EN/ES technical contract. |
| `docs/systems/passive-communications.md` | Implemented EN/ES technical contract. |
| `docs/testing/passive-communications-review.es.md` | EN/ES external technical review report. |
| `docs/testing/passive-communications-review.md` | EN/ES external technical review report. |
| `docs/testing/passive-communications-test-results.json` | Baseline/final evidence, new groups and procedural comparison. |
| `src/retorno/bootstrap.py` | Installs powered-off comms through the shared factory. |
| `src/retorno/cli/repl.py` | EN/ES help/diagnostics/notices and reading/import markers. |
| `src/retorno/core/communications.py` | Physical predicate, common ledger, capture/retry/reading and EN/ES diagnostics. |
| `src/retorno/core/deadnodes.py` | No new bridges; gated/idempotent existing stages. |
| `src/retorno/core/engine.py` | Revalidated boot, service stop on power-off, actual load, notices and retries. |
| `src/retorno/core/exploration_recovery.py` | Legacy creation deferral and broadcasts from existing chains. |
| `src/retorno/core/lore.py` | Gated writers, frozen content, producer commits after reception. |
| `src/retorno/io/save_load.py` | Safe additive default for schema 3 without comms. |
| `src/retorno/model/ship_layout.py` | Places comms in existing BRG-01. |
| `src/retorno/model/systems.py` | Physical factory, service flag, EN/ES names and load defaults. |
| `src/retorno/model/world.py` | RadioOpportunity and persistent collection/flag. |
| `src/retorno/ui_textual/presenter.py` | Adds shared status lines without a new panel. |
| `tests/deadnode_cooldown_zero_smoke.py` | Preserves zero/positive boundaries using an existing bridge and receiver. |
| `tests/exploration_recovery_smoke.py` | Verifies deferral and consumption of an existing chain. |
| `tests/known_routes_integrity_smoke.py` | Invalid frontier does not produce fictitious corrective activation. |
| `tests/narrative_world_integration_smoke.py` | Operational local receiver fixture for the same 20 e4 groups. |
| `tests/passive_communications_smoke.py` | 18 integration groups for this phase. |
| `tests/uplink_authored_and_failsafe_smoke.py` | Uplink retains its contract without counting deferred recovery as success. |

Work stops for external review without git add, commit or push.
