# Informe técnico — RETORNO 4D-3e3

Inglés: [scan-observation-review.md](scan-observation-review.md).
Estado: **implementado y pendiente de revisión externa**. Se detiene el trabajo
con esta entrega, sin `git add`, commit ni push.

## Auditoría, Git y alcance

Rama inicial/final `main`, upstream `origin/main`. SHA inicial/final:
`590a3e87dc0e5f0e472652ce7a6d0b3d55f79bd3`. El árbol inicial estaba limpio, sin trabajo local ajeno pendiente.
`git ls-remote origin refs/heads/main` confirmó el SHA de referencia; el primer
intento falló por DNS del sandbox y el reintento autorizado lo comprobó.
Se revisaron AGENTS, canon v0.3, guía de coherencia, roadmap v1.2, contrato
histórico y referencia de descubrimiento, además de consumidores de scan,
trabajos/eventos, persistencia y pruebas. Principios aplicados: C-WORLD-001,
C-DATA-002, D02/D05/D14/D16 y separación de D21–D24 pendientes de e4.

Estado final: 14 archivos modificados/nuevos de esta fase, sin stage;
`git diff --cached` vacío. `git diff --check` correcto, sin salida.
No se modifica `narrative/amanecer/`, otro contenido narrativo, canon,
configuración de balance, generador/manifiesto ni código de save/load. La
integridad del árbol narrativo se verificó durante empaquetado mediante hashes.

## Implementación y modelo de datos

Se reutiliza el único kernel `_perform_scan`. No se instala otro sistema de scan.
Al terminar toda la detección añade un `ScanObservation` congelado con ID
monotónico `SCAN00001…`, tiempo exacto `ClockState.t` (segundos desde inicio),
posición realmente usada, nodo físico de origen opcional, alcance, estado de
sensores, flags del sensor/servicio, factor y probabilidades near/far vigentes,
IDs detectados y nuevos como tuplas, detecciones por la excepción de recuperación,
resultado, contador RNG y clave interna opcional del trabajo.
Las condiciones son las de ejecución, incluidas variaciones legítimas de radio,
posición o sensores entre encolar y finalizar, no un snapshot de enqueue.

`WorldState.scan_observations` conserva los últimos **128** registros completos,
del más antiguo al más reciente. `next_scan_observation_seq` persiste y no se
reutiliza al podar. IDs y orden se conservan con tiempos iguales, guardados
repetidos y expansión posterior. Retener menos observaciones no olvida contactos,
intel ni pools. Los registros no contienen referencias a nodos o listas mutables.
Un origen retirado puede seguir citado históricamente, sin volver a materializarlo.

La API `scan_observation_history(world)` devuelve una tupla de registros
inmutables, de sólo lectura y sin generación ni cambios de estado. No existe
una superficie pública de historial ya adecuada; se entrega la API solicitada,
sin nuevo comando ni panel. La referencia técnica describe todos los campos.

El trabajo temporizado pasa por ese mismo kernel y guarda
`params['scan_observation_id']`. Marcador y estado terminal evitan reaplicar el
trabajo o consumir más RNG incluso cuando su registro ya salió de las últimas
128 entradas. Dos trabajos distintos simultáneos producen dos observaciones
ordenadas; no son duplicados del mismo barrido.

El helper `_scan_and_discover` mantiene gates y forma de retorno: un barrido
exitoso registra una sola vez. El kernel privado invocado directamente conserva
su semántica anterior sin gates propios, incluido el fallback de factores de
sensores que usan las pruebas; no se amplía el acceso público a scan.

## Resultados negativos, conocimiento y presentación

Se distinguen tres resultados:

| Resultado | Significado |
| --- | --- |
| `no_signals` | Ninguna señal detectada en esa observación/posición/condiciones. No certifica vacío. |
| `known_contacts_only` | Hubo detecciones, todas ya conocidas según el criterio vigente de `known_nodes`; no hubo descubrimientos nuevos. |
| `new_contacts` | Se detectaron contactos nuevos, separados del total observado. |

