> **4D-3e5 — estado vigente (2026-11-06).** Implementado el selector histórico, confirmación transaccional y recepción/progresión mediante el ledger común. El [contrato productivo](../systems/structural-recovery.es.md) y su informe prevalecen sobre las auditorías históricas de este documento: no se fabrican puentes, entradas ni gateways. El núcleo 3b/3c/3d sigue siendo diagnóstico; no autoriza materialización. Sin garantía de salida universal.

# Núcleo de propuestas de cadenas deadnode — Fases 4D-3b/3c/3d

Versión inglesa: [deadnode-chain-planner.md](deadnode-chain-planner.md).

API implementada: `propose_deadnode_chain(state, target_id, PlanningContext())`
en [`core/deadnode_planner.py`](../../src/retorno/core/deadnode_planner.py).
Calcula un valor inmutable sin confirmar. `evaluate_dead_nodes` no la invoca;
no activa nodos, enlaces, archivos, planes ni recepción.
**F-DEAD-01 permanece abierto.** El [contrato de navegación/recuperación](navigation-recovery-contract.es.md)
es vinculante; worldgen sigue regido por [su referencia canónica](../systems/world-generation.es.md).

## Decisión aprobada y limitaciones anteriores

**Precisión 4D-3e1:** el [contrato y auditoría de preexistencia](procedural-preexistence.es.md)
prevalece sobre interpretar cupos o centros geométricos como localizaciones
históricas verificadas. El catálogo no certifica latentes con el generador actual.
Este planificador sigue igual y sin integrar. El estado por capacidad/dependencias
de 4D-3d y la comparación de tiempo nominal no son la elegibilidad estructural
recién aprobada; daños, energía, scrap y reparaciones no deben decidir aceptación
de F-DEAD-01. La auditoría registra la separación necesaria y la futura búsqueda
progresiva acotada; las herramientas económicas pueden seguir como información.

**Buscar alternativas regionalmente coherentes y rodeos antes de desistir; no
garantizar salida ni crear excepciones a las reglas del universo.** Un viaje
más largo por otra región puede ser apropiado. Una rama sin recuperación también
puede ser una situación jugable válida. No se conceden recursos, drones, energía
ni reparaciones.

4D-3b ya buscaba rodeos arbitrarios por nodos existentes y conectores mixtos a
través de extremos existentes. No exigía alineación. Sus intermediarios nuevos
eran sólo subdivisiones equidistantes de conectores rectos; no movía posiciones
sin cupo. Las etiquetas conservaban reservas, pero la expansión ilimitada entre
todos los pares podía crecer combinatoriamente. `conditional` significaba tipo
y capacidad respaldados con inserción, pools y topología pendientes, nunca
permiso para crear un nodo.

Sondas aisladas previas con seed `271828` confirmaron:

- A=(0,25,1), B=(20,55,1), C=(50,55,1), D=(70,25,1) ya daban un rodeo existente:
  36,0555 + 30 + 36,0555 ly.
- A=(0,1,1), D=(100,1,1) daban dos intermediarios rectos sin tipo y un testigo
  incompleto: los sectores rectos correspondientes no tienen cupos.
- Sondas desconectadas sólo con existentes y 0/100/1000 nodos de fondo tardaron
  unos 1,25/1,75/8,60 ms; eran sondas dispersas, no cotas de peor caso.

## Representación independiente

Las dataclasses congeladas `RecoveryProposal`, `Stage`, `ProposedNode`, `Hop`,
`Hint`, `Dependency`, `MaterializationCheck`, `SearchReport`, `SearchBudget` y
`PlanningContext` sólo contienen valores/tuplas independientes. `origin_access_path`
registra el viaje dirigido conocido hasta el origen elegido; no mueve la nave.

| Campo | Significado |
| --- | --- |
| `geometry_valid` | Testigo completo con segmentos mayores que cero y de hasta 45 ly. |
| `physical_chain_valid` | Extremos existentes o tipos/cupos canónicos propuestos; la inserción sigue condicionada. |
| `information_status` | Mecánicas `verified`, recepción `future_required` o fuente indispensable `unavailable`. |
| `materialization` | `existing`, `conditional` o `unavailable`. |
| `viability` | `verified`, `conditional`, `incomplete` o candidato `rejected`; nunca rescate confirmado. |
| `checks` | Evidencia por nodo marcada `checked`, `conditional` o `inadmissible`. |
| `search` | Contadores deterministas, sectores muestreados, dominio y presupuestos agotados; sin tiempos reales. |

