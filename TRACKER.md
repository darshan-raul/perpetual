# Perpetual — Tracker

Plan: [IMPL_PLAN.md](IMPL_PLAN.md) (locked 2026-10-25). Spec: [spec.md](spec.md) & [`docs/spec/`](docs/spec/) (revision 4). Update this file at the end of every session.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` dropped (needs a decision-log entry)

## Overview

| Phase | Status | Exit criterion |
|---|---|---|
| P0 Engine foundation | [ ] | `perpetual graph --fixture ecs-broken` prints graph + overlay |
| P1 Simulation and recovery core | [ ] | §87 reproduced on fixtures; remediated fixture RECOVERABLE |
| P1b Importers, API, UI | [ ] | import → review/edit graph in UI → simulate |
| P2 AWS discovery (ECS slice) | [ ] | scan sandbox → normalized graph |
| P2b Observed evidence | [ ] | every edge shows basis; contradictions listed |
| P3 Stack discovery | [ ] | "checkout" is one stack with services |
| P3b LLM foundation | [ ] | `perpetual llm test` + cited explainer answer |
| P4 DR rule packs + advisor | [ ] | evidence-backed findings; cited advisory items |
| P5 Simulation on discovered stacks | [ ] | survives/fails and why, on sandbox |
| P6 Recovery DAG on live data | [ ] | architecture-derived RTO |
| P7 EKS slice | [ ] | cluster ready, application not |
| P8 RPO | [ ] | stack RPO from data stores |
| P9 Optimizer, planner, DR spec | [ ] | candidates compared; approved DR spec per demo |
| P10 IaC transformation | [ ] | demo design verified against targets; deployment/observed readiness pending |
| P11 Runbooks | [ ] | failover + failback for both demos |
| P12 Hardening, v0.1 | [ ] | §109 answer for a real stack |

## Release gate (v0.1)

| Gate | Status |
|---|---|
| §87 broken ECS demo: NOT DR READY with blockers (fixture) | [ ] |
| §88 remediated ECS demo: RECOVERABLE (fixture) | [ ] |
| §87/§88 reproduced on sandbox AWS | [ ] |
| §89 EKS demo: cluster PASS, application FAIL (fixture) | [ ] |
| §89 reproduced on sandbox | [ ] |
| §93 RTO tests (40 / 48 / 49.5) | [ ] |
| §94 optimizer test | [ ] |
| Review gate: no READY with unreviewed low-confidence required edges | [ ] |
| Canary test: no secrets, env values or raw logs persisted | [ ] |
| Import contracts green | [ ] |
| `uv tool install` + `perpetual ui` on a clean machine | [ ] |
| Both demo designs pass verification with explicit deployment prerequisites; observed READY requires fresh post-deployment evidence (§61.1) | [ ] |
| Hostile-LLM tests: no state, number or verdict upgraded without verification | [ ] |
| No apply/destroy/state/kubectl apply reachable from the transformer | [ ] |
| Companion Terraform passes fmt + validate | [ ] |
| LLM call log shows no state, secrets, env values or raw logs sent | [ ] |
| Docs: README, user guide, IAM policy, rule reference | [ ] |
| Planned snapshot lifecycle/unknown/root-identity regressions (§15.4) | [ ] |
| Partial scan, confirmed absence, stale metrics and cross-account skew regressions (§76.1) | [ ] |
| Readiness decision table and recoverable-but-RPO-FAIL case (§31) | [ ] |
| Coverage registry connects every enabled rule/estimator to typed producers/actions/tests (plan §3.5) | [ ] |
| Approval supersession, stale checkpoint and post-verification edit regressions (§56.3) | [ ] |
| ALL/ANY/quorum selected-path and shared-prerequisite regressions (§19.1) | [ ] |
| Ambiguous shared-role/ENI observations cannot gain exact-edge confidence (§14.1) | [ ] |
| Workload/price unknowns, total cost, budget bounds and Pareto regressions (§59.1) | [ ] |
| Isolated runner denies executable data sources/plugins, escapes, credential theft, egress and cloud mutation (§61) | [ ] |
| Saved-plan JSON accepted; UI event stream rejected (§15.4) | [ ] |
| All §90.2 review regressions pass; no static-only or conditional design labeled observed READY | [ ] |

---

## P0 Engine foundation

- [ ] P0-01 Repo skeleton, `mise.toml` with tasks, root-installable `uv` workspace, `__init__.py` subpackage stubs, ruff, mypy strict, pytest
- [ ] P0-02 import-linter contracts
- [ ] P0-03 GitHub Actions CI
- [ ] P0-04 Domain models incl. dependency groups, coverage, evaluation manifests, workload/cost and verification stages; complete typed service facts
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

## P1 Simulation and recovery core

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

## P1b Importers, API and UI

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

## P2 AWS discovery (ECS slice)

- [ ] P2-01 Collector protocol, sessions (incl. global/`us-east-1` pass), partial scans
- [ ] P2-02 EC2 (instances, ASG, launch templates, AMIs) / VPC, ELB, Route 53, CloudFront, ACM, WAF (REGIONAL + CLOUDFRONT) collectors
- [ ] P2-03 ECS, Lambda, ECR, SQS, SNS, Secrets, SSM, KMS, IAM, CloudWatch Logs collectors
- [ ] P2-04 RDS/Aurora, S3, Backup, EBS, EFS and initial DynamoDB collectors
- [ ] P2-05 Resource Explorer, AWS Config
- [ ] P2-06 Edge resolvers: SG, IAM, references, ASG→LT→AMI→Snapshot→KMS, Lambda→S3/ECR/Layers, event-source/subscription/WAF associations, Config
- [ ] P2-07 `perpetual scan` + API + UI status
- [ ] P2-08 Read-only IAM policy doc
- [ ] P2-09 moto + Floci (+ Postgres) tests, `examples/ecs-rds`
- [ ] P2-10 Contract suite skeleton + redaction
- [ ] P2-11 Real-AWS checkpoint
- [ ] P2-12 Quota/headroom, Region capability and CloudWatch Metrics collectors with typed facts/contracts
- [ ] P2-13 Coverage/freshness, confirmed absence, atomic snapshots and partial-scan regressions

## P2b Observed dependency evidence

- [ ] P2b-01 Synthetic log generator
- [ ] P2b-02 CloudTrail reader
- [ ] P2b-03 Principal → compute mapping (task role, Lambda role, IRSA, Pod Identity, EC2/ASG instance profile)
- [ ] P2b-04 Flow-log reader + ENI resolution (incl. EC2/ASG + Lambda Hyperplane ENIs)
- [ ] P2b-05 Aggregate-only observations + canary
- [ ] P2b-06 Contradictions, unobserved, external proposals
- [ ] P2b-07 Coverage report
- [ ] P2b-08 Real-AWS checkpoint
- [ ] P2b-09 Ambiguous observation attribution, candidate-set aggregation and review gates

## P3 Stack and service discovery

- [ ] P3-01 Grouping signals (incl. WAF→ALB→TG→ECS/EC2/ASG/Lambda & SNS→SQS→Lambda chains)
- [ ] P3-02 Service suggestion (ECS, EC2/ASG, Lambda; Deployments in P7)
- [ ] P3-03 Roots, closure, shared resources
- [ ] P3-04 Manual stack/service editing
- [ ] P3-05 Discovery confidence

## P3b LLM foundation

- [ ] P3b-01 Provider abstraction, per-role config, capability probe, `perpetual llm configure|test`
- [ ] P3b-02 LangGraph runtime, tools (incl. `web_search`, `web_fetch`), checkpointer, interrupts, validated outputs
- [ ] P3b-03 Fake chat model + recorded web-search/fetch harness + hostile/prompt-injection fixtures
- [ ] P3b-04 Guardrails: opt-in, redaction, query sanitization + untrusted web-content sanitization, `.perpetualignore`, call log
- [ ] P3b-05 Knowledge base: shipped domain docs (`knowledge/domain/`), `sources.yaml`, `kb sync|add|list|show|remove`, agent web-fetch ingestion, hybrid retrieval, citations
- [ ] P3b-06 Skills: format, loader, first-slice skills (incl. EC2/ASG, Lambda, SQS/SNS, WAF)
- [ ] P3b-07 Explainer agent

## P4 DR rule packs

- [ ] P4-01 Finding model, rule registry, rule docs
- [ ] P4-02 ECS, EC2/ASG, Lambda, ECR, SQS, SNS, Secrets/SSM, KMS, IAM packs
- [ ] P4-03 RDS, S3, network, ALB, Route 53, WAF, CloudWatch Logs packs
- [ ] P4-04 Cross-cutting rules
- [ ] P4-05 Readiness dimensions + scoring
- [ ] P4-06 `perpetual assess` + API + UI
- [ ] P4-07 Advisory review agent
- [ ] P4-08 Initial DynamoDB and EFS rules, mechanisms/options and evidence fixtures

## P5 Simulation on discovered stacks

- [ ] P5-01 Mechanisms from rule packs + DR-side resolution
- [ ] P5-02 Explainability
- [ ] P5-03 Fail Region UX on live data
- [ ] P5-04 Real-AWS checkpoint (§87/§88)

## P6 Recovery DAG on live data

- [ ] P6-01 Recovery actions for all packs
- [ ] P6-02 Catalog coverage report
- [ ] P6-03 Shared-resource marking
- [ ] P6-04 Recovery tab in UI

## P7 EKS slice

- [ ] P7-01 EKS collectors
- [ ] P7-02 Kubernetes collector (Level 2)
- [ ] P7-03 NetworkPolicy evidence
- [ ] P7-04 Services from Deployments/StatefulSets
- [ ] P7-05 EKS/EBS rules and reuse of P4 EFS rules with Kubernetes storage integration
- [ ] P7-06 EKS mechanisms + actions
- [ ] P7-07 Level 1 vs 2 confidence
- [ ] P7-08 Fixture B + §89 demo
- [ ] P7-09 Real-AWS checkpoint

## P8 RPO

- [ ] P8-01 RPO estimators
- [ ] P8-02 Stack RPO
- [ ] P8-03 RPO in CLI, API, UI

## P9 Optimizer, cost, planner and DR spec

- [ ] P9-01 Recovery options + strategy mapping
- [ ] P9-02 Candidate generation
- [ ] P9-03 Cost providers, ranges, line items, freshness, total DR budget and unknown handling
- [ ] P9-04 Feasibility gates, budget comparisons and complete-candidate Pareto ranking
- [ ] P9-05 Remediation planner (stack-level deltas)
- [ ] P9-06 `perpetual optimize` + UI + §94 test
- [ ] P9-07 LLM candidate planner
- [ ] P9-08 DR spec, immutable approval digest, supersession/resume checks and export
- [ ] P9-09 Versioned workload inputs, CLI/API/UI editing and cost-input validation (before P9-03)

## P10 IaC transformation

- [ ] P10-01 IaC declaration + resource-to-code mapping (Terraform, Kubernetes)
- [ ] P10-02 Worktree/branch + enforced command allowlist
- [ ] P10-09 Enforced execution isolation and hostile repository fixtures (before P10-03)
- [ ] P10-03 Transformation agent (+ EKS skills)
- [ ] P10-04 Saved-plan verification, authoritative graph, separate evidence stages, deployment prerequisites and artifact hashes
- [ ] P10-05 Change delivery (commits, patch, optional PR)
- [ ] P10-06 Companion fallback templates (incl. EC2/ASG, Lambda, SQS/SNS, basic DynamoDB/EFS recovery, WAF, CloudWatch Logs)
- [ ] P10-07 `perpetual transform` + API + UI
- [ ] P10-08 Demo design-verification evals plus static-only/stale/unknown regression cases

## P11 Runbooks

- [ ] P11-01 Failback metadata
- [ ] P11-02 Failover runbook
- [ ] P11-03 Failback runbook
- [ ] P11-04 Export + surfaces

## P12 Hardening and v0.1

- [ ] P12-01 §100 workflow on sandbox (ECS + EKS)
- [ ] P12-02 Security pass
- [ ] P12-03 Structured logging
- [ ] P12-04 Performance at 5k resources
- [ ] P12-05 Docs
- [ ] P12-06 Release 0.1.0

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
| §28.2 | LLM advisory review | P4-07 |
| §29–§31 | Findings, readiness, status, scoring | P1-07, P4-01, P4-05 |
| §32–§40 | ECS and EKS checks | P4-02, P7-05 |
| §41–§42 | RDS, data gravity | P4-03, P0-04 |
| §43–§46 | Simulator, output, reason chains | P1-04..08, P5-01..03 |
| §47–§50 | Plan, DAG, durations, buffer, RTO | P1-09..13, P6-01..04 |
| §51 | RPO | P8-01..03 |
| §52 | Target vs predicted | P1-14, P8-03 |
| §53 | Drills | backlog (schema only in P0-04) |
| §54–§60 | Optimizer, workload/cost/budget, remediation | P9-01..09 |
| §56.1–§56.3 | Candidate planner, immutable evaluations and DR spec approval | P0-15, P9-07/08, P10-01/04/05 |
| §61–§62.1 | Isolated IaC transformation, staged verification, delivery, companion | P1b-15, P10-01..09 |
| §63–§64 | Runbooks, failback | P11-01..04 |
| §65–§68 | Security, access, secrets, state | P2-01, P2-08, P2b-05, P12-02 |
| §69–§70 | LLM architecture, knowledge base, skills, guardrails, explainer | P3b-01..07, P10-08 |
| §71–§75 | Tech, deployment, layout, persistence | P0-01, P0-07, P1b-06, P1b-13 |
| §76–§76.1 | Scan model, coverage/freshness and confirmed absence | P0-15, P2-01/07/12/13 |
| §77 | Drift | backlog (scans retained from P2) |
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

---

## Decision log

Newest first. Any change to IMPL_PLAN.md, or any deviation from spec.md, goes here first.

| Date | Decision | Reason |
|---|---|---|
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
