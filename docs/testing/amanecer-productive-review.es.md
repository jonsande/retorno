# RETORNO — 4D-3e5c-C2b, revisión externa

Base: `main` actualizado, `12887bb` (2026-11-07). Arco instalado en el árbol de
trabajo; **recorrido jugable completo no certificado**. Se detiene la exploración
para revisión del descubrimiento, sin añadir pistas o rutas correctivas.

## Archivos

- Nuevo `data/arcs/amanecer_elena_01.json` y diez `.txt` EN/ES en
  `data/lore/packs/amanecer_elena_01/`: copias byte a byte del borrador aprobado.
- Nuevos `tests/amanecer_productive_integration.py` (comprobación estructural) y
  `tests/amanecer_public_journey.py` (reproducción pública acotada).
- Tres regresiones solicitadas adaptadas al catálogo ya no vacío: fixtures
  temporales reutilizables y selección por identidad de la pieza sintética.
- Contrato narrativo, scheduler, diseño relativo y README de integración EN/ES
  sincronizados. `narrative/amanecer/LOCATIONS.md` y nuevo `LOCATIONS.en.md`
  registran la decisión Liria y conservan el estado editorial anterior pendiente.
- Este informe EN/ES y evidencias JSON productiva y de recorrido en `docs/testing/`.
  El inventario del ZIP contiene la relación exacta y SHA-256 por archivo.

No cambia Python productivo, otros arcos, singles, worldgen, radio, F-DEAD-01,
balance, recursos, audio ni Textual. Borrador y manuscritos intactos. El cambio
local previo de `TODO.md` se conserva y se excluye del paquete.

## Pruebas

Intérprete: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.

| Script | Resultado |
| --- | --- |
| `tests/lore_relative_placement_integration.py` | PASS: tres semillas, EN/ES, salvamento/lectura, reservas y persistencia con fixture temporal |
| `tests/narrative_world_integration_smoke.py` | PASS: 20 comprobaciones |
| `tests/authored_closing_shift_integration.py` | PASS: compilación y viaje EN/ES |
| `tests/amanecer_productive_integration.py` | PASS: copias exactas, carga instalada, geometría, no divulgación, rutas de archivos, reservas, guardado/carga y no duplicación de archivos preparados |
| `tests/amanecer_public_journey.py` | Ejecutado sobre la semilla 701: recorrido incompleto, no PASS de accesibilidad |

Las tres regresiones fallaron inicialmente por supuestos de fixtures anteriores
al primer arco activo (catálogo vacío, directorio de textos inexistente, primera
pieza = pieza sintética); se corrigieron solo esas pruebas. No apareció un defecto
reproducible que exigiera tocar el motor. No se ejecutó la batería completa.

Semillas 1, 29 y 701 solo para geometría/distribución: tres hosts distintos,
posición estable de Liria y LINK HARBOR_12–Liria menor de 45 ly. La prueba
productiva valida EN/ES en 701 y persistencia sin duplicar archivos preparados.
C2a verifica entrega/lectura mediante fixture trasladada: **no prueba viaje público**.
Los guardados del nuevo catálogo cargan; los del catálogo previo se rechazan por
huella, sin alterar el archivo. Conservar el catálogo original para partidas antiguas.

## Recorrido público y bloqueo concreto

Reproducción: ejecutar `tests/amanecer_public_journey.py`. Usa prólogo normal 701,
parser, motor y handlers públicos de lectura/uplink/hibernación, sin debug,
teleportación, edición de estado, recursos o RNG. Los `wait` se simulan a pasos de
un segundo; los viajes largos usan la hibernación existente. Inicialmente repara
generación/distribución/comunicaciones, arranca sensores y descubre ECHO-7.
Recupera su caché y conoce HARBOR_12 por lectura legítima. La política solo elige
contactos conocidos con ruta adquirida o dentro del alcance de sensores; prioriza
destinos authored conocidos y después aproxima hacia HARBOR_12. El límite es seis
escalas; termina tras cinco al no quedar opciones que cumplan esa política.

Itinerario observado: `ECHO_7 → P-2.2.1.0 → P-0.4.0.0 → P-0.2.1.1 → P-2.2.0.0`.
Transcurren 2 210 349 022,43 s (70,09 años). Los cuatro tránsitos largos consumen
aproximadamente 20,37 + 17,97 + 16,77 + 14,98 años. En la tercera escala D1 queda
sin batería para salvamento/recall; el itinerario continúa sin resolver ese
mantenimiento, y D1 acaba inutilizado. En la quinta escala la distribución queda
LIMITED: `power on sensors` y `boot sensord` exigen NOMINAL; uplink tampoco puede
continuar porque datad está detenido. La estrategia no incluye un plan de
mantenimiento ni explora todas las alternativas: **su fallo no demuestra que
la colocación variable haga imposible el arco**, ni que se agote toda vía legítima.

| Distinción | Demostración |
| --- | --- |
| Host físicamente existente | Sí: testigo certificado `P-4.1.0.1` en 701, materializado por mecanismos existentes. |
| Host accesible | No certificado desde el prólogo. La consulta finita de grafo tampoco obtiene un camino testigo desde ECHO-7; no prueba ausencia global. |
| Host conocido por el jugador | No al terminar el recorrido. La reserva solo se consulta después del ensayo para evaluar el resultado. |
| Documento recuperable | Archivo reservado/preparado válido; salvamento y lectura probados con fixture temporal equivalente, no desde este recorrido. |
| Ruta a Liria obtenida/importada | No en el recorrido público. El LINK válido se importa al leer la pista en C2a. |
| Viaje a Liria y cuatro recuperaciones completados | No desde el prólogo; solo se verifica la asignación exclusiva y el mecanismo de recuperación con fixture. |

La evidencia completa está en `amanecer-public-journey-evidence.json`; la
estructural, en `amanecer-productive-evidence.json`. Son observaciones de desarrollo,
no conocimiento del jugador. **Riesgo abierto:** reserva seeded y existencia física
no aseguran un descubrimiento razonable de la pista ni una ruta pública hasta ella.
No se afirma imposibilidad ni se propone una corrección de canon/ruta. No promover
la integración como validada jugablemente sin revisar este punto.

No se cambian help ni manuales diegéticos: no hay comandos nuevos, y anunciar la
ubicación reservada revelaría secretos. Sin `git add`, commit ni push.
