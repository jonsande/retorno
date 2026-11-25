"""Reproducible ordinary sandbox journey through public navigation handlers.

Run with: ../retorno_venv/bin/python tests/nav_d2b1_public_walk.py
"""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.world import distance_between_nodes_ly
from retorno.runtime.loop import GameLoop


def run() -> None:
    state = create_initial_state_sandbox(seed=1)
    loop = GameLoop(Engine(), state)
    loop.set_auto_tick(False)

    def command(line: str):
        events = loop.apply_action(parse_command(line))
        print("COMMAND", line, [(event.type.value, event.data.get("reason"))
                                 for event in events], flush=True)
        return events

    def wait_jobs():
        while state.jobs.active_job_ids:
            due = min(state.jobs.jobs[key].eta_s for key in state.jobs.active_job_ids)
            events = loop.advance_interval(due)
            print("WAIT_JOBS", due, [event.type.value for event in events], flush=True)

    print("INITIAL", "seed", state.meta.rng_seed, "node", state.ship.current_node_id,
          "fuel", state.ship.antimatter_capsules, "battery_kwh", state.ship.power.e_batt_kwh,
          "generation_kw", state.ship.power.p_gen_base_kw, "drones", len(state.ship.drones),
          "engine_health", state.ship.systems["engines"].health,
          "hull", state.ship.hull_integrity,
          "lore_eval_seq", state.world.lore_placements.eval_seq, flush=True)
    command("dock ECHO_7")
    wait_jobs()
    with redirect_stdout(StringIO()) as output:
        repl._handle_uplink(state)
    print("COMMAND uplink", output.getvalue().strip().splitlines()[-2:], flush=True)
    with redirect_stdout(StringIO()) as output:
        repl.render_nav_routes(state)
    print("COMMAND nav map routes", output.getvalue().strip(), flush=True)
    routes = sorted((distance_between_nodes_ly(state.world, "ECHO_7", key), key)
                    for key in state.world.known_links["ECHO_7"])
    print("ROUTES", routes, flush=True)
    distance_ly, target = routes[0]
    command("undock")
    wait_jobs()
    command("engines speed 0.5")
    with redirect_stdout(StringIO()) as output:
        repl.render_nav_routes(state)
    print("COMMAND nav map routes after undock", output.getvalue().strip(), flush=True)
    initial_fuel = state.ship.antimatter_capsules
    departure = command("nav " + target)
    assert [event.type for event in departure] == [EventType.TRAVEL_PROFILE_SET,
                                                   EventType.TRAVEL_STARTED]
    paid = initial_fuel - state.ship.antimatter_capsules
    profile = state.ship.physical_transit.nominal_plan.profile
    print("DEPARTURE", "distance_ly", distance_ly, "target_beta", .5,
          "paid_capsules", paid, "nominal_galactic_years",
          profile.total_galactic_s / Balance.YEAR_S, "nominal_ship_years",
          profile.total_proper_s / Balance.YEAR_S, flush=True)
    first = repl._execute_hibernate(loop, 1.0)
    assert not first.woke_early and state.ship.physical_transit is not None
    print("COMMAND hibernate 1", "actual_years", first.actual_years,
          "clock_s", state.clock.t, "ship_clock_s", state.clock.ship_elapsed_s,
          "battery_kwh", state.ship.power.e_batt_kwh,
          "engine_health", state.ship.systems["engines"].health,
          "hull", state.ship.hull_integrity,
          "lore_eval_seq", state.world.lore_placements.eval_seq,
          "events", [event.type.value for _, event in first.events_to_render], flush=True)
    with TemporaryDirectory() as directory:
        slot = Path(directory) / "public.sav"
        save_single_slot(state, slot)
        restored = load_single_slot(slot).state
        assert restored.ship.physical_transit == state.ship.physical_transit
        assert restored.ship.power == state.ship.power
        assert restored.ship.drones == state.ship.drones
        assert restored.world.lore_placements == state.world.lore_placements
        assert restored.meta.rng_counter == state.meta.rng_counter
        print("SAVE_LOAD", "physical/power/drones/lore/RNG equal", flush=True)
        state = restored
        loop = GameLoop(Engine(), state)
        loop.set_auto_tick(False)
        final = repl._execute_hibernate(loop, 20.0, until_arrival=True)
    arrival = [(event.type.value, event.t) for _, event in final.events_to_render
               if event.type in {EventType.ARRIVED, EventType.PHYSICAL_STOPPED}]
    assert not final.woke_early and state.ship.physical_transit is None
    assert state.world.current_node_id == target
    assert len(arrival) == 1 and arrival[0][0] == EventType.ARRIVED.value
    assert state.ship.antimatter_capsules == initial_fuel - paid
    print("COMMAND hibernate until_arrival", "actual_years", final.actual_years,
          "wake_reason", final.wake_reason, "arrival", arrival, flush=True)
    print("FINAL", "clock_s", state.clock.t, "ship_clock_s", state.clock.ship_elapsed_s,
          "fuel", state.ship.antimatter_capsules,
          "engine_health", state.ship.systems["engines"].health,
          "hull", state.ship.hull_integrity,
          "battery_kwh", state.ship.power.e_batt_kwh,
          "drones", len(state.ship.drones), "node", state.world.current_node_id,
          "lore_eval_seq", state.world.lore_placements.eval_seq,
          "lore_next", state.world.lore_placements.next_non_forced_eval_t,
          "radio_opportunities", len(state.world.radio_opportunities),
          "rng_counter", state.meta.rng_counter, flush=True)
    command("engines speed 0.4")


if __name__ == "__main__":
    run()
