"""DR drill results (spec §53).

Only the schema ships now; importing drill evidence is post-MVP (P14). Until a
matching drill exists, a stack's readiness tier is at most CONFIGURED.
"""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import Digest, DomainModel, NonEmptyStr


class DrillSource(StrEnum):
    """Where a drill result comes from, most preferred first (spec §53)."""

    ARC_EXECUTION_REPORT = "arc_execution_report"
    RECOVERY_SCRIPT_LOG = "recovery_script_log"
    """The timestamped log of a recovery-script run (spec §63.2)."""
    FAULT_INJECTION = "fault_injection"
    RESILIENCE_HUB_TEST = "resilience_hub_test"


class DrillStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    ABORTED = "aborted"


class DRDrill(DomainModel):
    id: NonEmptyStr
    stack_id: NonEmptyStr
    source: DrillSource
    source_reference: NonEmptyStr
    """e.g. the execution-report location or the log file path."""
    started_at: AwareDatetime
    completed_at: AwareDatetime
    achieved_rto_seconds: int | None = Field(default=None, ge=0)
    achieved_rpo_seconds: int | None = Field(default=None, ge=0)
    """None when the drill did not measure it. Never assumed zero."""
    status: DrillStatus
    observations: list[NonEmptyStr] = Field(default_factory=list)
    evaluation_input_digest: Digest | None = None
    design_digest: Digest | None = None
    """The scan and approved design the drill tested; P14-01 binds them."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not be before started_at")
        return self
