# Segmentos físicos de navegación (NAV-BRAKE-01B3A)

## Precisión y avance prolongado (NAV-BRAKE-01B3H-D2B1-R2)

El coordinador conserva el tiempo local transcurrido dentro del segmento como
coordenada de cálculo. Calcula los límites propios y radiológicos con diferencias
locales, sin restar dos relojes absolutos grandes. Si un corte físico positivo
es menor que una ULP del reloj galáctico, lo sitúa en el siguiente instante
representable y avanza ambos relojes. La elección de umbrales estrictos de
salud se ajusta al lado correcto con `nextafter`; los residuos de hasta cuatro
ULP al final de una solicitud se tratan como coincidencias representacionales.
No se añade una duración mínima arbitraria ni se omite una frontera causal.
La agrupación de causas exige coincidencia tanto a escala del reloj absoluto
como a escala de la duración local solicitada; así, cuatro ULP de un reloj
galáctico enorme no agrupan eventos separados por segundos. El umbral
específico del 15 % de motores también se fija exactamente dentro de la
tolerancia numérica ya aplicada a los demás umbrales de salud.

La predicción nominal sin trabajos ni transición pendiente consulta el estado
sin copiarlo. El tick mantiene una copia transaccional completa mediante
serialización local, para preservar rollback e identidad de propietarios. La
clave de reglas del universo se memoriza solo dentro de la transacción atómica
del tick. Una hibernación estable en crucero puede pedir bloques de 26 semanas;
esto exige explícitamente `physical.intent == "coast"`, por lo que acelerar o
frenar mantiene los bloques semanales aunque las demás condiciones sean estables.
Las fronteras causales siguen cortando cada bloque, y el siguiente se decide
desde el estado consolidado. Con trabajos, batería variable, recuperación,
narrativa pendiente o mantenimiento de drones se conserva el horizonte de
siete días. La radio sigue sus restricciones de recepción durante hibernación.
Si al final de la petición queda un residuo positivo que redondea al instante
actual tras un avance real, la hibernación termina sin repetirlo ni contarlo como
tiempo transcurrido. Una transición causal pendiente o una petición que no puede
avanzar desde el inicio se comunican como bloqueo, sin declarar llegada.

Textual ejecuta la simulación de hibernación fuera de su bucle de interfaz. El
worker entrega tiempos reales por una cola, que el temporizador de paneles
consume en el hilo de Textual. La entrada permanece deshabilitada hasta el
despertar; el cierre espera a la simulación antes de guardar. Paneles y eventos
automáticos comparten una instantánea bajo lock no bloqueante; se omite un
refresco si el motor está ocupado. Un error inesperado en
el avance automático pausa el bucle y genera un aviso observable; no avanza
el tiempo de juego por un resultado ficticio.

## Corrección del playtest (NAV-BRAKE-01B3H-D2B1-R1)

La validación de intervalos físicos considera el mismo instante galáctico a
dos extremos separados por hasta cuatro ULP, conforme a la regla existente
del coordinador para coincidencias. El integrador sigue siendo la autoridad y
los límites causales anteriores siguen deteniendo el intervalo. Un tick físico
público prepara una sola copia del estado completo; el tramo nominal trabaja
sobre esa misma transacción provisional, con rollback e identidad estable de
los componentes principales. La predicción conserva una copia independiente
de solo lectura.

El avance automático de un segundo utiliza plazos monotónicos. El coste del
procesamiento deja de sumarse a cada período nominal; se omiten los plazos
perdidos sin reproducir ticks ni cambiar el tiempo de juego por tick. Tras un
despertar normal o anticipado legítimo, la hibernación restablece la política
previa de avance automático si la partida no está en estado terminal. Una
frontera técnica aún no resuelta mantiene el tiempo automático pausado y
emite un aviso; el guardado puede recargarse después de corregir el defecto.
Los subsistemas ordinarios de la nave siguen activos.

## Coordinación causal pública (NAV-BRAKE-01B3H-D2B1)

La navegación física pública admite drones a bordo, electricidad variable,
desgaste y radiación ordinarios, trabajos compatibles, evaluaciones narrativas,
radio y planes existentes de recuperación de exploración. La predicción interna
`Engine.next_physical_step()` selecciona el siguiente corte antes de cada
`Engine.tick()` productivo. `GameLoop.advance_interval()` la comparte con
`step()`, avance automático, espera DEBUG e hibernación de CLI y Textual. No
divide viajes largos en segundos fijos.

Los candidatos incluyen fin de fase, batería llena o vacía, cruces de carga y
calidad, regulación y alertas eléctricas, límites radiológicos y de casco,
umbrales de salud, finalización de trabajos y evaluación narrativa. La
electricidad y el desgaste ordinario usan tiempo propio; drones, trabajos y
narrativa conservan sus relojes vigentes. En un instante coincidente se integra
una vez el intervalo previo, se actualizan electricidad, exposición y desgaste,
se resuelven trabajos vencidos y se ejecutan alertas, recuperación de
exploración y radio sobre la posición física nueva. El siguiente pronóstico
parte del estado consolidado. Un fallo genuino conserva intacto el estado
anterior del subintervalo; una petición pública interrumpida informa del
tiempo ya ejecutado.

El 35 % de integridad de motores activa el frenado preventivo pagado y el
15 % termina la capacidad de frenado; la nave sigue por inercia hasta una
intervención válida. La llegada requiere beta cero dentro de tolerancia;
detenerse fuera crea un waypoint físico. `hibernate until_arrival` termina en
una llegada real. La hibernación de duración fija continúa tras una llegada
normal y despierta ante emergencia, detención física fuera del destino o
cruce radiológico ambiental configurado. La radio requiere `comms` y
`radiod` operativos; las reglas actuales suspenden recepción al hibernar.

Siguen restringidos el aborto físico voluntario, nueva aceleración durante el
tránsito, cambio de destino, inversión de rumbo y nuevas maniobras públicas
de recuperación manual; su interfaz corresponde a D2B2. `install`,
`cargo audit` y `auth recover` permanecen bloqueados durante el plan físico
nominal porque sus efectos requieren coordinación adicional. La reparación
inercial conserva sus reglas causales específicas. Los casos restantes con
drones desplegados o electricidad extrema se evalúan al producirse el evento;
no son precondiciones para viajar con drones almacenados.

## Navegación nominal pública (NAV-BRAKE-01B3H-D2A)

