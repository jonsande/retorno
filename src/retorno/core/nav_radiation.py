"""Pure spatial radiation and coupled hull exposure for physical motion.

Rates are rad/s. Doses integrate those rates in the explicitly named clock.
The profile is a conditional snapshot, not a persistent radiation field.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from retorno.config.balance import Balance
from retorno.core.nav_boundaries import TemporalLimit, ordinary_wear_rate
from retorno.core.nav_physics import (
    LIGHT_SPEED_M_S, MotionSegment, proper_time_in_segment, sample_segment,
)
from retorno.model.systems import ShipSystem


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _nonnegative(value: float, name: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class RadiationProfile:
    """Known endpoint rates on a one-dimensional physical route, in metres."""

    start_m: float
    end_m: float
    start_rad_per_s: float
    end_rad_per_s: float

    def __post_init__(self) -> None:
        for name in ("start_m", "end_m", "start_rad_per_s", "end_rad_per_s"):
            _nonnegative(getattr(self, name), name)
        if self.end_m <= self.start_m:
            raise ValueError("radiation route must have positive physical length")

    @property
    def slope_rad_per_s_m(self) -> float:
        return (self.end_rad_per_s - self.start_rad_per_s) / (self.end_m - self.start_m)

    def ambient_at(self, position_m: float) -> float:
        """Spatial interpolation; hold the nearest endpoint outside the route."""
        _nonnegative(position_m, "position_m")
        if position_m <= self.start_m:
            return self.start_rad_per_s
        if position_m >= self.end_m:
            return self.end_rad_per_s
        return self.start_rad_per_s + self.slope_rad_per_s_m * (position_m - self.start_m)


def internal_radiation_rate(env_rad_per_s: float, hull_integrity: float) -> float:
    """The productive ingress rule at the *current* hull integrity."""
    if not math.isfinite(env_rad_per_s) or not math.isfinite(hull_integrity):
        raise ValueError("radiation and hull integrity must be finite")
    hull = _unit(hull_integrity)
    ingress = (Balance.HULL_INTERNAL_RAD_MIN_INGRESS
               + (1.0 - hull) * (Balance.HULL_INTERNAL_RAD_MAX_INGRESS
                                 - Balance.HULL_INTERNAL_RAD_MIN_INGRESS))
    ingress = min(Balance.HULL_INTERNAL_RAD_MAX_INGRESS,
                  max(Balance.HULL_INTERNAL_RAD_MIN_INGRESS, ingress))
    return max(0.0, env_rad_per_s) * ingress


def hull_decay_rate(env_rad_per_s: float, *, in_transit: bool, hibernating: bool) -> float:
    """The productive ordinary hull loss per proper second; no state update."""
    if not math.isfinite(env_rad_per_s):
        raise ValueError("environmental radiation must be finite")
    env_norm = _unit(env_rad_per_s / Balance.HULL_RAD_REF) if Balance.HULL_RAD_REF > 0 else 0.0
    multiplier = 1.0 + env_norm * (Balance.HULL_RAD_DECAY_MULT_MAX - 1.0)
    if in_transit or hibernating:
        multiplier *= Balance.HULL_TRANSIT_DECAY_MULT
    return Balance.HULL_BASE_DECAY_PER_S * multiplier


def _position_cut(segment: MotionSegment, target_m: float, left: float, right: float) -> float:
    """Monotone position inverse bracketed to representable galactic time."""
    lo, hi = left, right
    for _ in range(256):
        mid = lo + (hi - lo) / 2.0
        if mid == lo or mid == hi:
            return hi
        if sample_segment(segment, mid).distance_m < target_m:
            lo = mid
        else:
            hi = mid
    raise ValueError("position crossing did not converge")


def _proper_moments(
    profile: RadiationProfile, segment: MotionSegment, left: float, right: float,
) -> tuple[float, float, float]:
    """Exact proper seconds, ambient dose, and its first proper-time moment.

    The caller cuts at spatial endpoint and hull-radiation saturation branches.
    Stable hyperbolic series avoid cancellation near zero acceleration/time.
    """
    dtau = proper_time_in_segment(segment, right) - proper_time_in_segment(segment, left)
    if dtau < 0 or (right > left and dtau == 0):
        raise ValueError("proper duration is below floating-point resolution")
    start = sample_segment(segment, left)
    middle = sample_segment(segment, left + (right - left) / 2.0)
    slope = (profile.slope_rad_per_s_m
             if profile.start_m < middle.distance_m < profile.end_m else 0.0)
    env0 = profile.ambient_at(start.distance_m)
    if dtau == 0:
        return 0.0, 0.0, 0.0
    inverse_gamma = math.sqrt((1.0 - start.beta) * (1.0 + start.beta))
    p0 = start.beta / inverse_gamma
    gamma0 = 1.0 / inverse_gamma
    acceleration = segment.proper_acceleration_m_s2
    z = acceleration * dtau / LIGHT_SPEED_M_S
    if abs(z) < 1e-3:
        z2 = z * z
        a1 = .5 + z2 / 24 + z2 * z2 / 720 + z2**3 / 40320
        b1 = 1 / 6 + z2 / 120 + z2 * z2 / 5040 + z2**3 / 362880
        a2 = 1 / 3 + z2 / 30 + z2 * z2 / 840 + z2**3 / 45360
        b2 = 1 / 8 + z2 / 144 + z2 * z2 / 5760 + z2**3 / 403200
    else:
        coshm1 = 2 * math.sinh(z / 2)**2
        sinh = math.sinh(z)
        cosh = 1 + coshm1
        a1 = coshm1 / z**2
        b1 = (sinh - z) / z**3
        a2 = (z * cosh - sinh) / z**3
        b2 = (z * sinh - coshm1 - z**2 / 2) / z**4
    distance_moment = (LIGHT_SPEED_M_S * p0 * dtau**2 * a1
                       + acceleration * gamma0 * dtau**3 * b1)
    timed_distance_moment = (LIGHT_SPEED_M_S * p0 * dtau**3 * a2
                             + acceleration * gamma0 * dtau**4 * b2)
    dose = math.fsum((env0 * dtau, slope * distance_moment))
    first_moment = math.fsum((env0 * dtau**2 / 2, slope * timed_distance_moment))
    if not all(math.isfinite(value) for value in (dose, first_moment)):
        raise ValueError("radiation integral exceeds floating-point range")
    return dtau, max(0.0, dose), max(0.0, first_moment)


def _integrate_controlled(
    function: Callable[[float], float], left: float, right: float,
    *, abs_tol: float, rel_tol: float, max_depth: int = 28,
) -> tuple[float, float]:
    """Adaptive Simpson integral with an explicit summed error estimate.

    Raises rather than returning an unconverged estimate. Smooth intervals
    are supplied by the caller; remaining clamp kinks are handled adaptively.
    """
    if left == right:
        return 0.0, 0.0
    width = right - left

    def value(u: float) -> float:
        # A rounded left + width may exceed right by one ULP near a segment end.
        result = function(min(right, max(left, left + u * width))) * width
        if not math.isfinite(result):
            raise ValueError("radiation integrand is not finite")
        return result

    fa, fm, fb = value(0), value(.5), value(1)
    initial = (fa + 4 * fm + fb) / 6

    def recurse(a: float, b: float, va: float, vm: float, vb: float,
                whole: float, depth: int, local_abs_tol: float) -> tuple[float, float]:
        mid = (a + b) / 2
        lm, rm = (a + mid) / 2, (mid + b) / 2
        if lm == a or rm == b:
            raise ValueError("radiation quadrature reached floating-point resolution")
        vl, vr = value(lm), value(rm)
        left_sum = (mid - a) * (va + 4 * vl + vm) / 6
        right_sum = (b - mid) * (vm + 4 * vr + vb) / 6
        estimate = left_sum + right_sum
        error = abs(estimate - whole) / 15
        if error <= max(local_abs_tol, rel_tol * abs(estimate)):
            return estimate + (estimate - whole) / 15, error
        if depth == 0:
            raise ValueError("radiation quadrature did not converge")
        lv, le = recurse(a, mid, va, vl, vm, left_sum, depth - 1, local_abs_tol / 2)
        rv, re = recurse(mid, b, vm, vr, vb, right_sum, depth - 1, local_abs_tol / 2)
        return lv + rv, le + re

    result, error = recurse(0, 1, fa, fm, fb, initial, max_depth, abs_tol)
    if error > max(abs_tol, rel_tol * abs(result)):
        raise ValueError("radiation quadrature exceeded requested tolerance")
    return result, error


def _section_hull_loss(dtau: float, env_dose: float, saturated: bool, base_rate: float) -> float:
    if saturated:
        return base_rate * Balance.HULL_RAD_DECAY_MULT_MAX * dtau
    return base_rate * (dtau + (Balance.HULL_RAD_DECAY_MULT_MAX - 1.0)
                        * env_dose / Balance.HULL_RAD_REF)


def _spatial_cuts(
    profile: RadiationProfile, segment: MotionSegment, left: float, right: float,
) -> tuple[float, ...]:
    start_x = sample_segment(segment, left).distance_m
    end_x = sample_segment(segment, right).distance_m
    cuts = [left, right]
    positions = [profile.start_m, profile.end_m]
    slope = profile.slope_rad_per_s_m
    if slope:
        positions.append(profile.start_m + (Balance.HULL_RAD_REF - profile.start_rad_per_s) / slope)
    for position in positions:
        if start_x < position < end_x:
            cuts.append(_position_cut(segment, position, left, right))
    return tuple(sorted(set(cuts)))


def _predicted_hull(
    profile: RadiationProfile, segment: MotionSegment, left: float, right: float,
    hull: float, *, in_transit: bool, hibernating: bool, god_active: bool,
) -> float:
    if god_active or hull == 0:
        return hull
    base_rate = Balance.HULL_BASE_DECAY_PER_S * (
        Balance.HULL_TRANSIT_DECAY_MULT if in_transit or hibernating else 1.0)
    cuts = _spatial_cuts(profile, segment, left, right)
    for a, b in zip(cuts, cuts[1:]):
        midpoint = sample_segment(segment, a + (b-a)/2)
        saturated = profile.ambient_at(midpoint.distance_m) >= Balance.HULL_RAD_REF
        dtau, dose, _ = _proper_moments(profile, segment, a, b)
        hull = max(0.0, hull - _section_hull_loss(dtau, dose, saturated, base_rate))
    return hull


@dataclass(frozen=True, slots=True)
class RadiationIntegral:
    galactic_s: float
    proper_s: float
    environmental_galactic_rad: float
    environmental_proper_rad: float
    internal_proper_rad: float
    normalized_internal_proper_s: float
    hull_start: float
    hull_end: float
    galactic_error_estimate_rad: float
    normalized_error_estimate_s: float

    @property
    def hull_loss(self) -> float:
        return self.hull_start - self.hull_end


def integrate_segment_radiation(
    profile: RadiationProfile, segment: MotionSegment,
    start_galactic_s: float, end_galactic_s: float, hull_integrity: float,
    *, in_transit: bool = True, hibernating: bool = False,
    god_active: bool = False, abs_tol: float = 1e-8, rel_tol: float = 1e-10,
) -> RadiationIntegral:
    """Integrate a local segment subinterval and its causal ordinary hull loss.

    Hull and internal radiation are coupled at each proper instant. The
    spatial field is conditional on fixed endpoint rates and segment geometry.
    Numerical estimates cover galactic dose and clipped internal wear factor;
    proper dose, hull loss and internal dose use analytic branch integrals.
    """
    for value, name in ((start_galactic_s, "start_galactic_s"),
                        (end_galactic_s, "end_galactic_s"),
                        (hull_integrity, "hull_integrity"),
                        (abs_tol, "abs_tol"), (rel_tol, "rel_tol")):
        _nonnegative(value, name)
    if not 0 <= start_galactic_s <= end_galactic_s <= segment.duration_galactic_s:
        raise ValueError("subinterval must lie within the segment")
    if hull_integrity > 1 or abs_tol == 0 or rel_tol == 0:
        raise ValueError("hull integrity and tolerances are out of range")
    total_proper = (proper_time_in_segment(segment, end_galactic_s)
                    - proper_time_in_segment(segment, start_galactic_s))
    if start_galactic_s == end_galactic_s:
        return RadiationIntegral(0, 0, 0, 0, 0, 0, hull_integrity, hull_integrity, 0, 0)
    cuts = _spatial_cuts(profile, segment, start_galactic_s, end_galactic_s)
    base_rate = Balance.HULL_BASE_DECAY_PER_S
    if in_transit or hibernating:
        base_rate *= Balance.HULL_TRANSIT_DECAY_MULT
    current_hull = hull_integrity
    gal_dose = proper_dose = internal_dose = normalized = 0.0
    gal_error = normalized_error = 0.0

    for left, right in zip(cuts, cuts[1:]):
        if left == right:
            continue
        midpoint = sample_segment(segment, left + (right - left) / 2)
        saturated = profile.ambient_at(midpoint.distance_m) >= Balance.HULL_RAD_REF
        dtau, env_dose, env_moment = _proper_moments(profile, segment, left, right)
        loss = 0.0 if god_active else _section_hull_loss(dtau, env_dose, saturated, base_rate)
        if not god_active and current_hull > 0 and loss > current_hull:
            lo, hi = left, right
            for _ in range(256):
                mid = lo + (hi - lo) / 2
                if mid == lo or mid == hi:
                    break
                local_tau, local_dose, _ = _proper_moments(profile, segment, left, mid)
                if _section_hull_loss(local_tau, local_dose, saturated, base_rate) < current_hull:
                    lo = mid
                else:
                    hi = mid
            # Process the physical floor as two analytic pieces.
            subcuts = ((left, hi), (hi, right)) if left < hi < right else ((left, right),)
        else:
            subcuts = ((left, right),)

        for a, b in subcuts:
            if a == b:
                continue
            dtau, env_dose, env_moment = _proper_moments(profile, segment, a, b)
            section_hull = current_hull
            section_loss = 0.0 if god_active else _section_hull_loss(dtau, env_dose, saturated, base_rate)
            if section_hull <= 0:
                section_internal = env_dose * Balance.HULL_INTERNAL_RAD_MAX_INGRESS
            else:
                ingress = (Balance.HULL_INTERNAL_RAD_MIN_INGRESS
                           + (1 - section_hull) * (Balance.HULL_INTERNAL_RAD_MAX_INGRESS
                                                   - Balance.HULL_INTERNAL_RAD_MIN_INGRESS))
                delta_ingress = (Balance.HULL_INTERNAL_RAD_MAX_INGRESS
                                 - Balance.HULL_INTERNAL_RAD_MIN_INGRESS)
                if god_active:
                    coupling = 0.0
                elif saturated:
                    coupling = base_rate * Balance.HULL_RAD_DECAY_MULT_MAX * env_moment
                else:
                    coupling = base_rate * (env_moment
                                            + (Balance.HULL_RAD_DECAY_MULT_MAX - 1.0)
                                            * env_dose**2 / (2 * Balance.HULL_RAD_REF))
                section_internal = ingress * env_dose + delta_ingress * coupling
            internal_dose += section_internal
            current_hull = max(0.0, section_hull - section_loss)
            proper_dose += env_dose

            if profile.ambient_at(sample_segment(segment, a).distance_m) == profile.ambient_at(
                    sample_segment(segment, b).distance_m):
                section_gal = profile.ambient_at(sample_segment(segment, a).distance_m) * (b - a)
                section_gal_error = 0.0
            else:
                section_gal, section_gal_error = _integrate_controlled(
                    lambda t: profile.ambient_at(sample_segment(segment, t).distance_m),
                    a, b, abs_tol=abs_tol * (b-a) / (end_galactic_s-start_galactic_s),
                    rel_tol=rel_tol)
            gal_dose += section_gal
            gal_error += section_gal_error

            def normalized_at(t: float) -> float:
                elapsed_tau, local_dose, _ = _proper_moments(profile, segment, a, t)
                loss_at = 0.0 if god_active else _section_hull_loss(
                    elapsed_tau, local_dose, saturated, base_rate)
                hull_at = max(0.0, section_hull - loss_at)
                motion = sample_segment(segment, t)
                rate = internal_radiation_rate(profile.ambient_at(motion.distance_m), hull_at)
                gamma_inverse = math.sqrt((1.0 - motion.beta) * (1.0 + motion.beta))
                return _unit(rate / Balance.R_REF) * gamma_inverse

            section_norm, section_norm_error = _integrate_controlled(
                normalized_at, a, b,
                abs_tol=abs_tol * (b-a) / (end_galactic_s-start_galactic_s),
                rel_tol=rel_tol)
            normalized += section_norm
            normalized_error += section_norm_error

    if gal_error > max(abs_tol, rel_tol * abs(gal_dose)):
        raise ValueError("galactic radiation dose exceeded requested tolerance")
    if normalized_error > max(abs_tol, rel_tol * abs(normalized)):
        raise ValueError("normalized radiation integral exceeded requested tolerance")
    return RadiationIntegral(
        end_galactic_s - start_galactic_s, total_proper, gal_dose, proper_dose,
        internal_dose, normalized, hull_integrity, current_hull,
        gal_error, normalized_error,
    )


def integrated_system_wear(
    system: ShipSystem, exposure: RadiationIntegral, quality_proper_s: float,
    *, in_transit: bool, op_mode: str, brownout_sustained: bool = False,
    god_active: bool = False,
) -> float:
    """Combine electric and radiation integrals through shared wear factors."""
    if not math.isfinite(quality_proper_s) or not 0 <= quality_proper_s <= exposure.proper_s:
        raise ValueError("quality integral must lie within the exposure interval")
    if god_active:
        return 0.0
    def rate(quality: float, radiation: float) -> float:
        return ordinary_wear_rate(system, quality, brownout_sustained, radiation,
                                  in_transit=in_transit, op_mode=op_mode)
    base = rate(1, 0)
    power_delta = rate(0, 0) - base
    radiation_delta = rate(1, Balance.R_REF) - base
    return (base * exposure.proper_s
            + power_delta * (exposure.proper_s - quality_proper_s)
            + radiation_delta * exposure.normalized_internal_proper_s)


def first_integrated_wear_at(
    system: ShipSystem, profile: RadiationProfile, segment: MotionSegment,
    start_galactic_s: float, end_galactic_s: float, hull_integrity: float,
    target_health: float, *, in_transit: bool, op_mode: str,
    hibernating: bool, quality_proper_s_at: Callable[[RadiationIntegral], float],
) -> float | None:
    """First representable local galactic instant attaining cumulative wear.

    The caller guarantees a fixed electrical regime and nondecreasing ordinary
    wear on this interval. Each probe reintegrates radiation and hull loss from
    the *same* initial state; a point wear rate is never extrapolated. The
    returned upper bracket differs from the last below-target float by one
    representable instant. None means the verified endpoint is below target.
    """
    if not math.isfinite(target_health) or target_health < 0:
        raise ValueError("target health must be finite and nonnegative")
    if (not math.isfinite(start_galactic_s) or not math.isfinite(end_galactic_s)
            or not 0 <= start_galactic_s <= end_galactic_s <= segment.duration_galactic_s):
        raise ValueError("wear search must remain inside the active segment")
    if system.health <= target_health:
        return start_galactic_s

    def wear_at(at: float) -> float:
        exposure = integrate_segment_radiation(
            profile, segment, start_galactic_s, at, hull_integrity,
            hibernating=hibernating,
        )
        return integrated_system_wear(
            system, exposure, quality_proper_s_at(exposure),
            in_transit=in_transit, op_mode=op_mode,
        )

    if system.health - wear_at(end_galactic_s) > target_health:
        return None
    lower, upper = start_galactic_s, end_galactic_s
    for _ in range(1075):  # Binary64 has at most 1074 positive subnormal steps.
        midpoint = lower + (upper - lower) / 2
        if midpoint == lower or midpoint == upper:
            break
        if system.health - wear_at(midpoint) <= target_health:
            upper = midpoint
        else:
            lower = midpoint
    else:
        raise ValueError("integrated wear threshold could not be isolated")
    if upper <= start_galactic_s:
        raise ValueError("positive wear threshold is below galactic resolution")
    return upper


@dataclass(frozen=True, slots=True)
class ResolvedRadiationLimit:
    """A processed zero cut bound to the complete radiological snapshot."""

    kind: str
    profile: RadiationProfile
    segment: MotionSegment
    at_galactic_s: float
    hull_integrity: float | None = None
    in_transit: bool = True
    hibernating: bool = False
    god_active: bool = False


def _radiation_limit(
    kind: str, seconds: float, validity: str,
) -> TemporalLimit:
    return TemporalLimit(kind, "proper", seconds, validity=validity,
                         uncertainty_reason="classification_or_notification_requires_reevaluation")


def environmental_limits(
    profile: RadiationProfile, segment: MotionSegment, current_galactic_s: float,
    *, hibernating: bool = False, hull_integrity: float | None = None,
    in_transit: bool = True, god_active: bool = False,
    resolved: frozenset[ResolvedRadiationLimit] = frozenset(),
) -> tuple[TemporalLimit, ...]:
    """Future spatial/ambient classification and wake candidates in proper s.

    An upward equality is already active under the productive `>=` rule. A
    downward equality needs a post-crossing check at zero and a resolution
    marker before it can be omitted at this instant.
    """
    _nonnegative(current_galactic_s, "current_galactic_s")
    if current_galactic_s > segment.duration_galactic_s:
        raise ValueError("current time exceeds segment")
    if hull_integrity is not None:
        _nonnegative(hull_integrity, "hull_integrity")
        if hull_integrity > 1:
            raise ValueError("hull integrity must not exceed one")
    now = sample_segment(segment, current_galactic_s)
    end = sample_segment(segment, segment.duration_galactic_s)
    if now.distance_m >= end.distance_m or profile.slope_rad_per_s_m == 0:
        return ()
    thresholds = (
        ("ambient_elevated", Balance.RAD_LEVEL_ENV_ELEVATED),
        ("ambient_high", Balance.RAD_LEVEL_ENV_HIGH),
        ("ambient_extreme", Balance.RAD_LEVEL_ENV_EXTREME),
        ("hull_radiation_saturation", Balance.HULL_RAD_REF),
    )
    if hibernating and Balance.HIBERNATE_WAKE_ON_ENV_RAD_THRESHOLD:
        thresholds += (("hibernate_ambient_wake", Balance.HIBERNATE_WAKE_ENV_RAD_THRESHOLD_RAD_PER_S),)
    limits = []
    for kind, threshold in thresholds:
        if not math.isfinite(threshold) or threshold < 0:
            continue
        slope = profile.slope_rad_per_s_m
        position = profile.start_m + (threshold - profile.start_rad_per_s) / slope
        if not profile.start_m <= position <= profile.end_m:
            continue
        if ((slope < 0 and position == profile.end_m)
                or (slope > 0 and position == profile.start_m)):
            continue
        if kind == "hibernate_ambient_wake" and slope < 0:
            continue
        if position < now.distance_m or position > end.distance_m:
            continue
        at_equality = abs(position - now.distance_m) <= 2 * max(
            math.ulp(position), math.ulp(now.distance_m))
        if at_equality:
            if slope >= 0 or kind in {"hibernate_ambient_wake", "hull_radiation_saturation"}:
                continue
            limit = _radiation_limit(kind, 0.0, "post_crossing_check")
            marker = ResolvedRadiationLimit(kind, profile, segment, current_galactic_s,
                                            hull_integrity, in_transit, hibernating, god_active)
            if marker not in resolved:
                limits.append(limit)
            continue
        if not now.distance_m < position < end.distance_m:
            continue
        at = _position_cut(segment, position, current_galactic_s, segment.duration_galactic_s)
        proper = (proper_time_in_segment(segment, at)
                  - proper_time_in_segment(segment, current_galactic_s))
        if proper <= 0:
            raise ValueError("radiation crossing is below proper-time resolution")
        limits.append(_radiation_limit(kind, proper, "fixed_segment_and_radiation_profile"))
    return tuple(sorted(limits, key=lambda limit: (limit.time_s, limit.kind)))


def _first_internal_crossing(
    profile: RadiationProfile, segment: MotionSegment, cuts: tuple[float, ...],
    threshold: float, hull_at: Callable[[float], float], *, god_active: bool,
    in_transit: bool, hibernating: bool,
) -> tuple[float | None, bool]:
    """Left-first root isolation; an unresolved interval precedes later roots.

    E is monotone on every spatial branch and ingress is nondecreasing. Their
    endpoint products enclose E*I. On a smooth branch the proper-time derivative
    is E' I + E I'; interval endpoint bounds can prove its sign. Floating-point
    ambiguity or an unresolved tangency returns uncertainty, never a guessed cut.
    """
    start, end = cuts[0], cuts[-1]
    delta_ingress = (Balance.HULL_INTERNAL_RAD_MAX_INGRESS
                     - Balance.HULL_INTERNAL_RAD_MIN_INGRESS)
    cached: dict[float, tuple[float, float, float]] = {}

    def state(at: float) -> tuple[float, float, float]:
        if at not in cached:
            motion = sample_segment(segment, at)
            env = profile.ambient_at(motion.distance_m)
            hull = hull_at(at)
            ingress = Balance.HULL_INTERNAL_RAD_MIN_INGRESS + (1-hull)*delta_ingress
            cached[at] = env, ingress, motion.beta
        return cached[at]

    def rate(at: float) -> float:
        env, ingress, _ = state(at)
        return env * ingress

    def bounds(a: float, b: float) -> tuple[float, float, float, float]:
        ea, ia, ba = state(a)
        eb, ib, bb = state(b)
        # E is monotone in position; hull loss makes I nondecreasing.
        low = min(ea, eb) * min(ia, ib)
        high = max(ea, eb) * max(ia, ib)
        midpoint_x = sample_segment(segment, a + (b-a)/2).distance_m
        slope = (profile.slope_rad_per_s_m
                 if profile.start_m < midpoint_x < profile.end_m else 0.0)
        pa = ba / math.sqrt((1-ba)*(1+ba))
        pb = bb / math.sqrt((1-bb)*(1+bb))
        ep_a, ep_b = slope * LIGHT_SPEED_M_S * pa, slope * LIGHT_SPEED_M_S * pb
        if god_active or hull_at(a) == 0:
            ip_a = ip_b = 0.0
        else:
            ip_a = delta_ingress * hull_decay_rate(
                ea, in_transit=in_transit, hibernating=hibernating)
            ip_b = delta_ingress * hull_decay_rate(
                eb, in_transit=in_transit, hibernating=hibernating)
        derivative_terms = (ep * ingress for ep in (ep_a, ep_b)
                            for ingress in (ia, ib))
        first = tuple(derivative_terms)
        second = tuple(env * ip for env in (ea, eb) for ip in (ip_a, ip_b))
        derivative_low = min(first) + min(second)
        derivative_high = max(first) + max(second)
        return (math.nextafter(low, -math.inf), math.nextafter(high, math.inf),
                math.nextafter(derivative_low, -math.inf),
                math.nextafter(derivative_high, math.inf))

    initial = rate(start)
    if abs(initial-threshold) <= 2*max(math.ulp(initial), math.ulp(threshold)):
        # Equality belongs to the upper productive category. Its descending
        # posterior side needs a zero cut; a tangency cannot be decided here.
        if (state(start)[0] == state(end)[0]
                and (state(start)[0] == 0 or hull_at(start) == hull_at(end))):
            return None, False
        first_b = cuts[1]
        _, _, derivative_low, derivative_high = bounds(start, first_b)
        if derivative_high < 0:
            return start, False
        if derivative_low > 0 and (
                profile.slope_rad_per_s_m >= 0
                or state(start)[0] == state(end)[0]):
            return None, False
        return None, True

    visited = 0

    def confirm(root: float) -> tuple[float | None, bool]:
        """Reject roots whose side separation is below numerical resolution."""
        probe = max(1024 * math.ulp(root), 1e-12 * (end-start))
        margin = 64 * math.ulp(threshold)

        def side(at: float) -> int:
            value = rate(at)
            return -1 if value < threshold-margin else 1 if value > threshold+margin else 0

        for _ in range(40):
            before = max(start, root-probe)
            after = min(end, root+probe)
            earlier, later = side(before), side(after)
            if (earlier * later == -1 or (root == end and earlier != 0)
                    or (root in cuts and earlier != 0
                        and abs(rate(root)-threshold) <= margin)):
                return root, False
            if earlier != 0 and later != 0:
                break
            if before == start and after == end:
                break
            probe *= 2
        return None, True

    def search(a: float, b: float, depth: int) -> tuple[float | None, bool]:
        nonlocal visited
        visited += 1
        if visited > 8192:
            return None, True
        lower, upper, dlow, dhigh = bounds(a, b)
        if threshold < lower or threshold > upper:
            return None, False
        fa, fb = rate(a), rate(b)
        if dlow > 0 or dhigh < 0 or (dlow == 0 and dhigh == 0):
            if fa == threshold:
                return confirm(a)
            if fb == threshold:
                return confirm(b)
            if (fa < threshold < fb) or (fb < threshold < fa):
                rising = fb > fa
                lo, hi = a, b
                for _ in range(256):
                    mid = lo + (hi-lo)/2
                    if mid == lo or mid == hi:
                        break
                    if (rate(mid) < threshold) == rising:
                        lo = mid
                    else:
                        hi = mid
                return confirm(hi)
            return None, False
        mid = a + (b-a)/2
        if depth == 0 or mid == a or mid == b:
            return None, True
        first_root, uncertain = search(a, mid, depth-1)
        if first_root is not None or uncertain:
            return first_root, uncertain
        return search(mid, b, depth-1)

    for a, b in zip(cuts, cuts[1:]):
        root, uncertain = search(a, b, 48)
        if root is not None or uncertain:
            return root, uncertain
    return None, False


def radiation_limits(
    profile: RadiationProfile, segment: MotionSegment, current_galactic_s: float,
    hull_integrity: float, *, in_transit: bool = True, hibernating: bool = False,
    god_active: bool = False, resolved: frozenset[ResolvedRadiationLimit] = frozenset(),
) -> tuple[TemporalLimit, ...]:
    """Ambient, hull-floor and first internal cuts, with explicit uncertainty."""
    _nonnegative(hull_integrity, "hull_integrity")
    if hull_integrity > 1:
        raise ValueError("hull integrity must not exceed one")
    limits = list(environmental_limits(profile, segment, current_galactic_s,
                                       hibernating=hibernating,
                                       hull_integrity=hull_integrity,
                                       in_transit=in_transit, god_active=god_active,
                                       resolved=resolved))
    now = sample_segment(segment, current_galactic_s)
    end_time = segment.duration_galactic_s
    end = sample_segment(segment, end_time)
    if current_galactic_s == end_time:
        return tuple(limits)

    def hull_at(at: float) -> float:
        return _predicted_hull(profile, segment, current_galactic_s, at, hull_integrity,
                               in_transit=in_transit, hibernating=hibernating,
                               god_active=god_active)

    floor_at = None
    if hull_integrity > 0 and not god_active and hull_at(end_time) == 0:
        lo, hi = current_galactic_s, end_time
        for _ in range(256):
            mid = lo + (hi-lo)/2
            if mid == lo or mid == hi:
                break
            if hull_at(mid) > 0:
                lo = mid
            else:
                hi = mid
        proper = (proper_time_in_segment(segment, hi)
                  - proper_time_in_segment(segment, current_galactic_s))
        if proper > 0:
            floor_at = hi
            limits.append(_radiation_limit("hull_integrity_zero", proper,
                                           "ordinary_hull_wear_only"))

    cuts = list(_spatial_cuts(profile, segment, current_galactic_s, end_time))
    if floor_at is not None and cuts[0] < floor_at < cuts[-1]:
        cuts.append(floor_at)
    cuts = tuple(sorted(set(cuts)))
    thresholds = (
        ("internal_elevated", Balance.RAD_LEVEL_INTERNAL_ELEVATED),
        ("internal_high", Balance.RAD_LEVEL_INTERNAL_HIGH),
        ("internal_extreme", Balance.RAD_LEVEL_INTERNAL_EXTREME),
        ("internal_wear_saturation", Balance.R_REF),
    )
    for kind, threshold in thresholds:
        if not math.isfinite(threshold) or threshold < 0:
            continue
        at, uncertain = _first_internal_crossing(
            profile, segment, cuts, threshold, hull_at, god_active=god_active,
            in_transit=in_transit, hibernating=hibernating)
        if uncertain:
            limits.append(TemporalLimit(
                kind, "proper", None, validity="numerical_isolation_unresolved",
                uncertainty_reason="first_internal_crossing_not_guaranteed"))
            continue
        if at is None:
            continue
        proper = (proper_time_in_segment(segment, at)
                  - proper_time_in_segment(segment, current_galactic_s))
        if at > current_galactic_s and proper <= 0:
            limits.append(TemporalLimit(
                kind, "proper", None, validity="proper_time_resolution_exhausted",
                uncertainty_reason="positive_crossing_not_representable"))
            continue
        if at == current_galactic_s:
            marker = ResolvedRadiationLimit(
                kind, profile, segment, current_galactic_s, hull_integrity,
                in_transit, hibernating, god_active)
            if marker not in resolved:
                limits.append(_radiation_limit(kind, 0, "post_crossing_check"))
        else:
            limits.append(_radiation_limit(kind, proper,
                                           "fixed_segment_profile_and_hull_wear"))
    return tuple(sorted(limits, key=lambda limit: (limit.time_s is None,
                                                   math.inf if limit.time_s is None else limit.time_s,
                                                   limit.kind)))


def resolve_radiation_limit(
    profile: RadiationProfile, segment: MotionSegment, current_galactic_s: float,
    hull_integrity: float, limit: TemporalLimit, *, in_transit: bool = True,
    hibernating: bool = False, god_active: bool = False,
) -> ResolvedRadiationLimit:
    """Return a pure marker after a zero classification check was processed."""
    if limit.time_s != 0 or limit not in radiation_limits(
            profile, segment, current_galactic_s, hull_integrity,
            in_transit=in_transit, hibernating=hibernating, god_active=god_active):
        raise ValueError("limit must be a pending zero radiation limit")
    return ResolvedRadiationLimit(limit.kind, profile, segment, current_galactic_s,
                                  hull_integrity, in_transit, hibernating, god_active)


def radiation_invalidation_reasons(
    before_profile: RadiationProfile, after_profile: RadiationProfile,
    before_segment: MotionSegment, after_segment: MotionSegment,
    *, expected_hull: float, actual_hull: float,
    expected_position_m: float | None = None, actual_position_m: float | None = None,
    before_operation: tuple[bool, bool, bool] | None = None,
    after_operation: tuple[bool, bool, bool] | None = None,
) -> tuple[str, ...]:
    """Reasons a conditional radiological forecast must be discarded.

    Operation tuples contain (in_transit, hibernating, god_active).
    """
    _nonnegative(expected_hull, "expected_hull")
    _nonnegative(actual_hull, "actual_hull")
    if (expected_position_m is None) != (actual_position_m is None):
        raise ValueError("both physical positions must be supplied together")
    if (before_operation is None) != (after_operation is None):
        raise ValueError("both operating snapshots must be supplied together")
    if expected_position_m is not None:
        _nonnegative(expected_position_m, "expected_position_m")
        _nonnegative(actual_position_m, "actual_position_m")
    if before_operation is not None:
        if (len(before_operation) != 3 or len(after_operation) != 3
                or any(type(value) is not bool for value in (*before_operation, *after_operation))):
            raise ValueError("operating snapshots must contain three booleans")
    reasons = []
    if before_profile != after_profile:
        reasons.append("radiation_profile_changed")
    if before_segment != after_segment:
        reasons.append("motion_segment_changed")
    if not math.isclose(expected_hull, actual_hull, rel_tol=1e-12, abs_tol=1e-12):
        reasons.append("hull_changed_unexpectedly")
    if expected_position_m is not None and not math.isclose(
            expected_position_m, actual_position_m, rel_tol=1e-12, abs_tol=1e-6):
        reasons.append("physical_position_changed_unexpectedly")
    if before_operation is not None and before_operation != after_operation:
        reasons.append("radiation_operation_changed")
    return tuple(reasons)
