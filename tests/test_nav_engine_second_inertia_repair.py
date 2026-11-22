"""Productive engine repair after either paid recovery interruption."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import LIGHT_SPEED_M_S, light_years_to_metres, brake_to_stop
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus
from retorno.model.world import distance_between_nodes_ly
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_recovery_coast_loss import paid_coast
from tests.test_nav_engine_recovery_reinterruption import recovery_brake_at_risk
from tests.test_nav_engine_repair_inertia import enqueue_repair
from tests.test_nav_engine_safety_brake import save_and_load, wear_cut


def second_inertia(origin, *, activate=True):
    game, cut = (recovery_brake_at_risk() if origin == "brake"
                 else (paid_coast(), None))
    if cut is None:
        cut = wear_cut(game, .15)
    assert cut is not None
    Engine().tick(game, cut)
    game.ship.systems["engines"].base_decay_per_s = .00001
    if activate:
        Engine().tick(game, 1)
        assert game.ship.physical_transit.inertial_continuation is not None
    return game


def historical_record(game, origin):
    physical = game.ship.physical_transit
    record = (physical.recovery_interruption if origin == "brake"
              else physical.recovery_coast_interruption)
    assert record is not None
    return record


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_real_second_repair_moves_and_keeps_both_histories(origin):
    game = save_and_load(second_inertia(origin))
    record = historical_record(game, origin)
    original_first = record.execution.inertial_history
    payment = record.execution.authorization
    fuel = game.ship.antimatter_capsules
    original_intent = game.ship.physical_transit.recovery_intent
    before_repair = game.ship.physical_transit.motion
    battery = game.ship.drones["D1"].battery
    dose = game.ship.drones["D1"].dose_rad
    integrity = game.ship.drones["D1"].integrity
    scrap = game.ship.cargo_scrap
    job = enqueue_repair(game)
    assert game.ship.cargo_scrap < scrap and job.status == JobStatus.QUEUED
    game = save_and_load(game)
    owners = tuple(getattr(game, name) for name in
                   ("ship", "clock", "world", "jobs", "events", "meta"))
    GameLoop(Engine(), game).step(3)
    running = game.jobs.jobs[job.internal_id]
    assert running.status == JobStatus.RUNNING
    assert running.eta_s == pytest.approx(job.eta_s - 3)
    assert game.ship.physical_transit.motion.beta == before_repair.beta
    assert game.ship.physical_transit.motion.distance_m > before_repair.distance_m
    assert game.ship.drones["D1"].battery < battery
    assert game.ship.drones["D1"].dose_rad > dose
    assert game.ship.drones["D1"].integrity < integrity
    game = save_and_load(game)
    GameLoop(Engine(), game).step(game.jobs.jobs[job.internal_id].eta_s - .5)
    almost = save_and_load(game)
    assert almost.jobs.jobs[job.internal_id].eta_s == pytest.approx(.5)
    health_before_finish = almost.ship.systems["engines"].health
    motion_before_finish = almost.ship.physical_transit.motion
    owners = tuple(getattr(almost, name) for name in
                   ("ship", "clock", "world", "jobs", "events", "meta"))
    GameLoop(Engine(), almost).step(almost.jobs.jobs[job.internal_id].eta_s)
    repaired = almost.ship.physical_transit
    assert almost.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert almost.ship.systems["engines"].health > health_before_finish
    assert almost.ship.systems["engines"].health > Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    assert repaired.motion.beta == motion_before_finish.beta == before_repair.beta
    assert repaired.motion.distance_m > motion_before_finish.distance_m
    assert repaired.recovery_execution is None
    assert historical_record(almost, origin) == record
    assert historical_record(almost, origin).execution.authorization == payment
    assert historical_record(almost, origin).execution.inertial_history == original_first
    assert repaired.recovery_intent == original_intent
    assert repaired.recovery_intent.status == "used"
    assert almost.ship.antimatter_capsules == fuel
    assert all(getattr(almost, name) is owner for name, owner in zip(
        ("ship", "clock", "world", "jobs", "events", "meta"), owners))
    assert len([e for e in almost.events.recent if e.type == EventType.JOB_COMPLETED]) == 2
    assert not any(e.type == EventType.ARRIVED for e in almost.events.recent)
    saved = save_and_load(almost)
    assert historical_record(saved, origin) == record
    assert saved.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    GameLoop(Engine(), saved).step(2)
    assert saved.ship.physical_transit.motion.beta == before_repair.beta
    assert saved.ship.physical_transit.motion.distance_m > repaired.motion.distance_m
    assert saved.ship.antimatter_capsules == fuel
    assert len([e for e in saved.events.recent if e.type == EventType.JOB_COMPLETED]) == 2
    prior = pickle.dumps(saved)
    with pytest.raises(RuntimeError, match="second interrupted recovery"):
        Engine().prepare_inertial_recovery(saved)
    with pytest.raises(RuntimeError):
        Engine().authorize_manual_inertial_recovery(saved, max_capsules=10)
    with pytest.raises(RuntimeError, match="inertial motion cannot prepare"):
        Engine().prepare_physical_segment(
            saved, brake_to_stop(saved.ship.physical_transit.motion, 1e7),
            saved.ship.physical_transit.original_destination_id, "brake", pricing_speed=.5)
    assert pickle.dumps(saved) == prior


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_failed_second_repair_is_productive_and_does_not_repeat(origin):
    game = second_inertia(origin)
    record = historical_record(game, origin)
    job = enqueue_repair(game)
    reserved = job.params["repair_scrap"]
    remaining_scrap = game.ship.cargo_scrap
    fuel = game.ship.antimatter_capsules
    health = game.ship.systems["engines"].health
    motion = game.ship.physical_transit.motion
    with patch.object(Balance, "REPAIR_JOB_FAIL_P_BASE", 1.0):
        Engine().tick(game, job.eta_s)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.FAILED
    assert game.ship.systems["engines"].health < health
    assert game.ship.physical_transit.motion.beta == motion.beta
    assert game.ship.physical_transit.motion.distance_m > motion.distance_m
    assert remaining_scrap <= game.ship.cargo_scrap <= remaining_scrap + reserved
    assert game.ship.antimatter_capsules == fuel
    assert game.meta.rng_counter > 0
    assert historical_record(game, origin) == record
    assert len([e for e in game.events.recent if e.type == EventType.JOB_FAILED]) == 1
    loaded = save_and_load(game)
    Engine().tick(loaded, 1)
    assert loaded.jobs.jobs[job.internal_id].status == JobStatus.FAILED
    assert len([e for e in loaded.events.recent if e.type == EventType.JOB_FAILED]) == 1


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_zero_eta_repair_after_second_cut_does_not_resume_spent_recovery(origin):
    game = second_inertia(origin, activate=False)
    record = historical_record(game, origin)
    job = enqueue_repair(game)
    game.jobs.jobs[job.internal_id].eta_s = 0.0
    start = game.ship.physical_transit.motion
    Engine().tick(game, 1)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.recovery_execution is None
    assert historical_record(game, origin) == record
    assert game.ship.physical_transit.motion.beta == start.beta
    assert game.ship.physical_transit.motion.distance_m > start.distance_m


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_second_repair_completion_matches_subdivided_interval(origin):
    whole = second_inertia(origin)
    job = enqueue_repair(whole)
    split = deepcopy(whole)
    Engine().tick(whole, job.eta_s + 2)
    Engine().tick(split, job.eta_s / 2)
    Engine().tick(split, split.jobs.jobs[job.internal_id].eta_s)
    Engine().tick(split, 2)
    assert whole.jobs.jobs[job.internal_id].status == split.jobs.jobs[job.internal_id].status
    assert whole.ship.physical_transit.motion.beta == split.ship.physical_transit.motion.beta
    assert whole.ship.physical_transit.motion.distance_m == pytest.approx(
        split.ship.physical_transit.motion.distance_m)
    assert whole.ship.systems["engines"].health == pytest.approx(
        split.ship.systems["engines"].health)
    assert whole.ship.drones["D1"].battery == pytest.approx(split.ship.drones["D1"].battery)
    assert historical_record(whole, origin) == historical_record(split, origin)
    assert whole.ship.antimatter_capsules == split.ship.antimatter_capsules


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_real_repair_after_destination_overshoot(origin):
    game = second_inertia(origin)
    game.ship.systems["engines"].base_decay_per_s = 0
    physical = game.ship.physical_transit
    origin_id = game.ship.transit_from or game.ship.current_node_id
    route_m = light_years_to_metres(distance_between_nodes_ly(
        game.world, origin_id, physical.original_destination_id))
    time_to_b = (route_m - physical.motion.distance_m) / (
        LIGHT_SPEED_M_S * physical.motion.beta)
    assert time_to_b > 0
    Engine().tick(game, time_to_b + 1)
    game = save_and_load(game)
    assert game.ship.physical_transit.motion.distance_m > route_m
    record = historical_record(game, origin)
    fuel = game.ship.antimatter_capsules
    job = enqueue_repair(game)
    Engine().tick(game, job.eta_s)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.motion.distance_m > route_m
    assert game.ship.physical_transit.motion.beta == physical.motion.beta
    assert historical_record(game, origin) == record
    assert game.ship.antimatter_capsules == fuel
    assert game.world.current_node_id != physical.original_destination_id
    assert not any(e.type == EventType.ARRIVED for e in game.events.recent)
    assert save_and_load(game).ship.physical_transit.motion.distance_m > route_m


@pytest.mark.parametrize("obstacle", ["wrong_sector", "reserve", "radiation",
                                      "integrity", "multiple_drones", "multiple_jobs",
                                      "multiple_queued",
                                      "power", "deferred_radiation"])
def test_second_repair_unsupported_boundaries_reject_atomically(obstacle):
    game = second_inertia("coast")
    job = enqueue_repair(game)
    drone = game.ship.drones["D1"]
    context = None
    if obstacle == "wrong_sector":
        drone.location = DroneLocation("ship_sector", "WRONG-SECTOR")
    elif obstacle == "reserve":
        drone.battery = .05
    elif obstacle == "radiation":
        drone.dose_rad = Balance.DRONE_RAD_DOSE_WARN - .00001
    elif obstacle == "integrity":
        drone.integrity = Balance.DRONE_RECALL_MIN_INTEGRITY + .00000001
    elif obstacle == "multiple_drones":
        sector = game.ship.systems["engines"].sector_id
        game.ship.drones["D2"] = DroneState("D2", "Operator D2", DroneStatus.DEPLOYED,
                                              DroneLocation("ship_sector", sector))
    elif obstacle in {"multiple_jobs", "multiple_queued"}:
        other = deepcopy(job)
        other.job_id = "SECOND_J2"
        other.internal_id = "SECOND_JOB_ID"
        other.status = (JobStatus.RUNNING if obstacle == "multiple_jobs"
                        else JobStatus.QUEUED)
        job.status = JobStatus.RUNNING
        game.jobs.jobs[other.internal_id] = other
        game.jobs.active_job_ids.append(other.internal_id)
    elif obstacle == "power":
        game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    else:
        context = patch("retorno.core.engine.radiation_limits", return_value=(
            TemporalLimit("internal_high", "proper", None,
                          validity="numerical_isolation_unresolved"),))
    prior = pickle.dumps(game)
    if context is None:
        with pytest.raises(RuntimeError):
            Engine().tick(game, 1)
    else:
        with context, pytest.raises(RuntimeError):
            Engine().tick(game, 1)
    assert pickle.dumps(game) == prior


def test_later_unsupported_boundary_rolls_back_second_repair():
    game = second_inertia("brake")
    job = enqueue_repair(game)
    game.world.lore_placements.next_non_forced_eval_t = game.clock.t + job.eta_s + 1
    prior = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        Engine().tick(game, job.eta_s + 2)
    assert pickle.dumps(game) == prior
