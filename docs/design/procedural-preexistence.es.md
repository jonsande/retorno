# Preexistencia procedural — Fase 4D-3e1

**Actualización 4D-3e2:** este documento conserva la evidencia histórica de su fase.
El contrato productivo vigente está en [Integración del worldgen histórico](historical-worldgen-integration.es.md).
El prototipo usa ahora el núcleo compartido y distingue su certificación por ámbito/razones;
el catálogo condicional legacy queda en fixtures de pruebas. Las limitaciones productivas
descritas aquí se leen como estado anterior, no como descripción del runtime actual.

Versión inglesa: [procedural-preexistence.md](procedural-preexistence.md).

Estado: **implementación parcial segura y auditoría reproducible**, sobre `main`
en `dd5b471`, 2026-11-05. El checkout estaba limpio al comenzar. El README raíz
es `readme.md`; no existe el `STEPS.md` solicitado. Se revisó el canon en
`docs/canon/universo.md` y `guia_coherencia.md`, especialmente `C-WORLD-001`,
`C-INF-004` y `C-DATA-002`. No cambian canon, comandos, UI, audio, balance,
esquema de guardado ni recuperación productiva. F-DEAD-01 sigue abierto.

## Decisiones aprobadas

Son hechos distintos: emplazamiento determinado por el universo, nodo físico
materializado, localización conocida por el jugador y ruta operativa publicada.
El cálculo lazy es válido sólo si las necesidades posteriores de recuperación no
determinan la existencia histórica. Una previsión provisional reproducible no basta.

Un scan negativo no demuestra ausencia. La futura fiabilidad de observaciones
debe contemplar repeticiones y estado de sensores sin exigir reintentos
sistemáticos de una lotería invisible. F-DEAD-01 resuelve continuidad estructural
de la exploración, nunca scrap, energía, reparaciones, combustible disponible ni
supervivencia. La elegibilidad espacial/topológica/procedural/informativa es
distinta de la capacidad actual de la nave. Priorizar oportunidades próximas por
acceso dirigido completo desde la nave; ampliar progresivamente sin un corte
permanente de distancia. Agotar presupuesto significa búsqueda incompleta, no
prueba de ausencia. No se garantizan rescate ni conectividad universal. Siguen
siendo vinculantes el cap de 45 ly, arquetipos/densidades canónicos, protección
de primaries y conservación del contenido consumido/visitado.

## API implementada y garantías reales

[`worldgen/catalog.py`](../../src/retorno/worldgen/catalog.py) ofrece:

```python
catalog_sector(state, "S+020_+020_+000")  # SectorCatalog
catalog_sectors(state, ("S+020_+020_+000", "S+021_+020_+000"), max_sectors=64)
# CatalogResult(configuration_key, sectors, physical_nodes_examined)
```

`CatalogResult`, `SectorCatalog` y `SiteRecord` son dataclasses congeladas con
tuplas/valores independientes. Las solicitudes son secuencias finitas explícitas,
validadas antes de inspeccionar; se eliminan duplicados y se ordenan sectores
canónicamente. La longitud bruta debe caber en la cota técnica positiva
`max_sectors`. Superarla lanza `ValueError`; nunca demuestra ausencia ni fija
un radio jugable. Una consulta sectorial no amplía al vecindario XY 3×3 del generador.

| `SiteStatus` | Significado |
| --- | --- |
| `physical` | Observado en `space.nodes` por pertenencia espacial real. Incluye nodos authored y técnicos; no declara elegibilidad para recuperación. |
| `verified_procedural` | Categoría contractual para un emplazamiento no materializado certificado. **Esta versión nunca la emite.** El generador vigente no puede garantizarla. |
| `conditional` | Previsión actual de slot/tipo base con muestra canónica y condiciones de existencia pendientes. Nunca reserva ni permiso de inserción. |
| `inadmissible` | Una posición nueva muestreada ya está ocupada físicamente en esta instantánea; no sirve como emplazamiento nuevo distinto. No demuestra inexistencia permanente. |

