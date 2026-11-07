## 4D-3e5c-B2 — implementada para revisión externa

[historical-radio-v1](../systems/historical-radio.es.md) separa hardware original, conservación, energía, programación y ondas en propagación. Reutiliza manifiesto, B1, física y ledger de recepción; authored explícito prevalece para todo su host. Se implementan descubrimiento lazy local, persistencia y fuentes certificadas para F-DEAD-01. La reparación física excepcional y la validación e6 prolongada quedan pendientes. Las menciones inferiores a B2 pendiente describen fases anteriores.

## 4D-3e5c-B1 — implementada para revisión externa

Las partidas nuevas usan [historical-information-v1](../systems/historical-information.es.md),
con archivos y registros navegacionales estables y finitos, conexiones históricas
y rutas calculadas tipadas, entrega protegida, validación aditiva estricta de
esquema 3 y reglas informativas legacy para toda la partida. B0 conserva sus
capacidades físicas. No cambian worldgen físico, políticas del scheduler, radio,
recursos ni audio. Esta actualización prevalece sobre el alcance editorial e5c
anterior. La versión 1.6 conserva D01–D24 literalmente. B2 queda pendiente:
transmisores/emisiones procedurales y una posible reactivación excepcional
requieren hardware original, conservación, energía, capacidad de reparación,
payload histórico, inicio real, propagación y trazabilidad persistida. No se
implementan emisiones retroactivas ni reparaciones. La validación jugable e6
prolongada de Textual/audio sigue separada.

## 4D-3e5b — implementada para revisión externa

El [modelo físico espacial/temporal](../systems/radio-spacetime.es.md) implementa
A2, B, C2, D y E: tres perfiles, potencia/sensibilidad, propagación a c, radio
pasiva automática y extensión optativa validada de emisores. F-DEAD-01 comparte
la frontera sin inventar emisiones históricas. Parámetros provisionales; sin
cambios de densidad, navegación, relojes completos o contenido de producción.
e5c mantiene la revisión editorial; e6 la validación prolongada Textual/audio.
D01–D24 se conservan. [Informe](../testing/radio-spacetime-review.es.md).


# RETORNO — Hoja de ruta de preexistencia procedural, lore y F-DEAD-01

**Versión:** 1.6 — 2026-11-06
**Estado:** 4D-3e5c-B1 implementada sobre `445217e` para revisión externa; B2/e6 pendientes. [English](roadmap-worldgen-lore-f-dead01.md).
**Destino recomendado en el repositorio:** `docs/design/roadmap-worldgen-lore-f-dead01.es.md`.

> **Propósito:** conservar las decisiones de diseño y la secuencia de trabajo durante la estabilización final del universo procedural, sin prolongarla indefinidamente ni perder el objetivo de volver a jugar RETORNO con Textual y sonido, y después desarrollar arcos, singles y contenido nuevo.
>
> **Precedencia:** esta hoja documenta decisiones de producto y coordinación. No reemplaza `docs/canon/universo.md`, `docs/canon/guia_coherencia.md`, los contratos técnicos existentes ni el código probado. Las discrepancias entre documentos o cambios de mecánica se deben señalar para decisión del desarrollador; no resolver por suposición.

## Intervención aprobada e implementada v1.5 — 4D-3e5a

Después del F-DEAD-01 publicado en `343829e`, se incorpora `C-DATA-004`, la regla
operativa en AGENTS y «¿Cómo sabe esto la nave?». Se retiran filtraciones de
`status`/`diag comms` y `ship survey`; debug explícito conserva el acceso interno.
Pruebas negativas comparativas EN/ES, CLI/Textual y preservación de información
adquirida: [informe](../testing/knowledge-boundary-review.es.md).
No cambia selector, mundo, ledger, RNG, persistencia, audio ni D01–D24.
**4D-3e5b** sigue separada: alcance físico, tipos de emisores, potencia,
sensibilidad y propagación temporal simplificada. No se implementa en e5a.
e6, validación jugable prolongada con Textual y sonido, sigue pendiente.

## Estado implementado v1.4 — 4D-3e5

Base `ba705e7` (Tweaks íntegro). F-DEAD-01 implementado para revisión externa: selección histórica acotada, ampliación, preparación atómica y pistas progresivas por radio/salvamento. Véanse [contrato](../systems/structural-recovery.es.md) e [informe](../testing/structural-recovery-review.es.md). D01–D24 permanecen literalmente intactas. Los apartados anteriores de coordinación y auditorías conservan su contexto histórico; la entrega e5 prevalece sobre sus referencias a activación aplazada. e6, validación jugable con Textual y sonido, queda pendiente.

