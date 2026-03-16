from __future__ import annotations

import asyncio
import os

from textual.widgets import Input

from retorno.ui_textual.app import RetornoTextualApp


async def _run() -> None:
    old_scenario = os.environ.get("RETORNO_SCENARIO")
    try:
        os.environ["RETORNO_SCENARIO"] = "sandbox"
        app = RetornoTextualApp(force_new_game=True)
        app.loop.state.os.debug_enabled = True
        app.loop.state.os.audio.enabled = False
        app.loop.state.os.audio.ambient_enabled = False
        app.loop.state.os.theme_preset = "amber"

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._theme_preset == "amber", app._theme_preset

            input_widget = app.query_one("#input", Input)
            input_widget.value = "config set theme ice"
            await pilot.press("enter")
            await pilot.pause()

            assert app._theme_preset == "ice", app._theme_preset
            assert app.loop.state.os.theme_preset == "ice", app.loop.state.os.theme_preset
            assert "Theme set to ice" in app._log_buffer, app._log_buffer[-10:]
    finally:
        if old_scenario is None:
            os.environ.pop("RETORNO_SCENARIO", None)
        else:
            os.environ["RETORNO_SCENARIO"] = old_scenario

    print("TEXTUAL THEME SMOKE PASSED")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
