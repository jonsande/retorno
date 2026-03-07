from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl


def _render(state, scale: str) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_nav_map(state, "galaxy", scale)
    return buf.getvalue()


def main() -> None:
    state = create_initial_state_prologue()
    for scale in ("sector", "local", "regional", "global"):
        first = _render(state, scale)
        second = _render(state, scale)
        assert first == second, f"map output must be deterministic for scale={scale}"
    print("NAV MAP GALAXY DETERMINISM SMOKE PASSED")


if __name__ == "__main__":
    main()
