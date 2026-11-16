"""Pure, conditional temporal limits for a future navigation coordinator.

Proper-time limits are never converted to galactic time here. Predictions must
be discarded when their sampled wear, job or propulsion conditions change.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from retorno.config.balance import Balance
from retorno.model.jobs import JobManagerState, JobStatus, JobType
from retorno.model.ship import ShipState
from retorno.model.systems import ShipSystem, SystemState


@dataclass(frozen=True, slots=True)
class TemporalLimit:
    """A navigation-relevant limit, in seconds of ``domain`` from now.

    ``time_s=None`` means no calculable instant. ``validity`` states the
    assumptions; ``uncertainty_reason`` prevents a candidate job completion
    from being mistaken for a guaranteed outcome. A health threshold at time
    zero is mathematical equality, not a universal loss of braking capacity.
    """

    kind: str
    domain: str
    time_s: float | None
    system_id: str | None = None
    job_id: str | None = None
    validity: str = ""
    uncertainty_reason: str | None = None


def _finite_nonnegative(value: float, name: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


def ordinary_wear_rate(
    system: ShipSystem,
    power_quality: float,
    brownout_sustained: bool,
    internal_rad: float,
    *,
    in_transit: bool,
    op_mode: str,
    god_active: bool = False,
) -> float:
    """Current ordinary health loss per proper second under fixed conditions.

    Shares the productive factors in ``Engine._apply_degradation``. The
    internal radiation factor is clamped to [0, 1], as in the existing engine.
    This is a point-rate, not an integrated forecast for varying conditions.
    """
    if god_active:
        return 0.0
    _finite_nonnegative(system.base_decay_per_s, "base_decay_per_s")
    for value, name in ((system.k_power, "k_power"), (system.k_rad, "k_rad"),
                        (power_quality, "power_quality"), (internal_rad, "internal_rad")):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if not 0.0 <= power_quality <= 1.0 or internal_rad < 0.0:
        raise ValueError("power_quality or internal_rad out of range")
    internal_rad_norm = min(1.0, max(0.0, internal_rad / Balance.R_REF))
    wear_mult = Balance.TRANSIT_WEAR_MULT_NORMAL if in_transit and op_mode != "CRUISE" else 1.0
    s_factor = 1.0 + system.k_power * (1.0 - power_quality) + system.k_rad * internal_rad_norm
    if brownout_sustained:
        if system.system_id == "energy_distribution":
            s_factor *= Balance.BROWNOUT_DEGRADE_MULT_DISTRIBUTION
        elif system.system_id == "power_core":
            s_factor *= Balance.BROWNOUT_DEGRADE_MULT_POWER_CORE
    rate = system.base_decay_per_s * s_factor * wear_mult
    if not math.isfinite(rate) or rate < 0.0:
        raise ValueError("ordinary wear rate must be finite and nonnegative")
    return rate


def thrust_available(ship: ShipState) -> bool:
    """Whether the *existing* engine classifier permits normal thrust now.

    This says nothing about target selection, speed ceiling, physical speed or
    fuel. It is not the future emergency-braking capability classifier for
    health in [15%, 35%). No new electrical quality threshold is imposed.
    Engine dependencies use the existing forced-offline/operating-state contract.
    """
    return ship.engine_operating_state() not in {SystemState.CRITICAL, SystemState.OFFLINE}


def acceleration_available(ship: ShipState) -> bool:
    """Whether normal engine integrity and isolation permit acceleration.

    Fuel, physical speed and destination feasibility remain separate checks.
    """
    return thrust_available(ship)


def braking_available(ship: ShipState) -> bool:
    """Whether normal or emergency engine integrity permits braking.

    The lower boundary is inclusive. Preserve the existing operating-state
    classifier, whose CRITICAL band covers emergency-only integrity.
    """
    engine = ship.systems.get("engines")
    return bool(engine is not None and not engine.forced_offline
                and math.isfinite(engine.health)
                and engine.health >= Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH)


def predict_engine_health_limit(
    ship: ShipState, wear_rate_per_proper_s: float, *, god_active: bool = False,
) -> TemporalLimit:
    """Predict mathematical arrival at the CRITICAL health threshold.

    The prediction is valid only while this proper-time wear rate remains
    constant. At equality engines are still DAMAGED; the existing CRITICAL
    classification applies immediately after equality if wear continues.
    Future emergency braking below 35% is a separate operational decision.
    This function does not resolve the strict inequality into galactic time.
    """
    return _predict_engine_threshold(
        ship, wear_rate_per_proper_s, Balance.SYSTEM_HEALTH_CRITICAL,
        "engine_health_threshold", "at_threshold_not_yet_critical",
        god_active=god_active,
    )


def predict_engine_braking_limit(
    ship: ShipState, wear_rate_per_proper_s: float, *, god_active: bool = False,
) -> TemporalLimit:
    """Predict equality with the inclusive emergency-braking minimum.

    At equality braking is still available; continuing positive wear removes
    it immediately afterward. The rate must remain fixed until the cut.
    """
    return _predict_engine_threshold(
        ship, wear_rate_per_proper_s, Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH,
        "engine_braking_threshold", "at_threshold_braking_still_available",
        god_active=god_active,
    )


def _predict_engine_threshold(
    ship: ShipState, wear_rate_per_proper_s: float, threshold: float,
    kind: str, at_equality: str, *, god_active: bool,
) -> TemporalLimit:
    _finite_nonnegative(wear_rate_per_proper_s, "wear_rate_per_proper_s")
    engine = ship.systems.get("engines")
    if engine is None:
        return TemporalLimit(kind, "proper", None, "engines",
                             validity="no_engine", uncertainty_reason="engine_missing")
    health = engine.health
    _finite_nonnegative(health, "engine health")
    _finite_nonnegative(engine.health_max_effective, "engine health_max_effective")
    if engine.health_max_effective == 0.0 or health > engine.health_max_effective:
        raise ValueError("engine health outside effective range")
    if health < threshold:
        return TemporalLimit(kind, "proper", None, "engines",
                             validity="already_below_threshold")
    if god_active:
        return TemporalLimit(kind, "proper", None, "engines",
                             validity="god_mode_no_wear")
    if health == threshold:
        return TemporalLimit(kind, "proper", 0.0, "engines", validity=at_equality)
    if wear_rate_per_proper_s == 0.0:
        return TemporalLimit(kind, "proper", None, "engines",
                             validity="no_crossing_at_zero_rate")
    seconds = (health - threshold) / wear_rate_per_proper_s
    if not math.isfinite(seconds):
        raise ValueError("Predicted threshold time exceeds floating-point range")
    return TemporalLimit(kind, "proper", seconds, "engines",
                         validity="constant_wear_conditions")


_PROPULSION_SYSTEMS = frozenset({"engines", "power_core", "energy_distribution"})
_PROPULSION_MODULES = frozenset({
    "engine_speed_upgrade_01",  # physical speed ceiling
    "bus_stabilizer", "aux_battery_cell", "micro_reactor_patch",  # electrical conditions
})


def propulsion_job_limits(jobs: JobManagerState) -> tuple[TemporalLimit, ...]:
    """Return candidate galactic-time boundaries in scheduler order.

    Only RUNNING work has a candidate completion ETA. An eligible QUEUED job
    supplies a time-zero activation *check*, never a completion ETA: the
    productive scheduler may start it and thereby change electrical load.
    Owner/route conflicts and confirmation blocks have no calculable instant.
    All candidates remain conditional on scheduler checks and outcomes.
    """
    limits: list[TemporalLimit] = []
    active = [jobs.jobs[key] for key in jobs.active_job_ids if key in jobs.jobs]
    running_owners = {job.owner_id for job in active
                      if job.status == JobStatus.RUNNING and job.owner_id}
    route_running = any(job.status == JobStatus.RUNNING and job.job_type == JobType.ROUTE_SOLVE
                        for job in active)
    for job_id in jobs.active_job_ids:
        job = jobs.jobs.get(job_id)
        if job is None or job.status not in {JobStatus.RUNNING, JobStatus.QUEUED}:
            continue
        _finite_nonnegative(job.power_draw_kw, "job power_draw_kw")
        target = job.target.id if job.target else None
        direct = (job.job_type in {JobType.REPAIR_SYSTEM, JobType.SELFTEST_REPAIR}
                  and target in _PROPULSION_SYSTEMS)
        module = (job.job_type in {JobType.INSTALL_MODULE, JobType.UNINSTALL_MODULE}
                  and job.params.get("module_id") in _PROPULSION_MODULES)
        load = job.power_draw_kw > 0.0
        if not (direct or module or load):
            continue
        system_id = target if direct else None
        kind = "propulsion_job"
        if job.status == JobStatus.QUEUED:
            blocked = ((job.owner_id and job.owner_id in running_owners)
                       or (job.job_type == JobType.ROUTE_SOLVE and route_running))
            if blocked:
                validity, seconds, reason = "indeterminate", None, "activation_blocked_by_running_job"
            else:
                kind = "job_activation"
                validity, seconds, reason = "queued_activation_candidate", 0.0, "scheduler_may_block_or_interrupt"
                if job.owner_id:
                    running_owners.add(job.owner_id)
                if job.job_type == JobType.ROUTE_SOLVE:
                    route_running = True
        elif job.params.get("awaiting_auto_move_confirmation"):
            validity, seconds, reason = "indeterminate", None, "awaiting_player_confirmation"
        else:
            _finite_nonnegative(job.eta_s, "job eta_s")
            validity, seconds, reason = "running_if_uninterrupted", job.eta_s, "interruption_or_outcome_may_change"
        limits.append(TemporalLimit(kind, "galactic", seconds, system_id,
                                    job_id, validity, reason))
    return tuple(limits)
