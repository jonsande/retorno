# Manifiesto procedural estable — contrato y prototipo 4D-3e1b

**Actualización 4D-3e2:** este documento conserva la evidencia histórica de su fase.
El contrato productivo vigente está en [Integración del worldgen histórico](historical-worldgen-integration.es.md).
El prototipo usa ahora el núcleo compartido y distingue su certificación por ámbito/razones;
el catálogo condicional legacy queda en fixtures de pruebas. Las limitaciones productivas
descritas aquí se leen como estado anterior, no como descripción del runtime actual.

Versión inglesa: [stable-procedural-manifest.md](stable-procedural-manifest.md).
Coordinación: [hoja de ruta vigente](roadmap-worldgen-lore-f-dead01.es.md).

## Informe ejecutivo y alcance

Se demuestra un manifiesto histórico independiente del registro materializado,
del orden de consulta/exploración y de necesidades de lore o failsafes. Es un
**prototipo puro, aislado del runtime**, no una sustitución de worldgen. Sus
políticas experimentales no quedan aprobadas para producción por superar pruebas.
La comparación detecta menos enlaces con la política local ensayada y una pequeña
diferencia de ocupación en halo: integrar sin decisión explícita sería cambiar
la distribución del universo. No se recomienda una sustitución directa en 4D-3e2.

Inspección inicial: rama `main`, árbol limpio, HEAD
`000e05bc40993ba45804c30d3fff51df3c655bb3`; `git ls-remote origin refs/heads/main`
confirmó exactamente ese SHA. `dc06d92` contiene 4D-3e1. Se revisaron `AGENTS.md`,
hoja de ruta, canon 0.3 y guía de coherencia, contrato navegación/recuperación,
catálogo, generador, bootstrap, modelos, datos activos y testigos legacy.
Aplican `C-WORLD-001`, `C-INF-004` y las decisiones D01–D04/D14–D17 de la hoja.
No se implementan las nuevas reglas temporales del canon.

La hoja de ruta actual asigna **e2 a integración de worldgen, e3 a memoria de
scan, e4 a lore/intel y e5 a F-DEAD-01**; prevalece sobre el reparto provisional
propuesto en la documentación histórica de 4D-3e1. No se reescribe la hoja.

## Contrato aprobado frente a hipótesis ensayadas

**Aprobado:** distinguir emplazamiento histórico determinado, nodo materializado,
conocimiento del jugador y ruta operativa. La historia depende de semilla, reglas
versionadas y base authored; ninguna consulta concede descubrimiento, recursos,
rutas, recepción ni permiso de materialización. Mantener 45 ly, dispersión y
configuración vigentes y la posibilidad de vacío/aislamiento; no garantizar rescate.

**Prototipado, pendiente de decisión productiva:** cupos por sector generador
contra base authored fija; guardrail en el 3×3 XY del origen; hubs/topología por
cohorte de procedencia; identidades con namespace; asignación intersectorial por
selección mutua entre las primeras k propuestas locales. Son soluciones concretas
para evaluar el contrato, no una nueva política de balance implantada.

## API y alcance de la certificación

[`manifest_prototype.py`](../../src/retorno/worldgen/manifest_prototype.py):

```python
definition = define_manifest(271828)
result = query_manifest(definition, (
    "S+15126_+000_+000", "S+15126_+000_+001",
))
lookup = lookup_site(definition, result.sectors[0].sites[0].identity)
```

`define_manifest` captura datos físicos authored y JSON de plantillas/arquetipos
como valores inmutables. La carga de ficheros sólo ocurre en esta frontera; las
consultas posteriores no leen el registro físico ni vuelven a cargar datos.
No acepta `GameState`. Reutiliza `_configuration_key` del catálogo y los helpers
canónicos `_select_archetype`, `_plan_sector_kinds`, `_sample_sector_node`,
regiones y parser. El guardrail vigente se ejecuta sobre una vista local nueva;
su escritura de flag nunca alcanza un estado de juego. No se duplica un generador
productivo ni se modifica `ensure_sector_generated`.

`ManifestDefinition`, `HistoricalSite`, `SectorManifest`, `HistoricalEdge`,
`ManifestResult`, `SiteIdentity` y resultados de consulta son valores congelados.
Se validan semilla, versión, configuración, caps y coordenadas. El entorno de
regiones/cap debe coincidir con la definición capturada; un cambio exige una
definición nueva y no reinterpreta silenciosamente resultados anteriores.