`nav <node_id>`, `travel <node_id>` y `nav --no-cruise <node_id>` inician
ahora la misma trayectoria física prepaga entre reposos para saltos directos
interestelares conocidos. `engines speed max|<beta>` selecciona la beta
objetivo; un trayecto corto puede alcanzar una beta máxima inferior. La
aceleración propia provisional es **1,0 m/s²**, el valor predeterminado de
`Engine.prepare_nominal_physical_travel()`, expuesto en
`Engine.NOMINAL_PROPER_ACCELERATION_M_S2` para su balance futuro. No hay
selector público de aceleración. `nav map routes` y la confirmación utilizan
`plan_travel()` para estimar tiempo galáctico y propio y conservan la tarifa
actual. La ETA es nominal y depende de que no haya incidencias propulsivas.

Los saltos locales (mismo sector y como máximo `LOCAL_TRAVEL_RADIUS_LY`)
conservan la vía histórica a 20 km/s y coste cero, incluido `nav abort`.
El viaje físico deja `ship.in_transit` en falso para que la llegada histórica
basada en `arrival_t` no teletransporte la nave. `ship.physical_transit` es
la autoridad del movimiento y el predicado operativo compartido protege otra
salida, resolución de rutas, acoplamiento, cambio de velocidad y aborto
histórico. Las consultas y los controles eléctricos compatibles conservan
sus restricciones; D2B1 admite trabajos compatibles y mantiene bloqueadas
las categorías indicadas arriba. La reparación inercial sigue disponible.
`status` y Textual muestran fase, beta instantánea, distancia
restante con signo, ambos tiempos transcurridos y ETA nominal solo mientras
el plan siga vigente. El sobrepaso no se limita; la inercia carece de ETA de
llegada garantizada.

En D2A, `GameLoop.advance_interval()` avanzaba por finales de fase nominal, incluido
el paso de aceleración a crucero, aceleración directa a frenado, crucero a
frenado y frenado a reposo. `hibernate until_arrival` se detiene al llegar;
`hibernate <años>` y `wait <segundos>` en modo DEBUG siguen con tiempo
ordinario si se solicitó más. `Engine.tick()` conserva el rechazo atómico de
intervalos que superen el horizonte físico. D2B1 amplió la coordinación a
los cortes ordinarios descritos arriba; los que sigan sin soporte interrumpen
el avance con el tiempo ya ejecutado.
El guardado durante cualquier fase conserva el plan pagado y sus relojes.

## Detención física y llegada operativa (NAV-BRAKE-01B3H-D1)

`Engine.tick()` cierra el frenado físico terminal en la misma transacción que
avanza su último intervalo. La muestra de movimiento aporta la única distancia
y el tiempo coordenado. Solo hay llegada con beta cero y dentro de
`Engine._nominal_distance_tolerance()` del destino original (como mínimo
1 metro, ampliado según la resolución binaria). La nave y el mundo pasan
entonces al nodo de destino, sin acoplar; se limpian `physical_transit` y los
campos operativos de tránsito, se marca el nodo como visitado, se cierra su
ventana de lore de entrada en órbita, progresa el prólogo de Harbor cuando
corresponde, se eliminan el waypoint temporal anterior y el nodo inicial
desconocido, se ejecuta la recuperación de exploración y se registra un único
evento `ARRIVED`. Estos efectos sin tiempo añadido no repiten el intervalo físico.

Con beta cero fuera de esa tolerancia, la transacción crea un nodo vacío de
tránsito `NAV_PT_...` en la posición integrada. Pasa a ser el nodo actual y
emite `PHYSICAL_STOPPED`, distinto de `TRAVEL_ABORTED` voluntario. No visita el
destino, no cierra su ventana de lore ni emite `ARRIVED`. El waypoint no ofrece
por sí mismo recursos, servicios, acoplamiento ni uplink. Solo enlaza con
origen o destino conocidos y existentes dentro del límite operativo de
45 años luz. Si ambos quedan fuera de alcance no se inventa un enlace;
resolver la movilidad allí queda pendiente de diseño. Un waypoint anterior
permanece durante la trayectoria que sale de él, y `_clear_tmp_node()` limpia
sus enlaces, índices, pools y trabajos dependientes al terminar. Los
waypoints físicos dejan `active_tmp_progress` vacío: ese campo sigue
representando el porcentaje del aborto voluntario histórico, sin limitar
la distancia física.

Cruzar B con beta positiva conserva el tránsito y el destino original aunque
la distancia integrada exceda A–B. Un límite de desgaste coincidente con beta
cero no programa inercia. Los ticks solicitados más allá de la detención se
rechazan atómicamente; el tiempo ordinario puede avanzar en el tick siguiente.
El guardado/carga del formato actual conserva movimiento activo, inercia y
detenciones ya consolidadas sin repetirlas. El comando público `travel`
interestelar utiliza ahora la salida física; la recuperación manual sigue
siendo interna. Las secciones previas conservan el alcance
incremental de su fase; esta sección define la finalización vigente.

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

## Viajes nominales con pago único (NAV-BRAKE-01B3H-B1)

`Engine.prepare_nominal_physical_travel(state, destination_id,
target_beta=None, proper_acceleration_m_s2=1.0)` es una API **interna** de
salida. Exige nave libre y desacoplada en el origen, destino conocido con
enlace existente dentro del límite de 45 al, aceleración ordinaria disponible
y velocidad objetivo discreta admitida sin superar el máximo actual. Convierte
la distancia geométrica conocida mediante `light_years_to_metres()`, llama a
`plan_travel()` y construye una cadena continua con `accelerate_to()`,
`coast_for()` opcional, `brake_to_stop()` y `append_segment()`. No crea ni
descubre rutas. Desde D2A, `Travel` público interestelar llama a esta API.

`NominalTravelState` guarda origen y destino, `TravelPlan` inmutable, dos o
tres segmentos inmutables, velocidad y coste de tarifa, índice acotado de
fase e indicadores explícitos de finalización e invalidación.
`PhysicalTransitState` mantiene el segmento activo y tiempo galáctico
transcurrido; su propiedad `motion` sigue siendo la fuente de posición, beta
y ambos relojes físicos. El registro nominal persiste y vincula toda la
cadena autorizada al destino original. Un pickle de estado físico de 01B3H-A
se carga con `nominal_plan=None`. La API anterior de preparación por segmento
y su recibo siguen disponibles para maniobras internas aisladas.

La preparación nominal llama a la preparación por segmento sobre una copia
privada para reutilizar validación de capacidad y la tarifa
`Engine.engine_fuel_cost()`. Después sustituye el recibo temporal por una
única autorización del plan y publica la copia una vez. Se descuenta
`ship.antimatter_capsules` una sola vez al salir; es el único saldo de
combustible. Aceleración y frenado previstos usan esa autorización sin nuevo
cobro; el crucero es inercial. Otro destino, fase o maniobra añadida no pueden
reutilizarla. Las maniobras extraordinarias o replanteadas no están cubiertas.

