# TEMP-01A — Audit of temporal bases

Spanish counterpart: [temporal-bases-audit.es.md](temporal-bases-audit.es.md).
Diagnostic snapshot of the productive code at HEAD. No time rule, balance,
save, or test was changed. The [approved invariant](../development/system-contracts.md)
requires internal ship physics to use ship proper time; external processes use
their physically appropriate frame; biological time derives from proper time
and physiology. A galactic event timestamp is a record, not proof that the
underlying process should run on galactic seconds.

## Reading the inventory

`G` is `ClockState.t` (galactic coordinate seconds), `P` is
`ship_elapsed_s` (ship proper seconds), and `B` is `bio_elapsed_s`. `dt` in
`Engine.tick` and `GameLoop.advance_interval` is G; `proper_dt`/`dt_ship`
is P. **Correct** refers only to the examined temporal base; it does not
certify the complete physical model. **Incorrect** means the present base or
interval arithmetic contradicts the approved invariant. **Decision** means
the intended frame or gameplay semantics must first be approved.

All fields mentioned below are in `GameState` and are pickled by
[`save_single_slot`](../../src/retorno/io/save_load.py); only the automatic
worker's monotonic debt is runtime-only. Hibernation uses
[`_execute_hibernate`](../../src/retorno/cli/repl.py), which repeatedly calls
`GameLoop.advance_interval`; it does not suspend onboard subsystems. Public
physical navigation uses an isolated staged transaction in `Engine.tick`,
[`_physical_limit_selection`](../../src/retorno/core/engine.py) and
[`select_next_boundary`](../../src/retorno/core/nav_coordinator.py). That
coordinator currently accepts proper limits and **galactic** job limits only.
Ordinary `_tick_interval` still makes one job/narrative/maintenance pass for
its G interval; electrical subdivision does not repeat those passes.

## Inventory: clocks, motion, electricity and wear

| Process and responsible code | Current base and evidence; required base | Durations, causal boundary, hibernation/navigation, persistence | Assessment |
| --- | --- | --- | --- |
| Automatic scheduling: [`GameLoop._run`](../../src/retorno/runtime/loop.py) | Host monotonic active time schedules requests; committed `clock.t` is subtracted from debt. Required: monotonic for wall scheduling, G for requested coordinate advance. | `tick_s` and `_auto_debt_s` are runtime seconds; bounded catch-up yields. Pause, manual advance, hibernation, error and close discard debt; no saved debt. | Correct. |
| Galactic/proper/biological clocks: [`Engine._tick_interval`, `_tick_physical_segment`](../../src/retorno/core/engine.py), [`temporal.py`](../../src/retorno/core/temporal.py) | Ordinary/legacy motion computes `dt_ship` from frozen speed; physical segments integrate analytic proper time; B increments from P with cryostasis factor. Required: G for coordinate motion, P for onboard, B for ageing. | Saved `t`, `ship_elapsed_s`, `bio_elapsed_s`, `last_dt`; physical segment start and elapsed G/P are saved in [`nav_state.py`](../../src/retorno/core/nav_state.py). Phase/arrival boundaries and atomic rollback apply during hibernation too. | Correct for clocks; physiological modulation is separately reviewed below. |
| Motion, arrival and propulsion: [`nav_physics.py`](../../src/retorno/core/nav_physics.py), [`Engine.next_physical_step`, `_tick_nominal_physical_travel`, `_tick_inertial`](../../src/retorno/core/engine.py) | Position and phase durations use G; proper acceleration and onboard elapsed use P. Required: the same two frames, related by trajectory. | Saved segment G duration, proper endpoints, frozen fuel receipts; legacy local travel saves `transit_start_t`/`arrival_t` in G. Segment, braking, recovery and arrival cuts precede commit; hibernation uses them. | Correct temporal basis. |
| Main battery, generation/load and drone charge: [`Engine._integrate_power_interval`, `_integrate_power_slice`](../../src/retorno/core/engine.py), [`nav_electricity.py`](../../src/retorno/core/nav_electricity.py), [`drone_charging.py`](../../src/retorno/core/drone_charging.py) | kW/kWh integrate over P; charging allocation uses proper seconds and shared power decision. Required: P for onboard energy. | Saved energy, power quality, drone battery; cuts at empty/full, 25% charging reserve, drone full and changed supply. Recomputed after shedding, including during hibernation/physical transit; forecast invalidation and staged rollback apply. | Correct. |
| Electrical regulation timers: [`Engine._integrate_power_slice`](../../src/retorno/core/engine.py), [`power_limits`](../../src/retorno/core/nav_electricity.py) | `low_q_shed_timer_s` and `brownout_sustained_s` gain P. Required: P for ship electronics. | Both float counters saved; quality, SoC, timed shed and sustained brownout are proper limits converted to G for physical motion. Hibernation does not change rate. | Correct. |
| System and hull ageing: [`Engine._apply_degradation`, `_apply_hull_degradation`](../../src/retorno/core/engine.py), [`ordinary_wear_rate`](../../src/retorno/core/nav_boundaries.py), [`integrated_system_wear`](../../src/retorno/core/nav_radiation.py) | Health/hull loss uses P, including moving/stationary arrival legs; physical path integrates quality and radiation over P. Required: P for onboard material wear. | Saved `health`/`hull_integrity`; physical health thresholds and hull-zero are causal cuts, with forecasts invalidated by changed conditions. Ordinary path still samples conditions at coarse interval ends; hibernation retains that behavior. | Correct base; ordinary sampling resolution remains a separate limitation. |
| Power-bus instability alert: [`Engine._update_alerts`, `_physical_limit_selection`](../../src/retorno/core/engine.py) | `clock.t >= Balance.BUS_INSTABILITY_AFTER_S` is an absolute G time since game start, not a duration of damaged distribution. If it denotes internal deterioration, required base is P while damaged; if a scripted world milestone, G may be intentional. | Absolute constant and saved alert; physical G boundary at the constant; evaluated during hibernation. No saved elapsed-damage timer. | Decision; likely misleading as an equipment timer. |

