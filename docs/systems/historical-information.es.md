> **P3 implementado:** la extensión `historical-prologue-chain-v1` reserva una cadena procedural antes de explorar; puede añadir un único slot inicial. Conserva los sorteos ordinarios y aísla la reserva de B2. Véase [Garantía histórica del prólogo](prologue-navigation.es.md), que precisa estas excepciones a las reglas base descritas debajo.

# Información histórica procedural — historical-information-v1

[English](historical-information.md). Implementado para revisión externa en
4D-3e5c-B1, sobre `445217e4503f9077c6dd53aef7c6cf9f53cf5b24`.

## Autoridad y seis hechos separados

`worldgen/information.py` proyecta hechos certificados de `historical-world-v1`
en archivos y registros navegacionales finitos. No añade otro generador físico,
registro global mutable, transmisor ni emisión. La preparación de partida nueva
captura una `InformationDefinition`; worldgen ordinario no activa pools de datos.

1. El manifiesto histórico determina existencia y relaciones físicas.
2. La definición informativa determina los registros históricos conservados.
3. Interfaces físicas y gates operativos/narrativos determinan disponibilidad.
4. Uplink, salvage o recepción recuperan registros.
5. Lectura/importación consume sus pistas inteligibles.
6. La publicación operativa validada modifica contactos y `known_links`.

Una consulta interna no modifica ninguno de los cuatro hechos finales.
Bootstrap/scan, solve manual, documentos authored y radio existente conservan
sus reglas de descubrimiento. Rige la [matriz B0](information-capabilities.es.md).

## Entradas capturadas, identidad y reglas

Las entradas estables son semilla/ámbito del universo, `SiteIdentity`, tipo y
posición certificados, aristas históricas incidentes, datos authored capturados
de archivos/tablas y reglas informativas versionadas. El núcleo recibe
`ManifestDefinition` e `InformationDefinition`, nunca el estado del jugador.
No consulta hora, nodos/rutas conocidos, visitas, contadores de uplink, RNG de
gameplay ni necesidades de recuperación.

`rules_key = SHA256(canonical_json((version, rules_json, authored_json)))`.
JSON canónico ordena claves, usa separadores compactos, UTF-8 y números finitos.
El snapshot guarda revisión del núcleo, dominio, límite de rutas, cap, pesos y
las seis probabilidades existentes de formatos salvage. Los datos authored
incluyen nombres, archivos y tablas uplink; excluyen desbloqueos de arcos,
reservas y declaraciones radio. El ámbito físico no cambia.

RNG locales independientes usan el entero SHA-256 de tuplas canónicas con
versión, huella de reglas, identidad histórica del host y familia (`uplink`,
`archive-files`, `telemetry`). No intervienen `hash()` de Python ni RNG mutable.
El idioma elige la representación del mismo registro.

Los IDs navegacionales son hashes de huella de reglas, identidad de origen,
destino y relación tipada, con prefijo `HI1:`. Los IDs de telemetría incluyen
identidad y familia. El ámbito contenido en la identidad vincula cada registro
a su universo. Cambiar semántica exige una revisión explícita de versión/núcleo;
la huella no versiona automáticamente cualquier edición de código Python.

## Consulta histórica completa y acotada

`query_information` reutiliza una sesión local del manifiesto, inventario físico
inverso y topología incidente completa. Su dominio contiene los 3×3×3 sectores
físicos fijos alrededor del sector del host, todos los extremos de aristas
incidentes y candidatos authored configurados explícitamente. No afirma enumerar
todo lugar a 45 ly. Las cohortes generadoras no sustituyen al inventario físico
inverso; el desbordamiento Z y la materialización parcial no alteran el resultado.
La sesión compartida optativa en resolución de IDs evita certificación repetida
sin cambiar reglas físicas.

Límites de aceptación por defecto: 27 sectores físicos, 4096 candidatos y 4096
cohortes generadoras examinadas. Los límites de sitios/cohortes se comprueban
tras cada proyección acotada del manifiesto; su límite de sesión de 32768
cohortes acota el trabajo intermedio, sin detener esa proyección exactamente
en 4096 cohortes. Recuperación admite además 128 hosts informativos distintos por
selección (`RecoveryBudget.information_hosts`, máximo 512). El cache sólo vive
durante esa selección. Fallos de dominio/trabajo lanzan error o producen
`incomplete` en recuperación; el inicializador no congela un pool vacío en su
lugar. No se enumera la galaxia completa.

## Registros navegacionales y uplink finito

### P1: exclusiones navegacionales fijas por host

Una localización authored puede declarar:

