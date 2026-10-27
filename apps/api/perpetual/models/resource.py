"""Normalized resource model (spec §15).

`properties` is the raw store only. Rule packs read typed per-type models
(spec §15.3), which arrive with P0-04b to P0-04e.
"""

from typing import Any

from pydantic import AwareDatetime, Field

from perpetual.models.common import DomainModel, NonEmptyStr
from perpetual.models.evidence import SourceType


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
    source_refs: list[SourceReference] = Field(default_factory=list)
    terraform_address: str | None = None
    planned: bool = False
    """True for a resource that exists only in a Terraform plan (spec §15.1)."""
    discovered_at: AwareDatetime
