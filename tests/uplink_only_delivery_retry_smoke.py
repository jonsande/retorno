from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
import retorno.core.lore as lore_mod
from retorno.core.lore import (
    _assign_piece_to_node,
    build_lore_context,
    maybe_deliver_lore,
    sync_node_pools_for_known_nodes,
)
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.world import SpaceNode, add_known_link


ARC_ID = "smoke_uplink_delivery"
PIECE_ID = "smoke_primary_link"
PIECE_KEY = f"arc:{ARC_ID}:{PIECE_ID}"


def _arc(line: str) -> dict:
    return {
        "arc_id": ARC_ID,
        "primary_intel": {
            "id": PIECE_ID,
            "kind": "link",
            "line": line,
            "confidence": 0.8,
            "allowed_channels": ["uplink_only"],
        },
        "secondary_lore_docs": [],
        "placement_rules": {"primary": {}},
    }


def _piece_entry(line: str) -> dict:
    return {
        "piece_key": PIECE_KEY,
        "piece_id": PIECE_ID,
        "piece": _arc(line)["primary_intel"],
        "arc_id": ARC_ID,
        "role": "primary",
        "force": False,
        "channels": ["uplink_only"],
        "placement_rules": {},
    }


def _add_node(state, node_id: str, *, dx: float) -> None:
    origin = state.world.space.nodes[state.world.current_node_id]
    state.world.space.nodes[node_id] = SpaceNode(
        node_id=node_id,
        name=node_id.replace("_", " ").title(),
        kind="station",
        region=origin.region,
        x_ly=origin.x_ly + dx,
        y_ly=origin.y_ly,
        z_ly=origin.z_ly,
    )


def _prepared_state(line: str):
    state = create_initial_state_sandbox()
    # This retry fixture edits its route pool and creates literal synthetic
    # endpoints. Test the retained legacy mechanism explicitly.
    state.world.information_version = "legacy-information-v0"
    state.world.information_definition = None
    state.world.radio_history_version = "legacy-radio-v0"
    state.world.radio_definition = None
    state.clock.t = 123.0
    state.ship.docked_node_id = state.world.current_node_id
    sync_node_pools_for_known_nodes(state)
    node_id = state.world.current_node_id
    assert _assign_piece_to_node(state, _piece_entry(line), node_id)
    pool = state.world.node_pools[node_id]
    pool.uplink_route_pool = []
    state.world.lore.last_delivery_t = 17.0
    return state


def _link_intel_count(state, left: str, right: str) -> int:
    return sum(
        1
        for item in state.world.intel
        if item.kind == "link" and item.from_id == left and item.to_id == right
    )


def _assert_pending(state, *, last_delivery_t: float = 17.0) -> None:
    node_id = state.world.current_node_id
    pool = state.world.node_pools[node_id]
    primary = state.world.arc_placements.get(ARC_ID, {}).get("primary", {})
    assert PIECE_KEY not in state.world.lore.delivered
    assert PIECE_KEY not in pool.delivered_piece_ids
    assert PIECE_KEY in pool.pending_push_piece_ids
    assert state.world.lore_placements.piece_to_node.get(PIECE_KEY) == node_id
    assert state.world.lore_placements.piece_channel_bindings.get(PIECE_KEY) == "uplink_only"
    assert not primary.get("unlocked", False)
    assert state.world.lore.last_delivery_t == last_delivery_t


def _assert_delivered(state, left: str, right: str) -> None:
    node_id = state.world.current_node_id
    pool = state.world.node_pools[node_id]
    arc_state = state.world.arc_placements.get(ARC_ID, {})
    primary = arc_state.get("primary", {})
    discovered = arc_state.get("discovered", set())
    assert PIECE_KEY in state.world.lore.delivered
    assert PIECE_KEY in pool.delivered_piece_ids
    assert PIECE_KEY not in pool.pending_push_piece_ids
    assert primary.get("unlocked") is True
    assert PIECE_ID in discovered
    assert right in state.world.known_links.get(left, set())
    assert left in state.world.known_links.get(right, set())
    assert _link_intel_count(state, left, right) == 1


def _assert_no_link_effect(state, left: str, right: str) -> None:
    assert right not in state.world.known_links.get(left, set())
    assert left not in state.world.known_links.get(right, set())
    assert _link_intel_count(state, left, right) == 0


def _public_uplink_output(state) -> str:
    output = io.StringIO()
    with redirect_stdout(output):
        repl._handle_uplink(state)
    return output.getvalue()


