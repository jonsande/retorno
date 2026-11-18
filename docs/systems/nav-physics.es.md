# Segmentos físicos de navegación (NAV-BRAKE-01B3A)

Esta es una API matemática pura de `src/retorno/core/nav_physics.py`, probada
en `tests/test_nav_segments.py`. No activa viajes físicos jugables, modifica
los relojes ni persiste rutas. El `TravelPlan` anterior desde reposo hasta
reposo y su coordinador siguen disponibles.

## Unidades y ecuaciones

La posición son metros hacia delante en un marco galáctico inercial
unidimensional. `beta = v/c` cumple `0 <= beta < 1`; `c` es
`LIGHT_SPEED_M_S`. Los tiempos galáctico y propio de la nave son segundos.
La aceleración propia firmada `a` se expresa en m/s²: positiva aumenta la
velocidad hacia delante, negativa frena y cero representa inercia.

Con rapidez inicial `eta0 = atanh(beta0)` y velocidad propia
`p0 = sinh(eta0) = gamma0*beta0`, un intervalo galáctico `dt` produce
`p = p0 + a*dt/c`, `beta = p/sqrt(1+p²)`,
`dx = c*dt*(p+p0)/(sqrt(1+p²)+sqrt(1+p0²))` y
`dτ = (c/a)*(asinh(p)-asinh(p0))`. La implementación calcula la diferencia
de rapidez con `log1p` y la distancia con la diferencia de gamma racionalizada
para evitar cancelaciones. Para `a=0`, `dx=c*beta0*dt` y
`dτ=dt*sqrt(1-beta0²)`. La inversa `galactic_time_at_segment_proper()` usa la
identidad del seno hiperbólico en el punto medio; no hay resolución iterativa
ni por pasos fijos. El muestreador anterior desde reposo utiliza ahora la misma
ecuación general.

## API y composición

`MotionState(galactic_s, distance_m, beta, proper_s)` registra valores
acumulados desde un origen elegido. `MotionSegment(start,
proper_acceleration_m_s2, duration_galactic_s, end_beta)` es inmutable y
valida su velocidad final física. Las factorías son `coast_for(start,
duration_galactic_s)`, `accelerate_to(start, target_beta,
proper_acceleration_m_s2)` y `brake_to_stop(start,
proper_deceleration_m_s2)`. Un objetivo de aceleración ya alcanzado y el
frenado desde reposo devuelven tramos explícitos de duración cero. La
aceleración no supera el objetivo y el frenado termina en cero.
`sample_segment(segment, dt)` devuelve el estado para cualquier tiempo
galáctico relativo del intervalo cerrado. `galactic_time_at_segment_proper(
segment, dτ)` devuelve el tiempo galáctico relativo para segundos propios
desde el comienzo del tramo.

Para interrumpir una maniobra, usar `truncate_segment(segment, dt)` y consultar
su extremo. Desde ese estado exacto se construye un tramo inercial o
propulsivo nuevo y se llama a `append_segment(chain, next_segment)`. Esta
operación exige igualdad exacta de posición, velocidad y ambos relojes en el
límite, y devuelve una tupla nueva. `sample_segments` consulta la cadena por
tiempo galáctico absoluto y asigna un límite compartido al tramo siguiente.
Las consultas no modifican la cadena. La posición puede superar la distancia
de un destino; esta API matemática no declara llegada ni visita un nodo.
`brake_to_stop()` emplea la duración de `braking_profile()`; la distancia y
el tiempo propio finales coinciden con ese perfil.

## Coordinador y trabajo pendiente

`select_next_boundary()` en `nav_coordinator.py` acepta ahora un `TravelPlan`
desde reposo hasta reposo o el `MotionSegment` activo. La selección sobre un
segmento usa su reloj inicial, estado y fin reales, sin recorrer la cadena
histórica ni recuperar tiempos nominales de fase o llegada.
`proper_time_in_segment()` y `galactic_time_at_segment_proper()` convierten un
límite de tiempo propio restante desde un segmento parcialmente recorrido.
El consumidor debe invalidar las predicciones obsoletas al cambiar la maniobra
o sus condiciones operativas y replantear desde la posición y velocidad
físicas actuales. Cruzar la coordenada de un destino no implica llegada. Véanse
los [límites temporales](nav-boundaries.es.md) para la política de cortes cero y
el orden causal pendiente.

