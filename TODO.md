========================
=== TODO AND PROMPTS ===
========================


=== PROLOGUE ===

- [ ] La primera vez que se ejecuta el juego no debe fallar nunca el deploy!.


=== DRONES ===

- [ ] Necesitamos que se puedan recuperar (salvage) nuevos drones. Una sub-orden nueva: 'drone salvage drone' (que admita también el plural 'drone salvage drones'). Estoy incluye incluir tablas apropiadas en los hubs authored y correspondientes ajustes en la generación procedural del botín.

- [ ] La orden "drone deploy <drone_id> <sector_id>" debería volver a admitir <system_id>, como hacía antes, pero generando un mensaque de que el drone se está desplegando en el sector_id en que se encuentra el system_id solicitado.

- [ ] Hace falta meter hints sobre cómo averiguar el id de los drones y de los system_id (por ejemplo en el error de "repair", en el man de drone, o en el error de drone repair). Mencionar en ese hint que siempre se puede pulsar dos veces TAB para que te liste las opciones que se pueden introducir (y, por tanto, averiguar directamente los id's que hacen falta)


=== NAVIGATION / ROUTES / WORLD GEN ===

- [ ] En las naves, estaciones, etc. visitadas se genera algo de scrap con el tiempo. Esto responde a la idea de que las estaciones, naves, etc. van deteriorándose y siempre es posible recuperar de ellas algo nuevo. También preveo algún módulo que permita desmantelar estaciones, algo que llevaría mucho tiempo hacer, pero que produciría mucho scrap.
- [ ] ¡Las estaciones, naves, etc. deben deteriorarse y y acabar desapareciendo con el tiempo! Todo rastro humano debe ir desapareciendo, teniendo en cuenta que una estación o nave abandonada difícilmente puede sobrevivir millones de años en el universo. Para una versión 3 o 4 del juego, se puede quizá diseñar un evento que haga que (alguna especie desconocida o resto de vida humana) vuelva a fabricar estaciones, naves, navegar por el espacio, etc. 
- [ ] Alguna forma de generar el grafo del mundo en el estado actual, bien sea con fines de debug o con fines de que pueda en un futuro desarrollarse un módulo instalable que permita visualizarlo en pantalla del juego.
- [ ] Los viajes deben ser más peligrosos. Los de muchos años luz deben, por lo pronto, exponerte a mucha radiación. Esto limitará el ir pegando saltos por ahí a lo loco. Viajar a 40 años luz debería ser a costa de llegar con los sitemas hechos polvo.
- [x] Al hacer scan, no se suponía que debía establecerse la distancia fina a los hubs con distancia de 0ly? No lo está reflejando el nav.
- [x] Actualizar manual dock! Tiene que aclarar que se puede hacer un dock cuando se está a "distancia fina".
- [x] Indicar en listado nav qué lugares han sido visitados.


=== SYSTEMS ===

DRONE BAY
- [ ] Necesitamos que drone_bay tenga una capacidad máxima para albergar drones.

VITALS
- [ ] La cámara de sarcófagos será un sistema independiente? o retocar life_support?
- [ ] Hay que desarrollar una v0 de vitals. El usuario tiene también que mantener a su PJ. La hibernación debe tener su coste (y/o riesgos). También tiene que haber algún consumo de alimento, y un generador de oxígeno que requiera alguna forma de mantenimiento o combustible o...

- [ ] Debe haber un límite de scrap que se puede tener. O un límite de volumen. Medir las cosas por volumen.

ENERGY



=== COMMANDS ===

- [ ] Estando docked en CURL_12, al hacer "uplink" el juego crashea y me devuelve un error "AttributeError: 'list' object has no attribute 'events'".

- [ ] Creo que el comando logs sigue indicando cuál es la cantidad de scrap total recupelable (available) al ordenar salvage scrap. No debería mostrarse. Eso el jugador sólo debe saberlo una vez el job de salvage ha finalizado (actualmente se generan mensajes correctos en este sentido). Sólo corregir la información que se ofrece a este respecto cuando el job está todavía queued.

- [x] comando undock para volver a in orbit.

- [ ] Parece que ahora se puede desactivar core_os y otros sistemas vitales que no deberían poder desacivarse. Pedirle a gpt que razone esto y me diga cuales tiene sentido y cuales no poder apagar.

- [ ] Estoy pudiendo ejecutar "route solve CURL_12" desde ECHO_12 teniendo todos los sitemas apagados. ¿Por qué?

- [x] Simplificar comandos 'nav' y 'travel'. Me inclino por sustituir el comando "travel <node_id|name>", "travel --no-cruise <dest>" y "travel abort" por "nav <node_id|name>", "nav --no-cruise <dest>" y "nav abort". Además, 'nav' debe ser un alias de 'navigation' (o sea, que funcione tanto escribir 'nav' como 'navigation'). El comando 'nav' actual, sin parámetros, lo sustituiremos por "nav routes" (o sea, que el comando "nav routes" hará lo que actualmente el comando "nav"). Después de implementar estos cambios hay que actualizar los manuales (localizados) en consecuencia, y el help. Por otra parte, si el usuario introduce el comando "nav" a secas, se debe imprimir un típico mensaje ParseError explicando el uso del comando.

- [x] Los ParseError no parecen estar localizados. Con en lang configurado en inglés salen mensajes como este:
ParseError: Uso: travel <node_id|name> | travel --no-cruise <dest> | travel abort
La palabra "uso" es español. Hay que localizar estos mensajes de error. Aprovechar para revisar que estén bien localizados otros mensajes de error, advertencias y hints.

- [x] Ahora mismo se informa del límite de scrap antes de llevar a cabo la operación de salvage si se ordena una cantidad mayor a la disponible. Esto no debería suceder. El jugador no debe saber antes de terminar el job de scrap cuál es el número total de scrap que hay en esa localización.
- [x] Locate debe admitir node_id's, tal como lo indica el Hint del drone deploy (cuando no se le da un tarjet válido).
- [x] jobs debe admitir número de entradas que se quieren imprimir en pantalla, o filtros.
- [x] El comando contacts debe imprimir también la distancia a la que se encuentra cada contacto y si hay o no ruta conocida.



=== LORE ===

- [!] El contacto y la ruta a ARCHIVE_01 me ha aparecido haciendo mi primer uplink en ECHO_7. Cómo es posible? Pensé que el arco estaba configurado para que costara más pasos lograr esa ruta. Acaso ha aparecido a través de uplink de forma aleatoria? La idea que yo tenía era: en ECHO_12 el documento echo_cache te proporciona el contacto (pero no la ruta) HARBOR_12. En HARBOR_12 el documento 0141 te proporciona el link a ARCHIVE_01. El link a ARCHIVE_01, pues, tratándose del intel primario de un arco diseñado, sólo se podía (o eso pensaba yo) obtener a través del documento 0141 de HARBOR_12, y de ningún otro modo más. Aclárame qué está pasando, y cómo están funcionando los arcos.


- [x] En el Virtual File Sistem no debe usarse ningún directorio llamado "lore". No es muy diegético. Por ejemplo, en el example_unforced encontramos esto:
  "path_template": "/logs/lore/example_unforced_note.{lang}.txt"
Hay que buscar una solución más diegética a esto. La información de lore que reciba el jugador debe almacenarse en su FS de un modo coherente y claro, pero sin ninguna referencia a la palabra "lore".

- [x] Dentro de la carpeta /lore, me interesa una carpeta llamada "singles", pensada para albergar documentos txt que serán de ser después "colocados" proceduralmente en el mundo.

- [x] Manual del comando mail. 

- [x] Perfeccionar comando mail.

- [x] Pensándolo mejor, sí quiero failsafe para algunos arcos. O mejor dicho, quiero tener la opción. Quiero que sea configurable para cada arco y/o .......

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

- [ ] Sistema de escalado de privilegios. Actualmente sólo se tiene acceso a archivos con un nivel de acceso de GUEST. No sé cuántos niveles hay actualmente definidos, pero me interesa que haya estos: GUEST, ENG, MED, OPS, SEC. Tenemos entonces que desarrollar formas diegéticas de elevar el acceso por distintos medios:
  - [ ] 0) Versión 0 muy simple pero funcional (MVP): comandos "auth status" "auth recover eng", "auth recover med". Requisitos: data_core >= LIMITED, datad running, opcional: securityd para MED (o al revés). Efecto: job de x segundos o minutos que, al completarse, añade ENG o MED a auth_levels. Resultado narrativo: empiezas en GUEST; puedes leer el mail del PJ; más tarde recuperas ENG; entonces ves los logs de los otros sarcófagos
  - [ ] 1) Boot de servicios + self-tests: La más natural para tu juego ahora mismo. Ejemplo: cuando data_core está operativo y datad corriendo, puedes ejecutar:
    auth probe
    auth recover eng
    auth recover med
  Y eso hace un job. Requerirá tiempo y energía, y, si sale bien, añade ENG o MED (pero quizá hay que limitar esto a la nave/station en la que se está docked, o a la propia nave; de forma que a esos comandos habría que añadires un id, como por ejemplo ECHO_7 o RETORNO_SHIP).
  Justificación diegética: estás restaurando tablas de permisos/certificados desde caché local.
  - [ ] 2) Salvage de credenciales desde nodos remoto (muy buena para la experiencia de exploración del Jugador): ejemplo: en un hospital ship o una estación técnica encuentras:
    med_override.token
    eng_cert.fragment
  Al extraerlos: auth import /remote/.../med_override.token
  obtienes acceso MED en ese hospital ship. [Esto convierte los permisos en parte del loop de exploración.]
  - [ ] 3) Módulos instalables: secure_coprocessor, legacy_auth_bridge, med_console_patch. Al instalar uno, desbloqueas cierno nivel o reduces dificultad de recuperación. [Esto da progresión material.]
  - [ ] 4) Acceso contextual/temporal (muy interesante, pero para más adelante): 
    a dockear en cierta station, recibes acceso temporal (ENG session token valid while docked), o sólo durante un timpo (contador atrás); o tras un uplink en un relay.

