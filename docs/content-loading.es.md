> **Actualización implementada 4D-3e4 (2026-11-05).** La frontera de activación sigue siendo no recursiva. El arranque recopila también requisitos optativos de arcos y singles, comprueba recursos obligatorios y conserva una huella y snapshot; guardar/cargar rechaza cambios del catálogo. Las descripciones anteriores de lectura tardía y recursos vacíos corresponden al loader aislado, no a la validación de partidas nuevas. La referencia vigente y sus ejemplos ejecutables son [Requisitos narrativos físicos](narrative-world-contract.es.md). El cuerpo anterior conservado a continuación es histórico donde contradiga esta actualización.

# Contrato de carga de contenido

Estado: **comportamiento implementado, verificado en el commit `2ffb1ab`**.

Versión inglesa: [content-loading.md](content-loading.md)

Este documento registra desde dónde carga RETORNO el contenido del universo y
el contenido narrativo. Describe la implementación actual; no aprueba una
política permanente de carpetas ni declara desechables los archivos inactivos.

## Modos de carga

- **Archivo directo:** el código abre una ruta exacta. Los archivos adyacentes
  no se descubren automáticamente.
- **Directorio explícito, no recursivo:** el código aplica
  `Path.glob("*.json")` a un directorio concreto. Los JSON de sus subdirectorios
  quedan excluidos.
- **Directorio recursivo:** el código aplica `Path.rglob(...)`; se incluyen los
  archivos coincidentes de los subdirectorios.
- **Referencia explícita:** una definición activa contiene una ruta relativa y
  el código abre ese recurso exacto. Depositar un recurso en ese árbol no lo
  activa por sí solo.

## Contrato implementado

La implementación principal está en
[`src/retorno/runtime/data_loader.py`](../src/retorno/runtime/data_loader.py).

| Contenido | Fuente activa | Modo de carga | Consecuencia actual |
| --- | --- | --- | --- |
| Localizaciones authored | `data/locations/*.json` | Directorio explícito, no recursivo (`load_locations`) | Se leen los cinco JSON de la raíz. `data/locations/templates/*.json` queda excluido. |
| Arcos | `data/arcs/*.json` | Directorio explícito, no recursivo (`load_arcs`) | Actualmente no hay JSON en la raíz, por lo que no se carga ninguna definición de arco. `data/arcs/templates/*.json` queda excluido. |
| Singles | `data/lore/singles/index.json` | Archivo directo (`load_singles`) | Solo participan las entradas del índice. Los textos adyacentes requieren un `content_ref_*` explícito. |
| Plantillas de región de worldgen | `data/worldgen/templates/*.json` | Directorio explícito, no recursivo (`load_worldgen_templates`) | `bulge`, `disk` y `halo` son entradas activas de la generación de sectores. El loader selecciona expresamente este directorio `templates/`. |
| Arquetipos de worldgen | `data/worldgen/archetypes/*.json` | Directorio explícito, no recursivo (`load_worldgen_archetypes`) | Los cinco JSON de arquetipos son entradas activas de la generación de sectores. |
| Módulos | `data/modules.json` | Archivo directo (`load_modules`) | Las definiciones de módulos se cargan desde este único objeto JSON. |
| Loot por nodo | `data/loot/<node_id_normalizado>.json` | Archivo directo calculado (`load_loot`) | No se escanea el directorio. Actualmente el repositorio no contiene archivos bajo `data/loot/`. |
| Recursos de localizaciones y lore programado | Rutas como `data/lore/...` indicadas por `content_ref` o `content_ref_en/es` | Referencia explícita | `data/lore/` no se escanea de forma general. Un recurso solo participa si lo referencia contenido activo o lo abre un loader dedicado. |
| Secuencias de inicio e hibernación | Nombres fijos bajo `data/lore/startup/` y `data/lore/hibernate/` | Archivos directos con fallback de idioma | `runtime/startup.py` prueba el idioma solicitado, después EN y después ES. Este loader no descubre los demás archivos de esos directorios. |
| Manuales diegéticos | `data/manuals/**/*.txt` | Directorio recursivo | `bootstrap.py` carga recursivamente todos los textos en `/manuals/` dentro del filesystem del juego. |

