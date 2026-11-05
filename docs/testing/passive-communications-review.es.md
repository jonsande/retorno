# RETORNO — Informe técnico 4D-3e4b

Fecha: 2026-11-06, Europe/Madrid. [English](passive-communications-review.md).
Entrega implementada para **revisión externa**, sin staging, commit ni push.

## Base y alcance

HEAD inicial/final: `78676dbfce5e7b98db36b2e241a427a19b0632fe`; rama `main`, upstream `origin/main`.
El remoto se consultó y coincidía con esa base al comenzar. Árbol inicialmente
limpio; la entrega e4 ya estaba integrada. El ZIP contiene únicamente todos los
archivos nuevos/modificados de **esta fase e4b**, no la entrega anterior.
No hay cambios staged. Los archivos de entrega quedan locales para revisión.

Se leyeron AGENTS, contrato de navegación/recuperación, roadmap v1.2, canon,
scheduler, failsafes, descubrimiento/intel e informe e4. Se revisaron bootstrap,
modelos, dependencias, energía, deterioro, trabajos, reparación, eventos, REPL,
adaptador Textual, audio y save/load. No se modificaron balance general,
worldgen, los cinco singles, templates inactivos, AMANECER ni audio.
El cambio Textual se limita a mostrar las líneas comunes en su status.

## Defectos auditados y corrección

Antes, `deliver_captured_signal`, `deliver_station_broadcast` y
`write_local_intel` escribían archivos sin receptor. `_deliver_piece` contaba
señales y `_deliver_assigned_for_trigger` consumía la pieza/pool al devolver
éxito. Gateway marcaba `dock_hint_delivered` al escribir; deadnodes incrementaba
`attempts` y `last_action_t` inmediatamente. Recovery creaba entrada/gateway,
sembraba archivos y avanzaba generación/contadores antes de distinguir recepción.

Ahora hay una sola oportunidad persistente para radio. El escritor público
prepara/captura mediante el predicado compartido; el escritor de archivo bruto
queda privado para la operación común y canales no radio. El commit de lore,
pool, signal_count correspondiente, flag de gateway o intento/cooldown deadnode
ocurre solo tras captura real. Mientras está bloqueada no hay archivo/evento
exitoso, intel, unlock ni consumo. Leer/importar sigue siendo otra transición.

El boot anterior podía marcar un servicio running aunque su propietario hubiese
sido apagado durante el trabajo. Se revalidan instalación, identidad, salud,
apagado forzado, dependencias y gates de potencia durante el trabajo y al aplicar
el resultado. Apagar hardware detiene su servicio inmediatamente. Se conserva
la activación legacy de sensores inicialmente OFFLINE no forzados por sensord;
radiod exige hardware activo. Cancelar/fallar usa los trabajos existentes.

## Hardware, servicio y gates

`comms`: ShipSystem en BRG-01 existente, salud inicial 0.90, OFFLINE forzado,
prioridad 4. Depende de energy_distribution NOMINAL efectivamente alimentado.
Nominal 0.15 kW, LIMITED 0.12, UPGRADED 0.165; la carga se mantiene completa en
CRUISE. Se mide también la diferencia real de batería en el test. Deterioro
reutilizado de data_core: base 8.5e-11/s, k_power 0.30, k_rad 0.10; mantiene
factores generales de desgaste y reparación ordinaria con dron, sin reparación
regalada. Ningún otro consumo se modifica.

`radiod`: ServiceState instalado/detenido, boot de 5 s, propiedad directa de
comms. No depende de sensors/sensord ni data_core/datad. `requires_active_owner`
permite expresar el gate sin otra infraestructura de daemons. Encender o reparar
comms no arranca el servicio. LIMITED/NOMINAL/UPGRADED reciben determinísticamente;
estados inferiores no. Se comprueban además salud, dependencias, Core OS, terminal,
Q >=0.55, brownout, capacidad eléctrica actual y contexto fuera de tránsito o
hibernación. No hay RNG, interferencias aleatorias ni reinicio automático.

