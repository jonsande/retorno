# PT001-07A/07B — recarga eléctrica de drones

Propuesta 07A aprobada en revisión externa y materializada en 07B. El consumo
fijo de `drone_bay` permanece en la carga base. La transferencia a drones es
una carga variable adicional y solo existe mientras un dron `DOCKED` en el
sector de su bahía recibe energía. La decisión de `core/drone_charging.py` es
compartida por la contabilidad productiva, la previsión eléctrica y los cortes
causales. No añade campos persistentes.

La calibración aprobada es `0,2 / (0,005 × 3600) = 1/90 kWh` por unidad de
batería de dron. Con bahía nominal, la tasa normal es 0,005 unidades por segundo
propio a 0,2 kW y la lenta es 0,00125 a 0,05 kW. Los multiplicadores existentes
de bahía limitada (0,5) y dañada/crítica (0,25) escalan potencia y tasa juntos.
Una asignación parcial escala la tasa linealmente con la potencia efectiva.
La potencia se reparte por identificador de dron ordenado. La tasa normal exige
excedente real suficiente; la lenta puede usar reserva si la batería de nave
está por encima del 25 % y queda capacidad de descarga tras la carga ordinaria.
En el umbral o por debajo solo se asigna excedente real. El umbral limita la
recarga, no la demanda ordinaria. `DRONE_CHARGE_NET_MIN_KW` ya no decide admisión.

La carga de cada tramo entra en `p_load_kw` antes de integrar la batería de nave;
su carga/descarga conserva `eta_charge`, `eta_discharge` y límites eléctricos
existentes. El incremento del dron usa exactamente la potencia asignada y los
segundos propios. Solo esta recarga cambia de base temporal: exposición,
consumo desplegado, descontaminación y reparación pasiva siguen usando el
intervalo galáctico que recibe el mantenimiento una vez por tick.

La integración eléctrica aplica la regulación inmediata antes de elegir un
corte de recarga. Un deslastre temporizado por calidad es una frontera
eléctrica: la energía anterior usa la asignación previa y la posterior usa la
asignación regulada. La integración divide internamente al llenarse un dron o
alcanzar el 25 %; recalcula el reparto sin volver a ejecutar trabajos,
narrativa, RNG, reparación ni desgaste. Nunca ajusta la batería principal a
un umbral no alcanzado, tampoco en god mode. La previsión física añade esos
cortes en tiempo propio
y compara el incremento efectivo del dron con el previsto. Un intervalo físico
que salte un corte pendiente falla atómicamente. La decisión se invalida al
cambiar potencia, estado de bahía/distribución, capacidad, SoC, elegibilidad o
batería de un dron. Sin recarga activa no se añaden cortes de recarga.

Pruebas dirigidas: `tests/test_pt001_07b.py`. Resultados y límites de la
intervención se registran en `docs/testing/pt001-07b-review.es.md`.
