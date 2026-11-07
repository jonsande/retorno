# RETORNO — 4D-3e5c-P3

[English](prologue-chain-review.md). Base: `dc09628a1f1124a4122c4d4671362d4b7a96ba58`;
árbol inicialmente limpio. Implementación para revisión externa.

## Resultado y garantía

La extensión `historical-prologue-chain-v1` fija una cadena pública
ECHO_7 → P procedural → HARBOR_12 antes de explorar. Busca P entre nueve
cohortes iniciales y excluye fuentes protegidas/reservadas. Si no hay candidato,
añade un solo slot `derelict` al manifiesto. Con los anclajes instalados, toda
su caja de posiciones `[4,6) × [1,3) × [0.1,0.2)` permite ambos saltos positivos
y menores de 45 ly. Esta construcción cubre todas las semillas válidas; las
comprobaciones de semillas son regresiones, no la demostración.

ECHO_7 conserva la selección habitual del uplink salvo, como máximo, su último
destino, necesario para reservar P. P tiene un archivo B1 permanente, bilingüe,
guest e importable mediante salvamento y lectura ordinarios. No hay entrega de
ruta directa procedural desde ECHO_7, uso obligatorio de ARCHIVE_01, dependencia
de radio, ventana narrativa ni recuperación posterior.

Se preservan los sitios, posiciones, sorteos, hubs, aristas y ámbito ordinarios.
El slot adicional no modifica pools ponderados preexistentes ni declara equipo
radio. B2 conserva su proyección B1 ordinaria sin las dos reservas adicionales;
las rutas alternativas y los mecanismos authored/manuales mantienen sus reglas.
El recorrido anterior de semilla 1 mediante dos uplinks sigue disponible.

La preparación y el guardado/carga certifican la elección física, distancias,
canales efectivos, archivo recuperable, máximo de tres destinos, protecciones
y ausencia de dependencia circular. Se versiona la extensión, capturada en el
manifiesto y la huella informativa; B2 queda vinculado a esa huella. No se migran
guardados previos. Contrato y prueba constructiva detallados:
[Garantía histórica del prólogo](../systems/prologue-navigation.es.md).

## Archivos

- `src/retorno/worldgen/manifest.py`: reserva determinista y slot histórico.
- `src/retorno/worldgen/narrative.py`: preparación después de reservas narrativas.
- `src/retorno/worldgen/information.py`: registros, archivo y certificación.
- `src/retorno/worldgen/historical_radio.py`: aislamiento específico de la reserva.
- `tests/prologue_chain_smoke.py`: nueva validación focal.
- `tests/prologue_navigation_policy_smoke.py`: comparación P1 de la proyección
  ordinaria y fixture de catálogo incompatible conservando P1.
- `tests/structural_recovery_smoke.py`: la escena sintética descarta el contrato
  del prólogo cuando reemplaza sus anclajes; no cambia la recuperación productiva.
- Documentación EN/ES: nuevo contrato, este informe y referencias desde
  `world-generation`, `historical-information` e `historical-radio`.

No se modifica `generator.py`: su materializador e inventario existentes ya
consumen los sitios del manifiesto. No cambian datos, comandos, help ni manuales
diegéticos, navegación ordinaria, tiempos, supervivencia, modo dios o lore.

## Validación ejecutada

Intérprete: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.
Entorno: `PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`.

- `python -u tests/prologue_chain_smoke.py`: PASS, siete grupos focales.
- Tras ajustar el nombre del archivo y del respaldo, repetición de
  `structural()`, `fallback()` y `public_chain()`: PASS. Incluye emisión
  navegacional B2 forzada y conservación del pool ordinario en el respaldo.
- `git diff --check`: PASS. Sin barrido de semillas ni batería general.

Cobertura: 1/29/701, certificados negativos, status sin revelación de estado
oculto, FAST_SANDBOX, respaldo sin candidato admisible, inventario físico,
materialización idempotente, guardado/carga del respaldo y de datos recuperados
antes de leerlos, importación EN/ES sin duplicados y rechazo de catálogo
incompatible. Recorrido nuevo público completo en semilla 1 desde FAST_SANDBOX,
sin debug, teleportación ni edición de recursos/conocimiento: saltos de
5.167647 y 14.369025 ly, incluyendo atraque, dron, salvamento y lectura.
También se verificó el prólogo normal en 29 y la alternativa de dos uplinks en 1.

El ZIP incremental contiene los archivos modificados completos y `AUDIT/`
con evidencia JSON, logs, base e inventario SHA-256/tamaños. No contiene partidas,
entorno virtual ni archivos sin cambios. El inventario no se incluye a sí mismo.
Sin `git add`, commit ni push. Trabajo detenido para revisión.
