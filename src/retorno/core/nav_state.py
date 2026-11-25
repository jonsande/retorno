"""Provisional physical-transit state for the internal navigation integration.

The active segment is the single source for physical position, speed and
proper time. No playable action creates this state in NAV-BRAKE-01B3C.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
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
class RecoveryExecution:
    """One prepaid recovery, retaining the earlier interrupted-brake history."""

    inertial_history: InertialContinuation
    segments: tuple[MotionSegment, ...]
    authorization: PropulsionAuthorization
    phase_index: int = 0
    completed: bool = False
    invalidated: bool = False

    def __post_init__(self) -> None:
        self.inertial_history.__post_init__()
        self.authorization.__post_init__()
        if (len(self.segments) not in (1, 2)
                or not 0 <= self.phase_index < len(self.segments)
                or self.completed and self.invalidated
                or self.completed and self.phase_index != len(self.segments) - 1
                or self.segments[-1].proper_acceleration_m_s2 >= 0
                or self.segments[-1].end_beta != 0
                or self.authorization.segment != self.segments[-1]
                or self.authorization.destination_id != self.inertial_history.destination_id):
            raise ValueError("recovery requires one paid final braking segment")
        if len(self.segments) == 2:
            coast, brake = self.segments
            if (coast.proper_acceleration_m_s2 != 0
                    or sample_segment(coast, coast.duration_galactic_s) != brake.start):
                raise ValueError("recovery coast and brake must be continuous")


@dataclass(frozen=True, slots=True)
class RecoveryInterruption:
    """One spent recovery brake cut; the first brake history stays nested once."""

    execution: RecoveryExecution
    interrupted_elapsed_galactic_s: float
    cut_motion: MotionState
    cause: Literal["engine_integrity_15"] = "engine_integrity_15"

    def __post_init__(self) -> None:
        self.execution.__post_init__()
        brake = self.execution.segments[-1]
        if (not self.execution.invalidated or self.execution.completed
                or self.execution.phase_index != len(self.execution.segments) - 1
                or not math.isfinite(self.interrupted_elapsed_galactic_s)
                or not 0 <= self.interrupted_elapsed_galactic_s < brake.duration_galactic_s
                or self.cut_motion != sample_segment(brake, self.interrupted_elapsed_galactic_s)
                or self.cut_motion.beta <= 0 or self.cause != "engine_integrity_15"):
            raise ValueError("recovery interruption requires a residual-speed paid brake cut")


@dataclass(frozen=True, slots=True)
class RecoveryCoastInterruption:
    """Paid recovery abandoned before its planned brake was ever executed."""

    execution: RecoveryExecution
    interrupted_elapsed_galactic_s: float
    cut_motion: MotionState
    cause: Literal["engine_integrity_15"] = "engine_integrity_15"

    def __post_init__(self) -> None:
        self.execution.__post_init__()
        if (not self.execution.invalidated or self.execution.completed
                or len(self.execution.segments) != 2 or self.execution.phase_index != 0
                or not math.isfinite(self.interrupted_elapsed_galactic_s)
                or not 0 <= self.interrupted_elapsed_galactic_s <= self.execution.segments[0].duration_galactic_s
                or self.cut_motion != sample_segment(
                    self.execution.segments[0], self.interrupted_elapsed_galactic_s)
                or self.cut_motion.beta <= 0 or self.cause != "engine_integrity_15"):
            raise ValueError("recovery coast interruption requires an unexecuted paid brake")


@dataclass(frozen=True, slots=True)
class RecoveryIntent:
    """One explicit, unpaid attempt; a prior cancellation is only history."""

    job_id: str | None
    destination_id: str
    authorized: bool
    max_capsules: float
    deceleration_policy: Literal["historical"] = "historical"
    status: Literal["pending", "used", "cancelled"] = "pending"
    outcome: str | None = None
    attempt_id: int = 1
    previous_cancelled: tuple[int, str | None, str] | None = None
    paid_predecessor_id: int | None = None

    def __post_init__(self) -> None:
        prior = self.previous_cancelled
        if ((self.job_id is not None and (not isinstance(self.job_id, str) or not self.job_id))
                or not self.destination_id or self.authorized is not True
                or isinstance(self.max_capsules, bool)
                or not isinstance(self.max_capsules, (int, float))
                or not math.isfinite(self.max_capsules) or self.max_capsules <= 0
                or self.deceleration_policy != "historical"
                or self.status not in {"pending", "used", "cancelled"}
                or (self.status == "pending") != (self.outcome is None)
                or isinstance(self.attempt_id, bool) or not isinstance(self.attempt_id, int)
                or self.attempt_id < 1
                or (self.paid_predecessor_id is not None and (
                    isinstance(self.paid_predecessor_id, bool)
                    or not isinstance(self.paid_predecessor_id, int)
                    or not 1 <= self.paid_predecessor_id < self.attempt_id))
                or (self.attempt_id == 1) != (prior is None)
                or (prior is not None and (
                    not isinstance(prior, tuple) or len(prior) != 3
                    or not isinstance(prior[0], int) or isinstance(prior[0], bool)
                    or not 1 <= prior[0] < self.attempt_id
                    or (prior[1] is not None and not isinstance(prior[1], str))
                    or not isinstance(prior[2], str) or not prior[2]))):
            raise ValueError("invalid one-use recovery intent")

    def __getstate__(self) -> list[object]:
        return [getattr(self, spec.name) for spec in fields(self)]

    def __setstate__(self, values: list[object]) -> None:
        """Accept C2B2A's seven-field intent without renewing its authority."""
        specs = fields(self)
        if not isinstance(values, (list, tuple)) or len(values) not in (7, 9, len(specs)):
            raise ValueError("unsupported recovery intent pickle payload")
        for spec, value in zip(specs, values):
            object.__setattr__(self, spec.name, value)
        if len(values) == 7:
            object.__setattr__(self, "attempt_id", 1)
            object.__setattr__(self, "previous_cancelled", None)
        if len(values) < 10:
            object.__setattr__(self, "paid_predecessor_id", None)
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class RecoveryAttemptRecord:
    """One detailed, spent recovery receipt; never an active permission."""

    attempt_id: int
    authorization_id: int
    authorization: PropulsionAuthorization
    outcome: Literal["active", "completed", "interrupted_brake", "interrupted_coast"]
    cut_motion: MotionState | None = None
    demonstrated_deceleration_m_s2: float | None = None

    def __post_init__(self) -> None:
        self.authorization.__post_init__()
        if (isinstance(self.attempt_id, bool) or not isinstance(self.attempt_id, int)
                or self.attempt_id < 1 or self.outcome not in {
                    "active", "completed", "interrupted_brake", "interrupted_coast"}
                or isinstance(self.authorization_id, bool)
                or not isinstance(self.authorization_id, int)
                or self.authorization_id < self.attempt_id
                or (self.cut_motion is None) != (self.outcome in {"active", "completed"})
                or (self.demonstrated_deceleration_m_s2 is not None and (
                    not math.isfinite(self.demonstrated_deceleration_m_s2)
                    or self.demonstrated_deceleration_m_s2 <= 0))):
            raise ValueError("invalid bounded recovery attempt")


