# RETORNO — 4D-3e5c-P4

[Español](prologue-completion-review.es.md). Base:
`f459786a3e4e4be7049663326a07bd98741aa388`, initially clean working tree.

## Change

Two lines in the existing `Engine.tick()` arrival handling set
`MetaState.prologue_complete` when the transit destination and the physical
node reached are HARBOR_12 and completion is still pending. This runs inside
the effective arrival branch for a non-transit node, without requiring docking.
No events, scenes, counters or separate progression system are introduced.

The model's initial `False` value is preserved and departure does not reset it.
Existing persistence serializes the boolean as part of `MetaState`: there is
no schema change or migration. CLI, Textual and hibernation share the engine.
Navigation, P3, generation, B1/B2, exploration, survival and lore are unchanged.

## Modified files

- `src/retorno/core/engine.py`: idempotent activation on arrival.
- `tests/prologue_chain_smoke.py`: extends the existing public journey,
  without running the remainder of its suite.
- `docs/systems/discovery-navigation-intel.es.md` and `.md`: EN/ES
  prologue completion contract.
- `docs/testing/prologue-completion-review.es.md` and `.md`: this report.

Help and diegetic manuals are unchanged: no commands or messages were added.

## Executed tests

Interpreter: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.
With `PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`, ran only
`prologue_chain_smoke.public_chain()` and saved its JSON journal.

Result: **PASS** for all required cases:

1. New prologue and FAST_SANDBOX games start with `False`.
2. Reading ECHO_7's contact, querying the debug graph in an isolated copy,
   and recovering/importing the route do not complete the prologue.
3. Starting travel and advancing halfway preserve `False`.
4. Ordinary and hibernation arrivals set `True` without docking.
5. It persists after departure, arrival back at P and save/load. Persistence
   is also checked before completion, at HARBOR_12 and during departure.
6. Three subsequent ticks neither repeat arrival nor clear completion.
7. The main journey uses seed 1's public P3 chain without debug, teleportation
   or resource/knowledge edits. The ordinary-arrival control reuses a copy of
   the legitimate transit with two large ticks; no additional prolonged
   survival simulation is run.

Static checks: AST syntax of modified Python files, report links and
`git diff --check`, **PASS**. No seed sweep or general suite was run.

Incremental ZIP: only the six files above and `AUDIT/` with base, command, log,
evidence and a SHA-256/size inventory. The inventory excludes itself.
No `git add`, commit or push. Stopped for external review.
