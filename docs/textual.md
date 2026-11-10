# Textual UI Guide

This game includes a Textual UI with multiple panels and keyboard shortcuts.

## Panels
- Header (top): galactic time, ship proper time, player biological time, ship mode, and location. The clocks use `G:` (galactic), `S:` (ship), and `P:` (player), with the same label color as `P_gen=` and `P_load=`, and include seconds; the header wraps on narrow terminals.
- Status (left): system states and health, without the engine speed summary.
- Alerts (right, top): active alerts.
- Jobs (right, bottom): job queue and recent results.
- Log (bottom): command output and events.
- Input (bottom): command line.

The `status` command also lists all three clocks. Ship time accounts for relativistic time dilation; player biological time also accounts for hibernation. Each clock counts from the start of the mission (year 1, day 1).

In `Y1 D1 00:01:58`, `Y1` is the first year, `D1` the first day of that year, and `00:01:58` hours, minutes, and seconds since mission start. Years and days are numbered from 1, so this example represents 1 minute 58 seconds elapsed. Years have 365 days. Spanish uses `A` instead of `Y`. The header omits the redundant `T+` prefix. Years below 10,000 appear in full; from 10,000 they use `k` (thousands), from 1,000,000 `M` (millions), and from 1,000,000,000 `B` (thousands of millions), rounded to one decimal place. For abbreviated years, the day appears as `+1d` instead of `D1`; for example, `Y12.5k +1d 00:00:00`.

## Core Shortcuts
- `TAB`: autocomplete the current command or argument.
- `Alt+J`: focus next panel.
- `Alt+K`: focus previous panel.
- `J`: scroll down in the focused panel.
- `K`: scroll up in the focused panel.
- `Ctrl+L`: clear the log panel.

## Panel Visibility Toggles
Primary (reliable):
- `F2`: toggle Status panel.
- `F3`: toggle Alerts panel.
- `F4`: toggle Jobs panel.
- `F5`: toggle all panels.

Optional (terminal-dependent):
- `Alt+1`: toggle Status panel.
- `Alt+2`: toggle Alerts panel.
- `Alt+3`: toggle Jobs panel.
- `Alt+0`: toggle all panels.

When panels are hidden, their space is reallocated to the remaining panels. If all status/alerts/jobs are hidden, the log panel expands.

## Autocomplete Notes
- Autocomplete uses known systems, contacts, sectors, and files.
- Press `TAB` to complete. If multiple options share a prefix, it will extend to the common prefix. If there’s no common prefix, press `TAB` twice to list candidates in the log.

## Focus Tips
- Use `Alt+J` / `Alt+K` to cycle focus.
- Scrolling applies to the focused panel.
