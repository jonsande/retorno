# RETORNO — Informe técnico 4D-3e5b

Fecha: 2026-11-06. Estado: implementada y detenida para revisión externa.
[English](radio-spacetime-review.md). [Contrato físico](../systems/radio-spacetime.es.md).
[Evidencia completa JSON](radio-spacetime-results.json).

## Corrección final — persistencia de invalidaciones

Entrega vigente: **46 archivos íntegros**, los 45 anteriores más
`tests/recovery_invalidation_smoke.py`. **La invalidación legítima ya permite
guardar y cargar sin pérdida de progreso.** HEAD permanece en
`4c4318502e83de9fae66be78f0baeb882c7d69d8`, main → origin/main, sin stage/commit/push.

### Reproducción y diagnóstico

Antes de modificar el núcleo se extendió el caso 12 de procedencia: carga del slot
real v1, captura única, lectura/importación de A → B, llegada a B y avance a la
segunda etapa. El plan quedó `invalid`, stage=1, captured=consumed=(0,), con una
sola oportunidad y sin fabricar transmisión. `save_single_slot()` falló con
`SaveLoadError (... Recovery stage ledger mismatch)`: la validación exigía la
oportunidad que `_radio_stage()` precisamente había rechazado crear.
El traceback completo anterior al cambio se conserva en el JSON.

Se reprodujeron por separado los otros dos supuestos usando el módulo del ZIP
anterior de 45 archivos, intacto, en un proceso aislado. Retirar controladamente
la emisión futura B → C tras confirmar/capturar/importar A → B invalidaba v2 en
stage=0; guardar fallaba con `Recovery declared stage emission unavailable`.
Recibir B → C pasivamente antes de activar su etapa generaba una recepción real,
pero el avance la trataba como colisión: invalid, stage=1, dos oportunidades,
y guardar fallaba con `Recovery stage ledger mismatch`. Ninguno creaba un slot.
El script y su salida se incluyen completos en el JSON; el ZIP anterior conserva
SHA-256 `c11b4e57d6f09a404a8bd00f4043dbd0cde65300c7d087d9879dc6712c8c6e84`.

### Validación corregida y continuidad

Solo cambia el núcleo `src/retorno/core/structural_recovery.py`. Reutiliza la
validación existente: contrato confirmado `source_contract`, comprobación explícita
de progreso y `invalidation=(motivo, huella)`, emitida por el motor tras validar
integridad física, propuesta, versión y ledger anterior. Son huellas de coherencia,
no firmas. No basta cambiar `status` a `invalid`; una propuesta adulterada tampoco
obtiene una constancia válida pasando por el avance del motor.

| Estado | Obligaciones al guardar/cargar |
| --- | --- |
| Activo | Fuentes válidas y todas las oportunidades ya preparadas; progreso coherente. |
| Completo | Todas las etapas consumidas, contrato y ledger íntegros. |
| Invalidado legítimamente | Constancia ligada a contrato/progreso; ledger anterior obligatorio; no exige disponibilidad futura ni la oportunidad actual nunca preparada. |
| Adulterado/incompatible | Rechazo sin borrar ni reescribir el slot: versión, certificados, propuesta, progreso, constancia o ledger incoherentes. |

Los campos son aditivos para schema 3: se cargan la fixture real v1 y slots v2
activos con la forma anterior. v1 sigue consumiendo únicamente oportunidades ya
preparadas; no cambia su significado ni se inventan emisores. Los roundtrips
comparan mundo, nave, OS, reloj y meta completos: rutas, intel, archivos, recursos,
recepciones, intentos y cooldowns se conservan. La escucha ordinaria puede mover
su cursor técnico al cambiar de ubicación; no se confunde con progreso o cooldown.
El plan sigue fuera de ACTIVE, no avanza ni duplica su primera recepción. Una
búsqueda posterior del mismo bloqueo puede confirmar una nueva primera fuente
legítima en B; la recepción antigua de A no se recicla. Probado en global y deadnode.

El defecto de recepción anticipada sí se reprodujo, por lo que se corrige de forma
local: la etapa v2 reutiliza el registro canónico recibido/importado, con emisión,
emisor, contenido y LINK exactos. No vuelve a capturar, generar eventos, incrementar
intentos/cooldowns ni escribir otro archivo. Una recepción sin leer sigue
requiriendo lectura/importación; si el LINK ya se importó, la etapa se consume al
llegar a ella. Ambos casos pueden guardarse/cargarse y completar la cadena.

