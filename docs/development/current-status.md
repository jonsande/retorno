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

## Open playtest issues and design directions

| ID | Status | Issue or approved outcome; technical work remaining |
| --- | --- | --- |
| PT001-01/09 | Open observations | Residual lag and clock regularity during physical transit. Measure on the current real profile before choosing a remedy; completed journeys do not close this issue. |
| PT001-06 | Open defect | Crash and inaccessible save when `core_os` is turned off during physical transit. Reproduce safely on a copy and define recovery without damaging the original. |
| PT001-07 | Approved outcome; implementation pending | Allow drone charging with negative net power when SoC is sufficient and other operational conditions hold; debit actual energy. Threshold and causal accounting need a focused design. |
| PT001-08 | Approved presentation direction; implementation pending | Show internal hibernation simulation progress only in debug mode. Keep ordinary presentation diegetic. Specify the debug surface. |
| PT001-10 | Approved presentation direction; implementation pending | Give specific reasons why a journey cannot start, including engines being off. Localize EN/ES and avoid internal leaks; specify message mapping. |
| PT001-11 | Approved direction; technical definition pending | Give engines an operational standby state during cruise and reactivate them early enough for braking. Define power, timing, failure and persistence rules first. |

These rows distinguish observed defects from approved future behavior. None
claims PT001-06 through PT001-11 is implemented. Causal, economic,
transactional and knowledge contracts remain in force.

## Pending milestones

- **D2B2:** pending; define and authorize its exact scope separately.
- **NAV-BRAKE-01C:** pending; define and authorize its exact scope separately.
- **NAV-BRAKE-02:** pending; define and authorize its exact scope separately.

Handle open issues in small, reviewable interventions. Preserve original
saves and unrelated edits; use the [work rules](working-rules.md).
