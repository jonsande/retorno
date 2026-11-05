> **Actualización implementada 4D-3e4 (2026-11-05).** Para catálogos con requisitos físicos nuevos, el manifiesto se fija en bootstrap, con identidad de catálogo y resultados compilados. Sin declaraciones adicionales se conserva el ámbito físico previo y la selección de semilla anterior a materialización. El esquema 3 guarda snapshot narrativo obligatorio; se rechazan saves anteriores sin él y catálogos modificados. Rige la hoja de ruta v1.2. El cuerpo siguiente documenta e2 y conserva su contexto histórico. La referencia vigente y sus ejemplos ejecutables son [Requisitos narrativos físicos](../narrative-world-contract.es.md). El cuerpo anterior conservado a continuación es histórico donde contradiga esta actualización.

# Integración del worldgen histórico — 4D-3e2

Inglés: [historical-worldgen-integration.md](historical-worldgen-integration.md).
Estado: implementado en el árbol de revisión basado en `5cdde28`; pendiente de
aprobación externa. Sigue vinculante la hoja de ruta v1.1
([ES](roadmap-worldgen-lore-f-dead01.es.md)).

## Contrato productivo

`historical-world-v1` es la versión productiva del manifiesto. `manifest.py`
define el universo inmutable y las consultas puras; `generator.py` materializa;
`topology.py` aporta la política de emparejamiento finita. El módulo del prototipo
es una entrada compatible al mismo núcleo con la política anterior de top-k
mutuo. El generador y catálogo legacy sólo existen como fixtures de pruebas.
No hay dos generadores productivos independientes ni caché global mutable del
universo. La memoización pertenece a cada sesión de consulta o materialización.

Se mantienen cuatro capas: existencia histórica, nodos materializados,
conocimiento del jugador y rutas conocidas operativas. Una consulta devuelve
evidencia, no permiso para insertar ni publicar rutas. `catalog_sector` y
`catalog_sectors` consultan ahora las cohortes generadoras del manifiesto;
`VERIFIED` no procede de promover una muestra condicional legacy. Los nodos
especiales/dinámicos quedan fuera de ese catálogo y continúan en el registro físico.

Versión, semilla, reglas físicas y base authored definen un ámbito. Bootstrap
registra la huella de reglas; la definición completa se fija al materializar o
guardar por primera vez. Consultar no fija ni modifica el juego. Después de
fijarla se rechazan cambios de semilla/reglas. `debug seed` comprueba esto antes
de modificar el estado en ambos frontales, sin cambiar la sintaxis. Antes de
fijarla conserva su uso para elegir semillas de prueba. `WorldState.rng_seed`
sigue siendo un campo legacy; se captura `MetaState.rng_seed`.

La huella incluye plantillas y arquetipos (también orden de pesos), transformación
de coordenadas, tamaño sectorial, balance de radiación/drones, módulos ordenados,
definiciones físicas/salvage authored y kernel gaussiano soportado. Excluye prosa
y archivos narrativos. Cambiar el algoritmo exige otra versión explícita; la
huella no versiona automáticamente todo el código. Entre universos se presupone
la resistencia de SHA-256 a colisiones.

## Identidad e IDs operativos

`SiteIdentity(scope, namespace, local_id)` es la identidad histórica. Authored
conserva su ID literal; la dirección procedural codifica sector generador e
índice. La representación operativa es otra capa:

- Los IDs authored (`UNKNOWN`, `ECHO_7`, `HARBOR_12`, `ARCHIVE_01` y futuras
  declaraciones explícitas) no cambian.
- Los procedurales usan `S+x_y_z:WG1_<SHA-256 completo del ámbito>_<índice>`,
  con el formato sectorial canónico con signos, abreviado aquí.
- Si un ID authored inmutable reserva ese texto exacto, `WG1C1`, `WG1C2`, etc.
  seleccionan la primera dirección libre. No se consulta el orden del registro
  materializado. Un ocupante físico incompatible provoca fallo antes de mutar.
- `legacy_id_hint` sólo ordena hubs y sirve para diagnóstico/nombre, nunca para
  garantizar unicidad. Los especiales/dinámicos conservan su mecanismo separado.
  `historical_key` y `generation_sector_id` registran procedencia.

`operative_id` y `resolve_operative_id` resuelven exactamente los IDs canónicos.
El helper vigente de compatibilidad `NODE:`/`LINK:` resuelve el ID nuevo a su
sector físico, incluido el desbordamiento Z. No cambia la sintaxis de comandos.
La intel literal no resuelta sigue siendo intel según el contrato existente.
Esto no concede nueva autoridad de navegación ni de fuente informativa.

## Base authored y condiciones iniciales

