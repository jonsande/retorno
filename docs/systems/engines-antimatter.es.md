# Motores, antimateria y velocidad objetivo de crucero

Implementado en `main` después de T-04A/B1/B2 (`d423fef`), según CANON v0.6.0
C-TECH-008/009 y P-TECH-003/004. Se actualiza el contrato existente de motores;
la discrepancia de desgaste ordinario continúa resuelta.

`engines` es el conjunto de propulsión por antimateria de ENG-R1: integridad
inicial nominal 0.90, auxiliares de 0.2 kW, prioridad 1 y protección de las
políticas existentes CRUISE/apagado automático. `power_core` genera electricidad
por fusión de forma independiente. La reserva divisible (`antimatter_capsules`,
inicialmente 12.0) es independiente del manifiesto de bodega. No se añade módulo,
suministro de cápsulas, aceleración/frenado ni cambios de velocidad en tránsito.

## Selección, techo y tránsito

- `engines speed`: consulta pura a bordo, disponible durante el tránsito.
- `engines speed max`: elige el mayor escalón admitido en cada salida.
- `engines speed 0.3`: guarda un objetivo explícito; reconoce escalones de
  0.1c a 0.8c, pero solo permite seleccionar valores actualmente disponibles.
- Durante cualquier tránsito se rechazan cambios, incluida otra selección de max.

`ShipState.target_cruise_speed` guarda None para max (predeterminado de partida
nueva), o un beta numérico. Nunca sustituye `cruise_speed_ly_per_year`, referencia
nominal configurable, inicialmente 0.5. `maximum_cruise_speed()` calcula capacidad
según salud real, aislamiento eléctrico y equipo instalado mediante
`Balance.ENGINE_SPEED_MULTIPLIERS` y `ENGINE_SPEED_UPGRADE_MULTIPLIERS`.
Elige el mayor escalón disponible igual o inferior al techo escalado por esa
referencia, siempre inferior a c. Con la referencia nominal predeterminada:

| Salud/estado del motor | Sin módulo de velocidad | Con módulo |
| --- | --- | --- |
| Capacidad nominal (NOMINAL / UPGRADED) | 0.5c | 0.8c |
| LIMITED | 0.4c | 0.6c |
| DAMAGED | 0.3c | 0.4c |
| CRITICAL / OFFLINE / apagado forzado | sin salida | sin salida |

`engine_operating_state()` conserva las bandas absolutas de salud y la
presentación UPGRADED solo con salud nominal y equipo instalado. El techo mejora
también en LIMITED/DAMAGED sin exigir esa etiqueta. Las copias no se acumulan.
`effective_cruise_speed()` devuelve la velocidad de la próxima salida: techo con
max, objetivo explícito válido o cero si dejó de serlo. Un objetivo invalidado
por daño, aislamiento o retirada permanece guardado. La salida interestelar se
bloquea; reparar/reinstalar puede recuperarlo, o se puede elegir max/un valor
menor admitido. No se reduce silenciosamente un objetivo explícito.

El viaje local mantiene 20 km/s, coste cero y requisitos físicos existentes.
Ignora el objetivo interestelar, incluso si quedó invalidado desde su selección.
CRUISE es un perfil eléctrico independiente; cambiar objetivo no aplica ese
perfil ni modifica potencia auxiliar, salud o máximo de salud.

## Combustible y estimaciones

`Engine.engine_fuel_cost(state, distance_ly, speed=None)` conserva la fórmula
original de integridad/eficiencia y multiplica por el factor de velocidad de
salida de `Balance.ENGINE_SPEED_FUEL_MULTIPLIERS`:

```text
(0.5 + distance_ly / 10)
* (1 + 1.5 * (1 - clamp(health / health_max_effective, 0, 1))**2)
* multiplicador_eficiencia * multiplicador_velocidad
```

| Velocidad | Multiplicador de precio |
| --- | --- |
| 0.1c | 0.30 |
| 0.2c | 0.48 |
| 0.3c | 0.66 |
| 0.4c | 0.82 |
| 0.5c | 1.00 |
| 0.6c | 1.28 |
| 0.7c | 1.65 |
| 0.8c | 2.20 |

El argumento opcional explícito permite valorar un escalón válido en simulación/
pruebas; las acciones/consultas ordinarias resuelven y validan antes el objetivo
actual. Sin velocidad futura válida no hay estimación interestelar disponible.
La estimación local sigue siendo cero.

`engine_efficiency_upgrade_01` multiplica el coste por 0.8 independientemente de
techos o selección. `engine_speed_upgrade_01` eleva techos sin descuento/recargo
directo a igual velocidad e integridad. Instalarlo con max puede elevar velocidad
y coste del próximo viaje. Ambos módulos raros de nave mantienen coste 18 y flujo
ordinario de drones; las copias no acumulan beneficios. UPGRADED consume la misma
potencia auxiliar que NOMINAL.

Las consultas públicas comparten autorización de rutas directas adquiridas;
nodos desconocidos, sin ruta, ausentes o fuera del límite devuelven None sin
generar sectores, escribir rangos, importar intel ni consumir RNG. La duración
es distancia / velocidad de salida válida, o el cálculo local existente.
CLI/REPL y Textual comparten parser, acción y renderizadores
(`render_engines_speed`, `speed_readout`, `fuel_readout`), además de opciones de
autocompletado. Status y `diag engines` distinguen objetivo,
techo, velocidad futura, velocidad real congelada, referencia nominal y modo eléctrico.

