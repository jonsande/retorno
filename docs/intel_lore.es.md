# Cómo se obtiene intel y lore

Este documento resume las formas actuales de obtener **intel** (conocimiento de navegación) y **lore** (contenido narrativo) en Retorno.

## Fuentes de intel

1) **scan**
- Detecta contactos dentro del rango de sensores.
- Registra intel de tipo `node`.
- Puede fijar **distancia fina** (km/mi) en contactos locales, pero **no añade rutas**.

2) **uplink** (relay/waystation/estación, docked, data_core+datad)
- Añade rutas nuevas (`link`) desde el nodo actual.
- Registra intel de tipo `link`.
- Escribe un registro en `/logs/nav/uplink_...`.
 - Puede disparar **entrega de lore** vía scheduler (ver Fuentes de lore).

3) **route <node_id>**
- Resuelve una ruta (job) dentro del rango de sensores.
- Al completarse, añade `link` y registra intel.

4) **cat <path> / intel import <path>**
- Auto‑importa intel desde líneas:
  - `LINK:`, `NODE:`, `SECTOR:`, `COORD:`
- Soporta bloques `[INTEL] ... [/INTEL]`:
  - Si contiene un `LINK`, añade la ruta.
  - Si contiene un node_id, name o id de sector, añade ese nodo authored como contacto conocido.
  - La intel corrupta puede fallar o generar un nuevo hub procedural.

5) **salvage data** (`drone salvage data`)
- Monta archivos remotos en `/remote/<node>/...`.
- Leerlos con `cat` auto‑importa intel.
 - Puede disparar **entrega de lore** vía scheduler.

## Fuentes de lore

1) **salvage data**
- Mails/logs remotos pueden incluir narrativa.
- Se accede vía `/remote/<node>/...` y `cat`.

2) **filesystem local**
- Mails/logs iniciales en `/mail` o `/logs`.

3) **arcos (colocación procedural + scheduler)**
- Los arcos pueden colocar documentos secundarios en nodos procedurales al salvager datos.
- Los arcos también pueden entregarse vía **scheduler** en triggers (`uplink`, `dock`, `salvage_data`).
- La entrega puede forzarse por pieza con `force` + `force_policy`.
- Ver `retorno_docs/arcs.es.md`.

4) **canales del scheduler**
- `ship_os_mail`: inserta un mail local en `/mail/inbox/...`.
- `captured_signal`: inserta un log en `/logs/signals/...`.
- `station_broadcast`: inserta un log en `/logs/broadcasts/...` al dockear.
- `uplink_only`: entrega el intel directamente (sin archivo).

5) **singles (lore ponderado)**
- Lore de una sola pieza desde `retorno/data/lore/singles/index.json`.
- Se entrega ocasionalmente según pesos.

## Cómo funcionan los pesos (singles)

Los singles usan **pesos relativos**:
- Un peso `2.0` es el doble de probable que `1.0` **cuando se elige un single**.
- Antes de aplicar pesos, el scheduler hace una **probabilidad base**:
  - Configurable con `Balance.LORE_SINGLES_BASE_P` en `retorno/src/retorno/config/balance.py`.
  - Si falla ese chequeo, **no se entrega ningún single** en ese trigger.
- Las constraints (`min_year`, `max_dist_ly`, `regions_any`, etc.) deben cumplirse igualmente.
