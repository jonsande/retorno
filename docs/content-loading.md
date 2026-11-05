> **Implemented 4D-3e4 update (2026-11-05).** Activation remains nonrecursive. Bootstrap also collects optional arc/single requirements, checks required resources and keeps a fingerprint and snapshot; save/load rejects catalogue changes. Older statements about late reading and empty resources describe the isolated loader, not new-game validation. The current contract and executable examples are [Physical narrative requirements](narrative-world-contract.md). The earlier body retained below is historical wherever it contradicts this update.

# Content loading contract

Status: **implemented behavior, verified at commit `2ffb1ab`**.

Spanish version: [content-loading.es.md](content-loading.es.md)

This document records where RETORNO currently loads universe and narrative
content from. It describes the implementation; it does not approve a permanent
folder policy or declare inactive files disposable.

## Loading modes

- **Direct file:** the code opens one exact path. Sibling files are not
  discovered automatically.
- **Explicit directory, non-recursive:** the code applies `Path.glob("*.json")`
  to one named directory. JSON files in child directories are excluded.
- **Recursive directory:** the code applies `Path.rglob(...)`; matching files
  below child directories are included.
- **Explicit reference:** an active definition contains a relative path and the
  code opens that exact asset. Merely placing an asset in the referenced tree
  does not activate it.

## Implemented contract

The main implementation is
[`src/retorno/runtime/data_loader.py`](../src/retorno/runtime/data_loader.py).

| Content | Active source | Loading mode | Current consequence |
| --- | --- | --- | --- |
| Authored locations | `data/locations/*.json` | Explicit directory, non-recursive (`load_locations`) | The five root JSON files are read. `data/locations/templates/*.json` is excluded. |
| Arcs | `data/arcs/*.json` | Explicit directory, non-recursive (`load_arcs`) | There are currently no root JSON files, so no arc definition is loaded. `data/arcs/templates/*.json` is excluded. |
| Singles | `data/lore/singles/index.json` | Direct file (`load_singles`) | Only entries in the index participate. Adjacent text assets require an explicit `content_ref_*`. |
| Worldgen region templates | `data/worldgen/templates/*.json` | Explicit directory, non-recursive (`load_worldgen_templates`) | `bulge`, `disk`, and `halo` are active inputs to sector generation. This `templates/` directory is deliberately named by the loader. |
| Worldgen archetypes | `data/worldgen/archetypes/*.json` | Explicit directory, non-recursive (`load_worldgen_archetypes`) | The five archetype JSON files are active inputs to sector generation. |
| Modules | `data/modules.json` | Direct file (`load_modules`) | Module definitions are loaded from this single JSON object. |
| Per-node loot | `data/loot/<normalized_node_id>.json` | Direct, computed file (`load_loot`) | No directory scan occurs. The repository currently has no `data/loot/` files. |
| Location and scheduled lore assets | Paths such as `data/lore/...` named by `content_ref` or `content_ref_en/es` | Explicit reference | `data/lore/` is not generally scanned. An asset participates only when active content refers to it or a dedicated loader opens it. |
| Startup and hibernation sequences | Fixed names under `data/lore/startup/` and `data/lore/hibernate/` | Direct files with locale fallback | `runtime/startup.py` tries the requested locale, then EN, then ES. Other files in those directories are not discovered by this loader. |
| Diegetic manuals | `data/manuals/**/*.txt` | Recursive directory | `bootstrap.py` loads every text file recursively into `/manuals/` in the in-game filesystem. |

The authored location definitions are consumed during bootstrap by
[`src/retorno/bootstrap.py`](../src/retorno/bootstrap.py). Worldgen templates
and archetypes are requested by
[`src/retorno/worldgen/generator.py`](../src/retorno/worldgen/generator.py).
Lore references and arc/single definitions are consumed by
[`src/retorno/core/lore.py`](../src/retorno/core/lore.py).

Directory names alone do not determine activation. In particular:

- `data/arcs/templates/` and `data/locations/templates/` are not traversed by
  their loaders and do not automatically participate in a run.
- `data/worldgen/templates/` does participate because the loader explicitly
  selects that exact directory.
- Making either authored-content loader recursive would change runtime
  behavior and is outside this contract.

## Active authored locations

The current root definitions are `ARCHIVE_01`, `ECHO_7`, `HARBOR_12`,
`RETORNO_SHIP`, and `UNKNOWN` (`start_00.json`). `RETORNO_SHIP` also supplies
ship filesystem content during bootstrap; it is not treated as an ordinary
world destination.

## Inactive arc template inventory

All four files below are excluded by the current non-recursive arc loader.
“Likely purpose” is an audit inference, not an approved lifecycle label.

