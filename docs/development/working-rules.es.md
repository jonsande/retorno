# Reglas permanentes de trabajo para agentes de Retorno

Versión inglesa: [working-rules.md](working-rules.md). Desarrolla
[AGENTS.md](../../AGENTS.md). Las incidencias actuales pertenecen a
[current-status.es.md](current-status.es.md).

## Alcance y repositorio

- Trabajar en intervenciones pequeñas y delimitadas. Definir comportamiento,
  superficies afectadas, criterios de aceptación y exclusiones antes de ampliar
  una tarea.
- Revisar primero el árbol. Preservar cambios ajenos, archivos sin rastrear,
  perfiles del jugador y partidas originales de evidencia. Usar copias privadas.
- No hacer commit, push ni merge sin autorización. No restablecer trabajo ajeno.
  Si el problema excede el alcance, detenerse e informar evidencia e impacto.
- Reutilizar infraestructura, unificar lógica duplicada y evitar
  infraestructuras paralelas. Solicitar autorización antes de implementar
  cambios con riesgos arquitectónicos significativos. Para
  Python usar `/home/jon/prog/retorno_case/retorno_venv/bin/python` en este
  checkout; nunca el intérprete del sistema ni `pytest` sin entorno.

## Evidencia y reanudación

- Ejecutar pruebas dirigidas durante el desarrollo; reservar la suite general
  para hitos de integración significativos o requisitos expresos.
- Registrar comandos exactos, resultados, fallos, mediciones y estado del
  código en notas intermedias reutilizables. No dar por superada una prueba
  interrumpida.
- Reutilizar validaciones completas mientras el código cubierto no cambie.
  Repetir solo ante riesgo concreto o requisito. Conservar referencias para
  comparar rendimiento.
- Verificar rutas afectadas y enlaces. Todo documento nuevo o modificado debe
  tener versión EN/ES con paridad semántica, que se verificará al entregar.

## Juego y presentación

- Preservar continuidad física y causal, recursos finitos y recibos de
  combustible, orden determinista, rollback atómico y guardado/carga de la
  **versión actual**. Migrar partidas antiguas requiere alcance expreso.
- Actualizar el documento técnico propietario ante cambios observables;
  revisar también manuales, ayuda, pruebas e idiomas. Distinguir implementación,
  diseño aprobado y propuesta técnica. Índice: [system-contracts.es.md](system-contracts.es.md).
- Todo texto visible al jugador y manual diegético requiere EN/ES mediante la
  localización existente. Mantener identificadores; los comentarios no
  requieren traducción artificial. Seguir la
  [guía de manuales](../manuals_style_guide.md).
- Aplicar [`C-DATA-004`](../canon/universo.md) y la
  [guía de coherencia](../canon/guia_coherencia.md): separar verdad física,
  conocimiento de la nave y scheduler. Nodos ocultos, lore y ledgers de
  recuperación no son conocimiento del jugador. Revisar CLI, Textual, eventos,
  sonidos, autocompletado y errores; probar no divulgación y retención de
  información adquirida. Cuando corresponda, mantener constantes las
  observaciones del jugador, variar los datos internos ocultos y comprobar
  que la salida pública no cambia.
- Reservar diagnósticos omniscientes a comandos `debug_enabled`. `status` y
  `diag` siguen siendo públicos incluso en debug. Consultar no debe mutar,
  consumir RNG, generar lugares ni importar intel. La interfaz normal usa
  términos diegéticos sobre el estado de la nave; progreso interno y detalles
  de implementación quedan en debug. Controles y guardado/carga no necesitan
  ficción forzada.
