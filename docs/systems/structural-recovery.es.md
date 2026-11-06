# Recuperación estructural F-DEAD-01 — 4D-3e5

[English](structural-recovery.md). Implementación para revisión externa, 2026-11-06.
Autoridad: `core/structural_recovery.py`; pruebas: `tests/structural_recovery_smoke.py`.

## Autoridad y alcance

Cada sitio se certifica contra `historical-world-v1` fijado para la partida,
incluidos los requisitos authored narrativos de e4. Consultar no materializa,
no consume RNG y no modifica conocimiento, recursos, pools, radio ni scheduler.
La confirmación materializa únicamente sitios certificados, con sus identidades,
coordenadas, tipos, procedencia y aristas históricas originales. No usa muestreos
correctivos ni cupos condicionales. Se retiraron `_create_bridge_node`,
`_sample_anchor_offset`, `_ensure_entry_node` y `_ensure_gateway_node`.
Las cadenas legacy ya guardadas conservan su entrega si siguen siendo válidas.

La selección resuelve estructura, sin filtrar por scrap, energía, daños, drones,
radiación, reparaciones o supervivencia. Los gates de acciones y recepción sí
siguen vigentes. No garantiza una salida universal ni sobrevivir al recorrido.

## Selección y ámbito

Se calcula acceso dirigido desde la nave usando conocimiento válido para viajar
y el kernel compartido `is_hop_within_cap`. Entre emisores históricos ya
alcanzables y con primera recepción espacialmente elegible se busca la cadena
con menor distancia completa de acceso y recorrido
en el inventario examinado; después desempata por incertidumbre de materialización,
saltos e IDs ordenados. Se consideran rodeos: la cercanía euclidiana del origen
al objetivo no sustituye al trayecto dirigido. No se afirma optimalidad galáctica.

El inventario incluye sitios materializados certificados, certificados retenidos,
sectores generados/observados y consultas físicas inversas del manifiesto, con
su desbordamiento Z. Un objetivo deadnode por ID se resuelve también si está lazy.
La primera consulta prioriza sectores relevantes y sondas del corredor hacia un
objetivo explícito; después el cursor recorre capas cúbicas 3D de sectores. Las
sondas eligen sectores, nunca inventan coordenadas de instalaciones.

Presupuesto predeterminado por selección: 16 sectores físicos (API permite 0–64),
2048 sitios, 4096 expansiones, 65536 comprobaciones de aristas y una ventana de
1024 certificados retenidos. Se rechazan configuraciones fuera de los límites
explícitos de `RecoveryBudget`. El acceso conocido también queda limitado por
el inventario y el presupuesto de aristas. La sesión del manifiesto es local.
El cursor avanza incluso si las prioridades llenan la consulta inicial.
No hay radio máximo de búsqueda de juego. La ventana retenida es finita: una cadena que no
quepa puede quedar sin demostrar; esto no prueba ausencia universal. Recortar
certificados sin hallar cadena produce `incomplete`, no una conclusión global.
Cambiar de ancla reinicia el ámbito próximo. Sin cambio de ancla, reintentar
continúa el cursor, también después de guardar/cargar.

| Resultado | Evidencia |
| --- | --- |
| `search_pending` | Evaluación solicitada; todavía sin resultado. |
| `validated` | Cadena completa con primera recepción espacialmente elegible; todavía no está confirmada. |
| `conditional` | Falta un emisor admisible o la primera recepción está fuera de cobertura; puede acompañarse de una propuesta física solo diagnóstica. No se confirma ni se inventa una señal. |
| `none_in_scope` | No se encontró una cadena completa en ese inventario acotado. |
| `incomplete` | Presupuesto, retención o dominio numérico impiden terminar la evaluación. |
| `invalid` | Protección narrativa, certificado, identidad o preparación no válidos. |

No hay exploración exhaustiva de la galaxia. Los límites de clausura/materialización
y dominio del manifiesto siguen aplicándose; no se convierten en reglas de balance.
Una consulta nueva tiene trabajo finito; no usa cachés globales mutables.

