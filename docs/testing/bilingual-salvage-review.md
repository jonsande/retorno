# RETORNO — 4D-3e5c-P5c

[Español](bilingual-salvage-review.es.md). Base:
`ebe16fb5592f481456b0d9992e24dce943facafd`.
`TODO.md` was already modified; it is preserved untouched and excluded.

## Fix

The `salvage_data` assignment in `src/retorno/core/lore.py` prepares EN and ES
through the existing renderer when resolved resources and normalized paths
are distinct. Both paths are checked against base and injected files before
inserting archives or recording placement; a collision rejects the whole set.
Both files retain a single `piece_key`, host, channel and delivery. Arc path
metadata retains the active-locale variant at assignment.

Texts, narrative restrictions, host selection and Elena's four-secondary limit
are unchanged. Monolingual content, shared resources and single-path pieces
retain their previous representation, as do other channels. Worldgen,
navigation, B1/B2 and god mode are unchanged. The fix applies to new assignments;
old saves are neither migrated nor backfilled.

## Executed validation

Interpreter `/home/jon/prog/retorno_case/retorno_venv/bin/python`, environment
`PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`.

1. `tests/bilingual_salvage_smoke.py`: **PASS**.
   EN→ES and ES→EN; recovery and reading of both navigation-clue files and
   eight files for the four documents. All secondaries remain exclusively
   on LIRIA; five logical arc deliveries (clue plus four documents), with
   one discovery of the clue. Repeated salvage, rereading and save/load
   preserve files and progression. EN/ES collisions in base/injected files
   reject assignment without any mutation. Monolingual, shared-path and
   inline compatibility, plus the existing channel-preference/unlock
   regression: **PASS**.
2. `lore_relative_placement_integration.test_amanecer()`: **PASS**, the
   existing focused test for 1/29/701. Artificial placement/file resets on
   locale changes were removed; the test now uses originally prepared
   variants. The remainder of its suite was not run.
3. AST syntax, new links and `git diff --check`: **PASS**.

Tests reuse the service fixture and real drone jobs. The fixture positions the
ship to test delivery; it does not recertify or repeat the prologue journey or
P3 navigation chains. Operational action counters still count ordinary actions;
the second language does not duplicate placements, deliveries or narrative
progression.

## Files and delivery

- `src/retorno/core/lore.py`.
- `tests/bilingual_salvage_smoke.py`.
- `tests/lore_relative_placement_integration.py`.
- `docs/systems/lore-scheduler.es.md` and `.md`.
- `docs/testing/bilingual-salvage-review.es.md` and `.md`.

Technical contract: [Lore scheduler](../systems/lore-scheduler.md).
No commands or messages were added; help and diegetic manuals keep their
existing salvage, listing and reading flows.

Incremental ZIP: seven task files plus audit material with base, commands,
logs, JSON evidence and a SHA-256/size inventory. The inventory excludes itself.
No `git add`, commit or push. Stopped for review.