`Engine.tick()` ejecuta el intervalo nominal sobre un `GameState` privado,
separándolo solo en los finales analíticos de fase y reutilizando
`_tick_physical_segment()` para cada parte. Cada segmento siguiente comienza
en el `MotionState` exacto del anterior. Salud, electricidad, radiación,
desgaste, posición y relojes mantienen continuidad. Los pronósticos se
calculan otra vez desde el estado preparado al cambiar de fase. El estado
original recibe un solo commit si todas las partes terminan. Un corte
anterior o diferido sin resolver rechaza el intervalo **completo**, incluso
si la segunda o tercera fase falla. No hay pasos fijos de un segundo.

Al terminar el frenado, beta vale exactamente cero y la distancia física
debe coincidir con el destino dentro de `max(1 metro, 64 ulp(distancia_m))`.
El registro pasa a `completed`; un tick físico positivo posterior se rechaza
sin reiniciar el empuje ni cobrar. No se producen llegada pública, visita,
cambio de manifiesto, waypoint ni acoplamiento. Una petición posterior al
extremo final se rechaza sin avance parcial.

Esta fase solo admite intervalos nominales no interrumpidos bajo las
restricciones de electricidad, radiación, salud, trabajos, drones, radio,
narrativa y supervivencia de 01B3H-A. Se conservan las reglas exactas del
35 % y 15 %, mientras el frenado preventivo y de emergencia automáticos
siguen pendientes. Con aceleración nominal de 1 m/s² pueden completarse
trayectos cortos; los intervalos largos pueden encontrar un corte operativo
y se rechazan hasta que B2 lo resuelva. B2 deberá invalidar planes nominales
obsoletos, resolver cortes simultáneos y averías, autorizar aparte cualquier
maniobra propulsiva nueva y replantear desde posición y beta reales.

## Primer corte causal por desgaste de motores (NAV-BRAKE-01B3H-B2A)

Dentro del régimen eléctrico y radiológico restringido de 01B3H-A,
`first_integrated_wear_at()` acota el primer acontecimiento de integridad de
motores en el intervalo físico solicitado. Cada evaluación de la bisección
recalcula `integrate_segment_radiation()` e `integrated_system_wear()` desde
el mismo casco, motor y estado eléctrico iniciales. Primero se comprueba el
extremo del intervalo; la búsqueda termina cuando las cotas son instantes
galácticos representables adyacentes. Utiliza la misma comparación redondeada
`health - wear <= threshold` que la actualización del estado. La anchura de
la cota es un paso de coma flotante para el desgaste **integrado
numéricamente**; también limitan la precisión temporal el error estimado de
cuadratura radiológica y la acumulación en coma flotante. Subdividir un caso
de radiación variable puede desplazar el corte varias décimas de nanosegundo:
hay que consultar de nuevo el límite desde el estado actualizado, sin
considerar autoritativa una predicción anterior. No se usa tick fijo ni se
inventa un épsilon positivo en un umbral estricto. Si el intervalo positivo o
el reloj propio no son representables, se rechaza.

Al alcanzar el 35 % mientras acelera, `_tick_physical_segment()` confirma la
posición, beta, relojes galáctico/propio/biológico, pérdida de casco y desgaste
ordinario solo hasta el límite. La integridad de motores queda exactamente en
0,35 sin alterar el clasificador vigente de `SystemState`.
`PhysicalTransitState` registra `pending_transition="safety_brake"` y
`replan_required=True`; el `NominalTravelState` pagado pasa a `invalidated` y
conserva el destino original. `safety_braking` y `braking_started` siguen
falsos: no se ha ejecutado un segmento nuevo de frenado. Al alcanzar el 15 %
durante un frenado, el valor pendiente es `"inertia"` y se conserva la beta
real no nula. En la igualdad todavía hay capacidad de frenar, pero se rechaza
el desgaste positivo posterior del segmento antiguo. El aislamiento efectivo
de motores sigue impidiendo la propulsión desde el inicio.
El mismo corte preventivo del 35 % se trata durante el crucero nominal; beta
permanece constante y no se declara iniciado ningún frenado.

`Engine.tick()` admite un intervalo que termina en un acontecimiento de motor
resoluble. Si pretende continuar después, falla atómicamente aunque ya se
haya evaluado una fase nominal anterior en el estado privado. Un final de
fase nominal simultáneo puede suspender su fase actual; un límite eléctrico,
radiológico, de salud u otro no resuelto y simultáneo rechaza todo el
intervalo. `select_next_boundary()` sigue comprobando esos otros límites.
La ETA y la autorización del plan nominal invalidado no pueden impulsar otro
tick ni pagar una maniobra nueva. La marca de suspensión persiste en
guardado/carga; los pickles físicos de ocho campos de 01B3H-A y nueve de
01B3H-B1 siguen siendo legibles. No hay llegada, waypoint, viaje público ni
cobro nuevo de combustible.

La siguiente intervención deberá sustituir la marca pendiente por un nuevo
segmento autorizado de frenado de seguridad o inercia desde la posición y
beta físicas conservadas, resolver cortes no motores simultáneos según el
orden causal y definir la contabilidad del frenado nominal ya pagado y de
cualquier propulsión adicional. Los cambios de calidad eléctrica, trabajos,
drones, cortes de radio/narrativa, cambios de estado de motor fuera del umbral
de capacidad tratado y límites radiológicos no resueltos aún rechazan el
intervalo.

## Frenado preventivo automático pagado (NAV-BRAKE-01B3H-B2B1)

En el siguiente `Engine.tick()` positivo tras un corte de B2A en aceleración
o crucero nominal, `pending_transition="safety_brake"` se sustituye en el
instante conservado por `brake_to_stop(physical.motion, aceleración propia
nominal)`. El nuevo segmento empieza en la posición, beta, reloj galáctico y
reloj propio reales. La transición en sí no consume tiempo, electricidad,
desgaste, RNG ni combustible. Un tick de duración cero sigue siendo inocuo.
El segmento recorre la vía física causal existente, con electricidad,
radiación, pérdida de casco, desgaste y tiempo propio y biológico. El plan
nominal permanece invalidado y `replan_required` sigue siendo verdadero.

