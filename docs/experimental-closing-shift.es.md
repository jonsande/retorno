# 4D-3e5c-C1 — El turno de cierre

[English](experimental-closing-shift.md). Contenido experimental de prueba;
**no es canon narrativo definitivo ni contenido instalado**.
Base: `main`, `a0acbd1` (HEAD local al comenzar).

Archivos nuevos: `tests/authored_closing_shift_integration.py`, esta nota y su
traducción, y `tests/fixtures/authored_closing_shift/`: `arc.json`, `single.json`,
`closure.en.txt`, `closure.es.txt`, `repetition.en.txt`, `repetition.es.txt`,
`inventory.en.txt`, `inventory.es.txt`.

Cierre es una estación clausurada; Margen conserva un bucle automático del
registro de cierre; Estiba es un remolcador retirado, declarado como `ship`
explorable. Quedan lámparas y un hervidor sin recoger. Los documentos no
determinan el destino de las personas ni afirman supervivientes actuales.

El arco declara las tres identidades una sola vez mediante `world_requirements`.
Cierre está en `(0.002, 0.002, 0)` ly; Margen a `0.002` ly de Cierre;
Estiba a `0.002–0.003` ly de Margen, con posición dependiente de la semilla.
Se certifican proximidad ECHO-7/Cierre, enlace físico Cierre/Margen, proximidad
Margen/Estiba y asociación histórica Cierre/Estiba. Los `spatial_bindings`
congelan ID, sector y coordenadas reales en las pistas. El LINK operativo
ECHO-7/Cierre no afirma una arista histórica directa.

El primary es un LINK por uplink de ECHO-7 a Cierre. Los dos secundarios son
el acta por salvage en Cierre (LINK a Margen) y su repetición por radio en
Margen (NODE y LINK a Estiba). El single del inventario se coloca por separado
en Estiba; no tiene condición de progreso del arco ni aporta otro desbloqueo.
Las cuatro piezas usan forzado `hard` para esta prueba, sin cambiar el balance.
Los filtros geométricos del single certifican Estiba en las semillas probadas;
no equivalen a una restricción universal por ID.

La emisión `closing-archive-loop` comienza en `t=-31536000` s y continúa como
archivo automático. Está vinculada al secundario: proximidad y radiod por sí
solos no lo entregan; el scheduler y un trigger legítimo de dock lo preparan.
Cierre y Estiba declaran emisores sin emisiones. No se desactiva B1/B2.

El recorrido público probado, en sandbox normal y sin debug, es:

1. `power off security`, `dock ECHO_7`, `wait 60`, `uplink` (también se repite).
2. `undock`, `wait 60`, `nav CLOSING_STATION`, esperar la ETA; `dock CLOSING_STATION`,
   `wait 60`, `power on drone_bay`, `drone deploy D1 CLOSING_STATION`, `wait 30`,
   `drone salvage data D1`, `wait 60`, `cat /remote/CLOSING_STATION/logs/records/closing_shift.es.txt`.
3. `drone recall D1`, `wait 60`, `power off data_core`, `power on comms`,
   `boot radiod`, `wait 5`; undock/nav/dock a `CLOSING_RELAY`, con sus esperas.
   Guardar/cargar la señal recibida; `intel import <archivo de señal>` y `cat <archivo de señal>`.
4. Undock/nav/dock a `CLOSING_WRECK`, restaurar `drone_bay`, desplegar D1 y recuperar
   datos; `cat /remote/CLOSING_WRECK/logs/records/left_inventory.es.txt`.
   Repetir salvamento y lectura; guardar/cargar y continuar con `wait 5`.

EN repite el recorrido con `.en.txt`. Las esperas de navegación usan la ETA
calculada por el motor; no se cambia posición, sistemas, pools ni RNG después
del arranque. Save/load usa la API de slots productiva, no el diálogo interactivo.
El test despacha las acciones del parser y los handlers públicos de la REPL.

Verificación reproducible desde la raíz del repositorio:

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/authored_closing_shift_integration.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
```

Resultados: ambas pruebas pasan. C1 compara compilación y orden de catálogo con
semillas 1, 29 y 701; juega el recorrido completo EN/ES con la semilla sandbox
16891. Comprueba identidades y relaciones, ausencia de divulgación en
status/diag/contactos/mapa, reservas previas al primary, textos compilados EN/ES,
propagación y frontera temporal de llegada con consultas puras, tres canales,
lectura/importación, rutas físicas válidas, dos ciclos de guardado/carga y
ausencia de entregas/archivos duplicados. Evidencia generada:
`/tmp/retorno-c1-evidence.json`. La frontera temporal se consulta por separado;
el recorrido recibe una emisión antigua que ya ha llegado.

Límites observados: los secundarios no esperan al primary; el uplink procedural
puede revelar Margen antes del acta; `uplink_only` entrega la ruta sin documento
narrativo. No se demuestra exclusividad del orden, continuidad universal ni
jugabilidad desde el prólogo averiado. No hubo bloqueo técnico ni necesidad de
modificar Python productivo. No se cambian catálogos activos, manuales ni help:
no cambia ningún comportamiento productivo. La instalación existe únicamente
en una copia temporal que conserva los cinco singles y las cinco localizaciones
activos. `log_copy.txt` tenía un cambio previo y queda fuera de la entrega.
No se hace staging, commit ni push; pendiente de revisión externa.
