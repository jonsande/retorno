# Motores, antimateria y velocidad de crucero

Implementado según CANON v0.5.0, C-TECH-001–007 y los parámetros provisionales
P-TECH-001–002. El commit canónico es
`bc95cae37c04c4cd20f9e205558766bb8bdbb066`.

`bootstrap.py` crea `engines` en ENG-R1 en NOMINAL, con integridad 0.90.
Sustituye al anterior sistema `security` y servicio `securityd` del jugador.
No afecta a otras instalaciones ni a conceptos de control de acceso. ENG-R1
está activo, no reservado. No hay diagnósticos independientes de componentes.

El modelo existente `ShipSystem` gestiona desgaste, transiciones por integridad,
consumo eléctrico, diagnóstico y reparación con drones. Los parámetros
provisionales utilizan una carga auxiliar de 0.2 kW y deterioro de
8.5e-11/s, con k_power=0.30 y k_rad=0.10. La prioridad 1 y etiqueta critical
preservan la alimentación del motor frente al apagado automático por carga;
CRUISE no lo aísla ni reduce su carga auxiliar. Sigue siendo posible el
apagado manual y el deterioro físico. La salida exige motores alimentados en
DAMAGED o superior; CRITICAL, OFFLINE o integridad cero bloquean la salida.
El desgaste posterior utiliza el modelo de tránsito existente y afecta al
precio de futuras salidas.

`ShipState.antimatter_capsules` es la reserva divisible en tiempo real:
12.0 cápsulas equivalentes iniciales. El contador es independiente del
manifiesto desactualizable de chatarra/módulos; una auditoría nunca lo
restablece. Las cápsulas se almacenan en CRG-01 con confinamiento autónomo.
`power_core` es un reactor compacto de fusión independiente con reservas
internas selladas y sin recurso consumible del jugador. Los reactivos
ordinarios del motor no tienen inventario separado.

`Engine.engine_fuel_cost` implementa la fórmula provisional:

```text
(0.5 + distancia_ly / 10)
* (1 + 1.5 * (1 - clamp(health / health_max_effective, 0, 1))**2)
* multiplicador_mejora
```

El multiplicador es 1.0 sin paquete de eficiencia y 0.8 con él. Los efectos del
catálogo de módulos definen el multiplicador; los trabajos existentes de
instalación/desinstalación lo activan y retiran. Varias copias del mismo paquete
no acumulan el efecto. Instalar cuesta 18 de chatarra y exige dron dentro de la
nave y soporte de bahía habituales; retirar devuelve el módulo a bodega.
Los efectos del módulo nunca cambian integridad ni máximo efectivo del motor.

`Engine.estimate_travel_fuel(state, destination_id)` es una consulta pública de
solo lectura que devuelve float sin redondear, o `None` si no puede estimarse
un salto directo conocido y físicamente válido. Comprueba conocimiento
adquirido del destino, ruta directa y límite de salto antes de calcular el
coste. No genera sectores, modifica distancias finas, importa intel ni consume
RNG. La clasificación local utiliza la misma regla de sector/radio que viajar,
incluso sin distancias finas almacenadas. El coste local es cero.

Las salidas interestelares aceptadas descuentan la cantidad estimada una vez,
inmediatamente antes de activar el tránsito. Con combustible insuficiente no
cambian navegación, caché de distancias ni combustible. Ninguna tolerancia
admite reservas inferiores al precio exacto. Repetir salida en tránsito, los
ticks, la llegada y `nav abort` no cobran más; abortar no devuelve combustible.
Las cantidades flotantes conservan toda su precisión interna sin redondeo por
viaje; los costes mostrados usan la representación reversible de float de
Python para no prometer salidas más baratas por redondeo visual. Las consultas
y la confirmación reflejan integridad y módulos actuales; la simulación en
curso puede modificar el precio futuro antes de aceptar la salida.

CLI/REPL y Textual comparten renderizadores y `fuel_readout` de `cli/repl.py`,
así como las mismas acciones de Engine. Comandos públicos:

- `inventory`, `cargo`, `status`: reserva actual de cápsulas.
- `nav map routes` (alias `nav routes`): estimaciones para rutas directas
  conocidas, reserva disponible y suficiencia. La confirmación repite el coste.
- `diag engines`, `locate engines`, `power status`, `power on/off engines`:
  estado global del motor, ubicación y control eléctrico.
- `drone deploy D1 ENG-R1`, `drone repair D1 engines`: reparación existente.
- `module inspect engine_efficiency_upgrade_01`, `drone install D1
  engine_efficiency_upgrade_01`, `drone uninstall D1
  engine_efficiency_upgrade_01`: flujo existente si hay copia en bodega.
- `man engines`, `man engine_efficiency_upgrade_01`: manuales bilingües.

Se conservan waypoints, reglas de hibernación, fórmula de tiempo propio y límites
de salto. T-04A añade las velocidades de salida por estado y el crucero inercial siguientes. La validación de guardado rechaza configuraciones anteriores del
jugador; no existe migración al nuevo estado de motores/combustible. Recuperar
cápsulas por salvage, su distribución procedural y resolver el agotamiento
quedan fuera de esta fase. El pool existente puede proporcionar el módulo de
eficiencia como módulo raro de nave.

## T-04A: velocidad por estado y crucero inercial

`ShipState.cruise_speed_ly_per_year` sigue siendo la referencia nominal
configurable (inicialmente 0.5). `Balance.ENGINE_SPEED_MULTIPLIERS` define el perfil:

| Estado | Multiplicador | Velocidad inicial |
| --- | --- | --- |
| UPGRADED | 1.6 | 0.8c |
| NOMINAL | 1.0 | 0.5c |
| LIMITED | 0.8 | 0.4c |
| DAMAGED | 0.6 | 0.3c |
| CRITICAL / OFFLINE | sin salida | no disponible |

`ShipState.engine_operating_state()` centraliza el estado específico del motor,
con las bandas absolutas existentes de Balance: nominal con salud >= 0.85,
limitado con >= 0.60, dañado con >= 0.35, crítico por encima de cero y apagado
con cero o aislamiento forzado. Solo `engine_speed_upgrade_01` instalado permite
UPGRADED con salud nominal. La salud por sí sola nunca lo concede. Desgaste,
reparación, restauración eléctrica manual y finalización de módulos usan la misma
regla; los demás sistemas conservan sus reglas de estado.
`effective_cruise_speed()` aplica el perfil y limita velocidades finitas positivas
a `math.nextafter(1.0, 0.0)`; resultados no positivos o no finitos bloquean salidas
interestelares. El viaje local sigue a 20 km/s, con los requisitos existentes de
motor, independientemente de los multiplicadores interestelares.

El módulo de velocidad usa catálogo, pool raro, coste de 18 de chatarra y tareas
ordinarias de instalación/retirada mediante drones. Su efecto booleano en catálogo
describe la activación de esta capacidad de estado. Varias copias no acumulan
beneficios; retirar la última restaura el estado apropiado para la salud.
Puede coexistir con el módulo de eficiencia. No cambia salud, máximo efectivo,
bonificaciones eléctricas ni precio de antimateria. Solo para engines, UPGRADED
consume la misma potencia auxiliar que NOMINAL, evitando el multiplicador eléctrico
genérico 1.10 de UPGRADED.

La salida interestelar aceptada calcula velocidad efectiva y duración, registra
`transit_speed_ly_per_year` y fija llegada. `Engine._tick_interval` usa ese valor
congelado para `proper_time_interval`: dt * sqrt(1 - beta²). Desgaste, reparación,
alimentación, configuración nominal o finalización de módulos posteriores afectan
a futuras salidas, nunca a velocidad, ETA o tiempo propio del viaje en curso.
La llegada sigue separando movimiento y reposo; abortar termina el movimiento sin
reembolso. No se simula aceleración ni frenado. Generación eléctrica, desgaste,
radiación, trabajos e hibernación conservan su integración temporal galáctica.

Guardar/cargar persiste ambos módulos y la velocidad congelada sin reconstruirla
con el estado actual del motor. Se rechazan guardados interestelares activos sin
velocidad congelada positiva válida inferior a c; no se implementan migraciones.

`Engine.estimate_travel_duration` devuelve segundos galácticos o None para saltos
desconocidos, inválidos o actualmente no disponibles. Comparte con combustible
el límite de rutas directas adquiridas y calcula rangos locales ausentes sin
caché ni uso de RNG. El planificador usa la misma consulta de velocidad efectiva.
CLI/REPL y Textual comparten `speed_readout` en status, diag engines, rutas y
confirmación; el panel de sistemas de Textual también lo incluye. Distingue
velocidad disponible, referencia nominal y velocidad real en tránsito; las
estimaciones son para futuras salidas, no revisiones de la ETA activa. Module
inspect y los contadores de instalación describen ambos efectos independientes.
`help --verbose` y los manuales cubren las consultas; help simple conserva sintaxis.

Usa `module inspect engine_speed_upgrade_01`, `drone install D1
engine_speed_upgrade_01`, `drone uninstall D1 engine_speed_upgrade_01` y
`man engine_speed_upgrade_01`. Se conservan las restricciones ordinarias:
CRUISE aísla drone_bay; restaura su soporte para instalar/reparar. No se permiten
solicitudes nuevas de retirada en tránsito; una retirada ya encolada puede terminar.

Las pruebas focalizadas están en `tests/test_engine_speed_upgrade.py`, junto con
las existentes de velocidad, relojes y antimateria. La [validación T-04A](../testing/engine-speed-upgrade-review.es.md)
registra comprobaciones y límites. Añadir al catálogo cambia su huella existente;
los guardados dependientes del catálogo anterior requieren partida nueva. La
fixture histórica del prólogo excluye explícitamente ambos módulos nuevos.

La validación está en `tests/engines_antimatter_smoke.py`, complementada por
las pruebas existentes de prólogo, rutas, energía, persistencia, traducciones
y Textual.

Comprobación mínima en Textual desde la raíz del repositorio:

```bash
RETORNO_SCENARIO=fast_sandbox PYTHONPATH=src /home/jon/prog/retorno_case/retorno_venv/bin/python -m retorno.ui_textual.app --new-game
```

Consulta `inventory`, `diag engines`, `ship map`, `nav map routes`; elige una
ruta mostrada, ejecuta `nav <id>` y confirma. Compara la nueva reserva con el
coste estimado. Ejecuta `nav abort` y confirma; la reserva debe mantenerse.
Para el prólogo normal usa `--new-game` y restaura energía/sensores antes de
adquirir rutas.

Los resultados de pruebas y la comparación con HEAD limpio están en [validación](../testing/engines-antimatter-review.es.md).
