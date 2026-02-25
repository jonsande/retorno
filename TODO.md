========================
=== TODO AND PROMPTS ===
========================

=== PROLOGUE ===

- [ ] La primera vez que se ejecuta el juego no debe fallar nunca el deploy!.


=== DRONES ===

- [ ] Necesitamos que se puedan recuperar (salvage) nuevos drones. Una sub-orden nueva: 'drone salvage drone' (que admita también el plural 'drone salvage drones'). Estoy incluye incluir tablas apropiadas en los hubs authored y correspondientes ajustes en la generación procedural del botín.


=== NAVIGATION / ROUTES / WORLD GEN ===

- [ ] Los viajes deben ser más peligrosos. Los de muchos años luz deben, por lo pronto, exponerte a mucha radiación. Esto limitará el ir pegando saltos por ahí a lo loco. Viajar a 40 años luz debería ser a costa de llegar con los sitemas hechos polvo.
- [x] Al hacer scan, no se suponía que debía establecerse la distancia fina a los hubs con distancia de 0ly? No lo está reflejando el nav.
- [ ] Actualizar manual dock! Tiene que aclarar que se puede hacer un dock cuando se está a "distancia fina".
- [x] Indicar en listado nav qué lugares han sido visitados.


=== SYSTEMS ===

DRONE BAY
- [ ] Necesitamos que drone_bay tenga una capacidad máxima para albergar drones.

VITALS
- [ ] La cámara de sarcófagos será un sistema independiente? o retocar life_support?
- [ ] Hay que desarrollar una v0 de vitals. El usuario tiene también que mantener a su PJ. La hibernación debe tener su coste (y/o riesgos). También tiene que haber algún consumo de alimento, y un generador de oxígeno que requiera alguna forma de mantenimiento o combustible o...

=== COMMANDS ===

- [x] Ahora mismo se informa del límite de scrap antes de llevar a cabo la operación de salvage si se ordena una cantidad mayor a la disponible. Esto no debería suceder. El jugador no debe saber antes de terminar el job de scrap cuál es el número total de scrap que hay en esa localización.
- [x] Locate debe admitir node_id's, tal como lo indica el Hint del drone deploy (cuando no se le da un tarjet válido).
- [ ] jobs debe admitir número de entradas que se quieren imprimir en pantalla, o filtros.
- [x] El comando contacts debe imprimir también la distancia a la que se encuentra cada contacto y si hay o no ruta conocida.



=== LORE ===

- [ ] Dentro de la carpeta /lore, me interesa una carpeta llamada "singles", pensada para albergar documentos txt que serán de ser después "colocados" proceduralmente en el mundo.

- [!] En el estado actual del juego, ¿cómo se están distribuyendo por el mundo los archivos txt y los packs? Cómo funciona corridor_01.json? Cómo funcionan los "arcs"Comprobar.

- [ ] Pensándolo mejor, sí quiero failsafe para algunos arcos. O mejor dicho, quiero tener la opción. Quiero que sea configurable para cada arco y/o .......


=== INTEL ===

- [!] Sistema procedural para descubrir información de rutas a nodos conocidos pero sin ruta conocida. A través de uplink y a través de un flag específico en los txt. El caso es que ahora mismo los datos corruptos (información entre etiquetas [INTEL][/INTEL] no procesable) genera contactos (nodos) sin ruta. Los INTEL incrustados también pueden generar (esto hay que confirmarlo) contactos authored pero sin ruta. Además, el generador de contactos de uplink _discover_routes_via_uplink() puede generar contactos sin rutas (confirmarlo). Así que el caso es que se van generando por distintas vías contactos sin ruta, y tiene que diseñarse una manera procedural de conseguir intel de rutas a contactos existentes, para que todo marche. Empezar por preguntar a codex: Actualmente ¿de qué maneras se pueden averiguar rutas para contactos conocidos (contactos authored y contactos procedurales)?