## Corrección focal: accesibilidad de la primera pista

`communications.radio_spatial_block_reason` es la comprobación reutilizable de
cobertura/contexto físico. La consultan selección, confirmación y captura; las
comparaciones de nodos del modelo local quedan en comunicaciones, no en F-DEAD-01.
Hoy exige fuente física en el nodo actual, tipo admitido y dock cuando proceda.
No comprueba salud, alimentación ni estado de comms/radiod. Estos gates operativos
pertenecen a `radio_block_reason` y se reevalúan al capturar. Un receptor apagado
o averiado en la ubicación adecuada permite un plan `receipt_pending`.

Si hay emisores espacialmente elegibles, solo ellos originan propuestas confirmables;
la distancia dirigida y los rodeos siguen ordenando las cadenas dentro de ese
conjunto. Sin ellos, la búsqueda puede devolver la mejor cadena remota examinada
como `conditional`, con razón `first_reception_outside_coverage`; `proposal` no es
autorización de confirmación. `request_recovery` solo confirma `validated` y
`confirm_recovery` vuelve a comprobar cobertura antes de copiar/materializar.
Una búsqueda condicionada no crea plan, oportunidad, archivo, ruta ni contador;
tampoco bloquea la siguiente búsqueda como frontera activa. El cursor puede
continuar y cambiar de ubicación permite una selección nueva.

El diagnóstico jugable conserva estados genéricos; no anuncia el emisor ni el
destino remoto. No se añade correo interno, transmisor local, guía omnisciente,
segunda cola ni nuevas reglas de alcance. La ampliación física futura sustituirá
la comprobación compartida; potencia, atenuación y latencia quedan para 4D-3e5b.
Los cambios de presentación de pendientes quedan para 4D-3e5a.
Al guardar/cargar un plan todavía sin captura se valida también el contexto
original de preparación (`access.path[0]`) mediante el mismo predicado espacial.
Esto admite salir de una fuente legítima y regresar después, con la oportunidad
pendiente intacta. Un guardado anterior con primera recepción remota inválida se
rechaza explícitamente sin borrar ni reescribir su archivo; no se migra ni se
inventa una orientación para hacerlo válido. Las pruebas 28–36
reproducen y cubren esta corrección; el grupo 5 conserva la comparación dirigida
remota con resultado condicionado en lugar de confirmable.

## Fuentes y progresión

La primera pista siempre es una comunicación nueva desde una estación, relé o
waystation históricos, alcanzables y con cobertura para la nave al confirmar.
Una ruta conocida hacia un emisor remoto no demuestra acceso informativo a su
primera pista. La capacidad local de esos tipos es la ya
existente en el modelo de broadcasts; no se simula una red interestelar.
Se prepara un `RadioOpportunity` en el ledger común. Reintentar conserva origen,
contenido EN/ES e identidad. No hay otra cola. Sin emisor comprobado se registra
la limitación sin mensaje ficticio ni intento consumido.

Cada pista publica un solo `LINK` entre extremos físicos, de distancia positiva
y como máximo 45 ly. Leer/importar usa el parser real y mantiene su semántica
bidireccional; no modifica las aristas históricas. Preparar/capturar no publica
`known_links` ni revela el resto de la cadena. `NODE`, `SECTOR`, `COORD`, scan y
resolución manual conservan sus reglas.

Una escala puede reutilizar un enlace operativo dirigido ya conocido, sin
añadir pistas ni fuentes. Llegar a esa escala habilita el tramo existente.
Los intermediarios ofrecen otra comunicación local o un documento de salvamento
preparado antes de la primera inspección. Un pool cerrado/limpio o un pecio ya
visitado no admite un documento nuevo. Un hub agotado sí puede emitir una
comunicación nueva legítima: su pool y sus recursos permanecen agotados.
Las reservas narrativas se excluyen; no se desplaza contenido ni se fuerza un
single opcional. La protección reutiliza los primaries existentes y falla de
forma conservadora si una referencia no puede interpretarse. Scan natural y
`route solve` manual exacto siguen siendo excepciones deliberadas.

