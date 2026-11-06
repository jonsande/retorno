# Recuperación estructural F-DEAD-01 — 4D-3e5

## Presentación y desarrollo — 4D-3e5a

La selección interna no es conocimiento de la nave (`C-DATA-004`). `status` y
`diag comms` no consultan `recovery_searches` ni `recovery_plans`, ni muestran
estados genéricos que dependan de ellos, incluso con debug activo. Preparar una
cadena sin primera captura no revela nada. Captura, archivo recibido, lectura e
intel legítimos mantienen la progresión anterior.

`debug on` habilita `debug recovery` en CLI y Textual: muestra búsquedas guardadas,
resultado/motivo, certificados candidatos retenidos, sectores, expansiones/aristas,
cursor y ancla; planes con estado, etapa, acceso, sitios y mecanismos de fuente,
etapas capturadas/consumidas y versión. Muestra los presupuestos técnicos
predeterminados como configuración actual, no como mediciones históricas.
No inventa un historial de candidatos rechazados ni reejecuta el selector para
reconstruirlo: solo puede mostrar razones y evidencia que ya estén conservadas.
`debug radio` permite relacionar planes con entregas y bloqueos vigentes.
`debug off` vuelve a bloquear ambas consultas. Las consultas no añaden logging
ni mutaciones de simulación. La frontera C-DATA-004 de e5a se conserva al ampliar
alcance y propagación en 4D-3e5b; los nuevos metadatos físicos sí se persisten.
Prueba: `tests/knowledge_boundary_smoke.py`.


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

## Cobertura de la primera pista — 4D-3e5b

`radio_spatial_block_reason` y `radio_temporal_block_reason` son las fronteras
comunes de selección, confirmación y captura. Los planes nuevos, locales y remotos, exigen
emisor certificado, emisión concreta, potencia/sensibilidad suficiente y onda
ya llegada. La compatibilidad local solo conserva oportunidades legacy previamente
persistidas e interacciones narrativas autorizadas. Conocer ruta al host o preparar ahora el mensaje no lo justifica.

Todo inicio de plan nuevo solo usa `navigation_link_to` declarado antes de detectar el
bloqueo, con contenido fijo para ese LINK. Requiere emisión continua sin final:
permite captura posterior tras reparar/encender. No se crea actividad histórica
retrospectiva, relé correctivo ni nueva estación. El examen de declaraciones de recuperación
está acotado a 4096 emisiones; agotamiento no significa ausencia.

La selección conserva acceso dirigido, rodeos, presupuesto, expansión, primaries
protegidos y reservas. Solo primeras fuentes espacial y temporalmente elegibles
pueden confirmar; sin ellas el resultado permanece condicionado y no crea plan,
oportunidad, archivo, ruta ni intento. La sensibilidad útil actual determina la
cobertura; equipo inoperativo usa referencia NOMINAL sin filtrar recursos o
supervivencia. Un receptor apagado puede mantener `receipt_pending` legítimo.

La propuesta persiste `first_emission_id`, `first_reception_sensitivity` y
`stage_sources`: identidad y huella del contenido de cada etapa informativa.
Confirmar revalida llegada y cobertura actuales antes de materializar la cadena.
El ledger único usa `radio:<emission_id>`; puede vincular un pendiente independiente
sin duplicarlo. Una emisión recibida no sirve para crear otra captura. Guardar
valida posición/contexto original (`access.path[0]`), sensibilidad y tiempo de
preparación, sin exigir salud o ubicación actuales. Capturar sí revalida estas.
Los planes nuevos usan `historical-recovery-v2`; no admiten fuentes vacías.
Saves v1 compatibles mantienen únicamente oportunidades ya preparadas, sin
asignarles emisores ficticios. No se crean nuevas etapas de radio legacy al
avanzar: si falta una oportunidad previamente persistida, esa continuación se
marca inválida y permite evaluar alternativas. Remotos inválidos se rechazan
sin reescribir. Pruebas 28–36, radio_spacetime y recovery_provenance.

`status`/`diag comms` siguen sin datos internos. `debug recovery` muestra emisión,
parámetros de cobertura/tiempo y bloqueo; `debug radio` inspecciona declaraciones
y ledger sin mutación. [Contrato físico](radio-spacetime.es.md).

