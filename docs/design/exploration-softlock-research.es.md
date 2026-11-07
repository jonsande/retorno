# RETORNO — Investigación pendiente: continuidad exploratoria y F-DEAD-01

[English](exploration-softlock-research.md) · **Estado: objetivo de diseño pendiente de validación**, 2026-11-07.

**Alcance:** bloqueo estructural de exploración con una nave capaz de explorar. Este documento **no** declara que exista una garantía universal, no modifica el comportamiento del juego y **no** autoriza F-DEAD-01 nivel 2. Los hechos de implementación se contrastan con [`exploration_recovery.py`](../../src/retorno/core/exploration_recovery.py), [`structural_recovery.py`](../../src/retorno/core/structural_recovery.py) y el [contrato vigente](../systems/structural-recovery.es.md). Las afirmaciones históricas de [`exploration-failsafes.es.md`](../systems/exploration-failsafes.es.md) que contradigan el contrato vigente no prevalecen.

## 1. Objetivo y definición

**Objetivo deseado del desarrollador:** ninguna partida debería terminar en un *bloqueo exploratorio estructural involuntario*. Este es un **objetivo por investigar y demostrar**, no una propiedad implementada ni verificada. No implica victoria garantizada, supervivencia ilimitada, caminos conocidos de antemano, conectividad histórica universal, ni eliminación de la incertidumbre.

Una **situación de bloqueo exploratorio estructural** existe cuando, aun suponiendo la nave funcional y los sistemas de exploración utilizables, el jugador ha agotado las oportunidades legítimas disponibles de descubrir o alcanzar nuevos emplazamientos y no dispone de una secuencia realizable de acciones ordinarias o recuperación permitida que restablezca el progreso exploratorio.

La definición requiere distinguir:

- **Ausencia de frontera visible:** no se conoce una oportunidad nueva. Es un síntoma, **no prueba** de bloqueo real.
- **Frontera potencial detectada:** existe ruta, contacto, archivo, uplink o pista aparentemente pendiente. No demuestra por sí sola progreso *efectivo*.
- **Bloqueo estructural real:** no hay procedimiento legítimo utilizable para salir de la región/estado exploratorio bajo las condiciones del análisis.
- **Imposibilidad operativa o de supervivencia:** falta energía, repuestos, combustible, salud, drones, integridad, etc. Se estudia aparte. F-DEAD-01 no debe suministrar recursos ficticios para evitarla.
- **Deadnode:** destino conocido o forzado sin acceso desde el componente alcanzable ni resolución local; no implica necesariamente que toda la exploración esté bloqueada.

La falta de progreso narrativo por una pieza authored bloqueada es un fenómeno distinto, aunque puede interactuar con la frontera exploratoria. La elección voluntaria del jugador de no usar un mecanismo disponible tampoco equivale a bloqueo estructural.

## 2. Cómo puede aparecer un bloqueo en el universo actual

`historical-world-v1` fija emplazamientos y topología antes de explorarlos, pero **no** exige conectividad universal (decisión D04). Los saltos operativos tienen cap de 45 años luz y el conocimiento del jugador es distinto de la existencia y de los enlaces físicos. Una nave podría agotar una región accesible aun cuando existan miles de lugares en otras regiones.

B1 (`historical-information-v1`) añade archivos y candidatos de uplink estables; B2 (`historical-radio-v1`) añade emisiones y ondas físicamente propagadas. **Ambos aumentan las oportunidades, pero ninguno demuestra que siempre llegue una pista nueva.** Un escaneo puede no detectar, un uplink puede agotarse o indicar lugares ya conocidos, un archivo puede ser ambiental o estar inaccesible, una señal puede carecer de `LINK` o quedar fuera de potencia/ventana temporal. Conocer dos extremos de una ruta remota tampoco aporta necesariamente un camino desde la nave.

