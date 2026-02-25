


lore/hubs authored  --->  lore/hubs fijos (no procedurales)




NOTAS (limpiar)


¿Qué es un hub? ¿Qué significa "hub"?

En el juego, “hub” es un nodo “centro” del sector: el punto principal de conectividad.
A nivel técnico, is_hub=True significa:

Es el nodo que conecta al resto de nodos del sector.
Es el que suele enlazar con hubs de sectores vecinos.
En el worldgen procedural, se elige un hub por sector y se crean enlaces hacia él.
Por eso hubs suelen ser relay, station o waystation: son el “nodo de tránsito”.
Un derelict o ship puede existir en el sector pero no es el nodo central.

==


Por qué ship_1.json tiene node_id: RETORNO_SHIP
Ese archivo usa el schema de “location” para almacenar fs_files del barco.
El node_id ahí no se añade al mundo porque en bootstrap se ignora cualquier location cuyo node_id sea igual a state.ship.ship_id.
Es decir: se usa solo como contenedor de archivos de la nave.

Si quieres, puedo refactorizar esto para que el fs_files de la nave esté en un archivo propio sin node_id, pero hoy el sistema de carga está pensado para “locations” y por eso aparece así.

SPOILERS!

Solución al puzzle/tutorial inicial:

drone deploy! D1 PWR-A2

Si falla...
    drone reboot D1   (tantas veces como haga falta)
    drone deploy! D1 PWR-A2

drone repair D1 power_core
drone repair D1 energy_distribution
drone recall D1
boot sensors
scan
dock ECHO_7
---
drone deploy D1 ECHO_7
drone salvage modules D1
drone salvage scrap D1 30
drone salvage modules D1
cargo audit
drone recall
power plan audit
travel DERELICT_A3
hibernate until_arrival

DEBUG

Instalar la UI de Textual:
pip install -e .[ui]

Arrancar con UI Textual:
python -m retorno.ui_textual.app

Saltar prólogo:
Iniciar con RETORNO_SCENARIO=sandbox python -m retorno.cli.repl
Dentro del juego, se puede cambiar de escenario con:
debug scenario prologue
debug scenario sandbox
debug scenario dev


===================

1. Por qué migrar también los manuales a JSON? Ventajas y desventajas?
2. Sí, añade plantillas y generaión procedural por región, pero teniendo en cuenta la orden que te voy a dar más abajo (ver más abajo).
3. A qué te refieres con hacer que *.json quede deprecado/eliminado?

Implementar generación procedural del “mundo” (WorldGen v0) con:
- Galaxia organizada por regiones (halo/disc/bulge) derivadas de coordenadas.
- Sectores fijos (grid 2.5D) usados para generación lazy determinista.
- Sitios (SpaceNode) generados por sector bajo demanda.
- Scan por radio (ly), no por sector completo.
- Descubrimiento de nuevos destinos por “intel” (nav fragments) además de scan.

Decisiones v0:
- Sector fijo: SECTOR_SIZE_LY = 10.0
- 2.5D: coords x,y en ly; z existe pero pequeña (disco) o más dispersa (halo).
- Scan radius inicial: ship.sensors_range_ly = 2.5 (módulos podrán aumentarlo más tarde).

A) Modelos nuevos/extendidos

1) WorldState
Archivo: src/retorno/model/world.py
- Añadir:
  current_node_id: str
  current_pos_ly: (x,y,z) o derivable del nodo actual
  known_nodes: set[str] (node_ids conocidos)
  known_intel: dict[str, dict] (opcional: metadata “known via intel”)
  generated_sectors: set[str] (sector_ids generados)
- Añadir función:
  sector_id_for_pos(x,y,z) -> str (ej "S+001_-003_+000")
  region_for_pos(x,y,z) -> "halo"|"disk"|"bulge"

2) ShipState
Archivo: src/retorno/model/ship.py
- Añadir:
  sensors_range_ly: float = 2.5

