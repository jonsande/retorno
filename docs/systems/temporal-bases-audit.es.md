# TEMP-01A — Auditoría de las bases temporales

Versión inglesa: [temporal-bases-audit.md](temporal-bases-audit.md).
Instantánea diagnóstica del código productivo en HEAD. No se cambiaron reglas
temporales, Balance, partidas ni pruebas. El [invariante aprobado](../development/system-contracts.es.md)
exige tiempo propio para la física interna de la nave; los procesos externos
usan el marco físicamente correspondiente; el tiempo biológico deriva del
propio y la fisiología. La fecha galáctica de un evento es un registro, no
prueba de que su proceso deba usar segundos galácticos.

## Cómo leer el inventario

`G` es `ClockState.t` (segundos de coordenada galáctica), `P` es
`ship_elapsed_s` (segundos propios de la nave) y `B` es `bio_elapsed_s`. `dt`
en `Engine.tick` y `GameLoop.advance_interval` es G; `proper_dt`/`dt_ship`
es P. **Correcto** juzga solo la base temporal examinada; no certifica todo
el modelo físico. **Incorrecto** indica contradicción del invariante en la
base o en el cálculo del intervalo. **Decisión** indica que antes debe
aprobarse el marco o la semántica jugable.

Todos los campos citados pertenecen a `GameState` y se serializan con
[`save_single_slot`](../../src/retorno/io/save_load.py); solo la deuda
monotónica del hilo automático existe exclusivamente en ejecución. La
hibernación utiliza [`_execute_hibernate`](../../src/retorno/cli/repl.py), que
llama reiteradamente a `GameLoop.advance_interval`; no suspende los sistemas
de a bordo. La navegación física pública utiliza una transacción aislada en
`Engine.tick`, [`_physical_limit_selection`](../../src/retorno/core/engine.py)
y [`select_next_boundary`](../../src/retorno/core/nav_coordinator.py). El
coordinador admite hoy límites propios y límites de trabajo **galácticos**.
La vía ordinaria `_tick_interval` aún ejecuta trabajos, narrativa y
mantenimiento una vez por intervalo G; las subdivisiones eléctricas no
repiten esas ejecuciones.

## Inventario: relojes, movimiento, electricidad y desgaste

