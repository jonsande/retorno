"""Pure recovery plans from real and boundary physical transit states."""
from copy import deepcopy
from dataclasses import replace
import math
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, LIGHT_YEAR_M, MotionState,
                                      brake_to_stop, braking_profile, coast_for,
                                      sample_segment)
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.core.nav_state import (InertialContinuation, PhysicalTransitState,
                                    PropulsionAuthorization)
from retorno.model.jobs import JobStatus
from retorno.model.systems import SystemState
from tests.test_nav_engine_repair_inertia import enqueue_repair, repairable_inertia
from tests.test_nav_engine_safety_brake import save_and_load


@pytest.fixture(scope="module")
def repaired_source():
    game = repairable_inertia()
    job = enqueue_repair(game)
    Engine().tick(game, job.eta_s)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.inertial_continuation is not None
    return game


def _route_at(game, distance_m):
    origin = game.world.space.nodes[game.ship.transit_from]
    destination = game.world.space.nodes[game.ship.physical_transit.original_destination_id]
    vector = (destination.x_ly - origin.x_ly,
              destination.y_ly - origin.y_ly,
              destination.z_ly - origin.z_ly)
    norm = math.sqrt(sum(component * component for component in vector))
    scale = distance_m / (LIGHT_YEAR_M * norm)
    destination.x_ly = origin.x_ly + vector[0] * scale
    destination.y_ly = origin.y_ly + vector[1] * scale
    destination.z_ly = origin.z_ly + vector[2] * scale
    _sync_world_position(game)


def _sync_world_position(game):
    origin = game.world.space.nodes[game.ship.transit_from]
    destination = game.world.space.nodes[game.ship.physical_transit.original_destination_id]
    distance_ly = math.dist((origin.x_ly, origin.y_ly, origin.z_ly),
                            (destination.x_ly, destination.y_ly, destination.z_ly))
    fraction = game.ship.physical_transit.motion.distance_m / (distance_ly * LIGHT_YEAR_M)
    game.world.current_pos_ly = tuple(a + fraction * (b - a) for a, b in zip(
        (origin.x_ly, origin.y_ly, origin.z_ly),
        (destination.x_ly, destination.y_ly, destination.z_ly)))


def _deceleration(game):
    return abs(game.ship.physical_transit.inertial_continuation.interrupted_segment.proper_acceleration_m_s2)


def _synthetic_inertia(game, beta, distance_m=0.0, acceleration=1.0):
    physical = game.ship.physical_transit
    source = MotionState(game.clock.t, distance_m, beta, game.clock.ship_elapsed_s)
    interrupted = brake_to_stop(source, acceleration)
    coast = coast_for(source, 1.0)
    receipt = PropulsionAuthorization(interrupted, physical.original_destination_id, .5, 1.0)
    history = InertialContinuation(interrupted, 0.0, physical.original_destination_id,
                                   coast, propulsion_receipt=receipt)
    game.ship.physical_transit = PhysicalTransitState(
        coast, 0.0, physical.original_destination_id, "coast",
        braking_started=True, replan_required=True, inertial_continuation=history)
    _sync_world_position(game)


def test_productive_repair_yields_pure_conditional_plan(repaired_source):
    game = deepcopy(repaired_source)
    before = pickle.dumps(game)
    plan = plan_inertial_recovery(game)
    assert plan.decision in {"coast_then_brake", "brake_now", "emergency_brake"}
    assert plan.physical_braking_available and plan.operational_braking_available
    assert plan.requires_fuel_authorization and plan.operational_outcome_conditional
    assert plan.start == game.ship.physical_transit.motion
    assert plan.destination_id == game.ship.physical_transit.original_destination_id
    assert plan.predicted_stop.beta == 0
    assert all(segment.proper_acceleration_m_s2 <= 0 for segment in plan.segments)
    assert plan.last_possible_brake_position_m == plan.recommended_brake_position_m
    assert plan.is_current(game)
    assert pickle.dumps(game) == before
    loaded = save_and_load(game)
    assert plan.is_current(loaded)
    assert plan_inertial_recovery(loaded) == plan
    assert loaded.ship.physical_transit.inertial_continuation.propulsion_receipt == (
        game.ship.physical_transit.inertial_continuation.propulsion_receipt)


def test_real_repair_changes_no_propulsion_into_conditional_braking_plan():
    game = repairable_inertia()
    before = plan_inertial_recovery(game)
    assert before.decision == "no_propulsion"
    assert not before.physical_braking_available
    fuel = game.ship.antimatter_capsules
    job = enqueue_repair(game)
    Engine().tick(game, job.eta_s)
    assert not before.is_current(game)
    after = plan_inertial_recovery(game)
    assert after.decision in {"coast_then_brake", "brake_now", "emergency_brake"}
    assert after.braking_segment is not None
    assert after.start == game.ship.physical_transit.motion
    assert game.ship.antimatter_capsules == fuel


