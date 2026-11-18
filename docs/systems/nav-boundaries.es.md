# Límites temporales de navegación (NAV-BRAKE-01B1 a 01B3C)

Esta API técnica está implementada en `src/retorno/core/nav_boundaries.py` y
`src/retorno/core/nav_coordinator.py`, y probada por sus archivos de prueba.
No está conectada a la navegación
jugable. `Engine.tick()`, viaje, aborto, relojes, combustible y guardado siguen
con su comportamiento anterior.

## Tasa de desgaste compartida

`ordinary_wear_rate(system, power_quality, brownout_sustained, internal_rad,
in_transit=..., op_mode=..., god_active=...)` devuelve la pérdida de integridad
**por segundo propio de la nave** bajo las condiciones fijas indicadas.
`Engine._apply_degradation` utiliza esa misma función y conserva su clamp,
eventos de estado, orden y salida temprana en god mode. Los factores son el
deterioro base, el déficit de calidad eléctrica, la radiación interna acotada,
el multiplicador de tránsito NORMAL y los multiplicadores de brownout sostenido
existentes para `energy_distribution` y `power_core`. La función no integra
condiciones variables.

## Empuje y umbral de integridad

`thrust_available(ship)` delega en la clasificación **actual de empuje normal**
de `ShipState.engine_operating_state()`. No clasifica la futura capacidad de
frenado de emergencia. No evalúa velocidad objetivo, velocidad física,
combustible ni un umbral nuevo de calidad eléctrica. El aislamiento usa el
contrato existente `forced_offline`.

`predict_engine_health_limit(ship, wear_rate_per_proper_s, god_active=...)`
devuelve un `TemporalLimit` inmutable para la llegada matemática a
`Balance.SYSTEM_HEALTH_CRITICAL`. Su dominio es `proper`. En la igualdad
exacta el motor sigue DAMAGED porque producción clasifica CRITICAL con `<`.
Por tanto, `time_s=0` significa *umbral alcanzado*, no incapacidad para frenar.
Una tasa positiva produce la clasificación CRITICAL actual inmediatamente
después; el futuro frenado de emergencia aún puede estar disponible. Tasa nula, god mode
o integridad ya inferior al umbral no producen un cruce futuro; `validity`
explica el caso. El aislamiento no borra un umbral de salud calculable aparte.

El tiempo predicho es exacto solo mientras la tasa facilitada y todas sus
entradas permanezcan constantes. Un cambio de calidad eléctrica, brownout,
radiación, modo, deterioro base, reparación o aislamiento invalida la
predicción. El consumidor debe volver a medir el estado y calcularla de nuevo.

## Candidatos de trabajos

`propulsion_job_limits(jobs)` devuelve `TemporalLimit` inmutables en el orden
de trabajos activos del scheduler, con `domain="galactic"`. Incluye
reparaciones de motores, núcleo eléctrico y distribución, cambios de módulos
relevantes y trabajos cuyo consumo eléctrico puede cambiar las condiciones al
terminar. `engine_speed_upgrade_01` cambia el techo físico de velocidad;
`bus_stabilizer`, `aux_battery_cell` y `micro_reactor_patch` cambian calidad,
capacidad o generación eléctrica y pueden cambiar el desgaste. No se presupone
que cualquier otra instalación modifique directamente el empuje.

Para un trabajo RUNNING, `time_s` es su ETA actual **condicionado a que siga
ejecutándose**. Ni la finalización, ni el éxito de una reparación, ni la
estabilidad de las condiciones están garantizados; `uncertainty_reason` lo
indica. Un trabajo QUEUED elegible tiene una comprobación `job_activation` en
tiempo cero, nunca una ETA de finalización. Un trabajo en cola bloqueado por
otro trabajo del mismo responsable o por cálculo de ruta, o un trabajo RUNNING
pendiente de confirmación, tiene `time_s=None`. Un trabajo QUEUED pendiente de
confirmación aún puede activarse y cambiar la carga en tiempo cero. El scheduler productivo todavía puede
rechazar el inicio por otras causas. Se omiten trabajos sin relación y sin
consumo eléctrico. El inicio, interrupción, parada o cambio de consumo de un
trabajo invalida la instantánea. El consumidor puede usar las ETA candidatas
como cortes, pero debe dejar que el scheduler productivo decida el resultado
una sola vez. La
predicción no aplica reparaciones ni consume RNG.

