# `historical-radio-v1` contract — 4D-3e5c-B2

[Español](historical-radio.es.md). Implemented for external review, 2026-11-07.
Authorities: `worldgen/historical_radio.py`, `core/communications.py`,
`core/structural_recovery.py`, `model/world.py`, `config/balance.py`.
Tests: `tests/historical_radio_smoke.py` and the existing authored matrices.

## Equipment history and energy

Every certified `station`, `relay`, `waystation`, `ship` or `derelict` has
original communications hardware, including wrecks in those classes. This does
not imply present capability or messages. An explicit authored transmitter owns
the whole host; no procedural history is added, including `emissions: []`.

`RadioHistory` separates physical certificate, relative installation time, final
hardware condition, failure/destruction time, end of energy availability, emission
program, payload and historical source. `equipment_at(t)` projects original
installation, conservation, energy and operational capability at that time.

| Class | Original hardware | Serviceable at t=0 | Damaged but retained | Destroyed | Energy at t=0 | Expected operational capability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| station | 100% | 64% | 20% | 16% | 62.5% | 40% |
| relay | 100% | 81.25% | 12% | 6.75% | 80% | 65% |
| waystation | 100% | 71.4286% | 15% | 13.5714% | 70% | 50% |
| ship | 100% | 25% | 40% | 35% | 40% | 10% |
| derelict | 100% | 20% | 30% | 50% | 25% | 5% |

Conservation and energy use independent sampling domains. Capability is their
intersection, rather than another draw or the fraction of receivable signals.
Retained includes serviceable and damaged equipment, excluding destroyed hardware.
Energy can remain with destroyed radio, or intact equipment can lack power. Its
program may be absent or finished despite operational capability.

The model uses coarse epochs: installation 150–350 years before t=0; applicable
failure/destruction and energy loss 0.25–25 years before t=0. Before those limits,
hardware is considered serviceable and powered. Every emission ends no later than
the first applicable limit. These are experimental game-relative offsets, without
absolute civilization dates, survivors or electronic simulation. Destruction refers
to communications; it does not remove the physical site or its B1 archives.

## Identity, determinism and provenance

