=== INTEL ===

- [x] Quiero que cada hub authored pueda tener su tabla propia de hubs a obtener mediante uplink. Quiero que sea opcional, es decir, que si la tiene, se use, pero que si no la tiene se aplique _discover_routes_via_uplink() con normalidad. La idea sería la siguiente: me gustaría que los hub authored (es decir, los que tienen su propio json) tengan una "tabla" propia en la que se pueda especificar qué otros hubs authored se pueden descubrir vía uplink en ellos. En esa tabla habrá que especificar la lista de hubs authored que se pueden descubrir por esta vía, el número máximo y mínimo de hubs authored que se pueden descubrir por esta vía, y el peso/probabilidad de que sea uno u otro el que se descubra. Como digo, en caso de que la localización authored no incluya esa tabla, o sus valores estén vacíos, se deberá usar  _discover_routes_via_uplink() como se venía haciendo hasta ahora. Dime, antes de implementar nada, si lo ves viable, y si crees que puede entrar en conflicto o generar algún problema. Por otra parte, ten siempre en cuenta que nos interesa la robustez y la escalabilidad, y aprovechar las cosas que ya tenemos y funcionan.

- [x] Cuando se introduce el comando 'intel' sin más parametros debería salir al final un hint (localizado) que recomendara usar 'intel import <path>' para añadir intel y 'intel show <intel_id>' para ver el detalle de los intels, y 'man intel' para saber más acerca del comando 'intel'.

- [x] Ahora mismo el node_id HARBOR_12 es un nodo conocido por el jugador desde el comienzo del run (aunque empieza sin conocer la ruta para llegar a él). Me gustaría modificar algunas cosas a este respecto, e implementar algo (pero antes de implementar nada, comprueba qué partes de lo que te voy a decir ya están desarrolladas o implementadas o pueden hacerse con lo ya implementado, y así economizar y no hacer cambios o añadidos innecesarios si verdaderamente no lo son, o no mejoran lo anterior): 

1) Quiero implementar una forma (si no estuviera implementada ya) de poder insertar en los archivos txt (es decir, en cualquier txt que el jugador lea con 'cat <path>' o 'intel import <path>') un flag o marcador "[INTEL] [/INTEL]" que le permita al sistema entender que lo que hay entre esos flags es: o bien un LINK (una ruta entre dos localizaciones, con el formato habitual "LINK: ECHO_7 -> CURL_12"), o bien un 'node_id', el 'name' de una localización o las coordenadas de un sector (con el formato habitual, por ejemplo "S+000_+000_+000"). Así, si el jugador accede a ese txt mediante 'cat <path>' o 'intel import <path>', y el txt en cuestión incluye una información entre los flags "[INTEL] [/INTEL]", entonces el juego debe: a) si es un LINK, incluir ese LINK a las rutas conocidas (y, en consecuencia, las dos localizaciones implicadas deben automáticamente entrar a considerarse localizaciones conocidas también, tal y como, si no me equivoco, ya está implementado en la lógica actual, pero confírmamelo); b) si no es un LINK, comprobar entre las localizaciones authored (los json) si existe alguna localización con ese mismo node_id, ese name, o esas coords de sector: si sí existe, debe incluirse esa localizacion entre los contacos conocidos.
c) si no es un LINK ni tampoco un node_id o name o coordenada identificable, hacer una de estas dos cosas: en un 50% de probabilidaes, emitir un mensaje informativo (localizado) diciendo que el documento tiene intel corrupta a la que no se puede acceder; y en otro 50% de probabilidades contruir proceduralmente un nuevo nodo en algún sector cercano o no muy lejano y dar a conocer su ruta. La probabilidad de que suceda lo uno o lo otro me gustaría que fuera configurable desde balance.py, y en un segundo paso (por ahora no) me gustaría desarrollar un módulo instalable que modificara estos porcentajes, es decir, un módulo que hiciera que sea más probable extraer intel (proceduralmente generada) a partir de intel corrupto.

2) Me gustaría que HARBOR_12 sólo se incluyera entre los destinos conocidos en el momento en que el jugador lea el log echo_cache.en.txt o echo_cache.es.txt, pues en ese log se menciona a HARBOR_12. Para ello, podríamos incluir el texto "[INTEL] HARBOR_12 [INTEL] dentro de log echo_cache.en.txt y echo_cache.es.txt". Nos servirá para testear que lo anterior funciona.

Antes de implementar nada, dime si ves algún conflicto en lo que te planteo, si lo ves viable, o si prevées que pueda dar algún problema.

