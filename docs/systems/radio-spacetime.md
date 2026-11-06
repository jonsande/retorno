# Spatial and temporal radio — 4D-3e5b

[Español](radio-spacetime.es.md). Implemented for external review. Authorities:
`src/retorno/core/communications.py`, `model/world.py`, `worldgen/radio.py`,
`worldgen/narrative.py`, `config/balance.py`. Tests and isolated scene:
`tests/radio_spacetime_smoke.py`, `tests/fixtures/radio_world/`.

## Physics and provisional balance

The receiver uses `world.current_pos_ly`. `RadioEmitter` hosts resolve through
the historical manifest, including lazy sites. Materialized nodes must match
their certificates. Emitters do not redefine coordinates.

```text
d = Euclidean 3D distance in light years
I = P / max(d, 10^-9 ly)^2
S = normalized inverse detection threshold
R = sqrt(P × S) ly; decodable if S > 0 and d <= R
delay = d × Balance.YEAR_S
```

P is equivalent isotropic power normalized at 1 ly; I and S are abstract budgets,
not calibrated W/dBm. The near-zero clamp limits I; the inclusive boundary uses R.
No RNG, sensors, routes or `MAX_ROUTE_HOP_LY` participate. Booleans, nonfinite
values and P outside 10^-8..10^4 fail.

| Profile | P | LIMITED R | NOMINAL R | UPGRADED R |
| --- | ---: | ---: | ---: | ---: |
| `emergency` | 0.25 | 0.25 ly | 0.5 ly | 0.75 ly |
| `station` | 36 | 3 ly | 6 ly | 9 ly |
| `interstellar_relay` | 400 | 10 ly | 20 ly | 30 ly |

Sensitivities: LIMITED 0.25, NOMINAL 1, UPGRADED 2.25. OFFLINE, CRITICAL and
DAMAGED cannot decode. These are configurable provisional values, not canon
or calibrated technology. Valid explicit P adjusts the profile. Being a station,
wreck or relay implies neither transmitter nor activity. Narrative needs do not
repair installations.

## Time

`radio_coordinate_time` provisionally adapts `clock.t` to galactic seconds since
game start. `Balance.YEAR_S` is 365 days. Persisted reference is
`game-coordinate-seconds-v1`; negative offsets precede t=0 without absolute dates.
Source/receiver are approximated as stationary at each check. The receiver window
is `[start_t + delay, end_t + delay)`, open-ended without an end. `continuous`
represents repetition with optional end; `finite` requires end after start and
represents a pulse with duration/finite window. Both offsets must be finite and
within ±10 million game years.

Preparation, emission, arrival, capture and reading are separate facts. A new
emission at 5 ly waits five years; a copy declared since -10 years may be available
at t=0. It may have ended at its host while still arriving. Reception establishes
neither survivors nor simultaneous activity. No wave cache exists. Ticks check
their final state: continuous signals survive jumps over arrival; expired finite
windows are not captured retrospectively. Transit/hibernation block capture;
arrival/wake permit the next check. Trajectory listening is not reconstructed.
Three clocks and relativity are not implemented; travel, hibernation, ageing,
energy, wear and deadlines remain unchanged.

## Optional versioned data

Traditional installed locations, arcs and singles accept this root block.
Hosts may come from `world_requirements` or exact procedural IDs certified for
the game; authored hosts resolve name/ID/alias.

```json
{"radio_emitters":{"version":"radio-emitters-v1","emitters":[{
  "id":"archive-radio","host":"HARBOR_12","category":"station",
  "emissions":[{"id":"archive-copy","mode":"continuous","start_t":-630720000,
    "content_by_locale":{"en":"Automated archive copy.","es":"Copia automática de archivo."}}]
}]}}
```

`power` is optional; `emissions: []` describes inactive equipment. Each emission
requires exactly one payload source:

- `content_by_locale`: nonempty inline EN/ES text without unresolved bindings.
- `piece_key`: installed `single:<id>` or `arc:<id>:<piece>`. The piece references
  it with `radio_emission: "<id>"` and authorizes exactly its channel; mail needs
  `mail_origin: "external"`. Host/channel are pinned, existing policies retained.