| Proceso y código responsable | Base actual y evidencia; base requerida | Duraciones, frontera causal, hibernación/navegación y persistencia | Clasificación |
| --- | --- | --- | --- |
| Planificación automática: [`GameLoop._run`](../../src/retorno/runtime/loop.py) | El reloj monotónico del equipo programa solicitudes durante el tiempo activo; se descuenta de la deuda el `clock.t` confirmado. Se requieren reloj monotónico para la planificación real y G para el avance de coordenada solicitado. | `tick_s` y `_auto_debt_s` son segundos en ejecución; la recuperación acotada cede. Pausa, avance manual, hibernación, error y cierre descartan la deuda; no se guarda. | Correcto. |
| Relojes galáctico, propio y biológico: [`Engine._tick_interval`, `_tick_physical_segment`](../../src/retorno/core/engine.py), [`temporal.py`](../../src/retorno/core/temporal.py) | El movimiento ordinario/legacy calcula `dt_ship` con velocidad fijada; los segmentos físicos integran tiempo propio analítico; B suma P con factor de criostasis. Se requieren G para movimiento de coordenada, P para procesos de a bordo y B para envejecimiento. | Se guardan `t`, `ship_elapsed_s`, `bio_elapsed_s`, `last_dt`; inicio de segmento y progreso G/P se guardan en [`nav_state.py`](../../src/retorno/core/nav_state.py). Las fronteras de fase/llegada y el rollback atómico rigen también en hibernación. | Correcto para los relojes; la modulación fisiológica se examina aparte. |
| Movimiento, llegada y propulsión: [`nav_physics.py`](../../src/retorno/core/nav_physics.py), [`Engine.next_physical_step`, `_tick_nominal_physical_travel`, `_tick_inertial`](../../src/retorno/core/engine.py) | Posición y duración de fases usan G; aceleración propia y tiempo a bordo usan P. Se requieren ambos marcos relacionados por la trayectoria. | Se guardan duración G de segmentos, extremos propios y recibos de combustible fijados; el viaje local legacy guarda `transit_start_t`/`arrival_t` en G. Las fronteras de segmento, frenado, recuperación y llegada preceden al commit, también durante hibernación. | Base temporal correcta. |
| Batería principal, generación/carga y recarga de drones: [`Engine._integrate_power_interval`, `_integrate_power_slice`](../../src/retorno/core/engine.py), [`nav_electricity.py`](../../src/retorno/core/nav_electricity.py), [`drone_charging.py`](../../src/retorno/core/drone_charging.py) | kW/kWh se integran sobre P; la recarga usa segundos propios y decisión compartida de potencia. Se requiere P para energía de a bordo. | Se guardan energía, calidad y batería de drones; cortes en batería vacía/llena, reserva de recarga al 25 %, dron lleno y cambio de suministro. La asignación se recalcula tras deslastre, también en hibernación/tránsito físico; rigen invalidación y rollback. | Correcto. |
| Temporizadores de regulación eléctrica: [`Engine._integrate_power_slice`](../../src/retorno/core/engine.py), [`power_limits`](../../src/retorno/core/nav_electricity.py) | `low_q_shed_timer_s` y `brownout_sustained_s` acumulan P. Se requiere P para electrónica de la nave. | Ambos contadores float se guardan; calidad, SoC, deslastre programado y déficit sostenido son límites propios convertidos a G para movimiento físico. La hibernación no cambia su tasa. | Correcto. |
| Desgaste de sistemas y casco: [`Engine._apply_degradation`, `_apply_hull_degradation`](../../src/retorno/core/engine.py), [`ordinary_wear_rate`](../../src/retorno/core/nav_boundaries.py), [`integrated_system_wear`](../../src/retorno/core/nav_radiation.py) | Salud/casco pierden integridad sobre P, también en los tramos móvil y estacionario de llegada; la vía física integra calidad y radiación sobre P. Se requiere P para material de a bordo. | Se guardan `health`/`hull_integrity`; umbrales físicos de salud y casco cero son cortes, con invalidación al cambiar condiciones. La vía ordinaria aún muestrea condiciones en extremos gruesos; hibernación conserva esa conducta. | Base correcta; la resolución del muestreo ordinario queda aparte. |
| Alerta de inestabilidad del bus: [`Engine._update_alerts`, `_physical_limit_selection`](../../src/retorno/core/engine.py) | `clock.t >= Balance.BUS_INSTABILITY_AFTER_S` es tiempo G absoluto desde el inicio, no duración de distribución dañada. Si representa deterioro interno se requiere P mientras esté dañada; si es un hito narrativo, G podría ser intencional. | Constante absoluta y alerta guardada; frontera física G en esa constante; se evalúa durante hibernación. No hay contador persistido de duración del daño. | Decisión; induce a confusión si se interpreta como temporizador del equipo. |

## Inventario: supervivencia, exposición e hibernación

