from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from typing import Optional, Tuple
from retorno.config.balance import Balance


@dataclass(slots=True)
class SpaceNode:
    node_id: str
    name: str
    kind: str  # "ship", "station", "derelict"
    radiation_rad_per_s: float = 0.0
    radiation_base: float = 0.0
    region: str = ""
    x_ly: float = 0.0
    y_ly: float = 0.0
    z_ly: float = 0.0
    salvage_scrap_available: int = 0
    salvage_modules_available: list[str] = field(default_factory=list)
    recoverable_drones_count: int = 0
    salvage_dry: bool = False
    links: set[str] = field(default_factory=set)
    is_hub: bool = False

    def __setstate__(self, state) -> None:
        """Backward-compatible unpickle for slot additions."""
        slot_state = state
        if isinstance(state, tuple):
            if len(state) == 2 and isinstance(state[1], dict):
                slot_state = state[1]
            elif len(state) == 2 and isinstance(state[0], dict):
                slot_state = state[0]
        if not isinstance(slot_state, dict):
            raise TypeError(f"Unsupported SpaceNode pickle payload: {type(state)!r}")

        data = dict(slot_state)
        if "recoverable_drones_count" not in data:
            data["recoverable_drones_count"] = 0

        for f in fields(self):
            if f.name in data:
                value = data[f.name]
            elif f.default is not MISSING:
                value = f.default
            elif f.default_factory is not MISSING:
                value = f.default_factory()
            else:
                continue
            object.__setattr__(self, f.name, value)


@dataclass(slots=True)
class SpaceGraph:
    nodes: dict[str, SpaceNode] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)  # adjacency


@dataclass(slots=True)
class IntelItem:
    intel_id: str
    t: float
    kind: str  # "node", "link", "sector", "coord"
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    sector_id: Optional[str] = None
    coord: Optional[Tuple[float, float, float]] = None
    confidence: float = 0.0
    source_kind: str = "nav_fragment"  # uplink | nav_fragment | mail | log | manual | scan
    source_ref: Optional[str] = None
    note: Optional[str] = None


@dataclass(slots=True)
class WorldState:
    space: SpaceGraph = field(default_factory=SpaceGraph)
    known_contacts: set[str] = field(default_factory=set)
    known_nodes: set[str] = field(default_factory=set)
    known_intel: dict[str, dict] = field(default_factory=dict)
    forced_hidden_nodes: set[str] = field(default_factory=set)
    intel: list[IntelItem] = field(default_factory=list)
    next_intel_seq: int = 1
    next_tmp_seq: int = 1
    active_tmp_node_id: str | None = None
    active_tmp_from: str | None = None
    active_tmp_to: str | None = None
    active_tmp_progress: float | None = None
    generated_sectors: set[str] = field(default_factory=set)
    known_links: dict[str, set[str]] = field(default_factory=dict)
    current_node_id: str = "UNKNOWN_00"
    current_pos_ly: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rng_seed: int = 0
    salvage_tip_nodes: set[str] = field(default_factory=set)
    arc_placements: dict[str, dict] = field(default_factory=dict)
    mobility_failsafe_count: int = 0
    mobility_no_new_uplink_count: int = 0
    mobility_hints: list[dict] = field(default_factory=list)
    visited_nodes: set[str] = field(default_factory=set)
    fine_ranges_km: dict[str, float] = field(default_factory=dict)
    lore: "LoreSchedulerState" = field(default_factory=lambda: LoreSchedulerState())
    node_pools: dict[str, "NodePoolState"] = field(default_factory=dict)
    lore_placements: "LorePlacementState" = field(default_factory=lambda: LorePlacementState())
    dead_nodes: dict[str, "DeadNodeState"] = field(default_factory=dict)
    deadnode_log: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NodePoolState:
    initialized_t: float = 0.0
    window_open: bool = True
    window_closed_t: float | None = None
    window_closed_reason: str | None = None
    base_files: list[dict] = field(default_factory=list)
    injected_files: list[dict] = field(default_factory=list)
    pending_push_piece_ids: set[str] = field(default_factory=set)
    delivered_piece_ids: set[str] = field(default_factory=set)
    uplink_route_pool: list[str] = field(default_factory=list)
    uplink_data_consumed: bool = False
    scrap_complete: bool = False
    data_complete: bool = False
    extras_complete: bool = False
    node_cleaned: bool = False


