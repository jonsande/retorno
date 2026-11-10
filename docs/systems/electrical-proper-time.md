# T-04B1 — ordinary electricity in ship proper time

Implemented on 2026-11-10 after T-04A. The owning code is
`src/retorno/core/engine.py`; `core/temporal.py` remains the sole relativistic
interval calculation. This change keeps all configured powers, capacities,
efficiencies, thresholds and automatic shedding rules.

`power_core` generation and active system/job electrical demand are onboard kW.
The ship battery stores kWh. `Engine._integrate_power_interval(state, dt_ship)`
uses onboard seconds for battery charge/discharge, `low_q_shed_timer_s`, and
`brownout_sustained_s`. Existing charge/discharge rate limits, efficiencies,
capacity clamps, power quality and instantaneous shedding remain in force.
Generation and load are instantaneous kW, with no velocity multiplier on the
power itself. Only the integration interval changes. At rest it is identical
to galactic elapsed seconds, including when the power profile is CRUISE.

`Engine._tick_interval` reuses the intervals already calculated for the ship
clock. Interstellar movement uses T-04A's frozen `transit_speed_ly_per_year`,
including after engine damage, repair or configuration changes. Local movement
uses the existing 20 km/s speed. Hibernation does not scale electrical energy
by the separate biological ageing rate.

An electrical segment still samples generation, computes load and shedding,
updates the low-quality timer, integrates battery energy, and updates quality
and brownout persistence in the existing order. Without arrival this remains
at the same point in the outer tick, after jobs and the lore scheduler. The
initial generation sample is retained as before; this task does not reschedule
jobs or reconstruct their completion times inside an interval.

When a tick reaches or crosses arrival, electricity has two segments:

1. Integrate the moving proper-time interval with the in-flight electrical
   state, before arrival hooks and job completion can replace that state.
2. Process the existing arrival, jobs and lore/recovery calls once, in their
   existing galactic order. Refresh generation for the resulting state and
   integrate the stationary remainder, where proper and galactic seconds agree.

At exact arrival the second segment has zero duration. It refreshes final
telemetry/regulation without charging or discharging energy for that segment.
A change to generation or load at arrival cannot price the preceding transit.
The electrical integrator does not invoke a narrative scheduler, advance clocks,
process jobs, change location, apply wear or maintain drones. There is no
per-second simulation loop. Existing drone decision boundaries in `Engine.tick`
remain intact; T-04B2 also reuses these segments for ordinary system/hull wear.
Electrical events retain the existing enclosing tick's galactic timestamp.

`clock.t`, `last_dt`, navigation ETA, historical events, narrative and radio
remain galactic. T-04B2 converts [ordinary system/hull wear](wear-proper-time.md)
to proper time without changing this electrical policy. Jobs, repairs, radiation,
drone consumption/charging/maintenance and life-support/hibernation rules still
receive their existing galactic interval once. Antimatter departure charging and abort rules
are unchanged. New saves persist the existing power values and timers without
new fields, migrations or changes to the save format.

Existing dependencies and limits are explicit:

- Sustained brownout and power quality still feed the existing wear model.
  The persistence threshold is measured onboard. T-04B2 now also measures the
  wear interval onboard, preserving its existing quality/brownout multipliers.
  These sampled conditions can activate consequences at different galactic times.
- Jobs and drone support already read electrical availability. Changed energy
  may change their admission/support, but their durations, drain and maintenance
  rates are not converted. No additional electrical cost for drones is added.
- Continuous reconstruction of battery-empty/full instants, intermediate job
  transitions and repeated shedding thresholds inside a large tick is outside
  this task. The existing sampled policy remains. Long/small-step equivalence
  is tested for stable circuits without such transitions.
- Recovery opportunity forecasts in `core/deadnode_opportunities.py` still use
  their existing coarse galactic-duration energy estimates. They are not the
  runtime integrator and have not been migrated or used as an energy oracle.

CLI/Textual power readings keep their commands and units. The bilingual power
manuals explain onboard kW/kWh and timers; no help command syntax or event text
changes are needed. Tests and results:
[verification](../testing/electrical-proper-time-review.md).
