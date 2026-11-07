"""Regression: time advancement must not revalidate the installed catalogue."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli.repl import _execute_hibernate
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.io.save_load import SaveLoadError, load_single_slot, save_single_slot
from retorno.runtime.loop import GameLoop
from retorno.worldgen import narrative


class TimeAdvancePerformanceTests(unittest.TestCase):
    def test_wait_keeps_one_second_ticks_without_catalogue_validation(self):
        state = create_initial_state_prologue()
        loop = GameLoop(Engine(), state)
        start = state.clock.t
        # Count expensive work instead of relying on machine-dependent timings.
        with patch.object(narrative, "collect_catalog", side_effect=AssertionError("catalogue reread")):
            with patch.object(loop.engine, "tick", wraps=loop.engine.tick) as tick:
                loop.step_many(3000)
        self.assertEqual(state.clock.t, start + 3000)
        self.assertEqual(tick.call_count, 3000)
        self.assertTrue(all(call.args[1] == 1.0 for call in tick.call_args_list))

    def test_full_hibernation_without_catalogue_validation(self):
        state = create_initial_state_sandbox()
        loop = GameLoop(Engine(), state)
        loop.set_auto_tick(False)
        start = state.clock.t
        with patch.object(narrative, "collect_catalog", side_effect=AssertionError("catalogue reread")):
            result = _execute_hibernate(loop, 15.23)
        self.assertFalse(result.woke_early)
        self.assertAlmostEqual(result.actual_years, 15.23)
        self.assertAlmostEqual(state.clock.t, start + 15.23 * Balance.YEAR_S)
        self.assertFalse(state.ship.is_hibernating)
        self.assertFalse(loop._auto_tick_enabled)

    def test_save_and_load_still_reject_catalogue_changes(self):
        state = create_initial_state_prologue()
        changed = narrative.collect_catalog()
        changed["texts"]["synthetic_regression_probe"] = "changed"
        with TemporaryDirectory(prefix="retorno-time-advance-") as directory:
            slot = Path(directory) / "save.dat"
            save_single_slot(state, slot)
            self.assertIsNotNone(load_single_slot(slot))
            original = slot.read_bytes()
            with patch.object(narrative, "collect_catalog", return_value=changed):
                with self.assertRaises(SaveLoadError):
                    save_single_slot(state, slot)
                with self.assertRaises(SaveLoadError):
                    load_single_slot(slot)
            self.assertEqual(slot.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
