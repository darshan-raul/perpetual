"""Validated NetworkX MultiDiGraph snapshot of resources, edges and groups (spec §17-§19.1).

Perpetual persists resources and edges relationally and builds a NetworkX
`MultiDiGraph` on demand for traversal and simulation. Edge direction is always
`dependent -> dependency` (spec §17).

Why a `MultiDiGraph` keyed by `edge.id`:
- two resources may have parallel typed edges (for example `connects_to` and
  `uses_secret`), and neither may overwrite the other (spec §19.1);
- dependency groups (`ALL`, `ANY`, `quorum`) reference individual edge IDs and
  keep rejected-edge context without silently lowering a quorum.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import networkx as nx

from perpetual.graph.overrides.types import GraphData, OverrideResult
from perpetual.ids import AwsResourceId, parse
from perpetual.models import (
    DependencyEdge,
    DependencyGroup,
    GroupScope,
    RecoveryMechanism,
    ResourceNode,
    ReviewState,
    Stack,
    StackResource,
    StackService,
)


class GraphError(ValueError):
    """The snapshot inputs violate a graph, identity or dependency-group invariant."""


@dataclass(frozen=True)
class GroupMember:
    """One member edge of a dependency group, keeping rejected-edge context intact."""

    edge: DependencyEdge
    rejected: bool


class DependencyGraph:
    """Read-only view over a validated NetworkX `MultiDiGraph` and its snapshot metadata.

    Active (non-rejected) edges live in `multigraph` keyed by `edge.id`. Rejected
    edges are excluded from `multigraph` so active traversals ignore them, while
    remaining indexed in `rejected_edges` so dependency groups can report rejected
    members without lowering `minimum_healthy`.
    """

    def __init__(
        self,
        *,
        multigraph: nx.MultiDiGraph[str],
        resources: dict[str, ResourceNode],
        edges: dict[str, DependencyEdge],
        rejected_edges: dict[str, DependencyEdge],
        groups: dict[str, DependencyGroup],
        mechanisms: dict[str, RecoveryMechanism],
        stacks: dict[str, Stack],
        stack_resources: dict[tuple[str, str], StackResource],
        stack_services: dict[str, StackService],
        group_by_scoped_edge: dict[tuple[GroupScope, str], str],
    ) -> None:
        self.multigraph = multigraph
        self.resources = resources
        self.edges = edges
        self.rejected_edges = rejected_edges
        self.groups = groups
        self.mechanisms = mechanisms
        self.stacks = stacks
        self.stack_resources = stack_resources
        self.stack_services = stack_services
        self._group_by_scoped_edge = group_by_scoped_edge

    @classmethod
    def from_graph_data(
        cls,
        graph_data: GraphData,
        *,
        groups: Iterable[DependencyGroup] = (),
        rejected_edges: Iterable[DependencyEdge] = (),
        mechanisms: Iterable[RecoveryMechanism] = (),
    ) -> DependencyGraph:
        """Build a `DependencyGraph` from `GraphData` plus snapshot groups and mechanisms."""
        return build_graph(
            resources=graph_data.resources,
            edges=graph_data.edges,
            groups=groups,
            rejected_edges=rejected_edges,
            mechanisms=mechanisms,
            stacks=graph_data.stacks,
            stack_resources=graph_data.stack_resources,
            stack_services=graph_data.stack_services,
        )

    @classmethod
    def from_override_result(
        cls,
        result: OverrideResult,
        *,
        groups: Iterable[DependencyGroup] = (),
        mechanisms: Iterable[RecoveryMechanism] = (),
    ) -> DependencyGraph:
        """Build a `DependencyGraph` directly from `apply_overrides` output."""
        return cls.from_graph_data(
            result.graph,
            groups=groups,
            rejected_edges=result.rejected_edges,
            mechanisms=mechanisms,
        )

    def resource(self, resource_id: str) -> ResourceNode:
        """Return one resource by canonical ID, or raise `GraphError` if absent."""
        node = self.resources.get(resource_id)
        if node is None:
            raise GraphError(f"unknown resource {resource_id!r}")
        return node

    def edge(self, edge_id: str) -> DependencyEdge:
        """Return one active edge by ID, or raise `GraphError` if absent."""
        found = self.edges.get(edge_id)
        if found is None:
            raise GraphError(f"unknown edge {edge_id!r}")
        return found

    def outgoing_edges(
        self,
        resource_id: str,
        *,
        operational_only: bool = False,
    ) -> tuple[DependencyEdge, ...]:
        """Active edges leaving `resource_id` (`dependent -> dependency`), sorted by ID."""
        self.resource(resource_id)
        collected: list[DependencyEdge] = []
        for _, _, edge_id in self.multigraph.out_edges(resource_id, keys=True):
            edge = self.edges[edge_id]
            if operational_only and not edge.relationship_type.is_operational_requirement:
                continue
            collected.append(edge)
        collected.sort(key=lambda item: item.id)
        return tuple(collected)

    def incoming_edges(
        self,
        resource_id: str,
        *,
        operational_only: bool = False,
    ) -> tuple[DependencyEdge, ...]:
        """Active edges entering `resource_id` (its direct dependents), sorted by ID."""
        self.resource(resource_id)
        collected: list[DependencyEdge] = []
        for _, _, edge_id in self.multigraph.in_edges(resource_id, keys=True):
            edge = self.edges[edge_id]
            if operational_only and not edge.relationship_type.is_operational_requirement:
                continue
            collected.append(edge)
        collected.sort(key=lambda item: item.id)
        return tuple(collected)

    def edges_between(
        self,
        from_resource_id: str,
        to_resource_id: str,
    ) -> tuple[DependencyEdge, ...]:
        """All parallel active edges from `from_resource_id` to `to_resource_id`, sorted by ID."""
        self.resource(from_resource_id)
        self.resource(to_resource_id)
        raw = self.multigraph.get_edge_data(from_resource_id, to_resource_id)
        if not raw:
            return ()
        edge_ids = sorted(str(edge_id) for edge_id in raw)
        return tuple(self.edges[edge_id] for edge_id in edge_ids)

    def groups_for(
        self,
        resource_id: str,
        *,
        scope: GroupScope | None = None,
    ) -> tuple[DependencyGroup, ...]:
        """Dependency groups owned by `resource_id`, optionally filtered by scope."""
        self.resource(resource_id)
        matched = [
            group
            for group in self.groups.values()
            if group.dependent_resource_id == resource_id
            and (scope is None or group.scope is scope)
        ]
        matched.sort(key=lambda item: item.id)
        return tuple(matched)

    def group_for_edge(
        self,
        edge_id: str,
        *,
        scope: GroupScope = GroupScope.PRIMARY,
    ) -> DependencyGroup | None:
        """Return the group containing `edge_id` in `scope`, or `None` if ungrouped."""
        group_id = self._group_by_scoped_edge.get((scope, edge_id))
        if group_id is None:
            return None
        return self.groups[group_id]

    def group_members(self, group_id: str) -> tuple[GroupMember, ...]:
        """Resolve each member edge of `group_id`, preserving rejected-edge context."""
        group = self.groups.get(group_id)
        if group is None:
            raise GraphError(f"unknown dependency group {group_id!r}")
        members: list[GroupMember] = []
        for edge_id in group.member_edge_ids:
            active = self.edges.get(edge_id)
            if active is not None:
                members.append(GroupMember(edge=active, rejected=False))
            else:
                members.append(GroupMember(edge=self.rejected_edges[edge_id], rejected=True))
        return tuple(members)

    def ungrouped_outgoing_edges(
        self,
        resource_id: str,
        *,
        scope: GroupScope = GroupScope.PRIMARY,
        operational_only: bool = True,
    ) -> tuple[DependencyEdge, ...]:
        """Active outgoing edges not in any group for `scope` (implicit ALL, spec §19.1)."""
        outgoing = self.outgoing_edges(resource_id, operational_only=operational_only)
        return tuple(
            edge for edge in outgoing if (scope, edge.id) not in self._group_by_scoped_edge
        )


def build_graph(
    *,
    resources: Iterable[ResourceNode],
    edges: Iterable[DependencyEdge] = (),
    groups: Iterable[DependencyGroup] = (),
    rejected_edges: Iterable[DependencyEdge] = (),
    mechanisms: Iterable[RecoveryMechanism] = (),
    stacks: Iterable[Stack] = (),
    stack_resources: Iterable[StackResource] = (),
    stack_services: Iterable[StackService] = (),
) -> DependencyGraph:
    """Validate snapshot records and build a NetworkX `MultiDiGraph`.

    Enforces unique IDs, canonical ID consistency (deferred from P0-05), edge
    endpoint existence, dependency-group invariants (spec §19.1), mechanism
    references, and stack membership consistency.
    """
    resources_by_id = _index_resources(resources)
    edges_by_id = _index_edges(edges, resources_by_id, allow_rejected=False, label="edge")
    rejected_by_id = _index_edges(
        rejected_edges, resources_by_id, allow_rejected=True, label="rejected edge"
    )
    overlap = sorted(edges_by_id.keys() & rejected_by_id.keys())
    if overlap:
        raise GraphError(f"edge {overlap[0]!r} appears in both active and rejected edges")

    mechanisms_by_id = _index_mechanisms(mechanisms, resources_by_id)
    groups_by_id, group_by_scoped_edge = _index_groups(
        groups,
        mechanisms_by_id,
        resources_by_id,
        edges_by_id,
        rejected_by_id,
    )
    stacks_by_id, stack_resources_by_key, services_by_id = _index_stacks(
        stacks, stack_resources, stack_services, resources_by_id
    )

    multigraph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    for resource_id in sorted(resources_by_id):
        multigraph.add_node(resource_id, resource=resources_by_id[resource_id])
    for edge_id in sorted(edges_by_id):
        edge = edges_by_id[edge_id]
        multigraph.add_edge(edge.from_resource_id, edge.to_resource_id, key=edge.id, edge=edge)

    return DependencyGraph(
        multigraph=multigraph,
        resources=resources_by_id,
        edges=edges_by_id,
        rejected_edges=rejected_by_id,
        groups=groups_by_id,
        mechanisms=mechanisms_by_id,
        stacks=stacks_by_id,
        stack_resources=stack_resources_by_key,
        stack_services=services_by_id,
        group_by_scoped_edge=group_by_scoped_edge,
    )


def _index_resources(resources: Iterable[ResourceNode]) -> dict[str, ResourceNode]:
    indexed: dict[str, ResourceNode] = {}
    for node in resources:
        if node.id in indexed:
            raise GraphError(f"duplicate resource id {node.id!r}")
        _check_node_identity(node)
        indexed[node.id] = node
    return indexed


def _check_node_identity(node: ResourceNode) -> None:
    """Confirm a node's fields agree with its canonical ID (P0-05 decision)."""
    try:
        parsed = parse(node.id)
    except ValueError as error:
        raise GraphError(f"resource {node.id!r} has an invalid canonical ID: {error}") from error

    if isinstance(parsed, AwsResourceId):
        if node.provider != "aws":
            raise GraphError(f"resource {node.id!r}: provider {node.provider!r} contradicts AWS ID")
        if node.service != parsed.service or node.resource_type != parsed.resource_type:
            raise GraphError(
                f"resource {node.id!r}: {node.service}/{node.resource_type} contradicts ID"
            )
        if node.account_id != parsed.account_id:
            raise GraphError(f"resource {node.id!r}: account_id {node.account_id!r} contradicts ID")
        if node.region != parsed.region:
            raise GraphError(f"resource {node.id!r}: region {node.region!r} contradicts ID")
        if node.planned != parsed.is_planned:
            raise GraphError(f"resource {node.id!r}: planned={node.planned} contradicts ID")
        return

    if node.provider != "external":
        raise GraphError(
            f"resource {node.id!r}: provider {node.provider!r} contradicts external ID"
        )
    if node.service != parsed.service:
        raise GraphError(f"resource {node.id!r}: service {node.service!r} contradicts external ID")


