========================
=== NEW TODO ===
========================

=== BALANCE ===

El adecuado balance de la dificultad debe ser un objetivo prioritario del desarrollo de RETORNO. No se puede esperar a que el juego esté muy desarrollado para empezar a tratar este asunto, pues resulta muy difícil lograr un equilibrio satisfactorio (divertido y que mantenga la tensión) cuando ya hay demasiadas variables. Hay que preocuparse de este equilibrio desde el principio. Empezando por la economía del juego. 

En el juego hay varios recursos actualmente, pero hacen falta más, a fin de encontrar tensiones más interesantes. Ahora mismo los recursos son: el scrap, el tiempo de juego real, el tiempo de juego diegético (y, en breve, está previsto introducir el tiempo biológico del PJ) y la energía. Por ahora la energía forma parte de su propio sistema/juego de economía, así que quizá no convenga mezclar con los otros (la economía energética tendrá más relevancia en el momento en que haya combate o situaciones en las que haya que reaccionar rápido y se dependa de un sistema en particular para sobrevivir). En efecto, comom dice chatGPT, en RETORNO se da una peculiaridad interesante: EL BALANCE ENERGÉTICO ES UN PROBLEMA DISTINTO DEL BALANCE DE MATERIALES.

La cuestión interesante de diseño es que la energía no tiene por qué funcionar únicamente como una cuenta atrás hasta la muerte. Puede ser una herramienta para crear decisiones estratégicas. Por ejemplo, el jugador podría apagar sensores para ahorrar energía, pero eso reduciría su conocimiento del entorno. Podría desconectar un sistema de reparación automática y destinar la energía a los motores. O quizá tenga que posponer una operación de salvamento para conservar una reserva de emergencia. Lo fundamental es que cada alternativa tenga un beneficio y un coste reconocibles. Y aquí aparece otra variable fundamental: el tiempo. Si recuperar recursos, viajar, reparar o investigar consume tiempo, y durante ese tiempo la nave sigue consumiendo energía, entonces el tiempo también se convierte en un recurso económico. Este tipo de interdependencias permite construir sistemas estratégicamente ricos a partir de unas pocas mecánicas.

En RETORNO buscamos que el jugador experimente escasez, incertidumbre, vulnerabilidad, satisfacción al recuperar una nave deteriorada y una sensación de conquista cuando consigue operar sistemas que antes eran inviables. El balance debería estar al servicio de esas experiencias.

Una idea crucial: una economía sostenible no es necesariamente una economía equilibrada en términos de diversión. Podríamos diseñar una economía perfectamente sostenible que fuera aburridísima: el jugador siempre consigue exactamente la cantidad de recursos que necesita y jamás tiene que elegir. Y podríamos diseñar una economía deficitaria que resultara fascinante: el jugador sabe que sus recursos se agotarán y necesita encontrar una solución antes de que eso suceda. En el caso del tiempo biológico del PJ, buscamos claramente una economía deficitaria: el jugador sabe que se le agota el tiempo, y eso presiona (al principio no mucho), pero poco a poco cada vez más, para encontrar una solución. La economía del resto de recursos, sin embargo, deberá ser una economía en la que tendrá que tomar decisiones y luchar a fin de conseguir la sostenibilidad. A veces la sostenibilidad de un subsistema será en detrimento de la de otro.

Tiene que haber zonas totalmente innaccesibles para el jugador hasta que no esté lo bastante preparado.

Para RETORNO, parece que son más apropiadas las retroalimentaciones negativas que las positivas. Por ejemplo: Más drones operativos → mayor coste de mantenimiento → menor excedente disponible para adquirir nuevos drones. El sistema dispone de un mecanismo que limita su propio crecimiento. Otro ejemplo: Menos energía disponible → desactivación de sistemas secundarios → reducción del consumo → mayor autonomía restante. Esta segunda posibilidad es especialmente interesante. El sistema no devuelve gratuitamente energía al jugador: le permite conservarla si acepta operar con menos capacidades.

Los bucles positivos tienden a amplificar diferencias, mientras que los negativos pueden estabilizar los sistemas. Esta distinción aparece expresamente en la literatura de diseño de juegos, incluyendo Rules of Play: Game Design Fundamentals.

PRINCIPIOS de diseño para RETORNO

Las malas decisiones deben poder tener consecuencias graves, incluso irreversibles, pero el jugador debería disponer de oportunidades razonables para anticiparlas y evitarlas. (Política frente a espirales de muerte)

El juego debería ser exigente en la planificación, la gestión de la incertidumbre y la administración de recursos, pero procurar que el esfuerzo rutinario tenga una función concreta y no sustituya a la dificultad estratégica.

La recuperación de capacidades debe producir satisfacción real, sin eliminar permanentemente la necesidad de tomar decisiones difíciles.



Hay que hacer estudios de balance. Empezando por un estudio del scrap. Tiene que haber scrap suficiente pero no de sobra. La buena administración del scrap tiene que ser vital para la supervivencia. El equilibrio entre el ingreso y el gasto del scrap tiene que ser tenso. Aumentar ingresos tiene que ser en detrimento de algo. Reducir gasto debe ser también en detrimento de algo. Ahora mismo, lo que presiona al jugador es el desgaste de la nave (creo que el desgaste se produce únicamente por radiación, o quizá tenga un desgaste por envejecimiento añadido). Por otra parte, cuando desarrollemos el sistema avanzado de salvage, el jugador tendrá la opción de ejecutar salvage automatizado (como el actual), que lleva menos tiempo de juego y tiempo real, pero recupera menos scrap, o salvage automatizado, que lleva más tiempo de juego y de tiempo real, y es más arriesgado, pero más lucrativo en scrap y otros recursos.

Los módulos o mejoras para la nave y drones deben formar parte del balance de dificultad del juego. Actualmente no tienen un gran impacto. Cuando diseñemos el sistema de salvage avanzado lo empezarán a tener mayor, pero no podemos esperar a ello para empezar a hacer tareas de balance en este sentido. Propongo que el juego, con sistema de salvage automatizado, tenga que ser un juego a su modo completo en sí mismo, divertido y tenso de jugar, con necesidad de tener que tomar decisiones estratégicas y tácticas.

- [] Viajar debe consumir algún recurso, además de tiempo y deterioro de la nave (e.e. scrap indirectamente). Algún combustible.

- [] La reparación de drones de debe ser gratuita.
Pero esto tiene que dar lugar a decisiones, como por ejemplo (es un ejemplo que para nuestro caso no aplica, pero bueno): si tienes 80 scrap, tienes que decidir entre reparar generadores (y mejorar la autonomía de la nave) o reparar el dron (y mejorar la capacidad de obtención de recursos). No es necesario que todas las opciones tengan exactamente el mismo valor. Lo deseable es que su valor dependa de las circunstancias, los objetivos y las prioridades del jugador.

En diseño económico, un concepto fundamental es el coste de oportunidad: aquello a lo que renunciamos al elegir una opción. Si la chatarra es tan abundante que podemos repararlo todo sin esfuerzo, el coste de oportunidad desaparece. Y con él, buena parte del interés estratégico. El problema actual en este sentido en RETORNO es que no hay verdadero coste de oportunidad de nada porque no hay nada a lo que el jugador pueda renunciar (que yo sepa). Todo es vital.

La escasez no es únicamente un obstáculo. Es también el mecanismo que hace que nuestras decisiones importen. Pero tampoco queremos llevarla al extremo. Si los recursos son tan escasos que el jugador solo puede permitirse una estrategia viable, volvemos a perder diversidad de decisiones. Por tanto, tanto la abundancia excesiva como la escasez extrema pueden empobrecer el juego.

