# Historical procedural information — historical-information-v1

[Español](historical-information.es.md). Implemented for external review in
4D-3e5c-B1, based on `445217e4503f9077c6dd53aef7c6cf9f53cf5b24`.

## Authority and six separate facts

`worldgen/information.py` projects certified `historical-world-v1` facts into
finite archives and navigation records. It adds no physical generator, global
mutable registry, transmitter or emission. New-game preparation captures an
`InformationDefinition`; ordinary worldgen does not prepare information pools.

1. The historical manifest determines physical existence and relationships.
2. The information definition determines retained historical records.
3. Physical interfaces and operational/narrative gates determine availability.
4. Uplink, salvage or reception acquire records.
5. Reading/importing consumes their intelligible clues.
6. Validated operational publication updates contacts and `known_links`.

Internal queries change none of the last four facts. Bootstrap/scan, manual
solve, authored documents and existing radio retain their own discovery rules.
The [B0 capability matrix](information-capabilities.md) remains authoritative.

## Captured inputs, identity and rules

Stable inputs are the universe seed/scope, `SiteIdentity`, certified kind and
position, incident historical edges, the captured authored archive/table data,
and the versioned information rules. The kernel accepts a `ManifestDefinition`
and `InformationDefinition`, never the player state. It cannot read clock,
known nodes/routes, visits, uplink counters, gameplay RNG or recovery needs.

`rules_key = SHA256(canonical_json((version, rules_json, authored_json)))`.
Canonical JSON sorts keys, uses compact separators, UTF-8 and finite numbers.
The rules snapshot stores kernel revision, candidate domain, route limit, hop
cap, weights and the six existing salvage format probabilities. Authored data
contains names, files and uplink tables; it excludes arc unlock state,
reservations and radio declarations. The physical scope remains unchanged.

Independent local RNGs use the integer SHA-256 of canonical tuples containing
version, rule key, host historical identity and family (`uplink`,
`archive-files`, `telemetry`). Neither Python `hash()` nor mutable RNG state
participates. Changing locale selects a rendering of the same record.

Navigation IDs hash rule key, source identity, destination identity and typed
relationship, prefixed `HI1:`. Telemetry IDs hash host identity and family.
World scope inside the identity binds these records to their universe.
Rule/code semantics changes require an explicit version/kernel revision; the
fingerprint does not automatically version arbitrary Python edits.

## Complete bounded historical query

`query_information` reuses a call-local manifest session, inverse physical
inventory and complete incident topology. The domain comprises the fixed
3×3×3 physical sectors centered on the host sector, every incident historical
edge endpoint, and explicitly configured authored candidates. It is not a
claim to enumerate every site within 45 ly. Generation cohorts are not
substituted for inverse physical inventory; Z spill and partial materialization
cannot alter the result. Optional shared sessions in manifest ID lookup avoid
repeated independent certification work without changing physical rules.

Default acceptance limits: 27 physical sectors, 4096 candidate sites and 4096
examined generation cohorts. Site/cohort limits are checked after each bounded
manifest projection; the manifest's 32768-cohort session cap bounds intermediate
work, rather than stopping that projection at exactly 4096 cohorts.
Recovery additionally permits 128 distinct information hosts per selection
(`RecoveryBudget.information_hosts`, maximum 512). Caches are local to that
selection. Domain/work failures raise or produce recovery `incomplete`;
initialization must not install an empty pool in their place. No whole-galaxy
enumeration occurs.

## Navigation records and finite uplink

### P1: fixed host navigation exclusions

An authored location may declare:

```json
"navigation_policy": {
  "version": "host-navigation-exclusions-v1",
  "exclude_destinations": ["HARBOR_12"]
}
```

`define_information` captures this optional subtractive policy before play.
Destinations are normalized authored IDs or unambiguous aliases. Invalid objects,
versions, keys, empty lists, unknown/self/player-ship or duplicate destinations
fail before play. Conflicting authored operative LINKs (including reverse,
implicit-host and INTEL forms) are rejected, never rewritten. Testimony/contact
mentions remain valid.

The original producer selects its finite records/files first; then excluded
selected uplink records and whole typed navigation files are removed. No re-roll,
slot refill or replacement file occurs. B2 retains its original selected record;
an excluded payload produces no procedural emission, with no replacement LINK or
ambient message. Equipment history, telemetry and other hosts remain unchanged.
This does not govern independent authored emitters or scheduler-owned pieces.

ECHO-7 configures HARBOR_12 in `data/locations/echo_7.json`. Its original EN/ES
cache still grants the contact when read, without the route. In seed 29 its three
uplink records become two; routes to HARBOR_12 obtained elsewhere remain valid.
No clock, knowledge, visits, progression or recovery request selects this policy.
Scan and route solve are unchanged; no general reachability guarantee is added.

The full information fingerprint includes the policy. `sampling_definition`
strips only this new field to preserve original v1 draws, record IDs, text and
retained archive provenance; pool fingerprints pin the full policy-aware
definition. B2 similarly separates original sampling from its full fingerprint.
The nonphysical policy is excluded from the physical catalogue hash, preserving
scope, positions, topology and operative IDs.

The policy has its own version; B1/B2 versions and save schema remain unchanged.
Without policy, prior v1 production is identical. Installing this ECHO-7 change
changes catalogue/full B1/B2 fingerprints: old-catalogue saves are rejected
nondestructively. Restore their original catalogue to load them; no migration or
removal of acquired routes occurs. Test: `tests/prologue_navigation_policy_smoke.py`.
See the [P1 review](../testing/prologue-navigation-policy-review.md).

