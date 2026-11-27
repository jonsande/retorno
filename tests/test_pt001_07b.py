"""PT001-07B acceptance: coupled drone charging and electrical cuts."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.actions import Travel
from retorno.core.drone_charging import decide_drone_charging
from retorno.core.engine import Engine
from retorno.core.nav_electricity import capture_power_snapshot, invalidation_reasons, power_limits
from retorno.core.temporal import proper_time_interval
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.systems import SystemState
from retorno.runtime.loop import GameLoop
from tests.test_nav_public_physical import public_game


def quiet_ship(*, net=0.2, soc=.5, drones=1):
    state = create_initial_state_sandbox(seed=713)
    state.jobs.jobs.clear()
    state.jobs.active_job_ids.clear()
    state.world.lore_placements.next_non_forced_eval_t = 1e9
    for system in state.ship.systems.values():
        system.health = 1.0
        system.state = SystemState.NOMINAL
        system.forced_offline = False
        system.base_decay_per_s = 0.0
        system.p_nom_kw = 0.0
    state.ship.systems["core_os"].p_nom_kw = .6
    state.ship.systems["drone_bay"].p_nom_kw = .4
    base = Engine()._compute_load_kw(state)
    assert base == pytest.approx(1.0)
    power = state.ship.power
    power.p_gen_base_kw = power.p_gen_kw = base + net
    power.e_batt_max_kwh = 10.0
    power.e_batt_kwh = soc * power.e_batt_max_kwh
    power.p_charge_max_kw = power.p_discharge_max_kw = 5.0
    power.eta_charge = power.eta_discharge = 1.0
    power.quality_offset = 1.0
    power.power_quality = 1.0
    first = state.ship.drones["D1"]
    first.battery = .5
    first.integrity = 1.0
    for index in range(2, drones + 1):
        extra = deepcopy(first)
        extra.drone_id = f"D{index}"
        state.ship.drones[extra.drone_id] = extra
    return state


@pytest.mark.parametrize("net,soc,expected_kw", [
    (.3, .5, .2), (-.1, .5, .05), (-.1, .25, 0), (-.1, .2, 0),
    (.03, .2, .03), (.03, .25, .03), (.1, .25, .05),
])
def test_charge_power_soc_and_energy(net, soc, expected_kw):
    state = quiet_ship(net=net, soc=soc)
    power = state.ship.power
    power.eta_charge = .8
    power.eta_discharge = .75
    initial_energy = power.e_batt_kwh
    initial_drone = state.ship.drones["D1"].battery
    base = Engine()._compute_load_kw(state)
    assert decide_drone_charging(state, power.p_gen_kw, base).power_kw == pytest.approx(expected_kw)
    Engine().tick(state, 10)
    assert state.ship.drones["D1"].battery - initial_drone == pytest.approx(
        expected_kw * 10 / 3600 / Balance.DRONE_BATTERY_KWH_PER_UNIT)
    actual_net = net - expected_kw
    expected_delta = (max(0, actual_net) * power.eta_charge
                      - max(0, -actual_net) / power.eta_discharge) * 10 / 3600
    assert power.e_batt_kwh - initial_energy == pytest.approx(expected_delta)
    assert power.p_load_kw == pytest.approx(base + expected_kw)


def test_floor_crossing_and_surplus_are_stable_in_both_directions():
    falling = quiet_ship(net=-.1, soc=.2501)
    falling.ship.power.eta_discharge = 1.0
    start_drone = falling.ship.drones["D1"].battery
    Engine().tick(falling, 200)
    floor = Balance.DRONE_CHARGE_RESERVE_SOC * falling.ship.power.e_batt_max_kwh
    assert falling.ship.power.e_batt_kwh < floor
    # 0.001 kWh above the floor, at 0.15 kW including charge.
    assert falling.ship.drones["D1"].battery - start_drone == pytest.approx(
        (.001 / .15 * 3600) * .00125)

    rising = quiet_ship(net=.1, soc=.2499)
    start_drone = rising.ship.drones["D1"].battery
    Engine().tick(rising, 100)
    assert rising.ship.power.e_batt_kwh > Balance.DRONE_CHARGE_RESERVE_SOC * 10
    assert rising.ship.drones["D1"].battery - start_drone == pytest.approx(.00125 * 100)

    sliding = quiet_ship(net=.03, soc=.25001)
    Engine().tick(sliding, 100)
    assert sliding.ship.power.e_batt_kwh == pytest.approx(2.5, abs=1e-12)
    assert sliding.ship.power.p_load_kw == pytest.approx(1.03)


def test_discharge_limit_bay_penalty_and_deterministic_distribution():
    state = quiet_ship(net=-.1, drones=3)
    state.ship.power.p_discharge_max_kw = .16
    plan = decide_drone_charging(state, .9, 1.0)
    assert [item.drone_id for item in plan.allocations] == ["D1", "D2"]
    assert [item.power_kw for item in plan.allocations] == pytest.approx([.05, .01])
    Engine().tick(state, 10)
    assert state.ship.drones["D1"].battery > state.ship.drones["D2"].battery > .5
    assert state.ship.drones["D3"].battery == .5

    limited = quiet_ship(net=.2)
    limited.ship.systems["drone_bay"].state = SystemState.LIMITED
    plan = decide_drone_charging(limited, 1.2, 1.0)
    assert plan.allocations[0].power_kw == pytest.approx(.1)
    assert plan.allocations[0].rate_per_s == pytest.approx(.0025)
    damaged = quiet_ship(net=.2)
    damaged.ship.systems["drone_bay"].state = SystemState.DAMAGED
    plan = decide_drone_charging(damaged, 1.2, 1.0)
    assert plan.allocations[0].power_kw == pytest.approx(.05)
    assert plan.allocations[0].rate_per_s == pytest.approx(.00125)


def test_only_docked_in_bay_drones_receive_power_and_full_drones_release_it():
    state = quiet_ship(net=.25, drones=4)
    state.ship.drones["D1"].battery = .99
    state.ship.drones["D3"].location = DroneLocation("ship_sector", "CORE")
    state.ship.drones["D4"].status = DroneStatus.DEPLOYED
    plan = decide_drone_charging(state, 1.25, 1.0)
    assert [item.drone_id for item in plan.allocations] == ["D1", "D2"]
    Engine().tick(state, 10)
    assert state.ship.drones["D1"].battery == pytest.approx(1.0)
    # D1 completes at two proper seconds; D2 receives the freed full rate.
    assert state.ship.drones["D2"].battery == pytest.approx(.5 + .00125 * 2 + .005 * 8)
    assert state.ship.drones["D3"].battery == .5
    assert state.ship.drones["D4"].battery < .5  # deployed idle drain only


def test_long_and_short_intervals_have_the_same_charge_and_accounting():
    long = quiet_ship(net=-.1, soc=.2501, drones=2)
    long.ship.drones["D1"].battery = .99
    short = deepcopy(long)
    Engine().tick(long, 40)
    for _ in range(40):
        Engine().tick(short, 1)
    assert long.ship.power.e_batt_kwh == pytest.approx(short.ship.power.e_batt_kwh, abs=1e-12)
    for key in long.ship.drones:
        assert long.ship.drones[key].battery == pytest.approx(short.ship.drones[key].battery, abs=1e-12)


def test_charge_during_relativistic_transit_uses_ship_seconds_only():
    state = quiet_ship(net=.3)
    ship = state.ship
    ship.in_transit = True
    ship.docked_node_id = None
    ship.transit_from = ship.current_node_id
    ship.transit_to = "FUTURE"
    ship.arrival_t = 1000.0
    ship.transit_speed_ly_per_year = .8
    ship.last_travel_is_local = False
    initial = ship.drones["D1"].battery
    Engine().tick(state, 10)
    assert ship.drones["D1"].battery - initial == pytest.approx(
        .005 * proper_time_interval(10, .8))
    assert state.clock.ship_elapsed_s == pytest.approx(proper_time_interval(10, .8))


def test_electrical_subdivisions_do_not_repeat_other_work():
    state = quiet_ship(net=-.1, soc=.2501)
    state.ship.drones["D1"].battery = .99
    engine = Engine()
    rng_before = state.meta.rng_counter
    with patch.object(engine, "_process_jobs", wraps=engine._process_jobs) as jobs, \
         patch.object(engine, "_update_drone_maintenance",
                      wraps=engine._update_drone_maintenance) as maintenance, \
         patch("retorno.core.engine.run_lore_scheduler_tick") as lore:
        engine.tick(state, 40)
    assert jobs.call_count == maintenance.call_count == lore.call_count == 1
    assert state.meta.rng_counter == rng_before


def test_forecast_cuts_full_drone_and_reserve_floor_without_idle_extras():
    state = quiet_ship(net=-.1, soc=.2501)
    snapshot = capture_power_snapshot(state, .9, 1.0)
    kinds = {limit.kind for limit in power_limits(snapshot)}
    assert {"drone_charge_soc_floor", "drone_battery_full"} <= kinds
    state.ship.drones["D1"].battery = 1.0
    snapshot = capture_power_snapshot(state, .9, 1.0)
    assert not any(limit.kind.startswith("drone_") for limit in power_limits(snapshot))


def test_charging_forecast_invalidates_when_availability_changes():
    state = quiet_ship(net=-.1)
    initial = capture_power_snapshot(state, .9, 1.0)
    state.ship.systems["drone_bay"].forced_offline = True
    after = capture_power_snapshot(state, .9, 1.0)
    assert "charging_changed" in invalidation_reasons(initial, after)
    assert after.charging.power_kw == 0


def test_physical_proper_seconds_and_unresolved_cut_atomicity():
    state = public_game(1e6 / 9.4607304725808e15)
    donor = quiet_ship(net=.3)
    state.ship.drones = donor.ship.drones
    for system in state.ship.systems.values():
        system.p_nom_kw = donor.ship.systems[system.system_id].p_nom_kw
    state.ship.power.p_gen_base_kw = state.ship.power.p_gen_kw = 1.3
    state.ship.power.quality_offset = 1.0
    state.ship.power.e_batt_kwh = 3.0
    engine = Engine()
    engine.apply_action(state, Travel("NOMINAL_B"))
    state.ship.systems["drone_bay"].forced_offline = False
    state.ship.systems["drone_bay"].state = SystemState.NOMINAL
    state.ship.drones["D1"].battery = .99
    before = pickle.dumps(state)
    with pytest.raises(RuntimeError, match="unresolved causal boundary"):
        engine._tick_physical_segment(state, 10)
    assert pickle.dumps(state) == before
    GameLoop(engine, state).advance_interval(10)
    gained = state.ship.drones["D1"].battery - .99
    proper = state.clock.ship_elapsed_s
    assert gained == pytest.approx(min(.01, .005 * proper))


def test_capacity_shed_does_not_force_a_stale_soc_floor():
    state = quiet_ship(net=-.1, soc=.2501)
    sensors = state.ship.systems["sensors"]
    sensors.p_nom_kw = .5
    sensors.priority = 99
    state.ship.power.p_discharge_max_kw = .2
    initial = state.ship.power.e_batt_kwh

    Engine()._integrate_power_interval(state, 18)

    assert sensors.forced_offline
    assert state.ship.power.p_load_kw == pytest.approx(1.05)
    assert state.ship.power.e_batt_kwh == pytest.approx(initial - .15 * 18 / 3600,
                                                        abs=1e-12)
    assert state.ship.power.e_batt_kwh > 2.5
    assert state.ship.drones["D1"].battery == pytest.approx(.5 + .00125 * 18)


def test_timed_shed_cuts_at_actual_drone_full_boundary():
    state = quiet_ship(net=.3, soc=.5)
    sensors = state.ship.systems["sensors"]
    sensors.p_nom_kw = .5
    sensors.priority = 99
    state.ship.power.quality_offset = -.65
    state.ship.power.low_q_shed_timer_s = 9.9
    state.ship.drones["D1"].battery = .99
    initial = state.ship.power.e_batt_kwh

    Engine()._integrate_power_interval(state, 10)

    assert sensors.forced_offline
    assert state.ship.drones["D1"].battery == pytest.approx(1.0)
    # The timer expires at 0.1 s; its slow gain leaves 1.975 s at full rate.
    expected = initial + (-.25 * .1 + .1 * 1.975 + .3 * 7.925) / 3600
    assert state.ship.power.e_batt_kwh == pytest.approx(expected, abs=1e-12)
    assert state.ship.power.p_load_kw == pytest.approx(1.0)


def test_shed_and_soc_floor_at_same_instant_keep_progress():
    state = quiet_ship(net=.3, soc=.25)
    sensors = state.ship.systems["sensors"]
    sensors.p_nom_kw = .5
    sensors.priority = 99
    state.ship.power.e_batt_kwh += .25 * .1 / 3600
    state.ship.power.quality_offset = -.3
    state.ship.power.low_q_shed_timer_s = 9.9
    initial = state.ship.power.e_batt_kwh

    Engine()._integrate_power_interval(state, 1)

    assert sensors.forced_offline
    assert state.ship.power.e_batt_kwh == pytest.approx(
        initial + (-.25 * .1 + .1 * .9) / 3600, abs=1e-12)
    assert state.ship.drones["D1"].battery == pytest.approx(
        .5 + .00125 * .1 + .005 * .9)


def test_no_charging_cut_when_shedding_makes_bay_unavailable():
    state = quiet_ship(net=-.1, soc=.2501)
    state.ship.power.p_discharge_max_kw = .05
    engine = Engine()
    with patch.object(engine, "_integrate_power_slice", wraps=engine._integrate_power_slice) as slices:
        engine._integrate_power_interval(state, 100)
    assert state.ship.systems["drone_bay"].forced_offline
    assert state.ship.drones["D1"].battery == .5
    assert slices.call_count == 1


def test_god_mode_never_snaps_main_battery_to_reserve_floor():
    state = quiet_ship(net=.3, soc=.24999)
    state.os.debug_enabled = state.os.debug_god_enabled = True
    initial = state.ship.power.e_batt_kwh
    Engine()._integrate_power_interval(state, 10)
    assert state.ship.power.e_batt_kwh == initial
    assert state.ship.drones["D1"].battery == pytest.approx(.55)
