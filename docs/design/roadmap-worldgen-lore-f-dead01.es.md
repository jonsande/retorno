# RETORNO — Hoja de ruta de preexistencia procedural, lore y F-DEAD-01

**Versión:** 1.0 — 2026-11-05  
**Estado:** planificación acordada; no constituye afirmación de implementación de las fases futuras.  
**Destino recomendado en el repositorio:** `docs/design/roadmap-worldgen-lore-f-dead01.es.md`.

> **Propósito:** conservar las decisiones de diseño y la secuencia de trabajo durante la estabilización final del universo procedural, sin prolongarla indefinidamente ni perder el objetivo de volver a jugar RETORNO con Textual y sonido, y después desarrollar arcos, singles y contenido nuevo.
>
> **Precedencia:** esta hoja documenta decisiones de producto y coordinación. No reemplaza `docs/canon/universo.md`, `docs/canon/guia_coherencia.md`, los contratos técnicos existentes ni el código probado. Las discrepancias entre documentos o cambios de mecánica se deben señalar para decisión del desarrollador; no resolver por suposición.

## 1. Punto de partida y estado verificable

- **Finalizadas y confirmadas anteriormente:** 4D-1 (rutas operativas y cap físico), 4D-2 (waypoints al abortar), 4D-3b (planificador puro), 4D-3c (rodeos físicos), 4D-3d (comparación contextual). El failsafe productivo antiguo de `src/retorno/core/deadnodes.py` **aún no utiliza** el nuevo planificador.
- **4D-3e1 — catálogo consultivo:** Codex entregó `src/retorno/worldgen/catalog.py`, extracción del muestreador común, pruebas de caracterización y documentación EN/ES. La revisión posterior lo **aprobó para commit**, pero **no consta en esta conversación una confirmación posterior del commit/push**. Verificar `git status`, `git log` y `origin/main` antes de comenzar la siguiente orden.
- **Hallazgo determinante:** la generación procedural actual no es completamente independiente del orden de generación: guardrail inicial, desbordamiento Z/cupos, identidades en colisiones y enlaces intersectoriales. El catálogo 4D-3e1 ofrece hechos físicos existentes y **muestras condicionales**, pero todavía no certifica emplazamientos latentes como existentes.
- **Baseline conocido antes de 4D-3e1:** `dd5b471` (actualización de audio), después de `6ae813e` (documentos canónicos) y `10a092f` (4D-3d). No tratar este SHA como HEAD actual sin comprobarlo.

## 2. Decisiones aprobadas — contrato de producto

