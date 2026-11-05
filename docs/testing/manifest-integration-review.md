# Review report — RETORNO 4D-3e2

Spanish: [manifest-integration-review.es.md](manifest-integration-review.es.md).
Implemented delivery, **pending external review**. Nothing staged, committed or
pushed. No additional decision is needed to present this implementation; its
policy was selected under the order's decision rule.

## Git and scope

Initial/final branch: `main`. Initial/final SHA:
`5cdde2804c74b7cf14d01120db84b097eb8e7b23`. Initial `git ls-remote origin refs/heads/main`
confirmed that SHA after an approved retry for sandbox DNS failure; this does
not assume the remote stays unchanged. The initial tree contained unrelated
untracked `narrative/` work. It was neither edited nor packaged. Final status
contains the 40 modified/new delivery files, unstaged, with `?? narrative/`
separate. `git diff --cached` is empty. `git diff --check`: **clean, no output**.
Canon v0.3, coherence guide, roadmap v1.1 D01–D20 and relevant contracts were
reviewed. No canon, active physical data, balance or narrative content was changed.

## Outcome and decisions

Productive worldgen uses `historical-world-v1` and an immutable definition.
Identity, position, kind, hubs, initial resources and edges are independent of
materialization order. The lazy API and explicit technical bounds remain;
querying/materializing does not discover sites or publish routes. One productive
core is shared with the experimental prototype entry point.

The authored base and historical UNKNOWN quota remain; its removed marker is
never resurrected. ECHO_7 is declared, RETORNO_SHIP stays special. Complete inverse
physical inventory preserves untruncated Z. The CPython 3.12 binary64 numerical
proof/domain are in the [technical contract](../design/historical-worldgen-integration.md).
Domain/work exhaustion raises rather than asserting empty space.

Fixed initial 3×3 priority followed by eight parity matchings retains pair rolls,
budgets and the 45 ly cap. This differs from order-dependent legacy and experimental
mutual top-k; differences are quantified below. No probabilities or quantities
were tuned to compensate. Resource seeds use full identity: exact outcomes change,
not balance parameters. These applied decisions remain externally reviewable.

Schema-3 saves pin definition/provenance, preserve depletion/knowledge and reject
schema 2, changed seed/rules/version or contradictory historical state. No migration
or automatic deletion; existing backup fallback remains. Minimal ID compatibility
resolves exact NODE/LINK IDs to physical sectors. Four Textual lines share the
CLI EN/ES seed guard to prevent corrupting a pinned universe; no UI redesign.

## Comparison and cost

Reused e1b comparator: ten seeds, 40 fixtures, 2,010 focus sectors.
[Full measurements](manifest-integration-measurements.json).

| Region | Edges legacy forward / reverse / prototype / productive | Nodes legacy forward / productive |
| --- | --- | --- |
| disk | 126 / 133 / 106 / 133 | 1040 / 1040 |
| bulge | 86 / 88 / 81 / 84 | 985 / 985 |
| halo | 39 / 41 / 37 / 43 | 746 / 748 |
| initial | 20 / 18 / 13 / 20 | 154 / 154 |

Initial components: 59/61/66/59; ECHO component node totals: 51/52/45/51. Halo
retains 11 Z outliers; two extra nodes (+0.27%) remove quota consumption from
foreign physical inflow. Four extra halo edges versus forward legacy are +10.3%
of its small baseline, +0.625 per 100 sectors, without a progression guarantee.
The sample does not prove universal distribution equivalence.

Procedural focus resources: scrap 76,980→77,363; modules 3,509→3,518; drones
419→456; aggregate radiation 8.2208→8.3801. Initial alone: scrap 2,768→3,064 and
drones 15→24 across 114 nodes. These new identity-seeded outcomes retain functions
and probability parameters; the variation is explicit.

Local median generation queries, 1/9/64 sectors, prototype→productive:
2.66→7.37 / 5.99→11.04 / 29.08→37.98 ms. Physical inverse:
4.61 / 7.23 / 21.36 ms. Public XY-union materialization:
19.89 / 34.00 / 103.36 ms. The contract includes measured cohorts and memory.
Single-query absolute overhead remains bounded; no further optimization campaign.

## Tests and failures

Canonical `/home/jon/prog/retorno_case/retorno_venv/bin/python`, `PYTHONPATH=src`.
61 smoke/style scripts/groups executed: final **60 pass, one confirmed existing
failure**, plus the successful comparator. The three modules without main had
their seven test functions explicitly called; empty imports are not coverage.
`pytest` is absent from this venv: its attempted invocation failed, so existing
executables were used without installing dependencies.

