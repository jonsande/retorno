"""The first productive physical interval uses Engine and the real ship state."""
from copy import deepcopy
import math
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.actions import Diag, PowerPlan, Repair, Status, Travel
from retorno.core.engine import Engine
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, MotionState, accelerate_to,
                                       brake_to_stop, coast_for,
                                       metres_to_light_years, sample_segment)
from retorno.core.nav_radiation import (RadiationProfile, integrate_segment_radiation,
                                        integrated_system_wear)
from retorno.core.nav_state import PhysicalTransitState
from retorno.core.temporal import biological_time_interval
from retorno.runtime.loop import GameLoop
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.jobs import Job, JobStatus, JobType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode
from retorno.ui_textual import presenter


def physical_game():
    game = create_initial_state_sandbox(seed=341)
    game.ship.drones.clear()
    game.ship.docked_node_id = None
    game.ship.systems["power_core"].state = SystemState.NOMINAL
    game.ship.systems["energy_distribution"].state = SystemState.NOMINAL
    game.ship.power.p_gen_base_kw = 12.0
    game.ship.power.p_gen_kw = 12.0
    game.ship.power.e_batt_kwh = 3.0
    game.ship.power.power_quality = 1.0
    game.world.lore_placements.next_non_forced_eval_t = 2000.0
    origin = game.world.space.nodes[game.world.current_node_id]
    origin.radiation_rad_per_s = .0001
    destination_m = LIGHT_SPEED_M_S * .5 * 500
    destination_ly = metres_to_light_years(destination_m)
    game.world.space.nodes["COAST_DEST"] = SpaceNode(
        "COAST_DEST", "Coast destination", "station",
        radiation_rad_per_s=.0002, x_ly=origin.x_ly + destination_ly,
        y_ly=origin.y_ly, z_ly=origin.z_ly,
    )
    segment = coast_for(MotionState(0, 0, .5, 0), 1000)
    game.ship.transit_from = origin.node_id
    game.ship.physical_transit = PhysicalTransitState(segment, 0, "COAST_DEST", "coast")
    return game, segment, destination_m


def test_engine_coast_integrates_real_ship_and_overshoots():
    game, segment, destination_m = physical_game()
    initial_health = game.ship.systems["life_support"].health
    life_support = game.ship.systems["life_support"]
    initial_fuel = game.ship.antimatter_capsules
    exposure = integrate_segment_radiation(
        RadiationProfile(0, destination_m, .0001, .0002), segment, 0, 1000,
        game.ship.hull_integrity,
    )
    before_rng = game.meta.rng_counter
    events = Engine().tick(game, 1000)
    assert game.ship.physical_transit.motion == sample_segment(segment, 1000)
    assert game.ship.physical_transit.motion.distance_m > destination_m
    assert game.ship.physical_transit.motion.beta == .5
    assert game.clock.t == 1000
    assert game.clock.ship_elapsed_s == pytest.approx(1000 * math.sqrt(.75))
    assert game.clock.bio_elapsed_s == pytest.approx(game.clock.ship_elapsed_s)
    assert game.ship.power.e_batt_kwh > 3.0
    assert game.ship.systems["life_support"].health < initial_health
    expected_wear = integrated_system_wear(
        life_support, exposure, exposure.proper_s, in_transit=True, op_mode="NORMAL")
    assert game.ship.systems["life_support"].health == pytest.approx(initial_health - expected_wear)
    assert game.ship.hull_integrity == pytest.approx(exposure.hull_end)
    assert game.ship.radiation_env_rad_per_s == pytest.approx(.0002)
    assert game.ship.antimatter_capsules == initial_fuel
    assert game.meta.rng_counter == before_rng
    assert not any(event.type == EventType.ARRIVED for event in events)
    assert game.ship.physical_transit.elapsed_galactic_s == 1000
    assert game.world.current_node_id != "COAST_DEST"


def test_coast_partition_and_segment_end_are_consistent():
    whole, _, _ = physical_game()
    split = deepcopy(whole)
    engine = Engine()
    events_whole = engine.tick(whole, 1000)
    events_first = engine.tick(split, 300)
    events_second = engine.tick(split, 700)
    assert split.ship.physical_transit.motion == whole.ship.physical_transit.motion
    assert split.clock.t == whole.clock.t
    assert split.clock.ship_elapsed_s == whole.clock.ship_elapsed_s
    assert split.ship.power.e_batt_kwh == pytest.approx(whole.ship.power.e_batt_kwh)
    assert split.ship.hull_integrity == pytest.approx(whole.ship.hull_integrity, abs=1e-14)
    for key in whole.ship.systems:
        assert split.ship.systems[key].health == pytest.approx(whole.ship.systems[key].health, abs=1e-14)
    assert [event.type for event in events_first + events_second] == [event.type for event in events_whole]
    with pytest.raises(RuntimeError, match="beyond this segment"):
        engine.tick(split, 1)


