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

## Automatic paid safety braking (NAV-BRAKE-01B3H-B2B1)

On the next positive `Engine.tick()` after a B2A nominal acceleration or
coast cut, `pending_transition="safety_brake"` is replaced at the stored
instant by `brake_to_stop(physical.motion, nominal proper acceleration)`.
This starts at the actual position, beta, galactic clock, and proper clock.
The transition itself uses no time, electricity, wear, RNG, or fuel. A zero
duration tick remains a no-op. The new segment runs through the existing
causal physical path, including electricity, radiation, hull loss, system
wear, and proper and biological time. The original nominal plan stays
invalidated and `replan_required` remains true.

`NominalBrakingSubstitution` records the invalidated paid plan, interrupted
phase and elapsed time, original destination, exact replacement segment, and
the 35% engine event. The state validates the segment as continuous braking
from the interrupted motion to beta zero at the nominal deceleration, no
faster than the plan's peak beta. It is the one braking maneuver already
included in the paid nominal fare; it neither creates a second receipt nor
changes the antimatter balance. It cannot authorize a changed destination,
another segment, or renewed acceleration. An independently paid physical
segment has no nominal braking allowance and still rejects this transition.
The authorization and completion marker survive save/load; earlier physical
pickle payloads remain readable.

Exactly 35% engine health permits the transition. Between 15% inclusive and
35%, engines may brake but cannot accelerate. The DAMAGED to CRITICAL state
event caused by the first positive braking interval is preserved once. At an
exact 15% cut with beta still positive, the segment stops advancing and
`pending_transition="inertia"` retains the real motion; automatic inertial
continuation belongs to B2B2. If beta reaches zero first, the substitution
becomes completed at the actual stopping position and later positive ticks
cannot restart it. No public arrival or waypoint is created, even if the
ship crosses the destination while moving. Radiation uses the provisional
endpoint policy beyond the route. With an unchanged, fixed nominal geometry
and the same deceleration, an interruption in acceleration or coast stops at
or before B; moving the destination geometry after departure can exercise
the beyond-B spatial path, but ordinary B2B1 travel does not produce it.

The activation and requested positive interval run on a private staged
`GameState` and commit together. Missing propulsion power, isolation,
unresolved electrical or radiation limits, unsupported health events, and
requested motion past a causal boundary reject the entire operation without
partially activating braking. B2B2 must resolve the pending inertial cut;
later work must handle repair and replanning, public arrival and waypoints,
and any additional powered maneuver with its own valid fuel authorization.

## Automatic inertial continuation (NAV-BRAKE-01B3H-B2B2)

After a braking interval ends at the causal 15% engine cut with residual beta,
the next positive `Engine.tick()` creates a zero-thrust `coast_for()` segment
from the exact stored `MotionState`. Its start preserves distance, beta,
galactic time, and proper time. A zero-duration tick does nothing. The engine
simulates the requested interval on a private state and commits the transition
and advance together; an unsupported electrical, radiological, health, job,
or other causal limit rejects the whole request and leaves the pending marker.
A request that *contains* the 15% cut still rejects as before: the caller
must end one tick at that cut and request the inertial interval separately.

`InertialContinuation` retains the interrupted braking segment and elapsed
time, original destination, and spent nominal or independent authorization.
For substituted safety braking it also retains the paid nominal plan and
`NominalBrakingSubstitution`; for direct nominal braking it retains the
invalidated paid plan; for an independent brake it retains its spent
`PropulsionAuthorization`. The active physical state has no propulsion receipt
or active substitution. The old plan remains invalidated, no antimatter is
charged or refunded, and new powered maneuvers cannot use this history.
Earlier physical save payloads remain readable. Each unpowered segment has
only the duration requested for that tick; after its administrative endpoint,
the next tick renews it from the exact previous endpoint. There is no
inertial arrival ETA or fixed-step scheduler.

The existing physical interval path advances position, battery, radiation,
hull and system wear, galactic/proper/biological clocks, and events. Engine
health may fall below 15%, or engines may be isolated or OFFLINE, without
altering inertial beta. Other operational cuts retain conservative rejection.
Crossing and moving beyond the original destination at positive beta does not
declare arrival, dock, create a waypoint, change the current node, or add a
route. The provisional radiation profile clamps to its endpoint beyond B.
Public `Travel` and `RouteSolve` remain prohibited while physical transit
exists. Repair, replanning, resumed braking, public waypoints and overshoot
warnings require later work and separate authorization for any new thrust.

