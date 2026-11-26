"""Boundary selection on active physical segments after interrupted plans."""
from dataclasses import FrozenInstanceError, asdict
import math

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.nav_boundaries import TemporalLimit, predict_engine_health_limit, thrust_available
from retorno.core.nav_coordinator import TemporalResolutionError, select_next_boundary
from retorno.core.nav_physics import (
    MotionState, accelerate_to, brake_to_stop, coast_for,
    galactic_time_at_segment_proper, proper_time_in_segment,
    sample_segment, truncate_segment,
)


def origin(beta=0.0, at=0.0, proper=0.0, distance=0.0):
    return MotionState(at, distance, beta, proper)


def kinds(selection):
    return [cause.limit.kind for cause in selection.causes]


@pytest.mark.parametrize("kind", ["acceleration", "braking", "inertia"])
def test_proper_limit_inside_active_segment(kind):
    start = origin(0.3, at=500, proper=420, distance=1e12)
    segment = (accelerate_to(start, 0.5, 9.81) if kind == "acceleration" else
               brake_to_stop(start, 9.81) if kind == "braking" else
               coast_for(start, 10000))
    now_local = segment.duration_galactic_s * 0.2
    target_local = segment.duration_galactic_s * 0.6
    now = start.galactic_s + now_local
    remaining_proper = (proper_time_in_segment(segment, target_local)
                        - proper_time_in_segment(segment, now_local))
    health = TemporalLimit("engine_health_threshold", "proper", remaining_proper,
                           validity="constant_wear_conditions")
    selected = select_next_boundary(segment, now, segment.duration_galactic_s,
                                    health_limit=health)
    assert kinds(selected) == ["engine_health_threshold"]
    assert selected.at_galactic_s == pytest.approx(start.galactic_s + target_local, rel=2e-14)
    assert selected.accumulated_proper_s == pytest.approx(sample_segment(segment, target_local).proper_s)
    assert galactic_time_at_segment_proper(segment, proper_time_in_segment(segment, target_local)) == pytest.approx(target_local)


def test_segment_end_and_horizon_with_partial_query():
    segment = coast_for(origin(0.3, at=50), 100)
    assert kinds(select_next_boundary(segment, 75, 10)) == ["requested_horizon"]
    assert kinds(select_next_boundary(segment, 75, 75)) == ["requested_horizon", "segment_end"]
    assert kinds(select_next_boundary(segment, 75, 500)) == ["segment_end"]
    end = select_next_boundary(segment, 150, 10)
    assert end.advance_galactic_s == 0
    assert kinds(end) == ["segment_end"]


def test_simultaneous_health_and_running_jobs_and_near_later_job():
    segment = coast_for(origin(0.5), 100)
    now = 20.0
    health = TemporalLimit("engine_health_threshold", "proper", 10 * math.sqrt(0.75))
    job_at = math.nextafter(30.0, math.inf)
    jobs = (TemporalLimit("propulsion_job", "galactic", 10, job_id="repair",
                          validity="running_if_uninterrupted", uncertainty_reason="may_fail"),
            TemporalLimit("propulsion_job", "galactic", job_at - now, job_id="later",
                          validity="running_if_uninterrupted"))
    selected = select_next_boundary(segment, now, 50, health_limit=health, job_limits=jobs)
    assert selected.at_galactic_s == 30
    assert [c.limit.job_id for c in selected.causes if c.limit.job_id] == ["repair", "later"]
    assert selected.causes[-1].at_galactic_s > selected.at_galactic_s
    assert selected.requires_reevaluation


def test_queued_activation_and_invalidation_do_not_assign_completion():
    segment = coast_for(origin(0.3), 100)
    queued = TemporalLimit("job_activation", "galactic", 0, job_id="queued",
                           validity="queued_activation_candidate")
    blocked = TemporalLimit("propulsion_job", "galactic", None, job_id="blocked",
                            validity="indeterminate")
    selected = select_next_boundary(segment, 20, 50, job_limits=(queued, blocked))
    assert selected.advance_galactic_s == 0
    assert kinds(selected) == ["job_activation"]
    assert selected.deferred == (blocked,)
    invalid = select_next_boundary(segment, 20, 50, job_limits=(queued, blocked),
                                   invalidation_reasons=("electrical_change",))
    assert kinds(invalid) == ["prediction_invalidated"]
    assert invalid.causes[0].limit.uncertainty_reason == "electrical_change"
    assert invalid.deferred == (blocked,)


def test_interrupted_chain_uses_only_active_segment():
    planned = accelerate_to(origin(), 0.5, 9.81)
    truncated = truncate_segment(planned, planned.duration_galactic_s * 0.4)
    at_loss = sample_segment(truncated, truncated.duration_galactic_s)
    inertial = coast_for(at_loss, 1000)
    selected = select_next_boundary(inertial, at_loss.galactic_s + 100, 2000)
    assert kinds(selected) == ["segment_end"]
    assert selected.at_galactic_s == at_loss.galactic_s + 1000
    assert selected.accumulated_proper_s == pytest.approx(sample_segment(inertial, 1000).proper_s)
    recovered = brake_to_stop(sample_segment(inertial, 1000), 9.81)
    assert kinds(select_next_boundary(recovered, recovered.start.galactic_s,
                                      recovered.duration_galactic_s * 2)) == ["segment_end"]


