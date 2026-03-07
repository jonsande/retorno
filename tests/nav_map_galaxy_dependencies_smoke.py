from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.model.systems import SystemState


def main() -> None:
    state = create_initial_state_prologue()
    parsed_sectors = parse_command("nav map sectors")
    parsed_galaxy = parse_command("nav map galaxy")
    parsed_galaxy_local = parse_command("nav map galaxy local")
    parsed_alias_global = parse_command("nav galaxy global")
    assert parsed_sectors == ("NAV_MAP", "sectors", None), parsed_sectors
    assert parsed_galaxy == ("NAV_MAP", "galaxy", None), parsed_galaxy
    assert parsed_galaxy_local == ("NAV_MAP", "galaxy", "local"), parsed_galaxy_local
    assert parsed_alias_global == ("NAV_MAP", "galaxy", "global"), parsed_alias_global

    core_os = state.ship.systems["core_os"]
    for core_state in (
        SystemState.NOMINAL,
        SystemState.LIMITED,
        SystemState.DAMAGED,
        SystemState.CRITICAL,
        SystemState.OFFLINE,
    ):
        core_os.state = core_state
        sectors_block = repl._command_blocked_message(state, parsed_sectors)
        galaxy_block = repl._command_blocked_message(state, parsed_galaxy)
        galaxy_local_block = repl._command_blocked_message(state, parsed_galaxy_local)
        galaxy_alias_block = repl._command_blocked_message(state, parsed_alias_global)
        assert sectors_block == galaxy_block == galaxy_local_block == galaxy_alias_block, (
            core_state,
            sectors_block,
            galaxy_block,
            galaxy_local_block,
            galaxy_alias_block,
        )

    print("NAV MAP GALAXY DEPENDENCIES SMOKE PASSED")


if __name__ == "__main__":
    main()
