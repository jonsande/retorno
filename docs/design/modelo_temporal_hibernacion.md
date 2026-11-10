> **Nota histórica 4D-3e5b — convención inicial de radio / historical initial radio convention.**
> `radio_coordinate_time(state)` usa provisionalmente `state.clock.t` como segundos
> de coordenadas galácticas desde t=0; `game-coordinate-seconds-v1` identifica la
> referencia persistida y `Balance.YEAR_S` el año de 365 días. Offsets negativos
> son relativos al inicio. No cambia ninguno de los consumidores actuales de
> tiempo ni implementa tres relojes. El futuro adaptador deberá conservar identidad
> y significado de las emisiones. / `radio_coordinate_time(state)` provisionally
> uses clock.t as galactic coordinate seconds since t=0, with persisted
> game-coordinate-seconds-v1 reference and the engine's 365-day year. Negative
> offsets are game-relative. No existing time consumer changes; three clocks
> remain unimplemented. A future adapter must preserve emission identity/meaning.
> [ES](../systems/radio-spacetime.es.md) · [EN](../systems/radio-spacetime.md).

# RETORNO — Modelo temporal, hibernación y edad biológica

> **T-04B1 (2026-11-10), electricidad implementada / implemented electricity:**
> Generación y demanda son kW a bordo; batería en kWh. Integración y temporizadores
> de regulación eléctrica usan tiempo propio, con tramos separados en la llegada.
> Los demás consumidores conservan el intervalo galáctico y su frecuencia de llamadas.
> / Generation and demand are onboard kW; storage is kWh. Electrical integration
> and regulation timers use proper time, with separate legs at arrival. Other
> consumers retain their galactic interval and call cadence.
> [ES](../systems/electrical-proper-time.es.md) · [EN](../systems/electrical-proper-time.md).

> **T-04A (2026-11-09), velocidad inercial implementada / implemented inertial speed:**
> El atributo de crucero es ahora referencia nominal; `effective_cruise_speed()`
> aplica el estado de engines y el módulo independiente de velocidad. Cada salida
> congela `transit_speed_ly_per_year` para ETA y tiempo propio hasta llegada/aborto.
> Daño, reparación o módulos posteriores no cambian el trayecto en curso.
> / The cruise attribute is now the nominal reference; effective speed follows
> engine state and the independent speed module. Departure freezes the transit
> speed for ETA and proper time until arrival/abort. Later damage, repair or
> module changes cannot change the active journey. Local travel remains 20 km/s.
> [ES](../systems/engines-antimatter.es.md) · [EN](../systems/engines-antimatter.md).

> **T-03 (2026-11-08), núcleo implementado / implemented core:**
> `ClockState.t` y `last_dt` conservan segundos galácticos; `ship_elapsed_s` y
> `bio_elapsed_s` empiezan en cero y se persisten en guardados nuevos, sin migración.
> `core/temporal.py` calcula `dt_ship = dt_galactic * sqrt(1 - beta²)`, con
> velocidad finita `0 <= beta < 1`. En reposo `beta=0`; en tránsito interestelar
> se usa la velocidad congelada de salida (T-04A); en viaje local, `20 / 299792.458`.
> `Engine.tick` separa movimiento hasta llegada y reposo posterior únicamente
> para estos acumuladores. La edad suma tiempo propio despierto o lo multiplica
> por `Balance.HIBERNATION_BIO_AGE_RATE_NOMINAL` (0.005) hibernando.
> / `t` and `last_dt` retain galactic seconds; the two new accumulators start at
> zero and persist in new saves, without migration. Proper time uses the formula
> above and rejects invalid speeds. Rest uses zero speed, interstellar transit
> uses the frozen departure speed (T-04A), and local transit uses 20 km/s divided by c. Arrival
> splits moving/rest intervals for clocks only. Biological ageing equals proper
> time awake, or proper time times the configurable nominal rate when hibernating.
>
> **Pendiente tras T-04B1 / pending after T-04B1:** trabajos, desgaste y demás
> consumidores no eléctricos conservan su tiempo galáctico actual. Una emergencia detectada al final de un
> bloque de hibernación aún contabiliza todo el bloque como hibernado; no se
> reconstruye el instante físico del fallo ni se cambia el margen de 300 s.
> Eficacia según `life_support`, interfaces y gravedad quedan pendientes.
> / Non-electrical consumers retain galactic time. An emergency detected at a block's
> end still counts the whole block as hibernation; the physical failure instant
> is not reconstructed and the 300-second grace is unchanged. Life-support
> effectiveness, clock displays and gravity remain pending.
>
> El resto del borrador conserva las propuestas y auditorías históricas;
> esta nota identifica el alcance implementado. / The remaining draft retains
> historical proposals and audits; this note identifies implemented scope.

