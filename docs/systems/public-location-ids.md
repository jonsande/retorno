# Public location IDs

[Español](public-location-ids.es.md).

Implemented contract, 4D-3e5c-ID. Owner: `src/retorno/cli/location_ids.py`;
clients: `cli/repl.py`, `ui_textual/app.py`, `ui_textual/presenter.py`.

## Identity and uniqueness

A procedural historical identity consists of universe scope, generation sector
and slot. Within one game the scope is implicit. The public ID encodes the
three **generation-sector** coordinates and the slot, not the physical sector
into which a Gaussian sample may fall:

`P-<base36(zigzag(x))>.<base36(zigzag(y))>.<base36(zigzag(z))>.<base36(slot)>`

Zigzag maps nonnegative n to 2n and negative n to -2n-1. Base 36 uses
`0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ`, without leading zeroes. For example:

| Internal reference | Public reference |
| --- | --- |
| `S-001_+001_+000:WG1_<64-character-scope>_1` | `P-1.2.0.1` |
| `ECHO_7` | `ECHO_7` |

The example is nine characters. Length grows logarithmically with the address;
there is no fixed-width digest or probabilistic collision budget. The signed
integer encoding is bijective, canonical base 36 is injective and the four
separated fields have unique boundaries. Thus two different procedural
addresses cannot share a token in the same universe. Different games can reuse
a token: this is an operational ID within a voyage, not a global certificate.

Authored IDs remain unchanged. A deterministic prefix reservation checks the
finite immutable authored IDs and authored alias keys, case-insensitively. If
any starts with `P-`, append `-` until the whole prefix is unused (`P--`,
`P---`, ...). This terminates beyond the longest reserved string, does not
enumerate procedural sites and cannot depend on discovery order. The existing
operative `WG1C<n>` escape for an authored collision with an internal spelling
is verified and maps to the same sector/slot address. An authored ID resembling
a procedural operative ID remains authored.

The frozen manifest and narrative snapshot already persist. No alias registry,
new save field or migration is needed. Earlier procedural identifiers without
a historical WG1 address and existing authored identifiers keep their spelling.
The read-only definition accessor also handles a new game before first sector
materialization/pinning. Projection never pins or generates a sector.

## Resolution and completion

Both clients call `repl._resolve_parsed_locations` after parsing and before
command gates/dispatch. It resolves location fields for Travel, RouteSolve,
Dock, DroneMove, DroneDeploy, DroneSurvey and salvage variants, plus ship survey
and map graph/path tuples. Parser syntax and engine actions remain unchanged.
Full internal IDs continue through the existing engine gates. Descriptive-name
resolution retains the previous normalized-name form and rejects ambiguity.

Public resolution compares against acquired contacts, known map references and
the current location. It never inverts a guessed token through the physical
catalogue. A failed resolution leaves the input to the original command's
unknown-contact handling, without testing physical existence. Resolving an
acquired ID does not grant a route, local access, docking or operational power.

CLI/readline and Textual reuse contextual target providers. Providers calculate
range, hop cap, known routes and locality using canonical IDs, then project the
result. Dock/drone suggestions remain local; nav offers reachable routes;
route solve offers unresolved in-range contacts. Ordinary completion never
uses the hidden physical node collection as its candidate source. Readline's
word delimiters remain whitespace; Textual retains common-prefix completion
and double-TAB listing. No arbitrary choice is made for shared prefixes.

Examples (the actual prefix depends on the immutable authored namespace):

```text
ship survey P-1.2.0.<TAB>  -> ship survey P-1.2.0.1
route solve P-1.2.0.<TAB>  -> route solve P-1.2.0.1
nav P-1.2.0.<TAB>          -> nav P-1.2.0.1
dock P-1.2.0.<TAB>        -> dock P-1.2.0.1
drone survey D1 P-1.2.0.<TAB>
nav map path P-1.2.0.<TAB>
```

These examples assume one eligible candidate. A known contact alone need not
appear in nav completion.

## Presentation and historical evidence

Ordinary REPL renderers use `@public_output` and the module-local print adapter.
A ContextVar scopes the state to a renderer; global stdout and engine events
are not replaced or mutated. Nested renderers share the same projection and
concurrent contexts remain separate. Textual captures those same renderers;
its header and confirmation prompts also project references. Explicit debug
renderers keep technical IDs. Ordinary status/diag retain their knowledge gates.
Intel list fields are projected before column truncation.

Before: `LINK: ECHO_7 -> S-001_+001_+000:WG1_<scope>_1`.
After: `LINK: ECHO_7 -> P-1.2.0.1`.
Descriptive names continue to accompany IDs in contacts, maps and surveys.

An authorized document renderer may project a reference to a newly revealed
installation: the evidence is the acquired/readable document itself. The view
does not enrich its text with a name, position, catalogue entry or sender
identity. Reading still passes the **original content and original path** to
intel import and radio read marking. LINK parsing, certified source validation,
physical references, archive fingerprints, duplicate handling, protected
narrative targets and F-DEAD-01 therefore retain their existing inputs.

Non-narrative certificate-only lines (`HI1:` / `HR1-record:` with their full
64-character digest) are omitted in ordinary document views. They remain in
the original file, pool, emission, save and provenance records. No certificate
is replaced with a truncated identifier. `public_text(..., certificates=True)`
retains these lines; `restore_public_references` reverses location substitutions
against the finite authorized source references, giving byte-exact original
LINK content. It cannot discover arbitrary endpoints.

Mounted virtual paths containing operative IDs are projected too. Path
resolution compares only existing onboard filesystem paths; cat, ls and intel
import retain their normal access checks and canonical source paths. No file
is renamed. Completion offers those existing paths in their displayed form.

## Validation and limits

`tests/public_location_ids_smoke.py` covers twelve seeds, signed addresses,
separate hash-seeded processes, reversed discovery, authored/operative prefix
collisions, save/load, full IDs, engine parity, CLI providers, live Textual TAB
and dispatch in EN/ES, original LINK and radio evidence, uplink and negative
hidden-data variations. Existing worldgen/B1/B2/F-DEAD-01 matrices remain the
historical-identity authorities. A separate public journey and complete
regression results are recorded in the paired review document.

No topology, node distribution, internal identity, archive generation, radio
probability, economy, navigation mechanics, failsafe, story arc, AMANECER,
balance, audio or manual renaming feature is changed. Scope-free tokens must
not be used as cross-game archival certificates.

[Review and validation results](../testing/public-location-ids-review.md).
