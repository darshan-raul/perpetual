# Perpetual — Code Walkthrough

How the code is organised and how it works, written for a person reading it. The spec in [`docs/spec/`](../spec/) says what Perpetual must do; these documents say how the code does it today.

**Kept current with the code.** Every task that changes code updates the relevant page here in the same change (see [Keeping these docs current](#keeping-these-docs-current)). If a page and the code disagree, the code is right and the page is a bug.

## Reading order

1. [architecture.md](architecture.md): the pipeline, what exists so far, and how the pieces connect.
2. [tooling.md](tooling.md): how to run things and how every change is checked (mise, uv, import rules, tests, CI).
3. The package pages below, in pipeline order. Each one says what the package owns, walks through its files, explains the rules it enforces and why, and points at its tests.
4. Flow pages (from the first cross-package feature): one end-to-end path at a time, such as "what happens during `perpetual simulate`".

## Packages

All Python code lives in `apps/api/perpetual/`, one subpackage per pipeline stage (IMPL_PLAN §3.2). A package gets a page once it holds real code.

| Package | What it owns | Status | Page |
|---|---|---|---|
| `models` | Domain models, enums, status vocabulary. No I/O. | Core graph and stack models (P0-04a); typed properties for compute, data/storage, messaging, network, edge, supporting services, ARC and Identity Center (P0-04b to P0-04d); external/generic fallbacks and quota, capability and metric facts (P0-04e); coverage, resolved observations, workload/cost, evaluation inputs, verification, drills and operator access (P0-04f) | [packages/models.md](packages/models.md), [models-properties.md](packages/models-properties.md) |
| `config` | Typed config loading + versioned defaults | Evidence weights and groups, review threshold, scoring, RTO-scope defaults, buffer, freshness, limits and cost units, with project overrides (P0-06) | [packages/config.md](packages/config.md) |
| `ids` | Canonical resource IDs | Live, global, planned (`tf:`) and external IDs: build, parse, validate (P0-05) | [packages/ids.md](packages/ids.md) |
| `fixtures` | Fixture format, loader, validator | stub | — |
| `persistence` | SQLAlchemy models, repositories, migrations | stub | — |
| `collectors` | AWS, Kubernetes, CloudTrail, flow-log readers | stub | — |
| `importers` | Terraform JSON, recorded AWS responses | stub | — |
| `normalization` | Raw facts to typed resource nodes | stub | — |
| `evidence` | Edge resolvers, confidence combination | stub | — |
| `graph` | Graph snapshots, overrides, traversal | stub | — |
| `stacks` | Stack grouping, services, RTO scope | stub | — |
| `rules` | DR rule packs | stub | — |
| `simulator` | Failure simulation | stub | — |
| `recovery` | Recovery DAG, RTO, RPO | stub | — |
| `optimizer` | DR design candidates | stub | — |
| `costing` | Cost providers | stub | — |
| `iac` | Companion Terraform, suggested edits, delivery | stub | — |
| `runbooks` | Runbook, scripts, ARC plan compiler | stub | — |
| `llm`, `knowledge` | LLM agents and knowledge base (v0.2) | stub | — |
| `api`, `cli` | FastAPI routes, Typer commands | stub | — |

## Flows

None yet. The first flow page arrives with the first command that crosses packages (`perpetual graph`, P0-12).

## Keeping these docs current

- **Same change as the code.** A task that adds or changes code updates its package page, this index's status table, and [architecture.md](architecture.md) when connections change.
- **New package with real code:** copy [_template.md](_template.md) to `packages/<name>.md` and link it above.
- **New end-to-end path:** add `flows/<name>.md` and list it under Flows.
- **Split, don't sprawl.** When a page passes roughly 400 lines, split it by topic and link the parts from the package page.
- **Describe the code that exists.** Planned work belongs in the tracker; a page may mention what comes next in one line.
