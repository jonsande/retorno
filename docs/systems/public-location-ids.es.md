# IDs públicos de localización

[English](public-location-ids.md).

Contrato implementado, 4D-3e5c-ID. Código responsable:
`src/retorno/cli/location_ids.py`; clientes: `cli/repl.py`,
`ui_textual/app.py`, `ui_textual/presenter.py`.

## Identidad y unicidad

Una identidad histórica procedural contiene scope del universo, sector de
generación e índice. Dentro de una partida el scope es implícito. El ID público
codifica las tres coordenadas del **sector de generación** y el índice, no el
sector físico en el que pueda caer una muestra gaussiana:

`P-<base36(zigzag(x))>.<base36(zigzag(y))>.<base36(zigzag(z))>.<base36(slot)>`

Zigzag transforma n no negativo en 2n y n negativo en -2n-1. La base 36 usa
`0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ`, sin ceros iniciales. Por ejemplo:

| Referencia interna | Referencia pública |
| --- | --- |
| `S-001_+001_+000:WG1_<scope-de-64-caracteres>_1` | `P-1.2.0.1` |
| `ECHO_7` | `ECHO_7` |

El ejemplo tiene nueve caracteres. La longitud crece logarítmicamente con la
dirección; no hay un digest de tamaño fijo ni un presupuesto probabilístico de
colisiones. La codificación de enteros con signo es biyectiva, la base 36
canónica es inyectiva y los cuatro campos separados tienen límites únicos.
Por tanto, dos direcciones procedurales diferentes no comparten token en un
universo. Distintas partidas pueden reutilizarlo: es un ID operativo dentro de
una travesía, no un certificado global.

Los IDs authored se conservan. Una reserva determinista de prefijo comprueba
los IDs authored inmutables y las claves de sus alias, sin distinguir mayúsculas.
Si alguno empieza por `P-`, añade `-` hasta dejar libre todo el prefijo (`P--`,
`P---`, ...). Termina al superar la longitud del texto reservado más largo, no
enumera instalaciones procedurales ni depende del descubrimiento. Se verifica
el escape operativo existente `WG1C<n>` frente a colisiones authored con una
grafía interna; conserva la misma dirección sector/índice. Un ID authored que
imita un ID operativo procedural continúa siendo authored.

El manifiesto congelado y el snapshot narrativo ya se guardan. No se necesita
registro de alias, campo de guardado ni migración. Los IDs procedurales antiguos
sin dirección histórica WG1 y los authored conservan su grafía. El acceso de
solo lectura a la definición también funciona antes de la primera
materialización/fijación de sectores. La proyección nunca fija ni genera sectores.

## Resolución y autocompletado

Ambos clientes invocan `repl._resolve_parsed_locations` tras el parser y antes
de las restricciones/despacho. Resuelve localizaciones en Travel, RouteSolve,
Dock, DroneMove, DroneDeploy, DroneSurvey y variantes de salvage, además de las
tuplas ship survey y map graph/path. No cambia el parser ni las acciones del
motor. Los IDs internos completos conservan las restricciones del motor. La
resolución de nombres descriptivos conserva su normalización y rechaza ambigüedad.

La resolución pública compara contactos adquiridos, referencias conocidas del
mapa y la ubicación actual. Nunca invierte un token adivinado mediante el
catálogo físico. Si falla, el comando original trata la entrada como contacto
desconocido sin comprobar existencia física. Resolver un ID adquirido no
concede ruta, acceso local, acoplamiento ni potencia operativa.

CLI/readline y Textual reutilizan los proveedores contextuales de destinos.
Estos calculan rango, cap de salto, rutas conocidas y localidad con IDs
canónicos, y después proyectan el resultado. Dock/dron siguen siendo locales;
nav ofrece rutas alcanzables; route solve ofrece contactos en rango sin ruta.
El autocompletado ordinario nunca toma candidatos de la colección física
oculta. Los delimitadores de readline siguen siendo espacios; Textual conserva
el prefijo común y el listado con doble TAB. No se elige arbitrariamente entre
varios candidatos.

