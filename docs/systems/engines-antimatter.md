# Engines, antimatter and cruise speed

Implemented against CANON v0.5.0, C-TECH-001–007 and provisional
P-TECH-001–002. The canon commit is
`bc95cae37c04c4cd20f9e205558766bb8bdbb066`.

`bootstrap.py` creates `engines` in ENG-R1 at NOMINAL, integrity 0.90. It
replaces the player's former `security` system and `securityd` service. Other
installations and access-control concepts are unaffected. ENG-R1 is active,
not reserved. There are no independent component diagnostics.

The existing `ShipSystem` model owns wear, health-state transitions,
electrical demand, diagnostics and drone repair. Provisional electrical and
wear settings use a 0.2 kW auxiliary load and 8.5e-11/s decay,
with k_power=0.30 and k_rad=0.10. Priority 1 and the critical tag preserve
engine supply through automatic load shedding; CRUISE does not isolate or
reduce its auxiliary load. Manual isolation and physical deterioration remain
possible. Departures require powered engines in DAMAGED or better state;
critical/offline or zero-integrity engines block departure. Subsequent wear
uses the existing transit model and affects prices for future departures.

`ShipState.antimatter_capsules` is the live, divisible reserve: initially 12.0
capsule equivalents. The meter is separate from the stale scrap/module cargo
manifest; an audit never resets it. Capsules are stored in CRG-01 with
self-powered confinement. `power_core` is an independent compact fusion
reactor with sealed internal reserves and no consumable player resource.
Ordinary engine reactants have no separate inventory.

`Engine.engine_fuel_cost` implements the provisional formula:

```text
(0.5 + distance_ly / 10)
* (1 + 1.5 * (1 - clamp(health / health_max_effective, 0, 1))**2)
* upgrade_multiplier
```

The multiplier is 1.0 without the efficiency package, 0.8 with it. Module
catalog effects own the multiplier; the existing installation/uninstallation
jobs own its activation and removal. Multiple copies of the same package do
not compound the effect. Installation costs 18 scrap and uses the normal
shipboard drone and bay requirements, returning the module to cargo on removal.
Engine integrity and effective maximum never change as module effects.

`Engine.estimate_travel_fuel(state, destination_id)` is a public read-only
query returning an unrounded float or `None` when no known, physically valid
direct hop can be estimated. It checks acquired destination knowledge, direct
route and hop cap before computing a cost. It does not generate sectors,
change fine ranges, import intel or consume RNG. Local classification uses
the same sector/radius rule as travel, including when fine ranges have not
yet been cached. Local costs are zero.

Accepted interstellar departures debit the quoted amount once, immediately
before setting transit state. Insufficient fuel changes neither navigation,
range caches nor fuel. No tolerance admits a reserve below the exact price.
Repeated departure requests during transit, ticks, arrival and `nav abort`
make no additional charge; abort does not refund. Floating-point quantities
retain full internal precision without per-trip rounding; displayed costs use
Python's round-trip float representation, so display rounding cannot promise
a cheaper departure. Queries and confirmation reflect current integrity and
installed modules; ongoing simulation may change a future price before acceptance.

CLI/REPL and Textual share `cli/repl.py` renderers and `fuel_readout`, plus the
same Engine actions. Public commands:

- `inventory`, `cargo`, `status`: live capsule reserve.
- `nav map routes` (alias `nav routes`): known direct route estimates, available
  reserve and sufficiency. Navigation confirmation repeats the estimate.
- `diag engines`, `locate engines`, `power status`, `power on/off engines`:
  global engine condition, location and electrical control.
- `drone deploy D1 ENG-R1`, `drone repair D1 engines`: existing repair flow.
- `module inspect engine_efficiency_upgrade_01`, `drone install D1
  engine_efficiency_upgrade_01`, `drone uninstall D1
  engine_efficiency_upgrade_01`: existing module flow when a cargo copy exists.
- `man engines`, `man engine_efficiency_upgrade_01`: bilingual manuals.

Waypoints, hibernation rules, proper-time formula and hop limits are unchanged.
T-04A adds the state-dependent departure speeds and inertial cruise below. Earlier player configurations are rejected by save validation;
there is no migration to the new engines/fuel state. Capsule salvage,
procedural capsule supply and fuel-exhaustion recovery are outside this phase.
The existing module pool can supply the efficiency module as a rare ship module.

## T-04A: state-dependent speed and inertial cruise

`ShipState.cruise_speed_ly_per_year` remains the configurable nominal reference
(initially 0.5). `Balance.ENGINE_SPEED_MULTIPLIERS` owns the initial profile:

| State | Multiplier | Initial speed |
| --- | --- | --- |
| UPGRADED | 1.6 | 0.8c |
| NOMINAL | 1.0 | 0.5c |
| LIMITED | 0.8 | 0.4c |
| DAMAGED | 0.6 | 0.3c |
| CRITICAL / OFFLINE | no departure | unavailable |

`ShipState.engine_operating_state()` centralizes engine-specific state, using
existing absolute health bands from Balance: nominal at health >= 0.85, limited
at >= 0.60, damaged at >= 0.35, critical above zero, offline at zero or when
forced off. Only an installed `engine_speed_upgrade_01` permits UPGRADED with
nominal health. Health alone never grants it. Wear, repairs, manual power
restoration and module completion use the same rule; other systems keep their
existing state logic. `effective_cruise_speed()` applies the configured profile
and caps finite positive speeds at `math.nextafter(1.0, 0.0)`; nonpositive or
nonfinite results block interstellar departure. Local travel stays at 20 km/s,
with the existing engine gate, independently of the interstellar multipliers.

The speed module uses the existing ship module catalogue and rare pool, 18 scrap,
and ordinary drone installation/removal. Its Boolean catalogue effect describes
activation of this state capability. Repeated copies do not compound; removing
the last copy restores the health-appropriate state. Both speed and efficiency
modules can coexist. Speed does not change health, effective maximum, electrical
bonuses or antimatter price. For engines only, UPGRADED draws the same auxiliary
power as NOMINAL, avoiding the generic UPGRADED 1.10 power multiplier.

Accepted interstellar departure calculates effective speed and duration, records
`transit_speed_ly_per_year` and fixes arrival time. `Engine._tick_interval` uses
that frozen value for `proper_time_interval`: dt * sqrt(1 - beta²). Later engine
wear, repair, power changes, nominal configuration or module completion affect
future departures, never the ongoing speed, ETA or proper time. Arrival still
splits moving/rest intervals; abort ends movement without a refund. No acceleration
or braking is simulated. T-04B1 integrates ordinary electricity and electrical
regulation in [ship proper time](electrical-proper-time.md); wear, radiation,
jobs and hibernation retain their existing galactic time integration.

Save/load persists both modules and frozen speed without reconstructing it from
current engine state. Active interstellar saves without a valid positive frozen
speed below c are rejected; no old-save migration is implemented.

`Engine.estimate_travel_duration` returns galactic seconds or None for an unknown,
invalid or currently unavailable hop. It shares the acquired direct-route boundary
with fuel queries and computes missing local ranges without caching or RNG use.
The planner uses the same effective-speed query. CLI/REPL and Textual share
`speed_readout` through status, diag engines, routes and navigation confirmation;
Textual's systems panel includes it. Telemetry distinguishes available departure
speed, nominal reference and actual transit speed; route estimates are prospective,
not revisions to the active ETA. Module inspect and installed counts describe both
independent effects. `help --verbose` and manuals cover the updated queries;
plain help retains the same command syntax.

Use `module inspect engine_speed_upgrade_01`, `drone install D1
engine_speed_upgrade_01`, `drone uninstall D1 engine_speed_upgrade_01`, and
`man engine_speed_upgrade_01`. Ordinary task gates remain: CRUISE isolates the
drone bay; restore its support to install/repair. New removal requests are blocked
in transit, while a previously queued removal can complete in flight.

Focused coverage is in `tests/test_engine_speed_upgrade.py`, existing speed/clocks
and antimatter tests. [T-04A verification](../testing/engine-speed-upgrade-review.md)
records actual checks and limitations. Catalogue additions change the existing
world fingerprint; fresh games are required for old catalogue-dependent saves.
The historical prologue fixture explicitly excludes both newer engine modules.

Verification lives in `tests/engines_antimatter_smoke.py`, supplemented by
existing prologue, route, power, persistence, localization and Textual tests.

Minimal Textual check from the repository root:

```bash
RETORNO_SCENARIO=fast_sandbox PYTHONPATH=src /home/jon/prog/retorno_case/retorno_venv/bin/python -m retorno.ui_textual.app --new-game
```

Use `inventory`, `diag engines`, `ship map`, `nav map routes`; choose a displayed
route, run `nav <id>` and confirm. Compare the new reserve with the quoted cost.
Run `nav abort` and confirm; the reserve must stay unchanged. For the ordinary
prologue use `--new-game` and restore power/sensors before acquiring routes.

Test results and the clean-HEAD comparison are recorded in [verification](../testing/engines-antimatter-review.md).
