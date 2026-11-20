"""Provisional physical-transit state for the internal navigation integration.

The active segment is the single source for physical position, speed and
proper time. No playable action creates this state in NAV-BRAKE-01B3C.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import math
from typing import Literal

from retorno.core.nav_physics import (LIGHT_SPEED_M_S, MotionSegment, MotionState,
                                      TravelPlan, brake_to_stop, sample_segment)


NavigationIntent = Literal["accelerate", "brake", "coast"]
PendingTransition = Literal["safety_brake", "inertia"]


@dataclass(frozen=True, slots=True)
class PropulsionAuthorization:
    """Receipt for one prepaid physical segment, never a reusable fuel pool."""

    segment: MotionSegment
    destination_id: str
    pricing_speed: float
    capsules_paid: float

    def __post_init__(self) -> None:
        if (self.segment.proper_acceleration_m_s2 == 0 or not self.destination_id
                or not math.isfinite(self.pricing_speed) or self.pricing_speed <= 0
                or not math.isfinite(self.capsules_paid) or self.capsules_paid <= 0):
            raise ValueError("propulsion authorization requires a paid powered segment")


@dataclass(frozen=True, slots=True)
class NominalTravelState:
    """One prepaid, finite rest-to-rest plan; phase progress is an index."""

    origin_id: str
    destination_id: str
    profile: TravelPlan
    segments: tuple[MotionSegment, ...]
    pricing_speed: float
    capsules_paid: float
    phase_index: int = 0
    completed: bool = False
    invalidated: bool = False

    def __post_init__(self) -> None:
        if (not self.origin_id or not self.destination_id
                or self.origin_id == self.destination_id
                or len(self.segments) not in (2, 3)
                or not 0 <= self.phase_index < len(self.segments)
                or not math.isfinite(self.pricing_speed) or self.pricing_speed <= 0
                or not math.isfinite(self.capsules_paid) or self.capsules_paid <= 0):
            raise ValueError("invalid nominal physical travel authorization")
        if self.completed and self.phase_index != len(self.segments) - 1:
            raise ValueError("only the last nominal segment can be complete")
        first, last = self.segments[0], self.segments[-1]
        profile = self.profile
        if (profile.has_cruise != (len(self.segments) == 3)
                or self.pricing_speed != profile.target_beta
                or first.start.beta != 0 or first.start.distance_m != 0
                or first.proper_acceleration_m_s2 != profile.proper_acceleration_m_s2
                or first.end_beta != profile.peak_beta
                or last.proper_acceleration_m_s2 != -profile.proper_acceleration_m_s2
                or last.end_beta != 0):
            raise ValueError("nominal segments disagree with the paid travel plan")
        for actual, expected in ((first.duration_galactic_s, profile.acceleration_galactic_s),
                                 (last.duration_galactic_s, profile.braking_galactic_s)):
            if abs(actual - expected) > 16 * math.ulp(max(1.0, actual, expected)):
                raise ValueError("nominal phase duration disagrees with the paid travel plan")
        if profile.has_cruise:
            middle = self.segments[1]
            if (middle.proper_acceleration_m_s2 != 0
                    or middle.end_beta != profile.peak_beta
                    or middle.duration_galactic_s != profile.cruise_galactic_s):
                raise ValueError("nominal cruise disagrees with the paid travel plan")
        for previous, following in zip(self.segments, self.segments[1:]):
            if sample_segment(previous, previous.duration_galactic_s) != following.start:
                raise ValueError("nominal segments are not physically continuous")
        stop = sample_segment(last, last.duration_galactic_s)
        if abs(stop.distance_m - profile.distance_m) > max(1.0, 64 * math.ulp(profile.distance_m)):
            raise ValueError("nominal plan does not end at its paid destination distance")


@dataclass(frozen=True, slots=True)
class NominalBrakingSubstitution:
    """One use of the braking already included in an invalidated paid journey.

    The immutable source plan remains the historical payment record. The
    interruption and new segment bind this permission to one physical stop;
    this is not another fuel receipt or a reusable antimatter balance.
    """

    paid_plan: NominalTravelState
    interrupted_segment: MotionSegment
    interrupted_elapsed_galactic_s: float
    braking_segment: MotionSegment
    destination_id: str
    cause: Literal["engine_integrity_35"] = "engine_integrity_35"
    completed: bool = False

    def __post_init__(self) -> None:
        plan = self.paid_plan
        plan.__post_init__()
        if (not plan.invalidated or plan.completed
                or plan.phase_index >= len(plan.segments) - 1
                or self.interrupted_segment != plan.segments[plan.phase_index]
                or not math.isfinite(self.interrupted_elapsed_galactic_s)
                or not 0 <= self.interrupted_elapsed_galactic_s <= self.interrupted_segment.duration_galactic_s
                or self.destination_id != plan.destination_id
                or self.cause != "engine_integrity_35"):
            raise ValueError("braking substitution requires an interrupted paid nominal journey")
        start = sample_segment(self.interrupted_segment, self.interrupted_elapsed_galactic_s)
        if (start.beta <= 0 or start.beta > plan.profile.peak_beta
                or self.braking_segment != brake_to_stop(start, plan.profile.proper_acceleration_m_s2)):
            raise ValueError("braking substitution must stop from the original interruption")


@dataclass(frozen=True, slots=True)
class InertialContinuation:
    """Spent braking authority and the current unpowered continuation."""

    interrupted_segment: MotionSegment
    interrupted_elapsed_galactic_s: float
    destination_id: str
    current_segment: MotionSegment
    nominal_plan: NominalTravelState | None = None
    braking_substitution: NominalBrakingSubstitution | None = None
    propulsion_receipt: PropulsionAuthorization | None = None

    def __post_init__(self) -> None:
        if (not math.isfinite(self.interrupted_elapsed_galactic_s)
                or not 0 <= self.interrupted_elapsed_galactic_s <= self.interrupted_segment.duration_galactic_s
                or self.interrupted_segment.proper_acceleration_m_s2 >= 0
                or not self.destination_id):
            raise ValueError("inertial continuation requires interrupted braking")
        cut = sample_segment(self.interrupted_segment, self.interrupted_elapsed_galactic_s)
        coast = self.current_segment
        if (cut.beta <= 0 or coast.proper_acceleration_m_s2 != 0
                or coast.start.beta != cut.beta or coast.end_beta != cut.beta
                or coast.start.galactic_s < cut.galactic_s
                or coast.start.proper_s < cut.proper_s
                or coast.start.distance_m < cut.distance_m):
            raise ValueError("inertial continuation must retain the interrupted speed")
        elapsed = coast.start.galactic_s - cut.galactic_s
        expected_distance = cut.distance_m + LIGHT_SPEED_M_S * cut.beta * elapsed
        expected_proper = cut.proper_s + elapsed * math.sqrt((1 - cut.beta) * (1 + cut.beta))
        if (abs(coast.start.distance_m - expected_distance)
                > max(1.0, 64 * math.ulp(max(1.0, expected_distance)))
                or abs(coast.start.proper_s - expected_proper)
                > max(1e-6, 64 * math.ulp(max(1.0, expected_proper)))):
            raise ValueError("inertial continuation is discontinuous from its braking cut")
        nominal = self.nominal_plan
        replacement = self.braking_substitution
        receipt = self.propulsion_receipt
        if receipt is not None:
            receipt.__post_init__()
        if nominal is not None:
            nominal.__post_init__()
            if (not nominal.invalidated or nominal.completed
                    or nominal.destination_id != self.destination_id
                    or receipt is not None):
                raise ValueError("inertial nominal history must be invalidated")
            if replacement is not None:
                replacement.__post_init__()
                if (replacement.completed or replacement.paid_plan != nominal
                        or replacement.braking_segment != self.interrupted_segment):
                    raise ValueError("inertial substituted braking history is invalid")
            elif (nominal.phase_index != len(nominal.segments) - 1
                  or nominal.segments[nominal.phase_index] != self.interrupted_segment):
                raise ValueError("inertial nominal braking history is invalid")
        elif (replacement is not None or receipt is None
              or receipt.segment != self.interrupted_segment
              or receipt.destination_id != self.destination_id):
            raise ValueError("inertial independent braking needs its spent receipt")


@dataclass(frozen=True, slots=True)
class PhysicalTransitState:
    """An active maneuver and the original requested destination.

    Segment clocks are local to physical transit; the game clock remains the
    authority for absolute game time. A future engine adapter must check their
    alignment before and after each causal cut.
    """

    active_segment: MotionSegment
    elapsed_galactic_s: float
    original_destination_id: str
    intent: NavigationIntent
    safety_braking: bool = False
    braking_started: bool = False
    replan_required: bool = False
    propulsion_authorization: PropulsionAuthorization | None = None
    nominal_plan: NominalTravelState | None = None
    pending_transition: PendingTransition | None = None
    nominal_braking_substitution: NominalBrakingSubstitution | None = None
    inertial_continuation: InertialContinuation | None = None

    def __post_init__(self) -> None:
        if (not math.isfinite(self.elapsed_galactic_s)
                or not 0 <= self.elapsed_galactic_s <= self.active_segment.duration_galactic_s):
            raise ValueError("physical transit elapsed time must lie within its segment")
        if not self.original_destination_id:
            raise ValueError("physical transit requires its original destination")
        if self.intent not in ("accelerate", "brake", "coast"):
            raise ValueError("unknown physical navigation intent")
        acceleration = self.active_segment.proper_acceleration_m_s2
        if self.active_segment.duration_galactic_s > 0 and (
            (self.intent == "accelerate" and acceleration <= 0)
            or (self.intent == "brake" and acceleration >= 0)
            or (self.intent == "coast" and acceleration != 0)
        ):
            raise ValueError("physical navigation intent disagrees with its segment")
        if self.intent == "brake" and not self.braking_started:
            raise ValueError("active braking requires braking_started")
        if self.safety_braking and not self.braking_started:
            raise ValueError("safety braking requires braking_started")
        if self.pending_transition not in (None, "safety_brake", "inertia"):
            raise ValueError("unknown pending physical transition")
        if self.pending_transition is not None and not self.replan_required:
            raise ValueError("pending physical transition requires replanning")
        if self.pending_transition == "safety_brake" and (self.intent not in {"accelerate", "coast"}
                                                          or self.safety_braking):
            raise ValueError("pending safety braking is not active braking")
        if self.pending_transition == "inertia" and self.intent != "brake":
            raise ValueError("pending inertia requires an interrupted braking segment")
        if self.propulsion_authorization is not None and (
            self.propulsion_authorization.segment != self.active_segment
            or self.propulsion_authorization.destination_id != self.original_destination_id
        ):
            raise ValueError("propulsion authorization is bound to this segment and destination")
        nominal = self.nominal_plan
        if nominal is not None:
            nominal.__post_init__()  # Also validate plans restored from a pickle.
        inertia = self.inertial_continuation
        if inertia is not None:
            inertia.__post_init__()
            if (self.active_segment != inertia.current_segment
                    or self.original_destination_id != inertia.destination_id
                    or self.intent != "coast" or not self.braking_started
                    or not self.replan_required or self.pending_transition is not None
                    or self.safety_braking or self.propulsion_authorization is not None
                    or self.nominal_braking_substitution is not None
                    or nominal != inertia.nominal_plan):
                raise ValueError("inertial motion cannot reuse braking authorization")
            return
        substitution = self.nominal_braking_substitution
        if substitution is not None:
            substitution.__post_init__()
            if (nominal != substitution.paid_plan
                    or self.original_destination_id != substitution.destination_id
                    or self.active_segment != substitution.braking_segment
                    or self.intent != "brake" or not self.safety_braking
                    or not self.braking_started or not self.replan_required
                    or self.propulsion_authorization is not None
                    or self.pending_transition not in (None, "inertia")
                    or (substitution.completed != (
                        self.elapsed_galactic_s == self.active_segment.duration_galactic_s))):
                raise ValueError("substituted braking is not bound to its paid journey and segment")
        if nominal is not None and substitution is None and (
            self.propulsion_authorization is not None
            or nominal.destination_id != self.original_destination_id
            or nominal.segments[nominal.phase_index] != self.active_segment
            or self.intent != ("accelerate" if nominal.phase_index == 0 else
                               "brake" if nominal.phase_index == len(nominal.segments) - 1 else "coast")
            or (nominal.completed and self.elapsed_galactic_s != self.active_segment.duration_galactic_s)
        ):
            raise ValueError("nominal plan does not authorize this physical phase")
        if self.pending_transition is not None and nominal is not None and not nominal.invalidated:
            raise ValueError("pending transition must invalidate the nominal plan")
        if self.safety_braking and substitution is None:
            raise ValueError("safety braking requires a one-use nominal substitution")

    @property
    def motion(self) -> MotionState:
        """Current physical position, speed and clocks, derived from the segment."""
        return sample_segment(self.active_segment, self.elapsed_galactic_s)

    def __getstate__(self) -> list[object]:
        return [getattr(self, spec.name) for spec in fields(self)]

    def __setstate__(self, values: list[object]) -> None:
        """Load physical payloads since 01B3H-A, defaulting newer fields."""
        specs = fields(self)
        if not isinstance(values, (list, tuple)) or len(values) not in (8, 9, 10, 11, len(specs)):
            raise ValueError("unsupported physical transit pickle payload")
        for spec, value in zip(specs, values):
            object.__setattr__(self, spec.name, value)
        if len(values) == 8:
            object.__setattr__(self, "nominal_plan", None)
        if len(values) < 10:
            object.__setattr__(self, "pending_transition", None)
        if len(values) < len(specs):
            object.__setattr__(self, "inertial_continuation", None)
        if len(values) < 11:
            object.__setattr__(self, "nominal_braking_substitution", None)
        self.__post_init__()
