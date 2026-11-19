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

## First powered engine intervals (NAV-BRAKE-01B3H-A)

`Engine.tick()` now passes internal `accelerate`, `coast`, and `brake` segments
through the same bounded `_tick_physical_segment()` adapter. It samples the
immutable `MotionSegment` at the requested galactic endpoint, obtains proper
time from `proper_time_in_segment()`, and carries physical position, speed,
ship time, and biological age forward without an ETA based reconstruction.
Acceleration starts from rest or positive beta and stops at the segment's
specified speed. Braking retains forward motion until its endpoint, where
beta can be exactly zero. Crossing the destination never declares arrival.
A tick beyond the segment is rejected until a continuous successor is
prepared. No public command creates physical travel.

The internal `Engine.prepare_physical_segment()` API checks clocks, endpoint
geometry, segment continuity, intent, engine capacity, and the existing speed
ceiling. A powered leg requires a discrete `pricing_speed` at least as high as
both endpoint speeds. Preparation debits `Engine.engine_fuel_cost()` once from
the ship's authoritative `antimatter_capsules` balance and stores an immutable
`PropulsionAuthorization` receipt bound to that one segment and original
destination. Subsequent ticks never debit again. Each additional powered leg
needs a new preparation and debit; a coast leg needs neither. This is an
internal provisional per-leg use of the existing journey tariff, not a
continuous fuel-burn model or a change to public travel pricing. A receipt is
trusted only when created by this internal preparation path; arbitrary save
editing is outside the state integrity contract.

The existing operating-state classifier remains strict at 35%. The separate
`acceleration_available()` and `braking_available()` capabilities apply, along
with effective engine isolation and an operational core and distribution.
At 35% acceleration is rejected because the required safety-braking transition
is not yet implemented. Braking remains possible at exactly 15% if no wear
would lower integrity during the interval. Acceleration or braking intervals
that cross their respective capability boundaries are rejected atomically.
Other health, electrical, radiological, narrative, job, radio, recovery, and
survival restrictions from 01B3G still apply. Proper-time electrical quality,
spatial radiation, coupled hull and system wear, and `select_next_boundary()`
are reused with changing beta. Propulsion adds no invented electrical load;
the existing productive power balance is the current policy.

Preparation and tick stage changes on a deep copy and publish once while
preserving `GameState` and immediate owner identities. Rejected intervals
leave fuel, clocks, events, and RNG unchanged. Tests cover analytic acceleration
and braking references, split intervals, capacity thresholds, paid receipts,
save/load, hibernation, overshoot, and failed cuts. NAV-BRAKE-01B3H-B must
resolve earlier cuts and same-instant transitions, job completions, power
regulation, dynamic propulsion replanning, safety braking, and physical
arrival before public activation. The earlier 01B3G descriptions above record
that phase's narrower scope.

## Prepaid nominal journeys (NAV-BRAKE-01B3H-B1)

`Engine.prepare_nominal_physical_travel(state, destination_id,
target_beta=None, proper_acceleration_m_s2=1.0)` is an **internal** departure
API. It requires an idle undocked ship at the origin, a known linked destination
within the existing 45 ly hop cap, available normal acceleration, and a
supported discrete target speed no greater than the ship's current maximum.
It converts the known geometric distance with `light_years_to_metres()`, calls
`plan_travel()`, and builds an exact continuous chain using `accelerate_to()`,
optional `coast_for()`, `brake_to_stop()`, and `append_segment()`. No route is
created or discovered. Public `Travel` remains on its historical path.

`NominalTravelState` stores origin and destination IDs, the immutable
`TravelPlan`, two or three immutable segments, the tariff speed and amount
paid, a bounded phase index, and explicit completed/invalidated flags.
`PhysicalTransitState` still owns the active segment and elapsed galactic time;
its motion property remains the source for position, beta, and both physical
clocks. The nominal record is persistent and binds the entire authorized
chain to the original destination. An old 01B3H-A physical-state pickle loads
with `nominal_plan=None`. The existing per-segment preparation API and receipt
remain available for isolated internal maneuvers.

The nominal preparation calls the existing segment preparation on a private
copy to reuse capacity validation and `Engine.engine_fuel_cost()` pricing.
It then replaces the temporary segment receipt with one plan authorization
and publishes the copy once. `ship.antimatter_capsules` is debited once at
departure and remains the only fuel balance. The planned acceleration and
braking phases consume that authorization without another debit; coast is
inertial. A changed destination, active phase, or additional maneuver cannot
reuse it. Emergency and replanned maneuvers are not funded by this contract.

