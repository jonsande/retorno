"""Numerical and runtime regressions from the second real playtest."""
from __future__ import annotations

import math
from pathlib import Path
import pickle

import pytest

from retorno.cli import repl
from retorno.config.balance import Balance
from retorno.core.engine import Engine
from retorno.core.nav_boundaries import TemporalLimit
from retorno.core.nav_coordinator import select_next_boundary
from retorno.core.nav_physics import (
    MotionSegment, MotionState, proper_time_between_segment, sample_segment,
)
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.runtime.loop import GameLoop
from tests.test_nav_playtest_r1 import fractional_departure


@pytest.mark.parametrize("absolute", [1.68e9, 6.3e9])
def test_sub_ulp_proper_boundary_uses_local_motion_and_advances_both_clocks(absolute):
    segment = MotionSegment(MotionState(absolute, 0, .5, absolute * .87),
                            0, 1.2e9, .5)
    local = 6.7e8
    now = sample_segment(segment, local)
    tiny = math.ulp(now.galactic_s) / 4
    cut = select_next_boundary(
        segment, now.galactic_s, 1.0,
        proper_limits=(TemporalLimit("test_cut", "proper", tiny),),
        elapsed_segment_s=local)
    assert cut.advance_galactic_s > 0
    end = sample_segment(segment, local + cut.advance_galactic_s)
    assert end.galactic_s > now.galactic_s
    assert end.proper_s > now.proper_s


def test_proper_duration_between_large_local_clocks_does_not_cancel():
    segment = MotionSegment(MotionState(1e9, 0, .5, 8e8), 0, 1.2e9, .5)
    left = 6.7e8
    right = math.nextafter(left, math.inf)
    assert proper_time_between_segment(segment, left, right) > 0


def test_unexpected_auto_exception_is_visible_and_pauses_thread(monkeypatch):
    _, loop = fractional_departure()

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _):
            return self.stopped

        def set(self):
            self.stopped = True

    loop._stop = Stop()
    monkeypatch.setattr(loop, "advance_interval", lambda *_: (_ for _ in ()).throw(
        RuntimeError("unexpected numerical failure")))
    loop._run()
    assert not loop._auto_tick_enabled
    assert loop.last_auto_error == "RuntimeError: unexpected numerical failure"
    events = loop.drain_events()
    assert events[-1][1].data["reason"] == "automatic_internal_error"
    assert "unexpected numerical failure" in events[-1][1].data["detail"]


@pytest.mark.parametrize("name", ["PT001-04-clock-resolution.dat",
                                  "PT001-05-proper-limit.dat"])
def test_real_playtest_save_reaches_arrival_and_roundtrips(tmp_path, name):
    original = Path(__file__).resolve().parents[2] / name
    if not original.exists():
        pytest.skip("real playtest evidence is external to the repository")
    state = load_single_slot(original).state
    before_fuel = state.ship.antimatter_capsules
    loop = GameLoop(Engine(), state)
    loop._auto_tick_enabled = False
    result = repl._execute_hibernate(loop, 60, until_arrival=True)
    assert result.wake_reason is None
    assert state.ship.physical_transit is None
    assert state.ship.antimatter_capsules == before_fuel
    restored = load_single_slot(save_single_slot(state, tmp_path / name)).state
    assert restored.clock == state.clock
    assert restored.ship == state.ship


def test_transaction_keeps_owners_and_rolls_back_with_pickle_clone(monkeypatch):
    game, _ = fractional_departure()
    owners = tuple(getattr(game, key) for key in ("ship", "world", "clock", "events"))
    before = pickle.dumps(game)
    monkeypatch.setattr(Engine, "_finish_physical_transit", lambda *_: (_ for _ in ()).throw(
        RuntimeError("late failure")))
    with pytest.raises(RuntimeError, match="late failure"):
        Engine().tick(game, 1.0)
    assert pickle.dumps(game) == before
    assert owners == tuple(getattr(game, key) for key in ("ship", "world", "clock", "events"))
