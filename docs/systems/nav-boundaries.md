# Navigation temporal boundaries (NAV-BRAKE-01B1 to 01B3C)

This internal API is implemented in `src/retorno/core/nav_boundaries.py` and
`src/retorno/core/nav_coordinator.py`, and tested by their matching test files.
It is not connected to playable
navigation. `Engine.tick()`, travel, abort, clocks, fuel, and save files still
use their previous behavior.

## Shared wear rate

`ordinary_wear_rate(system, power_quality, brownout_sustained, internal_rad,
in_transit=..., op_mode=..., god_active=...)` returns health loss **per ship
proper second** under the supplied, fixed conditions. `Engine._apply_degradation`
uses that same function and retains its existing clamp, system-state events,
ordering, and god-mode early return. The factors are base decay, power-quality
deficit, clamped internal radiation, the NORMAL transit multiplier, and the
existing sustained-brownout multipliers for `energy_distribution` and
`power_core`. The function does not integrate changing conditions.

## Thrust and health threshold

`thrust_available(ship)` delegates to the **existing normal-thrust**
classification in `ShipState.engine_operating_state()`. It is not the future
emergency-braking capability classifier. It does not test target speed,
physical speed, fuel, or a new electrical-quality threshold. Isolation uses
the existing `forced_offline` contract.

`predict_engine_health_limit(ship, wear_rate_per_proper_s, god_active=...)`
returns an immutable `TemporalLimit` for the mathematical arrival at
`Balance.SYSTEM_HEALTH_CRITICAL`. Its domain is `proper`. At exact equality
the engine is still DAMAGED because production classifies CRITICAL with `<`.
Thus `time_s=0` means *threshold reached*, not already unable to brake. A
positive rate produces the existing CRITICAL classification immediately after
that instant; future emergency braking may still be available. A zero rate, god
mode, or health already below the threshold yields no future crossing; the
`validity` field explains which case applies. Isolation does not erase a
separately calculable health threshold.

The predicted time is exact only while the supplied wear rate and all its
inputs remain constant. A change in power quality, brownout, radiation, mode,
base decay, repair, or isolation invalidates the prediction. A consumer must
sample the new state and recompute it.

## Job candidates

`propulsion_job_limits(jobs)` returns immutable `TemporalLimit` values in the
scheduler's active-job order, with `domain="galactic"`. It includes repairs
of engines, power core and energy distribution, relevant module changes, and
jobs whose power draw may change electrical conditions when they finish.
`engine_speed_upgrade_01` changes the physical speed ceiling;
`bus_stabilizer`, `aux_battery_cell`, and `micro_reactor_patch` change
electrical quality, capacity, or generation and thereby can change wear.
Other module installations are not assumed to change thrust directly.

For a RUNNING job, `time_s` is its current ETA **conditional on continued
execution**. Completion, repair success, and unchanged operating conditions
are not guaranteed; `uncertainty_reason` records this. An eligible QUEUED job
has a time-zero `job_activation` *check*, not a completion ETA. A queued job
blocked by an already running owner or route solve, or a RUNNING job awaiting
player confirmation, has `time_s=None`. A QUEUED job awaiting confirmation can
still activate and change load at time zero. The productive scheduler can still reject an
activation for other reasons. Unrelated zero-load jobs are omitted. A job
starting, stopping, being interrupted, or changing power draw invalidates the
snapshot. The consumer may use known candidate ETAs as cuts, but must let the
productive scheduler decide outcomes exactly once. It must not
apply a repair or alter RNG during prediction.

The API does not predict future electrical regulation, variable-rate wear,
random job outcomes, or the time at which blocked queued work will start.

## Pure coordinator (01B2)

`select_next_boundary(plan, elapsed_galactic_s, horizon_galactic_s, *,
health_limit=None, job_limits=(), invalidation_reasons=(),
seen_zero_selections=())` returns an immutable `BoundarySelection`.
`plan` may be the original `TravelPlan` or the **active** `MotionSegment`.
For a plan, `elapsed_galactic_s` and `at_galactic_s` are elapsed seconds since
departure. For a segment, they are absolute seconds in its cumulative galactic
clock; the caller supplies a query time inside that segment. `horizon_galactic_s`, `advance_galactic_s`,
and every input `TemporalLimit.time_s` are remaining seconds from the query.
`accumulated_proper_s` is ship time since departure. `causes` contains immutable
`BoundaryCause` values with the original conditional limit and its converted
galactic instant. `deferred` retains relevant limits with unknown time.
`requires_reevaluation` marks phase, health, job, or invalidation cuts.

