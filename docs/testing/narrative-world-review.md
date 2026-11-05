# RETORNO — 4D-3e4 external review report

Date: 2026-11-05, Europe/Madrid. [Español](narrative-world-review.es.md).
Status: productive minimum implemented and tested, **awaiting external approval**.
The new format is provisional and optional. F-DEAD-01 is not declared resolved.

## Focused correction after external review

This revision retains HEAD `d851d441b0548eb67035d5aa8cdb298db0499800` on `main`
and all 38 local files from the previous delivery. Only the eight files listed
below changed. No staging, commit or push occurred. Architecture, balance,
Textual, audio, AMANECER and F-DEAD-01 retain their previous state. The original
18 test groups retain their complete test bodies.

**Defect 1 — reserved tokens without bindings.** Pending tokens were detected
inside `render()`, which ran only when `spatial_bindings` existed. Startup was
reproduced incorrectly accepting `line: {{missing_9}}` without that block. A final
pass after rendering now always checks `line`, inline content, `content_ref`,
`content_ref_en/es`, `files` and active authored files. Original resource provenance
is retained even for private compiled references. `ContentError` identifies
package, file, field and token. The reserved grammar remains exactly
`[a-z][a-z0-9_]*` inside double braces; other braces and `[SECTOR_VAELOR]` remain
literals. No information is inferred from prose or editorial content activated.

**Defect 2 — essential document without an effective body.** A salvage opportunity
could pass based on a recoverable path alone; push channels checked a reference
but not its text. Startup was reproduced accepting an essential piece without
references or `line`. EN and ES now both require a non-whitespace body, using the
same reference precedence and fallback to EN as actual delivery. Salvage body
extraction is shared with `_file_for_salvage_piece`, retaining its `line` fallback
for absent references or exactly empty text before adding `log_header`. Push
channels do not acquire this fallback. Whitespace-only text, a log header or mail
headers do not count as an effective body. A missing referenced file still fails
loading even when `line` exists. Path/collision checks remain. Optional documents
without essential status may still have empty bodies; selection, placement and
delivery policies are unchanged.

**New tests.** Group 19 covers eight fields/sources without bindings, an unknown
token with bindings, successful resolution, literal braces and a catalogue with
no physical declarations. Group 20 covers 48 combinations of four channels and
twelve content scenarios, checking accepted deliveries in EN and ES. These cover
empty text, whitespace, headers only, explicitly empty ES, valid text, fallback
to EN, ES only, `line`, empty referenced text with `line`, whitespace with `line`,
and missing files. Two additional cases cover fallback through `files` and an
empty optional document. The new groups failed before the fix and pass afterward.

Result: **20/20 narrative groups PASS and 61/62 smoke scripts PASS** serially.
Only the previous `CARNAVAL_34` radiation failure remains; Textual passes in this
run. No dependencies needed installation. `git diff --check`: PASS. Previous
physical and variability evidence is unchanged.

Files changed in this correction (the final table lists all 38 phase files):

| File | Correction |
| --- | --- |
| `src/retorno/worldgen/narrative.py` | Final token validation independent of bindings, retaining provenance. |
| `src/retorno/core/lore.py` | Effective EN/ES bodies and salvage helper shared with delivery. |
| `tests/narrative_world_integration_smoke.py` | Groups 19 and 20; the previous 18 are unchanged. |
| `docs/narrative-world-contract.es.md` | Clarified reserved grammar and effective essential content. |
| `docs/narrative-world-contract.md` | English contract counterpart. |
| `docs/testing/narrative-world-review.es.md` | Updated report and this revision's results. |
| `docs/testing/narrative-world-review.md` | English report counterpart. |
| `docs/testing/narrative-world-test-results.json` | Full run and evidence for both corrections. |

The new ZIP is `../RETORNO-4D-3e4-correction-review.zip`, containing all **38
new/modified files** from 4D-3e4, including the previous delivery. Relative paths
are retained, inventory/member bytes are compared against the tree, and CRC is
verified. SHA-256 is delivered in its accompanying `.zip.sha256` file. The earlier
ZIP is preserved. Public commands and diegetic manuals do not change in this correction.

