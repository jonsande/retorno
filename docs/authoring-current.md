# RETORNO — Current guide to authoring arcs, singles and locations

**4D-3e5c-C preparation · 2026-11-07 · Status: working guide checked against published contracts; the first complete authored story has not yet been validated.**
[Español](authoring-current.es.md)

This guide supersedes the historical examples in `docs/arcs.md` and the older arc/single authoring notes as a **practical guide**. It does not supersede the implementation or technical contracts: [`narrative-world-contract.md`](narrative-world-contract.md), [`systems/lore-scheduler.md`](systems/lore-scheduler.md), [`systems/historical-information.md`](systems/historical-information.md), and [`systems/radio-spacetime.md`](systems/radio-spacetime.md). Resolve discrepancies against productive code before approving new content.

## 1. What is actually loaded

| Resource | Active location | Rule |
| --- | --- | --- |
| Authored locations | `data/locations/*.json` | Direct, nonrecursive scan. Five active locations at present. |
| Arcs | `data/arcs/*.json` | Direct, nonrecursive scan. **Zero** active arcs at present. |
| Singles | `data/lore/singles/index.json` | Only the entries in this index. Five active singles at present. |
| Narrative text | `data/lore/...` | Only assets explicitly referenced by installed content. |

JSON in `data/arcs/templates/` and `data/locations/templates/` is **inactive**. Copying a template to the root without checking references, constraints and physical consequences may fail compilation or change the universe of new games. Installed content is part of the save's catalog identity and is validated on load: use **fresh test games** for editorial changes; never erase saves automatically.

## 2. Five distinct concepts

1. **Literary mention:** a place name in prose creates no station.
2. **Physical declaration:** an authored location or a `world_requirements` entity contributes to the historical universe before it is explored.
3. **Document placement:** the scheduler may reserve a piece of lore on a certified historical host without revealing it.
4. **Player knowledge:** scan, reading/import, radio and other legitimate actions reveal facts.
5. **Operational route:** importing a valid, certified `LINK` may publish a traversable navigation edge; this need not be a historical physical edge, but must satisfy geometry and knowledge rules.

Never fabricate a historic installation after the fact to place a story. Forced-placement selection uses pre-existing hosts and can leave a piece pending if constraints are unmet. Historical existence also does not guarantee access.

## 3. Declaring physical entities and relationships

Installed locations, arcs and singles may use a root-level `world_requirements` block (`narrative-world-v1`). Declare each entity **once**; use `references` elsewhere instead of duplicate declarations. Executable examples: `tests/fixtures/narrative_world/alpha.json` and `beta.json`.

Position modes: `fixed_ly`, `box_ly`, and `offset_from` with `offset_box_ly`; sector and `regions_any` filters are supported. Relations: `near`, `historical_association`, and `physical_link`. The latter **verifies an existing worldgen-authorized edge**; it does not add a new edge. These fields do not simulate history, star systems, or populations.

`claims` may carry rumors or nonbinding assertions, but do not establish existence or prove survivors. Variable positions are determined from seed and installed catalog before play, with validation and bounded search. Canonical authored IDs remain stable; short public IDs (`P-...`) are player-facing and **do not replace canonical references** in authored `LINK`, `NODE` or JSON.

## 4. Arcs

An active `data/arcs/<arc_id>.json` may contain `primary_intel` and `secondary_lore_docs`, each with placement and delivery rules. A `primary_intel` of `kind: "link"` carrying `LINK: SOURCE -> DESTINATION` is the best-characterized navigation arc form. Both endpoints must identify real sites and the current hop cap is 45 ly.

`placement_rules.primary` and `.secondary` may filter hosts through `candidates`, `require_kind_any`, `avoid_node_ids`, and `max_hops_from_start`. Pieces may carry `constraints`, such as `min_year`, `max_year`, `min_dist_ly`, `max_dist_ly`, and `regions_any`. `secondary.count` **limits placements**, not story order, and does not wait for the primary. **There is no automatic dependency graph between documents.**

`force=true` means placement is attempted under `force_policy` (`soft`, `deadline`, or `hard`), **not** guaranteed reception, arrival, or reading. `force=true` with policy `none` supplies no useful placement route. All physical constraints and one-shot windows remain binding; depleted pools are not reopened. Bootstrap verifies an opportunity for essential pieces, not that the player will discover them.

## 5. Singles

Entries in `data/lore/singles/index.json` use `single_id` and may define `weight`, `channels`, `constraints`, files and EN/ES content. Singles do not use arc-specific `placement_rules` and do not automatically unlock a primary.

Under current balance, **each nonforced piece** independently rolls once per game year with `p = clamp(0.05 × max(weight, 0), 0, 1)` when eligible. `weight: 0.4` means 2% per eligible evaluation, **not** 40% of a weighted pool. A success chooses an available host; it does not immediately deliver the text. A single may never appear during a given game.

## 6. Channels, clues and radio

| Channel | Primary behavior |
| --- | --- |
| `salvage_data` | Drone recovery and remote-file reading; requires a salvage-capable host. |
| `uplink_only` | Publishes a valid `LINK` via uplink at station, relay or waystation; no lore file. |
| `ship_os_mail` | Scheduler mail delivered by a permitted trigger; reading is separate. |
| `captured_signal` | Signal delivery via the communications system under authorized triggers. |
| `station_broadcast` | Station/relay/waystation broadcast subject to context and reception. |

Arcs use `allowed_channels`; singles use `channels`. A placed piece still needs the correct trigger and operational gates. Text may include `LINK:`, `NODE:`, `SECTOR:`, or `COORD:`. Authored text is not imported into navigation until the player reads or imports it; use the supported syntax rather than inventing a format.

**Authored historical radio:** optional `radio_emitters` (`radio-emitters-v1`) declares transmitters/emissions and emission epochs in installed locations, arcs, or singles. An explicit declaration **overrides all procedural radio history for the same host**, even with `emissions: []`. Signals obey actual range and propagation delay; an old signal does not prove anyone is currently alive. This is distinct from merely choosing a scheduler signal channel. Follow `docs/systems/radio-spacetime.md` examples.

**Procedural information:** B1 maintains certified historical files/navigation records; B2 generates communications histories. Authored stories must not rewrite those facts based on player progress or depict a calculated solution as evidence of historic human traffic. Follow `C-DATA-004`: "How does the ship know this?"

## 7. Minimal test for 4D-3e5c-C

First build **one small, isolated story** as an opt-in test fixture, not active content: station, ship/wreck, relay; one arc with primary and secondary pieces; one or two singles. Distribute clues through at least two legitimate channels among salvage, uplink and radio. Only add `world_requirements`, bindings and relationships when actually needed. The past must precede observation and must not depend on visit order.

Verify at least: seed-based catalog compilation; no advance disclosure; placement and triggers without fabricated hosts; real import and hop cap; coherent EN/ES narrative; save/load; no duplicate delivery; and a public-command walkthrough that acquires information and progresses without debug. Correct content constraints before expanding Python when a fixture fails.

Reference regression:

```bash
cd /home/jon/prog/retorno_case/retorno
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
```

Do not install the first experiment into production roots: active arcs/locations affect new worlds and may invalidate previous test saves. Decide what to promote only after validating the fixture and experience.

## 8. Known open decisions

Universal exploration continuity is **not proven** (see [`design/exploration-softlock-research.md`](design/exploration-softlock-research.md)); F-DEAD-01 level 2 is postponed. Do not address authored-delivery problems by inventing stations, routes, or transmissions. Do not activate AMANECER or other archived material by copying templates. Older guides remain historical context, not the current contract.
