# Permanent work rules for Retorno agents

Spanish counterpart: [working-rules.es.md](working-rules.es.md). This expands
[AGENTS.md](../../AGENTS.md). Current issues belong to
[current-status.md](current-status.md).

## Scope and repository

- Work in small, bounded interventions. Define behavior, affected surfaces,
  acceptance criteria and exclusions before expanding a task.
- Inspect the working tree first. Preserve unrelated changes, untracked
  material, player profiles and original evidence saves. Use private copies.
- Do not commit, push or merge without authorization. Do not reset another
  person's work. Stop and report evidence and impact if a problem exceeds the
  authorized scope.
- Reuse existing infrastructure, unify duplicated logic and avoid parallel
  infrastructure. Ask for authorization before implementing changes with
  significant architectural risks. Use
  this checkout's `/home/jon/prog/retorno_case/retorno_venv/bin/python` for
  every Python command, never system `python` or plain `pytest`.

## Evidence and interruption recovery

- Run focused tests during development; use the general suite at significant
  integration milestones or when explicitly requested.
- Record exact commands, results, failures, measurements and code state in
  resumable intermediate notes. Never claim an interrupted test passed.
- Reuse completed validation while the code it covers is unchanged. Repeat
  only for a concrete remaining risk or required gate. Keep reference data for
  performance comparisons.
- Verify affected paths and links. Every new or modified document must have
  EN/ES versions with semantic parity, checked before handoff.

## Game and presentation

- Preserve physical and causal continuity, finite resources and fuel receipts,
  deterministic order, atomic rollback and correct save/load for the **current
  version**. Old-save migration is a separate task unless explicitly scoped.
- Update the owning technical document for observable behavior changes; also
  review manuals, help, tests and both languages. Distinguish implemented
  behavior, approved design and technical proposals. The index is
  [system-contracts.md](system-contracts.md).
- All player-facing text and diegetic manuals require EN/ES through existing
  localization. Keep identifiers stable; comments need no artificial
  translation. Follow the [manual style guide](../manuals_style_guide.md).
- Apply [`C-DATA-004`](../canon/universo.md) and the
  [coherence guide](../canon/guia_coherencia.md): separate physical truth, ship
  knowledge and scheduler state. Hidden nodes, lore and recovery ledgers are
  not player knowledge. Check CLI, Textual, events, sounds, completion and
  errors for leaks; test nondisclosure and retention of acquired information.
  Where applicable, hold player observations constant, vary hidden internal
  data and verify that public output does not change.
- Put omniscient diagnostics behind explicit `debug_enabled` commands.
  Ordinary `status` and `diag` stay public even in debug. Diagnostic queries
  must not mutate state, consume RNG, generate sites or import intel.
  Keep normal ship-state feedback diegetic; reserve internal progress and
  implementation details for debug. Controls and save/load need no fictional
  pretext.
