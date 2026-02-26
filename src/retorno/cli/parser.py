from __future__ import annotations

from dataclasses import dataclass
import difflib

from retorno.core.actions import (
    Boot,
    CargoAudit,
    Diag,
    Dock,
    DroneDeploy,
    DroneMove,
    DroneRecall,
    DroneReboot,
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
    RouteSolve,
    Status,
    Travel,
    TravelAbort,
)


@dataclass(slots=True)
class ParseError(Exception):
    message: str


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
        return "HELP"
    if cmd == "clear":
        return "CLEAR"

    if cmd == "contacts":
        return "CONTACTS"

    if cmd == "scan":
        return "SCAN"

    if cmd == "status":
        return Status()

    if cmd == "jobs":
        return "JOBS"
    if cmd == "job":
        if len(args) != 2 or args[0] != "cancel":
            raise ParseError("Uso: job cancel <job_id>")
        return JobCancel(job_id=args[1])

    if cmd == "nav":
        return "NAV"

    if cmd == "uplink":
        return "UPLINK"

    if cmd == "alerts":
        if len(args) == 0:
            return "ALERTS"
        if len(args) == 2 and args[0] == "explain":
            return ("ALERTS_EXPLAIN", args[1])
        raise ParseError("Uso: alerts | alerts explain <alert_key>")

    if cmd == "logs":
        return "LOGS"
    if cmd == "log":
        if len(args) == 0:
            raise ParseError("Uso: log copy [n]")
        if len(args) == 1 and args[0] == "copy":
            return ("LOG_COPY", None)
        if len(args) == 1 and args[0].startswith("copy") and args[0][4:].isdigit():
            return ("LOG_COPY", int(args[0][4:]))
        if len(args) == 2 and args[0] == "copy":
            try:
                amount = int(args[1])
            except ValueError as e:
                raise ParseError("log copy: [n] debe ser entero") from e
            if amount <= 0:
                raise ParseError("log copy: [n] debe ser > 0")
            return ("LOG_COPY", amount)
        raise ParseError("Uso: log copy [n]")

    if cmd == "wait":
        if len(args) != 1:
            raise ParseError("Uso: wait <segundos>")
        try:
            seconds = float(args[0])
        except ValueError as e:
            raise ParseError("wait: <segundos> debe ser número") from e
        if seconds <= 0:
            raise ParseError("wait: <segundos> debe ser > 0")
        return ("WAIT", seconds)

    if cmd == "debug":
        if len(args) == 2 and args[0] == "scenario" and args[1] in {"prologue", "sandbox", "dev"}:
            return ("DEBUG_SCENARIO", args[1])
        if len(args) == 2 and args[0] == "seed":
            try:
                seed = int(args[1])
            except ValueError as e:
                raise ParseError("debug seed: <n> debe ser entero") from e
            return ("DEBUG_SEED", seed)
        if len(args) == 1 and args[0] in {"arcs", "placement"}:
            return ("DEBUG_ARCS", None)
        if len(args) == 1 and args[0] == "lore":
            return ("DEBUG_LORE", None)
        if len(args) != 1 or args[0] not in {"on", "off", "status"}:
            raise ParseError("Uso: debug on|off|status | debug scenario prologue|sandbox|dev | debug seed <n> | debug arcs | debug lore")
        return ("DEBUG", args[0])

    if cmd == "dock":
        if len(args) != 1:
            raise ParseError("Uso: dock <node_id>")
        return Dock(node_id=args[0])

    if cmd == "travel":
        if len(args) == 1 and args[0] == "abort":
            return TravelAbort()
        if len(args) == 2 and args[0] == "--no-cruise":
            return Travel(node_id=args[1], no_cruise=True)
        if len(args) != 1:
            raise ParseError("Uso: travel <node_id|name> | travel --no-cruise <dest> | travel abort")
        return Travel(node_id=args[0])

    if cmd == "hibernate":
        if len(args) != 1:
            raise ParseError("Uso: hibernate until_arrival | hibernate <años>")
        if args[0].lower() == "until_arrival":
            return Hibernate(mode="until_arrival")
        try:
            years = float(args[0])
        except ValueError as e:
            raise ParseError("hibernate: <años> debe ser número") from e
        if years <= 0:
            raise ParseError("hibernate: <años> debe ser > 0")
        return Hibernate(mode="years", years=years)

    if cmd == "salvage":
        if len(args) < 2:
            raise ParseError(
                "Uso: drone salvage scrap <drone_id> <node_id> <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage data <drone_id> <node_id>"
            )
        kind = args[0].lower()
        if kind == "scrap":
            if len(args) != 4:
                raise ParseError("Uso: drone salvage scrap <drone_id> <node_id> <amount>")
            try:
                amount = int(args[3])
            except ValueError as e:
                raise ParseError("salvage: amount debe ser entero") from e
            if amount <= 0:
                raise ParseError("salvage: amount debe ser > 0")
            return SalvageScrap(drone_id=args[1], node_id=args[2], amount=amount)
        if kind in {"module", "modules"}:
            if len(args) != 3:
                raise ParseError("Missing node_id. Example: drone salvage modules D1 ECHO_7")
            return SalvageModule(drone_id=args[1], node_id=args[2])
        if kind == "data":
            if len(args) != 3:
                raise ParseError("Uso: drone salvage data <drone_id> <node_id>")
            return SalvageData(drone_id=args[1], node_id=args[2])
        raise ParseError(
            "Uso: drone salvage scrap <drone_id> <node_id> <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage data <drone_id> <node_id>"
        )

    if cmd in {"inventory", "cargo"}:
        if len(args) == 0:
            return "INVENTORY"
        if len(args) == 1 and args[0].lower() == "audit":
            return CargoAudit()
        raise ParseError("Uso: inventory|cargo | inventory|cargo audit")

    if cmd == "modules":
        return "MODULES"

    if cmd == "config":
        if len(args) == 0 or (len(args) == 1 and args[0] == "show"):
            return "CONFIG_SHOW"
        if len(args) == 3 and args[0] == "set" and args[1] == "lang":
            lang = args[2].lower()
            if lang not in {"en", "es"}:
                raise ParseError("config set lang <en|es>")
            return ("CONFIG_SET_LANG", lang)
        raise ParseError("Uso: config set lang <en|es> | config show")

    if cmd == "mail":
        if len(args) > 2:
            raise ParseError("Uso: mail [inbox] | mail read <id|latest>")
        if len(args) == 0:
            return ("MAIL_LIST", "inbox")
        if len(args) == 1:
            return ("MAIL_LIST", args[0])
        if len(args) == 2 and args[0] == "read":
            return ("MAIL_READ", args[1])
        raise ParseError("Uso: mail [inbox] | mail read <id|latest>")

    if cmd == "intel":
        if len(args) == 0:
            return "INTEL_LIST"
        if len(args) == 1:
            if args[0].lower() == "all":
                return ("INTEL_LIST", "all")
            try:
                amount = int(args[0])
            except ValueError as e:
                raise ParseError("Uso: intel | intel <amount> | intel all | intel show <intel_id> | intel import <path> | intel export <path>") from e
            if amount <= 0:
                raise ParseError("intel: amount debe ser > 0")
            return ("INTEL_LIST", amount)
        if len(args) == 2 and args[0] == "import":
            return ("INTEL_IMPORT", args[1])
        if len(args) == 2 and args[0] == "show":
            return ("INTEL_SHOW", args[1])
        if len(args) == 2 and args[0] == "export":
            return ("INTEL_EXPORT", args[1])
        raise ParseError("Uso: intel | intel <amount> | intel all | intel show <intel_id> | intel import <path> | intel export <path>")

    if cmd == "route":
        if len(args) != 1:
            raise ParseError("Uso: route <node_id>")
        return RouteSolve(node_id=args[0])

    if cmd == "relay":
        if len(args) == 1 and args[0] == "uplink":
            return "UPLINK"
        raise ParseError("Uso: relay uplink")

    if cmd == "sectors" or cmd == "map":
        return "SECTORS"

    if cmd == "locate":
        if len(args) != 1:
            raise ParseError("Uso: locate <system_id>")
        return ("LOCATE", args[0])

    if cmd == "diag":
        if len(args) != 1:
            raise ParseError("Uso: diag <system_id>")
        return Diag(system_id=args[0])

    if cmd == "install":
        if len(args) != 1:
            raise ParseError("Uso: install <module_id>")
        return Install(module_id=args[0])

    if cmd == "ls":
        if len(args) > 1:
            raise ParseError("Uso: ls [<path>]")
        path = args[0] if args else "/"
        return ("LS", path)

    if cmd == "cat":
        if len(args) != 1:
            raise ParseError("Uso: cat <path>")
        return ("CAT", args[0])

    if cmd == "about":
        if len(args) != 1:
            raise ParseError("Uso: about <system_id>")
        return ("ABOUT", args[0])

    if cmd == "man":
        if len(args) != 1:
            raise ParseError("Uso: man <comando>")
        return ("MAN", args[0])

    if cmd == "boot":
        if len(args) != 1:
            raise ParseError("Uso: boot <service_name>")
        return Boot(service_name=args[0])

    if cmd == "power":
        if not args:
            raise ParseError("Uso: power status | power plan cruise|normal | power shed <system_id> | power off <system_id>")
        sub = args[0].lower()
        if sub == "status":
            return "POWER_STATUS"
        if sub == "plan":
            if len(args) != 2 or args[1].lower() not in {"cruise", "normal"}:
                raise ParseError("Uso: power plan cruise|normal")
            return PowerPlan(mode=args[1].lower())
        if sub in {"shed", "off"}:
            if len(args) != 2:
                raise ParseError("Uso: power shed <system_id> | power off <system_id>")
            return PowerShed(system_id=args[1])
        if sub == "on":
            if len(args) != 2:
                raise ParseError("Uso: power on <system_id>")
            return SystemOn(system_id=args[1])
        raise ParseError("Subcomando power desconocido. Usa: power status | power plan cruise|normal | power shed/off <system_id> | power on <system_id>")

    if cmd in {"shutdown", "system"}:
        if cmd == "system":
            if len(args) != 2 or args[0].lower() not in {"off", "on"}:
                raise ParseError("Uso: system off <system_id> | system on <system_id>")
            if args[0].lower() == "off":
                return PowerShed(system_id=args[1])
            return SystemOn(system_id=args[1])
        if len(args) != 1:
            raise ParseError("Uso: shutdown <system_id>")
        return PowerShed(system_id=args[0])

    if cmd == "drone":
        if len(args) < 1:
            raise ParseError("Uso: drone deploy <drone_id> <sector_id> | drone status")
        sub = args[0].lower()
        if sub == "status":
            return "DRONE_STATUS"
        if sub == "recall":
            if len(args) != 2:
                raise ParseError("Uso: drone recall <drone_id>")
            return DroneRecall(drone_id=args[1])
        if sub == "reboot":
            if len(args) != 2:
                raise ParseError("Uso: drone reboot <drone_id>")
            return DroneReboot(drone_id=args[1])
        if sub == "repair":
            if len(args) != 3:
                raise ParseError("Uso: drone repair <drone_id> <system_id>")
            return Repair(drone_id=args[1], system_id=args[2])
        if sub == "move":
            if len(args) != 3:
                raise ParseError("Uso: drone move <drone_id> <target_id>")
            return DroneMove(drone_id=args[1], target_id=args[2])
        if sub == "salvage":
            if len(args) < 3:
                raise ParseError(
                    "Uso: drone salvage scrap <drone_id> <node_id> <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage data <drone_id> <node_id>"
                )
            kind = args[1].lower()
            rest = args[2:]
            if kind == "scrap":
                if len(rest) not in {2, 3}:
                    raise ParseError("Uso: drone salvage scrap <drone_id> <node_id> <amount>")
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
                    raise ParseError("salvage: amount debe ser entero") from e
                if amount <= 0:
                    raise ParseError("salvage: amount debe ser > 0")
                return SalvageScrap(drone_id=drone_id, node_id=node_id, amount=amount)
            if kind in {"module", "modules"}:
                if len(rest) not in {1, 2}:
                    raise ParseError("Missing node_id. Example: drone salvage modules D1 ECHO_7")
                drone_id = rest[0]
                node_id = rest[1] if len(rest) == 2 else None
                return SalvageModule(drone_id=drone_id, node_id=node_id)
            if kind == "data":
                if len(rest) != 2:
                    raise ParseError("Uso: drone salvage data <drone_id> <node_id>")
                drone_id = rest[0]
                node_id = rest[1]
                return SalvageData(drone_id=drone_id, node_id=node_id)
            raise ParseError(
                "Uso: drone salvage scrap <drone_id> <node_id> <amount> | drone salvage module(s) <drone_id> [node_id] | drone salvage data <drone_id> <node_id>"
            )
        emergency = False
        if sub in {"deploy", "deploy!"}:
            emergency = sub.endswith("!")
            rest = args[1:]
            if rest and rest[0] == "--emergency":
                emergency = True
                rest = rest[1:]
            if len(rest) != 2:
                raise ParseError("Uso: drone deploy <drone_id> <sector_id> | drone deploy! <drone_id> <sector_id>")
            return DroneDeploy(drone_id=rest[0], sector_id=rest[1], emergency=emergency)
        raise ParseError("Subcomando drone desconocido. Usa: drone status | drone deploy ...")

    if cmd == "repair":
        if len(args) == 2 and args[1] == "--selftest":
            return SelfTestRepair(system_id=args[0])
        if len(args) != 2:
            raise ParseError("Uso: drone repair <drone_id> <system_id> | repair <system_id> --selftest")
        return Repair(drone_id=args[0], system_id=args[1])

    suggestion = _suggest_command(cmd)
    if suggestion:
        raise ParseError(f"Comando desconocido: {cmd}. ¿Quizá quisiste decir: {suggestion} ?")
    raise ParseError(f"Comando desconocido: {cmd}")


def _suggest_command(cmd: str) -> str | None:
    commands = [
        "help",
        "status",
        "jobs",
        "alerts",
        "diag",
        "about",
        "man",
        "config",
        "mail",
        "intel",
        "uplink",
        "relay",
        "ls",
        "cat",
        "contacts",
        "scan",
        "sectors",
        "map",
        "locate",
        "dock",
        "travel",
        "salvage",
        "drone",
        "repair",
        "inventory",
        "cargo",
        "boot",
        "hibernate",
        "wait",
        "debug",
        "power",
        "logs",
        "exit",
        "quit",
    ]
    matches = difflib.get_close_matches(cmd, commands, n=1, cutoff=0.6)
    return matches[0] if matches else None
