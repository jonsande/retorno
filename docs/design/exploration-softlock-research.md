# RETORNO — Pending investigation: exploration continuity and F-DEAD-01

[Español](exploration-softlock-research.es.md) · **Status: design objective awaiting validation**, 2026-11-07.

**Scope:** structural exploration deadlocks while the ship is capable of exploration. This document **does not** claim a universal guarantee, change gameplay, or authorize F-DEAD-01 level 2. Implementation claims refer to [`exploration_recovery.py`](../../src/retorno/core/exploration_recovery.py), [`structural_recovery.py`](../../src/retorno/core/structural_recovery.py), and the [current contract](../systems/structural-recovery.md). Outdated statements in [`exploration-failsafes.md`](../systems/exploration-failsafes.md) do not override the current contract.

## 1. Objective and definition

**Developer's desired objective:** no game should reach an *unintended structural exploration deadlock*. This is an **objective to investigate and establish**, not an implemented or verified property. It does not imply guaranteed victory, endless survival, advance knowledge of paths, universally connected historical topology, or removal of uncertainty.

A **structural exploration deadlock** occurs when, assuming a functional ship and usable exploration systems, the player has exhausted legitimately available ways to discover or reach new locations and there is no executable sequence of ordinary or permitted recovery actions capable of restoring exploration progress.

Distinguish the following:

- **No visible frontier:** no new opportunity is known. A symptom, **not proof** of an actual deadlock.
- **Potential frontier detected:** a route, contact, file, uplink, or clue appears pending. This does not prove *effective* progress.
- **Actual structural deadlock:** no legitimate usable procedure leads out of the current exploration region/state under the analysis conditions.
- **Operational/survival failure:** insufficient power, spares, fuel, health, drones, hull integrity, etc. Analyze separately. F-DEAD-01 must not grant fictitious resources to resolve these.
- **Deadnode:** a known or forced destination outside the reachable component and beyond local solving range; this need not mean all exploration is blocked.

Narrative progress blocked by an authored piece is distinct, although it may affect exploration frontiers. A player choosing not to use an available mechanism is not a structural deadlock.

## 2. How deadlocks can arise in the present universe

`historical-world-v1` fixes sites and topology before discovery but does **not** mandate universal connectivity (decision D04). Operational hops are capped at 45 light years; player knowledge is separate from site existence and physical links. A ship can exhaust its reachable region even with thousands of other sites elsewhere.

B1 (`historical-information-v1`) adds stable archives and uplink candidates; B2 (`historical-radio-v1`) adds emissions and propagating waves. **They increase opportunity without proving that a new clue is always available.** A scan can miss a site; an uplink can be exhausted or contain only known destinations; an archive can be environmental or inaccessible; a signal may have no `LINK` or fall outside reception power/time. Knowing two ends of a remote route does not necessarily provide access from the ship.

Investigate historically disconnected regions, exhausted reachable components, contacts requiring an unreachable `route solve` origin, depleted/non-navigational information sources, pending clues that open no new route, absent/out-of-range/expired radio signals, and search/retention limits. None of these in isolation proves irreversibility: legitimate options may remain unexamined.

## 3. What the current detector checks

[`has_exploration_frontier`](../../src/retorno/core/exploration_recovery.py) considers, among other things:

1. An active recovery plan or previously recovered intel that can supply a link.
2. Readable `NODE` records that permit a valid local solution.
3. Known routes to unvisited destinations.
4. Acquired contacts that permit `route solve` from a reachable origin within sensor range and hop cap.
5. Pending uplinks at reachable facilities.
6. Recoverable archives, pushes, and other pending information sources.
7. Received recovery clues not yet imported.

Global recovery is requested when no recognized frontier remains; the `is_exploration_capable` operational gate requires adequate power, nominal Core OS, at least limited sensors and running `sensord`, among other conditions, and no transit/hibernation. **Deadnode** tracking has separate thresholds and should not be conflated with global frontier detection.

**Potential false positives:** a pending file may contain no navigation, an uplink may point only to already known destinations, or an apparent frontier may not be executable. **Potential false negatives:** a legitimate opportunity may be overlooked across another mechanism, time, or position. Reproducible cases are needed; completeness must not be assumed.

## 4. What F-DEAD-01 level 1 offers and cannot guarantee

