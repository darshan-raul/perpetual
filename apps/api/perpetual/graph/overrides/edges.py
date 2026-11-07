"""Edge edits on working copies, with user assertions kept as evidence (spec §23)."""

from perpetual.graph.overrides.state import WorkingGraph
from perpetual.graph.overrides.targets import edge_target
from perpetual.graph.overrides.types import OverrideError
from perpetual.models import (
    Basis,
    DependencyEdge,
    EdgeOrigin,
    Evidence,
    GraphOverride,
    ReviewState,
    SourceType,
)
from perpetual.models.override import AddEdgePayload, EditEdgePayload


def user_evidence(override: GraphOverride, note: str | None = None) -> Evidence:
    """Stable assertion identity and timestamp, independent of when replay runs."""
    return Evidence(
        id=f"override:{override.id}",
        source_type=SourceType.USER_CONFIRMATION,
        basis=Basis.ASSERTED,
        source=f"override:{override.project_id}:{override.id}:{override.author}",
        attribute=override.kind.value,
        value_summary=note or override.reason,
        confidence=1.0,
        collected_at=override.created_at,
    )


def confirm_edge(edge: DependencyEdge, override: GraphOverride) -> DependencyEdge:
    evidence = list(edge.evidence)
    assertion = user_evidence(override)
    for existing in evidence:
        if existing.id == assertion.id:
            if existing != assertion:
                raise OverrideError(f"evidence ID collision for {assertion.id!r}")
            break
    else:
        evidence.append(assertion)
    return DependencyEdge.model_validate(
        edge.model_dump()
        | {
            "confidence": 1.0,
            "confirmed": True,
            "review_state": ReviewState.CONFIRMED,
            "evidence": evidence,
        }
    )


def add_edge(state: WorkingGraph, override: GraphOverride) -> str | None:
    """Add an asserted edge or merge its assertion into a matching discovered edge."""
    payload = AddEdgePayload.model_validate(override.payload)
    if override.target != edge_target(payload):
        raise OverrideError(f"override {override.id!r}: target does not match edge payload")
    if (
        payload.from_resource_id not in state.resources
        or payload.to_resource_id not in state.resources
    ):
        return "an edge endpoint is absent"

    edge_id = state.edge_ids_by_target.get(override.target)
    if edge_id is None:
        edge_id = f"user-edge:{override.id}"
        if edge_id in state.edges:
            raise OverrideError(f"generated edge ID collides with {edge_id!r}")
        edge = DependencyEdge(
            id=edge_id,
            from_resource_id=payload.from_resource_id,
            to_resource_id=payload.to_resource_id,
            relationship_type=payload.relationship_type,
            criticality=payload.criticality,
            confidence=1.0,
            confirmed=True,
            inferred=False,
            origin=EdgeOrigin.USER,
            review_state=ReviewState.CONFIRMED,
            evidence=[user_evidence(override, payload.note)],
        )
        state.edge_ids_by_target[override.target] = edge_id
    else:
        edge = state.edges[edge_id]
        if edge_target(edge) != override.target:
            raise OverrideError(f"override {override.id!r}: add conflicts with an edited edge")
        assertion = user_evidence(override, payload.note)
        evidence = list(edge.evidence)
        if any(item.id == assertion.id and item != assertion for item in evidence):
            raise OverrideError(f"evidence ID collision for {assertion.id!r}")
        if assertion not in evidence:
            evidence.append(assertion)
        edge = DependencyEdge.model_validate(
            edge.model_dump()
            | {
                "criticality": payload.criticality,
                "confidence": 1.0,
                "confirmed": True,
                "review_state": ReviewState.CONFIRMED,
                "evidence": evidence,
            }
        )
    state.edges[edge_id] = edge
    state.rejected_ids.discard(edge_id)
    return None


def edit_edge(edge: DependencyEdge, override: GraphOverride) -> DependencyEdge:
    payload = EditEdgePayload.model_validate(override.payload)
    # An edit is not a confirmation. Preserve existing confidence and confirmation
    # instead of granting certainty merely because criticality changed.
    changes = payload.model_dump(exclude_none=True)
    changes["review_state"] = ReviewState.EDITED
    return DependencyEdge.model_validate(edge.model_dump() | changes)