- [ ] Los incrustados [INTEL]...[/INTEL] no debe verlos el usuario.



=== MODULES ===

- [ ] Debe haber algún límite de módulos (para estimular los builds). Y algunos deberán tener penalizaciones además de bonificaciones.

- [ ] Módulo que hace que los drones vuelvan automáticamente al dock (si es posible) cuando su batería cae a cierto nive.

- [ ] Módulo instalable que permita automatizar ciertas tareas en tránsito (aunque el PJ esté hibernando). Por ejemplo, llevar a cabo un scan cada x tiempo (configurable por el jugador), y dar la opcion de deshibernar en caso de que se detecte algo nuevo.



=== OTROS / SIN CATALOGAR ===

- [x] El formato del tiempo de "unacked=" en alerts cuál es? Sólo en segundos? Me gustaría que siguiera el mismo formato que las ETA de los travels y los jobs.

- [ ] Enterarse de cuales son las consecuencias de no atender una alerta crítica u otra (pues ahora mismo no lo tengo muy claro).

- [ ] La cantidad inicial de scrap debe ser configurable desde balance.py.

- [x] Ahora mismo, cuando se empieza el juego, se comienza como "location: UNKNOWN_00 (Unknown) [in orbit]". Esto me hace pensar que además de docked y in orbit hace falta un tercer estado, que sea ni 'docked' ni 'in orbit' (por ejemplo: cuando se cancela un viaje y la nave queda en un nodo temporal ¿en qué estado se encuentra?). Se supone que la nave RETORNO_ship al inicio del juego simplemente está "parada" en el espacio, no orbitando nada. Dime qué opinas de esto y si ves algún posible conflicto o error con lo que te planteo.

- [x] Ahora mismo, al comienzo de juego, cuando el jugador consigue encender el sistema sensors se detecta una señal automáticamente (por cierto, ¿dónde se configura esto?):
  [AUTO] [INFO] signal_detected :: Signal detected: ECHO_7
Al introducir después el comando 'nav' se obtine esto:
  === NAV ROUTES ===
  (no known routes from UNKNOWN_00)
  Nearby contacts without known route:
  - Derelict A-3 (derelict) sector=S+004_-001_+000 id=DERELICT_A3 dist=45.06ly
  - ECHO-7 Relay Station (station) sector=S+000_+000_+000 id=ECHO_7 dist=0.00ly
  - Harbor-12 Waystation (station) sector=S+001_+000_+000 id=HARBOR_12 dist=12.65ly
  Try: scan, route, intel, uplink (at relay/waystation), or acquire intel.
Como se ve, ECHO_7 aparece entre los contactos conocidos pero sin ruta conocida. Por otra parte (corrígeme si me equivoco) la nave del jugador (RETORNO_SHIP) se encuentra a) en el mismo sector que ECHO_7, b) a una distancia de 0.00ly de HECHO_7, y c) no en órbita (in orbit) de ECHO_7 ni atracada (docked) en ECHO_7. Me gustaría entonces modificar algunas cosas (o asegurarse de que ya están implementadas, si fuera el caso). Me gustaría que cuando se cumplan esas tres condiciones [ a) la nave del jugador se encuentra en el mismo sector de un hub, b) ese hub está a 0.00ly de distancia, y c) la nave del jugador no está ni docked ni tampoco "in orbit" de ese hub], pase lo siguiente: si el hub figura entre las localizaciones conocidas pero sin ruta conocida, no se podrá viajar a esa ruta con 'travel' hasta que no se conozca ruta; se podrá averiguar/establecer la ruta y la distancia "fina" a ese hub con el comando 'route <node_id>'; una vez conocida la ruta, se calculará la distancia a ese hub ya no en años-luz sino en kilómetros (en caso de que el 'config set lang' sea 'es') o millas (en caso de que sea 'en'), y a partir de entonces el comando 'nav' reflejará la distancia a ese hub en esas unidades (siempre y cuando, insisto, el hub en cuestión esté en el mismo sector que la nave del jugaddor y a distancia 0.00ly); aunque no se use el comando 'route <node_id>', el comando 'scan' también servirá para hacer el cálculo fino de distancia (en km o millas) al hub (pero no servirá para averiguar/establecer ruta al hub, como sí hacía route); cómo calcular o decidir esa distancia te lo dejo a ti (puedes ser creativo, pero siempre prefiriendo las opciones más consistentes); en caso de que el jugador decida viajar a ese hub (y así entrar en su órbita), el ETA del viaje se calculará en función a esa distancia; llegar al destino significa entrar "in orbit" de ese hub (no docked), y quedarse a distancia de 0 (kilómetros/millas) de ese hub.
Antes de implementar nada, dime qué opinas, si ves algún conflicto o problema potencial.

