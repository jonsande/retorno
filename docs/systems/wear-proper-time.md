# T-04B2 — ordinary system and hull wear in proper time

Implemented on `main` from `1b963ea` (T-04A, T-04B1, CANON v0.6.0).
Owning code: `src/retorno/core/engine.py`, specifically `_tick_interval`,
`_apply_degradation` and `_apply_hull_degradation`. Relativistic intervals
continue to come exclusively from `core/temporal.py`.

Ordinary `ShipSystem.health` loss and ordinary hull ageing now use ship proper
seconds. Rest uses the galactic interval; transit uses the already frozen speed
and clock interval, never a speed recomputed from current engine health. The
existing local-speed rule also feeds that clock calculation. No additional
velocity multiplier is applied. All configured base rates remain unchanged,
now interpreted per proper second for these two ageing routines.

The existing modifiers are preserved:

- System `k_power` quality penalty and `k_rad` normalized internal radiation.
- Sustained-brownout multipliers for power_core and energy_distribution.
- NORMAL transit system wear multiplier; CRUISE retains its existing modifier.
- Hull ambient-radiation modifier and its existing transit-or-hibernation factor.
- Existing health bands, state locks, forced isolation, god-mode protections,
  and ordinary engine health/module transitions.

At arrival the implementation reuses T-04B1's moving and stationary durations.
After the moving electrical segment, before arrival/jobs, it retains that
segment's final power quality, sustained-brownout Boolean, operating mode,
ambient-radiation point sample and hull-filtered internal sample. The second
sample uses the final stationary electrical state and final ambient/internal
readings. Wear is then applied in chronological segment order at its original
stage, after jobs, narrative and electrical integration. Explicit sampled
transit/mode arguments preserve the moving wear modifiers even though the
live ship has arrived. The stationary remainder is applied only when positive;
at exact arrival there is no extra wear pass for a zero-length remainder.

Without arrival there is one ordinary wear pass using the total proper interval
and the same end-of-electrical-interval quality/brownout/environment samples as
before. Brownout persistence is already onboard seconds under T-04B1. No timer
or electricity formula is modified here. Health transitions are still emitted
at the enclosing tick's galactic timestamp. Deterioration affects later
operations; it does not retroactively recalculate this tick's electricity,
frozen speed, arrival timestamp or proper clock interval. A reactor derated by
ordinary wear is sampled by the following tick's electrical generation.

Sampling remains deliberately coarse:

- Each segment uses its final quality and sustained-brownout condition for its
  whole duration. Threshold crossings inside that segment are not reconstructed.
- Jobs/repairs retain their existing galactic scheduling before the wear stage;
  completion times and intermediate health states are not replayed. Wear applies
  to the systems available at that stage, with their existing rates/coefficients.
- Environmental radiation remains a point sample. The existing interpolation
  reads the enclosing tick's advanced clock; at/crossing arrival it clamps to
  destination radiation even for the retained moving sample. This does not
  distinguish corridor exposure from arrival conditions precisely. Both internal
  samples use hull shielding before this tick's deferred wear; no continuous
  shielding/exposure integration is introduced.
- Long/small-step equivalence is established for stable conditions. Sampled
  quality, threshold transitions, repairs or changing radiation can still make
  coarse and subdivided ticks differ.

`_damage_hull` instantaneous damage and `_apply_radiation` dose integration are
unchanged. No relativistic external flux, interstellar-medium damage or new
radiation model is invented. Drone drain, integrity, charging, decontamination
and upkeep remain in their previous domain. Jobs, repairs, life-support timers,
hibernation rules, biological efficacy, narrative, radio, worldgen and recovery
remain unchanged; none is called twice for these wear segments. No per-second
loop, new save field or migration is added.

Engine ageing still produces LIMITED/DAMAGED/CRITICAL transitions and can block
future departure. T-04A's module/speed rules and antimatter price remain intact.
CANON v0.6.0's future `engines speed`, consumption ladder and improved damaged-
engine ceilings are not implemented. No availability or balance change is made.

This closes A-TECH-005's specific system/hull ageing discrepancy against
C-TIME-003. Its implementation-status description should now be updated through
canon maintenance, while local manoeuvres, acceleration/braking and in-transit
speed changes remain open. `docs/canon/universo.md` is deliberately unchanged.
Player-facing EN/ES manuals describe ageing separately from dose. Existing
commands, help syntax and event strings need no additions.

See [verification](../testing/wear-proper-time-review.md) and
[the electrical contract](electrical-proper-time.md).
