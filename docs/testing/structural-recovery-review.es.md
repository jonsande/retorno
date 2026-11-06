# Informe actualizado — 4D-3e5: primera recepción estructural

[English](structural-recovery-review.md). Corrección focal para revisión externa, 2026-11-06.

## Diagnóstico reproducido

Antes de modificar producción se añadió el grupo 28: nave en `A` (pecio), ruta
dirigida conocida `A -> REMOTE`, relé histórico `REMOTE` y salida física válida
hacia `T`. La búsqueda devolvió `validated / complete_in_examined_scope` donde la
prueba exigía `conditional`. La radio local no podía recibir desde `A` una emisión
en `REMOTE`. Una ruta navegable era tratada indebidamente como acceso informativo.
El grupo 5 anterior también aceptaba esa equivalencia al comprobar el mejor origen
remoto. Un plan así preparado quedaba activo y bloqueaba otra selección del bloqueo.

Se conserva la entrega inicial no publicada y todos los cambios de Tweaks. HEAD
inicial/final: `ba705e73d958334ca2e5dfa8d57d6a1f3644b89a`; rama `main`, upstream `origin/main`.
El árbol mantiene **34 archivos modificados/nuevos acumulados**, índice vacío.
No se ejecutaron staging, commit ni push. Se preservó una copia íntegra inicial
de los 34 archivos antes de modificar la corrección.

## Solución y futura ampliación física

Se extrajo `communications.radio_spatial_block_reason` de las comprobaciones ya
existentes de fuente física, nodo actual, tipo de broadcast y dock cuando se exige.
Esta comprobación no inspecciona salud, alimentación ni radiod. No se añadieron
alcance, potencia, atenuación, latencia ni modalidad de entrega.

El selector utiliza ese predicado para definir los emisores admisibles de primera
recepción. Si hay emisores elegibles, la búsqueda parte de ellos y conserva distancia
dirigida, desempates y rodeos físicos. Si solo hay emisores remotos, puede devolver
una propuesta física diagnóstica `conditional / first_reception_outside_coverage`.
`request_recovery` solo confirma resultados `validated`; la existencia de `proposal`
no basta. `confirm_recovery` revalida cobertura antes de copiar/materializar, de modo
que tampoco una llamada directa confirma la propuesta remota condicionada.

| Aspecto | Comprobación |
| --- | --- |
| Historia física | Certificados del manifiesto; identidades, tipos, posiciones y saltos originales. |
| Acceso al emisor | Trayecto dirigido de navegación conocido. No demuestra recepción. |
| Primera recepción espacial | Predicado compartido en comunicaciones; hoy, contexto local. |
| Receptor operativo | Gates existentes de comms/radiod y suministro, comprobados al capturar. |

Un receptor apagado/averiado en la ubicación adecuada permite preparar un plan
pendiente. Sin cobertura, la búsqueda no crea plan, ledger de radio, archivo,
conocimiento ni intento/cooldown/contador. No hay guía omnisciente hacia el emisor,
correo interno gratis ni transmisor inventado. Una búsqueda condicionada no entra
en `recovery_plans` y por tanto no bloquea alternativas como frontera activa.
Los reintentos conservan cursor y permiten seleccionar nuevamente al cambiar de
ubicación/contexto.

Selección, confirmación y captura llaman al mismo predicado; F-DEAD-01 no contiene
una comparación propia de igualdad entre nodos para decidir cobertura. El grupo 34
sustituye únicamente ese predicado, en una prueba aislada, y demuestra que los tres
consumidores siguen la política compartida. La futura cobertura de 4D-3e5b se
implementará en esa frontera sin reescribir el selector. `pending=N` y demás cambios
de presentación se conservan para 4D-3e5a.

Al guardar/cargar un plan sin captura se comprueba además el contexto original
registrado en `access.path[0]`, mediante el mismo predicado con un receptor explícito.
No se exige que el jugador siga allí: un plan preparado legítimamente puede salir
y regresar con su recepción pendiente intacta. Guardados anteriores con primera
recepción remota inválida se rechazan explícitamente conservando el archivo, sin
borrado ni reescritura; no se introduce migración correctiva ni orientación ficticia.
No se cambian esquema, recursos, pools, scheduler o umbrales/cooldowns.