## Fuentes y progresión

La primera pista procede de una estación, relé o waystation históricos,
alcanzables y con cobertura al confirmar, mediante un aviso local o remoto
previamente declarado y ya propagado. Estar en el host no prueba actividad.
La mera ruta conocida no demuestra recepción.
No se simula una red interestelar.
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
Los intermediarios requieren una emisión declarada para su LINK exacto o un
archivo físico recuperable que ya contenga esa pista. La selección consulta pools
existentes y archivos authored instalados; no genera documentos procedurales para
responder al bloqueo. Guarda referencia y huella del archivo, sin inyectar ni
reabrir pools. Un pool cerrado/limpio o ya inspeccionado no adquiere una pista
nueva. Una fuente reservada antes de su visita conserva la lectura legítima de
su archivo ya existente. Un hub agotado solo puede recibir su emisión declarada;
el tipo de instalación no implica actividad. Sus recursos permanecen agotados.
Las reservas narrativas se excluyen; no se desplaza contenido ni se fuerza un
single opcional. La protección reutiliza los primaries existentes y falla de
forma conservadora si una referencia no puede interpretarse. Scan natural y
`route solve` manual exacto siguen siendo excepciones deliberadas.

| Estado del plan | Transición |
| --- | --- |
| `prepared` | Preparación transaccional interna. |
| `receipt_pending` | Fuente preparada; captura pendiente de gates, cobertura y tiempo legítimos. |
| `active` | Captura real o etapa de salvamento habilitada. |
| `stage_consumed` | Archivo leído/importado y enlace realmente publicado. |
| `complete` | Se consumió la última pista y la nave llegó al destino final. |
| `invalid` | Una revalidación detectó una etapa física inválida. |

La siguiente etapa solo se habilita tras leer/importar la anterior y llegar a
su fuente. Los documentos posteriores están en sus hosts, no precargados en la
nave. Abandonar cobertura mantiene la oportunidad pendiente hasta una nueva
disponibilidad legítima según su modalidad. `comms`, `radiod`, suministro, tránsito, hibernación y contexto
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

Una invalidación legítima también se guarda y carga: conserva la propuesta,
etapa y recepciones/importaciones anteriores y queda fuera de `ACTIVE`. El motor
registra `invalidation` con motivo y huella del progreso; `source_contract` fija
la propuesta confirmada, versión, tiempo e intento. Cambiar solo `status` a
`invalid` no valida un plan. Se siguen comprobando certificados físicos,
protecciones, forma de las fuentes, integridad del contrato y correspondencia
entre ledger y progreso. Una continuación de radio nunca preparada puede carecer
únicamente de su oportunidad actual; las oportunidades anteriores son obligatorias.
La validación histórica de planes invalidados no exige disponibilidad actual de
fuentes futuras. Los activos mantienen la validación completa y los completos
requieren todas sus etapas consumidas. Los campos son aditivos para schema 3:
los slots antiguos obtienen la huella al deserializar y pasan las validaciones
habituales; no cambian las versiones v1/v2 ni se crean fuentes legacy.

Si una emisión de una etapa v2 posterior ya se recibió por escucha pasiva,
`_radio_stage` reutiliza esa recepción canónica con procedencia y contenido exactos.
No recaptura ni incrementa intentos/cooldowns: si falta leerla, sigue requiriendo
lectura/importación; si ya se importó su LINK, la etapa queda consumida al llegar
a ella. Los planes invalidados no bloquean nuevas búsquedas legítimas del mismo
bloqueo. Pruebas: `tests/recovery_invalidation_smoke.py` y caso 12 de
`tests/recovery_provenance_smoke.py`.

## Relación con el núcleo anterior y límites

`propose_deadnode_chain`, `evaluate_deadnode_opportunity` y
`compare_deadnode_opportunities` siguen disponibles como diagnóstico puro de
geometría/capacidad/economía. Sus nodos propuestos no son autoridad física.
Sin emisiones o archivos con pistas suficientes, la búsqueda queda condicionada
sin confirmar ni consumir intentos/cooldowns. No se añade un catálogo histórico
procedural de transmisiones. Su posible necesidad corresponde a una decisión
posterior, que podrá evaluarse en la auditoría editorial e5c.

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
