from __future__ import annotations

from dataclasses import dataclass


class Action:
    pass


@dataclass(slots=True)
class Status(Action):
    pass


@dataclass(slots=True)
class Diag(Action):
    system_id: str


@dataclass(slots=True)
class PowerShed(Action):
    system_id: str


@dataclass(slots=True)
class DroneDeploy(Action):
    drone_id: str
    sector_id: str
    emergency: bool = False


@dataclass(slots=True)
class Repair(Action):
    drone_id: str
    system_id: str


@dataclass(slots=True)
class Boot(Action):
    service_name: str


@dataclass(slots=True)
class Dock(Action):
    node_id: str


@dataclass(slots=True)
class Salvage(Action):
    node_id: str
    kind: str
    amount: int = 1


@dataclass(slots=True)
class Install(Action):
    module_id: str


@dataclass(slots=True)
class DroneReboot(Action):
    drone_id: str


@dataclass(slots=True)
class DroneRecall(Action):
    drone_id: str


@dataclass(slots=True)
class SalvageScrap(Action):
    drone_id: str
    node_id: str
    amount: int


@dataclass(slots=True)
class SalvageModule(Action):
    drone_id: str
    node_id: str
