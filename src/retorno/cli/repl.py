from __future__ import annotations

import argparse
from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
import os
import hashlib
import math
import random
import readline
import select
import subprocess
import shutil
import sys
import termios
import time
import tty
from pathlib import Path
from retorno.audio.config import AudioConfigError, load_audio_config
from retorno.audio.manager import AudioManager
from retorno.core.engine import Engine
from retorno.core.lore import (
    build_lore_context,
    list_lore_piece_entries,
    maybe_deliver_lore,
    recompute_node_completion,
    sync_node_pools_for_known_nodes,
)
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.exploration_recovery import ensure_exploration_recovery, uplink_blocked_reason
from retorno.core.actions import Action, AuthRecover, Hibernate, RouteSolve, Status
from retorno.runtime.loop import GameLoop
from retorno.runtime.operator_config import (
    apply_config_value,
    audio_flags,
    config_keys,
    config_show_lines,
    config_value_choices,
    resolve_help_verbose,
)
from retorno.core.power_policy import is_parsed_command_allowed_in_core_os_critical
from retorno.model.events import Event, EventType, Severity, SourceRef
from retorno.model.jobs import JobStatus, JobType, active_job_display_ids
from retorno.runtime.data_loader import load_modules, load_arcs, load_locations, load_worldgen_archetypes, load_worldgen_templates
from retorno.runtime.startup import load_startup_sequence_lines
from retorno.config.balance import Balance
from retorno.io.save_load import (
    LoadGameResult,
    SaveLoadError,
    load_single_slot,
    normalize_user_id,
    resolve_save_path,
    save_exists,
    save_single_slot,
)
from retorno.model.systems import SystemState
from retorno.model.drones import DroneLocation, DroneState, DroneStatus, compute_drone_effective_profile
from retorno.model.os import AccessLevel, FSNode, FSNodeType, Locale, list_dir, normalize_path, read_file, required_access_label
from retorno.model.galaxy import (
    galactic_margins_for_op_pos,
    galactic_radius,
    galactic_region_for_op_pos,
    legacy_operational_region_for_pos,
    op_to_galactic_coords,
)
from retorno.model.world import (
    SECTOR_SIZE_LY,
    add_known_link,
    distance_between_nodes_ly,
    is_hop_within_cap,
    record_intel,
    sector_id_for_pos,
)
from retorno.model.world import SpaceNode, region_for_pos
from retorno.worldgen.generator import ensure_sector_generated, procedural_radiation_for_node, sync_sector_state_for_node
from retorno.util.timefmt import format_elapsed_long, format_elapsed_short


def _maybe_run_startup_sequence(locale: str) -> None:
    if not Balance.STARTUP_SEQUENCE_ENABLED:
        return
    lines = load_startup_sequence_lines(locale)
    if not lines:
        return
    print("\033[2J\033[H", end="")
    _play_startup_sequence(lines)
    _print_startup_tips(locale)


def _print_startup_tips(locale: str) -> None:
    tips = {
        "en": [
            "\n[INFO] new mail detected.",
            "Tip: use 'mail inbox' to list messages.",
            "Tip: use 'mail read <id|latest>' or 'cat <path>' to read.",
            "Tip: if you still don't remember the command instructions, manuals are under /manuals (try: ls /manuals/commands, man <topic>).",
            "Tip: use 'config set lang' to change ship_os languaje",
            "Tip: use 'help' to see available commands.",
            "Tip: use TAB key for list and autocomplete available commands, id's, paths, etc.",
        ],
        "es": [
            "\n[INFO]: se han recibido mensajes nuevos.",
            "Consejo: usa 'mail inbox' para listarlos.",
            "Consejo: usa 'mail read <id|latest>' o 'cat <path> para leer.",
            "Consejo: si aún no recuerda la instrucción de operaciones, los manuales están en /manuals (prueba: ls /manuals/commands, man <tema>).",
            "Consejo: introduce 'config set lang' para cambiar el idioma de ship_os",
            "Consejo: usa 'help' para ver los comandos disponibles.",
            "Consejo: usa la tecla TAB para listar y/o completar automáticamente comandos disponibles, identificaciones, rutas, etc.",
            
        ],
    }
    for line in tips.get(locale, tips["en"]):
        print(line)


def _play_startup_sequence(lines: list[str]) -> None:
    typewriter = Balance.STARTUP_SEQUENCE_TYPEWRITER
    cps = max(1, int(Balance.STARTUP_SEQUENCE_TYPEWRITER_CPS))
    line_delay_s = max(0.0, float(Balance.STARTUP_SEQUENCE_LINE_DELAY_S))
    skippable = Balance.STARTUP_SEQUENCE_SKIPPABLE and sys.stdin.isatty()
    skip = False

    def _check_skip_escape() -> bool:
        if not skippable:
            return False
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
        except Exception:
            return False
        if not ready:
            return False
        try:
            ch = sys.stdin.read(1)
        except Exception:
            return False
        return ch == "\x1b"

    def _sleep_with_skip(seconds: float) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            if _check_skip_escape():
                return True
            time.sleep(0.05)
        return False

    def _write_line(line: str) -> bool:
        nonlocal skip
        if typewriter:
            for ch in line:
                if _check_skip_escape():
                    skip = True
                    return True
                sys.stdout.write(ch)
                sys.stdout.flush()
                time.sleep(1.0 / cps)
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            if _check_skip_escape():
                skip = True
                return True
            print(line)
        return False

    if skippable:
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except Exception:
            skippable = False
            old = None
    else:
        old = None

    try:
        for line in lines:
            if skip:
                break
            if _write_line(line):
                break
            if line_delay_s > 0.0 and _sleep_with_skip(line_delay_s):
                break
    finally:
        if skippable and old is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass

def print_help(locale: str = "en", verbose: bool = False) -> None:
    lang = "es" if locale == "es" else "en"
    sections: list[tuple[str, str, list[tuple[str, str, str]]]] = [
        (
            "Commands (summary)",
            "Comandos (resumen)",
            [
                ("help", "show command list", "muestra lista de comandos"),
                ("help --verbose", "show command list with short descriptions", "muestra comandos con descripciones breves"),
                ("help --no-verbose", "show command list without descriptions", "muestra comandos sin descripciones"),
                ("clear", "clear terminal output", "limpia salida de terminal"),
                ("exit", "save and close session", "guarda y cierra sesión"),
                ("quit", "save and close session", "guarda y cierra sesión"),
            ],
        ),
        (
            "FS / Manuals / Mail",
            "FS / Manuales / Correo",
            [
                ("ls [path]", "list directory entries", "lista entradas de directorio"),
                ("cat <path>", "show file content", "muestra contenido de archivo"),
                ("man <topic>", "open manual topic", "abre tema de manual"),
                ("about <system_id>", "show system summary", "muestra resumen de sistema"),
                ("mail inbox", "list inbox messages", "lista mensajes del buzón"),
                ("mail read <id|latest>", "read one inbox message", "lee un mensaje del buzón"),
                ("auth status", "show auth levels", "muestra niveles de acceso"),
                ("auth recover <level>", "attempt access recovery", "intenta recuperación de acceso"),
                ("intel", "list latest intel", "lista intel reciente"),
                ("intel <amount>", "list N latest intel entries", "lista N entradas de intel"),
                ("intel all", "list all intel entries", "lista toda la intel"),
                ("intel show <intel_id>", "show one intel entry", "muestra una entrada de intel"),
                ("intel import <path>", "import intel from file", "importa intel desde archivo"),
                ("intel export <path>", "export intel to file", "exporta intel a archivo"),
                ("config set lang <en|es>", "set interface language", "cambia idioma de interfaz"),
                ("config set verbose <on|off>", "toggle default help verbosity", "activa o desactiva la verbosidad por defecto de help"),
                ("config set audio <on|off>", "toggle all game audio", "activa o desactiva todo el audio"),
                ("config set ambientsound <on|off>", "toggle ambient loop", "activa o desactiva el loop ambiental"),
                ("config show", "show current config", "muestra configuración actual"),
            ],
        ),
        (
            "Info",
            "Información",
            [
                ("status", "show ship/system status", "muestra estado de nave/sistemas"),
                ("jobs", "show active jobs", "muestra trabajos activos"),
                ("jobs <amount>", "show first N active jobs", "muestra primeros N trabajos activos"),
                ("jobs all", "show all active jobs", "muestra todos los trabajos activos"),
                ("job cancel <job_id>", "cancel one job", "cancela un trabajo"),
                ("alerts", "show active alerts", "muestra alertas activas"),
                ("alerts explain <alert_key>", "explain one alert key", "explica una alerta"),
                ("logs", "show recent event logs", "muestra eventos recientes"),
                ("log copy [n]", "copy last N log lines", "copia últimas N líneas de log"),
                ("scan", "perform local sensor scan", "realiza escaneo local"),
                ("ship sectors", "show ship internal sectors", "muestra sectores internos de la nave"),
                ("ship survey <target>", "show concise target telemetry", "muestra telemetría concisa del objetivo"),
                ("locate <system_id>", "show known system position", "muestra posición conocida del sistema"),
            ],
        ),
        (
            "Navigation",
            "Navegación",
            [
                ("nav map sectors", "list known world sectors", "lista sectores del mundo conocidos"),
                (
                    "nav map galaxy [sector|local|regional|global]",
                    "show galactic map at selected scale (known nodes)",
                    "muestra mapa galáctico en escala seleccionada (nodos conocidos)",
                ),
                (
                    "nav galaxy [sector|local|regional|global]",
                    "alias of nav map galaxy",
                    "alias de nav map galaxy",
                ),
                ("nav map graph [node_id]", "show known route graph", "muestra grafo de rutas conocido"),
                ("nav map path <node_id>", "show best known path", "muestra mejor camino conocido"),
                ("nav map routes", "list direct known routes", "lista rutas directas conocidas"),
                ("nav map contacts", "list known contacts", "lista contactos conocidos"),
                ("nav <node_id>", "start transit to node", "inicia tránsito al nodo"),
                ("nav --no-cruise <node_id>", "start transit without cruise profile", "inicia tránsito sin perfil cruise"),
                ("nav abort", "abort active transit", "aborta tránsito activo"),
                ("dock <node_id>", "dock at current node", "acopla en nodo actual"),
                ("undock", "undock from current node", "desacopla del nodo actual"),
                ("uplink", "pull route intel from docked hub", "extrae intel de rutas desde hub acoplado"),
                ("route solve <node_id>", "compute route solution in range", "calcula solución de ruta en rango"),
                ("hibernate until_arrival", "hibernate until transit arrival", "hiberna hasta la llegada"),
                ("hibernate <years>", "hibernate for fixed years", "hiberna un número de años"),
                (
                    "debug galaxy map <sector|local|regional|global>",
                    "render debug galaxy map (debug mode)",
                    "muestra mapa galáctico debug (modo debug)",
                ),
            ],
        ),
        (
            "Systems / Power",
            "Sistemas / Energía",
            [
                ("diag <system_id>", "inspect system diagnostics", "inspecciona diagnóstico del sistema"),
                ("boot <service_name>", "start system service", "arranca servicio de sistema"),
                ("power status", "show power telemetry", "muestra telemetría eléctrica"),
                ("power plan cruise", "set cruise power profile", "activa plan energético cruise"),
                ("power plan normal", "set normal power profile", "activa plan energético normal"),
                ("power on <system_id>", "power on one system", "enciende un sistema"),
                ("power off <system_id>", "power off one system", "apaga un sistema"),
                ("repair <system_id> --selftest", "run self-test repair routine", "ejecuta rutina de autorreparación"),
            ],
        ),
        (
            "Drones",
            "Drones",
            [
                ("drone status [drone_id]", "show drone fleet or one drone status", "muestra estado de la flota o de un dron"),
                ("drone deploy <drone_id> <sector_id>", "deploy drone to sector", "despliega dron a sector"),
                ("drone deploy! <drone_id> <sector_id>", "emergency deploy override", "despliegue de emergencia"),
                ("drone move <drone_id> <target_id>", "move drone to target", "mueve dron a objetivo"),
                ("drone survey <drone_id> [node_id]", "survey salvage signatures at node", "inspecciona señales de salvage en nodo"),
                ("drone autorecall <drone_id> on", "enable automatic recall", "activa autorretorno"),
                ("drone autorecall <drone_id> off", "disable automatic recall", "desactiva autorretorno"),
                ("drone autorecall <drone_id> <percent>", "set recall battery threshold", "ajusta umbral de batería para retorno"),
                ("drone repair <drone_id> <target_id>", "repair target with drone", "repara objetivo con dron"),
                ("drone install <drone_id> <module_id>", "install module (ship/drone by scope)", "instala módulo (nave/dron según scope)"),
                ("drone uninstall <drone_id> <module_id>", "uninstall module (ship/drone by scope)", "desinstala módulo (nave/dron según scope)"),
                ("drone salvage scrap <drone_id> [node_id] <amount>", "salvage scrap from node", "recupera chatarra del nodo"),
                ("drone salvage module <drone_id> [node_id]", "salvage module from node", "recupera módulo del nodo"),
                ("drone salvage drone <drone_id> [node_id]", "recover all drones from node", "recupera todos los drones del nodo"),
                ("drone salvage drones <drone_id> [node_id]", "alias of salvage drone", "alias de salvage drone"),
                ("drone salvage data <drone_id> [node_id]", "salvage data from node", "recupera datos del nodo"),
                ("drone reboot <drone_id>", "reboot drone", "reinicia dron"),
                ("drone recall [<drone_id>|all]", "recall one or all drones to ship", "retorna uno o todos los drones a la nave"),
            ],
        ),
        (
            "Cargo / Modules",
            "Bodega / Módulos",
            [
                ("cargo", "show cargo summary", "muestra resumen de bodega"),
                ("cargo audit", "run cargo audit", "ejecuta auditoría de bodega"),
                ("module inspect <module_id>", "inspect module details", "inspecciona detalles de módulo"),
                ("modules", "list installed/known modules", "lista módulos instalados/conocidos"),
            ],
        ),
        (
            "Hints",
            "Sugerencias",
            [
                ("ls /manuals/commands", "list command manuals", "lista manuales de comandos"),
                ("man navigation", "open navigation manual", "abre manual de navegación"),
                ("cat /mail/inbox/0001.txt", "read inbox file directly", "lee archivo de correo directamente"),
            ],
        ),
        (
            "Debug",
            "Debug",
            [
                ("debug on|off|status", "toggle debug mode", "activa o desactiva modo debug"),
                ("debug galaxy", "show worldgen and galaxy summary", "muestra resumen de galaxia y worldgen"),
                ("debug galaxy map <sector|local|regional|global>", "show debug galaxy map", "muestra mapa galáctico debug"),
                ("debug worldgen sector <sector_id>", "dump one materialized/generated sector", "vuelca un sector materializado/generado"),
                ("debug graph all", "dump full materialized graph", "vuelca el grafo materializado completo"),
            ],
        ),
    ]

    lines = [""]
    for title_en, title_es, entries in sections:
        lines.append(title_es if lang == "es" else title_en)
        for command, desc_en, desc_es in entries:
            if verbose:
                desc = desc_es if lang == "es" else desc_en
                lines.append(f"  {command} - {desc}")
            else:
                lines.append(f"  {command}")
        lines.append("")
    print("\n".join(lines).rstrip())


class SafeDict(dict):
    def __missing__(self, key):
        return "?"


def _inventory_view(ship):
    # Returns manifest view plus dirty flag.
    return ship.manifest_scrap, list(ship.manifest_modules), ship.manifest_dirty


def _orbit_status_label(state, current_loc: str) -> str:
    locale = state.os.locale.value
    labels = {
        "en": {"docked": "docked", "orbit": "in orbit", "adrift": "adrift"},
        "es": {"docked": "acoplado", "orbit": "en órbita", "adrift": "a la deriva"},
    }
    key = state.ship.orbit_status(state.world, current_loc)
    return labels.get(locale, labels["en"]).get(key, key)


def _build_event_payload(e) -> dict:
    payload = {
        "sev": e.severity.value.upper(),
        "type": e.type.value,
        "message": e.message,
        "source_kind": e.source.kind,
        "source_id": e.source.id,
        "t": e.t,
    }
    if isinstance(e.data, dict):
        payload.update(e.data)
        target = e.data.get("target")
        if isinstance(target, dict):
            if "kind" in target:
                payload["target_kind"] = target.get("kind")
            if "id" in target:
                payload["target_id"] = target.get("id")
    if "target_id" in payload and "sector_id" not in payload:
        payload["sector_id"] = payload["target_id"]
    return payload


def _mark_arc_discovered(state, left: str, right: str) -> None:
    for arc in load_arcs():
        primary = arc.get("primary_intel", {})
        line = primary.get("line", "")
        if "->" not in line:
            continue
        try:
            expected_left, expected_right = [p.strip() for p in line.split(":", 1)[1].split("->", 1)]
        except Exception:
            continue
        if left == expected_left and right == expected_right:
            arc_id = arc.get("arc_id", "")
            if not arc_id:
                continue
            arc_state = state.world.arc_placements.setdefault(arc_id, {})
            discovered = arc_state.get("discovered")
            if not isinstance(discovered, set):
                discovered = set(discovered or [])
            discovered.add(primary.get("id", "primary"))
            arc_state["discovered"] = discovered
            primary_state = arc_state.get("primary")
            if not isinstance(primary_state, dict):
                primary_state = {}
            primary_state["unlocked"] = True
            arc_state["primary"] = primary_state


def _primary_link_pair(primary: dict) -> tuple[str, str] | None:
    line = str(primary.get("line", "")).strip()
    if "->" not in line:
        return None
    try:
        left, right = [p.strip() for p in line.split(":", 1)[1].split("->", 1)]
    except Exception:
        return None
    if not left or not right:
        return None
    return left, right


def _primary_target_node_id(primary: dict) -> str | None:
    kind = str(primary.get("kind", "")).strip().lower()
    if kind == "link":
        pair = _primary_link_pair(primary)
        return pair[1] if pair else None
    if kind == "node":
        line = str(primary.get("line", "")).strip()
        if not line:
            return None
        if ":" in line:
            head, payload = line.split(":", 1)
            if head.strip().upper() == "NODE":
                node_id = payload.strip()
                return node_id or None
        return line
    return None


def _locked_primary_targets(state) -> set[str]:
    locked: set[str] = set()
    for arc in load_arcs():
        arc_id = arc.get("arc_id", "")
        if not arc_id:
            continue
        primary = arc.get("primary_intel") or {}
        target = _primary_target_node_id(primary)
        if not target:
            continue
        pid = primary.get("id", "primary")
        arc_state = state.world.arc_placements.get(arc_id) or {}
        discovered = arc_state.get("discovered")
        if not isinstance(discovered, set):
            discovered = set(discovered or [])
        primary_state = arc_state.get("primary")
        if not isinstance(primary_state, dict):
            primary_state = {}
        unlocked = bool(primary_state.get("unlocked")) or pid in discovered
        if not unlocked:
            locked.add(target)
    return locked


def _has_unlock(state, command_key: str) -> bool:
    modules = load_modules()
    for mod_id in state.ship.installed_modules:
        effects = modules.get(mod_id, {}).get("effects", {})
        unlocks = effects.get("unlock_commands", [])
        if command_key in unlocks:
            return True
    return False