| Proceso y código responsable | Base actual y evidencia; base requerida | Duraciones, frontera causal, hibernación/navegación y persistencia | Clasificación |
| --- | --- | --- | --- |
| Campo ambiental espacial y exposición de casco/interior: [`Engine._compute_env_radiation_rad_per_s`](../../src/retorno/core/engine.py), [`integrate_segment_radiation`](../../src/retorno/core/nav_radiation.py) | El tránsito físico muestrea radiación por posición en trayectoria parametrizada por G e integra dosis a bordo y acoplamiento del casco sobre P. El viaje legacy muestrea en posición G avanzada. Se requiere campo espacial en marco de su fuente y exposición a bordo en P; el significado de `rad_per_s` configurado bajo movimiento relativista no está completamente definido. | Se guardan tasa ambiental, casco y niveles; límites espaciales/radiológicos físicos y umbral de despertar, con rollback si hay cortes sin resolver. | Decisión sobre marco del campo externo y flujo relativista; la base de integración a bordo es correcta. |
| Dosis de drones: [`Engine._apply_radiation`, `_tick_physical_segment`](../../src/retorno/core/engine.py) | Dosis de dron no acoplado = `env_rad * shield_factor * dt` con G, incluso para un dron desplegado dentro de la nave durante tránsito físico. Se requiere P para dron a bordo; uno dejado en un nodo necesita su marco local y exposición propios. | Se guarda `dose_rad`; la vía física usa dosis ambiental galáctica integrada dividida por G y vuelve a multiplicar por G; los avisos de nivel aparecen al final del intervalo, sin corte de dosis del dron. La hibernación no la suspende. | Incorrecto para drones a bordo; el marco de drones externos exige decisión. |
| Envejecimiento biológico: [`biological_time_interval`](../../src/retorno/core/temporal.py), ambos integradores de reloj del motor | B = P multiplicado por 1 despierto o por `HIBERNATION_BIO_AGE_RATE_NOMINAL` en criostasis. Se requiere derivar de P y modular por fisiología real/criostasis. | Se guardan `bio_elapsed_s` e `is_hibernating`; no hay integración del estado fisiológico ni cortes por umbrales biológicos. La hibernación cambia el indicador y avanza B. | Decisión: la relación P/criostasis es correcta, pero falta la modulación fisiológica. |
| Gracia de viabilidad del soporte vital y bloqueo terminal: [`Engine._apply_critical_system_consequences`](../../src/retorno/core/engine.py) | `life_support_offline_s += dt` usa G en vías ordinaria y física. Se requiere al menos P para pérdida de entorno de la nave; debe aprobarse si el límite de viabilidad usa B o una integral fisiológica aparte. | Contador float guardado, reiniciado al recuperar servicio; se comprueba al final del intervalo, sin corte físico específico de expiración. La hibernación lo avanza a tasa G; la vía física rechaza algunos estados iniciales apagados en vez de modelar la transición. | Base incorrecta; el criterio fisiológico exacto es una decisión. |
| Duración de hibernación y política de despertar: [`_execute_hibernate`, `_hibernate_interrupt_reason`, `_hibernate_transit_env_threshold_dt`](../../src/retorno/cli/repl.py) | Solicitud `years * YEAR_S`, resto y años efectivos usan G; los despertares comprueban eventos críticos, batería y radiación espacial. El marco de la *duración solicitada* es ambiguo: P transcurrido por nave/tripulación o G de llegada/calendario externo. Los predicados de despertar deben seguir el marco de su subsistema. | No se guarda temporizador de solicitud: sí indicador activo, relojes y eventos de inicio/fin; se respetan bloques, fases/llegada y paradas de emergencia. Un bloqueo técnico conserva tiempo/eventos confirmados y deja pausado el avance automático. | Decisión sobre el significado de los años solicitados; las fronteras físicas vigentes de despertar siguen siendo válidas. |
| Edad de alertas y fechas de eventos: [`Engine._make_event`, `_ensure_alert`, `_update_alert_timers`](../../src/retorno/core/engine.py) | Fechas de evento/primera/última aparición usan G, adecuado para cronología común. `unacked_s += int(dt)` pierde todos los intervalos menores de un segundo. Se requiere G para registros y conservar la fracción G acumulada antes de redondear para mostrar. | Se guardan fechas enteras y `unacked_s`; sin umbral causal; hibernación y cortes físicos cortos revelan la truncación. | Aritmética del contador incorrecta; marcas G de eventos correctas. |

## Inventario: servicios, trabajos, drones y sensores

