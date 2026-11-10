# RETORNO — Canon del universo

**ID:** `RET-CAN`  
**Versión:** `0.6.0`<br>
**Fecha:** 2026-11-10<br>
**Estado:** base canónica inicial, revisable mediante decisión explícita  
**Destinatarios:** diseño narrativo, sistemas, programación, pruebas y asistentes de desarrollo  
**Documento complementario:** [`guia_coherencia.md`](guia_coherencia.md)  
**Especificación de diseño relacionada:** [`modelo_temporal_hibernacion.md`](../design/modelo_temporal_hibernacion.md)

> **Uso interno.** Este documento describe la verdad de diseño del universo, no la información que necesariamente conoce el jugador. No es un texto de ficción destinado a aparecer en el juego.

## 1. Alcance y reglas de interpretación

Este documento persigue dos objetivos: conservar las decisiones ya tomadas sobre el mundo de RETORNO y proporcionar una referencia estable para desarrollar mecánicas y contenido narrativo sin contradicciones involuntarias.

Cada enunciado relevante pertenece a una de estas categorías:

- **C — Establecido:** decisión canónica que debe respetarse hasta que se revise expresamente.
- **P — Provisional:** orientación plausible de diseño, útil para explorar alternativas, pero todavía no obligatoria.
- **A — Abierto:** cuestión aún no resuelta. Nadie debe completarla tácitamente al desarrollar código o lore.

La categoría **no** expresa qué sabe el jugador. Una verdad canónica puede permanecer secreta; un mensaje recuperado puede contener errores, rumores o mentiras. Hay que distinguir siempre **verdad del universo**, **creencia de un personaje** y **conocimiento del jugador**.

**Límite importante:** el canon no certifica que una mecánica esté implementada. La implementación se verifica en el código y su documentación técnica; cualquier diferencia debe señalarse, no borrarse mediante una suposición.

## 2. Identidad del mundo y experiencia buscada

### C-NAR-001 — Arqueología de información fragmentaria [C]

RETORNO debe permitir reconstruir acontecimientos y relaciones mediante rastros técnicos, señales, documentos, registros, rutas y restos materiales. El jugador puede disponer de información incompleta, contradictoria o degradada. El relato no necesita explicarse de forma directa ni lineal.

### P-NAR-002 — Tono de referencia [P]

Se favorecen la soledad, la incertidumbre, la persistencia de máquinas sin sus creadores y el contraste entre escalas humanas y tiempos astronómicos. Estos rasgos orientan la escritura; **no** obligan a que cada encuentro sea sombrío ni excluyen humor, ternura, esperanza o excepciones sorprendentes.

### C-NAR-003 — El retorno a la humanidad como horizonte oculto [C]

Más allá de sobrevivir, reparar la nave, navegar y reunir vestigios, existe un **objetivo narrativo de fondo**: buscar una sociedad humana que todavía esté viva. Ese horizonte corresponde también a la **esperanza del personaje-jugador**. No se presupone que exista una sociedad superviviente, que pueda alcanzarse o que su búsqueda tenga éxito.

El título **RETORNO** designa un viaje de regreso «a casa» a través de un laberinto espacial e histórico. «Casa» incluye la posibilidad de reencontrar una **comunidad humana**, no necesariamente un domicilio o una coordenada predeterminados. Esto no prohíbe que ciertos lugares específicos cobren importancia narrativa más adelante.

### C-NAR-004 — Investigación orientada por la esperanza [C]

La arqueología documental no es únicamente acumulación de contexto sobre el pasado: también es una **investigación** para detectar indicios sobre la supervivencia, localización o trayectoria de posibles comunidades humanas. El jugador debe poder aprender a valorar la **procedencia, fecha, fiabilidad y vigencia** de los testimonios.

La búsqueda y su urgencia deben llegar a hacerse comprensibles para el jugador **de forma progresiva**. No se fija todavía un capítulo, una misión obligatoria, una secuencia de revelaciones ni un instante único de comprensión.

### C-NAR-005 — Estructura trágica: el tiempo contra el retorno [C]

RETORNO se concibe como un **viaje de resonancia trágica, inspirado en la tragedia griega**: atravesar un laberinto para regresar a la humanidad. Su contradicción central es que **buscar pistas exige tiempo y viajar hasta ellas consume aún más tiempo**, mientras la comunidad perseguida podría desaparecer antes de que el viajero llegue.

La **carrera contra el reloj** es un principio dramático, no una promesa de cuenta atrás visible, simulación de extinción, final inevitablemente negativo ni victoria garantizada. Es posible que una pista sea genuina y, sin embargo, haya dejado de describir el presente al llegar el protagonista.

## 3. Tiempo, desplazamiento y civilización

### C-TIME-001 — Viaje interestelar e hibernación [C]

En la experiencia de RETORNO, los desplazamientos interestelares duran periodos muy largos y la **hibernación es, en la práctica, la forma de hacerlos viables para el viajero**. Es normal que un trayecto implique cambios históricos que el tripulante no presencia despierto.

- Un **año luz** es una medida de distancia, no de tiempo.
- Deben distinguirse **distancia recorrida**, **tiempo exterior transcurrido** y, cuando resulte pertinente, **tiempo experimentado por el viajero**.
- Las naves con masa se desplazan a velocidades **inferiores a la de la luz** (`C-TIME-002`). Se contempla una velocidad de crucero **provisional** de `0,5c` (`P-TIME-005`).
- Se distinguen tres magnitudes temporales: tiempo galáctico, tiempo propio de la nave y envejecimiento biológico (`C-TIME-003`).
- No se deducen viajes o comunicaciones instantáneos. La tecnología general de `engines` se establece en `C-TECH-003`–`006`; siguen abiertos los perfiles físicos de aceleración/frenado y el cálculo relativista definitivo.

### C-TIME-002 — Viaje estrictamente sublumínico [C]

Una nave con masa **no alcanza ni supera la velocidad de la luz**. La duración de los trayectos debe ser compatible con esta restricción. La existencia de rutas de navegación no implica un atajo superlumínico ni una alteración arbitraria de la causalidad. La arquitectura tecnológica general de propulsión de la nave del jugador queda fijada en `C-TECH-003`–`006`; los perfiles de aceleración y frenado, el tratamiento físico preciso de la masa de reacción y el consumo energético realista continúan abiertos. La fórmula de consumo jugable descrita en `P-TECH-001` es provisional.

### C-TIME-003 — Tres magnitudes temporales diferenciadas [C]

RETORNO distinguirá:

1. **Tiempo galáctico transcurrido:** referencia convencional para la cronología de la partida; comienza en cero con cada nueva partida. Sirve para historia, mensajes y evolución de lugares exteriores a la nave.
2. **Tiempo propio de la nave:** tiempo medido por los relojes que viajan con ella; puede diferir del galáctico por velocidad y, en el futuro, por condiciones gravitatorias. Rige los procesos físicos y el envejecimiento de sus componentes.
3. **Envejecimiento biológico acumulado del protagonista:** una **magnitud fisiológica**, no un tercer reloj físico independiente. Depende del tiempo propio y de su estado de hibernación o vigilia.

No se presupone un «tiempo universal absoluto» de toda la galaxia: el reloj galáctico es una **convención útil de simulación** que deberá concretarse al modelar efectos relativistas intensos. Los tres valores deberán poder consultarse y persistirse sin confundir sus unidades o responsabilidades. El canon no afirma que esa separación ya esté implementada.

### C-BIO-001 — Hibernación química avanzada, ralentización no nula [C]

La civilización desarrolló una tecnología de hibernación extraordinariamente eficaz apoyada en **sistemas de conservación y agentes químicos adecuados**. Durante su aplicación correcta, el envejecimiento biológico del protagonista se reduce enormemente, **pero no se detiene por completo**. Esta capacidad constituye una concesión tecnológica de la ciencia ficción de RETORNO: no exige demostrar su plausibilidad con la medicina contemporánea ni establecer todavía sus mecanismos moleculares.

### C-BIO-002 — Eficacia dependiente de `life_support` y consultable [C]

La eficacia de la hibernación no será constante ante cualquier condición de la nave. Dependerá, como mínimo, del **estado de `life_support`**: el deterioro de este sistema puede empeorar la conservación biológica. El jugador debe disponer de una **consulta explícita** que muestre la eficacia o tasa de envejecimiento efectiva **en el estado actual de la nave**; el nombre y formato definitivo del comando siguen pendientes de diseño.

No se establece todavía la función matemática de degradación, cómo intervienen los agentes químicos, ni qué sucede exactamente en cada fallo crítico. La tasa nominal y la tasa efectiva deben distinguirse.

### C-BIO-003 — Edad biológica como recurso finito [C]

El personaje **acumula edad biológica incluso cuando hiberna**. Este envejecimiento constituye un recurso de supervivencia y una presión dramática de la búsqueda. No se fija todavía una edad de muerte automática, una esperanza de vida exacta, penalizaciones por edad ni una interfaz concreta. Tampoco se asume que sea posible rejuvenecer o restaurar la edad consumida.

### P-TIME-005 — Velocidad de crucero candidata: `0,5c` [P]

La candidata principal para el equilibrio interestelar es **la mitad de la velocidad de la luz**, aproximadamente `0,5 años luz/año` en el marco galáctico de referencia, durante la fase de crucero. El valor definitivo, las fases de aceleración/desaceleración y su relación con el balance general **siguen abiertos**. Que el prototipo utilice esta velocidad no convierte la cifra en un principio físico canónico definitivo.

### P-BIO-001 — Tasa nominal de envejecimiento en hibernación: `0,5 %` [P]

Se adopta como referencia inicial una tasa de **`0,5 %` del tiempo propio de la nave** (`0.005` como multiplicador decimal), con hibernación efectiva y `life_support` en condiciones nominales. Expresado de otro modo: **200 años propios de la nave producen un año de envejecimiento biológico**. Es una cifra de **balance configurable**, explícitamente revisable, no una ley física ni una constante inmutable del lore.

En vigilia se toma como referencia provisional una relación biológica de `1:1` con el tiempo propio. El envejecimiento efectivo dependerá de los estados operativos y de la hibernación; no se ha acordado una fórmula de penalización por daños.

### P-NAR-007 — Escala de grandes descubrimientos [P]

Una separación del orden de **200 años galácticos** entre *grandes hitos de investigación* es una referencia tentativa para estudiar el ritmo dramático, **no** una frecuencia del scheduler ni un intervalo obligatorio entre arcos, singles o hallazgos ordinarios.

### C-GRAV-001 — Objetos compactos y dilatación gravitatoria futura [C]

El universo jugable contará, en una **fase futura**, con **agujeros negros y regiones cercanas a objetos compactos** donde puedan producirse dilataciones gravitatorias intensas. Sus efectos temporales serán distintos de la reducción metabólica de la hibernación: primero condicionan el **tiempo propio físico**, y solo después el proceso de envejecimiento biológico utiliza ese tiempo propio.

No se consideran implementados por esta decisión. Quedan abiertos los perfiles gravitatorios, órbitas, efectos de marea, radiación, navegación, costes y riesgos. No se introduce por defecto un mecanismo seguro para acelerar el futuro ni viajes al pasado.

### C-HIST-001 — Colapso desigual y abandono escalonado [C]

El **colapso de la civilización humana fue un proceso extremadamente desigual, extendido durante milenios**. No ocurrió a la vez en toda la galaxia: distintas regiones, sociedades, rutas e infraestructuras siguieron trayectorias y ritmos propios. Algunas instalaciones o comunidades pudieron seguir funcionando muchísimo después de que otras desaparecieran. Este hecho **no** establece cuál fue el último lugar habitado ni si todavía queda alguno.

**Consecuencia canónica:** la fecha de construcción, la fecha del último mantenimiento, la fecha del último uso y la fecha del hallazgo no son necesariamente iguales ni intercambiables. Tampoco se debe usar una única «fecha del colapso» como fecha de abandono de cada localización.

### A-HIST-002 — Causas y cronología precisa del colapso [A]

Permanecen sin resolver su causa o causas definitivas, hitos y fechas precisos, alcance geográfico en cada periodo y protagonistas. **La duración milenaria y la desigualdad del proceso ya son canónicas**; las cifras y causas concretas, no. Los indicios de crisis escalonada presentes en material narrativo existente son compatibles con esta decisión, pero no autorizan a declarar una explicación causal cerrada.

### A-SOC-001 — Situación actual de posibles comunidades supervivientes [A]

**Ni el jugador ni el equipo de diseño conocen, por ahora, la respuesta** a si continúa existiendo alguna sociedad humana aislada en la galaxia. No se establece una localización válida, una fecha de extinción total ni una prueba indiscutible de supervivencia presente. Un testimonio que diga «seguimos vivos» puede ser auténtico y estar ya desactualizado.

La **esperanza del protagonista** (`C-NAR-003`) es un hecho narrativo; la **existencia efectiva de su objetivo** permanece abierta.

## 4. Arquitectura tecnológica de la nave RETORNO