- [] Hay que aumentar el coste actual de reparación en scrap. O disminuir el scrap inicial. O ambos.

=== SIN CLASIFICAR ===

- [] Implementar medios interlestelares: ya tenemos la radiación ambiental en los esencial, pero interesa añadir riesgos ligados al movimiento relativista, como partículas energéticas incidentes, colisiones con polvo y erosión del blindaje. Estos efectos dependerían de la velocidad, del medio interestelar atravesado y de las protecciones de la nave.

- [] Que el jugador pueda decidir la velocidad de viaje (0.3c o 0.5 si tiene 'engines' en 'nominal', y posibilidad de viajar a 0.8c si tiene el módulo que le permite 'upgraded').

- [] Módulo de menor consumo de antimateria. Y módulo (otro módulo independiente) de más velocidad de viaje (hasta 0.8c)

- [] La nave tiene que tener una capacidad máxima de 4 módulos.

- [] Al inicial el viaje debe sonar un sonido de motores funcionando (más, quizá, una explosión acto seguido).

- [] Un comando para poder auditar el estado de los distintos sistemas. Sería simplemente para mejorar la inmersiónd el juego, sin mayores consecuencias. El estado de los distintos sitemas de la nave (core_os, life_support, sensors, etc.) se considera una abstracción, pero la auditoría técnica puede dar información más detallada (sólo para la sensación de inmersión en el juego) de los problemas que está teniendo cada una de las partes. Por ejemplo auditorías técnicas que revelasen el estado particular del alimentador, la cámara y el sistema de empuje (sin tener que convertirlos necesariamente en tres sistemas independientes). [P.D. Actualmente el comando 'diag' ya está implementado. Decidir si valdría con ampliar ese, o modificar su fucnionamiento; en principoio sería interesante que 'diag' llevara algo de tiempo, y que diera un informe diegético inmersivo más completo.

- [] Virus informáticos! Al hacer uplink puede haber un riesgo de que data_core sea infectado con algún virus (cada uno de esos virus puede tener distintos efectos en la nave, algo así como las maldiciones de un roguelike tradicional). Así mismo habrá que implementar algún módulo que añade función de antivirus. O quizá que la nave tenga desde el principio un servicio de antivirus básico, pero que el módulo lo mejore. O que haya algún consumible (quizá esto sea mejor idea), de un solo uso, que te permite librarte de un solo virus por uso (cada tipo de consumible sirve para un tipo de virus: por ejemplo, un virus que te impide usar los sensores tendría a su vez un "antídoto" que limpia ese virus en particular).	

- [] Ahora mismo los sensores solo sirven para route solve y para scan. Hace falta añadir algún tipo de sensor pasivo o sonar pasivo/activo, que sirva para detectar peligros, para que así la decisión de apagar los sensores (y ganar energía) no sea gratis.

- [x] Actualmente, a la hora de configurar dónde pueden aparecer los documentos de un arco y/o las estaciones/pecios/etc. relativos a él, podemos configurar el rango de distancia, con respecto al origen de la partida, a la que pueden aparecer esos documentos. No podemos configurarlo para que los documentos aparezcan dentro de un rango de distancia con respecto a una estación o nodo en particular. Si quisiéramos distribuir documentos a un máximo de 15 años luz de Liria, por ejemplo, necesitaríamos diseñar una solución concreta; no existe un parámetro genérico equivalente a max_dist_from_node: "LIRIA". Necesitamos desarrollar esa solución.

- [!] LORE — Mejorar la búsqueda de emplazamientos mediante anclas espaciales. Actualmente, la búsqueda de hosts históricos para documentos esenciales examina un conjunto limitado de sectores (presupuesto de 64). Aunque existan estaciones que cumplan una restricción como anchor_distances (por ejemplo, a menos de 15 ly de Liria), pueden quedar fuera de la búsqueda. Solución propuesta: implementar una búsqueda centrada en el volumen espacial alrededor de las entidades de referencia, con presupuestos progresivos y resultados que distingan entre ausencia real de candidatos y búsqueda incompleta. No crear nodos ni rutas artificiales.

- [!] LORE — Optimizar el cálculo de distancias relativas. Actualmente, al evaluar posibles emplazamientos, se calculan distancias a entidades authored incluso para documentos que no utilizan anchor_distances. Este trabajo innecesario podría afectar al rendimiento cuando aumente el número de localizaciones y piezas narrativas. Solución propuesta: calcular únicamente las distancias a las anclas referenciadas por cada documento y reutilizar resultados cuando sea posible, manteniendo el determinismo y sin alterar las reglas de colocación.

- [] Existe un límite de drones que se pueden tener? Limitar a 4.

- [] Aumentar el tiempo que se tarda en acoplarse (dock).

- [x] Quiero un nuevo escenario de inicio: FAST_SANDBOX. La idea es empezar el juego con todos los sistemas reparados, todo el salvage disponible en ECHO_7 ya recuperado (incluida la información recuperable con uplink), el o los drones en su bahía y en perfecto estado, y la nave orbitando alrededor de ECHO_7, lista para iniciar el primer viaje. Quiero también incluir en el readme las instrucciones para ejecutar el juego desde los distintos escenarios, pero aclarando que el escenario SANDBOX y FAST_SANDBOX están en principio pensados exclusivamente para depuración de errores y pruebas de diseño.

- [!] Si no existen ya, necesitamos un comando debug que imprima los nodos materializados (incluidos lo que no conoce aún el jugador), y otro que te permita teletransportarte inmediatamente a cualquier nodo.

- [] Cada vez que cambia el estado de alguno de los sistemas de hardware recibo dos mensajes que en principio parecen redundates. Por ejemplo, tras un 'power on comms':

[CMD] [WARN] system_state_changed :: comms: offline -> limited (cause=manual_restore, health=0.72)
[CMD] Radio Communications Service (radiod): stopped (Try: boot radiod)
[CMD] [INFO] system_power_restored :: Power restored: comms (offline -> limited)

La primera línea y la tercera, ¿no son redundantes? Entiendo que el WARN está avisando cada vez que hay un cambio en el estado de un sistema de la nave. Esto es lo deseable en el caso de que el sistema cambie a un estado a peor (por ejemplo, de 'nominal' a 'limited'), pero no cuando cambia a mejor (por ejemplo de 'limited' a 'nominal'). Tampoco hace falta que se imprima un WARN cuando se enciende o apaga un sistema de la nave si el encendido o apagado lo ha ejecutado el jugador manualmente (en este caso, basta con la notificación INFO.

- [] He recibido por primera vez una señal de radio. El archivo tiene el nombre "radio_0017.en.txt". Por qué el número 0017, si es la primera señal de radio que recibo?

- [] Si no existe ya, necesitamos un comando 'delete' para borrar documentos.

- [] Capturo de forma más o menos habitual señales de radio como esta:

=== CAT /logs/broadcasts/radio_0017.en.txt ===                                                                                        
  AUTOMATED NAVIGATION NOTICE                                                                                                           
  Old data; present validity unverified.                                                                                                
  Calculated navigation solution; no evidence of historical traffic.                                                                    
  LINK: P-1.2.0.1 -> P-0.2.1.0
                                                                                                                                        
  (intel) route added: P-1.2.0.1 -> P-0.2.1.0

Qué tipo de señar de radio se supone que es esta? Es decir, qué explicacón diegética tiene?

- [] El otro tipo de señal de radio que suelo capturar es como esta:

=== CAT /logs/broadcasts/radio_0018.en.txt ===                                                                                        
  AUTOMATED ARCHIVE SIGNAL
  Recording age and reliability uncertain. Reception does not establish present human activity.                                         
  Historical distress recording: loss of control reported. Present situation and survival unknown.

¿Son mensajes generados proceduralmente? ¿Qué tipos de señales procedurales existen actualmente en el juego? Me gustaría poder editarlos.

- [] Si hago "cat logs/boot.log" obtengo este resultado:

  Access denied: requires ENG
  
¿Qué quiere decir? ¿Cómo se consigue actualmente en el juego acceder a documentos de este tipo?

- [] Al hacer un 'drone survey' obtengo una salida como esta:

[AUTO] Survey completed at ECHO_7                                                                                                     
  === SURVEY ===                                                                                                                        
  scrap detected: 13
  modules detected
  no recoverable drones detected
  possible recoverable data signatures detected
  uplink-capable infrastructure detected
  depletion: scrap=no, data=no, extras=no
  node not cleaned
  
Me gustaría que el output no mostrara lo no detectado (como, en este caso "no recoverable drones detected"), sólo lo sí detectado (o lo posible, como en este caso "possible recoverable data signatures detected"). Por otra parte, las líneas "depletion: scrap=no, data=no, extras=no" y "node not cleaned" sólo deberían ser visibles en modo debug.
  
- [] El sistema temporal del juego. Los tres relojes (tiempo galáctico, tiempo de la nave y tiempo biológico del personaje). Hay una conversación al respecto guardada en chatGPT (dentro de la conversación "CANON de RETORNO", sino recuerdo mal). Checkear y partir de ahí.

- [!] Al hacer un ship survey, cuando la distancia del objetivo no llega a 1ly, hay que dar la distancia en alguna unidad menor, para que no aparezca simplemente 0.00ly.

- [!] Situado en WAYSTATION_679A8E, a unos 25.35ly de distancia de ARCHIVE_01 (es decir, estando ARCHIVE_01 muy lejos del rango de los sensores), veo que puedo ejecutar sin problema la orden "ship survey ARCHIVE_01", y además que el comando "ship survey" me autocompleta el nombre de todos los destinos conocidos. Entiendo que esto no es correcto. Si la operación "ship survey" requiere tener encendidos data_core y sensors entiendo que es porque para obtener esa información hace falta usar ambos sistemas. Pero aquí hace falta distinguir dos cosas: a) la obtención de información NUEVA (mediante "ship survey") de un objetivo que se encuentra dentro del rango de los sensores, y b) la recuperación de la información ANTIGUA obtenida por ese mismo procedimiento. Para "b" no tiene sentido necesitar tener encendido el sistema sensors (y data_core tampoco). Se supone que simplemente se está recuperando información ya obtenida en el pasado. Para la recuperación de información archivada quizá haría falta un comando diferente a "ship survey", y reservar "ship survey" únicamente para la operación de obtener información de un objetivo en torno al cuál se está orbitando (y, en consecuencia, sólo debe autocompletar el nombre del objeto en torno al cuál se está orbitando). Además, actualmente la operación "ship survey" es inmediata (no tiene ETA). No debería ser así. Debería llevar un tiempo llevar a cabo esa operación.

