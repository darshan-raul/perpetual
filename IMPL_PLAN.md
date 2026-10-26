# Perpetual — Implementation Plan

Status: **locked** on 2026-10-25. Progress lives in [TRACKER.md](TRACKER.md). Change this file only through a decision-log entry there.

The product is defined in [spec.md](spec.md) (revision 4 overview & index) and its 7 modular topic files in [`docs/spec/`](docs/spec/). This plan orders the work and fixes the choices the spec leaves open. If this plan and the spec disagree, the spec wins unless a decision-log entry says otherwise.

## 1. Goal

Ship Perpetual v0.1: a local, single-user tool that delivers the MVP workflow in spec §100 for an ECS stack and an EKS stack on AWS.

1. Import Terraform and/or scan AWS.
2. Compute the dependency graph from evidence; the user reviews and edits it.
3. Group resources into a stack and its services; set RTO scope.
4. Enter target Region, RTO, RPO and budget for the stack.
5. Simulate Region failure: stack state, what survives, what fails, why.
6. Calculate one recovery plan, one RTO (with buffer) and one RPO for the stack.
7. Compare whole-stack DR architectures (deterministic and LLM-proposed) and approve a DR spec.
8. Change the user's Terraform and Kubernetes manifests to implement it, verify by re-simulating, and deliver a branch or PR.
9. Generate failover and failback runbooks.

## 2. Locked decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Names | Product and CLI `perpetual`. Python package `perpetual`. Repo `github.com/darshan-raul/perpetual`. |
| D2 | Source of truth | `spec.md` defines behaviour. This plan defines order and tooling. Section numbers in tasks refer to the spec. |
| D3 | Delivery | Local single-user tool (spec §71.1). `perpetual ui` runs one FastAPI process on `127.0.0.1:8000` that serves the API and the pre-built UI. SQLite by default. No hosting in v0.1. |
| D4 | Toolchain | `mise` pins Python 3.13, `uv`, Node (LTS, build-time only) and Terraform in the repo `mise.toml`. All commands run through `mise run <task>`. |
| D5 | Repo layout | Spec §73, with: a root `pyproject.toml` (uv workspace + root-installable `perpetual` package pointing Hatchling at `apps/api/perpetual` so `uv tool install .` works from the repo root); the Python package in `apps/api/perpetual/`; the Vite app in `apps/web/`; the UI build copied into `apps/api/perpetual/web/static/` (gitignored) and shipped inside the wheel. |
| D6 | Python stack | Pydantic v2, SQLAlchemy 2 (typed ORM), Alembic **from P0** (the spec defers it to 1b; starting early avoids migration debt), NetworkX, boto3, `kubernetes` client, Typer + Rich for the CLI, httpx, pytest, ruff, mypy `--strict`. |
| D7 | UI stack | Vite, React, TypeScript strict, Tailwind, shadcn/ui, React Flow with ELK layout, TanStack Query, TanStack Router. API types generated from OpenAPI with `openapi-typescript` into `packages/schemas`. |
| D8 | Layer boundaries | Enforced with `import-linter` contracts in CI (§3.3). Not left to review. |
| D9 | Order | Engine first, CLI first (spec §99). ECS vertical slice through simulation and recovery planning before EKS (spec §105). Plan phases P0–P12 below map onto spec phases in §4. |
| D10 | Test environments | Spec §90.1: fixtures → moto → Floci → real sandbox contract suite. No real AWS before P2. |
| D11 | Fixture format | Versioned YAML (`fixture_version: 1`) holding resources, edges with evidence, stacks, services, requirements, an optional pinned DR overlay, and overrides. A JSON Schema is generated from the Pydantic models and checked in CI. |
| D12 | Configuration | All weights, thresholds, correlation groups, scoring, RTO-scope defaults, buffer defaults and the duration catalog are YAML under `apps/api/perpetual/config/defaults/`, loaded into typed models. A project may override them. Freshness policies, alternative-selection limits and cost unit conversions are also versioned configuration. Nothing numeric is hard-coded in rule or engine code. |
| D13 | Cost in v0.1 | `StaticCostProvider` (versioned price table in config) first, then `AWSPricingProvider`. Infracost is optional and post-MVP. |
| D14 | LLM | In v0.1 (revised 2026-10-25, see tracker). LangGraph agents for advisory review, candidate planning, IaC transformation and explanation. "The LLM proposes, the engine verifies" (spec §2). |
| D15 | LLM provider | Replaceable through LangChain's chat-model interface (`init_chat_model`). OpenAI-compatible endpoints (OpenRouter), Anthropic, Bedrock and Ollama as optional extras. Per-role model config. Keys from env or keyring. |
| D16 | Changing infrastructure | Code only: Terraform and Kubernetes manifests (plain, Kustomize, Helm values) in a git worktree, delivered as a branch or PR. Never apply, never merge. Repository-controlled tools run only inside the enforced isolation boundary in spec §61. |
| D17 | Knowledge base | Local SQLite with `sqlite-vec` + FTS5 (hybrid retrieval); local embeddings by default (fastembed). Ships curated DR domain reference docs in `knowledge/domain/` for all in-scope AWS services, plus `knowledge/sources.yaml` (fetched via `perpetual kb sync`), plus dynamic agent `web_search` and `web_fetch` (with sanitized queries) that persist and index fetched documentation for out-of-scope/unmodeled resources into the local KB. |
| D18 | LLM tests | Fake chat model with recorded responses in CI; real-provider evals on demand in `evals/`. |

## 3. Architecture

### 3.1 Pipeline

