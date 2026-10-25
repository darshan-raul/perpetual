# Perpetual — Implementation Plan

Status: **locked** on 2026-10-25. Progress lives in [TRACKER.md](TRACKER.md). Change this file only through a decision-log entry there.

The product is defined in [spec.md](spec.md) (revision 3). This plan orders the work and fixes the choices the spec leaves open. If this plan and the spec disagree, the spec wins unless a decision-log entry says otherwise.

## 1. Goal

Ship Perpetual v0.1: a local, single-user tool that delivers the MVP workflow in spec §100 for an ECS stack and an EKS stack on AWS.

1. Import Terraform and/or scan AWS.
2. Compute the dependency graph from evidence; the user reviews and edits it.
3. Group resources into a stack and its services; set RTO scope.
4. Enter target Region, RTO, RPO and budget for the stack.
5. Simulate Region failure: stack state, what survives, what fails, why.
6. Calculate one recovery plan, one RTO (with buffer) and one RPO for the stack.
7. Recommend and compare whole-stack DR architectures with cost.
8. Generate companion DR Terraform and failover/failback runbooks.

## 2. Locked decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Names | Product and CLI `perpetual`. Python package `perpetual`. Repo `github.com/darshan-raul/perpetual`. |
| D2 | Source of truth | `spec.md` defines behaviour. This plan defines order and tooling. Section numbers in tasks refer to the spec. |
| D3 | Delivery | Local single-user tool (spec §71.1). `perpetual ui` runs one FastAPI process on `127.0.0.1:8000` that serves the API and the pre-built UI. SQLite by default. No hosting in v0.1. |
| D4 | Toolchain | `mise` pins Python 3.13, `uv`, Node (LTS, build-time only) and Terraform in the repo `mise.toml`. All commands run through `mise run <task>`. |
| D5 | Repo layout | Spec §73, with: a root `pyproject.toml` as a `uv` workspace; the Python package in `apps/api/perpetual/`; the Vite app in `apps/web/`; the UI build copied into `apps/api/perpetual/web/static/` (gitignored) and shipped inside the wheel. |
| D6 | Python stack | Pydantic v2, SQLAlchemy 2 (typed ORM), Alembic **from P0** (the spec defers it to 1b; starting early avoids migration debt), NetworkX, boto3, `kubernetes` client, Typer + Rich for the CLI, httpx, pytest, ruff, mypy `--strict`. |
| D7 | UI stack | Vite, React, TypeScript strict, Tailwind, shadcn/ui, React Flow with ELK layout, TanStack Query, TanStack Router. API types generated from OpenAPI with `openapi-typescript` into `packages/schemas`. |
| D8 | Layer boundaries | Enforced with `import-linter` contracts in CI (§3.3). Not left to review. |
| D9 | Order | Engine first, CLI first (spec §99). ECS vertical slice through simulation and recovery planning before EKS (spec §105). Plan phases P0–P12 below map onto spec phases in §4. |
| D10 | Test environments | Spec §90.1: fixtures → moto → Floci → real sandbox contract suite. No real AWS before P2. |
| D11 | Fixture format | Versioned YAML (`fixture_version: 1`) holding resources, edges with evidence, stacks, services, requirements, an optional pinned DR overlay, and overrides. A JSON Schema is generated from the Pydantic models and checked in CI. |
| D12 | Configuration | All weights, thresholds, correlation groups, scoring, RTO-scope defaults, buffer defaults and the duration catalog are YAML under `apps/api/perpetual/config/defaults/`, loaded into typed models. A project may override them. Nothing numeric is hard-coded in rule or engine code. |
| D13 | Cost in v0.1 | `StaticCostProvider` (versioned price table in config) first, then `AWSPricingProvider`. Infracost is optional and post-MVP. |
| D14 | LLM | Not in v0.1 (spec §69 makes it optional). Backlog. |

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
        |
        v