## Pruebas y resultados vigentes

**36 grupos estructurales correctos**: los 27 anteriores (grupo 5 adaptado a
resultado condicionado) y nueve nuevos. Se han reejecutado **20 grupos narrativos**
y **18 de comunicaciones**, además de navegación, worldgen, intel, guardados,
lore, energía/sistemas, planificadores, Textual y el resto de smoke tests.

| Grupo nuevo | Cobertura |
| --- | --- |
| 28 | Reproducción remota, confirmación directa rechazada y ausencia de progreso consumido. |
| 29 | Emisor local admisible frente a una cadena remota más corta (90 ly frente a un rodeo mayor). |
| 30 | Elegibilidad espacial con comms apagado/dañado; contexto de dock independiente. |
| 31 | Reparación y boot con comandos públicos; captura única tras recepción pendiente. |
| 32 | Búsqueda condicionada, ampliación, cambio de ubicación, save/load EN/ES e idempotencia. |
| 33 | Flujo público: búsqueda condicionada, viaje por ruta ya conocida, recepción local y lectura. |
| 34 | Única frontera espacial compartida por selección, confirmación y captura; prueba aislada sin implementar alcance. |
| 35 | Protección narrativa y diagnósticos genéricos sin revelar fuente/destino. |
| 36 | Contexto original de recepción en save/load, salida/regreso legítimos y preservación del guardado inválido. |

Flujos públicos nuevos desde escenas históricas declaradas, sin editar estado para
resolverlos después de iniciar los comandos; se mantienen separados del recorrido
real del prólogo y de las fixtures de fallos:

```text
PUBLIC FIRST RECEPTION REPAIR: power off security -> drone deploy D1 BRG-01 -> drone repair D1 comms -> power on comms -> boot radiod ; one capture
PUBLIC FIRST RECEPTION FLOW: scan -> nav REMOTE -> power off security -> power on comms -> boot radiod -> cat received file; one capture
```

Batería global final: **63/64 scripts correctos**. Único fallo:
`radiation_hull_smoke.py:183`, `AssertionError: []`, fixture `CARNAVAL_34`.
La traza es idéntica a la entrega inicial; no se corrigió ni se ocultó por esta vía.
Textual pasa en la ejecución final. Manuales EN/ES y `git diff --check`: PASS.
La pasada inicial de esta corrección (35 grupos, antes del guard adicional de
persistencia) también terminó en 63/64; la evidencia final usa 36 grupos.

```sh
# Canonical environment; temporary runner executes every tests/*smoke*.py serially,
# with PYTHONPATH=src:repo and isolated save directories.
/home/jon/prog/retorno_case/retorno_venv/bin/python /tmp/retorno_e4_regression.py e5-first-reception-final 1
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/manuals_style_check.py
git diff --check
```

El comando individual del script estructural se ejecutó antes de la prueba 36;
los 36 grupos completos se ejecutaron nuevamente en la batería global final.
Los logs, resultados por script y métricas actuales están en
[la evidencia acumulada](structural-recovery-test-results.json), que conserva
separadamente los resultados de la entrega inicial. La generación procedural no
se modificó; las pruebas correspondientes sí se ejecutaron de nuevo.

## Alcance, archivos y entrega

La corrección modifica **12 archivos** de los 34 acumulados; los restantes
**22** conservan exactamente sus bytes de la entrega inicial. No se modificaron
Textual/audio, AMANECER, historias, generación, balance/salud/consumo de comms,
radiod, gramática de intel, pools, salvamento ni umbrales/cooldowns.
Manuales de comms y contratos de selección/radio EN/ES actualizados. La ayuda y
comandos públicos no cambian; no requieren sintaxis nueva.

- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/structural-recovery-review.es.md`
- `docs/testing/structural-recovery-review.md`
- `docs/testing/structural-recovery-test-results.json`
- `src/retorno/core/communications.py`
- `src/retorno/core/structural_recovery.py`
- `tests/structural_recovery_smoke.py`

ZIP nuevo **íntegro**, con todos los archivos acumulados y rutas relativas:
`retorno-4D-3e5-first-reception-review-20261106.zip`. Se verifican inventario exacto, bytes, CRC y SHA-256 externo;
el checksum se entrega en el archivo `.sha256` acompañante y en la respuesta,
sin introducir una referencia circular dentro del propio ZIP. El ZIP inicial
`retorno-4D-3e5-review-20261106.zip` permanece intacto. Índice vacío y HEAD conservado.
Se detiene la intervención para revisión externa.

Inventario acumulado vigente:

- `data/manuals/concepts/navigation.en.txt`
- `data/manuals/concepts/navigation.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/design/deadnode-chain-planner.es.md`
- `docs/design/deadnode-chain-planner.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/systems/discovery-navigation-intel.es.md`
- `docs/systems/discovery-navigation-intel.md`
- `docs/systems/exploration-failsafes.es.md`
- `docs/systems/exploration-failsafes.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/structural-recovery-review.es.md`
- `docs/testing/structural-recovery-review.md`
- `docs/testing/structural-recovery-test-results.json`
- `src/retorno/core/communications.py`
- `src/retorno/core/deadnodes.py`
- `src/retorno/core/engine.py`
- `src/retorno/core/exploration_recovery.py`
- `src/retorno/core/lore.py`
- `src/retorno/core/structural_recovery.py`
- `src/retorno/io/save_load.py`
- `src/retorno/model/world.py`
- `tests/exploration_recovery_smoke.py`
- `tests/known_routes_integrity_smoke.py`
- `tests/passive_communications_smoke.py`
- `tests/structural_recovery_smoke.py`
- `tests/uplink_authored_and_failsafe_smoke.py`

## Informe de la entrega inicial — historial

La sección siguiente conserva el informe original. Sus cifras de grupos y nombre
de ZIP corresponden a esa entrega histórica; para esta corrección prevalecen los
resultados, contrato y paquete indicados arriba.


[English](structural-recovery-review.md). Fecha: 2026-11-06. Entrega para revisión externa, sin commit.

## Resultado y base auditada

F-DEAD-01 utiliza sitios históricos certificados, búsqueda dirigida acotada con
ampliación y preparación transaccional. La primera pista se recibe por el ledger
común de radio; las siguientes requieren lectura y exploración de cada etapa.
No se fabrican estaciones, puentes ni gateways. No se garantiza una salida universal.

HEAD inicial y final: `ba705e73d958334ca2e5dfa8d57d6a1f3644b89a`. Rama `main`, upstream
`origin/main`; referencias locales coincidentes. El SHA remoto de partida fue el
confirmado por el desarrollador; no se atribuye esta entrega a un commit nuevo.
Árbol inicial limpio; árbol final con 34 archivos modificados/nuevos listados abajo.
Índice vacío. No se ejecutaron `git add`, commit ni push.

Se leyeron AGENTS, canon/coherencia, roadmap 1.3 y los contratos indicados;
se auditaron modelos, planificadores, worldgen, lore, radio, persistencia, motor,
CLI y presentadores Textual. La referencia distingue decisiones D01–D24 aprobadas,
núcleo consultivo 3b/3c/3d y aplazamiento implementado en e4b. Las descripciones
históricas que fabricaban nodos quedan explícitamente subordinadas al contrato e5.

`Tweaks` permanece: comms OFFLINE 0.72, consumo real cero desconectado,
LIMITED al activarlo si sus dependencias lo permiten; avisos `(Try: boot …)` /
`(Prueba: boot …)`; deploy sin destino resuelve la bahía real; el panel de sistemas
Textual no incluye recepción. No se modificaron balance, datos del universo,
canon, audio, UI, borradores de AMANECER ni contenido de arcos/singles.

## Arquitectura y comparación con legacy

El [contrato productivo](../systems/structural-recovery.es.md) describe el algoritmo
y todos los límites. `select_recovery` es puro, sin RNG ni materialización. Usa el
manifiesto fijado, consulta física inversa con Z, certificados de sitios presentes
/lazy/authored y ordenación estable. Dijkstra prioriza distancia completa desde
la nave, incluido el acceso dirigido real al emisor; desempata por incertidumbre,
saltos e ID. Considera rodeos y escalas con enlaces dirigidos ya conocidos.

Se reutilizan `AccessRoute`, lectura de fuentes del planificador, capacidades de
entrega, política de primaries y kernel de salto. No se reutiliza como autoridad
la propuesta de nuevas posiciones de `propose_deadnode_chain`; las APIs
`evaluate_deadnode_opportunity` y `compare_deadnode_opportunities` retienen su
función diagnóstica, incluidos sus análisis económicos. El adaptador evita que
esos filtros invaliden una oportunidad estructural.

Se retiraron los creadores `_create_bridge_node`, `_sample_anchor_offset`,
`_ensure_entry_node` y `_ensure_gateway_node`, junto a su preparación retrospectiva.
Se conserva el consumo de cadenas legacy ya presentes y válidas. El antiguo
`recovery_activation_deferred` queda como campo compatible, sin activar creación;
los diagnósticos leen resultados de búsqueda y estados de planes.

Presupuesto predeterminado: 16 sectores por consulta, 2048 sitios, 4096 expansiones,
65536 aristas y 1024 certificados retenidos. Cursor de capas 3D, prioridades
iniciales de sectores observados/generados y corredor a objetivo explícito;
reintento determinista amplía el ámbito sin radio máximo de juego. Los límites
finitos de memoria, clausura, dominio y materialización pueden impedir demostrar
una cadena. Nunca se interpreta ese agotamiento como imposibilidad galáctica.
El código distingue `search_pending`, `validated`, `conditional`, `none_in_scope`,
`incomplete` e `invalid`. No promete optimalidad fuera del inventario examinado.

La confirmación revalida scope/versionado, huella estructural (incluidos trackers),
identidades, posiciones, tipos, procedencia, acceso, cada salto y fuentes/protección.
Materializa conjuntamente sobre una copia y prepara documentos/ledger antes de
publicar. Un fallo descarta la copia. La publicación conserva referencias existentes
a nodos/pools de los comandos. No consume recursos, intel, archivos ni RNG; tampoco
rolls o asignaciones narrativas. La misma oportunidad se reutiliza idempotentemente.

## Estados y entrega

| Estado | Significado / transición |
| --- | --- |
| Búsqueda pendiente/incompleta | Todavía sin propuesta demostrada; reintento sin consumir entrega. |
| `prepared` | Preparación interna transaccional. |
| `receipt_pending` | Fuente preparada en ledger; faltan gates/contexto de captura. |
| `active` | Comunicación capturada o etapa de salvamento habilitada. |
| `stage_consumed` | Lectura/importación publicó el enlace; falta llegar a la etapa siguiente. |
| `complete` | Última pista consumida y destino final alcanzado. |
| `invalid` | Revalidación física, de fuente o identidad fallida. |

La primera fuente es un hub histórico alcanzable, con emisión local admitida por
el modelo vigente. No hay emisor ficticio ni nueva cola. Cada pista contiene un
solo LINK positivo ≤45 ly; el parser real conserva su semántica bidireccional.
Ni seleccionar, confirmar ni capturar revela la cadena o publica rutas. Leer y
llegar habilitan la siguiente fuente. Un enlace operativo ya conocido se reutiliza
sin archivo nuevo. Salvamento se prepara en una ventana abierta antes de visita;
no se reabren pools ni se reponen archivos o recursos. Los hosts reservados se
excluyen y los primaries no interpretables bloquean conservadoramente el candidato.
Scan natural y resolución manual exacta conservan sus excepciones.

Se comprueban fronteras dirigidas, uplink pendiente independiente de reparaciones,
datos sin consumir, LINK/NODE legibles recuperados y planes activos. La existencia
estructural no depende de electricidad, salud, drones, scrap, radiación o reparación.
La captura sí comprueba `comms`, `radiod`, suministro, tránsito/hibernación y fuente
local vigente. Las pruebas conservan independencia de sensord/datad, correo interno,
salvage y gates propios de uplink.

El primer mensaje realmente capturado incrementa una vez attempts/last_action_t
para deadnode, o contador/generación global. Preparación, fallo, presupuesto,
recepción bloqueada y obsolescencia no cuentan. Las demás etapas no consumen otro
intento; se mantienen umbrales, semillas, triggers y cooldown originales. Un tracker
resuelto puede retirarse según la política previa; plan y ledger conservan historial.
Se persisten manifiesto, plan versionado, etapa, fuentes, capturas/lecturas, cursor,
certificados, contadores, pools e intel. Versiones incompatibles se rechazan y el
archivo se conserva; no se añadió migración histórica compleja.

## Validación y recorridos públicos

Referencia inicial: **62/63** scripts smoke correctos. Final: **63/64** correctos,
con el nuevo script incluido. Único fallo en ambas: `radiation_hull_smoke.py:183`,
`AssertionError: []`, fixture `CARNAVAL_34`; trazas literalmente iguales.
No se modificó radiación ni se presentó esa prueba como aprobada.

Integración nueva: **27 grupos**. Cubren materializados/lazy/authored, vacío,
aislado, Z, semillas/órdenes/procesos, distancia dirigida y rodeos, 45/>45/cero,
extremos ausentes, presupuestos/ampliación, invariancia económica, gates y retorno
a fuente, captura/lectura/etapas, pools visitados/limpios/cerrados, documentos antes
de consumir, primaries/scan/manual, save/load en fronteras, colisiones, snapshot
obsoleto y fallo inyectado después de materializar la copia, contadores/cooldown,
escalas con rutas conocidas, UI/localización y fronteras NODE recuperadas.

Integración narrativa: **20 grupos**; comunicaciones: **18 grupos**. Pasan las
regresiones de worldgen/manifiesto, navegación, planificadores 3b/3c/3d, lore/intel,
scan, energía/sistemas, salvage/pools, guardado/carga y Textual.
Un pase intermedio de `textual_theme_smoke.py` falló con `NoMatches` durante un
callback de desmontaje de `#header`. No se cambió Textual; las pasadas posteriores
completas, incluida la final, pasan. La traza intermedia se conserva en la evidencia.

