"""Compact route presentation through shared public rendering and theme rules."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import pickle
import random
import re
import unittest
from unittest.mock import patch

from rich.console import Console
from rich.style import Style

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.location_ids import public_node_id
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.ui_textual import presenter
from retorno.ui_theme import (
    ThemedStdout, get_theme_palette, render_rich_line, style_ansi_line, theme_presets,
)
from retorno.worldgen.generator import universe_definition


def output(state):
    with redirect_stdout(io.StringIO()) as stream:
        repl.render_nav_routes(state)
    return stream.getvalue()


class NavRoutesPresentationTests(unittest.TestCase):
    def setUp(self):
        self.state = create_initial_state_sandbox(seed=29)
        self.state.ship.docked_node_id = None
        self.origin = self.state.world.current_node_id
        self.state.world.known_nodes = {self.origin}
        self.state.world.known_links = {self.origin: set()}
        self.engine = Engine()

    def route(self, distance=2.0, ident='ROUTE_TEST', name=None):
        s = self.state
        origin = s.world.space.nodes[self.origin]
        step = distance if origin.x_ly % 10 < 5 else -distance
        s.world.space.nodes[ident] = SpaceNode(
            ident, name or ident, 'station', x_ly=origin.x_ly + step,
            y_ly=origin.y_ly, z_ly=origin.z_ly)
        s.world.known_nodes.add(ident)
        self.assertTrue(add_known_link(s.world, self.origin, ident))
        return ident

    def summary(self, rendered, ident='ROUTE_TEST'):
        lines = rendered.splitlines()
        row = next(i for i, line in enumerate(lines) if f'id={ident} ' in line)
        self.assertTrue(lines[row + 1].startswith(('  Fuel:', '  Combustible:')))
        self.assertFalse(row + 2 < len(lines) and lines[row + 2].startswith('  '))
        return lines[row + 1]

    def test_header_and_one_approximate_estimate_en_es_without_rounding_quotes(self):
        target = self.route(20.155)
        exact_cost = self.engine.estimate_travel_fuel(self.state, target)
        for locale in (Locale.EN, Locale.ES):
            with self.subTest(locale=locale):
                self.state.os.locale = locale
                text = output(self.state)
                self.assertIn('12.000', text)
                self.assertIn('NOMINAL |', text)
                self.assertIn('MAX (0.5c)', text)
                self.assertIn('engines speed <value>', text)
                line = self.summary(text)
                self.assertRegex(line, r'~\d+\.\d{3} (capsules|cápsulas) \| (Speed|Velocidad): 0.5c \| ETA: 40.31[ya]$')
                self.assertNotIn(str(exact_cost), line)
                self.assertEqual(self.engine.estimate_travel_fuel(self.state, target), exact_cost)
                self.assertNotIn('sufficient', line)
                self.assertNotIn('bloqueada', line)
                self.assertEqual(presenter.build_command_output(repl.render_nav_map, self.state, 'routes'),
                                 text.strip().splitlines())
        self.state.ship.target_cruise_speed = .3
        text = output(self.state)
        self.assertIn('Objetivo de crucero: 0.3c |', text)
        self.assertNotIn('MAX', text)
        self.assertIn('Velocidad: 0.3c', self.summary(text))

    def test_insufficient_fuel_uses_exact_threshold_even_if_display_rounds_equal(self):
        self.route()
        self.state.ship.antimatter_capsules = self.engine.estimate_travel_fuel(self.state, 'ROUTE_TEST') - 1e-10
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            text = output(self.state)
            self.assertIn('Combustible insuficiente' if locale == Locale.ES else 'Insufficient fuel', text)
            self.assertNotIn('Departure blocked', text)
            self.assertNotIn('Salida bloqueada', text)

    def test_invalid_fixed_target_preserved_with_maximum_and_no_fake_quote(self):
        self.route()
        self.state.ship.target_cruise_speed = .8
        self.state.ship.systems['engines'].health = .5
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            text = output(self.state)
            self.assertIn('DAMAGED |', text)
            self.assertIn('0.8c (', text)
            self.assertIn('0.3c)', text)
            self.assertIn('no disponible' if locale == Locale.ES else 'unavailable', text)
            line = self.summary(text)
            self.assertEqual(line.count('—'), 3)
            self.assertNotIn('~', line)
            self.assertIn('Salida bloqueada' if locale == Locale.ES else 'Departure blocked', line)
        self.assertEqual(self.state.ship.target_cruise_speed, .8)

    def test_local_speed_and_existing_compact_duration_without_fine_range_mutation(self):
        target = self.route(.001)
        self.state.ship.target_cruise_speed = .8  # Invalid interstellar target does not block local travel.
        for seconds in (12, 1000, 7200, 2 * 86400 + 3660, None):
            for locale in (Locale.EN, Locale.ES):
                with self.subTest(seconds=seconds, locale=locale):
                    self.state.os.locale = locale
                    if seconds is None:
                        self.state.world.fine_ranges_km.pop(target, None)
                    else:
                        self.state.world.fine_ranges_km[target] = seconds * Balance.LOCAL_TRAVEL_SPEED_KM_S
                    before = pickle.dumps(self.state)
                    duration = self.engine.estimate_travel_duration(self.state, target)
                    line = self.summary(output(self.state))
                    self.assertIn('~0.000', line)
                    self.assertIn('20 km/s', line)
                    self.assertIn('ETA: ' + repl._format_eta_short(duration, locale.value), line)
                    self.assertNotIn('blocked', line)
                    self.assertNotIn('bloqueada', line)
                    self.assertEqual(pickle.dumps(self.state), before)

    def test_close_destination_in_another_sector_keeps_interstellar_classification(self):
        s = self.state
        origin = s.world.space.nodes[self.origin]
        origin.x_ly, origin.y_ly, origin.z_ly = 9.9995, 1, 1
        target = self.route(.001)
        s.world.space.nodes[target].x_ly = 10.0005
        s.world.fine_ranges_km[target] = 200
        line = self.summary(output(s))
        self.assertIn('Speed: 0.5c', line)
        self.assertNotIn('km/s', line)
        self.assertNotIn('~0.000', line)

    def test_unavailable_engines_and_other_departure_blocks(self):
        self.route()
        for health in (.2, 0):
            self.state.ship.systems['engines'].health = health
            line = self.summary(output(self.state))
            self.assertEqual(line.count('—'), 3)
            self.assertIn('Departure blocked', line)
        self.state.ship.systems['engines'].health = .9
        for cause in ('docked', 'transit', 'power', 'core_os', 'terminal'):
            s = deepcopy(self.state)
            if cause == 'docked':
                s.ship.docked_node_id = self.origin
            elif cause == 'transit':
                s.ship.in_transit = True
            elif cause == 'power':
                s.ship.power.power_quality = .1
            elif cause == 'core_os':
                s.ship.systems['core_os'].state = SystemState.DAMAGED
            else:
                s.os.terminal_lock = True
            line = self.summary(output(s))
            self.assertIn('Departure blocked', line)
            self.assertIn('ETA:', line)
        s = deepcopy(self.state)
        s.ship.systems['core_os'].state = SystemState.CRITICAL
        s.os.debug_enabled = s.os.debug_god_enabled = True
        self.assertNotIn('Departure blocked', self.summary(output(s)))

    def test_queries_are_pure_and_do_not_reveal_hidden_destinations(self):
        self.route()
        before, rng = pickle.dumps(self.state), random.getstate()
        text = output(self.state)
        self.assertEqual(pickle.dumps(self.state), before)
        self.assertEqual(random.getstate(), rng)
        hidden = deepcopy(self.state)
        hidden.world.space.nodes['SECRET'] = SpaceNode('SECRET', 'Hidden star', 'station', x_ly=1000)
        self.assertEqual(output(hidden), text)
        self.assertEqual(presenter.build_command_output(repl.render_nav_routes, self.state), text.strip().splitlines())

    def test_long_destination_names_public_ids_and_colors_in_all_themes_en_es(self):
        scope = universe_definition(self.state).scope
        target = f'S+000_+000_+000:WG1_{scope}_987'
        name = 'NOMINAL observatory (outer ring): ' + 'Órbita distante ' * 15
        self.route(2, target, name.rstrip())
        alias = public_node_id(self.state, target)
        console = Console()
        for locale in (Locale.EN, Locale.ES):
            self.state.os.locale = locale
            lines = presenter.build_command_output(repl.render_nav_routes, self.state)
            self.assertEqual(lines, output(self.state).strip().splitlines())
            destination = next(line for line in lines if f'id={alias} ' in line)
            self.assertIn(name.rstrip(), destination)
            self.assertNotIn(target, destination)
            for preset in theme_presets():
                with self.subTest(locale=locale, preset=preset):
                    palette = get_theme_palette(preset)
                    for token in (name.rstrip(), alias):
                        start = destination.index(token)
                        rich = render_rich_line(destination, preset)
                        for index in (start, start + len(token) - 1):
                            style = rich.get_style_at_offset(console, index)
                            self.assertEqual(style, Style.parse(f'bold {palette.accent}'))
                    for line in lines:
                        rich = render_rich_line(line, preset)
                        for token in ('Antimatter:', 'Antimateria:', 'Engines:', 'Motores:', 'Fuel:',
                                      'Combustible:', 'Speed:', 'Velocidad:', 'ETA:', 'Set:', 'Configurar:'):
                            if token in line:
                                style = rich.get_style_at_offset(console, line.index(token))
                                self.assertEqual(style, Style.parse(palette.foreground))
                        if line.startswith('===') or line.startswith(('Known routes from ', 'Rutas conocidas desde ')):
                            self.assertEqual(rich.get_style_at_offset(console, 0), Style.parse(f'bold {palette.accent}'))
                        if 'NOMINAL |' in line:
                            self.assertEqual(rich.get_style_at_offset(console, line.index('NOMINAL')),
                                             Style.parse(f'bold {palette.ok}'))
                        stream = io.StringIO()
                        ansi = style_ansi_line(line, preset)
                        with patch.dict('os.environ', {'NO_COLOR': ''}), patch.object(stream, 'isatty', return_value=True):
                            themed = ThemedStdout(stream, lambda: preset)
                            themed.write(line + '\n')
                            themed.flush()
                        self.assertEqual(stream.getvalue(), ansi + '\n')
                        self.assertEqual(re.sub(r'\x1b\[[0-9;]*m', '', ansi), rich.plain)

    def test_theme_semantic_warnings_and_unrelated_formats_remain_unchanged(self):
        console = Console()
        for preset in theme_presets():
            palette = get_theme_palette(preset)
            for line in ('Fuel: other command', 'Antimatter: 12.0 equivalent capsules', 'engines: nominal'):
                rich = render_rich_line(line, preset)
                self.assertEqual(rich.get_style_at_offset(console, 0), Style.parse(f'bold {palette.accent}'))
            line = '- Other contact (station) sector=S+000_+000_+000 id=OTHER'
            rich = render_rich_line(line, preset)
            self.assertEqual(rich.get_style_at_offset(console, 2), Style.parse(palette.foreground))
            for state in ('NOMINAL', 'UPGRADED', 'LIMITED', 'DAMAGED', 'CRITICAL', 'OFFLINE'):
                header = f'Engines: {state} | Cruise target: MAX (0.5c) | Set: engines speed <value>'
                role = 'ok' if state in {'NOMINAL','UPGRADED'} else 'warn' if state in {'LIMITED','DAMAGED'} else 'critical' if state=='CRITICAL' else 'error'
                rich = render_rich_line(header, preset)
                self.assertEqual(rich.get_style_at_offset(console, header.index(state)),
                                 Style.parse(f'bold {getattr(palette, role)}'))
            for line, notice, role in (
                ('  Fuel: — | Speed: — | ETA: — | Departure blocked', 'Departure blocked', 'error'),
                ('  Combustible: ~0.700 cápsulas | Velocidad: 0.5c | ETA: 4.00a | Combustible insuficiente', 'Combustible insuficiente', 'warn'),
            ):
                rich = render_rich_line(line, preset)
                self.assertEqual(rich.get_style_at_offset(console, line.index(notice)),
                                 Style.parse(f'bold {getattr(palette, role)}'))


if __name__ == '__main__':
    unittest.main()
