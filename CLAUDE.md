# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Perpetual is a local, single-user tool that decides whether an AWS **stack** (one product: its services, data stores, networking and supporting services) can survive losing its Region within its RTO, RPO and budget. It computes a dependency graph from evidence, simulates the failure, plans recovery for the whole stack, and later generates DR Terraform and runbooks.

- Product definition: [spec.md](spec.md) (revision 3). It is the source of truth for behaviour; tasks and code comments cite it as `spec §N`.
- Plan (locked): [IMPL_PLAN.md](IMPL_PLAN.md). Progress: [TRACKER.md](TRACKER.md).
- At the start of a session, read TRACKER.md and continue from the session log's carry-over. At the end, update task states, the session log and the decision log.
- Changes to the plan, or any deviation from the spec, go through a decision-log entry in TRACKER.md first. Changes to product behaviour go into spec.md with a changelog line under its current revision.

## Status

No code yet. Work starts at P0-01. The commands and layout below are what P0 creates; P0-14 updates this file to match reality.

## Commands (from P0-01)

All tooling is pinned in `mise.toml` and run through mise.

```bash
mise install                 # Python 3.13, uv, Node (build-time only), Terraform
mise run lint                # ruff, eslint, import-linter contracts
mise run typecheck           # mypy --strict, tsc
mise run test                # pytest (fixtures + moto); no AWS, no Docker
mise run check               # lint + typecheck + test

uv run pytest apps/api/tests/simulator/test_rto.py::test_refined_dag -q   # one test
uv run perpetual graph --fixture ecs-broken
uv run perpetual simulate checkout --fixture ecs-broken --failure region:ap-south-1
uv run perpetual ui          # API + UI on http://127.0.0.1:8000

docker compose up -d floci   # emulator for collector integration tests (from P2)
uv run pytest -m contract    # real-AWS contract suite; needs sandbox credentials, never default
```

## Architecture

Pipeline (IMPL_PLAN §3.1): collectors/importers → normalizers + identity resolution → edge resolvers (evidence) → user override layer → NetworkX graph snapshot → stacks/services/RTO scope → rule packs (findings + DR overlay mechanisms) → two-pass simulator → recovery DAG → RTO/RPO → optimizer → Terraform compiler and runbooks.

- Python package `apps/api/perpetual/`, one subpackage per pipeline stage (IMPL_PLAN §3.2). Web UI in `apps/web/` (Vite + React), built into `apps/api/perpetual/web/static/` and served by FastAPI. TS API types in `packages/schemas` are generated from OpenAPI; never edit them by hand.
- Layer boundaries are enforced by import-linter (IMPL_PLAN §3.3): collectors only collect, rule packs never call collectors or LLMs, the simulator never rediscovers AWS, domain models never import FastAPI or SQLAlchemy.
- All numbers that tune behaviour (evidence weights, correlation groups, thresholds, scoring, RTO-scope defaults, buffer, duration catalog, prices) live in YAML under `apps/api/perpetual/config/defaults/`. Never put them in rule or engine code.

## Rules that span the codebase

- Edge direction is always dependent → dependency. `replicates_to` and `backed_up_by` are not "requires" edges; the impact pass skips them and only the DR overlay follows them (spec §20, §44).
- Missing evidence is `UNKNOWN`, never PASS or READY. An action with no catalog entry makes the RTO UNKNOWN, never zero (spec §30, §49.1).
- Use the canonical status vocabulary in spec §30.1; UI colours map onto it and are not separate states.
- DR results exist only per stack: one plan, one RTO, one RPO per stack and failure scenario. Per-resource durations, options and costs are inputs and must not be presented as results (spec §47, §50, §55).
- Monitoring, logging and CI/CD are out of RTO scope by default: shown and assessed, but never blocking and never on the plan (spec §24.1).
- A stack cannot be READY while a low-confidence required-path edge is unreviewed; it shows UNKNOWN with reason `graph_not_reviewed`. Negative results are never held back (spec §23).
- User graph edits are `GraphOverride` rows applied on top of each scan. Never mutate discovered data to reflect an edit (spec §23).
- "Reproducible" (`rebuild_from_iac`) has the strict meaning in spec §27.1; otherwise the mechanism is `unknown`.
- Read-only against AWS. Never call `GetSecretValue`, never enable trails, data events or flow logs. Persist only matched facts from env vars and ConfigMaps, and only aggregates of CloudTrail and flow-log data (spec §14.1, §65–§67).
- Graph traversal must terminate on cycles and record them as evidence; use NetworkX operations rather than hand-written recursion (spec §18).

## Testing

- Spec §90.1: fixtures for the engine (no network), moto for collector unit tests, Floci for collector integration tests, and an opt-in real-AWS contract suite in `tests/contract/` that always tears down what it creates.
- Canonical fixtures: `ecs-broken` (spec §87), `ecs-remediated` (§88), EKS fixture B (§86, §89). Their expected results are release gates in TRACKER.md.
- Synthetic CloudTrail and flow-log files come from the generator in `fixtures/logs/`; emulators produce no real logs.
