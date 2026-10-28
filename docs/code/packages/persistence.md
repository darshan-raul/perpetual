# `persistence` package

**Owns:** the database: SQLAlchemy tables, a project-scoped repository, and Alembic migrations.
**Spec:** §14.1, §15.4, §23, §56.3, §71.1, §75, §76, §76.1. **Tracker:** P0-07.
**Depends on:** `models`; SQLAlchemy and Alembic. **Used by:** the API, CLI and pipeline stages that save or load results, as they are built.

## In one paragraph

Perpetual stores everything in one SQLite file (`$XDG_DATA_HOME/perpetual/perpetual.db`, or `~/.local/share/perpetual/perpetual.db`), and the schema stays PostgreSQL-compatible so a hosted version could swap the URL. Each table row has a few typed **lookup columns** that queries filter on (IDs, project, snapshot, type, endpoints, status) and a **`payload`** column holding the full domain model as JSON. Loading rebuilds the domain model from the payload and validates it again, so the database can never hand the engine data the models would refuse. All access goes through `ProjectRepository`, which is bound to one project and adds `project_id` to every query.

## Files

| File | What it holds |
|---|---|
| `db.py` | Default database path, `make_engine` (turns SQLite foreign keys on), `make_session_factory`, `transaction` |
| `tables.py` | The 17 tables, the naming convention for constraints, and `UtcDateTime` |
| `repository.py` | `create_project`, `ProjectRepository`, `PersistenceError` |
| `migrate.py` | `upgrade(engine)` and `downgrade(engine, revision)`, run from code |
| `migrations/` | Alembic environment and `versions/0001_initial_schema.py` |

## The schema

```text
projects
  scans ── scan_coverage
  snapshots (live | planned; published once, then frozen)
    resource_versions   (a resource as this snapshot saw it)
    evidence ── edge_evidence ── edges
    dependency_groups   observations   recovery_mechanisms
    stacks   stack_resources   stack_services
  resources            (identity across snapshots: first seen, type)
  graph_overrides      (user edits, per project, applied on top of each snapshot)
  evaluation_inputs    (immutable manifests, add-only)
```

- **Snapshots** hold discovered data. A scan (or, later, a saved Terraform plan) fills an open snapshot, then `publish_snapshot` freezes it, and any further write raises. Older snapshots are kept; `resource_history` returns every version of one resource, oldest first (§76, drift in §77).
- **Overrides** are per project, not per snapshot, because they apply on top of every scan. Discovered rows are never changed to reflect an edit (§23). Only an override's status changes, e.g. to `orphaned`.
- **Evidence** is stored once per snapshot and linked to edges by position, so an edge reloads with its evidence in the same order. The same evidence ID with different content is refused: it means a bug upstream. Groups and mechanisms keep their (rare) evidence inside their payload.
- **Observations** are the resolved CloudTrail/flow-log aggregates from `models.observation`; raw events have nowhere to go.

## A scan's lifecycle

```text
 add_scan("scan-1")                    scans.status = running
      │
 create_snapshot("snap-1", live)       snapshots.published_at = NULL   (open)
      │
      ├── save_coverage(scan-1, …)     scan_coverage rows
      ├── save_resources(snap-1, …)    resources (identity, first time only) + resource_versions
      ├── save_edges(snap-1, …)        edges + evidence (once) + edge_evidence links
      ├── save_groups / save_observations / save_mechanisms / save_stacks
      │
 publish_snapshot("snap-1")            published_at = now   ── from here, every save_* to
      │                                                         snap-1 raises PersistenceError
 finish_scan("scan-1", completed|partial|failed)   can't be finished twice

 next scan -> new snapshot "snap-2"; snap-1 stays as it was (history, drift)
 overrides and evaluation inputs live beside snapshots, per project
```

## What `save_edges` writes

