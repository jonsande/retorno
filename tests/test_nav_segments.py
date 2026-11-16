"""Constant proper acceleration, inertia, interruption and segment composition."""
from dataclasses import FrozenInstanceError, asdict
import math

import pytest

from retorno.core.nav_physics import (
    LIGHT_SPEED_M_S, MotionSegment, MotionState, accelerate_to, append_segment,
    brake_to_stop, braking_profile, coast_for, galactic_time_at_segment_proper,
    plan_travel, sample_segment,
    sample_segments, sample_travel, truncate_segment,
)


def origin(beta=0.0):
    return MotionState(0.0, 0.0, beta, 0.0)


@pytest.mark.parametrize("beta", [0.0, 1e-12, 0.1, 0.3, 0.5, 0.8])
def test_inertia_from_existing_speed(beta):
    start = origin(beta)
    segment = coast_for(start, 1000)
    for t in (0, 0.1, 100, 1000):
        state = sample_segment(segment, t)
        assert state.beta == beta
        assert state.distance_m == pytest.approx(beta * LIGHT_SPEED_M_S * t)
        assert state.proper_s == pytest.approx(t * math.sqrt(1 - beta * beta))
        assert state.galactic_s == t


@pytest.mark.parametrize("beta0,target", [(0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.8)])
def test_accelerate_from_nonzero_speed(beta0, target):
    start = origin(beta0)
    segment = accelerate_to(start, target, 9.81)
    end = sample_segment(segment, segment.duration_galactic_s)
    rapidity = math.atanh(target) - math.atanh(beta0)
    assert end.beta == target
    assert end.proper_s == pytest.approx(LIGHT_SPEED_M_S / 9.81 * rapidity, rel=2e-14)
    gamma0 = 1 / math.sqrt(1 - beta0 * beta0)
    gamma1 = 1 / math.sqrt(1 - target * target)
    assert end.distance_m == pytest.approx(LIGHT_SPEED_M_S**2 / 9.81 * (gamma1 - gamma0), rel=2e-14)
    previous = start
    for fraction in (0.01, 0.2, 0.5, 0.8, 1):
        current = sample_segment(segment, fraction * segment.duration_galactic_s)
        assert previous.distance_m <= current.distance_m
        assert previous.beta <= current.beta <= target
        assert previous.proper_s <= current.proper_s <= current.galactic_s
        previous = current


def test_acceleration_from_rest_agrees_with_01a():
    plan = plan_travel(1e18, 0.5, 9.81)
    segment = accelerate_to(origin(), plan.peak_beta, 9.81)
    assert segment.duration_galactic_s == pytest.approx(plan.acceleration_galactic_s)
    for fraction in (0, 0.1, 0.5, 0.9):
        t = fraction * segment.duration_galactic_s
        state = sample_segment(segment, t)
        nominal = sample_travel(plan, t)
        assert state.distance_m == pytest.approx(nominal.distance_m, rel=3e-14, abs=1e-6)
        assert state.beta == pytest.approx(nominal.beta, rel=3e-14, abs=1e-16)
        assert state.proper_s == pytest.approx(nominal.proper_s, rel=3e-14, abs=1e-9)


@pytest.mark.parametrize("beta", [1e-12, 1e-9, 0.999999])
def test_small_and_near_light_speed_maneuvers(beta):
    acceleration = accelerate_to(origin(), beta, 9.81)
    accelerated = sample_segment(acceleration, acceleration.duration_galactic_s)
    assert accelerated.beta == beta
    assert accelerated.distance_m >= 0
    assert 0 < accelerated.proper_s <= accelerated.galactic_s
    braking = brake_to_stop(origin(beta), 9.81)
    stopped = sample_segment(braking, braking.duration_galactic_s)
    profile = braking_profile(beta, 9.81)
    assert stopped.beta == 0
    assert stopped.distance_m == pytest.approx(profile.distance_m, rel=2e-12, abs=1e-6)
    assert stopped.proper_s == pytest.approx(profile.proper_s, rel=2e-12, abs=1e-9)


@pytest.mark.parametrize("beta", [0.0, 0.1, 0.3, 0.5, 0.8])
def test_braking_from_nonzero_matches_01a(beta):
    start = origin(beta)
    segment = brake_to_stop(start, 9.81)
    profile = braking_profile(beta, 9.81)
    end = sample_segment(segment, segment.duration_galactic_s)
    assert segment.duration_galactic_s == profile.galactic_s
    assert end.beta == 0
    assert end.distance_m == pytest.approx(profile.distance_m, rel=3e-14, abs=1e-6)
    assert end.proper_s == pytest.approx(profile.proper_s, rel=3e-14, abs=1e-9)
    previous = start
    for fraction in (0.1, 0.5, 0.9, 1):
        current = sample_segment(segment, fraction * segment.duration_galactic_s)
        assert previous.distance_m <= current.distance_m
        assert 0 <= current.beta <= previous.beta
        previous = current


