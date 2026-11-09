"""Antimatter integration: real actions, fuel atomicity and shared public views."""
from contextlib import redirect_stdout
from copy import deepcopy
import asyncio
import io
import math
import os
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.actions import Repair, PowerPlan, PowerShed, SystemOn, Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.io.save_load import save_single_slot, load_single_slot, SaveLoadError
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.runtime.data_loader import load_modules
from retorno.ui_textual import presenter
from retorno.ui_textual.app import RetornoTextualApp

UPGRADE = 'engine_efficiency_upgrade_01'


def output(fn, *args):
    with redirect_stdout(io.StringIO()) as stream:
        fn(*args)
    return stream.getvalue()


class EnginesAntimatterTests(unittest.TestCase):
    def setUp(self):
        self.state = create_initial_state_sandbox(seed=29)
        self.engine = Engine()
        self.state.ship.docked_node_id = None

    def destination(self, distance=2.0, ident='FUEL_TEST'):
        s = self.state
        origin = s.world.space.nodes[s.world.current_node_id]
        # Move toward the interior of the current sector for local fixtures.
        step = distance if origin.x_ly % 10 < 5 else -distance
        s.world.space.nodes[ident] = SpaceNode(
            node_id=ident, name=ident, kind='station', radiation_rad_per_s=0.001,
            x_ly=origin.x_ly + step, y_ly=origin.y_ly, z_ly=origin.z_ly)
        s.world.known_nodes.add(ident)
        s.world.known_contacts.add(ident)
        self.assertTrue(add_known_link(s.world, s.world.current_node_id, ident, bidirectional=True))
        return ident

    def deployed_drone(self):
        s = self.state
        drone = s.ship.drones['D1']
        drone.status = DroneStatus.DEPLOYED
        drone.location = DroneLocation(kind='ship_sector', id='ENG-R1')
        drone.battery = drone.integrity = 1.0
        s.ship.cargo_scrap = 100
        s.ship.systems['engines'].base_decay_per_s = 0.0
        return drone

    def test_01_new_game_and_power_profiles(self):
        s = create_initial_state_prologue(seed=29)
        engines = s.ship.systems['engines']
        self.assertEqual((engines.state, engines.health, engines.sector_id), (SystemState.NOMINAL, .9, 'ENG-R1'))
        self.assertEqual(s.ship.antimatter_capsules, 12.0)
        self.assertNotIn('security', s.ship.systems)
        self.assertNotIn('securityd', self.engine._available_services(s))
        self.assertNotIn('reserved', s.ship.sectors['ENG-R1'].tags)
        self.engine.apply_action(s, PowerPlan(mode='cruise'))
        self.assertFalse(engines.forced_offline)
        self.assertEqual(engines.p_effective_kw(), .2)
        for shed in (self.engine._auto_load_shed,):
            shed(s, 0.0, self.engine._compute_load_kw(s))
        self.engine._shed_all_noncritical(s)
        self.engine._auto_shed_one_noncritical(s)
        self.assertFalse(engines.forced_offline)
        self.assertEqual(engines.state, SystemState.NOMINAL)
        self.assertGreaterEqual(self.engine._compute_load_kw(s), .2)

    def test_02_formula_normalization_and_fractional_precision(self):
        system = self.state.ship.systems['engines']
        system.health = 1.0
        for distance, expected in ((2, .7), (10, 1.5), (20, 2.5), (45, 5.0)):
            self.assertAlmostEqual(self.engine.engine_fuel_cost(self.state, distance), expected)
        system.health = .5
        self.assertAlmostEqual(self.engine.engine_fuel_cost(self.state, 10), 1.5 * 1.375)
        system.health_max_effective = 2
        system.health = 1
        self.assertAlmostEqual(self.engine.engine_fuel_cost(self.state, 10), 1.5 * 1.375)
        for health, factor in ((-1, 2.5), (4, 1)):
            system.health = health
            self.assertEqual(self.engine.engine_fuel_cost(self.state, 10), 1.5 * factor)
        for distance in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.engine.engine_fuel_cost(self.state, distance)

    def test_03_real_module_install_uninstall(self):
        self.deployed_drone()
        s = self.state
        s.ship.cargo_modules = [UPGRADE]
        integrity = s.ship.systems['engines'].health
        original = self.engine.engine_fuel_cost(s, 10)
        ev = self.engine.apply_action(s, parse_command(f'drone install D1 {UPGRADE}'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in ev), ev)
        self.assertEqual(self.engine.engine_fuel_cost(s, 10), original)
        self.engine.tick(s, Balance.INSTALL_TIME_S + 2)
        self.assertIn(UPGRADE, s.ship.installed_modules)
        self.assertEqual(s.ship.systems['engines'].health, integrity)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original * .8)
        # Existing module infrastructure permits duplicate copies: the first
        # efficiency level still means 0.8, not an exponential discount.
        s.ship.installed_modules.append(UPGRADE)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original * .8)
        s.ship.installed_modules.pop()
        ev = self.engine.apply_action(s, parse_command(f'drone uninstall D1 {UPGRADE}'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in ev), ev)
        self.engine.tick(s, Balance.UNINSTALL_TIME_S + 2)
        self.assertNotIn(UPGRADE, s.ship.installed_modules)
        self.assertIn(UPGRADE, s.ship.cargo_modules)
        self.assertEqual(s.ship.systems['engines'].health, integrity)
        self.assertEqual(self.engine.engine_fuel_cost(s, 10), original)

    def test_04_wear_and_drone_repair_recover_efficiency(self):
        s = self.state
        before = self.engine.engine_fuel_cost(s, 10)
        self.engine._apply_degradation(s, 10 * Balance.YEAR_S, .9, False, .001)
        damaged = self.engine.engine_fuel_cost(s, 10)
        self.assertGreater(damaged, before)
        self.deployed_drone()
        start_health = s.ship.systems['engines'].health
        ev = self.engine.apply_action(s, Repair(drone_id='D1', system_id='engines'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in ev), ev)
        with patch.object(Balance, 'REPAIR_JOB_FAIL_P_BASE', 0):
            self.engine.tick(s, Balance.REPAIR_TIME_S + 2)
        self.assertGreater(s.ship.systems['engines'].health, start_health)
        self.assertLess(self.engine.engine_fuel_cost(s, 10), damaged)

    def test_05_insufficient_fuel_atomicity_and_exact_balance(self):
        target = self.destination()
        s = self.state
        price = self.engine.estimate_travel_fuel(s, target)
        # One representable float below the unrounded price must be rejected.
        s.ship.antimatter_capsules = math.nextafter(price, 0)
        before = pickle.dumps((s.ship, s.world, s.meta.rng_counter))
        ev = self.engine.apply_action(s, Travel(node_id=target))
        self.assertEqual(ev[0].data['reason'], 'insufficient_antimatter')
        self.assertEqual(pickle.dumps((s.ship, s.world, s.meta.rng_counter)), before)
        s.ship.antimatter_capsules = price
        ev = self.engine.apply_action(s, Travel(node_id=target))
        self.assertTrue(s.ship.in_transit)
        self.assertEqual(s.ship.antimatter_capsules, 0.0)
        self.assertEqual(next(e for e in ev if e.type == EventType.TRAVEL_STARTED).data['fuel_cost'], price)
        self.assertFalse(s.ship.systems['engines'].forced_offline)
        self.assertEqual(s.ship.op_mode, 'CRUISE')
        self.assertEqual(s.ship.arrival_t, s.clock.t + 4 * Balance.YEAR_S)

    def test_06_duplicate_requests_abort_arrival_and_save_load(self):
        target = self.destination()
        s = self.state
        s.ship.installed_modules = [UPGRADE]
        cost = self.engine.estimate_travel_fuel(s, target)
        self.engine.apply_action(s, Travel(node_id=target))
        remaining = s.ship.antimatter_capsules
        self.assertEqual(remaining, 12.0 - cost)
        self.engine.apply_action(s, Travel(node_id=target))
        self.engine.tick(s, 10)
        self.assertEqual(s.ship.antimatter_capsules, remaining)
        with TemporaryDirectory() as folder:
            slot = Path(folder) / 'engines.dat'
            save_single_slot(s, slot)
            loaded = load_single_slot(slot).state
        self.assertEqual(loaded.ship.antimatter_capsules, remaining)
        self.assertEqual(loaded.ship.systems['engines'], s.ship.systems['engines'])
        self.assertIn(UPGRADE, loaded.ship.installed_modules)
        self.engine.apply_action(loaded, TravelAbort())
        self.assertFalse(loaded.ship.in_transit)
        self.assertEqual(loaded.ship.antimatter_capsules, remaining)
        waypoint = loaded.world.current_node_id
        self.engine.apply_action(loaded, TravelAbort())
        self.assertEqual(loaded.world.current_node_id, waypoint)
        self.assertEqual(loaded.ship.antimatter_capsules, remaining)
        # Completion charges nothing, independently of the initial charge.
        s.ship.arrival_t = s.clock.t + 1
        self.engine.tick(s, 1)
        self.assertFalse(s.ship.in_transit)
        self.assertEqual(s.ship.antimatter_capsules, remaining)

    def test_07_local_travel_and_isolated_engines(self):
        target = self.destination(.001)
        s = self.state
        s.ship.antimatter_capsules = 0.0
        self.assertEqual(self.engine.estimate_travel_fuel(s, target), 0.0)
        self.assertNotIn(target, s.world.fine_ranges_km)
        self.engine.apply_action(s, PowerShed(system_id='engines'))
        before = pickle.dumps((s.ship, s.world))
        ev = self.engine.apply_action(s, Travel(node_id=target))
        self.assertEqual(ev[0].data['reason'], 'engines_unavailable')
        self.assertEqual(before, pickle.dumps((s.ship, s.world)))
        self.engine.apply_action(s, SystemOn(system_id='engines'))
        ev = self.engine.apply_action(s, Travel(node_id=target, no_cruise=True))
        self.assertTrue(s.ship.in_transit, ev)
        self.assertTrue(s.ship.last_travel_is_local)
        self.assertEqual(s.ship.antimatter_capsules, 0.0)
        self.engine.apply_action(s, TravelAbort())
        self.assertEqual(s.ship.antimatter_capsules, 0.0)

    def test_11_engine_state_gates_and_upgrade_enables_departure(self):
        target = self.destination(10)
        s = self.state
        engines = s.ship.systems['engines']
        for state, health in ((SystemState.OFFLINE, 0), (SystemState.CRITICAL, .2)):
            engines.state, engines.health = state, health
            before = pickle.dumps((s.ship, s.world))
            ev = self.engine.apply_action(s, Travel(node_id=target))
            self.assertEqual(ev[0].data['reason'], 'engines_unavailable')
            self.assertEqual(pickle.dumps((s.ship, s.world)), before)
        engines.state, engines.health = SystemState.DAMAGED, .5
        original = self.engine.estimate_travel_fuel(s, target)
        s.ship.antimatter_capsules = original * .9
        ev = self.engine.apply_action(s, Travel(node_id=target))
        self.assertEqual(ev[0].data['reason'], 'insufficient_antimatter')
        s.ship.installed_modules = [UPGRADE]
        ev = self.engine.apply_action(s, Travel(node_id=target, no_cruise=True))
        self.assertTrue(s.ship.in_transit, ev)
        self.assertEqual(engines.health, .5)
        self.assertAlmostEqual(s.ship.antimatter_capsules, original * .1)
        self.assertEqual(s.ship.op_mode, 'NORMAL')

    def test_08_public_views_localization_and_textual_confirmations(self):
        target = self.destination()
        s = self.state
        for locale in (Locale.EN, Locale.ES):
            s.os.locale = locale
            expected = repl.fuel_readout(s, target)
            before = pickle.dumps(s)
            routes = output(repl.render_nav_routes, s)
            self.assertIn(expected, routes)
            self.assertEqual(presenter.build_command_output(repl.render_nav_routes, s), routes.strip().splitlines())
            self.assertEqual(pickle.dumps(s), before)
            for view in (repl.render_inventory, repl.render_status):
                self.assertIn(repl.fuel_readout(s), output(view, s))
            self.assertIn(repl.fuel_readout(s), presenter.build_power_lines(s)[0])
            self.assertIn('ENG-R1', output(repl.render_diag, s, 'engines'))
            self.assertIn('consumo de antimateria' if locale == Locale.ES else 'antimatter consumption',
                          output(repl.render_module_inspect, s, UPGRADE))
            with patch('builtins.input', return_value='s' if locale == Locale.ES else 'y'):
                self.assertIn(expected, output(repl._confirm_nav, s, Travel(node_id=target)))
            lines = []
            harness = SimpleNamespace(loop=SimpleNamespace(state=s), _log_line=lines.append)
            RetornoTextualApp._confirm_nav_needed(harness, s, Travel(node_id=target))
            self.assertIn(expected, lines)
            for reason in ('engines_unavailable', 'insufficient_antimatter'):
                if reason == 'engines_unavailable':
                    s.ship.systems['engines'].forced_offline = True
                else:
                    s.ship.systems['engines'].forced_offline = False
                    s.ship.antimatter_capsules = 0.0
                ev = self.engine.apply_action(s, Travel(node_id=target))
                rendered = output(repl.render_events, s, ev)
                self.assertIn('bloqueado' if locale == Locale.ES else 'blocked', rendered)
                self.assertIn('engines' if reason == 'engines_unavailable' else ('antimateria' if locale == Locale.ES else 'antimatter'), rendered)
            s.ship.antimatter_capsules = 12.0

    def test_09_no_disclosure_or_query_mutation(self):
        target = self.destination()
        s = self.state
        secret = self.destination(3, 'UNOBSERVED_SECRET')
        s.world.known_nodes.discard(secret)
        s.world.known_contacts.discard(secret)
        s.world.known_links[s.world.current_node_id].discard(secret)
        before = pickle.dumps(s)
        self.assertIsNone(self.engine.estimate_travel_fuel(s, secret))
        self.assertEqual(repl.fuel_readout(s, secret), '')
        a = output(repl.render_nav_routes, s)
        self.assertNotIn(secret, a)
        self.assertEqual(pickle.dumps(s), before)
        changed = deepcopy(s)
        changed.world.space.nodes[secret].x_ly += 100000
        changed.world.space.nodes[secret].name = 'CHANGED_SECRET'
        changed.world.space.nodes[secret].links.add('HIDDEN_ROUTE')
        self.assertEqual(output(repl.render_nav_routes, changed), a)
        # A known contact without an acquired route has no fuel quote.
        s.world.known_nodes.add(secret)
        self.assertIsNone(self.engine.estimate_travel_fuel(s, secret))
        self.assertIsNotNone(self.engine.estimate_travel_fuel(s, target))

    def test_10_old_saves_not_migrated_and_manual_pairs(self):
        s = self.state
        del s.ship.systems['engines']
        with TemporaryDirectory() as folder:
            with self.assertRaises(SaveLoadError):
                save_single_slot(s, Path(folder) / 'invalid.dat')
        manuals = Path(__file__).resolve().parents[1] / 'data/manuals'
        for stem in ('systems/engines', f'modules/{UPGRADE}'):
            for lang in ('en','es'):
                self.assertTrue((manuals / f'{stem}.{lang}.txt').is_file())
        info = load_modules()[UPGRADE]
        self.assertEqual(info['effects']['engine_fuel_mult'], .8)
        self.assertTrue(info['desc_en'] and info['desc_es'])
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            for topic in ('engines', UPGRADE):
                manual = output(repl.render_man, self.state, topic)
                self.assertIn(topic, manual)
                self.assertNotIn('No manual found', manual)

    def test_12_textual_input_quotes_cancellation_departure_and_abort(self):
        from textual.widgets import Input
        target = self.destination()

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

                cost = self.engine.estimate_travel_fuel(s, target)
                await command('inventory')
                await command('nav map routes')
                self.assertTrue(any(repl.fuel_readout(s, target) in line for line in app._log_buffer))
                await command('nav ' + target)
                await command('n')
                self.assertFalse(s.ship.in_transit)
                self.assertEqual(s.ship.antimatter_capsules, 12.0)
                await command('nav ' + target)
                await command('s' if locale == Locale.ES else 'y')
                self.assertTrue(s.ship.in_transit)
                self.assertEqual(s.ship.antimatter_capsules, 12.0 - cost)
                await command('nav abort')
                await command('s' if locale == Locale.ES else 'y')
                self.assertFalse(s.ship.in_transit)
                self.assertEqual(s.ship.antimatter_capsules, 12.0 - cost)

        with TemporaryDirectory() as folder:
            for locale in (Locale.EN, Locale.ES):
                asyncio.run(check(locale, Path(folder) / f'{locale.value}.dat'))


if __name__ == '__main__':
    unittest.main()
