from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.model.systems import SystemState


def main() -> None:
    state = create_initial_state_prologue()
    state.ship.systems["sensors"].state = SystemState.NOMINAL

    # Simulate being at HARBOR_12 after learning routes from ECHO_7 uplink.
    state.world.current_node_id = "HARBOR_12"
    state.ship.current_node_id = "HARBOR_12"
    state.world.known_nodes.update({"UNKNOWN", "ECHO_7", "HARBOR_12", "CURL_12", "DERELICT_A3"})
    state.world.known_contacts.update(state.world.known_nodes)
    state.world.known_links.setdefault("HARBOR_12", set()).add("ECHO_7")
    state.world.known_links.setdefault("ECHO_7", set()).add("HARBOR_12")
    state.world.visited_nodes.update({"UNKNOWN", "ECHO_7", "HARBOR_12"})

    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_contacts(state)
    text = buf.getvalue()

    harbor_line = next((line for line in text.splitlines() if "id=HARBOR_12" in line), "")
    assert harbor_line, text
    assert " route " in harbor_line, harbor_line
    assert " no_route " not in harbor_line, harbor_line

    print("CONTACTS SMOKE PASSED")


if __name__ == "__main__":
    main()