## Inventory: survival, exposure and hibernation

| Process and responsible code | Current base and evidence; required base | Durations, causal boundary, hibernation/navigation, persistence | Assessment |
| --- | --- | --- | --- |
| Spatial ambient field and hull/internal exposure: [`Engine._compute_env_radiation_rad_per_s`](../../src/retorno/core/engine.py), [`integrate_segment_radiation`](../../src/retorno/core/nav_radiation.py) | Physical transit samples ambient by position on a G-parametrized trajectory and integrates onboard dose/hull coupling over P. Legacy travel samples radiation at advanced G position. Required: spatial field in its source frame, onboard exposure in P; the meaning of configured `rad_per_s` under relativistic motion is not fully specified. | Saved ambient rate, hull and levels; physical spatial/radiological limits and hibernation wake threshold, with rollback on unresolved cuts. | Decision for external-field frame/relativistic flux; onboard integration base is correct. |
| Drone dose: [`Engine._apply_radiation`, `_tick_physical_segment`](../../src/retorno/core/engine.py) | Non-docked drone dose uses `env_rad * shield_factor * dt` where `dt` is G, even for an internal deployed drone in physical transit. Required: onboard drone P; a drone left at a world node needs its own local frame and exposure. | Saved `dose_rad`; physical path supplies integrated galactic ambient dose divided by G, then multiplies by G; dose-level events occur at interval end, without a drone-dose cut. Hibernation does not suppress it. | Incorrect for onboard drones; external drones require a frame decision. |
| Biological ageing: [`biological_time_interval`](../../src/retorno/core/temporal.py), both engine clock integrators | B = P times 1 awake or fixed `HIBERNATION_BIO_AGE_RATE_NOMINAL` in cryostasis. Required: derive from P, modulated by actual physiology and cryostasis. | Saved `bio_elapsed_s` and `is_hibernating`; no physiological-state integration or biological threshold cuts. Hibernation toggles the flag and advances B. | Decision: the P/cryostasis relation is correct, but physiological modulation remains unimplemented. |
| Life-support viability grace and terminal lock: [`Engine._apply_critical_system_consequences`](../../src/retorno/core/engine.py) | `life_support_offline_s += dt` with G in ordinary and physical paths. Required: at least onboard P for loss of ship environment; whether the viability limit should be B or a separate physiological exposure integral needs approval. | Saved float counter, reset on restored service; checked only at interval end, without a dedicated physical grace-expiry cut. Hibernation advances it at G rate; physical path rejects some offline starting states rather than model the transition. | Incorrect base; exact physiological criterion is a decision. |
| Hibernation duration and wake policy: [`_execute_hibernate`, `_hibernate_interrupt_reason`, `_hibernate_transit_env_threshold_dt`](../../src/retorno/cli/repl.py) | Requested `years * YEAR_S`, remaining and actual years use G; wake checks include critical events, battery and spatial radiation. Required frame for the *requested duration* is ambiguous: ship/crew elapsed P or external arrival/calendar G. Wake predicates use their underlying subsystem's proper frame. | No persistent request timer: active flag, clocks and start/end events are saved; chunks, physical phase/arrival cuts and emergency stops are honored. Technical causal blocks retain committed time/events and leave auto time paused. | Decision on requested-years semantics; existing physical wake boundaries remain valid. |
| Alert age and event dates: [`Engine._make_event`, `_ensure_alert`, `_update_alert_timers`](../../src/retorno/core/engine.py) | Event/first/last-seen dates use G, appropriate as common chronology. `unacked_s += int(dt)` loses every subsecond interval. Required: G chronology for records; a cumulative elapsed counter must retain fractional G time before display rounding. | Saved integer dates and `unacked_s`; no causal threshold; hibernation and short physical cuts expose truncation. | Incorrect counter arithmetic, although G event timestamps are correct. |

