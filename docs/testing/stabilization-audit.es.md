# Auditoría transversal y plan de estabilización

Versión inglesa: [stabilization-audit.md](stabilization-audit.md)

Esta auditoría se realizó sobre el árbol limpio en `320d06c` el 2026-11-02.
Consolida las referencias canónicas sin sustituirlas y no modifica mecánicas,
tests, balance ni contenido.

> **Actualización de Fases 4A/4B:** el desarrollador resolvió posteriormente parte
> de las decisiones que aquí figuran abiertas. El
> [contrato de navegación y recuperación](../design/navigation-recovery-contract.es.md)
> prevalece para validez de rutas, cadenas deadnode, nodos visitados, recepción
> diferida, protección narrativa y política de partidas. Las matrices de esta
> auditoría se conservan como diagnóstico del comportamiento observado.

## 0. Cierre de planificación de Fase 4B

Las decisiones abiertas de esta auditoría se cierran o reasignan así:

- la prealfa no requiere migraciones entre versiones; sí exige integridad y
  save/load de la versión vigente, rechazo explícito de incompatibles y ninguna
  eliminación automática de partidas;
- `comms`/`radiod` serán la dependencia de recepción para señal y broadcast;
  uplink conserva `data_core`/`datad` y salvage no usa radio;
- los failsafes garantizan oportunidades coherentes, no supervivencia, recursos
  gratuitos ni reparación universal;
- las categorías `modules_pool` son filtros para módulos reales; sus metadatos
  deben auditarse antes de implementar;
- singles, pools uplink, `radiation_base`, orden de worldgen y balance general
  siguen en estudios independientes.

La matriz ejecutiva vigente, con criterios completos en el contrato, es:

| ID | Prioridad | Prueba previa | Fase |
| --- | --- | --- | --- |
| F-LORE-01 — `uplink_only` sin efecto | **P0 alta** | malformed, extremo ausente, sobre-cap, válido nuevo/preexistente | **4C-1** |
| F-SENS-01 — factor `UPGRADED` | P1 media | matriz determinista de todos los estados | 4C-2a |
| F-WGEN-02 — `SECTOR` malformado | P1 media | formatos válidos/inválidos sin mutación | 4C-2b |
| F-INTEL-01 — `intel N` antiguo | P2 baja | timestamps controlados y límites 1/2/sin límite | 4C-2c |
| F-DEAD-02 — cooldown en `t=0` | P2 baja | cero, reevaluación inmediata y tras cooldown | 4C-2d |
| F-WGEN-01 — filtros `modules_pool` | P1 media | metadatos + seeds por región | 4C-3 |

El orden anterior sustituye las prioridades históricas de las secciones 4, 7 y
8 cuando entren en conflicto. Las demás matrices siguen describiendo los
defectos observados, no mecánicas corregidas.

## 1. Resumen ejecutivo

La integración usa tres capas legítimamente distintas —universo físico,
conocimiento y rutas publicadas—, pero varios consumidores no aplican el mismo
criterio de validez. Los problemas de mayor prioridad son:

1. `known_links` puede contener destinos inexistentes o saltos sobre el cap.
   Viaje los rechaza, mientras recuperación global y deadnodes los tratan como
   rutas/fronteras válidas. `nav abort` puede producir referencias inexistentes
   de este tipo durante juego normal.
2. Deadnodes coloca el puente cerca del objetivo, no de un origen alcanzable, y
   publica una pista desde el nodo actual sin validar 45 ly. En la sonda, el
   puente quedó a 99,38 ly, sin enlaces físicos ni pool, y la importación rechazó
   la ruta.
3. Una pieza `uplink_only` inválida o sobre el cap se marca `delivered` aunque no
   produzca ruta, evento, archivo ni unlock. No hay arcos activos ahora, pero el
   defecto comprometería primaries al activar contenido que use esa vía.

También están confirmados defectos más acotados: sensores `UPGRADED` usan el
factor de `CRITICAL`, `intel N` muestra los N registros más antiguos, bulge/halo
no recuperan módulos por la interpretación de `modules_pool`, ids de sector
malformados materializan el clúster del origen y el cooldown deadnode puede
saltarse exactamente en `t = 0`.