El mismo loader de `data/locations/*.json` alimenta bootstrap y manifiesto.
Los IDs authored duplicados se rechazan explícitamente. Coordenadas, nombres,
kinds, radiación authored y salvage conservan el comportamiento de bootstrap.
Una futura estación específica de arco puede declararse mediante ese mecanismo;
bootstrap la inserta físicamente sin añadir conocimiento salvo flags explícitos
de revelación ya existentes. Mencionarla en prosa no la declara ni revela.

`RETORNO_SHIP` conserva su tratamiento de nave/filesystem y se excluye de las
cohortes de destinos históricos. `UNKNOWN` sigue ocupando cupo authored en el
origen, incluso tras su eliminación normal: los cupos históricos no cambian
porque desaparezca el marcador. Nunca se resucita. `ECHO_7` sigue siendo el hub
declarado del origen; se elimina el fallback redundante que podía fabricarlo
si faltaba. La base activa lo sigue proporcionando. Ni una declaración ausente
ni una necesidad narrativa crean un sustituto.

Los cupos pertenecen a cohortes generadoras y cuentan su base authored fija.
La entrada física desde otro sector y los especiales runtime no consumen esos
cupos. Se conservan declaraciones authored que superen caps, sin crear slots
extra. Así se elimina la dependencia del orden y de la entrada Z sin ajustar
cantidades, probabilidades ni límites de tipos. Un sector físico puede recibir
más nodos que el cap de su cohorte; los consumidores deben distinguir inventarios.

## Consulta inversa completa y dominio numérico

`query_manifest` responde por cohortes generadoras y aristas históricas incidentes.
`query_physical_sectors` responde todos los emplazamientos históricos cuyas
coordenadas reales pertenecen a los sectores físicos solicitados. No se trunca,
remuestrea ni cambia la gaussiana. Ambas consultas son de sólo lectura y no
recorren toda la galaxia.

La certificación soporta CPython 3.12, binary64, radix 2, mantisa de 53 bits y
redondeo al más cercano. Se comprueba el SHA-256 fijado del código exacto de
`Random.gauss`. El valor absoluto del índice sectorial soportado no supera
`2**48 - 32`; la consulta física reserva cuatro índices interiores. Las plantillas
productivas deben cumplir `0 < z_sigma <= 2`.

Con un RNG nuevo, `random()` de CPython devuelve múltiplos de `2**-53` en `[0,1)`.
La gaussiana Box–Muller nueva usa
`sqrt(-2*log(1-u)) * cos(2*pi*v)`. Su módulo estándar queda acotado por
`sqrt(106*log(2)) ≈ 8.572 < 8.58 < 9`. El sampler llama una vez a `gauss` sobre
un RNG local nuevo; su segunda variable cacheada no interviene. El entorno
soportado es esa implementación fijada con operaciones binary64 estándar: la
cota corresponde al muestreador finito implementado, no a una gaussiana ideal
ilimitada.

En el dominio soportado, las fronteras/centros enteros `10*i` y `10*i+5` se
representan exactamente por debajo de `2**52`. Se usa la envolvente conservadora
`9*sigma + 2 ly`, con margen muy superior al redondeo de multiplicación, suma,
funciones elementales y división sectorial binary64 en ese dominio. Con sigma
máxima 2, la envolvente no supera 20 ly. Una procedencia a tres índices Z tiene
su centro al menos a 25 ly del intervalo destino; sólo pueden contribuir
`target_z-2 .. target_z+2`. Se filtran intervalos por la envolvente de su plantilla
y finalmente se comprueba la pertenencia con las coordenadas muestreadas reales.

X/Y parten de una frontera inferior exacta y suman `10*random()`. El redondeo
monótono puede alcanzar el extremo superior a gran escala. El índice físico es
el generador o su sucesor; la inversa incluye destino y procedencia anterior
en cada eje XY. Hay como máximo **20 procedencias por sector físico**, no sólo
los vecinos Z del mismo XY. Authored pertenece a su propia cohorte física.
La deduplicación por identidad evita repeticiones al agrupar solicitudes.

Las consultas puras admiten por defecto 64 sectores. Las sesiones limitan las
cohortes calculadas a 32.768. Runtime admite hasta 64 solicitudes, expande su
unión 3×3 XY (máximo 576 sectores físicos) y prepara hasta 2.048 nodos nuevos.
Los fallos de dominio, configuración, trabajo o colisión lanzan error antes de
devolver inventario o insertar nodos. No hay fallback parcial/vacío exitoso.
Son límites técnicos explícitos, no frontera galáctica ni radio de búsqueda de
recuperación. Las pruebas cubren uniformes extremos, redondeo XY lejano,
rechazo de dominio, agotamiento de trabajo y el outlier físico de semilla 271828.

## Política de topología y guardrail