| ID | Decisión vinculante |
| --- | --- |
| **D01 — Mundo preexistente** | Las estaciones, relés, pecios e instalaciones **históricas** deben tener existencia/identidad regidas por una definición independiente del failsafe, del scheduler narrativo y del orden de exploración. El cálculo y la materialización pueden ser *lazy*; no pueden fabricar retrospectivamente el pasado. |
| **D02 — Cuatro capas** | Separar (a) emplazamiento determinado por el universo, (b) nodo físico materializado, (c) conocimiento/intel del jugador y (d) ruta operativa publicada. Conocer una estación no implica conocer o poder usar una ruta. |
| **D03 — Manifiesto** | Adoptar como objetivo arquitectónico un **manifiesto procedural estable** (semilla + versión/reglas + base authored), consultable por sectores, sin construir toda la galaxia ni crear miles de objetos activos al inicio. La forma concreta debe verificarse con pruebas. |
| **D04 — Topología coherente** | Identidades, posición, tipo, reglas de hubs y conexiones históricas no deben cambiar arbitrariamente por el orden de las consultas. Mantener el límite de **45 años luz por salto** y la distinción entre grafo físico y `known_links`. No imponer conectividad universal. |
| **D05 — Exploración incierta** | Un `scan` negativo **no demuestra ausencia**. Los sensores pueden pasar por alto ubicaciones, especialmente si están degradados. Se acepta la exploración repetida/fiabilidad acumulada, pero no una rutina obligatoria de pulsar `scan` indefinidamente. Guardar historial de observaciones. |
| **D06 — F-DEAD-01, ámbito** | Resuelve bloqueos **estructurales de exploración** —existencia, topología, descubribilidad—, no la supervivencia. **No** descartar candidatos por scrap, energía, combustible, reparaciones, deterioro de nave o posibilidad de sobrevivir al viaje. |
| **D07 — Búsqueda progresiva** | Priorizar oportunidades próximas a la **posición actual** por camino dirigido completo; si no aparecen, ampliar gradualmente distancia y alcance de búsqueda. Ninguna distancia máxima rígida debe descartar para siempre la única salida legítima. El agotamiento de presupuesto computacional significa «búsqueda incompleta», nunca «no hay salida». |
| **D08 — Sin rescate garantizado** | El failsafe no teletransporta, no regala objetos, no inventa estaciones, no publica saltos imposibles ni garantiza un final favorable. Una derrota por falta de recursos es válida; no debe confundirse con un bloqueo estructural causado por errores del mundo. |
| **D09 — Fuentes de lore** | El scheduler puede decidir **qué contenido** aparece, **dónde** se asigna y **cuándo/cómo** se entrega, pero no crear instalaciones históricas para alojarlo. El *placement* puede ser dinámico; la existencia física, no. |
| **D10 — Arcos y singles** | Preservar en la medida posible formatos/semántica actuales: `primary_intel`, `secondary_lore_docs`, reglas, `force`, restricciones, canales, pesos y ciclos de singles. Las piezas esenciales necesitan **oportunidades legítimas verificables**; las opcionales pueden no aparecer. Una oportunidad disponible no garantiza que el jugador descubra el contenido. |
| **D11 — Nodos completados** | Nada de reabrir `node_pools`, recomponer ficheros consumidos o introducir pistas históricas nuevas en estaciones ya agotadas. Preparar/reservar contenido antes de su primera oportunidad relevante de inspección. Nunca exigir retrocesos repetitivos a lugares ya limpiados. |
| **D12 — Intel** | `NODE` remite a un emplazamiento válido; `LINK` necesita validación geométrica y operativa; `SECTOR` aporta información regional; `COORD` representa coordenadas, **no** implica una estación. Intel incompleta o falsa puede existir como dato, sin convertirse en enlace operativo imposible. |
| **D13 — Ad hoc** | Para lore forzoso y failsafes, sustituir la **creación histórica correctiva** por selección/reserva de emplazamientos preexistentes o canales narrativos legítimos. No prohibir sucesos dinámicos físicamente justificados en el futuro; distinguirlos explícitamente de instalaciones antiguas. |
| **D14 — Narrativa protegida** | Respetar primaries protegidos y las excepciones deliberadas de descubrimiento natural (`scan` y resolución manual válida). No filtrar secretos desde consultas internas del catálogo o la recuperación. |
| **D15 — Entrega diegética** | Separar oportunidad preparada, recepción/captura e importación/lectura. No conceder intel oculta solo porque el planificador encuentre un candidato. Las futuras `comms`/`radiod` tendrán sus puertas propias; no simular recepción gratuita mientras no estén implementadas. |
| **D16 — Rendimiento y partidas** | Presupuestos finitos, consultas acotadas, generación *lazy*, save/load, idempotencia. Las partidas anteriores son pruebas descartables: **no migraciones históricas complejas**, pero tampoco borrar guardados automáticamente. Versionar las reglas de worldgen para futuras partidas. |
| **D17 — Alcance del desarrollo** | Evitar ampliar la estabilización hacia balance exhaustivo, nuevas clases de estaciones, nueva UI/audio o sistema completo de sucesos dinámicos. Consultar al desarrollador ante decisiones de diseño importantes; Codex **no hará commit ni push**. |

## 3. Reglas específicas de distribución de contenido

### 3.1 Worldgen y manifiesto

- Las localizaciones *authored* forman parte de la base explícita del universo y tienen prioridad de identidad/ocupación según contrato validado.
- Los emplazamientos procedurales históricos se determinan por reglas/semilla/versionado independientes del orden de exploración; la materialización puede ser diferida.
- No asumir que un centro de sector o una muestra condicional de 4D-3e1 es una estación real.
- Coordinar con sectores de **10 años luz**, regiones físicas, posibles desbordamientos de coordenada Z, caps y conexión de hubs; no cambiar densidad por intuición.

### 3.2 Lore, arcos y singles

- La colocación de piezas puede continuar siendo probabilística, condicionada por región, distancia, tiempo, tipo, ventanas y canales.
- Arcos esenciales: comprobar de antemano que sus restricciones admiten **al menos una vía legítima de colocación/entrega** en las configuraciones relevantes. Esto no equivale a garantizárselas al jugador.
- Singles y piezas secundarias: conservar libertad para no aparecer, aparecer más adelante o quedar sin descubrir.
- Un contenido histórico nuevo no se inyecta retroactivamente en una fuente cuyo pool o posibilidad de recuperación ya se haya agotado. Se permiten señales o comunicaciones posteriores **si** su emisión, canal y recepción son legítimos.
- Proteger distinción entre *placement* (asignación), *preparation* (reserva de fuente/ventana) y *delivery* (recepción efectiva).

### 3.3 Intel y rutas