El muestreador se comparte con `generator.py`: semilla, sector, arquetipo, índice
y tipo alimentan la semilla BLAKE2b existente; dos extracciones uniformes y una
gaussiana Z conservan exactamente el orden RNG anterior, incluida su continuación
para asignar id. El catálogo nunca llama al asignador, a generación de
salvage/módulos ni a escritores. Reutiliza `_select_archetype`,
`_plan_sector_kinds`, loaders canónicos, parser sectorial y regiones físicas.
Una vista de lectura separada e indexada, como la del planificador de cadenas,
evita recorrer todos los nodos por cada sector.

La `key` procedural identifica una **dirección de muestra condicional**, derivada
de semilla, configuración, sector generador, arquetipo base, índice y tipo. No
depende de intentos, recursos/capacidad, tiempo, contadores RNG mutables,
distancia de la nave, orden de consultas, conjuntos ni iteración de diccionarios
del estado. La huella de configuración incluye plantillas, arquetipos, tamaño
sectorial, transformación de regiones y entradas de selección ponderada con
orden explícito. Ese orden de pesos ya forma parte de la semántica de
configuración vigente; cambiarlo cambia la configuración, no sólo el orden de
almacenamiento del estado. Las claves se acotan a este algoritmo/configuración,
sin promesa entre futuras revisiones del generador.

La misma dirección siempre produce la misma muestra dentro de ese alcance,
pero ocupación o guardrails pueden cambiar qué direcciones aparecen en una
previsión. `node_id` es `None` para todas las muestras; no se promete un id
dependiente de colisiones. Los registros físicos usan otra clave semilla/id y
nunca afirman reconstruir el slot de origen. Cambiar la semilla de una partida
no permite recuperar su historial de generación original.

En nodos físicos, `generation_sector_id=None`: los metadatos vigentes registran
pertenencia espacial, no procedencia de creación fiable. En muestras se explicitan
el sector generador y el físico real, incluidos outliers Z. La `region` sectorial
determina la plantilla generadora; la del registro depende de sus coordenadas
reales. Una frontera esférica puede cruzar un sector sin desbordamiento Z. No se
sustituye ningún tipo para facilitar recuperación. Los sectores generados sólo
devuelven registros físicos; estimar cupos restantes no autoriza inserciones
después de cerrar su pasada de generación.

**El catálogo es evidencia interna del mundo, no un selector de recuperación ni
una API de intel del jugador.** No evalúa primaries protegidos, acceso por rutas,
pools ni fuentes informativas. Cada sector declara esas limitaciones. Un objetivo
físico protegido puede figurar en el inventario interno; la consulta nunca lo
revela al jugador. Un consumidor futuro deberá aplicar protección narrativa,
validación de fuentes y rutas dirigidas antes de usar un registro. `physical`
no concede esa aprobación. Una previsión ausente/vacía no declara vacío espacial;
se informa de configuración faltante y se rechazan coordenadas físicas no finitas
en lugar de ocultar silenciosamente un estado inválido.

Ninguna consulta cambia nodos, flags de generación, metadatos, topología, pools,
salvage, filesystem, intel/conocimiento, historial, contadores, recuperación, RNG
global ni tiempo. Todas las RNG son locales; no se añade caché global ni catálogo
persistido. El llamador debe aportar una instantánea coherente de
estado/configuración; no se admite mutación concurrente. Save/load conserva el
estado consultado mediante el esquema existente.

## Auditoría de la generación actual: nueve hallazgos

1. **Arquetipo:** `_select_archetype` es determinista por semilla/sector/región
   central/configuración sin overrides. La primera solicitud que contiene el
   origen puede sobrescribirlo; el catálogo etiqueta la base, sin inventar un
   override final.
