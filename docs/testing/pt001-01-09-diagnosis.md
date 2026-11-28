# PT001-01/09-A — residual lag and clock cadence diagnosis

Date: 2026-11-28. Code: `a7b0ad5977b1474ac2f48e3599bdf3c878a7890b`.
This is a diagnosis and a proposal, not a change to timekeeping or navigation.

## Reproduction and measurement

The project Python ran a short private probe using `GameLoop`, the existing
`MeasuredLock` profiler, and a headless `RetornoTextualApp.run_test()` session.
The probe was kept outside the repository at `/tmp/pt001_01_09_diag.py`; its
raw output is `/tmp/pt001_01_09_diag.out`. Synthetic states used
`tests/test_nav_public_physical.py::public_game(.11)`, speed 0.1 c, with a
three-segment nominal route. Cruise and braking snapshots were prepared by
advancing private clones to 100 s into each segment (0.15/0.17 s wall time).
Each engine sample used three separate clones and a 1 s advance. Each automatic
sample measured four ticks at a 1 s period and polled the nonblocking state
lock about every 20 ms. Headless Textual sampled each synthetic phase for
about 2.9 s, with normal 250 ms panel refreshes, audio disabled, and a `status`
input. No long hibernation was run. The Textual input number includes test
driver dispatch and is a response-latency proxy, not a hardware keypress
measurement.

The real PT001-04 and PT001-05 saves were loaded into memory only, for the same
short probes. Both begin in nominal cruise at beta 0.5. SHA-256 checksums of
the original files remain respectively
`b5cca22d6cdb956d84d608af2fd3c45b9d6792b035336862fcdc49510458f8c4`
and `639f354b43ee81f4dbed378cb4615fe22111b8a61b9ba5c3c64b0ffa3896103a`.
The headless app used only temporary save slots.

| State | Separate 1 s advance median | Auto tick median / max | Tick start gaps | Galactic / proper advance in auto sample | Wall sample | Busy lock polls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Synthetic rest | 0.242 s | 0.004 / 0.279 s | 1.000 ± 0.0001 s | 4.000 / 4.000 s | 4.016 s | 11/196 |
| Synthetic acceleration | 0.124 s | 0.032 / 0.215 s | 0.999–1.000 s | 4.000 / 4.000 s | 4.056 s | 11/197 |
| Synthetic cruise | 0.0066 s | 0.029 / 0.045 s | 1.000 ± 0.0001 s | 4.000 / 3.980 s | 4.041 s | 4/198 |
| Synthetic braking | 0.015 s | 0.038 / 0.045 s | 1.000 ± 0.0001 s | 4.000 / 3.980 s | 4.059 s | 5/199 |
| PT001-04 cruise | 0.047 s | 0.088 / 0.143 s | 1.000 ± 0.0002 s | 4.000 / 3.464 s | 4.094 s | 15/198 |
| PT001-05 cruise | 0.241 s | 0.136 / 0.360 s | 1.000 ± 0.0002 s | 4.000 / 3.464 s | 4.110 s | 27/196 |

The first automatic tick can cost much more than later ticks in the same state;
the separate-clone medians intentionally include that cold state. These short
samples therefore describe local cost, not a guaranteed long-run rate. The
lock was held for 0.290/0.291/0.122/0.139 s over the four synthetic samples
in table order, and 0.405/0.738 s for PT001-04/05; total acquisition wait was
0.004–0.006 s per sample. The busy-poll counts show how often a nonblocking UI
read would skip a busy frame. No automatic error or missed deadline was seen
in these six samples.

| Headless Textual state | Refresh calls / median / max gap | Header changes | Busy lock reads | `status` response proxy |
| --- | ---: | ---: | ---: | ---: |
| Rest | 12 / 0.251 / 0.255 s | 2 | 0 | 0.135 s |
| Acceleration | 12 / 0.250 / 0.259 s | 2 | 2 | 0.195 s |
| Cruise | 12 / 0.251 / 0.255 s | 2 | 2 | 0.133 s |
| Braking | 12 / 0.250 / 0.260 s | 2 | 2 | 0.186 s |
| PT001-04 cruise | 12 / 0.250 / 0.258 s | 2 | 2 | 0.190 s |
| PT001-05 cruise | 12 / 0.251 / 0.255 s | 2 | 2 | 0.139 s |

