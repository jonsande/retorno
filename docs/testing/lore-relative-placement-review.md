# RETORNO — 4D-3e5c-C2a review

Base: local `main`, `0bd02fa` (2026-11-07). No staging, commit or push.

## Changes

- `src/retorno/core/lore.py`: shared relative-distance predicate and bootstrap
  validation for every piece, including optional singles; opt-in seeded primary
  reservation; reserved-host enforcement in candidate search and assignment.
- `tests/lore_relative_placement_integration.py`: focused schema, geometry,
  AND/boundary/alias, default/seeded, reservation, optional-piece and single checks;
  temporary AMANECER catalogue using the draft JSON and all ten supplied texts.
- EN/ES narrative contract, relative-placement design and integration README:
  implemented semantics and verification limits. No new player commands or help.

## Validation

Use `/home/jon/prog/retorno_case/retorno_venv/bin/python` with each script:

| Script | Result |
| --- | --- |
| `tests/lore_relative_placement_integration.py` | PASS |
| `tests/narrative_world_integration_smoke.py` | PASS, 20 checks |
| `tests/authored_closing_shift_integration.py` | PASS, three seeds and EN/ES journey |

AMANECER uses only seeds 1, 29 and 701. Liria exists in the historical manifest
before discovery and retains its compiled per-seed position on materialization.
The clue satisfies the existing 30 ly start bound and the new 15 ly Liria bound;
HARBOR_12–Liria remains below 45 ly. These seeds have multiple eligible certified
hosts and choose three distinct procedural hosts. All four Elena records bind
only to Liria. EN/ES drone salvage, exact text bodies, paths, reading/import of
the LINK, saved reservations/delivery and rejection of changed catalogues pass.
Normal status, comms diagnostics, contacts and map do not disclose hidden data;
queries preserve the serialized state. The production catalogue is preserved.

## Limits and handoff

The service fixture moves the ship to the hosts; a full AMANECER journey from the
prologue is not certified. Searches retain the existing finite domain and
`not_evaluated` budget semantics. Procedural anchors and the player ship are
excluded. Seeded selection does not imply uniform galactic sampling or variation
with one candidate. No full suite or broad seed sweep was run.

No worldgen, F-DEAD-01, balance, resource, audio, Textual, production catalogue or
original `narrative/amanecer/arcs/` text changed. Previous `TODO.md` edits are
untouched and excluded from the ZIP. Previously untracked design/draft inputs
remain in place; the draft JSON and ten texts are included unchanged as new-to-HEAD
test dependencies. The ZIP inventory records their SHA-256 and provenance.
Stop here for external review; AMANECER is not installed.
