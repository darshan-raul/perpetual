"""DR requirements, durations and plan buffer (spec §26, §27, §49, §49.2).

Targets exist only at stack level: one RTO and one RPO target per stack and
failure scope.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr


class DRStrategy(StrEnum):
    """Stack-level strategy families (spec §27). Each maps to per-service mechanisms."""

    BACKUP_RESTORE = "backup_restore"
    PILOT_LIGHT = "pilot_light"
    WARM_STANDBY = "warm_standby"
    HOT_STANDBY = "hot_standby"
    ACTIVE_ACTIVE = "active_active"


class EstimateConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DurationEstimate(DomainModel):
    """A duration range without fake statistical precision (spec §49).

    A None bound means that bound is unknown; it is never treated as zero.
    """

    low_seconds: int | None = Field(default=None, ge=0)
    expected_seconds: int | None = Field(default=None, ge=0)
    high_seconds: int | None = Field(default=None, ge=0)
    confidence: EstimateConfidence
    basis: NonEmptyStr

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        # Only the known bounds are compared: a None bound is "unknown", and an
        # unknown value has no order. RTO maths later turns unknown into UNKNOWN,
        # never into zero (spec §30, §49.1).
        known = [
            value
            for value in (self.low_seconds, self.expected_seconds, self.high_seconds)
            if value is not None
        ]
        if known != sorted(known):
            raise ValueError("duration bounds must satisfy low <= expected <= high")
        return self


class BufferPolicy(DomainModel):
    """Explicit plan buffer, shown separately from estimates (spec §49.2)."""

    handoff: DurationEstimate | None = None
    """Added before every manual or semi-automatic action."""
    stack_validation: DurationEstimate | None = None
    """One stack-wide validation action before the traffic switch."""
    contingency_percent: Decimal = Field(ge=0)


class FailureScope(StrEnum):
    AZ = "az"
    REGION = "region"


class RecoveryRequirement(DomainModel):
    """What a stack must achieve for one failure scope."""

    id: NonEmptyStr
    revision: int = Field(ge=1)
    stack_id: NonEmptyStr
    failure_scope: FailureScope
    target_rto_seconds: int = Field(gt=0)
    target_rpo_seconds: int = Field(ge=0)
    max_monthly_dr_cost_usd: Decimal | None = Field(default=None, ge=0)
    """Total steady-state DR cost (spec §59.1). None disables only the budget gate."""
    workload_profile_id: str | None = None
    preferred_strategy: DRStrategy | None = None
    target_region: str | None = None
    """Required for Region failure. The only place the DR Region is defined."""
    target_account_id: str | None = None
    """None means the primary account (spec §66)."""
    detection_and_decision_seconds: DurationEstimate | None = None
    """None means the catalog default, marked low confidence."""
    buffer: BufferPolicy | None = None
    """None means catalog defaults."""

    @model_validator(mode="after")
    def _region_target(self) -> Self:
        # Surviving a Region failure means recovering somewhere else, so the target
        # Region is part of the requirement. An AZ failure recovers in the same Region.
        if self.failure_scope is FailureScope.REGION and not self.target_region:
            raise ValueError("a Region failure requirement needs target_region")
        return self
