# Contrato `historical-radio-v1` — 4D-3e5c-B2

[English](historical-radio.md). Implementado para revisión externa, 2026-11-07.
Autoridades: `worldgen/historical_radio.py`, `core/communications.py`,
`core/structural_recovery.py`, `model/world.py`, `config/balance.py`.
Pruebas: `tests/historical_radio_smoke.py` y las matrices authored existentes.

## Historia, equipo y energía

Una instalación certificada de clase `station`, `relay`, `waystation`, `ship`
o `derelict` procede de hardware de comunicaciones originalmente instalado.
Esto incluye pecios de esas clases. No presupone capacidad actual ni mensajes.
Los hosts con transmisor authored explícito conservan íntegramente esa autoridad;
no se añade una segunda historia procedural, incluso si `emissions` está vacío.

`RadioHistory` separa certificado físico, fecha relativa de instalación, estado
final del equipo, momento de avería/destrucción, final de disponibilidad energética,
programa de emisión, payload y referencia histórica. `equipment_at(t)` devuelve
instalación, conservación, energía y capacidad operativa en ese instante.

| Clase | Hardware original | Utilizable en t=0 | Averiado conservado | Destruido | Energía en t=0 | Capacidad operativa esperada |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| station | 100 % | 64 % | 20 % | 16 % | 62,5 % | 40 % |
| relay | 100 % | 81,25 % | 12 % | 6,75 % | 80 % | 65 % |
| waystation | 100 % | 71,4286 % | 15 % | 13,5714 % | 70 % | 50 % |
| ship | 100 % | 25 % | 40 % | 35 % | 40 % | 10 % |
| derelict | 100 % | 20 % | 30 % | 50 % | 25 % | 5 % |

Conservación y energía usan dominios de muestreo independientes. La capacidad
actual es su intersección, no otro sorteo ni el porcentaje de señales recibibles.
Conservado incluye equipo utilizable y averiado, excluyendo el destruido. Puede
haber energía con radio destruida o equipo intacto sin energía. La programación
puede estar ausente o terminada pese a disponer de capacidad operativa.

El modelo usa épocas gruesas: instalación entre 150 y 350 años antes de t=0;
avería/destrucción y pérdida de energía, cuando existen, entre 0,25 y 25 años
antes de t=0. Antes de sus límites el equipo se considera utilizable y alimentado.
Una emisión termina como máximo en el primer límite aplicable. Son parámetros
experimentales relativos al inicio del juego, sin fechas absolutas de civilizaciones,
supervivientes ni simulación electrónica. La destrucción describe las comunicaciones;
no elimina el emplazamiento físico ni sus archivos B1.

## Identidad, determinismo y procedencia

`RadioDefinition` fija versión, JSON canónico de reglas, huella de B1 y hosts
con precedencia explícita. La semilla física, el ámbito del manifiesto y la
identidad certificada entran en dominios SHA-256 separados. No se usa RNG mutable,
hash de Python, reloj del jugador, conocimiento, orden de visita/materialización
ni activación de recovery. Consultar una historia no altera `GameState`.

Se reutilizan `RadioEmitter` y `RadioEmission`. IDs procedurales:
`@HR1:<host>` y `@HR1:<host>:0`. El prefijo `@` queda fuera de la gramática
editorial authored y evita colisiones sin reservar IDs authored existentes.
`resolve_emission` unifica ambas procedencias. No existe otro ledger.

Hay como máximo un mensaje por host en esta versión. La existencia de programa
se sortea independientemente del estado actual. Perfiles comparados: escaso 30 %,
intermedio 55 % y abundante 80 %. Solo cambia ese umbral; equipo, energía, ventanas,
selección y sorteos conservan los mismos dominios entre perfiles. El perfil activo
sigue siendo `intermediate`; la comparación no cambia automáticamente el balance.

Entre programas, 65 % son `continuous`, 35 % `finite`. La repetición comienza
entre 30 y 120 años antes de t=0. Un programa continuo tiene además un 25 % de
probabilidad de cese programado; avería o falta de energía también lo cierran.
Un programa finito dura entre 0,02 y 6 años y termina antes de t=0, limitado por
hardware y energía. La repetición dentro de una ventana no es periodicidad: un
calendario periódico queda como extensión futura.

El 30 % de los programas intenta transportar navegación: solo selecciona un
`NavigationRecord` ya certificado por B1, de uplink o archivo tipado, con origen,
destino físico y distancia de hasta 45 ly. Se conserva `historical_connection`
frente a `navigation_solution`, ID del registro y la advertencia de antigüedad.
La ausencia de registro produce contenido ambiental, sin destino de reemplazo.
Las demás familias son baliza, telemetría grabada, aviso técnico, socorro histórico,
advertencia, anuncio de ruta ilegible, portadora ambiental y datos deteriorados.
Un equipo destruido puede conservar su último socorro. Todo payload tiene EN/ES;
no certifica actividad humana actual. No consume arcos, singles ni `piece_key`.

## Física, recepción y conocimiento

Se conserva [radio espacial/temporal](radio-spacetime.es.md): distancia euclidiana
3D, potencia normalizada 0,25/36/400 según equipo de emergencia/estación/relé,
sensibilidad del receptor y propagación a c. Referencia:
`game-coordinate-seconds-v1`, con ventana `[start_t+d*YEAR_S, end_t+d*YEAR_S)`.
Sin final, la ventana continúa abierta. El estado presente del host no bloquea
una onda emitida antes de una avería: energía pasada y recepción actual son hechos
distintos. Mover RETORNO modifica legítimamente retardo y cobertura.

