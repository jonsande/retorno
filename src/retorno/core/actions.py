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
class SystemOn(Action):
    system_id: str


@dataclass(slots=True)
class PowerPlan(Action):
    mode: str  # "cruise" | "normal"


@dataclass(slots=True)
class DroneDeploy(Action):
    drone_id: str
    sector_id: str
    emergency: bool = False


@dataclass(slots=True)
class DroneMove(Action):
    drone_id: str
    target_id: str


@dataclass(slots=True)
class Repair(Action):
    drone_id: str
    system_id: str


@dataclass(slots=True)
class SelfTestRepair(Action):
    system_id: str


@dataclass(slots=True)
class Boot(Action):
    service_name: str


@dataclass(slots=True)
class Dock(Action):
    node_id: str


@dataclass(slots=True)
class Undock(Action):
    pass


@dataclass(slots=True)
class Salvage(Action):
    node_id: str
    kind: str
    amount: int = 1


@dataclass(slots=True)
class Install(Action):
    drone_id: str
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
    node_id: str | None
    amount: int


@dataclass(slots=True)
class SalvageModule(Action):
    drone_id: str
    node_id: str | None


@dataclass(slots=True)
class SalvageData(Action):
    drone_id: str
    node_id: str


@dataclass(slots=True)
class RouteSolve(Action):
    node_id: str


@dataclass(slots=True)
class CargoAudit(Action):
    pass


@dataclass(slots=True)
class JobCancel(Action):
    job_id: str


@dataclass(slots=True)
class Travel(Action):
    node_id: str
    no_cruise: bool = False


@dataclass(slots=True)
class TravelAbort(Action):
    pass


@dataclass(slots=True)
class AuthRecover(Action):
    level: str


@dataclass(slots=True)
class Hibernate(Action):
    mode: str  # "until_arrival" or "years"
    years: float = 0.0