La API no predice regulación eléctrica futura, desgaste con tasa variable,
resultados aleatorios ni cuándo empezará un trabajo en cola bloqueado.

## Coordinador puro (01B2)

`select_next_boundary(plan, elapsed_galactic_s, horizon_galactic_s, *,
health_limit=None, job_limits=(), invalidation_reasons=(),
seen_zero_selections=())` devuelve un `BoundarySelection` inmutable.
`plan` puede ser el `TravelPlan` original o el `MotionSegment` **activo**.
Para un plan, `elapsed_galactic_s` y `at_galactic_s` son segundos desde la
salida. Para un segmento, son segundos absolutos del reloj galáctico acumulado;
la consulta debe caer dentro de ese segmento. `horizon_galactic_s`,
`advance_galactic_s` y cada `TemporalLimit.time_s` son segundos restantes desde
la consulta. `accumulated_proper_s` es el tiempo propio acumulado desde la
salida. `causes` contiene valores `BoundaryCause` inmutables con el límite
condicional original y su instante galáctico convertido. `deferred` conserva
los límites relevantes sin instante calculable. `requires_reevaluation` marca
cortes por fase, integridad, trabajos o invalidación.

Para un plan nominal, el selector considera fin de aceleración, inicio de
frenado y fin del perfil. Para un segmento activo considera **solo el fin de
ese segmento**, nunca las fases ni la llegada del plan invalidado. Ambos
consideran el horizonte solicitado, un umbral de integridad suministrado, finalizaciones candidatas de
trabajos RUNNING, comprobaciones de activación QUEUED e invalidaciones
explícitas. Nunca ejecuta sus efectos. Si el horizonte pasa de la llegada,
corta primero el perfil. Una invalidación obliga a cortar en cero y descarta
las predicciones temporizadas obsoletas hasta recibir una instantánea nueva.
El selector es determinista y no modifica el plan ni el estado del juego.

`galactic_time_at_proper(plan, accumulated_proper_s)` en `nav_physics.py`
invierte la trayectoria de `sample_travel`: seno hiperbólico en aceleración,
gamma de beta máxima constante solo en crucero y aceleración invertida en
frenado. Los extremos exactos de fase se toman del plan. No hay resolución por
pasos fijos ni aproximación de beta fija durante aceleración o frenado. Puede
haber redondeo de coma flotante cerca de los extremos. Para un segmento,
`proper_time_in_segment()` obtiene el tiempo propio local sin restar relojes
acumulados grandes y `galactic_time_at_segment_proper()` invierte analíticamente
la duración propia restante. El `accumulated_proper_s` devuelto sigue siendo el
reloj propio acumulado de la nave.

El instante más temprano es el corte. Se conservan las causas a cuatro ULP o
menos de ese instante, cada una con su propio `at_galactic_s`; las causas
ligeramente posteriores **no** vencen en el corte anterior y deben comprobarse
de nuevo. Un límite en el instante actual produce duración cero. El consumidor
debe resolverlo, recalcularlo o detenerse; repetir la misma instantánea no es
progresar. No se añade un épsilon temporal positivo. La integridad del motor
igual al umbral todavía es DAMAGED; con desgaste positivo continuo pasa a
CRITICAL inmediatamente a la derecha según el clasificador actual. Una reparación completada en la
igualdad puede cambiar ese estado posterior, pero el coordinador no presupone
su éxito.
`seen_zero_selections` permite entregar los cortes cero ya resueltos en ese
instante. Repetir las mismas causas vencidas produce `TemporalResolutionError`,
aunque cambie el horizonte solicitado; la colección solo se limpia tras
avanzar el tiempo. Un horizonte positivo, ETA de trabajo o límite propio que
no pueda avanzar el reloj de coma flotante produce el mismo error controlado.
El selector no redondea un instante causal hacia delante para fabricar progreso.

## Contrato de integración causal

