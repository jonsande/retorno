"""Deterministic, focused regression checks for session-only god protection."""
from __future__ import annotations

import copy
import io
import pickle
import tempfile
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import ParseError, parse_command
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneStatus
from retorno.model.jobs import Job, JobStatus, JobType, RiskProfile, TargetRef
from retorno.model.os import Locale, OSState
from retorno.model.systems import SystemState
from retorno.runtime.loop import GameLoop
from retorno.ui_textual.app import RetornoTextualApp


def command(state, mode):
    with redirect_stdout(io.StringIO()) as out:
        repl.handle_debug_god(state, mode)
    return out.getvalue()


def main():
    engine = Engine()
    state = create_initial_state_prologue()
    for mode in ('on', 'off', 'status'):
        assert parse_command(f'debug god {mode}') == ('DEBUG_GOD', mode)
    for invalid in ('debug god', 'debug god yes', 'debug god on extra'):
        try:
            parse_command(invalid)
        except ParseError:
            pass
        else:
            raise AssertionError(invalid)
    assert 'DEBUG' in command(state, 'on') and not state.os.god_active
    state.os.set_debug(True)
    # The command must change only the debug flag: no knowledge, RNG, jobs or resources.
    before = pickle.dumps(state)
    assert 'ON' in command(state, 'on')
    assert state.os.god_active
    assert 'ON' in command(state, 'status')
    state.os.debug_god_enabled = False
    assert pickle.dumps(state) == before
    command(state, 'on')
    state.os.set_debug(True)  # Repeating debug on is not a new session.
    assert state.os.god_active
    for locale, word in ((Locale.EN, 'ON'), (Locale.ES, 'ACTIVADO')):
        state.os.locale = locale
        assert word in command(state, 'status')
        with redirect_stdout(io.StringIO()) as output:
            repl.print_help(locale.value, verbose=True)
        assert 'debug god on|off|status' in output.getvalue()
    state.os.locale = Locale.EN

    # Existing prologue failures remain; direct wear paths cannot repair them.
    old_systems = copy.deepcopy(state.ship.systems)
    state.ship.hull_integrity = .43
    drone = next(iter(state.ship.drones.values()))
    drone.status = DroneStatus.DEPLOYED
    drone.battery, drone.integrity, drone.dose_rad = .25, .36, 900.0
    for transit, hibernate in ((False, False), (True, False), (False, True)):
        state.ship.in_transit, state.ship.is_hibernating = transit, hibernate
        engine._apply_hull_degradation(state, 1000.0, 100.0)
        engine._apply_degradation(state, 1000.0, 0.0, True, 100.0)
        engine._apply_radiation(state, 1000.0, 100.0)
        engine._update_drone_maintenance(state, 1000.0)
        engine._update_drone_battery_alerts(state)
    assert state.ship.hull_integrity == .43
    assert state.ship.systems == old_systems
    assert (drone.battery, drone.integrity, drone.dose_rad) == (.25, .36, 900.0)
    assert drone.status == DroneStatus.DEPLOYED
    drone.status = DroneStatus.DISABLED
    engine._update_drone_maintenance(state, 10.0)
    assert drone.status == DroneStatus.DISABLED and drone.integrity == .36
    state.ship.in_transit = state.ship.is_hibernating = False

    # Battery costs share the same guarded path; exercise actual job completion too.
    drone.status = DroneStatus.DOCKED
    job = Job('J1', JobType.DEPLOY_DRONE, JobStatus.RUNNING, 7.0,
              owner_id=drone.drone_id, target=TargetRef('ship_sector', 'DRN-BAY'),
              params={'drone_id': drone.drone_id})
    engine._apply_job_effect(state, job)
    assert drone.status == DroneStatus.DEPLOYED and drone.battery == .25
    for cost_name in dir(Balance):
        if cost_name.startswith('DRONE_BATTERY_DRAIN_'):
            engine._drain_drone_battery(state, drone, getattr(Balance, cost_name))
    engine._drain_repair_operator_battery(state, job)
    assert drone.battery == .25

    # Force bay and emergency risk deterministically; failures still occur.
    job.params['bay_state_at_start'] = 'damaged'
    with patch.object(Balance, 'DRONE_BAY_DAMAGED_INTEGRITY_RISK_P', 1.0):
        assert engine._apply_drone_bay_damaged_integrity_risk(state, job, drone, 'deploy') == []
    job.risk = RiskProfile(p_fail_per_s=1.0)
    assert engine._maybe_fail_emergency_job(state, job, 1.0) is not None
    assert job.status == JobStatus.FAILED
    assert drone.status == DroneStatus.DEPLOYED and drone.integrity == .36

    # Passive repair failure still consumes scrap, but cannot damage the drone.
    drone.status = DroneStatus.DOCKED
    support = {'charge_rate': 0.0, 'decon_rate': 0.0, 'repair_rate_mult': 1.0,
               'repair_scrap_cost': 1, 'repair_fail_p': 1.0, 'repair_fail_hit': .1}
    state.ship.cargo_scrap = 5
    with patch.object(engine, '_drone_bay_support_snapshot', return_value=support):
        engine._update_drone_maintenance(state, 1.0)
        assert drone.integrity == .36 and state.ship.cargo_scrap == 4
        command(state, 'off')
        engine._update_drone_maintenance(state, 1.0)
        assert drone.integrity < .36 and state.ship.cargo_scrap == 3
    drone.status = DroneStatus.DEPLOYED
    command(state, 'on')
    state.os.set_debug(False)
    assert not state.os.god_active and not state.os.debug_god_enabled
    state.os.set_debug(True)
    assert not state.os.god_active
    engine._apply_hull_degradation(state, 1000.0, 100.0)
    engine._apply_degradation(state, 1000.0, 0.0, True, 100.0)
    engine._apply_radiation(state, 1000.0, 100.0)
    old_integrity = drone.integrity
    engine._update_drone_maintenance(state, 1000.0)
    assert state.ship.hull_integrity < .43
    assert any(s.health < old_systems[sid].health for sid, s in state.ship.systems.items())
    assert drone.integrity < old_integrity and drone.battery < .25 and drone.dose_rad > 900.0
    command(state, 'off')
    assert 'OFF' in command(state, 'status')

    # Normal bay damage and emergency disabling resume after god is switched off.
    drone.integrity, drone.battery = .9, .8
    with patch.object(Balance, 'DRONE_BAY_DAMAGED_INTEGRITY_RISK_P', 1.0):
        assert engine._apply_drone_bay_damaged_integrity_risk(state, job, drone, 'deploy')
    assert drone.integrity < .9
    engine._maybe_fail_emergency_job(state, job, 1.0)
    assert drone.status == DroneStatus.DISABLED
    # A stored true flag alone cannot protect a non-debug session.
    state.os.set_debug(False)
    state.os.debug_god_enabled = True
    assert not state.os.god_active
    old_hull = state.ship.hull_integrity
    engine._damage_hull(state, .01)
    assert state.ship.hull_integrity < old_hull
    assert repl._terminal_state_allows(('DEBUG_GOD', 'off'))

    # Legacy payloads default off; actual loading clears even a saved true flag.
    legacy = OSState.__new__(OSState)
    legacy.__setstate__((None, {'debug_enabled': True}))
    assert not legacy.god_active
    state = create_initial_state_sandbox()
    state.os.set_debug(True)
    command(state, 'on')
    assert copy.deepcopy(state).os == state.os  # Recovery staging must preserve OS state.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'save.dat'
        save_single_slot(state, path)
        assert state.os.god_active  # Saving must not change the live session.
        loaded = load_single_slot(path)
        assert loaded is not None and not loaded.state.os.debug_god_enabled
        save_single_slot(state, path)  # Creates the ordinary backup slot.
        path.write_bytes(b'corrupt-primary')
        backup = load_single_slot(path)
        assert backup is not None and backup.source == 'backup'
        assert not backup.state.os.god_active

    # Real Textual command dispatch, no wall-clock waits or background thread.
    with patch.dict('os.environ', {'RETORNO_SCENARIO': 'sandbox'}):
        app = RetornoTextualApp(force_new_game=True)
    lines = []
    app._log_line = lambda line, **kwargs: lines.append(line)
    app._log_lines = lines.extend
    app._startup_panel_blackout = app._startup_sequence_running = False
    def submit(text):
        app.on_input_submitted(SimpleNamespace(value=text, input=SimpleNamespace(value=text)))
    with patch.object(app.loop, 'start'):
        submit('debug on')
        assert not app.loop._auto_tick_enabled
        t = app.loop.state.clock.t
        submit('debug god on')
        assert app.loop.state.os.god_active and app.loop.state.clock.t == t
        submit('debug god status')
        assert 'God mode: ON' in lines
        submit('wait 3')
        assert app.loop.state.clock.t == t + 3
        submit('debug off')
        assert app.loop._auto_tick_enabled and not app.loop.state.os.god_active
        submit('debug on')
        assert not app.loop.state.os.god_active
    assert set(app._get_completion_candidates(app.loop.state, 'debug god ', '')) == {'on', 'off', 'status'}
    app.loop.stop()

    # Real CLI dispatch in each language, with deterministic manual time only.
    for locale in Locale:
        cli_state = create_initial_state_sandbox()
        cli_state.os.locale = locale
        commands = iter(('debug god on', 'debug on', 'debug god on',
                         'debug god status', 'wait 2', 'debug god off',
                         'debug god on', 'debug off', 'debug on', 'debug god status', 'exit'))
        start_t = cli_state.clock.t
        with patch.dict('os.environ', {'RETORNO_SCENARIO': 'sandbox'}), \
             patch.object(sys, 'argv', ['retorno', '--new-game', '--save-path', '/tmp/unused-god-test.dat']), \
             patch.object(repl, 'create_initial_state_sandbox', return_value=cli_state), \
             patch.object(repl, 'save_exists', return_value=False), \
             patch.object(repl, 'save_single_slot', return_value='test-only'), \
             patch.object(repl, 'run_console_entry_gate'), \
             patch.object(repl, '_maybe_run_startup_sequence'), \
             patch.object(repl, 'AudioManager', side_effect=repl.AudioConfigError('test-only')), \
             patch.object(GameLoop, 'start'), patch.object(GameLoop, 'stop'), \
             patch.object(repl.readline, 'set_completer'), \
             patch('builtins.input', side_effect=lambda *args: next(commands)), \
             redirect_stdout(io.StringIO()) as output:
            repl.main()
        transcript = output.getvalue()
        assert ('God mode: ON' if locale == Locale.EN else 'Modo dios: ACTIVADO') in transcript
        assert ('God mode: OFF' if locale == Locale.EN else 'Modo dios: DESACTIVADO') in transcript
        assert cli_state.clock.t == start_t + 3  # Initial CLI tick + wait 2.
        assert not cli_state.os.god_active

    # Compare short, identical physical travel and job progress with god on/off.
    base = create_initial_state_sandbox()
    base.ship.in_transit = True
    base.ship.transit_from = base.ship.current_node_id
    base.ship.transit_to = 'ECHO_7'
    base.ship.arrival_t = base.clock.t + 20.0
    moving_drone = next(iter(base.ship.drones.values()))
    moving_drone.status = DroneStatus.DEPLOYED
    moving_drone.battery = 1.0
    moving_drone.integrity = 1.0
    move = Job('J77', JobType.MOVE_DRONE, JobStatus.RUNNING, 30.0,
               owner_id=moving_drone.drone_id, target=TargetRef('ship_sector', 'DRN-BAY'),
               params={'drone_id': moving_drone.drone_id})
    base.jobs.jobs[move.job_id] = move
    base.jobs.active_job_ids.append(move.job_id)
    control, protected = copy.deepcopy(base), copy.deepcopy(base)
    for test_state, god in ((control, False), (protected, True)):
        test_state.os.set_debug(True)
        if god:
            command(test_state, 'on')
        GameLoop(Engine(), test_state).step_many(3.0)
    assert protected.clock == control.clock
    assert protected.ship.arrival_t == control.ship.arrival_t
    assert protected.ship.in_transit == control.ship.in_transit
    assert protected.jobs == control.jobs
    assert protected.jobs.jobs[move.job_id].status == JobStatus.RUNNING
    assert protected.jobs.jobs[move.job_id].eta_s == 27.0
    assert protected.ship.in_transit
    assert protected.world == control.world
    assert protected.ship.radiation_env_rad_per_s == control.ship.radiation_env_rad_per_s
    print('DEBUG GOD SMOKE PASSED')


if __name__ == '__main__':
    main()
