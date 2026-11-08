# RETORNO — 4D-3e5c-P5c

[English](bilingual-salvage-review.md). Base:
`ebe16fb5592f481456b0d9992e24dce943facafd`.
`TODO.md` ya estaba modificado; se conserva sin tocar y no se empaqueta.

## Corrección

La asignación de `salvage_data` en `src/retorno/core/lore.py` prepara EN y ES
con el renderer existente cuando sus recursos resueltos y rutas normalizadas
son distintos. Valida las dos rutas contra archivos base e inyectados antes
de insertar archivos o registrar colocación; una colisión rechaza el conjunto.
Los dos archivos conservan una sola `piece_key`, nodo, canal y entrega. El
metadato de ruta del arco mantiene la variante del idioma activo al asignarse.

No cambian los textos, las restricciones narrativas, el host seleccionado ni
el límite de cuatro secundarios de Elena. Se mantienen la representación
anterior de contenidos monolingües, recursos compartidos y rutas únicas, y
los otros canales. No hay cambios en worldgen, navegación, B1/B2 o modo dios.
La corrección afecta a asignaciones nuevas; no migra ni rellena partidas viejas.

## Validación ejecutada

Intérprete `/home/jon/prog/retorno_case/retorno_venv/bin/python`, entorno
`PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`.

1. `tests/bilingual_salvage_smoke.py`: **PASS**.
   EN→ES y ES→EN; recuperación y lectura de los dos archivos de la pista y
   de los ocho archivos de los cuatro documentos. Todos los secundarios
   permanecen exclusivamente en LIRIA; cinco entregas lógicas en el arco
   (pista más cuatro documentos), con un solo descubrimiento de la pista.
   Salvamento repetido, relectura y guardado/carga conservan archivos y progreso.
   Colisiones EN/ES en archivos base/inyección rechazan la asignación sin
   ninguna mutación. Compatibilidad monolingüe, ruta compartida, texto inline
   y regresión existente de preferencia de canal/desbloqueo: **PASS**.
2. `lore_relative_placement_integration.test_amanecer()`: **PASS**, prueba
   existente focalizada en 1/29/701. Se retiró el reinicio artificial de
   colocaciones y archivos al cambiar de idioma; ahora usa las variantes
   preparadas originalmente. No se ejecutó el resto de su batería.
3. Sintaxis AST, enlaces nuevos y `git diff --check`: **PASS**.

Las pruebas reutilizan la fixture de servicios y trabajos reales de dron.
La fixture posiciona la nave para probar entrega; no vuelve a certificar ni
repite el recorrido del prólogo o las cadenas de navegación de P3.
Los contadores operativos de acciones siguen contando cada acción normal;
el segundo idioma no duplica colocaciones, entregas ni progreso narrativo.

## Archivos y entrega

- `src/retorno/core/lore.py`.
- `tests/bilingual_salvage_smoke.py`.
- `tests/lore_relative_placement_integration.py`.
- `docs/systems/lore-scheduler.es.md` y `.md`.
- `docs/testing/bilingual-salvage-review.es.md` y `.md`.

Contrato técnico: [Scheduler de lore](../systems/lore-scheduler.es.md).
No se añaden comandos o mensajes; help y manuales diegéticos conservan sus
flujos de salvamento, listado y lectura existentes.

ZIP incremental: siete archivos propios, más auditoría con base, comandos,
logs, evidencia JSON e inventario SHA-256/tamaños. El inventario excluye su
propio contenido. Sin `git add`, commit ni push. Detenido para revisión.