Las localizaciones authored se consumen durante el bootstrap en
[`src/retorno/bootstrap.py`](../src/retorno/bootstrap.py). Las plantillas y
arquetipos de worldgen se solicitan desde
[`src/retorno/worldgen/generator.py`](../src/retorno/worldgen/generator.py). Las
referencias de lore y las definiciones de arcos y singles se consumen en
[`src/retorno/core/lore.py`](../src/retorno/core/lore.py).

El nombre de un directorio no determina por sí solo su activación:

- `data/arcs/templates/` y `data/locations/templates/` no son recorridos por sus
  loaders y no participan automáticamente en una partida.
- `data/worldgen/templates/` sí participa porque el loader selecciona
  expresamente ese directorio.
- Convertir en recursivo cualquiera de los loaders de contenido authored
  cambiaría el comportamiento y queda fuera de este contrato.

## Localizaciones authored activas

Las definiciones actuales en la raíz son `ARCHIVE_01`, `ECHO_7`, `HARBOR_12`,
`RETORNO_SHIP` y `UNKNOWN` (`start_00.json`). `RETORNO_SHIP` también proporciona
contenido para el filesystem de la nave durante el bootstrap; no se trata como
un destino ordinario del mundo.

## Inventario de plantillas de arcos inactivas

Los cuatro archivos siguientes quedan excluidos por el loader no recursivo de
arcos. La “finalidad probable” es una inferencia de auditoría, no una etiqueta
de ciclo de vida aprobada.

| Archivo / id de arco | Referencias a localizaciones y dependencias | Finalidad probable |
| --- | --- | --- |
| `blackout_01.json` / `blackout_01` | Primario `BLACKOUT_12 -> VAULT_09`; candidato `blackout_12`; dos parejas de lore EN/ES bajo `data/lore/packs/blackout_01/`. Ningún extremo tiene definición de localización en el árbol actual. | Borrador de arco incompleto o aparcado que ejercita constraints y varios documentos secundarios. |
| `carnaval_cache_01.json` / `carnaval_cache_01` | Primario `ANCORA -> CARNAVAL_34`; ambos extremos solo existen bajo `data/locations/templates/`; pareja de lore primario EN/ES bajo `data/lore/packs/carnaval_cache_01/`. | Borrador aparcado de arco con localizaciones authored y forzado por deadline. |
| `corridor_01.json` / `corridor_01` | Primario `HARBOR_12 -> ARCHIVE_01`; ambos extremos tienen definición activa en la raíz y variante inactiva; dos parejas de lore EN/ES bajo `data/lore/packs/corridor_01/`. | Antiguo arco activo/de referencia y ejemplo principal de esquema en `docs/arcs*`; actualmente aparcado. |
| `example_unforced.json` / `example_unforced` | Primario `HARBOR_12 -> GLASSHOLLOW`; `HARBOR_12` está activo y `GLASSHOLLOW` solo existe como plantilla; cuatro parejas de lore EN/ES bajo `data/lore/packs/example_unforced/`. | Ejemplo reutilizable explícito para piezas no forzadas, con un objetivo authored inactivo. |

Todos los archivos de lore referenciados en la tabla existen actualmente. Esto
confirma la presencia de recursos, no que los esquemas de los arcos inactivos
sean plenamente válidos frente a la semántica actual del scheduler.

## Inventario de plantillas de localizaciones authored inactivas

Los once archivos siguientes quedan excluidos por el loader no recursivo de
localizaciones.

