"""T-04A: engine state, independent modules and inertial transit via public flows."""
from contextlib import redirect_stdout
from copy import deepcopy
import asyncio
import csv
import io
import math
import os
from pathlib import Path
import pickle
import random
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rich.console import Console
from rich.style import Style

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import ParseError, format_parse_error, parse_command
from retorno.config.balance import Balance
from retorno.core.actions import EngineSpeed, PowerPlan, PowerShed, Repair, SystemOn, Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.core.temporal import proper_time_interval
from retorno.io.save_load import SaveLoadError, load_single_slot, save_single_slot
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.runtime.data_loader import load_modules
from retorno.ui_textual import presenter
from retorno.ui_textual.app import RetornoTextualApp
from retorno.ui_theme import get_theme_palette, render_rich_line, theme_presets
from retorno.cli.location_ids import public_node_id
from retorno.worldgen.generator import _pick_modules, universe_definition

SPEED = 'engine_speed_upgrade_01'
EFFICIENCY = 'engine_efficiency_upgrade_01'


def output(function, *args):
    with redirect_stdout(io.StringIO()) as stream:
        function(*args)
    return stream.getvalue()


def balance_matrix_rows():
    """Deterministic estimates: fixed CRUISE, Q=1, no brownout/radiation/repairs."""
    engine = Engine()
    initial = create_initial_state_sandbox(seed=29)
    profiles = ((.9, False, False), (.9, False, True), (.9, True, False),
                (.9, True, True), (.7, True, False), (.5, True, True))
    rows = []
    for distance in (2, 10, 20):
        for health, speed_module, efficiency in profiles:
            profile = deepcopy(initial)
            profile.ship.systems['engines'].health = health
            profile.ship.installed_modules = ([SPEED] if speed_module else []) + ([EFFICIENCY] if efficiency else [])
            maximum = profile.ship.maximum_cruise_speed()
            for beta in sorted({.1, .3, maximum}):
                s = deepcopy(profile)
                engine.apply_action(s, EngineSpeed(target=beta))
                assert s.ship.effective_cruise_speed() == beta
                cost = engine.engine_fuel_cost(s, distance)
                galactic = distance/beta*Balance.YEAR_S
                proper = proper_time_interval(galactic, beta)
                s.ship.in_transit, s.ship.op_mode = True, 'CRUISE'
                s.ship.hull_integrity = 1
                engine._apply_hull_degradation(s, proper, 0)
                engine._apply_degradation(s, proper, 1, False, 0)
                final = s.ship.systems['engines']
                rows.append(dict(distance_ly=distance, health=health, speed_upgrade=speed_module,
                    efficiency_upgrade=efficiency, target_c=beta, maximum_c=maximum,
                    fuel_capsules=cost, galactic_years=galactic/Balance.YEAR_S,
                    ship_years=proper/Balance.YEAR_S, engine_wear=health-final.health,
                    hull_wear=1-s.ship.hull_integrity, engine_health_after=final.health,
                    engine_state_after=final.state.value))
    return rows


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
                    if SPEED in installed:
                        if expected_state == SystemState.NOMINAL:
                            expected_state, speed = SystemState.UPGRADED, .8
                        elif expected_state == SystemState.LIMITED:
                            speed = .6
                        elif expected_state == SystemState.DAMAGED:
                            speed = .4
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
        self.assertAlmostEqual(ship.effective_cruise_speed(), .8)
        ship.cruise_speed_ly_per_year = .8
        self.assertGreater(ship.effective_cruise_speed(), 0)
        self.assertLess(ship.effective_cruise_speed(), 1)
        self.assertNotIn('available speed=1.0c', repl.speed_readout(self.state))
        with patch.object(Balance, 'ENGINE_SPEED_UPGRADE_MULTIPLIERS', {'upgraded': .75}):
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
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original_fuel * 2.2)
        self.assertEqual(self.system.p_effective_kw(), original_power)
        self.module_job('install', SPEED)
        self.assertEqual(s.ship.installed_modules.count(SPEED), 2)
        self.assertEqual(s.ship.effective_cruise_speed(), .8)
        self.module_job('install', EFFICIENCY)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original_fuel * 2.2 * .8)
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
        for health, module, beta in ((.9, False, .5), (.7, True, .6), (.5, True, .4), (.9, True, .8)):
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
        # Accelerated fixture wear is now per onboard second (T-04B2).
        self.system.base_decay_per_s = .01 / proper_time_interval(1, .8)
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
        self.assertEqual(output(repl.render_engines_speed, other), output(repl.render_engines_speed, s))
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
            self.assertIn('0.4c', expected)
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
            self.assertIn('engines speed [max|0.1..0.8]', output(repl.print_help, locale.value))
            manual = output(repl.render_man, s, 'engine_speed')
            self.assertIn('Propósito' if locale == Locale.ES else 'Purpose', manual)
            self.assertIn('0.7c: 1.65', manual)
            self.assertIn('engines speed max', manual)
            quote = repl.nav_confirmation(s, Travel(node_id=target))[0][1]
            with patch('builtins.input', return_value='s' if locale == Locale.ES else 'y'):
                self.assertIn(quote, output(repl._confirm_nav, s, Travel(node_id=target)))
            lines = []
            harness = SimpleNamespace(loop=SimpleNamespace(state=s), _log_line=lines.append)
            RetornoTextualApp._confirm_nav_needed(harness, s, Travel(node_id=target))
            self.assertIn(quote, lines)

    def test_speed_command_parsing_default_and_rejections_en_es(self):
        self.assertIsNone(self.state.ship.target_cruise_speed)
        self.assertEqual(parse_command('engines speed'), ('ENGINES_SPEED',))
        self.assertEqual(parse_command('engines speed max').target, None)
        for beta in Balance.ENGINE_SPEED_FUEL_MULTIPLIERS:
            self.assertEqual(parse_command(f'engines speed {beta}').target, beta)
        for command in ('engines', 'engines other', 'engines speed .15', 'engines speed 0',
                        'engines speed 1', 'engines speed nan', 'engines speed inf',
                        'engines speed -0.3', 'engines speed 0.3 extra'):
            with self.subTest(command=command), self.assertRaises(ParseError) as error:
                parse_command(command)
            for locale in ('en', 'es'):
                self.assertIn('engines speed', format_parse_error(error.exception, locale))
        events = self.engine.apply_action(self.state, EngineSpeed(target=.15))
        self.assertEqual(events[0].data['reason'], 'engine_speed_invalid')
        self.assertIsNone(self.state.ship.target_cruise_speed)
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            blocked = 'Velocidad bloqueada' if locale == Locale.ES else 'Speed blocked'
            self.assertIn(blocked, output(repl.render_events, self.state, events))
            self.assertIn(blocked, output(repl.render_logs, self.state))
        selected = self.engine.apply_action(self.state, EngineSpeed(target=.3))
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            label = 'Objetivo de velocidad' if locale == Locale.ES else 'Target speed'
            self.assertIn(label, output(repl.render_events, self.state, selected))
            self.assertIn(label, output(repl.render_logs, self.state))
            self.assertEqual(set(repl._ENGINE_SPEED_MESSAGES),
                             {key for key, translations in repl._ENGINE_SPEED_MESSAGES.items()
                              if set(translations) == {'en', 'es'}})

    def test_fixed_target_blocks_after_damage_and_recovers_after_real_repair(self):
        s = self.state
        target = self.destination()
        self.engine.apply_action(s, parse_command('engines speed 0.5'))
        self.system.health = .7
        self.refresh()
        before = pickle.dumps((s.ship, s.world, s.meta.rng_counter))
        events = self.engine.apply_action(s, Travel(node_id=target))
        self.assertEqual(events[0].data['reason'], 'engine_speed_exceeds_max')
        self.assertEqual(pickle.dumps((s.ship, s.world, s.meta.rng_counter)), before)
        self.assertEqual(s.ship.target_cruise_speed, .5)
        self.assertIsNone(self.engine.estimate_travel_fuel(s, target))
        self.assertIsNone(self.engine.estimate_travel_duration(s, target))
        drone = s.ship.drones['D1']
        drone.status, drone.battery = DroneStatus.DEPLOYED, 1
        drone.location = DroneLocation(kind='ship_sector', id='ENG-R1')
        s.ship.cargo_scrap = 100
        events = self.engine.apply_action(s, Repair(drone_id='D1', system_id='engines'))
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in events))
        with patch.object(Balance, 'REPAIR_JOB_FAIL_P_BASE', 0):
            self.engine.tick(s, Balance.REPAIR_TIME_S + 2)
        self.assertEqual(s.ship.effective_cruise_speed(), .5)
        self.assertEqual(s.ship.target_cruise_speed, .5)
        self.engine.apply_action(s, Travel(node_id=target))
        self.assertEqual(s.ship.transit_speed_ly_per_year, .5)

    def test_fixed_target_module_removal_reinstall_and_no_silent_lowering(self):
        s = self.state
        s.ship.cargo_modules = [SPEED]
        self.module_job('install', SPEED)
        self.engine.apply_action(s, parse_command('engines speed 0.8'))
        self.module_job('uninstall', SPEED)
        self.assertEqual(s.ship.target_cruise_speed, .8)
        self.assertEqual(s.ship.maximum_cruise_speed(), .5)
        self.assertEqual(s.ship.effective_cruise_speed(), 0)
        events = self.engine.apply_action(s, parse_command('engines speed 0.6'))
        self.assertEqual(events[0].data['reason'], 'engine_speed_exceeds_max')
        self.assertEqual(s.ship.target_cruise_speed, .8)
        self.module_job('install', SPEED)
        self.assertEqual(s.ship.effective_cruise_speed(), .8)
        self.system.health = .7
        self.refresh()
        self.assertEqual(s.ship.maximum_cruise_speed(), .6)
        self.assertEqual(s.ship.effective_cruise_speed(), 0)
        self.engine.apply_action(s, parse_command('engines speed max'))
        self.assertIsNone(s.ship.target_cruise_speed)
        self.assertEqual(s.ship.effective_cruise_speed(), .6)
        self.system.health = .2
        self.refresh()
        self.assertEqual(s.ship.maximum_cruise_speed(), 0)
        self.engine.apply_action(s, parse_command('engines speed max'))
        self.assertIsNone(s.ship.target_cruise_speed)

    def test_both_modules_are_independent_at_fixed_speed(self):
        s = self.state
        self.engine.apply_action(s, parse_command('engines speed 0.3'))
        original = self.engine.engine_fuel_cost(s, 10)
        s.ship.cargo_modules = [SPEED, EFFICIENCY]
        self.module_job('install', SPEED)
        self.assertEqual(s.ship.effective_cruise_speed(), .3)
        self.assertEqual(s.ship.maximum_cruise_speed(), .8)
        self.assertEqual(self.engine.engine_fuel_cost(s, 10), original)
        self.module_job('install', EFFICIENCY)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original*.8)
        self.module_job('uninstall', SPEED)
        self.assertEqual(s.ship.effective_cruise_speed(), .3)
        self.assertAlmostEqual(self.engine.engine_fuel_cost(s, 10), original*.8)

    def test_all_selectable_speeds_quote_debit_duration_and_proper_time(self):
        target = self.destination()
        base = self.engine.engine_fuel_cost(self.state, 4, .5)
        for beta, factor in Balance.ENGINE_SPEED_FUEL_MULTIPLIERS.items():
            with self.subTest(beta=beta):
                s = deepcopy(self.state)
                s.ship.installed_modules = [SPEED]
                self.engine.apply_action(s, parse_command(f'engines speed {beta}'))
                quote = self.engine.estimate_travel_fuel(s, target)
                self.assertAlmostEqual(quote, base*factor)
                duration = self.engine.estimate_travel_duration(s, target)
                self.assertAlmostEqual(duration, 4/beta*Balance.YEAR_S)
                events = self.engine.apply_action(s, Travel(node_id=target))
                start = next(e for e in events if e.type == EventType.TRAVEL_STARTED)
                self.assertEqual(start.data['fuel_cost'], quote)
                self.assertEqual(s.ship.antimatter_capsules, 12-quote)
                self.assertEqual(s.ship.transit_speed_ly_per_year, beta)
                self.engine.tick(s, 100)
                self.assertAlmostEqual(s.clock.ship_elapsed_s, proper_time_interval(100, beta))
                self.assertEqual(s.ship.antimatter_capsules, 12-quote)
        self.assertEqual(self.state.ship.cruise_speed_ly_per_year, .5)

    def test_in_transit_queries_pure_changes_rejected_and_selection_persisted(self):
        s = self.state
        target = self.destination()
        self.engine.apply_action(s, parse_command('engines speed 0.3'))
        self.engine.apply_action(s, Travel(node_id=target))
        eta, fuel = s.ship.arrival_t, s.ship.antimatter_capsules
        for command in ('engines speed max', 'engines speed 0.1'):
            before = pickle.dumps((s.ship, s.clock, s.meta.rng_counter))
            events = self.engine.apply_action(s, parse_command(command))
            self.assertEqual(events[0].data['reason'], 'engine_speed_in_transit')
            self.assertEqual(pickle.dumps((s.ship, s.clock, s.meta.rng_counter)), before)
        self.system.health = .2
        self.refresh()
        for locale in (Locale.EN, Locale.ES):
            s.os.locale = locale
            before = pickle.dumps(s)
            self.assertEqual(presenter.build_command_output(repl.render_engines_speed, s),
                             output(repl.render_engines_speed, s).strip().splitlines())
            self.assertEqual(pickle.dumps(s), before)
        with TemporaryDirectory() as folder:
            slot = Path(folder)/'target.dat'
            save_single_slot(s, slot)
            loaded = load_single_slot(slot).state
        self.assertEqual(loaded.ship.target_cruise_speed, .3)
        self.assertEqual(loaded.ship.effective_cruise_speed(), 0)
        self.assertEqual(loaded.ship.transit_speed_ly_per_year, .3)
        self.assertEqual(loaded.ship.arrival_t, eta)
        self.engine.tick(loaded, 100)
        self.assertAlmostEqual(loaded.clock.ship_elapsed_s, proper_time_interval(100, .3))
        self.engine.apply_action(loaded, TravelAbort())
        self.assertEqual(loaded.ship.antimatter_capsules, fuel)
        self.engine.apply_action(loaded, parse_command('engines speed max'))
        self.assertIsNone(loaded.ship.target_cruise_speed)

    def test_local_travel_ignores_invalid_interstellar_target_and_remains_free(self):
        s = self.state
        target = self.destination(local=True)
        s.ship.installed_modules = [SPEED]
        self.engine.apply_action(s, parse_command('engines speed 0.8'))
        s.ship.installed_modules.clear()
        s.ship.antimatter_capsules = 0
        self.refresh()
        self.assertEqual(s.ship.effective_cruise_speed(), 0)
        self.assertEqual(self.engine.estimate_travel_fuel(s, target), 0)
        self.assertEqual(self.engine.estimate_travel_duration(s, target), 1000)
        self.engine.apply_action(s, Travel(node_id=target))
        self.assertTrue(s.ship.last_travel_is_local)
        self.assertEqual(s.ship.arrival_t-s.clock.t, 1000)
        self.assertEqual(s.ship.antimatter_capsules, 0)

    def test_real_cli_engine_speed_dispatch_en_es_and_completion(self):
        from retorno.audio.config import AudioConfigError
        for locale in (Locale.EN, Locale.ES):
            s = deepcopy(self.state)
            s.os.locale = locale
            s.os.debug_enabled = True
            s.os.audio.enabled = False
            commands = iter(('engines speed 0.3', 'engines speed', 'engines speed max', 'exit'))
            callback, buffer = [], ['engines speed ']
            with TemporaryDirectory() as folder, \
                 patch.dict(os.environ, {'RETORNO_NEW_GAME':'0', 'RETORNO_SCENARIO':'prologue'}), \
                 patch.object(sys, 'argv', ['retorno', '--save-path', str(Path(folder)/'cli.dat')]), \
                 patch.object(repl, 'load_single_slot', return_value=SimpleNamespace(state=s,source='main',path='fixture')), \
                 patch.object(repl, 'run_console_entry_gate'), \
                 patch.object(repl, 'AudioManager', side_effect=AudioConfigError('controlled test')), \
                 patch.object(repl.readline, 'set_completer', side_effect=callback.append), \
                 patch.object(repl.readline, 'get_line_buffer', side_effect=lambda:buffer[0]), \
                 patch('builtins.input', side_effect=lambda prompt:next(commands)):
                rendered = output(repl.main)
                completions = [callback[0]('', i) for i in range(6)]
            self.assertIn('0.3c', rendered)
            self.assertIsNone(s.ship.target_cruise_speed)
            self.assertEqual(completions, ['max','0.1','0.2','0.3','0.4','0.5'])
            self.assertIn('Objetivo' if locale==Locale.ES else 'Target', rendered)

    def test_deterministic_balance_matrix_uses_existing_prices_clocks_and_wear(self):
        rows = balance_matrix_rows()
        self.assertEqual(rows, balance_matrix_rows())
        self.assertEqual(len(rows), 54)
        self.assertEqual({row['distance_ly'] for row in rows}, {2,10,20})
        row = next(row for row in rows if row['distance_ly']==10 and row['health']==.9
                   and not row['speed_upgrade'] and not row['efficiency_upgrade'] and row['target_c']==.1)
        self.assertAlmostEqual(row['fuel_capsules'], .45675)
        self.assertAlmostEqual(row['galactic_years'], 100)
        self.assertAlmostEqual(row['ship_years'], proper_time_interval(100, .1))
        self.assertGreater(row['engine_wear'], 0)
        self.assertTrue(any(row['engine_state_after']=='offline' for row in rows))

    def test_compact_nav_confirmation_max_explicit_public_id_and_full_precision(self):
        scope = universe_definition(self.state).scope
        target = self.destination(ident=f'S+000_+000_+000:WG1_{scope}_987')
        alias = public_node_id(self.state, target)
        for locale in (Locale.EN, Locale.ES):
            for selection in (None, .3):
                with self.subTest(locale=locale, selection=selection):
                    s = deepcopy(self.state)
                    s.os.locale = locale
                    s.ship.target_cruise_speed = selection
                    before, rng = pickle.dumps(s), random.getstate()
                    action = Travel(node_id=target)
                    lines, prompt = repl.nav_confirmation(s, action)
                    self.assertEqual(len(lines), 3)
                    self.assertEqual(lines[0], ('Destino: ' if locale == Locale.ES else 'Destination: ') + alias)
                    self.assertNotIn(target, '\n'.join(lines))
                    self.assertIn('MAX (0.5c)' if selection is None else '0.3c', lines[1])
                    self.assertIn('ETA galáctica' if locale == Locale.ES else 'Galactic ETA', lines[1])
                    cost = self.engine.estimate_travel_fuel(s, target)
                    self.assertIn(f'~{cost:.3f}', lines[2])
                    self.assertIn(f'12.000 → ~{12-cost:.3f}', lines[2])
                    self.assertEqual(prompt, '¿Iniciar viaje? [s/N]' if locale == Locale.ES else 'Start travel? [y/N]')
                    for reply, accepted in [('n', False), ('s' if locale == Locale.ES else 'y', True)]:
                        with patch('builtins.input', return_value=reply) as read:
                            with redirect_stdout(io.StringIO()) as stream:
                                self.assertEqual(repl._confirm_nav(s, action), accepted)
                        self.assertEqual(stream.getvalue().strip().splitlines(), lines)
                        self.assertEqual(read.call_args.args[0], prompt + ' ')
                        self.assertEqual(pickle.dumps(s), before)
                    log = []
                    harness = SimpleNamespace(loop=SimpleNamespace(state=s), _log_line=log.append)
                    RetornoTextualApp._confirm_nav_needed(harness, s, action)
                    self.assertEqual(log, [*lines, prompt])
                    self.assertEqual(pickle.dumps(s), before)
                    self.assertEqual(random.getstate(), rng)
                    self.engine.apply_action(s, action)
                    self.assertTrue(s.ship.in_transit)
                    self.assertEqual(s.ship.antimatter_capsules, 12-cost)

    def test_compact_local_confirmation_invalid_unknown_and_drone_warning(self):
        target = self.destination(local=True)
        self.state.world.fine_ranges_km[target] = 30_000
        self.state.ship.target_cruise_speed = .8  # Invalid interstellar target, valid local maneuver.
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            lines, prompt = repl.nav_confirmation(self.state, Travel(node_id=target))
            self.assertIn('20 km/s | ETA: 25m 0s', lines[1])
            self.assertEqual(lines[2], 'Antimateria: 0 cápsulas' if locale == Locale.ES else 'Antimatter: 0 capsules')
            self.assertNotIn('MAX', '\n'.join(lines))
            self.assertNotIn('WARNING', prompt)
        target = self.destination(ident='INTERSTELLAR')
        lines, _ = repl.nav_confirmation(self.state, Travel(node_id=target))
        self.assertIn('—', lines[1])
        self.assertIn('Salida bloqueada', lines[-1])
        self.state.ship.target_cruise_speed = None
        self.state.ship.antimatter_capsules = .1
        self.assertIn('Combustible insuficiente', repl.nav_confirmation(self.state, Travel(node_id=target))[0])
        self.state.ship.antimatter_capsules = 12
        secret = self.destination(ident='SECRET_PREVIEW')
        self.state.world.known_nodes.discard(secret)
        self.state.world.known_contacts.discard(secret)
        self.state.world.known_links[self.state.world.current_node_id].discard(secret)
        first = repl.nav_confirmation(self.state, Travel(node_id=secret))
        self.state.world.space.nodes[secret].name = 'Hidden changed name'
        self.state.world.space.nodes[secret].x_ly += 100_000
        self.assertEqual(repl.nav_confirmation(self.state, Travel(node_id=secret)), first)
        self.assertNotIn('Hidden changed name', str(first))
        drone = self.state.ship.drones['D1']
        drone.status, drone.location = DroneStatus.DEPLOYED, DroneLocation(kind='world_node', id=self.state.world.current_node_id)
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            before = pickle.dumps(self.state)
            lines, prompt = repl.nav_confirmation(self.state, Travel(node_id=target))
            self.assertTrue(prompt.startswith('ADVERTENCIA:' if locale == Locale.ES else 'WARNING:'))
            self.assertIn('abandonados' if locale == Locale.ES else 'abandoned', prompt)
            self.assertIn('D1', prompt)
            with patch('builtins.input', return_value='n'), redirect_stdout(io.StringIO()):
                self.assertFalse(repl._confirm_nav(self.state, Travel(node_id=target)))
            self.assertEqual(pickle.dumps(self.state), before)

    def test_compact_engine_query_invalid_target_frozen_speed_and_local_transit(self):
        s = self.state
        for locale in (Locale.EN, Locale.ES):
            s.os.locale = locale
            s.ship.target_cruise_speed = None
            self.system.health = .9
            text = output(repl.render_engines_speed, s)
            self.assertEqual(len(text.strip().splitlines()), 2)
            self.assertIn('NOMINAL |', text)
            self.assertIn('MAX (0.5c)', text)
            self.assertIn('Manual: man engines', text)
            s.ship.target_cruise_speed = .5
            self.system.health = .5
            before = pickle.dumps(s)
            text = output(repl.render_engines_speed, s)
            self.assertIn('DAMAGED |', text)
            self.assertIn('0.3c', text)
            self.assertIn('Objetivo: 0.5c | SALIDA BLOQUEADA' if locale == Locale.ES else
                          'Target: 0.5c | DEPARTURE BLOCKED', text)
            self.assertEqual(pickle.dumps(s), before)
            s.ship.in_transit, s.ship.transit_speed_ly_per_year = True, .8
            for local in (False, True):
                s.ship.last_travel_is_local = local
                before = pickle.dumps(s)
                text = output(repl.render_engines_speed, s)
                self.assertIn('20 km/s' if local else '0.8c', text)
                self.assertIn('(fija)' if locale == Locale.ES else '(fixed)', text)
                self.assertNotIn('NORMAL', text)
                self.assertNotIn('CRUISE', text)
                self.assertNotIn('nominal=', text)
                self.assertNotIn('Manual:', text)
                self.assertEqual(pickle.dumps(s), before)
            s.ship.in_transit = False

    def test_compact_nav_and_engine_colors_all_themes_en_es(self):
        target = self.destination()
        console = Console()
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            confirmation, prompt = repl.nav_confirmation(self.state, Travel(node_id=target))
            query = output(repl.render_engines_speed, self.state).strip().splitlines()
            for preset in theme_presets():
                with self.subTest(locale=locale, preset=preset):
                    palette = get_theme_palette(preset)
                    for line in [*confirmation, *query]:
                        rich = render_rich_line(line, preset)
                        self.assertEqual(rich.get_style_at_offset(console, 0), Style.parse(palette.foreground))
                        if target in line:
                            self.assertEqual(rich.get_style_at_offset(console, line.index(target)), Style.parse(f'bold {palette.accent}'))
                        if 'NOMINAL' in line:
                            self.assertEqual(rich.get_style_at_offset(console, line.index('NOMINAL')), Style.parse(f'bold {palette.ok}'))
                        for token in ('MAX', '12.000', '0.5c', 'ETA:', 'Manual:'):
                            if token in line:
                                self.assertEqual(rich.get_style_at_offset(console, line.index(token)), Style.parse(palette.foreground))
                    for legacy in (repl.fuel_readout(self.state), repl.speed_readout(self.state)):
                        self.assertEqual(render_rich_line(legacy, preset).get_style_at_offset(console, 0),
                                         Style.parse(f'bold {palette.accent}'))
                    question = render_rich_line(prompt, preset)
                    automove = render_rich_line('WARNING: auto-move the drone? [y/N]', preset)
                    self.assertEqual(question.get_style_at_offset(console, 0),
                                     automove.get_style_at_offset(console, 0))

    def test_blocked_departure_never_asks_for_confirmation_cli_or_textual(self):
        target = self.destination()
        for locale in (Locale.EN, Locale.ES):
            for cause in ('target', 'critical', 'docked', 'transit', 'power', 'fuel', 'unknown'):
                with self.subTest(locale=locale, cause=cause):
                    s = deepcopy(self.state)
                    s.os.locale = locale
                    if cause == 'target':
                        s.ship.target_cruise_speed = .5
                        s.ship.systems['engines'].health = .5
                    elif cause == 'critical':
                        s.ship.systems['engines'].health = .2
                    elif cause == 'docked':
                        s.ship.docked_node_id = s.world.current_node_id
                    elif cause == 'transit':
                        s.ship.in_transit = True
                    elif cause == 'power':
                        s.ship.power.power_quality = .1
                    elif cause == 'fuel':
                        s.ship.antimatter_capsules = 0
                    else:
                        s.world.known_links[s.world.current_node_id].discard(target)
                    action = Travel(node_id=target)
                    before = pickle.dumps(s)
                    lines, prompt = repl.nav_confirmation(s, action)
                    self.assertIsNone(prompt)
                    with patch('builtins.input') as read, redirect_stdout(io.StringIO()) as stream:
                        self.assertFalse(repl._confirm_nav(s, action))
                    read.assert_not_called()
                    self.assertEqual(stream.getvalue().strip().splitlines(), lines)
                    log = []
                    harness = SimpleNamespace(loop=SimpleNamespace(state=s), _log_line=log.append)
                    self.assertTrue(RetornoTextualApp._confirm_nav_needed(harness, s, action))
                    self.assertIsNone(harness._pending_confirm_action)
                    self.assertEqual(log, lines)
                    self.assertEqual(pickle.dumps(s), before)

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

                await command('engines speed 0.3')
                self.assertEqual(s.ship.target_cruise_speed, .3)
                await command('engines speed')
                self.assertTrue(all(line in app._log_buffer for line in presenter.build_command_output(repl.render_engines_speed, s)))
                before = pickle.dumps(s)
                await command('nav ' + target)
                self.assertEqual(pickle.dumps(s), before)
                self.assertEqual(app._pending_confirm_prompt, '¿Iniciar viaje? [s/N]' if locale == Locale.ES else 'Start travel? [y/N]')
                await command('n')
                self.assertEqual(pickle.dumps(s), before)
                s.ship.target_cruise_speed = .8
                s.ship.systems['engines'].health = .5
                before = pickle.dumps(s)
                await command('nav ' + target)
                self.assertIsNone(app._pending_confirm_action)
                self.assertEqual(pickle.dumps(s), before)
                await command('engines speed 0.3')
                self.assertEqual(s.ship.target_cruise_speed, .3)
                s.ship.systems['engines'].health = .9
                self.assertIn('0.8', app._get_completion_candidates(s, 'engines speed ', ''))
                await command('engines speed max')
                self.assertIsNone(s.ship.target_cruise_speed)
                await command('module inspect ' + SPEED)
                await command('nav map routes')
                label = 'Velocidad' if locale == Locale.ES else 'Speed'
                self.assertTrue(any(f'{label}: 0.8c | ETA:' in line for line in app._log_buffer))
                await command('nav ' + target)
                await command('s' if locale == Locale.ES else 'y')
                self.assertTrue(s.ship.in_transit)
                self.assertEqual(s.ship.transit_speed_ly_per_year, .8)
                eta = s.ship.arrival_t
                await command('engines speed 0.1')
                self.assertIsNone(s.ship.target_cruise_speed)
                await command('engines speed')
                actual = 'En tránsito: 0.8c (fija)' if locale == Locale.ES else 'In transit: 0.8c (fixed)'
                self.assertIn(actual, app._log_buffer)
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
    if '--balance-matrix' in sys.argv:
        rows = balance_matrix_rows()
        path = Path(__file__).resolve().parents[1]/'docs/testing/engine-speed-balance.csv'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({key:format(value, '.12g') if isinstance(value, float) else value
                                 for key,value in row.items()})
        print(path)
    else:
        unittest.main()
