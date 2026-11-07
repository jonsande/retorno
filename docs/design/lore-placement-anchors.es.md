# C2a — filtros de colocación relativa de lore

**ESTADO: IMPLEMENTADO para revisión externa, sobre HEAD 0bd02fa (2026-11-07).** Implementación: `src/retorno/core/lore.py`; prueba focal: `tests/lore_relative_placement_integration.py`. AMANECER permanece fuera del catálogo de producción.

## Necesidad
Permitir colocar una pieza de un arco o single en emplazamientos históricos certificados que satisfagan cotas de distancia euclídea 3D respecto a **una o varias identidades físicas**, aunque su ubicación sea lazy o variable por semilla. Mantener `min_dist_ly`, `max_dist_ly`, `regions_any` y las reglas existentes sin alteración.

## Sintaxis v1 (opcional)

```json
"constraints": {
  "max_dist_ly": 30,
  "anchor_distances": [
    {"anchor": "LIRIA", "min_ly": 0, "max_ly": 15}
  ]
}
```

Cada entrada refiere una identidad física canónica (ID o alias authored explícito). Los límites son números finitos no negativos, inclusivos; debe existir al menos un límite; ausencia de `min_ly` significa cero. Varias entradas se combinan con **AND**; no se introduce OR, distancia por grafo ni expresiones arbitrarias en v1. La semántica de `max_dist_ly` existente, respecto al inicio, permanece igual. El filtro afecta al **host del documento**, no a la posición física de la entidad declarada; para esa última se usa `world_requirements.entities[].position` y `relations.near`.

## Requisitos de implementación
- Resolver el ancla contra el manifiesto histórico y el snapshot compilado por semilla, **sin** exigir que se haya visitado, materializado o conocido. Si el ancla es inexistente, ambigua o no certificable, rechazar el catálogo antes de iniciar partida con diagnóstico por paquete/pieza/campo. No usar coordenadas `(0,0,0)` por defecto.
- Validación estricta: no aceptar silenciosamente listas vacías, claves desconocidas, `NaN`, `inf`, bool, negativos, cotas invertidas o referencia a un punto sin geometría estable. No alterar el comportamiento de piezas que no llevan `anchor_distances`.
- Aplicar el mismo predicado en la consulta física de hosts candidatos, la reserva/validación de piezas esenciales, la selección runtime y singles, de forma reproducible en EN/ES. No filtrar anclas ocultas en `status`, `map`, autocompletado o mensajes de error para el jugador.
- Conservar presupuestos finitos: una consulta sin testigo por presupuesto debe ser `not_evaluated`/incompleta, no prueba global de inexistencia. No crear historia, nodos, aristas o señales.
- Persistencia: snapshot y huella del catálogo, save/load y rechazo a cambios de catálogos instalados.

## Selección de hosts esenciales (optativa)

```json
"placement_rules": {"primary": {"host_selection": "seeded"}}
```

Por defecto la reserva de una pieza esencial usa el primer host viable ordenado por ID. `host_selection: "seeded"` elige reproduciblemente entre los testigos viables **dentro del ámbito certificado** utilizando semilla, clave de pieza y lista ordenada de identidades históricas. No garantiza que cada semilla escoja un host diferente ni una distribución uniforme en toda la galaxia. Runtime respeta **el mismo host**, incluso si otro candidato ya está materializado. Una reserva no disponible queda pendiente. Se rechazan modos desconocidos; esta opción pertenece solo a las reglas primary.

La validación se ejecuta durante bootstrap para todas las piezas, antes de reservar las esenciales, con el snapshot compilado y la geometría authored del manifiesto. Se excluyen anclas procedurales y la nave del jugador. Las consultas usan el dominio finito existente: las cotas relativas no lo amplían. La huella del catálogo y las reservas usan la persistencia existente, sin nuevo esquema. No cambian comandos, help ni manuales diegéticos porque son campos de autoría.

## Pruebas mínimas
1. Filtro geométrico: dentro, borde y fuera; ancla variable por semilla; múltiples reglas AND.
2. Errores: ID/alias inexistente, cota inválida, lista vacía, clave inválida y validación antes de empezar.
3. Misma semilla + orden distinto de catálogo + save/load => mismo host; cambio de semilla puede variar cuando hay varios testigos.
4. Reservas esenciales, singles y piezas no forzadas respetan el filtro; `host_selection` no cambia el default.
5. No divulgación de la posición del ancla y ninguna modificación de `worldgen` ni aristas.
6. Prueba narrativa focal AMANECER en catálogo temporal, y regresiones existentes de `narrative_world_integration_smoke.py` y `authored_closing_shift_integration.py`.
