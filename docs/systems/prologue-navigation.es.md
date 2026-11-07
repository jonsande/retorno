# Garantía histórica del prólogo — P3

[English](prologue-navigation.md). Implementado: extensión
`historical-prologue-chain-v1` de `historical-world-v1` y
`historical-information-v1`. No es una migración de partidas.

## Construcción y demostración

`worldgen/narrative.prepare_new_world` compila el catálogo y sus reservas
narrativas esenciales antes de reservar esta cadena. `manifest.reserve_prologue`
examina exactamente las nueve cohortes del vecindario inicial de ECHO_7.
Selecciona por hash estable de semilla e identidad un sitio procedural con
`salvage_data`, no reservado ni protegido, y a distancia positiva y como máximo
45 ly de ambos anclajes. ARCHIVE_01, como cualquier sitio authored, queda fuera.

Si el conjunto admisible está vacío, añade un único slot procedural `derelict`
al manifiesto inicial. Con los anclajes instalados ECHO_7=(0,0,0) y
HARBOR_12=(12,4,0), su posición pertenece a
`[4,6) × [1,3) × [0.1,0.2)`, determinada por un RNG local de la semilla.
Todo ese volumen está estrictamente dentro de ambas bolas de radio 45 ly y
excluye los anclajes. Esta desigualdad y la alternativa exhaustiva
«candidato admisible / conjunto vacío» establecen la garantía para cualquier
semilla válida; los ejemplos de semillas no son la demostración.

El slot ocupa el siguiente índice procedural libre de su cohorte. Se añade
después de muestrear sitios, hubs y aristas ordinarias; no cambia esos sorteos,
identidades ni conexiones. No necesita una arista física histórica: sus dos
saltos pueden ser soluciones navegacionales calculadas. Consultas por identidad,
inventario físico inverso y materialización ordinaria usan el mismo manifiesto.
La reserva se fija antes de explorar y no depende del orden de visitas.

Un catálogo con anclajes o restricciones incompatibles se rechaza, sin cambiar
semilla, relajar protecciones o aceptar una garantía parcial. No se promete
compatibilidad de esta caja con posiciones arbitrarias de los anclajes.

## Adquisición pública y conservación

`information.query_information` realiza primero la selección ordinaria y aplica
P1. Si falta el intermediario, añade su registro al uplink de ECHO_7; si ya hay
tres destinos, sustituye únicamente el último. Si ya estaba, conserva la lista.
No rellena con una ruta directa a HARBOR_12 ni modifica documentos authored.

En el intermediario se conserva `/data/nav/waystation_solution.txt`, con acceso
`guest`, registro tipado B1 y contenido bilingüe del renderer existente:
`LINK: P -> HARBOR_12`. Es un archivo base recuperable mediante
`dock`, `drone deploy`, `drone salvage data`, lectura e importación habituales.
No depende de ventanas, sorteos de archivos, radio ni recuperación posterior.
La ruta al intermediario se adquiere haciendo uplink en ECHO_7. El jugador
todavía debe viajar, recuperar datos y leerlos para utilizar la segunda ruta.

El slot adicional queda fuera de los pools ordinarios ponderados para no
reordenar historias existentes; su registro de entrada es la reserva explícita.
B2 consulta la proyección B1 sin ambas reservas nuevas. No cambia su pool
ordinario ni sus sorteos, no prohíbe pistas alternativas preexistentes y el
derelict adicional no declara equipo radio. Así la nueva garantía no produce
una emisión recibible en ECHO_7 con el LINK reservado hacia HARBOR_12.

## Contrato y certificación

`ManifestDefinition` captura versión, identidad elegida, exclusiones iniciales
y, cuando corresponde, el slot de respaldo. `InformationDefinition.prologue_json`
captura versión y host y participa en la huella informativa completa; su
proyección de muestreo conserva la huella B1 ordinaria. B2 vincula esa huella
completa, pero usa el muestreo ordinario. La extensión física no cambia el
ámbito de las identidades previas. Cambiar estas reglas requiere versionar
explícitamente la extensión.

`information.certify_prologue` se ejecuta al preparar y guardar/cargar:
reconstruye la elección física y comprueba identidad, distancias, restricciones,
interfaces, registro efectivo de uplink, límite de tres, ausencia de ruta directa
procedural y archivo base legible/importable. La primera pista está en ECHO_7;
la segunda en el destino que habilita esa primera pista: no hay dependencia
circular. No importa intel, activa pools, consume RNG ni cambia el reloj.
Las partidas anteriores con los anclajes pero sin este contrato se rechazan.

Prueba focal: `tests/prologue_chain_smoke.py`. Cubre 1/29/701, exclusiones P1,
respaldo controlado, inventario/materialización, certificados negativos,
ausencia de filtración del estado oculto en status, B2, FAST_SANDBOX,
salvamento/lectura/importación EN/ES, guardado/carga y recorrido público.
Conserva además el recorrido alternativo de dos uplinks observado en semilla 1.

No cambian comandos, help ni manuales diegéticos: los flujos son existentes y
esos textos no deben revelar la reserva secreta. No se modifican supervivencia,
tiempos, lore, modo dios ni criterios de finalización del prólogo.
