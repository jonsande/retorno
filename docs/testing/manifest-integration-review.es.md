# Informe de revisión — RETORNO 4D-3e2

Inglés: [manifest-integration-review.md](manifest-integration-review.md).
Entrega implementada, **pendiente de revisión externa**. No se ha hecho stage,
commit ni push. No se solicita ninguna decisión adicional para presentar esta
implementación; la política se ha elegido conforme a la regla de la orden.

## Git y alcance

Rama inicial/final: `main`. SHA inicial/final:
`5cdde2804c74b7cf14d01120db84b097eb8e7b23`. `git ls-remote origin refs/heads/main`
confirmó ese mismo SHA durante la auditoría inicial, tras reintentar con permiso
por el fallo DNS del sandbox. No se presupone que el remoto permanezca inmutable.
El árbol inicial tenía trabajo ajeno sin seguimiento en `narrative/`. No se ha
editado ni empaquetado ese árbol. El estado final contiene los 40 archivos
de esta entrega modificados/nuevos sin stage y mantiene `?? narrative/` aparte.
`git diff --cached` está vacío. `git diff --check`: **correcto, sin salida**.
Canon v0.3, guía de coherencia, hoja de ruta v1.1 D01–D20 y contratos pertinentes
revisados. No se modifica canon, datos físicos activos, balance ni contenido narrativo.

## Resultado y decisiones

Worldgen productivo usa `historical-world-v1` y una definición inmutable. Identidad,
posición, kind, hubs, recursos iniciales y aristas no dependen del orden de
materialización. El runtime mantiene su API lazy y los límites técnicos explícitos;
consultar o materializar no descubre ni publica rutas. Sólo hay un núcleo productivo.

Se conserva la base authored y el cupo histórico de UNKNOWN; no se resucita su
marcador retirado. ECHO_7 procede de su declaración, RETORNO_SHIP sigue especial.
La consulta física inversa completa conserva Z sin truncar; la demostración para
CPython 3.12 binary64 y el dominio de índices figura en el
[contrato técnico](../design/historical-worldgen-integration.es.md).
Fuera del dominio o presupuesto hay error, no una afirmación de vacío.

Se adopta prioridad fija del 3×3 inicial seguida de ocho emparejamientos por
paridad. Se respetan tiradas, cupos y cap de 45 ly. Es una política distinta del
legacy dependiente del orden y del top-k mutuo experimental; las diferencias se
cuantifican abajo. No se ajustan probabilidades ni cantidades para compensarlas.
Las claves de recursos usan identidad completa: cambian resultados concretos,
no parámetros de balance. Esas decisiones están aplicadas y quedan revisables.

Saves esquema 3 fijan definición/procedencia, preservan agotamiento y conocimiento
y rechazan esquema 2, semilla/reglas/versiones o estado histórico incompatible.
No hay migraciones ni borrado automático. Se conserva fallback a backup.
La adaptación mínima de IDs se limita a resolver NODE/LINK exactos hacia su sector
físico; las cuatro líneas Textual sólo impiden corromper un universo fijado con
`debug seed`, mediante el mismo guard EN/ES de CLI. No hay rediseño de interfaz.

## Comparación y coste

Mismo comparador de e1b: diez semillas, 40 fixtures, 2.010 sectores foco.
[Datos completos](manifest-integration-measurements.json).

| Región | Enlaces legacy directo / inverso / prototipo / productivo | Nodos legacy directo / productivo |
| --- | --- | --- |
| disk | 126 / 133 / 106 / 133 | 1040 / 1040 |
| bulge | 86 / 88 / 81 / 84 | 985 / 985 |
| halo | 39 / 41 / 37 / 43 | 746 / 748 |
| inicio | 20 / 18 / 13 / 20 | 154 / 154 |

Componentes iniciales: 59/61/66/59; nodos en componentes ECHO: 51/52/45/51.
Halo conserva 11 outliers Z; la diferencia de dos nodos (+0,27%) elimina la
ocupación de cupos por entrada física ajena. Halo añade cuatro enlaces frente a
legacy directo (+10,3% de su pequeña base; +0,625 por 100 sectores), sin garantía
de progreso. La comparación no demuestra equivalencia universal de distribuciones.

