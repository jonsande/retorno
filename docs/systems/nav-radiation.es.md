# Predicción radiológica del tránsito físico (NAV-BRAKE-01B3F)

`src/retorno/core/nav_radiation.py` es una predicción pura y condicional para
las posiciones unidimensionales de `MotionSegment` en `nav_physics.py`. El
tránsito físico sigue protegido en `Engine.tick()`; este módulo no cambia el
viaje público, las alertas, la hibernación ni la persistencia. La ruta jugable
anterior interpola la radiación ambiental según la ETA transcurrida en
`_compute_env_radiation_rad_per_s()`; 01B3F usa los metros realmente recorridos.

## Modelo espacial y relojes

`RadiationProfile(A_m, B_m, A_rad_per_s, B_rad_per_s)` es inmutable y exige
`B_m > A_m` y tasas no negativas en ambos extremos. Entre A y B la radiación
ambiental varía linealmente con la posición física. Antes de A conserva la tasa
de A; después de B conserva la de B, incluso si se sobrepasa el destino o la
nave se detiene más allá. Esta regla de extremos es provisional y no simula
todo el medio interestelar. El segmento expresa posición en metros; la
conversión desde años luz utiliza `LIGHT_YEAR_M` de `nav_physics.py`. El perfil
nunca reconstruye posición desde un plan con salida en reposo o una ETA
nominal. Sustituir un segmento continuo por otro en la misma posición no
provoca por tanto un salto de radiación ambiental.

Las tasas se expresan en rad/s y la dosis integrada en rad.
`integrate_segment_radiation()` acepta cualquier subintervalo de tiempo
galáctico relativo de un segmento y la integridad inicial del casco en ese
subintervalo. Devuelve dosis ambiental tanto en tiempo galáctico como propio,
dosis interna en tiempo propio e integral del factor radiológico normalizado de
desgaste en segundos propios. El desgaste ordinario de casco y sistemas usa
tiempo propio. La dosis productiva de drones sigue usando tiempo galáctico y
el factor de blindaje del dron; esta predicción no aplica efectos al dron.

## Acoplamiento de casco y radiación interna

`internal_radiation_rate()` y `hull_decay_rate()` son las mismas funciones puras
que utilizan `Engine._compute_internal_radiation_rad_per_s()` y
`Engine._apply_hull_degradation()`. La pérdida de casco por segundo propio es
la tasa base por `1 + (HULL_RAD_DECAY_MULT_MAX - 1) * clamp(env/HULL_RAD_REF)` y
el multiplicador existente de tránsito o hibernación. Se detiene en integridad
cero; God mode mantiene el casco fijo. La entrada radiológica es lineal en
`1 - casco_actual` entre sus límites existentes, por lo que la radiación interna
usa el casco de cada instante, nunca el casco final retroactivamente. God mode
conserva tasas y dosis físicas de radiación, pero no reduce la integridad de
casco o sistemas.

El integrador divide en A, B, la saturación radiológica del casco y el instante
en que el casco llega a cero. En cada rama, `MotionSegment` aporta posición y
tiempo propio; fórmulas hiperbólicas cerradas integran la dosis ambiental propia
y su primer momento temporal. La pérdida ordinaria del casco y la dosis interna
se obtienen algebraicamente e incluyen el cambio de entrada radiológica a
medida que se deteriora el casco. Una inversión acotada de posición o casco
resuelve las ramas hasta la resolución de coma flotante. No hay pasos fijos de
un segundo. `integrated_system_wear()` combina una integral de calidad aportada
por el consumidor con la integral radiológica interna normalizada mediante
valores base de `ordinary_wear_rate()`; devuelve una pérdida calculada y no la
aplica.

La dosis ambiental galáctica bajo aceleración y radiación variable, y el
factor radiológico interno recortado, usan Simpson adaptativo determinista.
El consumidor aporta tolerancias absoluta y relativa positivas (por defecto
`1e-8` y `1e-10`); el algoritmo suma estimaciones de error a posteriori,
comprueba la suma frente a la tolerancia solicitada y
lanza excepción si no se satisface la estimación solicitada o se agota la
resolución numérica/profundidad. Estas estimaciones controlan el cálculo, pero
no son cotas superiores matemáticas certificadas. Las pruebas comparan con
una referencia independiente de puntos medios finos y casos exactos constantes
o inerciales. Un adaptador productivo futuro debe tratar el fallo de
convergencia como corte obligatorio y decidir si el movimiento propulsado
exige una cota certificada.

## Límites condicionales e invalidez