def _run_matrix_case(
    line: str,
    *,
    nodes: list[tuple[str, float]],
    expect_success: bool,
    expected_link: tuple[str, str] | None = None,
    preexisting: bool = False,
) -> None:
    state = _prepared_state(line)
    for node_id, dx in nodes:
        _add_node(state, node_id, dx=dx)
    if preexisting and expected_link:
        add_known_link(state.world, expected_link[0], expected_link[1], bidirectional=True)

    before_counters = dict(state.world.lore.counters)
    before_event_seq = state.events.next_event_seq
    before_delivery_log = list(state.world.lore.delivery_log)
    ctx = build_lore_context(state, state.world.current_node_id)

    result = maybe_deliver_lore(state, "uplink", ctx, count_trigger=False)
    if expect_success:
        assert result.applied is True
        assert expected_link is not None
        _assert_delivered(state, expected_link[0], expected_link[1])
        assert state.world.lore.last_delivery_t == state.clock.t

        result_again = maybe_deliver_lore(state, "uplink", ctx, count_trigger=False)
        assert result_again.applied is False
        _assert_delivered(state, expected_link[0], expected_link[1])
    else:
        _assert_pending(state)
        assert result.applied is False
        if expected_link is not None:
            _assert_no_link_effect(state, expected_link[0], expected_link[1])
        result_again = maybe_deliver_lore(state, "uplink", ctx, count_trigger=False)
        assert result_again.applied is False
        _assert_pending(state)
        if expected_link is not None:
            _assert_no_link_effect(state, expected_link[0], expected_link[1])

    assert state.world.lore.counters == before_counters
    assert state.events.next_event_seq == before_event_seq
    assert state.world.lore.delivery_log == before_delivery_log


def _run_matrix() -> None:
    cases = [
        ("not a LINK", [], False, None, False),
        (
            "LINK: ECHO_7 -> MISSING_TARGET",
            [],
            False,
            ("ECHO_7", "MISSING_TARGET"),
            False,
        ),
        (
            "LINK: ECHO_7 -> FAR_TARGET",
            [("FAR_TARGET", 46.0)],
            False,
            ("ECHO_7", "FAR_TARGET"),
            False,
        ),
        (
            "LINK: ECHO_7 -> VALID_NEW_TARGET",
            [("VALID_NEW_TARGET", 10.0)],
            True,
            ("ECHO_7", "VALID_NEW_TARGET"),
            False,
        ),
        (
            "LINK: ECHO_7 -> VALID_KNOWN_TARGET",
            [("VALID_KNOWN_TARGET", 12.0)],
            True,
            ("ECHO_7", "VALID_KNOWN_TARGET"),
            True,
        ),
    ]
    for line, nodes, expect_success, expected_link, preexisting in cases:
        _run_case_with_loader(
            line,
            lambda line=line, nodes=nodes, expect_success=expect_success,
            expected_link=expected_link, preexisting=preexisting: _run_matrix_case(
                line,
                nodes=nodes,
                expect_success=expect_success,
                expected_link=expected_link,
                preexisting=preexisting,
            ),
        )


def _run_public_counter_matrix() -> None:
    def valid_only() -> None:
        state = _prepared_state("LINK: ECHO_7 -> VALID_ONLY_TARGET")
        _add_node(state, "VALID_ONLY_TARGET", dx=8.0)
        before_count = state.world.lore.counters.get("uplink_count", 0)

        _public_uplink_output(state)

        _assert_delivered(state, "ECHO_7", "VALID_ONLY_TARGET")
        assert state.world.lore.counters.get("uplink_count", 0) == before_count + 1

    _run_case_with_loader("LINK: ECHO_7 -> VALID_ONLY_TARGET", valid_only)

    def invalid_only() -> None:
        state = _prepared_state("LINK: ECHO_7 -> MISSING_ONLY_TARGET")
        before_count = state.world.lore.counters.get("uplink_count", 0)

        _public_uplink_output(state)

        _assert_pending(state)
        _assert_no_link_effect(state, "ECHO_7", "MISSING_ONLY_TARGET")
        assert state.world.lore.counters.get("uplink_count", 0) == before_count

    _run_case_with_loader("LINK: ECHO_7 -> MISSING_ONLY_TARGET", invalid_only)

    def route_and_valid() -> None:
        state = _prepared_state("LINK: ECHO_7 -> VALID_WITH_ROUTE_TARGET")
        _add_node(state, "VALID_WITH_ROUTE_TARGET", dx=8.0)
        _add_node(state, "POOL_ROUTE_TARGET", dx=6.0)
        state.world.node_pools[state.world.current_node_id].uplink_route_pool = [
            "POOL_ROUTE_TARGET"
        ]
        before_count = state.world.lore.counters.get("uplink_count", 0)

        _public_uplink_output(state)

        _assert_delivered(state, "ECHO_7", "VALID_WITH_ROUTE_TARGET")
        assert "POOL_ROUTE_TARGET" in state.world.known_links.get("ECHO_7", set())
        assert state.world.lore.counters.get("uplink_count", 0) == before_count + 1

    _run_case_with_loader("LINK: ECHO_7 -> VALID_WITH_ROUTE_TARGET", route_and_valid)


def _run_case_with_loader(line: str, callback) -> None:
    original_loader = lore_mod.load_arcs
    lore_mod.load_arcs = lambda: [_arc(line)]
    try:
        callback()
    finally:
        lore_mod.load_arcs = original_loader


