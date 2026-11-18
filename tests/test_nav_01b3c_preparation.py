"""Safe NAV-BRAKE-01B3C preparation while powered integration is blocked."""
from dataclasses import fields
import pickle

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import (
    acceleration_available, braking_available, predict_engine_braking_limit,
    predict_engine_health_limit,
)
from retorno.core.nav_physics import MotionState, accelerate_to
from retorno.core.nav_state import PhysicalTransitState
from retorno.model.ship import ShipState
from retorno.model.systems import SystemState


def _state():
    return create_initial_state_sandbox(seed=303)


@pytest.mark.parametrize("health,accelerate,brake", [
    (0.35000001, True, True),
    (0.35, True, True),
    (0.34999999, False, True),
    (0.15, False, True),
    (0.14999999, False, False),
    (0.0, False, False),
])
def test_distinct_engine_capabilities_at_exact_thresholds(health, accelerate, brake):
    ship = _state().ship
    engine = ship.systems["engines"]
    engine.health = health
    assert acceleration_available(ship) is accelerate
    assert braking_available(ship) is brake
    if health == 0.35:
        assert ship.engine_operating_state() == SystemState.DAMAGED
    if health == 0.15:
        assert ship.engine_operating_state() == SystemState.CRITICAL
    engine.forced_offline = True
    assert not acceleration_available(ship)
    assert not braking_available(ship)


def test_both_health_limits_keep_equality_and_prediction_pure():
    ship = _state().ship
    engine = ship.systems["engines"]
    engine.health = 0.45
    normal = predict_engine_health_limit(ship, 0.01)
    emergency = predict_engine_braking_limit(ship, 0.01)
    assert normal.time_s == pytest.approx(10.0)
    assert emergency.time_s == pytest.approx(30.0)
    assert emergency.kind == "engine_braking_threshold"
    assert engine.health == 0.45
    engine.health = Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH
    at = predict_engine_braking_limit(ship, 0.01)
    assert at.time_s == 0.0
    assert at.validity == "at_threshold_braking_still_available"
    assert braking_available(ship)
    engine.health = 0.149
    assert predict_engine_braking_limit(ship, 0.01).time_s is None


def test_physical_state_derives_pose_and_old_ship_state_still_loads():
    game = _state()
    start = MotionState(0.0, 0.0, 0.0, 0.0)
    segment = accelerate_to(start, 0.01, 10.0)
    active = PhysicalTransitState(segment, 5.0, "TARGET", "accelerate")
    assert active.motion.beta > 0
    assert active.motion.proper_s < 5.0
    assert pickle.loads(pickle.dumps(active)).motion == active.motion
    legacy_slots = {spec.name: getattr(game.ship, spec.name)
                    for spec in fields(ShipState) if spec.name != "physical_transit"}
    restored = object.__new__(ShipState)
    restored.__setstate__((None, legacy_slots))
    assert restored.physical_transit is None


def test_engine_refuses_unpaid_physical_thrust_without_advancing_time():
    game = _state()
    start = MotionState(0.0, 0.0, 0.0, 0.0)
    game.ship.physical_transit = PhysicalTransitState(
        accelerate_to(start, 0.01, 10.0), 0.0, "TARGET", "accelerate",
    )
    before = game.clock.t
    with pytest.raises(RuntimeError, match="segment authorization"):
        Engine().tick(game, 5.0)
    assert game.clock.t == before
    assert game.ship.physical_transit.motion == start
    game.ship.physical_transit = None
    Engine().tick(game, 5.0)
    assert game.clock.t == before + 5.0
