# Contrato de diseño de navegación y recuperación

Versión inglesa: [navigation-recovery-contract.md](navigation-recovery-contract.md)

## 1. Estado y alcance

Este documento registra decisiones aprobadas por el desarrollador para la
estabilización posterior a la Fase 4. No sustituye las referencias canónicas de
[navegación](../systems/discovery-navigation-intel.es.md),
[failsafes](../systems/exploration-failsafes.es.md),
[lore](../systems/lore-scheduler.es.md) o
[worldgen](../systems/world-generation.es.md). Especifica el resultado de
diseño que deberán respetar las futuras correcciones.

La investigación se hizo sobre `320d06c` y el árbol documental de Fases 4A/4B.
Estas fases sólo actualizaron documentación y pruebas. Las correcciones
posteriores se identifican expresamente como completadas; las demás propuestas
no deben leerse como comportamiento ya implementado.

Etiquetas usadas:

- **Aprobado:** decisión de diseño vinculante para la implementación futura.
- **Implementado:** comportamiento observado que ya coincide con la decisión.
- **Divergencia:** comportamiento observado que contradice o no garantiza el
  contrato.
- **Propuesta técnica:** forma de abordar el contrato, todavía no aprobada como
  arquitectura ni implementada.
- **Por medir:** no hay evidencia suficiente para cambiar política o balance.

## 2. Contrato aprobado

### 2.1 Existencia, conocimiento y ruta

**Aprobado:** deben permanecer separados estos hechos:

1. una localización existe físicamente en `space.nodes` o es una referencia
   procedural materializable;
2. el jugador conoce el lugar o conserva una pista sobre él;
3. existe una ruta operativa publicada.

Una referencia narrativa no verificable puede persistir como pista histórica o
contacto pendiente, pero no cuenta como ruta. Una ruta operativa requiere
extremos físicos válidos, un salto no superior a `MAX_ROUTE_HOP_LY` (45 ly) y
coherencia con las reglas de navegación. Validez estructural y capacidad actual
de la nave para viajar son preguntas distintas.

No se exige que cada ruta publicada sea una arista de `SpaceNode.links`:
`route solve` e intel mantienen un grafo operativo propio en `known_links`.
Tampoco se puede declarar inválido un id procedural sólo porque su sector aún no
se haya materializado; la futura validación deberá distinguir una referencia
materializable de un id inexistente.

**Implementado:** `route solve <node_id>` puede resolver un nodo físico aún no
descubierto cuando se conoce su id exacto, está dentro del alcance de sensores y
del cap y `sensord` funciona. Es deliberado. El destino pasa a conocido y se
publica en `known_links`, sin modificar `SpaceNode.links`. Un nodo ausente y un
salto fuera de rango se rechazan.

**Implementado en 4D-1:** F-ROUTE-01 quedó corregido mediante el criterio
compartido de salto físico y la proyección operativa del grafo conocido. Las
aristas dangling/sobre cap ya no conectan componentes ni cuentan como frontera,
y sus pistas históricas permanecen. El detalle de productores, consumidores,
lazy y persistencia está en la referencia canónica de navegación.

