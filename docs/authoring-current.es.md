# RETORNO — Guía vigente de autoría de arcos, singles y localizaciones

**Preparación de 4D-3e5c-C · 2026-11-07 · Estado: guía de trabajo contrastada con los contratos publicados; la primera historia authored completa aún no está validada.**
[English](authoring-current.md)

Esta guía sustituye como referencia práctica a los ejemplos históricos de `docs/arcs.es.md` y a las guías antiguas de creación de arcos y singles. No sustituye el código ni los contratos técnicos: [`narrative-world-contract.es.md`](narrative-world-contract.es.md), [`systems/lore-scheduler.es.md`](systems/lore-scheduler.es.md), [`systems/historical-information.es.md`](systems/historical-information.es.md) y [`systems/radio-spacetime.es.md`](systems/radio-spacetime.es.md). Si difieren, verificar el comportamiento productivo antes de autorizar nuevo contenido.

## 1. Qué se carga realmente

| Recurso | Ruta activa | Regla |
| --- | --- | --- |
| Localizaciones authored | `data/locations/*.json` | Lectura directa, no recursiva. Actualmente cinco activas. |
| Arcos | `data/arcs/*.json` | Lectura directa, no recursiva. Actualmente **cero** activos. |
| Singles | `data/lore/singles/index.json` | Solo las entradas del índice. Actualmente cinco activas. |
| Textos narrativos | `data/lore/...` | Solo las rutas expresamente referenciadas por contenido instalado. |

Los JSON bajo `data/arcs/templates/` y `data/locations/templates/` **no están activos**. Copiarlos a la raíz sin verificar referencias, restricciones y consecuencias físicas puede provocar errores de compilación o alterar partidas nuevas. El catálogo instalado forma parte de la definición de partida y se comprueba en save/load: usar **partidas nuevas de prueba** para ensayar cambios editoriales; no borrar partidas automáticamente.

## 2. Cinco conceptos que no deben confundirse

1. **Mención literaria:** un nombre en un relato no crea una estación.
2. **Declaración física:** una localización authored o una entidad de `world_requirements` contribuye al universo antes de explorarla.
3. **Ubicación de un documento:** el scheduler puede reservar una pieza narrativa en un host históricamente certificado sin revelarlo.
4. **Conocimiento del jugador:** solo scan, lectura/importación, radio u otras acciones legítimas revelan información.
5. **Ruta operativa:** un `LINK` válido, importado y certificado puede publicar un enlace navegable; no requiere necesariamente una arista histórica, pero sí cumplir las reglas geométricas y de conocimiento.

**Nunca** crear retroactivamente una instalación para colocar una historia. El selector de contenido forzado utiliza hosts preexistentes y puede dejar una pieza pendiente si no se cumplen sus condiciones. La existencia física tampoco implica que el jugador pueda visitar el lugar.

## 3. Añadir entidades y relaciones físicas

Los paquetes instalados de localizaciones, arcos y singles pueden incluir `world_requirements` (contrato `narrative-world-v1`). Las entidades se declaran **una sola vez**; otros paquetes deben referenciarlas con `references`, no duplicarlas. El ejemplo ejecutado está en `tests/fixtures/narrative_world/alpha.json` y `beta.json`.

Modos de posición: `fixed_ly`, `box_ly` y `offset_from` con `offset_box_ly`; la implementación permite filtros `sector` y `regions_any`. Relaciones compatibles: `near`, `historical_association` y `physical_link`. Esta última **verifica una arista ya permitida por worldgen**: no crea una conexión nueva. No inventar cronología, sistemas planetarios o habitantes mediante estos campos.

`claims` puede representar rumores o afirmaciones no vinculantes; no determina existencia ni constituye una prueba de supervivientes. Las posiciones variables se fijan por semilla y catálogo antes de jugar, con validación y límites de búsqueda. Los identificadores internos authored se mantienen estables; los IDs públicos cortos (`P-...`) son para el jugador y **no sustituyen las referencias canónicas** al escribir `LINK`, `NODE` o JSON de autoría.

## 4. Arcos

Un arco instalado en `data/arcs/<arc_id>.json` puede tener `primary_intel` y `secondary_lore_docs`, cada uno con reglas de colocación y entrega. Un `primary_intel` de `kind: "link"` con una línea `LINK: ORIGEN -> DESTINO` es la opción mejor caracterizada para un arco de navegación. Ambos extremos deben corresponder a identidades reales; el salto máximo vigente es 45 ly.

`placement_rules.primary` y `.secondary` pueden restringir los receptores por `candidates`, `require_kind_any`, `avoid_node_ids` y `max_hops_from_start`. Las piezas pueden usar `constraints` como `min_year`, `max_year`, `min_dist_ly`, `max_dist_ly` y `regions_any`. El valor `secondary.count` **limita el número asignado**, no ordena el argumento ni espera al primary. **No existe un grafo automático de precedencias entre documentos.**

