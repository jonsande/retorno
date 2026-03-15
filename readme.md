# RETORNO

**RETORNO** is a hard sci-fi, slow-paced, immersive system-driven game played through terminal commands (pure CLI game). You awaken inside a cryogenic sarcophagus aboard a damaged ship, thousands of years after entering suspended sleep. You cannot move physically. Your only link to the world is a terminal wired directly into your mind.

Through that terminal, you must understand what happened, restore critical ship functions, manage power, control maintenance drones, explore abandoned ships and stations, recover resources and information, and gradually navigate a fragmented and silent universe.

RETORNO is designed as an experience of technical survival, exploration, and reading: a calm game of deliberate decisions and real consequences, with occasional moments of sharp tension.

Have you tried the exceptional "Duskers"? **RETORNO** aims to be a hardcore version of it.

## Project status

**Active development.**  
RETORNO is currently a playable prototype. Many core systems are already implemented, but the game is still expanding and evolving.

## Key features

- **Terminal-based interface**: gameplay is driven by typed commands, using a parser inspired by diegetic operating systems and command-line environments.
- **Systemic hard sci-fi gameplay**: power, degradation, radiation, drones, structural damage, and critical states all interact.
- **Technical puzzle prologue**: the opening sequence teaches core mechanics through a power crisis and emergency repairs.
- **Ship systems management**: boot, shut down, diagnose, repair, and prioritize subsystems.
- **Drone control**: deploy, move, repair, salvage, survey, and install modules.
- **Non-linear space exploration**: travel between nodes, discover routes via scans, uplinks, data salvage, and intel.
- **Distributed lore**: emails, logs, navigation fragments, and scattered documents that let players reconstruct stories and small narrative arcs.
- **Hybrid world structure**: a mix of authored locations and procedurally generated nodes, routes, and salvageable content.
- **Real risk and failure states**: poor management can lead to critical conditions and, if not corrected, terminal collapse.

## Design philosophy

RETORNO is not meant to be a fast-paced action game or a traditional combat-heavy roguelike. Its core focus is:

- **technical management under pressure**
- **slow, deliberate exploration**
- **reading and interpreting scattered information**
- **player agency**, even when that means making bad decisions

The game aims to avoid both arbitrary punishment and excessive hand-holding: the player should be allowed to fail, but should also have real tools to understand the system and respond.

## Running the game

Normal (loads savegame if exists)

```bash
PYTHONPATH=src python -m retorno.ui_textual.app
```

User profiles (save per user):

```bash
PYTHONPATH=src python -m retorno.ui_textual.app --user Joe
```

Force a new game:

```bash
PYTHONPATH=src python -m retorno.ui_textual.app --new-game
```


## Basic commands

Some common in-game commands:

- **status**
- **alerts**
- **diag <system_id>**
- **boot <service_name>**
- **power status**
- **power plan cruise|normal**
- **drone status**
- **drone deploy! <drone_id> <sector_id>**
- **drone repair <drone_id> <system_id>**
- **drone salvage scrap <drone_id> <node_id>**
- **scan**
- **route solve <node_id>**
- **nav**
- **travel <node_id>**
- **dock <node_id>**
- **uplink**
- **mail**
- **ls**
- **cat <path>**
- **intel import <path>**

Use **help** in-game for the current and complete command list.

## Language

RETORNO is being prepared to support both Spanish and English.
Commands and technical system names remain in English; diegetic texts (mail, logs, manuals, system messages) can change depending on language settings.

## Manuals style

Official manual templates and structure rules are documented in:
- `docs/manuals_style_guide.md`

Run style validation with:

```bash
python tests/manuals_style_check.py
```

## Roadmap (summary)

Systems already implemented or currently in development include:

- **power management and critical state handling**
- **drones and salvage**
- **routes, navigation, and intel**
- **procedurally generated locations**
- **access privileges (GUEST, MED, etc.)**
- **degradation, radiation, and ship hull integrity**
- **travel events**
- **expansion of distributed lore and mini narrative arcs**

## Note

RETORNO is still under construction. Mechanics, commands, balance, and world structure may change frequently as the project evolves.