## Acuerdo explícito adicional v1.3

El desarrollador autoriza intercalar **4D-3e4b — comunicaciones pasivas** antes de
4D-3e5. Es una intervención adicional acotada, no la reserva de correcciones ni
una declaración de F-DEAD-01 terminado. Implementa comms/radiod, oportunidades
persistentes, captura local y lectura, avisos, compatibilidad de guardado y
pruebas EN/ES. Consumo nominal provisional autorizado: 0.15 kW. Véanse
[contrato](../systems/passive-communications.es.md) e
[informe](../testing/passive-communications-review.es.md).

No se reescriben D01–D24 ni los criterios de e5/e6. Se aplazan explícitamente las
activaciones legacy que necesitan fabricar nodos correctivos; la recuperación
estructural y su selección permanecen en e5. Las referencias siguientes a e2 en
curso y al procedimiento v1.1→v1.2 conservan su contexto histórico de coordinación,
no describen el estado actual del checkout. La tabla incorpora la intervención.

## 1. Punto de partida y estado verificable

- **Finalizadas y confirmadas anteriormente:** 4D-1 (rutas operativas y cap físico), 4D-2 (waypoints al abortar), 4D-3b (planificador puro), 4D-3c (rodeos físicos), 4D-3d (comparación contextual). El failsafe productivo antiguo de `src/retorno/core/deadnodes.py` no utilizaba todavía el nuevo planificador en la última revisión; comprobar su estado en el código actual.
- **4D-3e1 — catálogo consultivo:** Codex entregó `src/retorno/worldgen/catalog.py`, extracción del muestreador común, pruebas de caracterización y documentación EN/ES. La revisión anterior lo aprobó para commit; el SHA final no está registrado en esta hoja.
- **4D-3e1b — contrato/prototipo:** figura como trabajo previo previsto en esta hoja. **No se afirma aquí que su entrega esté aprobada o integrada**: verificar el informe y el historial del repositorio en la conversación de implementación.
- **4D-3e2 — integración productiva de worldgen:** **Codex ya está ejecutando esta orden** al aprobarse la versión 1.2. No interrumpir esa ejecución ni alterar en caliente su prompt. Revisar la entrega frente a las decisiones nuevas y programar únicamente la adaptación indispensable que no estuviera contemplada.
- **Hallazgo de partida:** el worldgen anterior no era completamente independiente del orden de generación (guardrail inicial, desbordamiento Z/cupos, colisiones de ID y enlaces intersectoriales). El catálogo 4D-3e1 distinguía hechos físicos de muestras condicionales; verificar qué cambia realmente tras 4D-3e2.
- **Referencia histórica, no HEAD actual:** `dd5b471` (audio), `6ae813e` (canon) y `10a092f` (4D-3d). Usar `git log`, `git status`, rama y upstream actuales antes de cualquier operación.
- **Decisión adicional durante 4D-3e2:** los **requisitos narrativos estructurados** de todos los arcos, singles y documentos instalados deben constituir una entrada de la construcción del universo de cada nueva partida (§2 y §3.4). Esta decisión es **objetivo de arquitectura pendiente de implementar/verificar**, no una característica ya funcional del generador.

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
| **D18 — Autoría y semántica** | **Preservar la capacidad de crear estaciones, pecios y lugares expresamente diseñados para arcos/singles**, declarados como localizaciones *authored* integradas en la definición física del universo antes de exponerlas al jugador. **Mencionar** un lugar en prosa no equivale a **declararlo**, y **declararlo** no equivale a **revelarlo**. No eliminar esta capacidad al sustituir ad hoc. |
| **D19 — Compatibilidad de sintaxis** | Mantener, siempre que sea técnicamente coherente, las instrucciones existentes `NODE:`, `LINK:`, `SECTOR:`, `COORD:`, los bloques de intel y las referencias *authored* reconocidas. Preservar su propósito sin fingir que todas crean estaciones; compatibilidad y diferencias respecto al comportamiento actual deben verificarse mediante tests. No introducir silenciosamente una nueva sintaxis o cambiar el formato de autoría sin consulta. |
| **D20 — Autoría de historias esenciales** | El contenido esencial necesita una definición y una comprobación de emplazamientos/canales elegibles **antes de que el jugador pueda consumir su fuente**. Reservar o vincular hosts preexistentes cuando proceda, sin reabrir pools ni garantizar descubrimiento; si las restricciones son imposibles, informar en validación de contenido, no improvisar una estación durante la partida. |
| **D21 — Worldgen condicionado por el lore** | **Antes de comenzar una nueva partida**, recopilar los requisitos espaciales vinculantes de los **arcos, singles y demás documentos/paquetes narrativos instalados**. El manifiesto de esa partida debe incorporar sus entidades y relaciones canónicas junto a la generación procedural, de manera que las pistas puedan conducir a lugares reales, estables y congruentes. No depender de leer la pista, activar el arco o generar un sector para decidir retroactivamente si el lugar existe. |
| **D22 — Declaraciones estructuradas y validación** | No inferir verdades físicas automáticamente de toda frase en prosa. Separar hechos canónicos explícitamente declarados, referencias a entidades, afirmaciones inciertas/engañosas y datos de intel que se revelarán en juego. Resolver identidades/alias, restricciones de tipo, ubicación, región, cercanía, rutas, cronología y contradicciones antes de iniciar la partida. Informar de errores de autoría de forma accionable, sin resolver conflictos creando nodos sobre la marcha. |
| **D23 — Autoría extensible** | Un diseñador debe poder añadir nuevos arcos y singles y sus requisitos físicos **sin modificar código del generador para cada historia**. Reutilizar formatos y guías existentes cuando sea viable; proponer cualquier esquema declarativo nuevo de forma **compatible y versionable**, sujeto a revisión antes de imponerlo. La inclusión de una historia en el catálogo de contenido no implica revelar su secreto ni garantizar que todas sus piezas narrativas aparezcan. |
| **D24 — Relaciones y pistas verificables** | No basta con que exista cada nombre: deben poder satisfacerse las relaciones espaciales que se hayan declarado (p. ej. pecio próximo a una estación, señal procedente de un relé, coordenadas coherentes), respetando topología, límites físicos y reglas de descubrimiento. Distinguir relación histórica, ruta física posible, ruta conocida por el jugador y pista aproximada o falsa. |


