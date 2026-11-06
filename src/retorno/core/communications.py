"""Passive radio: physical coverage, propagation, capture and consumption.

No world generation, scheduler rolls or intel import occurs here. Callers must
prepare only after their real trigger; retries retain that source and context.
"""
from __future__ import annotations

from copy import deepcopy
import math

from retorno.config.balance import Balance
from retorno.model.events import SourceRef
from retorno.model.systems import SystemState
from retorno.model.world import RadioOpportunity, RadioEmitter, RadioEmission, is_hop_within_cap

RADIO_CHANNELS = {"captured_signal", "station_broadcast"}
RECEIVING_STATES = {SystemState.LIMITED, SystemState.NOMINAL, SystemState.UPGRADED}


def radio_coordinate_time(state) -> float:
    """Provisional galactic coordinate seconds; replace this adapter with clocks.

    Negative emission offsets precede the game's t=0, not an absolute history.
    Travel, hibernation, ship ageing and the engine's year are left unchanged.
    """
    now = float(state.clock.t)
    if not math.isfinite(now):
        raise ValueError("Invalid radio coordinate time")
    return now


def receiver_sensitivity(state, *, reference_when_unavailable=False) -> float:
    comms = state.ship.systems.get("comms")
    if comms and comms.state in RECEIVING_STATES and comms.health >= Balance.SYSTEM_HEALTH_DAMAGED and not comms.forced_offline:
        return Balance.RADIO_SENSITIVITY[comms.state.value]
    return Balance.RADIO_SENSITIVITY["nominal"] if reference_when_unavailable else 0.0


def radio_link_budget(power: float, sensitivity: float, distance_ly: float) -> dict:
    """Equivalent isotropic P/d² with normalized inverse detection threshold S.

    Range = sqrt(P*S) ly; the finite near-field clamp prevents division by zero.
    No random reception, real-world power units or navigation cap is involved.
    """
    if (isinstance(power, bool) or not isinstance(power, (int, float)) or not math.isfinite(power)
            or not Balance.RADIO_MIN_POWER <= power <= Balance.RADIO_MAX_POWER):
        raise ValueError("Invalid normalized radio power")
    if (isinstance(sensitivity, bool) or not isinstance(sensitivity, (int, float))
            or not math.isfinite(sensitivity) or not 0 <= sensitivity <= max(Balance.RADIO_SENSITIVITY.values())):
        raise ValueError("Invalid normalized receiver sensitivity")
    if (isinstance(distance_ly, bool) or not isinstance(distance_ly, (int, float))
            or not math.isfinite(distance_ly) or distance_ly < 0):
        raise ValueError("Invalid radio distance")
    radius = math.sqrt(power * sensitivity)
    safe_distance = max(distance_ly, Balance.RADIO_DISTANCE_FLOOR_LY)
    strength = power / safe_distance / safe_distance
    return dict(power=power, sensitivity=sensitivity, distance_ly=distance_ly,
        range_ly=radius, received_strength=strength, decodable=sensitivity > 0 and distance_ly <= radius)


def _source_site(state, emitter):
    from retorno.worldgen.generator import universe_definition
    from retorno.worldgen.radio import certified_host
    site = certified_host(universe_definition(state), emitter.host_id)
    node = state.world.space.nodes.get(emitter.host_id)
    if node and (node.kind != site.kind or (node.x_ly, node.y_ly, node.z_ly) != site.position_ly):
        raise ValueError("Radio host contradicts certified coordinates")
    return site


def radio_link_metrics(state, emitter, emission=None, *, receiver_node_id=None, sensitivity=None):
    site = _source_site(state, emitter)
    if receiver_node_id is None:
        position = state.world.current_pos_ly
    else:
        receiver = state.world.space.nodes.get(receiver_node_id)
        if receiver is None:
            raise ValueError("Missing recorded receiver")
        position = (receiver.x_ly, receiver.y_ly, receiver.z_ly)
    if len(position) != 3 or not all(math.isfinite(v) for v in position):
        raise ValueError("Invalid receiver coordinates")
    sensitivity = receiver_sensitivity(state, reference_when_unavailable=True) if sensitivity is None else sensitivity
    metrics = radio_link_budget(emitter.power, sensitivity, math.dist(site.position_ly, position))
    delay = metrics["distance_ly"] * Balance.YEAR_S
    metrics.update(host=emitter.host_id, emitter_id=emitter.emitter_id, category=emitter.category,
        propagation_s=delay, coordinate_t=radio_coordinate_time(state))
    if emission:
        start = emission.start_t + delay
        end = None if emission.end_t is None else emission.end_t + delay
        metrics.update(emission_id=emission.emission_id, mode=emission.mode, emission_start_t=emission.start_t,
            emission_end_t=emission.end_t, arrival_start_t=start, arrival_end_t=end,
            temporally_available=start <= radio_coordinate_time(state) and (end is None or radio_coordinate_time(state) < end))
    return metrics