Al inicio de cada intervalo, resolver las comprobaciones de activación QUEUED
e identificar carga eléctrica, calidad, radiación, tasa de desgaste, estado de
propulsión y ETA efectivas. Seleccionar un corte. Integrar movimiento físico y
efectos del intervalo con el estado **anterior al corte**, incluida regulación
eléctrica y desgaste; avanzar contadores de trabajos RUNNING sin aplicar antes
sus efectos de finalización. En el corte, clasificar la integridad resultante
con el umbral estricto `<`, y después procesar interrupción, fallo y
finalización de trabajos en el orden del scheduler, aplicando reparaciones y
módulos con éxito una sola vez. Por último, recalcular electricidad, desgaste,
empuje y trayectoria antes de consumir tiempo restante. Deben considerarse
todos los trabajos y cambios de fase del mismo instante. NAV-BRAKE-01B3D separa
avance de contadores y efectos de finalización en el scheduler productivo.
El `_tick_interval()` histórico aún llama a `_process_jobs()` antes de
`_apply_degradation()`; dividir `Engine.tick()` sin más no corrige ese orden.

01B2 no modela la regulación eléctrica cambiante, inicio de brownout,
radiación, interrupciones imprevistas, resultados aleatorios ni acciones
externas dentro del intervalo. Estos cambios invalidan los límites recibidos
y requieren un corte nuevo. Las pruebas matemáticas no demuestran invariancia
operativa general al subdividir intervalos.

01B3A añade [segmentos físicos](nav-physics.es.md); 01B3B selecciona sobre el
segmento activo sin recorrer su historial. Tras consolidar un tramo, su estado
final y el segmento activo bastan para la siguiente selección; el historial
completo es opcional para diagnóstico, mientras que relojes acumulados,
posición/velocidad físicas, maniobra activa, destino pretendido y cortes
pendientes necesitarán persistencia más adelante.

### Política operativa futura aprobada (no implementada aquí)

Con integridad de motores **igual o superior al 35 %** se conservan aceleración
y frenado normales, con inicio preventivo del frenado de seguridad en el límite
del 35 %. Desde **15 % inclusive hasta menos del 35 %** solo queda frenado de
emergencia. Por debajo del **15 %**, o con motores aislados de manera efectiva,
el movimiento es inercial. NAV-BRAKE-01B3C añade
`Balance.ENGINE_EMERGENCY_BRAKE_MIN_HEALTH`, `acceleration_available(ship)`,
`braking_available(ship)` y `predict_engine_braking_limit(ship, rate)`.
El 15 % es inclusivo: el frenado sigue disponible en la igualdad; el desgaste
positivo lo elimina inmediatamente después. El predictor del 35 % y el
clasificador existente con comparaciones estrictas no cambian.
`thrust_available()` conserva su significado anterior de empuje normal.
Estas consultas no autorizan consumo de combustible ni valoran la viabilidad
de una maniobra.

El frenado de emergencia puede sobrepasar el destino cuando resulta imposible
detenerse antes; cruzar la coordenada con velocidad positiva no es una llegada
satisfactoria. Tras reparar, el replanteo parte de la posición y velocidad
reales, conserva el destino cuando sea posible y nunca vuelve a acelerar si
ya se estaba frenando antes de la avería. Fases posteriores deberán añadir
advertencias por terminal y correo interno durante la hibernación, waypoint en
la posición física de detención incluso más allá del destino, bloqueo de nuevas
salidas y `route solve` durante tránsito físico, límite operativo actual de
45 años luz para conexiones desde waypoints, un modelo de colisiones futuro
documentado y comprobaciones de reserva de combustible para cada maniobra
propulsiva adicional. Nada de ello está activo en 01B3C.

## Estado de la integración causal en 01B3C

El adaptador propulsivo de `Engine.tick()` está **bloqueado**. El campo opcional
`ShipState.physical_transit` contiene `PhysicalTransitState`: su
`MotionSegment` activo y tiempo transcurrido determinan por sí solos la
posición, velocidad y tiempo propio locales. También conserva destino original,
intención, marcas de frenado de seguridad e inicio del frenado y necesidad de
replanteo. Los guardados antiguos se leen con este campo a `None`. Ningún viaje
público lo crea. Si está presente, `Engine.tick()` lanza una excepción antes de
modificar el estado, impidiendo que una maniobra física sin implementar avance
silenciosamente.

El bloqueo es causal. `Engine._process_jobs()` aplica una reparación finalizada
antes de `Engine._apply_degradation()` para el intervalo, de modo que la
reparación puede afectar al desgaste anterior. `Engine._integrate_power_interval()`
modifica batería, calidad, desconexiones y contadores de brownout, pero el
desgaste utiliza una sola muestra de calidad y radiación al final. Por ello un
umbral predicho con la tasa inicial puede alcanzarse antes con condiciones
cambiantes. Esos efectos todavía no se cortan en los mismos instantes que un
`MotionSegment` con β variable. Los ticks arbitrariamente pequeños no aportan
un instante exacto de fallo ni una cota de error verificada.