@dataclass(slots=True)
class LorePlacementState:
    piece_to_node: dict[str, str] = field(default_factory=dict)
    piece_channel_bindings: dict[str, str] = field(default_factory=dict)
    next_non_forced_eval_t: float = 0.0
    eval_seq: int = 0


@dataclass(slots=True)
class LoreSchedulerState:
    delivered: set[str] = field(default_factory=set)
    counters: dict[str, int] = field(default_factory=lambda: {
        "uplink_count": 0,
        "dock_count": 0,
        "salvage_data_count": 0,
        "signal_count": 0,
    })
    last_delivery_t: float = 0.0
    delivery_log: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeadNodeState:
    stuck_since_t: float | None = None
    dead_since_t: float | None = None
    stuck_since_uplinks: int = 0
    dead_since_uplinks: int = 0
    stuck_threshold_uplinks: int = 0
    dead_threshold_uplinks: int = 0
    stuck_threshold_years: float = 0.0
    dead_threshold_years: float = 0.0
    attempts: int = 0
    last_action_t: float = 0.0
    bridge_node_id: str | None = None


SECTOR_SIZE_LY = 10.0


def sector_id_for_pos(x_ly: float, y_ly: float, z_ly: float) -> str:
    import math
    sx = math.floor(x_ly / SECTOR_SIZE_LY)
    sy = math.floor(y_ly / SECTOR_SIZE_LY)
    sz = math.floor(z_ly / SECTOR_SIZE_LY)
    return f"S{sx:+04d}_{sy:+04d}_{sz:+04d}"


def region_for_pos(x_ly: float, y_ly: float, z_ly: float) -> str:
    import math
    dx = x_ly - float(Balance.GALAXY_CENTER_X_LY)
    dy = y_ly - float(Balance.GALAXY_CENTER_Y_LY)
    dz = z_ly - float(Balance.GALAXY_CENTER_Z_LY)
    r = math.sqrt(dx * dx + dy * dy + dz * dz)
    if r < float(Balance.GALAXY_BULGE_RADIUS_LY):
        return "bulge"
    if r < float(Balance.GALAXY_DISK_OUTER_RADIUS_LY):
        return "disk"
    return "halo"


def add_known_link(
    state: WorldState, from_id: str, to_id: str, bidirectional: bool = False
) -> bool:
    if not from_id or not to_id or from_id == to_id:
        return False
    before = len(state.known_links.get(from_id, set()))
    state.known_links.setdefault(from_id, set()).add(to_id)
    added = len(state.known_links.get(from_id, set())) > before
    if bidirectional and from_id != to_id:
        state.known_links.setdefault(to_id, set()).add(from_id)
    return added


def _intel_key(
    kind: str,
    from_id: Optional[str],
    to_id: Optional[str],
    sector_id: Optional[str],
    coord: Optional[Tuple[float, float, float]],
) -> tuple:
    return (kind, from_id, to_id, sector_id, coord)


def record_intel(
    state: WorldState,
    *,
    t: float,
    kind: str,
    confidence: float,
    source_kind: str,
    source_ref: Optional[str] = None,
    from_id: Optional[str] = None,
    to_id: Optional[str] = None,
    sector_id: Optional[str] = None,
    coord: Optional[Tuple[float, float, float]] = None,
    note: Optional[str] = None,
) -> Optional[IntelItem]:
    key = _intel_key(kind, from_id, to_id, sector_id, coord)
    for item in state.intel:
        if _intel_key(item.kind, item.from_id, item.to_id, item.sector_id, item.coord) == key:
            return None
    intel_id = f"I{state.next_intel_seq}"
    state.next_intel_seq += 1
    item = IntelItem(
        intel_id=intel_id,
        t=t,
        kind=kind,
        from_id=from_id,
        to_id=to_id,
        sector_id=sector_id,
        coord=coord,
        confidence=confidence,
        source_kind=source_kind,
        source_ref=source_ref,
        note=note,
    )
    state.intel.append(item)
    return item


def reachable_from(state: WorldState, current_id: str) -> set[str]:
    return set(state.known_links.get(current_id, set()))
