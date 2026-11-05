# Comunicaciones pasivas — 4D-3e4b

[English](passive-communications.md). Implementación para revisión externa sobre
`78676dbfce5e7b98db36b2e241a427a19b0632fe`, 2026-11-06.
No implementa F-DEAD-01 ni comunicaciones interestelares generales.

## Sistema y servicio

`comms` — **Sistema de comunicaciones / Communications System** — es un
`ShipSystem` ordinario en `BRG-01`, una estancia existente. Empieza instalado,
`OFFLINE`, `forced_offline=True`, salud 0.90. Necesita
`energy_distribution >= NOMINAL` alimentado. No depende de sensores ni datos.
Se enciende, apaga, deteriora, repara y persiste con los mecanismos existentes.
Encenderlo o repararlo no arranca su servicio automáticamente.

Consumo nominal provisional: **0.15 kW**, frente a 0.7 kW de sensores. Usa los
multiplicadores normales por estado: LIMITED 0.12, NOMINAL 0.15, UPGRADED
0.165 kW. En CRUISE conserva esa carga completa si está encendido. No se modifica
la carga de otros sistemas. Prioridad 4; deterioro base `8.5e-11/s`, `k_power=0.30`,
`k_rad=0.10`, reutilizados de data_core. Su política de desgaste incluye los
factores globales existentes; estar apagado no detiene el envejecimiento.
Estos parámetros conservadores quedan sujetos a revisión de balance.

`radiod` — **Servicio de comunicaciones por radio / Radio Communications Service** —
es el `ServiceState` de comms. Instalado y detenido al comenzar; boot de 5 s
mediante `BOOT_SERVICE`. `requires_active_owner=True` exige propietario al menos
LIMITED. El boot revalida instalación, propietario, dependencias y potencia
durante el trabajo y al aplicar el resultado. Apagar el propietario detiene su
servicio. Cancelación y fallo usan los finalizadores ordinarios; no hay otro
gestor de daemons ni reinicio automático. Se conserva la activación legacy de
sensores inicialmente OFFLINE sin apagado forzado al arrancar sensord; radiod
exige primero `power on comms`.

## Capacidad y canales

`radio_block_reason` comprueba comms existente, no apagado/shed, estado LIMITED,
NOMINAL o UPGRADED y salud coherente; dependencias de alimentación; Core OS al
menos LIMITED, terminal disponible, Q >= 0.55 y ausencia de brownout. Reutiliza
los kernels eléctricos del motor para comprobar generación + descarga disponible
frente a carga actual, incluso entre ticks. Suspende recepción en tránsito o
hibernación. Exige radiod instalado y activo. No tira RNG ni consulta sensores/datad.

| Canal | Contrato efectivo |
| --- | --- |
| `captured_signal` | Radio y oportunidad local nacida de su trigger real. |
| `station_broadcast` | Radio, fuente física local station/relay/waystation y contexto autorizado. |
| `ship_os_mail` interno | Mantiene entrega interna sin radio. No se infiere origen externo a partir de prosa o nombres de remitentes. |
| Mail explícitamente externo | `mail_origin: "external"` en la pieza, o `external_origin=True` / SourceRef `kind="external"` en la API local, pasa por la misma recepción de radio; conserva canal y envoltura mail. No hay piezas activas con esos marcadores en esta base. |
| `salvage_data` | Pool, dron y recuperación existentes; sin radiod. |
| `uplink_trace` | Uplink local válido, data_core/datad instalado y activo; sin radio. |
| `uplink_only` | Requisitos actuales de uplink y validación del LINK; sin radio. |

No cambian triggers, pesos, sorteos, force ni deadlines. Los contadores de acciones
dock/uplink/salvage conservan sus contratos; un reintento automático no los incrementa.
`signal_count` conserva su significado de señales efectivamente recibidas de lore;
las pistas legacy no adquieren un nuevo incremento que alterase deadlines.

## Oportunidad, captura y lectura

Una sola colección `WorldState.radio_opportunities` contiene `RadioOpportunity`
para lore, API local y etapas legacy ya preparadas. Identidad de lore:
`lore:<piece_key>`; gateway: `recovery:<generation>:gateway`; deadnode:
`deadnode:<target>:<attempt>`. La API admite ID explícito; su fallback deriva de
canal, fuente, host y contenido, sin RNG.

Se congelan contenido EN/ES, fuente, host, trigger, exigencia de dock, metadatos de
commit y tiempo de preparación. Una API legacy que solo aporta un idioma conserva ese texto
como fallback en ambos sentidos al cambiar EN/ES. Se persisten estado, path, idioma y tiempo de
captura, y tiempo de lectura. Estados:

1. `pending`: no archivo, evento de éxito, intel, unlock ni consumo de pieza.
2. `received`: archivo GUEST real y un único evento SIGNAL_CAPTURED,
   BROADCAST_RECEIVED o MAIL_RECEIVED. Solo aquí se confirman ledger de lore,
   pool, signal_count correspondiente, flags/cooldowns de la etapa productora.
