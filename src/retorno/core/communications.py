"""Passive radio: frozen local opportunities, capture and subsequent consumption.

No world generation, scheduler rolls or intel import occurs here. Callers must
prepare only after their real trigger; retries retain that source and context.
"""
from __future__ import annotations

from copy import deepcopy

from retorno.config.balance import Balance
from retorno.model.events import SourceRef
from retorno.model.systems import SystemState
from retorno.model.world import RadioOpportunity, is_hop_within_cap

RADIO_CHANNELS = {"captured_signal", "station_broadcast"}
RECEIVING_STATES = {SystemState.LIMITED, SystemState.NOMINAL, SystemState.UPGRADED}


def radio_spatial_block_reason(state, origin_node_id: str, *, channel: str,
                               require_docked: bool = False,
                               receiver_node_id: str | None = None) -> str | None:
    """Physical reception eligibility, independent of receiver operation.

    Today's coverage is local to the current physical node. Selection and
    capture share this boundary so a future physical range model replaces it
    here without embedding coverage assumptions in structural recovery. An
    explicit receiver node validates the recorded preparation context on load.
    """
    node = state.world.space.nodes.get(origin_node_id)
    receiver_id = state.world.current_node_id if receiver_node_id is None else receiver_node_id
    if node is None or node.kind == "transit" or receiver_id != node.node_id:
        return "source_unavailable"
    if require_docked and state.ship.docked_node_id != node.node_id:
        return "source_requires_dock"
    if channel == "station_broadcast" and node.kind not in {"relay", "station", "waystation"}:
        return "source_unavailable"
    return None


def radio_block_reason(state, opportunity: RadioOpportunity | None = None) -> str | None:
    systems = state.ship.systems
    comms = systems.get("comms")
    if comms is None:
        return "comms_missing"
    if comms.health < Balance.SYSTEM_HEALTH_DAMAGED:
        return "comms_damaged"
    if comms.forced_offline or comms.state == SystemState.OFFLINE:
        return "comms_offline"
    if comms.state not in RECEIVING_STATES:
        return "comms_damaged"
    for dep in comms.dependencies:
        if dep.dep_type == "system_state_at_least":
            target = systems.get(dep.target_id)
            order = list(SystemState)
            if (target is None or target.forced_offline
                    or order.index(target.state) < order.index(SystemState(dep.value))):
                return "comms_power_dependency"
    if state.os.terminal_lock:
        return "terminal_locked"
    core = systems.get("core_os")
    if core is None or core.forced_offline or core.state not in RECEIVING_STATES:
        return "core_unavailable"
    if state.ship.power.brownout or state.ship.power.power_quality < Balance.POWER_QUALITY_BLOCK_THRESHOLD:
        return "power_unavailable"
    # Reuse the engine's read-only electrical kernels, including cruise and job
    # loads. Cached Q/brownout may precede a manual power transition this tick.
    from retorno.core.engine import Engine
    engine = Engine()
    power = state.ship.power
    supply = engine._compute_p_gen(state) + (power.p_discharge_max_kw if power.e_batt_kwh > 0 else 0.0)
    if supply < engine._compute_load_kw(state):
        return "power_unavailable"
    if state.ship.in_transit or state.ship.is_hibernating:
        return "receiver_context"
    svc = comms.service
    if not svc or svc.service_name != "radiod" or not svc.is_installed:
        return "radiod_missing"
    if not svc.is_running:
        return "radiod_stopped"
    if opportunity is not None:
        spatial_reason = radio_spatial_block_reason(
            state, opportunity.origin_node_id, channel=opportunity.channel,
            require_docked=opportunity.require_docked,
        )
        if spatial_reason:
            return spatial_reason
        node = state.world.space.nodes.get(opportunity.origin_node_id)
        delivery = opportunity.delivery
        if delivery.get("kind") == "structural_recovery":
            from retorno.core.structural_recovery import delivery_valid
            if not delivery_valid(state, opportunity):
                return "source_unavailable"
        if delivery.get("kind") == "recovery_gateway":
            from retorno.core.lore import _locked_primary_targets
            rec = state.world.exploration_recovery
            if (rec.generation != delivery["generation"] or rec.entry_node_id != node.node_id
                    or rec.gateway_node_id != delivery["gateway"] or rec.dock_hint_delivered
                    or delivery["gateway"] in _locked_primary_targets(state)
                    or not is_hop_within_cap(state.world, node.node_id, delivery["gateway"])):
                return "source_unavailable"
        if delivery.get("kind") == "deadnode":
            from retorno.core.lore import _locked_primary_targets
            tracker = state.world.dead_nodes.get(delivery["target"])
            if (tracker is None or tracker.attempts != delivery["attempt"]
                    or delivery["target"] in _locked_primary_targets(state)
                    or delivery["hint_target"] in _locked_primary_targets(state)
                    or not is_hop_within_cap(state.world, node.node_id, delivery["hint_target"])):
                return "source_unavailable"
    return None


