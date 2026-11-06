# RETORNO — Informe técnico de 4D-3e5a

[English](knowledge-boundary-review.md). Fecha: 2026-11-06. Entrega para revisión externa.

## Resultado

Se establece `C-DATA-004`: los datos del motor no se convierten en conocimiento
jugable por existir internamente. `status` y `diag comms` dependen solo del receptor,
con independencia de oportunidades, fuentes remotas, búsquedas o planes ocultos,
incluso con debug activo. Se conserva acceso omnisciente mediante `debug radio`
y `debug recovery`, protegidos por el modo existente y compartidos por CLI/Textual.
Se cierran además survey de nodos no descubiertos, resolución de nombres/alias
ocultos para dock y diferencias de errores/logs que revelaban existencia física.

La intervención cambia presentación, documentación y pruebas. No se modifican
selector F-DEAD-01, manifiesto, generación, colocación narrativa, probabilidades,
deadlines, ledger, captura, cobertura, salud/energía, radiod, reglas de navegación,
recursos, esquema de persistencia, audio ni AMANECER. No se implementa 4D-3e5b.

## Base, auditoría y Git

HEAD inicial y final: `343829ee925492b4de62c5ccfd6025e3549dea51`. Rama `main`, upstream `origin/main`;
la referencia local de upstream coincide. Árbol inicial limpio e índice vacío.
Árbol final: archivos modificados/nuevos enumerados al final; índice vacío.
No se ejecutaron `git add`, commit ni push, ni se consultó un remoto para alterar
el checkout. Los informes históricos de e5 siguen documentando su entrega anterior;
este informe y su evidencia corresponden a la fase e5a sobre el commit publicado.

Antes de editar se leyeron AGENTS, canon/coherencia, roadmap, contrato de navegación,
contratos de radio/recuperación/descubrimiento e informe de revisión estructural.
La referencia global previa terminó antes de editar pruebas o producción.
Se inspeccionaron consumidores y llamadas públicas en communications,
structural_recovery, deadnodes, lore, model/world, parser/REPL, presenter y app Textual.
La auditoría se limitó a estado, navegación, intel/lore, recuperación y comunicaciones.

## Superficies auditadas

| Superficie / código | Hallazgo y tratamiento |
| --- | --- |
| `communications.radio_diagnostic_lines` | Consultaba pendientes y cambiaba la causa por una fuente invisible. Eliminadas ambas dependencias; solo `radio_block_reason(state)`, sin oportunidad. |
| `status`, `diag comms` y ausencia de comms en REPL | Tres llamadas al helper público; corregidas juntas. Equipo/servicio/causas conocidas siguen visibles. |
| `recovery_searches` / `recovery_plans` | Estados técnicos agregados eran jugables. Retirados del diagnóstico público, incluidos estados genéricos. |
| `debug radio` | Consulta ledger real, fuentes/host, IDs, canales, contenido, estados, tiempos, path y delivery; motivos del receptor, espaciales y de captura. Solo debug. |
| `debug recovery` | Consulta búsquedas/certificados retenidos y planes; estado/motivo, cursor, trabajo, acceso, sitios, mecanismo, etapa y consumo. Presupuestos actuales etiquetados como predeterminados. Solo debug. |
| Textual, `presenter` y dispatch de `app` | Comandos públicos reutilizan renderers CLI. Nuevos debug usan la misma protección dentro del renderer. Panel de sistemas conserva únicamente sistemas. |
| `ship survey <id>` | Antes consultaba cualquier nodo físico por ID. Ahora exige contacto/localización conocidos; oculto y ausente producen el mismo rechazo EN/ES sin ID ni coordenadas. Aliases de nave y datos conocidos preservados. |
| Resolver de dock `_resolve_node_id_from_input` | Antes traducía nombres ocultos a IDs internos que podían aparecer en errores. Ahora resuelve solo conocimiento adquirido; no cambia los gates físicos de dock. |
| Mapas nav, graph, path, sectores y galaxia | Proyecciones conocidas, `known_links` y posición propia; añadir nodos ocultos no modifica salida. `include_all_loaded=True` solo se usa desde `debug galaxy map`, con guard en dispatch. |
| Contactos | Listado basado en contactos/nodos conocidos. No enumera `space.nodes` completo. Conserva distancia, visita y flags de ruta conocidos. |
| Intel list/show/export | Registros efectivamente importados; no placements ni candidatos. Los textos adquiridos pueden conservar afirmaciones no verificadas; no se reinterpreta su verdad. |
| `route solve`, scan y navegación | Se conserva la excepción manual exacta y el descubrimiento natural, protección primaria y semántica de rutas. No se modifica el motor de acciones. |
| Autocompletado CLI/readline y Textual | Destinos obtenidos de helpers de conocimiento/rutas/localidad. No proponen IDs exclusivos de manifiesto, placements, radio o recovery. Nuevos nombres debug son sintaxis general, no entidades secretas. |
| Errores de navegación y logs | La existencia física oculta producía `unknown_contact` frente a `node_missing` para un destino ausente. Proyección pública común EN/ES, sin ID; conserva códigos del motor y detalles de destinos conocidos. |
| Ayuda / errores | `diag comms` ya no promete recuentos; parser/help/compleción incluyen nuevos debug en EN/ES. Rechazos debug no consultan registros; survey no distingue existencia oculta. |
| Eventos de radio / archivos / lectura | Solo captura real produce evento/archivo; texto y path recibido siguen visibles. No se exponen `opportunity_id` ni plan en el renderer de evento normal. Leer/importar publica intel igual que antes. |
| Alertas / sonidos | No se encontró un productor público nuevo de eventos por mera preparación o búsqueda estructural. Sin cambios en tipos de evento, audio o alertas; regresiones existentes ejecutadas. |
| `world`, lore/deadnodes y save/load | Colecciones físicas/internas separadas de conocimiento. Ninguna mutación nueva ni campo persistido. Se conservan protección, etapas, ledger y registros. |

