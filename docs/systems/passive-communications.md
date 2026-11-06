# Passive communications — 4D-3e5b

[Español](passive-communications.es.md). Current contract for external review.
Physics/data: [spatial and temporal radio](radio-spacetime.md).
e4b history: [previous report](../testing/passive-communications-review.md).

## Hardware and operation

`comms` (Communications System) is a ShipSystem in BRG-01. Initially installed,
powered off, forced_offline=True, health 0.72, with no electrical load. Initial
health supports LIMITED; below 0.60 repair is needed before activation. It needs
energy_distribution >= NOMINAL and effective supply. `power on comms` does not
start `radiod` (Radio Communications Service): `boot radiod` is an ordinary
5-second job. Powering off stops the service. Repair, wear, notices and
dependencies retain their behavior.

Provisional nominal consumption is 0.15 kW: LIMITED 0.12, NOMINAL 0.15, UPGRADED
0.165 kW; full load in CRUISE. Priority 4, base wear 8.5e-11/s, k_power=0.30,
k_rad=0.10 and existing global factors remain. Greater reception distance adds
no consumption. Transmitter energy/repair is not simulated.

`radio_block_reason` requires coherent health and LIMITED/NOMINAL/UPGRADED state,
dependencies, Core OS at least LIMITED, available terminal, Q >= 0.55, no brownout,
enough generation + discharge and installed/running radiod. It reuses engine
electrical kernels. Transit/hibernation suspend reception. Sensors/sensord and
data_core/datad are not radio requirements.

## Sources, preparation, capture and reading

`radio_spatial_block_reason` shares coverage across selection and capture.
Declarations use 3D distance, power and sensitivity; capture adds the window
propagated at c through `radio_temporal_block_reason`. Preparation is not emission.
Without new metadata, legacy compatibility stays at the current physical host,
admissible kind and required docking. Local messages gain neither arbitrary
interstellar range nor an invented historical delay.
This compatibility cannot authorize new F-DEAD-01 emissions: every radio stage
needs a declared emission, including local stages.

| Channel | Contract |
| --- | --- |
| captured_signal | Radio; physical declaration or original trigger's local compatibility. |
| station_broadcast | Radio from station/relay/waystation; not every station transmits. |
| Internal ship_os_mail | Internal delivery independent of radio. |
| Explicit external mail | mail_origin: external, external_origin=True or external SourceRef uses radio and retains the mail envelope. |
| salvage_data | Pool/drone recovery, without radio. |
| uplink_trace / uplink_only | Existing local data_core/datad gates; without radio. |

Only `WorldState.radio_opportunities` and `RadioOpportunity` are used. Legacy
identities remain; declarations use radio:<emission_id>, lore uses lore:<piece_key>.
EN/ES content, source/host, trigger, docking, producer metadata and preparation
freeze; new data also freezes transmitter/emission. Range does not freeze:
capture revalidates position, sensitivity and time.

1. pending: no file, reception event, intel, unlock or narrative consumption.
2. received: one real GUEST file and SIGNAL_CAPTURED/BROADCAST_RECEIVED/MAIL_RECEIVED;
   only then are corresponding pools, lore, counters and cooldowns committed.
3. read_imported: cat, mail read or intel import accessed the file. The existing
   parser applies valid intel; this status does not guarantee an unlock.

IDs capture once across save/load. Deleting a file does not recreate it. Producers
may capture after preparation. End-of-tick retries, after energy/wear/consequences,
listen for declared independent emissions and retry pending opportunities without
scan. piece_key references never prepare through proximity: scheduler, weights,
windows and dock/uplink/salvage triggers plus docking context remain. Single
probabilities, deadlines and signal_count meaning do not change.

F-DEAD-01 shares these boundaries: remote first reception needs a pre-existing
certified notice, sufficient signal and actual arrival. Historical activity and
transmitters are not invented. Widening search, protection, attempts, cooldowns
and progression remain; see its [contract](structural-recovery.md).

## Persistence, knowledge and commands

V2/schema 3 envelope, checksum and backups remain. Older slots default to local
semantics. Catalogue/snapshot, radio configuration, hosts, index, ledger and plans
are validated. Incompatible files fail without deletion/rewriting. Radio changes
the content hash without changing physical manifest identity.

status/diag comms show only receiver, health, power, service and known operational
capability, never hidden signal counts/names/distances/windows. ready promises no
emission. debug on enables debug radio with internal parameters/reasons; debug
recovery reads stored searches/plans. Queries are pure: no generation, RNG,
time advance, capture or import. CLI/Textual share renderers; event/audio types remain.

```text
diag comms
power on comms
boot radiod
jobs
cat /logs/signals/<received_file>
power off comms
```

Distant signals may be travelling or already past. Silence proves no absence.
Repair in BRG-01 and stable supply permit new captures when emission mode still
allows them. Reception implies no living interlocutor. Tests:
passive_communications_smoke (18), knowledge_boundary_smoke (19),
radio_spacetime_smoke and the [phase report](../testing/radio-spacetime-review.md).