## 3. Reglas específicas de distribución de contenido

### 3.1 Worldgen y manifiesto

- Las localizaciones *authored* forman parte de la base explícita del universo y tienen prioridad de identidad/ocupación según contrato validado.
- **Entradas de worldgen al preparar una partida:** semilla, versión/reglas, base authored del universo, y **catálogo/versiones de contenido narrativo instalado con sus requisitos físicos estructurados**. Compilar/validar estas entradas y fijar un manifiesto estable antes de las oportunidades de exploración; la realización física sigue pudiendo ser *lazy*.
- La integración debe considerar tanto entidades singulares (naves, estaciones, pecios, relés, sectores, puntos de interés) como **relaciones** y restricciones narrativas declaradas (identidad, localización, proximidad, región, cronología y conectividad, cuando se exijan). «Una nave mencionada» no significa automáticamente «un pecio explorable».
- Una pieza de lore opcional puede no llegar a entregarse, pero cualquier **hecho físico canónico declarado como requisito del mundo** debe ser consistente con la partida. Distinguir el *world requirement* de la probabilidad de aparición del texto.
- La definición de manifiesto **no puede depender del orden de lectura de archivos, activación de arcos, exploración de sectores o descubrimiento de intel**. Establecer claves/IDs estables y política verificable ante conflictos de autoría; no inventar una política de prioridades silenciosa.

- Los emplazamientos procedurales históricos se determinan por reglas/semilla/versionado independientes del orden de exploración; la materialización puede ser diferida.
- No asumir que un centro de sector o una muestra condicional de 4D-3e1 es una estación real.
- Coordinar con sectores de **10 años luz**, regiones físicas, posibles desbordamientos de coordenada Z, caps y conexión de hubs; no cambiar densidad por intuición.

### 3.2 Lore, arcos y singles

- La colocación de piezas puede continuar siendo probabilística, condicionada por región, distancia, tiempo, tipo, ventanas y canales.
- Distinguir el **catálogo de contenido instalado** (declaraciones que condicionan el universo) de la **selección y distribución dinámica de documentos** durante la partida. Un single opcional no obliga a emitir su documento; sus requisitos físicos canónicos, si se incluyen en el manifiesto, sí deben respetarse.
- Los escritores deben poder expresar relaciones y pistas comprobables sin alterar a mano el código Python del generador. La especificación y el validador de contenido deben detectar referencias no resueltas, tipos incompatibles, condiciones geométricas imposibles y contradicciones antes de iniciar partida.

- Arcos esenciales: comprobar de antemano que sus restricciones admiten **al menos una vía legítima de colocación/entrega** en las configuraciones relevantes. Esto no equivale a garantizárselas al jugador.
- Singles y piezas secundarias: conservar libertad para no aparecer, aparecer más adelante o quedar sin descubrir.
- Un contenido histórico nuevo no se inyecta retroactivamente en una fuente cuyo pool o posibilidad de recuperación ya se haya agotado. Se permiten señales o comunicaciones posteriores **si** su emisión, canal y recepción son legítimos.
- Proteger distinción entre *placement* (asignación), *preparation* (reserva de fuente/ventana) y *delivery* (recepción efectiva).