def _index_edges(
    edges: Iterable[DependencyEdge],
    resources_by_id: dict[str, ResourceNode],
    *,
    allow_rejected: bool,
    label: str,
) -> dict[str, DependencyEdge]:
    indexed: dict[str, DependencyEdge] = {}
    for edge in edges:
        if edge.id in indexed:
            raise GraphError(f"duplicate {label} id {edge.id!r}")
        if not allow_rejected and edge.review_state is ReviewState.REJECTED:
            raise GraphError(
                f"active edge {edge.id!r} has review_state='rejected'; pass it in rejected_edges"
            )
        if edge.from_resource_id not in resources_by_id:
            raise GraphError(
                f"{label} {edge.id!r} references missing dependent {edge.from_resource_id!r}"
            )
        if edge.to_resource_id not in resources_by_id:
            raise GraphError(
                f"{label} {edge.id!r} references missing dependency {edge.to_resource_id!r}"
            )
        indexed[edge.id] = edge
    return indexed


def _index_mechanisms(
    mechanisms: Iterable[RecoveryMechanism],
    resources_by_id: dict[str, ResourceNode],
) -> dict[str, RecoveryMechanism]:
    indexed: dict[str, RecoveryMechanism] = {}
    for mechanism in mechanisms:
        if mechanism.id in indexed:
            raise GraphError(f"duplicate recovery mechanism id {mechanism.id!r}")
        if mechanism.primary_resource_id not in resources_by_id:
            raise GraphError(
                f"mechanism {mechanism.id!r} references missing primary resource "
                f"{mechanism.primary_resource_id!r}"
            )
        if (
            mechanism.counterpart_resource_id is not None
            and mechanism.counterpart_resource_id not in resources_by_id
        ):
            raise GraphError(
                f"mechanism {mechanism.id!r} references missing counterpart "
                f"{mechanism.counterpart_resource_id!r}"
            )
        for dependency_id in mechanism.dr_dependency_ids:
            if dependency_id not in resources_by_id:
                raise GraphError(
                    f"mechanism {mechanism.id!r} references missing DR dependency {dependency_id!r}"
                )
        indexed[mechanism.id] = mechanism
    return indexed


