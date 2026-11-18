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
gravity or direction reversal. Finite binary floats limit resolution at very
large accumulated times or positions; invalid/nonrepresentable maneuvers
raise `ValueError`.

## First internal engine interval (NAV-BRAKE-01B3G)

`Engine.tick()` now routes an existing `PhysicalTransitState` with a zero
acceleration `coast` segment through a bounded causal adapter. No public action
creates that state. The legacy tick and public `Travel` path retain their
existing behavior. The adapter uses `PhysicalTransitState.motion` for position,
speed, and accumulated clocks. It updates the galactic, ship proper, and
biological clocks once; maps physical metres onto the known endpoint vector;
and leaves the original destination and motion active even when B is crossed.
At exact segment end it retains the endpoint motion. A later tick beyond that
end is rejected until a real continuation segment exists. Inertia consumes no
antimatter and produces no arrival or waypoint.

The accepted interval has fixed, surplus electrical generation, quality 1,
no brownout or regulation timer, no active jobs or drones, blocked radio, no
active recovery plan, no narrative evaluation due, and no critical survival
transition. The route endpoint geometry and rates must exist. The engine uses
`nav_electricity` for conditional limits and the quality integral, its
productive electrical integrator for the battery, `nav_radiation` for spatial
ambient/internal dose and coupled hull loss, `nav_boundaries` for conservative
health forecasts, and `nav_coordinator` for the earliest cut. An internal
electrical, radiological, health, or segment-end cut before the requested
horizon is rejected; so is a deferred radiological limit, because this adapter
cannot prove that an uncertain first crossing lies after its horizon. No
fictitious ETA or fixed-second steps are introduced. System wear uses the
integrated quality and radiation exposure, not endpoint samples.

Forecast and execution run on a deep-copied `GameState`; staged fields are
published only after all productive effects and checks succeed.
Prediction queries consume no RNG. Rejected intervals leave the original
state, events, and RNG counter intact. General narrative, alert, recovery,
and radio hooks run once on the staged state under the restrictions above.
Powered segments, job completions, drone upkeep, radio reception, narrative
cuts, electrical regulation, and midinterval health transitions require a
future causal cut/resolution loop. The adapter does not copy `_tick_interval()`
or introduce a second game loop or save format.

## Navigation actions and state references (NAV-BRAKE-01B3G-R1)

An active `ship.physical_transit` is transit for public `Travel` and
`RouteSolve` decisions even while the legacy `ship.in_transit` flag is false.
Both actions return the existing `BOOT_BLOCKED` event with reason `physical_in_transit`
before fuel pricing, route refinement, job creation, or other navigation
writes. `Status`, `Diag`, and ordinary survival or repair actions retain their
existing individual checks. The CLI parser and Textual command path both
delegate these actions through `GameLoop.apply_action()` to the same engine
guard. This distinct reason avoids the historical `in_transit` advice to wait
until arrival, which has no meaning for an active physical segment. Route
presentation also marks departure as blocked. This does not
activate public physical travel or change historical travel when physical
state is absent.

`GameLoop` owns the `GameState` root; CLI renderers and Textual presenters
obtain current components from that root during each operation. The physical
commit now preserves the identity of the root and its immediate `meta`,
`clock`, `world`, `ship`, `os`, `jobs`, and `events` objects. It copies their
fields from the completed staged state; `GameLoop` holds its lock during this
operation. A failed staging
step leaves every original component untouched; a commit assignment failure
restores the prior fields and propagates the exception. Deeper objects such as
`ship.power`, systems, event lists, and world collections may be replaced at
a successful commit; consumers must read them through the current owner after
each tick. Existing CLI, Textual, persistence, and event paths do so. Tests
exercise held top-level references through a real `GameLoop` and Textual
presenter, successful movement, save/load, and both prevalidation and late
execution failures.