## Ledger persistente, fuente y commit

`RadioOpportunity` guarda ID, canal, fuente, host, trigger original, exigencia de
dock, contenido EN/ES congelado, metadatos mínimos del productor, instante de
preparación, estado, path, idioma/instante de recepción e instante de lectura.
IDs: lore:<piece_key>, recovery:<generation>:gateway, deadnode:<target>:<attempt>;
la API local admite ID explícito o digest estable. No hay segunda cola de recovery.

Estados: pending → received → read_imported. El último expresa que el jugador
accedió al contenido; no asegura intel útil. El contenido disponible se conserva
incluso si una API legacy solo congeló ES y se recibe luego en EN, o viceversa;
los textos de lore congelan ambas versiones con el fallback existente.

El tick reintenta después de energía/deterioro/consecuencias. Se exige que el host
siga existiendo y sea el nodo actual. Lore nacido de dock/uplink/salvage mantiene
su dock; la mera proximidad o llegada nunca crea su trigger. El gateway ya
preparado admite llegada local sin dock. Se revalidan identidad de etapa,
protección y saltos físicos de pistas legacy. Viajar suspende captura; volver
al contexto permite reintentar. No se inventan emisores ni cobertura galáctica.
La disponibilidad local persistente es el mínimo del modelo actual, sin simulación
de caducidad ni estado energético independiente del emisor.

La captura y bookkeeping son síncronos en memoria. Repetir trigger/tick o cargar
una recepción no duplica archivos, eventos, signal_count, log ni desbloqueos.
Los contadores de acciones mantienen la semántica previa; el reintento no cuenta
otro dock/uplink/salvage. Las señales legacy no suman un contador nuevo que cambie
deadlines. No se libera un primary de archivo antes de leer/importar intel válida.

## Productores y consumidores revisados

| Productor/consumidor | Antes | Después y punto de confirmación |
| --- | --- | --- |
| Lore captured_signal | Archivo/evento y signal_count directos al trigger. | Oportunidad congelada, radio + host/dock; commit_radio_delivery actualiza log/counter/pool/delivered tras captura. |
| Lore station_broadcast | Archivo/evento directo en dock. | Misma oportunidad común; radio, hub local y dock. No se adelanta al acercarse. |
| deliver_captured_signal / deliver_station_broadcast | Escritores sin gate. | Delegan en write_local_intel gated; bloqueados devuelven path vacío, sin archivo. |
| write_local_intel radio | Siempre escribía. | Prepara ID estable y captura; devuelve None/None si sigue pendiente. |
| Lore mail interno / deliver_ship_mail interno | Entrega interna sin radio. | Conservado; mismo canal/envoltura/consumo. |
| Mail externo explícito | No había marcador activo ni gate específico. | mail_origin=external en pieza, external_origin en API o SourceRef externo usan radio conservando mail. No se infiere de prosa/remitentes. |
| Recovery primera pista scan/route/dock/uplink/hibernate | Creaba entrada/gateway y entregaba según trigger. | Activación aplazada antes de fabricar nodos; sin generación, éxitos, archivos ni recepción ficticia. |
| Cache externa de hibernate legacy | Se presentaba como mail de CORE.OS tras crear cadena. | Esa activación también se aplaza; no se convierte en correo interno gratuito. |
| Gateway de cadena existente | Escribía/confirmaba al llegar incluso sin receptor. | Oportunidad generation/gateway local; commit de dock_hint_path/delivered solo al recibir. |
| Deadnode indirecto nuevo | Creaba puente y contaba intento. | Aplazado si falta puente; tracker puede observar umbrales sin consumir entrega. |
| Deadnode con puente existente / etapa directa | Archivo y attempts/cooldown inmediatos. | Fuente/etapa congeladas, cap/protección/radio; attempts y timestamp solo al capturar. |
| Salvage: archivo de pieza/pool y job de dron | Montaje independiente de lectura. | Conservado sin radiod; regresiones e4 y dron reales. |
| Uplink público / uplink_only | data_core/datad, dock, potencia y LINK válido. | Conservado sin radio; no se cuentan como éxito activaciones recovery aplazadas. |
| write_local_intel uplink_trace | Podía escribir sin validar el canal en su frontera. | Comprueba uplink_blocked_reason, incluido datad instalado/activo; sin radio. |
| cat / mail read / intel import | Parser aplica intel válida tras acceso. | Conservado; además marca oportunidad read_imported una sola vez tras acceso correcto. |
| status / diag / help / Textual | Sin receptor ni pendientes. | Nombres EN/ES, gates y cantidad; no muestran contenido, fuentes/objetivos secretos ni intel nueva. |
| Bootstrap y archivos authored montados | Archivo local inicial o recuperación de archivo físico. | Conservados: no se reinterpretan como recepción de radio en vivo. |

