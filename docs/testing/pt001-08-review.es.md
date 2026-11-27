# PT001-08 — validación de la presentación de hibernación

Fecha: 2026-11-27. HEAD inicial: `887bda2f4e12da2040051f3cf176328b3be79b96`.
Se conservaron el cambio ajeno en `TODO.md`, los artefactos de revisión
anteriores, las partidas originales y el perfil del jugador. No se hizo commit
ni push.

Tras la cuenta atrás, Textual normal oscurece paneles, log, reloj y entrada
durante el procesamiento del worker y el oscurecimiento previo al despertar.
Permanecen el worker y el refresco no bloqueante de R2. La secuencia de
despertar precede a los acontecimientos registrados seleccionados y al resumen
de hibernación. Un fallo técnico del worker restaura la interfaz y muestra el
error sin ejecutar la secuencia de despertar. El modo debug usa el indicador
existente `debug_enabled` y el callback de progreso para mostrar tiempo real
simulado mediante la cola de Textual. CLI normal ya limpia la pantalla y
permanece en silencio durante el procesamiento; CLI debug muestra ahora el
mismo progreso localizado. No cambiaron los recursos de entrada y salida, el
audio, la física, las reglas de hibernación ni el avance temporal.

Validación con `/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_08.py tests/test_nav_r2_f.py tests/hibernate_sequence_assets_smoke.py tests/test_nav_playtest_r1.py -k 'pt001_08 or nav_r2_f or hibernate_sequence_assets or hibernation or wake'` → **18 superadas, 5 excluidas** en 19,76 s.
- `-m pytest -q tests/test_pt001_08.py` → **7 superadas** en 16,10 s tras añadir la comprobación de errores técnicos EN/ES.
- `tests/textual_nav_r2_close_smoke.py` → **superada**; el cierre esperó al worker y guardó su reloj final.
- `tests/textual_nav_r2_responsiveness.py` → **superada** con una copia privada en memoria de PT001-05. Registró 55 refrescos durante el oscurecimiento, cero mensajes de progreso normal, brecha p95 del bucle de 0,0665 s, llegada y reanudación automática del tiempo tras despertar. El procesamiento tardó 11,66 s; la narración y el oscurecimiento de salida conservaron sus ajustes. El script guardó solo en una ruta temporal.

Las pruebas sintéticas dirigidas cubren presentación normal/debug en Textual
y CLI, progreso real del callback, oscurecimiento mientras el worker avanza el
reloj, respuesta de la interfaz, orden del despertar y errores técnicos EN/ES
visibles. Las pruebas de cierre y de Textual representativo de R2 cubren la
persistencia al cerrar y la ruta narrativa completa. No se ejecutaron la suite
general ni benchmarks extensos.

El desarrollador comunicó por separado la validación general definitiva de
PT001-07: **677 pruebas y 169 subpruebas superadas en 362,72 s**. PT001-08 no
la repitió.

## PT001-08-F — despertar frente a fallo técnico

La revisión externa de PT001-08 fue favorable salvo por las excepciones de CLI
y los bloqueos causales devueltos como resultado. La clasificación compartida
conserva las secuencias de despertar ordinarias y de emergencia legítima; los
resultados `causal_boundary:` omiten la secuencia en ambas interfaces. CLI
captura excepciones de ejecución y mantiene su guardado ordinario. Ambos caminos
técnicos pausan el tiempo automático, restauran la presentación e informan del
tiempo realmente avanzado. No cambiaron el motor, la supervivencia, los
recursos narrativos ni las reglas de audio.

Validación dirigida con `/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_08.py` → **13 superadas** en 26,38 s. Cubre excepción y guardado en CLI, bloqueos causales devueltos en CLI y Textual, fallo y avance localizados, y despertares de emergencia conservados.
- `-m pytest -q tests/test_nav_playtest_r1.py tests/test_nav_r2_f.py tests/hibernate_sequence_assets_smoke.py -k 'hibernation or wake or no_progress_before_any_tick or real_pending_causal_boundary or hibernate_sequence_assets'` → **11 superadas, 6 excluidas** en 6,15 s.

Una primera ejecución dirigida falló en cuatro casos nuevos de CLI porque su
doble de audio devolvía `None` cuando el inicio espera un aviso de audio. Se
corrigió el doble; las dos ejecuciones anteriores son las definitivas. No se
ejecutaron la suite general ni benchmarks.

## PT001-08-F2 — texto del evento final registrado

`HIBERNATION_ENDED` sigue registrado cuando un bloqueo causal detiene la
hibernación. Su `end_reason` persistido distingue la detención técnica del
despertar en la presentación inmediata EN/ES y en la consulta posterior del
registro de eventos. Se conserva el texto ordinario y de emergencia legítima.
El comando dirigido
`/home/jon/prog/retorno_case/retorno_venv/bin/python -m pytest -q tests/test_pt001_08.py`
superó **15 pruebas en 27,80 s**, incluido un evento final real generado por
`_execute_hibernate()`, su consulta tras guardar y cargar, y ambos idiomas.
No se ejecutaron otras pruebas ni benchmarks.