`ready_with_existing_mechanics` sólo valora la propuesta. Un LINK legible ya
almacenado puede evitar recepción nueva; una primera señal nueva sigue
necesitando futuros `comms`, `radiod` y captura/importación progresiva. No se
añaden campos de guardado de planes activos.

## Dominio de búsqueda, orden y límites técnicos

Los orígenes conservan gates de candidato por contacto/forced-hidden, pool limpio
y alcance base de sensores. `reachable_known_nodes` más `reachable_from` dirigido
y conocimiento normal de viaje rechazan aristas inversas/obsoletas y orígenes a
través de desconocidos. Un waypoint detenido es elegible; un viaje activo se
rechaza. El llamador sigue siendo responsable de los umbrales temporales.

1. Primero se busca en el grafo físico existente. Un índice espacial con celdas
   de 45 ly enumera extremos vecinos, incluidas localizaciones fuera de línea y
   en otras regiones; se comprueba la viabilidad informativa antes de guardar
   cada arista.
2. Si hace falta, se busca en un grafo ampliado. Se conservan subdivisiones
   rectas hacia el objetivo y los 16 extremos existentes más cercanos en el cubo
   circundante de cinco celdas. Se añaden sondas sectoriales condicionadas desde
   corredores alrededor de cada segmento origen-objetivo. La preferencia de
   reutilización ordena por nodos nuevos, saltos, distancia total e ids completos
   ordenados. Si funciona sólo con existentes, ni se generan sondas candidatas.
   Las cadenas mixtas con menos nodos nuevos ganan a las totalmente nuevas aun
   siendo más largas. Con igual cantidad se aplican los demás criterios.
3. Las sondas usan separación longitudinal máxima de 22,5 ly y bases ortogonales
   reproducibles en 3D (eje menos alineado, empates estables). Anchuras 10/20/40 ly
   muestrean el centro y ocho desplazamientos. Los flujos se intercalan por
   origen y anchura y se eliminan sectores duplicados. Los centros sectoriales
   son **sondas geométricas**, no coordenadas procedurales aprobadas. Un cupo
   previsto positivo habilita un candidato condicionado, nunca inserción confirmada.
4. A* usa cotas inferiores admisibles por distancia y componente física existente
   del objetivo, ignorando información sólo en la heurística. Cada arista exige
   el mecanismo informativo real y `is_hop_within_cap` compartido. Las etiquetas
   conservan cupos reservados; etiquetas más baratas con un subconjunto dominan
   otras más caras en el mismo extremo. Se excluyen ciclos y posiciones repetidas.
   Las cachés de pistas, intel, cupos y heurísticas son locales a la llamada.

`SearchBudget` predeterminado: 512 expansiones, 1024 aristas evaluadas y 512
etiquetas por pasada; 256 muestras brutas de corredor y 256 intermediarios por
conector recto. Son cotas técnicas configurables, **no un máximo jugable de
etapas**. La regresión de doce saltos sigue siendo válida. Contar muestras brutas
también acota corredores superpuestos. El precálculo acotado de componente
inversa usa una cota conservadora cuando la componente es grande.

Un presupuesto agotado aparece en `search.exhausted` y
`search_budget_exhausted`. Una cadena completa ya encontrada puede devolverse
con esa advertencia; su selección no está demostrada óptima. En otro caso se
devuelve `incomplete`, posiblemente con testigo geométrico diagnóstico cuyas
fuentes/cupos no disponibles se explicitan. Se omite el diagnóstico geométrico
opcional sólo con existentes tras agotar presupuesto. Ningún resultado demuestra
imposibilidad espacial universal. Los corredores finitos, extremos muestreados
y la política canónica de primer cupo libre tampoco constituyen búsqueda
exhaustiva aunque no se agote el presupuesto. No se afirma optimalidad sobre
posiciones arbitrarias, todos los órdenes de cupos ni todos los rodeos regionales.

El mundo se indexa y la intel legible se analiza una vez por llamada.
`_plan_sector_kinds` canónico se ejecuta sobre una vista independiente indexada
por sector, con la misma seed y nodos físicos, evitando recorrer el mundo por
cada previsión. Esta función y `_select_archetype` siguen siendo dueñas de pesos,
caps, conteos y aleatoriedad. Hace falta la vista porque la consulta pura vigente
recibe un estado, no una colección de nodos sectoriales; worldgen no cambia.

## Información y narrativa

