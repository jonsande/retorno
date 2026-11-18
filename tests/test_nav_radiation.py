"""Spatial and causally coupled radiation forecasts for physical segments."""
from dataclasses import FrozenInstanceError, asdict, replace
import math

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_coordinator import select_next_boundary
from retorno.core.nav_physics import (
    LIGHT_SPEED_M_S, MotionState, accelerate_to, brake_to_stop, coast_for,
    proper_time_in_segment, sample_segment, truncate_segment,
)
from retorno.core.nav_radiation import (
    RadiationProfile, environmental_limits, hull_decay_rate,
    integrate_segment_radiation, integrated_system_wear, internal_radiation_rate,
    radiation_invalidation_reasons, radiation_limits, resolve_radiation_limit,
)


def coast(duration=1000.0, beta=.5, start=None):
    return coast_for(start or MotionState(0, 0, beta, 0), duration)


def profile_for(segment, start_rad=.001, end_rad=.005):
    end = sample_segment(segment, segment.duration_galactic_s).distance_m
    return RadiationProfile(0, end, start_rad, end_rad)


def reference_integrals(profile, segment, left, right, hull, *, intervals=20000):
    """Independent composite midpoint reference in galactic time."""
    dt = (right-left) / intervals
    env_gal = env_proper = internal = norm = 0.0
    for index in range(intervals):
        at = left + (index + .5) * dt
        motion = sample_segment(segment, at)
        env = profile.ambient_at(motion.distance_m)
        proper_dt = math.sqrt(1-motion.beta**2) * dt
        loss = hull_decay_rate(env, in_transit=True, hibernating=False) * proper_dt
        middle_hull = max(0, hull - loss/2)
        rate = internal_radiation_rate(env, middle_hull)
        env_gal += env * dt
        env_proper += env * proper_dt
        internal += rate * proper_dt
        norm += min(1, rate / Balance.R_REF) * proper_dt
        hull = max(0, hull - loss)
    return env_gal, env_proper, internal, norm, hull


@pytest.mark.parametrize("start,end", [(.002,.002), (.001,.005), (.005,.001)])
def test_coast_spatial_profile_exact_doses_and_clamped_extensions(start, end):
    segment = coast(100, .6)
    route = profile_for(segment, start, end)
    result = integrate_segment_radiation(route, segment, 0, 100, 1)
    dtau = proper_time_in_segment(segment, 100)
    assert result.environmental_galactic_rad == pytest.approx(100*(start+end)/2, rel=1e-12)
    assert result.environmental_proper_rad == pytest.approx(dtau*(start+end)/2, rel=1e-12)
    assert route.ambient_at(0) == start
    assert route.ambient_at(route.end_m) == end
    assert route.ambient_at(route.end_m*2) == end
    with pytest.raises(FrozenInstanceError):
        route.end_rad_per_s = 2


def test_coast_subintervals_and_partition_with_evolving_hull():
    segment = coast(1000, .8)
    route = profile_for(segment, .001, .004)
    whole = integrate_segment_radiation(route, segment, 0, 1000, .7)
    first = integrate_segment_radiation(route, segment, 0, 300, .7)
    second = integrate_segment_radiation(route, segment, 300, 1000, first.hull_end)
    assert whole.environmental_galactic_rad == pytest.approx(
        first.environmental_galactic_rad+second.environmental_galactic_rad, rel=1e-11)
    assert whole.environmental_proper_rad == pytest.approx(
        first.environmental_proper_rad+second.environmental_proper_rad, rel=1e-11)
    assert whole.internal_proper_rad == pytest.approx(
        first.internal_proper_rad+second.internal_proper_rad, rel=1e-9)
    assert whole.hull_end == pytest.approx(second.hull_end, abs=2e-15)


