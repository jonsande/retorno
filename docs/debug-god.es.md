# Modo dios de depuración

Implementado en `src/retorno/model/os.py`, `src/retorno/core/engine.py`,
`src/retorno/cli/parser.py`, `src/retorno/cli/repl.py` y
`src/retorno/ui_textual/app.py` y `src/retorno/io/save_load.py`. Regresión: `tests/debug_god_smoke.py`.

`debug god on` requiere modo debug. `debug god off` y `debug god status`
funcionan en ambos modos. CLI y Textual comparten manejador y mensajes EN/ES.
La ayuda, el uso del parser, el autocompletado y los manuales incluyen la sintaxis.

La protección solo actúa con `debug_enabled` y `debug_god_enabled` activados.
`OSState.set_debug` la borra al salir de debug o iniciar una nueva sesión debug.
Repetir `debug on` dentro de una sesión existente la conserva.
Los escenarios nuevos parten desactivados. El cargador compartido borra
explícitamente la bandera en partidas principales y de respaldo; guardar no
modifica la sesión activa. Los payloads antiguos parten desactivados. Las copias
en memoria conservan el estado del SO para mantener las invariantes de la
preparación de recuperación. No requiere migración del esquema de guardado.

## Puntos de mutación cubiertos

| Fuente | Responsable en el motor | Protección |
| --- | --- | --- |
| Desgaste del casco, radiación y multiplicadores de tránsito/hibernación | `_apply_hull_degradation` → `_damage_hull` | Bloquea pérdida de integridad |
| Desgaste de sistemas, radiación, mala alimentación, brownout sostenido, tránsito sin CRUISE | `_apply_degradation` | Bloquea pérdida de salud y transiciones por desgaste |
| Exposición de drones a radiación | `_apply_radiation` | Bloquea dosis nueva; conserva la previa |
| Desgaste de drones amplificado por dosis acumulada | `_update_drone_maintenance` | Bloquea pérdida de integridad |
| Consumo de batería en espera desplegada | `_update_drone_maintenance` → `_drain_drone_battery` | Bloquea consumo |
| Despliegue, movimiento, reinicio/recogida, variantes de recuperación, operadores de reparación/selftest (incluidos intentos fallidos), instalación/retirada de módulos de nave | Efectos de trabajos / `_drain_repair_operator_battery` → `_drain_drone_battery` | Bloquea consumo |
| Riesgo de operación en bahía dañada/crítica | `_apply_drone_bay_damaged_integrity_risk` | Bloquea daño y su evento |
| Fallo de reparación pasiva en bahía | `_update_drone_maintenance` | Bloquea daño; conserva fallo y coste de chatarra |
| Fallo de trabajo de emergencia | `_maybe_fail_emergency_job` | Bloquea daño e inutilización del dron; conserva fallo del trabajo |

La batería es el mecanismo de autonomía operativa implementado. También se
cubren desgaste de integridad y dosis de radiación. Las alertas de batería baja,
reglas de recogida automática y mínimos operativos siguen normales: no se
restaura el agotamiento previo. Retirar módulos sigue limitando integridad y
batería a la nueva capacidad efectiva; es configuración, no daño ni agotamiento
operativo.

## Límites

Activarlo no repara salud/integridad, revive drones, rellena baterías, elimina
dosis previa, habilita sistemas averiados ni crea recursos. La reparación
ordinaria pagada en bahía, la carga, descontaminación y los trabajos de reparación
solicitados siguen sus reglas existentes. Generación eléctrica, consumo
energético de nave, desconexión por carga, dependencias de sistemas,
probabilidades de fallo de trabajos y costes de recursos siguen normales.
Las tiradas de riesgo se realizan aunque se bloquee su daño.

La radiación ambiental, los cálculos de penetración interna y sus lecturas siguen
normales. El modo dios nunca escribe worldgen, historia, B1/B2, contactos, rutas
conocidas, lore, propagación de radio ni planificación narrativa. Los descubrimientos
normales al avanzar el tiempo siguen siendo posibles. `debug on` sigue deteniendo
el tiempo automático y `wait N` avanza N segundos con los pasos existentes de un
segundo. No cambian las llegadas de viajes, duraciones ni reglas de progreso de trabajos.

## Validación focalizada

Ejecutar con el intérprete del entorno virtual canónico del repositorio:

- `tests/debug_god_smoke.py`: parser y sintaxis inválida, requisitos, ayuda y
  salida EN/ES, despacho real CLI/Textual, todas las categorías protegidas,
  fallos de riesgo forzados, daños previos, drones inutilizados, off/reentrada,
  unpickle y guardado/carga real, snapshot invariable al activar, wait manual y
  comparación breve de progreso de viaje/trabajo/mundo.
- `tests/radiation_hull_smoke.py`: comportamiento normal previo de casco/radiación.
- `tests/textual_completion_context_smoke.py`: límites previos del autocompletado.

Sin refactorización general de daños, cambios del scheduler ni exploraciones largas.

### Resultados de 4D-3e5c-GOD-1

- `debug_god_smoke.py`: PASS, incluida carga principal/respaldo y despacho real CLI/Textual.
- `textual_completion_context_smoke.py`: PASS.
- Compilación Python focalizada, paridad de sintaxis EN/ES, validación de rutas
  documentales y `git diff --check`: PASS.
- `radiation_hull_smoke.py`: fallo previo en línea 183 (espera alerta ambiental
  de radiación, lista de eventos vacía). Reproducido sin cambios en una exportación
  temporal limpia de `HEAD`; esta tarea no lo causa ni lo corrige. La prueba nueva
  comprueba de forma independiente el desgaste protegido y normal de
  casco/sistemas/drones por radiación.

Detenido para revisión externa; sin staging, commit ni push.