### 3.3 Intel y rutas

- La existencia física no revela `known_nodes` ni `known_links`.
- Importar una referencia solo materializa lo que ya es legítimo, cuando procede, y registra su procedencia.
- Las pistas indispensables se preparan en fuentes todavía aprovechables o mediante canales nuevos legítimos, sin forzar al jugador a reexaminar exhaustivamente regiones antiguas.
- Materializar una estación preexistente no debe duplicar salvage o archivos ni invalidar pools ya cerrados.

### 3.4 Contrato explícito de autoría, referencias e intel (acuerdo posterior)

**Hay tres operaciones distintas; no confundirlas al refactorizar:**

1. **Declarar una localización:** incluir una estación, pecio o instalación explícitamente *authored* en la definición física del universo y establecer identidad/posición bajo reglas verificables **antes** de que el jugador pueda encontrarla. Esto debe seguir siendo posible para historias concebidas alrededor de un lugar con nombre propio, sin depender de que worldgen lo produzca casualmente. La forma exacta de declaración/registro debe auditarse frente a los formatos existentes; no se aprueba por este documento una sintaxis nueva.
2. **Referirse narrativamente a ella:** escribir en prosa que «la Estación Némesis desapareció». La mención por sí sola **no** crea una instalación ni revela sus coordenadas/ID operativos, aunque hay que preservar y probar los reconocedores específicos de referencias *authored* dentro de bloques de intel donde corresponda.
3. **Revelar información operativa:** una instrucción de intel reconocida modifica el conocimiento del jugador según su semántica y validación física. Puede citar una localización preexistente aún no materializada; el descubrimiento no crea una instalación histórica ex nihilo.

**Sintaxis existente cuya compatibilidad debe caracterizarse y preservarse:**

```text
NODE: NEMESIS_STATION
LINK: RELAY_08 -> NEMESIS_STATION
SECTOR: S+003_+002_+000
COORD: 35.2, 12.0, 0.5
```

Los identificadores del ejemplo son ilustrativos, **no** contenido ya declarado. Comportamiento conocido antes de la refactorización:

- `NODE:` incorpora una referencia de nodo al conocimiento; actualmente **no garantiza que el nodo físico exista**. Nuevo contrato deseado: una referencia legítima a un lugar histórico debe resolverse contra nodo *authored*/manifiesto o conservarse explícitamente como pista pendiente o errónea, sin afirmar falsamente la existencia ni otorgar navegación.
- `LINK:` importa una referencia de ruta; su publicación operativa exige extremos físicos y un salto válido (≤45 ly). Conservar pistas históricas incompletas o falsas sin publicar rutas imposibles.
- `SECTOR:` permite incorporar intel de sector y disparar generación *lazy* legítima, sin equivaler a revelar todos sus nodos.
- `COORD:` actualmente puede crear un `nav_point` (`NAV_...`), que **no es una estación histórica**. Preservar la funcionalidad de coordenadas navegables conforme al contrato; no convertirla automáticamente en instalación.
- Bloques `[INTEL]`/referencias a lugares authored: auditar expresamente resolución de nombres, alias e IDs, incluida la diferencia entre interpretación de intel y prosa normal. No prometer reconocimiento de nombres sin sintaxis/registro válido.

**Compatibilidad con arcos y singles:** preservar `primary_intel`, `secondary_lore_docs`, `placement_rules`, `constraints`, `channels`, `weight`, `force_policy` y sus semánticas existentes siempre que no contradigan las decisiones aprobadas. Un arco puede definir una estación propia para la historia; su ubicación física debe quedar fijada antes de la exploración, aunque la asignación o recepción del documento siga siendo procedural y pueda ser tardía bajo límites históricos. Una pieza forzosa debe seleccionar/reservar un host legítimo, no fabricarlo. Los singles opcionales no requieren garantizar aparición.

**Regresión end-to-end obligatoria antes de cerrar 4D-3e4:**