- [] Existen textos procedurales que no contienen rutas. La función build_procedural_salvage_mail_content() genera informes de telemetría con información sobre el lugar: tipo de instalación, región, integridad de la caché, señales de deterioro y referencias a su entorno. Estos textos no son arcos ni singles. Son documentos generales producidos a partir de las características de la localización. No constituyen todavía un sistema narrativo procedural especialmente rico, pero sí proporcionan contenido ambiental básico. Debemos desarrollar un sistema narrativo procedural más rico.

- [] El sistema de descubrimiento tiene oportunidades finitas. Un uplink puede agotarse. Un nodo puede no tener enlaces útiles. Un scan puede no encontrar contactos nuevos. Y F-DEAD-01 tampoco garantiza una salida universal. Por tanto, no podemos concluir simplemente por la existencia de estos sistemas que todas las semillas permitan una exploración prolongada y satisfactoria. Necesitamos alguna manera de comprobar cómo de probable es una bloqueo exploratorio, y desarrollar las contramedidas necesarias para evitarlo o minimizarlo en lo posible (existe documentación en el repositorio explicando en detalle qué es un bloqueo exploratorio y qué está pendiente de investigar en este sentido).

- [!] Para **calcular una ruta nueva**, los requisitos actuales son:

| Sistema o servicio | Requisito |
|---|---|
| `core_os` | **NOMINAL o UPGRADED**. En LIMITED ya bloquea `route solve`. |
| `sensors` | **LIMITED o superior**, encendido. |
| `sensord` | Instalado y **en ejecución**. |
| `energy_distribution` | **NOMINAL o superior**, por la dependencia de `sensors`/`sensord`. |
| Alimentación | **Q ≥ 0.55**, sin `brownout` ni estado crítico de potencia. |

No exige `data_core`/`datad` ni `comms`/`radiod`. Tampoco exige un estado concreto de `power_core`: debe proporcionar alimentación suficiente para cumplir las condiciones anteriores. Durante el cálculo deben mantenerse **`sensors ≥ LIMITED` y `sensord` en ejecución**; si dejan de cumplirlo, el trabajo falla. Me gustaría que, para calcular una nueva ruta ("route solve"), además de los requisitos actuales, se requiera tener data_core LIMITED o superior y encendido, así como "datad" instalado y en ejecución.

- [x] Desde los últimos cambios la hibernación ahora tarda mucho en ejecutarse. Pasa lo mismo con la orden wait del modo debug: si haces wait 5 no se nota, pero wait 300 tarda unos 15s en ejecutarse, y wait 3000 tarda demasiado (no sé cuánto porque no he tenido paciencia y he matado el proceso del juego, pensando que podría haberse bloqueado el programa). Un viaje de 15.23ly hibernando tarda 1 minuto y 21 segundos aproximadamente en ejecutarse. Me parece excesivo. Antes de los últimos cambios esto no sucedía. El salto era prácticamente inmediato. ¿A qué se debe? Si no fuera posible reducir el tiempo de espera, haría falta indicárselo al jugador de alguna manera, pues de otro modo parece simplemente que el juego se ha quedado bloqueado.

- [BUG] Haciendo algunas pruebas, he apagado core_os a ver qué pasa. Tras apagarlo he tratado de encender el sistema security y el juego a crasheado. He vuelto a cargar la partida, y al cargar core_os estaba encendido. Lo he vuelto a apagar, y he tratado de encender sensors, y de nuevo crasheo.

- [BUG?] El survey me dice que "possible recoverable data signatures detected" y en "depletion" dice "data=no". Sin embargo cuando hago un "drone salvage data" sale el mensaje "Salvage blocked: node WAYSTATION 679A8E has no data interfaces".

- [] He recibido el mensaje "Battery low: SoC=0.40. Consider reducing load". Hay que estar seguros de que ese mensaje no sale si la batería se está cargando. Es decir, debe salir cuando se cruza hacia abajo cierto umbral (o sea, si la batería se está descargando), pero no si se cruza hacia arriba (la batería se está cargando), pues de otro modo puede resultar confuso.

- [] Cuando sale la alerta de que la radiación del drone desplegado es elevada, es difícil saber qué hacer. Quizá no estaría mal una sugerencia de mandar el drone a su baía para limpiarlo de radiación.

- [] En el output de drone survey, las líneas "depletion:" y "node cleaned" o "node not cleaned" entiendo que deberían ser exclusivas del modo debug, no? Lo digo porque esa es una información que en principio el jugador no tendría que conocer. Como mucho, podría salir un mensaje diciendo "node cleaned" pero que advirtiera de que el informe del drone puede no ser completo/exacto.

- [!] Hace falta un comando que te liste qué destinos sin ruta conocida (desde la posición actual) cumplen las condiciones como para hallar una ruta hacia ellos mediante un "route solve" exitoso. Es decir, el jugador debe poder sabe qué destinos pueden ser alcanzables desde su posición mediante un "route solve" y cuáles no.