## Result and Git state

Branch `main`; upstream `origin/main`. Initial and final HEAD:
`d851d441b0548eb67035d5aa8cdb298db0499800`. The remote was verified with
`git ls-remote origin refs/heads/main` and matches. The initial tree was clean;
the final tree contains the unstaged changes listed below. No `git add`, commit
or push was performed. No unrelated work was present or modified.

Real bootstrap compiles all active stories' requirements before returning a game.
The scheduler selects preexisting hosts and spatial text is frozen per game.
Two optional packages and 20 integration groups are delivered. Active authored
data, the five current singles and `narrative/amanecer/` are unchanged; only two
manuals under `data/` were updated.

## Initial audit and actual boundaries

AGENTS, roadmap v1.2 D01–D24 and §3.4/3.5, canon/coherence, historical integration,
worldgen/scheduler/discovery/intel/loading references, historical guides and
AMANECER README/CANON/LOCATIONS were consulted. Bootstrap, loaders, manifest,
generator, lore, Engine, REPL, models and save/load were reviewed.

| Question | Audited behaviour and adaptation |
| --- | --- |
| Activation | Root location/arc JSON only; singles only through their index. Zero active arcs, five singles, five locations. No template or editorial Markdown scan. |
| Pre-world inputs | Previously bootstrap materialized authored sites and captured rules, pinning the manifest later. It now collects, validates and compiles catalogue physics/clues and reserves opportunities; requirement-bearing manifests are pinned at bootstrap. |
| Rereads | Arcs, singles, locations and texts were reread during ticks, pools and delivery. A snapshot is now kept; legacy loaders remain domain boundaries after installed-file verification, while new requirements consume compiled snapshots. Modules/physical configuration retain previous fingerprints. Startup/manuals have separate loaders. |
| Ad hoc creation | Lore used `_spawn_ad_hoc_candidate_for_forced_piece` and coordinate sampling to fabricate hosts. `_select_historical_host_for_forced_piece` replaces it; samplers were removed and the old name delegates for compatibility. |
| Structural consumers | `register_hidden_anchored_node` remains used by `exploration_recovery`. Recovery/deadnodes were not rewritten; integration belongs to e5. |
| Candidates | ID/family/kind, region, time, distance, hops, window and channel rules. The new selector queries certified cohorts, including unmaterialized sites. Singles retain independent rolls. |
| Pools | One initialization for known/forced-hidden/anchor sites; frozen uplink routes; visit closes the window. Reservations finalize before first closure when placement policy permits. Exhausted sources never reopen. |
| Corrupt intel | It already queried worldgen without fabricating a site specific to the text. Legitimate discovery remains, now checking the actual radius and retaining uncertain tokens; it is not a narrative repair mechanism. |
| Saves | Pickle/checksum pinned physics but assignments could reread different definitions/texts. Snapshots persist and changed catalogues are rejected, preventing a different piece being delivered under an old identity. |

## Proposed format and compilation

Complete contract, examples and AMANECER matrix: [authoring guide](../narrative-world-contract.md).
Real examples: [`alpha.json`](../../tests/fixtures/narrative_world/alpha.json),
[`beta.json`](../../tests/fixtures/narrative_world/beta.json) and their EN/ES TXT.
Tests install them only into a temporary `data` copy.

`world_requirements.version = narrative-world-v1` adds entities, references,
relations and nonbinding claims. Positions support fixed coordinates, seeded
boxes and seeded offsets, with sector/region filters. Relations are `near`,
`physical_link`, `historical_association`, with endpoint kind checks. Sharing
requires references instead of redeclarations. Prose and document `constraints`
never imply existence. Existing formats do not have to adopt the block.

Abbreviated real example:

```json
{"id":"TEST_WRECK","kind":"ship","name":"Test Wreck",
 "position":{"offset_from":"Horizon","offset_box_ly":[[0.5,1.2],[0,0],[0,0]]}}
```

```json
{"type":"near","from":"TEST_STATION","to":"TEST_WRECK","min_ly":0.5,"max_ly":1.2}
```

The compiler resolves identities/aliases, checks resources/kinds, orders
dependencies, searches a finite domain and verifies relations using the productive
manifest. Each variable position has 32 seeded/ID-based candidates; the search
limit is 4096 steps. Game RNG is untouched. Proven conflicts are `invalid` or
`unsatisfiable`; incomplete work is `not_evaluated`, blocks startup and is never
reported as success. `physical_link` checks existing topology, without moving
fixed sites or adding edges. The 45 ly cap and possible isolation remain.

Optional same-version `spatial_bindings` supports `id`, `sector`, `coord` values.
Only declared explicit `{{...}}` tokens are substituted in documents. `line`,
inline content and referenced TXT compile to private frozen text addresses.
Reading does not choose positions again. `[SECTOR_VAELOR]` remains inactive.

## Seed variability evidence

Same two stories, seeds 0–7. The declared offset gives the wreck the station's
Y/Z; its X and the station's full position are shown. Fixed host `(26,27,1)` and
relay `(27,27,1)` have a certified 1 ly physical edge.

| Seed | Station (x,y,z), ly | Wreck x, ly | Distance, ly | Station sector | Region |
| --- | --- | --- | --- | --- | --- |
| 0 | (150031.241312, 5.543181, 2.646261) | 150032.083876 | 0.842564 | S+15003_+000_+000 | halo |
| 1 | (150018.621699, 2.269562, 2.131623) | 150019.377670 | 0.755972 | S+15001_+000_+000 | halo |
| 2 | (149990.661433, 7.404138, 3.834968) | 149991.197861 | 0.536428 | S+14999_+000_+000 | disk |
| 3 | (150045.295446, 5.964927, 7.917574) | 150046.437712 | 1.142266 | S+15004_+000_+000 | halo |
| 4 | (150026.522888, 6.520925, 6.535723) | 150027.682503 | 1.159615 | S+15002_+000_+000 | halo |
| 5 | (150049.645549, 2.307534, 4.350687) | 150050.415146 | 0.769597 | S+15004_+000_+000 | halo |
| 6 | (150017.459114, 5.158522, 7.532469) | 150018.602833 | 1.143719 | S+15001_+000_+000 | halo |
| 7 | (150027.147820, 5.931495, 2.663212) | 150028.305660 | 1.157840 | S+15002_+000_+000 | halo |

Eight different positions, inclusive 0.5–1.2 ly relation, stable identities,
matching clues, reading/exploration independence and no initial reveal are verified.
The box was intentionally placed near the disk/halo boundary to demonstrate
geographic variation. This sample does not prove universal gameplay variety,
global accessibility or guaranteed discovery.

## Authored quota/connectivity effects

Four new sites; only their focus cohorts are compared (two for these four seeds).
These are graphs **induced by those cohorts**, not the galaxy. Data also includes
incident edges and per-seed inventory.

| Seed | Sites before→after | Procedural | Hubs | Induced edges | Induced components |
| --- | --- | --- | --- | --- | --- |
| 0 | 4 → 5 | 4 → 1 | 0 → 3 | 2 → 3 | 2 → 2 |
| 1 | 5 → 5 | 5 → 1 | 0 → 3 | 3 → 3 | 2 → 2 |
| 2 | 1 → 4 | 1 → 0 | 0 → 3 | 0 → 2 | 1 → 2 |
| 3 | 5 → 5 | 5 → 1 | 1 → 3 | 4 → 4 | 2 → 2 |

Authored occupies existing quotas and can exceed authored targets without adding
procedural slots. Probabilities and quantities were not changed. The e2 comparator
was rerun for `0..7,29,271828`: aggregates, every row, inventory, resources and
configuration exactly match versioned measurements; only benchmark time/memory
differs. Legacy witnesses were not rewritten.

