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


@dataclass(slots=True)
class Repair(Action):
    drone_id: str
    system_id: str


@dataclass(slots=True)
class Boot(Action):
    service_name: str
