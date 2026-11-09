"""T-02: ship-owned cruise speed and independent local travel (discoverable)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from retorno.bootstrap import (
    create_initial_state_fast_sandbox,
    create_initial_state_prologue,
    create_initial_state_sandbox,
)
from retorno.config.balance import Balance
from retorno.core.actions import Travel
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.world import SpaceNode, add_known_link


class CruiseSpeedTests(unittest.TestCase):
    def test_new_game_speed(self):
        for factory in (create_initial_state_prologue, create_initial_state_sandbox,
                        create_initial_state_fast_sandbox):
            with self.subTest(factory=factory.__name__):
                self.assertEqual(factory().ship.cruise_speed_ly_per_year, 0.5)

    def start_travel(self, *, local=False, speed=None):
        state = create_initial_state_sandbox()
        if speed is not None:
            state.ship.cruise_speed_ly_per_year = speed
        state.world.space.nodes = {
            "A": SpaceNode("A", "A", "derelict", x_ly=1, y_ly=1, z_ly=1),
            "B": SpaceNode("B", "B", "derelict", x_ly=1.001 if local else 5,
                           y_ly=1, z_ly=1),
        }
        state.world.current_node_id = state.ship.current_node_id = "A"
        state.ship.docked_node_id = None
        state.world.known_nodes = {"A", "B"}
        state.world.known_links = {}
        self.assertTrue(add_known_link(state.world, "A", "B", bidirectional=True))
        state.world.fine_ranges_km = {"B": 20_000.0} if local else {}
        state.clock.t = 1234.5
        events = Engine().apply_action(state, Travel(node_id="B"))
        started = [e for e in events if e.type == EventType.TRAVEL_STARTED]
        self.assertEqual(len(started), 1, events)
        self.assertEqual(state.clock.t, 1234.5)
        return state, started[0]

    def test_four_light_years_take_eight_years(self):
        state, event = self.start_travel()
        self.assertFalse(event.data["local"])
        self.assertEqual(event.data["eta_years"], 8.0)
        self.assertEqual(event.data["eta_s"], 8.0 * Balance.YEAR_S)
        self.assertEqual(state.ship.arrival_t, state.clock.t + 8.0 * Balance.YEAR_S)

    def test_duration_uses_ship_attribute(self):
        state, event = self.start_travel(speed=0.8)
        self.assertEqual(event.data["eta_years"], 5.0)
        self.assertEqual(state.ship.arrival_t, state.clock.t + 5.0 * Balance.YEAR_S)

    def test_local_speed_is_independent(self):
        self.assertEqual(Balance.LOCAL_TRAVEL_SPEED_KM_S, 20.0)
        for speed in (0.5, 0.8):
            with self.subTest(speed=speed):
                state, event = self.start_travel(local=True, speed=speed)
                self.assertTrue(event.data["local"])
                self.assertEqual(event.data["eta_s"], 1000.0)
                self.assertEqual(state.ship.arrival_t, state.clock.t + 1000.0)

    def test_new_game_speed_survives_save_load(self):
        state = create_initial_state_prologue()
        with TemporaryDirectory(prefix="retorno-cruise-speed-") as directory:
            slot = Path(directory) / "save.dat"
            save_single_slot(state, slot)
            loaded = load_single_slot(slot)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.state.ship.cruise_speed_ly_per_year, 0.5)


if __name__ == "__main__":
    unittest.main()