No se clasifican como bugs dos políticas sin decisión: `route solve` hacia un
nodo físico no descubierto dentro de sensores/cap es deliberado; y los pools de
uplink congelados tienen cobertura y contrato actual, aunque su efecto sobre
oportunidades posteriores debe medirse. Tampoco hay evidencia de partida para
cambiar la probabilidad de singles.

## 2. Matriz de riesgos

Severidad: **alta** puede bloquear progresión o consumir contenido irrepetible;
**media** degrada una mecánica relevante con alternativa parcial; **baja** afecta
presentación o estados límite. “Frecuencia desconocida” significa que no hay
telemetría ni muestra de partidas, no que el caso sea improbable.

### 2.1 Defectos funcionales verificables

| ID | Problema | Subsistemas | Evidencia | Precondiciones | Consecuencia para el jugador | Severidad | Frecuencia | Recuperación actual | Pruebas existentes | Pruebas necesarias | Decisión pendiente | Orden |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-ROUTE-01 | Rutas conocidas inexistentes o sobre-cap cuentan como frontera/ruta para recuperación y deadnodes, pero viaje las rechaza. | Intel, `WorldState`, viaje, recuperación, deadnodes, save | Implementación + sonda en memoria | Importar `LINK` con extremo inexistente, cargar estado obsoleto o conservar arista inválida | Frontera fantasma; no se activa rescate y el destino no entra en deadnodes | Alta | Desconocida; el import dangling está disponible al jugador | No hay comando de limpieza; otras rutas independientes pueden seguir funcionando | `route_hop_cap_smoke` sólo cubre rechazo de viaje | Import dangling/sobre-cap → frontera → deadnodes → viaje, antes/después de sanear | Política de rechazo/migración para saves | 1 |
| F-NAV-01 | `_clear_tmp_node` elimina el waypoint y su entrada, pero deja referencias inversas en los extremos. | Viaje abortado, rutas, recuperación, persistencia | Implementación + sonda | `nav abort` y posterior salida del waypoint | Ruta fantasma producida por juego normal; puede activar F-ROUTE-01 | Alta | Desconocida | Ninguna automática | Sin cobertura específica | Abort → reanudar → llegada → ausencia total del id temporal, también tras save/load | Ninguna para la limpieza; definir migración de estados existentes | 1 |
| F-DEAD-01 | El puente deadnode se crea junto al objetivo y la pista parte del nodo actual sin validar cap; además no tiene enlace físico ni pool. | Deadnodes, intel, navegación, worldgen, pools | Implementación + sonda: 99,38 ly y ruta descartada | Objetivo inaccesible lejano alcanza umbral `dead` | Dos intentos indirectos pueden ser inutilizables; el directo puede seguir sobre-cap | Alta | Desconocida | Repetición cada 5 años y pista directa, sin garantía de utilidad | No hay test dedicado | Origen alcanzable → umbral → puente bajo cap → import → viaje; casos lejano, sector generado/no generado | Contrato del puente: origen, topología, pool y persistencia | 2 |
| F-LORE-01 | `uplink_only` se marca entregado aunque el LINK sea inválido/sobre-cap y no haya efecto. | Scheduler, primaries, intel, persistencia | Implementación + sonda sintética | Pieza asignada a `uplink_only` con línea no parseable o salto inválido | Contenido irrepetible consumido y primary no desbloqueado | Alta | Cero con los datos activos actuales; cierta al darse la precondición | Ninguna: `delivered` impide reintento | Test positivo de unlock con ruta preexistente | Negativos: malformed, nodo ausente, sobre-cap y éxito preexistente/nuevo | Éxito válido y reintento ya aprobados; falta implementación | 3 |
| F-SENS-01 | `UPGRADED` supera el gate pero falta en el mapa de detección y cae a `CRITICAL` (0,35). | Scan, sistemas, balance | Implementación + sonda con fallback aislado | Sensores en estado `UPGRADED` | Una mejora reduce la detección frente a nominal | Media | Desconocida | Repetir scan; entrada de recuperación tiene excepción garantizada | Sin cobertura del factor | Matriz determinista por cada `SystemState` | Elegir factor; normalmente nominal o superior | 1 |
| F-WGEN-01 | Lista `modules_pool: ["tech", "rare"]` se interpreta como ids; no existen esos ids y la selección queda vacía. | Templates, módulos, worldgen, salvage | Datos activos + implementación + sonda | Nodo salvage en bulge; en halo cuando el conteo sorteado es 1 | Pérdida sistemática de módulos configurados, segura en bulge (`min=1`) | Media | En cada perfil bulge aplicable; halo depende del sorteo | No existe recuperación del loot omitido | Worldgen no afirma pools de módulos | Semillas por región: conteos y pertenencia a categorías | Categorías como filtros aprobadas; falta mapear metadatos reales | 4 |
| F-WGEN-02 | `_parse_sector_id` convierte cualquier id malformado a `(0,0,0)`; `SECTOR:` puede materializar el origen y registrar el id inválido. | Intel, worldgen, estado sectorial | Implementación + sonda | Importar `SECTOR: <malformado>` o llamada interna equivalente | Mutación inesperada del origen e intel incoherente | Media | Desconocida | El mundo sigue jugable; no hay limpieza del registro inválido | Sin test negativo | Parser estricto en frontera pública y rechazo sin mutación | Formato aceptado y compatibilidad con saves | 1 |
| F-INTEL-01 | `intel N` ordena ascendente y corta al inicio pese a anunciar “latest”. | CLI/UI, historial intel | Implementación + sonda | Más de N registros | Oculta los registros más recientes solicitados | Baja | Frecuente cuando el historial supera el límite | `intel show` si se conoce el id; export completo | Sin cobertura | Tres timestamps y límites 1/2/sin límite | Elegir orden de presentación estable | 1 |
| F-DEAD-02 | El cooldown sólo se aplica si `last_action_t > 0`; acciones en `t=0` pueden repetirse inmediatamente. | Deadnodes, reloj | Implementación + sonda previa | Umbral alcanzado en `t=0` por fixture/debug/estado migrado | Dos indirectas y una directa sin esperar | Baja | Muy baja/desconocida en juego normal | El estado termina avanzando, pero con spam | Sin test | Caso `t=0` y caso positivo tras 5 años | Representar ausencia con `None` o condición explícita | 4 |

