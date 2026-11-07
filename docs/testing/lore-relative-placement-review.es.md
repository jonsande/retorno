# RETORNO — revisión 4D-3e5c-C2a

Base: `main` local, `0bd02fa` (2026-11-07). Sin staging, commit ni push.

## Cambios

- `src/retorno/core/lore.py`: predicado compartido de distancias relativas y
  validación en bootstrap de todas las piezas, incluidos singles opcionales;
  reserva primary seeded optativa; respeto del host reservado al buscar y asignar.
- `tests/lore_relative_placement_integration.py`: comprobaciones focales de esquema,
  geometría, AND/bordes/alias, defecto/seeded, reservas, piezas opcionales y singles;
  catálogo temporal AMANECER con el JSON y los diez textos suministrados.
- Contrato narrativo, diseño de filtros relativos y README de integración EN/ES:
  semántica implementada y límites verificados. No hay comandos ni help nuevos.

## Validación

Usar `/home/jon/prog/retorno_case/retorno_venv/bin/python` con cada script:

| Script | Resultado |
| --- | --- |
| `tests/lore_relative_placement_integration.py` | PASS |
| `tests/narrative_world_integration_smoke.py` | PASS, 20 comprobaciones |
| `tests/authored_closing_shift_integration.py` | PASS, tres semillas y viaje EN/ES |

AMANECER usa solo semillas 1, 29 y 701. Liria existe en el manifiesto histórico
antes de descubrirse y conserva su posición compilada por semilla al materializarse.
La pista cumple la cota vigente de 30 ly al inicio y la nueva de 15 ly a Liria;
HARBOR_12–Liria queda por debajo de 45 ly. Estas semillas tienen varios hosts
certificados elegibles y eligen tres hosts procedurales distintos. Los cuatro
registros de Elena se asignan solo a Liria. Pasan salvamento con dron EN/ES,
cuerpos de texto exactos, rutas, lectura/importación del LINK, persistencia de
reservas/entregas y rechazo de catálogos modificados. Status, diagnóstico comms,
contactos y mapa normales no revelan los datos ocultos; las consultas preservan
el estado serializado. Se conserva el catálogo de producción.

## Límites y entrega

La fixture de servicios traslada la nave a los hosts; no se certifica un viaje
AMANECER completo desde el prólogo. Las búsquedas conservan el ámbito finito
existente y la semántica `not_evaluated` por presupuesto. Se excluyen anclas
procedurales y la nave del jugador. Seeded no implica muestreo uniforme galáctico
ni variación con un solo candidato. No se ejecutó la batería completa ni barridos
amplios de semillas.

Sin cambios en worldgen, F-DEAD-01, balance, recursos, audio, Textual, catálogo de
producción o textos originales de `narrative/amanecer/arcs/`. Los cambios previos
de `TODO.md` permanecen intactos y quedan fuera del ZIP. Los documentos de diseño
y borrador previamente no versionados siguen en su lugar; el JSON y diez textos
se incluyen intactos como dependencias de prueba nuevas respecto a HEAD.
El inventario del ZIP registra SHA-256 y procedencia.
Se detiene aquí para revisión externa; AMANECER no está instalado.
