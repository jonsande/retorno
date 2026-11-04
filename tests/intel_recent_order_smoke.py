from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.model.os import Locale
from retorno.model.world import IntelItem
from retorno.ui_textual import presenter


EXPORT_PATH = "/data/nav/intel-recent-order.txt"


def _item(intel_id: str, t: float, target: str) -> IntelItem:
    return IntelItem(
        intel_id=intel_id,
        t=t,
        kind="node",
        to_id=target,
        confidence=0.8,
        source_kind="manual",
        source_ref="/manuals/test",
    )


def _state_with(items: list[IntelItem], *, locale: Locale = Locale.EN):
    state = create_initial_state_sandbox()
    state.os.locale = locale
    state.clock.t = 1000.0
    state.world.intel = list(items)
    state.world.next_intel_seq = len(items) + 1
    return state


def _knowledge_snapshot(state) -> dict:
    return {
        "intel": copy.deepcopy(state.world.intel),
        "next_intel_seq": state.world.next_intel_seq,
        "known_intel": copy.deepcopy(state.world.known_intel),
        "known_nodes": set(state.world.known_nodes),
        "known_contacts": set(state.world.known_contacts),
        "known_links": copy.deepcopy(state.world.known_links),
        "fine_ranges_km": copy.deepcopy(state.world.fine_ranges_km),
        "rng_counter": state.meta.rng_counter,
    }


def _run_public_command(state, command: str) -> str:
    parsed = parse_command(command)
    output = io.StringIO()
    with redirect_stdout(output):
        if parsed == "INTEL_LIST":
            repl.render_intel_list(state)
        elif isinstance(parsed, tuple) and parsed[0] == "INTEL_LIST":
            limit = None if parsed[1] == "all" else int(parsed[1])
            repl.render_intel_list(state, limit=limit)
        elif isinstance(parsed, tuple) and parsed[0] == "INTEL_SHOW":
            repl.render_intel_show(state, parsed[1])
        elif isinstance(parsed, tuple) and parsed[0] == "INTEL_EXPORT":
            repl._handle_intel_export(state, parsed[1])
        else:
            raise AssertionError(f"unexpected public parse result: {parsed!r}")
    return output.getvalue()


def _listed_ids(output: str, expected_ids: set[str]) -> list[str]:
    listed: list[str] = []
    for line in output.splitlines():
        fields = line.split()
        if fields and fields[0] in expected_ids:
            listed.append(fields[0])
    return listed


def _assert_read_only(state, command: str, expected_ids: list[str]) -> str:
    before = _knowledge_snapshot(state)
    output = _run_public_command(state, command)
    assert _listed_ids(output, {item.intel_id for item in state.world.intel}) == expected_ids
    assert _knowledge_snapshot(state) == before
    return output


def _assert_empty_and_single() -> None:
    empty = _state_with([])
    before = _knowledge_snapshot(empty)
    output = _run_public_command(empty, "intel")
    assert "(no intel)" in output
    assert "Try: intel import" in output
    assert _knowledge_snapshot(empty) == before

    single_item = _item("I_ONLY", 5.0, "NODE_ONLY")
    single = _state_with([single_item])
    _assert_read_only(single, "intel", ["I_ONLY"])
    _assert_read_only(single, "intel 10", ["I_ONLY"])
    _assert_read_only(single, "intel all", ["I_ONLY"])


def _assert_limits_timestamps_and_locales() -> None:
    items = [
        _item("I_OLD", 10.0, "NODE_OLD"),
        _item("I_NEW", 30.0, "NODE_NEW"),
        _item("I_MID", 20.0, "NODE_MID"),
        _item("I_TIE_OLD", 25.0, "NODE_TIE_OLD"),
        _item("I_TIE_NEW", 25.0, "NODE_TIE_NEW"),
    ]
    expected_all = ["I_NEW", "I_TIE_NEW", "I_TIE_OLD", "I_MID", "I_OLD"]
    state = _state_with(items)

    assert parse_command("intel") == "INTEL_LIST"
    assert parse_command("intel 1") == ("INTEL_LIST", 1)
    assert parse_command("intel 2") == ("INTEL_LIST", 2)
    assert parse_command("intel all") == ("INTEL_LIST", "all")

    _assert_read_only(state, "intel 1", expected_all[:1])
    _assert_read_only(state, "intel 2", expected_all[:2])
    _assert_read_only(state, "intel 10", expected_all)
    _assert_read_only(state, "intel all", expected_all)

    state.os.locale = Locale.ES
    output = _assert_read_only(state, "intel 2", expected_all[:2])
    assert "Prueba: intel import" in output

    before = _knowledge_snapshot(state)
    textual_lines = presenter.build_command_output(repl.render_intel_list, state, limit=2)
    assert _listed_ids("\n".join(textual_lines), {item.intel_id for item in items}) == expected_all[:2]
    assert _knowledge_snapshot(state) == before


def _assert_default_limit_is_latest_twenty() -> None:
    items = [
        _item(f"I{index:02d}", float(index), f"NODE_{index:02d}")
        for index in range(25)
    ]
    state = _state_with(items)
    expected = [f"I{index:02d}" for index in range(24, 4, -1)]
    _assert_read_only(state, "intel", expected)


def _assert_show_and_export_are_unchanged() -> None:
    items = [
        _item("I_OLD", 10.0, "NODE_OLD"),
        _item("I_NEW", 30.0, "NODE_NEW"),
        _item("I_MID", 20.0, "NODE_MID"),
    ]
    state = _state_with(items)

    before = _knowledge_snapshot(state)
    show_output = _run_public_command(state, "intel show I_MID")
    assert "id: I_MID" in show_output
    assert "to: NODE_MID" in show_output
    assert "t: 20.0" in show_output
    assert _knowledge_snapshot(state) == before

    export_output = _run_public_command(state, f"intel export {EXPORT_PATH}")
    assert f"(intel) export written to {EXPORT_PATH} (3 lines)" in export_output
    assert state.os.fs[EXPORT_PATH].content == (
        "NODE: NODE_OLD\n"
        "NODE: NODE_NEW\n"
        "NODE: NODE_MID\n"
    )
    assert _knowledge_snapshot(state) == before


def main() -> None:
    _assert_empty_and_single()
    _assert_limits_timestamps_and_locales()
    _assert_default_limit_is_latest_twenty()
    _assert_show_and_export_are_unchanged()
    print("INTEL RECENT ORDER SMOKE PASSED")


if __name__ == "__main__":
    main()
