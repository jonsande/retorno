# NAV-BRAKE-01B3H-D2B1-R1 — First playtest correction report

## Initial state and evidence

- Branch: `feature/nav-brake`; initial HEAD:
  `7f9f2fe7832d2773be7f40941218b4acc76c75d4`.
- `PT001-02-blocked.dat`, `PT001-02-blocked_002.dat`,
  `PT001-02-second-block.dat`, and
  `~/.retorno/users/playtest-d2b1/savegame.dat` were available. The original
  saves were never written. Reproductions loaded copies in memory and wrote
  the continued save to `/tmp/nav_r1_continued.dat`.
  The active profile and second copy have the same SHA-256:
  `ccdbb1c54f1ca0bcc1263f608de515a3c4c7faa755ef5a2247c4f5401785b8a6`.
- An unrelated change in `TODO.md` and untracked D2B1 artifacts
  (`INFORME.md`, `MANIFEST.sha256`, `RECORRIDO-D2B1.txt`, `changes.diff`) were
  already present. They were preserved; the R1 archive contains this phase's
  changes.

## Reproduction and root causes

**PT001-01.** One second of travel from the second real save took a median
**0.304 s** of processing at the initial HEAD; the lock was held for
**0.304 s**. `next_physical_step()` copied the whole state once and the nominal
`Engine.tick()` path chained three more copies. Four copies cost **0.203 s**;
boundary selection cost **0.010 s**. The ordinary rest control tick cost
**0.068 s**. Standard `cProfile` identified the copies as the main cost and
radio discovery as secondary. There was no evidence that sound caused the
delay. The loop also slept a full second *before* processing each tick, giving
a measured **1.380 s** between starts. Its sleep ignored stopping until it
woke and could start an extra tick after `stop()`.

**PT001-02A.** Both saved states reproduced
`Physical segment interval has an unresolved causal boundary` before the fix.
In `PT001-02-second-block.dat`, galactic time was `609444.539 s` and the
requested chunk was `604800 s`. Clock subtraction rounded the coordinated
step to `604799.9999999999 s`. The coordinator selected
`1214244.5389999999 s`, with only `requested_horizon`, no `deferred` and no
earlier cause. The integrator produced `1214244.539 s`, **one ULP** later
(`2.3283064365386963e-10 s`). The strict comparison
`selected.at_galactic_s < end.galactic_s` rejected it. The prediction and
execution zero-time preliminaries selected the same horizon, power quality
`1.0`, battery `5.0 kWh`, no active work and no preliminary events. Execution
also retries radio reception, but it produced no event during hibernation in
this save. A full battery, radio and seven-day chunks did not cause the fault.

In `PT001-02-blocked.dat`, `JOB35` was a queued deployment started after the
first failure. Forecast activation set a real boundary at **13 s**, which was
resolved once; the later rejection was the same seven-day horizon rounding.
The work did not cause the original hibernation failure. Waking after seven
days or after one second reflected the starting state of each request, not a
fixed chunk-size limitation.

**PT001-02B.** `_execute_hibernate()` restored time with
`was_auto and not woke_early`, so any early wake disabled the loop, even when
the event was legitimate and the ship could continue. Saving and loading
started another loop; that restored clocks without fixing the hibernation
rejection.

## Corrections and guarantees

- `Engine.tick()` retains one full transactional state copy and the forecast
  retains a separate read-only copy. Internal nominal segments work on the
  already provisional transaction; direct calls to the internal methods
  still create their own transaction. Top-level owner identity, rollback,
  events, RNG state and single fuel payment remain intact.
- Endpoint validation accepts differences of at most **four ULPs**, matching
  the coincidence rule already used by `select_next_boundary()`. The
  integrator still determines position and clocks. Truly earlier causes
  still stop or cut the interval; a work completion halfway through the
  interval verifies this.
- Automatic advancement uses interruptible monotonic deadlines. An overrun
  skips missed deadlines and executes only one tick per iteration, without
  bursts or changes in game seconds per tick.
- Normal and legitimate early wakes restore the prior automatic-time policy,
  except in terminal states. Deliberate pauses remain paused. A still
  unresolved technical boundary leaves automatic time stopped to avoid an
  error loop, and the localized EN/ES warning says so. Compatible work can
  progress after a legitimate wake.

Ordinary wear, power, drones, narrative and radio remain active. Balance,
fuel and physical parameters were not changed.

## Comparable measurement

Five repetitions per case, median monotonic-clock time, reloading
`PT001-02-second-block.dat` for each sample. Baseline code was extracted from
HEAD to `/tmp/nav_r1_baseline`; the same interpreter, data and
[`nav_r1_benchmark.py`](../../tests/nav_r1_benchmark.py) script were used.
Raw results: [`MEDICIONES-R1.json`](../../MEDICIONES-R1.json). Cadence used
[`nav_r1_cadence.py`](../../tests/nav_r1_cadence.py) and five automatic ticks.