Totales de recursos procedural foco: scrap 76.980→77.363, módulos 3.509→3.518,
drones 419→456, radiación agregada 8,2208→8,3801. Inicio por separado:
scrap 2.768→3.064 y drones 15→24 en 114 nodos. Son tiradas nuevas por identidad,
sin cambiar funciones ni parámetros probabilísticos; no se oculta esa variación.

Consulta generadora 1/9/64 sectores, mediana local prototipo→productivo:
2,66→7,37 / 5,99→11,04 / 29,08→37,98 ms. Inversa física:
4,61 / 7,23 / 21,36 ms. Materialización pública de sus uniones:
19,89 / 34,00 / 103,36 ms. El contrato incluye cohortes y memoria medidas.
El mayor coste absoluto individual sigue acotado; no se abrió otra optimización.

## Pruebas y fallos

Venv canónico: `/home/jon/prog/retorno_case/retorno_venv/bin/python`,
`PYTHONPATH=src`. Se ejecutaron 61 scripts/grupos smoke y estilo: resultado final
**60 correctos y un fallo previo confirmado**, más comparador correcto.
Los tres módulos sin main se ejecutaron llamando sus siete funciones test;
no se cuentan importaciones vacías como cobertura. `pytest` no está instalado
en este venv: el intento de invocarlo falló y se usaron los ejecutables existentes,
sin instalar dependencias.

La integración nueva pasa **14 grupos**, con semillas 2, 29 y 271828, estados
completos directo/inverso/agrupado, tres procesos hash-seed, expansión parcial,
guardados repetidos, consumo de recursos/pools, authored sin revelación, ID nuevo,
formatos de intel, COORD, límites/atomicidad, colisiones e incompatibilidades.
Pasan las regresiones actuales de scan, route solve, uplink, lore/pools, objetivos
protegidos, deadnodes, bootstrap, rutas/distancias y save/load. Prototipo 17 grupos,
catálogo histórico 17 y testigos legacy 9 también pasan.

El primer pase tuvo cuatro fallos: dos fixtures se adaptaron sin modificar sus
aserciones (declaración distante de UNKNOWN y marcador sintético de navegación).
`textual_theme_smoke.py` falló bajo concurrencia por `NoMatches('#header')` y pasó
al repetir aislado; también pasó el baseline aislado. No se oculta el fallo inicial
ni se afirma haber corregido esa carrera UI ajena al alcance.
`radiation_hull_smoke.py` sigue fallando en línea 183: espera un evento de radiación
al cambiar a `CARNAVAL_34`, ausente del contenido activo. La misma aserción falla
al ejecutar una copia limpia de `5cdde28` con el mismo venv.
No se arregló ese defecto ajeno. No queda ningún fallo de integración e2 conocido.

[Resultados y salidas](manifest-integration-test-results.json) conserva pase
inicial, repeticiones justificadas y comprobaciones baseline. Los golden rolls
legacy se mantienen en fixture congelada; la prueba productiva de módulo recupera
`field_service_rig` al segundo intento y conserva cargo/agotamiento. No se cambian
aserciones legacy simplemente para aceptar IDs o loot nuevos.

## Documentación, garantías y límites

Referencias de worldgen reescritas para el runtime vigente en EN/ES; contrato de
integración nuevo con identidad, authored, inversa/demostración, política,
materialización, persistencia, comparaciones y costes. Referencias e1/e1b quedan
marcadas como evidencia histórica; índices y nota de compatibilidad navegación
sincronizados. Manual debug actualizado EN/ES; el listado help no describe la
semilla y no necesitaba modificar su sintaxis o descripciones. Mensajes nuevos
incompatibilidad/guard de semilla disponibles EN/ES. Manual style check correcto.

