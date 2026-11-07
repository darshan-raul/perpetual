"""Private working copies and lookups for one application of overrides."""

from perpetual.graph.overrides.targets import edge_target
from perpetual.graph.overrides.types import GraphData, OverrideError
from perpetual.models import DependencyEdge


class WorkingGraph:
    def __init__(self, graph: GraphData) -> None:
        # Pydantic's frozen fields do not freeze nested lists. Deep copying keeps
        # both edits and later mutations of the result away from the source snapshot.
        graph = graph.model_copy(deep=True)
        self.resources = {node.id: node for node in graph.resources}
        self.edges = {edge.id: edge for edge in graph.edges}
        self.stacks = {stack.id: stack for stack in graph.stacks}
        self.services = {service.id: service for service in graph.stack_services}
        self.members = {
            (member.stack_id, member.resource_id): member for member in graph.stack_resources
        }
        collections = (
            (len(self.resources), len(graph.resources), "resource"),
            (len(self.edges), len(graph.edges), "edge"),
            (len(self.stacks), len(graph.stacks), "stack"),
            (len(self.services), len(graph.stack_services), "service"),
            (len(self.members), len(graph.stack_resources), "stack membership"),
        )
        for unique_count, count, label in collections:
            if unique_count != count:
                raise OverrideError(f"duplicate {label} identity in input graph")

        self.edge_ids_by_target: dict[str, str] = {}
        for edge in graph.edges:
            target = edge_target(edge)
            if target in self.edge_ids_by_target:
                raise OverrideError(f"ambiguous typed edge target: {target}")
            self.edge_ids_by_target[target] = edge.id
        self.rejected_ids: set[str] = set()

    def validate_references(self) -> None:
        """Refuse dangling effective edges and inconsistent stack membership."""
        for edge in self.edges.values():
            if edge.id in self.rejected_ids:
                continue
            if (
                edge.from_resource_id not in self.resources
                or edge.to_resource_id not in self.resources
            ):
                raise OverrideError(f"edge {edge.id!r} has a missing endpoint")
        for stack in self.stacks.values():
            if not set(stack.resource_ids) <= self.resources.keys():
                raise OverrideError(f"stack {stack.id!r} has a missing resource")
            for service_id in stack.service_ids:
                service = self.services.get(service_id)
                if service is None or service.stack_id != stack.id:
                    raise OverrideError(f"stack {stack.id!r} has an invalid service {service_id!r}")
        for service in self.services.values():
            owner = self.stacks.get(service.stack_id)
            if owner is None or not set(service.resource_ids) <= set(owner.resource_ids):
                raise OverrideError(f"service {service.id!r} has invalid stack membership")
        for member in self.members.values():
            owner = self.stacks.get(member.stack_id)
            if owner is None or member.resource_id not in owner.resource_ids:
                raise OverrideError(f"resource {member.resource_id!r} is not in its declared stack")

    def graph(self) -> GraphData:
        return GraphData(
            resources=[self.resources[key] for key in sorted(self.resources)],
            edges=[self.edges[key] for key in sorted(self.edges) if key not in self.rejected_ids],
            stacks=[self.stacks[key] for key in sorted(self.stacks)],
            stack_services=[self.services[key] for key in sorted(self.services)],
            stack_resources=[self.members[key] for key in sorted(self.members)],
        )

    def rejected_edges(self) -> tuple[DependencyEdge, ...]:
        return tuple(self.edges[key] for key in sorted(self.rejected_ids))