`Engine.tick()` runs a nominal interval on a private `GameState`, splitting
only at its analytic phase ends and reusing `_tick_physical_segment()` for each
part. Each next segment starts at the exact previous `MotionState`. Health,
electricity, radiation, wear, position, and all clocks carry forward. All
forecasts are taken again from the staged state at the new phase. The original
state receives one final commit if every part succeeds. Any unsupported
earlier or deferred cut rejects the *whole* requested interval, including a
failure in the second or third phase. There are no fixed one-second steps.

At the last braking endpoint, beta is exactly zero and physical distance must
match the destination within `max(1 metre, 64 ulp(distance_m))`. The nominal
record becomes `completed`; a later positive physical tick is rejected and
cannot restart propulsion or charge fuel. No public arrival event, visit,
manifest change, waypoint, or docking is performed. A request past the final
endpoint is rejected without partial advancement.

This phase accepts only nominal uninterrupted intervals under the restricted
01B3H-A electrical, radiological, health, job, drone, radio, narrative, and
survival conditions. The exact 35% and 15% propulsion rules remain, but
automatic safety and emergency braking are pending. With the nominal 1 m/s²
acceleration, short routes can complete; long intervals can encounter an
operational cut and are rejected until B2 resolves it. B2 must invalidate
stale nominal plans, resolve same-instant cuts and failures, authorize any new
powered maneuver separately, and replan from actual position and beta.

## First causal engine-wear cut (NAV-BRAKE-01B3H-B2A)

Within the restricted electrical and radiological regime of 01B3H-A,
`first_integrated_wear_at()` brackets the first engine-integrity event in the
requested physical interval. Every bisection probe recomputes
`integrate_segment_radiation()` and `integrated_system_wear()` from the same
initial hull, engine, and power snapshot. The endpoint is checked first; the
search stops when the upper and lower bounds are adjacent representable
galactic instants. It tests the same rounded `health - wear <= threshold`
comparison as the state update. The bracket is one floating-point step wide
for the **numerically integrated** wear; the radiation integrator's reported
quadrature error and floating-point accumulation also limit physical-time
accuracy. Safe subdivision can shift a variable-radiation cut by several
tenths of a nanosecond, so callers must query the next limit again from the
new state instead of treating an old forecast as authoritative. No fixed tick
or positive epsilon is inserted at a strict threshold. If a positive interval
or its proper clock cannot be represented, the interval is rejected.

At 35% during acceleration, `_tick_physical_segment()` commits position,
beta, galactic/proper/biological clocks, hull loss, and ordinary wear through
the limit only. Engine health is recorded at exactly 0.35; the existing
`SystemState` classifier remains unchanged. `PhysicalTransitState` sets
`pending_transition="safety_brake"` and `replan_required=True`, while the
prepaid `NominalTravelState` becomes `invalidated` and retains the original
destination. `safety_braking` and `braking_started` remain false: no new
braking segment has run. At 15% during braking, the equivalent pending value
is `"inertia"`; the real nonzero beta is retained. At equality, braking is
still capable, but any further positive wear on the old segment is rejected.
Effective engine isolation continues to prohibit propulsion at entry.
The same 35% preventive cut is handled during nominal coast; beta remains
constant and no braking is claimed to have begun.

`Engine.tick()` accepts an interval ending at a resolvable engine event. A
request extending beyond it fails atomically, even when an earlier nominal
phase has already been evaluated on the private state. A simultaneous nominal
phase end can suspend its current phase; a simultaneous unsupported electrical,
radiological, health, or other cut rejects the whole interval. The existing
`select_next_boundary()` still checks those other limits. The invalidated
nominal ETA and authorization cannot drive another tick or pay for a new
maneuver. The suspension marker is included in save/load; eight-field
01B3H-A and nine-field 01B3H-B1 physical-state pickles remain readable.
No arrival, waypoint, public journey, or new fuel charge occurs.

Future work must replace the pending marker with a newly authorized safety
braking or inertial segment from the stored physical position and beta, resolve
simultaneous non-engine cuts in causal order, and define how already-paid
nominal braking and any additional propulsion are accounted for. Electrical
quality changes, work, drones, radio/narrative cuts, engine state changes
outside the handled capability threshold, and unresolved radiation limits
still reject the interval.