| Estado del plan | Transición |
| --- | --- |
| `prepared` | Preparación transaccional interna. |
| `receipt_pending` | Fuente preparada; captura pendiente de gates y contexto local. |
| `active` | Captura real o etapa de salvamento habilitada. |
| `stage_consumed` | Archivo leído/importado y enlace realmente publicado. |
| `complete` | Se consumió la última pista y la nave llegó al destino final. |
| `invalid` | Una revalidación detectó una etapa física inválida. |

La siguiente etapa solo se habilita tras leer/importar la anterior y llegar a
su fuente. Los documentos posteriores están en sus hosts, no precargados en la
nave. Abandonar una fuente de radio mantiene la oportunidad pendiente hasta un
regreso legítimo. `comms`, `radiod`, suministro, tránsito, hibernación y contexto
se verifican al capturar. `sensord` y `datad` no habilitan radio.

## Activación, intentos y persistencia

La recuperación global comprueba rutas dirigidas, contactos resolubles, fuentes
uplink/salvage, intel legible recuperada y planes pendientes antes de buscar.
Una reparación necesaria no elimina una frontera estructural. Los triggers y
umbrales deadnode originales conservan semillas, años, uplinks y cooldown.
No se invoca la antigua creación de puentes. Solo hay un plan activo por bloqueo.

El primer mensaje realmente capturado incrementa una vez `attempts` y fija
`last_action_t` para deadnodes; en global incrementa el contador/generación de
recuperación. Tiempo cero es un timestamp válido. Ni buscar, preparar, agotar
presupuesto, bloquear recepción ni fallar confirmación consumen entrega o
cooldown. Las etapas posteriores no incrementan intentos. Al resolverse el
contacto puede retirarse su tracker legacy; el plan/ledger conservan su historial.

La propuesta lleva scope y huella estructural; confirmar revalida todas las etapas,
acceso dirigido, fuentes, protección e identidades. Trabaja sobre una copia,
materializa en una consulta conjunta acotada y prepara fuentes antes de publicar
el conjunto de cambios. Un fallo descarta la copia. La publicación conserva las
referencias existentes a nodos/pools usadas por comandos en curso. No ejecuta
rolls del scheduler ni consume archivos o recursos. Repetir reutiliza el plan.

Se persisten planes versionados, etapa, etapas capturadas/leídas, fuentes, ledger,
certificados/cursor de búsqueda y el universo ya fijado. Guardar/cargar valida
manifiesto y planes; una versión incompatible se rechaza sin borrar el archivo.
No se implementa migración compleja de universos antiguos. Los valores nuevos
vacíos admiten partidas schema 3 anteriores que ya eran compatibles.

## Relación con el núcleo anterior y límites

`propose_deadnode_chain`, `evaluate_deadnode_opportunity` y
`compare_deadnode_opportunities` siguen disponibles como diagnóstico puro de
geometría/capacidad/economía. Sus nodos propuestos no son autoridad física.
El adaptador productivo reutiliza `AccessRoute`, lectura de fuentes de intel,
capacidades de entrega, política de primaries y kernels de navegación existentes;
separa el Dijkstra estructural de los filtros económicos de aquellas APIs.

Las búsquedas son síncronas y acotadas bajo el bloqueo existente del motor; no se
introducen workers ni paneles nuevos. Las medidas de tiempo/memoria están en el
[informe](../testing/structural-recovery-review.es.md). El presupuesto puede
interrumpir una búsqueda antes de demostrar una cadena larga; la ventana retenida
no sustituye una exploración exhaustiva. Pueden faltar emisor, fuentes, sitios
conectables, permisos de dominio o recursos para completar el viaje. Esos límites
se reconocen; no se remedia ninguno fabricando historia.
