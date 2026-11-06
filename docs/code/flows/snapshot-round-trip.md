# Flow: save and reload a snapshot

This manual library example connects fixtures and persistence. No CLI command currently runs it. It uses an in-memory SQLite database, writes no database file, and calls no AWS services.

## Run from the repository root

```bash
mise exec -- uv run python - <<'PY'
from pathlib import Path

from perpetual.fixtures import load_fixture
from perpetual.persistence import (
    ProjectRepository,
    create_project,
    make_engine,
    make_session_factory,
    transaction,
    upgrade,
)

fixture = load_fixture(Path("fixtures/graphs/minimal.yaml"))
engine = make_engine("sqlite:///:memory:")
upgrade(engine)
factory = make_session_factory(engine)

with transaction(factory) as session:
    create_project(session, "demo", "Wiki example", fixture.captured_at)
    repository = ProjectRepository(session, "demo")
    repository.create_snapshot("snapshot-1", "live", fixture.captured_at)
    repository.save_resources("snapshot-1", fixture.resources)
    repository.save_edges("snapshot-1", fixture.edges)
    repository.publish_snapshot("snapshot-1", fixture.captured_at)

with transaction(factory) as session:
    repository = ProjectRepository(session, "demo")
    resources = repository.resources("snapshot-1")
    edges = repository.edges("snapshot-1")
    print("Stored:", len(resources), "resources,", len(edges), "edges")
    print("Evidence:", edges[0].evidence[0].id)
    print("Published:", repository.is_published("snapshot-1"))

engine.dispose()
PY
```

Expected output, apart from any migration logging:

```text
Stored: 2 resources, 1 edges
Evidence: ev-tf-db-host
Published: True
```

## How the calls connect

```text
 load_fixture -> validated resources and edges
 upgrade -> create database tables from Alembic migrations
 transaction -> open session and database transaction
   create_project -> establish the project
   create_snapshot -> open snapshot
   save_resources -> identities plus snapshot versions
   save_edges -> evidence rows, edge rows, links preserving evidence order
   publish_snapshot -> mark contents frozen through repository operations
 successful exit -> commit
 new transaction -> query rows -> rebuild and validate domain models
```

[repository.py](../../../apps/api/perpetual/persistence/repository.py) stores each resource's identity separately from its version in a snapshot. Evidence is also stored separately from edges because several edges can share it. `save_edges` gathers evidence across the batch, stores it once, creates edge rows, then links their database IDs. Flushing makes those IDs available before the links are inserted.

On reload, `edges` queries edge rows and their evidence links, groups evidence by edge row ID, copies each JSON payload, adds its evidence, and validates the full `DependencyEdge`. The stored payload is not mutated. `_load` handles simpler tables whose payload already contains the whole model.

[db.py](../../../apps/api/perpetual/persistence/db.py) owns the session and transaction lifecycle; [migrate.py](../../../apps/api/perpetual/persistence/migrate.py) runs schema migrations. See [the persistence package](../packages/persistence.md) for the schema and [concepts](../concepts.md) for flush versus commit.

## Failure paths and limits

A write to this published snapshot raises `PersistenceError`. Reusing an evidence ID with different content is also refused. Let errors escape the transaction block so its pending changes are rolled back. Invalid stored payloads fail model validation when read.

This example saves only resources and edges. It demonstrates storage, not a completed scan, graph construction, or DR readiness. It deliberately does not synthesize scan coverage or persist the fixture's requirements.

[Repository tests](../../../apps/api/tests/persistence/test_repository.py) cover round trips, evidence ordering and reuse, conflicting evidence, published snapshots, project isolation, and batch statement counts. [Migration tests](../../../apps/api/tests/persistence/test_schema_and_migrations.py) check schema creation and dialect compatibility.
