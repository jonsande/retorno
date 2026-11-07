# RETORNO — Informe técnico B2

[English](historical-radio-review.md).

Implementado para revisión externa, 2026-11-07. No se ejecutaron add, commit ni push.

HEAD: `c705293679193f46de92785800ed055607cb1ba6`. Branch: `main`; upstream: `origin/main`.

## Resultado y contrato

Las partidas nuevas tienen historia procedural determinista de radio. Equipo original, conservación, energía, ventanas reales y ondas aún en propagación son hechos separados. El modelo físico, compilador authored, scheduler y ledger de recepción existentes conservan la autoridad de entrega. Las reglas completas y la tabla de estados/probabilidades están en el [contrato historical-radio-v1](../systems/historical-radio.es.md).

La implementación añade un núcleo puro, `worldgen/historical_radio.py`, análogo al de información B1. No introduce otro motor físico, catálogo de emplazamientos, receptor, ledger, generador navegacional ni cola de recuperación. Reutiliza RadioEmitter, RadioEmission, inventario inverso, registros B1, puertas espaciales/temporales, escritor y oportunidades canónicas. bootstrap.py, generator.py, manifest.py, information.py e io/save_load.py permanecen sin cambios: los hooks existentes de bootstrap y validación invocan el contrato aditivo.

Hay como máximo un mensaje procedural por host. Las cinco clases elegibles tienen equipo original; la capacidad presente tiene las tasas esperadas aprobadas 40/65/50/10/5 por ciento. Sorteos independientes de conservación y energía producen esas tasas. Un sorteo separado de programa conserva instalaciones silenciosas, equipo intacto sin energía, radios averiadas con alimentación y mensajes anteriores a la destrucción de sus comunicaciones.

## Generador y procedencia

El generador resuelve una identidad del manifiesto, aplica precedencia authored para todo el host, muestrea dominios SHA-256 independientes para épocas gruesas de equipo/energía y existencia de programa, limita el final a hardware/energía y selecciona un mensaje bilingüe acotado. No intervienen reloj del jugador, orden de visita, rutas conocidas, RNG mutable ni necesidad de rescate. El espacio @HR1 no colisiona con IDs editoriales. La repetición usa ventanas continuous; los programas finite tienen final real. La programación periódica queda pendiente.

El perfil experimental seleccionado tiene 55 % de existencia de programa, 65 % de programas continuos y 30 % de intentos de navegación. Navegación solo copia registros certificados B1 de uplink o archivos tipados del productor, conservando historical_connection frente a navigation_solution y el cap de 45 ly. Los archivos authored que imitan metadatos B1 siguen siendo testimonio y no pueden falsificar procedencia procedural. Sin registro se emite texto ambiental, nunca un destino elegido para progresar. Ocho familias ambientales cubren baliza, telemetría, aviso técnico, socorro, advertencia de aproximación, anuncio de ruta ilegible, prueba de portadora y datos deteriorados.

## Método de medición

Doce semillas de la auditoría: 0, 1, 2, 7, 42, 137, 2026, 65535, 271828, 314159, 8675309, 2147483647. A usa contenido instalado; B elimina arcos y singles; C elimina además localizaciones authored salvo UNKNOWN, RETORNO_SHIP y ECHO_7, con las definiciones de B1. Cada muestra es el cubo físico completo 3×3×3 de [-10,20) ly por eje, consultado sin materialización jugable. Este dominio físico completo es mayor que la muestra operativa materializada en B1; no se presenta el rendimiento documental anterior como comparación con igual denominador.

Escaso/intermedio/abundante solo cambian existencia de programa (30/55/80 %). Se comprueba igualdad de huellas de equipo y definición física entre perfiles. A y B producen el mismo equipo/historia aquí: retirar paquetes narrativos no cambia la definición física/informativa de esta muestra instalada. C cambia la base física authored y por tanto ámbito e identidades. Los totales agregan doce universos separados, no una galaxia. El potencial usa sensibilidad nominal, t=0 y posiciones muestreadas; la recepción efectiva al iniciar es cero mientras el receptor permanece apagado.