Each Textual window contains two completed game ticks; its roughly 2.9 s wall
duration includes a partial scheduler period at each end. A naive ratio of
`2 game seconds / 2.9 wall seconds` would falsely imply lost time. Tick-start
intervals, not this partial-window ratio, are the cadence evidence. The panel
timer remained regular in these headless runs. Actual terminal rendering and
audio latency were not measured.

## Findings and limits

**Confirmed scheduler defect under overload.** `GameLoop._run()` adds exactly
`tick_s` to simulation per successful iteration, then moves an overdue
deadline ahead to the next future slot without accounting for skipped slots.
An isolated control added 1.25 s of artificial work per iteration to a rest
state. Four automatic ticks then took **8.259 s wall time**, advanced both
clocks only **4.000 s**, and began **2.000 s** apart: at least three scheduled
slots between observed starts were skipped. This proves accumulated simulation
time can lag wall time when ticks miss deadlines. The six ordinary short
samples did **not** encounter that overload; it remains unverified whether it
caused the specific reported cruise episode.

**Confirmed engine and lock cost, not a universal cruise slowdown.** The real
PT001-05 first-second state is heavier than PT001-04 and the quiet synthetic
cruise. A one-second PT001-05 `cProfile` run took 0.469 s instrumented, made
two causal engine ticks, and attributed 0.368 s cumulative to radio opportunity
discovery (overlapping nested calls). This agrees with the earlier R2 profile.
Long lock occupancy can suppress a panel refresh or delay a command that
acquires the lock. It did not exceed the one-second automatic budget in these
measurements. The 250 ms Textual timer and nonblocking skip prevent the event
loop from waiting for the engine merely to paint a panel; they cannot guarantee
that every refresh contains a new clock value.

**Confirmed visual quantization.** The public header uses `int(seconds)` for
all three clocks. In beta-0.5 cruise, proper time gains about 0.866 s per
galactic tick, so its displayed seconds must occasionally repeat. On the
PT001-04 starting value, nine consecutive readouts (initial plus eight ideal
one-second ticks) display ship seconds
`14, 15, 16, 17, 18, 18, 19, 20, 21`. This is physically correct proper time,
not lost galactic time. Galactic seconds should change once per successful
one-second tick; any longer real-time hold requires a missed tick, stalled
engine/UI, pause, or another cause. This short headless probe did not reproduce
the player's reported irregular galactic cadence.

Other possible contributors (terminal rendering, audio, host scheduling, and
later changing playtest state) remain hypotheses. These samples cannot assign
their shares or establish sustained real-time performance.

## Bounded proposal for PT001-01/09-B

1. Add focused scheduler tests with a controlled slow advance, stop/restart,
   debug pause, and a causal boundary. Track monotonic elapsed time and pending
   simulation debt explicitly. Do not silently discard overdue time; process
   bounded catch-up work with yields so Textual remains responsive, and make
   pause/close behavior for pending debt explicit. Preserve atomic physical
   advances and existing failure reporting.
2. Expose a small debug-only timing probe or reuse the profiling hooks to
   compare scheduled slots, completed simulation seconds, lock occupancy,
   skipped panel reads, and input latency on a private copy of the player's
   current cruise save. Do not expose hidden world data in normal UI.
3. Check the visible clock cadence against the continuous stored clocks and
   decide whether a presentation adjustment is needed. Keep proper-time
   dilation intact; address displayed jitter separately from scheduler debt.

No production code, balance, temporal rule, original save, or global test
configuration was changed in this diagnosis. No general suite or extended
benchmark was run.
