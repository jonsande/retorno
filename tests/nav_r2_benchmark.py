"""Read-only R2 playtest benchmark; all advances operate on private clones."""
from __future__ import annotations

import argparse
import cProfile
import json
import os
import pickle
import pstats
import statistics
import time

from retorno.cli import repl
from retorno.ui_textual import presenter
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot
from retorno.runtime.loop import GameLoop
from tests.nav_r1_benchmark import TimedLock


class MeasuredLock(TimedLock):
    def __init__(self, underlying):
        super().__init__(underlying)
        self.wait_s = 0.0

    def acquire(self, *args, **kwargs):
        start = time.perf_counter()
        acquired = super().acquire(*args, **kwargs)
        if acquired:
            self.wait_s += time.perf_counter() - start
        return acquired


def distribution(values):
    ordered = sorted(values)
    return {
        "median": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, int(.95 * len(ordered)))],
        "max": ordered[-1], "samples": values,
    }


def fresh(state):
    return pickle.loads(pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL))


def timed(operation):
    start = time.perf_counter()
    operation()
    return time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", required=True)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--hibernate", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")

    load_start = time.perf_counter()
    state = load_single_slot(args.save).state
    load_s = time.perf_counter() - load_start
    values = {key: [] for key in ("rest_tick", "physical_forecast", "physical_tick",
                                  "physical_advance", "physical_lock_held",
                                  "physical_lock_wait",
                                  "presentation_access", "state_clone")}
    for _ in range(args.samples):
        values["state_clone"].append(timed(lambda: fresh(state)))
        rest = fresh(state)
        rest.ship.physical_transit = None
        rest.ship.transit_from = rest.ship.transit_to = None
        values["rest_tick"].append(timed(lambda: Engine().tick(rest, 1.0)))
        physical = fresh(state)
        values["physical_forecast"].append(timed(
            lambda: Engine().next_physical_step(physical, 1.0)))
        physical = fresh(state)
        engine = Engine()
        causal_step = engine.next_physical_step(physical, 1.0)
        values["physical_tick"].append(timed(
            lambda: engine.tick(physical, causal_step)))
        physical = fresh(state)
        loop = GameLoop(Engine(), physical)
        lock = MeasuredLock(loop._lock)
        loop._lock = lock
        values["physical_advance"].append(timed(lambda: loop.advance_interval(1.0)))
        values["physical_lock_held"].append(lock.held_s)
        values["physical_lock_wait"].append(lock.wait_s)
        def present():
            presenter.build_header(state)
            presenter.build_status_lines(state)
            presenter.build_alerts_lines(state)
            presenter.build_jobs_lines(state)
            presenter.build_power_lines(state)
        values["presentation_access"].append(timed(present))

    sample = fresh(state)
    profile = cProfile.Profile()
    profile.enable()
    GameLoop(Engine(), sample).advance_interval(604800.0)
    profile.disable()
    stats = pstats.Stats(profile).stats
    selected = []
    names = ("_pickle.dumps", "_pickle.loads", "_physical_limit_selection",
             "first_integrated_wear_at", "integrate_segment_radiation",
             "_integrate_power_interval", "_begin_job_interval",
             "run_lore_scheduler_tick", "retry_radio_opportunities",
             "advance_recovery_plans", "_commit_physical_state")
    for (filename, lineno, func), (_, calls, own, cumulative, _) in stats.items():
        if any(name in func for name in names):
            selected.append({"function": func, "file": os.path.basename(filename),
                             "calls": calls, "own_s": own, "cumulative_s": cumulative})
    result = {
        "save": os.path.basename(args.save), "save_bytes": os.path.getsize(args.save),
        "state_pickle_bytes": len(pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)),
        "world_nodes": len(state.world.space.nodes),
        "known_nodes": len(state.world.known_nodes),
        "jobs": len(state.jobs.jobs),
        "radio_opportunities": len(state.world.radio_opportunities),
        "load_s": load_s,
        "latencies_s": {key: distribution(samples) for key, samples in values.items()},
        "profile_week_s": sum(entry.inlinetime for entry in profile.getstats()),
        "profile_components": sorted(selected, key=lambda row: -row["cumulative_s"]),
    }
    if args.hibernate:
        sample = fresh(state)
        loop = GameLoop(Engine(), sample)
        loop._auto_tick_enabled = False
        calls = [0]
        ticks = [0]
        original_advance = loop.advance_interval
        original_tick = loop.engine.tick
        def advance(*a, **kw):
            calls[0] += 1
            return original_advance(*a, **kw)
        def tick(*a, **kw):
            ticks[0] += 1
            return original_tick(*a, **kw)
        loop.advance_interval = advance
        loop.engine.tick = tick
        began = time.perf_counter()
        outcome = repl._execute_hibernate(loop, 60, until_arrival=True)
        result["hibernate"] = {
            "processing_s": time.perf_counter() - began,
            "outer_blocks": calls[0], "causal_ticks": ticks[0],
            "wake_reason": outcome.wake_reason,
            "arrived": sample.ship.physical_transit is None,
            "clock_t": sample.clock.t,
            "ship_time_s": sample.clock.ship_elapsed_s,
            "fuel": sample.ship.antimatter_capsules,
        }
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
