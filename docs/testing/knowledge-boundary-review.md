# RETORNO — Technical review of 4D-3e5a

[Español](knowledge-boundary-review.es.md). Date: 2026-11-06. External review delivery.

## Outcome

`C-DATA-004` establishes that engine data does not become playable knowledge merely
by existing internally. `status` and `diag comms` depend only on the receiver,
independently of hidden opportunities, remote sources, searches or plans, even
in debug mode. Omniscient access remains available through guarded `debug radio`
and `debug recovery`, shared by CLI/Textual. Additional small disclosures are
closed: surveying undiscovered IDs, resolving hidden dock names/aliases and
error/log differences exposing physical existence.

This change concerns presentation, documentation and tests. F-DEAD-01 selection,
manifest, generation, narrative placement, probabilities, deadlines, ledger,
capture, coverage, health/power, radiod, navigation rules, resources, persistence
schema, audio and AMANECER are unchanged. 4D-3e5b is not implemented.

## Baseline, audit and Git

Initial/final HEAD: `343829ee925492b4de62c5ccfd6025e3549dea51`. Branch `main`, upstream `origin/main`;
the local upstream ref matches. Initially clean working tree and empty index.
Final modified/new files are listed below; the index remains empty. No `git add`,
commit or push was executed; no remote operation changed the checkout. Historical
e5 reports retain their previous delivery context; this report and evidence apply
to e5a on the published commit.

Before editing, read AGENTS, canon/coherence, roadmap, navigation contract,
radio/recovery/discovery contracts and structural review. The complete baseline
finished before editing tests or production. Inspected public consumers/callers
in communications, structural_recovery, deadnodes, lore, model/world, parser/REPL,
Textual presenter and app. The audit stayed focused on status, navigation,
intel/lore, recovery and communications.

## Audited surfaces

| Surface / code | Finding and treatment |
| --- | --- |
| `communications.radio_diagnostic_lines` | Read pending entries and derived a reason from an invisible source. Both dependencies removed; uses only `radio_block_reason(state)` without an opportunity. |
| REPL `status`, `diag comms`, absent comms | Three calls to the public helper fixed together. Hardware/service/known operating reasons remain visible. |
| `recovery_searches` / `recovery_plans` | Technical aggregate states were playable. Removed from public diagnostics, including generic states. |
| `debug radio` | Existing ledger, source/host, IDs, channels, content, states, timestamps, path and delivery; receiver/spatial/capture reasons. Debug only. |
| `debug recovery` | Stored searches/certificates and plans; status/reason, cursor, work, access, sites, mechanisms, stage and consumption. Current budgets labeled as defaults. Debug only. |
| Textual `presenter` and app dispatch | Public commands reuse CLI renderers. New debug commands share renderer-level guards. Systems panel remains systems-only. |
| `ship survey <id>` | Previously inspected any physical ID. Now requires known contact/location; hidden and absent targets receive the same EN/ES rejection without ID or coordinates. Ship aliases/acquired data preserved. |
| Dock `_resolve_node_id_from_input` | Previously converted hidden names into internal IDs that could reach errors. Now resolves acquired knowledge only; physical dock gates unchanged. |
| Nav maps, graph, path, sectors and galaxy | Known projections, `known_links` and own position; hidden nodes leave output unchanged. `include_all_loaded=True` is used only by guarded `debug galaxy map` dispatch. |
| Contacts | Known contact/node list, not the whole physical graph. Distance, visits and known-route flags retained. |
| Intel list/show/export | Actually imported records, not placements/candidates. Acquired testimony can remain unverified without being reinterpreted as truth. |
| `route solve`, scan and navigation | Preserve the exact manual exception, natural discovery, primary protection and route semantics. Action engine unchanged. |
| CLI/readline and Textual completion | Knowledge/route/locality helpers do not suggest IDs exclusive to manifests, placements, radio or recovery. New debug names are general syntax. |
| Navigation errors and logs | Hidden existence yielded `unknown_contact` versus `node_missing` for absence. Shared EN/ES public projection without ID; engine codes and known-destination details preserved. |
| Help / errors | `diag comms` no longer promises counts; parser/help/completion include EN/ES debug commands. Debug denial does not inspect records; survey does not distinguish hidden existence. |
| Radio events / files / reading | Only real capture produces event/file. Received text/path remain visible; normal event rendering exposes neither opportunity nor plan ID. Reading/importing preserves intel. |
| Alerts / sounds | No new public event producer for mere preparation/search was found. Event types, audio and alerts unchanged; existing regressions run. |
| World, lore/deadnodes and saves | Physical/internal collections kept separate from knowledge. No new mutations/persisted fields. Protection, stages, ledger and records retained. |