El grupo 26 empieza una partida real seed 701 con contenido instalado, sin fixture
ni edición de recursos, geografía o sistemas: reparaciones normales, comms/radiod,
sensores, scan, route solve, viaje y dock en ECHO_7. Conserva una frontera existente
y evita un rescate innecesario. El grupo 19, separado, recorre recuperación positiva
con comandos públicos desde una escena histórica sintética agotada, sin modificar
estado para resolverla. Las cadenas difíciles y fallos usan fixtures distintas;
no se atribuye al prólogo una recuperación que no necesitaba.

```text
PUBLIC SCENE FLOW: power off security -> power on comms -> boot radiod -> scan -> cat /logs/broadcasts/A_0011.en.txt -> nav B ; resources and systems use ordinary rules
PUBLIC INSTALLED FLOW: power off security -> power off data_core -> drone deploy D1 PWR-A1 -> drone repair D1 power_core -> drone repair D1 power_core -> drone repair D1 power_core -> drone move D1 BUS-A2 -> drone repair D1 energy_distribution -> drone repair D1 energy_distribution -> drone move D1 BRG-01 -> drone repair D1 comms -> power on comms -> boot radiod -> power on sensors -> boot sensord -> scan -> route solve ECHO_7 -> nav ECHO_7 -> dock ECHO_7 ; t=2153.115s scrap=49; existing frontier preserved
```

