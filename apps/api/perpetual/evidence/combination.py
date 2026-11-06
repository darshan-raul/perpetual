"""Combine an edge's evidence into one confidence (spec §22).

Independent sources should raise confidence, but evidence is often correlated: a
security-group path and an endpoint match may both come from the same task
definition. So:

1. each evidence item belongs to a correlation group (from config, by its kind);
2. within a group, take the maximum;
3. across groups, apply the configured combination function.

Item value: a kind listed in config takes the configured weight, so tuning the
weights takes effect without a rescan. Only a user confirmation may have no kind
(it is outside the weights table); it counts by its own `confidence` in the group
`source:user_confirmation`. Any other evidence without a kind, or with a kind
config doesn't list, is a bug in the resolver that produced it, and raises:
otherwise a forgotten `kind=` would silently bypass the weights table, and
kind-less LLM inference would raise an edge's confidence (spec §2 rule 11).

The combination function is pluggable (spec §22): `COMBINATIONS` maps the names
config may choose to implementations, so it can be tuned later against confirmed
and rejected edges.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from perpetual.config import EvidenceConfig
from perpetual.models import Evidence, SourceType

CombinationFunction = Callable[[Sequence[float]], float]


def noisy_or(confidences: Sequence[float]) -> float:
    """1 - product(1 - c): the chance at least one independent source is right."""
    unsupported_probabilities = [1.0 - confidence for confidence in confidences]
    combined = 1.0 - math.prod(unsupported_probabilities)
    # Keep floating-point rounding inside the valid confidence range.
    return min(1.0, max(0.0, combined))


COMBINATIONS: dict[str, CombinationFunction] = {"noisy_or": noisy_or}
"""Every name `EvidenceConfig.combination` allows must be registered here (a test checks)."""


class UnknownEvidenceKindError(ValueError):
    """Evidence names a kind that the evidence config doesn't define, or names none."""


@dataclass(frozen=True)
class GroupContribution:
    group: str
    confidence: float
    """The maximum within the group."""
    evidence_ids: tuple[str, ...]
    """Every item in the group, sorted. The maximum may come from any of them."""


@dataclass(frozen=True)
class CombinedConfidence:
    confidence: float
    function: str
    groups: tuple[GroupContribution, ...]
    """Sorted by group name, so the breakdown reads the same every time."""


def group_of(item: Evidence, config: EvidenceConfig) -> tuple[str, float]:
    """The correlation group and value one evidence item counts with."""
    if item.kind is None:
        if item.source_type is not SourceType.USER_CONFIRMATION:
            raise UnknownEvidenceKindError(
                f"evidence {item.id!r} from {item.source_type.value} has no kind; "
                "only a user confirmation may omit it"
            )
        return f"source:{item.source_type.value}", item.confidence
    weight = config.weights.get(item.kind)
    if weight is None:
        raise UnknownEvidenceKindError(f"evidence {item.id!r} has unknown kind {item.kind!r}")
    return weight.group, weight.weight


def combine(evidence: Sequence[Evidence], config: EvidenceConfig) -> CombinedConfidence:
    """One confidence for an edge, with the per-group breakdown behind it.

    No evidence gives 0.0: nothing supports the edge.
    """
    best_by_group: dict[str, float] = {}
    evidence_ids_by_group: dict[str, list[str]] = {}
    for item in evidence:
        group_name, confidence = group_of(item, config)
        previous_best = best_by_group.get(group_name, 0.0)
        best_by_group[group_name] = max(previous_best, confidence)
        evidence_ids_by_group.setdefault(group_name, []).append(item.id)

    contributions = []
    for group_name in sorted(best_by_group):
        evidence_ids = tuple(sorted(evidence_ids_by_group[group_name]))
        contributions.append(GroupContribution(group_name, best_by_group[group_name], evidence_ids))

    # The registry selects the configured algorithm; the empty case has no support.
    function = COMBINATIONS[config.combination]
    confidence = 0.0
    if contributions:
        confidence = function([group.confidence for group in contributions])
    return CombinedConfidence(confidence, config.combination, tuple(contributions))
