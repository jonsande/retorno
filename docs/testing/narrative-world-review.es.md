# RETORNO — Informe 4D-3e4 para revisión externa

Fecha: 2026-11-05, Europe/Madrid. [English](narrative-world-review.md).
Estado: mínimo productivo implementado y probado, **pendiente de aprobación externa**.
El formato nuevo es provisional y optativo. No se declara resuelto F-DEAD-01.

## Corrección focal posterior a revisión externa

Esta revisión conserva HEAD `d851d441b0548eb67035d5aa8cdb298db0499800` en `main`
y los 38 archivos locales de la entrega anterior. Solo se han modificado los
ocho archivos enumerados abajo. No hay staging, commit ni push. La arquitectura,
el balance, Textual, audio, AMANECER y F-DEAD-01 permanecen como en la revisión
anterior. Los 18 grupos originales conservan íntegros sus cuerpos de prueba.

**Defecto 1 — tokens reservados sin bindings.** La detección de tokens pendientes
estaba dentro de `render()`, invocado únicamente si existía `spatial_bindings`.
Se reprodujo el arranque incorrectamente aceptado con `line: {{missing_9}}` sin
ese bloque. Ahora, tras completar el renderizado, se validan siempre `line`,
contenido inline, `content_ref`, `content_ref_en/es`, `files` y archivos authored
activos. Se conserva la procedencia del recurso original aunque su referencia
compilada sea privada. `ContentError` identifica paquete, archivo, campo y token.
Se mantiene exactamente la gramática reservada `[a-z][a-z0-9_]*` entre dobles
llaves; otras llaves y `[SECTOR_VAELOR]` son literales. No se infiere información
de prosa ni se activa contenido editorial.

**Defecto 2 — documento esencial sin cuerpo efectivo.** La oportunidad de
salvamento podía aprobarse solo por tener una ruta recuperable; los canales push
comprobaban la referencia, pero no su texto. Se reprodujo una pieza esencial sin
referencias ni `line` que superaba el arranque. Ahora se exige cuerpo no vacío
tras eliminar espacios para EN y ES, aplicando la precedencia y el fallback a EN
que ya usa la entrega real. La extracción del cuerpo de salvage se comparte
con `_file_for_salvage_piece`: conserva su fallback `line` cuando falta la
referencia o su texto es exactamente vacío, antes de añadir `log_header`.
Los canales push no adquieren ese fallback. Un texto solo de espacios, una
cabecera de log o los encabezados de correo no cuentan como cuerpo efectivo.
Un archivo referenciado ausente sigue fallando en carga, incluso si hay `line`.
Las comprobaciones de rutas/colisiones se mantienen. Los documentos opcionales
sin obligatoriedad siguen pudiendo tener cuerpo vacío; no cambian las políticas
de selección, colocación ni entrega.

**Pruebas nuevas.** Grupo 19: ocho campos/orígenes sin bindings, token desconocido
con bindings, resolución válida, llaves literales y catálogo sin declaraciones
físicas. Grupo 20: 48 combinaciones de cuatro canales y doce escenarios de
contenido; las entregas aceptadas se comprueban en EN y ES. Incluye vacío,
espacios, cabeceras solas, ES explícito vacío, texto válido, fallback a EN,
solo ES, `line`, referencia vacía con `line`, espacios con `line` y archivo
ausente. Dos casos adicionales cubren fallback desde `files` y opcional vacío.
Los nuevos grupos fallaron antes de la corrección y pasan después.

Resultado: **20/20 grupos narrativos PASS y 61/62 smoke scripts PASS** en serie.
Solo persiste el fallo previo de radiación `CARNAVAL_34`; Textual pasa en esta
ejecución. No ha sido necesario instalar dependencias. `git diff --check`: PASS.
La evidencia física y de variabilidad anterior se conserva sin cambios.

Archivos de esta corrección (la tabla al final incluye los 38 de la fase completa):

