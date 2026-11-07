> **4D-3e5b — optional transmitter extension.** Root-level `radio_emitters` in
> an installed location, arc or single declares equipment/emissions independently
> of host kind. It reuses this contract's identities, aliases and certificates,
> adding no geography. `piece_key` + `radio_emission` bind a piece to an emission
> without advancing its scheduler/trigger. The full catalogue includes radio;
> the physical hash excludes only that metadata. Format, limits, valid examples
> and compatibility: [spatial and temporal radio](systems/radio-spacetime.md).
> General authoring/editorial review remains e5c, without incompatible changes.

# Physical narrative requirements — 4D-3e4

[Español](narrative-world-contract.es.md). Status: tested minimum implementation;
**provisional opt-in format**, awaiting external review as a permanent interface.
Owners: `worldgen/narrative.py`, `worldgen/manifest.py`, `runtime/data_loader.py`
and `core/lore.py` under `src/retorno/`.

## Activation and five layers

Only `data/locations/*.json`, `data/arcs/*.json` and entries in
`data/lore/singles/index.json` participate. Loaders share a nonrecursive reader
with provenance. Neither `templates/` nor `narrative/` becomes active. Every
installed single contributes declarations even if its document is never selected.

Separate literary reference, canonical declaration, historical site, player
knowledge and published route. “Horizon disappeared” in prose neither changes
physics nor reveals intel. `claims` holds nonbinding assertions and does not feed
the solver. Rumours do not declare existence. Existing `constraints` continue
to filter **documents**.

## Executable data

Both complete packages and their EN/ES texts live in
[`tests/fixtures/narrative_world/`](../tests/fixtures/narrative_world/).
`alpha.json` is an arc; `beta.json` is a single index entry. They are optional
fixtures, **not installed content**. The test installs them only in a temporary
copy and exercises bootstrap, drone jobs, reading and import:

```sh
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
```

Minimal block, optionally added to a location, arc or single:

```json
{"world_requirements": {
  "version": "narrative-world-v1",
  "entities": [{"id": "TEST_HOST", "name": "Test Host", "kind": "station",
    "position": {"fixed_ly": [26, 27, 1]}}],
  "references": ["ECHO_7"],
  "relations": [],
  "claims": [{"text": "NEVER_EXISTED is inhabited", "status": "rumor"}]
}}
```

Declare each ID once; other packages share it through `references`. References
resolve IDs, names and explicit `aliases` case-insensitively. Duplicates, including
identical declarations, and all name/alias/ID ambiguities are rejected.
`RETORNO_SHIP` is reserved and is not a historical destination. Existing locations
keep their schema and attributes; adopting this block is optional.

A new entity accepts `id`, `name`, `aliases`, `kind`, `position`. Kinds are
`station`, `relay`, `waystation`, `ship`, `derelict`; an explorable wreck can use
`ship`. The existing `data/locations/` schema remains available for custom authored
salvage and files. The new block neither invents resources nor adds conservation
simulation.

Alternative positions used in the fixtures:

```json
{"id": "TEST_STATION", "name": "Test Horizon", "aliases": ["Horizon"],
 "kind": "station", "position": {"box_ly": [[149950,150050],[1,8],[1,8]],
 "regions_any": ["disk","halo"]}}
```

```json
{"id": "TEST_WRECK", "name": "Test Wreck", "kind": "ship",
 "position": {"offset_from": "Horizon", "offset_box_ly": [[0.5,1.2],[0,0],[0,0]]}}
```

Exactly one position mode is required: `fixed_ly`, `box_ly`, or `offset_box_ly`
with `offset_from`. Canonical `sector` and `regions_any` filters are supported.
There are no freeform constraints, orbits, planetary systems or dates. Unknown
geometry fields are rejected instead of being silently considered satisfied.

```json
{"type":"near", "from":"TEST_STATION", "to":"TEST_WRECK", "min_ly":0.5, "max_ly":1.2}
```

