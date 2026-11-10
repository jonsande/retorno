# T-04B2 — validación focalizada

Base: `main` limpio, HEAD `1b963eac3da5905549ce00209dfc3c6c84cdce52`.
Ya incorporaba T-04A, T-04B1 y CANON v0.6.0. Sin commit ni push, rediseño de
navegación, cambios de balance, auditoría general ni batería global.

Solo `src/retorno/core/engine.py` cambia comportamiento de producción. El desgaste
ordinario de sistemas/casco usa segundos propios y conserva sus modificadores.
Los tramos de llegada de T-04B1 aportan duración y muestras eléctricas; el desgaste
sigue en su fase existente, con contexto explícito de movimiento en el primer
tramo. Se sincronizaron documentación técnica y manuales de mantenimiento/
radiación/motor EN/ES. No hacen falta cambios de comandos, help ni textos de eventos.

El intérprete canónico ejecutó las pruebas focalizadas con `PYTHONPATH=src:.`.
Comandos, tiempos, salida exacta, referencia de HEAD limpio y comprobaciones de
funciones preservadas están en [la evidencia](wear-proper-time-results.json).

| Comprobación | Antes | Final |
| --- | --- | --- |
| Pruebas existentes de electricidad, velocidad/módulos, antimateria, relojes y crucero | 57 PASS, 64 subpruebas PASS | Incluidas debajo |
| Pruebas anteriores + 13 nuevas de desgaste ordinario | — | 70 PASS, 80 subpruebas PASS |
| Smoke eléctrico existente | — | PASS |
| Smoke existente de interpolación radiológica en tránsito | — | PASS |
| Estilo de manuales y parejas EN/ES | — | PASS |
| Smoke existente de radiación/casco | Fallo histórico | Mismo fallo histórico |

`radiation_hull_smoke.py` falla en línea 183 con `AssertionError: []`, al esperar
un evento de radiación ambiental. Se reprodujo en HEAD limpio antes de editar
y falla idénticamente después. No se modificó ni reparó esa prueba. No aparece
ningún fallo final nuevo en las comprobaciones ejecutadas; no se afirma que
todo el repositorio esté verde.

La cobertura nueva incluye reposo y CRUISE estacionario equivalentes; 0.3c/0.5c/
0.8c; tasas configuradas de sistemas individuales y casco; modificadores de
calidad, brownout, radiación, NORMAL/CRUISE e hibernación de casco conservados;
llegadas atravesadas/exactas; condiciones eléctricas diferentes por tramo;
ticks largos/subdivididos estables; transiciones LIMITED/DAMAGED/CRITICAL sin
cambiar velocidad/ETA/tiempo propio congelados; rechazo de salida futura;
dosis/mantenimiento de drones galácticos intactos; procesamiento único de
trabajos, narrativa, radio y recuperación; muestreo ambiental grueso en destino;
daño instantáneo; continuación tras guardado/carga nuevo; y reducción de reactor
reflejada por la electricidad del tick siguiente, sin reproducirla retroactivamente.

Solo se adaptaron fixtures existentes cuyas suposiciones invalida T-04B2:
la aserción del argumento temporal de desgaste espera segundos propios, las
llamadas de llegada esperan dos tramos y las tasas aceleradas de daño de pruebas
eléctricas/velocidad se expresan por segundo a bordo para conservar sus escenarios
de motor dañado. No se ajustó ninguna tasa de producción.

La igualdad AST respecto a HEAD confirma que no cambian el integrador eléctrico,
batería, cálculo de generación/carga, despacho de acciones/navegación, fórmula
de antimateria, dosis, mantenimiento de drones, consecuencias de soporte vital
ni daño instantáneo de casco. Balance y canon también permanecen intactos.

Se conservan simplificaciones: muestras finales de calidad/brownout por tramo;
radiación de destino al llegar, sin reconstruir exposición del corredor;
blindaje muestreado antes del desgaste diferido; jobs/reparaciones en su fase
galáctica existente; sin reconstrucción continua de salud, batería o umbrales.
Drones, dosis, trabajos y reglas de soporte vital conservan sus dominios previos;
flujo radiológico/medios interestelares requieren diseño posterior. No se
implementan selección de velocidad v0.6, escalera de combustible ni techos nuevos
para motores dañados mejorados.

Tras verificarlo, debe actualizarse la descripción de implementación de
A-TECH-005 para marcar resuelta la discrepancia de envejecimiento ordinario de
sistemas/casco. Maniobras locales, aceleración/frenado y cambios de velocidad
en tránsito siguen abiertos. No se reescribió ninguna decisión canónica.

[Implementación y política de muestreo](../systems/wear-proper-time.es.md).
