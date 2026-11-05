# Procedural preexistence — Phase 4D-3e1

**4D-3e2 update:** this document retains historical evidence from its phase.
The current productive contract is [Historical worldgen integration](historical-worldgen-integration.md).
The prototype now uses the shared core and distinguishes certification by scope/reasons;
the conditional legacy catalog lives in test fixtures. Productive limitations below
describe the earlier state, not the current runtime.

Spanish version: [procedural-preexistence.es.md](procedural-preexistence.es.md).

Status: **safe partial implementation and reproducible audit**, on `main` at
`dd5b471`, 2026-11-05. The checkout was initially clean. The root README is
`readme.md`; the requested `STEPS.md` is absent. Canon was reviewed in
`docs/canon/universo.md` and `guia_coherencia.md`, particularly `C-WORLD-001`,
`C-INF-004` and `C-DATA-002`. No canon, player command, UI, audio, balance,
save schema or production recovery behavior changes here. F-DEAD-01 stays open.

## Approved decisions

Four facts are separate: a universe-determined site, a materialized physical
node, a player-known location, and a published operational route. Lazy
calculation is valid only when later recovery needs do not determine historical
existence. A reproducible provisional forecast is insufficient.

Scan negatives do not prove absence. Future observation reliability must account
for repeated observations and sensor condition without requiring systematic
retries of an invisible lottery. F-DEAD-01 addresses structural exploration
continuity, never scrap, energy, repairs, fuel availability or survival.
Spatial/topological/procedural/informational eligibility is distinct from current
ship capability. Prefer nearby opportunities by complete directed access from
the ship; expand the search progressively without a permanent distance cutoff.
Budget exhaustion is incomplete search, not proof of absence. Rescue and universal
connectivity are not guaranteed. The 45 ly cap, canonical archetypes/densities,
primary protection and consumed/visited content remain binding.

## Implemented API and real guarantees

[`worldgen/catalog.py`](../../src/retorno/worldgen/catalog.py) exposes:

```python
catalog_sector(state, "S+020_+020_+000")  # SectorCatalog
catalog_sectors(state, ("S+020_+020_+000", "S+021_+020_+000"), max_sectors=64)
# CatalogResult(configuration_key, sectors, physical_nodes_examined)
```

`CatalogResult`, `SectorCatalog` and `SiteRecord` are frozen dataclasses with
independent tuple/value data. Requests are explicit finite sequences, validated
before inspection; duplicates collapse and sectors sort canonically. The raw
sequence length must fit the positive technical `max_sectors` bound. Exceeding
it raises `ValueError`; it never establishes absence or a gameplay radius.
One sector query does not expand to the generator's 3×3 XY neighborhood.

| `SiteStatus` | Meaning |
| --- | --- |
| `physical` | Observed in `space.nodes` by actual spatial membership. Includes authored and technical nodes; not a statement of recovery eligibility. |
| `verified_procedural` | Contract category for a certified unmaterialized site. **Never emitted in this version.** Legacy generation cannot guarantee it. |
| `conditional` | Current baseline slot/kind forecast, with its canonical sample and unresolved existence conditions. Never a reservation or permission to insert. |
| `inadmissible` | A sampled new position is already physically occupied in this snapshot; not usable as a distinct new site. Not a permanent nonexistence proof. |

The sampler is shared with `generator.py`: seed, sector, archetype, slot index
and kind feed the existing BLAKE2b seed; two uniform draws then a Gaussian Z
draw retain precisely the old RNG order, including continuation for id allocation.
Catalog inspection never calls the allocator, salvage/module generation or a
writer. `_select_archetype`, `_plan_sector_kinds`, canonical loaders, sector
parsing and physical region functions are reused. A detached indexed read view,
as used by the existing chain planner, avoids rescanning all nodes per sector.

