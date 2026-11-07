> **4D-3e5b — extensión optativa de emisores.** `radio_emitters` en la raíz de una
> localización, arco o single instalado declara equipo y emisiones independientes
> de su tipo de host. Reutiliza identidades, alias y certificados de este contrato;
> no define geografía adicional. `piece_key` + `radio_emission` vinculan una pieza
> a una emisión sin adelantar su scheduler/trigger. El catálogo completo incluye
> radio; la huella física excluye solo esos metadatos. Formato, límites, ejemplos
> válidos y compatibilidad: [radio espacial y temporal](systems/radio-spacetime.es.md).
> Guías generales de autoría y revisión editorial: e5c, sin cambios incompatibles.

# Requisitos narrativos físicos — 4D-3e4

[English](narrative-world-contract.md). Estado: implementación mínima probada;
**formato optativo provisional**, pendiente de revisión externa como interfaz
definitiva. Propietarios: `worldgen/narrative.py`, `worldgen/manifest.py`,
`runtime/data_loader.py` y `core/lore.py` bajo `src/retorno/`.

## Activación y cinco capas

Solo se recogen `data/locations/*.json`, `data/arcs/*.json` y las entradas de
`data/lore/singles/index.json`. Los loaders comparten la lectura no recursiva
con procedencia. No se activan `templates/` ni `narrative/`. Todos los singles
instalados aportan sus declaraciones, aunque nunca se sortee su documento.

Separar referencia literaria, declaración canónica, emplazamiento histórico,
conocimiento e itinerario publicado. «Horizon desapareció» en prosa no hace
nada físico ni revela intel. `claims` contiene afirmaciones no vinculantes;
no alimenta el solucionador. Los rumores no son declaraciones de existencia.
Las `constraints` existentes siguen filtrando **documentos**.

## Datos ejecutables

Los dos paquetes completos y sus textos EN/ES están en
[`tests/fixtures/narrative_world/`](../tests/fixtures/narrative_world/).
`alpha.json` es un arco; `beta.json` es una entrada de índice de singles.
Son fixtures optativas, **no contenido instalado**. El test los instala solo
en una copia temporal y ejercita bootstrap, trabajos de dron, lectura e importación:

```sh
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
```

Bloque mínimo, añadido opcionalmente a una localización, arco o single:

```json
{"world_requirements": {
  "version": "narrative-world-v1",
  "entities": [{"id": "TEST_HOST", "name": "Test Host", "kind": "station",
    "position": {"fixed_ly": [26, 27, 1]}}],
  "references": ["ECHO_7"],
  "relations": [],
  "claims": [{"text": "NEVER_EXISTED está habitado", "status": "rumor"}]
}}
```

Cada ID se declara una vez; los demás paquetes lo comparten mediante
`references`. Las referencias resuelven IDs, nombres y `aliases` explícitos
sin distinguir mayúsculas. Se rechazan duplicados, incluso idénticos, y toda
ambigüedad entre nombres, alias e IDs. `RETORNO_SHIP` queda reservado y no es
un destino histórico. Las localizaciones actuales conservan su esquema y
atributos; no necesitan adoptar este bloque.

Una entidad nueva admite `id`, `name`, `aliases`, `kind`, `position`. Sus kinds
son `station`, `relay`, `waystation`, `ship`, `derelict`; un pecio explorable
puede usar `ship`. Para salvage y archivos authored específicos, el esquema
existente de `data/locations/` sigue disponible. El bloque nuevo no inventa
recursos ni incorpora un simulador de conservación.

Posiciones alternativas, usadas en las fixtures:

```json
{"id": "TEST_STATION", "name": "Test Horizon", "aliases": ["Horizon"],
 "kind": "station", "position": {"box_ly": [[149950,150050],[1,8],[1,8]],
 "regions_any": ["disk","halo"]}}
```

```json
{"id": "TEST_WRECK", "name": "Test Wreck", "kind": "ship",
 "position": {"offset_from": "Horizon", "offset_box_ly": [[0.5,1.2],[0,0],[0,0]]}}
```

Solo un modo por posición: `fixed_ly`, `box_ly` u `offset_box_ly` con
`offset_from`. Se admiten filtros `sector` canónico y `regions_any`.
No hay restricciones de texto libre, órbitas, sistemas planetarios ni fechas.
Un campo geométrico desconocido se rechaza, nunca se ignora como satisfecho.

```json
{"type":"near", "from":"TEST_STATION", "to":"TEST_WRECK", "min_ly":0.5, "max_ly":1.2}
```