| Archivo | Corrección |
| --- | --- |
| `src/retorno/worldgen/narrative.py` | Validación final de tokens, independiente de bindings, con procedencia. |
| `src/retorno/core/lore.py` | Cuerpo efectivo EN/ES y helper de salvage compartido con entrega. |
| `tests/narrative_world_integration_smoke.py` | Grupos 19 y 20; los 18 previos no se modifican. |
| `docs/narrative-world-contract.es.md` | Precisión de gramática reservada y contenido esencial efectivo. |
| `docs/narrative-world-contract.md` | Contrapartida inglesa del contrato. |
| `docs/testing/narrative-world-review.es.md` | Informe actualizado y resultados de esta revisión. |
| `docs/testing/narrative-world-review.md` | Contrapartida inglesa del informe. |
| `docs/testing/narrative-world-test-results.json` | Ejecución completa y evidencia de ambas correcciones. |

El ZIP nuevo es `../RETORNO-4D-3e4-correction-review.zip`, con los **38 archivos**
modificados/nuevos de toda 4D-3e4, incluyendo la entrega anterior. Se conservan las
rutas relativas, se contrastan inventario y bytes contra el árbol y se verifica
el CRC. Su SHA-256 se entrega en el archivo `.zip.sha256` adjunto. El ZIP anterior
se conserva. No cambian comandos públicos ni manuales diegéticos en esta corrección.

## Resultado y estado Git

Rama: `main`; upstream: `origin/main`. HEAD inicial y final:
`d851d441b0548eb67035d5aa8cdb298db0499800`. El remoto se verificó con
`git ls-remote origin refs/heads/main` y coincide. Estado inicial limpio;
estado final con los cambios sin preparar enumerados al final. No se ejecutaron
`git add`, commit ni push. No hay cambios ajenos que preservar o mezclar.

El bootstrap real compila requisitos de todas las historias activas antes de
devolver una partida. El scheduler coloca en hosts preexistentes y los textos
espaciales se congelan por partida. Se entregan dos paquetes optativos y 20 grupos
de pruebas integradas. Los datos authored activos, los cinco singles actuales y
`narrative/amanecer/` no cambiaron; solo se actualizaron dos manuales bajo `data/`.

## Auditoría previa y fronteras reales

Se consultaron AGENTS, roadmap v1.2 D01–D24 y §3.4/3.5, canon y coherencia,
integración histórica, referencias de worldgen, scheduler, descubrimiento/intel,
carga, guías históricas y README/CANON/LOCATIONS de AMANECER. Se revisaron
bootstrap, loaders, manifiesto/generador, lore, Engine, REPL, modelos y save/load.

| Pregunta | Comportamiento auditado y adaptación |
| --- | --- |
| Activación | Solo localizaciones y arcos JSON de raíz; singles solo por índice. Cero arcos activos, cinco singles, cinco localizaciones. Ni plantillas ni Markdown editorial se recorren. |
| Datos anteriores al mundo | Antes: bootstrap materializaba base authored y capturaba reglas; el manifiesto se fijaba después. Ahora también se recoge el catálogo, valida y compila física/pistas y prepara reservas; con requisitos se fija el manifiesto en bootstrap. |
| Relecturas | Antes se releían arcos, singles, localizaciones y textos durante ticks, pools y entregas. Ahora hay snapshot; los loaders legacy siguen como puntos de dominio con verificación previa de archivos, y los nuevos requisitos consumen el snapshot compilado. Módulos/configuración física siguen sujetos a la huella anterior. Startup/manuales tienen sus loaders propios. |
| Creación ad hoc | Lore usaba `_spawn_ad_hoc_candidate_for_forced_piece` y muestreo de coordenadas para fabricar un host. Se sustituyó por `_select_historical_host_for_forced_piece`; se eliminaron los samplers y el nombre antiguo delega por compatibilidad. |
| Consumidores estructurales | `register_hidden_anchored_node` sigue usado por `exploration_recovery`; no se reescribió recuperación ni deadnodes. Su adaptación corresponde a e5. |
| Candidatos | Reglas de ID/familia/kind, región, tiempo, distancia, saltos, ventana y canal. El nuevo selector consulta cohortes certificadas, incluso no materializadas. Los singles mantienen su sorteo independiente. |
| Pools | Inicialización única por conocidos, ocultos forzados y anclas; rutas uplink congeladas; visita cierra ventana. Reservas se concretan antes del primer cierre cuando la política permite colocar. No se reabren fuentes agotadas. |
| Intel corrupta | Ya consultaba worldgen, sin fabricar una instalación específica del texto. Se conserva esa regla de descubrimiento legítimo, ahora con radio físico comprobado y token incierto registrado; no se usa como corrector narrativo. |
| Guardado | Pickle/checksum fijaba la física, pero las asignaciones podían releer otra definición/texto. Se persiste snapshot y se rechazan cambios de catálogo, evitando entregar otra pieza bajo una identidad anterior. |

