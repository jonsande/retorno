"""Public IDs: real historical addresses, original evidence and both clients."""
from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import itertools
import json
import os
from pathlib import Path
import pickle
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.location_ids import public_node_id, public_text, restore_public_references
from retorno.cli.parser import parse_command
from retorno.core import lore, communications
from retorno.core.engine import Engine
from retorno.io.save_load import save_single_slot, load_single_slot
from retorno.model.os import Locale, mount_files, read_file
from retorno.model.world import add_known_link
from retorno.worldgen import manifest, historical_radio
from retorno.worldgen.generator import ensure_sector_generated, universe_definition
from information_capabilities_smoke import scene
from knowledge_boundary_smoke import public

SEEDS = (0, 1, 2, 7, 42, 137, 2026, 65535, 271828, 314159, 8675309, 2147483647)


def output(fn, *args):
    with redirect_stdout(io.StringIO()) as stream:
        fn(*args)
    return stream.getvalue()


def command(state, line):
    return repl._resolve_parsed_locations(state, parse_command(line))


def test_01_injective_addresses_seeds_and_discovery_order():
    for seed in SEEDS:
        state = create_initial_state_prologue(seed=seed)
        w = universe_definition(state)
        rows = manifest.query_physical_sectors(w, ('S+000_+000_+000', 'S-001_+000_+000')).sites
        raw = [manifest.operative_id(w, row) for row in rows]
        before, rng = pickle.dumps(state), random.getstate()
        aliases = [public_node_id(state, nid) for nid in raw]
        assert len(aliases) == len(set(aliases))
        assert all(' ' not in alias and (':WG1' not in nid or len(alias) <= 14) for nid,alias in zip(raw,aliases))
        assert pickle.dumps(state) == before and random.getstate() == rng
        left, right = deepcopy(state), deepcopy(state)
        for sid in ('S+000_+000_+000', 'S-001_+000_+000'):
            ensure_sector_generated(left, sid)
        for sid in ('S-001_+000_+000', 'S+000_+000_+000'):
            ensure_sector_generated(right, sid)
        left.world.known_contacts.update(raw)
        right.world.known_contacts.update(reversed(raw))
        assert [public_node_id(left, nid) for nid in raw] == aliases
        assert [public_node_id(right, nid) for nid in raw] == aliases
        state.world.manifest_definition = w
        # A larger arithmetic address domain includes signed axes and slots
        # beyond one digit. No physical enumeration or generation is needed.
        addresses = [f'S{x:+04d}_{y:+04d}_{z:+04d}:WG1_{w.scope}_{slot}'
            for x,y,z,slot in itertools.product((-999,-36,-1,0,1,36,999), repeat=4) if slot >= 0]
        assert len({public_node_id(state,nid) for nid in addresses}) == len(addresses)


def test_02_independent_processes_and_hash_seeds():
    script = '''import json
from retorno.bootstrap import create_initial_state_prologue
from retorno.cli.location_ids import public_node_id
from retorno.worldgen.generator import universe_definition
result=[]
for seed in (0,42,271828):
 s=create_initial_state_prologue(seed=seed);w=universe_definition(s)
 result.append(public_node_id(s,f'S-001_+001_+000:WG1_{w.scope}_1'))
print(json.dumps(result))'''
    rows = [subprocess.check_output([sys.executable, '-c', script], text=True,
        env=dict(os.environ, PYTHONHASHSEED=seed)) for seed in ('0','137','987654321')]
    assert len(set(rows)) == 1
    assert json.loads(rows[0]) == ['P-1.2.0.1'] * 3  # Deliberately game-local.


