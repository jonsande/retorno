"""Pure cuts for a planned relativistic trajectory."""
from dataclasses import FrozenInstanceError, asdict
import math

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.nav_boundaries import TemporalLimit, predict_engine_health_limit
from retorno.core.nav_coordinator import select_next_boundary
from retorno.core.nav_physics import galactic_time_at_proper, plan_travel, sample_travel


@pytest.fixture
def plan():
    return plan_travel(1e18, 0.5, 9.81)


def kinds(selection):
    return [cause.limit.kind for cause in selection.causes]


def test_requested_horizon_and_profile_phases(plan):
    accel, brake, end = plan.cruise_start_s, plan.braking_start_s, plan.total_galactic_s
    assert kinds(select_next_boundary(plan, 0, accel / 2)) == ["requested_horizon"]
    assert kinds(select_next_boundary(plan, 0, accel * 1.5)) == ["acceleration_end"]
    assert kinds(select_next_boundary(plan, accel, brake - accel + 1)) == ["braking_start"]
    assert kinds(select_next_boundary(plan, brake, end - brake + 1)) == ["profile_end"]
    assert kinds(select_next_boundary(plan, 0, accel)) == ["requested_horizon", "acceleration_end"]
    assert select_next_boundary(plan, end, 100).advance_galactic_s == 0


def test_candidates_simultaneous_and_conditional_metadata(plan):
    now = plan.cruise_start_s
    health = TemporalLimit("engine_health_threshold", "proper", 10,
                           validity="constant_wear_conditions")
    proper_at_job = sample_travel(plan, now + 20).proper_s - sample_travel(plan, now).proper_s
    health = TemporalLimit("engine_health_threshold", "proper", proper_at_job,
                           validity="constant_wear_conditions")
    jobs = (TemporalLimit("propulsion_job", "galactic", 20, job_id="A",
                          validity="running_if_uninterrupted", uncertainty_reason="may_fail"),
            TemporalLimit("propulsion_job", "galactic", 20, job_id="B",
                          validity="running_if_uninterrupted", uncertainty_reason="may_fail"))
    result = select_next_boundary(plan, now, 100, health_limit=health, job_limits=jobs)
    assert result.advance_galactic_s == pytest.approx(20)
    assert set(kinds(result)) == {"engine_health_threshold", "propulsion_job"}
    assert [c.limit.job_id for c in result.causes if c.limit.job_id] == ["A", "B"]
    assert result.requires_reevaluation
    assert asdict(health)["time_s"] == proper_at_job
    with pytest.raises(FrozenInstanceError):
        result.advance_galactic_s = 9


@pytest.mark.parametrize("fraction", [0.3, 0.8])
def test_proper_limit_in_acceleration_and_braking(plan, fraction):
    tau = plan.acceleration_proper_s * fraction
    expected = galactic_time_at_proper(plan, tau)
    result = select_next_boundary(plan, 0, plan.total_galactic_s,
                                  health_limit=TemporalLimit("engine_health_threshold", "proper", tau))
    assert result.at_galactic_s == pytest.approx(expected)
    assert result.accumulated_proper_s == pytest.approx(tau)
    brake_tau = plan.total_proper_s - tau
    at_brake = galactic_time_at_proper(plan, brake_tau)
    now = plan.braking_start_s
    remaining = brake_tau - sample_travel(plan, now).proper_s
    result = select_next_boundary(plan, now, plan.total_galactic_s - now,
                                  health_limit=TemporalLimit("engine_health_threshold", "proper", remaining))
    assert result.at_galactic_s == pytest.approx(at_brake)
    assert result.accumulated_proper_s == pytest.approx(brake_tau)