## Formato propuesto y compilación

Contrato completo, ejemplos y matriz AMANECER: [guía de autoría](../narrative-world-contract.es.md).
Ejemplos auténticos: [`alpha.json`](../../tests/fixtures/narrative_world/alpha.json),
[`beta.json`](../../tests/fixtures/narrative_world/beta.json) y sus TXT EN/ES.
El test los instala exclusivamente en una copia temporal de `data`.

`world_requirements.version = narrative-world-v1` añade entidades, referencias,
relaciones y claims no vinculantes. Modos de posición: fija, caja sembrada o
offset sembrado de otra entidad; filtros de sector y región. Relaciones:
`near`, `physical_link` y `historical_association`, con comprobación de tipos.
Compartir exige referenciar, no redeclarar. No se infiere existencia de prosa
ni de `constraints` de documentos. Los formatos existentes siguen optativos.

Ejemplo real abreviado:

```json
{"id":"TEST_WRECK","kind":"ship","name":"Test Wreck",
 "position":{"offset_from":"Horizon","offset_box_ly":[[0.5,1.2],[0,0],[0,0]]}}
```

```json
{"type":"near","from":"TEST_STATION","to":"TEST_WRECK","min_ly":0.5,"max_ly":1.2}
```

El compilador resuelve identidades/alias, comprueba recursos y tipos, ordena
dependencias, prueba un dominio finito y verifica las relaciones sobre el
manifiesto productivo. Cada posición variable tiene 32 candidatos por semilla/ID;
el máximo de búsqueda es 4096 pasos. No se consume RNG de juego. Los conflictos
comprobados son `invalid` o `unsatisfiable`; la búsqueda incompleta es
`not_evaluated`, bloquea el inicio y nunca se presenta como satisfacción.
Una exigencia `physical_link` verifica la topología existente; no mueve sitios
fijos ni añade enlaces. El máximo sigue siendo 45 ly y puede haber aislamiento.

`spatial_bindings` de la misma versión admite valores `id`, `sector`, `coord`.
Solo reemplaza tokens explícitos `{{...}}` declarados en documentos. Se compila
`line`, texto inline y referencias a TXT a una dirección privada congelada.
La lectura no vuelve a escoger posición. `[SECTOR_VAELOR]` no se activa.

## Evidencia de variabilidad

Mismas dos historias, semillas 0–7. El pecio comparte Y/Z con la estación por
el offset declarado; se muestra su X y la posición completa de la estación.
El host fijo es `(26,27,1)` y el relé `(27,27,1)`: enlace físico certificado de 1 ly.

