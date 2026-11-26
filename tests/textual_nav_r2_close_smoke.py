"""Confirm Textual waits for hibernation work before saving on close.

Run with: PYTHONPATH=.:src:tests ../retorno_venv/bin/python tests/textual_nav_r2_close_smoke.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from retorno.io.save_load import load_single_slot
from retorno.ui_textual.app import RetornoTextualApp


async def run() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "close.sav"
        app = RetornoTextualApp(force_new_game=True, save_path=str(path))
        before = app.loop.state.clock.t

        async def finish_worker() -> None:
            await asyncio.sleep(.05)
            app.loop.state.clock.t += 3

        app._hibernate_worker = asyncio.create_task(finish_worker())
        await app.on_unmount()
        assert app._hibernate_worker.done()
        assert load_single_slot(path).state.clock.t == before + 3


if __name__ == "__main__":
    asyncio.run(run())
    print("TEXTUAL NAV R2 CLOSE SMOKE PASSED")