Esta sección fija la **verdad de diseño** de la nave del jugador. Los identificadores de sistemas y sectores son los nombres canónicos para el desarrollo, pero describir aquí una función no significa que esté implementada. El mapa distingue **sectores físicos**, **sistemas funcionales** y **componentes internos**: no son conceptos intercambiables.

### C-TECH-001 — Sectores físicos y distribución funcional [C]

La nave RETORNO dispone de diez sectores identificados de forma estable. Los sistemas pueden compartir sector y un sector puede albergar equipos sin constituir por sí mismo un sistema gestionable.

| Sector | Denominación funcional | Instalaciones y función principal |
|---|---|---|
| `DCK-A1` | Dársena / esclusa | Acoplamiento, acceso y operaciones de tránsito hacia el exterior. |
| `STS-BAY` | Bahía de estasis | Equipamiento de hibernación y conservación del ocupante. |
| `LFS-01` | Soporte vital | `life_support`, condiciones ambientales y apoyo a la estasis. |
| `PWR-A1` | Núcleo de potencia | `power_core`, generación eléctrica primaria. |
| `BUS-A2` | Distribución de energía | `energy_distribution`, distribución y estabilidad de la red. |
| `ENG-R1` | Sala de máquinas | `engines`, conjunto de propulsión por materia-antimateria. |
| `BRG-01` | Puente / mando | `core_os`, `data_core` y `comms`, control, datos y comunicaciones. |
| `SNS-R1` | Sala de sensores | `sensors`, observación y detección. |
| `DRN-BAY` | Bahía de drones | `drone_bay`, despliegue, recuperación y mantenimiento de drones. |
| `CRG-01` | Bodega de carga | Materiales recuperados, módulos y almacenamiento de cápsulas de antimateria. |

El sector `ENG-R1` es una instalación física existente en el plano de la nave; se le asigna ahora el nuevo **sistema funcional `engines`**. La arquitectura no obliga a convertir cada componente del motor en un `ShipSystem` independiente.

### C-TECH-002 — Generación eléctrica independiente de la propulsión [C]

`power_core` es un **reactor compacto de fusión nuclear** que suministra electricidad a la nave. Dispone de reservas internas selladas de combustible apropiadas para operaciones de muy larga duración. Son **finitas en la ficción**, pero su consumo **no se contabiliza como un recurso administrable por el jugador** dentro del modelo de juego previsto. La dificultad de la supervivencia energética procede de averías, limitaciones de generación, distribución, baterías y demanda, no de buscar periódicamente un segundo combustible nuclear.

`energy_distribution` recibe y distribuye esa electricidad mediante la red de potencia; su función es distinta de la generación. `power_core` y `energy_distribution` siguen siendo sistemas susceptibles de deterioro, reparación y mejora. El motor `engines` puede utilizar electricidad para sus equipos auxiliares y de control, pero el **combustible empleado para impulsar la nave** es independiente del reactor de fusión.

Por tanto, **las cápsulas de antimateria no alimentan `power_core`**. Tampoco se presupone que el reactor eléctrico impulse por sí solo la nave durante los viajes interestelares.

### C-TECH-003 — Sistema funcional `engines` y propulsión sublumínica [C]

El nombre canónico del sistema jugable de motores es **`engines`**, ubicado en `ENG-R1`. Es el conjunto destinado a producir empuje para el desplazamiento de la nave mediante **aniquilación controlada de materia y antimateria**. El término `propulsion` puede designar la función de propulsión o, más específicamente, el **componente de empuje**; no sustituye a `engines` como identificador del sistema completo.

La arquitectura de motor de antimateria se integra en el principio de viaje **estrictamente sublumínico** (`C-TIME-002`). Su existencia no implica viaje superlumínico, salto instantáneo, aceleración ilimitada ni cancelación de los costes temporales del viaje.

### C-TECH-004 — Tres componentes principales de `engines` [C]

1. **Alimentador de antimateria.** Recibe el contenido de las cápsulas y regula su transferencia y dosificación hacia la reacción, preservando el confinamiento y evitando el contacto prematuro con la materia ordinaria.
2. **Cámara de aniquilación.** Introduce cantidades controladas de materia ordinaria y antimateria; la aniquilación libera energía que el sistema debe gestionar, incluida la protección térmica y radiológica.
3. **Sistema de empuje (`propulsion`).** Aprovecha una parte de la energía y de los productos de reacción para producir empuje dirigido; se prevé tecnología de guiado y tobera magnética, sin fijar todavía su rendimiento físico definitivo.

El conjunto requiere controles, protecciones y gestión térmica, pero **no se establece una cuarta mecánica de mantenimiento** por cada elemento auxiliar. La estructura de tres componentes permite en el futuro **auditorías detalladas** que distingan el estado del alimentador, la cámara y el sistema de empuje. Por ahora se mantendrá una integridad operativa global de `engines`.

La materia ordinaria necesaria para la aniquilación procede inicialmente de **reservas internas de reactivos del motor**, sin inventario jugable independiente. También podría requerirse masa de reacción adicional. La procedencia, composición exacta, agotamiento y tratamiento de esas reservas no quedan fijados como mecánicas; véanse `A-TECH-002` y `A-TECH-003`.

### C-TECH-005 — Cápsulas de antimateria: confinamiento, carga y recuperación [C]

El combustible de propulsión recuperable es la **cápsula de antimateria**. Cada cápsula dispone de **trampas electromagnéticas y sistemas de alto vacío** que mantienen la antimateria aislada de la materia convencional. Su confinamiento cuenta con alimentación y protección **autónomas respecto de la red eléctrica general de RETORNO**, concebidas para conservaciones prolongadas. Esto no significa duración infinita, ausencia de averías ni que una cápsula encontrada tras siglos sea necesariamente segura o aprovechable.

Las cápsulas pueden transportarse como carga y almacenarse en `CRG-01`. Pueden recuperarse de otras instalaciones o restos cuando sus condiciones lo permitan. El motor dosifica su contenido, por lo que **una cápsula puede consumirse parcialmente** y conservarse el resto. La representación técnica del inventario puede utilizar **cápsulas equivalentes** como cantidad divisible sin exigir simular individualmente cada contenedor.

La antimateria es, en esta etapa, el **único recurso nuevo de combustible que el jugador debe gestionar**. La posibilidad futura de administrar también materia ordinaria sigue abierta, no se descarta.

### C-TECH-006 — Deterioro, reparación y mejoras de `engines` [C]