def test_interrupted_braking_and_destination_overshoot_are_not_arrival():
    braking = brake_to_stop(origin(0.5), 9.81)
    partial = truncate_segment(braking, braking.duration_galactic_s * 0.4)
    at_loss = sample_segment(partial, partial.duration_galactic_s)
    coast = coast_for(at_loss, 1000)
    destination = at_loss.distance_m + 1e10
    assert sample_segment(coast, 1000).distance_m > destination
    selected = select_next_boundary(coast, at_loss.galactic_s, 2000)
    assert kinds(selected) == ["segment_end"]
    assert all(c.limit.kind != "profile_end" for c in selected.causes)


def test_health_equality_and_braking_capacity_contract_pending():
    game = create_initial_state_sandbox(seed=301)
    game.ship.systems["engines"].health = Balance.SYSTEM_HEALTH_CRITICAL
    assert thrust_available(game.ship)  # existing 35% contract only
    limit = predict_engine_health_limit(game.ship, 0.01)
    segment = brake_to_stop(origin(0.3), 9.81)
    selected = select_next_boundary(segment, 0, 100, health_limit=limit)
    assert selected.advance_galactic_s == 0
    assert kinds(selected) == ["engine_health_threshold"]
    game.ship.systems["engines"].health = 0.2
    assert not thrust_available(game.ship)  # not a statement about emergency braking
    assert predict_engine_health_limit(game.ship, 0.01).time_s is None
    future_fifteen = TemporalLimit("emergency_brake_limit", "proper", 5,
                                   validity="constant_wear_conditions")
    assert kinds(select_next_boundary(segment, 0, 100, health_limit=future_fifteen)) == ["emergency_brake_limit"]


def test_zero_repeat_is_explicit_and_new_snapshot_can_continue():
    segment = coast_for(origin(0.3), 100)
    at = select_next_boundary(segment, 20, 40,
                              health_limit=TemporalLimit("engine_health_threshold", "proper", 0))
    with pytest.raises(TemporalResolutionError, match="repeated zero"):
        select_next_boundary(segment, 20, 40,
                             health_limit=TemporalLimit("engine_health_threshold", "proper", 0),
                             seen_zero_selections=(at,))
    after = select_next_boundary(segment, 20, 40,
                                 health_limit=TemporalLimit("engine_health_threshold", "proper", None),
                                 seen_zero_selections=(at,))
    assert after.advance_galactic_s == 40

    another = select_next_boundary(segment, 20, 20,
                                   invalidation_reasons=("power_changed",),
                                   seen_zero_selections=(at,))
    with pytest.raises(TemporalResolutionError, match="repeated zero"):
        select_next_boundary(segment, 20, 30,
                             invalidation_reasons=("power_changed",),
                             seen_zero_selections=(at, another))


def test_partition_equivalence_with_fixed_conditions():
    segment = coast_for(origin(0.5, at=100), 200)
    health = TemporalLimit("engine_health_threshold", "proper", 50 * math.sqrt(0.75))
    full = select_next_boundary(segment, 110, 100, health_limit=health)
    first = select_next_boundary(segment, 110, 20, health_limit=health)
    assert kinds(first) == ["requested_horizon"]
    remaining = health.time_s - proper_time_in_segment(segment, 30) + proper_time_in_segment(segment, 10)
    second = select_next_boundary(segment, 130, 80,
                                  health_limit=TemporalLimit("engine_health_threshold", "proper", remaining))
    assert second.at_galactic_s == pytest.approx(full.at_galactic_s)


def test_large_absolute_time_and_unrepresentable_positive_steps():
    at = 1e16
    segment = coast_for(origin(0.5, at=at), 100)
    selected = select_next_boundary(segment, at, 10)
    assert selected.at_galactic_s == at + 10
    with pytest.raises(TemporalResolutionError):
        select_next_boundary(segment, at, 0.1)
    with pytest.raises(TemporalResolutionError):
        select_next_boundary(segment, at, 10,
                             job_limits=(TemporalLimit("propulsion_job", "galactic", 0.1),))
    resolved = select_next_boundary(
        segment, at, 10,
        health_limit=TemporalLimit("engine_health_threshold", "proper", 1e-20))
    assert resolved.at_galactic_s == math.nextafter(at, math.inf)
    assert resolved.advance_galactic_s == math.ulp(at)
    assert kinds(resolved) == ["engine_health_threshold"]
    large_proper_clock = coast_for(origin(0.5, proper=1e16), 100)
    with pytest.raises(TemporalResolutionError, match="proper-clock"):
        select_next_boundary(large_proper_clock, 0, 0.1)


def test_pure_deterministic_and_invalid_queries():
    segment = coast_for(origin(0.3, at=100), 100)
    limit = TemporalLimit("engine_health_threshold", "proper", 10)
    before = asdict(segment), asdict(limit)
    selected = select_next_boundary(segment, 120, 50, health_limit=limit)
    assert selected == select_next_boundary(segment, 120, 50, health_limit=limit)
    assert before == (asdict(segment), asdict(limit))
    with pytest.raises(FrozenInstanceError):
        selected.advance_galactic_s = 1
    for now in (99, 201, math.nan):
        with pytest.raises(ValueError):
            select_next_boundary(segment, now, 10)