## Opportunities, delivery and exhaustion

All installed `force=true` pieces are validated as essential before play, including
effective channel, time window and recoverable file paths. Finite queries allow
up to 64 sectors. A search without proof does not certify galactic absence;
hop constraints on partial graphs are reported conservatively. Host/channel/
sector/provenance are reserved without revealing anything.

Policies still decide attempts. At pool initialization, an eligible reservation
can prepare content before visit closure. A document can be hosted on a wreck
with no other resources. Assignment, preparation, trigger, receipt and reading/
import remain separate. A deadline after cleanup leaves a piece pending, never
reopening the pool or adding history. Real drone salvage and all four other
delivery channels are exercised. Singles retain `p = clamp(base × weight)`:
weight 0.4 with base 0.05 gives 0.02. Nonappearance does not remove declared physics.
File path collisions do not silently replace documents.

## Intel compatibility

| Syntax | Verified result |
| --- | --- |
| `NODE:` | Valid ID/name/alias resolves history and materializes lazily; invalid/pending literals remain references without fabricated stations. |
| `LINK:` | Physical endpoints and ≤45 ly; missing endpoints/over-cap hops remain intel without publication. Retains the 4D-1 operational contract, which does not require a historical edge. |
| `SECTOR:` | Regional intel and lazy materialization, without inventory reveal. |
| `COORD:` | `NAV_...` `nav_point`, without station or automatic route; finite numbers. |
| `[INTEL]` | Authored ID/name/alias and bare-sector selector; explicit instruction blocks use the line parser without extra corruption. Ordinary prose never declares physics. |
| Corruption | Uncertain zero-confidence token; existing discovery bounded by actual radius and primary protection. No corrective installations. |

Reading and explicit import share the parser. Deliberate scan/manual solve
exceptions remain. Primary protection also resolves target aliases to canonical IDs.

## Persistence and versioning

Persisted snapshot: contract version, active catalogue fingerprint, definitions,
rendered texts, aliases, positions, relations/results and reservations. The manifest
retains final authored sites and catalogue identity when new declarations exist;
otherwise the previous physical scope remains.

Policy: reject save/load if the installed catalogue changes, including referenced
texts, identity changes or package removal. Restoring originals permits loading;
files are not deleted. Requirement-bearing runtime consumes snapshots without
delivering changed definitions. Three save/load cycles preserve world, routes,
knowledge and progress.

V2 container and schema 3 remain, with an added field. Older saves without the
required snapshot are explicitly rejected, without migration or deletion. Physical
changes remain subject to the previous rules fingerprint. Sites are never rebuilt
from a changed catalogue.

## Roadmap §3.4 and §3.5 acceptance

| Requirement | Evidence |
| --- | --- |
| §3.4.1 Stable secret authored declaration | New groups 01–03; manifest integration regression. |
| §3.4.2 Mention versus intel | Groups 01,07,12 and both packages' prose. |
| §3.4.3 Valid/invalid/pending NODE | Group 07 through reading and explicit import. |
| §3.4.4 Valid/missing/over-cap LINK | Groups 04,07,11,14; known_routes_integrity. |
| §3.4.5 SECTOR/COORD distinct from stations | Group 07; sector_intel_validation. |
| §3.4.6 Forced piece and single on legitimate hosts | Groups 04,05,14,15; lore regression. |
| §3.4.7 No retrospective lore creation | Groups 04,12,15; unchanged manifest before/after and dynamic creator forbidden in tests. |
| §3.4.8 No pool reopening | Group 06 and pool/deadnode fixtures. |
| §3.4.9 Repeated save/load | Groups 08,17; save_load, scan memory, waypoint and manifest integration. |
| §3.5.1 Two packages, loading/exploration orders | Group 02, reversed records and reverse materialization. |
| §3.5.2 Authoring without package-specific Python | Alpha/beta use only generic contracts and real bootstrap. |
| §3.5.3 Contradictions before play | Groups 09,11,13,17,18; JSON diagnostics. |
| §3.5.4 Prose, rumour and intel | Groups 01,07,12 and physically inert claims. |
| §3.5.5 Absent optional piece, stable physics | Group 05, controlled zero probability and same site. |
| §3.5.6 Versioning/changed catalogue | Groups 08,17: modification, removal and snapshot-less saves rejected. |
| §3.5.7 Authored measurements | Group 10 and ten-seed productive comparison. |