- [ ] En el estado actual del juego, los sectores son considerados ellos mismos nodos? Se puede viajar a un sector aunque no se conozca ninguna localización/hub en él? Cuál es el nombre que reciben los sectores proceduralmente generados?


- [-] Hay que mejorar la definición de "atasco" urgenemente. Pasar a una v1. No se trata de que se generen por arte de magia destinos. Hace falta comprobar detenidamente si el jugador tiene algún modo (aunque él no lo sepa) de lograr una localización (a través de uplink o scan o salvage data u otro).

- [ ] Hay que modificar el comando "map". No es muy intuitivo. Podría ser algo como "ship sectors" o "map ship".

- [ ] El comando travel devería ser el comando nav. Si se escribe sin parámetro, lista destinos y rutas, si con parámetro, funciona como travel.

- [?] Al  hacer 'route <node_id>' a un node_id para el que ya conoces ruta,  no se debería iniciar el job. Debería salir un mensaje informando de que ya se conoce ruta a ese objetivo. Por otra parte, debería de haber un comando para cancelar jobs en curso.

- [ ] Al iniciar la hibernación, debería de salir un mensaje (localizado) diciendo algo así como "Iniciando secuencia de hibernación", y una serie de mensajes (meramente narrativos) diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la criogenización, y una cuenta atrás de 10 segundos. Después, debe limpiarse la pantalla de logs, esperar 3 segundos e imprimirse una serie de mensajes diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la descriogenización, junto con un mensaje (que se repetirá siempre), advirtiendo de que hay un problema crítico y no es posible descriogenizar completamente al sujeto del sarcófago (es decir, al Personaje Jugador). El sarcófago del PJ debe tener un id, por cierto. 

- [ ] Necesitamos una merjor organización del help.

- [ ] Los jobs se numeran como J00001, J00002, etc. No me gusta esto. Implica que el límite está en 99999 jobs. Preveo que el jugador vaya a llevar a cabo más jobs que esos. No hay otra manera de identificar los jobs?

- [ ] Hay muchos mensajes (o partes de mensajes) que aparecen en español cuando el idioma de configuración es el inglés, y al revés, mensajes o partes de mensajes en inglés cuando deberían estar en español. Un ejemplo: estando la configuración en inglés, me ha salido este  mensaje: "ParseError: Subcomando power desconocido. Usa: power status | power plan cruise|normal | power shed/off <system_id> | power on <system_id>"



- [ ] se puede usar el comando "scan" estando el servicio "datad" offline?

- [?] En el frontend Textual algunos comandos no se autocompletan. 

- [!] Al hibernar para viajar el "time" debería reflejar los años que han pasado desde que el PJ se despertó por primera vez. Necesitamos un reloj mejor. No vale sólo indicar segundos, pues el número es demasiado grando. Necesitamos un reloj que indique años luz, días, horas, minutos, segundos (o algo así; díme tú qué opinas).

- [ ] Ahora mismo los manuals se han generado con un tono "diegético". Me gustaría ver cómo sería la versión más "técnica", pues chatgpt y codex me la han propuesto varias veces pero siempre la he rechazado sin llegar a ver cómo sería.