```text
collectors / importers           (P1b, P2, P2b, P7)
        |  DiscoveredResource, raw facts, observations
        v
normalizers + identity resolution (spec §15, §15.1, §15.3)
        |  ResourceNode with typed properties
        v
edge resolvers                    (spec §14.1, §21, §22)
        |  DependencyEdge + Evidence (basis, correlation group)
        v
override layer                    (spec §23)  <- GraphOverride from CLI / UI / YAML
        |
        v
graph snapshot (NetworkX)         (spec §17, §18)
        |
        +--> stacks + services + RTO scope   (spec §24, §24.1, §25)
        |
        +--> rule packs: findings + RecoveryMechanism (DR overlay)  (spec §27.1, §28)
        |        +--> advisor agent (LLM): proposals -> review queue / user  (spec §28.2)
        v
simulator: impact pass, recovery pass  (spec §43, §44)
        |
        v
recovery planner: actions -> DAG -> buffer -> RTO; RPO  (spec §47–§51)
        |
        v
optimizer + cost + remediation    (spec §54–§60)
        |        <--> planner agent (LLM): candidate proposals, evaluated here  (spec §56.1)
        v
DR spec (user approves)           (spec §56.2)
        |
        +--> transformer agent (LLM): edits Terraform + K8s in a worktree   (spec §61)
        |        -> verification: plan -> planned graph -> re-assess, re-simulate  (spec §61.1)
        |        -> branch / PR (code only)                                   (spec §62)
        +--> companion Terraform (no IaC repo or no LLM)                      (spec §62.1)
        +--> runbook generator                                                (spec §63, §64)

Agents read engine results and the knowledge base + skills (spec §69). The engine never calls an agent.
```

### 3.2 Packages

```text
apps/api/perpetual/
  models/          Pydantic domain models, enums, status vocabulary. No I/O.
  config/          typed config loading + defaults/*.yaml (weights, catalog, scope, buffer)
  ids/             canonical resource IDs (spec §15)
  fixtures/        fixture schema, loader, validator
  persistence/     SQLAlchemy models, repositories, Alembic migrations
  collectors/      AWS + Kubernetes + CloudTrail + flow-log readers. Collect only.
  importers/       Terraform JSON, recorded AWS responses
  normalization/   raw -> ResourceNode, typed properties, identity resolution
  evidence/        edge resolvers, combination function, fingerprints
  graph/           snapshot builder, overrides, traversal helpers
  stacks/          grouping, services, RTO scope
  rules/           rule packs per service + cross/ (findings, mechanisms, options, actions)
  simulator/       scenarios, two-pass simulation, reason chains
  recovery/        duration catalog, DAG builder, buffer, RTO, RPO
  optimizer/       candidates, Pareto, remediation
  costing/         CostProvider implementations
  iac/             resource-to-code mapping, worktrees, transformation runs, verification, companion templates
  llm/             provider abstraction, LangGraph agents (advisor, planner, transformer, explainer), guardrails, call log
  knowledge/       knowledge-base ingestion (shipped domain docs, sources.yaml, user docs, agent web-fetch) and hybrid retrieval
  runbooks/        failover / failback generator
  api/             FastAPI routes, static UI serving
  cli/             Typer commands
skills/            shipped DR skills (SKILL.md + references)
knowledge/         domain/ (shipped AWS service DR domain docs) + sources.yaml (public reference URLs)
evals/             real-provider evaluation suite
```

### 3.3 Import contracts (import-linter)

- `models`, `ids`, `config` import nothing else from `perpetual`.
- `collectors` must not import `rules`, `simulator`, `recovery`, `optimizer` (spec §102 rule 2).
- `normalization` must not import `api` or `cli` (rule 3).
- `rules` must not import `collectors` or any LLM code (rule 4).
- `simulator` must not import `collectors` or `importers` (rule 5).
- `optimizer` gets options only through the rule-pack protocol (rule 6).
- Nothing below `api` and `cli` imports them (rule 1).
- Only `llm` imports LangChain or LangGraph. Engine and deterministic pipeline packages (`rules`, `simulator`, `recovery`, `optimizer`, `costing`, `iac`, `graph`, `evidence`, `stacks`, `normalization`, `importers`) never import `llm`; agents call the engine, not the other way round (rule 11).

### 3.4 Invariants to test from the start

- Edge direction is always dependent → dependency.
- Missing evidence → `UNKNOWN`, never PASS or `READY`.
- Every traversal terminates on cycles.
- No secret values, env values, raw CloudTrail events or raw flow records are persisted. A test scans the database after the fixture and log suites for planted canary strings.
- RTO, RPO and plans exist only per stack. No API or CLI output reports a per-resource RTO as a result.
- A stack cannot be `READY` while a low-confidence required-path edge is unreviewed, or while a blocking advisory item is unresolved.
- No LLM output changes a state, number or verdict without verification or user confirmation. Tests run every LLM stage with a fake model that returns hostile output (false claims, missing citations, invalid schemas) and assert nothing upgrades.
- Transformation never runs a command outside its allowlist; a test asserts `apply`, `destroy`, `state` and `kubectl apply` are unreachable.
- Planned changes replace managed facts and invalidate stale operational proof; incomplete scans never prove absence (§15.4, §76.1).
- Readiness follows the ordered decision table (§31); design PASS is never presented as observed READY.
- Evaluation/approval/report hashes bind the exact inputs and output tree; stale approvals cannot resume or deliver.
- Alternative dependencies preserve ALL/ANY/quorum semantics; ambiguous observation groups are never treated as redundancy or exact evidence.
- Missing cost inputs/prices stay unknown; all enforced targets use range comparisons, including budget.
- The command runner enforces process/filesystem/network/credential isolation; an allowed Terraform command cannot escape through executable data sources or plugins.

### 3.5 Evidence-to-result coverage

This matrix defines ownership of v0.1 support. During P0/P2, encode the concrete resource types, required API operation families, typed properties, rule IDs, action types and metric units in a coverage registry. CI fails when an enabled rule or estimator lacks a producer, a supported mechanism lacks an action/catalog mapping, or a declared service has no fixture. Unsupported API operations produce explicit coverage limitations. Every row needs healthy, blocked and unknown fixtures; collector facts additionally need moto/recorded tests and opt-in AWS contracts where emulators cannot prove behavior.