No se añade una segunda copia de datos ni un historial de rechazo artificial.
`debug recovery` no reconstruye candidatos descartados que el motor no guardó;
solo muestra la evidencia existente. Para bloqueos de entrega vigentes se usa
`debug radio`, cuya consulta evalúa predicados existentes sin ejecutar captura.

## Separación pública y de desarrollo

| Consulta ordinaria | Consulta explícita de desarrollo |
| --- | --- |
| Equipo instalado, estado/salud, carga, alimentación, radiod instalado/en marcha, disponibilidad operativa y causas propias del receptor. | Oportunidades preparadas, fuente/host, contenido reservado, metadatos, estados pendientes/recibidos/leídos y bloqueos de fuente. |
| Contactos detectados, rutas registradas, intel adquirida, archivos/eventos efectivamente recibidos. | Búsquedas y planes F-DEAD-01, certificados retenidos, cursor, trabajo, etapas, acceso y mecanismos. |
| `status` / `diag` mantienen el mismo significado con debug on/off. | `debug on` habilita `debug radio` / `debug recovery`; `debug off` los bloquea otra vez. |

`ready` expresa capacidad del receptor; no afirma que exista una señal ni promete
recepción. No queda ninguna frase pública condicionada por presencia de una
oportunidad secreta o resultado oculto de F-DEAD-01 en el helper corregido.

## Principio canónico final

### C-DATA-004 — Conocimiento limitado y procedencia de la información [C]

La existencia de una información en el estado interno del universo no implica que el protagonista pueda conocerla. Toda información presentada como conocimiento de la nave o del jugador debe proceder de una observación, recepción, lectura, registro o inferencia legítima. Las inferencias pueden ser inciertas o erróneas y deben distinguirse de los hechos verificados. La simulación puede conocer hechos que permanecen inaccesibles al protagonista.

Deben distinguirse cinco capas:

1. Verdad física e histórica del universo.
2. Información interna del motor, incluidas decisiones procedurales y narrativas.
3. Observaciones y registros efectivamente adquiridos por la nave.
4. Inferencias o hipótesis elaboradas a partir de evidencia legítima.
5. Conocimiento que el jugador puede consultar por las interfaces ordinarias.

La existencia física o asignación interna no publica conocimiento. Conocer una localización no equivale a conocer una ruta hasta ella ni a poder recibir ahora sus transmisiones. Un testimonio recibido puede conservar información falsa sin convertirla en verdad física; una inferencia debe señalar su incertidumbre y su base disponible.

Este principio se refiere a hechos del universo y conocimientos atribuidos al protagonista o la nave. Menús, controles, guardado/carga y ayuda general pueden ofrecer información ordinaria del sistema sin una justificación diegética artificial. Los comandos explícitos de desarrollo pueden revelar el estado omnisciente del motor; activar debug no altera el significado de las consultas públicas. No se resuelven aquí supervivientes, cronología galáctica ni `A-COM-001`.


