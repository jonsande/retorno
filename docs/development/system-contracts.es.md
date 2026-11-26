# Contratos de sistemas: índice e invariantes transversales

Versión inglesa: [system-contracts.md](system-contracts.md). Este índice remite
a las especificaciones propietarias, sin sustituirlas. **Implementado** es el
comportamiento actual; **aprobado** vincula el diseño aunque falte código;
**propuesta** necesita una decisión técnica.

- **Implementado/exigido:** movimiento físico, relojes galáctico y propio,
  electricidad, radiación, desgaste, trabajos y límites de propulsión avanzan
  causalmente. Un tick atómico fallido conserva el estado consolidado.
  Propietarios: [física de navegación](../systems/nav-physics.es.md),
  [fronteras](../systems/nav-boundaries.es.md),
  [tiempo eléctrico](../systems/electrical-proper-time.es.md),
  [desgaste](../systems/wear-proper-time.es.md),
  [radiación](../systems/nav-radiation.es.md).
- **Implementado/exigido:** la propulsión gasta combustible autorizado;
  interrupción y recuperación no obtienen combustible gratis ni gastan
  cápsulas inexistentes. Llegar requiere detención física real en destino.
  Propietarios: [motores y antimateria](../systems/engines-antimatter.es.md) y
  [física de navegación](../systems/nav-physics.es.md).
- **Implementado/exigido:** operaciones sobre navegación, trabajos y mundo
  conservan orden transaccional y guardado/carga fiel de la versión actual.
  Migrar partidas antiguas es alcance separado. Propietarios:
  [física de navegación](../systems/nav-physics.es.md) y
  [recuperación estructural](../systems/structural-recovery.es.md).
- **Límite de conocimiento aprobado:** distinguir existencia física,
  conocimiento adquirido y rutas operativas; fundamentar la salida pública en
  evidencias. Propietarios:
  [navegación e intel](../systems/discovery-navigation-intel.es.md),
  [capacidades de información](../systems/information-capabilities.es.md),
  [contrato de diseño](../design/navigation-recovery-contract.es.md) y
  [`C-DATA-004`](../canon/universo.md).

El [estado actual](current-status.es.md) enumera fases e incidencias abiertas.
Una propuesta allí no altera los contratos implementados. Umbrales, ecuaciones,
economía y esquemas de persistencia detallados pertenecen a los documentos
propietarios; no copiarlos íntegros a prompts ni a este índice.
