"""Public interstellar navigation through the real action and time paths."""
from pathlib import Path
import pickle

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.actions import EngineSpeed, RouteSolve, SystemOn, Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.core.nav_physics import LIGHT_SPEED_M_S, LIGHT_YEAR_M
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.runtime.loop import GameLoop
from retorno.ui_textual import presenter
from tests.test_nav_engine_inertial import nominal_cut


def public_game(distance_ly: float = .11):
    # A controlled, quiet operational sector crossing. It is interstellar even
    # for very short distances because the endpoints lie in different sectors.
    game = create_initial_state_sandbox(seed=341)
    game.ship.drones.clear()
    game.ship.docked_node_id = None
    game.ship.systems["power_core"].state = SystemState.NOMINAL
    game.ship.systems["energy_distribution"].state = SystemState.NOMINAL
    game.ship.power.p_gen_base_kw = 12.0
    game.ship.power.p_gen_kw = 12.0
    game.ship.power.power_quality = 1.0
    game.world.lore_placements.next_non_forced_eval_t = 1e9
    game.world.space.nodes["NOMINAL_B"] = SpaceNode(
        "NOMINAL_B", "Nominal destination", "station", radiation_rad_per_s=.0002,
        x_ly=10 + distance_ly / 2, y_ly=0, z_ly=0)
    game.ship.power.e_batt_kwh = game.ship.power.e_batt_max_kwh
    for system in game.ship.systems.values():
        system.base_decay_per_s = 0.0
        system.k_rad = 0.0
        system.k_power = 0.0
    origin = SpaceNode("PUBLIC_A", "Public origin", "station",
                       radiation_rad_per_s=.0001,
                       x_ly=10 - distance_ly / 2, y_ly=0, z_ly=0)
    destination = game.world.space.nodes["NOMINAL_B"]
    destination.x_ly = 10 + distance_ly / 2
    destination.y_ly = destination.z_ly = 0
    game.world.space.nodes[origin.node_id] = origin
    game.world.current_node_id = game.ship.current_node_id = origin.node_id
    game.world.current_pos_ly = (origin.x_ly, 0, 0)
    game.world.known_nodes.update((origin.node_id, destination.node_id))
    assert add_known_link(game.world, origin.node_id, destination.node_id)
    return game


def test_public_route_quote_departure_payment_and_guards(capsys):
    game = public_game()
    engine = Engine()
    assert engine.apply_action(game, EngineSpeed(.1))[0].type == EventType.ENGINE_SPEED_SET
    before = pickle.dumps(game)
    quote = engine.estimate_travel_profile(game, "NOMINAL_B")
    cost = engine.estimate_travel_fuel(game, "NOMINAL_B")
    assert quote is not None and quote.has_cruise
    assert engine.estimate_travel_duration(game, "NOMINAL_B") == quote.total_galactic_s
    repl.render_nav_routes(game)
    lines, prompt = repl.nav_confirmation(game, Travel("NOMINAL_B"))
    assert "Peak beta" in capsys.readouterr().out
    assert any("Ship time" in line for line in lines) and prompt is not None
    assert pickle.dumps(game) == before
    reserve = game.ship.antimatter_capsules
    events = engine.apply_action(game, Travel("NOMINAL_B"))
    assert [event.type for event in events] == [EventType.TRAVEL_PROFILE_SET, EventType.TRAVEL_STARTED]
    assert game.ship.physical_transit is not None
    assert not game.ship.in_transit and game.ship.arrival_t == 0
    assert game.ship.physical_transit.nominal_plan.profile == quote
    assert game.ship.antimatter_capsules == pytest.approx(reserve - cost)
    assert engine.apply_action(game, Travel("NOMINAL_B"))[0].data["reason"] == "physical_in_transit"
    assert engine.apply_action(game, TravelAbort())[0].data["reason"] == "physical_in_transit"
    assert engine.apply_action(game, RouteSolve("NOMINAL_B"))[0].data["reason"] == "physical_in_transit"
    assert engine.apply_action(game, EngineSpeed(.2))[0].data["reason"] == "engine_speed_in_transit"
    assert engine.apply_action(game, SystemOn("comms"))[0].data.get("reason") != "physical_radio_unsupported"
    assert game.ship.antimatter_capsules == pytest.approx(reserve - cost)


