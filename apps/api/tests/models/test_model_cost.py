"""Workload profiles and cost estimates (spec §59.1)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import (
    CostEstimate,
    CostKind,
    CostLineItem,
    WorkloadProfile,
    WorkloadQuantity,
)
from tests.models.builders import NOW


def quantity(**overrides: Any) -> WorkloadQuantity:
    fields: dict[str, Any] = {
        "kind": "replication_gb_per_month",
        "resource_id": "aws://1/ap-south-1/rds/db/orders",
        "low": "40",
        "expected": "55",
        "high": "70",
        "unit": "GB",
        "source": "measured",
        "observed_from": NOW - timedelta(days=14),
        "observed_to": NOW,
        "collected_at": NOW,
        "confidence": "medium",
    }
    fields.update(overrides)
    return WorkloadQuantity(**fields)


def line(key: str, **overrides: Any) -> CostLineItem:
    fields: dict[str, Any] = {
        "key": key,
        "description": key,
        "region": "ap-south-2",
        "kind": "fixed",
        "low_usd": "10",
        "expected_usd": "12",
        "high_usd": "15",
    }
    fields.update(overrides)
    return CostLineItem(**fields)


def estimate(*lines: CostLineItem, **overrides: Any) -> CostEstimate:
    fields: dict[str, Any] = {
        "id": "cost-1",
        "stack_id": "checkout",
        "scope": "steady_state_dr",
        "price_catalog_version": "2026-10-01",
        "prices_collected_at": NOW,
        "line_items": list(lines),
        "confidence": "medium",
    }
    fields.update(overrides)
    return CostEstimate(**fields)


# --- workload ----------------------------------------------------------------------


def test_measured_quantity_needs_its_window() -> None:
    with pytest.raises(ValidationError, match="needs its observation window"):
        quantity(observed_from=None, observed_to=None)
    with pytest.raises(ValidationError, match="set together"):
        quantity(observed_to=None)


def test_estimates_record_their_assumptions() -> None:
    with pytest.raises(ValidationError, match="records its assumptions"):
        quantity(source="user_estimate", observed_from=None, observed_to=None)
    built = quantity(
        source="forecast", observed_from=None, observed_to=None, assumptions=["Q4 peak x2"]
    )
    assert built.assumptions == ["Q4 peak x2"]


def test_quantity_bounds_are_ordered_and_may_be_unknown() -> None:
    with pytest.raises(ValidationError, match="low <= expected <= high"):
        quantity(low="80")
    assert quantity(expected=None).expected is None


def test_profile_holds_one_value_per_quantity() -> None:
    profile = WorkloadProfile(id="wp", revision=1, stack_id="checkout", quantities=[quantity()])
    assert len(profile.quantities) == 1
    with pytest.raises(ValidationError, match="appears once"):
        WorkloadProfile(
            id="wp", revision=1, stack_id="checkout", quantities=[quantity(), quantity()]
        )


# --- cost --------------------------------------------------------------------------


def test_totals_and_subtotals_come_from_the_lines() -> None:
    built = estimate(
        line("rds-replica"),
        line("transfer", kind="variable", low_usd="1", expected_usd="2", high_usd="3"),
    )
    assert (built.low_usd, built.expected_usd, built.high_usd) == (
        Decimal(11),
        Decimal(14),
        Decimal(18),
    )
    assert built.total("high", CostKind.FIXED) == Decimal(15)
    assert built.total("high", CostKind.VARIABLE) == Decimal(3)


def test_an_unknown_line_makes_the_total_unknown() -> None:
    built = estimate(line("rds-replica"), line("transfer", kind="variable", high_usd=None))
    assert built.high_usd is None
    # The fixed subtotal is still known, but it can't stand in for the total.
    assert built.total("high", CostKind.FIXED) == Decimal(15)
    assert built.low_usd == Decimal(20)


def test_an_empty_estimate_is_zero() -> None:
    assert estimate().high_usd == Decimal(0)


def test_zero_needs_a_reason() -> None:
    with pytest.raises(ValidationError, match="says why it is zero"):
        line("free", low_usd="0", expected_usd="0", high_usd="0")
    built = line("free", low_usd="0", expected_usd="0", high_usd="0", zero_reason="free tier")
    assert built.high_usd == 0
    with pytest.raises(ValidationError, match="only for a line whose high bound is zero"):
        line("paid", zero_reason="free tier")


def test_line_keys_are_unique_so_shared_costs_count_once() -> None:
    with pytest.raises(ValidationError, match="keys must be unique"):
        estimate(line("vpc-nat", shared=True), line("vpc-nat", shared=True))


def test_cost_bounds_are_ordered_and_nonnegative() -> None:
    with pytest.raises(ValidationError, match="low <= expected <= high"):
        line("x", low_usd="20")
    with pytest.raises(ValidationError):
        line("x", low_usd="-1")


def test_workload_profile_reference_is_complete() -> None:
    with pytest.raises(ValidationError, match="set together"):
        estimate(workload_profile_id="wp")
    assert estimate(workload_profile_id="wp", workload_profile_revision=2).currency == "USD"
