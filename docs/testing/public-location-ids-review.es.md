# IDs públicos de localización — revisión

[English](public-location-ids-review.md).

Implementado para revisión externa, 2026-11-07. Base: `2516c9bec8bcec0262fec85562ea45daa68632c2`, rama `main`.
El árbol queda sin staging. El cambio previo de `log_copy.txt` se conserva
byte a byte y se excluye del parche y del paquete de revisión.

## Resultado y esquema

Las localizaciones procedurales tienen tokens públicos compactos sin espacios,
como `P-1.2.0.1`, aceptados por CLI y Textual. No cambian IDs operativos internos,
identidades históricas, IDs authored, claves de guardado, certificados ni
referencias físicas. El [contrato implementado](../systems/public-location-ids.es.md)
recoge la codificación, prueba de inyectividad, escape de colisiones authored,
límite de conocimiento y separación entre presentación y validación.

El esquema codifica en base 36 coordenadas con signo del sector de generación
e índice histórico. No trunca hashes, no necesita catálogo procedural ni
registro de alias y no depende del descubrimiento. El scope es implícito en la
partida; los tokens no son certificados entre partidas. Las colisiones de
prefijo se escapan usando el espacio authored finito e inmutable, antes de
cualquier descubrimiento. Siguen aceptándose los IDs antiguos y operativos completos.

## Antes/después y comandos

`S-001_+001_+000:WG1_<scope-de-64-caracteres>_1` pasa a `P-1.2.0.1`.
`ECHO_7` conserva `ECHO_7`. Contactos, rutas, mapas, scan, intel, eventos,
survey, vistas de radio/archivo, confirmaciones y cabecera Textual usan la
misma proyección. Se conservan los nombres descriptivos. Las columnas de intel
se abrevian antes de recortarse. Las líneas que solo contienen certificados
HI1/HR1 se omiten en la vista ordinaria y se conservan en la evidencia original;
no se usan como IDs cortos de localización.

Ejemplos TAB con un candidato elegible: `nav P-1.2.0.<TAB>`,
`route solve P-1.2.0.<TAB>`, `dock P-1.2.0.<TAB>`,
`ship survey P-1.2.0.<TAB>`, `drone move D1 P-1.2.0.<TAB>`,
`drone survey D1 P-1.2.0.<TAB>`, argumentos de localización de salvage y
`nav map path P-1.2.0.<TAB>`. Varios candidatos conservan prefijo común y
listado ordinarios. Los proveedores deciden elegibilidad con IDs canónicos;
ninguna colección física oculta suministra candidatos.

## Evidencia y cobertura

`tests/public_location_ids_smoke.py` supera sus 13 grupos:

| Grupos | Alcance |
| --- | --- |
| 01–03 | Doce seeds; direcciones con signo y varios dígitos; órdenes inversos de generación/descubrimiento; tres procesos PYTHONHASHSEED independientes; colisiones simuladas authored públicas/operativas y nombres ambiguos. |
| 04–05 | Save/load; IDs authored/completos; campos de localización de acciones y tuplas de mapa/survey; paridad de eventos y estado del motor canónico. |
| 06 | Autocompletado contextual CLI y presentación EN/ES; filtrado de rutas anterior a la conversión de IDs. |
| 07–08 | Vista LINK reversible byte a byte con certificados; archivo y registro B1 originales; repetición de import; rutas montadas públicas, extensión opcional y controles de acceso. |
| 09 | Observaciones fijas y cambios en nodos/placements ocultos: proyecciones CLI/Textual y errores de tokens desconocidos idénticos, sin resolución ni sugerencias secretas. |
| 10 | Recepción procedural real, conservación de payload/emisión/archivo, lectura/importación, validación e historia de uplink. |
| 11–12 | TAB/Enter Textual reales EN/ES, ambigüedad de prefijo y despacho; callback real de readline y despacho CLI. |
| 13 | Cálculo efectivo de ruta con ID público a un contacto histórico real en una fixture de rango controlada y etiquetada. |

Los scripts completos de worldgen, B1, B2 y F-DEAD-01 se conservan sin cambios
y pasan. El diff productivo no toca acciones/motor, generación, productores de
información/radio, persistencia, topología, balance, economía, audio ni paquetes
narrativos. El texto LINK y las rutas originales siguen entrando en validación,
importación y marca de radio leída; las vistas nunca los reescriben.

## Recorrido público

El paquete incluye una campaña EN con seed 42, transcripción y partidas reales.
El prefijo parte del prólogo sin modificar, repara mediante comandos públicos,
descubre ECHO, adquiere uplinks y visita instalaciones procedurales usando IDs
cortos. Las recargas usan los puntos de control genuinos de llegada.
Una maniobra ordinaria con waypoint crea un origen nuevo; un contacto procedural
cercano ya adquirido se consulta, recibe una ruta calculada con su ID público,
se visita y se acopla. La maniobra solo usa posiciones adquiridas y rutas
conocidas. Incluye hibernación numérica, nav abort y los avisos reales de
radiación; no hay comandos debug, asignaciones al reloj ni concesiones de estado.
Demuestra una interacción concreta, no exploración o supervivencia universales.
La paridad EN/ES se verifica por separado en las matrices reales de UI/CLI.

Testigo concreto: `P-0.3.0.1`, ruta calculada desde `NAV_PT_1720`, navegación, acoplamiento y recarga correctos; 101 entradas registradas de comandos/runtime. La secuencia final incluye `ship survey P-0.3.0.1`, `route solve P-0.3.0.1`, `nav map path P-0.3.0.1`, `nav P-0.3.0.1` y `dock P-0.3.0.1`.

## Regresión y entrega

Regresión global final: **74/75 scripts pasan**. Pasan los 13 grupos nuevos.
El único fallo es la aserción histórica de `radiation_hull_smoke.py` en
`CARNAVAL_34`, línea 183 (falta el evento de nivel de radiación ambiental).
Se reproduce el mismo fallo en un archivo aislado del HEAD base. No se oculta,
no se marca xfail ni se cuenta como aprobado. Se excluye el wrapper serial que
requiere argumento de salida; se ejecutan directamente todos los scripts smoke,
el verificador de manuales, la comparación de manifiestos y la geografía de radio.

Pasan `git diff --check` y la validación de parejas/estilo de manuales. El paquete
contiene archivos nuevos/modificados completos, parche aplicable, inventario
SHA-256 por archivo, procedencia, logs finales, fallo base, comparación de vistas,
transcripción/checkpoints públicos, drivers reproducibles y validación del ZIP.
El SHA-256 del ZIP se suministra a su lado.

Áreas productivas: módulo puro de localizaciones públicas; integración compartida
de entrada, salida y autocompletado REPL; despacho, confirmaciones y cabecera
Textual. Documentación: contrato/informe emparejados, índice, concepto de
navegación y ocho manuales de comandos. No cambian tests existentes; se añade
una matriz de 13 grupos. El inventario automático lista cada ruta exacta.

Los IDs sin scope crecen con la dirección y los escapes authored excepcionales;
son direcciones operativas compactas, no identificadores globales de tamaño fijo.
La vista no es el formato de importación: mandan los archivos originales. No se
añade renombrado manual ni un registro exhaustivo de alias.

No se ha ejecutado staging, commit ni push. El trabajo se detiene para revisión externa.