Comandos principales ejecutados (el runner temporal usa el intérprete canónico,
PYTHONPATH=src:repo, directorios de guardado temporales y timeout por script):

```sh
# Baseline and final global runs, canonical venv; serial runner invokes every tests/*smoke*.py.
/home/jon/prog/retorno_case/retorno_venv/bin/python /tmp/retorno_e4_regression.py e5-baseline 1
/home/jon/prog/retorno_case/retorno_venv/bin/python /tmp/retorno_e4_regression.py e5-release 1
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/worldgen_manifest_comparison.py --production --output /tmp/retorno-e5-manifest-comparison.json
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/manuals_style_check.py
git diff --check
```

El mismo runner también ejecutó `e5-first`, `e5-final` y `e5-delivery` durante la
integración; la evidencia normativa de entrega es `e5-release`. Todos los smoke
scripts son reproducibles individualmente con el intérprete y PYTHONPATH indicados.

Comparación física completa en 10 seeds (0–7, 29, 271828): métricas físicas,
componentes, identidades/distribuciones y recursos coinciden con
`manifest-integration-measurements.json`, excluyendo tiempos/benchmarks. Manuales
EN/ES: PASS. D01–D24 literalmente intactas en ambos roadmaps. AST/JSON, enlaces
nuevos y parejas EN/ES comprobados. `git diff --check`: PASS.

