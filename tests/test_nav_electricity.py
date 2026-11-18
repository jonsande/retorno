"""Analytic electrical cuts and wear for a future physical transit adapter."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
import math

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_coordinator import TemporalResolutionError, select_next_boundary
from retorno.core.nav_electricity import (
    battery_energy_after, capture_power_snapshot, energy_at, integrate_quality,
    integrated_wear, invalidation_reasons, power_limits, power_quality_components,
    quality_at, resolve_electrical_limit,
)
from retorno.core.nav_physics import galactic_time_at_proper, plan_travel
from retorno.model.jobs import Job, JobStatus, JobType, TargetRef
from retorno.model.systems import SystemState


@pytest.fixture
def state():
    game = create_initial_state_sandbox(seed=613)
    game.ship.drones.clear()
    game.jobs.jobs.clear()
    game.jobs.active_job_ids.clear()
    for system in game.ship.systems.values():
        system.health = 1.0
        system.state = SystemState.NOMINAL
        system.forced_offline = False
        system.p_nom_kw = 0.0
    power = game.ship.power
    power.e_batt_kwh = 40.0
    power.e_batt_max_kwh = 100.0
    power.p_charge_max_kw = 20.0
    power.p_discharge_max_kw = 20.0
    power.eta_charge = power.eta_discharge = 1.0
    power.quality_offset = 0.0
    power.power_quality = 0.85
    power.deficit_ratio = 0.5
    power.brownout_sustained_s = power.low_q_shed_timer_s = 0.0
    return game


def snapshot(state, generation=10.0, load=20.0, energy=40.0, **changes):
    state.ship.power.e_batt_kwh = energy
    return replace(capture_power_snapshot(state, generation, load), **changes)


def times(snapshot):
    return {limit.kind: limit.time_s for limit in power_limits(snapshot)}


def test_discharge_charge_balance_and_efficiencies(state):
    drain = snapshot(state, energy=40, eta_discharge=.8)
    assert energy_at(drain, 3600) == pytest.approx(27.5)
    assert times(drain)["soc_10_percent"] == pytest.approx(8640)
    charge = snapshot(state, generation=40, load=10, energy=40, eta_charge=.75)
    assert energy_at(charge, 3600) == pytest.approx(55)
    assert times(charge)["battery_full"] == pytest.approx(14400)
    balanced = snapshot(state, generation=10, load=10, energy=40)
    assert energy_at(balanced, 1e9) == 40
    assert not any(k.startswith("soc_") or k.startswith("battery_") for k in times(balanced))


def test_empty_full_soc_thresholds_and_exact_equalities(state):
    drain = snapshot(state, generation=0, load=20, energy=60)
    got = times(drain)
    assert got["soc_50_percent"] == pytest.approx(1800)
    assert got["soc_10_percent"] == pytest.approx(9000)
    assert got["battery_empty"] == pytest.approx(10800)
    assert energy_at(drain, 1e8) == 0
    at_ten = snapshot(state, generation=0, load=20, energy=10)
    assert times(at_ten)["soc_10_percent"] == 0
    assert next(limit for limit in power_limits(at_ten)
                if limit.kind == "low_soc_regulation").validity == "post_crossing_check"
    at_zero = snapshot(state, generation=20, load=0, energy=0)
    assert times(at_zero)["battery_empty"] == 0
    at_full = snapshot(state, generation=0, load=20, energy=100)
    assert times(at_full)["battery_full"] == 0
    saturated = snapshot(state, generation=20, load=0, energy=100)
    assert "battery_full" not in times(saturated)
    assert energy_at(saturated, 1e8) == 100


def test_quality_crossings_and_strict_conditions(state):
    # No deficit: Q = 0.4 + 1.5*(SOC - 0.1) in the sloping SOC band.
    drain = snapshot(state, generation=0, load=20, energy=40,
                     discharge_max_kw=100, quality_offset=-.1)
    # With deficit ratio .2, Q = .244 + 1.5*(SOC-.1).
    got = times(drain)
    assert got["quality_055"] == pytest.approx((40 - (10 + (.55 - .244)/.015)) / 20 * 3600)
    assert got["quality_040"] > got["quality_055"]
    assert got["quality_025"] > got["quality_040"]
    at_q = replace(drain, energy_kwh=10 + (.55 - .244)/.015)
    assert times(at_q)["quality_055"] == pytest.approx(0, abs=1e-10)
    assert quality_at(at_q, 0) == pytest.approx(.55)
    assert power_limits(at_q)[0].domain == "proper"


def test_immediate_regulation_timers_and_brownout(state):
    low = snapshot(state, generation=0, load=20, energy=5)
    assert times(low)["low_soc_regulation"] == 0
    collapse = snapshot(state, generation=0, load=20, energy=5,
                        distribution_state=SystemState.CRITICAL)
    assert times(collapse)["quality_collapse_regulation"] == 0
    overload = snapshot(state, generation=0, load=30, energy=40,
                        low_q_shed_timer_s=3, brownout_sustained_s=7)
    assert times(overload)["power_capacity_regulation"] == 0
    assert times(overload)["brownout_sustained"] == 23
    assert "brownout_sustained" not in times(replace(overload, brownout_sustained_s=30))
    assert next(limit for limit in power_limits(overload)
                if limit.kind == "power_capacity_regulation").uncertainty_reason == "load_shedding_changes_snapshot"
    timer = snapshot(state, generation=0, load=20, energy=20,
                     low_q_shed_timer_s=3, discharge_max_kw=20)
    assert times(timer)["low_quality_shed_timer"] == 7
    reset = replace(timer, generation_kw=20, load_kw=20)
    assert times(reset)["low_quality_timer_reset"] == 0
    assert times(replace(overload, generation_kw=40))["brownout_timer_reset"] == 0


def test_invalidation_for_jobs_repairs_modules_generation_and_energy(state):
    before = snapshot(state)
    state.jobs.jobs["J1"] = Job("J1", JobType.REPAIR_SYSTEM, JobStatus.RUNNING, 5,
                                 target=TargetRef("ship_system", "engines"), power_draw_kw=3)
    after_job = capture_power_snapshot(state, 10, 23)
    assert set(invalidation_reasons(before, after_job)) == {"power_changed", "jobs_changed"}
    state.ship.systems["engines"].health = .8
    after_repair = capture_power_snapshot(state, 10, 23)
    assert "systems_changed" in invalidation_reasons(after_job, after_repair)
    state.ship.installed_modules.append("engine_speed_upgrade_01")
    after_module = capture_power_snapshot(state, 12, 23)
    assert {"modules_changed", "power_changed"} <= set(invalidation_reasons(after_repair, after_module))
    state.ship.power.e_batt_kwh = 39
    changed_energy = capture_power_snapshot(state, 10, 20)
    assert "battery_energy_changed_unexpectedly" in invalidation_reasons(before, changed_energy,
                                                                           elapsed_proper_s=0)
    assert "regulation_state_changed" in invalidation_reasons(
        before, replace(before, brownout_sustained_s=1))


def test_quality_integral_and_independent_wear_reference(state):
    # With 10 kW deficit and 20 kW discharge, Q = .26 + 1.5*(SOC-.1).
    snap = snapshot(state, generation=10, load=20, energy=40)
    result = integrate_quality(snap, 3600)
    assert result.start == pytest.approx(.71)
    assert result.end == pytest.approx(.56)
    assert result.quality_proper_s == pytest.approx(3600 * (.71 + .56) / 2)
    assert result.deficit_proper_s == pytest.approx(3600 * (1 - .635))
    assert result.end_energy_kwh == 30
    system = state.ship.systems["engines"]
    system.base_decay_per_s = .0001
    system.k_power = .3
    system.k_rad = .4
    rad = Balance.R_REF / 2
    expected = .0001 * 3600 * (1 + .3 * (1 - .635) + .4 * .5)
    assert integrated_wear(system, snap, 3600, rad, in_transit=False,
                           op_mode="CRUISE") == pytest.approx(expected)


def test_piecewise_clamps_subdivision_and_long_horizon(state):
    snap = snapshot(state, generation=0, load=20, energy=40,
                    discharge_max_kw=20, quality_offset=.7)
    whole = integrate_quality(snap, 20000)
    assert whole.end_energy_kwh == 0
    assert 0 <= whole.end <= 1
    left = integrate_quality(snap, 7000)
    right_snap = replace(snap, energy_kwh=left.end_energy_kwh)
    right = integrate_quality(right_snap, 13000)
    assert whole.quality_proper_s == pytest.approx(left.quality_proper_s + right.quality_proper_s)
    assert whole.deficit_proper_s == pytest.approx(left.deficit_proper_s + right.deficit_proper_s)
    charge = snapshot(state, generation=100, load=0, energy=1, quality_offset=-1)
    assert integrate_quality(charge, 1e7).end_energy_kwh == 100


def test_brownout_wear_multiplier_uses_shared_rate(state):
    snap = snapshot(state, generation=10, load=20, energy=40)
    system = state.ship.systems["energy_distribution"]
    system.base_decay_per_s = .0001
    system.k_power = .3
    system.k_rad = 0
    expected = .0001 * 3600 * (1 + .3 * (1 - .635))
    expected *= Balance.BROWNOUT_DEGRADE_MULT_DISTRIBUTION
    assert integrated_wear(system, snap, 3600, 0, in_transit=False,
                           op_mode="CRUISE", brownout_sustained=True) == pytest.approx(expected)


def test_god_purity_determinism_and_invalid_inputs(state):
    snap = snapshot(state, god_active=True)
    frozen = asdict(snap)
    rng = deepcopy(state.meta.rng_counter)
    assert power_limits(snap) == ()
    assert energy_at(snap, 1e9) == 40
    assert integrate_quality(snap, 100).quality_proper_s == 100
    assert integrated_wear(state.ship.systems["engines"], snap, 100, 0,
                           in_transit=True, op_mode="NORMAL") == 0
    assert power_limits(snap) == power_limits(snap)
    assert asdict(snap) == frozen and state.meta.rng_counter == rng
    with pytest.raises(FrozenInstanceError):
        snap.energy_kwh = 5
    for bad in (-1, math.nan, math.inf):
        with pytest.raises(ValueError):
            energy_at(snap, bad)
        with pytest.raises(ValueError):
            integrate_quality(snap, bad)
    with pytest.raises(ValueError):
        replace(snap, energy_kwh=101)
    assert battery_energy_after(0, 100, 20, 20, 1, 1, 0, 20, 1000) == 0
    zero = snapshot(state, generation=0, load=0, energy=0, capacity_kwh=0,
                    charge_max_kw=0, discharge_max_kw=0, god_active=False)
    assert energy_at(zero, 1e9) == 0
    assert integrate_quality(zero, 1e-12).quality_proper_s >= 0


@pytest.mark.parametrize("generation,load,expected_deficit", [(20, 10, 0), (10, 20, .5)])
def test_productive_electricity_matches_in_valid_interval(state, generation, load, expected_deficit):
    engine = Engine()
    state.ship.systems["core_os"].p_nom_kw = load
    power = state.ship.power
    power.p_gen_kw = generation
    power.p_gen_base_kw = generation
    snap = snapshot(state, generation=generation, load=load, energy=40)
    # The actual interval has no load shedding, battery saturation or job effect.
    assert engine._compute_load_kw(state) == load
    assert engine._integrate_power_interval(state, 3600) == []
    assert power.e_batt_kwh == energy_at(snap, 3600)
    assert power.power_quality == quality_at(snap, 3600)
    assert power.deficit_ratio == expected_deficit
    q, deficit = power_quality_components(40, 100, 20, 10, 20, SystemState.NOMINAL, 0)
    assert q == pytest.approx(.85) and deficit == 0


def test_coordinator_merges_electrical_health_and_job_domains(state):
    plan = plan_travel(1e18, .5, 9.81)
    electrical = TemporalLimit("battery_empty", "proper", 5)
    health = TemporalLimit("engine_health_threshold", "proper", 7)
    job = TemporalLimit("repair_job", "galactic", 20)
    result = select_next_boundary(plan, 0, 30, health_limit=health,
                                  proper_limits=(electrical,), job_limits=(job,))
    assert result.causes[0].limit.kind == "battery_empty"
    assert result.at_galactic_s == pytest.approx(galactic_time_at_proper(plan, 5))
    with pytest.raises(ValueError):
        select_next_boundary(plan, 0, 30, proper_limits=(job,))


@pytest.mark.parametrize("timer,brownout,expected", [
    (7, True, ("brownout_sustained", 23)),
    (30, True, None),
    (45, True, None),
    (7, False, ("brownout_timer_reset", 0)),
    (0, False, None),
])
def test_brownout_timer_limits_follow_actual_brownout(state, timer, brownout, expected):
    snap = snapshot(state, generation=0 if brownout else 40, load=30,
                    brownout_sustained_s=timer)
    brownout_limits = [(limit.kind, limit.time_s) for limit in power_limits(snap)
                       if limit.kind.startswith("brownout_")]
    assert brownout_limits == ([] if expected is None else [expected])
    if brownout:
        assert times(snap)["power_capacity_regulation"] == 0
    else:
        assert "power_capacity_regulation" not in times(snap)


def test_sustained_brownout_has_no_fictitious_zero_cut_in_coordinator(state):
    snap = snapshot(state, generation=0, load=30, brownout_sustained_s=30)
    plan = plan_travel(1e18, .5, 9.81)
    first = select_next_boundary(plan, 0, 100, proper_limits=power_limits(snap))
    assert first.advance_galactic_s == 0
    assert all(cause.limit.kind != "brownout_timer_reset" for cause in first.causes)
    resolved = frozenset(resolve_electrical_limit(snap, cause.limit)
                         for cause in first.causes if cause.limit.kind != "requested_horizon")
    second = select_next_boundary(plan, 0, 100, proper_limits=power_limits(snap, resolved=resolved),
                                  seen_zero_selections=(first,))
    assert second.advance_galactic_s > 0


@pytest.mark.parametrize("energy,generation,load,kind", [
    (0, 20, 0, "battery_empty"),
    (10, 20, 0, "soc_10_percent"),
    (10, 0, 20, "soc_10_percent"),
    (50, 20, 0, "soc_50_percent"),
    (50, 0, 20, "soc_50_percent"),
    (100, 0, 20, "battery_full"),
])
def test_exact_soc_crossing_is_resolved_once(state, energy, generation, load, kind):
    snap = snapshot(state, generation=generation, load=load, energy=energy,
                    quality_offset=.5, discharge_max_kw=100)
    pending = next(limit for limit in power_limits(snap) if limit.kind == kind)
    assert pending.time_s == 0
    assert pending.validity == "mathematical_crossing"
    token = resolve_electrical_limit(snap, pending)
    assert token.direction == (1 if generation > load else -1)
    assert kind not in times_after_resolution(snap, token)
    assert kind in times_after_resolution(replace(snap, op_mode="CRUISE"), token)
    assert energy_at(snap, 1) > energy if generation > load else energy_at(snap, 1) < energy


def times_after_resolution(snap, token):
    return {limit.kind: limit.time_s for limit in power_limits(snap, resolved=frozenset({token}))}


@pytest.mark.parametrize("threshold,kind", [
    (.25, "quality_025"), (.40, "quality_040"), (.55, "quality_055"),
])
@pytest.mark.parametrize("direction", [-1, 1])
def test_exact_quality_crossing_direction_and_strict_post_side(state, threshold, kind, direction):
    generation, load = (0, 20) if direction < 0 else (40, 20)
    # At 30% SOC, Q_SOC contributes .3. The deficit branch contributes .344
    # during discharge and .4 during charge.
    offset = threshold - (.644 if direction < 0 else .7)
    snap = snapshot(state, generation=generation, load=load, energy=30,
                    discharge_max_kw=100, quality_offset=offset)
    limit = next(limit for limit in power_limits(snap) if limit.kind == kind)
    assert limit.time_s == 0
    assert quality_at(snap, 0) == pytest.approx(threshold, abs=1e-15)
    token = resolve_electrical_limit(snap, limit)
    assert token.direction == direction
    assert kind not in times_after_resolution(snap, token)
    if direction < 0 and kind == "quality_025":
        assert next(l for l in power_limits(snap)
                    if l.kind == "quality_collapse_regulation").validity == "post_crossing_check"
    if direction < 0 and kind == "quality_040":
        assert times(snap)["low_quality_shed_timer"] == 10
    if direction > 0:
        assert "quality_collapse_regulation" not in times(snap)


def test_coordinator_advances_then_resolves_zero_crossing_without_clock_padding(state):
    plan = plan_travel(1e18, .5, 9.81)
    initial = snapshot(state, generation=0, load=20, energy=60,
                       discharge_max_kw=100, quality_offset=.5)
    first = select_next_boundary(plan, 0, 10000, proper_limits=power_limits(initial))
    assert {cause.limit.kind for cause in first.causes} == {"soc_50_percent"}
    crossing_proper = next(l.time_s for l in power_limits(initial)
                           if l.kind == "soc_50_percent")
    assert first.accumulated_proper_s == pytest.approx(crossing_proper)
    at_boundary = replace(initial, energy_kwh=energy_at(initial, first.accumulated_proper_s))
    assert at_boundary.energy_kwh == pytest.approx(50)
    zero = select_next_boundary(plan, first.at_galactic_s, 100,
                                proper_limits=power_limits(at_boundary))
    assert zero.advance_galactic_s == 0
    with pytest.raises(TemporalResolutionError):
        select_next_boundary(plan, first.at_galactic_s, 100,
                             proper_limits=power_limits(at_boundary),
                             seen_zero_selections=(zero,))
    token = resolve_electrical_limit(at_boundary, zero.causes[0].limit)
    continuation = select_next_boundary(plan, first.at_galactic_s, 100,
                                        proper_limits=power_limits(at_boundary,
                                                                   resolved=frozenset({token})),
                                        seen_zero_selections=(zero,))
    assert continuation.advance_galactic_s > 0


def test_quality_crossing_keeps_real_post_side_regulation_pending(state):
    snap = snapshot(state, generation=0, load=20, energy=30,
                    discharge_max_kw=100, quality_offset=.25 - .644)
    plan = plan_travel(1e18, .5, 9.81)
    zero = select_next_boundary(plan, 0, 100, proper_limits=power_limits(snap))
    kinds = {cause.limit.kind for cause in zero.causes}
    assert {"quality_025", "quality_collapse_regulation"} <= kinds
    mathematical = next(cause.limit for cause in zero.causes if cause.limit.kind == "quality_025")
    resolved = frozenset({resolve_electrical_limit(snap, mathematical)})
    still_pending = select_next_boundary(plan, 0, 100,
                                         proper_limits=power_limits(snap, resolved=resolved),
                                         seen_zero_selections=(zero,))
    assert {cause.limit.kind for cause in still_pending.causes} == {"quality_collapse_regulation"}
    assert still_pending.advance_galactic_s == 0
    operational = still_pending.causes[0].limit
    fully_resolved = resolved | {resolve_electrical_limit(snap, operational)}
    continuation = select_next_boundary(plan, 0, 100,
                                        proper_limits=power_limits(snap, resolved=fully_resolved),
                                        seen_zero_selections=(zero, still_pending))
    assert continuation.advance_galactic_s > 0


def test_future_quality_crossing_resolves_without_repeated_zero(state):
    plan = plan_travel(1e18, .5, 9.81)
    initial = snapshot(state, generation=0, load=20, energy=40,
                       discharge_max_kw=100, quality_offset=-.1)
    future = next(limit for limit in power_limits(initial) if limit.kind == "quality_055")
    first = select_next_boundary(plan, 0, 10000, proper_limits=power_limits(initial))
    assert {cause.limit.kind for cause in first.causes} == {"quality_055"}
    assert first.accumulated_proper_s == pytest.approx(future.time_s)
    at_boundary = replace(initial, energy_kwh=energy_at(initial, first.accumulated_proper_s))
    zero = select_next_boundary(plan, first.at_galactic_s, 100,
                                proper_limits=power_limits(at_boundary))
    assert {cause.limit.kind for cause in zero.causes} == {"quality_055"}
    token = resolve_electrical_limit(at_boundary, zero.causes[0].limit)
    continuation = select_next_boundary(plan, first.at_galactic_s, 100,
                                        proper_limits=power_limits(at_boundary,
                                                                   resolved=frozenset({token})),
                                        seen_zero_selections=(zero,))
    assert continuation.advance_galactic_s > 0


def test_rounded_quality_equality_uses_crossing_direction(state):
    offset = math.nextafter(.25 - .7, -math.inf)
    rising = snapshot(state, generation=40, load=20, energy=30,
                      quality_offset=offset)
    assert times(rising)["quality_025"] == 0
    assert "quality_collapse_regulation" not in times(rising)