- [!] Tras escribir "nav map galaxy local " (o su versión abreviada "nav galaxy local "), si le doy a tab admite el autocompletado del nombre de varios nodos, pero por sintaxis no es correcto: el comando "nav map galaxy local" no admite ningún argumento más. Lo mismo pasa con "nav galaxy global", "nav galaxy regional", y "nav galaxy sector". Podríamos incluir la funcionalidad de imprimir el mapa conocido local o sectorial o regional del <node_id> que se introduzca como parámetro. Pero no tiene sentido "nav galaxy global <node_id>.
 
- [] Cada vez que se despierta de una hibernación, debería sonar el sonido que suena al iniciar una partida nueva. Los sonidos son parte esencial de la inmersión de RETORNO.

- [] Parece que 'module inspect' autocompleta todos los módulos existentes del juego, pero debería autocompletar únicamente el nombre de los módulos que disponga el jugador.

- [] Cuando el viaje va a durar varios meses, quizá estaría bien un mensaje sugiriendo la posibilidad de hibernar. Al introducir la orden de hibernación, debería también salir un mensaje advirtiendo de los peligros de viajes largos (deterioro de la nave, daño por radiación, eventos imprevistos, etc.), así como sugiriendo revisar antes la disponibilidad de recursos suficientes (por ahora, scrap; más adelante habrá más recursos en el juego) para llevar a cabo las operaciones de reparación/mantenimiento al despertar.

- [] Sería importante un comando que imprimiera la ruta que se ha seguido, es decir, todos los lugares (en orden) a los que se ha viajado, con fecha de llegada, etc. Es decir, una especie de cuaderno de bitácora.

- [] El comando "nav map path" no autocompleta todos los destinos conocidos. Debería.

- [] Hay actualmente alguna manera de arreglar el hull de la nave?

- [] No me gusta que cuando entra una notificación nueva en la ventana de logs o en la de jobs el scroll baje automáticamente hasta la última línea impresa. Si estoy leyendo un texto quiero poder seguir leyéndolo sin interrupciones. Para saber que hay alguna novedad ya están las notificaciones sonoras.

- [] Al hibernar la música debería detenerse.

- [!] Si se ordena apagar manualmente sensors, pero hay un trabajo en proceso que depende de sensors, como "route solve", debería aparecer un mensaje de confirmación. Lo mismo al intentar apagar manualmente otros sistemas mientras hay pendiente o en proceso un trabajo o tarea que depende de él. Esto evitaría perder por error el tiempo invertido en una operación.

- [] Estaría bien que en algún lugar se indicase cuál es el "sensor range" del comando "route solve" (y que existiera un módulo que lo ampliara, si no existe ya).

- [] La radiación se acumula? Hay alguna manera de limpiar la radiación de la nave?

- [] ¿Qué pasa si desatraco de una nave/estación y me dejo un dron en ella? Podría recuperarlo si vuelvo a atracar en la misma nave/estación y le queda batería al dron? Perdería la comunicación con el dron al marcharme de ese nodo?

- [] ¿Cómo funcionan actualmente los sistemas core_os y life_support? ¿Qué pasa si se apagan? ¿Qué cosas dependen de ellos?

== CAMBIOS PARA HACER EL JUEGO MÁS ACCESIBLE ==

La falta de un tutorial es parte de la diversión. Aprender a jugar es parte del puzzle inicial. Y no sólo es eso: que el jugador tenga que averiguar cómo funcionan las cosas, y qué hacer, tiene a su modo sentido dentro de la historia, pues hay que tener en cuenta que el personaje jugador se despierta después de no se sabe cuántos años en una cámara de criogenización, y se supone que no recuerda nada. Ahora bien, en el estado actual del juego la curva de aprendizaje es excesiva. Se deberían dar algunas pistas más de qué hacer, sobre todo una vez arreglados los principales sistemas (quizá recibir un mensaje de ECHO_7 al encender los sistemas de comunicaciones por primera vez, que le dé a entender al jugador de algún modo que puede viajar a ECHO_7 y acoplarse?). O la opción de activar un pequeño tutorial diegético. Aquí van algunas ideas:

- [] diseñar correctamente (y diegéticamente) las pistas/informaciones que recibe el jugador en los primeros minutos de juego, de forma que aprenda él sólo a usar el juego, a entenderlo, y a deducir qué hacer, pero sin que llegue a tener la sensación de estar haciendo un tutorial Esto sería mucho más diegético, y pienso que más gratificante.
- [] Al llegar de nuevas al juego, el nombre (del proceso) "sensord" no es quizá muy intuitivo ni descriptivo ni inmersivo (¿qué tipo de software es "sensord"?). Además, es facil de confundirlo con "sensors" y no entender entonces la diferencia entre el sistema "sensors" (hardware) y el servicio "sensorsd" (sofware). Uno es un sistema y el otro un servicio/demonio. Esto debería ser quizá más claro. Lo mismo sucede con "datad".
- [] Me está costando averiguar qué hacer después de reparar los sistemas. He recordado que había que descubrir ECHO_7 y viajar a él, pero no es algo que haya logrado deducir por mi cuenta. No queremos guiar al jugador de la mano, pero sí darle las pistas iniciales necesarias como para que pueda resolver el puzzle y que no sea excesivamente difícil, pues no queremos que el jugador nuevo se frustre antes de tiempo y abandone y se quede sin descubrir el potencial de RETORNO. Quizá se podría dar alguna pista que le lleve al jugador a entender que está cerca de un relé llamado ECHO_7, y que puede viajar hasta él (entrar en su órbita) y atracar en él, de forma que una vez arreglados los sistemas al menos tenga un objetivo claro. Ahora mismo tengo la sensación de que el jugador, una vez arregla los sistemas, la única manera que tiene de averiguar qué hacer es leyendo el output del comando help, y probando cosas. 'Help' es y debe ser, sí, parte de las herramientas de que dispone el jugador para descubrir qué pude hacer, pero no debe ser la única. Lo ideal sería que al arreglar y encender "comms" capturase una comunicación del relé ECHO_7, diciendo algo que le de a entender al jugador que está ahí cerca y que puede atracar en él. 
- [] Incluso sabiendo que debo viajar a ECHO_7, resulta difícil averiguar que se debe primero ejecutar "route solve" para poder viajar a ECHO_7. Debería informársele o sugerírsele de ello al jugador de algún modo. Quizá la solución podría ser esta: cuando se intenta una navegación a una localización para la que no se dispone de ruta directa conocida y salta el mensaje de bloqueo, que salte también un mensaje diciendo que si el objetivo está dentro de los límites (hay que especificar más claro cuáles son esos límites) puede probar a calcular una ruta con "route solve <node_id>".
- [] También puede resultar difícil saber qué hacer una vez se ha atracado en ECHO_7. He usado uplink gracias a que al verlo en el output del help he recordado que era parte de la rutina cuando se atraca en un nodo, pero no sé si un jugador nuevo sería capaz de averiguarlo en un tiempo razonable. En el output del comando "routes" se da una pista, pero estaría bien que hubiera alguna otra más. También puede costar entender que hay que usar los drones para entrar en ECHO_7, o incluso entender qué es ECHO_7. Quizá al iniciar el juego por primera vez podría salir un mensaje preguntántole al jugador si quiere activar el sistema de consejos hasta recordar de nuevo cómo operar; de modo que, estando esos consejos activos, al atracar por primera vez en ECHO_7 saltase el consejo de hacer uplink (y la sugerencia de "man uplink" para más información). Valorar otras formas de guiar al jugador a este respecto.
- [] Sucede lo mismo con los comandos de navegación: hay muchos comandos, y quizá puedan abrumar a los jugadores menos pacientes al principio, o dificultarles entender qué es qué y para qué. Los manuales están bien, pero sería preferible que el jugador no tuviera que invertir tanto tiempo leyendo manuales antes de empezar poder pasar a la acción. Yo soy personalmente un jugador que me gusta leer manuales, y soy paciente, y me gustaría satisfacer en este sentido a otros jugadores como yo, pero también me gustaría pensar en jugadores que necesitan pasar a la acción más rápido.
- [] En el output del comando routes propongo cambiar el texto "Try: scan,route solve, intel, uplink (at relay/waystation), or acquire intel" por otro (localizado) que pueda resultar de más ayuda; quizá esto: "Try: scan, route solve, intel, uplink (docked at relay/waystation), or acquire intel via drone salvage".
- [] Se me ocurre que podría estar bien un pequeño sistema de consejos que podría funcionar del siguiente modo: si el jugador no ha usado nunca un comando en particular, cada cierto tiempo se podría disparar un breve consejo mencionando la existencia de ese comando y un muy breve descripción (siempre localizada) de qué hace o para qué sirve. De este modo el jugador irá conociendo los distintos comandos y posibilidades de RETORNO. Algo del estilo a un "¿Sabía que...?", que suelen tener algunos programas. Este sistema de consejos debería poder desactivarse.
- [] Diseñar un sistema para catalogar documentos bajo etiquetas. O sea, que el jugador pueda crear, por ejemplo la etiqueta AMANECER y decidir qué documentos van a tener esa etiqueta. De forma que pueda ir clasificándolos a su gusto por hilos narrativos.




