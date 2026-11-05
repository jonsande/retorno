# RETORNO — Guía de coherencia narrativa y de diseño

**ID:** `RET-GUIA-COHERENCIA`  
**Versión:** `0.2.0`  
**Fecha:** 2026-11-05  
**Estado:** protocolo de trabajo inicial  
**Destinatarios:** desarrollo, Codex, diseño de sistemas, generación de arcos y singles, revisión de contenido  
**Fuente normativa del mundo:** [`universo.md`](universo.md)

> **Objeto:** traducir el canon a decisiones comprobables sin confundir la verdad del universo con las restricciones del motor ni convertir hipótesis creativas en hechos establecidos.

## 1. Qué documento responde a cada pregunta

| Pregunta | Fuente prioritaria |
|---|---|
| ¿Qué es verdad en el universo? | `docs/canon/universo.md`. |
| ¿Cómo debe afectar esa verdad al diseño, la escritura y la revisión? | Este documento. |
| ¿Qué hace hoy el juego? | Código actual y pruebas; documentación técnica como ayuda. |
| ¿Qué JSON, rutas, canales y triggers acepta el motor de lore? | Guías técnicas actuales de arcos/singles + verificación en el código. |
| ¿Qué ocurrió realmente en una historia todavía no cerrada? | **No presumirlo**: revisar canon o proponer una decisión pendiente. |
| ¿Sigue existiendo alguna sociedad humana? | **Es una incógnita abierta para jugador y autores** (`A-SOC-001`); ningún relato aislado prueba su existencia actual. |
| ¿Qué debería significar la investigación para el jugador? | La búsqueda de un posible retorno a la humanidad y la tensión entre averiguar y llegar a tiempo (`C-NAR-003`–`005`). |

**Regla de precedencia:** el canon guía la intención del mundo; el código determina lo que existe actualmente en el producto. Si chocan, **abrir una discrepancia de diseño**. Nunca dar por implementada una mecánica solo porque está en el canon ni degradar el canon silenciosamente para justificar el comportamiento vigente.

## 2. Proceso obligatorio para una decisión de diseño relevante

Antes de añadir o modificar mecánicas, generación, economía de recursos, navegación, interacciones con ruinas o canales de información:

1. **Precisar el cambio:** qué verá o podrá hacer el jugador y qué cambiará en el estado del juego.
2. **Consultar los principios aplicables** y citar sus IDs (`C-INF-004`, `C-DEC-001`, etc.).
3. **Separar tres capas:** explicación diegética, regla jugable y comportamiento técnico actualmente implementado.
4. **Revisar casos límite:** instalaciones antiguas funcionales, estructuras nuevas destruidas, archivos preservados en ruinas, regreso tras viajes largos, localizaciones vacías.
5. **Identificar lo no resuelto:** si hace falta fijar velocidad de viaje, edad, origen de la señal, límites de la IA o existencia de supervivientes, no inventarlos implícitamente.
6. **Evaluar tiempo e información:** separar cuándo sucedió algo, cuándo quedó registrado y cuándo llega a conocerlo el jugador; distinguir una pista cierta en el pasado de una prueba válida en el presente.
7. **Evaluar compatibilidad con la progresión:** no hacer desaparecer por azar una ruta, recurso o pista indispensable sin una alternativa definida. La carrera contra el tiempo no autoriza bloqueos irreversibles arbitrarios.
8. **Documentar resultado:** principio respetado, propuesta de excepción o nueva pregunta abierta; pruebas pertinentes.

### Ficha mínima de decisión (para tareas de Codex)

```text
Cambio propuesto:
Comportamiento visible para el jugador:
Principios del canon afectados (IDs):
Explicación diegética:
Estado actual del código (verificado / no verificado):
Cuestiones abiertas que condicionan la tarea:
Impacto en navegación, recursos, lore y guardados:
Casos límite y pruebas:
Decisión: implementar / prototipar / aplazar / solicitar canon nuevo
```

No hace falta cumplimentar esta ficha para correcciones puramente internas sin implicaciones de mundo.

## 3. Traducción del canon al diseño de sistemas

