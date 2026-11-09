# Preventive autorecall — validation

The project interpreter ran focused checks first, then the default pytest
collection and all 84 executable smoke/integration/unit scripts. The comparison
baseline is the previous engines integration, documented in
[its evidence](engines-antimatter-results.json). Results are retained
[per script](drone-autorecall-results.json).

| Check | Result |
| --- | --- |
| New reserve integration | 17 groups PASS |
| Default pytest | 17 PASS, 14 subtests PASS |
| Executable script suite | 66/84 PASS, 18 FAIL |
| Previous integration baseline | 65/83 PASS, the same 18 FAIL |
| Manuals style, EN/ES pairs and task whitespace | PASS |

The unchanged failures were already reproduced on clean canonical HEAD during
the engines integration. No new failing script was detected. This is not a
claim that the repository-wide suite is green; the full failing list is in the
machine-readable evidence. Energy policy, prologue chain/policy, save/load,
modules, recall-all, public IDs, knowledge boundaries, Textual, clocks and time
advancement pass. The new suite was rerun after the final per-drone configuration
filter; it passed all 17 groups.

The new integration tests exercise the reported 12% -> repair -> 4% case without
spending battery/time or losing scrap; one queued return; exactly one task debit
on success and failure; OFF and god-mode behavior; cumulative queue budgets and
refunds; return priority after safe running work; revalidation after battery,
threshold or capacity changes; long waits and low configured thresholds; explicit
non-spamming battery/integrity/docking blocks; read-only EN/ES status and shared
presentation; save/load of queued return and block state; compound move/repair;
and real Textual keyboard commands in both languages with paused debug.

The patch does not edit the current running game or grant energy to D1. An
already depleted drone remains subject to ordinary recall requirements. Start
the updated application to use the new logic; existing current-format engines
saves retain their batteries and jobs. No commit or push was made, and the
pre-existing TODO.md edit was preserved.

Behavior, formulas and public commands: [implementation](../systems/drone-autorecall.md).