===================================================================
=== TAREAS ANTIGUAS (¡REVISAR!). ALGUNAS PUEDEN ESTAR OBSOLETAS ===
===================================================================

=== PROLOGUE ===

- [ ] La primera vez que se ejecuta el juego no debe fallar nunca el deploy!.


=== DRONES ===

- [ ] No estoy seguro de que se estén generando drones recuperables en los nodos. Confirmar.

- [ ] Necesitamos que se puedan recuperar (salvage) nuevos drones. Una sub-orden nueva: 'drone salvage drone' (que admita también el plural 'drone salvage drones'). Estoy incluye incluir tablas apropiadas en los hubs authored y correspondientes ajustes en la generación procedural del botín.

- [ ] La orden "drone deploy <drone_id> <sector_id>" debería volver a admitir <system_id>, como hacía antes, pero generando un mensaque de que el drone se está desplegando en el sector_id en que se encuentra el system_id solicitado.

- [ ] Hace falta meter hints sobre cómo averiguar el id de los drones y de los system_id (por ejemplo en el error de "repair", en el man de drone, o en el error de drone repair). Mencionar en ese hint que siempre se puede pulsar dos veces TAB para que te liste las opciones que se pueden introducir (y, por tanto, averiguar directamente los id's que hacen falta)

- [ ] Opción de desmantelar drones para obtener scrap.

DRONE MODULES

- [ ] Módulo de sonido! Podría ser muy útil para interpretar cosas: interpretar el estado de los sistemas (sistemas degradados emiten sonidos de error o sonidos raros, y systemas nominales zumbidos característicos; interpretar si hay algo vivo en la sala, o algún tipo de evento ambiental)


=== NAVIGATION / ROUTES / WORLD GEN ===

- [ ] Se debería poder viajar a un sector. Los nodos de sector CREO que se en el código se llaman nav_point. Sea como sea, unas coordenadas de sector tienen que poder ser un destino válido (luego también un target válido de "route solve"). De este modo se abre la puerta a acudir a sectores del espacio e investigar qué hay en ellos.
- [ ] Desde un nodo "transit" (temporal) sólo deja navegar a origen/destino del viaje abortado. Debería dejar hacer un "route solve" a otros puntos en rango y, si la ruta es viable, permitirse esa navegación también. 
- [ ] En las naves, estaciones, etc. visitadas se genera algo de scrap con el tiempo. Esto responde a la idea de que las estaciones, naves, etc. van deteriorándose y siempre es posible recuperar de ellas algo nuevo. También preveo algún módulo que permita desmantelar estaciones, algo que llevaría mucho tiempo hacer, pero que produciría mucho scrap.
- [ ] ¡Las estaciones, naves, etc. deben deteriorarse y y acabar desapareciendo con el tiempo! Todo rastro humano debe ir desapareciendo, teniendo en cuenta que una estación o nave abandonada difícilmente puede sobrevivir millones de años en el universo. Para una versión 3 o 4 del juego, se puede quizá diseñar un evento que haga que (alguna especie desconocida o resto de vida humana) vuelva a fabricar estaciones, naves, navegar por el espacio, etc. 
- [ ] Alguna forma de generar el grafo del mundo en el estado actual, bien sea con fines de debug o con fines de que pueda en un futuro desarrollarse un módulo instalable que permita visualizarlo en pantalla del juego.
- [ ] Los viajes deben ser más peligrosos. Los de muchos años luz deben, por lo pronto, exponerte a mucha radiación. Esto limitará el ir pegando saltos por ahí a lo loco. Viajar a 40 años luz debería ser a costa de llegar con los sitemas hechos polvo.



=== SYSTEMS ===

- [!] Revisar/rediseñar qué comandos dependen de qué sistemas, y las implicaciones que ello tiene.

DRONE BAY
- [ ] Necesitamos que drone_bay tenga una capacidad máxima para albergar drones.

LIFE_SUPPORT
- [ ] Diseñar game over y reinicio diegénico.

- [ ] Hay que desarrollar una v1 de vitals. El usuario tiene también que mantener a su PJ. La hibernación debe tener su coste (y/o riesgos). También tiene que haber algún consumo de alimento, y un generador de oxígeno que requiera alguna forma de mantenimiento o combustible o...

- [ ] Hay que desarrollar un comando específico para conocer el status del "huesped" del sarcófago

CARGO
- [ ] Debe haber un límite de scrap que se puede tener. O un límite de volumen. Medir las cosas por volumen.

ENERGY



=== COMMANDS ===

- [!] Por lo que dice el manual life_support.es.txt los comandos status y alerts dependen de life_support. No deberían. Deben depender de core_os.

- [!] Cuando se ordena "salvage scrap", antes de que la tarea concluya, en el output del comando "logs" se imprime un mensaje que indica cuál es la cantidad de scrap total recupelable (available). Esa información no debería mostrarse/saberse hasta que la operación de "salvage scrap" no haya finalizado.

- [!] Hibernate until_arrive debería pedir confimacion. También hace falta algo de cinemática, para que no parezca que no ha pasado nada.

- [!] No debería dejar emprender viaje si se está dock. Antes se debe hacer con éxito un undock.



=== LORE ===

- [ ] Sistematizar y darle un sentido de minijuego a build_procedural_salvage_mail_content. La idea de los mails generados proceduralmente debe ser esta: que te ofrezcan indirectamente información útil para planear tus viajes. En esos mails tiene que haber un número determinado de categorías de información que pueden o no cubrirse, como, por ejemplo: nivel de radiación de un nodo en su último contacto, si tenía o no información relevante ese nodo, estado de su casco en su último contacto, si había drones en su último contacto, etc. De este modo el jugador irá obteniendo información que le servirá para seguir avanzando. Es decir que estos mails procedurales le sirven para obtener información de destinos que le puede ser útil de cara a organizarse y planificar su próximo viaje, o saber qué lugares evitar de momento, o a qué lugares le interesa acudir. Estos mails tambien tiene que servir para otra cosa: distribuir una serie de consejos generales (seleccionados de una batería) acerca del universo, de cómo obrar, de peligros de las zonas o consejos, etc. [Una nota acerca de cómo se obtiene ahora mismo la información de la radiación que tiene un nodo:
ship survey ahora muestra node_radiation en la salida; si el nodo ya fue visitado o está dentro del alcance actual de sensores, imprime el valor en rad/s; si no, devuelve unknown/desconocida]

- [!] Ideas para “formas de aparecer”. Además de las ya planteadas (salvage data, uplink, recibir mensaje automático o no automático, captar mensaje perdido en el espacio):
  
  - Recovered attachment: al cargo audit aparece “found unindexed attachment; run cargo audit again to decode” (bonito para tu “manifest stale”).

  - Salvage de caja negra. [DESCARTADO por ahora]
  
  - OS digest: cada X años de hibernación, el OS genera un “digest” (no lore garantizado; solo resumen + a veces un fragmento).

  - Ghost beacon: al entrar en bulbo/halo se disparan señales con baja confianza.

  - Corrupted route table: produce SECTOR: en vez de LINK: (intel parcial).

  - Dron (recuperado) que al desplegarlo (deploy) por primera vez produce un mensaje pregrabado (al estilo de R2D2).

  - Información que se obtiene sólo al desmantelar un dron.


=== INTEL ===

- [ ] [INTEL] S+003_-001_+001 [/INTEL] devuelve "corrupt data: no usable intel found". ¿Por qué? ¿Qué está mal con el formato? ¿No son unas coordenadas correctas?

- [ ] Los incrustados [INTEL]...[/INTEL] no debe verlos el usuario.

- [ ] Tres nuevas formas de "recuperar" información (intel y lore): 
  - [ ] 1) Recovered attachment: al hacer "cargo audit" aparece “found unindexed attachment; run cargo audit again to decode”; 
  - [ ] 2) Dron recuperado (mediante un futuro comando "drone salvage drone") que al desplegarlo (deploy) por primera vez produce un mensaje pregrabado; 
  - [ ] 3) Información que se obtiene/descubre al desmantelar un dron (mediante un futuro comando "drone dismantle", o algo así, que permite reducir a scrap un dron).

