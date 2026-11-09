import io
import json
import math
from contextlib import redirect_stdout
from pathlib import Path
from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.core.engine import Engine
from retorno.config.balance import Balance
from retorno.runtime.loop import GameLoop

s = create_initial_state_prologue(seed=701)
e = Engine()
loop = GameLoop(e, s)
loop.set_auto_tick(False)
rows = []

def do(text):
    buf = io.StringIO()
    with redirect_stdout(buf):
        if text == 'uplink':
            repl._handle_uplink(s)
            events = []
        elif text.startswith('cat '):
            repl.render_cat(s, text[4:])
            events = []
        elif text == 'hibernate until_arrival':
            blocked = repl._hibernate_blocked_message(s)
            if blocked:
                print(blocked)
                events = []
            else:
                result = repl._execute_hibernate(loop, (s.ship.arrival_t-s.clock.t+1)/Balance.YEAR_S)
                print('hibernate', result.wake_reason, result.actual_years)
                events = [event for _, event in result.events_to_render]
        else:
            action = parse_command(text)
            if isinstance(action, tuple) and action[0] == 'WAIT':
                events = loop.step_many(action[1], dt=1)
            else:
                events = e.apply_action(s, action)
        print('\n'.join(event.message for event in events))
    rows.append(dict(command=text, t=s.clock.t, output=buf.getvalue()))
    print(text, buf.getvalue()[:150].replace('\n',' | '), flush=True)
    if not text.startswith('wait '):
        for _ in range(1000):
            if not s.jobs.active_job_ids:
                break
            # Equivalent to successive public wait commands, recorded below.
            do('wait 1')
        assert not s.jobs.active_job_ids

def read_new():
    for path, node in list(s.os.fs.items()):
        if path not in read and path.endswith('.en.txt') and path.startswith(('/remote/', '/logs/nav/', '/logs/signals/')):
            read.add(path)
            do('cat ' + path)

def travel(ident):
    assert ident in s.world.known_nodes | s.world.known_contacts
    if s.ship.docked_node_id:
        do('undock')
    do('route solve ' + ident)
    do('nav ' + ident)
    if s.ship.in_transit:
        if s.ship.arrival_t-s.clock.t < 10000:
            do('wait ' + str(s.ship.arrival_t-s.clock.t+1))
        else:
            do('hibernate until_arrival')
    return not s.ship.in_transit and s.world.current_node_id == ident

read = set()
try:
    for text in ['power off data_core','drone deploy D1 PWR-A1',
                 'drone repair D1 power_core','drone repair D1 power_core','drone repair D1 power_core',
                 'drone move D1 BUS-A2','drone repair D1 energy_distribution','drone repair D1 energy_distribution',
                 'drone move D1 BRG-01','drone repair D1 comms','drone recall D1',
                 'power on comms','boot radiod','power on sensors','boot sensord','scan',
                 'power on data_core','boot datad']:
        do(text)
    explored = []
    for _ in range(6):
        read_new()
        known = s.world.known_nodes | s.world.known_contacts
        current = s.world.current_pos_ly
        options = [ident for ident in known if ident not in explored and ident in s.world.space.nodes
                   and s.world.space.nodes[ident].kind in {'station','relay','waystation'}
                   and (ident in s.world.known_links.get(s.world.current_node_id, set())
                        or math.dist(current, (s.world.space.nodes[ident].x_ly,s.world.space.nodes[ident].y_ly,s.world.space.nodes[ident].z_ly)) <= s.ship.sensors_range_ly)]
        priority = {'ECHO_7':0, 'HARBOR_12':1, 'LIRIA':2}
        goal = next((s.world.space.nodes[i] for i in ('LIRIA', 'HARBOR_12') if i in known), None)
        def rank(ident):
            node = s.world.space.nodes[ident]
            distance = math.dist((node.x_ly,node.y_ly,node.z_ly), (goal.x_ly,goal.y_ly,goal.z_ly)) if goal else 0
            return priority.get(ident,3), distance, ident
        options.sort(key=rank)
        if not options:
            break
        ident = options[0]
        explored.append(ident)
        if not travel(ident):
            break
        do('dock ' + ident)
        do('power plan normal')
        do('power on data_core')
        do('boot datad')
        do('uplink')
        do('power off data_core')
        do('power on drone_bay')
        do('drone deploy D1 ' + ident)
        do('drone salvage data D1')
        do('drone recall D1')
        read_new()
        do('power on sensors')
        do('boot sensord')
        do('scan')
    print('EXPLORED', explored, flush=True)
finally:
    # Omniscient assessment after the public policy has finished; never selects a command.
    key='arc:amanecer_elena_01:liria_navigation_index'
    reservation=s.world.narrative_snapshot['reservations'][key]
    host=reservation['node_id']
    result=dict(seed=701, transcript=rows, clock=s.clock.t, current=s.world.current_node_id,
                host=host, host_known=host in s.world.known_nodes,
                host_materialized=host in s.world.space.nodes,
                liria_known='LIRIA' in s.world.known_nodes,
                delivered=sorted(s.world.lore.delivered),
                known_links={k:sorted(v) for k,v in s.world.known_links.items()},
                known_nodes=sorted(s.world.known_nodes),
                positions=s.world.narrative_snapshot['positions'],
                debug=s.os.debug_enabled)
    Path('/tmp/retorno-c2b-public-evidence.json').write_text(json.dumps(result, indent=2))
    print('ASSESSMENT', {k:v for k,v in result.items() if k not in {'transcript','known_links','known_nodes','positions'}}, flush=True)