## Causal engine repair during inertia (NAV-BRAKE-01B3H-C1)

The internal inertial path now uses the productive job scheduler's
`_begin_job_interval()`, `_next_job_completion_s()`, `_advance_job_timers()`,
and `_resolve_job_interval()` phases. At each boundary, eligible QUEUED jobs
activate before the physical electrical snapshot. A RUNNING job's existing
`power_draw_kw` is therefore included in the forecast; ordinary repair jobs
currently configure zero additional draw. The next interval ends at the
earliest job completion or the requested horizon. Physical motion,
electricity, radiation, hull and system wear run first; galactic job ETA is
then debited and the productive repair outcome is resolved at that instant.
The next interval recomputes all conditions. A zero-ETA job resolves at the
current instant without a fabricated motion step. The public historical
scheduler retains its original order.

The admitted slice is one `REPAIR_SYSTEM` job for `engines`, owned by one
deployed drone in an internal ship sector. `Engine.apply_action(Repair)`
continues to reserve scrap and create the real job. The normal job resolver
performs its failure draw, refund or consumption, operator battery debit,
health change, and events. Inertial beta and spent propulsion history remain
unchanged even if repair restores braking capacity. New thrust and replanning
are still prohibited. A deployed drone's idle battery drain, radiation dose
and integrity decay use the existing productive methods in galactic seconds;
the physical radiation integral supplies its spatially integrated galactic
dose. The path rejects an interval before committing if a return reserve,
drone radiation threshold or integrity floor would be crossed without a
supported cut. This also prevents retrospective use of the endpoint radiation
rate for the whole drone interval.

The entire requested tick runs on a private `GameState`; job effects,
movement, events and RNG commit once. A later unsupported limit rolls back an
earlier simulated repair. More than one eligible job, non-engine jobs, other
drone configurations, auto-recall boundaries, and unresolved electrical,
radiological, health or narrative cuts still reject atomically. Public
`Travel`, `RouteSolve`, `Dock`, and node `Scan` remain blocked during physical
motion. Future replanning must start from actual position and beta, retain
the spent job and fuel history, and obtain a new fuel authorization for any
powered maneuver.

## Conditional recovery calculation after repair (NAV-BRAKE-01B3H-C2A)

`nav_recovery.plan_inertial_recovery()` is a pure internal query. It accepts a
validated `PhysicalTransitState` with `InertialContinuation` and reads its
current `MotionState`: distance along the original A–B line in metres, beta,
galactic seconds and ship proper seconds. The destination distance comes from
the actual A and B node geometry, converted with the physical Julian light
year. It uses the interrupted braking segment's proper deceleration by
default; a caller may supply a different currently available deceleration.
The old nominal ETA and paid phase index play no part in the calculation.

The existing relativistic `braking_profile()` gives the minimum stopping
distance. If the remaining distance exceeds that distance, the proposal is a
constant beta coast to the last possible braking point followed by
`brake_to_stop()`. Exact equality proposes immediate braking with no zero
duration coast. If there is less room, including a ship already past B, it
proposes immediate emergency braking and identifies the predicted physical
stop beyond B. No branch accelerates, reverses, declares arrival or creates a
waypoint. The recommended and last physically possible braking positions are
both represented; they coincide because no additional operational safety
margin has been approved. Numerical closure tolerance is only for validating
the segment calculation and does not alter the strict decision boundary.

The frozen `RecoveryPlan` separates engine braking capacity, current
operational braking availability through the existing power path, and the
pending authorization for any newly powered segment. Below 15% engine health
or with effective engine isolation it returns `no_propulsion`; a disabled
power path also returns `no_propulsion` while retaining the distinct physical
capacity result. A malformed or noninertial source returns `invalid`. A
powered proposal is only kinematically feasible under constant available
proper deceleration: future wear, radiation, power, drone and job events can
interrupt it. The plan's `is_current()` compares the source physical state,
clocks, geometry, relevant systems, power, active job load and fuel balance;
an external acceleration override must be passed again when checking freshness.
Plans are not persisted as an authoritative navigation state.

C2A does not change `Engine.tick()`, install segments or debit antimatter.
`InertialContinuation` retains its spent nominal, substituted or independent
braking authority solely as history. C2B must revalidate the plan immediately
before execution, define and reserve a new fuel authorization, then run the
existing causal electrical, radiation, wear and job cuts. Any later coast
boundary, emergency overshoot, arrival or waypoint policy remains separate.

