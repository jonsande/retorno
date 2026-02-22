SPOILERS!

Solución al puzzle/tutorial inicial:

drone deploy! D1 PWR-A2

Si falla...
    drone reboot D1   (tantas veces como haga falta)
    drone deploy! D1 PWR-A2

drone repair D1 power_core
drone repair D1 energy_distribution
drone recall D1
boot sensors
scan
dock ECHO_7
---
drone deploy D1 ECHO_7
drone salvage modules D1
drone salvage scrap D1 30
drone salvage modules D1
cargo audit
drone recall
power plan audit
travel DERELICT_A3
hibernate until_arrival

DEBUG

Instalar la UI de Textual:
pip install -e .[ui]

Arrancar con UI Textual:
python -m retorno.ui_textual.app

Saltar prólogo:
Iniciar con RETORNO_SCENARIO=sandbox python -m retorno.cli.repl
Dentro del juego, se puede cambiar de escenario con:
debug scenario prologue
debug scenario sandbox
debug scenario dev



- [x] Operaciones de salvage y de repair deberían estar dentro del comando drone.
- [x] La cantidad de scrap que se ordena recuperar con 'salvage' tiene que afectar al tiempo
que se tarda en llevar a cabo la tarea.
- [x] Establecer límite de scrap que se puede obtener de un derelict u objeto dockable.
- [x] debería haber un límite de scrap y un máximo de módules encontrables (y que todo esto sea configurable en el json).
- [x] Obtener scrap debería de hacerse con un dron (específico para las tareas de salvage),
sin tener el cual (o sin estar operativo y desplegado en el nodo adecuado) no debe ser posible
obtener scrap. 
- [x] Ahora mismo tenemos algo llamado "inventario". Estoy hay que modificarlo. El inventario debería ser un sector de la nave del PJ. Muchas naves (la del PJ incluida) tienen que tener un sector de carga o almacén, es decir, una bodega. Esa bodega junto con su id debe aparecer al ejecutar el comando sectors. Por lo demás, por ahora el funcionamiento de ese "inventario" será igual que actualmente. 
- [x] Otra cosa: el comando "inventory" debe conservarse, pero quiero modificar algo. Si se añade al inventario scrap nuevo o un módulo o lo que sea, no se verá reflejado en la información correspondiente del status ni en la información que genera el comando "inventory" hasta
que no se ejecute el commando "inventory update". No obstante, en la información que imprime "status" y en la información que imprime "inventory" debe aparecer de algún modo la indicación de que hay cambios en bodega y que es necesario inventariar para actualizar la información. Ahora bien, la operación "inventory update" quiero ser un "job", un trabajo, con su  orrespondiente ETA. La idea es que al introducir ese comando se ejecute un trabajo de actualización del inventario o inventariado de lo que hay en la bodega, y que eso tarde un rato.

- [!] Al hibernar para viajar el "time" debería reflejar los años que han pasado desde que el PJ se despertó por primera vez. Necesitamos un reloj mejor. No vale sólo indicar segundos, pues el número es demasiado grando. Necesitamos un reloj que indique años luz, días, horas, minutos, segundos (o algo así; díme tú qué opinas).

- [ ] El comando "travel" hay que cambiarlo quizá por "navigate" (o algo primero como "trazar ruta" y después "navigate").