`engines` es un sistema susceptible de **degradación, diagnóstico, reparación y mejoras**. Su deterioro reduce la eficiencia: realizar un mismo desplazamiento requiere más antimateria, mientras la reparación recupera eficiencia al restaurar integridad. Los daños pueden interpretarse como anomalías de cualquiera de los tres componentes principales, aunque inicialmente se representen mediante un estado global.

La **integridad** del sistema y su **nivel tecnológico de eficiencia** son conceptos distintos. Un **módulo de mejora de eficiencia de motores** permite consumir menos antimateria que un motor sin esa mejora, con la misma integridad. La instalación del módulo debe beneficiar la autonomía de expedición y permitir rutas o cadenas de viajes que de otro modo no serían viables con las reservas disponibles. El identificador, el coste, las restricciones y el modificador numérico definitivos del módulo pertenecen a la implementación y al balance, no quedan establecidos como hechos físicos del universo.

La investigación pormenorizada de los componentes mediante auditorías se contempla para una fase futura; el canon **no afirma que exista actualmente un comando de auditoría**.

### C-TECH-007 — Alcance de los sistemas de seguridad interna [C]

La nave del jugador **no tendrá un sistema funcional independiente `security`** en su configuración objetivo. Esto sustituye su presencia en el estado inicial actual del prototipo y **no prohíbe** que otras naves, estaciones o instalaciones dispongan de seguridad interior, contramedidas, controles de acceso o defensas, especialmente al desarrollar salvage avanzado. No se atribuye una mecánica de seguridad a esas instalaciones hasta que se diseñe explícitamente.

### C-TECH-008 — Selección explícita de velocidad objetivo en tránsito no local [C]

El piloto podrá seleccionar mediante `engines speed` la **velocidad de crucero objetivo** para el siguiente viaje **no local**, en escalones expresados como fracciones de `c`. El valor por defecto es `max`: la mayor velocidad que permitan **conjuntamente** las condiciones físicas del motor y las mejoras instaladas. También podrá elegirse una velocidad numérica explícita. Si supera el máximo disponible, se informará del límite y se impedirá la salida; no se reducirá silenciosamente la petición expresa del jugador.

La configuración de velocidad de crucero no es un nivel de potencia eléctrica, ni modifica el **perfil eléctrico CRUISE**, ni controla las maniobras locales. Para un viaje ya iniciado se conserva una velocidad efectiva fija; no se permitirá cambiarla durante el tránsito mientras no exista un modelo completo de aceleración, consumo y relojes para cambios en ruta. El modelo de desplazamiento sigue siendo sublumínico.

La velocidad elegida afectará tanto al **tiempo de viaje** como al **consumo de antimateria**, según parámetros provisionales de balance. El sistema debe mostrar antes de confirmar una salida la velocidad efectiva, el tiempo estimado, el combustible requerido y su suficiencia, utilizando solamente información de navegación legítimamente conocida por la nave.

### C-TECH-009 — Independencia de mejoras de velocidad y eficiencia [C]

Una **mejora de velocidad** aumenta el techo tecnológico de crucero; una **mejora de eficiencia** disminuye el gasto de antimateria a igualdad de trayecto, integridad y velocidad. Ambas son categorías diferentes y podrán coexistir. La primera se contempla para el futuro; la segunda ya tiene una primera implementación jugable prevista en `C-TECH-006` y `P-TECH-002`.

El límite operativo **no debe inferirse solamente del estado nominal `UPGRADED`**: el sistema deberá calcularlo a partir de su integridad y del equipamiento instalado. Instalar o retirar mejoras de eficiencia no altera por sí solo la velocidad máxima; reparar el motor no concede gratuitamente un módulo de velocidad.

### P-TECH-001 — Consumo interestelar experimental y eficiencia [P]

Se adopta la siguiente **fórmula inicial de balance para pruebas**, no una ley física ni un valor canónico irreversible:

```text
consumo_equivalente = (0.5 + distancia_ly / 10)
                      * (1 + 1.5 * (1 - integridad_normalizada)^2)
                      * multiplicador_mejora
```

- `consumo_equivalente`: contenido consumido, medido en cápsulas equivalentes; admite fracciones.
- `distancia_ly`: distancia interestelar expresada en años luz.
- `integridad_normalizada`: integridad efectiva de `engines` en el intervalo `0..1`; esto no define umbrales mínimos para poder encenderlo o viajar.
- `multiplicador_mejora`: `1.0` sin mejora y, como hipótesis inicial, `0.8` con el primer módulo de eficiencia (ahorro del 20 %).
- `0.5` es un coste fijo de balance asociado de forma simplificada a las maniobras de un viaje; `distancia_ly / 10` es una aproximación jugable, **no** una afirmación de proporcionalidad física entre combustible y distancia en una trayectoria relativista.

**Referencias de prueba, con motor íntegro y sin mejora:** 2 años luz → 0,70 cápsulas equivalentes; 10 → 1,50; 20 → 2,50; 45 → 5,00. El deterioro eleva los consumos; las reparaciones y mejoras los reducen. El consumo y las restricciones de las maniobras locales **no se integran aún en esta fórmula**; provisionalmente no exigirán gastar cápsulas de antimateria.

La cantidad exacta de combustible se debe **estimar y mostrar antes de iniciar un viaje**. Quedan por resolver la deducción o reserva del combustible, los abortos, los efectos de daños durante el trayecto y los casos límite de redondeo y agotamiento. Ninguna de estas reglas se considera implementada por escribirla aquí.

### P-TECH-002 — Reserva inicial y módulo de eficiencia de referencia [P]

Para iniciar pruebas de autonomía se propone **12 cápsulas equivalentes de antimateria** como reserva de una partida nueva; no es una cifra física definitiva. El primer módulo de eficiencia utilizaría el multiplicador **`0.8`** descrito en `P-TECH-001`. La disponibilidad de cápsulas en la generación procedural, la frecuencia de recuperación por salvage y el balance con distancias y deterioro deberán comprobarse mediante recorridos jugables.

Los parámetros anteriores pueden ajustarse sin cambiar el hecho canónico de que `engines` consume antimateria, se deteriora, puede repararse y admite mejoras de eficiencia.

### P-TECH-003 — Límites experimentales de velocidad [P]

Para la primera versión de selección se propone **`0.1c`, `0.2c`, `0.3c`, `0.4c` y `0.5c`**; `max` será la selección inicial. Un **futuro módulo de velocidad** podrá permitir progresivamente **`0.6c`, `0.7c` y `0.8c`**. `0.8c` es el **objetivo provisional de ese módulo**, no una capacidad ya implementada ni un límite físico universal.

