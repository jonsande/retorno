# Stable procedural manifest — 4D-3e1b contract and prototype

**4D-3e2 update:** this document retains historical evidence from its phase.
The current productive contract is [Historical worldgen integration](historical-worldgen-integration.md).
The prototype now uses the shared core and distinguishes certification by scope/reasons;
the conditional legacy catalog lives in test fixtures. Productive limitations below
describe the earlier state, not the current runtime.

Spanish version: [stable-procedural-manifest.es.md](stable-procedural-manifest.es.md).
Coordination: [current roadmap (Spanish)](roadmap-worldgen-lore-f-dead01.es.md).

## Executive report and scope

The prototype demonstrates a historical manifest independent of the materialized
registry, query/exploration order and lore/failsafe needs. This is a **pure
prototype isolated from runtime**, not a worldgen replacement. Passing tests
does not approve its experimental policies for production. Comparison finds fewer
links with the local policy tested and a small occupancy difference in halo:
integrating without an explicit decision would change the universe distribution.
A direct replacement in 4D-3e2 is not recommended.

Initial inspection: `main`, clean worktree, HEAD
`000e05bc40993ba45804c30d3fff51df3c655bb3`; `git ls-remote origin refs/heads/main`
confirmed exactly that SHA. `dc06d92` contains 4D-3e1. Reviewed `AGENTS.md`,
roadmap, canon 0.3 and coherence guide, navigation/recovery contract, catalog,
generator, bootstrap, models, active data and legacy witnesses. Applicable
principles include `C-WORLD-001`, `C-INF-004` and roadmap D01–D04/D14–D17.
The canon's new temporal rules are not implemented here.

The current roadmap assigns **e2 to worldgen integration, e3 to scan memory,
e4 to lore/intel and e5 to F-DEAD-01**, superseding the provisional allocation
proposed in historical 4D-3e1 documentation. The roadmap is not rewritten.

## Approved contract versus tested hypotheses

**Approved:** separate determined historical site, materialized node, player
knowledge and operational route. History depends on seed, versioned rules and
authored base; no query grants discovery, resources, routes, reception or
materialization permission. Preserve 45 ly, current dispersion/configuration
and possible emptiness/isolation; do not guarantee rescue.

**Prototyped, awaiting production decisions:** generation-sector quotas against
a fixed authored base; guardrail in the origin's 3×3 XY neighborhood; hubs/topology
by provenance cohort; namespaced identities; intersector allocation by mutual
selection among the first k local proposals. These are concrete ways to evaluate
the contract, not a deployed new balance policy.

## API and certification scope

[`manifest_prototype.py`](../../src/retorno/worldgen/manifest_prototype.py):

```python
definition = define_manifest(271828)
result = query_manifest(definition, (
    "S+15126_+000_+000", "S+15126_+000_+001",
))
lookup = lookup_site(definition, result.sectors[0].sites[0].identity)
```

`define_manifest` captures physical authored data and template/archetype JSON
as immutable values. File loading occurs only at that boundary; subsequent
queries neither read the physical registry nor reload data. No `GameState` is
accepted. It reuses catalog `_configuration_key` and canonical helpers
`_select_archetype`, `_plan_sector_kinds`, `_sample_sector_node`, regions and
parser. The existing guardrail runs on a fresh local view; its flag write never
reaches game state. No productive generator is duplicated and
`ensure_sector_generated` is unchanged.

`ManifestDefinition`, `HistoricalSite`, `SectorManifest`, `HistoricalEdge`,
`ManifestResult`, `SiteIdentity` and lookup results are frozen values. Seed,
version, configuration, caps and coordinates are validated. The region/cap
environment must match the captured definition; a change requires a new
definition rather than silently reinterpreting previous results.

| Status | Actual guarantee |
| --- | --- |
| `certified_for_prototype` | For this definition/experimental rules, identity, provenance, position, physical sector, kind, region, hubs and returned edges are determined. Does not certify the legacy universe or production approval. |
| `conditional` | Production materialization is pending and not authorized by inspection. |
| `invalid` | `lookup_site` rejects foreign scope, malformed address, missing authored id or nonexistent slot in this definition. Invalid configuration/requests raise before certification is emitted. |
| `not_evaluated` | Complete reverse physical inventory, resources/pools/files, radiation/historical age and dynamic special events. Does not mean zero, absence or permission. |

4D-3e1 `conditional` samples do not become addresses of the new manifest; lookup
rejects their keys. Only the explicit rules of a new definition determine the
prototype's sites. Narrative eligibility and operational F-DEAD-01 access are
not certified.

## A. Authored base, quotas and identity

