"""NetworkX MultiDiGraph snapshot, group validation and cycle-safe traversal (spec §17-§19.1)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from perpetual.evidence import edge_fingerprint
from perpetual.fixtures import load_fixture
from perpetual.graph import (
    DependencyGraph,
    GraphData,
    GraphError,
    ancestors_of,
    apply_overrides,
    build_graph,
    dependency_closure,
    detect_cycles,
    has_cycles,
    project_graph,
    shortest_dependency_path,
)
from perpetual.ids import aws_id, external_id
from perpetual.models import (
    Basis,
    Criticality,
    DependencyEdge,
    DependencyGroup,
    EdgeOrigin,
    Evidence,
    GraphOverride,
    GroupMode,
    GroupScope,
    MechanismKind,
    OverrideKind,
    RecoveryMechanism,
    RelationshipType,
    ResourceNode,
    ReviewState,
    RtoScope,
    ScopeSource,
    SourceType,
    Stack,
    StackCriticality,
    StackResource,
    StackService,
)

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ACCOUNT = "123456789012"
PRIMARY = "ap-south-1"
DR = "ap-south-2"


def make_aws_node(
    service: str,
    resource_type: str,
    identifier: str,
    *,
    region: str = PRIMARY,
    name: str | None = None,
) -> ResourceNode:
    resource_id = aws_id(ACCOUNT, region, service, resource_type, identifier)
    return ResourceNode(
        id=resource_id,
        provider="aws",
        service=service,
        resource_type=resource_type,
        account_id=ACCOUNT,
        region=region,
        name=name or identifier,
        discovered_at=NOW,
    )


def make_edge(
    edge_id: str,
    from_id: str,
    to_id: str,
    *,
    relationship: RelationshipType = RelationshipType.DEPENDS_ON,
    confidence: float = 1.0,
    criticality: Criticality = Criticality.REQUIRED,
    review_state: ReviewState = ReviewState.UNREVIEWED,
    confirmed: bool | None = None,
) -> DependencyEdge:
    evidence = Evidence(
        id=f"ev-{edge_id}",
        source_type=SourceType.TERRAFORM,
        basis=Basis.REFERENCED,
        source="terraform:root/default",
        kind="terraform_reference",
        confidence=confidence,
        collected_at=NOW,
    )
    return DependencyEdge(
        id=edge_id,
        from_resource_id=from_id,
        to_resource_id=to_id,
        relationship_type=relationship,
        confidence=confidence,
        confirmed=confirmed,
        evidence=[evidence],
        inferred=False,
        origin=EdgeOrigin.DISCOVERED,
        review_state=review_state,
        criticality=criticality,
    )


# --- multigraph & parallel edges ----------------------------------------------


def test_multigraph_preserves_parallel_typed_edges_and_projection_keeps_edge_ids() -> None:
    ecs = make_aws_node("ecs", "service", "checkout-api")
    rds = make_aws_node("rds", "instance", "orders-db")
    connects = make_edge("e-connect", ecs.id, rds.id, relationship=RelationshipType.CONNECTS_TO)
    reads = make_edge("e-read", ecs.id, rds.id, relationship=RelationshipType.READS_FROM)

    graph = build_graph(resources=[ecs, rds], edges=[connects, reads])

    assert graph.multigraph.number_of_edges(ecs.id, rds.id) == 2
    assert [edge.id for edge in graph.edges_between(ecs.id, rds.id)] == ["e-connect", "e-read"]
    assert [edge.id for edge in graph.outgoing_edges(ecs.id)] == ["e-connect", "e-read"]
    assert [edge.id for edge in graph.incoming_edges(rds.id)] == ["e-connect", "e-read"]

    projected = project_graph(graph)
    assert projected.edges[ecs.id, rds.id]["edge_ids"] == ("e-connect", "e-read")


# --- projection filtering -----------------------------------------------------


def test_projection_skips_structural_replication_and_optional_edges_when_requested() -> None:
    cluster = make_aws_node("ecs", "cluster", "prod")
    ecs = make_aws_node("ecs", "service", "checkout-api")
    rds_primary = make_aws_node("rds", "instance", "orders-db", region=PRIMARY)
    rds_dr = make_aws_node("rds", "instance", "orders-db-dr", region=DR)
    logs = make_aws_node("logs", "log-group", "checkout-logs")

    edges = [
        make_edge("e-contains", cluster.id, ecs.id, relationship=RelationshipType.CONTAINS),
        make_edge("e-db", ecs.id, rds_primary.id, relationship=RelationshipType.CONNECTS_TO),
        make_edge("e-repl", rds_primary.id, rds_dr.id, relationship=RelationshipType.REPLICATES_TO),
        make_edge(
            "e-logs",
            ecs.id,
            logs.id,
            relationship=RelationshipType.WRITES_TO,
            criticality=Criticality.OPTIONAL,
            confidence=0.7,
        ),
    ]
    graph = build_graph(resources=[cluster, ecs, rds_primary, rds_dr, logs], edges=edges)

    # Default operational projection skips `contains` and `replicates_to`.
    assert dependency_closure(graph, [ecs.id]) == tuple(sorted([rds_primary.id, logs.id]))
    assert dependency_closure(graph, [cluster.id]) == ()

    # Excluding optional edges keeps only required operational dependencies.
    assert dependency_closure(graph, [ecs.id], include_optional=False) == (rds_primary.id,)

    # Confidence threshold filters weak edges.
    assert dependency_closure(graph, [ecs.id], min_confidence=0.9) == (rds_primary.id,)

    # Including non-operational edges exposes replication and containment.
    assert dependency_closure(graph, [cluster.id], operational_only=False) == tuple(
        sorted([ecs.id, rds_primary.id, rds_dr.id, logs.id])
    )
    assert [edge.id for edge in graph.outgoing_edges(rds_primary.id, operational_only=True)] == []
    assert [edge.id for edge in graph.outgoing_edges(rds_primary.id, operational_only=False)] == [
        "e-repl"
    ]

    # Relationship-type filter isolates a specific edge kind.
    repl_only = project_graph(
        graph,
        operational_only=False,
        relationship_types=[RelationshipType.REPLICATES_TO],
    )
    assert list(repl_only.edges()) == [(rds_primary.id, rds_dr.id)]


# --- deep path, shared nodes, ancestors, shortest path ------------------------


def test_closure_ancestors_and_shortest_path_on_deep_shared_graph() -> None:
    alb = make_aws_node("elasticloadbalancing", "loadbalancer", "web-alb")
    api = make_aws_node("ecs", "service", "checkout-api")
    worker = make_aws_node("ecs", "service", "checkout-worker")
    secret = make_aws_node("secretsmanager", "secret", "db-creds")
    rds = make_aws_node("rds", "instance", "orders-db")
    kms = make_aws_node("kms", "key", "shared-cmk")
    isolated = make_aws_node("s3", "bucket", "unrelated")

    edges = [
        make_edge("e1", alb.id, api.id, relationship=RelationshipType.ROUTES_TO),
        make_edge("e2", api.id, secret.id, relationship=RelationshipType.USES_SECRET),
        make_edge("e3", api.id, rds.id, relationship=RelationshipType.CONNECTS_TO),
        make_edge("e4", worker.id, rds.id, relationship=RelationshipType.CONNECTS_TO),
        make_edge("e5", secret.id, kms.id, relationship=RelationshipType.ENCRYPTED_BY),
        make_edge("e6", rds.id, kms.id, relationship=RelationshipType.ENCRYPTED_BY),
    ]
    graph = build_graph(
        resources=[alb, api, worker, secret, rds, kms, isolated],
        edges=edges,
    )

    assert dependency_closure(graph, [alb.id]) == tuple(sorted([api.id, secret.id, rds.id, kms.id]))
    assert dependency_closure(graph, [alb.id], include_starts=True) == tuple(
        sorted([alb.id, api.id, secret.id, rds.id, kms.id])
    )
    assert dependency_closure(graph, []) == ()

    # Shared KMS key impacts both stacks/services and the upstream ALB.
    assert ancestors_of(graph, [kms.id]) == tuple(
        sorted([alb.id, api.id, worker.id, secret.id, rds.id])
    )
    assert ancestors_of(graph, [kms.id], include_targets=True) == tuple(
        sorted([alb.id, api.id, worker.id, secret.id, rds.id, kms.id])
    )
    assert ancestors_of(graph, []) == ()

    path = shortest_dependency_path(graph, alb.id, kms.id)
    assert path is not None
    assert path[0] == alb.id
    assert path[-1] == kms.id
    assert len(path) == 4  # alb -> api -> (rds|secret) -> kms
    assert shortest_dependency_path(graph, alb.id, isolated.id) is None
    assert has_cycles(graph) is False
    assert detect_cycles(graph) == ()


# --- cycle safety (spec §18) --------------------------------------------------


def test_traversal_terminates_and_reports_canonical_cycles_without_raising() -> None:
    svc_a = make_aws_node("ecs", "service", "svc-a")
    svc_b = make_aws_node("ecs", "service", "svc-b")
    svc_c = make_aws_node("ecs", "service", "svc-c")
    db = make_aws_node("rds", "instance", "orders-db")

    edges = [
        make_edge("e-ab", svc_a.id, svc_b.id),
        make_edge("e-bc", svc_b.id, svc_c.id),
        make_edge("e-ca", svc_c.id, svc_a.id),
        make_edge("e-c-db", svc_c.id, db.id),
    ]
    graph = build_graph(resources=[svc_a, svc_b, svc_c, db], edges=edges)

    assert has_cycles(graph) is True
    assert detect_cycles(graph) == ((svc_a.id, svc_b.id, svc_c.id),)
    assert dependency_closure(graph, [svc_a.id]) == tuple(sorted([svc_b.id, svc_c.id, db.id]))
    assert ancestors_of(graph, [db.id]) == tuple(sorted([svc_a.id, svc_b.id, svc_c.id]))
    assert shortest_dependency_path(graph, svc_a.id, db.id) == (svc_a.id, svc_b.id, svc_c.id, db.id)
    assert shortest_dependency_path(graph, db.id, svc_a.id) is None


# --- dependency groups & rejected-edge preservation ---------------------------


def test_quorum_group_preserves_rejected_member_without_lowering_quorum() -> None:
    api = make_aws_node("ecs", "service", "checkout-api")
    ep1 = make_aws_node("rds", "instance", "reader-1")
    ep2 = make_aws_node("rds", "instance", "reader-2")
    ep3 = make_aws_node("rds", "instance", "reader-3")
    kms = make_aws_node("kms", "key", "app-key")

    e1 = make_edge("e-r1", api.id, ep1.id, relationship=RelationshipType.READS_FROM)
    e2 = make_edge("e-r2", api.id, ep2.id, relationship=RelationshipType.READS_FROM)
    e3 = make_edge("e-r3", api.id, ep3.id, relationship=RelationshipType.READS_FROM)
    e_kms = make_edge("e-kms", api.id, kms.id, relationship=RelationshipType.ENCRYPTED_BY)

    quorum_group = DependencyGroup(
        id="grp-readers",
        dependent_resource_id=api.id,
        member_edge_ids=[e1.id, e2.id, e3.id],
        mode=GroupMode.QUORUM,
        minimum_healthy=2,
        scope=GroupScope.PRIMARY,
    )

    reject_e2 = GraphOverride(
        id="ov-reject-e2",
        project_id="proj-1",
        kind=OverrideKind.REJECT_EDGE,
        target=edge_fingerprint(e2),
        payload={},
        author="sre",
        created_at=NOW,
    )

    override_result = apply_overrides(
        GraphData(resources=[api, ep1, ep2, ep3, kms], edges=[e1, e2, e3, e_kms]),
        [reject_e2],
        project_id="proj-1",
    )
    graph = DependencyGraph.from_override_result(override_result, groups=[quorum_group])

    # Rejected edge is removed from active traversal, but kept on the snapshot.
    assert e2.id not in graph.edges
    assert e2.id in graph.rejected_edges
    assert dependency_closure(graph, [api.id]) == tuple(sorted([ep1.id, ep3.id, kms.id]))

    # Group quorum stays 2 (never silently lowered), and members report rejected context.
    stored_group = graph.groups["grp-readers"]
    assert stored_group.minimum_healthy == 2
    assert stored_group.required_members == 2
    assert graph.groups_for(api.id, scope=GroupScope.PRIMARY) == (stored_group,)
    assert graph.group_for_edge(e1.id, scope=GroupScope.PRIMARY) == stored_group
    assert graph.group_for_edge(e_kms.id, scope=GroupScope.PRIMARY) is None

    members = graph.group_members("grp-readers")
    assert [(m.edge.id, m.rejected) for m in members] == [
        ("e-r1", False),
        ("e-r2", True),
        ("e-r3", False),
    ]
    assert [edge.id for edge in graph.ungrouped_outgoing_edges(api.id)] == ["e-kms"]


def test_mechanism_dr_dependency_groups_are_validated_and_indexed() -> None:
    rds_primary = make_aws_node("rds", "instance", "orders", region=PRIMARY)
    rds_dr = make_aws_node("rds", "instance", "orders-dr", region=DR)
    kms_dr = make_aws_node("kms", "key", "orders-dr-key", region=DR)
    dr_edge = make_edge(
        "e-dr-kms", rds_dr.id, kms_dr.id, relationship=RelationshipType.ENCRYPTED_BY
    )
    dr_group = DependencyGroup(
        id="grp-dr-kms",
        dependent_resource_id=rds_dr.id,
        member_edge_ids=[dr_edge.id],
        mode=GroupMode.ALL,
        scope=GroupScope.DR,
    )
    mechanism = RecoveryMechanism(
        id="mech-rds",
        primary_resource_id=rds_primary.id,
        target_region=DR,
        target_account_id=ACCOUNT,
        kind=MechanismKind.LIVE_COUNTERPART,
        counterpart_resource_id=rds_dr.id,
        dr_dependency_ids=[kms_dr.id],
        dependency_groups=[dr_group],
        control_plane_dependent=True,
        confidence=1.0,
    )

    graph = build_graph(
        resources=[rds_primary, rds_dr, kms_dr],
        edges=[dr_edge],
        mechanisms=[mechanism],
    )
    assert graph.groups_for(rds_dr.id, scope=GroupScope.DR) == (dr_group,)
    assert graph.group_for_edge(dr_edge.id, scope=GroupScope.DR) == dr_group


# --- validation errors --------------------------------------------------------


def test_build_graph_rejects_identity_mismatches() -> None:
    wrong_region = ResourceNode(
        id=aws_id(ACCOUNT, PRIMARY, "ecs", "service", "api"),
        provider="aws",
        service="ecs",
        resource_type="service",
        account_id=ACCOUNT,
        region=DR,
        name="api",
        discovered_at=NOW,
    )
    with pytest.raises(GraphError, match="region"):
        build_graph(resources=[wrong_region])

    wrong_external = ResourceNode(
        id=external_id("payments", "stripe"),
        provider="aws",
        service="payments",
        resource_type="dependency",
        account_id=None,
        region=None,
        name="stripe",
        discovered_at=NOW,
    )
    with pytest.raises(GraphError, match="external ID"):
        build_graph(resources=[wrong_external])

    bad_id = ResourceNode(
        id="not-a-canonical-id",
        provider="aws",
        service="ecs",
        resource_type="service",
        account_id=ACCOUNT,
        region=PRIMARY,
        name="api",
        discovered_at=NOW,
    )
    with pytest.raises(GraphError, match="invalid canonical ID"):
        build_graph(resources=[bad_id])


def test_build_graph_rejects_invalid_edges_groups_and_stacks() -> None:
    api = make_aws_node("ecs", "service", "api")
    db = make_aws_node("rds", "instance", "db")
    other = make_aws_node("s3", "bucket", "assets")

    # Active edge marked rejected.
    rejected_active = make_edge(
        "e-rej",
        api.id,
        db.id,
        review_state=ReviewState.REJECTED,
        confirmed=False,
    )
    with pytest.raises(GraphError, match="rejected_edges"):
        build_graph(resources=[api, db], edges=[rejected_active])

    # Same edge in both active and rejected lists.
    active = make_edge("e-dup", api.id, db.id)
    with pytest.raises(GraphError, match="both active and rejected"):
        build_graph(resources=[api, db], edges=[active], rejected_edges=[active])

    # Group member starts at a different dependent.
    edge_from_other = make_edge("e-other", other.id, db.id)
    bad_dependent_group = DependencyGroup(
        id="grp-bad-dep",
        dependent_resource_id=api.id,
        member_edge_ids=[edge_from_other.id],
        mode=GroupMode.ALL,
        scope=GroupScope.PRIMARY,
    )
    with pytest.raises(GraphError, match="not dependent"):
        build_graph(
            resources=[api, db, other],
            edges=[edge_from_other],
            groups=[bad_dependent_group],
        )

    # Edge in two groups within the same scope.
    e1 = make_edge("e-1", api.id, db.id)
    g1 = DependencyGroup(
        id="grp-1",
        dependent_resource_id=api.id,
        member_edge_ids=[e1.id],
        mode=GroupMode.ALL,
        scope=GroupScope.PRIMARY,
    )
    g2 = DependencyGroup(
        id="grp-2",
        dependent_resource_id=api.id,
        member_edge_ids=[e1.id],
        mode=GroupMode.ANY,
        scope=GroupScope.PRIMARY,
    )
    with pytest.raises(GraphError, match="already belongs to group"):
        build_graph(resources=[api, db], edges=[e1], groups=[g1, g2])

    # Stack referencing a missing resource.
    missing_id = aws_id(ACCOUNT, PRIMARY, "sqs", "queue", "missing")
    bad_stack = Stack(
        id="stk-1",
        name="checkout",
        criticality=StackCriticality.HIGH,
        root_resource_ids=[api.id],
        resource_ids=[api.id, missing_id],
        primary_region=PRIMARY,
        discovery_confidence=1.0,
    )
    with pytest.raises(GraphError, match="missing resource"):
        build_graph(resources=[api], stacks=[bad_stack])

    # StackService referencing a resource outside its stack.
    valid_stack = Stack(
        id="stk-1",
        name="checkout",
        criticality=StackCriticality.HIGH,
        root_resource_ids=[api.id],
        resource_ids=[api.id],
        service_ids=["svc-1"],
        primary_region=PRIMARY,
        discovery_confidence=1.0,
    )
    bad_service = StackService(
        id="svc-1",
        stack_id="stk-1",
        name="checkout-api",
        resource_ids=[api.id, db.id],
    )
    with pytest.raises(GraphError, match="outside stack"):
        build_graph(
            resources=[api, db],
            stacks=[valid_stack],
            stack_services=[bad_service],
        )

    # StackResource referencing a resource not in the stack.
    bad_member = StackResource(
        stack_id="stk-1",
        resource_id=db.id,
        rto_scope=RtoScope.IN_SCOPE,
        scope_source=ScopeSource.USER,
    )
    with pytest.raises(GraphError, match="not in stack"):
        build_graph(
            resources=[api, db],
            stacks=[
                Stack(
                    id="stk-1",
                    name="checkout",
                    criticality=StackCriticality.HIGH,
                    root_resource_ids=[api.id],
                    resource_ids=[api.id],
                    primary_region=PRIMARY,
                    discovery_confidence=1.0,
                )
            ],
            stack_resources=[bad_member],
        )


def test_unknown_lookups_raise_graph_error() -> None:
    api = make_aws_node("ecs", "service", "api")
    graph = build_graph(resources=[api])

    with pytest.raises(GraphError, match="unknown resource"):
        graph.resource("missing")
    with pytest.raises(GraphError, match="unknown edge"):
        graph.edge("missing")
    with pytest.raises(GraphError, match="unknown dependency group"):
        graph.group_members("missing")
    with pytest.raises(GraphError, match="unknown resource"):
        dependency_closure(graph, ["missing"])


# --- fixture integration ------------------------------------------------------


def test_builds_from_repository_fixtures() -> None:
    fixtures_dir = Path(__file__).resolve().parents[4] / "fixtures/graphs"
    minimal = load_fixture(fixtures_dir / "minimal.yaml")
    graph = build_graph(
        resources=minimal.resources,
        edges=minimal.edges,
        groups=minimal.groups,
        mechanisms=minimal.mechanisms,
        stacks=minimal.stacks,
        stack_resources=minimal.stack_resources,
        stack_services=minimal.stack_services,
    )
    assert len(graph.resources) == len(minimal.resources)
    assert graph.multigraph.number_of_edges() == len(minimal.edges)
    assert has_cycles(graph) is False
