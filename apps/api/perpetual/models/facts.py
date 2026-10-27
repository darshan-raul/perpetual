"""Measured and reported facts that are not resource configuration (spec §28.1, §76.1).

Rules need quota headroom, instance-type offerings, Region/feature availability and
CloudWatch metrics (replication lag, usage). These change far faster than
configuration and have their own freshness limits (spec §76.1: 15 minutes for the
latest replication/usage/quota measurement), so they are kept apart from resources.

The guiding rule: missing data stays unknown.

- A metric with no samples is not zero.
- Quota limits without current usage cannot prove there is headroom.
- A feature whose availability no API or versioned catalog establishes is unknown.
- An access failure is recorded as such, never as "no data".
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr


class Fact(DomainModel):
    """Fields every fact carries: where and when it was collected, and how."""

    id: NonEmptyStr
    account_id: NonEmptyStr
    region: NonEmptyStr
    """An AWS Region, or "global"."""
    collected_at: AwareDatetime
    coverage_id: str | None = None
    """The ScanCoverage record of the collection that produced it (spec §76.1)."""
    carried_forward: bool = False
    """True for a previous fact kept as historical context. It keeps its original
    timestamp and cannot satisfy a check on its own (spec §76.1)."""


class QuotaFact(Fact):
    """A Service Quotas limit, with current usage when it could be measured."""

    kind: Literal["quota"] = "quota"
    service_code: NonEmptyStr
    """e.g. fargate, ec2, elasticloadbalancing."""
    quota_code: NonEmptyStr
    quota_name: NonEmptyStr
    value: float | None = Field(default=None, ge=0)
    """The applied limit. None when it could not be read."""
    default_value: float | None = Field(default=None, ge=0)
    adjustable: bool | None = None
    unit: str | None = None
    usage: float | None = Field(default=None, ge=0)
    """Current usage, from CloudWatch AWS/Usage. None when unknown."""
    usage_collected_at: AwareDatetime | None = None

    @property
    def headroom(self) -> float | None:
        """Limit minus usage, or None when either is unknown (spec §28.1).

        A limit alone never proves capacity: the account may already use most of it.
        """
        if self.value is None or self.usage is None:
            return None
        return self.value - self.usage

    @model_validator(mode="after")
    def _usage_has_a_time(self) -> Self:
        if (self.usage is None) != (self.usage_collected_at is None):
            raise ValueError("usage and usage_collected_at are set together")
        return self


class InstanceTypeOfferingFact(Fact):
    """Which instance types a Region or Availability Zone offers."""

    kind: Literal["instance_type_offering"] = "instance_type_offering"
    location_type: Literal["region", "availability-zone"]
    location: NonEmptyStr
    """The Region name, or the AZ name for availability-zone offerings."""
    instance_types: list[NonEmptyStr] = Field(default_factory=list)

    @field_validator("instance_types")
    @classmethod
    def _sorted_distinct(cls, types: list[str]) -> list[str]:
        # A set by meaning; stored sorted so the same offering hashes the same.
        return sorted(set(types))


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class CapabilityFact(Fact):
    """Whether a service, feature or option exists in a Region (REGION-SVC-001)."""

    kind: Literal["capability"] = "capability"
    capability: NonEmptyStr
    """e.g. service:dynamodb, feature:aurora-global-database."""
    status: CapabilityStatus
    source: Literal["api", "versioned_catalog"]
    catalog_version: str | None = None
    """Required when the answer comes from a versioned catalog rather than an API."""

    @model_validator(mode="after")
    def _catalog_answers_are_versioned(self) -> Self:
        if self.source == "versioned_catalog" and not self.catalog_version:
            raise ValueError("a catalog answer names its catalog_version")
        return self


class MetricSample(DomainModel):
    timestamp: AwareDatetime
    value: float


class MetricFact(Fact):
    """A CloudWatch metric series over a window, e.g. replica lag for RPO (spec §51)."""

    kind: Literal["metric"] = "metric"
    resource_id: str | None = None
    """The resource the metric describes, when it maps to one."""
    namespace: NonEmptyStr
    metric_name: NonEmptyStr
    dimensions: dict[str, str] = Field(default_factory=dict)
    statistic: NonEmptyStr
    """e.g. Average, Maximum, p99."""
    unit: str | None = None
    period_seconds: int = Field(ge=1)
    window_start: AwareDatetime
    window_end: AwareDatetime
    status: Literal["ok", "no_data", "access_denied", "error"]
    """no_data and access_denied are different: the second says nothing about the metric."""
    samples: list[MetricSample] = Field(default_factory=list)
    expected_samples: int | None = Field(default=None, ge=0)
    """How many periods the window holds, so gaps are visible as missing samples."""

    @property
    def latest_sample_at(self) -> AwareDatetime | None:
        """Time of the newest sample. Freshness is judged on this, not on collected_at."""
        return self.samples[-1].timestamp if self.samples else None

    @property
    def missing_samples(self) -> int | None:
        if self.expected_samples is None:
            return None
        return max(self.expected_samples - len(self.samples), 0)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.window_start > self.window_end:
            raise ValueError("window_start must not be after window_end")
        # Samples are kept in time order inside the window, so latest_sample_at is right.
        times = [sample.timestamp for sample in self.samples]
        if times != sorted(times):
            raise ValueError("samples must be in time order")
        if any(not self.window_start <= t <= self.window_end for t in times):
            raise ValueError("every sample lies inside the window")
        # Only an "ok" read can carry samples, and an "ok" read has at least one.
        # Otherwise "no data" could be confused with a value of zero.
        if (self.status == "ok") != bool(self.samples):
            raise ValueError("status ok has samples; other statuses have none")
        return self


FactRecord = Annotated[
    QuotaFact | InstanceTypeOfferingFact | CapabilityFact | MetricFact,
    Field(discriminator="kind"),
]
"""Any fact, chosen by `kind`."""