@pytest.mark.parametrize("initial_beta,acceleration", [(0,9.81), (.3,9.81), (.7,-9.81)])
def test_acceleration_and_braking_against_independent_reference(initial_beta, acceleration):
    start = MotionState(0, 0, initial_beta, 0)
    segment = (accelerate_to(start, min(.95, initial_beta+.15), acceleration)
               if acceleration > 0 else brake_to_stop(start, -acceleration))
    duration = min(segment.duration_galactic_s, 2e7)
    route = RadiationProfile(0, sample_segment(segment, duration).distance_m, .001, .004)
    result = integrate_segment_radiation(route, segment, 0, duration, .8)
    ref = reference_integrals(route, segment, 0, duration, .8)
    assert result.environmental_galactic_rad == pytest.approx(ref[0], rel=2e-8)
    assert result.environmental_proper_rad == pytest.approx(ref[1], rel=2e-8)
    assert result.internal_proper_rad == pytest.approx(ref[2], rel=2e-8)
    assert result.normalized_internal_proper_s == pytest.approx(ref[3], rel=2e-8)
    assert result.hull_end == pytest.approx(ref[4], abs=2e-10)


def test_interruption_continuity_coast_resume_and_overshoot():
    start = MotionState(0, 0, .2, 0)
    original = accelerate_to(start, .5, 9.81)
    interrupted = truncate_segment(original, original.duration_galactic_s/2)
    at = sample_segment(interrupted, interrupted.duration_galactic_s)
    later = coast_for(at, 2e7)
    route = RadiationProfile(0, at.distance_m*.7, .001, .006)
    assert route.ambient_at(at.distance_m) == .006
    assert route.ambient_at(sample_segment(later, 0).distance_m) == .006
    stopped = brake_to_stop(sample_segment(later, later.duration_galactic_s), 9.81)
    beyond = sample_segment(stopped, stopped.duration_galactic_s)
    assert beyond.distance_m > route.end_m
    assert route.ambient_at(beyond.distance_m) == .006
    first = integrate_segment_radiation(route, interrupted, 0,
                                        interrupted.duration_galactic_s, .9)
    middle = integrate_segment_radiation(route, later, 0, later.duration_galactic_s,
                                         first.hull_end)
    final = integrate_segment_radiation(route, stopped, 0, stopped.duration_galactic_s,
                                        middle.hull_end)
    assert first.hull_end >= middle.hull_end >= final.hull_end
    assert final.environmental_proper_rad > 0


def test_internal_dose_uses_hull_at_each_instant_and_floor():
    segment = coast(1e6, .5)
    route = profile_for(segment, .003, .003)
    result = integrate_segment_radiation(route, segment, 0, 1e6, .5)
    proper = proper_time_in_segment(segment, 1e6)
    hull_rate = Balance.HULL_BASE_DECAY_PER_S * Balance.HULL_TRANSIT_DECAY_MULT * Balance.HULL_RAD_DECAY_MULT_MAX
    ingress = Balance.HULL_INTERNAL_RAD_MIN_INGRESS + .5 * (
        Balance.HULL_INTERNAL_RAD_MAX_INGRESS-Balance.HULL_INTERNAL_RAD_MIN_INGRESS)
    expected_internal = .003 * (ingress*proper + .9*hull_rate*proper**2/2)
    assert result.hull_end == pytest.approx(.5-hull_rate*proper)
    assert result.internal_proper_rad == pytest.approx(expected_internal, rel=1e-12)
    assert result.internal_proper_rad > .003*ingress*proper
    floored = integrate_segment_radiation(route, segment, 0, 1e6, 1e-6)
    assert floored.hull_end == 0
    assert 0 < floored.internal_proper_rad <= floored.environmental_proper_rad
    assert floored.internal_proper_rad > result.internal_proper_rad


def test_hull_saturation_god_and_normalized_radiation_factor():
    segment = coast(1e5, .5)
    route = profile_for(segment, 1, 1)
    high = integrate_segment_radiation(route, segment, 0, 1e5, 1)
    god = integrate_segment_radiation(route, segment, 0, 1e5, 1, god_active=True)
    assert high.hull_loss == pytest.approx(
        Balance.HULL_BASE_DECAY_PER_S * Balance.HULL_TRANSIT_DECAY_MULT
        * Balance.HULL_RAD_DECAY_MULT_MAX * high.proper_s, abs=1e-15)
    assert high.normalized_internal_proper_s == pytest.approx(high.proper_s)
    assert god.hull_end == 1
    assert god.environmental_proper_rad == high.environmental_proper_rad
    assert god.internal_proper_rad == pytest.approx(.1*god.proper_s)
    assert high.internal_proper_rad > god.internal_proper_rad


