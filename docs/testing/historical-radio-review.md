# RETORNO — B2 technical review

[Español](historical-radio-review.es.md).

Implemented for external review, 2026-11-07. No staging, commit or push was performed.

HEAD: `c705293679193f46de92785800ed055607cb1ba6`. Branch: `main`; upstream: `origin/main`.

## Result and contract

New games now have deterministic procedural radio history. Original equipment, conservation, energy, actual transmission windows and waves still propagating are separate. The existing physical model, authored compiler, scheduler and reception ledger remain the delivery authorities. The complete rules and probability/state table are in the [historical-radio-v1 contract](../systems/historical-radio.md).

The implementation uses one new pure kernel, `worldgen/historical_radio.py`, analogous to B1 information. It does not introduce another physics engine, catalogue of physical sites, receiver, ledger, navigation generator or recovery queue. `RadioEmitter`, `RadioEmission`, manifest inverse inventory, B1 records, common spatial/temporal gates, writer and canonical opportunities are reused. `bootstrap.py`, `generator.py`, `manifest.py`, `information.py` and `io/save_load.py` remain unchanged: existing bootstrap/validation hooks invoke the additive contract.

There is at most one procedural message per host. All five eligible classes have original equipment; current capability has the approved expected rates 40/65/50/10/5 percent. Independent conservation and energy samples produce those rates. A separate program draw preserves silent installations, intact unpowered hardware, powered damaged radios and historical messages from subsequently destroyed communications.

## Generator and provenance

The generator resolves a manifest identity, applies authored whole-host precedence, samples independent SHA-256 domains for coarse equipment/energy epochs and program existence, clips emission end to hardware/energy limits, then selects one bounded bilingual message. No player clock, visit order, known routes, mutable RNG or need for rescue enters selection. The @HR1 namespace cannot collide with editorial IDs. Repetition uses continuous windows; finite programs have an actual end. Periodic scheduling is future work.

The selected experimental profile has 55% program existence, 65% continuous programs and 30% navigation attempts. Navigation can only copy a certified B1 uplink or typed producer-owned archive record, retaining historical_connection versus navigation_solution and the 45 ly cap. Authored files that imitate B1 metadata remain testimony and cannot forge procedural radio provenance. Missing records produce environmental text, never a target chosen for progress. Eight environmental families cover beacon, telemetry, technical warning, distress, approach warning, unreadable route announcement, carrier test and damaged data.

## Measurement method

Twelve audit seeds: 0, 1, 2, 7, 42, 137, 2026, 65535, 271828, 314159, 8675309, 2147483647. A uses installed content; B removes arcs and singles; C also removes authored locations except UNKNOWN, RETORNO_SHIP and ECHO_7, matching B1 scenario definitions. Every sample is the complete 3×3×3 physical-sector cube [-10,20) ly on each axis, queried without gameplay materialization. This complete physical domain is larger than B1’s operational materialization sample; historical document yields are not claimed to be a same-denominator comparison.

Sparse/intermediate/abundant profiles change only program existence (30/55/80%). Equipment signatures and physical definitions are asserted equal between profiles. A and B produce identical equipment/history here; removing narrative packages changes no physical/information definition in this installed sample. C changes the authored physical definition and therefore universe scope and identities. Counts aggregate twelve separate universes, never one galaxy. Reception potential uses nominal sensitivity, t=0 and sampled site positions; actual new-game receipt count is zero while the receiver is off.

### Equipment, intermediate profile, A/B

| Class | Sites | Original | Retained | Damaged | Destroyed | Energy | Operational |
| --- | --- | --- | --- | --- | --- | --- | --- |
| station | 80 | 80 | 66 | 14 | 14 | 46 | 32 |
| relay | 73 | 73 | 67 | 7 | 6 | 58 | 48 |
| waystation | 62 | 62 | 51 | 10 | 11 | 46 | 31 |
| ship | 126 | 126 | 87 | 54 | 39 | 54 | 15 |
| derelict | 196 | 196 | 103 | 64 | 93 | 52 | 13 |

### Emission distribution by class, intermediate A/B