No second data copy or artificial rejection history is added. `debug recovery`
does not reconstruct discarded candidates absent from stored state; it shows only
existing evidence. `debug radio` evaluates existing predicates to inspect current
delivery blocking reasons without attempting capture.

## Public and development separation

| Ordinary queries | Explicit development queries |
| --- | --- |
| Installed hardware, state/health, load, power, radiod installation/running state, operational capacity and receiver reasons. | Prepared opportunities, source/host, reserved content, metadata, pending/received/read state and source blocking. |
| Detected contacts, recorded routes, acquired intel, actually received files/events. | F-DEAD-01 searches/plans, retained certificates, cursor, work, stages, access and mechanisms. |
| `status` / `diag` keep the same meaning with debug on/off. | `debug on` enables `debug radio` / `debug recovery`; `debug off` blocks both again. |

`ready` means receiver capacity, not the existence of a signal or guaranteed
reception. No public phrase in the corrected helper depends on a secret
opportunity or hidden F-DEAD-01 result.

## Final canonical principle

The authoritative Spanish wording is reproduced verbatim in the Spanish review;
its complete English counterpart is in `docs/canon/universo.md` under
**C-DATA-004: Limited knowledge and information provenance [C]**:

Information existing in the universe’s internal state does not imply that the
protagonist can know it. All information presented as ship or player knowledge
must come from a legitimate observation, reception, reading, record or inference.
Inferences may be uncertain or wrong and must be distinguished from verified
facts. The simulation may know facts that remain inaccessible to the protagonist.

Distinguish physical/historical truth, engine internals, acquired observations,
inferences from legitimate evidence and ordinary consultable knowledge. Knowing
a location, knowing a route and receiving its transmissions now are separate.
False received testimony remains evidence rather than physical truth. Menus,
controls, save/load and general help need no artificial fictional explanation;
explicit development commands may expose internals without changing public queries.
Survivors, galactic chronology and `A-COM-001` remain open.

## Final AGENTS operational rule

The sole operational AGENTS remains English; the added block is:

```markdown
## Player knowledge and diegetic information boundaries

Follow `C-DATA-004` in `docs/canon/universo.md` and ask “How does the ship know
this?” using `docs/canon/guia_coherencia.md` before exposing universe facts.

- Every fact presented as ship or protagonist knowledge needs a legitimate
  observation, measurement, captured communication, read archive, prior ship
  record, or inference from available evidence.
- Distinguish physical truth, ship knowledge, and technical scheduler state.
  Inferences may be approximate, uncertain or false, but must be justifiable
  and distinguishable from verified facts.
- Never disclose secret catalogs, undiscovered historical sites, scheduler
  candidates, reserved documents, prepared narrative opportunities or internal
  recovery plans without a valid discovery event.
- Do not use internal collections containing hidden information directly as
  sources for playable diagnostics. Physical `space.nodes`, `lore_placements`,
  `radio_opportunities`, `recovery_searches` and `recovery_plans` are not ship
  knowledge. Known locations, known routes and current reception eligibility
  are separate facts.
- Keep omniscient diagnostics behind explicit development commands gated by
  `debug_enabled`. Ordinary `status` and `diag` retain their public meaning
  even with debug enabled. Diagnostic queries must not advance or mutate the
  simulation, consume RNG, generate sites, receive messages or import intel.
- CLI and Textual must enforce exactly the same knowledge boundary. Review
  events, sounds, help, contextual entity lists, completion and error messages
  as potential disclosure surfaces too.
- New features presenting universe state require negative disclosure tests:
  hold observations constant, vary hidden engine data, and compare public
  output. Also verify preservation of legitimately acquired information.

Menus, controls, save/load and general system help do not need artificial
fictional explanations. This rule concerns universe facts and knowledge
attributed to the protagonist or ship; it permits ordinary interface information
and explicitly activated development diagnostics.
```

## Negative tests and preservation

New `tests/knowledge_boundary_smoke.py`: **19 groups**. Full output comparisons
hold observations constant while varying hidden opportunities, out-of-coverage
sources, stopped service, search results, uncaptured plans, physical catalog and
placements. Includes status, diag, contacts, maps, routes, intel, alerts, Textual
header/panel; EN/ES debug gates, off after on, actual REPL and Textual input
dispatch, completion and dock aliases.

Before production changes, groups 1–6 and 14 failed on disclosures; 9–11 and 13
failed because the new commands did not exist yet. Groups 7–8, 12 and 15 already
passed, characterizing legitimate information and persistence. The additional
alias (18) and navigation-error (19) reproductions failed before their fixes. Groups 16–17 were added afterwards
as integration/catalog regressions. Before traces and final output are retained
in [complete evidence](knowledge-boundary-test-results.json).