def test_integrated_system_wear_uses_shared_factors():
    segment = coast(1000, .5)
    route = profile_for(segment, .001, .001)
    exposure = integrate_segment_radiation(route, segment, 0, 1000, .8)
    state = create_initial_state_sandbox(seed=3)
    system = state.ship.systems["engines"]
    system.base_decay_per_s = .0001
    system.k_power = .3
    system.k_rad = .4
    quality_integral = exposure.proper_s*.6
    expected = .0001*(exposure.proper_s*(1+.3*.4)
                       + .4*exposure.normalized_internal_proper_s)
    assert integrated_system_wear(system, exposure, quality_integral,
                                  in_transit=False, op_mode="CRUISE") == pytest.approx(expected)
    assert integrated_system_wear(system, exposure, quality_integral,
                                  in_transit=False, op_mode="CRUISE", god_active=True) == 0


def test_environmental_thresholds_and_coordinator_no_zero_repetition():
    segment = coast(100, .5)
    route = profile_for(segment, 0, .006)
    limits = environmental_limits(route, segment, 0)
    kinds = {limit.kind for limit in limits}
    assert {"ambient_elevated", "ambient_high", "hull_radiation_saturation"} <= kinds
    first = select_next_boundary(segment, 0, 100, proper_limits=limits)
    assert {cause.limit.kind for cause in first.causes} == {"ambient_elevated"}
    subsequent = environmental_limits(route, segment, first.at_galactic_s)
    assert "ambient_elevated" not in {limit.kind for limit in subsequent}
    next_cut = select_next_boundary(segment, first.at_galactic_s,
                                    100-first.at_galactic_s,
                                    proper_limits=subsequent,
                                    seen_zero_selections=(first,))
    assert next_cut.advance_galactic_s > 0
    falling = profile_for(segment, .006, 0)
    assert "hibernate_ambient_wake" not in {limit.kind for limit in environmental_limits(falling, segment, 0)}
    assert "hibernate_ambient_wake" in {limit.kind for limit in environmental_limits(
        route, segment, 0, hibernating=True)}


def test_downward_ambient_equality_requires_one_post_side_check():
    segment = coast(100, .5)
    route = profile_for(segment, .005, .001)
    at = 50.0  # Spatial midpoint has exactly .003 rad/s.
    pending = next(limit for limit in environmental_limits(route, segment, at)
                   if limit.kind == "ambient_high")
    assert pending.time_s == 0
    assert pending.validity == "post_crossing_check"
    selected = select_next_boundary(segment, at, 10,
                                    proper_limits=environmental_limits(route, segment, at))
    assert selected.advance_galactic_s == 0
    marker = resolve_radiation_limit(route, segment, at, 1, pending)
    later = select_next_boundary(segment, at, 10,
                                 proper_limits=environmental_limits(
                                     route, segment, at, resolved=frozenset({marker})),
                                 seen_zero_selections=(selected,))
    assert later.advance_galactic_s > 0
    assert "ambient_high" in {limit.kind for limit in environmental_limits(
        route, segment, at, resolved=frozenset())}
    at_endpoint = RadiationProfile(0, sample_segment(segment, 50).distance_m,
                                   .005, Balance.RAD_LEVEL_ENV_HIGH)
    assert "ambient_high" not in {limit.kind for limit in environmental_limits(
        at_endpoint, segment, 50)}