For a nominal plan, the selector considers acceleration end, braking start and
profile end. For an active segment, it considers **only that segment's end**,
never the invalidated plan's phases or arrival. Both forms consider the
requested horizon, a supplied health threshold, RUNNING completion candidates, eligible QUEUED
activation checks, and explicit invalidations. It never runs their effects.
The horizon may extend past arrival; profile end cuts first. An invalidation
forces a zero cut and suppresses stale timed predictions until a fresh snapshot
is supplied. The selector is deterministic and does not mutate the plan or
game state.

`galactic_time_at_proper(plan, accumulated_proper_s)` in `nav_physics.py`
inverts the same trajectory used by `sample_travel`: hyperbolic sine during
acceleration, constant peak-beta gamma only during cruise, and time reversal
of acceleration during braking. Exact phase endpoints are taken from the plan.
No fixed step solver or fixed-beta approximation spans acceleration or braking.
Floating-point roundoff remains possible near endpoints. For a segment,
`proper_time_in_segment()` obtains local proper time without subtracting large
accumulated clocks, and `galactic_time_at_segment_proper()` performs the
analytic inverse for the remaining health duration. The returned
`accumulated_proper_s` remains the cumulative ship clock.

The earliest instant is the cut. Causes within four ULPs of that instant are
retained, each with its own `at_galactic_s`; later near causes are **not** due
at the earlier cut and must be rechecked. A limit at the current instant yields
zero duration. The caller must resolve or resample it, or stop; retrying the
same snapshot is not progress. No positive epsilon is added. Exact engine
health equality is still DAMAGED; continuous positive wear crosses into
CRITICAL immediately to its right under the current classifier. A repair completed at equality can change
that right-hand state, but the coordinator does not assume repair success.
`seen_zero_selections` lets the caller pass zero cuts already resolved at this
instant. Repeating the same due causes raises `TemporalResolutionError`, even
if the requested horizon changes; clear the collection only after time advances.
A positive horizon, job ETA or proper-time limit that cannot advance the
floating-point clock raises the same controlled error. The selector does not
round a causal instant forward to manufacture progress.

## Causal integration contract

At an interval start, resolve eligible QUEUED activation checks and sample the
effective electrical load, power quality, radiation, wear rate, propulsion
state, and job ETAs. Select a cut. Integrate physical motion and interval
effects using the **pre-cut** state, including electrical regulation and wear;
advance running job timers without applying their completion effects early.
At the cut, classify the resulting integrity (with the existing strict `<`
threshold), then process job interruption/failure/completion in scheduler order
and apply successful repairs/module effects exactly once. Finally resample
power, wear, thrust and trajectory before using any remaining time. Multiple
jobs and phase changes at the same instant must all be considered. NAV-BRAKE-01B3D
separates timer advancement from completion effects in the productive scheduler.
The historical `_tick_interval()` still calls `_process_jobs()` before
`_apply_degradation()`; splitting `Engine.tick()` alone does not fix that order.

01B2 does not model changing electrical regulation, brownout onset, radiation,
unpredicted interruptions, stochastic job outcomes, or mid-interval external
actions. Those changes invalidate supplied limits and require a fresh cut.
No operational partition invariance is claimed by the mathematical tests.

01B3A adds [motion segments](nav-physics.md); 01B3B selects on the active
segment without scanning its history. Once a segment is consolidated, its
endpoint state and the current active segment suffice for future selection;
full history is optional for diagnostics, while cumulative clocks, physical
position/speed, active maneuver, destination intent and any unresolved cuts
would need persistence later.

### Approved future operating policy (not implemented here)

At engine health **at least 35%**, normal acceleration and braking remain
available, with preventive safety braking initiated at the 35% boundary.
From **15% inclusive to below 35%**, only emergency braking is available.
Below **15%**, or with effectively isolated engines, motion is inertial.
NAV-BRAKE-01B3C adds `Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH`,
`acceleration_available(ship)`, `braking_available(ship)` and
`predict_engine_braking_limit(ship, rate)`. The 15% boundary is inclusive:
braking remains available at equality; positive wear removes it immediately
afterward. The 35% predictor and strict operating-state classifier are unchanged.
`thrust_available()` retains its legacy normal-thrust meaning. These queries
do not authorize fuel use or evaluate maneuver feasibility.

