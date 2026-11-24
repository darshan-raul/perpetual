# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Perpetual is a local, single-user tool that decides whether an AWS **stack** (one product: its services, data stores, networking and supporting services) can survive losing its Region within its RTO, RPO and budget. It computes a dependency graph from evidence, simulates the failure, plans recovery for the whole stack, designs the target DR architecture, and then changes the user's own Terraform and Kubernetes manifests to implement it, verified by re-simulation and delivered as a branch or PR. LLM agents (LangGraph) help with advisory review, candidate planning and the code changes; the deterministic engine verifies everything they propose.

- Product definition: [spec.md](spec.md) (revision 4 overview & index) and the 7 modular parts in [`docs/spec/`](docs/spec/). Together they are the source of truth for behaviour; tasks and code comments cite sections as `spec §N`.
- Plan (locked): [IMPL_PLAN.md](IMPL_PLAN.md). Progress: [TRACKER.md](TRACKER.md).
- Code walkthrough: [`docs/code/`](docs/code/README.md) explains how the code works today (architecture, tooling, one page per package, end-to-end flows). During active M0/M1 iteration, update `docs/code/` at **phase boundaries** (end of `P0`, end of `P1`, end of `P1c`, end of `P2`, etc.) instead of every subtask; from M2 onward, update it in the same change (the package page, the status table in `docs/code/README.md`, and `architecture.md` when connections change). Comment the *why* in code on every task, especially validators and engine rules, citing spec sections.
- At the start of a session, read TRACKER.md and continue from the session log's carry-over. At the end, update task states, the session log, the decision log and (at phase boundaries in M0/M1, or every task from M2 onward) `docs/code/`.
- Changes to the plan, or any deviation from the spec, go through a decision-log entry in TRACKER.md first. Changes to product behaviour go into spec.md with a changelog line under its current revision.
- **Strict just-in-time modeling rule:** do not build schemas, database tables, or helpers for future milestones until the consumer task is next in line.

## Readability and living wiki

Follow [AGENTS.md](AGENTS.md) and [docs/code/readability.md](docs/code/readability.md). Write for readers with basic Python knowledge, explain necessary framework features, and prefer explicit control flow and focused functions. Every implementation task includes a readability review; living-wiki updates (`docs/code/`: concepts, affected packages, worked flows, index, and architecture as appropriate) happen at phase boundaries during M0/M1 and in every code-changing task from M2 onward. New pages extend the wiki; changed behavior requires correcting existing pages.

## Status

Milestone M0 PoC in progress: P0-01 to P0-10 are done (repo, CI, import rules, domain models, resource IDs, config, persistence, fixture format, evidence combination, graph overrides); P0-11, minimal P0-15, and P0-12..14 follow before P1 and P1c, then M1 runs a CLI-first ECS + RDS slice (`perpetual scan -> simulate -> plan`) on real sandbox AWS before P1b FastAPI/UI in M2 (`v0.1`). The current task is in TRACKER.md. Commands marked as later phases below do not exist yet; P0-14 updates this file to match reality.

## Commands (from P0-01)

All tooling is pinned in `mise.toml` and run through mise.

```bash
mise install                 # Python 3.13, uv, Node (build-time only), Terraform
mise run lint                # ruff, eslint, import-linter contracts
mise run typecheck           # mypy --strict, tsc
mise run test                # pytest (fixtures + Stubber/moto); no AWS, no Docker
mise run check               # lint + typecheck + test

uv run pytest apps/api/tests/simulator/test_rto.py::test_refined_dag -q   # one test
uv run perpetual fixtures validate                  # check every fixture in fixtures/graphs
uv run perpetual graph --fixture ecs-broken
uv run perpetual simulate checkout --fixture ecs-broken --failure region:ap-south-1
uv run perpetual ui          # API + UI on http://127.0.0.1:8000 (from M2 v0.1)

docker compose up -d aws-emulator   # aws/aws-emulator for collector/Terraform/script integration tests (from M1 P2)
uv run pytest -m contract           # real-AWS contract suite; needs sandbox credentials, never default
```

