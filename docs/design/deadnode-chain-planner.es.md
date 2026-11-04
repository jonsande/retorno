# Núcleo de propuestas de cadenas deadnode — Fase 4D-3b

Versión inglesa: [deadnode-chain-planner.md](deadnode-chain-planner.md).

API implementada: `propose_deadnode_chain(state, target_id, PlanningContext())`
en [`core/deadnode_planner.py`](../../src/retorno/core/deadnode_planner.py).
Calcula una propuesta inmutable y sin confirmar. `evaluate_dead_nodes` no la
invoca, no corrige F-DEAD-01 y no cambia estado vivo ni esquema de guardado.
El [contrato de navegación/recuperación](navigation-recovery-contract.es.md)
sigue siendo vinculante.

## Representación y viabilidad

Las dataclasses congeladas `RecoveryProposal`, `Stage`, `ProposedNode`, `Hop`,
`Hint`, `Dependency` y `PlanningContext` sólo contienen valores independientes
y tuplas. Describen identidades de oportunidad/extremos, nodos y saltos ordenados,
posiciones/distancias exactas, región física, sector/arquetipo/cupo, fuentes de
información, funciones, restricciones, preparación y dependencias de capacidad.
`origin_access_path` recoge el camino dirigido ya conocido hasta el origen
elegido; elegirlo no desplaza la nave.

El resultado distingue estas preguntas independientes:

| Campo | Significado |
| --- | --- |
| `geometry_valid` | Un testigo geométrico completo tiene segmentos dentro del cap inclusivo de 45 ly. |
| `physical_chain_valid` | Los extremos existen o tienen tipos propuestos respaldados por cupos procedurales canónicos. No garantiza materialización. |
| `information_status` | `verified` usa mecánicas existentes; `future_required` incluye recepción sin implementar; `unavailable` carece de fuente indispensable elegible. |
| `materialization` | `existing`, `conditional` para inserción propuesta o `unavailable` para colocación/tipo sin resolver. |
| `viability` | `verified`, `conditional`, `incomplete` o `rejected`. Una propuesta verificada sigue sin confirmar. |

`ready_with_existing_mechanics` sólo valora la propuesta. No publica rutas ni
confirma recuperación. Un LINK válido legible ya almacenado puede valorarse sin
inventar otra señal; una primera señal de recuperación nueva siempre depende
de futuros `comms`, `radiod` y captura/importación progresiva.

## Orígenes, búsqueda e información

El llamador gestiona umbrales y cooldown. Los filtros conservan las condiciones
vigentes de contacto/forced-hidden, pool limpio y alcance base de sensores;
no cambian silenciosamente la detección al alcance efectivo de la nave.
Un viaje activo no es origen de planificación; un waypoint detenido sí.
Los orígenes salen de `reachable_known_nodes`, refinado con `reachable_from`
y conocimiento normal de destinos para que aristas obsoletas/inversas o pasos
por nodos desconocidos no habiliten un origen.

Primero se busca una cadena de nodos existentes. La segunda pasada admite
subdivisiones rectas equidistantes entre extremos existentes. Cada conector
usa el mínimo geométrico de segmentos para el cap; no hay máximo arbitrario
de etapas. La búsqueda ordena por nodos nuevos, saltos, distancia e ids completos
ordenados. Las etiquetas conservan reservas de cupos para que dos conectores
no asignen el mismo cupo previsto. Reservas y cachés son locales a la llamada.
Cada segmento se comprueba con `is_hop_within_cap` sobre extremos independientes.

Cada arista necesita un mecanismo informativo. Se consideran, por orden: ruta
dirigida conocida, intel de enlace legítima almacenada/archivo legible no
corrupto de la nave, route solve normal hacia destino conocido dentro del
alcance efectivo, primera señal de recuperación y fuente local disponible.
Estas alternativas no mutan conocimiento. Rutas existentes, intel almacenada
y resolución normal permiten usar un nodo visitado como escala de navegación
sin archivo retroactivo.

La primera señal se captura en la nave aunque el salto parta de otro nodo
alcanzable. Una fuente local posterior obligatoria exige nodo no visitado,
ventana abierta y pool no limpio. Salvage data no reutiliza una fuente de datos
completada; uplink no reutiliza un uplink consumido. Los canales son distintos.
Reservar una pista uplink indispensable nueva es una dependencia explícita de
política futura; no se supone permiso para reescribir un pool de rutas congelado.
Las fuentes nuevas exigen preparación antes de revelar/visitar. Las escalas
de navegación no necesitan fuente ni archivo nuevo. Los gates normales de
hardware/operador siguen como dependencias explícitas; no se concede dron,
energía ni reparación.