### 2.2 Riesgos potenciales que necesitan reproducirse o medirse

| ID | Problema | Subsistemas | Evidencia | Precondiciones | Consecuencia para el jugador | Severidad | Frecuencia | Recuperación actual | Pruebas existentes | Pruebas necesarias | Decisión pendiente | Orden |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-LORE-01 | Un nodo ad hoc puede recibir una pieza forzada sin breadcrumb en ningún pool conocido. | Scheduler, pools, ad hoc, deadnodes | Flujo confirmado + sonda; bloqueo permanente no demostrado | Todos los pools conocidos están limpios/ausentes | Receptor oculto y pieza asignada sin vía inicial | Alta | Cero con arcos activos actuales; desconocida al activar force | Scan si está cerca; deadnodes tras décadas/uplinks | Fixture histórica falla antes de validar el flujo | Caso con host válido y caso sin host; comprobar descubrimiento/entrega | ¿Debe fallar la asignación, reservar deuda o crear canal alternativo? | 3 |
| R-LORE-02 | Deadnodes o gateway global pueden revelar/reutilizar un receptor procedural protegido. | Lore, locks, failsafes, scan | Implementación; no hay arco activo ni reproducción E2E | Primary/ad hoc oculto coincide con candidato de rescate | Bypass de ritmo narrativo o unlock fuera de secuencia | Alta | Cero hoy; desconocida con arcos | El contenido puede seguir entregándose, pero ya revelado | Ninguna | Arco sintético protegido frente a scan, deadnodes, gateway e intel corrupta | Alcance real del lock; scan deliberado o no | 3 |
| R-OPP-01 | El pool uplink congelado omite nodos materializados o desbloqueados después. | Pools, worldgen lazy, uplink | Implementación + `uplink_once_per_node_smoke` | Inicializar pool antes de expandir universo | Menos rutas/oportunidades que las disponibles posteriormente | Media | Desconocida | Scan, imports, otros hubs y recuperación global | Cubre congelación y consumo, no impacto de progreso | Pool inicial → expansión → uplink → alternativas restantes | Mantener snapshot, refrescar o versionar | 5 |
| R-OPP-02 | Un contacto puede descubrirse y visitarse antes del siguiente ciclo anual; su ventana se cierra sin haber sido candidato. | Scheduler, reloj, pools, navegación | Implementación | Descubrimiento/visita entre ciclos; pieza elegible para ese pool | Pérdida de oportunidad narrativa sin error visible | Media | Desconocida | Otros pools/ciclos para piezas no asignadas | Stress con intervalo 0 no representa balance real | Simulación multi-seed con calendario/visitas controladas | Política de reserva, deuda o cierre | 5 |
| R-OPP-03 | La frecuencia real de los cinco singles activos no está medida. | Balance, scheduler, contenido, estilo de juego | Probabilidad teórica por pieza/ciclo; sin datos de partidas | Elegibilidad, pools abiertos y calendario anual | Contenido excesivamente raro o concentrado; no demostrado | Media | Desconocida | Ciclos futuros mientras existan candidatos | Compatibilidad sólo con probabilidad forzada a 1 | Simulación de cohortes y trazas de partidas antes de tocar balance | Umbral de frecuencia aceptable | 5 |
| R-WGEN-01 | El mismo conjunto de sectores puede producir distinta arista intersectorial según orden de solicitudes. | Worldgen, determinismo, save | Diagnóstico previo con seed 2 | Solicitudes en orden distinto | Reproducibilidad parcial; mapas divergentes | Media | Confirmada para una seed, prevalencia desconocida | Ninguna; el mundo persistido conserva su versión | Determinismo sólo para misma secuencia | Regresión A→B→C frente a C→B→A con contrato explícito | ¿Determinismo incluye independencia de orden? | 5 |
| R-WGEN-02 | Nodos añadidos tras `internal_links_built` no reconstruyen topología; puentes ni siquiera añaden enlace manual. | Worldgen, ad hoc, deadnodes | Implementación; impacto general sin matriz | Inserción tardía en sector generado/vacío | Nodo físico huérfano o metadatos incoherentes | Media | Desconocida | Ad hoc anclado aporta enlace manual; bridge no | Sin cobertura de inserción tardía | Sector vacío/cerrado + cada tipo de inserción | Política de mutación topológica posterior | 2 |
| R-SAVE-01 | Estados de recuperación persisten, pero cambios/eliminación de definiciones de lore pueden dejar asignaciones sin pieza; no hay prueba versionada específica. | Save/load, scheduler, failsafes | Código + sondas temporales; deriva de contenido es hipótesis | Guardar antes/después de rescate o cambiar contenido entre versiones | Duplicados, push pendiente o entrega imposible tras actualización | Media | Desconocida | Compatibilidad parcial por `__setstate__`; no migra ids de contenido | `save_load_smoke` general | Save/load específico global, deadnode, ad hoc y single; fixture de definición ausente | Política de migración/versionado de contenido | 6 |