| Capability | Collection / typed normalization | Rules / mechanisms | Recovery and estimation | Validation owner |
|---|---|---|---|---|
| ECS, EC2/ASG, Lambda and artifacts/layers | P0-04, P1b-03, P2-02/03/06 | P4-02 | P6-01, P9-01/03; data-bearing volumes P8-01 | P2-09/10, P4-02, P10-08 |
| RDS/Aurora, S3, AWS Backup | P0-04, P2-04/12 | P4-03 | P6-01, P8-01, P9-01/03 | P2-09/10, P5-04, P8-01 |
| Initial DynamoDB: tables, PITR/backups, replicas, indexes, KMS | P0-04, P2-04/12 | P4-08 | P6-01, P8-01, P9-01/03 | P2-09/10, P4-08, P8-01 |
| EFS, EBS volumes/snapshots and AMIs | P0-04, P2-02/04/12 | P4-02/08, P7-05 | P6-01, P7-06, P8-01, P9-03 | P2-09/10, P4-08, P7-08 |
| SQS/SNS endpoint and message durability | P0-04, P2-03/06/12 | P4-02 | P6-01, P8-01, P9-01/03 | P2-09/10, P4-02, P8-01 |
| ECR image metadata, Secrets/SSM metadata, IAM, KMS | P0-04, P2-03/06 | P4-02/04 | P6-01, P9-01/03; content availability is an observed prerequisite | P2-09/10, P5-04, P10-08 |
| VPC/network, ALB/NLB, Route 53/ARC, CloudFront, ACM, WAF | P0-04, P2-01/02/06 | P4-03/04 | P6-01, P9-01/03 | P2-09/10, P5-04 |
| CloudWatch Logs (scope-aware) | P0-04, P2-03 | P4-03/05 | P6-01 if in scope, P9-03 | P2-09/10, P4-03 |
| EKS and Kubernetes workloads/storage | P7-01/02/03, new typed properties in P7 | P7-05 with P4-08 EFS reuse | P7-06, P8-01, P9-01/03 | P7-08/09, P10-08 |
| Quota limits/headroom and Region/feature availability | P2-12, typed fact models P0-04 | P4-04 | Capacity prerequisites in P6/P9; unknown headroom cannot pass | P2-12, P4-04 |
| Replication and usage metrics | P2-12, typed units/windows/freshness | P4 rules, P2-13 coverage | P8-01 RPO, P9-09 workloads, P9-03 costs | P2-12/13, P8-01, P9-09 |

Milestone ordering is explicit even where task IDs were appended: P0-15 precedes persisted evaluations; P1-18 precedes the P1 exit; P1b-15 precedes the importer exit; P2-12/13 precede P2-11 and P4; P2b-09 precedes P2b-08; P9-09 precedes costing; P9-08 pins approval inputs; P10-09 precedes any repository tool execution and P10-03. Task completion includes applicable CLI/API/UI contracts and §90.2 regression coverage.

## 4. Phase map

| Plan phase | Spec §99 phase | Content | Real AWS |
|---|---|---|---|
| P0 | Phase 0 | Foundation, models, fixtures, persistence, graph, overrides, CLI | no |
| P1 | Phase 1 | Simulator, mechanisms, recovery DAG, buffer, RTO (fixtures) | no |
| P1b | Phase 1b | Terraform importer, API, `perpetual ui`, graph editor, simulation view | no |
| P2 | Phase 2 | Live AWS discovery for the ECS slice, SG/IAM/reference evidence | checkpoint |
| P2b | Phase 2b | CloudTrail and VPC Flow Logs | checkpoint |
| P3 | Phase 3 | Stack and service discovery | no |
| P3b | Phase 3b | LLM foundation: providers, LangGraph, knowledge base, skills, guardrails, explainer | no |
| P4 | Phase 4 | DR rule packs for the ECS slice + cross-cutting rules + advisory review | no |
| P5 | Phase 5 | Simulation on discovered stacks, Fail Region UX | checkpoint |
| P6 | Phase 6 | Recovery DAG from rule packs on live data | no |
| P7 | §106 + EKS parts of 2/4 | EKS vertical slice incl. Kubernetes + NetworkPolicies | checkpoint |
| P8 | Phase 7 | RPO | no |
| P9 | Phase 8 | Optimizer, cost, LLM candidate planner, DR spec | no |
| P10 | Phase 9 | IaC transformation + verification + companion fallback | no |
| P11 | Phase 10 | Runbooks + failback | no |
| P12 | §100 | MVP hardening and v0.1 release | checkpoint |

Every task meets the spec §103 definition of done: typed model, implementation, unit tests, fixture, API and UI exposure where applicable, error handling, docs.

## 5. Phases

### P0 — Engine foundation (CLI only)

Spec: §15, §15.1–15.3, §16–§23, §24, §26, §27.1 (models), §30.1, §49 (model), §99 Phase 0, §104.