| Integridad/estado operativo de `engines` | Techo sin mejora de velocidad | Techo con futuro módulo de velocidad |
|---|---:|---:|
| NOMINAL (o integridad sana con presentación UPGRADED) | 0.5c | 0.8c |
| LIMITED | 0.4c | 0.6c |
| DAMAGED | 0.3c | 0.4c |
| CRITICAL / OFFLINE | No permite iniciar viaje | No permite iniciar viaje |

La tabla es **balance provisional**, no definición definitiva de umbrales de integridad, y tampoco obliga a que `UPGRADED` sea un estado persistente independiente de salud. Si se selecciona una velocidad fija que supera el nuevo techo tras un daño, la salida se bloqueará hasta reparar o reconfigurar; `max` siempre elegirá el techo efectivo.

### P-TECH-004 — Escalera de consumo por velocidad y equilibrio estratégico [P]

Como **hipótesis de balance preferente para pruebas**, se propone multiplicar el precio vigente de `P-TECH-001` por un factor dependiente de la velocidad. Dado que las velocidades seleccionables son discretas, una tabla configurable permite afinar la economía sin forzar una falsa ley física:

| Velocidad objetivo | Factor sobre consumo de `P-TECH-001` | Disponibilidad prevista |
|---|---:|---|
| 0.1c | 0.30 | Inicial |
| 0.2c | 0.48 | Inicial |
| 0.3c | 0.66 | Inicial |
| 0.4c | 0.82 | Inicial |
| 0.5c | 1.00 | Inicial, a integridad nominal |
| 0.6c | 1.28 | Futura mejora de velocidad |
| 0.7c | 1.65 | Futura mejora de velocidad |
| 0.8c | 2.20 | Futura mejora de velocidad |

Por ejemplo, con 10 años luz, integridad de `engines` de `0.90` respecto a máximo `1.0` y **sin módulo de eficiencia**, la fórmula base da 1,5225 cápsulas equivalentes a `0.5c`. La escala propuesta produciría aproximadamente 0,457 a `0.1c`, 0,731 a `0.2c`, 1,005 a `0.3c`, 1,248 a `0.4c` y 1,523 a `0.5c`. La futura `0.8c` consumiría aproximadamente 3,350 cápsulas equivalentes en ese ejemplo.

La escala anterior **sustituye como candidata preferente de ensayo** a la curva exploratoria `0.6 + 0.4 * (v/0.5)^2`: esta última ofrecía un ahorro escaso entre velocidades lentas en comparación con las décadas adicionales de viaje y el desgaste actual. **No se afirma que la nueva escala esté ya equilibrada.**

**Criterio de balance obligatorio antes de cerrar coeficientes:** evaluar conjuntamente consumo, disponibilidad de cápsulas, tiempo galáctico, tiempo propio, envejecimiento biológico, deterioro acumulado, capacidad de reparación y autonomía restante. Usar al menos viajes cortos, medios y largos, diferentes integridades, pocas/abundantes cápsulas y presencia/ausencia de módulos. Cada velocidad disponible debería resultar una elección razonable en algún escenario plausible; comprobar que ninguna domina en la práctica a todas las demás. Si la economía procedural todavía carece de datos, declararlo explícitamente y no concluir un equilibrio definitivo a partir de la fórmula aislada.

La velocidad objetivo debe consultarse junto con la estimación de viaje y ser consistente con la velocidad efectiva utilizada para el cálculo relativista. La configuración de `max` no debe suponer cambio imprevisto de velocidad a mitad de trayecto.

### A-TECH-001 — Perfiles de viaje, desgaste y semántica de consumo [A]

Quedan por concretar la aceleración y frenado, la dependencia entre empuje, masa, velocidad y tiempo galáctico/propio, el tratamiento del combustible ante `nav abort`, el desgaste durante tránsito y los fallos de `engines` en ruta. No modificar indirectamente el modelo temporal existente al implementar el combustible.

### A-TECH-002 — Posible economía separada de materia ordinaria [A]

No se decide todavía si el jugador podrá recuperar, refinar y gestionar materia ordinaria como segundo recurso de propulsión. Solo tendría sentido si origina decisiones jugables propias y una logística distinguible de la recuperación de antimateria. Hasta esa decisión, las reservas internas de materia ordinaria **no generan otro contador de combustible**.

### A-TECH-003 — Física de detalle y durabilidad de las reservas [A]

Permanecen abiertos el mecanismo exacto de la tobera y del aprovechamiento de productos de reacción, la cantidad de masa de reacción necesaria, los límites físicos de aceleración, la vida de las trampas de confinamiento, las protecciones activas y las tasas reales de agotamiento del combustible de fusión. Ninguna reserva debe considerarse físicamente infinita por el hecho de no modelarse como recurso.

### A-TECH-004 — Abastecimiento y agotamiento total de antimateria [A]

Quedan pendientes las probabilidades y ubicaciones de recuperación, las alternativas disponibles cuando no quedan cápsulas y los mecanismos de prevención o resolución de bloqueos de exploración por combustible. **No se adopta todavía una solución específica**. El futuro diseño deberá comprobar sus efectos sobre las rutas y el desarrollo narrativo.

### A-TECH-005 — Coherencia temporal del desgaste y maniobras locales [A]

El principio C-TIME-003 establece que los procesos físicos y el envejecimiento de los componentes de la nave deben regirse por el tiempo propio. Desde T-04B2, el deterioro ordinario de los sistemas y del casco se integra en tiempo propio, separando los tramos de tránsito y reposo cuando corresponde y conservando los modificadores operativos existentes. La discrepancia original entre canon e implementación queda resuelta para estos procesos. Permanecen pendientes la revisión de la exposición ambiental por tramos y la migración temporal de otros subsistemas físicos.

También permanecen abiertos los controles separados de maniobra local, las aceleraciones/desaceleraciones físicas y una eventual modificación de velocidad durante el tránsito. La primera implementación de `engines speed` no altera el movimiento local.

## 5. Conservación y desaparición de infraestructura

### C-INF-001 — Diseño para escalas temporales muy largas [C]

Al menos una parte significativa de la infraestructura interestelar fue concebida para resistir intervalos de tiempo mucho mayores que una vida humana. La escala de los viajes favorece construcciones duraderas, sistemas pasivos de preservación, redundancias y autonomía operativa.

Esto **no** significa que todas las naves o estaciones fueran igualmente robustas, ni que su durabilidad implique funcionamiento permanente. La finalidad, coste, ubicación y tecnología de cada estructura importan.

### C-INF-002 — Mantenimiento autónomo persistente y desigual [C]