Cada salto dirigido considera: ruta operativa conocida, intel de enlace o
archivo legible no corrupto de la nave, route solve normal hacia destino conocido
dentro del alcance efectivo, primera señal de recuperación y fuente local fresca.
Estas comprobaciones no publican `known_links`. Etapas con rutas/intel/resolución
existentes pueden ser sólo de navegación; no hace falta archivo obligatorio nuevo
en cada escala. Un camino corto con receptor inutilizable pierde ante otro más
largo que sí permite progresar.

La primera señal nueva se captura en la nave, incluso si el origen elegido es
otro nodo alcanzable. Las fuentes posteriores obligatorias exigen nodo no
visitado, ventana abierta y pool no limpio. Datos de salvage completados y uplink
consumido siguen siendo fuentes distintas no disponibles; no se reabre ningún
pool. Se prepararán fuentes antes de revelar/visitar. Reservar una pista uplink
sigue siendo política pendiente, no autoridad para reescribir un pool congelado.
Los gates normales de hardware, docking, drones y operador siguen explícitos.

| Tipo | Capacidad informativa local real |
| --- | --- |
| `relay` | `salvage_data`, `uplink` |
| `station` | `salvage_data`, `uplink` |
| `waystation` | `uplink`; Engine rechaza `SalvageData` |
| `derelict` | `salvage_data` |
| `ship` | `salvage_data` |

No se convierte ningún tipo existente. Los tipos desconocidos/prohibidos y la
capacidad canónica no disponible nunca se sustituyen por infraestructura
conveniente. La protección reutiliza `_locked_primary_targets` para primaries
NODE/LINK finales e intermedios. Se excluye el atajo protegido y se continúa
buscando alternativas. Los formatos bloqueados no soportados fallan de forma
conservadora con `primary_protection_query_incomplete`. Un host en
`forced_hidden_nodes` no está prohibido por sí solo. Scan natural y route solve
manual conservan sus excepciones aprobadas.

## Comprobación de materialización e inserción tardía

Cada nodo nuevo describe identidad, coordenadas, región real, sector/arquetipo,
tipo y primer cupo canónico libre. Comprueba colisiones de identidad reales y
locales, colisiones exactas de coordenadas, elegibilidad regional, capacidad y
reservas compartidas de propuesta. Las colisiones de ids se resuelven con nonces
locales deterministas sin asignar ids del juego. La elegibilidad de cupo no
valida coordenadas muestreadas. También se consideran ocupados ids pendientes
en conocimiento, pools, topología, índices sectoriales e intel histórica.

Las dependencias condicionadas incluyen `atomic_idempotent_materialization`,
`coordinate_slot_insertion_policy`, `pool_preparation_before_revelation` y
`lazy_sector_slot_reservation` o `late_sector_topology`. Sectores generados/con
estado añaden `generated_sector_insertion_policy`; un sector con nodo físico
visitado añade `explored_sector_appearance_policy`. La diferencia entre región
del centro/posición añade `sector_boundary_region_policy` y sigue exigiendo un
arquetipo admitido en la posición real. Metadatos sectoriales incoherentes añaden
`sector_metadata_reconciliation`; no se reparan implícitamente. Un guardrail inicial pendiente queda
explícito. El `Hint` de la etapa y sus restricciones también describen el trabajo
de pool/fuente.

`sync_sector_state_for_node` puede actualizar índices existentes, pero no
reconstruye topología interna cerrada; no se reintentan pares intersectoriales
evaluados. La generación lazy cuenta nodos físicos y puede cambiar la previsión
restante. El registrador anclado actual crea estado vivo, enlaces y pools, puede
invocar generación adicional y no es idempotente; el escritor de pistas también
produce archivos/eventos nuevos al repetirse. Ninguno es una transacción ni se
invoca aquí.

Escalas físicas, rutas dirigidas y fuentes utilizables existentes no necesitan
política de aparición. Una escala nueva propuesta en sector generado/visitado
sigue condicionada. Para el jugador: **¿puede una zona ya explorada contener más
tarde una localización de recuperación antes desconocida, y cómo se enteraría?**
Esta fase no decide esa política. Un centro sectorial, capacidad libre o pool
abierto no bastan para responderla.

## Confirmación atómica futura — sólo diseño

Una implementación posterior debería preparar una transacción independiente
con clave de oportunidad y huella de instantánea. Primero debe resolver todas
las políticas de inserción pendientes. Revalidar protección, orígenes, saltos,
receptores, conteos físicos e identidades/coordenadas/reservas propuestas contra
el estado más reciente. Preparar la cadena completa, nunca sólo el primer puente.

