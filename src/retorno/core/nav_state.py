"""Provisional physical-transit state for the internal navigation integration.

The active segment is the single source for physical position, speed and
proper time. No playable action creates this state in NAV-BRAKE-01B3C.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from retorno.core.nav_physics import MotionSegment, MotionState, sample_segment


NavigationIntent = Literal["accelerate", "brake", "coast"]


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
        if self.propulsion_authorization is not None and (
            self.propulsion_authorization.segment != self.active_segment
            or self.propulsion_authorization.destination_id != self.original_destination_id
        ):
            raise ValueError("propulsion authorization is bound to this segment and destination")

    @property
    def motion(self) -> MotionState:
        """Current physical position, speed and clocks, derived from the segment."""
        return sample_segment(self.active_segment, self.elapsed_galactic_s)