`NominalBrakingSubstitution` conserva el plan pagado e invalidado, la fase y
el tiempo transcurrido al interrumpirse, el destino original, el segmento
sustitutivo exacto y el acontecimiento de motores al 35 %. El estado valida
que sea un frenado continuo desde el movimiento interrumpido hasta beta cero,
con la desaceleración nominal y sin superar la beta máxima del plan. Es el
único frenado ya incluido en la tarifa nominal: no crea otro recibo ni cambia
el saldo de antimateria. No permite cambiar de destino, preparar otro
segmento ni reanudar la aceleración. Un segmento físico pagado por separado
carece de cobertura nominal para esta sustitución y sigue rechazándola. La
autorización y su marca de finalización persisten en guardado/carga; siguen
siendo legibles los payloads físicos anteriores.

La integridad exactamente igual al 35 % permite iniciar el frenado. Desde el
15 % inclusive y por debajo del 35 %, los motores pueden frenar, pero no
acelerar. El acontecimiento de cambio DAMAGED a CRITICAL provocado por el
primer intervalo positivo se conserva una sola vez. En un corte exactamente
al 15 % con beta positiva, se detiene el avance del segmento y
`pending_transition="inertia"` conserva el movimiento real; B2B2 deberá
activar la continuación inercial. Si beta llega antes a cero, la sustitución
queda finalizada en la posición real de parada y los ticks positivos
posteriores no pueden reiniciarla. No hay llegada pública ni waypoint aunque
se cruce el destino con velocidad positiva. Más allá de la ruta se utiliza
la política radiológica espacial provisional. Con geometría nominal fija y
la misma desaceleración, un corte en aceleración o crucero detiene la nave en
B o antes; desplazar la geometría del destino tras partir permite comprobar
el caso espacial de sobrepaso, que no se produce en el viaje ordinario B2B1.

La activación y el intervalo positivo solicitado se ejecutan sobre un
`GameState` preparado en privado y se confirman juntos. La falta de
alimentación, el aislamiento, los límites eléctricos o radiológicos sin
resolver, los acontecimientos de salud incompatibles y la petición de un
intervalo posterior al corte causal rechazan toda la operación sin activar
parcialmente el frenado. B2B2 deberá resolver la inercia pendiente;
intervenciones posteriores deberán tratar reparaciones y replanteamiento,
llegada pública y waypoints, y autorizar con combustible válido cualquier
maniobra propulsiva adicional.

## Continuación inercial automática (NAV-BRAKE-01B3H-B2B2)

Cuando un intervalo de frenado termina en el corte causal del 15 % con beta
residual, el siguiente `Engine.tick()` positivo crea un segmento `coast_for()`
sin empuje desde el `MotionState` exacto conservado. Su inicio mantiene
distancia, beta, tiempo galáctico y tiempo propio. Un tick de duración cero no
hace nada. El motor simula el intervalo solicitado sobre un estado privado y
confirma la transición y el avance juntos; un límite eléctrico, radiológico,
de salud, trabajo u otro límite causal no soportado rechaza toda la petición
y conserva la marca pendiente. Una petición que *contiene* el corte del 15 %
sigue rechazándose: el llamante debe terminar un tick en ese instante y
solicitar después el intervalo inercial.

`InertialContinuation` conserva el segmento y tiempo transcurrido del frenado
interrumpido, el destino original y la autorización nominal o independiente
ya utilizada. En el frenado preventivo sustitutivo conserva además el plan
nominal pagado y `NominalBrakingSubstitution`; en el frenado nominal directo,
el plan pagado e invalidado; y en un frenado independiente, su
`PropulsionAuthorization` gastada. El estado físico activo carece de recibo
propulsivo y de sustitución activa. El plan antiguo permanece invalidado, no
se cobra ni devuelve antimateria y este historial no autoriza nuevo empuje.
Siguen siendo legibles los estados físicos guardados anteriormente. Cada
segmento inercial dura solo el intervalo solicitado en ese tick; tras su
extremo administrativo, el siguiente tick lo renueva desde el extremo físico
exacto. No hay ETA inercial de llegada ni scheduler de pasos fijos.

La vía física existente actualiza posición, batería, radiación, casco,
desgaste de sistemas, relojes galáctico/propio/biológico y acontecimientos.
La integridad de motores puede bajar del 15 %, o los motores pueden quedar
aislados u OFFLINE, sin cambiar beta inercial. Los demás cortes operativos
conservan el rechazo conservador. Cruzar y sobrepasar el destino original con
beta positiva no declara llegada, no acopla, no crea waypoint, no cambia el
nodo actual ni agrega rutas. La política radiológica provisional se satura
al valor del extremo más allá de B. `Travel` y `RouteSolve` públicos siguen
prohibidos mientras existe tránsito físico. Reparaciones, replanteamiento,
reanudación del frenado, waypoints y avisos de sobrepaso requerirán fases
posteriores y autorización separada para cualquier empuje nuevo.

## Reparación causal de motores durante la inercia (NAV-BRAKE-01B3H-C1)

La vía inercial interna utiliza ahora las fases productivas del scheduler:
`_begin_job_interval()`, `_next_job_completion_s()`, `_advance_job_timers()`
y `_resolve_job_interval()`. En cada límite, los trabajos QUEUED admisibles
se activan antes de tomar la fotografía eléctrica. La previsión incluye así
el `power_draw_kw` existente de un trabajo RUNNING; actualmente la reparación
ordinaria configura un consumo adicional nulo. El intervalo siguiente acaba
en la primera finalización de trabajo o en el horizonte solicitado. Primero
se integran movimiento físico, electricidad, radiación y desgaste de casco y
sistemas; después se descuenta la ETA galáctica y se resuelve el resultado
productivo en ese mismo instante. El intervalo siguiente vuelve a calcular
todas las condiciones. Un trabajo con ETA cero se resuelve en el instante
actual sin inventar movimiento. El scheduler público histórico conserva su
orden previo.

La vía admitida comprende un solo trabajo `REPAIR_SYSTEM` para `engines`,
propiedad de un dron desplegado en un sector interior. `Engine.apply_action`
con `Repair` sigue reservando chatarra y creando el trabajo real. El
resolutor normal realiza el sorteo de fallo, el consumo o devolución de
materiales, el gasto de batería del operador, el cambio de integridad y los
eventos. La beta inercial y el historial propulsivo gastado permanecen
inalterados aunque la reparación restablezca la capacidad de frenar. El
nuevo empuje y el replanteamiento siguen prohibidos. El consumo de batería en
espera, la dosis radiológica y el deterioro del dron usan los métodos
productivos existentes en segundos galácticos; la integral radiológica física
proporciona la dosis galáctica espacial completa. Se rechaza antes de
confirmar un intervalo que cruce sin coordinación una reserva de retorno, un
umbral radiológico del dron o su límite de integridad. Tampoco se aplica a
todo el intervalo la tasa radiológica del extremo final.