| Principio | Criterio de diseño | Evitar |
|---|---|---|
| `C-INF-001` | La longevidad excepcional debe ser compatible con la función y construcción de la instalación. | Suponer que toda nave corriente conserva su integridad milenios. |
| `C-INF-002` | Los sistemas autónomos pueden preservar unas funciones y abandonar otras. | Dar por existente mantenimiento ilimitado o universal. |
| `C-INF-003` | Algunas localizaciones pueden contener solo restos, datos degradados o nada aprovechable. | Convertir cada contacto en una estación plenamente saqueable. |
| `C-INF-004` | Separar integridad, accesibilidad, operatividad y recuperabilidad. | Igualar «intacta», «accesible», «con energía» y «con datos». |
| `C-DEC-001` | Usar E1–E4 como lenguaje de diseño transversal a tipos de nodo. | Tratar E1–E4 como una progresión temporal obligatoria o como tipos `node.kind`. |
| `C-HIST-001` | El colapso duró milenios y afectó de modo desigual a regiones y sociedades; permitir fechas de abandono diferentes. | Una extinción simultánea de toda la galaxia o una fecha uniforme de cierre. |
| `C-NAR-003` | Hacer que supervivencia y arqueología puedan confluir en la búsqueda de comunidad humana. | Confundir el objetivo oculto con una misión pública desde el inicio o garantizar supervivientes. |
| `C-NAR-004` | Conservar la doble lectura de los documentos: historia del pasado y posibles pistas de un presente humano. | Reducir toda recuperación a coleccionables sin relevancia investigadora posible. |
| `C-NAR-005` | Considerar el tiempo como coste dramático de investigar, desviarse y desplazarse. | Introducir una cuenta atrás obligatoria o un desenlace fijado sin decisión adicional. |
| `C-DATA-002` | Justificar la procedencia/antigüedad de mensajes relevantes. | Inferir presencia de interlocutor vivo de cualquier correo recibido. |
| `C-DATA-003` | Introducir mensajes de emisores ya muertos con naturalidad, incluidos registros cotidianos. | Convertir todos los documentos en monólogos trágicos o confundir recepción con contemporaneidad. |
| `C-WORLD-001` | Interpretar la generación bajo demanda como descubrimiento/materialización técnica. | Narrar que un nodo surge físicamente al dispararse un failsafe. |

### Aplicación orientativa de E1–E4

- **E1, restos dispersos:** poca estructura funcional, pero puede persistir valor como materia o registro aislado.
- **E2, ruina estructural:** exploración limitada, sistemas dañados y archivos incompletos; puede haber preservación local excepcional.
- **E3, conservación parcial:** oportunidades selectivas de energía, datos, control y reparación; el estado de cada subsistema importa.
- **E4, infraestructura persistente:** funciones prolongadas y quizá automatismos activos, sin asumir seguridad, habitabilidad ni servicio completo.

**Decisión de implementación aún pendiente:** cómo representar estos estados en datos, con qué probabilidades generarlos, si cambian con los años y qué comandos los usan. No introducir campos, migraciones, balance ni degradación temporal solo por leer esta guía.

### La carrera temporal no es todavía una mecánica de extinción

La tensión entre **investigar para saber adónde ir** y **emplear tiempo en llegar** forma parte del diseño narrativo. Sin embargo, hoy no debe presuponerse que el código simula poblaciones humanas remotas, fechas de extinción, una cuenta atrás global, mensajes en tiempo real o finales condicionados por un temporizador (`A-TIME-004`).

Si se plantea una mecánica basada en el tiempo, especificar **qué cambia materialmente**, qué sabe el jugador, qué señales de advertencia recibe y cómo se evitan situaciones irresolubles por falta de información. La incertidumbre puede ser profunda sin convertir cada decisión en una trampa opaca.

## 4. Puentes con el motor actual: qué no se debe confundir

La documentación técnica de RETORNO describe `station`, `relay`, `waystation`, `derelict` y `ship` como tipos de localización; los cuatro estados E1–E4 propuestos **no son hoy otros cuatro tipos de nodo**. Los tipos `origin`, `transit` y `nav_point` tienen papeles técnicos propios.

