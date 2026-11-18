"""First internal radiation crossing under competing ambient and hull trends."""
import math

import pytest

from retorno.config.balance import Balance
from retorno.core.nav_coordinator import select_next_boundary
from retorno.core.nav_physics import (
    MotionState, accelerate_to, brake_to_stop, coast_for,
    proper_time_in_segment, sample_segment, truncate_segment,
)
from retorno.core.nav_radiation import (
    RadiationProfile, _first_internal_crossing, _predicted_hull,
    environmental_limits, radiation_limits, resolve_radiation_limit,
)


def _long_case():
    duration = 1e10
    segment = coast_for(MotionState(0, 0, .5, 0), duration)
    profile = RadiationProfile(0, sample_segment(segment, duration).distance_m,
                               .04, .001)
    return profile, segment


def _hull(profile, segment, left, right, initial):
    return _predicted_hull(profile, segment, left, right, initial,
                           in_transit=True, hibernating=False, god_active=False)


def _quadratic_reference(threshold):
    """Independent coast solution before the hull-radiation saturation cut."""
    duration = 1e10
    slope = (.001-.04)/duration
    ingress_slope = ((Balance.HULL_INTERNAL_RAD_MAX_INGRESS
                      - Balance.HULL_INTERNAL_RAD_MIN_INGRESS)
                     * Balance.HULL_BASE_DECAY_PER_S
                     * Balance.HULL_TRANSIT_DECAY_MULT
                     * Balance.HULL_RAD_DECAY_MULT_MAX * math.sqrt(1-.5**2))
    a = slope * ingress_slope
    b = .04 * ingress_slope + slope * .1
    c = .04 * .1 - threshold
    discriminant = b*b - 4*a*c
    return sorted(((-b+math.sqrt(discriminant))/(2*a),
                   (-b-math.sqrt(discriminant))/(2*a)))


def _kind(limits, kind):
    return next((limit for limit in limits if limit.kind == kind), None)


def test_first_of_two_crossings_and_subinterval_after_it():
    profile, segment = _long_case()
    first, second = _quadratic_reference(Balance.RAD_LEVEL_INTERNAL_EXTREME)
    initial = radiation_limits(profile, segment, 0, 1)
    extreme = _kind(initial, "internal_extreme")
    assert extreme is not None and extreme.time_s is not None
    assert extreme.time_s == pytest.approx(first * math.sqrt(.75), rel=2e-7)
    selection = select_next_boundary(segment, 0, 5e9, proper_limits=initial)
    assert selection.advance_galactic_s > 0
    assert selection.at_galactic_s <= first + 1
    after_first = 2e9
    hull = _hull(profile, segment, 0, after_first, 1)
    later = _kind(radiation_limits(profile, segment, after_first, hull),
                  "internal_extreme")
    assert later is not None and later.time_s is not None
    expected = proper_time_in_segment(segment, second) - proper_time_in_segment(segment, after_first)
    assert later.time_s == pytest.approx(expected, rel=2e-7)
    before_first = .5e9
    early_hull = _hull(profile, segment, 0, before_first, 1)
    remaining = _kind(radiation_limits(profile, segment, before_first, early_hull),
                      "internal_extreme")
    assert remaining.time_s + proper_time_in_segment(segment, before_first) == pytest.approx(
        extreme.time_s, rel=2e-7)


def test_interior_maximum_tangency_and_nearby_no_crossing():
    profile, segment = _long_case()
    duration = segment.duration_galactic_s
    slope = (.001-.04)/duration
    ingress_slope = (.9 * Balance.HULL_BASE_DECAY_PER_S
                     * Balance.HULL_TRANSIT_DECAY_MULT
                     * Balance.HULL_RAD_DECAY_MULT_MAX * math.sqrt(.75))
    peak_at = -(.04*ingress_slope+slope*.1)/(2*slope*ingress_slope)
    peak = (.04+slope*peak_at)*(.1+ingress_slope*peak_at)
    hull_at = lambda t: _hull(profile, segment, 0, t, 1)

    def crossing(threshold):
        return _first_internal_crossing(
            profile, segment, (0, duration), threshold, hull_at,
            god_active=False, in_transit=True, hibernating=False)

    assert crossing(peak) == (None, True)  # Roundoff cannot certify tangency.
    assert crossing(peak * (1+1e-6)) == (None, False)
    near, uncertain = crossing(peak * (1-1e-6))
    assert not uncertain and near < peak_at
    assert near == pytest.approx(_quadratic_reference(peak*(1-1e-6))[0], rel=2e-6)


@pytest.mark.parametrize("before_route", [False, True])
def test_constant_field_outside_route_with_wearing_hull(before_route):
    start = 0 if before_route else 1e19
    segment = coast_for(MotionState(0, start, .5, 0), 2e10)
    if before_route:
        profile = RadiationProfile(1e20, 2e20, .001, .02)
    else:
        profile = RadiationProfile(0, 1e18, .02, .001)
    limits = radiation_limits(profile, segment, 0, 1)
    assert not any(limit.kind.startswith("internal") and limit.time_s is None
                   for limit in limits)
    assert _kind(limits, "internal_elevated").time_s is not None


