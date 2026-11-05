"""Read-only recovery proposals. Nothing here activates or persists a plan.

Worldgen's archetype/slot queries below use local RNGs and only read state.
Its registration/generation helpers and lore's writers are deliberately absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import heapq
from itertools import count, product
import math
from types import SimpleNamespace

from retorno.config.balance import Balance
from retorno.core.gamestate import GameState
from retorno.core import lore
from retorno.model.systems import SystemState
from retorno.model.os import read_file
from retorno.model.world import (
    SpaceNode, WorldState, is_hop_within_cap, reachable_from, reachable_known_nodes,
    region_for_pos, sector_id_for_pos,
)
from retorno.runtime.data_loader import load_worldgen_archetypes, load_worldgen_templates
from retorno.worldgen.generator import _plan_sector_kinds, _sector_center, _select_archetype


class Viability(str, Enum):
    VERIFIED = "verified"
    CONDITIONAL = "conditional"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"


class InformationStatus(str, Enum):
    VERIFIED = "verified"
    FUTURE_REQUIRED = "future_required"
    UNAVAILABLE = "unavailable"


class Materialization(str, Enum):
    EXISTING = "existing"
    CONDITIONAL = "conditional"
    UNAVAILABLE = "unavailable"


class Mechanism(str, Enum):
    KNOWN_ROUTE = "known_route"
    EXISTING_INTEL = "existing_intel"
    ROUTE_SOLVE = "route_solve"
    RECOVERY_SIGNAL = "recovery_signal"
    SALVAGE_DATA = "salvage_data"
    UPLINK = "uplink"
    UNAVAILABLE = "unavailable"


class Role(str, Enum):
    NAVIGATION = "navigation"
    INFORMATION = "information"
    BOTH = "navigation_and_information"


@dataclass(frozen=True, slots=True)
class Dependency:
    code: str
    implemented: bool
    available_now: bool | None = None


@dataclass(frozen=True, slots=True)
class SearchBudget:
    """Technical work bounds per search pass, never a gameplay stage limit."""
    expansions: int = 512
    edges: int = 1024
    sector_samples: int = 256
    connector_nodes: int = 256
    labels: int = 512

    def __post_init__(self):
        if any(type(value) is not int or value <= 0
               for value in (self.expansions, self.edges, self.sector_samples,
                             self.connector_nodes, self.labels)):
            raise ValueError("Search budgets must be positive integers")


@dataclass(frozen=True, slots=True)
class SearchReport:
    expansions: int = 0
    edges: int = 0
    sector_queries: int = 0
    candidate_sectors: tuple[str, ...] = ()
    exhausted: tuple[str, ...] = ()
    domain: str = "existing_graph_then_straight_and_3d_corridor_samples"


@dataclass(frozen=True, slots=True)
class MaterializationCheck:
    """Read-only evidence; passed checks do not grant insertion permission."""
    code: str
    status: str  # checked, conditional, inadmissible


@dataclass(frozen=True, slots=True)
class PlanningContext:
    key: str = "deadnode"
    allow_new_nodes: bool = True
    budget: SearchBudget = SearchBudget()


@dataclass(frozen=True, slots=True)
class ProposedNode:
    node_id: str
    kind: str | None
    position_ly: tuple[float, float, float]
    region: str
    sector_id: str
    archetype: str | None
    existing: bool
    procedural_eligible: bool
    materialization: Materialization
    selection_reasons: tuple[str, ...]
    dependencies: tuple[Dependency, ...] = ()
    slot_index: int | None = None
    checks: tuple[MaterializationCheck, ...] = ()


@dataclass(frozen=True, slots=True)
class Hint:
    mechanism: Mechanism
    source_id: str
    destination_id: str
    source_ref: str | None = None
    requires_preparation: bool = False
    dependencies: tuple[Dependency, ...] = ()
    restrictions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Hop:
    from_id: str
    to_id: str
    distance_ly: float
    hint: Hint


@dataclass(frozen=True, slots=True)
class Stage:
    node: ProposedNode
    role: Role
    next_hint: Hint | None


@dataclass(frozen=True, slots=True)
class RecoveryProposal:
    """An unconfirmed value, never an active/persisted recovery plan."""
    opportunity_id: str
    target_id: str
    origin_id: str | None
    stages: tuple[Stage, ...]
    hops: tuple[Hop, ...]
    geometry_valid: bool
    physical_chain_valid: bool
    information_status: InformationStatus
    materialization: Materialization
    viability: Viability
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    origin_access_path: tuple[str, ...] = ()
    search: SearchReport = SearchReport()

    @property
    def new_nodes(self) -> tuple[ProposedNode, ...]:
        return tuple(stage.node for stage in self.stages if not stage.node.existing)

    @property
    def reused_nodes(self) -> tuple[str, ...]:
        return tuple(stage.node.node_id for stage in self.stages if stage.node.existing)

    @property
    def ready_with_existing_mechanics(self) -> bool:
        return self.viability == Viability.VERIFIED


# Engine.SalvageData rejects waystation, despite lore's broader channel filter.
# Uplink's kind gate is in exploration_recovery.uplink_blocked_reason.
def information_capabilities(kind: str) -> tuple[Mechanism, ...]:
    capabilities = []
    if kind in {"station", "ship", "derelict", "relay"}:
        capabilities.append(Mechanism.SALVAGE_DATA)
    if kind in {"station", "relay", "waystation"}:
        capabilities.append(Mechanism.UPLINK)
    return tuple(capabilities)


def _digest(*parts: object) -> str:
    return hashlib.blake2b(repr(parts).encode("utf-8"), digest_size=12).hexdigest().upper()


def _position(node: SpaceNode) -> tuple[float, float, float]:
    return node.x_ly, node.y_ly, node.z_ly


def _distance(left: ProposedNode, right: ProposedNode) -> float:
    return math.dist(left.position_ly, right.position_ly)


def _known(state: GameState) -> set[str]:
    return set(state.world.known_nodes) | set(state.world.known_contacts) | set(state.world.known_intel)


def _origin_paths(state: GameState) -> dict[str, tuple[str, ...]]:
    component = reachable_known_nodes(state.world, state.world.current_node_id)
    # A raw, physically valid record is not a license to traverse unknown nodes.
    permitted = set(state.world.known_nodes) | set(state.world.known_intel) | {state.world.current_node_id}
    reached = {state.world.current_node_id} & component
    paths = {nid: (nid,) for nid in reached}
    queue = sorted(reached)
    for node_id in queue:
        for dest in sorted(reachable_from(state.world, node_id) & permitted & component):
            if dest not in reached:
                reached.add(dest)
                paths[dest] = paths[node_id] + (dest,)
                queue.append(dest)
    return paths


def _existing(node: SpaceNode, state: GameState) -> ProposedNode:
    pos = _position(node)
    sid = sector_id_for_pos(*pos)
    sector = state.world.sector_states.get(sid)
    return ProposedNode(node.node_id, node.kind, pos, region_for_pos(*pos), sid,
                        sector.archetype if sector else None, True, True,
                        Materialization.EXISTING, ("existing_physical_node",))


def _intel_sources(state: GameState) -> dict[tuple[str, str], str]:
    sources = {}
    for item in state.world.intel:
        if item.kind == "link":
            sources.setdefault((item.from_id, item.to_id), item.intel_id)
    # Only already stored ship files, never unopened pools, authorize this path.
    for path, file in sorted(state.os.fs.items()):
        if file.is_corrupted:
            continue
        try:
            content = read_file(state.os.fs, path, state.os.auth_levels)
        except (PermissionError, IsADirectoryError):
            continue
        for line in content.splitlines():
            if line.strip().upper().startswith("LINK:"):
                parts = line.split(":", 1)[1].strip().split("->")
                if len(parts) == 2:
                    sources.setdefault(tuple(p.strip() for p in parts), path)
    return sources


def _hint(state: GameState, left: ProposedNode, right: ProposedNode, first: bool,
          sources: dict[tuple[str, str], str], routes: dict[str, set[str]], known: set[str]) -> Hint:
    a, b = left.node_id, right.node_id
    travel_known = b in state.world.known_nodes or b in state.world.known_intel
    recorded_route = left.existing and right.existing and b in routes.get(a, ())
    if recorded_route and travel_known:
        return Hint(Mechanism.KNOWN_ROUTE, a, b)
    ref = sources.get((a, b))
    if ref:
        return Hint(Mechanism.EXISTING_INTEL, a, b, ref,
                    dependencies=(Dependency("read_import_intel", True, True),))
    if right.existing and b in known and not (recorded_route and not travel_known) and _distance(left, right) <= state.ship.sensors_range_ly:
        sensors = state.ship.systems.get("sensors")
        usable = bool(sensors and sensors.state in {SystemState.LIMITED, SystemState.NOMINAL, SystemState.UPGRADED})
        service = bool(sensors and sensors.service and sensors.service.is_running)
        return Hint(Mechanism.ROUTE_SOLVE, a, b, dependencies=(
            Dependency("sensors_limited", True, usable), Dependency("sensord", True, service),
            Dependency("normal_route_power_and_ship_gates", True, None),
        ))
    if first:
        return Hint(Mechanism.RECOVERY_SIGNAL, state.ship.ship_id, b,
                    source_ref=state.world.current_node_id, requires_preparation=True,
                    dependencies=(Dependency("comms", False), Dependency("radiod", False),
                                  Dependency("progressive_capture_import", False)),
                    restrictions=("first_clue_aboard_ship", "no_retroactive_file_at_origin"))
    pool = state.world.node_pools.get(a) if left.existing else None
    fresh = not left.existing or bool(pool and a not in state.world.visited_nodes
                                     and pool.window_open and not pool.node_cleaned)
    restrictions = ("unvisited_receiver", "open_window", "no_consumed_source_reopened",
                    "prepare_before_first_visit", "normal_ship_and_operator_gates")
    if fresh:
        capabilities = information_capabilities(left.kind or "")
        if Mechanism.SALVAGE_DATA in capabilities and (not left.existing or not pool.data_complete):
            return Hint(Mechanism.SALVAGE_DATA, a, b, requires_preparation=True,
                        dependencies=(Dependency("dock", True),
                                      Dependency("drone_available_for_deployment", True, bool(state.ship.drones)),
                                      Dependency("deployed_drone_at_node", True),
                                      Dependency("drone_battery", True), Dependency("pool_data_source", True)),
                        restrictions=restrictions)
        if Mechanism.UPLINK in capabilities and (not left.existing or not pool.uplink_data_consumed):
            return Hint(Mechanism.UPLINK, a, b, requires_preparation=True,
                        dependencies=(Dependency("dock", True), Dependency("data_core_limited", True),
                                      Dependency("datad", True), Dependency("unconsumed_uplink", True),
                                      Dependency("uplink_hint_reservation_policy", False)),
                        restrictions=restrictions)
    return Hint(Mechanism.UNAVAILABLE, a, b, restrictions=("no_eligible_information_source",))


def _chain_cost_rank(cost, objective: str):
    new, hops, distance, ids = cost
    if objective == "distance":
        return distance, hops, new, ids
    if objective == "hops":
        return hops, distance, new, ids
    return cost


class _Planner:
    """Call-local queries, caches and reservations; writes no persistent state."""

    def __init__(self, state: GameState, opportunity_id: str, budget: SearchBudget):
        self.state = state
        self.sources = _intel_sources(state)
        self.routes = {nid: reachable_from(state.world, nid) for nid in sorted(state.world.known_links)}
        self.known = _known(state)
        self.budget = budget
        self.expansions = self.edges = 0
        self.exhausted: set[str] = set()
        self.candidate_sectors: list[str] = []
        world = state.world
        self.claimed_ids = (set(world.space.nodes) | world.known_nodes | world.known_contacts
                            | set(world.known_intel) | world.forced_hidden_nodes | world.visited_nodes
                            | set(world.node_pools) | set(world.dead_nodes)
                            | set(world.lore_placements.piece_to_node.values()))
        for adjacency in (world.known_links, world.space.edges):
            self.claimed_ids.update(adjacency)
            for destinations in adjacency.values():
                self.claimed_ids.update(destinations)
        for node in world.space.nodes.values():
            self.claimed_ids.update(node.links)
        for sector in world.sector_states.values():
            self.claimed_ids.update(sector.node_ids)
            self.claimed_ids.update(n for n in (sector.playable_hub_node_id, sector.topology_hub_node_id) if n)
        for item in world.intel:
            self.claimed_ids.update(n for n in (item.from_id, item.to_id) if n)
        for pair in self.sources:
            self.claimed_ids.update(pair)
        for tracked in world.dead_nodes.values():
            if tracked.bridge_node_id:
                self.claimed_ids.add(tracked.bridge_node_id)
        self.occupied = {_position(n) for n in world.space.nodes.values()}
        self.by_sector: dict[str, dict[str, SpaceNode]] = {}
        for nid, node in sorted(state.world.space.nodes.items()):
            if all(math.isfinite(v) for v in _position(node)):
                self.by_sector.setdefault(sector_id_for_pos(*_position(node)), {})[nid] = node
        self.opportunity_id = opportunity_id
        self.templates = load_worldgen_templates()
        self.archetypes = load_worldgen_archetypes()
        self.slots: dict[str, tuple[str, str, tuple[str, ...]]] = {}
        self.hints: dict[tuple[ProposedNode, ProposedNode, bool], Hint] = {}
        self.spatial_indexes: dict[int, dict[tuple[int, int, int], list[str]]] = {}
        self.physical_components: dict[tuple[int, str], set[str]] = {}

    def proposed_id(self, prefix: str, edge_key: tuple[str, str], index: int,
                    pos: tuple[float, float, float], reserved_ids: set[str]) -> str:
        for nonce in count():
            node_id = f"{prefix}_{_digest(self.opportunity_id, edge_key, index, pos, nonce)}"
            if node_id not in self.claimed_ids and node_id not in reserved_ids:
                return node_id

    def sector_slots(self, sid: str) -> tuple[str, str, tuple[str, ...]]:
        if sid not in self.slots:
            region = region_for_pos(*_sector_center(sid))
            sector = self.state.world.sector_states.get(sid)
            archetype = sector.archetype if sector and sector.archetype else _select_archetype(
                self.state, sid, region, self.templates)
            cfg = self.archetypes.get(archetype)
            allowed = self.templates.get(region, {}).get("archetype_weights", {})
            kinds: tuple[str, ...] = ()
            if cfg and float(allowed.get(archetype, 0)) > 0:
                # The canonical query only reads meta.seed and this sector's
                # physical nodes. A detached indexed view avoids O(world) per slot.
                view = SimpleNamespace(meta=self.state.meta, world=SimpleNamespace(
                    space=SimpleNamespace(nodes=self.by_sector.get(sid, {}))))
                planned, _ = _plan_sector_kinds(view, sid, archetype, region,
                                               self.templates[region], cfg)
                kinds = tuple(planned)
            self.slots[sid] = region, archetype, kinds
        return self.slots[sid]

    def report(self) -> SearchReport:
        return SearchReport(self.expansions, self.edges, len(self.slots),
                            tuple(self.candidate_sectors), tuple(sorted(self.exhausted)))

    def new_node(self, pos: tuple[float, float, float], edge_key: tuple[str, str], index: int,
                 used: tuple[tuple[str, int], ...], occupied: set[tuple[float, float, float]],
                 reserved_ids: set[str]) -> ProposedNode:
        sid = sector_id_for_pos(*pos)
        region, archetype, kinds = self.sector_slots(sid)
        cfg = self.archetypes.get(archetype, {})
        choices = [(slot, kind) for slot, kind in enumerate(kinds) if (sid, slot) not in used
                   and kind not in cfg.get("forbidden_kinds", [])
                   and kind in {"relay", "station", "waystation", "derelict", "ship"}]
        reasons = [f"canonical_sector_archetype:{archetype}", "canonical_slot_order"]
        actual_region = region_for_pos(*pos)
        if float(self.templates.get(actual_region, {}).get("archetype_weights", {}).get(archetype, 0)) <= 0:
            choices = []
            reasons.append("archetype_not_admitted_at_position")
        if pos in occupied:
            choices = []
            reasons.append("position_already_occupied")
        if not choices:
            return ProposedNode(self.proposed_id("UNRESOLVED", edge_key, index, pos, reserved_ids),
                                None, pos, region_for_pos(*pos), sid, archetype, False, False,
                                Materialization.UNAVAILABLE, tuple(reasons + ["no_admissible_procedural_slot"]),
                                checks=(MaterializationCheck("coordinates_unique", "inadmissible" if pos in occupied else "checked"),
                                        MaterializationCheck("canonical_capacity", "inadmissible")))
        slot, kind = choices[0]
        node_id = self.proposed_id("WRECK" if kind == "ship" else kind.upper(),
                                   edge_key, index, pos, reserved_ids)
        sector = self.state.world.sector_states.get(sid)
        late = bool(sector and sector.internal_links_built)
        dependencies = [Dependency("atomic_idempotent_materialization", False),
                        Dependency("coordinate_slot_insertion_policy", False),
                        Dependency("late_sector_topology" if late else "lazy_sector_slot_reservation", False),
                        Dependency("pool_preparation_before_revelation", False)]
        if not self.state.world.sparse_guardrail_done:
            dependencies.append(Dependency("pending_initial_guardrail_context", False))
        if sid in self.state.world.generated_sectors or sector:
            dependencies.append(Dependency("generated_sector_insertion_policy", False))
        sector_nodes = self.by_sector.get(sid, {})
        if sector and ((sector.region and sector.region != region)
                       or (sector.sector_id and sector.sector_id != sid)
                       or set(sector.node_ids) != set(sector_nodes)):
            dependencies.append(Dependency("sector_metadata_reconciliation", False))
        if set(sector_nodes) & self.state.world.visited_nodes:
            dependencies.append(Dependency("explored_sector_appearance_policy", False))
        if region_for_pos(*pos) != region:
            dependencies.append(Dependency("sector_boundary_region_policy", False))
        checks = tuple(MaterializationCheck(code, "checked") for code in (
            "identity_unique", "coordinates_unique", "sector_membership", "regional_archetype",
            "canonical_kind_capacity", "proposal_slot_reserved")) + tuple(
                MaterializationCheck(d.code, "conditional") for d in dependencies)
        reasons += [f"canonical_slot:{slot}", f"information_capabilities:{','.join(m.value for m in information_capabilities(kind))}"]
        return ProposedNode(node_id, kind, pos, region_for_pos(*pos), sid, archetype,
                            False, True, Materialization.CONDITIONAL, tuple(reasons),
                            tuple(dependencies), slot, checks)

    def connector(self, left: ProposedNode, right: ProposedNode, first: bool,
                  used: tuple[tuple[str, int], ...], path: tuple[ProposedNode, ...],
                  allow_new: bool, geometry_only: bool = False):
        distance = _distance(left, right)
        if distance <= 0 or not math.isfinite(distance):
            return None
        segments = max(1, math.ceil(distance / float(Balance.MAX_ROUTE_HOP_LY)))
        if segments - 1 > self.budget.connector_nodes:
            self.exhausted.add("connector_nodes")
            return None
        if segments > 1 and not allow_new:
            return None
        nodes = []
        reservations = list(used)
        occupied = self.occupied | {n.position_ly for n in path} if segments > 1 else set()
        ids = {n.node_id for n in path} if segments > 1 else set()
        for index in range(1, segments):
            pos = tuple(a + (b - a) * (index / segments)
                        for a, b in zip(left.position_ly, right.position_ly))
            node = self.new_node(pos, (left.node_id, right.node_id), index,
                                 tuple(reservations), occupied, ids)
            if not node.procedural_eligible and not geometry_only:
                return None
            nodes.append(node)
            ids.add(node.node_id)
            occupied.add(pos)
            if node.slot_index is not None:
                reservations.append((node.sector_id, node.slot_index))
        nodes.append(right)
        hops = []
        previous = left
        for index, node in enumerate(nodes):
            dist = _distance(previous, node)
            # Reuse the F-ROUTE-01 predicate on a tiny, detached physical view.
            # Existing/virtual endpoints are never inserted in the live world.
            view = WorldState()
            for endpoint in (previous, node):
                x, y, z = endpoint.position_ly
                view.space.nodes[endpoint.node_id] = SpaceNode(endpoint.node_id, endpoint.node_id,
                                                               endpoint.kind or "", x_ly=x, y_ly=y, z_ly=z)
            if dist <= 0 or not is_hop_within_cap(view, previous.node_id, node.node_id):
                return None
            hint_key = previous, node, first and index == 0
            if hint_key not in self.hints:
                self.hints[hint_key] = _hint(self.state, *hint_key, self.sources, self.routes, self.known)
            hint = self.hints[hint_key]
            if hint.mechanism == Mechanism.UNAVAILABLE and not geometry_only:
                return None
            hops.append(Hop(previous.node_id, node.node_id, dist, hint))
            previous = node
        return tuple(nodes), tuple(hops), tuple(sorted(reservations))

    def corridor_candidates(self, nodes: dict[str, ProposedNode], origins: tuple[str, ...],
                            target: str) -> dict[str, ProposedNode]:
        """Finite sampled corridors, not a new procedural placement distribution.

        Sector centers are geometric probes only. Their insertion remains conditional.
        Round-robin origins and widths prevent one long line starving every detour.
        """
        def corridor(origin: str, width: float):
            left, right = nodes[origin], nodes[target]
            delta = tuple(b-a for a, b in zip(left.position_ly, right.position_ly))
            length = math.hypot(*delta)
            if not math.isfinite(length) or length <= 0:
                return
            direction = tuple(v / length for v in delta)
            axis = min(range(3), key=lambda i: (abs(direction[i]), i))
            unit = tuple(float(i == axis) for i in range(3))
            cross = (direction[1]*unit[2]-direction[2]*unit[1],
                     direction[2]*unit[0]-direction[0]*unit[2],
                     direction[0]*unit[1]-direction[1]*unit[0])
            norm = math.hypot(*cross)
            u = tuple(v/norm for v in cross)
            v = (direction[1]*u[2]-direction[2]*u[1],
                 direction[2]*u[0]-direction[0]*u[2],
                 direction[0]*u[1]-direction[1]*u[0])
            steps = max(2, math.ceil(length / (Balance.MAX_ROUTE_HOP_LY / 2)))
            for step in range(1, steps):
                base = tuple(a + d*step/steps for a, d in zip(left.position_ly, delta))
                for a, b in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1),
                             (1, 1), (-1, 1), (1, -1), (-1, -1)):
                    yield sector_id_for_pos(*(base[i]+width*(a*u[i]+b*v[i]) for i in range(3)))
        streams = [iter(corridor(origin, width)) for width in (10.0, 20.0, 40.0)
                   for origin in origins]
        result: dict[str, ProposedNode] = {}
        seen: set[str] = set()
        # Bound raw samples too: overlapping corridors must not cause unbounded work.
        samples = 0
        while streams:
            pending = []
            for stream in streams:
                if samples >= self.budget.sector_samples:
                    self.exhausted.add("sector_samples")
                    return result
                try:
                    sid = next(stream)
                except StopIteration:
                    continue
                samples += 1
                pending.append(stream)
                if sid in seen:
                    continue
                seen.add(sid)
                self.candidate_sectors.append(sid)
                pos = _sector_center(sid)
                node = self.new_node(pos, ("corridor", sid), 0, (), self.occupied, set())
                if node.procedural_eligible:
                    result[node.node_id] = node
            streams = pending
        return result

    @staticmethod
    def cell(pos: tuple[float, float, float]) -> tuple[int, int, int]:
        return tuple(math.floor(v / Balance.MAX_ROUTE_HOP_LY) for v in pos)

    def search(self, nodes: dict[str, ProposedNode], origins: tuple[str, ...], target: str,
               allow_new: bool, geometry_only: bool = False,
               access_paths: dict[str, tuple[str, ...]] | None = None,
               objective: str = "geometry",
               access_distances: dict[str, float] | None = None):
        # The geometric API retains its original ranking. Contextual callers
        # seed real access costs and sample two additional practical objectives.
        def rank(cost):
            return _chain_cost_rank(cost, objective)
        graph = dict(nodes)
        if allow_new and not geometry_only:
            graph.update(self.corridor_candidates(nodes, origins, target))
        graph_key = id(nodes)  # session-owned immutable input, never a global cache
        if graph_key not in self.spatial_indexes:
            physical_index: dict[tuple[int, int, int], list[str]] = {}
            for nid, node in sorted(nodes.items()):
                physical_index.setdefault(self.cell(node.position_ly), []).append(nid)
            self.spatial_indexes[graph_key] = physical_index
        index = self.spatial_indexes[graph_key]
        if allow_new and not geometry_only:
            index = {cell: list(ids) for cell, ids in index.items()}
            for nid in sorted(set(graph)-set(nodes)):
                index.setdefault(self.cell(graph[nid].position_ly), []).append(nid)
        # Reverse physical component gives an admissible lower bound on new
        # intermediaries: outside one hop, at least one new stop is needed.
        # Do not use ceil(gap/cap)-1: another existing component can carry the
        # ship much closer at no new-node cost. Ignore information only here.
        component_key = graph_key, target
        if component_key not in self.physical_components:
            component = {target}
            todo = [target]
            for nid in todo:
                if len(component) > self.budget.expansions:
                    component = set(nodes)  # conservative bound when prepass is large
                    break
                cell = self.cell(nodes[nid].position_ly)
                for offset in product(range(-1, 2), repeat=3):
                    for other in index.get(tuple(a+b for a, b in zip(cell, offset)), ()):
                        if other in nodes and other not in component and _distance(nodes[nid], nodes[other]) <= Balance.MAX_ROUTE_HOP_LY:
                            component.add(other)
                            todo.append(other)
            self.physical_components[component_key] = component
        component = self.physical_components[component_key]
        lower_bounds = {}
        def priority(cost, node):
            if node.node_id not in lower_bounds:
                gap = 0.0 if node.node_id in component else min(_distance(node, nodes[n]) for n in component)
                direct = _distance(node, nodes[target])
                lower_bounds[node.node_id] = (
                    int(gap > Balance.MAX_ROUTE_HOP_LY) if math.isfinite(gap) else 0,
                    math.ceil(direct / Balance.MAX_ROUTE_HOP_LY) if math.isfinite(direct) else 0, direct)
            extra, hop_bound, distance_bound = lower_bounds[node.node_id]
            return rank((cost[0]+extra, cost[1]+hop_bound, cost[2]+distance_bound, cost[3]))
        queue = []
        serial = count()
        best = {}
        endpoint_best = {}
        for origin in origins:
            access = access_paths[origin] if access_paths is not None else (origin,)
            access_distance = (access_distances[origin] if access_distances is not None else
                               math.fsum(math.dist(_position(self.state.world.space.nodes[a]),
                                                   _position(self.state.world.space.nodes[b]))
                                         for a, b in zip(access, access[1:])))
            cost = (0, len(access)-1, access_distance, access if access_paths is not None else (origin,))
            heapq.heappush(queue, (priority(cost, nodes[origin]), next(serial), cost, origin, (), (nodes[origin],), ()))
            best[origin, ()] = cost
            endpoint_best.setdefault(origin, {})[()] = cost
        expansions = edges = 0
        incumbent = None
        incumbent_cost = None
        while queue:
            _, _, cost, current, used, path, hops = heapq.heappop(queue)
            if cost != best.get((current, used)):
                continue
            if current == target:
                return path, hops
            if expansions >= self.budget.expansions:
                self.exhausted.add("expansions")
                return incumbent
            expansions += 1
            self.expansions += 1
            left = path[-1]
            cell = self.cell(left.position_ly)
            nearby = {nid for offset in product(range(-1, 2), repeat=3)
                      for nid in index.get(tuple(a+b for a, b in zip(cell, offset)), ())
                      if 0 < math.dist(left.position_ly, graph[nid].position_ly) <= Balance.MAX_ROUTE_HOP_LY}
            destinations = set(nearby)
            if allow_new and left.existing:
                # Straight connectors to the target and nearest existing endpoints
                # in a two-hop neighborhood. This is a sampled search domain,
                # not a maximum chain length or a universe connectivity guarantee.
                local = {nid for offset in product(range(-2, 3), repeat=3)
                         for nid in index.get(tuple(a+b for a, b in zip(cell, offset)), ())
                         if graph[nid].existing and nid != current}
                nearest = sorted(local, key=lambda n: (_distance(left, graph[n]), n))[:16]
                destinations.update(nearest)
                destinations.add(target)
            path_ids = {n.node_id for n in path}
            path_positions = {n.position_ly for n in path}
            for dest in sorted(destinations):
                if dest in path_ids:
                    continue
                if edges >= self.budget.edges:
                    self.exhausted.add("edges")
                    return incumbent
                edges += 1
                self.edges += 1
                node = graph[dest]
                if not node.existing:
                    if node.position_ly in path_positions:
                        continue
                    node = self.new_node(node.position_ly, ("corridor", node.sector_id), 0,
                                         used, self.occupied, path_ids)
                    if not node.procedural_eligible:
                        continue
                edge = self.connector(left, node, not hops, used, path,
                                      allow_new and left.existing and node.existing, geometry_only)
                if edge is None:
                    continue
                added_nodes, added_hops, reservations = edge
                if not node.existing:
                    reservations = tuple(sorted((*reservations, (node.sector_id, node.slot_index))))
                new_cost = (cost[0] + sum(not n.existing for n in added_nodes),
                            cost[1] + len(added_hops),
                            cost[2] + sum(h.distance_ly for h in added_hops),
                            cost[3] + tuple(n.node_id for n in added_nodes))
                if dest == target and (incumbent_cost is None or rank(new_cost) < rank(incumbent_cost)):
                    incumbent = path + added_nodes, hops + added_hops
                    incumbent_cost = new_cost
                key = dest, reservations
                # Subset reservations dominate supersets at the same endpoint:
                # lower cost with more free slots cannot reduce continuation options.
                if any(set(slots).issubset(reservations) and rank(old) <= rank(new_cost)
                       for slots, old in endpoint_best.get(dest, {}).items()):
                    continue
                if len(best)-len(origins) >= self.budget.labels and key not in best:
                    self.exhausted.add("labels")
                    return incumbent
                best[key] = new_cost
                endpoint_best.setdefault(dest, {})[reservations] = new_cost
                heapq.heappush(queue, (priority(new_cost, node), next(serial), new_cost, dest, reservations,
                                       path + added_nodes, hops + added_hops))
        return None


class _ChainSession:
    """One read-only planning call; catalogs, indexes and hint/slot caches shared.

    Results contain copied immutable values. This session must never outlive the
    coherent snapshot supplied by its caller or be kept as a global cache.
    """

    def __init__(self, state: GameState, context: PlanningContext):
        self.state, self.context = state, context
        self.origin_paths = _origin_paths(state)
        self.protected = lore._locked_primary_targets(state)
        self.protection_incomplete = False
        for arc in lore.load_arcs():
            primary = arc.get("primary_intel") or {}
            placement = state.world.arc_placements.get(arc.get("arc_id", ""), {})
            primary_state = placement.get("primary")
            discovered = placement.get("discovered") or ()
            unlocked = (isinstance(primary_state, dict) and primary_state.get("unlocked")) or primary.get("id", "primary") in discovered
            if primary and not unlocked and lore._primary_target_node_id(primary) is None:
                self.protection_incomplete = True
        origins = self.origin_paths
        self.nodes = {nid: _existing(node, state) for nid, node in sorted(state.world.space.nodes.items())
                      if nid not in self.protected and all(math.isfinite(v) for v in _position(node))
                      and (node.kind not in {"origin", "transit"} or nid in origins)}
        self.planner: _Planner | None = None

    def propose(self, target_id: str, *, access_paths: dict[str, tuple[str, ...]] | None = None,
                objective: str = "geometry", augmented: bool = False,
                access_distances: dict[str, float] | None = None) -> RecoveryProposal:
        state, context = self.state, self.context
        target = state.world.space.nodes.get(target_id)
        attempts = state.world.dead_nodes.get(target_id)
        identity = "DEADNODE_" + _digest(state.meta.rng_seed, context.key,
                                        state.world.current_node_id, target_id,
                                        _position(target) if target else None,
                                        attempts.attempts if attempts else 0)
        limitations = ("proposal_only_no_activation", "no_exhaustive_spatial_search",
                       "future_materializer_must_revalidate_state")

        def reject(reason: str) -> RecoveryProposal:
            return RecoveryProposal(identity, target_id, None, (), (), False, False,
                                    InformationStatus.UNAVAILABLE, Materialization.UNAVAILABLE,
                                    Viability.REJECTED, (reason,), limitations)

        if target is None or not all(math.isfinite(v) for v in _position(target)):
            return reject("target_missing_or_nonfinite")
        if state.ship.in_transit:
            return reject("ship_in_transit")
        origin_paths = access_paths if access_paths is not None else self.origin_paths
        origins = tuple(sorted(origin_paths))
        if not origins:
            return reject("no_operational_origin")
        protected = self.protected
        if self.protection_incomplete:
            return reject("primary_protection_query_incomplete")
        if target_id in protected:
            return reject("protected_primary_target")
        if target_id not in state.world.known_contacts | state.world.forced_hidden_nodes:
            return reject("not_a_deadnode_contact")
        current_pool = state.world.node_pools.get(state.world.current_node_id)
        target_pool = state.world.node_pools.get(target_id)
        if (current_pool and current_pool.node_cleaned) or (target_pool and target_pool.node_cleaned):
            return reject("deadnode_clean_pool_gate")
        if target_id in self.origin_paths or any(math.dist(_position(state.world.space.nodes[n]), _position(target))
                                       <= Balance.SENSORS_RANGE_LY for n in self.origin_paths):
            return reject("already_connected_or_in_deadnode_sensor_range")
        nodes = self.nodes
        if target_id not in nodes:
            return reject("target_kind_ineligible")
        origins = tuple(nid for nid in origins if nid in nodes)
        if not origins:
            return reject("no_eligible_origin")
        if self.planner is None:
            self.planner = _Planner(state, identity, context.budget)
            self.planner.claimed_ids.update(protected)
        planner = self.planner
        planner.opportunity_id = identity
        planner.expansions = planner.edges = 0
        planner.exhausted.clear()
        planner.candidate_sectors.clear()
        # Existing-only behavior remains the geometric API's first choice. A
        # contextual witness may also test nearer new/mixed paths in one graph.
        costs = origin_paths if objective != "geometry" else None
        result = planner.search(nodes, origins, target_id, False,
                                access_paths=costs, objective=objective, access_distances=access_distances)
        need_augmented = result is None
        if augmented and result is not None and context.allow_new_nodes:
            path, hops = result
            access = origin_paths[path[0].node_id]
            distance = math.fsum(h.distance_ly for h in hops) + math.fsum(
                math.dist(_position(state.world.space.nodes[a]), _position(state.world.space.nodes[b]))
                for a, b in zip(access, access[1:]))
            direct = math.dist(_position(state.world.space.nodes[state.world.current_node_id]), _position(target))
            # Only skip a contextual mixed/new witness when the existing result
            # attains both physical lower bounds. No backtracking policy cutoff.
            need_augmented = not (distance == direct and len(access)-1+len(hops) == math.ceil(direct / Balance.MAX_ROUTE_HOP_LY))
        if need_augmented and context.allow_new_nodes:
            alternative = planner.search(nodes, origins, target_id, True,
                                         access_paths=costs, objective=objective, access_distances=access_distances)
            if alternative is not None:
                def quality(witness):
                    chain, chain_hops = witness
                    access = origin_paths[chain[0].node_id]
                    access_distance = math.fsum(math.dist(_position(state.world.space.nodes[a]), _position(state.world.space.nodes[b]))
                                                for a, b in zip(access, access[1:]))
                    return _chain_cost_rank((sum(not n.existing for n in chain), len(access)-1+len(chain_hops),
                        access_distance+math.fsum(h.distance_ly for h in chain_hops),
                        access+tuple(n.node_id for n in chain[1:])), objective)
                if result is None or quality(alternative) < quality(result):
                    result = alternative
        if result is None:
            # Preserve a geometric witness without mislabelling missing information
            # or undefined procedural placement as an operational opportunity.
            if not planner.exhausted:
                result = planner.search(nodes, origins, target_id, False, True,
                                        access_paths=costs, objective=objective, access_distances=access_distances)
            if result is None and context.allow_new_nodes:
                origin = min(origins, key=lambda nid: (math.dist(nodes[nid].position_ly, _position(target)), nid))
                edge = planner.connector(nodes[origin], nodes[target_id], True, (), (nodes[origin],), True, True)
                if edge:
                    result = (nodes[origin],) + edge[0], edge[1]
        if result is None:
            return RecoveryProposal(identity, target_id, None, (), (), False, False,
                                    InformationStatus.UNAVAILABLE, Materialization.UNAVAILABLE,
                                    Viability.INCOMPLETE, ("no_chain_in_sampled_domain",) + (("search_budget_exhausted",) if planner.exhausted else ()),
                                    limitations, search=planner.report())
        path, hops = result
        physical = all(n.procedural_eligible for n in path)
        unavailable = any(h.hint.mechanism == Mechanism.UNAVAILABLE for h in hops)
        future = any(not d.implemented for h in hops for d in h.hint.dependencies)
        information = (InformationStatus.UNAVAILABLE if unavailable else
                       InformationStatus.FUTURE_REQUIRED if future else InformationStatus.VERIFIED)
        materialization = (Materialization.UNAVAILABLE if not physical else
                           Materialization.CONDITIONAL if any(not n.existing for n in path) else Materialization.EXISTING)
        unavailable_now = any(d.available_now is not True for h in hops for d in h.hint.dependencies)
        viability = (Viability.INCOMPLETE if unavailable or not physical else
                     Viability.CONDITIONAL if future or unavailable_now or materialization == Materialization.CONDITIONAL
                     or any(h.hint.requires_preparation for h in hops) else Viability.VERIFIED)
        stages = tuple(Stage(node, Role.BOTH if index < len(hops) and hops[index].hint.requires_preparation
                             and hops[index].hint.mechanism != Mechanism.RECOVERY_SIGNAL else Role.NAVIGATION,
                             hops[index].hint if index < len(hops) else None)
                       for index, node in enumerate(path))
        reasons = tuple(sorted({"information_source_unavailable" for h in hops if h.hint.mechanism == Mechanism.UNAVAILABLE}
                               | {reason for n in path if not n.procedural_eligible for reason in n.selection_reasons}
                               | ({"search_budget_exhausted"} if planner.exhausted else set())
                               | ({"future_reception_required"} if future else set())
                               | ({"materialization_not_guaranteed"} if materialization != Materialization.EXISTING else set())))
        return RecoveryProposal(identity, target_id, path[0].node_id, stages, hops, True, physical,
                                information, materialization, viability, reasons, limitations,
                                origin_paths[path[0].node_id], planner.report())


def propose_deadnode_chain(state: GameState, target_id: str,
                           context: PlanningContext = PlanningContext()) -> RecoveryProposal:
    """Geometric proposal API; contextual comparison lives in deadnode_opportunities.

    Candidate timing is owned by the caller. This never activates deadnodes.
    """
    return _ChainSession(state, context).propose(target_id)