- `navigation_link_to`: certified target ID/alias for a pre-existing LINK;
  builds the shared EN/ES notice. Distinct endpoints and navigation cap are
  required, without implying a historical edge or known route.

```json
{"id":"dated-pulse","mode":"finite","start_t":0,"end_t":60,
 "content_by_locale":{"en":"Recorded packet.","es":"Paquete registrado."}}
```

Default channel is `captured_signal`; `station_broadcast` and external mail are
supported. Broadcast hosts require station/relay/waystation. Maximum 128 emissions
per transmitter. Unique stable IDs; unknown fields, types, versions, windows,
missing/ambiguous references and contradictions fail with file/entity/field context.
This is a minimal optional extension; definitive editorial guides remain e5c.

## Listening, ledger and recovery

The snapshot holds declarations and a derived power-tier index. Each emitter
occupies one cell with power-of-two side >= UPGRADED radius. Queries visit at most
27 cells per occupied tier, return 128 candidates per tick and continue through
persisted cursor/anchor. `complete=False` means incomplete, never absence. No
galaxy walk, materialization or mutable global cache is used.

With operational gates open, `retry_radio_opportunities` discovers available
independent emissions, prepares and captures without `scan`. It excludes
`piece_key`: only scheduler and real triggers prepare those documents, retaining
docking. The existing pool initializer may materialize in a normal tick; radio
adds no materialization. Only `WorldState.radio_opportunities` is used.
Emitter/emission/content/preparation freeze, range/sensitivity do not. Capture
revalidates position, health, state, supply, Q/brownout, dependencies, Core OS,
radiod and context. Electrical consumption is unchanged. Unique identity is
`radio:<emission_id>` or `lore:<piece_key>`; another ID for that emission fails.
Capture creates file/event; later reading/import applies intel without duplication.

Every new F-DEAD-01 plan, local or remote, requires `navigation_link_to` declared before blockage, a
certified/reachable host, coverage and arrival. It is conservatively restricted
to open-ended continuous repetition for later repair/power activation. No LINK
or historical activity is invented. It uses current useful sensitivity or NOMINAL
reference for unavailable equipment, without resource filters. Future/out-of-range
signals cannot confirm plans; receiver off may leave `receipt_pending`. Attempts
and cooldown advance only on capture. The stage reuses `radio:<id>`, optionally
binding a pending opportunity; received emissions cannot duplicate. ID, original
sensitivity/context and preparation time persist. Saving validates that evidence;
capture uses current state. Each radio stage stores its own emission and content
fingerprint in `stage_sources`; confirmation/capture revalidate that it authorizes
exactly that LINK. A station without equipment, inactive equipment or unrelated
emission is insufficient. Later stages need declared emissions, already known
routes or existing recoverable files containing the clue. Confirmation never
injects an archive or replaces its payload with a calculated LINK.

New plans use `historical-recovery-v2`. Local compatibility preserves only already
persisted v1 opportunities and authorized legacy narrative interactions. A v1 plan
can consume its saved opportunity, but cannot now create unprepared radio stages.
New plans cannot invoke that fallback. Missing sources leave a conditional result
without attempts/cooldown. No procedural transmission catalogue is added to fill
the gap; that possible dependency remains a design/editorial question for e5c.

A legitimately invalidated continuation persists inactive with its contract and
progress checked; it does not require an opportunity that could never be prepared.
Earlier receipts remain required and cannot duplicate. A later v2 stage's emission
received passively before activation is reused under its canonical ID, without
another capture; reading/import is still required. Integrity and compatibility
details are in [structural recovery](structural-recovery.md).

## Compatibility and information

Older schema 3 saves default to local metadata without retroactive interstellar
transmitters. V2 envelope, checksum and backups remain. Save/load validates
declarations, index, ledger and plans; catalogue/radio physical configuration
changes fail without rewriting files. Full content hash includes radio;
`physical_catalog_key` excludes only this extension, preserving manifest,
IDs, stations and routes when only radio metadata changes.

`status`/`diag comms` depend only on the receiver. `debug radio` exposes calculations,
delays, windows and reasons without mutation; `debug recovery` shows the plan's
first emission. CLI/Textual share C-DATA-004. Active transmissions, dynamic
repeaters, interference, moving emitters, new sensors and AMANECER remain outside scope.
