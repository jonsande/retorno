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
| [Discovery, navigation, and intel](systems/discovery-navigation-intel.md) | Canonical reference for player knowledge, scan, route solve, uplink, intel import, travel, narrative protection, and failsafes. | **Verified** against production code and focused tests, including repaired breadcrumb and exact-undiscovered-physical-id route-solve characterizations; no arcs are currently active. |
| [Descubrimiento, navegación e intel](systems/discovery-navigation-intel.es.md) | Spanish counterpart of the discovery and navigation reference. | **Verified**; maintained as a language pair with the English document. |
| [Lore scheduler, arcs, and singles](systems/lore-scheduler.md) | Canonical reference for narrative placement, channels, forcing, pools, unlocks, and active content. | **Verified** against production code, active data, and safe tests. All three historical fixtures are repaired with synthetic content; templates remain inactive. |
| [Scheduler de lore, arcos y singles](systems/lore-scheduler.es.md) | Spanish counterpart of the narrative scheduler reference. | **Verified**; maintained as a language pair with the English document. |
| [Exploration failsafes, deadnodes, and recovery](systems/exploration-failsafes.md) | Canonical reference for global recovery, deadnodes, forced-lore ad hoc nodes, guardrails, and supporting fallbacks. | **Verified** against production code and isolated tests. It separates guarantees, functional risks, and pending decisions; it makes no global progress promise. |
| [Failsafes de exploración, deadnodes y recuperación](systems/exploration-failsafes.es.md) | Spanish counterpart of the failsafes and recovery reference. | **Verified**; maintained as a language pair with the English document. |
| [Content loading contract](content-loading.md) | Defines which content paths the current loaders read directly, non-recursively, or recursively; also inventories inactive arc and location templates. | **Verified** against `src/retorno/runtime/data_loader.py`, `src/retorno/bootstrap.py`, `src/retorno/runtime/startup.py`, and the data tree at commit `2ffb1ab`. |
| [Contrato de carga de contenido](content-loading.es.md) | Spanish counterpart of the content loading contract. | **Verified**; maintained as a language pair with the English document. |
| [Cross-system audit and stabilization plan](testing/stabilization-audit.md) | Executive matrix of defects, risks, and decisions, with dependencies, priorities, fixture treatment, and a minimum integration suite. | **Verified** against canonical references, production code, existing tests, and isolated probes. It is an engineering plan, not a mechanics change. |
| [Auditoría transversal y plan de estabilización](testing/stabilization-audit.es.md) | Spanish counterpart of the cross-system audit. | **Verified**; maintained as a language pair with the English document. |
| [Navigation and recovery design contract](design/navigation-recovery-contract.md) | Approved decisions for routes, recovery, `comms`/`radiod`, reception, services, narrative protection, localization, and pre-alpha saves, with matrices and a 4C plan. | **Approved contract**; explicitly distinguishes current behavior, divergences, and future work. It does not claim that corrections are implemented. |
| [Contrato de diseño de navegación y recuperación](design/navigation-recovery-contract.es.md) | Spanish counterpart of the design contract. | **Verified**; maintained as a language pair with the English document. |

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

The cross-system audit and design contract define the stabilization sequence.
The proposed first Phase 4C correction prevents `uplink_only` from consuming a
primary without a valid effect. Later phases must keep the matrix and EN/ES
parity current while separating implemented behavior from proposals.