### Equipo, perfil intermedio, A/B

| Clase | Sitios | Original | Conservado | Averiado | Destruido | Energía | Operativo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| station | 80 | 80 | 66 | 14 | 14 | 46 | 32 |
| relay | 73 | 73 | 67 | 7 | 6 | 58 | 48 |
| waystation | 62 | 62 | 51 | 10 | 11 | 46 | 31 |
| ship | 126 | 126 | 87 | 54 | 39 | 54 | 15 |
| derelict | 196 | 196 | 103 | 64 | 93 | 52 | 13 |

### Distribución de emisiones por clase, intermedio A/B

| Clase | Historial | Continuas | Finitas | Navegación | Ambientales | Emitiendo ahora |
| --- | --- | --- | --- | --- | --- | --- |
| station | 48 | 34 | 14 | 14 | 34 | 7 |
| relay | 40 | 25 | 15 | 16 | 24 | 13 |
| waystation | 32 | 21 | 11 | 10 | 22 | 7 |
| ship | 74 | 49 | 25 | 15 | 59 | 3 |
| derelict | 103 | 66 | 37 | 32 | 71 | 3 |

Conservado significa utilizable más averiado, excluyendo hardware destruido. La energía es independiente de conservación. Capacidad operativa no equivale a transmisión actual, historial ni onda recibible.

### Comparación de perfiles

| Escenario | Perfil | Sitios | Programas | Activos ahora | Nav / ambiente | Alcanzan puntos muestreados | Terminadas aún llegando | Recovery validado en host |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | sparse | 537 | 160 | 18 | 44 / 116 | 30 | 12 | 4 |
| A | intermediate | 537 | 297 | 33 | 87 / 210 | 60 | 27 | 11 |
| A | abundant | 537 | 425 | 47 | 119 / 306 | 86 | 39 | 14 |
| B | sparse | 537 | 160 | 18 | 44 / 116 | 30 | 12 | 4 |
| B | intermediate | 537 | 297 | 33 | 87 / 210 | 60 | 27 | 11 |
| B | abundant | 537 | 425 | 47 | 119 / 306 | 86 | 39 | 14 |
| C | sparse | 530 | 154 | 26 | 52 / 102 | 33 | 7 | 8 |
| C | intermediate | 530 | 288 | 43 | 98 / 190 | 61 | 18 | 15 |
| C | abundant | 530 | 410 | 57 | 128 / 282 | 81 | 24 | 17 |

La elección intermedia sigue siendo experimental: solo 33/537 sitios de A/B transmiten en t=0, 87/297 programas llevan navegación y 27 emisiones terminadas aún alcanzan posiciones muestreadas. Escaso aporta menos oportunidades (4 fuentes validadas en host frente a 11); abundante las eleva a 14 y aumenta a 47 los transmisores actuales. Los datos justifican conservar la hipótesis intermedia para revisión; no establecen balance definitivo ni cambian automáticamente el perfil seleccionado.

### Detalle en las doce semillas, intermedio

| Semilla | Sitios A/B | Programas A/B | A/B cerca origen | A/B terminadas llegando | Recovery A/B | Sitios C | Programas C | C cerca origen | Recovery C |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 42 | 22 | 0 | 2 | 0 | 41 | 27 | 2 | 3 |
| 1 | 51 | 24 | 2 | 3 | 0 | 50 | 28 | 4 | 2 |
| 2 | 40 | 21 | 1 | 0 | 1 | 39 | 22 | 2 | 1 |
| 7 | 40 | 25 | 2 | 3 | 3 | 40 | 22 | 2 | 1 |
| 42 | 40 | 20 | 1 | 0 | 0 | 40 | 19 | 2 | 2 |
| 137 | 44 | 26 | 4 | 3 | 3 | 44 | 23 | 1 | 0 |
| 2026 | 48 | 27 | 1 | 1 | 1 | 46 | 21 | 0 | 1 |
| 65535 | 46 | 21 | 3 | 1 | 1 | 46 | 31 | 1 | 0 |
| 271828 | 46 | 28 | 1 | 4 | 0 | 45 | 24 | 3 | 0 |
| 314159 | 51 | 30 | 1 | 2 | 1 | 51 | 28 | 1 | 1 |
| 8675309 | 42 | 28 | 1 | 4 | 0 | 41 | 19 | 3 | 2 |
| 2147483647 | 47 | 25 | 1 | 4 | 1 | 47 | 24 | 0 | 2 |