def test_partial_query_and_partition_equivalence(plan):
    now = plan.cruise_start_s + 10
    event = now + 50
    delta_proper = sample_travel(plan, event).proper_s - sample_travel(plan, now).proper_s
    health = TemporalLimit("engine_health_threshold", "proper", delta_proper)
    full = select_next_boundary(plan, now, 100, health_limit=health)
    first = select_next_boundary(plan, now, 20, health_limit=health)
    assert kinds(first) == ["requested_horizon"]
    remaining_proper = delta_proper - (sample_travel(plan, now + 20).proper_s - sample_travel(plan, now).proper_s)
    second = select_next_boundary(plan, now + 20, 80,
                                  health_limit=TemporalLimit("engine_health_threshold", "proper", remaining_proper))
    assert second.at_galactic_s == pytest.approx(full.at_galactic_s)


def test_zero_health_queued_and_invalidated(plan):
    game = create_initial_state_sandbox(seed=301)
    game.ship.systems["engines"].health = Balance.SYSTEM_HEALTH_CRITICAL
    health = predict_engine_health_limit(game.ship, 0.01)
    assert health.validity == "at_threshold_not_yet_critical"
    queued = TemporalLimit("job_activation", "galactic", 0, job_id="Q",
                           validity="queued_activation_candidate")
    at = select_next_boundary(plan, 2, 50, health_limit=health, job_limits=(queued,))
    assert at.advance_galactic_s == 0
    assert kinds(at) == ["engine_health_threshold", "job_activation"]
    assert at.requires_reevaluation
    invalid = select_next_boundary(plan, 2, 50, health_limit=health, job_limits=(queued,),
                                   invalidation_reasons=("power_quality_changed",))
    assert kinds(invalid) == ["prediction_invalidated"]
    assert invalid.advance_galactic_s == 0


def test_phase_job_and_health_same_instant(plan):
    now = plan.braking_start_s - 10
    proper_remaining = plan.acceleration_proper_s + plan.cruise_proper_s - sample_travel(plan, now).proper_s
    result = select_next_boundary(
        plan, now, 50,
        health_limit=TemporalLimit("engine_health_threshold", "proper", proper_remaining),
        job_limits=(TemporalLimit("propulsion_job", "galactic", 10, job_id="repair"),),
    )
    assert result.at_galactic_s == plan.braking_start_s
    assert set(kinds(result)) == {"braking_start", "engine_health_threshold", "propulsion_job"}


def test_zero_requested_horizon(plan):
    result = select_next_boundary(plan, 5, 0)
    assert result.advance_galactic_s == 0
    assert kinds(result) == ["requested_horizon"]
    assert not result.requires_reevaluation


def test_deferred_and_near_simultaneous_do_not_advance_past_earliest(plan):
    now = plan.cruise_start_s
    near = math.nextafter(now + 10, math.inf)
    limits = (TemporalLimit("propulsion_job", "galactic", 10, job_id="A"),
              TemporalLimit("propulsion_job", "galactic", near - now, job_id="B"),
              TemporalLimit("propulsion_job", "galactic", None, job_id="Q"))
    result = select_next_boundary(plan, now, 20, job_limits=limits)
    assert result.at_galactic_s == now + 10
    assert [cause.limit.job_id for cause in result.causes] == ["A", "B"]
    assert result.causes[1].at_galactic_s > result.at_galactic_s
    assert [limit.job_id for limit in result.deferred] == ["Q"]


@pytest.mark.parametrize("bad", [-1, math.nan, math.inf])
def test_invalid_input(plan, bad):
    with pytest.raises(ValueError):
        select_next_boundary(plan, 0, bad)
    with pytest.raises(ValueError):
        select_next_boundary(plan, 0, 10, job_limits=(TemporalLimit("x", "galactic", bad),))
    with pytest.raises(ValueError):
        galactic_time_at_proper(plan, bad)
    with pytest.raises(ValueError):
        select_next_boundary(plan, bad, 10)
    with pytest.raises(ValueError):
        select_next_boundary(plan, 0, 10, health_limit=TemporalLimit("x", "galactic", 1))


def test_deterministic_and_pure(plan):
    health = TemporalLimit("engine_health_threshold", "proper", 100)
    before = asdict(plan), asdict(health)
    a = select_next_boundary(plan, 2, 1000, health_limit=health)
    b = select_next_boundary(plan, 2, 1000, health_limit=health)
    assert a == b
    assert before == (asdict(plan), asdict(health))