def radio_temporal_block_reason(state, emitter, emission, *, receiver_node_id=None, at_t=None):
    if emitter is None and emission is None:
        return None  # Legacy interaction-local delivery, negligible delay.
    if emitter is None or emission is None or emission.emitter_id != emitter.emitter_id:
        return "emission_unavailable"
    try:
        metrics = radio_link_metrics(state, emitter, emission, receiver_node_id=receiver_node_id)
    except (ValueError, TypeError, OverflowError):
        return "source_unavailable"
    now = metrics["coordinate_t"] if at_t is None else at_t
    if now < metrics["arrival_start_t"]:
        return "signal_not_arrived"
    if metrics["arrival_end_t"] is not None and now >= metrics["arrival_end_t"]:
        return "signal_passed"
    return None


def radio_spatial_block_reason(state, origin_node_id: str, *, channel: str,
                               require_docked: bool = False,
                               receiver_node_id: str | None = None,
                               emitter: RadioEmitter | None = None,
                               sensitivity: float | None = None) -> str | None:
    """Physical reception eligibility, independent of receiver operation.

    Declared sources use certified 3D coordinates; undeclared legacy sources
    retain their interaction-local scope. This query never generates a sector.
    Receiver operation is checked separately. Explicit node is for save audit.
    """
    node = state.world.space.nodes.get(origin_node_id)
    receiver_id = state.world.current_node_id if receiver_node_id is None else receiver_node_id
    if require_docked and state.ship.docked_node_id != origin_node_id:
        return "source_requires_dock"
    if emitter is None:
        if node is None or node.kind == "transit" or receiver_id != node.node_id:
            return "source_unavailable"
        kind = node.kind
    else:
        if emitter.host_id != origin_node_id:
            return "source_unavailable"
        try:
            kind = _source_site(state, emitter).kind
            metrics = radio_link_metrics(state, emitter, receiver_node_id=receiver_node_id, sensitivity=sensitivity)
        except (ValueError, TypeError, OverflowError):
            return "source_unavailable"
        if not metrics["decodable"]:
            return "outside_radio_range"
    if channel == "station_broadcast" and kind not in {"relay", "station", "waystation"}:
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
            emitter=opportunity.emitter, sensitivity=receiver_sensitivity(state),
        )
        if spatial_reason:
            return spatial_reason
        temporal_reason = radio_temporal_block_reason(state, opportunity.emitter, opportunity.emission)
        if temporal_reason:
            return temporal_reason
        if opportunity.emission and opportunity.emission.navigation_link_to:
            from retorno.core.lore import _locked_primary_targets
            locked = _locked_primary_targets(state)
            if opportunity.origin_node_id in locked or opportunity.emission.navigation_link_to in locked:
                return "source_unavailable"
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
    emission_id: str | None = None,
) -> RadioOpportunity:
    if channel not in RADIO_CHANNELS and channel != "ship_os_mail":
        raise ValueError(f"Not a radio channel: {channel}")
    existing = state.world.radio_opportunities.get(opportunity_id)
    if existing is not None:
        if emission_id is not None and (existing.emission is None or existing.emission.emission_id != emission_id):
            raise ValueError("Radio ledger identity collision")
        return existing
    emitter = emission = None
    if emission_id is not None:
        snapshot = state.world.narrative_snapshot
        emission = snapshot.get("radio_emissions", {}).get(emission_id)
        if emission is None:
            raise ValueError("Unknown declared radio emission")
        emitter = snapshot["radio_emitters"][emission.emitter_id]
        canonical_id = f"lore:{emission.piece_key}" if emission.piece_key else f"radio:{emission_id}"
        if opportunity_id != canonical_id:
            raise ValueError("Radio emission must use its canonical ledger identity")
        _source_site(state, emitter)
        if node_id != emitter.host_id or channel != emission.channel:
            raise ValueError("Radio emission host/channel mismatch")
        if emission.piece_key:
            if (delivery or {}).get("piece_key") != emission.piece_key:
                raise ValueError("Radio emission requires the authorized narrative trigger")
        elif content_by_locale != emission.content_by_locale:
            raise ValueError("Radio payload differs from pre-existing emission")
    source = source or SourceRef(kind="world", id=node_id)
    opportunity = RadioOpportunity(
        opportunity_id, channel, source.kind, source.id, node_id, trigger,
        require_docked, dict(content_by_locale), float(state.clock.t), deepcopy(delivery or {}),
        emitter=emitter, emission=deepcopy(emission),
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
    discover_radio_opportunities(state)
    for opportunity in tuple(state.world.radio_opportunities.values()):
        event = capture_radio_opportunity(state, opportunity)
        if event is not None:
            events.append(event)
    return events


def discover_radio_opportunities(state):
    """Continuously listen to declared standalone emissions, without scan.

    Piece references are never prepared here: the existing scheduler and real
    interaction must authorize those first. Candidate budgets resume fairly.
    """
    snapshot = state.world.narrative_snapshot
    if not snapshot.get("radio_emitters") or radio_block_reason(state):
        return
    from retorno.worldgen.radio import query_emitters
    from retorno.core.lore import _locked_primary_targets
    candidates, cursor, _complete = query_emitters(state, cursor=state.world.radio_search_cursor)
    state.world.radio_search_cursor = cursor
    locked = _locked_primary_targets(state)
    for ident in candidates:
        emitter = snapshot["radio_emitters"][ident]
        for eid in snapshot["radio_emissions_by_emitter"].get(ident, ()):
            emission = snapshot["radio_emissions"][eid]
            if emission.piece_key or emission.navigation_link_to in locked or emitter.host_id in locked:
                continue
            if radio_spatial_block_reason(state, emitter.host_id, channel=emission.channel, emitter=emitter,
                    sensitivity=receiver_sensitivity(state)) or radio_temporal_block_reason(state, emitter, emission):
                continue
            prepare_radio_opportunity(state, f"radio:{eid}", emission.channel, emission.content_by_locale,
                node_id=emitter.host_id, trigger="passive_listen", emission_id=eid,
                delivery={"kind": "declared_radio"})


def validate_radio_state(state):
    """Fail closed on incompatible declarations or ledger, without rewriting saves."""
    from dataclasses import asdict
    from retorno.worldgen.radio import validate_radio_catalog
    validate_radio_catalog(state)
    snapshot = state.world.narrative_snapshot
    for key, op in state.world.radio_opportunities.items():
        if (not isinstance(op, RadioOpportunity) or key != op.opportunity_id
                or op.status not in {"pending", "received", "read_imported"}
                or op.channel not in RADIO_CHANNELS | {"ship_os_mail"}
                or not math.isfinite(op.prepared_t)):
            raise ValueError("Invalid radio ledger / Ledger de radio no válido")
        if op.status != "pending" and (not op.path or op.received_t is None or not math.isfinite(op.received_t)):
            raise ValueError("Invalid radio receipt / Captura de radio no válida")
        if op.status == "read_imported" and (op.read_t is None or not math.isfinite(op.read_t)):
            raise ValueError("Invalid radio read time / Fecha de lectura no válida")
        if op.emitter is None and op.emission is None:
            continue
        if not isinstance(op.emitter, RadioEmitter) or not isinstance(op.emission, RadioEmission):
            raise ValueError("Incomplete radio provenance / Procedencia de radio incompleta")
        RadioEmitter(**asdict(op.emitter))
        RadioEmission(**asdict(op.emission))
        if (snapshot.get("radio_emitters", {}).get(op.emitter.emitter_id) != op.emitter
                or snapshot.get("radio_emissions", {}).get(op.emission.emission_id) != op.emission
                or op.origin_node_id != op.emitter.host_id or op.emission.emitter_id != op.emitter.emitter_id
                or op.channel != op.emission.channel):
            raise ValueError("Radio declaration mismatch / Declaración de radio incompatible")
        canonical_id = f"lore:{op.emission.piece_key}" if op.emission.piece_key else f"radio:{op.emission.emission_id}"
        if key != canonical_id or (not op.emission.piece_key and op.content_by_locale != op.emission.content_by_locale):
            raise ValueError("Radio payload/identity mismatch / Contenido o identidad de radio incompatible")
        _source_site(state, op.emitter)


def mark_radio_read(state, path: str) -> None:
    for opportunity in state.world.radio_opportunities.values():
        if opportunity.status == "received" and opportunity.path == path:
            opportunity.status = "read_imported"
            opportunity.read_t = float(state.clock.t)
    from retorno.core.structural_recovery import mark_stage_read
    mark_stage_read(state, path)


def radio_diagnostic_lines(state) -> list[str]:
    locale = state.os.locale.value
    # Public telemetry depends only on the observable receiver, even in debug.
    reason = radio_block_reason(state)
    labels = {
        "en": {
            "ready": "ready", "comms_missing": "comms not installed", "comms_offline": "comms powered off; use power on comms",
            "comms_damaged": "comms below LIMITED; repair comms", "comms_power_dependency": "comms power dependencies unavailable",
            "terminal_locked": "terminal locked", "core_unavailable": "Core OS unavailable", "power_unavailable": "power unavailable",
            "receiver_context": "reception suspended during transit/hibernation", "radiod_missing": "radiod not installed",
            "radiod_stopped": "radiod stopped; use boot radiod",
        },
        "es": {
            "ready": "disponible", "comms_missing": "comms no instalado", "comms_offline": "comms apagado; usa power on comms",
            "comms_damaged": "comms inferior a LIMITED; repara comms", "comms_power_dependency": "alimentación de comms no disponible",
            "terminal_locked": "terminal bloqueado", "core_unavailable": "Core OS no disponible", "power_unavailable": "potencia no disponible",
            "receiver_context": "recepción suspendida durante tránsito/hibernación", "radiod_missing": "radiod no instalado",
            "radiod_stopped": "radiod detenido; usa boot radiod",
        },
    }
    title = "Recepción de radio" if locale == "es" else "Radio reception"
    return [f"{title}: {labels.get(locale, labels['en'])[reason or 'ready']}"]
