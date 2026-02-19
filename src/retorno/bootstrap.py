from __future__ import annotations

from retorno.core.gamestate import GameState
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import AlertState, Event, EventType, Severity, SourceRef
from retorno.model.ship import PowerNetworkState
from retorno.model.os import AccessLevel, FSNode, FSNodeType, normalize_path
from retorno.model.systems import Dependency, ServiceState, ShipSystem, SystemState
from retorno.model.world import SpaceNode


def create_initial_state_prologue() -> GameState:
    state = GameState()

    state.ship.power = PowerNetworkState(
        p_gen_kw=3.2,
        e_batt_kwh=1.6,
        e_batt_max_kwh=5.0,
        p_charge_max_kw=4.0,
        p_discharge_max_kw=10.0,
    )

    state.ship.systems = {
        "core_os": ShipSystem(
            system_id="core_os",
            name="Core OS",
            state=SystemState.NOMINAL,
            health=1.0,
            p_nom_kw=0.4,
            priority=1,
            base_decay_per_s=1.0e-5,
            k_power=0.35,
            k_rad=0.15,
            service=ServiceState(service_name="core_os", is_running=True, boot_time_s=2),
            tags={"critical"},
        ),
        "life_support": ShipSystem(
            system_id="life_support",
            name="Life Support",
            state=SystemState.NOMINAL,
            health=1.0,
            p_nom_kw=1.2,
            priority=1,
            base_decay_per_s=1.2e-5,
            k_power=0.40,
            k_rad=0.20,
            tags={"critical"},
        ),
        "power_core": ShipSystem(
            system_id="power_core",
            name="Power Core",
            state=SystemState.DAMAGED,
            health=0.6,
            p_nom_kw=0.2,
            priority=2,
            base_decay_per_s=1.5e-5,
            k_power=0.25,
            k_rad=0.10,
            tags={"critical"},
        ),
        "energy_distribution": ShipSystem(
            system_id="energy_distribution",
            name="Energy Distribution",
            state=SystemState.DAMAGED,
            health=0.7,
            state_locked=True,
            p_nom_kw=0.3,
            priority=1,
            base_decay_per_s=1.1e-5,
            k_power=0.35,
            k_rad=0.15,
            tags={"critical"},
        ),
        "drone_bay": ShipSystem(
            system_id="drone_bay",
            name="Drone Bay",
            state=SystemState.NOMINAL,
            health=0.9,
            p_nom_kw=0.6,
            priority=4,
            base_decay_per_s=1.0e-5,
            k_power=0.35,
            k_rad=0.15,
            dependencies=[
                Dependency(
                    dep_type="system_state_at_least",
                    target_id="energy_distribution",
                    value=SystemState.NOMINAL.value,
                    #value=SystemState.LIMITED.value,

                )
            ],
        ),
        "security": ShipSystem(
            system_id="security",
            name="Security",
            state=SystemState.NOMINAL,
            health=0.9,
            p_nom_kw=0.5,
            priority=3,
            base_decay_per_s=1.1e-5,
            k_power=0.30,
            k_rad=0.10,
            dependencies=[
                Dependency(
                    dep_type="system_state_at_least",
                    target_id="energy_distribution",
                    value=SystemState.NOMINAL.value,
                )
            ],
            service=ServiceState(service_name="securityd", is_running=False, boot_time_s=6),
        ),
        "data_core": ShipSystem(
            system_id="data_core",
            name="Data Core",
            state=SystemState.NOMINAL,
            health=0.9,
            p_nom_kw=0.4,
            priority=3,
            base_decay_per_s=1.1e-5,
            k_power=0.30,
            k_rad=0.10,
            dependencies=[
                Dependency(
                    dep_type="system_state_at_least",
                    target_id="energy_distribution",
                    value=SystemState.NOMINAL.value,
                )
            ],
            service=ServiceState(service_name="datad", is_running=False, boot_time_s=5),
        ),
        "sensors": ShipSystem(
            system_id="sensors",
            name="Sensors",
            state=SystemState.OFFLINE,
            health=0.85,
            state_locked=True,
            p_nom_kw=0.7,
            priority=4,
            base_decay_per_s=1.2e-5,
            k_power=0.35,
            k_rad=0.15,
            dependencies=[
                Dependency(
                    dep_type="system_state_at_least",
                    target_id="energy_distribution",
                    value=SystemState.NOMINAL.value,
                )
            ],
            service=ServiceState(service_name="sensord", is_running=False, boot_time_s=8),
            tags={"locked"},
        ),
    }

    state.ship.drones = {
        "D1": DroneState(
            drone_id="D1",
            name="Drone-01",
            status=DroneStatus.DOCKED,
            location=DroneLocation(kind="ship_sector", id="drone_bay"),
            shield_factor=0.9,
        )
    }

    state.world.space.nodes[state.ship.ship_id] = SpaceNode(
        node_id=state.ship.ship_id,
        name=state.ship.name,
        kind="ship",
        radiation_rad_per_s=state.ship.radiation_env_rad_per_s,
    )
    state.world.space.nodes["ECHO_7"] = SpaceNode(
        node_id="ECHO_7",
        name="ECHO-7 Relay Station",
        kind="station",
        radiation_rad_per_s=0.002,
    )

    _bootstrap_os(state)
    _bootstrap_alerts(state)

    return state