## Inventory: services, work, drones and sensors

| Process and responsible code | Current base and evidence; required base | Durations, causal boundary, hibernation/navigation, persistence | Assessment |
| --- | --- | --- | --- |
| All queued/running work: [`Engine._process_jobs`, `_advance_job_timers`, `_physical_limit_selection`](../../src/retorno/core/engine.py), [`Job`](../../src/retorno/model/jobs.py), [`job_limits`](../../src/retorno/core/nav_boundaries.py) | `Job.eta_s` is a **relative remaining float**, decremented by G `dt`; physical forecasts label it `TemporalLimit(..., "galactic", eta_s)`. Most work is onboard and requires P. External actors may need another local frame. | Saved ETA/status/queue/owner/params, not an absolute completion date. Physical path cuts at G ETA and resolves effects once; ordinary path passes the full interval per job and may finish at its end. Hibernation runs jobs. `nav_coordinator` only accepts G job limits. | Incorrect for onboard work. No absolute galactic job deadline was found; changing the scheduler and limit domain, not merely renaming `eta_s`, is required. |
| Service boot and operation: [`Engine.apply_action` BOOT_SERVICE, `_apply_job_effect`](../../src/retorno/core/engine.py), [`ServiceState`](../../src/retorno/model/systems.py) | `boot_time_s` enters a G-decremented job. `is_running` is a persistent state, not a per-second process; active electrical draw and wear already use P. Required: P for startup and onboard operation. | Saved service flag and boot job; physical job cut currently G, and hibernation completes startup at that rate. Power/dependency changes interrupt or block the job. | Incorrect startup; steady operation's timed energy/wear is correct. |
| Computer/data work and ship repairs: [`Engine.apply_action`, `_enqueue_job`, `_apply_job_effect`, `_maybe_fail_emergency_job`](../../src/retorno/core/engine.py) | Route solve, auth recovery, cargo audit, module operations, system/self-test repair and salvage work share G ETA. Emergency failure probability uses `p_fail_per_s * interval.dt_s` with G. Required: P for onboard computation, machinery and hazard exposure; an external salvage agent needs its local frame. | Saved job ETA, risk, reserved materials and outcomes; physical completion cut exists but in G, risk/effect resolved once. Hibernation runs it; ordinary large intervals may postpone completion. RNG seed also includes `clock.t`, so domain changes affect deterministic outcomes. | Incorrect onboard durations/risk; external work requires a decision. |
| Drone movement/tasks and per-action battery debit: [`Engine.apply_action`, `_drone_job_battery_cost`, `_apply_job_effect`](../../src/retorno/core/engine.py) | Deployment, movement, recall, survey, salvage, drone repair/install/reboot use G job ETA. Fixed battery cost is charged at outcomes, not per second. Required: P for movement inside the ship; world-node operations need the drone's local proper frame. Fixed per-operation costs need no rate conversion. | Saved location, battery, job ETA and materials; physical job boundary currently G; hibernation progresses work. Rework must keep single debit and arrival/recall order. | Incorrect for onboard durations; external-drone clock requires a decision. |
| Deployed idle drain and autorecall reserve: [`Engine.tick`, `_update_drone_maintenance`, `_drone_return_reserve`](../../src/retorno/core/engine.py) | Idle drain uses G `dt`; forecast reserve multiplies G ETA by a per-second rate. Required: P for a drone moving with the ship, external local time for a drone left behind. | Saved battery/autorecall flags and jobs; ordinary `Engine.tick` cuts at projected reserve/ETA, physical path has a special single internal-drone check; hibernation keeps draining. Cuts and reserve equations must migrate together. | Incorrect onboard; external frame is undecided. |
| Drone integrity, bay decontamination and passive repair: [`Engine._update_drone_maintenance`](../../src/retorno/core/engine.py) | Deployed integrity loss and docked decontamination use G `dt`; bay repair consumes one scrap/roll per **call**, with gain independent of elapsed duration. Required: P for docked/onboard hardware, external local time for a remote drone. | Saved integrity/dose/cargo/RNG counter; no dedicated maintenance completion cut; physical path calls maintenance once per slice and ordinary path once per outer tick. Hibernation chunk size can change repair cost/roll count. | Incorrect onboard time base; passive-repair cadence/economics also require a separate design decision. |
| Sensors, scan and route solve: [`Engine.apply_action` Scan/RouteSolve, `_perform_scan`](../../src/retorno/core/engine.py) | Sensor job ETAs use G via common scheduler. Scan observation and acquired-intel `t=clock.t` are G records, correctly. Required: P for onboard scan/compute duration; external light-time or moving-target effects are currently outside the model. | Saved job, scan observation, RNG counter and acquired intel; physical cut currently G; scan materializes sectors at completion, so changing cut can change what is observed. Hibernation completes scans; no automatic scan tick. | Incorrect job duration; record timestamps are correct. |