New integration passes **14 groups**: seeds 2/29/271828, complete forward/reverse/
grouped states, three hash-seed processes, partial expansion, repeated saves,
resource/pool depletion, authored without reveal, new IDs, intel formats, COORD,
bounds/atomicity, collisions and incompatibilities. Current scan, route solve,
uplink, lore/pools, protected-target, deadnode, bootstrap, route/distance and
save/load regressions pass. Prototype 17 groups, historical catalog 17 and legacy
witnesses 9 pass too.

The initial pass had four failures. Two fixtures were adapted without changing
assertions: declare distant UNKNOWN before bootstrap and distinguish synthetic
navigation markers from complete historical inventory. `textual_theme_smoke.py`
failed concurrently with `NoMatches('#header')`, then passed isolated; isolated
baseline also passed. The initial failure is retained and no unrelated UI race
is claimed fixed. `radiation_hull_smoke.py` still fails line 183, expecting a
radiation event after switching to CARNAVAL_34, absent from active content. The
same assertion fails in a clean copy of `5cdde28` using the same venv.
That unrelated defect was left unchanged. No known e2 integration failure remains.

[Results/output](manifest-integration-test-results.json) retain initial runs,
justified follow-ups and baseline checks. Legacy resource goldens use the frozen
fixture; productive module salvage recovers field_service_rig on the second
attempt and preserves cargo/depletion. Legacy assertions were not merely changed
to accept new IDs or loot.

## Documentation, guarantees and limits

EN/ES worldgen references now describe productive behavior. The new integration
contract covers identity, authored base, inverse proof, topology, materialization,
saves, comparisons and cost. e1/e1b references are explicitly historical evidence;
indexes/navigation compatibility notices are synchronized. EN/ES debug manuals
were updated; help does not describe seed behavior, so its syntax/descriptions
needed no change. New incompatibility/seed messages are EN/ES. Manual style passes.

D18–D20 and all public formats remain explicit. e4 and practical authoring guides
are not declared complete. No accumulated scan memory, new probabilities, host
reservations, final ad hoc replacement, F-DEAD-01 planner activation, comms/radiod,
station class, audio or general balance changes. e3/e4/e5 remain pending; the
existing planner's conditional proposals receive no retroactive certification.

Guarantees concern the fixed definition and supported domain, not universal
connectivity, equality to all mutually incompatible legacy worlds, exact old
loot, other kernels or global statistical equivalence. Old/synthetic compatibility
markers without physical_inventory_complete do not certify historical inventory.

## Files and package

ZIP: `retorno-4D-3e2-review.zip`, beside the repository directory. Only the
40 listed modified/new files, repository-relative paths. No narrative,
real saves, caches, .git or recursive ZIP. Entry list, bytes and CRC verified.
Work stops for external review without stage/commit/push.