@pytest.mark.parametrize("motion", ["acceleration", "braking", "coast", "interrupted"])
def test_decreasing_field_crossing_on_motion_segments(motion):
    start = MotionState(0, 0, .3, 0)
    if motion == "acceleration":
        segment = accelerate_to(start, .45, 9.81)
    elif motion == "braking":
        segment = brake_to_stop(start, 9.81)
    elif motion == "interrupted":
        whole = accelerate_to(start, .5, 9.81)
        segment = truncate_segment(whole, whole.duration_galactic_s * .7)
    else:
        segment = coast_for(start, 1e7)
    end = sample_segment(segment, segment.duration_galactic_s).distance_m
    profile = RadiationProfile(0, end, .02, .001)
    limits = radiation_limits(profile, segment, 0, 1)
    high = _kind(limits, "internal_high")
    assert high is not None and high.time_s is not None and high.time_s > 0
    selection = select_next_boundary(segment, 0, segment.duration_galactic_s,
                                     proper_limits=(high,))
    assert selection.advance_galactic_s > 0


def test_hull_floor_before_and_after_internal_crossing():
    profile, segment = _long_case()
    early_floor = radiation_limits(profile, segment, 0, .01)
    assert _kind(early_floor, "hull_integrity_zero").time_s < _kind(
        early_floor, "internal_extreme").time_s
    extended = coast_for(MotionState(0, 0, .5, 0), 2e10)
    late_floor = radiation_limits(profile, extended, 0, .4)
    assert _kind(late_floor, "internal_extreme").time_s < _kind(
        late_floor, "hull_integrity_zero").time_s


def test_marker_snapshot_invalidation_and_no_repeated_zero():
    segment = coast_for(MotionState(0, 0, .5, 0), 100)
    profile = RadiationProfile(0, sample_segment(segment, 100).distance_m,
                               .005, .001)
    at = 50.0
    pending = _kind(radiation_limits(profile, segment, at, 1, god_active=True),
                    "internal_elevated")
    assert pending.time_s == 0
    marker = resolve_radiation_limit(profile, segment, at, 1, pending,
                                     god_active=True)
    assert not any(limit.kind == pending.kind and limit.time_s == 0
                   for limit in radiation_limits(profile, segment, at, 1,
                                                 god_active=True,
                                                 resolved=frozenset({marker})))
    assert _kind(radiation_limits(profile, segment, at, 1, god_active=False,
                                  resolved=frozenset({marker})),
                 "internal_elevated").time_s == 0
    for changed_hull in (.9, .99):
        assert radiation_limits(profile, segment, at, changed_hull, god_active=True,
                                resolved=frozenset({marker})) == radiation_limits(
                                    profile, segment, at, changed_hull, god_active=True)
    changed_profile = RadiationProfile(0, profile.end_m, .006, .001)
    assert radiation_limits(changed_profile, segment, at, 1, god_active=True,
                            resolved=frozenset({marker})) == radiation_limits(
                                changed_profile, segment, at, 1, god_active=True)
    ambient = _kind(environmental_limits(profile, segment, at, hull_integrity=1),
                    "ambient_high")
    ambient_marker = resolve_radiation_limit(profile, segment, at, 1, ambient)
    assert _kind(environmental_limits(profile, segment, at, hull_integrity=.8,
                                      resolved=frozenset({ambient_marker})),
                 "ambient_high").time_s == 0
    assert _kind(environmental_limits(profile, segment, at, hull_integrity=1,
                                      hibernating=True,
                                      resolved=frozenset({ambient_marker})),
                 "ambient_high").time_s == 0


def test_segment_endpoint_contact_and_overshoot_constant_region():
    segment = coast_for(MotionState(0, 0, .5, 0), 100)
    end = sample_segment(segment, 50).distance_m
    profile = RadiationProfile(0, end, .02, .01)
    limits = radiation_limits(profile, segment, 0, 1, god_active=True)
    high = _kind(limits, "internal_high")
    assert high is not None and high.time_s == pytest.approx(
        proper_time_in_segment(segment, 50), rel=1e-10)
    assert _kind(radiation_limits(profile, segment, 60, 1), "internal_high") is None


def test_internal_crossing_coincides_with_hull_floor():
    segment = coast_for(MotionState(0, 0, .5, 0), 1e9)
    profile = RadiationProfile(0, 1e18, .005, .005)
    limits = radiation_limits(profile, segment, 0, .01)
    assert _kind(limits, "internal_extreme").time_s == pytest.approx(
        _kind(limits, "hull_integrity_zero").time_s, rel=1e-13)