@pytest.mark.parametrize("gap,decision", [
    (1e8, "coast_then_brake"), (-1e8, "emergency_brake"),
])
def test_distance_to_b_selects_coast_or_emergency(repaired_source, gap, decision):
    game = deepcopy(repaired_source)
    start = game.ship.physical_transit.motion
    braking_m = braking_profile(start.beta, _deceleration(game)).distance_m
    _route_at(game, start.distance_m + braking_m + gap)
    plan = plan_inertial_recovery(game)
    assert plan.decision == decision
    assert plan.predicted_stop.beta == 0
    assert plan.braking_distance_m == pytest.approx(braking_m)
    if gap > 0:
        assert len(plan.segments) == 2
        assert plan.coast_segment.start == start
        assert sample_segment(plan.coast_segment, plan.coast_segment.duration_galactic_s) == plan.braking_segment.start
        assert plan.predicted_stop.distance_m == pytest.approx(plan.destination_distance_m, abs=1e3)
        assert plan.coast_segment.duration_galactic_s > 0
        assert plan.braking_segment.start.galactic_s > start.galactic_s
        assert plan.braking_segment.start.proper_s > start.proper_s
    else:
        assert len(plan.segments) == 1 and plan.brake_immediately
        assert plan.overshoot_inevitable
        assert plan.predicted_stop.distance_m > plan.destination_distance_m
        low, high = 0.0, plan.braking_segment.duration_galactic_s
        for _ in range(60):
            middle = (low + high) / 2
            if sample_segment(plan.braking_segment, middle).distance_m < plan.destination_distance_m:
                low = middle
            else:
                high = middle
        assert sample_segment(plan.braking_segment, high).beta > 0


def test_exact_braking_boundary_has_no_artificial_coast(repaired_source):
    game = deepcopy(repaired_source)
    _synthetic_inertia(game, .4)
    start = game.ship.physical_transit.motion
    braking_m = braking_profile(start.beta, _deceleration(game)).distance_m
    target_m = start.distance_m + braking_m
    with patch("retorno.core.nav_recovery.light_years_to_metres", return_value=target_m):
        plan = plan_inertial_recovery(game)
    assert plan.remaining_distance_m == braking_m
    assert plan.decision == "brake_now"
    assert plan.coast_segment is None
    assert plan.braking_segment.start == start
    assert plan.predicted_stop.distance_m == pytest.approx(target_m, abs=1e3)


def test_already_beyond_b_never_reverses_or_arrives(repaired_source):
    game = deepcopy(repaired_source)
    start = game.ship.physical_transit.motion
    _route_at(game, start.distance_m - 1e8)
    old_node = game.world.current_node_id
    plan = plan_inertial_recovery(game)
    assert plan.decision == "emergency_brake"
    assert plan.reason == "already_beyond_destination"
    assert plan.remaining_distance_m < 0
    assert plan.predicted_stop.distance_m > start.distance_m
    assert game.world.current_node_id == old_node
    assert all(segment.end_beta >= 0 for segment in plan.segments)


@pytest.mark.parametrize("health,available", [
    (Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH - 1e-12, False),
    (Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH, True),
    (Balance.SYSTEM_HEALTH_CRITICAL, True),
])
def test_exact_engine_integrity_gates(repaired_source, health, available):
    game = deepcopy(repaired_source)
    engine = game.ship.systems["engines"]
    engine.health = health
    engine.state = SystemState.CRITICAL if health < .35 else SystemState.DAMAGED
    plan = plan_inertial_recovery(game)
    assert plan.physical_braking_available is available
    assert plan.operational_braking_available is available
    assert (plan.decision != "no_propulsion") is available


@pytest.mark.parametrize("obstacle", ["engine_isolated", "engine_offline",
                                      "power_core_offline", "distribution_offline"])
def test_isolation_or_power_prevents_powered_plan(repaired_source, obstacle):
    game = deepcopy(repaired_source)
    if obstacle == "engine_isolated":
        game.ship.systems["engines"].forced_offline = True
    elif obstacle == "engine_offline":
        game.ship.systems["engines"].state = SystemState.OFFLINE
    else:
        key = "power_core" if obstacle == "power_core_offline" else "energy_distribution"
        game.ship.systems[key].state = SystemState.OFFLINE
    plan = plan_inertial_recovery(game)
    assert plan.decision == "no_propulsion"
    assert plan.segments == () and plan.predicted_stop is None
    assert not plan.requires_fuel_authorization