Límite explícito: las emisiones admitidas por recuperación son continuas sin final;
no se añade apagado dinámico de fuentes. La retirada de una fuente futura es una
alteración controlada de fixture recompilada con el compilador existente, no un
cambio de autoría, scheduler o worldgen. Borrar una declaración que respalda una
recepción ya persistida sigue siendo una incompatibilidad del ledger de radio,
no una invalidación legítima que deba aceptarse. Tampoco se reparan automáticamente
guardados inválidos sin constancia; la entrega anterior no permitía producir el
slot inválido de esta reproducción mediante la API productiva.

### Verificación final y entrega

**68/69 scripts PASS**, con el mismo único fallo histórico de `CARNAVAL_34` en
`radiation_hull_smoke.py:183`. Su log es idéntico byte a byte al anterior y a la
base: SHA-256 `e54ccf0ca0e8da2081a1c8a338d71c8489f84a37c99f4a9c7eb9946dc582195b`.
Pasan **8 grupos nuevos** de invalidación, **18** de procedencia (caso 12 ampliado),
**43** espaciales, **36** estructurales, **19** de conocimiento, **20** narrativos,
**18** de radio anterior, persistencia general, CLI/Textual/audio y manuales.
Tras completar los diagnósticos bilingües y ampliar la comprobación deadnode se
repitieron los 8+18 grupos focales: PASS. Comandos, tiempos, códigos y logs están
en el JSON. Manuales EN/ES revisados: no necesitan instrucciones nuevas porque
se restaura el guardado estándar sin exponer planes internos; checker PASS.
Contratos técnicos y diagnóstico actualizados en ambos idiomas.

No cambian potencias, alcances, propagación, emisores/emisiones de producción,
contrato de autoría, worldgen, scheduler, navegación, protección de primaries,
información procedural, recursos/supervivencia, CLI/Textual/audio ni AMANECER.
Todos los demás módulos fuente del ZIP anterior son idénticos byte a byte.
`git diff --check` y comprobación de índice vacío: PASS.

ZIP vigente: `deliverables/retorno-4D-3e5b-final.zip`, con manifiesto íntegro de
46 archivos y SHA-256 externos para evitar circularidad. Se conservan los ZIP
anteriores. Detenido para revisión externa; no se hace staging, commit ni push.

## Corrección focal incorporada — procedencia de todas las pistas F-DEAD-01

Esta sección conserva la corrección de procedencia anterior al ajuste final; corrige la excepción local de la primera
entrega e5b. Se conservan sus 40 archivos y todo el trabajo acumulado. Aquella entrega
corregida comprendía **45 archivos**, sin stage/commit/push; HEAD sigue en
`4c4318502e83de9fae66be78f0baeb882c7d69d8`, main → origin/main.

### Reproducción anterior al cambio

Antes de modificar el comportamiento se ejecutó el selector de la entrega original
sobre su escena certificada A → B. Resultado: validated, first_emission_id=None,
ningún radio_emitter declarado, y confirmación creó un broadcast LINK: A -> B.
En A → B → C, llegar al relé B creó LINK: B -> C con emission=None. Con B de tipo
ship, confirmar inyectó un archivo de salvamento calculado entonces. Los tres
testigos y sus payloads exactos se conservan en el JSON del informe.

Se generó y guardó un slot real con el código anterior, antes de la corrección:
`tests/fixtures/recovery_legacy/pending-v1.dat`, SHA-256 `384481e72ef383dcf4c4a1966d2dcceccbf824cd17e63020df58aecd074a0612`.
Su primer mensaje ya preparado se carga/captura una vez; su segunda etapa aún no
preparada ya no puede fabricar radio. El original no se reescribe.

### Corrección y evidencia por etapa

Los planes nuevos son historical-recovery-v2. RecoveryProposal.stage_sources guarda
una StageSource por etapa informativa: referencia estable y SHA-256 del contenido.
first_emission_id siempre identifica la emisión de la primera pista, incluso local.
La identidad del plan incluye estas fuentes para no confundir reintentos con
declaraciones diferentes. _source/_edge_source ya no convierten un kind en radio.

La selección solo usa emisiones instaladas con navigation_link_to exacto,
station_broadcast, repetición continua sin final y sin pieza narrativa pendiente
de scheduler. Primera recepción: cobertura y llegada en la posición de la nave.
Etapas posteriores: fuente certificada y emisión ya disponible en su propio host;
la repetición abierta permite esperar a la visita sin inventar historia futura.
La evidencia acompaña el camino elegido, sin mezclarse entre orígenes del buscador.
Confirmación revalida fuentes/cobertura/tiempo antes de publicar; cada captura
revalida el contenido y sus gates actuales. _radio_stage copia el payload declarado,
con su identidad radio:<id>, sin construir una pista de sustitución.

