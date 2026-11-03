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
    return min(1.0, max(0.0, 1.0 - math.prod(1.0 - c for c in confidences)))


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
    best: dict[str, float] = {}
    members: dict[str, list[str]] = {}
    for item in evidence:
        group, value = group_of(item, config)
        best[group] = max(best.get(group, 0.0), value)
        members.setdefault(group, []).append(item.id)
    groups = tuple(
        GroupContribution(name, best[name], tuple(sorted(members[name]))) for name in sorted(best)
    )
    function = COMBINATIONS[config.combination]
    confidence = function([g.confidence for g in groups]) if groups else 0.0
    return CombinedConfidence(confidence, config.combination, groups)