| Seed | Estación (x,y,z), ly | Pecio x, ly | Distancia, ly | Sector estación | Región |
| --- | --- | --- | --- | --- | --- |
| 0 | (150031.241312, 5.543181, 2.646261) | 150032.083876 | 0.842564 | S+15003_+000_+000 | halo |
| 1 | (150018.621699, 2.269562, 2.131623) | 150019.377670 | 0.755972 | S+15001_+000_+000 | halo |
| 2 | (149990.661433, 7.404138, 3.834968) | 149991.197861 | 0.536428 | S+14999_+000_+000 | disk |
| 3 | (150045.295446, 5.964927, 7.917574) | 150046.437712 | 1.142266 | S+15004_+000_+000 | halo |
| 4 | (150026.522888, 6.520925, 6.535723) | 150027.682503 | 1.159615 | S+15002_+000_+000 | halo |
| 5 | (150049.645549, 2.307534, 4.350687) | 150050.415146 | 0.769597 | S+15004_+000_+000 | halo |
| 6 | (150017.459114, 5.158522, 7.532469) | 150018.602833 | 1.143719 | S+15001_+000_+000 | halo |
| 7 | (150027.147820, 5.931495, 2.663212) | 150028.305660 | 1.157840 | S+15002_+000_+000 | halo |

Se verifican ocho posiciones diferentes, relación inclusiva 0.5–1.2 ly,
identidades iguales, pistas concordantes, independencia de lectura y exploración
y ausencia de revelación inicial. La caja se eligió expresamente junto al borde
disco/halo para demostrar variación geográfica. La muestra no prueba variedad
jugable universal, accesibilidad global ni descubrimiento garantizado.

## Efecto de authored sobre cupos y conectividad

Cuatro sitios nuevos; se comparan solo sus cohortes foco (dos en estas cuatro
semillas). Se muestran grafos **inducidos por esas cohortes**, no toda la galaxia.
Los datos incluyen además aristas incidentes e inventario por semilla.

| Seed | Sitios antes→después | Procedurales | Hubs | Aristas inducidas | Componentes inducidos |
| --- | --- | --- | --- | --- | --- |
| 0 | 4 → 5 | 4 → 1 | 0 → 3 | 2 → 3 | 2 → 2 |
| 1 | 5 → 5 | 5 → 1 | 0 → 3 | 3 → 3 | 2 → 2 |
| 2 | 1 → 4 | 1 → 0 | 0 → 3 | 0 → 2 | 1 → 2 |
| 3 | 5 → 5 | 5 → 1 | 1 → 3 | 4 → 4 | 2 → 2 |

Authored ocupa cupos existentes y puede superar el objetivo authored sin crear
slots procedurales extras. No se tocaron probabilidades ni cantidades. Se repitió
el comparador e2 con semillas `0..7,29,271828`: `aggregate`, todas las filas,
inventarios, recursos y configuración coinciden exactamente con las mediciones
versionadas; solo difieren tiempos/memoria de benchmark. No se reescriben testigos.

## Oportunidades, entrega y agotamiento

Antes de jugar se validan todos los `force=true` instalados como esenciales,
incluidos canal efectivo, ventana temporal y rutas de archivo recuperables.
La consulta finita admite hasta 64 sectores. Una búsqueda sin prueba no certifica
ausencia galáctica; restricciones de saltos sobre grafo parcial se reportan
conservadoramente. Se reserva host/canal/sector/procedencia sin revelar nada.

La política sigue decidiendo intentos. Al inicializar un pool, una reserva ya
elegible puede prepararse antes del cierre por visita. El documento puede alojarse
incluso en un pecio sin otros recursos. Asignación, preparación, trigger,
recepción y lectura/importación permanecen distintas. Un deadline posterior a
la limpieza deja la pieza pendiente: nunca reabre el pool ni añade historia.
Se prueban salvage con dron real y los cuatro canales de entrega restantes.
Los singles conservan `p = clamp(base × weight)`: peso 0.4 con base 0.05 da 0.02;
no aparecer no elimina la física declarada. Las colisiones de ruta de archivo
no sustituyen silenciosamente documentos.

## Compatibilidad de intel