> **T-02 (2026-11-08), actualización implementada / implemented update:**
> `ShipState.cruise_speed_ly_per_year` inicia ahora en `0.5`; navegación y
> estimaciones usan ese atributo. El viaje local sigue a 20 km/s. No se añaden
> relatividad, relojes ni cambios de hibernación. Las referencias inferiores a
> `1.0` describen la auditoría histórica anterior. / The ship attribute now
> defaults to `0.5`; navigation and estimates use it. Local travel remains at
> 20 km/s. No relativity, clocks or hibernation changes are introduced. References
> to `1.0` below describe the earlier historical audit.

**ID:** `RET-DESIGN-TIME`  
**Versión:** `0.1.0` (borrador de diseño, sin implementación)  
**Fecha:** 2026-11-05  
**Estado:** propuesta técnica para discusión y validación  
**Referencia canónica:** [`../canon/universo.md`](../canon/universo.md)  
**Guía operativa:** [`../canon/guia_coherencia.md`](../canon/guia_coherencia.md)

> Este archivo organiza requisitos, fórmulas candidatas y pruebas para un desarrollo posterior. **No modifica el comportamiento actual del juego ni aprueba automáticamente nombres de comandos o fórmulas no decididas.**

## 1. Separar decisiones firmes, valores de balance e incógnitas

| Aspecto | Estado | Valor o requisito |
|---|---|---|
| Viaje de naves masivas | Establecido | Siempre sublumínico. |
| Tres magnitudes temporales | Establecido | Tiempo galáctico, tiempo propio de nave, envejecimiento biológico acumulado. |
| Inicio del tiempo galáctico | Establecido | `T=0` al crear partida. |
| Hibernación | Establecido | Conservación química avanzada, ralentiza sin detener completamente envejecimiento. |
| Dependencia de `life_support` | Establecido | Un sistema degradado puede empeorar eficacia; tasa efectiva consultable. |
| Edad biológica | Establecido | Recurso finito, sin límite/muerte mecánica definidos. |
| Agujeros negros y dilatación gravitatoria | Establecido como objetivo futuro | Necesidad de compatibilidad arquitectónica, no de implementación inmediata. |
| Crucero | Provisional | `0.5 c` (0,5 años luz por año galáctico, sin aceleración). |
| Tasa nominal de hibernación | Provisional | `0.005` (0,5 % del tiempo propio). |
| Tasa despierto | Provisional / referencia natural | `1.0` año biológico por año propio. |
| Grandes hitos narrativos | Provisional | Orden de 200 años galácticos, no frecuencia obligatoria. |
| Fórmula `life_support` → eficiencia | Abierto | Determinar tras pruebas de equilibrio y viabilidad. |
| Químicos: inventario, dosis, agotamiento | Abierto | Necesitan contrato independiente si se vuelven recursos jugables. |
| Edad de inicio, vida máxima, efectos de salud | Abierto | No inferir un límite mortal ni una mecánica médica automática. |
| Gravedad intensa, órbitas, radiación | Abierto | Modelo relativista y peligros físicos en una fase futura. |

## 2. Estado técnico verificado como punto de partida

A la fecha de redacción, según inspección de la rama `main` del repositorio `jonsande/retorno`:

- `src/retorno/core/gamestate.py`: `ClockState.t` cuenta segundos desde inicio; no hay tres magnitudes temporales separadas.
- `src/retorno/model/ship.py`: `cruise_speed_ly_per_year` vale `1.0` en la clase de estado; hay `is_hibernating`, `life_support_offline_s` y estados de sistemas.
- `src/retorno/core/engine.py`: calcula años de tránsito `distance_ly / cruise_speed_ly_per_year`; la degradación de subsistemas utiliza un `dt` sin corrección explícita del tiempo propio.
- `src/retorno/config/balance.py`: contiene `HIBERNATE_CHUNK_S`, los umbrales de salud de sistemas y parámetros de desgaste, pero no la nueva ratio nominal de edad biológica.
- `life_support` ya participa en la supervivencia técnica y puede estar `OFFLINE`. Eso **no** constituye aún una fórmula de envejecimiento del personaje.

