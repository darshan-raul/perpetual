"""A persisted override survives rescans without changing published discovery."""

from pathlib import Path

import pytest

from perpetual.evidence import edge_fingerprint
from perpetual.fixtures import load_fixture
from perpetual.graph.overrides import GraphData, apply_overrides, dump_overrides, parse_overrides
from perpetual.models import DependencyEdge, GraphOverride, OverrideKind, OverrideStatus
from perpetual.persistence import (
    PersistenceError,
    ProjectRepository,
    create_project,
    make_engine,
    make_session_factory,
    transaction,
    upgrade,
)


def test_persisted_rejection_reproposal_orphan_and_withdrawal() -> None:
    fixture = load_fixture(Path(__file__).resolve().parents[4] / "fixtures/graphs/minimal.yaml")
    engine = make_engine("sqlite:///:memory:")
    upgrade(engine)
    factory = make_session_factory(engine)
    original = fixture.edges[0]
    rejection = GraphOverride(
        id="reject-db",
        project_id="p1",
        kind=OverrideKind.REJECT_EDGE,
        target=edge_fingerprint(original),
        payload={},
        author="operator",
        created_at=fixture.captured_at,
    )
    with transaction(factory) as session:
        create_project(session, "p1", "First", fixture.captured_at)
        create_project(session, "p2", "Second", fixture.captured_at)
        repository = ProjectRepository(session, "p1")
        repository.create_snapshot("s1", "live", fixture.captured_at)
        repository.save_resources("s1", fixture.resources)
        repository.save_edges("s1", fixture.edges)
        repository.publish_snapshot("s1", fixture.captured_at)
        repository.add_override(rejection)

    with transaction(factory) as session:
        repository = ProjectRepository(session, "p1")
        graph = GraphData(resources=repository.resources("s1"), edges=repository.edges("s1"))
        result = apply_overrides(graph, repository.overrides(), project_id="p1")
        assert result.graph.edges == []
        assert repository.edges("s1") == [original]
        exported = dump_overrides(repository.overrides(), project_id="p1")
        assert parse_overrides(exported, project_id="p1") == [rejection]

        # Fresh source evidence differs, but the persisted old source claim supplies
        # the context needed to explain why this rejected dependency returned.
        current = DependencyEdge.model_validate(
            original.model_dump()
            | {
                "evidence": [
                    original.evidence[0].model_dump()
                    | {"value_summary": "new dependency reference"}
                ]
            }
        )
        graph = graph.model_copy(update={"edges": [current]})
        result = apply_overrides(
            graph, repository.overrides(), project_id="p1", historical_edges=repository.edges("s1")
        )
        assert result.reproposals[0].rejection_id == rejection.id
        assert result.graph.edges == [current]

        missing = apply_overrides(
            GraphData(),
            repository.overrides(),
            project_id="p1",
            historical_edges=repository.edges("s1"),
        )
        repository.set_override_status(rejection.id, missing.overrides[0].status)
        assert repository.overrides()[0].status is OverrideStatus.ORPHANED

        other = ProjectRepository(session, "p2")
        with pytest.raises(PersistenceError, match="no override"):
            other.delete_override(rejection.id)
        assert repository.overrides()
        repository.delete_override(rejection.id)
        assert repository.overrides() == []
        assert repository.edges("s1") == [original]
    engine.dispose()
