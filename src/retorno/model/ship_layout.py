from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from retorno.model.ship import ShipSector

if TYPE_CHECKING:
    from retorno.core.gamestate import GameState


@dataclass(frozen=True, slots=True)
class CanonicalSectorSpec:
    sector_id: str
    name_en: str
    name_es: str
    tags: tuple[str, ...]
    notes: str = ""


# Canonical RETORNO layout.
# Sector IDs are reusable across ships; global uniqueness must come from ship/node context.
RETORNO_CANONICAL_SECTORS: tuple[CanonicalSectorSpec, ...] = (
    CanonicalSectorSpec("DCK-A1", "Dock / Airlock", "Darsena / Exclusa", ("dock", "airlock")),
    CanonicalSectorSpec("STS-BAY", "Stasis Bay", "Bahia de Estasis", ("stasis", "medical")),
    CanonicalSectorSpec("LFS-01", "Life Support", "Soporte Vital", ("life_support",)),
    CanonicalSectorSpec("PWR-A1", "Power Core", "Nucleo de Potencia", ("power", "generation")),
    CanonicalSectorSpec("PWR-A2", "Power Distribution", "Distribucion de Energia", ("power", "distribution")),
    CanonicalSectorSpec("PRP-R1", "Propulsion Room", "Sala de Propulsion", ("propulsion", "reserved")),
    CanonicalSectorSpec("BRG-01", "Bridge / Command", "Puente / Mando", ("bridge", "command", "restricted")),
    CanonicalSectorSpec("SNS-R1", "Sensors Room", "Sala de Sensores", ("sensors",)),
    CanonicalSectorSpec("DRN-BAY", "Drone Bay", "Bahia de Drones", ("drone", "bay")),
    CanonicalSectorSpec("CRG-01", "Cargo Hold", "Bodega de Carga", ("cargo",)),
)

RETORNO_CANONICAL_SECTOR_IDS: set[str] = {spec.sector_id for spec in RETORNO_CANONICAL_SECTORS}
RETORNO_CANONICAL_SECTOR_BY_ID: dict[str, CanonicalSectorSpec] = {
    spec.sector_id: spec for spec in RETORNO_CANONICAL_SECTORS
}

RETORNO_SYSTEM_TO_SECTOR: dict[str, str] = {
    "life_support": "LFS-01",
    "core_os": "BRG-01",
    "data_core": "BRG-01",
    "security": "BRG-01",
    "power_core": "PWR-A1",
    "energy_distribution": "PWR-A2",
    "sensors": "SNS-R1",
    "drone_bay": "DRN-BAY",
}

# Internal-only aliases for save/state migration.
RETORNO_LEGACY_SHIP_SECTOR_ALIASES: dict[str, str] = {
    "drone_bay": "DRN-BAY",
}


def canonical_ship_sector_id(sector_id: str) -> str:
    sid = str(sector_id or "").strip()
    if not sid:
        return sid
    if sid in RETORNO_CANONICAL_SECTOR_IDS:
        return sid
    alias_target = RETORNO_LEGACY_SHIP_SECTOR_ALIASES.get(sid)
    if alias_target:
        return alias_target
    upper_sid = sid.upper()
    if upper_sid in RETORNO_CANONICAL_SECTOR_IDS:
        return upper_sid
    return sid


def ship_sector_name_for_locale(sector_id: str, locale: str, fallback: str | None = None) -> str:
    sid = canonical_ship_sector_id(sector_id)
    spec = RETORNO_CANONICAL_SECTOR_BY_ID.get(sid)
    if spec is None:
        return fallback or sid
    if str(locale or "en").lower() == "es":
        return spec.name_es
    return spec.name_en


def build_retorno_ship_sectors() -> dict[str, ShipSector]:
    sectors: dict[str, ShipSector] = {}
    for spec in RETORNO_CANONICAL_SECTORS:
        sectors[spec.sector_id] = ShipSector(
            sector_id=spec.sector_id,
            name=spec.name_en,
            tags=set(spec.tags),
            notes=spec.notes,
        )
    return sectors


def compose_ship_sector_context_id(ship_id: str, sector_id: str) -> str:
    return f"{ship_id}:{canonical_ship_sector_id(sector_id)}"


def drone_bay_sector_id_for_ship(ship_state) -> str:
    system = ship_state.systems.get("drone_bay") if getattr(ship_state, "systems", None) else None
    if system:
        sid = canonical_ship_sector_id(system.sector_id)
        if sid in getattr(ship_state, "sectors", {}):
            return sid
    if "DRN-BAY" in getattr(ship_state, "sectors", {}):
        return "DRN-BAY"
    for sid, sector in getattr(ship_state, "sectors", {}).items():
        tags = getattr(sector, "tags", set()) or set()
        if "drone" in tags and "bay" in tags:
            return str(sid)
    return "DRN-BAY"


def apply_retorno_canonical_layout(state: GameState) -> None:
    ship = getattr(state, "ship", None)
    if ship is None or getattr(ship, "ship_id", "") != "RETORNO_SHIP":
        return

    ship.sectors = build_retorno_ship_sectors()

    for system_id, sector_id in RETORNO_SYSTEM_TO_SECTOR.items():
        system = ship.systems.get(system_id)
        if system is not None:
            system.sector_id = sector_id

    for drone in ship.drones.values():
        if drone.location.kind == "ship_sector":
            drone.location.id = canonical_ship_sector_id(drone.location.id)

    jobs_state = getattr(state, "jobs", None)
    if jobs_state is None:
        return
    for job in jobs_state.jobs.values():
        if job.target and job.target.kind == "ship_sector":
            job.target.id = canonical_ship_sector_id(job.target.id)
        if isinstance(job.params, dict):
            for key in ("sector_id", "ship_sector_id"):
                if key in job.params and isinstance(job.params[key], str):
                    job.params[key] = canonical_ship_sector_id(job.params[key])
            if "target_id" in job.params and isinstance(job.params["target_id"], str):
                job.params["target_id"] = canonical_ship_sector_id(job.params["target_id"])