These cases pass within the documented finite scope. Arbitrary constraints,
every seed and arbitrary package combinations are not promised.

## Test results

Exclusive interpreter: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.
Repository tests are scripts with their own runners; pytest is not installed.
Initial suite: 60/61 PASS. Final serial suite: **61/62 PASS**; the new script
includes **20 PASS groups**: the original 18 and two new groups for this focused correction. Productive comparator: PASS for ten seeds.

The existing `radiation_hull_smoke.py:183`, `AssertionError: []`, remains in the
`CARNAVAL_34` radiation witness. Neither that test nor radiation code was changed.
The Textual theme test intermittently produced `NoMatches #header` under concurrent
execution. It was also reproduced on original HEAD exported to `/tmp` (1 failure
in 4 concurrent runs), and passed standalone and in the final serial suite.
UI/audio were not changed to conceal it.

| Script | Final result | Seconds |
| --- | --- | --- |
| `audio_config_smoke.py` | PASS | 1.26 |
| `audio_runtime_notice_smoke.py` | PASS | 0.07 |
| `config_audio_smoke.py` | PASS | 0.17 |
| `contacts_sector_smoke.py` | PASS | 0.16 |
| `contacts_smoke.py` | PASS | 0.23 |
| `deadnode_chain_detours_smoke.py` | PASS | 3.46 |
| `deadnode_chain_planner_smoke.py` | PASS | 4.24 |
| `deadnode_cooldown_zero_smoke.py` | PASS | 0.37 |
| `deadnode_opportunity_selection_smoke.py` | PASS | 5.04 |
| `debug_add_commands_smoke.py` | PASS | 0.22 |
| `debug_galaxy_smoke.py` | PASS | 0.27 |
| `debug_lore_arcs_smoke.py` | PASS | 0.26 |
| `debug_worldgen_graph_smoke.py` | PASS | 0.26 |
| `drone_completion_context_smoke.py` | PASS | 0.22 |
| `drone_modular_v1_smoke.py` | PASS | 1.04 |
| `drone_recall_all_smoke.py` | PASS | 0.26 |
| `drone_salvage_survey_smoke.py` | PASS | 0.70 |
| `energy_policy_smoke.py` | PASS | 3.20 |
| `exploration_recovery_smoke.py` | PASS | 0.60 |
| `forced_hidden_ad_hoc_smoke.py` | PASS | 0.31 |
| `galaxy_physical_model_smoke.py` | PASS | 0.18 |
| `hibernate_radiation_wake_smoke.py` | PASS | 0.32 |
| `hibernate_sequence_assets_smoke.py` | PASS | 0.03 |
| `intel_recent_order_smoke.py` | PASS | 0.47 |
| `job_id_numbering_smoke.py` | PASS | 0.24 |
| `known_routes_integrity_smoke.py` | PASS | 2.48 |
| `lore_channel_preference_and_unlock_smoke.py` | PASS | 0.20 |
| `lore_distance_from_start_smoke.py` | PASS | 0.15 |
| `lore_secondary_count_weights_hard_smoke.py` | PASS | 1.07 |
| `lore_smoke.py` | PASS | 0.16 |
| `mail_metadata_and_log_header_smoke.py` | PASS | 0.23 |
| `narrative_world_integration_smoke.py` | PASS | 19.16 |
| `nav_abort_waypoint_cleanup_smoke.py` | PASS | 3.62 |
| `nav_map_galaxy_dependencies_smoke.py` | PASS | 0.22 |
| `nav_map_galaxy_determinism_smoke.py` | PASS | 0.27 |
| `nav_map_galaxy_smoke.py` | PASS | 0.25 |
| `procedural_radiation_smoke.py` | PASS | 0.16 |
| `radiation_hull_smoke.py` | FAIL previo / preexisting | 1.14 |
| `route_hop_cap_smoke.py` | PASS | 0.25 |
| `route_solve_out_of_range_origins_smoke.py` | PASS | 0.37 |
| `save_load_smoke.py` | PASS | 0.35 |
| `scan_job_smoke.py` | PASS | 0.47 |
| `scan_observation_memory_smoke.py` | PASS | 10.41 |
| `sector_intel_validation_smoke.py` | PASS | 0.76 |
| `sensor_detection_factor_smoke.py` | PASS | 3.49 |
| `ship_layout_output_smoke.py` | PASS | 0.22 |
| `ship_survey_radiation_smoke.py` | PASS | 0.22 |
| `smoke_test.py` | PASS | 0.34 |
| `textual_active_jobs_job_id_smoke.py` | PASS | 0.24 |
| `textual_command_spacing_smoke.py` | PASS | 3.74 |
| `textual_completion_context_smoke.py` | PASS | 1.91 |
| `textual_theme_smoke.py` | PASS | 3.79 |
| `transit_radiation_progression_smoke.py` | PASS | 0.16 |
| `uplink_authored_and_failsafe_smoke.py` | PASS | 0.57 |
| `uplink_once_per_node_smoke.py` | PASS | 0.36 |
| `uplink_only_delivery_retry_smoke.py` | PASS | 1.68 |
| `worldgen_manifest_integration_smoke.py` | PASS | 5.05 |
| `worldgen_manifest_prototype_smoke.py` | PASS | 2.81 |
| `worldgen_modules_pool_smoke.py` | PASS | 1.66 |
| `worldgen_preexistence_catalog_smoke.py` | PASS | 1.99 |
| `worldgen_preexistence_characterization_smoke.py` | PASS | 0.69 |
| `worldgen_sparse_archetypes_smoke.py` | PASS | 10.20 |

