# Motores y antimateria — validación

Base: commit canónico `bc95cae37c04c4cd20f9e205558766bb8bdbb066`, también HEAD del checkout.
Se conservó el cambio local previo en `TODO.md`. No se hizo commit ni push.

El intérprete del proyecto `/home/jon/prog/retorno_case/retorno_venv/bin/python`
ejecutó primero pruebas focalizadas y después los 83 scripts de pruebas
ejecutables y la colección predeterminada de pytest. Los programas de medición
/comparación y el envoltorio serial de la suite no son pruebas independientes.
Una copia temporal limpia de HEAD ejecutó la misma suite base de scripts
(82 antes de añadir la nueva prueba de integración). Las repeticiones finales
cubren la carga auxiliar ajustada, la integración y los fixtures dependientes
del catálogo modificados; sus resultados sustituyen ejecuciones intermedias.

| Comprobación | Resultado |
| --- | --- |
| Nueva integración de motores | 12 grupos CORRECTOS |
| Colección predeterminada de pytest | 17 CORRECTOS, 14 subtests CORRECTOS |
| Suite completa de scripts, con repeticiones finales | 65/83 CORRECTOS, 18 FALLOS |
| Base HEAD limpia | 61/82 CORRECTOS, 21 FALLOS |
| Estilo de manuales y parejas EN/ES | CORRECTO |
| Espacios en cambios de esta tarea | CORRECTO; excluido TODO.md preexistente |

Los 18 scripts que aún fallan también fallan en HEAD limpio. La suite
sigue en rojo; este cambio no afirma que todo el repositorio sea correcto.
Los resultados por script y sus excepciones finales están en
[el archivo de evidencia](engines-antimatter-results.json).

La integración nueva cubre inicio NOMINAL/0.90 y ausencia de security/securityd;
integridad normalizada y ejemplos canónicos de consumo; desgaste y reparación
real con dron; instalación, retirada y copias no acumulables del módulo;
combustible insuficiente sin modificar navegación/caché/RNG; agotamiento exacto;
viaje local; peticiones repetidas, llegada y aborto sin cobros duplicados;
guardado/carga en tránsito; consultas de rutas de solo lectura y comparaciones
negativas de datos ocultos; manuales, nombres/efectos del módulo y errores
bilingües; entrada real por teclado en Textual, cancelación, confirmación, cobro
y aborto en ambos idiomas. Pasan las pruebas existentes de cadena del prólogo,
política eléctrica, límite e integridad de rutas, relojes, viaje relativista,
guardado/carga, IDs públicos y Textual. El valor auxiliar final de 0.2 kW también
supera la hibernación de 15.23 años.

Los ajustes de fixtures conservan contratos sin cambiar reglas de producción:

- Los recorridos públicos omiten el comando de security retirado.
- El fixture de integridad de rutas fija la semilla antes de bootstrap en vez
  de modificar un universo ya fijado.
- El ejemplo original de dos uplinks de la semilla 1 congela explícitamente el
  catálogo anterior al módulo en datos desechables; la cadena garantizada y el
  prólogo normal siguen usando datos productivos actuales y consumen combustible.
- La sustracción de archivos se compara con los registros exactos sin filtrar,
  no con un recuento fijo dependiente del catálogo. Los ejemplos de radio excluyen
  fuentes/destinos protegidos y eligen un solapamiento real con el catálogo actual.
- Los fixtures de partidas anteriores a engines se rechazan explícitamente sin
  reescribirlos, según el contrato de partidas descartables; no hay migración nueva.

Fallos de base pendientes:

- `tests/authored_closing_shift_integration.py`
- `tests/deadnode_chain_detours_smoke.py`
- `tests/deadnode_chain_planner_smoke.py`
- `tests/deadnode_opportunity_selection_smoke.py`
- `tests/debug_lore_arcs_smoke.py`
- `tests/exploration_recovery_smoke.py`
- `tests/historical_information_smoke.py`
- `tests/lore_secondary_count_weights_hard_smoke.py`
- `tests/narrative_world_integration_smoke.py`
- `tests/nav_abort_waypoint_cleanup_smoke.py`
- `tests/radiation_hull_smoke.py`
- `tests/radio_spacetime_smoke.py`
- `tests/scan_observation_memory_smoke.py`
- `tests/structural_recovery_smoke.py`
- `tests/uplink_only_delivery_retry_smoke.py`
- `tests/worldgen_manifest_integration_smoke.py`
- `tests/worldgen_modules_pool_smoke.py`
- `tests/worldgen_preexistence_catalog_smoke.py`

Corresponden a fixtures históricos/de catálogo existentes, casos narrativos
protegidos, contratos de recuperación, un fixture superlumínico o aserciones de
radiación. No se han reparado modificando mecánicas ajenas.

El [contrato de implementación](../systems/engines-antimatter.es.md) documenta
comandos públicos, balance provisional, límites y pasos mínimos en Textual.