2. **Cupos/tipos:** todos los residentes físicos, incluidos authored, técnicos y
   outliers ya materializados, consumen total objetivo y caps por tipo. Un hub
   jugable existente suprime la tirada de otro. No existen slots adicionales.
3. **Ids:** bases de 24 bits con prefijo de tipo colisionan contra todo el registro
   físico; se resuelve con sufijos griegos y luego otra base. Radiación, salvage
   y nombres dependen del id asignado y no quedan certificados por la clave muestral.
4. **Guardrail inicial:** se consume una vez según el cluster de la primera
   solicitud. Los sectores ya generados ignoran overrides posteriores. Puede
   cambiar arquetipos/hub forzado de vecinos pendientes, no sólo topología.
5. **Coordenadas:** X/Y quedan dentro de la celda generadora; la Z gaussiana no
   está acotada. Un outlier se inserta globalmente, puede faltar en metadatos
   refrescados del sector de origen y consumir cupo de otro sector posterior.
6. **Enlaces internos:** se construyen una vez por sector tras crear nodos del
   cluster. Importan residentes actuales y selección lexicográfica del hub
   jugable/topológico; inserciones posteriores no reconstruyen el grafo cerrado.
7. **Enlaces intersectoriales:** se procesan pares vecinos de igual Z con
   presupuestos compartidos, registrados antes de saber si funcionan y sin
   reintento. Las mismas posiciones pueden acabar con distintos enlaces al
   cambiar el orden de materialización.
8. **Inspección y materialización posterior:** las muestras coinciden cuando el
   contexto relevante de ocupación/guardrail/configuración permanece igual. Se
   demuestra en un sector disk remoto, no se garantiza tras generación intermedia
   arbitraria.
9. **Hechos estables:** pueden inspeccionarse direcciones/coordenadas muestrales
   condicionadas y el registro físico actual. Existencia no materializada,
   familia final de tipos/slots, ids finales, recursos, hubs, topología y
   descubrimiento no están todos determinados con independencia del orden. Bajo
   el contrato vigente demostrado no hay emplazamientos latentes verificados reservables.

Regresiones concretas en
[`worldgen_preexistence_characterization_smoke.py`](../../tests/worldgen_preexistence_characterization_smoke.py):

| Semilla y solicitudes | Evidencia |
| --- | --- |
| `2`: `(20,20,0)`, `(22,20,0)`, `(20,22,0)` frente al inverso | Mismos nodos y pares evaluados; difieren cuatro entradas dirigidas (dos enlaces no dirigidos). |
| `29`: `(1,0,0)`, `(-1,0,0)` frente al inverso | Misma unión generada; `S+000_+001_+000` es `empty` frente a `relay_corridor`, con ids distintos. |
| `271828`: `(15126,0,0)`, `(15126,0,1)` frente al inverso | `WRECK_E39D3C` muestrea Z=`10.057691279289713` desde celda Z 0 hacia 1. El destino tiene uno frente a dos nodos; los metadatos de origen omiten el outlier. |
| `271828`: inspeccionar `S+020_+020_+000` y materializar | Estación en `(205.04909961494286,207.116870031816,4.97869392003561)` y derelict coinciden con la previsión sin cambiar contexto. Añadir un hub authored modifica la familia restante de tipos/slots. |
| Mismo slot con colisiones sintéticas de ids en otra zona | Coordenadas iguales; se asigna base, `_ALFA` u otra base. Cambia la radiación específica del nodo. |

## Límite respecto a scan y al planificador contextual

No cambia scan productivo. El alcance base sigue en 2,5 ly y se conservan las
probabilidades vigentes. Una observación persistente futura necesita posición
3D, radio efectivo, estado operativo de sensores, momento, contactos detectados
y contexto del modelo de detección para interpretar un resultado negativo.
La cobertura geométrica histórica por sí sola no da certeza de ausencia. El
catálogo no infiere que un sector no visitado/generado nunca fuese escaneado.

