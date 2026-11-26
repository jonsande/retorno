# NAV-BRAKE-01B3H-D2B1-R1 — Informe de corrección del primer playtest

## Estado inicial y evidencia

- Rama: `feature/nav-brake`; HEAD inicial: `7f9f2fe7832d2773be7f40941218b4acc76c75d4`.
- Disponibles `PT001-02-blocked.dat`, `PT001-02-blocked_002.dat`,
  `PT001-02-second-block.dat` y el perfil
  `~/.retorno/users/playtest-d2b1/savegame.dat`. Las partidas originales no
  se han escrito. Todas las reproducciones cargaron copias en memoria y el
  guardado de continuación se escribió en `/tmp/nav_r1_continued.dat`.
  El perfil activo y la segunda copia tienen el mismo SHA-256:
  `ccdbb1c54f1ca0bcc1263f608de515a3c4c7faa755ef5a2247c4f5401785b8a6`.
- Ya había una modificación ajena en `TODO.md` y artefactos sin rastrear de
  D2B1 (`INFORME.md`, `MANIFEST.sha256`, `RECORRIDO-D2B1.txt`, `changes.diff`).
  Se conservaron; el ZIP R1 contiene los cambios de esta intervención.

## Reproducción y causas raíz

**PT001-01.** Un segundo de tránsito de la segunda partida consumía una
mediana de **0,304 s** de procesamiento con el HEAD inicial y el lock
permanecía adquirido **0,304 s**. `next_physical_step()` hacía una copia
profunda y `Engine.tick()` encadenaba otras tres en el recorrido nominal.
Las cuatro copias ocupaban **0,203 s**; la selección de fronteras, **0,010 s**.
El tick ordinario de control costaba **0,068 s**. El perfil estándar `cProfile`
identificó las copias como coste principal y la exploración de radio como
coste secundario. No se encontró evidencia de que el sonido fuese la causa.
Además, el bucle dormía un segundo *antes* de procesar cada tick: la cadencia
real medida fue **1,380 s** entre inicios. Su `sleep` tampoco atendía la orden
de parada hasta despertar y podía iniciar un tick más después de `stop()`.

**PT001-02A.** Ambas copias reproducían
`Physical segment interval has an unresolved causal boundary` antes de la
corrección. En `PT001-02-second-block.dat`, el tiempo galáctico era
`609444.539 s`; se pidió un chunk de `604800 s`. Por redondeo de la resta
de relojes el paso coordinado fue `604799.9999999999 s`. El coordinador eligió
`1214244.5389999999 s` y solo la causa `requested_horizon`, sin `deferred` ni
ninguna causa anterior. El integrador obtuvo `1214244.539 s`: diferencia de
**una ULP** (`2.3283064365386963e-10 s`). La comparación estricta
`selected.at_galactic_s < end.galactic_s` lo rechazaba. La previsión y la
ejecución de tiempo cero dieron el mismo horizonte, calidad eléctrica `1.0`,
batería `5.0 kWh`, ningún trabajo activo ni eventos preliminares. La
recepción de radio se reintenta adicionalmente en la ejecución, pero no
produjo ningún evento durante la hibernación de esta copia. La batería llena,
la radio y los chunks de siete días no fueron la causa.

En `PT001-02-blocked.dat`, `JOB35` era un despliegue en cola iniciado después
del primer bloqueo: al prever, se activó y fijó una frontera real a **13 s**.
Se resolvió una vez; el rechazo posterior fue el mismo redondeo del horizonte
de siete días. El trabajo no explica la hibernación original. La diferencia
entre despertar a los siete días y a un segundo corresponde al estado desde
el que se inició cada solicitud, no a un límite fijo de tamaño del chunk.

**PT001-02B.** `_execute_hibernate()` restauraba el avance con
`was_auto and not woke_early`; cualquier despertar anticipado dejaba el bucle
apagado, aunque el acontecimiento fuese legítimo y la nave pudiera seguir.
Guardar y cargar iniciaba otro bucle, por eso recuperaba los relojes sin
arreglar el rechazo de hibernación.