Estos tramos solo modelan aceleración constante o inercia. No incluyen
gravedad ni inversión de rumbo. La coma flotante binaria limita la resolución
con tiempos o posiciones acumulados muy grandes; una maniobra inválida o no
representable produce `ValueError`.

## Primer intervalo interno del motor (NAV-BRAKE-01B3G)

`Engine.tick()` dirige un `PhysicalTransitState` existente con segmento
`coast` de aceleración cero a un adaptador causal acotado. Ninguna acción
pública crea ese estado. El tick histórico y `Travel` conservan su comportamiento.
El adaptador obtiene posición, velocidad y relojes acumulados de
`PhysicalTransitState.motion`. Actualiza una sola vez los relojes galáctico,
propio y biológico; proyecta los metros físicos sobre el vector entre nodos;
y conserva el destino y el movimiento aunque se cruce B. Al final exacto del
segmento conserva su estado final. Un tick posterior que lo sobrepase se
rechaza hasta disponer de una continuación real. La inercia no gasta
antimateria ni produce llegada o waypoint.

El intervalo admitido exige generación eléctrica excedente y fija, calidad
1, ausencia de brownout y temporizadores de regulación, trabajos y drones
activos, radio bloqueada, ningún plan de recuperación activo, ninguna
evaluación narrativa pendiente y ninguna transición crítica de supervivencia.
Se requieren geometría y tasas radiológicas conocidas en ambos extremos.
El motor usa `nav_electricity` para límites e integral de calidad, el
integrador eléctrico productivo para la batería, `nav_radiation` para dosis
espacial e interna y deterioro acoplado del casco, `nav_boundaries` para
pronósticos conservadores de salud y `nav_coordinator` para elegir el primer
corte. Rechaza un corte eléctrico, radiológico, de salud o fin de segmento
anterior al horizonte; también un límite radiológico diferido, pues no puede
demostrar que su primer cruce incierto quede después. No se inventan ETA ni
pasos fijos. El desgaste usa las integrales de calidad y radiación.

Predicción y ejecución se realizan sobre una copia profunda de `GameState`;
los campos preparados se publican solo tras completar todos los efectos y
comprobaciones. Las consultas predictivas no consumen RNG. Un rechazo
conserva estado, eventos y contador RNG originales. Los hooks generales de
narrativa, alertas, recuperación y radio se ejecutan una sola vez sobre la
copia y bajo las condiciones citadas. Los segmentos propulsivos, trabajos,
drones, recepción de radio, cortes narrativos, regulación eléctrica y cambios
de estado de salud internos requieren un futuro bucle de resolución causal.
El adaptador no copia `_tick_interval()`, no crea otro bucle de juego ni un
formato de guardado nuevo.

## Acciones de navegación y referencias del estado (NAV-BRAKE-01B3G-R1)

Un `ship.physical_transit` activo cuenta como tránsito para las decisiones
públicas de `Travel` y `RouteSolve`, aunque el indicador histórico
`ship.in_transit` sea falso. Ambas acciones devuelven el evento existente
`BOOT_BLOCKED` con motivo `physical_in_transit` antes de calcular combustible, refinar
rutas, crear trabajos o modificar la navegación. `Status`, `Diag` y las
acciones habituales de supervivencia o reparación conservan sus propias
validaciones. El parser CLI y la ruta de comandos de Textual delegan estas
acciones mediante `GameLoop.apply_action()` al mismo bloqueo del motor. Este
motivo evita el consejo histórico de `in_transit` de esperar hasta la llegada,
que no corresponde a un segmento físico activo. La
presentación de rutas también marca bloqueada la salida. Esto no activa el
viaje físico público ni cambia los viajes históricos sin estado físico.