Las etapas de salvage solo usan archivos existentes en pools o declarados authored
que ya contengan el LINK requerido. Se fija ruta y huella y se respeta la precedencia
de archivos base sobre inyectados al montar. Confirmar ya no inicializa pools para
inyectar pistas ni crea archivos. Rutas conocidas conservan su mecanismo dirigido.
Ventanas cerradas/limpias o fuentes ya inspeccionadas no reciben contenido nuevo.
La fuente legítima reservada antes de visitar puede consumirse después sin reabrirla.

| Fuente | Plan nuevo | Compatibilidad o condición |
| --- | --- | --- |
| Estación/relé sin equipo declarado | No | El tipo físico no prueba transmisión. |
| Equipo con emissions vacío | No | Equipo no equivale a actividad. |
| Emisión con otro destino/contenido | No | No se sustituye su payload por una pista calculada. |
| Emisión local continua histórica con LINK exacto | Sí | Certificado, cobertura, llegada y gates efectivos. |
| Emisión remota equivalente | Sí | Misma frontera espacial/temporal de e5b. |
| Emisión aún no llegada o ventana pasada | No | No existe recepción legítima actual. |
| Etapa intermedia sin fuente | No | Cadena incompleta, no se confirma plan. |
| Archivo existente con LINK exacto | Sí, como etapa salvage | Fuente elegible, ruta montable y huella verificable; sin inyección. |
| Ruta dirigida operativa conocida | Sí, como etapa de ruta | No genera mensajes/archivos. |
| Oportunidad legacy v1 ya persistida | Se conserva | Recepción local original, sin inventar metadatos de emisor. |
| Interacción narrativa legacy autorizada | Se conserva | Mantiene triggers y gates existentes; no es un plan nuevo. |
| Etapa de radio v1 todavía no preparada | No se crea | La continuación se marca inválida; permite evaluar alternativas. |

Sin cadena completa, conditional/incomplete no confirma plan, consume intentos o
cooldowns ni revela candidatos. Los reintentos siguen ampliándose y reaccionan a
cambios de posición/tiempo/conocimiento. Como el contenido instalado no contiene
un catálogo de transmisiones históricas para todos los bloqueos, puede faltar una
recuperación legítima. No se añadió ese catálogo ni emisores procedurales para
salvar tests; su posible necesidad se documenta para e5c y una decisión explícita.

### Validación y límites de la corrección

**18 grupos focales** nuevos en tests/recovery_provenance_smoke.py: ausencia de
equipo/actividad, contenido ajeno, local/remoto válidos, llegada/ventana, todas las
etapas, fuente intermedia ausente, salvage existente, no consumo/revelación,
slot v1 real, save/load v2, primaries, CLI/Textual/debug puro y rechazo de propuestas
sin evidencia. Incluyen colisiones de archivos montables y lectura de otro archivo
mientras una etapa de ruta ya fue consumida. Los 36 grupos estructurales se
mantienen: sus éxitos declaran explícitamente emisiones/archivos en el montaje de
escenas antes de buscar. No se infieren transmisores procedurales por kind.
El test 26 espacial ahora exige fixture-history también al llegar a su host.