Existió infraestructura de mantenimiento automatizado capaz de prolongar la vida útil de ciertas instalaciones sin presencia humana continua. Parte de ella pudo seguir actuando después del abandono de sus creadores. Esta capacidad está sujeta a fallos, agotamiento de recursos, aislamiento, instrucciones obsoletas o conservación parcial.

**No implica** una red universal aún activa, una IA omnipotente ni la presencia de robots funcionales en todas las ruinas. Su distribución, arquitectura, objetivos y nivel de autonomía concretos no están todavía determinados.

### C-INF-003 — Sesgo de supervivencia arqueológica [C]

Las estructuras que el jugador logra localizar o examinar son solo una fracción de las que alguna vez existieron. Muchas se han perdido, han sido destruidas, quedaron inaccesibles o ya no permiten recuperar información ni materiales reconocibles.

Un registro de navegación puede conducir a un lugar donde **no queda una instalación utilizable**, o donde solamente persisten fragmentos o una firma ambigua.

No se fija por ahora ningún porcentaje de supervivencia, densidad de ruinas ni tasa de destrucción.

### C-INF-004 — Existir no equivale a funcionar [C]

Debe distinguirse entre:

1. **Persistencia física**: queda materia o una estructura reconocible.
2. **Accesibilidad**: es posible aproximarse, inspeccionar o entrar.
3. **Operatividad**: algún subsistema puede realizar su función.
4. **Recuperabilidad**: todavía pueden obtenerse materiales, componentes o datos.

Estas propiedades pueden desacoplarse. Una nave intacta puede estar completamente muerta; un campo de restos puede conservar un archivo sellado; un relé puede conservar energía, pero haber perdido la capacidad de transmitir a larga distancia.

### P-INF-005 — Factores plausibles de deterioro [P]

La degradación debe resultar compatible con el entorno y la historia del objeto: impactos, radiación, condiciones térmicas, pérdida de fluidos o atmósferas, corrosión donde exista un medio reactivo, daño previo, fallos energéticos, desgaste de sistemas activos y ausencia o fracaso de mantenimiento. El vacío interestelar **no** equivale a desintegración rápida e inevitable, pero tampoco a conservación perfecta.

Estos factores todavía no constituyen un simulador físico ni un conjunto cerrado de reglas numéricas.

## 6. Cuatro estados de conservación

### C-DEC-001 — Taxonomía de cuatro estados [C]

Se adoptan **cuatro estados descriptivos** para orientar la construcción del mundo, la generación procedural y la escritura narrativa:

| Estado | Nombre | Caracterización | Posibilidades narrativas, no garantías |
|---|---|---|---|
| **E1** | **Restos dispersos** | Fragmentos, campos de escombros o vestigios apenas reconocibles. | Trazas, chatarra, módulos o soportes de datos excepcionalmente conservados. |
| **E2** | **Ruina estructural** | Instalación identificable, pero severamente dañada o inoperativa como conjunto. | Compartimentos inaccesibles, registros corruptos, piezas recuperables. |
| **E3** | **Conservación parcial** | Estructura con subsistemas aislados todavía operativos o recuperables. | Energía residual/local, archivos legibles, automatismos puntuales. |
| **E4** | **Infraestructura persistente** | Instalación conservada de modo extraordinario, a menudo mediante protección o mantenimiento. | Funciones de larga duración, sistemas autónomos y protocolos heredados. |

**Reglas de lectura de esta taxonomía:**

- Es una clasificación de **estado actual**, no de antigüedad ni de valor histórico.
- Los estados **no forman una cronología obligatoria**: un choque puede llevar directamente a E1; un objeto muy antiguo puede permanecer en E4.
- E4 **no** significa intacta, segura, habitada o totalmente operativa; E1 **no** excluye hallazgos valiosos.
- La clasificación global no sustituye los estados de los subsistemas. Puede existir un archivo intacto dentro de una ruina E2.
- Las transiciones, reparaciones y deterioros durante la partida son posibilidades de diseño, **no funcionalidades ya implementadas**.
- La distribución estadística de E1–E4 queda abierta; no se presupone que las cuatro categorías sean igual de frecuentes.

### C-DEC-002 — La conservación tiene causas [C]

Cuando una instalación excepcionalmente antigua conserva una capacidad relevante para el argumento o la mecánica, debe existir una **explicación diegética al menos plausible**: diseño robusto, aislamiento, conservación pasiva, mantenimiento automatizado, protección del entorno, reparaciones históricas u otra causa que se incorpore explícitamente al canon.

No es necesario explicar esa causa al jugador, ni en cada documento; sí debe poder sostenerse durante el desarrollo.

## 7. Información, señales y memoria

### C-DATA-001 — La información puede sobrevivir separada de sus sistemas [C]

La pérdida de una función operativa no implica necesariamente la destrucción de todos sus registros. Pueden sobrevivir archivos sellados, copias redundantes, cachés locales, transmisiones diferidas y fragmentos recuperables. En sentido inverso, un sistema con energía puede disponer de datos incompletos o inválidos.

### C-DATA-002 — Procedencia y temporalidad importan [C]

La mera recepción de un mensaje no prueba que su emisor siga vivo ni que su contenido sea actual. Para cualquier comunicación notable debe poder contemplarse si se trata de una transmisión nueva, una emisión automática, una reproducción, una caché recuperada o un mensaje retrasado.

El canon **no afirma** que todos esos mecanismos estén implementados ni establece aún la física definitiva de las comunicaciones interestelares.

### C-DATA-003 — Los mensajes de los muertos como motivo recurrente [C]

El viajero encontrará **una y otra vez mensajes cuyos emisores murieron hace mucho tiempo**. Pueden ser personales, rutinarios, administrativos, técnicos o íntimos; no todos deben anunciar una catástrofe ni estar redactados con solemnidad. Su fuerza deriva a menudo de lo cotidiano frente a la enorme distancia temporal.

Un mensaje puede conservar **verdad histórica** sin describir una **situación vigente**. La obra debe diferenciar, cuando importe, la fecha del hecho, la del registro, la de su transmisión o almacenamiento y la de su recuperación. La certeza sobre la muerte de un emisor tampoco debe inventarse en una fuente donde solo sea una conjetura.

### C-DATA-004 — Conocimiento limitado y procedencia de la información [C]

La existencia de una información en el estado interno del universo no implica que el protagonista pueda conocerla. Toda información presentada como conocimiento de la nave o del jugador debe proceder de una observación, recepción, lectura, registro o inferencia legítima. Las inferencias pueden ser inciertas o erróneas y deben distinguirse de los hechos verificados. La simulación puede conocer hechos que permanecen inaccesibles al protagonista.

