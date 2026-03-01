# Arcos y corridor_01.json

Este documento explica cómo funcionan los **arcos** y cómo añadir nuevos arcos de contenido a Retorno.

## ¿Qué es un arco?

Un **arco** es un paquete de contenido data‑driven que puede:
- colocar un **intel primario** (normalmente un LINK hacia una localización authored),
- colocar **documentos de lore secundarios** (con o sin LINKs incrustados),
- hacerlo de forma **procedural y determinista** por run (semilla `rng_seed`).

Los arcos se cargan desde `retorno/data/arcs/*.json` y se aplican de dos formas:
- **Colocación procedural** cuando se generan archivos remotos (p. ej. al salvager datos en nodos procedurales).
- **Entrega por scheduler** vía triggers como `uplink`, `dock` o `salvage_data` (opcional, por pieza).

## Ejemplo: corridor_01.json

Archivo: `retorno/data/arcs/corridor_01.json`

Partes clave:
- `arc_id`: id único del arco.
- `primary_intel`: el intel de lore principal (aquí, un LINK a la localización "de autor" ARCHIVE_01).
- `secondary_lore_docs`: 1–2 documentos de lore secundarios.
- `placement_rules`: dónde/cómo pueden aparecer el primary y los secundarios.

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
- `category`: actualmente `lore_intel` para destinos authored/lore.
- `kind`: tipo de intel (aquí `link`).
- `line`: línea LINK exacta que se inserta en el archivo.
**Detalles de campos**
- `preferred_sources`: dónde prefiere incrustarse el intel en la **colocación procedural** (`mail` o `log`). No afecta al scheduler.
- `confidence`: confianza usada al registrar IntelItem (más alto = más fiable).
- `force`: si es `true`, el **scheduler** puede forzar intentos de entrega; las `constraints` siguen aplicando.
- `force_policy`:
  - `none`: no forzar nunca.
  - `soft`: probabilidad creciente con el tiempo/eventos; no garantiza.
  - `deadline`: garantiza al superar (o acercarse a) el deadline.
  - `hard`: entrega inmediata si es elegible.
- `force_deadline`: límites usados por `deadline`.
  - `max_uplinks`, `max_events`, `max_docks`, `max_salvage_data`, `max_year`.
- `allowed_channels`: canales de entrega que el scheduler puede usar.
- `constraints`: filtros que **deben** cumplirse tanto en entrega por scheduler como en colocación procedural del arco:
  - `min_year`, `max_year`
  - `min_dist_ly`, `max_dist_ly`
  - `regions_any`

### secondary_lore_docs
Cada entrada describe un archivo de lore que puede colocarse:
```json
{
  "id": "corridor_01_lore_01",
  "path_template": "/logs/records/corridor_note_01.{lang}.txt",
  "content_ref_en": "lore/packs/corridor_01/corridor_note_01.en.txt",
  "content_ref_es": "lore/packs/corridor_01/corridor_note_01.es.txt"
}
```
**Detalles de campos**
- `path_template`: ruta donde aparecerá el archivo (soporta `{lang}`).
- `content_ref_*`: apunta al texto real dentro de `retorno/data/`.
- `force`, `force_policy`, `force_deadline`, `allowed_channels`, `constraints`: igual que en `primary_intel` (opcional).

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
Controla la **colocación procedural** (no el scheduler):
- `primary.candidates`: familias de nodos permitidas.
  - `procedural_station`, `procedural_relay`, `procedural_derelict`, y opcionalmente ids authored (p. ej. `harbor_12`).
- `primary.max_hops_from_start`: límite de saltos desde el inicio en el grafo real (fallback: distancia ly).
- `primary.require_kind_any`: restringe por kind.
- `primary.avoid_node_ids`: lista de bloqueo.
- `secondary.candidates`: qué kinds procedurales pueden recibir docs secundarios.
- `secondary.count`: máximo de docs secundarios a colocar.

## Cómo se aplican los arcos

Resumen de implementación:
- Los arcos se cargan con `load_arcs()` en `retorno/src/retorno/runtime/data_loader.py`.
- La **colocación procedural** ocurre al generar archivos remotos:
  - `Engine._maybe_inject_arc_content(...)` en `retorno/src/retorno/core/engine.py`.
- La **entrega por scheduler** ocurre con triggers:
  - `uplink`, `dock`, `salvage_data` llaman a `maybe_deliver_lore(...)` en `retorno/src/retorno/core/lore.py`.