### Numerical precision and acceleration provenance (C2A-R1)

The original profile check scaled its tolerance only from the initial and B
positions. A braking distance much larger than both can therefore differ by
a few metres from the sampled segment solely through floating-point
addition and subtraction, yet be rejected as `invalid`. The profile check
now uses 64 ULPs of the largest relevant magnitude: initial position,
stopping distance or predicted stop position, with a 1 m floor. The separate
coast-then-brake closure check uses the initial position, B, stopping
distance, coast endpoint and final position. Both are checks of numerical
consistency; the comparison of **remaining distance against braking distance
is still strict**. Neither tolerance grants extra room to stop at B. A
materially inconsistent profile still returns `invalid`.

`RecoveryPlan.deceleration_source` records `history` or `external`. A plan
using the interrupted brake's recorded acceleration can rederive it from the
current physical history. For an external acceleration, `is_current()` now
returns false unless the caller supplies the currently available value;
changed values also return false. C2B must check this before any authorization
or maneuver and must still reassess operational cuts during execution.

## Internal execution of repaired inertial recovery (NAV-BRAKE-01B3H-C2B1)

`Engine.prepare_inertial_recovery(state, plan=None,
proper_deceleration_m_s2=None)` is an internal operation. It requires a real
`InertialContinuation`, no active repair job, current braking capacity, and a
fresh `RecoveryPlan`. A supplied plan must pass `is_current()` and match a new
calculation from the current state. External deceleration must be supplied
again to both checks. A stale plan, missing external value, changed systems,
geometry, power, clocks, fuel or motion fails before payment. With no supplied
plan, preparation calculates a current one. `no_propulsion` and `invalid` are
never executable decisions.

The provisional tariff is the existing `engine_fuel_cost()` route tariff,
using the lowest supported pricing speed at or above the brake's initial
beta. If no supported ceiling exists, preparation fails. One new
`PropulsionAuthorization` is bound to the immutable recovery braking segment
and original destination, charged once, and stored in `RecoveryExecution`.
The preceding nominal and substituted braking payments remain in its nested
`InertialContinuation` as spent history. The active physical state carries no
second propulsion receipt and no revived nominal plan. Earlier physical
pickle layouts still load; new states serialize the recovery record.

`Engine.tick()` dispatches an active recovery through the existing physical
segment integrator. A `coast_then_brake` recovery moves at constant beta to
the calculated brake point, checks current propulsion there, and then brakes.
`brake_now` and `emergency_brake` start braking at once. The latter retains
the real position beyond B. The integrator advances galactic, proper and
biological clocks, electrical state, spatial radiation, hull and system wear,
and the deployed repair drone's maintenance. A tick may cross the coast to
brake boundary; the entire requested interval commits once. Unsupported
electrical, radiation, drone, job or engine integrity cuts reject the whole
tick atomically. A brake reaching zero beta marks the recovery complete and
leaves no active reusable receipt. Loading never debits again. Completion
does not update the public node, create a waypoint, or emit an arrival.

The explicitly armed automatic transition after a productive repair is
described below. During active recovery braking, C2B2B1 now records an exact
15% integrity cut and permits inertial continuation. A request extending
past that cut without a complete supported interval rejects atomically.
Unsupported operational changes before the planned braking point still
reject. Such rejection neither charges nor refunds fuel.

### Job safety and verified deceleration cap (C2B1-R1)

The C1 inertial continuation alone may run its limited productive engine
repair job through the causal job scheduler. Recovery execution has no job
scheduler. Preparation and every recovery tick therefore reject any active
job ID or any `QUEUED` or `RUNNING` job, including inconsistent indexes, before
moving the ship. A deployed drone still receives its ordinary maintenance
when no job is pending; its presence is not permission to skip a job. For
this internal phase, `Repair` remains a productive action and can queue a
job after recovery preparation. The following recovery tick rejects without
advancing that job, the ship, clocks, events or RNG. C2B2A handles one linked
repair; public activation still needs preventive coordination with new work.

No independent variable thrust-rating model exists yet. The interrupted
braking segment in `InertialContinuation` provides the provisional maximum
verified proper deceleration. A lower positive external value or the same
value may be authorized; a higher value remains a mathematical proposal only
and fails before fuel payment or recovery installation. `is_current()` still
requires an external value to be supplied again. Engine integrity, isolation
and the power path determine operational availability separately from this
magnitude cap. `Engine.tick()` checks the cap again before braking and at a
coast-to-brake transition. Unsupported capacity changes reject the complete
requested tick atomically; no thrust is applied past a failed check.

