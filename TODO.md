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

- [ ] Quiero que al arrancar el juego por primera vez se imprima un mensaje "técnico" que dé a entender de un modo u otro que ha habido un error y que se está ejecutando una instrucción de emergencia de descriogenización de los sarcófagos del sector en el que están los sarcófagos de criogenización; que ha fallado la descriogenización excepto en el caso de un sarcófago (que tendrá que tener su correspondiente id o código identificativo técnico); que no se ha podido completar satisfactoriamente la descriogenización de la persona que hay dentro (el personaje jugador) por un problema indeterminado en el sistema; pero que la persona (esto es el PJ) está consciente y puede llevar a cabo operaciones a través de la terminal de algún modo conectada a su cabeza. Este mensaje se imprimirá al iniciar el juego, pero quedará también como mail, de forma que se podrá volver a leer, en su versión española si se cambia la configuración de idioma. Antes de construir la instrucción para codex, constrúyeme una versión del mensaje, para que lo pulamos.

- [ ] Implementar guardar/cargar juego (savegames).

- [ ] hay que crear manuales para /manuals/systems/power_core , security, life_support y los sistemas que faltan.

- [ ] La cuestión de implementar Textual.

- [!] Las tareas de un mismo dron deberían ir en cola. Ahora mismo las hace simultáneamente si
le mandas más de una antes de de acabe la anterior.
- [ ] Los drones deben perder batería al trabajar. Deben recargarse al atracar (dock). Su batería debe también poder deteriorarse (por radiación u otros daños).

- [ ] Un comando que liste los trabajos (jobs) en proceso o en cola.

- [ ] Ahora mismo tu status muestra P_load=4.20kW estando docked; eso sugiere que el docking 
añade consumo o activa algo. Está bien, pero ojo con el prólogo: podrías querer que dock 
reduzca carga (porque apagas motores) o que cambie perfil. No lo toques ahora; solo para 
tenerlo en mente.

- [ ] repair debería consumir algo. Como mínimo scrap. (La nave inicial debe por tanto empezar con una cantidad de scrap).

- [ ] boot sensord no está devolviendo ningún mensaje, creo.

- [ ] [Esto quedó pendiente de hacer] Si quieres, también podemos añadir un mail automático al primer módulo encontrado (lore + “esto se instala con install <id>”), pero lo dejo para después de que el loop funcione.

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