Esto da variedad, pero no lo haría aún como primer sistema. 


=== MODULES ===

- [ ] Debe haber algún límite de módulos (para estimular los builds). Y algunos deberán tener penalizaciones además de bonificaciones.

- [ ] Módulo que hace que los drones vuelvan automáticamente al dock (si es posible) cuando su batería cae a cierto nive.

- [ ] Módulo instalable que permita automatizar ciertas tareas en tránsito (aunque el PJ esté hibernando). Por ejemplo, llevar a cabo un scan cada x tiempo (configurable por el jugador), y dar la opcion de deshibernar en caso de que se detecte algo nuevo.


=== WIN/LOST CONDITIONS AND LOOPS ===



=== OTROS / SIN CATALOGAR ===

- [ ] Pegarle a chatGPT:
  - debug lore después de 1–2 uplinks
  - un ejemplo del archivo entregado por captured_signal o ship_os_mail
  Para calibrar probabilidades (para que no “llueva lore” y siga siendo calmado).

- [x] Parece que se ha estropeado el autocomplete!

- [ ]

- [x] no sé si está funcionando bien el auto cruise, pues aunque ha subido el net a positivo, veo que todos los sistemas están activos.

- [x] En el output despues de hibernate until_arrival, el tiempo de "sleeping for" y "woke up after" debería escalarse. Sin han sido unos días, no tiene sentido que ponga 0.00y. Me gustaría usar aquí los mismos formatos que usamos para las ETA de los travels y los jobs.

