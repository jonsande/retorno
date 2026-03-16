from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.model.world import SpaceNode, add_known_link, region_for_pos, sector_id_for_pos


def _make_node(node_id: str, name: str, x_ly: float) -> SpaceNode:
    return SpaceNode(
        node_id=node_id,
        name=name,
        kind="station",
        radiation_rad_per_s=0.001,
        region=region_for_pos(x_ly, 0.0, 0.0),
        x_ly=x_ly,
        y_ly=0.0,
        z_ly=0.0,
    )


def test_contacts_sector_aliases_parse() -> None:
    assert parse_command("nav map contacts sector") == ("NAV_MAP", "contacts", "sector")
    assert parse_command("nav contacts sector") == ("NAV_MAP", "contacts", "sector")
    assert parse_command("contacts sector") == ("NAV_MAP", "contacts", "sector")


def test_contacts_render_includes_sector_region_and_sector_summary() -> None:
    state = create_initial_state_prologue()

    current_id = "TEST_CUR"
    same_sector_id = "TEST_SAME"
    next_sector_id = "TEST_NEXT"
    far_sector_id = "TEST_FAR"

    state.world.space.nodes[current_id] = _make_node(current_id, "Current", 0.5)
    state.world.space.nodes[same_sector_id] = _make_node(same_sector_id, "Same Sector", 1.0)
    state.world.space.nodes[next_sector_id] = _make_node(next_sector_id, "Next Sector", 12.0)
    state.world.space.nodes[far_sector_id] = _make_node(far_sector_id, "Far Sector", 26.0)

    state.world.current_node_id = current_id
    state.ship.current_node_id = current_id
    state.world.current_pos_ly = (0.5, 0.0, 0.0)
    state.world.known_nodes = {current_id, same_sector_id, next_sector_id, far_sector_id}
    state.world.known_contacts = set(state.world.known_nodes)
    state.world.known_links = {}
    add_known_link(state.world, current_id, same_sector_id, bidirectional=True)

    current_sector = sector_id_for_pos(0.5, 0.0, 0.0)
    next_sector = sector_id_for_pos(12.0, 0.0, 0.0)
    far_sector = sector_id_for_pos(26.0, 0.0, 0.0)

    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_nav_contacts(state)
    text = buf.getvalue()

    assert f"sector={current_sector}" in text, text
    assert "region=" in text, text
    same_idx = text.index(f"id={same_sector_id}")
    next_idx = text.index(f"id={next_sector_id}")
    far_idx = text.index(f"id={far_sector_id}")
    assert same_idx < next_idx < far_idx, text

    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_nav_contacts(state, map_arg="sector")
    sector_text = buf.getvalue()

    assert f"- {current_sector} " in sector_text, sector_text
    assert f"contacts=({current_id}, {same_sector_id})" in sector_text, sector_text
    assert f"- {next_sector} " in sector_text, sector_text
    assert f"contacts=({next_sector_id})" in sector_text, sector_text
    assert f"- {far_sector} " in sector_text, sector_text
    assert f"contacts=({far_sector_id})" in sector_text, sector_text
