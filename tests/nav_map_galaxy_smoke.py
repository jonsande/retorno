from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command


def main() -> None:
    parsed_full = parse_command("nav map galaxy")
    assert parsed_full == ("NAV_MAP", "galaxy", None), parsed_full

    parsed_alias = parse_command("nav galaxy")
    assert parsed_alias == ("NAV_MAP", "galaxy", None), parsed_alias

    parsed_scale = parse_command("nav map galaxy local")
    assert parsed_scale == ("NAV_MAP", "galaxy", "local"), parsed_scale

    parsed_alias_scale = parse_command("nav galaxy regional")
    assert parsed_alias_scale == ("NAV_MAP", "galaxy", "regional"), parsed_alias_scale

    state = create_initial_state_prologue()
    for scale in (None, "sector", "local", "regional", "global"):
        buf = io.StringIO()
        with redirect_stdout(buf):
            repl.render_nav_map(state, "galaxy", scale)
        out = buf.getvalue()
        assert "NAV MAP GALAXY" in out, (scale, out)
        assert "@" in out, (scale, out)
        assert ("scale=" in out) or ("escala=" in out), (scale, out)
        if scale in {None, "global"}:
            assert "#" in out and "." in out, (scale, out)
        assert ("legend:" in out) or ("leyenda:" in out), (scale, out)

    print("NAV MAP GALAXY SMOKE PASSED")


if __name__ == "__main__":
    main()
