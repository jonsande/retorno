"""Productive causal boundaries in public physical navigation."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.actions import Boot, SystemOn, Travel
from retorno.core.communications import prepare_radio_opportunity
from retorno.core.engine import Engine
from retorno.core.nav_electricity import battery_rate_kwh_per_proper_s, capture_power_snapshot
from retorno.core.nav_physics import LIGHT_YEAR_M, proper_time_in_segment
from retorno.model.events import EventType
from retorno.model.jobs import Job, JobStatus, JobType, TargetRef
from retorno.model.systems import SystemState
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from tests.test_nav_engine_inertial import nominal_cut
from tests.test_nav_engine_wear_cut import _critical_nominal
from tests.test_nav_public_physical import public_game


def departed(*, distance_ly=.11):
    game = public_game(distance_ly)
    engine = Engine()
    assert any(e.type == EventType.TRAVEL_STARTED
               for e in engine.apply_action(game, Travel("NOMINAL_B")))
    return game, GameLoop(engine, game)


def test_battery_full_then_further_physical_motion():
    game, loop = departed()
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh - .01
    first = loop.engine.next_physical_step(game, 1000)
    assert 0 < first < 1000
    loop.advance_interval(1000)
    assert game.ship.power.e_batt_kwh == game.ship.power.e_batt_max_kwh
    assert game.clock.t == pytest.approx(1000)
    assert game.ship.physical_transit.motion.distance_m > 0


def test_variable_power_quality_uses_ship_time():
    game, loop = departed()
    game.ship.power.p_gen_base_kw = 0.1
    game.ship.power.e_batt_kwh = 2.0
    initial = game.ship.power.power_quality
    loop.advance_interval(1000)
    assert game.ship.power.power_quality != initial
    assert game.ship.power.e_batt_kwh < 2.0
    assert game.clock.ship_elapsed_s < game.clock.t


def test_discharge_quality_transition_reports_legitimate_capacity_loss():
    game, loop = departed()
    game.ship.power.p_gen_base_kw = 2.0
    game.ship.power.e_batt_kwh = 1.0
    with pytest.raises(NavigationAdvanceBlocked, match="propulsion capacity") as blocked:
        loop.advance_interval(20000)
    assert 0 < blocked.value.elapsed_s < 20000
    assert game.clock.t == pytest.approx(blocked.value.elapsed_s)
    assert game.ship.physical_transit is not None
    assert game.ship.power.e_batt_kwh < 1.0


def test_hibernation_labels_propulsion_loss_as_emergency():
    game, loop = departed()
    game.ship.power.p_gen_base_kw = 2.0
    game.ship.power.e_batt_kwh = 1.0
    result = repl._execute_hibernate(loop, .001)
    loop.stop()
    assert result.woke_early
    assert result.wake_reason == "emergency:Physical propulsion capacity is unavailable"
    assert 0 < result.actual_years < .001


def test_battery_full_and_phase_end_at_same_instant():
    game, loop = departed(distance_ly=1e6 / LIGHT_YEAR_M)
    segment = game.ship.physical_transit.active_segment
    proper = proper_time_in_segment(segment, segment.duration_galactic_s)
    snapshot = capture_power_snapshot(game, loop.engine._compute_p_gen(game),
                                      loop.engine._compute_load_kw(game))
    game.ship.power.e_batt_kwh = (game.ship.power.e_batt_max_kwh
                                  - battery_rate_kwh_per_proper_s(snapshot) * proper)
    fuel = game.ship.antimatter_capsules
    loop.advance_interval(segment.duration_galactic_s)
    assert game.ship.physical_transit.nominal_plan.phase_index == 1
    assert game.ship.power.e_batt_kwh == game.ship.power.e_batt_max_kwh
    assert game.ship.antimatter_capsules == fuel


def test_system_health_transition_and_radiation_profile():
    game, loop = departed()
    system = game.ship.systems["power_core"]
    system.health = Balance.SYSTEM_HEALTH_LIMITED + .001
    system.base_decay_per_s = .00001
    origin = game.world.space.nodes["PUBLIC_A"]
    destination = game.world.space.nodes["NOMINAL_B"]
    origin.radiation_rad_per_s = .001
    destination.radiation_rad_per_s = .1
    initial_hull = game.ship.hull_integrity
    events = loop.advance_interval(1000)
    assert system is not game.ship.systems["power_core"]
    assert game.ship.systems["power_core"].state in {SystemState.LIMITED, SystemState.DAMAGED,
                                                    SystemState.CRITICAL, SystemState.OFFLINE}
    assert any(e.type == EventType.SYSTEM_STATE_CHANGED and e.source.id == "power_core" for e in events)
    assert game.ship.hull_integrity < initial_hull
    assert origin.radiation_rad_per_s < game.ship.radiation_env_rad_per_s < destination.radiation_rad_per_s


def test_docked_drone_charges_during_physical_travel():
    game, loop = departed()
    donor = create_initial_state_sandbox(seed=3)
    game.ship.drones = donor.ship.drones
    drone = next(iter(game.ship.drones.values()))
    loop.apply_action(SystemOn("drone_bay"))
    drone.battery = .2
    loop.advance_interval(1000)
    assert game.ship.drones[drone.drone_id].battery > .2
    assert game.ship.physical_transit is not None


def test_compatible_job_completes_once_during_travel(monkeypatch):
    monkeypatch.setattr(Balance, "REPAIR_JOB_FAIL_P_BASE", 0.0)
    game, loop = departed()
    system = game.ship.systems["sensors"]
    system.health = .8
    job = Job("J99", JobType.SELFTEST_REPAIR, JobStatus.RUNNING, 5.0,
              target=TargetRef("ship_system", "sensors"),
              params={"repair_amount": .05, "repair_scrap": 0})
    game.jobs.jobs[job.internal_id] = job
    game.jobs.active_job_ids.append(job.internal_id)
    events = loop.advance_interval(10)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED
    assert sum(e.type == EventType.JOB_COMPLETED for e in events) == 1
    assert game.ship.systems["sensors"].health > .8


def test_narrative_evaluation_and_operational_radio_do_not_block():
    game, loop = departed()
    game.world.lore_placements.next_non_forced_eval_t = 5.0
    loop.apply_action(SystemOn("comms"))
    loop.apply_action(Boot("radiod"))
    prepare_radio_opportunity(game, "test:public-motion", "captured_signal",
                              {"en": "Test transmission"}, node_id="PUBLIC_A",
                              trigger="passive_listen")
    loop.advance_interval(10)
    assert game.clock.t == pytest.approx(10)
    assert game.world.lore_placements.next_non_forced_eval_t > 5
    assert game.world.radio_opportunities["test:public-motion"].status == "received"


def test_public_advance_reaches_preventive_braking_without_exact_cut():
    game, _ = _critical_nominal()
    loop = GameLoop(Engine(), game)
    loop.advance_interval(5)
    assert game.ship.physical_transit.safety_braking
    assert game.ship.physical_transit.nominal_plan.invalidated
    assert game.ship.systems["engines"].health < .35


def test_hibernation_wakes_on_real_critical_health_transition():
    game, loop = departed()
    support = game.ship.systems["life_support"]
    support.health = .351
    support.state = SystemState.DAMAGED
    support.base_decay_per_s = .00001
    result = repl._execute_hibernate(loop, .001)
    loop.stop()
    assert result.woke_early
    assert result.wake_reason == "critical_system:life_support:critical"
    assert 0 < result.actual_years < .001
    assert game.ship.systems["life_support"].state == SystemState.CRITICAL


def test_hibernation_wakes_at_physical_radiation_crossing():
    game, loop = departed()
    game.world.space.nodes["NOMINAL_B"].radiation_rad_per_s = .004
    result = repl._execute_hibernate(loop, 10.0)
    loop.stop()
    assert result.woke_early
    assert result.wake_reason == "env_radiation_threshold:0.0030"
    assert 0 < result.actual_years < 10
    assert game.ship.radiation_env_rad_per_s == pytest.approx(.003)
    assert game.ship.physical_transit is not None


def test_inertial_coast_keeps_stored_drone_and_advances():
    game = nominal_cut()
    game.ship.drones = create_initial_state_sandbox(seed=3).ship.drones
    start_distance = game.ship.physical_transit.motion.distance_m
    GameLoop(Engine(), game).advance_interval(1000)
    assert game.ship.physical_transit.motion.distance_m > start_distance
    assert game.ship.physical_transit.intent == "coast"
    assert game.ship.drones


def test_genuine_execution_failure_is_atomic():
    game, loop = departed()
    before = pickle.dumps(game)
    with patch("retorno.core.engine.run_lore_scheduler_tick", side_effect=RuntimeError("test defect")):
        with pytest.raises(RuntimeError, match="test defect"):
            loop.advance_interval(10)
    assert pickle.dumps(game) == before


def test_step_and_advance_interval_share_causal_result():
    first, _ = departed()
    first.ship.power.e_batt_kwh = first.ship.power.e_batt_max_kwh - .01
    second = deepcopy(first)
    GameLoop(Engine(), first).step(1000)
    GameLoop(Engine(), second).advance_interval(1000)
    assert first.ship.physical_transit == second.ship.physical_transit
    assert first.ship.power == second.ship.power
    assert first.clock.t == second.clock.t
    assert first.meta.rng_counter == second.meta.rng_counter