## Evidencia temporal, espacial y de recuperación

Se conservan presupuesto inverso al cuadrado, tres sensibilidades, distancia euclidiana y retardo lumínico. Se prueban llegada/paso exactos, ventanas finitas/continuas, captura posterior a destrucción, cambio de posición, esperas largas, radiod detenido y saves anteriores a llegada y posteriores a captura/lectura. Las sondas de tiempo histórico negativo son pruebas físicas controladas; los recorridos públicos no asignan el reloj. No fue necesario cambiar viajes ni relatividad.

F-DEAD-01 considera payloads procedurales certificados por el resolver común, con hasta 128 hosts de radio examinados por búsqueda. El primer aviso debe ser accesible, haber llegado, tener cobertura y ser continuo sin final, con el LINK exacto y permiso narrativo. Se conserva la regla de primera fuente aún no recibida. Una captura procedural anterior puede adoptarse en una etapa posterior sin cambiar archivo, fecha ni número de capturas; se prueba con una cadena de dos radios. Un archivo authored no falsifica campos B1 ni una señal ambiental se convierte en ruta.

Cada candidato contado como recovery validado se comprueba con el selector real en una sonda instrumental situada en su fuente conocida, no convirtiendo un conteo geométrico en garantía. Los totales intermedios son A=11, B=11, C=15. Son oportunidades condicionadas en host, no salidas efectivas desde la posición inicial del jugador. Ausencia de fuente, presupuesto agotado, target protegido, señal futura o fuera de alcance conservan resultados condicionados/incompletos. No se inventa transmisor, archivo ni ruta por bloqueo.

## Independencia, conocimiento y persistencia

Las doce semillas tienen testigos guardados de invariancia frente a orden opuesto de consulta/materialización, reloj, idioma, conocimiento, rutas, contadores y contexto de recovery; estado consultado y RNG global permanecen idénticos en bytes. Procesos separados usan PYTHONHASHSEED=0/137/987654321 en los doce universos. La huella física permanece igual tras consultas/perfiles. No cambian versión ni productor B1. El núcleo consulta inventario certificado y hechos B1 sin producir observaciones del jugador.

Un único ledger distingue existencia histórica, elegibilidad física, preparación, captura, archivo, lectura/importación e intel. Los eventos procedurales identifican comms, usan nombres de archivo sin fuente y omiten IDs internos de oportunidad. Capturar no concede posición exacta ni intel navegacional; los payloads ambientales no revelan host. Las pruebas negativas fijan observaciones y cambian datos ocultos en superficies públicas CLI, Textual, eventos y completado. La inspección omnisciente de caché queda restringida a debug radio explícito y de solo lectura.

Se mantienen esquema 3 y contenedor V2. Se persisten nuevas definiciones, cursor/caché local y posición/sensibilidad reales de captura; la validación reconstruye el segmento de caché examinado y payload certificado. Cursor, payload, identidad, reglas o recepción imposible manipulados se rechazan sin sobrescribir slots existentes. Los fixtures anteriores conservan radio e información legacy, sin señales retrospectivas; no se elimina ninguno. Algunas matrices sintéticas previas activan radio legacy explícita para aislar sus aserciones originales; B2 incorpora una prueba real de coexistencia.

## Recorridos públicos CLI y Textual

