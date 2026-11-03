from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.config.balance import Balance
from retorno.core import engine as engine_mod
from retorno.core.actions import Scan
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode


ORIGIN_ID = "SENSOR_FACTOR_ORIGIN"
TARGET_ID = "SENSOR_FACTOR_TARGET"


class _FixedRandomModule:
    def __init__(self, roll: float) -> None:
        self._roll = roll

    def Random(self, _seed: int):  # noqa: N802 - mirrors random.Random
        return self

    def random(self) -> float:
        return self._roll


def _node(node_id: str, x_ly: float) -> SpaceNode:
    return SpaceNode(
        node_id=node_id,
        name=node_id,
        kind="station",
        region="disk",
        x_ly=x_ly,
        y_ly=0.0,
        z_ly=0.0,
    )


def _scan_state(sensor_state: SystemState, *, target_distance_ly: float = 1.0):
    state = create_initial_state_prologue()
    state.ship.power.power_quality = 0.90
    state.ship.systems["core_os"].state = SystemState.NOMINAL
    state.ship.systems["energy_distribution"].state = SystemState.NOMINAL
    sensors = state.ship.systems["sensors"]
    sensors.state = sensor_state
    sensors.forced_offline = False
    assert sensors.service is not None
    sensors.service.is_running = True
    state.ship.sensors_range_ly = 2.0

    state.world.space.nodes = {
        ORIGIN_ID: _node(ORIGIN_ID, 0.0),
        TARGET_ID: _node(TARGET_ID, target_distance_ly),
    }
    state.world.current_node_id = ORIGIN_ID
    state.ship.current_node_id = ORIGIN_ID
    state.world.current_pos_ly = (0.0, 0.0, 0.0)
    state.world.known_nodes = {ORIGIN_ID}
    state.world.known_contacts = {ORIGIN_ID}
    state.world.exploration_recovery.entry_node_id = None
    return state


def _target_detected(
    sensor_state: SystemState,
    *,
    roll: float,
    near_probability: float,
    far_probability: float,
    target_distance_ly: float = 1.0,
    guaranteed_recovery: bool = False,
) -> bool:
    state = _scan_state(sensor_state, target_distance_ly=target_distance_ly)
    if guaranteed_recovery:
        state.world.exploration_recovery.entry_node_id = TARGET_ID

    original_random = engine_mod.random
    original_near = Balance.SENSORS_DETECT_P_NEAR
    original_far = Balance.SENSORS_DETECT_P_FAR
    engine_mod.random = _FixedRandomModule(roll)
    Balance.SENSORS_DETECT_P_NEAR = near_probability
    Balance.SENSORS_DETECT_P_FAR = far_probability
    try:
        seen, _, _ = Engine()._perform_scan(state)  # noqa: SLF001
    finally:
        engine_mod.random = original_random
        Balance.SENSORS_DETECT_P_NEAR = original_near
        Balance.SENSORS_DETECT_P_FAR = original_far
    return TARGET_ID in seen


def _assert_factor_matrix() -> None:
    expected_factors = {
        SystemState.OFFLINE: Balance.SENSORS_DETECT_P_CRITICAL,
        SystemState.CRITICAL: Balance.SENSORS_DETECT_P_CRITICAL,
        SystemState.DAMAGED: Balance.SENSORS_DETECT_P_DAMAGED,
        SystemState.LIMITED: Balance.SENSORS_DETECT_P_LIMITED,
        SystemState.NOMINAL: Balance.SENSORS_DETECT_P_NOMINAL,
        SystemState.UPGRADED: Balance.SENSORS_DETECT_P_NOMINAL,
    }
    base_probability = 0.80
    for sensor_state, factor in expected_factors.items():
        threshold = base_probability * factor
        assert _target_detected(
            sensor_state,
            roll=max(0.001, threshold - 0.01),
            near_probability=base_probability,
            far_probability=base_probability,
        ), f"{sensor_state.value} should detect below its factor threshold {threshold:.3f}"
        assert not _target_detected(
            sensor_state,
            roll=min(1.0, threshold + 0.01),
            near_probability=base_probability,
            far_probability=base_probability,
        ), f"{sensor_state.value} should reject above its factor threshold {threshold:.3f}"


def _assert_distance_and_probability_limits() -> None:
    assert _target_detected(
        SystemState.NOMINAL,
        roll=0.49,
        near_probability=1.0,
        far_probability=0.0,
        target_distance_ly=1.0,
    )
    assert not _target_detected(
        SystemState.NOMINAL,
        roll=0.51,
        near_probability=1.0,
        far_probability=0.0,
        target_distance_ly=1.0,
    )
    assert _target_detected(
        SystemState.NOMINAL,
        roll=1.0,
        near_probability=2.0,
        far_probability=2.0,
    )
    assert not _target_detected(
        SystemState.NOMINAL,
        roll=0.001,
        near_probability=-1.0,
        far_probability=-1.0,
    )


def _assert_public_operational_gate() -> None:
    operational = {SystemState.LIMITED, SystemState.NOMINAL, SystemState.UPGRADED}
    for sensor_state in SystemState:
        state = _scan_state(sensor_state)
        events = Engine().apply_action(state, Scan())
        if sensor_state in operational:
            assert any(event.type == EventType.JOB_QUEUED for event in events), sensor_state
        else:
            assert any(event.type == EventType.BOOT_BLOCKED for event in events), sensor_state
            assert not state.jobs.active_job_ids


def _assert_recovery_entry_guarantee() -> None:
    assert _target_detected(
        SystemState.LIMITED,
        roll=0.999,
        near_probability=-1.0,
        far_probability=-1.0,
        guaranteed_recovery=True,
    )


def main() -> None:
    _assert_factor_matrix()
    _assert_distance_and_probability_limits()
    _assert_public_operational_gate()
    _assert_recovery_entry_guarantee()
    print("SENSOR DETECTION FACTOR SMOKE PASSED")


if __name__ == "__main__":
    main()