The current base contains `UNKNOWN`, `ECHO_7`, `HARBOR_12`, `ARCHIVE_01`, with
the same coordinates/kinds/hubs as bootstrap. `RETORNO_SHIP` is excluded as in
bootstrap. `UNKNOWN` is a technical marker, not historical infrastructure eligible
for recovery. Sharing its coordinates with ECHO does not merge identities. The
prototype explicitly preserves its initial quota contribution; whether it should
consume quota in a productive manifest remains a decision.

Only that fixed base consumes quotas before `_plan_sector_kinds`. Foreign-sector
wrecks and later scheduler/failsafe insertions do not. Rolls, weights,
probabilities, caps and authored-hub priority remain unchanged. An explicit base
exceeding its cap is retained and receives no additional slots. Duplicate authored
ids are rejected; legacy keeps the first according to file order. An ECHO missing
from an experimental base is not automatically added: the productive fallback
remains outside the manifest.

Proposed identity: `SiteIdentity(scope, namespace, local_id)`.

- `scope`: SHA-256 of seed, version `prototype-4d3e1b-v1`, rules fingerprint,
  sorted authored base and cap. The reused fingerprint includes explicit weight
  order, physical regions and sector size. Changing the base creates another
  universe; stability across different definitions is not promised.
- `authored`: `local_id` is the literal authored id.
- `procedural`: `local_id` canonically encodes `(generation_sector, index)`.
  It is not shortened to 24 bits and never consults an id registry.
- `special`: reserved namespace, not generated here.

JSON encoding of the three fields preserves the namespace. Within a scope,
different sector/index addresses and unique authored ids cannot collide. The
cross-universe fingerprint assumes normal cryptographic collision resistance;
this is not a mathematical proof that SHA-256 never collides across all universes.
Tests force procedural-hint collisions, authored/hint collisions and an authored
literal resembling an encoded identity: identities remain distinct.

`legacy_id_hint` reproduces the short base for diagnostics/hub ordering only;
**it is not a definitive node_id**. The encoded internal identity is also not a
new `NODE`/CLI command token. Preserving authored aliases and choosing persisted/
operational representation requires explicit e2 work. Dynamic special sites must
not claim the historical namespace.

## B. Fixed guardrail

For each definition, the existing rule is evaluated once, conceptually, over
`[-1,1]×[-1,1]×{0}` around the operational origin. Same overrides, early-neighbor
criterion and legacy seeds, but without waiting for the player's first request
or honoring already generated sectors. No connectivity is forced, nor a natural
hub roll where legacy would not force it. Adopting this particular neighborhood
in production requires approval.

## C. Z, spatial membership and completeness

The shared sampler retains exactly two uniform X/Y draws and Gaussian Z,
without truncation, rejection or corrective relocation. Every record retains
generation sector and physical sector calculated with `floor`. The provenance
inventory is complete; a sector's spatial inventory is not declared complete
from it. The template region uses the generation-sector center; the site's
region uses its actual position, including spherical boundaries. No kind is
substituted for convenience.

At seed `271828`, the ship generated in `S+15126_+000_+000` is at
`(151266.79157885376,9.329097599582711,10.057691279289713)`, inside Z=1.
The upper generation sector retains its own slot: two sites occupy that
physical sector when both provenances are queried. Legacy has one or two
depending on order because the outlier consumes the later quota.

A viable e2 solution is to retain this provenance and add certified reverse
lookup before wiring scan/materialization. Pending alternatives:

1. **Pin and prove the numeric kernel's support.** Current CPython `gauss` uses
   `cos(2πu)*sqrt(-2 log(1-v))`, with 53-bit uniforms. This suggests a conservative
   bound below `8.58σ`; with σ≤2, a reverse Z index could inspect five generation
   planes (±2), including rounding margin. This does not change the implemented
   distribution. The prototype **does not certify this bound**: it requires
   kernel versioning, a rounding/coordinate-domain proof and consideration of X/Y
   rounding too. This is the recommended option to investigate in e2.
2. **Persisted reverse index of already calculated provenance:** useful as a
   cache; by itself it cannot certify absence of entries from unexamined sources.
3. **Truncate, clamp or resample Z:** changes distribution/placement and requires
   approval. Not performed here. Ideal Gaussian mass outside the cell is about
   `2.29e-62` disk, `4.10e-10` bulge and **1.2419%** halo.

The ideal mathematical distribution is unbounded; no claim is made that finite
CPython has infinite support. Nor is bitwise reproducibility promised across
unverified Python/libm versions. Generation-owned quotas remove the dependence,
but this occupancy policy needs approval; it is neither the only possible fix
nor an expansion of latent slots.

## D/E. Hubs and bounded historical topology

A generation-sector cohort contains its fixed authored records and slots,
including Z outflow. Hub selection: an existing playable hub first, then
lexicographic hint with full identity as tie-breaker. An eligible-kind topology
hub becomes playable as in legacy; each nonempty cohort has exactly one topology
hub. Star and extra links reuse current rules, probabilities and seeds. Edges
never authorize `known_links`.