| Class | History | Continuous | Finite | Navigation | Ambient | Transmitting now |
| --- | --- | --- | --- | --- | --- | --- |
| station | 48 | 34 | 14 | 14 | 34 | 7 |
| relay | 40 | 25 | 15 | 16 | 24 | 13 |
| waystation | 32 | 21 | 11 | 10 | 22 | 7 |
| ship | 74 | 49 | 25 | 15 | 59 | 3 |
| derelict | 103 | 66 | 37 | 32 | 71 | 3 |

Retained means serviceable plus damaged, excluding destroyed hardware. Energy is independent of conservation. Operational capability does not equal current transmission, emission history or a receivable wave.

### Profile comparison

| Scenario | Profile | Sites | Programs | Active now | Nav / ambient | Reach sampled sites | Ended, still arriving | Validated recovery at host |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | sparse | 537 | 160 | 18 | 44 / 116 | 30 | 12 | 4 |
| A | intermediate | 537 | 297 | 33 | 87 / 210 | 60 | 27 | 11 |
| A | abundant | 537 | 425 | 47 | 119 / 306 | 86 | 39 | 14 |
| B | sparse | 537 | 160 | 18 | 44 / 116 | 30 | 12 | 4 |
| B | intermediate | 537 | 297 | 33 | 87 / 210 | 60 | 27 | 11 |
| B | abundant | 537 | 425 | 47 | 119 / 306 | 86 | 39 | 14 |
| C | sparse | 530 | 154 | 26 | 52 / 102 | 33 | 7 | 8 |
| C | intermediate | 530 | 288 | 43 | 98 / 190 | 61 | 18 | 15 |
| C | abundant | 530 | 410 | 57 | 128 / 282 | 81 | 24 | 17 |

The intermediate choice remains experimental: only 33/537 sites in A/B are transmitting at t=0, 87/297 programs carry navigation and 27 finished emissions can still reach sampled positions. Sparse gives fewer useful opportunities (4 validated at-host sources versus 11), while abundant increases them to 14 and increases current transmitters to 47. These measurements support retaining the middle hypothesis for review; they do not establish definitive balance or change the selected profile automatically.

### Twelve-seed detail, intermediate

| Seed | A/B sites | A/B programs | A/B near origin | A/B ended arriving | A/B recovery | C sites | C programs | C near origin | C recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 42 | 22 | 0 | 2 | 0 | 41 | 27 | 2 | 3 |
| 1 | 51 | 24 | 2 | 3 | 0 | 50 | 28 | 4 | 2 |
| 2 | 40 | 21 | 1 | 0 | 1 | 39 | 22 | 2 | 1 |
| 7 | 40 | 25 | 2 | 3 | 3 | 40 | 22 | 2 | 1 |
| 42 | 40 | 20 | 1 | 0 | 0 | 40 | 19 | 2 | 2 |
| 137 | 44 | 26 | 4 | 3 | 3 | 44 | 23 | 1 | 0 |
| 2026 | 48 | 27 | 1 | 1 | 1 | 46 | 21 | 0 | 1 |
| 65535 | 46 | 21 | 3 | 1 | 1 | 46 | 31 | 1 | 0 |
| 271828 | 46 | 28 | 1 | 4 | 0 | 45 | 24 | 3 | 0 |
| 314159 | 51 | 30 | 1 | 2 | 1 | 51 | 28 | 1 | 1 |
| 8675309 | 42 | 28 | 1 | 4 | 0 | 41 | 19 | 3 | 2 |
| 2147483647 | 47 | 25 | 1 | 4 | 1 | 47 | 24 | 0 | 2 |

## Time, space and recovery evidence

The existing inverse-square budget, three receiver sensitivities, Euclidean distance and light delay remain unchanged. Tests cover exact arrival/passage, finite and continuous windows, delayed post-destruction capture, moved receivers and long waits, stopped radiod, and saves before arrival and after receipt/read. Negative historical-time probes are controlled physics tests; public journeys never assign the clock. No travel or relativity model changes were needed.

F-DEAD-01 considers certified procedural payloads through the common resolver, up to 128 inspected radio hosts per search. A first notice must be accessible, arrived, in range and open-ended continuous, with the exact required LINK and narrative permission. First-stage unreceived-source rules remain. Later procedural receipts can be adopted without changing file, timestamp or capture count; this is tested on a two-radio chain. An authored file cannot forge B1 source fields, and an environmental signal cannot become a route.

