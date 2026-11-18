"""Conditional, analytic ship-electricity forecasts in proper seconds.

Snapshots are read-only assumptions, not an alternative electrical simulator.
The productive engine alone performs shedding, job effects and state writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from retorno.config.balance import Balance
from retorno.core.nav_boundaries import TemporalLimit, ordinary_wear_rate
from retorno.model.systems import ShipSystem, SystemState


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def power_quality_components(
    energy_kwh: float, capacity_kwh: float, generation_kw: float, load_kw: float,
    discharge_max_kw: float, distribution_state: SystemState | None,
    quality_offset: float, *, god_active: bool = False,
) -> tuple[float, float]:
    """Productive quality and deficit ratio under a fixed electrical state."""
    if god_active:
        return 1.0, 0.0
    soc = energy_kwh / capacity_kwh if capacity_kwh > 0 else 0.0
    q_soc = _clamp((soc - 0.10) / (0.50 - 0.10))
    deficit = max(0.0, load_kw - generation_kw)
    deficit_ratio = (_clamp(deficit / discharge_max_kw) if discharge_max_kw > 0 else 1.0)
    q_def = 1.0 - 0.7 * deficit_ratio
    quality = 0.6 * q_soc + 0.4 * q_def
    if distribution_state == SystemState.CRITICAL:
        quality -= 0.20
    elif distribution_state in (SystemState.DAMAGED, SystemState.LIMITED):
        quality -= 0.10
    quality += quality_offset
    return _clamp(quality), deficit_ratio


def battery_energy_after(
    energy_kwh: float, capacity_kwh: float, charge_max_kw: float,
    discharge_max_kw: float, eta_charge: float, eta_discharge: float,
    generation_kw: float, load_kw: float, proper_s: float,
    *, god_active: bool = False,
) -> float:
    """The productive battery clamp and efficiencies for constant powers."""
    if not math.isfinite(proper_s) or proper_s < 0:
        raise ValueError("proper_s must be finite and nonnegative")
    if god_active:
        return energy_kwh
    net = generation_kw - load_kw
    if net >= 0:
        delta = min(net, charge_max_kw) * proper_s / 3600.0 * eta_charge
        return min(capacity_kwh, energy_kwh + delta)
    delta = min(-net, discharge_max_kw) * proper_s / 3600.0 / max(eta_discharge, 1e-6)
    return max(0.0, energy_kwh - delta)


@dataclass(frozen=True, slots=True)
class PowerSnapshot:
    """Minimal fixed electrical inputs plus signatures of invalidating state."""

    generation_kw: float
    load_kw: float
    energy_kwh: float
    capacity_kwh: float
    charge_max_kw: float
    discharge_max_kw: float
    eta_charge: float
    eta_discharge: float
    sampled_quality: float
    sampled_deficit_ratio: float
    brownout: bool
    brownout_sustained_s: float
    low_q_shed_timer_s: float
    quality_offset: float
    distribution_state: SystemState | None
    god_active: bool
    op_mode: str
    installed_modules: tuple[str, ...]
    system_signature: tuple[tuple[str, float, SystemState, bool, float], ...]
    job_signature: tuple[tuple[str, str, float], ...]

    def __post_init__(self) -> None:
        nonnegative = (
            self.generation_kw, self.load_kw, self.energy_kwh, self.capacity_kwh,
            self.charge_max_kw, self.discharge_max_kw, self.eta_charge,
            self.eta_discharge, self.brownout_sustained_s, self.low_q_shed_timer_s,
        )
        if any(not math.isfinite(v) or v < 0 for v in nonnegative):
            raise ValueError("electrical values must be finite and nonnegative")
        if self.energy_kwh > self.capacity_kwh:
            raise ValueError("battery energy exceeds capacity")
        if (not math.isfinite(self.quality_offset)
                or not 0 <= self.sampled_quality <= 1
                or not 0 <= self.sampled_deficit_ratio <= 1):
            raise ValueError("invalid sampled quality or modifier")


def capture_power_snapshot(state, generation_kw: float, load_kw: float) -> PowerSnapshot:
    """Read productive powers and the small set of assumptions they rely on."""
    power = state.ship.power
    distribution = state.ship.systems.get("energy_distribution")
    return PowerSnapshot(
        generation_kw, load_kw, power.e_batt_kwh, power.e_batt_max_kwh,
        power.p_charge_max_kw, power.p_discharge_max_kw,
        power.eta_charge, power.eta_discharge, power.power_quality,
        power.deficit_ratio, power.brownout, power.brownout_sustained_s,
        power.low_q_shed_timer_s, power.quality_offset,
        distribution.state if distribution else None, state.os.god_active,
        state.ship.op_mode, tuple(state.ship.installed_modules),
        tuple((key, system.health, system.state, system.forced_offline, system.p_nom_kw)
              for key, system in sorted(state.ship.systems.items())),
        tuple((key, job.status.value, job.power_draw_kw)
              for key, job in sorted(state.jobs.jobs.items())),
    )


def invalidation_reasons(
    before: PowerSnapshot, after: PowerSnapshot, *, elapsed_proper_s: float | None = None,
) -> tuple[str, ...]:
    """Changes requiring a fresh forecast; optionally check expected battery energy."""
    reasons = []
    for label, fields in (
        ("power_changed", ("generation_kw", "load_kw", "charge_max_kw", "discharge_max_kw",
                           "eta_charge", "eta_discharge", "capacity_kwh", "quality_offset")),
        ("operation_changed", ("god_active", "op_mode", "distribution_state")),
        ("modules_changed", ("installed_modules",)),
        ("systems_changed", ("system_signature",)),
        ("jobs_changed", ("job_signature",)),
        ("regulation_state_changed", ("brownout", "brownout_sustained_s",
                                      "low_q_shed_timer_s")),
    ):
        if any(getattr(before, name) != getattr(after, name) for name in fields):
            reasons.append(label)
    if elapsed_proper_s is not None:
        expected = energy_at(before, elapsed_proper_s)
        if not math.isclose(after.energy_kwh, expected, rel_tol=1e-12, abs_tol=1e-12):
            reasons.append("battery_energy_changed_unexpectedly")
    return tuple(reasons)


def battery_rate_kwh_per_proper_s(snapshot: PowerSnapshot) -> float:
    if snapshot.god_active:
        return 0.0
    net = snapshot.generation_kw - snapshot.load_kw
    if net >= 0:
        return min(net, snapshot.charge_max_kw) * snapshot.eta_charge / 3600.0
    return -min(-net, snapshot.discharge_max_kw) / max(snapshot.eta_discharge, 1e-6) / 3600.0


def energy_at(snapshot: PowerSnapshot, proper_s: float) -> float:
    return battery_energy_after(
        snapshot.energy_kwh, snapshot.capacity_kwh,
        snapshot.charge_max_kw, snapshot.discharge_max_kw,
        snapshot.eta_charge, snapshot.eta_discharge,
        snapshot.generation_kw, snapshot.load_kw, proper_s,
        god_active=snapshot.god_active,
    )


def quality_at(snapshot: PowerSnapshot, proper_s: float) -> float:
    return power_quality_components(
        energy_at(snapshot, proper_s), snapshot.capacity_kwh,
        snapshot.generation_kw, snapshot.load_kw, snapshot.discharge_max_kw,
        snapshot.distribution_state, snapshot.quality_offset,
        god_active=snapshot.god_active,
    )[0]


def _time_to_energy(snapshot: PowerSnapshot, target_kwh: float) -> float | None:
    rate = battery_rate_kwh_per_proper_s(snapshot)
    if rate == 0:
        return None
    # Inverting a quality value can differ from the propagated energy by a
    # couple of representable floats. This is only a rounding allowance, not
    # a physical time tolerance or an artificial clock advance.
    at_equality = abs(target_kwh - snapshot.energy_kwh) <= 2 * max(
        math.ulp(target_kwh), math.ulp(snapshot.energy_kwh))
    if at_equality:
        # Equality is a mathematical cut. No cut is emitted when the battery
        # is already saturated and the nominal rate points outside its range.
        if (target_kwh == 0 and rate < 0
                or target_kwh == snapshot.capacity_kwh and rate > 0):
            return None
        return 0.0
    seconds = (target_kwh - snapshot.energy_kwh) / rate
    return seconds if math.isfinite(seconds) and seconds > 0 else None


def _quality_target_energy(snapshot: PowerSnapshot, quality: float) -> float | None:
    if snapshot.god_active or snapshot.capacity_kwh == 0:
        return None
    _, deficit = power_quality_components(
        snapshot.energy_kwh, snapshot.capacity_kwh,
        snapshot.generation_kw, snapshot.load_kw, snapshot.discharge_max_kw,
        snapshot.distribution_state, snapshot.quality_offset,
    )
    penalty = (0.20 if snapshot.distribution_state == SystemState.CRITICAL else
               0.10 if snapshot.distribution_state in (SystemState.DAMAGED, SystemState.LIMITED) else 0.0)
    base = 0.4 * (1.0 - 0.7 * deficit) - penalty + snapshot.quality_offset
    soc = 0.10 + (quality - base) / 1.5
    if not 0.10 <= soc <= 0.50:
        return None
    return soc * snapshot.capacity_kwh


@dataclass(frozen=True, slots=True)
class ResolvedElectricalLimit:
    """A zero limit handled at this instant for one immutable snapshot.

    Direction is -1/1 for a mathematical crossing and 0 for a regulation
    check. It distinguishes a reversal at the same threshold and never
    suppresses a later positive-time crossing.
    """

    kind: str
    direction: int
    snapshot: PowerSnapshot


_MATHEMATICAL_LIMITS = frozenset({
    "battery_empty", "soc_10_percent", "soc_50_percent", "battery_full",
    "quality_025", "quality_040", "quality_055",
})


def resolve_electrical_limit(
    snapshot: PowerSnapshot, limit: TemporalLimit,
) -> ResolvedElectricalLimit:
    """Mark a selected zero cut handled after the caller resolves its meaning.

    This is a pure marker. It does not execute regulation or change the clock.
    The caller retains it only at the current instant. A different snapshot
    cannot consume this marker, even if the kind and direction match.
    """
    if limit not in power_limits(snapshot) or limit.time_s != 0:
        raise ValueError("limit must be a pending zero electrical limit")
    rate = battery_rate_kwh_per_proper_s(snapshot)
    direction = (1 if rate > 0 else -1) if limit.kind in _MATHEMATICAL_LIMITS else 0
    return ResolvedElectricalLimit(limit.kind, direction, snapshot)


def power_limits(
    snapshot: PowerSnapshot, *, resolved: frozenset[ResolvedElectricalLimit] = frozenset(),
) -> tuple[TemporalLimit, ...]:
    """Conditional proper-time boundaries; no regulation or RNG is executed.

    ``resolved`` is scoped to this instant; each marker binds its snapshot.
    Only processed zero limits are filtered. Future crossings remain visible.
    """
    if snapshot.god_active:
        return ()
    limits: list[TemporalLimit] = []
    rate = battery_rate_kwh_per_proper_s(snapshot)

    def add(kind: str, seconds: float | None, *, validity: str = "fixed_electrical_conditions",
            reason: str | None = None) -> None:
        if seconds is not None:
            direction = (1 if rate > 0 else -1) if kind in _MATHEMATICAL_LIMITS else 0
            if seconds == 0 and ResolvedElectricalLimit(kind, direction, snapshot) in resolved:
                return
            limits.append(TemporalLimit(kind, "proper", seconds, validity=validity,
                                        uncertainty_reason=reason))

    soc = snapshot.energy_kwh / snapshot.capacity_kwh if snapshot.capacity_kwh > 0 else 0.0
    available = snapshot.discharge_max_kw if soc > 0 else 0.0
    capacity = snapshot.generation_kw + available
    q0 = quality_at(snapshot, 0.0)

    def at_quality_boundary(threshold: float) -> bool:
        target = _quality_target_energy(snapshot, threshold)
        return (target is not None
                and .10 * snapshot.capacity_kwh < target < .50 * snapshot.capacity_kwh
                and _time_to_energy(snapshot, target) == 0)

    def below_quality_on_current_side(threshold: float) -> bool:
        at_boundary = at_quality_boundary(threshold)
        return ((q0 < threshold and not (at_boundary and rate > 0))
                or (at_boundary and rate < 0))

    if snapshot.load_kw > capacity:
        add("power_capacity_regulation", 0.0, validity="immediate_regulation_check",
            reason="load_shedding_changes_snapshot")
    at_low_soc_boundary = _time_to_energy(snapshot, .10 * snapshot.capacity_kwh) == 0
    low_soc_post_crossing = at_low_soc_boundary and rate < 0
    low_soc_on_current_side = (0 < soc < 0.10 and not (at_low_soc_boundary and rate > 0))
    if (low_soc_on_current_side or low_soc_post_crossing) and snapshot.load_kw > snapshot.generation_kw:
        add("low_soc_regulation", 0.0,
            validity="post_crossing_check" if low_soc_post_crossing else "immediate_regulation_check",
            reason="load_shedding_changes_snapshot")
    collapse_post_crossing = (at_quality_boundary(Balance.POWER_QUALITY_COLLAPSE_THRESHOLD)
                              and rate < 0)
    if below_quality_on_current_side(Balance.POWER_QUALITY_COLLAPSE_THRESHOLD):
        add("quality_collapse_regulation", 0.0,
            validity="post_crossing_check" if collapse_post_crossing else "immediate_regulation_check",
            reason="load_shedding_changes_snapshot")
    for fraction, name in ((0.0, "battery_empty"), (0.10, "soc_10_percent"),
                           (0.50, "soc_50_percent"), (1.0, "battery_full")):
        add(name, _time_to_energy(snapshot, fraction * snapshot.capacity_kwh),
            validity="mathematical_crossing",
            reason="battery_state_or_quality_branch_changes")
    for threshold, name in ((Balance.POWER_QUALITY_COLLAPSE_THRESHOLD, "quality_025"),
                            (Balance.POWER_QUALITY_CRITICAL_THRESHOLD, "quality_040"),
                            (Balance.POWER_QUALITY_BLOCK_THRESHOLD, "quality_055")):
        target = _quality_target_energy(snapshot, threshold)
        if (target is not None and .10 * snapshot.capacity_kwh < target
                < .50 * snapshot.capacity_kwh):
            add(name, _time_to_energy(snapshot, target),
                validity="mathematical_crossing",
                reason="strict_quality_condition_must_be_rechecked")
    shed_condition = below_quality_on_current_side(Balance.POWER_QUALITY_CRITICAL_THRESHOLD) and (
        snapshot.load_kw > snapshot.generation_kw or snapshot.load_kw > capacity)
    if shed_condition:
        add("low_quality_shed_timer", max(0.0, Balance.POWER_QUALITY_SHED_INTERVAL_S
                                           - snapshot.low_q_shed_timer_s),
            reason="load_shedding_changes_snapshot")
    elif snapshot.low_q_shed_timer_s > 0:
        add("low_quality_timer_reset", 0.0, validity="immediate_regulation_check")
    brownout_now = snapshot.load_kw > capacity
    if brownout_now:
        if snapshot.brownout_sustained_s < Balance.BROWNOUT_SUSTAINED_AFTER_S:
            add("brownout_sustained", Balance.BROWNOUT_SUSTAINED_AFTER_S
                - snapshot.brownout_sustained_s, reason="wear_multiplier_changes")
    elif snapshot.brownout_sustained_s > 0:
        add("brownout_timer_reset", 0.0, validity="immediate_regulation_check")
    return tuple(sorted(limits, key=lambda limit: (limit.time_s, limit.kind)))


@dataclass(frozen=True, slots=True)
class QualityIntegral:
    start: float
    end: float
    quality_proper_s: float
    deficit_proper_s: float
    end_energy_kwh: float


def integrate_quality(snapshot: PowerSnapshot, proper_s: float) -> QualityIntegral:
    """Exact piecewise-affine Q integral, including SOC and Q clamps."""
    if not math.isfinite(proper_s) or proper_s < 0:
        raise ValueError("proper_s must be finite and nonnegative")
    rate = battery_rate_kwh_per_proper_s(snapshot)
    cuts = [0.0, proper_s]
    if rate:
        energies = [0.0, .10 * snapshot.capacity_kwh, .50 * snapshot.capacity_kwh,
                    snapshot.capacity_kwh]
        for q in (0.0, 1.0):
            target = _quality_target_energy(snapshot, q)
            if target is not None:
                energies.append(target)
        for energy in energies:
            at = (energy - snapshot.energy_kwh) / rate
            if 0 < at < proper_s:
                cuts.append(at)
    cuts = sorted(set(cuts))
    integral = sum((quality_at(snapshot, left) + quality_at(snapshot, right))
                   * (right - left) / 2.0 for left, right in zip(cuts, cuts[1:]))
    return QualityIntegral(quality_at(snapshot, 0.0), quality_at(snapshot, proper_s),
                           integral, proper_s - integral, energy_at(snapshot, proper_s))


def integrated_wear(
    system: ShipSystem, snapshot: PowerSnapshot, proper_s: float,
    internal_rad: float, *, in_transit: bool, op_mode: str,
    brownout_sustained: bool = False,
) -> float:
    """Analytic ordinary wear for a caller-verified event-free interval."""
    integrated = integrate_quality(snapshot, proper_s)
    at_zero = ordinary_wear_rate(system, 0.0, brownout_sustained, internal_rad,
                                 in_transit=in_transit, op_mode=op_mode,
                                 god_active=snapshot.god_active)
    at_one = ordinary_wear_rate(system, 1.0, brownout_sustained, internal_rad,
                                in_transit=in_transit, op_mode=op_mode,
                                god_active=snapshot.god_active)
    return at_zero * proper_s + (at_one - at_zero) * integrated.quality_proper_s
