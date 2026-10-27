"""Evidence and resource nodes (spec §15, §16)."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from perpetual.models import Basis, ResourceNode
from tests.models.builders import NOW, make_evidence


def test_observed_evidence_needs_a_window() -> None:
    with pytest.raises(ValidationError, match="observed evidence needs"):
        make_evidence(basis=Basis.OBSERVED)


def test_observed_evidence_with_window_is_valid() -> None:
    evidence = make_evidence(
        basis=Basis.OBSERVED,
        observed_from=NOW - timedelta(days=7),
        observed_to=NOW,
        observation_count=42,
    )
    assert evidence.observation_count == 42


def test_observed_window_must_be_in_order() -> None:
    with pytest.raises(ValidationError, match="must not be after"):
        make_evidence(
            basis=Basis.OBSERVED,
            observed_from=NOW,
            observed_to=NOW - timedelta(days=1),
            observation_count=1,
        )


def test_window_fields_only_for_observed_evidence() -> None:
    with pytest.raises(ValidationError, match="only valid for observed"):
        make_evidence(basis=Basis.REFERENCED, observation_count=3)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_is_bounded(confidence: float) -> None:
    with pytest.raises(ValidationError):
        make_evidence(confidence=confidence)


def test_timestamps_need_a_timezone() -> None:
    with pytest.raises(ValidationError):
        make_evidence(collected_at=datetime(2026, 10, 28, 12, 0))


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_evidence(secret_value="hunter2")


def test_models_are_immutable() -> None:
    evidence = make_evidence()
    with pytest.raises(ValidationError):
        evidence.confidence = 0.5  # type: ignore[misc]


def test_resource_node_defaults() -> None:
    node = ResourceNode(
        id="aws://123456789012/ap-south-1/rds/db/prod-mysql",
        provider="aws",
        service="rds",
        resource_type="db",
        discovered_at=NOW,
    )
    assert node.planned is False
    assert node.tags == {}
    assert node.source_refs == []