Todo el tick solicitado se ejecuta en un `GameState` privado; efectos del
trabajo, movimiento, eventos y RNG se confirman una sola vez. Un límite
posterior no soportado revierte una reparación simulada anterior. Más de un
trabajo admisible, trabajos ajenos a motores, otras configuraciones de dron,
límites de autorretorno y cortes eléctricos, radiológicos, de salud o
narrativos no resueltos continúan rechazándose atómicamente. `Travel`,
`RouteSolve`, `Dock` y `Scan` de nodo siguen bloqueados durante el movimiento
físico. El futuro replanteamiento deberá partir de posición y beta reales,
conservar el historial de trabajos y combustible ya gastado y obtener nueva autorización
de combustible para cualquier maniobra propulsiva.

## Cálculo condicional de recuperación tras reparar (NAV-BRAKE-01B3H-C2A)

`nav_recovery.plan_inertial_recovery()` es una consulta interna pura. Recibe
un `PhysicalTransitState` válido con `InertialContinuation` y lee su
`MotionState` actual: distancia recorrida en metros sobre la línea original
A–B, beta, segundos galácticos y segundos propios de la nave. La distancia al
destino procede de la geometría real de los nodos A y B, convertida con el año
luz físico juliano. Por defecto usa la desaceleración propia del frenado
interrumpido; el llamador puede indicar otra desaceleración disponible en ese
momento. Ni la ETA nominal antigua ni el índice de su fase pagada intervienen.

El `braking_profile()` relativista existente da la distancia mínima de
detención. Si la distancia restante es mayor, el plan propone inercia a beta
constante hasta el último punto posible de frenado, seguida de
`brake_to_stop()`. La igualdad exacta propone frenado inmediato, sin un tramo
inerte de duración cero. Si falta distancia, incluso cuando la nave ya está
más allá de B, propone frenado de emergencia inmediato e identifica la
posición física de detención más allá de B. Ninguna rama acelera, invierte la
marcha, declara llegada o crea waypoint. Se representan tanto el punto
recomendado como el último físicamente posible; coinciden porque no se ha
aprobado un margen operativo adicional. La tolerancia numérica de cierre
solo valida el cálculo de los segmentos y no modifica la frontera estricta
de decisión.

El `RecoveryPlan` inmutable separa la capacidad física de frenar, la
disponibilidad operativa actual según la vía eléctrica existente y la
autorización pendiente para todo segmento propulsivo nuevo. Bajo el 15 % de
integridad o con aislamiento efectivo de motores devuelve `no_propulsion`;
una vía eléctrica deshabilitada produce el mismo resultado, conservando la
distinción de capacidad física. Una entrada mal formada o ajena a la inercia
devuelve `invalid`. La viabilidad de un plan propulsivo solo es cinemática y
condicional a mantener la desaceleración propia: desgaste, radiación,
electricidad, drones y trabajos futuros pueden interrumpirlo. `is_current()`
compara estado físico, relojes, geometría, sistemas pertinentes, electricidad,
carga de trabajos activos y saldo de combustible; una desaceleración externa
debe volver a suministrarse al comprobar vigencia. Los planes
no se persisten como segundo estado autoritativo de navegación.

C2A no cambia `Engine.tick()`, instala segmentos ni descuenta antimateria.
`InertialContinuation` conserva la autoridad de frenado nominal, sustitutiva
o independiente ya utilizada solo como historial. C2B tendrá que revalidar
el plan justo antes de ejecutarlo, definir y reservar una nueva autorización
de combustible y después aplicar los cortes causales existentes de
electricidad, radiación, desgaste y trabajos. Las futuras políticas de límite
de inercia, sobrepaso, llegada o waypoint son independientes.

### Precisión numérica y origen de la desaceleración (C2A-R1)

La comprobación original del perfil escalaba su tolerancia solo con las
posiciones inicial y de B. Cuando la distancia de frenado supera mucho a
ambas, la suma y resta en coma flotante pueden producir una diferencia de
unos metros entre el perfil y el segmento, provocando un `invalid` erróneo.
La comprobación del perfil utiliza ahora 64 ULP de la mayor magnitud
pertinente: posición inicial, distancia de frenado o posición final prevista,
con un suelo de 1 m. La comprobación separada del cierre tras inercia usa la
posición inicial, B, distancia de frenado, extremo de inercia y posición
final. Ambas tolerancias comprueban coherencia numérica; la comparación
entre **distancia restante y distancia de frenado sigue siendo estricta**.
Ninguna tolerancia concede distancia adicional para detenerse en B. Una
incoherencia material sigue produciendo `invalid`.

`RecoveryPlan.deceleration_source` registra `history` o `external`. Cuando
se usa la desaceleración del frenado interrumpido, puede recuperarse del
historial físico actual. Para una desaceleración externa, `is_current()`
devuelve falso si el llamador no proporciona el valor disponible en ese
momento; también devuelve falso si el valor cambió. C2B debe verificarlo
antes de autorizar o ejecutar ninguna maniobra y seguir evaluando los cortes
operativos durante la ejecución.

## Ejecución interna de la recuperación tras reparar (NAV-BRAKE-01B3H-C2B1)

`Engine.prepare_inertial_recovery(state, plan=None,
proper_deceleration_m_s2=None)` es una operación interna. Exige un
`InertialContinuation` real, ningún trabajo de reparación activo, capacidad
actual de frenado y un `RecoveryPlan` vigente. Si se proporciona un plan,
debe superar `is_current()` y coincidir con un cálculo nuevo desde el estado
actual. La desaceleración externa debe suministrarse de nuevo en ambas
comprobaciones. Los cambios de sistemas, geometría, electricidad, relojes,
combustible o movimiento se rechazan antes del pago. Si no se aporta plan,
se calcula uno vigente. `no_propulsion` e `invalid` nunca son ejecutables.

La tarifa provisional reutiliza `engine_fuel_cost()` para la ruta, con la
menor velocidad de tarificación admitida que alcance la beta inicial del
frenado. Si no hay velocidad admisible, la preparación se rechaza. Se cobra
una vez un `PropulsionAuthorization` nuevo, vinculado al segmento inmutable
de frenado de recuperación y al destino original, y se guarda en
`RecoveryExecution`. Los pagos nominal y sustitutivo anteriores permanecen
en su `InertialContinuation` anidado como historial ya gastado. El estado
físico activo no lleva un segundo recibo ni rehabilita el plan nominal. Los
formatos físicos antiguos de pickle siguen cargando y los nuevos estados
serializan la recuperación.

