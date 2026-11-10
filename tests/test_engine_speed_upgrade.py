"""T-04A: engine state, independent modules and inertial transit via public flows."""
from contextlib import redirect_stdout
from copy import deepcopy
import asyncio
import io
import math
import os
from pathlib import Path
import pickle
import random
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.actions import PowerPlan, PowerShed, Repair, SystemOn, Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.io.save_load import SaveLoadError, load_single_slot, save_single_slot
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.runtime.data_loader import load_modules
from retorno.ui_textual import presenter
from retorno.ui_textual.app import RetornoTextualApp
from retorno.worldgen.generator import _pick_modules

SPEED = 'engine_speed_upgrade_01'
EFFICIENCY = 'engine_efficiency_upgrade_01'


def output(function, *args):
    with redirect_stdout(io.StringIO()) as stream:
        function(*args)
    return stream.getvalue()


class EngineSpeedUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.state = create_initial_state_sandbox(seed=29)
        self.engine = Engine()
        self.system = self.state.ship.systems['engines']
        self.system.base_decay_per_s = 0.0
        self.state.ship.docked_node_id = None

    def destination(self, local=False, ident='SPEED_TEST'):
        s = self.state
        origin = s.world.space.nodes[s.world.current_node_id]
        step = (.001 if local else 4.0) * (1 if origin.x_ly % 10 < 5 else -1)
        s.world.space.nodes[ident] = SpaceNode(
            ident, ident, 'station', x_ly=origin.x_ly + step,
            y_ly=origin.y_ly, z_ly=origin.z_ly, radiation_rad_per_s=.001)
        s.world.known_nodes.add(ident)
        s.world.known_contacts.add(ident)
        self.assertTrue(add_known_link(s.world, s.world.current_node_id, ident, bidirectional=True))
        if local:
            s.world.fine_ranges_km[ident] = 20_000.0
        return ident

    def refresh(self):
        self.engine._apply_health_state(self.system, self.state, [], cause='repair')

    def module_job(self, operation, module, *, complete=True):
        s = self.state
        drone = s.ship.drones['D1']
        drone.status = DroneStatus.DEPLOYED
        drone.location = DroneLocation(kind='ship_sector', id='ENG-R1')
        drone.battery = drone.integrity = 1.0
        s.ship.cargo_scrap = 200
        events = self.engine.apply_action(s, parse_command(f'drone {operation} D1 {module}'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in events), events)
        duration = Balance.INSTALL_TIME_S if operation == 'install' else Balance.UNINSTALL_TIME_S
        if complete:
            self.engine.tick(s, duration + 2)

    def test_state_speed_matrix_and_no_health_only_upgrade(self):
        bands = ((0, SystemState.OFFLINE, 0), (.2, SystemState.CRITICAL, 0),
                 (.35, SystemState.DAMAGED, .3), (.599, SystemState.DAMAGED, .3),
                 (.6, SystemState.LIMITED, .4), (.849, SystemState.LIMITED, .4),
                 (.85, SystemState.NOMINAL, .5), (1, SystemState.NOMINAL, .5))
        for installed in ([], [EFFICIENCY], [SPEED], [SPEED, SPEED, EFFICIENCY]):
            self.state.ship.installed_modules = installed
            for health, expected_state, speed in bands:
                with self.subTest(installed=installed, health=health):
                    self.system.health = health
                    if SPEED in installed and expected_state == SystemState.NOMINAL:
                        expected_state, speed = SystemState.UPGRADED, .8
                    self.refresh()
                    self.assertEqual(self.system.state, expected_state)
                    self.assertEqual(self.state.ship.engine_operating_state(), expected_state)
                    self.assertAlmostEqual(self.state.ship.effective_cruise_speed(), speed)
        # Even a stale externally assigned upgraded state cannot grant speed.
        self.state.ship.installed_modules = []
        self.system.state = SystemState.UPGRADED
        self.assertEqual(self.state.ship.effective_cruise_speed(), .5)
        self.refresh()
        self.assertEqual(self.system.state, SystemState.NOMINAL)

    def test_configuration_reference_and_subluminal_limit(self):
        ship = self.state.ship
        ship.cruise_speed_ly_per_year = .6
        self.assertEqual(ship.effective_cruise_speed(), .6)
        ship.installed_modules = [SPEED, SPEED]
        self.assertAlmostEqual(ship.effective_cruise_speed(), .96)
        ship.cruise_speed_ly_per_year = .8
        self.assertGreater(ship.effective_cruise_speed(), 0)
        self.assertLess(ship.effective_cruise_speed(), 1)
        self.assertNotIn('available speed=1.0c', repl.speed_readout(self.state))
        with patch.object(Balance, 'ENGINE_SPEED_MULTIPLIERS', {'upgraded': .75}):
            self.assertAlmostEqual(ship.effective_cruise_speed(), .6)
        for invalid in (0, -1, math.nan, math.inf):
            ship.cruise_speed_ly_per_year = invalid
            self.assertEqual(ship.effective_cruise_speed(), 0)

    def test_real_install_uninstall_duplicate_and_module_independence(self):
        s = self.state
        s.ship.cargo_modules = [SPEED, SPEED, EFFICIENCY]
        original_health = (self.system.health, self.system.health_max_effective)
        original_power = self.system.p_effective_kw()
        original_fuel = self.engine.engine_fuel_cost(s, 10)
        self.module_job('install', SPEED)
        self.assertEqual(s.ship.cargo_scrap, 182)
        self.assertEqual(self.system.state, SystemState.UPGRADED)
        self.assertEqual(s.ship.effective_cruise_speed(), .8)
        self.assertEqual(self.engine.engine_fuel_cost(s, 10), original_fuel)
        self.assertEqual(self.system.p_effective_kw(), original_power)
        self.module_job('install', SPEED)
        self.assertEqual(s.ship.installed_modules.count(SPEED), 2)
        self.assertEqual(s.ship.effective_cruise_speed(), .8)
        self.module_job('install', EFFICIENCY)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original_fuel * .8)
        self.assertEqual(s.ship.effective_cruise_speed(), .8)
        self.module_job('uninstall', SPEED)
        self.assertEqual(self.system.state, SystemState.UPGRADED)
        self.module_job('uninstall', SPEED)
        self.assertEqual(self.system.state, SystemState.NOMINAL)
        self.assertEqual(s.ship.effective_cruise_speed(), .5)
        self.assertIn(EFFICIENCY, s.ship.installed_modules)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original_fuel * .8)
        self.module_job('uninstall', EFFICIENCY)
        self.assertEqual(self.engine.engine_fuel_cost(s, 10), original_fuel)
        self.assertEqual((self.system.health, self.system.health_max_effective), original_health)
        self.assertEqual(self.system.p_effective_kw(), original_power)

    def test_damage_repair_shutdown_restart_and_critical_recovery(self):
        s = self.state
        s.ship.cargo_modules = [SPEED]
        self.module_job('install', SPEED)
        self.system.base_decay_per_s = .01
        self.engine._apply_degradation(s, 10, 1, False, 0)
        self.assertEqual(self.system.state, SystemState.LIMITED)
        self.system.base_decay_per_s = 0
        drone = s.ship.drones['D1']
        drone.battery = 1
        events = self.engine.apply_action(s, Repair(drone_id='D1', system_id='engines'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in events), events)
        with patch.object(Balance, 'REPAIR_JOB_FAIL_P_BASE', 0):
            self.engine.tick(s, Balance.REPAIR_TIME_S + 2)
        self.assertEqual(self.system.state, SystemState.UPGRADED)
        self.engine.apply_action(s, PowerShed(system_id='engines'))
        self.assertEqual(self.system.state, SystemState.OFFLINE)
        self.assertEqual(s.ship.effective_cruise_speed(), 0)
        self.engine.apply_action(s, SystemOn(system_id='engines'))
        self.assertEqual(self.system.state, SystemState.UPGRADED)
        self.system.health = .2
        self.refresh()
        self.assertEqual(self.system.state, SystemState.CRITICAL)
        for health, expected in ((.5, SystemState.DAMAGED), (.7, SystemState.LIMITED), (.9, SystemState.UPGRADED)):
            self.system.health = health
            self.refresh()
            self.assertEqual(self.system.state, expected)
        # Removing the module while damaged never restores nominal speed.
        self.system.health = .5
        self.module_job('uninstall', SPEED)
        self.assertEqual(self.system.state, SystemState.DAMAGED)
        self.assertEqual(s.ship.effective_cruise_speed(), .3)

    def test_departure_eta_fuel_and_proper_time_by_state(self):
        target = self.destination()
        for health, module, beta in ((.9, False, .5), (.7, True, .4), (.5, True, .3), (.9, True, .8)):
            with self.subTest(beta=beta):
                s = deepcopy(self.state)
                s.ship.systems['engines'].health = health
                s.ship.installed_modules = [SPEED] if module else []
                expected_fuel = self.engine.estimate_travel_fuel(s, target)
                duration = self.engine.estimate_travel_duration(s, target)
                self.assertAlmostEqual(duration, 4 / beta * Balance.YEAR_S)
                events = self.engine.apply_action(s, Travel(node_id=target))
                started = next(e for e in events if e.type == EventType.TRAVEL_STARTED)
                self.assertAlmostEqual(started.data['eta_s'], duration)
                self.assertEqual(started.data['speed_ly_per_year'], beta)
                self.assertEqual(s.ship.transit_speed_ly_per_year, beta)
                self.assertEqual(s.ship.arrival_t, s.clock.t + duration)
                self.assertEqual(s.ship.antimatter_capsules, 12 - expected_fuel)
                self.engine.tick(s, 100)
                self.assertAlmostEqual(s.clock.ship_elapsed_s, 100 * math.sqrt(1 - beta * beta))
                self.assertAlmostEqual(s.clock.bio_elapsed_s, s.clock.ship_elapsed_s)

    def test_inertial_freeze_with_damage_repairs_modules_and_save_load(self):
        target = self.destination()
        s = self.state
        s.ship.cargo_modules = [SPEED, EFFICIENCY]
        self.module_job('install', SPEED)
        self.module_job('install', EFFICIENCY)
        # Removal requests retain their existing transit gate. Queue before
        # departure; the ordinary job then completes while cruising.
        self.module_job('uninstall', SPEED, complete=False)
        before = s.clock.ship_elapsed_s
        self.engine.apply_action(s, Travel(node_id=target))
        arrival, fuel = s.ship.arrival_t, s.ship.antimatter_capsules
        self.system.base_decay_per_s = .01
        self.engine.tick(s, 50)
        self.assertEqual(self.system.state, SystemState.DAMAGED)
        self.assertEqual(s.ship.transit_speed_ly_per_year, .8)
        self.assertAlmostEqual(s.clock.ship_elapsed_s - before, 30)
        self.system.base_decay_per_s = 0
        self.assertNotIn(SPEED, s.ship.installed_modules)
        self.assertEqual(s.ship.transit_speed_ly_per_year, .8)
        self.engine.apply_action(s, PowerPlan(mode='normal'))
        self.system.health = .8
        self.refresh()
        events = self.engine.apply_action(s, Repair(drone_id='D1', system_id='engines'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in events), events)
        with patch.object(Balance, 'REPAIR_JOB_FAIL_P_BASE', 0):
            self.engine.tick(s, Balance.REPAIR_TIME_S + 2)
        self.assertEqual(self.system.state, SystemState.NOMINAL)
        s.ship.cruise_speed_ly_per_year = .6
        self.assertEqual(s.ship.effective_cruise_speed(), .6)
        self.assertEqual(s.ship.arrival_t, arrival)
        self.assertEqual(s.ship.antimatter_capsules, fuel)
        # Persist both modules as well as a degraded engine during an active trip.
        self.module_job('install', SPEED)
        self.system.health = .7
        self.refresh()
        with TemporaryDirectory() as folder:
            slot = Path(folder) / 'speed.dat'
            save_single_slot(s, slot)
            loaded = load_single_slot(slot).state
        self.assertEqual(loaded.ship.installed_modules, s.ship.installed_modules)
        self.assertEqual(loaded.ship.systems['engines'].state, SystemState.LIMITED)
        self.assertEqual(loaded.ship.transit_speed_ly_per_year, .8)
        self.assertEqual(loaded.ship.arrival_t, arrival)
        elapsed = loaded.clock.ship_elapsed_s
        self.engine.tick(loaded, 100)
        self.assertAlmostEqual(loaded.clock.ship_elapsed_s - elapsed, 60)
        self.assertEqual(loaded.ship.antimatter_capsules, fuel)
        self.engine.apply_action(loaded, TravelAbort())
        elapsed = loaded.clock.ship_elapsed_s
        self.engine.tick(loaded, 100)
        self.assertAlmostEqual(loaded.clock.ship_elapsed_s - elapsed, 100)
        self.assertEqual(loaded.ship.antimatter_capsules, fuel)

    def test_local_travel_and_gate_independent_of_multipliers(self):
        target = self.destination(local=True)
        for modules in ([], [SPEED, EFFICIENCY]):
            for health in (.5, .7, .9):
                s = deepcopy(self.state)
                s.ship.installed_modules = modules
                s.ship.systems['engines'].health = health
                s.ship.cruise_speed_ly_per_year = 0
                s.ship.antimatter_capsules = 0
                self.assertEqual(self.engine.estimate_travel_duration(s, target), 1000)
                self.engine.apply_action(s, Travel(node_id=target))
                self.assertTrue(s.ship.last_travel_is_local)
                self.assertEqual(s.ship.arrival_t - s.clock.t, 1000)
                self.assertEqual(s.ship.antimatter_capsules, 0)
                self.engine.tick(s, 10)
                self.assertAlmostEqual(s.clock.ship_elapsed_s, 10 * math.sqrt(1 - (20 / 299_792.458)**2))
        for health in (0, .2):
            s = deepcopy(self.state)
            s.ship.systems['engines'].health = health
            events = self.engine.apply_action(s, Travel(node_id=target))
            self.assertEqual(events[0].data['reason'], 'engines_unavailable')
            self.assertFalse(s.ship.in_transit)

    def test_public_queries_are_pure_and_respect_acquired_routes(self):
        target = self.destination()
        secret = self.destination(ident='UNOBSERVED_SPEED_SECRET')
        s = self.state
        s.world.known_nodes.discard(secret)
        s.world.known_contacts.discard(secret)
        s.world.known_links[s.world.current_node_id].discard(secret)
        before = pickle.dumps(s)
        self.assertIsNone(self.engine.estimate_travel_duration(s, secret))
        self.assertEqual(repl.speed_readout(s, secret), '')
        first = output(repl.render_nav_routes, s)
        self.assertNotIn(secret, first)
        self.assertEqual(pickle.dumps(s), before)
        other = deepcopy(s)
        other.world.space.nodes[secret].x_ly += 100000
        other.world.space.nodes[secret].name = 'CHANGED_SECRET'
        self.assertEqual(output(repl.render_nav_routes, other), first)
        self.assertIsNotNone(self.engine.estimate_travel_duration(s, target))
        self.system.forced_offline = True
        self.assertIsNone(self.engine.estimate_travel_duration(s, target))

    def test_catalog_manual_help_and_shared_public_views_en_es(self):
        modules = load_modules()
        self.assertEqual(modules[SPEED]['scope'], 'ship')
        for key in ('pool', 'scrap_cost'):
            self.assertEqual(modules[SPEED][key], modules[EFFICIENCY][key])
        self.assertEqual(modules[SPEED]['effects'], {'engine_speed_upgrade': True})
        selected = set()
        for seed in range(64):
            selected.update(_pick_modules(random.Random(seed), list(modules), 1, 3, 'rare'))
        self.assertIn(SPEED, selected)
        target = self.destination()
        s = self.state
        s.ship.installed_modules = [SPEED, EFFICIENCY]
        self.refresh()
        self.engine.apply_action(s, Travel(node_id=target))
        self.system.health = .5
        self.refresh()
        for locale in (Locale.EN, Locale.ES):
            s.os.locale = locale
            expected = repl.speed_readout(s)
            self.assertIn('0.3c', expected)
            self.assertIn('0.8c', expected)
            self.assertIn(expected, output(repl.render_status, s))
            self.assertIn(expected, output(repl.render_diag, s, 'engines'))
            self.assertNotIn(expected, presenter.build_status_lines(s))
            self.assertTrue(any(line.startswith('engines ') for line in presenter.build_status_lines(s)))
            self.assertEqual(presenter.build_command_output(repl.render_nav_routes, s),
                             output(repl.render_nav_routes, s).strip().splitlines())
            for module in (SPEED, EFFICIENCY):
                inspect = output(repl.render_module_inspect, s, module)
                self.assertIn(modules[module][f'desc_{locale.value}'], inspect)
                self.assertIn(module, output(repl.render_man, s, module))
            self.assertIn('duración' if locale == Locale.ES else 'duration', output(repl.print_help, locale.value, True))
            quote = repl.speed_readout(s, target)
            with patch('builtins.input', return_value='s' if locale == Locale.ES else 'y'):
                self.assertIn(quote, output(repl._confirm_nav, s, Travel(node_id=target)))
            lines = []
            harness = SimpleNamespace(loop=SimpleNamespace(state=s), _log_line=lines.append)
            RetornoTextualApp._confirm_nav_needed(harness, s, Travel(node_id=target))
            self.assertIn(quote, lines)

    def test_invalid_frozen_speed_is_rejected_on_save(self):
        target = self.destination()
        self.engine.apply_action(self.state, Travel(node_id=target))
        self.state.ship.transit_speed_ly_per_year = 0
        with TemporaryDirectory() as folder:
            with self.assertRaises(SaveLoadError):
                save_single_slot(self.state, Path(folder) / 'invalid.dat')

    def test_textual_commands_departure_and_inertial_telemetry_en_es(self):
        from textual.widgets import Input
        target = self.destination()
        self.state.ship.installed_modules = [SPEED, EFFICIENCY]
        self.refresh()

        async def check(locale, slot):
            with patch.dict(os.environ, {'RETORNO_SCENARIO': 'sandbox'}):
                app = RetornoTextualApp(force_new_game=True, save_path=str(slot))
            s = deepcopy(self.state)
            s.os.locale = locale
            s.os.audio.enabled = s.os.audio.ambient_enabled = False
            app.loop.state = s
            app.loop.set_auto_tick(False)
            app._play_startup_sequence = app._startup_panel_blackout = False
            async with app.run_test() as pilot:
                app.loop.set_auto_tick(False)
                widget = app.query_one('#input', Input)

                async def command(text):
                    widget.value = text
                    widget.focus()
                    await pilot.press('enter')
                    await pilot.pause()

                await command('module inspect ' + SPEED)
                await command('nav map routes')
                quote = repl.speed_readout(s, target)
                self.assertTrue(any(quote in line for line in app._log_buffer))
                await command('nav ' + target)
                await command('s' if locale == Locale.ES else 'y')
                self.assertTrue(s.ship.in_transit)
                self.assertEqual(s.ship.transit_speed_ly_per_year, .8)
                eta = s.ship.arrival_t
                s.ship.systems['engines'].health = .5
                self.engine._apply_health_state(s.ship.systems['engines'], s, [], cause='degradation')
                await command('diag engines')
                self.assertTrue(any(repl.speed_readout(s) in line for line in app._log_buffer))
                self.assertEqual(s.ship.arrival_t, eta)
                await command('nav abort')
                await command('s' if locale == Locale.ES else 'y')
                self.assertFalse(s.ship.in_transit)

        with TemporaryDirectory() as folder:
            for locale in (Locale.EN, Locale.ES):
                asyncio.run(check(locale, Path(folder) / f'{locale.value}.dat'))


if __name__ == '__main__':
    unittest.main()
