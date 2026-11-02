# Documentación de RETORNO

Este índice describe la documentación almacenada actualmente bajo `docs/` y su
estado de verificación. Enlazar una guía histórica o parcialmente obsoleta no
la convierte en fuente autoritativa.

Versión inglesa: [README.md](README.md)

## Estados

- **Verificado:** contrastado con la implementación para el alcance indicado.
- **Parcialmente verificado:** conserva material útil, pero algunas afirmaciones
  requieren una revisión técnica posterior.
- **Pendiente de revisión:** contiene afirmaciones obsoletas o sin verificar y
  no debe usarse como descripción del comportamiento vigente.
- **Guía normativa:** define una convención del proyecto, no el comportamiento
  en tiempo de ejecución.

## Referencia técnica vigente

| Documento | Finalidad | Estado |
| --- | --- | --- |
| [Universo físico y generación procedural](systems/world-generation.es.md) | Referencia canónica del modelo espacial, regiones, sectores, worldgen, topología, contenido authored y determinismo. | **Verificado** contra código productivo en `3658577`, datos activos y pruebas posteriores de la Fase 3A.1. Documenta las lagunas conocidas y el efecto materializador del diagnóstico de sector; no cubre en profundidad navegación, lore o failsafes. |
| [Physical universe and procedural generation](systems/world-generation.md) | Pareja inglesa de la referencia de universo y worldgen. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Descubrimiento, navegación e intel](systems/discovery-navigation-intel.es.md) | Referencia canónica del conocimiento del jugador, scan, route solve, uplink, importación de intel, viaje, protección narrativa y failsafes. | **Verificado** contra código productivo y pruebas específicas. Distingue comportamiento implementado, una expectativa de fixture fallida y decisiones pendientes; actualmente no hay arcos activos. |
| [Discovery, navigation, and intel](systems/discovery-navigation-intel.md) | Pareja inglesa de la referencia de descubrimiento y navegación. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Scheduler de lore, arcos y singles](systems/lore-scheduler.es.md) | Referencia canónica de colocación narrativa, canales, forzado, pools, desbloqueos y contenido activo. | **Verificado** contra código productivo, datos activos y pruebas seguras. Distingue fixtures, contenido real y lagunas extremo a extremo; registra tres fixtures obsoletas sin modificar producto ni tests. |
| [Lore scheduler, arcs, and singles](systems/lore-scheduler.md) | Pareja inglesa de la referencia del scheduler narrativo. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Failsafes de exploración, deadnodes y recuperación](systems/exploration-failsafes.es.md) | Referencia canónica de recuperación global, deadnodes, nodos ad hoc de lore, guardrails y fallbacks auxiliares. | **Verificado** contra código productivo y pruebas aisladas. Separa garantías, riesgos funcionales y decisiones pendientes; no promete progresión global. |
| [Exploration failsafes, deadnodes, and recovery](systems/exploration-failsafes.md) | Pareja inglesa de la referencia de failsafes y recuperación. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Contrato de carga de contenido](content-loading.es.md) | Define qué rutas leen los loaders actuales de forma directa, no recursiva o recursiva; también inventaría las plantillas inactivas de arcos y localizaciones. | **Verificado** contra `src/retorno/runtime/data_loader.py`, `src/retorno/bootstrap.py`, `src/retorno/runtime/startup.py` y el árbol de datos en el commit `2ffb1ab`. |
| [Content loading contract](content-loading.md) | Pareja inglesa del contrato de carga. | **Verificado**; se mantiene como pareja lingüística del documento español. |

## Guías existentes

| Documento | Finalidad | Estado y limitaciones |
| --- | --- | --- |
| [Arcos y `corridor_01.json`](arcs.es.md) / [EN](arcs.md) | Guía de autoría de arcos y singles. | **Pendiente de revisión.** Conserva ejemplos de esquema reutilizables, pero apunta a contenido inactivo y describe rutas de colocación, garantías de `force`, alcance de protección y pesos de singles obsoletos. No debe tratarse como arquitectura vigente. |
| [Cómo se obtiene intel y lore](intel_lore.es.md) / [EN](intel_lore.md) | Resumen de fuentes de intel y lore visibles para el jugador. | **Pendiente de revisión.** Las secciones de scan e importación conservan material útil, pero la sintaxis de comandos, el flujo de arcos, los enlaces y los pesos de singles necesitan corrección. |
| [Guía de la UI Textual](textual.es.md) / [EN](textual.md) | Paneles, atajos, foco y autocompletado. | **Parcialmente verificado.** La auditoría inicial no encontró una discrepancia concreta, pero no se revalidó de forma exhaustiva durante esta fase de carga de contenido. |
| [Manuals style guide](manuals_style_guide.md) | Estructura y convenciones bilingües de los manuales diegéticos de `data/manuals/`. | **Guía normativa.** No describe comportamiento de ejecución. |

## Límites documentales

- `readme.md` y `readme.es.md` son las entradas del proyecto y resumen
  instalación y comandos. Su paridad completa de comandos sigue pendiente de
  revisión.
- `data/manuals/` contiene los manuales diegéticos cargados en el filesystem del
  juego; es contenido de ejecución, no un sustituto de la documentación
  técnica.
- `data/lore/` contiene recursos narrativos. La mayoría solo se carga mediante
  referencias explícitas desde contenido activo o mediante un loader dedicado.
- `BUGS.md`, `TODO.md`, `DONE.md` y `borrame.md` son notas de trabajo o
  históricas. No son descripciones normativas del comportamiento vigente.

## Trabajo documental previsto

Las referencias canónicas del scheduler y de failsafes ya reconstruyen la
implementación unificada y sus límites de recuperación. Las fases posteriores
deberán usarlas para revisar las guías históricas de arcos y lore y añadir una
matriz de verificación global que relacione comportamiento y pruebas. Las
propuestas deberán mantenerse separadas de los documentos sobre comportamiento
implementado.