El guardrail se evalúa sobre el 3×3 XY fijo del origen, con los overrides,
criterio de vecino temprano y claves RNG existentes. No depende del primer
lugar solicitado. No fuerza una tirada natural de hub ni garantiza progresión
universal.

Las estrellas internas y aristas extra usan el muestreo canónico, preferencia
por hub jugable, orden de hint legacy con identidad histórica para desempatar
y cap de 45 ly. La topología pertenece a la cohorte generadora aunque haya
miembros desbordados en Z.

La alternativa al top-k mutuo que infrautilizaba cupos es un emparejamiento
maximal con presupuestos. Primero se consideran pares enteramente dentro del
3×3 fijo inicial en el orden legacy de la primera solicitud canónica, reservando
sus presupuestos. Después, cuatro direcciones XY no orientadas
`(1,0),(0,1),(1,1),(1,-1)` se dividen por paridad en ocho emparejamientos disjuntos.
Rondas fijas 0–7 consideran una vez cada otro par vecino. Se mantienen RNG y
probabilidad del par, presupuestos de ambos extremos y cap de 45 ly. Los pares
internos iniciales se omiten en las rondas exteriores.

La aceptación sólo consulta grados de rondas anteriores: la profundidad de
dependencias no supera ocho saltos vecinales más el pase inicial fijo. La
memoización local acota trabajo repetido; no existe cadena greedy ilimitada.
Cada par viable rechazado tiene un extremo saturado que permanece saturado:
el resultado es maximal, no necesariamente máximo. Es recíproco e independiente
del orden. Siguen siendo válidas regiones vacías, componentes aisladas y ramas
sin continuación.

## Materialización, recursos y persistencia

`ensure_sector_generated` conserva su API, expande la unión física 3×3 XY,
consulta inventario inverso, calcula dependencias justificadas de topología y
prepara nodos/propiedades/aristas antes de insertar. Sólo inserta emplazamientos
dentro de esa unión física. No inserta dependencias ni extremos de frontera
sólo para completar una arista. Se vincula cuando existen ambos extremos;
la expansión posterior añade esa misma arista predeterminada sin sustituir
las elecciones históricas. Los especiales conservan sus mecanismos separados.

`SectorGenState.node_ids` contiene residentes físicos; `generation_node_ids`,
miembros actualmente materializados de la cohorte. Hubs y contadores históricos
usan procedencia. `physical_inventory_complete` acompaña a los sectores físicos
generados. `intersector_link_pairs` queda como campo compatible inerte: ya no
decide historia. Consulta/materialización no modifican nodos conocidos,
contactos, rutas conocidas, archivos, pools ni RNG de juego.

Radiación, scrap, módulos, drones recuperables y nombres reutilizan helpers y
configuraciones vigentes. Las claves RNG de recursos usan la identidad histórica
completa en vez del ID corto operativo susceptible de colisión. Cambian tiradas
concretas; probabilidades, rangos, pools y cantidades configuradas no cambian.
Los recursos existentes, flags dry y agotamiento se conservan: repetir, guardar
y cargar no los repone. El salvage authored conserva su RNG de bootstrap.

El esquema es `MetaState.save_version = 3`; el contenedor con checksum sigue V2.
Se persisten definición inmutable, procedencia, estado físico, conocimiento y
pools. La validación comprueba ámbito/reglas/versión/semilla, posiciones/kinds/hubs,
aristas legítimas recíprocas, aristas ausentes entre extremos presentes e
inventarios sectoriales completos. No compara recursos consumidos con loot
inicial. Los mundos esquema 2 y reglas incompatibles se rechazan mediante
`SaveLoadError`, sin migración ni borrado automático. Se conserva el fallback
existente a backup. Los nuevos errores de incompatibilidad y semilla son EN/ES.

## Comparación reutilizada y decisión

Las [mediciones](../testing/manifest-integration-measurements.json) reutilizan las
diez semillas `0..7,29,271828`, 40 fixtures y 2.010 sectores foco de e1b. Cada
parche regional tiene 64 sectores foco y huella generadora legacy de 120;
el inicial tiene nueve y huella de 25. Son grafos inducidos por propiedad
generadora del foco, no grafos galácticos completos. Los conteos físicos
observados del comparador siguen referidos a esa huella finita; la consulta
inversa completa tiene pruebas separadas.

| Parche | Nodos legacy directo / inverso / productivo | Enlaces intersectoriales directo / inverso / prototipo / productivo | Componentes directo / inverso / prototipo / productivo |
| --- | --- | --- | --- |
| disk | 1040 / 1040 / 1040 | 126 / 133 / 106 / 133 | 438 / 430 / 458 / 431 |
| bulge | 985 / 985 / 985 | 86 / 88 / 81 / 84 | 457 / 455 / 462 / 459 |
| halo | 746 / 747 / 748 | 39 / 41 / 37 / 43 | 420 / 419 / 417 / 411 |
| inicial | 154 / 154 / 154 | 20 / 18 / 13 / 20 | 59 / 61 / 66 / 59 |