## Inventory: external world, radio and other temporal records

| Process and responsible code | Current base and evidence; required base | Durations, causal boundary, hibernation/navigation, persistence | Assessment |
| --- | --- | --- | --- |
| Authored/procedural radio emissions and propagation: [`radio_coordinate_time`, `radio_link_metrics`, `radio_temporal_block_reason`](../../src/retorno/core/communications.py), [`RadioHistory.equipment_at`](../../src/retorno/worldgen/historical_radio.py) | Source `start_t/end_t`, equipment epochs and `distance_ly * YEAR_S` use provisional G coordinate time. Required: emission in transmitter frame and propagation in a compatible spacetime coordinate; stationary sources fit current approximation. A moving transmitter would need another model. | Absolute windows/equipment times, source history and radio definition persisted in `WorldState`; physical motion changes receiver position. Reception checks at ticks/arrival/wake, not continuous trajectory cuts; hibernation blocks receiver. | Correct for the explicitly stationary provisional model; moving-source extension requires a decision. |
| Receiver capture, retry and ledger: [`retry_radio_opportunities`, `capture_radio_opportunity`](../../src/retorno/core/communications.py) | Eligibility is checked at current G and position; `prepared_t`/`received_t`/`read_t` are G records. Required: arrival in coordinate frame; receiver electronics operate onboard in P, but no separate receive-duration rate is modeled. | Saved pending/received ledger, cursor and intel; finite windows can pass entirely inside a long advance, while continuous signals survive later checks. Hibernation and legacy transit gate reception; physical path retries at causal slices. | Decision whether finite-window capture needs a causal arrival/expiry cut or remains sampled gameplay policy. |
| Radio discovery work budget: [`discover_radio_opportunities`](../../src/retorno/core/communications.py), [`query_local`](../../src/retorno/worldgen/historical_radio.py) | Candidate pages advance per eligible retry/tick, not by elapsed physical seconds. Required: a bounded technical search, with no implied universe-time rate. | Search cursors persist; long hibernation/physical cuts can change opportunities to run the search, while the same certified emissions remain. No independent causal deadline. | Correct as a work budget, not a physical evolution rate. |
| Narrative placement and delivery: [`run_lore_scheduler_tick`, `_deadline_reached`, `_soft_force_roll`](../../src/retorno/core/lore.py) | Non-forced cadence and `max_year` use G; event/dock/uplink/salvage counters are interaction counts. Required: calendar G only if this is world/editorial scheduling; onboard processing or crew experience would need P/B. | Saved `next_non_forced_eval_t`, `eval_seq`, placements, pools and delivery timestamps; physical path cuts at next G evaluation, ordinary path evaluates at interval end; hibernation runs it. Placement may certify new world knowledge, so no retroactive reroll. | Decision on narrative/calendar semantics and whether elapsed evaluations within a large interval need their own transactional cuts. |
| Dead-node evolution and recovery cooldown: [`evaluate_dead_nodes`](../../src/retorno/core/deadnodes.py), [`structural_recovery.on_capture`](../../src/retorno/core/structural_recovery.py) | `stuck_since_t`, `dead_since_t`, `last_action_t` and year thresholds use G; uplink thresholds use counts. Required: external node's local ageing/operations; G is plausible for stationary nodes in the provisional inertial frame, but remote clocks/causes are not specified. | Saved tracker, attempts, plans and radio receipts; evaluated on triggers rather than at a global causal deadline; hibernation may cross years before next trigger. Recovery stages are interaction-driven, not timed jobs. | Decision for external local frame and event timing; no evidence that these should use ship P. |
| Static sector/node generation, salvage inventory and recovery planning: [`ensure_sector_generated`](../../src/retorno/worldgen/generator.py), [`confirm_recovery`](../../src/retorno/core/structural_recovery.py) | Deterministic seed/query or interaction, not a continuously advancing time integral. Node-pool `initialized_t`/`window_closed_t` and recovery `created_t` are G records. Required: no rate conversion unless future physical evolution is specified. | Generated sectors, knowledge, inventories and plans persist; scan/arrival/action and lore/radio triggers materialize them. Physical transaction protects in-transit writes; hibernation can trigger scheduled lore, not autonomous node wear. | Correct as static/triggered data; future evolving nodes need a separate design. |
| Inventory manifest, mail/intel and event provenance: [`Engine._apply_job_effect` CARGO_AUDIT](../../src/retorno/core/engine.py), [`register_mail`](../../src/retorno/model/os.py), [`record_intel`](../../src/retorno/model/world.py) | Audit duration is the G job defect above; `manifest_last_sync_t`, mail receipt, intel and event `t` are G record dates. Required: P for work, G for common historical timestamps. | Saved records and acquired knowledge; no independent timed integral after the triggering job/action. Hibernation preserves acquisition order. | Correct timestamps, incorrect audit-job duration. |

