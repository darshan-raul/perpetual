"""Pass 2 of the failure simulator: cycle-safe recovery pass over the DR overlay (spec §44)."""

from __future__ import annotations

from dataclasses import dataclass

from perpetual.config import Config
from perpetual.graph import DependencyGraph
from perpetual.models import (
    Criticality,
    DependencyEdge,
    DependencyGroup,
    GroupScope,
    MechanismKind,
    RecoveryMechanism,
    ResourceState,
    ReviewState,
    RtoScope,
    ScopeSource,
    worst_state,
)
from perpetual.models.override import DrPosture
from perpetual.models.properties import ExternalResourceProperties
from perpetual.simulator.impact import ImpactRecord
from perpetual.simulator.scenarios import FailureScenario, RegionFailure


@dataclass(frozen=True)
class ResourceSimulationResult:
    """Simulation outcome for one resource after Pass 1 (impact) and Pass 2 (recovery)."""

    resource_id: str
    state: ResourceState
    rto_scope: RtoScope
    possible_impact: bool
    mechanism_kind: MechanismKind | None
    counterpart_resource_id: str | None
    reason: str
    blocking_resource_ids: tuple[str, ...] = ()
    cycle_detected: bool = False
    unreviewed_low_confidence_edge_ids: tuple[str, ...] = ()


def run_recovery_pass(
    graph: DependencyGraph,
    impacts: dict[str, ImpactRecord],
    mechanisms: dict[str, RecoveryMechanism],
    scenario: FailureScenario,
    config: Config,
    *,
    scopes: dict[str, tuple[RtoScope, ScopeSource]],
) -> tuple[dict[str, ResourceSimulationResult], tuple[tuple[str, ...], ...]]:
    """Evaluate recovery state for every resource with memoised, cycle-safe traversal (spec §44)."""
    evaluator = _RecoveryEvaluator(
        graph=graph,
        impacts=impacts,
        mechanisms=mechanisms,
        scenario=scenario,
        review_threshold=config.evidence.review_confidence_threshold,
        scopes=scopes,
    )
    results: dict[str, ResourceSimulationResult] = {}
    for resource_id in sorted(graph.resources):
        results[resource_id] = evaluator.evaluate(resource_id)
    cycles = tuple(sorted(evaluator.cycles))
    return results, cycles


