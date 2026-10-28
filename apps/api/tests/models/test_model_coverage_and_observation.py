"""Scan coverage, freshness policy and resolved observations (spec §14.1, §76.1)."""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import (
    Attribution,
    CoverageStatus,
    FreshnessPolicy,
    ResolvedObservation,
    ScanCoverage,
)
from tests.models.builders import NOW


def coverage(**overrides: Any) -> ScanCoverage:
    fields: dict[str, Any] = {
        "id": "cov-1",
        "account_id": "111122223333",
        "region": "ap-south-1",
        "service": "rds",
        "operation_family": "inventory",
        "status": "complete",
        "started_at": NOW,
        "completed_at": NOW + timedelta(seconds=30),
        "pagination_complete": True,
    }
    fields.update(overrides)
    return ScanCoverage(**fields)


def observation(**overrides: Any) -> ResolvedObservation:
    fields: dict[str, Any] = {
        "id": "obs-1",
        "source_type": "cloudtrail",
        "attribution": "exact",
        "candidate_from_resource_ids": ["aws://1/ap-south-1/ecs/service/checkout"],
        "candidate_to_resource_ids": ["aws://1/ap-south-1/dynamodb/table/orders"],
        "operation": "dynamodb:GetItem",
        "resolution_evidence_ids": ["ev-role"],
        "observed_from": NOW - timedelta(days=7),
        "observed_to": NOW,
        "observation_count": 42,
    }
    fields.update(overrides)
    return ResolvedObservation(**fields)


# --- coverage ----------------------------------------------------------------------


def test_complete_coverage_is_authoritative() -> None:
    assert coverage().is_authoritative


@pytest.mark.parametrize("status", ["partial", "unsupported"])
def test_other_statuses_are_not_authoritative(status: str) -> None:
    assert not coverage(status=status, pagination_complete=None).is_authoritative


def test_interrupted_pagination_is_never_complete() -> None:
    with pytest.raises(ValidationError, match="unfinished pagination"):
        coverage(pagination_complete=False)


def test_complete_coverage_needs_a_completion_time() -> None:
    with pytest.raises(ValidationError, match="needs completed_at"):
        coverage(completed_at=None)


def test_complete_coverage_has_no_errors() -> None:
    with pytest.raises(ValidationError, match="error codes cannot be complete"):
        coverage(error_codes=["ThrottlingException"])


def test_denied_coverage_records_why() -> None:
    with pytest.raises(ValidationError, match="records its error codes"):
        coverage(status="denied")
    assert coverage(status="denied", error_codes=["AccessDenied"]).status is CoverageStatus.DENIED


def test_not_requested_coverage_has_no_times() -> None:
    with pytest.raises(ValidationError, match="no start or completion time"):
        coverage(status="not_requested")
    built = coverage(status="not_requested", started_at=None, completed_at=None)
    assert not built.is_authoritative


def test_requested_coverage_needs_a_start_time() -> None:
    with pytest.raises(ValidationError, match="needs started_at"):
        coverage(status="partial", started_at=None, completed_at=None)


def test_coverage_times_and_window_are_ordered() -> None:
    with pytest.raises(ValidationError, match="completed_at must not be before"):
        coverage(completed_at=NOW - timedelta(seconds=1))
    with pytest.raises(ValidationError, match="set together"):
        coverage(window_start=NOW)
    with pytest.raises(ValidationError, match="window_start must not be after"):
        coverage(window_start=NOW, window_end=NOW - timedelta(hours=1))


def test_checked_identities_are_sorted_and_distinct() -> None:
    built = coverage(checked_identities=["db-b", "db-a"])
    assert built.checked_identities == ["db-a", "db-b"]
    with pytest.raises(ValidationError, match="must not repeat"):
        coverage(checked_identities=["db-a", "db-a"])


def test_freshness_policy_needs_positive_ages() -> None:
    policy = FreshnessPolicy(
        version="1",
        inventory_max_age=timedelta(hours=24),
        measurement_max_age=timedelta(minutes=15),
        primary_dr_max_skew=timedelta(minutes=30),
    )
    assert policy.measurement_max_age == timedelta(minutes=15)
    with pytest.raises(ValidationError):
        policy.model_validate(policy.model_dump() | {"inventory_max_age": timedelta(0)})


# --- resolved observations ---------------------------------------------------------


def test_exact_observation_has_one_resource_at_each_end() -> None:
    assert observation().attribution is Attribution.EXACT
    with pytest.raises(ValidationError, match="exactly one resource at each end"):
        observation(candidate_from_resource_ids=["svc-a", "svc-b"])


def test_exact_observation_cites_what_resolved_it() -> None:
    with pytest.raises(ValidationError, match="cites its resolution evidence"):
        observation(resolution_evidence_ids=[])


def test_shared_role_stays_ambiguous_with_sorted_candidates() -> None:
    built = observation(
        attribution="ambiguous",
        candidate_from_resource_ids=["svc-b", "svc-a"],
        resolution_evidence_ids=[],
    )
    assert built.candidate_from_resource_ids == ["svc-a", "svc-b"]
    # Stored once, against the set: the count is not multiplied per candidate.
    assert built.observation_count == 42


def test_ambiguous_observation_needs_several_candidates() -> None:
    with pytest.raises(ValidationError, match="several candidates at one end"):
        observation(attribution="ambiguous")


def test_observation_needs_a_candidate_at_each_end() -> None:
    with pytest.raises(ValidationError, match="at least one candidate"):
        observation(attribution="ambiguous", candidate_to_resource_ids=[])


def test_observation_window_and_count() -> None:
    with pytest.raises(ValidationError, match="observed_from must not be after"):
        observation(observed_from=NOW + timedelta(seconds=1))
    with pytest.raises(ValidationError):
        observation(observation_count=0)
    with pytest.raises(ValidationError, match="must not repeat"):
        observation(
            attribution="ambiguous",
            candidate_from_resource_ids=["svc-a", "svc-a"],
        )
