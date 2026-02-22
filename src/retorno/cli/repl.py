from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
import os
import math
import random
import readline
from retorno.core.engine import Engine
from retorno.core.actions import Hibernate
from retorno.runtime.loop import GameLoop
from retorno.model.events import Event, EventType, Severity, SourceRef
from retorno.model.jobs import JobStatus
from retorno.runtime.data_loader import load_modules
from retorno.config.balance import Balance
from retorno.model.systems import SystemState
from retorno.model.os import FSNodeType, Locale, list_dir, normalize_path, read_file
from retorno.model.world import SECTOR_SIZE_LY, sector_id_for_pos
from retorno.model.world import SpaceNode, region_for_pos
from retorno.worldgen.generator import ensure_sector_generated
from retorno.util.timefmt import format_elapsed_long


def print_help() -> None:
    print(
        "\nComandos (resumen):\n"
        "  help | exit | quit\n"
        "\nFS / Manuales / Correo:\n"
        "  ls [path] | cat <path>\n"
        "  man <topic> | about <system_id>\n"
        "  mail [inbox] | mail read <id>\n"
        "  intel import <path>\n"
        "  config set lang <en|es> | config show\n"
        "\nInformación:\n"
        "  status | jobs | alerts | alerts explain <alert_key> | logs\n"
        "  contacts | scan\n"
        "  sectors | map | locate <system_id>\n"
        "\nNavegación:\n"
        "  dock <node_id> | travel <node_id>\n"
        "  hibernate until_arrival | hibernate <años>\n"
        "\nSistemas / Energía:\n"
        "  diag <system_id> | boot <service_name>\n"
        "  system off <system_id> | system on <system_id>\n"
        "  power status | power plan cruise|normal | power shed/off/on <system_id>\n"
        "  repair <system_id> --selftest\n"
        "\nDrones:\n"
        "  drone status\n"
        "  drone deploy <drone_id> <sector_id> | drone deploy! <drone_id> <sector_id>\n"
        "  drone move <drone_id> <target_id>\n"
        "  drone repair <drone_id> <system_id>\n"
        "  drone salvage scrap <drone_id> <node_id> <amount>\n"
        "  drone salvage module <drone_id> [node_id]\n"
        "  drone reboot <drone_id> | drone recall <drone_id>\n"
        "\nBodega / Módulos:\n"
        "  inventory | cargo | cargo audit | inventory audit\n"
        "  install <module_id> | modules\n"
        "\nDebug:\n"
        "  wait <segundos> (DEBUG only)\n"
        "  debug on|off|status | debug scenario prologue|sandbox|dev\n"
        "\nSugerencias:\n"
        "  ls /manuals/commands\n"
        "  cat /mail/inbox/0001.txt\n"
    )


class SafeDict(dict):
    def __missing__(self, key):
        return "?"


def _inventory_view(ship):
    # Returns manifest view plus dirty flag.
    return ship.manifest_scrap, list(ship.manifest_modules), ship.manifest_dirty


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