La auditoría deberá repetirse antes de escribir cambios: el código puede haber evolucionado.

## 3. Contrato conceptual de los tres relojes

### A. Tiempo galáctico transcurrido

- Recurso de simulación para cronología externa; inicia en `0` por partida y avanza monótonamente.
- Debe servir como referencia de eventos históricos, antigüedad de documentos y procesos externos.
- No constituye un «presente simultáneo absoluto» en relatividad general; se trata de una convención de coordenadas para el mundo jugable.
- **Propuesta de compatibilidad:** mantener `state.clock.t` como tiempo galáctico, siempre que una auditoría de consumidores confirme que la semántica es compatible.

### B. Tiempo propio de la nave

- Acumula el tiempo que transcurre físicamente a bordo durante reposo, movimiento y, en el futuro, regiones de gravedad intensa.
- Debe alimentar desgastes, ciclos y temporizadores **locales** que tengan significado físico a bordo.
- Debe avanzar monótonamente, sin superar el intervalo galáctico en el caso sencillo de un marco de referencia inercial elegido y velocidades sublumínicas, y sin depender de la hibernación de la persona.
- Se necesita resolver qué temporizadores actuales son **galácticos** y cuáles son **propios**; no sustituir `dt` por otro valor de forma indiscriminada.

### C. Envejecimiento biológico acumulado

- Acumula una cantidad de edad fisiológica desde el comienzo de la partida (no presupone una edad inicial de personaje todavía indeterminada).
- Avanza según el **tiempo propio**, el estado de vigilia/hibernación y la eficacia de la conservación.
- La edad biológica no sustituye al tiempo de experiencia consciente ni se identifica con las horas que el jugador ha pasado despierto.
- No retrocede automáticamente por reparaciones del sarcófago; la posibilidad de tratamientos rejuvenecedores **no** está decidida.

## 4. Fórmulas candidatas y ejemplo numérico

### Cinemática simple para el primer modelo

En un marco galáctico aproximado, sin campo gravitatorio fuerte y sin aceleración:

```text
v_c = velocidad_de_nave / velocidad_de_la_luz
factor_propio = sqrt(1 - v_c**2)
dt_nave = dt_galactico * factor_propio
```

A `0.5c`: `factor_propio = sqrt(0.75) ≈ 0.8660254`.

Para un tramo de **200 años galácticos** con crucero constante a `0.5c`:

- Tiempo galáctico: `200 años`.
- Tiempo propio a bordo: `173.205 años`.
- Envejecimiento en hibernación nominal: `173.205 × 0.005 = 0.866 años biológicos`.

El envejecimiento nominal acumulado es distinto de la edad total de una persona. Si el personaje está despierto parte del viaje, sus intervalos deben integrarse con la tasa correspondiente.

### Envejecimiento nominal y efectivo

```text
si despierto:
    factor_envejecimiento ≈ 1.0       # candidato inicial
si hibernando:
    factor_envejecimiento = tasa_efectiva_hibernacion

dt_biologico = dt_nave * factor_envejecimiento
```

La **tasa efectiva** no se ha decidido matemáticamente. Debe derivarse de la nominal, el estado de `life_support` y, si se aprueba, los recursos químicos y demás condiciones del sarcófago. El cumplimiento nominal **no** debería asumirse cuando `life_support` esté degradado.

### Relatividad gravitatoria futura

Debe quedar un punto de extensión conceptual para calcular tiempo propio a partir de la **trayectoria y del entorno gravitatorio**, sin alterar la semántica de los relojes ni mezclar envejecimiento biológico con dilatación física. **No** añadir un factor arbitrario de agujero negro ni asumir que la corrección especial y la gravitatoria se multiplican siempre sin precisar el sistema de referencia.

## 5. Parámetros propuestos para `Balance` (NO EXISTEN AÚN)

| Parámetro propuesto | Valor inicial | Función |
|---|---:|---|
| `SHIP_CRUISE_SPEED_C` | `0.5` | Velocidad candidata como fracción de `c`; requiere migrar/conectar el campo actual de nave. |
| `HIBERNATION_BIO_AGE_RATE_NOMINAL` | `0.005` | Tasa de envejecimiento biológico nominal durante hibernación. |
| `AWAKE_BIO_AGE_RATE` | `1.0` | Valor base del envejecimiento en vigilia. |
| `HIBERNATION_EFFICIENCY_*` | pendiente | Configuración de respuesta a salud, disponibilidad y degradación de `life_support`. |