3) SpaceNode
Archivo: src/retorno/model/world.py (SpaceNode)
- Asegurar coords:
  x_ly,y_ly,z_ly
  kind ("station","derelict","ship","relay", etc.)
  region (opcional cache)
  salvage_* ya existente

B) Generador determinista lazy

Crear: src/retorno/worldgen/generator.py
- Función:
  ensure_sector_generated(state: GameState, sector_id: str) -> None
  - Si sector_id ya en state.world.generated_sectors: return
  - Derivar seed_sector determinista:
      seed = hash64(state.meta.rng_seed, sector_id)
    (usar tu helper determinista existente)
  - Generar N nodos según región:
      disk: 2..5
      halo: 0..2
      bulge: 3..7
  - Para cada nodo:
      - coords aleatorias dentro del cubo del sector (x in [sx*L, (sx+1)*L), etc.)
      - z dispersión por región (disk sigma 0.3; halo sigma 2.0; bulge sigma 0.8)
      - kind por weights según región
      - node_id determinista (p.ej f"{sector_id}:{i:02d}" o hash corto)
      - name generado (p.ej "Relay-7", "Derelict A-3", etc.) determinista
      - salvage_scrap_available y salvage_modules_available según kind/region (usando el mismo seed system)
    Insertar en state.world.space.nodes (o estructura equivalente)

- También generar 1 “hub” fijo al inicio (ECHO_7) en el sector inicial, si no existe.

C) Scan por radio (no sector completo)

Archivo: CLI handler scan (y/o Engine action)
- Al ejecutar scan:
  1) Obtener posición actual (coords del nodo actual)
  2) Calcular sector_id actual y sectores vecinos a considerar:
     - como scan_radius < sector_size, basta con sector actual
     - si quieres robustez, incluir sectores adyacentes si el radio toca borde (optional)
  3) ensure_sector_generated para los sectores relevantes
  4) Filtrar nodos por distancia <= ship.sensors_range_ly
  5) Mostrar solo esos nodos
  6) Añadirlos a known_nodes (descubiertos por scan)

D) Travel restringido a destinos conocidos
- travel <node_id> debe requerir:
  node_id en known_nodes OR en known_intel (descubierto por intel)
- Si no, bloquear con hint:
  "Unknown destination. Use scan or acquire navigation intel."

E) Intel / nav fragments (v0 minimal)
- Añadir un tipo de “intel” como archivo de datos en salvaged mails/logs:
  por ejemplo: /data/nav/fragments/frag_0001.txt con contenido:
    NODE: HARBOR_12
  o:
    COORD: x,y,z
- Implementar comando:
  intel import <path>
  que lee el archivo desde FS y añade node_id (o sector) a known_intel y known_nodes.
  (Si prefieres, integrar esto en `cat` cuando el path está bajo /data/nav/…)
- v0 puede ser simple: cuando cat detecta línea "NODE:", auto-add.

F) Región como bioma (solo datos por ahora)
- Añadir a SpaceNode:
  radiation_base (float) derivada de región
- A futuro se usará para degradación/radiación.

Aceptación:
- El mundo no se genera entero, solo sectores escaneados/visitados.
- scan solo muestra nodos dentro de sensors_range_ly.
- travel solo permite a nodos conocidos.
- Al importar intel (nav fragment), se añade un destino nuevo que antes no aparecía en scan.
- Determinismo: con el mismo rng_seed, el mismo sector genera los mismos nodos.

NOTA: No implementar habitaciones/decks todavía.








Cuándo tendría interés desactivar el auto-CRUISE (más adelante)

Cuando implementes al menos una de estas cosas:

eventos de ruta que solo detectas si sensores están activos

amenazas que requieren security online

trabajos en tránsito (reparación, auditoría, análisis) que consumen carga pero te ahorran tiempo al llegar

viaje corto (días) dentro del mismo “vecindario” donde no hibernas

En ese momento, NORMAL deja de ser “castigo” y pasa a ser una opción táctica.