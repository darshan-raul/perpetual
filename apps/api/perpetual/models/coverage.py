"""Scan coverage, presence and freshness policy (spec §76.1).

A verdict is only as good as the collection behind it. Every normalized fact points
at the `ScanCoverage` record of the collection that produced it, so the engine can
tell "checked and absent" from "never checked" and return UNKNOWN with
`coverage_incomplete` or `evidence_stale` instead of guessing.
"""

from datetime import timedelta
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr, SortedIds


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    """Some of the operation family succeeded, e.g. a list worked but a detail call failed."""
    DENIED = "denied"
    UNSUPPORTED = "unsupported"
    """The service or operation does not exist in this account or Region."""
    NOT_REQUESTED = "not_requested"


class ScanCoverage(DomainModel):
    """What one collection run checked, for one account, scope, service and operation family."""

    id: NonEmptyStr
    account_id: NonEmptyStr
    region: NonEmptyStr
    """An AWS Region, or "global"."""
    service: NonEmptyStr
    operation_family: NonEmptyStr
    """e.g. inventory, detail, metrics, policy."""
    window_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None
    """The inventory or metric window, when the operation reads one."""
    status: CoverageStatus
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    pagination_complete: bool | None = None
    """None when the operation does not paginate."""
    error_codes: SortedIds = Field(default_factory=list)
    checked_identities: SortedIds = Field(default_factory=list)
    """The resource identities actually checked."""
    checked_attributes: SortedIds = Field(default_factory=list)

    @property
    def is_authoritative(self) -> bool:
        """Only complete coverage can confirm that something is absent (spec §76.1)."""
        return self.status is CoverageStatus.COMPLETE

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("window_start and window_end are set together")
        if self.window_start and self.window_end and self.window_start > self.window_end:
            raise ValueError("window_start must not be after window_end")
        if self.status is CoverageStatus.NOT_REQUESTED:
            if self.started_at or self.completed_at:
                raise ValueError("not_requested coverage has no start or completion time")
            return self
        if self.started_at is None:
            raise ValueError(f"{self.status} coverage needs started_at")
        if self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at must not be before started_at")
        if self.status is CoverageStatus.COMPLETE:
            # An interrupted page sequence is never complete inventory, and a run
            # that recorded errors did not check everything (spec §76.1).
            if self.completed_at is None:
                raise ValueError("complete coverage needs completed_at")
            if self.pagination_complete is False:
                raise ValueError("coverage with unfinished pagination cannot be complete")
            if self.error_codes:
                raise ValueError("coverage with error codes cannot be complete")
        if self.status is CoverageStatus.DENIED and not self.error_codes:
            raise ValueError("denied coverage records its error codes")
        return self


class Presence(StrEnum):
    """Whether a resource or attribute exists, as far as coverage can tell (spec §76.1).

    Failed, denied, unsupported or unrequested discovery gives UNKNOWN. It never
    deletes a resource, orphans an override or proves mechanism `none`.
    """

    PRESENT = "present"
    CONFIRMED_ABSENT = "confirmed_absent"
    """Only after complete, authoritative inventory of the resource's ownership scope."""
    UNKNOWN = "unknown"


class FreshnessPolicy(DomainModel):
    """Maximum fact ages by fact family (spec §76.1).

    The values come from versioned YAML configuration, never from code. The
    version is recorded in every EvaluationInput.
    """

    version: NonEmptyStr
    inventory_max_age: timedelta = Field(gt=timedelta(0))
    """Inventory and configuration."""
    measurement_max_age: timedelta = Field(gt=timedelta(0))
    """The latest replication, usage or quota measurement."""
    primary_dr_max_skew: timedelta = Field(ge=timedelta(0))
    """Largest gap between primary and DR inventory completion times."""
