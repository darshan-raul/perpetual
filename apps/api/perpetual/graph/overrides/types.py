"""Inputs and results for the pure override layer (spec §23)."""

from dataclasses import dataclass

from pydantic import Field

from perpetual.models import (
    DependencyEdge,
    DomainModel,
    GraphOverride,
    ResourceNode,
    Stack,
    StackResource,
    StackService,
)


class OverrideError(ValueError):
    """An override or its input graph is invalid or ambiguous."""


class GraphData(DomainModel):
    """The records overrides can change; discovery remains the caller's source of truth.

    Groups and recovery mechanisms stay with the snapshot. P0-11 will combine
    these effective records with that metadata when building traversal projections.
    """

    resources: list[ResourceNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    stacks: list[Stack] = Field(default_factory=list)
    stack_resources: list[StackResource] = Field(default_factory=list)
    stack_services: list[StackService] = Field(default_factory=list)


@dataclass(frozen=True)
class Reproposal:
    """A new evidence claim for a previously rejected typed dependency."""

    edge_id: str
    rejection_id: str
    old_fingerprint: str
    new_fingerprint: str


@dataclass(frozen=True)
class OverrideResult:
    graph: GraphData
    overrides: tuple[GraphOverride, ...]
    """All overrides, including orphans, with status recomputed for this snapshot."""
    rejected_edges: tuple[DependencyEdge, ...]
    """Removed from effective edges, retained for review and group resolution."""
    orphan_reasons: dict[str, str]
    reproposals: tuple[Reproposal, ...]