Deben distinguirse cinco capas:

1. Verdad física e histórica del universo.
2. Información interna del motor, incluidas decisiones procedurales y narrativas.
3. Observaciones y registros efectivamente adquiridos por la nave.
4. Inferencias o hipótesis elaboradas a partir de evidencia legítima.
5. Conocimiento que el jugador puede consultar por las interfaces ordinarias.

La existencia física o asignación interna no publica conocimiento. Conocer una localización no equivale a conocer una ruta hasta ella ni a poder recibir ahora sus transmisiones. Un testimonio recibido puede conservar información falsa sin convertirla en verdad física; una inferencia debe señalar su incertidumbre y su base disponible.

Este principio se refiere a hechos del universo y conocimientos atribuidos al protagonista o la nave. Menús, controles, guardado/carga y ayuda general pueden ofrecer información ordinaria del sistema sin una justificación diegética artificial. Los comandos explícitos de desarrollo pueden revelar el estado omnisciente del motor; activar debug no altera el significado de las consultas públicas. No se resuelven aquí supervivientes, cronología galáctica ni `A-COM-001`.

**English — C-DATA-004: Limited knowledge and information provenance [C]**

Information existing in the universe’s internal state does not imply that the protagonist can know it. All information presented as ship or player knowledge must come from a legitimate observation, reception, reading, record or inference. Inferences may be uncertain or wrong and must be distinguished from verified facts. The simulation may know facts that remain inaccessible to the protagonist.

Distinguish five layers: (1) physical and historical truth; (2) internal engine information, including procedural and narrative decisions; (3) observations and records actually acquired by the ship; (4) inferences or hypotheses based on legitimate evidence; (5) knowledge accessible through ordinary player interfaces. Physical existence or internal assignment does not publish knowledge. Knowing a location, knowing a route to it and being able to receive its transmissions now are separate facts. False testimony remains received evidence rather than physical truth; inferences must identify their uncertainty and available basis.

The principle concerns universe facts and knowledge attributed to the protagonist or ship. Menus, controls, save/load and general help may provide ordinary system information without artificial fictional explanations. Explicit development commands may expose omniscient engine state; enabling debug does not change public queries. Survivors, galactic chronology and `A-COM-001` remain open.

## 8. Cómo interpretar la generación procedural

### C-WORLD-001 — Descubrir no es crear físicamente [C]

La aparición de una localización al explorar, escanear o resolver una ruta representa su incorporación al mundo **conocido por el jugador** o la materialización técnica de contenido del mundo; no significa que una estación antigua haya sido construida de repente.

Esta misma lectura debe aplicarse al contenido narrativo asignado durante la partida: el algoritmo puede elegir cuándo y dónde se recupera un rastro, pero su existencia y procedencia deben resultar coherentes dentro de la ficción.

**Excepción futura posible:** si se diseña expresamente un evento de construcción o desplazamiento de una instalación, se documentará como tal; no debe deducirse del generador actual.

## 9. Preguntas abiertas que no deben resolverse por accidente

| ID | Cuestión | Decisión pendiente |
|---|---|---|
| **A-TIME-002** | Perfiles físicos de viaje | La tecnología general de motores antimateria está fijada (`C-TECH-003`–`006`); permanecen abiertos aceleración/frenado, velocidad efectiva por fase, masa de reacción y velocidad definitiva (candidata `0,5c`). |
| **A-TECH-001** | Viajes y combustible | Aborto, desgaste en tránsito, daños en ruta, perfiles físicos y semántica de consumo. |
| **A-TECH-002** | Segundo recurso de materia ordinaria | Posibilidad futura, aún no decidida, de recuperar y consumir también materia ordinaria. |
| **A-TECH-003** | Física de detalle | Masa de reacción, tobera, confinamiento de largo plazo y límites de las reservas. |
| **A-TECH-004** | Abastecimiento y agotamiento | Recuperación procedural y alternativas ante la falta total de antimateria, deliberadamente pendientes. |
| **A-TECH-005** | Desgaste y tiempo propio | Desgaste ordinario de sistemas y casco migrado a tiempo propio en T-04B2. Pendientes exposición ambiental por tramos, maniobras locales y cambios de velocidad durante el tránsito. |
| **A-TIME-003** | Modelo matemático de los relojes | Convención del tiempo galáctico, integración del tiempo propio y tratamiento coherente de la relatividad. |
| **A-BIO-001** | Químicos y condiciones de hibernación | Existencias, consumo, suministro, carencias y sus efectos mecánicos. |
| **A-BIO-002** | Daño y eficacia de `life_support` | Fórmula efectiva, umbrales, comportamiento en fallos y consulta al jugador. |
| **A-BIO-003** | Longevidad y salud del protagonista | Edad inicial, límites, deterioro fisiológico, enfermedades y consecuencias de envejecer. |
| **A-GRAV-001** | Implementación futura de gravedad fuerte | Entornos, parámetros de objetos compactos, peligros y cálculo de dilatación. |
| **A-COM-001** | Comunicaciones a larga distancia — parcialmente resuelta | A2/B/C2/D/E: alcance por potencia/sensibilidad, tres familias, propagación a c y escucha pasiva según comms. Abiertos repetidores, interferencias complejas, radio activa, direccionalidad avanzada y excepciones. / Partly resolved: power/sensitivity range, three families, propagation at c and passive listening gated by comms; repeaters, complex interference, active radio, advanced directionality and exceptions remain open. |
| **A-HIST-003** | Cronología galáctica | Fechas e hitos de expansión, fases regionales del colapso milenario y época presente del jugador. |
| **A-AUTO-001** | Naturaleza de los automatismos | Autonomía, capacidad de autorreparación, límites energéticos y posibles objetivos. |
| **A-DEC-003** | Ritmos de deterioro | Dependencia de entorno, tecnología, mantenimiento y paso del tiempo. |
| **A-DEC-004** | Distribución E1–E4 | Probabilidades por clase de objeto y región, si se desea modelarlas. |
| **A-SOC-001** | Situación de posibles sociedades supervivientes | Se desconoce si queda alguna sociedad humana viva; también su localización, estabilidad y posibilidad de alcanzarla. |
| **A-PLAYER-001** | Historia específica del protagonista | Origen, horizonte temporal, relación con la crisis y momento en que reconoce su esperanza. |
| **A-NAR-006** | Forma de la revelación dramática | Qué hallazgos y situaciones hacen comprender la búsqueda y la urgencia; estructura y desenlace no fijados. |
| **A-TIME-004** | Traducción jugable de la carrera temporal | Si existen cambios históricos dinámicos, extinciones simuladas, plazos o solo consecuencias narrativas del tiempo. |