Procedural `key` identifies a **conditional sample address**, derived from seed,
configuration, generation sector, baseline archetype, index and kind. It does
not depend on attempts, resource/capability state, time, mutable RNG counters,
ship distance, query order, sets or state dictionary iteration. A configuration
fingerprint includes templates, archetypes, sector size, physical region mapping
and explicitly ordered weighted-choice entries. Weighted dictionary order is
already a legacy configuration semantic; changing it is a configuration change,
not merely rearranging state dictionaries. Keys are scoped to this algorithm and
configuration, not a promise across future generator revisions.

The same address always has the same sample within that scope, but occupancy or
guardrails may change which addresses appear in a forecast. `node_id` is `None`
for all samples; no collision-dependent id is promised. Physical records use a
separate seed/id key and never claim reconstructed slot provenance. Changing a
save's seed cannot recover its original generation history.

For physical nodes, `generation_sector_id=None`: legacy metadata records spatial
membership, not reliable creation provenance. For samples, generation and actual
physical sectors are both explicit, including Z outliers. Sector `region` owns
the generation template; a record's `region` follows actual coordinates. A sphere
boundary can cross a sector even without Z outflow. No type is substituted to
make recovery possible. Generated sectors return physical records only; no
remaining-slot estimate authorizes additions after their generation pass closed.

**The catalog is internal world evidence, not a recovery selector or player
intel API.** It does not assess protected primaries, route access, pools or
information sources. Every sector explicitly reports those limitations. A
protected physical target may be inventoried internally; querying never reveals
it to the player. A future consumer must apply primary protection, source
validation and directed route checks before using any record. `physical` does
not grant such approval. A missing or empty forecast is not a spatial void claim;
missing configuration is reported, and nonfinite physical coordinates reject the
request rather than silently hiding invalid state.

No query changes nodes, generated flags, metadata, topology, pools, salvage,
filesystem, intel/knowledge, history, counters, recovery, global RNG or time.
All RNGs are local; no global cache or persisted catalog is added. Callers must
supply a coherent state/configuration snapshot; concurrent mutation is not
supported. Save/load simply preserves the consulted state under the existing schema.

## Audit of current generation: nine findings

1. **Archetype:** `_select_archetype` is seed/sector/center-region/configuration
   deterministic without overrides. The first origin-containing request can
   override it; the catalog labels its baseline, not an invented final override.
2. **Quota/kinds:** all physically resident nodes, including authored, technical
   and previously materialized outliers, consume target total and kind caps.
   Existing playable hubs suppress a new playable hub roll. No extra slots exist.
3. **Ids:** 24-bit kind-prefixed bases collide against the entire physical registry;
   Greek suffixes and then another base resolve them. Radiation, salvage and names
   depend on the allocated id and are not certified by the sample key.
4. **Initial guardrail:** consumed once, based on the first request's cluster.
   Already generated sectors ignore later overrides. It can change ungenerated
   neighbors' archetypes/hub forcing, not merely topology.
5. **Coordinates:** X/Y are inside the generation cell; Gaussian Z is unbounded.
   An outlier is inserted globally but may be absent from its source sector's
   refreshed node metadata and consume a later sector's quota.
6. **Internal links:** built after cluster nodes are created, once per sector.
   Current residents and lexicographic playable/topology hub selection matter;
   later arrivals do not rebuild a closed internal graph.
7. **Intersector links:** neighboring same-Z pairs are processed with shared hub
   budgets, recorded before success and never retried. Identical node locations
   can have different links under different materialization orders.
8. **Inspection then materialization:** exact samples match when the relevant
   occupancy/guardrail/configuration context is unchanged. This is demonstrated
   for a remote disk sector, not guaranteed under arbitrary intervening generation.
9. **Stable facts:** conditional sampling addresses/coordinates and the current
   physical registry are inspectable. Unmaterialized existence, final kind/slot
   family, final ids, resources, hubs, topology and player discovery are not all
   determined independently of order. No verified latent locations are reservable
   under the demonstrated legacy contract.

Concrete regressions in
[`worldgen_preexistence_characterization_smoke.py`](../../tests/worldgen_preexistence_characterization_smoke.py):