- [x] Sistema procedural para descubrir información de rutas a nodos conocidos pero sin ruta conocida. A través de uplink y a través de un flag específico en los txt. El caso es que ahora mismo los datos corruptos (información entre etiquetas [INTEL][/INTEL] no procesable) genera contactos (nodos) sin ruta. Los INTEL incrustados también pueden generar (esto hay que confirmarlo) contactos authored pero sin ruta. Además, el generador de contactos de uplink _discover_routes_via_uplink() puede generar contactos sin rutas (confirmarlo). Así que el caso es que se van generando por distintas vías contactos sin ruta, y tiene que diseñarse una manera procedural de conseguir intel de rutas a contactos existentes, para que todo marche [P.D. ya diseñado; ver más abajo]. Empezar por preguntar a codex: Actualmente ¿de qué maneras se pueden averiguar rutas para contactos conocidos (contactos authored y contactos procedurales)?
==> PROMPT: Quiero desarrollar un sistema failsafe de gestión de nodos "colgados" o "muertos". No sé si actualmente existe ya en el juego algo parecido. Por "nodos colgados" o "nodos muertos" (indistintamente) entiendo aquellos contactos o nodos (sectores, stations, waystations, ships, o cualquier localización) que cumplen las siguientes condiciones: 1) son conocidos por el Personaje-Jugador (o sea que aparecen listados en el output del comando 'contacts' o 'nav'); 2) no se conoce ruta hacia ellos; 3) no existe actualmente una localización conocida (y con ruta) desde la cuál ese o esos nodos sin ruta queden a una distancia menor al radio de los sensores (en estado "nominal"), de forma que es estrictamente imposible para el jugador conseguir una ruta hacia ese o esos nodos por medio del comando 'route' desde ninguna posición; 4) no existe actualmente (bien porque no va a generarse proceduralmente nunca, bien porque no se ha generado proceduralmente aún) ningún documento extraible mediante "salvage data" o "uplink" u otro capaz de proporcionarle al jugador la ruta (link) hacia ellos. (Valorar si hace falta añadir alguna condición más o corregir alguna de las propuestas.)
El sistema de gestion de "nodos colgados" o "nodos muertos" debe llevar un registro de los nodos que se encuentra "colgados" o "muertos" en todo momento, e ir registrando el tiempo que permanecen colgados o muertos (es decir, llevar un control de durante cuánto tiempo, interno del juego, no tiempo real, siguen cumpliendo todas las condiciones para seguir considerándose colgados o muertos). A partir de cierto tiempo (configurable desde el balance.py), debe dispararse alguna estrategia (preferiblemente indirecta [ver más abajo]) para lograr que dejen de estar muertos o colgados. Las estrategias que se me ocurren podrían ser estas: 

a) Estrategias directas
- Injectar, en algún nodo no visitado, información (recuperable por alguna de las distintas vías de obtención de información) que proporcione la ruta al nodo muerto.

b) Estrategias indirectas
- Injectar, en algún nodo aún no visitado, información (recuperable mediante salvage data, uplink, captured signal, station_broadcast, u otras formas de obtención de información aún no desarrolladas pero que me gustaría que desarrollaremos pronto) de una ruta a alguna localización desde la cual sí sea posible calcular ruta (con el comando "route") hasta el nodo muerto.
- Injectar, en una localización procedural generada ad hoc, información (recuperable por alguna de las distintas vías de obtención de información) de la ruta al nodo muerto, y generar a su vez, en algún otro nodo ya existente pero aún no visitado, información (recuperable de algún modo) de la ruta que lleva a ese primer nodo generado ad hoc.

Deben siempre preferirse las estrategias indirectas a las directas. Si por alguna razón no se consigue aplicar con éxito alguna de las estrategias indirectas, se usará una estrategia directa.

A la hora de planificar cómo desarrollar todo esto, een en cuenta que en breve me gustaría diseñar nuevas formas de obtención de información. Es decir, que nos interesa poder añadir hacia atrás esas nuevas formas tanto en el failsafe de nodos muertos como en aquellas lógicas procedurales del juego que dependen o hacen uso de uno u otro modo de los modos de generación/colocación de información. Por ejemplo, en breve me gustaría desarrollar tres nuevas formas de "recuperar" información: 1) Recovered attachment: al hacer "cargo audit" aparece “found unindexed attachment; run cargo audit again to decode”; 2) Dron recuperado (mediante un futuro comando "drone salvage drone") que al desplegarlo (deploy) por primera vez produce un mensaje pregrabado; 3) Información que se obtiene/descubre al desmantelar un dron (mediante un futuro comando "drone dismantle", o algo así, que permite reducir a scrap un dron).

