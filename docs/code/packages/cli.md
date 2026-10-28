# `cli` package

**Owns:** the `perpetual` command (Typer + Rich).
**Spec:** §79. **Tracker:** P0-08 (first commands); P0-12 adds `perpetual graph`.
**Depends on:** any engine package it drives; nothing imports `cli` (an import rule enforces this). **Used by:** people, through the `perpetual` console script in `pyproject.toml`.

## Commands so far

```bash
uv run perpetual fixtures validate [NAME_OR_PATH ...]   # default: every fixture in fixtures/graphs
uv run perpetual fixtures schema [--out FILE]           # JSON Schema for fixture files
```

How a command runs end to end: [flows/fixtures-validate.md](../flows/fixtures-validate.md).

`validate` prints `ok` per valid fixture, or `FAIL` with every problem and its path. Exit codes: 0 all valid, 1 a fixture failed, 2 no fixtures found.

To refresh the committed schema after changing a model: `uv run perpetual fixtures schema --out fixtures/schema/fixture-v1.schema.json`. A test fails until you do.

## Files

| File | What it holds |
|---|---|
| `app.py` | The root Typer app and `main` |
| `fixtures.py` | `perpetual fixtures validate` and `schema` |

Commands stay thin: they resolve arguments, call a package function and print. Logic lives in the packages, so the API (P1b) can call the same functions.

## Tests

`apps/api/tests/cli/test_cli_fixtures.py` runs the commands with Typer's `CliRunner`: valid fixture, failing fixture with paths in the output, no fixtures, schema to stdout and to a file.