`environmental_limits()` predice cruces ambientales elevado/alto/extremo,
saturación radiológica del casco y umbral ascendente de despertar si se solicita
hibernación. `radiation_limits()` añade casco cero e internos
elevado/alto/extremo y saturación de desgaste, incluso cuando la radiación
ambiental baja mientras aumenta el ingreso por deterioro del casco. Divide en
A, B, saturación del deterioro y casco cero. En cada rama suave, para la tasa
interna `R=E*I`, se cumple `E' = pendiente_espacial*c*beta*gamma` e
`I' = amplitud_ingreso*hull_decay_rate(E)` hasta casco cero (o cero en God
mode). Los rangos de extremos de `E`, `I`, `E'` e `I'` acotan el producto y su
derivada en la rama. La cota del producto puede excluir un umbral; la de la
derivada puede demostrar una dirección de cambio y entonces una bisección
acotada localiza el primer cruce. Se subdividen primero los intervalos más
tempranos, de modo que ninguna raíz posterior oculte un intervalo anterior
indeterminado. Los campos constantes antes de A y después de B se reconocen
por su pendiente local nula aunque el perfil global sea decreciente. Los
límites calculables son `TemporalLimit` en tiempo propio;
`select_next_boundary()` los convierte con el segmento activo y conserva
simultaneidades y límites diferidos.

La aritmética de intervalos usa coma flotante ordinaria y amplía las cotas un
ULP hacia fuera; **no constituye una cota matemática certificada**. Solo se
acepta una raíz candidata si las tasas cercanas separan el umbral por 64 ULP.
La comprobación comienza al mayor de 1024 ULP temporales y `1e-12` del
segmento restante y puede ampliarse. Si no se puede decidir una rama tras 48
bisecciones, 8192 nodos o sin progreso representable en tiempo propio, se
devuelve `time_s=None` con causa explícita de incertidumbre. Un contacto
tangencial en un máximo interior, incluido el umbral exactamente igual al
máximo, puede quedar diferido. Un umbral algo superior al máximo puede
excluirse; uno algo inferior puede producir el primero de dos cruces. No hay
muestreo fijo por segundos ni tiempos inventados. El movimiento productivo
deberá detenerse ante un límite diferido hasta disponer de una cota certificada
u otra resolución válida.

Las clasificaciones radiológicas productivas usan `>=`. Una tasa inicial a
menos de dos ULP del umbral se trata como igualdad para absorber el redondeo
del producto entre tasa del extremo e ingreso; es una heurística numérica, no
un cambio del clasificador productivo. En una igualdad
ascendente la categoría nueva ya se cumple. En igualdad descendente, la
categoría inferior comienza solo en el lado posterior: se devuelve
`post_crossing_check` en cero. Tras procesarlo,
`resolve_radiation_limit()` produce una marca ligada al perfil, segmento,
instante, integridad del casco y condiciones operativas. Devolverla al
predictor con la misma instantánea elimina solamente ese cero. Las llamadas
directas a `environmental_limits()` deben aportar `hull_integrity` y las
condiciones operativas al reutilizarla. Una reparación, daño, cambio de
hibernación o God mode, nuevo perfil o segmento, o avance temporal hacen que
la marca anterior ya no sea aplicable. Corte matemático, cambio de clasificación,
alerta futura y despertar de hibernación son hechos distintos; el predictor no
emite notificaciones. Las mesetas fuera de los extremos no generan cruces
descendentes ficticios.

`radiation_invalidation_reasons()` detecta cambios de perfil o segmento,
integridad de casco o posición física inesperadas y cambios en las condiciones
operativas (`in_transit`, `hibernating`, `god_active`) respecto a las previstas.
El consumidor debe proporcionar las instantáneas de posición y operación para
comprobarlas y repetir la consulta tras cambios de destino o radiación de los
extremos, interrupción de segmento, reparación o daño extraordinario del casco.
Ninguna consulta modifica `GameState` ni consume RNG.
Antes de activar el movimiento físico, el futuro adaptador causal debe combinar
estos límites y las integrales propias de desgaste con la calidad eléctrica,
integridad de motores y límites galácticos de trabajos, resolver efectos
simultáneos y replantear desde posición y velocidad reales. Los límites
internos diferidos cerca de tangencias o del límite de resolución numérica
aún necesitan cotas certificadas de raíces antes de activar el movimiento.
Reserva de combustible y frenado
de emergencia son dependencias independientes. Cruzar B no es una llegada
satisfactoria y no crea waypoint.