- Ambas rutas son **deterministas** por run.
- La colocación es **probabilística** salvo que una pieza use `force` + policy.
- Los destinos protegidos por `primary_intel` no se pueden descubrir por vías procedurales generales (uplink normal, mobility failsafe y spawn de contactos por intel corrupta) hasta que el primary se desbloquee por la ruta del arco.

## Depuración de colocación

Con DEBUG activado:
```
debug arcs
```
Muestra:
- colocación del primary (si existe),
- colocación de docs secundarios,
- contadores y pistas de movilidad.

Para la entrega por scheduler:
```
debug lore
```
Muestra entregados, contadores y piezas forzadas pendientes.

## Canales de entrega (scheduler)

`allowed_channels` controla *cómo* se entrega una pieza:
- `captured_signal`: escribe un log en `/logs/signals/...` y emite evento de señal.
- `station_broadcast`: escribe un log en `/logs/broadcasts/...` (solo con trigger `dock`).
- `salvage_data`: inyecta un archivo en el montaje remoto (`/remote/<node>/...`).
- `ship_os_mail`: escribe un mail en `/mail/inbox/...`.
- `uplink_only`: aplica el intel directamente (sin archivo) en `uplink`.
- Para `primary_intel`, estos canales son también las vías previstas de desbloqueo; el enrutado procedural general no revela el objetivo protegido antes del desbloqueo.

Si hay varios canales permitidos, el scheduler escoge uno preferente según el trigger actual.

## Singles y pesos

Los singles viven en `retorno/data/lore/singles/index.json`.
- Cada single tiene un `weight` y `channels`.
- Los pesos son **relativos**, no absolutos: un peso `2.0` es el doble de probable que `1.0` cuando se elige un single.
- La selección sigue condicionada por:
  - trigger
  - constraints
  - una probabilidad base baja en el scheduler (ver `retorno/src/retorno/core/lore.py`).

Nota: la probabilidad base se puede ajustar con `Balance.LORE_SINGLES_BASE_P` en `retorno/src/retorno/config/balance.py`.

## Añadir un arco nuevo (checklist)

1. Crear la definición:
   - `retorno/data/arcs/mi_arco.json`
2. Añadir los textos:
   - `retorno/data/lore/packs/mi_arco/...`
3. Referenciar esos archivos con `content_ref_*`.
4. Definir `placement_rules`.
5. Probar con salvage de datos en nodos procedurales.
6. Usar `debug arcs` para verificar.

## Notas y buenas prácticas

- Usa `preferred_sources = ["mail","log"]` para variar la presentación.
- Mantén el `primary_intel` como `lore_intel` (sin failsafe).
- Evita colocar intel primario en el nodo destino.
- Para textos largos, usa `content_ref`.
- Usa `force=true` solo cuando sea necesario garantizar una entrega.
- `force` no salta nunca las `constraints`: si no se cumplen, la entrega se bloquea aunque `force=true`.
- Con `force=false`, la pieza puede seguir aparecer por rutas no forzadas del arco, pero el scheduler no la garantiza.

- ¿Primary intel que no sea LINK? Con la lógica actual lo más fiable es que el primary sea LINK hacia un node_id que exista en world.space.nodes. Es "lo más fiable" en el sentido de que no hay aún implementado un sistema que garantice la generación de información rutas a destinos conocidos (pero sin ruta), aunque es cierto que siempre se puede construir una ruta mediante el comando "route", colocándose lo bastante cerca del objetivo (e. e. a la distancia del radio de los sensores), si es que se disponen las coordenadas del objetivo. En cualquier caso, en breve se implementará la lógica necesaria para que se genere y coloque proceduralmente la información necesaria para hallar rutas a los nodos "colgados" o "muertos". Así pués, como primary intel también se pueden usar "NODE:", "SECTOR:", "COORD:" y el formato, más flexible "[INTEL]...[/INTEL]" (que sirve para revelar contactos authored por id/nombre/sector, con una peculiaridad interesante: si el id/name/sector-coords introducidas entre las etiquetas "[INTEL]...[/INTEL]" no cumple el formato, se considerará información corrupta, y hay una probabilidad de que genere proceduralmente una nueva localización).

- ¿Se puede forzar que primary_intel sea una ruta (link) a una localización (o localización a secas) no "de autor" (authored) sino proceduralmente generada? Crear una localización procedural (ni referira una localización procedural ya existente) desde un arc no está soportado actualmente, no directamente. Lo más cercano sería: usar intel corrupta (que puede spawnear un hub procedural), pero eso es aleatorio. En cualquier cosa, está programado implementar la lógica necesaria para que esto se pueda hacer en un futuro.