- [x] Cuando se intenta dockear estando lejos sale el mensaje "action blocked: not at ECHO_7". Quizá debería decir "Not in ECHO_7 orbit" o algo así.

- [x] El formato del tiempo de "unacked=" en alerts cuál es? Sólo en segundos? Me gustaría que siguiera el mismo formato que las ETA de los travels y los jobs.

- [ ] Enterarse de cuales son las consecuencias de no atender una alerta crítica u otra (pues ahora mismo no lo tengo muy claro).

- [x] La cantidad inicial de scrap debe ser configurable desde balance.py.

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

- [-] Hay que mejorar la definición de "atasco" urgenemente. Pasar a una v1. No se trata de que se generen por arte de magia destinos. Hace falta comprobar detenidamente si el jugador tiene algún modo (aunque él no lo sepa) de lograr una localización (a través de uplink o scan o salvage data u otro).

- [ ] Hay que modificar el comando "map". No es muy intuitivo. Podría ser algo como "ship sectors" o "map ship".

- [x] El comando travel devería ser el comando nav. Si se escribe sin parámetro, lista destinos y rutas, si con parámetro, funciona como travel.

- [?] Al  hacer 'route <node_id>' a un node_id para el que ya conoces ruta,  no se debería iniciar el job. Debería salir un mensaje informando de que ya se conoce ruta a ese objetivo. Por otra parte, debería de haber un comando para cancelar jobs en curso.

- [ ] Al iniciar la hibernación, debería de salir un mensaje (localizado) diciendo algo así como "Iniciando secuencia de hibernación", y una serie de mensajes (meramente narrativos) diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la criogenización, y una cuenta atrás de 10 segundos. Después, debe limpiarse la pantalla de logs, esperar 3 segundos e imprimirse una serie de mensajes diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la descriogenización, junto con un mensaje (que se repetirá siempre), advirtiendo de que hay un problema crítico y no es posible descriogenizar completamente al sujeto del sarcófago (es decir, al Personaje Jugador). El sarcófago del PJ debe tener un id, por cierto. 

- [ ] Necesitamos una merjor organización del help.

- [x] Los jobs se numeran como J00001, J00002, etc. No me gusta esto. Implica que el límite está en 99999 jobs. Preveo que el jugador vaya a llevar a cabo más jobs que esos. No hay otra manera de identificar los jobs?