**Regla:** no introducir simultáneamente estos nombres junto con parámetros equivalentes sin definir la fuente de verdad. El prototipo ya almacena velocidad en `ShipState`; la especificación debe resolver su relación con el balance global y con partidas guardadas.

## 6. Requisito de consulta operativa

El jugador necesita consultar cómo está funcionando su hibernación **en este instante**. El contrato propuesto para una consulta, por ejemplo `hibernate status` (nombre sin aprobar), es:

- Estado de hibernación: activo/inactivo, o preparado/no disponible según el futuro diseño.
- Estado y salud de `life_support`.
- Tasa nominal configurada (por ejemplo, 0,5 %).
- Tasa **efectiva** que se aplicaría ahora y de qué condiciones depende.
- Una equivalencia comprensible (por ejemplo, envejecimiento biológico estimado por 100 años propios de nave), claramente identificada como proyección condicionada.
- Advertencias útiles sobre degradación, falta de químicos, anomalías o fallo, únicamente cuando esas mecánicas estén definidas e implementadas.

No inventar un valor efectivo cuando hay datos insuficientes; distinguir «sin modelo todavía», «estimación» y «tasa aplicada» en prototipos y diagnósticos.

## 7. Riesgos y decisiones pendientes de implementación

1. **Temporalidad de procesos:** inventariar todos los usos de `state.clock.t`, `dt`, vencimientos de jobs, energía, desgaste, radiación y eventos de lore. Clasificarlos por tiempo galáctico o propio, documentando excepciones.
2. **Integración por fases:** el viaje tendrá aceleración/frenado si se decide incorporarlos; no simular todo a velocidad de crucero sin indicar la simplificación.
3. **Balance acumulado:** aumentar la duración de un viaje no solo altera edad del personaje; modifica la viabilidad del `power_core`, la batería, `life_support`, drones y casco. Ensayar recorridos de siglos.
4. **Estado de `life_support`:** distinguir salud continua y estados categóricos; acordar la tasa de hibernación con daños y la política de fallo/alerta sin contradecir las salvaguardas actuales de soporte vital.
5. **Sustancias de hibernación:** la existencia diegética de agentes químicos es canónica; inventario, recarga, consumo y degradación son decisiones abiertas.
6. **Guardados y migración:** serializar correctamente las nuevas magnitudes e inicializar de forma coherente las partidas antiguas.
7. **Determinismo:** una misma seed y una misma secuencia de acciones/tiempos deben producir los mismos resultados; evitar diferencias acumulativas según tamaño de tick.
8. **Interfaz:** presentar magnitudes con unidades y distinguir inequívocamente tasa nominal de tasa efectiva.
9. **Revelación narrativa:** no ligar automáticamente un reloj biológico a un contador de desaparición total de la humanidad; el misterio central sigue abierto.
10. **Agujeros negros futuros:** fase independiente con relatividad gravitatoria, fuerzas de marea, radiación, navegación y posibilidad de escape.

## 8. Secuencia de trabajo recomendada

1. **Auditoría de tiempos y supervivencia técnica (sin mutaciones):** mapa de usos actuales, invariantes, riesgos y comportamiento en viajes de 10/100/1000 años.
2. **Contrato aprobado de tres magnitudes:** nombres, unidades, reglas para tiempo propio, cálculo numérico, guardados y tests.
3. **Edad biológica e hibernación nominal:** incorporar tasa configurada, acumulación y consulta mínima, sin forzar aún una penalización de `life_support` no acordada.
4. **Eficacia y `life_support`:** acordar fórmula, eventos de alerta, dependencias y fallos; añadir consulta de tasa efectiva y pruebas.
5. **Crucero sublumínico:** aplicar el `0.5c` candidato y recalibrar consumo, desgaste, duraciones y recuperación de recursos tras evaluar resultados.
6. **Gravedad intensa (etapa posterior):** implementar objetos compactos y tiempos propios en gravedad fuerte con modelo físico explícito.

**Criterio de cierre:** no declarar finalizado el sistema temporal hasta que las duraciones, el envejecimiento y el desgaste sean coherentes entre sí, los jugadores puedan inspeccionar las tres magnitudes y la eficacia de la hibernación, y las partidas guardadas sigan funcionando.