### 2.3 Decisiones de diseño abiertas

| ID | Problema | Subsistemas | Evidencia | Precondiciones | Consecuencia para el jugador | Severidad | Frecuencia | Recuperación actual | Pruebas existentes | Pruebas necesarias | Decisión pendiente | Orden |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D-NAV-01 | `route solve` permite un nodo físico no descubierto dentro de sensores y cap. | Navegación, descubrimiento | Decisión confirmada por el desarrollador | Conocer/escribir el id exacto | Permite navegación por conocimiento externo | No es defecto | Deliberada | N/A | Cobertura indirecta | Caracterización explícita para no regresarlo | Revisar conveniencia sólo más adelante | Conservar |
| D-OPP-01 | Snapshot y consumo único de pools uplink. | Pools, uplink, worldgen | Contrato implementado y testado | Expansión posterior | Oportunidad limitada por orden temporal | Abierta | Desconocida | Otros canales/failsafes | `uplink_once_per_node_smoke` | Medición R-OPP-01 antes de cambio | Confirmar snapshot estricto o refresco controlado | 5 |
| D-DEAD-01 | Umbrales `stuck` no actúan; sólo `dead`; “uplink útil” es contador condicional. | Deadnodes, lore, debug | Implementación | Contacto candidato persistente | Diagnóstico y expectativa temporal ambiguos | Abierta | Cada deadnode | Acción al umbral `dead` | Sólo sonda temporal | Caracterización de ambas escalas y contadores | Implementar fase stuck, renombrar o retirar | 2 |
| D-LORE-01 | El lock de primary no es barrera global. | Lore, scan, failsafes, intel | Implementación; sin contenido activo | Activar arcos con target protegido | Ritmo narrativo variable por canal | Abierta | Cero hoy | Unlock posterior aún posible | Ninguna E2E | Matriz de canales de revelación | Qué bypasses son deliberados | 3 |
| D-REC-01 | El llamado `dock_hint` se entrega en llegada, sin dock. | Recuperación, motor, nomenclatura | Implementación + test que no distingue llegada/dock | Llegar a entrada global | Acceso al gateway antes de dock | Abierta | Cada cadena global usada | Pista salvage alternativa | Recovery smoke sólo observa después | Aserción justo tras llegada y después de dock | Confirmar llegada o exigir dock; alinear nombre/test | 2 |
| D-WGEN-01 | `radiation_base` regional de JSON está inactivo; manda `Balance`. | Worldgen, balance, datos | Implementación y datos | Generación procedural | Configuración aparente sin efecto | Abierta | Todo worldgen | Radiación efectiva sí existe por Balance | `procedural_radiation_smoke` cubre modelo efectivo | Contrato de precedencia y validación de campo muerto | Eliminar campo o integrarlo | 4 |
| D-WGEN-02 | El alcance de determinismo frente al orden no está definido. | Worldgen, QA, saves | R-WGEN-01 | Orden distinto | Dificulta reproducir/reportar mundos | Abierta | Desconocida | Seed + secuencia exacta reproducen | Parcial | Prueba dual condicionada al contrato | Aceptar dependencia o estabilizar pares | 5 |
| D-LORE-02 | No hay objetivo de frecuencia para singles; 0,05 × peso por ciclo es sólo tasa teórica condicionada. | Balance, narrativa, scheduler | Configuración; sin telemetría | Juego normal con elegibilidad variable | No se puede juzgar si el contenido es demasiado raro | Abierta | Desconocida | Ciclos posteriores | Stress no representativo | Cohortes multi-seed y trazas reales anonimizadas | Definir métrica antes de rebalancear | 5 |