## Tipos y contexto procedural

El gate real de interfaces de datos del Engine es más restrictivo que el
predicado genérico de canales de lore. El núcleo registra esta diferencia:

| Tipo | Mecanismos informativos locales posibles |
| --- | --- |
| `relay` | `salvage_data`, `uplink` |
| `station` | `salvage_data`, `uplink` |
| `waystation` | `uplink`; Engine rechaza `SalvageData` aquí |
| `derelict` | `salvage_data` |
| `ship` | `salvage_data` |

Los tipos nuevos proceden de las consultas puras existentes `_select_archetype`
y `_plan_sector_kinds`, usando plantillas/pesos regionales y de arquetipo,
caps por tipo, prohibiciones, conteos físicos actuales y orden determinista de
cupos. No se introducen pesos de aparición, tirada de hub adicional ni reparto
estético de tipos. Los nodos existentes adecuados se reutilizan con independencia
del tipo elegido para un cupo nuevo. Una política regional desconocida o falta
de cupo produce un testigo incompleto con `kind=None`, no un tipo válido inventado.

Con seed `271828`, `A=(0,25,1)` y `D=(100,25,1)`, los cupos en
`S+003_+002_+000` / `S+006_+002_+000` admiten una cadena `relay` / `station`
de tres saltos de unos 33,33 ly. Un destino a 70 ly necesita un intermediario;
40 y exactamente 45 ly no necesitan ninguno. Otras fixtures de la misma seed
seleccionan `ship` y `derelict`. En `y=1`, los sectores de la subdivisión de
100 ly carecen de cupos: se informa de incompletitud sin cambiar worldgen.

## Límites y decisiones pendientes

Las coordenadas equidistantes propuestas no se anuncian como las coordenadas
muestreadas por worldgen. Prever tipo/cupo establece un contexto respaldado,
no permiso para sobrescribir generación. Cada nodo nuevo registra por tanto
inserción de coordenadas, registro atómico/idempotente, preparación de pool y
reserva lazy de cupo o topología de sector cerrado todavía sin resolver.
Un guardrail inicial sin ejecutar añade otra dependencia explícita de contexto.
No se genera ni reconstruye ningún sector, gasta presupuesto, ni añade enlace
físico o ruta conocida.

Los ids propuestos usan un digest estable de seed, contexto de oportunidad y
del nodo; resolver colisiones localmente no asigna ids del juego. Esto no hace
idempotente una confirmación futura. Confirmar deberá revalidar el estado,
reservar cupos/identidades, preparar fuentes atómicamente y después confirmar
y entregar por etapas. Intentos/cooldowns, persistencia de planes activos,
comunicaciones y colas de recepción quedan fuera de esta fase.

La protección reutiliza `_locked_primary_targets` para primaries NODE/LINK y
excluye objetivos finales e intermediarios. Los formatos bloqueados sin resolver
fallan de forma conservadora con `primary_protection_query_incomplete`; no se
introduce progresión narrativa nueva. Un host narrativo forced-hidden no está
protegido automáticamente. Scan natural y resolución manual no cambian.

La búsqueda sólo es completa dentro de su familia de conectores/cupos, no sobre
coordenadas arbitrarias, desvíos regionales o toda asignación procedural posible.
Agotar la búsqueda devuelve `incomplete`, sin afirmar que el universo carezca
de solución.

## Verificación

[`deadnode_chain_planner_smoke.py`](../../tests/deadnode_chain_planner_smoke.py)
cubre 40/cap/70/100 ly, reutilización 35+35+30 ly, cadenas mixtas, orígenes
alternativos dirigidos, aristas obsoletas, tipos canónicos diversos y rechazo
por capacidad, receptores consumidos, escalas visitadas sin información nueva,
intel legible, protección NODE/LINK, formatos de protección no soportados,
contextos lazy/cerrados, colisiones, doce saltos, waypoints detenidos y negativos.
Cada fixture compara el estado completo serializado y RNG global antes/después
de llamadas repetidas. Reordenar contenedores y tres ciclos temporales save/load
reproducen las propuestas. No se invoca escritor, registrador ni generador
productivo.
