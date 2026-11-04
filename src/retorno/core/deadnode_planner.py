"""Read-only recovery proposals. Nothing here activates or persists a plan.

Worldgen's archetype/slot queries below use local RNGs and only read state.
Its registration/generation helpers and lore's writers are deliberately absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import heapq
from itertools import count
import math

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
class PlanningContext:
    key: str = "deadnode"
    allow_new_nodes: bool = True


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


def _intel_ref(state: GameState, left: str, right: str) -> str | None:
    for item in state.world.intel:
        if item.kind == "link" and item.from_id == left and item.to_id == right:
            return item.intel_id
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
                if len(parts) == 2 and tuple(p.strip() for p in parts) == (left, right):
                    return path
    return None


def _hint(state: GameState, left: ProposedNode, right: ProposedNode, first: bool) -> Hint:
    a, b = left.node_id, right.node_id
    travel_known = b in state.world.known_nodes or b in state.world.known_intel
    recorded_route = left.existing and right.existing and b in reachable_from(state.world, a)
    if recorded_route and travel_known:
        return Hint(Mechanism.KNOWN_ROUTE, a, b)
    ref = _intel_ref(state, a, b)
    if ref:
        return Hint(Mechanism.EXISTING_INTEL, a, b, ref,
                    dependencies=(Dependency("read_import_intel", True, True),))
    if right.existing and b in _known(state) and not (recorded_route and not travel_known) and _distance(left, right) <= state.ship.sensors_range_ly:
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


class _Planner:
    """Call-local queries, caches and reservations; writes no persistent state."""

    def __init__(self, state: GameState, opportunity_id: str):
        self.state = state
        self.opportunity_id = opportunity_id
        self.templates = load_worldgen_templates()
        self.archetypes = load_worldgen_archetypes()
        self.slots: dict[str, tuple[str, str, tuple[str, ...]]] = {}
        self.hints: dict[tuple[ProposedNode, ProposedNode, bool], Hint] = {}

    def proposed_id(self, prefix: str, edge_key: tuple[str, str], index: int,
                    pos: tuple[float, float, float], reserved_ids: set[str]) -> str:
        for nonce in count():
            node_id = f"{prefix}_{_digest(self.opportunity_id, edge_key, index, pos, nonce)}"
            if node_id not in self.state.world.space.nodes and node_id not in reserved_ids:
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
                planned, _ = _plan_sector_kinds(self.state, sid, archetype, region,
                                               self.templates[region], cfg)
                kinds = tuple(planned)
            self.slots[sid] = region, archetype, kinds
        return self.slots[sid]

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
        if pos in occupied:
            choices = []
            reasons.append("position_already_occupied")
        if not choices:
            return ProposedNode(self.proposed_id("UNRESOLVED", edge_key, index, pos, reserved_ids),
                                None, pos, region_for_pos(*pos), sid, archetype, False, False,
                                Materialization.UNAVAILABLE, tuple(reasons + ["no_admissible_procedural_slot"]))
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
        reasons += [f"canonical_slot:{slot}", f"information_capabilities:{','.join(m.value for m in information_capabilities(kind))}"]
        return ProposedNode(node_id, kind, pos, region_for_pos(*pos), sid, archetype,
                            False, True, Materialization.CONDITIONAL, tuple(reasons),
                            tuple(dependencies), slot)

    def connector(self, left: ProposedNode, right: ProposedNode, first: bool,
                  used: tuple[tuple[str, int], ...], path: tuple[ProposedNode, ...],
                  allow_new: bool, geometry_only: bool = False):
        distance = _distance(left, right)
        if distance <= 0 or not math.isfinite(distance):
            return None
        segments = max(1, math.ceil(distance / float(Balance.MAX_ROUTE_HOP_LY)))
        if segments > 1 and not allow_new:
            return None
        nodes = []
        reservations = list(used)
        occupied = {_position(n) for n in self.state.world.space.nodes.values()}
        occupied.update(n.position_ly for n in path)
        ids = {n.node_id for n in path}
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
            if not is_hop_within_cap(view, previous.node_id, node.node_id):
                return None
            hint_key = previous, node, first and index == 0
            if hint_key not in self.hints:
                self.hints[hint_key] = _hint(self.state, *hint_key)
            hint = self.hints[hint_key]
            if hint.mechanism == Mechanism.UNAVAILABLE and not geometry_only:
                return None
            hops.append(Hop(previous.node_id, node.node_id, dist, hint))
            previous = node
        return tuple(nodes), tuple(hops), tuple(sorted(reservations))

    def search(self, nodes: dict[str, ProposedNode], origins: tuple[str, ...], target: str,
               allow_new: bool, geometry_only: bool = False):
        queue = []
        serial = count()
        best = {}
        for origin in origins:
            cost = (0, 0, 0.0, (origin,))
            heapq.heappush(queue, (cost, next(serial), origin, (), (nodes[origin],), ()))
            best[origin, ()] = cost
        while queue:
            cost, _, current, used, path, hops = heapq.heappop(queue)
            if cost != best.get((current, used)):
                continue
            if current == target:
                return path, hops
            for dest, node in sorted(nodes.items()):
                if dest == current:
                    continue
                edge = self.connector(nodes[current], node, not hops, used, path,
                                      allow_new, geometry_only)
                if edge is None:
                    continue
                added_nodes, added_hops, reservations = edge
                new_cost = (cost[0] + len(added_nodes) - 1, cost[1] + len(added_hops),
                            cost[2] + sum(h.distance_ly for h in added_hops),
                            cost[3] + tuple(n.node_id for n in added_nodes))
                key = dest, reservations
                if key not in best or new_cost < best[key]:
                    best[key] = new_cost
                    heapq.heappush(queue, (new_cost, next(serial), dest, reservations,
                                           path + added_nodes, hops + added_hops))
        return None


def propose_deadnode_chain(state: GameState, target_id: str,
                           context: PlanningContext = PlanningContext()) -> RecoveryProposal:
    """Calculate a proposal without changing state, RNG, catalogs or persistence.

    This is not called by evaluate_dead_nodes. Candidate eligibility is retained;
    the caller owns threshold timing and any future confirmation transaction.
    """
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
    origin_paths = _origin_paths(state)
    origins = tuple(sorted(origin_paths))
    if not origins:
        return reject("no_operational_origin")
    protected = lore._locked_primary_targets(state)
    # The canonical query cannot resolve every possible primary format. Fail
    # closed for unresolved locked primaries, without inventing narrative rules.
    for arc in lore.load_arcs():
        primary = arc.get("primary_intel") or {}
        placement = state.world.arc_placements.get(arc.get("arc_id", ""), {})
        primary_state = placement.get("primary")
        discovered = placement.get("discovered") or ()
        unlocked = (isinstance(primary_state, dict) and primary_state.get("unlocked")) or primary.get("id", "primary") in discovered
        if primary and not unlocked and lore._primary_target_node_id(primary) is None:
            return reject("primary_protection_query_incomplete")
    if target_id in protected:
        return reject("protected_primary_target")
    if target_id not in state.world.known_contacts | state.world.forced_hidden_nodes:
        return reject("not_a_deadnode_contact")
    current_pool = state.world.node_pools.get(state.world.current_node_id)
    target_pool = state.world.node_pools.get(target_id)
    if (current_pool and current_pool.node_cleaned) or (target_pool and target_pool.node_cleaned):
        return reject("deadnode_clean_pool_gate")
    if target_id in origins or any(math.dist(_position(state.world.space.nodes[n]), _position(target))
                                   <= Balance.SENSORS_RANGE_LY for n in origins):
        return reject("already_connected_or_in_deadnode_sensor_range")
    nodes = {nid: _existing(node, state) for nid, node in sorted(state.world.space.nodes.items())
             if nid not in protected and all(math.isfinite(v) for v in _position(node))
             and (node.kind not in {"origin", "transit"} or nid in origins)}
    if target_id not in nodes:
        return reject("target_kind_ineligible")
    origins = tuple(nid for nid in origins if nid in nodes)
    if not origins:
        return reject("no_eligible_origin")
    planner = _Planner(state, identity)
    result = planner.search(nodes, origins, target_id, False)
    if result is None and context.allow_new_nodes:
        result = planner.search(nodes, origins, target_id, True)
    if result is None:
        # Preserve a geometric witness without mislabelling missing information
        # or undefined procedural placement as an operational opportunity.
        result = planner.search(nodes, origins, target_id, False, True)
        if result is None and context.allow_new_nodes:
            origin = min(origins, key=lambda nid: (math.dist(nodes[nid].position_ly, _position(target)), nid))
            edge = planner.connector(nodes[origin], nodes[target_id], True, (), (nodes[origin],), True, True)
            if edge:
                result = (nodes[origin],) + edge[0], edge[1]
    if result is None:
        return RecoveryProposal(identity, target_id, None, (), (), False, False,
                                InformationStatus.UNAVAILABLE, Materialization.UNAVAILABLE,
                                Viability.INCOMPLETE, ("no_chain_in_search_family",), limitations)
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
                           | ({"future_reception_required"} if future else set())
                           | ({"materialization_not_guaranteed"} if materialization != Materialization.EXISTING else set())))
    return RecoveryProposal(identity, target_id, path[0].node_id, stages, hops, True, physical,
                            information, materialization, viability, reasons, limitations,
                            origin_paths[path[0].node_id])