## 3. Dependencias entre problemas

```mermaid
flowchart LR
    A[F-ROUTE-01<br/>contrato de ruta válida] --> B[F-NAV-01<br/>limpieza waypoint]
    A --> C[F-DEAD-01<br/>puente utilizable]
    A --> D[recuperación global<br/>frontera real]
    E[R-WGEN-02<br/>inserción tardía] --> C
    F[F-LORE-01<br/>resultado de entrega] --> G[unlock primary coherente]
    H[R-LORE-01<br/>breadcrumb] --> G
    I[D-LORE-01<br/>protección] --> H
    J[D-OPP-01<br/>pools congelados] --> K[R-OPP-02/03<br/>frecuencia medida]
    L[tests de persistencia] --> M[migraciones de rutas y contenido]
```

- La validez canónica de rutas debe resolverse antes de ajustar deadnodes o
  recuperación: de otro modo cada subsistema volvería a definir “utilizable”.
  Debe reutilizar `distance_between_nodes_ly`, `is_hop_within_cap` y
  `add_known_link`, añadiendo una única validación/normalización compartida si
  hace falta, no parsers paralelos.
- La limpieza de waypoint es una fuente concreta de rutas fantasma y debe entrar
  en el mismo lote y migración.
- El puente deadnode depende además de una política para inserciones topológicas
  tardías; corregir sólo el texto de la pista no decide pool/enlace físico.
- La semántica de “entregado con efecto” debe fijarse antes de unificar unlocks
  o activar arcos.