### Authorized automatic recovery after repair (C2B2A)

`Engine.arm_inertial_recovery(state, job_id, max_capsules=...)` is internal.
It accepts an active, productive `engines` repair with a deployed owner drone
only during positive-speed physical inertia. It stores one immutable,
persisted `RecoveryIntent`: the job's internal ID, original destination,
explicit authorization, positive finite spending ceiling, historical
deceleration policy and pending status. Arming changes only this record. The
ceiling is a limit, not reserved antimatter; no fuel is debited until a fresh
plan can be installed. A second arm while an attempt is pending or used, and
reuse of a cancelled authorization, are rejected.

At the job's actual completion time, the C1 scheduler first integrates the
inertial interval and its power, radiation and wear, resolves the productive
repair and applies its effect. The linked pending intent then calls the
existing `prepare_inertial_recovery()` on that state. Preparation replans
from its real position and beta, checks current braking and electrical
capacity, verifies the historical deceleration cap, recalculates the
provisional route tariff, and charges once only if available antimatter and
the authorized ceiling both cover it. The new `RecoveryExecution` preserves
the interrupted brake history, and the intent becomes `used`. No clock,
position, wear or RNG advances during preparation. A later tick follows
`_tick_recovery()` without another instruction or debit.

A failed or insufficient repair, isolation, unavailable power or fuel,
unexecutable plan, or exceeded ceiling leaves the productive result in place
and marks the intent `cancelled`; the ship keeps coasting. A failed attempt
does not retry or charge. An unarmed repair has the C1 inertial behavior.
Save/load preserves pending, used and cancelled states; older physical
pickles default to no intent.

For a tick extending past the repair, the engine advances the remaining
duration through `_tick_recovery()` inside the same private simulation and
commits once. If a later transition cannot be modeled, the whole requested
tick rolls back, including the repair. Preexisting concurrent jobs still
hit the C1 scheduler's atomic rejection; if another job is pending at the
completion instant, the intent is cancelled and the completed repair remains.
Active recovery retains the R1 defensive job block. Public navigation still
needs preventive admission control for new jobs, handling of subsequent
braking-capacity loss and unsupported temporal cuts, and public arrival and
waypoint behavior.

### New authorization after cancellation (C2B2A-R1)

A cancelled intent is spent as an attempt, though it has paid no fuel. While
the ship remains in physical inertia, `arm_inertial_recovery()` may issue a
new intent for a *different active productive engine repair*. The old job
cannot trigger the new one. If braking is already available and no new repair
is needed, `authorize_manual_inertial_recovery(state, max_capsules=...)`
issues a distinct unpaid manual intent. The existing
`prepare_inertial_recovery()` then rechecks the current position, beta, power,
braking capacity, historical deceleration cap, route tariff, available fuel
and the new ceiling. A failed manual preparation leaves its pending intent
unchanged; `cancel_manual_inertial_recovery()` explicitly ends it before a
different ceiling can be authorized. None of these authorization operations
moves the ship or spends fuel.

Each intent has a monotonic attempt number and a bounded summary of the last
cancelled attempt (number, linked job if any, and outcome). New issuance
replaces the current cancelled intent with a new immutable object; it never
changes that old object back to pending. Only a pending intent can prepare a
recovery, and a used intent stays bound to the paid `RecoveryExecution`.
Save/load retains these distinctions, accepts the earlier seven-field intent
pickle, and does not repeat jobs or charges. The manual path remains internal;
public admission control and arrival behavior remain open.

### Second braking loss during recovery (C2B2B1)

During an active `RecoveryExecution` braking segment, the existing integrated
wear solver locates the first 15% engine integrity crossing. A tick ending
exactly there commits position, residual beta, clocks, electrical state,
radiation and wear up to the cut. A request for more time that cannot be
completed in the same transaction rejects atomically. Recovery becomes
`invalidated` and `replan_required`, with `pending_transition="inertia"`;
no arrival is declared.

An immutable, bounded `RecoveryInterruption` preserves the paid recovery,
interrupted segment, local cut time, position, beta and cause. That recovery
still contains the first `InertialContinuation` and its nominal or earlier
braking receipt. The second `PropulsionAuthorization` remains spent in
`RecoveryExecution`, then in the new `InertialContinuation` after transition.
`RecoveryIntent` retains its `used` status. No receipt becomes fresh
authority, and antimatter is not refunded.

