# PT001-01/09-A — diagnóstico del lag residual y la cadencia de los relojes

Fecha: 2026-11-28. Código: `a7b0ad5977b1474ac2f48e3599bdf3c878a7890b`.
Es un diagnóstico y una propuesta; no cambia los relojes ni la navegación.

## Reproducción y medición

El Python del proyecto ejecutó una sonda breve con estados privados mediante
`GameLoop`, el perfilador existente `MeasuredLock` y una sesión Textual sin
terminal con `RetornoTextualApp.run_test()`. La sonda quedó fuera del repositorio
en `/tmp/pt001_01_09_diag.py`; su salida bruta está en
`/tmp/pt001_01_09_diag.out`. Los estados sintéticos utilizaron
`tests/test_nav_public_physical.py::public_game(.11)`, velocidad 0,1 c y ruta
nominal de tres segmentos. Las muestras de crucero y frenado se prepararon
avanzando copias privadas hasta 100 s dentro de cada segmento (0,15/0,17 s
reales). Cada muestra del motor empleó tres copias distintas y un avance de
1 s. Cada muestra automática midió cuatro ticks de periodo 1 s y consultó el
lock sin bloqueo aproximadamente cada 20 ms. Textual midió cada fase sintética
unos 2,9 s, con refrescos normales cada 250 ms, audio desactivado y entrada
`status`. No hubo hibernación larga. La cifra de entrada incluye la gestión
del controlador de pruebas: aproxima la latencia de respuesta, no mide una
pulsación física de teclado.

Las partidas reales PT001-04 y PT001-05 solo se cargaron en memoria para las
mismas sondas breves. Ambas empiezan en crucero nominal a beta 0,5. Las sumas
SHA-256 de los originales siguen siendo, respectivamente,
`b5cca22d6cdb956d84d608af2fd3c45b9d6792b035336862fcdc49510458f8c4`
y `639f354b43ee81f4dbed378cb4615fe22111b8a61b9ba5c3c64b0ffa3896103a`.
La aplicación sin terminal solo usó partidas temporales.

| Estado | Mediana de avance independiente de 1 s | Tick automático mediana / máximo | Intervalos entre inicios | Avance galáctico / propio | Muestra real | Consultas con lock ocupado |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reposo sintético | 0,242 s | 0,004 / 0,279 s | 1,000 ± 0,0001 s | 4,000 / 4,000 s | 4,016 s | 11/196 |
| Aceleración sintética | 0,124 s | 0,032 / 0,215 s | 0,999–1,000 s | 4,000 / 4,000 s | 4,056 s | 11/197 |
| Crucero sintético | 0,0066 s | 0,029 / 0,045 s | 1,000 ± 0,0001 s | 4,000 / 3,980 s | 4,041 s | 4/198 |
| Frenado sintético | 0,015 s | 0,038 / 0,045 s | 1,000 ± 0,0001 s | 4,000 / 3,980 s | 4,059 s | 5/199 |
| PT001-04 en crucero | 0,047 s | 0,088 / 0,143 s | 1,000 ± 0,0002 s | 4,000 / 3,464 s | 4,094 s | 15/198 |
| PT001-05 en crucero | 0,241 s | 0,136 / 0,360 s | 1,000 ± 0,0002 s | 4,000 / 3,464 s | 4,110 s | 27/196 |

El primer tick automático puede costar bastante más que los siguientes del
mismo estado; las medianas con copias independientes incluyen deliberadamente
ese estado inicial frío. Por tanto, las muestras describen un coste local, no
garantizan una tasa sostenida. El lock estuvo ocupado 0,290/0,291/0,122/0,139 s
en las cuatro muestras sintéticas, en el orden de la tabla, y 0,405/0,738 s en
PT001-04/05. La espera acumulada para adquirirlo fue 0,004–0,006 s por
muestra. Las consultas ocupadas indican cuántas veces una lectura visual sin
bloqueo omitiría un fotograma. En las seis muestras no hubo error automático ni
plazo incumplido.

| Estado Textual sin terminal | Refrescos / mediana / máximo del intervalo | Cambios de cabecera | Lecturas con lock ocupado | Respuesta aproximada de `status` |
| --- | ---: | ---: | ---: | ---: |
| Reposo | 12 / 0,251 / 0,255 s | 2 | 0 | 0,135 s |
| Aceleración | 12 / 0,250 / 0,259 s | 2 | 2 | 0,195 s |
| Crucero | 12 / 0,251 / 0,255 s | 2 | 2 | 0,133 s |
| Frenado | 12 / 0,250 / 0,260 s | 2 | 2 | 0,186 s |
| PT001-04 en crucero | 12 / 0,250 / 0,258 s | 2 | 2 | 0,190 s |
| PT001-05 en crucero | 12 / 0,251 / 0,255 s | 2 | 2 | 0,139 s |

