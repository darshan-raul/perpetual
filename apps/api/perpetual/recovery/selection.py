"""Bounded ALL/ANY/quorum dependency-group path selection for recovery DAGs (spec §19.1, P1-18)."""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass

from perpetual.config import Config, load_config
from perpetual.graph import DependencyGraph, GraphError
from perpetual.models import (
    Criticality,
    DependencyGroup,
    DurationEstimate,
    GroupMode,
    GroupScope,
    RecoveryMechanism,
    RecoveryRequirement,
    ResourceState,
    ReviewState,
    RtoScope,
)
from perpetual.recovery.catalog import DurationCatalog, load_duration_catalog
from perpetual.recovery.planner import RecoveryPlan, plan_stack_recovery
from perpetual.simulator import FailureScenario, simulate_failure
from perpetual.stacks import classify_stack_scopes


@dataclass(frozen=True)
class SelectedPathResult:
    """Consistent chosen member edges across alternative groups plus optimal recovery plan."""

    selected_edge_ids_by_group: dict[str, tuple[str, ...]]
    selected_resource_ids: tuple[str, ...]
    plan: RecoveryPlan | None
    combinations_evaluated: int
    capped: bool
    """True when the search cap prevented checking all combinations (non-optimal, §19.1)."""
    feasible: bool
    selected_unreviewed_edge_ids: tuple[str, ...] = ()


def select_recovery_paths(
    graph: DependencyGraph,
    stack_id: str,
    *,
    requirement: RecoveryRequirement,
    mechanisms: Mapping[str, RecoveryMechanism],
    scenario: FailureScenario,
    config: Config | None = None,
    catalog: DurationCatalog | None = None,
    duration_overrides: Mapping[str, DurationEstimate] | None = None,
) -> SelectedPathResult:
    """Select the feasible alternative-group member set with lowest known expected RTO (§19.1).

    - Deduplicates shared prerequisites so no resource is counted twice.
    - Respects `config.limits.alternative_selection_cap` (default 32).
    - An unresolved (UNKNOWN) or blocked branch is never recommended as feasible.
    - Unselected alternative failures remain outside the plan's required actions.
    """
    stack = graph.stacks.get(stack_id)
    if stack is None:
        raise GraphError(f"unknown stack {stack_id!r}")

    effective_config = config or load_config()
    effective_catalog = catalog or load_duration_catalog()
    cap = effective_config.limits.alternative_selection_cap
    scopes = classify_stack_scopes(graph, stack_id, effective_config.rto_scope)

    # Evaluate per-resource recoverability once so we know which branches are usable.
    sim = simulate_failure(
        graph,
        stack_id,
        scenario,
        config=effective_config,
        mechanisms=dict(mechanisms),
    )

    alt_groups = _alternative_groups_in_stack(graph, stack.resource_ids)
    group_choices = _enumerate_group_choices(graph, alt_groups)
    if any(not choices for choices in group_choices):
        return SelectedPathResult(
            selected_edge_ids_by_group={},
            selected_resource_ids=(),
            plan=None,
            combinations_evaluated=0,
            capped=False,
            feasible=False,
        )

    total_possible = 1
    for choices in group_choices:
        total_possible *= len(choices)
    capped = total_possible > cap

    best_key: tuple[float, tuple[str, ...]] | None = None
    best_result: SelectedPathResult | None = None
    evaluated = 0

    for combo in itertools.islice(itertools.product(*group_choices), cap):
        evaluated += 1
        chosen_map = {
            group.id: chosen_edges for group, chosen_edges in zip(alt_groups, combo, strict=True)
        }
        selected_ids, unreviewed = _collect_selected_resources(
            graph,
            root_ids=stack.root_resource_ids,
            chosen_by_group=chosen_map,
            scopes=scopes,
            review_threshold=effective_config.evidence.review_confidence_threshold,
        )
        if not _is_feasible_selection(selected_ids, sim.resources):
            continue

        # Build the recovery plan over the selected resources only (shared nodes counted once).
        sub_stack = stack.model_copy(update={"resource_ids": sorted(selected_ids)})
        sub_graph = DependencyGraph(
            multigraph=graph.multigraph,
            resources=graph.resources,
            edges=graph.edges,
            rejected_edges=graph.rejected_edges,
            groups=graph.groups,
            mechanisms=graph.mechanisms,
            stacks={**graph.stacks, stack_id: sub_stack},
            stack_resources=graph.stack_resources,
            stack_services=graph.stack_services,
            group_by_scoped_edge={},
        )
        plan = plan_stack_recovery(
            sub_graph,
            stack_id,
            requirement=requirement,
            mechanisms=mechanisms,
            config=effective_config,
            catalog=effective_catalog,
            duration_overrides=duration_overrides,
        )
        if plan.rto.expected_seconds is None:
            continue

        flat_edges = tuple(eid for edges in combo for eid in edges)
        rank_key = (plan.rto.expected_seconds, flat_edges)
        if best_key is None or rank_key < best_key:
            best_key = rank_key
            best_result = SelectedPathResult(
                selected_edge_ids_by_group=chosen_map,
                selected_resource_ids=tuple(sorted(selected_ids)),
                plan=plan,
                combinations_evaluated=evaluated,
                capped=capped,
                feasible=True,
                selected_unreviewed_edge_ids=tuple(sorted(unreviewed)),
            )

    if best_result is not None:
        return SelectedPathResult(
            selected_edge_ids_by_group=best_result.selected_edge_ids_by_group,
            selected_resource_ids=best_result.selected_resource_ids,
            plan=best_result.plan,
            combinations_evaluated=evaluated,
            capped=capped,
            feasible=True,
            selected_unreviewed_edge_ids=best_result.selected_unreviewed_edge_ids,
        )

    return SelectedPathResult(
        selected_edge_ids_by_group={},
        selected_resource_ids=(),
        plan=None,
        combinations_evaluated=evaluated,
        capped=capped,
        feasible=False,
    )


