# Engines, antimatter and target cruise speed

Implemented on `main` after T-04A/B1/B2 (`d423fef`), following CANON v0.6.0
C-TECH-008/009 and P-TECH-003/004. This is the existing engine contract updated
for selectable speed; the resolved ordinary-wear discrepancy stays resolved.

`engines` is the antimatter propulsion assembly in ENG-R1: nominal initial
integrity 0.90, 0.2 kW auxiliaries, priority 1, protected by the existing CRUISE
and shedding policies. `power_core` independently generates fusion electricity.
Capsules have a divisible live reserve (`antimatter_capsules`, initially 12.0)
separate from the stale cargo manifest. No new module, capsule supply, physical
acceleration/braking or in-transit speed change is introduced.

## Selection, ceiling and transit

- `engines speed`: pure onboard query, available during transit.
- `engines speed max`: select the highest supported discrete speed on each departure.
- `engines speed 0.3`: persist an explicit target; all steps from 0.1c to 0.8c
  are recognized, but only currently supported values can be selected.
- Changes, including selecting max again, are rejected during any active transit.

`ShipState.target_cruise_speed` stores None for max (the new-game default), or a
numeric beta. It never overwrites `cruise_speed_ly_per_year`, the configurable
nominal reference, initially 0.5. `maximum_cruise_speed()` computes capability
from actual health, electrical isolation and installed speed equipment, using
`Balance.ENGINE_SPEED_MULTIPLIERS` and `ENGINE_SPEED_UPGRADE_MULTIPLIERS`.
It chooses the highest selectable step at/below that reference-scaled ceiling,
strictly below c. With the default nominal reference:

| Engine health/state | Without speed module | With speed module |
| --- | --- | --- |
| Nominal-capable (NOMINAL / UPGRADED) | 0.5c | 0.8c |
| LIMITED | 0.4c | 0.6c |
| DAMAGED | 0.3c | 0.4c |
| CRITICAL / OFFLINE / forced off | no departure | no departure |

`engine_operating_state()` keeps the existing absolute health bands and
UPGRADED presentation only for nominal-capable equipped engines. The ceiling
also benefits LIMITED/DAMAGED engines without requiring that label. Multiple
copies do not stack. `effective_cruise_speed()` returns the next departure's
speed: ceiling for max, explicit target if still valid, otherwise zero. A target
invalidated by damage, power isolation or removal stays persisted. An interstellar
departure then blocks; repair/reinstallation can restore it, or the operator can
select max/a supported lower value. There is no silent reduction of a fixed target.

Local travel retains 20 km/s, zero capsule cost and existing physical-engine gates.
It ignores the interstellar target, including a fixed target invalidated since
selection. CRUISE is an independent electrical profile; changing target speed
neither applies that profile nor changes auxiliary power, health or maximum health.

## Fuel and quotes

`Engine.engine_fuel_cost(state, distance_ly, speed=None)` keeps the original
integrity/efficiency formula and multiplies by the selected departure speed's
factor from `Balance.ENGINE_SPEED_FUEL_MULTIPLIERS`:

```text
(0.5 + distance_ly / 10)
* (1 + 1.5 * (1 - clamp(health / health_max_effective, 0, 1))**2)
* efficiency_multiplier * speed_multiplier
```

| Speed | Price multiplier |
| --- | --- |
| 0.1c | 0.30 |
| 0.2c | 0.48 |
| 0.3c | 0.66 |
| 0.4c | 0.82 |
| 0.5c | 1.00 |
| 0.6c | 1.28 |
| 0.7c | 1.65 |
| 0.8c | 2.20 |

The optional explicit speed parameter prices a valid step for simulation/testing;
normal actions/queries resolve and gate the live target first. With no valid
prospective speed, an interstellar quote is unavailable. Local quotes remain zero.

`engine_efficiency_upgrade_01` multiplies cost by 0.8, independently of ceilings
or selected speed. `engine_speed_upgrade_01` raises ceilings without a direct
fuel discount or surcharge at the same speed/integrity. Installing it while
using max can raise the next trip's speed and therefore cost. Both ordinary
18-scrap rare ship modules use existing drone installation/removal; repeated
copies do not compound benefits. UPGRADED engine auxiliary load equals NOMINAL.

