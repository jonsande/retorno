from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.model.world import sector_id_for_pos
from retorno.worldgen.generator import ensure_sector_generated


def main() -> None:
    parsed = parse_command("debug galaxy")
    assert isinstance(parsed, tuple) and parsed[0] == "DEBUG_GALAXY", parsed
    parsed_map = parse_command("debug galaxy map regional")
    assert parsed_map == ("DEBUG_GALAXY_MAP", "regional"), parsed_map

    state = create_initial_state_sandbox()
    current = state.world.space.nodes[state.world.current_node_id]
    ensure_sector_generated(state, sector_id_for_pos(current.x_ly, current.y_ly, current.z_ly))
    state.os.debug_enabled = True
    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_debug_galaxy(state)
    out = buf.getvalue()
    assert "DEBUG GALAXY" in out
    assert "player:" in out
    assert "current_sector_gen:" in out
    assert "sector_archetypes:" in out
    assert "sector_adjacency:" in out
    assert "sparse_synth[seed]:" in out
    assert "link_cap:" in out

    buf_map = io.StringIO()
    with redirect_stdout(buf_map):
        repl.render_debug_galaxy_map(state, "regional")
    out_map = buf_map.getvalue()
    assert "DEBUG GALAXY MAP" in out_map
    assert "NAV MAP GALAXY" in out_map
    assert "current_sector_archetype:" in out_map
    assert "@" in out_map

    print("DEBUG GALAXY SMOKE PASSED")


if __name__ == "__main__":
    main()