def test_03_authored_collisions_escape_without_discovery_dependence():
    state = create_initial_state_prologue(seed=0)
    w = universe_definition(state)
    nid = f'S-001_+001_+000:WG1_{w.scope}_1'
    alias = public_node_id(state,nid)
    authored = w.authored[0]
    # Adversarial fixture reserves public prefixes and the canonical operative
    # spelling. Do not recompile physical history; exercise spelling only.
    state.world.manifest_definition = replace(w, authored=w.authored + (
        replace(authored,raw_id=alias),replace(authored,raw_id='P--RESERVED'),
        replace(authored,raw_id=nid)))
    assert public_node_id(state,alias) == alias
    assert public_node_id(state,nid) == nid
    assert public_text(state,'PREFIX'+nid) == 'PREFIX'+nid
    escaped = nid.replace(':WG1_', ':WG1C1_')
    assert public_node_id(state,escaped) == 'P---1.2.0.1'
    state.world.known_nodes.add('UNRELATED')
    assert public_node_id(state,escaped) == 'P---1.2.0.1'
    # Ambiguous descriptive aliases never select the first inserted node.
    known = list(state.world.space.nodes.values())[:2]
    for node in known:
        node.name = 'Same Name'
        state.world.known_contacts.add(node.node_id)
    assert repl._resolve_node_id_from_input(state,'SameName') is None


def test_04_save_load_authored_and_legacy_inputs():
    state, nid = scene()
    alias = public_node_id(state,nid)
    before = deepcopy((state.world.manifest_definition,state.world.node_pools,state.os.fs))
    for line in (f'nav {alias}',f'route solve {alias}',f'dock {alias}',f'drone survey D1 {alias}',
                 f'drone salvage data D1 {alias}',f'drone salvage module D1 {alias}',
                 f'drone salvage drone D1 {alias}',f'drone salvage scrap D1 {alias} 1'):
        assert command(state,line).node_id == nid
    assert command(state,f'drone move D1 {alias}').target_id == nid
    assert command(state,f'drone deploy D1 {alias}').sector_id == nid
    assert command(state,f'nav {nid}').node_id == nid
    assert command(state,'nav ECHO_7').node_id == 'ECHO_7'
    for line in (f'ship survey {alias}',f'nav map path {alias}',f'nav map graph {alias}',f'map path {alias}'):
        assert command(state,line)[-1] == nid
    assert public_node_id(state,'ECHO_7') == 'ECHO_7'
    with TemporaryDirectory() as folder:
        loaded = load_single_slot(save_single_slot(state,Path(folder)/'public.dat')).state
    assert public_node_id(loaded,nid) == alias
    assert repl._resolve_node_id_from_input(loaded,alias) == nid
    assert (loaded.world.manifest_definition,loaded.world.node_pools,loaded.os.fs) == before


def test_05_action_semantics_match_canonical_engine_requests():
    state,nid = scene()
    alias = public_node_id(state,nid)
    lines = (f'dock {alias}',f'route solve {alias}',f'nav {alias}',f'drone move D1 {alias}',
             f'drone survey D1 {alias}',f'drone salvage data D1 {alias}',
             f'drone salvage module D1 {alias}',f'drone salvage drone D1 {alias}',
             f'drone salvage scrap D1 {alias} 1')
    for line in lines:
        left,right = deepcopy(state),deepcopy(state)
        a = Engine().apply_action(left,command(left,line))
        b = Engine().apply_action(right,parse_command(line.replace(alias,nid)))
        assert a == b and left == right, line


def test_06_cli_completion_context_and_public_projection():
    state,nid = scene()
    alias = public_node_id(state,nid)
    assert repl._dock_targets_for_completion(state) == [alias]
    assert repl._drone_local_world_node_targets_for_completion(state) == [alias]
    assert alias in repl._drone_move_targets_for_completion(state)
    assert nid not in repl._known_contact_ids_for_completion(state)
    # Route eligibility must be calculated before aliasing canonical IDs.
    target = next(n for n in state.world.space.nodes if ':WG1' in n and n != nid)
    state.world.known_contacts.add(target)
    assert all(':WG1' not in ident for ident in repl._route_solve_targets_for_completion(state))
    add_known_link(state.world,nid,target,bidirectional=True)
    assert public_node_id(state,target) in repl._travel_targets_for_completion(state)
    assert public_node_id(state,target) not in repl._route_solve_targets_for_completion(state)
    for locale in Locale:
        state.os.locale=locale
        for fn,args in ((repl.render_contacts,()),(repl.render_status,()),(repl.render_nav_routes,()),
                        (repl.render_map_path,(public_node_id(state,target),)),
                        (repl.render_ship_survey,(alias,))):
            text=output(fn,state,*args)
            assert ':WG1' not in text
            assert alias in text,(fn,text)
        assert ':WG1' not in output(repl.render_logs,state)
        events=Engine().apply_action(state,command(state,f'drone survey D1 {alias}'))
        assert alias in output(repl.render_events,state,events)