| Proceso y código responsable | Base actual y evidencia; base requerida | Duraciones, frontera causal, hibernación/navegación y persistencia | Clasificación |
| --- | --- | --- | --- |
| Todos los trabajos en cola/activos: [`Engine._process_jobs`, `_advance_job_timers`, `_physical_limit_selection`](../../src/retorno/core/engine.py), [`Job`](../../src/retorno/model/jobs.py), [`job_limits`](../../src/retorno/core/nav_boundaries.py) | `Job.eta_s` es un **float restante relativo**, reducido por `dt` G; las previsiones físicas lo etiquetan `TemporalLimit(..., "galactic", eta_s)`. La mayoría son trabajos de a bordo y requieren P. Actores externos pueden necesitar otro marco local. | Se guardan ETA/estado/cola/propietario/parámetros, no fecha absoluta de fin. La vía física corta en ETA G y resuelve efectos una vez; la ordinaria pasa todo el intervalo por trabajo y puede resolver al final. La hibernación ejecuta trabajos. `nav_coordinator` solo admite límites de trabajo G. | Incorrecto para trabajo a bordo. No se halló fecha absoluta galáctica de fin de trabajo; hay que cambiar planificador y dominio del límite, no solo renombrar `eta_s`. |
| Arranque y funcionamiento de servicios: [`Engine.apply_action` BOOT_SERVICE, `_apply_job_effect`](../../src/retorno/core/engine.py), [`ServiceState`](../../src/retorno/model/systems.py) | `boot_time_s` entra en trabajo reducido por G. `is_running` es estado persistido, no proceso por segundo; consumo y desgaste durante funcionamiento usan P. Se requiere P para arranque y operación de a bordo. | Se guardan indicador de servicio y trabajo de arranque; corte físico actualmente G; la hibernación completa el arranque a esa tasa. Cambios de potencia/dependencias interrumpen o bloquean el trabajo. | Arranque incorrecto; energía/desgaste del funcionamiento correcto. |
| Trabajo informático/de datos y reparaciones de nave: [`Engine.apply_action`, `_enqueue_job`, `_apply_job_effect`, `_maybe_fail_emergency_job`](../../src/retorno/core/engine.py) | Solución de rutas, recuperación de credenciales, auditoría de carga, módulos, reparación de sistema/autocomprobación y salvamento comparten ETA G. Probabilidad de fallo de emergencia = `p_fail_per_s * interval.dt_s` con G. Se requiere P para cómputo, maquinaria y exposición a riesgo de a bordo; agente externo de salvamento necesita marco local. | Se guardan ETA, riesgo, materiales reservados y resultados; existe corte físico de fin, pero G, y riesgo/efecto se resuelven una vez. La hibernación lo ejecuta; intervalos ordinarios largos pueden retrasar finalización. La semilla RNG también incluye `clock.t`: cambiar el dominio afecta resultados deterministas. | Duración/riesgo a bordo incorrectos; trabajo exterior exige decisión. |
| Movimiento/tareas de drones y débito por acción: [`Engine.apply_action`, `_drone_job_battery_cost`, `_apply_job_effect`](../../src/retorno/core/engine.py) | Despliegue, movimiento, retorno, exploración, salvamento, reparación/instalación/reinicio de drones usan ETA G. El coste fijo de batería se cobra al producirse el resultado, no por segundo. Se requiere P para movimiento dentro de la nave; operaciones en nodo requieren tiempo propio local del dron. Costes fijos por operación no necesitan conversión de tasa. | Se guardan ubicación, batería, ETA y materiales; frontera física del trabajo ahora G; la hibernación hace progresar tareas. Una corrección debe conservar débito único y orden de llegada/retorno. | Duraciones a bordo incorrectas; reloj de dron externo pendiente de decisión. |
| Descarga en reposo de desplegados y reserva de retorno: [`Engine.tick`, `_update_drone_maintenance`, `_drone_return_reserve`](../../src/retorno/core/engine.py) | Descarga en reposo usa `dt` G; previsión de reserva multiplica ETA G por tasa por segundo. Se requiere P para dron que viaja con nave y tiempo local externo para uno dejado atrás. | Se guardan batería/autorretorno/trabajos; `Engine.tick` ordinario corta en reserva/ETA previstas, la vía física tiene control especial para un dron interno; la hibernación mantiene descarga. Cortes y ecuación de reserva deben migrarse juntos. | Incorrecto a bordo; marco exterior no decidido. |
| Integridad, descontaminación y reparación pasiva de drones: [`Engine._update_drone_maintenance`](../../src/retorno/core/engine.py) | Pérdida de integridad desplegada y descontaminación acoplada usan `dt` G; la reparación de bahía cobra un material/tirada por **llamada**, con ganancia independiente de duración. Se requiere P para hardware acoplado/a bordo y tiempo local externo para remoto. | Se guardan integridad/dosis/carga/contador RNG; no hay corte específico de fin de mantenimiento; la vía física lo llama una vez por corte y la ordinaria una vez por tick exterior. El tamaño de bloque de hibernación puede cambiar coste/tiradas. | Base a bordo incorrecta; cadencia/economía de reparación pasiva exige otra decisión de diseño. |
| Sensores, escaneo y solución de rutas: [`Engine.apply_action` Scan/RouteSolve, `_perform_scan`](../../src/retorno/core/engine.py) | ETA de sensores usa G mediante planificador común. Observación de escaneo e intel adquirido con `t=clock.t` son registros G correctos. Se requiere P para duración de escaneo/cómputo a bordo; tiempo de luz externo u objetivos móviles no están modelados. | Se guardan trabajo, observación, RNG e intel adquirido; corte físico ahora G; escanear materializa sectores al completar, así que cambiar el corte puede cambiar lo observado. Hibernación completa escaneos; no hay escaneo automático por tick. | Duración del trabajo incorrecta; marcas de registro correctas. |

