"""Workload inputs and DR cost estimates (spec §59, §59.1).

Missing usage or prices stay unknown, never zero: an unknown line makes the
matching total unknown, and a fixed-cost subtotal can't hide it. Budget PASS needs
the high bound within budget, so a range with an unknown high bound can't pass.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr
from perpetual.models.requirement import EstimateConfidence


class QuantityKind(StrEnum):
    """Workload quantities that cost formulas can require (spec §59.1)."""

    REQUESTS = "requests"
    INVOCATIONS = "invocations"
    DURATION = "duration"
    CONCURRENCY = "concurrency"
    MESSAGES = "messages"
    STORED_GB = "stored_gb"
    WRITE_GB_PER_MONTH = "write_gb_per_month"
    REPLICATION_GB_PER_MONTH = "replication_gb_per_month"
    EGRESS_GB_PER_MONTH = "egress_gb_per_month"
    SERVING_CAPACITY = "serving_capacity"


class QuantitySource(StrEnum):
    MEASURED = "measured"
    """From read-only metrics over an observation window."""
    USER_ESTIMATE = "user_estimate"
    FORECAST = "forecast"


def _ordered(low: Decimal | None, expected: Decimal | None, high: Decimal | None) -> bool:
    known = [value for value in (low, expected, high) if value is not None]
    return known == sorted(known)


class WorkloadQuantity(DomainModel):
    kind: QuantityKind
    resource_id: str | None = None
    """The resource it describes, or None for a stack-wide quantity."""
    low: Decimal | None = Field(default=None, ge=0)
    expected: Decimal | None = Field(default=None, ge=0)
    high: Decimal | None = Field(default=None, ge=0)
    unit: NonEmptyStr
    source: QuantitySource
    observed_from: AwareDatetime | None = None
    observed_to: AwareDatetime | None = None
    collected_at: AwareDatetime
    confidence: EstimateConfidence
    expires_at: AwareDatetime | None = None
    assumptions: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not _ordered(self.low, self.expected, self.high):
            raise ValueError("quantity bounds must satisfy low <= expected <= high")
        start, end = self.observed_from, self.observed_to
        if (start is None) != (end is None):
            raise ValueError("observed_from and observed_to are set together")
        has_window = start is not None and end is not None
        if start is not None and end is not None and start > end:
            raise ValueError("observed_from must not be after observed_to")
        # A measurement says where it was measured; an estimate says why it was
        # chosen. Estimates never become measured evidence (spec §59.1).
        if self.source is QuantitySource.MEASURED and not has_window:
            raise ValueError("a measured quantity needs its observation window")
        if self.source is not QuantitySource.MEASURED and not self.assumptions:
            raise ValueError("an estimate or forecast records its assumptions")
        return self


class WorkloadProfile(DomainModel):
    """Versioned, stack-scoped workload inputs for cost formulas (spec §59.1).

    A quantity that is not listed is unknown; it is never assumed idle.
    """

    id: NonEmptyStr
    revision: int = Field(ge=1)
    stack_id: NonEmptyStr
    quantities: list[WorkloadQuantity] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_value_per_quantity(self) -> Self:
        # A user override takes precedence only for the quantity it names, so the
        # profile holds the one winning value per (resource, kind).
        keys = [(q.resource_id, q.kind) for q in self.quantities]
        if len(set(keys)) != len(keys):
            raise ValueError("each (resource_id, kind) quantity appears once")
        return self


class CostKind(StrEnum):
    FIXED = "fixed"
    VARIABLE = "variable"


class CostLineItem(DomainModel):
    key: NonEmptyStr
    """Unique billable resource/component key, so shared foundations count once."""
    resource_id: str | None = None
    description: NonEmptyStr
    region: NonEmptyStr
    kind: CostKind
    low_usd: Decimal | None = Field(default=None, ge=0)
    expected_usd: Decimal | None = Field(default=None, ge=0)
    high_usd: Decimal | None = Field(default=None, ge=0)
    """Monthly bounds. None means unknown (missing price or usage), never zero."""
    required_quantities: list[QuantityKind] = Field(default_factory=list)
    zero_reason: str | None = None
    """Why the line is zero. Zero is allowed only when the component is
    demonstrably free or unused (spec §59.1)."""
    shared: bool = False
    """A shared foundation, attributed once to this stack."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not _ordered(self.low_usd, self.expected_usd, self.high_usd):
            raise ValueError("cost bounds must satisfy low <= expected <= high")
        if self.high_usd == 0 and not self.zero_reason:
            raise ValueError("a zero-cost line says why it is zero")
        if self.zero_reason and self.high_usd != 0:
            raise ValueError("zero_reason is only for a line whose high bound is zero")
        return self


class CostScope(StrEnum):
    STEADY_STATE_DR = "steady_state_dr"
    """Total monthly DR ownership: what the requirement budget covers."""
    ONE_TIME_SETUP = "one_time_setup"
    FAILOVER_OPERATING = "failover_operating"
    """Temporary cost while running in the DR Region. Not in the monthly budget."""


def _sum(values: list[Decimal | None]) -> Decimal | None:
    # Any unknown bound makes the total unknown, so it can't be hidden by known lines.
    if any(value is None for value in values):
        return None
    return sum((v for v in values if v is not None), Decimal(0))


class CostEstimate(DomainModel):
    """A cost estimate for one candidate or the current DR design (spec §59.1).

    Totals and subtotals are computed from the lines, so they can't disagree.
    """

    id: NonEmptyStr
    stack_id: NonEmptyStr
    scope: CostScope
    currency: Literal["USD"] = "USD"
    price_catalog_version: NonEmptyStr
    prices_collected_at: AwareDatetime
    """When the price catalog was fetched; its age is judged against config."""
    workload_profile_id: str | None = None
    workload_profile_revision: int | None = Field(default=None, ge=1)
    line_items: list[CostLineItem] = Field(default_factory=list)
    confidence: EstimateConfidence
    assumptions: list[NonEmptyStr] = Field(default_factory=list)
    exclusions: list[NonEmptyStr] = Field(default_factory=list)
    """Named beside every budget result, e.g. one-time seeding and failover cost."""

    def _lines(self, kind: CostKind | None) -> list[CostLineItem]:
        return [line for line in self.line_items if kind is None or line.kind is kind]

    def total(
        self, bound: Literal["low", "expected", "high"], kind: CostKind | None = None
    ) -> Decimal | None:
        """Monthly total for one bound, optionally fixed or variable lines only."""
        return _sum([getattr(line, f"{bound}_usd") for line in self._lines(kind)])

    @property
    def low_usd(self) -> Decimal | None:
        return self.total("low")

    @property
    def expected_usd(self) -> Decimal | None:
        return self.total("expected")

    @property
    def high_usd(self) -> Decimal | None:
        return self.total("high")

    @model_validator(mode="after")
    def _check(self) -> Self:
        keys = [line.key for line in self.line_items]
        if len(set(keys)) != len(keys):
            raise ValueError("line item keys must be unique")
        if (self.workload_profile_id is None) != (self.workload_profile_revision is None):
            raise ValueError("workload_profile_id and workload_profile_revision are set together")
        return self