Tests go beyond string absence: full output structures, actual events/files,
`known_links`, contacts/intel and read states are compared. Entire serialized state
and global RNG are unchanged by queries: time, generation, scan history, filesystem,
radio, recovery, resources and knowledge remain intact. Temporary save/load covers
pending/captured/read in both locales and compares plans/ledger and public views.
Existing radio tests also preserve narrative unlocks and deduplication.

## Regression and validation

- Baseline: **63/64** smoke scripts passed.
- Final complete run on definitive code: **64/65** passed, including the new script.
- F-DEAD-01: **36 groups**; narrative: **20 groups**; radio: **18 groups**, all passed.
- REPL/Textual, diagnostics, completion, navigation/intel, save/load, manifest/worldgen
  and audio are included in the global suite.
- EN/ES manuals: `MANUAL STYLE CHECK PASSED`. Help/parser/new text, document pairs
  and local references checked.
- `git diff --check`: passed. Empty index and unchanged HEAD.

Separate historical failure: `radiation_hull_smoke.py:183`, `AssertionError: []`,
fixture `CARNAVAL_34`. Baseline/final traceback is identical. The fixture is neither
modified nor hidden; the suite is not represented as entirely green.

The intermediate global run also passed 64/65 with 17 new groups. After the dock
alias fix, another complete global run used 18 groups. The `e5a-release` pass covered 18 groups; the hidden/absent destination error
difference was then closed and covered by group 19. Final normative evidence is
`e5a-delivery`; earlier executions are distinguished.

Reproduction uses the canonical interpreter with `PYTHONPATH=src:.:tests`:
`tests/knowledge_boundary_smoke.py`, `tests/structural_recovery_smoke.py`,
`tests/narrative_world_integration_smoke.py`, `tests/passive_communications_smoke.py`,
and `tests/manuals_style_check.py`; also run `git diff --check`.
The global runner executes each `tests/*smoke*.py` serially with the same interpreter,
`PYTHONPATH=src:repo`, temporary saves and 240 s per-script timeout. Evidence includes
per-script logs/results and runner source. User saves are untouched.

## Documentation, scope and limits

Canon/coherence advance to 0.4.0 with date/history; amendments include their English
text inline, preserving existing Spanish canon without a parallel AGENTS.
Communications, recovery, discovery/navigation contracts, roadmap v1.5 and
comms/boot/diag/status/ship/navigation manuals are synchronized EN/ES. Help/parser use existing
bilingual infrastructure. Technical diagnostic identifiers remain stable while
explanation and denial are localized.

No per-property provenance model, radio coverage, latency or emitter model is added.
`A-COM-001`, survivors and galactic chronology remain open. 4D-3e5b and extended
e6 playable validation remain separate. Textual tests exercise presenters and
actual input dispatch; this phase does not claim extended manual play with sound.

## Inventory and package

- `AGENTS.md`
- `data/manuals/commands/boot.en.txt`
- `data/manuals/commands/boot.es.txt`
- `data/manuals/commands/diag.en.txt`
- `data/manuals/commands/diag.es.txt`
- `data/manuals/commands/ship.en.txt`
- `data/manuals/commands/ship.es.txt`
- `data/manuals/commands/status.en.txt`
- `data/manuals/commands/status.es.txt`
- `data/manuals/concepts/navigation.en.txt`
- `data/manuals/concepts/navigation.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/canon/guia_coherencia.md`
- `docs/canon/universo.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/systems/discovery-navigation-intel.es.md`
- `docs/systems/discovery-navigation-intel.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/knowledge-boundary-review.es.md`
- `docs/testing/knowledge-boundary-review.md`
- `docs/testing/knowledge-boundary-test-results.json`
- `src/retorno/cli/parser.py`
- `src/retorno/cli/repl.py`
- `src/retorno/core/communications.py`
- `src/retorno/ui_textual/app.py`
- `tests/knowledge_boundary_smoke.py`
- `tests/passive_communications_smoke.py`
- `tests/structural_recovery_smoke.py`

Complete ZIP: `retorno-4D-3e5a-review-20261106.zip` beside the repository. It contains
all final files above, with relative paths, including both reports, tests and
evidence. Exact inventory, CRC and byte equality are verified. External manifest
has per-file SHA-256; archive checksum is in `.manifest.json` and `.zip.sha256`.
The archive's own hash stays outside it to avoid circular content. No .git, venv,
caches or saves. Work stops for external review without staging/commit/push.