Textual refresh timers and audio/narrative playback delays are host-wall-time
presentation controls, not `Engine.tick` processes; this audit leaves them
unchanged. `RiskProfile.p_glitch_per_s` is stored/configured but has no
productive per-second consumer in the inspected engine; only
`p_fail_per_s` enters `_maybe_fail_emergency_job`.

## Confirmed problems, uncertainties and dependencies

1. **Shared job scheduler is the main dependency.** All onboard ETAs are
   decremented by G and forecast as G, including boot, computation, scan,
   repair and drone work. `eta_s` is relative, not an absolute galactic date;
   `arrival_t`, radio windows and `next_non_forced_eval_t` *are* absolute G
   values. A later implementation must carry a time-domain tag or separate
   typed limits and convert P completion to G through the active trajectory.
2. **Onboard drone maintenance and viability are inconsistent.** Idle drain,
   dose, integrity, decontamination and life-support grace use G; charging
   alone already uses P. Bay repair additionally charges one scrap/RNG roll
   per call, so changing only its `dt` would not make long and short intervals
   equivalent. Drone-world exposure, viability's physiological threshold and
   passive-repair economics require explicit decisions.
3. **Records are not rates.** G timestamps on events, scan observations,
   mail, intel and manifests should remain G even if the producing work moves
   to P. Alert `unacked_s` is a separate cumulative-counter defect caused by
   per-tick truncation. The global bus alert constant needs a semantic owner.