## Recuperación legacy y límite de e5

La orden autoriza aplazar una activación si exige mutaciones físicas difíciles
de separar de la recepción. La global siempre necesitaba fabricar entrada y
posiblemente gateway; deadnodes fabricaba el primer puente. Ahora no se invocan
esos creadores en activaciones nuevas. `recovery_activation_deferred` persiste y
el diagnóstico lo explica sin revelar targets. Se conservan helpers legacy y
selector/políticas para el trabajo estructural posterior; no se integra el nuevo
planificador ni se inventan estaciones históricas correctivas.

**Consecuencia material:** un bloqueo estructural puede permanecer sin rescate
automático hasta e5. Las cadenas previamente preparadas siguen consumibles con
canal válido. No se afirma F-DEAD-01 implementado, validado ni salida universal.
Los tests antiguos que exigían crear nodos se adaptaron explícitamente a este
contrato; no se ocultó el cambio con activación gratuita del receptor.

## Persistencia y compatibilidad

Contenedor V2 y esquema 3 conservados. WorldState restaura colección vacía/flag
por defaults; ServiceState deserializa su nuevo flag con false para los servicios
anteriores. Tras validar catálogo/universo, una partida sin comms recibe el
mismo sistema instalado OFFLINE de bootstrap. No hay energía, recursos,
reparaciones, activación o intel gratuitos. El archivo original y .bak permanecen
idénticos byte a byte al cargar. Se prueban slots con representación anterior
real de campos ausentes, pending, boot en marcha, received y read_imported,
repetición tras cargar y cambios EN↔ES. El snapshot e4 sigue siendo obligatorio.

## Experiencia pública y localización

Se usa la maquinaria existente de power/boot/jobs/repair. Los avisos recorren
propietarios y dependencias del modelo; distinguen detenido/no instalado/bloqueado,
muestran nombre localizado, ID y boot efectivo o diag. No se repiten cada tick
ni al pedir power on sobre hardware ya encendido. Se añaden help y manuales
EN/ES. CLI y Textual usan los mismos renderers y estado; no hay panel ni sonido
nuevo. Los tipos de recepción existentes se conservan.

Prólogo real, seed 701, sin modificar salud, scrap, potencia ni RNG:

```text
power off security
power off data_core
drone deploy D1 PWR-A1
drone repair D1 power_core   (tres intentos ordinarios)
drone move D1 BUS-A2
drone repair D1 energy_distribution   (dos intentos ordinarios)
power on comms
boot radiod
```

Resultado: t=256 s, scrap=52, Q≈0.711, comms NOMINAL y radiod activo. Un intento
ordinario de reparación puede fallar con su política previa; no se suprime ni se
regala éxito. El flujo alcanza recepción operativa con recursos restantes.
Los grupos nuevos ejercitan también cat, mail read, intel import, power off y
cancelación mediante parser/acciones públicas. No se hizo sesión audiovisual
manual de e6; Textual se ejecuta headless en sus regresiones.

## Pruebas y resultados