The next `Engine.tick()` starts unpowered motion at the exact cut and advances
at constant beta without another charge. The original destination remains a
reference; the ship may pass it without arrival, node changes, waypoints or
new links. Save/load retains the bounded history; physical pickles with up to
14 previous fields load without a second interruption. Further authorization
and a third maneuver were blocked at C2B2B1; C3A added one limited productive
repair job during the second inertia, and C3B1 permits the manual maneuver
below. Public navigation and arrival remain open.

### Braking capacity loss during the recovery wait (C2B2B2)

For `coast_then_brake`, the wait is unpowered but the later brake has already
been paid. The existing integrated wear solver locates the first instant at
which engine integrity reaches 15% during that wait. Reaching 35% does not
cancel recovery: the ship may enter the braking-only band, emit the ordinary
engine-state event and continue waiting. A tick ending exactly at 15% commits
only the preceding motion and physical effects; a request crossing that cut
without a fully supported interval rejects atomically. If the paid wait
starts exactly at 15% with positive ordinary wear, its cut occurs at zero
time and the same tick can continue inertially. The braking phase has not
yet run.

`RecoveryCoastInterruption` distinguishes this cancellation from
`RecoveryInterruption`, which is reserved for an active brake. It retains the
invalidated phase-zero `RecoveryExecution`, local cut time, position, beta,
cause and spent fuel receipt. The execution still holds the first
`InertialContinuation` and its history. The pending state uses
`pending_transition="inertia"`; on the next tick, the original inertial
history resumes at the exact cut, without treating the planned brake as
executed or charging or refunding antimatter. Save/load retains the history;
older physical pickles of up to 15 fields keep their meaning.

The ship retains destination and beta, may pass B, and creates no arrival,
waypoint or new link. A third authorization was blocked at C2B2B2; C3A added
one engine repair job, and C3B1 permits manual authorization below. Engine
isolation, electrical loss or another
operational change not caused by ordinary wear retains atomic rejection
until causal coordination exists; it is never recorded as a false integrity
cut. Later replanning, public admission control and public arrival remain open.

### Productive repair during the second inertia (C3A)

After either `RecoveryInterruption` or `RecoveryCoastInterruption`, the C1
causal scheduler can activate and resolve one `REPAIR_SYSTEM` job for
`engines` with one valid internal drone. Before advancing it verifies the
physical history, used intent, and agreement between `QUEUED`/`RUNNING`
jobs and the active index. It reuses `_begin_job_interval()`, job completion
boundaries, physical integration, electrical and radiation effects, drone
maintenance, and applies the productive effect only at completion. A zero
ETA job may resolve at the current instant without reactivating the
invalidated `RecoveryExecution`.

Repair can fail under productive risk or improve integrity after earlier
wear. In either outcome the ship keeps beta, destination, and inertial path.
No propulsion is charged or authorized; `RecoveryIntent` stays `used`, and
both interruption types retain the first history and recovery receipt. A
private transaction rolls the whole tick back if a later electrical,
radiological, drone, job, or narrative boundary cannot be coordinated.
Save/load does not repeat the outcome or RNG. Repair after passing B is also
supported without arrival or node change.

C3B1 introduced the bounded lineage and manual payment described below.

### Third, manually authorized recovery (C3B1, C3B1-R1)

After a second recovery interruption, an engine repair completed and applied
by the productive scheduler **after that cut**, together with current braking
capability, permits one new manual `RecoveryIntent`.
It has a fresh monotonic authorization ID and a finite positive spending
ceiling. Arming does not debit fuel. `prepare_inertial_recovery()` checks the
current `RecoveryPlan`, clocks, route, power, jobs, conservative deceleration
and fuel, then debits the existing `engine_fuel_cost()` tariff once. The new
`PropulsionAuthorization` binds one braking segment to the original
destination. A manual deceleration may be below the historically demonstrated
brake, never above it. A planned brake abandoned during coast is not proof of
its capacity; the earlier executed brake remains the cap. Capacity is checked
again before the powered phase.

`RecoveryLineage` in `src/retorno/core/nav_state.py` stores the original
origin and destination, counts of paid and interrupted recoveries, total
recovery antimatter spent, the highest spent authorization ID, and a fixed
window of **two** detailed `RecoveryAttemptRecord`s. A record holds a spent
segment receipt, authorization ID, outcome, interruption type and cut motion
when applicable. Older records roll into cumulative totals and a deterministic
SHA-256 commitment. The digest is not a reconstructible audit log; complete
historical receipts would require a separate persistent ledger. The lineage
never supplies current position, beta or clocks: the active physical segment
does. IDs through `spent_through_authorization_id` cannot be reused.