- [x] Sistema de escalado de privilegios. Actualmente sólo se tiene acceso a archivos con un nivel de acceso de GUEST. No sé cuántos niveles hay actualmente definidos, pero me interesa que haya estos: GUEST, ENG, MED, OPS, SEC. Tenemos entonces que desarrollar formas diegéticas de elevar el acceso por distintos medios:

  - [x] 0) Versión 0 muy simple pero funcional (MVP): comandos "auth status" "auth recover eng", "auth recover med". Requisitos: data_core >= LIMITED, datad running, opcional: securityd para MED (o al revés). Efecto: job de x segundos o minutos que, al completarse, añade ENG o MED a auth_levels. Resultado narrativo: empiezas en GUEST; puedes leer el mail del PJ; más tarde recuperas ENG; entonces ves los logs de los otros sarcófagos

  - [ ] 0.1) Hay que añadir objetivo:
      auth status <node_id>
      auth recover eng <node_id>
  La idea es que esto te da acceso a la documentación con credenciales de nivel ENG, pero sólo en la nave objetivo. De esta forma ya tenemos una primera versión de hackeo.

  - [ ] 1) Boot de servicios + self-tests: La más natural para tu juego ahora mismo. Ejemplo: cuando data_core está operativo y datad corriendo, puedes ejecutar:
    auth probe
    auth recover eng
    auth recover med
  Y eso hace un job. Requerirá tiempo y energía, y, si sale bien, añade ENG o MED (pero quizá hay que limitar esto a la nave/station en la que se está docked, o a la propia nave; de forma que a esos comandos habría que añadires un id, como por ejemplo ECHO_7 o RETORNO_SHIP).
  Justificación diegética: estás restaurando tablas de permisos/certificados desde caché local.

  - [ ] 1.1.) Sólo para salvage avanzado: las operaciones de auth recover sólo se pueden hacer si un drone con el módulo de hack apropiado encuentra una terminal en la nave y se logra conectar a ella.

  - [ ] 2) Salvage de credenciales desde nodos remoto (muy buena para la experiencia de exploración del Jugador): ejemplo: en un hospital ship o una estación técnica encuentras:
    med_override.token
    eng_cert.fragment
  Al extraerlos: auth import /remote/.../med_override.token
  obtienes acceso MED en ese hospital ship. [Esto convierte los permisos en parte del loop de exploración.] [P.D. Mejor: encontrar esos documentos hace que el hackeo sea más rápido, o incluso automático.]

  - [ ] 3) Módulos instalables: secure_coprocessor, legacy_auth_bridge, med_console_patch. Al instalar uno, desbloqueas cierno nivel o reduces dificultad de recuperación. [Esto da progresión material.]

  - [ ] 4) Acceso contextual/temporal (muy interesante, pero para más adelante): 
    a dockear en cierta station, recibes acceso temporal (ENG session token valid while docked), o sólo durante un timpo (contador atrás); o tras un uplink en un relay. 


=== MODULES ===

- [ ] Módulo instalable que te habilita el comando "nav map galaxy". Ahora mismo se puede usar desde el principio, pero quiero modificar esto. Quiero que para poder usar ese comando se exija tener un módulo específico de nave instalado (hay que inventar ese módulo también). Si ejecutas esa orden sin tener el módulo instalado, se bloquea y se te advierte de que necesitas tener ese módulo instalado. 

- [ ] Un módulo que añada "deepscan", para scaneos de mucha más larga distancia.

- [ ] Debe haber algún límite de módulos (para estimular los builds). Y algunos deberán tener penalizaciones además de bonificaciones.

- [ ] Módulo que hace que los drones vuelvan automáticamente al dock (si es posible) cuando su batería cae a cierto nive.

- [ ] Módulo instalable que permita automatizar ciertas tareas en tránsito (aunque el PJ esté hibernando). Por ejemplo, llevar a cabo un scan cada x tiempo (configurable por el jugador), y dar la opcion de deshibernar en caso de que se detecte algo nuevo.

- [ ] Módulo para aumentar el rango de route solve.

- [ ] Módulo de sonido de drones. Oir los sonidos que hacen los drones al operar, con un sonidito distinto por cada tipo de job o fallo, etc.


=== WIN/LOST CONDITIONS AND LOOPS ===




=== SOUND AND MUSIC ===