**Implementado en 4D-2 (F-NAV-01):** abortar detiene la nave en la posición
interpolada exacta. Un waypoint detenido permite scan y route solve normales;
una ruta válida permite viajar realmente a un tercer destino sin regresar antes.
La llegada o el reemplazo limpian referencias temporales vivas y conservan el
historial. El [inventario canónico](../systems/discovery-navigation-intel.es.md#aborto-y-nodo-temporal)
detalla vida útil, jobs, abortos repetidos y persistencia.

### 2.2 Recuperación progresiva

**Aprobado:** no se exige conectividad universal. Pueden existir regiones,
nodos y documentos opcionales inaccesibles. Un mecanismo de recuperación debe
ofrecer una oportunidad utilizable, no garantizar que el jugador la detecte,
lea o interprete.

Cuando deadnodes declare éxito para un objetivo lejano, debe existir un plan
completo de saltos navegables. Las etapas se revelarán progresivamente. Se
reutilizarán localizaciones físicas existentes cuando sean adecuadas y sólo se
crearán nuevas cuando sea necesario. Si no existe una cadena válida, el
objetivo queda pendiente: no se publica una ruta imposible ni se consumen
intentos, cooldowns u otros estados como si hubiese habido rescate.

**Aprobado en 4D-3c:** si la cadena directa es inviable, buscar alternativas
regionalmente coherentes y rodeos antes de desistir. Preferir localizaciones
físicas adecuadas; no garantizar salida ni inventar excepciones procedurales.
Un viaje utilizable más largo puede prevalecer sobre otro corto inutilizable.

**Aprobado en 4D-3d:** preferir oportunidades razonablemente próximas mediante
el trayecto dirigido completo desde la nave, incluido acceso al origen.
La evidencia de frontera es secundaria; las regiones conocidas cercanas siguen
siendo legítimas y pueden ganar a otras desconocidas lejanas. Evitar retrocesos
desproporcionados sin añadir umbral fijo de rechazo. Estos criterios failsafe no
restringen worldgen, lore, arcos ni singles generales. Scan, documentos, salvage,
uplink aplicable y comunicaciones capturadas futuras siguen siendo canales;
no se exige volver indiscriminadamente a nodos antiguos para reescanear. Las
fuentes completadas siguen completas y no se garantizan recursos ni viaje exitoso.
La cobertura de sensores no está registrada con suficiente precisión para
autorizar apariciones retroactivas.

**Implementado parcialmente:** la recuperación global crea una entrada dentro
del alcance, reutiliza un gateway existente apropiado o crea uno bajo el cap, y
prepara una pista posterior en el pool de la entrada. No concede por sí sola
las rutas ni obliga a importar los archivos.

**Divergencia:** deadnodes crea el puente cerca del objetivo y publica el primer
enlace desde el nodo actual sin validar el salto completo. No crea una cadena,
no garantiza topología/pool utilizable y contabiliza el intento al escribir la
pista. La auditoría reprodujo un puente a 99,38 ly.

**Fase 4D-3b:** el [núcleo independiente de propuestas](deadnode-chain-planner.es.md)
calcula cadenas inmutables y no mutantes con dependencias informativas y de
materialización explícitas. Deadnodes productivo no lo invoca; F-DEAD-01 sigue
abierto, incluidas confirmación, persistencia de planes activos y entrega.

**Fase 4D-3c:** el núcleo puro añade rodeos 3D muestreados deterministas,
presupuestos técnicos y comprobaciones explícitas de materialización por nodo.
Agotar presupuesto informa de búsqueda incompleta, nunca imposibilidad universal.
Los nodos nuevos en sectores generados/explorados quedan condicionados a política
aprobada de aparición e inserción; aquí no se establece ni se activa producción.
El diseño del núcleo detalla dominio, mediciones y escrituras atómicas futuras.

**Fase 4D-3d:** la API contextual pura compara trayectos completos y conserva
conflictos prácticos como alternativas. Tiempo nominal y energía a perfil
constante son condicionados; costes futuros de reparación/salvage y viabilidad
económica siguen desconocidos. Sectores generados/visitados aún necesitan política
aprobada de inserción y aparición. La valoración no activa recuperación ni cambia
esquema de guardado, detector, recursos, recepción o UI; F-DEAD-01 sigue abierto.

Los umbrales, probabilidades y límites de balance no se cambian por este
contrato. Su ajuste requiere una evaluación separada.

### 2.3 Localizaciones visitadas

**Aprobado:** no se añadirán pistas obligatorias nuevas a archivos o recursos
locales de nodos ya visitados si eso obliga a volver para encontrarlas.

- Un nodo visitado puede ser referencia o escala de navegación.
- Un nodo existente no visitado puede ser una etapa de recuperación.
- Una pista indispensable debe prepararse antes de la primera visita y antes de
  que su fuente pueda consumirse.
- `visited_nodes`, `window_open` y `node_cleaned` expresan hechos distintos.
- No se reabrirán pools ni se alterará contenido opcional para forzar la cadena.
- Se evitará el backtracking repetitivo, sin prohibir todo regreso.

**Implementado:** el scheduler cierra ventanas al visitar y las fixtures
reparadas usan receptores sintéticos conocidos pero no visitados; no reabren un
pool visitado.

**Pendiente:** el futuro planificador de cadenas debe filtrar receptores y
preparar cada etapa de forma atómica antes de exponerla.

### 2.4 Recepción, captura y lectura

**Aprobado:** la primera pista será una señal o comunicación nueva de la nave,
no un archivo retroactivo en una estación antigua. Sólo se considerará recibida
si existen capacidades físicas y operativas apropiadas. Si faltan, quedará
pendiente y reintentable, sin pérdida ni duplicación.

Se distinguirán explícitamente:

1. **pendiente:** la oportunidad existe, pero aún no ha sido recibida;
2. **capturada/recibida:** la nave la almacenó bajo condiciones válidas;
3. **leída/importada:** el jugador abrió el archivo y, si contenía intel válida,
   ésta se incorporó al estado operativo.

No se adopta una dependencia universal de `datad`. Cada canal debe usar las
capacidades que correspondan a su arquitectura. Las pistas posteriores se
obtendrán explorando cada nueva etapa y toda pista indispensable conducirá a
una posibilidad navegable, no sólo a un destino fuera de alcance.

**Arquitectura aprobada para la fase posterior:** `captured_signal` y
`station_broadcast` requerirán el sistema físico `comms` operativo y el servicio
`radiod` activo, además de las condiciones del emisor. Un broadcast podrá
recibirse al entrar en cobertura sin dock cuando su modelo físico lo permita;
esto no adelanta piezas de lore cuyo trigger vigente sea `dock`.
`ship_os_mail` distinguirá mensajes internos del sistema operativo de correo o
comunicaciones externas. `uplink_trace` mantendrá los gates actuales de uplink
y `datad` sin imponer `comms` a todo uplink. `salvage_data` no dependerá de
`radiod`. Recibir y leer seguirán siendo operaciones distintas.

### 2.5 Protección narrativa

**Aprobado:** la recuperación automática no debe revelar antes de tiempo los
objetivos protegidos de un primary. Se mantienen dos excepciones deliberadas:
descubrimiento natural por `scan` y resolución manual por id exacto mediante
`route solve`, si se cumplen sus requisitos normales.

Un objetivo primary protegido no es lo mismo que un nodo procedural creado
como receptor obligatorio. La implementación futura tendrá que etiquetar o
resolver esa diferencia sin activar los arcos de `data/arcs/templates/` ni
modificar los cinco singles activos.

**Divergencia:** deadnodes y la recuperación global no aplican hoy una barrera
común de protección narrativa. No hay arcos activos que permitan medir el
impacto real, pero la ruta está presente en código.

### 2.6 Persistencia

**Aprobado para prealfa:** no se exige compatibilidad de partidas entre versiones
antiguas. Las partidas existentes son pruebas privadas y pueden descartarse;
no se desarrollarán migraciones históricas innecesarias. La versión vigente sí
debe conservar integridad interna, determinismo aplicable y cobertura de
save/load. Un save incompatible se rechazará de forma explícita, nunca se
cargará silenciosamente como válido ni se borrará automáticamente. Esta política
se revisará antes de una alfa o beta pública.

Dentro de una misma versión, las rutas inválidas no deben quedar operativas ni
contar como fronteras. Una referencia a un sector procedural no generado no se
considerará inválida sólo por no estar materializada. Filesystem, intel, rutas,
pools, lore, recuperación y deadnodes forman parte del estado serializado; las
pruebas futuras deberán demostrar consistencia e idempotencia sólo donde la
versión vigente realice normalización.

### 2.7 Sistema `comms` y servicio `radiod`

**Aprobado:** una fase posterior añadirá un sistema físico independiente llamado
`comms`. Sus nombres visibles serán **Communications System** en inglés y
**Sistema de comunicaciones** en español. Su recepción pasiva consumirá
relativamente menos energía que los sensores de exploración, sin fijar todavía
valores de balance, y su modelo admitirá futuros servicios sin rediseñar el
sistema.

`radiod` dependerá directamente de `comms`, no de `sensors`, `sensord`,
`data_core` ni `datad`. Sus nombres visibles serán **Radio Communications
Service** y **Servicio de comunicaciones por radio**. Gestionará recepción y
captura de radio; `radiod` y `sensord` podrán funcionar de forma independiente.
Esta decisión no autoriza transmisión activa, transpondedor ni combate.

`comms` deteriorado podrá conservar capacidades limitadas —por ejemplo menos
alcance, interferencias, recepción intermitente o inestabilidad de `radiod`—,
pero probabilidades, consumo y reinicios automáticos quedan pendientes de
balance. Una incapacidad temporal no consumirá una oportunidad como recibida.

### 2.8 Coherencia de recuperación, no supervivencia

**Aprobado:** los failsafes garantizan la coherencia de las oportunidades que
ellos generan; no garantizan supervivencia, conectividad universal ni capacidad
de reparar la nave. Un bloqueo irreversible causado por decisiones del jugador
puede ser legítimo y acabar en game over. La recuperación no regalará drones,
scrap, energía ni reparaciones.

**Hechos implementados comprobados:** la reparación activa requiere un dron
existente y desplegado, batería mínima, objetivo válido y co-localización; reserva
scrap antes del job. La reparación dron-a-dron prohíbe autorrepararse. El modo
`repair <system_id> --selftest` requiere el unlock `selftest_repair` aportado por
`selftest_rig` y también scrap. `drone deploy! <drone_id>
<sector_id|node_id>` omite ciertos bloqueos de bahía/distribución y está permitido
en estado crítico, pero aún exige un dron acoplado, con integridad mínima y un
destino válido; además usa riesgo de fallo/glitch. No crea recursos ni garantiza
que la reparación posterior sea posible.

## 3. Dependencias actuales de comunicaciones

En la implementación actual, `write_local_intel` escribe directamente un
archivo de acceso `guest`, construye un evento y avanza la secuencia. No valida
sensores, energía, servicios, tránsito o hibernación. Esos requisitos dependen
del llamador. Por tanto, “se creó el archivo” y “la nave podía recibirlo” son hoy
el mismo commit técnico, aunque el contrato aprobado exige separarlos.

| Canal | Activación actual | Recepción actual | Lectura/importación | Si falta un sistema | Falta para entrega diferida fiable |
| --- | --- | --- | --- | --- | --- |
| `captured_signal` | Recuperación global en triggers que no eligen mail/broadcast/uplink; lore push en `dock`, `uplink` o `salvage_data`; deadnodes fuera de `dock`. | El escritor no comprueba receptor. La recuperación global sólo llega a él tras `is_exploration_capable`; lore y deadnodes no aplican esa puerta de canal. | `cat` sobre `/logs/signals/...`; por ser ruta `/logs`, autoimporta intel reconocida. `intel import` también sirve. El archivo es `guest`; no requiere `datad` ni sensores para leerlo. | La recuperación global no se activa sin Core OS nominal, sensores limitados con `sensord`, energía válida y nave fuera de tránsito/hibernación, por lo que puede reintentarse en otro trigger. Lore/deadnodes pueden escribir y consumir estado aunque el receptor equivalente esté apagado. | Registro pendiente persistente con id estable, gate futuro `comms`+`radiod`, commit sólo tras captura y deduplicación entre reintentos. |
| `ship_os_mail` | Recuperación global al terminar hibernación; lore push en `dock`, `uplink` o `salvage_data`. | `write_local_intel`/`deliver_ship_mail` registran el mensaje sin gate de comunicaciones. La recuperación global ya pasó `is_exploration_capable`; lore depende sólo del trigger que lo llamó. | `mail read` delega en `render_cat`; por tanto lee y autoimporta intel de rutas `/mail`. `cat` e `intel import` son equivalentes para la intel. No hay dependencia universal de `datad`. | En recuperación global la oportunidad no se genera si la nave sigue sin capacidad; en lore puede marcarse entregada y crear mail sin comprobar sensores/receptor. | Separar correo interno de comunicaciones externas, estado pendiente/recibido y reintento idempotente; asignar gates sólo después de clasificar el origen. |
| `station_broadcast` | Lore y deadnodes en `dock`; segundo paso de recuperación global al estar en la entrada. | El escritor no valida receptor. Además `_deliver_gateway_broadcast_if_needed` se ejecuta antes de `is_exploration_capable` y al evaluar la llegada, no exige un dock nuevo. Marca `dock_hint_delivered`. | `cat` sobre `/logs/broadcasts/...` autoimporta; también `intel import`. Acceso `guest`. | El broadcast del gateway puede escribirse y quedar marcado incluso con la capacidad global bloqueada. Los broadcasts de lore/deadnodes heredan las condiciones del dock, no un gate de receptor propio. | Aplicar `comms`+`radiod` y cobertura, conservar pendiente hasta recepción y no adelantar triggers de lore que exigen dock. |
| `uplink_trace` | Sólo recuperación global solicitada desde un uplink que alcanzó el umbral de “sin ruta nueva”. | El uplink exige nave acoplada en hub, potencia válida, `data_core >= LIMITED` y `datad` activo; después la recuperación exige además Core OS nominal, sensores/`sensord` y no tránsito/hibernación. El escritor no vuelve a validarlo. | `cat` sobre `/logs/nav/uplink_trace_...` autoimporta; también `intel import`. Leer el archivo ya almacenado no exige `datad`. | Si falla uplink no se llama a recuperación. Si falla capacidad exploratoria, no se activa y un trigger posterior puede reintentar; no existe una cola explícita del intento. | Persistir la oportunidad antes de recibir, registrar el conjunto exacto de requisitos satisfechos y deduplicar reintentos tras save/load. |

### 3.1 Sistemas y estados implicados

`is_exploration_capable` exige: feature flag activo; no tránsito ni hibernación;
sin `terminal_lock` ni brownout; calidad de energía sobre el umbral de bloqueo;
nodo físico actual; `core_os >= NOMINAL`; `sensors >= LIMITED`; y servicio
`sensord` instalado y activo.

El uplink añade su contrato propio: no tránsito/brownout, potencia válida,
`data_core >= LIMITED`, sin shed incompatible, servicio `datad` instalado y
activo, nave acoplada al nodo actual y nodo de tipo relay/station/waystation.
Esto justifica `datad` para `uplink_trace`, no para todos los canales.

El shell bloqueado por `terminal_lock` limita la posibilidad práctica de leer o
importar, pero las funciones de escritura no lo consultan. `cat`, `mail read` e
`intel import` aplican permisos del filesystem; los cuatro canales escriben
archivos `guest`. `mail read` llama a `render_cat`, de modo que sí autoimporta
intel reconocida.

### 3.2 Persistencia y duplicados

Los archivos, metadatos de mail, secuencia de eventos y estados de recuperación
y lore se serializan con la partida. Los llamadores suelen evitar duplicados
mediante flags concretos (`dock_hint_delivered`, pieza en `delivered`, rutas de
hint guardadas), pero no existe una cola común de recepción pendiente ni una
clave idempotente transversal `(oportunidad, etapa, canal)`. Deadnodes avanza
`attempts` y cooldown al escribir; los canales de lore marcan la pieza entregada
después del trigger. Esos commits son los puntos que la implementación futura
deberá posponer cuando no haya recepción válida.

### 3.3 Avisos de servicios detenidos

**Requisito aprobado de interfaz:** al activar un sistema físico, el juego
avisará una sola vez por transición de los servicios instalados que dependan de
él, estén detenidos y puedan arrancarse. El aviso localizado mostrará id,
descripción visible y el comando público real `boot <service_name>`. Distinguirá
servicio detenido, no instalado y bloqueado por avería/dependencias. La relación
se obtendrá dinámicamente de `ShipSystem.service` y `dependencies`, no de listas
duplicadas. Un fallo de acción por servicio ausente o detenido deberá explicar
el servicio requerido y cómo arrancarlo cuando sea posible.

**Situación actual:** `power on <system_id>` es el comando físico canónico
(`system on` es compatibilidad) y `boot <service_name>` arranca daemons. El
modelo sólo admite un `ServiceState` por sistema, las descripciones visibles de
servicios no están centralizadas y `SYSTEM_POWER_RESTORED` no enumera servicios
detenidos. Los mensajes de bloqueo tienen ids/reasons aprovechables, pero no
todos ofrecen una instrucción localizada para `boot`.

### 3.4 Infraestructura de localización observada

El runtime usa `Locale.EN/ES`, diccionarios locales `{"en", "es"}`, pares de
assets `.en.txt`/`.es.txt`, campos como `desc_en`/`desc_es` y fallbacks a inglés.
CLI y Textual comparten gran parte del renderizado, pero todavía existen cadenas
construidas en módulos distintos y no hay un catálogo central que pueda probar
su completitud global.

Controles automáticos existentes:

- `tests/manuals_style_check.py` comprueba parejas EN/ES y estructura para
  comandos, sistemas, conceptos, alertas y módulos diegéticos;
- `tests/hibernate_sequence_assets_smoke.py` comprueba assets EN/ES concretos;
- pruebas focalizadas ejercitan algunos renderers en ambos locales.

Faltan controles generales para: pares de documentación Markdown, todas las
claves/diccionarios de CLI y Textual, metadatos `desc_en`/`desc_es`, referencias
narrativas `content_ref_en`/`content_ref_es` y detección de nuevas cadenas
visibles hardcodeadas en un solo idioma. La regla obligatoria de `AGENTS.md`
cubre ya el proceso; automatizar esos huecos queda para una intervención
separada, sin crear ahora otra infraestructura de localización.

## 4. Cobertura de regresión

### 4.1 Decisiones ya caracterizadas

| Decisión/comportamiento | Cobertura |
| --- | --- |
| Scan materializa y descubre un contacto | `scan_job_smoke.py` |
| Factores de detección por estado de sensores y detección garantizada de la entrada de recuperación | `sensor_detection_factor_smoke.py` |
| `route solve` acepta un id físico exacto no descubierto dentro de sensores/cap y no muta `SpaceNode.links` | `route_solve_out_of_range_origins_smoke.py` |
| Rechazo de salto sobre 45 ly y links worldgen bajo cap | `route_hop_cap_smoke.py` |
| Pool uplink congelado y de un solo uso | `uplink_once_per_node_smoke.py` |
| Cadena actual de recuperación global e importación progresiva | `exploration_recovery_smoke.py` y `uplink_authored_and_failsafe_smoke.py` |
| Preferencia de canal y unlock primary por `uplink_only` válido preexistente | `lore_channel_preference_and_unlock_smoke.py` |
| Integridad, reintento público y persistencia de `uplink_only` | `uplink_only_delivery_retry_smoke.py` |
| Ids `SECTOR` canónicos estrictos, materialización lazy y rechazo localizado sin mutación | `sector_intel_validation_smoke.py` |
| Listado de intel reciente primero, límites, desempate estable y show/export sin cambios | `intel_recent_order_smoke.py` |
| Cooldown deadnode con timestamps cero/positivos, expiración exacta, independencia de candidatos y save/load | `deadnode_cooldown_zero_smoke.py` |
| Persistencia general de mundo/jobs/worldgen | `save_load_smoke.py` |
| Breadcrumb ad hoc con host explícito conocido y no visitado | `forced_hidden_ad_hoc_smoke.py` |
| `secondary.count`, pesos y hard-force sobre contenido sintético | `lore_secondary_count_weights_hard_smoke.py` |
| Debug con cero arcos activos y con arco sintético | `debug_lore_arcs_smoke.py` |

Las fixtures de lore sintéticas no activan arcos template. El caso de pesos
fuerza probabilidad 1 e intervalo 0 dentro de `try/finally`; no representa el
balance real. Las once filas preexistentes pasaron en el árbol de trabajo de
Fase 4C-1 el 2026-11-03; la fila de factores de sensores pasó en el árbol de
trabajo de Fase 4C-2a en la misma fecha.

### 4.2 Casos cubiertos y preparados

Estos casos distinguen los criterios cubiertos de la integración todavía pendiente:

- **IT-01/IT-06:** importar o construir en la versión vigente un LINK
  dangling/sobre-cap; conservar la pista histórica, excluirlo de ruta/frontera
  y demostrar estado estable tras save/load. Incluir una referencia procedural
  válida todavía no materializada. No exige migrar un save de otra versión.
- **IT-09 — cubierto en 4D-2:** abortar en posición interpolada, escanear,
  resolver y viajar a C o a cada extremo; limpiar referencias vivas, conservar
  historial, repetir abortos y guardar/cargar las cinco fases en slots temporales.
- **IT-04/IT-07:** alcanzar deadnode lejano; cada pista sólo se confirma si hay
  un salto válido y la cadena completa termina en el objetivo. Con receptor
  apagado, sin cadena o con target protegido, no avanzan intentos/cooldown. La
  regresión focalizada de timestamp cero ya cubre la persistencia del cooldown,
  pero no este contrato de rutas/receptores.
- **Protección:** arco sintético con primary protegido frente a gateway,
  deadnodes y breadcrumb automático; scan natural y route solve manual conservan
  las excepciones aprobadas.
- **Recepción:** cada canal se prueba con requisitos activos, apagados, reintento
  tras recuperación, save/load entre ambos y ausencia de duplicados.

Los criterios restantes siguen pendientes; IT-05 y la integridad de rutas ya
están implementados y cubiertos sin congelar como deseable ningún defecto anterior.

### 4.3 Aspectos por medir

Antes de cambiar política o balance deben medirse: impacto de pools uplink
congelados tras expansión lazy; oportunidades perdidas entre ciclos; frecuencia
real de los cinco singles; uso de los umbrales `stuck`; alcance del
determinismo frente al orden de generación; frecuencia de rutas obsoletas en
saves; y tasa de receptores/etapas existentes que puede reutilizar el
planificador sin crear nodos nuevos.

### 4.4 Defectos tempranos asignados

| Defecto | Prioridad | Regresión previa a la corrección | Criterio de aceptación | Fase propuesta |
| --- | --- | --- | --- | --- |
| F-ROUTE-01 — integridad de rutas conocidas | **Corregido** | `known_routes_integrity_smoke.py`: diez grupos de selección/publicación, importación EN/ES, componentes, frontera, deadnodes, lazy, viaje/jobs, waypoint inerte y save/load | Sin fronteras fantasma; contactos/historial conservados y ninguna ruta inválida operativa tras save/load | **4D-1 completada** |
| F-NAV-01 — waypoint detenido y limpieza | **Corregido** | `nav_abort_waypoint_cleanup_smoke.py`, seed 314159 | Exploración/navegación normales en T; limpieza dirigida idempotente, historial conservado, abortos repetidos y save/load | **4D-2 completada** |
| `uplink_only` consume primary sin efecto válido | **Corregido** | Casos sintéticos malformed, extremo ausente, sobre-cap, LINK nuevo válido y LINK válido preexistente | Sólo nuevo/preexistente válido marca `delivered` y desbloquea; los fallos quedan pendientes y reintentables | **4C-1 completada** |
| Sensores `UPGRADED` caían al factor `CRITICAL` | **Corregido** | `sensor_detection_factor_smoke.py`: matriz determinista de factor/detección para cada `SystemState` | `UPGRADED` usa el factor nominal; los demás estados, alcance, energía y duración no cambian | **4C-2a completada** |
| `SECTOR` malformado materializa origen | **Corregido** | `sector_intel_validation_smoke.py`: ids canónicos existentes/lazy/amplios y formatos inválidos mediante importaciones públicas | Rechazo localizado sin mutación; formatos canónicos siguen materializando | **4C-2b completada** |
| `intel N` devuelve los más antiguos | **Corregido** | `intel_recent_order_smoke.py`: historiales vacío/único/amplio, límites, empates de timestamp, EN/ES, CLI/Textual, show/export y estado de sólo lectura | Muestra los N más recientes en orden estable y conserva `intel show/export` | **4C-2c completada** |
| Cooldown deadnode se omite en `t=0` | **Corregido** | `deadnode_cooldown_zero_smoke.py`: timestamps cero/positivos, evaluaciones inmediata/anterior al límite/en el límite, candidatos independientes y save/load | `attempts > 0` identifica una acción previa; cero sigue siendo timestamp persistente válido y las evaluaciones bloqueadas no mutan efectos | **4C-2d completada** |
| `modules_pool` regional trataba categorías como ids | **Corregido** | `worldgen_modules_pool_smoke.py`: loader real, seeds 1/2, selección y clusters disk/bulge/halo, ceros legítimos, filtros vacíos/desconocidos, save/load y salvage normal | Categorías del campo `pool` filtran ids reales; conteos, orden de candidatos, repetición y RNG preservados; determinismo con igual secuencia y estado authored/ajeno íntegro | **4C-3 completada** |

Frecuencia de singles, snapshots uplink, `radiation_base`, dependencia del orden
de worldgen y balance general permanecen en estudios independientes.

No había un multiplicador de detección `UPGRADED` separado, configurado ni
aprobado. La Fase 4C-2a usa por tanto de forma conservadora
`SENSORS_DETECT_P_NOMINAL` (1.00); decidir si la mejora merece una bonificación
mayor sigue siendo trabajo de balance y no parte de esta corrección.

## 5. Plan de implementación posterior

Cada intervención requiere su propio cambio, documentación y autorización. El
orden evita que recuperación o lore vuelvan a inventar validadores paralelos.

| Intervención | Cambio y decisión que lo justifica | Módulos a revisar | Riesgos | Pruebas y save/load | Decisiones adicionales posibles |
| --- | --- | --- | --- | --- | --- |
| 0. Integridad `uplink_only` — implementada | No consumir un primary irrepetible sin efecto; distinguir éxito, fallo y retry. | `core/lore.py`, `cli/repl.py` y estado de entrega. | Doble unlock, reintentos duplicados o cambio accidental de singles. | Matriz 4C-1; save/load con pieza pendiente y entregada dentro de la versión vigente. | Cerrada: reintento narrativo separado del pool de rutas one-shot. |
| 1. Integridad de rutas e intel | Separar pista/contacto/ruta operativa; excluir dangling y sobre-cap; limpiar referencias de waypoint. | `model/world.py`, `core/engine.py`, `cli/repl.py`, consumidores de `known_links`. | Borrar conocimiento histórico, invalidar referencias procedurales lazy o cambiar UI. | IT-01, IT-06, IT-09, cap y route solve; estado vigente inválido → saneado estable → save/load. | Representación visible de una pista no verificable y protocolo para materializar ids procedurales. |
| 2. Integridad de saves vigentes | Versionar/rechazar explícitamente formatos incompatibles y preservar invariantes dentro de la versión, sin migraciones históricas prealfa. | `io/save_load.py`, modelo/versionado y validadores compartidos. | Aceptar corrupción o borrar/reemplazar datos del usuario. | Save/load vigente, backup/checksum, rechazo de versión incompatible y confirmación de que no se borra el archivo. | Revisar la política antes de alfa/beta pública. |
| 3. Planificador de cadenas | Calcular todos los saltos antes de publicar; preferir nodos existentes no visitados y crear sólo los necesarios. | `core/deadnodes.py`, `core/exploration_recovery.py`, worldgen/modelo de topología y pools. | Revelar contenido, crear islas tardías, usar nodos visitados o alterar determinismo. | IT-04/07 con objetivos cercanos/lejanos, sectores lazy, sin solución y protección; save/load a mitad de cadena. | Topología/pool de nodos nuevos y límite de etapas, sin tocar aún umbrales. |
| 4. Entrega progresiva persistente | Persistir oportunidad y etapa antes de emisión; revelar una etapa por vez con clave idempotente. | Estados de recovery/deadnodes/lore, `write_local_intel`, save/load. | Duplicados, pérdida al actualizar, pistas atascadas. | Reintentos repetidos, save antes/después de captura, cambio de trigger/canal y dedup. | Esquema/versionado de la cola y política de expiración, si existe. |
| 5. `comms`, `radiod` y recepción | Añadir sistema/servicio localizados; aplicar gates a señal/broadcast y no marcar entrega con receptor apagado; mantener `datad` específico de uplink. | Bootstrap/modelo de sistemas, energía, engine/repl, canales y ayuda/manuales EN/ES. | Bloquear contenido actual, dependencia circular, strings sin localizar o balance prematuro. | Estados `comms` × `radiod`, cobertura física, reintento/save-load/dedup y `manuals_style_check`. | Penalizaciones exactas de deterioro y consumo; no transmisión activa. |
| 6. Protección narrativa y receptores | Excluir primaries protegidos de automatismos, sin bloquear scan/route solve manual; distinguir receptor procedural obligatorio. | `core/lore.py`, recovery, deadnodes y locks/placements. | Primary imposible o bypass accidental. | Arcos sintéticos por canal, protected target, ad hoc forzado con/sin host; persistir lock y unlock. | Etiqueta o consulta canónica de protección; política sin host elegible. |
| 7. Integración, avisos y localización | Probar recorrido completo, avisos dinámicos de servicios y todo texto observable en EN/ES. | Tests, docs, manuales, ayuda y módulos tocados en 0–6. | Suite verde sin decisiones del jugador; divergencia CLI/Textual o traducciones incompletas. | IT-01–IT-10, suite completa, locales EN/ES, enlaces, manuales y saves en cada frontera. | Métricas de éxito, frecuencia aceptable y cualquier rebalanceo posterior. |

### Primera intervención correctiva completada: Fase 4C-1

`LoreDelivery.applied` distingue intento y efecto. Un LINK malformado, con un
extremo físico ausente o sobre cap conserva asignación, canal y pendiente; uno
nuevo o preexistente válido se registra y desbloquea una sola vez. Tras consumir
el pool de rutas, otro comando `uplink` sólo reevalúa `uplink_only` pendiente:
no repite rutas, logs, recompensas, recovery ni contadores. La fixture cubre los
cinco casos, fallo reiterado, cambio posterior de condiciones, save/load antes y
después del éxito y ausencia de duplicados. No se activaron templates ni se
cambiaron singles, UI o balance.

### Corrección estricta de ids de sector completada: Fase 4C-2b

El parser anterior descartaba el primer carácter, pasaba los tres componentes
restantes a `int()` y devolvía `(0, 0, 0)` ante cualquier error. Por ello, una
línea pública `SECTOR:` inválida podía generar el clúster del origen y registrar
después el literal inválido como intel de sector. El parser canónico exige ahora
una `S` mayúscula y tres componentes decimales con signo separados por guiones
bajos, cada uno igual a su representación `{value:+04d}`. La anchura puede
ampliarse más allá de cuatro caracteres. `ensure_sector_generated` valida antes
de mutar; ambas vías públicas de importación comparten el rechazo localizado y
continúan con las demás líneas válidas. Las importaciones válidas conservan
generación lazy, determinismo y contactos del sector ocultos. Un bloque que sólo
contiene líneas `SECTOR:` explícitas se delega directamente a ese parser de
líneas, por lo que no consume RNG ni entra en recuperación corrupta. Los bloques
que mezclan directivas explícitas con texto narrativo desconocido conservan su
semántica general anterior.

### Corrección del listado de intel reciente completada: Fase 4C-2c

El renderer del listado ordenaba antes por timestamp ascendente y después
recortaba desde el principio, contradiciendo el contrato público “latest”. Ahora
ordena una vista temporal indexada por `(timestamp, índice_de_inserción)`
descendente antes de aplicar el límite 20 por defecto o el N explícito. Por ello
`intel`, `intel N` e `intel all` muestran primero lo más reciente, y a igualdad
de timestamp gana el registro añadido después sin usar ids textuales como
cronología. El historial almacenado no cambia; `intel show` e `intel export`
conservan su búsqueda y orden de exportación anteriores, y Textual hereda el
mismo renderer.

### Corrección del cooldown deadnode en tiempo cero completada: Fase 4C-2d

`last_action_t == 0` significaba antes tanto «sin acción previa» como «la acción
previa ocurrió en tiempo cero», por lo que el segundo caso eludía el cooldown de
cinco años. `attempts` ya registra cada pista deadnode escrita con éxito y no
tiene otro escritor, así que `attempts > 0` identifica ahora la acción previa sin
cambiar el esquema. `last_action_t` queda como timestamp persistente ordinario,
incluido cero. La regresión focalizada demuestra ausencia de mutación antes de
vencer, nueva acción exactamente en el límite, independencia entre candidatos,
comportamiento positivo sin cambios y la misma semántica tras save/load. No
resuelve la validez de rutas deadnode ni la topología del puente (F-DEAD-01).

### Corrección de categorías regionales completada: Fase 4C-3

F-WGEN-01 se reprodujo antes de corregir tanto en la selección compuesta como
en la generación real. El inventario confirmó metadatos `pool` suficientes sin
listas de ids explícitos utilizadas. Sólo cambió `_pick_modules` procedural;
se conservan authored, conteos/ceros, repetición, orden y llamadas RNG.
`worldgen_modules_pool_smoke.py` cubre seeds `1`/`2`, clusters regionales,
determinismo con igual secuencia, save/load temporal y recuperación normal de
un módulo con D1, incluida la persistencia de cargo y depleción. El
[inventario y las seeds](../systems/world-generation.es.md#categorías-regionales-de-módulos-f-wgen-01-corregido-en-4c-3)
quedan en la referencia canónica de worldgen. No se cambiaron datos ni balance.

### Integridad de rutas conocidas completada: Fase 4D-1

`known_routes_integrity_smoke.py` reprodujo nueve grupos de aserciones fallidas
antes de modificar producción y ahora pasa sus diez grupos con seed `271828`.
El criterio compartido exige extremos físicos y cap inclusivo; publicación,
componentes, fronteras, candidatos deadnode, vistas y compleción lo reutilizan.
Importar conserva contactos y registros históricos de pistas no verificables.
La proyección de sólo lectura deja inertes los registros inválidos persistidos
sin podar referencias pendientes, mutar el mundo ni materializar al cargar.
SECTOR lazy y el helper existente de prefijos siguen ejecutándose antes de
validar; no se inventan alias de ids. Save/load repetido e incompatibles están
cubiertos con directorios temporales. El
[inventario canónico](../systems/discovery-navigation-intel.es.md#rutas-operativas-y-pistas-históricas-4d-1)
detalla cada consumidor. F-NAV-01 quedó corregido después en 4D-2; F-DEAD-01 sigue pendiente.

## 6. Riesgos y límites vigentes

- Desde 4D-1, `is_hop_within_cap` rechaza extremos ausentes. Los productores
  y consumidores operativos comparten el criterio sin destruir historial.
- `SECTOR` ya tiene un formato canónico estricto y rechaza referencias
  malformadas. El contrato más amplio de rutas/nodos aún no puede validar
  referencias procedurales sólo buscándolas en `space.nodes`; sigue siendo
  trabajo independiente.
- Preparar pistas antes de una visita exige una operación coherente entre
  planificador, pool y persistencia; escribir primero y completar después puede
  dejar etapas parcialmente visibles.
- `comms` y `radiod` están aprobados, pero faltan un catálogo localizado de
  nombres/descripciones, soporte de dependencias de servicio escalable, estado
  pendiente idempotente y eventos de transición no repetitivos. No deben
  modelarse con listas duplicadas.
- Las categorías de `modules_pool` ya filtran el campo real `pool` del catálogo
  desde 4C-3. Siguen abiertos `radiation_base`, independencia del orden de
  generación, frecuencia de singles, política final de pools uplink y balance.

## 7. Resultado de esta fase

El contrato incorpora las decisiones de Fase 4B y registra 4C-1 como primera
corrección productiva completada. `uplink_only` ya no consume piezas sin efecto
y dispone de reintento público compatible con el pool one-shot. La matriz
registra también 4C-2a/b/c/d, 4C-3 y 4D-1/2 como completadas; F-WGEN-01 ya respeta
las categorías regionales. Las demás intervenciones, comunicaciones y defectos
permanecen pendientes.

### Fase 4D-2: waypoints detenidos y F-NAV-01

`nav_abort_waypoint_cleanup_smoke.py` fija el contrato con seed `314159`:
abortar conserva coordenadas interpoladas y detiene la nave; scan usa T como
origen sin unlock de tránsito; route solve y viaje real admiten C o los extremos
anteriores con gates normales y cap inclusivo de 45 ly. La limpieza es dirigida
e idempotente, conserva rutas permanentes, contactos e intel histórica. Los
abortos repetidos reemplazan el waypoint anterior sin origen operativo inválido;
sus jobs scan/solve pendientes se cancelan con el finalizador existente.
Tres ciclos temporales de save/load cubren cada una de cinco fases del viaje.
El [cierre de auditoría](../testing/stabilization-audit.es.md#fase-4d-2-waypoints-detenidos-y-f-nav-01)
registra pruebas rojas, coordenadas y validación completa. F-DEAD-01 sigue abierto.
