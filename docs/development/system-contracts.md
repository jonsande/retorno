# System contracts: index and cross-system invariants

Spanish counterpart: [system-contracts.es.md](system-contracts.es.md). This
index points to owning specifications; it does not replace them. **Implemented**
means current behavior, **approved** means binding design that may remain
unimplemented, and **proposal** needs a technical decision.

- **Implemented/required:** physical motion, galactic and proper clocks,
  electricity, radiation, wear, jobs and propulsion limits advance causally.
  A failed atomic tick leaves the prior committed state intact. Owners:
  [navigation physics](../systems/nav-physics.md),
  [boundaries](../systems/nav-boundaries.md),
  [electrical time](../systems/electrical-proper-time.md),
  [wear](../systems/wear-proper-time.md),
  [radiation](../systems/nav-radiation.md).
- **Implemented/required:** propulsion spends authorized fuel; interruption
  and recovery may neither obtain free fuel nor spend absent capsules. Arrival
  requires a real physical stop at the destination. Owners:
  [engines and antimatter](../systems/engines-antimatter.md) and
  [navigation physics](../systems/nav-physics.md).
- **Implemented/required:** operations affecting navigation, jobs and world
  preserve transaction order and current-version save/load fidelity. Migration
  of old saves is separate scope. Owners: [navigation physics](../systems/nav-physics.md)
  and [structural recovery](../systems/structural-recovery.md).
- **Approved knowledge boundary:** distinguish physical existence, acquired
  knowledge and operational routes; public output must be grounded in evidence.
  Owners: [navigation and intel](../systems/discovery-navigation-intel.md),
  [information capabilities](../systems/information-capabilities.md),
  [design contract](../design/navigation-recovery-contract.md) and
  [`C-DATA-004`](../canon/universo.md).

The [current status](current-status.md) lists open phases and playtest issues.
An issue or proposal there does not alter implemented contracts. Detailed
thresholds, equations, economics and persistence schemas stay with the owners
above; do not reproduce them wholesale in prompts or this index.