`GameLoop` conserva la raíz `GameState`; los renderizadores CLI y los
presentadores de Textual obtienen sus componentes actuales de ella en cada
operación. El commit físico conserva ahora la identidad de la raíz y de sus
objetos inmediatos `meta`, `clock`, `world`, `ship`, `os`, `jobs` y `events`.
Copia sus campos desde el estado preparado completo; `GameLoop` mantiene su
bloqueo durante la operación.
Un fallo durante la preparación deja intactos los componentes originales; si
falla una asignación del commit, restaura los campos previos y propaga el
error. Los objetos más profundos, como `ship.power`, sistemas, listas de
eventos y colecciones del mundo, pueden sustituirse en un commit satisfactorio;
los consumidores deben leerlos desde su propietario actual tras cada tick.
Las rutas productivas de CLI, Textual, persistencia y eventos siguen esa
regla. Las pruebas ejercitan referencias superiores conservadas a través de
un `GameLoop` y el presentador Textual reales, movimiento, guardado/carga y
errores de prevalidación y ejecución tardía.

## Primeros intervalos propulsivos del motor (NAV-BRAKE-01B3H-A)

`Engine.tick()` procesa ahora segmentos internos `accelerate`, `coast` y
`brake` mediante el mismo adaptador acotado `_tick_physical_segment()`.
Muestrea el `MotionSegment` inmutable en el extremo galáctico solicitado,
obtiene el tiempo propio con `proper_time_in_segment()` y actualiza posición,
velocidad, tiempo de la nave y edad biológica sin reconstruirlos desde una ETA.
La aceleración admite reposo o beta positiva y se detiene en la velocidad
definida por el segmento. El frenado mantiene avance hasta el extremo, donde
beta puede ser exactamente cero. Cruzar el destino no declara llegada.
Se rechaza un tick posterior al fin del segmento hasta preparar una
continuación física. Ningún comando público crea tránsito físico.

La API interna `Engine.prepare_physical_segment()` comprueba relojes,
geometría, continuidad, intención, capacidad de motores y límite vigente de
velocidad. Cada tramo propulsivo requiere un `pricing_speed` discreto no menor
que las velocidades de ambos extremos. La preparación descuenta una vez
`Engine.engine_fuel_cost()` del saldo contable `antimatter_capsules` y guarda
un recibo inmutable `PropulsionAuthorization` asociado a ese segmento y al
destino original. Los ticks posteriores no vuelven a descontarlo. Cada tramo
propulsivo adicional necesita preparación y cobro propios; la inercia no los
necesita. Es una aplicación interna y provisional por tramo de la tarifa
existente por viaje, sin modelo de consumo continuo ni cambio del precio
público. El recibo es fiable cuando procede de esta preparación interna;
editar arbitrariamente un guardado queda fuera del contrato de integridad.

El clasificador existente conserva su comparación estricta en el 35 %.
Se usan por separado `acceleration_available()` y `braking_available()`,
además del aislamiento efectivo y el funcionamiento de núcleo y distribución.
En el 35 % se rechaza acelerar porque aún falta la transición de frenado
preventivo. Se puede frenar exactamente al 15 % si el desgaste del intervalo
no rebasa ese valor. Se rechazan atómicamente los intervalos que atraviesan
el límite de su capacidad. Siguen vigentes las restricciones de salud,
electricidad, radiación, narrativa, trabajos, radio, recuperación y
supervivencia de 01B3G. Se reutilizan la calidad eléctrica en tiempo propio,
la radiación espacial, el desgaste acoplado de casco y sistemas y
`select_next_boundary()` con beta variable. La propulsión no añade una carga
eléctrica inventada: rige el balance productivo existente.

Preparación y tick trabajan sobre una copia profunda y publican una vez,
conservando identidades de `GameState` y propietarios inmediatos. Un rechazo
conserva combustible, relojes, eventos y RNG. Las pruebas cubren referencias
analíticas de aceleración y frenado, subdivisión, umbrales, recibos pagados,
guardado/carga, hibernación, sobrepaso y cortes fallidos. NAV-BRAKE-01B3H-B
deberá resolver cortes anteriores y transiciones simultáneas, finalizaciones
de trabajos, regulación eléctrica, replanificación, frenado preventivo y
llegada física antes de la activación pública. Las descripciones anteriores de
01B3G conservan el alcance más estrecho de aquella fase.
