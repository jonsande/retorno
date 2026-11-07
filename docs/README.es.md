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
| [Universo físico y generación procedural](systems/world-generation.es.md) | Referencia canónica del modelo espacial, regiones, sectores, worldgen, topología, contenido authored y determinismo. | **Verificado** para la integración 4D-3e2 en el árbol basado en `5cdde28`, pendiente de revisión externa. Documenta las lagunas conocidas y el efecto materializador del diagnóstico de sector; no cubre en profundidad navegación, lore o failsafes. |
| [Physical universe and procedural generation](systems/world-generation.md) | Pareja inglesa de la referencia de universo y worldgen. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Descubrimiento, navegación e intel](systems/discovery-navigation-intel.es.md) | Referencia canónica del conocimiento del jugador, scan, route solve, uplink, importación de intel, viaje, protección narrativa y failsafes. | **Verificado** contra código productivo y pruebas específicas, incluidas las caracterizaciones reparadas de breadcrumb y route solve por id físico no descubierto; actualmente no hay arcos activos. |
| [Discovery, navigation, and intel](systems/discovery-navigation-intel.md) | Pareja inglesa de la referencia de descubrimiento y navegación. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Scheduler de lore, arcos y singles](systems/lore-scheduler.es.md) | Referencia canónica de colocación narrativa, canales, forzado, pools, desbloqueos y contenido activo. | **Verificado** contra código productivo, datos activos y pruebas seguras. Las tres fixtures históricas están reparadas con contenido sintético; no se activan templates. |
| [Lore scheduler, arcs, and singles](systems/lore-scheduler.md) | Pareja inglesa de la referencia del scheduler narrativo. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Failsafes de exploración, deadnodes y recuperación](systems/exploration-failsafes.es.md) | Referencia canónica de recuperación global, deadnodes, nodos ad hoc de lore, guardrails y fallbacks auxiliares. | **Verificado** contra código productivo y pruebas aisladas. Separa garantías, riesgos funcionales y decisiones pendientes; no promete progresión global. |
| [Exploration failsafes, deadnodes, and recovery](systems/exploration-failsafes.md) | Pareja inglesa de la referencia de failsafes y recuperación. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Contrato de carga de contenido](content-loading.es.md) | Define qué rutas leen los loaders actuales de forma directa, no recursiva o recursiva; también inventaría las plantillas inactivas de arcos y localizaciones. | **Verificado** contra `src/retorno/runtime/data_loader.py`, `src/retorno/bootstrap.py`, `src/retorno/runtime/startup.py` y el árbol de datos en el commit `2ffb1ab`. |
| [Content loading contract](content-loading.md) | Pareja inglesa del contrato de carga. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Auditoría transversal y plan de estabilización](testing/stabilization-audit.es.md) | Matriz ejecutiva de defectos, riesgos y decisiones; dependencias, prioridades, fixtures y batería mínima de integración. | **Verificado** contra las referencias canónicas, código productivo, pruebas existentes y sondas aisladas. Es un plan de ingeniería, no una modificación de mecánicas. |
| [Cross-system audit and stabilization plan](testing/stabilization-audit.md) | Pareja inglesa de la auditoría transversal. | **Verificado**; se mantiene como pareja lingüística del documento español. |
| [Contrato de diseño de navegación y recuperación](design/navigation-recovery-contract.es.md) | Decisiones aprobadas para rutas, recuperación, `comms`/`radiod`, recepción, servicios, protección narrativa, localización y saves prealfa; incluye matrices y plan 4C. | **Contrato aprobado**; distingue comportamiento vigente, divergencias y trabajo futuro. No declara implementadas las correcciones. |
| [Navigation and recovery design contract](design/navigation-recovery-contract.md) | Pareja inglesa del contrato de diseño. | **Verificado**; se mantiene como pareja lingüística del documento español. |

Fase 4D-3e2: [Integración del worldgen histórico](design/historical-worldgen-integration.es.md) /
[EN](design/historical-worldgen-integration.md) documenta la implementación productiva,
identidades, consulta física inversa completa en dominio certificado, topología, saves,
comparación y límites. Véase el [informe de revisión](testing/manifest-integration-review.es.md).
Los documentos e1/e1b siguientes conservan evidencia histórica; e4/e5 siguen pendientes; la memoria e3 se documenta a continuación.

Fase 4D-3e3: [Memoria de observaciones de scan](systems/discovery-navigation-intel.es.md#memoria-de-observaciones-4d-3e3) /
[EN](systems/discovery-navigation-intel.md#observation-memory-4d-3e3): historial persistente
de 128 barridos, evidencia negativa no concluyente y detección/RNG vigentes conservados.
[Informe para revisión](testing/scan-observation-review.es.md). No implementa F-DEAD-01
ni la compilación narrativa D21–D24, que sigue en e4.

## Guías existentes

Fase 4D-3e1: [Preexistencia procedural](design/procedural-preexistence.es.md) /
[EN](design/procedural-preexistence.md) documenta el catálogo acotado de sólo lectura,
dependencias del orden de worldgen demostradas y trabajo pendiente e2/e3/e4.
Es una implementación parcial segura: identidad muestral condicional no significa
existencia latente verificada ni activa F-DEAD-01.

Fase 4D-3e1b: [Manifiesto procedural estable](design/stable-procedural-manifest.es.md)
/ [EN](design/stable-procedural-manifest.md) contiene el contrato y prototipo
puro de identidad/topología independiente del orden, comparación de diez semillas
y decisiones pendientes para e2. La certificación pertenece a las reglas
experimentales; no sustituye worldgen ni activa lore, intel o F-DEAD-01. El orden
de integración vigente lo fija la hoja de ruta, no el reparto provisional de e1.

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

La auditoría transversal y el contrato fijan la secuencia de estabilización.
Fase 4C-1 ya impide que `uplink_only` consuma un primary sin producir un efecto
válido y conserva reintentos sin reabrir el pool de rutas. Las fases posteriores
deberán mantener la matriz, la paridad EN/ES y la separación entre comportamiento
implementado y propuestas.

- [IDs públicos de localización](systems/public-location-ids.es.md): referencias operativas compactas, resolución y evidencia histórica original.
- [Investigación de bloqueos exploratorios](design/exploration-softlock-research.es.md): objetivo de continuidad, límites de F-DEAD-01 nivel 1, criterios de validación y nivel 2 aplazado.
