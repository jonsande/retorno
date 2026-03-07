from __future__ import annotations

from dataclasses import dataclass, field
import difflib

from retorno.core.actions import (
    AuthRecover,
    Boot,
    CargoAudit,
    Diag,
    Dock,
    Undock,
    DroneDeploy,
    DroneMove,
    DroneRecall,
    DroneReboot,
    DroneSurvey,
    Hibernate,
    Install,
    JobCancel,
    PowerPlan,
    PowerShed,
    Repair,
    SelfTestRepair,
    SystemOn,
    SalvageModule,
    SalvageScrap,
    SalvageData,
    SalvageDrone,
    RouteSolve,
    Status,
    Travel,
    TravelAbort,
)


@dataclass(slots=True)
class ParseError(Exception):
    key: str
    params: dict[str, object] = field(default_factory=dict)


_PARSE_ERROR_MESSAGES = {
    "en": {
        "usage_help": "Usage: help [--verbose]",
        "usage_job_cancel": "Usage: job cancel <job_id>",
        "usage_alerts": "Usage: alerts | alerts explain <alert_key>",
        "usage_log_copy": "Usage: log copy [n]",
        "log_copy_int": "log copy: [n] must be an integer",
        "log_copy_gt0": "log copy: [n] must be > 0",
        "usage_wait": "Usage: wait <seconds>",
        "wait_number": "wait: <seconds> must be a number",
        "wait_gt0": "wait: <seconds> must be > 0",
        "debug_seed_int": "debug seed: <n> must be an integer",
        "usage_debug": "Usage: debug on|off|status | debug scenario prologue|sandbox|dev | debug seed <n> | debug arcs | debug lore | debug deadnodes | debug modules | debug galaxy | debug galaxy map <sector|local|regional|global>",
        "usage_dock": "Usage: dock <node_id>",
        "usage_undock": "Usage: undock",
        "usage_nav": "Usage: nav map sectors|graph [node_id]|path <node_id>|routes|contacts|galaxy [sector|local|regional|global] | nav <node_id> | nav --no-cruise <node_id> | nav abort",
        "usage_hibernate": "Usage: hibernate until_arrival | hibernate <years>",
        "hibernate_number": "hibernate: <years> must be a number",
        "hibernate_gt0": "hibernate: <years> must be > 0",
        "usage_salvage": "Usage: drone salvage scrap <drone_id> [node_id] <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage drone(s) <drone_id> [node_id] | drone salvage data <drone_id> [node_id]",
        "usage_salvage_scrap": "Usage: drone salvage scrap <drone_id> <node_id> <amount>",
        "salvage_amount_int": "salvage: amount must be an integer",
        "salvage_amount_gt0": "salvage: amount must be > 0",
        "salvage_missing_node": "Falta node_id. Ejemplo: drone salvage modules D1 ECHO_7",
        "usage_salvage_drone": "Usage: drone salvage drone(s) <drone_id> [node_id]",
        "usage_salvage_data": "Usage: drone salvage data <drone_id> [node_id]",
        "usage_inventory": "Usage: inventory|cargo | inventory|cargo audit",
        "config_set_lang": "config set lang <en|es>",
        "usage_config": "Usage: config set lang <en|es> | config show",
        "usage_mail": "Usage: mail inbox | mail read <id|latest>",
        "usage_mail_read": "Usage: mail read <id|latest>",
        "usage_intel": "Usage: intel | intel <amount> | intel all | intel show <intel_id> | intel import <path> | intel export <path>",
        "usage_module": "Usage: module inspect <module_id> | modules",
        "usage_auth": "Usage: auth status | auth recover <level>",
        "intel_amount_gt0": "intel: amount must be > 0",
        "usage_jobs": "Usage: jobs | jobs <amount> | jobs all",
        "jobs_amount_gt0": "jobs: amount must be > 0",
        "usage_route": "Usage: route solve <node_id>",
        "usage_relay": "Usage: relay uplink",
        "usage_map": "Usage: map path <node_id> (alias of nav map path <node_id>)",
        "usage_ship": "Usage: ship sectors | ship map | ship survey <target>",
        "sectors_migrated": "Command 'sectors' was removed. Use: ship sectors",
        "map_ship_migrated": "Command 'map ship' was removed. Use: ship sectors",
        "map_graph_migrated": "Command 'map graph' was moved. Use: nav map graph [node_id]",
        "usage_locate": "Usage: locate <system_id>",
        "usage_diag": "Usage: diag <system_id>",
        "usage_install": "Install via drones only. Use: drone install <drone_id> <module_id>",
        "usage_ls": "Usage: ls [<path>]",
        "usage_cat": "Usage: cat <path>",
        "usage_about": "Usage: about <system_id>",
        "usage_man": "Usage: man <command>",
        "usage_boot": "Usage: boot <service_name>",
        "usage_power": "Usage: power status | power plan cruise|normal | power on <system_id> | power off <system_id>",
        "usage_power_plan": "Usage: power plan cruise|normal",
        "usage_power_on": "Usage: power on <system_id>",
        "usage_power_off": "Usage: power off <system_id>",
        "usage_shutdown": "Usage: shutdown <system_id>",
        "usage_drone": "Usage: drone status [drone_id] | drone deploy <drone_id> <sector_id> | drone move <drone_id> <target_id> | drone survey <drone_id> [node_id] | drone recall <drone_id> | drone autorecall <drone_id> <on|off|amount_percent> | drone repair <drone_id> <target_id> | drone install <drone_id> <module_id>",
        "usage_drone_status": "Usage: drone status [drone_id]",
        "usage_drone_recall": "Usage: drone recall <drone_id>",
        "usage_drone_reboot": "Usage: drone reboot <drone_id>",
        "usage_drone_repair": "Usage: drone repair <drone_id> <target_id>",
        "usage_drone_move": "Usage: drone move <drone_id> <target_id>",
        "usage_drone_survey": "Usage: drone survey <drone_id> [node_id]",
        "usage_drone_autorecall": "Usage: drone autorecall <drone_id> <on|off|amount_percent>",
        "drone_autorecall_amount": "drone autorecall: amount must be a number in (0, 100]",
        "usage_drone_install": "Usage: drone install <drone_id> <module_id>",
        "usage_drone_salvage": "Usage: drone salvage scrap <drone_id> [node_id] <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage drone(s) <drone_id> [node_id] | drone salvage data <drone_id> [node_id]",
        "usage_drone_salvage_scrap": "Usage: drone salvage scrap <drone_id> <node_id> <amount>",
        "usage_drone_salvage_drone": "Usage: drone salvage drone(s) <drone_id> [node_id]",
        "usage_drone_salvage_data": "Usage: drone salvage data <drone_id> [node_id]",
        "usage_drone_deploy": "Usage: drone deploy <drone_id> <sector_id> | drone deploy! <drone_id> <sector_id>",
        "unknown_drone_subcommand": "Unknown drone subcommand. Use: drone status | drone deploy ... | drone move ... | drone survey ... | drone recall ... | drone autorecall ...",
        "usage_repair": "Usage: drone repair <drone_id> <target_id> | repair <system_id> --selftest",
        "module_install_migrated": "module install/install has been removed. Use: drone install <drone_id> <module_id>",
        "unknown_command_suggestion": "Unknown command: {cmd}. Did you mean: {suggestion}?",
        "unknown_command": "Unknown command: {cmd}",
    },
    "es": {
        "usage_help": "Uso: help [--verbose]",
        "usage_job_cancel": "Uso: job cancel <job_id>",
        "usage_alerts": "Uso: alerts | alerts explain <alert_key>",
        "usage_log_copy": "Uso: log copy [n]",
        "log_copy_int": "log copy: [n] debe ser entero",
        "log_copy_gt0": "log copy: [n] debe ser > 0",
        "usage_wait": "Uso: wait <segundos>",
        "wait_number": "wait: <segundos> debe ser número",
        "wait_gt0": "wait: <segundos> debe ser > 0",
        "debug_seed_int": "debug seed: <n> debe ser entero",
        "usage_debug": "Uso: debug on|off|status | debug scenario prologue|sandbox|dev | debug seed <n> | debug arcs | debug lore | debug deadnodes | debug modules | debug galaxy | debug galaxy map <sector|local|regional|global>",
        "usage_dock": "Uso: dock <node_id>",
        "usage_undock": "Uso: undock",
        "usage_nav": "Uso: nav map sectors|graph [node_id]|path <node_id>|routes|contacts|galaxy [sector|local|regional|global] | nav <node_id> | nav --no-cruise <node_id> | nav abort",
        "usage_hibernate": "Uso: hibernate until_arrival | hibernate <años>",
        "hibernate_number": "hibernate: <años> debe ser número",
        "hibernate_gt0": "hibernate: <años> debe ser > 0",
        "usage_salvage": "Uso: drone salvage scrap <drone_id> [node_id] <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage drone(s) <drone_id> [node_id] | drone salvage data <drone_id> [node_id]",
        "usage_salvage_scrap": "Uso: drone salvage scrap <drone_id> <node_id> <amount>",
        "salvage_amount_int": "salvage: amount debe ser entero",
        "salvage_amount_gt0": "salvage: amount debe ser > 0",
        "salvage_missing_node": "Missing node_id. Example: drone salvage modules D1 ECHO_7",
        "usage_salvage_drone": "Uso: drone salvage drone(s) <drone_id> [node_id]",
        "usage_salvage_data": "Uso: drone salvage data <drone_id> [node_id]",
        "usage_inventory": "Uso: inventory|cargo | inventory|cargo audit",
        "config_set_lang": "config set lang <en|es>",
        "usage_config": "Uso: config set lang <en|es> | config show",
        "usage_mail": "Uso: mail inbox | mail read <id|latest>",
        "usage_mail_read": "Uso: mail read <id|latest>",
        "usage_intel": "Uso: intel | intel <amount> | intel all | intel show <intel_id> | intel import <path> | intel export <path>",
        "usage_module": "Uso: module inspect <module_id> | modules",
        "usage_auth": "Uso: auth status | auth recover <level>",
        "intel_amount_gt0": "intel: amount debe ser > 0",
        "usage_jobs": "Uso: jobs | jobs <amount> | jobs all",
        "jobs_amount_gt0": "jobs: amount debe ser > 0",
        "usage_route": "Uso: route solve <node_id>",
        "usage_relay": "Uso: relay uplink",
        "usage_map": "Uso: map path <node_id> (alias de nav map path <node_id>)",
        "usage_ship": "Uso: ship sectors | ship map | ship survey <target>",
        "sectors_migrated": "El comando 'sectors' fue eliminado. Usa: ship sectors",
        "map_ship_migrated": "El comando 'map ship' fue eliminado. Usa: ship sectors",
        "map_graph_migrated": "El comando 'map graph' fue movido. Usa: nav map graph [node_id]",
        "usage_locate": "Uso: locate <system_id>",
        "usage_diag": "Uso: diag <system_id>",
        "usage_install": "Instalación solo con drones. Usa: drone install <drone_id> <module_id>",
        "usage_ls": "Uso: ls [<path>]",
        "usage_cat": "Uso: cat <path>",
        "usage_about": "Uso: about <system_id>",
        "usage_man": "Uso: man <comando>",
        "usage_boot": "Uso: boot <service_name>",
        "usage_power": "Uso: power status | power plan cruise|normal | power on <system_id> | power off <system_id>",
        "usage_power_plan": "Uso: power plan cruise|normal",
        "usage_power_on": "Uso: power on <system_id>",
        "usage_power_off": "Uso: power off <system_id>",
        "usage_shutdown": "Uso: shutdown <system_id>",
        "usage_drone": "Uso: drone status [drone_id] | drone deploy <drone_id> <sector_id> | drone move <drone_id> <target_id> | drone survey <drone_id> [node_id] | drone recall <drone_id> | drone autorecall <drone_id> <on|off|porcentaje> | drone repair <drone_id> <target_id> | drone install <drone_id> <module_id>",
        "usage_drone_status": "Uso: drone status [drone_id]",
        "usage_drone_recall": "Uso: drone recall <drone_id>",
        "usage_drone_reboot": "Uso: drone reboot <drone_id>",
        "usage_drone_repair": "Uso: drone repair <drone_id> <target_id>",
        "usage_drone_move": "Uso: drone move <drone_id> <target_id>",
        "usage_drone_survey": "Uso: drone survey <drone_id> [node_id]",
        "usage_drone_autorecall": "Uso: drone autorecall <drone_id> <on|off|porcentaje>",
        "drone_autorecall_amount": "drone autorecall: el porcentaje debe ser número en (0, 100]",
        "usage_drone_install": "Uso: drone install <drone_id> <module_id>",
        "usage_drone_salvage": "Uso: drone salvage scrap <drone_id> [node_id] <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage drone(s) <drone_id> [node_id] | drone salvage data <drone_id> [node_id]",
        "usage_drone_salvage_scrap": "Uso: drone salvage scrap <drone_id> <node_id> <amount>",
        "usage_drone_salvage_drone": "Uso: drone salvage drone(s) <drone_id> [node_id]",
        "usage_drone_salvage_data": "Uso: drone salvage data <drone_id> [node_id]",
        "usage_drone_deploy": "Uso: drone deploy <drone_id> <sector_id> | drone deploy! <drone_id> <sector_id>",
        "unknown_drone_subcommand": "Subcomando drone desconocido. Usa: drone status | drone deploy ... | drone move ... | drone survey ... | drone recall ... | drone autorecall ...",
        "usage_repair": "Uso: drone repair <drone_id> <target_id> | repair <system_id> --selftest",
        "module_install_migrated": "module install/install fue eliminado. Usa: drone install <drone_id> <module_id>",
        "unknown_command_suggestion": "Comando desconocido: {cmd}. ¿Quizá quisiste decir: {suggestion}?",
        "unknown_command": "Comando desconocido: {cmd}",
    },
}


