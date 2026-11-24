"""Ordered readiness composition table (spec §30.1, §31, §61.1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from perpetual.models import Readiness, StackState, TargetComparison


class EvaluationKind(StrEnum):
    """Distinguishes observed live readiness from modeled design verification (spec §61.1)."""

    OBSERVED = "observed"
    DESIGN = "design"


class FindingEffect(StrEnum):
    """Separates recovery blockers from target violations and warnings (spec §31)."""

    RECOVERY_BLOCKER = "recovery_blocker"
    TARGET_VIOLATION = "target_violation"
    WARNING = "warning"


@dataclass(frozen=True)
class ReadinessInputs:
    """All deterministic inputs to the ordered §31 readiness composition table."""

    stack_state: StackState
    evaluation_kind: EvaluationKind = EvaluationKind.OBSERVED
    has_recovery_blocker: bool = False
    rto_comparison: TargetComparison = TargetComparison.UNCERTAIN
    rpo_comparison: TargetComparison = TargetComparison.UNCERTAIN
    budget_comparison: TargetComparison | None = None
    """None when no monthly DR budget is configured (disables only the budget gate)."""
    coverage_incomplete: bool = False
    evidence_stale: bool = False
    unreviewed_required_edges: int = 0
    unresolved_attribution: bool = False
    advisory_unresolved: bool = False
    has_warnings: bool = False
    lost_redundancy: bool = False


@dataclass(frozen=True)
class ReadinessResult:
    """Final stack readiness verdict plus every gate reason that produced it."""

    readiness: Readiness
    evaluation_kind: EvaluationKind
    reasons: tuple[str, ...]


def compose_readiness(inputs: ReadinessInputs) -> ReadinessResult:
    """Evaluate the ordered §31 readiness table. Negative results are never held back."""
    enforced_targets: list[tuple[str, TargetComparison]] = [
        ("rto", inputs.rto_comparison),
        ("rpo", inputs.rpo_comparison),
    ]
    if inputs.budget_comparison is not None:
        enforced_targets.append(("budget", inputs.budget_comparison))

    not_ready = _not_ready_reasons(inputs, enforced_targets)
    if not_ready:
        return ReadinessResult(Readiness.NOT_READY, inputs.evaluation_kind, tuple(not_ready))

    unknown = _unknown_reasons(inputs, enforced_targets)
    if unknown:
        return ReadinessResult(Readiness.UNKNOWN, inputs.evaluation_kind, tuple(unknown))

    degraded = _degraded_reasons(inputs)
    if degraded:
        return ReadinessResult(Readiness.DEGRADED, inputs.evaluation_kind, tuple(degraded))

    return ReadinessResult(Readiness.READY, inputs.evaluation_kind, ())


def _not_ready_reasons(
    inputs: ReadinessInputs, enforced_targets: list[tuple[str, TargetComparison]]
) -> list[str]:
    """Row 1: proven blocker, simulation UNAVAILABLE, or any enforced target FAIL."""
    reasons: list[str] = []
    if inputs.has_recovery_blocker:
        reasons.append("recovery_blocker")
    if inputs.stack_state is StackState.UNAVAILABLE:
        reasons.append("simulation_unavailable")
    for name, comparison in enforced_targets:
        if comparison is TargetComparison.FAIL:
            reasons.append(f"{name}_target_failed")
    return reasons


def _unknown_reasons(
    inputs: ReadinessInputs, enforced_targets: list[tuple[str, TargetComparison]]
) -> list[str]:
    """Row 2: missing/stale evidence, unreviewed required edges, or UNCERTAIN target."""
    reasons: list[str] = []
    if inputs.stack_state is StackState.UNKNOWN:
        reasons.append("simulation_unknown")
    if inputs.coverage_incomplete:
        reasons.append("coverage_incomplete")
    if inputs.evidence_stale:
        reasons.append("evidence_stale")
    if inputs.unreviewed_required_edges > 0:
        reasons.append("graph_not_reviewed")
    if inputs.unresolved_attribution:
        reasons.append("attribution_unresolved")
    if inputs.advisory_unresolved:
        reasons.append("advisory_unresolved")
    for name, comparison in enforced_targets:
        if comparison is TargetComparison.UNCERTAIN:
            reasons.append(f"{name}_target_uncertain")
    return reasons


def _degraded_reasons(inputs: ReadinessInputs) -> list[str]:
    """Row 3: all enforced targets PASS and recovery is proven, with nonblocking warnings."""
    reasons: list[str] = []
    if inputs.has_warnings:
        reasons.append("in_scope_warnings")
    if inputs.lost_redundancy:
        reasons.append("redundant_alternative_lost")
    return reasons