| Seed and requests | Evidence |
| --- | --- |
| `2`: `(20,20,0)`, `(22,20,0)`, `(20,22,0)` versus reverse | Same nodes and evaluated pair set; four directed edge entries differ (two undirected edges). |
| `29`: `(1,0,0)`, `(-1,0,0)` versus reverse | Same generated union; `S+000_+001_+000` is `empty` versus `relay_corridor`, with different node ids. |
| `271828`: `(15126,0,0)`, `(15126,0,1)` versus reverse | `WRECK_E39D3C` samples Z=`10.057691279289713` from Z cell 0 into cell 1. Destination has one versus two nodes; source metadata omits the outlier. |
| `271828`: inspect `S+020_+020_+000`, then materialize | Station at `(205.04909961494286,207.116870031816,4.97869392003561)` and derelict match the unchanged-context forecast. An added authored hub changes the remaining kind/slot family. |
| Same slot with synthetic id collisions elsewhere | Coordinates agree; allocation chooses base, `_ALFA`, or another base. Node-specific radiation changes. |

## Scan and contextual planner boundary

No production scan changes. Base range remains 2.5 ly and existing detection
probabilities remain active. A future persistent observation needs 3D position,
effective radius, operational sensor condition, observation time, detected
contacts and the detection-model context needed to interpret a negative result.
Historical geometric coverage alone is not certainty of absence. The catalog
does not infer that an unvisited/ungenerated sector was never scanned.

`deadnode_opportunities.py` remains unchanged. Its `evaluate` gathers source
hardware/operator dependencies from the chain, adds critical-power and undock
conditions, and lowers status from `verified_mechanics` to `conditional` for
pending/unavailable dependencies. `compare_opportunities` prioritizes that status,
then compares distance/hops/nominal time and dependency sets. These practical
capability conditions can affect preference. That policy is **not the newly
approved structural eligibility policy**: damage and survival resources must
not reject a structural opportunity. Energy estimates do not currently reject
by available battery; travel scrap is a direct-charge zero, future repair/salvage
and economic feasibility remain unknown. Such estimates can survive as separate
advisory tools, without governing F-DEAD-01 acceptance. Sector centers in the old
planner are geometric probes, not catalog locations. No ranking or integration
changes are made here.

## Next subphases and decisions still needed

| Phase | Proposed work and dependency |
| --- | --- |
| **4D-3e2** | Persist scan observations and specify reliability/negative evidence, save/load and EN/ES presentation. No density or detection-probability change implied. |
| **4D-3e3** | Integrate catalog evidence into opportunity search, progressively widen bounded sector families, use complete directed access, and separate structural eligibility from survival/capability estimates. Requires resolving latent-site invariants before any conditional sample can be used as preexistent infrastructure. |
| **4D-3e4** | Detached preparation, stable reservations, atomic/idempotent materialization, closed topology and pair budgets, persistence, source-window protection and knowledge preservation. Revalidate stale proposals; no paid attempt or reveal on failed preparation. |

The audit adds a necessary worldgen decision before verified latent use in e3:

- **Existing-only integration first:** safely search physical locations now;
  fewer possible opportunities and no promise that suitable infrastructure exists.
- **Immutable procedural manifest:** derive slot families from a fixed authored
  baseline and immutable guardrail policy, retain provenance and separate stable
  addresses from allocated ids. Broad generator work; may alter layouts, quotas
  and future-save compatibility. Needs authorization and a topology contract.
- **Persist a creation-time manifest/reservations:** stabilizes an established
  baseline but does not by itself eliminate dependence on which manifest is
  created first. It only satisfies preexistence if its governing rules are fixed
  independently of recovery; also needs authorization.

Extra latent slots/density are a separate developer decision, not a remedy
introduced here. Clamping Gaussian Z alone would change distribution and would
not solve guardrails, foreign insertions, collisions or topology. No redesign,
density changes or regeneration of existing sectors is performed. Real saves
are never removed. The bounded pure part is the deliverable allowed by the
subphase's intervention limit, not completion of the full preexistence invariant.