El conjunto de escrituras debe incluir nodos físicos e identidades, coordenadas
y cupos, índices/hubs sectoriales, enlaces físicos permitidos y sus presupuestos/
pares, pools inicializados y archivos/reservas exactos de fuentes, identidad de
plan activo, estado de etapas y dependencias de recepción pendiente. Validar que
ninguna fuente visitada/consumida reciba contenido obligatorio y que se respeten
los caps topológicos. No reconstruir topología ni añadir conocimiento implícito.

Construir y validar esas escrituras sobre una instantánea independiente; publicar
el estado coherente de mundo/plan en un único punto de confirmación propiedad del
motor, sin entrega visible antes. Una preparación fallida/obsoleta descarta el
resultado independiente, no consume intento ni inicia cooldown. Confirmar de
nuevo la misma identidad debe devolver el mismo plan activo, no volver a llamar
registradores que asignan ids. La publicación durable usará el límite de guardado
existente sólo cuando el estado sea coherente; esquema/versión del plan activo
y detalles del punto atómico pertenecen a esa fase posterior.

Recepción, captura e importación seguirán como transiciones persistidas distintas
con claves de idempotencia. Un receptor pendiente no equivale a rescate exitoso.
El momento exacto de inicio de intento/cooldown respecto a preparación/captura
aún necesita decisión explícita de integración; ningún contador actual cambia.
Nada de esta transacción, comunicaciones o persistencia se implementa en 4D-3c.

## Mediciones y verificación

Reproducir con el Python canónico:
`tests/deadnode_chain_detours_smoke.py --benchmark`. Usa seed `271828`, tres
llamadas por celda, estados sintéticos aislados, excluye construir fixtures y
registra mediana/máximo en milisegundos y contadores deterministas. Los fondos de
0/300/1200/3000 nodos físicos ocupan 300×300×60 ly lejos del recorrido; el caso
agotado los concentra cerca del origen, marca sus datos consumidos y usa objetivo
a 2000 ly. Las densidades/resultados son sintéticos, no frecuencias jugables.

Mediana / máximo, ms:

| Nodos de fondo | Sólo existentes | Nuevos rectos | Rodeo | Presupuesto agotado |
| --- | --- | --- | --- | --- |
| 0 | 3.51 / 4.93 | 16.39 / 16.78 | 30.22 / 31.28 | 131.64 / 153.79 |
| 300 | 6.55 / 6.57 | 20.20 / 21.33 | 46.33 / 49.59 | 87.70 / 101.72 |
| 1200 | 15.81 / 16.37 | 32.83 / 39.09 | 47.67 / 48.75 | 80.20 / 89.52 |
| 3000 | 37.86 / 48.93 | 54.18 / 54.23 | 68.13 / 68.53 | 107.76 / 110.47 |

Indexar escala con el mundo físico y la intel almacenada. El trabajo de búsqueda
se acota con presupuestos técnicos, no combinaciones ilimitadas de reservas;
vecindarios densos y copias siguen siendo más caros. Las mediciones no garantizan
latencia máxima. La integración futura en Textual **deberá usar una instantánea
inmutable en un worker**, validar obsolescencia antes de confirmar y podrá ajustar
presupuestos técnicos/cachés. Aquí no se añade worker ni integración de UI.

Con seed `271828`, la fixture recta válida de 100 ly conserva dos nodos en y=25
y tres saltos de unos 33,3333 ly. En y=1, el rodeo nuevo propone (25,-5,5) y
(65,-5,5): unos 26,0192 + 40 + 35,7351 ly. Ambos tienen cupos canónicos; inserción
y primera recepción siguen condicionadas. Un nodo existente en (65,1,1) reduce
la propuesta a un intermediario nuevo. La fixture de frontera real disk/halo
cruza regiones sin cambiar balance ni definiciones regionales.

La [regresión original de 28 grupos](../../tests/deadnode_chain_planner_smoke.py)
y el [complemento 4D-3c](../../tests/deadnode_chain_detours_smoke.py) cubren juntos
la matriz solicitada (números de la solicitud 4D-3c):

