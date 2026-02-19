from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.core.engine import Engine
from retorno.model.events import EventType, Severity
from retorno.model.systems import SystemState
from retorno.model.os import FSNodeType, list_dir, normalize_path, read_file


def print_help() -> None:
    print(
        "\nComandos (resumen):\n"
        "  help\n"
        "  ls [path] | cat <path>\n"
        "  man <topic> | about <system_id>\n"
        "  status | power status | alerts | logs\n"
        "  contacts | scan\n"
        "  dock <node_id> | salvage <node_id> [scrap] [amount]\n"
        "  diag <system_id> | boot <service_name> | repair <drone_id> <system_id>\n"
        "  drone status | drone deploy | drone deploy!\n"
        "  wait <segundos>\n"
        "  exit | quit\n"
        "\nSugerencias:\n"
        "  ls /manuals/commands\n"
        "  cat /mail/inbox/0001.txt\n"
    )


def render_events(events) -> None:
    if not events:
        return
    for e in events:
        sev = e.severity.value.upper()
        if e.type == EventType.SYSTEM_STATE_CHANGED and e.data.get("from") and e.data.get("to"):
            system_id = e.source.id if e.source.kind == "ship_system" else "system"
            cause = e.data.get("cause", "")
            health = e.data.get("health", None)
            health_text = f"{health:.2f}" if isinstance(health, (int, float)) else "n/a"
            cause_text = f"cause={cause}" if cause else "cause=?"
            print(f"[{sev}] system_state_changed :: {system_id}: {e.data['from']} -> {e.data['to']} ({cause_text}, health={health_text})")
            continue
        print(f"[{sev}] {e.type.value} :: {e.message}")


def render_status(state) -> None:
    ship = state.ship
    p = ship.power
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    print("\n=== STATUS ===")
    print(f"time: {state.clock.t:.1f}s")
    node = state.world.space.nodes.get(state.world.current_node_id)
    node_name = node.name if node else state.world.current_node_id
    print(f"location: {state.world.current_node_id} ({node_name})")
    print(f"power: P_gen={p.p_gen_kw:.2f}kW  P_load={p.p_load_kw:.2f}kW  SoC={soc:.2f}  Q={p.power_quality:.2f}  brownout={p.brownout}")
    print(f"inventory: scrap={ship.inventory.scrap}")
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
    print("\n=== POWER ===")
    print(f"P_gen={p.p_gen_kw:.2f} kW")
    print(f"P_load={p.p_load_kw:.2f} kW")
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
    print(f"state: {sys.state.value}")
    print(f"health: {sys.health:.2f}")
    print(f"p_nom: {sys.p_nom_kw:.2f} kW  p_eff: {sys.p_effective_kw():.2f} kW")
    print(f"priority: {sys.priority}")
    print(f"forced_offline: {sys.forced_offline}")
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
    # Ordena por severidad y recencia
    sev_rank = {"critical": 0, "warn": 1, "info": 2}
    active.sort(key=lambda a: (sev_rank.get(a.severity.value, 9), -a.last_seen_t))
    for a in active:
        print(f"- {a.severity.value.upper():8s} {a.alert_key:24s} unacked={a.unacked_s}s")


def render_logs(state, limit: int = 15) -> None:
    print("\n=== EVENTS (recent) ===")
    for e in state.events.recent[-limit:]:
        print(f"- t={e.t:6d} [{e.severity.value.upper():8s}] {e.type.value}: {e.message}")


def render_drone_status(state) -> None:
    print("\n=== DRONES ===")
    for did, d in state.ship.drones.items():
        print(f"- {did}: status={d.status.value} loc={d.location.kind}:{d.location.id} battery={d.battery:.2f} integrity={d.integrity:.2f} dose={d.dose_rad:.3f}")


def render_inventory(state) -> None:
    print("\n=== INVENTORY ===")
    print(f"scrap: {state.ship.inventory.scrap}")
    if state.ship.inventory.components:
        print("components:")
        for cid, amt in state.ship.inventory.components.items():
            print(f"- {cid}: {amt}")

def render_contacts(state) -> None:
    print("\n=== CONTACTS ===")
    if not state.world.known_contacts:
        print("(no signals detected)")
        return
    for cid in sorted(state.world.known_contacts):
        node = state.world.space.nodes.get(cid)
        if node:
            print(f"- {cid}: {node.name} ({node.kind})")
        else:
            print(f"- {cid}")

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
    path = normalize_path(path)
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


def render_about(state, system_id: str) -> None:
    render_cat(state, f"/manuals/systems/{system_id}.txt")


def render_man(state, topic: str) -> None:
    try:
        print(f"\n=== MAN {topic} ===")
        print(read_file(state.os.fs, f"/manuals/commands/{topic}.txt", state.os.access_level))
        return
    except Exception:
        pass
    try:
        print(f"\n=== MAN {topic} ===")
        print(read_file(state.os.fs, f"/manuals/systems/{topic}.txt", state.os.access_level))
    except Exception:
        print("No manual found")

def main() -> None:
    from retorno.cli.parser import ParseError, parse_command

    engine = Engine()
    state = create_initial_state_prologue()
    engine.tick(state, 1.0)

    print("RETORNO (prologue)")
    print("Tip: cat /mail/inbox/0001.txt")
    render_status(state)
    render_alerts(state)

    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
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

        if parsed == "EXIT":
            break
        if parsed == "HELP":
            print_help()
            continue
        if isinstance(parsed, tuple) and parsed[0] == "LS":
            render_ls(state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "CAT":
            render_cat(state, parsed[1])
            continue
        if parsed == "CONTACTS":
            render_contacts(state)
            continue
        if parsed == "ALERTS":
            render_alerts(state)
            continue
        if parsed == "LOGS":
            render_logs(state)
            continue
        if parsed == "POWER_STATUS":
            render_power_status(state)
            continue
        if parsed == "DRONE_STATUS":
            render_drone_status(state)
            continue
        if isinstance(parsed, tuple) and parsed[0] == "ABOUT":
            render_about(state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "MAN":
            render_man(state, parsed[1])
            continue
        if isinstance(parsed, tuple) and parsed[0] == "WAIT":
            seconds = parsed[1]
            ev = engine.tick(state, seconds)
            render_events(ev)
            # tras esperar, muestra alertas si hay critical
            if any(e.severity == Severity.CRITICAL for e in ev):
                render_alerts(state)
            continue

        # Acciones del motor
        if parsed.__class__.__name__ == "Diag":
            render_diag(state, parsed.system_id)
            continue
        if parsed.__class__.__name__ == "Status":
            render_status(state)
            continue

        ev = engine.apply_action(state, parsed)
        render_events(ev)

    print("bye")


if __name__ == "__main__":
    main()
