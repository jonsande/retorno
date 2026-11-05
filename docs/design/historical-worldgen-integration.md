# Historical worldgen integration — 4D-3e2

Spanish: [historical-worldgen-integration.es.md](historical-worldgen-integration.es.md).
Status: implemented in the review working tree based on `5cdde28`; external
approval is pending. The binding coordination document remains roadmap v1.1
([ES](roadmap-worldgen-lore-f-dead01.es.md)).

## Productive contract

`historical-world-v1` is the productive manifest version. `manifest.py` owns
immutable historical definitions and pure queries; `generator.py` materializes
them; `topology.py` supplies their finite matching policy. The prototype module
is a compatibility entry point into the same core with the old mutual top-k
policy. Historical legacy generation/catalog code exists only in test fixtures.
There are no two independent productive generators and no mutable global
universe cache. Memoization is local to a query or materialization session.

Four layers remain distinct: historical existence, materialized nodes, player
knowledge and operational known routes. A read-only query returns evidence,
not permission to insert a node or publish a route. Productive `catalog_sector`
and `catalog_sectors` now query generation cohorts from this definition;
`VERIFIED` is not an upgrade of a legacy conditional sample. Dynamic/special
nodes are outside that catalog and remain in the physical registry.

The version, seed, physical rules and authored base define one scope. Bootstrap
records the rules fingerprint; the complete definition is pinned on first
materialization or save. A read-only query does not pin/mutate the game. After
pinning, changing the seed/rules is rejected. `debug seed` checks before changing
state in both front ends; syntax is unchanged. Before pinning it retains its
existing use for choosing a test seed. `WorldState.rng_seed` remains a legacy
field; `MetaState.rng_seed` is the input to definition capture.

The fingerprint includes regional templates and archetypes (including weighted
iteration order), coordinate mapping, sector size, radiation/drone balance,
ordered modules, authored physical/salvage definitions and the supported Gaussian
kernel. Narrative prose and files do not participate. An algorithm change
requires a new explicit version; the fingerprint is not automatic source-code
versioning. Cross-universe fingerprints assume SHA-256 collision resistance.

## Identity and operative IDs

`SiteIdentity(scope, namespace, local_id)` is historical identity. Authored
addresses retain their raw ID; procedural local addresses encode generation
sector and slot index. Operative IDs are separate:

- Authored IDs (`UNKNOWN`, `ECHO_7`, `HARBOR_12`, `ARCHIVE_01`, future explicit
  declarations) remain unchanged.
- Procedural IDs are `S+x_y_z:WG1_<full scope SHA-256>_<slot index>`, using the
  canonical signed sector syntax rather than the abbreviated example here.
- If an immutable authored ID reserves that exact text, `WG1C1`, `WG1C2`, etc.
  select the first unreserved address. Allocation never consults materialized
  registry order. A conflicting runtime occupant fails before mutation.
- `legacy_id_hint` is only a diagnostic/name/hub ordering hint, never uniqueness
  evidence. Special/dynamic IDs and their existing runtime mechanisms continue
  separately. `historical_key` and `generation_sector_id` provide provenance.

`operative_id` and `resolve_operative_id` round-trip exact canonical IDs. The
existing `NODE:`/`LINK:` compatibility helper resolves the new exact ID to its
physical sector, including a Z spill; commands retain their syntax. Unresolved
literal intel remains intel under the existing contract. This grants no new
navigation or information-source authority.

## Authored base and initial conditions

The same `data/locations/*.json` loader supplies bootstrap and the manifest.
Duplicate authored IDs fail explicitly. Coordinates, names, kinds, authored
radiation and salvage retain bootstrap behavior. Adding a specific future arc
station is a physical declaration through that existing mechanism; bootstrap
inserts it without adding knowledge unless its explicit existing reveal flags
request that. Mentioning its name in prose declares/reveals nothing.

