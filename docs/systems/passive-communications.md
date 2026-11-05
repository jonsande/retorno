# Passive communications — 4D-3e4b

[Español](passive-communications.es.md). Implementation for external review on
`78676dbfce5e7b98db36b2e241a427a19b0632fe`, 2026-11-06.
This does not implement F-DEAD-01 or general interstellar communications.

## System and service

`comms` — **Communications System / Sistema de comunicaciones** — is an ordinary
`ShipSystem` in existing room `BRG-01`. It starts installed, OFFLINE,
`forced_offline=True`, health 0.90. It needs powered
`energy_distribution >= NOMINAL`, independently of sensors and data systems.
Existing mechanisms control power, deterioration, repair and persistence.
Powering or repairing it does not automatically start its service.

Provisional nominal consumption: **0.15 kW**, compared with sensors' 0.7 kW.
Normal state multipliers apply: LIMITED 0.12, NOMINAL 0.15, UPGRADED 0.165 kW.
CRUISE retains this full load while powered. Other system loads are unchanged.
Priority 4; base deterioration `8.5e-11/s`, `k_power=0.30`, `k_rad=0.10`, reused
from data_core. Existing global wear factors apply; powering off does not stop
aging. These conservative parameters remain subject to balance review.

`radiod` — **Radio Communications Service / Servicio de comunicaciones por radio** —
is comms' `ServiceState`. Installed and stopped initially; a 5 s boot uses
`BOOT_SERVICE`. `requires_active_owner=True` requires at least LIMITED hardware.
Boot revalidates installation, owner, dependencies and power during execution
and when applying its outcome. Powering off the owner stops its service.
Cancellation and failure use existing finalizers; there is no second daemon
manager or automatic restart. Legacy sensord boot may still activate initially
OFFLINE sensors that were not forcibly powered off; radiod requires
`power on comms` first.

## Capacity and channels

`radio_block_reason` checks installed comms, no forced/shed power-off, LIMITED,
NOMINAL or UPGRADED state and consistent health; power dependencies; Core OS at
least LIMITED, available terminal, Q >= 0.55 and no brownout. It reuses the
engine's electrical kernels to compare current generation + available discharge
against load, including between ticks. Reception is suspended during transit
or hibernation. Installed, running radiod is required. No RNG or sensors/datad
consultation occurs.

| Channel | Effective contract |
| --- | --- |
| `captured_signal` | Radio and a local opportunity created by its real trigger. |
| `station_broadcast` | Radio, a local physical station/relay/waystation source and authorized context. |
| Internal `ship_os_mail` | Existing internal delivery without radio. External origin is not inferred from prose or sender names. |
| Explicit external mail | Piece `mail_origin: "external"`, or `external_origin=True` / SourceRef `kind="external"` in the local API, uses the same radio reception while retaining mail channel/envelope. No active pieces have these markers in this baseline. |
| `salvage_data` | Existing pool, drone and recovery; no radiod. |
| `uplink_trace` | Valid local uplink, installed/running data_core/datad; no radio. |
| `uplink_only` | Existing uplink requirements and LINK validation; no radio. |

Triggers, weights, rolls, force and deadlines are unchanged. Dock/uplink/salvage
action counters retain their contracts; automatic retries never increment them.
`signal_count` still counts effectively captured lore signals. Legacy hints
do not acquire a new increment that would change deadlines.

## Opportunity, capture and reading

One `WorldState.radio_opportunities` collection holds `RadioOpportunity` for
lore, local APIs and already prepared legacy stages. Lore identity is
`lore:<piece_key>`; gateway: `recovery:<generation>:gateway`; deadnode:
`deadnode:<target>:<attempt>`. The API accepts explicit IDs; its fallback derives
from channel, source, host and content without RNG.

EN/ES content, source, host, trigger, dock requirement, commit metadata and
preparation time are frozen. A legacy API supplying only one language retains that text
as fallback in either direction when switching EN/ES. Status, path, received language/time and read time
persist. States:

1. `pending`: no file, success event, intel, unlock or piece consumption.
2. `received`: an actual GUEST file and one SIGNAL_CAPTURED,
   BROADCAST_RECEIVED or MAIL_RECEIVED event. Only now are lore/pool delivery,
   applicable signal_count and producer flags/cooldowns committed.
3. `read_imported`: `cat`, `mail read` (delegates to cat) or `intel import`
   accessed the file. The existing parser applies valid intel; this status name
   does not guarantee useful intel or a primary unlock.

A file primary stays protected until valid reading/import. Pending diagnostics
show only counts and generic reasons, never content, secret sources, target IDs,
routes or coordinates. They do not import intel.

The shared writer preserves existing events/directories. Capture and bookkeeping
are one synchronous in-memory operation under the current execution model;
there is no deferred callback or intermediate save. Repeating a captured ID
does not write or emit again. Manually deleting a received file does not
recreate a consumed opportunity.

## Retries and coverage

Ticks retry pending entries after power, deterioration and engine consequences.
Producers may attempt immediate capture after preparation. Capacity and source
are always revalidated. The physical host must still exist and be the current
node, excluding transit waypoints. Lore opportunities originating from
dock/uplink/salvage retain docking at that host. Entering a nearby region or
starting radiod neither creates a lore trigger nor advances docking delivery.

An already prepared local opportunity remains available at the next receiver
availability in that same context; traveling suspends eligibility and returning
allows retry. This does not posit a new emitter or galactic propagation.
The current model has no independent emitter power evolution or electromagnetic
expiry: host existence/kind and local context are the available conservative
proof. Reduced range, latency, interference, intermittency and timed emission
windows remain design/balance work.

An existing legacy chain's gateway allows local arrival coverage without a new
dock. Generation, entry, gateway and primary protection are revalidated before
capture. Deadnode retries retain attempt and origin; cooldown is not consumed
until reception, and they do not publish routes directly.

## Pending structural recovery

Legacy global activation creates entry/gateway before preparing a hint. The
first indirect deadnode attempt also fabricates a bridge. As authorized for
this phase, these activations are explicitly deferred
(`recovery_activation_deferred`) without nodes, hints, success increments or
cooldown commits. Over-cap or protected-primary legacy LINKs are not transmitted.
Trackers may still observe thresholds without counting delivery. Stages with
existing bridges under cap and broadcasts from existing chains use the common
ledger. The selector, thresholds and cooldown lengths are unchanged; structural
integration remains e5. Deferral may leave a structural blockage without
automatic recovery until e5; this phase does not promise an exit in every map.

## Persistence and public operation

V2 container/schema 3 and e4 universe/catalog validation remain. WorldState
deserialization supplies added field defaults. Earlier schema-3 saves without
comms receive the same powered-off bootstrap system, without extra resources,
repairs, activation, historical geography or intel changes. ServiceState restores
the new flag as false for old services. Loading rewrites neither original nor
backup. There is no geography or content migration.

```text
diag comms
power on comms
boot radiod
jobs
diag comms
cat /logs/signals/<received_file>
power off comms
```

Repair energy_distribution first if power dependencies fail. Below LIMITED,
repair comms with an ordinary drone in BRG-01. `about comms` and `man boot`
explain operation. Activating hardware or restoring its useful threshold causes
the engine to inspect actual service ownership/dependencies and notify once of
stopped (`boot <id>`), uninstalled or blocked (`diag <owner>`) services, with
EN/ES names. There is no parallel daemon ownership list.

CLI and Textual share renderers, messages and diagnostics; the status adapter
adds identical lines without a new panel. Existing event types/audio are retained.

Code: [communications.py](../../src/retorno/core/communications.py),
[lore.py](../../src/retorno/core/lore.py), [engine.py](../../src/retorno/core/engine.py),
[model/world.py](../../src/retorno/model/world.py). Tests:
[passive_communications_smoke.py](../../tests/passive_communications_smoke.py),
[review report](../testing/passive-communications-review.md).