JSON [results](narrative-world-test-results.json) and
[measurements](narrative-world-measurements.json) include baseline/final runs,
new groups, intermittent baseline reproduction, positions, distances, diagnostics
and physical comparisons. Only temporary saves were used. No real save was
opened or modified. UI was exercised through headless smoke tests; no manual
audiovisual e6 session was performed.

## AMANECER matrix

| Category | Elements |
| --- | --- |
| Supported | Tábano `ship` with variable position and stable identity; host-ID-restricted documents; dynamic sector/coordinates; physical destination and certified direct edge. |
| Pending data adaptation | Declarative JSON, EN/ES TXT, boxes/regions/relations and channels; Tábano route bound to a real destination with specific verified access. |
| Editorial decision | Bruma's present state/playable kind; playable Liria; suspicious destination's nature; fate of the seven people. |
| Unimplemented system | VAELOR as a star system, planets/components; dynamic physical conservation and simulated chronology/survival. |

AMANECER was not activated and its Markdown was not copied. No canonical
coordinates, editorial destinations, separate planets or facts about people
were invented.

## Documentation, pending decisions and limits

The new EN/ES guide is authoritative for this change and contains executed
examples. Previous guides have explicit notices identifying superseded behaviour
while preserving historical context. Intel manuals remain bilingual and diegetic.
`help` and `help --verbose` need no changes: there are no new commands/channels or
public intel syntax; authoring blocks belong to the technical guide. EN/ES pairs,
fixture tokens and added links were reviewed.

Pending approval: stabilize `world_requirements`/`spatial_bindings` as a permanent
public interface and accept the finite bounds. AMANECER editorial decisions remain
open. General declarative multihop paths, planetary systems, historical dates and
mod management remain outside this contract. e5 retains structural recovery
integration. No new blocker requires expanding this phase; this is not presented
as a universal solver.

