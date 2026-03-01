# Textual UI Guide

This game includes a Textual UI with multiple panels and keyboard shortcuts.

## Panels
- Header (top): current time, ship mode, and location.
- Status (left): ship/system status.
- Alerts (right, top): active alerts.
- Jobs (right, bottom): job queue and recent results.
- Log (bottom): command output and events.
- Input (bottom): command line.

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