Emergency braking may carry the ship beyond its destination when stopping
before it is impossible; crossing the coordinate at positive speed is not a
successful arrival. After repair, replanning starts from the real position and
speed, preserves the destination where possible, and never accelerates again
if braking had already begun before the failure. Later phases must provide
terminal and hibernation mail warnings on overshoot, a waypoint at the physical
stop even beyond the destination, a block on departure and `route solve` during
physical transit, the current 45-light-year operational waypoint connection
limit, a documented future collision model, and fuel-reservation checks for
every additional powered maneuver. None of those behaviors is active in 01B3C.

## 01B3C causal integration status

The powered `Engine.tick()` adapter is **blocked**. Optional
`ShipState.physical_transit` holds `PhysicalTransitState`; its active
`MotionSegment` and elapsed time alone determine physical position, speed and
local proper time. It also stores original destination, intent, safety-braking
and braking-start flags, and whether replanning is required. Old saves load
with this field set to `None`. No public travel action creates it. If present,
`Engine.tick()` raises before modifying state, preventing silent advancement
of an unimplemented physical maneuver.

The blocker is causal. `Engine._process_jobs()` applies a completed repair
before `Engine._apply_degradation()` for the interval, so the repair may affect
earlier wear. `Engine._integrate_power_interval()` changes battery charge,
quality, shedding and brownout timers, but wear uses one end-of-interval quality
and radiation sample. Thus a threshold predicted at the initial wear rate may
occur earlier under changing conditions. These effects are not yet cut at the
same instants as a changing-β `MotionSegment`. Arbitrarily small ticks supply
neither an exact failure instant nor a verified error bound.

The adapter still requires electrical and radiation boundaries or a verified
continuous-integration error bound;
wear before same-instant repair outcomes; exact 35% and 15% zero-cut handling;
and verified fuel reservation for every powered segment. Only then can the
segment's proper-time integral replace fixed-β clock calculation on the
internal path. Legacy public travel remains the only advancing path here.

## 01B3D scheduler phases

`Engine._begin_job_interval(state)` uses the productive activation, owner,
route-solve, drone-reserve and interruption checks at the current instant. It
returns a one-use `_JobInterval` and events. The frozen work list contains jobs
permitted to advance during the interval. The ordinary `_compute_load_kw`
counts every job marked RUNNING, including one paused for confirmation and
excluded from that work list; this historical load rule is unchanged. A blocked
QUEUED job contributes no load.

`_next_job_completion_s(state, interval)` returns the earliest advancing ETA in
**galactic seconds**, including zero, without changing state or RNG. It includes
unrelated jobs because their completion may release an owner for relevant
queued work. This is a candidate: interruption and random failure can prevent
completion. The pure `nav_coordinator.py` does not execute this scheduler; a
future engine adapter must pass this limit to the coordinator alongside the
physical segment and other limits.

`_advance_job_timers(state, interval, dt)` debits only ETA, rejects intervals
that pass a completion boundary, and applies no job effect. The future caller
must first integrate the preceding physical/electrical/wear interval and set
the galactic game clock to the boundary. Then
`_resolve_job_interval(state, interval)` rechecks interruption, performs the
existing emergency-risk and repair-result checks in scheduler order, applies
each due effect through the single productive `_apply_job_effect()`, and returns
events. A second resolution of the token raises. Calling `_begin_job_interval`
again at that same instant can start newly unblocked QUEUED jobs, including an
ETA-zero job, without advancing the clock artificially. The caller owns event
recording and must not reuse a token across unrelated state changes.

`_process_jobs()` uses those same operations one job at a time, retaining the
old public order and its position before wear. For causal batches, completion
effects may follow wear, so a repair at T cannot affect the preceding interval.
The emergency failure probability still depends on the supplied `dt`; slicing
an interval can change stochastic outcomes and RNG timing. No stochastic
partition invariance is claimed and no balance probability was changed.
Electrical regulation, radiation, wear prediction and powered motion remain
outside this scheduler refactor. `Engine.tick()` still rejects physical transit.

## 01B3E conditional electricity and integrated wear

`nav_electricity.py` captures a frozen `PowerSnapshot` from effective generation,
effective load, battery limits and efficiencies, sampled quality/deficit,
brownout and shedding timers, operating mode, installed module IDs, and
distribution/system/job signatures. The snapshot is an assumption for a single
interval, not persistent state. `capture_power_snapshot()` does not recompute
power: the caller supplies the productive generation and load at the query
instant. A RUNNING job contributes to load according to `_compute_load_kw()`;
the scheduler's advancing work list is a separate matter. Module power effects
are represented by effective powers and module IDs.