## Inventario: universo externo, radio y otros registros temporales

| Proceso y código responsable | Base actual y evidencia; base requerida | Duraciones, frontera causal, hibernación/navegación y persistencia | Clasificación |
| --- | --- | --- | --- |
| Emisiones de radio declaradas/procedurales y propagación: [`radio_coordinate_time`, `radio_link_metrics`, `radio_temporal_block_reason`](../../src/retorno/core/communications.py), [`RadioHistory.equipment_at`](../../src/retorno/worldgen/historical_radio.py) | `start_t/end_t` de fuente, épocas del equipo y `distance_ly * YEAR_S` usan G provisional. Se requiere emisión en marco del transmisor y propagación en coordenada espaciotemporal compatible; fuentes estacionarias encajan en la aproximación actual. Un transmisor móvil necesita otro modelo. | Ventanas/épocas absolutas, historia de fuente y definición de radio guardadas en `WorldState`; movimiento cambia posición receptora. Recepción se comprueba en ticks/llegada/despertar, sin corte continuo de trayectoria; hibernación bloquea receptor. | Correcto para modelo provisional explícitamente estacionario; extensión móvil exige decisión. |
| Captura, reintento y libro de radio: [`retry_radio_opportunities`, `capture_radio_opportunity`](../../src/retorno/core/communications.py) | Admisión se comprueba en G/posición actuales; `prepared_t`/`received_t`/`read_t` son registros G. Se requiere llegada en marco de coordenada; electrónica receptora funciona en P, pero no existe tasa de duración de recepción separada. | Se guardan pendientes/recibidas, cursor e intel; ventanas finitas pueden transcurrir enteras durante un avance largo, mientras señales continuas sobreviven a comprobaciones posteriores. Hibernación y tránsito legacy bloquean recepción; vía física reintenta por cortes causales. | Decisión sobre cortar llegada/expiración de ventana finita o mantener política de muestreo. |
| Presupuesto de búsqueda de radio: [`discover_radio_opportunities`](../../src/retorno/core/communications.py), [`query_local`](../../src/retorno/worldgen/historical_radio.py) | Las páginas de candidatos avanzan por reintento/tick elegible, no por segundos físicos. Se requiere búsqueda técnica acotada, sin implicar tasa de tiempo universal. | Persisten cursores; hibernación larga/cortes físicos pueden cambiar las oportunidades de ejecutar búsqueda, mientras las emisiones certificadas siguen iguales. Sin plazo causal propio. | Correcto como presupuesto de trabajo, no tasa de evolución física. |
| Colocación y entrega narrativa: [`run_lore_scheduler_tick`, `_deadline_reached`, `_soft_force_roll`](../../src/retorno/core/lore.py) | Cadencia no forzada y `max_year` usan G; contadores de eventos/acoplamientos/enlaces/salvamento son recuentos de interacción. Se requiere G de calendario si es programación editorial/universal; proceso a bordo o experiencia de tripulación requeriría P/B. | Se guardan `next_non_forced_eval_t`, `eval_seq`, colocaciones, pools y fechas de entrega; la vía física corta en próxima evaluación G, la ordinaria evalúa al final; hibernación la ejecuta. La colocación puede certificar conocimiento, por lo que no cabe repetir tiradas retroactivamente. | Decisión sobre semántica narrativa/calendario y cortes transaccionales de evaluaciones dentro de intervalo grande. |
| Evolución de nodos muertos y enfriamiento de recuperación: [`evaluate_dead_nodes`](../../src/retorno/core/deadnodes.py), [`structural_recovery.on_capture`](../../src/retorno/core/structural_recovery.py) | `stuck_since_t`, `dead_since_t`, `last_action_t` y umbrales de años usan G; umbrales de enlaces usan conteos. Se requiere envejecimiento/operación local del nodo externo; G es plausible para nodos estacionarios en marco inercial provisional, pero no se especifican relojes/causas remotos. | Se guardan tracker, intentos, planes y recibos de radio; se evalúa por disparadores, no en plazo causal universal; hibernación puede cruzar años antes del siguiente disparador. Etapas de recuperación dependen de interacciones, no de trabajos temporizados. | Decisión sobre marco local externo y momento del evento; no hay evidencia para usar P de la nave. |
| Generación estática de sectores/nodos, inventario de salvamento y planificación de recuperación: [`ensure_sector_generated`](../../src/retorno/worldgen/generator.py), [`confirm_recovery`](../../src/retorno/core/structural_recovery.py) | Consulta/semilla determinista o interacción, sin integral de evolución continua. `initialized_t`/`window_closed_t` de nodo y `created_t` del plan son registros G. No se requiere convertir tasa salvo que se defina evolución física futura. | Sectores, conocimiento, inventarios y planes se guardan; escaneo/llegada/acción y narrativa/radio los materializan. La transacción física protege escrituras en tránsito; hibernación puede activar narrativa programada, no desgaste autónomo de nodos. | Correcto como datos estáticos/activados; evolución futura exige diseño separado. |
| Manifiesto de carga, correo/intel y procedencia de eventos: [`Engine._apply_job_effect` CARGO_AUDIT](../../src/retorno/core/engine.py), [`register_mail`](../../src/retorno/model/os.py), [`record_intel`](../../src/retorno/model/world.py) | Duración de auditoría tiene defecto G de trabajos; `manifest_last_sync_t`, recepción de correo, intel y evento `t` son fechas G de registro. Se requieren P para trabajo y G para cronología histórica común. | Se guardan registros y conocimiento adquirido; no hay integral temporizada independiente tras trabajo/acción disparadores. Hibernación conserva orden de adquisición. | Fechas correctas; duración del trabajo de auditoría incorrecta. |

