"""Conditional time boundaries remain pure and disconnected from navigation."""
from dataclasses import FrozenInstanceError, asdict
import math

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import (
    ordinary_wear_rate, predict_engine_health_limit, propulsion_job_limits,
    thrust_available,
)
from retorno.model.jobs import Job, JobManagerState, JobStatus, JobType, TargetRef
from retorno.model.systems import SystemState


def state():
    game = create_initial_state_sandbox(seed=301)
    game.ship.drones.clear()
    return game


@pytest.mark.parametrize("system_id", ["engines", "power_core", "energy_distribution", "sensors"])
@pytest.mark.parametrize("mode,moving", [("CRUISE", True), ("NORMAL", True), ("CRUISE", False)])
@pytest.mark.parametrize("quality,rad,brown", [(1.0, 0.0, False), (0.4, 0.01, False), (0.3, 1.0, True)])
def test_wear_rate_matches_previous_formula_and_productive_application(system_id, mode, moving, quality, rad, brown):
    game = state()
    system = game.ship.systems[system_id]
    system.health = 0.9
    system.base_decay_per_s = 0.02
    system.k_power, system.k_rad = 0.3, 0.4
    game.ship.in_transit, game.ship.op_mode = moving, mode
    norm = min(1.0, max(0.0, rad / Balance.R_REF))
    multiplier = Balance.TRANSIT_WEAR_MULT_NORMAL if moving and mode != "CRUISE" else 1.0
    factor = 1 + 0.3 * (1 - quality) + 0.4 * norm
    if brown and system_id == "energy_distribution":
        factor *= Balance.BROWNOUT_DEGRADE_MULT_DISTRIBUTION
    if brown and system_id == "power_core":
        factor *= Balance.BROWNOUT_DEGRADE_MULT_POWER_CORE
    expected = 0.02 * factor * multiplier
    rate = ordinary_wear_rate(system, quality, brown, rad, in_transit=moving, op_mode=mode)
    assert rate == pytest.approx(expected)
    before = asdict(system)
    for other in game.ship.systems.values():
        if other is not system:
            other.base_decay_per_s = 0.0
    assert asdict(system) == before
    Engine()._apply_degradation(game, 3.0, quality, brown, rad)
    assert system.health == pytest.approx(max(0.0, 0.9 - 3 * expected))


def test_wear_clamp_zero_and_god_mode():
    game = state()
    engine = game.ship.systems["engines"]
    engine.health, engine.base_decay_per_s = 0.1, 2.0
    assert ordinary_wear_rate(engine, 1.0, False, 0.0, in_transit=False, op_mode="NORMAL", god_active=True) == 0
    game.os.debug_enabled = game.os.debug_god_enabled = True
    Engine()._apply_degradation(game, 10, 1.0, False, 0.0)
    assert engine.health == 0.1
    game.os.debug_god_enabled = False
    Engine()._apply_degradation(game, 10, 1.0, False, 0.0)
    assert engine.health == 0
    engine.base_decay_per_s = 0
    assert ordinary_wear_rate(engine, 1.0, False, 0.0, in_transit=False, op_mode="NORMAL") == 0


@pytest.mark.parametrize("health,expected", [(0.9, True), (0.85, True), (0.6, True),
                                               (0.35, True), (0.349, False), (0.0, False)])
def test_thrust_bands_and_exact_threshold(health, expected):
    game = state()
    game.ship.systems["engines"].health = health
    assert thrust_available(game.ship) is expected
    if health == 0.35:
        assert game.ship.engine_operating_state() == SystemState.DAMAGED


def test_isolation_and_target_are_not_thrust():
    game = state()
    engine = game.ship.systems["engines"]
    game.ship.target_cruise_speed = 0.8
    assert thrust_available(game.ship)
    assert game.ship.effective_cruise_speed() == 0
    engine.forced_offline = True
    assert not thrust_available(game.ship)
    engine.forced_offline = False
    engine.state = SystemState.OFFLINE  # stale presentation; operating state uses health/isolation
    assert thrust_available(game.ship)
    engine.health = math.nan
    assert not thrust_available(game.ship)


def test_health_prediction_and_partition_equivalence():
    game = state()
    engine = game.ship.systems["engines"]
    engine.health = 0.85
    rate = 0.01
    before = asdict(game.ship)
    limit = predict_engine_health_limit(game.ship, rate)
    assert limit.domain == "proper" and limit.time_s == pytest.approx(50.0)
    assert limit.validity == "constant_wear_conditions"
    assert asdict(game.ship) == before
    left = engine.health - rate * limit.time_s
    split = engine.health - rate * 20 - rate * 30
    assert left == pytest.approx(Balance.SYSTEM_HEALTH_CRITICAL)
    assert split == pytest.approx(left)
    with pytest.raises(FrozenInstanceError):
        limit.time_s = 2


def test_health_threshold_equality_and_absent_crossing():
    game = state()
    engine = game.ship.systems["engines"]
    engine.health = Balance.SYSTEM_HEALTH_CRITICAL
    assert thrust_available(game.ship)
    at = predict_engine_health_limit(game.ship, 0.01)
    assert at.time_s == 0 and at.validity == "at_threshold_not_yet_critical"
    engine.health = 0.3
    assert predict_engine_health_limit(game.ship, 0.01).validity == "already_below_threshold"
    engine.health = 0.8
    assert predict_engine_health_limit(game.ship, 0).time_s is None
    assert predict_engine_health_limit(game.ship, 0.01, god_active=True).validity == "god_mode_no_wear"
    engine.forced_offline = True
    assert not thrust_available(game.ship)
    assert predict_engine_health_limit(game.ship, 0.01).time_s == pytest.approx(45.0)


