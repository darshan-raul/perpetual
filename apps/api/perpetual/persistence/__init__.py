"""SQLAlchemy tables, a project-scoped repository and Alembic migrations (spec §71.1, §75)."""

from perpetual.persistence.db import (
    default_database_path,
    make_engine,
    make_session_factory,
    sqlite_url,
    transaction,
)
from perpetual.persistence.migrate import downgrade, upgrade
from perpetual.persistence.repository import (
    PersistenceError,
    ProjectRepository,
    ScanStatus,
    SnapshotKind,
    create_project,
)
from perpetual.persistence.tables import Base

__all__ = [
    "Base",
    "PersistenceError",
    "ProjectRepository",
    "ScanStatus",
    "SnapshotKind",
    "create_project",
    "default_database_path",
    "downgrade",
    "make_engine",
    "make_session_factory",
    "sqlite_url",
    "transaction",
    "upgrade",
]