1. Declarar una estación *authored* para un arco y verificar que tiene identidad y emplazamiento físico estables desde la preparación de la partida (sin publicarlos al jugador).
2. Leer prosa que menciona esa estación y comprobar que no crea ni revela por sí sola un nodo; probar separadamente un bloque de intel que reconozca referencias authored.
3. Importar `NODE:` válido y comprobar descubrimiento de la estación correcta; ensayar ID inexistente, referencia pendiente y protección de primary.
4. Importar `LINK:` válido e inválido y comprobar los límites físicos y la publicación de ruta sin filtraciones.
5. Validar `SECTOR:` y `COORD:` (esta última crea/reutiliza punto de navegación, no una estación).
6. Ejecutar un arco con colocación forzosa y un single procedural sobre hosts existentes; no crear estaciones correctivas ni reabrir pools agotados.
7. Guardar/cargar varias veces y comprobar identidad, posición, intel conocida/desconocida, rutas y progreso narrativo, sin duplicados.
8. Ejecutar pruebas comparativas de formatos de contenido y procedimientos actuales de creación de arcos/singles; documentar cualquier incompatibilidad antes de cambiar guías.

**Documentación:** una vez implementado y probado, actualizar las guías prácticas de autoría y las referencias técnicas para explicar declaración, mención y revelación con **ejemplos ejecutables reales**, no sintaxis hipotética. Antes de 4D-3e4, las guías existentes no deben reescribirse como si las nuevas funciones ya estuvieran disponibles.

### 3.5 Contrato adicional: el contenido narrativo condiciona el universo (v1.2)

**Caso de uso rector:** un diseñador crea un arco sobre una estación abandonada llamada Némesis, la nave Ícaro desaparecida cerca de ella, un relé que registró una señal y documentos que contienen pistas espaciales. Al iniciar una partida nueva con ese contenido instalado, el universo debe contener los **hechos físicos canónicos declarados** (por ejemplo estación, pecio si se ha declarado como lugar explorable y relé), con identidades y relaciones coherentes. La lectura posterior de un documento puede descubrirlos, pero **no crearlos**.

**Canal de autoría propuesto como requisito, no como sintaxis ya aprobada o implementada:**

1. Mantener texto literario libre y las instrucciones de intel existentes para **revelaciones diegéticas**.
2. Disponer de una **declaración estructurada de requisitos de mundo** por paquete/arco/single, o un registro referenciado por ellos: tipos de entidad, IDs/alias, hechos físicos vinculantes, relaciones, restricciones y estatus narrativo (canónico, rumor, afirmación falsa o desconocida).
3. Compilar y validar el conjunto de declaraciones de todo el contenido instalado **antes de fijar el manifiesto de una partida nueva**. Reutilizar entidades authored comunes; rechazar o reportar ambigüedades y contradicciones no resueltas. La política de ubicación flexible/elección de semilla se decidirá con criterios explícitos y tests, no mediante excepciones por historia en el generador.
4. Combinar los requisitos con emplazamientos procedurales de forma determinista y estable, sin alterar silenciosamente densidades, rutas, límite de salto ni secretos. Puede reservarse una ubicación o fijarse una restricción sin cargar físicamente todos los sectores.
5. Mantener separadas **referencia narrativa → declaración canónica → manifestación física → conocimiento del jugador → ruta operativa**. Un documento puede contener nombres sin coordenadas, coordenadas aproximadas, datos falsos o información parcial; solo las reglas de intel determinan qué descubre el jugador.
6. Incorporar nuevos paquetes narrativos **en nuevas partidas** mediante datos de autoría; no reinterpretar silenciosamente el manifiesto de una partida ya empezada cuando cambian archivos o mods. Versionar/identificar el conjunto de contenido asociado al mundo guardado y definir conducta ante discrepancias.

**Ejemplos de intención, NO sintaxis ejecutable:**

- `NEMESIS_STATION` es una estación histórica, existente pero desconocida al inicio.
- `ICARO_WRECK` es un pecio físico cuya posición debe satisfacer una relación *cerca de* Némesis, dentro de los límites que se definan formalmente.
- `RELAY_08` es fuente de una señal histórica, pero recibir el mensaje requiere un canal implementado y legítimo.
- Un informe que solo diga «la Ícaro desapareció» **no** declara necesariamente un pecio localizable; un informe deliberadamente erróneo no obliga a falsear el manifiesto.

**Pruebas de aceptación adicionales para la integración de contenido (4D-3e4, con comprobaciones del contrato desde 4D-3e2):**