P1 adds a subtractive [host navigation policy](historical-information.md#p1-fixed-host-navigation-exclusions).
Original B1/B2 sampling is preserved independently of the policy-aware full
fingerprints. If the original selected navigation record is excluded at that
host, its procedural emission is absent; no other destination or environmental
payload replaces it. Equipment, energy, epochs and other hosts retain their
original projections. This adds no guarantee of a receivable prologue solution.

`RadioDefinition` pins version, canonical rule JSON, B1 fingerprint and explicitly
overridden hosts. Physical seed, manifest scope and certified identity enter
separate SHA-256 domains. No mutable RNG, Python hash, player clock, knowledge,
visit/materialization order or recovery activation selects history. A historical
query does not change `GameState`.

Existing `RadioEmitter` and `RadioEmission` are reused. Procedural IDs are
`@HR1:<host>` and `@HR1:<host>:0`. The `@` prefix is outside the authored editorial
grammar, preventing collisions without reserving existing authored IDs.
`resolve_emission` unifies both sources. There is no second ledger.

This version has at most one message per host. Program existence is independent
of present condition. Compared densities are sparse 30%, intermediate 55% and
abundant 80%. Only this threshold changes: equipment, energy, windows, selection
and sampling domains remain equal across profiles. The selected profile remains
`intermediate`; measurement never changes balance automatically.

Of programs, 65% are `continuous`, 35% `finite`. Repetition starts 30–120 years
before t=0. Continuous programs independently have a 25% scheduled-stop chance;
hardware failure or energy loss also closes them. Finite programs last 0.02–6
years, ending before t=0 and limited by hardware/energy. Repetition within a
window is not periodic scheduling; a periodic calendar remains a future extension.

30% of programs attempt navigation: they select only a B1-certified
`NavigationRecord` from uplink or typed files, with physical endpoints and a hop
of at most 45 ly. `historical_connection` remains distinct from
`navigation_solution`; source record ID and age caveat remain in the message.
If no record exists, environmental content is used without a replacement target.
Other families are beacon, recorded telemetry, technical notice, historical
distress, warning, unreadable route announcement, environmental carrier and
damaged data. Destroyed equipment may retain its final distress recording.
Every payload has EN/ES text and establishes no present human activity. No arc,
single or `piece_key` is consumed.

## Physics, reception and knowledge

Existing [spatial/temporal radio](radio-spacetime.md) applies: Euclidean 3D distance,
normalized emergency/station/relay power 0.25/36/400, receiver sensitivity and
propagation at c. Reference is `game-coordinate-seconds-v1`, with arrival window
`[start_t+d*YEAR_S, end_t+d*YEAR_S)`, open-ended without an end. Current host state
does not block a wave emitted before failure: past energy and present reception
are separate facts. Moving RETORNO legitimately changes delay and coverage.

Common gates still cover comms, radiod, supply, Core OS, transit and hibernation.
Ticks check their final instant; brief expired windows are not reconstructed.
Stopping radiod blocks capture, not historical transmission. Travel, sensors,
general clocks, hibernation and relativity remain unchanged.

Preparation, capture, file writing, reading/import and intel remain separate.
Canonical identity is `radio:<emission_id>` in `WorldState.radio_opportunities`.
Captures also retain actual receiver position and sensitivity for window validation.
Capturing alone imports no LINK and adds no contacts or coordinates.

C-DATA-004: procedural receipt events identify `comms`, not a hidden host;
filenames use `radio` and sequence without physical IDs. Their events omit internal
opportunity IDs. Navigation payloads may legitimately identify endpoints;
environmental payloads reveal neither host nor coordinates. CLI and Textual share
the writer and ledger. Status, diag, events, sounds and completion receive no hidden
catalogue. Only explicit, read-only `debug radio` shows examined history, cursor
and local cache count.

## Complete discovery in a bounded domain

Startup never generates or indexes the galaxy's transmitters. The certified
inverse inventory of `historical-world-v1` supplies unmaterialized sources.
For each 10 ly receiver cell, the complete domain is a 7×7×7 physical-sector cube,
covering the current maximum UPGRADED range of 30 ly. Cells sort by proximity
with stable ties. Complete means this domain, never the whole galaxy.

Per tick: at most four physical sectors and 64 examined sites, including silent
hosts. An offset resumes within crowded cells, preserving candidate 129. The
other half of the 128-candidate budget serves authored emitters with its own
cursor, preventing starvation. Procedural reception visits up to 64 cached
histories per tick with a circular cursor. The local cache holds at most 4096
histories with emissions per cache window. Once full, every cached candidate is
checked before continuing the next window from the physical cursor, preventing
permanent bias toward the first cells. In overflow mode the domain is revisited
after its last window to reevaluate future arrivals; this is necessary when all
sources do not fit in memory. Exhaustion never establishes silence. The pure page
exposes `complete`.

Only one local area is cached. Changing receiver cell resets it; completed
inventories that fit completely in cache are never scanned again within the same
cell. Cached emissions are
reevaluated spatially and temporally. Listening materializes no sectors, creates
no navigation files and discloses no candidates. Prepared emissions remain
deduplicated in the common ledger across area changes.

## F-DEAD-01 and persistence

The selector inspects at most 128 radio hosts per search in addition to existing
budgets, prioritizing accessible origins and then proximity. Exhaustion leaves an
incomplete result when no valid chain is found. Only the exact certified payload
LINK qualifies. The first stage remains accessible, arrived, protected, in range
and within its window. Radio stages retain the existing open-ended continuous
restriction. A previously captured emission can serve a later stage with the same
file and timestamp, without another capture. First stages retain their unreceived
source rule. Environmental messages never become navigation authority.
No universal exit or survival guarantee is introduced.

General schema 3 and V2 envelope remain. Specific versioning lives in
`WorldState.radio_history_version`/`radio_definition`. Cell cursor, within-cell
offset, derived local cache and reception offset persist. Save/load reconstructs
the exact searched segment to validate them. Overflow also persists window start
and remaining candidate checks. Validation includes rules, B1 relationship,
authored precedence, payload, canonical identity and physical receipt evidence.
Pre-B2 saves retain `legacy-radio-v0` without retrospective waves. Incompatibility
uses the existing understandable error and preserves the file. Existing legacy
fixtures remain and are tested.

## Measurement and future extension

[Validation report and matrix](../testing/historical-radio-review.md).
Measurements separate history, nominal-sensitivity potential, coverage at sampled
points and effective receipts in public walkthroughs. All three profiles remain
experimental. Physical density, topology, B1 and salvage are unchanged.

Future exceptional recovery would require retained/repairable hardware, energy
and physical dependencies, pre-existing historical archives and content authority,
intervention identity, actual start time and a persisted intervention ledger.
A new transmission must start after intervention and wait for propagation. B2
neither reactivates reserves, restarts, repairs nor invents emissions for the
failsafe. General electronics, population networks, interference and moving
emitters also remain outside scope.