| Sintaxis | Resultado verificado |
| --- | --- |
| `NODE:` | ID/nombre/alias válido resuelve historia y materializa lazy; inválido o pendiente queda como referencia sin estación fabricada. |
| `LINK:` | Extremos físicos y salto ≤45 ly; conserva intel de extremos ausentes y saltos excesivos sin publicarlos. Sigue el contrato operativo 4D-1, que no exige arista histórica. |
| `SECTOR:` | Intel regional y materialización lazy; no revela inventario. |
| `COORD:` | `NAV_...` de tipo `nav_point`, sin estación ni ruta automática; números finitos. |
| `[INTEL]` | ID/nombre/alias authored y selector bare de sector; bloques explícitos pasan al parser de líneas sin corrupción extra. Prosa normal no se reconoce como declaración. |
| Corrupción | Token incierto con confianza cero; descubrimiento existente acotado por radio y protección de primaries. No crea instalaciones correctivas. |

El parser es compartido entre lectura e import explícito. Las excepciones
deliberadas de scan y solve manual permanecen. Las protecciones también resuelven
alias del objetivo primary a su ID canónico.

## Persistencia y versionado

Snapshot persistido: versión de contrato, huella de catálogo activo, definiciones,
textos renderizados, aliases, posiciones, relaciones/resultados y reservas. El
manifiesto conserva authored definitivo e identidad de catálogo si hay nuevas
declaraciones. Sin bloques nuevos conserva su ámbito físico previo.

Política elegida: rechazar save/load si cambia el catálogo instalado, incluidos
textos referenciados, identidad o retirada de un paquete. Restaurar los originales
permite cargar; el archivo no se borra. El runtime con requisitos consume el
snapshot y no entrega una definición diferente. Las pruebas hacen tres ciclos
de guardado/carga conservando mundo, rutas, conocimiento y progreso.

El contenedor V2 y esquema 3 se conservan con un campo añadido. Las partidas
anteriores sin snapshot obligatorio se rechazan claramente, sin migración ni
borrado. Los cambios físicos siguen sujetos además a la huella previa de reglas.
No se reconstruyen emplazamientos a partir del catálogo modificado.

## Aceptación roadmap §3.4 y §3.5

| Requisito | Evidencia |
| --- | --- |
| §3.4.1 Declaración authored estable y secreta | Nuevos grupos 01–03; regresión manifest integration. |
| §3.4.2 Mención frente a intel | Grupos 01,07,12 y prosa de ambos paquetes. |
| §3.4.3 NODE válido/inválido/pendiente | Grupo 07, por lectura e import explícito. |
| §3.4.4 LINK válido/ausente/sobre cap | Grupos 04,07,11,14; known_routes_integrity. |
| §3.4.5 SECTOR/COORD distintos de estación | Grupo 07; sector_intel_validation. |
| §3.4.6 Forzado y single sobre hosts legítimos | Grupos 04,05,14,15; lore regression. |
| §3.4.7 Sin creación retrospectiva de lore | Grupos 04,12,15; manifiesto idéntico antes/después y creador dinámico prohibido durante prueba. |
| §3.4.8 Sin reapertura | Grupo 06 y fixtures de pools/deadnodes. |
| §3.4.9 Save/load repetido | Grupos 08,17; save_load, scan memory, waypoint y manifest integration. |
| §3.5.1 Dos paquetes, órdenes y exploración | Grupo 02; compilación con records invertidos y materialización inversa. |
| §3.5.2 Autoría sin Python específico | Alpha/beta usan solo contrato genérico y bootstrap real. |
| §3.5.3 Contradicciones antes de jugar | Grupos 09,11,13,17,18; diagnósticos en JSON. |
| §3.5.4 Prosa, rumor e intel | Grupos 01,07,12 y claims sin efecto físico. |
| §3.5.5 Opcional ausente, física estable | Grupo 05, probabilidad cero de prueba y mismo emplazamiento. |
| §3.5.6 Versionado y catálogo modificado | Grupos 08,17: modificación, retirada y save sin snapshot rechazados. |
| §3.5.7 Medición de authored | Grupo 10 y comparador productivo de diez semillas. |

Todos esos casos pasan en el alcance finito documentado. No se promete resolver
restricciones arbitrarias, cualquier semilla o cualquier conjunto de paquetes.