def test_hibernation_uses_ship_proper_time_for_biological_age():
    game, _, _ = physical_game()
    game.ship.is_hibernating = True
    Engine().tick(game, 200)
    assert game.clock.bio_elapsed_s == pytest.approx(
        biological_time_interval(game.clock.ship_elapsed_s, True))


def test_partial_segment_with_nonzero_absolute_clocks():
    game, _, _ = physical_game()
    segment = coast_for(MotionState(500, 1000, .5, 400), 1000)
    game.clock.t = 500
    game.clock.ship_elapsed_s = 400
    game.ship.physical_transit = PhysicalTransitState(segment, 0, "COAST_DEST", "coast")
    Engine().tick(game, 100)
    assert game.ship.physical_transit.motion == sample_segment(segment, 100)
    assert game.clock.t == 600
    assert game.clock.ship_elapsed_s == pytest.approx(400 + 100 * math.sqrt(.75))


def test_rejections_leave_state_untouched():
    game, _, _ = physical_game()
    game.ship.drones["probe"] = next(iter(create_initial_state_sandbox(seed=341).ship.drones.values()))
    before = deepcopy(game)
    with pytest.raises(RuntimeError, match="drones"):
        Engine().tick(game, 100)
    assert game == before
    game.ship.drones.clear()
    game.ship.power.p_gen_base_kw = 0
    before = deepcopy(game)
    with pytest.raises(RuntimeError, match="electrical"):
        Engine().tick(game, 100)
    assert game == before


@pytest.mark.parametrize("intent", ["accelerate", "brake"])
def test_propulsive_segments_are_rejected_without_mutation(intent):
    game, _, _ = physical_game()
    start = MotionState(0, 0, .5, 0)
    segment = (accelerate_to(start, .6, 9.81) if intent == "accelerate"
               else brake_to_stop(start, 9.81))
    game.ship.physical_transit = PhysicalTransitState(
        segment, 0, "COAST_DEST", intent, braking_started=intent == "brake")
    before = deepcopy(game)
    with pytest.raises(RuntimeError, match="propulsion"):
        Engine().tick(game, 100)
    assert game == before


def test_jobs_and_narrative_cut_are_rejected_before_mutation():
    game, _, _ = physical_game()
    game.jobs.jobs["J1"] = Job("J1", JobType.REPAIR_SYSTEM, JobStatus.QUEUED, 10)
    game.jobs.active_job_ids.append("J1")
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="jobs"):
        Engine().tick(game, 100)
    assert pickle.dumps(game) == before
    game.jobs.jobs.clear()
    game.jobs.active_job_ids.clear()
    game.world.lore_placements.next_non_forced_eval_t = 50
    before = deepcopy(game)
    with pytest.raises(RuntimeError, match="narrative"):
        Engine().tick(game, 100)
    assert game == before


def test_internal_electrical_radiation_and_health_cuts_are_rejected():
    engine = Engine()
    battery, _, _ = physical_game()
    battery.ship.power.e_batt_kwh = battery.ship.power.e_batt_max_kwh - .001
    before = deepcopy(battery)
    with pytest.raises(RuntimeError, match="unresolved causal boundary"):
        engine.tick(battery, 1000)
    assert battery == before

    radiation, _, _ = physical_game()
    radiation.world.space.nodes["COAST_DEST"].radiation_rad_per_s = .002
    before = deepcopy(radiation)
    with pytest.raises(RuntimeError, match="unresolved causal boundary"):
        engine.tick(radiation, 1000)
    assert radiation == before

    health, _, _ = physical_game()
    core = health.ship.systems["power_core"]
    core.health = Balance.SYSTEM_HEALTH_CRITICAL + 1e-8
    core.state = SystemState.DAMAGED
    before = deepcopy(health)
    with pytest.raises(RuntimeError, match="unresolved causal boundary"):
        engine.tick(health, 1000)
    assert health == before


def test_deferred_radiation_and_staged_failure_are_atomic():
    game, _, _ = physical_game()
    before = deepcopy(game)
    from retorno.core.nav_boundaries import TemporalLimit
    deferred = TemporalLimit("internal_high", "proper", None,
                             validity="numerical_isolation_unresolved")
    with patch("retorno.core.engine.radiation_limits", return_value=(deferred,)):
        with pytest.raises(RuntimeError, match="unresolved causal boundary"):
            Engine().tick(game, 100)
    assert game == before
    with patch.object(Engine, "_integrate_power_interval", side_effect=RuntimeError("staged failure")):
        with pytest.raises(RuntimeError, match="staged failure"):
            Engine().tick(game, 100)
    assert game == before


def test_physical_state_round_trips_without_new_save_format():
    game, _, _ = physical_game()
    Engine().tick(game, 200)
    with TemporaryDirectory() as folder:
        path = Path(folder) / "slot.sav"
        save_single_slot(game, path)
        loaded = load_single_slot(path)
        assert loaded is not None
        assert loaded.state.ship.physical_transit == game.ship.physical_transit


