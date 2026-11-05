# Operación AMANECER — Revisión conjunta de continuidad (v0.1)

## Alcance documental
Revisión de los paquetes narrativos: arco 01 v0.1; arco 02 v0.3; arco 03 v0.1; single VAELOR 01; singles 02–09 v0.1. Total: 3 arcos, 12 documentos de arco, 9 singles (21 documentos). No modifica los textos existentes.

## Canon de autor añadido por decisión del usuario
- Lou Levy es un hombre, capitán del carguero civil **Tábano**, originario de **THALLOINOV**, sistema **VAELOR**.
- El **Tábano** debe existir físicamente en las partidas; el generador determina su localización. Después de los cuatro documentos del arco 02, Lou y Leopold obtienen unas coordenadas atribuidas a una posible instalación secreta.
- En camino a las coordenadas, la nave sufre daños que no consiguen reparar. Lou, Leopold y los demás ocupantes que efectivamente estén embarcados mueren a bordo antes de llegar. No establecer tripulantes adicionales sin diseñarlos.
- El jugador puede descubrir el pecio del **Tábano**, sus registros y las coordenadas del lugar sospechoso. El jugador no debe confundir coordenadas investigadas con prueba de la existencia de la instalación ni con prueba de supervivencia de los siete.
- La **Bruma**, sexto transporte de AMANECER, también debe existir físicamente; su posición la decide el generador. El estado de conservación exacto y cómo se recuperan sus registros quedan por definir.
- **VAELOR** debe poder localizarse; contiene **THALLOINOV** (desértico), **Lunviea** (templado bioluminiscente) y **Druinope** (gigante de hielo). En el presente del jugador no queda comunidad humana viva allí, aunque sí vestigios.
- La supuesta instalación secreta debe tener un destino resoluble para que las coordenadas halladas en el Tábano conduzcan a algún lugar real del mundo generado; su naturaleza y contenido no están confirmados.

## Cronología provisional coherente
- T0: evacuación de Liria / Operación AMANECER; sexto transporte **Bruma**; documentación y anomalías durante el embarque y vuelo.
- T0 + 3 horas aproximadamente: separación registrada de un módulo de la Bruma según telemetría reconstruida por Mara.
- T0 + 6 horas aproximadamente: Elena recuerda una transmisión desde Liria. La procedencia verdadera de la señal sigue sin probarse.
- T0 + 11 días: fecha de la última apertura de salida por una de siete credenciales según el registro recuperado por Lou y Leopold; esto **no establece** que la solicitud de materiales del single 05 se realizase exactamente entonces.
- T0 + ~17 años: documentos retrospectivos de Elena.
- T0 + ~18 años: viaje narrado de Lou y Leopold y, posteriormente, pérdida del Tábano en su ruta hacia las coordenadas sospechosas.
- Presente del jugador: desaparición de las comunidades humanas de VAELOR. Cronología absoluta no fijada.

## Conexiones narrativas confirmadas a nivel de textos (no prueba omnisciente)
1. Elena observa doce plazas disponibles para diecinueve personas; Mara relata veinticuatro plazas físicas con certificación de solo doce. No confundir capacidad física con capacidad autorizada por el sistema.
2. Elena descubre una segunda autorización 43 segundos después de su firma; Mara observa una segunda orden en la telemetría a los 43 segundos. Correlación sugerente, no identidad transaccional demostrada.
3. Mara encuentra un consumo de aire equivalente a siete personas y un módulo desacoplado; Lou descubre siete credenciales de salida vinculadas a una instalación receptora. No se ha demostrado que las mismas siete personas estuvieran en ninguno de los dos lugares.
4. Single 05 describe siete kits sanitarios para un proyecto restringido; ofrece una hipótesis de investigación/desarrollo, no una conclusión.
5. Single 06 registra siete tazas en la Bruma; pista física ambigua, no prueba de ocupantes.
6. Single 08 (Joel) sitúa una bolsa de suministros desaparecida en Liria; el propio narrador contempla una explicación ordinaria.
7. Single 04 permite vincular temáticamente una grabación con la madre de Leopold, pero su cliente no está identificado.
8. Single 02 introduce la desaparición independiente de Óscar, que salió en el cuarto transporte. No fundir su historia con los siete.