| Estado | Garantía real |
| --- | --- |
| `certified_for_prototype` | Para esta definición/reglas experimentales, quedan determinados identidad, procedencia, posición, sector físico, tipo, región, hubs y aristas devueltas. No certifica el universo legacy ni aprobación productiva. |
| `conditional` | Materialización productiva pendiente y no autorizada por la consulta. |
| `invalid` | `lookup_site` rechaza scope ajeno, dirección malformada, authored ausente o slot inexistente de esta definición. Configuración/solicitud inválidas lanzan excepciones antes de emitir una certificación. |
| `not_evaluated` | Inventario físico inverso completo, recursos/pools/ficheros, radiación/edad histórica y sucesos especiales dinámicos. No representan cero, ausencia ni permiso. |

Las muestras `conditional` de 4D-3e1 no se convierten en direcciones del nuevo
manifiesto; un lookup de su clave se rechaza. Sólo las reglas explícitas de una
definición nueva determinan los emplazamientos del prototipo. No se certifican
elegibilidad narrativa ni acceso operativo de F-DEAD-01.

## A. Base authored, cupos e identidad

La base actual contiene `UNKNOWN`, `ECHO_7`, `HARBOR_12`, `ARCHIVE_01`, con las
mismas coordenadas/tipos/hubs que bootstrap. `RETORNO_SHIP` se excluye como hace
bootstrap. `UNKNOWN` es un marcador técnico, no una instalación histórica apta
para recuperación. Sus coordenadas compartidas con ECHO no fusionan identidades.
El prototipo preserva explícitamente su contribución inicial al cupo; decidir
si debe consumirlo en el manifiesto productivo sigue pendiente.

Sólo esa base fija consume cupos antes de `_plan_sector_kinds`. No los consumen
pecios de otro sector ni inserciones posteriores de scheduler/failsafe. Se
conservan tiradas, pesos, probabilidades, caps y prioridad de hubs authored. Una
base explícita que exceda el cap se conserva y no obtiene slots adicionales.
Los ids authored duplicados se rechazan; el legacy conserva el primero según
orden de ficheros. No se añade automáticamente un ECHO ausente de una base
experimental: el fallback productivo sigue fuera del manifiesto.

Identidad propuesta: `SiteIdentity(scope, namespace, local_id)`.

- `scope`: SHA-256 de semilla, versión `prototype-4d3e1b-v1`, huella de reglas,
  base authored ordenada y cap. La huella reutilizada incluye orden explícito de
  pesos, regiones físicas y tamaño sectorial. Cambiar la base crea otro universo;
  no se promete estabilidad entre definiciones distintas.
- `authored`: `local_id` es el id authored literal.
- `procedural`: `local_id` es la codificación canónica `(sector_generador, índice)`.
  No se acorta a 24 bits ni se consulta un registro de ids.
- `special`: namespace reservado; no lo genera este prototipo.

La codificación JSON de los tres campos conserva el namespace. Dentro de un
scope, direcciones de sectores/índices distintos y authored únicos no colisionan.
La huella entre universos tiene la hipótesis criptográfica habitual; no es una
prueba matemática de ausencia de colisiones SHA-256 entre todos los universos.
Se fuerzan colisiones de hints procedurales, authored contra hint y authored cuyo
literal parece una identidad codificada: las identidades siguen siendo distintas.

`legacy_id_hint` reproduce la base corta sólo para diagnóstico/orden de hubs;
**no es un node_id definitivo**. La identidad interna codificada tampoco es un
nuevo token de comando `NODE`/CLI. Conservar alias authored y decidir la
representación persistida/operativa requiere trabajo explícito en e2. Especiales
dinámicos no podrán apropiarse del namespace histórico.

## B. Guardrail fijo

Se evalúa la regla existente una vez, conceptualmente, sobre el vecindario
`[-1,1]×[-1,1]×{0}` centrado en el origen operacional, para cada definición.
Mismos overrides, criterio de vecino temprano y semillas del legacy, pero sin
esperar a la primera solicitud del jugador ni respetar sectores ya generados.
No se fuerza conectividad ni una tirada de hub natural cuando el legacy no la
forzaría. La adopción productiva de esta vecindad concreta necesita aprobación.

## C. Z, pertenencia espacial y completitud

Se conservan exactamente dos extracciones uniformes X/Y y la Z gaussiana del
muestreador compartido, sin truncado, rechazo ni desplazamiento correctivo.
Cada registro conserva sector generador y sector físico calculado por `floor`.
El inventario por procedencia es completo; no se declara completo el inventario
espacial de un sector a partir de él. La región de plantilla usa el centro del
sector generador; la región del emplazamiento usa su posición real, incluso en
fronteras esféricas. No se sustituye un tipo por conveniencia.

