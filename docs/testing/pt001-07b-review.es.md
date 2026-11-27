# PT001-07B — registro de implementación y validación

Fecha: 2026-11-27. La propuesta PT001-07A aprobada externamente llegó en esta
intervención como texto del desarrollador y queda fijada en
[recarga de drones](../systems/drone-charging.es.md). No se cambiaron esquemas
de guardado, mantenimiento general ni diseño eléctrico de la nave.

Decisiones: `drone_charging.py` asigna potencia en orden de identificador y
comparte la decisión con el integrador y la previsión. La bahía conserva su
consumo fijo. La recarga variable conserva la proporcionalidad exacta de
`1/90 kWh` por unidad de batería, multiplica potencia y tasa por degradación,
y usa el umbral de SoC del 25 % para reserva adicional. La potencia parcial
aprovecha excedente real pequeño o capacidad de descarga restante, con tasa
proporcional; es la concreción de los límites conjuntos de 07A. Los cortes
eléctricos por llenado y SoC no repiten mantenimiento, trabajos ni narrativa.

Validación ejecutada desde la raíz del repositorio con
`/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_07b.py tests/test_electrical_proper_time.py tests/test_nav_electricity.py tests/test_nav_public_physical.py tests/test_nav_engine_wear_cut.py tests/test_nav_boundaries.py tests/drone_autorecall_reserve_smoke.py tests/drone_completion_context_smoke.py tests/drone_modular_v1_smoke.py tests/drone_recall_all_smoke.py tests/drone_recall_emergency_smoke.py` → **172 passed, 14 subtests passed** en 89,18 s.
- Ejecución directa de `tests/energy_policy_smoke.py`,
  `tests/drone_autorecall_reserve_smoke.py`,
  `tests/drone_completion_context_smoke.py`,
  `tests/drone_modular_v1_smoke.py`, `tests/drone_recall_all_smoke.py` y
  `tests/drone_recall_emergency_smoke.py` con el intérprete del proyecto →
  **todas superadas**; autorecall ejecutó 17 pruebas internas. Dos scripts
  conservaban llamadas directas al mantenimiento para verificar recarga; sus
  comprobaciones ahora llaman al integrador eléctrico propietario.
- `git diff --check` → sin errores.

Las pruebas nuevas cubren net positivo/negativo, SoC arriba/abajo/igual al
umbral, excedente parcial, cruce estable en ambos sentidos, límites de descarga,
degradación, reparto de varios drones, elegibilidad, llenado, eficiencias,
proporcionalidad, partición temporal, tránsito relativista y rollback al saltar
una frontera física pendiente. No se ejecutaron suite general ni benchmarks
extensos, conforme al alcance autorizado.

Limitación: los trabajos y el mantenimiento no eléctrico conservan su política
de muestreo galáctico; esta intervención no reconstruye sus transiciones dentro
de un intervalo ordinario. No hubo desviación de la calibración ni del umbral
de 07A.

## PT001-07B-F — regulación y cortes de recarga

La ejecución sintética previa al arreglo reprodujo un salto indebido al umbral
de SoC, consumo de recarga después del llenado y un corte innecesario tras
deslastrar la bahía. Un cuarto fallo inicial provenía de la preparación de la
prueba (god mode es una propiedad derivada) y se corrigió antes de validar.
El deslastre inmediato precede ahora a los cortes de recarga. Un deslastre
temporizado por calidad divide el intervalo eléctrico en su frontera efectiva;
se recalcula la asignación para el resto. La batería principal solo se ajusta
al 25 % para eliminar redondeo si ese mismo tramo regulado alcanzó el umbral.
God mode nunca cambia su energía almacenada. El temporizador de deslastre por
calidad sigue disparándose una vez por intervalo eléctrico ordinario.

Validación con `/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_07b.py tests/test_electrical_proper_time.py tests/test_nav_electricity.py tests/test_nav_public_physical.py tests/test_nav_engine_wear_cut.py tests/test_nav_boundaries.py` → **160 passed, 14 subtests passed** en 51,44 s, con el código final.

No se ejecutaron la suite general ni benchmarks extensos. La política y
calibración de recarga aprobadas siguen intactas. **TEMP-01** queda registrado
como trabajo futuro; no se ha auditado aquí la base temporal de otros
subsistemas.