def prepare_radio_opportunity(
    state, opportunity_id: str, channel: str, content_by_locale: dict[str, str], *,
    node_id: str, trigger: str, source: SourceRef | None = None,
    require_docked: bool = False, delivery: dict | None = None,
) -> RadioOpportunity:
    if channel not in RADIO_CHANNELS and channel != "ship_os_mail":
        raise ValueError(f"Not a radio channel: {channel}")
    existing = state.world.radio_opportunities.get(opportunity_id)
    if existing is not None:
        return existing
    source = source or SourceRef(kind="world", id=node_id)
    opportunity = RadioOpportunity(
        opportunity_id, channel, source.kind, source.id, node_id, trigger,
        require_docked, dict(content_by_locale), float(state.clock.t), deepcopy(delivery or {}),
    )
    state.world.radio_opportunities[opportunity_id] = opportunity
    return opportunity


def capture_radio_opportunity(state, opportunity: RadioOpportunity):
    if opportunity.status != "pending" or radio_block_reason(state, opportunity):
        return None
    # The low-level writer is shared with existing non-radio delivery envelopes.
    from retorno.core.lore import _write_local_intel, commit_radio_delivery
    locale = state.os.locale.value
    content = opportunity.content_by_locale.get(locale)
    if content is None:
        content = opportunity.content_by_locale.get("en", next(iter(opportunity.content_by_locale.values()), ""))
    path, event = _write_local_intel(
        state, opportunity.channel, content,
        node_id=opportunity.origin_node_id,
        source=SourceRef(opportunity.source_kind, opportunity.source_id),
        mail_from=opportunity.delivery.get("mail_from"),
        mail_subject=opportunity.delivery.get("mail_subject"),
    )
    opportunity.status = "received"
    opportunity.path = path
    opportunity.received_locale = locale
    opportunity.received_t = float(state.clock.t)
    event.data["opportunity_id"] = opportunity.opportunity_id
    commit_radio_delivery(state, opportunity)
    return event


def retry_radio_opportunities(state) -> list:
    events = []
    for opportunity in tuple(state.world.radio_opportunities.values()):
        event = capture_radio_opportunity(state, opportunity)
        if event is not None:
            events.append(event)
    return events


def mark_radio_read(state, path: str) -> None:
    for opportunity in state.world.radio_opportunities.values():
        if opportunity.status == "received" and opportunity.path == path:
            opportunity.status = "read_imported"
            opportunity.read_t = float(state.clock.t)
    from retorno.core.structural_recovery import mark_stage_read
    mark_stage_read(state, path)


def radio_diagnostic_lines(state) -> list[str]:
    locale = state.os.locale.value
    pending = [o for o in state.world.radio_opportunities.values() if o.status == "pending"]
    reason = radio_block_reason(state)
    if reason is None and any(radio_block_reason(state, o) for o in pending):
        reason = "source_unavailable"
    labels = {
        "en": {
            "ready": "ready", "comms_missing": "comms not installed", "comms_offline": "comms powered off; use power on comms",
            "comms_damaged": "comms below LIMITED; repair comms", "comms_power_dependency": "comms power dependencies unavailable",
            "terminal_locked": "terminal locked", "core_unavailable": "Core OS unavailable", "power_unavailable": "power unavailable",
            "receiver_context": "reception suspended during transit/hibernation", "radiod_missing": "radiod not installed",
            "radiod_stopped": "radiod stopped; use boot radiod", "source_unavailable": "pending source outside legitimate local reception conditions",
        },
        "es": {
            "ready": "disponible", "comms_missing": "comms no instalado", "comms_offline": "comms apagado; usa power on comms",
            "comms_damaged": "comms inferior a LIMITED; repara comms", "comms_power_dependency": "alimentación de comms no disponible",
            "terminal_locked": "terminal bloqueado", "core_unavailable": "Core OS no disponible", "power_unavailable": "potencia no disponible",
            "receiver_context": "recepción suspendida durante tránsito/hibernación", "radiod_missing": "radiod no instalado",
            "radiod_stopped": "radiod detenido; usa boot radiod", "source_unavailable": "fuente pendiente fuera de condiciones legítimas de recepción local",
        },
    }
    title, count = ("Radio reception", "pending") if locale != "es" else ("Recepción de radio", "pendientes")
    lines = [f"{title}: {labels.get(locale, labels['en'])[reason or 'ready']}; {count}={len(pending)}"]
    statuses = {p.status for p in state.world.recovery_plans.values()}
    if not statuses:
        statuses = {s["status"] for s in state.world.recovery_searches.values()}
    translations = {
        "en": {"search_pending": "search pending", "validated": "prepared", "prepared": "prepared", "receipt_pending": "reception pending", "active": "active",
               "stage_consumed": "stage consumed", "complete": "complete", "incomplete": "search incomplete",
               "none_in_scope": "no complete opportunity in examined scope", "conditional": "delivery unverified", "invalid": "invalid candidate"},
        "es": {"search_pending": "búsqueda pendiente", "validated": "preparada", "prepared": "preparada", "receipt_pending": "recepción pendiente", "active": "activa",
               "stage_consumed": "etapa consumida", "complete": "completada", "incomplete": "búsqueda incompleta",
               "none_in_scope": "sin oportunidad completa en el ámbito examinado", "conditional": "entrega sin verificar", "invalid": "candidato no válido"},
    }
    if statuses:
        title = "Recuperación estructural" if locale == "es" else "Structural recovery"
        labels = translations.get(locale, translations["en"])
        lines.append(title+": "+", ".join(labels[s] for s in sorted(statuses)))
    return lines