`near` verifica distancia euclídea inclusiva. `physical_link` exige una arista
directa que **ya autorice la topología productiva**, dentro de 45 ly; no añade
aristas especiales. `historical_association` comprueba identidades y conserva
el hecho histórico sin inventar cronología. `from_kind`/`to_kind` permiten
comprobar tipos. Proximidad, enlace físico y ruta conocida son distintos.
No se admite todavía una exigencia general de camino multihop entre entidades.

## Compilación y límites

Antes de devolver el estado inicial, `prepare_new_world` recoge el catálogo,
valida recursos referenciados, IDs y alias, resuelve posiciones y relaciones,
compila pistas y verifica oportunidades esenciales. Usa `define_manifest` y
sus sesiones productivas; no sustituye muestreo, cupos, guardrail ni topología.

Cada posición variable tiene 32 candidatos derivados de versión, semilla e ID.
Se ordenan entidades por dependencias e ID y se prueba mediante backtracking
con un máximo de 4096 pasos. No se usa RNG de juego. Ciclos de posiciones,
intervalos invertidos y contradicciones demostrables se rechazan.
`not_evaluated` significa presupuesto agotado o ausencia de solución verificada
en la discretización; **no** demuestra imposibilidad continua ni permite jugar.
`unsatisfiable` se reserva para contradicciones demostradas o dominios cerrados;
`invalid`, para errores de contrato. Los errores incluyen procedencia, entidad
y campo cuando se conocen.

El manifiesto incorpora entidades authored adicionales, su ámbito de catálogo
cuando hay declaraciones nuevas, y conserva resultados y relaciones certificados
en `WorldState.narrative_snapshot`. Los nuevos nodos se materializan lazy sin
contactos iniciales. Los nodos authored actuales mantienen bootstrap y loot.
Sin bloques nuevos se conserva el ámbito físico anterior. El snapshot de
catálogo se guarda también en ese caso. La comparación medida no cambia knobs
de densidad, hubs, recursos ni conectividad: authored ocupa los cupos existentes.

## Pistas vinculadas a la semilla

`spatial_bindings` es optativo, separado de las instrucciones públicas de intel:

```json
{"spatial_bindings": {"version":"narrative-world-v1", "values": {
  "dest_id":{"entity":"TEST_WRECK","field":"id"},
  "dest_sector":{"entity":"TEST_WRECK","field":"sector"},
  "dest_coord":{"entity":"TEST_WRECK","field":"coord"}
}}}
```

Se aplica a `line`, contenido inline y `content_ref`, `content_ref_en/es` del
documento y sus `files`. Campos admitidos: `id`, `sector`, `coord`. Ejemplo TXT:

```text
Archivo del pecio: {{dest_sector}}, {{dest_coord}}.
NODE: {{dest_id}}
SECTOR: {{dest_sector}}
```

Se renderiza **al compilar** y se congela bajo una referencia privada de texto;
la lectura no vuelve a elegir el destino. Tras aplicar los bindings, siempre se
rechaza un token reservado `{{nombre}}` sin resolver (`[a-z][a-z0-9_]*`), aunque
el documento no incluya `spatial_bindings`. La comprobación abarca `line`, texto
inline y recursos referenciados, incluidos los archivos authored activos, con
diagnóstico de paquete, archivo y campo. Las llaves que no cumplen esa sintaxis
son literales. Una referencia ausente también falla antes de jugar. No hay sustituciones globales de nombres
ni reconocimiento de prosa. `[SECTOR_VAELOR]` sigue siendo un marcador editorial
inerte. Compilar un texto no lo entrega ni importa.

## Hosts, reservas y consumo

Todos los `force=true` instalados se validan como esenciales. El campo optativo
`essential=true` exige una política de forzado válida. Se conserva `primary_intel`,
`secondary_lore_docs`, candidatos, constraints, canales, preferencias, pesos,
políticas y deadlines. La validación prueba un instante temporal elegible y un
host/canal; no garantiza la conducta del jugador ni una oportunidad eterna.

El campo opcional `constraints.anchor_distances` filtra hosts por cotas inclusivas
de distancia euclídea 3D respecto a IDs authored certificados o alias inequívocos,
incluidas entidades ocultas/lazy de `world_requirements`. Cada entrada de una lista
no vacía admite solo `anchor`, `min_ly`, `max_ly`; exige al menos una cota finita no
negativa, el mínimo ausente vale cero y las entradas se combinan por AND. Bootstrap
rechaza IDs, geometría o estructura inválidos, bool, números no finitos y cotas
invertidas, también en piezas opcionales y singles. Distancias al inicio y regiones
conservan su significado. `placement_rules.primary.host_selection: "seeded"` elige
una reserva esencial de forma determinista entre testigos viables certificados
del ámbito finito; el defecto sigue siendo el primer host ordenado. Runtime nunca
sustituye el host reservado. Véase el [contrato relativo](design/lore-placement-anchors.es.md).

