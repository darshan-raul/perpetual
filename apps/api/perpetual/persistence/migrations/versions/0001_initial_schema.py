"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_table(
        "evaluation_inputs",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("evaluation_id", sa.String(length=512), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_evaluation_inputs_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_evaluation_inputs")),
        sa.UniqueConstraint(
            "project_id",
            "evaluation_id",
            name=op.f("uq_evaluation_inputs_project_id_evaluation_id"),
        ),
    )
    with op.batch_alter_table("evaluation_inputs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_evaluation_inputs_project_id"), ["project_id"], unique=False
        )

    op.create_table(
        "graph_overrides",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("override_id", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_graph_overrides_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_graph_overrides")),
        sa.UniqueConstraint(
            "project_id", "override_id", name=op.f("uq_graph_overrides_project_id_override_id")
        ),
    )
    with op.batch_alter_table("graph_overrides", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_graph_overrides_project_id"), ["project_id"], unique=False
        )

    op.create_table(
        "resources",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_resources_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_resources")),
        sa.UniqueConstraint(
            "project_id", "resource_id", name=op.f("uq_resources_project_id_resource_id")
        ),
    )
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_resources_project_id"), ["project_id"], unique=False)

    op.create_table(
        "scans",
        sa.Column("id", sa.String(length=512), nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("resource_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_scans_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scans")),
    )
    with op.batch_alter_table("scans", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scans_project_id"), ["project_id"], unique=False)

    op.create_table(
        "scan_coverage",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("scan_id", sa.String(length=512), nullable=False),
        sa.Column("coverage_id", sa.String(length=512), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_scan_coverage_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"], ["scans.id"], name=op.f("fk_scan_coverage_scan_id_scans")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_scan_coverage")),
        sa.UniqueConstraint(
            "project_id", "coverage_id", name=op.f("uq_scan_coverage_project_id_coverage_id")
        ),
    )
    with op.batch_alter_table("scan_coverage", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_scan_coverage_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_scan_coverage_scan_id"), ["scan_id"], unique=False)

    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(length=512), nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("scan_id", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_snapshots_project_id_projects")
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name=op.f("fk_snapshots_scan_id_scans")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_snapshots")),
    )
    with op.batch_alter_table("snapshots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_snapshots_project_id"), ["project_id"], unique=False)

    op.create_table(
        "dependency_groups",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("group_id", sa.String(length=512), nullable=False),
        sa.Column("dependent_resource_id", sa.String(length=512), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_dependency_groups_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_dependency_groups_snapshot_id_snapshots"),
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_dependency_groups")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "group_id",
            name=op.f("uq_dependency_groups_project_id_snapshot_id_group_id"),
        ),
    )
    op.create_table(
        "edges",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("edge_id", sa.String(length=512), nullable=False),
        sa.Column("from_resource_id", sa.String(length=512), nullable=False),
        sa.Column("to_resource_id", sa.String(length=512), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("review_state", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_edges_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_edges_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_edges")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "edge_id",
            name=op.f("uq_edges_project_id_snapshot_id_edge_id"),
        ),
    )
    with op.batch_alter_table("edges", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_edges_project_id_snapshot_id_from_resource_id"),
            ["project_id", "snapshot_id", "from_resource_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_edges_project_id_snapshot_id_to_resource_id"),
            ["project_id", "snapshot_id", "to_resource_id"],
            unique=False,
        )

    op.create_table(
        "evidence",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("evidence_id", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("basis", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=512), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_evidence_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_evidence_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_evidence")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "evidence_id",
            name=op.f("uq_evidence_project_id_snapshot_id_evidence_id"),
        ),
    )
    op.create_table(
        "observations",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("observation_id", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("attribution", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_observations_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_observations_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_observations")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "observation_id",
            name=op.f("uq_observations_project_id_snapshot_id_observation_id"),
        ),
    )
    op.create_table(
        "recovery_mechanisms",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("mechanism_id", sa.String(length=512), nullable=False),
        sa.Column("primary_resource_id", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_recovery_mechanisms_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_recovery_mechanisms_snapshot_id_snapshots"),
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_recovery_mechanisms")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "mechanism_id",
            name=op.f("uq_recovery_mechanisms_project_id_snapshot_id_mechanism_id"),
        ),
    )
    with op.batch_alter_table("recovery_mechanisms", schema=None) as batch_op:
        batch_op.create_index(
            "ix_recovery_mechanisms_primary",
            ["project_id", "snapshot_id", "primary_resource_id"],
            unique=False,
        )

    op.create_table(
        "resource_versions",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("planned", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_resource_versions_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_resource_versions_snapshot_id_snapshots"),
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_resource_versions")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "resource_id",
            name=op.f("uq_resource_versions_project_id_snapshot_id_resource_id"),
        ),
    )
    with op.batch_alter_table("resource_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_resource_versions_project_id_resource_id"),
            ["project_id", "resource_id"],
            unique=False,
        )

    op.create_table(
        "stack_resources",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("rto_scope", sa.String(length=64), nullable=False),
        sa.Column("scope_source", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_stack_resources_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_stack_resources_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_stack_resources")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "stack_id",
            "resource_id",
            name=op.f("uq_stack_resources_project_id_snapshot_id_stack_id_resource_id"),
        ),
    )
    op.create_table(
        "stack_services",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("service_id", sa.String(length=512), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_stack_services_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_stack_services_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_stack_services")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "service_id",
            name=op.f("uq_stack_services_project_id_snapshot_id_service_id"),
        ),
    )
    op.create_table(
        "stacks",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_stacks_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_stacks_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_stacks")),
        sa.UniqueConstraint(
            "project_id",
            "snapshot_id",
            "stack_id",
            name=op.f("uq_stacks_project_id_snapshot_id_stack_id"),
        ),
    )
    op.create_table(
        "edge_evidence",
        sa.Column("edge_row_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("evidence_row_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edge_row_id"],
            ["edges.row_id"],
            name=op.f("fk_edge_evidence_edge_row_id_edges"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_row_id"],
            ["evidence.row_id"],
            name=op.f("fk_edge_evidence_evidence_row_id_evidence"),
        ),
        sa.PrimaryKeyConstraint("edge_row_id", "position", name=op.f("pk_edge_evidence")),
    )
    with op.batch_alter_table("edge_evidence", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_edge_evidence_evidence_row_id"), ["evidence_row_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("edge_evidence", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_edge_evidence_evidence_row_id"))

    op.drop_table("edge_evidence")
    op.drop_table("stacks")
    op.drop_table("stack_services")
    op.drop_table("stack_resources")
    with op.batch_alter_table("resource_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resource_versions_project_id_resource_id"))

    op.drop_table("resource_versions")
    with op.batch_alter_table("recovery_mechanisms", schema=None) as batch_op:
        batch_op.drop_index("ix_recovery_mechanisms_primary")

    op.drop_table("recovery_mechanisms")
    op.drop_table("observations")
    op.drop_table("evidence")
    with op.batch_alter_table("edges", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_edges_project_id_snapshot_id_to_resource_id"))
        batch_op.drop_index(batch_op.f("ix_edges_project_id_snapshot_id_from_resource_id"))

    op.drop_table("edges")
    op.drop_table("dependency_groups")
    with op.batch_alter_table("snapshots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_snapshots_project_id"))

    op.drop_table("snapshots")
    with op.batch_alter_table("scan_coverage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scan_coverage_scan_id"))
        batch_op.drop_index(batch_op.f("ix_scan_coverage_project_id"))

    op.drop_table("scan_coverage")
    with op.batch_alter_table("scans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scans_project_id"))

    op.drop_table("scans")
    with op.batch_alter_table("resources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resources_project_id"))

    op.drop_table("resources")
    with op.batch_alter_table("graph_overrides", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_graph_overrides_project_id"))

    op.drop_table("graph_overrides")
    with op.batch_alter_table("evaluation_inputs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_evaluation_inputs_project_id"))

    op.drop_table("evaluation_inputs")
    op.drop_table("projects")