def _run_public_retry_and_persistence_for_locale(
    locale: Locale,
    *,
    exhausted_message: str,
    applied_message: str,
) -> None:
    line = "LINK: ECHO_7 -> LATE_TARGET"

    def scenario() -> None:
        state = _prepared_state(line)
        state.os.locale = locale
        pool = state.world.node_pools[state.world.current_node_id]
        before_counters = dict(state.world.lore.counters)
        before_logs = {
            path for path in state.os.fs if path.startswith("/logs/nav/uplink_")
        }

        _public_uplink_output(state)
        assert pool.uplink_data_consumed is True
        _assert_pending(state)
        _assert_no_link_effect(state, "ECHO_7", "LATE_TARGET")
        assert state.world.lore.counters == before_counters
        first_logs = {
            path for path in state.os.fs if path.startswith("/logs/nav/uplink_")
        }
        assert len(first_logs) == len(before_logs) + 1

        failed_retry_output = _public_uplink_output(state)
        assert exhausted_message in failed_retry_output
        assert applied_message not in failed_retry_output
        _assert_pending(state)
        _assert_no_link_effect(state, "ECHO_7", "LATE_TARGET")
        assert state.world.lore.counters == before_counters
        assert {
            path for path in state.os.fs if path.startswith("/logs/nav/uplink_")
        } == first_logs

        with TemporaryDirectory() as tmp_dir:
            pending_path = Path(tmp_dir) / "pending.dat"
            save_single_slot(state, pending_path)
            pending_result = load_single_slot(pending_path)
            assert pending_result is not None
            pending = pending_result.state
            _assert_pending(pending)
            _assert_no_link_effect(pending, "ECHO_7", "LATE_TARGET")
            assert pending.world.lore.counters == before_counters
            assert pending.world.node_pools[pending.world.current_node_id].uplink_data_consumed is True

            _add_node(pending, "LATE_TARGET", dx=8.0)
            success_counters = dict(pending.world.lore.counters)
            success_logs = {
                path for path in pending.os.fs if path.startswith("/logs/nav/uplink_")
            }
            before_success_events = len(pending.events.recent)
            successful_retry_output = _public_uplink_output(pending)
            assert applied_message in successful_retry_output
            assert exhausted_message not in successful_retry_output
            assert len(pending.events.recent) == before_success_events + 1
            assert pending.events.recent[-1].type == EventType.UPLINK_COMPLETE
            assert pending.events.recent[-1].message == applied_message
            _assert_delivered(pending, "ECHO_7", "LATE_TARGET")
            assert pending.world.lore.counters == success_counters
            assert {
                path for path in pending.os.fs if path.startswith("/logs/nav/uplink_")
            } == success_logs

            narrative_events = [
                event
                for event in pending.events.recent
                if event.type
                in {EventType.MAIL_RECEIVED, EventType.SIGNAL_CAPTURED, EventType.BROADCAST_RECEIVED}
            ]
            assert narrative_events == []
            assert pending.world.lore.delivery_log == []

            delivered_path = Path(tmp_dir) / "delivered.dat"
            save_single_slot(pending, delivered_path)
            delivered_result = load_single_slot(delivered_path)
            assert delivered_result is not None
            delivered = delivered_result.state
            _assert_delivered(delivered, "ECHO_7", "LATE_TARGET")
            assert delivered.world.lore.counters == success_counters

            before_retry_intel = len(delivered.world.intel)
            before_retry_discovered = set(
                delivered.world.arc_placements[ARC_ID].get("discovered", set())
            )
            before_retry_events = len(delivered.events.recent)
            repeated_output = _public_uplink_output(delivered)
            assert exhausted_message in repeated_output
            assert applied_message not in repeated_output
            _assert_delivered(delivered, "ECHO_7", "LATE_TARGET")
            assert len(delivered.world.intel) == before_retry_intel
            assert delivered.world.lore.counters == success_counters
            assert delivered.world.arc_placements[ARC_ID].get("discovered", set()) == before_retry_discovered
            assert len(delivered.events.recent) == before_retry_events + 1
            assert delivered.events.recent[-1].type == EventType.UPLINK_COMPLETE
            assert delivered.events.recent[-1].message == exhausted_message

    _run_case_with_loader(line, scenario)


def _run_public_retry_and_persistence() -> None:
    _run_public_retry_and_persistence_for_locale(
        Locale.EN,
        exhausted_message="uplink_complete :: node data already exhausted",
        applied_message="uplink_complete :: node data exhausted; pending narrative delivery applied",
    )
    _run_public_retry_and_persistence_for_locale(
        Locale.ES,
        exhausted_message="uplink_complete :: datos del nodo ya agotados",
        applied_message="uplink_complete :: datos del nodo agotados; entrega narrativa pendiente aplicada",
    )


def main() -> None:
    _run_matrix()
    _run_public_counter_matrix()
    _run_public_retry_and_persistence()
    print("UPLINK_ONLY DELIVERY + RETRY SMOKE PASSED")


if __name__ == "__main__":
    main()
