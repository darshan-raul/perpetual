"""Pass 1 of the failure simulator: impact propagation over the primary graph (spec §44)."""

from __future__ import annotations

from dataclasses import dataclass

from perpetual.config import Config
from perpetual.graph import DependencyGraph
from perpetual.models import (
    Criticality,
    DependencyEdge,
    DependencyGroup,
    GroupScope,
    RtoScope,
    ScopeSource,
)
from perpetual.simulator.scenarios import FailureScenario, seed_failed_resources


@dataclass(frozen=True)
class ImpactRecord:
    """Impact-pass outcome for one resource."""

    resource_id: str
    affected: bool
    directly_failed: bool
    possible_impact: bool
    rto_scope: RtoScope
    triggering_edge_ids: tuple[str, ...] = ()


def run_impact_pass(
    graph: DependencyGraph,
    scenario: FailureScenario,
    config: Config,
    *,
    scopes: dict[str, tuple[RtoScope, ScopeSource]],
) -> dict[str, ImpactRecord]:
    """Seed failed resources and propagate impact to dependents (spec §19.1, §24.1, §44).

    Uses an iterative fixed-point loop so cyclic graphs always terminate cleanly.
    Skips structural (`contains`, `member_of`) and DR-overlay (`replicates_to`,
    `backed_up_by`) edges. Out-of-scope failures never spread to in-scope nodes.
    """
    threshold = config.evidence.review_confidence_threshold
    directly_failed = seed_failed_resources(graph, scenario)

    # Track per-node state: (affected, possible_impact, triggering_edges)
    affected: dict[str, bool] = {rid: rid in directly_failed for rid in graph.resources}
    possible: dict[str, bool] = dict.fromkeys(graph.resources, False)
    triggers: dict[str, set[str]] = {rid: set() for rid in graph.resources}

    changed = True
    while changed:
        changed = False
        for resource_id in sorted(graph.resources):
            if resource_id in directly_failed:
                continue
            node_scope = scopes[resource_id][0]
            new_affected, new_possible, new_triggers = _evaluate_dependent_impact(
                graph,
                resource_id,
                node_scope=node_scope,
                affected=affected,
                possible=possible,
                scopes=scopes,
                threshold=threshold,
            )
            if not new_affected:
                continue
            was_affected = affected[resource_id]
            was_possible = possible[resource_id]
            # Definite impact (possible=False) overrides possible_impact=True.
            merged_possible = new_possible if not was_affected else (was_possible and new_possible)
            before_triggers = set(triggers[resource_id])
            triggers[resource_id].update(new_triggers)
            if (
                not was_affected
                or merged_possible != was_possible
                or triggers[resource_id] != before_triggers
            ):
                affected[resource_id] = True
                possible[resource_id] = merged_possible
                changed = True

    return {
        rid: ImpactRecord(
            resource_id=rid,
            affected=affected[rid],
            directly_failed=rid in directly_failed,
            possible_impact=possible[rid] if affected[rid] else False,
            rto_scope=scopes[rid][0],
            triggering_edge_ids=tuple(sorted(triggers[rid])),
        )
        for rid in sorted(graph.resources)
    }


def _evaluate_dependent_impact(
    graph: DependencyGraph,
    resource_id: str,
    *,
    node_scope: RtoScope,
    affected: dict[str, bool],
    possible: dict[str, bool],
    scopes: dict[str, tuple[RtoScope, ScopeSource]],
    threshold: float,
) -> tuple[bool, bool, set[str]]:
    """Check whether any ungrouped requirement or dependency group impacts `resource_id`."""
    definite = False
    uncertain = False
    trigger_edges: set[str] = set()

    # 1. Ungrouped operational edges (implicit ALL).
    for edge in graph.ungrouped_outgoing_edges(
        resource_id, scope=GroupScope.PRIMARY, operational_only=True
    ):
        edge_state = _edge_impact_state(
            edge,
            dependent_scope=node_scope,
            affected=affected,
            possible=possible,
            scopes=scopes,
            threshold=threshold,
        )
        if edge_state == "definite":
            definite = True
            trigger_edges.add(edge.id)
        elif edge_state == "possible":
            uncertain = True
            trigger_edges.add(edge.id)

    # 2. Primary dependency groups (ALL / ANY / quorum, spec §19.1).
    for group in graph.groups_for(resource_id, scope=GroupScope.PRIMARY):
        group_state, group_triggers = _group_impact_state(
            graph,
            group,
            dependent_scope=node_scope,
            affected=affected,
            possible=possible,
            scopes=scopes,
            threshold=threshold,
        )
        if group_state == "definite":
            definite = True
            trigger_edges.update(group_triggers)
        elif group_state == "possible":
            uncertain = True
            trigger_edges.update(group_triggers)

    if definite:
        return True, False, trigger_edges
    if uncertain:
        return True, True, trigger_edges
    return False, False, set()


def _edge_impact_state(
    edge: DependencyEdge,
    *,
    dependent_scope: RtoScope,
    affected: dict[str, bool],
    possible: dict[str, bool],
    scopes: dict[str, tuple[RtoScope, ScopeSource]],
    threshold: float,
) -> str:
    """Return 'none', 'possible', or 'definite' for one operational edge."""
    if not edge.relationship_type.is_operational_requirement:
        return "none"
    if edge.criticality is Criticality.OPTIONAL:
        return "none"
    target_scope = scopes[edge.to_resource_id][0]
    # Spec §24.1: edges from in-scope to out-of-scope are treated as optional.
    if dependent_scope is RtoScope.IN_SCOPE and target_scope is RtoScope.OUT_OF_SCOPE:
        return "none"
    if not affected[edge.to_resource_id]:
        return "none"

    is_uncertain_edge = (
        edge.criticality in {Criticality.LIKELY_REQUIRED, Criticality.UNKNOWN}
        or edge.confidence < threshold
        or possible[edge.to_resource_id]
    )
    return "possible" if is_uncertain_edge else "definite"


def _group_impact_state(
    graph: DependencyGraph,
    group: DependencyGroup,
    *,
    dependent_scope: RtoScope,
    affected: dict[str, bool],
    possible: dict[str, bool],
    scopes: dict[str, tuple[RtoScope, ScopeSource]],
    threshold: float,
) -> tuple[str, set[str]]:
    """Evaluate a dependency group's impact using §19.1 threshold semantics."""
    required_k = group.required_members
    surviving = 0
    uncertain = 0
    trigger_edges: set[str] = set()

    for member in graph.group_members(group.id):
        if member.rejected:
            # Rejected member cannot satisfy the quorum; never lower required_k.
            continue
        state = _edge_impact_state(
            member.edge,
            dependent_scope=dependent_scope,
            affected=affected,
            possible=possible,
            scopes=scopes,
            threshold=threshold,
        )
        if state == "none":
            surviving += 1
        elif state == "possible":
            uncertain += 1
            trigger_edges.add(member.edge.id)
        else:
            trigger_edges.add(member.edge.id)

    if surviving >= required_k:
        return "none", set()
    if surviving + uncertain >= required_k:
        return "possible", trigger_edges
    return "definite", trigger_edges
