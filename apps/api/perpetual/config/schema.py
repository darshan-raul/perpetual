"""Typed configuration models (IMPL_PLAN D12).

Every number that tunes behaviour lives in YAML under `config/defaults/` and is
loaded into these models; rule and engine code never hard-codes one. Unknown keys
are rejected, so a typo in a project override fails loudly instead of being
ignored.

`config` may not import other Perpetual packages (an import rule), so freshness
here is its own model; callers build `models.FreshnessPolicy` from it.
"""

import re
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

_TYPE_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")


def _type_key(value: str) -> str:
    if not _TYPE_KEY.match(value):
        raise ValueError(f"not a SERVICE/TYPE type key: {value!r}")
    return value


TypeKey = Annotated[str, AfterValidator(_type_key)]
Version = Annotated[str, Field(min_length=1)]


class ConfigModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceWeight(ConfigModel):
    weight: float = Field(ge=0.0, le=1.0)
    group: str
    supporting_only: bool = False
    """Too broad to suggest a dependency alone; only supports other evidence."""

    @model_validator(mode="after")
    def _supporting_weighs_nothing(self) -> Self:
        if self.supporting_only and self.weight != 0:
            raise ValueError("supporting-only evidence has weight 0")
        return self


class EvidenceConfig(ConfigModel):
    """Evidence weights and correlation groups (spec §22, §23)."""

    version: Version
    combination: Literal["noisy_or"]
    """Name of the cross-group combination function. Pluggable (spec §22): the
    evidence package registers implementations; new names are added here."""
    review_confidence_threshold: float = Field(gt=0.0, le=1.0)
    correlation_groups: list[str] = Field(min_length=1)
    weights: dict[str, EvidenceWeight] = Field(min_length=1)

    @model_validator(mode="after")
    def _groups_exist(self) -> Self:
        if len(set(self.correlation_groups)) != len(self.correlation_groups):
            raise ValueError("correlation groups must not repeat")
        known = set(self.correlation_groups)
        for kind, weight in self.weights.items():
            if weight.group not in known:
                raise ValueError(f"evidence {kind!r} names unknown group {weight.group!r}")
        return self


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScoringConfig(ConfigModel):
    """Descriptive score weights per finding severity (spec §31). Never decides readiness."""

    version: Version
    severity_weights: dict[Severity, int]

    @model_validator(mode="after")
    def _complete_and_ordered(self) -> Self:
        if set(self.severity_weights) != set(Severity):
            raise ValueError("every severity needs a weight")
        ordered = [self.severity_weights[s] for s in Severity]
        if any(w > 0 for w in ordered) or ordered != sorted(ordered):
            raise ValueError("weights are <= 0 and less severe findings never cost more")
        return self


class OutOfScopeCategory(StrEnum):
    MONITORING = "monitoring"
    LOGGING = "logging"
    CICD = "cicd"


class RtoScopeConfig(ConfigModel):
    """Types out of RTO scope by default (spec §24.1)."""

    version: Version
    out_of_scope: dict[OutOfScopeCategory, list[TypeKey]]

    @property
    def out_of_scope_type_keys(self) -> frozenset[str]:
        return frozenset(key for keys in self.out_of_scope.values() for key in keys)

    def category_of(self, type_key: str) -> OutOfScopeCategory | None:
        for category, keys in self.out_of_scope.items():
            if type_key in keys:
                return category
        return None

    @model_validator(mode="after")
    def _each_type_once(self) -> Self:
        keys = [key for keys in self.out_of_scope.values() for key in keys]
        if len(set(keys)) != len(keys):
            raise ValueError("a type key is listed in one out-of-scope category, once")
        return self


class BufferConfig(ConfigModel):
    """Plan buffer defaults (spec §49.2)."""

    version: Version
    contingency_percent: Decimal = Field(ge=0)
    handoff_catalog_key: str = Field(min_length=1)
    stack_validation_catalog_key: str = Field(min_length=1)


class FreshnessConfig(ConfigModel):
    """Maximum fact ages (spec §76.1). Same fields as `models.FreshnessPolicy`."""

    version: Version
    inventory_max_age: timedelta = Field(gt=timedelta(0))
    measurement_max_age: timedelta = Field(gt=timedelta(0))
    primary_dr_max_skew: timedelta = Field(ge=timedelta(0))


class CostUnits(ConfigModel):
    hours_per_month: Decimal = Field(gt=0)
    price_max_age: timedelta = Field(gt=timedelta(0))

    @property
    def days_per_month(self) -> Decimal:
        """Monthly days follow from monthly hours (spec §59.1: 730 hours, 730/24 days)."""
        return self.hours_per_month / 24


class LimitsConfig(ConfigModel):
    version: Version
    alternative_selection_cap: int = Field(ge=1)
    """Member-set combinations compared per selection (spec §19.1)."""
    cost: CostUnits


class Config(ConfigModel):
    """All tunable configuration, after defaults and any project overrides."""

    evidence: EvidenceConfig
    scoring: ScoringConfig
    rto_scope: RtoScopeConfig
    buffer: BufferConfig
    freshness: FreshnessConfig
    limits: LimitsConfig
    overridden_paths: list[str] = Field(default_factory=list)
    """Dotted paths a project override changed, sorted. Recorded with every
    evaluation so results show which values were not product defaults (§76.1)."""

    @property
    def versions(self) -> dict[str, str]:
        """Version of each section, e.g. {"evidence": "1", ...}."""
        return {
            name: getattr(self, name).version
            for name in ("evidence", "scoring", "rto_scope", "buffer", "freshness", "limits")
        }