La consulta ordinaria `engines speed` tiene una vista específica: estado y
objetivo (MAX con velocidad resuelta, o valor explícito), seguidos de indicaciones
de configuración/manual. Un objetivo no disponible muestra el techo permitido
y bloqueo de salida sin cambiar la selección guardada. En tránsito añade la
velocidad real congelada (km/s en viaje local) y la restricción de cambios, en
lugar de la indicación de configuración. Modo eléctrico y referencia nominal
permanecen en el diagnóstico completo.

`nav_confirmation(state, action)` genera una única vista y pregunta pública,
sin mutación, para REPL y Textual: ID público del destino; crucero objetivo/efectivo
y ETA galáctica; coste aproximado de cápsulas, reserva actual y restante estimada.
Las cápsulas usan tres decimales y `~` en las estimaciones redondeadas. La maniobra
local reutiliza la clasificación real y muestra km/s, ETA compacta y combustible
cero. Una estimación no disponible muestra guiones y bloqueo; la falta de
combustible conserva su aviso. La pregunta ordinaria es neutra. Se mantiene
íntegro el aviso de abandono de drones desplegados/deshabilitados fuera de la nave.
Consultar, aceptar la pregunta o rechazarla no cobra ni inicia tránsito: solo lo
hace la acción posterior del Engine existente tras revalidar las condiciones.
Sin cambios de audio, drenaje de eventos automáticos ni flujo de aceptación/cancelación.

Ambas vistas compactas mantienen etiquetas y cifras neutras, IDs públicos del
destino con acento del tema y estados de motores con colores semánticos existentes.
Las alertas conservan colores de advertencia/error. Los patrones específicos de
`ui_theme.py` no cambian estilos de otros comandos; `fuel_readout` y `speed_readout`
mantienen el detalle diagnóstico completo. Las pruebas focalizadas amplían
`tests/test_engine_speed_upgrade.py`.

`nav map routes` usa una presentación compacta compartida por CLI/Textual:
reserva con tres decimales, estado físico del motor y MAX (velocidad resuelta) o
el objetivo explícito en cabecera. Un objetivo no disponible conserva su valor
y muestra el máximo permitido. Cada línea identificativa existente va seguida
de una línea Combustible/Velocidad/ETA. El combustible es aproximado (`~`, tres
decimales); la clasificación local reutiliza las consultas puras del motor y
muestra km/s. ETA usa `_format_eta_short`. Estimaciones no disponibles muestran
guiones; solo hay avisos por combustible insuficiente o salida bloqueada. Nombres
e IDs públicos usan el acento del tema, los encabezados de navegación conservan
énfasis, las etiquetas de magnitudes quedan neutras y los estados mantienen
colores semánticos. `ui_theme.py` reconoce solo los formatos de esta vista;
los estilos de otros comandos no cambian. Se verifica en
`tests/test_nav_routes_presentation.py`.

La salida aceptada pasa esa velocidad exacta al mismo cálculo de combustible
que las estimaciones y cobra una vez antes del tránsito. Falta de combustible
u objetivo inválido no cambia nave/mundo/rangos/RNG. Repeticiones, ticks y llegada
no cobran más. Abortar no reembolsa ni añade coste. Se conserva precisión completa;
solo se redondean las estimaciones mostradas en rutas y confirmación, sin redondear la comparación de
combustible suficiente ni el descuento. La simulación puede cambiar
una estimación antes de confirmar, así que la aceptación vuelve a validarla.

## Dominios temporales existentes y persistencia

T-04A registra `transit_speed_ly_per_year` y llegada al salir. Los integradores
de relojes, [electricidad](electrical-proper-time.es.md) y
[desgaste ordinario](wear-proper-time.es.md) siguen usando esa velocidad congelada.
No se cambian esos integradores ni su muestreo de llegada. El daño afecta a
salidas futuras, no a velocidad, ETA, tiempo propio ni combustible pagado del
tránsito actual. Dosis, trabajos, drones, soporte vital y narrativa conservan
sus dominios. No se añade bucle de simulación por segundo.

Guardar/cargar persiste selección y velocidad congelada de forma independiente.
Un escalón válido puede guardarse aunque supere el techo actual. Los valores
por defecto del cargador slots existente aportan max si falta la selección;
no se añade esquema nuevo ni migración general. Se conserva la validación de
universo/guardados. No cambia el catálogo ni la distribución procedural de recursos.

## Comprobación pública

Usa `engines speed`, `engines speed 0.3`, `engines speed max`, `nav map routes`,
`diag engines`, `module inspect engine_speed_upgrade_01` y `man engine_speed`.
`man engines` conserva el manual de sistema. Help/manuales EN/ES cubren selección
y eficiencia independiente. Se conservan requisitos de core/energía, soporte de
bahía y restricciones ordinarias de instalación de módulos.

[Pruebas focalizadas, matriz de balance y recorrido Textual con sonido](../testing/engine-speed-selection-review.es.md).
El balance es provisional hasta evaluar economía de cápsulas y mantenimiento
en juego procedural; no se ajustan coeficientes ajenos para mejorar resultados.