CLI usa parser/handlers y bucle normales desde el prólogo sin modificar, con semilla/idioma como configuración. Repara alimentación/distribución, descubre y alcanza ECHO_7, enciende la bahía después del viaje, repara comms, arranca radiod, escucha, lee/importa archivos realmente capturados, guarda/reinicia y continúa con dock/datad/uplink. No usa debug, recursos concedidos, asignación de coordenadas ni decisiones por destinos ocultos. Las lecturas de snapshot solo registran evidencia.

| Escenario | Idioma | Comandos | Segundos de juego | Capturas procedurales | Leídas/importadas | Carga/deduplicación |
| --- | --- | --- | --- | --- | --- | --- |
| A | en | 37 | 1311.0 | 3 | 3 | PASS |
| A | es | 37 | 1311.0 | 3 | 3 | PASS |
| B | en | 37 | 1311.0 | 3 | 3 | PASS |
| B | es | 37 | 1311.0 | 3 | 3 | PASS |
| C | en | 35 | 1311.0 | 2 | 2 | PASS |
| C | es | 35 | 1311.0 | 2 | 2 | PASS |

Textual ejecuta además un recorrido mediante teclado real en ambos idiomas, desde un prólogo intacto guardado con semilla 42 y solo preferencias de idioma/audio headless. Los drones completan reparaciones reales; radiod captura tres mensajes procedurales; cat/import pasan por Input.Submitted. El comando público exit persiste, una aplicación nueva carga y diag comms más ticks ordinarios continúan sin duplicados. Cada recorrido usa 22 comandos y alcanza t=486 s. Las sondas de integración controlada de la matriz se identifican por separado. El cubo mayor de escucha explica que las capturas efectivas CLI no equivalgan al potencial nominal de la muestra de 27 sectores.

## Descubrimiento acotado y coste

La escucha local completa un cubo 7×7×7 para el alcance máximo actual de 30 ly. Examina como máximo cuatro sectores y 64 sitios por tick, compartiendo los 128 candidatos con radio authored. Los offsets internos conservan candidatos de celdas densas; un fixture de 260 hosts supera 128 sin omisiones ni duplicados. La recepción rota por historias cacheadas. Un inventario completo que cabe en caché no se reconstruye hasta cambiar de celda. Al alcanzar 4096 historias, las ventanas comprobadas rotan desde el cursor físico; el barrido con desbordamiento revisita todo el ámbito para futuras llegadas. Una prueba con cap de tres entradas demuestra cobertura, vuelta completa y save/load sin sesgo permanente de celdas.

| Medición | Resultado |
| --- | --- |
| Páginas de inventario completo | 86 |
| Historias retenidas / caché local serializada | 307 / 399595 bytes |
| Pico de consulta con tracemalloc | 1260694 bytes |
| Mediana / máximo de página trazada | 190.83 / 549.57 ms |
| Mediana / máximo de descubrimiento solo radio sin trazado | 143.35 / 259.03 ms |
| Mediana / máximo de radio con inventario completo sin trazado | 58.26 / 158.94 ms |

Son tiempos de pared de instrumentación local, no una garantía universal por frame; trazado y carga compartida influyen. El benchmark de radio usa receptor sano configurado explícitamente y no sustituye evidencia jugable pública. Comprueba geografía materializada y conocimiento iguales pese a capturar. Save/load asume deliberadamente recertificación acotada de la ventana de caché. Una densidad local extrema puede agotar capacidad o retrasar descubrimiento; ondas breves perdidas durante paginación no se capturan retrospectivamente.

## Regresión y matriz de pruebas obligatorias

Baseline: 72/73 scripts pasan. Final: 73/74 scripts pasan, incluidos los 27 grupos B2 nuevos. El único fallo de ambos es la aserción histórica radiation_hull_smoke.py en CARNAVAL_34: falta el evento esperado de nivel de radiación ambiental. Sigue siendo fallo real, no xfail ni PASS. Se conservan logs completos y códigos. El wrapper serial que necesita argumento de salida se excluye por ser wrapper; se ejecutan directamente todos los smoke, checker de manuales, comparación de manifiesto y geografía de radio.