def test_07_link_view_reverses_exactly_without_changing_archive_or_provenance():
    state,nid = scene('station')
    archive = lore.historical_information_for_node(state,nid)
    entry = next(f for f in archive.files if f.get('navigation_record'))
    record = entry['navigation_record']
    endpoints = (record['source_id'],record['destination_id'])
    raw = entry['content']
    # Keep the certificate for a byte-exact reversibility witness. Ordinary
    # presentation omits only the non-narrative certificate line.
    view = public_text(state,raw,certificates=True)
    assert restore_public_references(state,view,endpoints) == raw
    assert 'HI1:' not in public_text(state,raw)
    assert ':WG1' not in public_text(state,raw)
    path='/data/nav/public-id-witness.txt'
    mount_files(state.os.fs,'',[dict(entry,path=path)])
    stored=deepcopy(state.os.fs[path])
    text=output(repl.render_cat,state,path)
    assert f"LINK: {public_node_id(state,endpoints[0])} -> {public_node_id(state,endpoints[1])}" in text
    assert endpoints[1] in state.world.known_nodes
    assert state.os.fs[path] == stored
    facts=deepcopy((state.world.known_links,state.world.intel,state.os.fs,state.meta.rng_counter))
    output(repl._handle_intel_import,state,path)
    # Existing duplicate intel ledger semantics remain; route/RNG/files do not.
    assert (state.world.known_links,state.os.fs,state.meta.rng_counter) == (facts[0],facts[2],facts[3])
    assert lore.historical_information_for_node(state,nid) == archive


def test_08_mounted_path_projection_keeps_access_controls():
    state,nid=scene('station')
    raw=f'/remote/{nid}/data/nav/view.txt'
    mount_files(state.os.fs,f'/remote/{nid}',[dict(path='/data/nav/view.txt',content='PUBLIC PATH WITNESS',access='guest')])
    alias=public_text(state,raw)
    assert command(state,'cat '+alias)[1] == raw
    assert 'PUBLIC PATH WITNESS' in output(repl.render_cat,state,alias)
    assert 'PUBLIC PATH WITNESS' in output(repl.render_cat,state,alias[:-4])
    assert 'view.txt' in output(repl.render_ls,state,f'/remote/{public_node_id(state,nid)}/data/nav')
    state.os.fs[raw].access = __import__('retorno.model.os',fromlist=['AccessLevel']).AccessLevel.ROOT
    state.os.auth_levels.discard('ROOT')
    assert 'PUBLIC PATH WITNESS' not in output(repl.render_cat,state,alias)


def test_09_negative_disclosure_across_cli_textual_and_commands():
    state,nid=scene()
    secret=next(n for n in state.world.space.nodes if ':WG1' in n and n != nid)
    alias=public_node_id(state,secret)
    before=public(state)
    hidden=deepcopy(state)
    hidden.world.space.nodes[secret].name='SECRET CHANGED'
    hidden.world.space.nodes[secret].x_ly += 10000
    hidden.world.lore_placements.piece_to_node['UNRECEIVED']=secret
    assert public(hidden) == before
    assert repl._resolve_node_id_from_input(state,alias) is None
    assert repl._resolve_node_id_from_input(hidden,alias) is None
    for line in (f'nav {alias}',f'route solve {alias}',f'dock {alias}',f'drone survey D1 {alias}'):
        a,b=deepcopy(state),deepcopy(hidden)
        ae=Engine().apply_action(a,command(a,line));be=Engine().apply_action(b,command(b,line))
        assert output(repl.render_events,a,ae) == output(repl.render_events,b,be)
    assert alias not in repl._known_contact_ids_for_completion(state)
    assert output(repl.render_ship_survey,state,alias) == output(repl.render_ship_survey,hidden,alias)


