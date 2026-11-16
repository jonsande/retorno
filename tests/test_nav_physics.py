"""Focused physical and numerical checks for the disconnected navigation core."""
from dataclasses import FrozenInstanceError, asdict
import math

import pytest

from retorno.config.balance import Balance
from retorno.core.nav_physics import (
    JULIAN_YEAR_S, LIGHT_SPEED_M_S, LIGHT_YEAR_M, braking_profile, galactic_time_at_proper,
    light_years_to_metres, metres_to_light_years, plan_travel, sample_travel,
)
from retorno.core.temporal import SPEED_OF_LIGHT_KM_S


def close(actual, expected, *, rel=2e-13, abs_=1e-8):
    assert math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_)


@pytest.mark.parametrize("beta", [0.1, 0.3, 0.5, 0.8])
@pytest.mark.parametrize("distance_ly", [0.01, 2.0, 45.0])
def test_physical_invariants_across_speeds_and_distances(beta, distance_ly):
    distance = light_years_to_metres(distance_ly)
    plan = plan_travel(distance, beta, 1.0)
    assert 0 < plan.peak_beta <= beta < 1
    close(sum((plan.acceleration_distance_m, plan.cruise_distance_m,
               plan.braking_distance_m)), distance)
    assert plan.total_galactic_s >= distance / LIGHT_SPEED_M_S
    assert 0 < plan.total_proper_s <= plan.total_galactic_s
    states = [sample_travel(plan, plan.total_galactic_s * i / 200) for i in range(201)]
    assert all(0 <= s.beta < 1 for s in states)
    assert all(a.distance_m <= b.distance_m for a, b in zip(states, states[1:]))
    assert all(a.proper_s <= b.proper_s for a, b in zip(states, states[1:]))
    braking = [s.beta for s in states if s.phase == "braking"]
    assert braking == sorted(braking, reverse=True)
    assert states[0].distance_m == states[0].beta == states[0].proper_s == 0
    assert states[-1].distance_m == distance and states[-1].beta == 0
    assert states[-1].proper_s == plan.total_proper_s


def test_cruise_and_phase_boundaries():
    plan = plan_travel(light_years_to_metres(2), 0.3, 1.0)
    assert plan.has_cruise and plan.cruise_galactic_s > 0
    start = sample_travel(plan, plan.cruise_start_s)
    brake = sample_travel(plan, plan.braking_start_s)
    assert start.phase == "cruise" and brake.phase == "braking"
    close(start.distance_m, plan.acceleration_distance_m)
    close(brake.distance_m, plan.acceleration_distance_m + plan.cruise_distance_m)
    close(start.beta, plan.peak_beta)
    close(brake.beta, plan.peak_beta)
    close(start.proper_s, plan.acceleration_proper_s)
    close(brake.proper_s, plan.acceleration_proper_s + plan.cruise_proper_s)
    mid = sample_travel(plan, (plan.cruise_start_s + plan.braking_start_s) / 2)
    assert mid.phase == "cruise" and mid.beta == plan.peak_beta
    close(mid.distance_m, plan.distance_m / 2)


def test_short_trip_and_exact_threshold():
    target = 0.8
    stopping = braking_profile(target, 1.0)
    threshold = 2 * stopping.distance_m
    for distance in (threshold, math.nextafter(threshold, 0), threshold * 0.1):
        plan = plan_travel(distance, target, 1.0)
        assert not plan.has_cruise
        assert plan.cruise_distance_m == plan.cruise_galactic_s == 0
        assert plan.peak_beta <= target
        center = sample_travel(plan, plan.cruise_start_s)
        assert center.phase == "braking"
        close(center.distance_m, distance / 2)
        close(center.beta, plan.peak_beta)
        close(center.proper_s, plan.total_proper_s / 2)
        assert sample_travel(plan, plan.total_galactic_s).distance_m == distance
    assert plan_travel(math.nextafter(threshold, math.inf), target, 1.0).has_cruise