def render_events(state, events, origin_override: str | None = None) -> None:
    if not events:
        return
    job_queued_templates = {
        "en": "[{sev}] job_queued :: {job_id} {job_type} target={kind}:{tid} ETA={eta_s}s{emergency}",
        "es": "[{sev}] job_queued :: {job_id} {job_type} objetivo={kind}:{tid} ETA={eta_s}s{emergency}",
    }
    salvage_job_queued_templates = {
        "en": "[{sev}] job_queued :: {job_id} salvage_scrap requested={requested} available={available} will_recover={effective} ETA={eta_s}s",
        "es": "[{sev}] job_queued :: {job_id} salvage_scrap pedido={requested} disponible={available} recupera={effective} ETA={eta_s}s",
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
    signal_detected_templates = {
        "en": "[{sev}] signal_detected :: Signal detected: {contact_id}",
        "es": "[{sev}] signal_detected :: Señal detectada: {contact_id}",
    }
    docked_templates = {
        "en": "[{sev}] docked :: Docked at {node_id}",
        "es": "[{sev}] docked :: Acoplado en {node_id}",
    }
    travel_templates = {
        "travel_started": {
            "en": "[{sev}] travel_started :: To {to} dist={distance_ly:.2f}ly ETA={eta_years:.2f}y",
            "es": "[{sev}] travel_started :: A {to} dist={distance_ly:.2f}ly ETA={eta_years:.2f}a",
        },
        "arrived": {
            "en": "[{sev}] arrived :: Arrived at {to} (from {from})",
            "es": "[{sev}] arrived :: Llegada a {to} (desde {from})",
        },
        "hibernation_started": {
            "en": "[{sev}] hibernation_started :: Sleeping for {years:.2f}y",
            "es": "[{sev}] hibernation_started :: Hibernando durante {years:.2f}a",
        },
        "hibernation_ended": {
            "en": "[{sev}] hibernation_ended :: Woke up after {years:.2f}y",
            "es": "[{sev}] hibernation_ended :: Despertaste tras {years:.2f}a",
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
        "unknown_contact": {
            "en": "Action blocked: unknown contact ({node_id}). Use 'scan' or acquire navigation intel.",
            "es": "Acción bloqueada: contacto desconocido ({node_id}). Usa 'scan' o consigue inteligencia de navegación.",
        },
        "invalid_amount": {
            "en": "Action blocked: invalid amount",
            "es": "Acción bloqueada: cantidad inválida",
        },
        "not_docked": {
            "en": "Action blocked: not docked at {node_id}",
            "es": "Acción bloqueada: no acoplado en {node_id}",
        },
        "scrap_empty": {
            "en": "No scrap available",
            "es": "No hay chatarra disponible",
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
            "en": "Install blocked: unknown module ({module_id})",
            "es": "Instalación bloqueada: módulo desconocido ({module_id})",
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
        "system_too_damaged": {
            "en": "System on blocked: system too damaged",
            "es": "System on bloqueado: sistema demasiado dañado",
        },
        "in_transit": {
            "en": "Action blocked: ship in transit. Use 'hibernate until_arrival' to advance.",
            "es": "Acción bloqueada: nave en tránsito. Usa 'hibernate until_arrival' para avanzar.",
        },
        "already_at_target": {
            "en": "Action blocked: already at destination ({node_id})",
            "es": "Acción bloqueada: ya estás en destino ({node_id})",
        },
    }
    job_completed_keys = {
        "job_completed_repair": {
            "en": "Repair completed for {system_id}",
            "es": "Reparación completada en {system_id}",
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
        "job_completed_salvage": {
            "en": "Salvage complete: +{amount} {kind} from {node_id}",
            "es": "Recuperación completa: +{amount} {kind} de {node_id}",
        },
        "job_completed_install": {
            "en": "Module installed: {module_id}",
            "es": "Módulo instalado: {module_id}",
        },
        "job_completed_cargo_audit": {
            "en": "Cargo manifest updated",
            "es": "Manifiesto de bodega actualizado",
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
            payload.update({
                "job_id": job_id,
                "job_type": job_type,
                "kind": kind,
                "tid": tid,
                "eta_s": eta_s,
                "emergency": emergency,
                "requested": e.data.get("requested", "?"),
                "available": e.data.get("available", "?"),
                "effective": e.data.get("effective", "?"),
            })
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
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
        if e.type == EventType.JOB_FAILED and e.data.get("job_id"):
            locale = state.os.locale.value
            tmpl = job_failed_templates.get(locale, job_failed_templates["en"])
            payload.update({
                "job_id": e.data.get("job_id", "?"),
                "job_type": e.data.get("job_type", "?"),
            })
            try:
                print(f"[{origin_tag}] " + _safe_format(tmpl, payload))
            except Exception:
                print(f"[{origin_tag}] [{sev}] {e.type.value} :: {e.message} (data={e.data})")
            continue
        if e.type == EventType.JOB_COMPLETED and e.data.get("job_id"):
            locale = state.os.locale.value
            key = e.data.get("message_key", "")
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
        if e.type in {EventType.TRAVEL_STARTED, EventType.ARRIVED, EventType.HIBERNATION_STARTED, EventType.HIBERNATION_ENDED}:
            locale = state.os.locale.value
            key = e.type.value
            tmpl = travel_templates.get(key, {}).get(locale)
            payload.update({
                "to": e.data.get("to", "?"),
                "from": e.data.get("from", "?"),
                "distance_ly": e.data.get("distance_ly", 0.0),
                "eta_years": e.data.get("eta_years", 0.0),
                "years": e.data.get("years", 0.0),
            })
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
                extra = f"{extra} | cost: {scrap_cost} scrap"
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


def render_status(state) -> None:
    ship = state.ship
    p = ship.power
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    net = p.p_gen_kw - p.p_load_kw
    deficit = max(0.0, p.p_load_kw - p.p_gen_kw)
    headroom = p.p_discharge_max_kw - deficit
    print("\n=== STATUS ===")
    print(f"time: {format_elapsed_long(state.clock.t)}")
    mode = "DEBUG" if state.os.debug_enabled else "NORMAL"
    print(f"mode: {mode}")
    print(f"ship_mode: {ship.op_mode}")
    current_loc = ship.current_node_id or state.world.current_node_id
    node = state.world.space.nodes.get(current_loc)
    node_name = node.name if node else current_loc
    if ship.in_transit:
        remaining_s = max(0.0, ship.arrival_t - state.clock.t)
        remaining_years = remaining_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
        remaining_days = remaining_s / Balance.DAY_S if Balance.DAY_S else 0.0
        print(f"location: en route to {ship.transit_to} (from {ship.transit_from}) ETA={remaining_years:.2f}y ({remaining_days:.1f}d)")
        dist = getattr(ship, "transit_distance_ly", 0.0) or 0.0
        print(f"transit: {ship.transit_from} -> {ship.transit_to}  dist={dist:.2f}ly  ETA={remaining_years:.2f}y ({remaining_days:.1f}d)")
    else:
        print(f"location: {current_loc} ({node_name})")
    print(f"power: P_gen={p.p_gen_kw:.2f}kW  P_load={p.p_load_kw:.2f}kW  net={net:+.2f}kW headroom={headroom:.2f}kW  SoC={soc:.2f}  Q={p.power_quality:.2f}  brownout={p.brownout}")
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
        print("notes: manually powered down (power shed/shutdown).")
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
        print(f"- {a.severity.value.upper():8s} {a.alert_key:24s} unacked={a.unacked_s}s")


def render_logs(state, limit: int = 15) -> None:
    print("\n=== EVENTS (recent) ===")
    for e in state.events.recent[-limit:]:
        print(f"- t={e.t:6d} [{e.severity.value.upper():8s}] {e.type.value}: {e.message}")


def render_jobs(state) -> None:
    print("\n=== JOBS ===")
    jobs_state = state.jobs
    active_jobs = []
    for job_id in jobs_state.active_job_ids:
        job = jobs_state.jobs.get(job_id)
        if job:
            active_jobs.append(job)
    running_by_owner: set[str] = set()
    for job in active_jobs:
        if job.status == JobStatus.RUNNING and job.owner_id:
            running_by_owner.add(job.owner_id)

    if not jobs_state.jobs:
        print("(none)")
        return

    locale = state.os.locale.value
    wait_note_templates = {
        "en": " (waiting: drone busy {drone_id})",
        "es": " (en espera: dron ocupado {drone_id})",
    }

    def _format_job(job):
        target = f"{job.target.kind}:{job.target.id}" if job.target else "-"
        eta = f"{max(0, int(job.eta_s))}s" if job.status in {JobStatus.QUEUED, JobStatus.RUNNING} else "-"
        owner = job.owner_id or "-"
        emergency = " EMERGENCY" if job.params.get("emergency") else ""
        wait_note = ""
        if job.status == JobStatus.QUEUED and job.owner_id and job.owner_id in running_by_owner:
            tmpl = wait_note_templates.get(locale, wait_note_templates["en"])
            wait_note = tmpl.format(drone_id=job.owner_id)
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
        if job.job_id not in jobs_state.active_job_ids and job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
    ]
    if history:
        print("Recent complete/failed:")
        for job in sorted(history, key=lambda j: j.job_id, reverse=True)[:5]:
            print(_format_job(job))


def render_drone_status(state) -> None:
    print("\n=== DRONES ===")
    for did, d in state.ship.drones.items():
        print(f"- {did}: status={d.status.value} loc={d.location.kind}:{d.location.id} battery={d.battery:.2f} integrity={d.integrity:.2f} dose={d.dose_rad:.3f}")


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


def render_modules_catalog(state) -> None:
    print("\n=== MODULES CATALOG ===")
    modules = load_modules()
    if not modules:
        print("(none)")
        return
    locale = state.os.locale.value
    for mid, info in modules.items():
        name = info.get("name", mid)
        scrap_cost = info.get("scrap_cost", "?")
        effects = info.get("effects", {})
        effects_str = ", ".join(f"{k}={v}" for k, v in effects.items()) or "no effects"
        desc = info.get("desc_es") if locale == "es" else info.get("desc_en")
        print(f"- {mid}: {name} (scrap {scrap_cost}) [{effects_str}]")
        if desc:
            print(f"  {desc}")

def render_contacts(state) -> None:
    print("\n=== CONTACTS ===")
    known = state.world.known_nodes if hasattr(state.world, "known_nodes") and state.world.known_nodes else state.world.known_contacts
    if not known:
        print("(no signals detected)")
        return
    for cid in sorted(known):
        node = state.world.space.nodes.get(cid)
        if node:
            print(f"- {cid}: {node.name} ({node.kind})")
        else:
            print(f"- {cid}")


def render_scan_results(state, node_ids: list[str]) -> None:
    print("\n=== SCAN ===")
    if not node_ids:
        print("(no signals detected)")
        return
    for cid in sorted(node_ids):
        node = state.world.space.nodes.get(cid)
        if node:
            print(f"- {cid}: {node.name} ({node.kind})")
        else:
            print(f"- {cid}")


def _scan_and_discover(state) -> tuple[list[str], list[str]]:
    current_id = state.world.current_node_id
    node = state.world.space.nodes.get(current_id)
    if node:
        x, y, z = node.x_ly, node.y_ly, node.z_ly
    else:
        x, y, z = state.world.current_pos_ly
    r = state.ship.sensors_range_ly
    min_sx = math.floor((x - r) / SECTOR_SIZE_LY)
    max_sx = math.floor((x + r) / SECTOR_SIZE_LY)
    min_sy = math.floor((y - r) / SECTOR_SIZE_LY)
    max_sy = math.floor((y + r) / SECTOR_SIZE_LY)
    min_sz = math.floor((z - r) / SECTOR_SIZE_LY)
    max_sz = math.floor((z + r) / SECTOR_SIZE_LY)
    for sx in range(min_sx, max_sx + 1):
        for sy in range(min_sy, max_sy + 1):
            for sz in range(min_sz, max_sz + 1):
                sector_id = f"S{sx:+04d}_{sy:+04d}_{sz:+04d}"
                ensure_sector_generated(state, sector_id)

    discovered: list[str] = []
    seen: list[str] = []
    for nid, n in state.world.space.nodes.items():
        dx = n.x_ly - x
        dy = n.y_ly - y
        dz = n.z_ly - z
        if dx * dx + dy * dy + dz * dz <= r * r:
            seen.append(nid)
            if nid not in state.world.known_nodes:
                discovered.append(nid)
            state.world.known_nodes.add(nid)
            state.world.known_contacts.add(nid)
    return seen, discovered


def _handle_intel_import(state, path: str) -> None:
    try:
        content = read_file(state.os.fs, path, state.os.access_level)
    except PermissionError:
        print("intel import: permission denied")
        return
    except Exception:
        print("intel import: file not found")
        return

    added: list[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("NODE:"):
            node_id = line.split(":", 1)[1].strip()
            if not node_id:
                continue
            if node_id.startswith("S") and ":" in node_id:
                sector_id = node_id.split(":", 1)[0]
                ensure_sector_generated(state, sector_id)
            state.world.known_intel[node_id] = {"source": path}
            state.world.known_nodes.add(node_id)
            state.world.known_contacts.add(node_id)
            added.append(node_id)
        if line.upper().startswith("SECTOR:"):
            sector_id = line.split(":", 1)[1].strip()
            if not sector_id:
                continue
            ensure_sector_generated(state, sector_id)
            state.world.known_intel[sector_id] = {"source": path, "sector": True}
            added.append(sector_id)
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
                node = SpaceNode(
                    node_id=nid,
                    name="Nav Point",
                    kind="nav_point",
                    radiation_rad_per_s=0.0,
                    x_ly=x,
                    y_ly=y,
                    z_ly=z,
                )
                node.region = region_for_pos(x, y, z)
                state.world.space.nodes[nid] = node
            state.world.known_intel[nid] = {"source": path, "coord": [x, y, z]}
            state.world.known_nodes.add(nid)
            state.world.known_contacts.add(nid)
            added.append(nid)
    if added:
        print(f"(intel) added: {', '.join(sorted(set(added)))}")
    else:
        print("(intel) no usable intel found")

def render_sectors(state) -> None:
    print("\n=== SECTORS ===")
    if not state.ship.sectors:
        print("(none)")
        return
    for sid, sector in state.ship.sectors.items():
        tags = ",".join(sorted(sector.tags)) if sector.tags else "-"
        print(f"- {sid}: {sector.name} [{tags}]")


def render_locate(state, system_id: str) -> None:
    sys = state.ship.systems.get(system_id)
    if not sys:
        print("(locate) system_id no encontrado")
        return
    sector = state.ship.sectors.get(sys.sector_id)
    if sector:
        print(f"{system_id} -> {sys.sector_id} ({sector.name})")
    else:
        print(f"{system_id} -> {sys.sector_id}")


def _resolve_localized_path(state, path: str) -> str:
    path = normalize_path(path)
    if path in state.os.fs:
        return path
    if path.endswith(".txt"):
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
    entries = list_dir(state.os.fs, path, state.os.access_level)
    print(f"\n=== LS {path} ===")
    if not entries:
        print("(empty)")
        return
    for name in entries:
        node = state.os.fs.get(normalize_path(f"{path}/{name}"))
        suffix = "/" if node and node.node_type == FSNodeType.DIR else ""
        print(f"- {name}{suffix}")


def render_cat(state, path: str) -> None:
    path = _resolve_localized_path(state, path)
    try:
        content = read_file(state.os.fs, path, state.os.access_level)
    except KeyError:
        print("No such file")
        return
    except PermissionError:
        print("Permission denied")
        return
    except IsADirectoryError:
        print("Is a directory")
        return
    print(f"\n=== CAT {path} ===")
    print(content)

def render_mailbox(state, box: str) -> None:
    path = f"/mail/{box}"
    print(f"\n=== MAIL {box} ===")
    entries = list_dir(state.os.fs, path, state.os.access_level)
    if not entries:
        print("(empty)")
        return
    for name in entries:
        if name.endswith(".notice.txt"):
            print(f"- {name}")
            continue
        if name.endswith(f".{state.os.locale.value}.txt"):
            print(f"- {name}")
            continue
        if name.endswith(".txt") and f"{name[:-4]}.{state.os.locale.value}.txt" not in entries:
            print(f"- {name}")

def _latest_mail_id(state, box: str) -> str | None:
    path = f"/mail/{box}"
    entries = list_dir(state.os.fs, path, state.os.access_level)
    ids: set[str] = set()
    for name in entries:
        if not name.endswith(".txt"):
            continue
        if name.endswith(".notice.txt"):
            continue
        base = name[:-4]
        if base.endswith(".en") or base.endswith(".es"):
            base = base[:-3]
        if base.isdigit():
            ids.add(base)
    if not ids:
        return None
    return sorted(ids)[-1]


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


 


def _apply_salvage_loot(loop, state, events):
    return


def _run_hibernate(loop, years: float) -> None:
    total_s = max(0.0, years * Balance.YEAR_S)
    if total_s <= 0:
        print("hibernate: nothing to do (duration <= 0)")
        return
    events_to_render: list[tuple[str, Event]] = []
    with loop.with_lock() as locked_state:
        locked_state.ship.op_mode = "CRUISE"
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
    loop.set_auto_tick(False)
    remaining = total_s
    step_events: list[tuple[str, Event]] = []
    while remaining > 0:
        step = Balance.HIBERNATE_CHUNK_S if remaining >= Balance.HIBERNATE_CHUNK_S else remaining
        ev = loop.step(step)
        step_events.extend([("step", e) for e in ev])
        remaining -= step
    with loop.with_lock() as locked_state:
        _emit_runtime_event(
            locked_state,
            events_to_render,
            "cmd",
            EventType.HIBERNATION_ENDED,
            Severity.INFO,
            SourceRef(kind="ship", id=locked_state.ship.ship_id),
            f"Hibernation ended after {years:.2f} years",
            data={"years": years},
        )
        end_soc = locked_state.ship.power.e_batt_kwh / locked_state.ship.power.e_batt_max_kwh if locked_state.ship.power.e_batt_max_kwh else 0.0
        end_health = {sid: sys.health for sid, sys in locked_state.ship.systems.items() if "critical" in sys.tags}
        # Keep cruise profile active unless manually changed later
        if not locked_state.ship.in_transit:
            locked_state.ship.op_mode = "CRUISE"
    loop.set_auto_tick(was_auto)
    filtered = [pair for pair in step_events if pair[1].severity == Severity.CRITICAL or pair[1].type in {EventType.ARRIVED}]
    events_to_render.extend(filtered)
    with loop.with_lock() as locked_state:
        if events_to_render:
            render_events(locked_state, events_to_render)
        days = years * (Balance.YEAR_S / Balance.DAY_S)
        print(f"Advanced time by {years:.2f} years ({days:.1f} days).")
        # digest de degradación para críticos
        if start_health:
            print("Hibernate digest (critical systems):")
            for sid, h0 in start_health.items():
                h1 = end_health.get(sid, h0)
                dh = h1 - h0
                print(f"- {sid}: Δhealth={dh:+.3f} now={h1:.3f}")
        print(f"SoC: start={start_soc:.3f} end={end_soc:.3f}")


def render_about(state, system_id: str) -> None:
    path = _resolve_localized_path(state, f"/manuals/systems/{system_id}.txt")
    if path in state.os.fs:
        render_cat(state, path)
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
    resolved_path = None
    for path in (cmd_path, concept_path, sys_path, alert_path):
        if path in state.os.fs:
            resolved_path = path
            break
    if not resolved_path:
        print("No manual found")
        return
    try:
        print(f"\n=== MAN {topic} ===")
        print(read_file(state.os.fs, resolved_path, state.os.access_level))
    except PermissionError:
        print("Permission denied")
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
            print(f"Severity: {alert.severity.value}   Active: True   Unacked while active: {alert.unacked_s}s")
        else:
            print(f"Severity: {alert.severity.value}   Active: False (cleared)   Unacked while active: {alert.unacked_s}s")
    else:
        print("Severity: unknown   Active: unknown   Unacked: unknown")

    manual_path = _resolve_localized_path(state, f"/manuals/alerts/{alert_key}.txt")
    if manual_path not in state.os.fs:
        fallback = f"/manuals/alerts/{alert_key}.en.txt"
        if fallback in state.os.fs:
            manual_path = fallback
    try:
        print(read_file(state.os.fs, manual_path, state.os.access_level))
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

def main() -> None:
    from retorno.cli.parser import ParseError, parse_command

    engine = Engine()
    scenario = os.environ.get("RETORNO_SCENARIO", "prologue").lower()
    if scenario in {"sandbox", "dev"}:
        state = create_initial_state_sandbox()
    else:
        state = create_initial_state_prologue()
    loop = GameLoop(engine, state, tick_s=1.0)
    loop.step(1.0)
    if not state.os.debug_enabled:
        loop.set_auto_tick(True)
        loop.start()
    else:
        loop.set_auto_tick(False)

    base_commands = [
        "help",
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
        "contacts",
        "scan",
        "sectors",
        "map",
        "locate",
        "dock",
        "travel",
        "salvage",
        "diag",
        "boot",
        "repair",
        "inventory",
        "cargo",
        "install",
        "modules",
        "shutdown",
        "system",
        "hibernate",
        "drone",
        "wait",
        "debug",
        "exit",
        "quit",
    ]

    def _completer(text: str, state_idx: int) -> str | None:
        buf = readline.get_line_buffer()
        tokens = buf.strip().split()
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
                sectors = list(locked_state.ship.sectors.keys())
                contacts = sorted(
                    locked_state.world.known_nodes if hasattr(locked_state.world, "known_nodes") and locked_state.world.known_nodes else locked_state.world.known_contacts
                )
                modules = list(set(locked_state.ship.cargo_modules))
                services = []
                for sys in locked_state.ship.systems.values():
                    if sys.service and sys.service.is_installed:
                        services.append(sys.service.service_name)
                fs_paths = list(locked_state.os.fs.keys())

            if len(tokens) == 1:
                candidates = [c for c in base_commands if c.startswith(text)]
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
                    entries = list_dir(locked_state.os.fs, dir_path, locked_state.os.access_level)
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
                candidates = [c for c in contacts if c.startswith(text)]
            elif cmd == "travel":
                candidates = [c for c in contacts if c.startswith(text)]
            elif cmd == "power":
                if len(tokens) == 2:
                    candidates = [c for c in ["status", "shed", "off", "on", "plan"] if c.startswith(text)]
                elif len(tokens) == 3 and tokens[1] in {"shed", "off", "on"}:
                    candidates = [s for s in systems if s.startswith(text)]
                elif len(tokens) == 3 and tokens[1] == "plan":
                    candidates = [c for c in ["cruise", "normal"] if c.startswith(text)]
            elif cmd == "debug":
                if len(tokens) == 2:
                    candidates = [c for c in ["on", "off", "status", "scenario"] if c.startswith(text)]
                elif len(tokens) == 3 and tokens[1] == "scenario":
                    candidates = [c for c in ["prologue", "sandbox", "dev"] if c.startswith(text)]
            elif cmd == "install":
                candidates = [m for m in modules if m.startswith(text)]
            elif cmd == "inventory":
                if len(tokens) == 2:
                    candidates = [c for c in ["audit"] if c.startswith(text)]
            elif cmd == "cargo":
                if len(tokens) == 2:
                    candidates = [c for c in ["audit"] if c.startswith(text)]
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
                    if path.startswith("/manuals/commands/") or path.startswith("/manuals/systems/") or path.startswith("/manuals/alerts/") or path.startswith("/manuals/modules/"):
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
            elif cmd == "drone":
                if len(tokens) == 2:
                    candidates = [
                        c for c in ["status", "deploy", "deploy!", "move", "reboot", "recall", "repair", "salvage"]
                        if c.startswith(text)
                    ]
                elif len(tokens) == 3 and tokens[1] in {"deploy", "deploy!", "reboot", "recall", "repair", "move"}:
                    candidates = [d for d in drones if d.startswith(text)]
                elif len(tokens) == 4 and tokens[1] in {"deploy", "deploy!"}:
                    candidates = [s for s in sectors if s.startswith(text)] + [c for c in contacts if c.startswith(text)]
                elif len(tokens) == 4 and tokens[1] == "move":
                    candidates = [s for s in sectors if s.startswith(text)] + [c for c in contacts if c.startswith(text)]
                elif len(tokens) == 3 and tokens[1] == "salvage":
                    candidates = [c for c in ["scrap", "module", "modules"] if c.startswith(text)]
                elif len(tokens) == 4 and tokens[1] == "salvage":
                    candidates = [d for d in drones if d.startswith(text)]
                elif len(tokens) == 5 and tokens[1] == "salvage":
                    candidates = [c for c in contacts if c.startswith(text)]
            elif cmd == "salvage":
                if len(tokens) == 2:
                    candidates = [c for c in ["scrap", "module", "modules"] if c.startswith(text)]
                elif len(tokens) == 3:
                    candidates = [d for d in drones if d.startswith(text)]
                elif len(tokens) == 4:
                    candidates = [c for c in contacts if c.startswith(text)]
            elif cmd == "config":
                if len(tokens) == 2:
                    candidates = [c for c in ["set", "show"] if c.startswith(text)]
                elif len(tokens) == 3 and tokens[1] == "set":
                    candidates = [c for c in ["lang"] if c.startswith(text)]
                elif len(tokens) == 4 and tokens[1] == "set" and tokens[2] == "lang":
                    candidates = [c for c in ["en", "es"] if c.startswith(text)]
            elif cmd == "mail":
                if len(tokens) == 2:
                    candidates = [c for c in ["inbox", "read"] if c.startswith(text)]
                elif len(tokens) == 3 and tokens[1] == "read":
                    candidates = [c for c in ["latest"] if c.startswith(text)]
            elif cmd == "intel":
                if len(tokens) == 2:
                    candidates = [c for c in ["import"] if c.startswith(text)]
                elif len(tokens) == 3 and tokens[1] == "import":
                    path_text = token or text
                    if "/" in path_text:
                        dir_part, base_part = path_text.rsplit("/", 1)
                        dir_path = normalize_path(dir_part or "/")
                        prefix = base_part
                    else:
                        dir_path = "/"
                        prefix = path_text
                    try:
                        entries = list_dir(locked_state.os.fs, dir_path, locked_state.os.access_level)
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

        if state_idx < len(candidates):
            return candidates[state_idx]
        return None

    readline.set_completer_delims(" \t\n")
    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")

    def _drain_auto_events() -> None:
        auto_ev = loop.drain_events()
        if auto_ev:
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, auto_ev)
                render_events(locked_state, auto_ev)

    print("RETORNO (prologue)")
    print("Tip: cat /mail/inbox/0000.notice.txt")
    with loop.with_lock() as locked_state:
        render_status(locked_state)
        render_alerts(locked_state)

    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            loop.stop()
            print("\n(exit)")
            break

        try:
            parsed = parse_command(line)
        except ParseError as e:
            print(f"ParseError: {e.message}")
            continue

        if parsed is None:
            # sin comando: mundo sigue si quieres; aquí no tickeamos automáticamente
            continue

        ev = loop.drain_events()
        if ev:
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, ev)
                render_events(locked_state, ev)

        if parsed == "EXIT":
            loop.stop()
            break
        if parsed == "HELP":
            _drain_auto_events()
            print_help()
            continue
        if parsed == "CONFIG_SHOW":
            with loop.with_lock() as locked_state:
                print(f"language: {locked_state.os.locale.value}")
                print(f"access: {locked_state.os.access_level.value}")
            continue
        if isinstance(parsed, tuple) and parsed[0] == "CONFIG_SET_LANG":
            lang = parsed[1]
            with loop.with_lock() as locked_state:
                locked_state.os.locale = Locale(lang)
                print(f"Language set to {locked_state.os.locale.value}")
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
        if parsed == "CONTACTS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_contacts(locked_state)
            continue
        if parsed == "SCAN":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                seen, discovered = _scan_and_discover(locked_state)
                render_scan_results(locked_state, seen)
                if discovered:
                    print(f"(scan) new: {', '.join(sorted(discovered))}")
            continue
        if parsed == "INVENTORY":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_inventory(locked_state)
            continue
        if parsed == "MODULES":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_modules_catalog(locked_state)
            continue
        if parsed == "SECTORS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_sectors(locked_state)
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
        if parsed == "JOBS":
            _drain_auto_events()
            with loop.with_lock() as locked_state:
                render_jobs(locked_state)
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
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, cmd_events)
                render_events(locked_state, cmd_events)
                if any(e.severity == Severity.CRITICAL for _, e in cmd_events):
                    render_alerts(locked_state)
            auto_ev = loop.drain_events()
            if auto_ev:
                with loop.with_lock() as locked_state:
                    _apply_salvage_loot(loop, locked_state, auto_ev)
                    render_events(locked_state, auto_ev)
            continue
        if isinstance(parsed, Hibernate):
            _drain_auto_events()
            if parsed.mode == "until_arrival":
                with loop.with_lock() as locked_state:
                    if not locked_state.ship.in_transit:
                        print("hibernate: not in transit")
                        continue
                    remaining_s = max(0.0, locked_state.ship.arrival_t - locked_state.clock.t)
                    years = remaining_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
            else:
                years = parsed.years
            _run_hibernate(loop, years)
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

        ev = loop.apply_action(parsed)
        with loop.with_lock() as locked_state:
            _apply_salvage_loot(loop, locked_state, ev)
            render_events(locked_state, ev)
        auto_ev = loop.drain_events()
        if auto_ev:
            with loop.with_lock() as locked_state:
                _apply_salvage_loot(loop, locked_state, auto_ev)
                render_events(locked_state, auto_ev)

    print("bye")


if __name__ == "__main__":
    main()
