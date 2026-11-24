"""Recovery DAG builder, plan buffer, critical-path RTO and target comparison (§47-§52)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

import networkx as nx

from perpetual.config import Config, load_config
from perpetual.graph import DependencyGraph, GraphError
from perpetual.models import (
    BufferPolicy,
    DurationEstimate,
    EstimateConfidence,
    RecoveryMechanism,
    RecoveryRequirement,
    RtoScope,
    TargetComparison,
)
from perpetual.recovery.actions import (
    PHASE_ORDER,
    AutomationLevel,
    RecoveryAction,
    RecoveryPhase,
    actions_for_mechanism,
)
from perpetual.recovery.catalog import DurationCatalog, load_duration_catalog
from perpetual.stacks import classify_stack_scopes

DECIDE_ACTION_ID = "act:decide"
STACK_VALIDATION_ACTION_ID = "act:stack_validation"


class PlanError(ValueError):
    """Raised when recovery actions form a cycle or reference a missing prerequisite."""


@dataclass(frozen=True)
class RtoBreakdown:
    """Stack-level RTO range with critical path vs parallel breakdown (spec §50)."""

    low_seconds: float | None
    expected_seconds: float | None
    high_seconds: float | None
    critical_path_action_ids: tuple[str, ...]
    parallel_action_ids: tuple[str, ...]
    unknown_action_ids: tuple[str, ...]
    contingency_percent: Decimal
    handoff_applied_action_ids: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryPlan:
    """One stack-level recovery DAG and its computed RTO (spec §47, §50)."""

    stack_id: str
    actions: dict[str, RecoveryAction]
    edges: tuple[tuple[str, str], ...]
    """Directed prerequisite edges `(prereq_action_id, dependent_action_id)`."""
    rto: RtoBreakdown
    rto_comparison: TargetComparison | None = None


def compare_target(
    low: float | None,
    high: float | None,
    target: float,
) -> TargetComparison:
    """Compare a predicted `[low, high]` range against a target bound (spec §52).

    PASS requires `high <= target`; FAIL requires `low > target`; missing bounds
    or a range straddling the target yield UNCERTAIN.
    """
    if low is None or high is None:
        return TargetComparison.UNCERTAIN
    if high <= target:
        return TargetComparison.PASS
    if low > target:
        return TargetComparison.FAIL
    return TargetComparison.UNCERTAIN


def build_recovery_dag(
    actions: Iterable[RecoveryAction],
    *,
    stack_id: str,
    buffer: BufferPolicy | None = None,
    target_rto_seconds: float | None = None,
) -> RecoveryPlan:
    """Wire phase-template default edges + refinements, apply buffer, and compute RTO (§47-§50)."""
    action_map = _index_actions(actions)

    # Inject stack_validation action in TRAFFIC phase when configured (§49.2).
    if (
        buffer is not None
        and buffer.stack_validation is not None
        and STACK_VALIDATION_ACTION_ID not in action_map
    ):
        action_map[STACK_VALIDATION_ACTION_ID] = RecoveryAction(
            id=STACK_VALIDATION_ACTION_ID,
            name="Stack-wide DR validation",
            action_type="stack_validation",
            phase=RecoveryPhase.TRAFFIC,
            estimated_duration=buffer.stack_validation,
            automation_level=AutomationLevel.AUTOMATIC,
        )

    dag = _wire_dag_edges(action_map)
    if not nx.is_directed_acyclic_graph(dag):
        raise PlanError("recovery DAG contains a cycle; check action prerequisites")

    rto = _compute_rto(dag, action_map, buffer)
    comparison = (
        compare_target(rto.low_seconds, rto.high_seconds, target_rto_seconds)
        if target_rto_seconds is not None
        else None
    )
    edges = tuple(sorted(dag.edges()))
    return RecoveryPlan(
        stack_id=stack_id,
        actions=action_map,
        edges=edges,
        rto=rto,
        rto_comparison=comparison,
    )


def plan_stack_recovery(
    graph: DependencyGraph,
    stack_id: str,
    *,
    requirement: RecoveryRequirement,
    mechanisms: Mapping[str, RecoveryMechanism],
    config: Config | None = None,
    catalog: DurationCatalog | None = None,
    duration_overrides: Mapping[str, DurationEstimate] | None = None,
) -> RecoveryPlan:
    """Build one complete recovery plan and RTO for `stack_id` (spec §47-§50).

    Out-of-scope resources (§24.1) add no actions and no time to the plan.
    Compute actions (`ecs_scale_service`) refine prerequisites to foundation
    actions so they run in parallel with database promotion (§47.1).
    """
    stack = graph.stacks.get(stack_id)
    if stack is None:
        raise GraphError(f"unknown stack {stack_id!r}")

    effective_config = config or load_config()
    effective_catalog = catalog or load_duration_catalog()
    scopes = classify_stack_scopes(graph, stack_id, effective_config.rto_scope)

    decide_duration = requirement.detection_and_decision_seconds or effective_catalog.estimate(
        "decide_default"
    )
    actions: list[RecoveryAction] = [
        RecoveryAction(
            id=DECIDE_ACTION_ID,
            name="Detect failure and decide to fail over",
            action_type="decide",
            phase=RecoveryPhase.DECIDE,
            estimated_duration=decide_duration,
            automation_level=AutomationLevel.AUTOMATIC,
        )
    ]

    for resource_id in sorted(stack.resource_ids):
        if scopes[resource_id][0] is RtoScope.OUT_OF_SCOPE:
            continue
        mechanism = mechanisms.get(resource_id)
        if mechanism is None:
            continue
        actions.extend(
            actions_for_mechanism(
                mechanism,
                graph.resources[resource_id],
                effective_catalog,
                duration_overrides=duration_overrides,
            )
        )

    # Refine ECS compute actions to depend on foundation (or decide) rather than waiting
    # on database promotion, letting independent work overlap (§47.1, §93).
    foundation_ids = [action.id for action in actions if action.phase is RecoveryPhase.FOUNDATION]
    compute_prereqs = foundation_ids or [DECIDE_ACTION_ID]
    refined: list[RecoveryAction] = []
    for action in actions:
        if action.action_type == "ecs_scale_service":
            refined.append(
                action.model_copy(
                    update={"prerequisites": compute_prereqs, "refined_prerequisites": True}
                )
            )
        else:
            refined.append(action)

    buffer = _resolve_buffer_policy(requirement, effective_config, effective_catalog)
    return build_recovery_dag(
        refined,
        stack_id=stack_id,
        buffer=buffer,
        target_rto_seconds=float(requirement.target_rto_seconds),
    )


def _resolve_buffer_policy(
    requirement: RecoveryRequirement,
    config: Config,
    catalog: DurationCatalog,
) -> BufferPolicy:
    if requirement.buffer is not None:
        return requirement.buffer
    return BufferPolicy(
        handoff=catalog.estimate(config.buffer.handoff_catalog_key),
        stack_validation=catalog.estimate(config.buffer.stack_validation_catalog_key),
        contingency_percent=config.buffer.contingency_percent,
    )


def _index_actions(actions: Iterable[RecoveryAction]) -> dict[str, RecoveryAction]:
    indexed: dict[str, RecoveryAction] = {}
    for action in actions:
        if action.id in indexed:
            raise PlanError(f"duplicate recovery action id {action.id!r}")
        indexed[action.id] = action
    return indexed


def _wire_dag_edges(action_map: dict[str, RecoveryAction]) -> nx.DiGraph[str]:
    dag: nx.DiGraph[str] = nx.DiGraph()
    for action_id in sorted(action_map):
        dag.add_node(action_id)

    # Group actions by phase (excluding stack_validation when computing prior phase for traffic).
    by_phase: dict[RecoveryPhase, list[str]] = {phase: [] for phase in RecoveryPhase}
    for action_id in sorted(action_map):
        action = action_map[action_id]
        if action_id == STACK_VALIDATION_ACTION_ID:
            continue
        by_phase[action.phase].append(action_id)

    ordered_phases = sorted(RecoveryPhase, key=lambda p: PHASE_ORDER[p])

    for action_id, action in sorted(action_map.items()):
        if action_id == STACK_VALIDATION_ACTION_ID:
            # Stack validation waits on every action in phases before TRAFFIC (data/compute/etc.).
            for prereq_id in _latest_non_empty_prior_actions(
                RecoveryPhase.TRAFFIC, ordered_phases, by_phase, all_prior_compute_and_data=True
            ):
                dag.add_edge(prereq_id, action_id)
            continue

        if action.refined_prerequisites:
            _add_explicit_prereqs(dag, action_id, action.prerequisites, action_map)
            continue

        # Default phase-barrier edges (§47.1): wait on previous non-empty phase.
        # Traffic-switch actions also wait on stack_validation when present (§49.2).
        if action.phase is RecoveryPhase.TRAFFIC and STACK_VALIDATION_ACTION_ID in action_map:
            dag.add_edge(STACK_VALIDATION_ACTION_ID, action_id)
            continue

        for prereq_id in _latest_non_empty_prior_actions(
            action.phase, ordered_phases, by_phase, all_prior_compute_and_data=False
        ):
            dag.add_edge(prereq_id, action_id)
        _add_explicit_prereqs(dag, action_id, action.prerequisites, action_map)

    return dag


def _add_explicit_prereqs(
    dag: nx.DiGraph[str],
    action_id: str,
    prereq_ids: list[str],
    action_map: dict[str, RecoveryAction],
) -> None:
    for prereq_id in prereq_ids:
        if prereq_id not in action_map:
            raise PlanError(f"action {action_id!r} references unknown prerequisite {prereq_id!r}")
        dag.add_edge(prereq_id, action_id)


def _latest_non_empty_prior_actions(
    phase: RecoveryPhase,
    ordered_phases: list[RecoveryPhase],
    by_phase: dict[RecoveryPhase, list[str]],
    *,
    all_prior_compute_and_data: bool,
) -> list[str]:
    phase_idx = PHASE_ORDER[phase]
    if all_prior_compute_and_data:
        # Collect actions in DATA and COMPUTE (since refined compute may run in parallel with data).
        parallel_prior = by_phase[RecoveryPhase.DATA] + by_phase[RecoveryPhase.COMPUTE]
        if parallel_prior:
            return parallel_prior
    for prior_phase in reversed(ordered_phases[:phase_idx]):
        if by_phase[prior_phase]:
            return by_phase[prior_phase]
    return []


def _compute_rto(
    dag: nx.DiGraph[str],
    action_map: dict[str, RecoveryAction],
    buffer: BufferPolicy | None,
) -> RtoBreakdown:
    contingency = buffer.contingency_percent if buffer is not None else Decimal(0)
    multiplier = float(Decimal(1) + contingency / Decimal(100))
    handoff = buffer.handoff if buffer is not None else None

    handoff_applied: list[str] = []
    unknown_ids: list[str] = []
    for action_id, action in sorted(action_map.items()):
        if action.estimated_duration.expected_seconds is None:
            unknown_ids.append(action_id)
        if handoff is not None and action.automation_level in {
            AutomationLevel.MANUAL,
            AutomationLevel.SEMI_AUTOMATIC,
        }:
            handoff_applied.append(action_id)

    low_total, _ = _longest_path_bound(dag, action_map, "low_seconds", handoff)
    expected_total, critical_path = _longest_path_bound(
        dag, action_map, "expected_seconds", handoff
    )
    high_total, _ = _longest_path_bound(dag, action_map, "high_seconds", handoff)

    # If any action has unknown expected duration, expected RTO is UNKNOWN (§50).
    if unknown_ids:
        expected_total = None

    def _apply_contingency(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value * multiplier, 6)

    critical_set = set(critical_path)
    parallel_ids = tuple(sorted(aid for aid in action_map if aid not in critical_set))

    return RtoBreakdown(
        low_seconds=_apply_contingency(low_total),
        expected_seconds=_apply_contingency(expected_total),
        high_seconds=_apply_contingency(high_total),
        critical_path_action_ids=critical_path,
        parallel_action_ids=parallel_ids,
        unknown_action_ids=tuple(unknown_ids),
        contingency_percent=contingency,
        handoff_applied_action_ids=tuple(handoff_applied),
    )


def _longest_path_bound(
    dag: nx.DiGraph[str],
    action_map: dict[str, RecoveryAction],
    field_name: str,
    handoff: DurationEstimate | None,
) -> tuple[float | None, tuple[str, ...]]:
    """Compute the longest weighted path over `dag` for one duration bound."""
    if not action_map:
        return 0.0, ()

    has_unknown = False
    weights: dict[str, float] = {}
    for action_id, action in action_map.items():
        base = getattr(action.estimated_duration, field_name)
        if base is None:
            has_unknown = True
            weights[action_id] = 0.0
            continue
        extra = 0.0
        if handoff is not None and action.automation_level in {
            AutomationLevel.MANUAL,
            AutomationLevel.SEMI_AUTOMATIC,
        }:
            handoff_val = getattr(handoff, field_name)
            if handoff_val is None:
                has_unknown = True
            else:
                extra = float(handoff_val)
        weights[action_id] = float(base) + extra

    # Standard DAG DP in topological order (breaks ties deterministically by ID).
    best_dist: dict[str, float] = {}
    best_prev: dict[str, str | None] = {}
    for node_id in nx.topological_sort(dag):
        preds = sorted(dag.predecessors(node_id))
        if not preds:
            best_dist[node_id] = weights[node_id]
            best_prev[node_id] = None
        else:
            chosen = max(preds, key=lambda p: (best_dist[p], p))
            best_dist[node_id] = best_dist[chosen] + weights[node_id]
            best_prev[node_id] = chosen

    end_node = max(sorted(action_map), key=lambda n: (best_dist[n], n))
    path: list[str] = []
    cursor: str | None = end_node
    while cursor is not None:
        path.append(cursor)
        cursor = best_prev[cursor]
    path.reverse()

    total: float | None = None if has_unknown else best_dist[end_node]
    return total, tuple(path)


def zero_confidence_estimate(basis: str) -> DurationEstimate:
    """Helper for unknown duration estimates."""
    return DurationEstimate(
        low_seconds=None,
        expected_seconds=None,
        high_seconds=None,
        confidence=EstimateConfidence.LOW,
        basis=basis,
    )
