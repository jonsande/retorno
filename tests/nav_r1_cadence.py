"""Measure actual automatic tick start intervals on a copy of a save."""
import argparse
import json
import statistics
import threading
import time

from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot
from retorno.runtime.loop import GameLoop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", required=True)
    parser.add_argument("--ticks", type=int, default=5)
    args = parser.parse_args()
    state = load_single_slot(args.save).state
    loop = GameLoop(Engine(), state, tick_s=1.0)
    original = loop.advance_interval
    starts = []
    finished = threading.Event()

    def timed(*call_args, **call_kwargs):
        starts.append(time.monotonic())
        events = original(*call_args, **call_kwargs)
        if len(starts) == args.ticks:
            finished.set()
        return events

    loop.advance_interval = timed
    loop.start()
    try:
        if not finished.wait(timeout=20):
            raise RuntimeError("automatic cadence sample did not finish")
    finally:
        loop.stop()
    intervals = [right - left for left, right in zip(starts, starts[1:])]
    print(json.dumps({"ticks": len(starts), "intervals_s": intervals,
                      "median_interval_s": statistics.median(intervals),
                      "galactic_advance_s": state.clock.t - load_single_slot(args.save).state.clock.t},
                     indent=2))


if __name__ == "__main__":
    main()