| File | Responsibility |
| --- | --- |
| [data/manuals/commands/debug.en.txt](../../data/manuals/commands/debug.en.txt) | EN/ES debug manual: when the seed can change. |
| [data/manuals/commands/debug.es.txt](../../data/manuals/commands/debug.es.txt) | EN/ES debug manual: when the seed can change. |
| [docs/README.es.md](../../docs/README.es.md) | EN/ES index and phase status. |
| [docs/README.md](../../docs/README.md) | EN/ES index and phase status. |
| [docs/design/historical-worldgen-integration.es.md](../../docs/design/historical-worldgen-integration.es.md) | EN/ES technical contract, numerical proof, decisions and comparison. |
| [docs/design/historical-worldgen-integration.md](../../docs/design/historical-worldgen-integration.md) | EN/ES technical contract, numerical proof, decisions and comparison. |
| [docs/design/procedural-preexistence.es.md](../../docs/design/procedural-preexistence.es.md) | Mark e1/e1b as historical evidence and link current contract. |
| [docs/design/procedural-preexistence.md](../../docs/design/procedural-preexistence.md) | Mark e1/e1b as historical evidence and link current contract. |
| [docs/design/stable-procedural-manifest.es.md](../../docs/design/stable-procedural-manifest.es.md) | Mark e1/e1b as historical evidence and link current contract. |
| [docs/design/stable-procedural-manifest.md](../../docs/design/stable-procedural-manifest.md) | Mark e1/e1b as historical evidence and link current contract. |
| [docs/systems/discovery-navigation-intel.es.md](../../docs/systems/discovery-navigation-intel.es.md) | EN/ES ID compatibility and D18–D20 notice. |
| [docs/systems/discovery-navigation-intel.md](../../docs/systems/discovery-navigation-intel.md) | EN/ES ID compatibility and D18–D20 notice. |
| [docs/systems/world-generation.es.md](../../docs/systems/world-generation.es.md) | EN/ES canonical reference updated for stable runtime. |
| [docs/systems/world-generation.md](../../docs/systems/world-generation.md) | EN/ES canonical reference updated for stable runtime. |
| [docs/testing/manifest-integration-measurements.json](../../docs/testing/manifest-integration-measurements.json) | 40 fixtures, four-model aggregates, resources and benchmarks. |
| [docs/testing/manifest-integration-review.es.md](../../docs/testing/manifest-integration-review.es.md) | Delivery report and complete file inventory (EN/ES). |
| [docs/testing/manifest-integration-review.md](../../docs/testing/manifest-integration-review.md) | Delivery report and complete file inventory (EN/ES). |
| [docs/testing/manifest-integration-test-results.json](../../docs/testing/manifest-integration-test-results.json) | Initial results, justified follow-ups and baseline checks. |
| [src/retorno/bootstrap.py](../../src/retorno/bootstrap.py) | Capture physical rules on startup; preserve authored bootstrap. |
| [src/retorno/cli/repl.py](../../src/retorno/cli/repl.py) | Physical resolution of new IDs; guard pinned seed changes. |
| [src/retorno/core/gamestate.py](../../src/retorno/core/gamestate.py) | Save schema 3. |
| [src/retorno/io/save_load.py](../../src/retorno/io/save_load.py) | Persistence/validation and EN/ES incompatibility rejection. |
| [src/retorno/model/world.py](../../src/retorno/model/world.py) | Version, definition and provenance; physical/cohort inventory metadata. |
| [src/retorno/ui_textual/app.py](../../src/retorno/ui_textual/app.py) | Same seed guard: four compatibility lines, no UI redesign. |
| [src/retorno/worldgen/catalog.py](../../src/retorno/worldgen/catalog.py) | Historical evidence without upgrading conditional samples. |
| [src/retorno/worldgen/generator.py](../../src/retorno/worldgen/generator.py) | Stable productive materialization, resources and universe validation. |
| [src/retorno/worldgen/manifest.py](../../src/retorno/worldgen/manifest.py) | Pure historical core, identity, generation and inverse physical queries. |
| [src/retorno/worldgen/manifest_prototype.py](../../src/retorno/worldgen/manifest_prototype.py) | Compatibility entry point to the shared core with experimental policy. |
| [src/retorno/worldgen/topology.py](../../src/retorno/worldgen/topology.py) | Fixed initial priority and eight bounded matching rounds. |
| [tests/fixtures/worldgen_catalog_5cdde28.py](../../tests/fixtures/worldgen_catalog_5cdde28.py) | Isolated conditional legacy catalog for historical evidence. |
| [tests/fixtures/worldgen_legacy_5cdde28.py](../../tests/fixtures/worldgen_legacy_5cdde28.py) | Byte-exact HEAD generator to preserve witnesses; test-only. |
| [tests/known_routes_integrity_smoke.py](../../tests/known_routes_integrity_smoke.py) | Pin definition before the persistence fixture snapshot. |
| [tests/lore_secondary_count_weights_hard_smoke.py](../../tests/lore_secondary_count_weights_hard_smoke.py) | Declare distant UNKNOWN before bootstrap instead of moving it afterwards. |
| [tests/nav_abort_waypoint_cleanup_smoke.py](../../tests/nav_abort_waypoint_cleanup_smoke.py) | Navigation fixture pins definition without a false historical completeness claim. |
| [tests/worldgen_manifest_comparison.py](../../tests/worldgen_manifest_comparison.py) | Reused e1b comparator with productive model, resources and cost. |
| [tests/worldgen_manifest_integration_smoke.py](../../tests/worldgen_manifest_integration_smoke.py) | 14 new integration and numerical-bound test groups. |
| [tests/worldgen_manifest_prototype_smoke.py](../../tests/worldgen_manifest_prototype_smoke.py) | 17 prototype groups with shared kernel and explicit legacy reference. |
| [tests/worldgen_modules_pool_smoke.py](../../tests/worldgen_modules_pool_smoke.py) | Separate legacy goldens; productive profiles, actions and depletion. |
| [tests/worldgen_preexistence_catalog_smoke.py](../../tests/worldgen_preexistence_catalog_smoke.py) | Legacy contract assertions against frozen fixture. |
| [tests/worldgen_preexistence_characterization_smoke.py](../../tests/worldgen_preexistence_characterization_smoke.py) | Original witnesses against frozen legacy generator/catalog. |