Intérprete exclusivo: /home/jon/prog/retorno_case/retorno_venv/bin/python;
PYTHONPATH=src:repo y slots temporales. Scripts propios del proyecto, sin pytest.
Base: **61/62 PASS**. Final serial: **62/63 PASS**, incluyendo **18 grupos nuevos**
y los **20 grupos e4** (18 originales más las dos correcciones focales).
Manuals style, pares EN/ES, enlaces añadidos, AST/JSON y git diff --check: PASS.

Los 18 grupos nuevos cubren hardware/prólogo/carga/batería, boot con apagado,
retirada, desinstalación, dependencia, brownout, cancelación y salud; estados y
servicios independientes; lore pendiente/capturado/leído; cobertura/dock sin
adelanto; reparación; canales no radio y mail externo; saves y defaults antiguos;
aplazamiento y gateway existente; cooldown deadnode; CLI/Textual/avisos; ausencia
de RNG/cambios físicos; recorrido público sin overrides; contenido congelado
EN/ES; gates vivos sin efectos; mail externo de lore leído con mail read;
protección/extremos físicos al reintentar; save/load durante boot.

Comparador productivo ejecutado para semillas 0–7,29,271828: aggregate, rows,
resource_totals, configuration_key, método, algoritmo, patches y semillas
coinciden exactamente con docs/testing/manifest-integration-measurements.json.
Solo tiempos/memoria de benchmark son observacionales; no se actualizó el testigo.
Esto complementa las regresiones de scan, memoria, sensores, topología y recursos.

Único fallo: radiation_hull_smoke.py:183, AssertionError: [], testigo CARNAVAL_34,
idéntico al de la base. No se corrigió con cambios ajenos. Las regresiones de
Textual, servicios/energía/reparación, lore/intel, recovery/deadnodes y save/load
pasan. La prueba de tema pasa en la ejecución serial de entrega.