## Resultados de pruebas

Intérprete exclusivo: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.
Los tests del repositorio son scripts con runner propio; no hay pytest instalado.
Batería inicial: 60/61 PASS. Batería final serial: **61/62 PASS**; la nueva prueba
incluye **20 grupos PASS**: los 18 originales y dos nuevos para esta corrección focal. Comparador productivo: PASS en diez semillas.

Se conserva el fallo anterior `radiation_hull_smoke.py:183`, `AssertionError: []`
en el testigo `CARNAVAL_34` relacionado con radiación. No se modificó esa prueba
ni código de radiación. La prueba Textual de tema mostró `NoMatches #header`
intermitente en ejecuciones concurrentes. Se reprodujo también en el HEAD
original exportado a `/tmp` (1 fallo de 4 ejecuciones concurrentes); pasa aislada
y en la batería final serial. No se modificaron UI ni audio para ocultarlo.

| Script | Resultado final | Segundos |
| --- | --- | --- |
| `audio_config_smoke.py` | PASS | 1.26 |
| `audio_runtime_notice_smoke.py` | PASS | 0.07 |
| `config_audio_smoke.py` | PASS | 0.17 |
| `contacts_sector_smoke.py` | PASS | 0.16 |
| `contacts_smoke.py` | PASS | 0.23 |
| `deadnode_chain_detours_smoke.py` | PASS | 3.46 |
| `deadnode_chain_planner_smoke.py` | PASS | 4.24 |
| `deadnode_cooldown_zero_smoke.py` | PASS | 0.37 |
| `deadnode_opportunity_selection_smoke.py` | PASS | 5.04 |
| `debug_add_commands_smoke.py` | PASS | 0.22 |
| `debug_galaxy_smoke.py` | PASS | 0.27 |
| `debug_lore_arcs_smoke.py` | PASS | 0.26 |
| `debug_worldgen_graph_smoke.py` | PASS | 0.26 |
| `drone_completion_context_smoke.py` | PASS | 0.22 |
| `drone_modular_v1_smoke.py` | PASS | 1.04 |
| `drone_recall_all_smoke.py` | PASS | 0.26 |
| `drone_salvage_survey_smoke.py` | PASS | 0.70 |
| `energy_policy_smoke.py` | PASS | 3.20 |
| `exploration_recovery_smoke.py` | PASS | 0.60 |
| `forced_hidden_ad_hoc_smoke.py` | PASS | 0.31 |
| `galaxy_physical_model_smoke.py` | PASS | 0.18 |
| `hibernate_radiation_wake_smoke.py` | PASS | 0.32 |
| `hibernate_sequence_assets_smoke.py` | PASS | 0.03 |
| `intel_recent_order_smoke.py` | PASS | 0.47 |
| `job_id_numbering_smoke.py` | PASS | 0.24 |
| `known_routes_integrity_smoke.py` | PASS | 2.48 |
| `lore_channel_preference_and_unlock_smoke.py` | PASS | 0.20 |
| `lore_distance_from_start_smoke.py` | PASS | 0.15 |
| `lore_secondary_count_weights_hard_smoke.py` | PASS | 1.07 |
| `lore_smoke.py` | PASS | 0.16 |
| `mail_metadata_and_log_header_smoke.py` | PASS | 0.23 |
| `narrative_world_integration_smoke.py` | PASS | 19.16 |
| `nav_abort_waypoint_cleanup_smoke.py` | PASS | 3.62 |
| `nav_map_galaxy_dependencies_smoke.py` | PASS | 0.22 |
| `nav_map_galaxy_determinism_smoke.py` | PASS | 0.27 |
| `nav_map_galaxy_smoke.py` | PASS | 0.25 |
| `procedural_radiation_smoke.py` | PASS | 0.16 |
| `radiation_hull_smoke.py` | FAIL previo / preexisting | 1.14 |
| `route_hop_cap_smoke.py` | PASS | 0.25 |
| `route_solve_out_of_range_origins_smoke.py` | PASS | 0.37 |
| `save_load_smoke.py` | PASS | 0.35 |
| `scan_job_smoke.py` | PASS | 0.47 |
| `scan_observation_memory_smoke.py` | PASS | 10.41 |
| `sector_intel_validation_smoke.py` | PASS | 0.76 |
| `sensor_detection_factor_smoke.py` | PASS | 3.49 |
| `ship_layout_output_smoke.py` | PASS | 0.22 |
| `ship_survey_radiation_smoke.py` | PASS | 0.22 |
| `smoke_test.py` | PASS | 0.34 |
| `textual_active_jobs_job_id_smoke.py` | PASS | 0.24 |
| `textual_command_spacing_smoke.py` | PASS | 3.74 |
| `textual_completion_context_smoke.py` | PASS | 1.91 |
| `textual_theme_smoke.py` | PASS | 3.79 |
| `transit_radiation_progression_smoke.py` | PASS | 0.16 |
| `uplink_authored_and_failsafe_smoke.py` | PASS | 0.57 |
| `uplink_once_per_node_smoke.py` | PASS | 0.36 |
| `uplink_only_delivery_retry_smoke.py` | PASS | 1.68 |
| `worldgen_manifest_integration_smoke.py` | PASS | 5.05 |
| `worldgen_manifest_prototype_smoke.py` | PASS | 2.81 |
| `worldgen_modules_pool_smoke.py` | PASS | 1.66 |
| `worldgen_preexistence_catalog_smoke.py` | PASS | 1.99 |
| `worldgen_preexistence_characterization_smoke.py` | PASS | 0.69 |
| `worldgen_sparse_archetypes_smoke.py` | PASS | 10.20 |