- [x] Sonido ambiente (https://www.youtube.com/watch?v=wVMrSszssyo)

- [x] Posibilidad de apagar/encender el sonido ambiente.

- [ ] Reproductor de música clásica (Sibelius, Mahler, Buckner, etc.).
  - [ ] Sibelius sinfonía No.2 D mayor, op. 43
  - [ ] Mahler sinfonía No.5 (o 4?)
  - [ ] Strauss Blue Danube
  - [ ] Dvorsak

- [ ] Ruido de estática.

- [-] Bips con las advertencias. Quizá sonido de discos duros al procesar ciertas órdenes. Sonidos específicos únicos para ciertas tareas como solve route o hibernate. Sonido lejano pesado al hacer dock y undock. Chirridos de casco cuando el hull baja.
- [x] Quiero un sonido específico para cuando sale el mensaje de "Action blocked".
- [ ] Sonido de advertencia cuando aumenta la radiación.

- [x] Comprobar que efectivamente está funcionando el volumen configurable de los beeps, etc.


=== OTROS / SIN CATALOGAR ===

- [ ] Definitivamente hay que diseñar un tutorial.

- [ ] Actualmente el comando ship survey es un pelín confuso?

- [!] Necesitamos un comando que te liste el camino que has seguido. El orden de los nodos que has visitado. Incluso estaría bien que junto a los nodos por los que has pasado apareciera entre paréntesis o algo un listado de los nodos que eran accesibles desde él.

- [ ] Tiene que haber un aliciente claro para explorar los nodos del sector antes de dar el salto al siguiente. Un salto de muchos años de hibernación tiene que tener riesgos. No debe tampoco haber muchas rutas que conecten un sector con otro. Lo normal ha de ser que haya una.

- [ ] Cada vez que se consigue un contacto o link tiene que especificarse si es nuevo (no conocido) o no.

- [ ] El bonus de tiempo del módulo rapid_maneuver_module debe ser mayor. Los drones con ese módulo deben ser más rápidos.

- [ ] El mensaje "uplink complete :: node data already exhausted" es quizá un poco confuso (puede dar a entender que tampoco hay data recuperable vía "salvage data"). Debería, mejor, ser "uplink complete :: uplink data already exhausted".

- [-] Mejorar el manual de drones. Hacerlo detallado y más homogéneo al resto.

- [?] Creo que route solve no sólo debería depender de sensord sino también de datad. (Valorarlo.)

- [ ] Nuevo sistema: sonar. Que haga pip-pip. O un radar que esté constantemente en funcionamiento. Basarse en los submarinos actuales. La idea es que se puedan captar a veces objetos en movimiento. Incluso naves a la deriva. O peligros.

- [ ] Nuevo loot: uranio (como combustible). La idea es que para poder generar energía, el reactor nuclear necesita uranio. Es duradero, pero teniendo en cuenta que se viaja durante años... El uranio (o lo que sea) se tiene que poder obtener con los drones de otras derelics.

- [ ] Chequeos periódicos. Permite configurar “wake every N years/days” (cuando desbloquees software).

hibernate until_arrival --wake-every 2y

- [ ] Diseñar 3 eventos básicos que te despierten de hibernación.. Eventos aleatorios durante viajes/hibernación, que despiertan de hibernación automática.
  Tipos de eventos:
    - [ ] Señal/mensaje capturado.
    - [ ] Impacto con...
    - [ ] ...

- [ ] Posible contamination_ship (rad que se acumula y se disipa lento y ha que limpiar). La fórmula sería  internal_rad = env_rad * ingress_factor + contamination_rad. Por otra parte, necesitamos diseñar una forma de limpiar la nave (e. e. el hull y los sistemas o lo que sea) de radiación. Podría haber algunas estaciones especializadas en ello. Y algún módulo que redujeran lentamente la radiación. Y operaciones con drones.

- [ ] Módulos para drones. Aumento de shield_factor de radiación, aumento de batería, velocidad, opciones de ataque o defensa, soplete, etc.

- [x] Quiero que me generes un documento en "/home/jon/prog/retorno_case/retorno_docs/" en el que se le explique a chatGPT exactamente qué debe hacerse y cómo (incluyendo ejemplos) para crear nuevos arcos y para crear singles. La idea es que con esas instrucciones chatGPT pueda crearme nuevos arcos y singles.

- [ ] Al dockear en una nave o estación, algunas naves o estaciones deben añadir rads/s a los rad/s del nodo.
- [ ] Ship survey tiene que servir también para obtener un informe del nivel de radiación del nodo dockable (y así poder valorar si merece la pena dockear o no).

- [ ] Modelo avanzado de salvage. La opción simplificada (la actual, siempre estará disponible). La avanzada (juego dungeoning) tendrá riesgos, y llevará más tiempo, pero también posibles recompensas mayores. Este modelo avanzado de salvage requiere un nuevo comando "drone survey" entre otros muchos. Desarrollar una v0.

- [x] Los trabajos de reparación no deberían permitirse si el health del sistema en cuestión en está en su máximo. Por otra parte, al finalizar un trabajo de reparación debería indicarse el número de scrap gastado.

- [x] Hay que asegurarse de que a la hora de chequear si el health de un sistema o un dron está al máximo no se emplean valores absolutos, pues aunque el health máximo normalmente es 1.00, la idea es implementar módulos que puedan subir el health máximo a 1.20 o más.

- [x] El mensaje de confirmación de automvimiento para operación de reparación no está funcionando con el debug on. Esto se puede solucionar?

- [ ] Salvage avanzado v0. Quizá para poder acceder al modo avanzado haga falta instalar un módulo especial (advanced_drone_salvage_ops). Al hacer un deploy de dron a una nave o estación que no sea la del personaje-jugador (y lo mismo al mover un dron fuera de la nave del personaje-jugador), tiene que salir un mensaje preguntando si se desea entrar en modo salvage avanzado, o continuar con la versión automatizada.
Todas las estaciones, ships, derelics, etc. tienen que tener un esquema de "sectores". Por ejemplo, y para la v0, todo ship tendrá los mismos sectores que la nuestra. Habrá que pedirle a GPT que cree un esquema básico de los sectores que tiene cada tipo kind.
El paso de un sector a otro estará bloqueado por puertas. A veces esas puertas se pueden abrir sin más, otras veces hace falta reparar o hackear algo para que funcionen, y otras veces hará falta forzarlas. En cada sector se supone que se puede obtener un tipo de loot y que puede haber unas interacciones u otras.

- [ ] Diseñar sistema "security". Por ahora, este sistema servirá para detectar intrusos en la nave (biológicos o no biológicos)

- [ ] HAcer dock tiene que tener una pequeña posibilidad de que "se meta algo" en tu nave al dockear, u otros eventos.

- [!] Se tiene que poder "añadir jobs a la cola". Es decir, una forma de introducir comandos que sólo se ejecuten una vez terminada la última tarea en cola.

- [ ] Pegarle a chatGPT:
  - debug lore después de 1–2 uplinks
  - un ejemplo del archivo entregado por captured_signal o ship_os_mail
  Para calibrar probabilidades (para que no “llueva lore” y siga siendo calmado).

- [ ] Quiero diseñar e implementar la cinemática de inicio de hibernación. Al iniciar la hibernación, debería de salir un mensaje (localizado) diciendo que se está iniciando la secuencia de criogenización, y una serie de mensajes (meramente narrativos) diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la criogenización/hibernación. Es decir, hay que diseñar una serie de mensajes diegéticos para el proceso de hibernación/criogenización (esos mensajes tienen que ser coherentes con los mensajes relacionados que se generan en la intro cinemática al iniciar nueva partida). 
Una vez impresos esos mensajes, deberá iniciarse una cuenta atrás de 10 segundos (visible para el jugador). Al llegar a 0, debe limpiarse la ventana de logs, y se considerará que la hibernación se ha hecho efectiva. En un segundo paso, necesitamos diseñar una cinemática del despertar de la hibernación, pero diseñemos primero la cinemática del inicio de hibernación.

Actualmente esos mensajes son los siguientes:

«
[core_os] wake schedule integrity: FAIL (chronometry desync)
[core_os] Multiple wake timers unreadable or outside valid bounds.
[core_os] No authorized medical staff response detected.
[core_os] Entering autonomous emergency recovery protocol.
AUTONOMOUS RECOVERY PROTOCOL engaged
CRYO VAULT status scan... ok
TARGET selected: Sarcophagus-05
Decryo sequence: INIT (emergency profile)
Thermal gradient stabilized
Neurochemical thaw: PARTIAL
Motor pathway recovery: FAIL (indeterminate system fault)
Host vitals: nominal
Conscious Interface Recovery Protocol (CIRP): ARMED
Neural terminal link: ONLINE
Manual operations required
Timebase fault detected: internal clock invalid
Chronology reset: Year 1 / Day 1 / 00:00:00
Awaiting operator input
»


algunos de esos mensajes no tienen que volver a salir, pero otros sí. Dependerá de cuál sea la causa para despertar de la hibernación. Si la causa para despertar/salir de la hibernación es por una interrupción automatizada (por ejemplo porque un sistema crítico pasa a CRITICAL u OFFLINE, o alguna otra de las razones que me acabas de describir), entonces te
Al salir/despertar de la hibernación (por la causa que sea) debe limpiarse la pantalla de logs, esperar 2 segundos e imprimirse una serie de mensajes diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la descriogenización.
junto con un mensaje (que se repetirá siempre), advirtiendo de que hay un problema crítico y no es posible descriogenizar completamente al sujeto del sarcófago (es decir, al Personaje Jugador). El sarcófago del PJ debe tener un id, por cierto. 

- [ ] Necesitamos una merjor organización del help.

- [ ] Hay muchos mensajes (o partes de mensajes) que aparecen en español cuando el idioma de configuración es el inglés, y al revés, mensajes o partes de mensajes en inglés cuando deberían estar en español. Un ejemplo: estando la configuración en inglés, me ha salido este  mensaje: "ParseError: Subcomando power desconocido. Usa: power status | power plan cruise|normal | power shed/off <system_id> | power on <system_id>"

- [ ] se puede usar el comando "scan" estando el servicio "datad" offline?

- [ ] Ahora mismo los manuals se han generado con un tono "diegético". Me gustaría ver cómo sería la versión más "técnica", pues chatgpt y codex me la han propuesto varias veces pero siempre la he rechazado sin llegar a ver cómo sería.

- [ ] También creo que tendría que aparecer en primer lugar el nombre de la hubicación (si la tiene), por ejemplo Relay-97 (relay) dist=1.30ly coord=S+000_-001_-001:02""


- [x] dose es la dosis acumulada de radiación que ha recibido el dron (en rad). Se incrementa cada tick en función de la radiación ambiental (state.ship.radiation_env_rad_per_s) y el shield_factor del dron:
drone.dose_rad += r_env * shield_factor * dt
Ahora mismo es informativo (no afecta directamente a integridad/batería), pero lo usamos como base para futuras penalizaciones o fallos por exposición prolongada. Si quieres, puedo añadir un aviso cuando supere umbrales, o hacerlo afectar a la integridad.


- [-] Diseñar el sistema de encontrar nuevos destinos. A nivel de sistema solar, tiene que ser posible detectar vía escáneres o algo así; a nivel de galaxia, quizá sólo a partir de información que se obtenga (cartas de navegación). Más allá de galaxia, no se sabe. El comando contacts/scan debe tener un alcance pequeño relativamente.

- [ ] Algunos world_node, como las naves, las estaciones y los derelics tienen que tener ship_sector's. O station_sector's (habitaciones, vaya). Los planetas también tendrán que tener sectores (cuando hagamos planetas y drones capaces de desplegarse en ellos),

- [ ] Implementar guardar/cargar juego (savegames).

- [ ] las baterías (de drones y de nave) deben también poder deteriorarse (por radiación u otros daños).

- [ ] Aclarar cómo se crean nuevas naves, estaciones, etc.

- [ ] Ahora mismo tu status muestra P_load=4.20kW estando docked; eso sugiere que el docking añade consumo o activa algo. Está bien, pero ojo con el prólogo: podrías querer que dock reduzca carga (porque apagas motores) o que cambie perfil. No lo toques ahora; solo para tenerlo en mente.

- [ ] boot sensord no está devolviendo ningún mensaje, creo.

- [ ] [Esto quedó pendiente de hacer] Si quieres, también podemos añadir un mail automático al primer módulo encontrado (lore + “esto se instala con install <id>”), pero lo dejo para después de que el loop funcione.

- [ ] Generación automática de mails al comienzo de la partida, para aprender cosas e introducirse.



=== USER INTERFACE ===

TEXTUAL
- [!] Cuando al emprender un viaje se pone el ship_status automáticamente en cruise, no cambia en el panel head. De todas formas, no sé si está funcionando bien el auto cruise, pues aunque ha subido el net a positivo, veo que todos los sistemas están activos. 
- [x] Auto completado del system_id en el comando drone repair <drone_id> <system_id> no funciona.
- [ ] El panel status debería poder modificarse por otro.
- [!] Los paneles, excepto header, botton, comandos y logs deberían poder activarse desactivarse, para tener más espacio para logs. Mediate atajos de teclado.
- [ ] Colores. Y archivo de configuración de colores, para poder configurar paletas.
  - Que cuando cambie a mejor algo del status se ponga verde, y rojo cuando a peor.
  - Tag de advertencias naranja. Info en azul.



=== VERSIÓN II ===

transponders/items como fuente de intel (muy fácil ahora que tienes inventory/modules)

señales como intel parcial (SECTOR/COORD con baja confianza)

eventos en tránsito (sólo 1–2, muy suaves)


- [ ] Virus informáticos. Que afectan a alguno de los sistemas, pudiendo llegar a inutilizarlo total o temporalmente, o a hacer que falle ocasionalmente.

data_core. Ahora mismo data_core sirve para habilitar operaciones de auditoría de bodega y para servicios de datos: Audit de cargo/manifest: cargo audit / inventory audit se bloquean si data_core no está operativo o si datad no está corriendo.
Servicio asociado: datad (se debe bootear para auditorías).

Fuera de eso, todavía no tiene funciones “de gameplay” adicionales (p. ej. análisis avanzado, logs, descifrado). Es el lugar previsto para futuro contenido de datos/registro, pero hoy su uso principal es permitir la auditoría del inventario.

economía

viajes

amenazas

eventos dinámicos



- [ ] Paso 2 del sistema de hibernación/viaje/navegación: 
    Probabilidad de fallos de sistemas durante décadas,
    Eventos raros (“wake event”),
    Degradación acumulada,
    Necesidad de preparar la nave antes de dormir (SoC, redundancias, drones, etc.),
    Quizá “periodic wake checks” automáticos.

Sugerencias de diseño para la hibernación “con consecuencias” (Paso 2)

Para que viajes de décadas sean jugables y tensos sin ser arbitrarios:


Riesgo como función de preparación
Riesgo aumenta con:

low_power_quality sostenida

SoC bajo

radiación alta

sistemas dañados
Y disminuye con módulos (bus stabilizer), redundancias, etc.

Digest de hibernación
Al despertar, imprimir un informe compacto:

“Years slept: 45.2”

“Events: 2 warnings, 1 critical”

“System health deltas”

“Resources consumed/produced”



Sugerencia de diseño (para Paso 2, “hibernación jugable”)

Una vez esto esté estable, el “riesgo” de hibernar décadas no debe ser “te mueres siempre”, sino:

umbral de preparación: si Q bajo / SoC bajo / core dañado → aumenta probabilidad de WAKE_EVENT.

WAKE_EVENT corta la hibernación automáticamente y te devuelve al modo normal con una alerta crítica.

Tú decides si reparas o vuelves a dormir.

Eso te da viajes largos con narrativa emergente.



Sugerencias de diseño para “años” sin aburrimiento (ya a nivel juego, no motor)

Cuando el core loop ya esté, lo que te dará “novela” en viajes largos es:

descubrimiento de logs por décadas: al llegar, mails con timestamps futuros (“while you slept…”)

cambios del entorno: radiación, señales, densidad de restos

wake events raros (poco frecuentes al principio, más si vas mal preparado)

Pero eso es Paso 2. Ahora mismo lo correcto es consolidar CRUISE.



siguiente bloque real: descubrimiento en el nodo destino (DERELICT_A3) + salvaging por sectores + primer “encounter” no-combate (por ejemplo, puerta cerrada, señal, o sistema de acceso).