def _alternative_groups_in_stack(
    graph: DependencyGraph, resource_ids: list[str]
) -> list[DependencyGroup]:
    in_stack = set(resource_ids)
    groups = [
        group
        for group in graph.groups.values()
        if group.scope is GroupScope.PRIMARY
        and group.dependent_resource_id in in_stack
        and group.mode in {GroupMode.ANY, GroupMode.QUORUM}
    ]
    groups.sort(key=lambda g: g.id)
    return groups


def _enumerate_group_choices(
    graph: DependencyGraph, groups: list[DependencyGroup]
) -> list[list[tuple[str, ...]]]:
    all_choices: list[list[tuple[str, ...]]] = []
    for group in groups:
        active_edges = sorted(
            member.edge.id for member in graph.group_members(group.id) if not member.rejected
        )
        k = group.required_members
        if len(active_edges) < k:
            all_choices.append([])
        else:
            all_choices.append(list(itertools.combinations(active_edges, k)))
    return all_choices


def _collect_selected_resources(
    graph: DependencyGraph,
    *,
    root_ids: list[str],
    chosen_by_group: dict[str, tuple[str, ...]],
    scopes: Mapping[str, tuple[RtoScope, object]],
    review_threshold: float,
) -> tuple[set[str], set[str]]:
    selected: set[str] = set()
    unreviewed: set[str] = set()
    queue = [rid for rid in root_ids if scopes[rid][0] is RtoScope.IN_SCOPE]

    while queue:
        current = queue.pop(0)
        if current in selected:
            continue
        selected.add(current)

        # Follow ungrouped operational edges (implicit ALL).
        for edge in graph.ungrouped_outgoing_edges(
            current, scope=GroupScope.PRIMARY, operational_only=True
        ):
            if edge.criticality is Criticality.OPTIONAL:
                continue
            if scopes[edge.to_resource_id][0] is RtoScope.OUT_OF_SCOPE:
                continue
            if edge.review_state is ReviewState.UNREVIEWED and edge.confidence < review_threshold:
                unreviewed.add(edge.id)
            if edge.to_resource_id not in selected:
                queue.append(edge.to_resource_id)

        # Follow ONLY the chosen member edges for each primary group.
        for group in graph.groups_for(current, scope=GroupScope.PRIMARY):
            edge_ids = (
                chosen_by_group[group.id]
                if group.id in chosen_by_group
                else tuple(m.edge.id for m in graph.group_members(group.id) if not m.rejected)
            )
            for eid in edge_ids:
                edge = graph.edges[eid]
                if (
                    edge.review_state is ReviewState.UNREVIEWED
                    and edge.confidence < review_threshold
                ):
                    unreviewed.add(edge.id)
                if edge.to_resource_id not in selected:
                    queue.append(edge.to_resource_id)

    return selected, unreviewed


def _is_feasible_selection(
    selected_ids: set[str],
    resource_results: Mapping[str, object],
) -> bool:
    for rid in selected_ids:
        res = resource_results.get(rid)
        if res is None:
            return False
        state = getattr(res, "state", ResourceState.UNKNOWN)
        if state not in {ResourceState.SURVIVES, ResourceState.RECOVERABLE}:
            return False
    return True
