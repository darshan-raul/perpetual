"""P1-01 rule-pack registry and P1-02 first-slice mechanism resolution (spec §27.1, §28)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from perpetual.fixtures import load_fixture
from perpetual.graph import build_graph
from perpetual.ids import aws_id, external_id
from perpetual.models import (
    Basis,
    Criticality,
    DependencyEdge,
    EdgeOrigin,
    Evidence,
    MechanismKind,
    RelationshipType,
    ResourceNode,
    SourceType,
)
from perpetual.rules import (
    CROSS_CUTTING_RULE_IDS,
    AssessmentContext,
    DRRulePack,
    RDSRulePack,
    ReproducibilityEvidence,
    RulePackError,
    RulePackRegistry,
    default_registry,
)

REPO = Path(__file__).resolve().parents[4]
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ACCOUNT = "123456789012"
PRIMARY = "ap-south-1"
DR = "ap-south-2"


def test_default_registry_registers_all_first_slice_packs_and_rejects_duplicates() -> None:
    registry = default_registry()
    assert set(registry.services()) == {
        "ecr",
        "ecs",
        "elasticloadbalancing",
        "kms",
        "logs",
        "rds",
        "route53",
        "s3",
        "secretsmanager",
    }
    for service in registry.services():
        pack = registry.get(service)
        assert isinstance(pack, DRRulePack)
    assert len(registry.versions()) == len(registry.services())
    assert "XREG-KMS-003" in CROSS_CUTTING_RULE_IDS

    with pytest.raises(RulePackError, match="duplicate rule pack"):
        registry.register(RDSRulePack())


@pytest.mark.parametrize("fixture_name", ["ecs-broken", "ecs-remediated"])
def test_resolved_mechanisms_match_pinned_fixture_overlay(fixture_name: str) -> None:
    fixture = load_fixture(REPO / f"fixtures/graphs/{fixture_name}.yaml")
    graph = build_graph(
        resources=fixture.resources,
        edges=fixture.edges,
        groups=fixture.groups,
        mechanisms=fixture.mechanisms,
        stacks=fixture.stacks,
        stack_resources=fixture.stack_resources,
        stack_services=fixture.stack_services,
    )
    stack = fixture.stacks[0]
    requirement = fixture.requirements[0]
    assert requirement.target_region is not None

    context = AssessmentContext(
        graph=graph,
        target_region=requirement.target_region,
        target_account_id=ACCOUNT,
    )
    registry = default_registry()
    stack_nodes = [graph.resources[rid] for rid in stack.resource_ids]
    resolved = registry.resolve_all(stack_nodes, context)

    pinned_by_primary = {mech.primary_resource_id: mech for mech in fixture.mechanisms}
    for resource_id, pinned in pinned_by_primary.items():
        actual = resolved[resource_id]
        assert actual.kind is pinned.kind, f"{fixture_name}:{resource_id}"
        assert actual.counterpart_resource_id == pinned.counterpart_resource_id
        assert actual.control_plane_dependent == pinned.control_plane_dependent
        assert sorted(actual.dr_dependency_ids) == sorted(pinned.dr_dependency_ids)


def test_strict_reproducibility_requires_all_four_criteria_or_user_confirmation() -> None:
    unmodeled = ResourceNode(
        id=aws_id(ACCOUNT, PRIMARY, "sqs", "queue", "orders"),
        provider="aws",
        service="sqs",
        resource_type="queue",
        account_id=ACCOUNT,
        region=PRIMARY,
        name="orders",
        terraform_address="aws_sqs_queue.orders",
        discovered_at=NOW,
    )
    graph = build_graph(resources=[unmodeled])
    registry = RulePackRegistry()

    # Having a Terraform address alone is never enough for rebuild_from_iac (§27.1).
    partial = ReproducibilityEvidence(
        has_iac_origin=True,
        no_hardcoded_primary_refs=True,
        dr_region_supported=True,
        dr_dependencies_resolve=False,
    )
    ctx_partial = AssessmentContext(
        graph=graph,
        target_region=DR,
        target_account_id=ACCOUNT,
        reproducibility={unmodeled.id: partial},
    )
    assert registry.resolve_mechanism(unmodeled, ctx_partial).kind is MechanismKind.UNKNOWN

    # All four criteria satisfied -> rebuild_from_iac.
    complete = ReproducibilityEvidence(
        has_iac_origin=True,
        no_hardcoded_primary_refs=True,
        dr_region_supported=True,
        dr_dependencies_resolve=True,
    )
    ctx_complete = AssessmentContext(
        graph=graph,
        target_region=DR,
        target_account_id=ACCOUNT,
        reproducibility={unmodeled.id: complete},
    )
    assert (
        registry.resolve_mechanism(unmodeled, ctx_complete).kind is MechanismKind.REBUILD_FROM_IAC
    )

    # Explicit user confirmation also satisfies §27.1.
    confirmed = ReproducibilityEvidence(user_confirmed=True)
    ctx_confirmed = AssessmentContext(
        graph=graph,
        target_region=DR,
        target_account_id=ACCOUNT,
        reproducibility={unmodeled.id: confirmed},
    )
    assert (
        registry.resolve_mechanism(unmodeled, ctx_confirmed).kind is MechanismKind.REBUILD_FROM_IAC
    )


def test_external_resource_and_rds_snapshot_restore() -> None:
    ext = ResourceNode(
        id=external_id("payments", "stripe"),
        provider="external",
        service="payments",
        resource_type="saas",
        account_id=None,
        region=None,
        name="stripe",
        discovered_at=NOW,
    )
    rds = ResourceNode(
        id=aws_id(ACCOUNT, PRIMARY, "rds", "db", "orders"),
        provider="aws",
        service="rds",
        resource_type="db",
        account_id=ACCOUNT,
        region=PRIMARY,
        name="orders",
        discovered_at=NOW,
    )
    dr_snap = ResourceNode(
        id=aws_id(ACCOUNT, DR, "rds", "snapshot", "orders-snap-dr"),
        provider="aws",
        service="rds",
        resource_type="snapshot",
        account_id=ACCOUNT,
        region=DR,
        name="orders-snap-dr",
        discovered_at=NOW,
    )
    backup_edge = DependencyEdge(
        id="e-rds-snap",
        from_resource_id=rds.id,
        to_resource_id=dr_snap.id,
        relationship_type=RelationshipType.BACKED_UP_BY,
        confidence=1.0,
        evidence=[
            Evidence(
                id="ev-snap",
                source_type=SourceType.AWS_API,
                basis=Basis.REFERENCED,
                source="rds:describe_db_snapshots",
                kind="aws_resource_relationship",
                confidence=0.95,
                collected_at=NOW,
            )
        ],
        inferred=False,
        origin=EdgeOrigin.DISCOVERED,
        criticality=Criticality.REQUIRED,
    )
    graph = build_graph(resources=[ext, rds, dr_snap], edges=[backup_edge])
    context = AssessmentContext(graph=graph, target_region=DR, target_account_id=ACCOUNT)
    registry = default_registry()

    assert registry.resolve_mechanism(ext, context).kind is MechanismKind.EXTERNAL
    rds_mech = registry.resolve_mechanism(rds, context)
    assert rds_mech.kind is MechanismKind.RESTORE_FROM_RECOVERY_POINT
    assert rds_mech.recovery_point_ids == [dr_snap.id]
    assert rds_mech.control_plane_dependent is True