- [ ] El comando "travel" hay que cambiarlo quizá por "navigate" (o algo primero como "trazar ruta" y después "navigate").

- [!] Ahora mismo si queremos viajar a "S+000_-001_-001:02: Relay-97 (relay) dist=1.30ly" hace falta introducir "travel S+000_-001_-001:0". Me gustaría que también se pudiera introducit "travel Realy-97" simplemente, y que el autocompletado funcionara. Y por cierto: ¿qué quiere decir "000_-001_-001:02"? ¿Son unas coordenadas? Si es así, creo que estaría bien indicar de algún modo que esa numeración son unas coordenadas. 

- [ ] También creo que tendría que aparecer en primer lugar el nombre de la hubicación (si la tiene), por ejemplo Relay-97 (relay) dist=1.30ly coord=S+000_-001_-001:02""


- [ ] dose es la dosis acumulada de radiación que ha recibido el dron (en rad). Se incrementa cada tick en función de la radiación ambiental (state.ship.radiation_env_rad_per_s) y el shield_factor del dron:
drone.dose_rad += r_env * shield_factor * dt
Ahora mismo es informativo (no afecta directamente a integridad/batería), pero lo usamos como base para futuras penalizaciones o fallos por exposición prolongada. Si quieres, puedo añadir un aviso cuando supere umbrales, o hacerlo afectar a la integridad.


- [-] Diseñar el sistema de encontrar nuevos destinos. A nivel de sistema solar, tiene que ser posible detectar vía escáneres o algo así; a nivel de galaxia, quizá sólo a partir de información que se obtenga (cartas de navegación). Más allá de galaxia, no se sabe. El comando contacts/scan debe tener un alcance pequeño relativamente.

- [ ] Cómo se desconectan sistemas ahora mismo? Cómo se reduce carga de energía?

- [ ] Quiero que al arrancar el juego por primera vez se imprima un mensaje "técnico" diegético que dé a entender de un modo u otro que ha habido un error y que se está ejecutando una instrucción de emergencia de descriogenización del sarcófago; que no se ha podido completar satisfactoriamente la descriogenización de la persona que hay dentro (el personaje jugador) del <id_sarcófago> por un problema indeterminado en el sistema; que se procede a intentar poner al huesped en estado consciente para que pueda llevar a cabo operaciones a través de la terminal conectada a su cerebro. También se indicará que el reloj/calendario interno de la nave ha sufrido un fallo indeterminado o algo así y que todo ha sido puesto a 0 (buscar la manera técnica diegética de decir esto). Este mensaje se imprimirá al iniciar el juego, pero quedará también como mail, de forma que se podrá volver a leer, en su versión española si se cambia la configuración de idioma. También quiero que se generen otros 5 mails con un texto muy similar, pero refiriendo cada uno de ellos a un sarcófago diferente, e indicando que ha fallado la descriogenización, y que no se detectan constantes vitales en el huesped (los 5 mails serán iguales, sólo cambiará <id_sarcófago>, de modo que al leerlos se pueda deducir que todos los compañeros del Personaje Jugador han muerto). Antes de construir la instrucción para codex, constrúyeme una versión del mensaje, para que lo pulamos.

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
- [ ] El panel status debería poder modificarse por otro.
- [ ] Los paneles, excepto header, botton, comandos y logs deberían poder activarse desactivarse, para tener más espacio para logs.
- [ ] Colores. Y archivo de configuración de colores, para poder configurar paletas.



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

Despertar por eventos
Durante hibernación, si ocurre un CRITICAL (p.ej. POWER_BUS_INSTABILITY, LIFE_SUPPORT_FAILURE), el sistema despierta al jugador automáticamente:

“WAKE_EVENT: life_support anomaly”
Esto evita “morir offscreen” y crea puzzles emergentes.

Chequeos periódicos
Permite configurar “wake every N years/days” (cuando desbloquees software).

hibernate until_arrival --wake-every 2y

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