`RETORNO_SHIP` keeps its special filesystem/ship handling and is excluded from
historical destination cohorts. `UNKNOWN` remains a quota-bearing authored
origin marker, including after its normal runtime removal: historical quotas
never change because the marker was removed. It is never resurrected.
`ECHO_7` remains the declared origin hub; the redundant generator fallback that
could fabricate it when absent has been removed. The active authored base still
provides it. Neither a missing declaration nor lore need creates a replacement.

Quotas belong to generation cohorts and count the fixed authored base there.
Foreign physical inflow and runtime special nodes do not consume those quotas.
Over-cap authored definitions are preserved without extra procedural slots.
This removes the old Z-inflow/request-order dependency without tuning any count,
kind probability or cap. Physical-sector counts can exceed cohort caps because
they can receive inflow; consumers must not equate the two inventories.

## Complete physical inverse query and numerical domain

`query_manifest` answers generation cohorts and incident historical edges.
`query_physical_sectors` answers all historical sites whose actual coordinates
belong to requested physical sectors. The Gaussian is unchanged, untruncated and
not resampled. Both results are read-only; no whole-galaxy search is performed.

Certification supports CPython 3.12, binary64, radix 2, 53-bit mantissa and
round-to-nearest. The exact `Random.gauss` Python source is checked against its
pinned SHA-256. The supported sector index magnitude is at most
`2**48 - 32`; physical inverse requests reserve four indices inside that bound.
The productive templates must have `0 < z_sigma <= 2`.

For a fresh RNG, CPython `random()` returns multiples of `2**-53` in `[0,1)`.
The fresh Box–Muller Gaussian uses
`sqrt(-2*log(1-u)) * cos(2*pi*v)`. Thus its standard magnitude is at most
`sqrt(106*log(2)) ≈ 8.572 < 8.58 < 9`. The sampler calls `gauss` once on a fresh
local RNG, so its cached second variate is irrelevant. The pinned implementation
and standard binary64 operations are the supported numerical environment; this
is a bound on the finite implemented sampler, not an ideal unbounded Gaussian.

At the supported index magnitude, integer sector boundaries/centers `10*i` and
`10*i+5` are exactly representable below `2**52`. The code uses `9*sigma + 2 ly`
as a conservative envelope, allowing much more than binary64 multiplication,
addition, elementary-function and sector-division rounding at that magnitude.
With sigma at most 2 this envelope is at most 20 ly. A source three Z indices
away has its center at least 25 ly from the target interval; therefore only
`target_z-2 .. target_z+2` can contribute. Candidate intervals are filtered by
their template's envelope, then actual sampled coordinates determine membership.

X/Y use an exact lower boundary plus `10*random()`. Rounding is monotone and can
reach the upper endpoint at large coordinates. Physical index is the source
index or its successor; inverse lookup includes target and preceding source on
each XY axis. There are at most **20 source candidates per physical sector**,
not merely its same-XY Z neighbors. Authored sites belong to their own physical
cohort. Identity deduplication prevents duplicate results for grouped requests.

Public pure requests default to 64 sectors. Sessions cap computed cohorts at
32,768. The runtime accepts at most 64 requested sectors, expands their 3×3 XY
union (at most 576 physical sectors), and stages at most 2,048 new nodes. Domain,
configuration, work-budget or collision failures raise before returning an
inventory or committing nodes. There is no successful partial/empty fallback.
These are explicit technical bounds, not galaxy boundaries or a recovery search
radius. Tests exercise extreme uniform values, large-coordinate XY rounding,
domain rejection, work exhaustion and the seed-271828 physical outlier.

## Topology and guardrail policy

The guardrail is evaluated against a fixed 3×3 XY origin neighborhood, using the
existing overrides, early-neighbor criterion and RNG keys. It never depends on
which area was requested first. It does not force a naturally selected hub roll
or guarantee universal progression.

Internal stars and optional extra links use the canonical sampling, playable
hub preference, legacy-hint ordering with historical-identity tie breaking, and
45 ly cap. Topology belongs to generation cohorts even when members spill in Z.

