"""Run Alembic migrations from code (spec §71.1: tested on SQLite and PostgreSQL)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config(url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    if url is not None:
        config.set_main_option("sqlalchemy.url", url)
    return config


def upgrade(engine: Engine, revision: str = "head") -> None:
    """Bring the database at `engine` up to `revision`."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def downgrade(engine: Engine, revision: str) -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, revision)
