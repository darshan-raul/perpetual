"""P1-15 persistence round-trips and P1-18 bounded ALL/ANY/quorum path selection tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from perpetual.config import load_config
from perpetual.graph import build_graph
from perpetual.ids import aws_id
from perpetual.models import (
    Basis,
    Criticality,
    DependencyEdge,
    DependencyGroup,
    DurationEstimate,
    EdgeOrigin,
    EstimateConfidence,
    Evidence,
    FailureScope,
    GroupMode,
    GroupScope,
    MechanismKind,
    RecoveryMechanism,
    RecoveryRequirement,
    RelationshipType,
    ResourceNode,
    ReviewState,
    SourceType,
    Stack,
    StackCriticality,
)
from perpetual.persistence import (
    PersistenceError,
    ProjectRepository,
    create_project,
    make_engine,
    make_session_factory,
    transaction,
    upgrade,
)
from perpetual.recovery import select_recovery_paths
from perpetual.simulator import RegionFailure

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ACCOUNT = "123456789012"
PRIMARY = "ap-south-1"
DR = "ap-south-2"


def _node(service: str, rtype: str, ident: str, *, region: str = PRIMARY) -> ResourceNode:
    return ResourceNode(
        id=aws_id(ACCOUNT, region, service, rtype, ident),
        provider="aws",
        service=service,
        resource_type=rtype,
        account_id=ACCOUNT,
        region=region,
        name=ident,
        discovered_at=NOW,
    )


def _edge(
    eid: str,
    src: str,
    dst: str,
    *,
    confidence: float = 1.0,
    review_state: ReviewState = ReviewState.CONFIRMED,
    confirmed: bool | None = True,
) -> DependencyEdge:
    return DependencyEdge(
        id=eid,
        from_resource_id=src,
        to_resource_id=dst,
        relationship_type=RelationshipType.CONNECTS_TO,
        confidence=confidence,
        confirmed=confirmed,
        evidence=[
            Evidence(
                id=f"ev-{eid}",
                source_type=SourceType.TERRAFORM,
                basis=Basis.REFERENCED,
                source="terraform:infra/default",
                kind="terraform_reference",
                confidence=confidence,
                collected_at=NOW,
            )
        ],
        inferred=False,
        origin=EdgeOrigin.DISCOVERED,
        review_state=review_state,
        criticality=Criticality.REQUIRED,
    )


# --- P1-18 selected-path regressions ------------------------------------------


def test_any_group_selects_lowest_rto_feasible_path_and_excludes_unselected() -> None:
    api = _node("ecs", "service", "api")
    db_fast = _node("rds", "db", "db-fast")
    db_slow = _node("rds", "db", "db-slow")
    db_fast_dr = _node("rds", "db", "db-fast-dr", region=DR)
    db_slow_dr = _node("rds", "db", "db-slow-dr", region=DR)

    e_fast = _edge("e-fast", api.id, db_fast.id)
    e_slow = _edge("e-slow", api.id, db_slow.id)
    any_group = DependencyGroup(
        id="grp-db-any",
        dependent_resource_id=api.id,
        member_edge_ids=[e_fast.id, e_slow.id],
        mode=GroupMode.ANY,
        scope=GroupScope.PRIMARY,
    )
    stack = Stack(
        id="stk",
        name="stk",
        criticality=StackCriticality.HIGH,
        root_resource_ids=[api.id],
        resource_ids=[api.id, db_fast.id, db_slow.id],
        primary_region=PRIMARY,
        discovery_confidence=1.0,
    )
    mechs = {
        api.id: RecoveryMechanism(
            id="m-api",
            primary_resource_id=api.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.REBUILD_FROM_IAC,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        db_fast.id: RecoveryMechanism(
            id="m-fast",
            primary_resource_id=db_fast.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=db_fast_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        db_slow.id: RecoveryMechanism(
            id="m-slow",
            primary_resource_id=db_slow.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=db_slow_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
    }
    graph = build_graph(
        resources=[api, db_fast, db_slow, db_fast_dr, db_slow_dr],
        edges=[e_fast, e_slow],
        groups=[any_group],
        mechanisms=list(mechs.values()),
        stacks=[stack],
    )
    req = RecoveryRequirement(
        id="req-1",
        revision=1,
        stack_id="stk",
        failure_scope=FailureScope.REGION,
        target_rto_seconds=3600,
        target_rpo_seconds=300,
        target_region=DR,
    )
    overrides = {
        db_fast.id: DurationEstimate(
            low_seconds=120,
            expected_seconds=180,
            high_seconds=240,
            confidence=EstimateConfidence.HIGH,
            basis="fast replica",
        ),
        db_slow.id: DurationEstimate(
            low_seconds=900,
            expected_seconds=1200,
            high_seconds=1500,
            confidence=EstimateConfidence.HIGH,
            basis="slow replica",
        ),
    }

    selected = select_recovery_paths(
        graph,
        "stk",
        requirement=req,
        mechanisms=mechs,
        scenario=RegionFailure(region=PRIMARY),
        duration_overrides=overrides,
    )
    assert selected.feasible is True
    assert selected.capped is False
    assert selected.selected_edge_ids_by_group == {"grp-db-any": ("e-fast",)}
    assert db_fast.id in selected.selected_resource_ids
    assert db_slow.id not in selected.selected_resource_ids
    assert selected.plan is not None
    # Unselected slow DB adds no recovery action to the plan (§19.1).
    assert not any("db-slow" in aid for aid in selected.plan.actions)


def test_shared_failed_prerequisite_blocks_all_alternatives_and_respects_cap() -> None:
    api = _node("ecs", "service", "api")
    db1 = _node("rds", "db", "db1")
    db2 = _node("rds", "db", "db2")
    shared_kms = _node("kms", "key", "shared-cmk")
    db1_dr = _node("rds", "db", "db1-dr", region=DR)
    db2_dr = _node("rds", "db", "db2-dr", region=DR)

    e1 = _edge("e1", api.id, db1.id)
    e2 = _edge("e2", api.id, db2.id)
    e_k1 = _edge("ek1", db1.id, shared_kms.id)
    e_k2 = _edge("ek2", db2.id, shared_kms.id)
    any_group = DependencyGroup(
        id="grp-any",
        dependent_resource_id=api.id,
        member_edge_ids=[e1.id, e2.id],
        mode=GroupMode.ANY,
        scope=GroupScope.PRIMARY,
    )
    stack = Stack(
        id="stk",
        name="stk",
        criticality=StackCriticality.HIGH,
        root_resource_ids=[api.id],
        resource_ids=[api.id, db1.id, db2.id, shared_kms.id],
        primary_region=PRIMARY,
        discovery_confidence=1.0,
    )
    mechs = {
        api.id: RecoveryMechanism(
            id="m-api",
            primary_resource_id=api.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.REBUILD_FROM_IAC,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        db1.id: RecoveryMechanism(
            id="m-db1",
            primary_resource_id=db1.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=db1_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        db2.id: RecoveryMechanism(
            id="m-db2",
            primary_resource_id=db2.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=db2_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        shared_kms.id: RecoveryMechanism(
            id="m-kms",
            primary_resource_id=shared_kms.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.NONE,
            control_plane_dependent=False,
            confidence=0.95,
        ),
    }
    graph = build_graph(
        resources=[api, db1, db2, shared_kms, db1_dr, db2_dr],
        edges=[e1, e2, e_k1, e_k2],
        groups=[any_group],
        mechanisms=list(mechs.values()),
        stacks=[stack],
    )
    req = RecoveryRequirement(
        id="req-1",
        revision=1,
        stack_id="stk",
        failure_scope=FailureScope.REGION,
        target_rto_seconds=3600,
        target_rpo_seconds=300,
        target_region=DR,
    )

    # Shared KMS key has mechanism NONE -> both branches infeasible.
    capped_cfg = load_config({"limits": {"alternative_selection_cap": 1}})
    result = select_recovery_paths(
        graph,
        "stk",
        requirement=req,
        mechanisms=mechs,
        scenario=RegionFailure(region=PRIMARY),
        config=capped_cfg,
    )
    assert result.feasible is False
    assert result.capped is True
    assert result.combinations_evaluated == 1


# --- P1-15 persistence round-trip ---------------------------------------------


def test_persist_requirements_simulations_and_recovery_plans(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'p1.db'}")
    upgrade(engine)

    req_v1 = RecoveryRequirement(
        id="req-checkout",
        revision=1,
        stack_id="checkout",
        failure_scope=FailureScope.REGION,
        target_rto_seconds=1800,
        target_rpo_seconds=300,
        target_region=DR,
    )
    req_v2 = req_v1.model_copy(update={"revision": 2, "target_rto_seconds": 900})

    sessions = make_session_factory(engine)
    with transaction(sessions) as session:
        create_project(session, "proj-1", "Checkout", NOW)
        create_project(session, "proj-2", "Other", NOW)
        repo = ProjectRepository(session, "proj-1")
        other_repo = ProjectRepository(session, "proj-2")

        repo.add_scan("scan-1", NOW, ["fixture"])
        repo.create_snapshot("snap-1", "live", NOW, scan_id="scan-1")

        repo.save_requirement(req_v1, created_at=NOW)
        repo.save_requirement(req_v2, created_at=NOW)
        assert repo.requirement("req-checkout", revision=1).target_rto_seconds == 1800
        assert repo.requirement("req-checkout").target_rto_seconds == 900

        repo.save_simulation(
            "sim-1",
            "snap-1",
            stack_id="checkout",
            scenario_kind="region",
            stack_state="UNAVAILABLE",
            readiness="NOT_READY",
            created_at=NOW,
            payload={"stack_state": "UNAVAILABLE"},
        )
        assert repo.simulation("sim-1") == {"stack_state": "UNAVAILABLE"}

        repo.save_recovery_plan(
            "plan-1",
            "snap-1",
            stack_id="checkout",
            requirement_id="req-checkout",
            requirement_revision=2,
            rto_comparison="PASS",
            created_at=NOW,
            payload={"expected_seconds": 600},
        )
        assert repo.recovery_plan("plan-1") == {"expected_seconds": 600}

        # Project isolation enforced on all three tables.
        with pytest.raises(PersistenceError, match="no requirement"):
            other_repo.requirement("req-checkout")
        with pytest.raises(PersistenceError, match="no simulation"):
            other_repo.simulation("sim-1")
        with pytest.raises(PersistenceError, match="no recovery plan"):
            other_repo.recovery_plan("plan-1")