Los totales de componentes ECHO iniciales son 51/52/45/51 en ese mismo orden de
modelos. Disk/bulge mantienen población, arquetipos, hubs y enlaces internos.
Halo tiene 11 outliers Z en todos los modelos; los cupos por procedencia dan dos
nodos más que legacy directo (0,27%), tres hubs topológicos más (451→454),
un hub jugable menos (100→99) y nueve aristas internas más (299→308). Fracciones
de cohortes vacías: disk 12,03%, bulge 15,16%, halo 29,38% legacy frente a 29,06%
productivo, inicial 12,22%. Densidades: 1,625/1,539/1,169/1,711 nodos por sector
foco. Estas pequeñas diferencias eliminan la dependencia de entrada ajena.

La política conserva las oportunidades iniciales canónicas y evita la pérdida
sistemática del prototipo. Las diferencias exteriores son +7, -2 y +4 aristas
frente a legacy directo en 640 sectores por región; el aumento halo es 10,3%
sobre una base pequeña de 39 aristas, o 0,625 aristas extra por 100 sectores.
Las rondas fijas sin prioridad inicial daban 15 enlaces iniciales y ECHO 43;
las rondas permutadas por semilla sin prioridad daban disk/bulge/halo/inicial
117/80/38/14 y ECHO 42. Esas alternativas acotadas justifican priorizar el origen,
sin campaña indefinida de ajuste. No se cambiaron probabilidades ni cantidades.
Se aplica la regla de decisión de la orden y se adopta la alternativa mejor
respaldada, sujeta a revisión externa: la muestra no demuestra equivalencia
estadística universal.

En la población procedural foco, legacy directo frente a productivo:
2.885→2.887 nodos, scrap 76.980→77.363 (+0,50%), módulos 3.509→3.518 (+0,26%),
drones 419→456 (+8,83%), suma de radiación 8,2208→8,3801 (+1,94%). En el inicio
por separado, scrap 2.768→3.064 y drones 15→24 en 114 nodos: las tiradas concretas
importan en muestras pequeñas. El JSON contiene totales regionales. Son cambios
aleatorios derivados de semillas estables, no nuevas probabilidades ni garantías.

En este checkout, medianas de consulta generadora de 1/9/64 sectores:
prototipo 2,66/5,99/29,08 ms y productivo 7,37/11,04/37,98 ms; cohortes evaluadas
14/30/151 frente a 29/46/182, máximos trazados de asignación 31,8/49,7/155,2
frente a 52,2/79,9/257,7 KiB. La inversa completa cuesta 4,61/7,23/21,36 ms;
materializar las uniones XY públicas, 19,89/34,00/103,36 ms, con 19/51/197 nodos
totales. Son mediciones locales, no garantías. La política finita añade coste
sobre todo a consultas individuales; no se introduce optimización extra ni caché global.

## Verificación y fases posteriores

Ejecutar desde el repo con el venv canónico y `PYTHONPATH=src`, usando
`python -m tests.worldgen_manifest_integration_smoke` (sustituir `python` por la
ruta absoluta de `AGENTS.md`). Los 14 grupos comparan nodos, recursos,
procedencias, metadatos y aristas completos con órdenes directo/inverso/agrupado,
expansión parcial, guardados repetidos y tres procesos `PYTHONHASHSEED`.
También cubren integridad del estado puro, declaraciones authored, intel con
IDs nuevos, bloques sectoriales, COORD como punto de navegación, colisiones,
cotas numéricas e incompatibilidades. Los testigos y goldens de módulos legacy
se ejecutan contra fixtures congeladas de pruebas, conservando sus aserciones.
La cobertura productiva separada comprueba pools/rangos y agotamiento con acciones reales.

El [informe de revisión](../testing/manifest-integration-review.es.md) y los
[resultados](../testing/manifest-integration-test-results.json) registran la
regresión completa y el inventario de entrega.

Se conservan D18–D20: declaración física distinta de prosa y revelación;
`NODE:`, `LINK:`, `SECTOR:`, `COORD:`, bloques de intel y referencias authored;
regresión authored/arcos/singles/contenido forzoso completa reservada para e4.
Siguen activas las regresiones actuales de objetivos protegidos. No se
implementan reservas de hosts, sustitución de ad hoc, memoria de scan, nuevas
probabilidades de detección, activación de F-DEAD-01, `comms` ni `radiod`.
El planificador anterior sigue puro y condicional donde ya lo era; su integración
con historia certificada sigue en e5. No se declaran completas e3/e4/e5 ni las
guías prácticas de autoría.