def test_plan_invalidates_on_motion_health_destination_and_power_changes(repaired_source):
    game = deepcopy(repaired_source)
    plan = plan_inertial_recovery(game)
    Engine().tick(game, 1)
    assert not plan.is_current(game)
    game = deepcopy(repaired_source)
    plan = plan_inertial_recovery(game)
    game.ship.systems["engines"].health -= .01
    assert not plan.is_current(game)
    game = deepcopy(repaired_source)
    plan = plan_inertial_recovery(game)
    game.world.space.nodes[plan.destination_id].x_ly += .001
    assert not plan.is_current(game)
    game = deepcopy(repaired_source)
    plan = plan_inertial_recovery(game)
    game.ship.power.e_batt_kwh -= .01
    assert not plan.is_current(game)
    game = deepcopy(repaired_source)
    plan = plan_inertial_recovery(game)
    enqueue_repair(game)
    assert not plan.is_current(game)
    assert not plan.is_current(repaired_source, proper_deceleration_m_s2=2.0)


def test_invalid_source_returns_nonexecuting_plan(repaired_source):
    game = deepcopy(repaired_source)
    game.ship.physical_transit = None
    plan = plan_inertial_recovery(game)
    assert plan.decision == "invalid"
    assert plan.segments == () and not plan.is_current(game)
    game = deepcopy(repaired_source)
    assert plan_inertial_recovery(game, proper_deceleration_m_s2=-1).decision == "invalid"
    game.world.current_pos_ly = (0.0, 0.0, 0.0)
    assert plan_inertial_recovery(game).decision == "invalid"


@pytest.mark.parametrize("beta", [1e-8, .9])
def test_small_and_relativistic_speed_against_independent_rapidity(repaired_source, beta):
    game = deepcopy(repaired_source)
    _synthetic_inertia(game, beta, 1e12)
    stop_m = (LIGHT_SPEED_M_S ** 2) * 2 * math.sinh(math.atanh(beta) / 2) ** 2
    stop_t = LIGHT_SPEED_M_S * beta / math.sqrt((1 - beta) * (1 + beta))
    stop_tau = LIGHT_SPEED_M_S * math.atanh(beta)
    plan = plan_inertial_recovery(game)
    assert plan.decision != "invalid"
    assert plan.braking_distance_m == pytest.approx(stop_m, rel=1e-6, abs=1.0)
    assert plan.braking_segment.start.beta == beta
    assert plan.braking_segment.duration_galactic_s == pytest.approx(stop_t)
    assert plan.predicted_stop.proper_s - plan.braking_segment.start.proper_s == pytest.approx(stop_tau)
    assert plan.predicted_stop.beta == 0


def test_near_braking_boundary_uses_strict_comparison(repaired_source):
    game = deepcopy(repaired_source)
    start = game.ship.physical_transit.motion
    braking_m = braking_profile(start.beta, _deceleration(game)).distance_m
    exact = start.distance_m + braking_m
    _route_at(game, exact)
    with patch("retorno.core.nav_recovery.light_years_to_metres",
               return_value=exact + 8 * math.ulp(exact)):
        longer = plan_inertial_recovery(game)
    with patch("retorno.core.nav_recovery.light_years_to_metres",
               return_value=exact - 8 * math.ulp(exact)):
        shorter = plan_inertial_recovery(game)
    assert longer.decision == "coast_then_brake"
    assert shorter.decision == "emergency_brake"


@pytest.mark.parametrize("beta,acceleration", [(.5, 1.0), (.893, .288)])
def test_large_braking_distance_beyond_b_is_valid_emergency(repaired_source, beta, acceleration):
    game = deepcopy(repaired_source)
    _synthetic_inertia(game, beta, 1e12, acceleration)
    _route_at(game, 5e11)
    before = pickle.dumps(game)
    plan = plan_inertial_recovery(game)
    independent_m = (2 * LIGHT_SPEED_M_S ** 2 / acceleration
                     * math.sinh(math.atanh(beta) / 2) ** 2)
    assert independent_m > plan.start.distance_m
    assert plan.decision == "emergency_brake"
    assert plan.reason == "already_beyond_destination"
    assert plan.braking_distance_m == pytest.approx(independent_m, rel=1e-12)
    assert plan.predicted_stop.distance_m > plan.start.distance_m
    assert pickle.dumps(game) == before


