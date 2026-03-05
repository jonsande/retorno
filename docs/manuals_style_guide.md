# Manuals Style Guide

Version: 1.0
Scope: `/data/manuals/*`

This document defines the official template families for RETORNO manuals.
Goal: keep manuals diegetic, clear, detailed, and structurally uniform.

## General Rules
- Keep command ids, system ids, and technical keys in English (code-canonical).
- Keep narrative/operator prose localized (`.en.txt` / `.es.txt`).
- Use section headers consistently (same order per template family).
- Prefer operational language: conditions, impact, recovery, and related commands.
- Avoid implementation noise (`TODO`, `mvp`, speculative behavior) in published manuals.

## Template Families

### 1) Command Manual — FULL
Use for operationally complex commands (`drone`, `route`, `repair`, `uplink`, `boot`, etc.).

Required section order:
1. command syntax lines
2. `Purpose` / `Propósito`
3. `Requirements (gating)` / `Requisitos (gating)`
4. `Operational behavior` / `Comportamiento operativo`
5. `Common block reasons` / `Bloqueos frecuentes`
6. `Related commands` / `Comandos relacionados`

Optional sections:
- `Operational notes` / `Notas operativas`
- `Emergency advice` / `Consejo de emergencia`
- `Equivalent forms` / `Formas equivalentes`

### 2) Command Manual — COMPACT
Use for utility/alias/simple commands (`ls`, `cat`, `wait`, `man`, `job`, etc.).

Required section order:
1. command syntax lines
2. `Purpose` / `Propósito`
3. `Operational behavior` / `Comportamiento operativo`
4. `Related commands` / `Comandos relacionados`

Optional sections:
- `Usage notes` / `Notas de uso`
- `Command status` / `Estado del comando`

### 3) System Manual

Required section order:
1. `SYSTEM SUMMARY — <system_id>` / `RESUMEN DE SISTEMA — <system_id>`
2. `Ref: ...`
3. system intro paragraph
4. `Function` / `Función`
5. `Operational dependencies` / `Dependencias operativas`
6. `Command impact by state` / `Impacto en comandos por estado`
7. `Common symptoms` / `Síntomas comunes`
8. `Recovery pattern` / `Recuperación típica`
9. `Related commands` / `Comandos relacionados`

### 4) Concept Manual

Required structure:
1. `SHIP OS — ...`
2. `Ref: ...`
3. conceptual framing paragraph
4. model sections (clear subsystem breakdown)
5. operator guidance section
6. related commands section

Recommended sections:
- `Model layers` / `Capas del modelo`
- `Operational guidance` / `Guía operativa`

### 5) Alert Manual

Required section order:
1. `ALERT — <alert_key>` / `ALERTA — <alert_key>`
2. `Meaning` / `Significado`
3. `Operational impact` / `Impacto operativo`
4. `Immediate response` / `Respuesta inmediata`

Optional sections:
- escalation thresholds
- trigger conditions

### 6) Module Manual

Required section order:
1. `MODULE DOSSIER — <module_id>` / `DOSSIER DE MÓDULO — <module_id>`
2. `Role` / `Rol`
3. `Operational effect` / `Efecto operativo`
4. `Integration notes` / `Notas de integración`

Optional section:
- `Field note` / `Nota de campo`

## Language Pairing Rules
- Every `<name>.en.txt` should have `<name>.es.txt` in same folder.
- Section intent must match between EN and ES versions.

## Quality Checklist (Definition of Done)
- Correct template family chosen.
- Required sections present and ordered.
- No TODO/MVP placeholders.
- Gating and operational impact are explicit.
- Related commands include the next operator step.
- EN/ES parity preserved.

## Suggested Workflow
1. Pick template family (FULL/COMPACT/system/concept/alert/module).
2. Draft EN and ES together.
3. Run manual style checker.
4. Review technical accuracy against engine behavior.
5. Merge only when checker passes.
