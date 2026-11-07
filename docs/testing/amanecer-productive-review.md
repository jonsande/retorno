# RETORNO — 4D-3e5c-C2b, external review

Base: updated `main`, `12887bb` (2026-11-07). Arc installed in the working tree;
**complete playable journey not certified**. Exploration stops for discovery
review without adding corrective clues or routes.

## Files

- New `data/arcs/amanecer_elena_01.json` and ten EN/ES `.txt` files under
  `data/lore/packs/amanecer_elena_01/`: byte-identical copies of the approved draft.
- New `tests/amanecer_productive_integration.py` (structural check) and
  `tests/amanecer_public_journey.py` (bounded public reproduction).
- Three requested regressions adapted to the populated catalogue: reusable
  temporary fixtures and synthetic-piece selection by identity.
- EN/ES narrative contract, scheduler, relative design and integration README
  synchronized. `narrative/amanecer/LOCATIONS.md` and new `LOCATIONS.en.md` record
  the Liria decision and preserve the previous undecided editorial status.
- This EN/ES report and productive/journey JSON evidence under `docs/testing/`.
  The ZIP inventory contains exact paths and SHA-256 for each file.

No production Python, other arcs, singles, worldgen, radio, F-DEAD-01, balance,
resources, audio or Textual changed. Draft and manuscripts remain intact. Previous
local `TODO.md` changes are preserved and excluded from the package.

## Tests

Interpreter: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.

| Script | Result |
| --- | --- |
| `tests/lore_relative_placement_integration.py` | PASS: three seeds, EN/ES, salvage/reading, reservations and persistence with temporary fixture |
| `tests/narrative_world_integration_smoke.py` | PASS: 20 checks |
| `tests/authored_closing_shift_integration.py` | PASS: compilation and EN/ES journey |
| `tests/amanecer_productive_integration.py` | PASS: exact copies, installed loading, geometry, nondisclosure, file paths, reservations, save/load and no duplicate prepared files |
| `tests/amanecer_public_journey.py` | Executed on seed 701: incomplete journey, not an accessibility PASS |

The three regressions initially failed on fixture assumptions predating the first
active arc (empty catalogue, absent text directory, first piece = synthetic piece);
only those tests were corrected. No reproducible defect required engine changes.
The full suite was not run.

Seeds 1, 29 and 701 were used only for geometry/distribution: three distinct hosts,
stable Liria positions and HARBOR_12–Liria LINK below 45 ly. Productive checks cover
EN/ES in 701 and persistence without duplicate prepared files. C2a checks delivery
and reading using a relocated fixture: **it does not prove a public journey**.
New-catalogue saves load; previous-catalogue saves are rejected by fingerprint
without changing the file. Retain the original catalogue for old voyages.

## Public journey and concrete block

Reproduce with `tests/amanecer_public_journey.py`. It uses normal prologue 701,
parser, engine and public reading/uplink/hibernation handlers, without debug,
teleportation, state/resource/RNG edits. Waits use one-second steps; long voyages
use existing hibernation. It first repairs generation/distribution/communications,
starts sensors and discovers ECHO-7. Salvaging and reading its cache legitimately
reveals HARBOR_12. The policy selects only known contacts with an acquired route
or within sensor range; it prioritizes known authored destinations, then approaches
HARBOR_12. The limit is six stops; it ends after five with no remaining option
that meets that policy.

Observed itinerary: `ECHO_7 → P-2.2.1.0 → P-0.4.0.0 → P-0.2.1.1 → P-2.2.0.0`.
Elapsed time: 2,210,349,022.43 s (70.09 years). Four long transits take approximately
20.37 + 17.97 + 16.77 + 14.98 years. At the third stop D1 lacks battery for
salvage/recall; the itinerary continues without solving that maintenance problem,
and D1 becomes disabled. At the fifth stop distribution is LIMITED: `power on
sensors` and `boot sensord` require NOMINAL; uplink cannot continue with datad
stopped. The strategy has no maintenance planner and does not exhaust alternatives:
**its failure does not establish that variable placement makes the arc impossible**,
or that every legitimate avenue has been exhausted.

| Distinction | Evidence |
| --- | --- |
| Physically existing host | Yes: certified witness `P-4.1.0.1` in 701, materialized by existing mechanisms. |
| Accessible host | Not certified from the prologue. The finite graph query also finds no witness path from ECHO-7; this is not global absence. |
| Host known to the player | No at journey end. Reservation is inspected only after the experiment to assess its outcome. |
| Recoverable document | Valid reserved/prepared file; salvage and reading pass in an equivalent temporary fixture, not through this journey. |
| Liria route obtained/imported | No in the public journey. C2a imports the valid LINK by reading the clue. |
| Liria travel and four recoveries completed | Not from the prologue; exclusive assignment and recovery mechanism are checked only with a fixture. |

Full evidence: `amanecer-public-journey-evidence.json`; structural evidence:
`amanecer-productive-evidence.json`. These are development observations, not player
knowledge. **Open risk:** seeded reservation and physical existence do not ensure
reasonable clue discovery or a public route to it. No impossibility is asserted
and no canon/route correction is proposed. Do not promote this integration as
playably validated until this point is reviewed.

Help and diegetic manuals are unchanged: no new commands, and announcing the
reserved location would reveal secrets. No `git add`, commit or push.
