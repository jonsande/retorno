# T-04A — validación de la mejora de velocidad

Implementado sobre HEAD actual; se conservó el cambio previo de `TODO.md` y se
excluyó de la entrega. Sin commit ni push. Cambio focalizado, sin auditoría general,
batería global ni reparaciones históricas ajenas.

El intérprete canónico ejecutó las comprobaciones registradas en
[la evidencia](engine-speed-upgrade-results.json). Cada entrada incluye comando,
PYTHONPATH, código de salida, tiempo y salida real.

| Comprobación | Resultado |
| --- | --- |
| Mejora de velocidad, referencia de crucero, relojes y antimateria (`pytest`) | 40 PASS, 50 subpruebas PASS |
| Nuevas pruebas T-04A solas (incluidas arriba) | 11 PASS, 36 subpruebas PASS |
| Estilo de manuales y parejas EN/ES | PASS |
| Límite de salto e integridad de rutas conocidas | PASS |
| Guardado/carga | PASS |
| Política de navegación del prólogo y fixture histórica de catálogo seed-1 | PASS |
| Política energética | PASS |
| Autocompletado, trabajos activos y tema de Textual | PASS |
| Retorno preventivo de drones | 17 PASS |
| IDs públicos, despacho CLI y entrada real Textual | 13 grupos PASS |
| Pools de módulos worldgen | Fallo histórico existente, descrito abajo |

Las 13 comprobaciones registradas contienen 12 aprobadas y un fallo histórico
conocido. `worldgen_modules_pool_smoke.py`, con `PYTHONPATH=src:.`, falla con
`ValueError: Historical universe seed/version changed` en `_assert_regions`.
Es el mismo fallo registrado en [los resultados previos](drone-autorecall-results.json)
y [los anteriores de motores](engines-antimatter-results.json), no una regresión
nueva de T-04A. La primera ejecución con solo `PYTHONPATH=src` falló al importar
`tests.fixtures`; la ejecución corregida es el resultado final. La nueva prueba
focalizada comprueba por separado que el módulo participa en el pool raro ordinario.
El retorno preventivo pasa aunque emite ResourceWarnings de subprocesos.
No se encontró ningún fallo final nuevo en las comprobaciones ejecutadas; no se
afirma que la batería global esté verde.

La cobertura incluye las cuatro bandas de velocidad, rechazo crítico/apagado,
imposibilidad de mejorar solo por salud, referencia nominal y multiplicadores
configurables, límite sublumínico sin redondearlo a 1c en pantalla, instalación/
retirada real mediante drones y duplicados, daño/reparación y ciclos eléctricos,
eficiencia y velocidad independientes, integridad y demanda eléctrica intactas,
cobro/reembolso de antimateria intactos, ETA galáctica y tiempo propio relativista,
daño en vuelo, retirada ya encolada completada en vuelo, reparaciones/instalaciones
posteriores, cambios de configuración nominal, guardado/carga activo con ambos
módulos y viaje local independiente. Las comprobaciones EN/ES cubren vistas
compartidas CLI/Textual, inspección, manuales, descripciones de help, estimaciones
y comandos reales de salida/diagnóstico/aborto por teclado en Textual. Las consultas
de duración respetan rutas adquiridas sin mutar estado ni revelar nodos ocultos.

Las fixtures existentes se adaptaron solo al contrato nuevo: tránsitos sintéticos
en pruebas de relojes/guardado aportan la velocidad congelada; el catálogo histórico
del prólogo excluye explícitamente el módulo de velocidad y el de eficiencia.

Límites pendientes: balance provisional (18 de chatarra y raro); se conservan las
restricciones ordinarias de drones, incluido soporte de drone_bay y bloqueo de
solicitudes nuevas de retirada en tránsito; sin migraciones antiguas, aceleración/
frenado ni conversión global de dominios temporales. No se cambian generación,
desgaste ordinario, radiación, hibernación/life_support ni narrativa procedural.
Los cambios del catálogo mantienen el requisito existente de partida nueva.

El [contrato de implementación](../systems/engines-antimatter.es.md) documenta
estados, fuentes de configuración, comandos y semántica del crucero inercial.
