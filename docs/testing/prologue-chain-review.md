# RETORNO — 4D-3e5c-P3

[Español](prologue-chain-review.es.md). Base: `dc09628a1f1124a4122c4d4671362d4b7a96ba58`;
initially clean working tree. Implementation for external review.

## Result and guarantee

The `historical-prologue-chain-v1` extension fixes a public chain
ECHO_7 → procedural P → HARBOR_12 before exploration. It searches nine initial
cohorts and excludes protected/reserved sources. If none qualifies, one extra
`derelict` slot is added to the manifest. With the installed anchors, its whole
position box `[4,6) × [1,3) × [0.1,0.2)` admits two positive hops below 45 ly.
This construction covers every valid seed; sample-seed checks are regressions,
not the proof.

ECHO_7 preserves ordinary uplink selection except for, at most, the last
destination needed to reserve P. P contains a permanent bilingual, guest B1
archive importable through ordinary salvage and reading. There is no direct
procedural route grant from ECHO_7, required use of ARCHIVE_01, dependency on
radio, narrative windows or later recovery.

Ordinary sites, positions, draws, hubs, edges and identity scope are preserved.
The additional slot neither perturbs existing weighted pools nor declares
radio equipment. B2 preserves its ordinary B1 projection without the two new
reservations; alternative routes and authored/manual mechanisms keep their
rules. The previous seed 1 two-uplink journey remains available.

Preparation and save/load certify physical selection, distances, effective
channels, recoverable archive, the three-destination limit, protections and
absence of a circular dependency. The versioned extension is captured in the
manifest and information fingerprint; B2 binds that fingerprint. Older saves
are not migrated. Detailed contract and constructive proof:
[Historical prologue guarantee](../systems/prologue-navigation.md).

## Files

- `src/retorno/worldgen/manifest.py`: deterministic reservation and historical slot.
- `src/retorno/worldgen/narrative.py`: preparation after narrative reservations.
- `src/retorno/worldgen/information.py`: records, archive and certification.
- `src/retorno/worldgen/historical_radio.py`: reservation-specific isolation.
- `tests/prologue_chain_smoke.py`: new focused verification.
- `tests/prologue_navigation_policy_smoke.py`: P1 comparison of the ordinary
  projection and an incompatible-catalog fixture that preserves P1.
- `tests/structural_recovery_smoke.py`: the synthetic scene discards the prologue
  contract when replacing its anchors; productive recovery is unchanged.
- EN/ES documentation: new contract, this report and references from
  `world-generation`, `historical-information` and `historical-radio`.

`generator.py` needs no edit: its existing materializer and inventory already
consume manifest sites. Data, commands, help, diegetic manuals, ordinary
navigation, times, survival, god mode and lore are unchanged.

## Executed validation

Interpreter: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.
Environment: `PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`.

- `python -u tests/prologue_chain_smoke.py`: PASS, seven focused groups.
- After adjusting the archive and fallback names, reran `structural()`,
  `fallback()` and `public_chain()`: PASS. Includes forced B2 navigation
  emissions and preservation of the ordinary pool in the fallback case.
- `git diff --check`: PASS. No seed sweep or general test suite.

Coverage: 1/29/701, negative certificates, hidden-state nondisclosure in status,
FAST_SANDBOX, fallback without an admissible candidate, physical inventory,
idempotent materialization, save/load of the fallback and recovered data before
reading, EN/ES import without duplicates, and incompatible-catalog rejection.
Completed the new public journey in seed 1 starting from FAST_SANDBOX without
debug, teleportation or resource/knowledge edits: 5.167647 and 14.369025 ly hops,
including docking, drone deployment, salvage and reading. Also verified the
normal prologue in 29 and the alternative two-uplink journey in 1.

The incremental ZIP contains complete modified files and `AUDIT/` with JSON
evidence, logs, base and a SHA-256/size inventory. It excludes saves, the virtual
environment and unchanged files. The inventory excludes itself.
No `git add`, commit or push. Work stopped for review.
