# RETORNO — 4D-3e5c-P4

[English](prologue-completion-review.md). Base:
`f459786a3e4e4be7049663326a07bd98741aa388`, árbol inicialmente limpio.

## Cambio

Dos líneas en el tratamiento existente de llegada de `Engine.tick()` activan
`MetaState.prologue_complete` si el destino del tránsito y el nodo físico
alcanzado son HARBOR_12 y el indicador sigue pendiente. Se ejecuta dentro de
la rama de llegada efectiva a un nodo no transitorio, sin exigir atraque.
No se añaden eventos, escenas, contadores ni otro sistema de progresión.

Se conserva el valor inicial `False` del modelo y no existe reinicio al salir.
La persistencia existente serializa el booleano como parte de `MetaState`:
no cambia el esquema ni se añade una migración. CLI, Textual e hibernación
comparten el mismo motor. No se modifican navegación, P3, generación, B1/B2,
exploración, supervivencia o lore.

## Archivos modificados

- `src/retorno/core/engine.py`: activación idempotente en la llegada.
- `tests/prologue_chain_smoke.py`: amplía el recorrido público existente,
  sin ejecutar el resto de su batería.
- `docs/systems/discovery-navigation-intel.es.md` y `.md`: contrato EN/ES
  de finalización del prólogo.
- `docs/testing/prologue-completion-review.es.md` y `.md`: este informe.

No cambian help ni manuales diegéticos: no hay comandos o mensajes nuevos.

## Pruebas ejecutadas

Intérprete: `/home/jon/prog/retorno_case/retorno_venv/bin/python`.
Con `PYTHONPATH=src:tests PYTHONDONTWRITEBYTECODE=1`, se ejecutó únicamente
`prologue_chain_smoke.public_chain()` y se guardó su diario JSON.

Resultado: **PASS** en todos los casos requeridos:

1. Partida nueva y FAST_SANDBOX comienzan con `False`.
2. Leer el contacto de ECHO_7, consultar el grafo de debug en una copia aislada
   y recuperar/importar la ruta no completan el prólogo.
3. Iniciar el viaje y avanzar hasta su mitad mantienen `False`.
4. Llegada normal y mediante hibernación establecen `True` sin atraque.
5. Se mantiene tras salir, llegar de nuevo a P y guardar/cargar. También se
   comprueba persistencia antes de completar, en HARBOR_12 y durante la salida.
6. Tres ticks posteriores no repiten la llegada ni desactivan el indicador.
7. El recorrido principal utiliza la cadena pública P3 de semilla 1, sin debug,
   teleportación ni edición de recursos/conocimiento. Para el control de llegada
   normal se reutiliza una copia del tránsito legítimo con dos ticks grandes;
   no se ejecuta otra simulación prolongada de supervivencia.

Comprobaciones estáticas: sintaxis AST de los Python modificados, enlaces del
informe y `git diff --check`, **PASS**. No se ejecutaron barridos ni batería general.

ZIP incremental: solo los seis archivos anteriores y `AUDIT/` con base,
comando, log, evidencia e inventario SHA-256/tamaños. El inventario no se incluye
a sí mismo. Sin `git add`, commit ni push. Detenido para revisión externa.