def _index_groups(
    groups: Iterable[DependencyGroup],
    mechanisms_by_id: dict[str, RecoveryMechanism],
    resources_by_id: dict[str, ResourceNode],
    edges_by_id: dict[str, DependencyEdge],
    rejected_by_id: dict[str, DependencyEdge],
) -> tuple[dict[str, DependencyGroup], dict[tuple[GroupScope, str], str]]:
    """Validate and index all primary and DR-overlay dependency groups (spec §19.1)."""
    all_groups: list[DependencyGroup] = list(groups)
    for mechanism in mechanisms_by_id.values():
        all_groups.extend(mechanism.dependency_groups)

    indexed: dict[str, DependencyGroup] = {}
    group_by_scoped_edge: dict[tuple[GroupScope, str], str] = {}
    for group in all_groups:
        if group.id in indexed:
            raise GraphError(f"duplicate dependency group id {group.id!r}")
        if group.dependent_resource_id not in resources_by_id:
            raise GraphError(
                f"group {group.id!r} references missing dependent {group.dependent_resource_id!r}"
            )
        for edge_id in group.member_edge_ids:
            edge = edges_by_id.get(edge_id) or rejected_by_id.get(edge_id)
            if edge is None:
                raise GraphError(f"group {group.id!r} references missing edge {edge_id!r}")
            if edge.from_resource_id != group.dependent_resource_id:
                raise GraphError(
                    f"group {group.id!r}: member edge {edge_id!r} starts at "
                    f"{edge.from_resource_id!r}, not dependent {group.dependent_resource_id!r}"
                )
            scoped_key = (group.scope, edge_id)
            if scoped_key in group_by_scoped_edge:
                existing = group_by_scoped_edge[scoped_key]
                raise GraphError(
                    f"edge {edge_id!r} already belongs to group {existing!r} "
                    f"in scope {group.scope.value!r}"
                )
            group_by_scoped_edge[scoped_key] = group.id
        indexed[group.id] = group
    return indexed, group_by_scoped_edge