def render_events(state, events, origin_override: str | None = None) -> None:
    if not events:
        return
    job_queued_templates = {
        "en": "[{sev}] job_queued :: {job_id} {job_type} target={kind}:{tid} ETA={eta}{emergency}",
        "es": "[{sev}] job_queued :: {job_id} {job_type} objetivo={kind}:{tid} ETA={eta}{emergency}",
    }
    salvage_job_queued_templates = {
        "en": "[{sev}] job_queued :: {job_id} salvage_scrap requested={requested} ETA={eta}",
        "es": "[{sev}] job_queued :: {job_id} salvage_scrap pedido={requested} ETA={eta}",
    }
    system_state_templates = {
        "en": "[{sev}] system_state_changed :: {system_id}: {from_state} -> {to_state} (cause={cause}, health={health})",
        "es": "[{sev}] system_state_changed :: {system_id}: {from_state} -> {to_state} (causa={cause}, salud={health})",
    }
    state_labels = {
        "es": {
            "offline": "fuera_de_linea",
            "critical": "critico",
            "damaged": "danado",
            "limited": "limitado",
            "nominal": "nominal",
            "upgraded": "mejorado",
        }
    }
    cause_labels = {
        "es": {
            "degradation": "degradacion",
            "repair": "reparacion",
            "boot": "arranque",
            "manual_shed": "corte_manual",
            "load_shed": "corte_carga",
            "energy_distribution_offline": "colapso_distribucion",
        }
    }
    job_failed_templates = {
        "en": "[{sev}] job_failed :: {job_id} {job_type} (EMERGENCY)",
        "es": "[{sev}] job_failed :: {job_id} {job_type} (EMERGENCIA)",
    }
    job_completed_templates = {
        "en": "[{sev}] job_completed :: {job_id} {message}",
        "es": "[{sev}] job_completed :: {job_id} {message}",
    }
    boot_blocked_templates = {
        "en": "[{sev}] boot_blocked :: {message}",
        "es": "[{sev}] boot_blocked :: {message}",
    }
    action_warning_templates = {
        "en": "[{sev}] warning :: {message}",
        "es": "[{sev}] advertencia :: {message}",
    }
    signal_detected_templates = {
        "en": "[{sev}] signal_detected :: Signal detected: {contact_id}",
        "es": "[{sev}] signal_detected :: Señal detectada: {contact_id}",
    }
    service_running_templates = {
        "en": "[{sev}] service_already_running :: Service already running: {service}",
        "es": "[{sev}] service_already_running :: Servicio ya en ejecución: {service}",
    }
    docked_templates = {
        "en": "[{sev}] docked :: Docked at {node_id}",
        "es": "[{sev}] docked :: Acoplado en {node_id}",
    }
    undocked_templates = {
        "en": "[{sev}] undocked :: Undocked from {node_id}",
        "es": "[{sev}] undocked :: Desacoplado de {node_id}",
    }
    travel_templates = {
        "travel_started": {
            "en": "[{sev}] travel_started :: To {to} dist={distance_ly:.2f}ly ETA={eta} (hint: nav abort)",
            "es": "[{sev}] travel_started :: A {to} dist={distance_ly:.2f}ly ETA={eta} (pista: nav abort)",
        },
        "arrived": {
            "en": "[{sev}] arrived :: Arrived at {to} (from {from})",
            "es": "[{sev}] arrived :: Llegada a {to} (desde {from})",
        },
        "travel_aborted": {
            "en": "[{sev}] travel_aborted :: Travel aborted",
            "es": "[{sev}] travel_aborted :: Viaje abortado",
        },
        "hibernation_started": {
            "en": "[{sev}] hibernation_started :: Sleeping for {duration}",
            "es": "[{sev}] hibernation_started :: Hibernando durante {duration}",
        },
        "hibernation_ended": {
            "en": "[{sev}] hibernation_ended :: Woke up after {duration}",
            "es": "[{sev}] hibernation_ended :: Despertaste tras {duration}",
        },
    }
    power_alert_templates = {
        "power_net_deficit": {
            "en": "[{sev}] power_net_deficit :: Power deficit detected",
            "es": "[{sev}] power_net_deficit :: Déficit de energía detectado",
        },
        "power_core_degraded": {
            "en": "[{sev}] power_core_degraded :: Power core degraded",
            "es": "[{sev}] power_core_degraded :: Núcleo de energía degradado",
        },
        "power_bus_instability": {
            "en": "[{sev}] power_bus_instability :: Power bus instability",
            "es": "[{sev}] power_bus_instability :: Inestabilidad en el bus de energía",
        },
        "low_power_quality": {
            "en": "[{sev}] low_power_quality :: Low power quality",
            "es": "[{sev}] low_power_quality :: Baja calidad de energía",
        },
        "battery_reserve_exhausted": {
            "en": "[{sev}] battery_reserve_exhausted :: Battery reserve exhausted",
            "es": "[{sev}] battery_reserve_exhausted :: Reserva de batería agotada",
        },
        "drone_bay_charging_unavailable": {
            "en": "[{sev}] drone_bay_charging_unavailable :: Drone bay charging unavailable while energy_distribution remains offline",
            "es": "[{sev}] drone_bay_charging_unavailable :: Recarga en drone_bay no disponible mientras energy_distribution siga offline",
        },
        "drone_bay_maintenance_blocked": {
            "en": (
                "[{sev}] drone_bay_maintenance_blocked :: "
                "Docked drones need maintenance but bay support conditions are not met "
                "(charge_needed={needs_charge_count}, repair_needed={needs_repair_count})"
            ),
            "es": (
                "[{sev}] drone_bay_maintenance_blocked :: "
                "Hay drones acoplados que requieren mantenimiento, pero no se cumplen las condiciones "
                "de soporte de bahía (carga={needs_charge_count}, reparación={needs_repair_count})"
            ),
        },
        "low_soc_warning": {
            "en": "[{sev}] low_soc_warning :: Battery critical. Heavy action may be unsafe (SoC={soc:.2f})",
            "es": "[{sev}] low_soc_warning :: Batería crítica. Acción pesada puede ser insegura (SoC={soc:.2f})",
        },
        "low_soc_notice": {
            "en": "[{sev}] low_soc_notice :: Battery low. Consider reducing load (SoC={soc:.2f})",
            "es": "[{sev}] low_soc_notice :: Batería baja. Considera reducir carga (SoC={soc:.2f})",
        },
    }
    power_restore_templates = {
        "en": "[{sev}] system_power_restored :: Power restored: {system_id} ({from_state} -> {to_state})",
        "es": "[{sev}] system_power_restored :: Energía restaurada: {system_id} ({from_state} -> {to_state})",
    }
    salvage_templates = {
        "salvage_scrap_gained": {
            "en": "[{sev}] salvage_scrap_gained :: +{amount} scrap",
            "es": "[{sev}] salvage_scrap_gained :: +{amount} chatarra",
        },
        "salvage_module_found": {
            "en": "[{sev}] salvage_module_found :: Module found: {module_id}",
            "es": "[{sev}] salvage_module_found :: Módulo encontrado: {module_id}",
        },
        "node_depleted": {
            "en": "[{sev}] node_depleted :: Node depleted",
            "es": "[{sev}] node_depleted :: Nodo agotado",
        },
    }
    def _format_effects(effects: dict) -> str:
        if not effects:
            return ""
        parts = []
        if "p_gen_bonus_kw" in effects:
            parts.append(f"P_gen+{float(effects['p_gen_bonus_kw']):.2f}kW")
        if "e_batt_bonus_kwh" in effects:
            parts.append(f"E_batt_max+{float(effects['e_batt_bonus_kwh']):.2f}kWh")
        if "power_quality_offset" in effects:
            parts.append(f"Q+{float(effects['power_quality_offset']):.2f}")
        return ", ".join(parts)
    boot_blocked_reasons = {
        "service_missing": {
            "en": "Unknown service '{service}'. Available: {available}{suggestion}",
            "es": "Servicio desconocido '{service}'. Disponibles: {available}{suggestion}",
        },
        "deps_unmet": {
            "en": "Boot blocked: {service} requires {dep_target}>={dep_required} (current={dep_current})",
            "es": "Arranque bloqueado: {service} requiere {dep_target}>={dep_required} (actual={dep_current})",
        },
        "drone_bay_deps_unmet": {
            "en": "Drone deploy blocked: drone_bay requires {dep_target}>={dep_required} (current={dep_current}). Use deploy! for emergency override.",
            "es": "Despliegue bloqueado: drone_bay requiere {dep_target}>={dep_required} (actual={dep_current}). Usa deploy! para emergencia.",
        },
        "drone_missing": {
            "en": "Action blocked: drone not found ({drone_id})",
            "es": "Acción bloqueada: dron no encontrado ({drone_id})",
        },
        "drone_not_docked": {
            "en": "Action blocked: drone not docked ({drone_id})",
            "es": "Acción bloqueada: dron no acoplado ({drone_id})",
        },
        "drone_bay_offline": {
            "en": "Action blocked: drone bay offline",
            "es": "Acción bloqueada: bahía de drones fuera de línea",
        },
        "drone_bay_deploy_offline": {
            "en": "Action blocked: drone bay offline; use 'drone deploy!' for emergency launch",
            "es": "Acción bloqueada: drone_bay offline; usa 'drone deploy!' para lanzamiento de emergencia",
        },
        "drone_bay_install_offline": {
            "en": "Action blocked: drone bay offline; module installation requires bay support",
            "es": "Acción bloqueada: drone_bay offline; la instalación de módulos requiere soporte de bahía",
        },
        "drone_not_deployed": {
            "en": "Action blocked: drone not deployed ({drone_id})",
            "es": "Acción bloqueada: dron no desplegado ({drone_id})",
        },
        "drone_not_disabled": {
            "en": "Action blocked: drone not disabled ({drone_id})",
            "es": "Acción bloqueada: dron no deshabilitado ({drone_id})",
        },
        "drone_already_deployed": {
            "en": "Action blocked: drone already deployed ({drone_id})",
            "es": "Acción bloqueada: dron ya desplegado ({drone_id})",
        },
        "drone_disabled": {
            "en": "Action blocked: drone disabled ({drone_id})",
            "es": "Acción bloqueada: dron deshabilitado ({drone_id})",
        },
        "recall_not_docked": {
            "en": "Recall blocked: ship not docked at {node_id}",
            "es": "Recall bloqueado: nave no acoplada en {node_id}",
        },
        "system_missing": {
            "en": "Action blocked: system not found ({system_id})",
            "es": "Acción bloqueada: sistema no encontrado ({system_id})",
        },
        "node_missing": {
            "en": "Action blocked: node not found ({node_id})",
            "es": "Acción bloqueada: nodo no encontrado ({node_id})",
        },
        "ship_sector_missing": {
            "en": "Action blocked: ship sector not found ({sector_id})",
            "es": "Acción bloqueada: sector de nave no encontrado ({sector_id})",
        },
        "deploy_target_hint": {
            "en": "Hint: valid targets are ship_sector IDs (use 'locate <system_id>') or world node IDs (use 'contacts', 'scan' or 'nav').",
            "es": "Pista: los objetivos válidos son ship_sector (usa 'locate <system_id>') o nodos del mundo (usa 'contacts', 'scan' o 'nav').",
        },
        "unknown_contact": {
            "en": "Action blocked: unknown contact ({node_id}). Use 'scan' or acquire navigation intel.",
            "es": "Acción bloqueada: contacto desconocido ({node_id}). Usa 'scan' o consigue inteligencia de navegación.",
        },
        "dock_not_allowed": {
            "en": "Action blocked: docking not allowed at {node_id}",
            "es": "Acción bloqueada: no se puede acoplar en {node_id}",
        },
        "no_route": {
            "en": "Action blocked: no known route to {node_id}. Try: route solve <node_id> (if in range), or acquire intel at other hubs.",
            "es": "Acción bloqueada: no hay ruta conocida a {node_id}. Prueba: route solve <node_id> (si está en rango) o consigue intel en otros hubs.",
        },
        "invalid_amount": {
            "en": "Action blocked: invalid amount",
            "es": "Acción bloqueada: cantidad inválida",
        },
        "not_docked": {
            "en": "Action blocked: not docked at {node_id}",
            "es": "Acción bloqueada: no acoplado en {node_id}",
        },
        "drone_not_at_node": {
            "en": "Action blocked: drone not at {node_id} (current {drone_loc})",
            "es": "Acción bloqueada: dron no está en {node_id} (actual {drone_loc})",
        },
        "sensors_offline": {
            "en": "Action blocked: sensors offline (requires >= limited)",
            "es": "Acción bloqueada: sensores fuera de línea (requiere >= limitado)",
        },
        "sensord_not_running": {
            "en": "Action blocked: sensord not running. Try: boot sensord",
            "es": "Acción bloqueada: sensord no está en ejecución. Prueba: boot sensord",
        },
        "scan_sensors_offline": {
            "en": "Action blocked: sensors offline (requires >= limited)",
            "es": "Acción bloqueada: sensores fuera de línea (requiere >= limitado)",
        },
        "scan_sensord_not_running": {
            "en": "Action blocked: sensord not running. Try: boot sensord",
            "es": "Acción bloqueada: sensord no está en ejecución. Prueba: boot sensord",
        },
        "scan_locked_in_transit": {
            "en": "Action blocked: scan unavailable while adrift",
            "es": "Acción bloqueada: scan no disponible en tránsito",
        },
        "out_of_range": {
            "en": "Action blocked: target out of sensor range ({node_id})",
            "es": "Acción bloqueada: objetivo fuera de rango de sensores ({node_id})",
        },
        "ship_not_docked": {
            "en": "Action blocked: ship not docked at {node_id}",
            "es": "Acción bloqueada: nave no acoplada en {node_id}",
        },
        "ship_docked": {
            "en": "Action blocked: ship is docked at {node_id}. Use 'undock' before starting travel.",
            "es": "Acción bloqueada: la nave está acoplada en {node_id}. Usa 'undock' antes de iniciar el viaje.",
        },
        "scrap_empty": {
            "en": "No scrap available",
            "es": "No hay chatarra disponible",
        },
        "recoverable_drones_empty": {
            "en": "No recoverable drones available",
            "es": "No hay drones recuperables disponibles",
        },
        "emergency_override": {
            "en": "Emergency override: deploying despite unmet dependencies. Risk of failure and drone damage.",
            "es": "Anulación de emergencia: despliegue pese a dependencias. Riesgo de fallo y daño al dron.",
        },
        "module_missing": {
            "en": "Install blocked: module not in inventory ({module_id})",
            "es": "Instalación bloqueada: módulo no disponible ({module_id})",
        },
        "module_unknown": {
            "en": "Module operation blocked: unknown module ({module_id})",
            "es": "Operación de módulo bloqueada: módulo desconocido ({module_id})",
        },
        "module_scope_mismatch": {
            "en": "Module operation blocked: incompatible module scope ({module_id})",
            "es": "Operación de módulo bloqueada: scope de módulo incompatible ({module_id})",
        },
        "module_not_installed": {
            "en": "Module operation blocked: module not installed ({module_id})",
            "es": "Operación de módulo bloqueada: módulo no instalado ({module_id})",
        },
        "module_slots_full": {
            "en": "Install blocked: no free drone module slots ({slots_used}/{slots_max})",
            "es": "Instalación bloqueada: sin slots libres de módulos de dron ({slots_used}/{slots_max})",
        },
        "drone_not_in_bay": {
            "en": "Module operation blocked: target drone is not docked in drone_bay ({drone_id})",
            "es": "Operación de módulo bloqueada: el dron objetivo no está acoplado en drone_bay ({drone_id})",
        },
        "drone_bay_not_nominal": {
            "en": "Module operation blocked: drone_bay must be NOMINAL",
            "es": "Operación de módulo bloqueada: drone_bay debe estar en NOMINAL",
        },
        "drone_module_not_installed": {
            "en": "Uninstall blocked: module not installed on target drone ({module_id})",
            "es": "Desinstalación bloqueada: módulo no instalado en el dron objetivo ({module_id})",
        },
        "scrap_insufficient": {
            "en": "Install blocked: insufficient scrap ({scrap_cost})",
            "es": "Instalación bloqueada: chatarra insuficiente ({scrap_cost})",
        },
        "scrap_insufficient_repair": {
            "en": "Repair blocked: insufficient scrap ({scrap_cost})",
            "es": "Reparación bloqueada: chatarra insuficiente ({scrap_cost})",
        },
        "selftest_not_available": {
            "en": "Repair blocked: self-test rig not installed",
            "es": "Reparación bloqueada: Self-Test Rig no instalado",
        },
        "drone_too_damaged": {
            "en": "Recall blocked: drone integrity too low ({integrity:.2f})",
            "es": "Recall bloqueado: integridad de dron demasiado baja ({integrity:.2f})",
        },
        "drone_low_battery": {
            "en": "Action blocked: drone battery too low ({battery:.2f} < {threshold:.2f})",
            "es": "Acción bloqueada: batería de dron demasiado baja ({battery:.2f} < {threshold:.2f})",
        },
        "drone_target_not_co_located": {
            "en": "Repair blocked: target drone not at operator location ({drone_id})",
            "es": "Reparación bloqueada: dron objetivo fuera de la ubicación del operador ({drone_id})",
        },
        "invalid_target": {
            "en": "Action blocked: invalid target",
            "es": "Acción bloqueada: objetivo inválido",
        },
        "already_nominal": {
            "en": "Action skipped: target already nominal",
            "es": "Acción omitida: objetivo ya está nominal",
        },
        "system_too_damaged": {
            "en": "System on blocked: system too damaged",
            "es": "System on bloqueado: sistema demasiado dañado",
        },
        "in_transit": {
            "en": "Action blocked: ship in transit. Use 'hibernate until_arrival' to advance.",
            "es": "Acción bloqueada: nave en tránsito. Usa 'hibernate until_arrival' para avanzar.",
        },
        "power_quality_low": {
            "en": "Action blocked: power quality too low (Q={q:.2f}, requires >= {required:.2f})",
            "es": "Acción bloqueada: calidad de energía demasiado baja (Q={q:.2f}, requiere >= {required:.2f})",
        },
        "power_quality_critical": {
            "en": "Action blocked: power quality critical (Q={q:.2f}, requires >= {required:.2f})",
            "es": "Acción bloqueada: calidad de energía crítica (Q={q:.2f}, requiere >= {required:.2f})",
        },
        "power_quality_collapse": {
            "en": "Action blocked: power quality collapse (Q={q:.2f}, requires >= {required:.2f})",
            "es": "Acción bloqueada: colapso de calidad de energía (Q={q:.2f}, requiere >= {required:.2f})",
        },
        "critical_power_state": {
            "en": "Action blocked: non-essential operations disabled during critical power state",
            "es": "Acción bloqueada: operaciones no esenciales deshabilitadas durante estado crítico de energía",
        },
        "brownout_active": {
            "en": "Action blocked: brownout active",
            "es": "Acción bloqueada: brownout activo",
        },
        "terminal_state": {
            "en": "Action blocked: terminal state active",
            "es": "Acción bloqueada: estado terminal activo",
        },
        "already_at_target": {
            "en": "Action blocked: already at destination ({node_id})",
            "es": "Acción bloqueada: ya estás en destino ({node_id})",
        },
        "not_in_transit": {
            "en": "Action blocked: not in transit",
            "es": "Acción bloqueada: no estás en tránsito",
        },
        "not_at_node": {
            "en": "Action blocked: not in {node_id} orbit",
            "es": "Acción bloqueada: no en órbita de {node_id}",
        },
        "route_known": {
            "en": "Route already known to {node_id}.",
            "es": "Ruta ya conocida hacia {node_id}.",
        },
        "job_missing": {
            "en": "Job not found: {job_id}",
            "es": "Trabajo no encontrado: {job_id}",
        },
        "job_not_active": {
            "en": "Job not active: {job_id}",
            "es": "Trabajo no activo: {job_id}",
        },
    }
    job_completed_keys = {
        "job_completed_repair": {
            "en": "Repair completed for {system_id}",
            "es": "Reparación completada en {system_id}",
        },
        "job_completed_drone_repair": {
            "en": "Drone repair completed for {drone_id}",
            "es": "Reparación de dron completada en {drone_id}",
        },
        "job_completed_boot": {
            "en": "Service booted: {service}",
            "es": "Servicio iniciado: {service}",
        },
        "job_completed_deploy": {
            "en": "Drone deployed to {sector_id}",
            "es": "Dron desplegado en {sector_id}",
        },
        "job_completed_reboot": {
            "en": "Drone rebooted: {drone_id}",
            "es": "Dron reiniciado: {drone_id}",
        },
        "job_completed_recall": {
            "en": "Drone recalled: {drone_id}",
            "es": "Dron recuperado: {drone_id}",
        },
        "job_failed_recall": {
            "en": "Drone recall failed: {drone_id}",
            "es": "Fallo en recuperación de dron: {drone_id}",
        },
        "job_failed_dock_interrupted": {
            "en": "Dock interrupted at {node_id}",
            "es": "Dock interrumpido en {node_id}",
        },
        "job_failed_undock_interrupted": {
            "en": "Undock interrupted at {node_id}",
            "es": "Undock interrumpido en {node_id}",
        },
        "job_failed_route_sensors_unavailable": {
            "en": "Route solve interrupted: sensors unavailable for {node_id}",
            "es": "Route solve interrumpido: sensores no disponibles para {node_id}",
        },
        "job_failed_route_sensord_stopped": {
            "en": "Route solve interrupted: sensord stopped for {node_id}",
            "es": "Route solve interrumpido: sensord detenido para {node_id}",
        },
        "job_failed_scan_sensors_unavailable": {
            "en": "Scan interrupted: sensors unavailable for {node_id}",
            "es": "Scan interrumpido: sensores no disponibles para {node_id}",
        },
        "job_failed_scan_sensord_stopped": {
            "en": "Scan interrupted: sensord stopped for {node_id}",
            "es": "Scan interrumpido: sensord detenido para {node_id}",
        },
        "job_failed_scan_locked_in_transit": {
            "en": "Scan interrupted: scan unavailable while adrift",
            "es": "Scan interrumpido: scan no disponible en tránsito",
        },
        "job_failed_scan_context_changed": {
            "en": "Scan interrupted: location changed during scan ({node_id})",
            "es": "Scan interrumpido: la ubicación cambió durante el scan ({node_id})",
        },
        "job_failed_repair_attempt": {
            "en": (
                "Repair failed for {target_id}. "
                "Consumed {scrap_consumed}/{scrap_required} scrap (refund: {scrap_refunded})"
            ),
            "es": (
                "Reparación fallida en {target_id}. "
                "Se consumió {scrap_consumed}/{scrap_required} chatarra (reembolso: {scrap_refunded})"
            ),
        },
        "job_completed_salvage": {
            "en": "Salvage complete: +{amount} {kind} from {node_id}",
            "es": "Recuperación completa: +{amount} {kind} de {node_id}",
        },
        "job_completed_install": {
            "en": "Module installed: {module_id}",
            "es": "Módulo instalado: {module_id}",
        },
        "job_completed_uninstall": {
            "en": "Module uninstalled: {module_id}",
            "es": "Módulo desinstalado: {module_id}",
        },
        "job_completed_drone_install": {
            "en": "Drone module installed: {module_id} -> {drone_id}",
            "es": "Módulo de dron instalado: {module_id} -> {drone_id}",
        },
        "job_completed_drone_uninstall": {
            "en": "Drone module uninstalled: {module_id} <- {drone_id}",
            "es": "Módulo de dron desinstalado: {module_id} <- {drone_id}",
        },
        "job_failed_drone_install": {
            "en": "Drone module install failed: {module_id} -> {drone_id}",
            "es": "Falló la instalación de módulo de dron: {module_id} -> {drone_id}",
        },
        "job_failed_drone_uninstall": {
            "en": "Drone module uninstall failed: {module_id} <- {drone_id}",
            "es": "Falló la desinstalación de módulo de dron: {module_id} <- {drone_id}",
        },
        "job_completed_cargo_audit": {
            "en": "Cargo manifest updated",
            "es": "Manifiesto de bodega actualizado",
        },
        "job_completed_route": {
            "en": "Route solved: {from_id} -> {node_id}",
            "es": "Ruta calculada: {from_id} -> {node_id}",
        },
        "job_completed_scan": {
            "en": "Scan completed at {node_id}",
            "es": "Scan completado en {node_id}",
        },
        "job_completed_drone_survey": {
            "en": "Survey completed at {node_id}",
            "es": "Survey completado en {node_id}",
        },
        "job_completed_drone_salvage": {
            "en": "Drone salvage complete at {node_id}: recovered {recovered_count} drone(s) [{recovered_ids}]",
            "es": "Salvage de drones completado en {node_id}: recuperados {recovered_count} dron(es) [{recovered_ids}]",
        },
        "route_refined": {
            "en": "Route refined: fine range fixed for {node_id}",
            "es": "Ruta afinada: distancia fina fijada para {node_id}",
        },
        "job_cancelled": {
            "en": "Job cancelled: {job_id}",
            "es": "Trabajo cancelado: {job_id}",
        },
    }
    def _safe_format(tmpl: str, payload: dict) -> str:
        return tmpl.format_map(SafeDict(payload))
    for item in events:
        if isinstance(item, tuple) and len(item) == 2:
            origin, e = item
        else:
            origin, e = "cmd", item
        if origin_override:
            origin_tag = origin_override
        else:
            if origin == "auto":
                origin_tag = "AUTO"
            elif origin == "step":
                origin_tag = "STEP"
            else:
                origin_tag = "CMD"
        sev = e.severity.value.upper()
        payload = _build_event_payload(e)
        if e.type == EventType.JOB_QUEUED:
            job_id = e.data.get("job_id", "?")
            job_type = e.data.get("job_type", "?")
            target = e.data.get("target", {})
            eta_s = e.data.get("eta_s", "?")
            emergency = " (EMERGENCY)" if e.data.get("emergency") else ""
            kind = target.get("kind", "?")
            tid = target.get("id", "?")
            locale = state.os.locale.value
            if job_type == "salvage_scrap" and "requested" in e.data:
                tmpl = salvage_job_queued_templates.get(locale, salvage_job_queued_templates["en"])
            else:
                tmpl = job_queued_templates.get(locale, job_queued_templates["en"])
            eta_val = eta_s
            if isinstance(eta_s, (int, float)) or (isinstance(eta_s, str) and eta_s.replace(".", "", 1).isdigit()):
                try:
                    eta_val = _format_eta_short(float(eta_s), locale)
                except Exception:
                    eta_val = eta_s
            payload.update({
                "job_id": job_id,
                "job_type": job_type,
                "kind": kind,
                "tid": tid,
                "eta": eta_val,
                "emergency": emergency,
                "requested": e.data.get("requested", "?"),
            })
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.DATA_SALVAGED:
            print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message}")
            mounted_paths_new = e.data.get("mounted_paths_new") if isinstance(e.data, dict) else None
            mounted_paths_existing = e.data.get("mounted_paths_existing") if isinstance(e.data, dict) else None
            if isinstance(mounted_paths_new, list) and mounted_paths_new:
                locale = state.os.locale.value
                title = {
                    "en": "Recovered documents:",
                    "es": "Documentos recuperados:",
                }.get(locale, "Recovered documents:")
                print(title)
                for path in mounted_paths_new:
                    print(f"- {path}")
            if isinstance(mounted_paths_existing, list) and mounted_paths_existing:
                locale = state.os.locale.value
                title = {
                    "en": "Already mounted documents:",
                    "es": "Documentos ya montados:",
                }.get(locale, "Already mounted documents:")
                print(title)
                for path in mounted_paths_existing:
                    print(f"- {path}")
            tip = None
            if isinstance(e.data, dict):
                tip_key = e.data.get("tip_key")
                if tip_key == "data_salvaged_cat":
                    locale = state.os.locale.value
                    tip = {
                        "en": "Tip: use 'cat <path>' to read recovered files and auto-import their intel.",
                        "es": "Pista: usa 'cat <path>' para leer los archivos recuperados e importar su intel automáticamente.",
                    }.get(locale)
                else:
                    tip = e.data.get("tip")
            if tip:
                locale = state.os.locale.value
                if locale == "es" and tip.startswith("Tip:"):
                    tip = tip.replace("Tip:", "Pista:", 1)
                print(tip)
            continue
        if e.type == EventType.SYSTEM_STATE_CHANGED and e.data.get("from") and e.data.get("to"):
            system_id = e.source.id if e.source.kind == "ship_system" else "system"
            cause = e.data.get("cause", "")
            health = e.data.get("health", None)
            health_text = f"{health:.2f}" if isinstance(health, (int, float)) else "n/a"
            locale = state.os.locale.value
            from_state = e.data["from"]
            to_state = e.data["to"]
            if locale in state_labels:
                from_state = state_labels[locale].get(from_state, from_state)
                to_state = state_labels[locale].get(to_state, to_state)
            if locale in cause_labels and cause:
                cause = cause_labels[locale].get(cause, cause)
            tmpl = system_state_templates.get(locale, system_state_templates["en"])
            payload.update({
                "system_id": system_id,
                "from_state": from_state,
                "to_state": to_state,
                "cause": cause or "?",
                "health": health_text,
            })
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.SERVICE_ALREADY_RUNNING:
            locale = state.os.locale.value
            tmpl = service_running_templates.get(locale, service_running_templates["en"])
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.JOB_FAILED and e.data.get("job_id"):
            locale = state.os.locale.value
            key = e.data.get("message_key", "")
            if key in job_completed_keys:
                tmpl = job_completed_keys[key].get(locale, job_completed_keys[key]["en"])
                message = _safe_format(tmpl, payload)
            else:
                tmpl = job_failed_templates.get(locale, job_failed_templates["en"])
                payload.update({
                    "job_id": e.data.get("job_id", "?"),
                    "job_type": e.data.get("job_type", "?"),
                })
                message = None
            try:
                if message is not None:
                    payload.update({
                        "job_id": e.data.get("job_id", "?"),
                        "message": message,
                    })
                    tmpl_ok = job_completed_templates.get(locale, job_completed_templates["en"])
                    print(f"[{origin_tag}] " + _safe_format(tmpl_ok, payload))
                else:
                    print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.JOB_COMPLETED and e.data.get("job_id"):
            locale = state.os.locale.value
            key = e.data.get("message_key", "")
            if key == "job_completed_drone_salvage":
                ids = e.data.get("recovered_ids", [])
                if isinstance(ids, list) and ids:
                    payload["recovered_ids"] = ", ".join(str(x) for x in ids)
                else:
                    payload["recovered_ids"] = "-"
            if key in job_completed_keys:
                tmpl = job_completed_keys[key].get(locale, job_completed_keys[key]["en"])
                message = _safe_format(tmpl, payload)
            else:
                tmpl = job_completed_templates.get(locale, job_completed_templates["en"])
                message = e.message
            payload.update({
                "job_id": e.data.get("job_id", "?"),
                "message": message,
            })
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            if key == "job_completed_scan":
                seen_ids = [str(item) for item in (e.data.get("seen_ids") or [])]
                new_ids = [str(item) for item in (e.data.get("new_ids") or [])]
                fine_updates = e.data.get("fine_range_updates") or []
                render_scan_results(state, seen_ids)
                for update in fine_updates:
                    if not isinstance(update, dict):
                        continue
                    node_id = str(update.get("node_id", "?"))
                    fine_km = float(update.get("distance_km", 0.0) or 0.0)
                    if locale == "en":
                        dist_txt = f"{_format_large_distance(fine_km * 0.621371)}mi"
                        print(f"[INFO] (scan) fine range fixed: {node_id} ({dist_txt})")
                    else:
                        dist_txt = f"{_format_large_distance(fine_km)}km"
                        print(f"[INFO] (scan) distancia fina fijada: {node_id} ({dist_txt})")
                if new_ids:
                    print(f"(scan) new: {', '.join(sorted(new_ids))}")
            if key == "job_completed_drone_survey":
                scrap = int(e.data.get("scrap_available", 0) or 0)
                modules_detected = bool(e.data.get("modules_detected", False))
                recoverable_drones = int(e.data.get("recoverable_drones_count", 0) or 0)
                data_signatures = bool(e.data.get("data_signatures_detected", False))
                scrap_complete = bool(e.data.get("scrap_complete", False))
                data_complete = bool(e.data.get("data_complete", False))
                extras_complete = bool(e.data.get("extras_complete", False))
                node_cleaned = bool(e.data.get("node_cleaned", False))
                uplink_detected = bool(e.data.get("uplink_detected", False))
                if locale == "es":
                    print("=== SURVEY ===")
                    print(f"chatarra detectable: {scrap}")
                    print("módulos detectados" if modules_detected else "sin módulos detectados")
                    if recoverable_drones > 0:
                        print(f"drones recuperables detectados: {recoverable_drones}")
                    else:
                        print("sin drones recuperables detectados")
                    print(
                        "posibles firmas de datos recuperables detectadas"
                        if data_signatures
                        else "sin firmas de datos recuperables"
                    )
                    print(
                        "infraestructura con capacidad uplink detectada"
                        if uplink_detected
                        else "sin infraestructura con capacidad uplink"
                    )
                    print(
                        f"agotamiento: chatarra={'sí' if scrap_complete else 'no'}, "
                        f"datos={'sí' if data_complete else 'no'}, "
                        f"extras={'sí' if extras_complete else 'no'}"
                    )
                    print("nodo limpio" if node_cleaned else "nodo no limpio")
                else:
                    print("=== SURVEY ===")
                    print(f"scrap detected: {scrap}")
                    print("modules detected" if modules_detected else "no modules detected")
                    if recoverable_drones > 0:
                        print(f"recoverable drones detected: {recoverable_drones}")
                    else:
                        print("no recoverable drones detected")
                    print(
                        "possible recoverable data signatures detected"
                        if data_signatures
                        else "no recoverable data signatures detected"
                    )
                    print(
                        "uplink-capable infrastructure detected"
                        if uplink_detected
                        else "no uplink-capable infrastructure detected"
                    )
                    print(
                        f"depletion: scrap={'yes' if scrap_complete else 'no'}, "
                        f"data={'yes' if data_complete else 'no'}, "
                        f"extras={'yes' if extras_complete else 'no'}"
                    )
                    print("node cleaned" if node_cleaned else "node not cleaned")
            continue
        if e.type == EventType.BOOT_BLOCKED:
            locale = state.os.locale.value
            reason = e.data.get("reason", "")
            if reason in boot_blocked_reasons:
                msg_tmpl = boot_blocked_reasons[reason].get(locale, boot_blocked_reasons[reason]["en"])
                suggestion = e.data.get("suggestion", "")
                if suggestion:
                    if locale == "es":
                        payload["suggestion"] = f" ¿Quisiste decir '{suggestion}'?"
                    else:
                        payload["suggestion"] = f" Did you mean '{suggestion}'?"
                else:
                    payload["suggestion"] = ""
                message = _safe_format(msg_tmpl, payload)
            else:
                message = e.message
            tmpl = boot_blocked_templates.get(locale, boot_blocked_templates["en"])
            payload.update({"message": message})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            if reason == "out_of_range":
                target_id = str(e.data.get("node_id", "") or "").strip()
                if target_id:
                    for line in _route_solve_origin_hint_lines(state, target_id):
                        print(line)
            hint_key = e.data.get("hint_key", "")
            if hint_key and hint_key in boot_blocked_reasons:
                hint = boot_blocked_reasons[hint_key].get(locale, boot_blocked_reasons[hint_key]["en"])
                print(f"[{origin_tag}] {hint}")
            continue
        if e.type == EventType.ACTION_WARNING:
            locale = state.os.locale.value
            if e.data.get("message_key") == "radiation_level_changed":
                level_labels = {
                    "en": {
                        "low": "low",
                        "elevated": "elevated",
                        "high": "high",
                        "extreme": "extreme",
                    },
                    "es": {
                        "low": "bajo",
                        "elevated": "elevado",
                        "high": "alto",
                        "extreme": "extremo",
                    },
                }
                metric_labels = {
                    "en": {
                        "env": "ambient radiation",
                        "internal": "internal radiation",
                        "drone_dose": "drone dose",
                    },
                    "es": {
                        "env": "radiación ambiental",
                        "internal": "radiación interna",
                        "drone_dose": "dosis de dron",
                    },
                }
                templates = {
                    "en": "[{sev}] radiation :: {target} {metric}: {from_level} -> {to_level} ({value_txt})",
                    "es": "[{sev}] radiación :: {target} {metric}: {from_level} -> {to_level} ({value_txt})",
                }
                metric = e.data.get("metric", "")
                value = max(0.0, float(e.data.get("value", 0.0) or 0.0))
                if metric in {"env", "internal"}:
                    value_txt = f"{value:.4f}rad/s"
                else:
                    value_txt = f"{value:.3f}"
                level_map = level_labels.get(locale, level_labels["en"])
                metric_map = metric_labels.get(locale, metric_labels["en"])
                from_level = level_map.get(e.data.get("from_level", ""), e.data.get("from_level", "?"))
                to_level = level_map.get(e.data.get("to_level", ""), e.data.get("to_level", "?"))
                target_kind = e.data.get("target_kind", "")
                target_id = e.data.get("target_id", "?")
                if target_kind == "drone":
                    target = target_id
                else:
                    target = "ship" if locale == "en" else "nave"
                payload.update(
                    {
                        "target": target,
                        "metric": metric_map.get(metric, metric),
                        "from_level": from_level,
                        "to_level": to_level,
                        "value_txt": value_txt,
                    }
                )
                tmpl = templates.get(locale, templates["en"])
                try:
                    print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
                except Exception:
                    print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
                continue
            tmpl = action_warning_templates.get(locale, action_warning_templates["en"])
            payload.update({"message": e.message})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.SIGNAL_DETECTED:
            locale = state.os.locale.value
            tmpl = signal_detected_templates.get(locale, signal_detected_templates["en"])
            payload.update({"contact_id": e.data.get("contact_id", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.DOCKED:
            locale = state.os.locale.value
            tmpl = docked_templates.get(locale, docked_templates["en"])
            payload.update({"node_id": e.data.get("node_id", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.UNDOCKED:
            locale = state.os.locale.value
            tmpl = undocked_templates.get(locale, undocked_templates["en"])
            payload.update({"node_id": e.data.get("node_id", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type in {EventType.TRAVEL_STARTED, EventType.TRAVEL_ABORTED, EventType.ARRIVED, EventType.HIBERNATION_STARTED, EventType.HIBERNATION_ENDED}:
            locale = state.os.locale.value
            key = e.type.value
            tmpl = travel_templates.get(key, {}).get(locale)
            payload.update({
                "to": e.data.get("to", "?"),
                "from": e.data.get("from", "?"),
                "distance_ly": e.data.get("distance_ly", 0.0),
                "eta_years": e.data.get("eta_years", 0.0),
                "eta": _format_eta_short((e.data.get("eta_years", 0.0) or 0.0) * Balance.YEAR_S, locale),
                "years": e.data.get("years", 0.0),
                "duration": _format_eta_short((e.data.get("years", 0.0) or 0.0) * Balance.YEAR_S, locale),
            })
            if e.type == EventType.TRAVEL_STARTED and e.data.get("local"):
                km = e.data.get("distance_km") or 0.0
                eta_s = e.data.get("eta_s") or 0.0
                if locale == "en":
                    dist_txt = f"{_format_large_distance(km * 0.621371)}mi"
                else:
                    dist_txt = f"{_format_large_distance(km)}km"
                eta_h = eta_s / 3600.0
                msg = {
                    "en": f"[{{sev}}] travel_started :: To {{to}} dist={dist_txt} ETA={_format_eta_short(eta_s, 'en')} (hint: nav abort)",
                    "es": f"[{{sev}}] travel_started :: A {{to}} dist={dist_txt} ETA={_format_eta_short(eta_s, 'es')} (pista: nav abort)",
                }
                tmpl_local = msg.get(locale, msg["en"])
                try:
                    print(f"[{origin_tag}] " + _safe_format(tmpl_local, payload))
                except Exception:
                    print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
                continue
            if tmpl:
                try:
                    print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
                except Exception:
                    print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            else:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message}")
            continue
        if e.type == EventType.TRAVEL_PROFILE_SET:
            locale = state.os.locale.value
            key = e.data.get("message_key", "")
            templates = {
                "travel_profile_auto": {
                    "en": "[{sev}] travel_profile_set :: Travel profile set: CRUISE (auto). Use 'nav --no-cruise <node_id>' to override.",
                    "es": "[{sev}] travel_profile_set :: Perfil de viaje: CRUISE (auto). Usa 'nav --no-cruise <node_id>' para anular.",
                },
                "travel_profile_manual": {
                    "en": "[{sev}] travel_profile_set :: Travel override: CRUISE disabled. Increased wear expected.",
                    "es": "[{sev}] travel_profile_set :: Anulación de viaje: CRUISE desactivado. Se espera mayor desgaste.",
                },
            }
            tmpl = templates.get(key, {}).get(locale)
            if tmpl:
                try:
                    print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
                except Exception:
                    print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            else:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message}")
            continue
        if e.type == EventType.DRONE_DISABLED:
            locale = state.os.locale.value
            tmpl = {
                "en": "[{sev}] drone_disabled :: Drone disabled: {drone_id}",
                "es": "[{sev}] drone_disabled :: Dron deshabilitado: {drone_id}",
            }.get(locale, "[{sev}] drone_disabled :: Drone disabled: {drone_id}")
            payload.update({"drone_id": e.data.get("drone_id", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.MODULE_INSTALLED:
            locale = state.os.locale.value
            modules = load_modules()
            mod = modules.get(e.data.get("module_id", ""), {})
            desc = mod.get("desc_es") if locale == "es" else mod.get("desc_en")
            effects = e.data.get("effects") or mod.get("effects", {})
            scrap_cost = mod.get("scrap_cost")
            effects_text = _format_effects(effects)
            if desc:
                if effects_text:
                    extra = f" — {desc} | effects: {effects_text}"
                else:
                    extra = f" — {desc}"
            else:
                extra = f" | effects: {effects_text}" if effects_text else ""
            if scrap_cost is not None:
                extra = f"{extra} | installation cost: {scrap_cost} scrap"
            tmpl = {
                "en": "[{sev}] module_installed :: Module installed: {module_id}{extra}",
                "es": "[{sev}] module_installed :: Módulo instalado: {module_id}{extra}",
            }.get(locale, "[{sev}] module_installed :: Module installed: {module_id}{extra}")
            payload.update({"module_id": e.data.get("module_id", "?")})
            payload.update({"extra": extra})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.SYSTEM_POWER_RESTORED:
            locale = state.os.locale.value
            tmpl = power_restore_templates.get(locale, power_restore_templates["en"])
            system_id = e.source.id if e.source.kind == "ship_system" else "system"
            from_state = e.data.get("from", "offline")
            to_state = e.data.get("to", "?")
            payload.update({"system_id": system_id, "from_state": from_state, "to_state": to_state})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.SALVAGE_SCRAP_GAINED:
            locale = state.os.locale.value
            tmpl = salvage_templates["salvage_scrap_gained"].get(
                locale, salvage_templates["salvage_scrap_gained"]["en"]
            )
            payload.update({"amount": e.data.get("amount", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.SALVAGE_MODULE_FOUND:
            locale = state.os.locale.value
            tmpl = salvage_templates["salvage_module_found"].get(
                locale, salvage_templates["salvage_module_found"]["en"]
            )
            payload.update({"module_id": e.data.get("module_id", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.DRONE_DAMAGED:
            locale = state.os.locale.value
            tmpl = {
                "en": "[{sev}] drone_damaged :: Drone damaged: {drone_id}",
                "es": "[{sev}] drone_damaged :: Dron dañado: {drone_id}",
            }.get(locale, "[{sev}] drone_damaged :: Drone damaged: {drone_id}")
            payload.update({"drone_id": e.data.get("drone_id", "?")})
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.DRONE_LOW_BATTERY:
            locale = state.os.locale.value
            tmpl = {
                "en": "[{sev}] drone_low_battery :: Low battery: {drone_id} ({battery:.2f})",
                "es": "[{sev}] drone_low_battery :: Batería baja: {drone_id} ({battery:.2f})",
            }.get(locale, "[{sev}] drone_low_battery :: Low battery: {drone_id} ({battery:.2f})")
            payload.update(
                {
                    "drone_id": e.data.get("drone_id", "?"),
                    "battery": e.data.get("battery", 0.0),
                }
            )
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.NODE_DEPLETED:
            locale = state.os.locale.value
            tmpl = salvage_templates["node_depleted"].get(locale, salvage_templates["node_depleted"]["en"])
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type in {
            EventType.POWER_NET_DEFICIT,
            EventType.POWER_CORE_DEGRADED,
            EventType.POWER_BUS_INSTABILITY,
            EventType.LOW_POWER_QUALITY,
            EventType.LOW_SOC_WARNING,
            EventType.LOW_SOC_NOTICE,
            EventType.DRONE_BAY_CHARGING_UNAVAILABLE,
            EventType.DRONE_BAY_MAINTENANCE_BLOCKED,
        }:
            locale = state.os.locale.value
            tmpl = power_alert_templates.get(e.type.value, {}).get(locale)
            if tmpl:
                try:
                    print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
                except Exception:
                    print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
                continue
        print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message}")


def _compute_internal_radiation_for_status(hull_integrity: float, env_rad: float) -> float:
    hull = max(0.0, min(1.0, hull_integrity))
    ingress = (
        Balance.HULL_INTERNAL_RAD_MIN_INGRESS
        + (1.0 - hull) * (Balance.HULL_INTERNAL_RAD_MAX_INGRESS - Balance.HULL_INTERNAL_RAD_MIN_INGRESS)
    )
    ingress = max(
        Balance.HULL_INTERNAL_RAD_MIN_INGRESS,
        min(Balance.HULL_INTERNAL_RAD_MAX_INGRESS, ingress),
    )
    return max(0.0, env_rad) * ingress


def _radiation_level_id(value: float, elevated: float, high: float, extreme: float) -> str:
    v = max(0.0, float(value))
    if v >= extreme:
        return "extreme"
    if v >= high:
        return "high"
    if v >= elevated:
        return "elevated"
    return "low"


def _radiation_level_label(locale: str, level: str) -> str:
    labels = {
        "en": {
            "low": "low",
            "elevated": "elevated",
            "high": "high",
            "extreme": "extreme",
        },
        "es": {
            "low": "bajo",
            "elevated": "elevado",
            "high": "alto",
            "extreme": "extremo",
        },
    }
    return labels.get(locale, labels["en"]).get(level, level)


def render_status(state) -> None:
    ship = state.ship
    p = ship.power
    locale = state.os.locale.value
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    net = p.p_gen_kw - p.p_load_kw
    deficit = max(0.0, p.p_load_kw - p.p_gen_kw)
    headroom = p.p_discharge_max_kw - deficit
    print("\n=== STATUS ===")
    print(f"time: {format_elapsed_long(state.clock.t)}")
    if ship.op_mode == "CRUISE":
        source = ship.op_mode_source or "manual"
        print(f"ship_mode: {ship.op_mode} ({source})")
    else:
        print(f"ship_mode: {ship.op_mode}")
    current_loc = state.world.current_node_id
    node = state.world.space.nodes.get(current_loc)
    node_name = node.name if node else current_loc
    if ship.in_transit:
        remaining_s = max(0.0, ship.arrival_t - state.clock.t)
        total_s = max(0.0, ship.arrival_t - ship.transit_start_t)
        if getattr(ship, "last_travel_is_local", False):
            locale = state.os.locale.value
            dist_total_km = getattr(ship, "last_travel_distance_km", 0.0) or 0.0
            if total_s > 0:
                remaining_km = dist_total_km * (remaining_s / total_s)
            else:
                remaining_km = dist_total_km
            if locale == "en":
                dist_total = dist_total_km * 0.621371
                remaining = remaining_km * 0.621371
                unit = "mi"
            else:
                dist_total = dist_total_km
                remaining = remaining_km
                unit = "km"
            remaining_hours = remaining_s / 3600.0
            print(
                f"location: en route to {ship.transit_to} (from {ship.transit_from}) "
                f"ETA={_format_eta_short(remaining_s, locale)}"
            )
            print(
                f"transit: {ship.transit_from} -> {ship.transit_to}  "
                f"dist_total={dist_total:.0f}{unit}  remaining={remaining:.0f}{unit}  "
                f"ETA={_format_eta_short(remaining_s, locale)}"
            )
        else:
            remaining_years = remaining_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
            remaining_days = remaining_s / Balance.DAY_S if Balance.DAY_S else 0.0
            print(
                f"location: en route to {ship.transit_to} (from {ship.transit_from}) "
                f"ETA={_format_eta_short(remaining_s, locale)}"
            )
            dist_total = getattr(ship, "last_travel_distance_ly", 0.0) or 0.0
            if total_s > 0:
                remaining_ly = dist_total * (remaining_s / total_s)
            else:
                remaining_ly = dist_total
            print(
                f"transit: {ship.transit_from} -> {ship.transit_to}  "
                f"dist_total={dist_total:.2f}ly  remaining={remaining_ly:.2f}ly  "
                f"ETA={_format_eta_short(remaining_s, locale)}"
            )
    else:
        status_label = _orbit_status_label(state, current_loc)
        print(f"location: {current_loc} ({node_name}) [{status_label}]")
        if state.world.active_tmp_node_id == current_loc:
            tmp_from = state.world.active_tmp_from or "?"
            tmp_to = state.world.active_tmp_to or "?"
            progress = state.world.active_tmp_progress
            locale = state.os.locale.value
            if isinstance(progress, (int, float)):
                pct = int(progress * 100)
                msg = {
                    "en": f"transit: between {tmp_from} and {tmp_to} (aborted, {pct}%)",
                    "es": f"transit: entre {tmp_from} y {tmp_to} (abortado, {pct}%)",
                }
                print(msg.get(locale, msg["en"]))
            else:
                msg = {
                    "en": f"transit: between {tmp_from} and {tmp_to} (aborted)",
                    "es": f"transit: entre {tmp_from} y {tmp_to} (abortado)",
                }
                print(msg.get(locale, msg["en"]))
    print(
        f"power: P_gen={p.p_gen_kw:.2f}kW  P_load={p.p_load_kw:.2f}kW  net={net:+.2f}kW "
        f"headroom={headroom:.2f}kW  SoC={soc:.2f}  Q={p.power_quality:.2f}  brownout={p.brownout}"
    )
    env_rad = max(0.0, float(ship.radiation_env_rad_per_s))
    internal_rad = _compute_internal_radiation_for_status(ship.hull_integrity, env_rad)
    env_level = _radiation_level_id(
        env_rad,
        Balance.RAD_LEVEL_ENV_ELEVATED,
        Balance.RAD_LEVEL_ENV_HIGH,
        Balance.RAD_LEVEL_ENV_EXTREME,
    )
    internal_level = _radiation_level_id(
        internal_rad,
        Balance.RAD_LEVEL_INTERNAL_ELEVATED,
        Balance.RAD_LEVEL_INTERNAL_HIGH,
        Balance.RAD_LEVEL_INTERNAL_EXTREME,
    )
    print(f"hull: {ship.hull_integrity:.2f}")
    print(
        "radiation: "
        f"env={env_rad:.4f}rad/s ({_radiation_level_label(locale, env_level)}) "
        f"internal={internal_rad:.4f}rad/s ({_radiation_level_label(locale, internal_level)})"
    )
    core_os = ship.systems.get("core_os")
    if core_os:
        if core_os.state == SystemState.OFFLINE:
            msg = {
                "en": "core_os: offline (terminal control lost)",
                "es": "core_os: fuera de línea (control terminal perdido)",
            }
            print(msg.get(locale, msg["en"]))
        elif core_os.state == SystemState.CRITICAL:
            msg = {
                "en": "core_os: critical (emergency recovery command set active)",
                "es": "core_os: crítico (set de recuperación de emergencia activo)",
            }
            print(msg.get(locale, msg["en"]))
        elif core_os.state == SystemState.LIMITED:
            msg = {
                "en": "core_os: limited (advanced commands blocked)",
                "es": "core_os: limitado (comandos avanzados bloqueados)",
            }
            print(msg.get(locale, msg["en"]))
        elif core_os.state == SystemState.DAMAGED:
            msg = {
                "en": "core_os: damaged (advanced commands blocked; travel blocked)",
                "es": "core_os: dañado (comandos avanzados bloqueados; viaje bloqueado)",
            }
            print(msg.get(locale, msg["en"]))
    life_support = ship.systems.get("life_support")
    if life_support:
        if life_support.state == SystemState.OFFLINE:
            remaining = max(0.0, Balance.LIFE_SUPPORT_CRITICAL_GRACE_S - ship.life_support_offline_s)
            if state.os.terminal_lock and state.os.terminal_reason == "life_support_offline":
                msg = {
                    "en": "life_support: offline (host viability lost)",
                    "es": "life_support: fuera de línea (viabilidad del huésped perdida)",
                }
            else:
                msg = {
                    "en": f"life_support: offline (grace { _format_eta_short(remaining, locale) } remaining)",
                    "es": f"life_support: fuera de línea (gracia restante { _format_eta_short(remaining, locale) })",
                }
            print(msg.get(locale, msg["en"]))
        elif life_support.state == SystemState.CRITICAL:
            msg = {
                "en": "life_support: critical",
                "es": "life_support: crítico",
            }
            print(msg.get(locale, msg["en"]))
        elif life_support.state == SystemState.LIMITED:
            msg = {
                "en": "life_support: limited (degraded)",
                "es": "life_support: limitado (degradado)",
            }
            print(msg.get(locale, msg["en"]))
    disp_scrap, disp_modules, dirty = _inventory_view(ship)
    dirty_suffix = " [manifest stale]" if dirty else ""
    print(f"inventory: scrap={disp_scrap} modules={len(disp_modules)}{dirty_suffix}")
    if disp_modules:
        counts: dict[str, int] = {}
        for mid in disp_modules:
            counts[mid] = counts.get(mid, 0) + 1
        summary = ", ".join(f"{mid} x{count}" for mid, count in sorted(counts.items()))
        print(f"modules: {summary}")
    if ship.installed_modules:
        counts: dict[str, int] = {}
        for mid in ship.installed_modules:
            counts[mid] = counts.get(mid, 0) + 1
        summary = ", ".join(f"{mid} x{count}" for mid, count in sorted(counts.items()))
        print(f"installed: {summary}")
    print("systems:")
    for sid, sys in ship.systems.items():
        svc = ""
        if sys.service:
            svc = f" svc={sys.service.service_name} running={sys.service.is_running}"
        fo = " forced_offline" if sys.forced_offline else ""
        print(f" - {sid:18s} state={sys.state.value:8s} health={sys.health:.2f}{fo}{svc}")


def render_auth_status(state) -> None:
    ordered = ["GUEST", "MED", "ENG", "OPS", "SEC", "ROOT"]
    levels = [lvl for lvl in ordered if lvl in state.os.auth_levels]
    print("\n=== AUTH STATUS ===")
    if not levels:
        print("(none)")
        return
    for lvl in levels:
        print(f"- {lvl}")


def render_power_status(state) -> None:
    ship = state.ship
    p = ship.power
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    net = p.p_gen_kw - p.p_load_kw
    deficit = max(0.0, p.p_load_kw - p.p_gen_kw)
    headroom = p.p_discharge_max_kw - deficit
    print("\n=== POWER ===")
    print(f"P_gen={p.p_gen_kw:.2f} kW")
    print(f"P_load={p.p_load_kw:.2f} kW")
    print(f"net={net:+.2f} kW  headroom={headroom:.2f} kW")
    print(f"Battery={p.e_batt_kwh:.3f}/{p.e_batt_max_kwh:.3f} kWh (SoC={soc:.2f})")
    print(f"Quality={p.power_quality:.2f}  DeficitRatio={p.deficit_ratio:.2f}  Brownout={p.brownout}")
    print(f"hull: {ship.hull_integrity:.2f}")


def render_diag(state, system_id: str) -> None:
    sys = state.ship.systems.get(system_id)
    if not sys:
        print(f"(diag) system_id no encontrado: {system_id}")
        return
    print("\n=== DIAG ===")
    print(f"id: {sys.system_id}")
    print(f"name: {sys.name}")
    sector = state.ship.sectors.get(sys.sector_id)
    if sector:
        print(f"location: {sys.sector_id} ({sector.name})")
    else:
        print(f"location: {sys.sector_id}")
    print(f"state: {sys.state.value}")
    print(f"health: {sys.health:.2f}")
    print(f"p_nom: {sys.p_nom_kw:.2f} kW  p_eff: {sys.p_effective_kw():.2f} kW")
    print(f"priority: {sys.priority}")
    print(f"forced_offline: {sys.forced_offline}")
    if sys.forced_offline:
        if sys.auto_offline_reason == "energy_distribution_offline":
            print("notes: auto-offline due to energy_distribution collapse.")
        else:
            print("notes: manually powered down (power off/shutdown).")
    if sys.dependencies:
        print("dependencies:")
        for d in sys.dependencies:
            print(f" - {d.dep_type} {d.target_id} >= {d.value}")
    if sys.service:
        print(f"service: {sys.service.service_name} running={sys.service.is_running} boot_time={sys.service.boot_time_s}s")
    if system_id == "energy_distribution" and sys.state != SystemState.NOMINAL:
        print("notes: grid phase alignment unstable. manual intervention required.")
    if system_id == "power_core" and sys.state == SystemState.DAMAGED:
        print("notes: output oscillation detected. efficiency reduced.")
    if system_id == "drone_bay":
        dist = state.ship.systems.get("energy_distribution")
        if sys.state == SystemState.OFFLINE or (dist and dist.state == SystemState.OFFLINE):
            print("notes: no drone charging available.")


def render_alerts(state) -> None:
    print("\n=== ALERTS (active) ===")
    active = [a for a in state.events.alerts.values() if a.is_active]
    if not active:
        print("(none)")
        return
    locale = state.os.locale.value
    hint = {
        "en": "Hint: use 'alerts explain <alert_key>' for more details.",
        "es": "Sugerencia: usa 'alerts explain <alert_key>' para más detalles.",
    }.get(locale, "Hint: use 'alerts explain <alert_key>' for more details.")
    print(hint)
    # Ordena por severidad y recencia
    sev_rank = {"critical": 0, "warn": 1, "info": 2}
    active.sort(key=lambda a: (sev_rank.get(a.severity.value, 9), -a.last_seen_t))
    for a in active:
        print(f"- {a.severity.value.upper():8s} {a.alert_key:24s} unacked={_format_eta_short(a.unacked_s, locale)}")


def render_logs(state, limit: int = 15) -> None:
    print("\n=== EVENTS (recent) ===")
    for e in state.events.recent[-limit:]:
        t_label = format_elapsed_short(float(e.t), include_seconds=True)
        if t_label.startswith("T+"):
            t_label = t_label[2:]
        print(f"- [{t_label}] [{e.severity.value.upper()}] {e.type.value}: {e.message}")


def render_jobs(state, limit: int | None = 5) -> None:
    print("\n=== JOBS ===")
    jobs_state = state.jobs
    active_jobs = []
    for job_id in jobs_state.active_job_ids:
        job = jobs_state.jobs.get(job_id)
        if job:
            active_jobs.append(job)
    running_by_owner: set[str] = set()
    route_solve_running = False
    for job in active_jobs:
        if job.status == JobStatus.RUNNING and job.owner_id:
            running_by_owner.add(job.owner_id)
        if job.status == JobStatus.RUNNING and job.job_type == JobType.ROUTE_SOLVE:
            route_solve_running = True

    if not jobs_state.jobs:
        print("(none)")
        return

    locale = state.os.locale.value
    wait_note_templates = {
        "en": " (waiting: drone busy {drone_id})",
        "es": " (en espera: dron ocupado {drone_id})",
    }
    route_wait_note_templates = {
        "en": " (waiting: route solver busy)",
        "es": " (en espera: solver de rutas ocupado)",
    }

    def _format_job(job):
        target = f"{job.target.kind}:{job.target.id}" if job.target else "-"
        eta = _format_eta_short(job.eta_s, locale) if job.status in {JobStatus.QUEUED, JobStatus.RUNNING} else "-"
        owner = job.owner_id or "-"
        emergency = " EMERGENCY" if job.params.get("emergency") else ""
        wait_note = ""
        if job.status == JobStatus.QUEUED and job.owner_id and job.owner_id in running_by_owner:
            tmpl = wait_note_templates.get(locale, wait_note_templates["en"])
            wait_note = tmpl.format(drone_id=job.owner_id)
        if job.status == JobStatus.QUEUED and job.job_type == JobType.ROUTE_SOLVE and route_solve_running:
            tmpl = route_wait_note_templates.get(locale, route_wait_note_templates["en"])
            wait_note += tmpl
        return f"- {job.job_id}: {job.status.value:8s} type={job.job_type.value} target={target} ETA={eta} owner={owner}{emergency}{wait_note}"

    print("Active (queued/running):")
    if active_jobs:
        for job in active_jobs:
            print(_format_job(job))
    else:
        print("- (none)")

    history = [
        job
        for job in jobs_state.jobs.values()
        if (job.internal_id or job.job_id) not in jobs_state.active_job_ids
        and job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
    ]
    if history:
        print("Recent complete/failed/cancelled:")
        history_sorted = sorted(history, key=lambda job: int(job.terminal_seq or 0), reverse=True)
        if limit is not None:
            history_sorted = history_sorted[:limit]
        for job in history_sorted:
            print(_format_job(job))


def render_drone_status(state, drone_id: str | None = None) -> None:
    print("\n=== DRONES ===")
    locale = state.os.locale.value
    drones = state.ship.drones
    if drone_id is not None:
        d = drones.get(drone_id)
        if d is None:
            msg = {
                "en": f"drone status: drone not found ({drone_id})",
                "es": f"drone status: dron no encontrado ({drone_id})",
            }
            print(msg.get(locale, msg["en"]))
            return
        drone_items = [(drone_id, d)]
    else:
        drone_items = list(drones.items())
    modules = load_modules()
    for did, d in drone_items:
        profile = compute_drone_effective_profile(d, modules)
        battery_pct = 100.0 * d.battery / max(0.000001, profile.battery_max_effective)
        integrity_pct = 100.0 * d.integrity / max(0.000001, profile.integrity_max_effective)
        installed_modules = list(d.installed_modules or [])
        module_counts = _module_counts(installed_modules)
        slots_used = 0
        for mid in installed_modules:
            info = modules.get(mid, {})
            if _module_scope(info) != "drone":
                continue
            slots_used += int(info.get("slot_cost", 1) or 1)
        modules_suffix = ""
        if installed_modules:
            listed = ", ".join(
                f"{mid} x{count}" if count > 1 else mid
                for mid, count in module_counts.items()
            )
            modules_suffix = f" ({listed})"
        dose_level = _radiation_level_id(
            d.dose_rad,
            Balance.RAD_LEVEL_DRONE_DOSE_ELEVATED,
            Balance.RAD_LEVEL_DRONE_DOSE_HIGH,
            Balance.RAD_LEVEL_DRONE_DOSE_EXTREME,
        )
        ar_mode = "on" if d.autorecall_enabled else "off"
        ar_threshold = int(round(d.autorecall_threshold * 100.0))
        print(
            f"- drone_id={did} status={d.status.value} loc={d.location.kind}:{d.location.id} "
            f"battery={d.battery:.2f}/{profile.battery_max_effective:.2f} ({battery_pct:.0f}%) "
            f"integrity={d.integrity:.2f}/{profile.integrity_max_effective:.2f} ({integrity_pct:.0f}%) "
            f"dose={d.dose_rad:.3f} ({_radiation_level_label(locale, dose_level)}) "
            f"slots={slots_used}/{int(d.module_slots_max)} "
            f"mods={len(installed_modules)}{modules_suffix} "
            f"autorecall={ar_mode}@{ar_threshold}%"
        )
        if drone_id is not None and installed_modules:
            label = "módulos instalados" if locale == "es" else "installed modules"
            print(f"  {label}:")
            for mid, count in sorted(module_counts.items()):
                info = modules.get(mid, {})
                name = str(info.get("name", mid))
                suffix = f" x{count}" if count > 1 else ""
                print(f"  - {name}{suffix} [{mid}]")


def _set_drone_autorecall(state, drone_id: str, enabled: bool | None = None, threshold: float | None = None) -> None:
    drone = state.ship.drones.get(drone_id)
    locale = state.os.locale.value
    if not drone:
        msg = {
            "en": f"drone autorecall: drone not found ({drone_id})",
            "es": f"drone autorecall: dron no encontrado ({drone_id})",
        }
        print(msg.get(locale, msg["en"]))
        return
    if enabled is not None:
        drone.autorecall_enabled = bool(enabled)
        mode = "on" if drone.autorecall_enabled else "off"
        msg = {
            "en": f"drone autorecall: {drone_id} set to {mode} (threshold={drone.autorecall_threshold*100:.0f}%)",
            "es": f"drone autorecall: {drone_id} configurado a {mode} (umbral={drone.autorecall_threshold*100:.0f}%)",
        }
        print(msg.get(locale, msg["en"]))
        return
    if threshold is not None:
        drone.autorecall_threshold = max(0.0, min(1.0, float(threshold)))
        msg = {
            "en": f"drone autorecall: {drone_id} threshold set to {drone.autorecall_threshold*100:.0f}%",
            "es": f"drone autorecall: umbral de {drone_id} configurado a {drone.autorecall_threshold*100:.0f}%",
        }
        print(msg.get(locale, msg["en"]))


def render_inventory(state) -> None:
    print("\n=== INVENTORY ===")
    disp_scrap, disp_modules, dirty = _inventory_view(state.ship)
    suffix = " (stale; run 'cargo audit')" if dirty else ""
    print(f"scrap: {disp_scrap}{suffix}")
    if disp_modules:
        counts: dict[str, int] = {}
        for mid in disp_modules:
            counts[mid] = counts.get(mid, 0) + 1
        print("modules:")
        for mid, count in sorted(counts.items()):
            suffix = f" x{count}" if count > 1 else ""
            print(f"- {mid}{suffix}")
    else:
        print("modules: (none)")
    if dirty:
        print("(cargo changes pending; run 'cargo audit' to refresh)")


def _module_scope(info: dict) -> str:
    scope = str(info.get("scope", "ship")).strip().lower() or "ship"
    return scope if scope in {"ship", "drone"} else "ship"


def _module_effects(info: dict) -> dict:
    scope = _module_scope(info)
    if scope == "drone":
        return dict(info.get("drone_effects", {}) or {})
    return dict(info.get("effects", {}) or {})


def _format_module_effect(effect_key: str, value, locale: str) -> str:
    labels = {
        "integrity_max_add": {"en": "max integrity", "es": "integridad máxima"},
        "battery_max_add": {"en": "max battery", "es": "batería máxima"},
        "cargo_capacity_add": {"en": "cargo capacity", "es": "capacidad de carga"},
        "move_time_mult": {"en": "move time", "es": "tiempo de movimiento"},
        "deploy_time_mult": {"en": "deploy time", "es": "tiempo de despliegue"},
        "survey_time_mult": {"en": "survey time", "es": "tiempo de survey"},
        "repair_time_mult": {"en": "repair time", "es": "tiempo de reparación"},
        "repair_fail_p_mult": {"en": "repair fail chance", "es": "prob. de fallo de reparación"},
        "repair_scrap_cost_mult": {"en": "repair scrap cost", "es": "coste de chatarra en reparación"},
        "power_quality_offset": {"en": "power quality", "es": "calidad de energía"},
        "e_batt_bonus_kwh": {"en": "battery capacity", "es": "capacidad de batería"},
        "p_gen_bonus_kw": {"en": "generation power", "es": "potencia de generación"},
    }
    label = labels.get(effect_key, {}).get(locale, effect_key)
    try:
        fv = float(value)
    except Exception:
        return f"{label}: {value}"
    if effect_key.endswith("_mult"):
        return f"{label}: x{fv:.2f}"
    sign = "+" if fv >= 0 else ""
    return f"{label}: {sign}{fv:.2f}"


def _module_drawbacks(info: dict, locale: str) -> list[str]:
    key = "drawbacks_es" if locale == "es" else "drawbacks_en"
    raw = info.get(key, [])
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _module_counts(module_ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for mid in module_ids:
        counts[mid] = counts.get(mid, 0) + 1
    return counts


def render_modules_installed(state) -> None:
    print("\n=== MODULES ===")
    locale = state.os.locale.value
    modules = load_modules()
    disp_scrap, disp_modules, dirty = _inventory_view(state.ship)
    _ = disp_scrap

    print("ship installed:")
    ship_installed = list(state.ship.installed_modules or [])
    if ship_installed:
        ship_counts = _module_counts(ship_installed)
        for mid, count in sorted(ship_counts.items()):
            info = modules.get(mid, {})
            name = info.get("name", mid)
            scope = _module_scope(info)
            suffix = f" x{count}" if count > 1 else ""
            print(f"- {mid}: {name}{suffix} [scope={scope}]")
    else:
        print("- (none)")

    print("drone installed:")
    has_drone_modules = False
    for drone_id in sorted(state.ship.drones.keys()):
        drone = state.ship.drones[drone_id]
        mids = list(drone.installed_modules or [])
        if not mids:
            continue
        has_drone_modules = True
        used_slots = 0
        for mid in mids:
            info = modules.get(mid, {})
            if _module_scope(info) != "drone":
                continue
            used_slots += int(info.get("slot_cost", 1) or 1)
        print(f"- {drone_id} (slots {used_slots}/{int(drone.module_slots_max)}):")
        counts = _module_counts(mids)
        for mid, count in sorted(counts.items()):
            info = modules.get(mid, {})
            name = info.get("name", mid)
            scope = _module_scope(info)
            suffix = f" x{count}" if count > 1 else ""
            print(f"  - {mid}: {name}{suffix} [scope={scope}]")
    if not has_drone_modules:
        print("- (none)")

    print("inventory (manifest view):")
    inv_ship: dict[str, int] = {}
    inv_drone: dict[str, int] = {}
    for mid in list(disp_modules or []):
        info = modules.get(mid, {})
        if _module_scope(info) == "drone":
            inv_drone[mid] = inv_drone.get(mid, 0) + 1
        else:
            inv_ship[mid] = inv_ship.get(mid, 0) + 1
    print("- ship scope:")
    if inv_ship:
        for mid, count in sorted(inv_ship.items()):
            info = modules.get(mid, {})
            name = info.get("name", mid)
            suffix = f" x{count}" if count > 1 else ""
            print(f"  - {mid}: {name}{suffix}")
    else:
        print("  - (none)")
    print("- drone scope:")
    if inv_drone:
        for mid, count in sorted(inv_drone.items()):
            info = modules.get(mid, {})
            name = info.get("name", mid)
            suffix = f" x{count}" if count > 1 else ""
            print(f"  - {mid}: {name}{suffix}")
    else:
        print("  - (none)")
    if dirty:
        note = {
            "en": "(manifest stale; run 'cargo audit' for synchronized inventory view)",
            "es": "(manifiesto desactualizado; ejecuta 'cargo audit' para sincronizar inventario)",
        }
        print(note.get(locale, note["en"]))


def render_module_inspect(state, module_id: str) -> None:
    modules = load_modules()
    info = modules.get(module_id)
    if not info:
        print(f"(module) unknown module_id: {module_id}")
        return
    locale = state.os.locale.value
    name = info.get("name", module_id)
    scope = _module_scope(info)
    effects = _module_effects(info)
    drawbacks = _module_drawbacks(info, locale)
    slot_cost = int(info.get("slot_cost", 1) or 1) if scope == "drone" else 0
    desc = info.get("desc_es") if locale == "es" else info.get("desc_en")
    in_inventory_count = state.ship.cargo_modules.count(module_id)
    ship_installed_count = state.ship.installed_modules.count(module_id)
    drone_holders: dict[str, int] = {}
    for drone_id, drone in state.ship.drones.items():
        cnt = list(drone.installed_modules or []).count(module_id)
        if cnt > 0:
            drone_holders[drone_id] = cnt

    print("\n=== MODULE INSPECT ===")
    print(f"id: {module_id}")
    print(f"name: {name}")
    print(f"scope: {scope}")
    if scope == "drone":
        print(f"slots: {slot_cost}")
    else:
        print("slots: n/a (ship module)")
    print("effects:")
    if effects:
        for key, value in effects.items():
            print(f"- {_format_module_effect(str(key), value, locale)}")
    else:
        empty = {"en": "(none)", "es": "(ninguno)"}
        print(f"- {empty.get(locale, empty['en'])}")
    print("drawbacks:")
    if drawbacks:
        for line in drawbacks:
            print(f"- {line}")
    else:
        empty = {"en": "(none declared)", "es": "(sin contrapartidas declaradas)"}
        print(f"- {empty.get(locale, empty['en'])}")
    if desc:
        print(f"desc: {desc}")
    print("presence:")
    print(f"- inventory: {in_inventory_count}")
    print(f"- ship installed: {ship_installed_count}")
    if drone_holders:
        for drone_id in sorted(drone_holders.keys()):
            count = drone_holders[drone_id]
            suffix = f" x{count}" if count > 1 else ""
            print(f"- drone {drone_id}{suffix}")
    else:
        none = {"en": "- drones: (none)", "es": "- drones: (ninguno)"}
        print(none.get(locale, none["en"]))


def render_modules_catalog(state) -> None:
    print("\n=== MODULES CATALOG ===")
    modules = load_modules()
    if not modules:
        print("(none)")
        return
    locale = state.os.locale.value
    for mid, info in modules.items():
        name = info.get("name", mid)
        scope = _module_scope(info)
        slot_cost = int(info.get("slot_cost", 1) or 1) if scope == "drone" else 0
        scrap_cost = info.get("scrap_cost", "?")
        effects = _module_effects(info)
        effects_str = ", ".join(f"{k}={v}" for k, v in effects.items()) or "no effects"
        desc = info.get("desc_es") if locale == "es" else info.get("desc_en")
        slot_txt = f" slots={slot_cost}" if scope == "drone" else ""
        print(f"- {mid}: {name} [scope={scope}{slot_txt}] (installation scrap cost {scrap_cost}) [{effects_str}]")
        if desc:
            print(f"  {desc}")


def render_debug_arcs(state) -> None:
    print("\n=== DEBUG ARCS ===")
    arcs = load_arcs()
    placements = state.world.lore_placements.piece_to_node
    channels = state.world.lore_placements.piece_channel_bindings
    delivered = state.world.lore.delivered
    if not arcs:
        print("(none)")
    else:
        legacy = state.world.arc_placements
        for arc in arcs:
            arc_id = arc.get("arc_id", "?")
            st = legacy.get(arc_id, {})
            primary_piece = arc.get("primary_intel") or {}
            print(f"- {arc_id}:")
            if primary_piece:
                primary_id = primary_piece.get("id") or "primary"
                primary_key = f"arc:{arc_id}:{primary_id}"
                node_id = placements.get(primary_key)
                channel = channels.get(primary_key, "-")
                status = "delivered" if primary_key in delivered else ("assigned" if node_id else "unplaced")
                if node_id:
                    print(f"  primary: {node_id} channel={channel} status={status}")
                else:
                    print("  primary: (unplaced)")
            else:
                print("  primary: (none)")
            secondary_docs = arc.get("secondary_lore_docs", []) or []
            if secondary_docs:
                for doc in secondary_docs:
                    doc_id = doc.get("id") or "secondary"
                    doc_key = f"arc:{arc_id}:{doc_id}"
                    node_id = placements.get(doc_key)
                    channel = channels.get(doc_key, "-")
                    status = "delivered" if doc_key in delivered else ("assigned" if node_id else "unplaced")
                    if node_id:
                        print(f"  secondary: {doc_id} -> {node_id} channel={channel} status={status}")
                    else:
                        print(f"  secondary: {doc_id} -> (unplaced)")
            else:
                print("  secondary: (none)")
            if st:
                counters = st.get("counters", {})
                if counters:
                    print(f"  legacy_counters: {counters}")
        print(
            f"- scheduler: eval_seq={state.world.lore_placements.eval_seq} "
            f"next_non_forced_eval_t={state.world.lore_placements.next_non_forced_eval_t:.1f}s"
        )
    print(f"- mobility_failsafe_count: {state.world.mobility_failsafe_count}")
    print(f"- mobility_no_new_uplink_count: {state.world.mobility_no_new_uplink_count}")
    if state.world.mobility_hints:
        for hint in state.world.mobility_hints[-5:]:
            print(
                f"  mobility_hint: {hint.get('from')} -> {hint.get('to')} "
                f"conf={hint.get('confidence')} source={hint.get('source_kind')}"
            )

def render_debug_lore(state) -> None:
    print("\n=== DEBUG LORE ===")
    delivered = sorted(state.world.lore.delivered)
    print(f"- delivered_count: {len(delivered)}")
    if delivered:
        for item in delivered[-10:]:
            print(f"  delivered: {item}")
        if len(delivered) > 10:
            print("  ...")
    counters = state.world.lore.counters
    print(f"- counters: {counters}")
    print(f"- last_delivery_t: {state.world.lore.last_delivery_t:.1f}s")
    placements = state.world.lore_placements
    print(f"- placements_count: {len(placements.piece_to_node)}")
    print(
        f"- scheduler: eval_seq={placements.eval_seq} "
        f"next_non_forced_eval_t={placements.next_non_forced_eval_t:.1f}s"
    )
    if placements.piece_to_node:
        print("- assigned_recent:")
        assigned_recent = sorted(placements.piece_to_node.items())[-10:]
        for piece_key, node_id in assigned_recent:
            channel = placements.piece_channel_bindings.get(piece_key, "-")
            status = "delivered" if piece_key in state.world.lore.delivered else "pending"
            print(f"  {piece_key} -> {node_id} channel={channel} status={status}")

    pending_forced_unplaced: list[dict] = []
    pending_forced_assigned: list[dict] = []
    for entry in list_lore_piece_entries():
        piece = entry.get("piece") or {}
        if not entry.get("force", False):
            continue
        policy = str(piece.get("force_policy", "none") or "none")
        if policy == "none":
            continue
        piece_key = entry.get("piece_key")
        if not piece_key or piece_key in state.world.lore.delivered:
            continue
        item = {
            "key": piece_key,
            "policy": policy,
            "deadline": piece.get("force_deadline"),
            "allowed": entry.get("channels"),
            "constraints": piece.get("constraints"),
            "node_id": placements.piece_to_node.get(piece_key),
            "channel": placements.piece_channel_bindings.get(piece_key),
        }
        if item["node_id"]:
            pending_forced_assigned.append(item)
        else:
            pending_forced_unplaced.append(item)

    if pending_forced_unplaced or pending_forced_assigned:
        if pending_forced_unplaced:
            print("- forced_pending_unplaced:")
            for item in pending_forced_unplaced:
                print(
                    f"  {item['key']} policy={item['policy']} "
                    f"deadline={item['deadline']} allowed={item['allowed']} constraints={item['constraints']}"
                )
        if pending_forced_assigned:
            print("- forced_pending_assigned:")
            for item in pending_forced_assigned:
                print(
                    f"  {item['key']} node={item['node_id']} channel={item['channel']} policy={item['policy']}"
                )
    else:
        print("- forced_pending: (none)")

    current_node_id = state.world.current_node_id
    pool = state.world.node_pools.get(current_node_id)
    if pool:
        pending_push = sorted(pid for pid in pool.pending_push_piece_ids if pid not in pool.delivered_piece_ids)
        print(
            f"- current_pool[{current_node_id}]: window_open={pool.window_open} "
            f"node_cleaned={pool.node_cleaned} scrap_complete={pool.scrap_complete} "
            f"data_complete={pool.data_complete} extras_complete={pool.extras_complete} "
            f"uplink_data_consumed={pool.uplink_data_consumed}"
        )
        if pending_push:
            print(f"  pending_push_count={len(pending_push)}")

    if state.world.dead_nodes:
        print("- dead_nodes:")
        for node_id, st in state.world.dead_nodes.items():
            print(
                f"  {node_id} stuck_uplinks={st.stuck_threshold_uplinks} "
                f"dead_uplinks={st.dead_threshold_uplinks} "
                f"stuck_years={st.stuck_threshold_years:.1f} "
                f"dead_years={st.dead_threshold_years:.1f} "
                f"attempts={st.attempts} bridge={st.bridge_node_id}"
            )
    if state.world.deadnode_log:
        print("- deadnode_log:")
        for line in state.world.deadnode_log[-10:]:
            print(f"  {line}")


def render_debug_deadnodes(state) -> None:
    print("\n=== DEBUG DEADNODES ===")
    if not state.world.dead_nodes:
        print("(none)")
        return
    for node_id, st in state.world.dead_nodes.items():
        print(
            f"- {node_id}: "
            f"stuck_uplinks={st.stuck_threshold_uplinks} "
            f"dead_uplinks={st.dead_threshold_uplinks} "
            f"stuck_years={st.stuck_threshold_years:.1f} "
            f"dead_years={st.dead_threshold_years:.1f} "
            f"attempts={st.attempts} "
            f"bridge={st.bridge_node_id}"
        )
    if state.world.deadnode_log:
        print("log:")
        for line in state.world.deadnode_log[-10:]:
            print(f"- {line}")


def _galactic_radius_ly(x_ly: float, y_ly: float, z_ly: float) -> float:
    gx, gy, gz = op_to_galactic_coords(x_ly, y_ly, z_ly)
    return galactic_radius(gx, gy, gz)


def _sector_center_ly(sector_id: str) -> tuple[float, float, float] | None:
    coords = _sector_coords_from_id(sector_id)
    if coords is None:
        return None
    sx, sy, sz = coords
    half = SECTOR_SIZE_LY * 0.5
    return (
        sx * SECTOR_SIZE_LY + half,
        sy * SECTOR_SIZE_LY + half,
        sz * SECTOR_SIZE_LY + half,
    )


def _sector_region_operational(sector_id: str) -> str:
    center = _sector_center_ly(sector_id)
    if center is None:
        return "unknown"
    x, y, z = center
    return legacy_operational_region_for_pos(x, y, z)


def _sector_region_physical(sector_id: str) -> str:
    center = _sector_center_ly(sector_id)
    if center is None:
        return "unknown"
    x, y, z = center
    return galactic_region_for_op_pos(x, y, z)


def _neighbor_sectors_2d(sector_id: str) -> list[str]:
    coords = _sector_coords_from_id(sector_id)
    if coords is None:
        return []
    sx, sy, sz = coords
    out: list[str] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            out.append(f"S{sx+dx:+04d}_{sy+dy:+04d}_{sz:+04d}")
    return out


def _radiation_band_id(value: float) -> str:
    v = max(0.0, float(value))
    if v >= Balance.RAD_LEVEL_ENV_EXTREME:
        return "extreme"
    if v >= Balance.RAD_LEVEL_ENV_HIGH:
        return "high"
    if v >= Balance.RAD_LEVEL_ENV_ELEVATED:
        return "elevated"
    return "low"


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str | None:
    items = [(key, max(0.0, float(weight))) for key, weight in weights.items() if max(0.0, float(weight)) > 0.0]
    if not items:
        return None
    total = sum(weight for _, weight in items)
    if total <= 0.0:
        return None
    roll = rng.random() * total
    upto = 0.0
    for key, weight in items:
        upto += weight
        if roll <= upto:
            return key
    return items[-1][0]


def render_debug_galaxy(state) -> None:
    print("\n=== DEBUG GALAXY ===")
    op_cx = float(Balance.GALAXY_OP_REGION_CENTER_X_LY)
    op_cy = float(Balance.GALAXY_OP_REGION_CENTER_Y_LY)
    op_cz = float(Balance.GALAXY_OP_REGION_CENTER_Z_LY)
    op_bulge_r = float(Balance.GALAXY_OP_BULGE_RADIUS_LY)
    op_disk_r = float(Balance.GALAXY_OP_DISK_OUTER_RADIUS_LY)
    print(
        f"- model_operational: center=({op_cx:.2f},{op_cy:.2f},{op_cz:.2f}) "
        f"bulge<{op_bulge_r:.2f}ly disk<{op_disk_r:.2f}ly halo>=disk"
    )
    ph_cx = float(Balance.GALAXY_PHYSICAL_CENTER_X_LY)
    ph_cy = float(Balance.GALAXY_PHYSICAL_CENTER_Y_LY)
    ph_cz = float(Balance.GALAXY_PHYSICAL_CENTER_Z_LY)
    ph_bulge_r = float(Balance.GALAXY_PHYSICAL_BULGE_RADIUS_LY)
    ph_disk_r = float(Balance.GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY)
    ph_galaxy_r = float(Balance.GALAXY_PHYSICAL_RADIUS_LY)
    print(
        f"- model_physical: center=({ph_cx:.2f},{ph_cy:.2f},{ph_cz:.2f}) "
        f"bulge<{ph_bulge_r:.2f}ly disk<{ph_disk_r:.2f}ly halo>=disk galaxy<= {ph_galaxy_r:.2f}ly"
    )

    px, py, pz = state.world.current_pos_ly
    op_region = legacy_operational_region_for_pos(px, py, pz)
    gx, gy, gz = op_to_galactic_coords(px, py, pz)
    pr = _galactic_radius_ly(px, py, pz)
    phys_region = galactic_region_for_op_pos(px, py, pz)
    margins = galactic_margins_for_op_pos(px, py, pz)
    psector = sector_id_for_pos(px, py, pz)
    print(
        f"- player: node={state.world.current_node_id} sector={psector} "
        f"op_pos=({px:.2f},{py:.2f},{pz:.2f}) operational_region={op_region}"
    )
    print(f"  physical_pos=({gx:.2f},{gy:.2f},{gz:.2f}) r_gc={pr:.2f}ly physical_region={phys_region}")
    print(
        f"  margin_physical: to_bulge={float(margins.get('distance_to_bulge_ly', 0.0)):.2f}ly "
        f"to_halo={float(margins.get('distance_to_halo_ly', 0.0)):.2f}ly "
        f"to_galaxy_edge={float(margins.get('distance_to_galaxy_edge_ly', 0.0)):.2f}ly "
        f"inside_galaxy={bool(margins.get('inside_galaxy', True))}"
    )

    sector_ids: set[str] = set(state.world.generated_sectors)
    for node in state.world.space.nodes.values():
        sector_ids.add(sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly))
    sector_ids.add(psector)

    op_region_counts: dict[str, int] = {"bulge": 0, "disk": 0, "halo": 0, "unknown": 0}
    phys_region_counts: dict[str, int] = {"bulge": 0, "disk": 0, "halo": 0, "unknown": 0}
    for sid in sector_ids:
        op_reg = _sector_region_operational(sid)
        phys_reg = _sector_region_physical(sid)
        op_region_counts[op_reg] = op_region_counts.get(op_reg, 0) + 1
        phys_region_counts[phys_reg] = phys_region_counts.get(phys_reg, 0) + 1
    print(
        f"- sectors_seen: total={len(sector_ids)} "
        f"operational(b={op_region_counts.get('bulge', 0)},d={op_region_counts.get('disk', 0)},h={op_region_counts.get('halo', 0)}) "
        f"physical(b={phys_region_counts.get('bulge', 0)},d={phys_region_counts.get('disk', 0)},h={phys_region_counts.get('halo', 0)})"
    )

    transitions: dict[tuple[str, str], int] = {}
    for sid in sorted(sector_ids):
        r1 = _sector_region_physical(sid)
        for nid in _neighbor_sectors_2d(sid):
            if nid not in sector_ids or sid >= nid:
                continue
            r2 = _sector_region_physical(nid)
            key = tuple(sorted((r1, r2)))
            transitions[key] = transitions.get(key, 0) + 1
    same = sum(v for k, v in transitions.items() if k[0] == k[1])
    bd = transitions.get(("bulge", "disk"), 0)
    dh = transitions.get(("disk", "halo"), 0)
    bh = transitions.get(("bulge", "halo"), 0)
    print(f"- sector_adjacency: same_region={same} bulge<->disk={bd} disk<->halo={dh} bulge<->halo={bh}")
    if bh > 0:
        print("! warning: bulge<->halo direct adjacency detected (coherence risk)")
    capped = float(Balance.MAX_ROUTE_HOP_LY)
    known_link_total = 0
    known_link_over_cap = 0
    for left, rights in state.world.known_links.items():
        for right in rights:
            if left >= right:
                continue
            dist = distance_between_nodes_ly(state.world, left, right)
            if dist is None:
                continue
            known_link_total += 1
            if dist > capped:
                known_link_over_cap += 1
    print(
        f"- link_cap: max_hop={capped:.1f}ly known_links={known_link_total} over_cap={known_link_over_cap}"
    )
    archetypes = load_worldgen_archetypes()
    current_sector_state = state.world.sector_states.get(psector)
    if current_sector_state:
        archetype_cfg = archetypes.get(current_sector_state.archetype, {})
        caps = archetype_cfg.get("kind_caps", {}) or {}
        forbidden = sorted(str(item) for item in (archetype_cfg.get("forbidden_kinds", []) or []))
        caps_txt = ",".join(f"{kind}:{int(caps[kind])}" for kind in sorted(caps)) or "-"
        forbidden_txt = ",".join(forbidden) or "-"
        print(
            f"- current_sector_gen: generated=yes region={current_sector_state.region or phys_region} "
            f"archetype={current_sector_state.archetype or '-'} nodes={len(current_sector_state.node_ids)} "
            f"topology_hub={current_sector_state.topology_hub_node_id or '-'} "
            f"playable_hub={current_sector_state.playable_hub_node_id or '-'} "
            f"internal_links={int(current_sector_state.internal_link_count)} "
            f"intersector_links={int(current_sector_state.intersector_link_count)}"
        )
        print(
            "  archetype_cfg: "
            f"caps={caps_txt} forbidden={forbidden_txt} "
            f"playable_hub_prob={float(archetype_cfg.get('playable_hub_prob', 0.0) or 0.0):.2f} "
            f"intersector_link_max={int(archetype_cfg.get('intersector_link_max', 0) or 0)} "
            f"intersector_link_prob={float(archetype_cfg.get('intersector_link_prob', 0.0) or 0.0):.2f} "
            f"extra_internal_link_prob={float(archetype_cfg.get('extra_internal_link_prob', 0.0) or 0.0):.2f}"
        )
    else:
        print(f"- current_sector_gen: generated={'yes' if psector in state.world.generated_sectors else 'no'} region={phys_region} archetype=(not_generated)")
    if state.world.current_node_id == "UNKNOWN_00":
        if phys_region != "disk":
            print("! warning: prologue start node UNKNOWN_00 is not in physical disk")
        margin_bulge = float(margins.get("distance_to_bulge_ly", 0.0))
        margin_halo = float(margins.get("distance_to_halo_ly", 0.0))
        if margin_bulge < 100000.0 or margin_halo < 100000.0:
            print("! warning: prologue start node UNKNOWN_00 is too close to physical bulge/halo edge (<100k ly)")

    authored_ids = _authored_node_ids()
    proc_values: list[float] = []
    authored_count = 0
    procedural_count = 0
    by_region: dict[str, list[float]] = {}
    by_kind: dict[str, list[float]] = {}
    for node in state.world.space.nodes.values():
        is_authored = node.node_id in authored_ids
        if is_authored:
            authored_count += 1
            continue
        procedural_count += 1
        val = max(0.0, float(node.radiation_rad_per_s))
        proc_values.append(val)
        reg = node.region or region_for_pos(node.x_ly, node.y_ly, node.z_ly)
        by_region.setdefault(reg, []).append(val)
        by_kind.setdefault(node.kind or "unknown", []).append(val)
    print(f"- nodes: total={len(state.world.space.nodes)} authored={authored_count} procedural={procedural_count}")

    if proc_values:
        pmin = min(proc_values)
        pmax = max(proc_values)
        pavg = sum(proc_values) / len(proc_values)
        bands: dict[str, int] = {"low": 0, "elevated": 0, "high": 0, "extreme": 0}
        for v in proc_values:
            bands[_radiation_band_id(v)] += 1
        print(
            f"- procedural_rad_live: min={pmin:.4f} max={pmax:.4f} mean={pavg:.4f} rad/s "
            f"| low={bands['low']} elevated={bands['elevated']} high={bands['high']} extreme={bands['extreme']}"
        )
        for reg in sorted(by_region.keys()):
            vals = by_region[reg]
            avg = sum(vals) / len(vals)
            print(f"  region[{reg}]: n={len(vals)} mean={avg:.4f} min={min(vals):.4f} max={max(vals):.4f}")
        for kind in sorted(by_kind.keys()):
            vals = by_kind[kind]
            avg = sum(vals) / len(vals)
            print(f"  kind[{kind}]: n={len(vals)} mean={avg:.4f} min={min(vals):.4f} max={max(vals):.4f}")
    else:
        print("- procedural_rad_live: (no procedural nodes loaded)")

    templates = load_worldgen_templates()
    sector_states = sorted(state.world.sector_states.values(), key=lambda item: item.sector_id)
    if sector_states:
        archetype_counts: dict[str, int] = {}
        archetype_node_totals: dict[str, int] = {}
        archetype_inter_totals: dict[str, int] = {}
        dead_ends = 0
        single_exit = 0
        multi_exit = 0
        for sector_state in sector_states:
            archetype = sector_state.archetype or "unknown"
            archetype_counts[archetype] = archetype_counts.get(archetype, 0) + 1
            archetype_node_totals[archetype] = archetype_node_totals.get(archetype, 0) + len(sector_state.node_ids)
            archetype_inter_totals[archetype] = archetype_inter_totals.get(archetype, 0) + int(sector_state.intersector_link_count)
            if int(sector_state.intersector_link_count) <= 0:
                dead_ends += 1
            elif int(sector_state.intersector_link_count) == 1:
                single_exit += 1
            else:
                multi_exit += 1
        total_sector_nodes = sum(len(sector_state.node_ids) for sector_state in sector_states)
        print(
            f"- sector_archetypes: materialized={len(sector_states)} mean_nodes={total_sector_nodes/len(sector_states):.2f} "
            f"dead_ends={dead_ends} single_exit={single_exit} multi_exit={multi_exit}"
        )
        for archetype in sorted(archetype_counts):
            count = archetype_counts[archetype]
            print(
                f"  archetype[{archetype}]: sectors={count} "
                f"mean_nodes={archetype_node_totals[archetype]/count:.2f} "
                f"mean_intersector={archetype_inter_totals[archetype]/count:.2f}"
            )
    else:
        print("- sector_archetypes: (no materialized sectors)")

    weights = {k: float(v) for k, v in phys_region_counts.items() if k in {"bulge", "disk", "halo"} and float(v) > 0.0}
    if not weights:
        weights = {phys_region if phys_region in {"bulge", "disk", "halo"} else "disk": 1.0}
    total_w = sum(weights.values()) or 1.0
    acc: list[tuple[str, float]] = []
    running = 0.0
    for reg, w in sorted(weights.items()):
        running += w / total_w
        acc.append((reg, running))
    rng = random.Random(state.meta.rng_seed ^ 0xA5A5A5A5)
    syn_count = 4096
    syn_nodes_total = 0
    syn_playable_hub = 0
    syn_bins = {"0": 0, "1": 0, "2": 0, "3+": 0}
    syn_archetypes: dict[str, int] = {}
    for _ in range(syn_count):
        roll = rng.random()
        reg = acc[-1][0]
        for name, cutoff in acc:
            if roll <= cutoff:
                reg = name
                break
        tmpl = templates.get(reg) or templates.get("disk") or {}
        archetype = _weighted_choice(rng, tmpl.get("archetype_weights", {}) or {}) or "empty"
        cfg = archetypes.get(archetype) or archetypes.get("empty") or {}
        min_nodes = int(cfg.get("node_count_min", 0) or 0)
        max_nodes = int(cfg.get("node_count_max", 0) or 0)
        if max_nodes < min_nodes:
            max_nodes = min_nodes
        node_count = rng.randint(max(0, min_nodes), max(0, max_nodes))
        syn_nodes_total += node_count
        syn_archetypes[archetype] = syn_archetypes.get(archetype, 0) + 1
        if node_count <= 0:
            syn_bins["0"] += 1
        elif node_count == 1:
            syn_bins["1"] += 1
        elif node_count == 2:
            syn_bins["2"] += 1
        else:
            syn_bins["3+"] += 1
        hub_prob = max(0.0, min(1.0, float(cfg.get("playable_hub_prob", 0.0) or 0.0)))
        if rng.random() <= hub_prob:
            syn_playable_hub += 1
    archetype_txt = " ".join(
        f"{name}={100.0 * count / syn_count:.1f}%"
        for name, count in sorted(syn_archetypes.items())
    )
    print(
        "- sparse_synth[seed]: "
        f"mean_nodes={syn_nodes_total/syn_count:.2f} "
        f"zero={100.0*syn_bins['0']/syn_count:.1f}% "
        f"one={100.0*syn_bins['1']/syn_count:.1f}% "
        f"two={100.0*syn_bins['2']/syn_count:.1f}% "
        f"three_plus={100.0*syn_bins['3+']/syn_count:.1f}% "
        f"playable_hub={100.0*syn_playable_hub/syn_count:.1f}%"
    )
    print(f"  sparse_synth_archetypes: {archetype_txt or '-'}")


def render_debug_galaxy_map(state, scale: str | None) -> None:
    print("\n=== DEBUG GALAXY MAP ===")
    render_nav_map_galaxy(state, scale, include_all_loaded=True)
    sector_id = sector_id_for_pos(*state.world.current_pos_ly)
    sector_state = state.world.sector_states.get(sector_id)
    if sector_state and sector_state.archetype:
        print(f"- current_sector_archetype: {sector_state.archetype}")


def _yn(flag: bool) -> str:
    return "yes" if flag else "no"


def _counts_text(values: dict[str, int]) -> str:
    if not values:
        return "-"
    return " ".join(f"{key}={values[key]}" for key in sorted(values))


def _loaded_sector_node_ids(state, sector_id: str) -> list[str]:
    sector_state = state.world.sector_states.get(sector_id)
    if sector_state:
        return sorted(sector_state.node_ids)
    return sorted(
        node.node_id
        for node in state.world.space.nodes.values()
        if sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly) == sector_id
    )


def render_debug_worldgen_sector(state, sector_id: str) -> None:
    print("\n=== DEBUG WORLDGEN SECTOR ===")
    coords = _sector_coords_from_id(sector_id)
    if coords is None:
        print(f"- invalid_sector_id: {sector_id}")
        return

    before_generated = set(state.world.generated_sectors)
    ensure_sector_generated(state, sector_id)
    after_generated = set(state.world.generated_sectors)
    generated_now = sector_id not in before_generated and sector_id in after_generated
    cluster_generated = sorted(after_generated - before_generated)

    center = _sector_center_ly(sector_id)
    sx, sy, sz = coords
    origin = (sx * SECTOR_SIZE_LY, sy * SECTOR_SIZE_LY, sz * SECTOR_SIZE_LY)
    op_region = _sector_region_operational(sector_id)
    phys_region = _sector_region_physical(sector_id)
    sector_state = state.world.sector_states.get(sector_id)
    archetypes = load_worldgen_archetypes()
    authored_ids = _authored_node_ids()
    node_ids = _loaded_sector_node_ids(state, sector_id)
    nodes = [state.world.space.nodes[node_id] for node_id in node_ids if node_id in state.world.space.nodes]
    authored_count = sum(1 for node_id in node_ids if node_id in authored_ids)
    procedural_count = max(0, len(node_ids) - authored_count)

    placements_by_node: dict[str, list[str]] = {}
    for piece_key, node_id in sorted(state.world.lore_placements.piece_to_node.items()):
        channel = state.world.lore_placements.piece_channel_bindings.get(piece_key, "-")
        status = "delivered" if piece_key in state.world.lore.delivered else "pending"
        placements_by_node.setdefault(node_id, []).append(f"{piece_key}@{channel}[{status}]")

    intel_refs = [
        item
        for item in state.world.intel
        if item.sector_id == sector_id
        or item.from_id in node_ids
        or item.to_id in node_ids
        or (item.coord and sector_id_for_pos(*item.coord) == sector_id)
    ]
    intel_by_kind: dict[str, int] = {}
    for item in intel_refs:
        intel_by_kind[item.kind] = intel_by_kind.get(item.kind, 0) + 1

    force_hidden = sorted(node_id for node_id in node_ids if node_id in state.world.forced_hidden_nodes)
    pool_nodes = sorted(node_id for node_id in node_ids if node_id in state.world.node_pools)
    dead_nodes = sorted(node_id for node_id in node_ids if node_id in state.world.dead_nodes)

    print(
        f"- sector={sector_id} generated_now={_yn(generated_now)} "
        f"cluster_generated={_map_preview(cluster_generated, max_items=12)}"
    )
    if center is not None:
        print(
            f"- geometry: origin=({origin[0]:.2f},{origin[1]:.2f},{origin[2]:.2f}) "
            f"center=({center[0]:.2f},{center[1]:.2f},{center[2]:.2f})"
        )
    print(f"- region: operational={op_region} physical={phys_region}")

    if sector_state:
        archetype_cfg = archetypes.get(sector_state.archetype, {})
        caps = archetype_cfg.get("kind_caps", {}) or {}
        forbidden = sorted(str(item) for item in (archetype_cfg.get("forbidden_kinds", []) or []))
        caps_txt = ",".join(f"{kind}:{int(caps[kind])}" for kind in sorted(caps)) or "-"
        forbidden_txt = ",".join(forbidden) or "-"
        print(
            f"- sector_state: archetype={sector_state.archetype or '-'} nodes={len(node_ids)} "
            f"authored={authored_count} procedural={procedural_count}"
        )
        print(
            f"- hubs: topology={sector_state.topology_hub_node_id or '-'} "
            f"playable={sector_state.playable_hub_node_id or '-'}"
        )
        print(
            f"- budgets: internal_links={int(sector_state.internal_link_count)} "
            f"intersector_links={int(sector_state.intersector_link_count)}/"
            f"{int(archetype_cfg.get('intersector_link_max', 0) or 0)} "
            f"playable_hub_prob={float(archetype_cfg.get('playable_hub_prob', 0.0) or 0.0):.2f} "
            f"intersector_link_prob={float(archetype_cfg.get('intersector_link_prob', 0.0) or 0.0):.2f} "
            f"extra_internal_link_prob={float(archetype_cfg.get('extra_internal_link_prob', 0.0) or 0.0):.2f}"
        )
        print(f"- rules: caps={caps_txt} forbidden={forbidden_txt}")
    else:
        print("- sector_state: (missing)")

    print(
        f"- overlays: lore_bindings={sum(len(v) for v in placements_by_node.values())} "
        f"node_pools={len(pool_nodes)} intel_refs={len(intel_refs)} "
        f"forced_hidden={len(force_hidden)} dead_nodes={len(dead_nodes)}"
    )
    if intel_by_kind:
        print(f"  intel_by_kind: {_counts_text(intel_by_kind)}")

    neighbors = [sid for sid in _neighbor_sectors_2d(sector_id) if sid != sector_id]
    if neighbors:
        print("- local_ring:")
        for neighbor_id in sorted(neighbors):
            neighbor_state = state.world.sector_states.get(neighbor_id)
            if neighbor_state:
                print(
                    f"  {neighbor_id}: archetype={neighbor_state.archetype or '-'} "
                    f"nodes={len(neighbor_state.node_ids)} "
                    f"playable_hub={neighbor_state.playable_hub_node_id or '-'} "
                    f"intersector_links={int(neighbor_state.intersector_link_count)}"
                )
            else:
                print(f"  {neighbor_id}: (not materialized)")

    if not nodes:
        print("- nodes: (none)")
        return

    print("- nodes:")
    for node in nodes:
        marker = "*" if node.node_id == state.world.current_node_id else ""
        internal_links: list[str] = []
        intersector_links: list[str] = []
        for dest_id in sorted(node.links):
            dest = state.world.space.nodes.get(dest_id)
            if not dest:
                continue
            dest_sector = sector_id_for_pos(dest.x_ly, dest.y_ly, dest.z_ly)
            if dest_sector == sector_id:
                internal_links.append(dest_id)
            else:
                intersector_links.append(dest_id)
        known_links = sorted(
            dest_id for dest_id in state.world.known_links.get(node.node_id, set()) if dest_id in state.world.space.nodes
        )
        pool = state.world.node_pools.get(node.node_id)
        lore_items = placements_by_node.get(node.node_id, [])
        print(
            f"  - {node.node_id}{marker} ({node.name}, {node.kind}) "
            f"authored={_yn(node.node_id in authored_ids)} "
            f"known_node={_yn(node.node_id in state.world.known_nodes)} "
            f"known_contact={_yn(node.node_id in state.world.known_contacts)} "
            f"visited={_yn(node.node_id in state.world.visited_nodes)} "
            f"hidden={_yn(node.node_id in state.world.forced_hidden_nodes)} "
            f"deadnode={_yn(node.node_id in state.world.dead_nodes)}"
        )
        print(
            f"    pos=({node.x_ly:.2f},{node.y_ly:.2f},{node.z_ly:.2f}) "
            f"rad={float(node.radiation_rad_per_s):.4f} "
            f"playable_hub={_yn(node.is_hub)} topology_hub={_yn(node.is_topology_hub)}"
        )
        print(
            f"    salvage: scrap={int(getattr(node, 'salvage_scrap_available', 0) or 0)} "
            f"modules={len(getattr(node, 'salvage_modules_available', []) or [])} "
            f"drones={int(getattr(node, 'recoverable_drones_count', 0) or 0)}"
        )
        if pool:
            print(
                f"    pool: window_open={_yn(pool.window_open)} node_cleaned={_yn(pool.node_cleaned)} "
                f"scrap_complete={_yn(pool.scrap_complete)} data_complete={_yn(pool.data_complete)} "
                f"extras_complete={_yn(pool.extras_complete)} uplink_data_consumed={_yn(pool.uplink_data_consumed)}"
            )
        if lore_items:
            print(f"    lore: {_map_preview(sorted(lore_items), max_items=8)}")
        print(f"    links_internal: {_map_preview(internal_links, max_items=12)}")
        print(f"    links_intersector: {_map_preview(intersector_links, max_items=12)}")
        print(f"    known_links: {_map_preview(known_links, max_items=12)}")


def render_debug_graph_all(state) -> None:
    print("\n=== DEBUG GRAPH ALL ===")
    ship_id = getattr(state.ship, "ship_id", "RETORNO_SHIP")
    authored_ids = _authored_node_ids()
    all_nodes = sorted(
        [node for node in state.world.space.nodes.values() if node.node_id != ship_id],
        key=lambda node: (sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly), node.node_id),
    )
    all_node_ids = {node.node_id for node in all_nodes}
    physical_adj: dict[str, set[str]] = {node.node_id: set() for node in all_nodes}
    known_adj: dict[str, set[str]] = {node.node_id: set() for node in all_nodes}

    for node in all_nodes:
        for dest_id in node.links:
            if dest_id in all_node_ids and dest_id != node.node_id:
                physical_adj[node.node_id].add(dest_id)
    for src, dests in state.world.known_links.items():
        if src not in known_adj:
            continue
        for dst in dests:
            if dst in known_adj and dst != src:
                known_adj[src].add(dst)

    physical_edges: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for src, dests in sorted(physical_adj.items()):
        for dst in sorted(dests):
            edge = tuple(sorted((src, dst)))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            physical_edges.append(edge)

    known_edges: list[tuple[str, str]] = []
    seen_known_edges: set[tuple[str, str]] = set()
    for src, dests in sorted(known_adj.items()):
        for dst in sorted(dests):
            edge = tuple(sorted((src, dst)))
            if edge in seen_known_edges:
                continue
            seen_known_edges.add(edge)
            known_edges.append(edge)

    sector_ids: set[str] = set(state.world.generated_sectors)
    for node in all_nodes:
        sector_ids.add(sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly))
    sector_ids = {sid for sid in sector_ids if sid}

    kind_counts: dict[str, int] = {}
    for node in all_nodes:
        kind_counts[node.kind] = kind_counts.get(node.kind, 0) + 1
    archetype_counts: dict[str, int] = {}
    for sector_state in state.world.sector_states.values():
        archetype = sector_state.archetype or "unknown"
        archetype_counts[archetype] = archetype_counts.get(archetype, 0) + 1

    physical_components = _map_component_count(all_node_ids, physical_adj) if all_node_ids else 0
    known_components = _map_component_count(all_node_ids, known_adj) if all_node_ids else 0
    playable_hubs = sum(1 for node in all_nodes if node.is_hub)
    topology_hubs = sum(1 for node in all_nodes if node.is_topology_hub)
    authored_count = sum(1 for node in all_nodes if node.node_id in authored_ids)
    procedural_count = max(0, len(all_nodes) - authored_count)
    dead_end_sectors = sum(
        1 for sector_state in state.world.sector_states.values() if int(sector_state.intersector_link_count) <= 0
    )
    print(
        f"- totals: materialized_sectors={len(sector_ids)} nodes={len(all_nodes)} "
        f"physical_edges={len(physical_edges)} known_edges={len(known_edges)} "
        f"physical_components={physical_components} known_components={known_components}"
    )
    print(
        f"- composition: authored={authored_count} procedural={procedural_count} "
        f"playable_hubs={playable_hubs} topology_hubs={topology_hubs} "
        f"forced_hidden={len(state.world.forced_hidden_nodes)} node_pools={len(state.world.node_pools)} "
        f"intel={len(state.world.intel)} lore_placements={len(state.world.lore_placements.piece_to_node)} "
        f"dead_nodes={len(state.world.dead_nodes)} dead_end_sectors={dead_end_sectors}"
    )
    print(f"- by_kind: {_counts_text(kind_counts)}")
    print(f"- by_archetype: {_counts_text(archetype_counts)}")

    print("- sectors:")
    for sector_id in sorted(sector_ids):
        node_ids = _loaded_sector_node_ids(state, sector_id)
        sector_state = state.world.sector_states.get(sector_id)
        authored_sector = sum(1 for node_id in node_ids if node_id in authored_ids)
        known_sector = sum(1 for node_id in node_ids if node_id in state.world.known_nodes or node_id in state.world.known_contacts)
        print(
            f"  - {sector_id}: archetype={(sector_state.archetype if sector_state else '-') or '-'} "
            f"nodes={len(node_ids)} authored={authored_sector} known={known_sector} "
            f"topology_hub={(sector_state.topology_hub_node_id if sector_state else '-') or '-'} "
            f"playable_hub={(sector_state.playable_hub_node_id if sector_state else '-') or '-'} "
            f"intersector_links={int(sector_state.intersector_link_count) if sector_state else 0}"
        )

    print("- nodes:")
    if not all_nodes:
        print("  (none)")
    for node in all_nodes:
        sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
        phys_links = sorted(physical_adj.get(node.node_id, set()))
        known_links = sorted(known_adj.get(node.node_id, set()))
        marker = "*" if node.node_id == state.world.current_node_id else ""
        print(
            f"  - {node.node_id}{marker}: sector={sector_id} kind={node.kind} "
            f"authored={_yn(node.node_id in authored_ids)} "
            f"known={_yn(node.node_id in state.world.known_nodes or node.node_id in state.world.known_contacts)} "
            f"visited={_yn(node.node_id in state.world.visited_nodes)} "
            f"hidden={_yn(node.node_id in state.world.forced_hidden_nodes)} "
            f"playable_hub={_yn(node.is_hub)} topology_hub={_yn(node.is_topology_hub)} "
            f"degree_phys={len(phys_links)} degree_known={len(known_links)}"
        )
        print(f"    links_phys: {_map_preview(phys_links, max_items=14)}")
        print(f"    links_known: {_map_preview(known_links, max_items=14)}")

    print("- physical_edges:")
    if not physical_edges:
        print("  (none)")
    for left_id, right_id in physical_edges:
        left = state.world.space.nodes.get(left_id)
        right = state.world.space.nodes.get(right_id)
        left_sector = sector_id_for_pos(left.x_ly, left.y_ly, left.z_ly) if left else "-"
        right_sector = sector_id_for_pos(right.x_ly, right.y_ly, right.z_ly) if right else "-"
        edge_type = "internal" if left_sector == right_sector else "intersector"
        dist = distance_between_nodes_ly(state.world, left_id, right_id)
        known = right_id in known_adj.get(left_id, set()) or left_id in known_adj.get(right_id, set())
        print(
            f"  - {left_id} <-> {right_id} "
            f"dist={(dist or 0.0):.2f}ly type={edge_type} known={_yn(known)}"
        )


def _next_debug_drone_id(state) -> str:
    max_idx = 0
    for drone_id in state.ship.drones.keys():
        if not drone_id.startswith("D"):
            continue
        suffix = drone_id[1:]
        if not suffix.isdigit():
            continue
        max_idx = max(max_idx, int(suffix))
    candidate = max_idx + 1
    while f"D{candidate}" in state.ship.drones:
        candidate += 1
    return f"D{candidate}"


def debug_add_scrap(state, amount: int) -> None:
    amount = int(amount)
    if amount <= 0:
        print("debug add scrap: amount must be > 0")
        return
    state.ship.cargo_scrap += amount
    state.ship.manifest_dirty = True
    print(f"debug add scrap: +{amount} (cargo_scrap={state.ship.cargo_scrap})")


def debug_add_module(state, module_id: str, count: int = 1) -> None:
    count = int(count)
    if count <= 0:
        print("debug add module: count must be > 0")
        return
    modules = load_modules()
    if module_id not in modules:
        print(f"debug add module: unknown module_id '{module_id}'")
        return
    for _ in range(count):
        state.ship.cargo_modules.append(module_id)
    state.ship.manifest_dirty = True
    print(f"debug add module: +{count} {module_id} (inventory_count={state.ship.cargo_modules.count(module_id)})")


def debug_add_drones(state, count: int = 1) -> None:
    count = int(count)
    if count <= 0:
        print("debug add drone: count must be > 0")
        return
    created: list[str] = []
    for _ in range(count):
        drone_id = _next_debug_drone_id(state)
        state.ship.drones[drone_id] = DroneState(
            drone_id=drone_id,
            name=f"Drone-{drone_id[1:].zfill(2)}",
            status=DroneStatus.DOCKED,
            location=DroneLocation(kind="ship_sector", id="drone_bay"),
            shield_factor=0.9,
            battery=1.0,
            integrity=1.0,
        )
        created.append(drone_id)
    print(f"debug add drone: created {len(created)} -> {', '.join(created)}")


def _known_contact_cache_ids(state) -> set[str]:
    known = state.world.known_nodes if hasattr(state.world, "known_nodes") and state.world.known_nodes else state.world.known_contacts
    return set(known)


def _contact_distance_text(state, node: SpaceNode, current_pos: tuple[float, float, float]) -> tuple[float, str]:
    x, y, z = current_pos
    dx = node.x_ly - x
    dy = node.y_ly - y
    dz = node.z_ly - z
    dist = (dx * dx + dy * dy + dz * dz) ** 0.5
    if node.node_id in state.world.fine_ranges_km and dist <= Balance.LOCAL_TRAVEL_RADIUS_LY:
        km = state.world.fine_ranges_km.get(node.node_id, 0.0)
        locale = state.os.locale.value
        if locale == "en":
            return dist, f"{_format_large_distance(km * 0.621371)}mi"
        return dist, f"{_format_large_distance(km)}km"
    if dist < 0.1:
        return dist, f"{dist:.4f}ly"
    if dist < 1.0:
        return dist, f"{dist:.3f}ly"
    return dist, f"{dist:.2f}ly"


def _collect_known_contact_entries(state) -> list[dict[str, object]]:
    current_id = state.world.current_node_id
    known = _known_contact_cache_ids(state)
    current = state.world.space.nodes.get(current_id)
    if current:
        x, y, z = current.x_ly, current.y_ly, current.z_ly
    else:
        x, y, z = state.world.current_pos_ly
    routes = state.world.known_links.get(current_id, set())
    current_pos = (x, y, z)
    entries: list[dict[str, object]] = []
    for cid in sorted(known):
        node = state.world.space.nodes.get(cid)
        if node:
            sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
            region = node.region or region_for_pos(node.x_ly, node.y_ly, node.z_ly)
            sector_center = _sector_center_ly(sector_id)
            sector_dist = float("inf")
            if sector_center is not None:
                sx, sy, sz = sector_center
                dx = sx - x
                dy = sy - y
                dz = sz - z
                sector_dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            dist, dist_txt = _contact_distance_text(state, node, current_pos)
            visited = "visited" if cid in state.world.visited_nodes else "unvisited"
            # Current location is always directly reachable (no self-link is stored).
            route_flag = "route" if cid == current_id or cid in routes else "no_route"
            entries.append({
                "cid": cid,
                "name": node.name,
                "kind": node.kind,
                "sector_id": sector_id,
                "region": region,
                "sector_dist": sector_dist,
                "dist": dist,
                "dist_txt": dist_txt,
                "route_flag": route_flag,
                "visited": visited,
                "node_present": True,
            })
        else:
            entries.append({
                "cid": cid,
                "name": cid,
                "kind": "?",
                "sector_id": "?",
                "region": "unknown",
                "sector_dist": float("inf"),
                "dist": float("inf"),
                "dist_txt": "?",
                "route_flag": "no_route",
                "visited": "unvisited",
                "node_present": False,
            })
    entries.sort(key=lambda item: (
        float(item["sector_dist"]),
        str(item["sector_id"]),
        float(item["dist"]),
        str(item["cid"]),
    ))
    return entries


def _render_contacts_table(state) -> None:
    if state.ship.in_transit:
        locale = state.os.locale.value
        msg = {
            "en": "contacts: in transit; showing cached known contacts only",
            "es": "contacts: en tránsito; mostrando solo contactos conocidos en caché",
        }
        print(msg.get(locale, msg["en"]))
    print("\n=== CONTACTS ===")
    entries = _collect_known_contact_entries(state)
    if not entries:
        print("(no signals detected)")
        return
    for entry in entries:
        if not bool(entry["node_present"]):
            print(f"- {entry['cid']}")
            continue
        print(
            f"- {entry['name']} ({entry['kind']}) "
            f"sector={entry['sector_id']} region={entry['region']} "
            f"id={entry['cid']} dist={entry['dist_txt']} {entry['route_flag']} {entry['visited']}"
        )


def _render_contact_sectors_table(state) -> None:
    if state.ship.in_transit:
        locale = state.os.locale.value
        msg = {
            "en": "contacts sector: in transit; showing cached known contacts only",
            "es": "contacts sector: en tránsito; mostrando solo contactos conocidos en caché",
        }
        print(msg.get(locale, msg["en"]))
    print("\n=== CONTACT SECTORS ===")
    entries = _collect_known_contact_entries(state)
    if not entries:
        print("(none)")
        return

    grouped: dict[str, dict[str, object]] = {}
    for entry in entries:
        sector_id = str(entry["sector_id"])
        if sector_id not in grouped:
            grouped[sector_id] = {
                "sector_id": sector_id,
                "region": entry["region"],
                "sector_dist": entry["sector_dist"],
                "contacts": [],
            }
        grouped[sector_id]["contacts"].append(str(entry["cid"]))

    ordered = sorted(
        grouped.values(),
        key=lambda item: (float(item["sector_dist"]), str(item["sector_id"])),
    )
    for item in ordered:
        contacts_txt = ", ".join(sorted(set(item["contacts"])))
        sector_dist = item["sector_dist"]
        sector_dist_txt = "?" if sector_dist == float("inf") else f"{float(sector_dist):.2f}ly"
        print(
            f"- {item['sector_id']} region={item['region']} sector_dist={sector_dist_txt} "
            f"contacts=({contacts_txt})"
        )


def render_nav_contacts(state, map_arg: str | None = None) -> None:
    if map_arg == "sector":
        _render_contact_sectors_table(state)
        return
    _render_contacts_table(state)


def render_contacts(state) -> None:
    # Legacy wrapper used by tests and old call sites.
    render_nav_contacts(state)


def render_scan_results(state, node_ids: list[str]) -> None:
    print("\n=== SCAN ===")
    if not node_ids:
        print("(no signals detected)")
        return
    for cid in sorted(node_ids):
        node = state.world.space.nodes.get(cid)
        if node:
            sector = ""
            if node.node_id.startswith("S"):
                sector = f" sector={node.node_id.split(':', 1)[0]}"
            print(f"- {node.name} ({node.kind}){sector} id={cid}")
        else:
            print(f"- {cid}")


def _scan_and_discover(state) -> tuple[list[str], list[str], list[str], list[str], str | None]:
    engine = Engine()
    blocked = engine._scan_blocked_event(state)
    if blocked is not None:
        return [], [], [], [], blocked.message
    seen, discovered, fine_range_updates = engine._perform_scan(state)
    route_msgs: list[str] = []
    locale = state.os.locale.value
    for update in fine_range_updates:
        node_id = str(update.get("node_id", "?"))
        fine_km = float(update.get("distance_km", 0.0) or 0.0)
        if locale == "en":
            dist_txt = f"{_format_large_distance(fine_km * 0.621371)}mi"
            route_msgs.append(f"[INFO] (scan) fine range fixed: {node_id} ({dist_txt})")
        else:
            dist_txt = f"{_format_large_distance(fine_km)}km"
            route_msgs.append(f"[INFO] (scan) distancia fina fijada: {node_id} ({dist_txt})")
    return seen, discovered, [], route_msgs, None


def _hash64(seed: int, text: str) -> int:
    import hashlib
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode("utf-8"))
    h.update(text.encode("utf-8"))
    return int.from_bytes(h.digest(), "big", signed=False)


def _format_large_distance(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.2f}k"
    return f"{value:.0f}"


def _compute_fine_range_km(state, from_id: str, to_id: str) -> float:
    a, b = sorted([from_id, to_id])
    seed = _hash64(state.meta.rng_seed, f"fine:{a}:{b}")
    t = (seed % 10_000) / 10_000.0
    return Balance.LOCAL_TRAVEL_MIN_KM + (Balance.LOCAL_TRAVEL_MAX_KM - Balance.LOCAL_TRAVEL_MIN_KM) * t


def _maybe_set_fine_range(state, from_id: str, to_id: str) -> float | None:
    if to_id in state.world.fine_ranges_km:
        return None
    from_node = state.world.space.nodes.get(from_id)
    to_node = state.world.space.nodes.get(to_id)
    if not from_node or not to_node:
        return None
    if sector_id_for_pos(from_node.x_ly, from_node.y_ly, from_node.z_ly) != sector_id_for_pos(
        to_node.x_ly, to_node.y_ly, to_node.z_ly
    ):
        return None
    dx = to_node.x_ly - from_node.x_ly
    dy = to_node.y_ly - from_node.y_ly
    dz = to_node.z_ly - from_node.z_ly
    dist_ly = (dx * dx + dy * dy + dz * dz) ** 0.5
    if dist_ly > Balance.LOCAL_TRAVEL_RADIUS_LY:
        return None
    fine_km = _compute_fine_range_km(state, from_id, to_id)
    state.world.fine_ranges_km[to_id] = fine_km
    return fine_km


def _state_rank(state: SystemState) -> int:
    order = {
        SystemState.OFFLINE: 0,
        SystemState.CRITICAL: 1,
        SystemState.DAMAGED: 2,
        SystemState.LIMITED: 3,
        SystemState.NOMINAL: 4,
        SystemState.UPGRADED: 5,
    }
    return order[state]


def _authored_node_ids() -> set[str]:
    node_ids: set[str] = set()
    for loc in load_locations():
        node_cfg = loc.get("node", {})
        node_id = node_cfg.get("node_id")
        if node_id:
            node_ids.add(node_id)
    return node_ids


_GALAXY_MAP_SCALES: dict[str, float] = {
    "sector": 10.0,
    "local": 100.0,
    "regional": 10000.0,
    "global": 500000.0,
}


def _normalize_galaxy_scale(scale: str | None) -> str:
    if not scale:
        return "global"
    name = str(scale).strip().lower()
    if name in _GALAXY_MAP_SCALES:
        return name
    return "global"


def _node_symbol_rank(node: SpaceNode, authored_ids: set[str]) -> tuple[int, int]:
    kind_rank = {
        "relay": 60,
        "waystation": 60,
        "hub": 60,
        "station": 50,
        "derelict": 40,
        "ship": 40,
        "wreck": 40,
    }
    authored_bonus = 1 if node.node_id in authored_ids else 0
    return kind_rank.get((node.kind or "").lower(), 20), authored_bonus


def _stable_cell_tiebreak(seed: int, scale: str, gx: int, gy: int, node_id: str) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode("utf-8"))
    h.update(scale.encode("utf-8"))
    h.update(f"{gx}:{gy}".encode("utf-8"))
    h.update(node_id.encode("utf-8"))
    return int.from_bytes(h.digest(), "big", signed=False)


def _try_add_known_link_with_cap(
    state,
    from_id: str,
    to_id: str,
    *,
    bidirectional: bool = False,
) -> tuple[bool, bool, float | None]:
    if not from_id or not to_id or from_id == to_id:
        return False, False, None
    dist = distance_between_nodes_ly(state.world, from_id, to_id)
    if not is_hop_within_cap(state.world, from_id, to_id):
        return False, True, dist
    added = add_known_link(state.world, from_id, to_id, bidirectional=bidirectional)
    return added, False, dist

def _core_os_limited_blocks(parsed) -> bool:
    if parsed == "UPLINK":
        return True
    if isinstance(parsed, RouteSolve):
        return True
    if isinstance(parsed, AuthRecover):
        return True
    return False


def _core_os_damaged_blocks(parsed) -> bool:
    if _core_os_limited_blocks(parsed):
        return True
    return parsed.__class__.__name__ == "Travel"


def _terminal_state_allows(parsed) -> bool:
    if parsed in {"HELP", "HELP_VERBOSE", "HELP_NO_VERBOSE", "EXIT", "CLEAR"}:
        return True
    if isinstance(parsed, Status):
        return True
    if isinstance(parsed, str) and parsed in {"LOGS", "ALERTS", "JOBS"}:
        return True
    if isinstance(parsed, tuple):
        token = parsed[0]
        if token in {
            "LOG_COPY",
            "ALERTS_EXPLAIN",
            "JOBS",
            "DEBUG",
            "DEBUG_ARCS",
            "DEBUG_LORE",
            "DEBUG_DEADNODES",
            "DEBUG_MODULES",
            "DEBUG_GALAXY",
            "DEBUG_GALAXY_MAP",
            "DEBUG_WORLDGEN_SECTOR",
            "DEBUG_GRAPH_ALL",
            "DEBUG_SEED",
            "DEBUG_SCENARIO",
        }:
            return True
    return False


def _command_blocked_message(state, parsed) -> str | None:
    core_os = state.ship.systems.get("core_os")
    life_support = state.ship.systems.get("life_support")
    locale = state.os.locale.value
    messages = {
        "terminal": {
            "en": "Core OS offline. Terminal control lost.",
            "es": "Core OS fuera de línea. Control de terminal perdido.",
        },
        "core_os_critical": {
            "en": "Core OS degraded: emergency recovery command set active",
            "es": "Core OS degradado: set de recuperación de emergencia activo",
        },
        "core_os_limited": {
            "en": "Core OS degraded: advanced commands blocked.",
            "es": "Core OS degradado: comandos avanzados bloqueados.",
        },
        "core_os_damaged": {
            "en": "Core OS damaged: advanced commands blocked; navigation travel blocked.",
            "es": "Core OS dañado: comandos avanzados bloqueados; viaje de navegación bloqueado.",
        },
        "life_support_offline": {
            "en": "Life support offline. Host viability lost.",
            "es": "Soporte vital fuera de línea. Viabilidad del huésped perdida.",
        },
    }

    if state.os.terminal_lock:
        if not _terminal_state_allows(parsed):
            reason = state.os.terminal_reason or "terminal"
            if reason == "life_support_offline":
                return messages["life_support_offline"].get(locale, messages["life_support_offline"]["en"])
            return messages["terminal"].get(locale, messages["terminal"]["en"])
        return None
    if core_os and core_os.state == SystemState.OFFLINE:
        if not _terminal_state_allows(parsed):
            return messages["terminal"].get(locale, messages["terminal"]["en"])
        return None
    if core_os and core_os.state == SystemState.CRITICAL:
        if parsed == "UPLINK" or isinstance(parsed, Hibernate):
            return messages["core_os_critical"].get(locale, messages["core_os_critical"]["en"])
        if not isinstance(parsed, Action) and not is_parsed_command_allowed_in_core_os_critical(parsed):
            return messages["core_os_critical"].get(locale, messages["core_os_critical"]["en"])
    if core_os and core_os.state == SystemState.LIMITED:
        if _core_os_limited_blocks(parsed):
            return messages["core_os_limited"].get(locale, messages["core_os_limited"]["en"])
    if core_os and core_os.state == SystemState.DAMAGED:
        if _core_os_damaged_blocks(parsed):
            return messages["core_os_damaged"].get(locale, messages["core_os_damaged"]["en"])
    return None


def _hibernate_blocked_message(state) -> str | None:
    locale = state.os.locale.value
    q = state.ship.power.power_quality
    life_support = state.ship.systems.get("life_support")
    if state.ship.power.brownout:
        msg = {
            "en": "Hibernate blocked: brownout active",
            "es": "Hibernación bloqueada: brownout activo",
        }
        return msg.get(locale, msg["en"])
    if q < Balance.POWER_QUALITY_CRITICAL_THRESHOLD:
        msg = {
            "en": f"Hibernate blocked: power quality too low (Q={q:.2f}, requires >= {Balance.POWER_QUALITY_CRITICAL_THRESHOLD:.2f})",
            "es": f"Hibernación bloqueada: calidad de energía demasiado baja (Q={q:.2f}, requiere >= {Balance.POWER_QUALITY_CRITICAL_THRESHOLD:.2f})",
        }
        return msg.get(locale, msg["en"])
    if life_support and life_support.state in {SystemState.LIMITED, SystemState.CRITICAL, SystemState.OFFLINE}:
        msg = {
            "en": "Hibernate blocked: life_support degraded",
            "es": "Hibernación bloqueada: soporte vital degradado",
        }
        return msg.get(locale, msg["en"])
    return None


def _hibernate_soc_warning(state) -> str | None:
    soc = (state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh) if state.ship.power.e_batt_max_kwh else 0.0
    locale = state.os.locale.value
    if 0.10 <= soc < 0.25:
        msg = {
            "en": f"[WARN] Battery critical: SoC={soc:.2f}. Hibernate may be unsafe.",
            "es": f"[WARN] Batería crítica: SoC={soc:.2f}. Hibernar puede ser inseguro.",
        }
        return msg.get(locale, msg["en"])
    if 0.25 <= soc < 0.50:
        msg = {
            "en": f"[INFO] Battery low: SoC={soc:.2f}. Consider reducing load.",
            "es": f"[INFO] Batería baja: SoC={soc:.2f}. Considera reducir carga.",
        }
        return msg.get(locale, msg["en"])
    return None


def _handle_uplink(state) -> None:
    reason = uplink_blocked_reason(state)
    locale = state.os.locale.value
    q = state.ship.power.power_quality
    soc = (state.ship.power.e_batt_kwh / state.ship.power.e_batt_max_kwh) if state.ship.power.e_batt_max_kwh else 0.0
    if 0.10 <= soc < 0.25:
        warn = {
            "en": f"[WARN] Battery critical: SoC={soc:.2f}. Uplink may be unsafe.",
            "es": f"[WARN] Batería crítica: SoC={soc:.2f}. Uplink puede ser inseguro.",
        }
        print(warn.get(locale, warn["en"]))
    elif 0.25 <= soc < 0.50:
        warn = {
            "en": f"[INFO] Battery low: SoC={soc:.2f}. Consider reducing load.",
            "es": f"[INFO] Batería baja: SoC={soc:.2f}. Considera reducir carga.",
        }
        print(warn.get(locale, warn["en"]))
    blocked = {
        "en": {
            "in_transit": "Uplink blocked: ship in transit.",
            "brownout_active": "Uplink blocked: brownout active.",
            "power_quality_low": f"Uplink blocked: power quality too low (Q={q:.2f}, requires >= {Balance.POWER_QUALITY_BLOCK_THRESHOLD:.2f}).",
            "power_quality_collapse": f"Uplink blocked: power quality collapse (Q={q:.2f}, requires >= {Balance.POWER_QUALITY_COLLAPSE_THRESHOLD:.2f}).",
            "not_docked": "Uplink blocked: ship not docked.",
            "not_relay": "Uplink blocked: current node is not a relay/waystation/station.",
            "missing_data_core": "Uplink blocked: data_core missing.",
            "data_core_shed": "Uplink blocked: data_core offline. Try: power on data_core; boot datad",
            "data_core_offline": "Uplink blocked: data_core offline.",
            "datad_not_installed": "Uplink blocked: datad not installed.",
            "datad_not_running": "Uplink blocked: datad not running. Try: boot datad",
            "data_core_degraded": "Uplink blocked: data_core degraded (requires >= limited).",
        },
        "es": {
            "in_transit": "Uplink bloqueado: nave en tránsito.",
            "brownout_active": "Uplink bloqueado: brownout activo.",
            "power_quality_low": f"Uplink bloqueado: calidad de energía demasiado baja (Q={q:.2f}, requiere >= {Balance.POWER_QUALITY_BLOCK_THRESHOLD:.2f}).",
            "power_quality_collapse": f"Uplink bloqueado: colapso de calidad de energía (Q={q:.2f}, requiere >= {Balance.POWER_QUALITY_COLLAPSE_THRESHOLD:.2f}).",
            "not_docked": "Uplink bloqueado: nave no está docked.",
            "not_relay": "Uplink bloqueado: el nodo actual no es relay/waystation/estación.",
            "missing_data_core": "Uplink bloqueado: falta data_core.",
            "data_core_shed": "Uplink bloqueado: data_core offline. Prueba: power on data_core; boot datad",
            "data_core_offline": "Uplink bloqueado: data_core offline.",
            "datad_not_installed": "Uplink bloqueado: datad no instalado.",
            "datad_not_running": "Uplink bloqueado: datad no está en ejecución. Prueba: boot datad",
            "data_core_degraded": "Uplink bloqueado: data_core degradado (requiere >= limited).",
        },
    }
    if reason:
        print(blocked.get(locale, blocked["en"]).get(reason, blocked["en"]["not_relay"]))
        return
    sync_node_pools_for_known_nodes(state)
    current_node_id = state.world.current_node_id
    pool = state.world.node_pools.get(current_node_id)
    if pool and pool.uplink_data_consumed:
        msg = {
            "en": "uplink_complete :: node data already exhausted",
            "es": "uplink_complete :: datos del nodo ya agotados",
        }
        print(msg.get(locale, msg["en"]))
        events_out: list[tuple[str, Event]] = []
        _emit_runtime_event(
            state,
            events_out,
            "cmd",
            EventType.UPLINK_COMPLETE,
            Severity.INFO,
            SourceRef(kind="ship_system", id="data_core"),
            msg.get(locale, msg["en"]),
            data={"routes": []},
        )
        return
    fixed_pool = list(pool.uplink_route_pool) if pool else []
    added: list[str] = []
    discarded_by_cap = 0
    for dest in fixed_pool:
        if not dest or dest == current_node_id:
            continue
        added_link, blocked_by_cap, _ = _try_add_known_link_with_cap(
            state, current_node_id, dest, bidirectional=True
        )
        if blocked_by_cap:
            discarded_by_cap += 1
            continue
        if added_link:
            added.append(dest)
        state.world.known_nodes.add(dest)
        state.world.known_contacts.add(dest)
    if added:
        state.world.mobility_no_new_uplink_count = 0
    else:
        state.world.mobility_no_new_uplink_count += 1

    if added:
        for nid in added:
            record_intel(
                state.world,
                t=state.clock.t,
                kind="link",
                from_id=current_node_id,
                to_id=nid,
                confidence=0.9,
                source_kind="uplink",
                source_ref=current_node_id,
            )
    if "/logs/nav" not in state.os.fs:
        state.os.fs["/logs/nav"] = FSNode(path="/logs/nav", node_type=FSNodeType.DIR, access=AccessLevel.GUEST)
    seq = state.events.next_event_seq
    log_path = f"/logs/nav/uplink_{current_node_id}_{seq:05d}.txt"
    log_content = "".join(f"LINK: {nid}\n" for nid in added)
    state.os.fs[log_path] = FSNode(
        path=log_path,
        node_type=FSNodeType.FILE,
        content=log_content,
        access=AccessLevel.GUEST,
    )
    if added:
        msg = {
            "en": f"uplink_complete :: routes added: {', '.join(sorted(added))}",
            "es": f"uplink_complete :: rutas añadidas: {', '.join(sorted(added))}",
        }
    else:
        msg = {
            "en": "uplink_complete :: no new routes found",
            "es": "uplink_complete :: no se encontraron rutas nuevas",
        }
    print(msg.get(locale, msg["en"]))
    if discarded_by_cap > 0:
        cap_msg = {
            "en": f"uplink_cap :: discarded {discarded_by_cap} route(s) above {Balance.MAX_ROUTE_HOP_LY:.1f}ly",
            "es": f"uplink_cap :: descartadas {discarded_by_cap} ruta(s) por encima de {Balance.MAX_ROUTE_HOP_LY:.1f}ly",
        }
        print(cap_msg.get(locale, cap_msg["en"]))
    lore_ctx = build_lore_context(state, current_node_id)
    lore_result = maybe_deliver_lore(state, "uplink", lore_ctx, count_trigger=False)
    _render_and_store_events(state, lore_result.events)
    dead_events = evaluate_dead_nodes(state, "uplink", debug=state.os.debug_enabled)
    _render_and_store_events(state, dead_events)
    recovery_events: list[Event] = []
    if not added and state.world.mobility_no_new_uplink_count >= Balance.UPLINK_FAILSAFE_N:
        recovery_events = ensure_exploration_recovery(state, "uplink")
        if recovery_events:
            state.world.mobility_no_new_uplink_count = 0
    _render_and_store_events(state, recovery_events)
    if added or lore_result.files or lore_result.events or recovery_events:
        counters = state.world.lore.counters
        counters["uplink_count"] = counters.get("uplink_count", 0) + 1
    if pool:
        pool.uplink_data_consumed = True
        recompute_node_completion(state, current_node_id)
    events_out: list[tuple[str, Event]] = []
    _emit_runtime_event(
        state,
        events_out,
        "cmd",
        EventType.UPLINK_COMPLETE,
        Severity.INFO,
        SourceRef(kind="ship_system", id="data_core"),
        msg.get(locale, msg["en"]),
        data={"routes": list(sorted(added))},
    )
    log_msg = {
        "en": f"Log written to {log_path}",
        "es": f"Registro escrito en {log_path}",
    }
    print(log_msg.get(locale, log_msg["en"]))

def _infer_intel_source(path: str) -> tuple[str, float, str]:
    if path.startswith("/remote/"):
        if "/mail/" in path:
            return "mail", 0.7, path
        if "/logs/" in path:
            return "log", 0.8, path
        if "/data/" in path:
            return "nav_fragment", 0.8, path
    if path.startswith("/mail"):
        return "mail", 0.7, path
    if path.startswith("/logs"):
        return "log", 0.8, path
    if path.startswith("/manuals"):
        return "manual", 0.8, path
    return "nav_fragment", 0.8, path

def _is_intel_path(path: str) -> bool:
    if path.startswith("/data/nav") or path.startswith("/mail") or path.startswith("/logs"):
        return True
    if path.startswith("/remote/"):
        return "/data/nav/" in path or "/mail/" in path or "/logs/" in path
    return False

def _extract_intel_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    start_tag = "[INTEL]"
    end_tag = "[/INTEL]"
    idx = 0
    while True:
        start = text.find(start_tag, idx)
        if start < 0:
            break
        end = text.find(end_tag, start + len(start_tag))
        if end < 0:
            break
        content = text[start + len(start_tag):end].strip()
        if content:
            blocks.append(content)
        idx = end + len(end_tag)
    return blocks


def _resolve_authored_matches(state, token: str) -> list[str]:
    token_norm = token.strip()
    if not token_norm:
        return []
    authored_ids = _authored_node_ids()
    node_id_matches: list[str] = []
    name_matches: list[str] = []
    sector_matches: list[str] = []
    for loc in load_locations():
        node_cfg = loc.get("node", {})
        node_id = node_cfg.get("node_id")
        if not node_id or node_id not in authored_ids:
            continue
        if node_id == token_norm:
            node_id_matches.append(node_id)
            continue
        name = node_cfg.get("name", "")
        if name and name.lower() == token_norm.lower():
            name_matches.append(node_id)
            continue
        try:
            x = float(node_cfg.get("x_ly", 0.0))
            y = float(node_cfg.get("y_ly", 0.0))
            z = float(node_cfg.get("z_ly", 0.0))
        except Exception:
            x = y = z = 0.0
        sector_id = sector_id_for_pos(x, y, z)
        if sector_id == token_norm:
            sector_matches.append(node_id)
            continue
    if node_id_matches:
        return node_id_matches[:1]
    if sector_matches:
        return sector_matches
    if name_matches:
        if len(name_matches) > 1 and state.os.debug_enabled:
            print(f"[DEBUG] intel name collision for '{token_norm}': {', '.join(name_matches)}")
        if len(name_matches) == 1:
            return name_matches
        current = state.world.space.nodes.get(state.world.current_node_id)
        if current:
            name_matches.sort(
                key=lambda nid: (
                    (state.world.space.nodes.get(nid).x_ly - current.x_ly) ** 2
                    + (state.world.space.nodes.get(nid).y_ly - current.y_ly) ** 2
                    + (state.world.space.nodes.get(nid).z_ly - current.z_ly) ** 2
                )
                if state.world.space.nodes.get(nid)
                else float("inf")
            )
        return name_matches[:1]
    return []


def _spawn_corrupt_intel_contact(state, source_path: str) -> str | None:
    current = state.world.space.nodes.get(state.world.current_node_id)
    if not current:
        return None
    radius = Balance.INTEL_CORRUPT_SPAWN_RADIUS_LY
    seed = _hash64(state.meta.rng_seed + state.meta.rng_counter, f"intel_corrupt:{source_path}:{int(state.clock.t)}")
    state.meta.rng_counter += 1
    rng = random.Random(seed)
    locked_primary_targets = _locked_primary_targets(state)
    # Try to find an unknown hub within radius.
    for _ in range(32):
        dx = rng.uniform(-radius, radius)
        dy = rng.uniform(-radius, radius)
        dz = rng.uniform(-radius, radius)
        x = current.x_ly + dx
        y = current.y_ly + dy
        z = current.z_ly + dz
        sector_id = sector_id_for_pos(x, y, z)
        if sector_id not in state.world.generated_sectors:
            ensure_sector_generated(state, sector_id)
        hubs = [
            n
            for n in state.world.space.nodes.values()
            if n.is_hub and sector_id_for_pos(n.x_ly, n.y_ly, n.z_ly) == sector_id
        ]
        hubs = [h for h in hubs if h.node_id not in state.world.known_contacts and h.node_id not in locked_primary_targets]
        if not hubs:
            continue
        hubs.sort(key=lambda n: n.node_id)
        node_id = hubs[0].node_id
        break
    else:
        return None
    state.world.known_nodes.add(node_id)
    state.world.known_contacts.add(node_id)
    record_intel(
        state.world,
        t=state.clock.t,
        kind="node",
        to_id=node_id,
        confidence=0.4,
        source_kind="intel_corrupt",
        source_ref=source_path,
        note="corrupt intel salvage",
    )
    return node_id


def _process_intel_token(state, token: str, source_path: str, messages: list[str]) -> None:
    token = token.strip()
    if not token:
        return
    # LINK inside token
    for raw in token.splitlines():
        line = raw.strip()
        if line.upper().startswith("LINK:"):
            payload = line.split(":", 1)[1].strip()
            if "->" in payload:
                left, right = [p.strip() for p in payload.split("->", 1)]
                if left and right:
                    for nid in (left, right):
                        if nid.startswith("S") and ":" in nid:
                            sector_id = nid.split(":", 1)[0]
                            ensure_sector_generated(state, sector_id)
                    added_link, blocked_by_cap, dist_ly = _try_add_known_link_with_cap(
                        state, left, right, bidirectional=True
                    )
                    if blocked_by_cap:
                        state.world.known_nodes.add(left)
                        state.world.known_nodes.add(right)
                        state.world.known_contacts.add(left)
                        state.world.known_contacts.add(right)
                        messages.append(
                            f"(intel) route skipped (hop cap): {left} -> {right}"
                        )
                        if state.os.debug_enabled:
                            locale = state.os.locale.value
                            msg = {
                                "en": f"[DEBUG] intel link dropped by cap: {left}->{right} dist={(dist_ly or 0.0):.2f}ly",
                                "es": f"[DEBUG] enlace intel descartado por cap: {left}->{right} dist={(dist_ly or 0.0):.2f}ly",
                            }
                            print(msg.get(locale, msg["en"]))
                        return
                    if added_link:
                        _mark_arc_discovered(state, left, right)
                        state.world.known_nodes.add(left)
                        state.world.known_nodes.add(right)
                        state.world.known_contacts.add(left)
                        state.world.known_contacts.add(right)
                        source_kind, confidence, source_ref = _infer_intel_source(source_path)
                        record_intel(
                            state.world,
                            t=state.clock.t,
                            kind="link",
                            from_id=left,
                            to_id=right,
                            confidence=confidence,
                            source_kind=source_kind,
                            source_ref=source_ref,
                        )
                        messages.append(f"(intel) route added: {left} -> {right}")
            return

    # Non-link token: try authored matches.
    matches = _resolve_authored_matches(state, token)
    if matches:
        for node_id in matches:
            if node_id not in state.world.known_nodes:
                state.world.known_nodes.add(node_id)
                state.world.known_contacts.add(node_id)
                source_kind, confidence, source_ref = _infer_intel_source(source_path)
                record_intel(
                    state.world,
                    t=state.clock.t,
                    kind="node",
                    to_id=node_id,
                    confidence=confidence,
                    source_kind=source_kind,
                    source_ref=source_ref,
                )
                messages.append(f"(intel) node known: {node_id}")
        return

    # Corrupt intel handling.
    rng = random.Random(_hash64(state.meta.rng_seed + state.meta.rng_counter, f"intel_corrupt_roll:{source_path}:{token}"))
    state.meta.rng_counter += 1
    if rng.random() < Balance.INTEL_CORRUPT_P_FAIL:
        locale = state.os.locale.value
        msg = {
            "en": "(intel) corrupt data: unable to recover",
            "es": "(intel) datos corruptos: no se pudo recuperar",
        }
        print(msg.get(locale, msg["en"]))
        return
    node_id = _spawn_corrupt_intel_contact(state, source_path)
    if node_id:
        messages.append(f"(intel) node known: {node_id}")
    else:
        locale = state.os.locale.value
        msg = {
            "en": "(intel) corrupt data: no usable intel found",
            "es": "(intel) datos corruptos: no se pudo recuperar",
        }
        print(msg.get(locale, msg["en"]))

def _handle_intel_import(state, path: str) -> None:
    try:
        content = read_file(state.os.fs, path, state.os.auth_levels)
    except PermissionError as e:
        required = e.args[0] if e.args else None
        if required:
            print(f"intel import: access denied (requires {required})")
        else:
            print("intel import: access denied")
        return
    except Exception:
        print("intel import: file not found")
        return

    source_kind, confidence, source_ref = _infer_intel_source(path)
    added_msgs: list[str] = []
    discarded_by_cap = 0
    blocks = _extract_intel_blocks(content)
    for block in blocks:
        _process_intel_token(state, block, path, added_msgs)
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if blocks:
            # Skip legacy parsing when INTEL blocks are present, except for explicit LINK/NODE/SECTOR/COORD lines.
            if not (line.upper().startswith("LINK:") or line.upper().startswith("NODE:") or line.upper().startswith("SECTOR:") or line.upper().startswith("COORD:")):
                continue
        if line.upper().startswith("NODE:"):
            node_id = line.split(":", 1)[1].strip()
            if not node_id:
                continue
            if node_id.startswith("S") and ":" in node_id:
                sector_id = node_id.split(":", 1)[0]
                ensure_sector_generated(state, sector_id)
            if node_id not in state.world.known_nodes:
                state.world.known_intel[node_id] = {"source": path}
                state.world.known_nodes.add(node_id)
                state.world.known_contacts.add(node_id)
                record_intel(
                    state.world,
                    t=state.clock.t,
                    kind="node",
                    to_id=node_id,
                    confidence=confidence,
                    source_kind=source_kind,
                    source_ref=source_ref,
                )
                added_msgs.append(f"(intel) node known: {node_id}")
        if line.upper().startswith("SECTOR:"):
            sector_id = line.split(":", 1)[1].strip()
            if not sector_id:
                continue
            ensure_sector_generated(state, sector_id)
            prev = state.world.known_intel.get(sector_id, {}).get("sector")
            if not prev:
                state.world.known_intel[sector_id] = {"source": path, "sector": True}
                record_intel(
                    state.world,
                    t=state.clock.t,
                    kind="sector",
                    sector_id=sector_id,
                    confidence=confidence,
                    source_kind=source_kind,
                    source_ref=source_ref,
                )
                added_msgs.append(f"(intel) sector known: {sector_id}")
        if line.upper().startswith("LINK:"):
            payload = line.split(":", 1)[1].strip()
            if "->" in payload:
                left, right = [p.strip() for p in payload.split("->", 1)]
                if left and right:
                    for nid in (left, right):
                        if nid.startswith("S") and ":" in nid:
                            sector_id = nid.split(":", 1)[0]
                            ensure_sector_generated(state, sector_id)
                    added_link, blocked_by_cap, _ = _try_add_known_link_with_cap(
                        state, left, right, bidirectional=True
                    )
                    if blocked_by_cap:
                        discarded_by_cap += 1
                        state.world.known_nodes.add(left)
                        state.world.known_nodes.add(right)
                        state.world.known_contacts.add(left)
                        state.world.known_contacts.add(right)
                        added_msgs.append(f"(intel) route skipped (hop cap): {left} -> {right}")
                    if added_link:
                        _mark_arc_discovered(state, left, right)
                        state.world.known_nodes.add(left)
                        state.world.known_nodes.add(right)
                        state.world.known_contacts.add(left)
                        state.world.known_contacts.add(right)
                        record_intel(
                            state.world,
                            t=state.clock.t,
                            kind="link",
                            from_id=left,
                            to_id=right,
                            confidence=confidence,
                            source_kind=source_kind,
                            source_ref=source_ref,
                        )
                        added_msgs.append(f"(intel) route added: {left} -> {right}")
            else:
                to_id = payload
                if to_id:
                    from_id = state.world.current_node_id
                    if to_id.startswith("S") and ":" in to_id:
                        sector_id = to_id.split(":", 1)[0]
                        ensure_sector_generated(state, sector_id)
                    added_link, blocked_by_cap, _ = _try_add_known_link_with_cap(
                        state, from_id, to_id, bidirectional=True
                    )
                    if blocked_by_cap:
                        discarded_by_cap += 1
                        state.world.known_nodes.add(from_id)
                        state.world.known_nodes.add(to_id)
                        state.world.known_contacts.add(from_id)
                        state.world.known_contacts.add(to_id)
                        added_msgs.append(f"(intel) route skipped (hop cap): {from_id} -> {to_id}")
                    if added_link:
                        _mark_arc_discovered(state, from_id, to_id)
                        state.world.known_nodes.add(from_id)
                        state.world.known_nodes.add(to_id)
                        state.world.known_contacts.add(from_id)
                        state.world.known_contacts.add(to_id)
                        record_intel(
                            state.world,
                            t=state.clock.t,
                            kind="link",
                            from_id=from_id,
                            to_id=to_id,
                            confidence=confidence,
                            source_kind=source_kind,
                            source_ref=source_ref,
                        )
                        added_msgs.append(f"(intel) route added: {from_id} -> {to_id}")
        if line.upper().startswith("COORD:"):
            coord_txt = line.split(":", 1)[1].strip()
            try:
                x_s, y_s, z_s = [p.strip() for p in coord_txt.split(",")]
                x, y, z = float(x_s), float(y_s), float(z_s)
            except Exception:
                continue
            import hashlib
            h = hashlib.blake2b(digest_size=4)
            h.update(coord_txt.encode("utf-8"))
            nid = f"NAV_{int.from_bytes(h.digest(), 'big'):08x}"
            if nid not in state.world.space.nodes:
                region = region_for_pos(x, y, z)
                node = SpaceNode(
                    node_id=nid,
                    name="Nav Point",
                    kind="nav_point",
                    radiation_rad_per_s=procedural_radiation_for_node(
                        state.meta.rng_seed, nid, "nav_point", region
                    ),
                    x_ly=x,
                    y_ly=y,
                    z_ly=z,
                )
                node.region = region
                state.world.space.nodes[nid] = node
                sync_sector_state_for_node(state, nid)
            if nid not in state.world.known_nodes:
                state.world.known_intel[nid] = {"source": path, "coord": [x, y, z]}
                state.world.known_nodes.add(nid)
                state.world.known_contacts.add(nid)
                record_intel(
                    state.world,
                    t=state.clock.t,
                    kind="coord",
                    coord=(x, y, z),
                    confidence=confidence,
                    source_kind=source_kind,
                    source_ref=source_ref,
                )
                added_msgs.append(f"(intel) node known: {nid}")
    if added_msgs:
        for msg in sorted(set(added_msgs)):
            print(msg)
    else:
        print("(intel) no usable intel found")
    if discarded_by_cap > 0:
        locale = state.os.locale.value
        msg = {
            "en": f"(intel) links skipped by hop cap: {discarded_by_cap} (>{Balance.MAX_ROUTE_HOP_LY:.1f}ly)",
            "es": f"(intel) enlaces descartados por cap de salto: {discarded_by_cap} (>{Balance.MAX_ROUTE_HOP_LY:.1f}ly)",
        }
        print(msg.get(locale, msg["en"]))


def _auto_import_intel_from_text(state, text: str, source_path: str) -> list[str]:
    source_kind, confidence, source_ref = _infer_intel_source(source_path)
    added_msgs: list[str] = []
    discarded_by_cap = 0
    blocks = _extract_intel_blocks(text)
    for block in blocks:
        _process_intel_token(state, block, source_path, added_msgs)
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if blocks:
            if not (line.upper().startswith("LINK:") or line.upper().startswith("NODE:") or line.upper().startswith("SECTOR:") or line.upper().startswith("COORD:")):
                continue
        if line.upper().startswith("NODE:"):
            node_id = line.split(":", 1)[1].strip()
            if node_id:
                if node_id not in state.world.known_nodes:
                    state.world.known_intel[node_id] = {"source": source_path}
                    state.world.known_nodes.add(node_id)
                    state.world.known_contacts.add(node_id)
                    record_intel(
                        state.world,
                        t=state.clock.t,
                        kind="node",
                        to_id=node_id,
                        confidence=confidence,
                        source_kind=source_kind,
                        source_ref=source_ref,
                    )
                    added_msgs.append(f"(intel) node known: {node_id}")
        if line.upper().startswith("SECTOR:"):
            sector_id = line.split(":", 1)[1].strip()
            if sector_id:
                ensure_sector_generated(state, sector_id)
                prev = state.world.known_intel.get(sector_id, {}).get("sector")
                if not prev:
                    state.world.known_intel[sector_id] = {"source": source_path, "sector": True}
                    record_intel(
                        state.world,
                        t=state.clock.t,
                        kind="sector",
                        sector_id=sector_id,
                        confidence=confidence,
                        source_kind=source_kind,
                        source_ref=source_ref,
                    )
                    added_msgs.append(f"(intel) sector known: {sector_id}")
        if line.upper().startswith("LINK:"):
            payload = line.split(":", 1)[1].strip()
            if "->" in payload:
                left, right = [p.strip() for p in payload.split("->", 1)]
                if left and right:
                    for nid in (left, right):
                        if nid.startswith("S") and ":" in nid:
                            sector_id = nid.split(":", 1)[0]
                            ensure_sector_generated(state, sector_id)
                    added_link, blocked_by_cap, _ = _try_add_known_link_with_cap(
                        state, left, right, bidirectional=True
                    )
                    if blocked_by_cap:
                        discarded_by_cap += 1
                        state.world.known_nodes.add(left)
                        state.world.known_nodes.add(right)
                        state.world.known_contacts.add(left)
                        state.world.known_contacts.add(right)
                        added_msgs.append(f"(intel) route skipped (hop cap): {left} -> {right}")
                    if added_link:
                        _mark_arc_discovered(state, left, right)
                        state.world.known_nodes.add(left)
                        state.world.known_nodes.add(right)
                        state.world.known_contacts.add(left)
                        state.world.known_contacts.add(right)
                        record_intel(
                            state.world,
                            t=state.clock.t,
                            kind="link",
                            from_id=left,
                            to_id=right,
                            confidence=confidence,
                            source_kind=source_kind,
                            source_ref=source_ref,
                        )
                        added_msgs.append(f"(intel) route added: {left} -> {right}")
            else:
                to_id = payload
                if to_id:
                    from_id = state.world.current_node_id
                    if to_id.startswith("S") and ":" in to_id:
                        sector_id = to_id.split(":", 1)[0]
                        ensure_sector_generated(state, sector_id)
                    added_link, blocked_by_cap, _ = _try_add_known_link_with_cap(
                        state, from_id, to_id, bidirectional=True
                    )
                    if blocked_by_cap:
                        discarded_by_cap += 1
                        state.world.known_nodes.add(from_id)
                        state.world.known_nodes.add(to_id)
                        state.world.known_contacts.add(from_id)
                        state.world.known_contacts.add(to_id)
                        added_msgs.append(f"(intel) route skipped (hop cap): {from_id} -> {to_id}")
                    if added_link:
                        _mark_arc_discovered(state, from_id, to_id)
                        state.world.known_nodes.add(from_id)
                        state.world.known_nodes.add(to_id)
                        state.world.known_contacts.add(from_id)
                        state.world.known_contacts.add(to_id)
                        record_intel(
                            state.world,
                            t=state.clock.t,
                            kind="link",
                            from_id=from_id,
                            to_id=to_id,
                            confidence=confidence,
                            source_kind=source_kind,
                            source_ref=source_ref,
                        )
                        added_msgs.append(f"(intel) route added: {from_id} -> {to_id}")
        if line.upper().startswith("COORD:"):
            coord_txt = line.split(":", 1)[1].strip()
            try:
                x_s, y_s, z_s = [p.strip() for p in coord_txt.split(",")]
                x, y, z = float(x_s), float(y_s), float(z_s)
            except Exception:
                continue
            import hashlib
            h = hashlib.blake2b(digest_size=4)
            h.update(coord_txt.encode("utf-8"))
            nid = f"NAV_{int.from_bytes(h.digest(), 'big'):08x}"
            if nid not in state.world.space.nodes:
                region = region_for_pos(x, y, z)
                node = SpaceNode(
                    node_id=nid,
                    name="Nav Point",
                    kind="nav_point",
                    radiation_rad_per_s=procedural_radiation_for_node(
                        state.meta.rng_seed, nid, "nav_point", region
                    ),
                    x_ly=x,
                    y_ly=y,
                    z_ly=z,
                )
                node.region = region
                state.world.space.nodes[nid] = node
                sync_sector_state_for_node(state, nid)
            if nid not in state.world.known_nodes:
                state.world.known_intel[nid] = {"source": source_path, "coord": [x, y, z]}
                state.world.known_nodes.add(nid)
                state.world.known_contacts.add(nid)
                record_intel(
                    state.world,
                    t=state.clock.t,
                    kind="coord",
                    coord=(x, y, z),
                    confidence=confidence,
                    source_kind=source_kind,
                    source_ref=source_ref,
                )
                added_msgs.append(f"(intel) node known: {nid}")
    if discarded_by_cap > 0:
        added_msgs.append(
            f"(intel) links skipped by hop cap: {discarded_by_cap} (>{Balance.MAX_ROUTE_HOP_LY:.1f}ly)"
        )
    return added_msgs

def render_ship_sectors(state) -> None:
    print("\n=== RETORNO SHIP SECTORS ===")
    if not state.ship.sectors:
        print("(none)")
        return
    for sid, sector in state.ship.sectors.items():
        tags = ",".join(sorted(sector.tags)) if sector.tags else "-"
        print(f"- {sid}: {sector.name} [{tags}]")


def render_sectors(state) -> None:
    # Legacy wrapper used by existing call sites/tests.
    render_ship_sectors(state)


def _map_known_nodes(state) -> set[str]:
    current_id = state.world.current_node_id
    known = set(state.world.known_nodes if state.world.known_nodes else state.world.known_contacts)
    known.add(current_id)
    ship_id = getattr(state.ship, "ship_id", "RETORNO_SHIP")
    known = {nid for nid in known if nid != ship_id and (nid == current_id or not nid.startswith("UNKNOWN_"))}
    for src, dests in state.world.known_links.items():
        if src != ship_id and (src == current_id or not src.startswith("UNKNOWN_")):
            known.add(src)
        for dst in dests:
            if dst != ship_id and (dst == current_id or not dst.startswith("UNKNOWN_")):
                known.add(dst)
    return known


def _map_known_adjacency(state, nodes: set[str]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {nid: set() for nid in nodes}
    for src, dests in state.world.known_links.items():
        if src not in adj:
            continue
        for dst in dests:
            if dst in adj and dst != src:
                adj[src].add(dst)
    return adj


def _map_component_count(nodes: set[str], adj: dict[str, set[str]]) -> int:
    undirected: dict[str, set[str]] = {nid: set() for nid in nodes}
    for src, dests in adj.items():
        if src not in undirected:
            continue
        for dst in dests:
            if dst not in undirected:
                continue
            undirected[src].add(dst)
            undirected[dst].add(src)
    remaining = set(nodes)
    components = 0
    while remaining:
        start = next(iter(remaining))
        queue = [start]
        seen = {start}
        i = 0
        while i < len(queue):
            cur = queue[i]
            i += 1
            for nxt in undirected.get(cur, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        remaining -= seen
        components += 1
    return components


def _map_preview(items: list[str], max_items: int = 6) -> str:
    if not items:
        return "-"
    if len(items) <= max_items:
        return ", ".join(items)
    shown = ", ".join(items[:max_items])
    return f"{shown}, +{len(items) - max_items} more"


def _map_reachable_nodes(adj: dict[str, set[str]], start_id: str) -> set[str]:
    if start_id not in adj:
        return {start_id}
    queue = [start_id]
    seen = {start_id}
    i = 0
    while i < len(queue):
        cur = queue[i]
        i += 1
        for nxt in sorted(adj.get(cur, set())):
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _distance_ly_between_nodes(state, left_id: str, right_id: str) -> float | None:
    left = state.world.space.nodes.get(left_id)
    right = state.world.space.nodes.get(right_id)
    if not left or not right:
        return None
    dx = left.x_ly - right.x_ly
    dy = left.y_ly - right.y_ly
    dz = left.z_ly - right.z_ly
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _map_bfs_path(adj: dict[str, set[str]], start_id: str, target_id: str) -> tuple[list[str] | None, set[str]]:
    queue = [start_id]
    prev: dict[str, str | None] = {start_id: None}
    i = 0
    while i < len(queue):
        cur = queue[i]
        i += 1
        for nxt in sorted(adj.get(cur, set())):
            if nxt in prev:
                continue
            prev[nxt] = cur
            queue.append(nxt)
            if nxt == target_id:
                break
    reachable = set(prev.keys())
    if target_id not in prev:
        return None, reachable
    path: list[str] = []
    cur: str | None = target_id
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path, reachable


def _route_solve_sources_for_target(state, target_id: str, source_ids: set[str]) -> list[tuple[float, str]]:
    sensors_range_ly = max(0.0, float(getattr(state.ship, "sensors_range_ly", Balance.SENSORS_RANGE_LY)))
    candidates: list[tuple[float, str]] = []
    for src_id in sorted(source_ids):
        if src_id == target_id:
            continue
        dist = _distance_ly_between_nodes(state, src_id, target_id)
        if dist is None or dist > sensors_range_ly:
            continue
        candidates.append((dist, src_id))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates


def _route_solve_origin_hints(state, target_id: str) -> list[tuple[float, str, bool, bool]]:
    known_nodes = _map_known_nodes(state)
    current_id = state.world.current_node_id
    adj = _map_known_adjacency(state, known_nodes)
    adj.setdefault(current_id, set())
    reachable = _map_reachable_nodes(adj, current_id)

    hints: list[tuple[float, str, bool, bool]] = []
    for dist, src_id in _route_solve_sources_for_target(state, target_id, known_nodes):
        route_known = target_id in state.world.known_links.get(src_id, set())
        hints.append((dist, src_id, src_id in reachable, route_known))

    hints.sort(key=lambda item: (0 if item[2] else 1, 0 if item[3] else 1, item[0], item[1]))
    return hints


def _route_solve_origin_hint_lines(state, target_id: str) -> list[str]:
    locale = state.os.locale.value
    hints = _route_solve_origin_hints(state, target_id)
    if not hints:
        msg = {
            "en": f"No known nodes place {target_id} within route-solve range.",
            "es": f"Ningun nodo conocido situa {target_id} dentro del rango de route solve.",
        }
        return [msg.get(locale, msg["en"])]

    title = {
        "en": f"Known nodes from which {target_id} is within route-solve range:",
        "es": f"Nodos conocidos desde los que {target_id} entra en rango de route solve:",
    }
    reachable_labels = {
        "en": "reachable",
        "es": "alcanzable",
    }
    unreachable_labels = {
        "en": "no known path from current",
        "es": "sin camino conocido desde aqui",
    }
    route_known_labels = {
        "en": "route already known",
        "es": "ruta ya conocida",
    }
    route_solve_labels = {
        "en": "route solve possible",
        "es": "route solve posible",
    }

    lines = [title.get(locale, title["en"])]
    for dist, src_id, is_reachable, route_known in hints:
        tags = [
            reachable_labels.get(locale, reachable_labels["en"])
            if is_reachable
            else unreachable_labels.get(locale, unreachable_labels["en"]),
            route_known_labels.get(locale, route_known_labels["en"])
            if route_known
            else route_solve_labels.get(locale, route_solve_labels["en"]),
        ]
        lines.append(f"- {src_id} ({', '.join(tags)}, {dist:.2f}ly)")
    return lines


def render_map_graph(state, node_id: str | None = None) -> None:
    locale = state.os.locale.value
    current_id = state.world.current_node_id
    nodes = _map_known_nodes(state)
    if node_id is not None and node_id not in nodes:
        msg = {
            "en": f"map graph: unknown node ({node_id})",
            "es": f"map graph: nodo desconocido ({node_id})",
        }
        print(msg.get(locale, msg["en"]))
        return
    adj = _map_known_adjacency(state, nodes)

    print("\n=== MAP GRAPH ===")
    if node_id is None:
        edge_count = sum(len(v) for v in adj.values()) // 2
        components = _map_component_count(nodes, adj)
        print(f"known_nodes={len(nodes)} known_links={edge_count} components={components}")
        render_ids = sorted(nodes)
    else:
        render_ids = [node_id]

    for nid in render_ids:
        neighbors = sorted(adj.get(nid, set()))
        marker = "*" if nid == current_id else ""
        visited = "visited" if nid in state.world.visited_nodes else "unvisited"
        node = state.world.space.nodes.get(nid)
        if node:
            print(f"- {nid}{marker} ({node.name}, {node.kind}) {visited}")
        else:
            print(f"- {nid}{marker} {visited}")
        print(f"  links: {_map_preview(neighbors, max_items=8)}")


def render_map_path(state, target_id: str) -> None:
    locale = state.os.locale.value
    current_id = state.world.current_node_id
    nodes = _map_known_nodes(state)
    adj = _map_known_adjacency(state, nodes)

    print("\n=== MAP PATH ===")
    if target_id not in nodes:
        msg = {
            "en": f"map path: unknown node ({target_id})",
            "es": f"map path: nodo desconocido ({target_id})",
        }
        print(msg.get(locale, msg["en"]))
        return
    if current_id not in nodes:
        nodes.add(current_id)
        adj.setdefault(current_id, set())
    if target_id == current_id:
        msg = {
            "en": f"already at destination: {target_id}",
            "es": f"ya estás en destino: {target_id}",
        }
        print(msg.get(locale, msg["en"]))
        return

    path, reachable = _map_bfs_path(adj, current_id, target_id)
    if path:
        hops = max(0, len(path) - 1)
        print(f"path: {' -> '.join(path)}")
        print(f"hops: {hops}")
        return

    unreachable = sorted(n for n in nodes if n not in reachable)
    msg = {
        "en": f"no known path from {current_id} to {target_id}",
        "es": f"no hay camino conocido desde {current_id} hasta {target_id}",
    }
    print(msg.get(locale, msg["en"]))
    print(f"reachable_component={len(reachable)} unreachable_known={len(unreachable)}")

    bridges: list[tuple[float, str, str]] = []
    reachable_sources = set(reachable)
    for dst in unreachable:
        for dist, src in _route_solve_sources_for_target(state, dst, reachable_sources):
            bridges.append((dist, src, dst))
    bridges.sort(key=lambda x: x[0])
    if bridges:
        hint = {
            "en": "possible bridge links in sensor range (route solve):",
            "es": "posibles enlaces puente en rango de sensores (route solve):",
        }
        print(hint.get(locale, hint["en"]))
        for dist, src, dst in bridges[:8]:
            print(f"- {src} -> {dst} ({dist:.2f}ly)")
    else:
        hint = {
            "en": "Try: travel within reachable nodes, then uplink/scan/route solve to discover bridge links.",
            "es": "Prueba: viaja por nodos alcanzables y luego usa uplink/scan/route solve para descubrir enlaces puente.",
        }
        print(hint.get(locale, hint["en"]))


def _sector_coords_from_id(sector_id: str) -> tuple[int, int, int] | None:
    if not sector_id.startswith("S"):
        return None
    body = sector_id[1:]
    parts = body.split("_")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def render_nav_map_sectors(state) -> None:
    print("\n=== NAV MAP SECTORS ===")
    known_ids = _map_known_nodes(state)
    sector_ids: set[str] = set()
    for nid in known_ids:
        node = state.world.space.nodes.get(nid)
        if not node:
            continue
        sector_ids.add(sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly))
    cx, cy, cz = state.world.current_pos_ly
    sector_ids.add(sector_id_for_pos(cx, cy, cz))
    if not sector_ids:
        print("(none)")
        return
    for sid in sorted(sector_ids):
        coords = _sector_coords_from_id(sid)
        if coords is None:
            print(f"- {sid}")
            continue
        sx, sy, sz = coords
        origin_x = sx * SECTOR_SIZE_LY
        origin_y = sy * SECTOR_SIZE_LY
        origin_z = sz * SECTOR_SIZE_LY
        print(
            f"- {sid} coord=({sx:+d},{sy:+d},{sz:+d}) "
            f"origin_ly=({origin_x:.2f},{origin_y:.2f},{origin_z:.2f})"
        )


def _iter_nodes_for_galaxy_map(state, include_all_loaded: bool) -> list[SpaceNode]:
    if include_all_loaded:
        return list(state.world.space.nodes.values())
    known_ids = _map_known_nodes(state)
    out: list[SpaceNode] = []
    for nid in sorted(known_ids):
        node = state.world.space.nodes.get(nid)
        if node:
            out.append(node)
    return out


def render_nav_map_galaxy(state, scale: str | None = None, *, include_all_loaded: bool = False) -> None:
    scale_name = _normalize_galaxy_scale(scale)
    radius_ly = float(_GALAXY_MAP_SCALES[scale_name])
    locale = state.os.locale.value
    labels = {
        "en": {
            "title": "\n=== NAV MAP GALAXY ===",
            "legend": "- legend: @ ship | b/d/h node by physical region | o bulge ring | . disk edge | # galaxy edge",
            "meta": "- meta:",
            "player_op": "- player_op_pos_ly:",
            "player_phys": "- player_physical_pos_ly:",
            "player_region": "- player_physical_region:",
            "margins": "- margins_ly:",
            "center": "center",
            "radius": "radius",
            "scale": "scale",
            "visible": "visible_nodes",
            "occluded": "occluded_nodes",
            "outside": "outside_galaxy",
        },
        "es": {
            "title": "\n=== NAV MAP GALAXY ===",
            "legend": "- leyenda: @ nave | b/d/h nodo por region fisica | o anillo bulge | . borde disk | # borde galaxia",
            "meta": "- meta:",
            "player_op": "- jugador_pos_op_ly:",
            "player_phys": "- jugador_pos_fisica_ly:",
            "player_region": "- jugador_region_fisica:",
            "margins": "- margenes_ly:",
            "center": "centro",
            "radius": "radio",
            "scale": "escala",
            "visible": "nodos_visibles",
            "occluded": "nodos_ocultos",
            "outside": "fuera_de_galaxia",
        },
    }
    txt = labels.get(locale, labels["en"])
    print(txt["title"])

    width = 61
    height = 31
    cx = width // 2
    cy = height // 2
    half_w = max(1, width // 2)
    half_h = max(1, height // 2)
    grid: list[list[str]] = [[" " for _ in range(width)] for _ in range(height)]
    priority: dict[str, int] = {" ": 0, "#": 1, ".": 2, "o": 3, "b": 4, "d": 4, "h": 4, "@": 9}

    opx, opy, opz = state.world.current_pos_ly
    ppx, ppy, ppz = op_to_galactic_coords(opx, opy, opz)
    center_x = float(Balance.GALAXY_PHYSICAL_CENTER_X_LY) if scale_name == "global" else float(opx)
    center_y = float(Balance.GALAXY_PHYSICAL_CENTER_Y_LY) if scale_name == "global" else float(opy)
    center_kind = "physical" if scale_name == "global" else "operational"

    def _paint(gx: int, gy: int, ch: str) -> None:
        if gx < 0 or gx >= width or gy < 0 or gy >= height:
            return
        cur = grid[gy][gx]
        if priority.get(ch, 0) >= priority.get(cur, 0):
            grid[gy][gx] = ch

    def _to_grid(px: float, py: float) -> tuple[int, int] | None:
        if radius_ly <= 0.0:
            return None
        nx = (px - center_x) / radius_ly
        ny = (py - center_y) / radius_ly
        if abs(nx) > 1.0 or abs(ny) > 1.0:
            return None
        gx = int(round(cx + nx * half_w))
        gy = int(round(cy - ny * half_h))
        if gx < 0 or gx >= width or gy < 0 or gy >= height:
            return None
        return gx, gy

    def _draw_ring(radius_ring_ly: float, ch: str) -> None:
        if radius_ring_ly <= 0.0:
            return
        steps = 720
        for i in range(steps):
            ang = 2.0 * math.pi * (i / steps)
            px = center_x + radius_ring_ly * math.cos(ang)
            py = center_y + radius_ring_ly * math.sin(ang)
            point = _to_grid(px, py)
            if point:
                _paint(point[0], point[1], ch)

    if scale_name == "global":
        _draw_ring(float(Balance.GALAXY_PHYSICAL_RADIUS_LY), "#")
        _draw_ring(float(Balance.GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY), ".")
        _draw_ring(float(Balance.GALAXY_PHYSICAL_BULGE_RADIUS_LY), "o")

    authored_ids = _authored_node_ids()
    nodes = _iter_nodes_for_galaxy_map(state, include_all_loaded=include_all_loaded)
    buckets: dict[tuple[int, int], list[SpaceNode]] = {}
    visible_nodes = 0
    for node in nodes:
        px = float(node.x_ly)
        py = float(node.y_ly)
        if scale_name == "global":
            gpx, gpy, _ = op_to_galactic_coords(node.x_ly, node.y_ly, node.z_ly)
            px = gpx
            py = gpy
        point = _to_grid(px, py)
        if point is None:
            continue
        visible_nodes += 1
        buckets.setdefault(point, []).append(node)

    occluded_nodes = 0
    marker_by_region = {"bulge": "b", "disk": "d", "halo": "h"}
    for (gx, gy), cell_nodes in buckets.items():
        if len(cell_nodes) > 1:
            occluded_nodes += len(cell_nodes) - 1
        winner = max(
            cell_nodes,
            key=lambda n: (
                _node_symbol_rank(n, authored_ids),
                _stable_cell_tiebreak(state.meta.rng_seed, scale_name, gx, gy, n.node_id),
            ),
        )
        marker = marker_by_region.get(
            galactic_region_for_op_pos(winner.x_ly, winner.y_ly, winner.z_ly),
            "d",
        )
        _paint(gx, gy, marker)

    player_point: tuple[int, int] | None
    if scale_name == "global":
        player_point = _to_grid(ppx, ppy)
    else:
        player_point = (cx, cy)
    if player_point is None:
        player_point = (cx, cy)
    _paint(player_point[0], player_point[1], "@")

    for row in grid:
        print("".join(row))

    margins = galactic_margins_for_op_pos(opx, opy, opz)
    region = galactic_region_for_op_pos(opx, opy, opz)
    margin_bulge = float(margins.get("distance_to_bulge_ly", 0.0))
    margin_halo = float(margins.get("distance_to_halo_ly", 0.0))
    in_galaxy = bool(margins.get("inside_galaxy", True))
    center_txt = f"{center_kind}=({center_x:.2f},{center_y:.2f})"
    print(
        f"{txt['meta']} {txt['scale']}={scale_name} {txt['radius']}={radius_ly:.1f}ly "
        f"{txt['center']}={center_txt} {txt['visible']}={visible_nodes} {txt['occluded']}={occluded_nodes}"
    )
    print(f"{txt['player_op']} ({opx:.2f}, {opy:.2f}, {opz:.2f})")
    print(f"{txt['player_phys']} ({ppx:.2f}, {ppy:.2f}, {ppz:.2f})")
    if in_galaxy:
        print(f"{txt['player_region']} {region}")
    else:
        print(f"{txt['player_region']} {region} ({txt['outside']})")
    print(f"{txt['margins']} to_bulge={margin_bulge:.2f} to_halo={margin_halo:.2f}")
    print(txt["legend"])


def render_nav_map(state, mode: str, map_arg: str | None = None) -> None:
    if mode == "graph":
        render_map_graph(state, node_id=map_arg)
        return
    if mode == "path":
        if not map_arg:
            msg = {
                "en": "nav map path: missing node_id",
                "es": "nav map path: falta node_id",
            }
            print(msg.get(state.os.locale.value, msg["en"]))
            return
        render_map_path(state, target_id=map_arg)
        return
    if mode == "routes":
        render_nav_routes(state)
        return
    if mode == "contacts":
        render_nav_contacts(state, map_arg=map_arg)
        return
    if mode == "sectors":
        render_nav_map_sectors(state)
        return
    if mode == "galaxy":
        render_nav_map_galaxy(state, map_arg)
        return
    msg = {
        "en": "nav map: unknown mode",
        "es": "nav map: modo desconocido",
    }
    print(msg.get(state.os.locale.value, msg["en"]))


def render_locate(state, system_id: str) -> None:
    sys = state.ship.systems.get(system_id)
    if sys:
        sector = state.ship.sectors.get(sys.sector_id)
        if sector:
            print(f"system_id: {system_id}")
            print(f"ship_sector: {sys.sector_id} ({sector.name})")
        else:
            print(f"system_id: {system_id}")
            print(f"ship_sector: {sys.sector_id}")
        return
    node = state.world.space.nodes.get(system_id)
    if not node:
        print("(locate) system_id/node_id no encontrado")
        return
    sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
    print(f"node_id: {system_id}")
    print(f"name: {node.name}")
    print(f"sector: {sector_id}")
    print(f"coords: {node.x_ly:.2f}, {node.y_ly:.2f}, {node.z_ly:.2f}")


def render_nav_routes(state) -> None:
    print("\n=== NAV ROUTES ===")
    current_id = state.world.current_node_id
    player_ship_id = getattr(state.ship, "ship_id", "RETORNO_SHIP")
    routes = {
        rid
        for rid in state.world.known_links.get(current_id, set())
        if rid != current_id and rid != player_ship_id
    }
    current = state.world.space.nodes.get(current_id)
    cx, cy, cz = (current.x_ly, current.y_ly, current.z_ly) if current else state.world.current_pos_ly
    def _format_dist(node) -> str:
        dx = node.x_ly - cx
        dy = node.y_ly - cy
        dz = node.z_ly - cz
        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
        same_sector = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly) == sector_id_for_pos(cx, cy, cz)
        if (
            same_sector
            and dist <= Balance.LOCAL_TRAVEL_RADIUS_LY
            and node.node_id in state.world.fine_ranges_km
        ):
            km = state.world.fine_ranges_km.get(node.node_id, 0.0)
            locale = state.os.locale.value
            if locale == "en":
                miles = km * 0.621371
                return f"{_format_large_distance(miles)}mi"
            return f"{_format_large_distance(km)}km"
        if dist < 0.1:
            return f"{dist:.4f}ly"
        if dist < 1.0:
            return f"{dist:.3f}ly"
        return f"{dist:.2f}ly"

    if routes:
        print(f"Known routes from {current_id}:")
        for nid in sorted(routes):
            node = state.world.space.nodes.get(nid)
            if node:
                if node.node_id.startswith("S"):
                    sector_id = node.node_id.split(":", 1)[0]
                else:
                    sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
                sector = f" sector={sector_id}"
                visited = "visited" if nid in state.world.visited_nodes else "unvisited"
                print(f"- {node.name} ({node.kind}){sector} id={nid} dist={_format_dist(node)} {visited}")
            else:
                print(f"- id={nid}")
    else:
        print(f"(no known routes from {current_id})")
    # Nearby contacts without routes
    nearby = [
        nid
        for nid in state.world.known_nodes
        if nid not in routes and nid != current_id and nid != player_ship_id
    ]
    if nearby:
        print("Nearby contacts without known route:")
        for nid in sorted(nearby):
            node = state.world.space.nodes.get(nid)
            if node:
                if node.node_id.startswith("S"):
                    sector_id = node.node_id.split(":", 1)[0]
                else:
                    sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
                sector = f" sector={sector_id}"
                visited = "visited" if nid in state.world.visited_nodes else "unvisited"
                print(f"- {node.name} ({node.kind}){sector} id={nid} dist={_format_dist(node)} {visited}")
            else:
                print(f"- {nid}")
        locale = state.os.locale.value
        hint = {
            "en": "Try: scan, route solve, intel, uplink (at relay/waystation), or acquire intel.",
            "es": "Prueba: scan, route solve, intel, uplink (en relay/waystation) o consigue inteligencia.",
        }
        print(hint.get(locale, hint["en"]))


def render_nav(state) -> None:
    # Legacy wrapper used by old call sites.
    render_nav_routes(state)


def _ship_survey_blocked_reason(state) -> str | None:
    sensors = state.ship.systems.get("sensors")
    if not sensors:
        return "missing_sensors"
    if sensors.state == SystemState.OFFLINE:
        return "sensors_offline"
    if _state_rank(sensors.state) < _state_rank(SystemState.LIMITED):
        return "sensors_degraded"
    if not sensors.service or sensors.service.service_name != "sensord" or not sensors.service.is_installed:
        return "sensord_missing"
    if not sensors.service.is_running:
        return "sensord_not_running"

    data_core = state.ship.systems.get("data_core")
    if not data_core:
        return "missing_data_core"
    if data_core.state == SystemState.OFFLINE:
        return "data_core_offline"
    if _state_rank(data_core.state) < _state_rank(SystemState.LIMITED):
        return "data_core_degraded"
    if not data_core.service or data_core.service.service_name != "datad" or not data_core.service.is_installed:
        return "datad_missing"
    if not data_core.service.is_running:
        return "datad_not_running"
    return None


def _ship_survey_blocked_message(state, reason: str) -> str:
    locale = state.os.locale.value
    messages = {
        "en": {
            "missing_sensors": "ship survey blocked: sensors missing",
            "sensors_offline": "ship survey blocked: sensors offline",
            "sensors_degraded": "ship survey blocked: sensors degraded (requires >= limited)",
            "sensord_missing": "ship survey blocked: sensord not installed",
            "sensord_not_running": "ship survey blocked: sensord not running. Try: boot sensord",
            "missing_data_core": "ship survey blocked: data_core missing",
            "data_core_offline": "ship survey blocked: data_core offline",
            "data_core_degraded": "ship survey blocked: data_core degraded (requires >= limited)",
            "datad_missing": "ship survey blocked: datad not installed",
            "datad_not_running": "ship survey blocked: datad not running. Try: boot datad",
        },
        "es": {
            "missing_sensors": "ship survey bloqueado: falta sensors",
            "sensors_offline": "ship survey bloqueado: sensors offline",
            "sensors_degraded": "ship survey bloqueado: sensors degradado (requiere >= limited)",
            "sensord_missing": "ship survey bloqueado: sensord no instalado",
            "sensord_not_running": "ship survey bloqueado: sensord no está en ejecución. Prueba: boot sensord",
            "missing_data_core": "ship survey bloqueado: falta data_core",
            "data_core_offline": "ship survey bloqueado: data_core offline",
            "data_core_degraded": "ship survey bloqueado: data_core degradado (requiere >= limited)",
            "datad_missing": "ship survey bloqueado: datad no instalado",
            "datad_not_running": "ship survey bloqueado: datad no está en ejecución. Prueba: boot datad",
        },
    }
    localized = messages.get(locale, messages["en"])
    return localized.get(reason, messages["en"].get(reason, "ship survey blocked"))


def render_ship_survey(state, target_id: str) -> None:
    reason = _ship_survey_blocked_reason(state)
    if reason:
        print(_ship_survey_blocked_message(state, reason))
        return

    ship_id = getattr(state.ship, "ship_id", "RETORNO_SHIP")
    target_norm = target_id.strip()
    locale = state.os.locale.value
    unknown_radiation = {
        "en": "unknown",
        "es": "desconocida",
    }
    print("\n=== SHIP SURVEY ===")

    if target_norm in {ship_id, "RETORNO_SHIP"}:
        x, y, z = state.world.current_pos_ly
        sector_id = sector_id_for_pos(x, y, z)
        current_id = state.world.current_node_id
        visited = "visited" if current_id in state.world.visited_nodes else "unvisited"
        print(f"id: {ship_id}")
        print("name: RETORNO")
        print("kind: ship")
        print(f"node: {current_id}")
        print(f"sector: {sector_id}")
        print(f"coords: {x:.2f}, {y:.2f}, {z:.2f}")
        print("distance: 0.00ly")
        print(f"visited: {visited}")
        print("route: self")
        print("availability: onboard")
        print(f"node_radiation: {max(0.0, float(state.ship.radiation_env_rad_per_s)):.4f}rad/s")
        return

    node = state.world.space.nodes.get(target_norm)
    if not node:
        msg = {
            "en": f"ship survey: unknown node ({target_norm})",
            "es": f"ship survey: nodo desconocido ({target_norm})",
        }
        print(msg.get(locale, msg["en"]))
        return

    current_id = state.world.current_node_id
    current = state.world.space.nodes.get(current_id)
    if current:
        cx, cy, cz = current.x_ly, current.y_ly, current.z_ly
    else:
        cx, cy, cz = state.world.current_pos_ly
    dx = node.x_ly - cx
    dy = node.y_ly - cy
    dz = node.z_ly - cz
    distance = (dx * dx + dy * dy + dz * dz) ** 0.5
    sector_id = sector_id_for_pos(node.x_ly, node.y_ly, node.z_ly)
    known = target_norm in (
        state.world.known_nodes if state.world.known_nodes else state.world.known_contacts
    )
    route = target_norm == current_id or target_norm in state.world.known_links.get(current_id, set())
    visited = target_norm in state.world.visited_nodes
    in_sensor_range = distance <= state.ship.sensors_range_ly
    radiation_known = visited or in_sensor_range
    if radiation_known:
        radiation_line = f"{max(0.0, float(node.radiation_rad_per_s)):.4f}rad/s"
    else:
        radiation_line = unknown_radiation.get(locale, unknown_radiation["en"])
    print(f"id: {target_norm}")
    print(f"name: {node.name}")
    print(f"kind: {node.kind}")
    print(f"sector: {sector_id}")
    print(f"coords: {node.x_ly:.2f}, {node.y_ly:.2f}, {node.z_ly:.2f}")
    print(f"distance: {distance:.2f}ly")
    print(f"visited: {'yes' if visited else 'no'}")
    print(f"known_contact: {'yes' if known else 'no'}")
    print(f"known_route_from_current: {'yes' if route else 'no'}")
    print(f"in_sensor_range: {'yes' if in_sensor_range else 'no'}")
    print(f"node_radiation: {radiation_line}")


def _format_age_short(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds >= 86400:
        return f"{int(seconds // 86400)}d"
    if seconds >= 3600:
        return f"{int(seconds // 3600)}h"
    if seconds >= 60:
        return f"{int(seconds // 60)}m"
    return f"{int(seconds)}s"


def _format_eta_short(seconds: float, locale: str = "en") -> str:
    seconds = max(0.0, seconds)
    unit = {
        "en": {"s": "s", "m": "m", "h": "h", "d": "d", "y": "y"},
        "es": {"s": "s", "m": "m", "h": "h", "d": "d", "y": "a"},
    }.get(locale, {"s": "s", "m": "m", "h": "h", "d": "d", "y": "y"})
    if seconds < 60:
        return f"{int(seconds)}{unit['s']}"
    if seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}{unit['m']} {secs}{unit['s']}"
    if seconds < 86400:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}{unit['h']} {mins}{unit['m']}"
    if seconds < Balance.YEAR_S:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{days}{unit['d']} {hours}{unit['h']} {mins}{unit['m']}"
    return f"{seconds / Balance.YEAR_S:.2f}{unit['y']}"


_LOG_BUFFER: list[str] = []


class _TeeStdout:
    def __init__(self, stream, buffer: list[str], max_lines: int = 2000) -> None:
        self._stream = stream
        self._buffer = buffer
        self._max_lines = max_lines
        self._partial = ""

    def write(self, s: str) -> int:
        if not s:
            return 0
        self._stream.write(s)
        self._partial += s
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            if line:
                self._buffer.append(line)
                if len(self._buffer) > self._max_lines:
                    del self._buffer[:-self._max_lines]
        return len(s)

    def flush(self) -> None:
        self._stream.flush()

    def isatty(self) -> bool:
        try:
            return self._stream.isatty()
        except Exception:
            return False

    def fileno(self) -> int:
        return self._stream.fileno()

    @property
    def encoding(self):
        return getattr(self._stream, "encoding", None)

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def _copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["pbcopy"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-8"))
            return proc.returncode == 0
        except Exception:
            continue
    return False


def _write_log_copy_file(content: str) -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "log_copy.txt"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _handle_log_copy(state, amount: int | None) -> None:
    locale = state.os.locale.value
    lines = list(_LOG_BUFFER)
    if amount is None:
        amount = min(50, len(lines))
    if amount <= 0:
        amount = 0
    slice_lines = lines[-amount:] if amount else []
    content = "\n".join(slice_lines)
    ok = _copy_to_clipboard(content)
    if ok:
        msg = {
            "en": f"(log) copied {len(slice_lines)} lines to clipboard",
            "es": f"(log) copiadas {len(slice_lines)} líneas al portapapeles",
        }
        print(msg.get(locale, msg["en"]))
    else:
        path = _write_log_copy_file(content)
        msg = {
            "en": f"(log) clipboard unavailable; wrote {len(slice_lines)} lines to {path}",
            "es": f"(log) portapapeles no disponible; escrito {len(slice_lines)} líneas en {path}",
        }
        print(msg.get(locale, msg["en"]))


def render_intel_list(state, limit: int | None = 20) -> None:
    print("\n=== INTEL ===")
    items = list(state.world.intel)
    if not items:
        print("(no intel)")
        locale = state.os.locale.value
        hint = {
            "en": "Try: intel import <path> | intel show <intel_id> | man intel",
            "es": "Prueba: intel import <path> | intel show <intel_id> | man intel",
        }
        print(hint.get(locale, hint["en"]))
        return
    items.sort(key=lambda i: i.t)
    if limit is not None:
        items = items[:limit]
    id_w = max(2, max((len(item.intel_id) for item in items), default=2))
    print(f"{'ID':<{id_w}}  kind   what                        conf  source                 age")
    now = state.clock.t
    for item in items:
        if item.kind == "link":
            what = f"{item.from_id} -> {item.to_id}"
        elif item.kind == "node":
            what = f"{item.to_id}"
        elif item.kind == "sector":
            what = f"{item.sector_id}"
        elif item.kind == "coord" and item.coord:
            what = f"{item.coord[0]:.2f},{item.coord[1]:.2f},{item.coord[2]:.2f}"
        else:
            what = "?"
        if len(what) > 28:
            what = what[:25] + "..."
        source = item.source_kind
        if item.source_ref:
            source = f"{item.source_kind}@{item.source_ref}"
            if len(source) > 20:
                source = source[:17] + "..."
        age = _format_age_short(now - item.t)
        print(f"{item.intel_id:<{id_w}}  {item.kind:<6} {what:<28} {item.confidence:>4.2f}  {source:<20} {age:>4}")
    locale = state.os.locale.value
    hint = {
        "en": "Try: intel import <path> | intel show <intel_id> | man intel",
        "es": "Prueba: intel import <path> | intel show <intel_id> | man intel",
    }
    print(hint.get(locale, hint["en"]))


def render_intel_show(state, intel_id: str) -> None:
    print("\n=== INTEL DETAIL ===")
    target = None
    for item in state.world.intel:
        if item.intel_id.lower() == intel_id.lower():
            target = item
            break
    if not target:
        print("(intel) not found")
        return
    now = state.clock.t
    age = _format_age_short(now - target.t)
    print(f"id: {target.intel_id}")
    print(f"kind: {target.kind}")
    if target.from_id:
        print(f"from: {target.from_id}")
    if target.to_id:
        print(f"to: {target.to_id}")
    if target.sector_id:
        print(f"sector: {target.sector_id}")
    if target.coord:
        x, y, z = target.coord
        print(f"coord: {x:.3f}, {y:.3f}, {z:.3f}")
    print(f"confidence: {target.confidence:.2f}")
    print(f"source_kind: {target.source_kind}")
    if target.source_ref:
        print(f"source_ref: {target.source_ref}")
    print(f"t: {target.t} (age {age})")
    if target.note:
        print(f"note: {target.note}")


def _handle_intel_export(state, path: str) -> None:
    path = normalize_path(path)
    if not (path.startswith("/logs/nav") or path.startswith("/data/nav")):
        print("intel export: path must be under /logs/nav or /data/nav")
        return
    if path.endswith("/"):
        print("intel export: path must be a file")
        return
    if path.startswith("/logs/nav") and "/logs/nav" not in state.os.fs:
        state.os.fs["/logs/nav"] = FSNode(path="/logs/nav", node_type=FSNodeType.DIR, access=AccessLevel.ENG)
    if not state.world.intel:
        print("intel export: no intel to export")
        return
    lines: list[str] = []
    seen: set[str] = set()
    for item in state.world.intel:
        line = ""
        if item.kind == "link" and item.from_id and item.to_id:
            line = f"LINK: {item.from_id} -> {item.to_id}"
        elif item.kind == "node" and item.to_id:
            line = f"NODE: {item.to_id}"
        elif item.kind == "sector" and item.sector_id:
            line = f"SECTOR: {item.sector_id}"
        elif item.kind == "coord" and item.coord:
            x, y, z = item.coord
            line = f"COORD: {x}, {y}, {z}"
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    if not lines:
        print("intel export: no intel to export")
        return
    content = "\n".join(lines) + "\n"
    state.os.fs[path] = FSNode(path=path, node_type=FSNodeType.FILE, content=content, access=AccessLevel.ENG)
    print(f"(intel) export written to {path} ({len(lines)} lines)")


def _confirm_abandon_drones(state, action) -> bool:
    if not state.ship.drones:
        return True
    current_node = state.world.current_node_id
    out = []
    for d in state.ship.drones.values():
        if d.status in {DroneStatus.DEPLOYED, DroneStatus.DISABLED} and d.location.kind == "world_node":
            out.append(d)
    if not out:
        return True
    locale = state.os.locale.value
    dest = getattr(action, "node_id", "?")
    drone_ids = ", ".join(d.drone_id for d in out)
    msg = {
        "en": f"WARNING: drones not aboard ({drone_ids}). Leaving {current_node} will abandon them. Continue? [y/N] ",
        "es": f"ADVERTENCIA: drones fuera de la nave ({drone_ids}). Al salir de {current_node} quedarán abandonados. ¿Continuar? [s/N] ",
    }.get(locale, "WARNING: drones not aboard. Continue? [y/N] ")
    reply = input(msg).strip().lower()
    if locale == "es":
        return reply in {"s", "si", "sí", "y", "yes"}
    return reply in {"y", "yes"}


def _confirm_travel_abort(state) -> bool:
    locale = state.os.locale.value
    msg = {
        "en": "WARNING: aborting travel. Continue? [y/N] ",
        "es": "ADVERTENCIA: abortar el viaje. ¿Continuar? [s/N] ",
    }.get(locale, "WARNING: aborting travel. Continue? [y/N] ")
    reply = input(msg).strip().lower()
    if locale == "es":
        return reply in {"s", "si", "sí", "y", "yes"}
    return reply in {"y", "yes"}


def _confirm_nav(state, action) -> bool:
    locale = state.os.locale.value
    current_node = state.world.current_node_id
    dest = getattr(action, "node_id", "?")
    out = []
    for d in state.ship.drones.values():
        if d.status in {DroneStatus.DEPLOYED, DroneStatus.DISABLED} and d.location.kind == "world_node":
            out.append(d)
    if out:
        drone_ids = ", ".join(d.drone_id for d in out)
        msg = {
            "en": (
                f"WARNING: confirm nav to {dest}? "
                f"Drones not aboard ({drone_ids}) will be abandoned when leaving {current_node}. Continue? [y/N] "
            ),
            "es": (
                f"ADVERTENCIA: ¿confirmar nav a {dest}? "
                f"Los drones fuera de la nave ({drone_ids}) quedarán abandonados al salir de {current_node}. "
                "¿Continuar? [s/N] "
            ),
        }.get(locale, f"WARNING: confirm nav to {dest}. Continue? [y/N] ")
    else:
        msg = {
            "en": f"WARNING: confirm nav to {dest}. Continue? [y/N] ",
            "es": f"ADVERTENCIA: confirmar nav a {dest}. ¿Continuar? [s/N] ",
        }.get(locale, f"WARNING: confirm nav to {dest}. Continue? [y/N] ")
    reply = input(msg).strip().lower()
    if locale == "es":
        return reply in {"s", "si", "sí", "y", "yes"}
    return reply in {"y", "yes"}


def _resolve_node_id_from_input(state, token: str) -> str | None:
    token_lower = token.lower()
    nodes = state.world.space.nodes
    if token in nodes:
        return token
    # Exact name match (case-insensitive)
    for nid, node in nodes.items():
        if node.name.lower() == token_lower:
            return nid
    # Alias: drop spaces/dashes in name (e.g., Relay-97)
    normalized = token_lower.replace(" ", "").replace("-", "")
    for nid, node in nodes.items():
        name_norm = node.name.lower().replace(" ", "").replace("-", "")
        if name_norm == normalized:
            return nid
    return None

def _resolve_localized_path(state, path: str) -> str:
    path = normalize_path(path)
    if path in state.os.fs:
        return path
    if not path.endswith(".txt"):
        candidate = f"{path}.txt"
        if candidate in state.os.fs:
            return candidate
        candidate = f"{path}.{state.os.locale.value}.txt"
        if candidate in state.os.fs:
            return candidate
        fallback = "en" if state.os.locale.value == "es" else "es"
        candidate = f"{path}.{fallback}.txt"
        if candidate in state.os.fs:
            return candidate
    else:
        base = path[:-4]
        candidate = f"{base}.{state.os.locale.value}.txt"
        if candidate in state.os.fs:
            return candidate
        fallback = "en" if state.os.locale.value == "es" else "es"
        candidate = f"{base}.{fallback}.txt"
        if candidate in state.os.fs:
            return candidate
    return path


def render_ls(state, path: str) -> None:
    path = normalize_path(path)
    entries = list_dir(state.os.fs, path)
    print(f"\n=== LS {path} ===")
    if not entries:
        print("(empty)")
        return
    for name in entries:
        node = state.os.fs.get(normalize_path(f"{path}/{name}"))
        suffix = "/" if node and node.node_type == FSNodeType.DIR else ""
        locked = False
        required = None
        if node:
            required = required_access_label(node)
            locked = required not in state.os.auth_levels
        lock_tag = f" [{required} locked]" if locked and required else ""
        print(f"- {name}{suffix}{lock_tag}")


def render_cat(state, path: str) -> None:
    path = _resolve_localized_path(state, path)
    try:
        content = read_file(state.os.fs, path, state.os.auth_levels)
    except KeyError:
        print("No such file")
        return
    except PermissionError as e:
        required = None
        try:
            required = str(e.args[0])
        except Exception:
            required = None
        if required:
            print(f"Access denied: requires {required}")
        else:
            print("Access denied")
        return
    except IsADirectoryError:
        print(f"{path} is a directory. Try: ls {path}")
        return
    print(f"\n=== CAT {path} ===")
    print(content)
    if _is_intel_path(path):
        added = _auto_import_intel_from_text(state, content, path)
        if added:
            for msg in sorted(set(added)):
                print(msg)


def _mail_headers_from_content(content: str) -> tuple[str | None, str | None]:
    sender: str | None = None
    subject: str | None = None
    for raw in content.splitlines()[:20]:
        line = raw.strip()
        if sender is None and line.upper().startswith("FROM:"):
            sender = line.split(":", 1)[1].strip() or None
            continue
        if subject is None and line.upper().startswith("SUBJ:"):
            subject = line.split(":", 1)[1].strip() or None
            continue
        if sender is not None and subject is not None:
            break
    return sender, subject


def _mail_path_for_base(state, box: str, base: str, entries: list[str]) -> str | None:
    locale = state.os.locale.value
    preferred = f"{base}.{locale}.txt"
    if preferred in entries:
        return f"/mail/{box}/{preferred}"
    generic = f"{base}.txt"
    if generic in entries:
        return f"/mail/{box}/{generic}"
    for alt in ("en", "es"):
        candidate = f"{base}.{alt}.txt"
        if candidate in entries:
            return f"/mail/{box}/{candidate}"
    return None

def render_mailbox(state, box: str) -> None:
    path = f"/mail/{box}"
    print(f"\n=== MAIL {box} ===")
    entries = list_dir(state.os.fs, path)
    if not entries:
        print("(empty)")
        return
    notices = [name for name in entries if name.endswith(".notice.txt")]
    for name in sorted(notices):
        print(f"- {name}")

    base_ids: set[str] = set()
    for name in entries:
        if not name.endswith(".txt"):
            continue
        if name.endswith(".notice.txt"):
            continue
        base = name[:-4]
        if base.endswith(".en") or base.endswith(".es"):
            base = base[:-3]
        if base:
            base_ids.add(base)
    ordered = sorted(
        base_ids,
        key=lambda base: (
            state.os.mail_received_t.get(base, -1.0),
            state.os.mail_received_seq_map.get(base, -1),
            base,
        ),
        reverse=True,
    )
    for base in ordered:
        full_path = _mail_path_for_base(state, box, base, entries)
        sender: str | None = None
        subject: str | None = None
        if full_path:
            node = state.os.fs.get(full_path)
            if node and node.node_type == FSNodeType.FILE:
                sender, subject = _mail_headers_from_content(node.content or "")
        tags: list[str] = []
        if sender:
            tags.append(f"from={sender}")
        if subject:
            tags.append(f"subj={subject}")
        if tags:
            print(f"- {base} ({', '.join(tags)})")
        else:
            print(f"- {base}")

def _latest_mail_id(state, box: str) -> str | None:
    path = f"/mail/{box}"
    entries = list_dir(state.os.fs, path)
    base_ids: set[str] = set()
    for name in entries:
        if not name.endswith(".txt"):
            continue
        if name.endswith(".notice.txt"):
            continue
        base = name[:-4]
        if base.endswith(".en") or base.endswith(".es"):
            base = base[:-3]
        if base:
            base_ids.add(base)
    if not base_ids:
        return None
    best = None
    best_key = None
    for base in base_ids:
        t = state.os.mail_received_t.get(base, -1.0)
        seq = state.os.mail_received_seq_map.get(base, -1)
        key = (t, seq, base)
        if best_key is None or key > best_key:
            best_key = key
            best = base
    return best


def _list_mail_ids(state, box: str) -> list[str]:
    path = f"/mail/{box}"
    try:
        entries = list_dir(state.os.fs, path)
    except Exception:
        return []
    ids = []
    for name in entries:
        if not name.endswith(".txt"):
            continue
        if name.endswith(".notice.txt"):
            continue
        ids.append(name[:-4])
    return sorted(set(ids))


def render_mail_read(state, mail_id: str) -> None:
    base = mail_id
    if mail_id == "latest":
        latest = _latest_mail_id(state, "inbox")
        if not latest:
            print("(no mail)")
            return
        base = latest
    if base.endswith(".txt"):
        base = base[:-4]
    path = f"/mail/inbox/{base}.txt"
    render_cat(state, path)


def _emit_runtime_event(state, events_out, origin: str, event_type: EventType, severity: Severity, source: SourceRef, message: str, data: dict) -> None:
    seq = state.events.next_event_seq
    state.events.next_event_seq += 1
    event = Event(
        event_id=f"E{seq:05d}",
        t=int(state.clock.t),
        type=event_type,
        severity=severity,
        source=source,
        message=message,
        data=data,
    )
    state.events.recent.append(event)
    events_out.append((origin, event))


def _store_recent_events(state, events: list[Event]) -> None:
    for event in events:
        state.events.recent.append(event)
    if len(state.events.recent) > 50:
        state.events.recent = state.events.recent[-50:]


def _render_and_store_events(state, events: list[Event], *, origin: str = "cmd") -> None:
    if not events:
        return
    render_events(state, [(origin, event) for event in events])
    _store_recent_events(state, events)


def _apply_salvage_loot(loop, state, events):
    return


def _hibernate_interrupt_reason(state, step_events: list[Event], wake_on_low_battery: bool) -> str | None:
    if state.os.terminal_lock:
        reason = state.os.terminal_reason or "terminal"
        return f"terminal:{reason}"

    for event in step_events:
        if event.type != EventType.SYSTEM_STATE_CHANGED:
            continue
        if event.source.kind != "ship_system":
            continue
        system = state.ship.systems.get(event.source.id)
        if not system or "critical" not in system.tags:
            continue
        to_state = str(event.data.get("to") or "").lower()
        if to_state in {SystemState.CRITICAL.value, SystemState.OFFLINE.value}:
            return f"critical_system:{system.system_id}:{to_state}"

    if wake_on_low_battery:
        for event in step_events:
            if event.type.value in Balance.HIBERNATE_WAKE_EVENT_TYPES:
                return f"event:{event.type.value}"

    return None


def _hibernate_env_radiation_threshold() -> float:
    return max(0.0, float(Balance.HIBERNATE_WAKE_ENV_RAD_THRESHOLD_RAD_PER_S))


def _hibernate_env_radiation_wake_enabled() -> bool:
    return bool(Balance.HIBERNATE_WAKE_ON_ENV_RAD_THRESHOLD)


def _hibernate_transit_env_threshold_dt(state, max_dt_s: float) -> float | None:
    if not _hibernate_env_radiation_wake_enabled():
        return None
    if max_dt_s <= 0.0 or not state.ship.in_transit:
        return None
    threshold = _hibernate_env_radiation_threshold()
    if threshold <= 0.0:
        return None
    nodes = state.world.space.nodes
    from_node = nodes.get(state.ship.transit_from)
    to_node = nodes.get(state.ship.transit_to)
    if not from_node or not to_node:
        return None
    from_rad = max(0.0, float(from_node.radiation_rad_per_s))
    to_rad = max(0.0, float(to_node.radiation_rad_per_s))
    # Wake is only meaningful when crossing upward into a dangerous band.
    if to_rad <= from_rad:
        return None
    start_t = float(state.ship.transit_start_t)
    end_t = float(state.ship.arrival_t)
    now_t = float(state.clock.t)
    if end_t <= start_t or now_t >= end_t:
        return None
    duration = end_t - start_t
    slope = (to_rad - from_rad) / duration
    if slope <= 0.0:
        return None
    progress_now = max(0.0, min(1.0, (now_t - start_t) / duration))
    rad_now = from_rad + (to_rad - from_rad) * progress_now
    if rad_now >= threshold:
        return None
    t_cross = start_t + (threshold - from_rad) / slope
    if t_cross <= now_t:
        return None
    dt_cross = t_cross - now_t
    if dt_cross <= 0.0 or dt_cross > max_dt_s:
        return None
    return dt_cross


def _hibernate_reached_env_threshold(state) -> bool:
    if not _hibernate_env_radiation_wake_enabled() or not state.ship.in_transit:
        return False
    return float(state.ship.radiation_env_rad_per_s) >= _hibernate_env_radiation_threshold()


def _run_hibernate(loop, years: float, wake_on_low_battery: bool = False) -> None:
    total_s = max(0.0, years * Balance.YEAR_S)
    if total_s <= 0:
        print("hibernate: nothing to do (duration <= 0)")
        return
    events_to_render: list[tuple[str, Event]] = []
    actual_years = years
    start_t = 0.0
    wake_t: float | None = None
    wake_reason: str | None = None
    with loop.with_lock() as locked_state:
        prev_mode = locked_state.ship.op_mode
        prev_source = locked_state.ship.op_mode_source
        start_t = locked_state.clock.t
        start_soc = locked_state.ship.power.e_batt_kwh / locked_state.ship.power.e_batt_max_kwh if locked_state.ship.power.e_batt_max_kwh else 0.0
        start_health = {sid: sys.health for sid, sys in locked_state.ship.systems.items() if "critical" in sys.tags}
    with loop.with_lock() as locked_state:
        _emit_runtime_event(
            locked_state,
            events_to_render,
            "cmd",
            EventType.HIBERNATION_STARTED,
            Severity.INFO,
            SourceRef(kind="ship", id=locked_state.ship.ship_id),
            f"Hibernation for {years:.2f} years",
            data={"years": years},
        )
    was_auto = getattr(loop, "_auto_tick_enabled", True)
    remaining = total_s
    step_events: list[tuple[str, Event]] = []
    woke_early = False
    end_soc = start_soc
    end_health = dict(start_health)
    try:
        with loop.with_lock() as locked_state:
            locked_state.ship.is_hibernating = True
        loop.set_auto_tick(False)
        while remaining > 0:
            step = Balance.HIBERNATE_CHUNK_S if remaining >= Balance.HIBERNATE_CHUNK_S else remaining
            if wake_on_low_battery:
                step = min(step, Balance.HIBERNATE_WAKE_CHECK_S)
            radiation_cross_dt = None
            with loop.with_lock() as locked_state:
                radiation_cross_dt = _hibernate_transit_env_threshold_dt(locked_state, step)
            if radiation_cross_dt is not None:
                step = min(step, max(1.0e-6, radiation_cross_dt))
            ev = loop.step(step)
            step_events.extend([("step", e) for e in ev])
            with loop.with_lock() as locked_state:
                reason = _hibernate_interrupt_reason(locked_state, ev, wake_on_low_battery)
                if not reason and radiation_cross_dt is not None and _hibernate_reached_env_threshold(locked_state):
                    threshold = _hibernate_env_radiation_threshold()
                    reason = f"env_radiation_threshold:{threshold:.4f}"
                if reason:
                    woke_early = True
                    wake_t = locked_state.clock.t
                    wake_reason = reason
            remaining -= step
            if woke_early:
                break
        with loop.with_lock() as locked_state:
            if woke_early:
                if wake_t is not None:
                    elapsed_s = max(0.0, wake_t - start_t)
                else:
                    elapsed_s = total_s - remaining
                actual_years = elapsed_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
            _emit_runtime_event(
                locked_state,
                events_to_render,
                "cmd",
                EventType.HIBERNATION_ENDED,
                Severity.INFO,
                SourceRef(kind="ship", id=locked_state.ship.ship_id),
                f"Hibernation ended after {actual_years:.2f} years",
                data={"years": actual_years},
            )
            end_soc = (
                locked_state.ship.power.e_batt_kwh / locked_state.ship.power.e_batt_max_kwh
                if locked_state.ship.power.e_batt_max_kwh
                else 0.0
            )
            end_health = {sid: sys.health for sid, sys in locked_state.ship.systems.items() if "critical" in sys.tags}
            # Do not change ship_mode; restore previous values.
            locked_state.ship.op_mode = prev_mode
            locked_state.ship.op_mode_source = prev_source
    finally:
        with loop.with_lock() as locked_state:
            locked_state.ship.is_hibernating = False
        loop.set_auto_tick(was_auto)
    filtered = [pair for pair in step_events if pair[1].severity == Severity.CRITICAL or pair[1].type in {EventType.ARRIVED}]
    events_to_render.extend(filtered)
    with loop.with_lock() as locked_state:
        if events_to_render:
            render_events(locked_state, events_to_render)
        recovery_events = ensure_exploration_recovery(locked_state, "hibernate_end")
        _render_and_store_events(locked_state, recovery_events)
        if woke_early:
            locale = locked_state.os.locale.value
            msg = None
            if wake_reason:
                if wake_reason == f"event:{EventType.DRONE_LOW_BATTERY.value}":
                    msg = {
                        "en": "Hibernation interrupted: drone low battery",
                        "es": "Hibernación interrumpida: batería baja en dron",
                    }
                elif wake_reason.startswith("terminal:"):
                    terminal_reason = wake_reason.split(":", 1)[1]
                    if terminal_reason in {"life_support_offline", "life_support_critical"}:
                        msg = {
                            "en": "Hibernation interrupted: life support is no longer viable",
                            "es": "Hibernación interrumpida: el soporte vital ya no es viable",
                        }
                    elif terminal_reason == "core_os_offline":
                        msg = {
                            "en": "Hibernation interrupted: core_os went offline",
                            "es": "Hibernación interrumpida: core_os pasó a offline",
                        }
                elif wake_reason.startswith("critical_system:"):
                    _, system_id, to_state = wake_reason.split(":", 2)
                    msg = {
                        "en": f"Hibernation interrupted: critical system '{system_id}' reached {to_state}",
                        "es": f"Hibernación interrumpida: el sistema crítico '{system_id}' alcanzó {to_state}",
                    }
                elif wake_reason.startswith("env_radiation_threshold:"):
                    threshold_txt = wake_reason.split(":", 1)[1]
                    msg = {
                        "en": f"Hibernation interrupted: ambient radiation reached threshold ({threshold_txt} rad/s)",
                        "es": f"Hibernación interrumpida: la radiación ambiental alcanzó el umbral ({threshold_txt} rad/s)",
                    }
            if not msg:
                msg = {
                    "en": f"Hibernation interrupted: {wake_reason or 'unknown reason'}",
                    "es": f"Hibernación interrumpida: {wake_reason or 'motivo desconocido'}",
                }
            print(f"[WARN] {msg.get(locale, msg['en'])}")
        days = actual_years * (Balance.YEAR_S / Balance.DAY_S)
        print(f"Advanced time by {actual_years:.2f} years ({days:.1f} days).")
        # digest de degradación para críticos
        if start_health:
            print("Hibernate digest (critical systems):")
            for sid, h0 in start_health.items():
                h1 = end_health.get(sid, h0)
                dh = h1 - h0
                print(f"- {sid}: Δhealth={dh:+.3f} now={h1:.3f}")
        print(f"SoC: start={start_soc:.3f} end={end_soc:.3f}")


def _confirm_hibernate_non_cruise(state) -> bool:
    locale = state.os.locale.value
    msg = {
        "en": "WARNING: hibernating while not in CRUISE may increase wear. Continue? [y/N] ",
        "es": "ADVERTENCIA: hibernar fuera de CRUISE puede aumentar el desgaste. ¿Continuar? [s/N] ",
    }.get(locale, "WARNING: hibernating while not in CRUISE may increase wear. Continue? [y/N] ")
    reply = input(msg).strip().lower()
    if locale == "es":
        return reply in {"s", "si", "sí", "y", "yes"}
    return reply in {"y", "yes"}


def _confirm_hibernate_start(state, parsed: Hibernate) -> bool:
    locale = state.os.locale.value
    if parsed.mode == "until_arrival":
        msg = {
            "en": "WARNING: confirm hibernation until arrival. Continue? [y/N] ",
            "es": "ADVERTENCIA: confirmar hibernación hasta la llegada. ¿Continuar? [s/N] ",
        }.get(locale, "WARNING: confirm hibernation until arrival. Continue? [y/N] ")
    else:
        msg = {
            "en": f"WARNING: confirm hibernation for {parsed.years:g}y. Continue? [y/N] ",
            "es": f"ADVERTENCIA: confirmar hibernación durante {parsed.years:g} años. ¿Continuar? [s/N] ",
        }.get(locale, "WARNING: confirm hibernation. Continue? [y/N] ")
    reply = input(msg).strip().lower()
    if locale == "es":
        return reply in {"s", "si", "sí", "y", "yes"}
    return reply in {"y", "yes"}


def _confirm_hibernate_drones(state) -> tuple[bool, bool]:
    deployed = [
        d for d in state.ship.drones.values()
        if d.status in {DroneStatus.DEPLOYED, DroneStatus.DISABLED}
        and d.location.kind in {"world_node", "ship_sector"}
    ]
    if not deployed:
        return True, False
    locale = state.os.locale.value
    drone_ids = ", ".join(d.drone_id for d in deployed)
    msg = {
        "en": f"WARNING: drones deployed ({drone_ids}) may drain batteries during hibernation. Continue? [y/N] ",
        "es": f"ADVERTENCIA: drones desplegados ({drone_ids}) pueden agotar batería durante la hibernación. ¿Continuar? [s/N] ",
    }.get(locale, "WARNING: drones deployed may drain batteries during hibernation. Continue? [y/N] ")
    reply = input(msg).strip().lower()
    if locale == "es":
        ok = reply in {"s", "si", "sí", "y", "yes"}
    else:
        ok = reply in {"y", "yes"}
    if not ok:
        return False, False
    msg2 = {
        "en": "Wake if any drone reaches low battery threshold? [y/N] ",
        "es": "¿Despertar si algún dron alcanza batería baja? [s/N] ",
    }.get(locale, "Wake if any drone reaches low battery threshold? [y/N] ")
    reply2 = input(msg2).strip().lower()
    if locale == "es":
        wake = reply2 in {"s", "si", "sí", "y", "yes"}
    else:
        wake = reply2 in {"y", "yes"}
    return True, wake


def render_about(state, system_id: str) -> None:
    path = _resolve_localized_path(state, f"/manuals/systems/{system_id}.txt")
    if path in state.os.fs:
        render_cat(state, path)
        # Auto-import intel from nav/mail/logs (including remote)
        if _is_intel_path(path):
            content = state.os.fs[path].content
            added = _auto_import_intel_from_text(state, content, path)
            if added:
                for msg in sorted(set(added)):
                    print(msg)
        return
    alert_path = _resolve_localized_path(state, f"/manuals/alerts/{system_id}.txt")
    if alert_path in state.os.fs:
        render_cat(state, alert_path)
        return
    concept_path = _resolve_localized_path(state, f"/manuals/concepts/{system_id}.txt")
    if concept_path in state.os.fs:
        print(f"No system manual for '{system_id}'. Try: man {system_id}")
        return
    print("No manual available. Try: ls /manuals/systems")


def render_man(state, topic: str) -> None:
    cmd_path = _resolve_localized_path(state, f"/manuals/commands/{topic}.txt")
    concept_path = _resolve_localized_path(state, f"/manuals/concepts/{topic}.txt")
    sys_path = _resolve_localized_path(state, f"/manuals/systems/{topic}.txt")
    alert_path = _resolve_localized_path(state, f"/manuals/alerts/{topic}.txt")
    module_path = _resolve_localized_path(state, f"/manuals/modules/{topic}.txt")
    resolved_path = None
    for path in (cmd_path, concept_path, sys_path, alert_path, module_path):
        if path in state.os.fs:
            resolved_path = path
            break
    if not resolved_path:
        print("No manual found")
        return
    try:
        print(f"\n=== MAN {topic} ===")
        print(read_file(state.os.fs, resolved_path, state.os.auth_levels))
    except PermissionError as e:
        required = e.args[0] if e.args else None
        if required:
            print(f"Access denied: requires {required}")
        else:
            print("Access denied")
    except Exception:
        print("No manual found")


def get_power_metrics(state) -> dict:
    p = state.ship.power
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    net_kw = p.p_gen_kw - p.p_load_kw
    deficit = max(0.0, p.p_load_kw - p.p_gen_kw)
    battery_headroom_kw = p.p_discharge_max_kw - deficit
    return {
        "p_gen_kw": p.p_gen_kw,
        "p_load_kw": p.p_load_kw,
        "soc": soc,
        "power_quality": p.power_quality,
        "deficit_ratio": p.deficit_ratio,
        "brownout": p.brownout,
        "p_discharge_max_kw": p.p_discharge_max_kw,
        "p_charge_max_kw": p.p_charge_max_kw,
        "net_kw": net_kw,
        "battery_headroom_kw": battery_headroom_kw,
    }


def render_alert_explain(state, alert_key: str) -> None:
    alert = state.events.alerts.get(alert_key)
    print(f"\n=== ALERT EXPLAIN: {alert_key} ===")
    if alert:
        if alert.is_active:
            print(
                f"Severity: {alert.severity.value}   Active: True   "
                f"Unacked while active: {_format_eta_short(alert.unacked_s, state.os.locale.value)}"
            )
        else:
            print(
                f"Severity: {alert.severity.value}   Active: False (cleared)   "
                f"Unacked while active: {_format_eta_short(alert.unacked_s, state.os.locale.value)}"
            )
    else:
        print("Severity: unknown   Active: unknown   Unacked: unknown")

    manual_path = _resolve_localized_path(state, f"/manuals/alerts/{alert_key}.txt")
    if manual_path not in state.os.fs:
        fallback = f"/manuals/alerts/{alert_key}.en.txt"
        if fallback in state.os.fs:
            manual_path = fallback
    try:
        print(read_file(state.os.fs, manual_path, state.os.auth_levels))
    except Exception:
        print("(no manual found)")

    metrics = get_power_metrics(state)
    print("Current values:")
    print(
        f"- P_gen={metrics['p_gen_kw']:.2f}kW  "
        f"P_load={metrics['p_load_kw']:.2f}kW  "
        f"SoC={metrics['soc']:.2f}  "
        f"Q={metrics['power_quality']:.2f}  "
        f"deficit_ratio={metrics['deficit_ratio']:.2f}  "
        f"brownout={metrics['brownout']}"
    )
    if alert_key == "power_net_deficit":
        capacity = metrics["p_gen_kw"] + metrics["p_discharge_max_kw"]
        print(f"- capacity={capacity:.2f}kW (P_gen + P_discharge_max)")
        net = metrics["net_kw"]
        print(f"- net={net:+.2f}kW")
        headroom = metrics["battery_headroom_kw"]
        over = " (over limit)" if headroom < 0 else ""
        print(f"- battery_headroom={headroom:.2f}kW{over}")
        print("- condition: P_load > P_gen (battery may cover until headroom exhausted)")
    if alert_key == "low_power_quality":
        print(f"- threshold={Balance.LOW_POWER_QUALITY_THRESHOLD:.2f}")
    if alert_key == "power_bus_instability":
        dist = state.ship.systems.get("energy_distribution")
        if dist:
            print(f"- energy_distribution state={dist.state.value} health={dist.health:.2f}")
        if alert:
            elapsed = max(0, int(state.clock.t) - alert.first_seen_t)
            print(f"- time_since_first_seen={elapsed}s")
    if alert_key == "drone_bay_maintenance_blocked":
        locale = state.os.locale.value
        charge_reason_labels = {
            "drone_bay_offline": {"en": "drone_bay is OFFLINE", "es": "drone_bay está OFFLINE"},
            "energy_distribution_offline": {
                "en": "energy_distribution is OFFLINE",
                "es": "energy_distribution está OFFLINE",
            },
            "insufficient_net_power": {
                "en": "insufficient net power for charging thresholds",
                "es": "potencia neta insuficiente para los umbrales de carga",
            },
        }
        repair_reason_labels = {
            "drone_bay_offline": {"en": "drone_bay is OFFLINE", "es": "drone_bay está OFFLINE"},
            "energy_distribution_offline": {
                "en": "energy_distribution is OFFLINE",
                "es": "energy_distribution está OFFLINE",
            },
            "insufficient_scrap": {
                "en": "not enough scrap for passive repair cost",
                "es": "no hay chatarra suficiente para el coste de reparación pasiva",
            },
        }

        data = alert.data if alert else {}
        if data:
            bay_state = data.get("bay_state", "?")
            dist_off = bool(data.get("distribution_offline", False))
            print(f"- bay_state={bay_state}  distribution_offline={dist_off}")
            print(
                f"- docked_in_bay={int(data.get('docked_in_bay', 0))}  "
                f"needs_charge={int(data.get('needs_charge_count', 0))}  "
                f"needs_repair={int(data.get('needs_repair_count', 0))}"
            )
            print(
                f"- charge_possible={bool(data.get('charge_possible', False))}  "
                f"repair_possible={bool(data.get('repair_possible', False))}  "
                f"decon_possible={bool(data.get('decon_possible', False))}"
            )
            ckey = str(data.get("charge_block_reason", "") or "")
            if ckey:
                cmsg = charge_reason_labels.get(ckey, {}).get(locale, ckey)
                print(f"- charge_block_reason={cmsg}")
            rkey = str(data.get("repair_block_reason", "") or "")
            if rkey:
                rmsg = repair_reason_labels.get(rkey, {}).get(locale, rkey)
                print(f"- repair_block_reason={rmsg}")
            print(
                f"- net_kw={float(data.get('net_kw', metrics['net_kw'])):+.2f}kW  "
                f"SoC={float(data.get('soc', metrics['soc'])):.2f}  "
                f"scrap={int(data.get('scrap_available', state.ship.cargo_scrap))}  "
                f"repair_scrap_cost={int(data.get('scrap_required_per_tick', 0))}"
            )

        print("Battery charging conditions:")
        print("- Drone must be docked in drone_bay and battery below its effective maximum")
        print("- drone_bay must not be OFFLINE")
        print("- energy_distribution must not be OFFLINE")
        print(
            f"- Power gate: net >= {Balance.DRONE_CHARGE_KW:.2f}kW (normal charge), or "
            f"SoC > 0 with net >= {Balance.DRONE_CHARGE_NET_MIN_KW:.2f}kW (slow charge)"
        )
        print("Integrity passive-repair conditions:")
        print("- Drone must be docked in drone_bay and integrity below its effective maximum")
        print("- drone_bay and energy_distribution must be available (not OFFLINE)")
        print("- Ship must have enough scrap for passive repair cost of the current bay state")
        print("Drone decontamination conditions:")
        print("- Drone must be docked in drone_bay")
        print("- drone_bay must not be OFFLINE")
        print("- energy_distribution must not be OFFLINE")
        print("- Decontamination does not require positive net power or scrap")


def _known_contact_ids_for_completion(state) -> list[str]:
    known_ids = (
        state.world.known_nodes
        if hasattr(state.world, "known_nodes") and state.world.known_nodes
        else state.world.known_contacts
    )
    return sorted(c for c in known_ids if c != "UNKNOWN_00")


def _dock_targets_for_completion(state) -> list[str]:
    current_node_id = getattr(state.world, "current_node_id", "")
    if not current_node_id or current_node_id == "UNKNOWN_00":
        return []
    node = state.world.space.nodes.get(current_node_id)
    if not node or node.kind in {"origin", "transit"}:
        return []
    return [current_node_id]


def _route_solve_targets_for_completion(state) -> list[str]:
    current_node_id = getattr(state.world, "current_node_id", "")
    if not current_node_id or current_node_id == "UNKNOWN_00":
        return []
    known_routes = set(state.world.known_links.get(current_node_id, set()))
    return [
        node_id
        for node_id in _known_contact_ids_for_completion(state)
        if node_id != current_node_id and node_id not in known_routes
    ]


def _travel_targets_for_completion(state) -> list[str]:
    current_node_id = getattr(state.world, "current_node_id", "")
    if not current_node_id or current_node_id == "UNKNOWN_00":
        return []
    candidates = [
        node_id
        for node_id in sorted(state.world.known_links.get(current_node_id, set()))
        if node_id != current_node_id and node_id != "UNKNOWN_00"
    ]
    if (
        getattr(state.world, "active_tmp_node_id", None)
        and current_node_id == state.world.active_tmp_node_id
    ):
        allowed = {state.world.active_tmp_from, state.world.active_tmp_to}
        candidates = [node_id for node_id in candidates if node_id in allowed]
    return candidates


def _drone_local_world_node_targets_for_completion(state) -> list[str]:
    # Drone world interactions are local to the ship position (orbit/docked node).
    candidates: list[str] = []
    current_node_id = getattr(state.world, "current_node_id", "")
    if current_node_id and current_node_id != "UNKNOWN_00":
        node = state.world.space.nodes.get(current_node_id)
        if node and node.kind != "transit":
            candidates.append(current_node_id)
    docked_node_id = getattr(state.ship, "docked_node_id", None)
    if (
        docked_node_id
        and docked_node_id != "UNKNOWN_00"
        and docked_node_id in state.world.space.nodes
    ):
        candidates.append(docked_node_id)
    return list(dict.fromkeys(candidates))


def _drone_ship_sector_targets_for_completion(state) -> list[str]:
    return sorted(s for s in state.ship.sectors.keys() if s != "UNKNOWN_00")


def _drone_move_targets_for_completion(state) -> list[str]:
    # Single extension point for future docked-node interiors.
    targets = _drone_local_world_node_targets_for_completion(state) + _drone_ship_sector_targets_for_completion(state)
    return list(dict.fromkeys(targets))


def _drone_deploy_targets_for_completion(state) -> list[str]:
    # Same contextual targeting as move for now; separated for future divergence.
    return _drone_move_targets_for_completion(state)


def main() -> None:
    from retorno.cli.parser import ParseError, parse_command, format_parse_error

    parser = argparse.ArgumentParser(description="RETORNO (CLI)")
    parser.add_argument(
        "--new-game",
        "--new",
        action="store_true",
        help="Start a new game and ignore existing save slot.",
    )
    parser.add_argument(
        "--save-path",
        default=None,
        help="Override save slot path (default: ~/.retorno/savegame.dat).",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Save profile name (stored under ~/.retorno/users/<user>/savegame.dat).",
    )
    args = parser.parse_args()

    if not isinstance(sys.stdout, _TeeStdout):
        sys.stdout = _TeeStdout(sys.stdout, _LOG_BUFFER)
    if os.environ.get("RETORNO_DEBUG_COMPLETER", "").strip().lower() in {"1", "true", "yes"}:
        try:
            if hasattr(sys.stdout, "isatty") and not sys.stdout.isatty():
                sys.stderr.write("[DEBUG] stdout is not a TTY; readline may disable completion/history\n")
        except Exception:
            pass

    engine = Engine()
    scenario = os.environ.get("RETORNO_SCENARIO", "prologue").lower()
    env_force_new = os.environ.get("RETORNO_NEW_GAME", "").strip().lower() in {"1", "true", "yes", "on"}
    force_new_game = args.new_game or env_force_new
    try:
        profile_user = normalize_user_id(args.user)
    except SaveLoadError as exc:
        print(f"[ERROR] {exc}")
        return
    if force_new_game and save_exists(args.save_path, user=profile_user):
        save_path = resolve_save_path(args.save_path, user=profile_user)
        try:
            reply = input(f"[WARN] Existing save found at {save_path}. Start a new game anyway? [y/N]: ").strip().lower()
        except EOFError:
            reply = ""
        if reply not in {"y", "yes", "s", "si", "sí"}:
            print("Cancelled.")
            return

    play_startup_sequence = False
    startup_message = ""
    startup_audio_context = "load_game"
    if scenario in {"sandbox", "dev"}:
        state = create_initial_state_sandbox()
        play_startup_sequence = True
        startup_audio_context = "new_game"
        startup_message = f"[INFO] Scenario '{scenario}' started as new game (save slot bypassed)."
    elif force_new_game:
        state = create_initial_state_prologue()
        play_startup_sequence = True
        startup_audio_context = "new_game"
        startup_message = "[INFO] Started new game (save slot ignored by --new-game/RETORNO_NEW_GAME)."
    else:
        try:
            loaded: LoadGameResult | None = load_single_slot(args.save_path, user=profile_user)
        except SaveLoadError as exc:
            state = create_initial_state_prologue()
            play_startup_sequence = True
            startup_audio_context = "new_game"
            startup_message = f"[WARN] Could not load saved game ({exc}). Starting new game."
        else:
            if loaded is None:
                state = create_initial_state_prologue()
                play_startup_sequence = True
                startup_audio_context = "new_game"
                startup_message = "[INFO] No saved game found. Starting new game."
            else:
                state = loaded.state
                startup_audio_context = "load_game"
                if loaded.source == "backup":
                    startup_message = f"[WARN] Main save unreadable. Loaded backup: {loaded.path}"
                else:
                    startup_message = f"[INFO] Loaded saved game: {loaded.path}"

    audio_warning = ""
    try:
        audio_manager = AudioManager(load_audio_config())
    except AudioConfigError as exc:
        audio_manager = None
        audio_warning = f"[WARN] Audio disabled: {exc}"
    else:
        audio_warning = audio_manager.notice or ""

    loop = GameLoop(engine, state, tick_s=1.0)
    loop.step(1.0)
    audio_enabled, ambient_enabled = audio_flags(state.os)
    if audio_manager is not None:
        audio_manager.prepare_session(audio_enabled, ambient_enabled, startup_audio_context)
        audio_manager.start(audio_enabled, ambient_enabled)
        audio_manager.play_startup(audio_enabled, startup_audio_context)
        audio_warning = audio_manager.consume_notice() or audio_warning
    if startup_message:
        print(startup_message)
    if play_startup_sequence:
        _maybe_run_startup_sequence(state.os.locale.value)
    if audio_warning:
        print(audio_warning)
    if not state.os.debug_enabled:
        loop.set_auto_tick(True)
        loop.start()
    else:
        loop.set_auto_tick(False)

    base_commands = [
        "help",
        "clear",
        "ls",
        "cat",
        "man",
        "about",
        "config",
        "mail",
        "intel",
        "status",
        "jobs",
        "power",
        "alerts",
        "logs",
        "log",
        "scan",
        "map",
        "routes",
        "graph",
        "path",
        "locate",
        "ship",
        "nav",
        "navigation",
        "uplink",
        "relay",
        "dock",
        "undock",
        "travel",
        "route",
        "salvage",
        "diag",
        "boot",
        "repair",
        "inventory",
        "cargo",
        "module",
        "modules",
        "shutdown",
        "system",
        "hibernate",
        "drone",
        "job",
        "wait",
        "debug",
        "exit",
        "quit",
    ]

    debug_completer = os.environ.get("RETORNO_DEBUG_COMPLETER", "").strip().lower() in {"1", "true", "yes"}

    def _completer(text: str, state_idx: int) -> str | None:
        try:
            buf = readline.get_line_buffer()
            tokens = buf.split()
            if buf.endswith(" "):
                tokens.append("")
            token = ""
            if buf and not buf.endswith(" ") and tokens:
                token = tokens[-1]
            if not tokens:
                candidates = [c for c in base_commands if c.startswith(text)]
            else:
                cmd = tokens[0]
                candidates = []
                with loop.with_lock() as locked_state:
                    systems = list(locked_state.ship.systems.keys())
                    drones = list(locked_state.ship.drones.keys())
                    contacts = _known_contact_ids_for_completion(locked_state)
                    dock_targets = _dock_targets_for_completion(locked_state)
                    route_solve_targets = _route_solve_targets_for_completion(locked_state)
                    travel_targets = _travel_targets_for_completion(locked_state)
                    drone_local_world_targets = _drone_local_world_node_targets_for_completion(locked_state)
                    drone_move_targets = _drone_move_targets_for_completion(locked_state)
                    drone_deploy_targets = _drone_deploy_targets_for_completion(locked_state)
                    modules_catalog = sorted(load_modules().keys())
                    modules = list(set(locked_state.ship.cargo_modules or locked_state.ship.manifest_modules))
                    services = []
                    for sys in locked_state.ship.systems.values():
                        if sys.service and sys.service.is_installed:
                            services.append(sys.service.service_name)
                    fs_paths = list(locked_state.os.fs.keys())

                if len(tokens) == 1:
                    candidates = [c for c in base_commands if c.startswith(text)]
                elif cmd == "help":
                    if len(tokens) == 2:
                        candidates = [c for c in ["--verbose", "-v", "--no-verbose"] if c.startswith(text)]
                elif cmd == "diag" or cmd == "about" or cmd == "locate":
                    candidates = [s for s in systems if s.startswith(text)]
                elif cmd == "boot":
                    candidates = [s for s in services if s.startswith(text)]
                elif cmd in {"ls", "cat"}:
                    path_text = token or text
                    if "/" in path_text:
                        dir_part, base_part = path_text.rsplit("/", 1)
                        dir_path = normalize_path(dir_part or "/")
                        prefix = base_part
                    else:
                        dir_path = "/"
                        prefix = path_text
                    try:
                        entries = list_dir(locked_state.os.fs, dir_path)
                    except Exception:
                        entries = []
                    for name in entries:
                        if not name.startswith(prefix):
                            continue
                        if "/" in path_text:
                            if path_text.startswith("/"):
                                full = normalize_path(f"{dir_path}/{name}")
                            else:
                                full = f"{dir_part}/{name}" if dir_part else name
                            candidates.append(full)
                        else:
                            candidates.append(name)
                elif cmd == "repair":
                    if len(tokens) == 2:
                        candidates = [d for d in drones if d.startswith(text)] + [s for s in systems if s.startswith(text)]
                    elif len(tokens) == 3:
                        if tokens[1] in systems:
                            candidates = [c for c in ["--selftest"] if c.startswith(text)]
                        else:
                            candidates = [s for s in systems if s.startswith(text)]
                elif cmd == "dock":
                    candidates = [c for c in dock_targets if c.startswith(text)]
                elif cmd == "undock":
                    candidates = []
                elif cmd in {"nav", "navigation", "travel"}:
                    def _travel_targets(prefix: str) -> list[str]:
                        return [c for c in travel_targets if c.startswith(prefix)]

                    if len(tokens) == 2:
                        base_opts = ["map", "abort", "--no-cruise"]
                        if cmd == "nav":
                            base_opts.extend(["sectors", "routes", "contacts", "graph", "galaxy"])
                        candidates = [c for c in base_opts if c.startswith(text)]
                        candidates += _travel_targets(text)
                    elif len(tokens) == 3 and tokens[1] == "map":
                        candidates = [c for c in ["sectors", "graph", "path", "routes", "contacts", "galaxy"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "map" and tokens[2] == "galaxy":
                        candidates = [c for c in ["sector", "local", "regional", "global"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "map" and tokens[2] == "contacts":
                        candidates = [c for c in ["sector"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "map" and tokens[2] in {"graph", "path"}:
                        candidates = _travel_targets(text)
                    elif len(tokens) == 3 and tokens[1] == "--no-cruise":
                        candidates = _travel_targets(text)
                    elif len(tokens) == 3 and tokens[1] == "contacts":
                        candidates = [c for c in ["sector"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "graph":
                        candidates = _travel_targets(text)
                    elif len(tokens) == 3 and tokens[1] == "galaxy":
                        candidates = [c for c in ["sector", "local", "regional", "global"] if c.startswith(text)]
                    else:
                        candidates = _travel_targets(text)
                elif cmd == "map":
                    if len(tokens) == 2:
                        candidates = [c for c in ["path"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "path":
                        candidates = [c for c in contacts if c.startswith(text)]
                elif cmd == "ship":
                    if len(tokens) == 2:
                        candidates = [c for c in ["sectors", "survey", "map"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "survey":
                        ship_aliases = [locked_state.ship.ship_id] if locked_state.ship.ship_id.startswith(text) else []
                        ship_aliases += [s for s in ["RETORNO_SHIP"] if s.startswith(text)]
                        candidates = [c for c in contacts if c.startswith(text)] + ship_aliases
                elif cmd == "graph":
                    if len(tokens) == 2:
                        candidates = [c for c in contacts if c.startswith(text)]
                elif cmd == "path":
                    if len(tokens) == 2:
                        candidates = [c for c in contacts if c.startswith(text)]
                elif cmd == "power":
                    if len(tokens) == 2:
                        candidates = [c for c in ["status", "plan", "on", "off"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] in {"off", "on"}:
                        candidates = [s for s in systems if s.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "plan":
                        candidates = [c for c in ["cruise", "normal"] if c.startswith(text)]
                elif cmd == "debug":
                    if len(tokens) == 2:
                        candidates = [
                            c
                            for c in ["on", "off", "status", "scenario", "seed", "deadnodes", "arcs", "lore", "modules", "galaxy", "add"]
                            if c.startswith(text)
                        ]
                    elif len(tokens) == 3 and tokens[1] == "scenario":
                        candidates = [c for c in ["prologue", "sandbox", "dev"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "add":
                        candidates = [c for c in ["scrap", "module", "drone", "drones"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "add" and tokens[2] == "module":
                        candidates = [m for m in modules_catalog if m.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "add" and tokens[2] in {"scrap", "drone", "drones"}:
                        candidates = [c for c in ["1", "5", "10", "50", "100"] if c.startswith(text)]
                    elif len(tokens) == 5 and tokens[1] == "add" and tokens[2] == "module":
                        candidates = [c for c in ["1", "2", "5", "10"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "galaxy":
                        candidates = [c for c in ["map"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "galaxy" and tokens[2] == "map":
                        candidates = [c for c in ["sector", "local", "regional", "global"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "worldgen":
                        candidates = [c for c in ["sector"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "worldgen" and tokens[2] == "sector":
                        sector_candidates = set(locked_state.world.generated_sectors)
                        sector_candidates.add(sector_id_for_pos(*locked_state.world.current_pos_ly))
                        candidates = [sid for sid in sorted(sector_candidates) if sid.startswith(text.upper())]
                    elif len(tokens) == 3 and tokens[1] == "graph":
                        candidates = [c for c in ["all"] if c.startswith(text)]
                elif cmd == "module":
                    if len(tokens) == 2:
                        candidates = [c for c in ["inspect"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "inspect":
                        candidates = [m for m in modules_catalog if m.startswith(text)]
                elif cmd == "inventory":
                    if len(tokens) == 2:
                        candidates = [c for c in ["audit"] if c.startswith(text)]
                elif cmd == "cargo":
                    if len(tokens) == 2:
                        candidates = [c for c in ["audit"] if c.startswith(text)]
                elif cmd == "job":
                    if len(tokens) == 2:
                        candidates = [c for c in ["cancel"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "cancel":
                        candidates = [jid for jid in active_job_display_ids(locked_state.jobs) if jid.startswith(text)]
                elif cmd == "log":
                    if len(tokens) == 2:
                        candidates = [c for c in ["copy"] if c.startswith(text)]
                elif cmd == "jobs":
                    if len(tokens) == 2:
                        candidates = [c for c in ["all", "5", "10", "20", "50"] if c.startswith(text)]
                elif cmd == "intel":
                    if len(tokens) == 2:
                        candidates = [c for c in ["show", "import", "export", "all"] if c.startswith(text)] + [t for t in ["10", "20", "50"] if t.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "show":
                        candidates = [i.intel_id for i in locked_state.world.intel if i.intel_id.startswith(text.upper())]
                    elif len(tokens) == 3 and tokens[1] in {"import", "export"}:
                        path_text = token or text
                        if "/" in path_text:
                            dir_part, base_part = path_text.rsplit("/", 1)
                            dir_path = normalize_path(dir_part or "/")
                            prefix = base_part
                        else:
                            dir_path = "/"
                            prefix = path_text
                        try:
                            entries = list_dir(locked_state.os.fs, dir_path)
                        except Exception:
                            entries = []
                        for name in entries:
                            if not name.startswith(prefix):
                                continue
                            if "/" in path_text:
                                if path_text.startswith("/"):
                                    full = normalize_path(f"{dir_path}/{name}")
                                else:
                                    full = f"{dir_part}/{name}" if dir_part else name
                                candidates.append(full)
                            else:
                                candidates.append(name)
                elif cmd == "shutdown":
                    if len(tokens) == 2:
                        candidates = [s for s in systems if s.startswith(text)]
                elif cmd == "system":
                    if len(tokens) == 2:
                        candidates = [c for c in ["off", "on"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] in {"off", "on"}:
                        candidates = [s for s in systems if s.startswith(text)]
                elif cmd == "hibernate":
                    if len(tokens) == 2:
                        candidates = [c for c in ["until_arrival"] if c.startswith(text)]
                elif cmd == "man":
                    topics: set[str] = set()
                    for path in fs_paths:
                        if (
                            path.startswith("/manuals/commands/")
                            or path.startswith("/manuals/systems/")
                            or path.startswith("/manuals/alerts/")
                            or path.startswith("/manuals/modules/")
                            or path.startswith("/manuals/concepts/")
                        ):
                            name = path.rsplit("/", 1)[-1]
                            if name.endswith(".txt"):
                                name = name[:-4]
                            if name.endswith(".en") or name.endswith(".es"):
                                name = name[:-3]
                            topics.add(name)
                    candidates = [t for t in sorted(topics) if t.startswith(text)]
                elif cmd == "about":
                    topics = set(systems)
                    topics.update(locked_state.events.alerts.keys())
                    for path in fs_paths:
                        if path.startswith("/manuals/alerts/"):
                            name = path.rsplit("/", 1)[-1]
                            if name.endswith(".txt"):
                                name = name[:-4]
                            if name.endswith(".en") or name.endswith(".es"):
                                name = name[:-3]
                            topics.add(name)
                        if path.startswith("/manuals/modules/"):
                            name = path.rsplit("/", 1)[-1]
                            if name.endswith(".txt"):
                                name = name[:-4]
                            if name.endswith(".en") or name.endswith(".es"):
                                name = name[:-3]
                            topics.add(name)
                    candidates = [t for t in sorted(topics) if t.startswith(text)]
                elif cmd == "alerts":
                    if len(tokens) == 2:
                        candidates = [c for c in ["explain"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "explain":
                        candidates = [k for k in locked_state.events.alerts.keys() if k.startswith(text)]
                elif cmd == "uplink":
                    candidates = []
                elif cmd == "relay":
                    if len(tokens) == 2:
                        candidates = [c for c in ["uplink"] if c.startswith(text)]
                elif cmd == "drone":
                    if len(tokens) == 2:
                        candidates = [
                            c for c in ["status", "deploy", "deploy!", "move", "survey", "reboot", "recall", "autorecall", "repair", "install", "uninstall", "salvage"]
                            if c.startswith(text)
                        ]
                    elif len(tokens) == 3 and tokens[1] in {"status", "deploy", "deploy!", "reboot", "autorecall", "repair", "move", "install", "uninstall", "survey"}:
                        candidates = [d for d in drones if d.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "recall":
                        candidates = [c for c in ["all"] if c.startswith(text)]
                        candidates += [d for d in drones if d.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] in {"deploy", "deploy!"}:
                        candidates = [t for t in drone_deploy_targets if t.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "move":
                        ship_aliases = [locked_state.ship.ship_id] if locked_state.ship.ship_id.startswith(text) else []
                        local_targets = [t for t in drone_move_targets if t.startswith(text)]
                        candidates = list(dict.fromkeys(local_targets + ship_aliases))
                    elif len(tokens) == 4 and tokens[1] == "autorecall":
                        candidates = [c for c in ["on", "off", "10"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "install":
                        candidates = [m for m in modules if m.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "uninstall":
                        target_id = tokens[2]
                        target_drone = locked_state.ship.drones.get(target_id)
                        ship_installed = sorted(set(locked_state.ship.installed_modules or []))
                        if target_drone:
                            installed = sorted(set(target_drone.installed_modules or []))
                            all_candidates = list(dict.fromkeys(ship_installed + installed))
                            candidates = [m for m in all_candidates if m.startswith(text)]
                        else:
                            candidates = [m for m in ship_installed if m.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "repair":
                        candidates = [x for x in sorted(set(systems) | set(drones)) if x.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "survey":
                        candidates = [c for c in drone_local_world_targets if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "salvage":
                        candidates = [c for c in ["scrap", "module", "modules", "drone", "drones", "data"] if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "salvage":
                        candidates = [d for d in drones if d.startswith(text)]
                    elif len(tokens) == 5 and tokens[1] == "salvage":
                        candidates = [c for c in drone_local_world_targets if c.startswith(text)]
                elif cmd == "salvage":
                    if len(tokens) == 2:
                        candidates = [c for c in ["scrap", "module", "modules", "drone", "drones", "data"] if c.startswith(text)]
                    elif len(tokens) == 3:
                        candidates = [d for d in drones if d.startswith(text)]
                    elif len(tokens) == 4:
                        candidates = [c for c in drone_local_world_targets if c.startswith(text)]
                elif cmd == "route":
                    if len(tokens) == 2:
                        candidates = [c for c in ["solve"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "solve":
                        candidates = [c for c in route_solve_targets if c.startswith(text)]
                elif cmd == "contacts":
                    if len(tokens) == 2:
                        candidates = [c for c in ["sector"] if c.startswith(text)]
                elif cmd == "config":
                    if len(tokens) == 2:
                        candidates = [c for c in ["set", "show"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "set":
                        candidates = [c for c in config_keys() if c.startswith(text)]
                    elif len(tokens) == 4 and tokens[1] == "set":
                        candidates = [c for c in config_value_choices(tokens[2]) if c.startswith(text)]
                elif cmd == "mail":
                    if len(tokens) == 2:
                        candidates = [c for c in ["inbox", "read"] if c.startswith(text)]
                    elif len(tokens) == 3 and tokens[1] == "read":
                        mail_ids = _list_mail_ids(locked_state, "inbox")
                        candidates = [c for c in ["latest"] + mail_ids if c.startswith(text)]
            if debug_completer and state_idx == 0:
                try:
                    sys.stderr.write(f"[DEBUG] completer call text='{text}' tokens={tokens} candidates={len(candidates)}\n")
                except Exception:
                    pass
            if state_idx < len(candidates):
                return candidates[state_idx]
            return None
        except Exception as e:
            try:
                with loop.with_lock() as locked_state:
                    if locked_state.os.debug_enabled:
                        sys.stderr.write(f"[DEBUG] completer error: {e}\\n")
            except Exception:
                pass
            return None

    # Minimal readline setup (matches the previously working behavior).
    readline.set_completer_delims(" \t\n")
    readline.set_completer(_completer)
    if "libedit" in (readline.__doc__ or "").lower():
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    if debug_completer and hasattr(readline, "get_completer_delims"):
        try:
            sys.stderr.write(
                f"[DEBUG] completer set={readline.get_completer() is not None} delims='{readline.get_completer_delims()}'\n"
            )
        except Exception:
            pass

    def _drain_auto_events() -> None:
        auto_ev = loop.drain_events()
        if auto_ev:
            audio_enabled = False
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, auto_ev)
                render_events(locked_state, auto_ev)
                audio_enabled = locked_state.os.audio.enabled
            if audio_manager is not None:
                audio_manager.handle_event_batch(audio_enabled, auto_ev)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)

    # print("RETORNO (prologue)")
    # print("\nTip: cat /mail/inbox/0000.notice.txt")
    with loop.with_lock() as locked_state:
        render_status(locked_state)
        render_alerts(locked_state)

    did_persist_on_exit = False

    def _stop_and_persist() -> None:
        nonlocal did_persist_on_exit
        if did_persist_on_exit:
            return
        loop.stop()
        if audio_manager is not None:
            audio_manager.shutdown()
        try:
            with loop.with_lock() as locked_state:
                saved_path = save_single_slot(locked_state, args.save_path, user=profile_user)
            print(f"[INFO] Game saved: {saved_path}")
        except SaveLoadError as exc:
            print(f"[WARN] Failed to save game: {exc}")
        did_persist_on_exit = True

    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print("\n(exit)")
            _stop_and_persist()
            break

        try:
            parsed = parse_command(line)
        except ParseError as e:
            with loop.with_lock() as locked_state:
                locale = locked_state.os.locale.value
            print(f"ParseError: {format_parse_error(e, locale)}")
            continue

        if parsed is None:
            # sin comando: mundo sigue si quieres; aquí no tickeamos automáticamente
            continue

        with loop.with_lock() as locked_state:
            block_msg = _command_blocked_message(locked_state, parsed)
            audio_enabled = locked_state.os.audio.enabled
        if block_msg:
            print(block_msg)
            if audio_manager is not None:
                severity = Severity.WARN if "Action blocked" in block_msg or "Acción bloqueada" in block_msg else Severity.INFO
                audio_manager.play_event(audio_enabled, EventType.BOOT_BLOCKED, severity)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)
            continue

        ev = loop.drain_events()
        if ev:
            audio_enabled = False
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, ev)
                render_events(locked_state, ev)
                audio_enabled = locked_state.os.audio.enabled
            if audio_manager is not None:
                audio_manager.handle_event_batch(audio_enabled, ev)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)

        if parsed == "EXIT":
            _stop_and_persist()
            break
        if parsed == "HELP":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                locale = locked_state.os.locale.value
                verbose = resolve_help_verbose(locked_state.os)
            print_help(locale, verbose=verbose)
            continue
        if parsed == "HELP_VERBOSE":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                locale = locked_state.os.locale.value
            print_help(locale, verbose=True)
            continue
        if parsed == "HELP_NO_VERBOSE":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                locale = locked_state.os.locale.value
            print_help(locale, verbose=False)
            continue
        if parsed == "CLEAR":
            print("\033[2J\033[H", end="")
            continue
        if parsed == "CONFIG_SHOW":
            backend_name = audio_manager.backend.name if audio_manager is not None else None
            runtime_status = None
            if audio_manager is None:
                runtime_status = "disabled"
            elif audio_manager.notice:
                runtime_status = "degraded"
            with loop.with_lock() as locked_state:
                for line in config_show_lines(
                    locked_state.os,
                    audio_backend=backend_name,
                    audio_runtime_status=runtime_status,
                ):
                    print(line)
            continue
        if parsed == "AUTH_STATUS":
            with loop.with_lock() as locked_state:
                render_auth_status(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "CONFIG_SET":
            key, value = parsed[1], parsed[2]
            with loop.with_lock() as locked_state:
                message = apply_config_value(locked_state.os, key, value)
                audio_enabled, ambient_enabled = audio_flags(locked_state.os)
                print(message)
            if audio_manager is not None and key in {"audio", "ambientsound"}:
                audio_manager.apply_preferences(audio_enabled, ambient_enabled)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "MAIL_LIST":
            with loop.with_lock() as locked_state:
                render_mailbox(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "MAIL_READ":
            with loop.with_lock() as locked_state:
                render_mail_read(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_IMPORT":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                _handle_intel_import(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG":
            mode = parsed[1]
            if mode == "status":
                with loop.with_lock() as locked_state:
                    print("DEBUG" if locked_state.os.debug_enabled else "NORMAL")
                continue
            if mode == "on":
                with loop.with_lock() as locked_state:
                    locked_state.os.debug_enabled = True
                loop.set_auto_tick(False)
                print("DEBUG mode enabled")
                continue
            if mode == "off":
                with loop.with_lock() as locked_state:
                    locked_state.os.debug_enabled = False
                loop.set_auto_tick(True)
                loop.start()
                print("DEBUG mode disabled")
                continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ARCS":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug arcs: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_arcs(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_LORE":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug lore: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_lore(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_DEADNODES":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug deadnodes: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_deadnodes(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_MODULES":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug modules: available only in DEBUG mode. Use: debug on")
                    continue
                render_modules_catalog(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_GALAXY":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug galaxy: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_galaxy(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_GALAXY_MAP":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug galaxy map: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_galaxy_map(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_WORLDGEN_SECTOR":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug worldgen sector: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_worldgen_sector(locked_state, str(parsed[1]))
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_GRAPH_ALL":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug graph all: available only in DEBUG mode. Use: debug on")
                    continue
                render_debug_graph_all(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_SEED":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug seed: available only in DEBUG mode. Use: debug on")
                    continue
                seed = parsed[1]
                locked_state.meta.rng_seed = seed
                locked_state.meta.rng_counter = 0
                loop._rng = random.Random(seed)
                print(f"Seed set to {seed}")
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ADD_SCRAP":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug add scrap: available only in DEBUG mode. Use: debug on")
                    continue
                debug_add_scrap(locked_state, int(parsed[1]))
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ADD_MODULE":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug add module: available only in DEBUG mode. Use: debug on")
                    continue
                debug_add_module(locked_state, str(parsed[1]), int(parsed[2]))
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_ADD_DRONE":
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("debug add drone: available only in DEBUG mode. Use: debug on")
                    continue
                debug_add_drones(locked_state, int(parsed[1]))
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DEBUG_SCENARIO":
            scenario = parsed[1]
            loop.set_auto_tick(False)
            loop.stop()
            with loop.with_lock() as locked_state:
                keep_debug = locked_state.os.debug_enabled
            if scenario in {"sandbox", "dev"}:
                new_state = create_initial_state_sandbox()
            else:
                new_state = create_initial_state_prologue()
            new_state.os.debug_enabled = keep_debug
            with loop.with_lock() as locked_state:
                loop.state = new_state
                loop._events_auto.clear()
                loop._rng = random.Random(new_state.meta.rng_seed)
            loop.step(1.0)
            if not keep_debug:
                loop.set_auto_tick(True)
                loop.start()
            with loop.with_lock() as locked_state:
                print(f"Scenario set to {scenario}")
                render_status(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "LS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_ls(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "CAT":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_cat(locked_state, parsed[1])
            continue
        if parsed == "INVENTORY":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_inventory(locked_state)
            continue
        if parsed == "MODULES":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_modules_installed(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "MODULE_INSPECT":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_module_inspect(locked_state, parsed[1])
            continue
        if parsed == "SHIP_SECTORS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_ship_sectors(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "SHIP_SURVEY":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_ship_survey(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "NAV_MAP":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_nav_map(locked_state, parsed[1], parsed[2])
            continue
        if parsed == "ALERTS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_alerts(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "ALERTS_EXPLAIN":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_alert_explain(locked_state, parsed[1])
            continue
        if parsed == "LOGS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_logs(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "LOG_COPY":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                _handle_log_copy(locked_state, parsed[1])
            continue
        if parsed == "JOBS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_jobs(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "JOBS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                limit = None if parsed[1] == "all" else int(parsed[1])
                render_jobs(locked_state, limit=limit)
            continue
        if isinstance(parsed, RouteSolve):
            _drain_auto_events()
            ev = loop.apply_action(parsed)
            audio_enabled = False
            with loop.with_lock() as locked_state:
                render_events(locked_state, ev)
                audio_enabled = locked_state.os.audio.enabled
            if audio_manager is not None:
                audio_manager.handle_event_batch(audio_enabled, ev)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)
            auto_ev = loop.drain_events()
            if auto_ev:
                audio_enabled = False
                with loop.with_lock() as locked_state:
                    render_events(locked_state, auto_ev)
                    audio_enabled = locked_state.os.audio.enabled
                if audio_manager is not None:
                    audio_manager.handle_event_batch(audio_enabled, auto_ev)
                    notice = audio_manager.consume_notice()
                    if notice:
                        print(notice)
            continue
        if parsed == "INTEL_LIST":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_intel_list(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_LIST":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                limit = None if parsed[1] == "all" else int(parsed[1])
                render_intel_list(locked_state, limit=limit)
            continue
        if parsed.__class__.__name__ == "TravelAbort":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                if not _confirm_travel_abort(locked_state):
                    continue
            ev = loop.apply_action(parsed)
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, ev)
                render_events(locked_state, ev)
            auto_ev = loop.drain_events()
            if auto_ev:
                audio_enabled = False
                with loop.with_lock() as locked_state:
                    _apply_salvage_loot(loop, locked_state, auto_ev)
                    render_events(locked_state, auto_ev)
                    audio_enabled = locked_state.os.audio.enabled
                if audio_manager is not None:
                    audio_manager.handle_event_batch(audio_enabled, auto_ev)
                    notice = audio_manager.consume_notice()
                    if notice:
                        print(notice)
            continue
        if parsed == "UPLINK":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                _handle_uplink(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_SHOW":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_intel_show(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "INTEL_EXPORT":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                _handle_intel_export(locked_state, parsed[1])
            continue
        if parsed == "POWER_STATUS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_power_status(locked_state)
            continue
        if parsed == "DRONE_STATUS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_drone_status(locked_state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DRONE_STATUS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_drone_status(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DRONE_AUTORECALL_ENABLED":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                _set_drone_autorecall(locked_state, parsed[1], enabled=bool(parsed[2]))
            continue
        if isinstance(parsed, tuple) and parsed[0] == "DRONE_AUTORECALL_THRESHOLD":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                _set_drone_autorecall(locked_state, parsed[1], threshold=float(parsed[2]))
            continue
        if isinstance(parsed, tuple) and parsed[0] == "ABOUT":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_about(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "MAN":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_man(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "LOCATE":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_locate(locked_state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "WAIT":
            seconds = parsed[1]
            with loop.with_lock() as locked_state:
                if not locked_state.os.debug_enabled:
                    print("wait is available only in DEBUG mode. Use: debug on")
                    continue
            step_events = loop.step_many(seconds, dt=1.0)
            cmd_events = [("step", e) for e in step_events]
            audio_enabled = False
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, cmd_events)
                render_events(locked_state, cmd_events)
                audio_enabled = locked_state.os.audio.enabled
                if any(e.severity == Severity.CRITICAL for _, e in cmd_events):
                    render_alerts(locked_state)
            if audio_manager is not None:
                audio_manager.handle_event_batch(audio_enabled, step_events)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)
            auto_ev = loop.drain_events()
            if auto_ev:
                audio_enabled = False
                with loop.with_lock() as locked_state:
                    _apply_salvage_loot(loop, locked_state, auto_ev)
                    render_events(locked_state, auto_ev)
                    audio_enabled = locked_state.os.audio.enabled
                if audio_manager is not None:
                    audio_manager.handle_event_batch(audio_enabled, auto_ev)
                    notice = audio_manager.consume_notice()
                    if notice:
                        print(notice)
            continue
        if isinstance(parsed, Hibernate):
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                block_msg = _hibernate_blocked_message(locked_state)
                warn_msg = _hibernate_soc_warning(locked_state)
            if block_msg:
                print(block_msg)
                continue
            with loop.with_lock() as locked_state:
                if not _confirm_hibernate_start(locked_state, parsed):
                    continue
            if warn_msg:
                print(warn_msg)
            with loop.with_lock() as locked_state:
                ok, wake_on_low = _confirm_hibernate_drones(locked_state)
                if not ok:
                    continue
            if parsed.mode == "until_arrival":
                with loop.with_lock() as locked_state:
                    if not locked_state.ship.in_transit:
                        print("hibernate: not in transit")
                        continue
                    if locked_state.ship.op_mode != "CRUISE":
                        if not _confirm_hibernate_non_cruise(locked_state):
                            continue
                    remaining_s = max(0.0, locked_state.ship.arrival_t - locked_state.clock.t)
                    years = remaining_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
            else:
                years = parsed.years
            _run_hibernate(loop, years, wake_on_low_battery=wake_on_low)
            continue

        # Acciones del motor
        if parsed.__class__.__name__ == "Diag":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_diag(locked_state, parsed.system_id)
            continue
        if parsed.__class__.__name__ == "Status":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_status(locked_state)
            continue
        if parsed.__class__.__name__ in {"Dock", "Travel", "Undock"}:
            with loop.with_lock() as locked_state:
                if parsed.__class__.__name__ == "Dock":
                    resolved = _resolve_node_id_from_input(locked_state, parsed.node_id)
                    if resolved:
                        parsed.node_id = resolved
                if parsed.__class__.__name__ == "Travel":
                    if not _confirm_nav(locked_state, parsed):
                        continue
                elif not _confirm_abandon_drones(locked_state, parsed):
                    continue

        ev = loop.apply_action(parsed)
        audio_enabled = False
        with loop.with_lock() as locked_state:
            _apply_salvage_loot(loop, locked_state, ev)
            render_events(locked_state, ev)
            audio_enabled = locked_state.os.audio.enabled
            if parsed.__class__.__name__ == "Travel":
                for item in ev:
                    event = item[1] if isinstance(item, tuple) and len(item) == 2 else item
                    if event.type == EventType.TRAVEL_STARTED:
                        locale = locked_state.os.locale.value
                        dest = event.data.get("to", parsed.node_id)
                        msg = {
                            "en": f"(nav) confirmed: en route to {dest}",
                            "es": f"(nav) confirmado: rumbo a {dest}",
                        }
                        print(msg.get(locale, msg["en"]))
                        break
        if audio_manager is not None:
            audio_manager.handle_event_batch(audio_enabled, ev)
            notice = audio_manager.consume_notice()
            if notice:
                print(notice)
        auto_ev = loop.drain_events()
        if auto_ev:
            audio_enabled = False
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, auto_ev)
                render_events(locked_state, auto_ev)
                audio_enabled = locked_state.os.audio.enabled
            if audio_manager is not None:
                audio_manager.handle_event_batch(audio_enabled, auto_ev)
                notice = audio_manager.consume_notice()
                if notice:
                    print(notice)

    _stop_and_persist()
    print("bye")


if __name__ == "__main__":
    main()
