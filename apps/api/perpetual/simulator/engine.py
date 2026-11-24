"""Two-pass failure simulator orchestration and failure reason chains (spec §43-§46)."""

from __future__ import annotations

from dataclasses import dataclass

from perpetual.config import Config, load_config
from perpetual.graph import DependencyGraph, GraphError
from perpetual.models import (
    RecoveryMechanism,
    ResourceState,
    RtoScope,
    StackState,
    TargetComparison,
    stack_state,
)
from perpetual.rules import AssessmentContext, RulePackRegistry, default_registry
from perpetual.simulator.impact import run_impact_pass
from perpetual.simulator.readiness import (
    EvaluationKind,
    ReadinessInputs,
    ReadinessResult,
    compose_readiness,
)
from perpetual.simulator.recovery import ResourceSimulationResult, run_recovery_pass
from perpetual.simulator.scenarios import FailureScenario
from perpetual.stacks import classify_stack_scopes


@dataclass(frozen=True)
class ReasonChain:
    """Path from a stack root to a root-cause BLOCKED or UNKNOWN resource (spec §46)."""

    root_resource_id: str
    target_resource_id: str
    state: ResourceState
    steps: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class SimulationResult:
    """Complete stack-level failure simulation outcome (spec §45)."""

    stack_id: str
    scenario: FailureScenario
    stack_state: StackState
    readiness: ReadinessResult
    resources: dict[str, ResourceSimulationResult]
    reason_chains: tuple[ReasonChain, ...]
    cycles: tuple[tuple[str, ...], ...]
    unreviewed_required_edge_ids: tuple[str, ...]


def simulate_failure(
    graph: DependencyGraph,
    stack_id: str,
    scenario: FailureScenario,
    *,
    config: Config | None = None,
    mechanisms: dict[str, RecoveryMechanism] | None = None,
    registry: RulePackRegistry | None = None,
    target_region: str | None = None,
    target_account_id: str | None = None,
    rto_comparison: TargetComparison = TargetComparison.UNCERTAIN,
    rpo_comparison: TargetComparison = TargetComparison.UNCERTAIN,
    budget_comparison: TargetComparison | None = None,
    evaluation_kind: EvaluationKind = EvaluationKind.OBSERVED,
    coverage_incomplete: bool = False,
    evidence_stale: bool = False,
    unresolved_attribution: bool = False,
    advisory_unresolved: bool = False,
) -> SimulationResult:
    """Run Pass 1 (impact), Pass 2 (recovery), reason chains, and §31 readiness for `stack_id`."""
    stack = graph.stacks.get(stack_id)
    if stack is None:
        raise GraphError(f"unknown stack {stack_id!r}")

    effective_config = config or load_config()
    scopes = classify_stack_scopes(graph, stack_id, effective_config.rto_scope)
    resolved_mechanisms = _resolve_mechanisms(
        graph,
        stack_resource_ids=stack.resource_ids,
        mechanisms=mechanisms,
        registry=registry,
        target_region=target_region,
        target_account_id=target_account_id,
    )

    impacts = run_impact_pass(graph, scenario, effective_config, scopes=scopes)
    resource_results, cycles = run_recovery_pass(
        graph,
        impacts,
        resolved_mechanisms,
        scenario,
        effective_config,
        scopes=scopes,
    )

    in_scope_roots = [rid for rid in stack.root_resource_ids if scopes[rid][0] is RtoScope.IN_SCOPE]
    required_ids = in_scope_roots or [
        rid for rid in stack.resource_ids if scopes[rid][0] is RtoScope.IN_SCOPE
    ]
    computed_stack_state = stack_state([resource_results[rid].state for rid in required_ids])

    unreviewed_edges: set[str] = set()
    for rid in stack.resource_ids:
        if scopes[rid][0] is RtoScope.IN_SCOPE:
            unreviewed_edges.update(resource_results[rid].unreviewed_low_confidence_edge_ids)

    reason_chains = _build_reason_chains(
        stack.root_resource_ids,
        resource_results,
    )
    readiness = compose_readiness(
        ReadinessInputs(
            stack_state=computed_stack_state,
            evaluation_kind=evaluation_kind,
            has_recovery_blocker=computed_stack_state is StackState.UNAVAILABLE,
            rto_comparison=rto_comparison,
            rpo_comparison=rpo_comparison,
            budget_comparison=budget_comparison,
            coverage_incomplete=coverage_incomplete,
            evidence_stale=evidence_stale,
            unreviewed_required_edges=len(unreviewed_edges),
            unresolved_attribution=unresolved_attribution,
            advisory_unresolved=advisory_unresolved,
        )
    )

    stack_results = {rid: resource_results[rid] for rid in sorted(stack.resource_ids)}
    return SimulationResult(
        stack_id=stack_id,
        scenario=scenario,
        stack_state=computed_stack_state,
        readiness=readiness,
        resources=stack_results,
        reason_chains=reason_chains,
        cycles=cycles,
        unreviewed_required_edge_ids=tuple(sorted(unreviewed_edges)),
    )


