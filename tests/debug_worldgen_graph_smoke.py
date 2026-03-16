from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.model.world import sector_id_for_pos


def main() -> None:
    parsed_sector = parse_command("debug worldgen sector S+000_+000_+000")
    assert parsed_sector == ("DEBUG_WORLDGEN_SECTOR", "S+000_+000_+000"), parsed_sector
    parsed_graph = parse_command("debug graph all")
    assert parsed_graph == ("DEBUG_GRAPH_ALL", None), parsed_graph

    state = create_initial_state_sandbox()
    state.os.debug_enabled = True
    current = state.world.space.nodes[state.world.current_node_id]
    sector_id = sector_id_for_pos(current.x_ly, current.y_ly, current.z_ly)

    buf_sector = io.StringIO()
    with redirect_stdout(buf_sector):
        repl.render_debug_worldgen_sector(state, sector_id)
    out_sector = buf_sector.getvalue()
    assert "DEBUG WORLDGEN SECTOR" in out_sector
    assert f"sector={sector_id}" in out_sector
    assert "sector_state: archetype=" in out_sector
    assert "- nodes:" in out_sector
    assert "links_internal:" in out_sector

    buf_graph = io.StringIO()
    with redirect_stdout(buf_graph):
        repl.render_debug_graph_all(state)
    out_graph = buf_graph.getvalue()
    assert "DEBUG GRAPH ALL" in out_graph
    assert "materialized_sectors=" in out_graph
    assert "- sectors:" in out_graph
    assert "- nodes:" in out_graph
    assert "- physical_edges:" in out_graph

    print("DEBUG WORLDGEN/GRAPH SMOKE PASSED")


if __name__ == "__main__":
    main()