Si consideras que es preferible desarrollar e implementar primero estas nuevas formas de obtención de información, antes de desarrollar el failsafe de nodos muertos, dímelo.

Como regla general: antes de implementar nada, valora la propuesta, su viabilidad y dime posibles conflictos o problemas que podría producir. Tengamos también en cuenta que nos interesa siempre la robustez y la escalabilidad. Queremos aprovechar siempre las herramientas ya disponibles (si son adecuadas) e introducir los cambios mínimos (a no ser que haya alguna buena razón para obrar de otro modo).


=== NAVIGATION / ROUTES / WORLD GEN ===

- [x] Si no me equivoco, ahora mismo el node_id de una localización puede estar construirda mediante unas coordenadas de sector más un sufijo. Hay pues algunas localizaciones que tienen nombre pero que su node_id no está construido en base a su nombre sino en base a las coordenadas del sector en que se encuentra (y añadiéndole un sufico). Lo primero, confírmame que estoy en lo correcto. Este sería el caso, por ejemplo, de la siguiente localización:

Derelict-P-1 (derelict) sector=S+000_-001_-001 id=S+000_-001_-001:25294E dist=6.99ly

Ahora bien, es un poco engorroso para el jugador tener que usar 'S+000_-001_-001:25294E' como node_id, así que propongo lo siguiente. Los hubs que tengan un name, como en el ejemplo de arriba ('Derelict-P-1'), su node_id debería construirse a partir de su 'name', a poder ser siguiendo la siguiente convención: transformar todas las minúsculas a mayúsculas, todos los espacios en blanco en guiones bajos, y todos los guiones a guiones bajos. O sea, que para el ejemplo de arriba, el node_id quedarí así: DERELICT_P_1. Todo esto, claro, suponiendo que no pueda haber dos nodos con mismo 'name' (confírmamelo). Por tanto, el formato coordenadas + sufico (como 'S+000_-001_-001:25294E') debe reservarse únicamente para los casos en los que la localización o hub en cuestión no tenga 'name'. Antes de implementar nada, dime si te parece viable lo que te planteo, o si prevees que pueda entrar en conflicto con algo, o causar algún problema.

- [x] Generador de nombres de hubs

- [x] Generador de prefijos

- [x] Failsafe y definición de "atasco". Actualmente (v0) definición de “atasco” (v0): desde current_node, known_routes_count_to_new_nodes == 0 (solo vuelta al origen o rutas ya visitadas). O alternativamente: el jugador ha ejecutado uplink N veces (configurable desde balance.py) y no se añadió ninguna ruta NUEVA (a ningún nodo). 

Codex propone lo siguiente a este respecto:

Aquí van 3 criterios de “atasco” que funcionan bien en práctica. Te doy pros/contras para que elijas uno o combinemos:

Solo por rutas “útiles” desde el nodo actual
Regla: “atasco” si known_routes_to_unvisited == 0.
Pros: simple y diegético (no hay ningún sitio nuevo).
Contras: puede disparar aunque el jugador tenga rutas nuevas desde otros nodos (pero no desde el actual).
Por intentos sin novedades (lo que ya tenemos, refinado)
Regla: tras N uplinks seguidos sin añadir rutas nuevas y sin rutas a nodos no visitados desde el nodo actual.
Pros: evita falsos positivos; no dispara a la primera.
Contras: si el jugador nunca usa uplink, no dispara.
Por “movilidad global mínima”
Regla: “atasco” si total de rutas a nodos no visitados en todo known_links es 0.
Pros: refleja bloqueo real de movilidad global.
Contras: más caro y puede sentirse “menos local” (la solución podría estar en un nodo remoto conocido).
Si quieres mi recomendación v0: combina 1 + 2.

atasco = (no rutas nuevas desde nodo actual) AND (N uplinks sin novedades).
Si prefieres más estricto: 3 + 2.

atasco = (no rutas nuevas globalmente) AND (N uplinks sin novedades).
Dime cuál prefieres y lo ajusto.

Riesgo: podrías tener “movilidad global” teórica, pero práctica inalcanzable si el único camino nuevo está muy lejos y la nave no aguanta el desgaste ni tiene scrap suficiente para reparaciones.

Si quieres cubrir eso, te propongo extender el criterio con “alcanzable en coste razonable”. Tres opciones:

1. Distancia máxima “realista” desde el nodo actual
Atasco si no hay rutas a nodos no visitados dentro de MAX_MOBILITY_RANGE_LY (configurable).
Es simple y se alinea con el coste de viaje.
2. Costo de desgaste estimado
Calcula un coste aproximado de desgaste por ly (o por año de viaje) y compara con scrap actual o con un umbral de salud mínima.
3. Atasco si todos los destinos nuevos exceden el “presupuesto” de desgaste/scrap.
Tiempo máximo de viaje razonable
Atasco si todas las rutas nuevas implican ETA > MAX_TRAVEL_YEARS_FOR_MOBILITY (configurable).

