# AMANECER — Places and exploration clues (editorial contract, NOT engine schema)

| Reference | Classification | Generation and use |
|---|---|---|
| **Tábano** | **REQUIRED / PERSISTENT** | Explorable shipwreck. Generator selects its position. Holds `05_the_route.md`, `06_last_watch.md` and a navigation route to a suspected destination. |
| **Bruma** | **REQUIRED / PERSISTENT** | Ship associated with AMANECER's sixth transport. Generated position. Present condition remains undecided. |
| **VAELOR** | **REQUIRED / LOCATABLE** | Stellar system whose location/sector must be inferable from a clue. Its human community is extinct in the playable present. |
| **THALLOINOV, Lunviea, Druinope** | **VAELOR COMPONENTS** | Do not create three separate nodes from textual mentions: use the game's supported system/planet model. |
| **Tábano route destination** | **REQUIRED / REACHABLE** | Generator selects its position. May or may not coincide with the research facility; do not decide here. Information recoverable only from the wreck. |
| **Liria** | **AUTHORED / EXPLORABLE (C2b under review)** | Pre-existing abandoned station, identity `LIRIA`, variable position relative to HARBOR_12, stable per seed. All four Elena documents are reserved exclusively there for salvage and reading. |
| **Bruma auxiliary module** | **REFERENCE ONLY FOR NOW** | Do not generate an independent node. |
| **Other generic places** | **AMBIENT** | Do not create nodes from mentions of sectors, ports, repeaters, etc. |

## Planned narrative dependencies
1. One or more clues let the player find **Tábano**. Define channel and modality when implementing the arcs; no coordinates have been invented.
2. Inside the wreck, the player recovers a narrative record explaining the origin of a route **and generated/parameterized intel** for the suspected destination. They must agree in the run.
3. The route points to an existing place, without guaranteeing the seven people's fate or whether the secret facility operated there.
4. Single `01_vaelor_shipping_receipt.md` contains `[SECTOR_VAELOR]`, pending replacement by an authentic value compatible with the generated world.

## Liria decision — C2b (2026-11-07)
The previous editorial status was “UNDECIDED”: existence as an additional playable
node had not been resolved. C2a approved a historical authored station; C2b copies
the approved draft into the working-tree catalogue. The initial clue is a replica
of an administrative index at an eligible host, not an emission by Elena.
The HARBOR_12 → LIRIA LINK respects 45 ly; it does not assert a historical physical
route or resolve anyone's fate. The bounded public seed-701 journey did not
discover the clue and ended with maintenance/resource blocks. Complete playable
access remains under review; no corrective route is invented. See the
[C2b report](../../docs/testing/amanecer-productive-review.md).
Tábano, Bruma, VAELOR and other arcs/singles retain their previous status.

## Technical-phase caution
The existing `LINK: NODE_A -> NODE_B` lore/intel system may not alone cover
**required ships with variable positions**, **complete planetary systems**, or
**interaction among multiple wreck artifacts**. Evaluate the necessary design
before claiming JSON is sufficient. The editorial contract states desired
outcomes rather than already demonstrated engine capability.