La arquitectura también separa mundo físico (`space.nodes` y sus `links`), conocimiento de rutas (`known_links`) y contenido recuperable (`node_pools`/`lore_placements`). La generación de sectores es bajo demanda y determinista. El scheduler asigna piezas a localizaciones y canales; acciones como `dock`, `uplink` y `salvage_data` activan entregas.

Distinciones de especial importancia:

| Término técnico actual | Qué significa | Qué **no** significa por sí solo |
|---|---|---|
| `node_cleaned` | Se agotaron categorías de contenido explotable del nodo en el sistema actual. | Que se haya limpiado físicamente, reparado o desintegrado. |
| `deadnodes` / nodo `dead` | Mecanismo antíbloqueo de contactos sin acceso operativo desde las rutas conocidas. | Muerte física o desaparición de la estación. |
| `known_contacts`, `known_nodes` | Conocimiento disponible para el jugador. | Fecha de construcción o comienzo de existencia de la instalación. |
| `known_links` | Rutas conocidas para el jugador. | Que todos los enlaces estén actualmente verificados o activos físicamente. |
| `lore_placements` | Dónde y por qué canal se asigna una pieza narrativa. | Momento histórico en que se creó el documento. |
| `min_year` / `max_year` de `constraints` | Ventanas de elegibilidad del scheduler según tiempo de partida. | Edad física de una nave o época histórica del documento. |
| `uplink` | Acción disponible en determinados hubs, con pools/consumo técnico. | Prueba de una red en vivo ni de conectividad instantánea. |

Para los procedimientos exactos de `worldgen`, restricciones por `node.kind`, canales, colas, `deadnodes` y casos de borde, consultar el código y las guías técnicas del proyecto; no inferirlos exclusivamente de esta guía.

### Generación ad hoc y failsafes

Los mecanismos que generan nodos puente o candidatos ocultos existen para salvaguardar la **progresión del juego**. Diegéticamente, el descubrimiento tardío de un relé o una nave suele representar el hallazgo de algo preexistente, no su construcción instantánea. Las pistas `LINK` inyectadas por estos mecanismos deben interpretarse como información accesible/reconstruible, no necesariamente emitida en tiempo real por un ser consciente.

### Lógica narrativa frente a balance

Un principio canónico como «gran parte del patrimonio se ha perdido» no fija un porcentaje de encuentros sin botín. Las probabilidades de `salvage`, el ritmo de `uplink`, los límites de rutas y las garantías de acceso forman parte del **balance**, que debe justificarse y comprobarse mediante pruebas jugables. El canon limita lo plausible, pero no sustituye al balance.

## 5. Guía de creación de arcos y singles

Un arco es una estructura de `primary_intel` y `secondary_lore_docs`; un single es una pieza independiente. Sus archivos, campos y canales deben seguir las guías técnicas actuales. **No usar el canon como sustituto de esos contratos.**

### Antes de escribir

1. Formular en una frase qué descubre, sospecha o siente el jugador; distinguir **objetivo narrativo** de hecho canónico revelado. Preguntar si la pieza aporta pasado, una pista hacia posibles supervivientes, ambas cosas o solo atmósfera: **no todas tienen que orientar directamente la búsqueda**.
2. Determinar si el contenido **confirma**, **sugiere**, **contradice desde un testimonio** o **deja abierta** una cuestión. Para una comunidad humana supuestamente viva, distinguir afirmación del emisor, prueba de vida **en una fecha histórica** y prueba de vida **en el presente del jugador**.
3. Elegir una procedencia creíble: registro local, archivo sellado, correo almacenado, emisión automática, señal interceptada, etc.
4. Si se hace referencia a una ruina antigua, asignarle un estado E1–E4 **cuando sea relevante**, sin necesitar mostrarlo numéricamente al jugador.
5. Preguntar por qué la información sobrevive y por qué el jugador puede recuperarla ahora. Distinguir fecha del acontecimiento, del registro o envío y de la recepción cuando sea relevante.
6. Considerar la **dimensión humana cotidiana**: mensajes administrativos, bromas, quejas o afectos pueden expresar mejor la ausencia de sus remitentes que una exposición solemne.
7. Verificar que no se introduce como verdad un detalle todavía abierto (velocidad, fecha exacta del colapso, sistema universal de comunicaciones, supervivientes actuales, causa definitiva, desenlace).