La salida EN/ES de un negativo dice expresamente que no confirma que el espacio
esté vacío. Sólo conocidos tiene un mensaje diferente. CLI y Textual utilizan
el renderer de eventos existente; las pruebas comparan sus salidas. No cambia
la sintaxis ni se rediseñan paneles. Se actualizan los manuales EN/ES; `help`
sigue describiendo correctamente «realiza escaneo local» y no necesita cambio.
No se añaden eventos de sonido ni cues.

No se guardan candidatos omitidos, inventario secreto del manifiesto, certificados
por sector ni inferencias de ausencia. Un negativo no borra intel ni impide
un descubrimiento posterior. El historial no publica `known_links`. Se preserva
la excepción deliberada de descubrimiento natural por scan para primaries
protegidos: un contacto protegido puede aparecer sólo si la detección real lo
observó, no porque una consulta interna lo enumerara. Consultar memoria o
manifiesto no produce registros ni revelaciones.

Bloqueos, cancelaciones e interrupciones no registran resultados completos.
Si worldgen o la evaluación fallan, el trabajo termina `FAILED`, con motivo
`scan_evaluation_incomplete` y mensaje EN/ES de observación incompleta. No se
convierte la excepción en «sin señales» ni se consume ID de observación.
La llamada directa propaga el error. Pueden permanecer sectores físicos de
materializaciones anteriores correctas; nunca representan evidencia negativa.
No se promete rollback global de excepciones arbitrarias del motor.

No cambian SCAN_TIME_S, probabilidades/factores, radio, gates de sensord,
viaje activo/waypoint detenido, tiradas, contador RNG de scan, entrada de
recuperación, record_intel, distancias finas, rutas ni protección narrativa.
El historial no modifica probabilidades, exige cobertura o impone repeticiones.

## Persistencia

Se conserva **esquema 3** y el contenedor V2 con checksum. El `__setstate__`
existente de WorldState ya aplica defaults para slots añadidos; no necesitó
modificarse el loader. Un save anterior sin los campos nuevos carga historial
vacío y secuencia 1; no se inventan observaciones históricas desde intel.
Los trabajos anteriores todavía encolados pueden completarse y registrar su
primera observación nueva. No hay migración compleja ni borrado.

Además de probar la representación exacta anterior de slots sin los campos,
se creó una partida con una copia limpia del código de `590a3e8` y se cargó
con la implementación nueva: correcto, esquema 3, historial vacío y secuencia 1.
Guardados repetidos conservan orden, IDs, registros, marcadores, contactos y
agotamiento. Nuevos scans tras cargar continúan la secuencia; podar no la reinicia.

## Pruebas ejecutadas

Entorno canónico `/home/jon/prog/retorno_case/retorno_venv/bin/python`,
`PYTHONPATH=src`, ejecutables existentes, sin instalar dependencias.
**32 comprobaciones: 31 correctas, un fallo previo confirmado.** La batería
nueva pasa **20 grupos**, incluidos los 20 casos solicitados y dos trabajos
terminando al mismo tiempo. La equivalencia diferencial usa cinco semillas y
tres estados de sensores: 15 comparaciones exactas contra el kernel congelado
`590a3e8`. Coinciden retornos, estado completo salvo los campos nuevos, distancias
finas, intel y consumo RNG; el RNG global tampoco cambia.

