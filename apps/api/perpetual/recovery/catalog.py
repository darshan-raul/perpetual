"""Versioned duration catalog loader and bucket matching (spec §49.1)."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import Field

from perpetual.models import DomainModel, DurationEstimate, EstimateConfidence, NonEmptyStr


class DurationBucket(DomainModel):
    """One volumetric bucket rule inside a catalog action entry."""

    when: dict[str, str] = Field(default_factory=dict)
    low: int = Field(ge=0)
    expected: int = Field(ge=0)
    high: int = Field(ge=0)


class CatalogActionEntry(DomainModel):
    """One action definition in `duration_catalog.yaml`."""

    phase: NonEmptyStr
    confidence: EstimateConfidence
    basis: NonEmptyStr
    low: int | None = Field(default=None, ge=0)
    expected: int | None = Field(default=None, ge=0)
    high: int | None = Field(default=None, ge=0)
    buckets: list[DurationBucket] = Field(default_factory=list)


class DurationCatalog(DomainModel):
    """Versioned catalog of action durations (spec §49.1).

    An action with no catalog entry (and no project override) receives
    `expected_seconds=None`, making RTO UNKNOWN rather than zero.
    """

    catalog_version: NonEmptyStr
    actions: dict[str, CatalogActionEntry]

    def estimate(
        self,
        action_type: str,
        *,
        attributes: Mapping[str, float | int | None] | None = None,
        override: DurationEstimate | None = None,
    ) -> DurationEstimate:
        """Return a `DurationEstimate` recording `catalog_version` and matched bucket."""
        if override is not None:
            return override

        entry = self.actions.get(action_type)
        if entry is None:
            return DurationEstimate(
                low_seconds=None,
                expected_seconds=None,
                high_seconds=None,
                confidence=EstimateConfidence.LOW,
                basis=(
                    f"missing duration catalog entry for {action_type!r} "
                    f"(catalog {self.catalog_version})"
                ),
            )

        if entry.buckets:
            bucket, bucket_label = _select_bucket(entry.buckets, attributes or {})
            return DurationEstimate(
                low_seconds=bucket.low,
                expected_seconds=bucket.expected,
                high_seconds=bucket.high,
                confidence=entry.confidence,
                basis=(f"{entry.basis} [catalog={self.catalog_version}, bucket={bucket_label}]"),
            )

        return DurationEstimate(
            low_seconds=entry.low,
            expected_seconds=entry.expected,
            high_seconds=entry.high,
            confidence=entry.confidence,
            basis=f"{entry.basis} [catalog={self.catalog_version}]",
        )


def load_duration_catalog(path: Path | None = None) -> DurationCatalog:
    """Load the shipped duration catalog YAML, or a custom file path."""
    if path is not None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        default_text = (
            files("perpetual.config.defaults")
            .joinpath("duration_catalog.yaml")
            .read_text(encoding="utf-8")
        )
        raw = yaml.safe_load(default_text)
    return DurationCatalog.model_validate(raw)


def _select_bucket(
    buckets: list[DurationBucket],
    attributes: Mapping[str, float | int | None],
) -> tuple[DurationBucket, str]:
    """Match the first bucket whose `when` predicates hold; fall back to the first bucket."""
    for bucket in buckets:
        if _matches_all(bucket.when, attributes):
            label = ", ".join(f"{k}:{v}" for k, v in sorted(bucket.when.items()))
            return bucket, label
    first = buckets[0]
    label = ", ".join(f"{k}:{v}" for k, v in sorted(first.when.items())) + " (default)"
    return first, label


def _matches_all(
    predicates: Mapping[str, str],
    attributes: Mapping[str, float | int | None],
) -> bool:
    for key, expr in predicates.items():
        value = attributes.get(key)
        if value is None or not _matches_expr(float(value), expr):
            return False
    return True


def _matches_expr(value: float, expr: str) -> bool:
    cleaned = expr.strip()
    if cleaned.startswith("<="):
        return value <= float(cleaned[2:])
    if cleaned.startswith(">="):
        return value >= float(cleaned[2:])
    if cleaned.startswith("<"):
        return value < float(cleaned[1:])
    if cleaned.startswith(">"):
        return value > float(cleaned[1:])
    if "-" in cleaned:
        low_str, _, high_str = cleaned.partition("-")
        return float(low_str) <= value <= float(high_str)
    return value == float(cleaned)