Cada ventana Textual contiene dos ticks completados; sus aproximadamente 2,9 s
reales incluyen fracciones del periodo del planificador al principio y al final.
Dividir ingenuamente `2 s de juego / 2,9 s reales` sugeriría erróneamente
pérdida de tiempo. La prueba de cadencia son los intervalos entre inicios de
tick, no esa razón parcial. El temporizador de paneles se mantuvo regular en
estas ejecuciones sin terminal. No se midieron el renderizado en terminal real
ni la latencia del audio.

## Hallazgos y límites

**Defecto confirmado del planificador bajo sobrecarga.** `GameLoop._run()`
añade exactamente `tick_s` de simulación por iteración completada y después
desplaza un plazo vencido al siguiente hueco futuro sin contabilizar los huecos
saltados. Un control aislado añadió 1,25 s de trabajo artificial por iteración
en reposo. Cuatro ticks automáticos tardaron entonces **8,259 s reales**,
avanzaron ambos relojes solo **4,000 s** y comenzaron cada **2,000 s**: se
omitieron al menos tres huecos entre los inicios observados. Esto demuestra que
el tiempo simulado puede retrasarse acumulativamente respecto al real cuando
se incumplen plazos. Las seis muestras ordinarias breves **no** sufrieron esa
sobrecarga; sigue sin verificarse que causara el episodio concreto del playtest.

**Coste confirmado del motor y del lock, sin ralentización universal de
crucero.** El primer segundo de PT001-05 cuesta más que PT001-04 y el crucero
sintético tranquilo. Una ejecución de 1 s con `cProfile` tardó 0,469 s bajo
instrumentación, efectuó dos ticks causales y atribuyó 0,368 s acumulados a
descubrir oportunidades de radio (llamadas anidadas solapadas). Concuerda con
el perfil anterior de R2. Una ocupación larga del lock puede impedir un
refresco o retrasar un comando que lo adquiere. En estas mediciones no superó
el presupuesto automático de un segundo. El temporizador Textual de 250 ms y
las lecturas sin bloqueo evitan que el bucle visual espere al motor solo para
dibujar un panel; no garantizan un valor nuevo del reloj en cada refresco.

**Cuantización visual confirmada.** La cabecera pública aplica `int(seconds)`
a los tres relojes. En crucero a beta 0,5, el tiempo propio gana unos 0,866 s
por tick galáctico; por ello sus segundos mostrados se repiten a veces. Con el
valor inicial de PT001-04, nueve lecturas consecutivas (la inicial y ocho ticks
ideales de un segundo) muestran segundos propios
`14, 15, 16, 17, 18, 18, 19, 20, 21`. Es tiempo propio físicamente correcto,
no pérdida de tiempo galáctico. Los segundos galácticos deberían cambiar una
vez por tick completado de un segundo; una pausa real mayor exige un tick
omitido, un bloqueo del motor o la interfaz, una pausa u otra causa. La sonda
breve sin terminal no reprodujo la irregularidad galáctica comunicada.

El renderizado del terminal, el audio, la planificación del sistema anfitrión
y otros estados posteriores de la partida siguen siendo hipótesis. Estas
muestras no permiten repartir su impacto ni demostrar rendimiento sostenido.

## Propuesta acotada para PT001-01/09-B

1. Añadir pruebas dirigidas del planificador con avance lento controlado,
   parada/reinicio, pausa debug y frontera causal. Registrar explícitamente el
   tiempo monotónico transcurrido y la deuda de simulación. No descartar
   silenciosamente tiempo vencido; procesar recuperación limitada con cesiones
   al bucle visual y definir el tratamiento de la deuda al pausar o cerrar.
   Conservar avances físicos atómicos y avisos de fallo existentes.
2. Ofrecer una pequeña sonda solo en debug o reutilizar los instrumentos de
   perfilado para comparar huecos programados, segundos simulados, ocupación
   del lock, lecturas visuales omitidas y latencia de entrada en una copia
   privada de la partida actual del jugador. No divulgar datos ocultos en UI
   normal.
3. Comparar la cadencia visual con los relojes continuos almacenados y decidir
   si hace falta ajustar la presentación. Mantener la dilatación del tiempo
   propio; tratar el temblor visual por separado de la deuda del planificador.