1. Dos paquetes narrativos independientes, instalados simultáneamente, definen entidades y relaciones compatibles; el mismo seed/config/conjunto de contenido produce idéntico manifiesto aunque cambien el orden de carga, activación y exploración.
2. Una nueva historia con estación, pecio y relé propios se incorpora **mediante datos**, sin modificar el generador; las relaciones canónicas se satisfacen o se comunica una validación fallida.
3. Una referencia a entidad inexistente, un alias ambiguo y dos requisitos espaciales incompatibles generan diagnósticos concretos **antes de jugar**; no una reparación ad hoc en mitad de la partida.
4. Prosa normal, rumor y afirmación falsa no producen estaciones ni revelaciones; `NODE`, `LINK`, `SECTOR`, `COORD` y bloques intel mantienen su semántica real sin confundir existencia física y conocimiento.
5. Un contenido opcional no emitido no causa una sorpresa retrospectiva: si su requisito físico fue declarado como canónico, permanece estable; si es solo una posibilidad narrativa, no se convierte automáticamente en instalación física.
6. Guardar/cargar preserva identidad/versión del mundo y del contenido instalado. La alteración posterior del catálogo de historias no cambia silenciosamente los hechos históricos de la partida ya iniciada.
7. Se mide el impacto de la incorporación authored sobre densidad, colisiones, hubs y navegabilidad para varias semillas. **No** prometer integración de cualquier conjunto contradictorio.

**Límite del hito:** no construir ahora un editor visual, un parser libre de lenguaje natural ni un sistema general de mods. Diseñar la interfaz de datos mínima y verificable que sostenga autoría futura, y completarla cuando corresponda a lore/intel.

### 3.6 F-DEAD-01

- Buscar primero candidatos ya existentes físicamente o manifiestos legítimos cercanos; ampliar el ámbito cuando falten.
- Medir la proximidad por **acceso completo dirigido desde la nave** y cadena resultante, no por solo distancia en línea recta. Si no hay ruta válida, no afirmar acceso navegable.
- **No** usar como filtro de legitimidad: estado de energía, scrap, desgaste, reparaciones o recursos disponibles. Los datos de costes de 4D-3d pueden conservarse como informes externos, pero no decidir aceptación del failsafe.
- Si no hay candidato, dejar oportunidad pendiente y poder reintentar sin consumir recursos, contadores o cooldowns de «rescate exitoso».
- Una pista no es «recibida» hasta superar su canal real. No filtrar primaries ni publicar enlaces superiores a 45 ly.

## 4. Programa corto de implementación — seis encargos principales

**Meta de coordinación: 6 órdenes de Codex tras 4D-3e1, con una 7.ª reservada solo para defectos bloqueantes.** Es una meta de alcance, no garantía de que todos los casos quedarán resueltos en exactamente siete órdenes. Reducir trabajo de alcance no crítico antes de multiplicar fases; jamás sacrificar integridad de partida o afirmaciones de diseño falsas.

| Orden | Identificador de trabajo | Entrega obligatoria | Criterio de salida |
| --- | --- | --- | --- |
| **1** | **4D-3e1b — Contrato de manifiesto** | Diseño verificable y prototipo puro: identidad, generación-sector vs sector físico, authored, guardrail, colisiones, Z, conexiones estables; conservar la posibilidad de estaciones *authored* para arcos y singles y la separación entre declarar/mencionar/revelar; baterías comparativas de semillas/órdenes y distribuciones. Sin sustituir worldgen. | Especificar qué será independiente del orden y demostrarlo en el prototipo; decisiones de balance explícitamente pendientes. |
| **2** | **4D-3e2 — Integración de worldgen (EN CURSO al redactar v1.2)** | Implementación productiva por manifiesto, generación *lazy*, IDs/topología, coexistencia con ubicaciones *authored*, versionado de algoritmo, límites de materialización, tests de guardado y comparación estadística de mapas. **Revisar a la entrega la extensibilidad para requisitos narrativos declarativos; no alterar el prompt en ejecución.** | Igual semilla/configuración produce mismo universo histórico/topología independiente del orden; no leaks de conocimiento ni cambios silenciosos de balance. **La compilación completa de paquetes de lore no se presume terminada en esta orden.** |
| **3** | **4D-3e3 — Memoria de scan** | Registro persistente y acotado de observaciones (posición, alcance efectivo, estado de sensores, resultados y tiempo), modelo de evidencia negativa no infalible y pruebas; evitar repetición compulsiva. | Scan normal e historial sobreviven save/load; escaneos negativos no certifican vacío; sensores degradados se tratan conforme al contrato actual salvo cambio aprobado. |
| **4** | **4D-3e4 — Lore/intel/ad hoc** | Implementar el mínimo **contrato de datos + compilación/validación de requisitos físicos de arcos/singles/documentos instalados antes de la nueva partida**, integrado con el manifiesto; adaptar hosts, reservas y declaraciones authored; preservar/verificar `NODE/LINK/SECTOR/COORD`, bloques intel y mención frente a revelación; retirar creación retrospectiva. Ejecutar §3.4 y §3.5; revisar las guías de autoría. | Historias nuevas pueden declarar entidades/relaciones **sin tocar código del generador**; se validan contradicciones; el universo es consistente con pistas canónicas; no se reabren pools ni se crea una estación por necesidad tardía, y la sintaxis intel sigue operativa. |
| **4b adicional** | **4D-3e4b — Comunicaciones pasivas (acuerdo v1.3)** | Sistema físico comms, radiod, recepción local persistente e idempotente, lectura/importación, gates reales, avisos y pruebas/documentación EN/ES. Aplazar activaciones legacy que fabrican nodos; no rehacer F-DEAD-01. | Receptor/servicio reales, sin capturas gratuitas ni consumo bloqueado; pendientes sobreviven save/load. Revisión externa antes de e5. |
| **5** | **4D-3e5 — F-DEAD-01** | Integrar selector contextual con manifiesto, búsqueda próxima que se amplía progresivamente, condiciones estructurales sin filtros económicos, preparación atómica e idempotente de pistas, distinción pendiente/recibida, validaciones de navegación y protección. | Sin salto >45 ly, sin rescate gratuito ni estación retrospectiva; intentos fallidos no consumidos; la búsqueda agotada es «incompleta» y la recepción respeta canales reales. |
| **6** | **4D-3e6 — Validación jugable y cierre** | Regresión integrada, varios universos/semillas, save/load repetido, casos de fallo, prueba con controles públicos en Textual y **sonido**, informe de experiencia y defectos. | Recorrido jugable estable; cerrar F-DEAD-01 solo con evidencias. Volver a producir arcos, singles y contenido tras bloquear únicamente defectos graves. |

