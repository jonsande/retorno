# PT001-10 — departure diagnostics validation

Date: 2026-11-28. Initial HEAD: `840d354c36a74e55844e9d20e5ec13b1aab3845f`.
The unrelated `TODO.md` edit and prior review artifacts were preserved.

CLI and Textual share a pure departure diagnosis. It distinguishes engine power
from engine damage, selected speed beyond current capacity, docking/transit,
unknown/current/unrouted/out-of-range destinations, antimatter, and electrical
or core OS restrictions. `nav map routes` uses the same diagnosis. Valid quotes,
local travel, drone abandonment confirmation, and Engine revalidation remain.
The unknown-destination result does not depend on hidden physical existence.

Focused validation with `/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_10.py` → initial **16 passed, 1 failed**. The new out-of-range case expected a route-map row, but the existing map correctly excludes hops beyond its cap. The test expectation was corrected.
- `-m pytest -q tests/test_pt001_10.py tests/test_nav_routes_presentation.py tests/test_engine_speed_upgrade.py tests/engines_antimatter_smoke.py tests/test_nav_public_physical.py -k 'pt001_10 or nav_routes_presentation or compact_nav_confirmation or compact_local_confirmation or blocked_departure or public_views_localization or no_disclosure_or_query_mutation or nav_public_physical or engines_antimatter and (local_travel or insufficient_fuel)'` → **51 passed, 1 failed, 30 deselected, 38 subtests passed**. The isolated failure is the older `EnginesAntimatterTests.test_05_insufficient_fuel_atomicity_and_exact_balance`: its second departure emits `TRAVEL_STARTED`, but it asserts the legacy `ship.in_transit` flag, which current physical travel does not set. It also fails when run alone. PT001-10 does not alter the engine or that test.
- `-m pytest -q tests/test_pt001_10.py tests/test_nav_routes_presentation.py tests/test_nav_public_physical.py tests/test_engine_speed_upgrade.py::EngineSpeedUpgradeTests::test_compact_local_confirmation_invalid_unknown_and_drone_warning tests/test_engine_speed_upgrade.py::EngineSpeedUpgradeTests::test_blocked_departure_never_asks_for_confirmation_cli_or_textual tests/engines_antimatter_smoke.py::EnginesAntimatterTests::test_07_local_travel_and_isolated_engines tests/engines_antimatter_smoke.py::EnginesAntimatterTests::test_08_public_views_localization_and_textual_confirmations tests/engines_antimatter_smoke.py::EnginesAntimatterTests::test_09_no_disclosure_or_query_mutation` → **50 passed, 34 subtests passed** in 16.82 s.
- `-m pytest -q tests/test_pt001_10.py` → **17 passed** in 4.80 s after the final recovery hint wording.
- `-m pytest -q tests/test_pt001_10.py` → **19 passed** in 5.14 s after explicit unavailable-engine and critical-core cases were added.
- The same final targeted regression command listed above → **52 passed, 34 subtests passed** in 17.66 s after protecting the existing local-travel exception to the interstellar power-path check.
- Final repeat of that command → **54 passed, 34 subtests passed** in 17.93 s after adding life-support terminal and incomplete acquired-route cases.
- Final repeat after the missing-engine case → **55 passed, 34 subtests passed** in 19.62 s.

No general suite or benchmarks ran. No commit or push was made.

## PT001-10-F — historical navigation regressions

The antimatter smoke tests now check physical transit, the nominal plan and
its predeparture estimate instead of legacy `ship.in_transit` and `arrival_t`
for interstellar departures. The one-representable-float-short rejection is
atomic; exact-price departure pays once and leaves zero reserve. Duplicate
requests and aborts during physical transit are rejected without another
debit. A loaded trajectory retains its payment and reaches the destination
without an arrival charge. The same obsolete transit assertions in test_11
and the Textual test_12 were updated after the first module run exposed them;
their engine, fuel, confirmation and blocked-abort coverage remains.

The unknown-destination check now varies hidden physical data both inside
(2 ly) and outside (1000 ly) navigation range, while known nodes, contacts and
links remain identical. Public output, state and RNG remain unchanged.

Pytest's effective `python_files` patterns are `test_*.py` and `*_test.py`;
`engines_antimatter_smoke.py` is **not collected automatically**. It was run
by explicit module path. Discovery configuration was not changed.

Validation with the project Python:

- `-m pytest -q tests/engines_antimatter_smoke.py tests/test_pt001_10.py` →
  **34 passed, 2 failed** (the additional obsolete test_11/test_12 assertions).
- The same command after those assertions were updated → **36 passed** in
  24.45 s.
- Final repeat after asserting the localized Textual blocked-abort message →
  **36 passed** in 23.51 s.

No production code, navigation rules or Balance were changed. No general
suite, benchmarks, commit or push were run.