For intersector links the alternative to underfilled mutual top-k is a maximal
budgeted matching. First, pairs wholly inside the fixed origin 3×3 are considered
in the legacy canonical first-request order, reserving their budgets. Then four
undirected XY directions `(1,0),(0,1),(1,1),(1,-1)` split by endpoint parity into
eight disjoint matchings. Fixed rounds 0–7 consider every other neighbor pair
once. Each keeps the existing pair RNG/probability, both configured budgets and
the 45 ly check. Internal-origin pairs are skipped in these outer rounds.

Acceptance recursively asks only degrees from earlier rounds: dependency depth
is at most eight neighbor hops plus the fixed origin pass. Local memoization
bounds repeated work; there is no unbounded greedy dependency chain. Every
rejected viable pair has a saturated endpoint which remains saturated, so the
result is maximal, not necessarily maximum. It is reciprocal and independent
of query order. Empty regions, isolated components and dead ends remain valid.

## Materialization, resources and persistence

The existing `ensure_sector_generated` API expands the 3×3 physical XY union,
queries inverse inventory, computes justified topology dependencies, and stages
nodes/properties/edges before committing. Only sites in that physical union are
inserted. Dependency/boundary sites used to calculate edges are not inserted
merely to complete an edge. An edge is attached when both endpoints exist;
later expansion attaches the same predetermined edge without replacing old
historical choices. Special runtime nodes retain their separate mechanisms.

`SectorGenState.node_ids` lists physical residents; `generation_node_ids` lists
currently materialized members of its cohort. Hubs and historical link counters
use cohort provenance. `physical_inventory_complete` accompanies generated
physical sectors. `intersector_link_pairs` is an inert compatibility field;
it no longer determines historical choices. Internal queries/materialization do
not modify known nodes, contacts, known links, files, pools or gameplay RNG.

Radiation, scrap, module selection, recoverable drones and display names reuse
existing helpers and configurations. Resource RNG keys now use full historical
identity rather than a collision-prone operative short ID. Exact rolls differ;
probabilities, ranges, module pools and amounts are unchanged. Existing node
resources are preserved, including depletion and dry flags; repeat requests and
save/load cannot refill them. Authored salvage keeps its existing bootstrap RNG.

Save schema is `MetaState.save_version = 3`; the checked container remains V2.
The complete immutable definition, provenance, physical state, knowledge and
pools are persisted. Validation checks scope/rules/version/seed, historical
positions/kinds/hubs, reciprocal legitimate edges, missing edges between existing
endpoints and complete-sector inventories. Consumed resources are not compared
with initial loot. Old schema-2 worlds and incompatible rules are rejected via
`SaveLoadError`; no migration or automatic deletion occurs. Existing backup
fallback behavior remains. New incompatibility and debug-seed feedback is EN/ES.

## Reused comparison and decision

[Measurements](../testing/manifest-integration-measurements.json) reuse the ten
seeds `0..7,29,271828`, 40 fixtures and 2,010 focus sectors of e1b. Regional
patches have 64 focus sectors with a 120-sector legacy generation footprint;
the initial patch has nine focus sectors and a 25-sector footprint. Metrics are
induced focus graphs by generation ownership, not full-galaxy graphs. Observed
physical counts in this comparison still refer to that finite footprint; the
complete inverse inventory is tested separately.

| Patch | Nodes legacy forward / reverse / productive | Intersector edges forward / reverse / prototype / productive | Components forward / reverse / prototype / productive |
| --- | --- | --- | --- |
| disk | 1040 / 1040 / 1040 | 126 / 133 / 106 / 133 | 438 / 430 / 458 / 431 |
| bulge | 985 / 985 / 985 | 86 / 88 / 81 / 84 | 457 / 455 / 462 / 459 |
| halo | 746 / 747 / 748 | 39 / 41 / 37 / 43 | 420 / 419 / 417 / 411 |
| initial | 154 / 154 / 154 | 20 / 18 / 13 / 20 | 59 / 61 / 66 / 59 |