class _RecoveryEvaluator:
    def __init__(
        self,
        *,
        graph: DependencyGraph,
        impacts: dict[str, ImpactRecord],
        mechanisms: dict[str, RecoveryMechanism],
        scenario: FailureScenario,
        review_threshold: float,
        scopes: dict[str, tuple[RtoScope, ScopeSource]],
    ) -> None:
        self.graph = graph
        self.impacts = impacts
        self.mechanisms = mechanisms
        self.scenario = scenario
        self.review_threshold = review_threshold
        self.scopes = scopes
        self.memo: dict[str, ResourceSimulationResult] = {}
        self.visiting: list[str] = []
        self.cycles: set[tuple[str, ...]] = set()

    def evaluate(self, resource_id: str) -> ResourceSimulationResult:
        if resource_id in self.memo:
            return self.memo[resource_id]

        # Cycle safety (spec §18, §44): revisiting a node on the active stack
        # yields UNKNOWN for that path and records the cycle as evidence.
        if resource_id in self.visiting:
            cycle_start = self.visiting.index(resource_id)
            cycle = self.visiting[cycle_start:]
            smallest = min(cycle)
            rot = cycle.index(smallest)
            self.cycles.add(tuple(cycle[rot:] + cycle[:rot]))
            return ResourceSimulationResult(
                resource_id=resource_id,
                state=ResourceState.UNKNOWN,
                rto_scope=self.scopes[resource_id][0],
                possible_impact=self.impacts[resource_id].possible_impact,
                mechanism_kind=None,
                counterpart_resource_id=None,
                reason="dependency cycle detected during recovery evaluation",
                cycle_detected=True,
            )

        self.visiting.append(resource_id)
        try:
            result = self._compute(resource_id)
        finally:
            self.visiting.pop()

        # Only cache results that did not short-circuit on an in-progress cycle.
        if not result.cycle_detected:
            self.memo[resource_id] = result
        return result

    def _compute(self, resource_id: str) -> ResourceSimulationResult:
        impact = self.impacts[resource_id]
        node_scope = self.scopes[resource_id][0]
        if not impact.affected:
            return ResourceSimulationResult(
                resource_id=resource_id,
                state=ResourceState.SURVIVES,
                rto_scope=node_scope,
                possible_impact=False,
                mechanism_kind=None,
                counterpart_resource_id=None,
                reason="unaffected by failure scenario",
            )

        own_state, mech_kind, counterpart, own_reason, own_blockers = self._evaluate_own_mechanism(
            resource_id
        )
        dep_states, dep_blockers, unreviewed_edges, saw_cycle = self._evaluate_primary_dependencies(
            resource_id, node_scope
        )

        combined = worst_state([own_state, *dep_states])
        all_blockers = tuple(sorted(set(own_blockers) | set(dep_blockers)))
        reason = own_reason
        if combined is ResourceState.BLOCKED and own_state is not ResourceState.BLOCKED:
            reason = f"required dependency blocked ({', '.join(all_blockers)})"
        elif combined is ResourceState.UNKNOWN and own_state not in {
            ResourceState.BLOCKED,
            ResourceState.UNKNOWN,
        }:
            reason = (
                "dependency cycle detected"
                if saw_cycle
                else f"required dependency unknown ({', '.join(all_blockers)})"
            )

        return ResourceSimulationResult(
            resource_id=resource_id,
            state=combined,
            rto_scope=node_scope,
            possible_impact=impact.possible_impact,
            mechanism_kind=mech_kind,
            counterpart_resource_id=counterpart,
            reason=reason,
            blocking_resource_ids=all_blockers,
            cycle_detected=saw_cycle,
            unreviewed_low_confidence_edge_ids=tuple(sorted(unreviewed_edges)),
        )

    def _evaluate_own_mechanism(
        self, resource_id: str
    ) -> tuple[ResourceState, MechanismKind | None, str | None, str, list[str]]:
        mechanism = self.mechanisms.get(resource_id)
        if mechanism is None:
            return (
                ResourceState.UNKNOWN,
                MechanismKind.UNKNOWN,
                None,
                "no recovery mechanism resolved",
                [],
            )

        kind = mechanism.kind
        if kind is MechanismKind.NONE:
            return (
                ResourceState.BLOCKED,
                kind,
                None,
                "no recovery mechanism configured (mechanism: none)",
                [],
            )
        if kind is MechanismKind.UNKNOWN:
            return (
                ResourceState.UNKNOWN,
                kind,
                None,
                "insufficient evidence to determine recovery mechanism",
                [],
            )
        if kind is MechanismKind.EXTERNAL:
            return self._evaluate_external(resource_id, mechanism)
        if kind is MechanismKind.GLOBAL_SERVICE:
            return self._evaluate_global_service(mechanism)

        # LIVE_COUNTERPART, RESTORE_FROM_RECOVERY_POINT, REBUILD_FROM_IAC
        dr_states, dr_blockers = self._evaluate_dr_dependencies(mechanism)
        combined = worst_state([ResourceState.RECOVERABLE, *dr_states])
        reason = f"recoverable via {kind.value}"
        if combined is ResourceState.BLOCKED:
            reason = f"DR dependency blocked ({', '.join(sorted(dr_blockers))})"
        elif combined is ResourceState.UNKNOWN:
            reason = f"DR dependency unknown ({', '.join(sorted(dr_blockers))})"
        return combined, kind, mechanism.counterpart_resource_id, reason, dr_blockers

    def _evaluate_external(
        self, resource_id: str, mechanism: RecoveryMechanism
    ) -> tuple[ResourceState, MechanismKind, str | None, str, list[str]]:
        node = self.graph.resources[resource_id]
        props = node.typed_properties
        posture = props.dr_posture if isinstance(props, ExternalResourceProperties) else None
        if posture is DrPosture.AVAILABLE:
            return (
                ResourceState.SURVIVES,
                mechanism.kind,
                None,
                "external dependency declared available during Region failure",
                [],
            )
        if posture is DrPosture.UNAVAILABLE_IN_REGION_FAILURE:
            return (
                ResourceState.BLOCKED,
                mechanism.kind,
                None,
                "external dependency declared unavailable in Region failure",
                [],
            )
        return (
            ResourceState.UNKNOWN,
            mechanism.kind,
            None,
            "external dependency DR posture is unknown",
            [],
        )

    def _evaluate_global_service(
        self, mechanism: RecoveryMechanism
    ) -> tuple[ResourceState, MechanismKind, str | None, str, list[str]]:
        if (
            mechanism.control_plane_dependent
            and isinstance(self.scenario, RegionFailure)
            and self.scenario.region == "us-east-1"
        ):
            return (
                ResourceState.UNKNOWN,
                mechanism.kind,
                None,
                "CTRL-PLANE-001: global service control plane depends on failed us-east-1",
                [],
            )
        dr_states, dr_blockers = self._evaluate_dr_dependencies(mechanism)
        combined = worst_state([ResourceState.SURVIVES, *dr_states])
        reason = "global service data-plane failover"
        if combined is ResourceState.BLOCKED:
            reason = f"DR target blocked ({', '.join(sorted(dr_blockers))})"
        elif combined is ResourceState.UNKNOWN:
            reason = f"DR target unknown ({', '.join(sorted(dr_blockers))})"
        return combined, mechanism.kind, mechanism.counterpart_resource_id, reason, dr_blockers

    def _evaluate_dr_dependencies(
        self, mechanism: RecoveryMechanism
    ) -> tuple[list[ResourceState], list[str]]:
        states: list[ResourceState] = []
        blockers: list[str] = []
        for dep_id in mechanism.dr_dependency_ids:
            dep_result = self.evaluate(dep_id)
            states.append(dep_result.state)
            if dep_result.state in {ResourceState.BLOCKED, ResourceState.UNKNOWN}:
                blockers.append(dep_id)
        for group in mechanism.dependency_groups:
            group_state, group_blockers, _ = self._evaluate_group(group)
            states.append(group_state)
            blockers.extend(group_blockers)
        return states, blockers

    def _evaluate_primary_dependencies(
        self, resource_id: str, dependent_scope: RtoScope
    ) -> tuple[list[ResourceState], list[str], set[str], bool]:
        states: list[ResourceState] = []
        blockers: list[str] = []
        unreviewed_edges: set[str] = set()
        saw_cycle = False

        for edge in self.graph.ungrouped_outgoing_edges(
            resource_id, scope=GroupScope.PRIMARY, operational_only=True
        ):
            if not self._is_required_operational_edge(edge, dependent_scope):
                continue
            if (
                edge.review_state is ReviewState.UNREVIEWED
                and edge.confidence < self.review_threshold
            ):
                unreviewed_edges.add(edge.id)
            dep_result = self.evaluate(edge.to_resource_id)
            states.append(dep_result.state)
            if dep_result.cycle_detected:
                saw_cycle = True
            if dep_result.state in {ResourceState.BLOCKED, ResourceState.UNKNOWN}:
                blockers.append(edge.to_resource_id)

        for group in self.graph.groups_for(resource_id, scope=GroupScope.PRIMARY):
            group_state, group_blockers, group_unreviewed = self._evaluate_group(group)
            states.append(group_state)
            blockers.extend(group_blockers)
            unreviewed_edges.update(group_unreviewed)

        return states, blockers, unreviewed_edges, saw_cycle

    def _evaluate_group(self, group: DependencyGroup) -> tuple[ResourceState, list[str], set[str]]:
        """Evaluate an ALL/ANY/quorum dependency group using spec §19.1 rules."""
        required_k = group.required_members
        usable = 0
        surviving = 0
        unknown = 0
        blockers: list[str] = []
        unreviewed: set[str] = set()

        for member in self.graph.group_members(group.id):
            if member.rejected:
                continue
            edge = member.edge
            if (
                edge.review_state is ReviewState.UNREVIEWED
                and edge.confidence < self.review_threshold
            ):
                unreviewed.add(edge.id)
            dep_result = self.evaluate(edge.to_resource_id)
            if dep_result.state is ResourceState.SURVIVES:
                usable += 1
                surviving += 1
            elif dep_result.state is ResourceState.RECOVERABLE:
                usable += 1
            elif dep_result.state is ResourceState.UNKNOWN:
                unknown += 1
                blockers.append(edge.to_resource_id)
            else:
                blockers.append(edge.to_resource_id)

        if usable >= required_k:
            state = ResourceState.SURVIVES if surviving >= required_k else ResourceState.RECOVERABLE
            return state, [], unreviewed
        if usable + unknown >= required_k:
            return ResourceState.UNKNOWN, blockers, unreviewed
        return ResourceState.BLOCKED, blockers, unreviewed

    def _is_required_operational_edge(
        self, edge: DependencyEdge, dependent_scope: RtoScope
    ) -> bool:
        if not edge.relationship_type.is_operational_requirement:
            return False
        if edge.criticality is Criticality.OPTIONAL:
            return False
        target_scope = self.scopes[edge.to_resource_id][0]
        return not (dependent_scope is RtoScope.IN_SCOPE and target_scope is RtoScope.OUT_OF_SCOPE)