@pytest.mark.parametrize("block", ["unknown", "route", "cap", "engines", "fuel", "dock"])
def test_public_rejection_is_spatially_and_economically_atomic(block):
    game = public_game()
    engine = Engine()
    if block == "unknown":
        game.world.known_nodes.remove("NOMINAL_B")
    elif block == "route":
        game.world.known_links["PUBLIC_A"].remove("NOMINAL_B")
    elif block == "cap":
        game.world.space.nodes["NOMINAL_B"].x_ly = 60.0
    elif block == "engines":
        game.ship.systems["engines"].forced_offline = True
    elif block == "fuel":
        game.ship.antimatter_capsules = 0.0
    else:
        game.ship.docked_node_id = "PUBLIC_A"
    old_pos = game.world.current_pos_ly
    old_fuel = game.ship.antimatter_capsules
    old_rng = game.meta.rng_seed
    event = engine.apply_action(game, Travel("NOMINAL_B"))[0]
    assert event.type == EventType.BOOT_BLOCKED
    assert game.ship.physical_transit is None
    assert game.world.current_pos_ly == old_pos
    assert game.ship.antimatter_capsules == old_fuel
    assert game.meta.rng_seed == old_rng


def test_public_preflight_accepts_docked_drones_and_variable_power():
    game = public_game(1e6 / LIGHT_YEAR_M)
    donor = create_initial_state_sandbox(seed=341)
    game.ship.drones = donor.ship.drones
    game.ship.power.p_gen_base_kw = game.ship.power.p_gen_kw = 3.2
    fuel = game.ship.antimatter_capsules
    events = Engine().apply_action(game, Travel("NOMINAL_B"))
    assert [event.type for event in events] == [EventType.TRAVEL_PROFILE_SET, EventType.TRAVEL_STARTED]
    assert game.ship.physical_transit is not None
    assert game.ship.drones
    assert game.ship.antimatter_capsules < fuel


@pytest.mark.parametrize("distance_ly, speed, cruise", [(.11, .1, True), (1e6 / LIGHT_YEAR_M, .5, False)])
def test_public_nominal_arrives_and_restores_mode(distance_ly, speed, cruise):
    game = public_game(distance_ly)
    engine = Engine()
    engine.apply_action(game, EngineSpeed(speed))
    quote = engine.estimate_travel_profile(game, "NOMINAL_B")
    assert quote is not None and quote.has_cruise == cruise
    start_fuel = game.ship.antimatter_capsules
    engine.apply_action(game, Travel("NOMINAL_B"))
    loop = GameLoop(engine, game)
    events = loop.advance_interval(quote.total_galactic_s, stop_at_arrival=True)
    assert [event.type for event in events].count(EventType.ARRIVED) == 1
    assert game.ship.physical_transit is None
    assert game.world.current_node_id == "NOMINAL_B"
    assert game.ship.antimatter_capsules == pytest.approx(start_fuel - engine.engine_fuel_cost(game, distance_ly, speed))
    assert game.ship.op_mode == "NORMAL"
    assert game.clock.t == pytest.approx(quote.total_galactic_s)
    assert game.clock.ship_elapsed_s == pytest.approx(quote.total_proper_s)
    assert engine.apply_action(game, EngineSpeed(.2))[0].type == EventType.ENGINE_SPEED_SET


@pytest.mark.parametrize("phase", ["rest", "accelerate", "cruise", "brake", "arrived"])
def test_public_save_load_preserves_paid_trajectory(tmp_path: Path, phase):
    game = public_game()
    engine = Engine()
    engine.apply_action(game, EngineSpeed(.1))
    if phase != "rest":
        engine.apply_action(game, Travel("NOMINAL_B"))
        nominal = game.ship.physical_transit.nominal_plan
        if phase == "accelerate":
            duration = nominal.segments[0].duration_galactic_s / 2
        elif phase == "cruise":
            duration = nominal.segments[0].duration_galactic_s + nominal.segments[1].duration_galactic_s / 2
        elif phase == "brake":
            duration = nominal.segments[-1].start.galactic_s + nominal.segments[-1].duration_galactic_s / 2
        else:
            duration = nominal.profile.total_galactic_s
        GameLoop(engine, game).advance_interval(duration)
    reserve = game.ship.antimatter_capsules
    path = tmp_path / "public.sav"
    save_single_slot(game, path)
    restored = load_single_slot(path).state
    assert restored.ship.antimatter_capsules == reserve
    assert restored.ship.physical_transit == game.ship.physical_transit
    if phase not in {"rest", "arrived"}:
        remaining = repl._remaining_arrival_s(restored)
        events = GameLoop(Engine(), restored).advance_interval(remaining, stop_at_arrival=True)
        assert any(event.type == EventType.ARRIVED for event in events)