Every selected destination is certified, different from the host, at positive
distance and at most 45 ly away. Two record types remain distinct:

| Type | Evidence | Interpretation |
| --- | --- | --- |
| `historical_connection` | Exact incident manifest edge, with internal/intersector provenance | A documented historical physical connection |
| `navigation_solution` | Certified endpoints and valid geometry, without that edge | Retained data sufficient for a calculated navigable route; no evidence of historical traffic or a network connection |

Eligible candidates receive weight 8 for an incident connection, otherwise 5
for a historical hub, 4 for another uplink-capable installation, or 1 for a
vessel/derelict. Explicit authored table weights and min/max authored quotas
are applied first, clamped to the three-record limit. Remaining slots use
stable ID ordering and weighted draws without replacement. Knowledge and
protected targets do not select, remove or replace historical records.

`NodePoolState.uplink_records` preserves typed records alongside the existing
destination list. The first valid action reads only authorized slots and may
resolve/materialize their certified lazy destinations at that point. It writes
a log of authorized records, including already known routes, with full LINK
instructions and bilingual relationship labels. Known routes are never
replaced by new targets. Repeating an exhausted uplink grants no new routes,
logs or rewards; existing pending narrative delivery can still retry.

## Salvage files and archival environmental text

Existing authored base files take precedence and keep their content and paths;
they may contain testimony rather than certified historical assertions. The
new procedural producer chooses a navigation record from complete incident
edges, or a calculated destination when no such connection is available.
It never constructs a LINK from a partially materialized `node.links` list.

Log/mail/fragment probabilities remain 70/50/25 percent for the corresponding
station/ship or station/derelict groups, with the existing 50/30/15 percent
fallback groups. The exact six fields remain in `config/balance.py`. As before,
an available navigation clue always gets a fragment fallback if no log was
selected: nominal fragment probability is not final fragment frequency.
Changes in historical candidate sets and seed domains can change individual
draws; the probabilities and physical resources do not change.

Paths, guest access and remote mounting remain. One retained mail has both
`/mail/inbox/0001.en.txt` and `.es.txt` renderings, sharing an identity and draw.
Navigation files contain a stable bilingual label and common LINK syntax.
Metadata records contract, rule key, record ID and typed navigation provenance.
Pool initialization freezes this projection once; it does not continually add
archives. Base/injected files and mounted information are never erased.

`build_procedural_salvage_mail_content` remains the public helper. New telemetry
is explicitly an undated retained archive, not a live measurement. Integrity
and clock drift are recorded claims. Certified historical connection counts
do not imply responsive peers, present traffic, recent handshakes, operational
stations or living people. Legacy text remains legacy text in old saves.

## Disclosure, scheduler and recovery

The existing protected-primary-target policy gates procedural delivery, not
history. Unauthorized navigation files stay in the raw pool and are excluded
from collectible/pending projections. Unlocking can make that same file
recoverable without rewriting it. At first uplink consumption, protected slots
are withheld without replacements; that one-shot route pool remains consumed,
including those slots. Later unlocks do not create uplink replenishment.
Natural scan and manual solve are not globally prohibited. Authorized scheduler
primaries keep their delivery/unlock semantics.

Scheduler weights, probabilities, deadlines, triggers and windows are unchanged.
Pending legitimate pushes can keep data incomplete after uplink exhaustion.
Scrap/extras stay independent, preserving B0 completion semantics.

F-DEAD-01 may query a not-yet-prepared v1 archive as pre-existing evidence. It
must find the exact LINK in the fixed file, preserve its path and payload hash,
and revalidate it during confirmation/save/progression. Querying neither
activates a pool nor injects a file. A first declared emission is still required;
without a legitimate source, recovery remains conditional/incomplete. Existing
`historical-recovery-v1/v2` plans retain their versions and provenance. Legacy
unprepared procedural archives acquire no retrospective source certificate.

## Save/load and legacy semantics

The general schema remains 3 and the checksum container V2. New worlds opt into
v1 explicitly. Save/load validate version, canonical rule/authored snapshot,
current rule compatibility and immutable prepared base files/route records.
Consumption, mounting and scheduler-owned injected pieces remain mutable.
Incompatibilities raise `SaveLoadError` without rewriting the original slot;
the existing backup policy remains.

Missing WorldState slots default to `legacy-information-v0` and no new
definition. Missing NodePool slots default to legacy provenance and no typed
records. The genuine B0 fixture tests actual unpickling of the old slot layout.
All existing pools, files, routes and consumption are retained. Uninitialized
hosts in that same save continue using the B0 clock/knowledge-dependent
algorithms; no mixed opt-in migration occurs. Version v0 identifies the
approved B0 probabilities and deterministic switch: incompatible future
configuration is rejected at save/load, not silently substituted.

## Validation and B2 boundary

`tests/historical_information_smoke.py` covers invariance, certificates, budgets,
protection, legacy slots, nondestructive rejection, finite actions, scheduler,
negative public disclosure and actual EN/ES Textual input. B0 tests remain.
External evidence covers the twelve audit seeds, A/B/C catalogues, baseline and
final regression, command-driven prologue runs, save/load and continuation.

B2 is implemented separately in [historical-radio-v1](historical-radio.md), reusing
these unchanged records for procedural emission content. Original hardware,
conservation, energy, programs and propagating waves are separate facts. Archives
do not activate transmitters. Exceptional repair/reactivation and its persisted
intervention provenance remain future work; B2 adds no retrospective rescue
emission, station repair, topology, new action, sensor or audio change.
