from __future__ import annotations

from retorno.core.gamestate import GameState
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import AlertState, Event, EventType, Severity, SourceRef
from retorno.model.ship import PowerNetworkState, ShipSector
from retorno.model.os import AccessLevel, FSNode, FSNodeType, Locale, normalize_path, register_mail
from retorno.model.systems import Dependency, ServiceState, ShipSystem, SystemState
from retorno.model.world import SpaceNode, region_for_pos, sector_id_for_pos, add_known_link
from retorno.worldgen.generator import ensure_sector_generated
from retorno.runtime.data_loader import load_modules, load_locations
from retorno.config.balance import Balance
import random
from pathlib import Path


def create_initial_state_prologue() -> GameState:
    state = GameState()

    state.ship.power = PowerNetworkState(
        p_gen_kw=3.2,
        p_gen_base_kw=3.2,
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
    state.ship.cargo_scrap = Balance.STARTING_SCRAP

    state.ship.sectors = {
        "DRN-BAY": ShipSector(sector_id="DRN-BAY", name="Drone Bay", tags={"bay"}),
        "PWR-A2": ShipSector(sector_id="PWR-A2", name="Power Trunk A2", tags={"power"}),
        "BRG-01": ShipSector(sector_id="BRG-01", name="Bridge Access", tags={"restricted"}),
        "CRG-01": ShipSector(sector_id="CRG-01", name="Cargo Hold", tags={"cargo"}),
    }

    state.world.current_node_id = "UNKNOWN_00"
    state.ship.current_node_id = state.world.current_node_id
    state.world.visited_nodes.add(state.world.current_node_id)
    rng = random.Random(state.meta.rng_seed)
    modules = load_modules()
    module_ids = list(modules.keys())
    _bootstrap_locations(state, rng, module_ids)
    # Sync known_nodes for compatibility
    if state.world.known_contacts:
        state.world.known_nodes.update(state.world.known_contacts)
    current_node = state.world.space.nodes.get(state.world.current_node_id)
    if current_node:
        state.world.current_pos_ly = (current_node.x_ly, current_node.y_ly, current_node.z_ly)
        if current_node.node_id != "UNKNOWN_00":
            # Generate links for the current sector and seed known routes
            sector_id = sector_id_for_pos(current_node.x_ly, current_node.y_ly, current_node.z_ly)
            ensure_sector_generated(state, sector_id)
            if current_node.links:
                # If current node is not hub, reveal link to hub. Otherwise reveal one outgoing link.
                if not current_node.is_hub:
                    hub = next((n for n in state.world.space.nodes.values() if n.is_hub and sector_id_for_pos(n.x_ly, n.y_ly, n.z_ly) == sector_id), None)
                    if hub:
                        add_known_link(state.world, current_node.node_id, hub.node_id, bidirectional=True)
                        state.world.known_contacts.add(hub.node_id)
                        state.world.known_nodes.add(hub.node_id)
                else:
                    dest = sorted(current_node.links)[0]
                    add_known_link(state.world, current_node.node_id, dest, bidirectional=True)
                    state.world.known_contacts.add(dest)
                    state.world.known_nodes.add(dest)

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
    state.world.visited_nodes.add(state.world.current_node_id)
    node = state.world.space.nodes.get("ECHO_7")
    if node:
        state.world.current_pos_ly = (node.x_ly, node.y_ly, node.z_ly)

    # Known contacts for testing
    state.world.known_contacts.update({"ECHO_7", "HARBOR_12", "DERELICT_A3"})
    state.world.known_nodes.update({"ECHO_7", "HARBOR_12", "DERELICT_A3"})

    # Give some cargo for testing
    state.ship.cargo_scrap = max(state.ship.cargo_scrap, Balance.STARTING_SCRAP)
    state.ship.manifest_dirty = True

    return state

def _bootstrap_locations(state: GameState, rng: random.Random, module_ids: list[str]) -> None:
    locations = load_locations()
    if not locations:
        return

    def _pick_modules(cfg: dict) -> list[str]:
        if not module_ids:
            return []
        min_count = int(cfg.get("modules_min", 0))
        max_count = int(cfg.get("modules_max", 0))
        if max_count <= 0:
            return []
        count = rng.randint(min_count, max_count)
        pool = cfg.get("modules_pool", "all")
        modules = load_modules()
        pool_map: dict[str, list[str]] = {"common": [], "rare": [], "tech": []}
        for mid in module_ids:
            mod = modules.get(mid, {})
            tag = mod.get("pool", "common")
            pool_map.setdefault(tag, []).append(mid)
        if isinstance(pool, list) and pool:
            candidates = [m for m in pool if m in module_ids]
        elif isinstance(pool, str) and pool in pool_map:
            candidates = pool_map[pool]
        else:
            candidates = module_ids
        if not candidates:
            return []
        return [rng.choice(candidates) for _ in range(count)]

    def _access_level(value: str) -> AccessLevel:
        try:
            return AccessLevel(value)
        except Exception:
            return AccessLevel.GUEST

    for loc in locations:
        node_cfg = loc.get("node", {})
        node_id = node_cfg.get("node_id")
        if node_id == state.ship.ship_id:
            node_id = None
        if node_id and node_id not in state.world.space.nodes:
            node = SpaceNode(
                node_id=node_id,
                name=node_cfg.get("name", node_id),
                kind=node_cfg.get("kind", "unknown"),
                radiation_rad_per_s=float(node_cfg.get("radiation_rad_per_s", 0.0)),
                x_ly=float(node_cfg.get("x_ly", 0.0)),
                y_ly=float(node_cfg.get("y_ly", 0.0)),
                z_ly=float(node_cfg.get("z_ly", 0.0)),
            )
            if "is_hub" in node_cfg:
                node.is_hub = bool(node_cfg.get("is_hub"))
            else:
                node.is_hub = node.kind in {"relay", "station", "waystation", "ship", "derelict"}
            node.region = region_for_pos(node.x_ly, node.y_ly, node.z_ly)
            node.radiation_base = float(node_cfg.get("radiation_base", 0.0))
            salvage_cfg = loc.get("salvage") or {}
            if salvage_cfg:
                scrap_min = int(salvage_cfg.get("scrap_min", 0))
                scrap_max = int(salvage_cfg.get("scrap_max", 0))
                if scrap_max > 0:
                    node.salvage_scrap_available = rng.randint(scrap_min, scrap_max)
                node.salvage_modules_available = _pick_modules(salvage_cfg)
            state.world.space.nodes[node_id] = node
        if loc.get("known_on_start") and node_id:
            state.world.known_contacts.add(node_id)
            state.world.known_nodes.add(node_id)

        # Optional filesystem files (mails/logs) attached to location data.
        # Only load files that belong to the player ship location at bootstrap.
        if node_cfg.get("node_id") != state.ship.ship_id:
            continue
        fs_files = loc.get("fs_files", [])
        for file_cfg in fs_files:
            path = file_cfg.get("path")
            if not path:
                continue
            content = file_cfg.get("content", "")
            access = _access_level(file_cfg.get("access", "GUEST"))
            norm = normalize_path(path)
            state.os.fs[norm] = FSNode(path=norm, node_type=FSNodeType.FILE, content=content, access=access)
            register_mail(state.os, norm, state.clock.t)


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
        fs[norm] = FSNode(path=norm, node_type=FSNodeType.FILE, content=content, access=access)

    def _load_manuals_from_disk() -> None:
        if not manuals_root.exists():
            return
        for path in manuals_root.rglob("*.txt"):
            if not path.is_file():
                continue
            rel = path.relative_to(manuals_root).as_posix()
            vpath = normalize_path(f"/manuals/{rel}")
            parent = normalize_path(str(Path(vpath).parent))
            if parent not in fs:
                add_dir(parent)
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                content = ""
            fs[vpath] = FSNode(
                path=vpath,
                node_type=FSNodeType.FILE,
                content=content,
                access=AccessLevel.GUEST,
            )

    add_dir("/")
    add_dir("/manuals")
    add_dir("/manuals/commands")
    add_dir("/manuals/concepts")
    add_dir("/manuals/systems")
    add_dir("/manuals/alerts")
    add_dir("/manuals/modules")
    add_dir("/mail")
    add_dir("/mail/inbox")
    add_dir("/data")
    add_dir("/data/nav")
    add_dir("/data/nav/fragments")
    add_dir("/logs", access=AccessLevel.ENG)
    add_dir("/logs/nav", access=AccessLevel.ENG)

    _load_manuals_from_disk()

    # Location-specific mails/logs are loaded from data/locations/*.json
