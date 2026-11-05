# RETORNO — Canon del universo

**ID:** `RET-CAN`  
**Versión:** `0.3.0`  
**Fecha:** 2026-11-05  
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
- No se deducen viajes o comunicaciones instantáneos; el sistema de propulsión, las fases de aceleración/frenado y el cálculo relativista definitivo siguen pendientes.

### C-TIME-002 — Viaje estrictamente sublumínico [C]

Una nave con masa **no alcanza ni supera la velocidad de la luz**. La duración de los trayectos debe ser compatible con esta restricción. La existencia de rutas de navegación no implica un atajo superlumínico ni una alteración arbitraria de la causalidad. La propulsión concreta y sus perfiles de aceleración, frenado y consumo energético permanecen abiertos.

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

La candidata principal para el equilibrio interestelar es **la mitad de la velocidad de la luz**, aproximadamente `0,5 años luz/año` en el marco galáctico de referencia, durante la fase de crucero. El valor exacto, la aceleración, la desaceleración y su relación con el balance general **se verificarán antes de implementarse**. La velocidad actual del prototipo no se redefine por el hecho de documentar esta preferencia.

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

## 4. Conservación y desaparición de infraestructura

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

## 5. Cuatro estados de conservación

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

## 6. Información, señales y memoria

### C-DATA-001 — La información puede sobrevivir separada de sus sistemas [C]

La pérdida de una función operativa no implica necesariamente la destrucción de todos sus registros. Pueden sobrevivir archivos sellados, copias redundantes, cachés locales, transmisiones diferidas y fragmentos recuperables. En sentido inverso, un sistema con energía puede disponer de datos incompletos o inválidos.

### C-DATA-002 — Procedencia y temporalidad importan [C]

La mera recepción de un mensaje no prueba que su emisor siga vivo ni que su contenido sea actual. Para cualquier comunicación notable debe poder contemplarse si se trata de una transmisión nueva, una emisión automática, una reproducción, una caché recuperada o un mensaje retrasado.

El canon **no afirma** que todos esos mecanismos estén implementados ni establece aún la física definitiva de las comunicaciones interestelares.

### C-DATA-003 — Los mensajes de los muertos como motivo recurrente [C]

El viajero encontrará **una y otra vez mensajes cuyos emisores murieron hace mucho tiempo**. Pueden ser personales, rutinarios, administrativos, técnicos o íntimos; no todos deben anunciar una catástrofe ni estar redactados con solemnidad. Su fuerza deriva a menudo de lo cotidiano frente a la enorme distancia temporal.

Un mensaje puede conservar **verdad histórica** sin describir una **situación vigente**. La obra debe diferenciar, cuando importe, la fecha del hecho, la del registro, la de su transmisión o almacenamiento y la de su recuperación. La certeza sobre la muerte de un emisor tampoco debe inventarse en una fuente donde solo sea una conjetura.

## 7. Cómo interpretar la generación procedural

### C-WORLD-001 — Descubrir no es crear físicamente [C]

La aparición de una localización al explorar, escanear o resolver una ruta representa su incorporación al mundo **conocido por el jugador** o la materialización técnica de contenido del mundo; no significa que una estación antigua haya sido construida de repente.

Esta misma lectura debe aplicarse al contenido narrativo asignado durante la partida: el algoritmo puede elegir cuándo y dónde se recupera un rastro, pero su existencia y procedencia deben resultar coherentes dentro de la ficción.

**Excepción futura posible:** si se diseña expresamente un evento de construcción o desplazamiento de una instalación, se documentará como tal; no debe deducirse del generador actual.

## 8. Preguntas abiertas que no deben resolverse por accidente

| ID | Cuestión | Decisión pendiente |
|---|---|---|
| **A-TIME-002** | Propulsión y perfil real de velocidad | Aceleración/frenado, velocidad efectiva en cada fase, energía y velocidad definitiva (candidata `0,5c`). |
| **A-TIME-003** | Modelo matemático de los relojes | Convención del tiempo galáctico, integración del tiempo propio y tratamiento coherente de la relatividad. |
| **A-BIO-001** | Químicos y condiciones de hibernación | Existencias, consumo, suministro, carencias y sus efectos mecánicos. |
| **A-BIO-002** | Daño y eficacia de `life_support` | Fórmula efectiva, umbrales, comportamiento en fallos y consulta al jugador. |
| **A-BIO-003** | Longevidad y salud del protagonista | Edad inicial, límites, deterioro fisiológico, enfermedades y consecuencias de envejecer. |
| **A-GRAV-001** | Implementación futura de gravedad fuerte | Entornos, parámetros de objetos compactos, peligros y cálculo de dilatación. |
| **A-COM-001** | Comunicaciones a larga distancia | Alcance, latencia, repetidores, disponibilidad y excepciones. |
| **A-HIST-003** | Cronología galáctica | Fechas e hitos de expansión, fases regionales del colapso milenario y época presente del jugador. |
| **A-AUTO-001** | Naturaleza de los automatismos | Autonomía, capacidad de autorreparación, límites energéticos y posibles objetivos. |
| **A-DEC-003** | Ritmos de deterioro | Dependencia de entorno, tecnología, mantenimiento y paso del tiempo. |
| **A-DEC-004** | Distribución E1–E4 | Probabilidades por clase de objeto y región, si se desea modelarlas. |
| **A-SOC-001** | Situación de posibles sociedades supervivientes | Se desconoce si queda alguna sociedad humana viva; también su localización, estabilidad y posibilidad de alcanzarla. |
| **A-PLAYER-001** | Historia específica del protagonista | Origen, horizonte temporal, relación con la crisis y momento en que reconoce su esperanza. |
| **A-NAR-006** | Forma de la revelación dramática | Qué hallazgos y situaciones hacen comprender la búsqueda y la urgencia; estructura y desenlace no fijados. |
| **A-TIME-004** | Traducción jugable de la carrera temporal | Si existen cambios históricos dinámicos, extinciones simuladas, plazos o solo consecuencias narrativas del tiempo. |

Una historia o implementación puede trabajar con una de estas incógnitas, pero debe señalar su tratamiento como **hipótesis**, **perspectiva de un personaje** o **propuesta de nueva decisión canónica**.

## 9. Registro de decisiones y cambios

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
| **0.3** | `C-GRAV-001` | Agujeros negros y dilatación gravitatoria intensa previstos para una fase futura. | Establecido como objetivo de mundo |

Las referencias narrativas a miles de años son compatibles con el **colapso milenario** establecido; **ninguna fecha exacta, porcentaje de supervivencia, duración de viaje o final posible** se vuelve canónico por figurar en un ejemplo de lore. Las tasas `0,5c` y `0,5 %` son **hipótesis de balance** hasta su validación.

## 10. Mantenimiento del documento

1. Toda decisión nueva debe indicar si **añade**, **precisa** o **sustituye** un principio existente.
2. Mantener identificadores estables; no reutilizar un ID retirado para otra idea.
3. Si cambia un hecho establecido, revisar sus consecuencias en arcos, singles, nodos, mecánicas y documentación.
4. Evitar reescribir silenciosamente archivos ya publicados: registrar el cambio de versión y, si procede, un resumen del impacto.
5. Las dudas se convierten en preguntas abiertas antes de convertirse en hechos.

El procedimiento operativo de revisión se desarrolla en [`guia_coherencia.md`](guia_coherencia.md).