@pytest.mark.parametrize("bad", [-1, math.nan, math.inf, -math.inf])
def test_invalid_prediction_and_rate_inputs(bad):
    game = state()
    with pytest.raises(ValueError):
        predict_engine_health_limit(game.ship, bad)
    with pytest.raises(ValueError):
        ordinary_wear_rate(game.ship.systems["engines"], bad, False, 0,
                           in_transit=True, op_mode="CRUISE")


def test_invalid_engine_health_range():
    game = state()
    engine = game.ship.systems["engines"]
    for bad in (-0.1, math.nan, math.inf, engine.health_max_effective + 0.1):
        engine.health = bad
        with pytest.raises(ValueError):
            predict_engine_health_limit(game.ship, 0.01)


def _job(job_id, kind, status, eta, target=None, *, draw=0, waiting=False, module=None):
    params = {"awaiting_auto_move_confirmation": waiting}
    if module:
        params["module_id"] = module
    return Job(job_id, kind, status, eta, target=TargetRef("ship_system", target) if target else None,
               params=params, power_draw_kw=draw)


def test_job_limits_running_queued_blocked_and_simultaneous():
    manager = JobManagerState()
    entries = [
        _job("J1", JobType.REPAIR_SYSTEM, JobStatus.RUNNING, 30, "engines"),
        _job("J2", JobType.REPAIR_SYSTEM, JobStatus.RUNNING, 30, "power_core"),
        _job("J3", JobType.REPAIR_SYSTEM, JobStatus.QUEUED, 5, "engines"),
        _job("J4", JobType.REPAIR_SYSTEM, JobStatus.RUNNING, 3, "engines", waiting=True),
        _job("J5", JobType.CARGO_AUDIT, JobStatus.RUNNING, 2),
        _job("J6", JobType.CARGO_AUDIT, JobStatus.RUNNING, 4, draw=2),
        _job("J7", JobType.INSTALL_MODULE, JobStatus.RUNNING, 6, module="engine_speed_upgrade_01"),
    ]
    manager.jobs = {job.job_id: job for job in entries}
    manager.active_job_ids = list(manager.jobs)
    before = asdict(manager)
    limits = propulsion_job_limits(manager)
    assert [limit.job_id for limit in limits] == ["J1", "J2", "J3", "J4", "J6", "J7"]
    assert [limit.time_s for limit in limits] == [30, 30, 0, None, 4, 6]
    assert all(limit.domain == "galactic" for limit in limits)
    assert limits[2].kind == "job_activation"
    assert limits[2].uncertainty_reason == "scheduler_may_block_or_interrupt"
    assert limits[3].uncertainty_reason == "awaiting_player_confirmation"
    assert all(limit.uncertainty_reason for limit in limits)
    assert asdict(manager) == before


def test_no_job_limit_and_invalid_eta():
    manager = JobManagerState()
    assert propulsion_job_limits(manager) == ()
    job = _job("J1", JobType.REPAIR_SYSTEM, JobStatus.RUNNING, math.nan, "engines")
    manager.jobs[job.job_id] = job
    manager.active_job_ids.append(job.job_id)
    with pytest.raises(ValueError):
        propulsion_job_limits(manager)


@pytest.mark.parametrize("module", ["bus_stabilizer", "aux_battery_cell",
                                     "micro_reactor_patch", "engine_speed_upgrade_01"])
def test_relevant_module_install_and_uninstall_are_conditional_limits(module):
    manager = JobManagerState()
    entries = [
        _job("install", JobType.INSTALL_MODULE, JobStatus.RUNNING, 7, module=module),
        _job("uninstall", JobType.UNINSTALL_MODULE, JobStatus.RUNNING, 8, module=module),
    ]
    manager.jobs = {job.job_id: job for job in entries}
    manager.active_job_ids = list(manager.jobs)
    assert [limit.time_s for limit in propulsion_job_limits(manager)] == [7, 8]


def test_queued_activation_respects_owner_and_has_no_completion_eta():
    manager = JobManagerState()
    running = _job("running", JobType.REPAIR_SYSTEM, JobStatus.RUNNING, 9, "engines")
    running.owner_id = "DRONE_1"
    blocked = _job("blocked", JobType.REPAIR_SYSTEM, JobStatus.QUEUED, 2, "engines", draw=1)
    blocked.owner_id = "DRONE_1"
    free = _job("free", JobType.REPAIR_SYSTEM, JobStatus.QUEUED, 4, "power_core", draw=1)
    free.owner_id = "DRONE_2"
    manager.jobs = {job.job_id: job for job in (running, blocked, free)}
    manager.active_job_ids = list(manager.jobs)
    limits = propulsion_job_limits(manager)
    assert [limit.time_s for limit in limits] == [9, None, 0]
    assert limits[1].uncertainty_reason == "activation_blocked_by_running_job"
    assert limits[2].kind == "job_activation"