`near` checks inclusive Euclidean distance. `physical_link` requires a direct
edge **already authorized by productive topology**, within 45 ly; it does not add
special edges. `historical_association` checks identities and retains the historical
fact without inventing a chronology. `from_kind`/`to_kind` check endpoint kinds.
Proximity, physical edges and known routes are separate. General multihop path
requirements between entities are not yet supported.

## Compilation and bounds

Before returning initial state, `prepare_new_world` collects the catalogue,
validates referenced resources, IDs and aliases, resolves positions and relations,
binds clues and verifies essential opportunities. It uses `define_manifest` and
productive sessions; sampling, quotas, guardrail and topology are reused.

Each variable position has 32 candidates derived from version, seed and ID.
Entities are ordered by dependency and ID, with at most 4096 backtracking steps.
Game RNG is not used. Cyclic positions, inverted intervals and provable
contradictions are rejected. `not_evaluated` means exhausted budget or no verified
solution within the discretization; it **does not** prove continuous impossibility
or authorize starting play. `unsatisfiable` is reserved for proven contradictions
or closed domains; `invalid` denotes contract errors. Diagnostics include source,
entity and field when known.

The manifest incorporates additional authored sites and its catalogue scope when
new declarations exist. Certified results and relations are retained in
`WorldState.narrative_snapshot`. New sites materialize lazily without initial
contacts. Existing authored sites retain bootstrap and loot. With no new blocks,
the previous physical scope is preserved; a catalogue snapshot is still saved.
Measured comparisons do not change density, hub, resource or connectivity knobs:
authored sites occupy existing quotas.

## Seed-bound clues

`spatial_bindings` is optional and separate from public intel instructions:

```json
{"spatial_bindings": {"version":"narrative-world-v1", "values": {
  "dest_id":{"entity":"TEST_WRECK","field":"id"},
  "dest_sector":{"entity":"TEST_WRECK","field":"sector"},
  "dest_coord":{"entity":"TEST_WRECK","field":"coord"}
}}}
```

It applies to `line`, inline content, and the document's or its `files` entries'
`content_ref`, `content_ref_en/es`. Supported fields: `id`, `sector`, `coord`.
Example TXT:

```text
Wreck archive: {{dest_sector}}, {{dest_coord}}.
NODE: {{dest_id}}
SECTOR: {{dest_sector}}
```

Rendering happens **during compilation**, under a private frozen text reference.
Reading does not choose the destination again. After applying bindings, any
unresolved reserved `{{name}}` token (`[a-z][a-z0-9_]*`) is always rejected,
even without a `spatial_bindings` block. This checks `line`, inline text and
referenced resources, including active authored files, with package/file/field
diagnostics. Braces outside that syntax are literals. Missing references also
fail before play. No global name substitutions or prose
recognition occur. `[SECTOR_VAELOR]` remains an inert editorial placeholder.
Compiling text neither delivers nor imports it.

## Hosts, reservations and consumption

All installed `force=true` pieces are validated as essential. Optional
`essential=true` requires a valid force policy. Existing `primary_intel`,
`secondary_lore_docs`, candidates, constraints, channels, preferences, weights,
policies and deadlines remain. Validation proves a host/channel at an eligible
time; it does not guarantee player behaviour or an everlasting opportunity.

Optional `constraints.anchor_distances` filters document hosts by inclusive 3D
Euclidean bounds relative to certified authored IDs or unambiguous aliases,
including hidden/lazy `world_requirements` entities. Each nonempty-list entry
accepts only `anchor`, `min_ly`, `max_ly`; at least one finite nonnegative bound
is required, minimum defaults to zero, and entries combine by AND. Bootstrap
rejects invalid IDs, geometry, structure, booleans, nonfinite or reversed bounds
for optional pieces and singles too. Existing origin distances and regions keep
their meaning. `placement_rules.primary.host_selection: "seeded"` chooses an
essential reservation deterministically from the finite certified viable set;
default remains first sorted host. Runtime never substitutes another host for
a reservation. See [relative placement contract](design/lore-placement-anchors.md).