For constant generation and load, `battery_energy_after()` uses the productive
charge/discharge caps, efficiencies and battery clamp in **ship proper seconds**.
`power_quality_components()` is shared with the productive engine and retains
the `deficit_ratio` write in `_compute_power_quality()`. Between regulation
events, quality is a clipped piecewise affine function of battery energy: its
SOC branch changes at 10% and 50%, and its outer clamp at quality 0 and 1.
`integrate_quality()` splits at those exact mathematical branches and battery
0/full, then integrates each linear piece by its endpoints. `integrated_wear()`
uses the shared `ordinary_wear_rate()` at quality 0 and 1; affine dependence on
quality makes the result exact for a fixed system, constant internal radiation,
fixed transit/mode, and fixed sustained-brownout multiplier. It returns a loss
amount and never applies it to health. Floating-point rounding remains.

`power_limits()` reports conditional `TemporalLimit`s in proper seconds:
battery 0/10%/50%/full, quality 0.25/0.40/0.55, immediate capacity/low-SOC/
collapse regulation, the 10-second low-quality shedding timer, and the
30-second sustained-brownout timer or immediate timer resets. A threshold cut
with `validity="mathematical_crossing"` is equality, not an applied action.
Future crossings remain candidates. If a snapshot starts exactly on a crossing,
`power_limits()` emits a zero cut with its direction inferred from battery flow.
After handling that cut, the caller passes its `ResolvedElectricalLimit` from
`resolve_electrical_limit()` back as `resolved`. This suppresses only that
processed zero cut; it does not suppress a future crossing. Each marker binds
the immutable snapshot and is ignored for different conditions. It must be
cleared after time advances. An unresolved zero still triggers the existing
`seen_zero_selections` guard in `nav_coordinator.py`; no clock padding is used.
Quality inversion allows only two floating-point ULPs when identifying an
equality reached by analytic propagation.

Strict `<` checks are evaluated from the side entered after a descending
crossing. Thus 10% SOC and quality 0.25 may report a
`validity="post_crossing_check"` regulation at zero even though their strict
condition is false at equality. The 0.40 quality crossing starts the shedding
timer on that side; equality alone is not an expired timer. Operational zero
checks remain pending after a mathematical crossing is resolved and require a
separate resolution after the engine performs or rejects the corresponding
action. Battery availability uses `SOC > 0`; timer expiry uses `>=`.
Sustained brownout already at or above 30 seconds emits neither a new
sustained threshold nor a reset while brownout remains active. A reset is
reported only after brownout ends with a positive timer. Regulation can change
load, so all later cuts from that snapshot become stale. These limits do not
themselves perform shedding, decide the subsequent load, or predict random
outcomes.

`invalidation_reasons()` detects changed effective power/limits, operation or
distribution, modules, systems (including repair/forced isolation), job
status/power, and brownout/shedding timer state. With `elapsed_proper_s`, it also detects battery energy that
departs from the fixed-power prediction. The caller must also invalidate on
reactor changes, job activation/completion, shedding, battery saturation,
mode changes, and any intervening event that changes assumptions. A changed
quality branch calls for reevaluation even when the analytic integral remains
well-defined. The sampled quality/deficit are diagnostic fields; predicted
quality is derived from shared inputs, not from stale sampled values.

`select_next_boundary(..., proper_limits=...)` now accepts multiple proper-time
limits alongside the health limit. It maps each through the active relativistic
segment; job limits stay galactic. A future adapter should gather phase, health,
job and electric candidates, cut at the earliest, integrate preceding
electricity and wear, apply same-instant effects in causal order, then take a
fresh snapshot. It must establish a bound for varying internal radiation and
resolve fuel reservations and emergency-braking policy before enabling physical
movement. Existing `Engine.tick()` and public travel remain unchanged; their
current end-sampled wear is not replaced by this preparatory integral.

## 01B3F spatial radiation forecast

The pure [physical radiation model](nav-radiation.md) predicts ambient rates
from actual segment position, integrates environmental and coupled internal
dose, and calculates ordinary hull and system wear contributions. Its proper
threshold candidates use this coordinator; the first internal crossing under
decreasing ambient radiation is isolated when the branch can be resolved.
Numerically ambiguous contacts remain deferred. Productive physical movement
remains guarded.
