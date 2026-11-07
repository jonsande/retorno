# Debug god mode

Implemented in `src/retorno/model/os.py`, `src/retorno/core/engine.py`,
`src/retorno/cli/parser.py`, `src/retorno/cli/repl.py` and
`src/retorno/ui_textual/app.py` and `src/retorno/io/save_load.py`. Regression: `tests/debug_god_smoke.py`.

`debug god on` requires debug mode. `debug god off` and `debug god status`
work in either mode. CLI and Textual use the same command handler and EN/ES
messages. Help, parser usage, completion and command manuals include the syntax.

Protection is effective only when both `debug_enabled` and `debug_god_enabled`
are true. `OSState.set_debug` clears protection when leaving debug or starting a
new debug session. Repeating `debug on` in an existing session preserves it.
New scenarios default to off. The shared save loader explicitly clears the flag
for both primary and backup saves; saving does not alter the live session.
Legacy payloads default to off. In-memory copies preserve OS state so recovery
staging keeps its existing invariants. No save schema migration is required.

## Covered mutation points

| Source | Engine owner | Protection |
| --- | --- | --- |
| Hull wear, radiation and transit/hibernation multipliers | `_apply_hull_degradation` → `_damage_hull` | Blocks integrity loss |
| System wear, radiation, poor power, sustained brownout, non-CRUISE transit | `_apply_degradation` | Blocks health loss and associated wear transitions |
| Drone radiation exposure | `_apply_radiation` | Blocks new dose; preserves existing dose |
| Drone wear amplified by accumulated dose | `_update_drone_maintenance` | Blocks integrity loss |
| Deployed idle battery drain | `_update_drone_maintenance` → `_drain_drone_battery` | Blocks consumption |
| Deploy, move, reboot/recall, salvage variants, repair/selftest operators (including failed attempts), ship module installation/removal | Job effects / `_drain_repair_operator_battery` → `_drain_drone_battery` | Blocks consumption |
| Damaged/critical bay operation risk | `_apply_drone_bay_damaged_integrity_risk` | Blocks damage and its event |
| Passive bay repair failure | `_update_drone_maintenance` | Blocks damage; keeps failure and scrap cost |
| Emergency job failure | `_maybe_fail_emergency_job` | Blocks drone damage and disabling; keeps job failure |

Battery is the implemented operational autonomy mechanism. Integrity wear and
radiation dose are also covered. Low-battery alerts, automatic recall rules and
minimum operation requirements remain normal: existing depletion is not healed.
Module removal still clamps integrity/battery to the new effective capacity;
this is a configuration change, not damage or operational exhaustion.

## Boundaries

Activation does not repair health/integrity, revive disabled drones, refill
batteries, remove existing dose, enable failed systems or create resources.
Ordinary paid bay repair, charging, decontamination and requested repair jobs
continue under their existing rules. Power generation, ship energy use, load
shedding, system dependencies, job failure probabilities and resource costs
remain normal. Risk rolls still occur even when their damage is blocked.

Ambient radiation and internal ingress calculations/readings remain normal.
God mode never writes worldgen, history, B1/B2, contacts, known routes, lore,
radio propagation or narrative scheduling. Normal discoveries while time
advances remain possible. `debug on` still stops automatic time, and `wait N`
still advances N seconds in the existing one-second steps. Travel arrival times,
job durations and progress rules are unchanged.

## Focused validation

Run with the repository's canonical virtualenv interpreter:

- `tests/debug_god_smoke.py`: parser and invalid syntax, gating, EN/ES help and
  output, actual CLI/Textual dispatch, all protection categories, forced risk
  failures, previous damage, disabled drones, off/re-entry, unpickle and real
  save/load, unchanged activation snapshot, manual wait and paired short
  travel/job/world progression.
- `tests/radiation_hull_smoke.py`: existing normal hull/radiation behavior.
- `tests/textual_completion_context_smoke.py`: existing completion boundaries.

No general damage refactor, scheduler changes or extended exploration runs.

### Results for 4D-3e5c-GOD-1

- `debug_god_smoke.py`: PASS, including primary/backup load and real CLI/Textual dispatch.
- `textual_completion_context_smoke.py`: PASS.
- Targeted Python compilation, EN/ES command syntax parity, documentation path
  validation and `git diff --check`: PASS.
- `radiation_hull_smoke.py`: existing failure at line 183 (expected ambient
  radiation alert, empty event list). Reproduced unchanged in a temporary clean
  export of `HEAD`; not caused or repaired by this task. The new focused test
  independently checks protected and normal hull/system/drone radiation wear.

Stopped for external review; no staging, commit or push.
