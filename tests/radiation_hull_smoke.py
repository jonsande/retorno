from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import EventType
from retorno.model.systems import SystemState


def _fresh_state():
    state = create_initial_state_prologue()
    state.ship.systems["power_core"].state = SystemState.NOMINAL
    state.ship.systems["power_core"].health = 1.0
    state.ship.systems["energy_distribution"].state = SystemState.NOMINAL
    state.ship.systems["energy_distribution"].health = 1.0
    state.ship.systems["drone_bay"].state = SystemState.NOMINAL
    state.ship.systems["drone_bay"].forced_offline = False
    state.ship.power.p_gen_base_kw = 20.0
    state.ship.power.p_gen_kw = 20.0
    state.ship.power.e_batt_kwh = state.ship.power.e_batt_max_kwh
    state.ship.in_transit = False
    state.ship.is_hibernating = False
    state.ship.hull_integrity = 1.0
    return state


def _set_node(state, node_id: str) -> None:
    state.world.current_node_id = node_id
    state.ship.current_node_id = node_id


def _capture_status(state) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        repl.render_status(state)
    return buf.getvalue()


def main() -> None:
    engine = Engine()

    # 1) status includes hull + radiation env/internal.
    state = _fresh_state()
    engine.tick(state, 1.0)
    status_text = _capture_status(state)
    assert "hull:" in status_text
    assert "radiation: env=" in status_text and "internal=" in status_text

    # 2) Hull decays very slowly in normal/low-radiation operation.
    state = _fresh_state()
    _set_node(state, "UNKNOWN")
    h0 = state.ship.hull_integrity
    engine.tick(state, 30 * Balance.DAY_S)
    h1 = state.ship.hull_integrity
    normal_decay = h0 - h1
    assert 0.0 < normal_decay < 1.0e-3, normal_decay

    # 3) Hull decays faster in high radiation and transit.
    state_high = _fresh_state()
    _set_node(state_high, "ARCHIVE_01")
    hh0 = state_high.ship.hull_integrity
    engine.tick(state_high, 30 * Balance.DAY_S)
    hh1 = state_high.ship.hull_integrity
    high_rad_decay = hh0 - hh1
    assert high_rad_decay > normal_decay, (high_rad_decay, normal_decay)

    state_transit = _fresh_state()
    state_transit.ship.in_transit = True
    state_transit.ship.transit_from = "ARCHIVE_01"
    state_transit.ship.transit_to = "DERELICT_A3"
    state_transit.ship.arrival_t = state_transit.clock.t + 1.0e12
    ht0 = state_transit.ship.hull_integrity
    engine.tick(state_transit, 30 * Balance.DAY_S)
    ht1 = state_transit.ship.hull_integrity
    transit_decay = ht0 - ht1
    assert transit_decay > high_rad_decay, (transit_decay, high_rad_decay)

    # 4) Internal radiation depends on hull with same env.
    state = _fresh_state()
    env_rad = 0.003
    state.ship.hull_integrity = 1.0
    internal_hi = engine._compute_internal_radiation_rad_per_s(state, env_rad)  # noqa: SLF001
    state.ship.hull_integrity = 0.30
    internal_lo = engine._compute_internal_radiation_rad_per_s(state, env_rad)  # noqa: SLF001
    assert internal_lo > internal_hi, (internal_lo, internal_hi)

    # 5) Lower hull => higher internal radiation => higher system wear.
    hi_hull = _fresh_state()
    _set_node(hi_hull, "ARCHIVE_01")
    lo_hull = _fresh_state()
    _set_node(lo_hull, "ARCHIVE_01")
    hi_hull.ship.hull_integrity = 1.0
    lo_hull.ship.hull_integrity = 0.10
    sid = "sensors"
    hi_hull.ship.systems[sid].health = 1.0
    lo_hull.ship.systems[sid].health = 1.0
    engine.tick(hi_hull, 10 * Balance.YEAR_S)
    engine.tick(lo_hull, 10 * Balance.YEAR_S)
    assert lo_hull.ship.systems[sid].health < hi_hull.ship.systems[sid].health, (
        lo_hull.ship.systems[sid].health,
        hi_hull.ship.systems[sid].health,
    )

    # 6) Deployed drones accumulate dose; docked drones do not.
    state = _fresh_state()
    _set_node(state, "ARCHIVE_01")
    state.ship.drones["D1"].status = DroneStatus.DEPLOYED
    state.ship.drones["D1"].location = DroneLocation(kind="ship_sector", id="PWR-A2")
    state.ship.drones["D1"].dose_rad = 0.0
    state.ship.drones["D2"] = DroneState(
        drone_id="D2",
        name="Drone-02",
        status=DroneStatus.DOCKED,
        location=DroneLocation(kind="ship_sector", id="DRN-BAY"),
        dose_rad=0.0,
    )
    engine.tick(state, 100.0)
    assert state.ship.drones["D1"].dose_rad > 0.0
    assert state.ship.drones["D2"].dose_rad == 0.0

    # 7) Higher dose bands increase deployed drone integrity wear.
    losses: list[float] = []
    for dose in (0.5, 2.0, 4.0, 7.0):
        state = _fresh_state()
        drone = state.ship.drones["D1"]
        drone.status = DroneStatus.DEPLOYED
        drone.location = DroneLocation(kind="ship_sector", id="PWR-A2")
        drone.integrity = 1.0
        drone.dose_rad = dose
        engine._update_drone_maintenance(state, 1000.0)  # noqa: SLF001
        losses.append(1.0 - drone.integrity)
    assert losses[0] < losses[1] < losses[2] < losses[3], losses

    # 8) Docked drone decontaminates automatically when bay support is available.
    state = _fresh_state()
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DOCKED
    drone.location = DroneLocation(kind="ship_sector", id="DRN-BAY")
    drone.dose_rad = 5.0
    engine._update_drone_maintenance(state, 10.0)  # noqa: SLF001
    assert drone.dose_rad < 5.0, drone.dose_rad

    # 9) No decontamination when bay/distribution are offline.
    state = _fresh_state()
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DOCKED
    drone.location = DroneLocation(kind="ship_sector", id="DRN-BAY")
    drone.dose_rad = 5.0
    state.ship.systems["drone_bay"].state = SystemState.OFFLINE
    engine._update_drone_maintenance(state, 10.0)  # noqa: SLF001
    assert drone.dose_rad == 5.0

    state = _fresh_state()
    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DOCKED
    drone.location = DroneLocation(kind="ship_sector", id="DRN-BAY")
    drone.dose_rad = 5.0
    state.ship.systems["energy_distribution"].state = SystemState.OFFLINE
    engine._update_drone_maintenance(state, 10.0)  # noqa: SLF001
    assert drone.dose_rad == 5.0

    # 10) Radiation level warnings are emitted on threshold change only.
    state = _fresh_state()
    _set_node(state, "UNKNOWN")
    baseline_events = engine.tick(state, 1.0)
    assert not any(
        e.type == EventType.ACTION_WARNING and e.data.get("message_key") == "radiation_level_changed"
        for e in baseline_events
    )

    _set_node(state, "CARNAVAL_34")
    ship_change_events = engine.tick(state, 1.0)
    ship_rad_events = [
        e
        for e in ship_change_events
        if e.type == EventType.ACTION_WARNING and e.data.get("message_key") == "radiation_level_changed"
    ]
    assert any(e.data.get("metric") == "env" for e in ship_rad_events), ship_rad_events
    assert any(e.data.get("metric") == "internal" for e in ship_rad_events), ship_rad_events

    drone = state.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED
    drone.location = DroneLocation(kind="ship_sector", id="PWR-A2")
    drone.dose_rad = Balance.RAD_LEVEL_DRONE_DOSE_HIGH - 0.01
    drone.radiation_level = "elevated"
    drone_cross_events = engine.tick(state, 1.0)
    drone_rad_events = [
        e
        for e in drone_cross_events
        if e.type == EventType.ACTION_WARNING
        and e.data.get("message_key") == "radiation_level_changed"
        and e.data.get("metric") == "drone_dose"
        and e.data.get("target_id") == "D1"
    ]
    assert drone_rad_events, drone_cross_events

    drone_same_band_events = engine.tick(state, 1.0)
    drone_same_band_rad_events = [
        e
        for e in drone_same_band_events
        if e.type == EventType.ACTION_WARNING
        and e.data.get("message_key") == "radiation_level_changed"
        and e.data.get("metric") == "drone_dose"
        and e.data.get("target_id") == "D1"
    ]
    assert not drone_same_band_rad_events, drone_same_band_rad_events

    print("RADIATION/HULL SMOKE PASSED")


if __name__ == "__main__":
    main()
