"""T-04B2: ship-system/hull ageing, sampled conditions and inertial travel."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core import engine as engine_module
from retorno.core.actions import Travel, TravelAbort
from retorno.core.engine import Engine
from retorno.core.temporal import proper_time_interval
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneLocation, DroneState, DroneStatus
from retorno.model.events import EventType
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, add_known_link


class WearProperTimeTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.state = create_initial_state_sandbox(seed=29)
        self.state.ship.drones.clear()
        self.default_rates = {sid: system.base_decay_per_s for sid, system in self.state.ship.systems.items()}
        for system in self.state.ship.systems.values():
            system.state, system.health, system.forced_offline = SystemState.NOMINAL, 1.0, False
            system.p_nom_kw = system.base_decay_per_s = system.k_power = system.k_rad = 0.0
        p = self.state.ship.power
        p.p_gen_kw = p.p_gen_base_kw = 10
        p.p_gen_bonus_kw = p.quality_offset = 0
        p.e_batt_kwh = p.e_batt_max_kwh = 100
        p.p_charge_max_kw = p.p_discharge_max_kw = 20
        self.state.ship.docked_node_id = None
        origin = self.state.world.space.nodes[self.state.world.current_node_id]
        origin.radiation_rad_per_s = 0
        self.target = 'WEAR_TEST'
        self.state.world.space.nodes[self.target] = SpaceNode(
            self.target, self.target, 'station', x_ly=origin.x_ly + 4,
            y_ly=origin.y_ly, z_ly=origin.z_ly, radiation_rad_per_s=0)
        self.state.world.known_nodes.add(self.target)
        add_known_link(self.state.world, origin.node_id, self.target, bidirectional=True)

    def transit(self, beta=.8, mode='CRUISE', remaining=10000, state=None):
        s = state or self.state
        s.ship.in_transit = True
        s.ship.transit_from = s.world.current_node_id
        s.ship.transit_to = self.target
        s.ship.transit_start_t = s.clock.t
        s.ship.arrival_t = s.clock.t + remaining
        s.ship.transit_speed_ly_per_year = beta
        s.ship.op_mode = mode
        return s

    def test_rest_preserves_previous_rates_and_stationary_cruise_behavior(self):
        for mode in ('NORMAL', 'CRUISE'):
            with self.subTest(mode=mode):
                s = deepcopy(self.state)
                s.ship.op_mode = mode
                for sid in ('engines', 'core_os', 'sensors'):
                    s.ship.systems[sid].base_decay_per_s = self.default_rates[sid]
                self.engine.tick(s, 10000)
                for sid in ('engines', 'core_os', 'sensors'):
                    self.assertAlmostEqual(s.ship.systems[sid].health, 1-self.default_rates[sid]*10000, places=14)
                self.assertAlmostEqual(s.ship.hull_integrity, 1-Balance.HULL_BASE_DECAY_PER_S*10000, places=14)
                self.assertEqual(s.clock.ship_elapsed_s, 10000)

    def test_frozen_03_05_08_speeds_scale_systems_and_hull_once(self):
        for beta in (.3, .5, .8):
            for mode in ('NORMAL', 'CRUISE'):
                with self.subTest(beta=beta, mode=mode):
                    s = self.transit(beta, mode, state=deepcopy(self.state))
                    dt_ship = proper_time_interval(1000, beta)
                    for sid in ('engines', 'core_os', 'sensors'):
                        s.ship.systems[sid].base_decay_per_s = self.default_rates[sid]
                    self.engine.tick(s, 1000)
                    modifier = Balance.TRANSIT_WEAR_MULT_NORMAL if mode == 'NORMAL' else 1
                    for sid in ('engines', 'core_os', 'sensors'):
                        self.assertAlmostEqual(s.ship.systems[sid].health, 1-self.default_rates[sid]*modifier*dt_ship, places=14)
                    self.assertAlmostEqual(s.ship.hull_integrity, 1-Balance.HULL_BASE_DECAY_PER_S*Balance.HULL_TRANSIT_DECAY_MULT*dt_ship, places=14)
                    self.assertEqual(s.clock.t, 1000)

    def test_quality_brownout_radiation_and_mode_modifiers_are_retained(self):
        s = self.transit(mode='NORMAL')
        for sid in ('power_core', 'energy_distribution', 'sensors'):
            system = s.ship.systems[sid]
            system.base_decay_per_s, system.k_power, system.k_rad = .0001, .3, .4
        s.ship.power.p_gen_base_kw = 0
        s.ship.power.p_discharge_max_kw = 1
        s.ship.systems['core_os'].p_nom_kw = 6
        # Keep this wear test's reactor available while exercising real brownout.
        s.ship.systems['power_core'].priority = 1
        env = Balance.HULL_RAD_REF
        s.world.space.nodes[s.ship.transit_from].radiation_rad_per_s = env
        s.world.space.nodes[self.target].radiation_rad_per_s = env
        internal = self.engine._compute_internal_radiation_rad_per_s(s, env)
        self.engine.tick(s, 100)
        self.assertTrue(s.ship.power.brownout)
        self.assertGreater(s.ship.power.brownout_sustained_s, Balance.BROWNOUT_SUSTAINED_AFTER_S)
        q = s.ship.power.power_quality
        base_factor = 1 + .3*(1-q) + .4*min(1, internal/Balance.R_REF)
        for sid, brown_mult in (('power_core', Balance.BROWNOUT_DEGRADE_MULT_POWER_CORE),
                                ('energy_distribution', Balance.BROWNOUT_DEGRADE_MULT_DISTRIBUTION), ('sensors', 1)):
            expected = 1 - .0001*base_factor*brown_mult*Balance.TRANSIT_WEAR_MULT_NORMAL*proper_time_interval(100, .8)
            self.assertAlmostEqual(s.ship.systems[sid].health, expected)
        expected_hull = 1 - Balance.HULL_BASE_DECAY_PER_S*Balance.HULL_RAD_DECAY_MULT_MAX*Balance.HULL_TRANSIT_DECAY_MULT*proper_time_interval(100, .8)
        self.assertAlmostEqual(s.ship.hull_integrity, expected_hull)

    def test_arrival_crossing_and_exact_boundary_preserve_transit_modifiers(self):
        for duration in (30, 100):
            for mode in ('NORMAL', 'CRUISE'):
                with self.subTest(duration=duration, mode=mode):
                    s = self.transit(mode=mode, remaining=30, state=deepcopy(self.state))
                    s.ship.systems['sensors'].base_decay_per_s = .0001
                    moving = proper_time_interval(30, .8)
                    stationary = duration-30
                    modifier = Balance.TRANSIT_WEAR_MULT_NORMAL if mode == 'NORMAL' else 1
                    events = self.engine.tick(s, duration)
                    self.assertAlmostEqual(s.ship.systems['sensors'].health, 1-.0001*(modifier*moving+stationary))
                    self.assertAlmostEqual(s.ship.hull_integrity, 1-Balance.HULL_BASE_DECAY_PER_S*(Balance.HULL_TRANSIT_DECAY_MULT*moving+stationary))
                    self.assertFalse(s.ship.in_transit)
                    self.assertEqual(sum(e.type == EventType.ARRIVED for e in events), 1)

    def test_arrival_uses_each_electrical_sample_without_rerunning_electricity(self):
        s = self.transit(remaining=30)
        target = s.ship.systems['sensors']
        target.base_decay_per_s, target.k_power = .001, .5
        # Sampling policy test: a pre-arrival interval under sustained brownout,
        # then healthy power after arrival. No new electrical rule is introduced.
        samples = []
        original = self.engine._integrate_power_interval

        def electrical_segment(state, dt_ship):
            events = original(state, dt_ship)
            moving = state.ship.in_transit
            p = state.ship.power
            p.power_quality = .2 if moving else .9
            p.brownout = moving
            p.brownout_sustained_s = 40 if moving else 0
            samples.append(dt_ship)
            return events

        # Distribution has a distinct brownout modifier; the unrelated sensor
        # keeps only the quality modifier. Both use their segment's snapshot.
        distribution = s.ship.systems['energy_distribution']
        distribution.base_decay_per_s, distribution.k_power = .001, .5
        with patch.object(self.engine, '_integrate_power_interval', side_effect=electrical_segment):
            self.engine.tick(s, 100)
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(samples[0], 18)
        self.assertEqual(samples[1], 70)
        self.assertAlmostEqual(target.health, 1-.001*(18*1.4+70*1.05))
        self.assertAlmostEqual(distribution.health, 1-.001*(18*1.4*Balance.BROWNOUT_DEGRADE_MULT_DISTRIBUTION+70*1.05))

    def test_stable_long_and_subdivided_intervals_including_arrival_agree(self):
        for mode in ('NORMAL', 'CRUISE'):
            for arrival in (300, 3000):
                with self.subTest(mode=mode, arrival=arrival):
                    s = self.transit(mode=mode, remaining=arrival, state=deepcopy(self.state))
                    s.ship.systems['engines'].base_decay_per_s = .00001
                    split = deepcopy(s)
                    self.engine.tick(s, 1000)
                    for _ in range(10):
                        self.engine.tick(split, 100)
                    self.assertAlmostEqual(s.ship.systems['engines'].health, split.ship.systems['engines'].health)
                    self.assertAlmostEqual(s.ship.hull_integrity, split.ship.hull_integrity)
                    self.assertAlmostEqual(s.clock.ship_elapsed_s, split.clock.ship_elapsed_s)
                    self.assertAlmostEqual(s.ship.power.e_batt_kwh, split.ship.power.e_batt_kwh)

    def test_engine_transitions_do_not_change_frozen_speed_eta_or_proper_time(self):
        s = self.transit(remaining=1000)
        engines = s.ship.systems['engines']
        engines.health, engines.base_decay_per_s = .9, .01
        s.ship.installed_modules = ['engine_speed_upgrade_01']
        self.engine._apply_health_state(engines, s, [], cause='module_install')
        arrival, fuel = s.ship.arrival_t, s.ship.antimatter_capsules
        elapsed = 0
        for dt, expected in ((30, SystemState.LIMITED), (30, SystemState.DAMAGED), (40, SystemState.CRITICAL)):
            elapsed += dt
            events = self.engine.tick(s, dt)
            self.assertEqual(engines.state, expected)
            self.assertTrue(any(e.type == EventType.SYSTEM_STATE_CHANGED and e.source.id == 'engines' for e in events))
            self.assertEqual(s.ship.transit_speed_ly_per_year, .8)
            self.assertEqual(s.ship.arrival_t, arrival)
            self.assertEqual(s.ship.arrival_t-s.clock.t, 1000-elapsed)
            self.assertEqual(s.ship.antimatter_capsules, fuel)
        self.assertAlmostEqual(s.clock.ship_elapsed_s, 60)
        self.engine.apply_action(s, TravelAbort())
        events = self.engine.apply_action(s, Travel(node_id=self.target))
        self.assertEqual(events[0].data['reason'], 'engines_unavailable')

    def test_radiation_dose_drones_jobs_and_life_support_keep_galactic_time(self):
        s = self.transit(remaining=30)
        s.world.space.nodes[s.ship.transit_from].radiation_rad_per_s = .002
        s.world.space.nodes[self.target].radiation_rad_per_s = .002
        drone = DroneState('D9', 'D9', DroneStatus.DEPLOYED,
                           DroneLocation('ship_sector', 'ENG-R1'), autorecall_enabled=False, shield_factor=.5)
        s.ship.drones['D9'] = drone
        with patch.object(self.engine, '_process_jobs', wraps=self.engine._process_jobs) as jobs, \
             patch.object(engine_module, 'run_lore_scheduler_tick', wraps=engine_module.run_lore_scheduler_tick) as lore, \
             patch.object(engine_module, 'ensure_exploration_recovery', wraps=engine_module.ensure_exploration_recovery) as recovery, \
             patch.object(engine_module, 'retry_radio_opportunities', wraps=engine_module.retry_radio_opportunities) as radio, \
             patch.object(self.engine, '_apply_radiation', wraps=self.engine._apply_radiation) as radiation, \
             patch.object(self.engine, '_update_drone_maintenance', wraps=self.engine._update_drone_maintenance) as maintenance, \
             patch.object(self.engine, '_apply_critical_system_consequences', wraps=self.engine._apply_critical_system_consequences) as life_support:
            self.engine.tick(s, 100)
        for consumer in (jobs, radiation, maintenance, life_support):
            self.assertEqual(consumer.call_count, 1)
            self.assertEqual(consumer.call_args.args[1], 100)
        for consumer in (lore, recovery, radio):
            self.assertEqual(consumer.call_count, 1)
        self.assertAlmostEqual(drone.dose_rad, .002*.5*100)
        self.assertAlmostEqual(drone.battery, 1-Balance.DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S*100)

    def test_arrival_radiation_remains_endpoint_sample_not_trajectory_integral(self):
        s = self.transit(remaining=30)
        s.world.space.nodes[s.ship.transit_from].radiation_rad_per_s = 0
        s.world.space.nodes[self.target].radiation_rad_per_s = Balance.HULL_RAD_REF
        with patch.object(self.engine, '_apply_hull_degradation', wraps=self.engine._apply_hull_degradation) as hull:
            self.engine.tick(s, 100)
        self.assertEqual(hull.call_count, 2)
        for call in hull.call_args_list:
            self.assertEqual(call.args[2], Balance.HULL_RAD_REF)
        expected = 1-Balance.HULL_BASE_DECAY_PER_S*Balance.HULL_RAD_DECAY_MULT_MAX*(18*Balance.HULL_TRANSIT_DECAY_MULT+70)
        self.assertAlmostEqual(s.ship.hull_integrity, expected)

    def test_hibernation_keeps_hull_modifier_without_biological_scaling(self):
        s = self.transit(remaining=30)
        s.ship.is_hibernating = True
        s.ship.systems['engines'].base_decay_per_s = .001
        self.engine.tick(s, 100)
        self.assertAlmostEqual(s.ship.systems['engines'].health, 1-.001*88)
        self.assertAlmostEqual(s.ship.hull_integrity, 1-Balance.HULL_BASE_DECAY_PER_S*Balance.HULL_TRANSIT_DECAY_MULT*88)
        self.assertAlmostEqual(s.clock.bio_elapsed_s, 88*Balance.HIBERNATION_BIO_AGE_RATE_NOMINAL)

    def test_instantaneous_hull_damage_is_not_scaled_by_cruise_speed(self):
        s = self.transit()
        self.engine._damage_hull(s, .2)
        self.assertAlmostEqual(s.ship.hull_integrity, .8)
        self.assertEqual(s.clock.t, 0)

    def test_save_load_continues_wear_with_frozen_speed(self):
        s = self.transit()
        s.ship.systems['engines'].base_decay_per_s = .001
        self.engine.tick(s, 100)
        with TemporaryDirectory(prefix='retorno-t04b2-') as directory:
            slot = Path(directory)/'new.dat'
            save_single_slot(s, slot)
            loaded = load_single_slot(slot).state
        self.engine.tick(s, 100)
        self.engine.tick(loaded, 100)
        self.assertEqual(asdict(s.ship.systems['engines']), asdict(loaded.ship.systems['engines']))
        self.assertEqual(s.ship.hull_integrity, loaded.ship.hull_integrity)
        self.assertEqual(asdict(s.clock), asdict(loaded.clock))

    def test_wear_keeps_existing_electrical_sampling_stage(self):
        s = self.transit(remaining=30)
        core = s.ship.systems['power_core']
        core.base_decay_per_s = .003
        # T-04B1 samples both electrical segments before the existing wear stage.
        # A wear-induced reactor derating is visible to the following tick.
        self.engine.tick(s, 100)
        self.assertEqual(core.state, SystemState.LIMITED)
        self.assertEqual(s.ship.power.p_gen_kw, 10)
        self.engine.tick(s, 1)
        self.assertEqual(s.ship.power.p_gen_kw, 10*Balance.POWER_CORE_MULT_LIMITED)


if __name__ == '__main__':
    unittest.main()