The initial ECHO component totals are 51/52/45/51 in the same four-model order.
Disk/bulge populations, archetypes, hubs and internal edges are identical.
Halo has 11 Z outliers in every model; source-owned quotas give two more nodes
than forward legacy (0.27%), three more topology hubs (451→454), one fewer
playable hub (100→99) and nine more internal edges (299→308). Empty cohort
fractions are disk 12.03%, bulge 15.16%, halo 29.38% legacy versus 29.06%
productive, and initial 12.22%. Density remains 1.625/1.539/1.169/1.711 nodes per
focus sector. These small quota differences remove foreign-inflow dependence.

The selected policy keeps the canonical initial opportunities and avoids the
prototype's systematic link loss. Exterior differences are +7, -2 and +4 edges
versus forward legacy across 640 sectors per region; the halo increase is
10.3% of its small 39-edge baseline, or 0.625 extra edges per 100 sectors.
Fixed rounds without origin priority yielded initial 15 edges and ECHO total 43;
seed-shuffled rounds without that priority yielded disk/bulge/halo/initial
117/80/38/14 and ECHO 42. These bounded alternatives motivated origin priority,
not an open-ended tuning campaign. No probabilities or balance quantities were
changed. Under the order's decision rule this is adopted as the best-supported
alternative, subject to external review; sample agreement is not a universal
statistical-equivalence proof.

Across the same procedural focus population, legacy forward versus productive:
2,885→2,887 nodes, scrap 76,980→77,363 (+0.50%), modules 3,509→3,518 (+0.26%),
drones 419→456 (+8.83%), radiation sum 8.2208→8.3801 (+1.94%). Initial scrap
alone is 2,768→3,064 and drones 15→24 across 114 nodes: exact re-seeding matters
in small samples. Regional totals are in the JSON. These are changed random
outcomes from stable identity seeds, not changed probabilities or guarantees.

On this checkout, median generation-query times for 1/9/64 sectors were
prototype 2.66/5.99/29.08 ms and productive 7.37/11.04/37.98 ms; evaluated cohorts
14/30/151 versus 29/46/182, peak traced allocations 31.8/49.7/155.2 versus
52.2/79.9/257.7 KiB. Complete inverse queries cost 4.61/7.23/21.36 ms;
materializing their public XY unions cost 19.89/34.00/103.36 ms, inserting
19/51/197 total nodes. These are local measurements, not performance guarantees.
The finite dependency policy increases single-query overhead; no additional
optimization or global cache is introduced.

## Verification and subsequent phases

Run with the canonical venv from the repository, `PYTHONPATH=src`, using
`python -m tests.worldgen_manifest_integration_smoke` (substitute the full
canonical interpreter path from `AGENTS.md`). The 14 groups compare full node,
resource, provenance, sector-state and edge values across forward/reverse/grouped
requests, partial expansion, repeated saves and three `PYTHONHASHSEED` processes.
They also cover pure-state integrity, authored declarations, new-ID intel,
sector blocks, COORD nav points, collisions, numerical bounds and incompatible
saves. Existing witnesses and module goldens run against frozen test-only legacy
fixtures; their original assertions are retained. Productive module/action
coverage separately checks configured pools/ranges and real depletion.

The [review report](../testing/manifest-integration-review.md) and
[test results](../testing/manifest-integration-test-results.json) record the full
regression outcome and delivery inventory.

D18–D20 remain explicit: a physical declaration is distinct from prose and
revelation; retain `NODE:`, `LINK:`, `SECTOR:`, `COORD:`, intel blocks and authored
references; the full authored/arc/single/forced-content end-to-end regression
belongs to e4. Current protected-target regressions remain active. No new lore
host reservations, replacement of ad hoc nodes, scan memory, detection
probabilities, F-DEAD-01 activation, `comms` or `radiod` are implemented. The old
chain planner remains pure and conditional where it was conditional; its
integration with certified history is still e5. e3/e4/e5 and practical authoring
guides are not declared complete.
