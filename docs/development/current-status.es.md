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
- **Implementado en PT001-07B y corregido en 07B-F:** recarga de drones con
  carga variable, reserva por encima del 25 % y cortes causales tras la
  regulación efectiva. La propuesta 07A, antes conservada
  solo en una conversación, está registrada en la
  [especificación de recarga](../systems/drone-charging.es.md). Véase la
  [validación dirigida](../testing/pt001-07b-review.es.md).
- **PT001-07 aprobado tras la validación general definitiva comunicada por el desarrollador:**
  `677 passed, 169 subtests passed in 362.72s`. Es el resultado completado
  de PT001-07, no una ejecución de la suite en PT001-08.
- **Implementado y revisado en PT001-08, 08-F y 08-F2:** la hibernación normal oculta el progreso de
  simulación, relojes y paneles intermedios hasta el despertar; debug conserva
  el progreso real mediante el mecanismo existente. Los bloqueos técnicos
  restauran la interfaz, pausan el tiempo automático y muestran el avance real
  sin narración de despertar. El evento final registrado también presenta una
  detención técnica al consultarlo después. Véase el
  [registro de presentación](../testing/pt001-08-review.es.md).
- **Implementado en PT001-10:** CLI y Textual explican impedimentos concretos
  de partida mediante el mismo diagnóstico público y puro; las filas de rutas
  también lo utilizan. Los destinos ocultos siguen siendo indistinguibles de
  los inexistentes. Véase la
  [validación dirigida](../testing/pt001-10-review.es.md).

## Incidencias abiertas y direcciones de diseño

| ID | Estado | Incidencia o resultado aprobado; trabajo técnico pendiente |
| --- | --- | --- |
| PT001-01/09 | Observaciones abiertas | Lag residual y regularidad de relojes durante tránsito físico. Medir en el perfil real actual antes de elegir solución; los viajes completados no cierran esta incidencia. |
| PT001-06 | 06A: carga protegida; transición causal pendiente | La partida real carga en CLI y Textual; el avance se pausa y se informa cuando `core_os` ya está apagado durante tránsito físico. Se impide apagar `core_os` o `life_support` mediante comandos públicos mientras hay tránsito físico. El terminal apagado conserva sus restricciones: la partida afectada no puede reanudar el viaje sin una futura transición causal de supervivencia, fuera de 06A. |
| PT001-07 | Aprobado; validación general definitiva completada | Recarga variable y reserva con umbral del 25 %, contabilidad energética y cortes causales tras la regulación eléctrica efectiva. Superadas 677 pruebas y 169 subpruebas. |
| TEMP-01 | Invariante aprobado; auditoría pendiente | Auditar y corregir progresivamente las bases temporales de todos los subsistemas. La física interna de la nave usa tiempo propio; los procesos externos, el físicamente correspondiente; el tiempo biológico deriva del propio y del estado fisiológico. 07B-F no implementa TEMP-01. |
| PT001-08 | 08-F2 implementado; validación dirigida completada | La hibernación normal de Textual permanece oscura durante el procesamiento; CLI guarda silencio tras limpiar la pantalla. El debug existente muestra progreso real. Los despertares ordinarios y las emergencias legítimas conservan su secuencia. Las excepciones y los bloqueos causales devueltos pausan el tiempo automático, muestran el avance real y omiten la narración de despertar; el evento final registrado comunica una detención técnica al consultarlo después. CLI puede guardar al salir. |
| PT001-10 | Implementado; validación dirigida completada | Diagnósticos específicos EN/ES para alimentación y salud de motores, velocidad objetivo, tránsito/acoplamiento, rutas conocidas/alcance, combustible y restricciones eléctricas o del sistema operativo. CLI, Textual y filas de rutas comparten el resultado de solo lectura. La admisión y el cobro siguen en Engine. |
| PT001-11 | Diseño aprobado; implementación pendiente | `ACTIVE` durante aceleración y frenado; `STANDBY` durante crucero con reactivación anticipada; `OFFLINE` automático tras detenerse efectivamente en destino. Separar estado operativo, salud del sistema y causa de desconexión. La reactivación para una nueva partida, los consumos, el desgaste y los tiempos de arranque requieren concreción en NAV-BRAKE-01C. |

La tabla distingue defectos observados de comportamiento futuro aprobado. No
afirma que PT001-11 esté implementada; PT001-06 solo tiene la
protección de carga y prevención de 06A. Siguen vigentes los
contratos causales, económicos, transaccionales y de conocimiento.

## Hitos pendientes

- **D2B2:** pendiente; definir y autorizar alcance exacto por separado.
- **NAV-BRAKE-01C:** pendiente; definir y autorizar alcance exacto por separado.
- **NAV-BRAKE-02:** pendiente; definir y autorizar alcance exacto por separado.

Tratar incidencias en intervenciones pequeñas y revisables. Preservar partidas
originales y cambios ajenos; aplicar las [reglas de trabajo](working-rules.es.md).
