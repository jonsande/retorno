# Arcs and corridor_01.json

This document explains how **arcs** work and how to add new content arcs to Retorno.

## What Is an Arc?

An **arc** is a small, data‑driven content package that can:
- place a **primary intel** item (usually a LINK to an authored location),
- place **secondary lore documents** (with or without LINKs),
- do so **procedurally and deterministically** per run (seeded by `rng_seed`).

Arcs are loaded from `retorno/data/arcs/*.json` and are used in two ways:
- **Procedural placement** when remote files are generated (e.g. data salvage on procedural nodes).
- **Scheduler delivery** via triggers like `uplink`, `dock`, or `salvage_data` (optional, per piece).

## Example: corridor_01.json

File: `retorno/data/arcs/corridor_01.json`

Key parts:
- `arc_id`: unique id for the arc.
- `primary_intel`: the key lore intel (here a LINK to ARCHIVE_01).
- `secondary_lore_docs`: 1–2 extra lore documents.
- `placement_rules`: where/how the primary and secondary docs may appear.

### primary_intel
```json
"primary_intel": {
  "id": "corridor_01_to_archive",
  "category": "lore_intel",
  "kind": "link",
  "line": "LINK: HARBOR_12 -> ARCHIVE_01",
  "preferred_sources": ["mail", "log"],
  "confidence": 0.70,
  "force": true,
  "force_policy": "deadline",
  "force_deadline": {"max_uplinks": 4},
  "allowed_channels": ["uplink_only", "station_broadcast", "salvage_data"],
  "constraints": {}
}
```
- `category`: currently `lore_intel` for authored/lore destinations.
- `kind`: type of intel (here `link`).
- `line`: the exact LINK line inserted into a file.
**Field details**
- `preferred_sources`: where the **procedural placement** prefers to embed the intel (`mail` or `log`). It only affects the procedural injection path (salvage on procedural nodes), not scheduler delivery.
- `confidence`: the IntelItem confidence recorded when the intel is applied (higher = more reliable).
- `force`: if `true`, the **scheduler** may force delivery attempts; `constraints` still apply.
- `force_policy`:
  - `none`: never force.
  - `soft`: increasing probability over time/events; not guaranteed.
  - `deadline`: guaranteed once the deadline is reached (or near it).
  - `hard`: deliver immediately when eligible.
- `force_deadline`: limits used by the `deadline` policy.
  - `max_uplinks`: maximum uplinks before delivery.
  - `max_events`: total scheduler-relevant events before delivery.
  - `max_docks`: dock operations before delivery.
  - `max_salvage_data`: salvage_data completions before delivery.
  - `max_year`: years since wake.
- `allowed_channels`: which **delivery channels** the scheduler may use. If a channel is not allowed, it won’t be used even when forced.
- `constraints`: filters that **must** pass for both scheduler delivery and procedural arc placement:
  - `min_year`, `max_year`
  - `min_dist_ly`, `max_dist_ly`
  - `regions_any`: list of allowed regions.

### secondary_lore_docs
Each entry describes a lore file that can be placed:
```json
{
  "id": "corridor_01_lore_01",
  "path_template": "/logs/records/corridor_note_01.{lang}.txt",
  "content_ref_en": "lore/packs/corridor_01/corridor_note_01.en.txt",
  "content_ref_es": "lore/packs/corridor_01/corridor_note_01.es.txt"
}
```
**Field details**
- `path_template`: where the file will appear (supports `{lang}`).
- `content_ref_*`: points to real text under `retorno/data/`.
- `force`, `force_policy`, `force_deadline`, `allowed_channels`, `constraints`: same as `primary_intel` (optional).

### placement_rules
```json
"placement_rules": {
  "primary": {
    "candidates": ["procedural_station", "procedural_relay", "procedural_derelict", "harbor_12"],
    "max_hops_from_start": 3,
    "require_kind_any": ["station", "relay", "derelict"],
    "avoid_node_ids": ["ARCHIVE_01"]
  },
  "secondary": {
    "candidates": ["procedural_station", "procedural_derelict"],
    "count": 2
  }
}
```
This controls **procedural placement** (not scheduler delivery):
- `primary.candidates`: node families allowed for placement.
  - `procedural_station`, `procedural_relay`, `procedural_derelict`, plus optional authored ids (e.g. `harbor_12`).
- `primary.max_hops_from_start`: max hop distance from start in the real graph (fallback to ly distance).
- `primary.require_kind_any`: restrict by node kind.
- `primary.avoid_node_ids`: hard block list.
- `secondary.candidates`: which procedural kinds can receive secondary docs.
- `secondary.count`: max number of secondary docs to place.

