"""Stacks, requirements, durations, mechanisms and overrides (spec §23, §24, §26, §27.1, §49)."""

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import (
    DependencyGroup,
    DurationEstimate,
    EstimateConfidence,
    FailureScope,
    GraphOverride,
    GroupMode,
    GroupScope,
    MechanismKind,
    OverrideKind,
    RecoveryMechanism,
    RecoveryRequirement,
    Stack,
    StackCriticality,
)
from perpetual.models.override import AddEdgePayload
from tests.models.builders import NOW


def test_stack_roots_must_be_members() -> None:
    with pytest.raises(ValidationError, match="root resources must be stack members"):
        Stack(
            id="checkout",
            name="checkout",
            criticality=StackCriticality.CRITICAL,
            root_resource_ids=["r1"],
            resource_ids=["r2"],
            primary_region="ap-south-1",
            discovery_confidence=0.8,
        )


def make_requirement(**overrides: Any) -> RecoveryRequirement:
    fields: dict[str, Any] = {
        "id": "req-1",
        "revision": 1,
        "stack_id": "checkout",
        "failure_scope": FailureScope.REGION,
        "target_rto_seconds": 1800,
        "target_rpo_seconds": 300,
        "target_region": "ap-south-2",
        "max_monthly_dr_cost_usd": Decimal("1200"),
    }
    fields.update(overrides)
    return RecoveryRequirement(**fields)


def test_region_requirement_needs_target_region() -> None:
    with pytest.raises(ValidationError, match="needs target_region"):
        make_requirement(target_region=None)


def test_az_requirement_needs_no_target_region() -> None:
    assert make_requirement(failure_scope=FailureScope.AZ, target_region=None).target_region is None


def test_rto_target_must_be_positive_and_rpo_may_be_zero() -> None:
    with pytest.raises(ValidationError):
        make_requirement(target_rto_seconds=0)
    assert make_requirement(target_rpo_seconds=0).target_rpo_seconds == 0


def test_duration_bounds_are_ordered() -> None:
    with pytest.raises(ValidationError, match="low <= expected <= high"):
        DurationEstimate(
            low_seconds=600,
            expected_seconds=300,
            confidence=EstimateConfidence.MEDIUM,
            basis="catalog",
        )


def test_unknown_duration_bounds_stay_unknown() -> None:
    estimate = DurationEstimate(
        expected_seconds=420, confidence=EstimateConfidence.LOW, basis="catalog default"
    )
    assert estimate.low_seconds is None
    assert estimate.high_seconds is None


def make_mechanism(**overrides: Any) -> RecoveryMechanism:
    fields: dict[str, Any] = {
        "id": "mech-1",
        "primary_resource_id": "aws://1/ap-south-1/rds/db/checkout",
        "target_region": "ap-south-2",
        "target_account_id": "123456789012",
        "kind": MechanismKind.LIVE_COUNTERPART,
        "control_plane_dependent": False,
        "confidence": 0.9,
    }
    fields.update(overrides)
    return RecoveryMechanism(**fields)


def test_mechanism_groups_are_dr_side() -> None:
    group = DependencyGroup(
        id="g",
        dependent_resource_id="aws://1/ap-south-2/rds/db/checkout-replica",
        member_edge_ids=["e1"],
        mode=GroupMode.ALL,
        scope=GroupScope.PRIMARY,
    )
    with pytest.raises(ValidationError, match="scope dr"):
        make_mechanism(dependency_groups=[group])


def make_override(kind: OverrideKind, payload: dict[str, Any]) -> GraphOverride:
    return GraphOverride(
        id="ov-1",
        project_id="p1",
        kind=kind,
        target="aws://1/ap-south-1/ecs/service/checkout",
        payload=payload,
        author="darshan",
        created_at=NOW,
    )


def test_add_edge_payload_is_validated_and_typed() -> None:
    override = make_override(
        OverrideKind.ADD_EDGE,
        {
            "from_resource_id": "a",
            "to_resource_id": "b",
            "relationship_type": "depends_on",
            "criticality": "required",
        },
    )
    assert isinstance(override.typed_payload(), AddEdgePayload)


@pytest.mark.parametrize(
    ("kind", "payload", "message"),
    [
        (OverrideKind.ADD_EDGE, {"from_resource_id": "a"}, "Field required"),
        (OverrideKind.EDIT_EDGE, {}, "must change relationship_type or criticality"),
        (OverrideKind.EDIT_NODE, {"stack_id": "checkout"}, "must change membership"),
        (OverrideKind.CONFIRM_EDGE, {"unexpected": 1}, "Extra inputs"),
        (
            OverrideKind.ADD_NODE,
            {
                "node_kind": "external",
                "resource_id": "external://payments",
                "provider": "aws",
                "service": "payments-gateway",
                "resource_type": "saas",
            },
            'provider "external"',
        ),
        (
            OverrideKind.ADD_NODE,
            {
                "node_kind": "placeholder",
                "resource_id": "aws://1/ap-south-1/sqs/queue/orders",
                "provider": "aws",
                "service": "sqs",
                "resource_type": "queue",
                "dr_posture": "available",
            },
            "only declared for external",
        ),
    ],
)
def test_override_payload_must_match_its_kind(
    kind: OverrideKind, payload: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_override(kind, payload)