Historical queries use up to 64 sectors, including authored sites and a finite
search near the start and declared distances. A certified opportunity can be
reserved without materializing or revealing its host. If the search cannot
certify an opportunity, the game does not start. Budget exhaustion does not
claim galactic absence. Every essential file channel needs a nonempty body in
EN and ES, checked before headers and using the existing fallback to EN.
Salvage supports the `line` fallback when a reference is absent or its text is
empty; this does not apply to whitespace-only text or push channels. Headers
alone do not count as content. File-path/collision checks and optional documents'
previous behaviour remain. Essential `uplink_only` needs a physically valid LINK.

Only host, channel, sector and historical provenance are persisted for a
reservation. When its pool initializes, a piece whose policy permits placement
is prepared before visit closure. Late attempts respect windows and exhaustion.
A deadline may expire without delivery; the piece stays pending and never
reopens a pool. The selector materializes certified sites instead of creating
stations. The old private `_spawn_ad_hoc_candidate_for_forced_piece` delegates
to that selector for compatibility. Lore's ad hoc position samplers were removed.
`register_hidden_anchored_node` remains for existing structural recovery, whose
integration belongs to e5; this phase does not resolve F-DEAD-01.

## Intel and saves

`NODE` and authored blocks resolve IDs/names/aliases and materialize valid history.
Missing literals retain clues without creating stations. `LINK` shares one parser
between explicit import and reading, requiring physical endpoints and the cap.
It retains the 4D-1 operational contract: a valid route table need not match a
historical graph edge. Declarative `physical_link` does require one. `SECTOR`
adds regional intel and lazy materialization without revealing inventory.
`COORD` creates a `NAV_...` `nav_point`, never a station; nonfinite values fail.

Blocks containing only explicit instructions go to the line parser without an
extra corruption roll. A bare name/alias/ID block reveals authored content; the
historical bare-sector selector remains. An unresolved token stays as zero
confidence intel. Corrupt recovery keeps its roll and only discovers preexisting
hubs within its radius, excluding protected primary targets. It creates no
corrective installations. Scan and manual solve retain their deliberate exceptions.

The load policy is **reject installed catalogue changes**, including removal,
identity changes, text resources and package replacement. Compiled definitions
and texts are saved. For legacy content without new blocks, existing loaders
are consulted after fingerprint verification; requirement-bearing runtime uses
the snapshot. Save/load verifies the full fingerprint. Restoring the original
packages allows loading again. Saves are neither deleted nor historically
migrated. Schema 3 adds a required snapshot for new loads; older saves without
it are explicitly rejected. The V2 container, checksum, backup, progress,
identities and consumed resources remain.

## AMANECER and limits

| Category | Application |
| --- | --- |
| Supported | Tábano wreck as `ship` with stable identity and seeded position; documents restricted by ID; sector bindings; existing destination and validated edges. |
| Pending data adaptation | Optional JSON, EN/ES texts, regions/boxes, relations and real channels; making the destination reachable needs a specific certified route. |
| Editorial decision | Bruma's present state, destination's nature, fate of the seven people. |
| Unimplemented system | VAELOR as a star system with planets/components; dynamic physical conservation, chronology and community simulation. |

Bruma's existence can only be mapped to a playable kind after an editorial
decision; no wreck is imposed. Names alone do not turn VAELOR or its planets
into nodes. C2b installs only Elena Varela's arc and its approved historical Liria
in the working-tree catalogue. The bounded public journey did not discover its
clue; see the [C2b review](testing/amanecer-productive-review.md). Other AMANECER
arcs and singles remain inactive, with their original manuscripts preserved. There is no editor,
universal mod manager, new channel, new scan or general rebalance.