def test_physical_status_is_localized_and_inertia_has_no_nominal_eta(capsys):
    game = public_game(1e6 / LIGHT_YEAR_M)
    Engine().apply_action(game, Travel("NOMINAL_B"))
    for locale in ("en", "es"):
        game.os.locale = type(game.os.locale)(locale)
        repl.render_status(game)
        output = capsys.readouterr().out
        assert ("acceleration" if locale == "en" else "aceleración") in output
        assert ("nominal ETA" if locale == "en" else "ETA nominal") in output
        header = presenter.build_header(game)
        assert "NOMINAL_B" in header
        assert ("acceleration" if locale == "en" else "aceleración") in header
    # A normal battery charging boundary no longer blocks physical time.
    game.ship.power.e_batt_kwh = 3.0
    loop = GameLoop(Engine(), game)
    duration = game.ship.physical_transit.nominal_plan.profile.total_galactic_s
    events = loop.advance_interval(duration)
    assert any(event.type == EventType.ARRIVED for event in events)
    assert game.clock.t == pytest.approx(duration)
    assert game.ship.physical_transit is None


def test_inertial_status_omits_arrival_eta_and_marks_overshoot():
    game = nominal_cut()
    physical = game.ship.physical_transit
    assert physical.pending_transition == "inertia"
    lines = repl.physical_transit_lines(game)
    assert any("inertial continuation" in line for line in lines)
    assert not any("ETA" in line for line in lines)
    assert repl._remaining_arrival_s(game) is None
    game.ship.systems["engines"].base_decay_per_s = 0.0
    Engine().tick(game, 1.0)
    motion = game.ship.physical_transit.motion
    route_m = Engine()._distance_between_nodes(game, game.ship.transit_from,
                                                physical.original_destination_id) * LIGHT_YEAR_M
    to_destination = (route_m - motion.distance_m) / (LIGHT_SPEED_M_S * motion.beta)
    Engine().tick(game, to_destination)
    Engine().tick(game, 10)
    lines = repl.physical_transit_lines(game)
    assert "destination overshot" in lines
    assert not any("ETA" in line for line in lines)


def test_public_hibernate_until_arrival_and_fixed_wait_after_stop():
    game = public_game(1e6 / LIGHT_YEAR_M)
    Engine().apply_action(game, Travel("NOMINAL_B"))
    loop = GameLoop(Engine(), game)
    remaining = repl._remaining_arrival_s(game)
    result = repl._execute_hibernate(loop, remaining / Balance.YEAR_S,
                                     until_arrival=True)
    assert not result.woke_early
    assert game.world.current_node_id == "NOMINAL_B"
    assert game.ship.physical_transit is None
    assert result.actual_years == pytest.approx(game.clock.t / Balance.YEAR_S)
    stopped = game.clock.t
    loop.advance_interval(300)
    assert game.clock.t == pytest.approx(stopped + 300)


def test_local_travel_remains_historical():
    game = public_game(1e6 / LIGHT_YEAR_M)
    # Move the destination into the origin's sector without changing its range.
    destination = game.world.space.nodes["NOMINAL_B"]
    origin = game.world.space.nodes["PUBLIC_A"]
    origin.x_ly = 9.0
    game.world.current_pos_ly = (9.0, 0, 0)
    destination.x_ly = origin.x_ly + 1e6 / LIGHT_YEAR_M
    assert Engine()._is_local_hop(game, "PUBLIC_A", "NOMINAL_B", 1e6 / LIGHT_YEAR_M)
    reserve = game.ship.antimatter_capsules
    Engine().apply_action(game, Travel("NOMINAL_B"))
    assert game.ship.in_transit and game.ship.physical_transit is None
    assert game.ship.antimatter_capsules == reserve
