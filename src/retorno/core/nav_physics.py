"""Pure one-dimensional relativistic navigation in an inertial galactic frame.

Distances are metres, galactic and ship proper times are seconds, speed is
dimensionless beta = v/c, and proper acceleration is m/s². Piecewise constant
acceleration is represented by immutable segments. Gravity, fuel, and playable
navigation are outside this model. A physical
light-year uses 365.25 days; Balance.YEAR_S uses 365 days for the game clock.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from retorno.core.temporal import SPEED_OF_LIGHT_KM_S


LIGHT_SPEED_M_S = SPEED_OF_LIGHT_KM_S * 1_000.0
JULIAN_YEAR_S = 365.25 * 86_400.0
LIGHT_YEAR_M = LIGHT_SPEED_M_S * JULIAN_YEAR_S


def light_years_to_metres(distance_ly: float) -> float:
    """Convert physical light-years to metres, using a 365.25-day Julian year."""
    _positive_finite(distance_ly, "distance_ly")
    result = distance_ly * LIGHT_YEAR_M
    if not math.isfinite(result):
        raise ValueError("Converted distance must be finite")
    return result


def metres_to_light_years(distance_m: float) -> float:
    """Convert a nonnegative physical distance in metres to light-years."""
    if not math.isfinite(distance_m) or distance_m < 0:
        raise ValueError("distance_m must be finite and nonnegative")
    return distance_m / LIGHT_YEAR_M


def _positive_finite(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def _gamma_minus_one(beta: float) -> float:
    # Rationalized form avoids cancellation when beta is small.
    inverse_gamma = math.sqrt((1.0 - beta) * (1.0 + beta))
    return beta * beta / (inverse_gamma * (1.0 + inverse_gamma))


@dataclass(frozen=True, slots=True)
class BrakingProfile:
    """Stopping distance (m), galactic duration (s), and proper duration (s)."""

    distance_m: float
    galactic_s: float
    proper_s: float


def braking_profile(beta: float, proper_acceleration_m_s2: float) -> BrakingProfile:
    """Stop from 0 <= beta < 1 with constant opposing proper acceleration.

    Initial beta zero gives a zero-length maneuver. The galactic frame is
    inertial; the returned proper time belongs to the braking ship.
    """
    if not math.isfinite(beta) or not 0 <= beta < 1:
        raise ValueError("beta must be finite and satisfy 0 <= beta < 1")
    _positive_finite(proper_acceleration_m_s2, "proper_acceleration_m_s2")
    c, a = LIGHT_SPEED_M_S, proper_acceleration_m_s2
    inverse_gamma = math.sqrt((1.0 - beta) * (1.0 + beta))
    result = BrakingProfile(
        (c * c / a) * _gamma_minus_one(beta),
        (c / a) * beta / inverse_gamma,
        (c / a) * math.atanh(beta),
    )
    if not all(map(math.isfinite, (result.distance_m, result.galactic_s, result.proper_s))):
        raise ValueError("Braking profile exceeds floating-point range")
    return result


@dataclass(frozen=True, slots=True)
class TravelPlan:
    """Rest-to-rest trajectory; all distances are m and all durations are s.

    Transition instants are elapsed galactic seconds. Zero cruise duration means
    a triangular profile with no cruise phase. The same acceleration magnitude
    applies to acceleration and braking. No game state is retained.
    """

    distance_m: float
    target_beta: float
    peak_beta: float
    proper_acceleration_m_s2: float
    has_cruise: bool
    acceleration_distance_m: float
    cruise_distance_m: float
    braking_distance_m: float
    acceleration_galactic_s: float
    cruise_galactic_s: float
    braking_galactic_s: float
    acceleration_proper_s: float
    cruise_proper_s: float
    braking_proper_s: float
    cruise_start_s: float
    braking_start_s: float
    total_galactic_s: float
    total_proper_s: float


def plan_travel(distance_m: float, target_beta: float, proper_acceleration_m_s2: float) -> TravelPlan:
    """Plan an analytic constant-proper-acceleration, coast, braking journey."""
    _positive_finite(distance_m, "distance_m")
    if not math.isfinite(target_beta) or not 0 < target_beta < 1:
        raise ValueError("target_beta must be finite and satisfy 0 < beta < 1")
    _positive_finite(proper_acceleration_m_s2, "proper_acceleration_m_s2")
    c, a = LIGHT_SPEED_M_S, proper_acceleration_m_s2
    requested = braking_profile(target_beta, a)
    if 2.0 * requested.distance_m >= distance_m:
        # cosh(eta)-1 = a*d/(2*c²); asinh form remains stable near zero.
        u = (a / c) * (distance_m / (2.0 * c))
        eta = 2.0 * math.asinh(math.sqrt(u / 2.0))
        peak_beta = math.tanh(eta)
        if peak_beta == 0.0:
            raise ValueError("Peak speed is below floating-point resolution")
        acceleration_distance = distance_m / 2.0
        cruise_distance = 0.0
        acceleration_galactic = (c / a) * math.sinh(eta)
        acceleration_proper = (c / a) * eta
    else:
        peak_beta = target_beta
        acceleration_distance = requested.distance_m
        cruise_distance = math.fsum((distance_m, -acceleration_distance, -acceleration_distance))
        acceleration_galactic = requested.galactic_s
        acceleration_proper = requested.proper_s
    cruise_galactic = cruise_distance / (peak_beta * c) if cruise_distance else 0.0
    cruise_proper = cruise_galactic * math.sqrt((1.0 - peak_beta) * (1.0 + peak_beta))
    braking_start = acceleration_galactic + cruise_galactic
    total_galactic = braking_start + acceleration_galactic
    total_proper = acceleration_proper + cruise_proper + acceleration_proper
    values = (acceleration_galactic, acceleration_proper, cruise_galactic,
              cruise_proper, braking_start, total_galactic, total_proper)
    if not all(map(math.isfinite, values)) or total_galactic <= braking_start:
        raise ValueError("Travel plan exceeds floating-point resolution or range")
    return TravelPlan(
        distance_m, target_beta, peak_beta, a, cruise_distance > 0.0,
        acceleration_distance, cruise_distance, acceleration_distance,
        acceleration_galactic, cruise_galactic, acceleration_galactic,
        acceleration_proper, cruise_proper, acceleration_proper,
        acceleration_galactic, braking_start, total_galactic, total_proper,
    )


@dataclass(frozen=True, slots=True)
class TravelState:
    """Phase, galactic position (m), beta, and accumulated proper seconds."""

    phase: str
    distance_m: float
    beta: float
    proper_s: float


def _rest_acceleration(elapsed_s: float, acceleration_m_s2: float) -> tuple[float, float, float]:
    return _motion_delta(0.0, acceleration_m_s2, elapsed_s)


def sample_travel(plan: TravelPlan, elapsed_galactic_s: float) -> TravelState:
    """Sample by absolute galactic time without advancing state.

    Phases are acceleration [0, cruise_start), optional cruise
    [cruise_start, braking_start), braking [braking_start, arrival), and
    arrived exactly at arrival. Invalid or later times raise ValueError.
    """
    if not math.isfinite(elapsed_galactic_s) or not 0 <= elapsed_galactic_s <= plan.total_galactic_s:
        raise ValueError("elapsed_galactic_s must be finite and within the journey")
    t = elapsed_galactic_s
    if t == plan.total_galactic_s:
        return TravelState("arrived", plan.distance_m, 0.0, plan.total_proper_s)
    if t < plan.cruise_start_s:
        distance, beta, proper = _rest_acceleration(t, plan.proper_acceleration_m_s2)
        return TravelState("acceleration", distance, beta, proper)
    if plan.has_cruise and t < plan.braking_start_s:
        elapsed = t - plan.cruise_start_s
        return TravelState("cruise", plan.acceleration_distance_m + plan.peak_beta * LIGHT_SPEED_M_S * elapsed,
                           plan.peak_beta, plan.acceleration_proper_s + elapsed * math.sqrt(1.0 - plan.peak_beta**2))
    if t == plan.braking_start_s:
        return TravelState("braking", plan.acceleration_distance_m + plan.cruise_distance_m,
                           plan.peak_beta, plan.acceleration_proper_s + plan.cruise_proper_s)
    remaining = plan.total_galactic_s - t
    reverse_distance, beta, reverse_proper = _rest_acceleration(remaining, plan.proper_acceleration_m_s2)
    return TravelState("braking", plan.distance_m - reverse_distance, beta,
                       plan.total_proper_s - reverse_proper)


def galactic_time_at_proper(plan: TravelPlan, accumulated_proper_s: float) -> float:
    """Invert this plan's accumulated ship time to elapsed galactic seconds.

    The three branches use the same constant-proper-acceleration trajectory as
    ``sample_travel``. Exact phase endpoints are returned from the plan to
    avoid roundoff splitting simultaneous events.
    """
    if not math.isfinite(accumulated_proper_s) or not 0 <= accumulated_proper_s <= plan.total_proper_s:
        raise ValueError("accumulated_proper_s must be finite and within the journey")
    tau = accumulated_proper_s
    accel_end = plan.acceleration_proper_s
    brake_start = accel_end + plan.cruise_proper_s
    if tau == 0.0:
        return 0.0
    if tau == plan.total_proper_s:
        return plan.total_galactic_s
    if tau == accel_end:
        return plan.cruise_start_s
    if tau == brake_start:
        return plan.braking_start_s
    c = LIGHT_SPEED_M_S
    a = plan.proper_acceleration_m_s2
    if tau < accel_end:
        return (c / a) * math.sinh(a * tau / c)
    if tau < brake_start:
        inverse_gamma = math.sqrt((1.0 - plan.peak_beta) * (1.0 + plan.peak_beta))
        return plan.cruise_start_s + (tau - accel_end) / inverse_gamma
    remaining = plan.total_proper_s - tau
    return plan.total_galactic_s - (c / a) * math.sinh(a * remaining / c)


@dataclass(frozen=True, slots=True)
class MotionState:
    """Absolute forward position and accumulated clocks in the galactic frame."""

    galactic_s: float
    distance_m: float
    beta: float
    proper_s: float

    def __post_init__(self) -> None:
        if any(not math.isfinite(value) or value < 0
               for value in (self.galactic_s, self.distance_m, self.proper_s)):
            raise ValueError("motion clocks and distance must be finite and nonnegative")
        if not math.isfinite(self.beta) or not 0 <= self.beta < 1:
            raise ValueError("motion beta must satisfy 0 <= beta < 1")


@dataclass(frozen=True, slots=True)
class MotionSegment:
    """Constant signed proper acceleration, bounded by an exact end speed.

    ``duration_galactic_s`` is a relative interval. ``start`` holds cumulative
    values; the endpoint speed is explicit so braking stops exactly at zero.
    A zero-duration no-op has zero acceleration and end_beta=start.beta.
    """

    start: MotionState
    proper_acceleration_m_s2: float
    duration_galactic_s: float
    end_beta: float

    def __post_init__(self) -> None:
        a, duration = self.proper_acceleration_m_s2, self.duration_galactic_s
        if not math.isfinite(a) or not math.isfinite(duration) or duration < 0:
            raise ValueError("segment acceleration and duration must be finite; duration nonnegative")
        if not math.isfinite(self.end_beta) or not 0 <= self.end_beta < 1:
            raise ValueError("segment end_beta must satisfy 0 <= beta < 1")
        if duration == 0 and (a != 0 or self.end_beta != self.start.beta):
            raise ValueError("a zero-duration segment must be a no-op")
        if a > 0 and self.end_beta < self.start.beta:
            raise ValueError("positive acceleration cannot reduce speed")
        if a < 0 and self.end_beta > self.start.beta:
            raise ValueError("braking cannot increase speed")
        if a == 0 and self.end_beta != self.start.beta:
            raise ValueError("inertial speed must remain constant")
        if duration > 0:
            if self.start.galactic_s + duration == self.start.galactic_s:
                raise ValueError("segment duration is below galactic time resolution")
            distance, beta, proper = _motion_delta(self.start.beta, a, duration)
            if not math.isclose(beta, self.end_beta, rel_tol=0,
                                abs_tol=8 * math.ulp(max(1.0, beta, self.end_beta))):
                raise ValueError("segment end_beta disagrees with its acceleration and duration")
            MotionState(self.start.galactic_s + duration, self.start.distance_m + distance,
                        self.end_beta, self.start.proper_s + proper)


def _momentum(beta: float) -> float:
    """Dimensionless proper velocity, sinh(rapidity), for forward motion."""
    return beta / math.sqrt((1.0 - beta) * (1.0 + beta))


def _motion_delta(beta0: float, acceleration: float, elapsed_s: float) -> tuple[float, float, float]:
    """Return (forward distance, beta, proper time) for a local interval."""
    gamma0_inv = math.sqrt((1.0 - beta0) * (1.0 + beta0))
    if acceleration == 0 or elapsed_s == 0:
        return LIGHT_SPEED_M_S * beta0 * elapsed_s, beta0, elapsed_s * gamma0_inv
    p0 = beta0 / gamma0_inv
    dp = acceleration * (elapsed_s / LIGHT_SPEED_M_S)
    p = p0 + dp
    if not math.isfinite(p) or p < -4 * math.ulp(max(1.0, p0)):
        raise ValueError("maneuver would reverse direction or exceed floating-point range")
    p = max(0.0, p)
    if p == p0:
        return LIGHT_SPEED_M_S * beta0 * elapsed_s, beta0, elapsed_s * gamma0_inv
    gamma0, gamma = math.hypot(1.0, p0), math.hypot(1.0, p)
    actual_dp = p - p0
    gamma_change = actual_dp * ((p + p0) / (gamma + gamma0))
    rapidity_change = math.log1p((actual_dp + gamma_change) / (p0 + gamma0))
    distance = elapsed_s * (LIGHT_SPEED_M_S * ((p + p0) / (gamma + gamma0)))
    proper = elapsed_s * (rapidity_change / actual_dp)
    return distance, p / gamma, proper


def sample_segment(segment: MotionSegment, elapsed_galactic_s: float) -> MotionState:
    """Sample a segment by relative galactic time without changing it."""
    if not math.isfinite(elapsed_galactic_s) or not 0 <= elapsed_galactic_s <= segment.duration_galactic_s:
        raise ValueError("elapsed_galactic_s must lie within the segment")
    start = segment.start
    distance, beta, proper = _motion_delta(start.beta, segment.proper_acceleration_m_s2,
                                            elapsed_galactic_s)
    if elapsed_galactic_s == segment.duration_galactic_s:
        beta = segment.end_beta
    elif segment.proper_acceleration_m_s2 > 0:
        beta = min(beta, segment.end_beta)
    elif segment.proper_acceleration_m_s2 < 0:
        beta = max(beta, segment.end_beta)
    return MotionState(start.galactic_s + elapsed_galactic_s,
                       start.distance_m + distance, beta, start.proper_s + proper)


def proper_time_in_segment(segment: MotionSegment, elapsed_galactic_s: float) -> float:
    """Return local proper seconds without subtracting large cumulative clocks."""
    if not math.isfinite(elapsed_galactic_s) or not 0 <= elapsed_galactic_s <= segment.duration_galactic_s:
        raise ValueError("elapsed_galactic_s must lie within the segment")
    return _motion_delta(segment.start.beta, segment.proper_acceleration_m_s2,
                         elapsed_galactic_s)[2]


def proper_time_between_segment(segment: MotionSegment, left: float, right: float) -> float:
    """Proper duration from a local galactic interval without clock cancellation."""
    if (not math.isfinite(left) or not math.isfinite(right)
            or not 0 <= left <= right <= segment.duration_galactic_s):
        raise ValueError("proper interval must lie within the segment")
    if left == right:
        return 0.0
    at_left = sample_segment(segment, left)
    return _motion_delta(at_left.beta, segment.proper_acceleration_m_s2, right - left)[2]


def galactic_time_at_segment_proper(segment: MotionSegment, elapsed_proper_s: float) -> float:
    """Invert proper seconds since this segment's start to galactic seconds.

    The result is relative to the segment start. The midpoint form of the
    rapidity integral avoids subtracting two nearly equal hyperbolic sines.
    """
    total_proper = proper_time_in_segment(segment, segment.duration_galactic_s)
    if not math.isfinite(elapsed_proper_s) or not 0 <= elapsed_proper_s <= total_proper:
        raise ValueError("elapsed_proper_s must lie within the segment")
    if elapsed_proper_s == 0:
        return 0.0
    if elapsed_proper_s == total_proper:
        return segment.duration_galactic_s
    a = segment.proper_acceleration_m_s2
    if a == 0:
        inverse_gamma = math.sqrt((1.0 - segment.start.beta) * (1.0 + segment.start.beta))
        return elapsed_proper_s / inverse_gamma
    half_delta = a * (elapsed_proper_s / (2 * LIGHT_SPEED_M_S))
    midpoint_rapidity = math.atanh(segment.start.beta) + half_delta
    factor = math.sinh(half_delta) / half_delta if half_delta else 1.0
    elapsed = elapsed_proper_s * (math.cosh(midpoint_rapidity) * factor)
    if not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("proper-time inverse exceeds floating-point range")
    if elapsed > segment.duration_galactic_s:
        raise ValueError("proper-time inverse exceeds segment duration at floating-point resolution")
    return elapsed


def coast_for(start: MotionState, duration_galactic_s: float) -> MotionSegment:
    """Continue at the current physical speed with no thrust."""
    return MotionSegment(start, 0.0, duration_galactic_s, start.beta)


def accelerate_to(start: MotionState, target_beta: float, proper_acceleration_m_s2: float) -> MotionSegment:
    """Accelerate from the current speed, stopping at the requested ceiling."""
    if not math.isfinite(target_beta) or not 0 <= target_beta < 1:
        raise ValueError("target_beta must satisfy 0 <= beta < 1")
    _positive_finite(proper_acceleration_m_s2, "proper_acceleration_m_s2")
    if target_beta <= start.beta:
        return MotionSegment(start, 0.0, 0.0, start.beta)
    duration = LIGHT_SPEED_M_S * ((_momentum(target_beta) - _momentum(start.beta))
                                  / proper_acceleration_m_s2)
    if not math.isfinite(duration) or duration <= 0 or start.galactic_s + duration == start.galactic_s:
        raise ValueError("acceleration duration exceeds range or time resolution")
    return MotionSegment(start, proper_acceleration_m_s2, duration, target_beta)


def brake_to_stop(start: MotionState, proper_deceleration_m_s2: float) -> MotionSegment:
    """Brake from the current speed to rest, using the 01A stopping profile."""
    profile = braking_profile(start.beta, proper_deceleration_m_s2)
    if start.beta == 0:
        return MotionSegment(start, 0.0, 0.0, 0.0)
    if start.galactic_s + profile.galactic_s == start.galactic_s:
        raise ValueError("braking duration is below galactic time resolution")
    return MotionSegment(start, -proper_deceleration_m_s2, profile.galactic_s, 0.0)


def truncate_segment(segment: MotionSegment, elapsed_galactic_s: float) -> MotionSegment:
    """Freeze a planned maneuver at an interruption without changing its past."""
    state = sample_segment(segment, elapsed_galactic_s)
    return MotionSegment(segment.start, segment.proper_acceleration_m_s2,
                         elapsed_galactic_s, state.beta) if elapsed_galactic_s else coast_for(segment.start, 0.0)


def append_segment(segments: tuple[MotionSegment, ...], segment: MotionSegment) -> tuple[MotionSegment, ...]:
    """Return a continuous immutable chain; boundaries belong to the next leg."""
    if segments and segment.start != sample_segment(segments[-1], segments[-1].duration_galactic_s):
        raise ValueError("segment start must equal the previous endpoint")
    return segments + (segment,)


def sample_segments(segments: tuple[MotionSegment, ...], galactic_s: float) -> MotionState:
    """Sample an absolute galactic instant in a continuous segment chain."""
    if not segments or not math.isfinite(galactic_s):
        raise ValueError("segments must be nonempty and galactic_s finite")
    if galactic_s < segments[0].start.galactic_s:
        raise ValueError("galactic_s precedes the segment chain")
    for segment in segments[:-1]:
        end = segment.start.galactic_s + segment.duration_galactic_s
        if galactic_s < end:
            return sample_segment(segment, galactic_s - segment.start.galactic_s)
    last = segments[-1]
    end = last.start.galactic_s + last.duration_galactic_s
    if galactic_s > end:
        raise ValueError("galactic_s exceeds the segment chain")
    if galactic_s == end:
        return sample_segment(last, last.duration_galactic_s)
    return sample_segment(last, galactic_s - last.start.galactic_s)