### Ficha interna mínima de plausibilidad temporal (no es un esquema JSON)

Para un arco o single que afecte a la investigación principal, completar mentalmente o en notas **internas de autor**:

```text
¿Qué afirma el documento y quién lo afirma?:
¿A qué lugar o población se refiere?:
¿Cuándo ocurrió lo relatado? (fecha, rango, o desconocido):
¿Cuándo se creó/emitió/almacenó este registro? (o desconocido):
¿Cómo llegó al nodo donde puede recuperarse?:
¿Por qué se ha conservado y es recuperable?:
¿Qué sabía realmente el emisor? ¿Qué puede inferir el jugador?:
¿La pista prueba solo un pasado humano o podría orientar una búsqueda?:
¿Se mantiene abierta la existencia ACTUAL de una comunidad superviviente?:
```

Estas respuestas **no obligan a incluir metadatos nuevos en los JSON** ni a inventar fechas precisas. Si una pieza puede aparecer proceduralmente en distintos nodos, justificar su distribución (copias, cachés, reenvíos históricos, etc.) o evitar referencias espaciales rígidas.

### Coherencia diegética de canales actuales

| Canal técnico | Lecturas narrativas posibles | Precaución |
|---|---|---|
| `salvage_data` | Archivo extraído de sistemas locales, caché o soporte superviviente. | Debe haber una justificación plausible de persistencia y legibilidad. |
| `ship_os_mail` | Mensaje importado, entrega diferida, buzón o documento recuperado presentado como correo. | El remitente no se presume vivo ni la comunicación inmediata. |
| `captured_signal` | Baliza automática, eco de transmisión, señal fragmentaria, repetición, mensaje retrasado. | Distinguir señal detectada de diálogo en tiempo real. |
| `station_broadcast` | Difusión local automatizada, aviso grabado o protocolo de estación. | Su recepción al hacer `dock` no demuestra una estación habitada. |
| `uplink_only` | Tablas de navegación, rutas en caché, datos de un relé o interfaz de consulta. | No presupone red galáctica activa ni datos siempre actuales. |

Estas son **interpretaciones narrativas admisibles**, no una especificación de física o nuevas funciones del motor.

### Reglas de compatibilidad para no romper el flujo actual

- Para arcos, el caso robusto de `primary_intel.kind` es **`link`**; el `line` de navegación debe usar el formato `LINK: ORIGEN -> DESTINO`.
- El soporte de `kind: node` es parcial en la documentación disponible: no emplearlo como dependencia de progresión sin verificar el código.
- Las piezas se colocan por las reglas de `placement_rules`, `constraints` y `allowed_channels`; la entrega depende de los triggers efectivos del motor.
- La distribución procedural puede situar documentos en nodos distintos entre partidas. Evitar en el texto referencias locales rígidas («este compartimento», «la estación de enfrente») si la pieza no está restringida a un lugar que las haga ciertas.
- Revisar especialmente el origen de toda pista imprescindible. El lore opcional puede faltar; una pista crítica necesita mecanismos de entrega y recuperación robustos.
- Mantener los textos en español e inglés cuando corresponda, validando JSON, referencias de archivo, IDs y canales contra las guías existentes.

**Documentación técnica de referencia aportada al proyecto:** `arquitectura_lore_intel_universo.md`, `guia_practica_crear_arcos.md`, `guia_practica_crear_singles.md`, `guia_chatgpt_arcos_y_singles.md`, `guia_bolsillo_contenido_lore.md`, `generacion_de_nodos_procedurales_commit_audio_v0.1_bugfix_002.md`, `generacion_nodos_ad_hoc_forzosas.md`, `deadnodes_failsafe_actual.md` y `tipos_de_nodos_actuales.md`. Confirmar su ubicación efectiva en el repositorio antes de crear enlaces o automatizaciones a esos archivos.

## 6. Cómo introducir misterio sin romper el canon

Puede haber fuentes equivocadas, dataciones inexactas, falsificaciones, protocolos que repiten información obsoleta y explicaciones parciales. Esto es compatible con `C-NAR-001` si se respetan tres niveles:

- **Verdad interna:** lo que efectivamente sucedió, si está decidido.
- **Fuente diegética:** lo que un emisor, archivo o sistema cree o afirma.
- **Inferencia del jugador:** lo que puede deducirse a partir de los rastros.

Un documento puede decir «la red sigue activa» aunque sea falso; lo que no debemos hacer es asumir que ese texto establece la existencia canónica de una red activa. Cuando el motivo del error sea significativo para un arco, registrarlo en su ficha interna o notas de diseño, no necesariamente en el texto del jugador.

### Protección del misterio central: ¿queda alguien?

- **Permitido:** registros verificables de comunidades que sobrevivieron durante siglos o milenios al colapso de otras; mapas históricos, solicitudes de auxilio, rumores de refugios, señales automáticas, documentos con fechas ambiguas y contradicciones entre fuentes.
- **Permitido con cautela:** testimonios en primera persona («seguimos aquí», «hay una colonia en…»). Debe ser posible leerlos como información situada en **una fecha** y en **una fuente**, no como constatación omnisciente del presente galáctico.
- **No establecer sin decisión expresa:** una sociedad humana que exista ahora de forma indiscutible; un certificado definitivo de extinción total; un «último ser humano de la galaxia» presentado como hecho objetivo; un destino final garantizado; una cuenta atrás de supervivencia simulada.
- **Evitar también el extremo contrario:** no volver todas las pistas falsas, inútiles o irresolubles. La investigación debe poder producir avances reales, aunque la continuidad temporal de sus objetivos siga siendo incierta.

Una señal de socorro **auténtica** demuestra que alguien estuvo en peligro cuando fue originada; no que la petición siga vigente cuando llega. Una ruta **auténtica** demuestra conectividad registrada, no vida actual en su destino. El jugador puede aprender esa diferencia como parte de su arco de comprensión.

### Ejemplos de comprobación (hipotéticos; no son hechos nuevos)

- Una estación E4 transmite un saludo cada siglo: plausible si se trata de un protocolo automático con energía y soporte de larga duración; queda abierto **cómo** obtiene esa energía.
- Un `ship` E2 contiene un mensaje legible de miles de años: plausible si existe un soporte protegido o copia; no implica integridad de todos sus sistemas.
- Un mensaje llega a la nave poco después de un `uplink`: podría proceder de una caché local. No obliga a postular mensajería instantánea entre estrellas.
- Una ruina visitada siglos después permanece igual: puede ser plausible bajo ciertas condiciones, pero hoy **no demuestra** que el motor tenga envejecimiento físico simulado.

## 7. Revisión editorial y de implementación

### Checklist narrativo (arco, single o nodo authored)

- [ ] Identifica qué principios del canon toca, si corresponde.
- [ ] No convierte una pregunta abierta en una verdad accidental.
- [ ] Diferencia hechos, rumores, errores de registro y observaciones.
- [ ] No confirma ni descarta de manera omnisciente sociedades humanas actuales (`A-SOC-001`).
- [ ] Distingue, cuando importa, fecha del suceso, registro, emisión y hallazgo.
- [ ] El soporte/medio y la preservación del mensaje son verosímiles.
- [ ] La edad, el estado y la funcionalidad del lugar no se contradicen.
- [ ] Si el contenido es procedural, su redacción tolera otras ubicaciones.
- [ ] Los datos de navegación no crean imposibles técnicos ni bloqueos de progresión.
- [ ] Respeta tono e incertidumbre sin explicar de más; no exige que cada single contenga una pista principal.
- [ ] Si introduce la urgencia temporal, no impone arbitrariamente un reloj mecánico o final garantizado.
- [ ] Cumple los requisitos de JSON, textos bilingües y canales soportados.

### Checklist técnico (mecánica o cambio del generador)

