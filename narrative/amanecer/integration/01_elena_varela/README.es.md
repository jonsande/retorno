# AMANECER — Arco Elena Varela: integración C2 (borrador)

**C2b: instalado en el catálogo del árbol de trabajo para revisión externa; acceso exploratorio pendiente de demostrar.** `data/arcs/amanecer_elena_01.json` y los diez recursos de `data/lore/packs/amanecer_elena_01/` son copias exactas del borrador aprobado. Se conservan el borrador y los manuscritos originales. El recorrido público acotado de la semilla 701 no descubrió el host de la pista ni Liria; terminó con bloqueos de mantenimiento/recursos. No prueba inaccesibilidad global. Véase la [revisión C2b](../../../../docs/testing/amanecer-productive-review.es.md) antes de promover.

Validación histórica C2a: `tests/lore_relative_placement_integration.py` verifica semillas 1, 29 y 701, hosts elegibles distintos para la pista, posición estable de Liria, LINK menor de 45 ly, asignación exclusiva de Elena, límites de conocimiento público, salvamento/lectura EN/ES y guardado/carga. Su fixture de servicios traslada la nave a los hosts y por tanto no prueba un recorrido público.

## Decisiones aprobadas
- Liria es una estación histórica authored, explorable y abandonada en el presente. Su posición es variable y estable por semilla, a 6–9,6 años luz de HARBOR_12, sin crearla al leer una pista.
- Los cuatro registros originales de Elena permanecen en Liria; se conservan sus hechos, su ambigüedad y su lectura no secuencial. El documento privado no enviado permanece en archivo local, no se distribuye como correo enviado.
- La pista inicial es un registro administrativo **replicado antes del presente** en un host permitido, no un mensaje de Elena. Contiene un LINK válido HARBOR_12 → LIRIA y un sector vinculado por `spatial_bindings` a la semilla. El archivo no acredita tráfico histórico, supervivencia ni vínculos adicionales con la desaparición de los siete.
- HARBOR_12 sigue siendo candidato, no necesariamente anfitrión único. El contenido esencial no garantiza hallazgo o supervivencia.

## Datos aprobados
- `world_requirements` declara **una sola vez** LIRIA; `HARBOR_12` se referencia.
- Distancia a LIRIA desde el host de la pista: hasta 15 ly; además, a hasta 30 ly del inicio (filtro vigente). Solo estaciones y relés; fuente `salvage_data`.
- Selector opcional `host_selection: seeded` sobre los hosts certificados, para evitar que la reserva esencial favorezca sistemáticamente el primero por ID. Si solo hay uno, ese será el elegido. La semilla no debe reordenar un catálogo ni mutar estado de juego.
- Cuatro `secondary_lore_docs` forzados en Liria, por rutas `data/amanecer/...`; `secondary.count=4`. No se exige orden. La ventana de los pools no debe reabrirse.

## Estado de promoción
Las copias C2b están preparadas, sin cambios de motor. Pasan las comprobaciones estructurales productivas; queda pendiente una secuencia completa de adquisición y viaje públicos. No se ha añadido ninguna pista ni ruta correctiva. El contrato vigente de huella rechaza guardados de un catálogo instalado distinto; conservar su catálogo original.

## Alcance pendiente
- La entrada de navegación es una ruta operativa, no una arista física histórica (`physical_link` no se declara). La accesibilidad del trayecto completo desde el prólogo necesitará validación jugable posterior.
- Los cuatro documentos no son objetos de `fs_files` authored: son secundarios programados para `salvage_data` en Liria. Esa diferencia importa para limpieza de pools, ventanas y pruebas.
- El módulo de planetas VAELOR, el Tábano y la Bruma quedan fuera de C2.
- Canon editorial: `narrative/amanecer/CANON.md`; la decisión sobre Liria y su estado anterior pendiente constan en `narrative/amanecer/LOCATIONS.md` y `LOCATIONS.en.md`.
