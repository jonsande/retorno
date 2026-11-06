> **Compatibilidad B1.** Se conservan la matriz física y la finalización B0 descritas abajo. Las partidas nuevas preparan archivos [historical-information-v1](historical-information.es.md), manteniendo archivos brutos inaccesibles de waystation sin frontera de salvage. Los pushes legítimos pendientes siguen siendo independientes del uplink agotado.

# Capacidades físicas de información — 4D-3e5c-B0

[English](information-capabilities.md). Implementado el 2026-11-06, sobre
`80f68320ba236cdc32e73774c551b270fd8d4b9f`.

## Autoridad y alcance

`src/retorno/model/world.py:information_capabilities` es la autoridad del
criterio de interfaces físicas de información. Describe interacciones
potenciales; disponibilidad de la nave, acoplamiento, ubicación del dron,
payload disponible y conocimiento conservan sus gates separados. El
planificador adapta este criterio y conserva su API del enum `Mechanism`.

| Tipo físico | `drone salvage data` | `uplink` |
| --- | --- | --- |
| `station` | Sí | Sí |
| `relay` | Sí | Sí |
| `ship` | Sí | No |
| `derelict` | Sí | No |
| `waystation` | No | Sí |
| `origin`, `unknown`, `nav_point`, `transit`, otros tipos | No | No |

Son las capacidades de acción preexistentes. B0 no concede interfaces ni
cambia gates operativos. La recuperación de recursos es independiente de la
tabla.

## Archivos preparados y oportunidades efectivas

La inicialización conserva su orden y los `base_files`/`injected_files` brutos.
No cambian el productor de archivos procedurales, sus tiradas ni la política
de selección de uplink. Pueden conservarse archivos históricos o asignados
internamente por compatibilidad aunque su host no tenga interfaz pública de
salvage.

`core/lore.py:collect_node_salvage_data_files` sólo devuelve archivos de hosts
físicos con capacidad de salvage. `_pending_node_files_count` aplica el mismo
criterio antes de proyectar el montaje. Así, cantidades y firmas del survey
describen datos recuperables por salvage; una waystation sigue indicando su
infraestructura uplink medida. El filtro nunca borra archivos ni los marca
como entregados.

La finalización conserva los campos persistidos existentes:

- `scrap_complete`: no queda scrap físico.
- `extras_complete`: no quedan módulos ni drones recuperables.
- `data_complete`: no quedan rutas nuevas montables por una interfaz física
  de salvage disponible, no hay push pendiente sin entregar y, o no existe
  interfaz uplink, o su pool de rutas ya se consumió.
- `node_cleaned`: los tres indicadores anteriores son ciertos.

Un host con uplink sigue pendiente hasta consumirlo. Los pushes pendientes son
independientes y pueden mantener datos pendientes después de ese consumo.
Los fallos temporales de la nave no borran potencial ni completan el host.
Un uplink agotado conserva los reintentos existentes de entrega narrativa
pendiente. La información ya montada/leída y el intel legítimo a bordo siguen
siendo utilizables.

## Frontera, deadnodes y recuperación

`core/exploration_recovery.py` filtra tanto pools inicializados como el fallback
de archivos sin inicializar. Un archivo de waystation no puede simular una
frontera de salvage. Payload legítimo de uplink, pushes pendientes, rutas
conocidas e intel adquirido conservan sus reglas. Las consultas siguen siendo
puras.

`core/deadnodes.py` ya excluye pools `node_cleaned`; ahora recibe el resultado
derivado correcto mediante el recálculo normal y la carga de partidas. No
cambian umbrales, tiempos ni políticas de puentes. La recuperación estructural
usa el criterio compartido en su comprobación de fuentes y no puede certificar
un archivo irrecuperable de waystation como evidencia de salvage. La
recuperación global puede solicitar selección histórica al desaparecer la
frontera falsa. Eso no garantiza fuente ni salida: el catálogo instalado puede
dar un resultado condicional. Véase [recuperación estructural](structural-recovery.es.md).

## Persistencia y conocimiento

Se mantiene el esquema 3. Tras las validaciones existentes, la carga recalcula
indicadores derivados de hosts físicos sin capacidad de salvage, incluidos
caches anteriores a B0. Conserva archivos brutos y montados, marcas de
consumo/entrega, recursos, rutas físicas y los bytes originales de la partida
en disco. Un guardado posterior escribe el cache actualizado normalmente. Los
hosts con salvage conservan su comportamiento de carga.

No se publica información interna de archivos o scheduler. CLI y Textual usan
el mismo evento medido de survey y renderizadores localizados. `status`, `diag`
y las demás consultas públicas no revelan archivos preparados ni mutan el
estado. Se conserva `C-DATA-004`.

## Validación y límites

`tests/information_capabilities_smoke.py` cubre una waystation procedural real
de semilla 0, rechazo público de salvage y acciones de uplink/survey, los cuatro
tipos con salvage, finalización, archivos y pushes conservados, deadnodes y
recuperación global/estructural, partidas de esquema 3 antiguas/actuales y
comparaciones negativas CLI/Textual EN/ES variando archivos ocultos. El informe
externo incluye muestras deterministas referencia/B0 y un recorrido desde el
prólogo con comandos públicos.

B0 no implementa `historical-information-v1` ni cambia generación histórica,
topología física, radio, políticas de asignación del scheduler, contenido
narrativo authored, balance de recursos, navegación, sistemas de nave ni
audio. Los archivos internos sin interfaz siguen inertes; su uso futuro exige
una decisión de diseño separada.