simulator: impact pass, recovery pass  (spec §43, §44)
        |
        v
recovery planner: actions -> DAG -> buffer -> RTO; RPO  (spec §47–§51)
        |
        v
optimizer + cost + remediation    (spec §54–§60)
        |
        +--> Terraform compiler   (spec §61, §62)
        +--> runbook generator    (spec §63, §64)
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
  terraform/       companion DR Terraform compiler
  runbooks/        failover / failback generator
  api/             FastAPI routes, static UI serving
  cli/             Typer commands
```

### 3.3 Import contracts (import-linter)

- `models`, `ids`, `config` import nothing else from `perpetual`.
- `collectors` must not import `rules`, `simulator`, `recovery`, `optimizer` (spec §102 rule 2).
- `normalization` must not import `api` or `cli` (rule 3).
- `rules` must not import `collectors` or any LLM code (rule 4).
- `simulator` must not import `collectors` or `importers` (rule 5).
- `optimizer` gets options only through the rule-pack protocol (rule 6).
- Nothing below `api` and `cli` imports them (rule 1).

### 3.4 Invariants to test from the start

- Edge direction is always dependent → dependency.
- Missing evidence → `UNKNOWN`, never PASS or `READY`.
- Every traversal terminates on cycles.
- No secret values, env values, raw CloudTrail events or raw flow records are persisted. A test scans the database after the fixture and log suites for planted canary strings.
- RTO, RPO and plans exist only per stack. No API or CLI output reports a per-resource RTO as a result.
- A stack cannot be `READY` while a low-confidence required-path edge is unreviewed.

## 4. Phase map

| Plan phase | Spec §99 phase | Content | Real AWS |
|---|---|---|---|
| P0 | Phase 0 | Foundation, models, fixtures, persistence, graph, overrides, CLI | no |
| P1 | Phase 1 | Simulator, mechanisms, recovery DAG, buffer, RTO (fixtures) | no |
| P1b | Phase 1b | Terraform importer, API, `perpetual ui`, graph editor, simulation view | no |
| P2 | Phase 2 | Live AWS discovery for the ECS slice, SG/IAM/reference evidence | checkpoint |
| P2b | Phase 2b | CloudTrail and VPC Flow Logs | checkpoint |
| P3 | Phase 3 | Stack and service discovery | no |
| P4 | Phase 4 | DR rule packs for the ECS slice + cross-cutting rules | no |
| P5 | Phase 5 | Simulation on discovered stacks, Fail Region UX | checkpoint |
| P6 | Phase 6 | Recovery DAG from rule packs on live data | no |
| P7 | §106 + EKS parts of 2/4 | EKS vertical slice incl. Kubernetes + NetworkPolicies | checkpoint |
| P8 | Phase 7 | RPO | no |
| P9 | Phase 8 | Optimizer, cost, remediation | no |
| P10 | Phase 9 | Terraform compiler | no |
| P11 | Phase 10 | Runbooks + failback | no |
| P12 | §100 | MVP hardening and v0.1 release | checkpoint |

Every task meets the spec §103 definition of done: typed model, implementation, unit tests, fixture, API and UI exposure where applicable, error handling, docs.

## 5. Phases

### P0 — Engine foundation (CLI only)

Spec: §15, §15.1–15.3, §16–§23, §24, §26, §27.1 (models), §30.1, §49 (model), §99 Phase 0, §104.

| ID | Task |
|---|---|
| P0-01 | Repo skeleton: `mise.toml` (python, uv, node, terraform + tasks `lint`, `fmt`, `typecheck`, `test`, `check`), root `pyproject.toml` (uv workspace), `apps/api/pyproject.toml`, ruff, mypy strict, pytest config, `.gitignore`. |
| P0-02 | `import-linter` contracts (§3.3). |
| P0-03 | GitHub Actions: lint, typecheck, import contracts, tests on Linux. |
| P0-04 | Domain models in `models/` for every type in spec §104, plus `StackService`, `GraphOverride`, `BufferPolicy`, status enums (spec §30.1). Typed properties (discriminated union) for first-slice types: Route 53 zone/record, ALB, listener, target group, ECS cluster/service/task definition, ECR repository, Secrets Manager secret, SSM parameter, KMS key, RDS instance, S3 bucket, VPC, subnet, security group, IAM role/policy. |
| P0-05 | `ids/`: canonical IDs, global IDs, planned `tf:` IDs, parsing and tests. |
| P0-06 | `config/`: typed loading of defaults (evidence weights, correlation groups, thresholds, scoring, RTO-scope defaults, buffer defaults) with per-project override. |
| P0-07 | `persistence/`: SQLAlchemy models for resources, edges, evidence, graph_overrides, stacks, stack_resources, stack_services, recovery_mechanisms (+ projects, scans). Initial Alembic migration. Repositories scoped by `project_id`. |
| P0-08 | `fixtures/`: fixture format v1, loader, validator, JSON Schema export, `perpetual fixtures validate`. |
| P0-09 | `evidence/`: combination function with correlation groups (pluggable), evidence fingerprints (spec §22, §23). |
| P0-10 | `graph/overrides`: apply confirm/reject/add/edit edge and add/edit node overrides; rescan merge rules; orphan detection; YAML export/apply. |
| P0-11 | `graph/`: snapshot → NetworkX `DiGraph`; dependency closure, ancestors, cycle detection; never raises on cycles. |
| P0-12 | CLI: `perpetual graph --fixture NAME [--stack S] [--unreviewed] [--json]`, `perpetual graph overrides export|apply`. |
| P0-13 | Fixtures: `ecs-broken` (spec §87), `ecs-remediated` (§88), and unit fixtures `cycle`, `shared-node`, `deep-path`. |
| P0-14 | Update `CLAUDE.md` commands to match what exists. |

Exit: `perpetual graph --fixture ecs-broken` prints the dependency graph and DR overlay.

### P1 — Simulation and recovery core (CLI only)

Spec: §24.1, §27.1, §28, §30.1, §43–§50, §52, §92, §93.

| ID | Task |
|---|---|
| P1-01 | `DRRulePack` protocol and registry; `rules/cross/` skeleton. |
| P1-02 | Minimal `resolve_mechanism` for first-slice services from normalized properties and `replicates_to` / `backed_up_by` edges. Strict "reproducible" check (spec §27.1). A fixture's pinned overlay is compared with resolver output in tests. |
| P1-03 | RTO scope classification with defaults and overrides (spec §24.1). |
| P1-04 | `FailureScenario` hierarchy and dispatch on `kind`. `AZFailure` and `LogicalCorruption` exist as types and return a clear "not supported in v0.1" error. |
| P1-05 | Impact pass: seeding, spread over requires edges, skipping `replicates_to`/`backed_up_by`, thresholds, `possible_impact`, out-of-scope handling. |
| P1-06 | Recovery pass over the DR overlay: memoised, cycle-safe, `worst()` ordering, DR-side dependencies, control-plane rule for global services. |
| P1-07 | Stack state mapping and the review gate (`UNKNOWN`, reason `graph_not_reviewed`). |
| P1-08 | Reason chains from stack root to root cause, crossing into the overlay (spec §44, §46). |
| P1-09 | Duration catalog v1: loader, bucket matching, `catalog_version` and bucket in `basis`, `None` for missing entries. |
| P1-10 | `recovery_actions()` for first-slice mechanisms with phases and refined prerequisites. |
| P1-11 | DAG builder: phase-template default edges, refinement, `decide` action, `stack_validation` action, acyclicity error. |
| P1-12 | Buffer: handoff on manual/semi-automatic actions, stack validation, contingency. |
| P1-13 | RTO: longest path for low/expected/high, UNKNOWN propagation with partial path, breakdown (critical path vs parallel). |
| P1-14 | Target comparison PASS/FAIL/UNCERTAIN. |
| P1-15 | Persist simulations, impacts, mechanisms, plans, actions. |
| P1-16 | CLI: `perpetual simulate STACK --fixture F --failure region:R [--json]`, `perpetual plan STACK ...` (plan + RTO breakdown). |
| P1-17 | Tests: spec §92; §93 (40, 48, 49.5); cycle → UNKNOWN; missing DR KMS → BLOCKED; `unknown` mechanism never RECOVERABLE; out-of-scope BLOCKED does not change stack; review gate. |

Exit: `perpetual simulate checkout --fixture ecs-broken --failure region:ap-south-1` reproduces spec §87 (NOT DR READY, blockers, RTO range); `ecs-remediated` shows RECOVERABLE.

### P1b — Importers, API and UI

Spec: §10, §15.1, §71.1, §72, §78, §80–§84.

| ID | Task |
|---|---|
| P1b-01 | Terraform importer for `terraform show -json` state and plan: resources, addresses, references → `referenced` evidence, planned IDs, re-keying. |
| P1b-02 | Identity resolution across sources (spec §15.1); conflicts kept as separate evidence. |
| P1b-03 | Normalizers for first-slice types reading recorded AWS API responses (`fixtures/aws/`); `perpetual import-aws-fixture`. P2 collectors reuse these normalizers. |
| P1b-04 | FastAPI app: projects, imports/scans, resources, graph (with filters), edges (POST/PATCH/DELETE, confirm, reject), nodes, overrides (list/import), stacks, services, requirements, simulate, recovery plan. Error model. |
| P1b-05 | OpenAPI → `packages/schemas` TypeScript types; CI fails on drift. |
| P1b-06 | `perpetual ui`: serve API + static UI; bind `127.0.0.1`; `--host` needs `--i-know-there-is-no-auth` and prints a warning. |
| P1b-07 | Web scaffold: Vite, React, TS strict, Tailwind, shadcn/ui, TanStack Router + Query, eslint. |
| P1b-08 | Graph editor view: whole graph, grouping by stack/service/VPC with collapse, filters, ELK layout, edge style by basis, muted out-of-scope nodes. |
| P1b-09 | Graph editor review: evidence panel, review queue (required paths first, then lowest confidence), contradictions and unobserved lists, confirm/reject/edit. |
| P1b-10 | Graph editor edits: add edge by drag, delete edge, add external/placeholder node, change stack/service membership and RTO scope; each edit asks for an optional reason. |
| P1b-11 | Home (§80) and stack screen (§81): requirement form, readiness, targets vs predicted. |
| P1b-12 | Simulation view (§83): fail Region, state colours, result panel, reason chain, RTO breakdown, review-gate banner linking to the queue. |
| P1b-13 | Packaging: UI build copied into the wheel; `uv tool install .` then `perpetual ui` works on a clean machine. |
| P1b-14 | One Playwright smoke test: load fixture, confirm an edge, simulate. |

Exit: import fixture → review and correct the graph in the UI → simulate on it.

### P2 — AWS discovery (ECS slice)

Spec: §9, §11–§13, §14.1 (security groups, IAM), §21, §22, §65–§67, §76, §90.1, §97.

| ID | Task |
|---|---|
| P2-01 | Collector protocol; per-account sessions (primary + DR account, profile or role); region iteration; pagination; throttling retries; per-collector failure → scan `partial`. |
| P2-02 | Collectors: EC2/VPC (VPC, subnets, route tables, NAT, IGW, endpoints, TGW attachments, ENIs, security groups), ELB, Route 53 (incl. health checks, ARC if present), ACM. |
| P2-03 | Collectors: ECS, ECR (incl. replication config), Secrets Manager (metadata, replication), SSM parameters (metadata), KMS (incl. multi-Region), IAM roles/policies. |
| P2-04 | Collectors: RDS/Aurora (instances, clusters, replicas, snapshots), S3 (versioning, replication), AWS Backup. |
| P2-05 | Supplementary: Resource Explorer, AWS Config items and relationships. |
| P2-06 | Edge resolvers: security groups (spec §14.1 rules incl. wide-open handling), IAM (identity and resource policies, wildcard handling), configuration references (task-definition secrets, env/endpoint matching that persists only the matched fact), Config relationships. |
| P2-07 | `perpetual scan --profile P --region R --dr-region R2 [--dr-profile P2]`; `POST /projects/{id}/scans`; scan status and errors in UI. |
| P2-08 | `docs/iam/perpetual-readonly.json` minimal read-only policy, with optional log-reading statements. |
| P2-09 | Tests: moto unit tests per collector; `docker-compose.yml` with Floci; `examples/ecs-rds/` Terraform applied to Floci and scanned in CI. Check Floci support per operation first and record gaps in the decision log. |
| P2-10 | Contract suite skeleton `tests/contract/` (opt-in marker, create/destroy with guaranteed teardown); redaction of recorded responses into `fixtures/aws/`. |
| P2-11 | Real-AWS checkpoint: scan the sandbox account → normalized graph. |

Exit: scan AWS account → normalized graph.

### P2b — Observed dependency evidence

Spec: §14.1 (CloudTrail, flow logs, persistence, contradictions), §16, §22, §65, §66, §90.1.

| ID | Task |
|---|---|
| P2b-01 | Synthetic log generator `fixtures/logs/` (CloudTrail S3 layout, flow logs v2 and v5, edge cases). |
| P2b-02 | CloudTrail reader: S3, CloudTrail Lake, Athena; `LookupEvents` fallback; window config (default 30 days). |
| P2b-03 | Principal → compute mapping (task role, IRSA, Pod Identity, instance profile). |
| P2b-04 | Flow-log reader: S3 and CloudWatch Logs; time-aware ENI resolution (current ENIs, Config history, CloudTrail ENI events); v5 fields; ephemeral-port folding; dropped-flow counts. |
| P2b-05 | Observations: aggregate-only persistence; canary test proving raw data is not stored. |
| P2b-06 | Contradiction and "unobserved in window" flags; external-node proposals from unknown destinations. |
| P2b-07 | Coverage report (trails, data events, flow-log destinations) in CLI and UI. |
| P2b-08 | Real-AWS checkpoint: real CloudTrail and flow logs → observed edges. |

Exit: every edge shows its basis; permitted-but-unobserved edges and observed-but-not-permitted flows are listed for review.

### P3 — Stack and service discovery

Spec: §24, §24.1, §25.

| ID | Task |
|---|---|
| P3-01 | Grouping signals: tags, Terraform modules, ALB → target group → ECS chains, connectivity (including observed), IAM references. |
| P3-02 | Service suggestion inside a stack (ECS services, Lambda; Deployments in P7) with resources only they use; shared resources stay at stack level. |
| P3-03 | Root resources and dependency closure; shared resources across stacks. |
| P3-04 | Manual editing of stacks and services in CLI (`perpetual stacks ...`) and UI; stored as overrides. |
| P3-05 | Discovery confidence. |

Exit: Perpetual understands "checkout" as one stack with its services, not unrelated resources.

### P4 — DR rule packs (ECS slice)

Spec: §8.1, §28, §28.1, §29–§32, §41, §91.

| ID | Task |
|---|---|
| P4-01 | Finding model, stable rule-ID registry, rule docs generated to `docs/rules/`. |
| P4-02 | Packs: ECS (§32), ECR, Secrets/SSM, KMS, IAM. |
| P4-03 | Packs: RDS (§41, Multi-AZ ≠ cross-Region), S3, network (VPC, subnets, NAT, routes, endpoints), ALB, Route 53 (data-plane vs control-plane, §8.1). |
| P4-04 | Cross-cutting rules: XREG-CONFIG-001, XREG-IAM-002, XREG-KMS-003, CTRL-PLANE-001, QUOTA-DR-001, REGION-SVC-001. |
| P4-05 | Readiness dimensions (§30) with UNKNOWN for dimensions without rules; scoring (§31); Observability reports out-of-scope findings and never blocks. |
| P4-06 | `perpetual assess STACK`; findings API; findings tab in UI. |

Exit: stack assessment produces evidence-backed findings.

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
| P7-05 | EKS rule packs: control plane, compute, scheduling, add-ons, identity, images, storage; EBS and EFS packs. |
| P7-06 | Mechanisms and recovery actions for EKS (cluster, node groups, add-ons, manifests via GitOps if present — in RTO scope per §24.1). |
| P7-07 | Level 1 vs Level 2 confidence; UNKNOWN for Kubernetes workload recovery without credentials (§98). |
| P7-08 | Fixture B (§86) and EKS demo (§89): cluster PASS, application FAIL (no EBS CSI). |
| P7-09 | Real-AWS checkpoint for the EKS demo (kind or EKS in sandbox; decide in the decision log). |

Exit: cluster DR ready while the application is not, because of storage or identity.

### P8 — RPO

Spec: §51, §52.

| ID | Task |
|---|---|
| P8-01 | RPO estimators per mechanism: recovery-point age, replica lag (CloudWatch metrics), S3 replication (RTC metrics if present), DynamoDB Global Tables posture, EBS snapshot age. |
| P8-02 | Stack RPO (worst over required in-scope stores), UNKNOWN propagation, contributors. |
| P8-03 | RPO in CLI, API and UI; target comparison. |

Exit: data-store recovery posture contributes to stack RPO.

### P9 — Optimizer, cost and remediation

Spec: §54–§60, §94.

| ID | Task |
|---|---|
| P9-01 | `recovery_options()` in packs; strategy → mechanism mapping per pack (§27). |
| P9-02 | Candidate generation per strategy + bounded variants; current architecture as baseline; prerequisite and conflict rejection. |
| P9-03 | `CostProvider`: `StaticCostProvider` with versioned price table; then `AWSPricingProvider`. Cost confidence and assumptions (§59). |
| P9-04 | Evaluate candidates: DAG, RTO, RPO, readiness. Pareto frontier. Requirement-driven and budget-driven modes. |
| P9-05 | Remediation planner (§60): re-plan the whole stack per change and explain stack-level deltas. |
| P9-06 | `perpetual optimize STACK --rto --rpo --budget`; Optimize tab in UI. Spec §94 test. |

Exit: several whole-stack candidates can be compared on cost, RTO and RPO.

### P10 — Terraform compiler

Spec: §61, §62.

| ID | Task |
|---|---|
| P10-01 | Template set per mechanism (Jinja2) producing `generated/dr/` companion files. |
| P10-02 | Variables for existing values, generated comments, assumptions file, no secrets. |
| P10-03 | `terraform fmt` and `terraform validate` in tests; optional `apply` to Floci. |
| P10-04 | CLI, API (`/terraform/generate`) and UI tab with download. |

Exit: `terraform fmt` and `terraform validate` pass on generated fixture configuration.

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
| P12-01 | Full §100 workflow on the sandbox for the ECS and EKS stacks. |
| P12-02 | Security pass: canary tests, Terraform-state redaction (§68), no outbound calls except AWS and Kubernetes. |
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
- LLM explanation layer (§69, §70).
- Hosted version: login, PostgreSQL, workers, cross-account role with external ID (§66, §71.1).
- Infracost and CUR cost providers (§58).
- DynamoDB and Aurora Global depth; Lambda, SQS, ElastiCache rule packs.
- Multi-stack view that de-duplicates shared resources.