**Orden 7 opcional:** correcciones de bloqueos detectados en 2–6; no es una invitación a perfeccionar el motor indefinidamente. Si la orden 5 exige una separación por seguridad de materialización y recepción, usar la reserva disponible y ajustar el cierre.

**Dependencias críticas:** v1.2 se aprueba **con 4D-3e2 ya en ejecución**: no atribuirle retrospectivamente requisitos no incluidos en su prompt. Verificar su extensibilidad al revisarlo, y planificar cualquier adaptación puntual imprescindible dentro de 4D-3e4 o una corrección acotada con aprobación, evitando rehacer worldgen por defecto. No consumir muestras `conditional` del catálogo como emplazamientos históricos certificados antes de cerrar 1–2. No forzar la migración de `scan` antes de disponer del contrato físico estable. La adaptación de lore y de deadnodes debe usar la misma noción de preexistencia.

## 5. Comprobaciones mínimas antes de cerrar cada orden

1. Leer `AGENTS.md`, canon y documentos técnicos relevantes; verificar `git status`, rama y SHA antes de tocar código.
2. Delimitar el alcance. Si hace falta cambiar densidades, probabilidades, recursos, política de guardrail, formato de arcos o canales, **detener la decisión sustantiva y consultar**.
3. Pruebas nuevas + smoke tests de worldgen, generación de lore, intel, route solve, deadnodes, save/load; incluir regresiones de localizaciones authored, bloques `[INTEL]`, `NODE/LINK/SECTOR/COORD`, colocación forzosa y **requisitos narrativos estructurados** (entidades, relaciones, contradicciones y orden de carga); ampliar matriz si cambia un contrato.
4. Verificar determinismo entre procesos/orden de materialización, ausencia de alteraciones ilegítimas de `known_nodes/known_links`, fuentes agotadas y objetivos narrativos protegidos.
5. Distinguir «verificado», «condicional», «no evaluado por presupuesto», «pendiente de entrega» y «no válido».
6. Reporte claro de cambios por archivo, pruebas ejecutadas, limitaciones; ZIP solo con archivos cambiados/nuevos y rutas relativas; `git diff --check`; **sin `git add`, commit ni push** por Codex.
7. Revisión externa por ChatGPT y commit/push manual del desarrollador tras aprobar los cambios.

## 6. Qué queda deliberadamente fuera del hito

- Nuevos arcos y singles completos (se retoman al acabar este hito, pero se pueden **diseñar** antes sin integrarlos).
- Editor visual de contenido, parser automático de prosa en lenguaje natural, gestor universal de mods y migración automática de universos ya iniciados tras instalar historias.
- Nuevas clases de instalaciones y reajustes generales de densidad, loot o recursos sin evidencia.
- Sistema complejo de triangulación y múltiples modos de sensores; basta un historial honesto y verificable.
- Simulación completa de sucesos dinámicos futuros, combate u otros sistemas ajenos.
- Revisión integral de todo el contenido antiguo no afectado por la preexistencia.
- Desarrollo completo de comunicaciones interestelares fuera del mínimo pasivo autorizado en e4b. **Si su ausencia impide la recepción diegética de F-DEAD-01, no simularlas ni declarar la fase cerrada**: usar únicamente un canal legítimo ya implementado o elevar el mínimo imprescindible como dependencia explícita para decisión.
- Migraciones de partidas de prueba antiguas; no borrar guardados sin acción explícita.

