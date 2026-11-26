# Estado actual del desarrollo y trabajo pendiente

Versión inglesa: [current-status.md](current-status.md). Estado DOC-DEV-01. El
histórico [`TODO.md`](../../TODO.md) permanece intacto y no es por sí solo una
especificación vigente. Los documentos técnicos propietarios están en
[system-contracts.es.md](system-contracts.es.md).

## Implementado y observado

- **Implementado y aprobado:** NAV-BRAKE R2 y R2-F. Como antecedente, la suite
  general de R2-V superó 642 pruebas y 169 subpruebas. Tras R2-F, el usuario
  ejecutó personalmente desde Ubuntu una única suite general definitiva con
  resultado exacto `646 passed, 169 subtests passed in 358.01s (0:05:58)`.
  R2-F también superó cuatro pruebas dirigidas nuevas y 65 regresiones
  relacionadas durante su intervención. Véanse el
  [informe R2](../testing/nav-playtest-r2-review.es.md) y la
  [física de navegación](../systems/nav-physics.es.md).
- **Observación del playtest real comunicada por el desarrollador:** los viajes
  posteriores a HARBOR_12 y P-4.2.2.0 terminaron sin errores técnicos. Esto
  no cierra todos los problemas de tránsito.
- **Medido en copias privadas tras R2-F:** la hibernación de PT001-04 y
  PT001-05 tardó 12,00 s y 13,81 s de procesamiento, con llegada y combustible
  inalterado. R2-E había medido 3,44 s y 7,12 s. R2-F restringió los bloques
  largos al crucero nominal estable; no se intentó otra optimización. Véase el
  [registro de mediciones R2-F](../../MEDICIONES-R2-F.json).

## Incidencias abiertas y direcciones de diseño

| ID | Estado | Incidencia o resultado aprobado; trabajo técnico pendiente |
| --- | --- | --- |
| PT001-01/09 | Observaciones abiertas | Lag residual y regularidad de relojes durante tránsito físico. Medir en el perfil real actual antes de elegir solución; los viajes completados no cierran esta incidencia. |
| PT001-06 | 06A: carga protegida; transición causal pendiente | La partida real carga en CLI y Textual; el avance se pausa y se informa cuando `core_os` ya está apagado durante tránsito físico. Se impide apagar `core_os` o `life_support` mediante comandos públicos mientras hay tránsito físico. El terminal apagado conserva sus restricciones: la partida afectada no puede reanudar el viaje sin una futura transición causal de supervivencia, fuera de 06A. |
| PT001-07 | Resultado aprobado; implementación pendiente | Permitir recargar drones con net eléctrico negativo si hay SoC suficiente y se cumplen las demás condiciones operativas; contabilizar energía real. Umbral y contabilidad causal requieren diseño acotado. |
| PT001-08 | Dirección de presentación aprobada; implementación pendiente | Mostrar progreso interno de simulación de hibernación solo en debug. La interfaz normal sigue siendo diegética. Concretar la superficie de debug. |
| PT001-10 | Dirección de presentación aprobada; implementación pendiente | Explicar motivos específicos que impiden iniciar viaje, incluido engines apagado. Localizar EN/ES sin divulgar estado interno; concretar mensajes. |
| PT001-11 | Diseño aprobado; implementación pendiente | `ACTIVE` durante aceleración y frenado; `STANDBY` durante crucero con reactivación anticipada; `OFFLINE` automático tras detenerse efectivamente en destino. Separar estado operativo, salud del sistema y causa de desconexión. La reactivación para una nueva partida, los consumos, el desgaste y los tiempos de arranque requieren concreción en NAV-BRAKE-01C. |

La tabla distingue defectos observados de comportamiento futuro aprobado. No
afirma que PT001-07 a PT001-11 estén implementadas; PT001-06 solo tiene la
protección de carga y prevención de 06A. Siguen vigentes los
contratos causales, económicos, transaccionales y de conocimiento.

## Hitos pendientes

- **D2B2:** pendiente; definir y autorizar alcance exacto por separado.
- **NAV-BRAKE-01C:** pendiente; definir y autorizar alcance exacto por separado.
- **NAV-BRAKE-02:** pendiente; definir y autorizar alcance exacto por separado.

Tratar incidencias en intervenciones pequeñas y revisables. Preservar partidas
originales y cambios ajenos; aplicar las [reglas de trabajo](working-rules.es.md).