Intersector links:

1. Inspect the generation sector's eight XY neighbors at the same Z index.
2. Require hubs, configured capacity, existing pair roll and distance ≤45 ly.
3. Order candidate pairs by a stable BLAKE2b seed/pair priority.
4. Each sector proposes its first k pairs, with k its current configured budget.
   Accept a pair only when both endpoints propose it.

The intersection guarantees reciprocity and degree≤k without shared counters or
insertion order. Certifying incident edges needs at most a radius-two XY
dependency closure, up to 25 generation sectors per request. It may leave
capacity unused and **is not a maximal matching**. A global greedy ordering can
need an unbounded dependency chain; a fixed seed alone is insufficient. An
alternative with edge-color rounds could fill more capacity with finite
dependencies, but would produce another distribution and is not implemented here.

The result includes outside endpoints as `boundary_sites`, without publishing
their contacts. Later neighbor queries do not change a previously determined
edge. Emptiness, isolated components and dead ends remain possible. Zero-distance
edges between distinct identities are allowed as in legacy physical ECHO/UNKNOWN;
there are no self-edges or implied travel permissions.

## Reproducible comparison and distribution consequences

[`worldgen_manifest_comparison.py`](../../tests/worldgen_manifest_comparison.py)
produces [the full measurements](../testing/manifest-prototype-measurements.json).
Seeds `0..7`, `29`, `271828`; 64 sectors per region/seed (8×4 XY, two Z planes),
plus nine around the origin: **2010 focus sectors, 40 fixtures**. Public legacy
requests run forward and reversed on separate states; both generate the same
union (120 sectors per regional patch, 25 in the initial patch). The prototype
queries that same union with an explicit technical bound. Creation provenance
and link kind in its original pass are tracked without changing the algorithm
or legacy assertions.

Node counts use **generation provenance**. Physical occupancy includes observed
inflow from the finite generated union, not a global inventory. Graphs below
are induced on focus sectors and may connect through excluded external nodes;
their components prove neither galactic isolation nor operational accessibility.
All figures sum the ten seeds except stated fractions/means.

| Patch (sectors) | Nodes forward / reverse / prototype | Nodes/sector forward → prototype | Empty forward → prototype |
| --- | --- | --- | --- |
| Disk (640) | 1040 / 1040 / 1040 | 1.625 → 1.625 | 12.0313% → 12.0313% |
| Bulge (640) | 985 / 985 / 985 | 1.539062 → 1.539062 | 15.1562% → 15.1562% |
| Halo (640) | 746 / 747 / 748 | 1.165625 → 1.168750 | 29.3750% → 29.0625% |
| Initial (90) | 154 / 154 / 154 | 1.711111 → 1.711111 | 12.2222% → 12.2222% |

Halo has **two additional derelicts** versus forward: +0.2681% nodes, without
new weights/maximum slots. Archetypes and kind histograms match in the other
three samples. These patches have no per-sector archetype changes; that does
not invalidate the seed-29 guardrail witness outside this initial request order.
Complete histograms by archetype, kind and actual region are in JSON.

| Patch | Playable hubs forward → proto | Topology hubs forward → proto | Internal edges forward → proto | Intersector edges forward / reverse / proto |
| --- | --- | --- | --- | --- |
| Disk | 254 → 254 | 563 → 563 | 513 → 513 | 126 / 133 / 106 |
| Bulge | 174 → 174 | 543 → 543 | 466 → 466 | 86 / 88 / 81 |
| Halo | 100 → 99 | 451 → 454 | 299 → 308 | 39 / 41 / 37 |
| Initial | 42 → 42 | 79 → 79 | 78 → 78 | 20 / 18 / 13 |

| Patch | Components forward / proto | Single-node components forward / proto | Degree-one sectors forward / proto |
| --- | --- | --- | --- |
| Disk | 438 / 458 | 165 / 178 | 190 / 170 |
| Bulge | 457 / 462 | 184 / 190 | 150 / 142 |
| Halo | 420 / 417 | 235 / 229 | 76 / 72 |
| Initial | 59 / 66 | 19 / 21 | 28 / 18 |

ECHO's component within the nine initial sectors totals 51 nodes forward,
52 reversed and 45 in the prototype; per-seed medians are 4, 4.5 and 3. These
are not known routes or a promise of escape. Each model has 11 halo Z outliers
and zero in the other samples. Observed physical halo occupancy is 740 / 741 /
742 nodes respectively; the different later quota explains the difference
without changing σ.

The loss of disk links (−15.87%) and initial links (−35%, small sample) **is
not an inevitable cost of correcting order dependence**: it depends on the
tested mutual policy and requires acceptance or another topology policy.
Likewise, the small halo node increase depends on generation-owned quotas.
The unavoidable fact is that all divergent legacy worlds cannot be reproduced
simultaneously, not these particular changes. No parameter is adjusted to improve
results and no population-level statistical inference is made.