def test_external_deceleration_must_be_resupplied_for_freshness(repaired_source):
    game = deepcopy(repaired_source)
    historical = plan_inertial_recovery(game)
    external = plan_inertial_recovery(game, proper_deceleration_m_s2=2.0)
    before = pickle.dumps(game)
    assert historical.deceleration_source == "history"
    assert historical.is_current(game)
    assert external.deceleration_source == "external"
    assert external.decision != "invalid"
    assert not external.is_current(game)
    assert external.is_current(game, proper_deceleration_m_s2=2.0)
    assert not external.is_current(game, proper_deceleration_m_s2=2.01)
    assert external.is_current(save_and_load(game), proper_deceleration_m_s2=2.0)
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("destination_ly", [30.0, 60.0])
def test_recovery_at_tens_of_light_years(repaired_source, destination_ly):
    game = deepcopy(repaired_source)
    beta, acceleration = .893, .288
    _synthetic_inertia(game, beta, 1e12, acceleration)
    _route_at(game, destination_ly * LIGHT_YEAR_M)
    plan = plan_inertial_recovery(game)
    assert plan.decision in {"coast_then_brake", "emergency_brake"}
    independent_m = (2 * LIGHT_SPEED_M_S ** 2 / acceleration
                     * math.sinh(math.atanh(beta) / 2) ** 2)
    expected = ("coast_then_brake" if plan.remaining_distance_m > independent_m
                else "emergency_brake")
    assert plan.decision == expected
    assert plan.predicted_stop.beta == 0


def test_material_profile_disagreement_still_rejects(repaired_source):
    game = deepcopy(repaired_source)
    _synthetic_inertia(game, .5, 1e12, 1.0)
    actual = braking_profile(.5, 1.0)
    with patch("retorno.core.nav_recovery.braking_profile",
               return_value=replace(actual, distance_m=actual.distance_m + 1e7)):
        plan = plan_inertial_recovery(game)
    assert plan.decision == "invalid"
    assert plan.reason == "braking_profile_and_segment_disagree"


def test_material_coast_closure_disagreement_still_rejects(repaired_source):
    game = deepcopy(repaired_source)
    start = game.ship.physical_transit.motion
    _route_at(game, start.distance_m + 2 * braking_profile(
        start.beta, _deceleration(game)).distance_m)
    original_sample = sample_segment

    def shifted_brake_endpoint(segment, elapsed):
        motion = original_sample(segment, elapsed)
        if (segment.proper_acceleration_m_s2 < 0
                and segment.start.galactic_s > start.galactic_s
                and elapsed == segment.duration_galactic_s):
            return replace(motion, distance_m=motion.distance_m + 1e7)
        return motion

    with patch("retorno.core.nav_recovery.sample_segment", side_effect=shifted_brake_endpoint):
        plan = plan_inertial_recovery(game)
    assert plan.decision == "invalid"
    assert plan.reason == "braking_geometry_did_not_close"


def test_deterministic_recovery_precision_sweep(repaired_source):
    game = deepcopy(repaired_source)
    decisions = set()
    checked = 0
    for beta in (1e-4, .05, .25, .5, .75, .893, .99):
        for acceleration in (.288, 1.0, 10.0, 1e4, 1e7):
            independent_m = (2 * LIGHT_SPEED_M_S ** 2 / acceleration
                             * math.sinh(math.atanh(beta) / 2) ** 2)
            for travelled in (0.0, 1e6, 1e12, 1e16, 1e18):
                _synthetic_inertia(game, beta, travelled, acceleration)
                for destination_m in (max(1.0, travelled / 2),
                                      travelled + independent_m / 2,
                                      travelled + 2 * independent_m,
                                      travelled + max(1e18, 4 * independent_m)):
                    _route_at(game, max(1.0, destination_m))
                    plan = plan_inertial_recovery(game)
                    checked += 1
                    assert plan.reason not in {
                        "braking_profile_and_segment_disagree",
                        "braking_geometry_did_not_close",
                    }, (beta, acceleration, travelled, destination_m, plan.reason)
                    if plan.decision == "invalid":
                        assert plan.reason == "coast_or_brake_below_numerical_resolution"
                        continue
                    assert plan.braking_distance_m == pytest.approx(
                        independent_m, rel=1e-12, abs=1e-6)
                    remaining = plan.remaining_distance_m
                    braking_m = plan.braking_distance_m
                    expected = ("coast_then_brake" if remaining > braking_m else
                                "brake_now" if remaining == braking_m else
                                "emergency_brake")
                    assert plan.decision == expected
                    decisions.add(plan.decision)
    assert checked == 700
    assert {"coast_then_brake", "emergency_brake"} <= decisions