Ejemplos (el prefijo real depende del espacio authored inmutable):

```text
ship survey P-1.2.0.<TAB>  -> ship survey P-1.2.0.1
route solve P-1.2.0.<TAB>  -> route solve P-1.2.0.1
nav P-1.2.0.<TAB>          -> nav P-1.2.0.1
dock P-1.2.0.<TAB>         -> dock P-1.2.0.1
drone survey D1 P-1.2.0.<TAB>
nav map path P-1.2.0.<TAB>
```

Se supone un único candidato elegible. Un contacto conocido por sí solo no
necesariamente aparece en el autocompletado de nav.

## Presentación y evidencia histórica

Los renderizadores ordinarios del REPL usan `@public_output` y el adaptador de
print local al módulo. Un ContextVar limita el estado al renderizador; no se
sustituye stdout global ni se mutan eventos del motor. Los renderizadores
anidados comparten proyección y los contextos concurrentes siguen separados.
Textual captura los mismos renderizadores; también proyecta cabecera y
confirmaciones. Los renderizadores debug explícitos conservan los IDs técnicos.
Status/diag ordinarios conservan sus restricciones de conocimiento. Las columnas
de la lista de intel se proyectan antes de recortarse.

Antes: `LINK: ECHO_7 -> S-001_+001_+000:WG1_<scope>_1`.
Después: `LINK: ECHO_7 -> P-1.2.0.1`.
Los nombres descriptivos siguen acompañando IDs en contactos, mapas y surveys.

Un renderizador autorizado puede proyectar una referencia recién revelada:
la evidencia es el propio documento adquirido y legible. La vista no añade un
nombre, posición, entrada de catálogo ni identidad de emisor. La lectura sigue
entregando el **contenido y la ruta originales** a importación de intel y marca
de radio leída. Parseo LINK, validación de fuentes, referencias físicas,
huellas de archivo, duplicados, protección narrativa y F-DEAD-01 conservan sus
entradas existentes.

Las líneas que solo contienen certificados no narrativos (`HI1:` /
`HR1-record:` con digest completo de 64 caracteres) se omiten en la vista
ordinaria. Siguen en archivos, pools, emisiones, partidas y procedencia. Ningún
certificado se sustituye por un ID truncado. `public_text(..., certificates=True)`
conserva esas líneas; `restore_public_references` revierte sustituciones usando
las referencias finitas autorizadas de la fuente y reproduce exactamente el
contenido LINK original. No descubre extremos arbitrarios.

También se proyectan rutas virtuales montadas que contienen IDs operativos. Su
resolución compara solo rutas existentes del sistema de archivos a bordo;
cat, ls e intel import conservan sus controles de acceso y rutas canónicas de
fuente. No se renombra ningún archivo. El autocompletado ofrece esas rutas
existentes con su grafía visible.

## Validación y límites

`tests/public_location_ids_smoke.py` cubre doce seeds, direcciones con signo,
procesos independientes con distintas hash seeds, descubrimiento inverso,
colisiones de prefijos authored/operativos, save/load, IDs completos, paridad
del motor, proveedores CLI, TAB y despacho Textual reales EN/ES, evidencia
original de LINK/radio, uplink y variaciones negativas de datos ocultos. Las
matrices worldgen/B1/B2/F-DEAD-01 siguen siendo autoridades de identidad
histórica. El informe emparejado recoge un recorrido público independiente y
los resultados de la regresión completa.

No cambian topología, distribución, identidad interna, generación de archivos,
probabilidad de radio, economía, navegación, failsafes, arcos, AMANECER, balance,
audio ni se añade renombrado manual. Los tokens sin scope no deben usarse como
certificados de archivo entre partidas.

[Informe y resultados de validación](../testing/public-location-ids-review.es.md).