| Casos | Cobertura ejecutable |
| --- | --- |
| 1 | `test_direct_viable_is_retained`, originales directo/45/70/100 |
| 2, 4 | `test_reference_seed_empty_straight_slots_find_offline_nodes` |
| 3 | `test_existing_detour_preferred_over_shorter_all_new` |
| 5 | `test_mixed_detour_minimizes_new_nodes` |
| 6 | `test_real_regional_boundary_with_existing_detour` |
| 7, 21 | `test_short_unusable_receiver_loses_to_longer_information_path` |
| 8 | `test_equal_alternatives_have_stable_tie_breaks` |
| 9, 18 | `test_regional_kind_restrictions_not_overridden` |
| 10 | `test_no_procedural_context_is_not_a_permission` |
| 11–15, 30–31 | `_checked`/`_plan` original comparan estado completo serializado/RNG global y cap positivo exacto mediante `_assert_hops`; originales de cap inclusivo |
| 16, 20 | `test_navigation_only_exhausted_stop_and_direction_preserved`, originales de orígenes dirigidos |
| 17 | Pruebas originales de tipos canónicos y capacidad waystation mediante Engine real |
| 19 | `test_shared_slot_reservations_and_coordinate_collision`; cada propuesta también exige reservas únicas |
| 22–23 | `test_protected_shortcut_excluded_alternative_retained`, originales NODE/LINK/primary no soportado |
| 24–25 | `test_sources_and_first_reception_remain_pending` |
| 26–27, 29 | `test_generated_explored_and_lazy_insertion_are_distinct` |
| 28 | `test_collision_safe_detour_identities`, colisión original de id y `test_pending_identity_references_are_not_reused` |
| 32–33 | `test_detour_save_load_hash_seeds_and_all_state_purity`, originales orden/guardado/hash |
| 34 | `test_budget_exhaustion_is_incomplete_not_universal_impossibility` |
| 35 | `test_populated_world_has_bounded_search_and_preserves_state`, benchmark |

Comparar el estado entero cubre mundo, topología sectorial, conocimiento/intel,
pools, filesystem, contadores/cooldown, RNG/secuencias, eventos, nave/recursos,
recuperación y tiempo. Tres ciclos temporales save/load y subprocesos con seeds
hash conservan propuestas. La previsión indexada se compara con la consulta canónica sobre el mundo completo
en `test_indexed_forecasts_match_the_canonical_full_world_query`. No se abren partidas reales. Pruebas específicas
prohíben llamar escritores/generadores. Manuales/help no necesitan cambios:
no cambia ningún comando del jugador.

## Decisiones de producto aún necesarias

- Si el jugador puede descubrir localizaciones nuevas de recuperación en áreas
  generadas/exploradas y cómo; qué sectores deben excluirse en su lugar.
- Cómo conviven coordenadas/cupos condicionados con muestreo lazy normal,
  guardrails iniciales y regiones en fronteras sin aumentar densidad.
- Cómo respetan enlaces/hubs físicos tardíos topología cerrada y presupuestos
  intersectoriales.
- Cómo reservar datos uplink indispensables sin reabrir pools congelados/
  consumidos y qué preparación de fuentes puede confirmarse atómicamente.
- Cuándo preparación/captura hace contar el rescate para intentos/cooldown,
  esquema del plan activo/recepción y semántica de invalidación/reintento.

La regla de rodeos aprobada no requiere otra aprobación. No se propone tipo,
peso, probabilidad, límite jugable de saltos ni garantía de supervivencia universal.

## Oportunidades contextuales — Fase 4D-3d

**Aprobado:** preferir oportunidades failsafe razonablemente cercanas, incluyendo
el trayecto de la nave al origen. La evidencia de frontera es secundaria frente
a la accesibilidad práctica; un territorio conocido cercano puede ser preferible
a otro desconocido lejano. Evitar retrocesos desproporcionados sin imponer un
nuevo límite fijo de distancia/saltos. Estos criterios se aplican a recuperación
deadnode, no a worldgen, lore, arcos o singles generales. Escaneo normal,
documentos, salvage, uplink cuando corresponda y futuras comunicaciones capturadas
siguen siendo vías legítimas. No se exige volver indiscriminadamente a nodos
antiguos para repetir escaneos. Localizaciones/pools completados siguen completos.
La recuperación no concede recursos ni garantiza supervivencia o éxito, y puede
no encontrar opción razonable. Sigue vigente la regla aprobada de rodeos regionales.

### API y compatibilidad

[`core/deadnode_opportunities.py`](../../src/retorno/core/deadnode_opportunities.py)
ofrece `evaluate_deadnode_opportunity(state, proposal)`,
`compare_opportunities(left, right)` y
`compare_deadnode_opportunities(state, target_ids, context, budget)`.
Los valores congelados tipados `OpportunityEvaluation`, `AccessRoute`,
`TerritoryEvidence`, `TravelCosts`, `Estimate`, `OpportunityComparison`,
`OpportunitySelection` y `OpportunityBudget` describen acceso, recorrido entero,
evidencia, incertidumbre y comparación parcial. No son planes activos ni añaden
esquema de guardado.

