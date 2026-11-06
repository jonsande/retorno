> **B1 compatibility.** The B0 physical matrix and completion semantics below remain. New games prepare [historical-information-v1](historical-information.md) archives, retaining raw inaccessible waystation files without a salvage frontier. Legitimate pending pushes remain independent of exhausted uplink.

# Physical information capabilities — 4D-3e5c-B0

[Español](information-capabilities.es.md). Implemented on 2026-11-06, based on
`80f68320ba236cdc32e73774c551b270fd8d4b9f`.

## Authority and scope

`src/retorno/model/world.py:information_capabilities` owns the physical
information-interface criterion. It describes potential interactions; ship
readiness, docking, drone location, available payload and knowledge remain
separate gates. The planner preserves its existing `Mechanism` enum API by
adapting this criterion.

| Physical kind | `drone salvage data` | `uplink` |
| --- | --- | --- |
| `station` | Yes | Yes |
| `relay` | Yes | Yes |
| `ship` | Yes | No |
| `derelict` | Yes | No |
| `waystation` | No | Yes |
| `origin`, `unknown`, `nav_point`, `transit`, other kinds | No | No |

These are the preexisting action capabilities. B0 grants no new interface and
changes no readiness gates. Resource recovery is independent of this table.

## Prepared archives and effective opportunities

Pool initialization keeps its ordering and raw `base_files`/`injected_files`.
The procedural archive producer, random draws and uplink selection policy are
unchanged. Raw historical or assigned files can remain internally for
compatibility even when their host has no public salvage interface.

`core/lore.py:collect_node_salvage_data_files` returns files only for a physical
salvage-capable host. `_pending_node_files_count` applies the same criterion
before mount projection. Survey counts and signatures therefore describe
recoverable salvage data; a waystation still reports its measured uplink
infrastructure. Archives are never deleted or marked delivered by this filter.

Completion retains the existing persisted fields:

- `scrap_complete`: no physical scrap remains.
- `extras_complete`: no recoverable modules or drones remain.
- `data_complete`: no new mountable salvage paths for an available physical
  interface, no undelivered pending push, and either no uplink interface or an
  already consumed uplink route pool.
- `node_cleaned`: all three completion flags are true.

An uplink-capable host remains pending until its uplink is consumed. Pending
pushes remain independent and can keep data pending after that consumption.
Temporary ship faults do not erase potential or complete a host. An exhausted
uplink keeps the existing retry semantics for pending narrative delivery.
Already mounted/read information and legitimate onboard intel remain usable.

## Frontier, deadnodes and recovery

`core/exploration_recovery.py` filters both initialized file pools and the
uninitialized archive fallback. A waystation archive cannot impersonate a
salvage frontier. Legitimate uplink payload, pending pushes, known routes and
acquired intel retain their existing frontier semantics. Queries remain pure.

`core/deadnodes.py` already excludes `node_cleaned` pools; it now receives the
correct derived result through normal completion recomputation and save load.
No thresholds, timers or bridge policies change. Structural recovery uses the
shared criterion for its existing source check and cannot certify an
unrecoverable waystation archive as salvage evidence. Global recovery can
request historical selection once the false frontier disappears. This does
not guarantee a source or an exit; the installed catalogue can yield a
conditional result. See [structural recovery](structural-recovery.md).

## Persistence and knowledge

Schema 3 is retained. After existing validations, load refreshes derived flags
for physical hosts without salvage capability, including pre-B0 stale caches.
It preserves raw archives, mounted files, consumption/delivery markers,
resources, physical routes and the original save bytes on disk. A subsequent
save writes the refreshed cache normally. Salvage-capable hosts keep their
existing load behavior.

No internal archive or scheduler information becomes public. CLI and Textual
use the same measured survey event and localized renderers. `status`, `diag`
and other public queries neither reveal prepared archives nor mutate state.
This preserves `C-DATA-004`.

## Validation and limits

`tests/information_capabilities_smoke.py` covers a real seed-0 procedural
waystation, public salvage rejection/uplink/survey actions, all four salvage
host kinds, completion, preserved files and pushes, deadnodes/global and
structural recovery, old/current schema-3 saves, and EN/ES CLI/Textual negative
disclosure comparisons while hidden archives vary. Reference/B0 deterministic
samples and a public-command prologue walkthrough accompany the external
review report.

B0 does not implement `historical-information-v1` or change historical
generation, physical topology, radio, scheduler assignment policies, authored
story content, resource balance, navigation, ship systems or audio. Internal
archives without an interface remain inert; their future use requires a
separate design decision.