Los JSON [resultados](narrative-world-test-results.json) y
[mediciones](narrative-world-measurements.json) incluyen base inicial, ejecución
final, grupos nuevos, reproducción del fallo intermitente, posiciones, distancias,
diagnósticos y comparación física. Solo se usaron partidas temporales; no se
abrió ni modificó un save real. La UI se ejercitó mediante sus smoke tests
headless; no se realizó una sesión audiovisual manual de e6.

## Matriz AMANECER

| Categoría | Elementos |
| --- | --- |
| Soportado | Tábano `ship` con posición variable e identidad estable; documentos por ID del host; sector/coord dinámicos; destino físico y enlace directo certificado. |
| Adaptación de datos pendiente | JSON declarativos, TXT EN/ES, cajas/regiones/relaciones y canales; ruta del Tábano ligada a destino real con acceso comprobado concreto. |
| Decisión editorial | Estado presente y kind jugable de Bruma; Liria jugable; naturaleza del destino sospechoso; suerte de las siete personas. |
| Sistema no implementado | VAELOR como sistema estelar, planetas/componentes; conservación física dinámica y cronología/supervivencia simuladas. |

No se activó AMANECER ni se copiaron sus Markdown. No se inventaron coordenadas
canónicas, destinos editoriales, planetas independientes ni hechos sobre personas.

## Documentación, decisiones pendientes y límites

La guía nueva EN/ES es normativa para este cambio, con ejemplos ejecutados.
Las guías anteriores tienen una advertencia explícita que identifica los apartados
superados, manteniendo su contexto histórico. Los manuales de intel son bilingües
y diegéticos. `help` y `help --verbose` no necesitan cambios: no hay comandos,
canales ni nueva sintaxis de intel pública; los bloques de autoría se explican en
la guía técnica. Se revisaron pares EN/ES, tokens de fixtures y enlaces añadidos.

Pendiente de aprobación: estabilizar `world_requirements`/`spatial_bindings` como
interfaz pública definitiva y aceptar sus límites finitos. Decisiones editoriales
de AMANECER siguen abiertas. Camino multihop declarativo general, sistemas
planetarios, fechas históricas y gestor de mods siguen fuera del contrato.
e5 conserva la integración de recuperación estructural. No hay un bloqueo nuevo
que exija ampliar esta fase; no se presenta la integración como un solver universal.

