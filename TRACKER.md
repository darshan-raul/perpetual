# Perpetual — Tracker

Plan: [IMPL_PLAN.md](IMPL_PLAN.md) (locked 2026-10-25). Spec: [spec.md](spec.md) (revision 3). Update this file at the end of every session.

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
| P4 DR rule packs | [ ] | evidence-backed findings |
| P5 Simulation on discovered stacks | [ ] | survives/fails and why, on sandbox |
| P6 Recovery DAG on live data | [ ] | architecture-derived RTO |
| P7 EKS slice | [ ] | cluster ready, application not |
| P8 RPO | [ ] | stack RPO from data stores |
| P9 Optimizer, cost, remediation | [ ] | whole-stack candidates compared |
| P10 Terraform compiler | [ ] | fmt + validate pass |
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
| Generated Terraform passes fmt + validate | [ ] |
| Docs: README, user guide, IAM policy, rule reference | [ ] |

---

## P0 Engine foundation

- [ ] P0-01 Repo skeleton, `mise.toml` with tasks, uv workspace, ruff, mypy strict, pytest
- [ ] P0-02 import-linter contracts
- [ ] P0-03 GitHub Actions CI
- [ ] P0-04 Domain models + first-slice typed properties + status enums
- [ ] P0-05 Canonical resource IDs
- [ ] P0-06 Typed config + defaults
- [ ] P0-07 Persistence + initial Alembic migration
- [ ] P0-08 Fixture format v1, loader, validator, JSON Schema
- [ ] P0-09 Evidence combination + fingerprints
- [ ] P0-10 Graph overrides (apply, merge, orphan, YAML)
- [ ] P0-11 NetworkX snapshot + traversal helpers
- [ ] P0-12 `perpetual graph` CLI
- [ ] P0-13 Fixtures: ecs-broken, ecs-remediated, cycle, shared-node, deep-path
- [ ] P0-14 CLAUDE.md commands updated

## P1 Simulation and recovery core

- [ ] P1-01 Rule-pack protocol + registry
- [ ] P1-02 First-slice mechanism resolution (strict "reproducible")
- [ ] P1-03 RTO scope classification
- [ ] P1-04 FailureScenario dispatch
- [ ] P1-05 Impact pass
- [ ] P1-06 Recovery pass
- [ ] P1-07 Stack state + review gate
- [ ] P1-08 Reason chains
- [ ] P1-09 Duration catalog v1
- [ ] P1-10 First-slice recovery actions
- [ ] P1-11 DAG builder (template, refinement, decide, stack validation)
- [ ] P1-12 Buffer
- [ ] P1-13 RTO (low/expected/high, UNKNOWN, breakdown)
- [ ] P1-14 Target comparison
- [ ] P1-15 Persist simulation + plan
- [ ] P1-16 `perpetual simulate` / `perpetual plan`
- [ ] P1-17 Spec §92/§93 + simulation tests

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

## P2 AWS discovery (ECS slice)

- [ ] P2-01 Collector protocol, sessions, partial scans
- [ ] P2-02 EC2/VPC, ELB, Route 53, ACM collectors
- [ ] P2-03 ECS, ECR, Secrets, SSM, KMS, IAM collectors
- [ ] P2-04 RDS/Aurora, S3, Backup collectors
- [ ] P2-05 Resource Explorer, AWS Config
- [ ] P2-06 Edge resolvers: SG, IAM, references, Config
- [ ] P2-07 `perpetual scan` + API + UI status
- [ ] P2-08 Read-only IAM policy doc
- [ ] P2-09 moto + Floci tests, `examples/ecs-rds`
- [ ] P2-10 Contract suite skeleton + redaction
- [ ] P2-11 Real-AWS checkpoint

## P2b Observed dependency evidence

- [ ] P2b-01 Synthetic log generator
- [ ] P2b-02 CloudTrail reader
- [ ] P2b-03 Principal → compute mapping
- [ ] P2b-04 Flow-log reader + ENI resolution
- [ ] P2b-05 Aggregate-only observations + canary
- [ ] P2b-06 Contradictions, unobserved, external proposals
- [ ] P2b-07 Coverage report
- [ ] P2b-08 Real-AWS checkpoint

## P3 Stack and service discovery

- [ ] P3-01 Grouping signals
- [ ] P3-02 Service suggestion
- [ ] P3-03 Roots, closure, shared resources
- [ ] P3-04 Manual stack/service editing
- [ ] P3-05 Discovery confidence

## P4 DR rule packs

