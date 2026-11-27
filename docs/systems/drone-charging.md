# PT001-07A/07B — electrical drone charging

The 07A proposal was approved in an external review and implemented in 07B.
The fixed `drone_bay` draw remains part of base load. Transfer to drones is an
additional variable load only while a `DOCKED` drone in its bay sector receives
energy. The decision in `core/drone_charging.py` is shared by productive
accounting, electrical forecasts, and causal cuts. It adds no persistent fields.

The approved calibration is `0.2 / (0.005 × 3600) = 1/90 kWh` per drone battery
unit. With a nominal bay, normal charging is 0.005 units per proper second at
0.2 kW; slow charging is 0.00125 at 0.05 kW. Existing limited (0.5) and
damaged/critical (0.25) bay multipliers scale power and rate together. A partial
allocation scales the rate linearly with actual power. Power is allocated in
sorted drone ID order. Normal charging requires enough real surplus; slow
charging may draw reserve when ship battery SoC is above 25% and discharge
capacity remains after ordinary load. At or below the threshold, only real
surplus can be assigned. The threshold limits charging, not ordinary demand.
`DRONE_CHARGE_NET_MIN_KW` no longer controls admission.

Each segment's charge enters `p_load_kw` before the ship battery is integrated;
its charge/discharge keeps the existing `eta_charge`, `eta_discharge`, and power
limits. The drone gains exactly the assigned power converted over proper
seconds. Only charging changes time base: exposure, deployed drain,
decontamination, and passive repair continue to use the galactic interval
passed once to maintenance per tick.

The electrical integrator applies immediate regulation before choosing a
charging cut. A timed quality shed is an electrical boundary: energy up to it
uses the preceding allocation, and later energy uses the regulated allocation.
The integrator subdivides when a drone fills or SoC reaches 25%, then
recomputes allocation without repeating jobs, narrative, RNG, repair, or
wear. It never snaps the main battery to an unachieved floor, including in
god mode. Physical forecasts add those proper-time cuts and compare the
effective drone gain to the forecast. A physical interval that skips a pending cut fails
atomically. The decision is invalidated when power, bay/distribution state,
capacity, SoC, eligibility, or drone battery changes. No charging cuts are
added without active charging.

Targeted tests: `tests/test_pt001_07b.py`. Intervention results and limits are
recorded in `docs/testing/pt001-07b-review.md`.
