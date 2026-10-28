"""Fixture format v1: a normalized graph, DR overlay and overrides in one YAML file
(spec §90.1, §104).

Fixtures let the engine run with no AWS, no credentials and no collectors. The
file holds domain models directly, so anything the engine accepts can be written
down, and anything a fixture holds has passed the same validation as live data.

To keep files short, the loader fills in values that follow from other values
(see `loader.DERIVED_FIELDS`): a resource's provider, account, Region, service,
type and planned flag come from its canonical ID, and missing timestamps default
to the fixture's `captured_at`.
"""

from typing import Any, Literal

from pydantic import AwareDatetime, Field

from perpetual.models import (
    DependencyEdge,
    DependencyGroup,
    DomainModel,
    FactRecord,
    GraphOverride,
    NonEmptyStr,
    RecoveryMechanism,
    RecoveryRequirement,
    ResolvedObservation,
    ResourceNode,
    ScanCoverage,
    Stack,
    StackResource,
    StackService,
)

FORMAT = "perpetual-fixture"
VERSION = 1


class Fixture(DomainModel):
    format: Literal["perpetual-fixture"]
    version: Literal[1]
    name: NonEmptyStr
    description: str | None = None
    captured_at: AwareDatetime
    """When the scene is set. The default for missing discovery and collection times."""

    resources: list[ResourceNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    groups: list[DependencyGroup] = Field(default_factory=list)
    observations: list[ResolvedObservation] = Field(default_factory=list)
    mechanisms: list[RecoveryMechanism] = Field(default_factory=list)
    """The DR overlay (spec §27.1)."""
    stacks: list[Stack] = Field(default_factory=list)
    stack_resources: list[StackResource] = Field(default_factory=list)
    stack_services: list[StackService] = Field(default_factory=list)
    requirements: list[RecoveryRequirement] = Field(default_factory=list)
    overrides: list[GraphOverride] = Field(default_factory=list)
    """User edits applied on top of the graph (spec §23)."""
    facts: list[FactRecord] = Field(default_factory=list)
    coverage: list[ScanCoverage] = Field(default_factory=list)


def fixture_json_schema() -> dict[str, Any]:
    """JSON Schema for authored fixtures: derived fields are optional (for editors)."""
    from perpetual.fixtures.loader import DERIVED_FIELDS  # noqa: PLC0415 (avoids a cycle)

    schema = Fixture.model_json_schema()
    schema["$id"] = "https://github.com/darshan-raul/perpetual/fixtures/schema/fixture-v1.json"
    schema["title"] = "Perpetual fixture v1"
    for model_name, fields in DERIVED_FIELDS.items():
        definition = schema["$defs"][model_name]
        required = [name for name in definition.get("required", []) if name not in fields]
        if required:
            definition["required"] = required
        else:
            definition.pop("required", None)
    return schema