- Breadcrumb y protección de primaries requieren una decisión común sobre qué
  mecanismos pueden revelar objetivos ocultos.
- No debe cambiarse snapshot, ventanas o probabilidades hasta medir juntos
  elegibilidad, ritmo de visitas y persistencia.

## 4. Propuesta de prioridades

| Prioridad | Resultado | Alcance recomendado | Criterio de salida |
| --- | --- | --- | --- |
| P0 — Caracterización | Convertir sondas críticas en regresiones aisladas | Rutas inválidas, waypoint, `UPGRADED`, intel, módulos, sector inválido, entrega sin efecto, persistencia | Tests rojos sólo donde se va a corregir; decisiones deliberadas fijadas en verde |
| P1 — Integridad de rutas | Una ruta publicada es viajable o está explícitamente marcada/no publicada | Validador compartido, importadores, limpieza waypoint, normalización de saves | Ninguna arista dangling/sobre-cap cuenta como frontera o resolución deadnode |
| P2 — Recuperación | Deadnodes y recuperación sólo ofrecen oportunidades consumibles | Origen de puente alcanzable, cap, topología/pool, cooldown y semántica `stuck`; confirmar llegada/dock | Cadena deadnode E2E y save/load verde |
| P3 — Integridad narrativa | No consumir piezas sin efecto ni asignarlas sin política de acceso | Resultado de entrega, retry, breadcrumb, unlock y protección | Primaries sintéticos cubren éxito, fallo y ruta preexistente |
| P4 — Defectos acotados de datos/UI | Reparaciones independientes y de bajo riesgo | `UPGRADED`, orden intel, ids sector, `modules_pool`, campo de radiación según decisión | Matrices por estado/región y errores públicos claros |
| P5 — Política de oportunidades | Decidir con evidencia, no intuición | Pools congelados, ventanas, ciclo anual, singles, determinismo de orden | Simulación reproducible y umbral de producto aprobado |
| P6 — Persistencia/migración | Mantener invariantes al cargar estados antiguos | Saneado de rutas, ids temporales, recovery/lore versionado | Tests temporales antes/después y estrategia de compatibilidad documentada |

P0 no implica incorporar todos los arneses como utilidades compartidas. Los
smokes actuales usan builders locales; conviene mantener fixtures pequeñas en
cada test hasta que tres o más pruebas demuestren una abstracción común real.

## 5. Plan mínimo de pruebas de integración

Todas deben usar `/home/jon/prog/retorno_case/retorno_venv/bin/python`, seeds
literales, `create_initial_state_sandbox/prologue`, `Engine` y
`TemporaryDirectory`. Ninguna debe resolver rutas de saves reales.