Con semilla `271828`, el ship generado en `S+15126_+000_+000` está en
`(151266.79157885376,9.329097599582711,10.057691279289713)`, dentro de Z=1.
El sector generador superior conserva su propio slot: dos ubicaciones ocupan
ese sector físico al consultar ambas procedencias. En legacy quedan una o dos
según orden, porque el outlier consume el cupo posterior.

Solución viable para e2: conservar esta procedencia y añadir consulta inversa
certificada antes de conectar scan/materialización. Opciones pendientes:

1. **Fijar y demostrar el soporte numérico del kernel.** El `gauss` CPython actual
   usa `cos(2πu)*sqrt(-2 log(1-v))`, con uniformes de 53 bits. Sugiere una cota
   conservadora menor de `8.58σ`; con σ≤2, un índice inverso Z podría inspeccionar
   cinco planos generadores (±2), incluyendo margen de redondeo. No altera la
   distribución implementada. Esta cota **no queda certificada por el prototipo**:
   exige versionar kernel, demostrar redondeos/rango de coordenadas y considerar
   también redondeos X/Y. Es la opción recomendada para estudiar en e2.
2. **Índice inverso persistido de procedencias ya calculadas:** útil como caché;
   por sí solo no certifica ausencia de entradas de procedencias no examinadas.
3. **Truncar, recortar o remuestrear Z:** cambia distribución/colocación y requiere
   aprobación. No se hace aquí. La masa gaussiana ideal fuera de la celda es
   aproximadamente `2.29e-62` disk, `4.10e-10` bulge y **1.2419 %** halo.

La distribución matemática ideal es no acotada; no se afirma que la implementación
finita de CPython tenga soporte infinito. Tampoco se promete reproducibilidad
bit a bit entre versiones de Python/libm no verificadas. El cambio de cupos por
procedencia evita la dependencia, pero es una política de ocupación que debe
aprobarse; no es la única corrección posible ni una ampliación de slots latentes.

## D/E. Hubs y topología histórica acotada

La cohorte de un sector generador contiene sus authored fijos y sus slots,
incluidos los que físicamente salen por Z. Selección de hub: primero un hub
jugable, después hint lexicográfico con identidad completa como desempate.
El hub de tipo apto se vuelve jugable como en el legacy; hay un único hub
topológico por cohorte no vacía. Estrella y enlaces extra reutilizan las reglas,
probabilidades y semillas actuales. Las aristas no autorizan `known_links`.

Para enlaces intersectoriales:

1. Examinar los ocho vecinos XY del sector generador, al mismo índice Z.
2. Exigir hubs, capacidad configurada, tirada de pareja vigente y distancia ≤45 ly.
3. Ordenar parejas candidatas por prioridad BLAKE2b estable de semilla/pareja.
4. Cada sector propone sus primeras k parejas, siendo k su presupuesto vigente.
   Sólo se acepta una pareja si ambos extremos la proponen.

La intersección garantiza reciprocidad y grado≤k sin contadores compartidos ni
orden de inserción. Certificar aristas incidentes necesita como máximo un radio
XY 2 de dependencias, hasta 25 sectores generadores por solicitado. Puede dejar
cupo sin usar y **no es un matching maximal**. Una ordenación greedy global puede
necesitar una cadena de dependencias no acotada; fijar sólo una semilla no basta.
Una alternativa con rondas de colores de aristas podría llenar más cupos con
dependencia finita, pero tendría otra distribución y no se implementa aquí.

El resultado incluye extremos externos como `boundary_sites`, sin publicar sus
contactos. Consultar vecinos posteriormente no cambia una arista previamente
determinada. Vacío, componentes aisladas y callejones sin salida se conservan.
Se permiten aristas de distancia cero entre identidades distintas como el
legacy físico ECHO/UNKNOWN; no hay autoaristas ni autorización de viaje por ello.

## Comparación reproducible y consecuencias de distribución

[`worldgen_manifest_comparison.py`](../../tests/worldgen_manifest_comparison.py)
produce [las mediciones completas](../testing/manifest-prototype-measurements.json).
Semillas `0..7`, `29`, `271828`; 64 sectores por región y semilla (8×4 XY, dos
planos Z), más nueve del origen: **2010 sectores objetivo, 40 fixtures**.
Las solicitudes públicas legacy se ejecutan en orden directo y luego inverso
sobre estados separados; ambos generan la misma unión (120 sectores por parche
regional, 25 en el inicial). El prototipo consulta esa misma unión con cota
técnica explícita. Se capturan procedencia al crear nodos y tipo de enlace en la
pasada original, sin cambiar su algoritmo ni sus aserciones.

