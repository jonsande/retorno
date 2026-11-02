# RETORNO documentation

This index describes the documentation currently stored under `docs/` and its
verification status. It does not make historical or partially outdated guides
authoritative merely by linking to them.

Spanish version: [README.es.md](README.es.md)

## Status labels

- **Verified:** checked against the implementation for the stated scope.
- **Partially verified:** useful material remains, but some claims require a
  later technical review.
- **Pending review:** known outdated or unverified claims prevent using the
  document as a description of current behavior.
- **Normative guide:** defines a project convention rather than runtime
  behavior.

## Current technical reference

| Document | Purpose | Status |
| --- | --- | --- |
| [Physical universe and procedural generation](systems/world-generation.md) | Canonical reference for the spatial model, regions, sectors, worldgen, topology, authored content, and determinism. | **Verified** against production code at `3658577`, active data, and later Phase 3A.1 tests. It records known gaps and the sector diagnostic's materializing effect; it does not fully cover navigation, lore, or failsafes. |
| [Universo físico y generación procedural](systems/world-generation.es.md) | Spanish counterpart of the universe and worldgen reference. | **Verified**; maintained as a language pair with the English document. |
| [Discovery, navigation, and intel](systems/discovery-navigation-intel.md) | Canonical reference for player knowledge, scan, route solve, uplink, intel import, travel, narrative protection, and failsafes. | **Verified** against production code and focused tests. It distinguishes implemented behavior, one failing fixture expectation, and pending decisions; no arcs are currently active. |
| [Descubrimiento, navegación e intel](systems/discovery-navigation-intel.es.md) | Spanish counterpart of the discovery and navigation reference. | **Verified**; maintained as a language pair with the English document. |
| [Lore scheduler, arcs, and singles](systems/lore-scheduler.md) | Canonical reference for narrative placement, channels, forcing, pools, unlocks, and active content. | **Verified** against production code, active data, and safe tests. It separates fixture evidence, real content, and end-to-end gaps; it records three outdated fixtures without changing product or tests. |
| [Scheduler de lore, arcos y singles](systems/lore-scheduler.es.md) | Spanish counterpart of the narrative scheduler reference. | **Verified**; maintained as a language pair with the English document. |
| [Content loading contract](content-loading.md) | Defines which content paths the current loaders read directly, non-recursively, or recursively; also inventories inactive arc and location templates. | **Verified** against `src/retorno/runtime/data_loader.py`, `src/retorno/bootstrap.py`, `src/retorno/runtime/startup.py`, and the data tree at commit `2ffb1ab`. |
| [Contrato de carga de contenido](content-loading.es.md) | Spanish counterpart of the content loading contract. | **Verified**; maintained as a language pair with the English document. |

## Existing guides

| Document | Purpose | Status and limitations |
| --- | --- | --- |
| [Arcs and `corridor_01.json`](arcs.md) / [ES](arcs.es.md) | Arc and single authoring guide. | **Pending review.** It contains reusable schema examples, but currently points to inactive template content and describes obsolete placement paths, force guarantees, protection scope, and single weighting. Do not treat it as current runtime architecture. |
| [How intel and lore are acquired](intel_lore.md) / [ES](intel_lore.es.md) | Overview of player-facing intel and lore sources. | **Pending review.** Scan and import sections contain useful material, but command syntax, arc flow, links, and single weighting need correction. |
| [Textual UI guide](textual.md) / [ES](textual.es.md) | Panels, shortcuts, focus, and autocomplete. | **Partially verified.** No discrepancy was identified in the initial audit, but it was not revalidated comprehensively during the content-loading phase. |
| [Manuals style guide](manuals_style_guide.md) | Structure and language-pair conventions for diegetic manuals in `data/manuals/`. | **Normative guide.** It does not describe runtime behavior. |

## Documentation boundaries

- Root `readme.md` and `readme.es.md` provide project entry points,
  installation, and command summaries. Their full command parity remains to be
  reviewed.
- `data/manuals/` contains diegetic manuals loaded into the in-game filesystem;
  it is runtime content, not a replacement for technical documentation.
- `data/lore/` contains narrative runtime assets. Most files are loaded only
  through explicit references from active content or a dedicated loader.
- `BUGS.md`, `TODO.md`, `DONE.md`, and `borrame.md` are working or historical
  notes. They are not normative descriptions of current behavior.

## Planned documentation work

The canonical scheduler reference now reconstructs the unified implementation.
Later phases should use it to revise the historical arc/lore guides, deepen
failsafe documentation, and add a global verification matrix linking behavior
to tests. Proposals should live separately from documents that describe
implemented behavior.
