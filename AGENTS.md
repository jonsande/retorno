# AGENTS.md

This file defines the operational rules for agents working in this repository.
It keeps the essential project rules versioned with the code so they also apply
to collaborators and future checkouts.

The goal is to prioritize robustness, reuse of existing infrastructure, and
long-term maintainability.

## Python environment

This project uses the virtual environment at:

```text
/home/jon/prog/retorno_case/retorno_venv
```

This is the canonical path for the current checkout. If a collaborator checks
out the repository elsewhere, they must use the project-specific virtual
environment for that checkout and substitute its absolute interpreter path in
the commands below; using the system interpreter is never an acceptable
fallback.

Always use this interpreter for Python commands:

```text
/home/jon/prog/retorno_case/retorno_venv/bin/python
```

Never run plain `python` or plain `pytest`. Examples:

```text
/home/jon/prog/retorno_case/retorno_venv/bin/python script.py
/home/jon/prog/retorno_case/retorno_venv/bin/python -m pip show <package>
/home/jon/prog/retorno_case/retorno_venv/bin/python -m pytest
/home/jon/prog/retorno_case/retorno_venv/bin/python -m pytest tests/textual_completion_context_smoke.py
```

All project dependencies, including `textual`, are installed in this virtual
environment.

## Engineering workflow

Before modifying code, audit the repository for reusable infrastructure.

1. Reuse existing infrastructure whenever possible.
2. Unify duplicated logic instead of adding parallel implementations.
3. Avoid unnecessary helpers, services, modules, and abstractions.
4. Prefer robust, scalable solutions over ad hoc fixes.

If existing infrastructure cannot be reused, explain why briefly.

When a task can affect several modules or introduce infrastructure, first
identify the relevant modules, helpers, services, and similar implementations.
Small, localized changes do not require an extensive exploration.

## Risk evaluation

Evaluate conflicts, side effects, and architectural risks before making a
change.

- For significant risks, explain the issue, possible solutions, and the
  recommendation, then wait for confirmation before implementing.
- For minor risks, state them briefly and proceed with the best-supported
  option, explaining the decision.

## Documentation synchronization

Any change that alters observable behavior, commands, data schemas,
configuration semantics, universe generation, navigation, intel, lore, or
failsafes must review and update the corresponding technical documentation in
the same change.

Before declaring work complete, evaluate and update, when applicable:

- technical documentation under `docs/`;
- diegetic and user manuals under `data/manuals/`;
- in-game `help` and `help --verbose` output;
- existing English and Spanish counterparts;
- tests or verification matrices that establish the documented behavior.

Documentation must clearly distinguish among implemented behavior, design
decisions, and future proposals. Cite the owning code, configuration, data, or
test paths when useful, and avoid creating a second, duplicated source of
truth. Validate internal paths and links.

For diegetic manuals, follow `docs/manuals_style_guide.md`.

If a behavior change needs no documentation update, state why in the handoff.

## Localization — Mandatory project rule

RETORNO is a bilingual project. All player-facing text must be available in
English and Spanish (EN/ES).

- This applies to CLI/REPL and Textual UI output, menus, events, errors,
  warnings, notifications, help, system and service messages, narrative text,
  and diegetic documentation.
- Every new or modified document must have a corresponding EN/ES version and
  maintain semantic parity with it.
- Use the existing localization infrastructure. Do not introduce parallel
  localization mechanisms or hardcode new player-visible strings in only one
  language.
- Keep internal identifiers, command syntax, localization keys, and technical
  names stable unless a task explicitly authorizes changing them. Localize
  their player-visible descriptions, not the identifiers themselves.
- Internal code comments do not require artificial EN/ES duplication.
- Any change affecting text must validate translation references,
  completeness, and EN/ES consistency. Automate these checks when practical.
- If the existing localization system cannot support required text, report the
  limitation instead of silently leaving it untranslated.
- A change that introduces player-facing text or documentation is incomplete
  until both supported languages have been updated and validated.

## Player knowledge and diegetic information boundaries

Follow `C-DATA-004` in `docs/canon/universo.md` and ask “How does the ship know
this?” using `docs/canon/guia_coherencia.md` before exposing universe facts.

- Every fact presented as ship or protagonist knowledge needs a legitimate
  observation, measurement, captured communication, read archive, prior ship
  record, or inference from available evidence.
- Distinguish physical truth, ship knowledge, and technical scheduler state.
  Inferences may be approximate, uncertain or false, but must be justifiable
  and distinguishable from verified facts.
- Never disclose secret catalogs, undiscovered historical sites, scheduler
  candidates, reserved documents, prepared narrative opportunities or internal
  recovery plans without a valid discovery event.
- Do not use internal collections containing hidden information directly as
  sources for playable diagnostics. Physical `space.nodes`, `lore_placements`,
  `radio_opportunities`, `recovery_searches` and `recovery_plans` are not ship
  knowledge. Known locations, known routes and current reception eligibility
  are separate facts.
- Keep omniscient diagnostics behind explicit development commands gated by
  `debug_enabled`. Ordinary `status` and `diag` retain their public meaning
  even with debug enabled. Diagnostic queries must not advance or mutate the
  simulation, consume RNG, generate sites, receive messages or import intel.
- CLI and Textual must enforce exactly the same knowledge boundary. Review
  events, sounds, help, contextual entity lists, completion and error messages
  as potential disclosure surfaces too.
- New features presenting universe state require negative disclosure tests:
  hold observations constant, vary hidden engine data, and compare public
  output. Also verify preservation of legitimately acquired information.

Menus, controls, save/load and general system help do not need artificial
fictional explanations. This rule concerns universe facts and knowledge
attributed to the protagonist or ship; it permits ordinary interface information
and explicitly activated development diagnostics.