```json
"navigation_policy": {
  "version": "host-navigation-exclusions-v1",
  "exclude_destinations": ["HARBOR_12"]
}
```

`define_information` captura esta política opcional y sustractiva antes de jugar.
Los destinos se normalizan a IDs authored o alias inequívocos. Se rechazan objetos,
versiones, claves o listas vacías inválidos, destinos desconocidos, el propio host,
la nave del jugador y duplicados. Los LINK operativos authored contradictorios
(inversos, con host implícito o en INTEL incluidos) se rechazan, nunca se reescriben.
Las menciones de testimonio/contacto siguen siendo válidas.

El productor original selecciona primero sus registros/archivos finitos; después
se retiran los registros de uplink seleccionados excluidos y archivos navegacionales
tipados completos. No se repiten sorteos, rellenan huecos ni sustituyen archivos.
B2 conserva el registro seleccionado original: un payload excluido no produce
emisión procedural, ni LINK o mensaje ambiental sustitutivo. Historia del equipo,
telemetría y otros hosts permanecen iguales. No regula emisores authored
independientes ni piezas del scheduler.

ECHO-7 configura HARBOR_12 en `data/locations/echo_7.json`. Su caché original EN/ES
conserva el contacto al leerla, sin la ruta. En la semilla 29 sus tres registros
de uplink pasan a dos; las rutas obtenidas en otros hosts siguen siendo válidas.
La política no depende del reloj, conocimiento, visitas, progreso o recuperación.
Scan y route solve no cambian; no se añade garantía general de accesibilidad.

La huella informativa completa incluye la política. `sampling_definition` retira
solo este campo nuevo para conservar sorteos v1, IDs, textos y procedencia
archivística retenida originales; las huellas de pools fijan la definición
completa con política. B2 separa igualmente el muestreo original de su huella
completa. La política no física se excluye de la huella del catálogo físico,
conservando ámbito, posiciones, topología e IDs operativos.

La política tiene versión propia; versiones B1/B2 y esquema de guardado no cambian.
Sin política, la producción v1 anterior es idéntica. Instalar este cambio de ECHO-7
modifica las huellas de catálogo/B1/B2 completas: se rechazan sin alterarlos los
guardados del catálogo anterior. Restaurar su catálogo permite cargarlos; no hay
migración ni retirada de rutas adquiridas. Prueba: `tests/prologue_navigation_policy_smoke.py`.
Véase la [revisión P1](../testing/prologue-navigation-policy-review.es.md).

Cada destino seleccionado está certificado, difiere del host, queda a distancia
positiva y no supera 45 ly. Se distinguen dos tipos:

| Tipo | Evidencia | Interpretación |
| --- | --- | --- |
| `historical_connection` | Arista incidente exacta del manifiesto, con procedencia interna/intersectorial | Conexión física histórica documentada |
| `navigation_solution` | Extremos certificados y geometría válida sin esa arista | Datos conservados suficientes para calcular una ruta navegable; no acreditan tráfico histórico ni conexión de red |

Un candidato recibe peso 8 por conexión incidente; en otro caso, 5 por hub
histórico, 4 por otra instalación con uplink o 1 por nave/derrelicto. Los pesos
y cuotas min/max authored explícitos se aplican primero, acotados a tres
registros. Los huecos restantes usan orden de IDs estable y tiradas ponderadas
sin reemplazo. Conocimiento y protección narrativa no eligen, eliminan ni
sustituyen registros históricos.

`NodePoolState.uplink_records` conserva los registros tipados junto a la lista
de destinos existente. La primera acción válida consulta sólo slots autorizados
y puede resolver/materializar entonces sus destinos lazy certificados. Escribe
un log de los registros autorizados, incluidas rutas ya conocidas, con LINK
completos y etiquetas bilingües de relación. Una ruta conocida nunca se cambia
por otro destino. Repetir uplink agotado no concede rutas, logs ni recompensas
nuevos; la entrega narrativa pendiente conserva sus reintentos existentes.

## Archivos de salvage y texto ambiental archivado

Los archivos base authored existentes tienen prioridad y conservan texto y
rutas; pueden ser testimonios, no afirmaciones históricas certificadas. El nuevo
productor procedural elige un registro de navegación de aristas incidentes
completas, o un destino calculable cuando no dispone de conexión. Nunca genera
un LINK a partir de `node.links` materializados parcialmente.