La API geométrica `propose_deadnode_chain` conserva comportamiento 4D-3c por
compatibilidad. Por sí sola no selecciona failsafes contextuales: sus orígenes
siguen empezando con coste geométrico de cadena cero. Su `origin_access_path`
por anchura favorece saltos e ids estables; un camino empatado en saltos puede
ser más largo. Una rama larga lexicográficamente anterior demuestra el límite
en la regresión 05.

La API contextual usa tres testigos Dijkstra dirigidos por origen alcanzable:
menor distancia de red, menos saltos y menor tiempo nominal. Sólo admite aristas
operativas F-ROUTE-01 y conocimiento normal del destino; contactos por sí solos,
aristas colgantes/inversas/fuera del cap/de longitud cero no conceden acceso.
Conserva alternativas de acceso, sin sustituirlas implícitamente en una propuesta
recibida. El evaluador independiente informa de entrada obsoleta/inaccesible,
sin mover la nave ni reparar conocimiento.

Una `_ChainSession` local comparte descriptores canónicos, catálogos, cupos,
intel legible, índices espaciales físicos, componentes relajadas del objetivo
y cachés de pistas entre objetivos/criterios. Muestrea la cadena geométrica
y dos objetivos prácticos A* con distancia/saltos reales de acceso en el coste
inicial. Conservan testigos sólo de existentes y pueden probar corredores mixtos/
nuevos cuando los caminos existentes no alcanzan ambas cotas geométricas de
distancia/saltos. Se pasan los resúmenes de acceso directamente, sin recalcularlos
para cada origen/objetivo. La heurística usa diferencia cero inmediatamente si
el nodo ya está en su componente relajada. Las etiquetas de origen son entrada
indexada; `SearchBudget.labels` acota etiquetas adicionales a esos orígenes.

Cada cadena se evalúa con las alternativas de acceso muestreadas para su origen.
Se eliminan testigos cadena/acceso duplicados. No se afirma cubrir todos los
caminos Pareto, pares origen-cadena ni optimalidad espacial global. La elegibilidad/
protección sigue en el núcleo de cadenas; umbrales, tiempos y
`evaluate_dead_nodes` permanecen sin cambios.

### Recorrido completo y economía condicionada

El trayecto registrado es nodo actual → acceso dirigido → origen → etapas →
objetivo. Se separan métricas de acceso y cadena y los totales incluyen ambas
distancias y saltos. La distancia euclidiana nave-objetivo es otro campo. Elegir
otro origen nunca recoloca gratis la nave. Quedan explícitos ids reutilizados/
nuevos, saltos con rutas conocidas, territorio por nodo y dependencias de
información/materialización/recepción.

| Evidencia/estimación | Autoridad canónica y límites |
| --- | --- |
| Segundos nominales de tránsito | `Engine.Travel`: distancia dividida por `ShipState.effective_cruise_speed()` por `Balance.YEAR_S` (velocidad cero no tiene estimación); viaje local usa km finos divididos por `max(0.1, LOCAL_TRAVEL_SPEED_KM_S)`. `_compute_fine_range_km` de sólo lectura aporta un rango local ausente. |
| Energía CRUISE condicionada | `Engine._compute_load_kw` y `Engine._compute_p_gen` de sólo lectura sobre vista independiente de sistemas auto-CRUISE, excluyendo jobs. kW constantes × segundos nominales / 3600 dan kWh brutos de demanda/generación. |
| Evolución real de batería/red | Desconocida: `Engine._update_battery` limita carga/descarga y aplica eficiencias; calidad, shedding, cambios de estado y jobs futuros afectan el viaje. No se ejecutan esos helpers mutantes. |
| Scrap directo de tránsito | Cero calculable: `Travel` no cobra scrap por salto. Excluye reparaciones, mantenimiento y trabajo informativo. |
| Desgaste de sistemas/casco | `Engine._apply_degradation` depende de duración, deterioro base, calidad, radiación y brownout; tránsito normal sin CRUISE usa `TRANSIT_WEAR_MULT_NORMAL`. El casco también depende de exposición/tránsito. Daño y decisiones de reparación futuros no están cuantificados. |
| Scrap de reparación/salvage | Desconocido. `_repair_scrap_cost` tasa un importe/perfil concreto; los fallos pueden consumir/devolver reservas. Salvage depende de disponibilidad real, drones, batería y jobs exitosos; no se gana antes de ejecutarlo. |

