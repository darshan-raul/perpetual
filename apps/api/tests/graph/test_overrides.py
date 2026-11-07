"""Override replay and rescan contracts (spec §23); no AWS or database required."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from perpetual.evidence import edge_fingerprint
from perpetual.fixtures import load_fixture
from perpetual.graph.overrides import GraphData, OverrideError, apply_overrides, edge_target
from perpetual.models import (
    Criticality,
    DependencyEdge,
    EdgeOrigin,
    GraphOverride,
    OverrideKind,
    OverrideStatus,
    ReviewState,
    RtoScope,
    ScopeSource,
    SourceType,
    StackService,
)
from perpetual.models.override import AddEdgePayload, DrPosture
from perpetual.models.properties import ExternalResourceProperties

NOW = datetime(2026, 11, 7, tzinfo=UTC)
PROJECT = "test-project"
EXTERNAL = "external://payments/stripe"


@pytest.fixture
def graph() -> GraphData:
    path = Path(__file__).resolve().parents[4] / "fixtures/graphs/minimal.yaml"
    fixture = load_fixture(path)
    return GraphData(resources=fixture.resources, edges=fixture.edges, stacks=fixture.stacks)


def change(
    kind: OverrideKind,
    target: str,
    payload: dict[str, Any] | None = None,
    *,
    override_id: str = "change-1",
    created_at: datetime = NOW,
    project_id: str = PROJECT,
    status: OverrideStatus = OverrideStatus.ACTIVE,
) -> GraphOverride:
    return GraphOverride(
        id=override_id,
        project_id=project_id,
        kind=kind,
        target=target,
        payload=payload or {},
        author="reviewer",
        created_at=created_at,
        status=status,
    )


def addition(edge: DependencyEdge, *, target: str | None = None) -> GraphOverride:
    payload = AddEdgePayload(
        from_resource_id=edge.from_resource_id,
        to_resource_id=target or edge.to_resource_id,
        relationship_type=edge.relationship_type,
        criticality=Criticality.OPTIONAL,
        note="needed for checkout",
    )
    return change(OverrideKind.ADD_EDGE, edge_target(payload), payload.model_dump(mode="json"))


def external_node() -> GraphOverride:
    return change(
        OverrideKind.ADD_NODE,
        EXTERNAL,
        {
            "node_kind": "external",
            "resource_id": EXTERNAL,
            "provider": "external",
            "service": "payments",
            "resource_type": "saas",
        },
        override_id="node",
        created_at=NOW + timedelta(days=1),
    )


def changed_claim(edge: DependencyEdge) -> DependencyEdge:
    evidence = edge.evidence[0].model_dump() | {"value_summary": "new configuration reference"}
    return DependencyEdge.model_validate(
        edge.model_dump() | {"id": "new-edge", "evidence": [evidence]}
    )


def test_confirm_adds_traceable_assertion_without_changing_source(graph: GraphData) -> None:
    before = graph.model_dump()
    override = change(OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]))
    result = apply_overrides(graph, [override], project_id=PROJECT)
    edge = result.graph.edges[0]
    assert (edge.confidence, edge.confirmed, edge.review_state) == (
        1.0,
        True,
        ReviewState.CONFIRMED,
    )
    assertion = edge.evidence[-1]
    assert assertion.source_type is SourceType.USER_CONFIRMATION
    assert assertion.collected_at == NOW
    assert override.id in assertion.source
    assert graph.model_dump() == before
    edge.evidence.clear()
    assert graph.model_dump() == before  # result collections also cannot mutate the source


def test_replay_is_deterministic_and_reactivates_an_orphan(graph: GraphData) -> None:
    override = change(
        OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]), status=OverrideStatus.ORPHANED
    )
    first = apply_overrides(graph, [override], project_id=PROJECT)
    second = apply_overrides(graph, [override], project_id=PROJECT)
    assert first == second
    assert first.overrides[0].status is OverrideStatus.ACTIVE
    assert override.status is OverrideStatus.ORPHANED


def test_confirmation_survives_scan_edge_id_change(graph: GraphData) -> None:
    override = change(OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]))
    renamed = graph.edges[0].model_copy(update={"id": "fresh-scan-id"})
    result = apply_overrides(
        graph.model_copy(update={"edges": [renamed]}), [override], project_id=PROJECT
    )
    assert result.graph.edges[0].confirmed is True


def test_edit_preserves_confidence_and_targets_only_one_relationship(graph: GraphData) -> None:
    original = graph.edges[0].model_copy(update={"confidence": 0.5})
    parallel = DependencyEdge.model_validate(
        original.model_dump() | {"id": "encryption", "relationship_type": "encrypted_by"}
    )
    source = graph.model_copy(update={"edges": [original, parallel]})
    override = change(OverrideKind.EDIT_EDGE, edge_target(original), {"criticality": "optional"})
    result = apply_overrides(source, [override], project_id=PROJECT)
    by_id = {edge.id: edge for edge in result.graph.edges}
    edited = by_id[original.id]
    assert edited.criticality is Criticality.OPTIONAL
    assert edited.review_state is ReviewState.EDITED
    assert edited.confidence == 0.5
    assert edited.confirmed is None
    assert by_id[parallel.id] == parallel


def test_edit_relationship_is_reapplied_after_rescan(graph: GraphData) -> None:
    override = change(
        OverrideKind.EDIT_EDGE, edge_target(graph.edges[0]), {"relationship_type": "reads_from"}
    )
    result = apply_overrides(graph, [override], project_id=PROJECT)
    assert result.graph.edges[0].relationship_type.value == "reads_from"
    assert apply_overrides(graph, result.overrides, project_id=PROJECT).graph == result.graph


def test_reject_suppresses_the_source_claim_and_keeps_review_record(graph: GraphData) -> None:
    edge = graph.edges[0]
    override = change(OverrideKind.REJECT_EDGE, edge_fingerprint(edge))
    result = apply_overrides(graph, [override], project_id=PROJECT)
    assert result.graph.edges == []
    assert result.rejected_edges[0].review_state is ReviewState.REJECTED
    assert result.overrides[0].status is OverrideStatus.ACTIVE
    assert graph.edges == [edge]


def test_rescan_times_counts_and_ids_do_not_revive_a_rejection(graph: GraphData) -> None:
    edge = graph.edges[0]
    override = change(OverrideKind.REJECT_EDGE, edge_fingerprint(edge))
    evidence = edge.evidence[0].model_copy(update={"id": "fresh", "collected_at": NOW})
    fresh = edge.model_copy(update={"id": "fresh-edge", "evidence": [evidence], "confidence": 0.8})
    result = apply_overrides(
        graph.model_copy(update={"edges": [fresh]}), [override], project_id=PROJECT
    )
    assert result.graph.edges == []
    assert result.reproposals == ()


def test_changed_evidence_is_reproposed_with_prior_rejection_context(graph: GraphData) -> None:
    old = graph.edges[0]
    override = change(OverrideKind.REJECT_EDGE, edge_fingerprint(old))
    current = changed_claim(old)
    result = apply_overrides(
        graph.model_copy(update={"edges": [current]}),
        [override],
        project_id=PROJECT,
        historical_edges=[old],
    )
    assert result.graph.edges == [current]
    assert result.graph.edges[0].review_state is ReviewState.UNREVIEWED
    assert result.overrides[0].status is OverrideStatus.ACTIVE
    assert len(result.reproposals) == 1
    link = result.reproposals[0]
    assert (link.edge_id, link.rejection_id) == (current.id, override.id)
    assert link.old_fingerprint != link.new_fingerprint


def test_missing_history_is_reported_without_suppressing_new_evidence(graph: GraphData) -> None:
    old = graph.edges[0]
    override = change(OverrideKind.REJECT_EDGE, edge_fingerprint(old))
    current = changed_claim(old)
    result = apply_overrides(
        graph.model_copy(update={"edges": [current]}), [override], project_id=PROJECT
    )
    assert result.graph.edges == [current]
    assert "historical" in result.orphan_reasons[override.id]


def test_parallel_relationship_is_not_rejected(graph: GraphData) -> None:
    edge = graph.edges[0]
    parallel = DependencyEdge.model_validate(
        edge.model_dump() | {"id": "encrypted", "relationship_type": "encrypted_by"}
    )
    override = change(OverrideKind.REJECT_EDGE, edge_fingerprint(edge))
    result = apply_overrides(
        graph.model_copy(update={"edges": [edge, parallel]}), [override], project_id=PROJECT
    )
    assert result.graph.edges == [parallel]


def test_latest_confirmation_can_restore_rejected_edge(graph: GraphData) -> None:
    reject = change(OverrideKind.REJECT_EDGE, edge_fingerprint(graph.edges[0]), override_id="a")
    confirm = change(OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]), override_id="b")
    result = apply_overrides(graph, [confirm, reject], project_id=PROJECT)
    assert result.graph.edges[0].confirmed is True
    assert result.rejected_edges == ()
    assert [override.id for override in result.overrides] == ["a", "b"]


def test_later_rejection_wins_over_confirmation(graph: GraphData) -> None:
    reject = change(OverrideKind.REJECT_EDGE, edge_fingerprint(graph.edges[0]), override_id="b")
    confirm = change(OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]), override_id="a")
    result = apply_overrides(graph, [reject, confirm], project_id=PROJECT)
    assert result.graph.edges == []


def test_added_edge_merges_when_discovered_on_a_later_scan(graph: GraphData) -> None:
    override = addition(graph.edges[0])
    first = apply_overrides(graph.model_copy(update={"edges": []}), [override], project_id=PROJECT)
    user_edge = first.graph.edges[0]
    assert user_edge.origin is EdgeOrigin.USER
    assert user_edge.confidence == 1.0
    assert user_edge.evidence[0].value_summary == "needed for checkout"
    later = apply_overrides(graph, first.overrides, project_id=PROJECT)
    assert len(later.graph.edges) == 1
    merged = later.graph.edges[0]
    assert merged.id == graph.edges[0].id
    assert merged.origin is EdgeOrigin.DISCOVERED
    assert merged.criticality is Criticality.OPTIONAL
    assert len(merged.evidence) == 2
    assert graph.edges[0].evidence == merged.evidence[:1]


def test_removing_addition_restores_discovery_and_removes_user_only_edge(graph: GraphData) -> None:
    empty = graph.model_copy(update={"edges": []})
    assert apply_overrides(empty, [addition(graph.edges[0])], project_id=PROJECT).graph.edges
    assert apply_overrides(empty, [], project_id=PROJECT).graph.edges == []
    assert apply_overrides(graph, [], project_id=PROJECT).graph.edges == graph.edges


def test_missing_edge_endpoint_orphans_addition_and_can_return(graph: GraphData) -> None:
    override = addition(graph.edges[0], target=EXTERNAL)
    first = apply_overrides(graph, [override], project_id=PROJECT)
    assert first.overrides[0].status is OverrideStatus.ORPHANED
    assert "endpoint" in first.orphan_reasons[override.id]
    later = apply_overrides(graph, [*first.overrides, external_node()], project_id=PROJECT)
    assert not later.orphan_reasons
    assert len(later.graph.edges) == 2


def test_missing_typed_edge_orphans_confirmation(graph: GraphData) -> None:
    override = change(OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]))
    result = apply_overrides(graph.model_copy(update={"edges": []}), [override], project_id=PROJECT)
    assert result.overrides[0].status is OverrideStatus.ORPHANED


def test_external_node_is_created_before_earlier_edge_and_defaults_to_unknown(
    graph: GraphData,
) -> None:
    result = apply_overrides(
        graph, [addition(graph.edges[0], target=EXTERNAL), external_node()], project_id=PROJECT
    )
    node = next(node for node in result.graph.resources if node.id == EXTERNAL)
    assert isinstance(node.typed_properties, ExternalResourceProperties)
    assert node.typed_properties.dr_posture is DrPosture.UNKNOWN
    assert node.source_refs[0].source_type is SourceType.USER_CONFIRMATION
    assert len(result.graph.edges) == 2


def test_external_posture_is_preserved(graph: GraphData) -> None:
    override = external_node()
    override = GraphOverride.model_validate(
        override.model_dump() | {"payload": override.payload | {"dr_posture": "available"}}
    )
    result = apply_overrides(graph, [override], project_id=PROJECT)
    node = next(node for node in result.graph.resources if node.id == EXTERNAL)
    assert isinstance(node.typed_properties, ExternalResourceProperties)
    assert node.typed_properties.dr_posture is DrPosture.AVAILABLE


def test_placeholder_uses_canonical_identity_and_later_discovery_wins(graph: GraphData) -> None:
    resource = graph.resources[0]
    override = change(
        OverrideKind.ADD_NODE,
        resource.id,
        {
            "node_kind": "placeholder",
            "resource_id": resource.id,
            "provider": "aws",
            "service": resource.service,
            "resource_type": resource.resource_type,
            "name": "placeholder",
        },
    )
    first = apply_overrides(GraphData(), [override], project_id=PROJECT).graph.resources[0]
    assert first.account_id == resource.account_id
    assert first.region == resource.region
    assert first.typed_properties is None
    later = apply_overrides(graph, [override], project_id=PROJECT)
    found = next(node for node in later.graph.resources if node.id == resource.id)
    assert found.name == resource.name
    assert len(found.source_refs) == len(resource.source_refs) + 1


def test_node_identity_contradictions_fail(graph: GraphData) -> None:
    override = external_node()
    bad = GraphOverride.model_validate(
        override.model_dump() | {"payload": override.payload | {"service": "wrong"}}
    )
    with pytest.raises(OverrideError, match="contradicts"):
        apply_overrides(graph, [bad], project_id=PROJECT)


def test_edit_node_assigns_service_and_explicit_rto_scope(graph: GraphData) -> None:
    resource_id = graph.resources[0].id
    service = StackService(id="api", stack_id="checkout", name="API")
    source = graph.model_copy(update={"stack_services": [service]})
    override = change(
        OverrideKind.EDIT_NODE,
        resource_id,
        {"stack_id": "checkout", "service_id": "api", "rto_scope": "out_of_scope"},
    )
    result = apply_overrides(source, [override], project_id=PROJECT)
    assert result.graph.stack_services[0].resource_ids == [resource_id]
    assert result.graph.stacks[0].service_ids == ["api"]
    member = result.graph.stack_resources[0]
    assert (member.rto_scope, member.scope_source) == (RtoScope.OUT_OF_SCOPE, ScopeSource.USER)
    assert source.stack_services[0].resource_ids == []


def test_remove_membership_cleans_roots_services_and_scope(graph: GraphData) -> None:
    resource_id = graph.stacks[0].root_resource_ids[0]
    service = StackService(id="api", stack_id="checkout", name="API", resource_ids=[resource_id])
    source = graph.model_copy(update={"stack_services": [service]})
    scope = change(
        OverrideKind.EDIT_NODE,
        resource_id,
        {"stack_id": "checkout", "rto_scope": "in_scope"},
        override_id="a",
    )
    remove = change(
        OverrideKind.EDIT_NODE,
        resource_id,
        {"stack_id": "checkout", "member": False},
        override_id="b",
    )
    result = apply_overrides(source, [scope, remove], project_id=PROJECT)
    assert resource_id not in result.graph.stacks[0].resource_ids
    assert result.graph.stacks[0].root_resource_ids == []
    assert result.graph.stack_services[0].resource_ids == []
    assert result.graph.stack_resources == []
    assert len(result.graph.resources) == len(graph.resources)


def test_add_member_without_inventing_rto_scope(graph: GraphData) -> None:
    member = change(OverrideKind.EDIT_NODE, EXTERNAL, {"stack_id": "checkout", "member": True})
    result = apply_overrides(graph, [external_node(), member], project_id=PROJECT)
    assert EXTERNAL in result.graph.stacks[0].resource_ids
    assert result.graph.stack_resources == []  # default classification belongs to P1-03


@pytest.mark.parametrize(
    "payload",
    [
        {"stack_id": "missing", "member": True},
        {"stack_id": "checkout", "service_id": "missing"},
    ],
)
def test_missing_membership_targets_are_orphans(graph: GraphData, payload: dict[str, Any]) -> None:
    override = change(OverrideKind.EDIT_NODE, graph.resources[0].id, payload)
    result = apply_overrides(graph, [override], project_id=PROJECT)
    assert result.overrides[0].status is OverrideStatus.ORPHANED


def test_removal_and_assignment_together_is_an_error(graph: GraphData) -> None:
    override = change(
        OverrideKind.EDIT_NODE,
        graph.resources[0].id,
        {"stack_id": "checkout", "member": False, "rto_scope": "in_scope"},
    )
    with pytest.raises(OverrideError, match="removing"):
        apply_overrides(graph, [override], project_id=PROJECT)


def test_foreign_project_and_duplicate_overrides_are_refused(graph: GraphData) -> None:
    override = change(OverrideKind.CONFIRM_EDGE, edge_target(graph.edges[0]))
    with pytest.raises(OverrideError, match="another project"):
        apply_overrides(graph, [override], project_id="other")
    with pytest.raises(OverrideError, match="duplicate override"):
        apply_overrides(graph, [override, override], project_id=PROJECT)


def test_duplicate_graph_ids_are_not_silently_dropped(graph: GraphData) -> None:
    bad = graph.model_copy(update={"resources": [*graph.resources, graph.resources[0]]})
    with pytest.raises(OverrideError, match="duplicate resource"):
        apply_overrides(bad, [], project_id=PROJECT)


def test_duplicate_typed_edges_and_edit_collisions_are_refused(graph: GraphData) -> None:
    duplicate = graph.edges[0].model_copy(update={"id": "other"})
    with pytest.raises(OverrideError, match="ambiguous"):
        apply_overrides(
            graph.model_copy(update={"edges": [*graph.edges, duplicate]}), [], project_id=PROJECT
        )
    parallel = DependencyEdge.model_validate(
        duplicate.model_dump() | {"relationship_type": "encrypted_by"}
    )
    override = change(
        OverrideKind.EDIT_EDGE, edge_target(graph.edges[0]), {"relationship_type": "encrypted_by"}
    )
    with pytest.raises(OverrideError, match="ambiguous"):
        apply_overrides(
            graph.model_copy(update={"edges": [*graph.edges, parallel]}),
            [override],
            project_id=PROJECT,
        )


def test_malformed_targets_fail_instead_of_becoming_orphans(graph: GraphData) -> None:
    for kind, target in [
        (OverrideKind.REJECT_EDGE, "not-a-hash"),
        (OverrideKind.CONFIRM_EDGE, "scan-edge-id"),
        (OverrideKind.CONFIRM_EDGE, "edge:[]"),
    ]:
        with pytest.raises(OverrideError):
            apply_overrides(graph, [change(kind, target)], project_id=PROJECT)


def test_all_override_kinds_from_repository_fixture() -> None:
    path = Path(__file__).resolve().parents[4] / "fixtures/graphs/review-overrides.yaml"
    fixture = load_fixture(path)
    source = GraphData(resources=fixture.resources, edges=fixture.edges, stacks=fixture.stacks)
    before = source.model_dump()
    result = apply_overrides(source, fixture.overrides, project_id="fixture")
    assert {override.kind for override in result.overrides} == set(OverrideKind)
    assert not result.orphan_reasons
    assert len(result.graph.resources) == 3
    assert len(result.graph.edges) == 2
    assert len(result.rejected_edges) == 1
    assert result.graph.stack_resources[0].scope_source is ScopeSource.USER
    assert source.model_dump() == before


def test_conflicting_node_declarations_are_refused(graph: GraphData) -> None:
    first = external_node()
    second = GraphOverride.model_validate(
        first.model_dump()
        | {"id": "another", "payload": first.payload | {"dr_posture": "available"}}
    )
    with pytest.raises(OverrideError, match="conflicting node declarations"):
        apply_overrides(graph, [first, second], project_id=PROJECT)


def test_rejection_orphan_reactivates_when_original_claim_returns(graph: GraphData) -> None:
    original = graph.edges[0]
    rejection = change(OverrideKind.REJECT_EDGE, edge_fingerprint(original))
    missing = apply_overrides(
        GraphData(), [rejection], project_id=PROJECT, historical_edges=[original]
    )
    assert "endpoint" in missing.orphan_reasons[rejection.id]
    returned = apply_overrides(graph, missing.overrides, project_id=PROJECT)
    assert returned.overrides[0].status is OverrideStatus.ACTIVE
    assert returned.graph.edges == []


def test_history_without_current_typed_edge_reports_an_orphan(graph: GraphData) -> None:
    original = graph.edges[0]
    rejection = change(OverrideKind.REJECT_EDGE, edge_fingerprint(original))
    result = apply_overrides(
        graph.model_copy(update={"edges": []}),
        [rejection],
        project_id=PROJECT,
        historical_edges=[original],
    )
    assert "typed edge" in result.orphan_reasons[rejection.id]


def test_old_rejection_links_even_after_several_scans(graph: GraphData) -> None:
    original = graph.edges[0]
    intermediate = changed_claim(original)
    latest = DependencyEdge.model_validate(
        intermediate.model_dump()
        | {"evidence": [intermediate.evidence[0].model_dump() | {"value_summary": "third version"}]}
    )
    rejection = change(OverrideKind.REJECT_EDGE, edge_fingerprint(original))
    result = apply_overrides(
        graph.model_copy(update={"edges": [latest]}),
        [rejection],
        project_id=PROJECT,
        historical_edges=[original, intermediate],
    )
    assert result.reproposals[0].old_fingerprint == rejection.target
    assert result.reproposals[0].new_fingerprint == edge_fingerprint(latest)


def test_service_move_does_not_change_membership_in_other_stacks(graph: GraphData) -> None:
    resource_id = graph.resources[0].id
    other_stack = graph.stacks[0].model_copy(update={"id": "other"})
    services = [
        StackService(id="old", stack_id="checkout", name="Old", resource_ids=[resource_id]),
        StackService(id="new", stack_id="checkout", name="New"),
        StackService(
            id="other-service", stack_id="other", name="Other", resource_ids=[resource_id]
        ),
    ]
    source = graph.model_copy(
        update={"stacks": [*graph.stacks, other_stack], "stack_services": services}
    )
    override = change(
        OverrideKind.EDIT_NODE, resource_id, {"stack_id": "checkout", "service_id": "new"}
    )
    result = apply_overrides(source, [override], project_id=PROJECT)
    by_id = {service.id: service for service in result.graph.stack_services}
    assert by_id["old"].resource_ids == []
    assert by_id["new"].resource_ids == [resource_id]
    assert by_id["other-service"].resource_ids == [resource_id]


def test_assigning_a_foreign_stack_service_is_refused(graph: GraphData) -> None:
    service = StackService(id="foreign", stack_id="other", name="Other")
    source = graph.model_copy(update={"stack_services": [service]})
    override = change(
        OverrideKind.EDIT_NODE,
        graph.resources[0].id,
        {"stack_id": "checkout", "service_id": "foreign"},
    )
    with pytest.raises(OverrideError, match="another stack"):
        apply_overrides(source, [override], project_id=PROJECT)


def test_target_must_match_add_payload(graph: GraphData) -> None:
    override = addition(graph.edges[0]).model_copy(update={"target": "different"})
    with pytest.raises(OverrideError, match="does not match"):
        apply_overrides(graph, [override], project_id=PROJECT)


def test_input_with_dangling_edge_is_refused(graph: GraphData) -> None:
    with pytest.raises(OverrideError, match="missing endpoint"):
        apply_overrides(graph.model_copy(update={"resources": []}), [], project_id=PROJECT)


def test_missing_resource_or_membership_orphans_node_edit(graph: GraphData) -> None:
    override = change(
        OverrideKind.EDIT_NODE, EXTERNAL, {"stack_id": "checkout", "rto_scope": "in_scope"}
    )
    missing_resource = apply_overrides(graph, [override], project_id=PROJECT)
    assert "resource is absent" in missing_resource.orphan_reasons[override.id]
    missing_membership = apply_overrides(graph, [override, external_node()], project_id=PROJECT)
    assert "not a member" in missing_membership.orphan_reasons[override.id]


def test_superseded_confirmation_does_not_approve_reproposed_evidence(graph: GraphData) -> None:
    original = graph.edges[0]
    confirm = change(OverrideKind.CONFIRM_EDGE, edge_target(original), override_id="a")
    reject = change(OverrideKind.REJECT_EDGE, edge_fingerprint(original), override_id="b")
    current = changed_claim(original).model_copy(update={"confidence": 0.5})
    source = graph.model_copy(update={"edges": [current]})
    result = apply_overrides(
        source, [confirm, reject], project_id=PROJECT, historical_edges=[original]
    )
    edge = result.graph.edges[0]
    assert edge.review_state is ReviewState.UNREVIEWED
    assert edge.confirmed is None
    assert edge.confidence == 0.5
    assert edge.evidence == current.evidence
    assert result.reproposals

    accept_new = change(OverrideKind.CONFIRM_EDGE, edge_target(current), override_id="c")
    accepted = apply_overrides(
        source, [confirm, reject, accept_new], project_id=PROJECT, historical_edges=[original]
    )
    assert accepted.graph.edges[0].review_state is ReviewState.CONFIRMED


def test_edit_after_rejection_does_not_restore_edge(graph: GraphData) -> None:
    original = graph.edges[0]
    reject = change(OverrideKind.REJECT_EDGE, edge_fingerprint(original), override_id="a")
    edit = change(
        OverrideKind.EDIT_EDGE, edge_target(original), {"criticality": "optional"}, override_id="b"
    )
    result = apply_overrides(graph, [reject, edit], project_id=PROJECT)
    assert result.graph.edges == []
    assert result.rejected_edges[0].review_state is ReviewState.REJECTED
    assert result.rejected_edges[0].criticality is Criticality.OPTIONAL
