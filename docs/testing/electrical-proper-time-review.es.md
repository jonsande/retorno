# T-04B1 — validación focalizada

Implementado sobre HEAD `8e4b9e924a3ca9aeff1fe6cf8e31a3ec0e1325c0`.
Se calcularon hashes de los 11 archivos modificados/nuevos iniciales y se
conservaron byte a byte, incluidos `TODO.md`, cambios de interfaz/relojes y las
pruebas T-04A existentes. Se excluyen de la entrega. Sin commit ni push.

Solo `src/retorno/core/engine.py` cambia comportamiento de producción. La
política eléctrica se extrae a `_integrate_power_interval`, con segundos propios
para batería y temporizadores de regulación. En la llegada solo se divide la
electricidad en movimiento/reposo. Los demás consumidores conservan intervalo
galáctico, orden y frecuencia; no se añade esquema, valor de balance, llamada
narrativa ni bucle por segundo. Documentación y manuales tienen cambios EN/ES
parejos. No hacen falta cambios de sintaxis, descripciones de help o textos de
eventos: las lecturas eléctricas conservan unidades y significado.

Todas las comprobaciones usan Python canónico y `PYTHONPATH=src:.`. Los
comandos, resultados y salidas exactos están en
[la evidencia](electrical-proper-time-results.json).

| Comprobación | Resultado |
| --- | --- |
| Smoke eléctrico existente, antes de modificar | PASS |
| Pruebas nuevas de electricidad + relojes y antimateria existentes | 41 PASS, 23 subpruebas PASS |
| Regresión existente de módulo inercial/guardado/carga, prueba seleccionada | 1 PASS, 10 omitidas |
| Smoke eléctrico existente, después de modificar | PASS |
| Estilo de manuales y parejas EN/ES | PASS |

Las 17 pruebas nuevas cubren reposo (incluido CRUISE estacionario), 0.5c y 0.8c,
balance positivo/negativo/nulo, límites y eficiencias de carga/descarga, batería
llena/vacía, persistencia y recuperación de brownout en tiempo propio, apagado
retardado por baja calidad y reinicio del contador, llegada atravesada y exacta,
cambios de generación/consumo antes y después de llegada mediante un trabajo
real de módulo, reparto de temporizadores, equivalencia en circuitos estables
entre intervalos largos/cortos, daño y cambio de referencia nominal con velocidad
congelada, antimateria/aborto intactos, guardado/carga nuevo con temporizadores,
movimiento local, hibernación sin factor biológico en electricidad y un siglo
con una integración eléctrica y una llamada narrativa. Las pruebas de llegada
comprueban además que trabajos, desgaste, casco, radiación, mantenimiento de
drones y consecuencias de soporte vital no se subdividen ni reciben tiempo propio.

No aparece ningún fallo final. No se ejecutó batería global ni se repararon
pruebas históricas ajenas; no se afirma que todo el repositorio esté verde.
El apagado automático existente puede aislar `power_core`; la fixture de
recuperación de brownout lo vuelve a encender, sin modificar esa política.

Las dependencias y límites restantes están en
[el contrato de implementación](../systems/electrical-proper-time.es.md):
calidad/brownout siguen influyendo en desgaste y disponibilidad de drones/
trabajos, que conservan tiempo galáctico. La política muestreada no reconstruye
todas las transiciones de batería o trabajos dentro de un tick largo. Las
previsiones de recuperación conservan estimaciones aproximadas de energía por
duración galáctica, fuera deliberadamente de esta migración eléctrica activa.
No se añaden migraciones de guardados antiguos.
