# `cli` package

**Owns:** the `perpetual` command (Typer + Rich).
**Spec:** §79. **Tracker:** P0-08 (`fixtures`), P0-12 (`graph`).
**Depends on:** any engine package it drives; nothing imports `cli` (an import rule enforces this). **Used by:** people, through the `perpetual` console script in `pyproject.toml`.

## Commands so far

```bash
uv run perpetual fixtures validate [NAME_OR_PATH ...]   # default: every fixture in fixtures/graphs
uv run perpetual fixtures schema [--out FILE]           # JSON Schema for fixture files
uv run perpetual graph --fixture NAME [--stack S] [--unreviewed] [--json]
uv run perpetual graph overrides export --fixture NAME [--out FILE]
uv run perpetual graph overrides apply FILE --fixture NAME [--project ID] [--out FILE] [--json]
```

How a command runs end to end: [flows/fixtures-validate.md](../flows/fixtures-validate.md).

`validate` prints `ok` per valid fixture, or `FAIL` with every problem and its path. Exit codes: 0 all valid, 1 a fixture failed, 2 no fixtures found.

`graph` applies fixture overrides, builds the validated `DependencyGraph` and `SnapshotManifest`, detects cycles, highlights unreviewed edges below `review_confidence_threshold`, and renders Rich tables (resources, dependency edges, DR overlay mechanisms) or JSON.

To refresh the committed schema after changing a model: `uv run perpetual fixtures schema --out fixtures/schema/fixture-v1.schema.json`. A test fails until you do.

## Files

| File | What it holds |
|---|---|
| `app.py` | The root Typer app and `main` |
| `fixtures.py` | `perpetual fixtures validate` and `schema` |
| `graph.py` | `perpetual graph` and `perpetual graph overrides export|apply` |

Commands stay thin: they resolve arguments, call a package function and print. Logic lives in the packages, so the API (P1b) can call the same functions.

## Tests

`apps/api/tests/cli/test_cli_fixtures.py` and `apps/api/tests/cli/test_cli_graph.py` run the commands with Typer's `CliRunner`: fixture validation/schema, graph tables/JSON/stack/unreviewed filtering, and override YAML export/apply round-trips and errors.
