from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command


def main() -> None:
    parsed = parse_command("debug galaxy")
    assert isinstance(parsed, tuple) and parsed[0] == "DEBUG_GALAXY", parsed

    state = create_initial_state_prologue()
    state.os.debug_enabled = True
    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_debug_galaxy(state)
    out = buf.getvalue()
    assert "DEBUG GALAXY" in out
    assert "player:" in out
    assert "sector_adjacency:" in out
    assert "procedural_rad_synth[seed]:" in out

    print("DEBUG GALAXY SMOKE PASSED")


if __name__ == "__main__":
    main()