## Correcciones y garantías

- `Engine.tick()` conserva una copia transaccional del estado y el pronóstico
  conserva su copia de solo lectura. Los tramos nominales internos trabajan
  sobre la transacción ya provisional; las llamadas directas a los métodos
  internos aún crean su propia transacción. Se mantienen la identidad de los
  propietarios principales, el rollback, los eventos, el RNG y el pago único
  de combustible.
- La validación del extremo acepta únicamente diferencias de hasta **cuatro
  ULP**, la tolerancia para coincidencias que ya emplea
  `select_next_boundary()`. El integrador sigue definiendo posición y relojes.
  Una causa realmente anterior continúa rechazándose o cortándose por el
  coordinador; la prueba de un trabajo a mitad del intervalo lo verifica.
- El bucle automático usa plazos monotónicos e interrumpibles. Si se excede
  un período, salta los plazos vencidos y ejecuta un solo tick por iteración:
  no acumula ráfagas ni cambia los segundos de juego por tick.
- Un despertar normal o anticipado por evento legítimo restablece la política
  de avance que existía antes de dormir, salvo estado terminal. Una pausa
  deliberada permanece pausada. Una frontera técnica aún no resuelta mantiene
  el avance automático detenido para evitar un bucle de errores; el aviso
  localizado EN/ES lo dice expresamente. Un trabajo compatible progresa tras
  un despertar legítimo.

Los subsistemas normales de desgaste, electricidad, drones, narrativa y radio
siguen activos. No se modificaron balance, combustible ni parámetros físicos.

## Medición comparable

Cinco repeticiones por caso, mediana de reloj monotónico, cargando de nuevo
`PT001-02-second-block.dat` para cada muestra. El código base se extrajo de
HEAD a `/tmp/nav_r1_baseline`; se usaron el mismo intérprete, datos y script
[`nav_r1_benchmark.py`](../../tests/nav_r1_benchmark.py). Resultados brutos:
[`MEDICIONES-R1.json`](../../MEDICIONES-R1.json). La cadencia se midió con
[`nav_r1_cadence.py`](../../tests/nav_r1_cadence.py) y cinco ticks automáticos.

| Magnitud | Antes | Después |
| --- | ---: | ---: |
| Tick ordinario en reposo | 0,068 s | 0,070 s |
| `next_physical_step(1 s)` | 0,055 s | 0,058 s |
| `Engine.tick(1 s)` físico | 0,241 s | 0,148 s |
| Avance público físico de 1 s | 0,304 s | 0,208 s |
| Lock adquirido en ese avance | 0,304 s | 0,208 s |
| Copias profundas / coste total | 4 / 0,203 s | 2 / 0,110 s |
| Selección de fronteras total | 0,010 s | 0,008 s |
| Mediana entre ticks automáticos | 1,380 s | 1,000 s |

El avance físico público mejora aproximadamente un **32 %**. La cadencia
automática vuelve al período programado de un segundo en este equipo. La
ocupación del lock de unos 0,208 s aún puede causar una breve espera de UI;
no se promete tiempo real estricto bajo carga de CPU superior.

## Continuación de la partida real

En una copia de `PT001-02-second-block.dat`, el mismo manejador de
`hibernate until_arrival` avanzó **26,502413447782804 años** de juego y
registró una única llegada al identificador físico de destino de esa semilla
(alias público de la sesión: `P-1.1.0.0`). El estado inicial fue tiempo
`609444.539 s`, beta `0.002019859901703708`, distancia recorrida
`183339158801.09335 m` y `10.40581506308498` cápsulas. El final fue tiempo
`836389555.0282785 s`, tiempo propio `753898345.6323009 s`, tránsito
físico terminado y las mismas `10.40581506308498` cápsulas. Hubo dos cambios
de estado de sistemas y una llegada; no una emergencia propulsiva. El
resultado se guardó y cargó correctamente desde `/tmp/nav_r1_continued.dat`.
No se alteraron salud, combustible, drones, universo, desgaste ni relojes.
La política del bucle al despertar fue `[False, True]`.