`EstimateStatus` separa `calculable`, `conditional` y `unknown`; los desconocidos
son `None`, nunca cero ni penalización inventada. El tiempo nominal supone
velocidad actual, tránsito normal y ausencia de escalas/jobs. La energía CRUISE
supone sistemas constantes con los objetivos normales de apagado automático;
no es descarga de batería ni promesa de suministro sostenido. El tiempo local
puede favorecer un camino geométricamente más largo. La acción Travel real del
Engine comprueba las estimaciones en la regresión 17.

`economic_feasibility` permanece `unknown`, incluso con `verified_mechanics`.
Este estado verifica la valoración actual de mecánicas/fuentes, no una expedición
asequible ni supervivencia. Se revalidarán gates normales de nave/operador y todas
las condiciones. El posible módulo futuro de canibalización de drones podría
cambiar oportunidades de recursos al regresar, pero no está implementado,
no aporta scrap aquí ni es requisito de planificación.

### Evidencia territorial y aparición tardía

La evidencia persistida es distinta: generación física (`generated_sectors` y
`sector_states`), intel sectorial explícita del jugador (`known_intel`/`IntelItem`
de sector), nodos conocidos, contactos detectados, `visited_nodes` y
`node_cleaned` del pool. `TerritoryEvidence` también indica si un sector tiene
nodos detectados/visitados o si una región galáctica física tiene algún visitado.
Nada significa cobertura exhaustiva. Sin pool, completitud desconocida, sin
suponer que el lugar esté completado o disponible.

El modelo no persiste un registro durable de cobertura volumétrica de sensores.
Eventos recientes de scan, contactos, datos de jobs y rangos finos no prueban que
se haya examinado todo el espacio ni que un sector sin nodos visitados nunca se
haya escaneado. Cada evidencia declara `sensor_coverage=not_recorded`; no se
inventa mapa de escaneo.

Las señales de frontera son sólo evidencia: etapa no visitada, etapa sin
identificar y ausencia de intel sectorial explícita (expresamente no ausencia de
escaneo previo). No se infiere territorio virgen de generación interna ni falta
de visitas. Las zonas conocidas siguen elegibles y no se reabren fuentes
completadas. Las escalas nuevas en sectores generados/explorados conservan todas
las dependencias 4D-3c de inserción, aparición, topología y pools. El evaluador
recomprueba identidad/posición física, reservas canónicas actuales y estado de
fuentes; los cambios requieren replanificar. No se introduce explicación de
invisibilidad, permiso de aparición retroactiva ni mecánica de cobertura nueva.

### Comparación parcial, presupuesto y límite de integración

1. Priorizar legitimidad mecánica: `verified_mechanics`, después `conditional`;
   conservar `unusable` como diagnóstico y excluirlo de ids preferidos.
2. Dentro de un estado comparable, comparar Pareto de distancia/saltos de acceso,
   distancia/saltos totales y segundos nominales. Los conjuntos de dependencias
   pendientes/no disponibles no deben aumentar para dominar otra propuesta.
   Requisitos distintos o conflictos menor distancia/más saltos conservan alternativas.
3. Sólo con métricas prácticas y dependencias equivalentes usar un superconjunto
   estricto de evidencia de frontera. Evidencia igual/incomparable conserva empates.

No hay puntuación económica ponderada, porcentaje inventado, penalización por
coste desconocido, prohibición fija de retroceso ni ganador por id arbitrario.
Los ids sólo ordenan la salida. Las razones por pares explican dominancia o
conflicto; todas las evaluaciones se pueden inspeccionar. `preferred_ids` es el
conjunto no dominado muestreado, no una orden de activación ni prueba de mejor
viaje económico.

`OpportunityBudget` predeterminado: 8 objetivos, 16384 expansiones de acceso,
65536 aristas de acceso entre las tres pasadas y 4096 comparaciones. Cada testigo
de cadena conserva su `SearchBudget`. Con hasta tres testigos de cadena y tres
de acceso por objetivo, la familia predeterminada tiene hasta 72 evaluaciones.
Ordenar ids reproduce el muestreo técnico, sin establecer prioridad de producto.
Los objetivos sobrantes quedan sin valorar y se registran en `omitted_targets`; agotar presupuesto
hace falso `complete_within_sampled_family`. Ese campo nunca afirma búsqueda
espacial completa. Indexar mundo/conocimiento escala con la entrada; las copias
de caminos en componentes conocidas largas añaden trabajo/memoria polinómicos.
No hay caché global ni enumeración combinatoria de todos los caminos.

