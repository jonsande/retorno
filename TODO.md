========================
=== TODO AND PROMPTS ===
========================


=== PROLOGUE ===

- [ ] La primera vez que se ejecuta el juego no debe fallar nunca el deploy!.


=== DRONES ===

- [ ] Necesitamos que se puedan recuperar (salvage) nuevos drones. Una sub-orden nueva: 'drone salvage drone' (que admita también el plural 'drone salvage drones'). Estoy incluye incluir tablas apropiadas en los hubs authored y correspondientes ajustes en la generación procedural del botín.

- [ ] La orden "drone deploy <drone_id> <sector_id>" debería volver a admitir <system_id>, como hacía antes, pero generando un mensaque de que el drone se está desplegando en el sector_id en que se encuentra el system_id solicitado.

- [ ] Hace falta meter hints sobre cómo averiguar el id de los drones y de los system_id (por ejemplo en el error de "repair", en el man de drone, o en el error de drone repair). Mencionar en ese hint que siempre se puede pulsar dos veces TAB para que te liste las opciones que se pueden introducir (y, por tanto, averiguar directamente los id's que hacen falta)

- [ ] Opción de desmantelar drones para obtener scrap.


=== NAVIGATION / ROUTES / WORLD GEN ===

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

- [ ] Un módulo que añada "deepscan", para scaneos de mucha más larga distancia.

- [ ] Debe haber algún límite de módulos (para estimular los builds). Y algunos deberán tener penalizaciones además de bonificaciones.

- [ ] Módulo que hace que los drones vuelvan automáticamente al dock (si es posible) cuando su batería cae a cierto nive.

- [ ] Módulo instalable que permita automatizar ciertas tareas en tránsito (aunque el PJ esté hibernando). Por ejemplo, llevar a cabo un scan cada x tiempo (configurable por el jugador), y dar la opcion de deshibernar en caso de que se detecte algo nuevo.


=== WIN/LOST CONDITIONS AND LOOPS ===



=== OTROS / SIN CATALOGAR ===

- [ ] Quiero que me generes un documento en el que se le explique a chatGPT exactamente qué debe hacerse y cómo (incluyendo ejemplos) para crear nuevos arcos.

- [ ] Modelo avanzado de salvage. La opción simplificada (la actual, siempre estará disponible). La avanzada (juego dungeoning) tendrá riesgos, y llevará más tiempo, pero también posibles recompensas mayores. Este modelo avanzado de salvage requiere un nuevo comando "drone survey" entre otrso muchos. Desarrollar una v0.

- [ ] Diseñar sistema "security". Por ahora, este sistema servirá para detectar intrusos en la nave (biológicos o no biológicos)

- [ ] HAcer dock tiene que tener una pequeña posibilidad de que "se meta algo" en tu nave al dockear, u otros eventos.

- [!] Se tiene que poder "añadir jobs a la cola". Es decir, añadir comandos a ejecutarse cuando se acaben las tareas actualmente en cola.Poder indicarle varios comandos en cadena, que cada cual se ejecute sólo cuando haya acabado el anterior.

- [ ] Que sentido tiene que "contacts" dependa de sensors? Qué operaciones/comandos dependen actualmente de "sensors"?

- [ ] A veces en textual al darle a TAB no se autocompleta (ni listan las opciones) sino que se cambia el foco de la ventana. Esto sólo sucede a veces.

- [ ] Pegarle a chatGPT:
  - debug lore después de 1–2 uplinks
  - un ejemplo del archivo entregado por captured_signal o ship_os_mail
  Para calibrar probabilidades (para que no “llueva lore” y siga siendo calmado).

- [ ] Enterarse de cuales son las consecuencias de no atender una alerta crítica u otra (pues ahora mismo no lo tengo muy claro).

- [-] Hay que mejorar la definición de "atasco" urgenemente. Pasar a una v1. No se trata de que se generen por arte de magia destinos. Hace falta comprobar detenidamente si el jugador tiene algún modo (aunque él no lo sepa) de lograr una localización (a través de uplink o scan o salvage data u otro).

- [ ] Hay que modificar el comando "map". No es muy intuitivo. Podría ser algo como "ship sectors" o "map ship".

- [?] Al  hacer 'route <node_id>' a un node_id para el que ya conoces ruta,  no se debería iniciar el job. Debería salir un mensaje informando de que ya se conoce ruta a ese objetivo. Por otra parte, debería de haber un comando para cancelar jobs en curso.

- [ ] Al iniciar la hibernación, debería de salir un mensaje (localizado) diciendo algo así como "Iniciando secuencia de hibernación", y una serie de mensajes (meramente narrativos) diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la criogenización, y una cuenta atrás de 10 segundos. Después, debe limpiarse la pantalla de logs, esperar 3 segundos e imprimirse una serie de mensajes diegéticos técnicos (localizados) sobre las operaciones que se están llevando a cabo para la descriogenización, junto con un mensaje (que se repetirá siempre), advirtiendo de que hay un problema crítico y no es posible descriogenizar completamente al sujeto del sarcófago (es decir, al Personaje Jugador). El sarcófago del PJ debe tener un id, por cierto. 

- [ ] Necesitamos una merjor organización del help.

- [ ] Hay muchos mensajes (o partes de mensajes) que aparecen en español cuando el idioma de configuración es el inglés, y al revés, mensajes o partes de mensajes en inglés cuando deberían estar en español. Un ejemplo: estando la configuración en inglés, me ha salido este  mensaje: "ParseError: Subcomando power desconocido. Usa: power status | power plan cruise|normal | power shed/off <system_id> | power on <system_id>"

- [ ] se puede usar el comando "scan" estando el servicio "datad" offline?

- [ ] Ahora mismo los manuals se han generado con un tono "diegético". Me gustaría ver cómo sería la versión más "técnica", pues chatgpt y codex me la han propuesto varias veces pero siempre la he rechazado sin llegar a ver cómo sería.

- [x] El comando "travel" hay que cambiarlo quizá por "navigate" (o algo primero como "trazar ruta" y después "navigate").

- [-] Ahora mismo si queremos viajar a "S+000_-001_-001:02: Relay-97 (relay) dist=1.30ly" hace falta introducir "travel S+000_-001_-001:0". Me gustaría que también se pudiera introducit "travel Realy-97" simplemente, y que el autocompletado funcionara. Y por cierto: ¿qué quiere decir "000_-001_-001:02"? ¿Son unas coordenadas? Si es así, creo que estaría bien indicar de algún modo que esa numeración son unas coordenadas. 

- [ ] También creo que tendría que aparecer en primer lugar el nombre de la hubicación (si la tiene), por ejemplo Relay-97 (relay) dist=1.30ly coord=S+000_-001_-001:02""


- [ ] dose es la dosis acumulada de radiación que ha recibido el dron (en rad). Se incrementa cada tick en función de la radiación ambiental (state.ship.radiation_env_rad_per_s) y el shield_factor del dron:
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

