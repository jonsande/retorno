# T-04A — engine speed upgrade verification

Implemented on the current HEAD; the pre-existing `TODO.md` edit was preserved
and excluded from the delivery. No commit or push was made. This was a focused
change, without a general audit, global suite run or unrelated historical repairs.

The canonical project interpreter ran the checks recorded in
[the evidence](engine-speed-upgrade-results.json). Each entry includes its command,
PYTHONPATH, exit code, elapsed time and actual output.

| Check | Result |
| --- | --- |
| Speed upgrade, cruise reference, temporal clocks and antimatter (`pytest`) | 40 PASS, 50 subtests PASS |
| New T-04A tests alone (included above) | 11 PASS, 36 subtests PASS |
| Manuals style and EN/ES pairing | PASS |
| Route hop cap and known-route integrity | PASS |
| Save/load | PASS |
| Prologue navigation policy and historical seed-1 catalogue fixture | PASS |
| Energy policy | PASS |
| Textual completion, active jobs and theme | PASS |
| Drone preventive autorecall | 17 PASS |
| Public location IDs, CLI dispatch and actual Textual input | 13 groups PASS |
| Worldgen module pools | Existing historical failure, described below |

The 13 recorded checks contain 12 passes and one documented historical failure.
`worldgen_modules_pool_smoke.py`, invoked with `PYTHONPATH=src:.`, fails with
`ValueError: Historical universe seed/version changed` in `_assert_regions`.
This is the same recorded failure in
[the previous results](drone-autorecall-results.json) and
[the earlier engine results](engines-antimatter-results.json), not a new T-04A
regression. The first invocation with only `PYTHONPATH=src` failed importing
`tests.fixtures`; the corrected invocation is the final result. The new focused
test separately verifies that the speed module participates in the ordinary
rare pool. Autorecall passes while emitting subprocess ResourceWarnings.
No new final failure was found in the checks executed; the global suite is not
claimed green.

Coverage includes all four speed bands, critical/offline rejection, no health-only
upgrade, nominal reference and configurable multipliers, strict subluminal limits
without display rounding to 1c, actual drone installation/removal and duplicate
copies, damage/repair and power cycling, independent efficiency and speed effects,
unchanged integrity and electrical demand, unchanged antimatter debit/refund rules,
galactic ETA and relativistic proper time, damage in flight, queued removal in
flight, subsequent repairs/installation, frozen nominal configuration, active save/
load with both modules, and independent local travel. EN/ES checks cover shared
CLI/Textual views, module inspection, manuals, help descriptions, navigation quotes
and actual keyboard-driven Textual departure/diagnostics/abort. Read-only duration
queries retain acquired-route boundaries and do not mutate state or disclose hidden
nodes.

Existing fixtures were adjusted only for the new contracts: synthetic transits in
clock/save tests now provide the frozen speed; the historical prologue catalogue
explicitly excludes the new speed module as well as the efficiency module.

Remaining limits: balance (18 scrap and rare) is provisional; ordinary drone gates
remain, including drone_bay support and no new removal request in transit; no old-save
migration, acceleration/braking or global time-domain conversion was implemented.
Generation, ordinary wear, radiation, hibernation/life_support and procedural narrative
were not changed. Catalogue changes retain the existing fresh-game requirement.

See [the implementation contract](../systems/engines-antimatter.md) for state rules,
configuration ownership, public commands and inertial cruise semantics.