| Prueba | Resultado |
| --- | --- |
| [tests/contacts_sector_smoke.py](../../tests/contacts_sector_smoke.py) | CORRECTO |
| [tests/deadnode_chain_detours_smoke.py](../../tests/deadnode_chain_detours_smoke.py) | CORRECTO |
| [tests/deadnode_chain_planner_smoke.py](../../tests/deadnode_chain_planner_smoke.py) | CORRECTO |
| [tests/deadnode_cooldown_zero_smoke.py](../../tests/deadnode_cooldown_zero_smoke.py) | CORRECTO |
| [tests/deadnode_opportunity_selection_smoke.py](../../tests/deadnode_opportunity_selection_smoke.py) | CORRECTO |
| [tests/exploration_recovery_smoke.py](../../tests/exploration_recovery_smoke.py) | CORRECTO |
| [tests/forced_hidden_ad_hoc_smoke.py](../../tests/forced_hidden_ad_hoc_smoke.py) | CORRECTO |
| [tests/intel_recent_order_smoke.py](../../tests/intel_recent_order_smoke.py) | CORRECTO |
| [tests/known_routes_integrity_smoke.py](../../tests/known_routes_integrity_smoke.py) | CORRECTO |
| [tests/lore_channel_preference_and_unlock_smoke.py](../../tests/lore_channel_preference_and_unlock_smoke.py) | CORRECTO |
| [tests/lore_secondary_count_weights_hard_smoke.py](../../tests/lore_secondary_count_weights_hard_smoke.py) | CORRECTO |
| [tests/lore_smoke.py](../../tests/lore_smoke.py) | CORRECTO |
| [tests/manuals_style_check.py](../../tests/manuals_style_check.py) | CORRECTO |
| [tests/nav_abort_waypoint_cleanup_smoke.py](../../tests/nav_abort_waypoint_cleanup_smoke.py) | CORRECTO |
| [tests/nav_map_galaxy_determinism_smoke.py](../../tests/nav_map_galaxy_determinism_smoke.py) | CORRECTO |
| [tests/nav_map_galaxy_smoke.py](../../tests/nav_map_galaxy_smoke.py) | CORRECTO |
| [tests/procedural_radiation_smoke.py](../../tests/procedural_radiation_smoke.py) | CORRECTO |
| [tests/radiation_hull_smoke.py](../../tests/radiation_hull_smoke.py) | FALLO PREVIO |
| [tests/route_hop_cap_smoke.py](../../tests/route_hop_cap_smoke.py) | CORRECTO |
| [tests/route_solve_out_of_range_origins_smoke.py](../../tests/route_solve_out_of_range_origins_smoke.py) | CORRECTO |
| [tests/save_load_smoke.py](../../tests/save_load_smoke.py) | CORRECTO |
| [tests/scan_job_smoke.py](../../tests/scan_job_smoke.py) | CORRECTO |
| [tests/scan_observation_memory_smoke.py](../../tests/scan_observation_memory_smoke.py) | CORRECTO |
| [tests/sector_intel_validation_smoke.py](../../tests/sector_intel_validation_smoke.py) | CORRECTO |
| [tests/sensor_detection_factor_smoke.py](../../tests/sensor_detection_factor_smoke.py) | CORRECTO |
| [tests/textual_completion_context_smoke.py](../../tests/textual_completion_context_smoke.py) | CORRECTO |
| [tests/uplink_authored_and_failsafe_smoke.py](../../tests/uplink_authored_and_failsafe_smoke.py) | CORRECTO |
| [tests/uplink_once_per_node_smoke.py](../../tests/uplink_once_per_node_smoke.py) | CORRECTO |
| [tests/uplink_only_delivery_retry_smoke.py](../../tests/uplink_only_delivery_retry_smoke.py) | CORRECTO |
| [tests/worldgen_manifest_integration_smoke.py](../../tests/worldgen_manifest_integration_smoke.py) | CORRECTO |
| [tests/worldgen_modules_pool_smoke.py](../../tests/worldgen_modules_pool_smoke.py) | CORRECTO |
| [tests/worldgen_sparse_archetypes_smoke.py](../../tests/worldgen_sparse_archetypes_smoke.py) | CORRECTO |

`radiation_hull_smoke.py` conserva el fallo de línea 183 asociado a CARNAVAL_34:
no aparece el evento esperado. Se reprodujo la misma aserción con una copia
limpia del HEAD inicial, usando el mismo venv. No se modificó código ajeno para
resolverlo y no se identifica como regresión e3.

