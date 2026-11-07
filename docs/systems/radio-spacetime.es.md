> **Actualización B2.** [Radio histórica](historical-radio.es.md) añade historias procedurales deterministas de equipo y emisiones a las partidas nuevas junto al contrato authored siguiente. Las cinco clases de instalación tienen hardware original de comunicaciones; capacidad presente y transmisión son hechos separados. El contrato B2 sustituye la ausencia anterior de fuentes procedurales.

# Radio espacial y temporal — 4D-3e5b

[English](radio-spacetime.md). Implementado para revisión externa. Autoridades:
`src/retorno/core/communications.py`, `model/world.py`, `worldgen/radio.py`,
`worldgen/narrative.py` y `config/balance.py`. Pruebas y escena aislada:
`tests/radio_spacetime_smoke.py`, `tests/fixtures/radio_world/`.

## Física y balance provisional

El receptor usa `world.current_pos_ly`. El host de `RadioEmitter` se resuelve
contra el manifiesto histórico, también si está lazy. Un nodo materializado
debe coincidir con su certificado. El emisor no redefine coordenadas.

```text
d = distancia euclídea 3D en años luz
I = P / max(d, 10^-9 ly)^2
S = inverso normalizado del umbral de detección
R = sqrt(P × S) ly; decodificable si S > 0 y d <= R
retardo = d × Balance.YEAR_S
```

P es potencia isotrópica equivalente normalizada a 1 ly; I y S son presupuestos
abstractos, sin calibración W/dBm. El clamp cerca de cero limita I; la frontera
inclusiva usa R. No usa RNG, sensores, rutas ni `MAX_ROUTE_HOP_LY`.
Se rechazan booleanos, no finitos y P fuera de 10^-8..10^4.

| Perfil | P | R LIMITED | R NOMINAL | R UPGRADED |
| --- | ---: | ---: | ---: | ---: |
| `emergency` | 0,25 | 0,25 ly | 0,5 ly | 0,75 ly |
| `station` | 36 | 3 ly | 6 ly | 9 ly |
| `interstellar_relay` | 400 | 10 ly | 20 ly | 30 ly |

Sensibilidades: LIMITED 0,25; NOMINAL 1; UPGRADED 2,25. OFFLINE, CRITICAL y
DAMAGED no decodifican. Son cifras configurables provisionales, no canon ni
tecnología calibrada. P explícita válida ajusta el perfil. Las instalaciones B2
tienen hardware original de comunicaciones; capacidad presente y emisiones reales
requieren su modelo histórico separado. No se reparan instalaciones por narrativa.

## Tiempo

`radio_coordinate_time` adapta provisionalmente `clock.t` a segundos galácticos
desde inicio. `Balance.YEAR_S` son 365 días. La referencia persistida es
`game-coordinate-seconds-v1`; offsets negativos preceden t=0, sin fechas absolutas.
Fuente/receptor se aproximan estacionarios durante cada comprobación.
La ventana en el receptor es `[start_t + retardo, end_t + retardo)`; sin final,
queda abierta. `continuous` representa repetición, con final opcional; `finite`
exige final mayor que inicio y representa pulso con duración/ventana finita.
Ambos offsets deben ser finitos dentro de ±10 millones de años de juego.

Preparación, emisión, llegada, captura y lectura son hechos separados. Una
emisión nueva a 5 ly espera cinco años; una copia declarada desde -10 años puede
estar disponible en t=0. Puede haber terminado en el host y seguir llegando.
Recibir no demuestra supervivientes ni actividad simultánea. No hay caché de onda.
Ticks comprueban el estado final: una continua no se pierde al saltar su llegada;
una ventana finita ya pasada no se captura retrospectivamente. Tránsito e
hibernación bloquean; llegada/despertar permiten la siguiente comprobación.
No se reconstruye escucha de trayectorias. No se implementan tres relojes ni
relatividad; viajes, hibernación, edad, energía, desgaste y deadlines no cambian.

## Datos optativos versionados

Localizaciones tradicionales, arcos y singles instalados admiten este bloque
en su raíz. Hosts pueden proceder de `world_requirements` o IDs procedurales
exactos certificados para la partida; los authored resuelven nombre/ID/alias.

```json
{"radio_emitters":{"version":"radio-emitters-v1","emitters":[{
  "id":"archive-radio","host":"HARBOR_12","category":"station",
  "emissions":[{"id":"archive-copy","mode":"continuous","start_t":-630720000,
    "content_by_locale":{"en":"Automated archive copy.","es":"Copia automática de archivo."}}]
}]}}
```

`power` es opcional; `emissions: []` representa equipo sin actividad. Cada emisión
exige exactamente una fuente de contenido:

- `content_by_locale`: texto inline no vacío EN/ES, sin bindings pendientes.
- `piece_key`: `single:<id>` o `arc:<id>:<pieza>` instalada. La pieza referencia
  esta emisión mediante `radio_emission: "<id>"` y autoriza exactamente su canal;
  mail exige `mail_origin: "external"`. Fija host/canal, preservando políticas.