## Puntos que requieren tratamiento editorial antes de JSON/TXT
- **Hallazgo de las coordenadas**: el arco 02 termina cuando Lou todavía no las tiene. Debe existir un registro posterior legible a bordo del Tábano que explique cómo llegaron a esa localización sin dar por verificada la instalación.
- **Causa del siniestro**: la avería del depurador está prefigurada; puede ser relevante, pero no se ha canonizado el mecanismo exacto de muerte. Evitar llamar «sabotaje» a una avería sin apoyo.
- **Tripulación**: los textos solo identifican con certeza a Lou y Leopold a bordo. «Todos los tripulantes» significa todos los ocupantes que decidamos que existían, no exige inventar nombres ahora.
- **Liria**: estación definida literariamente, pero decisión de generación física pendiente. Evitar nodos duplicados.
- **Bruma**: debe existir; no está establecido que hoy sea un pecio ni qué estado conserva.
- **Calendario**: el 'once días después de AMANECER' del arco 02 debe distinguirse de la fecha relativa del pedido del single 05 ('expediente abierto once días antes del suministro').
- **Orden de hallazgo**: la entrega procedural no garantiza orden. Cada pieza debe poder entenderse de forma aislada. El registro de coordenadas del Tábano es una dependencia de navegación, no necesariamente el cierre cronológico de los documentos de Lou.
- **VAELOR y AMANECER**: que la historia sea conocida en VAELOR no demuestra que los siete llegaran a ese sistema. No forzar tal conexión.
- **Denominación de Liria**: es una estación civil; aclarar cualquier referencia a la terminal como parte de la estación, no como nuevo lugar.
- **Punto de partida**: el single de flete contiene `[SECTOR_VAELOR]`, pendiente de adaptación al sistema real de navegación; no presentarlo como coordenada jugable válida.
- **Erratas documentales**: `README.md` del arco 02 conserva «originaria» para Lou; corregir a «originario» al consolidar documentación. En notas antiguas del arco 01 persiste el empaquetado bajo `amanecer_paquete/arcos/`, distinto de la convención en inglés del repositorio.

## Registro de entidades — contrato narrativo, no esquema implementado
| Entidad | Estado | Ubicación | Uso |
|---|---|---|---|
| Tábano | GENERAR OBLIGATORIAMENTE, pecio | Generador elige | Contiene intel recuperable hacia destino sospechoso |
| Bruma | GENERAR OBLIGATORIAMENTE, nave persistente | Generador elige | Investigaciones de AMANECER; estado físico por concretar |
| VAELOR | GENERAR/LOCALIZAR OBLIGATORIAMENTE | Sector pendiente | Vestigios de un sistema humano perdido |
| THALLOINOV / Lunviea / Druinope | COMPONENTES DE VAELOR | Dependiente de VAELOR | No crear nodos extra por una mención textual |
| Instalación sospechosa | DESTINO RESOLUBLE, identidad misteriosa | Generador elige, coordenadas derivadas | La pista del Tábano apunta a aquí; llegada no valida hipótesis |
| Liria | ESTACIÓN DE LORE, DECISIÓN PENDIENTE | No fijada | Evacuación y posibles registros |
| Módulo auxiliar de Bruma | NO GENERAR INDEPENDIENTEMENTE AÚN | Desconocida | Pista contextual, no misión obligatoria |
| Otros nombres comunes / lugares descriptivos | NO GENERAR | N/A | Ambientación |

## Separación de niveles de conocimiento
- **Autor**: conoce la muerte de Lou y Leopold y la localización real del pecio; decide el destino generable al que apuntan las coordenadas.
- **Personajes**: Lou y Leopold creen haber encontrado un rastro hacia una instalación; nunca comprueban la hipótesis.
- **Jugador**: descubre solo los documentos que encuentre y, si llega al Tábano, recupera la ruta a un lugar sospechoso; puede descubrir datos adicionales allí sin obtener una resolución plena.

## Pendiente de implementación técnica
Confirmar el esquema actual de registro de entidades persistentes y el tipo de intel navegable. Diseñar la secuencia en dos etapas: mención/búsqueda del **Tábano** -> hallazgo del pecio -> lectura del intel que conduce a la **instalación**. No introducir coordenadas literales inventadas, no añadir nodos por mera mención y no alterar mecánicas Python antes de una decisión de diseño explícita.