def test_interrupted_acceleration_and_recovery():
    planned = accelerate_to(origin(), 0.5, 9.81)
    partial = truncate_segment(planned, planned.duration_galactic_s * 0.4)
    at_loss = sample_segment(partial, partial.duration_galactic_s)
    assert at_loss == sample_segment(planned, partial.duration_galactic_s)
    inertia = coast_for(at_loss, 2000)
    at_recovery = sample_segment(inertia, inertia.duration_galactic_s)
    resumed = accelerate_to(at_recovery, 0.6, 9.81)
    chain = append_segment(append_segment(append_segment((), partial), inertia), resumed)
    assert sample_segments(chain, at_loss.galactic_s) == at_loss
    assert sample_segments(chain, at_recovery.galactic_s) == at_recovery
    assert sample_segment(resumed, resumed.duration_galactic_s).beta == 0.6
    assert sample_segment(planned, planned.duration_galactic_s).beta == 0.5
    assert sample_segments(chain, 0) == origin()


def test_interrupted_braking_keeps_moving_and_can_overshoot_destination():
    planned = brake_to_stop(origin(0.5), 9.81)
    partial = truncate_segment(planned, planned.duration_galactic_s * 0.5)
    at_loss = sample_segment(partial, partial.duration_galactic_s)
    assert 0 < at_loss.beta < 0.5
    destination = at_loss.distance_m + 1e10
    inertia = coast_for(at_loss, 1000)
    chain = append_segment((partial,), inertia)
    end = sample_segments(chain, at_loss.galactic_s + 1000)
    assert end.distance_m > destination
    assert end.beta == at_loss.beta
    assert sample_segment(planned, planned.duration_galactic_s).beta == 0
    assert sample_segments(chain, at_loss.galactic_s) == at_loss
    resumed = brake_to_stop(end, 9.81)
    recovered = append_segment(chain, resumed)
    stopped = sample_segments(recovered, end.galactic_s + resumed.duration_galactic_s)
    assert stopped.beta == 0
    assert stopped.distance_m > end.distance_m
    assert sample_segments(recovered, end.galactic_s) == end


def test_partition_purity_determinism_and_noop():
    start = MotionState(12, 100, 0.3, 10)
    segment = accelerate_to(start, 0.5, 9.81)
    snapshot = asdict(segment)
    whole = sample_segment(segment, segment.duration_galactic_s)
    for count in (1, 7, 100):
        intermediate = [sample_segment(segment, segment.duration_galactic_s * i / count)
                        for i in range(count + 1)]
        assert intermediate[-1] == whole
    assert asdict(segment) == snapshot
    assert sample_segment(segment, segment.duration_galactic_s) == whole
    assert accelerate_to(start, 0.2, 9.81).duration_galactic_s == 0
    assert brake_to_stop(origin(), 9.81).duration_galactic_s == 0
    with pytest.raises(FrozenInstanceError):
        segment.end_beta = 0.9


@pytest.mark.parametrize("kind", ["inertia", "acceleration", "braking"])
def test_segment_proper_time_inverse(kind):
    start = origin(0.3)
    segment = (coast_for(start, 5000) if kind == "inertia" else
               accelerate_to(start, 0.5, 9.81) if kind == "acceleration" else
               brake_to_stop(start, 9.81))
    end = sample_segment(segment, segment.duration_galactic_s)
    assert galactic_time_at_segment_proper(segment, 0) == 0
    assert galactic_time_at_segment_proper(segment, end.proper_s) == segment.duration_galactic_s
    for fraction in (0.01, 0.2, 0.5, 0.8, 0.99):
        target = end.proper_s * fraction
        t = galactic_time_at_segment_proper(segment, target)
        assert sample_segment(segment, t).proper_s == pytest.approx(target, rel=4e-14, abs=1e-9)


@pytest.mark.parametrize("bad", [-1, math.nan, math.inf, -math.inf])
def test_invalid_inputs(bad):
    with pytest.raises(ValueError):
        coast_for(origin(0.1), bad)
    with pytest.raises(ValueError):
        sample_segment(coast_for(origin(0.1), 10), bad)
    with pytest.raises(ValueError):
        brake_to_stop(origin(0.1), bad)
    with pytest.raises(ValueError):
        accelerate_to(origin(), 0.5, bad)
    with pytest.raises(ValueError):
        MotionState(0, 0, bad, 0)
    with pytest.raises(ValueError):
        accelerate_to(origin(), bad, 1)
    with pytest.raises(ValueError):
        galactic_time_at_segment_proper(coast_for(origin(0.1), 10), bad)


def test_no_reverse_and_chain_validation():
    with pytest.raises(ValueError):
        MotionSegment(origin(0.1), -9.81, 1e20, 0)
    first = coast_for(origin(0.3), 10)
    with pytest.raises(ValueError):
        append_segment((first,), coast_for(origin(0.3), 10))
    with pytest.raises(ValueError):
        sample_segments((), 0)
    with pytest.raises(ValueError):
        sample_segments((first,), 11)
