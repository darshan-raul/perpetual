# Tooling and checks

How to run the project and what checks every change.

## Commands

All tools are pinned in `mise.toml` and run through mise.

| Command | What it does |
|---|---|
| `mise install` | Installs the pinned Python, uv, Node and Terraform |
| `mise run sync` | Installs Python dependencies into `.venv` from `uv.lock` |
| `mise run fmt` | Formats and auto-fixes with ruff |
| `mise run lint` | ruff lint, ruff format check, import-linter rules |
| `mise run typecheck` | mypy in strict mode, with Pydantic's plugin |
| `mise run test` | pytest (no AWS, no Docker) |
| `mise run check` | lint + typecheck + test; the same command CI runs |

One test: `uv run pytest apps/api/tests/models/test_model_edge.py::test_bases_are_derived_from_evidence -q`.

Machine-only settings go in `mise.local.toml`, which is gitignored.

## Project layout

```text
pyproject.toml            the one Python project: builds `perpetual` from apps/api/perpetual,
                          plus ruff, mypy, pytest and import-linter config
uv.lock                   exact dependency versions
mise.toml                 pinned tools and tasks
apps/api/perpetual/       the package, one subpackage per pipeline stage
apps/api/tests/           tests, mirroring the package (tests/models/ for perpetual.models)
.github/workflows/ci.yml  CI
docs/spec/                what Perpetual must do
docs/code/                how the code does it (these pages)
```

## Import rules

Defined in `pyproject.toml` under `[tool.importlinter]`; run by `mise run lint`.

| Rule | Why |
|---|---|
| `models`, `ids`, `config` import nothing else from Perpetual | They are the shared vocabulary; everything depends on them |
| `models` never imports FastAPI or SQLAlchemy | Domain models stay free of web and database concerns |
| Collectors never import rules, simulator, recovery, optimizer | Collectors only collect |
| Normalization never imports `api` or `cli` | Lower layers do not reach up |
| Rules never import collectors | Rules work on the graph, never on AWS directly |
| Simulator never imports collectors or importers | The simulator never rediscovers AWS |
| Nothing below `api` and `cli` imports them | They are the top layer |
| The engine never imports `llm` or `knowledge` | The LLM proposes; the engine verifies and never calls an agent |
| Only `llm` imports LangChain or LangGraph | Keeps the LLM stack in one place |

`apps/api/tests/test_import_contracts.py` proves each rule works by planting a forbidden import in a temporary copy of the package and checking that the right rule fails.

## Tests

- Tests mirror the package: `apps/api/tests/<package>/test_<topic>.py`.
- pytest runs in importlib mode, so tests cannot import helpers from `conftest.py`. Shared builders live in a normal module, for example `tests/models/builders.py`, imported as `from tests.models.builders import ...`.
- Tests marked `contract` need real AWS sandbox credentials and are skipped by default.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request: it installs the pinned tools with mise, installs dependencies with `uv sync --locked` (failing if `uv.lock` is stale), then runs `mise run check`. Actions are pinned to exact commit SHAs.