Los temporizadores de refresco Textual y los retrasos de reproducción sonora y
narrativa son controles de presentación de reloj real del equipo, no procesos
de `Engine.tick`; esta auditoría no los cambia. `RiskProfile.p_glitch_per_s`
se guarda/configura, pero no tiene consumidor productivo por segundo en el
motor inspeccionado; solo `p_fail_per_s` entra en `_maybe_fail_emergency_job`.

## Problemas confirmados, incertidumbres y dependencias

1. **El planificador compartido de trabajos es la dependencia principal.**
   Todos los ETA a bordo se reducen con G y se prevén como G, incluidos
   arranques, cómputo, escaneo, reparaciones y tareas de drones. `eta_s` es
   relativo, no fecha absoluta galáctica; `arrival_t`, ventanas de radio y
   `next_non_forced_eval_t` *sí* son absolutos G. Una intervención posterior
   deberá marcar dominio temporal o separar límites tipados y convertir el
   fin en P a G usando la trayectoria activa.
2. **Mantenimiento a bordo y viabilidad son incoherentes.** Descarga, dosis,
   integridad, descontaminación y gracia de soporte vital usan G; solo la
   recarga usa ya P. Además, reparación de bahía cobra un material/tirada
   por llamada; cambiar únicamente `dt` no igualaría intervalos largos/cortos.
   Exposición de drones remotos, umbral fisiológico de viabilidad y economía
   de reparación pasiva necesitan decisiones explícitas.
3. **Registros no son tasas.** Las marcas G de eventos, observaciones,
   correo, intel y manifiestos deben seguir en G aunque el trabajo productor
   pase a P. `unacked_s` es un defecto aparte de acumulación por truncación
   por tick. La constante global de alerta del bus necesita dueño semántico.
4. **Tiempo externo no equivale siempre a G de la nave.** Emisores históricos
   estáticos usan coordenada común provisional; transmisores móviles, drones
   externos y nodos remotos evolutivos pueden requerir tiempos propios locales
   o modelo espaciotemporal. Los años narrativos pueden ser editoriales.

## Propuesta de intervenciones pequeñas ordenadas por dependencias

1. **TEMP-01B: dominios temporales tipados y conversión determinista de
   trabajos.** Aprobar el dominio de cada `JobType`; introducir dominios
   explícitos de duración restante y conversión de frontera P→G en el
   planificador y `nav_coordinator`. Mantener `Job.eta_s` y semántica de
   cola/orden hasta demostrar fase/llegada, hibernación y frontera parcial.
   Verificar equivalencia de intervalos, rollback, carga/guardado de partida
   vigente a mitad de trabajo y débito único de combustible/materiales.