- [ ] Hay muchos mensajes (o partes de mensajes) que aparecen en español cuando el idioma de configuración es el inglés, y al revés, mensajes o partes de mensajes en inglés cuando deberían estar en español. Un ejemplo: estando la configuración en inglés, me ha salido este  mensaje: "ParseError: Subcomando power desconocido. Usa: power status | power plan cruise|normal | power shed/off <system_id> | power on <system_id>"



- [ ] se puede usar el comando "scan" estando el servicio "datad" offline?

- [?] En el frontend Textual algunos comandos no se autocompletan. 

- [x] Al hibernar para viajar el "time" debería reflejar los años que han pasado desde que el PJ se despertó por primera vez. Necesitamos un reloj mejor. No vale sólo indicar segundos, pues el número es demasiado grando. Necesitamos un reloj que indique años luz, días, horas, minutos, segundos (o algo así; díme tú qué opinas).

- [ ] Ahora mismo los manuals se han generado con un tono "diegético". Me gustaría ver cómo sería la versión más "técnica", pues chatgpt y codex me la han propuesto varias veces pero siempre la he rechazado sin llegar a ver cómo sería.

- [x] El comando "travel" hay que cambiarlo quizá por "navigate" (o algo primero como "trazar ruta" y después "navigate").

- [-] Ahora mismo si queremos viajar a "S+000_-001_-001:02: Relay-97 (relay) dist=1.30ly" hace falta introducir "travel S+000_-001_-001:0". Me gustaría que también se pudiera introducit "travel Realy-97" simplemente, y que el autocompletado funcionara. Y por cierto: ¿qué quiere decir "000_-001_-001:02"? ¿Son unas coordenadas? Si es así, creo que estaría bien indicar de algún modo que esa numeración son unas coordenadas. 

- [ ] También creo que tendría que aparecer en primer lugar el nombre de la hubicación (si la tiene), por ejemplo Relay-97 (relay) dist=1.30ly coord=S+000_-001_-001:02""


- [ ] dose es la dosis acumulada de radiación que ha recibido el dron (en rad). Se incrementa cada tick en función de la radiación ambiental (state.ship.radiation_env_rad_per_s) y el shield_factor del dron:
drone.dose_rad += r_env * shield_factor * dt
Ahora mismo es informativo (no afecta directamente a integridad/batería), pero lo usamos como base para futuras penalizaciones o fallos por exposición prolongada. Si quieres, puedo añadir un aviso cuando supere umbrales, o hacerlo afectar a la integridad.


- [-] Diseñar el sistema de encontrar nuevos destinos. A nivel de sistema solar, tiene que ser posible detectar vía escáneres o algo así; a nivel de galaxia, quizá sólo a partir de información que se obtenga (cartas de navegación). Más allá de galaxia, no se sabe. El comando contacts/scan debe tener un alcance pequeño relativamente.

- [x] Quiero que al arrancar el juego por primera vez se impriman una serie de mensajes "técnicos" diegéticos que dén a entender de un modo u otro que ha habido un error y que se está ejecutando una instrucción de emergencia de descriogenización del sarcófago número 5. Después una serie de mensajes técnicos diegéticos delas operaciones que se estarían llevando para la descriogenización; llegando un punto en que se produzca un mensaje que venga de algún modo a decir que no se ha podido completar satisfactoriamente la descriogenización de la persona que hay dentro (el personaje jugador) del <id_sarcófago> por un problema indeterminado en el sistema; que las constantes vitales del huesped son normales y que se procede a intentar poner al huesped en estado consciente para que pueda llevar a cabo operaciones manuales a través de la terminal conectada a su cerebro (quiero una forma técnica diegética de decir esto, que suene creíble y con terminología técnica). También se indicará que el reloj/calendario interno de la nave ha sufrido un fallo indeterminado o algo así y que todo ha sido puesto a 0 (buscar la manera técnica diegética de decir esto). Me gustaría que entre mensaje y mensaje se produjera una pausa de unos 3 segundos (configurable). También me gustaría, si es posible, un efecto tipewriting al imprimir cada mensaje (activable o desactivable desde balance.py). Estos mensajes se imprimirán al iniciar un nuevo juego, pero quedará también como mail (localizado). También quiero que se generen otros 5 mails con un texto muy similar, pero refiriendo cada uno de ellos a un sarcófago diferente (sarcófago 1, 2, 3, 4, y 6), e indicando que ha fallado la descriogenización, y que no se detectan constantes vitales en el huesped (los 5 mails serán iguales, sólo cambiará <id_sarcófago>, de modo que al leerlos se pueda deducir que todos los compañeros del Personaje Jugador han muerto). Antes de construir la instrucción para codex, constrúyeme una versión del mensaje, para que lo pulamos. Dime también si algo de lo que te planteo puede generar algún conflicto o problema.

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