Las puertas de comms, radiod, suministro, Core OS, tránsito e hibernación siguen
siendo comunes. Se comprueba el instante final de cada tick; no se reconstruyen
capturas de ventanas breves ya atravesadas. Apagar radiod impide captura, no emisión.
No cambian viajes, sensores, relojes generales, hibernación ni relatividad.

Preparación, captura, archivo, lectura/importación e intel siguen separados.
Identidad única `radio:<emission_id>` en `WorldState.radio_opportunities`.
Una captura guarda también posición y sensibilidad reales para validar su ventana.
La captura por sí sola no importa LINK ni añade contactos/coordenadas.

C-DATA-004: los eventos procedurales atribuyen la recepción a `comms`, no al host
oculto; nombres de archivos usan `radio` y secuencia, sin el ID físico. No se añade
el ID interno de oportunidad a esos eventos. El payload navegacional puede identificar
legítimamente sus extremos; el ambiental no revela host ni coordenadas. CLI y
Textual usan el mismo escritor/ledger. Status, diag, eventos, sonidos y completado
no reciben el catálogo oculto. Solo `debug radio`, explícito y de solo lectura,
muestra cursor, cantidad cacheada e historias examinadas.

## Descubrimiento completo en un ámbito acotado

No se generan ni indexan transmisores de toda la galaxia al arrancar. El inventario
inverso certificado de `historical-world-v1` proporciona fuentes no materializadas.
Para cada celda receptora de 10 ly, el ámbito completo es un cubo de 7×7×7 sectores
físicos, suficiente para el radio máximo actual UPGRADED de 30 ly. Se ordena por
cercanía de celdas y desempate estable. Completo significa ese ámbito, nunca la galaxia.

Por tick: como máximo cuatro sectores de inventario y 64 emplazamientos examinados
(incluidos silenciosos), con offset dentro de la celda para no perder el candidato
129. La otra mitad del presupuesto de 128 queda para emisores authored, con cursor
independiente; ninguno monopoliza al otro. La recepción procedural recorre hasta
64 historias cacheadas por tick con cursor circular. El límite 4096 se aplica a
historias con emisión por ventana de caché local. Al llenarla, primero se comprueba
cada candidato cacheado y después se continúa con la siguiente ventana desde el cursor
físico, sin favorecer permanentemente las primeras celdas. En modo de desbordamiento
se recorre de nuevo el ámbito tras la última ventana para reevaluar llegadas futuras;
es necesario al no caber todas las fuentes en memoria. Agotar un presupuesto no
demuestra silencio. La página pura devuelve `complete`.

La caché solo ocupa una zona local. Al cambiar de celda receptora se reinicia;
dentro de ella, un inventario que cabe completo en caché no se vuelve a explorar. Las emisiones
cacheadas se reevalúan temporal y espacialmente. La escucha no materializa sectores,
no crea archivos de navegación ni revela candidatos. Preparaciones ya existentes
continúan deduplicadas en el ledger común aunque cambie la zona.

## F-DEAD-01 y persistencia

El selector puede inspeccionar hasta 128 hosts de radio por búsqueda, además de
sus presupuestos previos. Prioriza orígenes accesibles y después cercanía; agotarlo
produce resultado incompleto si no se encuentra una cadena válida. Considera solo
el LINK exacto del payload certificado. Conserva la primera etapa accesible y
realmente llegada, protección de primaries, cobertura y ventanas. Mantiene la
restricción previa a repetición continua sin final para sus etapas de radio.
Una emisión recibida antes puede reutilizarse en una etapa posterior con su mismo
archivo y fecha, sin recaptura. La primera etapa conserva la regla de fuente aún
no recibida. Los mensajes ambientales no se convierten en avisos navegacionales.
No existe garantía universal de salida ni de supervivencia.

El esquema general 3 y contenedor V2 permanecen. Versionado específico en
`WorldState.radio_history_version`/`radio_definition`. Se persisten cursor de celda,
offset, caché local derivada y cursor de recepción. En desbordamiento persisten
también inicio de ventana y candidatos pendientes de comprobación. Save/load
reconstruye exactamente el segmento examinado de cada ventana para comprobarlos. También valida reglas, relación B1,
precedencia authored, payload, identidad canónica y evidencia física de las capturas.
Los guardados pre-B2 conservan `legacy-radio-v0`, sin ondas retrospectivas. Un
contrato incompatible se rechaza con el error comprensible existente, sin sobrescribir
el archivo. Los fixtures legacy existentes permanecen y se prueban.

## Medición y extensión futura

[Informe y matriz de validación](../testing/historical-radio-review.es.md).
La medición separa historia, potencial a sensibilidad nominal, cobertura en puntos
muestreados y recepción efectiva en recorridos públicos. Las tres densidades son
hipótesis experimentales. No se ajustan densidad física, topología, B1 ni salvage.

La futura reparación excepcional necesitaría estado conservado/reparable, energía
y dependencias físicas, archivo histórico y autorización de contenido preexistentes,
identidad de intervención, fecha real de inicio y su ledger persistente. Debe crear
una emisión posterior a la intervención y esperar su propagación. B2 no reactiva
reservas, reinicia, repara ni inventa transmisiones en nombre del failsafe. Tampoco
implementa electrónica general, redes poblacionales, interferencia o emisores móviles.