def _index_stacks(
    stacks: Iterable[Stack],
    stack_resources: Iterable[StackResource],
    stack_services: Iterable[StackService],
    resources_by_id: dict[str, ResourceNode],
) -> tuple[dict[str, Stack], dict[tuple[str, str], StackResource], dict[str, StackService]]:
    stacks_by_id = _index_stack_records(stacks, resources_by_id)
    services_by_id = _index_stack_services(stack_services, stacks_by_id)
    _check_stack_service_refs(stacks_by_id, services_by_id)
    members_by_key = _index_stack_resources(stack_resources, stacks_by_id)
    return stacks_by_id, members_by_key, services_by_id


def _index_stack_records(
    stacks: Iterable[Stack],
    resources_by_id: dict[str, ResourceNode],
) -> dict[str, Stack]:
    stacks_by_id: dict[str, Stack] = {}
    for stack in stacks:
        if stack.id in stacks_by_id:
            raise GraphError(f"duplicate stack id {stack.id!r}")
        for resource_id in stack.resource_ids:
            if resource_id not in resources_by_id:
                raise GraphError(f"stack {stack.id!r} references missing resource {resource_id!r}")
        stacks_by_id[stack.id] = stack
    return stacks_by_id


def _index_stack_services(
    stack_services: Iterable[StackService],
    stacks_by_id: dict[str, Stack],
) -> dict[str, StackService]:
    services_by_id: dict[str, StackService] = {}
    for service in stack_services:
        if service.id in services_by_id:
            raise GraphError(f"duplicate stack service id {service.id!r}")
        owner = stacks_by_id.get(service.stack_id)
        if owner is None:
            raise GraphError(
                f"service {service.id!r} references missing stack {service.stack_id!r}"
            )
        for resource_id in service.resource_ids:
            if resource_id not in owner.resource_ids:
                raise GraphError(
                    f"service {service.id!r} references resource {resource_id!r} "
                    f"outside stack {owner.id!r}"
                )
        services_by_id[service.id] = service
    return services_by_id


def _check_stack_service_refs(
    stacks_by_id: dict[str, Stack],
    services_by_id: dict[str, StackService],
) -> None:
    for stack in stacks_by_id.values():
        for service_id in stack.service_ids:
            service = services_by_id.get(service_id)
            if service is None or service.stack_id != stack.id:
                raise GraphError(f"stack {stack.id!r} references invalid service {service_id!r}")


def _index_stack_resources(
    stack_resources: Iterable[StackResource],
    stacks_by_id: dict[str, Stack],
) -> dict[tuple[str, str], StackResource]:
    members_by_key: dict[tuple[str, str], StackResource] = {}
    for member in stack_resources:
        key = (member.stack_id, member.resource_id)
        if key in members_by_key:
            raise GraphError(
                f"duplicate stack resource membership ({member.stack_id!r}, {member.resource_id!r})"
            )
        owner = stacks_by_id.get(member.stack_id)
        if owner is None:
            raise GraphError(
                f"stack resource {member.resource_id!r} references missing stack "
                f"{member.stack_id!r}"
            )
        if member.resource_id not in owner.resource_ids:
            raise GraphError(f"stack resource {member.resource_id!r} is not in stack {owner.id!r}")
        members_by_key[key] = member
    return members_by_key
