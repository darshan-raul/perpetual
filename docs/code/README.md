# Perpetual — Living Code Wiki

How the code is organised and how it works, written for a person reading it. The spec in [`docs/spec/`](../spec/) says what Perpetual must do; these documents say how the code does it today.

**Kept current with the code.** During active M0/M1 iteration, update the relevant pages here at **phase boundaries** (end of `P0`, end of `P1`, end of `P1c`, end of `P2`, etc.); from M2 onward, update them in the same change as the code (see [Keeping these docs current](#keeping-these-docs-current)). If a page and the code disagree, the code is right and the page is a bug.

Written for readers with basic Python knowledge. Start with the concepts, follow a worked flow, then open the linked source files. This wiki grows with implementation; existing pages are revised when behavior changes.

## Reading order

1. [concepts.md](concepts.md): domain vocabulary and Python/library features used in the code.
2. [architecture.md](architecture.md): the pipeline, what exists so far, and how the pieces connect.
3. [tooling.md](tooling.md): how to run things and how every change is checked (mise, uv, import rules, tests, CI).
4. The package pages below, in pipeline order. Each one says what the package owns, walks through its files, explains the rules it enforces and why, and points at its tests.
5. Flow pages: one end-to-end path at a time, such as "what happens during `perpetual fixtures validate`".

```text
 README (this page) ──> concepts.md ──> architecture.md ──> tooling.md
                              │
                              ▼
        packages/ids.md   packages/models.md ──> models-properties.md
        packages/config.md    packages/persistence.md
        packages/fixtures.md  packages/cli.md   packages/evidence.md
                              │
                              ▼
                     flows/fixtures-validate.md   (how they work together)
```

## Packages

All Python code lives in `apps/api/perpetual/`, one subpackage per pipeline stage (IMPL_PLAN §3.2). A package gets a page once it holds real code.

| Package | What it owns | Status | Page |
|---|---|---|---|
| `models` | Domain models, enums, status vocabulary. No I/O. | Core graph and stack models (P0-04a); typed properties for compute, data/storage, messaging, network, edge, supporting services, ARC and Identity Center (P0-04b to P0-04d); external/generic fallbacks and quota, capability and metric facts (P0-04e); coverage, resolved observations, workload/cost, evaluation inputs, verification, drills and operator access (P0-04f) | [packages/models.md](packages/models.md), [models-properties.md](packages/models-properties.md) |
| `config` | Typed config loading + versioned defaults | Evidence weights and groups, review threshold, scoring, RTO-scope defaults, buffer, freshness, limits and cost units, with project overrides (P0-06) | [packages/config.md](packages/config.md) |
| `ids` | Canonical resource IDs | Live, global, planned (`tf:`) and external IDs: build, parse, validate (P0-05) | [packages/ids.md](packages/ids.md) |
| `fixtures` | Fixture format, loader, validator | Format v1, ID-derived fields, model and cross-reference checks with paths, lookup by name, JSON Schema, versioned inputs & workload profiles, canonical fixtures (`ecs-broken`, `ecs-remediated`, `cycle`, `shared-node`, `deep-path`) (P0-08, P0-13, P0-15) | [packages/fixtures.md](packages/fixtures.md) |
| `persistence` | SQLAlchemy models, repositories, migrations | 20 tables (17 P0 foundation tables + `recovery_requirements`, `simulations`, `recovery_plans` in P1-15), `ProjectRepository`, migrations `0001`–`0002` (P0-07, P1-15) | [packages/persistence.md](packages/persistence.md) |
| `collectors` | AWS, Kubernetes, CloudTrail, flow-log readers | stub | — |
| `importers` | Terraform JSON, recorded AWS responses | stub | — |
| `normalization` | Raw facts to typed resource nodes | stub | — |
| `evidence` | Edge resolvers, confidence combination | Combination with correlation groups (pluggable, config-driven) and evidence fingerprints (P0-09); explicit grouping and stable-hash regression after readability review; resolvers in P2b | [packages/evidence.md](packages/evidence.md) |
| `graph` | Graph snapshots, overrides, traversal, manifests | Override replay, rescan merge, orphan/reproposal diagnostics and versioned YAML (P0-10); NetworkX `MultiDiGraph` snapshot, group validation & cycle-safe traversal (P0-11); canonical SHA-256 digests & `SnapshotManifest` (P0-15) | [packages/graph.md](packages/graph.md) |
| `stacks` | Stack grouping, services, RTO scope | RTO scope classification from config defaults and per-resource overrides (P1-03) | [packages/stacks.md](packages/stacks.md) |
| `rules` | DR rule packs | `DRRulePack` protocol, `RulePackRegistry`, `rules/cross/` skeleton (P1-01); 9 first-slice ECS + RDS mechanism resolvers with strict §27.1 reproducibility (P1-02) | [packages/rules.md](packages/rules.md) |
| `simulator` | Failure simulation | Scenario hierarchy & dispatch, two-pass impact + cycle-safe recovery engine, ordered §31 readiness composition, reason chains (P1-04..P1-08) | [packages/simulator.md](packages/simulator.md) |
| `recovery` | Recovery DAG, RTO, RPO | Versioned duration catalog v1, first-slice + generic fallback actions, phase-template + refined DAG builder, buffer, critical-path RTO, target comparison, bounded ALL/ANY/quorum path selection (P1-09..P1-14, P1-18) | [packages/recovery.md](packages/recovery.md) |
| `optimizer` | DR design candidates | stub | — |
| `costing` | Cost providers | stub | — |
| `iac` | Companion Terraform, suggested edits, delivery | stub | — |
| `runbooks` | Runbook, scripts (`v0.1`), ARC plan compiler (`v0.2` M3) | stub | — |
| `llm`, `knowledge` | LLM agents and knowledge base (`v0.3` M4) | stub | — |
| `cli` | Typer commands | `perpetual fixtures validate|schema` (P0-08), `perpetual graph` + `overrides export|apply` (P0-12), `perpetual simulate` & `perpetual plan` (P1-16) | [packages/cli.md](packages/cli.md) |
| `api` | FastAPI routes | stub | — |

## Flows

Paths across packages, with command flows and manual library examples labeled separately:

| Flow | Packages |
|---|---|
| [`perpetual fixtures validate`](flows/fixtures-validate.md) | `cli` → `fixtures` → `ids`, `models` |
| [Inspect fixture evidence (manual library example)](flows/fixture-evidence.md) | `fixtures` → `config` → `evidence` |
| [Snapshot round trip (manual library example)](flows/snapshot-round-trip.md) | `fixtures` → `persistence` → `models` |
| [Apply graph overrides (manual library example)](flows/graph-overrides.md) | `fixtures` → `graph.overrides` → `evidence`, `ids`, `models` |

## Writing and reviewing

The [2026-11-07 readability audit](readability-audit.md) records the reviewed scope, refactors, and compatibility checks.

Follow [readability.md](readability.md) for the code style and completion checklist. Use [_template.md](_template.md) for package pages and [_flow-template.md](_flow-template.md) for flows.

## Keeping these docs current

- **Explain concepts as they arrive.** Extend [concepts.md](concepts.md), or add a linked topic page, when a feature introduces domain terms, algorithms, or unfamiliar Python/library features. Define the idea before describing the implementation.
- **Grow and correct.** Add new concepts and flows as work progresses; revise or remove obsolete explanations. Keep historical decisions in `TRACKER.md` and Git history, so the wiki describes the current code.
- **Phase boundaries in M0/M1; same change from M2.** During active M0/M1 iteration, update affected package pages, this index's status table, and [architecture.md](architecture.md) at phase boundaries (end of `P0`, `P1`, `P1c`, `P2`, etc.) rather than every subtask. From M2 onward, update them in the same change as the code.
- **New package with real code:** copy [_template.md](_template.md) to `packages/<name>.md` and link it above.
- **New end-to-end path:** use [_flow-template.md](_flow-template.md) to add `flows/<name>.md` and list it under Flows. Include concrete input/output, source links, error cases, and relevant tests. Label library compositions that are not wired into a command.
- **Split, don't sprawl.** When a page passes roughly 400 lines, split it by topic and link the parts from the package page.
- **Draw the flow.** Each package page has at least one ASCII diagram of its main path (what calls what, what data goes in and comes out, where it can fail), and each flow page traces one command through the packages with file and function names. Diagrams use plain `text` code blocks so they read the same in a terminal and on GitHub.
- **Describe the code that exists.** Planned work belongs in the tracker; a page may mention what comes next in one line.
