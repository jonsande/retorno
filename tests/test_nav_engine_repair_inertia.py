"""Real engine repair jobs while the ship continues physical inertia."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from retorno.core.actions import Dock, Repair, Scan
from retorno.core.engine import Engine
from retorno.config.balance import Balance
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_physics import brake_to_stop
from retorno.core.nav_physics import LIGHT_SPEED_M_S, light_years_to_metres
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus, JobType
from retorno.runtime.loop import GameLoop
from retorno.model.world import distance_between_nodes_ly
from tests.test_nav_engine_inertial import safety_cut
from tests.test_nav_engine_safety_brake import save_and_load


def repairable_inertia():
    game = safety_cut()
    game.ship.systems["engines"].base_decay_per_s = .00001
    Engine().tick(game, 1)
    assert game.ship.physical_transit.inertial_continuation is not None
    sector = game.ship.systems["engines"].sector_id
    drone = DroneState("D1", "Operator D1", DroneStatus.DEPLOYED,
                       DroneLocation("ship_sector", sector),
                       battery=1.0, integrity=1.0)
    game.ship.drones[drone.drone_id] = drone
    game.ship.cargo_scrap = 200
    return game


def enqueue_repair(game):
    fuel = game.ship.antimatter_capsules
    scrap = game.ship.cargo_scrap
    events = Engine().apply_action(game, Repair("D1", "engines"))
    assert any(event.type == EventType.JOB_QUEUED for event in events)
    jobs = [job for job in game.jobs.jobs.values()
            if job.job_type == JobType.REPAIR_SYSTEM
            and job.target and job.target.id == "engines"
            and job.status in {JobStatus.QUEUED, JobStatus.RUNNING}]
    assert len(jobs) == 1
    assert game.ship.cargo_scrap < scrap
    assert game.ship.antimatter_capsules == fuel
    return jobs[0]


def test_productive_repair_completes_at_causal_time_while_ship_moves():
    game = repairable_inertia()
    job = enqueue_repair(game)
    assert job.status == JobStatus.QUEUED
    duration = job.eta_s
    start = game.ship.physical_transit.motion
    health = game.ship.systems["engines"].health
    dose = game.ship.drones["D1"].dose_rad
    battery = game.ship.drones["D1"].battery
    integrity = game.ship.drones["D1"].integrity
    fuel = game.ship.antimatter_capsules
    owners = tuple(getattr(game, key) for key in ("ship", "clock", "world", "events", "meta"))
    GameLoop(Engine(), game).step(duration / 2)
    active = game.jobs.jobs[job.internal_id]
    assert active.status == JobStatus.RUNNING
    assert active.eta_s == pytest.approx(duration / 2)
    assert game.ship.physical_transit.motion.beta == start.beta
    assert game.ship.physical_transit.motion.distance_m > start.distance_m
    assert game.ship.systems["engines"].health < health
    assert game.ship.drones["D1"].dose_rad > dose
    assert game.ship.drones["D1"].battery < battery
    assert game.ship.drones["D1"].integrity < integrity
    before_finish = game.ship.systems["engines"].health
    GameLoop(Engine(), game).step(active.eta_s)
    completed = game.jobs.jobs[job.internal_id]
    assert completed.status == JobStatus.COMPLETED
    assert game.ship.systems["engines"].health > before_finish
    assert game.ship.systems["engines"].health > Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    assert game.ship.physical_transit.motion.beta == start.beta
    assert game.ship.physical_transit.replan_required
    assert game.ship.antimatter_capsules == fuel
    with pytest.raises(RuntimeError, match="inertial motion cannot prepare"):
        Engine().prepare_physical_segment(
            game, brake_to_stop(game.ship.physical_transit.motion, 1e7),
            "NOMINAL_B", "brake", pricing_speed=.5)
    assert all(getattr(game, key) is owner for key, owner in zip(
        ("ship", "clock", "world", "events", "meta"), owners))
    assert len([event for event in game.events.recent
                if event.type == EventType.JOB_COMPLETED]) == 1
    saved = pickle.loads(pickle.dumps(game))
    assert saved.ship.physical_transit.inertial_continuation == game.ship.physical_transit.inertial_continuation
    assert saved.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED


def test_repair_interval_rejects_prior_causal_failure_atomically():
    game = repairable_inertia()
    job = enqueue_repair(game)
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .000001
    prior = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        Engine().tick(game, min(5, job.eta_s / 2))
    assert pickle.dumps(game) == prior


def test_productive_repair_failure_consumes_rng_and_refunds_scrap_once():
    game = repairable_inertia()
    job = enqueue_repair(game)
    reserved = job.params["repair_scrap"]
    after_reservation = game.ship.cargo_scrap
    fuel = game.ship.antimatter_capsules
    before_motion = game.ship.physical_transit.motion
    with patch.object(Balance, "REPAIR_JOB_FAIL_P_BASE", 1.0):
        Engine().tick(game, job.eta_s)
    outcome = game.jobs.jobs[job.internal_id]
    assert outcome.status == JobStatus.FAILED
    assert game.ship.physical_transit.motion.beta == before_motion.beta
    assert game.ship.physical_transit.motion.distance_m > before_motion.distance_m
    assert game.ship.antimatter_capsules == fuel
    assert game.meta.rng_counter > 0
    assert game.ship.cargo_scrap >= after_reservation
    assert game.ship.cargo_scrap <= after_reservation + reserved
    assert len([event for event in game.events.recent
                if event.type == EventType.JOB_FAILED]) == 1
    saved = pickle.loads(pickle.dumps(game))
    assert saved.jobs.jobs[job.internal_id].status == JobStatus.FAILED
    Engine().tick(saved, 1)
    assert len([event for event in saved.events.recent
                if event.type == EventType.JOB_FAILED]) == 1


def test_queued_repair_activates_before_power_forecast_and_finishes_once():
    game = repairable_inertia()
    base_load = Engine()._compute_load_kw(game)
    job = enqueue_repair(game)
    assert job.status == JobStatus.QUEUED
    # Productive repairs currently have zero configured draw; exercise the
    # existing scheduler load field without changing balance or job effects.
    job.power_draw_kw = 1.0
    Engine().tick(game, 1)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.RUNNING
    assert game.ship.power.p_load_kw == pytest.approx(base_load + job.power_draw_kw)
    assert game.jobs.jobs[job.internal_id].eta_s == pytest.approx(job.eta_s - 1)


@pytest.mark.parametrize("obstacle", ["wrong_sector", "reserve", "drone_radiation", "drone_integrity"])
def test_operator_or_drone_boundary_rejects_atomically(obstacle):
    game = repairable_inertia()
    enqueue_repair(game)
    drone = game.ship.drones["D1"]
    if obstacle == "wrong_sector":
        drone.location = DroneLocation("ship_sector", "WRONG-SECTOR")
    elif obstacle == "reserve":
        drone.battery = .05
    else:
        if obstacle == "drone_radiation":
            drone.dose_rad = Balance.DRONE_RAD_DOSE_WARN - .00001
        else:
            drone.integrity = Balance.DRONE_RECALL_MIN_INTEGRITY + .00000001
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_late_unsupported_event_rolls_back_completed_repair():
    game = repairable_inertia()
    job = enqueue_repair(game)
    game.world.lore_placements.next_non_forced_eval_t = game.clock.t + job.eta_s + 1
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError):
        Engine().tick(game, job.eta_s + 2)
    assert pickle.dumps(game) == before


def test_ship_radiation_uncertainty_rejects_repair_tick_atomically():
    game = repairable_inertia()
    enqueue_repair(game)
    before = pickle.dumps(game)
    with patch("retorno.core.engine.radiation_limits", return_value=(
        TemporalLimit("internal_high", "proper", None,
                      validity="numerical_isolation_unresolved"),
    )):
        with pytest.raises(RuntimeError):
            Engine().tick(game, 1)
    assert pickle.dumps(game) == before


@pytest.mark.parametrize("same_eta", [False, True])
def test_concurrent_repairs_reject_without_advancing_either_job(same_eta):
    game = repairable_inertia()
    first = enqueue_repair(game)
    second = deepcopy(first)
    second.job_id = "J2"
    second.internal_id = "JOB2"
    second.status = JobStatus.RUNNING
    second.eta_s = first.eta_s if same_eta else first.eta_s + 5
    first.status = JobStatus.RUNNING
    game.jobs.jobs[second.internal_id] = second
    game.jobs.active_job_ids.append(second.internal_id)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="one eligible repair interval"):
        Engine().tick(game, 1)
    assert pickle.dumps(game) == before


def test_zero_eta_job_resolves_at_start_without_retroactive_wear():
    game = repairable_inertia()
    job = enqueue_repair(game)
    game.jobs.jobs[job.internal_id].eta_s = 0.0
    before = game.ship.physical_transit.motion
    Engine().tick(game, 1)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.motion.beta == before.beta
    assert game.ship.physical_transit.motion.distance_m > before.distance_m


def test_repair_completion_and_later_coast_share_one_atomic_tick():
    game = repairable_inertia()
    job = enqueue_repair(game)
    before = game.ship.physical_transit.motion
    fuel = game.ship.antimatter_capsules
    Engine().tick(game, job.eta_s + 2)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.motion.galactic_s == pytest.approx(
        before.galactic_s + job.eta_s + 2)
    assert game.ship.physical_transit.motion.beta == before.beta
    assert game.ship.antimatter_capsules == fuel
    assert len([event for event in game.events.recent
                if event.type == EventType.JOB_COMPLETED]) == 1


def test_safe_subdivision_matches_single_tick_with_repair_completion():
    game = repairable_inertia()
    job = enqueue_repair(game)
    whole = deepcopy(game)
    Engine().tick(whole, job.eta_s)
    Engine().tick(game, job.eta_s / 2)
    remaining = game.jobs.jobs[job.internal_id].eta_s
    Engine().tick(game, remaining)
    assert game.jobs.jobs[job.internal_id].status == whole.jobs.jobs[job.internal_id].status
    assert game.ship.physical_transit.motion.beta == whole.ship.physical_transit.motion.beta
    assert game.ship.physical_transit.motion.distance_m == pytest.approx(
        whole.ship.physical_transit.motion.distance_m)
    assert game.ship.systems["engines"].health == pytest.approx(
        whole.ship.systems["engines"].health)
    assert game.ship.drones["D1"].battery == pytest.approx(whole.ship.drones["D1"].battery)


def test_save_load_before_during_and_after_real_repair():
    game = repairable_inertia()
    job = enqueue_repair(game)
    waiting = save_and_load(game)
    assert waiting.jobs.jobs[job.internal_id].status == JobStatus.QUEUED
    Engine().tick(waiting, 3)
    midway = save_and_load(waiting)
    assert midway.jobs.jobs[job.internal_id].status == JobStatus.RUNNING
    remaining = midway.jobs.jobs[job.internal_id].eta_s
    Engine().tick(midway, remaining - .5)
    almost = save_and_load(midway)
    assert almost.jobs.jobs[job.internal_id].eta_s == pytest.approx(.5)
    Engine().tick(almost, almost.jobs.jobs[job.internal_id].eta_s)
    completed = save_and_load(almost)
    assert completed.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert completed.ship.physical_transit.inertial_continuation is not None
    assert len([event for event in completed.events.recent
                if event.type == EventType.JOB_COMPLETED]) == 1


def test_node_actions_stay_blocked_while_repair_remains_available():
    game = repairable_inertia()
    motion = game.ship.physical_transit.motion
    for action in (Dock(game.world.current_node_id), Scan()):
        events = Engine().apply_action(game, action)
        assert len(events) == 1 and events[0].type == EventType.BOOT_BLOCKED
        assert game.ship.physical_transit.motion == motion
    assert enqueue_repair(game).status == JobStatus.QUEUED


def test_real_repair_can_finish_beyond_original_destination():
    game = repairable_inertia()
    game.ship.systems["engines"].base_decay_per_s = 0
    load = Engine()._compute_load_kw(game)
    game.ship.power.p_gen_base_kw = load
    game.ship.power.p_gen_kw = load
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh / 2
    route_m = light_years_to_metres(distance_between_nodes_ly(
        game.world, game.ship.transit_from, "NOMINAL_B"))
    motion = game.ship.physical_transit.motion
    to_b = (route_m - motion.distance_m) / (LIGHT_SPEED_M_S * motion.beta)
    assert to_b > 0
    Engine().tick(game, to_b + 1)
    assert game.ship.physical_transit.motion.distance_m > route_m
    game = save_and_load(game)
    job = enqueue_repair(game)
    start = game.ship.physical_transit.motion
    Engine().tick(game, job.eta_s)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert game.ship.physical_transit.motion.beta == start.beta
    assert game.ship.physical_transit.motion.distance_m > start.distance_m > route_m
    assert game.world.current_node_id != "NOMINAL_B"
    saved = save_and_load(game)
    assert saved.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert saved.ship.physical_transit.motion.distance_m > route_m
