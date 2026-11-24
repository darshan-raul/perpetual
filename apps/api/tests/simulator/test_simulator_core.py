"""P1-03..P1-08: RTO scope, scenarios, two-pass simulator, readiness and reason chains."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from perpetual.config import load_config
from perpetual.fixtures import load_fixture
from perpetual.graph import DependencyGraph, build_graph
from perpetual.ids import aws_id
from perpetual.models import (
    Basis,
    Criticality,
    DependencyEdge,
    DependencyGroup,
    EdgeOrigin,
    Evidence,
    GroupMode,
    GroupScope,
    MechanismKind,
    Readiness,
    RecoveryMechanism,
    RelationshipType,
    ResourceNode,
    ResourceState,
    ReviewState,
    RtoScope,
    ScopeSource,
    SourceType,
    Stack,
    StackCriticality,
    StackResource,
    StackState,
    TargetComparison,
)
from perpetual.simulator import (
    AZFailure,
    EvaluationKind,
    LogicalCorruption,
    ReadinessInputs,
    RegionFailure,
    UnsupportedScenarioError,
    compose_readiness,
    parse_scenario,
    simulate_failure,
)
from perpetual.stacks import classify_resource_scope

REPO = Path(__file__).resolve().parents[4]
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ACCOUNT = "123456789012"
PRIMARY = "ap-south-1"
DR = "ap-south-2"


def _load_graph(fixture_name: str) -> DependencyGraph:
    fixture = load_fixture(REPO / f"fixtures/graphs/{fixture_name}.yaml")
    return build_graph(
        resources=fixture.resources,
        edges=fixture.edges,
        groups=fixture.groups,
        mechanisms=fixture.mechanisms,
        stacks=fixture.stacks,
        stack_resources=fixture.stack_resources,
        stack_services=fixture.stack_services,
    )


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
    criticality: Criticality = Criticality.REQUIRED,
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
        criticality=criticality,
    )


# --- §87 / §88 canonical demos ------------------------------------------------


def test_ecs_broken_demo_is_unavailable_and_not_ready_with_reason_chains() -> None:
    graph = _load_graph("ecs-broken")
    result = simulate_failure(graph, "checkout", RegionFailure(region=PRIMARY))

    assert result.stack_state is StackState.UNAVAILABLE
    assert result.readiness.readiness is Readiness.NOT_READY
    assert "simulation_unavailable" in result.readiness.reasons
    assert result.reason_chains
    # Out-of-scope log group is evaluated and marked OUT_OF_SCOPE.
    log_id = aws_id(ACCOUNT, PRIMARY, "logs", "log-group", "checkout-api-logs")
    assert result.resources[log_id].rto_scope is RtoScope.OUT_OF_SCOPE
    assert result.resources[log_id].state is ResourceState.BLOCKED


def test_ecs_remediated_demo_is_recoverable_despite_blocked_out_of_scope_logs() -> None:
    graph = _load_graph("ecs-remediated")

    # Missing RTO/RPO evaluators keep readiness UNKNOWN even when recoverable (§31).
    unknown_eval = simulate_failure(graph, "checkout", RegionFailure(region=PRIMARY))
    assert unknown_eval.stack_state is StackState.RECOVERABLE
    assert unknown_eval.readiness.readiness is Readiness.UNKNOWN
    assert "rto_target_uncertain" in unknown_eval.readiness.reasons

    # Out-of-scope log group is BLOCKED, yet stack is RECOVERABLE and READY when targets PASS.
    log_id = aws_id(ACCOUNT, PRIMARY, "logs", "log-group", "checkout-api-logs")
    assert unknown_eval.resources[log_id].rto_scope is RtoScope.OUT_OF_SCOPE
    assert unknown_eval.resources[log_id].state is ResourceState.BLOCKED

    ready_eval = simulate_failure(
        graph,
        "checkout",
        RegionFailure(region=PRIMARY),
        rto_comparison=TargetComparison.PASS,
        rpo_comparison=TargetComparison.PASS,
        budget_comparison=TargetComparison.PASS,
    )
    assert ready_eval.stack_state is StackState.RECOVERABLE
    assert ready_eval.readiness.readiness is Readiness.READY

    # Recoverable path that misses RPO is RECOVERABLE in simulation and NOT_READY overall (§31).
    rpo_fail = simulate_failure(
        graph,
        "checkout",
        RegionFailure(region=PRIMARY),
        rto_comparison=TargetComparison.PASS,
        rpo_comparison=TargetComparison.FAIL,
    )
    assert rpo_fail.stack_state is StackState.RECOVERABLE
    assert rpo_fail.readiness.readiness is Readiness.NOT_READY
    assert "rpo_target_failed" in rpo_fail.readiness.reasons


# --- cycle safety & scenario dispatch -----------------------------------------


def test_cycle_fixture_terminates_and_reports_unknown_with_cycle_evidence() -> None:
    graph = _load_graph("cycle")
    result = simulate_failure(graph, "cyclic-stack", RegionFailure(region=PRIMARY))

    assert result.stack_state is StackState.UNKNOWN
    assert result.readiness.readiness is Readiness.UNKNOWN
    assert len(result.cycles) == 1
    assert len(result.cycles[0]) == 3


def test_scenario_parsing_and_unsupported_scenarios() -> None:
    assert parse_scenario("region:ap-south-1") == RegionFailure(region="ap-south-1")
    graph = _load_graph("minimal")

    with pytest.raises(UnsupportedScenarioError, match=r"not supported in v0\.1"):
        simulate_failure(graph, "checkout", AZFailure(availability_zone="ap-south-1a"))

    with pytest.raises(UnsupportedScenarioError, match=r"not supported in v0\.1"):
        simulate_failure(
            graph,
            "checkout",
            LogicalCorruption(
                resource_ids=[aws_id(ACCOUNT, PRIMARY, "rds", "db", "checkout")],
                detected_after_seconds=600,
            ),
        )


# --- review gate & RTO scope --------------------------------------------------


def test_unreviewed_low_confidence_required_edge_blocks_ready_but_not_negative_results() -> None:
    api = _node("ecs", "service", "api")
    db = _node("rds", "db", "db")
    db_dr = _node("rds", "db", "db-dr", region=DR)
    low_conf = _edge(
        "e-low",
        api.id,
        db.id,
        confidence=0.75,
        review_state=ReviewState.UNREVIEWED,
        confirmed=None,
    )
    stack = Stack(
        id="stk",
        name="stk",
        criticality=StackCriticality.HIGH,
        root_resource_ids=[api.id],
        resource_ids=[api.id, db.id],
        primary_region=PRIMARY,
        discovery_confidence=1.0,
    )
    mechs = [
        RecoveryMechanism(
            id="m-api",
            primary_resource_id=api.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.REBUILD_FROM_IAC,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        RecoveryMechanism(
            id="m-db",
            primary_resource_id=db.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=db_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
    ]
    graph = build_graph(
        resources=[api, db, db_dr], edges=[low_conf], mechanisms=mechs, stacks=[stack]
    )

    result = simulate_failure(
        graph,
        "stk",
        RegionFailure(region=PRIMARY),
        rto_comparison=TargetComparison.PASS,
        rpo_comparison=TargetComparison.PASS,
    )
    assert result.stack_state is StackState.RECOVERABLE
    assert result.readiness.readiness is Readiness.UNKNOWN
    assert "graph_not_reviewed" in result.readiness.reasons
    assert result.unreviewed_required_edge_ids == ("e-low",)


def test_rto_scope_classification_defaults_and_override() -> None:
    cfg = load_config().rto_scope
    log_node = _node("logs", "log-group", "app-logs")
    ecs_node = _node("ecs", "service", "api")

    assert classify_resource_scope(log_node, cfg) == (
        RtoScope.OUT_OF_SCOPE,
        ScopeSource.RULE_DEFAULT,
    )
    assert classify_resource_scope(ecs_node, cfg) == (
        RtoScope.IN_SCOPE,
        ScopeSource.RULE_DEFAULT,
    )

    user_in_scope = StackResource(
        stack_id="stk",
        resource_id=log_node.id,
        rto_scope=RtoScope.IN_SCOPE,
        scope_source=ScopeSource.USER,
    )
    assert classify_resource_scope(log_node, cfg, override=user_in_scope) == (
        RtoScope.IN_SCOPE,
        ScopeSource.USER,
    )


# --- ALL / ANY / quorum groups & §31 readiness table --------------------------


def test_any_and_quorum_dependency_group_semantics() -> None:
    api = _node("ecs", "service", "api")
    r1 = _node("rds", "db", "r1")
    r2 = _node("rds", "db", "r2")
    r3 = _node("rds", "db", "r3")
    r1_dr = _node("rds", "db", "r1-dr", region=DR)
    r2_dr = _node("rds", "db", "r2-dr", region=DR)

    e1 = _edge("e1", api.id, r1.id)
    e2 = _edge("e2", api.id, r2.id)
    e3 = _edge("e3", api.id, r3.id)
    quorum = DependencyGroup(
        id="grp-q",
        dependent_resource_id=api.id,
        member_edge_ids=[e1.id, e2.id, e3.id],
        mode=GroupMode.QUORUM,
        minimum_healthy=2,
        scope=GroupScope.PRIMARY,
    )
    stack = Stack(
        id="stk",
        name="stk",
        criticality=StackCriticality.HIGH,
        root_resource_ids=[api.id],
        resource_ids=[api.id, r1.id, r2.id, r3.id],
        primary_region=PRIMARY,
        discovery_confidence=1.0,
    )
    # 2 recoverable (r1, r2) + 1 blocked (r3) satisfies quorum=2 -> RECOVERABLE.
    mechs_pass = [
        RecoveryMechanism(
            id="m-api",
            primary_resource_id=api.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.REBUILD_FROM_IAC,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        RecoveryMechanism(
            id="m-r1",
            primary_resource_id=r1.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=r1_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        RecoveryMechanism(
            id="m-r2",
            primary_resource_id=r2.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.LIVE_COUNTERPART,
            counterpart_resource_id=r2_dr.id,
            control_plane_dependent=True,
            confidence=0.95,
        ),
        RecoveryMechanism(
            id="m-r3",
            primary_resource_id=r3.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.NONE,
            control_plane_dependent=True,
            confidence=0.95,
        ),
    ]
    g_pass = build_graph(
        resources=[api, r1, r2, r3, r1_dr, r2_dr],
        edges=[e1, e2, e3],
        groups=[quorum],
        mechanisms=mechs_pass,
        stacks=[stack],
    )
    assert simulate_failure(g_pass, "stk", RegionFailure(region=PRIMARY)).stack_state is (
        StackState.RECOVERABLE
    )

    # 1 recoverable + 1 unknown + 1 blocked -> S=1 < 2 <= S+U=2 -> UNKNOWN.
    mechs_unknown = [
        *mechs_pass[:2],
        RecoveryMechanism(
            id="m-r2",
            primary_resource_id=r2.id,
            target_region=DR,
            target_account_id=ACCOUNT,
            kind=MechanismKind.UNKNOWN,
            control_plane_dependent=False,
            confidence=0.0,
        ),
        mechs_pass[3],
    ]
    g_unknown = build_graph(
        resources=[api, r1, r2, r3, r1_dr, r2_dr],
        edges=[e1, e2, e3],
        groups=[quorum],
        mechanisms=mechs_unknown,
        stacks=[stack],
    )
    assert simulate_failure(g_unknown, "stk", RegionFailure(region=PRIMARY)).stack_state is (
        StackState.UNKNOWN
    )


def test_readiness_decision_table_precedence_and_evaluation_kind() -> None:
    # Proven failure beats unknowns (NOT_READY, never hidden by UNKNOWN).
    proven_and_unknown = compose_readiness(
        ReadinessInputs(
            stack_state=StackState.RECOVERABLE,
            rto_comparison=TargetComparison.PASS,
            rpo_comparison=TargetComparison.FAIL,
            unreviewed_required_edges=3,
            coverage_incomplete=True,
        )
    )
    assert proven_and_unknown.readiness is Readiness.NOT_READY

    # Warnings after all gates pass yield DEGRADED, preserving DESIGN evaluation kind.
    degraded = compose_readiness(
        ReadinessInputs(
            stack_state=StackState.RECOVERABLE,
            evaluation_kind=EvaluationKind.DESIGN,
            rto_comparison=TargetComparison.PASS,
            rpo_comparison=TargetComparison.PASS,
            has_warnings=True,
        )
    )
    assert degraded.readiness is Readiness.DEGRADED
    assert degraded.evaluation_kind is EvaluationKind.DESIGN