def test_10_radio_view_reception_link_import_and_uplink_history():
    from historical_radio_smoke import chosen,prepare,ready
    state,row=chosen(lambda r:r.navigation_record is not None and r.emissions[0].end_t is None)
    ready(state)
    # Controlled reception integration; the public journey is separate.
    state.world.current_pos_ly=row.host.position_ly
    op=prepare(state,row)
    assert communications.capture_radio_opportunity(state,op)
    original=deepcopy((state.os.fs[op.path],op.content_by_locale,op.emission.emission_id))
    for locale in Locale:
        state.os.locale=locale
        text=output(repl.render_cat,state,op.path)
        assert ':WG1' not in text and 'HI1:' not in text
        assert public_node_id(state,row.navigation_record.destination_id) in text
    assert (state.os.fs[op.path],op.content_by_locale,op.emission.emission_id) == original
    historical_radio.validate_state(state)
    state,nid=scene()
    archive=lore.historical_information_for_node(state,nid)
    text=output(repl._handle_uplink,state)
    assert ':WG1' not in text and archive == lore.historical_information_for_node(state,nid)
    assert state.world.node_pools[nid].uplink_data_consumed


def test_11_real_textual_tab_shared_prefix_and_dispatch_en_es():
    from retorno.ui_textual.app import RetornoTextualApp
    from textual.widgets import Input
    from retorno.ui_textual import presenter
    async def run(locale):
        with patch.dict(os.environ,{'RETORNO_SCENARIO':'sandbox'}):
            app=RetornoTextualApp(force_new_game=True)
        state,nid=scene('station')
        state.os.locale=locale
        state.os.audio.enabled=state.os.audio.ambient_enabled=False
        state.os.debug_enabled=True
        app.loop.state=state
        app._play_startup_sequence=app._startup_panel_blackout=False
        alias=public_node_id(state,nid)
        assert alias in presenter.build_header(state)
        for line in ('dock ','ship survey ','drone move D1 ','drone survey D1 ',
                     'drone salvage data D1 ','drone salvage module D1 ',
                     'drone salvage drone D1 ','drone salvage scrap D1 '):
            assert alias in app._get_completion_candidates(state,line,'')
        async with app.run_test() as pilot:
            app.loop.set_auto_tick(False)
            widget=app.query_one('#input',Input)
            widget.focus()
            widget.value='ship survey '+alias[:-1]
            await pilot.press('tab')
            assert widget.value == 'ship survey '+alias
            await pilot.press('enter');await pilot.pause()
            assert any('id: '+alias in line for line in app._log_buffer)
            assert not any(':WG1' in line for line in app._log_buffer)
            # Several legitimate contacts share a prefix: TAB cannot pick one.
            others=[n for n in state.world.space.nodes if ':WG1' in n and n != nid][:3]
            for target in others:
                state.world.known_contacts.add(target)
                add_known_link(state.world,nid,target,bidirectional=True)
            widget.value='nav P-'
            await pilot.press('tab')
            candidates=app._get_completion_candidates(state,'nav P-','P-')
            assert len(candidates)>1
            assert widget.value != 'nav '+candidates[0] or all(c==candidates[0] for c in candidates)
            # Dispatch a location action through the actual Textual input.
            widget.value='drone survey D1 '+alias
            await pilot.press('enter');await pilot.pause()
            assert any(job.target.id==nid for job in state.jobs.jobs.values())
    for locale in Locale:
        asyncio.run(run(locale))


