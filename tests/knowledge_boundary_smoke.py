"""4D-3e5a: compare identical observations while varying hidden engine state."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import os
import pickle
import random
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from retorno.cli import repl
from retorno.cli.parser import parse_command, ParseError, format_parse_error
from retorno.core import communications as radio, structural_recovery as rec
from retorno.io import save_load
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.ui_textual import presenter
from retorno.ui_textual.app import RetornoTextualApp
from structural_recovery_smoke import scene, proposal, ready, SMALL


def output(func, *args, **kwargs):
    with redirect_stdout(io.StringIO()) as buf:
        func(*args, **kwargs)
    return buf.getvalue().strip().splitlines()


def public(s):
    """Actual public renderers, including Textual panels and event-independent views."""
    return {
        "status": output(repl.render_status, s),
        "diag": output(repl.render_diag, s, "comms"),
        "contacts": output(repl.render_contacts, s),
        "map": output(repl.render_map_graph, s),
        "galaxy": output(repl.render_nav_map_galaxy, s, "local"),
        "sectors": output(repl.render_nav_map_sectors, s),
        "routes": output(repl.render_nav_routes, s),
        "intel": output(repl.render_intel_list, s),
        "alerts": presenter.build_alerts_lines(s),
        "panel": presenter.build_status_lines(s),
        "header": presenter.build_header(s),
    }


def hidden(s, origin="B"):
    return radio.prepare_radio_opportunity(s, "secret-op", "station_broadcast",
        {"en": "LINK: A -> B", "es": "LINK: A -> B"}, node_id=origin,
        trigger="test", delivery={"secret": "reserved-target"})


def test_01_empty_status_has_no_pending_count():
    for locale in Locale:
        s=scene();s.os.locale=locale
        text="\n".join(output(repl.render_status,s))
        assert "pending=" not in text and "pendientes=" not in text
        assert ("Radio reception:" if locale==Locale.EN else "Recepción de radio:") in text


def test_02_hidden_opportunity_is_publicly_indistinguishable():
    for locale in Locale:
        s=scene();s.os.locale=locale
        before=public(s);hidden(s)
        assert public(s)==before


def test_03_stopped_service_only_reports_receiver():
    for locale in Locale:
        s=scene();ready(s);s.os.locale=locale
        s.ship.systems["comms"].service.is_running=False
        before=public(s);hidden(s)
        assert public(s)==before
        assert "boot radiod" in "\n".join(before["diag"])


def test_04_remote_source_does_not_change_ready_receiver():
    for locale in Locale:
        s=scene();ready(s);s.os.locale=locale
        before=public(s);op=hidden(s)
        assert radio.radio_block_reason(s) is None
        assert radio.radio_block_reason(s,op)=="source_unavailable"
        assert public(s)==before


def test_05_hidden_search_transitions_are_invisible():
    for locale in Locale:
        s=scene();s.os.locale=locale;before=public(s)
        for status in ("search_pending","incomplete","conditional","none_in_scope","invalid","validated"):
            s.world.recovery_searches["secret-block"]={"status":status,"reason":"secret-reason","cursor":987}
            assert public(s)==before,status


def test_06_prepared_chain_is_invisible_before_capture():
    for locale in Locale:
        s=scene();s.os.locale=locale;before=public(s)
        p=rec.confirm_recovery(s,proposal(s))
        assert p.status=="receipt_pending" and not p.captured
        assert not s.world.known_links
        assert public(s)==before


def test_07_capture_preserves_event_and_readable_file():
    for locale in Locale:
        s=scene();s.os.locale=locale
        p=rec.confirm_recovery(s,proposal(s));ready(s)
        events=radio.retry_radio_opportunities(s)
        assert len(events)==1 and p.captured==(0,)
        op=next(iter(s.world.radio_opportunities.values()))
        assert op.path in s.os.fs and "LINK: A -> B" in s.os.fs[op.path].content
        assert not s.world.known_links
        lines=presenter.format_event_lines(s,events)
        assert lines==output(repl.render_events,s,events)
        assert any(op.path in line for line in lines)
        assert all(p.plan_id not in line and op.opportunity_id not in line for line in lines)
        assert radio.retry_radio_opportunities(s)==[]


def test_08_read_and_import_keep_normal_unlocks():
    for method in (repl.render_cat,repl._handle_intel_import):
        s=scene();rec.confirm_recovery(s,proposal(s));ready(s)
        radio.retry_radio_opportunities(s)
        op=next(iter(s.world.radio_opportunities.values()))
        output(method,s,op.path)
        assert s.world.known_links["A"]=={"B"}
        assert "B" in s.world.known_contacts and "B" in s.world.known_nodes
        assert op.status=="read_imported" and s.world.intel


def test_09_debug_guard_and_live_records_en_es():
    for locale in Locale:
        s=scene();s.os.locale=locale
        rec.confirm_recovery(s,proposal(s));rec.request_recovery(s,"other")
        op=next(iter(s.world.radio_opportunities.values()))
        for name in ("radio","recovery"):
            assert parse_command("debug "+name)==("DEBUG_"+name.upper(),None)
            renderer=getattr(repl,"render_debug_"+name)
            denied=output(renderer,s)
            assert "debug on" in "\n".join(denied)
            assert op.opportunity_id not in "\n".join(denied)
            s.os.debug_enabled=True
            allowed="\n".join(output(renderer,s))
            assert (op.opportunity_id if name=="radio" else "receipt_pending") in allowed
            assert ("source_unavailable" if name=="radio" and radio.radio_block_reason(s,op)=="source_unavailable" else "DEBUG") in allowed
            s.os.debug_enabled=False
            assert output(renderer,s)==denied


def test_10_debug_does_not_change_public_meaning():
    s=scene();rec.confirm_recovery(s,proposal(s));before=public(s)
    s.os.debug_enabled=True
    assert public(s)==before
    output(repl.render_debug_radio,s);output(repl.render_debug_recovery,s)
    assert public(s)==before


def test_11_textual_command_dispatch_and_off_gate():
    with patch.dict(os.environ,{"RETORNO_SCENARIO":"sandbox"}):
        app=RetornoTextualApp(force_new_game=True)
    app.loop.state=scene();s=app.loop.state
    rec.confirm_recovery(s,proposal(s))
    app._startup_panel_blackout=app._startup_sequence_running=False
    lines=[]
    with patch.object(app,"_log_line",side_effect=lambda text,*a,**k:lines.append(text)), \
         patch.object(app,"_log_lines",side_effect=lambda text,*a,**k:lines.extend(text)), \
         patch.object(app.loop,"start"),patch.object(app.loop,"set_auto_tick"):
        for locale in Locale:
            s.os.locale=locale
            for mode in (False,True,False):
                app.on_input_submitted(SimpleNamespace(value="debug on" if mode else "debug off",input=SimpleNamespace(value="")))
                assert s.os.debug_enabled==mode
                for name in ("radio","recovery"):
                    lines.clear()
                    app.on_input_submitted(SimpleNamespace(value="debug "+name,input=SimpleNamespace(value="")))
                    expected=output(getattr(repl,"render_debug_"+name),s)
                    assert lines[-len(expected):]==expected,(lines,expected)


def test_12_completion_only_uses_acquired_destinations():
    s=scene();before=[fn(s) for fn in (repl._known_contact_ids_for_completion,repl._route_solve_targets_for_completion,repl._travel_targets_for_completion)]
    rec.confirm_recovery(s,proposal(s))
    assert [fn(s) for fn in (repl._known_contact_ids_for_completion,repl._route_solve_targets_for_completion,repl._travel_targets_for_completion)]==before
    with patch.dict(os.environ,{"RETORNO_SCENARIO":"sandbox"}):
        app=RetornoTextualApp(force_new_game=True)
    for command in ("nav ","route solve ","dock ","ship survey ","map graph "):
        assert "B" not in app._get_completion_candidates(s,command,"")


def test_13_queries_are_read_only_for_entire_state_and_rng():
    s=scene();rec.confirm_recovery(s,proposal(s));rec.request_recovery(s,"other")
    s.os.debug_enabled=True
    before=pickle.dumps(s);rng=random.getstate()
    public(s);output(repl.render_debug_radio,s);output(repl.render_debug_recovery,s)
    repl._route_solve_targets_for_completion(s)
    assert pickle.dumps(s)==before and random.getstate()==rng


def test_14_survey_hidden_equals_absent_and_known_is_preserved():
    for locale in Locale:
        s=scene();s.os.locale=locale
        for sid in ("sensors","data_core"):
            sys=s.ship.systems[sid];sys.state=SystemState.NOMINAL
            sys.forced_offline=False;sys.service.is_running=True
        node=s.world.space.nodes.pop("B")
        absent=output(repl.render_ship_survey,s,"B")
        s.world.space.nodes["B"]=node
        assert output(repl.render_ship_survey,s,"B")==absent
        assert not any(node.name in line or "coords:" in line for line in absent)
        s.world.known_contacts.add("B")
        assert any("coords:" in line for line in output(repl.render_ship_survey,s,"B"))
        assert output(repl.render_ship_survey,s,"B")==presenter.build_command_output(repl.render_ship_survey,s,"B")


def test_15_save_load_preserves_hidden_and_received_states():
    for locale in Locale:
        s=scene();s.os.locale=locale
        rec.confirm_recovery(s,proposal(s))
        for phase in ("pending","received","read_imported"):
            if phase=="received":ready(s);radio.retry_radio_opportunities(s)
            if phase=="read_imported":output(repl.render_cat,s,next(iter(s.world.radio_opportunities.values())).path)
            before=public(s);plans=deepcopy(s.world.recovery_plans);ops=deepcopy(s.world.radio_opportunities)
            with TemporaryDirectory() as directory:
                path=str(__import__("pathlib").Path(directory)/"slot.dat")
                save_load.save_single_slot(s,path);loaded=save_load.load_single_slot(path).state
            assert loaded.world.recovery_plans==plans and loaded.world.radio_opportunities==ops
            assert public(loaded)==before
            assert next(iter(loaded.world.radio_opportunities.values())).status==phase


def test_16_real_repl_dispatch_debug_on_off_en_es():
    for locale in Locale:
        s=scene();s.os.locale=locale;rec.confirm_recovery(s,proposal(s))
        op=next(iter(s.world.radio_opportunities.values()))
        commands=iter(("debug radio","debug recovery","debug on","debug radio","debug recovery","status","diag comms","debug off","debug radio","debug recovery","exit"))
        def read_command(*args):
            command=next(commands)
            print("@@COMMAND "+command)
            return command
        with patch.dict(os.environ,{"RETORNO_SCENARIO":"sandbox"}), \
             patch.object(sys,"argv",["retorno","--new-game","--save-path","/tmp/unused-knowledge-test.dat"]), \
             patch.object(repl,"create_initial_state_sandbox",return_value=s), \
             patch.object(repl,"save_exists",return_value=False), \
             patch.object(repl,"save_single_slot",return_value="test-only"), \
             patch.object(repl,"run_console_entry_gate"),patch.object(repl,"_maybe_run_startup_sequence"), \
             patch.object(repl,"AudioManager",side_effect=repl.AudioConfigError("test-only")), \
             patch.object(repl.GameLoop,"start"),patch.object(repl.GameLoop,"stop"),patch.object(repl.GameLoop,"step"), \
             patch.object(repl.readline,"set_completer"),patch("builtins.input",side_effect=read_command):
            transcript="\n".join(output(repl.main))
        sections=transcript.split("@@COMMAND ")[1:]
        for index in (0,1,8,9):
            assert "debug on" in sections[index] and op.opportunity_id not in sections[index]
        assert op.opportunity_id in sections[3] and "receipt_pending" in sections[4]
        assert op.opportunity_id not in sections[5]+sections[6]
        assert "receipt_pending" not in sections[5]+sections[6]
        assert not s.os.debug_enabled


def test_17_hidden_catalog_and_scheduler_do_not_affect_public_views_or_errors():
    for locale in Locale:
        s=scene();s.os.locale=locale
        before=public(s)
        errors=[output(fn,s,"UNACQUIRED") for fn in (repl.render_map_graph,repl.render_map_path,repl.render_diag)]
        s.world.space.nodes["EXCLUSIVELY_INTERNAL"]=replace(s.world.space.nodes["B"],node_id="EXCLUSIVELY_INTERNAL",name="Reserved site")
        s.world.lore_placements.piece_to_node["secret-piece"]="EXCLUSIVELY_INTERNAL"
        s.world.lore_placements.piece_channel_bindings["secret-piece"]="captured_signal"
        s.world.lore_placements.eval_seq+=10
        hidden(s,"EXCLUSIVELY_INTERNAL")
        assert public(s)==before
        assert errors==[output(fn,s,"UNACQUIRED") for fn in (repl.render_map_graph,repl.render_map_path,repl.render_diag)]
        assert "EXCLUSIVELY_INTERNAL" not in repl._known_contact_ids_for_completion(s)
        try:parse_command("debug unrecognized")
        except ParseError as error:
            text=format_parse_error(error,locale.value)
            assert "debug radio" in text and "debug recovery" in text
            assert "EXCLUSIVELY_INTERNAL" not in text and "secret-piece" not in text


def test_18_dock_alias_resolution_does_not_disclose_hidden_ids():
    s=scene();node=s.world.space.nodes["B"];node.name="Unreceived Relay"
    assert repl._resolve_node_id_from_input(s,"Unreceived Relay") is None
    assert repl._resolve_node_id_from_input(s,"UnreceivedRelay") is None
    assert repl._resolve_node_id_from_input(s,"B") is None
    s.world.known_contacts.add("B")
    assert repl._resolve_node_id_from_input(s,"Unreceived Relay")=="B"
    assert repl._resolve_node_id_from_input(s,"UnreceivedRelay")=="B"
    assert repl._resolve_node_id_from_input(s,"B")=="B"


def test_19_unacquired_navigation_errors_and_logs_hide_physical_existence():
    from retorno.core.engine import Engine
    for locale in Locale:
        base=scene();base.os.locale=locale
        rendered=[];logs=[]
        for exists in (False,True):
            s=deepcopy(base)
            if not exists:s.world.space.nodes.pop("B")
            events=Engine().apply_action(s,parse_command("nav B"))
            assert events[0].data["reason"]==("unknown_contact" if exists else "node_missing")
            rendered.append(output(repl.render_events,s,events))
            logs.append(output(repl.render_logs,s))
            assert rendered[-1]==presenter.format_event_lines(s,events)
        assert rendered[0]==rendered[1] and logs[0]==logs[1]
        assert all("(B)" not in line and "->" not in line for line in rendered[0]+logs[0])
        # A missing location already recorded by the ship remains a legitimate
        # error detail, rather than being erased by a blanket redaction.
        s=deepcopy(base);s.world.known_contacts.add("B");s.world.known_nodes.add("B")
        s.world.space.nodes.pop("B")
        events=Engine().apply_action(s,parse_command("nav B"))
        assert any("(B)" in line for line in output(repl.render_events,s,events))


def main():
    failures=[]
    for name,func in sorted(globals().copy().items()):
        if name.startswith("test_"):
            try:func();print("PASS",name,flush=True)
            except Exception as exc:
                import traceback
                traceback.print_exc();failures.append(name)
    assert not failures, failures
    print("KNOWLEDGE BOUNDARY: 19 GROUPS PASSED")


if __name__=="__main__":main()