Conteos de nodos por sector usan **procedencia generadora**. Ocupación física
incluye entradas observadas desde la unión finita generada; no es inventario
global. Los grafos de abajo son inducidos sobre los sectores objetivo y pueden
conectarse a través de nodos externos excluidos; sus componentes no prueban
aislamiento galáctico ni accesibilidad operativa. Todas las cifras son sumas de
las diez semillas, salvo fracciones/medias indicadas.

| Parche (sectores) | Nodos directo / inverso / prototipo | Nodos/sector directo → prototipo | Vacíos directo → prototipo |
| --- | --- | --- | --- |
| Disk (640) | 1040 / 1040 / 1040 | 1.625 → 1.625 | 12.0313 % → 12.0313 % |
| Bulge (640) | 985 / 985 / 985 | 1.539062 → 1.539062 | 15.1562 % → 15.1562 % |
| Halo (640) | 746 / 747 / 748 | 1.165625 → 1.168750 | 29.3750 % → 29.0625 % |
| Inicial (90) | 154 / 154 / 154 | 1.711111 → 1.711111 | 12.2222 % → 12.2222 % |

En halo hay **dos derelicts más** frente al directo: +0.2681 % de nodos, sin
nuevos pesos/slots máximos. Arquetipos e histogramas de tipos coinciden en las
otras tres muestras. En estos parches no cambian los arquetipos por sector; esto
no invalida el testigo específico de guardrail de semilla 29 fuera de este orden
inicial. Los histogramas íntegros por arquetipo, tipo y región real están en JSON.

| Parche | Hubs jugables directo → proto | Hubs topológicos directo → proto | Enlaces internos directo → proto | Intersectoriales directo / inverso / proto |
| --- | --- | --- | --- | --- |
| Disk | 254 → 254 | 563 → 563 | 513 → 513 | 126 / 133 / 106 |
| Bulge | 174 → 174 | 543 → 543 | 466 → 466 | 86 / 88 / 81 |
| Halo | 100 → 99 | 451 → 454 | 299 → 308 | 39 / 41 / 37 |
| Inicial | 42 → 42 | 79 → 79 | 78 → 78 | 20 / 18 / 13 |

| Parche | Componentes directo / proto | Componentes de un nodo directo / proto | Sectores de grado uno directo / proto |
| --- | --- | --- | --- |
| Disk | 438 / 458 | 165 / 178 | 190 / 170 |
| Bulge | 457 / 462 | 184 / 190 | 150 / 142 |
| Halo | 420 / 417 | 235 / 229 | 76 / 72 |
| Inicial | 59 / 66 | 19 / 21 | 28 / 18 |

El componente inicial de ECHO dentro de los nueve sectores contiene en total
51 nodos en directo, 52 en inverso y 45 en el prototipo; medianas por semilla
4, 4.5 y 3. No son rutas conocidas ni una promesa de salida. Hay 11 outliers Z
en halo en cada modelo y cero en las otras muestras. La ocupación física observada
de halo es 740 / 741 / 742 nodos, respectivamente; el distinto cupo posterior
explica la diferencia sin cambiar σ.

La pérdida de enlaces de disk (−15.87 %) e inicial (−35 %, muestra pequeña)
**no es un coste inevitable de corregir el orden**: depende de la política
mutua ensayada y requiere aceptación o una alternativa topológica. Igualmente,
la pequeña subida de nodos halo depende de elegir cupos por procedencia. Lo
inevitable es no reproducir simultáneamente todos los mundos legacy divergentes,
no estas magnitudes concretas de cambio. No se ajusta ningún parámetro para
mejorar el resultado ni se hace inferencia estadística poblacional.

## Pruebas, rendimiento y límites demostrados

Intérprete `/home/jon/prog/retorno_case/retorno_venv/bin/python`, `PYTHONPATH=src`:

```text
.../retorno_venv/bin/python tests/worldgen_manifest_prototype_smoke.py
.../retorno_venv/bin/python tests/worldgen_manifest_comparison.py --output docs/testing/manifest-prototype-measurements.json
```

**17 grupos nuevos**: igualdad repetida/inversa/duplicados y por consulta aislada,
subprocesos `PYTHONHASHSEED=1/7/99`, exploración/materialización legacy simuladas,
pureza de definición/GameState/RNG, escritores y loaders prohibidos, colisiones
forzadas, authored/overflow de caps, fronteras regionales, Z, guardrail, reciprocidad,
presupuestos y cotas. Las aserciones de los testigos legacy permanecen intactas.

