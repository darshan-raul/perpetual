"""Project-scoped repository (spec §71.1, §75).

Every read and write goes through a `ProjectRepository`, which is bound to one
project and adds `project_id` to every query, so one project can never see
another's rows.

Snapshot rows are written while the snapshot is open and frozen once it is
published (spec §15.4, §76.1: built atomically from a declared set of runs).
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from perpetual.models import (
    DependencyEdge,
    DependencyGroup,
    EvaluationInput,
    Evidence,
    GraphOverride,
    OverrideStatus,
    RecoveryMechanism,
    ResolvedObservation,
    ResourceNode,
    ScanCoverage,
    Stack,
    StackResource,
    StackService,
)
from perpetual.persistence.tables import (
    DependencyGroupRow,
    EdgeEvidenceRow,
    EdgeRow,
    EvaluationInputRow,
    EvidenceRow,
    GraphOverrideRow,
    ObservationRow,
    Project,
    RecoveryMechanismRow,
    ResourceRow,
    ResourceVersionRow,
    Scan,
    ScanCoverageRow,
    Snapshot,
    StackResourceRow,
    StackRow,
    StackServiceRow,
)

ScanStatus = Literal["pending", "running", "completed", "partial", "failed"]
SnapshotKind = Literal["live", "planned"]
_SCAN_STATUSES = {"pending", "running", "completed", "partial", "failed"}
_FINAL_SCAN_STATUSES = {"completed", "partial", "failed"}

M = TypeVar("M", bound=BaseModel)


class PersistenceError(ValueError):
    """A write that would break a storage rule, or a lookup of a missing row."""


def create_project(session: Session, project_id: str, name: str, created_at: datetime) -> None:
    if session.get(Project, project_id) is not None:
        raise PersistenceError(f"project {project_id!r} already exists")
    session.add(Project(id=project_id, name=name, created_at=created_at))
    session.flush()


def _dump(model: BaseModel, **kwargs: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", **kwargs)


class ProjectRepository:
    def __init__(self, session: Session, project_id: str) -> None:
        if session.get(Project, project_id) is None:
            raise PersistenceError(f"no project {project_id!r}")
        self.session = session
        self.project_id = project_id

    # --- scans and snapshots -------------------------------------------------------

    def add_scan(self, scan_id: str, started_at: datetime, sources: Sequence[str]) -> None:
        self.session.add(
            Scan(
                id=scan_id,
                project_id=self.project_id,
                status="running",
                started_at=started_at,
                completed_at=None,
                sources=list(sources),
                errors=[],
            )
        )
        self.session.flush()

    def finish_scan(
        self,
        scan_id: str,
        status: ScanStatus,
        completed_at: datetime,
        *,
        resource_count: int,
        edge_count: int,
        errors: Sequence[str] = (),
    ) -> None:
        if status not in _FINAL_SCAN_STATUSES:
            raise PersistenceError(f"a finished scan is completed, partial or failed, not {status}")
        scan = self._scan(scan_id)
        if scan.status in _FINAL_SCAN_STATUSES:
            raise PersistenceError(f"scan {scan_id!r} is already finished")
        scan.status = status
        scan.completed_at = completed_at
        scan.resource_count = resource_count
        scan.edge_count = edge_count
        scan.errors = list(errors)
        self.session.flush()

    def scan_status(self, scan_id: str) -> str:
        return self._scan(scan_id).status

    def create_snapshot(
        self,
        snapshot_id: str,
        kind: SnapshotKind,
        created_at: datetime,
        *,
        scan_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if scan_id is not None:
            self._scan(scan_id)
        self.session.add(
            Snapshot(
                id=snapshot_id,
                project_id=self.project_id,
                kind=kind,
                scan_id=scan_id,
                created_at=created_at,
                published_at=None,
                details=details or {},
            )
        )
        self.session.flush()

    def publish_snapshot(self, snapshot_id: str, published_at: datetime) -> None:
        snapshot = self._open_snapshot(snapshot_id)
        snapshot.published_at = published_at
        self.session.flush()

    def is_published(self, snapshot_id: str) -> bool:
        return self._snapshot(snapshot_id).published_at is not None

    def snapshot_ids(self) -> list[str]:
        """Oldest first. Previous snapshots are kept (spec §76)."""
        rows = self.session.scalars(
            select(Snapshot.id)
            .where(Snapshot.project_id == self.project_id)
            .order_by(Snapshot.created_at, Snapshot.id)
        )
        return list(rows)

    def save_coverage(self, scan_id: str, records: Iterable[ScanCoverage]) -> None:
        self._scan(scan_id)
        for record in records:
            self.session.add(
                ScanCoverageRow(
                    project_id=self.project_id,
                    scan_id=scan_id,
                    coverage_id=record.id,
                    account_id=record.account_id,
                    region=record.region,
                    service=record.service,
                    status=record.status.value,
                    payload=_dump(record),
                )
            )
        self.session.flush()

    def coverage(self, scan_id: str) -> list[ScanCoverage]:
        rows = self.session.scalars(
            select(ScanCoverageRow)
            .where(ScanCoverageRow.project_id == self.project_id)
            .where(ScanCoverageRow.scan_id == scan_id)
            .order_by(ScanCoverageRow.coverage_id)
        )
        return [ScanCoverage.model_validate(row.payload) for row in rows]

    # --- snapshot contents ---------------------------------------------------------

    def save_resources(self, snapshot_id: str, nodes: Iterable[ResourceNode]) -> None:
        self._open_snapshot(snapshot_id)
        for node in nodes:
            identity = self.session.scalar(
                select(ResourceRow)
                .where(ResourceRow.project_id == self.project_id)
                .where(ResourceRow.resource_id == node.id)
            )
            if identity is None:
                self.session.add(
                    ResourceRow(
                        project_id=self.project_id,
                        resource_id=node.id,
                        provider=node.provider,
                        service=node.service,
                        resource_type=node.resource_type,
                        first_seen_at=node.discovered_at,
                    )
                )
            self.session.add(
                ResourceVersionRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    resource_id=node.id,
                    account_id=node.account_id,
                    region=node.region,
                    planned=node.planned,
                    payload=_dump(node),
                )
            )
        self.session.flush()

    def resources(self, snapshot_id: str) -> list[ResourceNode]:
        return self._load(
            ResourceVersionRow, ResourceNode, snapshot_id, ResourceVersionRow.resource_id
        )

    def resource_history(self, resource_id: str) -> list[tuple[str, ResourceNode]]:
        """Every stored version of one resource, as (snapshot_id, node), oldest first."""
        rows = self.session.execute(
            select(ResourceVersionRow)
            .join(Snapshot, Snapshot.id == ResourceVersionRow.snapshot_id)
            .where(ResourceVersionRow.project_id == self.project_id)
            .where(ResourceVersionRow.resource_id == resource_id)
            .order_by(Snapshot.created_at, Snapshot.id)
        ).scalars()
        return [(row.snapshot_id, ResourceNode.model_validate(row.payload)) for row in rows]

    def save_edges(self, snapshot_id: str, edges: Iterable[DependencyEdge]) -> None:
        self._open_snapshot(snapshot_id)
        for edge in edges:
            row = EdgeRow(
                project_id=self.project_id,
                snapshot_id=snapshot_id,
                edge_id=edge.id,
                from_resource_id=edge.from_resource_id,
                to_resource_id=edge.to_resource_id,
                relationship_type=edge.relationship_type.value,
                review_state=edge.review_state.value,
                payload=_dump(edge, exclude={"evidence"}),
            )
            self.session.add(row)
            self.session.flush()
            for position, item in enumerate(edge.evidence):
                evidence_row = self._store_evidence(snapshot_id, item)
                self.session.add(
                    EdgeEvidenceRow(
                        edge_row_id=row.row_id, position=position, evidence_row_id=evidence_row
                    )
                )
        self.session.flush()

    def edges(self, snapshot_id: str) -> list[DependencyEdge]:
        rows = self.session.scalars(
            select(EdgeRow)
            .where(EdgeRow.project_id == self.project_id)
            .where(EdgeRow.snapshot_id == snapshot_id)
            .order_by(EdgeRow.edge_id)
        ).all()
        links = self.session.execute(
            select(EdgeEvidenceRow.edge_row_id, EvidenceRow.payload)
            .join(EvidenceRow, EvidenceRow.row_id == EdgeEvidenceRow.evidence_row_id)
            .where(EdgeEvidenceRow.edge_row_id.in_([row.row_id for row in rows]))
            .order_by(EdgeEvidenceRow.edge_row_id, EdgeEvidenceRow.position)
        ).all()
        evidence: dict[int, list[dict[str, Any]]] = {}
        for edge_row_id, payload in links:
            evidence.setdefault(edge_row_id, []).append(payload)
        return [
            DependencyEdge.model_validate(row.payload | {"evidence": evidence.get(row.row_id, [])})
            for row in rows
        ]

    def evidence(self, snapshot_id: str) -> list[Evidence]:
        return self._load(EvidenceRow, Evidence, snapshot_id, EvidenceRow.evidence_id)

    def save_groups(self, snapshot_id: str, groups: Iterable[DependencyGroup]) -> None:
        self._open_snapshot(snapshot_id)
        for group in groups:
            self.session.add(
                DependencyGroupRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    group_id=group.id,
                    dependent_resource_id=group.dependent_resource_id,
                    mode=group.mode.value,
                    payload=_dump(group),
                )
            )
        self.session.flush()

    def groups(self, snapshot_id: str) -> list[DependencyGroup]:
        return self._load(
            DependencyGroupRow, DependencyGroup, snapshot_id, DependencyGroupRow.group_id
        )

    def save_observations(self, snapshot_id: str, items: Iterable[ResolvedObservation]) -> None:
        self._open_snapshot(snapshot_id)
        for item in items:
            self.session.add(
                ObservationRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    observation_id=item.id,
                    source_type=item.source_type,
                    attribution=item.attribution.value,
                    payload=_dump(item),
                )
            )
        self.session.flush()

    def observations(self, snapshot_id: str) -> list[ResolvedObservation]:
        return self._load(
            ObservationRow, ResolvedObservation, snapshot_id, ObservationRow.observation_id
        )

    def save_mechanisms(self, snapshot_id: str, items: Iterable[RecoveryMechanism]) -> None:
        self._open_snapshot(snapshot_id)
        for item in items:
            self.session.add(
                RecoveryMechanismRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    mechanism_id=item.id,
                    primary_resource_id=item.primary_resource_id,
                    kind=item.kind.value,
                    payload=_dump(item),
                )
            )
        self.session.flush()

    def mechanisms(self, snapshot_id: str) -> list[RecoveryMechanism]:
        return self._load(
            RecoveryMechanismRow, RecoveryMechanism, snapshot_id, RecoveryMechanismRow.mechanism_id
        )

    def save_stacks(
        self,
        snapshot_id: str,
        stacks: Iterable[Stack],
        members: Iterable[StackResource] = (),
        services: Iterable[StackService] = (),
    ) -> None:
        self._open_snapshot(snapshot_id)
        for stack in stacks:
            self.session.add(
                StackRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    stack_id=stack.id,
                    name=stack.name,
                    payload=_dump(stack),
                )
            )
        for member in members:
            self.session.add(
                StackResourceRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    stack_id=member.stack_id,
                    resource_id=member.resource_id,
                    rto_scope=member.rto_scope.value,
                    scope_source=member.scope_source.value,
                )
            )
        for service in services:
            self.session.add(
                StackServiceRow(
                    project_id=self.project_id,
                    snapshot_id=snapshot_id,
                    service_id=service.id,
                    stack_id=service.stack_id,
                    payload=_dump(service),
                )
            )
        self.session.flush()

    def stacks(self, snapshot_id: str) -> list[Stack]:
        return self._load(StackRow, Stack, snapshot_id, StackRow.stack_id)

    def stack_resources(self, snapshot_id: str, stack_id: str) -> list[StackResource]:
        rows = self.session.scalars(
            select(StackResourceRow)
            .where(StackResourceRow.project_id == self.project_id)
            .where(StackResourceRow.snapshot_id == snapshot_id)
            .where(StackResourceRow.stack_id == stack_id)
            .order_by(StackResourceRow.resource_id)
        )
        return [
            StackResource.model_validate(
                {
                    "stack_id": row.stack_id,
                    "resource_id": row.resource_id,
                    "rto_scope": row.rto_scope,
                    "scope_source": row.scope_source,
                }
            )
            for row in rows
        ]

    def stack_services(self, snapshot_id: str) -> list[StackService]:
        return self._load(StackServiceRow, StackService, snapshot_id, StackServiceRow.service_id)

    # --- overrides and evaluation inputs (per project) ------------------------------

    def add_override(self, override: GraphOverride) -> None:
        if override.project_id != self.project_id:
            raise PersistenceError("override belongs to another project")
        self.session.add(
            GraphOverrideRow(
                project_id=self.project_id,
                override_id=override.id,
                kind=override.kind.value,
                target=override.target,
                status=override.status.value,
                created_at=override.created_at,
                payload=_dump(override),
            )
        )
        self.session.flush()

    def set_override_status(self, override_id: str, status: OverrideStatus) -> GraphOverride:
        """Change only the status (e.g. orphaned after a rescan, spec §23)."""
        row = self.session.scalar(
            select(GraphOverrideRow)
            .where(GraphOverrideRow.project_id == self.project_id)
            .where(GraphOverrideRow.override_id == override_id)
        )
        if row is None:
            raise PersistenceError(f"no override {override_id!r}")
        updated = GraphOverride.model_validate(row.payload).model_copy(update={"status": status})
        row.status = status.value
        row.payload = _dump(updated)
        self.session.flush()
        return updated

    def overrides(self, status: OverrideStatus | None = None) -> list[GraphOverride]:
        query = select(GraphOverrideRow).where(GraphOverrideRow.project_id == self.project_id)
        if status is not None:
            query = query.where(GraphOverrideRow.status == status.value)
        rows = self.session.scalars(
            query.order_by(GraphOverrideRow.created_at, GraphOverrideRow.override_id)
        )
        return [GraphOverride.model_validate(row.payload) for row in rows]

    def add_evaluation_input(self, manifest: EvaluationInput) -> None:
        """Manifests are immutable (spec §56.3): there is no update."""
        self.session.add(
            EvaluationInputRow(
                project_id=self.project_id,
                evaluation_id=manifest.id,
                stack_id=manifest.stack_id,
                evaluated_at=manifest.evaluated_at,
                payload=_dump(manifest),
            )
        )
        self.session.flush()

    def evaluation_input(self, evaluation_id: str) -> EvaluationInput:
        row = self.session.scalar(
            select(EvaluationInputRow)
            .where(EvaluationInputRow.project_id == self.project_id)
            .where(EvaluationInputRow.evaluation_id == evaluation_id)
        )
        if row is None:
            raise PersistenceError(f"no evaluation input {evaluation_id!r}")
        return EvaluationInput.model_validate(row.payload)

    # --- helpers -------------------------------------------------------------------

    def _scan(self, scan_id: str) -> Scan:
        scan = self.session.get(Scan, scan_id)
        if scan is None or scan.project_id != self.project_id:
            raise PersistenceError(f"no scan {scan_id!r} in this project")
        return scan

    def _snapshot(self, snapshot_id: str) -> Snapshot:
        snapshot = self.session.get(Snapshot, snapshot_id)
        if snapshot is None or snapshot.project_id != self.project_id:
            raise PersistenceError(f"no snapshot {snapshot_id!r} in this project")
        return snapshot

    def _open_snapshot(self, snapshot_id: str) -> Snapshot:
        snapshot = self._snapshot(snapshot_id)
        if snapshot.published_at is not None:
            raise PersistenceError(f"snapshot {snapshot_id!r} is published and can't change")
        return snapshot

    def _store_evidence(self, snapshot_id: str, item: Evidence) -> int:
        # Evidence is stored once per snapshot. The same ID must mean the same fact;
        # a different payload under one ID is a bug upstream, not something to merge.
        payload = _dump(item)
        existing = self.session.scalar(
            select(EvidenceRow)
            .where(EvidenceRow.project_id == self.project_id)
            .where(EvidenceRow.snapshot_id == snapshot_id)
            .where(EvidenceRow.evidence_id == item.id)
        )
        if existing is not None:
            if existing.payload != payload:
                raise PersistenceError(f"evidence {item.id!r} already stored with other content")
            return existing.row_id
        row = EvidenceRow(
            project_id=self.project_id,
            snapshot_id=snapshot_id,
            evidence_id=item.id,
            source_type=item.source_type.value,
            basis=item.basis.value if item.basis else None,
            resource_id=item.resource_id,
            payload=payload,
        )
        self.session.add(row)
        self.session.flush()
        return row.row_id

    def _load(self, table: Any, model: type[M], snapshot_id: str, order: Any) -> list[M]:
        # `table` is any snapshot-scoped row class (they all have these columns).
        rows = self.session.scalars(
            select(table)
            .where(table.project_id == self.project_id)
            .where(table.snapshot_id == snapshot_id)
            .order_by(order)
        )
        return [model.model_validate(row.payload) for row in rows]
