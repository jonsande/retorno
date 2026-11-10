# T-04B1 — electricidad ordinaria en tiempo propio de la nave

Implementado el 2026-11-10 después de T-04A. El código responsable está en
`src/retorno/core/engine.py`; `core/temporal.py` sigue siendo el único cálculo
de intervalos relativistas. Se mantienen potencias, capacidades, eficiencias,
umbrales y reglas de apagado automático configurados.

La generación de `power_core` y la demanda eléctrica de sistemas/trabajos son
kW a bordo. La batería de la nave almacena kWh.
`Engine._integrate_power_interval(state, dt_ship)` usa segundos a bordo para
carga/descarga, `low_q_shed_timer_s` y `brownout_sustained_s`. Conserva límites
de potencia de carga/descarga, eficiencias, topes de capacidad, calidad y
apagados instantáneos. Generación y demanda son kW instantáneos, sin aplicar
un multiplicador de velocidad a la potencia. Solo cambia el intervalo de
integración. En reposo equivale al intervalo galáctico, incluso con perfil CRUISE.

`Engine._tick_interval` reutiliza los intervalos ya calculados para el reloj
de nave. El movimiento interestelar usa `transit_speed_ly_per_year` congelado
por T-04A, incluso tras daño, reparación o cambios de configuración. El viaje
local usa los 20 km/s existentes. Hibernar no multiplica la energía eléctrica
por la tasa separada de envejecimiento biológico.

Cada tramo eléctrico conserva el orden de muestreo de generación, cálculo de
carga y apagados, temporizador de baja calidad, integración de batería y
actualización de calidad/persistencia del brownout. Sin llegada, sigue en el
mismo punto del tick, después de jobs y scheduler de lore. Se conserva el
muestreo inicial de generación; no se reprograman trabajos ni se reconstruyen
sus instantes de finalización dentro de un intervalo.

Si un tick alcanza o atraviesa una llegada, la electricidad tiene dos tramos:

1. Integra el tiempo propio en movimiento con el estado eléctrico en vuelo,
   antes de que los efectos de llegada o finalización de trabajos lo sustituyan.
2. Procesa llegada, trabajos y llamadas de lore/recuperación una sola vez, en
   su orden galáctico existente. Refresca generación para el estado resultante
   e integra el resto en reposo, donde segundos propios y galácticos coinciden.

En la llegada exacta, el segundo tramo dura cero. Refresca telemetría/regulación
final sin cargar ni descargar energía por ese tramo. Un cambio de generación o
consumo en la llegada no puede aplicarse al tránsito anterior. El integrador
eléctrico no invoca el scheduler narrativo, avanza relojes, procesa trabajos,
cambia ubicación, aplica desgaste ni mantiene drones. No hay bucle por segundo.
Se conservan las fronteras existentes de decisión de drones en `Engine.tick`;
T-04B2 reutiliza también estos tramos para desgaste ordinario de sistemas/casco. Los
eventos eléctricos mantienen la marca galáctica del tick que los contiene.

`clock.t`, `last_dt`, ETA, eventos históricos, narrativa y radio siguen siendo
galácticos. T-04B2 convierte [desgaste ordinario de sistemas/casco](wear-proper-time.es.md)
a tiempo propio sin cambiar esta política eléctrica. Trabajos, reparaciones,
radiación, consumo/carga/mantenimiento de drones y reglas de soporte vital/
hibernación siguen recibiendo una vez su intervalo galáctico existente. El cobro de
antimateria y las reglas de aborto no cambian. Los guardados nuevos persisten
valores y temporizadores eléctricos existentes sin campos nuevos, migraciones
ni cambios de formato.

Se explicitan las dependencias y límites existentes:

- Brownout sostenido y calidad eléctrica siguen alimentando el modelo de
  desgaste. El umbral de persistencia se mide a bordo. T-04B2 mide también a
  bordo el intervalo de desgaste y conserva sus multiplicadores de calidad/
  brownout. Estas muestras pueden activar consecuencias en otro momento galáctico.
- Trabajos y soporte de drones ya consultan disponibilidad eléctrica. La energía
  distinta puede cambiar admisión/soporte, pero no convierte sus duraciones,
  consumo ni mantenimiento. No se añade coste eléctrico para drones.
- Reconstruir continuamente instantes de batería vacía/llena, transiciones de
  trabajos y umbrales repetidos de apagado dentro de un tick largo queda fuera.
  Se conserva la política muestreada existente. La equivalencia entre intervalos
  largos/cortos se prueba con circuitos estables sin esas transiciones.
- Las previsiones de recuperación de `core/deadnode_opportunities.py` conservan
  sus estimaciones aproximadas de energía por duración galáctica. No son el
  integrador activo y no se migran ni se usan como referencia energética exacta.

Las lecturas eléctricas CLI/Textual conservan comandos y unidades. Los manuales
bilingües explican kW/kWh y temporizadores a bordo; no hacen falta cambios de
sintaxis de help ni de textos de eventos. Pruebas y resultados:
[validación](../testing/electrical-proper-time-review.es.md).
