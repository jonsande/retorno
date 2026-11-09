"""T-03: clock integration without changing existing subsystem time domains."""
from copy import deepcopy
from dataclasses import asdict
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.temporal import proper_time_interval
from retorno.io.save_load import load_single_slot, save_single_slot


class TemporalClockTests(unittest.TestCase):
    def setUp(self):
        self.state = create_initial_state_sandbox()
        self.engine = Engine()

    def transit(self, *, beta=0.5, remaining=1000.0, local=False):
        ship = self.state.ship
        ship.in_transit = True
        ship.transit_from = ship.transit_to = ship.current_node_id
        ship.transit_start_t = self.state.clock.t
        ship.arrival_t = self.state.clock.t + remaining
        ship.transit_speed_ly_per_year = beta
        ship.last_travel_is_local = local

    def test_initial_clocks(self):
        for state in (self.state, create_initial_state_prologue()):
            self.assertEqual(state.clock.t, 0.0)
            self.assertEqual(state.clock.ship_elapsed_s, 0.0)
            self.assertEqual(state.clock.bio_elapsed_s, 0.0)

    def test_rest_awake_including_cruise_mode(self):
        self.state.ship.op_mode = "CRUISE"
        self.engine.tick(self.state, 100.0)
        self.assertEqual(self.state.clock.t, 100.0)
        self.assertEqual(self.state.clock.last_dt, 100.0)
        self.assertEqual(self.state.clock.ship_elapsed_s, 100.0)
        self.assertEqual(self.state.clock.bio_elapsed_s, 100.0)

    def test_rest_hibernating(self):
        self.state.ship.is_hibernating = True
        self.engine.tick(self.state, 100.0)
        self.assertEqual(self.state.clock.t, 100.0)
        self.assertEqual(self.state.clock.ship_elapsed_s, 100.0)
        self.assertEqual(self.state.clock.bio_elapsed_s, 0.5)

    def test_interstellar_speeds(self):
        for beta in (0.3, 0.5, 0.8):
            with self.subTest(beta=beta):
                self.state = create_initial_state_sandbox()
                self.transit(beta=beta)
                # NORMAL mode must still apply the movement factor.
                self.assertEqual(self.state.ship.op_mode, "NORMAL")
                self.engine.tick(self.state, 100.0)
                expected = 100.0 * math.sqrt(1.0 - beta ** 2)
                self.assertEqual(self.state.clock.t, 100.0)
                self.assertAlmostEqual(self.state.clock.ship_elapsed_s, expected)
                self.assertAlmostEqual(self.state.clock.bio_elapsed_s, expected)

    def test_interstellar_hibernating_and_configurable_rate(self):
        self.transit()
        self.state.ship.is_hibernating = True
        self.engine.tick(self.state, 100.0)
        expected = 100.0 * math.sqrt(0.75)
        self.assertAlmostEqual(self.state.clock.bio_elapsed_s, expected * 0.005)
        with patch.object(Balance, "HIBERNATION_BIO_AGE_RATE_NOMINAL", 0.01):
            self.engine.tick(self.state, 100.0)
        self.assertAlmostEqual(self.state.clock.ship_elapsed_s, 2 * expected)
        self.assertAlmostEqual(self.state.clock.bio_elapsed_s, expected * 0.015)

    def test_local_travel_uses_physical_speed(self):
        self.transit(beta=0.8, local=True)
        self.assertEqual(Balance.LOCAL_TRAVEL_SPEED_KM_S, 20.0)
        self.engine.tick(self.state, 100.0)
        expected = 100.0 * math.sqrt(1 - (20.0 / 299_792.458) ** 2)
        self.assertLess(self.state.clock.ship_elapsed_s, 100.0)
        self.assertAlmostEqual(self.state.clock.ship_elapsed_s, expected, places=12)
        self.assertAlmostEqual(self.state.clock.bio_elapsed_s, expected, places=12)

    def test_tick_crosses_arrival(self):
        self.transit(remaining=3 * Balance.DAY_S)
        self.engine.tick(self.state, 10 * Balance.DAY_S)
        expected = (3 * math.sqrt(0.75) + 7) * Balance.DAY_S
        self.assertFalse(self.state.ship.in_transit)
        self.assertEqual(self.state.clock.t, 10 * Balance.DAY_S)
        self.assertAlmostEqual(self.state.clock.ship_elapsed_s, expected)
        self.assertAlmostEqual(self.state.clock.bio_elapsed_s, expected)

    def test_consecutive_ticks_and_wake_transition(self):
        self.transit(beta=0.8)
        self.engine.tick(self.state, 10.0)
        self.state.ship.is_hibernating = True
        self.engine.tick(self.state, 20.0)
        self.state.ship.is_hibernating = False
        self.engine.tick(self.state, 30.0)
        self.assertEqual(self.state.clock.t, 60.0)
        self.assertAlmostEqual(self.state.clock.ship_elapsed_s, 36.0)
        self.assertAlmostEqual(self.state.clock.bio_elapsed_s, 24.06)

    def test_subdivision_without_intermediate_events(self):
        self.transit(beta=0.8)
        self.state.ship.is_hibernating = True
        split = deepcopy(self.state)
        self.engine.tick(self.state, 100.0)
        for _ in range(10):
            self.engine.tick(split, 10.0)
        for name in ("t", "ship_elapsed_s", "bio_elapsed_s"):
            self.assertAlmostEqual(getattr(self.state.clock, name), getattr(split.clock, name))

    def test_arrival_partition_invariance(self):
        self.transit(remaining=30.0)
        split = deepcopy(self.state)
        self.engine.tick(self.state, 100.0)
        self.engine.tick(split, 30.0)
        self.engine.tick(split, 70.0)
        self.assertAlmostEqual(self.state.clock.ship_elapsed_s, split.clock.ship_elapsed_s)
        self.assertAlmostEqual(self.state.clock.bio_elapsed_s, split.clock.bio_elapsed_s)

    def test_invalid_speed_rejected_before_clock_mutation(self):
        for beta in (-0.3, 1.0, 1.1, math.inf, -math.inf, math.nan):
            with self.subTest(beta=beta):
                self.transit(beta=beta)
                before = asdict(self.state.clock)
                with self.assertRaises(ValueError):
                    self.engine.tick(self.state, 1.0)
                self.assertEqual(asdict(self.state.clock), before)
        for beta in (-0.1, 1.0, math.inf, math.nan):
            with self.assertRaises(ValueError):
                proper_time_interval(1.0, beta)

    def test_new_clocks_survive_save_load_and_continue(self):
        self.state.ship.is_hibernating = True
        self.engine.tick(self.state, 100.0)
        self.state.ship.is_hibernating = False
        self.engine.tick(self.state, 20.0)
        with TemporaryDirectory(prefix="retorno-clocks-") as directory:
            slot = Path(directory) / "save.dat"
            save_single_slot(self.state, slot)
            loaded = load_single_slot(slot)
            self.assertIsNotNone(loaded)
            self.assertEqual(asdict(loaded.state.clock), asdict(self.state.clock))
            self.engine.tick(loaded.state, 10.0)
            self.assertEqual(loaded.state.clock.t, 130.0)
            self.assertEqual(loaded.state.clock.ship_elapsed_s, 130.0)
            self.assertEqual(loaded.state.clock.bio_elapsed_s, 30.5)


if __name__ == "__main__":
    unittest.main()