`deadnode_opportunities.py` permanece igual. Su `evaluate` reúne dependencias
de hardware/operador de las fuentes de la cadena, añade condiciones de energía
crítica y desatraque, y rebaja `verified_mechanics` a `conditional` por
dependencias pendientes/no disponibles. `compare_opportunities` prioriza ese
estado y después compara distancias/saltos/tiempo nominal y conjuntos de
dependencias. Estas condiciones prácticas de capacidad pueden afectar la
preferencia. Esa política **no es la elegibilidad estructural recién aprobada**:
daños y recursos de supervivencia no deben rechazar una oportunidad estructural.
Las estimaciones energéticas no rechazan actualmente por batería disponible;
scrap de viaje es cero de cargo directo, mientras reparación/salvage futuros y
viabilidad económica siguen desconocidos. Pueden conservarse como herramientas
informativas independientes sin gobernar aceptación de F-DEAD-01. Los centros
sectoriales del planificador anterior son sondas geométricas, no localizaciones
del catálogo. Aquí no se cambia ranking ni integración.

## Siguientes subfases y decisiones pendientes

| Fase | Trabajo propuesto y dependencia |
| --- | --- |
| **4D-3e2** | Persistir observaciones de scan y especificar fiabilidad/evidencia negativa, save/load y presentación EN/ES. No implica cambiar densidad ni probabilidades de detección. |
| **4D-3e3** | Integrar evidencia del catálogo con búsqueda de oportunidades, ampliar progresivamente familias acotadas, usar acceso dirigido completo y separar elegibilidad estructural de supervivencia/estimaciones operativas. Requiere resolver las invariantes latentes antes de usar una muestra condicional como infraestructura preexistente. |
| **4D-3e4** | Preparación separada, reservas estables, materialización atómica/idempotente, topología cerrada y presupuestos de pares, persistencia, protección de ventanas de fuentes y conocimiento. Revalidar propuestas obsoletas; preparación fallida no consume intento ni revela. |

La auditoría añade una decisión de worldgen necesaria antes de usar latentes
verificados en e3:

- **Integrar primero sólo existentes:** buscar localizaciones físicas con
  seguridad; menos oportunidades posibles y ninguna promesa de infraestructura apta.
- **Manifiesto procedural inmutable:** derivar familias de slots de una base
  authored fija y guardrail inmutable, conservar procedencia y separar direcciones
  estables de ids asignados. Trabajo amplio del generador; puede alterar mapas,
  cupos y compatibilidad futura de saves. Requiere autorización y contrato topológico.
- **Persistir manifiesto/reservas al crear:** estabiliza una base establecida,
  pero no elimina por sí mismo la dependencia de qué manifiesto se crea primero.
  Sólo satisface preexistencia si sus reglas se fijan con independencia de la
  recuperación; también requiere autorización.

Slots latentes/densidad adicionales son otra decisión del desarrollador, no un
remedio introducido aquí. Acotar la Z gaussiana cambiaría distribución y no
resolvería guardrails, inserciones ajenas, colisiones ni topología. No se
rediseña, altera densidad ni regenera sectores existentes. Nunca se eliminan
partidas reales. La parte pura acotada es la entrega permitida por el límite de
intervención, no la consecución de la invariante completa de preexistencia.

## Verificación y entrega por archivo

Intérprete canónico: `/home/jon/prog/retorno_case/retorno_venv/bin/python`;
ejecutar con `PYTHONPATH=src`. Los dos smokes nuevos contienen **9 grupos de
caracterización y 17 del catálogo**. Cubren resultados congelados, orden de
consultas/diccionarios, pureza pickle/RNG integral, escritores prohibidos, tres
regiones, cinco arquetipos y 0–3 slots, fronteras región real/plantilla, nodos
generados y authored, hub de origen ausente, pools consumidos, nave dañada/sin
recursos, conservación del conocimiento de primary protegido, tres ciclos
temporales de guardado, tres procesos hash (`1/7/99`), cotas técnicas y estado inválido.

