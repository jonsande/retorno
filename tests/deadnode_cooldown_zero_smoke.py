from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.world import DeadNodeState, SpaceNode


CURRENT_ID = "DEADNODE_CURRENT_TEST"
TARGET_A = "DEADNODE_TARGET_A"
TARGET_B = "DEADNODE_TARGET_B"


def _node(node_id: str, x_ly: float) -> SpaceNode:
    return SpaceNode(
        node_id=node_id,
        name=node_id.replace("_", " ").title(),
        kind="station",
        region="disk",
        x_ly=x_ly,
        y_ly=0.0,
        z_ly=0.0,
        is_hub=True,
        is_topology_hub=True,
    )


def _ready_deadnode(action_t: float = 0.0) -> DeadNodeState:
    return DeadNodeState(
        stuck_since_t=action_t,
        dead_since_t=action_t,
        stuck_since_uplinks=0,
        dead_since_uplinks=0,
        stuck_threshold_uplinks=Balance.DEADNODE_STUCK_UPLINKS_MIN,
        dead_threshold_uplinks=Balance.DEADNODE_DEAD_UPLINKS_MIN,
        stuck_threshold_years=Balance.DEADNODE_STUCK_YEARS_MIN,
        dead_threshold_years=Balance.DEADNODE_DEAD_YEARS_MIN,
    )


def _make_state(*, start_t: float = 0.0):
    state = create_initial_state_sandbox()
    state.clock.t = start_t
    state.world.space.nodes = {
        CURRENT_ID: _node(CURRENT_ID, 0.0),
        TARGET_A: _node(TARGET_A, 100.0),
    }
    state.world.current_node_id = CURRENT_ID
    state.ship.current_node_id = CURRENT_ID
    state.ship.docked_node_id = None
    state.world.current_pos_ly = (0.0, 0.0, 0.0)
    state.world.known_nodes = {CURRENT_ID, TARGET_A}
    state.world.known_contacts = {TARGET_A}
    state.world.known_links = {CURRENT_ID: set()}
    state.world.visited_nodes = {CURRENT_ID}
    state.world.forced_hidden_nodes = set()
    state.world.generated_sectors = set()
    state.world.sector_states = {}
    state.world.intersector_link_pairs = set()
    state.world.node_pools = {}
    state.world.dead_nodes = {TARGET_A: _ready_deadnode(start_t)}
    state.world.lore.counters["uplink_count"] = 0
    return state


def _signal_files(state) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (path, node.content)
            for path, node in state.os.fs.items()
            if path.startswith("/logs/signals/") and getattr(node, "content", None) is not None
        )
    )


def _observable_snapshot(state, target_id: str) -> dict:
    tracked = state.world.dead_nodes[target_id]
    return {
        "attempts": tracked.attempts,
        "last_action_t": tracked.last_action_t,
        "bridge_node_id": tracked.bridge_node_id,
        "next_event_seq": state.events.next_event_seq,
        "signal_files": _signal_files(state),
        "known_links": copy.deepcopy(state.world.known_links),
        "intel": copy.deepcopy(state.world.intel),
    }


def _assert_one_action(state, target_id: str, expected_attempts: int, expected_t: float) -> None:
    events = evaluate_dead_nodes(state, "scan")
    assert len(events) == 1, events
    tracked = state.world.dead_nodes[target_id]
    assert tracked.attempts == expected_attempts, tracked
    assert tracked.last_action_t == expected_t, tracked
    assert len(_signal_files(state)) == expected_attempts


def _assert_blocked_without_mutation(state, target_id: str) -> None:
    before = _observable_snapshot(state, target_id)
    events = evaluate_dead_nodes(state, "scan")
    assert events == [], events
    assert _observable_snapshot(state, target_id) == before


def _assert_zero_timestamp_cooldown_boundaries() -> None:
    state = _make_state(start_t=0.0)
    _assert_one_action(state, TARGET_A, expected_attempts=1, expected_t=0.0)

    _assert_blocked_without_mutation(state, TARGET_A)

    cooldown_s = Balance.DEADNODE_ACTION_COOLDOWN_YEARS * Balance.YEAR_S
    state.clock.t = cooldown_s - 1.0
    _assert_blocked_without_mutation(state, TARGET_A)

    state.clock.t = cooldown_s
    _assert_one_action(state, TARGET_A, expected_attempts=2, expected_t=cooldown_s)
    assert state.world.known_links == {CURRENT_ID: set()}
    assert state.world.intel == []


def _assert_positive_timestamp_behavior_is_preserved() -> None:
    start_t = 123.0
    state = _make_state(start_t=start_t)
    _assert_one_action(state, TARGET_A, expected_attempts=1, expected_t=start_t)
    _assert_blocked_without_mutation(state, TARGET_A)

    cooldown_s = Balance.DEADNODE_ACTION_COOLDOWN_YEARS * Balance.YEAR_S
    state.clock.t = start_t + cooldown_s - 1.0
    _assert_blocked_without_mutation(state, TARGET_A)
    state.clock.t = start_t + cooldown_s
    _assert_one_action(state, TARGET_A, expected_attempts=2, expected_t=state.clock.t)


def _assert_new_candidate_and_candidate_independence() -> None:
    state = _make_state(start_t=0.0)
    _assert_one_action(state, TARGET_A, expected_attempts=1, expected_t=0.0)

    state.world.space.nodes[TARGET_B] = _node(TARGET_B, 200.0)
    state.world.known_nodes.add(TARGET_B)
    state.world.known_contacts.add(TARGET_B)
    state.world.dead_nodes[TARGET_B] = _ready_deadnode(0.0)

    events = evaluate_dead_nodes(state, "scan")
    assert len(events) == 1, events
    assert state.world.dead_nodes[TARGET_A].attempts == 1
    assert state.world.dead_nodes[TARGET_A].last_action_t == 0.0
    assert state.world.dead_nodes[TARGET_B].attempts == 1
    assert state.world.dead_nodes[TARGET_B].last_action_t == 0.0
    assert len(_signal_files(state)) == 2


def _assert_zero_timestamp_cooldown_survives_save_load() -> None:
    state = _make_state(start_t=0.0)
    _assert_one_action(state, TARGET_A, expected_attempts=1, expected_t=0.0)

    with TemporaryDirectory() as tmp_dir:
        slot_path = Path(tmp_dir) / "deadnode-zero.dat"
        save_single_slot(state, slot_path)
        result = load_single_slot(slot_path)
        assert result is not None
        loaded = result.state

        tracked = loaded.world.dead_nodes[TARGET_A]
        assert tracked.attempts == 1
        assert tracked.last_action_t == 0.0
        assert len(_signal_files(loaded)) == 1
        _assert_blocked_without_mutation(loaded, TARGET_A)

        cooldown_s = Balance.DEADNODE_ACTION_COOLDOWN_YEARS * Balance.YEAR_S
        loaded.clock.t = cooldown_s
        _assert_one_action(loaded, TARGET_A, expected_attempts=2, expected_t=cooldown_s)


def main() -> None:
    _assert_zero_timestamp_cooldown_boundaries()
    _assert_positive_timestamp_behavior_is_preserved()
    _assert_new_candidate_and_candidate_independence()
    _assert_zero_timestamp_cooldown_survives_save_load()
    print("DEADNODE COOLDOWN ZERO SMOKE PASSED")


if __name__ == "__main__":
    main()