La integración Textual futura capturará instantánea coherente inmutable,
calculará fuera del hilo UI, comprobará vigencia y revalidará antes de confirmar.
Los resultados obsoletos se descartarán sin tocar la partida. Un worker nunca
mutará estado vivo. No se implementan worker, entrega, persistencia de planes ni
materialización. **F-DEAD-01 continúa abierto.**

### Ejemplos reproducibles, rendimiento y pruebas

Seed `271828`, todo aislado:

- Veinte saltos conocidos de acceso de 30 ly más cadena de 30 ly son 630 ly y
  21 saltos, no 30 ly. Una oportunidad de 40 ly desde el nodo actual domina ese
  retroceso.
- Una oportunidad cercana en zona visitada puede ganar a otra desconocida lejana.
  Con viajes iguales de 40 ly y dependencias iguales, una alternativa sin
  identificar/no visitada gana por frontera; dos conocidas equivalentes empatan.
- Tiempo local real: acceso de 0,009 ly tarda nominalmente 2479,871 s y la
  alternativa de 0,0117062814 ly tarda 847,178 s. Se conserva el conflicto distancia/tiempo.

Ejecutar `tests/deadnode_opportunity_selection_smoke.py --benchmark` con Python
canónico. Tres llamadas por celda excluyen construir fixtures. La primera matriz
usa 0/1000/3000 nodos físicos de fondo lejanos y 1/4/8 objetivos cercanos; los casos
adicionales tienen 1000/3000 aristas reales de red dirigida conocida y cuatro
objetivos. Son mediciones sintéticas, no frecuencias jugables ni garantías de
latencia. El acceso compartido se calcula una vez por llamada, independientemente
de cuántos objetivos haya. Una futura invocación UI seguirá necesitando worker.

Mediana / máximo, ms; nodos físicos de fondo:

| Fondo | 1 objetivo | 4 objetivos | 8 objetivos |
| --- | --- | --- | --- |
| 0 | 3.79 / 4.22 | 7.82 / 7.98 | 14.72 / 15.55 |
| 1000 | 17.75 / 19.34 | 27.32 / 28.93 | 33.42 / 34.14 |
| 3000 | 52.47 / 56.06 | 79.30 / 83.73 | 67.36 / 74.96 |

| Aristas dirigidas conocidas | Objetivos | Mediana / máximo, ms | Aristas de acceso evaluadas |
| --- | --- | --- | --- |
| 1000 | 4 | 190.54 / 198.84 | 3000 |
| 3000 | 4 | 674.55 / 760.22 | 9000 |

[`deadnode_opportunity_selection_smoke.py`](../../tests/deadnode_opportunity_selection_smoke.py)
contiene 40 grupos numerados según la solicitud 4D-3d:

| Grupos | Cobertura |
| --- | --- |
| 01–08 | Orígenes actual/multihop/dirigidos, alternativas mínimas de acceso, retroceso y coste completo sin movimiento gratis. |
| 09–16 | Territorio desconocido/visitado/antiguo/generado, nodos incompletos/completados, cobertura desconocida e inserción condicionada con rechazo de capacidad obsoleta. |
| 17–22 | Tiempo largo/local y energía CRUISE del Engine real, acceso local más largo y rápido, scrap directo cero distinto de reparación/salvage desconocidos, sin canibalización ni recursos concedidos. |
| 23–32 | Cercanía frente a retroceso, conocido frente a desconocido lejano, frontera secundaria, fuentes imposibles frente a rodeos utilizables, primaries, recepción futura, ejemplo verificado de mecánicas, empates/conflictos y orden estable. |
| 33–40 | Pureza de estado/RNG/contadores/conocimiento, escritores/acciones vivos prohibidos, seeds hash, tres ciclos temporales save/load, miles de nodos, comparación compartida acotada y waypoint detenido real. |

Siguen aplicándose los 49 grupos 4D-3c y controles generales anteriores.
Manuales/help no requieren actualización: son APIs puras internas, sin cambios
de comandos ni UI localizada. Aún deben decidirse política de retroceso aceptable
(si se desea exclusión dura), resolución de conflictos/economía desconocida y
las políticas existentes de inserción/topología/fuentes/recepción. No se aprueba
ni implementa umbral nuevo de distancia, mecánica de cobertura ni rescate garantizado.