@pytest.mark.parametrize("command", ["nav COAST_DEST", "route solve COAST_DEST"])
def test_public_navigation_actions_are_blocked_during_physical_transit(command):
    game, _, _ = physical_game()
    loop = GameLoop(Engine(), game)
    physical = game.ship.physical_transit
    before_fuel = game.ship.antimatter_capsules
    before_scrap = game.ship.cargo_scrap
    before_jobs = pickle.dumps(game.jobs)
    before_links = deepcopy(game.world.known_links)
    before_ranges = deepcopy(game.world.fine_ranges_km)
    action = parse_command(command)
    events = loop.apply_action(action)
    assert len(events) == 1
    assert events[0].type == EventType.BOOT_BLOCKED
    assert events[0].data["reason"] == "physical_in_transit"
    assert game.ship.physical_transit is physical
    assert game.ship.in_transit is False
    assert game.ship.antimatter_capsules == before_fuel
    assert game.ship.cargo_scrap == before_scrap
    assert pickle.dumps(game.jobs) == before_jobs
    assert game.world.known_links == before_links
    assert game.world.fine_ranges_km == before_ranges
    assert game.clock.t == 0
    assert game.events.recent[-1] is events[0]
    assert repl._nav_departure_blocked(game)
    game.os.locale = Locale.EN
    english = " ".join(presenter.format_event_lines(game, [("cmd", events[0])]))
    game.os.locale = Locale.ES
    spanish = " ".join(presenter.format_event_lines(game, [("cmd", events[0])]))
    assert "already moving" in english
    assert "ya está en movimiento" in spanish
    assert "until_arrival" not in english + spanish


def test_diagnostics_and_survival_actions_are_not_globally_blocked():
    game, _, _ = physical_game()
    engine = Engine()
    assert engine.apply_action(game, Status()) == []
    assert engine.apply_action(game, Diag("life_support")) == []
    repair = engine.apply_action(game, Repair("missing_drone", "life_support"))
    assert repair and repair[0].data["reason"] == "drone_missing"
    assert engine.apply_action(game, PowerPlan("normal")) == []
    assert game.ship.physical_transit is not None


def test_real_loop_and_presenter_keep_state_owner_references_after_tick():
    game, segment, _ = physical_game()
    loop = GameLoop(Engine(), game)
    root = loop.get_state_snapshot()
    owners = {name: getattr(root, name) for name in
              ("meta", "clock", "world", "ship", "os", "jobs", "events")}
    power_before = root.ship.power.e_batt_kwh
    with loop.with_lock() as locked:
        assert locked is root
        assert presenter.build_header(locked)
    loop.step(200)
    assert loop.get_state_snapshot() is root
    for name, reference in owners.items():
        assert getattr(root, name) is reference
    assert owners["clock"].t == 200
    assert owners["ship"].physical_transit.motion == sample_segment(segment, 200)
    assert owners["ship"].power.e_batt_kwh > power_before
    assert presenter.build_power_lines(root) == presenter.build_power_lines(loop.state)
    with loop.with_lock() as locked:
        assert locked is root
        assert locked.ship is owners["ship"]
        assert locked.world is owners["world"]


def test_transaction_failures_preserve_owner_identities_and_values():
    game, _, _ = physical_game()
    engine = Engine()
    owners = {name: getattr(game, name) for name in
              ("meta", "clock", "world", "ship", "os", "jobs", "events")}
    before = deepcopy(game)
    game.ship.power.p_gen_base_kw = 0
    invalid = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="electrical"):
        engine.tick(game, 100)
    assert pickle.dumps(game) == invalid
    game.ship.power.p_gen_base_kw = 12
    assert game == before
    with patch.object(Engine, "_update_alerts", side_effect=RuntimeError("late failure")):
        with pytest.raises(RuntimeError, match="late failure"):
            engine.tick(game, 100)
    assert game == before
    for name, reference in owners.items():
        assert getattr(game, name) is reference


def test_historical_travel_still_starts_without_physical_transit():
    game = create_initial_state_sandbox(seed=342)
    game.ship.docked_node_id = None
    origin = game.world.space.nodes[game.world.current_node_id]
    game.world.space.nodes["HIST_DEST"] = SpaceNode(
        "HIST_DEST", "Historical destination", "station",
        x_ly=origin.x_ly + 3, y_ly=origin.y_ly, z_ly=origin.z_ly)
    from retorno.model.world import add_known_link
    game.world.known_nodes.add("HIST_DEST")
    add_known_link(game.world, origin.node_id, "HIST_DEST")
    events = Engine().apply_action(game, Travel("HIST_DEST", no_cruise=True))
    assert any(event.type == EventType.TRAVEL_STARTED for event in events)
    assert game.ship.in_transit
    assert game.ship.physical_transit is None