Pasan **24 scripts**: el nuevo y los dos smokes 4D-3e1; sparse archetypes, modules
pool, procedural radiation, galaxy model, route hop cap, known routes integrity,
abort waypoint, route solve origins, sector intel, scan job, sensor factor,
save/load, los tres planificadores 4D-3b/c/d, cooldown cero, lore, preferencia de
canales/desbloqueo, forced hidden ad hoc, secondary weights/hard y retry uplink.
No se modifica ni abre una partida real. Los guardados temporales sólo pertenecen
a regresiones existentes. Rutas y pares EN/ES de los documentos se validan.

El benchmark del comparador excluye crear la definición y usa tres llamadas por
familia, más una medición tracemalloc separada. Para 1/9/64 solicitudes se evalúan
14/30/151 cohortes; el orden de magnitud es 3/6/30 ms, con picos de unos
32/50/158 KiB en esta máquina. Cifras exactas y versión de Python están en JSON;
no son límites de latencia. No hay caché global ni dependencia del tamaño de
`space.nodes`. Memoria/trabajo dependen de base authored y cierre sectorial
acotado, no de toda la galaxia. Superar una cota técnica rechaza la petición;
nunca prueba ausencia. La ausencia de integración productiva y de inventario
físico inverso no se presenta como una propiedad ya resuelta.

## Decisiones para 4D-3e2 y compatibilidad

Antes de sustituir worldgen, aprobar o revisar: contribución de `UNKNOWN` y
fallback ECHO a la base; cupos por procedencia; vecindario del guardrail; topología
por cohorte y arbitraje local con la reducción medida de enlaces; direcciones
persistidas/alias authored y namespace de especiales; kernel RNG/versionado y
consulta física inversa. Recomendación: conservar la identidad tipada y la base
inmutable como contrato; **no adoptar silenciosamente la política topológica
ensayada**. Resolver esas decisiones dentro de la preparación de e2, sin abrir
una campaña indefinida de optimización.

No es una sustitución compatible con saves legacy ni con sus ids/counters.
Integrar exige fijar versión de universo por partida, rechazar incompatibilidades
explícitamente, conservar procedencia y preparar materialización idempotente y
topología sin leaks. No exige migraciones históricas complejas ni borrar saves.
Radiación/loot con semillas dependientes de node_id necesitan una política de
semilla estable en e2; no se han recalculado ni comparado recursos aquí.

Lore podrá seleccionar/reservar estos emplazamientos, pero no crearlos por
necesidad; intel tendrá que resolver identidad, no fabricar destinos a partir de
centros/coords; F-DEAD-01 deberá evaluar protección y acceso dirigido, no recursos.
Nada de ello está integrado. Las excepciones de scan natural y resolución manual
siguen bajo las reglas productivas actuales. Manuales/ayuda no requieren cambios:
no hay comandos, texto de jugador ni comportamiento observable nuevos.

## Archivos y cierre Git

| Archivo relativo | Propósito |
| --- | --- |
| `src/retorno/worldgen/manifest_prototype.py` | Definición inmutable, consultas históricas acotadas, identidad, hubs y aristas experimentales. |
| `tests/worldgen_manifest_prototype_smoke.py` | 17 grupos focalizados, incluidos testigos legacy intactos. |
| `tests/worldgen_manifest_comparison.py` | Comparación de diez semillas, instrumentación de procedencia/tipo de enlace y benchmark. |
| `docs/testing/manifest-prototype-measurements.json` | Evidencia reproducible versionada, no caché ni artefacto temporal. |
| `docs/design/stable-procedural-manifest.es.md` | Este informe/contrato español. |
| `docs/design/stable-procedural-manifest.md` | Pareja inglesa con el mismo alcance y datos. |
| `docs/README.es.md` | Enlace al nuevo contrato/prototipo. |
| `docs/README.md` | Pareja inglesa del índice. |

Estado de entrega: `main`, mismo HEAD inicial/remoto confirmado, dos documentos
de índice modificados y seis archivos nuevos de esta entrega; índice de Git vacío.
Durante el trabajo aparecieron además seis archivos no rastreados bajo
`narrative/operacion_amanecer_narrativa_v0.1/amanecer_paquete/`, ajenos a esta fase:
se conservan intactos y se excluyen del ZIP. No se toca
ningún archivo productivo existente ni los testigos 4D-3e1. Resultado de
`git diff --check`: correcto. El ZIP de entrega contiene exclusivamente esos
ocho archivos con rutas relativas; no incluye saves, entornos, cachés, archivos
intactos ni temporales. No se hace staging, commit ni push. La entrega se detiene
para revisión externa; certificación experimental no significa autorización de e2.