Every candidate counted as validated recovery was checked by the real selector in an instrumented probe starting at its known source, not by turning a geometric count into a guarantee. Intermediate totals are A=11, B=11, C=15. These are conditional at-host opportunities, not effective escapes from the initial player position. No-source, exhausted-budget, protected-target, future and out-of-range cases remain conditional/incomplete. No transmitter, archive or route is invented for blockage.

## Independence, knowledge and persistence

All twelve seeds have saved invariance witnesses over opposite query/materialization order, clock, locale, knowledge, routes, counters and recovery context; queried state and global RNG remain byte-identical. Separate processes use PYTHONHASHSEED=0/137/987654321 for all twelve universes. The physical definition signature is unchanged by every profile/history query. B1 version and producer code are unchanged. The new kernel consults the certified inventory and existing B1 facts without making player observations.

One ledger distinguishes historical existence, physical eligibility, preparation, receipt, file, read/import and acquired intel. Procedural receipt events identify comms, use source-neutral filenames and omit internal opportunity IDs. Capturing alone grants no exact source position or navigation intel; environmental payloads disclose no host. Negative tests hold observations fixed and vary hidden data across public CLI, Textual, events and completion. Omniscient cache inspection is restricted to explicit read-only debug radio.

Schema 3 and V2 envelope remain. New definitions, local cursor/cache and actual receipt position/sensitivity persist; validation reconstructs the exact searched cache segment and certified payload. Tampered cursor, payload, identity, rules and impossible receipt evidence fail without overwriting existing slots. Old fixtures retain legacy radio and information rules without retrospective signals; no fixture was deleted. Some older synthetic matrices explicitly opt into legacy radio to isolate their original delivery assertions; B2 coexistence has its own live test.

## Public CLI and Textual journeys

CLI uses the ordinary parser/handlers and simulation loop, starting from the unmodified prologue with seed/locale as configuration. It repairs power/distribution, discovers and reaches ECHO_7, powers the drone bay after travel, repairs comms, boots radiod, listens, reads/imports real captured files, saves/restarts and continues with dock/datad/uplink. No debug command, resource grant, coordinate assignment or hidden destination decision is used. Snapshot reads record evidence only.

| Scenario | Locale | Commands | Game seconds | Procedural receipts | Read/imported | Reload/dedup |
| --- | --- | --- | --- | --- | --- | --- |
| A | en | 37 | 1311.0 | 3 | 3 | PASS |
| A | es | 37 | 1311.0 | 3 | 3 | PASS |
| B | en | 37 | 1311.0 | 3 | 3 | PASS |
| B | es | 37 | 1311.0 | 3 | 3 | PASS |
| C | en | 35 | 1311.0 | 2 | 2 | PASS |
| C | es | 35 | 1311.0 | 2 | 2 | PASS |

Textual additionally runs an actual keyboard-input journey in both languages, beginning from a saved untouched seed-42 prologue with only locale/headless-audio preferences configured. Drones complete real repairs; radiod captures three procedural messages; cat/import run through Input.Submitted. The public exit command persists, a fresh application loads, diag comms and ordinary ticks continue without duplicate receipts. Both runs use 22 commands and reach t=486 s. Controlled integration probes in the automated matrix remain labelled separately. CLI’s larger listening cube explains why its effective receipts are not the same quantity as nominal potential in the 27-sector measurement sample.

## Bounded discovery and cost

The local listening domain is a complete 7×7×7 cube for the current maximum 30 ly range. At most four physical sectors and 64 sites are inspected per tick, sharing the total 128 receiver-candidate budget with authored radio. Within-cell offsets retain crowded-cell candidates; a 260-host fixture exceeds 128 without omission or duplicate. Reception rotates over cached histories. A completed inventory fitting in cache is never rebuilt until cell change. At the 4096-history cap, checked cache windows rotate from the physical cursor; overflow sweeps revisit the domain fairly for future arrivals. A three-entry-cap test proves full candidate coverage, wraparound and save/load without permanent cell bias.

| Measurement | Result |
| --- | --- |
| Complete inventory pages | 86 |
| Retained histories / serialized local cache | 307 / 399595 bytes |
| Query peak with tracemalloc | 1260694 bytes |
| Traced page median / maximum | 190.83 / 549.57 ms |
| Untraced radio-only discovery median / max | 143.35 / 259.03 ms |
| Untraced completed-inventory radio median / max | 58.26 / 158.94 ms |

