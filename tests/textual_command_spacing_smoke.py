from __future__ import annotations

import asyncio
import os

from textual.widgets import Input, RichLog

from retorno.ui_textual.app import RetornoTextualApp


async def _run() -> None:
    old_scenario = os.environ.get("RETORNO_SCENARIO")
    try:
        os.environ["RETORNO_SCENARIO"] = "sandbox"
        app = RetornoTextualApp(force_new_game=True)
        app.loop.state.os.debug_enabled = True
        app.loop.state.os.audio.enabled = False
        app.loop.state.os.audio.ambient_enabled = False
        app._play_startup_sequence = False
        app._startup_panel_blackout = False

        async with app.run_test() as pilot:
            app.query_one("#log", RichLog).clear()
            app._log_buffer.clear()
            app._log_line("previous output")
            input_widget = app.query_one("#input", Input)
            input_widget.value = "jobs"
            await pilot.press("enter")
            await pilot.pause()

            command_index = app._log_buffer.index("> jobs")
            assert command_index >= 2, app._log_buffer[:6]
            assert app._log_buffer[command_index - 1] == "", app._log_buffer[max(0, command_index - 3):command_index + 3]
            assert app._log_buffer[command_index - 2] != "", app._log_buffer[max(0, command_index - 3):command_index + 3]
    finally:
        if old_scenario is None:
            os.environ.pop("RETORNO_SCENARIO", None)
        else:
            os.environ["RETORNO_SCENARIO"] = old_scenario

    print("TEXTUAL COMMAND SPACING SMOKE PASSED")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