Physical pickle payloads of 8–17 fields and recovery intents of 7 or 9
fields still load. The lineage is created only when a new paid maneuver is
prepared. It migrates the second interruption's validated receipt and cut
without moving the ship, changing clocks, refunding fuel or activating an
old intent. C3B1 originally inferred a second repair from two distinct
completed engine jobs. Both could predate the second cut, so their count does
not establish causality. C3B1-R1 instead records immutable
`SecondRepairEvidence` only when `_tick_inertial()` resolves a successful
`REPAIR_SYSTEM` job for `engines` and actually improves engine health. The
evidence binds its internal job ID, terminal sequence, completion galactic
time, health before and after application, interruption type, cut motion and
spent recovery receipt. Authorization rechecks the completed job and current
braking capability; evidence alone never authorizes propulsion or debits fuel.
It cannot be attached to a different interruption. Failed, cancelled,
queued, running or unrelated jobs provide no evidence.

An inertial state without current repair evidence cannot issue a new manual
authorization or pay for a recovery. Rejection leaves fuel, motion, clocks,
jobs, drones, events and RNG untouched.

The existing `Engine.tick()` recovery path executes immediate braking,
coast then braking, and emergency overshoot. It can cross the coast/brake
boundary in one private transaction. Completion marks the last bounded
record completed. C3B2 extends this path to successive cuts below.

### Successive manual recovery cycle (C3B2)

Every paid recovery can now lose braking capacity at the 15% wear boundary,
either during its brake or during a prepaid coast. The interrupted execution
and its receipt remain spent. A residual-speed cut updates the latest
`RecoveryLineage` record to `interrupted_brake` or `interrupted_coast`, records
the exact `MotionState`, invalidates the current execution, and starts
unpowered continuation without a jump in position, beta or clocks. A brake
that actually reaches beta zero is completed, not interrupted. A prepaid
coast beginning at exactly 15% can cut at zero elapsed time. No cut declares
arrival or creates a waypoint, even after passing the destination.

The current `RecoveryInterruption` or `RecoveryCoastInterruption` is the only
detailed interruption outside the two-record lineage window. The existing
`SecondRepairEvidence` name now denotes evidence for **that current cut**:
the productive scheduler records a successful engine repair with actual
health gain, terminal sequence and completion time while processing the
post-cut inertial state. Zero-ETA completion may share the cut's galactic
instant because it occurs after the cut in scheduler order. Preparation
consumes the evidence, appends one paid record, and clears the current
interruption and evidence. The next cut therefore cannot reuse an earlier
repair. Cancellation of a pending manual intent leaves current evidence
intact and increments the next authorization ID. Past paid IDs stay spent
even when their detailed records leave the window.

`InertialContinuation.interrupted_segment` retains the last **executed**
brake. A cut during prepaid coast carries this earlier executed brake
forward; an unexecuted planned brake never raises the demonstrated
deceleration ceiling. `plan_inertial_recovery()` and preparation use that
segment as the default and maximum physical deceleration, respectively,
including after the lineage has evicted its original detailed record.
`RecoveryLineage` keeps cumulative paid capsules, attempt and interruption
counts, highest spent authorization ID and a chained digest with at most
two detailed records. It does not supply live motion or clocks.

The existing planner, physical integrator, job scheduler and one-use fuel
tariff execute each cycle. Authorization alone is free; successful preparation
debits exactly once. Ticks run on private staged state and commit only after
all supported boundaries resolve; a later unsupported electrical, radiation,
drone, job or narrative boundary rolls back motion, repair evidence, fuel,
events and RNG together. Current-version save/load preserves pending,
interrupted, repaired, authorized, paid and completed phases, including
lineage rollover. During experimental development no migration or backward
compatibility is promised for older save schemas; incompatible payloads must
fail clearly. Existing compatibility code outside this cycle is not a design
constraint for future formats.

Operational limits still apply: actual braking capability, electrical power,
geometry, clocks, jobs, plan freshness, demonstrated deceleration, available
antimatter and the authorized spending ceiling. Unsupported causal boundaries
and incompatible jobs still reject atomically. Public arrival, stopping
waypoints, new destinations, acceleration during transit and automatic
successive recovery remain outside this phase. The next navigation block
will handle physical arrival, overshoot and the stopping waypoint.
