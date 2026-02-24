from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.cli import repl
from retorno.util.timefmt import format_elapsed_short
from retorno.config.balance import Balance


def _capture_output(func, *args, **kwargs) -> list[str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    text = buf.getvalue()
    lines = [line.rstrip() for line in text.splitlines()]
    # Drop leading/trailing empty lines for cleaner panels.
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def build_header(state) -> str:
    ship = state.ship
    p = ship.power
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    mode = "DEBUG" if state.os.debug_enabled else "NORMAL"
    if ship.in_transit:
        remaining_s = max(0.0, ship.arrival_t - state.clock.t)
        remaining_years = remaining_s / Balance.YEAR_S if Balance.YEAR_S else 0.0
        loc = f"en route to {ship.transit_to} (ETA {remaining_years:.2f}y)"
    else:
        loc_id = state.world.current_node_id
        node = state.world.space.nodes.get(loc_id)
        node_name = node.name if node else loc_id
        loc = f"{loc_id} ({node_name})"
    elapsed = format_elapsed_short(state.clock.t, include_seconds=True)
    return f"{elapsed} | ship_mode={mode} | {loc}"


def build_power_lines(state) -> list[str]:
    p = state.ship.power
    soc = (p.e_batt_kwh / p.e_batt_max_kwh) if p.e_batt_max_kwh else 0.0
    net = p.p_gen_kw - p.p_load_kw
    return [
        f"P_gen={p.p_gen_kw:.2f}kW  P_load={p.p_load_kw:.2f}kW  net={net:+.2f}kW  SoC={soc:.2f}  Q={p.power_quality:.2f}"
    ]


def build_status_lines(state) -> list[str]:
    lines = _capture_output(repl.render_status, state)
    sys_lines = []
    in_systems = False
    for line in lines:
        if line.strip().lower() == "systems:":
            in_systems = True
            continue
        if in_systems and line.strip().startswith("-"):
            compact = line.strip()
            if compact.startswith("- "):
                compact = compact[2:]
            compact = compact.replace("state=", "").replace("health=", "")
            parts = [p for p in compact.split() if not (p.startswith("svc=") or p.startswith("running="))]
            compact = " ".join(parts)
            sys_lines.append(compact)
    return sys_lines if sys_lines else lines


def build_alerts_lines(state) -> list[str]:
    lines = _capture_output(repl.render_alerts, state)
    if lines and lines[0].strip().upper().startswith("=== ALERTS"):
        lines = lines[1:]
    return lines


def build_jobs_lines(state) -> list[str]:
    lines = _capture_output(repl.render_jobs, state)
    if lines and lines[0].strip().upper() == "=== JOBS ===":
        lines = lines[1:]
    if not lines:
        return ["Active jobs (queued/running):", "- (none)"]
    if lines[0].strip().lower().startswith("active"):
        lines[0] = "Active jobs (queued/running):"
    else:
        lines.insert(0, "Active jobs (queued/running):")
    filtered = []
    for line in lines:
        if line.strip().lower().startswith("recent complete/failed"):
            break
        if line.lstrip().startswith("- ") and ":" in line:
            prefix, rest = line.split(":", 1)
            # Replace job id prefix with drone_id if present.
            if " owner=" in rest:
                owner_part = rest.split(" owner=", 1)[1]
                owner_id = owner_part.split()[0]
                if owner_id != "-":
                    line = f"- {owner_id}:{rest}"
        filtered.append(line)
    return filtered


def build_help_lines() -> list[str]:
    return _capture_output(repl.print_help)


def build_command_output(func, *args, **kwargs) -> list[str]:
    return _capture_output(func, *args, **kwargs)


def format_event_lines(state, events, origin_override: str | None = None) -> list[str]:
    return _capture_output(repl.render_events, state, events, origin_override)