| ID | Task |
|---|---|
| P0-01 | Repo skeleton: `mise.toml` (python, uv, node, terraform + tasks `lint`, `fmt`, `typecheck`, `test`, `check`), root `pyproject.toml` (uv workspace + Hatchling package pointing at `apps/api/perpetual` for `uv tool install .`), `apps/api/pyproject.toml`, `__init__.py` stubs for all §3.2 subpackages, ruff, mypy strict, pytest config, `.gitignore`. |
| P0-02 | `import-linter` contracts (§3.3). |
| P0-03 | GitHub Actions: lint, typecheck, import contracts, tests on Linux. |
| P0-04 | Domain models in `models/` for every type in spec §104, plus `StackService`, `GraphOverride`, `BufferPolicy`, `DependencyGroup`, `ScanCoverage`, `EvaluationInput`, `WorkloadProfile`, `CostEstimate`, deployment prerequisite and verification-stage models, status enums (spec §30.1). Typed properties (discriminated union) for first-slice types: Route 53 zone/record, WAF web ACL, ALB, listener, target group, ECS cluster/service/task definition, EC2 instance/Auto Scaling group/launch template/AMI, Lambda function/event-source mapping, SQS queue, SNS topic/subscription, ECR repository, Secrets Manager secret, SSM parameter, KMS key, RDS instance/Aurora cluster, DynamoDB table/replica/backup, EFS filesystem/replication, EBS volume/snapshot, S3 bucket, VPC, subnet, security group, IAM role/policy, CloudWatch log group, plus out-of-scope CI/CD types (`CodePipelineProperties`), `ExternalResourceProperties` (spec §15.2) and fallback `GenericResourceProperties`; typed quota, availability and metric facts plus supporting-service properties required by §3.5. |
| P0-05 | `ids/`: canonical IDs, global IDs, planned `tf:` IDs, parsing and tests. |
| P0-06 | `config/`: typed loading of defaults (evidence weights, correlation groups, thresholds, scoring, RTO-scope defaults, buffer defaults) with per-project override. |
| P0-07 | `persistence/`: SQLAlchemy models for resources, edges, evidence, graph_overrides, stacks, stack_resources, stack_services, recovery_mechanisms, resource_versions, dependency_groups, scan_coverage, evaluation_inputs (+ projects, scans). Initial Alembic migration. Repositories scoped by `project_id`. SQL compilation / dialect test asserting all models and migrations compile cleanly against both `sqlite` and `postgresql` dialects (spec §71.1). |
| P0-08 | `fixtures/`: fixture format v1, loader, validator, JSON Schema export, `perpetual fixtures validate`. |
| P0-09 | `evidence/`: combination function with correlation groups (pluggable), evidence fingerprints (spec §22, §23). |
| P0-10 | `graph/overrides`: apply confirm/reject/add/edit edge and add/edit node overrides; rescan merge rules; orphan detection; YAML export/apply. |
| P0-11 | `graph/`: snapshot → NetworkX `MultiDiGraph` with derived traversal projections preserving typed parallel edges and dependency groups; dependency closure, ancestors, cycle detection; never raises on cycles. |
| P0-12 | CLI: `perpetual graph --fixture NAME [--stack S] [--unreviewed] [--json]`, `perpetual graph overrides export|apply`. |
| P0-13 | Fixtures: `ecs-broken` (spec §87), `ecs-remediated` (§88), and unit fixtures `cycle`, `shared-node`, `deep-path`. |
| P0-14 | Update `CLAUDE.md` commands to match what exists. |
| P0-15 | Immutable snapshot/evaluation manifests (§56.3, §76.1), deterministic canonical hashes and revision references; preserve provenance and distinguish absent/unknown/null. Fixture support for coverage, groups, input versions and workload profiles. Later stages extend the manifest without mutating historical evaluations. |

Exit: `perpetual graph --fixture ecs-broken` prints the dependency graph and DR overlay.

### P1 — Simulation and recovery core (CLI only)

Spec: §24.1, §27.1, §28, §30.1, §43–§50, §52, §92, §93.

| ID | Task |
|---|---|
| P1-01 | `DRRulePack` protocol and registry; `rules/cross/` skeleton. |
| P1-02 | Minimal `resolve_mechanism` for first-slice services from normalized properties and `replicates_to` / `backed_up_by` edges. Strict "reproducible" check (spec §27.1). A fixture's pinned overlay is compared with resolver output in tests. |
| P1-03 | RTO scope classification with defaults and overrides (spec §24.1). |
| P1-04 | `FailureScenario` hierarchy and dispatch on `kind`. `AZFailure` and `LogicalCorruption` exist as types and return a clear "not supported in v0.1" error. |
| P1-05 | Impact pass: seeding, operational dependency groups (ALL/ANY/quorum, §19.1), skipping structural/replication/backup edges, thresholds, possible impact and out-of-scope handling. |
| P1-06 | Recovery pass over the DR overlay: memoised, cycle-safe, ALL worst-state and ANY/quorum evaluation, selected dependency paths, control-plane rule; target violations do not make mechanisms BLOCKED. |
| P1-07 | Stack state and readiness composition table (§30.1, §31), finding effect classification, coverage/review/attribution/advisory gates; missing RPO/cost evaluators never imply PASS. Preserve observed vs design evaluation kind. |
| P1-08 | Reason chains from stack root to root cause, crossing into the overlay (spec §44, §46). |
| P1-09 | Duration catalog v1: loader, bucket matching, `catalog_version` and bucket in `basis`, generic fallback action types (`generic_promote_counterpart`, `generic_restore_from_backup`, `generic_rebuild_from_iac`), per-resource project duration overrides, `None` for missing entries. |
| P1-10 | `recovery_actions()` for first-slice mechanisms with phases and refined prerequisites, plus fallback action synthesis for user-confirmed mechanisms on unmodeled resources. |
| P1-11 | DAG builder: phase-template default edges, refinement, `decide` action, `stack_validation` action, acyclicity error. |
| P1-12 | Buffer: handoff on manual/semi-automatic actions, stack validation, contingency. |
| P1-13 | RTO: longest path for low/expected/high, UNKNOWN propagation with partial path, breakdown (critical path vs parallel). |
| P1-14 | Target comparison PASS/FAIL/UNCERTAIN. |
| P1-15 | Persist simulations, impacts, mechanisms, plans, actions. |
| P1-16 | CLI: `perpetual simulate STACK --fixture F --failure region:R [--json]`, `perpetual plan STACK ...` (plan + RTO breakdown). |
| P1-17 | Tests: spec §92; §93 (40, 48, 49.5); cycle → UNKNOWN; missing DR KMS → BLOCKED; `unknown` mechanism never RECOVERABLE; out-of-scope BLOCKED does not change stack; review gate. |
| P1-18 | Dependency-group member selection for recovery DAGs (§19.1): consistent chosen paths, shared prerequisites, bounded deterministic search and non-optimal/unknown reporting; fixture tests for ALL/ANY/quorum, unknown members, selected-path gates, and readiness decision-table precedence (§90.2). |

Exit: `perpetual simulate checkout --fixture ecs-broken --failure region:ap-south-1` reproduces spec §87 (NOT DR READY, blockers, RTO range); `ecs-remediated` shows RECOVERABLE.

### P1b — Importers, API and UI

Spec: §10, §15.1, §71.1, §72, §78, §80–§84.

