"""Schema, migrations and dialect compatibility (spec §71.1, §75)."""

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from perpetual.persistence import Base, default_database_path, downgrade, make_engine, upgrade
from perpetual.persistence.migrate import alembic_config

EXPECTED_TABLES = {
    "projects",
    "scans",
    "snapshots",
    "scan_coverage",
    "resources",
    "resource_versions",
    "evidence",
    "edges",
    "edge_evidence",
    "dependency_groups",
    "observations",
    "recovery_mechanisms",
    "stacks",
    "stack_resources",
    "stack_services",
    "graph_overrides",
    "evaluation_inputs",
}


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return make_engine(f"sqlite:///{tmp_path / 'test.db'}")


def test_metadata_has_the_planned_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_table_is_scoped_by_project() -> None:
    # Link and root tables are scoped through their parents.
    for name, table in Base.metadata.tables.items():
        if name in {"projects", "edge_evidence"}:
            continue
        assert "project_id" in table.columns, name


def test_migration_matches_the_models(engine: Engine) -> None:
    upgrade(engine)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_downgrade_removes_every_table(engine: Engine) -> None:
    upgrade(engine)
    downgrade(engine, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}


@pytest.mark.parametrize("dialect_name", ["sqlite", "postgresql"])
def test_models_compile_on_both_dialects(dialect_name: str) -> None:
    dialect = make_url(f"{dialect_name}://").get_dialect()()
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=dialect))
        for index in table.indexes:
            assert str(CreateIndex(index).compile(dialect=dialect))


def test_identifiers_fit_postgresql() -> None:
    for table in Base.metadata.tables.values():
        names = [table.name]
        names += [str(c.name) for c in table.constraints if c.name]
        names += [str(i.name) for i in table.indexes if i.name]
        for name in names:
            assert len(name) <= 63, name


def test_migration_renders_as_postgresql_sql() -> None:
    # Offline mode compiles every migration step for PostgreSQL without a server.
    buffer = io.StringIO()
    config = alembic_config("postgresql://localhost/perpetual")
    config.output_buffer = buffer
    command.upgrade(config, "head", sql=True)
    sql = buffer.getvalue()
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table} " in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql


def test_default_database_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_database_path() == tmp_path / "perpetual" / "perpetual.db"
    monkeypatch.delenv("XDG_DATA_HOME")
    assert default_database_path() == Path.home() / ".local/share/perpetual/perpetual.db"
