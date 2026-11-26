"""Pure selection of the next physical navigation boundary; no game-state writes."""
from __future__ import annotations

from dataclasses import dataclass
import math

from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import (
    MotionSegment, TravelPlan, galactic_time_at_proper,
    galactic_time_at_segment_proper, proper_time_in_segment,
    sample_segment, sample_travel,
)


class TemporalResolutionError(ValueError):
    """A positive causal interval cannot be represented, or zero repeats."""


@dataclass(frozen=True, slots=True)
class BoundaryCause:
    """A source limit and its absolute galactic instant in the profile frame."""

    limit: TemporalLimit
    at_galactic_s: float


@dataclass(frozen=True, slots=True)
class BoundarySelection:
    """Earliest safe cut; near causes must be rechecked before execution."""

    at_galactic_s: float
    advance_galactic_s: float
    accumulated_proper_s: float
    causes: tuple[BoundaryCause, ...]
    deferred: tuple[TemporalLimit, ...]
    requires_reevaluation: bool


def _validate_limit(limit: TemporalLimit) -> None:
    if limit.domain not in {"proper", "galactic"}:
        raise ValueError("limit domain must be proper or galactic")
    if limit.time_s is not None and (not math.isfinite(limit.time_s) or limit.time_s < 0):
        raise ValueError("limit time_s must be finite and nonnegative")


def _zero_signature(selection: BoundarySelection) -> tuple[float, tuple[TemporalLimit, ...]] | None:
    if selection.advance_galactic_s != 0:
        return None
    due = tuple(cause.limit for cause in selection.causes
                if cause.at_galactic_s == selection.at_galactic_s
                and cause.limit.kind != "requested_horizon")
    return (selection.at_galactic_s, due) if due else None


