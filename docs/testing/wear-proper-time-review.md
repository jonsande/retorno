# T-04B2 — focused verification

Base: clean `main`, HEAD `1b963eac3da5905549ce00209dfc3c6c84cdce52`.
T-04A, T-04B1 and CANON v0.6.0 were already present. No commit or push, no
navigation redesign, no balance changes and no general audit/global suite.

Only `src/retorno/core/engine.py` changes production behavior. Ordinary system
and hull wear now consume proper seconds, retaining their existing modifiers.
The T-04B1 arrival segments supply both duration and electrical samples; wear
still runs at its existing stage, with explicit moving context for the first
segment. EN/ES technical documentation and maintenance/radiation/engine manuals
were synchronized. Existing command syntax, help and event text need no changes.

The canonical project interpreter ran the focused checks with `PYTHONPATH=src:.`.
Commands, timing, exact output, clean-HEAD baseline and preserved-function checks
are in [the evidence](wear-proper-time-results.json).

| Check | Before | Final |
| --- | --- | --- |
| Existing electricity, speed/module, antimatter, clock and cruise tests | 57 PASS, 64 subtests PASS | Included below |
| Above tests + 13 new ordinary-wear tests | — | 70 PASS, 80 subtests PASS |
| Existing electrical policy smoke | — | PASS |
| Existing transit radiation interpolation smoke | — | PASS |
| Manuals style and EN/ES pairs | — | PASS |
| Existing radiation/hull smoke | Historical failure | Same historical failure |

`radiation_hull_smoke.py` fails at line 183 with `AssertionError: []`, expecting
an environmental radiation event. It was reproduced on the requested clean HEAD
before edits and fails identically afterward. That test was not modified or
repaired. No new final failure was found among executed checks; no claim is made
that the entire repository is green.

New coverage includes rest and stationary CRUISE equivalence; 0.3c/0.5c/0.8c;
individual configured system rates and hull ageing; retained quality, brownout,
radiation, NORMAL/CRUISE and hull hibernation modifiers; crossing/exact arrivals;
distinct electrical conditions for each segment; stable long/subdivided ticks;
LIMITED/DAMAGED/CRITICAL engine transitions with frozen speed/ETA/proper time;
future departure rejection; unchanged galactic dose/drone upkeep; single job,
narrative, radio and recovery processing; coarse endpoint environmental sampling;
instantaneous damage; new save/load continuation; and reactor derating sampled
by electricity on the next tick rather than replayed retroactively.

Existing regression fixtures changed only where T-04B2 intentionally invalidated
old assumptions: the wear-argument assertion now expects proper seconds, arrival
spies expect two wear segments, and accelerated damage fixtures in the electrical
and speed suites are expressed per onboard second to preserve their intended
damaged-engine scenarios. No production rate was adjusted.

AST equality against HEAD confirms that the ordinary electrical integrator,
battery integrator, generation/load calculation, action dispatch/navigation,
antimatter formula, dose routine, drone maintenance, life-support consequences
and instantaneous hull damage routines are unchanged. Balance and canon files
are unchanged as well.

Remaining simplifications: final-per-segment quality/brownout samples; endpoint
radiation at arrival rather than reconstructed corridor exposure; shielding
sampled before deferred wear; jobs/repairs applied at their existing galactic
stage; no continuous reconstruction of health, battery or threshold transitions.
Drones, dose, jobs and life-support rules retain their earlier domains; radiation
flux/interstellar media require later design. Future v0.6 speed selection, fuel
ladder and damaged-engine upgrade ceilings remain unimplemented.

A-TECH-005's implementation-status description should be updated after this
verification to mark the ordinary system/hull ageing discrepancy resolved.
Its local-manoeuvre, acceleration/braking and in-transit speed questions remain
open. No canonical decision was rewritten.

[Implementation and sampling policy](../systems/wear-proper-time.md).