def _resolve_mechanisms(
    graph: DependencyGraph,
    *,
    stack_resource_ids: list[str],
    mechanisms: dict[str, RecoveryMechanism] | None,
    registry: RulePackRegistry | None,
    target_region: str | None,
    target_account_id: str | None,
) -> dict[str, RecoveryMechanism]:
    if mechanisms is not None:
        return mechanisms
    pinned = {mech.primary_resource_id: mech for mech in graph.mechanisms.values()}
    if pinned or target_region is None:
        return pinned
    effective_registry = registry or default_registry()
    account = target_account_id or _infer_account_id(graph, stack_resource_ids)
    context = AssessmentContext(
        graph=graph,
        target_region=target_region,
        target_account_id=account,
    )
    nodes = [graph.resources[rid] for rid in stack_resource_ids if rid in graph.resources]
    return effective_registry.resolve_all(nodes, context)


def _infer_account_id(graph: DependencyGraph, resource_ids: list[str]) -> str:
    for rid in resource_ids:
        account = graph.resources[rid].account_id
        if account is not None:
            return account
    return "000000000000"


def _build_reason_chains(
    root_ids: list[str],
    results: dict[str, ResourceSimulationResult],
) -> tuple[ReasonChain, ...]:
    """Trace paths from each stack root down to every leaf BLOCKED/UNKNOWN root cause."""
    chains: list[ReasonChain] = []
    seen_pairs: set[tuple[str, str]] = set()

    for root_id in sorted(root_ids):
        root_result = results.get(root_id)
        if root_result is None or root_result.state not in {
            ResourceState.BLOCKED,
            ResourceState.UNKNOWN,
        }:
            continue
        _walk_blockers(
            root_id=root_id,
            current_id=root_id,
            path=[root_id],
            results=results,
            chains=chains,
            seen_pairs=seen_pairs,
        )
    return tuple(chains)


def _walk_blockers(
    *,
    root_id: str,
    current_id: str,
    path: list[str],
    results: dict[str, ResourceSimulationResult],
    chains: list[ReasonChain],
    seen_pairs: set[tuple[str, str]],
) -> None:
    current = results[current_id]
    next_blockers = [
        child_id
        for child_id in current.blocking_resource_ids
        if child_id in results and child_id not in path
    ]
    if not next_blockers:
        pair = (root_id, current_id)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            chains.append(
                ReasonChain(
                    root_resource_id=root_id,
                    target_resource_id=current_id,
                    state=current.state,
                    steps=tuple(path),
                    summary=current.reason,
                )
            )
        return

    for child_id in next_blockers:
        _walk_blockers(
            root_id=root_id,
            current_id=child_id,
            path=[*path, child_id],
            results=results,
            chains=chains,
            seen_pairs=seen_pairs,
        )