4. **External time is not universally ship G.** Static historical emitters
   use a provisional common coordinate; moving transmitters, external drones
   and evolving remote nodes may require their own local proper times or a
   spacetime model. Narrative year gates may be editorial rather than physical.

## Proposed small, dependency-ordered interventions

1. **TEMP-01B: typed time domains and deterministic job conversion.** Approve
   the domain of each `JobType`, then introduce explicit remaining-duration
   domains and proper-to-G boundary conversion in the shared scheduler and
   `nav_coordinator`. Keep `Job.eta_s` and queue/order semantics stable until
   tests demonstrate arrival/phase, hibernation and partial-boundary behavior.
   Verify short/long interval equivalence, atomic rollback, save/reload of
   current-version mid-job states, and unchanged single fuel/material debit.
2. **TEMP-01C: onboard jobs and service/sensor effects.** Move approved
   onboard boot, computer, scan, repairs and their emergency risk to P using
   the shared mechanism. Revalidate electrical job load, service availability,
   scan position/knowledge and deterministic RNG at completion. Avoid repeating
   jobs, narrative, radio or RNG when electricity subdivides an interval.
3. **TEMP-01D: drone clocks and maintenance.** First decide the frame of
   remote drones and passive bay repair's per-time economics. Then migrate
   onboard movement/idle drain/reserve/dose/integrity/decontamination together;
   integrate resource/RNG repair at explicit proper-time opportunities. Preserve
   07B charging energy and rescue cut ordering.
4. **TEMP-01E: survival and records.** Decide whether life-support grace is
   equipment P, physiological B or an exposure integral; add its causal cut
   and hibernation/physical validation. Separately accumulate fractional alert
   age without changing event G timestamps. Decide bus-alert semantics before
   altering its absolute threshold.
5. **TEMP-01F: external clocks and narrative.** Approve whether lore year
   gates are calendar/editorial and whether finite radio windows must cut a
   physical advance. Only then adjust external-node, moving-emitter or remote
   drone models as warranted; preserve certified radio provenance, acquired
   knowledge and deterministic world generation.

The order is a proposal, not authorization to implement. Each phase needs
focused EN/ES specification and tests for causal atomicity, hibernation
throughput, current-version persistence, energy conservation, and knowledge
non-disclosure. Older-save migration is not required for these experimental
phases; valid saves produced by the resulting current version must reload.

## Validation of this audit

Code and owning specifications were read; no tests, general suite or benchmark
were run. The definitive PT001-01/09-B suite result supplied for this record is
**727 tests and 169 subtests passed in 461.08 s**; it is not a TEMP-01A run.

## TEMP-01B preflight: ordinary-job causal blocker

**Status: blocked before implementation.** The requested shared P/G job scheduler
cannot guarantee causal completion across all active routes without a broader
ordinary-integrator change. This is the explicit stop condition of TEMP-01B;
no production job, save format, or test was changed in this intervention.

[`Engine._tick_interval`](../../src/retorno/core/engine.py) advances G/P/B
clocks for the entire requested interval, performs any legacy arrival, then
calls `_process_jobs(state, dt)` once. That routine visits jobs in historical
order, subtracts the whole G interval from each `eta_s`, and resolves effects
only at the end. [`GameLoop.advance_interval`](../../src/retorno/runtime/loop.py)
does not cut an ordinary interval at job completion (except when explicitly
stopping at legacy arrival). For example, a running 2 s job in a 10 s rest
tick completes and records its effect at G+10; ten 1 s ticks can complete it
at G+2. An arrival between those instants changes the location and the order
of arrival/job effects. Changing only the ETA debit to P, or forecasting its
boundary in `job_limits`, would leave this inconsistency intact.

