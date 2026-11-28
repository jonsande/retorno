# Current development status and pending work

Spanish counterpart: [current-status.es.md](current-status.es.md). DOC-DEV-01
snapshot. The historical [`TODO.md`](../../TODO.md) remains unchanged and is
not a current implementation specification. Technical owners are indexed in
[system-contracts.md](system-contracts.md).

## Implemented and observed

- **Implemented and approved:** NAV-BRAKE R2 and R2-F. As an earlier milestone,
  the R2-V general suite passed 642 tests and 169 subtests. After R2-F, the user
  personally ran one definitive general suite on Ubuntu with the exact result
  `646 passed, 169 subtests passed in 358.01s (0:05:58)`. R2-F also passed four
  new targeted tests and 65 related regressions during its intervention. See the
  [R2 review](../testing/nav-playtest-r2-review.md) and
  [navigation physics](../systems/nav-physics.md).
- **Real playtest observation reported by the developer:** the later journeys
  to HARBOR_12 and P-4.2.2.0 finished without technical errors. This does not
  close every transit issue.
- **Measured on private save copies after R2-F:** PT001-04 and PT001-05
  hibernation processing took 12.00 s and 13.81 s, with arrival and unchanged
  fuel. R2-E had measured 3.44 s and 7.12 s. R2-F restricted extended blocks
  to stable nominal coast; no further optimization was attempted. See the
  [R2-F measurement record](../../MEDICIONES-R2-F.json).
- **Implemented in PT001-07B and corrected in 07B-F:** variable-load drone
  charging, reserve above 25% SoC, and causal cuts after effective regulation.
  The 07A proposal, previously held only in a
  conversation, is now recorded in the
  [charging specification](../systems/drone-charging.md). See the
  [targeted verification](../testing/pt001-07b-review.md).
- **PT001-07 approved after definitive general validation reported by the developer:**
  `677 passed, 169 subtests passed in 362.72s`. This is the completed
  PT001-07 validation result, not a suite run in PT001-08.
- **PT001-01/09-B definitively validated as reported by the developer:**
  `727 passed, 169 subtests passed in 461.08s`. TEMP-01A did not rerun that
  suite. The [scheduler diagnosis](../testing/pt001-01-09-diagnosis.md)
  retains its focused measurements and remaining real-terminal limitation.
- **Implemented and reviewed in PT001-08, 08-F, and 08-F2:** normal hibernation hides simulation progress,
  clocks, and intermediate panels until wake; debug mode retains real progress
  through the existing mechanism. Technical blocks return to the interface
  with automatic time paused and actual progress shown, without wake narration.
  The recorded end event also presents a technical stop when consulted later. See the
  [presentation record](../testing/pt001-08-review.md).
- **Implemented in PT001-10:** CLI and Textual now explain specific departure
  blockers through the same pure public diagnosis; route rows use it too.
  Hidden destinations remain indistinguishable from absent ones. See the
  [focused validation](../testing/pt001-10-review.md).

## Open playtest issues and design directions

| ID | Status | Issue or approved outcome; technical work remaining |
| --- | --- | --- |
| PT001-01/09 | B implemented; definitive general validation complete | Automatic time retains active-time debt after missed deadlines and recovers it in bounded, yielding steps. Pauses, manual advance, hibernation, errors and close discard debt; permitted restarts begin fresh epochs. 727 tests and 169 subtests passed. Sustained overload and real-terminal perception remain open; see the [diagnosis](../testing/pt001-01-09-diagnosis.md). |
| PT001-06 | 06A: safe load; causal transition pending | The real save loads in CLI and Textual; time advance pauses with a visible explanation when `core_os` is already offline during physical transit. Public commands cannot turn off `core_os` or `life_support` during physical transit. Offline terminal restrictions remain: the affected save cannot resume travel without a future causal survival transition, outside 06A. |
| PT001-07 | Approved; definitive general validation complete | Variable charging load and reserve with a 25% SoC threshold, energy accounting, and causal cuts after effective electrical regulation. 677 tests and 169 subtests passed. |
| TEMP-01 | 01A audit complete; 01B blocked before implementation | The [temporal audit and 24-type job matrix](../systems/temporal-bases-audit.md) identify an ordinary-integrator blocker: jobs resolve once at interval end, so P/G ETA conversion alone cannot guarantee causal completion or short/long equivalence. Ordinary slicing and transactional effect order require a separate scoped design. All productive jobs remain G; 01C/D/E/F have not started. |
| PT001-08 | 08-F2 implemented; focused validation complete | Normal Textual hibernation stays dark during processing; CLI remains silent after its cleared screen. Existing debug mode shows real progress. Ordinary and legitimate emergency wakes retain their sequence. Exceptions and returned causal blocks pause automatic time, show actual progress, and omit wake narration; the recorded end event reports a technical stop on later consultation. CLI can still save on exit. |
| PT001-10 | Implemented; focused validation complete | Specific EN/ES departure diagnostics cover engine power/health, target speed, transit/docking, route knowledge/range, fuel and electrical/core OS restrictions. CLI, Textual and route rows share the read-only result. Admission and debit remain in Engine. |
| QA-01 | Future audit pending | Audit regression scripts excluded from automatic pytest collection, assess their current contracts and decide explicitly which should be collected or run separately. No QA-01 implementation in PT001-01/09-A. |
| PT001-11 | Approved design; implementation pending | `ACTIVE` during acceleration and braking; `STANDBY` during cruise with early reactivation; automatic `OFFLINE` after the ship actually stops at its destination. Separate operational state, system health, and disconnection cause. Reactivation for a new departure, power use, wear, and startup times need definition in NAV-BRAKE-01C. |

These rows distinguish observed defects from approved future behavior. None
claims PT001-11 is implemented; PT001-06 only has the 06A
load and prevention safeguards. Causal, economic,
transactional and knowledge contracts remain in force.

## Pending milestones

- **D2B2:** pending; define and authorize its exact scope separately.
- **NAV-BRAKE-01C:** pending; define and authorize its exact scope separately.
- **NAV-BRAKE-02:** pending; define and authorize its exact scope separately.

Handle open issues in small, reviewable interventions. Preserve original
saves and unrelated edits; use the [work rules](working-rules.md).