También pasan: `worldgen_sparse_archetypes`, `worldgen_modules_pool`,
`procedural_radiation`, `galaxy_physical_model`, `route_hop_cap`,
`known_routes_integrity`, `nav_abort_waypoint_cleanup`,
`route_solve_out_of_range_origins`, `sector_intel_validation`, `scan_job`,
`sensor_detection_factor`, `save_load`, `deadnode_chain_planner`,
`deadnode_chain_detours`, `deadnode_opportunity_selection` (todos `_smoke.py`).
Las dependencias del orden observadas son caracterizaciones que pasan, no cambios
de mecánica ni fallos de prueba sin explicar. No se usan guardados reales.

Una comparación adicional con el generador cargado directamente de `HEAD`
confirmó igualdad de GameState serializado completo tras ocho solicitudes en
orden directo e inverso para semillas `2`, `29`, `271828` (seis ejecuciones
independientes). La extracción del muestreador conserva la generación productiva,
incluidas sus dependencias conocidas del orden.

Benchmark: `tests/worldgen_preexistence_catalog_smoke.py --benchmark`, semilla
`271828`, 3 llamadas/celda sin construcción de fixture. El pico incremental de
memoria Python se mide en otra llamada tracemalloc. Los nodos de fondo son
derelicts remotos sintéticos; antes de añadirlos existen cuatro nodos físicos
authored/técnicos. Son mediciones, no garantía de latencia:

| Fondo | Sectores | Mediana / máximo ms | Pico KiB |
| --- | --- | --- | --- |
| 0 | 1 / 9 / 64 | 0.906/0.994 · 1.898/2.166 · 8.790/8.980 | 21.7 / 31.3 / 73.9 |
| 1000 | 1 / 9 / 64 | 2.906/3.014 · 4.139/4.192 · 10.401/10.799 | 52.1 / 63.4 / 105.9 |
| 3000 | 1 / 9 / 64 | 7.269/7.462 · 7.664/8.354 · 14.647/14.758 | 210.9 / 223.3 / 272.4 |

Una pasada examina N nodos físicos y después sólo los sectores solicitados.
Memoria auxiliar O(N + sectores solicitados + registros devueltos); se añade el
coste habitual de ordenar. No se genera el universo entero ni se copia GameState
en profundidad.

| Archivos (rutas relativas al repositorio) | Cambio |
| --- | --- |
| `src/retorno/worldgen/catalog.py` | Nueva API tipada y acotada de evidencia de sólo lectura. |
| `src/retorno/worldgen/generator.py` | Extracción del mismo muestreador canónico de coordenadas/RNG para reutilizarlo. |
| `tests/worldgen_preexistence_characterization_smoke.py` | Nueve testigos ejecutables de dependencias vigentes. |
| `tests/worldgen_preexistence_catalog_smoke.py` | Diecisiete grupos de regresión de API y benchmark opcional. |
| `docs/design/procedural-preexistence.md`, `.es.md` | Este diseño bilingüe, evidencias, límites y entrega. |
| `docs/design/navigation-recovery-contract.md`, `.es.md` | Decisiones vinculantes 4D-3e1 y estado parcial seguro. |
| `docs/design/deadnode-chain-planner.md`, `.es.md` | Divergencias del planificador actual respecto al nuevo contrato estructural. |
| `docs/systems/world-generation.md`, `.es.md` | Enlace al catálogo y sustitución de afirmaciones sin prueba sobre orden/Z por evidencia. |
| `docs/README.md`, `README.es.md` | Índice de la nueva referencia bilingüe. |

Manuales y ayuda del juego no necesitan cambios: no cambian comandos, texto,
claves de localización ni comportamiento visible. La validación Git y el ZIP
sólo con cambios se informan en la entrega; no se hace staging, commit ni push.