| Script | Resultado | Segundos |
| --- | --- | --- |
| `audio_config_smoke.py` | PASS | 1.24 |
| `audio_runtime_notice_smoke.py` | PASS | 0.07 |
| `config_audio_smoke.py` | PASS | 0.21 |
| `contacts_sector_smoke.py` | PASS | 0.18 |
| `contacts_smoke.py` | PASS | 0.29 |
| `deadnode_chain_detours_smoke.py` | PASS | 3.47 |
| `deadnode_chain_planner_smoke.py` | PASS | 4.26 |
| `deadnode_cooldown_zero_smoke.py` | PASS | 0.52 |
| `deadnode_opportunity_selection_smoke.py` | PASS | 4.95 |
| `debug_add_commands_smoke.py` | PASS | 0.22 |
| `debug_galaxy_smoke.py` | PASS | 0.27 |
| `debug_lore_arcs_smoke.py` | PASS | 0.27 |
| `debug_worldgen_graph_smoke.py` | PASS | 0.25 |
| `drone_completion_context_smoke.py` | PASS | 0.21 |
| `drone_modular_v1_smoke.py` | PASS | 1.0 |
| `drone_recall_all_smoke.py` | PASS | 0.24 |
| `drone_salvage_survey_smoke.py` | PASS | 0.7 |
| `energy_policy_smoke.py` | PASS | 3.12 |
| `exploration_recovery_smoke.py` | PASS | 0.5 |
| `forced_hidden_ad_hoc_smoke.py` | PASS | 0.29 |
| `galaxy_physical_model_smoke.py` | PASS | 0.15 |
| `hibernate_radiation_wake_smoke.py` | PASS | 0.29 |
| `hibernate_sequence_assets_smoke.py` | PASS | 0.03 |
| `intel_recent_order_smoke.py` | PASS | 0.43 |
| `job_id_numbering_smoke.py` | PASS | 0.21 |
| `known_routes_integrity_smoke.py` | PASS | 2.25 |
| `lore_channel_preference_and_unlock_smoke.py` | PASS | 0.2 |
| `lore_distance_from_start_smoke.py` | PASS | 0.15 |
| `lore_secondary_count_weights_hard_smoke.py` | PASS | 1.08 |
| `lore_smoke.py` | PASS | 0.17 |
| `mail_metadata_and_log_header_smoke.py` | PASS | 0.22 |
| `narrative_world_integration_smoke.py` | PASS | 18.86 |
| `nav_abort_waypoint_cleanup_smoke.py` | PASS | 3.61 |
| `nav_map_galaxy_dependencies_smoke.py` | PASS | 0.22 |
| `nav_map_galaxy_determinism_smoke.py` | PASS | 0.27 |
| `nav_map_galaxy_smoke.py` | PASS | 0.26 |
| `passive_communications_smoke.py` | PASS | 8.16 |
| `procedural_radiation_smoke.py` | PASS | 0.17 |
| `radiation_hull_smoke.py` | FAIL previo / preexisting | 1.09 |
| `route_hop_cap_smoke.py` | PASS | 0.24 |
| `route_solve_out_of_range_origins_smoke.py` | PASS | 0.35 |
| `save_load_smoke.py` | PASS | 0.32 |
| `scan_job_smoke.py` | PASS | 0.44 |
| `scan_observation_memory_smoke.py` | PASS | 10.66 |
| `sector_intel_validation_smoke.py` | PASS | 0.79 |
| `sensor_detection_factor_smoke.py` | PASS | 3.56 |
| `ship_layout_output_smoke.py` | PASS | 0.23 |
| `ship_survey_radiation_smoke.py` | PASS | 0.23 |
| `smoke_test.py` | PASS | 0.34 |
| `textual_active_jobs_job_id_smoke.py` | PASS | 0.24 |
| `textual_command_spacing_smoke.py` | PASS | 3.65 |
| `textual_completion_context_smoke.py` | PASS | 1.95 |
| `textual_theme_smoke.py` | PASS | 3.77 |
| `transit_radiation_progression_smoke.py` | PASS | 0.17 |
| `uplink_authored_and_failsafe_smoke.py` | PASS | 0.53 |
| `uplink_once_per_node_smoke.py` | PASS | 0.36 |
| `uplink_only_delivery_retry_smoke.py` | PASS | 1.71 |
| `worldgen_manifest_integration_smoke.py` | PASS | 5.1 |
| `worldgen_manifest_prototype_smoke.py` | PASS | 2.84 |
| `worldgen_modules_pool_smoke.py` | PASS | 1.68 |
| `worldgen_preexistence_catalog_smoke.py` | PASS | 1.99 |
| `worldgen_preexistence_characterization_smoke.py` | PASS | 0.71 |
| `worldgen_sparse_archetypes_smoke.py` | PASS | 10.12 |

## Documentación, decisiones pendientes y entrega

Contrato técnico nuevo y manual comms EN/ES; boot/power y ayuda actualizados.
Navigation-recovery distingue lo implementado del inventario histórico. Scheduler,
failsafes y discovery/intel señalan la nueva recepción y el aplazamiento.
Roadmap v1.3 registra el acuerdo explícito e4b antes de e5; sus 24 filas D01–D24
permanecen idénticas a HEAD. Se añade su contraparte inglesa. Canon intacto.

Pendientes: balance definitivo de consumo/desgaste/estado mejorado, alcance
reducido, caducidad/ventanas del emisor, latencia, interferencias/intermitencia,
comunicaciones interestelares y recuperación estructural e5. No hay transmisión,
chat, transpondedor, combate ni gestor universal de sucesos.

ZIP de revisión: ../RETORNO-4D-3e4b-review.zip, con todos los 39 archivos
nuevos/modificados de esta fase, rutas relativas, sin saves, .git, temporales ni
archivos no cambiados. Se verifican inventario exacto, bytes y CRC de cada miembro;
SHA-256 en el .zip.sha256 adyacente y en la respuesta de entrega. No se introduce
el ZIP en el repositorio. Informe y evidencia JSON sí están incluidos.

## Inventario de archivos

