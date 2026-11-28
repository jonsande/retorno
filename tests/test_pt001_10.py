"""PT001-10: public departure explanations without changing admission."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import pickle
import random
from types import SimpleNamespace

import pytest

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.actions import Travel
from retorno.core.engine import Engine
from retorno.model.events import EventType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link
from retorno.ui_textual.app import RetornoTextualApp


def _known_route(distance: float = 4.0):
    state = create_initial_state_sandbox(seed=29)
    state.ship.docked_node_id = None
    origin_id = state.world.current_node_id
    origin = state.world.space.nodes[origin_id]
    step = distance if origin.x_ly % 10 < 5 else -distance
    target = "PT001_10_TARGET"
    state.world.space.nodes[target] = SpaceNode(
        target, target, "station", x_ly=origin.x_ly + step,
        y_ly=origin.y_ly, z_ly=origin.z_ly,
    )
    state.world.known_nodes.add(target)
    assert add_known_link(state.world, origin_id, target)
    return state, target


def _routes(state) -> str:
    with redirect_stdout(io.StringIO()) as out:
        repl.render_nav_routes(state)
    return out.getvalue()


@pytest.mark.parametrize("cause,en,es", [
    ("engines_off", "engines are off", "motores están apagados"),
    ("engines_damaged", "engines are damaged", "motores están averiados"),
    ("engines_unavailable", "engines are unavailable", "motores no están disponibles"),
    ("engines_missing", "engines are unavailable", "motores no están disponibles"),
    ("target", "target speed exceeds", "velocidad objetivo supera"),
    ("docked", "ship is docked", "nave está acoplada"),
    ("in_transit", "already in transit", "ya está en tránsito"),
    ("current", "already at the destination", "ya estás en el destino"),
    ("no_route", "no known route", "no hay una ruta conocida"),
    ("out_of_range", "exceeds navigation range", "excede el alcance"),
    ("antimatter", "Insufficient fuel", "Combustible insuficiente"),
    ("critical_power", "electrical supply is unstable", "suministro eléctrico es inestable"),
    ("distribution", "energy distribution is offline", "distribución eléctrica está apagada"),
    ("power_path", "propulsion has no electrical supply", "propulsión no recibe electricidad"),
    ("core_os", "core OS is damaged", "sistema operativo central está dañado"),
    ("core_os_critical", "core OS is critical", "sistema operativo central está en estado crítico"),
    ("terminal", "terminal control is unavailable", "control del terminal no está disponible"),
    ("life_support", "life support is offline", "soporte vital está apagado"),
])
def test_departure_diagnostics_cli_textual_and_routes(cause, en, es):
    state, target = _known_route()
    origin = state.world.current_node_id
    if cause == "engines_off":
        state.ship.systems["engines"].forced_offline = True
    elif cause == "engines_damaged":
        state.ship.systems["engines"].health = .2
    elif cause == "engines_unavailable":
        state.ship.cruise_speed_ly_per_year = 0.0
    elif cause == "engines_missing":
        del state.ship.systems["engines"]
    elif cause == "target":
        state.ship.target_cruise_speed = .8
    elif cause == "docked":
        state.ship.docked_node_id = origin
    elif cause == "in_transit":
        state.ship.in_transit = True
    elif cause == "current":
        target = origin
    elif cause == "no_route":
        state.world.known_links[origin].discard(target)
    elif cause == "out_of_range":
        state.world.space.nodes[target].x_ly += Balance.MAX_ROUTE_HOP_LY + 10
    elif cause == "antimatter":
        state.ship.antimatter_capsules = 0.0
    elif cause == "critical_power":
        state.ship.power.power_quality = .1
    elif cause == "distribution":
        state.ship.systems["energy_distribution"].state = SystemState.OFFLINE
    elif cause == "power_path":
        state.ship.systems["power_core"].forced_offline = True
    elif cause == "core_os":
        state.ship.systems["core_os"].state = SystemState.DAMAGED
    elif cause == "core_os_critical":
        state.ship.systems["core_os"].state = SystemState.CRITICAL
    elif cause == "terminal":
        state.os.terminal_lock = True
    elif cause == "life_support":
        state.os.terminal_lock = True
        state.os.terminal_reason = "life_support_offline"

    for locale, expected in ((Locale.EN, en), (Locale.ES, es)):
        state.os.locale = locale
        before, rng = pickle.dumps(state), random.getstate()
        action = Travel(target)
        lines, prompt = repl.nav_confirmation(state, action)
        assert prompt is None
        assert expected in lines[-1]
        assert "estimate unavailable" not in "\n".join(lines)
        assert "estimación no disponible" not in "\n".join(lines)
        log = []
        harness = SimpleNamespace(loop=SimpleNamespace(state=state), _log_line=log.append)
        assert RetornoTextualApp._confirm_nav_needed(harness, state, action)
        assert harness._pending_confirm_action is None
        assert log == lines
        if cause not in {"current", "no_route", "out_of_range"}:
            route_text = _routes(state)
            row = next(line for line in route_text.splitlines() if line.startswith(("  Fuel:", "  Combustible:")))
            assert expected in row
            assert "estimate unavailable" not in row
        assert pickle.dumps(state) == before
        assert random.getstate() == rng


@pytest.mark.parametrize("hidden_distance", [2.0, 1000.0])
@pytest.mark.parametrize("locale,unknown", [
    (Locale.EN, "destination unknown"), (Locale.ES, "destino desconocido"),
])
def test_unknown_destination_does_not_reveal_hidden_existence(locale, unknown, hidden_distance):
    state, _ = _known_route()
    state.os.locale = locale
    absent = repl.nav_confirmation(state, Travel("SECRET"))
    assert absent[1] is None
    assert unknown in absent[0][-1]
    hidden = deepcopy(state)
    origin = hidden.world.space.nodes[hidden.world.current_node_id]
    hidden.world.space.nodes["SECRET"] = SpaceNode(
        "SECRET", "Hidden star", "station",
        x_ly=origin.x_ly + hidden_distance, y_ly=origin.y_ly, z_ly=origin.z_ly)
    hidden.world.space.nodes["SECRET"].links.add("HIDDEN_LINK")
    assert hidden.world.known_nodes == state.world.known_nodes
    assert hidden.world.known_contacts == state.world.known_contacts
    assert hidden.world.known_links == state.world.known_links
    before, rng = pickle.dumps(hidden), random.getstate()
    assert repl.nav_confirmation(hidden, Travel("SECRET")) == absent
    assert _routes(hidden) == _routes(state)
    assert pickle.dumps(hidden) == before
    assert random.getstate() == rng


def test_acquired_route_with_missing_endpoint_reports_incomplete_data():
    state, target = _known_route()
    del state.world.space.nodes[target]
    before = pickle.dumps(state)
    lines, prompt = repl.nav_confirmation(state, Travel(target))
    assert prompt is None
    assert "known route data is incomplete" in lines[-1]
    assert "exceeds navigation range" not in lines[-1]
    assert pickle.dumps(state) == before


def test_nominal_and_local_departure_keep_quotes_and_motor_authority():
    state, target = _known_route()
    cost = Engine().estimate_travel_fuel(state, target)
    before, rng = pickle.dumps(state), random.getstate()
    lines, prompt = repl.nav_confirmation(state, Travel(target))
    assert prompt is not None
    assert f"~{cost:.3f}" in "\n".join(lines)
    assert "Departure blocked" not in "\n".join(lines)
    assert pickle.dumps(state) == before
    assert random.getstate() == rng
    departure = Engine().apply_action(state, Travel(target))
    assert any(event.type == EventType.TRAVEL_STARTED for event in departure)

    local, local_target = _known_route(.001)
    local.ship.target_cruise_speed = .8  # Interstellar limit does not block a local hop.
    local.ship.antimatter_capsules = 0.0
    before, rng = pickle.dumps(local), random.getstate()
    lines, prompt = repl.nav_confirmation(local, Travel(local_target))
    assert prompt is not None
    assert "Local maneuver" in "\n".join(lines)
    assert "Antimatter: 0 capsules" in lines
    assert pickle.dumps(local) == before
    assert random.getstate() == rng
    departure = Engine().apply_action(local, Travel(local_target))
    assert any(event.type == EventType.TRAVEL_STARTED for event in departure)
    assert local.ship.antimatter_capsules == 0.0

    # Current local admission does not use the interstellar propulsion power path.
    local_power, local_target = _known_route(.001)
    local_power.ship.systems["power_core"].forced_offline = True
    assert repl.nav_confirmation(local_power, Travel(local_target))[1] is not None
    assert any(event.type == EventType.TRAVEL_STARTED
               for event in Engine().apply_action(local_power, Travel(local_target)))
