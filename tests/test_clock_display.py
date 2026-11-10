"""Public clock displays preserve the three independent time domains."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import os
import unittest
from unittest.mock import patch

from rich.console import Console
from textual.widgets import Static

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.model.os import Locale
from retorno.ui_textual import presenter
from retorno.ui_textual.app import RetornoTextualApp
from retorno.ui_theme import render_rich_line, theme_presets


class ClockDisplayTests(unittest.TestCase):
    def test_independent_values_and_localization_without_mutation(self):
        state = create_initial_state_sandbox()
        state.clock.t = 90061
        state.clock.ship_elapsed_s = 3661
        state.clock.bio_elapsed_s = 61
        for locale, labels, day, year in (
            (Locale.EN, ("G", "S", "P"), "Day", "Y"),
            (Locale.ES, ("G", "S", "P"), "Día", "A"),
        ):
            with self.subTest(locale=locale):
                state.os.locale = locale
                before = deepcopy(state)
                with redirect_stdout(io.StringIO()) as stream:
                    repl.render_status(state)
                status = stream.getvalue()
                self.assertIn(f"{day} 2 01:01:01", status)
                self.assertIn(f"{day} 1 01:01:01", status)
                self.assertIn(f"{day} 1 00:01:01", status)
                self.assertIn("biológico" if locale == Locale.ES else "biological", status)
                header = presenter.build_header(state)
                for label, day_number, time in zip(labels, (2, 1, 1), ("01:01:01", "01:01:01", "00:01:01")):
                    self.assertIn(f"{label}: {year}1 D{day_number} {time}", header)
                self.assertNotIn("T+", header)
                self.assertEqual(status.strip().splitlines(), presenter.build_command_output(repl.render_status, state))
                self.assertEqual(state, before)

    def test_large_year_abbreviations_in_header(self):
        state = create_initial_state_sandbox()
        for locale, prefix in ((Locale.EN, 'Y'), (Locale.ES, 'A')):
            state.os.locale = locale
            for year, expected in ((9999, '9999 D1'), (10000, '10.0k +1d'),
                                   (12500, '12.5k +1d'), (1000000, '1.0M +1d'),
                                   (1000000000, '1.0B +1d')):
                with self.subTest(locale=locale, year=year):
                    seconds = (year - 1) * 365 * 86400
                    state.clock.t = state.clock.ship_elapsed_s = state.clock.bio_elapsed_s = seconds
                    header = presenter.build_header(state)
                    for label in ('G', 'S', 'P'):
                        self.assertIn(f'{label}: {prefix}{expected} 00:00:00', header)
                    self.assertNotIn('T+', header)

    def test_clock_labels_use_power_key_color_in_every_theme(self):
        state = create_initial_state_sandbox()
        for locale in (Locale.EN, Locale.ES):
            state.os.locale = locale
            for preset in theme_presets():
                with self.subTest(locale=locale, preset=preset):
                    header = render_rich_line(presenter.build_header(state), preset)
                    power = render_rich_line(presenter.build_power_lines(state)[0], preset)
                    console = Console()
                    expected = power.get_style_at_offset(console, 0)
                    for label in ('G:', 'S:', 'P:'):
                        actual = header.get_style_at_offset(console, header.plain.index(label))
                        self.assertEqual(actual, expected)


class ClockHeaderLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_header_wraps_to_keep_clocks_visible(self):
        with patch.dict(os.environ, {"RETORNO_SCENARIO": "sandbox"}):
            app = RetornoTextualApp(force_new_game=True)
            app.loop.state.os.audio.enabled = False
            app.loop.state.os.audio.ambient_enabled = False
            app._play_startup_sequence = False
            app._startup_panel_blackout = False
            async with app.run_test(size=(80, 30)) as pilot:
                for locale in (Locale.EN, Locale.ES):
                    app.loop.state.os.locale = locale
                    for width in (40, 80, 160):
                        with self.subTest(locale=locale, width=width):
                            await pilot.resize_terminal(width, 30)
                            app.refresh_panels()
                            await pilot.pause()
                            header = app.query_one("#header", Static)
                            self.assertGreaterEqual(header.size.height, 1)
                            if width == 40:
                                self.assertGreater(header.size.height, 1)
                            self.assertGreater(app.query_one("#input").region.height, 0)


if __name__ == "__main__":
    unittest.main()