## Architecture

Pipeline (IMPL_PLAN §3.1): collectors/importers → normalizers + identity resolution → edge resolvers (evidence) → user override layer → NetworkX graph snapshot → stacks/services/RTO scope → rule packs (findings + DR overlay mechanisms) → two-pass simulator → recovery DAG → RTO/RPO → optimizer (`StaticCostProvider` + 3–4 presets in v0.1; combinatorial search + `AWSPricingProvider` in v0.2 M3) → DR spec → IaC transformation with verification → branch/PR; companion Terraform; recovery artifacts (runbooks, prerequisite and Python recovery scripts in v0.1; compiled ARC Region switch plan added in v0.2 M3). M1 runs a CLI-first ECS + RDS slice (`perpetual scan -> simulate -> plan`) on real sandbox AWS before FastAPI + read-only React Flow UI (`P1b`) in M2 (`v0.1`). From v0.3 (`M4`), LLM agents attach at three points: advisor after rule packs (spec §28.2), planner inside the optimizer loop (§56.1), transformer after DR spec approval (§61).

- Python package `apps/api/perpetual/`, one subpackage per pipeline stage (IMPL_PLAN §3.2). Web UI in `apps/web/` (Vite + React), built into `apps/api/perpetual/web/static/` and served by FastAPI. TS API types in `packages/schemas` are generated from OpenAPI; never edit them by hand.
- Layer boundaries are enforced by import-linter (IMPL_PLAN §3.3): collectors only collect, rule packs never call collectors or LLMs, the simulator never rediscovers AWS, domain models never import FastAPI or SQLAlchemy. Only `perpetual.llm` imports LangChain/LangGraph; the engine never calls an agent.
- LLM providers are configured, not coded: everything goes through LangChain's chat-model interface (`init_chat_model`), so OpenRouter, Anthropic, Bedrock or Ollama can be swapped per role (spec §69.1). Never import a vendor SDK directly.
- Agent know-how lives in `skills/` (SKILL.md per DR mechanism) and the local knowledge base (`knowledge/domain/` shipped service DR docs + `knowledge/sources.yaml` + dynamic `web_search`/`web_fetch` ingestion for unmodeled/out-of-scope resources); prompts stay small and load skills on demand (spec §69.3, §69.4).
- All numbers that tune behaviour (evidence weights, correlation groups, thresholds, scoring, RTO-scope defaults, buffer, duration catalog, prices) live in YAML under `apps/api/perpetual/config/defaults/`. Never put them in rule or engine code.

## Rules that span the codebase

