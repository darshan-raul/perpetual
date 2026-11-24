"""add recovery_requirements, simulations and recovery_plans (P1-15)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recovery_requirements",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("requirement_id", sa.String(length=512), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("failure_scope", sa.String(length=64), nullable=False),
        sa.Column("target_region", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_recovery_requirements_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_recovery_requirements")),
        sa.UniqueConstraint(
            "project_id",
            "requirement_id",
            "revision",
            name=op.f("uq_recovery_requirements_project_id_requirement_id_revision"),
        ),
    )
    op.create_index(
        op.f("ix_recovery_requirements_project_id"),
        "recovery_requirements",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recovery_requirements_stack_id"),
        "recovery_requirements",
        ["stack_id"],
        unique=False,
    )

    op.create_table(
        "simulations",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("simulation_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("scenario_kind", sa.String(length=64), nullable=False),
        sa.Column("stack_state", sa.String(length=64), nullable=False),
        sa.Column("readiness", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_simulations_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_simulations_snapshot_id_snapshots"),
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_simulations")),
        sa.UniqueConstraint(
            "project_id",
            "simulation_id",
            name=op.f("uq_simulations_project_id_simulation_id"),
        ),
    )
    op.create_index(op.f("ix_simulations_project_id"), "simulations", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_simulations_snapshot_id"), "simulations", ["snapshot_id"], unique=False
    )
    op.create_index(op.f("ix_simulations_stack_id"), "simulations", ["stack_id"], unique=False)

    op.create_table(
        "recovery_plans",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=512), nullable=False),
        sa.Column("plan_id", sa.String(length=512), nullable=False),
        sa.Column("snapshot_id", sa.String(length=512), nullable=False),
        sa.Column("stack_id", sa.String(length=512), nullable=False),
        sa.Column("requirement_id", sa.String(length=512), nullable=False),
        sa.Column("requirement_revision", sa.Integer(), nullable=False),
        sa.Column("rto_comparison", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_recovery_plans_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_recovery_plans_snapshot_id_snapshots"),
        ),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_recovery_plans")),
        sa.UniqueConstraint(
            "project_id",
            "plan_id",
            name=op.f("uq_recovery_plans_project_id_plan_id"),
        ),
    )
    op.create_index(
        op.f("ix_recovery_plans_project_id"), "recovery_plans", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_recovery_plans_snapshot_id"), "recovery_plans", ["snapshot_id"], unique=False
    )
    op.create_index(
        op.f("ix_recovery_plans_stack_id"), "recovery_plans", ["stack_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_recovery_plans_stack_id"), table_name="recovery_plans")
    op.drop_index(op.f("ix_recovery_plans_snapshot_id"), table_name="recovery_plans")
    op.drop_index(op.f("ix_recovery_plans_project_id"), table_name="recovery_plans")
    op.drop_table("recovery_plans")

    op.drop_index(op.f("ix_simulations_stack_id"), table_name="simulations")
    op.drop_index(op.f("ix_simulations_snapshot_id"), table_name="simulations")
    op.drop_index(op.f("ix_simulations_project_id"), table_name="simulations")
    op.drop_table("simulations")

    op.drop_index(op.f("ix_recovery_requirements_stack_id"), table_name="recovery_requirements")
    op.drop_index(op.f("ix_recovery_requirements_project_id"), table_name="recovery_requirements")
    op.drop_table("recovery_requirements")
