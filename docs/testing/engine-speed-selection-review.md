# Target speed verification and provisional balance

Implemented against `main` at `d423fef7654987b83f186f24630b080a79363712`.
The [existing engine contract](../systems/engines-antimatter.md) owns behavior
and formulas; this report records checks and balance evidence. No commit or push.

## Focused verification

The pre-change T-04A, fuel, cruise, clock, electrical and wear tests passed:
70 tests, 80 subtests. The final selection of those same suites passes 79 tests,
97 subtests. Existing tests were extended rather than duplicated. Coverage includes
all eight speed steps, default max, every health/module ceiling, real drone repair,
installation/removal, fixed-target invalidation/recovery, exact quote/debit,
ETA/proper time, frozen transit, abort, local travel, pure queries, hidden-data
non-disclosure, save/load and real CLI/Textual dispatch in EN/ES.

```bash
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python -m pytest -q \
  tests/test_engine_speed_upgrade.py tests/engines_antimatter_smoke.py \
  tests/test_cruise_speed.py tests/test_temporal_clocks.py \
  tests/test_electrical_proper_time.py tests/test_wear_proper_time.py
```

Additional standalone scripts passed, run with that interpreter and PYTHONPATH:

| Script | Result |
| --- | --- |
| `tests/energy_policy_smoke.py` | PASS |
| `tests/save_load_smoke.py` | PASS |
| `tests/textual_completion_context_smoke.py` | PASS |
| `tests/known_routes_integrity_smoke.py` | PASS, 10 checks, seed 271828 |
| `tests/manuals_style_check.py` | PASS, including EN/ES file pairing |
| `tests/audio_config_smoke.py` | PASS |
| `tests/config_audio_smoke.py` | PASS |

After completing manuals and shared EN/ES event/log messages, the engine-speed
suite was rerun: 20 tests and 53 subtests passed. The existing public-view test
also verifies command help/manuals. No final failures; no general suite run or historical
test repair. The initial iterations only adjusted expectations deliberately
changed by speed pricing/ceilings and the CLI test's scenario fixture.

An AST comparison against the starting revision verifies that the only modified
existing Engine methods are `apply_action`, `engine_fuel_cost` and
`estimate_travel_fuel`. Tick, arrival sampling, proper time, electrical regulation,
battery and ordinary-wear integration remain unchanged. CANON and module catalogue
are unchanged. Save selection validation uses the existing save format/loader.

## Deterministic matrix

[Full CSV: 54 cases](engine-speed-balance.csv), distances 2/10/20 ly; initial
engine health 0.9/0.7/0.5; independent speed/efficiency equipment combinations.
Each profile compares 0.1c, 0.3c and its available maximum. Regenerate with:

```bash
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python \
  tests/test_engine_speed_upgrade.py --balance-matrix
```

The existing test fixture (seed 29) calls the actual fuel, proper-time and
system/hull wear helpers. It assumes constant CRUISE, Q=1, no brownout,
environmental/internal radiation, repair, other events or resource exhaustion.
Hull starts at 1.0. Wear columns are absolute integrity loss, clamped at zero
remaining health. These are conditional ordinary-wear estimates, not a complete
centuries-long game simulation or a survival guarantee. No coefficients changed.

Example, 10 ly at initial engine health 0.9, speed module installed, no efficiency:

| Speed | Capsules | Galactic years | Ship years | Engine wear | Hull wear |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.1c | 0.45675 | 100 | 99.49874 | 0.266712 | 0.047067 |
| 0.3c | 1.00485 | 33.33333 | 31.79797 | 0.085236 | 0.015042 |
| 0.8c | 3.34950 | 12.5 | 7.5 | 0.020104 | 0.003548 |

At 10 ly, max without the speed module is 0.5c: 1.5225 capsules,
20 galactic years and 17.32051 ship years. Efficiency multiplies fuel by 0.8 at
equal health/speed, leaving these times and conditional wear unchanged. Equipped
health 0.7 supports max 0.6c; health 0.5 supports max 0.4c.

No sampled speed dominates both fuel and time/wear. The extremes are costly:
0.8c costs 7.33 times the capsules of 0.1c at equal integrity/distance, while
0.1c incurs 13.27 times its ship time and ordinary wear before clamping. At 20 ly,
starting at health 0.5 with both modules, 0.1c leaves engines OFFLINE in this
estimate; 0.3c leaves them CRITICAL, while max 0.4c leaves them DAMAGED. Slow travel
can be a poor maintenance trade even when capsule-cheap. Whether either extreme
is too attractive or impractical remains pending procedural capsule availability
and the wider maintenance economy; nothing was retuned to force a balance result.

## Textual with sound

From this checkout, launch a disposable test slot:

```bash
cd /home/jon/prog/retorno_case/retorno
RETORNO_SCENARIO=fast_sandbox PYTHONPATH=src \
  /home/jon/prog/retorno_case/retorno_venv/bin/python -m retorno.ui_textual.app \
  --new-game --save-path /tmp/retorno-speed-demo.dat
```

In the terminal:

```text
config set audio on
config set ambientsound on
config show
man engine_speed
engines speed
engines speed 0.3
nav map routes
```

Use `nav <id shown by nav map routes>` and confirm with y (EN) or s (ES).
`engines speed` now shows the frozen actual 0.3c separately from the target,
ceiling and CRUISE electrical mode. `engines speed max` must reject changes
while moving. `nav abort`, confirm, then `engines speed max` succeeds without
refunding capsules. Compare the next `nav map routes` quote. Values over 0.5c
require the existing speed module and sufficient engine health; 0.8c at nominal
health, 0.6c when LIMITED, 0.4c when DAMAGED.

Audio uses the existing backend, preferences and event routing; no new sound
asset or independent audio path. Automated UI checks disable playback and the
audio configuration smokes passed; physical speaker playback was not tested.
