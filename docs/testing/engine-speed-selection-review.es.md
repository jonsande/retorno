# Verificación de velocidad objetivo y balance provisional

Implementado sobre `main` en `d423fef7654987b83f186f24630b080a79363712`.
El [contrato existente de motores](../systems/engines-antimatter.es.md) define
comportamiento y fórmulas; este informe recoge pruebas y balance. Sin commit ni push.

## Verificación focalizada

Antes del cambio pasaban las pruebas de T-04A, combustible, crucero, relojes,
electricidad y desgaste: 70 pruebas, 80 subpruebas. La selección final de esas
mismas suites pasa 79 pruebas y 97 subpruebas. Se ampliaron pruebas existentes.
Cubren ocho escalones, max por defecto, todos los techos por salud/módulos,
reparación real con dron, instalación/retirada, invalidación y recuperación del
objetivo fijo, estimación/descuento exactos, ETA/tiempo propio, tránsito congelado,
aborto, viajes locales, consultas puras, protección de datos ocultos, guardado/carga
y ejecución real en CLI/Textual EN/ES.

```bash
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python -m pytest -q \
  tests/test_engine_speed_upgrade.py tests/engines_antimatter_smoke.py \
  tests/test_cruise_speed.py tests/test_temporal_clocks.py \
  tests/test_electrical_proper_time.py tests/test_wear_proper_time.py
```

También pasaron estos scripts independientes, con ese intérprete y PYTHONPATH:

| Script | Resultado |
| --- | --- |
| `tests/energy_policy_smoke.py` | PASS |
| `tests/save_load_smoke.py` | PASS |
| `tests/textual_completion_context_smoke.py` | PASS |
| `tests/known_routes_integrity_smoke.py` | PASS, 10 comprobaciones, semilla 271828 |
| `tests/manuals_style_check.py` | PASS, incluido emparejado EN/ES |
| `tests/audio_config_smoke.py` | PASS |
| `tests/config_audio_smoke.py` | PASS |

Tras cerrar manuales y mensajes compartidos EN/ES de eventos/logs, se repitió la
suite de velocidad: 20 pruebas y 53 subpruebas pasaron. La prueba existente de
vistas públicas también verifica ayuda/manuales. Sin fallos finales; no se ejecutó la suite
general ni se repararon pruebas históricas. Las primeras iteraciones solo adaptaron
expectativas modificadas intencionadamente por precios/techos y el escenario de
la fixture de CLI.

Una comparación AST con la revisión inicial verifica que los únicos métodos
existentes de Engine modificados son `apply_action`, `engine_fuel_cost` y
`estimate_travel_fuel`. Tick, muestreo de llegada, tiempo propio, regulación eléctrica,
batería e integración del desgaste ordinario permanecen intactos. CANON y catálogo
de módulos sin cambios. La selección se valida mediante el formato/cargador existente.

## Matriz determinista

[CSV completo: 54 casos](engine-speed-balance.csv), distancias 2/10/20 al;
salud inicial del motor 0.9/0.7/0.5; combinaciones independientes de mejoras de
velocidad/eficiencia. Cada perfil compara 0.1c, 0.3c y su máximo disponible.
Regenerar con:

```bash
PYTHONPATH=src:. /home/jon/prog/retorno_case/retorno_venv/bin/python \
  tests/test_engine_speed_upgrade.py --balance-matrix
```

La fixture existente (semilla 29) llama a los cálculos reales de combustible,
tiempo propio y desgaste de sistemas/casco. Supone CRUISE constante, Q=1, sin
brownout, radiación ambiental/interna, reparación, otros eventos ni agotamiento
de recursos. El casco parte de 1.0. Las columnas de desgaste son pérdida absoluta
de integridad, limitada a salud restante cero. Son estimaciones condicionadas de
desgaste ordinario, no una simulación completa de siglos ni garantía de supervivencia.
No se cambiaron coeficientes.

Ejemplo, 10 al con salud inicial del motor 0.9, módulo de velocidad, sin eficiencia:

| Velocidad | Cápsulas | Años galácticos | Años propios | Desgaste motor | Desgaste casco |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.1c | 0.45675 | 100 | 99.49874 | 0.266712 | 0.047067 |
| 0.3c | 1.00485 | 33.33333 | 31.79797 | 0.085236 | 0.015042 |
| 0.8c | 3.34950 | 12.5 | 7.5 | 0.020104 | 0.003548 |

A 10 al, max sin módulo de velocidad es 0.5c: 1.5225 cápsulas,
20 años galácticos y 17.32051 años propios. La eficiencia multiplica el combustible
por 0.8 a igual salud/velocidad, sin alterar tiempos ni desgaste condicionado.
Equipado y con salud 0.7 admite max 0.6c; con salud 0.5 admite max 0.4c.

Ninguna velocidad muestreada domina a la vez combustible y tiempo/desgaste. Los
extremos son costosos: 0.8c consume 7.33 veces las cápsulas de 0.1c a igual
integridad/distancia, mientras 0.1c acumula 13.27 veces su tiempo propio y desgaste
ordinario antes del límite de salud. A 20 al, partiendo de salud 0.5 con ambos
módulos, 0.1c deja engines OFFLINE en esta estimación; 0.3c lo deja CRITICAL,
mientras max 0.4c lo deja DAMAGED. Viajar lento puede ser una mala elección de
mantenimiento aunque ahorre cápsulas. Determinar si algún extremo es demasiado
ventajoso o impráctico queda pendiente de la disponibilidad procedural de cápsulas
y la economía de mantenimiento; no se reajustó nada para forzar el resultado.

## Textual con sonido

Desde este checkout, abre una partida de prueba separada:

```bash
cd /home/jon/prog/retorno_case/retorno
RETORNO_SCENARIO=fast_sandbox PYTHONPATH=src \
  /home/jon/prog/retorno_case/retorno_venv/bin/python -m retorno.ui_textual.app \
  --new-game --save-path /tmp/retorno-speed-demo.dat
```

En el terminal:

```text
config set audio on
config set ambientsound on
config show
man engine_speed
engines speed
engines speed 0.3
nav map routes
```

Usa `nav <id mostrado por nav map routes>` y confirma con y (EN) o s (ES).
`engines speed` mostrará la velocidad real congelada de 0.3c separada del objetivo,
techo y modo eléctrico CRUISE. `engines speed max` debe rechazar el cambio en
movimiento. Ejecuta `nav abort`, confirma y después `engines speed max`: se acepta
sin devolver cápsulas. Compara la siguiente estimación de `nav map routes`.
Valores superiores a 0.5c requieren el módulo existente de velocidad y salud
suficiente: 0.8c nominal, 0.6c LIMITED, 0.4c DAMAGED.

El audio usa backend, preferencias y enrutamiento de eventos existentes; sin
nuevos recursos de sonido ni vía paralela. Las pruebas de interfaz desactivan la
reproducción y pasaron los smokes de configuración de audio; no se comprobó la
salida física por altavoces.