Casos a investigar: regiones históricamente separadas; componentes alcanzables agotados; contactos que exigen un origen no alcanzable para `route solve`; fuentes informativas ya consumidas o sin navegación; pistas pendientes que en realidad no abren caminos; fuentes de radio inexistentes, fuera de cobertura o ya pasadas; límites de búsqueda y retención. Ningún caso individual equivale automáticamente a bloqueo irreversible: podrían existir otras acciones legítimas no examinadas.

## 3. Qué comprueba hoy el detector

[`has_exploration_frontier`](../../src/retorno/core/exploration_recovery.py) considera, entre otras cosas:

1. Un plan de recuperación activo o intel ya recuperada susceptible de aportar enlace.
2. Registros `NODE` legibles desde los que pueda surgir una resolución local válida.
3. Rutas conocidas hacia destinos no visitados.
4. Contactos adquiridos sin ruta que permitan `route solve` desde algún origen alcanzable, dentro de sensor y cap de salto.
5. Uplinks aún disponibles en instalaciones alcanzables.
6. Archivos recuperables, pushes y otras fuentes informativas pendientes.
7. Pistas de recuperación recibidas pero todavía no importadas.

La evaluación global se solicita al no encontrar frontera reconocida; la habilitación operativa de `is_exploration_capable` exige, entre otras condiciones, energía adecuada, Core OS nominal, sensores al menos limitados y `sensord` operativo, sin tránsito/hibernación. El seguimiento de **deadnodes** usa umbrales distintos: no debe confundirse con el detector global.

**Riesgo de falsos positivos:** un archivo pendiente puede no ofrecer navegación; un uplink puede contener únicamente destinos ya conocidos; una frontera detectada puede no ser realizable. **Riesgo de falsos negativos:** el detector puede no reconocer una oportunidad legítima accesible a través de otro mecanismo, momento o posición. Deben demostrarse casos reproducibles; no basta con suponer que el algoritmo es completo.

## 4. Qué ofrece F-DEAD-01 nivel 1 y qué no garantiza

El selector estructural trabaja con emplazamientos certificados del manifiesto y busca cadenas de acceso dirigido. Su **primera etapa** requiere una emisión de navegación histórica válida y recibible, continua y sin final; los enlaces posteriores necesitan fuentes verificables, registros B1, radio B2 o rutas conocidas. Se reutiliza el ledger común. No se inventan instalaciones, aristas físicas, archivos ni transmisiones en respuesta al bloqueo.

Las búsquedas son progresivas, paginadas y limitadas por presupuesto (por defecto: 16 sectores físicos, 2048 sitios, 4096 expansiones, 65536 pruebas de arista; además de límites propios de fuentes). Pueden producir `validated`, `conditional`, `none_in_scope`, `incomplete` o `invalid`. **`none_in_scope` no demuestra inexistencia galáctica de salida; `incomplete` no debe convertirse en ausencia.** Un plan válido tampoco implica supervivencia o que el jugador haya leído/importado y utilizado la pista.

Por tanto, **no está demostrado** que el nivel 1 baste para evitar bloqueos en todas las partidas, ni que su insuficiencia sea frecuente. Las comparativas de semillas y recorridos anteriores verifican funciones concretas, pero no una propiedad universal ni partidas de agotamiento sistemático de fronteras.

## 5. Investigación antes de decidir el nivel 2

**Prioridad:** completar la revisión del sistema authored y realizar partidas integrales con Textual y sonido; estudiar la continuidad exploratoria durante esas pruebas. No alterar balance radioeléctrico ni implementar una reparación excepcional sin evidencia.

Protocolo propuesto:

1. **Definir un oráculo de progreso** para pruebas controladas: acciones legítimas disponibles, componentes dirigidos, rutas calculables, contactos/material informativo accesibles, ventanas reales de radio y posibilidad efectiva de descubrir y visitar un nuevo lugar. El oráculo de depuración puede conocer el mundo; la UI pública, nunca.
2. **Recorrer semillas y configuraciones diversas**, con y sin contenido authored, en regiones de diferente densidad. Registrar recorridos públicos prolongados, no solo inicio y primer contacto; complementar con escenarios sintéticos adversariales reproducibles.
3. **Clasificar cada aparente agotamiento**: progreso natural posible, recuperación nivel 1 validada y consumible, plan condicionado, búsqueda incompleta, ausencia local de fuente, falsa frontera, fallo de activación o bloqueo estructural demostrado.
4. **Seguir la cadena completa**: detección, selección, recepción físicamente válida, lectura/importación, nueva ruta o contacto, viaje y continuación; no contar un mensaje recibido como solución automática.
5. **Separar límites**: efectuar la prueba estructural suponiendo equipamiento funcional y recursos suficientes; probar supervivencia y disponibilidad de reparación en otro bloque. No consumir pruebas como si fueran partidas reales.
6. **Documentar métricas y contraejemplos**: seed, versión/reglas, estado inicial, secuencia reproducible, hora/posición, componente conocido, fuentes agotadas, razón y presupuesto del selector, resultado real, si el jugador podía conocerlo legítimamente, y la mínima corrección candidata.
7. **Repetir tras correcciones** y comprobar determinismo, save/load, ausencia de filtraciones `C-DATA-004`, no creación retrospectiva y protección authored.

### Criterios de evaluación

- **Caso satisfactorio:** se demuestra una secuencia legítima para continuar, ordinaria o mediante nivel 1, sin teletransporte ni recursos inventados.
- **Defecto:** se encuentra bloqueo estructural reproducible pese a existir una solución que los mecanismos deberían poder ofrecer; corregir primero detector/selección/distribución o procedencia, según su causa.
- **Brecha de diseño:** no existe fuente legítima accesible ni plan nivel 1 demostrado en la situación analizada; estudiar solución estructural compatible con el canon antes de introducir intervención física.
- **Evidencia insuficiente:** presupuesto agotado, ventana o condición temporal sin resolver, prueba incompleta. Nunca contabilizar como garantía ni como imposibilidad universal.

Las pruebas de un conjunto finito de semillas aportan **confianza empírica**, no una demostración matemática de «ninguna partida». Una garantía fuerte requeriría un invariante del generador/recuperación y pruebas adecuadas de sus supuestos, o una formulación más acotada del objetivo. La posible tensión entre D04 (sin conectividad histórica universal), D08 (sin rescate garantizado) y la aspiración de continuidad debe resolverse explícitamente sin cambiar el canon por inferencia.

## 6. Estado de decisiones y seguimiento

| Asunto | Estado |
| --- | --- |
| Aspiración a evitar bloqueos exploratorios involuntarios en cualquier partida viable | **Objetivo de diseño, pendiente de validación** |
| Nivel 1: recuperación histórica certificada, información B1 y radio B2 | **Implementado, sin garantía universal demostrada** |
| Investigación de falsas fronteras y bloqueos reales | **Pendiente; incorporar en 4D-3e6** |
| Ajuste de balance radioeléctrico | **Aplazado** |
| F-DEAD-01 nivel 2: reparación/reactivación física excepcional | **Aplazado; no implementado** |
| Primer conjunto authored y revisión de guías | **Pendiente** |

El diseño reservado del nivel 2 exigiría una instalación y archivos históricos preexistentes, intervención mínima físicamente plausible y persistente, inicio real de una nueva emisión y retardo de propagación; nunca emisiones retrospectivas. **No se ejecutará por defecto**. Primero se debe demostrar una necesidad que el nivel 1 o una corrección menos intrusiva no puedan resolver.

**Seguimiento:** futuras evidencias en `docs/testing/`, con un informe por campaña y enlaces desde este documento. Revisar el estado tras la validación integral. El documento no declara resultados experimentales que todavía no existen.
