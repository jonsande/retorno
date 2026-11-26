"""Reproducible PT001-01 timing against a copy of the real playtest save.

Run with PYTHONPATH=src or with PYTHONPATH pointing at an extracted HEAD tree.
The source save is loaded afresh for each sample and is never written.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

import retorno.core.engine as engine_module
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot
from retorno.runtime.loop import GameLoop


class TimedLock:
    def __init__(self, underlying):
        self.underlying = underlying
        self.started = None
        self.held_s = 0.0

    def acquire(self, *args, **kwargs):
        acquired = self.underlying.acquire(*args, **kwargs)
        if acquired:
            self.started = time.perf_counter()
        return acquired

    def release(self):
        self.held_s += time.perf_counter() - self.started
        self.started = None
        self.underlying.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    original_deepcopy = engine_module.deepcopy
    measures = {name: [] for name in ("rest_tick_s", "physical_forecast_s",
                                    "physical_tick_s", "physical_advance_s",
                                    "physical_lock_held_s", "deepcopy_count",
                                    "deepcopy_total_s", "boundary_selection_s")}
    for _ in range(args.repeats):
        state = load_single_slot(args.save).state
        state.ship.physical_transit = None
        state.ship.transit_from = state.ship.transit_to = None
        start = time.perf_counter()
        Engine().tick(state, 1.0)
        measures["rest_tick_s"].append(time.perf_counter() - start)

        state = load_single_slot(args.save).state
        engine = Engine()
        start = time.perf_counter()
        engine.next_physical_step(state, 1.0)
        measures["physical_forecast_s"].append(time.perf_counter() - start)

        state = load_single_slot(args.save).state
        start = time.perf_counter()
        engine.tick(state, 1.0)
        measures["physical_tick_s"].append(time.perf_counter() - start)

        state = load_single_slot(args.save).state
        loop = GameLoop(Engine(), state)
        lock = TimedLock(loop._lock)
        loop._lock = lock
        copies = []
        boundaries = []
        original_selection = Engine._physical_limit_selection

        def timed_copy(value):
            copy_start = time.perf_counter()
            try:
                return original_deepcopy(value)
            finally:
                copies.append(time.perf_counter() - copy_start)

        def timed_selection(self, value, horizon):
            select_start = time.perf_counter()
            try:
                return original_selection(self, value, horizon)
            finally:
                boundaries.append(time.perf_counter() - select_start)

        engine_module.deepcopy = timed_copy
        Engine._physical_limit_selection = timed_selection
        try:
            start = time.perf_counter()
            loop.advance_interval(1.0)
            measures["physical_advance_s"].append(time.perf_counter() - start)
        finally:
            engine_module.deepcopy = original_deepcopy
            Engine._physical_limit_selection = original_selection
        measures["physical_lock_held_s"].append(lock.held_s)
        measures["deepcopy_count"].append(len(copies))
        measures["deepcopy_total_s"].append(sum(copies))
        measures["boundary_selection_s"].append(sum(boundaries))
    print(json.dumps({"save": args.save, "repeats": args.repeats,
                      "median": {key: statistics.median(values) for key, values in measures.items()},
                      "samples": measures}, indent=2))


if __name__ == "__main__":
    main()
