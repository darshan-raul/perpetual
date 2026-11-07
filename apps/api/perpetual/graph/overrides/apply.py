"""Replay user corrections over fresh discovered records (spec §23)."""

from collections.abc import Iterable

from perpetual.evidence import edge_fingerprint
from perpetual.graph.overrides.edges import add_edge, confirm_edge, edit_edge
from perpetual.graph.overrides.nodes import add_node, edit_node
from perpetual.graph.overrides.state import WorkingGraph
from perpetual.graph.overrides.targets import edge_target
from perpetual.graph.overrides.types import GraphData, OverrideError, OverrideResult, Reproposal
from perpetual.graph.overrides.validation import ordered_overrides
from perpetual.models import (
    DependencyEdge,
    GraphOverride,
    OverrideKind,
    OverrideStatus,
    ReviewState,
)
from perpetual.models.override import AddNodePayload


def apply_overrides(
    graph: GraphData,
    overrides: Iterable[GraphOverride],
    *,
    project_id: str,
    historical_edges: Iterable[DependencyEdge] = (),
) -> OverrideResult:
    """Return an effective graph and review diagnostics without changing inputs or storage.

    Always pass fresh source records, not the previous effective graph. Historical
    source edges explain unmatched rejection hashes; include the original rejected
    claims, even when they are older than the immediately preceding scan.
    """
    try:
        return _apply(graph, overrides, project_id, historical_edges)
    except ValueError as error:
        if isinstance(error, OverrideError):
            raise
        raise OverrideError(str(error)) from error


def _apply(
    graph: GraphData,
    overrides: Iterable[GraphOverride],
    project_id: str,
    historical_edges: Iterable[DependencyEdge],
) -> OverrideResult:
    records = ordered_overrides(project_id, overrides)
    state = WorkingGraph(graph)
    history = {edge_fingerprint(edge): edge for edge in historical_edges}
    source_edges = dict(state.edges)
    source_by_fingerprint = {edge_fingerprint(edge): edge for edge in source_edges.values()}
    orphan_reasons: dict[str, str] = {}
    reproposals: list[Reproposal] = []

    # Node declarations establish targets before any relationship or membership
    # edit. This makes YAML row order and timestamps independent of node existence.
    _add_nodes(state, records)

    for override in records:
        reason = None
        if override.kind is OverrideKind.ADD_NODE:
            continue
        if override.kind is OverrideKind.ADD_EDGE:
            reason = add_edge(state, override)
        elif override.kind is OverrideKind.EDIT_NODE:
            reason = edit_node(state, override)
        elif override.kind is OverrideKind.REJECT_EDGE:
            reason = _reject(
                state,
                override,
                source_by_fingerprint,
                history,
                source_edges,
                reproposals=reproposals,
            )
        else:
            reason = _review_edge(state, override)
        if reason is not None:
            orphan_reasons[override.id] = reason

    state.validate_references()
    # Editing a type must not silently combine two independently reviewed claims.
    effective_graph = state.graph()
    effective_targets = [edge_target(edge) for edge in effective_graph.edges]
    if len(set(effective_targets)) != len(effective_targets):
        raise OverrideError("an edge edit creates an ambiguous typed dependency")
    updated = []
    for override in records:
        status = OverrideStatus.ORPHANED if override.id in orphan_reasons else OverrideStatus.ACTIVE
        updated.append(GraphOverride.model_validate(override.model_dump() | {"status": status}))
    return OverrideResult(
        graph=effective_graph,
        overrides=tuple(updated),
        rejected_edges=state.rejected_edges(),
        orphan_reasons=orphan_reasons,
        reproposals=tuple(reproposals),
    )


def _reject(
    state: WorkingGraph,
    override: GraphOverride,
    source_by_fingerprint: dict[str, DependencyEdge],
    history: dict[str, DependencyEdge],
    source_edges: dict[str, DependencyEdge],
    *,
    reproposals: list[Reproposal],
) -> str | None:
    source = source_by_fingerprint.get(override.target)
    if source is not None:
        edge = state.edges[source.id]
        state.edges[source.id] = DependencyEdge.model_validate(
            edge.model_dump() | {"confirmed": False, "review_state": ReviewState.REJECTED}
        )
        state.rejected_ids.add(source.id)
        return None

    previous = history.get(override.target)
    if previous is None:
        return "rejection fingerprint is absent; historical source evidence is unavailable"
    if (
        previous.from_resource_id not in state.resources
        or previous.to_resource_id not in state.resources
    ):
        return "a rejected edge endpoint is absent"
    edge_id = state.edge_ids_by_target.get(edge_target(previous))
    if edge_id is None or edge_id not in source_edges:
        return "the rejected typed edge is absent"
    current = source_edges[edge_id]
    # An earlier confirmation was superseded by this rejection. It must not
    # silently confirm the new claim when all old instructions replay on a rescan.
    # A later confirmation in the replay can still explicitly accept the claim.
    state.edges[edge_id] = DependencyEdge.model_validate(
        state.edges[edge_id].model_dump()
        | {
            "confidence": current.confidence,
            "confirmed": None,
            "review_state": ReviewState.UNREVIEWED,
            "evidence": current.evidence,
        }
    )
    reproposals.append(
        Reproposal(current.id, override.id, override.target, edge_fingerprint(current))
    )
    # This rejection is still a valid rule for the old fingerprint, not for the
    # current claim. Keep it active and expose the changed evidence for review.
    return None


def _review_edge(state: WorkingGraph, override: GraphOverride) -> str | None:
    edge_id = state.edge_ids_by_target.get(override.target)
    if edge_id is None:
        return "the typed edge is absent"
    if override.kind is OverrideKind.CONFIRM_EDGE:
        state.edges[edge_id] = confirm_edge(state.edges[edge_id], override)
        state.rejected_ids.discard(edge_id)
    else:
        edited = edit_edge(state.edges[edge_id], override)
        if edge_id in state.rejected_ids:
            edited = DependencyEdge.model_validate(
                edited.model_dump() | {"review_state": ReviewState.REJECTED}
            )
        state.edges[edge_id] = edited
    return None


def _add_nodes(state: WorkingGraph, records: list[GraphOverride]) -> None:
    declarations: dict[str, AddNodePayload] = {}
    for override in records:
        if override.kind is not OverrideKind.ADD_NODE:
            continue
        declaration = AddNodePayload.model_validate(override.payload)
        previous = declarations.get(override.target)
        if previous is not None and previous != declaration:
            raise OverrideError(f"conflicting node declarations for {override.target!r}")
        declarations[override.target] = declaration
        add_node(state, override)
