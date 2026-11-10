# T-04B2 — desgaste ordinario de sistemas y casco en tiempo propio

Implementado en `main` desde `1b963ea` (T-04A, T-04B1, CANON v0.6.0).
Código responsable: `src/retorno/core/engine.py`, en `_tick_interval`,
`_apply_degradation` y `_apply_hull_degradation`. Los intervalos relativistas
siguen procediendo exclusivamente de `core/temporal.py`.

La pérdida ordinaria de `ShipSystem.health` y el envejecimiento ordinario del
casco usan segundos propios. En reposo usan el intervalo galáctico; en tránsito
usan la velocidad ya congelada y el intervalo del reloj, nunca una velocidad
recalculada desde la salud actual de engines. La velocidad local existente
alimenta ese mismo cálculo. No se añade multiplicador por velocidad. Se
conservan las tasas base, interpretadas ahora por segundo propio en estas dos
rutinas de envejecimiento.

Se conservan los modificadores existentes:

- Penalización `k_power` por calidad e `k_rad` por radiación interna normalizada.
- Multiplicadores de brownout sostenido para power_core y energy_distribution.
- Multiplicador de sistemas en tránsito NORMAL; CRUISE conserva su comportamiento.
- Modificador ambiental de casco y su factor existente de tránsito o hibernación.
- Bandas de salud, bloqueos de estado, aislamiento forzado, protección god y
  transiciones de engines según salud/módulos.

Al llegar se reutilizan las duraciones de movimiento y reposo de T-04B1.
Después del tramo eléctrico en movimiento, antes de llegada/jobs, se conserva
su calidad eléctrica final, booleano de brownout sostenido, modo operativo,
muestra ambiental y muestra interna filtrada por casco. La segunda muestra usa
el estado eléctrico final en reposo y las lecturas ambiental/interna finales.
El desgaste se aplica en orden de tramos, en su punto original del tick,
después de jobs, narrativa e integración eléctrica. Los argumentos explícitos
de tránsito/modo conservan los modificadores del movimiento aunque la nave ya
haya llegado. El resto en reposo solo se aplica si es positivo; una llegada
exacta no produce una pasada adicional de desgaste de duración cero.

Sin llegada hay una sola pasada con el intervalo propio completo y las mismas
muestras de calidad/brownout/entorno al terminar la electricidad que antes.
La persistencia del brownout ya usa segundos a bordo en T-04B1. No se cambia
ningún temporizador ni fórmula eléctrica. Las transiciones de salud conservan
la marca galáctica del tick. El deterioro afecta a operaciones posteriores;
no recalcula retroactivamente electricidad del tick, velocidad congelada,
llegada ni intervalo de reloj propio. La generación del tick siguiente refleja
un reactor reducido por este desgaste.

Se conserva deliberadamente el muestreo grueso:

- Cada tramo usa su calidad final y condición final de brownout sostenido para
  toda su duración. No se reconstruyen cruces de umbrales dentro del tramo.
- Jobs/reparaciones conservan su programación galáctica anterior al desgaste;
  no se reproducen sus instantes de finalización ni saludes intermedias. Se
  desgastan los sistemas disponibles en esa fase, con sus tasas/coeficientes.
- La radiación ambiental sigue siendo puntual. La interpolación usa el reloj
  ya avanzado del tick; al alcanzar/atravesar la llegada se limita a radiación
  de destino incluso para la muestra de movimiento. No distingue con precisión
  exposición del corredor y condiciones de llegada. Ambas muestras internas
  usan el blindaje previo al desgaste diferido del tick; no se integra de forma
  continua la exposición ni el blindaje.
- Se comprueba equivalencia entre intervalos largos/cortos en condiciones
  estables. Calidad muestreada, umbrales, reparaciones o radiación cambiante
  pueden seguir produciendo diferencias entre ticks gruesos y subdivididos.

El daño instantáneo de `_damage_hull` y la dosis de `_apply_radiation` no cambian.
No se inventa flujo relativista externo, daño de medio interestelar ni modelo
radiológico nuevo. Consumo, integridad, carga, descontaminación y mantenimiento
de drones conservan su dominio anterior. Trabajos, reparaciones, temporizadores
de soporte vital, reglas de hibernación, eficacia biológica, narrativa, radio,
worldgen y recuperación no cambian ni se invocan dos veces por estos tramos.
No se añade bucle por segundo, campo de guardado ni migración.

El deterioro de engines sigue produciendo LIMITED/DAMAGED/CRITICAL y puede
bloquear futuras salidas. Se conservan módulos/velocidades de T-04A y precio de
antimateria. No se implementan `engines speed`, escalera de consumo ni techos
nuevos para motores dañados mejorados previstos en v0.6.0. No cambia el balance
ni la disponibilidad de recursos.

Se cierra la discrepancia concreta de envejecimiento de sistemas/casco de
A-TECH-005 respecto a C-TIME-003. Su descripción del estado de implementación
debe actualizarse mediante mantenimiento canónico; maniobras locales,
aceleración/frenado y cambios de velocidad en ruta siguen abiertos. Se deja
`docs/canon/universo.md` intacto. Los manuales EN/ES distinguen envejecimiento
y dosis. No hacen falta comandos, sintaxis de help ni textos de eventos nuevos.

Véanse [validación](../testing/wear-proper-time-review.es.md) y
[contrato eléctrico](electrical-proper-time.es.md).