Una historia o implementación puede trabajar con una de estas incógnitas, pero debe señalar su tratamiento como **hipótesis**, **perspectiva de un personaje** o **propuesta de nueva decisión canónica**.

## 10. Registro de decisiones y cambios

| Versión | ID | Resolución | Estado |
|---|---|---|---|
| 0.1 | `C-INF-001` | Infraestructura diseñada en parte para periodos milenarios. | Establecido |
| 0.1 | `C-INF-002` | Mantenimiento autónomo histórico y persistencia desigual. | Establecido |
| 0.1 | `C-INF-003` | Solo una fracción de las estructuras originales es localizable/recuperable. | Establecido |
| 0.1 | `C-DEC-001` | Cuatro estados: restos, ruina, conservación parcial, persistencia. | Establecido |
| 0.1 | `C-TIME-001` | Viajes muy largos; hibernación como vía práctica. | Establecido |
| **0.2** | `C-HIST-001` | Se precisa: el colapso humano fue extremadamente desigual y se extendió durante milenios. | Establecido |
| **0.2** | `C-NAR-003` | La esperanza del protagonista es encontrar una sociedad humana viva: el retorno a la humanidad. | Establecido |
| **0.2** | `C-NAR-004` | La arqueología orienta una investigación y la urgencia debe emerger progresivamente. | Establecido |
| **0.2** | `C-NAR-005` | El viaje tiene una estructura trágica: investigar y viajar consumen el tiempo de la esperanza. | Establecido |
| **0.2** | `C-DATA-003` | Los mensajes de emisores muertos hace mucho son un motivo recurrente. | Establecido |
| **0.2** | `A-SOC-001` | Existencia presente de sociedades supervivientes: desconocida también para el diseño. | Abierto |
| 0.1–0.2 | `A-TIME-002` | Velocidad efectiva y propulsión inicialmente sin fijar. | Abierto |
| **0.3** | `C-TIME-002` | Viajes necesariamente sublumínicos. | Establecido |
| **0.3** | `C-TIME-003` | Tres magnitudes: tiempo galáctico, propio de la nave y edad biológica acumulada. | Establecido |
| **0.3** | `C-BIO-001`–`003` | Hibernación química avanzada; envejecimiento no nulo, dependiente de `life_support` y recurso finito. | Establecido |
| **0.3** | `P-TIME-005` | Velocidad de crucero candidata `0,5c`; aún no implementada. | Provisional |
| **0.3** | `P-BIO-001` | Tasa nominal en hibernación `0,5 %` (`0.005`); configurable y pendiente de balance. | Provisional |
| **0.3** | `P-NAR-007` | Escala orientativa de 200 años galácticos entre grandes hitos. | Provisional |
| **0.4 — 2026-11-06** | `C-DATA-004` | Conocimiento limitado, cinco capas y procedencia legítima; diagnósticos explícitos de desarrollo separados. / Limited knowledge, five layers and legitimate provenance; explicit development diagnostics kept separate. | Establecido / Established |
| **0.3** | `C-GRAV-001` | Agujeros negros y dilatación gravitatoria intensa previstos para una fase futura. | Establecido como objetivo de mundo |
| **0.5 — 2026-11-09** | `C-TECH-001`–`007` | Mapa de diez sectores; reactor de fusión independiente; `engines` por aniquilación materia-antimateria con tres componentes; cápsulas confinadas en vacío y trampas electromagnéticas; degradación, reparación y mejoras; retirada prevista de `security` del jugador. | Establecido como diseño, pendiente de implementación |
| **0.5 — 2026-11-09** | `P-TECH-001`–`002` | Fórmula de consumo experimental, módulo de eficiencia al 20 % y 12 cápsulas iniciales. | Provisional, sujeto a pruebas |
| **0.5 — 2026-11-09** | `A-TECH-001`–`004`, `A-TIME-002` | Perfiles y física detallada, segundo recurso de materia, semántica de consumo y alternativas al agotamiento permanecen abiertos. | Abierto |
| **0.6 — 2026-11-10** | `C-TECH-008`–`009` | Selección de velocidad objetivo no local; independencia de mejoras de velocidad y eficiencia. | Establecido como diseño, pendiente de implementación |
| **0.6 — 2026-11-10** | `P-TECH-003`–`004` | Límites experimentales hasta 0.5c sin módulo y futura mejora hasta 0.8c; escalera provisional de consumo y criterios de pruebas de equilibrio. | Provisional, sujeto a simulación y recorrido jugable |
| **0.6 — 2026-11-10** | `A-TECH-005` | Discrepancia entre tiempo propio canónico y desgaste actual basado en tiempo galáctico; maniobras locales y cambios de velocidad durante el tránsito sin resolver. | Abierto |

Las referencias narrativas a miles de años son compatibles con el **colapso milenario** establecido; **ninguna fecha exacta, porcentaje de supervivencia, duración de viaje o final posible** se vuelve canónico por figurar en un ejemplo de lore. Las tasas `0,5c` y `0,5 %`, así como las cifras de consumo, eficiencia, velocidad y reservas de `P-TECH-001`–`004`, son **hipótesis de balance** hasta su validación.

## 11. Mantenimiento del documento

1. Toda decisión nueva debe indicar si **añade**, **precisa** o **sustituye** un principio existente.
2. Mantener identificadores estables; no reutilizar un ID retirado para otra idea.
3. Si cambia un hecho establecido, revisar sus consecuencias en arcos, singles, nodos, mecánicas y documentación.
4. Evitar reescribir silenciosamente archivos ya publicados: registrar el cambio de versión y, si procede, un resumen del impacto.
5. Las dudas se convierten en preguntas abiertas antes de convertirse en hechos.

El procedimiento operativo de revisión se desarrolla en [`guia_coherencia.md`](guia_coherencia.md).

**4D-3e5b — A-COM-001 parcialmente resuelta / partly resolved (2026-11-06).**
Se implementa el modelo pasivo simplificado del [contrato ES](../systems/radio-spacetime.es.md)
/ [EN contract](../systems/radio-spacetime.md). Sus perfiles y cifras son
provisionales, no canon definitivo. C-TIME-001/002/003 y C-DATA-004 se conservan;
recibir no demuestra actualidad ni supervivencia. / The simplified passive
model is implemented; profiles/numbers remain provisional, not definitive canon.
C-TIME-001/002/003 and C-DATA-004 remain; reception proves neither currency nor survival.