2. **TEMP-01C: trabajos a bordo y efectos de servicios/sensores.** Migrar
   arranque, cómputo, escaneo, reparaciones y riesgos de emergencia aprobados
   a P con el mecanismo común. Revalidar carga eléctrica de trabajos,
   disponibilidad de servicios, posición/conocimiento del escaneo y RNG de
   fin. No repetir trabajos, narrativa, radio ni RNG al subdividir electricidad.
3. **TEMP-01D: relojes y mantenimiento de drones.** Decidir primero el marco
   de drones remotos y la economía por tiempo de reparación pasiva. Migrar
   juntos movimiento a bordo, descarga/reserva, dosis, integridad y
   descontaminación; integrar recursos/RNG de reparación en oportunidades
   explícitas de tiempo propio. Conservar energía de recarga 07B y orden de
   cortes de rescate.
4. **TEMP-01E: supervivencia y registros.** Decidir si gracia de soporte
   vital es P de equipo, B fisiológico o integral de exposición; añadir corte
   causal y validación en hibernación/navegación física. Acumular aparte
   fracciones de edad de alertas sin cambiar marcas G de eventos. Decidir
   semántica de alerta del bus antes de cambiar su umbral absoluto.
5. **TEMP-01F: relojes externos y narrativa.** Aprobar si límites narrativos
   de año son calendario/editoriales y si ventanas finitas de radio deben
   cortar avance físico. Ajustar solo entonces modelos de nodos externos,
   emisores móviles o drones remotos según proceda; preservar procedencia
   certificada de radio, conocimiento adquirido y generación determinista.

El orden es propuesta, no autorización para implementar. Cada fase necesita
especificación EN/ES y pruebas dirigidas de atomicidad causal, rendimiento de
hibernación, persistencia de versión vigente, conservación energética y no
divulgación de conocimiento. Estas fases experimentales no exigen migrar
partidas antiguas; las partidas válidas de la versión resultante sí deben
recargarse correctamente.

## Validación de esta auditoría

Se leyeron código y especificaciones propietarias; no se ejecutaron pruebas,
suite general ni benchmarks. El resultado definitivo de PT001-01/09-B
aportado para este registro es **727 pruebas y 169 subpruebas superadas en
461,08 s**; no es una ejecución de TEMP-01A.

## Comprobación previa TEMP-01B: bloqueo causal de trabajos ordinarios

**Estado: detenido antes de implementar.** El planificador compartido P/G
solicitado no puede garantizar la finalización causal en todas las vías de
avance sin una modificación más amplia del integrador ordinario. Se aplica
la condición de parada explícita de TEMP-01B; esta intervención no cambió
trabajos productivos, formato de partidas ni pruebas.

[`Engine._tick_interval`](../../src/retorno/core/engine.py) adelanta los
relojes G/P/B durante todo el intervalo solicitado, procesa una posible
llegada legacy y llama una sola vez a `_process_jobs(state, dt)`. Este método
recorre los trabajos en su orden histórico, resta todo el intervalo G de
cada `eta_s` y resuelve los efectos al final.
[`GameLoop.advance_interval`](../../src/retorno/runtime/loop.py) no corta
un intervalo ordinario al terminar un trabajo (salvo si se pide detenerse
en la llegada legacy). Por ejemplo, un trabajo de 2 s en un tick de 10 s
en reposo termina y registra su efecto en G+10; diez ticks de 1 s pueden
terminarlo en G+2. Una llegada intermedia cambia la localización y el orden
de sus efectos respecto a los del trabajo. Cambiar solo el débito de ETA a
P o la previsión en `job_limits` no resolvería la incoherencia.

La vía física sí prepara un estado transaccional y selecciona límites
causales, pero [`job_limits`](../../src/retorno/core/nav_boundaries.py) y
[`select_next_boundary`](../../src/retorno/core/nav_coordinator.py) exigen
límites de trabajo G; el segundo rechaza los P. Una solución completa debe
subdividir también los intervalos ordinarios en las fronteras de trabajo y
llegada, convertir cada ETA P restante a G sobre la trayectoria activa y
confirmar relojes, efectos, riesgo, carga eléctrica y registros en su orden
real. Debe preservar simultaneidad, orden de trabajos, avance parcial y
rollback sin repetir mantenimiento, narrativa ni RNG. Esta ordenación
transaccional excede el cambio acotado de dominio/conversión de TEMP-01B.
Por eso no se introduce por separado el soporte de la vía física.
La hibernación usa `advance_interval` y comparte el bloqueo. Todos los
trabajos productivos de la versión actual siguen usando G.