## Tests, performance and demonstrated limits

Interpreter `/home/jon/prog/retorno_case/retorno_venv/bin/python`, `PYTHONPATH=src`:

```text
.../retorno_venv/bin/python tests/worldgen_manifest_prototype_smoke.py
.../retorno_venv/bin/python tests/worldgen_manifest_comparison.py --output docs/testing/manifest-prototype-measurements.json
```

**17 new groups:** repeated/reversed/duplicate and isolated-query equality,
`PYTHONHASHSEED=1/7/99` subprocesses, simulated legacy exploration/materialization,
definition/GameState/RNG purity, forbidden writers/loaders, forced collisions,
authored/over-cap bases, regional boundaries, Z, guardrail, reciprocity, budgets
and bounds. Legacy witness assertions remain intact.

**24 scripts pass:** the new one and both 4D-3e1 smokes; sparse archetypes,
module pool, procedural radiation, galaxy model, route hop cap, known-route
integrity, abort waypoint, route-solve origins, sector intel, scan job, sensor
factor, save/load, the three 4D-3b/c/d planners, zero cooldown, lore, channel
preference/unlock, forced hidden ad hoc, secondary weights/hard and uplink retry.
No real save is modified or opened. Temporary saves belong only to existing
regressions. Document paths and EN/ES counterparts are validated.

The comparison benchmark excludes definition construction and uses three calls
per family plus a separate tracemalloc measurement. Requests of 1/9/64 evaluate
14/30/151 cohorts; order of magnitude is 3/6/30 ms, with peaks around
32/50/158 KiB on this machine. Exact values/Python version are in JSON; these are
not latency bounds. No global cache or dependence on `space.nodes` size exists.
Memory/work depend on authored base and bounded sector closure, not the galaxy.
Exceeding a technical bound rejects the request and never proves absence. Missing
production integration and physical reverse inventory are not presented as solved.

## 4D-3e2 decisions and compatibility

Before replacing worldgen, approve or revise: `UNKNOWN` and ECHO fallback in
the base; generation-owned quotas; guardrail neighborhood; cohort topology and
local arbitration with the measured link reduction; persisted addresses/authored
aliases and special namespaces; versioned RNG kernel and reverse physical
lookup. Recommendation: retain typed identity and immutable base as a contract;
**do not silently adopt the tested topology policy**. Resolve these decisions
while preparing e2 without starting an indefinite optimization campaign.

This is not compatible as a replacement for legacy saves or their ids/counters.
Integration requires pinning the universe version per game, explicit rejection
of incompatible saves, provenance and idempotent materialization/topology without
knowledge leaks. It does not require complex historical migrations or save
deletion. Radiation/loot seeded by node_id need a stable seed policy in e2;
no resources were recalculated or compared here.

Lore may select/reserve these sites but not create them to satisfy a need;
intel must resolve identity rather than fabricate destinations from centers/
coordinates; F-DEAD-01 must assess protection and directed access, not resources.
None is integrated. Natural scan and valid manual-resolution exceptions retain
their current production rules. Manuals/help need no change: no new commands,
player text or observable behavior.

## Files and Git handoff

| Relative file | Purpose |
| --- | --- |
| `src/retorno/worldgen/manifest_prototype.py` | Immutable definition, bounded historical queries, identity, experimental hubs/edges. |
| `tests/worldgen_manifest_prototype_smoke.py` | 17 focused groups, including unchanged legacy witnesses. |
| `tests/worldgen_manifest_comparison.py` | Ten-seed comparison, provenance/link-kind instrumentation and benchmark. |
| `docs/testing/manifest-prototype-measurements.json` | Versioned reproducible evidence, not a cache or temporary artifact. |
| `docs/design/stable-procedural-manifest.es.md` | Spanish report/contract. |
| `docs/design/stable-procedural-manifest.md` | This English counterpart with matching scope/data. |
| `docs/README.es.md` | Index link to the new contract/prototype. |
| `docs/README.md` | English index counterpart. |

Handoff state: `main`, same initial/confirmed remote HEAD, two modified index
documents and six new files belonging to this delivery; Git index empty. Six
additional untracked files appeared during work under
`narrative/operacion_amanecer_narrativa_v0.1/amanecer_paquete/`, outside this phase;
they are preserved untouched and excluded from the ZIP. No existing productive file or
4D-3e1 witness is edited. `git diff --check` passed before packaging. The
delivery ZIP contains only these eight files with relative paths: no saves,
environments, caches, unchanged files or temporary artifacts. No staging, commit
or push. Work stops for external review; experimental certification does not
authorize e2.
