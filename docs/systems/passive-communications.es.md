# Comunicaciones pasivas — 4D-3e5b

[English](passive-communications.md). Contrato vigente para revisión externa.
La física y los datos se especifican en [radio espacial y temporal](radio-spacetime.es.md).
Historial de e4b: [informe anterior](../testing/passive-communications-review.es.md).

## Equipo y operación

`comms` (Sistema de comunicaciones) es un ShipSystem en BRG-01. Comienza
instalado, apagado, `forced_offline=True`, salud 0.72 y sin carga eléctrica.
Su salud inicial permite LIMITED; por debajo de 0.60 necesita reparación antes
de encender. Requiere `energy_distribution >= NOMINAL` y suministro efectivo.
`power on comms` no arranca `radiod` (Servicio de comunicaciones por radio):
se inicia con `boot radiod`, trabajo ordinario de 5 segundos. Apagar el equipo
detiene el servicio. Se conservan reparación, deterioro, avisos y dependencias.

Consumo nominal provisional 0.15 kW: LIMITED 0.12, NOMINAL 0.15, UPGRADED
0.165 kW; completo en CRUISE. Prioridad 4, deterioro base 8.5e-11/s,
k_power=0.30, k_rad=0.10 y factores globales intactos. Escuchar más lejos no
aumenta consumo. No se simula energía o reparación del emisor.

`radio_block_reason` exige salud coherente y estado LIMITED/NOMINAL/UPGRADED,
dependencias, Core OS al menos LIMITED, terminal disponible, Q >= 0.55, sin
brownout, generación + descarga suficiente y radiod instalado/activo. Reutiliza
los kernels eléctricos del motor. Suspende recepción durante tránsito e
hibernación. Sensores/sensord y data_core/datad no son requisitos de radio.

## Fuentes, preparación, captura y lectura

`radio_spatial_block_reason` comparte cobertura entre selección y captura.
Con declaración física usa distancia 3D, potencia y sensibilidad; la captura
añade la ventana propagada a c mediante `radio_temporal_block_reason`.
Preparar no es emitir. Sin metadatos nuevos, la compatibilidad heredada sigue
limitada al host físico actual, kind admisible y dock cuando proceda, sin
atribuir varios años luz ni retardo histórico a un mensaje local.
Esta compatibilidad no autoriza emisiones para planes F-DEAD-01 nuevos: cada
etapa de radio necesita una emisión declarada, también cuando sea local.

| Canal | Contrato |
| --- | --- |
| captured_signal | Radio; declaración física o compatibilidad local del trigger original. |
| station_broadcast | Radio desde station/relay/waystation; no toda estación emite. |
| ship_os_mail interno | Entrega interna independiente de radio. |
| Mail externo explícito | `mail_origin: external`, `external_origin=True` o SourceRef external usa radio y conserva la envoltura mail. |
| salvage_data | Recuperación por pool/dron, sin radio. |
| uplink_trace / uplink_only | Gates locales de data_core/datad; sin radio. |

Solo existe `WorldState.radio_opportunities`, con `RadioOpportunity`.
Identidades legacy se conservan; declaraciones usan `radio:<emission_id>` y lore
`lore:<piece_key>`. Se congelan contenido EN/ES, fuente/host, trigger, dock,
metadatos del productor y preparación; con datos nuevos también emisor/emisión.
No se congela alcance: cada captura revalida posición, sensibilidad y tiempo.

1. `pending`: sin archivo, evento de recepción, intel, unlock ni consumo narrativo.
2. `received`: un archivo GUEST real y SIGNAL_CAPTURED/BROADCAST_RECEIVED/MAIL_RECEIVED;
   solo entonces se confirman pool, lore, contadores y cooldown correspondientes.
3. `read_imported`: `cat`, `mail read` o `intel import` accedieron al archivo.
   La intel válida se aplica por su parser; el estado no garantiza un unlock.

Los IDs se capturan una vez, también tras save/load. Borrar un archivo no lo
recrea. El productor puede intentar captura tras preparar. Al final del tick,
después de energía/desgaste/consecuencias, los reintentos escuchan emisiones
independientes declaradas y reevalúan pendientes. No necesitan `scan`.
Referencias `piece_key` no se preparan por proximidad: conservan scheduler,
pesos, ventanas y triggers dock/uplink/salvage, además del contexto de dock.
No cambia la probabilidad de singles, deadlines ni el significado de signal_count.

F-DEAD-01 comparte estas fronteras: primera recepción remota exige aviso
preexistente certificado, suficiente señal y llegada efectiva. No se inventa
actividad retrospectiva ni un nuevo transmisor. Se conserva búsqueda ampliable,
protección, intentos, cooldowns y progresión; véase su [contrato](structural-recovery.es.md).

## Persistencia, conocimiento y comandos

Contenedor V2/schema 3, checksum y backups intactos. Slots antiguos sin metadatos
usan defaults locales. Se valida catálogo/snapshot, configuración de radio,
hosts, índice, ledger y planes. Incompatibles se rechazan sin borrar/reescribir.
Añadir radio cambia huella de contenido, no la identidad física del manifiesto.

`status`/`diag comms` solo muestran receptor, salud, energía, servicio y capacidad
operativa conocida. Nunca cantidades, nombres, distancias ni ventanas de señales
ocultas. `ready` no promete una emisión. `debug on` permite `debug radio` con
parámetros y causas internas; `debug recovery` consulta búsquedas/planes guardados.
Son consultas puras: sin generación, RNG, avance, captura ni importación. CLI y
Textual comparten renderers; tipos de evento y audio permanecen intactos.

```text
diag comms
power on comms
boot radiod
jobs
cat /logs/signals/<archivo_recibido>
power off comms
```

Las señales lejanas pueden estar en viaje o haber pasado. El silencio no prueba
ausencia. Reparar en BRG-01 y estabilizar alimentación permite nuevas capturas
cuando la modalidad aún las justifica. Recepción no implica interlocutores vivos.
Pruebas: passive_communications_smoke (18), knowledge_boundary_smoke (19),
radio_spacetime_smoke y el [informe de esta fase](../testing/radio-spacetime-review.es.md).