Pasan 43 grupos espaciales, 36 estructurales, 19 de conocimiento, 20 narrativos y
18 de comunicaciones previas. Regresión de aquella entrega: **67/68 PASS**; solo permanece
radiation_hull_smoke.py:183, CARNAVAL_34, log idéntico a las dos referencias anteriores.
Manuales EN/ES y git diff --check correctos. Fórmulas, perfiles, potencia/sensibilidad,
propagación, comms/radiod, energía, navegación, topología, densidad, probabilidades,
supervivencia, protección, conocimiento, Textual/audio y AMANECER no cambian.

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/recovery_provenance_smoke.py
/home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_validation.py /tmp/retorno-radio-correction-release
```

ZIP acumulado: deliverables/retorno-4D-3e5b-corrected.zip, con SHA-256 y manifiesto
adjuntos. Incluye los 45 archivos íntegros. El ZIP anterior se conserva
sin alteraciones (`c0270639b2aba5f3cf39cf81786397021994515739aeb35e9af733b4674f0ba4`). Detenido para revisión externa.

## 1. Referencia y estado Git

- HEAD inicial y final: `4c4318502e83de9fae66be78f0baeb882c7d69d8`.
- Rama `main`; upstream `origin/main`. El árbol estaba limpio al iniciar e5b;
  la corrección focal partió de sus 40 archivos modificados/nuevos sin publicar.
- Entrega con 46 archivos modificados/nuevos, todos sin stage. No se
  ejecutaron git add, commit ni push; HEAD permanece en la referencia aprobada.
- El ZIP se entrega fuera del repositorio como `deliverables/retorno-4D-3e5b-final.zip`,
  con rutas relativas del repositorio, manifiesto por archivo y SHA-256 adjuntos.
  Incluye íntegros los 46 archivos, con comprobación CRC y comparación de bytes.

## 2. Auditoría inicial y reutilización

Se leyeron AGENTS, canon/coherencia, diseño temporal, contratos de comunicaciones,
recuperación, scheduler, requisitos narrativos, navegación y roadmap. Se auditó
communications, structural_recovery, lore, engine, world/ship/gamestate, balance,
manifest/narrative/generator, data_loader, save_load, parser/CLI y renderers Textual.

| Hecho previo | Resultado e integración |
| --- | --- |
| Posición de nave | world.current_pos_ly; sincronizada al llegar/abortar. Durante tránsito la radio permanece bloqueada. |
| Fuente certificada | ManifestDefinition/HistoricalSite; resolve_operative_id resuelve authored/procedural lazy sin materializar. |
| Radio anterior | Coincidencia de nodo/kind/dock; comms/radiod, salud, dependencias, alimentación efectiva, Core OS, Q y brownout. |
| Productores | Lore prepara solo tras dock/uplink/salvage compatible; recovery al confirmar/avanzar etapa; API legacy local. |
| Tick | Suma dt a clock.t al comienzo, procesa llegada/jobs/scheduler, electricidad/desgaste y consecuencias; reintenta radio al final. |
| Hibernación | CLI/loop ejecutan ticks por chunks con is_hibernating=True; al terminar se retira el flag y se evalúa recuperación. |
| Tiempo | ClockState.t son segundos desde inicio; YEAR_S=365×86400. Jobs, eventos, navegación, lore y cooldowns comparten reloj básico. |
| Contenido/slots | Catálogo no recursivo, snapshot y fingerprints; contenedor V2/schema 3 con pickle, checksum y backup, validación histórica. |

No hizo falta otro servicio, ledger, sistema de sensores o generador. El nuevo
worldgen/radio.py concentra compilación e índice de declaraciones; communications
mantiene kernels físicos, gates, captura y validación. Engine y parser no requieren
cambios: el reintento y los comandos públicos existentes ya ofrecen los puntos de entrada.

## 3. Geografía medida y elección provisional

Antes de fijar los valores se midieron cuatro semillas alrededor del inicio:
43–52 sitios en 27 sectores de 10 ly, vecinos con medianas 3,85–4,70 ly incluyendo
co-localizaciones authored. La medición reproducible ampliada excluye separaciones
cero al calcular vecino positivo y añade bulge/halo: tabla siguiente, 12 muestras
y 324 sectores físicos consultados (no materializados). No se cambia ningún dato
de densidad, cuota, ubicación, radiación o topología.

| Semilla | Región | Sitios / 27 sectores | Sitios/sector | Mediana vecino positivo ly | Mediana arista positiva ly |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | disk | 52 | 1.93 | 4.110 | 5.240 |
| 1 | bulge | 40 | 1.48 | 4.508 | 4.873 |
| 1 | halo | 37 | 1.37 | 4.805 | 5.796 |
| 8 | disk | 43 | 1.59 | 3.950 | 6.087 |
| 8 | bulge | 45 | 1.67 | 4.891 | 5.708 |
| 8 | halo | 41 | 1.52 | 4.648 | 4.965 |
| 701 | disk | 45 | 1.67 | 4.447 | 4.412 |
| 701 | bulge | 39 | 1.44 | 3.693 | 5.651 |
| 701 | halo | 41 | 1.52 | 5.685 | 6.048 |
| 271828 | disk | 47 | 1.74 | 4.769 | 5.445 |
| 271828 | bulge | 38 | 1.41 | 4.363 | 4.786 |
| 271828 | halo | 34 | 1.26 | 6.683 | 7.068 |

Sensores conservan 2,5 ly. Cerca del inicio, el siguiente hub físico después del
co-localizado ECHO_7 está a 5,448–8,495 ly según semilla. HARBOR_12 está a 12,649 ly
y ARCHIVE_01 a 15,455 ly. A 6 ly hay 1–2 hubs geométricos incluyendo el local; a
20 ly hay 8–17, **sin implicar transmisores o emisiones**. Bulge/halo demuestran
huecos reales: el hub más cercano puede estar a 7,47–15,96 ly. Son candidatos
físicos de los inventarios que usa F-DEAD-01, no certificados de recepción o acceso.
La escena de recuperación nueva usa primera fuente a 5 ly y LINK posterior de 12 ly.

| Familia | P normalizada | Alcance nominal provisional | Motivo |
| --- | ---: | ---: | --- |
| Local/emergencia | 0,25 | 0,5 ly | Vecindad muy corta respecto de separación típica, distinta de receptor de estación. |
| Estación | 36 | 6 ly | Cubre parte de los vecinos habituales y supera sensores sin abarcar toda la zona. |
| Relé interestelar | 400 | 20 ly | Permite conexiones informativas entre instalaciones separadas por varios sectores, solo con actividad declarada. |

Sensibilidad LIMITED/NOMINAL/UPGRADED: 0,25/1/2,25; alcances multiplicados por
0,5/1/1,5. P explícita ajusta un emisor dentro de límites. Las cifras no son canon
definitivo ni W/dBm: no se ha calibrado ingeniería de antenas/potencias reales.
La jugabilidad se demuestra con 5 ly y actividad declarada; no se remedia escasez
de fuentes inventando emisores. El alcance de navegación de 45 ly no interviene.

## 4. Arquitectura, fórmulas y tiempo

`RadioEmitter` separa identidad de equipo, host, categoría y potencia.
`RadioEmission` separa identidad de emisión, actividad, payload y referencia
temporal. Las estaciones sin declaración no transmiten automáticamente.

`d=math.dist(host_certificado, current_pos_ly)`; intensidad normalizada
`I=P/max(d,1e-9)^2`; sensibilidad inversa de umbral S; radio `R=sqrt(P*S)`.
La frontera es inclusiva d<=R con S>0. Potencia 10^-8..10^4, números finitos y
tipos validados; clamp cerca de cero sin división por cero. Es determinista y
monótono, sin RNG ni dependencia del orden de exploración.

La onda viaja a c: retardo d×YEAR_S. Ventana recibible
`[start_t+retardo,end_t+retardo)`. continuous permite final abierto o declarado;
finite exige duración positiva. Un pulso es una ventana finita, no un paquete
que permanece eternamente. No se reconstruyen ventanas que pasaron entre ticks.
Una continua no se pierde por saltar el comienzo. Se bloquea captura en tránsito
e hibernación y se revalida al llegar/despertar.

radio_coordinate_time adapta clock.t como referencia galáctica simplificada.
Se persiste game-coordinate-seconds-v1; offsets negativos son relativos a t=0.
Preparar no altera start_t. Fuente y receptor se aproximan estacionarios en cada
comprobación. No se altera ningún consumidor actual del reloj. No están implementados
tiempo propio/edad biológica separados, relatividad ni movimiento de emisores.
El default de crucero 1.0 ly/año ya existía y permanece como deuda previa frente
al canon sublumínico; esta fase no cambia propulsión, duración ni hibernación.

## 5. Contrato de datos y búsqueda acotada

radio_emitters es un bloque optativo versionado en raíz de localización/arco/single
instalado. Hosts se resuelven por alias o ID certificado, incluido procedural exacto.
No se añade otra geografía. Categoría da P por defecto; emissions vacío es inactividad.
Cada emisión declara modo, start_t y end_t si procede, canal y exactamente uno de:
content_by_locale EN/ES; piece_key instalado; navigation_link_to certificado.
Ejemplos JSON válidos completos y de pulso están en el [contrato](../systems/radio-spacetime.es.md)
y scene.json. La fixture de pieza EN/ES se instala solo en data temporal.

piece_key exige radio_emission recíproco y un canal de radio inequívoco; correo
externo conserva su marcador explícito. Su host queda fijado sin eludir candidates,
constraints, pesos, sorteos, ventanas o deadlines. No se activa por proximidad.
Las guías generales de autoría no se reforman; e5c mantiene revisión editorial.

El compilador valida procedencia/archivo/entidad/campo: IDs duplicados, hosts
ausentes/no certificados, tipo, categoría, versiones, atributos desconocidos,
NaN/infinito/negativos, ventanas invertidas, payloads ambiguos y bindings pendientes.
Máximo 128 emisiones por emisor; offsets acotados a ±10 millones de años.

Índice derivado por niveles de potencia, celda de lado potencia de dos >= radio
UPGRADED. Consulta hasta 27 celdas por nivel, 128 candidatos por tick y cursor
persistido; páginas incompletas no prueban ausencia. Prueba presupuesto 1 y
save/load entre páginas. Sin recorrido galáctico, materialización por escucha ni
caché global mutable. El scheduler previo puede materializar al inicializar pools;
una ejecución gemela sin radio demuestra que la escucha no añade materialización.

## 6. Flujo jugable, lore y recuperación

Se reutilizan radio_spatial_block_reason, radio_block_reason, prepare/capture,
retry y mark_radio_read. Nuevos datos se congelan en RadioOpportunity, no su
alcance. Captura recalcula distancia/sensibilidad y ventana, además de todos los
gates eléctricos/operativos originales. Comms conserva consumo y deterioro.
pending no crea archivo/evento/intel/unlock/consumo. Captura produce un archivo y
evento, actualiza productor; lectura/importación posterior concede intel legítima.
Identidad canónica radio:<emisión> o lore:<pieza>, sin segunda cola ni duplicación.

Con radiod activo, retry descubre automáticamente emisiones independientes
legítimamente disponibles. Documentos con piece_key esperan selección/preparación
del scheduler y sus interacciones originales; dock requerido se conserva incluso
si la emisión tiene alcance remoto. Canales no radio mantienen sus gates y efectos.
Se prueba pieza opcional no seleccionada y pieza forzosa que espera cada trigger.

La primera pista local o remota de todo plan nuevo F-DEAD-01 requiere un aviso navigation_link_to que ya
existía, cobertura y llegada. Conservadoramente solo repetición continua sin final
permite confirmar plan pendiente de reparación/encendido; no se inventa emisión
histórica cuando surge un bloqueo. Futuras/fuera de alcance/sin actividad conservan
resultado condicionado, sin plan activo falso. Se protege primary, reservas,
acceso dirigido y fuentes; no se crean estaciones/emisores correctivos.
La etapa usa el mismo radio:<id>, vincula un pendiente sin duplicar y no reutiliza
una emisión ya capturada para obtener otra entrega. Intentos/cooldowns avanzan
solo con captura. Se guardan emisión y sensibilidad/contexto de preparación;
validación del save no confunde salud/posición actual con evidencia inicial.

## 7. Demostración pública y frontera de información

```text
Escena instalada únicamente en copia temporal: tests/fixtures/radio_world/scene.json
Receptor ECHO_7: (0,0,0); host RADIO_REMOTE: (-3,4,0); separación 5 ly.
Emisión fixture-history: continuous, start_t=-315360000 s (-10 años relativos).
Retardo: 157680000 s (5 años); llegada inicial -157680000 s.
power off security
power off data_core
power on comms
boot radiod
5 segundos de motor: una SIGNAL_CAPTURED, sin scan.
cat /logs/signals/0010.en.txt  [EN] / 0010.es.txt [ES]
NODE/LINK se importan solo al leer. Save/load antes/después no duplica.
```

Grupo 15 ejecuta ambos idiomas desde sandbox normal, con comandos públicos y
sin editar recursos/sistemas/posición tras bootstrap. Grupo 43 repara comms con
dron mediante comandos reales: LIMITED no alcanza 5 ly con perfil estación;
al pasar a NOMINAL llega una única captura continua sin repetir scan.
Pruebas puras de fórmula se distinguen de estos recorridos completos.

status/diag comms no consultan emisores/oportunidades/planes para informar de
señales ocultas. Pruebas negativas varían host, distancia, tiempo, ausencia,
pendientes y arcos protegidos con observaciones constantes. CLI/Textual comparten
renderers EN/ES. debug radio permite auditar potencia, distancia, alcance, emisión,
llegada y bloqueo; debug recovery incluye primera emisión y métricas del plan.
Ambos son puros: pickle de estado y RNG permanecen iguales. C-DATA-004 se conserva.

## 8. Persistencia y compatibilidad

Schema 3 y contenedor V2 permanecen. Nuevos slots tienen defaults seguros al
deserializar. Las oportunidades v1 ya preparadas mantienen semántica local, sin crear nuevas etapas; no se
asigna emisor interestelar retroactivo. Captura/lectura y fecha efectiva persisten.
Save/load valida emisores, ventanas, índice, identidades, ledger y recuperación;
catálogo o configuración física incompatibles se rechazan sin borrar/reescribir.

La huella completa de catálogo incluye todos los metadatos de radio.
physical_catalog_key excluye solo radio_emitters/radio_emission al construir el
ámbito físico. Sin nuevos datos es idéntica a la huella previa. Cambiar potencia
altera catálogo/snapshot pero no manifest ni IDs/estaciones/rutas, probado también
con requisitos narrativos. generator admite snapshots anteriores con fallback
a catalog_key. No se modifican manifest.py, densidad ni datos narrativos activos.
AMANECER y plantillas permanecen inactivos.

## 9. Validación y comandos

Base original: **65/66 PASS**. Entrega e5b: **66/67 PASS**. Procedencia: **67/68 PASS**. Final de persistencia: **68/69 PASS**, sin roturas nuevas. El runner incluye
todos los tests/*smoke*.py y manuals_style_check, serie con intérprete canónico,
PYTHONPATH=src:.:tests, audio/vídeo dummy y slots temporales. Mantiene return code
1 por el fallo histórico; no lo silencia ni lo cuenta como éxito.

- Nuevos: **8 grupos de invalidación** y **18 grupos focales** de procedencia, además de **43 grupos** de física, propagación, contenido, gameplay, F-DEAD-01,
  persistencia y conocimiento.
- 4D-3e5a: **19**; F-DEAD-01: **36**; narrativa: **20**; radio anterior: **18**.
- Pasan manifiesto/worldgen, catálogo/authored, save/load, navegación/intel,
  CLI/REPL, Textual, audio y manuales. Enlaces internos y pares EN/ES verificados.
- Único fallo: radiation_hull_smoke.py:183, AssertionError: [], CARNAVAL_34.
  Logs inicial/final idénticos byte a byte; SHA-256 `e54ccf0ca0e8da2081a1c8a338d71c8489f84a37c99f4a9c7eb9946dc582195b`.
  No se modifica ese test ni su código físico.
- git diff --check: correcto.

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/recovery_invalidation_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/recovery_provenance_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/knowledge_boundary_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/passive_communications_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_geography.py /tmp/retorno-radio-geography.json
/home/jon/prog/retorno_case/retorno_venv/bin/python tests/radio_spacetime_validation.py /tmp/retorno-invalidation-release
git diff --check
```