| ID | Task |
|---|---|
| P1b-01 | Terraform saved-plan/state JSON importer (§15.4): configuration references, root/workspace-qualified planned IDs, masks for unknown/sensitive values, provider/account mappings, format validation and explicit re-keying; reject UI event streams as plan documents. |
| P1b-02 | Identity resolution across sources (spec §15.1); conflicts kept as separate evidence. |
| P1b-03 | Normalizers for first-slice types reading recorded AWS API responses (`fixtures/aws/`); `perpetual import-aws-fixture`. P2 collectors reuse these normalizers. |
| P1b-04 | FastAPI app: projects, imports/scans, resources, graph (with filters), edges (POST/PATCH/DELETE, confirm, reject), nodes, overrides (list/import), stacks, services, requirements, simulate, recovery plan. Error model. |
| P1b-05 | OpenAPI → `packages/schemas` TypeScript types; CI fails on drift. |
| P1b-06 | `perpetual ui`: serve API + static UI; bind `127.0.0.1`; `--host` needs `--i-know-there-is-no-auth` and prints a warning. |
| P1b-07 | Web scaffold: Vite, React, TS strict, Tailwind, shadcn/ui, TanStack Router + Query, eslint. |
| P1b-08 | Graph editor view: whole graph, grouping by stack/service/VPC with collapse, filters, ELK layout, edge style by basis, muted out-of-scope nodes. |
| P1b-09 | Graph editor review: evidence panel, review queue (required paths first, then lowest confidence), contradictions and unobserved lists, confirm/reject/edit. |
| P1b-10 | Graph editor edits: add edge by drag, delete edge, add external/placeholder node, change stack/service membership and RTO scope; dependency-group editing/validation and ambiguity resolution; each edit asks for an optional reason. |
| P1b-11 | Home (§80) and stack screen (§81): requirement form, readiness, targets vs predicted, evaluation kind/time, coverage and stale reasons. |
| P1b-12 | Simulation view (§83): fail Region, state colours, result panel, reason chain, RTO breakdown, review-gate banner linking to the queue. |
| P1b-13 | Packaging: UI build copied into the wheel; `uv tool install .` then `perpetual ui` works on a clean machine. |
| P1b-14 | One Playwright smoke test: load fixture, confirm an edge, simulate. |
| P1b-15 | Authoritative planned snapshot builder (§15.4): create/update/delete/replace/no-op/moved-address semantics, operational-evidence invalidation, override revalidation and unmanaged context. Tests for changed live values, stale edges, deletion/replacement, unknown fields and duplicate addresses across roots. P10 extends it with rendered deployment inventories. |

Exit: import fixture → review and correct the graph in the UI → simulate on it.

### P2 — AWS discovery (ECS slice)

Spec: §9, §11–§13, §14.1 (security groups, IAM), §21, §22, §65–§67, §76, §90.1, §97.

| ID | Task |
|---|---|
| P2-01 | Collector protocol; per-account sessions (primary + DR account, profile or role); region iteration + global/`us-east-1` pass (`Route 53`, `IAM`, `CloudFront`, `WAFv2 Scope=CLOUDFRONT`, `ACM in us-east-1`); pagination; throttling retries; per-collector failure → scan `partial`. |
| P2-02 | Collectors: EC2 (instances, Auto Scaling groups, launch templates, AMIs) / VPC (VPC, subnets, route tables, NAT, IGW, endpoints, TGW attachments, ENIs, security groups), ELB, Route 53 (incl. health checks, ARC if present), CloudFront distributions/origins, ACM, WAF (WAFv2 `REGIONAL` and `CLOUDFRONT` Web ACLs, rule groups, associations). |
| P2-03 | Collectors: ECS, Lambda (functions, layers, event-source mappings), ECR (incl. replication config and image digest/manifest metadata), SQS (queues, DLQs, policies), SNS (topics, subscriptions, policies), Secrets Manager (metadata, replication), SSM parameters (metadata), KMS (incl. multi-Region), IAM roles/policies, CloudWatch Logs (log groups, KMS, retention, subscription filters). |
| P2-04 | Collectors: RDS/Aurora (instances, clusters, replicas, snapshots), S3 (versioning, replication), AWS Backup, EBS volumes/snapshots, EFS filesystems/mount targets/replication/backup metadata, DynamoDB tables/PITR/backups/replicas/indexes/KMS. Typed normalization and absence/coverage records per §3.5. |
| P2-05 | Supplementary: Resource Explorer, AWS Config items and relationships. |
| P2-06 | Edge resolvers: security groups (spec §14.1 rules incl. wide-open handling), IAM (identity and resource policies, wildcard handling), configuration references (task-definition secrets, Lambda/ECS env/endpoint matching that persists only the matched fact, `ASG → LaunchTemplate → AMI → EBS Snapshot → KMS Key`, `Lambda → S3 code bucket / ECR image / Lambda Layer`, event-source mappings, SNS→SQS/Lambda subscriptions, WAF→ALB/CloudFront associations, EC2 instance profiles/volumes), Config relationships. |
| P2-07 | `perpetual scan --profile P --region R --dr-region R2 [--dr-profile P2]`; `POST /projects/{id}/scans`; scan status and errors in UI. |
| P2-08 | `docs/iam/perpetual-readonly.json` minimal read-only policy, with optional log-reading statements. |
| P2-09 | Tests: moto unit tests per collector; `docker-compose.yml` with Floci and PostgreSQL (for live Postgres migration verification, spec §71.1, §73); `examples/ecs-rds/` Terraform applied to Floci and scanned in CI. Check Floci support per operation first and record gaps in the decision log. |
| P2-10 | Contract suite skeleton `tests/contract/` (opt-in marker, create/destroy with guaranteed teardown); redaction of recorded responses into `fixtures/aws/`. |
| P2-11 | Real-AWS checkpoint: scan the sandbox account → normalized graph. |
| P2-12 | Service Quotas limits and available usage/headroom, EC2 instance-type offerings, versioned Region/feature capability facts, and CloudWatch Metrics reader for replication lag, copy/replication status and usage inputs. Preserve units/windows/latest-sample time, missing samples and access failures; never substitute Logs for Metrics. Fixtures, read-only IAM statements and opt-in contracts for each fact family. |
| P2-13 | Coverage/freshness evaluation (§76.1): operation-level completeness, pagination/detail failures, historical carry-forward, confirmed absence, atomic snapshot publication, primary/DR skew and verdict gates. CLI/API/UI coverage reports and regression cases in §90.2; required before the P2 real-AWS checkpoint. |

Exit: scan AWS account → normalized graph.

### P2b — Observed dependency evidence

Spec: §14.1 (CloudTrail, flow logs, persistence, contradictions), §16, §22, §65, §66, §90.1.

