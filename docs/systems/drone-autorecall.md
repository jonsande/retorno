# Preventive drone autorecall

Implemented in `src/retorno/core/engine.py`; public CLI and Textual paths share
the same job admission, scheduler, battery costs and recall actions.

With autorecall enabled, an operating drone must preserve return energy before
accepting work. `_drone_job_battery_cost` owns the existing lump-sum debits for
deploy, move, repair, ship-module installation/removal, survey and salvage;
actual completion and repair failure use the same amounts. This change does
not add a recall debit or change normal task costs, repair failure probability,
recall success probability or recovery-reboot requirements.

The absolute reserve is the larger of:

- configured threshold times current effective battery capacity;
- existing recall minimum times effective capacity, plus idle consumption for
  the current recall ETA and one second of scheduling margin.

The required budget adds all pending work for that drone: remaining duration
at the existing deployed idle rate and each outstanding task debit. Current
module capacity and movement/bay ETA modifiers are included. Reservations are
computed from live state; they are not spent or stored as a second battery.
God mode bypasses the reserve because it bypasses the corresponding consumption.
Non-consuming work in the bay and recovery reboot keep their existing rules.

A 12% base-capacity drone cannot accept an 8% repair lasting 45 s with the
ordinary 10% autorecall threshold: it needs 18.09% including 0.09% idle draw.
The repair is rejected before time advances or battery is spent; any scrap
reserved by the command is returned, and an early return is requested.

The scheduler revalidates the budget at task start and while running, including
after loading a pending job, threshold changes or equipment changes. Unsafe
unfinished work is cancelled without its completion debit; existing repair
scrap reservations are refunded exactly once. Queued work for that drone is
cancelled before automatic return. Safe running work finishes first; return is
prioritized over additional work, with no duplicate pending recall job. Other
drones' queues are unaffected. Existing terminal job IDs and outcomes are used.

`Engine.tick` preserves ordinary ticks when the projected reserve is safe.
When necessary, it stops at a drone's relevant task completion or idle reserve
boundary so a large wait cannot skip the recall window. Movement still takes
its normal duration. CLI and Textual `debug on` pause automatic time: admission
and configuration decisions remain immediate, while `wait` advances the return.
The power telemetry cache issue under paused debug is outside this change.

Unmet battery, integrity or external-docking requirements now produce localized
messages and are retained in `DroneState.autorecall_block_reason`, visible via
`drone status [D1]`. Repeated identical blocks do not flood the log. Diagnostics
remain read-only and expose no unknown installation IDs. A drone already at 4%
receives no free energy; the ordinary 5% recall minimum still blocks it.
Autorecall OFF permits deliberate risk within existing operation gates.

Public commands remain `drone autorecall D1 on|off|<percent>`, `drone status D1`,
`drone repair D1 <system_id>`, `drone recall D1`, `jobs`, and `wait <seconds>` in
DEBUG. Help and diegetic drone/repair manuals are maintained in EN/ES.

`tests/drone_autorecall_reserve_smoke.py` covers immediate refusal/refund,
completion/failure debits, queue budgets and priority, start revalidation,
capacity/threshold changes, large waits, low thresholds, current depleted drones,
localized diagnostics, save/load, compound move/repair and real Textual input
in both languages with paused debug. See the [validation report](../testing/drone-autorecall-review.md).