## Verification and file handoff

Canonical interpreter: `/home/jon/prog/retorno_case/retorno_venv/bin/python`;
run with `PYTHONPATH=src`. The two new smoke scripts contain **9 characterization
and 17 catalog groups**. Catalog coverage includes frozen results, ordered
queries/dictionaries, full pickle/RNG purity, forbidden writers, three regions,
all five archetypes and 0–3 slots, actual/template region boundaries, generated
and authored nodes, missing origin hub, consumed pools, damaged/resource-empty
ships, protected-primary knowledge preservation, three temporary save cycles,
three subprocess hash seeds (`1/7/99`), technical bounds and invalid state.

Also passed: `worldgen_sparse_archetypes`, `worldgen_modules_pool`,
`procedural_radiation`, `galaxy_physical_model`, `route_hop_cap`,
`known_routes_integrity`, `nav_abort_waypoint_cleanup`,
`route_solve_out_of_range_origins`, `sector_intel_validation`, `scan_job`,
`sensor_detection_factor`, `save_load`, `deadnode_chain_planner`,
`deadnode_chain_detours`, `deadnode_opportunity_selection` (all `_smoke.py`).
The observed order dependencies are passing characterizations, not changed
mechanics or unexplained test failures. No real save files are used.

An additional comparison against the generator loaded directly from `HEAD`
confirmed identical whole serialized GameState after eight requests in forward
and reverse order for seeds `2`, `29`, `271828` (six independent runs). The
shared-sampler extraction preserves productive generation, including its known
order dependencies.

Benchmark: `tests/worldgen_preexistence_catalog_smoke.py --benchmark`, seed
`271828`, 3 calls/cell, excluding fixture construction. Peak incremental Python
memory is a separate tracemalloc call. Background nodes are synthetic remote
derelicts; four physical authored/technical nodes exist before adding them.
Time is a measurement, not a latency guarantee:

| Background | Sectors | Median / max ms | Peak KiB |
| --- | --- | --- | --- |
| 0 | 1 / 9 / 64 | 0.906/0.994 · 1.898/2.166 · 8.790/8.980 | 21.7 / 31.3 / 73.9 |
| 1000 | 1 / 9 / 64 | 2.906/3.014 · 4.139/4.192 · 10.401/10.799 | 52.1 / 63.4 / 105.9 |
| 3000 | 1 / 9 / 64 | 7.269/7.462 · 7.664/8.354 · 14.647/14.758 | 210.9 / 223.3 / 272.4 |

One pass examines N physical nodes, then requested sectors only. Auxiliary
memory is O(N + requested sectors + returned records); sorting adds normal
ordering costs. No whole-universe generation or deep GameState copy occurs.

| Files (paths relative to repository) | Change |
| --- | --- |
| `src/retorno/worldgen/catalog.py` | New bounded typed read-only evidence API. |
| `src/retorno/worldgen/generator.py` | Extract identical canonical coordinate/RNG sampler for shared use. |
| `tests/worldgen_preexistence_characterization_smoke.py` | Nine executable legacy-dependency witnesses. |
| `tests/worldgen_preexistence_catalog_smoke.py` | Seventeen API regression groups and optional benchmark. |
| `docs/design/procedural-preexistence.md`, `.es.md` | This bilingual design, evidence, limitations and handoff. |
| `docs/design/navigation-recovery-contract.md`, `.es.md` | Record binding 4D-3e1 decisions and safe partial status. |
| `docs/design/deadnode-chain-planner.md`, `.es.md` | Clarify current planner divergence from the new structural contract. |
| `docs/systems/world-generation.md`, `.es.md` | Link the catalog and replace previously untested order/Z claims with evidence. |
| `docs/README.md`, `README.es.md` | Index the new bilingual reference. |

Manuals and in-game help require no edits: no player-visible command, text,
localization key or behavior changes. Git validation and the changed-files-only
ZIP are reported in the delivery; no staging, commit or push is performed.
