from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.cli import repl
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
        loc_id = ship.current_node_id or state.world.current_node_id
        node = state.world.space.nodes.get(loc_id)
        node_name = node.name if node else loc_id
        loc = f"{loc_id} ({node_name})"
    return (
        f"t={state.clock.t:.1f}s | mode={mode} | loc={loc} | "
        f"P_gen={p.p_gen_kw:.2f}kW P_load={p.p_load_kw:.2f}kW Q={p.power_quality:.2f} SoC={soc:.2f}"
    )


def build_status_lines(state) -> list[str]:
    return _capture_output(repl.render_status, state)


def build_alerts_lines(state) -> list[str]:
    return _capture_output(repl.render_alerts, state)


def build_jobs_lines(state) -> list[str]:
    return _capture_output(repl.render_jobs, state)


def build_help_lines() -> list[str]:
    return _capture_output(repl.print_help)


def build_command_output(func, *args, **kwargs) -> list[str]:
    return _capture_output(func, *args, **kwargs)


def format_event_lines(state, events, origin_override: str | None = None) -> list[str]:
    return _capture_output(repl.render_events, state, events, origin_override)