La base se ejecutó con el mismo runner serial en /tmp antes de los cambios;
el equivalente reproducible versionado es tests/radio_spacetime_validation.py.
JSON adjunto conserva comandos, return codes, tiempos y logs completos de ambas pasadas.

| Script final | Resultado | Segundos |
| --- | --- | ---: |
| `audio_config_smoke.py` | PASS | 0.916 |
| `audio_runtime_notice_smoke.py` | PASS | 0.095 |
| `config_audio_smoke.py` | PASS | 0.270 |
| `contacts_sector_smoke.py` | PASS | 0.219 |
| `contacts_smoke.py` | PASS | 0.281 |
| `deadnode_chain_detours_smoke.py` | PASS | 4.383 |
| `deadnode_chain_planner_smoke.py` | PASS | 5.543 |
| `deadnode_cooldown_zero_smoke.py` | PASS | 0.687 |
| `deadnode_opportunity_selection_smoke.py` | PASS | 6.927 |
| `debug_add_commands_smoke.py` | PASS | 0.271 |
| `debug_galaxy_smoke.py` | PASS | 0.334 |
| `debug_lore_arcs_smoke.py` | PASS | 0.328 |
| `debug_worldgen_graph_smoke.py` | PASS | 0.304 |
| `drone_completion_context_smoke.py` | PASS | 0.634 |
| `drone_modular_v1_smoke.py` | PASS | 1.312 |
| `drone_recall_all_smoke.py` | PASS | 0.373 |
| `drone_salvage_survey_smoke.py` | PASS | 0.935 |
| `energy_policy_smoke.py` | PASS | 4.084 |
| `exploration_recovery_smoke.py` | PASS | 0.783 |
| `forced_hidden_ad_hoc_smoke.py` | PASS | 0.369 |
| `galaxy_physical_model_smoke.py` | PASS | 0.186 |
| `hibernate_radiation_wake_smoke.py` | PASS | 0.383 |
| `hibernate_sequence_assets_smoke.py` | PASS | 0.032 |
| `intel_recent_order_smoke.py` | PASS | 0.514 |
| `job_id_numbering_smoke.py` | PASS | 0.284 |
| `knowledge_boundary_smoke.py` | PASS | 12.786 |
| `known_routes_integrity_smoke.py` | PASS | 3.106 |
| `lore_channel_preference_and_unlock_smoke.py` | PASS | 0.250 |
| `lore_distance_from_start_smoke.py` | PASS | 0.188 |
| `lore_secondary_count_weights_hard_smoke.py` | PASS | 1.362 |
| `lore_smoke.py` | PASS | 0.206 |
| `mail_metadata_and_log_header_smoke.py` | PASS | 0.270 |
| `manuals_style_check.py` | PASS | 0.056 |
| `narrative_world_integration_smoke.py` | PASS | 23.473 |
| `nav_abort_waypoint_cleanup_smoke.py` | PASS | 4.685 |
| `nav_map_galaxy_dependencies_smoke.py` | PASS | 0.275 |
| `nav_map_galaxy_determinism_smoke.py` | PASS | 0.340 |
| `nav_map_galaxy_smoke.py` | PASS | 0.319 |
| `passive_communications_smoke.py` | PASS | 12.435 |
| `procedural_radiation_smoke.py` | PASS | 0.200 |
| `radiation_hull_smoke.py` | FAIL (historical) | 1.480 |
| `radio_spacetime_smoke.py` | PASS | 15.010 |
| `recovery_invalidation_smoke.py` | PASS | 10.397 |
| `recovery_provenance_smoke.py` | PASS | 6.520 |
| `route_hop_cap_smoke.py` | PASS | 0.302 |
| `route_solve_out_of_range_origins_smoke.py` | PASS | 0.475 |
| `save_load_smoke.py` | PASS | 0.408 |
| `scan_job_smoke.py` | PASS | 0.569 |
| `scan_observation_memory_smoke.py` | PASS | 13.335 |
| `sector_intel_validation_smoke.py` | PASS | 1.032 |
| `sensor_detection_factor_smoke.py` | PASS | 4.418 |
| `ship_layout_output_smoke.py` | PASS | 0.269 |
| `ship_survey_radiation_smoke.py` | PASS | 0.269 |
| `smoke_test.py` | PASS | 0.500 |
| `structural_recovery_smoke.py` | PASS | 38.653 |
| `textual_active_jobs_job_id_smoke.py` | PASS | 0.358 |
| `textual_command_spacing_smoke.py` | PASS | 3.580 |
| `textual_completion_context_smoke.py` | PASS | 1.745 |
| `textual_theme_smoke.py` | PASS | 3.754 |
| `transit_radiation_progression_smoke.py` | PASS | 0.205 |
| `uplink_authored_and_failsafe_smoke.py` | PASS | 0.742 |
| `uplink_once_per_node_smoke.py` | PASS | 0.463 |
| `uplink_only_delivery_retry_smoke.py` | PASS | 2.246 |
| `worldgen_manifest_integration_smoke.py` | PASS | 6.240 |
| `worldgen_manifest_prototype_smoke.py` | PASS | 3.314 |
| `worldgen_modules_pool_smoke.py` | PASS | 2.268 |
| `worldgen_preexistence_catalog_smoke.py` | PASS | 3.457 |
| `worldgen_preexistence_characterization_smoke.py` | PASS | 1.544 |
| `worldgen_sparse_archetypes_smoke.py` | PASS | 14.045 |