`git diff --check`: **PASS**, sin salida. El ZIP de revisión se verifica comparando
inventario y bytes de cada miembro con el árbol, conservando rutas relativas y
conteniendo exclusivamente archivos nuevos/modificados. Se deja fuera del repo:
`../RETORNO-4D-3e4-correction-review.zip`. No contiene saves, `.git`, código no cambiado ni
los árboles temporales de prueba. Su SHA-256 se entrega junto al ZIP.

## Archivos modificados o nuevos y función

38 archivos en esta entrega, sin staging. El ZIP incluye también este
informe y su versión inglesa.

| Archivo | Función |
| --- | --- |
| `data/manuals/commands/intel.en.txt` | Manual operativo intel EN/ES actualizado. |
| `data/manuals/commands/intel.es.txt` | Manual operativo intel EN/ES actualizado. |
| `docs/arcs.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/arcs.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/content-loading.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/content-loading.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/design/historical-worldgen-integration.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/design/historical-worldgen-integration.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/intel_lore.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/intel_lore.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/narrative-world-contract.es.md` | Guía vigente EN/ES con ejemplos reales y límites. |
| `docs/narrative-world-contract.md` | Guía vigente EN/ES con ejemplos reales y límites. |
| `docs/systems/discovery-navigation-intel.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/systems/discovery-navigation-intel.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/systems/lore-scheduler.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/systems/lore-scheduler.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/systems/world-generation.es.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/systems/world-generation.md` | Actualización EN/ES y advertencia sobre el cuerpo histórico superado. |
| `docs/testing/narrative-world-measurements.json` | Evidencia reproducible de pruebas o mediciones. |
| `docs/testing/narrative-world-review.es.md` | Informe de revisión externa EN/ES. |
| `docs/testing/narrative-world-review.md` | Informe de revisión externa EN/ES. |
| `docs/testing/narrative-world-test-results.json` | Evidencia reproducible de pruebas o mediciones. |
| `src/retorno/bootstrap.py` | Compilación previa; sitios declarados lazy y sin contactos iniciales. |
| `src/retorno/cli/repl.py` | Parser intel compartido, alias, resolución histórica, incertidumbre y radio de recuperación. |
| `src/retorno/core/lore.py` | Oportunidades esenciales, reservas y selección histórica; pools y entrega. |
| `src/retorno/io/save_load.py` | Huella de catálogo obligatoria y rechazo seguro de incompatibilidades. |
| `src/retorno/model/world.py` | Snapshot narrativo persistente. |
| `src/retorno/runtime/data_loader.py` | Frontera no recursiva compartida con procedencia e índice estricto. |
| `src/retorno/worldgen/generator.py` | Integración del snapshot en identidad y materialización authored. |
| `src/retorno/worldgen/manifest.py` | Identidad opcional de catálogo dentro del ámbito del manifiesto. |
| `src/retorno/worldgen/narrative.py` | Compilador, validación, catálogo, geometría finita y bindings versionados. |
| `tests/fixtures/narrative_world/alpha.en.txt` | Paquete sintético optativo o texto bilingüe; no se activa en producción. |
| `tests/fixtures/narrative_world/alpha.es.txt` | Paquete sintético optativo o texto bilingüe; no se activa en producción. |
| `tests/fixtures/narrative_world/alpha.json` | Paquete sintético optativo o texto bilingüe; no se activa en producción. |
| `tests/fixtures/narrative_world/beta.en.txt` | Paquete sintético optativo o texto bilingüe; no se activa en producción. |
| `tests/fixtures/narrative_world/beta.es.txt` | Paquete sintético optativo o texto bilingüe; no se activa en producción. |
| `tests/fixtures/narrative_world/beta.json` | Paquete sintético optativo o texto bilingüe; no se activa en producción. |
| `tests/narrative_world_integration_smoke.py` | 20 grupos de aceptación por bootstrap/runtime/save reales. |