El adaptador aún necesita límites eléctricos y radiológicos o una cota
verificada del error de
integración continua; desgaste anterior a reparaciones simultáneas; tratamiento
exacto de cortes cero del 35 % y 15 %; y reserva de combustible verificada para
cada tramo propulsivo. Solo entonces podrá sustituirse el cálculo del reloj con
β fija por la integral de tiempo propio del segmento en la vía interna. El
viaje público antiguo sigue siendo la única vía que avanza en esta fase.

## Fases del scheduler en 01B3D

`Engine._begin_job_interval(state)` utiliza las comprobaciones productivas de
activación, exclusividad por responsable, cálculo de rutas, reserva de dron e
interrupción en el instante actual. Devuelve un `_JobInterval` de un solo uso y
eventos. La lista congelada contiene los trabajos autorizados a avanzar durante
el intervalo. El `_compute_load_kw` ordinario cuenta todos los trabajos marcados
RUNNING, incluso los pausados por confirmación y excluidos de esa lista; esta
regla histórica de carga no cambia. Un QUEUED bloqueado no añade carga.

`_next_job_completion_s(state, interval)` devuelve la ETA en avance más próxima
en **segundos galácticos**, incluido cero, sin modificar estado ni RNG. Incluye
trabajos ajenos a propulsión porque pueden liberar a un responsable para
trabajos en cola relevantes. Es un candidato: una interrupción o un fallo
aleatorio puede impedir la finalización. El `nav_coordinator.py` puro no ejecuta
el scheduler; un futuro adaptador del motor deberá suministrarle ese límite
junto con el segmento físico y los otros límites.

`_advance_job_timers(state, interval, dt)` solo descuenta ETA, rechaza un
intervalo que sobrepase una finalización y no aplica efectos. El futuro
consumidor debe integrar primero el intervalo físico, eléctrico y de desgaste
precedente y situar el reloj galáctico del juego en el límite. Después,
`_resolve_job_interval(state, interval)` vuelve a comprobar interrupciones,
ejecuta las reglas existentes de riesgo de emergencia y resultado de reparación
en orden del scheduler, aplica cada efecto vencido mediante el único
`_apply_job_effect()` productivo y devuelve eventos. Resolver dos veces el
token produce un error. Una nueva llamada a `_begin_job_interval` en el mismo
instante puede arrancar trabajos QUEUED recién desbloqueados, incluso con ETA
cero, sin avance artificial del reloj. El consumidor debe registrar los eventos
y no reutilizar un token tras cambios ajenos del estado.

`_process_jobs()` usa las mismas operaciones trabajo por trabajo, conservando
el orden público anterior y su posición previa al desgaste. En lotes causales
los efectos de finalización pueden seguir al desgaste, por lo que una reparación
en T no afecta al intervalo precedente. La probabilidad de fallo de emergencia
sigue dependiendo del `dt` suministrado; la subdivisión puede cambiar resultados
estocásticos y el instante de RNG. No se afirma invariancia estocástica ni se
modificó ningún parámetro probabilístico. Regulación eléctrica, radiación,
predicción de desgaste y movimiento propulsivo siguen fuera de esta
refactorización. `Engine.tick()` continúa rechazando el tránsito físico.

## 01B3E: electricidad condicional y desgaste integrado

`nav_electricity.py` captura un `PowerSnapshot` inmutable con generación y
carga efectivas, límites y eficiencias de batería, calidad y déficit muestreados,
temporizadores de brownout y deslastre, modo operativo, identificadores de
módulos instalados y firmas de distribución, sistemas y trabajos. La fotografía
es una hipótesis para un intervalo, no estado persistente.
`capture_power_snapshot()` no recalcula potencias: quien llama aporta generación
y carga productivas en el instante de consulta. Un trabajo RUNNING suma carga
según `_compute_load_kw()`; la lista de trabajos cuyos temporizadores avanzan
es independiente. Las potencias efectivas y los identificadores de módulos
representan sus modificadores eléctricos.