La cobertura de los 25 criterios obligatorios se corresponde con estos grupos nuevos y matrices authored/comunes conservadas. Las referencias numéricas son test_XX de historical_radio_smoke.py.

| Criterio requerido | Grupos nuevos | Evidencia |
| --- | --- | --- |
| 1–2 | 01–04 | Equipo original, conservación, energía, hosts silenciosos |
| 3–6 | 03–07, 24 | Ondas tras avería, continua/finita, potencia, retardo y ventanas |
| 7 | 08, 12–13 | Fuentes lazy sin materializar y dominio completo acotado |
| 8–12 | 08–10, 20 | Independencia de semilla, tiempo, orden, hash y conocimiento |
| 13–15 | 11, 14–15, 23 | Coexistencia authored, primaries y deduplicación canónica |
| 16–17 | 16–18, 22, 24 | Saves en propagación, reutilización y ausencia de recaptura |
| 18–19 | 18–19, 22, 26 | Recovery procedural certificado y ausencia de fuente válida |
| 20 | 14–15, 25 | Divulgación negativa y debug explícito de solo lectura |
| 21–23 | 05, 08–09, 18–20, 26 | B1/física sin cambios, sin ruta inventada para rescate |
| 24–25 | 05, 12–13, 20–21, 25, 27 | Paridad EN/ES, input Textual real y rendimiento acotado |

La regresión existente cubre además worldgen, manifiesto, uplink, salvage, scheduler de lore, navegación, recuperación estructural, deadnodes, save/load, CLI/Textual, audio y manuales. No cambian disposición visual ni implementación de audio. Manuales EN/ES y documentos técnicos correspondientes se sincronizan; help existente sigue siendo correcto porque no cambia ningún comando público ni puerta del receptor. git diff --check se exige en la verificación final del paquete.

## Archivos y artefacto de revisión

Los cambios de producción se limitan al núcleo histórico de radio, parámetros de balance, campos aditivos de WorldState/RadioOpportunity, preparación de partida nueva, comunicaciones comunes, resolución de fuentes de recovery y debug restringido. Los fixtures retienen explícitamente el contrato previo cuando corresponde; historical_radio_smoke.py añade 27 grupos sustantivos. La documentación incluye contrato/informe EN/ES, frontera B1, referencias de radio/recovery, roadmap y manuales comms. El paquete incluye archivos nuevos/modificados completos, diff binario tracked, inventario SHA-256 por archivo, procedencia Git, logs iniciales/finales, 108 filas de medición, benchmarks, saves de invariancia en doce semillas y transcripciones/saves CLI/Textual públicos. Construirlo no requiere mutar Git.

## Riesgos pendientes y propuesta de reparación excepcional

Probabilidades y edades gruesas siguen siendo experimentales, no balance final de supervivencia ni cronología absoluta. Solo se modela un mensaje/programa por host estacionario; no hay calendario periódico, simulación electrónica/civilizatoria, emisor móvil ni interferencia. Silencio actual no prueba ausencia de hardware ni de onda histórica. Paginación, capacidad finita y muestreo al final del tick pueden perder oportunidades breves; no implican ausencia ni escape universal. Las campañas e6 prolongadas de audio/Textual siguen separadas de esta validación funcional B2 completada.

La futura recuperación excepcional debería comprobar equipo conservado frente a destrucción irreparable, energía y dependencias, archivo/payload B1 previo, permiso narrativo y elegibilidad de intervención. La intervención persistida necesitaría identidad única, causa, instante real, registro fuente e ID de nueva emisión. La transmisión solo puede empezar en/después de la intervención, con retardo lumínico normal y el mismo ledger. No se implementan recarga de reservas, reinicio ni reparación de radios, ni se reescribe el pasado. No cambian densidad, topología, propulsión, sensores, probabilidades de salvage, economía, recursos, arcos/singles activos, AMANECER, balance de supervivencia ni modelo temporal general.

El trabajo se detiene para revisión externa con el árbol deliberadamente sin staging.