3. `read_imported`: `cat`, `mail read` (delega en cat) o `intel import` accedieron
   al archivo. El parser existente aplica la intel que sea válida; el nombre del
   estado no garantiza que hubiese intel útil ni que se desbloquease un primary.

Un primary de archivo sigue protegido hasta su lectura/importación válida. La
consulta de pendientes muestra únicamente cantidad y causas genéricas, nunca
texto, fuente secreta, IDs de objetivos, rutas o coordenadas. No importa intel.

El escritor común conserva los eventos y directorios existentes. La captura y
su bookkeeping son una operación síncrona en memoria bajo el modelo de ejecución
actual; no hay callback diferido ni segundo guardado intermedio. Repetir el mismo
ID después de capturarlo no escribe ni emite otra vez. El borrado manual de un
archivo recibido no recrea una oportunidad consumida.

## Reintentos y cobertura

El tick reintenta pendientes al final de energía, deterioro y consecuencias del
motor. Un productor puede intentar capturar inmediatamente tras preparar. Siempre
se revalida capacidad y fuente. Debe seguir existiendo el host físico y ser el
nodo actual; no puede ser un waypoint de tránsito. Las oportunidades nacidas de
dock/uplink/salvage de lore conservan la exigencia de dock en ese host. Visitar
una región cercana o encender radiod no crea un trigger de lore ni adelanta dock.

La oportunidad local ya preparada se conserva para la siguiente disponibilidad
del receptor en ese mismo contexto; viajar suspende su elegibilidad y volver
permite reintentar. No se postula un emisor nuevo ni una propagación galáctica.
El modelo actual no tiene evolución independiente de energía del emisor ni
caducidad electromagnética: existencia/kind del host y contexto local son la
prueba conservadora disponible. Alcance reducido, latencia, interferencias,
intermitencia y ventanas temporales de emisión quedan por diseñar/balancear.

El gateway de una cadena legacy existente admite presencia local al llegar,
sin exigir dock nuevo. Su generación, entrada, gateway y protección primaria se
revalidan antes de capturar. Los reintentos deadnode conservan intento y origen;
no consumen cooldown hasta recibir y no publican enlaces por sí mismos.

## Recuperación estructural pendiente

La activación global legacy crea entrada/gateway antes de poder preparar la
pista. El primer intento indirecto deadnode también fabrica un puente. Conforme
a la autorización de esta fase, esas activaciones se aplazan explícitamente
(`recovery_activation_deferred`) sin crear nodos, entregar pistas, incrementar
éxitos ni confirmar cooldown. Un LINK legacy sobre cap o a un primary protegido
tampoco se transmite. Los trackers pueden seguir observando umbrales, sin contar
una entrega. Las etapas con puente ya existente bajo cap y los broadcasts de
cadenas existentes sí usan el ledger común. No se reemplaza el selector ni se
modifican thresholds/cooldowns; su integración estructural sigue siendo e5.
El aplazamiento puede dejar un bloqueo estructural sin recuperación automática
hasta e5; esta fase no promete que cualquier mapa tenga salida.

## Persistencia y operación pública

Se mantiene contenedor V2/esquema 3 y la validación de universo/catálogo e4.
WorldState añade campos con defaults al deserializar. Un esquema 3 anterior sin
comms recibe el mismo sistema apagado de bootstrap, sin recursos adicionales,
reparaciones, activación, cambios de física histórica ni intel. ServiceState
restaura el nuevo flag con default false en servicios antiguos. No se reescribe
el archivo ni backup al cargar. No hay migración de geografía ni de contenido.

```text
diag comms
power on comms
boot radiod
jobs
diag comms
cat /logs/signals/<archivo_recibido>
power off comms
```

Si falla alimentación, reparar primero energy_distribution. Si comms está por
debajo de LIMITED, repararlo con el dron ordinario en BRG-01. `about comms` y
`man boot` explican la operación. Al activar un sistema o recuperar su umbral
útil, el motor recorre propietarios/dependencias reales y avisa una vez de
servicios detenidos (`boot <id>`), no instalados o bloqueados (`diag <owner>`),
con nombre EN/ES. No mantiene una lista paralela de asociaciones de daemons.

CLI y Textual comparten renderers, mensajes y diagnóstico; el adaptador de status
añade las mismas líneas sin panel nuevo. Se conservan tipos de evento y audio.

Código: [communications.py](../../src/retorno/core/communications.py),
[lore.py](../../src/retorno/core/lore.py), [engine.py](../../src/retorno/core/engine.py),
[model/world.py](../../src/retorno/model/world.py). Pruebas:
[passive_communications_smoke.py](../../tests/passive_communications_smoke.py),
[informe de revisión](../testing/passive-communications-review.es.md).
