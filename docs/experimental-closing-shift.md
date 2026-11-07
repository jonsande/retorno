# 4D-3e5c-C1 — The closing shift

[Español](experimental-closing-shift.es.md). Experimental test content;
**neither definitive narrative canon nor installed content**.
Base: `main`, `a0acbd1` (local HEAD at the start).

New files: `tests/authored_closing_shift_integration.py`, this note and its
translation, and `tests/fixtures/authored_closing_shift/`: `arc.json`, `single.json`,
`closure.en.txt`, `closure.es.txt`, `repetition.en.txt`, `repetition.es.txt`,
`inventory.en.txt`, `inventory.es.txt`.

Cierre is a closed station; Margen holds an automatic loop of its closure
register; Estiba is a withdrawn tug declared as an explorable `ship`.
Lamps and a kettle remain uncollected. The documents do not establish the
people's fate or claim any present survivors.

The arc declares the three identities once through `world_requirements`.
Cierre is at `(0.002, 0.002, 0)` ly; Margen is `0.002` ly from Cierre;
Estiba is `0.002–0.003` ly from Margen, with seed-dependent coordinates.
Certification covers ECHO-7/Cierre proximity, a Cierre/Margen physical edge,
Margen/Estiba proximity and Cierre/Estiba historical association.
`spatial_bindings` freeze real IDs, sectors and coordinates in clues.
The operative ECHO-7/Cierre LINK does not assert a direct historical edge.

The primary is an ECHO-7 to Cierre uplink LINK. The two secondaries are a
salvaged register at Cierre (LINK to Margen) and its radio repetition at Margen
(NODE and LINK to Estiba). The inventory single is placed separately at Estiba;
it has no arc progression condition and unlocks nothing else. All four pieces
use `hard` forcing for this test, without balance changes. The single's distance
filters certify Estiba for tested seeds; they are not a universal ID restriction.

The `closing-archive-loop` emission starts at `t=-31536000` s and continues as
an automatic archive. It is bound to the secondary: proximity and radiod alone
do not deliver it; the scheduler and a legitimate dock trigger prepare it.
Cierre and Estiba declare emitters with no emissions. B1/B2 remain enabled.

The tested public journey uses ordinary sandbox mode, without debug:

1. `power off security`, `dock ECHO_7`, `wait 60`, `uplink` (also repeated).
2. `undock`, `wait 60`, `nav CLOSING_STATION`, wait for ETA; `dock CLOSING_STATION`,
   `wait 60`, `power on drone_bay`, `drone deploy D1 CLOSING_STATION`, `wait 30`,
   `drone salvage data D1`, `wait 60`, `cat /remote/CLOSING_STATION/logs/records/closing_shift.en.txt`.
3. `drone recall D1`, `wait 60`, `power off data_core`, `power on comms`,
   `boot radiod`, `wait 5`; undock/nav/dock at `CLOSING_RELAY`, including waits.
   Save/load the received signal; `intel import <signal file>` and `cat <signal file>`.
4. Undock/nav/dock at `CLOSING_WRECK`, restore `drone_bay`, deploy D1 and salvage
   data; `cat /remote/CLOSING_WRECK/logs/records/left_inventory.en.txt`.
   Repeat salvage and reading; save/load and continue with `wait 5`.

ES repeats the journey with `.es.txt`. Navigation waits use the engine's ETA;
position, systems, pools and RNG are never edited after bootstrap. Save/load
uses the production slot API, rather than the interactive dialog. The test
dispatches parser actions and public REPL handlers.

Reproduce from the repository root:

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/authored_closing_shift_integration.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
```

Results: both tests pass. C1 compares compilation and catalogue ordering for
seeds 1, 29 and 701; it plays the complete EN/ES journey with sandbox seed 16891.
It checks identities and relations, no disclosure through status/diag/contacts/map,
reservations before primary delivery, compiled EN/ES text, propagation and the
arrival boundary through pure queries, three channels, reading/import, valid
physical routes, two save/load cycles, and no duplicate deliveries/files.
Generated evidence: `/tmp/retorno-c1-evidence.json`. The temporal boundary is
queried separately; the journey receives an old emission that has already arrived.

Observed limits: secondaries do not wait for the primary; procedural uplink can
reveal Margen before the register; `uplink_only` delivers a route without a
narrative document. This does not prove an exclusive order, universal continuity
or playability from the damaged prologue. There was no technical blocker and no
need to modify production Python. Active catalogues, manuals and help remain
unchanged because production behavior does not change. Installation exists only
in a temporary copy preserving all five active singles and five active locations.
`log_copy.txt` had a pre-existing change and is excluded from delivery.
No staging, commit or push; awaiting external review.