- `navigation_link_to`: destino certificado ID/alias de un LINK preexistente;
  genera el aviso EN/ES común. Exige extremos distintos y cap de navegación,
  sin afirmar arista histórica ni ruta conocida.

```json
{"id":"dated-pulse","mode":"finite","start_t":0,"end_t":60,
 "content_by_locale":{"en":"Recorded packet.","es":"Paquete registrado."}}
```

Canal por defecto `captured_signal`; se admiten `station_broadcast` y mail
externo. Broadcast exige host station/relay/waystation. Hasta 128 emisiones por
emisor. IDs únicos estables; campos desconocidos, tipos, versiones, ventanas,
referencias ausentes/ambiguas y contradicciones fallan con archivo/entidad/campo.
Es una extensión mínima optativa; las guías editoriales definitivas siguen en e5c.

## Escucha, ledger y recuperación

El snapshot guarda declaraciones y un índice derivado por niveles de potencia.
Cada emisor ocupa una celda de lado potencia de dos >= radio UPGRADED. La consulta
visita hasta 27 celdas por nivel ocupado, devuelve 128 candidatos por tick y
continúa mediante cursor/anchor persistidos. `complete=False` significa incompleto,
nunca ausencia. No recorre la galaxia, materializa ni usa cachés globales mutables.

Con gates operativos válidos, `retry_radio_opportunities` descubre emisiones
independientes disponibles, prepara y captura sin `scan`. Excluye `piece_key`:
solo scheduler y trigger real preparan esos documentos, conservando dock.
El inicializador previo de pools puede materializar en un tick normal; la radio
no añade materialización. Solo existe `WorldState.radio_opportunities`.
Se congelan emisor/emisión/contenido/preparación, nunca alcance/sensibilidad.
Captura revalida posición, salud, estado, alimentación, Q/brownout, dependencias,
Core OS, radiod y contexto. Consumo eléctrico intacto. Identidad única:
`radio:<emission_id>` o `lore:<piece_key>`; otro ID para la misma emisión falla.
Capturar crea archivo/evento; leer/importar aplica intel después, sin duplicación.

Todo plan nuevo F-DEAD-01, local o remoto, exige `navigation_link_to` declarado antes del bloqueo, host
certificado/alcanzable, cobertura y llegada. Se limita conservadoramente a
repetición continua sin final para permitir reparación/encendido posterior.
No inventa LINK ni actividad histórica. Usa sensibilidad útil actual o referencia
NOMINAL para equipo inoperativo, sin filtros de recursos. Futuras/fuera de alcance
no confirman plan; apagado puede dejar `receipt_pending`. Intentos/cooldown solo
avanzan al capturar. La etapa reutiliza `radio:<id>` y puede vincular un pendiente;
una emisión recibida no se duplica. Se persisten ID, sensibilidad/contexto original
y tiempo de preparación; guardar valida esa evidencia, capturar usa estado actual.
Cada etapa de radio guarda su propia emisión y huella de contenido en
`stage_sources`; la confirmación y captura revalidan que autorice exactamente
ese LINK. Una estación sin emisor, un transmisor inactivo o una emisión ajena
no sirven. Las etapas posteriores requieren emisiones declaradas, rutas ya
conocidas o archivos recuperables existentes que contengan la pista. Confirmar
no inyecta archivos ni sustituye contenido por el LINK calculado.

Los planes nuevos usan `historical-recovery-v2`. La compatibilidad local solo
conserva oportunidades v1 ya persistidas e interacciones narrativas legacy
autorizadas. Un plan v1 puede consumir su oportunidad guardada; no puede crear
ahora etapas de radio no preparadas. Los nuevos planes no pueden invocar ese
fallback. La falta de fuentes deja el resultado condicionado, sin intentos ni
cooldown. B2 aporta historias procedurales preexistentes y certificadas por el
mismo resolver; nunca genera una emisión para suplir una carencia de recovery.

Una continuación legítimamente invalidada persiste inactiva con contrato y
progreso comprobados; no exige una oportunidad que nunca pudo prepararse.
Las recepciones previas siguen siendo obligatorias y no se duplican. Una emisión
de una etapa v2 posterior recibida pasivamente antes de activarla se reutiliza
con su ID canónico, sin nueva captura; leer/importar sigue siendo necesario.
Los detalles de integridad y compatibilidad están en
[recuperación estructural](structural-recovery.es.md).

## Compatibilidad e información

Schema 3 antiguo sin metadatos recibe defaults locales, sin emisor interestelar
retroactivo. Contenedor V2, checksum y backups intactos. Save/load valida
declaraciones, índice, ledger y planes; cambios de catálogo/configuración física
de radio se rechazan sin reescribir archivos. Huella completa incluye radio;
`physical_catalog_key` excluye solo esta extensión para conservar manifiesto,
IDs, estaciones y rutas al cambiar metadatos de radio.

`status`/`diag comms` dependen solo del receptor. `debug radio` expone cálculos,
retardos, ventanas y motivos sin mutar; `debug recovery` muestra la primera emisión
del plan. CLI/Textual comparten C-DATA-004. Sin transmisiones activas, repetidores
dinámicos, interferencias, movimiento de emisores, sensores nuevos ni AMANECER.