## Regla operativa final de AGENTS

Se conserva un único AGENTS operativo en inglés; el bloque añadido es:

```markdown
## Player knowledge and diegetic information boundaries

Follow `C-DATA-004` in `docs/canon/universo.md` and ask “How does the ship know
this?” using `docs/canon/guia_coherencia.md` before exposing universe facts.

- Every fact presented as ship or protagonist knowledge needs a legitimate
  observation, measurement, captured communication, read archive, prior ship
  record, or inference from available evidence.
- Distinguish physical truth, ship knowledge, and technical scheduler state.
  Inferences may be approximate, uncertain or false, but must be justifiable
  and distinguishable from verified facts.
- Never disclose secret catalogs, undiscovered historical sites, scheduler
  candidates, reserved documents, prepared narrative opportunities or internal
  recovery plans without a valid discovery event.
- Do not use internal collections containing hidden information directly as
  sources for playable diagnostics. Physical `space.nodes`, `lore_placements`,
  `radio_opportunities`, `recovery_searches` and `recovery_plans` are not ship
  knowledge. Known locations, known routes and current reception eligibility
  are separate facts.
- Keep omniscient diagnostics behind explicit development commands gated by
  `debug_enabled`. Ordinary `status` and `diag` retain their public meaning
  even with debug enabled. Diagnostic queries must not advance or mutate the
  simulation, consume RNG, generate sites, receive messages or import intel.
- CLI and Textual must enforce exactly the same knowledge boundary. Review
  events, sounds, help, contextual entity lists, completion and error messages
  as potential disclosure surfaces too.
- New features presenting universe state require negative disclosure tests:
  hold observations constant, vary hidden engine data, and compare public
  output. Also verify preservation of legitimately acquired information.

Menus, controls, save/load and general system help do not need artificial
fictional explanations. This rule concerns universe facts and knowledge
attributed to the protagonist or ship; it permits ordinary interface information
and explicitly activated development diagnostics.
```

## Pruebas negativas y preservación

Nuevo `tests/knowledge_boundary_smoke.py`: **19 grupos**. Compara salidas completas
para estado observable idéntico con diferentes oportunidades ocultas, fuente fuera
de cobertura, servicio detenido, resultados de búsqueda, plan sin primera pista,
catálogo físico y placements. Incluye status, diag, contactos, mapas, rutas, intel,
alertas, cabecera y panel Textual. Prueba gates debug EN/ES, off posterior,
comandos reales del REPL y handler Textual, autocompletado y aliases de dock.

Antes de corregir producción fallaron los grupos 1–6 y 14 por las filtraciones;
9–11 y 13 fallaron porque los comandos nuevos todavía no existían. Los grupos
7–8, 12 y 15 ya pasaban, caracterizando información legítima y persistencia.
La reproducción adicional de aliases (grupo 18) y los errores de navegación
(grupo 19) fallaron antes de sus respectivas correcciones.
Los grupos 16–17 se añadieron después como regresiones de integración y catálogo.
Se conservan trazas de antes y resultados finales en
[la evidencia completa](knowledge-boundary-test-results.json).

No son solo búsquedas de cadenas: se comparan estructuras de salida completas,
eventos reales, archivos, `known_links`, contactos/intel y estado de lectura.
Se serializa el estado entero antes/después y se compara el RNG global: consultar
no altera tiempo, generación, historial de scan, filesystem, radio, recovery,
recursos ni conocimiento. Save/load temporal cubre pendiente, capturado y leído en
ambos locales; conserva planes y ledger por igualdad y las mismas vistas públicas.
Las pruebas radio existentes conservan además unlocks narrativos y deduplicación.

## Regresión y validación

- Referencia previa: **63/64** smoke scripts correctos.
- Batería final sobre código definitivo: **64/65** correctos, incluido el nuevo script.
- F-DEAD-01: **36 grupos**; narrativa: **20 grupos**; radio: **18 grupos**, todos correctos.
- REPL/Textual, diagnósticos, compleción, navegación/intel, guardado/carga,
  manifiesto/worldgen y audio incluidos en la batería global.
- Manuales EN/ES: `MANUAL STYLE CHECK PASSED`. Ayuda, parser, textos nuevos,
  parejas documentales y referencias locales comprobados.
- `git diff --check`: correcto. Índice vacío; HEAD conservado.

Fallo histórico separado: `radiation_hull_smoke.py:183`, `AssertionError: []`,
fixture `CARNAVAL_34`. La traza previa y final es idéntica. No se modifica ni
oculta la fixture. No se afirma que toda la suite esté verde.

