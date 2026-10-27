"""Dependency edges and groups (spec §19, §19.1, §20)."""

from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import (
    Basis,
    Criticality,
    DependencyEdge,
    DependencyGroup,
    EdgeOrigin,
    GroupMode,
    GroupScope,
    RelationshipType,
    ReviewState,
    SourceType,
)
from tests.models.builders import NOW, make_evidence


def make_edge(**overrides: Any) -> DependencyEdge:
    fields: dict[str, Any] = {
        "id": "edge-1",
        "from_resource_id": "aws://1/ap-south-1/ecs/service/checkout",
        "to_resource_id": "aws://1/ap-south-1/rds/db/checkout",
        "relationship_type": RelationshipType.DEPENDS_ON,
        "confidence": 0.94,
        "evidence": [make_evidence()],
        "inferred": True,
        "origin": EdgeOrigin.DISCOVERED,
        "criticality": Criticality.REQUIRED,
    }
    fields.update(overrides)
    return DependencyEdge(**fields)


def test_bases_are_derived_from_evidence() -> None:
    edge = make_edge(
        evidence=[
            make_evidence(id="a", basis=Basis.PERMITTED),
            make_evidence(id="b", basis=Basis.REFERENCED),
            make_evidence(
                id="c",
                source_type=SourceType.CLOUDTRAIL,
                basis=Basis.OBSERVED,
                observed_from=NOW,
                observed_to=NOW,
                observation_count=5,
            ),
        ]
    )
    assert edge.bases == {Basis.PERMITTED, Basis.REFERENCED, Basis.OBSERVED}


def test_dependency_evidence_needs_a_basis() -> None:
    with pytest.raises(ValidationError, match="needs a basis"):
        make_edge(evidence=[make_evidence(basis=None)])


def user_evidence() -> Any:
    return make_evidence(source_type=SourceType.USER_CONFIRMATION, basis=Basis.ASSERTED)


def test_user_edge_is_certain_and_asserted() -> None:
    edge = make_edge(
        origin=EdgeOrigin.USER, inferred=False, confidence=1.0, evidence=[user_evidence()]
    )
    assert edge.bases == {Basis.ASSERTED}


def test_user_edge_with_lower_confidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"confidence 1\.0"):
        make_edge(origin=EdgeOrigin.USER, confidence=0.9, evidence=[user_evidence()])


def test_user_edge_without_user_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="user_confirmation"):
        make_edge(origin=EdgeOrigin.USER, confidence=1.0)


@pytest.mark.parametrize(
    ("review_state", "confirmed", "valid"),
    [
        (ReviewState.UNREVIEWED, None, True),
        (ReviewState.UNREVIEWED, True, False),
        (ReviewState.CONFIRMED, True, True),
        (ReviewState.CONFIRMED, None, False),
        (ReviewState.REJECTED, False, True),
        (ReviewState.REJECTED, True, False),
        (ReviewState.EDITED, None, True),
        (ReviewState.EDITED, True, True),
    ],
)
def test_review_state_and_confirmed_agree(
    review_state: ReviewState, confirmed: bool | None, valid: bool
) -> None:
    if valid:
        assert (
            make_edge(review_state=review_state, confirmed=confirmed).review_state is review_state
        )
    else:
        with pytest.raises(ValidationError, match="requires confirmed"):
            make_edge(review_state=review_state, confirmed=confirmed)


@pytest.mark.parametrize(
    "relationship",
    [
        RelationshipType.CONTAINS,
        RelationshipType.MEMBER_OF,
        RelationshipType.REPLICATES_TO,
        RelationshipType.BACKED_UP_BY,
    ],
)
def test_structural_and_dr_relationships_are_not_requirements(
    relationship: RelationshipType,
) -> None:
    assert relationship.is_operational_requirement is False


def test_depends_on_is_a_requirement() -> None:
    assert RelationshipType.DEPENDS_ON.is_operational_requirement is True


def test_relationship_outside_the_vocabulary_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_edge(relationship_type="talks_to")


def make_group(**overrides: Any) -> DependencyGroup:
    fields: dict[str, Any] = {
        "id": "group-1",
        "dependent_resource_id": "aws://1/ap-south-1/ecs/service/checkout",
        "member_edge_ids": ["e1", "e2", "e3"],
        "mode": GroupMode.ALL,
        "scope": GroupScope.PRIMARY,
    }
    fields.update(overrides)
    return DependencyGroup(**fields)


@pytest.mark.parametrize(
    ("mode", "minimum_healthy", "required"),
    [(GroupMode.ALL, None, 3), (GroupMode.ANY, None, 1), (GroupMode.QUORUM, 2, 2)],
)
def test_required_members(mode: GroupMode, minimum_healthy: int | None, required: int) -> None:
    group = make_group(mode=mode, minimum_healthy=minimum_healthy)
    assert group.required_members == required


@pytest.mark.parametrize("minimum_healthy", [None, 0, 4])
def test_quorum_must_be_between_one_and_member_count(minimum_healthy: int | None) -> None:
    with pytest.raises(ValidationError, match="quorum group needs"):
        make_group(mode=GroupMode.QUORUM, minimum_healthy=minimum_healthy)


def test_minimum_healthy_only_for_quorum() -> None:
    with pytest.raises(ValidationError, match="only valid for quorum"):
        make_group(mode=GroupMode.ANY, minimum_healthy=1)


def test_group_members_are_distinct_and_present() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        make_group(member_edge_ids=["e1", "e1"])
    with pytest.raises(ValidationError):
        make_group(member_edge_ids=[])
