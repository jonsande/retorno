# Operación AMANECER — Paquete narrativo consolidado

**Estado:** borrador narrativo consolidado v0.4 (no implementado como lore jugable).  
**Contenido:** 3 arcos / 14 documentos de arcos (4 + 6 + 4) y 9 singles; **23 documentos narrativos** en total.

Este directorio se incorpora dentro de `narrative/` en el repositorio. No debe copiarse en `retorno/data/arcs/` ni `retorno/data/lore/packs/` sin una fase de conversión técnica: faltan JSON, TXT bilingües y decisiones de integración procedural.

## Estructura
- `arcs/01_elena_varela/`: cuatro documentos de Elena (arco 01).
- `arcs/02_the_searchers/`: cuatro documentos del viaje y **dos registros exclusivos del pecio Tábano** (`05_the_route.md` y `06_last_watch.md`).
- `arcs/03_the_sixth_transport/`: cuatro documentos de Mara Soler (arco 03).
- `singles/`: nueve documentos independientes, incluido el albarán de VAELOR.
- `CANON.md`: canon editorial consolidado y niveles de conocimiento.
- `LOCATIONS.md`: política de lugares, aparición y dependencias navegables.
- `CONTINUITY_REVIEW_v0.1.md`: revisión previa, preservada como histórico.
- `WORLD_VAELOR.md`, `CONTINUITY_ARC02.md`, `CONTINUITY_ARC03.md`, `CANON_ARC01.md`, `SINGLES_BATCH_01.md`: notas previas para trazabilidad.

## Decisiones editoriales
- Lou Levy es **hombre**, capitán del **Tábano**, procedente de **THALLOINOV** (VAELOR). Su pasajero es **Leopold Devorák**; su madre, **Leda Devorák**.
- El *Tábano* debe generarse como **pecio explorable**, situado por el generador; Lou y Leopold mueren a bordo antes de llegar a la instalación que sospechaban encontrar.
- Los documentos 05 y 06 del arco 02 solo se colocarán dentro del pecio. La copia de ruta allí guardada debe transformarse posteriormente en un **destino navegable dinámico**, no en coordenadas literales.
- La *Bruma*, sexto transporte de AMANECER, debe existir en el universo. VAELOR y sus planetas deben ser reconocibles como entorno de exploración; su población humana ha desaparecido en el presente jugable.
- Mencionar lugares no obliga a generarlos; véase `LOCATIONS.md`.
- Los textos originales de los arcos y singles se conservan en sustancia. Se ha corregido la errata de género en el README del arco 02, y se han normalizado nombres de carpeta/archivo del arco 01.

## Pendientes al integrar
Comprobar el esquema real de entidades persistentes, cómo reservar un nodo del mundo para cada nave y la instalación, la representación de VAELOR, y cómo descubrir las coordenadas mediante el sistema de intel sin romper el orden libre de lectura. El single 01 aún contiene `[SECTOR_VAELOR]`, marcador editorial intencional. No se han inventado coordenadas.