These are local instrumentation wall times, not a universal frame-time guarantee; tracing and shared host load affect them. The radio-only benchmark uses an explicitly configured healthy receiver and does not replace public gameplay evidence. It confirms unchanged materialized geography and player knowledge despite receipt. Save/load intentionally pays for bounded cache-window recertification. Extreme local density may hit capacity or delay discovery; short waves missed while paging are never received retrospectively.

## Regression and required test matrix

Baseline: 72/73 scripts pass. Final: 73/74 scripts pass, including all 27 new B2 groups. The only failure in each is the historical radiation_hull_smoke.py assertion at CARNAVAL_34: expected environmental radiation-level event absent. It remains a real failure, not an xfail or pass. Full logs and exit codes are retained. The serial wrapper needing an output argument is excluded as a wrapper; all smoke scripts, manual checker, manifest comparison and radio geography script run directly.

Coverage of the user’s 25 mandatory criteria maps to the new groups below and unchanged authored/common matrices. Numerical references are test_XX in historical_radio_smoke.py.

| Required criterion | New groups | Evidence |
| --- | --- | --- |
| 1–2 | 01–04 | Original equipment, conservation, energy, silent hosts |
| 3–6 | 03–07, 24 | Post-failure waves, continuous/finite, power, delay and windows |
| 7 | 08, 12–13 | Lazy unmaterialized sources and complete bounded domain |
| 8–12 | 08–10, 20 | Seed, time, order, hash seed, knowledge independence |
| 13–15 | 11, 14–15, 23 | Authored coexistence, primaries, canonical deduplication |
| 16–17 | 16–18, 22, 24 | Propagation saves, receipt reuse and no repeated capture |
| 18–19 | 18–19, 22, 26 | Certified procedural recovery and no valid source |
| 20 | 14–15, 25 | Negative disclosure, explicit read-only debug |
| 21–23 | 05, 08–09, 18–20, 26 | Unchanged B1/physics, no invented rescue route |
| 24–25 | 05, 12–13, 20–21, 25, 27 | EN/ES parity, actual Textual input, bounded performance |

Existing regression also covers worldgen, manifest, uplink, salvage, lore scheduler, navigation, structural recovery, deadnodes, save/load, CLI/Textual, audio and manuals. No UI layout or audio implementation changed. EN/ES manuals and corresponding technical documents are synchronized; existing help remains accurate because no public command or receiver gate changed. git diff --check is required by the final package verification.

## Files and review artifact

Production changes are confined to the historical radio kernel, balance parameters, additive WorldState/RadioOpportunity fields, new-world preparation, common communications, recovery source lookup and gated debug output. Test fixtures retain their earlier contract explicitly where appropriate; historical_radio_smoke.py adds 27 substantive groups. Documentation updates include paired historical radio contract/review, B1 boundary, radio/recovery references, roadmap and comms manuals. The review package contains complete new/modified files, binary tracked diff, per-file SHA-256 inventory, Git provenance, baseline/final logs, 108 measurement rows, profile benchmarks, twelve-seed invariance saves and public CLI/Textual transcripts/saves. No git mutation is needed to build it.

## Remaining risks and exceptional repair proposal

Probabilities and coarse ages remain experimental, not final survival balance or absolute chronology. Only one stationary-host message/program is modeled; there is no periodic calendar, electronics/civilization simulation, moving emitter or interference. Current silence does not prove no hardware or no historical wave. Paging, finite cache capacity and final-instant tick sampling can miss short opportunities; no absence or universal escape claim follows. Prolonged e6 audio/Textual campaigns remain separate from this completed B2 functional validation.

Future exceptional recovery should inspect retained versus irrecoverably destroyed equipment, energy and dependencies, a pre-existing B1 archive/payload, narrative permission and intervention eligibility. A persisted intervention would need a unique identity, cause, actual time, source record and newly initiated emission ID. Transmission may start only at/after intervention, with normal light delay and the same reception ledger. Recharging reserves, restarting or repairing radios is not implemented here and cannot rewrite prior history. No density, topology, propulsion, sensors, salvage odds, economy, resources, active arcs/singles, AMANECER, survival balance or general time model changed.

Work stops for external review with the working tree intentionally unstaged.
