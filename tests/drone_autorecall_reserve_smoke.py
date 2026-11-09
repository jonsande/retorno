"""Preventive autorecall: reserve budgets, scheduler priority and public clients."""
import asyncio
from contextlib import redirect_stdout
from copy import deepcopy
import io
import os
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.cli.parser import parse_command
from retorno.config.balance import Balance
from retorno.core.actions import DroneMove, DroneDeploy, Repair
from retorno.core.engine import Engine
from retorno.io.save_load import save_single_slot, load_single_slot
from retorno.model.drones import DroneLocation, DroneStatus
from retorno.model.events import EventType
from retorno.model.jobs import JobStatus, JobType
from retorno.model.os import Locale
from retorno.model.systems import SystemState
from retorno.ui_textual import presenter
from retorno.ui_textual.app import RetornoTextualApp


def capture(fn, *args):
    with redirect_stdout(io.StringIO()) as stream:
        fn(*args)
    return stream.getvalue()


class AutorecallReserveTests(unittest.TestCase):
    def setUp(self):
        self.s = create_initial_state_sandbox(seed=29)
        self.e = Engine()
        self.d = self.s.ship.drones['D1']
        self.d.status = DroneStatus.DEPLOYED
        self.d.location = DroneLocation('ship_sector', 'ENG-R1')
        self.d.integrity = 1.0
        for system in self.s.ship.systems.values():
            system.base_decay_per_s = 0.0
        self.s.ship.power.p_gen_base_kw = 20
        self.s.ship.systems['engines'].health = .5
        self.s.ship.docked_node_id = None
        self.success = patch.multiple(Balance, REPAIR_JOB_FAIL_P_BASE=0.0, DRONE_RECALL_P_MIN=1.0, DRONE_RECALL_P_MAX=1.0)
        self.success.start()
        self.addCleanup(self.success.stop)

    def repair(self):
        return self.e.apply_action(self.s, Repair(drone_id='D1', system_id='engines'))

    def active(self, kind):
        return [j for j in self.s.jobs.jobs.values() if j.job_type == kind and j.status in {JobStatus.QUEUED, JobStatus.RUNNING}]

    def test_01_twelve_percent_repair_rejected_and_recalled_without_tick(self):
        self.s.os.set_debug(True)
        self.d.battery = .12
        scrap, health, clock = self.s.ship.cargo_scrap, self.s.ship.systems['engines'].health, self.s.clock.t
        events = self.repair()
        self.assertEqual(events[0].data['reason'], 'drone_return_reserve')
        self.assertAlmostEqual(events[0].data['required_percent'], 18.09)
        self.assertEqual(self.d.battery, .12)
        self.assertEqual(self.s.ship.cargo_scrap, scrap)
        self.assertEqual(self.s.ship.systems['engines'].health, health)
        self.assertEqual(self.s.clock.t, clock)
        self.assertFalse(self.active(JobType.REPAIR_SYSTEM))
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)
        self.e.tick(self.s, 30)
        self.assertEqual(self.d.status, DroneStatus.DOCKED)

    def test_02_safe_repair_charged_once_and_return_triggered_at_threshold(self):
        self.d.battery = .1 + .08 + 45 * Balance.DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S
        self.assertTrue(any(e.type == EventType.JOB_QUEUED for e in self.repair()))
        self.e.tick(self.s, 45)
        self.assertAlmostEqual(self.d.battery, .1)
        self.assertAlmostEqual(self.s.ship.systems['engines'].health, .65)
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)
        self.assertEqual(sum(j.job_type == JobType.REPAIR_SYSTEM and j.status == JobStatus.COMPLETED for j in self.s.jobs.jobs.values()), 1)
        self.e.tick(self.s, 25)
        self.assertEqual(self.d.status, DroneStatus.DOCKED)
        self.assertGreaterEqual(self.d.battery, .05)

    def test_03_autorecall_off_keeps_risk_opt_in(self):
        self.d.autorecall_enabled = False
        self.d.battery = .12
        self.repair()
        self.e.tick(self.s, 45)
        self.assertLess(self.d.battery, .05)
        self.assertAlmostEqual(self.s.ship.systems['engines'].health, .65)
        self.assertFalse(self.active(JobType.RECALL_DRONE))

    def test_04_queue_budget_and_refunds_and_priority(self):
        self.d.battery = .3
        scrap = self.s.ship.cargo_scrap
        self.repair()
        self.repair()
        self.assertEqual(len(self.active(JobType.REPAIR_SYSTEM)), 2)
        events = self.repair()
        self.assertTrue(any(e.data.get('reason') == 'drone_return_reserve' for e in events))
        self.assertFalse(self.active(JobType.REPAIR_SYSTEM))
        self.assertEqual(self.s.ship.cargo_scrap, scrap)
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)
        self.assertEqual(self.s.jobs.jobs[self.s.jobs.active_job_ids[0]].job_type, JobType.RECALL_DRONE)
        self.repair()
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)
        self.assertEqual(self.s.ship.cargo_scrap, scrap)

    def test_05_recheck_on_start_after_battery_or_threshold_changes(self):
        for change in ('battery', 'threshold', 'capacity'):
            s, d, e = deepcopy(self.s), None, self.e
            d = s.ship.drones['D1']
            d.battery = .3
            e.apply_action(s, Repair(drone_id='D1', system_id='engines'))
            if change == 'battery': d.battery = .12
            elif change == 'threshold': d.autorecall_threshold = .3
            else: d.installed_modules = ['high_density_cell']; d.battery = .2
            scrap = s.ship.cargo_scrap
            events = e.tick(s, 1)
            self.assertTrue(any(v.data.get('reason') == 'drone_return_reserve' or v.data.get('message_key') == 'job_cancelled_autorecall' for v in events), change)
            self.assertAlmostEqual(s.ship.systems['engines'].health, .5)
            self.assertGreater(s.ship.cargo_scrap, scrap)

    def test_06_running_safe_work_finishes_before_prioritized_return(self):
        self.d.battery = .3
        self.repair()
        self.e.tick(self.s, 1)
        running = self.active(JobType.REPAIR_SYSTEM)[0]
        # A second task no longer fits after accounting for the running task.
        self.d.autorecall_threshold = .15
        events = self.repair()
        self.assertEqual(running.status, JobStatus.RUNNING)
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)
        self.e.tick(self.s, 44)
        self.assertEqual(running.status, JobStatus.COMPLETED)
        self.e.tick(self.s, 25)
        self.assertEqual(self.d.status, DroneStatus.DOCKED)

    def test_07_large_wait_does_not_skip_idle_threshold(self):
        self.d.battery = .101
        events = self.e.tick(self.s, 200)
        self.assertEqual(self.d.status, DroneStatus.DOCKED)
        self.assertEqual(sum(v.data.get('reason') == 'drone_autorecall' for v in events), 1)
        self.assertFalse(any(v.type == EventType.DRONE_DISABLED for v in events))
        self.assertAlmostEqual(self.s.clock.t, 200)

    def test_08_low_user_threshold_keeps_a_minimum_return_margin(self):
        self.d.autorecall_threshold = .01
        self.d.battery = .055
        self.e.tick(self.s, 500)
        self.assertEqual(self.d.status, DroneStatus.DOCKED)
        self.assertGreaterEqual(self.d.battery, 0)

    def test_09_actual_four_percent_stays_blocked_with_one_notice(self):
        self.d.battery = .04
        events = self.e.tick(self.s, 1)
        self.assertEqual(self.d.autorecall_block_reason, 'drone_autorecall_battery')
        self.assertEqual(sum(v.data.get('reason') == 'drone_autorecall_battery' for v in events), 1)
        self.assertFalse(self.active(JobType.RECALL_DRONE))
        events = self.e.tick(self.s, 1)
        self.assertFalse(any(v.data.get('reason') == 'drone_autorecall_battery' for v in events))
        self.assertLess(self.d.battery, .04)

    def test_10_block_diagnostics_localization_and_shared_presenter(self):
        for reason in ('drone_autorecall_battery', 'drone_autorecall_integrity', 'drone_autorecall_not_docked'):
            for locale in (Locale.EN, Locale.ES):
                s = deepcopy(self.s)
                d = s.ship.drones['D1'];s.os.locale = locale
                d.battery = .04 if reason.endswith('battery') else .09
                if reason.endswith('integrity'): d.integrity = .01
                if reason.endswith('not_docked'): d.location = DroneLocation('world_node', 'ECHO_7')
                events = self.e._update_drone_battery_alerts(s)
                text = capture(repl.render_events, s, events)
                self.assertIn('Autorretorno bloqueado' if locale == Locale.ES else 'Autorecall blocked', text)
                self.assertIn('D1', text)
                before = pickle.dumps(s)
                lines = capture(repl.render_drone_status, s, 'D1')
                self.assertEqual(presenter.build_command_output(repl.render_drone_status, s, 'D1'), lines.strip().splitlines())
                self.assertEqual(before, pickle.dumps(s))

    def test_11_move_and_deploy_reserve_and_module_capacity(self):
        self.d.battery = .12
        events = self.e.apply_action(self.s, DroneMove(drone_id='D1', target_id='BRG-01'))
        self.assertTrue(any(v.data.get('reason') == 'drone_return_reserve' for v in events))
        self.d.status = DroneStatus.DOCKED
        self.d.location = DroneLocation('ship_sector', 'DRN-BAY')
        self.s.jobs.active_job_ids.clear()
        events = self.e.apply_action(self.s, DroneDeploy(drone_id='D1', sector_id='ENG-R1'))
        self.assertTrue(any(v.data.get('reason') == 'drone_return_reserve' for v in events))
        self.assertEqual(self.d.status, DroneStatus.DOCKED)
        self.d.status = DroneStatus.DEPLOYED;self.d.location.id = 'ENG-R1'
        self.d.installed_modules = ['high_density_cell']
        self.d.battery = .21
        events = self.repair()
        self.assertTrue(any(v.data.get('reason') == 'drone_return_reserve' for v in events))

    def test_12_pending_return_and_reason_survive_save_load(self):
        self.d.battery = .12
        self.repair()
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'slot.dat'
            save_single_slot(self.s, path)
            s = load_single_slot(path).state
            self.e.tick(s, 30)
            self.assertEqual(s.ship.drones['D1'].status, DroneStatus.DOCKED)
            self.assertEqual(sum(j.job_type == JobType.RECALL_DRONE for j in s.jobs.jobs.values()), 1)
            d = s.ship.drones['D1']
            d.status = DroneStatus.DEPLOYED
            d.battery = .04
            self.e.tick(s, 1)
            save_single_slot(s, path)
            s = load_single_slot(path).state
            self.assertEqual(s.ship.drones['D1'].autorecall_block_reason, 'drone_autorecall_battery')
            self.assertFalse(any(v.data.get('reason') == 'drone_autorecall_battery' for v in self.e.tick(s, 1)))

    def test_13_debug_setting_enables_return_without_advancing_time(self):
        self.d.battery = .09;self.d.autorecall_enabled = False
        before = self.s.clock.t
        text = capture(repl._set_drone_autorecall, self.s, 'D1', True, None)
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)
        self.assertEqual(self.s.clock.t, before)
        self.assertIn('recall_drone', text)

    def test_14_failed_repair_spends_battery_once_and_still_returns(self):
        self.d.battery = .1809
        self.repair()
        with patch.object(Balance, 'REPAIR_JOB_FAIL_P_BASE', 1.0):
            self.e.tick(self.s, 45)
        self.assertAlmostEqual(self.d.battery, .1)
        self.assertAlmostEqual(self.s.ship.systems['engines'].health, .5)
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)

    def test_15_textual_debug_input_rejects_and_queues_before_wait_en_es(self):
        from textual.widgets import Input

        async def run(locale, slot):
            with patch.dict(os.environ, {'RETORNO_SCENARIO': 'sandbox'}):
                app = RetornoTextualApp(force_new_game=True, save_path=str(slot))
            s = deepcopy(self.s)
            s.os.set_debug(True)
            s.os.locale = locale
            s.os.audio.enabled = s.os.audio.ambient_enabled = False
            d = s.ship.drones['D1'];d.battery = .12
            app.loop.state = s
            app.loop.set_auto_tick(False)
            app._play_startup_sequence = app._startup_panel_blackout = False
            async with app.run_test() as pilot:
                app.loop.set_auto_tick(False)
                widget = app.query_one('#input', Input)

                async def command(text):
                    widget.focus();widget.value = text
                    await pilot.press('enter');await pilot.pause()

                clock, battery, scrap = s.clock.t, d.battery, s.ship.cargo_scrap
                await command('drone repair D1 engines')
                self.assertEqual(s.clock.t, clock)
                self.assertEqual(d.battery, battery)
                self.assertEqual(s.ship.cargo_scrap, scrap)
                self.assertEqual(len([j for j in s.jobs.jobs.values() if j.job_type == JobType.RECALL_DRONE]), 1)
                self.assertTrue(any(('Tarea bloqueada' if locale == Locale.ES else 'Task blocked') in line for line in app._log_buffer))
                await command('wait 30')
                self.assertEqual(d.status, DroneStatus.DOCKED)

        with TemporaryDirectory() as folder:
            for locale in (Locale.EN, Locale.ES):
                asyncio.run(run(locale, Path(folder) / f'{locale.value}.dat'))

    def test_16_compound_move_repair_refund(self):
        self.d.battery = .2
        self.d.location.id = 'BRG-01'
        scrap = self.s.ship.cargo_scrap
        events = self.e.apply_action(self.s, Repair(drone_id='D1', system_id='engines', auto_move=True))
        self.assertTrue(any(v.data.get('reason') == 'drone_return_reserve' for v in events))
        self.assertEqual(self.s.ship.cargo_scrap, scrap)
        self.assertFalse(self.active(JobType.MOVE_DRONE))
        self.assertFalse(self.active(JobType.REPAIR_SYSTEM))
        self.assertEqual(len(self.active(JobType.RECALL_DRONE)), 1)

    def test_17_god_mode_does_not_reserve_consumption_it_bypasses(self):
        self.s.os.set_debug(True)
        self.s.os.debug_god_enabled = True
        self.d.battery = .12
        self.repair()
        self.e.tick(self.s, 45)
        self.assertEqual(self.d.battery, .12)
        self.assertAlmostEqual(self.s.ship.systems['engines'].health, .65)
        self.assertFalse(self.active(JobType.RECALL_DRONE))


if __name__ == '__main__':
    unittest.main()