- Edge direction is always dependent → dependency. `replicates_to` and `backed_up_by` are not "requires" edges; the impact pass skips them and only the DR overlay follows them (spec §20, §44).
- Missing evidence is `UNKNOWN`, never PASS or READY. An action with no catalog entry makes the RTO UNKNOWN, never zero (spec §30, §49.1).
- Use the ordered readiness table in spec §31. A usable recovery path that misses RPO is recoverable but NOT_READY; target failure alone is not application unavailability.
- Live and planned snapshots have different precedence. Apply lifecycle changes under §15.4 and invalidate old operational proof; import saved-plan `terraform show -json`, never the `plan -json` UI stream.
- Coverage, confirmed absence and freshness follow §76.1. Failed collectors retain historical context but cannot prove current presence, absence or readiness.
- Preserve ALL/ANY/quorum groups and selected recovery paths (§19.1). Ambiguous shared-role/ENI observations remain candidate sets, without exact-edge confidence uplift (§14.1).
- Bind results, approvals and verification reports to immutable input/output digests (§56.3). Check validity on resume and delivery. Design verification never establishes observed READY (§61.1).
- Cost uses versioned workload inputs and total steady-state DR ownership (§59.1); missing usage/prices stay unknown. Budget PASS requires the high bound within budget.
- Use the canonical status vocabulary in spec §30.1; UI colours map onto it and are not separate states.
- DR results exist only per stack: one plan, one RTO, one RPO per stack and failure scenario. Per-resource durations, options and costs are inputs and must not be presented as results (spec §47, §50, §55).
- Monitoring, logging and CI/CD are out of RTO scope by default: shown and assessed, but never blocking and never on the plan (spec §24.1).
- A stack cannot be READY while a low-confidence required-path edge is unreviewed; it shows UNKNOWN with reason `graph_not_reviewed`. Negative results are never held back (spec §23).
- User graph edits are `GraphOverride` rows applied on top of each scan. Never mutate discovered data to reflect an edit (spec §23).
- "Reproducible" (`rebuild_from_iac`) has the strict meaning in spec §27.1; otherwise the mechanism is `unknown`.
- Read-only against AWS. Never call `GetSecretValue`, never enable trails, data events or flow logs. Persist only matched facts from env vars and ConfigMaps, and only aggregates of CloudTrail and flow-log data (spec §14.1, §65–§67).
- Graph traversal must terminate on cycles and record them as evidence; use NetworkX operations rather than hand-written recursion (spec §18).
- The LLM proposes, the engine verifies (spec §2, rule 11). LLM output never upgrades a state, supplies a number, or counts as proof. Proposals need citations; uncited ones are dropped. A blocking advisory item keeps the stack from READY (`advisory_unresolved`).
- Code changes happen only in a git worktree on a `perpetual/dr/...` branch. The command allowlist and process/filesystem/network/credential isolation in §61 are mandatory before repository tool execution; no unsandboxed fallback. `terraform apply|destroy|import|state` and `kubectl apply` stay unreachable. Reports separate static checks, design verification, deployment prerequisites and observed readiness (§61.1).
- Recovery runs by laptop-run Python recovery scripts (`P11-06`), prerequisite scripts (`P11-05`), and explanatory runbooks (`P11-02/03`) in v0.1 (`M2`); the compiled ARC Region switch plan compiler (`P11-07`) arrives in v0.2 (`M3 Expansion`), adding a second execution method chosen in the DR spec. All artifacts come from one recovery DAG with the same digest and step numbers; Perpetual generates and checks them and never runs them (spec §47.2, §63).
- Never send Terraform state, secret values, env/ConfigMap values or raw logs to an LLM. Redact IaC before sending, sanitize `web_search`/`web_fetch` queries to generic AWS/DR/Terraform terms only, honour `.perpetualignore`, and record every call in `llm_calls` (spec §69.5).
- Strict just-in-time modeling: never add database tables, schemas, or helpers for future milestones until the consumer task is next in line.

## Testing

- Spec §90.1 3-tier test pyramid: fixtures for the engine (no network), `botocore.stub.Stubber` / `moto` for pure in-process unit error-injection tests, `aws/aws-emulator` (`aws-emulator`) for stateful collector/Terraform/recovery-script integration tests, and an opt-in real-AWS contract suite in `tests/contract/` (with guaranteed teardown) for what emulators cannot prove (real cross-Region replication lag, CloudWatch Metrics, Service Quotas, CloudTrail/Flow Log delivery, cross-account STS).
- Spec §90.2 and IMPL_PLAN §3.5 assign review regressions and end-to-end evidence coverage. Implement each gate in its owning phase; do not defer them all to hardening.
- Canonical fixtures: `ecs-broken` (spec §87) and `ecs-remediated` (§88) are M0/M1/v0.1 release gates; EKS fixture B (§86, §89) is post-v0.1 (`M3 Expansion`). Their expected results are release gates in TRACKER.md.
- Synthetic CloudTrail (M1) and flow-log (M3 Expansion) files come from the generator in `fixtures/logs/`; `aws/aws-emulator` produces no real logs.
- LLM stages run in tests against a fake chat model with recorded responses, including hostile outputs; CI never needs an API key. Real-provider evals live in `evals/` and run on demand (spec §69.6).