## 7. Riesgos y señales de parada

- **Rehacer worldgen afecta distribución:** exigir comparación de muchas semillas, colas de dispersión, rutas aisladas y origen jugable; un manifiesto determinista no garantiza buen juego.
- **Nodos authored y generación Z:** no cambiar reglas por comodidad; cuantificar el efecto del desbordamiento y acordar política antes de corregirlo.
- **Topología dependiente de vecino:** no reconstruir enlaces pasados de forma retroactiva ni depender del orden en que el jugador solicite los sectores.
- **Arcos esenciales con restricciones imposibles:** reportar y validar capacidad de alojamiento; permitir estaciones authored declaradas antes de la partida, pero no forzar instalaciones nuevas como solución automática durante la exploración.
- **Paquetes narrativos incompatibles:** detectar en preparación del mundo identidades duplicadas, nombres ambiguos y restricciones espaciales contradictorias, sin improvisar un mapa que falsee los documentos.
- **Actualización del catálogo con partida iniciada:** los requisitos de historias recién añadidas no deben alterar retroactivamente la geografía histórica del save; vincular manifiesto y versión/listado de contenido.
- **Regresión de autoría:** si la refactorización deja de reconocer la sintaxis vigente, impide declarar una estación para un arco, convierte una simple mención en revelación o confunde `COORD` con una estación, detener el cierre y corregir antes de declarar la fase compatible.
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

**Control de versión:** al modificar el roadmap, conservar los acuerdos anteriores, incrementar su versión y hacer un commit documental separado, para que otras conversaciones y órdenes futuras lean el texto actualizado.

### Actualización documental durante una orden de Codex en curso

1. **No detener ni reescribir 4D-3e2** por el cambio de v1.1 a v1.2. Conservar su informe y ZIP de cambios tal como los produzca la orden original.
2. Revisar **4D-3e2** con sus criterios originales, anotando separadamente la **nueva dependencia de v1.2**: entrada futura de requisitos narrativos y compilación de contenido. No declarar un fallo de implementación solo por una función que no se le pidió.
3. Para actualizar la hoja en Git, preferir **después de que termine Codex y de revisar/commitear 4D-3e2**, haciendo **un commit documental separado** de `docs/design/roadmap-worldgen-lore-f-dead01.es.md`. Si urge compartir el documento antes, hacerlo por el chat como adjunto y **no ejecutar `git add .` ni `git commit -a`** en un árbol mezclado con cambios de Codex.
4. Antes de cada commit, ejecutar `git status --short --branch`, `git diff --name-only`, `git diff --check` y usar `git diff --cached --name-only` después de `git add` selectivo. Verificar que el commit solo incluya los archivos aprobados.
5. `git push` sin asumir rama (`main` o `master`): confirmar `git branch --show-current` y `git branch -vv`. Si la rama ya tiene upstream, `git push`; si no, establecerlo explícitamente solo tras verificar el remoto y la rama de destino.
6. El nuevo contrato de autoría debe incorporarse al **siguiente prompt aún no enviado**, y sus resultados verificarse especialmente al preparar **4D-3e4**. Si 4D-3e2 revela una incompatibilidad arquitectónica real, proponer un parche acotado y pedir decisión antes de otro cambio grande.

**Siguiente coordinación efectiva:** recibir y revisar la salida de **4D-3e2**; registrar el commit aprobado y la versión v1.2 en la conversación de implementación antes de preparar 4D-3e3. No confundir aprobación de decisiones con implementación verificada.

### Historial del documento

- **v1.0:** secuencia de trabajo del manifiesto, scan, lore y F-DEAD-01.
- **v1.1:** preservación de localizaciones authored y sintaxis de intel; declaración, mención y revelación.
- **v1.2:** contenido narrativo instalado como entrada de worldgen; entidades/relaciones estructuradas y validación previa a la partida; procedimiento seguro con 4D-3e2 en curso.

- **v1.3:** acuerdo explícito para insertar e4b antes de e5; comms/radiod y recepción persistente local; aplazamiento seguro de activaciones correctivas legacy. D01–D24 y criterios F-DEAD-01 preservados.

- **v1.5 — 2026-11-06:** 4D-3e5a, conocimiento limitado y diagnósticos explícitos de desarrollo; e5b y e6 separados.
