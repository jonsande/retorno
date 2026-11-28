# PT001-10 — validación de diagnósticos de partida

Fecha: 2026-11-28. HEAD inicial: `840d354c36a74e55844e9d20e5ec13b1aab3845f`.
Se conservaron el cambio ajeno de `TODO.md` y los artefactos de revisión previos.

CLI y Textual comparten un diagnóstico puro de partida. Distingue motores
apagados de averiados, velocidad seleccionada superior a la capacidad actual,
acoplamiento/tránsito, destinos desconocidos/actuales/sin ruta/fuera de alcance,
antimateria y restricciones eléctricas o del sistema operativo central.
`nav map routes` usa el mismo diagnóstico. Se mantienen las estimaciones válidas,
las maniobras locales, la confirmación sobre abandono de drones y la
revalidación de Engine. El resultado de destino desconocido no depende de la
existencia física oculta.

Validación dirigida con `/home/jon/prog/retorno_case/retorno_venv/bin/python`:

- `-m pytest -q tests/test_pt001_10.py` → primera ejecución: **16 superadas, 1 fallida**. El nuevo caso de fuera de alcance esperaba una fila en el mapa, pero el mapa existente excluye correctamente los saltos que superan el límite. Se corrigió la expectativa.
- `-m pytest -q tests/test_pt001_10.py tests/test_nav_routes_presentation.py tests/test_engine_speed_upgrade.py tests/engines_antimatter_smoke.py tests/test_nav_public_physical.py -k 'pt001_10 or nav_routes_presentation or compact_nav_confirmation or compact_local_confirmation or blocked_departure or public_views_localization or no_disclosure_or_query_mutation or nav_public_physical or engines_antimatter and (local_travel or insufficient_fuel)'` → **51 superadas, 1 fallida, 30 excluidas y 38 subpruebas superadas**. La falla aislada corresponde a `EnginesAntimatterTests.test_05_insufficient_fuel_atomicity_and_exact_balance`: la segunda partida emite `TRAVEL_STARTED`, pero la prueba exige el indicador legacy `ship.in_transit`, que el tránsito físico actual no activa. También falla al ejecutarla sola. PT001-10 no modifica el motor ni esa prueba.
- `-m pytest -q tests/test_pt001_10.py tests/test_nav_routes_presentation.py tests/test_nav_public_physical.py tests/test_engine_speed_upgrade.py::EngineSpeedUpgradeTests::test_compact_local_confirmation_invalid_unknown_and_drone_warning tests/test_engine_speed_upgrade.py::EngineSpeedUpgradeTests::test_blocked_departure_never_asks_for_confirmation_cli_or_textual tests/engines_antimatter_smoke.py::EnginesAntimatterTests::test_07_local_travel_and_isolated_engines tests/engines_antimatter_smoke.py::EnginesAntimatterTests::test_08_public_views_localization_and_textual_confirmations tests/engines_antimatter_smoke.py::EnginesAntimatterTests::test_09_no_disclosure_or_query_mutation` → **50 superadas y 34 subpruebas superadas** en 16,82 s.
- `-m pytest -q tests/test_pt001_10.py` → **17 superadas** en 4,80 s tras ajustar el texto de la última sugerencia de recuperación.
- `-m pytest -q tests/test_pt001_10.py` → **19 superadas** en 5,14 s tras añadir casos explícitos de motores indisponibles y núcleo del sistema operativo en estado crítico.
- El mismo comando dirigido final indicado arriba → **52 superadas y 34 subpruebas superadas** en 17,66 s tras preservar la excepción de maniobras locales respecto a la ruta eléctrica de propulsión interestelar.
- Repetición final de ese comando → **54 superadas y 34 subpruebas superadas** en 17,93 s tras añadir los casos de bloqueo del terminal por soporte vital y ruta adquirida incompleta.
- Repetición final tras añadir el caso de motores ausentes → **55 superadas y 34 subpruebas superadas** en 19,62 s.

No se ejecutaron la suite general ni benchmarks. No se hizo commit ni push.

## PT001-10-F — regresiones históricas de navegación

Las pruebas de antimateria comprueban ahora el tránsito físico, el plan nominal
y su estimación previa en lugar de `ship.in_transit` y `arrival_t` legacy para
partidas interestelares. El rechazo con el flotante representable inmediatamente
inferior al precio es atómico; la partida con el precio exacto cobra una sola
vez y deja la reserva a cero. Las solicitudes duplicadas y el aborto durante
el tránsito físico se rechazan sin otro débito. La trayectoria cargada conserva
su pago y llega al destino sin cargo de llegada. Tras la primera ejecución se
actualizaron las mismas expectativas obsoletas de test_11 y test_12 de Textual;
se conserva su cobertura de motores, combustible, confirmación y aborto
bloqueado.

La prueba de destino desconocido varía datos físicos ocultos dentro (2 al) y
fuera (1000 al) del alcance, con nodos, contactos y enlaces conocidos idénticos.
La salida pública, el estado y el RNG permanecen iguales.

Los patrones efectivos `python_files` de pytest son `test_*.py` y `*_test.py`;
`engines_antimatter_smoke.py` **no se recoge automáticamente**. Se ejecutó
indicando su ruta explícita. No se cambió la configuración de descubrimiento.

Validación con el Python del proyecto:

- `-m pytest -q tests/engines_antimatter_smoke.py tests/test_pt001_10.py` →
  **34 superadas, 2 fallidas** (expectativas obsoletas adicionales de test_11/test_12).
- El mismo comando tras actualizar esas expectativas → **36 superadas** en
  24,45 s.
- Repetición final tras comprobar el mensaje localizado de aborto bloqueado en
  Textual → **36 superadas** en 23,51 s.

No se modificaron código productivo, reglas de navegación ni Balance. No se
ejecutaron la suite general ni benchmarks; tampoco se hizo commit o push.
