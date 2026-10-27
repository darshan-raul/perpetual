"""Source evidence (spec §16). Every material fact is traceable to evidence.

Never put credentials or secret values in evidence.
"""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import Confidence, DomainModel, NonEmptyStr


class SourceType(StrEnum):
    """Where a piece of evidence came from."""

    AWS_API = "aws_api"
    AWS_CONFIG = "aws_config"
    RESOURCE_EXPLORER = "resource_explorer"
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"
    CLOUDTRAIL = "cloudtrail"
    VPC_FLOW_LOGS = "vpc_flow_logs"
    INFERENCE = "inference"
    LLM_INFERENCE = "llm_inference"
    USER_CONFIRMATION = "user_confirmation"
    METRIC = "metric"


class Basis(StrEnum):
    """What dependency evidence says about a dependency (spec §14.1)."""

    PERMITTED = "permitted"
    """A connection is allowed (security groups, NetworkPolicies, IAM)."""
    REFERENCED = "referenced"
    """Configuration points at the dependency."""
    OBSERVED = "observed"
    """Traffic or calls were seen (CloudTrail, flow logs)."""
    ASSERTED = "asserted"
    """A person said so."""


class Evidence(DomainModel):
    """One traceable piece of evidence."""

    id: NonEmptyStr
    source_type: SourceType
    basis: Basis | None = None
    """Required for dependency evidence; DependencyEdge enforces that."""
    source: NonEmptyStr
    resource_id: str | None = None
    attribute: str | None = None
    value_summary: str | None = None
    confidence: Confidence
    collected_at: AwareDatetime
    observed_from: AwareDatetime | None = None
    observed_to: AwareDatetime | None = None
    observation_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _observation_window(self) -> Self:
        # Observed evidence (CloudTrail calls, flow-log flows) is stored only as an
        # aggregate: a time window and a count, never the raw events (spec §65-§67).
        # So observed evidence must have all three fields, and other evidence none,
        # otherwise a reader could mistake configuration for observed traffic.
        start, end, count = self.observed_from, self.observed_to, self.observation_count
        if self.basis is Basis.OBSERVED:
            if start is None or end is None or count is None:
                raise ValueError(
                    "observed evidence needs observed_from, observed_to and observation_count"
                )
            if start > end:
                raise ValueError("observed_from must not be after observed_to")
        elif start is not None or end is not None or count is not None:
            raise ValueError("observation window fields are only valid for observed evidence")
        return self
