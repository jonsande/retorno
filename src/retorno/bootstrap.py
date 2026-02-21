from __future__ import annotations

from retorno.core.gamestate import GameState
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import AlertState, Event, EventType, Severity, SourceRef
from retorno.model.ship import PowerNetworkState, ShipSector
from retorno.model.os import AccessLevel, FSNode, FSNodeType, Locale, normalize_path
from retorno.model.systems import Dependency, ServiceState, ShipSystem, SystemState
from retorno.model.world import SpaceNode
from retorno.runtime.data_loader import load_modules
from retorno.config.balance import Balance
import random
from pathlib import Path


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
            sector_id="BRG-01",
            p_nom_kw=0.4,
            priority=1,
            base_decay_per_s=6.0e-11,  # calibrated for decades-long travel
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
            sector_id="BRG-01",
            p_nom_kw=1.2,
            priority=1,
            base_decay_per_s=8.0e-11,
            k_power=0.40,
            k_rad=0.20,
            tags={"critical"},
        ),
        "power_core": ShipSystem(
            system_id="power_core",
            name="Power Core",
            state=SystemState.DAMAGED,
            health=0.6,
            sector_id="PWR-A2",
            p_nom_kw=0.2,
            priority=2,
            base_decay_per_s=1.0e-10,
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
            sector_id="PWR-A2",
            p_nom_kw=0.3,
            priority=1,
            base_decay_per_s=8.0e-11,
            k_power=0.35,
            k_rad=0.15,
            tags={"critical"},
        ),
        "drone_bay": ShipSystem(
            system_id="drone_bay",
            name="Drone Bay",
            state=SystemState.NOMINAL,
            health=0.9,
            sector_id="DRN-BAY",
            p_nom_kw=0.6,
            priority=4,
            base_decay_per_s=8.0e-11,
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
            sector_id="BRG-01",
            p_nom_kw=0.5,
            priority=3,
            base_decay_per_s=8.5e-11,
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
            sector_id="BRG-01",
            p_nom_kw=0.4,
            priority=3,
            base_decay_per_s=8.5e-11,
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
            sector_id="BRG-01",
            p_nom_kw=0.7,
            priority=4,
            base_decay_per_s=9.0e-11,
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

    state.ship.sectors = {
        "DRN-BAY": ShipSector(sector_id="DRN-BAY", name="Drone Bay", tags={"bay"}),
        "PWR-A2": ShipSector(sector_id="PWR-A2", name="Power Trunk A2", tags={"power"}),
        "BRG-01": ShipSector(sector_id="BRG-01", name="Bridge Access", tags={"restricted"}),
        "CRG-01": ShipSector(sector_id="CRG-01", name="Cargo Hold", tags={"cargo"}),
    }

    state.world.space.nodes[state.ship.ship_id] = SpaceNode(
        node_id=state.ship.ship_id,
        name=state.ship.name,
        kind="ship",
        radiation_rad_per_s=state.ship.radiation_env_rad_per_s,
        x_ly=0.0,
        y_ly=0.0,
        z_ly=0.0,
    )
    state.ship.current_node_id = state.world.current_node_id
    rng = random.Random(state.meta.rng_seed)
    modules = load_modules()
    module_ids = list(modules.keys())
    state.world.space.nodes["ECHO_7"] = SpaceNode(
        node_id="ECHO_7",
        name="ECHO-7 Relay Station",
        kind="station",
        radiation_rad_per_s=0.002,
        x_ly=0.0,
        y_ly=0.0,
        z_ly=0.0,
        salvage_scrap_available=rng.randint(Balance.ECHO_7_SCRAP_MIN, Balance.ECHO_7_SCRAP_MAX),
        salvage_modules_available=_bootstrap_modules(rng, module_ids),
    )
    state.world.space.nodes["HARBOR_12"] = SpaceNode(
        node_id="HARBOR_12",
        name="Harbor-12 Waystation",
        kind="station",
        radiation_rad_per_s=0.001,
        x_ly=12.0,
        y_ly=4.0,
        z_ly=0.0,
    )
    state.world.space.nodes["DERELICT_A3"] = SpaceNode(
        node_id="DERELICT_A3",
        name="Derelict A-3",
        kind="derelict",
        radiation_rad_per_s=0.003,
        x_ly=45.0,
        y_ly=-2.0,
        z_ly=1.0,
    )
    state.world.known_contacts.update({"HARBOR_12", "DERELICT_A3"})

    _bootstrap_os(state)
    _bootstrap_alerts(state)
    state.ship.manifest_scrap = state.ship.cargo_scrap
    state.ship.manifest_modules = list(state.ship.cargo_modules)
    state.ship.manifest_dirty = False
    state.ship.manifest_last_sync_t = state.clock.t

    return state


def create_initial_state_sandbox() -> GameState:
    state = create_initial_state_prologue()

    # Sandbox overrides: systems healthy, services running, known contacts.
    for sys in state.ship.systems.values():
        if sys.system_id in {"energy_distribution", "power_core", "drone_bay"}:
            sys.state = SystemState.NOMINAL
            sys.health = max(sys.health, 0.9)
            sys.state_locked = False
        if sys.system_id == "sensors":
            sys.state = SystemState.NOMINAL
            sys.health = max(sys.health, 0.9)
            sys.state_locked = False
    data_core = state.ship.systems.get("data_core")
    if data_core and data_core.service:
        data_core.service.is_running = True

    sensors = state.ship.systems.get("sensors")
    if sensors and sensors.service:
        sensors.service.is_running = True

    state.ship.op_mode = "NORMAL"
    state.ship.current_node_id = "ECHO_7"
    state.world.current_node_id = "ECHO_7"

    # Known contacts for testing
    state.world.known_contacts.update({"ECHO_7", "HARBOR_12", "DERELICT_A3"})

    # Give some cargo for testing
    state.ship.cargo_scrap = max(state.ship.cargo_scrap, 20)
    state.ship.manifest_dirty = True

    return state

def _bootstrap_modules(rng: random.Random, module_ids: list[str]) -> list[str]:
    if not module_ids:
        return []
    count = rng.randint(Balance.ECHO_7_MODULES_MIN, Balance.ECHO_7_MODULES_MAX)
    return [rng.choice(module_ids) for _ in range(count)]


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
    state.os.locale = Locale.EN

    manuals_root = Path(__file__).resolve().parents[2] / "data" / "manuals"

    def add_dir(path: str, access: AccessLevel = AccessLevel.GUEST) -> None:
        norm = normalize_path(path)
        fs[norm] = FSNode(path=norm, node_type=FSNodeType.DIR, access=access)

    def add_file(path: str, content: str, access: AccessLevel = AccessLevel.GUEST) -> None:
        norm = normalize_path(path)
        if norm.startswith("/manuals/"):
            disk_path = manuals_root / norm[len("/manuals/") :].lstrip("/")
            try:
                if disk_path.exists():
                    content = disk_path.read_text(encoding="utf-8")
                else:
                    disk_path.parent.mkdir(parents=True, exist_ok=True)
                    disk_path.write_text(content, encoding="utf-8")
            except Exception:
                pass
        fs[norm] = FSNode(path=norm, node_type=FSNodeType.FILE, content=content, access=access)

    add_dir("/")
    add_dir("/manuals")
    add_dir("/manuals/commands")
    add_dir("/manuals/concepts")
    add_dir("/manuals/systems")
    add_dir("/manuals/alerts")
    add_dir("/manuals/modules")
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
        "/manuals/commands/boot.en.txt",
        "boot <service_name>\n"
        "- Starts an installed service.\n"
        "- Requires dependencies satisfied.\n",
    )
    add_file(
        "/manuals/commands/boot.es.txt",
        "boot <service_name>\n"
        "- Inicia un servicio instalado.\n"
        "- Requiere dependencias satisfechas.\n",
    )
    add_file(
        "/manuals/commands/shutdown.en.txt",
        "shutdown <system_id>\n"
        "system off <system_id>\n"
        "power off <system_id>\n"
        "power on <system_id>\n"
        "- Manually powers down a system (forced offline).\n"
        "- Use to reduce load or isolate faults.\n",
    )
    add_file(
        "/manuals/commands/shutdown.es.txt",
        "shutdown <system_id>\n"
        "system off <system_id>\n"
        "power off <system_id>\n"
        "power on <system_id>\n"
        "- Apaga manualmente un sistema (forced offline).\n"
        "- Úsalo para reducir carga o aislar fallos.\n",
    )
    add_file(
        "/manuals/commands/system.en.txt",
        "system on <system_id>\n"
        "system off <system_id>\n"
        "- Toggles manual power state for a subsystem.\n"
        "- 'off' forces the system offline (no load).\n"
        "- 'on' clears the manual lock; state follows health.\n",
    )
    add_file(
        "/manuals/commands/system.es.txt",
        "system on <system_id>\n"
        "system off <system_id>\n"
        "- Cambia el estado manual de energía de un subsistema.\n"
        "- 'off' fuerza el sistema a offline (sin carga).\n"
        "- 'on' libera el bloqueo manual; el estado sigue la salud.\n",
    )
    add_file(
        "/manuals/commands/repair.en.txt",
        "drone repair <drone_id> <system_id>\n"
        "repair <system_id> --selftest\n"
        "- Repairs a system using a drone.\n"
        "- Self-test repair is slower and requires a Self-Test Rig module.\n"
        "- Repair operations require deployed drone units.\n",
    )
    add_file(
        "/manuals/commands/repair.es.txt",
        "drone repair <drone_id> <system_id>\n"
        "repair <system_id> --selftest\n"
        "- Repara un sistema con un dron.\n"
        "- La auto-reparación es más lenta y requiere el módulo Self-Test Rig.\n"
        "- Las reparaciones requieren drones desplegados.\n",
    )
    add_file(
        "/manuals/commands/wait.txt",
        "wait <segundos>\n"
        "- Avanza el tiempo del simulador.\n"
        "- Útil para completar jobs.\n",
    )
    add_file(
        "/manuals/commands/jobs.en.txt",
        "jobs\n"
        "- Shows queued/running jobs and recent results.\n"
        "- Columns: id status type target ETA owner.\n",
    )
    add_file(
        "/manuals/commands/jobs.es.txt",
        "jobs\n"
        "- Muestra trabajos en cola/ejecución y recientes.\n"
        "- Columnas: id estado tipo objetivo ETA owner.\n",
    )
    add_file(
        "/manuals/commands/alerts.en.txt",
        "alerts\n"
        "- Lists active alerts.\n"
        "- Critical alerts require attention.\n"
        "alerts explain <alert_key>\n"
        "- Shows explanation and current values.\n",
    )
    add_file(
        "/manuals/commands/alerts.es.txt",
        "alerts\n"
        "- Lista alertas activas.\n"
        "- Las críticas requieren atención.\n"
        "alerts explain <alert_key>\n"
        "- Muestra explicación y valores actuales.\n",
    )
    add_file(
        "/manuals/commands/inventory.en.txt",
        "SHIP OS — Cargo Manifest / Audit Procedure\n"
        "Ref: OS-MAN/CMD/CARGO-01\n"
        "\n"
        "The sarcophagus terminal distinguishes between:\n"
        "\n"
        "Cargo (truth)\n"
        "What is physically stored in the hold. Cargo changes immediately when you salvage materials,\n"
        "install modules, or consume resources.\n"
        "\n"
        "Manifest (record)\n"
        "What the ship's record believes is stored. The manifest can become stale after field operations,\n"
        "power loss, or partial subsystem failures.\n"
        "\n"
        "The sarcophagus terminal reads the manifest, so you may see old totals until an audit is run.\n"
        "\n"
        "Commands\n"
        "\n"
        "inventory\n"
        "Shows the manifest (record view). If stale, the terminal will indicate it.\n"
        "\n"
        "cargo audit / inventory audit\n"
        "Queues an audit job and synchronizes the manifest with the actual hold contents.\n"
        "\n"
        "Audits take time. Under instability (low Q) they may be delayed or incomplete (future behavior).\n"
        "\n"
        "Operational notes\n"
        "\n"
        "Salvage and module installation affect cargo immediately.\n"
        "\n"
        "Audit updates only the manifest.\n"
        "\n"
        "Installation costs are deducted from cargo even if the manifest is stale.\n"
        "Audit requirements\n"
        "- Cargo audits require data_core to be online and the service datad running.\n"
        "- In CRUISE, restore NORMAL (power plan normal) before auditing.\n",
    )
    add_file(
        "/manuals/commands/inventory.es.txt",
        "SHIP OS — Manifiesto de bodega / Procedimiento de auditoría\n"
        "Ref: OS-MAN/CMD/CARGO-01\n"
        "\n"
        "La terminal del sarcófago distingue entre:\n"
        "\n"
        "Cargo (verdad)\n"
        "Lo que está físicamente en la bodega. El cargo cambia inmediatamente cuando recuperas materiales, instalas módulos o consumes recursos.\n"
        "\n"
        "Manifest (registro)\n"
        "Lo que el registro de la nave cree que hay almacenado. El manifiesto puede quedar desactualizado tras operaciones de campo, pérdida de energía o fallos parciales de subsistemas.\n"
        "\n"
        "La terminal del sarcófago consulta el manifest, por lo que puedes ver totales antiguos hasta que se realice una auditoría.\n"
        "\n"
        "Comandos\n"
        "\n"
        "inventory\n"
        "Muestra el manifest (vista del registro). Si está desactualizado, la terminal lo indicará.\n"
        "\n"
        "cargo audit / inventory audit\n"
        "Lanza un trabajo de auditoría y sincroniza el manifest con el contenido real de la bodega.\n"
        "\n"
        "Las auditorías requieren tiempo. Con inestabilidad (Q baja) pueden demorarse o resultar incompletas (comportamiento futuro).\n"
        "\n"
        "Notas operativas\n"
        "\n"
        "Recuperación de materiales e instalación de módulos afectan al cargo inmediatamente.\n"
        "\n"
        "La auditoría actualiza solo el manifest.\n"
        "\n"
        "Los costes de instalación se descuentan del cargo, aunque el manifest esté desactualizado.\n"
        "Requisitos de auditoría\n"
        "- La auditoría requiere data_core operativo y el servicio datad en ejecución.\n"
        "- En CRUISE, vuelve a NORMAL (power plan normal) antes de auditar.\n",
    )
    add_file(
        "/manuals/commands/install.en.txt",
        "install <module_id>\n"
        "- Installs a module from inventory.\n"
        "- Consumes the module item.\n",
    )
    add_file(
        "/manuals/commands/install.es.txt",
        "install <module_id>\n"
        "- Instala un módulo del inventario.\n"
        "- Consume el módulo.\n",
    )
    add_file(
        "/manuals/commands/travel.en.txt",
        "travel <node_id>\n"
        "- Start an interstellar transit to the target node.\n"
        "- Shows ETA in years; ship goes in-transit until arrival.\n"
        "- Operational commands are blocked during transit.\n",
    )
    add_file(
        "/manuals/commands/travel.es.txt",
        "travel <node_id>\n"
        "- Inicia un tránsito interestelar hacia el nodo destino.\n"
        "- Muestra ETA en años; la nave queda en tránsito hasta llegar.\n"
        "- Los comandos operativos quedan bloqueados en tránsito.\n",
    )
    add_file(
        "/manuals/commands/hibernate.en.txt",
        "hibernate until_arrival | hibernate <years>\n"
        "- Advances time in large chunks during transit.\n"
        "- until_arrival sleeps until the current trip ends.\n"
        "- Suppresses intermediate spam; shows arrival and critical events.\n",
    )
    add_file(
        "/manuals/commands/hibernate.es.txt",
        "hibernate until_arrival | hibernate <años>\n"
        "- Avanza el tiempo en bloques grandes durante el tránsito.\n"
        "- until_arrival duerme hasta el fin del viaje actual.\n"
        "- Suprime el ruido intermedio; muestra llegada y eventos críticos.\n",
    )
    add_file(
        "/manuals/commands/modules.en.txt",
        "modules\n"
        "- Lists available module definitions.\n"
        "- Use to inspect install options.\n",
    )
    add_file(
        "/manuals/commands/modules.es.txt",
        "modules\n"
        "- Lista módulos disponibles.\n"
        "- Úsalo para ver opciones de instalación.\n",
    )
    add_file(
        "/manuals/concepts/power.en.txt",
        "POWER\n"
        "- P_gen: generation (kW)\n"
        "- P_load: current load (kW)\n"
        "- net: P_gen - P_load (positive = charging)\n"
        "- SoC: battery state of charge (0..1)\n"
        "- headroom: remaining discharge margin (kW)\n"
        "- Q (power_quality): stability of the bus (0..1)\n"
        "- brownout: True when overdraw persists\n"
        "Recommended:\n"
        " - reduce load or shed non-critical systems\n"
        " - repair energy_distribution if Q is low\n"
        " - install stabilizers / extra batteries when possible\n",
    )
    add_file(
        "/manuals/concepts/power.es.txt",
        "ENERGÍA\n"
        "- P_gen: generación (kW)\n"
        "- P_load: carga actual (kW)\n"
        "- neto: P_gen - P_load (positivo = cargando)\n"
        "- SoC: estado de carga de baterías (0..1)\n"
        "- margen: descarga restante (kW)\n"
        "- Q (power_quality): estabilidad del bus (0..1)\n"
        "- brownout: True cuando el sobreconsumo persiste\n"
        "Recomendado:\n"
        " - reducir carga o cortar sistemas no críticos\n"
        " - reparar energy_distribution si Q es baja\n"
        " - instalar estabilizadores / baterías extra cuando sea posible\n",
    )
    add_file(
        "/manuals/systems/core_os.en.txt",
        "core_os\n"
        "- Bridge kernel and control stack. Keeps the ship coherent.\n"
        "- Tags: critical. Power draw is modest but ever-present.\n"
        "- Dependencies: none. Keep power stable to avoid resets.\n"
        "- Related commands: status, diag core_os.\n",
    )
    add_file(
        "/manuals/systems/core_os.es.txt",
        "core_os\n"
        "- Núcleo de control y coordinación. Mantiene la nave coherente.\n"
        "- Tags: crítico. Consumo modesto pero continuo.\n"
        "- Dependencias: ninguna. Mantén energía estable para evitar resets.\n"
        "- Comandos: status, diag core_os.\n",
    )
    add_file(
        "/manuals/systems/life_support.en.txt",
        "life_support\n"
        "- Atmosphere, pressure, and environmental control for crew.\n"
        "- Tags: critical. Higher draw; degrades faster under bad power.\n"
        "- Dependencies: stable power distribution.\n"
        "- Related commands: status, diag life_support.\n",
    )
    add_file(
        "/manuals/systems/life_support.es.txt",
        "life_support\n"
        "- Atmósfera, presión y control ambiental para la tripulación.\n"
        "- Tags: crítico. Consumo alto; degrada más rápido con mala energía.\n"
        "- Dependencias: distribución estable.\n"
        "- Comandos: status, diag life_support.\n",
    )
    add_file(
        "/manuals/systems/power_core.en.txt",
        "power_core\n"
        "- Primary generation core. Provides baseline P_gen.\n"
        "- Tags: critical. Degraded state reduces stability and Q.\n"
        "- Dependencies: distribution nominal to avoid instability.\n"
        "- Related commands: diag power_core, install modules to boost.\n",
    )
    add_file(
        "/manuals/systems/power_core.es.txt",
        "power_core\n"
        "- Núcleo principal de generación. Fuente de P_gen base.\n"
        "- Tags: crítico. En degradado reduce estabilidad y Q.\n"
        "- Dependencias: distribución nominal para evitar inestabilidad.\n"
        "- Comandos: diag power_core, install módulos para mejorar.\n",
    )
    add_file(
        "/manuals/systems/energy_distribution.en.txt",
        "energy_distribution\n"
        "- Routes power across subsystems. Locked if badly damaged.\n"
        "- Tags: critical. Poor state lowers Q and blocks boots.\n"
        "- Dependencies: healthy enough to unlock services.\n"
        "- Related commands: status, diag energy_distribution.\n",
    )
    add_file(
        "/manuals/systems/energy_distribution.es.txt",
        "energy_distribution\n"
        "- Enruta energía entre subsistemas. Bloquea si está muy dañado.\n"
        "- Tags: crítico. Mal estado reduce Q y bloquea arranques.\n"
        "- Dependencias: salud suficiente para desbloquear servicios.\n"
        "- Comandos: status, diag energy_distribution.\n",
    )
    add_file(
        "/manuals/systems/sensors.en.txt",
        "sensors\n"
        "- External signal detection. Boots sensord to detect contacts.\n"
        "- Tags: locked initially. Requires distribution nominal.\n"
        "- Related commands: boot sensord, contacts, scan, diag sensors.\n",
    )
    add_file(
        "/manuals/systems/sensors.es.txt",
        "sensors\n"
        "- Detección de señales externas. Arranca sensord para contactos.\n"
        "- Tags: bloqueado al inicio. Requiere distribución nominal.\n"
        "- Comandos: boot sensord, contacts, scan, diag sensors.\n",
    )
    add_file(
        "/manuals/commands/contacts.en.txt",
        "contacts | scan\n"
        "- Lists detected signals.\n"
        "- Requires sensord active.\n",
    )
    add_file(
        "/manuals/commands/contacts.es.txt",
        "contacts | scan\n"
        "- Lista señales detectadas.\n"
        "- Requiere sensord activo.\n",
    )
    add_file(
        "/manuals/commands/dock.en.txt",
        "dock <node_id>\n"
        "- Dock the ship at a node.\n"
        "- Must be a known contact.\n",
    )
    add_file(
        "/manuals/commands/dock.es.txt",
        "dock <node_id>\n"
        "- Acopla la nave al nodo.\n"
        "- Debe ser contacto conocido.\n",
    )
    add_file(
        "/manuals/commands/salvage.en.txt",
        "drone salvage scrap <drone_id> <node_id> <amount>\n"
        "drone salvage module <drone_id> [node_id]\n"
        "- Salvage scrap or modules from a node.\n"
        "- Drone must be deployed at the node.\n"
        "- If node_id is omitted, uses the drone's current node.\n",
    )
    add_file(
        "/manuals/commands/salvage.es.txt",
        "drone salvage scrap <drone_id> <node_id> <amount>\n"
        "drone salvage module <drone_id> [node_id]\n"
        "- Recupera chatarra o módulos del nodo.\n"
        "- El dron debe estar desplegado en el nodo.\n"
        "- Si no se indica node_id, se usa el nodo actual del dron.\n",
    )
    add_file(
        "/manuals/commands/drone.en.txt",
        "drone deploy <drone_id> <sector_id>\n"
        "drone deploy! <drone_id> <sector_id>\n"
        "drone move <drone_id> <target_id>\n"
        "drone repair <drone_id> <system_id>\n"
        "drone salvage scrap <drone_id> <node_id> <amount>\n"
        "drone salvage module <drone_id> [node_id]\n"
        "drone reboot <drone_id>\n"
        "drone recall <drone_id>\n"
        "- Deploys a drone to a ship sector.\n"
        "- Use 'sectors' to list available ship sectors.\n"
        "- Move repositions a deployed drone between sectors or nodes.\n"
        "- If deploy is blocked by dependencies, use deploy! for emergency override.\n"
        "- Emergency deploy may risk failure and drone damage.\n"
        "- Drones consume battery on jobs and movement.\n"
        "- Docked drones recharge in the bay if it is at least LIMITED.\n"
        "- Docked drones can be repaired slowly using scrap.\n"
        "- Reboot attempts recovery of a disabled drone.\n",
    )
    add_file(
        "/manuals/commands/drone.es.txt",
        "drone deploy <drone_id> <sector_id>\n"
        "drone deploy! <drone_id> <sector_id>\n"
        "drone move <drone_id> <target_id>\n"
        "drone repair <drone_id> <system_id>\n"
        "drone salvage scrap <drone_id> <node_id> <amount>\n"
        "drone salvage module <drone_id> [node_id]\n"
        "drone reboot <drone_id>\n"
        "drone recall <drone_id>\n"
        "- Despliega un dron a un sector de la nave.\n"
        "- Usa 'sectors' para listar sectores disponibles.\n"
        "- Move reposiciona un dron desplegado entre sectores o nodos.\n"
        "- Si el despliegue está bloqueado por dependencias, usa deploy! como anulación de emergencia.\n"
        "- El despliegue de emergencia puede fallar y dañar al dron.\n"
        "- Los drones consumen batería en trabajos y desplazamientos.\n"
        "- En el dock recargan si la bahía está al menos en LIMITED.\n"
        "- En el dock se reparan lentamente usando chatarra.\n"
        "- Reboot intenta recuperar un dron deshabilitado.\n",
    )
    add_file(
        "/manuals/systems/energy_distribution.en.txt",
        "energy_distribution\n"
        "- Power routing subsystem.\n"
        "- When integrity drops below nominal, downstream systems may refuse to initialize.\n",
    )
    add_file(
        "/manuals/systems/energy_distribution.es.txt",
        "energy_distribution\n"
        "- Enrutamiento de energía.\n"
        "- Cuando la integridad cae bajo nominal, algunos sistemas pueden negarse a iniciar.\n",
    )
    add_file(
        "/manuals/systems/power_core.en.txt",
        "power_core\n"
        "- Primary generation core.\n"
        "- Degraded state reduces stability.\n",
        access=AccessLevel.ENG,
    )
    add_file(
        "/manuals/systems/power_core.es.txt",
        "power_core\n"
        "- Núcleo de generación primaria.\n"
        "- Estado degradado reduce estabilidad.\n",
        access=AccessLevel.ENG,
    )
    add_file(
        "/manuals/systems/sensors.en.txt",
        "sensors\n"
        "- External signal detection.\n"
        "- Boot sensord to activate.\n",
    )
    add_file(
        "/manuals/systems/sensors.es.txt",
        "sensors\n"
        "- Detección de señales externas.\n"
        "- Boot sensord para activar.\n",
    )
    add_file(
        "/manuals/systems/data_core.en.txt",
        "data_core\n"
        "- Data services and audit subsystem.\n"
        "- Required for cargo/manifest audit (datad).\n"
        "- If offline or degraded, inventory audit is blocked.\n"
        "- Keep at least LIMITED for reliable audits.\n"
        "- Related commands: boot datad, cargo audit.\n",
    )
    add_file(
        "/manuals/systems/data_core.es.txt",
        "data_core\n"
        "- Servicios de datos y auditoría.\n"
        "- Requerido para auditoría de bodega (datad).\n"
        "- Si está offline o degradado, se bloquea la auditoría.\n"
        "- Mantén al menos LIMITED para auditorías fiables.\n"
        "- Comandos: boot datad, cargo audit.\n",
    )
    add_file(
        "/manuals/systems/drone_bay.en.txt",
        "drone_bay\n"
        "- Drone launch subsystem.\n"
        "- In emergencies use deploy!.\n",
    )
    add_file(
        "/manuals/systems/drone_bay.es.txt",
        "drone_bay\n"
        "- Salida de drones al casco.\n"
        "- En emergencia usa deploy!.\n",
    )
    add_file(
        "/manuals/alerts/power_net_deficit.en.txt",
        "power_net_deficit\n"
        "- Load exceeds generation (battery may cover the gap).\n"
        "- Typical causes: high load, low generation, damaged core.\n"
        "- If persistent: reduced quality, possible brownout if headroom runs out.\n"
        "Recommended: reduce load, repair power_core, charge batteries.\n",
    )
    add_file(
        "/manuals/alerts/power_net_deficit.es.txt",
        "power_net_deficit\n"
        "- La carga supera la generación (la batería puede cubrir el hueco).\n"
        "- Causas típicas: carga alta, baja generación, core dañado.\n"
        "- Si persiste: menor calidad, posible brownout si se agota el margen.\n"
        "Recomendado: reduce consumo, aumenta generación, recarga baterías.\n",
    )
    add_file(
        "/manuals/alerts/low_power_quality.en.txt",
        "low_power_quality\n"
        "- Power quality below nominal range.\n"
        "- Causes: low SoC, sustained deficit, distribution damage.\n"
        "- If persistent: system degradation accelerates.\n"
        "Recommended: stabilize distribution, reduce load, restore SoC.\n",
    )
    add_file(
        "/manuals/alerts/low_power_quality.es.txt",
        "low_power_quality\n"
        "- Calidad de energía por debajo del rango nominal.\n"
        "- Causas: SoC bajo, déficit sostenido, distribución dañada.\n"
        "- Si persiste: degradación acelerada de sistemas.\n"
        "Recomendado: recarga baterías, reduce carga, repara `energy_distribution`.\n",
    )
    add_file(
        "/manuals/alerts/power_bus_instability.en.txt",
        "power_bus_instability\n"
        "- Distribution bus instability detected.\n"
        "- Often tied to damaged energy_distribution.\n"
        "- If persistent: intermittent shutdowns, sensor dropouts.\n"
        "Recommended: repair energy_distribution, reduce load.\n",
    )
    add_file(
        "/manuals/alerts/power_bus_instability.es.txt",
        "power_bus_instability\n"
        "- Inestabilidad detectada en el bus de distribución.\n"
        "- Suele asociarse a energy_distribution dañado.\n"
        "- Si persiste: apagados intermitentes, pérdida de sensores.\n"
        "Recomendado: repara `energy_distribution`, reduce carga.\n",
    )
    add_file(
        "/manuals/modules/bus_stabilizer.en.txt",
        "bus_stabilizer\n"
        "- Phase-lock filter for aging distribution busses.\n"
        "- Dampens transient spikes and line noise.\n"
        "- Restores smoother load-sharing across subsystems.\n"
        "- Common in long-haul retrofit kits.\n"
        "- Installation requires brief bus re-sync.\n"
        "- Side effect: slightly higher idle draw.\n"
        "- Recommended when Q is unstable.\n"
        "Lore: These units were nicknamed \"calmers\" by deck crews.\n",
    )
    add_file(
        "/manuals/modules/bus_stabilizer.es.txt",
        "bus_stabilizer\n"
        "- Filtro de fase para buses de distribución envejecidos.\n"
        "- Atenúa picos transitorios y ruido de línea.\n"
        "- Suaviza el reparto de carga entre subsistemas.\n"
        "- Común en kits de modernización de largo alcance.\n"
        "- La instalación requiere una resincronización breve.\n"
        "- Efecto secundario: mayor consumo en reposo.\n"
        "- Recomendado cuando Q es inestable.\n"
        "Lore: En la tripulación se le llamaba \"calmador\".\n",
    )
    add_file(
        "/manuals/modules/aux_battery_cell.en.txt",
        "aux_battery_cell\n"
        "- Auxiliary LiFe cell pack for emergency buffer.\n"
        "- Raises maximum capacity without altering core chemistry.\n"
        "- Slows depth-of-discharge stress during deficits.\n"
        "- Installation is non-invasive to power core.\n"
        "- Best paired with stable distribution.\n"
        "Lore: The original vendor marketed these as \"lifeboat cells\".\n",
    )
    add_file(
        "/manuals/modules/aux_battery_cell.es.txt",
        "aux_battery_cell\n"
        "- Pack auxiliar de celdas LiFe para amortiguación.\n"
        "- Aumenta la capacidad máxima sin tocar la química base.\n"
        "- Reduce el estrés por descargas profundas.\n"
        "- Instalación no invasiva al núcleo de energía.\n"
        "- Mejor rendimiento con distribución estable.\n"
        "Lore: El fabricante los vendía como \"celdas salvavidas\".\n",
    )
    add_file(
        "/manuals/modules/micro_reactor_patch.en.txt",
        "micro_reactor_patch\n"
        "- Micro-injector retrofit for tired reactor cores.\n"
        "- Improves fuel mixing and thermal balance.\n"
        "- Grants a small but steady generation increase.\n"
        "- Requires careful calibration after install.\n"
        "- Not recommended if the core is critical.\n"
        "Lore: Field engineers dubbed it \"the whisper patch\".\n",
    )
    add_file(
        "/manuals/modules/micro_reactor_patch.es.txt",
        "micro_reactor_patch\n"
        "- Retroadaptación de microinyectores para núcleos fatigados.\n"
        "- Mejora mezcla de combustible y balance térmico.\n"
        "- Aporta un aumento estable de generación.\n"
        "- Requiere calibración cuidadosa tras instalar.\n"
        "- No recomendado si el core está en estado crítico.\n"
        "Lore: Los ingenieros lo llamaban \"parche susurro\".\n",
    )
    add_file(
        "/manuals/modules/selftest_rig.en.txt",
        "selftest_rig\n"
        "- Self-test and calibration harness for onboard subsystems.\n"
        "- Enables internal repair cycles without drones.\n"
        "- Best used for limited systems that cannot spare drone time.\n"
        "- Slower than field repair but safer for critical bays.\n"
        "Lore: The rig was designed for stations that ran with skeleton crews.\n",
    )
    add_file(
        "/manuals/modules/selftest_rig.es.txt",
        "selftest_rig\n"
        "- Arnés de auto‑prueba y calibración para subsistemas.\n"
        "- Habilita ciclos internos de reparación sin drones.\n"
        "- Útil en sistemas LIMITADOS cuando no hay drones disponibles.\n"
        "- Más lento que la reparación de campo, pero más seguro.\n"
        "Lore: Se diseñó para estaciones con tripulación mínima.\n",
    )

    add_file(
        "/mail/inbox/0000.notice.txt",
        "EN: Language can be changed with: config set lang en|es\n"
        "ES: El idioma se puede cambiar con: config set lang en|es\n",
    )
    add_file(
        "/mail/inbox/0001.en.txt",
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
        "/mail/inbox/0001.es.txt",
        "FROM: Autonomous Systems\n"
        "SUBJ: Emergency Wake Event\n"
        "\n"
        "Condición de despertar activada por inestabilidad de energía.\n"
        "\n"
        "Integridad de la red de distribución primaria bajo umbrales nominales.\n"
        "La salida del núcleo fluctúa.\n"
        "\n"
        "Protocolos de mantenimiento de emergencia disponibles para el operador consciente.\n"
        "\n"
        "Acciones recomendadas:\n"
        " - revisar diagnósticos del sistema\n"
        " - evaluar disponibilidad de drones de mantenimiento\n"
        " - estabilizar la infraestructura de señal\n"
        "\n"
        "Advertencia: fallas en cascada posibles si la inestabilidad persiste.\n"
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