- [ ] Diseñar y desarrollar el sistema de generación del "universo/mundo", es decir, los distintos plots (después habrá que diseñar cómo el jugador obtiene las id's de nuevas localizaciones a las que poder viajar, pues no quiero que tenga siempre disponibles todos los destinos, y además quiero que los destinos se vayan generando proceduralmente). Me gustaría que el universo estuviera "organizado" o dividido. Ayúdame tú a esa organización, pero, por lo pronto, se me ocurre que podría ser algo como lo siguiente (pero hazme sugerencias o corrígeme si algo no es muy realista): el universo accesible al jugador será una galaxia de forma de espiral: la galaxia estará por lo pronto dividida en tres regiones: halo (zona más externa), el disco, y bulbo (zona central de la galaxia, donde la densidad de estrallas es mayor, y en cuyo centro se encuentra en agujero negro supermasivo Sagitario A*). Esas partes no serán plots; pero se me ocurre que ciertas localizacione o plots sólo puedan generarse en una región u otra, y que en cada una de las regiones apliquen ciertas condiciones (por ejemplo, que en los sectores pertenecientes al bulbo haya más radiación, o que )

- [ ] Diseñar el sistema de encontrar nuevos destinos. A nivel de sistema solar, tiene que ser posible detectar vía escáneres o algo así; a nivel de galaxia, quizá sólo a partir de información que se obtenga (cartas de navegación). Más allá de galaxia, no se sabe. El comando contacts/scan debe tener un alcance pequeño relativamente.

- [ ] Cómo se desconectan sistemas ahora mismo? Cómo se reduce carga de energía?

- [ ] Se debería poder mover un dron desplegado a otro plot sin necesidad de llevarlo a dock antes y desplegar de nuevo.

- [ ] Entiendo que el drone_bay se tiene que poder desconectar, para ahorrar energía.

- [ ] Quiero que al arrancar el juego por primera vez se imprima un mensaje "técnico" diegético que dé a entender de un modo u otro que ha habido un error y que se está ejecutando una instrucción de emergencia de descriogenización del sarcófago; que no se ha podido completar satisfactoriamente la descriogenización de la persona que hay dentro (el personaje jugador) del <id_sarcófago> por un problema indeterminado en el sistema; que se procede a intentar poner al huesped en estado consciente para que pueda llevar a cabo operaciones a través de la terminal conectada a su cerebro. También se indicará que el reloj/calendario interno de la nave ha sufrido un fallo indeterminado o algo así y que todo ha sido puesto a 0 (buscar la manera técnica diegética de decir esto). Este mensaje se imprimirá al iniciar el juego, pero quedará también como mail, de forma que se podrá volver a leer, en su versión española si se cambia la configuración de idioma. También quiero que se generen otros 5 mails con un texto muy similar, pero refiriendo cada uno de ellos a un sarcófago diferente, e indicando que ha fallado la descriogenización, y que no se detectan constantes vitales en el huesped (los 5 mails serán iguales, sólo cambiará <id_sarcófago>, de modo que al leerlos se pueda deducir que todos los compañeros del Personaje Jugador han muerto). Antes de construir la instrucción para codex, constrúyeme una versión del mensaje, para que lo pulamos.

- [ ] Algunos world_node, como las naves, las estaciones y los derelics tienen que tener plots ship_sector. O station_sector. Los planetas también tendrán que tener sectores (cuando hagamos planetas y drones capaces de desplegarse en ellos),

- [ ] Implementar guardar/cargar juego (savegames).

- [x] hay que crear manuales para /manuals/systems/power_core , security, life_support y los sistemas que faltan.

- [ ] La cuestión de implementar Textual.

- [x] Las tareas de un mismo dron deberían ir en cola. Ahora mismo las hace simultáneamente. Si le mandas más de una antes de que acabe la anterior.

- [x] Los drones deben perder batería al trabajar. Deben recargarse al atracar (dock). 

- [ ] Su batería debe también poder deteriorarse (por radiación u otros daños).

- [x] Un comando que liste los trabajos (jobs) en proceso o en cola.

- [ ] Aclarar cómo se crean nuevas naves, estaciones, etc. Ahora mismo hay un json pero parece que se está haciendo desde bootstrap.

- [ ] Ahora mismo tu status muestra P_load=4.20kW estando docked; eso sugiere que el docking 
añade consumo o activa algo. Está bien, pero ojo con el prólogo: podrías querer que dock 
reduzca carga (porque apagas motores) o que cambie perfil. No lo toques ahora; solo para 
tenerlo en mente.

- [ ] repair debería consumir algo. Como mínimo scrap. (La nave inicial debe por tanto empezar con una cantidad de scrap).

- [ ] boot sensord no está devolviendo ningún mensaje, creo.

- [ ] [Esto quedó pendiente de hacer] Si quieres, también podemos añadir un mail automático al primer módulo encontrado (lore + “esto se instala con install <id>”), pero lo dejo para después de que el loop funcione.


=========== USER INTERFACE ===========
TEXTUAL

Alternar foco del panel:  alt+j/k
Scroll arriba/abajo en panel activo: k/j
Comandos textual: ctrl+p

- [x] cuando se arranca el juego, debería por defecto estar activo el panel en el que se introducen órdenes. Ahora mismo no está funcionando así.
- [x] Me gustaría darle a la interfaz Textual un aspecto mucho más parecido a como se vería con Curses. Quiero además que el color de fondo sea igual en todos los paneles. No quiero que se dibujen líneas de contorno en los paneles.
- [ ] El panel de JOBS y de ALERTS deben tener scroll ambos. Pero no quiero ninguna barra de scroll (ocupa demasiado espacio en pantalla); prefiero, si es posible, que cuando el texto no entra en la caja del panel aparezca un pequeño símbolo de flecha hacia abajo (o algo así) en la parte inferior derecha del panel, indicando así que hay más texto que no se está biendo y que está disponible la posibilidad de hacer scroll para verlo.
- [ ] El contenido de los paneles fijos de la interfaz Textual es el mismo que el que se imprime al introducir el comando correspondiente (por ejemplo, en el panel status se observa exactamente lo mismo que se imprime cuando se escribe "status"). Esto me gustaría modificarlo. Es decir: por razones de diseño y espacio, quiero que lo que se ve en cada uno de los paneles pueda ser diferente a lo que se imprime al introducir un comando. En el panel status, por ejemplo 


=========== Versión 2 ============

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