def test_12_actual_readline_callback_and_cli_dispatch():
    from types import SimpleNamespace
    from retorno.audio.config import AudioConfigError
    from retorno.core.actions import Action
    state,nid=scene('station')
    state.os.debug_enabled=True
    state.os.audio.enabled=state.os.audio.ambient_enabled=False
    alias=public_node_id(state,nid)
    other=next(n for n in state.world.space.nodes if ':WG1' in n and n!=nid)
    state.world.known_contacts.add(other)
    add_known_link(state.world,nid,other,bidirectional=True)
    other_alias=public_node_id(state,other)
    callback=[]
    seen=[]
    buffer=['']
    original=Engine.apply_action
    lines=iter((f'ship survey {alias}',f'route solve {alias}',f'nav {alias}',
                f'dock {alias}',f'drone survey D1 {alias}','exit'))
    completed=[]
    def apply(engine,s,action):
        seen.append(action)
        return original(engine,s,action)
    def reader(prompt):
        if prompt!='\n> ':
            return 'y'
        if not completed:
            for buf,expected in ((f'ship survey {alias[:-1]}',alias),
                                 ('dock ',alias),('drone move D1 ',alias),
                                 ('drone survey D1 ',alias),('drone salvage data D1 ',alias),
                                 ('nav ',other_alias),('nav map path ',other_alias)):
                buffer[0]=buf
                token=buf.split()[-1] if not buf.endswith(' ') else ''
                results=[]
                for i in range(1000):
                    value=callback[0](token,i)
                    if value is None:
                        break
                    results.append(value)
                assert expected in results,(buf,expected,results)
                assert all(':WG1' not in v for v in results)
                completed.append(buf)
        return next(lines)
    with TemporaryDirectory() as folder, \
         patch.dict(os.environ,{'RETORNO_SCENARIO':'prologue','RETORNO_NEW_GAME':'0'}), \
         patch.object(sys,'argv',['retorno','--save-path',str(Path(folder)/'cli.dat')]), \
         patch.object(repl,'load_single_slot',return_value=SimpleNamespace(state=state,source='main',path='fixture')), \
         patch.object(repl,'run_console_entry_gate'), \
         patch.object(repl,'AudioManager',side_effect=AudioConfigError('controlled audio-free test')), \
         patch.object(repl.readline,'set_completer',side_effect=lambda fn:callback.append(fn)), \
         patch.object(repl.readline,'get_line_buffer',side_effect=lambda:buffer[0]), \
         patch.object(Engine,'apply_action',apply),patch('builtins.input',side_effect=reader):
        text=output(repl.main)
    assert completed and callback
    assert any(a.__class__.__name__=='RouteSolve' and a.node_id==nid for a in seen)
    assert any(a.__class__.__name__=='Travel' and a.node_id==nid for a in seen)
    assert not any(getattr(a,'node_id',None)==alias for a in seen)
    assert alias in text and ':WG1' not in text


def test_13_successful_route_computation_with_public_contact_id():
    import math
    state,nid=scene('station')
    # Instrumented range fixture, not the public gameplay evidence. The target
    # and geometry are real historical sites; no topology or identity changes.
    state.ship.sensors_range_ly=45
    origin=state.world.space.nodes[nid]
    target=next(n for n in state.world.space.nodes.values() if ':WG1' in n.node_id
        and n.node_id!=nid and 0<math.dist((origin.x_ly,origin.y_ly,origin.z_ly),
            (n.x_ly,n.y_ly,n.z_ly))<=45)
    state.world.known_contacts.add(target.node_id)
    alias=public_node_id(state,target.node_id)
    assert alias in repl._route_solve_targets_for_completion(state)
    events=Engine().apply_action(state,command(state,'route solve '+alias))
    assert any(e.data.get('job_type')=='route_solve' for e in events),events
    job=state.jobs.jobs[state.jobs.active_job_ids[-1]]
    completed=Engine().tick(state,job.eta_s+1)
    assert target.node_id in state.world.known_links[nid]
    assert alias in repl._travel_targets_for_completion(state)
    assert alias not in repl._route_solve_targets_for_completion(state)
    text=output(repl.render_events,state,completed)
    assert alias in text and ':WG1' not in text


def main():
    for name,fn in sorted(globals().copy().items()):
        if name.startswith('test_'):
            fn();print('PASS',name,flush=True)
    print('PUBLIC LOCATION IDS: 13 GROUPS PASS')


if __name__=='__main__':
    main()
