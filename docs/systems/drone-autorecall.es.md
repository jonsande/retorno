# Autorretorno preventivo de drones

Implementado en `src/retorno/core/engine.py`; CLI y Textual comparten admisión
de trabajos, planificador, costes de batería y acciones de retorno.

Con autorecall activado, un dron operativo debe conservar energía para volver
antes de aceptar trabajo. `_drone_job_battery_cost` define los descuentos por
tarea existentes de despliegue, movimiento, reparación, instalación/retirada de
módulos de nave, survey y salvage; la finalización real y el fallo de reparación
utilizan las mismas cantidades. Este cambio no añade un descuento al retorno
ni cambia costes normales, probabilidad de fallo de reparación, probabilidad de
éxito del retorno o requisitos del reinicio de recuperación.

La reserva absoluta es el mayor valor entre:

- umbral configurado multiplicado por capacidad efectiva actual de batería;
- mínimo existente de retorno por capacidad efectiva, más consumo en espera
  durante el ETA actual de recall y un segundo de margen de planificación.

El presupuesto necesario suma todo el trabajo pendiente del mismo dron: duración
restante al consumo en espera existente y cada descuento de tarea pendiente.
Se incluyen capacidad de módulos y modificadores de ETA de movimiento/bahía
actuales. Las reservas se calculan con el estado vivo; no se gastan ni almacenan
como una segunda batería. El modo dios omite la reserva porque evita el consumo
correspondiente. Operaciones sin consumo en bahía y reinicios de recuperación
mantienen sus reglas existentes.

Un dron de capacidad base con 12% no puede aceptar una reparación de 8% y 45 s
con umbral normal de autorretorno de 10%: necesita 18.09%, incluido 0.09% en espera.
Se rechaza la reparación sin avanzar tiempo ni gastar batería; se devuelve la
chatarra que el comando hubiera reservado y se solicita retorno anticipado.

El planificador revalida el presupuesto al iniciar tareas y durante su ejecución,
incluidos trabajos cargados desde guardado, cambios de umbral o de equipo.
Se cancela trabajo inacabado inseguro sin su descuento de finalización; la
chatarra de reparación reservada se devuelve exactamente una vez. Antes del
autorretorno se cancelan tareas en cola del mismo dron. El trabajo activo seguro
termina primero; el retorno tiene prioridad sobre trabajo adicional y no se
duplica un recall pendiente. No se afectan las colas de otros drones. Se utilizan
los identificadores y resultados terminales de trabajo existentes.

`Engine.tick` conserva los ticks normales si la reserva proyectada es segura.
Cuando hace falta, se detiene en la finalización relevante de una tarea del dron
o en el límite de reserva por espera, para que una espera grande no salte la
ventana de retorno. El movimiento conserva su duración normal. En CLI y Textual,
`debug on` pausa el tiempo automático: admisión y configuración deciden de
inmediato, pero `wait` hace avanzar el retorno. La caché de telemetría eléctrica
con debug pausado queda fuera de este cambio.

Los requisitos incumplidos de batería, integridad o acoplamiento externo producen
ahora mensajes localizados y se conservan en `DroneState.autorecall_block_reason`,
visible mediante `drone status [D1]`. No se repiten continuamente bloqueos
idénticos. El diagnóstico sigue siendo de solo lectura y no revela IDs de
instalaciones desconocidas. Un dron ya al 4% no recibe energía gratis; el mínimo
normal del 5% sigue impidiendo su retorno. Autorecall OFF permite asumir riesgo
deliberado dentro de los requisitos existentes de operación.

Los comandos públicos siguen siendo `drone autorecall D1 on|off|<porcentaje>`,
`drone status D1`, `drone repair D1 <system_id>`, `drone recall D1`,
`drone recall! D1|all`, `jobs` y `wait <segundos>` en DEBUG. La ayuda y los
manuales diegéticos de drone/repair se mantienen en EN/ES.

## Recall de emergencia y tránsito

`drone recall! <drone_id|all>` reutiliza la acción existente `DroneRecall` con un
indicador `emergency`. Antes de cancelar nada valida las compuertas normales de
recall: estado desplegado, integridad mínima, batería mínima y, para un dron en
una instalación externa, co-localización con la nave. Por tanto, un recall de
emergencia bloqueado deja intactos el dron y su trabajo. Cuando valida, cancela
todo trabajo en cola o en ejecución del dron o drones objetivo, devuelve la
chatarra de reparación reservada mediante el mismo helper que usa el autorretorno,
finaliza cada trabajo con la ruta terminal ordinaria de cancelación e inserta un
único trabajo de recall al frente de la cola. Un trabajo `RECALL_DRONE` ya activo
se conserva en lugar de duplicarse. No es un acoplamiento instantáneo; el retorno
mantiene su ETA y reglas de éxito normales.

La compuerta de tránsito de `Engine.apply_action` ahora acepta `JobCancel` y
`RepairAutoMoveDecision`, además de las acciones existentes. Esto permite a la
nave cancelar trabajo y responder una decisión diferida de reparación durante el
tránsito. El fallo anterior era que la compuerta rechazaba la decisión, de modo
que el aviso se consumía y nunca se reemitía mientras el trabajo seguía en
`awaiting_auto_move_confirmation` con ETA congelada.

Los avisos ahora son recuperables. CLI y Textual reconstruyen los avisos
pendientes desde el estado vivo del trabajo (`_pending_repair_auto_move_prompts`)
durante el drenaje de eventos automáticos a nivel de comando, tras la
hibernación y al responder la confirmación en cola. Textual mantiene una cola
deduplicada para no descartar un aviso mientras
otra confirmación está abierta ni mostrarlo dos veces. El indicador
`awaiting_auto_move_confirmation` del trabajo sigue siendo la única fuente de
verdad; un evento obsoleto no puede resucitar un trabajo que ya no espera.

`tests/drone_recall_emergency_smoke.py` cubre el parser, decisiones y cancelación
en tránsito, recall de emergencia individual/todos, recall bloqueado que preserva
el trabajo y el rearme de avisos. Las suites existentes de recall, autorretorno y
autocompletado siguen pasando.

`tests/drone_autorecall_reserve_smoke.py` cubre rechazo/devolución inmediatos,
descuentos al completar/fallar, presupuesto y prioridad de colas, revalidación al
iniciar, cambios de capacidad/umbral, esperas grandes, umbrales bajos, drones ya
agotados, diagnóstico localizado, guardado/carga, movimiento/reparación compuestos
y entrada real de Textual en ambos idiomas con debug pausado. Véase el [informe
de validación](../testing/drone-autorecall-review.es.md).
