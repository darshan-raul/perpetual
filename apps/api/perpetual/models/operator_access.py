"""Operator access profile: the `operator_access` section of `perpetual.yaml` (spec §28.1).

Both recovery methods need a person: scripts run from an operator's laptop, and
ARC plans are started and approved by an operator. So how operators sign in and
reach private endpoints is part of every stack's recovery path. The profile is
declared in git and reviewed like code; the loader arrives in P4-04c.

Discovered facts take precedence over declared ones. A fact that is neither
discovered nor declared stays unknown: here that is None, never an empty list.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr, SortedIds


class IdentitySource(StrEnum):
    IAM_IDENTITY_CENTER = "iam_identity_center"
    IAM_USERS = "iam_users"
    EXTERNAL_IDP = "external_idp"


class OperatorIdentity(DomainModel):
    source: IdentitySource
    home_region: str | None = None
    """The IAM Identity Center home Region. None when unknown."""
    replica_regions: SortedIds | None = None
    """None means unknown; [] means declared to have no replicas."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.source is not IdentitySource.IAM_IDENTITY_CENTER and (
            self.home_region is not None or self.replica_regions is not None
        ):
            raise ValueError("home and replica Regions apply only to IAM Identity Center")
        if self.home_region and self.home_region in (self.replica_regions or []):
            raise ValueError("the home Region is not one of its own replicas")
        return self


class BreakGlass(DomainModel):
    """How operators sign in if the identity source fails."""

    method: NonEmptyStr
    """e.g. iam_role."""
    description: NonEmptyStr


class NetworkPath(DomainModel):
    """How laptops reach a private endpoint (OPS-ACCESS-002)."""

    target: NonEmptyStr
    """e.g. eks_api_private, rds_private."""
    path: NonEmptyStr
    """e.g. vpn, bastion, ssm_session."""
    terminates_in: NonEmptyStr
    """The Region where the path ends. A path ending in the failed Region fails with it."""


class OperatorAccessProfile(DomainModel):
    identity: OperatorIdentity | None = None
    break_glass: BreakGlass | None = None
    network: list[NetworkPath] = Field(default_factory=list)
    tools: dict[str, str] = Field(default_factory=dict)
    """Pinned tool versions on the operator's laptop, e.g. {"uv": "0.8"}."""

    @model_validator(mode="after")
    def _one_path_per_target(self) -> Self:
        targets = [item.target for item in self.network]
        if len(set(targets)) != len(targets):
            raise ValueError("each network target is declared once")
        return self