- La existencia física no revela `known_nodes` ni `known_links`.
- Importar una referencia solo materializa lo que ya es legítimo, cuando procede, y registra su procedencia.
- Las pistas indispensables se preparan en fuentes todavía aprovechables o mediante canales nuevos legítimos, sin forzar al jugador a reexaminar exhaustivamente regiones antiguas.
- Materializar una estación preexistente no debe duplicar salvage o archivos ni invalidar pools ya cerrados.

### 3.4 F-DEAD-01

- Buscar primero candidatos ya existentes físicamente o manifiestos legítimos cercanos; ampliar el ámbito cuando falten.
- Medir la proximidad por **acceso completo dirigido desde la nave** y cadena resultante, no por solo distancia en línea recta. Si no hay ruta válida, no afirmar acceso navegable.
- **No** usar como filtro de legitimidad: estado de energía, scrap, desgaste, reparaciones o recursos disponibles. Los datos de costes de 4D-3d pueden conservarse como informes externos, pero no decidir aceptación del failsafe.
- Si no hay candidato, dejar oportunidad pendiente y poder reintentar sin consumir recursos, contadores o cooldowns de «rescate exitoso».
- Una pista no es «recibida» hasta superar su canal real. No filtrar primaries ni publicar enlaces superiores a 45 ly.

## 4. Programa corto de implementación — seis encargos principales

**Meta de coordinación: 6 órdenes de Codex tras 4D-3e1, con una 7.ª reservada solo para defectos bloqueantes.** Es una meta de alcance, no garantía de que todos los casos quedarán resueltos en exactamente siete órdenes. Reducir trabajo de alcance no crítico antes de multiplicar fases; jamás sacrificar integridad de partida o afirmaciones de diseño falsas.

| Orden | Identificador de trabajo | Entrega obligatoria | Criterio de salida |
| --- | --- | --- | --- |
| **1** | **4D-3e1b — Contrato de manifiesto** | Diseño verificable y prototipo puro: identidad, generación-sector vs sector físico, authored, guardrail, colisiones, Z, conexiones estables; baterías comparativas de semillas/órdenes y distribuciones. Sin sustituir worldgen. | Especificar qué será independiente del orden y demostrarlo en el prototipo; decisiones de balance explícitamente pendientes. |
| **2** | **4D-3e2 — Integración de worldgen** | Implementación productiva por manifiesto, generación *lazy*, IDs/topología, versionado de algoritmo, límites de materialización, tests de guardado y comparación estadística de mapas. | Igual semilla/configuración produce mismo universo histórico/topología independiente del orden; no leaks de conocimiento ni cambios silenciosos de balance. |
| **3** | **4D-3e3 — Memoria de scan** | Registro persistente y acotado de observaciones (posición, alcance efectivo, estado de sensores, resultados y tiempo), modelo de evidencia negativa no infalible y pruebas; evitar repetición compulsiva. | Scan normal e historial sobreviven save/load; escaneos negativos no certifican vacío; sensores degradados se tratan conforme al contrato actual salvo cambio aprobado. |
| **4** | **4D-3e4 — Lore/intel/ad hoc** | Adaptar selección de hosts, reservas de contenido esencial, `NODE/LINK/SECTOR/COORD`, fuentes no consumidas; eliminar creación retrospectiva de instalaciones antiguas por piezas forzosas. Tests de arcos/singles y primaries. | No se abre un pool agotado, no se crea una estación por necesidad de lore y las piezas esenciales disponen de validación de viabilidad sin revelación gratuita. |
| **5** | **4D-3e5 — F-DEAD-01** | Integrar selector contextual con manifiesto, búsqueda próxima que se amplía progresivamente, condiciones estructurales sin filtros económicos, preparación atómica e idempotente de pistas, distinción pendiente/recibida, validaciones de navegación y protección. | Sin salto >45 ly, sin rescate gratuito ni estación retrospectiva; intentos fallidos no consumidos; la búsqueda agotada es «incompleta» y la recepción respeta canales reales. |
| **6** | **4D-3e6 — Validación jugable y cierre** | Regresión integrada, varios universos/semillas, save/load repetido, casos de fallo, prueba con controles públicos en Textual y **sonido**, informe de experiencia y defectos. | Recorrido jugable estable; cerrar F-DEAD-01 solo con evidencias. Volver a producir arcos, singles y contenido tras bloquear únicamente defectos graves. |

**Orden 7 opcional:** correcciones de bloqueos detectados en 2–6; no es una invitación a perfeccionar el motor indefinidamente. Si la orden 5 exige una separación por seguridad de materialización y recepción, usar la reserva disponible y ajustar el cierre.

**Dependencias críticas:** no consumir muestras `conditional` del catálogo como emplazamientos históricos certificados antes de cerrar 1–2. No forzar la migración de `scan` antes de disponer del contrato físico estable. La adaptación de lore y de deadnodes debe usar la misma noción de preexistencia.

