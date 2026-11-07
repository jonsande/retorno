# Public location IDs — review

[Español](public-location-ids-review.es.md).

Implemented for external review, 2026-11-07. Base: `2516c9bec8bcec0262fec85562ea45daa68632c2`, branch `main`.
The working tree remains unstaged. The pre-existing `log_copy.txt` change is
preserved byte for byte and excluded from the review patch/package.

## Result and scheme

Procedural locations now have compact, whitespace-free public tokens such as
`P-1.2.0.1`, accepted by CLI and Textual. Internal operative IDs, historical
identities, authored IDs, save keys, certificates and physical references are
unchanged. The [implemented contract](../systems/public-location-ids.md) gives
the address encoding, injectivity proof, authored-prefix collision escape,
knowledge boundary and presentation/validation split.

The scheme encodes signed generation-sector coordinates and the historical
slot in base 36. It truncates no hash, needs no procedural catalogue or alias
registry and is independent of discovery order. Scope is implicit within the
saved game; tokens are deliberately not cross-game certificates. Authored
prefix collisions are escaped against the immutable finite namespace, before
any discovery. Legacy and full operative identifiers remain accepted.

## Before/after and commands

`S-001_+001_+000:WG1_<64-character-scope>_1` becomes `P-1.2.0.1`.
`ECHO_7` remains `ECHO_7`. Contacts, routes, maps, scan, intel, events, survey,
radio/archive views, confirmation prompts and Textual headers use the same
projection. Descriptive names remain available. Intel columns abbreviate
before truncating. Certificate-only HI1/HR1 lines are hidden in the ordinary
view, retained in the original evidence, and never used as short location IDs.

TAB examples with one eligible candidate: `nav P-1.2.0.<TAB>`,
`route solve P-1.2.0.<TAB>`, `dock P-1.2.0.<TAB>`,
`ship survey P-1.2.0.<TAB>`, `drone move D1 P-1.2.0.<TAB>`,
`drone survey D1 P-1.2.0.<TAB>`, salvage location arguments and
`nav map path P-1.2.0.<TAB>`. Multiple candidates retain ordinary common-prefix
and list behavior. Context providers still decide eligibility with canonical
IDs; no hidden physical collection supplies candidates.

## Evidence and coverage

`tests/public_location_ids_smoke.py` passes all 13 groups:

| Groups | Scope |
| --- | --- |
| 01–03 | Twelve seeds; signed multi-digit addresses; opposite generation/discovery orders; three independent PYTHONHASHSEED processes; simulated authored public/operative collisions and ambiguous names. |
| 04–05 | Save/load; authored/full IDs; all location action fields and map/survey tuples; canonical engine event/state parity. |
| 06 | CLI contextual completion and public presentation in EN/ES; route filtering precedes ID conversion. |
| 07–08 | Byte-exact reversible LINK view with certificates; original file and B1 record retention; normal import replay; mounted public paths, extension fallback and access restrictions. |
| 09 | Fixed observations with changed hidden nodes/placements: identical public CLI/Textual projections and unknown-token action errors, no secret completion or resolution. |
| 10 | Actual procedural reception, original payload/emission/file retention, read/import, validation and uplink history. |
| 11–12 | Actual Textual TAB/Enter in EN/ES, shared-prefix ambiguity and action dispatch; actual readline callback and CLI dispatch. |
| 13 | Successful route computation from a real historical contact with a public ID in a labelled controlled range fixture. |

The complete scripts for worldgen, B1, B2 and F-DEAD-01 remain unmodified and
pass. The production diff does not touch core actions/engine, generation,
information/radio producers, persistence, topology, balance, economy, audio or
narrative packages. Original LINK text and source paths remain the inputs to
certification, import and radio read marking; views never rewrite them.

## Public gameplay witness

The review package includes a seed-42 EN campaign transcript and real saves.
The prefix starts from the unmodified prologue, repairs systems with public
commands, discovers ECHO, acquires uplinks and visits procedural installations
using short IDs. Application reloads use the genuine arrival checkpoints.
A normal waypoint maneuver creates a new route origin; an already acquired
nearby procedural contact is surveyed, solved with its public ID, visited and
docked. The maneuver is chosen only from acquired positions and known routes.
It includes numeric hibernation, nav abort and any genuine radiation wakes;
there are no debug commands, clock assignments or gameplay-state grants.
This proves a concrete interaction, not universal exploration or survival.
EN/ES client parity is separately exercised by the live UI/CLI matrices.

Concrete witness: `P-0.3.0.1`, solved from `NAV_PT_1720`, then navigated, docked and reloaded successfully; 101 recorded commands/runtime entries. The final sequence includes `ship survey P-0.3.0.1`, `route solve P-0.3.0.1`, `nav map path P-0.3.0.1`, `nav P-0.3.0.1` and `dock P-0.3.0.1`.

## Regression and delivery

Global final regression: **74/75 scripts pass**. All 13 new groups pass.
The sole failure is the historical `radiation_hull_smoke.py` assertion at
`CARNAVAL_34`, line 183 (no environmental radiation-level event). The same
failure is reproduced from an isolated archive of the base HEAD. It is not
suppressed, marked xfail or counted as a pass. The serial wrapper requiring
an output argument is excluded; every smoke script, manual checker, manifest
comparison and radio geography script runs directly.

`git diff --check` and paired-manual/style validation pass. The package contains
complete changed/new files, an applicable patch, per-file SHA-256 inventory,
source provenance, final regression logs, baseline failure, before/after
presentation, public transcript/checkpoints, reproducible drivers and ZIP
verification. The ZIP's SHA-256 is supplied alongside it.

Changed production areas: one pure public-location module; shared REPL input,
output and completion integration; Textual dispatch/prompts/header integration.
Documentation: paired system contract/review, documentation index, navigation
concept and eight command manuals. Existing test files are unchanged; one new
13-group matrix is added. The machine inventory lists every exact path.

Scope-free IDs grow with address size and exceptional authored prefix escapes;
they are compact operational addresses, not fixed-length/global identifiers.
The displayed projection is not the import format: original files remain the
authority. No manual renaming or exhaustive alias registry is introduced.

No staging, commit or push was performed. Work stops for external review.
