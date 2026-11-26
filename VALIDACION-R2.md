# NAV-BRAKE-01B3H-D2B1-R2-V — validación definitiva

Fecha: 26 de noviembre de 2026. Referencia de situación: `ESTADO-R2.md`.

## Estado de partida

- Rama: `feature/nav-brake` (seguimiento de `origin/feature/nav-brake`).
- HEAD: `cc5e58412c3606554c9dc19bd638c232e231ee43`.
- Árbol con los 20 archivos rastreados modificados y los archivos sin rastrear detallados en `ESTADO-R2.md`; `TODO.md` es una modificación ajena. No se cambió de rama ni se hizo commit o push.
- Entorno canónico según `AGENTS.md`: `/home/jon/prog/retorno_case/retorno_venv/bin/python`, con `PYTHONPATH=src:.` para la suite. Se empleó el mismo alcance general `pytest -q tests` de las pasadas anteriores.

## Suite general: una única ejecución

Directorio: `/home/jon/prog/retorno_case/retorno`.

```bash
/usr/bin/time -p -o /tmp/nav_r2_v_time.txt env PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python -m pytest -q tests > /tmp/nav_r2_v_suite.log 2>&1
```

**Resultado:** código de salida `0`; `642 passed, 169 subtests passed in 349.71s (0:05:49)`. Medición externa: `real 350.38`, `user 323.65`, `sys 15.12` segundos. La salida íntegra quedó en `/tmp/nav_r2_v_suite.log` y la medición externa en `/tmp/nav_r2_v_time.txt`. No hubo líneas de fallo, traceback ni avisos en el resumen de pytest. La suite llegó a `[100%]` y terminó normalmente. No se inició una segunda ejecución.

## Comprobaciones condicionadas al resultado favorable

Compilación de los 19 archivos Python afectados, incluidos los nuevos sin rastrear:

```bash
PYTHONPYCACHEPREFIX=/tmp/nav_r2_v_pycache /usr/bin/time -p -o /tmp/nav_r2_v_compile_time.txt /home/jon/prog/retorno_case/retorno_venv/bin/python -m py_compile \
  src/retorno/cli/repl.py src/retorno/core/engine.py src/retorno/core/nav_coordinator.py \
  src/retorno/core/nav_physics.py src/retorno/core/nav_radiation.py src/retorno/runtime/loop.py \
  src/retorno/ui_textual/app.py src/retorno/worldgen/generator.py src/retorno/worldgen/manifest.py \
  tests/test_nav_playtest_r1.py tests/test_nav_public_causal.py tests/test_nav_public_physical.py \
  tests/test_nav_segment_coordinator.py tests/test_wear_proper_time.py tests/textual_nav_d2b1_smoke.py \
  tests/nav_r2_benchmark.py tests/test_nav_playtest_r2.py tests/textual_nav_r2_close_smoke.py \
  tests/textual_nav_r2_responsiveness.py
```

**Resultado:** código `0`, sin salida ni avisos; `real 0.53`, `user 0.48`, `sys 0.03` segundos. Los bytecode se dirigieron a `/tmp/nav_r2_v_pycache`.

```bash
git diff --check
```

**Resultado:** código `0`, sin salida ni avisos. Esta orden comprueba los cambios rastreados de Git; los archivos sin rastrear quedan fuera de su alcance.

## Alcance y conservación

La validación acredita la suite general y la sintaxis de los Python afectados **para el código existente durante esta ejecución**. No se modificaron código ni pruebas; el estado de Git tras las comprobaciones conservó los mismos 20 rastreados modificados y los mismos archivos sin rastrear previos a este informe. No se ejecutaron benchmarks ni smokes adicionales, no se generó el ZIP y no se tocaron las partidas originales ni el perfil del jugador. La entrega y revisión externa de R2 siguen siendo trabajos separados.