The physical path does stage state and select causal limits, but
[`job_limits`](../../src/retorno/core/nav_boundaries.py) and
[`select_next_boundary`](../../src/retorno/core/nav_coordinator.py) currently
require G job limits; the latter rejects a P job limit. A complete change
would need to slice ordinary intervals at eligible job and arrival limits,
convert each remaining P ETA to G along the active motion, then commit the
corresponding clocks, effects, risk, electrical load, and records in their
actual order. It must preserve simultaneous-limit resolution, job order,
partial progress and rollback without replaying maintenance, lore, or RNG.
That integration and transactional ordering exceeds the bounded TEMP-01B
domain-field/conversion change. The physical-only portion is therefore not
introduced in isolation. Hibernation uses `advance_interval`, so it shares
the blocker. In the current version, all productive jobs still use G.

### Proposed domain matrix for all 24 JobType values

`P` means ship proper time for work physically aboard. `L` means the local
time of an external actor or work site, **not automatically ship G**; no
independent L clock exists yet. `P/L` requires the execution location to be
fixed or tracked. All rows remain implemented as G until a later migration.
The matrix classifies the *work duration*; event timestamps remain G.

| JobType | Proposed domain | Location, owner, or execution-context dependency / pending decision |
| --- | --- | --- |
| `REPAIR_SYSTEM` | P/L | Drone operator and ship-system target; confirm whether an external operator is possible and which clock governs it. |
| `REPAIR_DRONE` | P/L | Drone operator and target must be colocated; use P aboard, decide external actor clock elsewhere. |
| `SELFTEST_REPAIR` | P | Ship system self-test; no external owner. |
| `BOOT_SERVICE` | P | Ship service startup; ship context. |
| `DEPLOY_DRONE` | P | Starts with a docked drone and uses bay timing; destination may be a ship sector or external node. |
| `MOVE_DRONE` | P/L | Drone and destination may be inside the ship or at a world node; decide at enqueue and on relocation. |
| `DOCK` | Decision | Ship/external-node manoeuvre; choose the physical duration frame before migration. |
| `UNDOCK` | Decision | Ship/external-node manoeuvre; choose the physical duration frame before migration. |
| `SALVAGE` | Decision | Enum value has no productive enqueue/effect in the inspected engine; define semantics before assigning a clock. |
| `INSTALL_MODULE` | P | Ship module installation; onboard work context. |
| `UNINSTALL_MODULE` | P | Ship module removal; onboard work context. |
| `DRONE_INSTALL_MODULE` | P/L | Drone operator/location and module target determine onboard versus external work. |
| `DRONE_UNINSTALL_MODULE` | P/L | Drone operator/location and module target determine onboard versus external work. |
| `REBOOT_DRONE` | P/L | Disabled drone may be in bay or outside; bay equipment and drone owner clocks need a decision. |
| `SALVAGE_SCRAP` | L | Drone at a world node; external actor/site clock needs definition. |
| `SALVAGE_MODULE` | L | Drone at a world node; external actor/site clock needs definition. |
| `SALVAGE_DATA` | L | Drone at a world node; external actor/site clock needs definition. |
| `SURVEY_DRONE` | L | Drone and world node; decide actor versus site clock. |
| `SALVAGE_DRONE` | L | Drone and world node; decide actor versus site clock. |
| `ROUTE_SOLVE` | P | Ship computer work; onboard service context. |
| `SCAN` | P | Ship sensor work; onboard service context. |
| `RECALL_DRONE` | P/L | External return plus bay recovery; decide whether to split phases or use actor/site clock. |
| `CARGO_AUDIT` | P | Ship manifest computation; onboard service context. |
| `RECOVER_AUTH` | P | Ship OS authorization recovery; onboard service context. |

Before retrying TEMP-01B, approve the ordinary-integrator slicing and
transactional scope as a separate design step. A narrow acceptance probe
should first show identical completion times and single effects for 10×1 s
and 1×10 s at rest, then for legacy arrival, phase transitions and P jobs in
physical transit. No external actor clocks or productive migrations belong
to that prerequisite.