| ID | Flujo y montaje controlado | Aserciones mínimas | Infraestructura / fixture |
| --- | --- | --- | --- |
| IT-01 | Seed fija: generar sector, scan, descubrir objetivo físico cercano, `route solve`, completar job, viajar y completar llegada | Generar no revela; scan sí; solve publica bajo cap; viaje exige ruta; llegada actualiza visita/pool | Reusar Engine, worldgen y helpers de ETA de smokes; fixture local de dos nodos |
| IT-02 | Inicializar pool uplink, materializar hub posterior, ejecutar uplink y después otro canal de descubrimiento | Snapshot no cambia hoy; consumo es único; el hub tardío conserva una vía alternativa o el test documenta la pérdida | Extender `uplink_once_per_node_smoke`; sin helper nuevo |
| IT-03 | Estado sin frontera → recuperación global → importar entrada → solve/viaje → llegada → importar gateway → viaje | Una sola generación, distancias bajo cap, broadcast en el evento acordado, rutas viajables | Extender `exploration_recovery_smoke`; seed fija |
| IT-04 | Contacto lejano sin ruta → avanzar contador/tiempo → deadnode → importar pista → viajar al puente → resolver objetivo | Cada pista publicada pasa validador; puente tiene integración decidida; cooldown y attempts persisten | Nueva fixture deadnode sintética; no existe equivalente |
| IT-05 | Arco sintético hard sin candidato → ad hoc → breadcrumb en host conocido → importar la ruta → viaje → trigger → entrega/unlock | Nodo oculto, breadcrumb recuperable, ruta bajo cap, pieza no `delivered` antes de efecto | Reparar fixture forced-hidden y añadir test E2E separado |
| IT-06 | Importar LINK inexistente y sobre-cap; cargar arista obsoleta; ejecutar frontera, deadnodes y viaje | Rechazo/no publicación; ningún falso frontier; contacto conserva semántica decidida; migración idempotente | Nueva fixture de rutas inválidas; reutilizar parser y Engine |
| IT-07 | Guardar antes y después de activar recuperación global/deadnode; cargar dos veces | IDs, paths, pools, thresholds, attempts y bridge persisten; no se duplica generación/pista | Extender `save_load_smoke` o test específico con `TemporaryDirectory` |
| IT-08 | Filtrar un single real activo, probabilidad/intervalo controlados, receptor conocido abierto, trigger, lectura/import, save/load | Binding correcto, un solo delivery, contenido real legible, efecto intel esperado (ninguno si el archivo no contiene intel), persistencia | Loader real + filtro local; no copiar el contenido al test |
| IT-09 | Viaje → abort → save/load opcional → reanudar a cada extremo | Waypoint desaparece de nodos, rutas, conocidos, intel/fine ranges aplicables y componentes | Nueva prueba local sobre `TravelAbort`/`_clear_tmp_node` |
| IT-10 | Generar bulge/halo/disk con seeds conocidas y nodo salvage aplicable | Conteo respeta min/max y cada módulo pertenece a la semántica aprobada; determinismo | Reusar loader y descriptor de worldgen; tabla de seeds explícita |

La sonda de auditoría en memoria confirmó F-ROUTE-01, F-NAV-01, F-DEAD-01,
F-LORE-01, F-SENS-01, F-WGEN-01, F-WGEN-02 y F-INTEL-01, además del escenario
R-LORE-01. Una sonda temporal adicional colocó el single real
`sig_echo_fragment_01`, lo entregó por `captured_signal`, leyó/importó su texto
sin producir intel —resultado correcto para ese asset— y confirmó persistencia.
Otra sonda con slots temporales confirmó que recuperación global y deadnodes
persisten sin duplicar la generación global tras la primera carga. Estas sondas
no sustituyen regresiones versionadas.

Las pruebas existentes ejecutadas en esta auditoría dieron PASS para scan, cap
de salto, sugerencias de origen, pool uplink único, recuperación global, failsafe
de uplink, save/load, worldgen sparse y preferencia/unlock de canales. Las tres
fixtures históricas fallaron en las expectativas inventariadas en la sección 6.

## 6. Tratamiento de fixtures obsoletas

### `forced_hidden_ad_hoc_smoke.py`

- Debe seguir siendo **sintética**: prueba infraestructura, no contenido activo.
- Crear explícitamente un `BREADCRUMB_HOST` físico, conocido, no visitado y con
  pool abierto; no usar `HARBOR_12` ni hacer conocidos todos los authored.
- Marcar los demás pools como no elegibles y afirmar que el breadcrumb aparece
  sólo en el host.
- Separar un segundo caso “sin host elegible” que documente el comportamiento
  decidido: no asignar, deuda pendiente o fallback. No convertir el silencio
  actual en garantía por accidente.

### `lore_secondary_count_weights_hard_smoke.py`

- Mantener contenido sintético y casos separados por función.
- Para `count=1`, crear un receptor físico conocido, no visitado, con pool
  abierto antes del tick; fijar probabilidad a 1 e intervalo a 0 dentro de
  `try/finally`.
- Ejecutar cada caso de forma independiente para que un fallo de `count` no
  oculte weights y hard-force. El runner puede agregar resultados sólo después.
- Conservar `weight=0/1`, constraints hard y no-relax; no activar templates.

### `debug_lore_arcs_smoke.py`

- Dividir contrato real y formato sintético.
- Con datos activos reales, afirmar `load_arcs() == []`, salida `(none)` y línea
  de estado del scheduler; no exigir `primary:`.
