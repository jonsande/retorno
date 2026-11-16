# Navigation motion segments (NAV-BRAKE-01B3A)

This is a pure mathematical API in `src/retorno/core/nav_physics.py`, tested in
`tests/test_nav_segments.py`. It does not activate physical playable travel,
change the clocks, or persist a route. The earlier rest-to-rest `TravelPlan`
and its coordinator remain available.

## Units and equations

Position is forward metres in a one-dimensional inertial galactic frame.
`beta = v/c` satisfies `0 <= beta < 1`; `c` is `LIGHT_SPEED_M_S`. Galactic and
ship proper times are seconds. Signed proper acceleration `a` is m/s²:
positive increases forward speed, negative brakes, zero is inertia.

For initial rapidity `eta0 = atanh(beta0)` and proper velocity
`p0 = sinh(eta0) = gamma0*beta0`, a galactic interval `dt` gives
`p = p0 + a*dt/c`, `beta = p/sqrt(1+p²)`,
`dx = c*dt*(p+p0)/(sqrt(1+p²)+sqrt(1+p0²))`, and
`dτ = (c/a)*(asinh(p)-asinh(p0))`. The implementation evaluates the rapidity
difference with `log1p` and the distance with the rationalized gamma
difference to avoid cancellation. For `a=0`, `dx=c*beta0*dt` and
`dτ=dt*sqrt(1-beta0²)`. The inverse `galactic_time_at_segment_proper()`
uses the midpoint hyperbolic-sine identity; no iterative or fixed-step solver
is used. The existing rest-start sampler now calls the same general equation.

## API and composition

`MotionState(galactic_s, distance_m, beta, proper_s)` records cumulative values
from a chosen origin. `MotionSegment(start, proper_acceleration_m_s2,
duration_galactic_s, end_beta)` is immutable and validates its physical end
speed. Factories are `coast_for(start, duration_galactic_s)`,
`accelerate_to(start, target_beta, proper_acceleration_m_s2)`, and
`brake_to_stop(start, proper_deceleration_m_s2)`. A reached acceleration target
and braking from rest return explicit zero-duration no-ops. Acceleration does
not exceed its target and braking ends at zero. `sample_segment(segment, dt)`
returns a state for any relative galactic time in the closed segment interval.
`galactic_time_at_segment_proper(segment, dτ)` returns the relative galactic
time for proper seconds from the segment start.

To interrupt a maneuver, call `truncate_segment(segment, dt)` and sample its
endpoint. Build an inertial or new powered segment from that exact state, then
use `append_segment(chain, next_segment)`. It requires exact endpoint equality
for position, speed, and both clocks and returns a new tuple. `sample_segments`
queries the chain by absolute galactic time and assigns a shared boundary to
the following segment. Queries do not alter the chain. Position may pass a
destination distance; this mathematical API does not declare arrival or visit
a node. `brake_to_stop()` uses the existing `braking_profile()` duration; its
endpoint distance and proper time agree with that profile.

## Coordinator and remaining work

`select_next_boundary()` in `nav_coordinator.py` now accepts either a
rest-to-rest `TravelPlan` or the active `MotionSegment`. Segment selection uses
its actual start clock, state and end, without scanning a historical chain or
reviving nominal phase/arrival times. `proper_time_in_segment()` and
`galactic_time_at_segment_proper()` convert a remaining proper-time limit from
a partially completed segment. The caller must invalidate stale predictions
when the maneuver or its operating conditions change and replan from current
physical position and speed. Crossing a destination coordinate does not imply
arrival. See [temporal boundaries](nav-boundaries.md) for zero-cut and causal
integration rules.

These segments model constant acceleration or inertia only. They have no
gravity, direction reversal, fuel, electrical state, propulsion failures,
arrival policy, or persistence. Finite binary floats limit resolution at very
large accumulated times or positions; invalid/nonrepresentable maneuvers
raise `ValueError`. Pure segment partition tests do not establish operational
partition invariance of `Engine.tick()`.