def select_next_boundary(
    plan: TravelPlan | MotionSegment,
    elapsed_galactic_s: float,
    horizon_galactic_s: float,
    *,
    health_limit: TemporalLimit | None = None,
    proper_limits: tuple[TemporalLimit, ...] = (),
    job_limits: tuple[TemporalLimit, ...] = (),
    invalidation_reasons: tuple[str, ...] = (),
    seen_zero_selections: tuple[BoundarySelection, ...] = (),
    elapsed_segment_s: float | None = None,
) -> BoundarySelection:
    """Select the earliest cut of a nominal plan or the active physical segment.

    For a TravelPlan, ``elapsed_galactic_s`` is from departure (origin zero).
    For a MotionSegment it is absolute in the segment's galactic clock.
    The horizon and input limit times are remaining durations from the query.
    Repeating an already seen causal zero cut at the same instant raises;
    callers retain these selections only until galactic time advances.
    No event is executed and no game state is changed.
    """
    if not math.isfinite(horizon_galactic_s) or horizon_galactic_s < 0:
        raise ValueError("horizon_galactic_s must be finite and nonnegative")
    requested_end = elapsed_galactic_s + horizon_galactic_s
    if not math.isfinite(requested_end):
        raise ValueError("requested horizon exceeds floating-point range")
    if horizon_galactic_s > 0 and requested_end == elapsed_galactic_s:
        raise TemporalResolutionError("positive horizon is below galactic clock resolution")
    for reason in invalidation_reasons:
        if not isinstance(reason, str) or not reason:
            raise ValueError("invalidation reasons must be nonempty strings")

    own_limits = (() if health_limit is None else (health_limit,)) + tuple(proper_limits)
    sources = own_limits + tuple(job_limits)
    for limit in sources:
        _validate_limit(limit)
    if health_limit is not None and health_limit.domain != "proper":
        raise ValueError("health_limit must use proper time")
    if any(limit.domain != "proper" for limit in proper_limits):
        raise ValueError("proper_limits must use proper time")
    if any(limit.domain != "galactic" for limit in job_limits):
        raise ValueError("job_limits must use galactic time")
    deferred = tuple(limit for limit in sources if limit.time_s is None)
    candidates: list[BoundaryCause] = []

    if isinstance(plan, TravelPlan):
        current_proper = sample_travel(plan, elapsed_galactic_s).proper_s
        current_accumulated_proper = current_proper
        profile_end = plan.total_galactic_s
        total_local_proper = plan.total_proper_s

        def proper_at(at: float) -> float:
            return sample_travel(plan, at).proper_s

        def galactic_at_proper(target: float) -> float:
            return galactic_time_at_proper(plan, target)

        phases = (
            ("acceleration_end", plan.cruise_start_s) if plan.has_cruise else None,
            ("braking_start", plan.braking_start_s),
        )
        end_kind = "profile_end"
    elif isinstance(plan, MotionSegment):
        start = plan.start.galactic_s
        absolute_end = start + plan.duration_galactic_s
        if not math.isfinite(elapsed_galactic_s) or not start <= elapsed_galactic_s <= absolute_end:
            raise ValueError("elapsed_galactic_s must lie within the active segment")
        local_now = (elapsed_segment_s if elapsed_segment_s is not None else
                     plan.duration_galactic_s if elapsed_galactic_s == absolute_end
                     else elapsed_galactic_s - start)
        if not math.isfinite(local_now) or not 0 <= local_now <= plan.duration_galactic_s:
            raise ValueError("elapsed_segment_s must lie within the active segment")
        # The saved local coordinate is authoritative. Reconstructing it by
        # subtracting two decade-scale absolute clocks can move a boundary by
        # one or more local ULPs.
        remaining_local = plan.duration_galactic_s - local_now
        profile_end = elapsed_galactic_s + remaining_local
        if remaining_local > 0 and profile_end == elapsed_galactic_s:
            profile_end = math.nextafter(elapsed_galactic_s, math.inf)
        current_proper = proper_time_in_segment(plan, local_now)
        current_accumulated_proper = sample_segment(plan, local_now).proper_s
        total_local_proper = proper_time_in_segment(plan, plan.duration_galactic_s)

        def proper_at(at: float) -> float:
            local = (plan.duration_galactic_s if at == profile_end else
                     min(plan.duration_galactic_s, local_now + (at - elapsed_galactic_s)))
            return sample_segment(plan, local).proper_s

        def galactic_at_proper(target: float) -> float:
            local_target = galactic_time_at_segment_proper(plan, target)
            delta = local_target - local_now
            if delta <= 0 and target > current_proper:
                # The local inverse itself rounded to this representable
                # instant. The real crossing lies in the next clock quantum.
                delta = math.ulp(elapsed_galactic_s)
            at = elapsed_galactic_s + delta
            if target > current_proper and at == elapsed_galactic_s:
                at = math.nextafter(elapsed_galactic_s, math.inf)
            return at

        phases = ()
        end_kind = "segment_end"
    else:
        raise TypeError("plan must be TravelPlan or MotionSegment")

    def add(limit: TemporalLimit, at: float) -> None:
        if not math.isfinite(at):
            raise ValueError("boundary exceeds floating-point range")
        if elapsed_galactic_s <= at <= min(profile_end, requested_end):
            candidates.append(BoundaryCause(limit, at))

    add(TemporalLimit("requested_horizon", "galactic", horizon_galactic_s,
                      validity="requested"), requested_end)
    for phase in phases:
        if phase is not None:
            kind, at = phase
            if at > elapsed_galactic_s:
                add(TemporalLimit(kind, "galactic", at - elapsed_galactic_s,
                                  validity="planned_profile"), at)
    add(TemporalLimit(end_kind, "galactic", profile_end - elapsed_galactic_s,
                      validity="active_segment" if end_kind == "segment_end" else "planned_profile"),
        profile_end)

    if not invalidation_reasons:
        for proper_limit in own_limits:
            if proper_limit.time_s is None:
                continue
            target_proper = current_proper + proper_limit.time_s
            if not math.isfinite(target_proper):
                raise ValueError("proper-time limit exceeds floating-point range")
            if (isinstance(plan, TravelPlan) and proper_limit.time_s > 0
                    and target_proper == current_proper):
                raise TemporalResolutionError("positive proper limit is below clock resolution")
            if target_proper <= total_local_proper:
                at = (elapsed_galactic_s if proper_limit.time_s == 0
                      else math.nextafter(elapsed_galactic_s, math.inf)
                      if isinstance(plan, MotionSegment) and target_proper == current_proper
                      else galactic_at_proper(target_proper))
                if at < elapsed_galactic_s or (proper_limit.time_s > 0 and at == elapsed_galactic_s):
                    raise TemporalResolutionError("proper limit cannot advance the galactic clock")
                add(proper_limit, at)
        for limit in job_limits:
            if limit.time_s is not None:
                at = elapsed_galactic_s + limit.time_s
                if limit.time_s > 0 and at == elapsed_galactic_s:
                    raise TemporalResolutionError("positive job ETA is below galactic clock resolution")
                add(limit, at)
    else:
        for reason in invalidation_reasons:
            add(TemporalLimit("prediction_invalidated", "galactic", 0.0,
                              validity="requires_fresh_snapshot", uncertainty_reason=reason),
                elapsed_galactic_s)

    # The horizon can lie beyond the active profile, but its end supplies a cut.
    earliest = min(cause.at_galactic_s for cause in candidates)
    tolerance = 4 * math.ulp(max(1.0, abs(earliest)))
    if isinstance(plan, MotionSegment):
        # A large absolute clock ULP can span whole seconds. Causes are
        # simultaneous only if they also coincide at the query's local scale.
        tolerance = min(tolerance, 4 * math.ulp(max(1.0, abs(horizon_galactic_s))))
    causes = tuple(cause for cause in candidates
                   if cause.at_galactic_s - earliest <= tolerance)
    advance = earliest - elapsed_galactic_s
    if isinstance(plan, MotionSegment):
        # Absolute addition can contract a local duration by an ULP. Keep the
        # local cut itself as the executable duration, and resolve all causes
        # that map to the same representable absolute instant together.
        local_advances = []
        for cause in causes:
            limit = cause.limit
            if limit.kind == "segment_end":
                duration = plan.duration_galactic_s - local_now
            elif limit.domain == "proper" and limit.time_s is not None:
                target = current_proper + limit.time_s
                duration = (galactic_time_at_segment_proper(plan, target) - local_now
                            if limit.time_s > 0 else 0.0)
                if limit.time_s > 0 and duration <= 0:
                    duration = math.ulp(elapsed_galactic_s)
            else:
                duration = limit.time_s or 0.0
            if duration > 0:
                duration = max(duration, math.ulp(elapsed_galactic_s))
            local_advances.append(duration)
        advance = max(local_advances)
        local_at = min(plan.duration_galactic_s, local_now + advance)
        accumulated_at = sample_segment(plan, local_at).proper_s
        if advance > 0:
            for _ in range(256):
                sampled = sample_segment(plan, local_at)
                if (sampled.galactic_s > elapsed_galactic_s
                        and sampled.proper_s > current_accumulated_proper):
                    accumulated_at = sampled.proper_s
                    advance = local_at - local_now
                    break
                next_local = math.nextafter(local_at, math.inf)
                if next_local > plan.duration_galactic_s:
                    raise TemporalResolutionError(
                        "positive interval is below cumulative proper-clock resolution")
                local_at = next_local
            else:
                raise TemporalResolutionError(
                    "positive interval is below cumulative proper-clock resolution")
    else:
        accumulated_at = proper_at(earliest)
    if earliest > elapsed_galactic_s and accumulated_at == current_accumulated_proper:
        raise TemporalResolutionError("positive interval is below cumulative proper-clock resolution")
    selection = BoundarySelection(
        earliest, advance, accumulated_at, causes, deferred,
        any(cause.limit.kind != "requested_horizon" for cause in causes),
    )
    signature = _zero_signature(selection)
    if signature is not None and any(_zero_signature(previous) == signature
                                     for previous in seen_zero_selections):
        raise TemporalResolutionError("repeated zero boundary requires resolution or a fresh snapshot")
    return selection