La primera copia también supera una semana: `JOB35` termina una vez y aparecen
avisos y desactivación de un dron durante el intervalo. Son efectos del
despliegue presente en esa copia, no bloqueos técnicos ni evidencia de que el
primer fallo fuese causado por el dron.

Desde dos cargas equivalentes de la segunda copia, diez ticks de un segundo
y un intervalo de diez segundos terminaron con los mismos tiempo galáctico
(`609454.539 s`), tiempo propio (`609454.1272231016 s`), distancia
(`183345214238.74057 m`), beta (`0.0020198932579090917`), combustible y
eventos. `clock.last_dt` difiere por diseño: 1 s frente a 10 s.

Para continuar el perfil original con la versión corregida, cerrar la sesión
antigua mediante `exit` si aún está abierta y ejecutar desde el repositorio:

```bash
RETORNO_SCENARIO=PROLOGUE PYTHONPATH=src \
  ../retorno_venv/bin/python -m retorno.ui_textual.app \
  --user playtest-d2b1
```

Cargar la partida existente; **no** usar `--new-game`. Ya en la sesión
corregida, usar `hibernate until_arrival` y confirmar. Un despertar legítimo
deja el avance automático activo si lo estaba antes. El reinicio único aplica
el código nuevo al proceso antiguo; una vez cargado, no hace falta reiniciar
para recuperar el tiempo después de un despertar legítimo.

## Validación, archivos y límites

Regresiones nuevas: `tests/test_nav_playtest_r1.py` cubre el redondeo, una
frontera real, rollback, copias, políticas de despertar, progreso de trabajos
y cadencia con sobrecarga. Se ajustó la firma del mock en
`tests/test_nav_engine_nominal.py` a la nueva llamada privada.

Archivos de producto: `src/retorno/core/engine.py`,
`src/retorno/runtime/loop.py`, `src/retorno/cli/repl.py`. Documentación EN/ES:
`docs/systems/nav-physics.md`, `docs/systems/nav-physics.es.md` y este
informe con su contraparte inglesa. Herramientas de reproducción:
`tests/nav_r1_benchmark.py`, `tests/nav_r1_cadence.py`, `MEDICIONES-R1.json`.

Pruebas finales: batería dirigida D2B1/D2A/D1/coordinador/recuperación,
**116 passed en 134,04 s**; regresiones adicionales de interrupción,
inercia, reparación y seguridad, **105 passed en 112,22 s**; fichero R1
completo tras añadir los casos de política temporal, **11 passed en 11,15 s**.
`tests/textual_nav_d2b1_smoke.py` terminó con
`TEXTUAL NAV D2B1 SMOKE PASSED`. `py_compile` y `git diff --check` pasaron.
No cambia la sintaxis de comandos ni el contenido diegético: no se alteraron
manuales ni `help`; el nuevo aviso al jugador está completo en EN/ES.

Límites: la optimización de transacciones se centra en el tránsito nominal;
las rutas excepcionales de inercia y recuperación conservan copias anidadas.
El coste secundario de radio sigue presente. Una frontera técnica genuina aún
no soportada detiene el tiempo con aviso; D2B2 y maniobras nuevas siguen fuera
de alcance. No se añade compatibilidad general con partidas antiguas.

Estado final previsto de Git: rama `feature/nav-brake`, HEAD inicial sin
cambios, seis archivos R1 rastreados modificados y seis nuevos; persisten
`TODO.md` y los cuatro artefactos previos de D2B1 sin incluirlos en el ZIP R1.
No se ha realizado commit ni push. El ZIP de revisión se verifica al final.
