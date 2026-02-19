from __future__ import annotations

from dataclasses import dataclass, field

from retorno.model.events import EventManagerState
from retorno.model.jobs import JobManagerState
from retorno.model.ship import ShipState
from retorno.model.os import OSState
from retorno.model.world import WorldState


@dataclass(slots=True)
class MetaState:
    save_version: int = 1
    rng_seed: int = 12345
    prologue_complete: bool = False


@dataclass(slots=True)
class ClockState:
    t: float = 0.0          # segundos desde inicio
    last_dt: float = 1.0


@dataclass(slots=True)
class GameState:
    meta: MetaState = field(default_factory=MetaState)
    clock: ClockState = field(default_factory=ClockState)
    world: WorldState = field(default_factory=WorldState)
    ship: ShipState = field(default_factory=lambda: ShipState(ship_id="SHIP_1", name="RETORNO"))
    os: OSState = field(default_factory=OSState)
    jobs: JobManagerState = field(default_factory=JobManagerState)
    events: EventManagerState = field(default_factory=EventManagerState)
