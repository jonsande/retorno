from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.core.engine import Engine
from retorno.core.actions import Boot, DroneDeploy, Repair


def assert_any_event(events, event_type):
    assert any(e.type == event_type for e in events), f"Expected event type {event_type} in {events}"


def assert_any_message_contains(events, substring: str):
    assert any(substring.lower() in (e.message or "").lower() for e in events), (
        f"Expected some event message to contain '{substring}'. Got: {[e.message for e in events]}"
    )


def main() -> None:
    engine = Engine()
    state = create_initial_state_prologue()

    # 1) Sanity: alerts iniciales existen
    assert "power_net_deficit" in state.events.alerts, "Missing initial POWER_NET_DEFICIT alert"
    assert "power_core_degraded" in state.events.alerts, "Missing initial POWER_CORE_DEGRADED alert"

    # 2) Tick de unos segundos no debe explotar
    engine.tick(state, 1.0)
    engine.tick(state, 1.0)

    # 3) Intentar desplegar dron al inicio: debe encolar job.
    ev = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2"))
    assert ev and all(e.severity.value != "warn" for e in ev), (
        "DroneDeploy should enqueue at start; events: " + ", ".join([e.message for e in ev])
    )

    # 4) Boot sensores al inicio debe bloquearse (depende de distribution NOMINAL)
    ev = engine.apply_action(state, Boot(service_name="sensord"))
    assert ev, "Expected boot blocked event for sensord"
    assert_any_message_contains(ev, "requires")  # o "dependencies", según tu mensaje

    # --- Transición controlada para probar desbloqueo ---
    # Forzamos estado energético estable para simular "puzzle resuelto".
    dist = state.ship.systems["energy_distribution"]
    dist.health = 0.90
    dist.state = dist.state.NOMINAL  # SystemState.NOMINAL
    state.ship.systems["core_os"].state = state.ship.systems["core_os"].state.NOMINAL
    state.ship.power.power_quality = 0.90
    state.ship.power.brownout = False

    # Ejecutamos tiempo suficiente para completar el deploy inicial (DEPLOY_TIME_S) + margen
    engine.tick(state, 20.0)
    assert state.ship.drones["D1"].status.value == "deployed", "Drone should be DEPLOYED after deploy job"

    # 5) Repair: debe requerir dron DEPLOYED. Probamos repair de power_core (existe).
    ev = engine.apply_action(state, Repair(drone_id="D1", system_id="power_core"))
    assert ev and all(e.severity.value != "warn" for e in ev), (
        "Repair should be enqueued when drone deployed; got events: "
        + ", ".join([e.message for e in ev])
    )

    # Avanza tiempo para completar reparación
    engine.tick(state, 30.0)
    assert state.ship.systems["power_core"].health > 0.6, "Power core health should have increased after repair"

    # 6) Boot sensord ahora debe permitir encolar job (no bloquear)
    ev = engine.apply_action(state, Boot(service_name="sensord"))
    assert ev and all(e.severity.value != "warn" for e in ev), (
        "sensord boot should be enqueued now; got events: " + ", ".join([e.message for e in ev])
    )
    engine.tick(state, 20.0)
    sensors = state.ship.systems["sensors"]
    assert sensors.service is not None and sensors.service.is_running, "sensord should be running after boot job"

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