| ID | Task |
|---|---|
| P2b-01 | Synthetic log generator `fixtures/logs/` (CloudTrail S3 layout, flow logs v2 and v5, edge cases). |
| P2b-02 | CloudTrail reader: S3, CloudTrail Lake, Athena; `LookupEvents` fallback; window config (default 30 days). |
| P2b-03 | Principal → compute mapping (ECS task role, Lambda execution role, IRSA, Pod Identity, EC2 instance profile rolled up to Auto Scaling group); exact attribution requires unique time-valid evidence, otherwise preserve candidate sets (§14.1). |
| P2b-04 | Flow-log reader: S3 and CloudWatch Logs; time-aware ENI resolution (current ENIs, Config history, CloudTrail ENI events, incl. EC2/ASG ENIs and Lambda VPC Hyperplane ENIs); v5 fields; ephemeral-port folding; dropped-flow counts; ambiguous shared ENIs never yield exact caller evidence. |
| P2b-05 | Observations: aggregate-only persistence; canary test proving raw data is not stored. |
| P2b-06 | Contradiction and "unobserved in window" flags; external-node proposals from unknown destinations. |
| P2b-07 | Coverage report (trails, data events, flow-log destinations) in CLI and UI. |
| P2b-08 | Real-AWS checkpoint: real CloudTrail and flow logs → observed edges. |
| P2b-09 | Ambiguous observation model and review flow (§14.1): aggregate once per candidate set, no copied counts or exact-edge confidence uplift, explicit attribution gate, user resolution and evidence audit. Tests for shared task roles, Lambda ENIs, ENI reuse and exact positive attribution; run before P2b checkpoint. |

Exit: every edge shows its basis; permitted-but-unobserved edges and observed-but-not-permitted flows are listed for review.

### P3 — Stack and service discovery

Spec: §24, §24.1, §25.

| ID | Task |
|---|---|
| P3-01 | Grouping signals: tags, Terraform modules, WAF → ALB → target group → ECS / EC2 / ASG / Lambda chains, SNS → SQS → Lambda event chains, connectivity (including observed), IAM references. |
| P3-02 | Service suggestion inside a stack (ECS services, EC2 / Auto Scaling groups, Lambda; Deployments in P7) with resources only they use; shared resources stay at stack level. |
| P3-03 | Root resources and dependency closure; shared resources across stacks. |
| P3-04 | Manual editing of stacks and services in CLI (`perpetual stacks ...`) and UI; stored as overrides. |
| P3-05 | Discovery confidence. |

Exit: Perpetual understands "checkout" as one stack with its services, not unrelated resources.

### P3b — LLM foundation

Spec: §2, §69, §70.

| ID | Task |
|---|---|
| P3b-01 | Provider abstraction: config schema (default + per-role + embeddings), `init_chat_model`, OpenAI-compatible/OpenRouter, Anthropic, Bedrock, Ollama extras; capability probe (tool calling, structured output); `perpetual llm configure|test`. |
| P3b-02 | LangGraph runtime: graph base, tool registry over read-only engine APIs + `web_search` and `web_fetch` tools for unmodeled/out-of-scope resources (persisting fetched docs into the local KB), SQLite checkpointer, interrupts, Pydantic-validated outputs with one retry then fail closed. |
| P3b-03 | Fake chat model + recorded-response and recorded `web_search`/`web_fetch` harness; hostile-output and prompt-injection web-page fixtures (no live network in CI). |
| P3b-04 | Guardrails: per-project opt-in notice, redaction pass, query sanitization for `web_search`/`web_fetch` (generic AWS/DR/Terraform terms only; `--offline` / `allow_web_research` toggle), untrusted web-content sanitization (strip prompt injections before KB indexing), `.perpetualignore`, `llm_calls` log, `perpetual llm log`, UI view. |
| P3b-05 | Knowledge base: shipped domain knowledge (`knowledge/domain/` covering ECS, EKS, EC2/ASG, Lambda, RDS/Aurora, DynamoDB, S3, EBS, EFS, SQS, SNS, ECR, Secrets, SSM, KMS, IAM, Route 53, ALB, WAF, CloudWatch Logs, VPC), `knowledge/sources.yaml`, `perpetual kb sync|add|list|show|remove` (+ `GET/DELETE /kb/documents`), automatic ingestion of agent `web_fetch` results (`origin = "agent_web_fetch"`), chunking, sqlite-vec + FTS5 hybrid retrieval, citations by chunk ID. |
| P3b-06 | Skills: format, loader, index, `load_skill` tool, project overrides in `.perpetual/skills/`; first skills for the ECS slice (RDS replica, ECR replication, Secrets replication, KMS multi-Region, S3 CRR, basic DynamoDB/EFS recovery, Route 53 failover, ECS DR service, EC2/ASG + AMI DR, Lambda multi-Region, SQS/SNS DR, WAF Web ACL DR). |
| P3b-07 | Explainer agent (spec §70) in CLI (`perpetual ask`) and UI. |

Exit: `perpetual llm test` passes for a configured provider; the explainer answers "why can't checkout meet 30m?" with cited, engine-sourced numbers.

### P4 — DR rule packs (ECS slice)

Spec: §8.1, §28, §28.1, §29–§32, §41, §91.

| ID | Task |
|---|---|
| P4-01 | Finding model, stable rule-ID registry, rule docs generated to `docs/rules/`. |
| P4-02 | Packs: ECS (§32), EC2/Auto Scaling (§5.3, incl. cross-Region AMI copy + snapshot KMS decryptability), Lambda (§5.4, incl. DR S3 package / ECR image / regional layer availability + event-source mappings), ECR, SQS (§7.1, endpoint recovery vs in-flight message RPO), SNS (§7.1), Secrets/SSM, KMS, IAM. |
| P4-03 | Packs: RDS/Aurora (§41, Multi-AZ ≠ cross-Region), S3, network (VPC, subnets, NAT, routes, endpoints), ALB/NLB, CloudFront origin failover and ACM certificate availability, Route 53 (data-plane vs control-plane, §8.1), WAF (§8, primary-vs-DR Web ACL and rule parity), CloudWatch Logs (§8, §24.1). |
| P4-04 | Cross-cutting rules: XREG-CONFIG-001, XREG-IAM-002, XREG-KMS-003, CTRL-PLANE-001, QUOTA-DR-001, REGION-SVC-001. |
| P4-05 | Readiness dimensions (§30) with UNKNOWN for dimensions without rules; scoring and centralized readiness composition (§31); declare required coverage/freshness for each rule; Observability reports out-of-scope findings and never blocks. |
| P4-06 | `perpetual assess STACK`; findings API; findings tab in UI. |
| P4-07 | Advisory review agent (spec §28.2): typed proposals, citation check, effects on edges/mechanisms/stack state (`advisory_unresolved`), accept/dismiss with fingerprints; `perpetual advise`; UI panel. |
| P4-08 | Initial DynamoDB and EFS packs: current replication/backup posture, KMS/network prerequisites, basic existing-counterpart and backup-restore mechanisms/options, no unsupported replication guarantees. Use P2-04/P2-12 evidence, register actions for P6 and estimates for P8/P9. Fixtures for healthy, blocked and missing-evidence cases. |