- Con un loader monkeypatched a un arco mínimo sintético, afirmar `primary:`,
  estado assigned/unplaced/delivered y claves canónicas.
- Restaurar loaders en `finally`; no mover JSON fuera de `templates/`.

Como cobertura activa independiente, IT-08 debe usar un single real del índice.
Las fixtures de algoritmos no deben depender de nombres narrativos authored.

## 7. Decisiones que requieren intervención del desarrollador

1. Definir si una ruta inválida se rechaza, se conserva sólo como contacto/intel
   o se marca explícitamente como no navegable; y cómo sanear saves existentes.
2. Elegir el contrato físico del puente deadnode: origen alcanzable, enlace,
   pool, sector y estrategia cuando el objetivo está a más de un salto.
3. Definir éxito/reintento para `uplink_only` y para una pieza forzada sin
   breadcrumb.
4. Determinar qué mecanismos pueden revelar un primary protegido. La decisión
   deliberada sobre `route solve` no responde por scan, deadnodes o gateways.
5. Confirmar llegada frente a dock para la pista del gateway.
6. Confirmar snapshot estricto de uplink y política de ventanas sólo después de
   medir R-OPP-01/02.
7. Definir semántica de listas `modules_pool` y destino de `radiation_base`.
8. Definir si el determinismo debe ser independiente del orden de generación.
9. Establecer una métrica de frecuencia de singles antes de cambiar balance.
10. Decidir si `stuck` es una fase real y qué cuenta como uplink deadnode.

## 8. Secuencia de trabajo recomendada

1. Reparar las tres fixtures sin cambios productivos y añadir caracterizaciones
   para decisiones deliberadas.
2. Añadir IT-06 e IT-09, acordar el contrato de ruta y centralizar validación.
3. Corregir/sanear rutas fantasma y waypoint; después revalidar recuperación y
   componentes conocidos.
4. Acordar el puente y completar IT-04 + IT-07 antes de tocar deadnodes.
5. Acordar resultado de entrega, breadcrumb y protección; implementar IT-05 y
   negativos de `uplink_only`.
6. Corregir `UPGRADED`, listado intel e id sectorial como cambios acotados.
7. Resolver `modules_pool`/`radiation_base` con IT-10 y revisar datos existentes.
8. Ejecutar simulación multi-seed de oportunidades y decidir pools, ventanas,
   singles y determinismo sin rebalancear antes.
9. Cerrar con suite completa, save/load/migraciones, paridad documental y una
   matriz de regresión actualizada.

Cada paso que cambie comportamiento deberá actualizar la referencia canónica
propietaria, ayuda/manuales si son observables y la matriz de tests. Esta fase no
autoriza ninguno de esos cambios.

## 9. Referencias

Documentación canónica:

- [Contrato de carga](../content-loading.es.md)
- [Universo físico y worldgen](../systems/world-generation.es.md)
- [Descubrimiento, navegación e intel](../systems/discovery-navigation-intel.es.md)
- [Scheduler de lore](../systems/lore-scheduler.es.md)
- [Failsafes y recuperación](../systems/exploration-failsafes.es.md)

Implementación propietaria:

- [`model/world.py`](../../src/retorno/model/world.py): conocimiento, rutas y
  estado persistente.
- [`core/engine.py`](../../src/retorno/core/engine.py): scan, route solve, viaje,
  waypoint y orden de jobs/failsafes.
- [`cli/repl.py`](../../src/retorno/cli/repl.py): importadores, uplink, intel y
  comandos públicos.
- [`core/lore.py`](../../src/retorno/core/lore.py): pools, scheduler, entrega,
  locks y nodos ad hoc.
- [`core/exploration_recovery.py`](../../src/retorno/core/exploration_recovery.py)
  y [`core/deadnodes.py`](../../src/retorno/core/deadnodes.py): recuperación.
- [`worldgen/generator.py`](../../src/retorno/worldgen/generator.py),
  [`data/worldgen/templates`](../../data/worldgen/templates) y
  [`config/balance.py`](../../src/retorno/config/balance.py): generación y
  configuración efectiva.
- [`io/save_load.py`](../../src/retorno/io/save_load.py): persistencia V2,
  checksum y fallback a backup.
