"""Project-scoped repository: round trips, isolation, immutability (spec §15.4, §23, §56.3,
§71.1, §75, §76)."""

from collections.abc import Iterator
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from perpetual.models import (
    Attribution,
    CoverageStatus,
    Criticality,
    DependencyEdge,
    DependencyGroup,
    EdgeOrigin,
    EvaluationInput,
    GraphOverride,
    GroupMode,
    GroupScope,
    MechanismKind,
    OverrideKind,
    OverrideStatus,
    RecoveryMechanism,
    RelationshipType,
    ResolvedObservation,
    ResourceNode,
    RtoScope,
    ScanCoverage,
    ScopeSource,
    Stack,
    StackCriticality,
    StackResource,
    StackService,
)
from perpetual.persistence import (
    PersistenceError,
    ProjectRepository,
    create_project,
    make_engine,
    make_session_factory,
    upgrade,
)
from tests.models.builders import NOW, make_evidence

SVC = "aws://123456789012/ap-south-1/ecs/service/checkout"
DB = "aws://123456789012/ap-south-1/rds/db/checkout"
QUEUE = "aws://123456789012/ap-south-1/sqs/queue/orders"
DIGEST = "sha256:" + "a" * 64


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    upgrade(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        create_project(session, "p1", "Project one", NOW)
        create_project(session, "p2", "Project two", NOW)
        yield session


@pytest.fixture
def repo(session: Session) -> ProjectRepository:
    repo = ProjectRepository(session, "p1")
    repo.add_scan("scan-1", NOW, ["aws_api"])
    repo.create_snapshot("snap-1", "live", NOW, scan_id="scan-1")
    return repo


def node(resource_id: str, service: str, resource_type: str, **extra: Any) -> ResourceNode:
    return ResourceNode.model_validate(
        {
            "id": resource_id,
            "provider": "aws",
            "service": service,
            "resource_type": resource_type,
            "account_id": "123456789012",
            "region": "ap-south-1",
            "discovered_at": NOW,
        }
        | extra
    )


def edge(edge_id: str, to: str, evidence_ids: list[str]) -> DependencyEdge:
    return DependencyEdge(
        id=edge_id,
        from_resource_id=SVC,
        to_resource_id=to,
        relationship_type=RelationshipType.DEPENDS_ON,
        confidence=0.9,
        evidence=[make_evidence(id=item) for item in evidence_ids],
        inferred=True,
        origin=EdgeOrigin.DISCOVERED,
        criticality=Criticality.REQUIRED,
    )


def override(override_id: str = "ov-1", project_id: str = "p1") -> GraphOverride:
    return GraphOverride(
        id=override_id,
        project_id=project_id,
        kind=OverrideKind.CONFIRM_EDGE,
        target="e1",
        payload={},
        author="user",
        created_at=NOW,
    )


# --- round trips -------------------------------------------------------------------


def test_resources_round_trip_with_aware_datetimes(repo: ProjectRepository) -> None:
    nodes = [node(SVC, "ecs", "service"), node(DB, "rds", "db", tags={"team": "pay"})]
    repo.save_resources("snap-1", nodes)
    loaded = repo.resources("snap-1")
    assert loaded == sorted(nodes, key=lambda n: n.id)
    assert loaded[0].discovered_at.tzinfo is not None


def test_edges_keep_evidence_order_and_share_evidence_rows(repo: ProjectRepository) -> None:
    edges = [edge("e1", DB, ["ev-b", "ev-a"]), edge("e2", QUEUE, ["ev-a"])]
    repo.save_edges("snap-1", edges)
    assert repo.edges("snap-1") == edges
    # ev-a is attached to both edges but stored once.
    assert [item.id for item in repo.evidence("snap-1")] == ["ev-a", "ev-b"]


def test_same_evidence_id_with_other_content_is_refused(repo: ProjectRepository) -> None:
    repo.save_edges("snap-1", [edge("e1", DB, ["ev-a"])])
    other = edge("e2", QUEUE, []).model_copy(
        update={"evidence": [make_evidence(id="ev-a", source="other")]}
    )
    with pytest.raises(PersistenceError, match="other content"):
        repo.save_edges("snap-1", [other])


def test_groups_observations_mechanisms_round_trip(repo: ProjectRepository) -> None:
    group = DependencyGroup(
        id="g1",
        dependent_resource_id=SVC,
        member_edge_ids=["e1", "e2"],
        mode=GroupMode.ANY,
        scope=GroupScope.PRIMARY,
    )
    observation = ResolvedObservation(
        id="obs-1",
        source_type="cloudtrail",
        attribution=Attribution.AMBIGUOUS,
        candidate_from_resource_ids=[SVC, "aws://123456789012/ap-south-1/ecs/service/admin"],
        candidate_to_resource_ids=[DB],
        observed_from=NOW - timedelta(days=1),
        observed_to=NOW,
        observation_count=3,
    )
    mechanism = RecoveryMechanism(
        id="m1",
        primary_resource_id=DB,
        target_region="ap-south-2",
        target_account_id="123456789012",
        kind=MechanismKind.LIVE_COUNTERPART,
        control_plane_dependent=False,
        confidence=0.9,
    )
    repo.save_groups("snap-1", [group])
    repo.save_observations("snap-1", [observation])
    repo.save_mechanisms("snap-1", [mechanism])
    assert repo.groups("snap-1") == [group]
    assert repo.observations("snap-1") == [observation]
    assert repo.mechanisms("snap-1") == [mechanism]


def test_stacks_round_trip(repo: ProjectRepository) -> None:
    stack = Stack(
        id="checkout",
        name="checkout",
        criticality=StackCriticality.CRITICAL,
        root_resource_ids=[SVC],
        resource_ids=[SVC, DB],
        primary_region="ap-south-1",
        discovery_confidence=0.8,
    )
    members = [
        StackResource(
            stack_id="checkout",
            resource_id=DB,
            rto_scope=RtoScope.IN_SCOPE,
            scope_source=ScopeSource.RULE_DEFAULT,
        )
    ]
    service = StackService(id="svc-api", stack_id="checkout", name="api", resource_ids=[SVC])
    repo.save_stacks("snap-1", [stack], members, [service])
    assert repo.stacks("snap-1") == [stack]
    assert repo.stack_resources("snap-1", "checkout") == members
    assert repo.stack_services("snap-1") == [service]


def test_coverage_round_trip(repo: ProjectRepository) -> None:
    record = ScanCoverage(
        id="cov-1",
        account_id="123456789012",
        region="ap-south-1",
        service="rds",
        operation_family="inventory",
        status=CoverageStatus.COMPLETE,
        started_at=NOW,
        completed_at=NOW,
        pagination_complete=True,
    )
    repo.save_coverage("scan-1", [record])
    assert repo.coverage("scan-1") == [record]


# --- snapshots and scans -----------------------------------------------------------


def test_published_snapshot_is_immutable(repo: ProjectRepository) -> None:
    repo.save_resources("snap-1", [node(SVC, "ecs", "service")])
    repo.publish_snapshot("snap-1", NOW)
    assert repo.is_published("snap-1")
    with pytest.raises(PersistenceError, match="published and can't change"):
        repo.save_resources("snap-1", [node(DB, "rds", "db")])
    with pytest.raises(PersistenceError, match="published"):
        repo.publish_snapshot("snap-1", NOW)


def test_previous_snapshots_and_resource_history_are_kept(repo: ProjectRepository) -> None:
    repo.save_resources("snap-1", [node(DB, "rds", "db")])
    repo.publish_snapshot("snap-1", NOW)
    later = NOW + timedelta(hours=1)
    repo.create_snapshot("snap-2", "live", later)
    repo.save_resources("snap-2", [node(DB, "rds", "db", tags={"v": "2"}, discovered_at=later)])
    assert repo.snapshot_ids() == ["snap-1", "snap-2"]
    history = repo.resource_history(DB)
    assert [snapshot for snapshot, _ in history] == ["snap-1", "snap-2"]
    assert history[1][1].tags == {"v": "2"}


def test_scan_lifecycle(repo: ProjectRepository) -> None:
    assert repo.scan_status("scan-1") == "running"
    with pytest.raises(PersistenceError, match="completed, partial or failed"):
        repo.finish_scan("scan-1", "running", NOW, resource_count=0, edge_count=0)
    repo.finish_scan("scan-1", "partial", NOW, resource_count=2, edge_count=1, errors=["denied"])
    assert repo.scan_status("scan-1") == "partial"
    with pytest.raises(PersistenceError, match="already finished"):
        repo.finish_scan("scan-1", "completed", NOW, resource_count=2, edge_count=1)


# --- project scope -----------------------------------------------------------------


def test_projects_cannot_see_each_other(session: Session, repo: ProjectRepository) -> None:
    repo.save_resources("snap-1", [node(SVC, "ecs", "service")])
    repo.add_override(override())
    other = ProjectRepository(session, "p2")
    assert other.resources("snap-1") == []
    assert other.overrides() == []
    assert other.snapshot_ids() == []
    with pytest.raises(PersistenceError, match="no snapshot"):
        other.save_resources("snap-1", [node(DB, "rds", "db")])
    with pytest.raises(PersistenceError, match="no scan"):
        other.scan_status("scan-1")


def test_unknown_project_and_duplicate_project(session: Session) -> None:
    with pytest.raises(PersistenceError, match="no project"):
        ProjectRepository(session, "missing")
    with pytest.raises(PersistenceError, match="already exists"):
        create_project(session, "p1", "again", NOW)


def test_override_must_belong_to_the_project(repo: ProjectRepository) -> None:
    with pytest.raises(PersistenceError, match="another project"):
        repo.add_override(override(project_id="p2"))


# --- overrides and evaluation inputs -----------------------------------------------


def test_override_status_changes_without_touching_the_edit(repo: ProjectRepository) -> None:
    repo.add_override(override())
    updated = repo.set_override_status("ov-1", OverrideStatus.ORPHANED)
    assert updated.status is OverrideStatus.ORPHANED
    assert repo.overrides(OverrideStatus.ACTIVE) == []
    assert repo.overrides(OverrideStatus.ORPHANED) == [updated]
    assert updated.model_copy(update={"status": OverrideStatus.ACTIVE}) == override()
    with pytest.raises(PersistenceError, match="no override"):
        repo.set_override_status("missing", OverrideStatus.ACTIVE)


def test_evaluation_input_round_trip(repo: ProjectRepository) -> None:
    manifest = EvaluationInput(
        id="eval-1",
        stack_id="checkout",
        failure_scenario="region:ap-south-1",
        primary_snapshot_id="snap-1",
        primary_inventory_completed_at=NOW,
        graph_revision=1,
        override_revision=0,
        group_revision=0,
        requirement_id="req-1",
        requirement_revision=1,
        engine_version="0.0.0",
        config_digest=DIGEST,
        duration_catalog_digest=DIGEST,
        freshness_policy_version="1",
        evaluated_at=NOW.astimezone(UTC),
    )
    repo.add_evaluation_input(manifest)
    assert repo.evaluation_input("eval-1") == manifest
    with pytest.raises(PersistenceError, match="no evaluation input"):
        repo.evaluation_input("missing")