## 5. Comprobaciones mínimas antes de cerrar cada orden

1. Leer `AGENTS.md`, canon y documentos técnicos relevantes; verificar `git status`, rama y SHA antes de tocar código.
2. Delimitar el alcance. Si hace falta cambiar densidades, probabilidades, recursos, política de guardrail, formato de arcos o canales, **detener la decisión sustantiva y consultar**.
3. Pruebas nuevas + smoke tests de worldgen, generación de lore, intel, route solve, deadnodes, save/load; ampliar matriz si cambia un contrato.
4. Verificar determinismo entre procesos/orden de materialización, ausencia de alteraciones ilegítimas de `known_nodes/known_links`, fuentes agotadas y objetivos narrativos protegidos.
5. Distinguir «verificado», «condicional», «no evaluado por presupuesto», «pendiente de entrega» y «no válido».
6. Reporte claro de cambios por archivo, pruebas ejecutadas, limitaciones; ZIP solo con archivos cambiados/nuevos y rutas relativas; `git diff --check`; **sin `git add`, commit ni push** por Codex.
7. Revisión externa por ChatGPT y commit/push manual del desarrollador tras aprobar los cambios.

## 6. Qué queda deliberadamente fuera del hito

- Nuevos arcos y singles completos (se retoman al acabar este hito, pero se pueden **diseñar** antes sin integrarlos).
- Nuevas clases de instalaciones y reajustes generales de densidad, loot o recursos sin evidencia.
- Sistema complejo de triangulación y múltiples modos de sensores; basta un historial honesto y verificable.
- Simulación completa de sucesos dinámicos futuros, combate u otros sistemas ajenos.
- Revisión integral de todo el contenido antiguo no afectado por la preexistencia.
- Desarrollo completo de comunicaciones `comms`/`radiod` fuera de su plan específico. **Si su ausencia impide la recepción diegética de F-DEAD-01, no simularlas ni declarar la fase cerrada**: usar únicamente un canal legítimo ya implementado o elevar el mínimo imprescindible como dependencia explícita para decisión.
- Migraciones de partidas de prueba antiguas; no borrar guardados sin acción explícita.

## 7. Riesgos y señales de parada

- **Rehacer worldgen afecta distribución:** exigir comparación de muchas semillas, colas de dispersión, rutas aisladas y origen jugable; un manifiesto determinista no garantiza buen juego.
- **Nodos authored y generación Z:** no cambiar reglas por comodidad; cuantificar el efecto del desbordamiento y acordar política antes de corregirlo.
- **Topología dependiente de vecino:** no reconstruir enlaces pasados de forma retroactiva ni depender del orden en que el jugador solicite los sectores.
- **Arcos esenciales con restricciones imposibles:** reportar y validar capacidad de alojamiento; no forzar instalaciones nuevas como solución automática.
- **Recuperación vs supervivencia:** separar criterios estructurales de gates que afectan a la capacidad efectiva de ejecución de una acción. Estos últimos pueden seguir rigiendo el viaje o la recepción, pero **no la legitimidad de un candidato**.
- **Escaneos repetidos:** si se convierten en obligación mecánica tediosa, replantear el feedback antes de aumentar complejidad.
- **Falsos «sin salida»:** el agotamiento técnico no es prueba de imposibilidad ni justificación de game over.

## 8. Regla de salida hacia el contenido

Tras 4D-3e6, hacer una **partida real con interfaz Textual y sonido**, desde una partida nueva, usando controles públicos. Documentar defectos reproducibles. Corregir primero los que impidan progresar, corrompan estado/guardados, revelen intel protegida o rompan reglas físicas.

El resto pasa a un backlog posterior. **Retomar creación y distribución de arcos, singles, localizaciones authored y contenido narrativo**. No posponerlo por refinamientos cosméticos del generador.

## 9. Cómo utilizar esta hoja de ruta en conversaciones nuevas

Al iniciar otra conversación dentro del proyecto RETORNO:

- Adjuntar esta hoja o señalar su ruta ya confirmada en el repositorio.
- Indicar la última orden ejecutada, el commit aprobado y la salida de Codex, si existe.
- Pedir explícitamente que no se confunda «aprobado» con «implementado» y que no se inventen decisiones ausentes.
- Continuar **una sola orden de Codex por ciclo**: prompt -> ejecución -> informe/ZIP -> revisión -> commit/push manual -> siguiente orden.
- Antes de iniciar la siguiente etapa, comprobar si **4D-3e1 está efectivamente confirmada en Git**.

**Próxima acción al aprobar esta hoja:** comprobar el commit de 4D-3e1 y preparar **4D-3e1b**, contrato/prototipo del manifiesto procedural estable, sin sustitución productiva prematura.