Exit: stack assessment produces evidence-backed findings; advisory items appear with citations and can be accepted or dismissed.

### P5 — Simulation on discovered stacks

Spec: §43–§46, §83, §84.

| ID | Task |
|---|---|
| P5-01 | Mechanisms come from rule packs for every first-slice service; DR-side dependencies resolved against the DR Region/account scan. |
| P5-02 | Explainability (§84) for every BLOCKED/UNKNOWN: what, why, evidence, dependents, remediation pointer. |
| P5-03 | Fail Region UX on live data, graph transitions, top blockers. |
| P5-04 | Real-AWS checkpoint: §87 and §88 rebuilt in the sandbox give the same results as the fixtures. |

Exit: Perpetual identifies which stack dependencies survive and why.

### P6 — Recovery DAG on live data

Spec: §47–§50, §52.

| ID | Task |
|---|---|
| P6-01 | `recovery_actions()` for all P4 packs with refined prerequisites. |
| P6-02 | Catalog coverage report: actions without catalog entries (they make RTO UNKNOWN). |
| P6-03 | Shared-resource marking in plans. |
| P6-04 | Recovery tab in UI: DAG view, critical path, buffer lines, targets vs predicted. |

Exit: predicted RTO is architecture-derived for scanned stacks.

### P7 — EKS vertical slice

Spec: §5.2, §14 (Levels 1 and 2), §14.1 (NetworkPolicies), §33–§40, §86, §89, §98, §106.

| ID | Task |
|---|---|
| P7-01 | EKS collectors: clusters, node groups, Fargate profiles, add-ons, Pod Identity associations, OIDC provider (IRSA). |
| P7-02 | `KubernetesCollector` (Level 2): workloads, Services, Ingress/Gateway, PVC/PV/StorageClass, ServiceAccounts, scheduling constraints, image refs, ConfigMap matching without storing values. |
| P7-03 | NetworkPolicy evidence incl. enforcement detection. |
| P7-04 | Services suggested from Deployments/StatefulSets. |
| P7-05 | EKS rule packs: control plane, compute, scheduling, add-ons, identity, images, storage; EBS pack and reuse P4-08 EFS pack with Kubernetes PVC/CSI integration. |
| P7-06 | Mechanisms and recovery actions for EKS (cluster, node groups, add-ons, manifests via GitOps if present — in RTO scope per §24.1). |
| P7-07 | Level 1 vs Level 2 confidence; UNKNOWN for Kubernetes workload recovery without credentials (§98). |
| P7-08 | Fixture B (§86) and EKS demo (§89): cluster PASS, application FAIL (no EBS CSI). |
| P7-09 | Real-AWS checkpoint for the EKS demo (kind or EKS in sandbox; decide in the decision log). |

Exit: cluster DR ready while the application is not, because of storage or identity.

### P8 — RPO

Spec: §51, §52.

| ID | Task |
|---|---|
| P8-01 | RPO estimators per mechanism: recovery-point age, replica lag (CloudWatch metrics), S3 replication (RTC metrics if present), DynamoDB replica mode/metrics and backup age, EFS replication/recovery-point evidence, EBS/AMI snapshot age (EC2/EKS), SQS stateful in-flight message RPO vs endpoint recovery (§7.1, §51). Depend on P2-12 metrics and P2-13 freshness; explicit design estimators with versioned assumptions or UNKNOWN for future stores. |
| P8-02 | Stack RPO (worst over selected required in-scope stores), UNKNOWN propagation, contributors, proven stateless case and no reuse of observed lag for proposed replicas. |
| P8-03 | RPO in CLI, API and UI; target comparison. |

Exit: data-store recovery posture contributes to stack RPO.

### P9 — Optimizer, cost and remediation

Spec: §54–§60, §94.

| ID | Task |
|---|---|
| P9-01 | `recovery_options()` in packs; strategy → mechanism mapping per pack (§27). |
| P9-02 | Candidate generation per strategy + bounded variants; current architecture as baseline; prerequisite and conflict rejection. |
| P9-03 | `CostProvider`: `StaticCostProvider` with versioned price table (covering ECS, EKS, EC2/ASG, Lambda, RDS/Aurora, DynamoDB, S3, EBS/EFS, SQS/SNS, ECR, Secrets, KMS, Route 53, ALB, WAF, CloudWatch Logs, NAT/VPC); then `AWSPricingProvider`. Include NLB/CloudFront/ACM and every billable component enabled in §3.5. Cost ranges, line-item deduplication, workload units, price/usage freshness and total-steady-state budget contract (§59.1); missing inputs remain UNKNOWN. Depends on P9-09. |
| P9-04 | Evaluate candidates: DAG, RTO, RPO, readiness and budget range comparison. Feasibility before recommendation; exclude unknown values from dominance, use high bounds for complete-candidate Pareto ranking (§57, §59.1), keep baseline and disclose search limits. Requirement-driven and budget-driven modes; test missing costs, crossing ranges and exact-boundary equality. |
| P9-05 | Remediation planner (§60): re-plan the whole stack per change and explain stack-level deltas. |
| P9-06 | `perpetual optimize STACK --rto --rpo --budget`; Optimize tab in UI. Spec §94 test. |
| P9-07 | LLM candidate planner (spec §56.1): `CandidateProposal` schema, new-option rules (citation, catalog action types, prerequisites), refine loop, deterministic candidates always kept. |
| P9-08 | DR spec (§56.2–56.3): selected candidate, cited rationale, immutable input manifest and canonical approval digest, supersession/freshness checks, Markdown export and approval UI/CLI. Pin declared IaC baseline metadata before approval; P10-01 performs detailed block mapping. Test requirement/scan/override/catalog/base-tree changes and resumed checkpoints. |
| P9-09 | Versioned workload profiles (§59.1): measured quantities from P2-12 or explicit user bounds, units/windows/provenance/expiry, CLI/API/UI editing and cost-input validation. Implement before P9-03; test missing usage, regional prices, shared foundations and total versus incremental/incident cost. |