Se registran también las iteraciones, sin ocultarlas: la primera ejecución de
la prueba nueva falló en el grupo 3 porque la fixture controlada carecía de
frontera informativa; el recovery anterior añadió su entrada de detección
excepcional entre barridos. Se dio a la fixture una fuente real no agotada,
sin cambiar recovery ni probabilidades. Los 20 grupos pasaron después. Se
repitió la batería focalizada tras añadir la comprobación de trabajos simultáneos
y el test de estilo después de actualizar manuales; ambos correctos. Scan,
sensores y save/load también pasaron como primeras comprobaciones y en la
regresión completa. Salidas iniciales, repeticiones y baseline se conservan en
[scan-observation-test-results.json](scan-observation-test-results.json).

## Límites y trabajo posterior

La memoria registra observación, no inventario físico, certeza negativa ni
solución de F-DEAD-01. La retención elimina detalles antiguos sin eliminar
conocimiento; no se ofrece aún un navegador de historial en UI. No introduce
fiabilidad acumulativa, triangulación, simulación bayesiana ni una obligación
de repetir scans. La memoria no es entrada del planificador de recuperación.

Se mantienen materialización lazy, consulta inversa y cotas de e2. El testigo Z
271828 se observa desde su posición real y conserva distinto sector generador
y físico. No se compilan requisitos de historias instaladas: D21–D24 y la
adaptación lore/intel/ad hoc siguen en e4; integración F-DEAD-01, en e5.
No se alteran narrativas, arcos, singles o guías de autoría. No quedó una
incompatibilidad que requiriese ampliar alcance o pedir otra decisión.

## Archivos y ZIP

`retorno-4D-3e3-review.zip`, junto al directorio del repositorio: únicamente
los 14 archivos siguientes, con rutas relativas. Se verificaron lista,
CRC y contenido byte a byte; sin .git, cachés, saves, archivos narrativos ni
inclusión recursiva del ZIP. Documentación técnica y manuales EN/ES sincronizados;
enlaces internos comprobados. Se entrega para revisión externa, sin stage,
commit ni push.

| Archivo | Responsabilidad |
| --- | --- |
| [data/manuals/commands/scan.en.txt](../../data/manuals/commands/scan.en.txt) | Manual scan EN/ES actualizado. |
| [data/manuals/commands/scan.es.txt](../../data/manuals/commands/scan.es.txt) | Manual scan EN/ES actualizado. |
| [docs/README.es.md](../../docs/README.es.md) | Índice EN/ES de la memoria implementada y fases pendientes. |
| [docs/README.md](../../docs/README.md) | Índice EN/ES de la memoria implementada y fases pendientes. |
| [docs/systems/discovery-navigation-intel.es.md](../../docs/systems/discovery-navigation-intel.es.md) | Referencia técnica EN/ES: estructura, semántica, persistencia y compatibilidad. |
| [docs/systems/discovery-navigation-intel.md](../../docs/systems/discovery-navigation-intel.md) | Referencia técnica EN/ES: estructura, semántica, persistencia y compatibilidad. |
| [docs/testing/scan-observation-review.es.md](../../docs/testing/scan-observation-review.es.md) | Informe de revisión y lista de archivos EN/ES. |
| [docs/testing/scan-observation-review.md](../../docs/testing/scan-observation-review.md) | Informe de revisión y lista de archivos EN/ES. |
| [docs/testing/scan-observation-test-results.json](../../docs/testing/scan-observation-test-results.json) | Todas las salidas de 32 comprobaciones, repeticiones y baseline. |
| [src/retorno/cli/repl.py](../../src/retorno/cli/repl.py) | Feedback EN/ES para negativos, sólo conocidos y fallo; renderer compartido con Textual. |
| [src/retorno/core/engine.py](../../src/retorno/core/engine.py) | Registro único al completar detección; marcador idempotente y fallo explícito de evaluación incompleta. |
| [src/retorno/model/world.py](../../src/retorno/model/world.py) | ScanObservation inmutable, ScanOutcome, retención 128, secuencia y API de lectura. |
| [tests/fixtures/scan_590a3e8.py](../../tests/fixtures/scan_590a3e8.py) | Kernel anterior congelado sólo para comparación diferencial de pruebas. |
| [tests/scan_observation_memory_smoke.py](../../tests/scan_observation_memory_smoke.py) | 20 grupos nuevos, flujo real, persistencia, secreto, límites y equivalencia RNG. |