| Archivo / id de nodo | Dependencias y relaciones | Finalidad probable |
| --- | --- | --- |
| `ancora.json` / `ANCORA` | Origen del enlace del arco inactivo `carnaval_cache_01`; referenciado por la tabla uplink de la plantilla `HARBOR_12`. | Estación aparcada de soporte para un arco. |
| `archive_01.json` / `ARCHIVE_01` | Variante inactiva del `ARCHIVE_01` activo; referencia los mismos recursos EN/ES de last-signal, pero carece de los campos de drones de la variante activa. | Variante anterior de referencia o balance, no un destino único. |
| `carnaval_34.json` / `CARNAVAL_34` | Destino del arco inactivo `carnaval_cache_01`. | Destino de arco aparcado. |
| `curl_12.json` / `CURL_12` | Destino de un `LINK` incrustado en la plantilla `ECHO_7`. | Extremo aparcado de una cadena authored antigua. |
| `derelict_a3.json` / `DERELICT_A3` | Sin dependencia explícita desde las plantillas inventariadas. | Ejemplo o borrador de localización authored independiente. |
| `echo_7.json` / `ECHO_7` | Variante inactiva del `ECHO_7` activo; añade cuatro fragmentos y un mail EN, incluido `ECHO_7 -> CURL_12`. Los recursos referenciados existen. | Variante narrativa anterior o ejemplo de integración reutilizable. |
| `glasshollow.json` / `GLASSHOLLOW` | Destino de `example_unforced`; candidato en tablas uplink de plantilla. | Destino aparcado de arco/uplink. |
| `harbor_12.json` / `HARBOR_12` | Variante inactiva del `HARBOR_12` activo; contiene una tabla uplink authored para `ANCORA`, `MOURN_ANCHOR`, `VEIL_GARDEN`, `SABLE_CHAPEL` y `GLASSHOLLOW`. | Red authored anterior o ejemplo de uplink. |
| `mourn_anchor.json` / `MOURN_ANCHOR` | Referenciado por las tablas uplink de las plantillas `HARBOR_12` y `SABLE_CHAPEL`. | Relay aparcado de una red authored. |
| `sable_chapel.json` / `SABLE_CHAPEL` | Es referenciado y contiene candidatos uplink de plantilla; su propia tabla también incluye `SABLE_CHAPEL`. | Waystation aparcada de una red authored; la autorreferencia debe revisarse antes de activarla. |
| `veil_garden.json` / `VEIL_GARDEN` | Referenciado por las tablas uplink de las plantillas `HARBOR_12` y `SABLE_CHAPEL`. | Estación aparcada de una red authored. |

El historial muestra que el commit `36911df` movió tres arcos y diez
localizaciones a estos directorios `templates/` sin modificar los loaders. Esto
respalda una desactivación deliberada durante el rebalance previo a worldgen,
pero no define por sí solo su ciclo de vida final ni su calidad.

## Propuesta de clasificación futura

Esta propuesta no mueve archivos. Antes de reorganizar contenido, cada
definición debería recibir un estado revisado explícito:

1. **Activo:** contenido de producción destinado a ser descubierto por un
   loader y cubierto por pruebas de integración. Su directorio debe coincidir
   con el contrato documentado del loader.
2. **Borrador:** contenido de producción incompleto o desactivado
   intencionadamente. Puede depender de nodos inactivos o esquemas en evolución
   y no debe ser visible para el loader.
3. **Ejemplo reutilizable:** material mínimo y mantenido de autoría destinado a
   documentación o pruebas, no a partidas normales. Debe indicar qué
   esquema/versión demuestra y no aparentar ser contenido activo.

Clasificación candidata, pendiente de revisión:

- `example_unforced` es el candidato más claro a ejemplo reutilizable.
- `blackout_01` y `carnaval_cache_01` son candidatos a borrador porque sus
  dependencias de localización no están activas; `corridor_01` necesita una
  decisión de producto porque sus extremos están activos y también se usa como
  documentación.
- Las variantes de plantilla de `ARCHIVE_01`, `ECHO_7` y `HARBOR_12` deben
  compararse con sus definiciones activas antes de clasificarlas como borradores
  o ejemplos.
- Las demás localizaciones que solo existen como plantilla forman dependencias
  de arcos o redes uplink aparcadas y deben revisarse por grupos, no activarse
  individualmente.

