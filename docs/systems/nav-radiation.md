# Physical transit radiation forecast (NAV-BRAKE-01B3F)

`src/retorno/core/nav_radiation.py` is a pure, conditional forecast for the
one-dimensional `MotionSegment` positions in `nav_physics.py`. Physical travel
is still guarded in `Engine.tick()`; this module does not change public travel,
alerts, hibernation or persistence. The earlier playable route interpolates
ambient radiation by elapsed ETA in `_compute_env_radiation_rad_per_s()`;
01B3F uses actual travelled metres instead.

## Spatial model and clocks

`RadiationProfile(A_m, B_m, A_rad_per_s, B_rad_per_s)` is immutable and requires
`B_m > A_m` and nonnegative endpoint rates. Ambient radiation varies linearly
with physical position between A and B. Before A it holds A's rate; beyond B
it holds B's rate, including overshoot and a stop beyond B. This endpoint rule
is provisional and does not model the full interstellar medium. Segment
position is in metres; conversion from light-years uses `LIGHT_YEAR_M` in
`nav_physics.py`. The profile never reconstructs position from a rest-start
plan or nominal ETA. Replacing one continuous segment with another at the same
position therefore does not change ambient radiation.

Rates are rad/s; integrated dose is rad. `integrate_segment_radiation()` accepts
any relative galactic-time subinterval of one segment and initial hull integrity
at its beginning. It reports ambient dose on both the galactic and ship proper
clocks, internal dose on the proper clock, and the integral of the normalized
internal radiation wear factor in proper seconds. Ordinary hull and system wear
use proper time. Productive drone dose still uses galactic time and a drone's
shield factor; this forecast does not apply drone effects.

## Hull and internal coupling

`internal_radiation_rate()` and `hull_decay_rate()` are the same pure formulas
used by productive `Engine._compute_internal_radiation_rad_per_s()` and
`Engine._apply_hull_degradation()`. Hull loss per proper second is the base
rate times `1 + (HULL_RAD_DECAY_MULT_MAX - 1) * clamp(env/HULL_RAD_REF)` and the
existing transit/hibernation multiplier. It stops at integrity zero; God mode
keeps hull fixed. Ingress is linear in `1 - current_hull` between its existing
min/max, so internal radiation uses the hull at each instant, never the final
hull retroactively. God mode still has a physical radiation rate and dose but
does not lose hull or system integrity.

The integrator splits at A, B, the hull-radiation saturation, and any hull-zero
instant. On each branch, `MotionSegment` gives proper time and position;
hyperbolic closed forms integrate ambient proper dose and its first proper-time
moment. Ordinary hull loss and internal dose then follow algebraically, with
the latter including the change in ingress while the hull wears. A bracketed
position/hull inverse resolves branch instants to floating-point time
resolution. No fixed-second stepping is used. `integrated_system_wear()`
combines a caller-provided quality integral with the normalized internal
radiation integral through `ordinary_wear_rate()` at its basis values; it
returns a calculated loss and never applies it.

Ambient galactic dose when radiation varies under acceleration, and the
clipped internal radiation wear factor, use deterministic adaptive Simpson
integration. Callers supply positive absolute and relative tolerances
(defaults `1e-8` and `1e-10`); the algorithm sums local a posteriori error
estimates, checks the aggregate against the requested tolerance, and raises
if the requested estimate is not met or refinement runs
out of floating-point/depth resolution. These estimates are numerical control,
not certified mathematical upper bounds. Tests compare against an independent
fine midpoint reference and exact constant/coasting cases. A future productive
adapter must retain this convergence failure as a hard cut and decide whether
a certified bound is required for powered movement.

## Conditional limits and invalidation

`environmental_limits()` predicts ambient elevated/high/extreme crossings,
hull-radiation saturation, and an upward hibernation wake threshold when
hibernating is requested. `radiation_limits()` adds ordinary hull-zero and
internal elevated/high/extreme and wear-saturation thresholds when internal
radiation is provably monotone: nondecreasing ambient, fixed hull in God mode,
or already-zero hull. Decreasing ambient with a wearing hull has competing
effects and returns deferred internal limits (`time_s=None`) rather than
inventing a crossing. All calculable limits are proper-time `TemporalLimit`s;
the existing `select_next_boundary()` converts them through the active segment.

The productive radiation classifications use `>=`. At an upward equality the
new category is already active. At a downward equality, the lower category is
entered only on the posterior side: a `post_crossing_check` at zero is emitted.
After processing it, `resolve_radiation_limit()` returns a marker bound to the
profile, segment and instant. Passing it back to the predictor removes only
that zero. Markers must be discarded when time advances. Mathematical cuts,
classification changes, future alerts and a hibernation wake remain separate;
the predictor sends no notifications. Endpoint plateaus do not generate false
downward crossings.

`radiation_invalidation_reasons()` detects a changed profile or segment,
unexpected hull integrity, physical position, or operating snapshot
(`in_transit`, `hibernating`, `god_active`) relative to the prediction. The
caller must supply the latter two snapshots if it wants those checks and
resample after destination/radiation endpoint changes, segment interruption,
repair or extraordinary hull damage. No query
mutates `GameState` or consumes RNG. Before physical movement can be enabled,
the future causal adapter must combine these proper-time limits and wear
integrals with electric quality, engine-health and galactic job limits, resolve
same-instant effects, and replan from real position/speed. Deferred internal
limits on decreasing ambient profiles still need a certified root-isolation or
monotonicity analysis. Fuel reservation and emergency braking remain separate
dependencies. Crossing B is not a successful arrival and creates no waypoint.