- [ ] P4-01 Finding model, rule registry, rule docs
- [ ] P4-02 ECS, ECR, Secrets/SSM, KMS, IAM packs
- [ ] P4-03 RDS, S3, network, ALB, Route 53 packs
- [ ] P4-04 Cross-cutting rules
- [ ] P4-05 Readiness dimensions + scoring
- [ ] P4-06 `perpetual assess` + API + UI

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
- [ ] P7-05 EKS, EBS, EFS rule packs
- [ ] P7-06 EKS mechanisms + actions
- [ ] P7-07 Level 1 vs 2 confidence
- [ ] P7-08 Fixture B + §89 demo
- [ ] P7-09 Real-AWS checkpoint

## P8 RPO

- [ ] P8-01 RPO estimators
- [ ] P8-02 Stack RPO
- [ ] P8-03 RPO in CLI, API, UI

## P9 Optimizer, cost and remediation

- [ ] P9-01 Recovery options + strategy mapping
- [ ] P9-02 Candidate generation
- [ ] P9-03 Cost providers + confidence
- [ ] P9-04 Evaluation + Pareto
- [ ] P9-05 Remediation planner (stack-level deltas)
- [ ] P9-06 `perpetual optimize` + UI + §94 test

## P10 Terraform compiler

- [ ] P10-01 Templates per mechanism
- [ ] P10-02 Variables, comments, assumptions
- [ ] P10-03 fmt + validate tests
- [ ] P10-04 CLI, API, UI

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
| §15–§15.3 | Resource model, identity, external, typed props | P0-04, P0-05, P1b-02, P1b-10 |
| §16 | Evidence | P0-04, P0-09 |
| §17–§20 | Graph, edges, relationships | P0-04, P0-11 |
| §21–§22 | Evidence and confidence | P0-09, P2-06 |
| §23 | Review and editing, review gate | P0-10, P1-07, P1b-09, P1b-10 |
| §24–§25 | Stacks, services, discovery | P0-04, P3-01..05, P7-04 |
| §24.1 | RTO scope | P1-03, P1-05, P4-05 |
| §26 | Requirement | P0-04, P1b-11 |
| §27–§27.1 | Strategies, mechanisms, overlay | P1-02, P5-01, P9-01 |
| §28–§28.1 | Rule packs, cross-cutting | P1-01, P4-02..04, P7-05 |
| §29–§31 | Findings, readiness, status, scoring | P1-07, P4-01, P4-05 |
| §32–§40 | ECS and EKS checks | P4-02, P7-05 |
| §41–§42 | RDS, data gravity | P4-03, P0-04 |
| §43–§46 | Simulator, output, reason chains | P1-04..08, P5-01..03 |
| §47–§50 | Plan, DAG, durations, buffer, RTO | P1-09..13, P6-01..04 |
| §51 | RPO | P8-01..03 |
| §52 | Target vs predicted | P1-14, P8-03 |
| §53 | Drills | backlog (schema only in P0-04) |
| §54–§60 | Optimizer, cost, remediation | P9-01..06 |
| §61–§62 | Terraform | P10-01..04 |
| §63–§64 | Runbooks, failback | P11-01..04 |
| §65–§68 | Security, access, secrets, state | P2-01, P2-08, P2b-05, P12-02 |
| §69–§70 | LLM | backlog |
| §71–§75 | Tech, deployment, layout, persistence | P0-01, P0-07, P1b-06, P1b-13 |
| §76 | Scan model | P2-01, P2-07 |
| §77 | Drift | backlog (scans retained from P2) |
| §78–§79 | API, CLI | P0-12, P1-16, P1b-04, P2-07, P4-06, P9-06 |
| §80–§84 | UI | P1b-08..12, P5-02..03, P6-04 |
| §85–§89 | Fixtures and demos | P0-13, P7-08, P5-04, P7-09 |
| §90–§94 | Testing, test environments | P1-17, P2-09..10, P2b-01, P9-06 |
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

---

## Decision log

Newest first. Any change to IMPL_PLAN.md, or any deviation from spec.md, goes here first.

| Date | Decision | Reason |
|---|---|---|
| 2026-10-25 | Plan locked. Alembic from P0 instead of P1b. | Avoid writing an unmanaged SQLite schema that later needs a migration path. |
| 2026-10-25 | EKS slice is P7, after the ECS slice reaches a live recovery DAG (P6). Spec Phase 2 and 4 EKS items move there. | Spec §105 says complete the ECS slice first. |
| 2026-10-25 | Typer + Rich for the CLI; TanStack Router for the UI; ELK for graph layout; Jinja2 for Terraform templates. | Spec leaves these open. |

---

## Session log

Newest first. Each entry: date, what was done, carry-over for the next session.

### 2026-10-25 — Planning

- Spec revision 3 written and pushed (stack-level DR, evidence-based graph editing, review gate, local-first, test environments).
- IMPL_PLAN.md, TRACKER.md and CLAUDE.md created.
- **Carry-over:** start P0-01. Resolve nothing else first; Q1–Q6 are needed later.