| File / arc id | Location references and dependencies | Likely purpose |
| --- | --- | --- |
| `blackout_01.json` / `blackout_01` | Primary `BLACKOUT_12 -> VAULT_09`; candidate `blackout_12`; two EN/ES lore pairs under `data/lore/packs/blackout_01/`. Neither endpoint has a location definition in the current data tree. | Incomplete or parked arc draft used to exercise constraints and multiple secondary documents. |
| `carnaval_cache_01.json` / `carnaval_cache_01` | Primary `ANCORA -> CARNAVAL_34`; both endpoints exist only under `data/locations/templates/`; primary EN/ES lore pair under `data/lore/packs/carnaval_cache_01/`. | Parked authored-location arc draft with deadline forcing. |
| `corridor_01.json` / `corridor_01` | Primary `HARBOR_12 -> ARCHIVE_01`; both endpoints have active root definitions and inactive template variants; two EN/ES lore pairs under `data/lore/packs/corridor_01/`. | Former active/reference arc and main schema example in `docs/arcs*`; currently parked. |
| `example_unforced.json` / `example_unforced` | Primary `HARBOR_12 -> GLASSHOLLOW`; `HARBOR_12` is active and `GLASSHOLLOW` is template-only; four EN/ES lore pairs under `data/lore/packs/example_unforced/`. | Explicit reusable example for non-forced pieces, with an inactive authored target. |

All referenced lore files listed above currently exist. This confirms asset
presence, not that the inactive arc schemas are fully valid against current
scheduler semantics.

## Inactive authored-location template inventory

All eleven files below are excluded by the current non-recursive location
loader.

| File / node id | Dependencies and relationships | Likely purpose |
| --- | --- | --- |
| `ancora.json` / `ANCORA` | Source of the inactive `carnaval_cache_01` link; referenced by the template `HARBOR_12` uplink table. | Parked arc-supporting station. |
| `archive_01.json` / `ARCHIVE_01` | Inactive variant of active `ARCHIVE_01`; references the same EN/ES last-signal assets but lacks the active variant's drone salvage fields. | Older reference or tuning variant, not a unique destination. |
| `carnaval_34.json` / `CARNAVAL_34` | Destination of inactive `carnaval_cache_01`. | Parked arc destination. |
| `curl_12.json` / `CURL_12` | Destination of an embedded `LINK` in template `ECHO_7`. | Parked endpoint from an older authored discovery chain. |
| `derelict_a3.json` / `DERELICT_A3` | No explicit dependency from the inventoried templates. | Standalone authored-location example or draft. |
| `echo_7.json` / `ECHO_7` | Inactive variant of active `ECHO_7`; adds four fragments and one EN mail, including `ECHO_7 -> CURL_12`. Referenced assets exist. | Older narrative-rich variant or reusable integration example. |
| `glasshollow.json` / `GLASSHOLLOW` | Destination of `example_unforced`; candidate in template uplink tables. | Parked arc/uplink destination. |
| `harbor_12.json` / `HARBOR_12` | Inactive variant of active `HARBOR_12`; contains an authored uplink table for `ANCORA`, `MOURN_ANCHOR`, `VEIL_GARDEN`, `SABLE_CHAPEL`, and `GLASSHOLLOW`. | Older authored-network or uplink example. |
| `mourn_anchor.json` / `MOURN_ANCHOR` | Referenced by template `HARBOR_12` and `SABLE_CHAPEL` uplink tables. | Parked authored-network relay. |
| `sable_chapel.json` / `SABLE_CHAPEL` | Referenced by and contains template uplink candidates; its own table also lists `SABLE_CHAPEL`. | Parked authored-network waystation; self-reference requires review before activation. |
| `veil_garden.json` / `VEIL_GARDEN` | Referenced by template `HARBOR_12` and `SABLE_CHAPEL` uplink tables. | Parked authored-network station. |

The repository history shows that commit `36911df` moved three arcs and ten
locations into these `templates/` directories without changing the loaders.
That supports deliberate deactivation during the pre-worldgen rebalance, but
does not by itself define their final lifecycle or quality.

## Proposed future classification

No files are moved by this proposal. Before reorganizing content, assign each
definition an explicit reviewed status:

1. **Active:** production content intended to be discovered by a loader and
   covered by integration tests. Its directory must match the documented
   loader contract.
2. **Draft:** incomplete or intentionally disabled production content. It may
   depend on inactive nodes or evolving schemas and must not be loader-visible.
3. **Reusable example:** minimal, maintained authoring material intended for
   documentation or tests, not for normal runs. Examples should state which
   schema/version they demonstrate and must not masquerade as active content.

Candidate triage, subject to review:

- `example_unforced` is the clearest reusable-example candidate.
- `blackout_01` and `carnaval_cache_01` are draft candidates because their
  location dependencies are not active; `corridor_01` needs a product decision
  because its endpoints are active and it is also used as documentation.
- Template variants of `ARCHIVE_01`, `ECHO_7`, and `HARBOR_12` should be
  compared with their active definitions before classifying them as drafts or
  examples.
- The remaining template-only locations form dependencies for parked arcs or
  authored uplink networks and should be reviewed as groups, not activated
  individually.