`Engine.tick()` ejecuta la recuperación mediante el integrador de segmentos
físicos existente. En `coast_then_brake` avanza con beta constante hasta el
punto calculado, comprueba allí la capacidad propulsiva y frena. `brake_now`
y `emergency_brake` frenan inmediatamente. El segundo conserva la posición
real más allá de B. El integrador actualiza relojes galáctico, propio y
biológico, electricidad, radiación espacial, casco, desgaste de sistemas y
mantenimiento del dron de reparación desplegado. Un tick puede cruzar la
frontera inercia→frenado; todo el intervalo solicitado se confirma una sola
vez. Los cortes eléctricos, radiológicos, de dron, trabajos o integridad de
motores no soportados rechazan el tick completo de forma atómica. Al llegar
a beta cero, la recuperación queda completada y no conserva un permiso
activo reutilizable. La carga de una partida nunca repite el cobro. La
detención no cambia el nodo público, no crea waypoint y no emite llegada.

La transición automática interna tras una reparación productiva autorizada
se describe más abajo. La nueva pérdida del umbral de frenado del 15 %
durante el frenado activo de recuperación alcanza exactamente el 15 % de
integridad, C2B2B1 registra el corte y permite continuar por inercia. Un
intervalo que sobrepase ese corte sin poder procesarse entero se rechaza de
forma atómica. Los cambios operativos no soportados antes del punto de
frenado previsto también se rechazan. Esos rechazos no cobran ni devuelven
combustible.

### Seguridad de trabajos y límite verificado de desaceleración (C2B1-R1)

Solo la continuación inercial de C1 puede ejecutar su trabajo productivo
limitado de reparación de motores mediante el scheduler causal. La ejecución
de recuperación todavía no tiene scheduler de trabajos. Por ello, la
preparación y cada tick de recuperación rechazan cualquier ID de trabajo
activo o trabajo `QUEUED` o `RUNNING`, incluidos índices incoherentes, antes
de mover la nave. Un dron desplegado sigue recibiendo su mantenimiento normal
si no hay trabajos pendientes; su presencia no autoriza omitir trabajos. En
esta fase interna, `Repair` conserva su acceso productivo y puede encolar un
trabajo después de preparar la recuperación. El siguiente tick de
recuperación se rechaza sin avanzar el trabajo, la nave, los relojes, los
eventos ni el RNG. C2B2A coordina una reparación vinculada; la activación
pública aún necesita impedir o coordinar nuevos trabajos concurrentes.

Todavía no existe un modelo independiente de rendimiento propulsivo
variable. El segmento de frenado interrumpido en `InertialContinuation`
proporciona el máximo provisional de desaceleración propia verificable. Un
valor externo positivo menor o igual puede autorizarse; uno mayor sigue
siendo solo una propuesta matemática y se rechaza antes de cobrar combustible
o instalar la recuperación. `is_current()` continúa exigiendo que se vuelva
a proporcionar el valor externo. La integridad de motores, el aislamiento y
la vía eléctrica determinan la disponibilidad operativa por separado de este
límite de magnitud. `Engine.tick()` vuelve a comprobar el límite antes de
frenar y en la transición de inercia a frenado. Los cambios de capacidad no
soportados rechazan de forma atómica todo el tick solicitado; no se aplica
empuje después de fallar la comprobación.

### Recuperación automática autorizada tras reparar (C2B2A)

`Engine.arm_inertial_recovery(state, job_id, max_capsules=...)` es una API
interna. Solo admite una reparación productiva activa de `engines`, con dron
propietario desplegado, durante una inercia física con velocidad positiva.
Guarda una `RecoveryIntent` inmutable y persistente con ID interno del trabajo,
destino original, autorización explícita, límite positivo y finito de gasto,
política de desaceleración histórica y estado pendiente. Armar solo cambia
este registro: el límite no reserva antimateria ni produce ningún cargo.
Se rechazan otro armado mientras el intento esté pendiente o utilizado y
la reutilización de una autorización cancelada.

En el instante real de finalización, el scheduler C1 integra primero la
inercia, electricidad, radiación y desgaste; luego resuelve la reparación
productiva y aplica su efecto. La intención vinculada llama entonces a
`prepare_inertial_recovery()` sobre ese estado. Se replantea desde posición
y beta reales, se comprueban capacidad de frenado, vía eléctrica y límite
histórico de desaceleración, y se recalcula la tarifa provisional. Solo si
hay antimateria disponible y el precio cabe en el límite autorizado se cobra
una vez y se instala `RecoveryExecution`. La intención pasa a `used` y conserva
el historial del frenado interrumpido. La preparación no avanza relojes,
posición, desgaste ni RNG. Un tick posterior ejecuta `_tick_recovery()` sin
otra orden ni otro cargo.

Una reparación fallida o insuficiente, aislamiento, indisponibilidad eléctrica
o de combustible, plan no ejecutable o precio superior al límite dejan intacto
el resultado productivo y marcan la intención `cancelled`; la nave sigue por
inercia. No se reintenta ni se cobra. Sin intención armada, se mantiene el
comportamiento inercial C1. Guardar y cargar conserva los estados pendiente,
utilizado y cancelado; los pickles anteriores cargan sin intención.

Si un tick sobrepasa la reparación, el tiempo restante se procesa mediante
`_tick_recovery()` en la misma simulación privada y se confirma una sola vez.
Una transición posterior no soportada revierte íntegramente ese tick, incluida
la reparación. Los trabajos concurrentes preexistentes aún provocan el rechazo
atómico del scheduler C1; si queda otro trabajo pendiente en T, se cancela
la intención y se conserva la reparación completada. La recuperación activa
mantiene el bloqueo defensivo R1 para trabajos. Antes de la navegación pública
faltan el control preventivo de nuevas órdenes, la pérdida posterior de frenado,
otros cortes temporales y la llegada y los waypoints públicos.

### Nueva autorización tras una cancelación (C2B2A-R1)

Una intención cancelada agotó su intento, aunque no pagó combustible. Si la
nave sigue en inercia física, `arm_inertial_recovery()` puede emitir una
intención nueva vinculada a *otra reparación productiva activa de motores*.
El trabajo antiguo no puede activar la nueva. Si el frenado ya está disponible
y no hace falta reparar de nuevo,
`authorize_manual_inertial_recovery(state, max_capsules=...)` emite una intención
manual distinta y sin pago. La API
existente `prepare_inertial_recovery()` vuelve a comprobar posición y beta
actuales, electricidad, capacidad de frenado, límite histórico de
desaceleración, tarifa de ruta, combustible y nuevo límite autorizado. Una
preparación manual rechazada deja pendiente esa intención;
`cancel_manual_inertial_recovery()` la termina expresamente antes de autorizar
otro límite. Ninguna de estas operaciones de autorización mueve la nave ni
consume combustible.