## How Arcs Are Applied

Implementation (summary):
- Arcs are loaded by `load_arcs()` in `retorno/src/retorno/runtime/data_loader.py`.
- **Procedural placement** happens during remote file generation:
  - `Engine._maybe_inject_arc_content(...)` in `retorno/src/retorno/core/engine.py`.
- **Scheduler delivery** happens on triggers:
  - `uplink`, `dock`, `salvage_data` call `maybe_deliver_lore(...)` in `retorno/src/retorno/core/lore.py`.
- Both paths are **seeded and deterministic** per run.
- Placement is **probabilistic** unless a piece uses `force` + policy.
- `primary_intel` targets are protected from generic procedural discovery paths (regular uplink routing, mobility failsafe, and corrupt-intel contact spawn) until the primary is unlocked through arc flow.

## Debugging Arc Placement

If DEBUG is on, use:
```
debug arcs
```
This prints:
- primary placement (if any),
- secondary docs placement,
- counters and mobility hints.

For scheduler delivery, use:
```
debug lore
```
This prints delivered items, counters, and forced pieces still pending.

## Delivery Channels (Scheduler)

`allowed_channels` controls *how* a forced/scheduled piece is delivered:
- `captured_signal`: writes a log under `/logs/signals/...` and emits a signal event.
- `station_broadcast`: writes a log under `/logs/broadcasts/...` (only on `dock` trigger).
- `salvage_data`: injects a file into the **remote** salvage mount (`/remote/<node>/...`).
- `ship_os_mail`: writes a mail into `/mail/inbox/...`.
- `uplink_only`: applies the intel directly (no file) on `uplink`.
- For `primary_intel`, these channels are also the intended unlock paths; generic procedural routing will not reveal the protected primary target before unlock.

If multiple channels are allowed, the scheduler chooses a preferred one based on the current trigger.

## Singles and Weights

Singles live in `retorno/data/lore/singles/index.json`.
- Each single has a `weight` and `channels`.
- Weights are **relative**, not absolute: a weight of `2.0` is twice as likely as `1.0` when a single is selected.
- Selection is still gated by:
  - trigger eligibility
  - constraints
  - a low base probability in the scheduler (see `retorno/src/retorno/core/lore.py`).
Note: the base probability is configurable via `Balance.LORE_SINGLES_BASE_P` in `retorno/src/retorno/config/balance.py`.

## Adding a New Arc (Checklist)

1. Create an arc definition:
   - `retorno/data/arcs/my_arc.json`
2. Add lore text files:
   - `retorno/data/lore/packs/my_arc/...`
3. Reference those files via `content_ref_*`.
4. Define placement rules.
5. Test by salvaging data from procedural nodes.
6. Use `debug arcs` to verify placement.

## Notes and Best Practices

- Use `preferred_sources` = `["mail","log"]` to vary presentation.
- Keep `primary_intel` as `lore_intel` (no failsafe).
- Avoid placing primary intel on the destination node itself.
- Keep docs small and readable; long texts should use `content_ref`.
- Only set `force=true` when you really want a guaranteed delivery.
- `force` never bypasses `constraints`. If constraints fail, delivery is blocked even with `force=true`.
- With `force=false`, the piece can still appear via non-forced arc paths, but it will not be guaranteed by the scheduler.

- Primary intel that isn’t LINK? With the current logic, the most reliable option is for the primary intel to be a LINK pointing to a node_id that exists in world.space.nodes. It is “the most reliable” in the sense that there is not yet a system in place that guarantees the generation of route information to known destinations (but without a route), although it is true that a route can always be built using the "route" command by moving close enough to the target (e.g. within the sensors’ radius), provided that the target’s coordinates are available. In any case, the necessary logic will soon be implemented so that the information required to find routes to “dangling” or “dead” nodes is generated and placed procedurally. Therefore, "NODE:", "SECTOR:", "COORD:", and the more flexible format "[INTEL]...[/INTEL]" can also be used as primary intel (this format can be used to reveal authored contacts by id/name/sector, with an interesting peculiarity: if the id/name/sector-coordinates entered between the "[INTEL]...[/INTEL]" tags do not match the expected format, it will be treated as corrupted intel, and there is a chance that it will procedurally generate a new location).

- Can primary_intel be forced to be a route (link) to a location (or simply a location) that is not authored but procedurally generated? Creating a procedural location (or referring to an already existing procedural location) from an arc is not currently supported, at least not directly. The closest thing would be to use corrupted intel (which can spawn a procedural hub), but that is random. In any case, the necessary logic to make this possible in the future is planned for implementation.
