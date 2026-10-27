"""Stacks, their services and RTO scope (spec §24, §24.1).

A stack is the unit of DR: one plan, one RTO and one RPO per stack and failure
scenario. Services exist for display and explanation only; they have no targets.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from perpetual.models.common import Confidence, DomainModel, NonEmptyStr


class StackCriticality(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RtoScope(StrEnum):
    """Whether a stack resource is on its recovery path (spec §24.1)."""

    IN_SCOPE = "in_scope"
    """Needed for the product to serve users after failover."""
    OUT_OF_SCOPE = "out_of_scope"
    """Monitoring, logging and CI/CD by default: assessed, never blocking."""


class ScopeSource(StrEnum):
    RULE_DEFAULT = "rule_default"
    """Proposed by a rule pack from the resource type."""
    USER = "user"
    """Set by the user through an override."""


class Stack(DomainModel):
    """Everything one product needs to serve its users.

    The DR target Region and account live only on RecoveryRequirement, never here.
    """

    id: NonEmptyStr
    name: NonEmptyStr
    description: str | None = None
    environment: str | None = None
    criticality: StackCriticality
    root_resource_ids: list[NonEmptyStr] = Field(default_factory=list)
    resource_ids: list[NonEmptyStr] = Field(default_factory=list)
    service_ids: list[NonEmptyStr] = Field(default_factory=list)
    primary_region: NonEmptyStr
    discovery_confidence: Confidence

    @model_validator(mode="after")
    def _roots_are_members(self) -> Self:
        # Roots are where users enter the stack (e.g. the public load balancer); the
        # dependency closure is computed from them. A root outside the stack would
        # pull unrelated resources into the stack's plan.
        missing = set(self.root_resource_ids) - set(self.resource_ids)
        if missing:
            raise ValueError(f"root resources must be stack members: {sorted(missing)}")
        return self


class StackService(DomainModel):
    """A service inside a stack, e.g. "checkout-api".

    Holds its compute plus the resources only it uses. Shared resources such as
    the VPC or a shared database belong to the stack directly.
    """

    id: NonEmptyStr
    stack_id: NonEmptyStr
    name: NonEmptyStr
    resource_ids: list[NonEmptyStr] = Field(default_factory=list)


class StackResource(DomainModel):
    """Stack membership with its RTO scope. Membership is many-to-many."""

    stack_id: NonEmptyStr
    resource_id: NonEmptyStr
    rto_scope: RtoScope
    scope_source: ScopeSource
