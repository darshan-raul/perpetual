"""SQLAlchemy tables (spec §75).

Each row has a few typed lookup columns (IDs, project, snapshot, type, endpoints,
status) and a `payload` column with the full domain model as JSON. Queries filter
on the lookup columns; the domain model is rebuilt from the payload and validated
again on load, so the database can't hand the engine data the models would refuse.

Rules that span the schema:

- Every row carries `project_id` (spec §71.1), and repositories always filter on it.
- Discovered graph data belongs to a snapshot. A published snapshot is immutable;
  a new scan makes a new snapshot and older ones are kept (spec §15.4, §76).
- User edits are `graph_overrides`, per project, applied on top of each snapshot.
  Discovered rows are never changed to reflect an edit (spec §23).
- Evidence is stored once and linked to edges through `edge_evidence`.
- PostgreSQL-compatible: only portable types; datetimes are stored in UTC.
"""

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names, so migrations can refer to them on every dialect.
NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

ID = String(512)
"""Wide enough for canonical resource IDs, which embed names and Terraform addresses."""
SHORT = String(64)


class UtcDateTime(TypeDecorator[datetime]):
    """Aware datetimes in, aware UTC datetimes out, on every dialect.

    SQLite has no time zones and would return naive values; the domain models
    reject naive datetimes.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not stored")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSON,
        list[Any]: JSON,
        datetime: UtcDateTime,
    }


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime]


class Scan(Base):
    """One collection run (spec §76). Previous scans are kept for drift (§77)."""

    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(SHORT)
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    sources: Mapped[list[Any]]
    errors: Mapped[list[Any]]
    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)


class Snapshot(Base):
    """An immutable set of resources, edges and observations: live (from a scan)
    or planned (from a saved Terraform plan, spec §15.4)."""

    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(SHORT)
    scan_id: Mapped[str | None] = mapped_column(ForeignKey("scans.id"))
    created_at: Mapped[datetime]
    published_at: Mapped[datetime | None]
    """Set once, when the snapshot is complete. After that its rows never change."""
    details: Mapped[dict[str, Any]]
    """e.g. for a planned snapshot: base evaluation, plan hash, root mapping."""


def _snapshot_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"])


class ScanCoverageRow(Base):
    __tablename__ = "scan_coverage"
    __table_args__ = (UniqueConstraint("project_id", "coverage_id"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), index=True)
    coverage_id: Mapped[str] = mapped_column(ID)
    account_id: Mapped[str] = mapped_column(SHORT)
    region: Mapped[str] = mapped_column(SHORT)
    service: Mapped[str] = mapped_column(SHORT)
    status: Mapped[str] = mapped_column(SHORT)
    payload: Mapped[dict[str, Any]]


class ResourceRow(Base):
    """A resource's identity across snapshots: one row per project and resource ID."""

    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("project_id", "resource_id"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    resource_id: Mapped[str] = mapped_column(ID)
    provider: Mapped[str] = mapped_column(SHORT)
    service: Mapped[str] = mapped_column(SHORT)
    resource_type: Mapped[str] = mapped_column(SHORT)
    first_seen_at: Mapped[datetime]


class ResourceVersionRow(Base):
    """A resource as one snapshot saw it."""

    __tablename__ = "resource_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_id", "resource_id"),
        Index(None, "project_id", "resource_id"),
        _snapshot_fk(),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    resource_id: Mapped[str] = mapped_column(ID)
    account_id: Mapped[str | None] = mapped_column(SHORT)
    region: Mapped[str | None] = mapped_column(SHORT)
    planned: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]]


class EvidenceRow(Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("project_id", "snapshot_id", "evidence_id"), _snapshot_fk())

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    evidence_id: Mapped[str] = mapped_column(ID)
    source_type: Mapped[str] = mapped_column(SHORT)
    basis: Mapped[str | None] = mapped_column(SHORT)
    resource_id: Mapped[str | None] = mapped_column(ID)
    payload: Mapped[dict[str, Any]]