| Measure | Before | After |
| --- | ---: | ---: |
| Ordinary rest tick | 0.068 s | 0.070 s |
| `next_physical_step(1 s)` | 0.055 s | 0.058 s |
| Physical `Engine.tick(1 s)` | 0.241 s | 0.148 s |
| Public one-second physical advance | 0.304 s | 0.208 s |
| Lock held during that advance | 0.304 s | 0.208 s |
| Deep copies / total cost | 4 / 0.203 s | 2 / 0.110 s |
| Total boundary selection | 0.010 s | 0.008 s |
| Median between automatic ticks | 1.380 s | 1.000 s |

Public physical advance improved by about **32%**. Automatic cadence returned
to the scheduled one-second period on this machine. A lock occupation of
about 0.208 s can still briefly delay the UI; strict real-time behavior under
higher CPU load is not guaranteed.

## Continuing the real save

From a copy of `PT001-02-second-block.dat`, the same handler used by
`hibernate until_arrival` advanced **26.502413447782804 game years** and
recorded one arrival at that seed's physical destination identifier (session
alias: `P-1.1.0.0`). Initial state: galactic time `609444.539 s`, beta
`0.002019859901703708`, distance traveled `183339158801.09335 m`, and
`10.40581506308498` capsules. Final state: galactic time
`836389555.0282785 s`, proper time `753898345.6323009 s`, no physical
transit, and the same `10.40581506308498` capsules. Two system-state changes
and one arrival occurred, with no propulsion emergency. The result was saved
and loaded successfully at `/tmp/nav_r1_continued.dat`. Health, fuel, drones,
universe, wear settings and clocks were not modified for this continuation.
The loop policy at wake was `[False, True]`.

The first save also advances a week: `JOB35` completes once, followed by
warnings and a drone disablement during that interval. Those are consequences
of the deployment in that copy, not technical blocks or evidence that the
first failure was caused by the drone.

From two equivalent loads of the second copy, ten one-second ticks and one
ten-second interval ended with the same galactic time (`609454.539 s`), proper
time (`609454.1272231016 s`), distance (`183345214238.74057 m`), beta
(`0.0020198932579090917`), fuel and events. `clock.last_dt` differs by design:
1 s versus 10 s.

To continue the original profile under the corrected version, close the old
session with `exit` if it is still open, then run from the repository:

```bash
RETORNO_SCENARIO=PROLOGUE PYTHONPATH=src \
  ../retorno_venv/bin/python -m retorno.ui_textual.app \
  --user playtest-d2b1
```

Load the existing game; do **not** use `--new-game`. Then run
`hibernate until_arrival` and confirm. A legitimate wake keeps automatic
advancement enabled if it was enabled before sleep. The one restart applies
the new code to the old process; no restart is needed after a legitimate wake
in the corrected session.

## Validation, files and limits

New regressions in `tests/test_nav_playtest_r1.py` cover rounding, a real
boundary, rollback, copy counts, wake policies, work progress and cadence
under overrun. The mock in `tests/test_nav_engine_nominal.py` was adjusted
to accept the new private call signature.

Product files: `src/retorno/core/engine.py`, `src/retorno/runtime/loop.py`,
`src/retorno/cli/repl.py`. EN/ES documentation: `docs/systems/nav-physics.md`,
`docs/systems/nav-physics.es.md`, this report and its Spanish counterpart.
Reproduction tools: `tests/nav_r1_benchmark.py`, `tests/nav_r1_cadence.py`,
`MEDICIONES-R1.json`.

Final tests: the directed D2B1/D2A/D1/coordinator/recovery set had
**116 passed in 134.04 s**; additional interruption, inertia, repair and
safety regressions had **105 passed in 112.22 s**; the complete R1 file after
adding time-policy cases had **11 passed in 11.15 s**.
`tests/textual_nav_d2b1_smoke.py` finished with
`TEXTUAL NAV D2B1 SMOKE PASSED`. `py_compile` and `git diff --check` passed.
Command syntax and diegetic content did not change, so manuals and `help`
were not edited; the new player warning is complete in EN/ES.

Limits: transaction optimization targets nominal travel; exceptional inertia
and recovery paths retain nested copies. Secondary radio cost remains. A
genuinely unsupported technical boundary still stops time with a warning.
D2B2 and new maneuvers remain out of scope. No general old-save migration was
added.

Expected final Git state: branch `feature/nav-brake`, initial HEAD unchanged,
six tracked R1 files modified and six new R1 files; `TODO.md` and four prior
D2B1 artifacts remain and are excluded from the R1 archive. No commit or push
was made. The review archive is verified at the end.
