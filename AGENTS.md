# Agent instructions — Retorno

Use the project environment at `/home/jon/prog/retorno_case/retorno_venv`.
Run Python through its `bin/python`; never use system `python` or plain
`pytest`. In another checkout, use that checkout's project environment.

Read these references as needed before work:

1. [Permanent work rules](docs/development/working-rules.md)
   ([español](docs/development/working-rules.es.md)) — scope, Git, testing,
   interruption recovery, localization and player knowledge.
2. [System contract index](docs/development/system-contracts.md)
   ([español](docs/development/system-contracts.es.md)) — cross-system
   invariants and links to the owning technical specifications.
3. [Current development status](docs/development/current-status.md)
   ([español](docs/development/current-status.es.md)) — completed work,
   playtest issues and pending phases. `TODO.md` remains an uncurated backlog.

Keep interventions small. Preserve unrelated changes and original saves.
Do not commit, push or merge without authorization. Stop and report a problem
that exceeds the authorized scope. Do not rerun still-valid tests. Keep normal
UI diegetic and internal diagnostics behind debug mode.