- [ ] Canon relevante consultado y documentado.
- [ ] Se distingue claramente estado deseado y comportamiento implementado.
- [ ] No confunde `node_cleaned` o `deadnodes` con degradación física.
- [ ] Los nuevos estados, si se introducen, tienen semántica y persistencia explícitas.
- [ ] Las partidas guardadas, la generación determinista y la progresión siguen siendo coherentes.
- [ ] Se revisaron interacciones con `salvage`, `uplink`, `dock`, `scan` y distribución de lore.
- [ ] Si se modifican tiempos, pistas o accesibilidad, se consideran mensajes desfasados, llegada tardía y efectos sobre la progresión narrativa.
- [ ] No se ha asumido una simulación de supervivientes, un final determinado ni una cuenta atrás sin diseño aprobado.
- [ ] Se añadieron/actualizaron pruebas cuando el cambio alteró lógica existente.
- [ ] Cualquier conflicto con un principio canónico se hizo visible para decidirlo.

## 8. Protocolo de cambios de canon

1. **Propuesta:** indicar ID afectado, formulación anterior, formulación nueva y motivo.
2. **Impacto narrativo:** identificar arcos, singles y localizaciones existentes potencialmente contradictorios.
3. **Impacto técnico:** identificar datos, sistemas, reglas de generación, balance, guardados y pruebas que podrían cambiar.
4. **Decisión humana:** aceptar, rechazar o mantener como provisional/abierto. Codex no debe decidir unilateralmente cambios de canon.
5. **Registro:** actualizar versión de `universo.md`, el registro de decisiones y, si procede, esta guía.
6. **Ejecución separada:** modificar código o datos solo mediante una tarea de implementación específica; aprobar el canon no implementa automáticamente nada.

La modificación del canon no obliga a retocar de inmediato todos los contenidos preexistentes, pero sí a registrar los conflictos que queden por resolver.

## 9. Instrucciones sugeridas para `AGENTS.md`

Este bloque está **listo para copiar**, adaptándolo a la organización real del repositorio. No se modifica `AGENTS.md` automáticamente al incorporar estos documentos.

```markdown
## Canon y coherencia de RETORNO

- Antes de crear o modificar mecánicas del mundo, navegación, ruinas,
  deterioro, información, generación procedural o contenido narrativo,
  consulta `docs/canon/universo.md` y `docs/canon/guia_coherencia.md`.
- Trata los principios marcados [C] como restricciones de diseño;
  los [P] como hipótesis y los [A] como preguntas sin resolver.
- No conviertas una hipótesis narrativa, un ejemplo ni un hecho contado
  por un personaje en verdad canónica sin decisión explícita.
- El colapso humano duró milenios y fue desigual. No asumas que existe
  hoy una sociedad humana superviviente ni que toda la humanidad se extinguió:
  ambas conclusiones siguen abiertas para autores y jugador.
- Respeta el horizonte oculto del retorno a la humanidad y el papel
  del tiempo como tensión trágica, sin inventar desenlaces ni temporizadores.
- Distingue siempre el canon deseado del comportamiento actual del motor.
  Verifica este último en código y pruebas.
- Para arcos y singles consulta además las guías técnicas vigentes.
  No inventes canales, formatos de intel, campos JSON ni triggers.
- Si una tarea requiere cambiar el canon o resolver una cuestión abierta,
  identifica la discrepancia y pide una decisión de diseño antes de fijarla.
- No modifiques `docs/canon/` de forma unilateral ni implementes mecánicas
  nuevas solo porque el canon contempla su posibilidad.
```

## 10. Registro de revisión 0.2 y próximas decisiones

**Versión 0.2.0:** se incorpora el colapso humano milenario y desigual, la esperanza del personaje de encontrar una comunidad viva, la lectura investigadora de la arqueología, el antagonismo dramático del tiempo y el motivo recurrente de mensajes cuyos emisores murieron. Se añade una regla explícita contra confirmar por accidente la supervivencia o extinción total y una comprobación temporal para arcos y singles. **No se modifica el contrato JSON ni el comportamiento del motor.**

Una revisión posterior puede tratar **velocidad efectiva de viaje**, distinción entre tiempos de referencia y duración de la hibernación, y límites de comunicación. Solo cuando esas decisiones estén fijadas convendrá decidir duraciones concretas, edades típicas y mecanismos de degradación temporal. La secuencia exacta de descubrimiento de la esperanza, el desenlace y cualquier cuenta atrás siguen abiertos; no se decidirán indirectamente al ajustar el balance.