Cada intención tiene un número de intento creciente y un resumen acotado del
último intento cancelado (número, trabajo vinculado si existe y resultado).
La nueva emisión sustituye la intención cancelada por otro objeto inmutable;
nunca cambia el objeto anterior a pendiente. Solo una intención pendiente
puede preparar la recuperación, y la utilizada permanece vinculada al
`RecoveryExecution` pagado. Guardar y cargar conserva estas distinciones,
acepta el pickle previo de siete campos y no repite trabajos ni cargos. La
vía manual sigue siendo interna; quedan pendientes el control de admisión
público y el comportamiento de llegada.

### Segunda pérdida de frenado durante la recuperación (C2B2B1)

Durante el segmento de frenado de `RecoveryExecution`, el integrador de
desgaste existente localiza el primer cruce de `engines` al 15 %. Un tick
que termina exactamente allí confirma posición, beta residual, relojes,
electricidad, radiación y desgaste hasta ese instante. Si solicita más tiempo
y todavía no puede continuar dentro de la misma transacción, se rechaza
atómicamente. La recuperación queda `invalidated` y `replan_required`, con
`pending_transition="inertia"`; no se declara llegada.

`RecoveryInterruption` conserva una copia inmutable y acotada de la
recuperación pagada, su segmento interrumpido, tiempo local del corte,
posición, beta y causa. La recuperación guarda a su vez la primera
`InertialContinuation`, con el recibo nominal o del frenado anterior. El
segundo recibo de `PropulsionAuthorization` permanece gastado en
`RecoveryExecution` y, tras la transición, en la nueva
`InertialContinuation`. `RecoveryIntent` conserva el estado `used`. Ningún
recibo se convierte en permiso nuevo ni se devuelve antimateria.

El siguiente `Engine.tick()` crea un segmento inercial desde el corte exacto
y avanza con beta constante sin empuje ni cargo. Se mantiene el destino
original como referencia; la nave puede sobrepasarlo sin llegada, cambio de
nodo, waypoint ni enlace nuevo. El historial permanece en guardado/carga;
los pickles físicos anteriores, de hasta 14 campos, cargan sin segunda
interrupción. En C2B2B1, otra autorización y una tercera maniobra estaban
bloqueadas; C3A añadió una reparación productiva limitada y C3B1 permite la
maniobra manual descrita abajo. Siguen pendientes navegación y llegada
públicas.

### Pérdida de capacidad en la espera de recuperación (C2B2B2)

En `coast_then_brake`, la espera es inercial pero el frenado posterior ya
está pagado. El integrador de desgaste existente localiza el primer instante
en que `engines` alcanza el 15 % durante esa espera. El 35 % no cancela la
recuperación: la nave puede pasar a la banda de solo frenado, con el evento
normal de estado de motores, y seguir esperando. Un tick que termina
exactamente en el 15 % confirma solo el movimiento y los efectos físicos
previos al corte; uno que lo sobrepasa sin poder procesarse entero se
rechaza atómicamente. Si la espera pagada empieza exactamente al 15 % y el
desgaste ordinario es positivo, el corte ocurre en tiempo cero y ese mismo
tick puede continuar por inercia. La fase de frenado aún no se ejecuta.

`RecoveryCoastInterruption` distingue esta cancelación de
`RecoveryInterruption`, reservado al frenado activo. Conserva la
`RecoveryExecution` invalidada en fase de espera, el tiempo local, la
posición, beta, causa y recibo de combustible gastado. Esa ejecución guarda
la primera `InertialContinuation` y su historial. La transición pendiente
usa `pending_transition="inertia"`; en el siguiente tick se recupera la
inercia original desde el punto exacto del corte, sin tratar el frenado
planificado como ejecutado ni cobrar o reembolsar antimateria. El historial
persiste en guardado/carga; los pickles anteriores de hasta 15 campos
conservan su interpretación.

La nave conserva destino y beta, puede sobrepasar B y no produce llegada,
waypoint ni enlace nuevo. En C2B2B2, la tercera autorización estaba bloqueada;
C3A añadió un trabajo de reparación y C3B1 permite la autorización manual.
Un aislamiento, pérdida eléctrica u
otro cambio operativo no causado por el desgaste ordinario conserva el
rechazo atómico hasta disponer de coordinación causal; no se registra como
un falso corte de integridad. Quedan pendientes replanteamiento posterior,
control de admisión público y llegada pública.

### Reparación productiva durante la segunda inercia (C3A)

Tras `RecoveryInterruption` o `RecoveryCoastInterruption`, el scheduler causal
de C1 puede activar y resolver un único `REPAIR_SYSTEM` de `engines` con dron
interior válido. Antes de avanzar, verifica el historial físico, la intención
ya utilizada y la coherencia entre trabajos `QUEUED`/`RUNNING` e índice activo.
Reutiliza `_begin_job_interval()`, los límites de finalización, la integración
física, electricidad, radiación y mantenimiento del dron, y aplica el efecto
productivo solo al concluir el trabajo. Un trabajo de ETA cero puede resolverse
en el instante actual sin reactivar la `RecoveryExecution` invalidada.

La reparación puede fallar conforme al riesgo productivo o mejorar la
integridad después del desgaste anterior. En ambos casos la nave mantiene
beta, destino y trayectoria inercial. No se cobra ni autoriza propulsión;
`RecoveryIntent` permanece `used`, y ambos tipos de interrupción conservan
la primera historia y el recibo de la recuperación. La simulación privada
revierte el tick entero si un límite eléctrico, radiológico, de dron, de
trabajos o narrativo posterior no puede coordinarse. Guardar/cargar no repite
el resultado ni el RNG. También se admite reparar después de sobrepasar B,
sin llegada ni cambio de nodo.

C3B1 introdujo el linaje acotado y el pago manual descritos a continuación.

### Tercera recuperación autorizada manualmente (C3B1, C3B1-R1)

Tras la segunda interrupción, una reparación de motores terminada y aplicada
por el scheduler productivo **después del corte**, junto con la capacidad
actual de frenado, permite una nueva `RecoveryIntent` manual.
Tiene un identificador monótono nuevo y un límite de gasto positivo y finito.
Armarla no descuenta combustible. `prepare_inertial_recovery()` verifica
`RecoveryPlan`, relojes, ruta, electricidad, trabajos, desaceleración
conservadora y combustible actuales, y descuenta una sola vez la tarifa
existente de `engine_fuel_cost()`. La nueva `PropulsionAuthorization` queda
ligada a un segmento de frenado y al destino original. Una desaceleración
manual puede ser inferior a la demostrada históricamente, nunca superior.
Un frenado planificado y abandonado durante la espera no demuestra capacidad;
el frenado anterior ejecutado sigue siendo el límite. La capacidad se vuelve
a comprobar antes de iniciar la fase propulsiva.

