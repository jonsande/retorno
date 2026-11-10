# T-04B1 — focused verification

Implemented against HEAD `8e4b9e924a3ca9aeff1fe6cf8e31a3ec0e1325c0`.
The initial 11 changed/untracked files were hashed before work and preserved
byte-for-byte, including `TODO.md`, clock display/UI changes and the existing
T-04A test edits. They are excluded from this delivery. No commit or push.

Only `src/retorno/core/engine.py` changes production behavior. The electrical
policy was extracted into `_integrate_power_interval`, with proper seconds for
battery integration and regulation timers. On arrival only electricity has
moving/rest segments. Other consumers keep their galactic interval and call
order/cadence; no new schema, balance value, narrative scheduler call or
per-second loop is introduced. Documentation and manuals have matching EN/ES
updates. Command syntax, help descriptions and event wording need no changes:
the existing power readings retain their units and meanings.

All checks used the canonical project Python and `PYTHONPATH=src:.`. Exact
commands, results and output are in
[the evidence](electrical-proper-time-results.json).

| Check | Result |
| --- | --- |
| Existing electrical policy smoke, before modification | PASS |
| New electricity tests + existing temporal clocks + antimatter | 41 PASS, 23 subtests PASS |
| Existing inertial module/save/load regression, selected test | 1 PASS, 10 deselected |
| Existing electrical policy smoke, after modification | PASS |
| Manual style and EN/ES pairs | PASS |

The 17 new tests cover rest (including stationary CRUISE), 0.5c and 0.8c,
positive/negative/balanced power, charge/discharge limits and efficiencies,
battery full/empty clamps, proper-time brownout persistence and recovery,
low-quality delayed shedding and reset, arrival crossing and exact arrival,
pre/post-arrival generation/load changes from a real module job, timer
partitioning, stable long/small-step agreement, damage and changed nominal
reference with frozen transit speed, unchanged antimatter/abort rules, new save/
load continuation including power timers, local movement, hibernation without
biological scaling of electricity, and a century interval with one electrical
integration and one narrative call. Arrival tests also check that jobs, wear,
hull, radiation, drone upkeep and life-support consequences are not subdivided
or converted to proper time.

No final failing check was found. No global suite or unrelated historical test
was run or repaired; this does not claim that the entire repository is green.
The existing shedding behavior can isolate `power_core`; the brownout recovery
fixture explicitly powers it back on rather than changing that policy.

Remaining dependencies and limitations are recorded in
[the implementation contract](../systems/electrical-proper-time.md): electrical
quality/brownout still influence existing wear and drone/job availability;
those consumers retain galactic time. The sampled policy does not reconstruct
all battery or job transitions within a long tick. Recovery forecasts retain
coarse galactic-duration energy estimates and were deliberately left outside
this runtime electrical migration. No old-save migration was added.
