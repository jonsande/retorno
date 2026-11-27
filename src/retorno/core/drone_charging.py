"""One read-only allocation for productive charging and electrical forecasts."""
from __future__ import annotations

from dataclasses import dataclass

from retorno.config.balance import Balance
from retorno.model.drones import DroneStatus, compute_drone_effective_profile
from retorno.model.ship_layout import canonical_ship_sector_id, drone_bay_sector_id_for_ship
from retorno.model.systems import SystemState
from retorno.runtime.data_loader import load_modules


@dataclass(frozen=True, slots=True)
class DroneCharge:
    drone_id: str
    power_kw: float
    rate_per_s: float
    remaining: float
    start_battery: float


@dataclass(frozen=True, slots=True)
class ChargingDecision:
    allocations: tuple[DroneCharge, ...] = ()
    candidate: bool = False

    @property
    def power_kw(self) -> float:
        return sum(item.power_kw for item in self.allocations)


def decide_drone_charging(state, generation_kw: float, base_load_kw: float) -> ChargingDecision:
    """Allocate real generation first, then usable discharge, in drone ID order."""
    if not state.ship.drones:
        return ChargingDecision()
    bay = state.ship.systems.get("drone_bay")
    distribution = state.ship.systems.get("energy_distribution")
    if (bay is None or bay.forced_offline or bay.state == SystemState.OFFLINE
            or (not state.os.god_active and distribution is not None
                and distribution.state == SystemState.OFFLINE)):
        return ChargingDecision()
    multiplier = (Balance.DRONE_BAY_LIMITED_CHARGE_RATE_MULT
                  if bay.state == SystemState.LIMITED else
                  Balance.DRONE_BAY_DAMAGED_CHARGE_RATE_MULT
                  if bay.state in {SystemState.DAMAGED, SystemState.CRITICAL} else 1.0)
    if multiplier <= 0:
        return ChargingDecision()
    bay_sector = drone_bay_sector_id_for_ship(state.ship)
    modules = None
    candidates = []
    for drone_id, drone in sorted(state.ship.drones.items()):
        if (drone.status != DroneStatus.DOCKED or drone.location.kind != "ship_sector"
                or canonical_ship_sector_id(drone.location.id) != bay_sector):
            continue
        if modules is None:
            modules = load_modules()
        remaining = compute_drone_effective_profile(drone, modules).battery_max_effective - drone.battery
        if remaining > 1e-12:
            candidates.append((drone_id, remaining, drone.battery))
    if not candidates:
        return ChargingDecision()
    power = state.ship.power
    soc = power.e_batt_kwh / power.e_batt_max_kwh if power.e_batt_max_kwh > 0 else 0.0
    surplus = max(0.0, generation_kw - base_load_kw)
    discharge_headroom = max(0.0, power.p_discharge_max_kw - max(0.0, base_load_kw - generation_kw))
    reserve = (discharge_headroom if soc > Balance.DRONE_CHARGE_RESERVE_SOC else 0.0)
    available = surplus + reserve
    allocations = []
    for drone_id, remaining, battery in candidates:
        normal_kw = Balance.DRONE_CHARGE_KW * multiplier
        slow_kw = normal_kw * Balance.DRONE_BATTERY_CHARGE_LOW_MULT
        # A full-rate transfer requires real surplus. Slow transfer may use
        # reserve above the floor; below it, any real surplus is useful.
        if surplus >= normal_kw:
            granted = normal_kw
        else:
            granted = min(slow_kw, available)
        if granted <= 1e-12:
            break
        rate = granted / (3600.0 * Balance.DRONE_BATTERY_KWH_PER_UNIT)
        allocations.append(DroneCharge(drone_id, granted, rate, remaining, battery))
        available -= granted
        surplus = max(0.0, surplus - granted)
    return ChargingDecision(tuple(allocations), candidate=bool(allocations))
