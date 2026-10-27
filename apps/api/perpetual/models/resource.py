"""Normalized resource model (spec §15).

`properties` is the raw store only. Rule packs read `typed_properties`, the typed
per-type model (spec §15.3), which normalizers fill in.
"""

from typing import Any, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr
from perpetual.models.evidence import SourceType
from perpetual.models.properties import ResourceProperties


class SourceReference(DomainModel):
    """Where a resource was seen. The spec uses this type without defining it.

    `locator` identifies the record in its source, for example a Terraform address
    qualified by root and workspace, or an AWS API operation and identifier.
    """

    source_type: SourceType
    locator: NonEmptyStr
    collected_at: AwareDatetime
    scan_id: str | None = None


class ResourceNode(DomainModel):
    """One resource from any source, merged by identity resolution (spec §15.1)."""

    id: NonEmptyStr
    """Stable canonical ID, e.g. aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER."""
    provider: NonEmptyStr
    service: NonEmptyStr
    resource_type: NonEmptyStr
    account_id: str | None = None
    region: str | None = None
    availability_zone: str | None = None
    name: str | None = None
    arn: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)
    """Raw store only. Rules never read it (spec §15.3)."""
    typed_properties: ResourceProperties | None = None
    """Typed configuration for this resource type. None until a normalizer exists for
    the type; rules then treat the resource's configuration as UNKNOWN."""
    source_refs: list[SourceReference] = Field(default_factory=list)
    terraform_address: str | None = None
    planned: bool = False
    """True for a resource that exists only in a Terraform plan (spec §15.1)."""
    discovered_at: AwareDatetime

    @model_validator(mode="after")
    def _typed_properties_match_type(self) -> Self:
        # The typed model is chosen by its type_key (e.g. "ecs/service"). It must
        # describe this node's own type: ECS service properties on an RDS node would
        # make every rule read the wrong fields.
        if self.typed_properties is not None:
            expected = f"{self.service}/{self.resource_type}"
            if self.typed_properties.type_key != expected:
                raise ValueError(
                    f"typed_properties are for {self.typed_properties.type_key!r}, "
                    f"but this node is {expected!r}"
                )
        return self