def test_short_distance_and_low_beta_stability():
    plan = plan_travel(1.0, 1e-6, 1.0)
    assert 0 < plan.peak_beta <= 1e-6
    close(plan.acceleration_distance_m * 2, 1.0)
    close(sample_travel(plan, plan.total_galactic_s).distance_m, 1.0)
    stop = braking_profile(1e-9, 1.0)
    close(stop.distance_m, (1e-9 * LIGHT_SPEED_M_S) ** 2 / 2, rel=1e-12)


@pytest.mark.parametrize("beta", [0.0, 0.1, 0.3, 0.5, 0.8])
def test_independent_braking(beta):
    stop = braking_profile(beta, 1.0)
    assert stop.distance_m >= 0 and stop.galactic_s >= stop.proper_s >= 0
    if beta:
        # v = a*t/gamma in the galactic frame; low-beta limit approaches v²/2a.
        gamma = 1 / math.sqrt(1 - beta * beta)
        close(stop.galactic_s, gamma * beta * LIGHT_SPEED_M_S)
        close(stop.distance_m, (gamma - 1) * LIGHT_SPEED_M_S**2, rel=1e-12)
        plan = plan_travel(2 * stop.distance_m, beta, 1.0)
        close(plan.braking_distance_m, stop.distance_m)
        close(plan.braking_galactic_s, stop.galactic_s)


def test_partition_independence_and_purity():
    plan = plan_travel(light_years_to_metres(2), 0.5, 1.0)
    before = asdict(plan)
    direct = sample_travel(plan, plan.total_galactic_s)
    for count in (1, 7, 1000):
        samples = [sample_travel(plan, plan.total_galactic_s * i / count) for i in range(count + 1)]
        assert samples[-1] == direct
    assert asdict(plan) == before
    assert plan_travel(light_years_to_metres(2), 0.5, 1.0) == plan
    with pytest.raises(FrozenInstanceError):
        plan.target_beta = 0.3


def test_units_and_calendar_distinction():
    assert LIGHT_SPEED_M_S == SPEED_OF_LIGHT_KM_S * 1000
    assert JULIAN_YEAR_S == 365.25 * 86400
    assert JULIAN_YEAR_S != Balance.YEAR_S
    close(metres_to_light_years(LIGHT_YEAR_M), 1.0)
    close(light_years_to_metres(2), 2 * LIGHT_YEAR_M)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -1.0, 0.0])
def test_invalid_positive_inputs(bad):
    with pytest.raises(ValueError):
        plan_travel(bad, 0.5, 1)
    with pytest.raises(ValueError):
        plan_travel(1, 0.5, bad)
    with pytest.raises(ValueError):
        braking_profile(0.5, bad)
    with pytest.raises(ValueError):
        light_years_to_metres(bad)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.1, 0.0, 1.0, 1.1])
def test_invalid_target_beta(bad):
    with pytest.raises(ValueError):
        plan_travel(1e12, bad, 1)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.1, 1.0, 1.1])
def test_invalid_braking_beta(bad):
    with pytest.raises(ValueError):
        braking_profile(bad, 1)


def test_invalid_sample_times_and_conversion():
    plan = plan_travel(light_years_to_metres(0.01), 0.5, 1.0)
    for bad in (-1, math.nan, math.inf, math.nextafter(plan.total_galactic_s, math.inf)):
        with pytest.raises(ValueError):
            sample_travel(plan, bad)
    for bad in (-1, math.nan, math.inf):
        with pytest.raises(ValueError):
            metres_to_light_years(bad)


@pytest.mark.parametrize("distance", [1e14, 1e18])
def test_proper_time_inverse_across_all_phases(distance):
    plan = plan_travel(distance, 0.5, 9.81)
    assert galactic_time_at_proper(plan, 0) == 0
    assert galactic_time_at_proper(plan, plan.acceleration_proper_s) == plan.cruise_start_s
    assert galactic_time_at_proper(plan, plan.acceleration_proper_s + plan.cruise_proper_s) == plan.braking_start_s
    assert galactic_time_at_proper(plan, plan.total_proper_s) == plan.total_galactic_s
    for fraction in (0.01, 0.2, 0.5, 0.8, 0.99):
        tau = plan.total_proper_s * fraction
        galactic = galactic_time_at_proper(plan, tau)
        close(sample_travel(plan, galactic).proper_s, tau, rel=2e-13)
