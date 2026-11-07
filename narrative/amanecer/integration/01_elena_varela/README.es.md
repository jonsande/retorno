# AMANECER — Arco Elena Varela: integración C2 (borrador)

**No instalado; validado en catálogo temporal C2a.** Estos archivos bajo `narrative/` siguen siendo material de autoría. `constraints.anchor_distances` y `placement_rules.primary.host_selection` están implementados para revisión. `tests/lore_relative_placement_integration.py` verifica semillas 1, 29 y 701, hosts elegibles distintos para la pista, posición estable de Liria, LINK menor de 45 ly, asignación exclusiva de Elena, límites de conocimiento público, salvamento/lectura EN/ES y guardado/carga. La fixture de servicios traslada la nave a los hosts; queda sin verificar el viaje jugable completo desde el prólogo. No instalar en producción durante esta revisión.

## Decisiones aprobadas
- Liria es una estación histórica authored, explorable y abandonada en el presente. Su posición es variable y estable por semilla, a 6–9,6 años luz de HARBOR_12, sin crearla al leer una pista.
- Los cuatro registros originales de Elena permanecen en Liria; se conservan sus hechos, su ambigüedad y su lectura no secuencial. El documento privado no enviado permanece en archivo local, no se distribuye como correo enviado.
- La pista inicial es un registro administrativo **replicado antes del presente** en un host permitido, no un mensaje de Elena. Contiene un LINK válido HARBOR_12 → LIRIA y un sector vinculado por `spatial_bindings` a la semilla. El archivo no acredita tráfico histórico, supervivencia ni vínculos adicionales con la desaparición de los siete.
- HARBOR_12 sigue siendo candidato, no necesariamente anfitrión único. El contenido esencial no garantiza hallazgo o supervivencia.

## Datos propuestos
- `world_requirements` declara **una sola vez** LIRIA; `HARBOR_12` se referencia.
- Distancia a LIRIA desde el host de la pista: hasta 15 ly; además, a hasta 30 ly del inicio (filtro vigente). Solo estaciones y relés; fuente `salvage_data`.
- Selector opcional `host_selection: seeded` sobre los hosts certificados, para evitar que la reserva esencial favorezca sistemáticamente el primero por ID. Si solo hay uno, ese será el elegido. La semilla no debe reordenar un catálogo ni mutar estado de juego.
- Cuatro `secondary_lore_docs` forzados en Liria, por rutas `data/amanecer/...`; `secondary.count=4`. No se exige orden. La ventana de los pools no debe reabrirse.

## Instalación futura (no ejecutar ahora)
- Copiar `amanecer_elena_01.draft.json` como `data/arcs/amanecer_elena_01.json` **solo cuando** C2a esté implementada y probada.
- Copiar los diez `.txt` a `data/lore/packs/amanecer_elena_01/`, con los mismos nombres (sin `textos/`).
- Ensayar en catálogo temporal con C1 como precedente: varias semillas, variante ES/EN, destino real, límite de salto 45 ly, lectura de los cuatro registros con dron en Liria, no filtraciones, save/load, y demostrar que puede variar el host entre semillas cuando existen múltiples candidatos.
- No copiar el ZIP ni el JSON a producción por adelantado. El snapshot de catálogo instalado afecta la compatibilidad de guardados.

## Alcance pendiente
- La entrada de navegación es una ruta operativa, no una arista física histórica (`physical_link` no se declara). La accesibilidad del trayecto completo desde el prólogo necesitará validación jugable posterior.
- Los cuatro documentos no son objetos de `fs_files` authored: son secundarios programados para `salvage_data` en Liria. Esa diferencia importa para limpieza de pools, ventanas y pruebas.
- El módulo de planetas VAELOR, el Tábano y la Bruma quedan fuera de C2.
- Canon editorial: `narrative/amanecer/CANON.md`; el estado anterior «Liria por decidir» en `LOCATIONS.md` debe actualizarse al aprobar la instalación.
