# Perpetual — Tracker

Plan: [IMPL_PLAN.md](IMPL_PLAN.md) (locked 2026-10-25; milestones restructured 2026-10-27). Spec: [spec.md](spec.md) & [`docs/spec/`](docs/spec/) (revision 4). Update this file at the end of every session.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` dropped (needs a decision-log entry). A task with lettered subtasks (e.g. P0-04a) is done when all its subtasks are done.

**Current focus:** M0 PoC · next task **P0-04a**.

## Milestones

| Milestone | Release | Phases | Status | Exit (demo) |
|---|---|---|---|---|
| M0 PoC | — | P0, P1, P1c | [~] | `perpetual poc fix --fixture ecs-broken`: generated Terraform + recovery script, re-simulated stack matches `ecs-remediated` |
| M1 Alpha | — | P1b, P2, P2b, P3, P4 (no P4-07), P5, P6, P8 | [ ] | a real sandbox ECS stack gets its graph, blockers, RTO and RPO in the UI |
| M2 MVP | v0.1 | P7, P9 (no P9-07), P10 (v0.1 tasks), P11, P12 | [ ] | spec §100 workflow, deterministic: DR spec → companion Terraform + suggested edits + scripts/ARC plan on a branch or PR → verified with a supplied saved plan → observed READY after deploy |
| M3 Agents | v0.2 | P3b, P4-07, P9-07, P10 (v0.2 tasks), P13 | [ ] | LLM advisor, planner and in-place IaC transformation in an isolated runner; v0.2 gates pass |
| M4 Proven | v0.3 | P14 | [ ] | a game day or ARC execution report takes a sandbox stack to PROVEN |
| M5 Production | v1.0 | P15 | [ ] | installable from PyPI/Homebrew, upgradeable, audited, documented supported-service matrix |

## Phases

| Phase | Milestone | Status | Exit criterion |
|---|---|---|---|
| P0 Engine foundation | M0 | [~] | `perpetual graph --fixture ecs-broken` prints graph + overlay |
| P1 Simulation and recovery core | M0 | [ ] | §87 reproduced on fixtures; remediated fixture RECOVERABLE |
| P1c PoC compile loop | M0 | [ ] | fixture fix → Terraform + script → re-simulated RECOVERABLE |
| P1b Importers, API, UI | M1 | [ ] | import → review/edit graph in UI → simulate |
| P2 AWS discovery (ECS slice) | M1 | [ ] | scan sandbox → normalized graph |
| P2b Observed evidence | M1 | [ ] | every edge shows basis; contradictions listed |
| P3 Stack discovery | M1 | [ ] | "checkout" is one stack with services |
| P4 DR rule packs | M1 (P4-07 M3) | [ ] | evidence-backed findings |
| P5 Simulation on discovered stacks | M1 | [ ] | survives/fails and why, on sandbox |
| P6 Recovery DAG on live data | M1 | [ ] | architecture-derived RTO |
| P8 RPO | M1 | [ ] | stack RPO from data stores |
| P7 EKS slice | M2 | [ ] | cluster ready, application not |
| P9 Optimizer, DR spec | M2 (P9-07 M3) | [ ] | deterministic candidates compared; approved DR spec per demo |
| P10 IaC delivery | M2 / M3 | [ ] | v0.1: companion + suggested edits verified with a supplied plan; v0.2: in-place edits verified in isolation |
| P11 Recovery artifacts | M2 | [ ] | runbook, scripts and ARC plan from one DAG for both demos |
| P12 Hardening, v0.1 | M2 | [ ] | §109 answer for a real stack; 0.1.0 released |
| P3b LLM foundation | M3 | [ ] | `perpetual llm test` + cited explainer answer |
| P13 Agents integration, v0.2 | M3 | [ ] | v0.2 gates pass; 0.2.0 released |
| P14 Proven readiness, v0.3 | M4 | [ ] | PROVEN tier from imported drill evidence; 0.3.0 released |
| P15 Production, v1.0 | M5 | [ ] | 1.0.0 released with support policy |

## Release gates

### M0 PoC

| Gate | Status |
|---|---|
| §87 broken ECS demo: NOT DR READY with blockers (fixture) | [ ] |
| §88 remediated ECS demo: RECOVERABLE (fixture) | [ ] |
| §93 RTO tests (40 / 48 / 49.5) | [ ] |
| PoC loop: generated Terraform passes fmt + validate; recovery script passes lint and a moto dry run; re-simulation matches §88 | [ ] |
| Import contracts green | [~] |

### v0.1 (M2)

| Gate | Status |
|---|---|
| §87/§88 reproduced on sandbox AWS | [ ] |
| §89 EKS demo: cluster PASS, application FAIL (fixture) | [ ] |
| §89 reproduced on sandbox | [ ] |
| §94 optimizer test | [ ] |
| Review gate: no READY with unreviewed low-confidence required edges | [ ] |
| Canary test: no secrets, env values or raw logs persisted | [ ] |
| `uv tool install` + `perpetual ui` on a clean machine | [ ] |
| Both demo designs pass verification from a supplied saved plan, with explicit deployment prerequisites; observed READY requires fresh post-deployment evidence (§61.1) | [ ] |
| Companion Terraform passes fmt + validate; it creates new resources only, and changes to managed resources are suggested edits by address (§62.1) | [ ] |
| Perpetual never runs `terraform plan` or any repository tool in v0.1 (§61.1) | [ ] |
| Docs: README, user guide, IAM policy, rule reference | [ ] |
| Planned snapshot lifecycle/unknown/root-identity regressions (§15.4) | [ ] |
| Partial scan, confirmed absence, stale metrics and cross-account skew regressions (§76.1) | [ ] |
| Readiness decision table and recoverable-but-RPO-FAIL case (§31) | [ ] |
| Coverage registry connects every enabled rule/estimator to typed producers/actions/tests (plan §3.5) | [ ] |
| Approval supersession, stale checkpoint and post-verification edit regressions (§56.3) | [ ] |
| ALL/ANY/quorum selected-path and shared-prerequisite regressions (§19.1) | [ ] |
| Ambiguous shared-role/ENI observations cannot gain exact-edge confidence (§14.1) | [ ] |
| Workload/price unknowns, total cost, budget bounds and Pareto regressions (§59.1) | [ ] |
| Saved-plan JSON accepted; UI event stream rejected (§15.4) | [ ] |
| All §90.2 review regressions pass; no static-only or conditional design labeled observed READY | [ ] |
| Runbook, recovery scripts and ARC plan come from one DAG with matching step numbers; scripts pass lint + fixture dry run; ARC plan covers every action or names a script step (§63) | [ ] |
| No generated script or plan is executed by Perpetual; generated plans have no alarm triggers (§63, §101) | [ ] |
| No LLM dependency installed or called in v0.1 | [ ] |

### v0.2 (M3)

| Gate | Status |
|---|---|
| Hostile-LLM tests: no state, number or verdict upgraded without verification | [ ] |
| No apply/destroy/state/kubectl apply reachable from the transformer | [ ] |
| Isolated runner denies executable data sources/plugins, escapes, credential theft, egress and cloud mutation (§61) | [ ] |
| LLM call log shows no state, secrets, env values or raw logs sent | [ ] |
| In-place edits on both demos pass design verification; companion path still works with LLM disabled | [ ] |

### v0.3 (M4)

| Gate | Status |
|---|---|
| A sandbox game day (script log) and an ARC execution report each produce a PROVEN result for the matching scan and design digest | [ ] |
| Drift after a drill demotes PROVEN/CONFIGURED as specified (§77) | [ ] |
| Imported drill data stores timings only; canary test passes | [ ] |

### v1.0 (M5)

| Gate | Status |
|---|---|
| Upgrade from 0.1/0.2/0.3 databases and config without data loss | [ ] |
| Install from PyPI and Homebrew on Linux and macOS | [ ] |
| External security review findings closed | [ ] |
| Published supported-service matrix matches the coverage registry | [ ] |

---

## M0 PoC

### P0 Engine foundation

- [x] P0-01 Repo skeleton, `mise.toml` with tasks, root-installable `uv` workspace, `__init__.py` subpackage stubs, ruff, mypy strict, pytest
- [x] P0-02 import-linter contracts
- [x] P0-03 GitHub Actions CI
- [ ] P0-04a Core graph and stack models, status enums
- [ ] P0-04b Typed properties: compute and containers
- [ ] P0-04c Typed properties: data and storage
- [ ] P0-04d Typed properties: messaging, network, edge and supporting services
- [ ] P0-04e Out-of-scope, external and generic properties; quota/availability/metric facts
- [ ] P0-04f Evaluation, coverage, workload/cost, prerequisite, verification and drill models
- [ ] P0-05 Canonical resource IDs
- [ ] P0-06 Typed config + defaults
- [ ] P0-07 Persistence + initial Alembic migration + SQLite/PostgreSQL dialect compilation check
- [ ] P0-08 Fixture format v1, loader, validator, JSON Schema
- [ ] P0-09 Evidence combination + fingerprints
- [ ] P0-10 Graph overrides (apply, merge, orphan, YAML)
- [ ] P0-11 NetworkX snapshot + traversal helpers
- [ ] P0-12 `perpetual graph` CLI
- [ ] P0-13 Fixtures: ecs-broken, ecs-remediated, cycle, shared-node, deep-path
- [ ] P0-14 CLAUDE.md commands updated
- [ ] P0-15 Immutable evaluation/snapshot manifests, canonical hashes and versioned fixture inputs

### P1 Simulation and recovery core

- [ ] P1-01 Rule-pack protocol + registry
- [ ] P1-02 First-slice mechanism resolution (strict "reproducible")
- [ ] P1-03 RTO scope classification
- [ ] P1-04 FailureScenario dispatch
- [ ] P1-05 Impact pass
- [ ] P1-06 Recovery pass
- [ ] P1-07 Stack state + readiness composition, target/evidence/review gates and evaluation kind
- [ ] P1-08 Reason chains
- [ ] P1-09 Duration catalog v1 (incl. generic fallback action types + per-resource duration overrides)
- [ ] P1-10 First-slice recovery actions (+ fallback actions for user-accepted unmodeled mechanisms)
- [ ] P1-11 DAG builder (template, refinement, decide, stack validation)
- [ ] P1-12 Buffer
- [ ] P1-13 RTO (low/expected/high, UNKNOWN, breakdown)
- [ ] P1-14 Target comparison
- [ ] P1-15 Persist simulation + plan
- [ ] P1-16 `perpetual simulate` / `perpetual plan`
- [ ] P1-17 Spec §92/§93 + simulation tests
- [ ] P1-18 ALL/ANY/quorum selection, shared prerequisites and readiness decision-table regressions

### P1c PoC compile loop

- [ ] P1c-01 Modeled DR change set applied to `ecs-broken` (ECR replication, RDS cross-Region replica, multi-Region KMS key)
- [ ] P1c-02 Companion Terraform templates for the three changes; fmt + validate
- [ ] P1c-03 Re-simulate the modeled snapshot; match `ecs-remediated`
- [ ] P1c-04 One Python recovery script (RDS promote, ECS scale, DR health check); moto dry run
- [ ] P1c-05 `perpetual poc fix` CLI + README demo

## M1 Alpha

### P1b Importers, API and UI

- [ ] P1b-01 Terraform importer
- [ ] P1b-02 Identity resolution
- [ ] P1b-03 Recorded-AWS normalizers + importer
- [ ] P1b-04 FastAPI routes
- [ ] P1b-05 OpenAPI → TS types, drift check
- [ ] P1b-06 `perpetual ui` (localhost, host flag warning)
- [ ] P1b-07 Web scaffold
- [ ] P1b-08 Graph editor: view
- [ ] P1b-09 Graph editor: review
- [ ] P1b-10 Graph editor: edits
- [ ] P1b-11 Home + stack screen
- [ ] P1b-12 Simulation view
- [ ] P1b-13 Packaging (UI in wheel)
- [ ] P1b-14 Playwright smoke test
- [ ] P1b-15 Authoritative planned snapshots: lifecycle changes, unknowns, stale-proof invalidation and root identities

### P2 AWS discovery (ECS slice)

- [ ] P2-01 Collector protocol, sessions (incl. global/`us-east-1` pass), partial scans
- [ ] P2-02a EC2 instances, Auto Scaling groups, launch templates, AMIs
- [ ] P2-02b VPC, subnets, route tables, NAT, IGW, endpoints, TGW attachments, ENIs, security groups
- [ ] P2-02c ELB (ALB/NLB, listeners, target groups)
- [ ] P2-02d Route 53 (zones, records, health checks, Accelerated Recovery) and ARC (routing controls, Region switch plans + evaluation, legacy readiness checks)
- [ ] P2-02e CloudFront, ACM (incl. `us-east-1`), WAFv2 (REGIONAL + CLOUDFRONT)
- [ ] P2-03a ECS
- [ ] P2-03b Lambda (functions, layers, event-source mappings)
- [ ] P2-03c ECR (replication, image metadata)
- [ ] P2-03d SQS and SNS
- [ ] P2-03e Secrets Manager and SSM parameters (metadata, primary + DR)
- [ ] P2-03f KMS, IAM, IAM Identity Center Regions
- [ ] P2-03g CloudWatch Logs
- [ ] P2-04a RDS/Aurora (instances, clusters, replicas, snapshots)
- [ ] P2-04b S3 and AWS Backup
- [ ] P2-04c EBS and EFS
- [ ] P2-04d Initial DynamoDB
- [ ] P2-05 Resource Explorer, AWS Config
- [ ] P2-06 Edge resolvers: SG, IAM, references, ASG→LT→AMI→Snapshot→KMS, Lambda→S3/ECR/Layers, event-source/subscription/WAF associations, Config
- [ ] P2-07 `perpetual scan` + API + UI status
- [ ] P2-08 Read-only IAM policy doc
- [ ] P2-09 moto + Floci (+ Postgres) tests, `examples/ecs-rds`
- [ ] P2-10 Contract suite skeleton + redaction
- [ ] P2-11 Real-AWS checkpoint
- [ ] P2-12 Quota/headroom, Region capability and CloudWatch Metrics collectors with typed facts/contracts
- [ ] P2-13 Coverage/freshness, confirmed absence, atomic snapshots and partial-scan regressions

### P2b Observed dependency evidence

- [ ] P2b-01 Synthetic log generator
- [ ] P2b-02 CloudTrail reader
- [ ] P2b-03 Principal → compute mapping (task role, Lambda role, IRSA, Pod Identity, EC2/ASG instance profile)
- [ ] P2b-04 Flow-log reader + ENI resolution (incl. EC2/ASG + Lambda Hyperplane ENIs)
- [ ] P2b-05 Aggregate-only observations + canary
- [ ] P2b-06 Contradictions, unobserved, external proposals
- [ ] P2b-07 Coverage report
- [ ] P2b-08 Real-AWS checkpoint
- [ ] P2b-09 Ambiguous observation attribution, candidate-set aggregation and review gates

### P3 Stack and service discovery

- [ ] P3-01 Grouping signals (incl. WAF→ALB→TG→ECS/EC2/ASG/Lambda & SNS→SQS→Lambda chains)
- [ ] P3-02 Service suggestion (ECS, EC2/ASG, Lambda; Deployments in P7)
- [ ] P3-03 Roots, closure, shared resources
- [ ] P3-04 Manual stack/service editing
- [ ] P3-05 Discovery confidence

### P4 DR rule packs

- [ ] P4-01 Finding model, rule registry, rule docs
- [ ] P4-02a ECS pack
- [ ] P4-02b EC2/ASG pack (AMI copy, snapshot KMS)
- [ ] P4-02c Lambda pack (DR package/image/layers, event-source mappings)
- [ ] P4-02d ECR pack
- [ ] P4-02e SQS and SNS packs
- [ ] P4-02f Secrets/SSM pack
- [ ] P4-02g KMS and IAM packs
- [ ] P4-03a RDS/Aurora pack
- [ ] P4-03b S3 pack
- [ ] P4-03c Network pack
- [ ] P4-03d ALB/NLB, CloudFront origin failover, ACM
- [ ] P4-03e Route 53 pack (data vs control plane)
- [ ] P4-03f WAF pack (primary vs DR parity)
- [ ] P4-03g CloudWatch Logs pack (scope-aware)
- [ ] P4-04a Cross-cutting: XREG-CONFIG-001, XREG-IAM-002, XREG-KMS-003, CTRL-PLANE-001, QUOTA-DR-001, REGION-SVC-001
- [ ] P4-04b Cross-cutting: ARC-RS-001, SSM-PARITY-001
- [ ] P4-04c Cross-cutting: OPS-ACCESS-001/002 + `operator_access` loader
- [ ] P4-05 Readiness dimensions + scoring
- [ ] P4-06 `perpetual assess` + API + UI
- [ ] P4-08 Initial DynamoDB and EFS rules, mechanisms/options and evidence fixtures

### P5 Simulation on discovered stacks

- [ ] P5-01 Mechanisms from rule packs + DR-side resolution
- [ ] P5-02 Explainability
- [ ] P5-03 Fail Region UX on live data
- [ ] P5-04 Real-AWS checkpoint (§87/§88)

### P6 Recovery DAG on live data

- [ ] P6-01 Recovery actions for all packs
- [ ] P6-02 Catalog coverage report
- [ ] P6-03 Shared-resource marking
- [ ] P6-04 Recovery tab in UI

### P8 RPO

- [ ] P8-01 RPO estimators
- [ ] P8-02 Stack RPO
- [ ] P8-03 RPO in CLI, API, UI

## M2 MVP (v0.1)

### P7 EKS slice

- [ ] P7-01 EKS collectors
- [ ] P7-02 Kubernetes collector (Level 2)
- [ ] P7-03 NetworkPolicy evidence
- [ ] P7-04 Services from Deployments/StatefulSets
- [ ] P7-05 EKS/EBS rules and reuse of P4 EFS rules with Kubernetes storage integration
- [ ] P7-06 EKS mechanisms + actions
- [ ] P7-07 Level 1 vs 2 confidence
- [ ] P7-08 Fixture B + §89 demo
- [ ] P7-09 Real-AWS checkpoint

### P9 Optimizer, cost and DR spec

- [ ] P9-09 Versioned workload inputs, CLI/API/UI editing and cost-input validation (before P9-03)
- [ ] P9-01 Recovery options + strategy mapping
- [ ] P9-02 Candidate generation
- [ ] P9-03 Cost providers, ranges, line items, freshness, total DR budget and unknown handling
- [ ] P9-04 Feasibility gates, budget comparisons and complete-candidate Pareto ranking
- [ ] P9-05 Remediation planner (stack-level deltas)
- [ ] P9-06 `perpetual optimize` + UI + §94 test
- [ ] P9-08 DR spec (incl. execution method, deterministic rationale), immutable approval digest, supersession/resume checks and export

### P10 IaC delivery (v0.1)

- [ ] P10-02 Worktree/branch management and approved-baseline checks (no repository tool execution)
- [ ] P10-06a Companion templates: network, KMS, IAM
- [ ] P10-06b Companion templates: data (RDS/Aurora, S3, DynamoDB, EFS)
- [ ] P10-06c Companion templates: compute and images (ECS, EC2/ASG, Lambda, ECR)
- [ ] P10-06d Companion templates: messaging, edge and supporting (SQS/SNS, Route 53, WAF, Secrets, CloudWatch Logs)
- [ ] P10-10 Suggested edits by Terraform address for resources the user's IaC manages
- [ ] P10-04 Verification: static checks of generated code, supplied saved-plan import, provenance, re-evaluation and stage separation
- [ ] P10-05 Change delivery (commits, patch, optional PR)
- [ ] P10-07 `perpetual transform` + API + UI
- [ ] P10-11 Demo design-verification tests from supplied plans (ECS + EKS) plus static-only/stale/unknown regressions

### P11 Recovery artifacts

- [ ] P11-01 Failback metadata
- [ ] P11-02 Failover runbook (explanatory)
- [ ] P11-03 Failback runbook (explanatory)
- [ ] P11-04 Export + surfaces
- [ ] P11-05 Prerequisite scripts and SOPs
- [ ] P11-06 Recovery scripts (failover + failback)
- [ ] P11-07 ARC Region switch plan compiler
- [ ] P11-08 Method-specific RTO and cost

### P12 Hardening and v0.1

- [ ] P12-01 §100 workflow on sandbox (ECS + EKS)
- [ ] P12-02 Security pass (deterministic scope)
- [ ] P12-03 Structured logging
- [ ] P12-04 Performance at 5k resources
- [ ] P12-05a Docs: README and install
- [ ] P12-05b Docs: user guide (scan → review → simulate → design → deliver → run recovery)
- [ ] P12-05c Docs: read-only IAM policy and `operator_access`
- [ ] P12-05d Docs: rule reference and fixture format
- [ ] P12-06 Release 0.1.0

## M3 Agents (v0.2)

### P3b LLM foundation

- [ ] P3b-01 Provider abstraction, per-role config, capability probe, `perpetual llm configure|test`
- [ ] P3b-02 LangGraph runtime, tools (incl. `web_search`, `web_fetch`), checkpointer, interrupts, validated outputs
- [ ] P3b-03 Fake chat model + recorded web-search/fetch harness + hostile/prompt-injection fixtures
- [ ] P3b-04 Guardrails: opt-in, redaction, query sanitization + untrusted web-content sanitization, `.perpetualignore`, call log
- [ ] P3b-05 Knowledge base: shipped domain docs (`knowledge/domain/`), `sources.yaml`, `kb sync|add|list|show|remove`, agent web-fetch ingestion, hybrid retrieval, citations
- [ ] P3b-06 Skills: format, loader, first-slice skills (incl. EC2/ASG, Lambda, SQS/SNS, WAF)
- [ ] P3b-07 Explainer agent

### LLM tasks in earlier phases

- [ ] P4-07 Advisory review agent
- [ ] P9-07 LLM candidate planner

### P10 IaC delivery (v0.2)

- [ ] P10-01 IaC declaration + resource-to-code mapping (Terraform, Kubernetes)
- [ ] P10-09 Enforced execution isolation and hostile repository fixtures (before P10-03)
- [ ] P10-03 Transformation agent (+ EKS skills)
- [ ] P10-12 Runner-executed saved plans inside the isolation boundary
- [ ] P10-08 Transformation evals plus hostile/stale/static-only regression cases

### P13 Agents integration and v0.2

- [ ] P13-01 Wire advisor, planner and transformer into CLI/API/UI behind the opt-in
- [ ] P13-02 In-place edits replace suggested edits when an IaC repo is declared; companion stays the fallback
- [ ] P13-03 LLM-cited DR spec rationale
- [ ] P13-04 v0.2 security pass (LLM data, isolation, hostile fixtures) on the sandbox
- [ ] P13-05 Docs: LLM setup, providers, what is sent
- [ ] P13-06 Release 0.2.0

## M4 Proven (v0.3)

### P14 Proven readiness

- [ ] P14-01 Drill model wiring and recovery-script log import
- [ ] P14-02 ARC Region switch execution-report import (opt-in, timings only)
- [ ] P14-03 FIS and Resilience Hub test-result import
- [ ] P14-04 PROVEN tier in readiness, reports and UI
- [ ] P14-05 Duration-catalog calibration from drills
- [ ] P14-06 Resilience Hub importer: discovered dependencies as candidate edges
- [ ] P14-07 Drift between scans and demotion of CONFIGURED/PROVEN
- [ ] P14-08 Game-day checklist generation (incl. operator-access proof)
- [ ] P14-09 Release 0.3.0

## M5 Production (v1.0)

### P15 Production readiness

- [ ] P15-01 Distribution: PyPI, Homebrew tap, signed releases, SBOM
- [ ] P15-02 Upgrade path: database, config, fixture and catalog migrations across versions
- [ ] P15-03 Supported platforms (Linux, macOS) with CI on each
- [ ] P15-04 Published supported-service matrix from the coverage registry
- [ ] P15-05 More services: ElastiCache Global Datastore, Step Functions, API Gateway, Aurora Global depth, advanced DynamoDB
- [ ] P15-06 Security review: threat model, external review, dependency scanning
- [ ] P15-07 Scale: 20k resources, multi-stack accounts, multi-stack view without double counting
- [ ] P15-08 Documentation site: guides, tutorials, troubleshooting
- [ ] P15-09 Accuracy report: predicted vs proven RTO across drills
- [ ] P15-10 Release 1.0.0 with support and deprecation policy

---

## Spec coverage

Where each spec area is implemented. A spec section with no task is either covered by an invariant (IMPL_PLAN §3.4) or in the backlog.

| Spec | Topic | Tasks |
|---|---|---|
| §1–§4 | Definition, principles, scope | invariants |
| §5–§8.1 | Services in scope, control vs data plane | P2-02..04, P4-03, P7-01 |
| §9–§13 | Input sources | P1b-01, P2-01..05 |
| §14 | Kubernetes discovery | P7-02, P7-07 |
| §14.1 | Dependency sources | P2-06, P2b-01..07, P7-03 |
| §15–§15.4 | Resource model, identity, typed props, planned snapshot | P0-04/05/15, P1b-01/02/10/15 |
| §16 | Evidence | P0-04, P0-09 |
| §17–§20 | Graph, edges, ALL/ANY/quorum groups | P0-04/11, P1-05/06/18 |
| §21–§22 | Evidence and confidence | P0-09, P2-06 |
| §23 | Review and editing, review gate | P0-10, P1-07, P1b-09, P1b-10 |
| §24–§25 | Stacks, services, discovery | P0-04, P3-01..05, P7-04 |
| §24.1 | RTO scope | P1-03, P1-05, P4-05 |
| §26 | Requirement | P0-04, P1b-11 |
| §27–§27.1 | Strategies, mechanisms, overlay | P1-02, P5-01, P9-01 |
| §28–§28.1 | Rule packs, cross-cutting | P1-01, P4-02..04, P7-05 |
| §28.2 | LLM advisory review | P4-07 (v0.2) |
| §29–§31 | Findings, readiness, status, scoring | P1-07, P4-01, P4-05 |
| §32–§40 | ECS and EKS checks | P4-02, P7-05 |
| §41–§42 | RDS, data gravity | P4-03, P0-04 |
| §43–§46 | Simulator, output, reason chains | P1-04..08, P5-01..03 |
| §47–§50 | Plan, DAG, durations, buffer, RTO | P1-09..13, P6-01..04 |
| §47.2 | Execution method | P9-08, P11-08 |
| §51 | RPO | P8-01..03 |
| §52 | Target vs predicted | P1-14, P8-03 |
| §53 | Drills | schema P0-04f; import and PROVEN tier P14-01..05 |
| §54–§60 | Optimizer, workload/cost/budget, remediation | P9-01..09 |
| §56.1–§56.3 | Candidate planner, immutable evaluations and DR spec approval | P0-15, P9-08, P10-04/05; planner P9-07 (v0.2) |
| §61–§62.1 | IaC delivery: companion + suggested edits (v0.1), isolated transformation (v0.2), staged verification | P1b-15, P1c-02, P10-01..12, P13-02 |
| §63–§64 | Recovery artifacts (runbook, prerequisite and recovery scripts, ARC plan), failback | P1c-04, P11-01..08 |
| §65–§68 | Security, access, secrets, state | P2-01, P2-08, P2b-05, P12-02 |
| §69–§70 | LLM architecture, knowledge base, skills, guardrails, explainer (v0.2) | P3b-01..07, P10-08, P13-01..05 |
| §71–§75 | Tech, deployment, layout, persistence | P0-01, P0-07, P1b-06, P1b-13 |
| §76–§76.1 | Scan model, coverage/freshness and confirmed absence | P0-15, P2-01/07/12/13 |
| §77 | Drift | P14-07 |
| §78–§79 | API, CLI | P0-12, P1-16, P1b-04, P2-07, P4-06, P9-06 |
| §80–§84 | UI | P1b-08..12, P5-02..03, P6-04 |
| §85–§89 | Fixtures and demos | P0-13, P7-08, P5-04, P7-09 |
| §90–§94 | Testing and review regression gates | owners in spec §90.2; P1-17/18, P2-09/10, P2b-01/09, P9-06 |
| §95–§98 | Quality, observability, errors, unknown | P0-01..03, P12-03, P2-01 |
| §99–§109 | Phases, MVP, non-goals, constraints | this plan |

---

## Open questions

Resolve these with a decision-log entry before the task that needs them.

| # | Question | Needed by |
|---|---|---|
| Q1 | Default confidence threshold for "low-confidence" edges (impact pass and review gate). Spec says configuration; pick an initial value. | P1-05 |
| Q2 | Source for initial duration-catalog numbers (AWS docs, own measurements in the sandbox). | P1-09 |
| Q3 | Which first-slice operations Floci supports (ECS, ELB, Route 53, RDS replicas, ECR replication). | P2-09 |
| Q4 | Sandbox accounts: one account with two Regions, or a separate DR account from the start (spec §66). | P2-11 |
| Q5 | EKS checkpoint on real EKS (cost) vs kind for Kubernetes-level checks plus EKS for AWS-level checks. | P7-09 |
| Q6 | Price table source and refresh for `StaticCostProvider`. | P9-03 |
| Q7 | Default model per role for evals and docs (OpenRouter model IDs), and the cost budget for an eval run. | P3b-01 |
| Q8 | Which public sources go in `knowledge/sources.yaml` first, and their licence terms for local ingestion. | P3b-05 |
| Q9 | UX for declaring IaC roots (CLI flags and/or `perpetual.yaml`); multiple roots require distinct root/workspace identities. Must be declared before approval under §56.3. | P9-08 |
| Q10 | Resolved 2026-10-27: isolated local runner or supplied saved plan with matching provenance; no unsandboxed execution. Static-only otherwise (§61–61.1). | P10-09/04 |
| Q11 | Resolved 2026-10-27: Python with boto3, run as a self-contained `uv run` script (§63.2). | P11-06 |
| Q12 | Resolved 2026-10-27: EFS and ElastiCache failover steps and the `aws_arcregionswitch_plan` schema confirmed against AWS and provider docs (§63.2, §63.3). | P11-07 |
| Q13 | Resolved 2026-10-27: an `operator_access` section in `perpetual.yaml`, reviewed in git; the UI displays it read-only (§28.1). | P4-04 |

---

## Decision log

Newest first. Any change to IMPL_PLAN.md, or any deviation from spec.md, goes here first.

| Date | Decision | Reason |
|---|---|---|
| 2026-10-28 | P0-02: nine import-linter contracts in `pyproject.toml`, run by `mise run lint`, each proven by a test that plants a violation in a temporary copy of the package. Two widen the plan: `knowledge` is forbidden to the engine alongside `llm`, and the LangChain/LangGraph ban covers every package except `llm`, including `api` and `cli`. Rule 6 (optimizer gets options only through the rule-pack protocol) is added in P1-01, when the protocol module exists. | Contracts that are never seen to fail could silently check nothing, especially for external packages that are not installed. A contract needs real module names, and the rule-pack protocol does not exist yet. |
| 2026-10-28 | P0-01 setup choices: (1) the root `pyproject.toml` is the only Python project and builds `perpetual` from `apps/api/perpetual`; no separate `apps/api/pyproject.toml`, and no uv workspace until a second Python package exists. (2) Pinned tools in `mise.toml`: Python 3.13.13, uv 0.13.1, Node 24.22.1 (LTS), Terraform 1.16.7. (3) Tests live in `apps/api/tests` with pytest's importlib mode; the `contract` marker is excluded by default. (4) ruff skips Markdown. (5) `mise.local.toml` is gitignored for machine-specific overrides. No license is declared yet. | Two projects cannot build the same package (IMPL_PLAN D5 listed both). Versions are ones that installed reliably here; any machine gets them through `mise install`. The license is the owner's decision. |
| 2026-10-27 | Close consistency gaps from the restructure review: P12-02 limited to deterministic checks; ARC, Identity Center, Accelerated Recovery and `OperatorAccessProfile` models added to P0-04d/f; Identity Center row and ARC plan owners added to §3.5; ARC plan price added to P9-03; §61 scope relabelled v0.2; v0.1 verification contract states that the supplied plan includes the companion module and applied suggested edits, plus rendered manifests for EKS; suggested edits cover Kubernetes objects; §78/§79 regrouped with new `verify` and recovery-artifact endpoints/commands; README and `runbooks/` descriptions updated. | Leftovers from moving LLM work to v0.2 and from the reorientation; an unambiguous v0.1 verification contract is needed before P10. |
| 2026-10-27 | Restructure the plan into milestones and move all LLM work to v0.2. M0 PoC (P0, P1, new P1c compile loop on fixtures) → M1 Alpha (discovery, rules, simulation, RTO/RPO on real AWS) → M2 v0.1 MVP (EKS, optimizer, IaC delivery, recovery artifacts, hardening; fully deterministic) → M3 v0.2 Agents (P3b, P4-07, P9-07, P10-01/03/08/09/12, new P13) → M4 v0.3 Proven (new P14: drill import, PROVEN tier, drift, catalog calibration, Resilience Hub importer) → M5 v1.0 Production (new P15). v0.1 delivers companion Terraform for new resources plus suggested edits by Terraform address for managed resources, and verifies designs from a saved plan the user supplies; Perpetual runs no repository tools until the v0.2 isolated runner. Large tasks split into lettered subtasks (P0-04a–f, P2-02a–e, P2-03a–g, P2-04a–d, P4-02a–g, P4-03a–g, P4-04a–c, P10-06a–d, P12-05a–d). New tasks P10-10..12. Plan: D14 and D16 revised, D20 added; spec §28.2, §56.1, §56.2, §61, §61.1, §62.1, §69, §99, §100 updated. | The main selling point (the design-and-change loop) should be proven first on fixtures (M0), not after collectors and agents. The transformation agent and its isolation sandbox are the riskiest parts, so they follow a deterministic v0.1. Without the agent, editing existing IaC in place is unsafe, so v0.1 keeps a single owner per resource: new resources in companion code, changes to managed resources as suggested edits. Smaller tasks make progress visible; milestones beyond v0.1 turn the backlog into a route to production. |
| 2026-10-27 | Resolve Q13: the operator access profile is an `operator_access` section in `perpetual.yaml` (identity source and home Region, break-glass path, network path to private endpoints, tool versions). The UI shows it read-only; edits go through git. A missing section leaves OPS-ACCESS-001/002 UNKNOWN. | Operator access is part of the recovery design, so it is versioned and reviewed like code. A single source avoids drift between file and database. |
| 2026-10-27 | Resolve Q11 and Q12. Q11: recovery and prerequisite scripts are Python with boto3, each a self-contained script run with `uv run` (inline dependency metadata pins boto3); kubectl only for Kubernetes steps. Q12, confirmed against AWS docs: EFS failover deletes the replication configuration from the DR Region (`--deletion-mode LOCAL_CONFIGURATION_ONLY` when the source Region is unreachable), takes several minutes, typical RPO 15 minutes; failback replicates the replica back to the primary and then re-creates the original configuration. ElastiCache Global Datastore failover is `FailoverGlobalReplicationGroup` and is allowed when the primary Region is unavailable; replication is asynchronous, so RPO equals replica lag. Neither has a Region switch block, so both are script steps. `aws_arcregionswitch_plan` exists in the AWS provider; parallel work is a `Parallel` step with `parallel_config` (one level). The provider's block-type list lags the API, so the compiler emits only types the pinned provider supports. | Python matches the codebase, is testable with the same fixtures and moto, and `uv run` needs no install beyond uv. Q12 facts set the EFS script step, failback order and catalog inputs, and the compiler's output schema. |
| 2026-10-27 | Reorient Perpetual (no pivot) after reviewing AWS's 2026 resilience tooling. (1) Position it as a DR design compiler for AWS stacks: whole-stack RTO/RPO before DR exists, dormant failover blockers, the cheapest design within budget, and a verified IaC PR. ARC Region switch is an optional runtime (spec §3). (2) Cross-cloud and multi-cloud DR rejected (§4, §101). (3) Recovery runs by exactly two methods, chosen per stack in the DR spec: recovery scripts kept in git and run by an operator from a laptop with human checks (default, no CI runner), or a compiled ARC Region switch plan. The runbook explains the flow and is not an execution method. RTO is computed for the chosen method (§47.2, §56.2, §63). (4) Terraform owns steady-state DR configuration (replication, standby resources, keys). Generated prerequisite scripts and SOPs cover one-off backfill and account-level work: SSM parameter copy with an operator edit step, S3 Batch Replication of existing objects, quota requests (§62, §63.1). (5) Readiness tiers: design verified → configured (observed READY after deployment and rescan) → proven (game day, ARC execution report or fault-injection test) (§3, §53). (6) ARC readiness checks become legacy, collected only. Collect Region switch plans, Route 53 Accelerated Recovery and IAM Identity Center Regions. New rules ARC-RS-001, SSM-PARITY-001, OPS-ACCESS-001/002; CTRL-PLANE-001 refined for us-east-1 scenarios (§8, §8.1, §28.1). (7) Resilience Hub stays an optional future evidence source, never required. Plan: D19 added; P2-02/03, P4-04 and P9-08 extended; P11 becomes recovery artifacts (P11-05..08); Resilience Hub and execution-report importers go to the backlog. | AWS Resilience Hub (next generation, 2026) now discovers dependencies and runs AI failure-mode analysis and FIS tests, and ARC Region switch runs multi-Region failovers, so assessment alone no longer sets Perpetual apart. Neither designs DR within a budget or changes the user's IaC, and Region switch needs DR resources to exist plus a correct step list, which Perpetual produces. Cross-cloud targets cannot be verified without Azure/GCP expertise. Laptop-run scripts keep humans in the loop; ARC costs $70 per plan per month, so it stays optional. |
| 2026-10-27 | Split `spec.md` (5,500+ lines) into 7 modular topic files under `docs/spec/` (`01-product-and-aws-scope.md` through `07-platform-ui-and-testing.md`) preserving all `§1`–`§109` section numbers and verbatim contracts, while turning root `spec.md` into a concise ~250-line architecture overview, reader's guide and complete section index. | Make the specification readable for human reviewers without losing any detail or breaking `spec §N` citations in `IMPL_PLAN.md`, `TRACKER.md` and `CLAUDE.md`. |
| 2026-10-27 | Close all ten review findings and the Terraform command error in revision 4: define authoritative planned snapshots, separate design verification from observed readiness, enforce isolated IaC execution, track scan coverage/freshness, specify readiness composition, complete collector-to-rule coverage, bind approvals to immutable inputs, model ALL/ANY/quorum dependencies, preserve ambiguous observation attribution, and define workload-driven budget acceptance. Add implementation tasks and regression/release gates; use saved-plan JSON for verification. | User requested all review findings fixed. These contracts prevent stale or speculative evidence from producing READY, close missing implementation dependencies, and make verification restrictions enforceable. Implementation remains unstarted; documentation completion does not mark engineering tasks done. |
| 2026-10-26 | Close 5 service-specific and CI-security gaps: (1) add a global/`us-east-1` collector pass in `P2-01..02` for `WAFv2 (Scope=CLOUDFRONT)`, `ACM (us-east-1)`, `Route 53`, `IAM`, `CloudFront`, and check primary-vs-DR WAF parity in `P4-03`; (2) resolve `ASG → LaunchTemplate → AMI → EBS Snapshot → KMS Key` in `P2-06` and verify cross-Region AMI + snapshot KMS decryptability in `P4-02`; (3) resolve `Lambda → S3 code bucket / ECR image / Lambda Layer` in `P2-06` and verify DR artifact/layer availability in `P4-02`; (4) distinguish SQS endpoint recovery (`RTO`) from in-flight message durability (`RPO`) in `spec §7.1`, `§51`, `P4-02`, and `P8-01`; (5) add offline recorded `web_search`/`web_fetch` fixtures (including hostile/prompt-injection web pages) in `P3b-03` and untrusted web-content sanitization in `P3b-04`. | Prevent missed `us-east-1`/CloudFront WAF & ACM resources, catch Regional AMI/Lambda layer/S3 package blockers, model SQS in-flight message RPO accurately, and keep CI offline and resilient to prompt injection from web-fetched docs. |
| 2026-10-26 | Close 5 pipeline integration gaps for expanded AWS services and KB web research: (1) add generic fallback action types (`generic_promote_counterpart`, `generic_restore_from_backup`, `generic_rebuild_from_iac`) and per-resource duration overrides in the duration catalog (`P1-09`, `P1-10`, `spec §49.1`, `§56.1`) so user-accepted mechanisms on unmodeled resources can produce a valid RTO; (2) add Lambda execution-role and ASG instance-profile mapping in `P2b-03` and EC2/ASG + Lambda Hyperplane ENI resolution in `P2b-04` (`spec §14.1`); (3) add `WAF→ALB→TG→ECS/EC2/ASG/Lambda` and `SNS→SQS→Lambda` grouping chains in `P3-01` and `EC2/ASG` service suggestions in `P3-02`; (4) cover `EC2/ASG`, `Lambda`, `SQS/SNS`, `WAF`, and `CloudWatch Logs` in `StaticCostProvider` (`P9-03`) and companion Terraform templates (`P10-06`, `spec §62.1`); (5) add `perpetual kb list|show|remove` and `GET /kb/documents`, `DELETE /kb/documents/{id}` (`P3b-05`, `spec §78–79`) to inspect and curate agent-fetched KB documents. | Ensure end-to-end consistency across observed evidence, stack grouping, RTO calculation, costing, companion templates and KB curation for the expanded v0.1 scope. |
| 2026-10-26 | Expand v0.1 AWS services and KB web-research capabilities: (1) add `EC2` (instances, ASG, launch templates, AMIs), `Lambda`, `SQS`, `SNS`, `WAF` (WAFv2), and `CloudWatch Logs` across models (`P0-04`), collectors (`P2-02..03`), rule packs (`P4-02..03`), recovery actions (`P6-01`), RPO (`P8-01`) and skills (`P3b-06`); (2) ship curated domain knowledge for all in-scope services in `knowledge/domain/` (`P3b-05`); (3) give LLM agents sanitized `web_search` and `web_fetch` tools (`P3b-02`, `P3b-04`, `P3b-05`) so when an out-of-scope / unmodeled resource appears, the agent fetches official docs, persists/indexes them into the local knowledge base (`kb_documents`/`kb_chunks`) to improve local docs, and cites them during advisory review and DR candidate planning. | User direction: cover EC2, Lambda, SQS, SNS, WAF and CloudWatch Logs in v0.1, hold local domain knowledge for all supported services, and let agents research unmodeled resources via `web_search`/`web_fetch` while enriching the local doc store. |
| 2026-10-26 | Tighten P0/P2 plan details: (1) root `pyproject.toml` builds the `perpetual` package from `apps/api/perpetual` so `uv tool install .` works from the repo root; (2) P0-04 discriminated union includes out-of-scope (`CloudWatchLogGroupProperties`, `CodePipelineProperties`), `ExternalResourceProperties` and fallback `GenericResourceProperties`; (3) P0-01 creates `__init__.py` stubs for all §3.2 subpackages so P0-02 `import-linter` contracts run immediately, and `iac`, `graph`, `evidence`, `stacks`, `normalization`, `importers` are also forbidden from importing `llm`; (4) P0-07 tests SQLite + PostgreSQL dialect compilation for models/migrations and P2-09 includes PostgreSQL in `docker-compose.yml`. | Ensure root installability (`P1b-13`), typed validation for out-of-scope/external resources (`spec §15.2–15.3, §24.1`), day-one `import-linter` contract enforcement (`P0-02`), and PostgreSQL schema compatibility (`spec §71.1, §73`). |
| 2026-10-25 | Spec revision 4: Perpetual changes the user's Terraform and Kubernetes manifests (code only, branch/PR, never apply). LLM agents on LangGraph join advisory review, candidate planning and IaC transformation, with RAG and skills. Provider replaceable (OpenRouter, Anthropic, Bedrock, Ollama). Plan: D14 revised, D15–D18 added, new phase P3b, P4-07, P9-07/08, P10 replaced. | User direction: the tool must fix infrastructure, not only assess it, and use LLMs with RAG and skills to reach the best DR design. "LLM proposes, engine verifies" keeps results trustworthy. |
| 2026-10-25 | Plan locked. Alembic from P0 instead of P1b. | Avoid writing an unmanaged SQLite schema that later needs a migration path. |
| 2026-10-25 | EKS slice is P7, after the ECS slice reaches a live recovery DAG (P6). Spec Phase 2 and 4 EKS items move there. | Spec §105 says complete the ECS slice first. |
| 2026-10-25 | Typer + Rich for the CLI; TanStack Router for the UI; ELK for graph layout; Jinja2 for Terraform templates. | Spec leaves these open. |

---

## Session log

Newest first. Each entry: date, what was done, carry-over for the next session.

### 2026-10-28 — P0-03 CI

- `.github/workflows/ci.yml`: Ubuntu, actions pinned by SHA (checkout v7.0.1, mise-action v5.2.4), mise 2026.9.1, read-only token, `uv sync --locked`, then `mise run check`. actionlint clean; first run on `aefbacf` green.
- **Carry-over:** P0-04a (core graph and stack models).

### 2026-10-28 — P0-02 import contracts

- Nine import-linter contracts (IMPL_PLAN §3.3, CLAUDE.md) in `pyproject.toml`; `lint-imports` added to `mise run lint`.
- `test_import_contracts.py` plants one forbidden import per contract in a temporary copy of the package and checks the right contract breaks; `llm` may import LangGraph.
- `mise run check`: 9 contracts kept, mypy clean, 34 tests pass.
- **Carry-over:** P0-03 (CI); add the rule-6 optimizer contract in P1-01.

### 2026-10-28 — P0-01 repo skeleton

- `mise.toml` (tools + `sync`, `fmt`, `lint`, `typecheck`, `test`, `check`), root `pyproject.toml` (Hatchling package from `apps/api/perpetual`, ruff, mypy strict, pytest), `uv.lock`, 22 subpackage stubs with ownership docstrings, `py.typed`, skeleton tests, `.gitignore`.
- `mise run check` passes (ruff, mypy strict on 24 files, 23 tests); the wheel builds from the repo root.
- Network note: PyPI and GitHub downloads stalled on this machine until Cloudflare WARP was enabled. Python 3.13.13 was linked into mise from an existing local install (`mise link`, machine-local only).
- **Carry-over:** P0-02 (import-linter contracts), then P0-03 (CI).

### 2026-10-27 — Milestone restructure; LLM moved to v0.2

- Reorientation committed and pushed (`844d414`).
- Restructured the plan into milestones M0–M5 with demo exits and per-milestone release gates. Added P1c (PoC compile loop), P13 (v0.2), P14 (v0.3 Proven) and P15 (v1.0 Production); split large tasks into lettered subtasks; moved LLM work to v0.2.
- Spec: v0.1 delivery is companion Terraform + suggested edits with supplied-plan verification (§61, §61.1, §62.1); LLM sections marked v0.2 (§28.2, §56.1, §56.2, §69); §99 and §100 updated.
- Closed review findings on the restructure (P12-02 scope, missing ARC/Identity Center models and coverage, ARC price, §61 label, §78/§79, README, v0.1 verification contract).
- **Carry-over:** start P0-01 (M0 PoC).

### 2026-10-27 — Reorientation against AWS Resilience Hub and ARC Region switch

- Reviewed current AWS docs: Resilience Hub next generation (dependency discovery from DNS query logs, AI failure-mode analysis, FIS tests), ARC Region switch (execution blocks, plan evaluation, execution reports, $70/plan/month), ARC readiness checks closed to new customers, Route 53 Accelerated Recovery, IAM Identity Center multi-Region.
- Considered and rejected a multi-cloud pivot. Recorded the reorientation in the decision log.
- Spec: positioning and readiness tiers (§3), scope (§4, §8, §8.1), new cross-cutting rules (§28.1), execution method (§47.2, §56.2), drill sources (§53), Terraform vs scripts split (§62), recovery artifacts (§63–§63.4), failback (§64), secret handling for generated scripts (§67), non-goals (§101), long-term direction (§108).
- Plan: D19; P2-02/03, P4-04, P9-08 extended; P11 renamed and P11-05..08 added; backlog items; new release gates; Q11–Q13.
- **Carry-over:** start P0-01. Q13 is needed by P4-04, Q11–Q12 by P11.

### 2026-10-27 — Modularize `spec.md` and close specification/plan review findings

- Split `spec.md` (5,500+ lines) into 7 modular topic files in `docs/spec/` (`01-product-and-aws-scope.md` through `07-platform-ui-and-testing.md`) preserving all `§1`–`§109` section numbers and verbatim content, and replaced root `spec.md` with a concise architecture overview, reader's guide and full section index.
- Closed all ten findings and corrected Terraform verification to saved-plan `show -json` input.
- Added contracts for planned snapshots, staged verification, isolation, coverage/freshness, readiness composition, evidence producers, immutable approvals, dependency groups, observation ambiguity and workload/budget handling.
- Added plan coverage matrix, phase dependencies, nine explicit tasks, and spec §90.2 regression/release gates; synchronized task ownership here. Updated README and contributor guidance to distinguish design verification from observed readiness.
- Documentation checks: task IDs/ownership, section references, Markdown links/fences and diff whitespace; no runtime tests because no implementation exists yet. All implementation tasks remain unchecked.
- **Carry-over:** start P0-01 with these contracts; P0-15 is required before persisted evaluations. Resolve remaining open questions by their listed dependency phases.

### 2026-10-26 — Plan review, AWS service expansion & KB web research

- Tightened P0/P2 plan details (root-installable `uv` workspace, out-of-scope/fallback typed properties, `import-linter` subpackage stubs and boundaries, SQLite/PostgreSQL dialect compilation checks).
- Expanded v0.1 AWS service scope to include EC2 & Auto Scaling, Lambda, SQS, SNS, WAF (WAFv2), and CloudWatch Logs across `spec.md`, `IMPL_PLAN.md`, `TRACKER.md`, `CLAUDE.md` and `README.md`.
- Added shipped domain knowledge (`knowledge/domain/`) for all in-scope services and sanitized `web_search` / `web_fetch` agent tools to fetch, persist and cite docs for unmodeled/out-of-scope resources in the local KB.
- Closed 5 pipeline integration gaps: generic fallback duration-catalog actions + per-resource duration overrides for unmodeled resources, CloudTrail/ENI resolution for EC2/ASG and Lambda, WAF/SQS/SNS/EC2/Lambda stack grouping chains, static cost + companion Terraform coverage, and KB curation CLI/API (`kb list|show|remove`).
- Closed 5 service-specific and CI-security gaps: global/`us-east-1` discovery pass for CloudFront WAFv2/ACM + DR WAF parity, `ASG→LaunchTemplate→AMI→Snapshot→KMS` and `Lambda→S3/ECR/Layer` dependency chains, SQS endpoint RTO vs in-flight message RPO distinction, and offline recorded/hostile `web_search`/`web_fetch` fixtures + prompt-injection sanitization.
- **Carry-over:** start P0-01.

### 2026-10-25 — Revision 4

- Spec revision 4: IaC transformation with LLM agents, advisory review, LLM candidate planner, DR spec, knowledge base, skills, provider abstraction, guardrails.
- IMPL_PLAN, TRACKER, README and CLAUDE.md updated to match.
- **Carry-over:** unchanged, start P0-01. Q7–Q10 are needed from P3b onward.

### 2026-10-25 — Planning

- Spec revision 3 written and pushed (stack-level DR, evidence-based graph editing, review gate, local-first, test environments).
- IMPL_PLAN.md, TRACKER.md and CLAUDE.md created.
- **Carry-over:** start P0-01. Resolve nothing else first; Q1–Q6 are needed later.