Este diagnóstico no cambió código productivo, Balance, reglas temporales,
partidas originales ni configuración global de pruebas. No se ejecutaron la
suite general ni benchmarks extensos.

## Implementación y validación dirigida de PT001-01/09-B

`GameLoop` acumula ahora tiempo monotónico únicamente mientras su hilo
automático está activo y descuenta el tiempo galáctico realmente confirmado
por cada avance. Una tanda de recuperación solicita como máximo dos avances
de un segundo, con una cesión de 50 ms entre solicitudes vencidas. Una pequeña
tolerancia evita un bucle por redondeo en la frontera del plazo. El hilo libera
el lock entre solicitudes; la cadencia normal sigue siendo de un segundo. Un
avance parcial positivo que retorna normalmente permanece como tiempo
pendiente hasta que transcurre más tiempo activo. Una frontera causal conserva
tiempo y eventos confirmados, pausa enseguida y emite el aviso existente.

La política del ciclo de vida es explícita: una pausa deliberada y `stop()`
esperan al hilo y descartan la deuda; `start()` inicia una época monotónica
nueva. Un avance manual externo detiene antes el hilo. La hibernación detiene
el tiempo automático antes de fijar su reloj inicial y solo lo reanuda según
la política de despertar existente, en una época nueva. Los errores técnicos
pausan y descartan deuda, pero conservan el estado confirmado. El cierre
espera al hilo antes de guardar, por lo que no hay escritura automática tras
el guardado. La deuda no se persiste ni se acumula en pausa, hibernación o
cierre.

La sonda versionada y de solo lectura está en
[`tests/nav_auto_cadence_probe.py`](../../tests/nav_auto_cadence_probe.py).
Con el mismo crucero sintético de cuatro ticks empleado en A, B midió
**4,000 s galácticos / 3,980 s propios en 4,033 s reales**; los inicios de
tick ocurrieron a 1,000, 2,001, 3,001 y 4,001 s. El lock estuvo ocupado
0,122 s, con 4/198 consultas ocupadas. Una ejecución Textual breve sin
terminal mantuvo una mediana de 250 ms entre refrescos, dos cambios de
cabecera y una respuesta aproximada de 0,146 s a `status`. En la copia
privada PT001-05, B midió **4,000 / 3,464 s en 4,120 s reales**, con inicios
cada segundo, 0,663 s de ocupación total del lock y 27/197 consultas ocupadas.
Son cifras nominales cercanas a las muestras de A de 4,041 s y 4,110 s reales;
la comparación es local y breve, no una garantía de rendimiento sostenido.

Con 1,25 s de trabajo artificial solo en el primer tick, una muestra de seis
ticks en reposo recuperó el atraso y alcanzó **6,000 s de juego en 6,017 s
reales**; el segundo tick comenzó a 2,733 s y después los inicios volvieron a
3, 4, 5 y 6 s. Con el mismo retraso sostenido en los cuatro ticks medidos,
B avanzó 4,000 s en 6,423 s reales; el tiempo pendiente creció hasta al menos
2,102 s y el hilo cedió entre ticks vencidos. La recuperación no puede superar
un motor persistentemente más lento. Una parada deliberada descarta esa deuda,
conforme a la política anterior; B no promete equivalencia en tiempo real bajo
sobrecarga sostenida ni reproducir tiempo transcurrido tras una pausa o cierre.

Las pruebas deterministas cubren cadencia nominal, sobrecarga puntual y
sostenida, avance real frente a solicitado, bloqueo causal parcial,
pausa/reinicio, avance manual, hibernación, serialización de hilos, guardado
tras parada/cierre y tiempo propio relativista. La primera selección de regresiones
relacionadas produjo **58 superadas, 2 fallidas** en 103,12 s: una prueba R1
aún exigía omitir plazos vencidos y su mock no avanzaba el reloj de juego. Se
actualizó esa expectativa histórica; sus dos casos y las pruebas nuevas de
entonces superaron **11 pruebas** en 4,27 s. Tras añadir comprobaciones de
pausa y guardado, el módulo del planificador superó **10 pruebas** en 4,13 s.
La selección dirigida final, incluidos cierre, errores R1/R2, capacidad de respuesta
Textual de PT001-08 e hibernación física, superó **30 pruebas en 34,63 s**.
No se ejecutaron la suite general ni benchmarks extensos.

No se modificaron motor, radio, reglas físicas, formato de los relojes, audio
ni Balance. El crucero irregular observado por el jugador en terminal real
sigue sin verificarse; la cuantización visual a segundos enteros y la
latencia dependiente del equipo quedan fuera de B.
