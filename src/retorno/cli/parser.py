from __future__ import annotations

from dataclasses import dataclass

from retorno.core.actions import Boot, Diag, Dock, DroneDeploy, PowerShed, Repair, Salvage, Status


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

    if cmd == "contacts":
        return "CONTACTS"

    if cmd == "scan":
        return "CONTACTS"

    if cmd == "status":
        return Status()

    if cmd == "alerts":
        return "ALERTS"

    if cmd == "logs":
        return "LOGS"

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

    if cmd == "dock":
        if len(args) != 1:
            raise ParseError("Uso: dock <node_id>")
        return Dock(node_id=args[0])

    if cmd == "salvage":
        if len(args) not in {1, 2, 3}:
            raise ParseError("Uso: salvage <node_id> [scrap] [amount]")
        node_id = args[0]
        kind = "scrap"
        amount = 1
        if len(args) >= 2:
            kind = args[1]
        if len(args) == 3:
            try:
                amount = int(args[2])
            except ValueError as e:
                raise ParseError("salvage: amount debe ser entero") from e
        return Salvage(node_id=node_id, kind=kind, amount=amount)

    if cmd == "diag":
        if len(args) != 1:
            raise ParseError("Uso: diag <system_id>")
        return Diag(system_id=args[0])

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
            raise ParseError("Uso: power shed <system_id> | power status")
        sub = args[0].lower()
        if sub == "status":
            return "POWER_STATUS"
        if sub == "shed":
            if len(args) != 2:
                raise ParseError("Uso: power shed <system_id>")
            return PowerShed(system_id=args[1])
        raise ParseError("Subcomando power desconocido. Usa: power status | power shed <system_id>")

    if cmd == "drone":
        if len(args) < 1:
            raise ParseError("Uso: drone deploy <drone_id> <sector_id> | drone status")
        sub = args[0].lower()
        if sub == "status":
            return "DRONE_STATUS"
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
        if len(args) != 2:
            raise ParseError("Uso: repair <drone_id> <system_id>")
        return Repair(drone_id=args[0], system_id=args[1])

    raise ParseError(f"Comando desconocido: {cmd}")
