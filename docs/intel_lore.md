# How Intel and Lore Are Acquired

This document summarizes the current ways players can obtain **intel** (navigation knowledge) and **lore** (narrative text) in Retorno.

## Intel Sources

1) **scan**
- Detects contacts within sensor range.
- Records intel of type `node`.
- May fix **fine range** (km/mi) for nearby local contacts, but **does not add routes**.

2) **uplink** (relay/waystation/station, docked, data_core+datad)
- Adds new routes (`link`) from the current node.
- Records intel of type `link`.
- Writes a log under `/logs/nav/uplink_...`.
 - May trigger **lore delivery** via the scheduler (see Lore Sources).

3) **route <node_id>**
- Solves a route (job) within sensor range.
- On completion, adds `link` and records intel.

4) **cat <path> / intel import <path>**
- Auto‑imports intel from lines:
  - `LINK:`, `NODE:`, `SECTOR:`, `COORD:`
- Supports `[INTEL] ... [/INTEL]` blocks:
  - If it contains a `LINK`, adds route.
  - If it contains a node_id, name, or sector id, adds that authored node as a known contact.
  - Corrupt intel may fail or spawn a new procedural hub contact.

5) **salvage data** (`drone salvage data`)
- Mounts remote files at `/remote/<node>/...`.
- Reading those files via `cat` auto‑imports intel.
 - May trigger **lore delivery** via the scheduler.

## Lore Sources

1) **salvage data**
- Remote mails/logs can include narrative content.
- Access via `/remote/<node>/...` and `cat`.

2) **local filesystem**
- Initial mails/logs in `/mail` or `/logs` are lore by default.

3) **arcs (procedural placement + scheduler)**
- Arcs can place secondary lore documents on procedural nodes during salvage.
- Arcs can also deliver pieces via **scheduler** on triggers (`uplink`, `dock`, `salvage_data`).
- Delivery can be forced per piece with `force` + `force_policy`.
- See `retorno_docs/arcs.md`.

4) **scheduler channels**
- `ship_os_mail`: inserts a local mail in `/mail/inbox/...`.
- `captured_signal`: inserts a log in `/logs/signals/...`.
- `station_broadcast`: inserts a log in `/logs/broadcasts/...` when docking.
- `uplink_only`: delivers the intel directly (no file).

5) **singles (weighted lore)**
- Optional single‑file lore items from `retorno/data/lore/singles/index.json`.
- Delivered occasionally by the scheduler based on weights.

## How Weights Work (Singles)

Singles use **relative weights**:
- A weight of `2.0` is twice as likely as `1.0` **when a single is chosen**.
- Before weights apply, the scheduler does a **base probability** check:
  - Controlled by `Balance.LORE_SINGLES_BASE_P` in `retorno/src/retorno/config/balance.py`.
  - If this check fails, **no single is delivered** for that trigger.
- Constraints (`min_year`, `max_dist_ly`, `regions_any`, etc.) still must pass.
