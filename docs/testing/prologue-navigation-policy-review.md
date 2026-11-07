# RETORNO — 4D-3e5c-P1

Base: local tree on `main` `12887bb`, with pending C2b and FAST_SANDBOX work.
The ZIP is incremental for that tree; it does not repackage prior work.

## Cause and correction

B1 selected certified destinations without an authored host policy. Seed 29
selected ECHO_7 → HARBOR_12 and uplink published that hop. FAST_SANDBOX inherited
the effect by consuming the same uplink during preparation.

`data/locations/echo_7.json` declares `navigation_policy`, version
`host-navigation-exclusions-v1`, with `exclude_destinations: ["HARBOR_12"]`.
It is captured before exploration. Only excluded selected records/files are
removed, without new draws or slot refills. B2 keeps its original choice and
suppresses an emission when the selected record is excluded, without a replacement
payload. Conflicting authored LINK files fail before play; testimony is never
rewritten. The original EN/ES cache and its HARBOR_12 contact remain intact.

The full fingerprint includes policy; retained draws, IDs and bodies use the
previous sampling definition without that field. The nonphysical field is also
excluded from the physical fingerprint. Positions, topology, scope and universe
IDs do not change. An additional comparison with the original producers saved
before editing confirms the intended differences for seeds 1, 29 and 701 and
their inspected hosts: only the excluded record disappears and definition
fingerprints change.

## P1-owned files

- `data/locations/echo_7.json`: declarative exclusion.
- `src/retorno/worldgen/information.py`: capture/validation, stable sampling and
  subtractive uplink/file exclusion.
- `src/retorno/worldgen/historical_radio.py`: preserves draws and prevents
  replacement of excluded navigation emissions.
- `src/retorno/worldgen/radio.py`: separates policy from physical catalogue.
- `tests/prologue_navigation_policy_smoke.py`: new focused regression.
- `tests/historical_information_smoke.py`, `tests/historical_radio_smoke.py` and
  `tests/structural_recovery_smoke.py`: fixture adjustments for the active C2b
  catalogue, separate physical hash and isolated quota/protection/old-save checks.
- EN/ES B1/B2 contracts, this EN/ES report and JSON evidence under `docs/testing/`.

Fixture adjustments retain their assertions: B0 loads with its original catalogue
in a temporary copy; the dense cell uses 300 hosts to exceed 128 emissions (260
produced 123); the shared-ledger test fixes seed 1. F-DEAD-01 logic is unchanged.
C2b, FAST_SANDBOX, TODO and all previous work are preserved. No AMANECER, balance,
maintenance, route solve, range, physical connections, manuscripts or ECHO-7
texts are modified.

## Validation

Interpreter: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.

| Script | Result |
| --- | --- |
| `tests/prologue_navigation_policy_smoke.py` | PASS, four focused groups |
| `tests/historical_information_smoke.py` | PASS, 16 groups |
| `tests/historical_radio_smoke.py` | PASS, 27 groups |
| `tests/fast_sandbox_smoke.py` | PASS |

- **29:** ECHO-7 uplink drops from three to two original records, without a
  substitute; checked in FAST_SANDBOX and through normal-prologue commands.
  Salvaging and reading the cache grant the contact without a route. EN/ES checked.
- **1:** public journey from FAST_SANDBOX: read ECHO-7 cache/uplink, follow its
  first acquired destination `P-2.2.2.0`, uplink there, then travel to HARBOR_12.
  Both 24.14 and 17.43 ly hops remain; actual arrival without debug, teleportation
  or state/resource edits. The introduction is not repeated.
- **701:** other-host records remain, including `P-2.1.0.0:/logs/nav.log` toward
  HARBOR_12. No public access to that source is asserted and the decades-long
  random itinerary is not repeated.
- A separate fixture exercises actual navigation-file exclusion and suppression
  of a selected B2 emission without replacement; production seeds alone do not
  exercise all these cases. Queries are pure and geometry is stable.
- New save/load, exhausted uplink without duplicates, nondestructive old-catalogue
  rejection and loading that same save after restoring its catalogue.

No full suite or expanded seed sweep was run.

## Versioning, limits and pending guarantee

Versioned additive extension: B1/B2 and save-schema versions stay unchanged.
Without policy, the previous v1 producer remains identical. The JSON changes the
installed hash and full B1/B2 fingerprints: previous-catalogue saves are rejected
through the existing contract without migration or deleting routes. Retain/restore
their catalogue to continue them. No broad migration is introduced.

The rule covers B1 and derived procedural B2; independent authored emitters and
scheduler pieces retain their contracts. Prologue completion is not guaranteed.
Certification still needs a complete pre-play chain from legitimate initial
knowledge to a recoverable intermediate source and finally HARBOR_12, covering
channels, hop bounds, temporal radio availability, protections and public
acquisition/import. An existing host or isolated clue is insufficient; exhausted
budgets remain incomplete searches.

Help and diegetic manuals are unchanged: this is an authoring rule without new
commands or public information. Inventory and SHA-256 accompany the ZIP. No
`git add`, commit or push; stop for external review.