Con generación y carga constantes, `battery_energy_after()` conserva los topes,
eficiencias y saturación productivos en **segundos propios de nave**.
`power_quality_components()` se comparte con el motor productivo, manteniendo
la escritura de `deficit_ratio` en `_compute_power_quality()`. Entre
regulaciones, la calidad es una función afín por tramos y recortada de la energía
de batería: su rama de carga cambia al 10 % y 50 %, y el recorte exterior al
alcanzar calidad 0 o 1. `integrate_quality()` divide en esas ramas matemáticas
y en batería 0/llena, e integra cada tramo lineal por sus extremos.
`integrated_wear()` utiliza `ordinary_wear_rate()` compartida en calidad 0 y 1:
la dependencia afín produce un resultado exacto para un sistema fijo,
radiación interna constante, tránsito/modo y multiplicador de brownout sostenido
constantes. Devuelve pérdida calculada y no la aplica a la integridad. Se
mantiene el redondeo de coma flotante.

`power_limits()` devuelve `TemporalLimit` condicionales en tiempo propio:
batería 0/10 %/50 %/llena, calidad 0,25/0,40/0,55, regulación inmediata por
capacidad, carga baja o colapso, temporizador de deslastre de 10 segundos y
temporizador de brownout sostenido de 30 segundos o reinicios inmediatos. Un
corte con `validity="mathematical_crossing"` representa igualdad matemática,
no una acción aplicada. Los cruces futuros siguen siendo candidatos. Si la
fotografía empieza exactamente en un cruce, `power_limits()` devuelve un corte
cero y deduce su sentido del flujo de batería. Tras tratarlo, el consumidor
devuelve a la consulta su `ResolvedElectricalLimit`, obtenido mediante
`resolve_electrical_limit()`, en `resolved`. Así se omite solamente el corte cero
ya procesado, sin ocultar un cruce futuro. Cada marca está vinculada a la
fotografía inmutable y no afecta a condiciones distintas. Debe descartarse
al avanzar el tiempo. Un cero sin resolver sigue activando la protección
`seen_zero_selections` de `nav_coordinator.py`, sin añadir tiempo artificial.
La inversión de calidad permite solo dos ULP de coma flotante para reconocer
igualdad tras la propagación analítica.

Las comprobaciones estrictas `<` se valoran por el lado al que se entra tras
un cruce descendente. Por eso el SOC del 10 % y la calidad 0,25 pueden devolver
una regulación cero con `validity="post_crossing_check"` aunque su condición
estricta sea falsa en la igualdad. El cruce de calidad 0,40 inicia el contador
de deslastre por ese lado; la igualdad no significa que haya vencido. Resolver
el cruce matemático no elimina las comprobaciones operativas cero: requieren
resolución aparte después de que el motor ejecute o descarte la acción. La
disponibilidad de batería usa `SOC > 0`; los temporizadores vencen con `>=`.
Con brownout activo y contador igual o superior a 30 segundos no se emite un
nuevo umbral sostenido ni un reinicio. Solo se informa un reinicio cuando el
brownout termina con contador positivo. La regulación puede alterar la carga y
deja obsoletos todos los límites posteriores de la fotografía. Los predictores
no deslastran, no deciden una carga posterior y no anticipan resultados
aleatorios.

`invalidation_reasons()` detecta cambios de potencia o límites efectivos,
operación o distribución, módulos, sistemas (incluidas reparación y aislamiento),
estado/potencia de trabajos y estado de brownout o temporizadores de deslastre.
Con `elapsed_proper_s` detecta además energía de
batería distinta de la evolución prevista. El consumidor debe invalidar también
tras cambios del reactor, activación/finalización de trabajos, deslastre,
saturación de batería, cambio de modo o cualquier acontecimiento que altere las
hipótesis. Un cambio de rama de calidad requiere reevaluación aunque la integral
analítica siga definida. La calidad y déficit muestreados son diagnósticos; la
calidad prevista se obtiene de las entradas compartidas, no de muestras antiguas.

`select_next_boundary(..., proper_limits=...)` acepta ahora varios límites
propios junto al de integridad. Convierte cada uno mediante el segmento
relativista activo; los trabajos siguen en tiempo galáctico. Un adaptador futuro
deberá reunir fase, integridad, trabajos y electricidad, cortar en el primero,
integrar electricidad y desgaste previos, aplicar efectos simultáneos en orden
causal y obtener una fotografía nueva. Antes de activar el movimiento físico
faltan una cota para la radiación interna variable, la reserva de combustible y
la política de frenado de emergencia. `Engine.tick()` y el viaje público no
cambian; su desgaste actual por muestra final no se sustituye en esta fase.