`git diff --check`: **PASS**, no output. The review ZIP is verified against the
tree's exact inventory and member bytes, preserving relative paths and including
only new/modified files. It is outside the repo at `../RETORNO-4D-3e4-correction-review.zip`.
It contains no saves, `.git`, unchanged code or temporary test trees. Its SHA-256
is delivered beside the ZIP.

## Modified/new files and purpose

38 files, unstaged. The ZIP includes this report and its Spanish counterpart.

| File | Purpose |
| --- | --- |
| `data/manuals/commands/intel.en.txt` | Updated EN/ES operational intel manual. |
| `data/manuals/commands/intel.es.txt` | Updated EN/ES operational intel manual. |
| `docs/arcs.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/arcs.md` | EN/ES update and notice about the superseded historical body. |
| `docs/content-loading.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/content-loading.md` | EN/ES update and notice about the superseded historical body. |
| `docs/design/historical-worldgen-integration.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/design/historical-worldgen-integration.md` | EN/ES update and notice about the superseded historical body. |
| `docs/intel_lore.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/intel_lore.md` | EN/ES update and notice about the superseded historical body. |
| `docs/narrative-world-contract.es.md` | Current EN/ES guide with real examples and bounds. |
| `docs/narrative-world-contract.md` | Current EN/ES guide with real examples and bounds. |
| `docs/systems/discovery-navigation-intel.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/systems/discovery-navigation-intel.md` | EN/ES update and notice about the superseded historical body. |
| `docs/systems/lore-scheduler.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/systems/lore-scheduler.md` | EN/ES update and notice about the superseded historical body. |
| `docs/systems/world-generation.es.md` | EN/ES update and notice about the superseded historical body. |
| `docs/systems/world-generation.md` | EN/ES update and notice about the superseded historical body. |
| `docs/testing/narrative-world-measurements.json` | Reproducible test or measurement evidence. |
| `docs/testing/narrative-world-review.es.md` | EN/ES external review report. |
| `docs/testing/narrative-world-review.md` | EN/ES external review report. |
| `docs/testing/narrative-world-test-results.json` | Reproducible test or measurement evidence. |
| `src/retorno/bootstrap.py` | Pre-play compilation; lazy declared sites without initial contacts. |
| `src/retorno/cli/repl.py` | Shared intel parser, aliases, historical resolution, uncertainty and recovery radius. |
| `src/retorno/core/lore.py` | Essential opportunities, reservations and historical selection; pools and delivery. |
| `src/retorno/io/save_load.py` | Required catalogue fingerprint and safe incompatibility rejection. |
| `src/retorno/model/world.py` | Persistent narrative snapshot. |
| `src/retorno/runtime/data_loader.py` | Shared nonrecursive boundary with provenance and strict index validation. |
| `src/retorno/worldgen/generator.py` | Snapshot integration with identity and authored materialization. |
| `src/retorno/worldgen/manifest.py` | Optional catalogue identity within manifest scope. |
| `src/retorno/worldgen/narrative.py` | Compiler, validation, catalogue, finite geometry and versioned bindings. |
| `tests/fixtures/narrative_world/alpha.en.txt` | Optional synthetic package or bilingual text; inactive in production. |
| `tests/fixtures/narrative_world/alpha.es.txt` | Optional synthetic package or bilingual text; inactive in production. |
| `tests/fixtures/narrative_world/alpha.json` | Optional synthetic package or bilingual text; inactive in production. |
| `tests/fixtures/narrative_world/beta.en.txt` | Optional synthetic package or bilingual text; inactive in production. |
| `tests/fixtures/narrative_world/beta.es.txt` | Optional synthetic package or bilingual text; inactive in production. |
| `tests/fixtures/narrative_world/beta.json` | Optional synthetic package or bilingual text; inactive in production. |
| `tests/narrative_world_integration_smoke.py` | 20 acceptance groups through real bootstrap/runtime/save paths. |