La consulta histórica usa hasta 64 sectores, los authored y una búsqueda finita
cerca del inicio y de las distancias declaradas. Una oportunidad certificada
puede reservarse sin materializar ni revelar el host. Si la búsqueda no certifica
oportunidad, no se inicia la partida. No se afirma ausencia galáctica a partir
del presupuesto. Cada canal de archivo esencial necesita un cuerpo no vacío
en EN y ES, comprobado antes de añadir cabeceras y con el fallback lingüístico
existente a EN. Salvamento admite el fallback `line` cuando la referencia falta
o su texto está vacío; no lo aplica a texto formado solo por espacios, ni a
canales push. Las cabeceras solas no cuentan como contenido. Se conservan las
comprobaciones de rutas/colisiones y el comportamiento previo de documentos
opcionales. `uplink_only` esencial necesita un LINK físico válido.

Se persiste solo host, canal, sector y procedencia de la reserva. Al inicializar
su pool se prepara una pieza cuya política ya permite colocarla, antes del
cierre por visita. Los intentos tardíos respetan ventanas y agotamiento. Un
deadline puede caducar sin entregar; se deja pendiente y nunca reabre un pool.
El selector materializa emplazamientos certificados, no crea estaciones.
El antiguo helper privado `_spawn_ad_hoc_candidate_for_forced_piece` delega
en ese selector por compatibilidad. Los muestreadores ad hoc de lore se retiraron.
`register_hidden_anchored_node` sigue reservado al recovery estructural existente,
que se integrará en e5; esta fase no resuelve F-DEAD-01.

## Intel y partidas

`NODE` y bloques authored resuelven ID/nombre/alias y materializan historia válida.
Los literales ausentes conservan pistas sin crear estaciones. `LINK` comparte
parser entre import explícito y lectura; exige extremos físicos y cap. Mantiene
el contrato operativo de 4D-1: una tabla válida no necesita una arista del grafo
histórico. `physical_link` declarativo sí la exige. `SECTOR` aporta intel regional
y materialización lazy sin revelar inventario. `COORD` crea `NAV_...` de tipo
`nav_point`, nunca estación; se rechazan números no finitos.

Los bloques formados solo por instrucciones explícitas pasan al parser de
líneas, sin sorteo de corrupción adicional. Un bloque bare de nombre/alias/ID
revela authored; el selector bare de sector histórico sigue existiendo. Un token
no resuelto queda como intel de confianza cero. La recuperación corrupta conserva
su tirada y solo descubre hubs preexistentes dentro del radio, excluyendo primaries
protegidos. No crea instalaciones correctivas. Scan y solve manual conservan sus
excepciones deliberadas.

La política de carga es **rechazar cambios del catálogo instalado**, incluidos
retirada, identidad, recursos de texto y sustitución de paquetes. Se guardan
definiciones y textos compilados. Para contenido legacy sin bloques nuevos,
los loaders existentes se consultan con verificación previa de la huella; con
requisitos nuevos, runtime consume el snapshot. Guardar/cargar verifica la huella
completa. Restaurar los paquetes originales permite volver a cargar. No se borran
saves ni se migra historia. El esquema 3 añade snapshot obligatorio para las
nuevas cargas; saves anteriores sin él se rechazan explícitamente. Contenedor V2,
checksum, backups, progreso, identidades y recursos consumidos se conservan.

## AMANECER y límites

| Categoría | Aplicación |
| --- | --- |
| Soportado | Pecio Tábano como `ship` con identidad estable y posición por semilla; documentos restringidos por ID; bindings de sector; un destino existente y enlaces validados. |
| Adaptación de datos pendiente | JSON optativos, textos EN/ES, regiones/cajas, relaciones y canales reales; hacer alcanzable el destino requiere una ruta certificada concreta. |
| Decisión editorial | Estado presente de Bruma, naturaleza del destino, suerte de las siete personas. |
| Sistema no implementado | VAELOR como sistema estelar y sus planetas/componentes; conservación física dinámica, cronología y simulación de comunidades. |

La existencia de Bruma solo puede concretarse en un kind jugable tras decisión
editorial; no se fuerza un pecio. VAELOR y sus planetas no se convierten en nodos
por mencionar sus nombres. C2b instala solo el arco de Elena Varela y su Liria
histórica aprobada en el catálogo del árbol de trabajo. El recorrido público
acotado no descubrió la pista; véase la [revisión C2b](testing/amanecer-productive-review.es.md).
Los otros arcos y singles de AMANECER siguen inactivos y se conservan los
manuscritos originales. No hay editor,
gestor universal de mods, nuevos canales, nuevo scan ni rebalance general.