## Coste medido y límites

Medidas con `tracemalloc` en esta máquina; tiempo incluye instrumentación y
comprobación de pureza. No son umbrales de rendimiento ni promesa de tiempo real.

| Caso | Resultado | Segundos | Pico bytes | Sectores / cohortes | Expansiones / aristas |
| --- | --- | ---: | ---: | ---: | ---: |
| installed | validated | 0.249722 | 853771 | 16 / 42 | 2 / 25 |
| chain | validated | 0.068067 | 837338 | 16 / 38 | 3 / 2 |
| materialized | validated | 0.228007 | 955502 | 16 / 30 | 2 / 4 |

La búsqueda es síncrona bajo el bloqueo existente del motor y está acotada por
trabajo, no por deadline de reloj. Un inventario grande o cadena extensa puede
agotar presupuesto/ventana retenida; un nuevo ámbito no garantiza conservar toda
la cadena anterior. No hay exploración exhaustiva ni conectividad universal.
Puede faltar un emisor local, un intermediario con fuente, ámbito numérico o
recursos para viajar. El resultado permanece condicionado/incompleto/sin cadena
en ese ámbito; no se fabrica una solución. e6, validación jugable prolongada con
Textual y sonido, sigue pendiente. No se ampliaron balance ni modalidades de entrega.

## Archivos y paquete

34 archivos completos modificados/nuevos, todos incluidos en el ZIP con
rutas relativas. No incluye .git, venv, cachés ni guardados del usuario.
Inventario y SHA-256 por archivo se verifican externamente al ZIP. Se comprobó
inventario exacto, igualdad de bytes, CRC y SHA-256 del archivo final.
ZIP: `retorno-4D-3e5-review-20261106.zip`, junto al repositorio; checksum en el
archivo homónimo `.sha256` y en la entrega. El hash del ZIP no se introduce dentro
de un archivo que pertenece al propio ZIP, para evitar una referencia circular.
[Resultados completos](structural-recovery-test-results.json).

- `data/manuals/concepts/navigation.en.txt`
- `data/manuals/concepts/navigation.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/design/deadnode-chain-planner.es.md`
- `docs/design/deadnode-chain-planner.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/systems/discovery-navigation-intel.es.md`
- `docs/systems/discovery-navigation-intel.md`
- `docs/systems/exploration-failsafes.es.md`
- `docs/systems/exploration-failsafes.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/structural-recovery-review.es.md`
- `docs/testing/structural-recovery-review.md`
- `docs/testing/structural-recovery-test-results.json`
- `src/retorno/core/communications.py`
- `src/retorno/core/deadnodes.py`
- `src/retorno/core/engine.py`
- `src/retorno/core/exploration_recovery.py`
- `src/retorno/core/lore.py`
- `src/retorno/core/structural_recovery.py`
- `src/retorno/io/save_load.py`
- `src/retorno/model/world.py`
- `tests/exploration_recovery_smoke.py`
- `tests/known_routes_integrity_smoke.py`
- `tests/passive_communications_smoke.py`
- `tests/structural_recovery_smoke.py`
- `tests/uplink_authored_and_failsafe_smoke.py`
