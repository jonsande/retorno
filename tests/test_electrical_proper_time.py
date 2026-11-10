"""T-04B1 electricity regressions, updated for T-04B2 ordinary ship wear."""
from copy import deepcopy
from dataclasses import asdict
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core import engine as engine_module
from retorno.core.actions import SystemOn, Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.core.temporal import proper_time_interval
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.events import EventType
from retorno.model.jobs import Job, JobStatus, JobType, TargetRef
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link


class ElectricalProperTimeTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.state = create_initial_state_sandbox(seed=29)
        self.state.ship.drones.clear()
        # Fixed powers isolate integration from ordinary wear and bay upkeep.
        for system in self.state.ship.systems.values():
            system.health = 1.0
            system.state = SystemState.NOMINAL
            system.forced_offline = False
            system.p_nom_kw = 0.0
            system.base_decay_per_s = 0.0
        self.state.ship.systems['core_os'].p_nom_kw = 4.0
        p = self.state.ship.power
        p.p_gen_base_kw = p.p_gen_kw = 10.0
        p.p_gen_bonus_kw = p.quality_offset = 0.0
        p.e_batt_kwh, p.e_batt_max_kwh = 60.0, 100.0
        p.p_charge_max_kw = p.p_discharge_max_kw = 20.0
        p.eta_charge = p.eta_discharge = p.power_quality = 1.0
        self.state.ship.docked_node_id = None
        origin = self.state.world.space.nodes[self.state.world.current_node_id]
        self.target = 'ELECTRICAL_TEST'
        self.state.world.space.nodes[self.target] = SpaceNode(
            self.target, self.target, 'station', x_ly=origin.x_ly + 4.0,
            y_ly=origin.y_ly, z_ly=origin.z_ly, radiation_rad_per_s=.001)
        self.state.world.known_nodes.add(self.target)
        add_known_link(self.state.world, origin.node_id, self.target, bidirectional=True)

    def depart(self, beta=.8, state=None):
        s = state or self.state
        if beta == .8:
            s.ship.installed_modules.append('engine_speed_upgrade_01')
            self.engine._apply_health_state(s.ship.systems['engines'], s, [], cause='module_install')
        else:
            self.assertEqual(beta, .5)
        events = self.engine.apply_action(s, Travel(node_id=self.target, no_cruise=True))
        self.assertTrue(any(e.type == EventType.TRAVEL_STARTED for e in events), events)
        self.assertEqual(s.ship.transit_speed_ly_per_year, beta)
        return s

    def test_rest_retains_charge_and_discharge_including_cruise_profile(self):
        for mode in ('NORMAL', 'CRUISE'):
            for generation, load, expected in ((10, 4, 66), (4, 10, 54), (4, 4, 60)):
                with self.subTest(mode=mode, generation=generation, load=load):
                    s = deepcopy(self.state)
                    s.ship.op_mode = mode
                    s.ship.power.p_gen_base_kw = generation
                    s.ship.systems['core_os'].p_nom_kw = load
                    self.engine.tick(s, 3600)
                    self.assertEqual(s.ship.power.e_batt_kwh, expected)
                    self.assertEqual(s.ship.power.p_gen_kw, generation)
                    self.assertEqual(s.ship.power.p_load_kw, load)
                    self.assertEqual(s.clock.t, 3600)
                    self.assertEqual(s.clock.ship_elapsed_s, 3600)

    def test_nominal_and_upgraded_cruise_positive_negative_and_balanced_power(self):
        for beta in (.5, .8):
            for generation, load in ((10, 4), (4, 10), (4, 4)):
                with self.subTest(beta=beta, generation=generation, load=load):
                    s = self.depart(beta, deepcopy(self.state))
                    s.ship.power.p_gen_base_kw = generation
                    s.ship.systems['core_os'].p_nom_kw = load
                    dt_ship = proper_time_interval(3600, beta)
                    self.engine.tick(s, 3600)
                    self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 + (generation-load)*dt_ship/3600)
                    self.assertEqual(s.ship.power.p_gen_kw, generation)
                    self.assertEqual(s.ship.power.p_load_kw, load)
                    self.assertAlmostEqual(s.clock.ship_elapsed_s, dt_ship)
                    self.assertEqual(s.clock.t, 3600)
                    self.assertEqual(s.clock.last_dt, 3600)

    def test_charge_rate_discharge_efficiency_and_capacity_limits_unchanged(self):
        s = self.depart()
        p = s.ship.power
        p.p_charge_max_kw, p.eta_charge = 2.0, .75
        self.engine.tick(s, 3600)
        self.assertAlmostEqual(p.e_batt_kwh, 60 + 2*.6*.75)
        p.p_gen_base_kw = 4
        s.ship.systems['core_os'].p_nom_kw = 10
        p.eta_discharge = .8
        before = p.e_batt_kwh
        self.engine.tick(s, 3600)
        self.assertAlmostEqual(p.e_batt_kwh, before - 6*.6/.8)
        p.p_gen_base_kw = 100
        p.e_batt_kwh = 99.99
        self.engine.tick(s, 3600)
        self.assertEqual(p.e_batt_kwh, 100)
        p.p_gen_base_kw = 0
        p.e_batt_kwh = .001
        self.engine.tick(s, 3600)
        self.assertEqual(p.e_batt_kwh, 0)

    def test_brownout_persistence_uses_onboard_seconds_and_resets(self):
        s = self.depart()
        p = s.ship.power
        p.p_gen_base_kw = 0
        p.p_discharge_max_kw = 1
        s.ship.systems['core_os'].p_nom_kw = 6
        with patch.object(self.engine, '_apply_degradation', wraps=self.engine._apply_degradation) as wear:
            self.engine.tick(s, 36)
            self.assertTrue(p.brownout)
            self.assertAlmostEqual(p.brownout_sustained_s, 21.6)
            self.assertFalse(wear.call_args.args[3])
            self.engine.tick(s, 20)
            self.assertAlmostEqual(p.brownout_sustained_s, 33.6)
            self.assertTrue(wear.call_args.args[3])
            self.assertAlmostEqual(wear.call_args.args[1], proper_time_interval(20, .8))
        p.p_gen_base_kw = 10
        self.engine.apply_action(s, SystemOn(system_id='power_core'))
        self.engine.tick(s, 1)
        self.assertFalse(p.brownout)
        self.assertEqual(p.brownout_sustained_s, 0)

    def test_low_quality_shedding_waits_for_onboard_threshold(self):
        s = self.depart()
        p = s.ship.power
        p.p_gen_base_kw, p.p_discharge_max_kw, p.e_batt_kwh = 0, 10, 20
        s.ship.systems['core_os'].p_nom_kw = 8.9
        sensors = s.ship.systems['sensors']
        sensors.p_nom_kw, sensors.priority = .1, 5
        self.engine.tick(s, 9)
        self.assertAlmostEqual(p.low_q_shed_timer_s, 5.4)
        self.assertFalse(sensors.forced_offline)
        self.engine.tick(s, 6)
        self.assertAlmostEqual(p.low_q_shed_timer_s, 9)
        self.assertFalse(sensors.forced_offline)
        events = self.engine.tick(s, 2)
        self.assertTrue(sensors.forced_offline)
        self.assertEqual(p.low_q_shed_timer_s, 0)
        self.assertTrue(any(e.data.get('cause') == 'load_shed' and e.source.id == 'sensors' for e in events))
        p.p_gen_base_kw = 10
        self.engine.tick(s, 1)
        self.assertEqual(p.low_q_shed_timer_s, 0)

    def test_arrival_mixes_transit_proper_time_and_stationary_time(self):
        s = self.depart()
        s.ship.arrival_t = s.clock.t + 30
        split = deepcopy(s)
        events = self.engine.tick(s, 100)
        self.engine.tick(split, 30)
        self.engine.tick(split, 70)
        self.assertAlmostEqual(s.clock.ship_elapsed_s, 88)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 + 6*88/3600)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, split.ship.power.e_batt_kwh)
        self.assertEqual(s.clock.t, 100)
        self.assertEqual(sum(e.type == EventType.ARRIVED for e in events), 1)
        self.assertFalse(s.ship.in_transit)

    def test_arrival_keeps_pre_and_post_job_electrical_states_separate(self):
        s = self.depart()
        s.ship.arrival_t = s.clock.t + 30
        s.ship.power.p_gen_base_kw = 5
        s.ship.cargo_modules = ['micro_reactor_patch']
        s.ship.cargo_scrap = 100
        job = Job('J1', JobType.INSTALL_MODULE, JobStatus.RUNNING, 30,
                  target=TargetRef('ship', s.ship.ship_id),
                  params={'module_id': 'micro_reactor_patch'}, power_draw_kw=2)
        s.jobs.jobs['J1'] = job
        s.jobs.active_job_ids = ['J1']
        with patch.object(self.engine, '_process_jobs', wraps=self.engine._process_jobs) as jobs, \
             patch.object(engine_module, 'run_lore_scheduler_tick', wraps=engine_module.run_lore_scheduler_tick) as lore:
            self.engine.tick(s, 100)
        self.assertEqual(jobs.call_count, 1)
        self.assertEqual(jobs.call_args.args[1], 100)
        self.assertEqual(lore.call_count, 1)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIn('micro_reactor_patch', s.ship.installed_modules)
        # Moving: generation 5, load 6, 18 onboard seconds. Rest: generation
        # 5.5, load 4, 70 onboard seconds. Final powers cannot price both legs.
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 + (-18 + 1.5*70)/3600)
        self.assertEqual(s.ship.power.p_gen_kw, 5.5)
        self.assertEqual(s.ship.power.p_load_kw, 4)

    def test_arrival_regulation_timers_also_partition_proper_and_rest_time(self):
        s = self.depart()
        s.ship.arrival_t = s.clock.t + 30
        p = s.ship.power
        p.p_gen_base_kw, p.p_discharge_max_kw = 0, 1
        s.ship.systems['core_os'].p_nom_kw = 6
        self.engine.tick(s, 100)
        self.assertAlmostEqual(p.brownout_sustained_s, 88)

    def test_exact_arrival_does_not_apply_completed_job_load_retroactively(self):
        s = self.depart()
        s.ship.arrival_t = s.clock.t + 30
        s.ship.power.p_gen_base_kw = 4
        job = Job('J1', JobType.CARGO_AUDIT, JobStatus.RUNNING, 30, power_draw_kw=2)
        s.jobs.jobs['J1'] = job
        s.jobs.active_job_ids = ['J1']
        self.engine.tick(s, 30)
        self.assertFalse(s.ship.in_transit)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 - 2*18/3600)
        self.engine.tick(s, 70)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 - 2*18/3600)

    def test_hibernation_does_not_scale_electricity_by_biological_ageing(self):
        s = self.depart()
        s.ship.is_hibernating = True
        self.engine.tick(s, 3600)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 + 6*.6)
        self.assertAlmostEqual(s.clock.ship_elapsed_s, 2160)
        self.assertAlmostEqual(s.clock.bio_elapsed_s, 2160*Balance.HIBERNATION_BIO_AGE_RATE_NOMINAL)

    def test_local_travel_uses_existing_physical_proper_time(self):
        s = self.state
        origin = s.world.space.nodes[s.world.current_node_id]
        s.world.space.nodes[self.target].x_ly = origin.x_ly + (.001 if origin.x_ly % 10 < 5 else -.001)
        s.world.fine_ranges_km[self.target] = 20_000
        self.engine.apply_action(s, Travel(node_id=self.target, no_cruise=True))
        self.assertTrue(s.ship.last_travel_is_local)
        self.engine.tick(s, 100)
        dt_ship = proper_time_interval(100, Balance.LOCAL_TRAVEL_SPEED_KM_S / engine_module.SPEED_OF_LIGHT_KM_S)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 + 6*dt_ship/3600)

    def test_constant_circuit_long_and_subdivided_intervals_agree(self):
        for generation in (4, 10):
            with self.subTest(generation=generation):
                s = self.depart(state=deepcopy(self.state))
                s.ship.power.p_gen_base_kw = generation
                s.ship.systems['core_os'].p_nom_kw = 7
                split = deepcopy(s)
                self.engine.tick(s, 3600)
                for _ in range(12):
                    self.engine.tick(split, 300)
                self.assertAlmostEqual(s.ship.power.e_batt_kwh, split.ship.power.e_batt_kwh)
                self.assertAlmostEqual(s.ship.power.power_quality, split.ship.power.power_quality)
                self.assertAlmostEqual(s.clock.ship_elapsed_s, split.clock.ship_elapsed_s)

    def test_frozen_speed_survives_engine_damage_and_nominal_reference_changes(self):
        s = self.depart()
        engines = s.ship.systems['engines']
        # Preserve this fixture's damaged-engine scenario in onboard seconds.
        engines.base_decay_per_s = .004 / proper_time_interval(1, .8)
        self.engine.tick(s, 50)
        self.assertEqual(engines.state, SystemState.DAMAGED)
        self.assertEqual(s.ship.effective_cruise_speed(), .4)
        self.assertEqual(s.ship.transit_speed_ly_per_year, .8)
        engines.base_decay_per_s = 0
        s.ship.cruise_speed_ly_per_year = .4
        self.engine.tick(s, 50)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh, 60 + 6*60/3600)
        self.assertAlmostEqual(s.clock.ship_elapsed_s, 60)

    def test_antimatter_departure_charge_and_abort_refund_rules_unchanged(self):
        self.state.ship.installed_modules = ['engine_speed_upgrade_01']
        cost = self.engine.estimate_travel_fuel(self.state, self.target)
        s = self.depart()
        fuel = s.ship.antimatter_capsules
        self.assertEqual(fuel, 12-cost)
        self.engine.tick(s, 100)
        self.assertEqual(s.ship.antimatter_capsules, fuel)
        self.engine.apply_action(s, TravelAbort())
        self.assertEqual(s.ship.antimatter_capsules, fuel)
        before = s.ship.power.e_batt_kwh
        self.engine.tick(s, 100)
        self.assertAlmostEqual(s.ship.power.e_batt_kwh - before, 6*100/3600)

    def test_new_save_load_preserves_power_timers_frozen_speed_and_continuation(self):
        s = self.depart()
        self.engine.tick(s, 50)
        s.ship.power.brownout_sustained_s = 3.25
        s.ship.power.low_q_shed_timer_s = 2.75
        with TemporaryDirectory(prefix='retorno-t04b1-') as directory:
            slot = Path(directory) / 'new.dat'
            save_single_slot(s, slot)
            loaded = load_single_slot(slot).state
        self.assertEqual(asdict(loaded.ship.power), asdict(s.ship.power))
        self.assertEqual(loaded.ship.transit_speed_ly_per_year, .8)
        self.engine.tick(s, 100)
        self.engine.tick(loaded, 100)
        self.assertEqual(asdict(loaded.ship.power), asdict(s.ship.power))
        self.assertEqual(asdict(loaded.clock), asdict(s.clock))
        self.assertEqual(loaded.ship.antimatter_capsules, s.ship.antimatter_capsules)

    def test_century_interval_does_not_create_per_second_or_extra_scheduler_ticks(self):
        s = self.depart()
        dt = 100 * Balance.YEAR_S
        s.ship.arrival_t = s.clock.t + 2*dt
        s.ship.power.p_gen_base_kw = 4
        with patch.object(self.engine, '_integrate_power_interval', wraps=self.engine._integrate_power_interval) as electricity, \
             patch.object(self.engine, '_process_jobs', wraps=self.engine._process_jobs) as jobs, \
             patch.object(engine_module, 'run_lore_scheduler_tick') as lore:
            self.engine.tick(s, dt)
        self.assertEqual(electricity.call_count, 1)
        self.assertEqual(jobs.call_count, 1)
        self.assertEqual(lore.call_count, 1)
        self.assertEqual(s.ship.power.e_batt_kwh, 60)
        self.assertTrue(math.isclose(s.clock.ship_elapsed_s, .6*dt, rel_tol=1e-12))
        self.assertEqual(s.clock.t, dt)

    def test_remaining_consumers_keep_galactic_time_while_wear_uses_arrival_segments(self):
        s = self.depart()
        s.ship.arrival_t = s.clock.t + 30
        with patch.object(self.engine, '_apply_degradation', wraps=self.engine._apply_degradation) as wear, \
             patch.object(self.engine, '_apply_hull_degradation', wraps=self.engine._apply_hull_degradation) as hull, \
             patch.object(self.engine, '_apply_radiation', wraps=self.engine._apply_radiation) as radiation, \
             patch.object(self.engine, '_update_drone_maintenance', wraps=self.engine._update_drone_maintenance) as drones, \
             patch.object(self.engine, '_apply_critical_system_consequences', wraps=self.engine._apply_critical_system_consequences) as life_support:
            self.engine.tick(s, 100)
        for consumer in (radiation, drones, life_support):
            self.assertEqual(consumer.call_count, 1)
            self.assertEqual(consumer.call_args.args[1], 100)
        for consumer in (wear, hull):
            self.assertEqual(consumer.call_count, 2)
            self.assertAlmostEqual(consumer.call_args_list[0].args[1], 18)
            self.assertEqual(consumer.call_args_list[0].kwargs['in_transit'], True)
            self.assertEqual(consumer.call_args_list[1].args[1], 70)


if __name__ == '__main__':
    unittest.main()