Se conservan expresamente D18–D20 y todos los formatos públicos. No se declara
completa e4 ni se reescriben sus guías prácticas. No hay memoria acumulada scan,
nuevas probabilidades, reservas de hosts, sustitución definitiva de ad hoc,
activación del planificador F-DEAD-01, comms/radiod, nueva estación, sonido ni
cambios generales de balance. e3/e4/e5 siguen pendientes. El planificador existente
no recibe certificación retroactiva de sus propuestas condicionales.

Garantías demostradas para la definición y dominio soportados; no se prometen
conectividad universal, igualdad con todos los legacy incompatibles entre sí,
igualdad exacta de loot anterior, soporte de otros kernels ni equivalencia
estadística global a partir de esta muestra. Los marcadores antiguos/sintéticos
sin `physical_inventory_complete` no certifican inventario histórico completo.

## Archivos y paquete

ZIP: `retorno-4D-3e2-review.zip`, junto al directorio del repositorio. Contiene
exclusivamente los 40 archivos listados, con rutas relativas al repo;
no incluye narrative, saves reales, cachés, .git ni este ZIP dentro de sí mismo.
Se comprobó lista, contenido byte a byte y CRC. Se detiene el trabajo para
revisión externa, sin stage/commit/push.

| Archivo | Responsabilidad |
| --- | --- |
| [data/manuals/commands/debug.en.txt](../../data/manuals/commands/debug.en.txt) | Manual debug EN/ES: cuándo puede cambiarse la semilla. |
| [data/manuals/commands/debug.es.txt](../../data/manuals/commands/debug.es.txt) | Manual debug EN/ES: cuándo puede cambiarse la semilla. |
| [docs/README.es.md](../../docs/README.es.md) | Índice EN/ES y estado de las fases. |
| [docs/README.md](../../docs/README.md) | Índice EN/ES y estado de las fases. |
| [docs/design/historical-worldgen-integration.es.md](../../docs/design/historical-worldgen-integration.es.md) | Contrato técnico EN/ES, prueba numérica, decisiones y comparación. |
| [docs/design/historical-worldgen-integration.md](../../docs/design/historical-worldgen-integration.md) | Contrato técnico EN/ES, prueba numérica, decisiones y comparación. |
| [docs/design/procedural-preexistence.es.md](../../docs/design/procedural-preexistence.es.md) | Identifica evidencia histórica e1/e1b y enlaza el contrato vigente. |
| [docs/design/procedural-preexistence.md](../../docs/design/procedural-preexistence.md) | Identifica evidencia histórica e1/e1b y enlaza el contrato vigente. |
| [docs/design/stable-procedural-manifest.es.md](../../docs/design/stable-procedural-manifest.es.md) | Identifica evidencia histórica e1/e1b y enlaza el contrato vigente. |
| [docs/design/stable-procedural-manifest.md](../../docs/design/stable-procedural-manifest.md) | Identifica evidencia histórica e1/e1b y enlaza el contrato vigente. |
| [docs/systems/discovery-navigation-intel.es.md](../../docs/systems/discovery-navigation-intel.es.md) | Nota EN/ES de compatibilidad de IDs y acuerdos D18–D20. |
| [docs/systems/discovery-navigation-intel.md](../../docs/systems/discovery-navigation-intel.md) | Nota EN/ES de compatibilidad de IDs y acuerdos D18–D20. |
| [docs/systems/world-generation.es.md](../../docs/systems/world-generation.es.md) | Referencia canónica EN/ES actualizada al runtime estable. |
| [docs/systems/world-generation.md](../../docs/systems/world-generation.md) | Referencia canónica EN/ES actualizada al runtime estable. |
| [docs/testing/manifest-integration-measurements.json](../../docs/testing/manifest-integration-measurements.json) | 40 fixtures, agregados de cuatro modelos, recursos y benchmarks. |
| [docs/testing/manifest-integration-review.es.md](../../docs/testing/manifest-integration-review.es.md) | Informe de entrega y lista completa de archivos (EN/ES). |
| [docs/testing/manifest-integration-review.md](../../docs/testing/manifest-integration-review.md) | Informe de entrega y lista completa de archivos (EN/ES). |
| [docs/testing/manifest-integration-test-results.json](../../docs/testing/manifest-integration-test-results.json) | Resultados iniciales, repeticiones justificadas y comprobaciones baseline. |
| [src/retorno/bootstrap.py](../../src/retorno/bootstrap.py) | Captura de reglas físicas al iniciar; base authored intacta. |
| [src/retorno/cli/repl.py](../../src/retorno/cli/repl.py) | Resolución física de IDs nuevos; bloqueo de cambio de semilla fijada. |
| [src/retorno/core/gamestate.py](../../src/retorno/core/gamestate.py) | Esquema de guardado 3. |
| [src/retorno/io/save_load.py](../../src/retorno/io/save_load.py) | Persistencia/validación y rechazo EN/ES de incompatibilidades. |
| [src/retorno/model/world.py](../../src/retorno/model/world.py) | Versión, definición y procedencia; inventarios físicos/cohortes. |
| [src/retorno/ui_textual/app.py](../../src/retorno/ui_textual/app.py) | Mismo guard de semilla: cuatro líneas de compatibilidad, sin rediseño de UI. |
| [src/retorno/worldgen/catalog.py](../../src/retorno/worldgen/catalog.py) | Evidencia histórica sin promover muestras condicionales. |
| [src/retorno/worldgen/generator.py](../../src/retorno/worldgen/generator.py) | Materialización productiva estable, recursos y validación de universo. |
| [src/retorno/worldgen/manifest.py](../../src/retorno/worldgen/manifest.py) | Núcleo histórico puro, identidad, consultas generadoras e inversa física. |
| [src/retorno/worldgen/manifest_prototype.py](../../src/retorno/worldgen/manifest_prototype.py) | Entrada compatible al núcleo compartido con política experimental. |
| [src/retorno/worldgen/topology.py](../../src/retorno/worldgen/topology.py) | Prioridad inicial fija y ocho rondas de emparejamiento acotadas. |
| [tests/fixtures/worldgen_catalog_5cdde28.py](../../tests/fixtures/worldgen_catalog_5cdde28.py) | Catálogo condicional legacy aislado para evidencia histórica. |
| [tests/fixtures/worldgen_legacy_5cdde28.py](../../tests/fixtures/worldgen_legacy_5cdde28.py) | Copia byte a byte del generador HEAD para conservar testigos; sólo pruebas. |
| [tests/known_routes_integrity_smoke.py](../../tests/known_routes_integrity_smoke.py) | Definición fijada antes del snapshot de la fixture de persistencia. |
| [tests/lore_secondary_count_weights_hard_smoke.py](../../tests/lore_secondary_count_weights_hard_smoke.py) | Declara UNKNOWN distante antes de bootstrap en vez de moverlo después. |
| [tests/nav_abort_waypoint_cleanup_smoke.py](../../tests/nav_abort_waypoint_cleanup_smoke.py) | Fixture de navegación fija definición y no afirma completitud histórica ficticia. |
| [tests/worldgen_manifest_comparison.py](../../tests/worldgen_manifest_comparison.py) | Comparador e1b reutilizado con modelo productivo, recursos y costes. |
| [tests/worldgen_manifest_integration_smoke.py](../../tests/worldgen_manifest_integration_smoke.py) | 14 grupos nuevos de integración y límites numéricos. |
| [tests/worldgen_manifest_prototype_smoke.py](../../tests/worldgen_manifest_prototype_smoke.py) | 17 grupos del prototipo con kernel compartido y referencia legacy explícita. |
| [tests/worldgen_modules_pool_smoke.py](../../tests/worldgen_modules_pool_smoke.py) | Goldens legacy separados; perfiles, acciones y agotamiento productivos. |
| [tests/worldgen_preexistence_catalog_smoke.py](../../tests/worldgen_preexistence_catalog_smoke.py) | Aserciones del contrato legacy contra fixture congelada. |
| [tests/worldgen_preexistence_characterization_smoke.py](../../tests/worldgen_preexistence_characterization_smoke.py) | Testigos originales contra generador/catálogo legacy congelados. |