Mi recomendación: combinar 3+2 con (1) por ahora.

“No hay rutas nuevas globales alcanzables dentro de X ly” y “N uplinks sin novedades”.
Así mantienes el failsafe diegético y evitas bloquear al jugador por rutas “teóricas” pero inviables.

[Escogemos 2+3+1]

- [x] Quiero que me ayudes a diseñar y desarrollar el sistema de generación del "universo/mundo", es decir, los distintos plots (después habrá que diseñar cómo el jugador obtiene las id's de nuevas localizaciones a las que poder viajar, pues no quiero que tenga siempre disponibles todos los destinos, y además quiero que los destinos y sus contenidos se vayan generando proceduralmente). Me gustaría que el universo estuviera "organizado" o dividido. Ayúdame tú a esa organización, pero, por lo pronto, se me ocurre que podría ser algo como lo siguiente (pero hazme sugerencias o corrígeme si algo no es muy realista): el universo accesible al jugador será una galaxia de forma de espiral (la vía láctea, aun que el Jugador no tiene por qué saberlo al empezar el juego): la galaxia estará por lo pronto dividida en tres regiones: halo (zona más externa), el disco, y bulbo (zona central de la galaxia, donde la densidad de estrallas es mayor, y en cuyo centro se encuentra en agujero negro supermasivo Sagitario A*). Esas partes no serán plots; pero se me ocurre que ciertas localizaciones o plots sólo puedan generarse en una des estas regiones u otras, y que en cada una de las regiones apliquen ciertas condiciones (por ejemplo, que en los sectores pertenecientes al bulbo haya más radiación, o que puedan darse ciertos eventos especiales específicos de cada región). Aparte de esas tres regiones, cada región deberia estar dividida en... ¿sectores quizá? Qué me sugieres? Deberían dividirse también los sectores, o será complicarlo mucho? Suponiendo que no se dividan, entiendo que en cada uno de esos sectores habría world_plots, no? Esos world_plots podrían ser estaiones abandonadas, naves abandonadas (o no abandonadas), derelicts, planetas... Por otra parte, ahora que lo pienso, hará falta conectar unos sectores con otros, de forma que no se pueda llegar a cualquiera desde cualquiera. ¿O es una complicación innecesaria? Lo que sí tengo más claro es que no me gustaría que la nave pudiera scanear plots a mucha distancia. Quizá sólo los plots dentre de su sector (o la división más pequeña que decidamos). Aparte de eso, las nuevas localizaciones (es decir los plots en nuevos sectores) sólo se podrán descubrir obteniendo información por otros medios: por ejemplo accediedo a los mails de una nave o al registro de navegación o cosas así. Dame ideas también a este respecto.



=== OPERATIONS ===

DRONES
- [x] Operaciones de salvage y de repair deberían estar dentro del comando drone.
- [x] La cantidad de scrap que se ordena recuperar con 'salvage' tiene que afectar al tiempo
que se tarda en llevar a cabo la tarea.
- [x] Establecer límite de scrap que se puede obtener de un derelict u objeto dockable.
- [x] debería haber un límite de scrap y un máximo de módules encontrables (y que todo esto sea configurable en el json).
- [x] Obtener scrap debería de hacerse con un dron (específico para las tareas de salvage),
sin tener el cual (o sin estar operativo y desplegado en el nodo adecuado) no debe ser posible
obtener scrap. 
- [x] Hay que ver cómo controlar para que al viajar o hibernar no "mueran" los drones por batería. Ahora mismo parece que si te los dejas fuera de su dock e hibernas no les pasa nada. Es como si hibernaran ellos también.
- [x] El drone deploy admite como target "power_core", "energy_distribution" o "sensors", además de ship_sector inexistentes. ¿Cómo es posible? Entiendo que tampoco debería admitir "power_core" o "energy_distribution" o "sensors" como targets. Entiendo que esos no son ship_sectors sino sistemas. Entiendo que los sistemas están localizados en ship_sectors. Los ship_sectors sí deberían ser lugares apropiados para desplegar los drones. 
- [x] Necesitamos un comando para abortar lo que sea que esté haciendo el dron!!
- [x] Si un drone se encuentra fuera de la nave propia y se intenta "desdockear" la nave propia (por ejemplo para dockear en otra localización o para emprender un viaje), me gustaría que saliera un mensaje de alerta advirtiendo de que el drone en cuestión no está en la nave propia y pidiendo confirmación para abandonarlo.
- [x] Se debería poder mover un dron desplegado a otro plot sin necesidad de llevarlo a dock antes y desplegar de nuevo. Quiero comando 'drone move'.
- [x] Las tareas de un mismo dron deberían ir en cola. Ahora mismo las hace simultáneamente. Si le mandas más de una antes de que acabe la anterior.
- [x] Los drones deben perder batería al trabajar. Deben recargarse al atracar (dock).
- [x] repair debería consumir algo. Como mínimo scrap. (La nave inicial debe por tanto empezar con una cantidad de scrap). 

JOBS
- [x] Un comando que liste los trabajos (jobs) en proceso o en cola.


NAVIGATION
- [x] no debe crearse ruta conocida desde el nodo actual al hub ECHO_7 hasta que ECHO_7 no sea descubierto. En el momento en que se descubra ECHO_7, sí debe automáticamente crearse una ruta conocida también, pues se supone que ECHO_7 se encuentra en el mismo nodo de la nave del PJ.




=== SYSTEMS ===

CARGO
- [x] Ahora mismo tenemos algo llamado "inventario". Estoy hay que modificarlo. El inventario debería ser un sector de la nave del PJ. Muchas naves (la del PJ incluida) tienen que tener un sector de carga o almacén, es decir, una bodega. Esa bodega junto con su id debe aparecer al ejecutar el comando sectors. Por lo demás, por ahora el funcionamiento de ese "inventario" será igual que actualmente. 
- [x] Otra cosa: el comando "inventory" debe conservarse, pero quiero modificar algo. Si se añade al inventario scrap nuevo o un módulo o lo que sea, no se verá reflejado en la información correspondiente del status ni en la información que genera el comando "inventory" hasta que no se ejecute el commando "inventory update" [P.D. ahora 'cargo audit']. No obstante, en la información que imprime "status" y en la información que imprime "inventory" debe aparecer de algún modo la indicación de que hay cambios en bodega y que es necesario inventariar para actualizar la información. Ahora bien, la operación "inventory update" quiero ser un "job", un trabajo, con su  orrespondiente ETA. La idea es que al introducir ese comando se ejecute un trabajo de actualización del inventario o inventariado de lo que hay en la bodega, y que eso tarde un rato.

SENSORS
- [x] Con los sensors con health 1.00, al intentar encenderlos con "system on sensors" me ha salido este mensaje:
[CMD] [WARN] boot_blocked :: System on blocked: system too damaged
- [x] Comando scan detecta a la propia nave. Filtrar esto.

DRONE BAY
- [x] Entiendo que el drone_bay se tiene que poder desconectar, para ahorrar energía.


=== MANUALS ===

- [x] hay que crear manuales para /manuals/systems/power_core , security, life_support y los sistemas que faltan.



=== TEXTUAL UI ===
- [x] Implementar Textual como frontend alternativo (no obligatorio).
- [x] Atajos:
  Alternar foco del panel:  alt+j/k
  Scroll arriba/abajo en panel activo: k/j
  Comandos textual: ctrl+p
- [x] cuando se arranca el juego, debería por defecto estar activo el panel en el que se introducen órdenes. Ahora mismo no está funcionando así.
- [x] Me gustaría darle a la interfaz Textual un aspecto mucho más parecido a como se vería con Curses. Quiero además que el color de fondo sea igual en todos los paneles. No quiero que se dibujen líneas de contorno en los paneles.
- [DESCARTADO] El panel de JOBS y de ALERTS deben tener scroll ambos. Pero no quiero ninguna barra de scroll (ocupa demasiado espacio en pantalla); prefiero, si es posible, que cuando el texto no entra en la caja del panel aparezca un pequeño símbolo de flecha hacia abajo (o algo así) en la parte inferior derecha del panel, indicando así que hay más texto que no se está biendo y que está disponible la posibilidad de hacer scroll para verlo.
- [X] El contenido de los paneles fijos de la interfaz Textual es el mismo que el que se imprime al introducir el comando correspondiente (por ejemplo, en el panel status se observa exactamente lo mismo que se imprime cuando se escribe "status"). Esto me gustaría modificarlo. Es decir: por razones de diseño y espacio, quiero que lo que se ve en cada uno de los paneles pueda ser diferente a lo que se imprime al introducir un comando. En el panel status, por ejemplo, no quiero que se vea la línea de "time", ni de "location", ni de "power", ni de "inventory". Sólo quiero que aparezcan las líneas que refieren a los sistemas (core_os, life_support, etc.). Es posible?

- [x] en el header no quiero que ponga "mode=" sino "ship_mode="