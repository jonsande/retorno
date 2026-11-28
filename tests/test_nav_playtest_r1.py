"""Regressions from the first real physical-navigation playtest."""
import pickle
from unittest.mock import patch

import pytest

from retorno.cli import repl
from retorno.core.actions import Travel
from retorno.core.engine import Engine
from retorno.model.jobs import Job, JobStatus, JobType, TargetRef
from retorno.model.systems import SystemState
from retorno.runtime.loop import GameLoop, NavigationAdvanceBlocked
from tests.test_nav_public_causal import departed
from tests.test_nav_public_physical import public_game


def fractional_departure():
    game = public_game(.11)
    # The observed save started its segment at 3904.539 s. At seven days of
    # elapsed motion, absolute and segment-local sums round differently.
    game.clock.t = game.clock.ship_elapsed_s = 3904.539
    engine = Engine()
    engine.apply_action(game, Travel("NOMINAL_B"))
    return game, GameLoop(engine, game)


def test_fractional_clock_hibernation_horizon_advances_without_duplicate_effects(tmp_path):
    game, loop = fractional_departure()
    loop.advance_interval(605540)
    start_t = game.clock.t
    start_distance = game.ship.physical_transit.motion.distance_m
    start_ship_time = game.clock.ship_elapsed_s
    fuel = game.ship.antimatter_capsules
    events_before = len(game.events.recent)
    loop.advance_interval(7 * 86400)
    assert game.clock.t == pytest.approx(start_t + 7 * 86400, abs=1e-9)
    assert game.clock.ship_elapsed_s > start_ship_time
    assert game.ship.physical_transit.motion.distance_m > start_distance
    assert game.ship.physical_transit.motion.beta > 0
    assert game.ship.antimatter_capsules == fuel
    assert len(game.events.recent) == events_before
    from retorno.io.save_load import load_single_slot, save_single_slot
    path = save_single_slot(game, tmp_path / "playtest-r1.dat")
    restored = load_single_slot(path).state
    assert restored.clock.t == game.clock.t
    assert restored.ship.physical_transit.motion == game.ship.physical_transit.motion


def test_physical_tick_rolls_back_after_late_failure():
    game, _ = fractional_departure()
    owners = tuple(getattr(game, name) for name in ("ship", "world", "clock", "events", "meta"))
    before = pickle.dumps(game)
    with patch.object(Engine, "_finish_physical_transit", side_effect=RuntimeError("late failure")):
        with pytest.raises(RuntimeError, match="late failure"):
            Engine().tick(game, 1)
    assert pickle.dumps(game) == before
    assert all(getattr(game, name) is owner for name, owner in
               zip(("ship", "world", "clock", "events", "meta"), owners))


def test_rounding_tolerance_does_not_cross_a_real_job_boundary():
    game, loop = fractional_departure()
    job = Job("J-CUT", JobType.SELFTEST_REPAIR, JobStatus.RUNNING, .5,
              target=TargetRef("ship_system", "sensors"),
              params={"repair_amount": .05, "repair_scrap": 0})
    game.jobs.jobs[job.internal_id] = job
    game.jobs.active_job_ids.append(job.internal_id)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="unresolved causal boundary"):
        loop.engine.tick(game, 1.0)
    assert pickle.dumps(game) == before
    loop.advance_interval(1.0)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED


def test_nominal_public_tick_avoids_redundant_deep_copies(monkeypatch):
    import retorno.core.engine as engine_module
    game, loop = fractional_departure()
    original = engine_module.deepcopy
    copies = []

    def counted(value):
        copies.append(value)
        return original(value)

    monkeypatch.setattr(engine_module, "deepcopy", counted)
    loop.advance_interval(1)
    assert copies == []


def test_hibernation_legitimate_wake_restores_prior_auto_policy_and_job_progress(monkeypatch):
    game, loop = departed()
    support = game.ship.systems["life_support"]
    support.health = .351
    support.state = SystemState.DAMAGED
    support.base_decay_per_s = .00001
    policy = []
    monkeypatch.setattr(loop, "set_auto_tick", lambda enabled: policy.append(enabled))
    result = repl._execute_hibernate(loop, .001)
    assert result.woke_early and result.wake_reason.startswith("critical_system:")
    assert policy == [False, True]
    job = Job("J-PT001", JobType.SELFTEST_REPAIR, JobStatus.RUNNING, 1.0,
              target=TargetRef("ship_system", "sensors"),
              params={"repair_amount": .05, "repair_scrap": 0})
    game.jobs.jobs[job.internal_id] = job
    game.jobs.active_job_ids.append(job.internal_id)
    loop.advance_interval(2)
    assert game.jobs.jobs[job.internal_id].status == JobStatus.COMPLETED


def test_hibernation_unresolved_boundary_stays_paused(monkeypatch):
    game, loop = fractional_departure()
    policy = []
    monkeypatch.setattr(loop, "set_auto_tick", lambda enabled: policy.append(enabled))

    def blocked(*args, **kwargs):
        raise NavigationAdvanceBlocked("still unresolved", 0, [])

    monkeypatch.setattr(loop, "advance_interval", blocked)
    result = repl._execute_hibernate(loop, .001)
    assert result.wake_reason == "causal_boundary:still unresolved"
    assert policy == [False, False]
    assert not game.ship.is_hibernating


@pytest.mark.parametrize("previously_enabled", [True, False])
def test_normal_hibernation_preserves_prior_auto_policy(monkeypatch, previously_enabled):
    from retorno.config.balance import Balance
    game, loop = departed()
    loop._auto_tick_enabled = previously_enabled
    policy = []
    monkeypatch.setattr(loop, "set_auto_tick", lambda enabled: policy.append(enabled))
    result = repl._execute_hibernate(loop, 1.0 / Balance.YEAR_S)
    assert not result.woke_early
    assert policy == [False, previously_enabled]


def test_terminal_hibernation_does_not_restart_automatic_time(monkeypatch):
    from retorno.config.balance import Balance
    game, loop = departed()
    original_advance = loop.advance_interval

    def advance(*args, **kwargs):
        events = original_advance(*args, **kwargs)
        game.os.terminal_lock = True
        return events

    policy = []
    monkeypatch.setattr(loop, "advance_interval", advance)
    monkeypatch.setattr(loop, "set_auto_tick", lambda enabled: policy.append(enabled))
    repl._execute_hibernate(loop, 1.0 / Balance.YEAR_S)
    assert policy == [False, False]


@pytest.mark.parametrize("processing_s,expected_wait", [(.2, .8), (1.3, .05)])
def test_automatic_loop_tracks_overruns_without_skipping_time(monkeypatch, processing_s, expected_wait):
    import retorno.runtime.loop as loop_module
    game, loop = fractional_departure()
    loop.tick_s = 1.0
    simulated = [0.0]
    waits = []
    count = [0]

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, delay):
            waits.append(delay)
            simulated[0] += delay
            return self.stopped

        def set(self):
            self.stopped = True

    loop._stop = Stop()
    monkeypatch.setattr(loop_module.time, "monotonic", lambda: simulated[0])
    initial_t = game.clock.t

    def advance(*args, **kwargs):
        simulated[0] += processing_s
        game.clock.t += args[0]
        count[0] += 1
        if count[0] == 3:
            loop._stop.set()
        return []

    monkeypatch.setattr(loop, "advance_interval", advance)
    loop._run()
    assert waits[:2] == pytest.approx([1.0, expected_wait])
    assert count[0] == 3
    assert game.clock.t - initial_t == pytest.approx(3.0)
