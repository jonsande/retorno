# RETORNO — 4D-3e5c-P1

Base: árbol local sobre `main` `12887bb`, con C2b y FAST_SANDBOX pendientes.
El ZIP es incremental para ese árbol; no reempaqueta el trabajo previo.

## Causa y corrección

B1 seleccionaba entre destinos certificados, sin política authored por host.
En la semilla 29 seleccionaba ECHO_7 → HARBOR_12 y el uplink publicaba ese salto.
FAST_SANDBOX heredaba el efecto al consumir el mismo uplink durante su preparación.

Se declara `navigation_policy` en `data/locations/echo_7.json`, versión
`host-navigation-exclusions-v1`, con `exclude_destinations: ["HARBOR_12"]`.
Se captura antes de explorar. Se retiran solo registros/archivos seleccionados
excluidos, sin repetir sorteos ni rellenar huecos. B2 conserva su elección original
y suprime la emisión si el registro elegido está excluido, sin payload sustituto.
Archivos authored con un LINK contradictorio se rechazan antes de jugar; no se
reescribe testimonio. La caché EN/ES original y su contacto HARBOR_12 siguen intactos.

La huella completa incluye la política; los sorteos, IDs y cuerpos conservados
usan la definición de muestreo previa sin ese campo. El campo no físico tampoco
entra en la huella física. No cambian posiciones, topología, ámbito ni IDs del
universo. La comparación adicional con los productores originales guardados antes
de editar confirma las diferencias previstas en semillas 1, 29 y 701 y sus hosts
comprobados: solo desaparece el registro excluido y cambian huellas de definición.

## Archivos propios de P1

- `data/locations/echo_7.json`: exclusión declarativa.
- `src/retorno/worldgen/information.py`: captura/validación, muestreo estable y
  exclusión sustractiva de uplink/archivos.
- `src/retorno/worldgen/historical_radio.py`: conserva sorteos y evita sustitución
  de emisiones navegacionales excluidas.
- `src/retorno/worldgen/radio.py`: separa la política del catálogo físico.
- `tests/prologue_navigation_policy_smoke.py`: nueva regresión focal.
- `tests/historical_information_smoke.py`, `tests/historical_radio_smoke.py` y
  `tests/structural_recovery_smoke.py`: ajustes de fixtures para catálogo C2b activo,
  huella física separada y pruebas aisladas de cuotas/protección/guardado antiguo.
- Contratos B1/B2 EN/ES, este informe EN/ES y evidencia JSON en `docs/testing/`.

Los ajustes de fixtures conservan sus comprobaciones: el guardado B0 se abre con
su catálogo original en copia temporal; la celda densa usa 300 hosts para superar
128 emisiones (con 260 producía 123); la prueba de ledger compartido fija semilla 1.
No se modifica la lógica de F-DEAD-01. Se preservan C2b, FAST_SANDBOX, TODO y todo
trabajo previo; no se modifican AMANECER, balance, mantenimiento, route solve,
alcance, conexiones físicas, manuscritos o textos de ECHO-7.

## Validación

Intérprete: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.

| Script | Resultado |
| --- | --- |
| `tests/prologue_navigation_policy_smoke.py` | PASS, cuatro grupos focales |
| `tests/historical_information_smoke.py` | PASS, 16 grupos |
| `tests/historical_radio_smoke.py` | PASS, 27 grupos |
| `tests/fast_sandbox_smoke.py` | PASS |

- **29:** el uplink de ECHO-7 pasa de tres a dos registros originales, sin suplente;
  comprobado en FAST_SANDBOX y mediante comandos del prólogo normal. Salvamento y
  lectura de la caché dan el contacto, sin ruta. También se comprueba EN/ES.
- **1:** recorrido público desde FAST_SANDBOX: leer caché/uplink de ECHO-7, seguir
  el primer destino adquirido `P-2.2.2.0`, hacer allí uplink y viajar a HARBOR_12.
  Se conservan los dos saltos de 24,14 y 17,43 ly; llegada efectiva sin debug,
  teleportación ni modificaciones de estado/recursos. No se repite la introducción.
- **701:** se mantienen los registros de otros hosts, incluido el archivo
  `/logs/nav.log` de `P-2.1.0.0` hacia HARBOR_12. No se afirma acceso público hasta
  esa fuente ni se vuelve a ejecutar el recorrido aleatorio de décadas.
- Fixture separada verifica exclusión real de archivos navegacionales y de una
  emisión B2 seleccionada, sin mensaje de sustitución; las semillas de producción
  por sí solas no ejercitan todos esos casos. Consultas puras y geometría estable.
- Guardado/carga nuevo, uplink agotado sin duplicados, rechazo no destructivo del
  catálogo anterior y carga de ese mismo guardado al restaurar su catálogo.

No se ejecutó la batería completa ni se amplió el barrido de semillas.

## Versionado, límites y garantía pendiente

Extensión aditiva versionada: B1/B2 y esquema de guardado mantienen sus versiones.
Sin política, el productor v1 previo sigue igual. El cambio de JSON altera la
huella instalada y las huellas completas B1/B2: guardados del catálogo anterior
se rechazan mediante el contrato existente, sin migrarlos ni borrar rutas. Debe
conservarse/restaurarse su catálogo para continuarlos. No hay migración amplia.

La regla se aplica a B1 y B2 procedural derivado; emisores authored independientes
y piezas del scheduler conservan sus contratos. No se garantiza completar el
prólogo. Para ello falta certificar antes de jugar una cadena completa desde el
conocimiento legítimo inicial hasta una fuente intermedia recuperable y finalmente
HARBOR_12, incluyendo canales, cotas de salto, disponibilidad temporal si hay radio,
protecciones y adquisición/importación pública. La existencia de un host o de una
pista aislada no basta; presupuestos agotados siguen siendo búsquedas incompletas.

No cambian help ni manuales diegéticos: es una regla de autoría y no se añaden
comandos ni información pública. Inventario y SHA-256 acompañan el ZIP. Sin
`git add`, commit ni push; detenerse para revisión externa.
