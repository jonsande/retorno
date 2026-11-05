"""Pure contextual comparison of deadnode proposals, never production activation.

No weighted score or economic simulation: practical conflicts remain alternatives.
All caches and technical work limits belong to one coherent input snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import heapq
import math
from types import SimpleNamespace
from typing import Iterable

from retorno.config.balance import Balance
from retorno.core.deadnode_planner import (
    Dependency, InformationStatus, Mechanism, PlanningContext,
    ProposedNode, RecoveryProposal, Viability, _ChainSession, _Planner, _digest, _existing,
    _hint, _position,
)
from retorno.core.gamestate import GameState
from retorno.core.power_policy import is_critical_power_state
from retorno.model.systems import SystemState
from retorno.model.world import SpaceNode, WorldState, is_hop_within_cap, reachable_from, region_for_pos, sector_id_for_pos


class EstimateStatus(str, Enum):
    CALCULABLE = "calculable"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class OpportunityStatus(str, Enum):
    VERIFIED_MECHANICS = "verified_mechanics"
    CONDITIONAL = "conditional"
    UNUSABLE = "unusable"


@dataclass(frozen=True, slots=True)
class Estimate:
    value: float | None
    unit: str
    status: EstimateStatus
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TravelCosts:
    nominal_transit_s: Estimate
    steady_cruise_load_kwh: Estimate
    steady_cruise_generation_kwh: Estimate
    direct_travel_scrap: Estimate
    future_repair_scrap: Estimate
    future_salvage_scrap: Estimate
    economic_feasibility: EstimateStatus
    unknown_risks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccessRoute:
    path: tuple[str, ...]
    distance_ly: float
    nominal_transit_s: float | None
    criterion: str

    @property
    def hops(self) -> int:
        return max(0, len(self.path)-1)


@dataclass(frozen=True, slots=True)
class TerritoryEvidence:
    node_id: str
    sector_id: str
    region: str
    proposed: bool
    node_known: bool
    contact_detected: bool
    visited: bool
    completed: bool | None
    sector_generated: bool
    sector_intel_known: bool
    sector_has_detected_node: bool
    sector_has_visited_node: bool
    region_has_visited_node: bool
    sensor_coverage: str = "not_recorded"


@dataclass(frozen=True, slots=True)
class OpportunityEvaluation:
    evaluation_id: str
    proposal: RecoveryProposal
    current_node_id: str
    current_position_ly: tuple[float, float, float]
    origin_id: str | None
    access_path: tuple[str, ...]
    alternative_access_routes: tuple[AccessRoute, ...]
    access_valid: bool
    access_hops: int | None
    access_distance_ly: float | None
    chain_hops: int
    chain_distance_ly: float
    total_hops: int | None
    total_distance_ly: float | None
    euclidean_to_target_ly: float | None
    reused_nodes: tuple[str, ...]
    new_nodes: tuple[str, ...]
    known_hops: int
    territory: tuple[TerritoryEvidence, ...]
    frontier_signals: tuple[str, ...]
    dependencies: tuple[Dependency, ...]
    pending_dependencies: tuple[str, ...]
    unavailable_now: tuple[str, ...]
    costs: TravelCosts
    status: OpportunityStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpportunityComparison:
    left_id: str
    right_id: str
    preferred_id: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpportunityBudget:
    targets: int = 8
    access_expansions: int = 16384
    access_edges: int = 65536
    comparisons: int = 4096

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (
                self.targets, self.access_expansions, self.access_edges, self.comparisons)):
            raise ValueError("Opportunity budgets must be positive integers")


@dataclass(frozen=True, slots=True)
class OpportunitySelection:
    evaluations: tuple[OpportunityEvaluation, ...]
    preferred_ids: tuple[str, ...]
    comparisons: tuple[OpportunityComparison, ...]
    omitted_targets: tuple[str, ...]
    access_expansions: int
    access_edges: int
    complete_within_sampled_family: bool
    limitations: tuple[str, ...]


class _OpportunityContext:
    def __init__(self, state: GameState, context: PlanningContext, budget: OpportunityBudget):
        # These Engine helpers only read state. Do not call tick/apply_action,
        # power-quality (which writes deficit_ratio), or generation from here.
        from retorno.core.engine import Engine
        self.engine = Engine()
        self.state, self.context, self.budget = state, context, budget
        self.session = _ChainSession(state, context)
        world = state.world
        self.routes = {n: reachable_from(world, n) for n in sorted(world.known_links)}
        self.edges: dict[str, tuple[str, ...]] = {}
        finite_nodes = {n for n, node in world.space.nodes.items() if all(math.isfinite(v) for v in _position(node))}
        permitted = set(self.session.origin_paths) & finite_nodes
        self.physical = dict(self.session.nodes)
        self.physical.update((n, _existing(world.space.nodes[n], state))
                             for n in sorted(permitted-set(self.physical)))
        for n in sorted(permitted):
            self.edges[n] = tuple(d for d in sorted(self.routes.get(n, set()) & permitted)
                                  if math.dist(_position(world.space.nodes[n]), _position(world.space.nodes[d])) > 0)
        self.edge_times: dict[tuple[ProposedNode, ProposedNode], float | None] = {}
        self.access_expansions = self.access_edges = 0
        self.exhausted: set[str] = set()
        self.access_maps: dict[str, dict[str, AccessRoute]] = {}
        for criterion in ("distance", "hops", "time"):
            self.access_maps[criterion] = self._access(criterion)
        self.visited_sectors = {sector_id_for_pos(*_position(world.space.nodes[n]))
                                for n in world.visited_nodes if n in finite_nodes}
        self.visited_regions = {region_for_pos(*_position(world.space.nodes[n])) for n in world.visited_nodes if n in finite_nodes}
        self.detected_sectors = {sector_id_for_pos(*_position(world.space.nodes[n]))
                                for n in world.known_nodes | world.known_contacts | set(world.known_intel)
                                if n in finite_nodes}
        self.sector_intel = {n for n, info in world.known_intel.items() if info.get("sector")}
        self.sector_intel.update(item.sector_id for item in world.intel if item.kind == "sector" and item.sector_id)
        systems = {sid: replace(system, state=SystemState.OFFLINE, forced_offline=True)
                   if sid in {"sensors", "security", "data_core", "drone_bay"} else system
                   for sid, system in state.ship.systems.items()}
        view = SimpleNamespace(ship=replace(state.ship, op_mode="CRUISE", systems=systems),
                               jobs=SimpleNamespace(jobs={}))
        self.cruise_load_kw = self.engine._compute_load_kw(view)
        self.generation_kw = self.engine._compute_p_gen(view)

    def duration(self, left: ProposedNode, right: ProposedNode) -> float | None:
        key = left, right
        if key not in self.edge_times:
            distance = math.dist(left.position_ly, right.position_ly)
            speed = self.state.ship.cruise_speed_ly_per_year
            if not math.isfinite(speed) or not math.isfinite(distance):
                duration = None
            elif left.sector_id == right.sector_id and distance <= Balance.LOCAL_TRAVEL_RADIUS_LY:
                fine = self.state.world.fine_ranges_km.get(right.node_id)
                if fine is None:
                    fine = self.engine._compute_fine_range_km(self.state, left.node_id, right.node_id)
                duration = fine / max(0.1, Balance.LOCAL_TRAVEL_SPEED_KM_S)
            else:
                duration = distance / max(0.001, speed) * Balance.YEAR_S
            self.edge_times[key] = duration if duration is not None and math.isfinite(duration) and duration >= 0 else None
        return self.edge_times[key]

    def _access(self, criterion: str) -> dict[str, AccessRoute]:
        current = self.state.world.current_node_id
        if current not in self.edges:
            return {}
        def rank(distance, hops, duration, path):
            if criterion == "hops":
                return hops, distance, duration, path
            if criterion == "time":
                return duration, distance, hops, path
            return distance, hops, duration, path
        queue = [(rank(0.0, 0, 0.0, (current,)), current, (current,), 0.0, 0.0)]
        best = {current: queue[0][0]}
        result = {}
        while queue:
            priority, nid, path, distance, duration = heapq.heappop(queue)
            if priority != best[nid]:
                continue
            if self.access_expansions >= self.budget.access_expansions:
                self.exhausted.add("access_expansions")
                break
            self.access_expansions += 1
            result[nid] = AccessRoute(path, distance, duration if math.isfinite(duration) else None, criterion)
            for dest in self.edges[nid]:
                if self.access_edges >= self.budget.access_edges:
                    self.exhausted.add("access_edges")
                    return result
                self.access_edges += 1
                left = self.physical[nid]
                right = self.physical[dest]
                length = math.dist(left.position_ly, right.position_ly)
                seconds = self.duration(left, right)
                new_distance = distance + length
                new_duration = duration + seconds if seconds is not None else math.inf
                new_path = path + (dest,)
                cost = rank(new_distance, len(new_path)-1, new_duration, new_path)
                if dest not in best or cost < best[dest]:
                    best[dest] = cost
                    heapq.heappush(queue, (cost, dest, new_path, new_distance, new_duration))
        return result

    def access_alternatives(self, origin: str | None) -> tuple[AccessRoute, ...]:
        paths = {}
        for routes in self.access_maps.values():
            if origin in routes:
                route = routes[origin]
                paths.setdefault(route.path, route)
        return tuple(paths[path] for path in sorted(paths))

    def costs(self, duration: float | None) -> TravelCosts:
        assumptions = ("current_speed_held_constant", "normal_travel_timing_only", "no_stops_or_jobs")
        nominal = Estimate(duration, "s", EstimateStatus.CONDITIONAL if duration is not None else EstimateStatus.UNKNOWN, assumptions)
        def energy(power):
            value = power * duration / 3600 if duration is not None and math.isfinite(power) else None
            return Estimate(value, "kWh", EstimateStatus.CONDITIONAL if value is not None else EstimateStatus.UNKNOWN,
                            ("steady_auto_cruise_systems", "no_active_jobs", "no_degradation_or_reshedding"))
        return TravelCosts(nominal, energy(self.cruise_load_kw), energy(self.generation_kw),
                           Estimate(0.0, "scrap", EstimateStatus.CALCULABLE, ("Travel_has_no_direct_scrap_charge",)),
                           Estimate(None, "scrap", EstimateStatus.UNKNOWN), Estimate(None, "scrap", EstimateStatus.UNKNOWN),
                           EstimateStatus.UNKNOWN, ("future_power_distribution_and_battery", "radiation_and_system_wear",
                           "repair_choices_failures_and_operator_battery", "stops_and_information_work",
                           "future_salvage_not_earned", "cannibalization_not_implemented"))

    def evaluate(self, proposal: RecoveryProposal) -> OpportunityEvaluation:
        state, world = self.state, self.state.world
        access = proposal.origin_access_path
        origin = proposal.origin_id
        valid = bool(origin and access and access[0] == world.current_node_id and access[-1] == origin)
        valid = valid and all(b in self.edges.get(a, ()) for a, b in zip(access, access[1:]))
        reasons = {"economic_feasibility_unquantified", "sensor_coverage_not_recorded", "no_free_repositioning", "normal_ship_and_operator_gates_revalidate"}
        if not valid:
            reasons.add("origin_access_not_operational")
        nodes = tuple(stage.node for stage in proposal.stages)
        stale = (not nodes or nodes[0].node_id != origin or nodes[-1].node_id != proposal.target_id
                 or len(proposal.hops) != max(0, len(nodes)-1)
                 or any(n.node_id in self.session.protected for n in nodes) or self.session.protection_incomplete
                 or state.ship.in_transit
                 or any(world.node_pools[n].node_cleaned for n in (world.current_node_id, proposal.target_id)
                        if n in world.node_pools))
        query = self.session.planner
        if nodes and query is None:
            query = self.session.planner = _Planner(state, proposal.opportunity_id, self.context.budget)
        reservations = ()
        proposed_positions = set()
        proposed_ids = set()
        for index, node in enumerate(nodes):
            physical = world.space.nodes.get(node.node_id)
            if node.existing:
                stale |= physical is None or _position(physical) != node.position_ly or physical.kind != node.kind
            else:
                stale |= (node.node_id in query.claimed_ids or node.node_id in proposed_ids
                          or node.position_ly in query.occupied or node.position_ly in proposed_positions)
                preflight = query.new_node(node.position_ly, ("preflight", node.node_id), index,
                                           reservations, query.occupied, proposed_ids)
                stale |= (not preflight.procedural_eligible or preflight.kind != node.kind
                          or preflight.slot_index != node.slot_index or preflight.dependencies != node.dependencies)
                if node.slot_index is not None:
                    reservations += ((node.sector_id, node.slot_index),)
                proposed_positions.add(node.position_ly)
                proposed_ids.add(node.node_id)
        view = WorldState()
        for node in nodes:
            view.space.nodes[node.node_id] = SpaceNode(node.node_id, node.node_id, node.kind or "",
                                                      x_ly=node.position_ly[0], y_ly=node.position_ly[1], z_ly=node.position_ly[2])
        geometry = bool(nodes) and all(math.dist(a.position_ly, b.position_ly) > 0 and
                    is_hop_within_cap(view, a.node_id, b.node_id) for a, b in zip(nodes, nodes[1:]))
        stale |= any((hop.from_id, hop.to_id) != (a.node_id, b.node_id)
                     or hop.distance_ly != math.dist(a.position_ly, b.position_ly)
                     for hop, a, b in zip(proposal.hops, nodes, nodes[1:]))
        if stale or not geometry:
            reasons.add("proposal_stale_or_invalid")
        dependencies = {d for node in nodes for d in node.dependencies}
        if nodes and proposal.hops:
            # Recheck stored, visited and consumed sources without opening a pool.
            for index, (a, b) in enumerate(zip(nodes, nodes[1:])):
                current_hint = _hint(state, a, b, index == 0, query.sources, self.routes, query.known)
                if index >= len(proposal.hops) or current_hint != proposal.hops[index].hint:
                    stale = True
                    reasons.add("information_snapshot_changed")
                dependencies.update(current_hint.dependencies)
        if is_critical_power_state(state):
            dependencies.add(Dependency("normal_travel_power_gate", True, False))
        if state.ship.docked_node_id:
            dependencies.add(Dependency("undock_before_travel", True, False))
        dep_tuple = tuple(sorted(dependencies, key=lambda d: (d.code, d.implemented, str(d.available_now))))
        pending = tuple(sorted({d.code for d in dependencies if not d.implemented or d.available_now is None}))
        unavailable = tuple(sorted({d.code for d in dependencies if d.available_now is False and d.implemented}))
        access_nodes = tuple(self.physical[n] for n in access) if valid else ()
        access_distance = math.fsum(math.dist(a.position_ly, b.position_ly) for a, b in zip(access_nodes, access_nodes[1:])) if valid else None
        access_times = [self.duration(a, b) for a, b in zip(access_nodes, access_nodes[1:])]
        chain_distance = math.fsum(math.dist(a.position_ly, b.position_ly) for a, b in zip(nodes, nodes[1:]))
        times = access_times + [self.duration(a, b) for a, b in zip(nodes, nodes[1:])]
        seconds = math.fsum(times) if valid and all(t is not None for t in times) else None
        evidence = []
        seen = set()
        for node in access_nodes + nodes:
            if node.node_id in seen:
                continue
            seen.add(node.node_id)
            pool = world.node_pools.get(node.node_id)
            evidence.append(TerritoryEvidence(node.node_id, node.sector_id, node.region, not node.existing,
                node.node_id in world.known_nodes or node.node_id in world.known_intel,
                node.node_id in world.known_contacts, node.node_id in world.visited_nodes,
                pool.node_cleaned if pool else None, node.sector_id in world.generated_sectors,
                node.sector_id in self.sector_intel, node.sector_id in self.detected_sectors,
                node.sector_id in self.visited_sectors, node.region in self.visited_regions))
        chain_evidence = [e for e in evidence if e.node_id in {n.node_id for n in nodes[1:]}]
        frontier = set()
        if any(not e.visited for e in chain_evidence):
            frontier.add("unvisited_stage")
        if any(not e.node_known and not e.contact_detected for e in chain_evidence):
            frontier.add("unidentified_stage")
        if any(not e.sector_intel_known for e in chain_evidence):
            frontier.add("sector_intel_absent_not_sensor_coverage")
        usable = (valid and geometry and not stale and proposal.physical_chain_valid and
                  proposal.viability not in {Viability.REJECTED, Viability.INCOMPLETE} and
                  proposal.information_status != InformationStatus.UNAVAILABLE)
        status = (OpportunityStatus.UNUSABLE if not usable else OpportunityStatus.CONDITIONAL
                  if pending or unavailable or proposal.viability != Viability.VERIFIED else OpportunityStatus.VERIFIED_MECHANICS)
        if status == OpportunityStatus.UNUSABLE:
            reasons.update(proposal.reasons)
        if proposal.new_nodes:
            reasons.add("materialization_policy_pending")
        if any(d.code in {"comms", "radiod"} for d in dependencies):
            reasons.add("future_reception_required")
        target = world.space.nodes.get(proposal.target_id)
        current = world.space.nodes.get(world.current_node_id)
        straight = math.dist(_position(current), _position(target)) if current and target else None
        if straight is not None and not math.isfinite(straight):
            straight = None
        key = "OPPORTUNITY_" + _digest(proposal.opportunity_id, tuple(n.node_id for n in nodes), access)
        return OpportunityEvaluation(key, proposal, world.current_node_id, tuple(world.current_pos_ly), origin,
            access, self.access_alternatives(origin), valid, len(access)-1 if valid else None,
            access_distance, len(proposal.hops), chain_distance,
            len(access)-1+len(proposal.hops) if valid else None,
            access_distance+chain_distance if valid else None, straight,
            proposal.reused_nodes, tuple(n.node_id for n in proposal.new_nodes),
            (len(access)-1 if valid else 0)+sum(h.hint.mechanism == Mechanism.KNOWN_ROUTE for h in proposal.hops),
            tuple(evidence), tuple(sorted(frontier)), dep_tuple, pending, unavailable,
            self.costs(seconds), status, tuple(sorted(reasons)))


def evaluate_deadnode_opportunity(state: GameState, proposal: RecoveryProposal) -> OpportunityEvaluation:
    """Assess the recorded directed access path; do not silently repair stale input."""
    return _OpportunityContext(state, PlanningContext(), OpportunityBudget()).evaluate(proposal)


def compare_opportunities(left: OpportunityEvaluation, right: OpportunityEvaluation) -> OpportunityComparison:
    """Partial order: legitimacy, Pareto practical burden, then frontier evidence.

    Unknown economic costs are never replaced by zero or a guessed penalty.
    """
    def result(winner, reason):
        return OpportunityComparison(left.evaluation_id, right.evaluation_id,
                                     winner.evaluation_id if winner else None, (reason,))
    tiers = {OpportunityStatus.VERIFIED_MECHANICS: 0, OpportunityStatus.CONDITIONAL: 1, OpportunityStatus.UNUSABLE: 2}
    if tiers[left.status] != tiers[right.status]:
        return result(left if tiers[left.status] < tiers[right.status] else right, "mechanical_legitimacy_first")
    if left.status == OpportunityStatus.UNUSABLE:
        return result(None, "no_usable_candidate")
    def vector(e):
        return e.access_distance_ly, e.access_hops, e.total_distance_ly, e.total_hops, e.costs.nominal_transit_s.value
    lv, rv = vector(left), vector(right)
    if any(v is None for v in lv+rv):
        return result(None, "insufficient_practical_cost_data")
    left_deps = set(left.pending_dependencies) | set(left.unavailable_now)
    right_deps = set(right.pending_dependencies) | set(right.unavailable_now)
    le = all(a <= b for a, b in zip(lv, rv)) and left_deps <= right_deps
    re = all(b <= a for a, b in zip(lv, rv)) and right_deps <= left_deps
    if le and not re:
        return result(left, "lower_complete_journey_burden")
    if re and not le:
        return result(right, "lower_complete_journey_burden")
    if not le or not re:
        return result(None, "practical_or_dependency_tradeoff")
    lf, rf = set(left.frontier_signals), set(right.frontier_signals)
    if lf > rf:
        return result(left, "frontier_evidence_after_equal_accessibility")
    if rf > lf:
        return result(right, "frontier_evidence_after_equal_accessibility")
    return result(None, "equivalent_context" if lf == rf else "frontier_evidence_tradeoff")


def compare_deadnode_opportunities(state: GameState, target_ids: Iterable[str],
        context: PlanningContext = PlanningContext(), budget: OpportunityBudget = OpportunityBudget()) -> OpportunitySelection:
    """Bounded multi-target/route witnesses; never a global optimum or activation.

    Existing detector timing and candidate sources remain owned by deadnodes.
    Caller supplies ids; the chain kernel retains its eligibility/protection gates.
    """
    ctx = _OpportunityContext(state, context, budget)
    targets = sorted(set(target_ids))
    evaluations = {}
    for target in targets[:budget.targets]:
        proposals = [ctx.session.propose(target)]
        for objective in ("distance", "hops"):
            access = {nid: route.path for nid, route in ctx.access_maps[objective].items()}
            if access:
                distances = {nid: route.distance_ly for nid, route in ctx.access_maps[objective].items()}
                proposals.append(ctx.session.propose(target, access_paths=access, objective=objective,
                                                     augmented=True, access_distances=distances))
        for proposal in proposals:
            paths = ctx.access_alternatives(proposal.origin_id)
            variants = [replace(proposal, origin_access_path=r.path) for r in paths] if paths else [proposal]
            for variant in variants:
                evaluation = ctx.evaluate(variant)
                evaluations.setdefault(evaluation.evaluation_id, evaluation)
    rows = tuple(evaluations[key] for key in sorted(evaluations))
    comparisons = []
    dominated = set()
    for index, left in enumerate(rows):
        for right in rows[index+1:]:
            if len(comparisons) >= budget.comparisons:
                ctx.exhausted.add("comparisons")
                break
            comparison = compare_opportunities(left, right)
            comparisons.append(comparison)
            if comparison.preferred_id:
                dominated.add(right.evaluation_id if comparison.preferred_id == left.evaluation_id else left.evaluation_id)
        if "comparisons" in ctx.exhausted:
            break
    omitted = tuple(targets[budget.targets:])
    if omitted:
        ctx.exhausted.add("targets")
    search_exhausted = any(e.proposal.search.exhausted for e in rows)
    limitations = ("sampled_chain_and_access_objectives_not_complete_pareto_search", "economic_feasibility_unknown",
                   "sensor_coverage_not_recorded", "proposal_only_no_activation") + tuple(sorted(ctx.exhausted))
    preferred = tuple(e.evaluation_id for e in rows if e.evaluation_id not in dominated and e.status != OpportunityStatus.UNUSABLE)
    return OpportunitySelection(rows, preferred, tuple(comparisons), omitted, ctx.access_expansions, ctx.access_edges,
                                not ctx.exhausted and not search_exhausted, limitations)