def format_parse_error(err: ParseError, locale: str) -> str:
    templates = _PARSE_ERROR_MESSAGES.get(locale, _PARSE_ERROR_MESSAGES["en"])
    tmpl = templates.get(err.key, _PARSE_ERROR_MESSAGES["en"].get(err.key, err.key))
    try:
        return tmpl.format(**(err.params or {}))
    except Exception:
        return tmpl


def parse_command(line: str):
    line = line.strip()
    if not line:
        return None

    parts = line.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in {"quit", "exit"}:
        return "EXIT"

    if cmd == "help":
        if len(args) == 0:
            return "HELP"
        if len(args) == 1 and args[0] in {"--verbose", "-v"}:
            return "HELP_VERBOSE"
        raise ParseError("usage_help")
    if cmd == "clear":
        return "CLEAR"

    if cmd == "contacts":
        if len(args) != 0:
            raise ParseError("usage_nav")
        return ("NAV_MAP", "contacts", None)

    if cmd == "scan":
        return "SCAN"

    if cmd == "status":
        return Status()

    if cmd == "jobs":
        if len(args) == 0:
            return "JOBS"
        if len(args) == 1:
            if args[0].lower() == "all":
                return ("JOBS", "all")
            try:
                amount = int(args[0])
            except ValueError as e:
                raise ParseError("usage_jobs") from e
            if amount <= 0:
                raise ParseError("jobs_amount_gt0")
            return ("JOBS", amount)
        raise ParseError("usage_jobs")
    if cmd == "job":
        if len(args) != 2 or args[0] != "cancel":
            raise ParseError("usage_job_cancel")
        return JobCancel(job_id=args[1])

    galaxy_scales = {"sector", "local", "regional", "global"}

    if cmd in {"nav", "navigation", "travel"}:
        if len(args) == 0:
            raise ParseError("usage_nav")
        if args[0] == "map":
            if len(args) == 2 and args[1] in {"sectors", "routes", "contacts", "graph", "galaxy"}:
                return ("NAV_MAP", args[1], None)
            if len(args) == 3 and args[1] == "galaxy" and args[2] in galaxy_scales:
                return ("NAV_MAP", "galaxy", args[2])
            if len(args) == 3 and args[1] == "graph":
                return ("NAV_MAP", "graph", args[2])
            if len(args) == 3 and args[1] == "path":
                return ("NAV_MAP", "path", args[2])
            raise ParseError("usage_nav")
        if len(args) == 1 and args[0] in {"sectors", "routes", "contacts", "galaxy"}:
            return ("NAV_MAP", args[0], None)
        if len(args) == 2 and args[0] == "galaxy" and args[1] in galaxy_scales:
            return ("NAV_MAP", "galaxy", args[1])
        if len(args) == 1 and args[0] == "graph":
            return ("NAV_MAP", "graph", None)
        if len(args) == 2 and args[0] == "graph":
            return ("NAV_MAP", "graph", args[1])
        if len(args) == 1 and args[0] == "abort":
            return TravelAbort()
        if len(args) == 2 and args[0] == "--no-cruise":
            return Travel(node_id=args[1], no_cruise=True)
        if len(args) == 1:
            return Travel(node_id=args[0])
        raise ParseError("usage_nav")

    if cmd == "routes":
        if len(args) != 0:
            raise ParseError("usage_nav")
        return ("NAV_MAP", "routes", None)

    if cmd == "graph":
        if len(args) == 0:
            return ("NAV_MAP", "graph", None)
        if len(args) == 1:
            return ("NAV_MAP", "graph", args[0])
        raise ParseError("usage_nav")

    if cmd == "path":
        if len(args) == 1:
            return ("NAV_MAP", "path", args[0])
        raise ParseError("usage_nav")

    if cmd == "uplink":
        return "UPLINK"

    if cmd == "alerts":
        if len(args) == 0:
            return "ALERTS"
        if len(args) == 2 and args[0] == "explain":
            return ("ALERTS_EXPLAIN", args[1])
        raise ParseError("usage_alerts")

    if cmd == "logs":
        return "LOGS"
    if cmd == "log":
        if len(args) == 0:
            raise ParseError("usage_log_copy")
        if len(args) == 1 and args[0] == "copy":
            return ("LOG_COPY", None)
        if len(args) == 1 and args[0].startswith("copy") and args[0][4:].isdigit():
            return ("LOG_COPY", int(args[0][4:]))
        if len(args) == 2 and args[0] == "copy":
            try:
                amount = int(args[1])
            except ValueError as e:
                raise ParseError("log_copy_int") from e
            if amount <= 0:
                raise ParseError("log_copy_gt0")
            return ("LOG_COPY", amount)
        raise ParseError("usage_log_copy")

    if cmd == "wait":
        if len(args) != 1:
            raise ParseError("usage_wait")
        try:
            seconds = float(args[0])
        except ValueError as e:
            raise ParseError("wait_number") from e
        if seconds <= 0:
            raise ParseError("wait_gt0")
        return ("WAIT", seconds)

    if cmd == "debug":
        if len(args) == 2 and args[0] == "scenario" and args[1] in {"prologue", "sandbox", "dev"}:
            return ("DEBUG_SCENARIO", args[1])
        if len(args) == 2 and args[0] == "seed":
            try:
                seed = int(args[1])
            except ValueError as e:
                raise ParseError("debug_seed_int") from e
            return ("DEBUG_SEED", seed)
        if len(args) == 1 and args[0] == "modules":
            return ("DEBUG_MODULES", None)
        if len(args) == 1 and args[0] in {"arcs", "placement"}:
            return ("DEBUG_ARCS", None)
        if len(args) == 1 and args[0] == "lore":
            return ("DEBUG_LORE", None)
        if len(args) == 1 and args[0] == "deadnodes":
            return ("DEBUG_DEADNODES", None)
        if len(args) == 1 and args[0] == "galaxy":
            return ("DEBUG_GALAXY", None)
        if len(args) == 3 and args[0] == "galaxy" and args[1] == "map" and args[2] in galaxy_scales:
            return ("DEBUG_GALAXY_MAP", args[2])
        if len(args) != 1 or args[0] not in {"on", "off", "status"}:
            raise ParseError("usage_debug")
        return ("DEBUG", args[0])

    if cmd == "dock":
        if len(args) != 1:
            raise ParseError("usage_dock")
        return Dock(node_id=args[0])
    if cmd == "undock":
        if len(args) != 0:
            raise ParseError("usage_undock")
        return Undock()

    if cmd == "hibernate":
        if len(args) != 1:
            raise ParseError("usage_hibernate")
        if args[0].lower() == "until_arrival":
            return Hibernate(mode="until_arrival")
        try:
            years = float(args[0])
        except ValueError as e:
            raise ParseError("hibernate_number") from e
        if years <= 0:
            raise ParseError("hibernate_gt0")
        return Hibernate(mode="years", years=years)

    if cmd == "salvage":
        if len(args) < 2:
            raise ParseError("usage_salvage")
        kind = args[0].lower()
        if kind == "scrap":
            if len(args) != 4:
                raise ParseError("usage_salvage_scrap")
            try:
                amount = int(args[3])
            except ValueError as e:
                raise ParseError("salvage_amount_int") from e
            if amount <= 0:
                raise ParseError("salvage_amount_gt0")
            return SalvageScrap(drone_id=args[1], node_id=args[2], amount=amount)
        if kind in {"module", "modules"}:
            if len(args) != 3:
                raise ParseError("salvage_missing_node")
            return SalvageModule(drone_id=args[1], node_id=args[2])
        if kind in {"drone", "drones"}:
            if len(args) != 3:
                raise ParseError("usage_salvage_drone")
            return SalvageDrone(drone_id=args[1], node_id=args[2])
        if kind == "data":
            if len(args) != 3:
                raise ParseError("usage_salvage_data")
            return SalvageData(drone_id=args[1], node_id=args[2])
        raise ParseError("usage_salvage")

    if cmd in {"inventory", "cargo"}:
        if len(args) == 0:
            return "INVENTORY"
        if len(args) == 1 and args[0].lower() == "audit":
            return CargoAudit()
        raise ParseError("usage_inventory")

    if cmd in {"module", "modules"}:
        if len(args) == 0:
            return "MODULES"
        if len(args) == 2 and args[0] == "install":
            raise ParseError("module_install_migrated")
        if len(args) == 2 and args[0] == "inspect":
            return ("MODULE_INSPECT", args[1])
        raise ParseError("usage_module")

    if cmd == "config":
        if len(args) == 0 or (len(args) == 1 and args[0] == "show"):
            return "CONFIG_SHOW"
        if len(args) == 3 and args[0] == "set" and args[1] == "lang":
            lang = args[2].lower()
            if lang not in {"en", "es"}:
                raise ParseError("config_set_lang")
            return ("CONFIG_SET_LANG", lang)
        raise ParseError("usage_config")

    if cmd == "auth":
        if len(args) == 1 and args[0].lower() == "status":
            return "AUTH_STATUS"
        if len(args) == 2 and args[0].lower() == "recover":
            level = args[1].strip()
            if level:
                return AuthRecover(level=level.upper())
        raise ParseError("usage_auth")

    if cmd == "mail":
        if len(args) > 2:
            raise ParseError("usage_mail")
        if len(args) == 0:
            raise ParseError("usage_mail")
        if len(args) == 1:
            if args[0] == "read":
                raise ParseError("usage_mail_read")
            return ("MAIL_LIST", args[0])
        if len(args) == 2 and args[0] == "read":
            return ("MAIL_READ", args[1])
        raise ParseError("usage_mail")

    if cmd == "intel":
        if len(args) == 0:
            return "INTEL_LIST"
        if len(args) == 1:
            if args[0].lower() == "all":
                return ("INTEL_LIST", "all")
            try:
                amount = int(args[0])
            except ValueError as e:
                raise ParseError("usage_intel") from e
            if amount <= 0:
                raise ParseError("intel_amount_gt0")
            return ("INTEL_LIST", amount)
        if len(args) == 2 and args[0] == "import":
            return ("INTEL_IMPORT", args[1])
        if len(args) == 2 and args[0] == "show":
            return ("INTEL_SHOW", args[1])
        if len(args) == 2 and args[0] == "export":
            return ("INTEL_EXPORT", args[1])
        raise ParseError("usage_intel")

    if cmd == "route":
        if len(args) != 2 or args[0] != "solve":
            raise ParseError("usage_route")
        return RouteSolve(node_id=args[1])

    if cmd == "relay":
        if len(args) == 1 and args[0] == "uplink":
            return "UPLINK"
        raise ParseError("usage_relay")

    if cmd == "sectors":
        raise ParseError("sectors_migrated")

    if cmd == "map":
        if len(args) == 2 and args[0] == "path":
            return ("NAV_MAP", "path", args[1])
        if len(args) >= 1 and args[0] == "ship":
            raise ParseError("map_ship_migrated")
        if len(args) >= 1 and args[0] == "graph":
            raise ParseError("map_graph_migrated")
        raise ParseError("usage_map")

    if cmd == "ship":
        if len(args) == 1 and args[0] in {"sectors", "map"}:
            return "SHIP_SECTORS"
        if len(args) == 2 and args[0] == "survey":
            return ("SHIP_SURVEY", args[1])
        raise ParseError("usage_ship")

    if cmd == "locate":
        if len(args) != 1:
            raise ParseError("usage_locate")
        return ("LOCATE", args[0])

    if cmd == "diag":
        if len(args) != 1:
            raise ParseError("usage_diag")
        return Diag(system_id=args[0])

    if cmd == "install":
        raise ParseError("module_install_migrated")

    if cmd == "ls":
        if len(args) > 1:
            raise ParseError("usage_ls")
        path = args[0] if args else "/"
        return ("LS", path)

    if cmd == "cat":
        if len(args) != 1:
            raise ParseError("usage_cat")
        return ("CAT", args[0])

    if cmd == "about":
        if len(args) != 1:
            raise ParseError("usage_about")
        return ("ABOUT", args[0])

    if cmd == "man":
        if len(args) != 1:
            raise ParseError("usage_man")
        return ("MAN", args[0])

    if cmd == "boot":
        if len(args) != 1:
            raise ParseError("usage_boot")
        return Boot(service_name=args[0])

    if cmd == "power":
        if not args:
            raise ParseError("usage_power")
        sub = args[0].lower()
        if sub == "status":
            return "POWER_STATUS"
        if sub == "plan":
            if len(args) != 2 or args[1].lower() not in {"cruise", "normal"}:
                raise ParseError("usage_power_plan")
            return PowerPlan(mode=args[1].lower())
        if sub == "off":
            if len(args) != 2:
                raise ParseError("usage_power_off")
            return PowerShed(system_id=args[1])
        if sub == "on":
            if len(args) != 2:
                raise ParseError("usage_power_on")
            return SystemOn(system_id=args[1])
        raise ParseError("usage_power")

    if cmd in {"shutdown", "system"}:
        if cmd == "system":
            if len(args) != 2 or args[0].lower() not in {"off", "on"}:
                raise ParseError("usage_power")
            if args[0].lower() == "off":
                return PowerShed(system_id=args[1])
            return SystemOn(system_id=args[1])
        if len(args) != 1:
            raise ParseError("usage_shutdown")
        return PowerShed(system_id=args[0])

    if cmd == "drone":
        if len(args) < 1:
            raise ParseError("usage_drone")
        sub = args[0].lower()
        if sub == "status":
            if len(args) == 1:
                return "DRONE_STATUS"
            if len(args) == 2:
                return ("DRONE_STATUS", args[1])
            raise ParseError("usage_drone_status")
        if sub == "recall":
            if len(args) != 2:
                raise ParseError("usage_drone_recall")
            return DroneRecall(drone_id=args[1])
        if sub == "reboot":
            if len(args) != 2:
                raise ParseError("usage_drone_reboot")
            return DroneReboot(drone_id=args[1])
        if sub == "repair":
            if len(args) != 3:
                raise ParseError("usage_drone_repair")
            return Repair(drone_id=args[1], system_id=args[2])
        if sub == "move":
            if len(args) != 3:
                raise ParseError("usage_drone_move")
            return DroneMove(drone_id=args[1], target_id=args[2])
        if sub == "survey":
            if len(args) not in {2, 3}:
                raise ParseError("usage_drone_survey")
            drone_id = args[1]
            node_id = args[2] if len(args) == 3 else None
            return DroneSurvey(drone_id=drone_id, node_id=node_id)
        if sub == "autorecall":
            if len(args) != 3:
                raise ParseError("usage_drone_autorecall")
            drone_id = args[1]
            value = args[2].strip().lower()
            if value in {"on", "off"}:
                return ("DRONE_AUTORECALL_ENABLED", drone_id, value == "on")
            if value.endswith("%"):
                value = value[:-1].strip()
            try:
                amount = float(value)
            except ValueError as e:
                raise ParseError("drone_autorecall_amount") from e
            if not (0.0 < amount <= 100.0):
                raise ParseError("drone_autorecall_amount")
            return ("DRONE_AUTORECALL_THRESHOLD", drone_id, amount / 100.0)
        if sub == "install":
            if len(args) != 3:
                raise ParseError("usage_drone_install")
            return Install(drone_id=args[1], module_id=args[2])
        if sub == "salvage":
            if len(args) < 3:
                raise ParseError("usage_drone_salvage")
            kind = args[1].lower()
            rest = args[2:]
            if kind == "scrap":
                if len(rest) not in {2, 3}:
                    raise ParseError("usage_drone_salvage_scrap")
                if len(rest) == 2:
                    drone_id = rest[0]
                    node_id = None
                    amount_str = rest[1]
                else:
                    drone_id = rest[0]
                    node_id = rest[1]
                    amount_str = rest[2]
                try:
                    amount = int(amount_str)
                except ValueError as e:
                    raise ParseError("salvage_amount_int") from e
                if amount <= 0:
                    raise ParseError("salvage_amount_gt0")
                return SalvageScrap(drone_id=drone_id, node_id=node_id, amount=amount)
            if kind in {"module", "modules"}:
                if len(rest) not in {1, 2}:
                    raise ParseError("salvage_missing_node")
                drone_id = rest[0]
                node_id = rest[1] if len(rest) == 2 else None
                return SalvageModule(drone_id=drone_id, node_id=node_id)
            if kind in {"drone", "drones"}:
                if len(rest) not in {1, 2}:
                    raise ParseError("usage_drone_salvage_drone")
                drone_id = rest[0]
                node_id = rest[1] if len(rest) == 2 else None
                return SalvageDrone(drone_id=drone_id, node_id=node_id)
            if kind == "data":
                if len(rest) not in {1, 2}:
                    raise ParseError("usage_drone_salvage_data")
                drone_id = rest[0]
                node_id = rest[1] if len(rest) == 2 else None
                return SalvageData(drone_id=drone_id, node_id=node_id)
            raise ParseError("usage_drone_salvage")
        emergency = False
        if sub in {"deploy", "deploy!"}:
            emergency = sub.endswith("!")
            rest = args[1:]
            if rest and rest[0] == "--emergency":
                emergency = True
                rest = rest[1:]
            if len(rest) != 2:
                raise ParseError("usage_drone_deploy")
            return DroneDeploy(drone_id=rest[0], sector_id=rest[1], emergency=emergency)
        raise ParseError("unknown_drone_subcommand")

    if cmd == "repair":
        if len(args) == 2 and args[1] == "--selftest":
            return SelfTestRepair(system_id=args[0])
        if len(args) != 2:
            raise ParseError("usage_repair")
        return Repair(drone_id=args[0], system_id=args[1])

    suggestion = _suggest_command(cmd)
    if suggestion:
        raise ParseError("unknown_command_suggestion", {"cmd": cmd, "suggestion": suggestion})
    raise ParseError("unknown_command", {"cmd": cmd})


def _suggest_command(cmd: str) -> str | None:
    commands = [
        "help",
        "status",
        "jobs",
        "job",
        "alerts",
        "diag",
        "about",
        "man",
        "auth",
        "config",
        "mail",
        "intel",
        "uplink",
        "relay",
        "ls",
        "cat",
        "contacts",
        "scan",
        "routes",
        "graph",
        "path",
        "map",
        "ship",
        "locate",
        "dock",
        "undock",
        "nav",
        "navigation",
        "travel",
        "salvage",
        "drone",
        "repair",
        "inventory",
        "cargo",
        "boot",
        "route",
        "hibernate",
        "wait",
        "debug",
        "power",
        "logs",
        "module",
        "exit",
        "quit",
    ]
    matches = difflib.get_close_matches(cmd, commands, n=1, cutoff=0.6)
    return matches[0] if matches else None
