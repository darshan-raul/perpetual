"""Cross-reference checks across a whole fixture.

The domain models check themselves; these rules need the whole file. They run on
fixtures because fixtures are hand-written and the engine trusts their contents
the way it will trust a normalized scan.

Some rules here (a group's members share one dependent, an edge is in at most one
group per scope) will also be enforced by the graph builder (P0-11) for live data.
Overrides are not checked against resources: an override whose target is gone is
orphaned, which is a valid state (spec §23).
"""

from collections import Counter
from collections.abc import Iterable

from perpetual.fixtures.loader import FixtureIssue
from perpetual.fixtures.schema import Fixture
from perpetual.models import DependencyGroup


def check_references(fixture: Fixture) -> list[FixtureIssue]:
    """Every problem in the fixture's cross-references, in file order."""
    checker = _Checker(fixture)
    checker.unique_ids()
    checker.edges()
    checker.groups("groups", fixture.groups)
    checker.observations()
    checker.mechanisms()
    checker.stacks()
    checker.requirements_and_facts()
    return checker.issues


class _Checker:
    def __init__(self, fixture: Fixture) -> None:
        self.fixture = fixture
        self.issues: list[FixtureIssue] = []
        self.resources = {r.id for r in fixture.resources}
        self.edges_by_id = {e.id: e for e in fixture.edges}
        self.stacks_by_id = {s.id: s for s in fixture.stacks}

    def add(self, path: str, message: str) -> None:
        self.issues.append(FixtureIssue(path, message))

    def need(self, path: str, resource_id: str | None) -> None:
        if resource_id is not None and resource_id not in self.resources:
            self.add(path, f"no resource {resource_id!r}")

    def need_all(self, path: str, resource_ids: Iterable[str]) -> None:
        for j, resource_id in enumerate(resource_ids):
            self.need(f"{path}[{j}]", resource_id)

    def unique_ids(self) -> None:
        f = self.fixture
        collections: dict[str, Iterable[str]] = {
            "resources": (x.id for x in f.resources),
            "edges": (x.id for x in f.edges),
            "groups": (x.id for x in f.groups),
            "observations": (x.id for x in f.observations),
            "mechanisms": (x.id for x in f.mechanisms),
            "stacks": (x.id for x in f.stacks),
            "stack_resources": (f"{x.stack_id}/{x.resource_id}" for x in f.stack_resources),
            "stack_services": (x.id for x in f.stack_services),
            "requirements": (x.id for x in f.requirements),
            "overrides": (x.id for x in f.overrides),
            "facts": (x.id for x in f.facts),
            "coverage": (x.id for x in f.coverage),
        }
        for name, ids in collections.items():
            for item, count in sorted(Counter(ids).items()):
                if count > 1:
                    self.add(name, f"id {item!r} appears {count} times")

    def edges(self) -> None:
        for i, edge in enumerate(self.fixture.edges):
            self.need(f"edges[{i}].from_resource_id", edge.from_resource_id)
            self.need(f"edges[{i}].to_resource_id", edge.to_resource_id)

    def groups(self, prefix: str, groups: list[DependencyGroup]) -> None:
        seen: dict[tuple[str, str], str] = {}
        for i, group in enumerate(groups):
            path = f"{prefix}[{i}]"
            self.need(f"{path}.dependent_resource_id", group.dependent_resource_id)
            for j, edge_id in enumerate(group.member_edge_ids):
                member = f"{path}.member_edge_ids[{j}]"
                edge = self.edges_by_id.get(edge_id)
                if edge is None:
                    self.add(member, f"no edge {edge_id!r}")
                    continue
                # A group says how one dependent's edges combine (spec §19.1).
                if edge.from_resource_id != group.dependent_resource_id:
                    self.add(member, f"edge {edge_id!r} does not start at the dependent")
                key = (group.scope.value, edge_id)
                if key in seen:
                    self.add(member, f"edge {edge_id!r} is already in group {seen[key]!r}")
                seen[key] = group.id

    def observations(self) -> None:
        for i, obs in enumerate(self.fixture.observations):
            path = f"observations[{i}]"
            self.need_all(f"{path}.candidate_from_resource_ids", obs.candidate_from_resource_ids)
            self.need_all(f"{path}.candidate_to_resource_ids", obs.candidate_to_resource_ids)

    def mechanisms(self) -> None:
        for i, mech in enumerate(self.fixture.mechanisms):
            path = f"mechanisms[{i}]"
            self.need(f"{path}.primary_resource_id", mech.primary_resource_id)
            self.need(f"{path}.counterpart_resource_id", mech.counterpart_resource_id)
            self.need_all(f"{path}.dr_dependency_ids", mech.dr_dependency_ids)
            self.groups(f"{path}.dependency_groups", mech.dependency_groups)

    def stacks(self) -> None:
        services = {s.id for s in self.fixture.stack_services}
        for i, stack in enumerate(self.fixture.stacks):
            self.need_all(f"stacks[{i}].root_resource_ids", stack.root_resource_ids)
            self.need_all(f"stacks[{i}].resource_ids", stack.resource_ids)
            for j, service_id in enumerate(stack.service_ids):
                if service_id not in services:
                    self.add(f"stacks[{i}].service_ids[{j}]", f"no service {service_id!r}")

        for i, member in enumerate(self.fixture.stack_resources):
            path = f"stack_resources[{i}]"
            owner = self.stacks_by_id.get(member.stack_id)
            if owner is None:
                self.add(f"{path}.stack_id", f"no stack {member.stack_id!r}")
                continue
            self.need(f"{path}.resource_id", member.resource_id)
            if member.resource_id not in {*owner.resource_ids, *owner.root_resource_ids}:
                self.add(f"{path}.resource_id", f"not a member of stack {owner.id!r}")

        for i, service in enumerate(self.fixture.stack_services):
            if service.stack_id not in self.stacks_by_id:
                self.add(f"stack_services[{i}].stack_id", f"no stack {service.stack_id!r}")
            self.need_all(f"stack_services[{i}].resource_ids", service.resource_ids)

    def requirements_and_facts(self) -> None:
        for i, requirement in enumerate(self.fixture.requirements):
            if requirement.stack_id not in self.stacks_by_id:
                self.add(f"requirements[{i}].stack_id", f"no stack {requirement.stack_id!r}")
        coverage = {c.id for c in self.fixture.coverage}
        for i, fact in enumerate(self.fixture.facts):
            if fact.coverage_id is not None and fact.coverage_id not in coverage:
                self.add(f"facts[{i}].coverage_id", f"no coverage {fact.coverage_id!r}")