Exit: deterministic and LLM-proposed candidates can be compared on cost, RTO and RPO, and each demo stack has an approved DR spec.

### P10 — IaC transformation

Spec: §61, §61.1, §62, §62.1, §69.6.

| ID | Task |
|---|---|
| P10-01 | Validate approved IaC roots and baseline manifest (§56.3); detailed resource-to-code mapping for Terraform addresses/files and Kubernetes rendered objects/files, with explicit per-cluster managed inventory. Conflicting root ownership or changed baseline invalidates approval. |
| P10-02 | Worktree/branch management, approved-baseline checks, argument/path allowlist and trusted command runner interface. No shell/arbitrary flags; P10-09 isolation must pass before executing repository-controlled tools. |
| P10-09 | Enforce spec §61 execution isolation before P10-03: no ambient host credentials/mounts, constrained read-only AWS/backend access, read-only backend planning without lock writes, before/after lineage/serial/digest checks, pinned reviewed providers/modules, executable data-source/plugin rejection, network broker, symlink protection, limits/cancellation and sensitive-output/scratch cleanup. Hostile Terraform/plugin fixtures prove denial; no unsandboxed fallback. |
| P10-03 | Transformation agent (LangGraph): locate → plan edits → edit → static checks → plan and import → verify → retry → package. Skills for EKS added (EKS DR via GitOps, EBS snapshot copy). |
| P10-04 | Verification (§15.4, §56.3, §61.1): static checks, secret/path checks, saved `terraform plan -out=<file>` then `terraform show -json <file>`, provenance validation, authoritative planned graph plus rendered manifests, engine re-evaluation and strict PASS target gates. Separate static/design/deployment/observed stages; track seeding/copy/manual prerequisites, modeled future estimates or UNKNOWN. Static-only fallback never claims design verification. Bind reports to exact output-tree/plan hashes. |
| P10-05 | Change delivery: commit per DR spec change, patch file, optional PR via `gh`/`glab`, PR body with before/after, stage-specific verification report, pending prerequisites and exact artifact digest; recheck approval/report validity before delivery; manual steps passed to runbooks. |
| P10-06 | Companion fallback templates (Jinja2) for first-slice mechanisms (incl. ECS, EC2/ASG, Lambda, SQS/SNS, RDS, basic DynamoDB/EFS recovery, S3, ECR, Secrets, KMS, WAF, CloudWatch Logs, Route 53, VPC); `terraform fmt` + `validate` tests. |
| P10-07 | `perpetual transform`; API; UI: diff view, verification report, progress. |
| P10-08 | Evals: transform `examples/ecs-rds` and `examples/eks-rds` from the broken demos; design verification must pass with explicit modeled assumptions and deployment prerequisites; hostile/stale-input/static-only cases stay unverified; metrics recorded. |

Exit: for the broken ECS and EKS demos, `perpetual transform` changes the example Terraform and manifests, design verification passes and modeled targets are met with explicit deployment prerequisites. Observed readiness remains pending until deployment/rescan in P12.

### P11 — Runbooks and failback

Spec: §63, §64.

| ID | Task |
|---|---|
| P11-01 | Failback metadata on mechanisms (`failover_supported`, `failback_supported`, `failback_complexity`, `data_resynchronization_required`). |
| P11-02 | Failover runbook from the recovery DAG (order, owners, manual steps, validation). |
| P11-03 | Failback runbook. |
| P11-04 | Markdown export; CLI, API and UI. |

Exit: failover and failback runbooks generated from the plan for both demo stacks.

### P12 — MVP hardening and v0.1 release

Spec: §65–§68, §96–§98, §100, §109.

| ID | Task |
|---|---|
| P12-01 | Full §100 workflow on the sandbox for the ECS and EKS stacks, including a design-verified transformation PR applied by the user's pipeline, completion of deployment prerequisites and a fresh matching rescan that establishes observed readiness and meets targets; execute all §90.2 release regressions. |
| P12-02 | Security pass: canary tests, Terraform-state redaction (§68), `web_search`/`web_fetch` query sanitization tests, outbound calls limited to AWS, Kubernetes, the configured LLM provider, Terraform providers during `plan`, and sanitized doc lookups when enabled; review of what `llm_calls` shows was sent; re-run P10-09 isolation tests on supported platforms. |
| P12-03 | Structured logging (§96) for scan, collectors, graph, assessment, simulation, optimization. |
| P12-04 | Performance: graph of 5,000 resources and 20,000 edges builds, simulates and renders acceptably. |
| P12-05 | Docs: README, user guide, IAM policy, rule reference, fixture format. |
| P12-06 | Release 0.1.0: version, changelog, tag, install instructions. |

Exit: an engineer installs Perpetual, scans a representative stack and gets an answer like spec §109.

## 6. Post-MVP backlog

Not scheduled. Each needs a decision-log entry before work starts.

- Drift between scans (§77).
- AZ failure and logical-corruption scenarios (§43).
- Drill results and proven RTO/RPO (§53).
- Editing CI pipelines, remote modules, CloudFormation/CDK/Pulumi.
- Learning duration-catalog values and evidence weights from drills and confirmed edges.
- Hosted version: login, PostgreSQL, workers, cross-account role with external ID (§66, §71.1).
- Infracost and CUR cost providers (§58).
- Advanced DynamoDB topology optimization and Aurora Global depth (initial DynamoDB support is P2/P4/P8); ElastiCache, Step Functions and API Gateway rule packs.
- Multi-stack view that de-duplicates shared resources.
