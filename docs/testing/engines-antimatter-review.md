# Engines and antimatter — verification

Base: CANON commit `bc95cae37c04c4cd20f9e205558766bb8bdbb066`, also the checkout HEAD.
The existing local `TODO.md` edit was preserved. No commit or push was made.

The project interpreter `/home/jon/prog/retorno_case/retorno_venv/bin/python`
ran focused checks first, followed by all 83 executable test scripts and the
default pytest collection. Benchmark/comparison programs and the serial suite
wrapper are not independent tests. A clean temporary archive of HEAD ran the
same baseline script suite (82 scripts before the new integration test).
Final reruns cover the adjusted auxiliary load, integration tests and changed
catalogue-dependent fixtures; their results replace earlier intermediate runs.

| Check | Result |
| --- | --- |
| New engine integration | 12 groups PASS |
| Default pytest collection | 17 PASS, 14 subtests PASS |
| Full executable script suite, including final reruns | 65/83 PASS, 18 FAIL |
| Clean HEAD baseline | 61/82 PASS, 21 FAIL |
| Manual style and EN/ES pairing | PASS |
| Whitespace check for task changes | PASS; pre-existing TODO.md excluded |

All 18 remaining failing scripts also fail on clean HEAD. The suite is
still red; this change does not claim complete repository correctness. The
per-script results and final exception lines are in
[the evidence file](engines-antimatter-results.json).

Coverage of the new integration includes NOMINAL/0.90 initialization and no
security/securityd; normalized integrity and canonical cost examples; wear and
real drone repair; module installation, removal and non-stacking copies;
insufficient fuel with no navigation/cache/RNG mutation; exact fuel exhaustion;
local travel; repeated requests, arrival and abort without duplicate charges;
active-transit save/load; read-only route queries and negative hidden-data
comparisons; bilingual manuals, module names/effects and error messages; and
actual Textual keyboard input, cancellation, confirmation, fuel debit and abort
in both languages. Existing prologue chain, power policy, route cap, route
integrity, clocks, relativistic travel, save/load, public IDs and Textual checks
pass. The final 0.2 kW auxiliary setting also passes 15.23-year hibernation.

Fixture adjustments preserve contracts rather than change production rules:

- Public walkthroughs omit the removed security command.
- The route-integrity fixture supplies its seed before bootstrap instead of
  changing an already pinned universe.
- The original seed-1 two-uplink example explicitly freezes the pre-module
  catalogue in a disposable data root; the guaranteed prologue chain and normal
  prologue checks still run with current productive data and consume fuel.
- Ordinary archive subtraction is compared to exact unfiltered records rather
  than a catalogue-dependent fixed count. Radio witnesses exclude protected
  sources/targets and select an actual overlap under the current catalogue.
- Pre-engine saved fixtures are explicitly rejected without rewrite, as required
  by the new disposable-save contract; no migration was added.

Remaining baseline failures:

- `tests/authored_closing_shift_integration.py`
- `tests/deadnode_chain_detours_smoke.py`
- `tests/deadnode_chain_planner_smoke.py`
- `tests/deadnode_opportunity_selection_smoke.py`
- `tests/debug_lore_arcs_smoke.py`
- `tests/exploration_recovery_smoke.py`
- `tests/historical_information_smoke.py`
- `tests/lore_secondary_count_weights_hard_smoke.py`
- `tests/narrative_world_integration_smoke.py`
- `tests/nav_abort_waypoint_cleanup_smoke.py`
- `tests/radiation_hull_smoke.py`
- `tests/radio_spacetime_smoke.py`
- `tests/scan_observation_memory_smoke.py`
- `tests/structural_recovery_smoke.py`
- `tests/uplink_only_delivery_retry_smoke.py`
- `tests/worldgen_manifest_integration_smoke.py`
- `tests/worldgen_modules_pool_smoke.py`
- `tests/worldgen_preexistence_catalog_smoke.py`

These concern existing historical/catalogue fixtures, protected narrative cases,
recovery contracts, a superluminal test fixture, or radiation assertions. They
were not repaired through changes to unrelated gameplay mechanics.

The [implementation contract](../systems/engines-antimatter.md) documents public
commands, provisional balance, known limitations and minimal Textual steps.