Se conservan probabilidades log/mail/fragmento de 70/50/25 por ciento en los
grupos station/ship o station/derelict correspondientes, y 50/30/15 en los grupos
alternativos existentes. Los seis campos exactos siguen en `config/balance.py`.
Como antes, una pista navegacional disponible recibe un fragmento fallback si
no salió log: la probabilidad nominal de fragmento no es su frecuencia final.
Cambiar candidatos históricos y dominios de semilla puede cambiar tiradas
individuales; no modifica probabilidades ni recursos físicos.

Se mantienen rutas, permiso guest y montaje remoto. Un mismo mail conservado
tiene representaciones `/mail/inbox/0001.en.txt` y `.es.txt`, con una identidad
y tirada compartidas. Los archivos navegacionales contienen etiqueta bilingüe
estable y sintaxis LINK común. Los metadatos indican contrato, huella, ID y
procedencia navegacional tipada. El pool congela esa proyección una sola vez;
no añade archivos continuamente. No se borran base/injected ni información
montada.

Se conserva `build_procedural_salvage_mail_content`. La telemetría nueva se
presenta como archivo conservado sin fecha, no como medición actual. Integridad
y deriva de reloj son afirmaciones registradas. Las conexiones históricas
certificadas no implican peers con respuesta, tráfico presente, handshakes
recientes, estaciones operativas ni personas vivas. El texto legacy sigue
siendo texto legacy en partidas antiguas.

## Divulgación, scheduler y recuperación

La política existente de objetivos primarios protegidos filtra entrega
procedural, no historia. Los archivos navegacionales no autorizados permanecen
en el pool bruto y se excluyen de la proyección recuperable/pendiente. Un
desbloqueo puede habilitar ese mismo archivo sin reescribirlo. En el primer
consumo de uplink se retienen los slots protegidos sin sustitutos; ese pool
one-shot queda consumido, incluidos esos slots. Desbloquear después no repone
uplink. Scan natural y solve manual no quedan prohibidos globalmente. Los
primaries autorizados del scheduler conservan entrega y desbloqueo.

No cambian pesos, probabilidades, deadlines, triggers ni ventanas del scheduler.
Pushes legítimos pendientes pueden mantener datos incompletos tras agotar
uplink. Scrap/extras siguen siendo independientes, conservando B0.

F-DEAD-01 puede consultar un archivo v1 aún no preparado como evidencia
preexistente. Debe encontrar el LINK exacto en el archivo fijo, conservar ruta y
huella del payload y revalidarlos al confirmar/guardar/progresar. Consultar no
activa pool ni inyecta archivo. Sigue siendo necesaria una primera emisión
declarada; sin fuente legítima, la recuperación es condicional/incompleta.
Planes `historical-recovery-v1/v2` conservan versión y procedencia. Los archivos
procedurales legacy sin preparar no adquieren certificados retrospectivos.

## Guardado/carga y semántica legacy

El esquema general sigue en 3 y el contenedor checksum en V2. Partidas nuevas
activan v1 explícitamente. Save/load valida versión, snapshot canónico
reglas/authored, compatibilidad de reglas vigentes y preparación inmutable de
base_files/registros de rutas. Consumo, montaje y piezas injected del scheduler
siguen siendo mutables. Las incompatibilidades generan `SaveLoadError` sin
reescribir el slot original; se mantiene la política de backup existente.

Slots ausentes de WorldState reciben `legacy-information-v0` y ninguna
definición nueva. Los de NodePool reciben procedencia legacy y cero registros
tipados. El fixture B0 auténtico prueba deserialización del layout antiguo.
Se conservan pools, archivos, rutas y consumo existentes. Los hosts aún sin
inicializar de esa misma partida siguen usando los algoritmos B0 dependientes
de hora/conocimiento; no hay migración mixta optativa. La versión v0 identifica
las probabilidades B0 aprobadas y su switch determinista: una configuración
futura incompatible se rechaza al guardar/cargar, no se sustituye en silencio.

## Validación y frontera B2

`tests/historical_information_smoke.py` cubre invariancia, certificados, límites,
protección, slots legacy, rechazo no destructivo, acciones finitas, scheduler,
pruebas negativas de divulgación e input Textual EN/ES real. B0 permanece.
La evidencia externa cubre las doce semillas auditadas, catálogos A/B/C,
baseline y regresión final, recorridos desde prólogo, save/load y continuación.

B2 se implementa por separado en [historical-radio-v1](historical-radio.es.md),
reutilizando estos registros sin cambios para el contenido de emisiones. Hardware
original, conservación, energía, programas y ondas son hechos separados. Tener
archivos no activa transmisores. Reparación/reactivación excepcional y procedencia
persistida de la intervención quedan como trabajo futuro; B2 no añade emisiones
de rescate retrospectivas, reparación, topología, acciones/sensores nuevos ni audio.
