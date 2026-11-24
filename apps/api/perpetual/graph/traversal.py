"""Derived traversal projections and cycle-safe NetworkX helpers (spec §18, §19.1, §20).

All traversal runs on a derived NetworkX `DiGraph` built from `DependencyGraph`
without mutating the underlying `MultiDiGraph`. Each projected edge `(u, v)`
carries `edge_ids: tuple[str, ...]` so parallel typed edge evidence is never
silently collapsed.

Per spec §18, every helper delegates to NetworkX (`descendants`, `ancestors`,
`shortest_path`, `simple_cycles`, `is_directed_acyclic_graph`), terminates on
cycles, and never raises on cyclic graphs.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

import networkx as nx

from perpetual.graph.snapshot import DependencyGraph
from perpetual.models import Criticality, RelationshipType


def project_graph(
    graph: DependencyGraph,
    *,
    operational_only: bool = True,
    include_optional: bool = True,
    min_confidence: float = 0.0,
    relationship_types: Collection[RelationshipType] | None = None,
) -> nx.DiGraph[str]:
    """Build a derived `DiGraph` for traversal while preserving parallel edge IDs.

    Defaults match operational dependency traversal (spec §19.1, §20):
    - `operational_only=True` skips structural (`contains`, `member_of`) and
      DR-overlay (`replicates_to`, `backed_up_by`) edges.
    - `include_optional=False` excludes `Criticality.OPTIONAL` edges so optional
      dependencies do not become required through closure.
    """
    projected: nx.DiGraph[str] = nx.DiGraph()
    for resource_id in sorted(graph.resources):
        projected.add_node(resource_id)

    allowed_types = frozenset(relationship_types) if relationship_types is not None else None
    edge_ids_by_pair: dict[tuple[str, str], list[str]] = {}
    for edge_id in sorted(graph.edges):
        edge = graph.edges[edge_id]
        if operational_only and not edge.relationship_type.is_operational_requirement:
            continue
        if not include_optional and edge.criticality is Criticality.OPTIONAL:
            continue
        if edge.confidence < min_confidence:
            continue
        if allowed_types is not None and edge.relationship_type not in allowed_types:
            continue
        pair = (edge.from_resource_id, edge.to_resource_id)
        edge_ids_by_pair.setdefault(pair, []).append(edge.id)

    for (source_id, target_id), edge_ids in sorted(edge_ids_by_pair.items()):
        projected.add_edge(source_id, target_id, edge_ids=tuple(edge_ids))

    return projected


def dependency_closure(
    graph: DependencyGraph,
    start_resource_ids: Iterable[str],
    *,
    operational_only: bool = True,
    include_optional: bool = True,
    include_starts: bool = False,
    min_confidence: float = 0.0,
) -> tuple[str, ...]:
    """All resources transitively required by `start_resource_ids` (`nx.descendants`).

    Terminates cleanly on cycles and returns canonical IDs in sorted order.
    """
    starts = _validate_resource_ids(graph, start_resource_ids)
    if not starts:
        return ()

    projected = project_graph(
        graph,
        operational_only=operational_only,
        include_optional=include_optional,
        min_confidence=min_confidence,
    )
    reached: set[str] = set()
    for start_id in starts:
        reached.update(nx.descendants(projected, start_id))
    if include_starts:
        reached.update(starts)
    return tuple(sorted(reached))


def ancestors_of(
    graph: DependencyGraph,
    target_resource_ids: Iterable[str],
    *,
    operational_only: bool = True,
    include_optional: bool = True,
    include_targets: bool = False,
    min_confidence: float = 0.0,
) -> tuple[str, ...]:
    """All resources that transitively depend on `target_resource_ids` (`nx.ancestors`).

    Terminates cleanly on cycles and returns canonical IDs in sorted order.
    """
    targets = _validate_resource_ids(graph, target_resource_ids)
    if not targets:
        return ()

    projected = project_graph(
        graph,
        operational_only=operational_only,
        include_optional=include_optional,
        min_confidence=min_confidence,
    )
    dependents: set[str] = set()
    for target_id in targets:
        dependents.update(nx.ancestors(projected, target_id))
    if include_targets:
        dependents.update(targets)
    return tuple(sorted(dependents))


def shortest_dependency_path(
    graph: DependencyGraph,
    from_resource_id: str,
    to_resource_id: str,
    *,
    operational_only: bool = True,
    include_optional: bool = True,
    min_confidence: float = 0.0,
) -> tuple[str, ...] | None:
    """Shortest path of resource IDs from dependent to dependency, or `None` if unreachable."""
    graph.resource(from_resource_id)
    graph.resource(to_resource_id)
    projected = project_graph(
        graph,
        operational_only=operational_only,
        include_optional=include_optional,
        min_confidence=min_confidence,
    )
    try:
        path = nx.shortest_path(projected, source=from_resource_id, target=to_resource_id)
    except nx.NetworkXNoPath:
        return None
    return tuple(path)


def has_cycles(
    graph: DependencyGraph,
    *,
    operational_only: bool = True,
    include_optional: bool = True,
    min_confidence: float = 0.0,
) -> bool:
    """True when the projected dependency graph contains at least one directed cycle."""
    projected = project_graph(
        graph,
        operational_only=operational_only,
        include_optional=include_optional,
        min_confidence=min_confidence,
    )
    return not nx.is_directed_acyclic_graph(projected)


def detect_cycles(
    graph: DependencyGraph,
    *,
    operational_only: bool = True,
    include_optional: bool = True,
    min_confidence: float = 0.0,
) -> tuple[tuple[str, ...], ...]:
    """Return every elementary directed cycle in deterministic canonical order (spec §18).

    Each cycle is rotated so its lexicographically smallest resource ID comes
    first, then all cycles are sorted. Never raises on cyclic or acyclic graphs.
    """
    projected = project_graph(
        graph,
        operational_only=operational_only,
        include_optional=include_optional,
        min_confidence=min_confidence,
    )
    canonical_cycles: list[tuple[str, ...]] = []
    for raw_cycle in nx.simple_cycles(projected):
        canonical_cycles.append(_canonicalize_cycle(raw_cycle))
    canonical_cycles.sort()
    return tuple(canonical_cycles)


def _validate_resource_ids(graph: DependencyGraph, resource_ids: Iterable[str]) -> list[str]:
    validated: list[str] = []
    for resource_id in resource_ids:
        graph.resource(resource_id)
        validated.append(resource_id)
    return validated


def _canonicalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Rotate a cycle so its smallest resource ID is first for stable output."""
    smallest = min(cycle)
    start_index = cycle.index(smallest)
    return tuple(cycle[start_index:] + cycle[:start_index])