## 10. Riesgos, límites y decisiones pendientes

- Balance provisional sin calibración tecnológica real; no se convierte en canon.
- Receptor/fuente estacionarios por comprobación y muestreo al final del tick:
  ventanas finitas breves entre ticks no se reconstruyen. Está documentado/probado.
- Índice paginado puede demorar captura bajo mucha carga; incompleto no equivale a ausencia.
- Fuentes remotas de recuperación necesitan contenido histórico explícito; no se
  promete que todo bloqueo tenga salida ni que los recursos permitan sobrevivir.
- A-COM-001 queda parcialmente resuelta; repetidores, interferencia compleja,
  radio activa, direccionalidad avanzada y excepciones siguen abiertas.
- Tres relojes/propulsión, e5c editorial y e6 Textual/audio prolongado permanecen separados.
- No hay arcos/singles nuevos de producción, ni red galáctica, nuevos sensores,
  recursos, lugares, audio o UI. Se actualizan manuales y contratos EN/ES.

## 11. Inventario íntegro de entrega

- `data/manuals/commands/boot.en.txt`
- `data/manuals/commands/boot.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/canon/universo.md`
- `docs/design/modelo_temporal_hibernacion.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/narrative-world-contract.es.md`
- `docs/narrative-world-contract.md`
- `docs/systems/lore-scheduler.es.md`
- `docs/systems/lore-scheduler.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/radio-spacetime.es.md`
- `docs/systems/radio-spacetime.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/radio-spacetime-results.json`
- `docs/testing/radio-spacetime-review.es.md`
- `docs/testing/radio-spacetime-review.md`
- `src/retorno/cli/repl.py`
- `src/retorno/config/balance.py`
- `src/retorno/core/communications.py`
- `src/retorno/core/gamestate.py`
- `src/retorno/core/lore.py`
- `src/retorno/core/structural_recovery.py`
- `src/retorno/io/save_load.py`
- `src/retorno/model/world.py`
- `src/retorno/worldgen/generator.py`
- `src/retorno/worldgen/narrative.py`
- `src/retorno/worldgen/radio.py`
- `tests/fixtures/radio_world/piece.en.txt`
- `tests/fixtures/radio_world/piece.es.txt`
- `tests/fixtures/radio_world/scene.json`
- `tests/fixtures/recovery_legacy/README.es.md`
- `tests/fixtures/recovery_legacy/README.md`
- `tests/fixtures/recovery_legacy/pending-v1.dat`
- `tests/radio_spacetime_geography.py`
- `tests/radio_spacetime_smoke.py`
- `tests/radio_spacetime_validation.py`
- `tests/recovery_invalidation_smoke.py`
- `tests/recovery_provenance_smoke.py`
- `tests/structural_recovery_smoke.py`

ZIP/SHA-256 y manifiesto de hashes se entregan aparte para evitar una referencia
circular al hash del propio informe. No se hace stage, commit ni push. Detenido
para revisión externa.