```text
 DependencyEdge e1 (evidence: [ev-b, ev-a])      DependencyEdge e2 (evidence: [ev-a])
        │                                                │
        ▼                                                ▼
 edges row  e1  payload = edge WITHOUT evidence   edges row  e2
        │                                                │
        ├─ position 0 ─> _store_evidence(ev-b) ─> new evidence row
        ├─ position 1 ─> _store_evidence(ev-a) ─> new evidence row ◄─┐
        │                                                            │ same id, same content:
        │                                        position 0 ─────────┘ reuse the row
        ▼
 edge_evidence (edge_row, position, evidence_row)
 same id with DIFFERENT content -> PersistenceError (a bug upstream, never merged)
```

## How loading works

```text
 repo.edges("snap-1")
   SELECT edges WHERE project_id = repo.project_id AND snapshot_id = "snap-1" ORDER BY edge_id
   SELECT evidence payloads via edge_evidence, ORDER BY position
        │
        ▼
   payload + {"evidence": [...]}  ──>  DependencyEdge.model_validate(...)
                                       every model rule runs again; a bad row can't reach
                                       the engine as a "valid" edge
```

Every query includes the repository's `project_id`; a scan or snapshot ID from another project is "not found".

## Using it

```python
from perpetual.persistence import (
    ProjectRepository, create_project, make_engine, make_session_factory,
    sqlite_url, default_database_path, transaction, upgrade,
)

engine = make_engine(sqlite_url(default_database_path()))
upgrade(engine)
factory = make_session_factory(engine)

with transaction(factory) as session:
    create_project(session, "p1", "Checkout", now)
    repo = ProjectRepository(session, "p1")
    repo.add_scan("scan-1", now, ["aws_api"])
    repo.create_snapshot("snap-1", "live", now, scan_id="scan-1")
    repo.save_resources("snap-1", nodes)
    repo.save_edges("snap-1", edges)
    repo.publish_snapshot("snap-1", now)
    repo.finish_scan("scan-1", "completed", now, resource_count=len(nodes), edge_count=len(edges))
```

## Rules it enforces, and why

| Rule | Where | Why (spec) |
|---|---|---|
| Every query filters on the repository's project; another project's scan or snapshot can't be read or written | `ProjectRepository` | Rows are scoped by `project_id` (§71.1) |
| A published snapshot can't change | `_open_snapshot` | Snapshots are built atomically and stay immutable (§15.4, §76.1) |
| Overrides are a separate table; only their status changes | `set_override_status` | Never mutate discovered data to reflect an edit (§23) |
| Evaluation inputs have no update | `add_evaluation_input` | Manifests are immutable (§56.3) |
| One evidence ID, one content | `_store_evidence` | Evidence is a traceable fact (§16) |
| A finished scan stays finished | `finish_scan` | Previous scans are kept as they were (§76) |
| Datetimes are stored in UTC and come back timezone-aware | `UtcDateTime` | SQLite has no time zones; the models reject naive datetimes |
| Portable types only; constraint names ≤ 63 characters | `tables.py` | PostgreSQL compatibility (§71.1) |

## Migrations

`upgrade(engine)` runs Alembic from code; there is no `alembic.ini`. Migrations run in batch mode so later ones can alter tables on SQLite. The initial migration was autogenerated from the tables and uses plain SQLAlchemy types (no imports from Perpetual), so it stays valid if the code changes. To add one: change `tables.py`, then generate a revision against a database at head, and review it.

## Tests

`apps/api/tests/persistence/`:

- `test_schema_and_migrations.py`: the planned tables exist and carry `project_id`; the migration matches the models exactly (Alembic compare); downgrade removes everything; tables and indexes compile on SQLite and PostgreSQL; identifiers fit PostgreSQL; the migration renders as PostgreSQL SQL offline; default database path.
- `test_repository.py`: round trips for resources, edges (evidence order, shared evidence stored once), groups, observations, mechanisms, stacks, coverage, overrides and evaluation inputs; conflicting evidence refused; published snapshots frozen; history across snapshots; scan lifecycle; project isolation; override status changes leave the edit intact.

## Not here yet

Tables for later phases (findings, simulations, recovery plans, cost estimates, DR specs, verification reports, drills, LLM calls, knowledge base) arrive with their tasks, each as a new migration.
