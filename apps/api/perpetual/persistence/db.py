"""Database location, engine and sessions (spec §71.1).

One SQLite file in the user's data directory by default. The schema stays
PostgreSQL-compatible, so a hosted version can swap the URL.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def default_database_path() -> Path:
    """`$XDG_DATA_HOME/perpetual/perpetual.db`, or `~/.local/share/perpetual/perpetual.db`."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "perpetual" / "perpetual.db"


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path}"


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked, per connection.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection: Any, _record: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """A session that commits on success and rolls back on any error."""
    with factory() as session, session.begin():
        yield session