`force=true` significa que se intentará colocar la pieza según su `force_policy`: `soft`, `deadline` o `hard`; no garantiza recepción, visita ni lectura. Una pieza con `force=true` y política `none` no obtiene una vía útil de colocación. Las condiciones físicas y ventanas de oportunidad siguen siendo obligatorias; no se reabren pools agotados. El arranque valida oportunidades para piezas esenciales, no el éxito del jugador en descubrirlas.

## 5. Singles

Cada entrada de `data/lore/singles/index.json` requiere una identidad `single_id` y puede configurar `weight`, `channels`, `constraints`, archivos y contenido EN/ES. No usa el `placement_rules` propio de los arcos y no desbloquea automáticamente un primary.

Con el balance actual, **cada pieza no forzada** se evalúa de manera independiente cada año de juego con `p = clamp(0.05 × max(weight, 0), 0, 1)`, siempre que resulte elegible. `weight: 0.4` equivale a 2 % por evaluación elegible; **no** es el 40 % de una bolsa ponderada. El sorteo decide una asignación a un host válido, no una recepción inmediata. Puede no aparecer nunca en una partida.

## 6. Canales, pistas y radio

| Canal | Uso y condición principal |
| --- | --- |
| `salvage_data` | Recuperación con dron y lectura del archivo remoto; solo donde existe interfaz de salvage. |
| `uplink_only` | Publica un `LINK` válido mediante uplink en estación, relé o waystation; sin archivo narrativo. |
| `ship_os_mail` | Correo entregado por el scheduler mediante trigger permitido; lectura separada. |
| `captured_signal` | Señal canalizada mediante el sistema de comunicaciones y los triggers admitidos. |
| `station_broadcast` | Broadcast de estación, relé o waystation, sujeto a su contexto y recepción. |

En los arcos se usa `allowed_channels`; en singles, `channels`. Una pieza asignada no se entrega hasta cumplir el trigger y las puertas operativas. Un texto puede incluir `LINK:`, `NODE:`, `SECTOR:` o `COORD:`; la mera escritura no importa intel hasta que el jugador lo lea o importe. Usar los enlaces y vinculaciones definidos por el motor, no inventar sintaxis.

**Radio authored histórica:** el bloque opcional `radio_emitters` (versión `radio-emitters-v1`) define transmisores/emisiones y tiempos de origen en localizaciones, arcos o singles. Una declaración explícita **tiene precedencia sobre toda la radio procedural del mismo host**, incluso con `emissions: []`. La onda requiere alcance y tiempo de propagación real. Una emisión antigua no demuestra actividad humana presente. Es un contrato distinto del simple canal de entrega del scheduler; consultar el ejemplo de `docs/systems/radio-spacetime.es.md` antes de usarlo.

**Información procedural:** B1 conserva archivos y rutas históricas certificadas; B2 genera historia de comunicaciones. Un arco no debe alterarlas según el progreso del jugador ni presentar una solución calculada como prueba de tráfico humano histórico. El contenido tiene que respetar `C-DATA-004`: «¿Cómo sabe esto la nave?».

## 7. Prueba mínima recomendada para 4D-3e5c-C

Crear **una historia pequeña y aislada**, primero como fixture optativa de pruebas (no en directorios activos): estación, pecio/nave y relé; un arco con primary y secundarios; uno o dos singles. Distribuir indicios por al menos dos canales legítimos entre salvage, uplink y radio. Emplear `world_requirements`, bindings y relaciones **solo cuando aporten una necesidad real**. Los hechos deben preceder a la observación y no depender del orden de visita.

Verificar como mínimo: compilación de catálogo e identidades por semilla; no divulgación prematura; colocación y triggers sin fabricar hosts; importación real y límite de salto; continuidad de historia EN/ES; save/load; ausencia de duplicados; un recorrido con comandos públicos que descubra información y avance sin debug. Si una restricción impide el escenario, corregir sus datos antes de ampliar Python.

Prueba de regresión de referencia:

```bash
cd /home/jon/prog/retorno_case/retorno
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
```

En la primera pasada, evitar introducir localizaciones y arcos directamente en el catálogo real: activarlos cambia el universo de nuevas partidas y puede invalidar guardados de prueba anteriores. Una vez aceptado el fixture y su experiencia, decidir explícitamente qué contenido se promociona a producción.

## 8. Pendientes editoriales conocidos

La continuidad exploratoria universal sigue **sin demostrarse** (ver [`design/exploration-softlock-research.es.md`](design/exploration-softlock-research.es.md)); F-DEAD-01 nivel 2 está aplazado. No resolver problemas de entrega authored mediante nodos, rutas o señales inventados. No activar AMANECER ni otros materiales antiguos por copiar plantillas. Las guías históricas deben conservarse como archivo de referencia, no como contrato vigente.