El primer pase global intermedio también terminó en 64/65 con 17 grupos nuevos;
tras cerrar el alias de dock se ejecutó otra batería global completa con 18 grupos.
El pase `e5a-release` validó 18 grupos; después se cerró la diferencia de error
entre destino oculto y ausente, cubierta por el grupo 19. La evidencia normativa
final es `e5a-delivery`; las ejecuciones anteriores se distinguen.

Reproducción (intérprete canónico):

```sh
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/knowledge_boundary_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/structural_recovery_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/narrative_world_integration_smoke.py
PYTHONPATH=src:.:tests /home/jon/prog/retorno_case/retorno_venv/bin/python tests/passive_communications_smoke.py
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python tests/manuals_style_check.py
git diff --check
```

La batería global ejecuta en serie cada `tests/*smoke*.py` con el mismo intérprete,
`PYTHONPATH=src:repo`, guardados temporales y timeout de 240 s por script. La
evidencia conserva resultado y log por script, más el código del runner temporal.
No se modifican guardados del usuario.

## Documentación, alcance y límites

Canon y guía suben a 0.4.0 con fecha e historial; las adiciones incluyen su texto
EN en el mismo archivo, conservando el canon histórico español y sin crear un
AGENTS paralelo. Contratos de comunicaciones, recuperación, descubrimiento y
navegación, roadmap v1.5 y manuales comms/boot/diag/status/ship/navigation están sincronizados EN/ES.
La ayuda y parser usan la infraestructura bilingüe existente. Los identificadores
técnicos de diagnóstico permanecen estables; la explicación y el rechazo se localizan.

No se introduce un modelo nuevo de procedencia por propiedad, cobertura de radio,
latencia ni emisores. `A-COM-001`, supervivientes y cronología galáctica siguen
abiertos. 4D-3e5b y la validación jugable prolongada e6 quedan separadas. Los tests
Textual ejercitan presentadores y dispatch real de entrada; no se atribuye a esta
fase una sesión manual prolongada con sonido.

## Inventario y paquete

- `AGENTS.md`
- `data/manuals/commands/boot.en.txt`
- `data/manuals/commands/boot.es.txt`
- `data/manuals/commands/diag.en.txt`
- `data/manuals/commands/diag.es.txt`
- `data/manuals/commands/ship.en.txt`
- `data/manuals/commands/ship.es.txt`
- `data/manuals/commands/status.en.txt`
- `data/manuals/commands/status.es.txt`
- `data/manuals/concepts/navigation.en.txt`
- `data/manuals/concepts/navigation.es.txt`
- `data/manuals/systems/comms.en.txt`
- `data/manuals/systems/comms.es.txt`
- `docs/canon/guia_coherencia.md`
- `docs/canon/universo.md`
- `docs/design/navigation-recovery-contract.es.md`
- `docs/design/navigation-recovery-contract.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.es.md`
- `docs/design/roadmap-worldgen-lore-f-dead01.md`
- `docs/systems/discovery-navigation-intel.es.md`
- `docs/systems/discovery-navigation-intel.md`
- `docs/systems/passive-communications.es.md`
- `docs/systems/passive-communications.md`
- `docs/systems/structural-recovery.es.md`
- `docs/systems/structural-recovery.md`
- `docs/testing/knowledge-boundary-review.es.md`
- `docs/testing/knowledge-boundary-review.md`
- `docs/testing/knowledge-boundary-test-results.json`
- `src/retorno/cli/parser.py`
- `src/retorno/cli/repl.py`
- `src/retorno/core/communications.py`
- `src/retorno/ui_textual/app.py`
- `tests/knowledge_boundary_smoke.py`
- `tests/passive_communications_smoke.py`
- `tests/structural_recovery_smoke.py`

ZIP íntegro: `retorno-4D-3e5a-review-20261106.zip`, junto al repositorio, con las
rutas relativas y bytes finales de todos los archivos anteriores. Incluye este
informe, contraparte EN, pruebas y evidencia. Se verifican inventario exacto,
CRC e igualdad byte a byte. Manifiesto externo con SHA-256 por archivo y checksum
del ZIP en `.manifest.json` y `.zip.sha256`; el SHA del propio ZIP se mantiene
fuera de su contenido para evitar referencia circular. No incluye .git, venv,
cachés ni partidas. Trabajo detenido para revisión externa, sin staging/commit/push.