def _attempt_digest(previous: str, record: RecoveryAttemptRecord) -> str:
    """Deterministic commitment to summaries, not a reconstructible audit log."""
    return hashlib.sha256((previous + "|" + repr(record)).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RecoveryLineage:
    """Fixed two-record window plus monotonic spent IDs and cumulative totals."""

    origin_id: str
    destination_id: str
    attempt_count: int
    interruption_count: int
    capsules_spent: float
    recent: tuple[RecoveryAttemptRecord, ...]
    digest: str
    prefix_digest: str = "0" * 64
    spent_through_authorization_id: int = 0

    def __post_init__(self) -> None:
        if (not self.origin_id or not self.destination_id
                or self.origin_id == self.destination_id
                or isinstance(self.attempt_count, bool)
                or not isinstance(self.attempt_count, int) or self.attempt_count < 1
                or isinstance(self.interruption_count, bool)
                or not isinstance(self.interruption_count, int)
                or not 0 <= self.interruption_count <= self.attempt_count
                or not math.isfinite(self.capsules_spent) or self.capsules_spent <= 0
                or not 1 <= len(self.recent) <= 2
                or self.recent[-1].attempt_id != self.attempt_count
                or self.spent_through_authorization_id != self.recent[-1].authorization_id
                or any(a.attempt_id + 1 != b.attempt_id
                       for a, b in zip(self.recent, self.recent[1:]))
                or any(a.authorization_id >= b.authorization_id
                       for a, b in zip(self.recent, self.recent[1:]))
                or any(r.outcome == "active" for r in self.recent[:-1])
                or any(r.authorization.destination_id != self.destination_id
                       for r in self.recent)
                or len(self.digest) != 64 or len(self.prefix_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.digest + self.prefix_digest)):
            raise ValueError("invalid bounded recovery lineage")
        for record in self.recent:
            record.__post_init__()
        digest = self.prefix_digest
        for record in self.recent:
            digest = _attempt_digest(digest, record)
        if (self.digest != digest
                or self.interruption_count < sum(
                    r.outcome.startswith("interrupted") for r in self.recent)
                or self.capsules_spent < sum(
                    r.authorization.capsules_paid for r in self.recent)
                or (self.attempt_count == len(self.recent) and (
                    self.prefix_digest != "0" * 64
                    or self.interruption_count != sum(
                        r.outcome.startswith("interrupted") for r in self.recent)
                    or not math.isclose(self.capsules_spent, sum(
                        r.authorization.capsules_paid for r in self.recent), rel_tol=1e-12)))):
            raise ValueError("recovery lineage totals disagree with detailed records")

    @classmethod
    def first(cls, origin_id: str, destination_id: str,
              record: RecoveryAttemptRecord) -> RecoveryLineage:
        return cls(origin_id, destination_id, 1,
                   int(record.outcome.startswith("interrupted")),
                   record.authorization.capsules_paid, (record,),
                   _attempt_digest("0" * 64, record),
                   spent_through_authorization_id=record.authorization_id)

    def append(self, record: RecoveryAttemptRecord) -> RecoveryLineage:
        if (record.attempt_id != self.attempt_count + 1
                or record.authorization_id <= self.spent_through_authorization_id
                or self.recent[-1].outcome == "active"):
            raise ValueError("recovery attempt IDs must increase monotonically")
        prefix = (self.prefix_digest if len(self.recent) < 2 else
                  _attempt_digest(self.prefix_digest, self.recent[0]))
        recent = (*self.recent, record)[-2:]
        digest = prefix
        for item in recent:
            digest = _attempt_digest(digest, item)
        return RecoveryLineage(
            self.origin_id, self.destination_id, record.attempt_id,
            self.interruption_count + int(record.outcome.startswith("interrupted")),
            self.capsules_spent + record.authorization.capsules_paid,
            recent, digest, prefix, record.authorization_id)

    def replace_last(self, record: RecoveryAttemptRecord) -> RecoveryLineage:
        if record.attempt_id != self.attempt_count or self.recent[-1].outcome != "active":
            raise ValueError("only the active latest recovery may change outcome")
        records = (*self.recent[:-1], record)
        digest = self.prefix_digest
        for item in records:
            digest = _attempt_digest(digest, item)
        return RecoveryLineage(
            self.origin_id, self.destination_id, self.attempt_count,
            self.interruption_count + int(record.outcome.startswith("interrupted")),
            self.capsules_spent, records, digest, self.prefix_digest,
            self.spent_through_authorization_id)


@dataclass(frozen=True, slots=True)
class SecondRepairEvidence:
    """A productive repair witnessed after the currently interrupted recovery."""

    interruption_kind: Literal["brake", "coast"]
    cut_motion: MotionState
    spent_receipt: PropulsionAuthorization
    job_internal_id: str
    terminal_seq: int
    completed_galactic_s: float
    engine_health_before: float
    engine_health_after: float

    def __post_init__(self) -> None:
        self.spent_receipt.__post_init__()
        if (self.interruption_kind not in {"brake", "coast"}
                or not self.job_internal_id
                or isinstance(self.terminal_seq, bool)
                or not isinstance(self.terminal_seq, int)
                or self.terminal_seq < 1
                or not math.isfinite(self.completed_galactic_s)
                or self.completed_galactic_s < self.cut_motion.galactic_s
                or not math.isfinite(self.engine_health_before)
                or not math.isfinite(self.engine_health_after)
                or not 0 <= self.engine_health_before < self.engine_health_after <= 1):
            raise ValueError("recovery repair evidence requires an applied post-cut repair")


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
    recovery_execution: RecoveryExecution | None = None
    recovery_intent: RecoveryIntent | None = None
    recovery_interruption: RecoveryInterruption | None = None
    recovery_coast_interruption: RecoveryCoastInterruption | None = None
    recovery_lineage: RecoveryLineage | None = None
    second_repair_evidence: SecondRepairEvidence | None = None

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
        if (self.pending_transition == "inertia" and self.intent != "brake"
                and not (self.intent == "coast" and self.recovery_coast_interruption is not None)):
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
        recovery = self.recovery_execution
        armed = self.recovery_intent
        interrupted = self.recovery_interruption
        coast_interrupted = self.recovery_coast_interruption
        lineage = self.recovery_lineage
        evidence = self.second_repair_evidence
        if evidence is not None:
            evidence.__post_init__()
            source = interrupted if interrupted is not None else coast_interrupted
            kind = "brake" if interrupted is not None else "coast"
            if (source is None or evidence.interruption_kind != kind
                    or evidence.cut_motion != source.cut_motion
                    or evidence.spent_receipt != source.execution.authorization):
                raise ValueError("recovery repair evidence belongs to another interruption")
        if lineage is not None:
            lineage.__post_init__()
            if (lineage.destination_id != self.original_destination_id
                    or (recovery is not None and (
                        lineage.recent[-1].outcome != (
                            "interrupted_brake" if interrupted is not None else
                            "interrupted_coast" if coast_interrupted is not None else
                            "completed" if recovery.completed else "active")
                        or lineage.recent[-1].authorization != recovery.authorization))
                    or (recovery is None and (
                        lineage.recent[-1].outcome not in {
                            "interrupted_brake", "interrupted_coast"}
                        or (interrupted is None and coast_interrupted is None)))
                    or ((interrupted is not None or coast_interrupted is not None) and (
                        lineage.recent[-1].outcome != (
                            "interrupted_brake" if interrupted is not None else "interrupted_coast")
                        or lineage.recent[-1].cut_motion != (
                            interrupted.cut_motion if interrupted is not None
                            else coast_interrupted.cut_motion)
                        or lineage.recent[-1].authorization != (
                            interrupted.execution.authorization if interrupted is not None
                            else coast_interrupted.execution.authorization)))
                    or (armed is not None and (
                        armed.attempt_id != lineage.spent_through_authorization_id
                        if armed.status == "used" else
                        armed.paid_predecessor_id != lineage.spent_through_authorization_id))):
                raise ValueError("bounded lineage must match the active recovery")
        if interrupted is not None and coast_interrupted is not None:
            raise ValueError("a recovery cannot fail in both phases")
        if coast_interrupted is not None:
            coast_interrupted.__post_init__()
            history = coast_interrupted.execution.inertial_history
            if (self.original_destination_id != history.destination_id
                    or (recovery is not None and (
                        recovery != coast_interrupted.execution
                        or self.elapsed_galactic_s != coast_interrupted.interrupted_elapsed_galactic_s
                        or self.motion != coast_interrupted.cut_motion))
                    or (recovery is None and (
                        inertia is None or self.pending_transition is not None
                        or inertia.interrupted_segment != history.interrupted_segment
                        or inertia.interrupted_elapsed_galactic_s
                        != history.interrupted_elapsed_galactic_s
                        or inertia.nominal_plan != history.nominal_plan
                        or inertia.braking_substitution != history.braking_substitution
                        or inertia.propulsion_receipt != history.propulsion_receipt
                        or inertia.current_segment.start.galactic_s
                        < coast_interrupted.cut_motion.galactic_s))):
                raise ValueError("abandoned recovery coast must bind its earlier inertia")
        if interrupted is not None:
            interrupted.__post_init__()
            if (self.original_destination_id != interrupted.execution.inertial_history.destination_id
                    or (recovery is not None and recovery != interrupted.execution)
                    or (recovery is not None and (
                        self.elapsed_galactic_s != interrupted.interrupted_elapsed_galactic_s
                        or self.motion != interrupted.cut_motion))
                    or (recovery is None and (
                        inertia is None or self.pending_transition is not None
                        or inertia.interrupted_segment != interrupted.execution.segments[-1]
                        or inertia.interrupted_elapsed_galactic_s
                        != interrupted.interrupted_elapsed_galactic_s
                        or inertia.propulsion_receipt != interrupted.execution.authorization
                        or inertia.nominal_plan is not None
                        or inertia.braking_substitution is not None))):
                raise ValueError("interrupted recovery history must bind the new inertia")
        if armed is not None:
            armed.__post_init__()
            if (armed.destination_id != self.original_destination_id
                    or (recovery is None and inertia is None and interrupted is None
                        and coast_interrupted is None)
                    or (recovery is not None and armed.status != "used")
                    or (recovery is None and armed.status == "used"
                        and interrupted is None and coast_interrupted is None)
                    or ((interrupted is not None or coast_interrupted is not None)
                        and armed.status != "used"
                        and not (recovery is None and armed.job_id is None
                                 and armed.status in {"pending", "cancelled"}))):
                raise ValueError("recovery intent must match its physical history")
        if recovery is not None:
            recovery.__post_init__()
            if (inertia is not None or nominal is not None
                    or self.nominal_braking_substitution is not None
                    or self.propulsion_authorization is not None
                    or self.safety_braking
                    or self.original_destination_id != recovery.inertial_history.destination_id
                    or self.active_segment != recovery.segments[recovery.phase_index]
                    or self.intent != ("brake" if recovery.phase_index == len(recovery.segments) - 1
                                       else "coast")
                    or not self.braking_started
                    or self.pending_transition != (
                        "inertia" if interrupted is not None or coast_interrupted is not None else None)
                    or recovery.invalidated != (interrupted is not None or coast_interrupted is not None)
                    or self.replan_required != recovery.invalidated
                    or recovery.completed != (
                        self.elapsed_galactic_s == self.active_segment.duration_galactic_s
                        and self.intent == "brake")):
                raise ValueError("recovery execution does not match its paid physical phase")
            return
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
        if not isinstance(values, (list, tuple)) or len(values) not in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, len(specs)):
            raise ValueError("unsupported physical transit pickle payload")
        for spec, value in zip(specs, values):
            object.__setattr__(self, spec.name, value)
        if len(values) == 8:
            object.__setattr__(self, "nominal_plan", None)
        if len(values) < 10:
            object.__setattr__(self, "pending_transition", None)
        if len(values) < 12:
            object.__setattr__(self, "inertial_continuation", None)
        if len(values) < 13:
            object.__setattr__(self, "recovery_execution", None)
        if len(values) < 14:
            object.__setattr__(self, "recovery_intent", None)
        if len(values) < 15:
            object.__setattr__(self, "recovery_interruption", None)
        if len(values) < 16:
            object.__setattr__(self, "recovery_coast_interruption", None)
        if len(values) < 17:
            object.__setattr__(self, "recovery_lineage", None)
        if len(values) < 18:
            object.__setattr__(self, "second_repair_evidence", None)
        if len(values) < 11:
            object.__setattr__(self, "nominal_braking_substitution", None)
        self.__post_init__()
