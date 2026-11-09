"""4D-3e4b integration: public actions, frozen lore, local reception and saves."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.communications import radio_block_reason, retry_radio_opportunities
from retorno.core.engine import Engine
from retorno.core import lore
from retorno.core.deadnodes import evaluate_dead_nodes
from retorno.core.exploration_recovery import ensure_exploration_recovery
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus
from retorno.model.os import Locale
from retorno.model.systems import SystemState, ServiceState
from retorno.model.world import SpaceNode, DeadNodeState, ExplorationRecoveryState
from retorno.ui_textual import presenter
from narrative_world_integration_smoke import installed, KEY

E = Engine()
RECEIPTS = {EventType.SIGNAL_CAPTURED, EventType.BROADCAST_RECEIVED, EventType.MAIL_RECEIVED}


def command(s, text):
    action = parse_command(text)
    return E.apply_action(s, action)


def at(s, node_id, docked=True):
    s.world.current_node_id = s.ship.current_node_id = node_id
    s.ship.docked_node_id = node_id if docked else None
    n = s.world.space.nodes[node_id]
    s.world.current_pos_ly = (n.x_ly, n.y_ly, n.z_ly)


def ready(s=None):
    s = s or create_initial_state_sandbox()
    # Isolate the pre-B2 interaction-delivery matrix from unrelated broadcasts.
    s.world.radio_history_version = "legacy-radio-v0"
    s.world.radio_definition = None
    s.ship.systems["comms"].health = .9  # Receiver fixtures start repaired; prologue is tested separately.
    for ident in ("energy_distribution", "power_core"):
        sys = s.ship.systems[ident]
        sys.health = 1
        sys.state = SystemState.NOMINAL
        sys.state_locked = sys.forced_offline = False
    s.ship.power.e_batt_kwh = s.ship.power.e_batt_max_kwh
    s.ship.power.power_quality = 1
    s.ship.power.brownout = False
    return s


def start_radio(s):
    command(s, "power on comms")
    assert not s.ship.systems["comms"].service.is_running
    events = command(s, "boot radiod")
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    events = E.tick(s, 5)
    assert s.ship.systems["comms"].service.is_running, events
    return events


def capture_output(func, *args):
    out = io.StringIO()
    with redirect_stdout(out):
        func(*args)
    return out.getvalue()


def test_01_prologue_power_and_boot():
    s = create_initial_state_prologue(seed=701)
    c = s.ship.systems["comms"]
    assert c.sector_id == "BRG-01" and c.sector_id in s.ship.sectors
    assert c.health == .72 and c.forced_offline and c.state == SystemState.OFFLINE
    assert c.p_effective_kw() == 0
    assert radio_block_reason(s) == "comms_offline"
    assert c.p_nom_kw == .15 < s.ship.systems["sensors"].p_nom_kw
    assert command(s, "boot radiod")[0].type == EventType.BOOT_BLOCKED
    assert command(s, "power on comms")[0].type == EventType.BOOT_BLOCKED
    for _ in range(3):
        E.tick(s, 1)
    assert c.state == SystemState.OFFLINE and not c.service.is_running
    dist = s.ship.systems["energy_distribution"]
    dist.state = SystemState.NOMINAL
    dist.forced_offline = False
    assert not any(e.type == EventType.BOOT_BLOCKED for e in command(s, "power on comms"))
    assert c.state == SystemState.LIMITED
    command(s, "power off comms")
    c.health = .5
    assert command(s, "power on comms")[0].data["reason"] == "system_too_damaged"
    ready(s)
    before = E._compute_load_kw(s)
    events = command(s, "power on comms")
    assert sum(e.data.get("message_key") == "service_activation_notice" for e in events) == 1
    assert abs(E._compute_load_kw(s) - before - .15) < 1e-9
    assert command(s, "power on comms") == []
    assert not c.service.is_running
    command(s, "boot radiod")
    E.tick(s, 4)
    assert not c.service.is_running
    E.tick(s, 1)
    assert c.service.is_running
    command(s, "power off comms")
    assert not c.service.is_running
    command(s, "power on comms")
    assert not c.service.is_running
    # Passive reception remains a real .15 kW load in the cruise profile too.
    s.ship.op_mode = "CRUISE"
    on = E._compute_load_kw(s)
    command(s, "power off comms")
    assert abs(on - E._compute_load_kw(s) - .15) < 1e-9
    # Actual battery accounting, at equal clock and ordinary generation/load.
    off = ready(); on_state = deepcopy(off)
    command(on_state, "power on comms")
    E.tick(off,1); E.tick(on_state,1)
    assert abs(off.ship.power.e_batt_kwh - on_state.ship.power.e_batt_kwh - .15/3600) < 1e-10


def test_02_boot_interruptions_and_missing_installation():
    for mode in ("off", "remove", "uninstall", "dependency", "brownout", "cancel", "health"):
        s = ready()
        command(s, "power on comms")
        command(s, "boot radiod")
        E.tick(s, 1)
        job = next(j for j in s.jobs.jobs.values() if j.target and j.target.id == "radiod")
        c = s.ship.systems["comms"]
        if mode == "off": command(s, "power off comms")
        if mode == "remove": s.ship.systems.pop("comms")
        if mode == "uninstall": c.service.is_installed = False
        if mode == "dependency": s.ship.systems["energy_distribution"].state = SystemState.DAMAGED
        if mode == "brownout": s.ship.power.brownout = True
        if mode == "cancel": command(s, f"job cancel {job.job_id}")
        if mode == "health": c.health = 0
        E.tick(s, 10)
        assert not c.service.is_running, mode
        assert job.status in {JobStatus.CANCELLED, JobStatus.FAILED}, (mode, job)
    s = ready()
    c = s.ship.systems["comms"]
    c.service.is_installed = False
    assert command(s, "boot radiod")[0].data["reason"] == "service_missing"
    events = command(s, "power on comms")
    assert any(e.data.get("service_status") == "not_installed" for e in events)
    c.service = None
    assert radio_block_reason(s) == "radiod_missing"


def test_03_receiver_states_and_independence():
    s = ready(); start_radio(s)
    command(s, "power off sensors"); command(s, "power off data_core")
    assert radio_block_reason(s) is None
    c = s.ship.systems["comms"]
    for state, health in ((SystemState.LIMITED,.7), (SystemState.NOMINAL,.9), (SystemState.UPGRADED,1)):
        c.state, c.health = state, health
        assert radio_block_reason(s) is None
    for state, health in ((SystemState.DAMAGED,.5), (SystemState.CRITICAL,.1), (SystemState.OFFLINE,0)):
        c.state, c.health = state, health
        assert radio_block_reason(s)
    c.health = .9; c.state = SystemState.NOMINAL
    before = c.health
    E.tick(s, 1)
    assert c.health < before
    command(s, "power off comms")
    command(s, "power on sensors"); command(s, "boot sensord"); E.tick(s, 8)
    assert s.ship.systems["sensors"].service.is_running
    assert radio_block_reason(s) == "comms_offline"


def test_04_lore_pending_capture_read_and_idempotence():
    def signal(alpha, beta): alpha["primary_intel"]["allowed_channels"] = ["captured_signal"]
    with installed(mutate=signal):
        s = ready(create_initial_state_prologue(seed=9))
        lore.run_lore_scheduler_tick(s)
        at(s, "TEST_HOST")
        before = (dict(s.os.fs), s.events.next_event_seq, deepcopy(s.world.lore.counters))
        result = lore.maybe_deliver_lore(s, "dock", lore.build_lore_context(s, "TEST_HOST"), count_trigger=False)
        assert not result.applied and not result.events
        assert (dict(s.os.fs), s.events.next_event_seq, s.world.lore.counters) == before
        assert KEY not in s.world.lore.delivered and KEY in s.world.node_pools["TEST_HOST"].pending_push_piece_ids
        assert "TEST_WRECK" not in s.world.known_nodes
        op = s.world.radio_opportunities[f"lore:{KEY}"]
        frozen = deepcopy(op.content_by_locale)
        assert op.status == "pending" and op.received_t is None
        events = start_radio(s)
        received = [e for e in events if e.type == EventType.SIGNAL_CAPTURED]
        assert len(received) == 1 and op.status == "received"
        assert KEY in s.world.lore.delivered and s.world.lore.counters["signal_count"] == 1
        assert "TEST_WRECK" not in s.world.known_nodes
        assert not s.world.arc_placements["synthetic_alpha"]["primary"].get("unlocked")
        snapshot = (deepcopy(s.world.lore), deepcopy(s.os.fs), s.events.next_event_seq)
        for _ in range(3):
            assert retry_radio_opportunities(s) == []
            lore.maybe_deliver_lore(s, "dock", lore.build_lore_context(s, "TEST_HOST"), count_trigger=False)
        assert snapshot == (s.world.lore, s.os.fs, s.events.next_event_seq)
        s.os.locale = Locale.ES
        capture_output(repl.render_cat, s, op.path)
        assert op.status == "read_imported" and op.read_t is not None
        assert "TEST_WRECK" in s.world.known_nodes and op.content_by_locale == frozen


def test_05_coverage_and_no_early_dock():
    def broadcast(alpha, beta): alpha["primary_intel"]["allowed_channels"] = ["station_broadcast"]
    with installed(mutate=broadcast):
        s = ready(create_initial_state_prologue(seed=2))
        lore.run_lore_scheduler_tick(s); at(s, "TEST_HOST", docked=False); start_radio(s)
        E.tick(s,1)
        assert not s.world.radio_opportunities and KEY not in s.world.lore.delivered
        # Even a producer invoked with an invalid dock context cannot capture.
        result = lore.maybe_deliver_lore(s, "dock", lore.build_lore_context(s, "TEST_HOST"), count_trigger=False)
        assert not result.applied
        at(s, "TEST_RELAY")
        assert retry_radio_opportunities(s) == []
        at(s, "TEST_HOST", docked=False)
        assert retry_radio_opportunities(s) == []
        at(s, "TEST_HOST")
        assert len(retry_radio_opportunities(s)) == 1
        assert retry_radio_opportunities(s) == []
    s = ready(); origin = s.world.current_node_id
    path, ev = lore.write_local_intel(s,"captured_signal","NODE: SECRET", opportunity_id="local-test")
    assert path is ev is None
    s.world.space.nodes["ELSEWHERE"] = SpaceNode("ELSEWHERE","Elsewhere","station",x_ly=12)
    at(s,"ELSEWHERE"); start_radio(s)
    assert s.world.radio_opportunities["local-test"].status == "pending"
    at(s,origin)
    assert len(retry_radio_opportunities(s)) == 1


def test_06_repair_then_capture():
    s = ready(); at(s,s.world.current_node_id)
    c = s.ship.systems["comms"]; c.health = .59
    command(s,"power on comms")
    assert command(s,"boot radiod")[0].type == EventType.BOOT_BLOCKED
    lore.write_local_intel(s,"captured_signal","Archived packet",opportunity_id="repair-test")
    drone = s.ship.drones["D1"]
    drone.status = DroneStatus.DEPLOYED; drone.location = DroneLocation("ship_sector","BRG-01")
    drone.battery = 1
    before = s.ship.cargo_scrap
    events = command(s,"drone repair D1 comms")
    assert any(e.type == EventType.JOB_QUEUED for e in events), events
    for _ in range(20):
        E.tick(s,5)
        if not s.jobs.active_job_ids: break
    assert c.health > .6 and s.ship.cargo_scrap < before
    assert s.world.radio_opportunities["repair-test"].status == "pending"
    start_radio(s)
    assert s.world.radio_opportunities["repair-test"].status == "received"


def test_07_non_radio_channels_and_explicit_external_mail():
    for locale in (Locale.EN, Locale.ES):
        s = ready(); s.os.locale = locale
        path, event = lore.write_local_intel(s,"ship_os_mail","Internal maintenance memo")
        assert path in s.os.fs and event.type == EventType.MAIL_RECEIVED
        path, event = lore.write_local_intel(s,"ship_os_mail","External packet", external_origin=True,opportunity_id="external")
        assert path is event is None and s.world.radio_opportunities["external"].status == "pending"
        at(s,s.world.current_node_id)
        s.ship.systems["data_core"].service.is_running = True
        path,event = lore.write_local_intel(s,"uplink_trace","LINK: A -> B")
        assert path in s.os.fs and event.type == EventType.UPLINK_TRACE_RECEIVED
        s.ship.systems["data_core"].service.is_running = False
        assert lore.write_local_intel(s,"uplink_trace","LINK: A -> C") == (None,None)
        start_radio(s)
        assert s.world.radio_opportunities["external"].status == "received"
    # Real salvage/push integration of e4 is also run in the regression suite.
    s = ready()
    entry = lore._file_for_salvage_piece({"piece_key":"optional","piece":{"line":"NODE: ECHO_7"}},"en",s)
    assert entry["content"] == "NODE: ECHO_7\n" and radio_block_reason(s) == "comms_offline"


def test_08_save_pending_received_read_and_old_schema_defaults():
    with TemporaryDirectory() as directory:
        path = Path(directory)/"slot.dat"
        s = ready(); at(s,s.world.current_node_id)
        lore.write_local_intel(s,"captured_signal","NODE: ECHO_7",opportunity_id="persist")
        frozen = deepcopy(s.world.radio_opportunities["persist"])
        save_single_slot(s,path); s=load_single_slot(path).state
        assert s.world.radio_opportunities["persist"] == frozen
        assert radio_block_reason(s) == "comms_offline"
        s.os.locale = Locale.ES; start_radio(s)
        op = s.world.radio_opportunities["persist"]
        assert op.status == "received" and len([p for p in s.os.fs if p.startswith('/logs/signals/') and p.endswith('.txt')]) == 1
        assert op.received_locale == "es" and s.os.fs[op.path].content == "NODE: ECHO_7"
        for _ in range(2):
            save_single_slot(s,path); s=load_single_slot(path).state
            assert retry_radio_opportunities(s) == []
        op = s.world.radio_opportunities["persist"]
        capture_output(repl._handle_intel_import,s,op.path)
        assert op.status == "read_imported"
        save_single_slot(s,path); s=load_single_slot(path).state
        assert s.world.radio_opportunities["persist"].status == "read_imported"
        # Encode the genuine pre-addition slot representation, not a new-game default.
        s.ship.systems.pop("comms")
        del s.world.radio_opportunities
        del s.world.recovery_activation_deferred
        del s.ship.systems["sensors"].service.requires_active_owner
        blob=pickle.dumps(s,pickle.HIGHEST_PROTOCOL)
        raw=b"RETORNO_SAVE_V2\n"+hashlib.sha256(blob).hexdigest().encode()+b"\n"+blob
        path.write_bytes(raw); Path(str(path)+".bak").write_bytes(raw)
        loaded=load_single_slot(path).state
        assert loaded.ship.systems["comms"].forced_offline and not loaded.ship.systems["comms"].service.is_running
        assert loaded.world.radio_opportunities == {} and loaded.ship.systems["sensors"].service.requires_active_owner is False
        assert path.read_bytes() == raw and Path(str(path)+".bak").read_bytes() == raw
    # Local legacy producers may freeze only the language available at preparation.
    for initial,received in ((Locale.EN,Locale.ES),(Locale.ES,Locale.EN)):
        s=ready(); s.os.locale=initial
        lore.write_local_intel(s,"captured_signal","FROZEN LOCAL TEXT",opportunity_id="locale-fallback")
        s.os.locale=received; start_radio(s)
        op=s.world.radio_opportunities["locale-fallback"]
        assert s.os.fs[op.path].content=="FROZEN LOCAL TEXT"


def test_09_recovery_legacy_deferral_and_existing_gateway():
    from exploration_recovery_smoke import _make_blocked_state
    s,anchor = _make_blocked_state(docked=False)
    before = deepcopy(s.world.space)
    for trigger in ("scan","dock","uplink","hibernate_end"):
        assert ensure_exploration_recovery(s,trigger) == []
    assert s.world.space == before and s.world.mobility_failsafe_count == 0
    assert s.world.recovery_searches["global"]["status"] == "conditional"
    # Previously prepared chains may still be consumed legitimately on arrival.
    s.world.space.nodes["ENTRY"] = SpaceNode("ENTRY","Entry","station",x_ly=1)
    s.world.space.nodes["GATEWAY"] = SpaceNode("GATEWAY","Gateway","station",x_ly=15)
    s.world.exploration_recovery = ExplorationRecoveryState(generation=4,entry_node_id="ENTRY",gateway_node_id="GATEWAY")
    at(s,"ENTRY",docked=False)
    assert ensure_exploration_recovery(s,"arrival") == []
    assert not s.world.exploration_recovery.dock_hint_delivered
    ready(s); events = start_radio(s)
    assert sum(e.type == EventType.BROADCAST_RECEIVED for e in events) == 1
    assert s.world.exploration_recovery.dock_hint_delivered
    assert "GATEWAY" not in s.world.known_nodes
    assert ensure_exploration_recovery(s,"arrival") == []


def test_10_deadnode_no_premature_commit_or_new_bridge():
    s=ready(); current=s.world.current_node_id
    s.world.space.nodes["TARGET"] = SpaceNode("TARGET","Target","station",x_ly=500)
    s.world.known_contacts.add("TARGET")
    s.world.dead_nodes["TARGET"] = DeadNodeState(dead_since_t=0)
    before=set(s.world.space.nodes)
    assert evaluate_dead_nodes(s,"scan") == []
    tracker=s.world.dead_nodes["TARGET"]
    assert tracker.attempts == 0 and tracker.bridge_node_id is None and set(s.world.space.nodes)==before
    s.world.space.nodes["BRIDGE"] = SpaceNode("BRIDGE","Bridge","relay",x_ly=s.world.current_pos_ly[0]+1,y_ly=s.world.current_pos_ly[1],z_ly=s.world.current_pos_ly[2])
    tracker.bridge_node_id="BRIDGE"
    assert evaluate_dead_nodes(s,"scan") == []
    assert tracker.attempts == 0 and tracker.last_action_t == 0
    assert len(s.world.radio_opportunities)==1
    start_radio(s)
    assert tracker.attempts==1 and tracker.last_action_t==s.clock.t
    assert evaluate_dead_nodes(s,"scan")==[]


def test_11_localization_diagnostics_and_dynamic_notices():
    for locale in (Locale.EN,Locale.ES):
        s=ready(); s.os.locale=locale
        lore.write_local_intel(s,"captured_signal","SECRET COORD: 999,999,999",opportunity_id="hidden")
        text=capture_output(repl.render_diag,s,"comms")
        assert "SECRET" not in text and "999" not in text and "pending=" not in text and "pendientes=" not in text
        assert text.strip().splitlines()==presenter.build_command_output(repl.render_diag,s,"comms")
        panel = presenter.build_status_lines(s)
        assert any(line.startswith("comms ") for line in panel)
        assert not any("Radio reception" in line or "Recepción de radio" in line for line in panel)
        status = capture_output(repl.render_status,s)
        assert "pending=" not in status and "pendientes=" not in status
        assert ("Sistema de comunicaciones" if locale==Locale.ES else "Communications System") in text
        # Ownership is read from the live model, including another installed daemon.
        owner=s.ship.systems["data_core"]
        owner.service=ServiceState("fixture_service")
        owner.dependencies[0].target_id="comms"
        events=command(s,"power on comms")
        assert {e.data.get("service") for e in events if e.data.get("message_key")=="service_activation_notice"}=={"radiod","fixture_service"}
        rendered=capture_output(repl.render_events,s,events)
        hint = "Try" if locale == Locale.EN else "Prueba"
        assert f"({hint}: boot radiod)" in rendered and f"({hint}: boot fixture_service)" in rendered
        assert ("Servicio de comunicaciones por radio" if locale==Locale.ES else "Radio Communications Service") in rendered
        assert command(s,"power on comms")==[]
        for owner_id in ("sensors", "data_core", "comms"):
            actual = ready()
            actual.os.locale = locale
            command(actual, f"power off {owner_id}")
            notices = command(actual, f"power on {owner_id}")
            service = actual.ship.systems[owner_id].service.service_name
            output = capture_output(repl.render_events, actual, notices)
            assert f"({hint}: boot {service})" in output, (owner_id, output)
            assert output.strip().splitlines() == presenter.format_event_lines(actual, notices)
        for verbose in (False,True):
            help_text=capture_output(repl.print_help,locale.value,verbose)
            assert "power on comms" in help_text and "diag comms" in help_text


def test_12_radio_does_not_consume_rng_or_change_physics():
    from retorno.worldgen.generator import ensure_sector_generated
    left=ready(); right=deepcopy(left)
    start_radio(right)
    E.tick(left,5)
    # Compare the kernel at identical clocks/ship sensor state; reception uses no RNG.
    left.clock.t=right.clock.t
    before=right.meta.rng_counter
    lore.write_local_intel(right,"captured_signal","Old message",opportunity_id="rng")
    assert right.meta.rng_counter==before
    assert left.world.space==right.world.space
    assert left.world.lore_placements==right.world.lore_placements
    assert left.ship.cargo_scrap==right.ship.cargo_scrap
    for ident in ("S+005_+002_+000","S+006_+002_+000"):
        ensure_sector_generated(left,ident); ensure_sector_generated(right,ident)
    assert left.world.space==right.world.space
    assert left.world.sector_states==right.world.sector_states
    # A radio capture cannot alter the random observation sequence.
    left.meta.rng_counter=right.meta.rng_counter
    assert E._perform_scan(left)==E._perform_scan(right)
    assert left.world.scan_observations[-1].detected_ids==right.world.scan_observations[-1].detected_ids


def test_13_public_prologue_sequence_without_resource_overrides():
    s=create_initial_state_prologue(seed=701)
    script=["power off data_core","drone deploy D1 PWR-A1",
            "drone repair D1 power_core","drone repair D1 power_core","drone repair D1 power_core",
            "drone move D1 BUS-A2","drone repair D1 energy_distribution","drone repair D1 energy_distribution",
            "drone move D1 BRG-01","drone repair D1 comms",
            "power on comms","boot radiod"]
    for text in script:
        events=command(s,text)
        assert events and not any(e.type==EventType.BOOT_BLOCKED for e in events), (text,events)
        for _ in range(200):
            if not s.jobs.active_job_ids: break
            events=E.tick(s,1)
            # Ordinary probabilistic repair failures remain part of this real run.
        assert not s.jobs.active_job_ids, text
    assert s.ship.systems["comms"].service.is_running and radio_block_reason(s) is None
    assert s.ship.cargo_scrap > 0 and s.ship.power.power_quality > Balance.POWER_QUALITY_BLOCK_THRESHOLD
    print("PUBLIC FLOW:"," -> ".join(script),f"; t={s.clock.t}s scrap={s.ship.cargo_scrap} radio=ready")


def test_14_frozen_lore_across_pending_save_and_locale_switch():
    def signal(alpha,beta): alpha["primary_intel"]["allowed_channels"]=["captured_signal"]
    with installed(mutate=signal), TemporaryDirectory() as directory:
        s=ready(create_initial_state_prologue(seed=8)); lore.run_lore_scheduler_tick(s); at(s,"TEST_HOST")
        lore.maybe_deliver_lore(s,"dock",lore.build_lore_context(s,"TEST_HOST"),count_trigger=False)
        original=deepcopy(s.world.radio_opportunities[f"lore:{KEY}"])
        slot=Path(directory)/"lore.dat"; save_single_slot(s,slot)
        s=load_single_slot(slot).state; s.os.locale=Locale.ES
        events=start_radio(s)
        op=s.world.radio_opportunities[f"lore:{KEY}"]
        assert op.content_by_locale==original.content_by_locale
        assert s.os.fs[op.path].content==original.content_by_locale["es"]
        assert len([e for e in events if e.type==EventType.SIGNAL_CAPTURED])==1
        save_single_slot(s,slot); s=load_single_slot(slot).state
        assert not lore.maybe_deliver_lore(s,"dock",lore.build_lore_context(s,"TEST_HOST"),count_trigger=False).applied
        assert s.world.lore.counters["signal_count"]==1


def test_15_live_gates_do_not_write_or_consume_pending():
    for gate in ("stopped","missing","power","no_supply","dependency","terminal","transit","hibernate","core"):
        s=ready(); start_radio(s)
        if gate=="stopped": s.ship.systems["comms"].service.is_running=False
        if gate=="missing": s.ship.systems["comms"].service.is_installed=False
        if gate=="power": s.ship.power.power_quality=.1
        if gate=="no_supply":
            s.ship.power.e_batt_kwh=0
            s.ship.systems["power_core"].state=SystemState.OFFLINE
        if gate=="dependency": s.ship.systems["energy_distribution"].forced_offline=True
        if gate=="terminal": s.os.terminal_lock=True
        if gate=="transit": s.ship.in_transit=True
        if gate=="hibernate": s.ship.is_hibernating=True
        if gate=="core": s.ship.systems["core_os"].state=SystemState.CRITICAL
        before=(deepcopy(s.os.fs),s.events.next_event_seq,deepcopy(s.world.lore))
        path,event=lore.write_local_intel(s,"captured_signal","NODE: SECRET",opportunity_id="blocked")
        assert path is event is None,gate
        assert before==(s.os.fs,s.events.next_event_seq,s.world.lore),gate
        assert retry_radio_opportunities(s)==[]
        assert s.world.radio_opportunities["blocked"].status=="pending"
    # Neither of the old direct radio writers can bypass the shared receiver.
    s=ready()
    assert lore.deliver_captured_signal(s,"lore/singles/sig_echo_fragment_01.en.txt","en")==""
    assert lore.deliver_station_broadcast(s,s.world.current_node_id,"unused","en")==""
    assert len(s.world.radio_opportunities)==2


def test_16_explicit_external_lore_mail_uses_radio():
    def external(alpha,beta):
        alpha["primary_intel"].update(allowed_channels=["ship_os_mail"],mail_origin="external",mail_from="Archive")
    with installed(mutate=external):
        s=ready(create_initial_state_prologue(seed=1)); lore.run_lore_scheduler_tick(s); at(s,"TEST_HOST")
        result=lore.maybe_deliver_lore(s,"dock",lore.build_lore_context(s,"TEST_HOST"),count_trigger=False)
        assert not result.applied and KEY not in s.world.lore.delivered
        s.os.locale=Locale.ES
        events=start_radio(s)
        assert sum(e.type==EventType.MAIL_RECEIVED for e in events)==1
        op=s.world.radio_opportunities[f"lore:{KEY}"]
        assert op.status=="received" and s.os.fs[op.path].content.startswith("FROM: Archive")
        assert "TEST_WRECK" not in s.world.known_nodes
        capture_output(repl.render_mail_read,s,"latest")
        assert op.status=="read_imported" and "TEST_WRECK" in s.world.known_nodes


def test_17_legacy_gateway_rechecks_protected_and_physical_target():
    from retorno.worldgen.generator import ensure_historical_node
    with installed():
        s=ready(create_initial_state_prologue(seed=4)); lore.run_lore_scheduler_tick(s)
        ensure_historical_node(s,"TEST_RELAY"); at(s,"TEST_HOST",docked=False)
        s.world.exploration_recovery=ExplorationRecoveryState(generation=1,entry_node_id="TEST_HOST",gateway_node_id="TEST_RELAY")
        assert ensure_exploration_recovery(s,"arrival")==[]
        start_radio(s)
        op=s.world.radio_opportunities["recovery:1:gateway"]
        assert op.status=="pending" and not s.world.exploration_recovery.dock_hint_delivered
        path,_event=lore.write_local_intel(s,"ship_os_mail","LINK: TEST_HOST -> TEST_RELAY")
        capture_output(repl.render_cat,s,path)
        assert "TEST_RELAY" not in lore._locked_primary_targets(s)
        target=s.world.space.nodes.pop("TEST_RELAY")
        assert retry_radio_opportunities(s)==[]
        s.world.space.nodes["TEST_RELAY"]=target
        assert len(retry_radio_opportunities(s))==1
        assert s.world.exploration_recovery.dock_hint_delivered


def test_18_save_load_during_service_boot():
    with TemporaryDirectory() as directory:
        s=ready(); command(s,"power on comms"); command(s,"boot radiod"); E.tick(s,1)
        slot=Path(directory)/"boot.dat"; save_single_slot(s,slot); s=load_single_slot(slot).state
        assert not s.ship.systems["comms"].service.is_running
        assert s.ship.systems["comms"].service.requires_active_owner
        E.tick(s,4)
        assert s.ship.systems["comms"].service.is_running
        assert all(j.status==JobStatus.COMPLETED for j in s.jobs.jobs.values())


def main():
    tests=[value for name,value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(test.__name__,"PASS",flush=True)
    print(f"PASSIVE COMMUNICATIONS: {len(tests)} groups PASS")


if __name__=="__main__": main()