Public fuel and duration queries share acquired direct-route authorization;
unknown/unacquired/missing/over-cap routes return None without generating
sectors, writing ranges, importing intel or consuming RNG. Duration is distance
/ valid departure speed, or the existing local fine-range calculation. CLI/REPL
and Textual use the same parser, action and renderer (`render_engines_speed`,
`speed_readout`, `fuel_readout`); completions share speed choices. Status and
`diag engines` distinguish target, ceiling, prospective
speed, actual frozen transit speed, nominal reference and electrical mode.

The ordinary `engines speed` query is specialized: state and target (MAX with
resolved speed, or an explicit value), followed by configuration/manual hints.
An unavailable target instead shows the permitted ceiling and a departure block
without changing the saved selection. In transit, the view adds the actual frozen
speed (km/s locally) and a restriction on changes, replacing the configuration
hint. Electrical mode and nominal-reference fields stay in the full diagnostics.

`nav_confirmation(state, action)` provides one pure public preview and prompt
for REPL and Textual: destination public ID; target/effective cruise and galactic
ETA; approximate capsule cost, current reserve and approximate remaining reserve.
Capsules use three decimals and `~` for the rounded estimates. Local maneuvers
reuse the actual local-hop classifier and show km/s, compact ETA and zero fuel.
Unavailable quotes show dashes and a block notice; insufficient fuel remains an
explicit warning. The ordinary question is neutral. The original abandonment
warning for deployed/disabled drones outside the ship remains intact. Asking,
accepting the question or declining it does not debit or start transit; only
the existing subsequent Engine action can do that, after revalidating conditions.
No changes to audio, auto-event draining or confirmation/cancellation dispatch.

Both compact views keep labels and figures neutral, destination public IDs in
theme accent, and engine states in their existing semantic colors. Alerts retain
warning/error colors. The specialized patterns in `ui_theme.py` leave other
command styles unchanged; `fuel_readout` and `speed_readout` remain available
at full diagnostic detail. Focused checks extend `tests/test_engine_speed_upgrade.py`.

`nav map routes` uses a compact shared CLI/Textual presentation: reserve to three
decimals, physical engine state and MAX (resolved speed) or the explicit target
in the header. An unavailable target retains its value and shows the permitted
maximum. Each existing destination identity line is followed by one Fuel/Speed/ETA
line. Fuel is explicitly approximate (`~`, three decimals); local classification
reuses the engine's read-only helpers and shows km/s. ETA uses `_format_eta_short`.
Unavailable estimates show dashes; notices appear only for insufficient fuel or
blocked departure. Names and public IDs use the current theme accent, navigation
headings retain emphasis, metric labels stay plain and states retain semantic
colors. `ui_theme.py` recognizes only this view's line formats; other command
styles are unchanged. Verified in `tests/test_nav_routes_presentation.py`.

Travel acceptance passes that exact speed to the same fuel calculation used by
quotes and debits once before transit starts. Insufficient fuel or an invalid
fixed target does not mutate ship/world/range/RNG state. Repeated requests, ticks
and arrival do not charge again. Abort gives no refund and adds no charge.
Float prices retain full precision; route lists and confirmation round only
displayed estimates, without rounding the sufficiency comparison or debit.
Simulation can change a quote before confirmation, so acceptance revalidates it.

## Existing time domains and persistence

T-04A records `transit_speed_ly_per_year` and arrival time at departure. Existing
clock integration, [electricity](electrical-proper-time.md) and
[ordinary wear](wear-proper-time.md) continue to use that frozen speed. Their
integrators and arrival sampling are unchanged by this feature. Damage affects
future departure capability, not ongoing speed, ETA, proper time or paid fuel.
Radiation dose, jobs, drones, life-support rules and narrative retain their
existing domains. There is no per-second simulation loop.

Save/load persists the new selection independently of the frozen trip speed.
A valid discrete selection may remain saved even when currently above the ceiling.
The existing slots loader's field defaults yield max for an omitted selection;
no new save schema or general migration is introduced. Existing universe/save
validation still applies. No catalogue or procedural-resource distribution changes.

## Public checks

Use `engines speed`, `engines speed 0.3`, `engines speed max`, `nav map routes`,
`diag engines`, `module inspect engine_speed_upgrade_01` and `man engine_speed`.
`man engines` remains the system manual. Shared EN/ES help and manuals cover
selection and the independent efficiency package. Ordinary core/power command
gates, drone bay support and module task restrictions remain in force.

[Focused tests, balance matrix and sound-enabled Textual walkthrough](../testing/engine-speed-selection-review.md).
The balance is provisional until capsule economy and maintenance can be evaluated
in procedural play; no unrelated coefficients were tuned to improve the results.