def test_internal_thresholds_hull_floor_and_deferred_nonmonotone_case():
    segment = coast(1e6, .5)
    increasing = profile_for(segment, .001, .1)
    limits = radiation_limits(increasing, segment, 0, 1)
    kinds = {limit.kind for limit in limits}
    assert {"internal_elevated", "internal_high", "internal_extreme"} <= kinds
    assert all(limit.domain == "proper" for limit in limits)
    near_zero_hull = radiation_limits(increasing, segment, 0, 1e-6)
    assert "hull_integrity_zero" in {limit.kind for limit in near_zero_hull}
    decreasing = profile_for(segment, .02, .001)
    uncertain = radiation_limits(decreasing, segment, 0, .5)
    assert next(limit for limit in uncertain if limit.kind == "internal_high").time_s is None
    fixed = radiation_limits(decreasing, segment, 0, .5, god_active=True)
    assert next(limit for limit in fixed if limit.kind == "internal_high").time_s is not None


def test_internal_downward_equality_is_resolved_once():
    segment = coast(100, .5)
    route = profile_for(segment, .005, .001)
    # At t=50, environmental rate is .003 and ingress at full hull is .1.
    limits = radiation_limits(route, segment, 50, 1, god_active=True)
    target = next(limit for limit in limits if limit.kind == "internal_elevated")
    assert target.time_s == 0
    marker = resolve_radiation_limit(route, segment, 50, 1, target, god_active=True)
    remaining = radiation_limits(route, segment, 50, 1, god_active=True,
                                 resolved=frozenset({marker}))
    assert not any(limit.kind == "internal_elevated" and limit.time_s == 0
                   for limit in remaining)


def test_purity_invalid_inputs_and_invalidation():
    segment = coast(100, .5)
    route = profile_for(segment)
    before = asdict(route), asdict(segment)
    first = integrate_segment_radiation(route, segment, 0, 50, .8)
    second = integrate_segment_radiation(route, segment, 0, 50, .8)
    assert first == second
    assert before == (asdict(route), asdict(segment))
    assert radiation_invalidation_reasons(route, route, segment, segment,
                                          expected_hull=first.hull_end,
                                          actual_hull=first.hull_end) == ()
    assert "radiation_profile_changed" in radiation_invalidation_reasons(
        route, replace(route, end_rad_per_s=.004), segment, segment,
        expected_hull=.8, actual_hull=.8)
    assert "hull_changed_unexpectedly" in radiation_invalidation_reasons(
        route, route, segment, segment, expected_hull=.8, actual_hull=.7)
    reasons = radiation_invalidation_reasons(
        route, route, segment, segment, expected_hull=.8, actual_hull=.8,
        expected_position_m=10, actual_position_m=12,
        before_operation=(True, False, False),
        after_operation=(True, True, False))
    assert reasons == ("physical_position_changed_unexpectedly",
                       "radiation_operation_changed")
    with pytest.raises(ValueError):
        radiation_invalidation_reasons(route, route, segment, segment,
                                       expected_hull=.8, actual_hull=.8,
                                       expected_position_m=10)
    with pytest.raises(ValueError):
        RadiationProfile(1, 0, .001, .002)
    with pytest.raises(ValueError):
        route.ambient_at(-1)
    with pytest.raises(ValueError):
        integrate_segment_radiation(route, segment, 0, 101, .8)
    with pytest.raises(ValueError):
        integrate_segment_radiation(route, segment, 0, 50, 1.1)
    with pytest.raises(ValueError):
        integrate_segment_radiation(route, segment, 0, 50, .8, abs_tol=0)


def test_shared_productive_radiation_rules_are_unchanged():
    engine = Engine()
    game = create_initial_state_sandbox(seed=8)
    game.ship.hull_integrity = .7
    game.ship.in_transit = False
    game.ship.is_hibernating = False
    for rad in (0, .001, Balance.HULL_RAD_REF, .05):
        assert engine._compute_internal_radiation_rad_per_s(game, rad) == pytest.approx(
            internal_radiation_rate(rad, .7))
        initial = game.ship.hull_integrity
        engine._apply_hull_degradation(game, 1000, rad, in_transit=False)
        assert game.ship.hull_integrity == pytest.approx(
            initial-hull_decay_rate(rad, in_transit=False, hibernating=False)*1000)
        game.ship.hull_integrity = .7