The structural selector uses certified historical sites and searches directed access chains. Its **first stage** requires a valid decodable historical navigation emission, continuous without an end; later legs require certified information sources from B1, radio B2, or known routes. The shared reception ledger is reused. The deadlock does not cause stations, physical edges, documents, or transmissions to be fabricated.

Search is progressive, paginated, and budget-limited (defaults: 16 physical sectors, 2048 sites, 4096 expansions, 65536 edge checks, plus source-specific limits). Results include `validated`, `conditional`, `none_in_scope`, `incomplete`, and `invalid`. **`none_in_scope` does not prove galaxy-wide absence of a route; `incomplete` is not absence.** Even a valid plan does not imply survival or that the player has read/imported and used the clue.

It is thus **not established** that level 1 prevents deadlocks in every game, or that its failures are frequent. Previous seed comparisons and public journeys demonstrate particular functions, not a universal property or systematic frontier-exhaustion runs.

## 5. Research before deciding on level 2

**Priority:** complete the authored-system review and run integral Textual/audio playthroughs, evaluating exploration continuity as part of those runs. Do not rebalance radio or implement exceptional repair without evidence.

Proposed protocol:

1. **Define a progress oracle** for controlled tests: legitimate actions, directed components, calculable routes, reachable contacts/information, real radio windows, and actual capacity to discover and visit a new site. A debug-only oracle may inspect the world; the public UI never may.
2. **Exercise diverse seeds and configurations**, with/without authored content and across density regimes. Record extended public journeys beyond the prologue and first discovery; complement with reproducible adversarial synthetic cases.
3. **Classify every apparent exhaustion**: ordinary progress possible, level-1 recovery validated and consumable, conditional plan, incomplete search, locally absent source, false frontier, failed activation, or proven structural deadlock.
4. **Follow the entire chain**: detection, selection, physically valid reception, read/import, new link/contact, travel, and further exploration. Receiving a message alone is not success.
5. **Keep failure modes separate**: evaluate structural reachability with functional equipment and sufficient resources; analyze survival and repair affordability elsewhere. Do not pass tests off as organic gameplay.
6. **Record metrics and counterexamples**: seed, rules/versions, starting state, reproducible action sequence, time/position, known component, exhausted sources, selector reason and budget, actual result, legitimate player knowledge, and smallest proposed fix.
7. **Re-run after changes**, checking determinism, save/load, `C-DATA-004` nondisclosure, no retroactive world creation, and authored protections.

### Evaluation criteria

- **Satisfactory:** a legitimate sequence allows continuation, normally or through level 1, without teleportation or invented resources.
- **Defect:** a reproducible structural deadlock occurs despite an opportunity the game should provide; fix detector/selection/distribution/provenance as indicated first.
- **Design gap:** no legitimate accessible source or provable level-1 plan exists in the case under examination; assess a canon-compatible structural remedy before physical intervention.
- **Insufficient evidence:** budget exhaustion, unresolved time/window, or incomplete test. Never count as universal guarantee or global impossibility.

Testing a finite seed set gives **empirical confidence**, not mathematical proof of “no game.” A strong guarantee would require an invariant of worldgen/recovery and tests of its assumptions, or a narrower formulation of the objective. Any tension between D04 (no universally connected historical graph), D08 (no guaranteed rescue), and desired exploration continuity must be resolved explicitly rather than silently altering canon.

## 6. Decision status and follow-up

| Item | Status |
| --- | --- |
| Aim to avoid unintended exploration deadlocks in every viable game | **Design objective, awaiting validation** |
| Level 1: certified historical recovery, B1 information, B2 radio | **Implemented, no proven universal guarantee** |
| Investigation of false frontiers and actual deadlocks | **Pending; incorporate into 4D-3e6** |
| Radio balancing | **Deferred** |
| F-DEAD-01 level 2: exceptional physical restart/repair | **Deferred; not implemented** |
| First authored content set and authoring-guide review | **Pending** |

The reserved level-2 design requires pre-existing historical sites and archives, minimal plausible persistent physical intervention, an actual new emission timestamp, and light-speed propagation; never retroactive emissions. **It is not enabled by default.** First establish a need that level 1 or a less intrusive correction cannot solve.

**Follow-up:** place future campaign evidence in `docs/testing/`, one report per campaign, linked from this document. Re-evaluate after integral validation. No experimental results are claimed before they exist.