`RecoveryLineage`, en `src/retorno/core/nav_state.py`, conserva origen y
destino originales, cantidades de recuperaciones pagadas e interrumpidas,
antimateria acumulada gastada en recuperaciones, identificador máximo ya
gastado y una ventana fija de **dos** `RecoveryAttemptRecord` detallados.
Cada registro contiene recibo gastado de segmento, identificador, resultado,
tipo de interrupción y estado físico del corte cuando corresponde. Los
registros antiguos se resumen en acumulados y una huella SHA-256
determinista. La huella no equivale a un registro de auditoría reconstruible;
conservar todos los recibos exigiría un libro persistente separado. El linaje
nunca determina posición, beta ni relojes actuales: eso corresponde al
segmento físico activo. No pueden reutilizarse identificadores hasta
`spent_through_authorization_id`.

Siguen cargándose los formatos físicos anteriores de 8–17 campos y las
intenciones de 7 o 9 campos. El linaje se crea solo al preparar el nuevo
pago: incorpora el recibo y corte validados de la segunda interrupción sin
mover la nave, modificar relojes, reembolsar combustible ni activar una
intención antigua. C3B1 infería la segunda reparación a partir de dos trabajos
de motores terminados y distintos. Ambos podían preceder al segundo corte,
por lo que su cantidad no acredita causalidad. C3B1-R1 registra una
`SecondRepairEvidence` inmutable solo cuando `_tick_inertial()` resuelve un
trabajo `REPAIR_SYSTEM` de `engines` satisfactorio y mejora realmente la
integridad. La evidencia vincula ID interno, secuencia terminal, instante
galáctico de terminación, integridad anterior y posterior, tipo de
interrupción, estado físico del corte y recibo de recuperación ya gastado.
Al autorizar se comprueban de nuevo el trabajo terminado y la capacidad
actual de frenado; la evidencia por sí sola no autoriza propulsión ni cobra
combustible. No puede asociarse a otra interrupción. Los trabajos fallidos,
cancelados, pendientes, en curso o de otros sistemas no sirven de prueba.

Un estado inercial sin evidencia vigente de reparación no puede recibir una
nueva autorización manual ni pagar una recuperación. El rechazo conserva
combustible, movimiento, relojes, trabajos, drones, eventos y RNG.

La vía existente de `Engine.tick()` ejecuta frenado inmediato, espera seguida
de frenado y sobrepaso inevitable. Puede cruzar el límite espera/frenado en
una sola transacción privada. Al detenerse, marca como terminado el último
registro acotado. C3B2 extiende esta vía a cortes sucesivos.

### Ciclo de recuperaciones manuales sucesivas (C3B2)

Toda recuperación pagada puede perder la capacidad de frenado en el límite
de desgaste del 15 %, durante el frenado o durante una espera ya pagada. La
ejecución interrumpida y su recibo permanecen gastados. Un corte con velocidad
residual actualiza el último registro de `RecoveryLineage` a
`interrupted_brake` o `interrupted_coast`, conserva el `MotionState` exacto,
invalida la ejecución actual y comienza la continuación inercial sin salto de
posición, beta ni relojes. Un frenado que alcanza beta cero se marca terminado,
sin interrupción ficticia. Una espera pagada que empieza justo al 15 % puede
cortarse en tiempo cero. El corte no declara llegada ni crea waypoint, aunque
se haya sobrepasado el destino.

La `RecoveryInterruption` o `RecoveryCoastInterruption` actual es la única
interrupción detallada fuera de la ventana de dos registros del linaje. El
nombre existente `SecondRepairEvidence` pasa a designar la prueba del **corte
actual**: el scheduler productivo registra una reparación satisfactoria de
motores con mejora real de integridad, secuencia terminal e instante de
terminación al procesar el estado inercial posterior al corte. Una reparación
de ETA cero puede compartir el instante galáctico del corte porque el
scheduler la resuelve después de este. La preparación consume la evidencia,
añade un registro pagado y elimina la interrupción y la evidencia vigentes.
Por ello, el corte siguiente no puede reutilizar una reparación anterior.
Cancelar una autorización manual pendiente conserva la evidencia y aumenta
el próximo ID de autorización. Los ID pagados siguen gastados cuando sus
registros detallados salen de la ventana.

`InertialContinuation.interrupted_segment` conserva el último frenado
**ejecutado**. Un corte durante una espera pagada traslada ese frenado previo;
un frenado planificado pero no ejecutado nunca eleva el límite de
desaceleración demostrada. `plan_inertial_recovery()` y la preparación usan
ese segmento como valor predeterminado y máximo físico, respectivamente,
también tras expulsar del linaje el registro detallado original.
`RecoveryLineage` conserva acumulados de antimateria pagada, intentos e
interrupciones, ID máximo gastado y una huella encadenada con un máximo de dos
registros detallados. No determina el movimiento ni los relojes actuales.

El planificador, integrador físico, scheduler de trabajos y tarifa única de
combustible existentes ejecutan cada ciclo. Autorizar no cobra; preparar con
éxito cobra una sola vez. Los ticks trabajan sobre un estado privado y solo
confirman al resolver todos los límites admitidos; un límite eléctrico,
radiológico, de dron, trabajo o narrativo posterior revierte conjuntamente
movimiento, evidencia de reparación, combustible, eventos y RNG. Guardar y
cargar la versión actual conserva fases pendientes, interrumpidas, reparadas,
autorizadas, pagadas y terminadas, incluido el avance de la ventana. Durante
el desarrollo experimental no se promete migración ni compatibilidad con
esquemas de guardado anteriores; las cargas incompatibles deben fallar con
claridad. El código de compatibilidad existente fuera de este ciclo no es
una restricción de diseño para formatos futuros.

Siguen vigentes los límites operativos: capacidad real de frenado,
electricidad, geometría, relojes, trabajos, vigencia del plan, desaceleración
demostrada, antimateria disponible y techo de gasto autorizado. Los límites
causales no soportados y trabajos incompatibles aún se rechazan atómicamente.
Quedan fuera de esta fase llegada pública, waypoints de detención, destinos
nuevos, aceleración durante el tránsito y recuperación automática sucesiva.
El siguiente bloque de navegación tratará llegada física, sobrepaso y
waypoint de detención.
