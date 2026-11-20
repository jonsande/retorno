"""Pure, conditional recovery planning after interrupted physical braking.

The planner reads a real inertial PhysicalTransitState. It neither authorizes
fuel nor installs a new segment in the engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
import math
from typing import Literal

from retorno.core.nav_boundaries import braking_available
from retorno.core.nav_physics import (LIGHT_SPEED_M_S, MotionSegment, MotionState,
                                      brake_to_stop, braking_profile, coast_for,
                                      light_years_to_metres, sample_segment)
from retorno.core.gamestate import GameState
from retorno.model.world import distance_between_nodes_ly


RecoveryDecision = Literal["coast_then_brake", "brake_now", "emergency_brake",
                           "no_propulsion", "invalid"]


def _freeze(value: object) -> object:
    """Copy relevant mutable state into immutable, equality-comparable values."""
    if isinstance(value, Enum):
        return (type(value).__name__, value.value)
    if is_dataclass(value):
        return (type(value).__name__, tuple(
            (spec.name, _freeze(getattr(value, spec.name))) for spec in fields(value)))
    if isinstance(value, dict):
        return tuple(sorted((_freeze(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def _source_signature(state: GameState, acceleration: float) -> tuple[object, ...]:
    ship, world = state.ship, state.world
    physical = ship.physical_transit
    origin_id = ship.transit_from or ship.current_node_id
    destination_id = physical.original_destination_id if physical else None
    origin = world.space.nodes.get(origin_id)
    destination = world.space.nodes.get(destination_id)
    active_jobs = tuple(sorted((key, job.status, job.power_draw_kw)
                               for key, job in state.jobs.jobs.items()
                               if key in state.jobs.active_job_ids))
    return (
        _freeze(physical), state.clock.t, state.clock.ship_elapsed_s,
        origin_id, destination_id,
        _freeze(origin) if origin else None,
        _freeze(destination) if destination else None,
        world.current_node_id, _freeze(world.current_pos_ly),
        ship.current_node_id, ship.transit_to,
        ship.in_transit, ship.docked_node_id, ship.op_mode,
        _freeze(ship.systems), _freeze(ship.power), _freeze(ship.installed_modules),
        _freeze(active_jobs), ship.hull_integrity, ship.antimatter_capsules,
        state.os.god_active, acceleration,
    )


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """Kinematic proposal; any powered leg still needs a new fuel receipt."""

    decision: RecoveryDecision
    reason: str
    start: MotionState | None
    destination_id: str | None
    destination_distance_m: float | None
    braking_distance_m: float | None
    recommended_brake_position_m: float | None
    last_possible_brake_position_m: float | None
    segments: tuple[MotionSegment, ...]
    physical_braking_available: bool
    operational_braking_available: bool
    requires_fuel_authorization: bool
    operational_outcome_conditional: bool = True
    _signature: tuple[object, ...] | None = field(default=None, repr=False)
    deceleration_source: Literal["history", "external"] = "history"

    @property
    def remaining_distance_m(self) -> float | None:
        if self.start is None or self.destination_distance_m is None:
            return None
        return self.destination_distance_m - self.start.distance_m

    @property
    def predicted_stop(self) -> MotionState | None:
        if not self.segments:
            return None
        final = self.segments[-1]
        return sample_segment(final, final.duration_galactic_s)

    @property
    def coast_segment(self) -> MotionSegment | None:
        return self.segments[0] if len(self.segments) == 2 else None

    @property
    def braking_segment(self) -> MotionSegment | None:
        return self.segments[-1] if self.segments else None

    @property
    def brake_immediately(self) -> bool:
        return self.decision in {"brake_now", "emergency_brake"}

    @property
    def destination_stop_kinematically_feasible(self) -> bool:
        return self.decision in {"coast_then_brake", "brake_now"}

    @property
    def overshoot_inevitable(self) -> bool:
        return self.decision == "emergency_brake"

    def is_current(self, state: GameState, *,
                   proper_deceleration_m_s2: float | None = None) -> bool:
        """Reject a proposal after any relevant source or assumed thrust change."""
        if self._signature is None:
            return False
        if self.deceleration_source == "external" and proper_deceleration_m_s2 is None:
            return False
        if proper_deceleration_m_s2 is None:
            physical = state.ship.physical_transit
            if physical is None or physical.inertial_continuation is None:
                return False
            acceleration = abs(physical.inertial_continuation.interrupted_segment.proper_acceleration_m_s2)
        else:
            acceleration = proper_deceleration_m_s2
        return self._signature == _source_signature(state, acceleration)


def plan_inertial_recovery(
    state: GameState, *, proper_deceleration_m_s2: float | None = None,
) -> RecoveryPlan:
    """Plan a forward stop from current inertia, without mutating ``state``.

    The interrupted brake supplies the default nominal deceleration. A caller
    may provide its current available deceleration and must provide it again
    when checking plan freshness. Omission of an external value never confirms
    freshness.
    """
    ship = state.ship
    physical = ship.physical_transit
    destination_id = physical.original_destination_id if physical else None
    start: MotionState | None = None
    empty: tuple[MotionSegment, ...] = ()

    def invalid(reason: str) -> RecoveryPlan:
        return RecoveryPlan("invalid", reason, start, destination_id, None,
                            None, None, None, empty, False, False, False, False)

    if physical is None or physical.inertial_continuation is None:
        return invalid("physical_inertial_continuation_required")
    try:
        physical.__post_init__()
        start = physical.motion
    except ValueError:
        return invalid("invalid_physical_transit")
    history = physical.inertial_continuation
    if (physical.intent != "coast" or not physical.braking_started
            or not physical.replan_required or start is None or start.beta <= 0
            or ship.in_transit or ship.docked_node_id is not None
            or state.clock.t != start.galactic_s
            or state.clock.ship_elapsed_s != start.proper_s):
        return invalid("inertial_source_or_clock_invalid")
    origin_id = ship.transit_from or ship.current_node_id
    route_ly = distance_between_nodes_ly(state.world, origin_id, destination_id)
    if route_ly is None or not math.isfinite(route_ly) or route_ly <= 0:
        return invalid("destination_geometry_invalid")
    try:
        destination_m = light_years_to_metres(route_ly)
    except ValueError:
        return invalid("destination_geometry_invalid")
    origin = state.world.space.nodes[origin_id]
    destination = state.world.space.nodes[destination_id]
    fraction = start.distance_m / destination_m
    expected_pos = tuple(a + fraction * (b - a) for a, b in zip(
        (origin.x_ly, origin.y_ly, origin.z_ly),
        (destination.x_ly, destination.y_ly, destination.z_ly)))
    if (len(state.world.current_pos_ly) != 3 or any(
            not math.isfinite(actual) or not math.isfinite(expected)
            for actual, expected in zip(state.world.current_pos_ly, expected_pos)) or any(
            abs(actual - expected) > max(
                1e-12, 64 * math.ulp(max(1.0, abs(actual), abs(expected))))
            for actual, expected in zip(state.world.current_pos_ly, expected_pos))):
        return invalid("world_and_physical_position_disagree")
    acceleration = (abs(history.interrupted_segment.proper_acceleration_m_s2)
                    if proper_deceleration_m_s2 is None else proper_deceleration_m_s2)
    if (not isinstance(acceleration, (int, float)) or not math.isfinite(acceleration)
            or acceleration <= 0):
        return invalid("braking_acceleration_invalid")
    deceleration_source: Literal["history", "external"] = (
        "history" if proper_deceleration_m_s2 is None else "external")
    signature = _source_signature(state, acceleration)
    physical_capacity = braking_available(ship)
    # Reuse the engine's current operational gate rather than duplicating its
    # power path. Local import avoids a module-level engine dependency.
    from retorno.core.engine import Engine
    operational = Engine._physical_propulsion_available(state, "brake")
    if not physical_capacity or not operational:
        reason = ("engine_repair_or_isolation_recovery_required" if not physical_capacity
                  else "operational_power_recovery_required")
        return RecoveryPlan("no_propulsion", reason, start, destination_id,
                            destination_m, None, None, None, empty,
                            physical_capacity, operational, False, False,
                            deceleration_source=deceleration_source, _signature=signature)
    try:
        profile = braking_profile(start.beta, acceleration)
        immediate = brake_to_stop(start, acceleration)
        stop_now = sample_segment(immediate, immediate.duration_galactic_s)
    except ValueError:
        return invalid("braking_calculation_out_of_range")
    braking_m = profile.distance_m
    profile_tol = max(1.0, 64 * math.ulp(max(
        start.distance_m, braking_m, stop_now.distance_m)))
    if (stop_now.beta != 0 or abs((stop_now.distance_m - start.distance_m) - braking_m)
            > profile_tol):
        return invalid("braking_profile_and_segment_disagree")
    remaining = destination_m - start.distance_m
    last = destination_m - braking_m
    if remaining <= braking_m:
        decision: RecoveryDecision = "brake_now" if remaining == braking_m else "emergency_brake"
        reason = ("exact_braking_boundary" if decision == "brake_now" else
                  "already_beyond_destination" if remaining < 0 else
                  "insufficient_distance_to_stop_at_destination")
        return RecoveryPlan(decision, reason, start, destination_id, destination_m,
                            braking_m, last, last, (immediate,), physical_capacity,
                            operational, True, deceleration_source=deceleration_source,
                            _signature=signature)
    coast_m = remaining - braking_m
    coast_s = coast_m / (LIGHT_SPEED_M_S * start.beta)
    try:
        coast = coast_for(start, coast_s)
        coast_end = sample_segment(coast, coast.duration_galactic_s)
        brake = brake_to_stop(coast_end, acceleration)
        stop = sample_segment(brake, brake.duration_galactic_s)
    except ValueError:
        return invalid("coast_or_brake_below_numerical_resolution")
    closure_tol = max(1.0, 64 * math.ulp(max(
        start.distance_m, destination_m, braking_m,
        coast_end.distance_m, stop.distance_m)))
    if stop.beta != 0 or abs(stop.distance_m - destination_m) > closure_tol:
        return invalid("braking_geometry_did_not_close")
    return RecoveryPlan("coast_then_brake", "coast_to_last_braking_point",
                        start, destination_id, destination_m, braking_m, last,
                        last, (coast, brake), physical_capacity, operational,
                        True, deceleration_source=deceleration_source,
                        _signature=signature)