def _bootstrap_alerts(state: GameState) -> None:
    def emit_alert(event_type: EventType, severity: Severity, source: SourceRef, message: str) -> None:
        seq = state.events.next_event_seq
        state.events.next_event_seq += 1
        event = Event(
            event_id=f"E{seq:05d}",
            t=int(state.clock.t),
            type=event_type,
            severity=severity,
            source=source,
            message=message,
        )
        state.events.recent.append(event)
        state.events.alerts[event_type.value] = AlertState(
            alert_key=event_type.value,
            severity=severity,
            first_seen_t=int(state.clock.t),
            last_seen_t=int(state.clock.t),
            is_active=True,
        )

    emit_alert(
        EventType.POWER_NET_DEFICIT,
        Severity.WARN,
        SourceRef(kind="ship", id=state.ship.ship_id),
        "Power deficit detected",
    )
    emit_alert(
        EventType.POWER_CORE_DEGRADED,
        Severity.WARN,
        SourceRef(kind="ship_system", id="power_core"),
        "Power core degraded",
    )


def _bootstrap_os(state: GameState) -> None:
    fs = state.os.fs
    state.os.access_level = AccessLevel.GUEST

    def add_dir(path: str, access: AccessLevel = AccessLevel.GUEST) -> None:
        norm = normalize_path(path)
        fs[norm] = FSNode(path=norm, node_type=FSNodeType.DIR, access=access)

    def add_file(path: str, content: str, access: AccessLevel = AccessLevel.GUEST) -> None:
        norm = normalize_path(path)
        fs[norm] = FSNode(path=norm, node_type=FSNodeType.FILE, content=content, access=access)

    add_dir("/")
    add_dir("/manuals")
    add_dir("/manuals/commands")
    add_dir("/manuals/systems")
    add_dir("/mail")
    add_dir("/mail/inbox")
    add_dir("/logs", access=AccessLevel.ENG)

    add_file(
        "/manuals/commands/status.txt",
        "status\n"
        "- Muestra energía, sistemas y reloj.\n"
        "- Úsalo tras wait para ver cambios.\n",
    )
    add_file(
        "/manuals/commands/diag.txt",
        "diag <system_id>\n"
        "- Diagnóstico técnico del sistema.\n"
        "- Verifica dependencias y servicio.\n",
    )
    add_file(
        "/manuals/commands/boot.txt",
        "boot <service_name>\n"
        "- Inicia un servicio instalado.\n"
        "- Requiere dependencias satisfechas.\n",
    )
    add_file(
        "/manuals/commands/repair.txt",
        "repair <drone_id> <system_id>\n"
        "- Repara un sistema con un dron.\n"
        "- El dron debe estar desplegado.\n"
        "- Repair operations require deployed drone units.\n",
    )
    add_file(
        "/manuals/commands/wait.txt",
        "wait <segundos>\n"
        "- Avanza el tiempo del simulador.\n"
        "- Útil para completar jobs.\n",
    )
    add_file(
        "/manuals/commands/alerts.txt",
        "alerts\n"
        "- Lista alertas activas.\n"
        "- Las críticas requieren atención.\n",
    )
    add_file(
        "/manuals/commands/contacts.txt",
        "contacts | scan\n"
        "- Lista señales detectadas.\n"
        "- Requiere sensord activo.\n",
    )
    add_file(
        "/manuals/commands/dock.txt",
        "dock <node_id>\n"
        "- Acopla la nave al nodo.\n"
        "- Debe ser contacto conocido.\n",
    )
    add_file(
        "/manuals/commands/salvage.txt",
        "salvage <node_id> [scrap] [amount]\n"
        "- Recupera recursos del nodo.\n"
        "- Debes estar acoplado allí.\n",
    )
    add_file(
        "/manuals/systems/energy_distribution.txt",
        "energy_distribution\n"
        "- Enrutamiento de energía.\n"
        "- Cuando la integridad cae bajo nominal, algunos sistemas pueden negarse a iniciar.\n",
    )
    add_file(
        "/manuals/systems/power_core.txt",
        "power_core\n"
        "- Núcleo de generación primaria.\n"
        "- Estado degradado reduce estabilidad.\n",
        access=AccessLevel.ENG,
    )
    add_file(
        "/manuals/systems/sensors.txt",
        "sensors\n"
        "- Detección de señales externas.\n"
        "- Boot sensord para activar.\n",
    )
    add_file(
        "/manuals/systems/drone_bay.txt",
        "drone_bay\n"
        "- Salida de drones al casco.\n"
        "- En emergencia usa deploy!.\n",
    )

    add_file(
        "/mail/inbox/0001.txt",
        "FROM: Autonomous Systems\n"
        "SUBJ: Emergency Wake Event\n"
        "\n"
        "Wake condition triggered by power instability.\n"
        "\n"
        "Primary distribution grid integrity below nominal thresholds.\n"
        "Core output fluctuating.\n"
        "\n"
        "Emergency maintenance protocols available to conscious operator.\n"
        "\n"
        "Recommended actions:\n"
        " - review system diagnostics\n"
        " - assess maintenance drone availability\n"
        " - stabilize signal infrastructure\n"
        "\n"
        "Warning: cascading failures possible if instability persists.\n"
        "\n"
        "— Ship OS\n",
    )
    add_file(
        "/logs/boot.log",
        "BOOT TRACE\n"
        "core_os: ok\n"
        "power_core: degraded\n"
        "energy_distribution: damaged\n"
        "sensors: offline\n"
        "drone_bay: nominal\n",
        access=AccessLevel.ENG,
    )
