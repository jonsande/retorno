"""Textual command and presenter smoke for shared physical navigation.

Run with: PYTHONPATH=.:src ../retorno_venv/bin/python tests/textual_nav_d2b1_smoke.py
"""
import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from textual.widgets import Input

from retorno.config.balance import Balance
from retorno.core.nav_physics import LIGHT_YEAR_M
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.ui_textual.app import RetornoTextualApp
from test_nav_public_physical import public_game


async def run() -> None:
    old_scenario = os.environ.get("RETORNO_SCENARIO")
    try:
        os.environ["RETORNO_SCENARIO"] = "sandbox"
        with TemporaryDirectory() as directory:
            app = RetornoTextualApp(force_new_game=True,
                                    save_path=str(Path(directory) / "textual.sav"))
            app.loop.state = public_game(1e6 / LIGHT_YEAR_M)
            app.loop.state.os.debug_enabled = True
            app.loop.state.os.audio.enabled = False
            app.loop.state.os.audio.ambient_enabled = False
            app._play_startup_sequence = False
            app._startup_panel_blackout = False
            Balance.HIBERNATE_SEQUENCE_TYPEWRITER = False
            Balance.HIBERNATE_SEQUENCE_LINE_DELAY_S = 0.0
            Balance.HIBERNATE_SEQUENCE_COUNTDOWN_S = 0
            Balance.HIBERNATE_WAKE_PANEL_BLACKOUT_S = 0.0
            Balance.HIBERNATE_WAKE_SEQUENCE_TYPEWRITER = False
            Balance.HIBERNATE_WAKE_SEQUENCE_LINE_DELAY_S = 0.0
            async with app.run_test() as pilot:
                async def command(line):
                    field = app.query_one("#input", Input)
                    field.value = line
                    await pilot.press("enter")
                    await pilot.pause()

                await command("engines speed 0.5")
                await command("nav NOMINAL_B")
                assert app._pending_confirm_action is not None
                await command("y")
                assert app.loop.state.ship.physical_transit is not None
                await command("status")
                assert any("acceleration" in line for line in app._log_buffer)
                await command("wait 100")
                assert app.loop.state.clock.t >= 101
                save_single_slot(app.loop.state, app._save_path)
                restored = load_single_slot(app._save_path).state
                assert restored.ship.physical_transit == app.loop.state.ship.physical_transit
                app.loop.state = restored
                await command("hibernate until_arrival")
                assert app._pending_confirm_action == "HIBERNATE_START"
                await command("y")
                for _ in range(20):
                    await pilot.pause(.2)
                    if app.loop.state.ship.physical_transit is None:
                        break
                assert app.loop.state.ship.physical_transit is None
                assert app.loop.state.world.current_node_id == "NOMINAL_B"
                await command("status")
                assert any("arrived" in line.lower() for line in app._log_buffer)
    finally:
        if old_scenario is None:
            os.environ.pop("RETORNO_SCENARIO", None)
        else:
            os.environ["RETORNO_SCENARIO"] = old_scenario
    print("TEXTUAL NAV D2B1 SMOKE PASSED")


if __name__ == "__main__":
    asyncio.run(run())