### Matriz de dominio propuesto de los 24 JobType

`P` significa tiempo propio de la nave para trabajo físicamente a bordo.
`L` significa tiempo local de un actor externo o del lugar de trabajo,
**no necesariamente G de la nave**; todavía no existe un reloj L independiente.
`P/L` exige fijar o seguir la localización de ejecución. Todos los tipos
siguen implementados en G hasta una migración posterior. La matriz clasifica
la *duración del trabajo*; la fecha registrada del evento sigue siendo G.

| JobType | Dominio propuesto | Dependencia de localización, propietario o contexto / decisión pendiente |
| --- | --- | --- |
| `REPAIR_SYSTEM` | P/L | Operador dron y sistema de la nave; confirmar si el operador puede ser externo y qué reloj lo rige. |
| `REPAIR_DRONE` | P/L | Operador y objetivo deben coincidir en localización; P a bordo y decisión sobre el actor externo en otro lugar. |
| `SELFTEST_REPAIR` | P | Autocomprobación de un sistema de la nave; sin propietario externo. |
| `BOOT_SERVICE` | P | Arranque de servicio de la nave; contexto a bordo. |
| `DEPLOY_DRONE` | P | Comienza con el dron acoplado y usa duración de bahía; el destino puede ser sector de la nave o nodo exterior. |
| `MOVE_DRONE` | P/L | Dron y destino pueden estar dentro de la nave o en un nodo; decidir al encolar y ante un traslado. |
| `DOCK` | Decisión | Maniobra nave/nodo externo; elegir el marco físico de la duración antes de migrar. |
| `UNDOCK` | Decisión | Maniobra nave/nodo externo; elegir el marco físico de la duración antes de migrar. |
| `SALVAGE` | Decisión | El valor del enum no tiene encolado ni efecto productivo en el motor inspeccionado; definir su semántica primero. |
| `INSTALL_MODULE` | P | Instalación de módulo de la nave; trabajo a bordo. |
| `UNINSTALL_MODULE` | P | Retirada de módulo de la nave; trabajo a bordo. |
| `DRONE_INSTALL_MODULE` | P/L | Operador dron, localización y objetivo determinan trabajo interior o exterior. |
| `DRONE_UNINSTALL_MODULE` | P/L | Operador dron, localización y objetivo determinan trabajo interior o exterior. |
| `REBOOT_DRONE` | P/L | El dron averiado puede estar en bahía o fuera; decidir entre reloj de bahía y del dron. |
| `SALVAGE_SCRAP` | L | Dron en nodo exterior; falta definir el reloj del actor/lugar. |
| `SALVAGE_MODULE` | L | Dron en nodo exterior; falta definir el reloj del actor/lugar. |
| `SALVAGE_DATA` | L | Dron en nodo exterior; falta definir el reloj del actor/lugar. |
| `SURVEY_DRONE` | L | Dron y nodo exterior; decidir reloj del actor o del lugar. |
| `SALVAGE_DRONE` | L | Dron y nodo exterior; decidir reloj del actor o del lugar. |
| `ROUTE_SOLVE` | P | Cálculo del ordenador de la nave; servicio a bordo. |
| `SCAN` | P | Trabajo de sensores de la nave; servicio a bordo. |
| `RECALL_DRONE` | P/L | Retorno exterior y recogida en bahía; decidir si dividir fases o usar reloj de actor/lugar. |
| `CARGO_AUDIT` | P | Cómputo del manifiesto; servicio a bordo. |
| `RECOVER_AUTH` | P | Recuperación de autorización del SO; servicio a bordo. |

Antes de reintentar TEMP-01B hay que aprobar por separado el alcance de
subdivisión y transacción del integrador ordinario. Una prueba mínima debería
demostrar igual instante de finalización y efecto único para 10×1 s y 1×10 s
en reposo; después, llegada legacy, cambios de fase y trabajos P en tránsito
físico. Ese prerrequisito no incluye relojes externos ni migraciones productivas.
