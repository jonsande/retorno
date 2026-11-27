# PT001-07B — implementation and verification record

Date: 2026-11-27. The externally approved PT001-07A proposal was supplied as
developer text during this intervention and is now recorded in
[drone charging](../systems/drone-charging.md). Save schemas, general drone
maintenance, and the ship electrical design were not changed.

Decisions: `drone_charging.py` allocates power in sorted ID order and shares
the decision with the integrator and forecast. The bay retains its fixed draw.
Variable charging preserves exactly `1/90 kWh` per drone battery unit, scales
both power and rate with bay degradation, and uses the 25% SoC threshold for
additional reserve. Partial power uses small real surpluses or remaining
discharge capacity at a proportional rate; this makes 07A's joint limits
concrete. Electrical cuts at full drones and the SoC threshold do not repeat
maintenance, jobs, or narrative work.

Verification run from the repository root with
`/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_07b.py tests/test_electrical_proper_time.py tests/test_nav_electricity.py tests/test_nav_public_physical.py tests/test_nav_engine_wear_cut.py tests/test_nav_boundaries.py tests/drone_autorecall_reserve_smoke.py tests/drone_completion_context_smoke.py tests/drone_modular_v1_smoke.py tests/drone_recall_all_smoke.py tests/drone_recall_emergency_smoke.py` → **172 passed, 14 subtests passed** in 89.18 s.
- Direct execution of `tests/energy_policy_smoke.py`,
  `tests/drone_autorecall_reserve_smoke.py`,
  `tests/drone_completion_context_smoke.py`,
  `tests/drone_modular_v1_smoke.py`, `tests/drone_recall_all_smoke.py`, and
  `tests/drone_recall_emergency_smoke.py` with the project interpreter →
  **all passed**; autorecall ran 17 internal tests. Two scripts had direct
  maintenance calls to verify charging; those checks now call the owning
  electrical integrator.
- `git diff --check` → no errors.

New tests cover positive/negative net, SoC above/below/at the threshold,
partial surplus, stable crossing in both directions, discharge limits, bay
degradation, multiple-drone allocation, eligibility, full batteries,
efficiencies, proportionality, interval partitioning, relativistic transit,
and rollback when a pending physical boundary is skipped. The general suite
and extensive benchmarks were not run, as requested.

Limit: jobs and nonelectrical maintenance retain their galactic sampled
policy; this intervention does not reconstruct their transitions within an
ordinary interval. There was no deviation from 07A's calibration or threshold.

## PT001-07B-F — regulation and charging cuts

The synthetic pre-fix run reproduced a stale SoC-floor snap, charging power
after a drone had filled, and an unnecessary cut after the bay was shed. A
fourth initial failure was a test setup error (god mode is a derived property),
corrected before validation. Immediate load shedding now precedes charging
cuts. A timed quality shed splits the electrical interval at its actual
boundary; the effective allocation is recalculated for the remainder. The
main battery is snapped to the 25% floor only to remove roundoff after that
same regulated slice reached it. God mode never changes its stored energy.
The quality-shed timer still fires once per ordinary electrical interval.

Validation with `/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_07b.py tests/test_electrical_proper_time.py tests/test_nav_electricity.py tests/test_nav_public_physical.py tests/test_nav_engine_wear_cut.py tests/test_nav_boundaries.py` → **160 passed, 14 subtests passed** in 51.44 s, final code state.

The general suite and extensive benchmarks were not run. The approved charging
policy and calibration remain unchanged. **TEMP-01** is recorded as future work;
no time-base audit of other subsystems was implemented here.

The developer subsequently reported definitive PT001-07 general validation:
**677 tests and 169 subtests passed in 362.72 s**. This result was not
rerun during PT001-08.