class EdgeRow(Base):
    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_id", "edge_id"),
        Index(None, "project_id", "snapshot_id", "from_resource_id"),
        Index(None, "project_id", "snapshot_id", "to_resource_id"),
        _snapshot_fk(),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    edge_id: Mapped[str] = mapped_column(ID)
    from_resource_id: Mapped[str] = mapped_column(ID)
    to_resource_id: Mapped[str] = mapped_column(ID)
    relationship_type: Mapped[str] = mapped_column(SHORT)
    review_state: Mapped[str] = mapped_column(SHORT)
    payload: Mapped[dict[str, Any]]
    """The edge without its evidence, which lives in `evidence`."""


class EdgeEvidenceRow(Base):
    __tablename__ = "edge_evidence"

    edge_row_id: Mapped[int] = mapped_column(
        ForeignKey("edges.row_id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Order of the evidence on the edge, so a reload is identical."""
    evidence_row_id: Mapped[int] = mapped_column(ForeignKey("evidence.row_id"), index=True)


class DependencyGroupRow(Base):
    __tablename__ = "dependency_groups"
    __table_args__ = (UniqueConstraint("project_id", "snapshot_id", "group_id"), _snapshot_fk())

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    group_id: Mapped[str] = mapped_column(ID)
    dependent_resource_id: Mapped[str] = mapped_column(ID)
    mode: Mapped[str] = mapped_column(SHORT)
    payload: Mapped[dict[str, Any]]


class ObservationRow(Base):
    """Resolved CloudTrail and flow-log aggregates (spec §14.1). Never raw events."""

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_id", "observation_id"),
        _snapshot_fk(),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    observation_id: Mapped[str] = mapped_column(ID)
    source_type: Mapped[str] = mapped_column(SHORT)
    attribution: Mapped[str] = mapped_column(SHORT)
    payload: Mapped[dict[str, Any]]


class RecoveryMechanismRow(Base):
    __tablename__ = "recovery_mechanisms"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_id", "mechanism_id"),
        # Named explicitly: the generated name exceeds PostgreSQL's 63-character limit.
        Index("ix_recovery_mechanisms_primary", "project_id", "snapshot_id", "primary_resource_id"),
        _snapshot_fk(),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    mechanism_id: Mapped[str] = mapped_column(ID)
    primary_resource_id: Mapped[str] = mapped_column(ID)
    kind: Mapped[str] = mapped_column(SHORT)
    payload: Mapped[dict[str, Any]]


class StackRow(Base):
    __tablename__ = "stacks"
    __table_args__ = (UniqueConstraint("project_id", "snapshot_id", "stack_id"), _snapshot_fk())

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    stack_id: Mapped[str] = mapped_column(ID)
    name: Mapped[str] = mapped_column(String(256))
    payload: Mapped[dict[str, Any]]


class StackResourceRow(Base):
    __tablename__ = "stack_resources"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_id", "stack_id", "resource_id"),
        _snapshot_fk(),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    stack_id: Mapped[str] = mapped_column(ID)
    resource_id: Mapped[str] = mapped_column(ID)
    rto_scope: Mapped[str] = mapped_column(SHORT)
    scope_source: Mapped[str] = mapped_column(SHORT)


class StackServiceRow(Base):
    __tablename__ = "stack_services"
    __table_args__ = (UniqueConstraint("project_id", "snapshot_id", "service_id"), _snapshot_fk())

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    snapshot_id: Mapped[str] = mapped_column(ID)
    service_id: Mapped[str] = mapped_column(ID)
    stack_id: Mapped[str] = mapped_column(ID)
    payload: Mapped[dict[str, Any]]


class GraphOverrideRow(Base):
    """A user edit (spec §23). Per project, applied on top of every snapshot."""

    __tablename__ = "graph_overrides"
    __table_args__ = (UniqueConstraint("project_id", "override_id"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    override_id: Mapped[str] = mapped_column(ID)
    kind: Mapped[str] = mapped_column(SHORT)
    target: Mapped[str] = mapped_column(ID)
    status: Mapped[str] = mapped_column(SHORT)
    created_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class EvaluationInputRow(Base):
    """Immutable evaluation manifests (spec §56.3). Never updated, only added."""

    __tablename__ = "evaluation_inputs"
    __table_args__ = (UniqueConstraint("project_id", "evaluation_id"),)

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    evaluation_id: Mapped[str] = mapped_column(ID)
    stack_id: Mapped[str] = mapped_column(ID)
    evaluated_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]