| Archivo | Función |
| --- | --- |
| `data/manuals/commands/boot.en.txt` | Manual diegético EN/ES actualizado. |
| `data/manuals/commands/boot.es.txt` | Manual diegético EN/ES actualizado. |
| `data/manuals/commands/power.en.txt` | Manual diegético EN/ES actualizado. |
| `data/manuals/commands/power.es.txt` | Manual diegético EN/ES actualizado. |
| `data/manuals/systems/comms.en.txt` | Manual diegético EN/ES actualizado. |
| `data/manuals/systems/comms.es.txt` | Manual diegético EN/ES actualizado. |
| `docs/design/navigation-recovery-contract.es.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/design/navigation-recovery-contract.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/design/roadmap-worldgen-lore-f-dead01.es.md` | Roadmap v1.3 EN/ES; acuerdo e4b antes de e5, D01–D24 preservados. |
| `docs/design/roadmap-worldgen-lore-f-dead01.md` | Roadmap v1.3 EN/ES; acuerdo e4b antes de e5, D01–D24 preservados. |
| `docs/systems/discovery-navigation-intel.es.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/systems/discovery-navigation-intel.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/systems/exploration-failsafes.es.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/systems/exploration-failsafes.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/systems/lore-scheduler.es.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/systems/lore-scheduler.md` | Actualización EN/ES: implementado, histórico y pendiente. |
| `docs/systems/passive-communications.es.md` | Contrato técnico implementado EN/ES. |
| `docs/systems/passive-communications.md` | Contrato técnico implementado EN/ES. |
| `docs/testing/passive-communications-review.es.md` | Informe técnico para revisión externa EN/ES. |
| `docs/testing/passive-communications-review.md` | Informe técnico para revisión externa EN/ES. |
| `docs/testing/passive-communications-test-results.json` | Evidencia de base, final, grupos nuevos y comparación procedural. |
| `src/retorno/bootstrap.py` | Instala comms apagado usando la fábrica compartida. |
| `src/retorno/cli/repl.py` | Ayuda/diagnóstico/avisos EN/ES y marcas de lectura/importación. |
| `src/retorno/core/communications.py` | Predicado físico, ledger común, captura/reintento/lectura y diagnóstico EN/ES. |
| `src/retorno/core/deadnodes.py` | No crea puentes nuevos; etapas existentes gated e idempotentes. |
| `src/retorno/core/engine.py` | Boot revalidado, pérdida de servicio al apagar, carga real, avisos y reintentos. |
| `src/retorno/core/exploration_recovery.py` | Aplazamiento de creación legacy y broadcast de cadenas existentes. |
| `src/retorno/core/lore.py` | Escritores gated, contenido congelado, commit de productores tras recepción. |
| `src/retorno/io/save_load.py` | Default aditivo seguro para esquema 3 sin comms. |
| `src/retorno/model/ship_layout.py` | Ubica comms en BRG-01 existente. |
| `src/retorno/model/systems.py` | Fábrica física, flag de servicio, nombres EN/ES y defaults al cargar. |
| `src/retorno/model/world.py` | RadioOpportunity y colección/flag persistentes. |
| `src/retorno/ui_textual/presenter.py` | Añade al status las mismas líneas comunes, sin panel nuevo. |
| `tests/deadnode_cooldown_zero_smoke.py` | Conserva límites cero/positivos con puente preexistente y radio real. |
| `tests/exploration_recovery_smoke.py` | Verifica aplazamiento y cadena preexistente consumible. |
| `tests/known_routes_integrity_smoke.py` | Frontera inválida no produce activación correctiva ficticia. |
| `tests/narrative_world_integration_smoke.py` | Fixture local operativa para los mismos 20 grupos e4. |
| `tests/passive_communications_smoke.py` | 18 grupos de integración de la nueva fase. |
| `tests/uplink_authored_and_failsafe_smoke.py` | Uplink conserva contrato y no cuenta recuperación aplazada como éxito. |

Se detiene el trabajo para revisión externa, sin git add, commit ni push.
