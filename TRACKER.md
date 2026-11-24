# Perpetual — Tracker

Plan: [IMPL_PLAN.md](IMPL_PLAN.md) (locked 2026-10-25; milestones & scope updated 2026-11-24). Spec: [spec.md](spec.md) & [`docs/spec/`](docs/spec/) (revision 4). Update this file at the end of every session.

A task is done when its code, tests, and [readability checklist](docs/code/readability.md#review-before-completing-a-task) review are complete. During active M0/M1 iteration, update the living code wiki ([`docs/code/`](docs/code/README.md)) at phase boundaries (end of P0, P1, P1c, P2, etc.) rather than every subtask (from M2 onward, update in the same change). Strict just-in-time modeling rule: do not build schemas, database tables, or helpers for future milestones until the consumer task is next in line.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` dropped (needs a decision-log entry). A task with lettered subtasks (e.g. P0-04a) is done when all its subtasks are done.

**Current focus:** M0 PoC · **P1 complete** · next phase **P1c** (PoC compile loop: `P1c-01..P1c-05`).

## Milestones

| Milestone | Release | Phases | Status | Exit (demo) |
|---|---|---|---|---|
| M0 PoC | — | P0 (minimal P0-15), P1, P1c | [~] | `perpetual poc fix --fixture ecs-broken`: generated Terraform + recovery script, re-simulated stack matches `ecs-remediated` |
| M1 Alpha | — | P1b-02/03, CLI-only P2 (ECS + RDS slice), P2b (CloudTrail-only), P3, P4 (ECS + RDS + cross-cutting), P5, P6 (CLI), P8 (CLI) | [ ] | `perpetual scan -> simulate -> plan` on a real sandbox ECS + RDS stack produces its normalized graph, blockers, RTO and RPO in the CLI |
| M2 MVP | v0.1 | P1b (P1b-01, P1b-15, P1b-04..09, P1b-11..14 + deferred M1 UI views incl. P6-04), P9 (StaticCostProvider + 3–4 discrete presets), P10 (ECS + RDS companion Terraform + suggested edits + supplied-plan verification), P11 (runbooks + prereq/Python recovery scripts), P12 | [ ] | spec §100 workflow, deterministic, for ECS + RDS: read-only React Flow viewer + review/confirm/reject panel (structural edits in YAML overrides) -> preset DR spec -> companion Terraform + suggested edits + runbooks/scripts on a branch or PR -> verified with a supplied saved plan -> observed READY after deploy |
| M3 Expansion | v0.2 | P0-15b, P1b-10, P2b-04/09, P2c (EC2/ASG, Lambda, SQS/SNS, CloudFront, WAF, EBS/EFS, DynamoDB), P7 (EKS), P9 (combinatorial search + AWSPricingProvider), P11-07 (ARC Region switch plan compiler) | [ ] | full multi-service deterministic coverage incl. EKS (§89), Flow Logs, interactive structural UI editor, combinatorial optimizer + live AWS pricing, and ARC Region switch plan compiler |
| M4 Agents | v0.3 | P3b, P4-07, P9-07, P10 (agentic PR tasks), P13 | [ ] | LLM advisor, planner and in-place IaC transformation in an isolated runner; v0.3 gates pass |
| M5 Proven | v0.4 | P14 | [ ] | a game day or ARC execution report takes a sandbox stack to PROVEN |
| M6 Production | v1.0 | P15 | [ ] | installable from PyPI/Homebrew, upgradeable, audited, documented supported-service matrix |

## Phases

| Phase | Milestone | Status | Exit criterion |
|---|---|---|---|
| P0 Engine foundation | M0 | [x] | `perpetual graph --fixture ecs-broken` prints graph + overlay; minimal P0-15 hashes/manifests |
| P1 Simulation and recovery core | M0 | [x] | §87 reproduced on fixtures; remediated fixture RECOVERABLE |
| P1c PoC compile loop | M0 | [ ] | fixture fix → Terraform + script → re-simulated RECOVERABLE |
| P1b-02/03 Normalization & identity | M1 | [ ] | recorded-AWS normalizers + identity resolution feed P2 collectors |
| P2 AWS discovery (ECS + RDS slice, CLI) | M1 | [ ] | `perpetual scan` on sandbox → normalized graph |
| P2b Observed evidence (CloudTrail-only, CLI) | M1 | [ ] | every edge shows basis; contradictions listed |
| P3 Stack discovery (CLI) | M1 | [ ] | "checkout" is one stack with services |
| P4 DR rule packs (ECS + RDS slice, CLI) | M1 (P4-07 M4) | [ ] | evidence-backed findings in CLI |
| P5 Simulation on discovered stacks (CLI) | M1 | [ ] | survives/fails and why, on sandbox via CLI |
| P6 Recovery DAG on live data (CLI) | M1 (P6-04 M2) | [ ] | architecture-derived RTO via CLI |
| P8 RPO (CLI) | M1 (UI M2) | [ ] | stack RPO from data stores via CLI |
| P1b Terraform import, API, read-only UI | M2 | [ ] | saved-plan import → read-only React Flow viewer + review/confirm/reject → simulate/findings/recovery/RPO views |
| P9 Optimizer, cost and DR spec (presets) | M2 (full/live M3; P9-07 M4) | [ ] | `StaticCostProvider` + 3–4 presets compared; approved DR spec for ECS + RDS |
| P10 IaC delivery (ECS + RDS) | M2 / M4 | [ ] | v0.1: ECS + RDS companion + suggested edits verified with supplied plan; v0.3: in-place edits verified in isolation |
| P11 Recovery artifacts (runbooks + scripts) | M2 (P11-07 M3) | [ ] | runbooks, prereq scripts, and Python recovery scripts from one DAG for ECS + RDS |
| P12 Hardening, v0.1 | M2 | [ ] | §109 answer for a real ECS + RDS stack; 0.1.0 released |
| P0-15b Schema-migration upgrade registry | M3 | [ ] | registered payload schema upgrades across persisted versions |
| P1b-10 Interactive structural UI editor | M3 | [ ] | add/delete edges/nodes and edit stack/service/groups in UI |
| P2b-04/09 Flow Logs & ambiguous review UI | M3 | [ ] | time-aware ENI resolution + candidate-set review UI |
| P2c Expanded services | M3 | [ ] | EC2/ASG, Lambda, SQS/SNS, CloudFront, WAF, EBS/EFS, DynamoDB scanned and assessed |
| P7 EKS slice | M3 | [ ] | cluster ready, application not (§89) |
| P9 (full) + P11-07 Combinatorial optimizer & ARC | M3 | [ ] | combinatorial search + `AWSPricingProvider` + ARC Region switch plan compiler |
| P3b LLM foundation | M4 | [ ] | `perpetual llm test` + cited explainer answer |
| P13 Agents integration, v0.3 | M4 | [ ] | v0.3 agent gates pass; 0.3.0 released |
| P14 Proven readiness, v0.4 | M5 | [ ] | PROVEN tier from imported drill evidence; 0.4.0 released |
| P15 Production, v1.0 | M6 | [ ] | 1.0.0 released with support policy |

## Release gates

### M0 PoC

| Gate | Status |
|---|---|
| §87 broken ECS demo: NOT DR READY with blockers (fixture) | [x] |
| §88 remediated ECS demo: RECOVERABLE (fixture) | [x] |
| §93 RTO tests (40 / 48 / 49.5) | [x] |
| PoC loop: generated Terraform passes fmt + validate; recovery script passes lint and a `moto` dry run (plus `aws/aws-emulator` integration once wired); re-simulation matches §88 | [ ] |
| Lightweight `P0-15`: canonical hashes, immutable manifests, and versioned fixture inputs pass | [x] |
| Import contracts green | [x] |

### M1 Alpha (CLI)

| Gate | Status |
|---|---|
| `perpetual scan -> simulate -> plan` runs end-to-end on a real sandbox AWS ECS + RDS stack (ECS, RDS, S3, ECR, Secrets/SSM, KMS, IAM, ALB, Route 53, VPC) | [ ] |
| §87/§88 reproduced on sandbox AWS via CLI | [ ] |
| CloudTrail-only `P2b` evidence, contradiction/unobserved reporting, and canary test pass | [ ] |
| `aws/aws-emulator` (`aws-emulator`) integration tests for `examples/ecs-rds/` and opt-in `tests/contract/` real-AWS tests pass | [ ] |
| Partial scan, confirmed absence, stale metrics and cross-account skew regressions (§76.1) | [ ] |

### v0.1 (M2 MVP)

| Gate | Status |
|---|---|
| ECS + RDS end-to-end §87/§88 reproduced on sandbox AWS through API/UI | [ ] |
| §94 preset optimizer test (`StaticCostProvider` + 3–4 discrete stack presets: Backup/Restore, Pilot Light, Warm Standby) | [ ] |
| Review gate: no READY with unreviewed low-confidence required edges; read-only React Flow viewer + review/confirm/reject panel works; structural edits stay in YAML overrides (`P0-10`) | [ ] |
| Canary test: no secrets, env values or raw logs persisted | [ ] |
| `uv tool install` + `perpetual ui` on a clean machine | [ ] |
| ECS + RDS demo design passes verification from a supplied saved plan, with explicit deployment prerequisites; observed READY requires fresh post-deployment evidence (§61.1) | [ ] |
| Companion Terraform (ECS + RDS) passes fmt + validate; it creates new resources only, and changes to managed resources are suggested edits by address (§62.1) | [ ] |
| Perpetual never runs `terraform plan` or any repository tool in v0.1 (§61.1) | [ ] |
| Docs: README, user guide, IAM policy, rule reference | [ ] |
| Planned snapshot lifecycle/unknown/root-identity regressions (§15.4) | [ ] |
| Partial scan, confirmed absence, stale metrics and cross-account skew regressions (§76.1) | [ ] |
| Readiness decision table and recoverable-but-RPO-FAIL case (§31) | [ ] |
| Coverage registry connects every enabled rule/estimator to typed producers/actions/tests (plan §3.5) | [ ] |
| Approval supersession, stale checkpoint and post-verification edit regressions (§56.3) | [ ] |
| ALL/ANY/quorum selected-path and shared-prerequisite regressions (§19.1) | [ ] |
| Workload/price unknowns, total cost and budget bounds regressions (§59.1) | [ ] |
| Saved-plan JSON accepted; UI event stream rejected (§15.4) | [ ] |
| All §90.2 v0.1 review regressions pass; no static-only or conditional design labeled observed READY | [ ] |
| Runbooks, prerequisite scripts, and Python recovery scripts come from one DAG with matching step numbers; scripts pass lint + `moto`/`aws-emulator` dry run (§63) | [ ] |
| No generated script is executed by Perpetual (§63, §101) | [ ] |
| No LLM dependency installed or called in v0.1 | [ ] |

### v0.2 (M3 Expansion)

| Gate | Status |
|---|---|
| `P0-15b` schema-migration upgrade registry upgrades persisted payloads across schema versions | [ ] |
| `P1b-10` interactive structural graph-editor UI (add/delete edges/nodes, stack/service/group edits) passes Playwright + API regressions | [ ] |
| `P2b-04`/`P2b-09` Flow Logs + time-aware ENI resolution and ambiguous candidate-set review UI pass; ambiguous shared-role/ENI observations cannot gain exact-edge confidence (§14.1) | [ ] |
| `P2c` services (EC2/ASG, Lambda, SQS/SNS, CloudFront, WAF, EBS/EFS, DynamoDB) scanned, assessed, simulated, costed, and delivered end-to-end | [ ] |
| `P7` §89 EKS demo: cluster PASS, application FAIL (fixture and reproduced on sandbox); `examples/eks-rds` passes supplied-plan verification | [ ] |
| `P9` full combinatorial candidate search, Pareto ranking, and `AWSPricingProvider` pass §94 tests | [ ] |
| `P11-07` ARC Region switch plan compiler emits `aws_arcregionswitch_plan` from the same DAG with matching step numbers, no alarm triggers, and method-specific RTO/cost (§63.3) | [ ] |

### v0.3 (M4 Agents)

| Gate | Status |
|---|---|
| Hostile-LLM tests: no state, number or verdict upgraded without verification | [ ] |
| No apply/destroy/state/kubectl apply reachable from the transformer | [ ] |
| Isolated runner denies executable data sources/plugins, escapes, credential theft, egress and cloud mutation (§61) | [ ] |
| LLM call log shows no state, secrets, env values or raw logs sent | [ ] |
| In-place edits on both demos pass design verification; companion path still works with LLM disabled | [ ] |

### v0.4 (M5 Proven)

| Gate | Status |
|---|---|
| A sandbox game day (script log) and an ARC execution report each produce a PROVEN result for the matching scan and design digest | [ ] |
| Drift after a drill demotes PROVEN/CONFIGURED as specified (§77) | [ ] |
| Imported drill data stores timings only; canary test passes | [ ] |

### v1.0 (M6 Production)

| Gate | Status |
|---|---|
| Upgrade from 0.1/0.2/0.3/0.4 databases and config without data loss | [ ] |
| Install from PyPI and Homebrew on Linux and macOS | [ ] |
| External security review findings closed | [ ] |
| Published supported-service matrix matches the coverage registry | [ ] |

---

## M0 PoC

### P0 Engine foundation

- [x] P0-01 Repo skeleton, `mise.toml` with tasks, root-installable `uv` workspace, `__init__.py` subpackage stubs, ruff, mypy strict, pytest
- [x] P0-02 import-linter contracts
- [x] P0-03 GitHub Actions CI
- [x] P0-04a Core graph and stack models, status enums
- [x] P0-04b Typed properties: compute and containers
- [x] P0-04c Typed properties: data and storage
- [x] P0-04d Typed properties: messaging, network, edge and supporting services
- [x] P0-04e Out-of-scope, external and generic properties; quota/availability/metric facts
- [x] P0-04f Evaluation, coverage, workload/cost, prerequisite, verification and drill models; operator access profile; resolved-observation model (exact | ambiguous, §14.1)
- [x] P0-05 Canonical resource IDs
- [x] P0-06 Typed config + defaults
- [x] P0-07 Persistence + initial Alembic migration + SQLite/PostgreSQL dialect compilation check
- [x] P0-08 Fixture format v1, loader, validator, JSON Schema
- [x] P0-09 Evidence combination + fingerprints
- [x] P0-10 Graph overrides (apply, merge, orphan, YAML)
- [x] P0-11 NetworkX snapshot + traversal helpers
- [x] P0-15 Lightweight immutable evaluation/snapshot manifests, canonical hashes, and versioned fixture inputs (before P0-12/13; payload schema-migration upgrade registry deferred to M3 `P0-15b`)
- [x] P0-12 `perpetual graph` CLI
- [x] P0-13 Fixtures: ecs-broken, ecs-remediated, cycle, shared-node, deep-path
- [x] P0-14 CLAUDE.md commands updated

### P1 Simulation and recovery core

- [x] P1-01 Rule-pack protocol + registry
- [x] P1-02 First-slice mechanism resolution on real `DRRulePack` classes (strict "reproducible")
- [x] P1-03 RTO scope classification
- [x] P1-04 FailureScenario dispatch
- [x] P1-05 Impact pass
- [x] P1-06 Recovery pass
- [x] P1-07 Stack state + readiness composition, target/evidence/review gates and evaluation kind
- [x] P1-08 Reason chains
- [x] P1-09 Duration catalog v1 (incl. generic fallback action types + per-resource duration overrides)
- [x] P1-10 First-slice recovery actions (+ fallback actions for user-accepted unmodeled mechanisms)
- [x] P1-11 DAG builder (template, refinement, decide, stack validation)
- [x] P1-12 Buffer
- [x] P1-13 RTO (low/expected/high, UNKNOWN, breakdown)
- [x] P1-14 Target comparison
- [x] P1-15 Persist simulation + plan + recovery requirements
- [x] P1-16 `perpetual simulate` / `perpetual plan`
- [x] P1-17 Spec §92/§93 + simulation tests
- [x] P1-18 ALL/ANY/quorum selection, shared prerequisites and readiness decision-table regressions

### P1c PoC compile loop

- [ ] P1c-01 Modeled DR change set applied to `ecs-broken` (ECR replication, RDS cross-Region replica, multi-Region KMS key)
- [ ] P1c-02 Companion Terraform templates for the three changes; fmt + validate
- [ ] P1c-03 Re-simulate the modeled snapshot; match `ecs-remediated`
- [ ] P1c-04 One Python recovery script (RDS promote, ECS scale, DR health check); `moto` dry run (plus `aws/aws-emulator` integration once wired)
- [ ] P1c-05 `perpetual poc fix` CLI + README demo

## M1 Alpha (CLI-only ECS + RDS vertical slice)

### P1b Normalizers and identity (CLI foundation; API/UI in M2)

- [ ] P1b-02 Identity resolution across sources
- [ ] P1b-03 Recorded-AWS normalizers + importer (`perpetual import-aws-fixture`)

### P2 AWS discovery (ECS + RDS slice, CLI-only)

- [ ] P2-01 Collector protocol, sessions (incl. global/`us-east-1` pass), partial scans
- [ ] P2-02b VPC, subnets, route tables, NAT, IGW, endpoints, TGW attachments, ENIs, security groups
- [ ] P2-02c ELB (ALB/NLB, listeners, target groups)
- [ ] P2-02d Route 53 (zones, records, health checks, Accelerated Recovery) and read-only ARC discovery (routing controls, Region switch plans + evaluation, legacy readiness checks)
- [ ] P2-02e ACM (incl. `us-east-1`)
- [ ] P2-03a ECS
- [ ] P2-03c ECR (replication, image metadata)
- [ ] P2-03e Secrets Manager and SSM parameters (metadata, primary + DR)
- [ ] P2-03f KMS, IAM, IAM Identity Center Regions
- [ ] P2-03g CloudWatch Logs
- [ ] P2-04a RDS/Aurora (instances, clusters, replicas, snapshots)
- [ ] P2-04b S3 and AWS Backup
- [ ] P2-05 Resource Explorer, AWS Config
- [ ] P2-06 Edge resolvers: SG, IAM, references, Config (ECS + RDS slice in M1; EC2/Lambda/messaging/WAF chains in M3 · P2c)
- [ ] P2-07 `perpetual scan` CLI (API + UI status in M2)
- [ ] P2-08 Read-only IAM policy doc
- [ ] P2-09 `botocore.stub.Stubber` / `moto` unit error-injection tests + `docker-compose.yml` with `aws/aws-emulator` (`aws-emulator`) and Postgres + `examples/ecs-rds/` applied to `aws-emulator` and scanned in CI
- [ ] P2-10 Contract suite skeleton (`tests/contract/`) + redaction
- [ ] P2-12 Quota/headroom, Region capability and CloudWatch Metrics collectors with typed facts/contracts; facts persisted
- [ ] P2-13 Coverage/freshness, confirmed absence, atomic snapshots and partial-scan regressions
- [ ] P2-11 Real-AWS checkpoint (after P2-12/13)

### P2b Observed dependency evidence (CloudTrail-only subset, CLI-only)

- [ ] P2b-01 Synthetic log generator (CloudTrail fixtures in M1; Flow-log v2/v5 fixtures in M3 · P2b-04)
- [ ] P2b-02 CloudTrail reader (S3 + `LookupEvents`; Lake/Athena in backlog)
- [ ] P2b-03 Principal → compute mapping (ECS task role in M1; Lambda role and EC2/ASG instance profile in M3 · P2c; IRSA/Pod Identity in M3 · P7)
- [ ] P2b-05 Aggregate-only observations + canary
- [ ] P2b-06 Contradictions, unobserved, external proposals
- [ ] P2b-07 Coverage report (CLI in M1; UI view in M2)
- [ ] P2b-08 Real-AWS checkpoint (real CloudTrail → observed edges in M1; Flow Logs in M3 · P2b-04)

### P3 Stack and service discovery (CLI-only)

- [ ] P3-01 Grouping signals (ECS + RDS chains in M1; WAF/EC2/Lambda/SNS→SQS chains in M3 · P2c)
- [ ] P3-02 Service suggestion (ECS in M1; EC2/ASG and Lambda in M3 · P2c; Deployments in M3 · P7)
- [ ] P3-03 Roots, closure, shared resources
- [ ] P3-04 Manual stack/service editing (CLI `perpetual stacks ...` in M1; UI editing in M3 · P1b-10)
- [ ] P3-05 Discovery confidence

### P4 DR rule packs (ECS + RDS slice + cross-cutting, CLI-only)

- [ ] P4-01 Finding model, rule registry, rule docs
- [ ] P4-02a ECS pack
- [ ] P4-02d ECR pack
- [ ] P4-02f Secrets/SSM pack
- [ ] P4-02g KMS and IAM packs
- [ ] P4-03a RDS/Aurora pack
- [ ] P4-03b S3 pack
- [ ] P4-03c Network pack
- [ ] P4-03d ALB/NLB, ACM
- [ ] P4-03e Route 53 pack (data vs control plane)
- [ ] P4-03g CloudWatch Logs pack (scope-aware)
- [ ] P4-04a Cross-cutting: XREG-CONFIG-001, XREG-IAM-002, XREG-KMS-003, CTRL-PLANE-001, QUOTA-DR-001, REGION-SVC-001
- [ ] P4-04b Cross-cutting: ARC-RS-001, SSM-PARITY-001
- [ ] P4-04c Cross-cutting: OPS-ACCESS-001/002 + `operator_access` loader
- [ ] P4-05 Readiness dimensions + scoring
- [ ] P4-06 `perpetual assess` CLI (API + UI findings tab in M2)

### P5 Simulation on discovered stacks (CLI-only)

- [ ] P5-01 Mechanisms from rule packs + DR-side resolution
- [ ] P5-02 Explainability
- [ ] P5-03 Fail Region CLI on live data (UI view in M2)
- [ ] P5-04 Real-AWS checkpoint (§87/§88)

### P6 Recovery DAG on live data (CLI-only)

- [ ] P6-01 Recovery actions for ECS + RDS packs (`P2c` packs in M3)
- [ ] P6-02 Catalog coverage report
- [ ] P6-03 Shared-resource marking

### P8 RPO (CLI-only)

- [ ] P8-01 RPO estimators (RDS/Aurora + S3 in M1; DynamoDB/EFS/EBS/SQS in M3 · P2c)
- [ ] P8-02 Stack RPO
- [ ] P8-03 RPO in CLI (API + UI in M2)

## M2 MVP (v0.1 — ECS + RDS end-to-end)

### P1b Terraform importer, API and read-only UI (moved after M1 CLI slice; IDs unchanged)

- [ ] P1b-01 Terraform saved-plan/state JSON importer (§15.4)
- [ ] P1b-15 Authoritative planned snapshots: lifecycle changes, unknowns, stale-proof invalidation and root identities (before the API and UI)
- [ ] P1b-04 FastAPI routes (incl. deferred M1 API routes for P2-07, P4-06, P8-03)
- [ ] P1b-05 OpenAPI → TS types, drift check
- [ ] P1b-06 `perpetual ui` (localhost, host flag warning)
- [ ] P1b-07 Web scaffold
- [ ] P1b-08 Graph viewer (read-only React Flow: whole graph, grouping by stack/service/VPC, filters, ELK layout, edge style by basis, muted out-of-scope nodes)
- [ ] P1b-09 Graph review panel (evidence panel, review queue, contradictions and unobserved lists, confirm/reject; structural edits stay in YAML overrides P0-10)
- [ ] P1b-11 Home + stack screen (incl. P2-07 scan status, P2b-07 coverage, P4-06 findings, P8-03 RPO)
- [ ] P1b-12 Simulation view (incl. P5-03 Fail Region UX)
- [ ] P6-04 Recovery tab in UI (DAG view, critical path, buffer lines, targets vs predicted)
- [ ] P1b-13 Packaging (UI in wheel)
- [ ] P1b-14 Playwright smoke test

### P9 Optimizer, cost and DR spec (v0.1 preset mode)

- [ ] P9-09 Versioned workload inputs, CLI/API/UI editing and cost-input validation (before P9-03)
- [ ] P9-01 Recovery options + strategy mapping (ECS + RDS slice)
- [ ] P9-02 Preset-based candidate evaluation (3–4 discrete stack presets: Backup/Restore, Pilot Light, Warm Standby evaluated through the simulator; full combinatorial search deferred to M3)
- [ ] P9-03 `StaticCostProvider` (versioned price table for ECS + RDS components), cost ranges, line items, freshness, total DR budget and unknown handling (`AWSPricingProvider` deferred to M3)
- [ ] P9-04 Feasibility gates, budget comparisons and preset Pareto ranking
- [ ] P9-05 Remediation planner (stack-level deltas)
- [ ] P9-06 `perpetual optimize` + UI + §94 test
- [ ] P9-08 DR spec (execution method = laptop-run scripts in v0.1, deterministic rationale), immutable approval digest, supersession/resume checks and export

### P10 IaC delivery (v0.1 — ECS + RDS)

- [ ] P10-02 Worktree/branch management and approved-baseline checks (no repository tool execution)
- [ ] P10-06a Companion templates: network, KMS, IAM
- [ ] P10-06b Companion templates: data (RDS/Aurora, S3; DynamoDB/EFS moved to M3 · P2c)
- [ ] P10-06c Companion templates: compute and images (ECS, ECR; EC2/ASG, Lambda moved to M3 · P2c)
- [ ] P10-06d Companion templates: edge and supporting (Route 53, Secrets, CloudWatch Logs; SQS/SNS, WAF moved to M3 · P2c)
- [ ] P10-10 Suggested edits by Terraform address for resources the user's IaC manages
- [ ] P10-04 Verification: static checks of generated code, supplied saved-plan import, provenance, re-evaluation and stage separation
- [ ] P10-05 Change delivery (commits, patch, optional PR)
- [ ] P10-07 `perpetual transform` + API + UI
- [ ] P10-11 Demo design-verification tests from supplied plans (`examples/ecs-rds`) plus static-only/stale/unknown regressions (`examples/eks-rds` deferred to M3 · P7)

### P11 Recovery artifacts (v0.1 — runbooks + scripts)

- [ ] P11-01 Failback metadata
- [ ] P11-02 Failover runbook (explanatory)
- [ ] P11-03 Failback runbook (explanatory)
- [ ] P11-04 Export + surfaces
- [ ] P11-05 Prerequisite scripts and SOPs
- [ ] P11-06 Recovery scripts (failover + failback; `moto` dry run + `aws/aws-emulator` integration)
- [ ] P11-08 Method-specific RTO and cost (human-check gates for laptop-run scripts in v0.1; ARC method RTO/cost in M3 · P11-07)

### P12 Hardening and v0.1

- [ ] P12-01 §100 workflow on sandbox (ECS + RDS)
- [ ] P12-02 Security pass (deterministic scope)
- [ ] P12-03 Structured logging
- [ ] P12-04 Performance at 5k resources
- [ ] P12-05a Docs: README and install
- [ ] P12-05b Docs: user guide (scan → review → simulate → design → deliver → run recovery)
- [ ] P12-05c Docs: read-only IAM policy and `operator_access`
- [ ] P12-05d Docs: rule reference and fixture format
- [ ] P12-06 Release 0.1.0

## M3 Expansion (v0.2 — Post-v0.1 deterministic expansion)

### Deferred foundation, UI & Flow Logs (IDs unchanged)

- [ ] P0-15b Payload schema-migration upgrade registry across persisted model schema versions (split from M0 `P0-15`)
- [ ] P1b-10 Graph editor: interactive structural edits (add edge by drag, delete edge, add external/placeholder node, change stack/service membership and RTO scope in UI; dependency-group editing/validation)
- [ ] P2b-04 Flow-log reader + time-aware ENI resolution (S3 and CloudWatch Logs, v5 fields, EC2/ASG + Lambda Hyperplane ENIs)
- [ ] P2b-09 Ambiguous observation review UI & flow, candidate-set aggregation and real-AWS flow-log checkpoint (engine model in P0-04f; review gate in P1-07)

### P2c Expanded services

- [ ] P2-02a EC2 instances, Auto Scaling groups, launch templates, AMIs
- [ ] P2-02f CloudFront, WAFv2 (REGIONAL + CLOUDFRONT)
- [ ] P2-03b Lambda (functions, layers, event-source mappings)
- [ ] P2-03d SQS and SNS
- [ ] P2-04c EBS and EFS
- [ ] P2-04d Initial DynamoDB
- [ ] P4-02b EC2/ASG pack (AMI copy, snapshot KMS)
- [ ] P4-02c Lambda pack (DR package/image/layers, event-source mappings)
- [ ] P4-02e SQS and SNS packs
- [ ] P4-03f WAF pack (primary vs DR parity)
- [ ] P4-03h CloudFront origin failover
- [ ] P4-08 Initial DynamoDB and EFS rules, mechanisms/options and evidence fixtures
- [ ] P2c-01 Expanded-service parts of P2-06, P2b-03/04, P3-01/02, P6-01, P8-01, plus P10-06 companion templates for EC2/ASG, Lambda, SQS/SNS, WAF, DynamoDB, EFS
- [ ] P2c-02 `examples/` expanded stack + `moto` / `aws/aws-emulator` tests + real-AWS checkpoint

### P7 EKS slice

- [ ] P7-01 EKS collectors
- [ ] P7-02 Kubernetes collector (Level 2)
- [ ] P7-03 NetworkPolicy evidence
- [ ] P7-04 Services from Deployments/StatefulSets
- [ ] P7-05 EKS/EBS rules and reuse of P4 EFS rules with Kubernetes storage integration
- [ ] P7-06 EKS mechanisms + actions
- [ ] P7-07 Level 1 vs 2 confidence
- [ ] P7-08 Fixture B + §89 demo
- [ ] P7-09 Real-AWS checkpoint (+ `examples/eks-rds` supplied-plan verification in `P10-11`)

### Full Optimizer, live AWS pricing & ARC Region switch compiler

- [ ] P9-02 (full) Full combinatorial candidate search across all service options and variants
- [ ] P9-03 (`AWSPricingProvider`) Live AWS pricing provider covering all `P2c` + EKS + ARC components
- [ ] P11-07 ARC Region switch plan compiler (`aws_arcregionswitch_plan`) + ARC method RTO/cost (`P11-08` extension)

## M4 Agents (v0.3)

### P3b LLM foundation

- [ ] P3b-01 Provider abstraction, per-role config, capability probe, `perpetual llm configure|test`
- [ ] P3b-02 LangGraph runtime, tools (incl. `web_search`, `web_fetch`), checkpointer, interrupts, validated outputs
- [ ] P3b-03 Fake chat model + recorded web-search/fetch harness + hostile/prompt-injection fixtures
- [ ] P3b-04 Guardrails: opt-in, redaction, query sanitization + untrusted web-content sanitization, `.perpetualignore`, call log
- [ ] P3b-05 Knowledge base: shipped domain docs (`knowledge/domain/`), `sources.yaml`, `kb sync|add|list|show|remove`, agent web-fetch ingestion, hybrid retrieval, citations
- [ ] P3b-06 Skills: format, loader, first-slice and expanded skills (incl. EC2/ASG, Lambda, SQS/SNS, WAF)
- [ ] P3b-07 Explainer agent

### LLM tasks in earlier phases

- [ ] P4-07 Advisory review agent
- [ ] P9-07 LLM candidate planner

### P10 IaC delivery (v0.3)

- [ ] P10-01 IaC declaration + resource-to-code mapping (Terraform, Kubernetes)
- [ ] P10-09 Enforced execution isolation and hostile repository fixtures (before P10-03)
- [ ] P10-03 Transformation agent (+ EKS skills)
- [ ] P10-12 Runner-executed saved plans inside the isolation boundary
- [ ] P10-08 Transformation evals plus hostile/stale/static-only regression cases

### P13 Agents integration and v0.3

- [ ] P13-01 Wire advisor, planner and transformer into CLI/API/UI behind the opt-in
- [ ] P13-02 In-place edits replace suggested edits when an IaC repo is declared; companion stays the fallback
- [ ] P13-03 LLM-cited DR spec rationale
- [ ] P13-04 v0.3 security pass (LLM data, isolation, hostile fixtures) on the sandbox
- [ ] P13-05 Docs: LLM setup, providers, what is sent
- [ ] P13-06 Release 0.3.0

## M5 Proven (v0.4)

### P14 Proven readiness

- [ ] P14-01 Drill model wiring and recovery-script log import
- [ ] P14-02 ARC Region switch execution-report import (opt-in, timings only)
- [ ] P14-03 FIS and Resilience Hub test-result import
- [ ] P14-04 PROVEN tier in readiness, reports and UI
- [ ] P14-05 Duration-catalog calibration from drills
- [ ] P14-06 Resilience Hub importer: discovered dependencies as candidate edges
- [ ] P14-07 Drift between scans and demotion of CONFIGURED/PROVEN
- [ ] P14-08 Game-day checklist generation (incl. operator-access proof)
- [ ] P14-09 Release 0.4.0

## M6 Production (v1.0)

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
| §5–§8.1 | Services in scope, control vs data plane | ECS+RDS: P2-02b..e/03a/03c/03e..g/04a..b, P4-02a/d/f/g, P4-03a..e/g (M1); P2c + P7-01 (M3 v0.2) |
| §9–§13 | Input sources | P2-01..05 (M1), P1b-01 (M2 v0.1), P2c (M3 v0.2) |
| §14 | Kubernetes discovery | P7-02, P7-07 (M3 v0.2) |
| §14.1 | Dependency sources | P2-06, P2b-01..03/05..07 (M1); P2b-04/09, P2c-01, P7-03 (M3 v0.2) |
| §15–§15.4 | Resource model, identity, typed props, planned snapshot | P0-04/05/15 (M0), P0-15b (M3), P1b-02/03 (M1), P1b-01/15 (M2 v0.1), P1b-10 (M3 v0.2) |
| §16 | Evidence | P0-04, P0-09 (M0) |
| §17–§20 | Graph, edges, ALL/ANY/quorum groups | P0-04/11, P1-05/06/18 (M0) |
| §21–§22 | Evidence and confidence | P0-09 (M0), P2-06 (M1) |
| §23 | Review and editing, review gate | P0-10, P1-07 (M0); P1b-09 (M2 v0.1); P1b-10 (M3 v0.2) |
| §24–§25 | Stacks, services, discovery | P0-04 (M0), P3-01..05 (M1), P2c-01, P7-04 (M3 v0.2) |
| §24.1 | RTO scope | P1-03, P1-05 (M0), P4-05 (M1) |
| §26 | Requirement | P0-04 (M0), P1b-11 (M2 v0.1) |
| §27–§27.1 | Strategies, mechanisms, overlay | P1-02 (M0), P5-01 (M1), P9-01 (M2 v0.1) |
| §28–§28.1 | Rule packs, cross-cutting | P1-01 (M0), P4-02..04 (M1), P4-08, P7-05 (M3 v0.2) |
| §28.2 | LLM advisory review | P4-07 (M4 v0.3) |
| §29–§31 | Findings, readiness, status, scoring | P1-07 (M0), P4-01, P4-05 (M1) |
| §32–§40 | ECS and EKS checks | ECS: P4-02a (M1); EKS: P7-05 (M3 v0.2) |
| §41–§42 | RDS, data gravity | P0-04 (M0), P4-03a (M1) |
| §43–§46 | Simulator, output, reason chains | P1-04..08 (M0), P5-01..02/04 (M1), P5-03 (M1 CLI / M2 UI) |
| §47–§50 | Plan, DAG, durations, buffer, RTO | P1-09..13 (M0), P6-01..03 (M1 CLI), P6-04 (M2 UI) |
| §47.2 | Execution method | P9-08, P11-08 (M2 v0.1 scripts; M3 v0.2 ARC extension) |
| §51 | RPO | P8-01..03 (M1 CLI / M2 UI; P2c/EKS in M3 v0.2) |
| §52 | Target vs predicted | P1-14 (M0), P8-03 (M1 CLI / M2 UI) |
| §53 | Drills | schema P0-04f (M0); import and PROVEN tier P14-01..05 (M5 v0.4) |
| §54–§60 | Optimizer, workload/cost/budget, remediation | presets + StaticCostProvider: P9-01..06, P9-08..09 (M2 v0.1); combinatorial search + AWSPricingProvider (M3 v0.2) |
| §56.1–§56.3 | Candidate planner, immutable evaluations and DR spec approval | P0-15 (M0), P9-08, P10-04/05 (M2 v0.1); planner P9-07 (M4 v0.3) |
| §61–§62.1 | IaC delivery: companion + suggested edits (v0.1), isolated transformation (v0.3), staged verification | P1c-02 (M0), P1b-15, P10-02/04/05/06a..d/07/10/11 (M2 v0.1); P10-01/03/08/09/12, P13-02 (M4 v0.3) |
| §63–§64 | Recovery artifacts (runbook, prerequisite and recovery scripts, ARC plan), failback | P1c-04 (M0), P11-01..06/08 (M2 v0.1); ARC compiler P11-07 (M3 v0.2) |
| §65–§68 | Security, access, secrets, state | P2-01, P2-08, P2b-05 (M1); P12-02 (M2 v0.1) |
| §69–§70 | LLM architecture, knowledge base, skills, guardrails, explainer (v0.3) | P3b-01..07, P10-08, P13-01..05 (M4 v0.3) |
| §71–§75 | Tech, deployment, layout, persistence | P0-01, P0-07 (M0); P1b-06, P1b-13 (M2 v0.1) |
| §76–§76.1 | Scan model, coverage/freshness and confirmed absence | P0-15 (M0), P2-01/12/13 (M1), P2-07 (M1 CLI / M2 API+UI) |
| §77 | Drift | P14-07 (M5 v0.4) |
| §78–§79 | API, CLI | CLI: P0-12 (M0), P1-16 (M0), P2-07/P4-06/P5-03/P8-03 (M1); API: P1b-04, P9-06, P10-07, P11-04 (M2 v0.1) |
| §80–§84 | UI | read-only graph + review/sim/recovery/RPO: P1b-08..09/11..12, P6-04 (M2 v0.1); interactive structural UI editor P1b-10 & ambiguous review UI P2b-09 (M3 v0.2) |
| §85–§89 | Fixtures and demos | P0-13 (M0), P5-04 (M1); P7-08, P7-09 (M3 v0.2) |
| §90–§94 | Testing and review regression gates | owners in spec §90.2; P1-17/18 (M0), P2-09/10, P2b-01 (M1), P9-06 (M2 v0.1), P2b-09, P2c-02 (M3 v0.2) |
| §95–§98 | Quality, observability, errors, unknown | P0-01..03 (M0), P2-01 (M1), P12-03 (M2 v0.1) |
| §99–§109 | Phases, MVP, non-goals, constraints | this plan |

---

## Open questions

Resolve these with a decision-log entry before the task that needs them.

| # | Question | Needed by |
|---|---|---|
| Q1 | Default confidence threshold for "low-confidence" edges (impact pass and review gate). Spec says configuration; pick an initial value. | P1-05 |
| Q2 | Source for initial duration-catalog numbers (AWS docs, own measurements in the sandbox). | P1-09 |
| Q3 | Resolved 2026-11-24: replaced Floci with `aws/aws-emulator` (`aws-emulator`) in §90.1 for stateful collector/Terraform/script integration tests; keep `botocore.stub.Stubber` / `moto` for in-process unit error-injection tests and `tests/contract/` for real-AWS behavior emulators cannot prove. Check `aws-emulator` operation coverage per slice in P2-09. | P2-09 |
| Q4 | Sandbox accounts: one account with two Regions, or a separate DR account from the start (spec §66). | P2-11 |
| Q5 | **(M3 Expansion, v0.2)** EKS checkpoint on real EKS (cost) vs kind for Kubernetes-level checks plus EKS for AWS-level checks. | P7-09 |
| Q6 | Price table source and refresh for `StaticCostProvider` (v0.1 M2; `AWSPricingProvider` deferred to M3 Expansion, v0.2). | P9-03 |
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
| 2026-11-24 | Replace `Floci` with `aws/aws-emulator` (`aws-emulator`) in the §90.1 test pyramid (`P2-09`, `P1c-04`/`P11-06`, `P2b`, `P10`/`P1b-01`, `P2c-02`); closes **Q3**. Keep `botocore.stub.Stubber` / `moto` for pure in-process unit error-injection tests and `tests/contract/` for real-AWS behaviors emulators cannot prove (cross-Region replication lag, CloudWatch Metrics, Service Quotas, CloudTrail/Flow Log delivery, cross-account STS). | `aws/aws-emulator` gives broader, actively maintained stateful AWS emulation for Terraform + collector + recovery-script integration tests, while `Stubber`/`moto` stay fast in-process for error injection and `tests/contract/` covers real-AWS semantics. |
| 2026-11-24 | Cut **v0.1 (`M2 MVP`)** to **ECS + RDS end-to-end** (`ECS + RDS + S3 + ECR + Secrets/SSM + KMS + IAM + ALB + Route 53 + VPC`) and reorganize post-v0.1 milestones (`M3 Expansion v0.2 -> M4 Agents v0.3 -> M5 Proven v0.4 -> M6 Production v1.0`). In v0.1 (`M2`): `P2b` is CloudTrail-only; UI (`P1b-07..09, 11..14`) is a read-only React Flow viewer plus review/confirm/reject panel (structural graph edits remain in YAML overrides `P0-10`); Optimizer (`P9`) uses `StaticCostProvider` plus 3–4 discrete stack presets (`Backup/Restore`, `Pilot Light`, `Warm Standby`) evaluated through the simulator; IaC delivery (`P10`) covers ECS + RDS companion Terraform + suggested edits + supplied-plan verification; recovery artifacts (`P11`) cover runbooks (`P11-02/03`) and prerequisite/Python recovery scripts (`P11-05/06`). Defer `P2c` (EC2/ASG, Lambda, SQS/SNS, CloudFront, WAF, EBS/EFS, DynamoDB), `P7` (EKS), `P2b-04` (VPC Flow Logs + time-aware ENI resolution), `P2b-09` (ambiguous candidate-set review UI), `P1b-10` (interactive structural graph-editor UI), `P9` full combinatorial search + `AWSPricingProvider`, `P11-07` (ARC Region switch plan compiler), and `P0-15b` (schema-migration upgrade registry) to `M3 Expansion (v0.2)`. Preserve full post-v0.1 specifications in `docs/spec/` intact. | Shipping a complete, rock-solid deterministic loop for one realistic stack (ECS + RDS) avoids carrying multi-service surface area, EKS, Flow Logs, combinatorial pricing, and ARC compilation on the v0.1 critical path while keeping every existing task ID and full post-v0.1 spec contract intact. |
| 2026-11-24 | Invert `P1b` and `P2` for a CLI-first real-AWS vertical slice: keep normalizers and identity resolution (`P1b-02`, `P1b-03`) ahead of `P2`, then build minimal CLI-only `P2` + `P2b` (CloudTrail-only) + `P3` + `P4` (ECS+RDS+cross-cutting) + `P5` + `P6` + `P8` (`perpetual scan -> simulate -> plan`) and run against a real sandbox AWS account in `M1 Alpha` before building Terraform saved-plan import (`P1b-01`), planned snapshots (`P1b-15`), FastAPI, and React UI (`P1b-04..09, 11..14`) in `M2 MVP (v0.1)`. | Running real AWS scans through the engine in CLI-only M1 stress-tests typed properties, identity resolution, and rule packs against actual AWS API shapes before investing in FastAPI routes, OpenAPI schema generation, and React UI screens. |
| 2026-11-24 | Finish `M0 PoC` (`P0-11 -> minimal P0-15 -> P0-12..14 -> P1 -> P1c`) on fixtures with lightweight `P0-15` (canonical hashes, immutable evaluation/snapshot manifests, and versioned fixture inputs only; defer schema-migration upgrade registry `P0-15b` to `M3 Expansion`). Adopt a **strict just-in-time modeling rule** (do not build schemas, database tables, or helpers for future milestones until the consumer task is next in line) and **phase-boundary `docs/code/` wiki updates** during active M0/M1 iteration (end of `P0`, `P1`, `P1c`, `P2`, etc.) instead of per subtask, while keeping per-task readability and code comments. | Fixture PoC does not outlive schema versions, so an upgrade registry before real snapshots is premature; phase-boundary wiki updates and strict just-in-time modeling keep M0/M1 velocity high without sacrificing code readability or architectural accuracy. |
| 2026-11-07 | P0-10 uses a pure override application layer on copied resource/edge/stack models. Confirm/edit targets encode the endpoints and relationship type; reject targets remain evidence fingerprints. Historical source edges supply rejection context on rescans; changed claims are linked to old rejection IDs. Replay is deterministic by creation time and ID, with node additions established first. YAML uses a versioned, project-bound envelope; CLI wiring stays P0-12. Missing targets produce orphan diagnostics, and invalid/ambiguous inputs fail explicitly. | Preserve discovered snapshots, typed parallel edges, reproducible user edits and review context without inventing information from a one-way hash. |
| 2026-11-07 | Make basic-Python readability and the living code wiki part of every implementation task. Keep `docs/code/` as the single code wiki; add concepts and worked flows as features arrive, and revise existing explanations when behavior changes. Add repository-wide agent instructions and a review checklist. | User requested readable code and continuously growing documentation of concepts and flows. Framework features remain allowed when explained; correctness and existing contracts remain required. |
| 2026-11-03 | Fixes from an external review of P0-01–P0-09 and the roadmap. **Code:** (1) the evidence fingerprint adds the relationship type (spec §23 amended), so parallel typed edges between the same resources (§19.1) are rejected independently; (2) `combine` accepts a kind-less item only from `user_confirmation`; any other kind-less item raises, like an unlisted kind; (3) `save_resources`/`save_edges` look up existing identities and evidence once per batch (chunks of 500) and flush twice per call instead of per row; (4) `DERIVED_FIELDS` and `FixtureIssue` move to `fixtures/schema.py`, removing both function-local imports. **Plan:** (5) M1 covers the ECS + RDS slice; EC2/ASG, Lambda, SQS/SNS, CloudFront, WAF, EBS/EFS and DynamoDB collectors, packs and resolvers form new phase P2c in M2 (IDs kept, marked `(M2 · P2c)`; P2-02e split into ACM and P2-02f CloudFront/WAF; P4-03d split into ALB/ACM and P4-03h CloudFront; new P2c-01/02). v0.1 scope is unchanged. (6) P2b-02 reads trails from S3 and `LookupEvents`; CloudTrail Lake and Athena go to the backlog (spec §99 amended). (7) Checklist order matches execution order: P0-15 after P0-11 and before P0-12/13; P1b-15 after P1b-03; P2-11 after P2-12/13; P2b-08 after P2b-09. (8) P1-02 implements `resolve_mechanism` on real `DRRulePack` classes that P4 extends. (9) Owners set for tables that fixtures carry but persistence lacks: `recovery_requirements` in P1-15, facts in P2-12; payload schema versions with registered upgrades in P0-15. **Not adopted:** a separate "modeled preview" mode in P10-04, because P9-04/P9-05 already evaluate each candidate and remediation as a modeled snapshot before any saved plan exists; building fact/requirement tables now, because their consumers don't exist yet. | A forgotten `kind=` or kind-less LLM evidence would otherwise silently bypass the weights table or add confidence (§2 rule 11). Per-row queries made a 5,000-resource snapshot cost tens of thousands of statements. M1's exit needs only the ECS + RDS services; the rest delayed the first real-AWS validation. S3 trail files cover the same events as Lake and Athena. |
| 2026-10-28 | P0-09 evidence. `Evidence` gains an optional `kind` naming its row in the §22 weights table. A configured kind counts with the configured weight (so tuning applies without a rescan); a kind-less item (user confirmation, anything outside the table) counts with its own `confidence` in a group named `source:<source_type>`; an unlisted kind raises. No evidence gives 0.0. Combination functions are a name→function registry that must cover every name config allows. The fingerprint is sha256 over compact JSON of the endpoints and the sorted set of `(source_type, attribute, value_summary)` (§23); it ignores evidence IDs, times, counts, confidences, edge ID and relationship type, and keeps `None` distinct from `""`. | Config stays the single source of weights; grouping kind-less items by source is the conservative reading of §22; the fingerprint follows §23 exactly and is stable across rescans. |
| 2026-10-28 | P0-08 fixtures. One YAML file per fixture in `fixtures/graphs/` (beside the spec's `fixtures/aws`, `terraform`, …) holding the domain models directly, header `format: perpetual-fixture` / `version: 1` / `captured_at`. The loader fills resource provider, account, Region, service, type, `planned` and planned `terraform_address` from the canonical ID and reports any authored value that contradicts it (the node-vs-ID check deferred from P0-05); global resources get region `"global"`; missing discovery/collection times default to `captured_at`, and overrides to project `fixture`. All problems are reported together with paths. Cross-reference checks also enforce the group rules (members start at the dependent; one group per edge per scope) that P0-11 will enforce on live data; overrides are not checked against resources (orphans are valid). A committed JSON Schema (`fixtures/schema/fixture-v1.schema.json`, derived fields optional) is kept current by a test. The first CLI commands (`perpetual fixtures validate|schema`) and the `perpetual` console script land here; Typer and Rich added. `minimal.yaml` is a small example; canonical fixtures stay in P0-13. | Short fixtures are easier to review, and deriving from the ID removes a whole class of inconsistency; reporting all problems at once makes hand-written fixtures practical. |
| 2026-10-28 | P0-07 storage. Rows have typed lookup columns plus a `payload` JSON column with the full domain model, validated again on load (no column-per-field mapping). Added a `snapshots` table (live or planned, published once, then frozen) that §75 doesn't list; graph data, mechanisms and stacks are per snapshot, while overrides and evaluation inputs are per project. `resources` holds identity across snapshots and `resource_versions` each snapshot's copy. Edge evidence is stored once per snapshot with an `edge_evidence` link table that keeps order; group and mechanism evidence stays in their payloads. `observations` added (the P0-04d decision moved them here). Status/enum columns are plain strings, since values come from validated models. The initial migration is autogenerated, uses plain SQLAlchemy types, and runs from code (no `alembic.ini`). One index is named explicitly to fit PostgreSQL's 63-character limit. SQLAlchemy and Alembic added. | Keeps the schema small while the models are still growing; the payload round-trip keeps model validation authoritative; frozen snapshots implement §15.4/§76.1; per-project overrides follow §23. |
| 2026-10-28 | P0-06 config. **Review confidence threshold defaults to 0.90**: the spec requires one (§23) but gives no number. At 0.90, Terraform references, AWS relationships and mapped CloudTrail calls pass alone; an endpoint match (0.85) or IAM permission (0.80) alone needs review; IAM plus SG path (0.95 combined) passes. Evidence kinds named after the §22 table; `name_only_heuristic` gets its own `heuristics` group (the spec's initial groups don't cover it); Kubernetes, ECS-secret and endpoint references go in `configuration_references`. Freshness, alternative-selection cap (32) and cost units (730 h, 30-day price age) are config too (D12). Out-of-scope defaults are by type key; role-based cases (log buckets, OpenSearch for logs) stay with rule packs. Buffer defaults name duration-catalog keys rather than durations, since the catalog (P1-09) owns durations. Overrides merge mappings and replace lists; changed paths are recorded. `config` keeps its own `FreshnessConfig` because it may not import `models`; a test keeps it in step with `FreshnessPolicy`. PyYAML added. | Every tuning number in YAML (D12); the threshold needs a value before readiness gates exist, and 0.90 keeps single weak signals in review. |
| 2026-10-28 | P0-05 IDs: `SERVICE/TYPE` in an ID is the type key (so `route53/hostedzone`, not the spec example's `hosted-zone`). Account is 12 digits; Region matches any partition or is `global`; names are lowercase letters, digits and `-`; the identifier is the last part and may contain `/`. Planned IDs put the Terraform address last because `for_each` keys may contain `:`; root ID and workspace may not; a live identifier may not start with `tf:`. External nodes get `external://SERVICE/NAME`, which the spec does not define. `ids` does not decide which services are global, and the node-vs-ID consistency check lives in the fixture validator and graph build because `models` may not import `ids`. | One key per type everywhere; an ID that can't round-trip would break overrides and digests; fixtures need a format for external nodes. |
| 2026-10-28 | P0-04f shapes. `BufferPolicy` already existed (P0-04a), so it was not redone. Digests are typed `sha256:<64 lowercase hex>`; ID sets use `SortedIds` (repeats rejected, stored sorted). `FreshnessPolicy` has no default values: the §76.1 numbers go into YAML in P0-06. `ScanCoverage` complete needs a completion time, finished pagination and no error codes; denied needs error codes. An exact `ResolvedObservation` must cite resolution evidence. `CostEstimate` totals are computed properties (any unknown line gives an unknown total), and a zero line needs `zero_reason`. `VerificationReport` enforces the §61.1 pass gates and refuses observed READY unless every prerequisite is satisfied; settled prerequisites cite evidence. `ReadinessTier` (§3) added to `status.py`. `OperatorIdentity.replica_regions` is None for unknown, `[]` for declared none. Budget comparison and canonical digests stay in their owning tasks (costing, P9-08). | Each rule turns a spec "never" into a construction error; computed totals can't drift from their lines; keeping config values and digest computation out of `models` follows the layer rules. |
| 2026-10-28 | P0-04e: `external/dependency` properties are matched on `provider="external"` (user-chosen service names, §15.2); `generic/resource` is allowed only for types without a model (`SPECIFIC_TYPE_KEYS`); CodePipeline records action Regions and providers for the §24.1 in-scope exception. Facts live in `models/facts.py`, separate from resources: `QuotaFact` (headroom None unless limit and usage known), `InstanceTypeOfferingFact` (sorted set), `CapabilityFact` (catalog answers name a version), `MetricFact` (ok/no_data/access_denied/error; only ok has samples, ordered and inside the window). Every fact has account, Region, collection time, coverage ID and `carried_forward`. | Missing data must stay unknown (§28.1, §76.1); facts change faster than configuration and need their own freshness handling; a fallback must not bypass a type's validation. |
| 2026-10-28 | Fixes from an external review of P0-04a–d. (1) `is_missing()` treats None and empty strings/collections as missing, never 0 or False (the review's `is None` fix would let an HTTPS listener with `[]` certificates pass). (2) AWS-assigned values (IDs, ARNs, URIs, computed numbers) are declared in `required_fields`, typed nullable, and must be present or listed in `unknown_fields`; nested parts inherit `PropertyPart`, and an unknown nested value marks the parent field unknown (one level deep). (3) Every "set together" pairing check skips when a side is unknown (Aurora global membership, SQS redrive, KMS multi-Region role, Route 53 failover role), and S3's versioning check respects unknown versioning. (4) DynamoDB replicas are structured (`DynamoDBReplica`: Region, status, KMS key, table-class override). (5) `unknown_fields` is sorted and rejects repeats. (6) The resolved-observation model (§14.1) moves to P0-04f so persistence (P0-07) can store it; P2b-09 keeps the review flow. | §15.4 forbids inventing ARNs for planned resources, and the Terraform importer needs this before P1b; stable hashes need normalized lists (§56.3); per-replica KMS decides whether a replica can be read in DR. |
| 2026-10-28 | P0-04d scope and rules: also models route tables, NAT and internet gateways, VPC endpoints, Transit Gateway attachments, Route 53 health checks, CloudFront, ACM, ECR registry (replication is per registry) and ECR images, which P2 collectors gather but the P0-04d list omitted. SNS subscription endpoints are stored only for AWS-resource protocols (email/SMS/HTTP endpoints are personal data). IAM policies are stored as structured statements for XREG-IAM-002. `accelerated_recovery_enabled` is a nullable bool rather than an API enum. A test fails if a properties model is not registered in the union. The typed-properties docs moved to `docs/code/packages/models-properties.md`. | Collectors need somewhere typed to put every fact they gather; personal data has no DR value; a forgotten union registration would otherwise surface only when a fixture fails to parse. |
| 2026-10-28 | P0-04c: `type_key` follows the service name in each resource's ARN (`ec2/volume`, `ec2/snapshot`, `elasticfilesystem/file-system`, `backup/recovery-point`); one `RDSSnapshotProperties` model takes both `rds/snapshot` and `rds/cluster-snapshot`; AWS Backup vaults and recovery points are modelled here because restores depend on them; volumetric fields (§42) live on the models while fast-changing metrics wait for P0-04e facts; validators use `TypedProperties.is_missing()` so values known only after apply never fail a prerequisite check. | One naming rule for keys and IDs; restore mechanisms need recovery points as typed resources; metrics need freshness handling that configuration does not. |
| 2026-10-28 | P0-04b typed-property conventions: (1) each model's `type_key` is `SERVICE/TYPE` from the canonical ID (`ecs/service`, `autoscaling/group`, `ec2/launch-template`, `ec2/image`, `lambda/function`, …) and is the discriminator of the `ResourceProperties` union; `ResourceNode.typed_properties` holds it and must match the node's type. (2) None means absent/null; `unknown_fields` lists fields unknown until apply (§15.4); an empty list means known-empty. (3) Secrets are stored as references, env vars as names only, launch-template user data as a presence flag; there is no field for the values (§67). (4) Lambda module is `awslambda.py` (`lambda` is a keyword). | `resource_type` alone repeats across services (`cluster`); a key aligned with the ID is unambiguous. Unknown plan values must never read as absent or as the old live value. Making secret values unstorable is stronger than a rule saying not to store them. |
| 2026-10-28 | Add a code walkthrough in `docs/code/`: an index with a package status table, `architecture.md` (pipeline as built), `tooling.md`, one page per package with real code (`packages/<name>.md`, from `_template.md`) and, later, end-to-end `flows/<name>.md`. Every task that changes code updates it in the same change; it is part of the definition of done (IMPL_PLAN §4 note, CLAUDE.md). Code comments explain the *why* of validators and engine rules, citing spec sections. | User request: a scalable, always-current document to understand the code before reading it, as the codebase grows. |
| 2026-10-28 | P0-04a model choices. (1) Domain models are immutable, reject unknown fields and require timezone-aware timestamps. (2) Spec MUSTs are enforced in the models: confidence in [0, 1]; observed evidence needs its window and count, other evidence must not have one; every dependency-edge evidence item has a basis; user-added edges have confidence 1.0 and `user_confirmation`/`asserted` evidence; `confirmed` agrees with `review_state`; quorum groups have 1 ≤ `minimum_healthy` ≤ members; Region requirements name `target_region`; duration bounds are ordered and unknown bounds stay None; stack roots are members; mechanism dependency groups are DR-side. (3) `relationship_type` is the §20 vocabulary as an enum (spec: `str`); `contains`, `member_of`, `replicates_to`, `backed_up_by` are flagged as not operational requirements. (4) `GraphOverride.payload` stays a dict but is validated against a per-kind schema. (5) Added `SourceReference` (used but undefined in the spec), `StackResource` (membership + RTO scope, §24.1), `ResourceNode.planned` (§15.1). (6) `DurationEstimate` and `BufferPolicy` moved here from P0-04f because `RecoveryRequirement` needs them. (7) `worst_state` refuses an empty input instead of returning SURVIVES. (8) Graph-wide group checks (shared dependent and scope, one group per edge) run in P0-11. (9) Pydantic's mypy plugin is enabled. | Catch invalid fixtures and imports at the boundary instead of inside the engine; keep snapshots stable for digests (§56.3); never let an empty or missing input read as healthy. |
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

### 2026-11-24 — P1-15 persistence, P1-18 selected-path regressions & end-of-P1 wiki (P1 complete)

- Added `RecoveryRequirementRow`, `SimulationRow`, and `RecoveryPlanRow` tables (`tables.py`), Alembic migration `0002_p1_simulation_and_plans.py` (SQLite + PostgreSQL verified, downgrade clean), and project-scoped `ProjectRepository` methods (`save_requirement`, `requirement`, `save_simulation`, `simulation`, `save_recovery_plan`, `recovery_plan`).
- Added `perpetual.recovery.selection` (`SelectedPathResult`, `select_recovery_paths`): bounded deterministic search over ALL/ANY/quorum groups capped by `config.limits.alternative_selection_cap`, deduplicating shared prerequisites and excluding unselected alternatives from plan actions (§19.1).
- Added 3 regression tests in `apps/api/tests/recovery/test_selected_paths_and_persistence.py` and updated `tests/persistence/test_schema_and_migrations.py` for the 20 tables.
- Completed end-of-P1 phase-boundary `docs/code/` update: updated `docs/code/README.md` and added package pages for `stacks`, `rules`, `simulator`, and `recovery`.
- Validation: `mise run check` passes (477 tests, 9/9 import contracts kept, strict mypy clean on 134 files, ruff check & format clean).
- **Carry-over:** Start **P1c PoC compile loop** (`P1c-01` modeled DR change set on `ecs-broken`, `P1c-02` companion Terraform templates with `fmt` + `validate`, `P1c-03` re-simulation matching `ecs-remediated`, `P1c-04` Python recovery script with dry-run test, `P1c-05` `perpetual poc fix` CLI).

### 2026-11-24 — P1-09..P1-14, P1-16, P1-17 recovery DAG, buffer, RTO & CLI

- Added versioned `apps/api/perpetual/config/defaults/duration_catalog.yaml` and `perpetual.recovery.catalog` (`DurationCatalog`, `load_duration_catalog`) with volumetric bucket matching, generic fallback action types (`generic_promote_counterpart`, `generic_restore_from_backup`, `generic_rebuild_from_iac`), per-resource duration overrides, and `None` (UNKNOWN, never zero) for missing entries (§49.1).
- Added `perpetual.recovery.actions` (`RecoveryAction`, `RecoveryPhase`, `AutomationLevel`, `actions_for_mechanism`) synthesizing first-slice recovery actions plus generic fallbacks (§48).
- Added `perpetual.recovery.planner` (`build_recovery_dag`, `plan_stack_recovery`, `compare_target`, `RecoveryPlan`, `RtoBreakdown`, `PlanError`): phase-template default edges + refined prerequisites, `decide` and `stack_validation` actions, handoff + contingency buffer (§49.2), topological longest-path RTO with UNKNOWN propagation (§50), and target comparison (§52).
- Added `perpetual simulate` and `perpetual plan` CLI commands in `perpetual.cli.simulate` (`--fixture`, `--failure`, `--json`) wired into `perpetual.cli.app`.
- Added 8 tests in `apps/api/tests/recovery/test_rto_and_plan.py` verifying spec §93 RTO math (`40`, `48`, `49.5` minutes), catalog buckets/overrides/missing entries, UNKNOWN propagation, DAG cycle rejection, target comparison boundaries, and CLI execution on `ecs-broken` and `ecs-remediated`.
- Validation: `mise run check` passes (474 tests, 9/9 import contracts kept, strict mypy clean on 131 files, ruff check & format clean).
- **Carry-over:** Finish P1 with **P1-15** (persist simulation, plan & recovery requirements) and **P1-18** (ALL/ANY/quorum selected-path regressions) + end-of-P1 `docs/code/` update, then **P1c** (PoC compile loop: modeled DR change set, companion Terraform, Python recovery script, `perpetual poc fix`).

### 2026-11-24 — P1-03..P1-08 two-pass failure simulator, readiness & reason chains

- Added `perpetual.stacks.scope` (`classify_resource_scope`, `classify_stack_scopes`) honoring config defaults (`rto_scope.yaml`) and per-resource `StackResource` overrides (§24.1).
- Added `perpetual.simulator`:
  - `scenarios.py` (`FailureScenario`, `RegionFailure`, `AZFailure`, `LogicalCorruption`, `UnsupportedScenarioError`, `parse_scenario`, `seed_failed_resources`) dispatching on `kind` (§43).
  - `impact.py` (`ImpactRecord`, `run_impact_pass`): fixed-point cycle-safe impact propagation skipping structural/replication/backup edges, respecting out-of-scope boundaries, confidence thresholds, and ALL/ANY/quorum groups (§19.1, §44).
  - `recovery.py` (`ResourceSimulationResult`, `run_recovery_pass`): memoised, cycle-safe DR-overlay traversal handling `none`, `unknown`, `live_counterpart`, `restore_from_recovery_point`, `rebuild_from_iac`, `global_service` (`CTRL-PLANE-001` for `us-east-1`), `external`, and ALL/ANY/quorum groups (§19.1, §44).
  - `readiness.py` (`EvaluationKind`, `FindingEffect`, `ReadinessInputs`, `ReadinessResult`, `compose_readiness`): ordered 4-row §31 readiness composition table separating simulation recoverability from target compliance and review/coverage gates.
  - `engine.py` (`ReasonChain`, `SimulationResult`, `simulate_failure`): end-to-end orchestration and root-to-blocker reason chains (§45, §46).
- Added 8 tests in `apps/api/tests/simulator/test_simulator_core.py` verifying §87 (`ecs-broken` → `UNAVAILABLE`/`NOT_READY`), §88 (`ecs-remediated` → `RECOVERABLE` despite blocked out-of-scope logs), `cycle.yaml` termination, unsupported scenarios, review gate (`graph_not_reviewed`), quorum groups, and §31 precedence.
- Validation: `mise run check` passes (466 tests, 9/9 import contracts kept, strict mypy clean on 126 files, ruff check & format clean).
- **Carry-over:** P1-09 (Duration catalog v1), P1-10 (first-slice recovery actions), P1-11 (DAG builder), P1-12 (Buffer), P1-13 (RTO), P1-14 (Target comparison), P1-16 (`perpetual simulate` / `perpetual plan` CLI), and P1-17/18 (spec §92/§93 tests).

### 2026-11-24 — P1-01 rule-pack protocol & P1-02 first-slice mechanism resolution

- Added `perpetual.rules.protocol` (`DRRulePack`, `AssessmentContext`, `ReproducibilityEvidence`, `RulePackRegistry`, `RulePackError`) and `perpetual.rules.cross` (`CrossCuttingRule`, `CROSS_CUTTING_RULE_IDS`), enforcing strict §27.1 reproducibility for `rebuild_from_iac` and falling back to `unknown` for unmodeled services.
- Added `perpetual.rules.first_slice` with 9 real `DRRulePack` classes (`Route53RulePack`, `ELBRulePack`, `ECSRulePack`, `ECRRulePack`, `SecretsManagerRulePack`, `KMSRulePack`, `RDSRulePack`, `S3RulePack`, `LogsRulePack`) and `default_registry()`.
- Added 5 tests in `apps/api/tests/rules/test_rule_packs_and_mechanisms.py` verifying registry contracts, exact DR-overlay parity against both `ecs-broken.yaml` and `ecs-remediated.yaml`, strict §27.1 reproducibility, external resources, and RDS `backed_up_by` snapshot restore. (Fixed `mech-ecs.dr_dependency_ids` in `ecs-broken.yaml` to include `checkout-assets-dr`.)
- Validation: `mise run check` passes (458 tests, 9/9 import contracts kept, strict mypy clean on 119 files, ruff check & format clean).
- **Carry-over:** P1-03 (RTO scope classification), P1-04 (`FailureScenario` dispatch), P1-05 (Impact pass), P1-06 (Recovery pass).

### 2026-11-24 — P0-13 canonical fixtures & P0-14 wrap-up (P0 complete)

- Authored all 5 canonical P0-13 fixtures under `fixtures/graphs/`: `ecs-broken.yaml` (spec §85/§87), `ecs-remediated.yaml` (spec §85/§88), `cycle.yaml` (spec §18), `shared-node.yaml` (multi-stack shared KMS/VPC), and `deep-path.yaml` (6-node chain > 4 hops).
- Verified P0 exit criterion: `uv run perpetual fixtures validate` passes on all 7 fixtures, and `uv run perpetual graph --fixture ecs-broken` renders the full dependency graph, canonical manifest digest, and DR overlay.
- Completed P0-14: updated `CLAUDE.md` status/commands to match reality and performed the end-of-P0 phase-boundary update to `docs/code/` (`README.md`, `packages/graph.md`, `packages/cli.md`).
- Validation: `mise run check` passes cleanly across all tests, mypy strict, ruff, and 9 import contracts.
- **Carry-over:** Start **P1 Simulation and recovery core** at **P1-01** (`DRRulePack` protocol and registry; `rules/cross/` skeleton), followed by **P1-02** (`resolve_mechanism` on real `DRRulePack` classes for the `ecs-broken` slice).

### 2026-11-24 — P0-12 `perpetual graph` CLI

- Added `perpetual.cli.graph` (`perpetual graph --fixture NAME [--stack S] [--unreviewed] [--json]` and `perpetual graph overrides export|apply`) and registered it on `perpetual.cli.app`.
- Applies fixture overrides, builds the validated `DependencyGraph` and `SnapshotManifest`, detects cycles, highlights unreviewed edges below `review_confidence_threshold`, and prints Rich tables (resources, dependency edges, DR overlay mechanisms, cycles, orphaned overrides) or structured JSON.
- Added 6 CLI tests in `apps/api/tests/cli/test_cli_graph.py`.
- Validation: `mise run check` passes (453 tests, 9/9 import contracts kept, strict mypy clean on 115 files, ruff check & format clean).
- **Carry-over:** P0-13 (canonical fixtures: `ecs-broken`, `ecs-remediated`, `cycle`, `shared-node`, `deep-path`), then P0-14 (update `CLAUDE.md` + P0 phase-boundary `docs/code/` update).

### 2026-11-24 — P0-15 lightweight manifests & canonical hashes

- Added `perpetual.graph.manifest` (`canonical_json`, `canonical_digest`, `config_digest`, `evaluation_input_digest`, `SnapshotManifest`, `build_snapshot_manifest`): deterministic SHA-256 hashing over normalized JSON (UTC ISO-8601 timestamps, normalized Decimals, `timedelta` seconds, sorted keys, explicit `null` distinct from `unknown_fields`).
- Extended `perpetual.fixtures` (`FixtureInputVersions`, `Fixture.workload_profiles`, `Fixture.input_versions`, `WorkloadQuantity.collected_at` defaulting, stack/resource cross-reference checks) and regenerated `fixtures/schema/fixture-v1.schema.json`.
- Added 7 tests in `apps/api/tests/graph/test_manifest.py` covering canonicalization, absent/unknown/null distinction, config/snapshot/evaluation digests, and versioned fixture inputs.
- Validation: `mise run check` passes (447 tests, 9/9 import contracts kept, strict mypy clean on 113 files, ruff check & format clean).
- **Carry-over:** P0-12 (`perpetual graph` CLI), then P0-13 (canonical fixtures: `ecs-broken`, `ecs-remediated`, `cycle`, `shared-node`, `deep-path`) and P0-14 (update `CLAUDE.md` + P0 phase-boundary `docs/code/` update).

### 2026-11-24 — Roadmap alignment commit + P0-11 NetworkX snapshot and traversal

- Committed and pushed the roadmap, scope, governance, and `aws/aws-emulator` updates (`69cc9e2`).
- Added `networkx` (3.7) and `types-networkx` to `pyproject.toml` / `uv.lock`.
- Added `perpetual.graph.snapshot` (`DependencyGraph`, `GraphError`, `GroupMember`, `build_graph`, `from_graph_data`, `from_override_result`): builds a validated `nx.MultiDiGraph` keyed by `edge.id` preserving parallel typed edges, enforces canonical node-vs-ID consistency, validates primary and DR-overlay dependency groups (§19.1), and keeps rejected edges out of active traversal while preserving rejected-member context without lowering quorums.
- Added `perpetual.graph.traversal` (`project_graph`, `dependency_closure`, `ancestors_of`, `shortest_dependency_path`, `has_cycles`, `detect_cycles`): derived `nx.DiGraph` projections preserving parallel `edge_ids`, operational/optional/confidence/type filters, and cycle-safe NetworkX traversal that never raises on cycles and canonicalizes cycle order.
- Added 10 tests in `apps/api/tests/graph/test_snapshot_and_traversal.py` covering parallel edges, projection filters, deep shared graphs, cycles, quorum preservation with `apply_overrides`, DR mechanism groups, validation errors, and fixture integration.
- Readability review: focused `_index_*` helpers, explicit loops/errors, NetworkX delegation, and spec citations. Per M0/M1 phase-boundary cadence, `docs/code/` updates batch at the end of P0.
- Validation: `mise run check` passes (440 tests, 9/9 import contracts kept, strict mypy clean on 111 files, ruff check & format clean).
- **Carry-over:** P0-15 (lightweight canonical hashes, immutable snapshot/evaluation manifests, and versioned fixture inputs; schema-migration upgrade registry stays deferred to M3 `P0-15b`), then P0-12 (`perpetual graph` CLI), P0-13 (canonical fixtures), and P0-14 (update `CLAUDE.md` + P0 phase-boundary `docs/code/` update).

### 2026-11-07 — P0-10 graph overrides

- Added `graph.overrides`: pure replay of confirm/reject/add/edit edge and add/edit node instructions over copied records; stable typed targets, deterministic ordering, user assertions, merge on discovery, orphan reactivation and historical rejection links. Conflicting/ambiguous inputs fail explicitly. Changed evidence does not inherit an earlier confirmation superseded by a rejection.
- Versioned project-bound YAML export/load/parse and additive, idempotent import merge. Added project-scoped `ProjectRepository.delete_override` for withdrawal without changing source snapshots. Graph/override CLI wiring remains P0-12.
- `review-overrides.yaml` exercises all six kinds. Added replay, YAML, and persistence integration tests covering source isolation, parallel types, history across rescans, membership/scope, missing targets, ordering, import conflicts and cross-project protection.
- Wiki: graph package page, runnable override flow, architecture/import connections and current status; linked the existing evidence/models/persistence pages. Readability review: public inputs/results documented, responsibilities split into focused modules, explicit loops/validation and no new runtime dependency.
- Validation: `mise run check` passes (430 tests, including 61 new override tests; strict mypy on 108 files; lint/formatting; nine import contracts). Both repository fixtures validate; the new wiki example runs with the documented output; local file links and code fences checked across 21 wiki pages; diff whitespace clean.
- **Carry-over:** P0-11 (NetworkX snapshot and traversal). Preserve dependency groups and rejected-edge context; never silently lower a quorum. P0-15 still precedes P0-12/13. Callers must provide fresh source records and historical rejected claims; override status persistence is explicit.

### 2026-11-07 — Python readability audit and refactor

- Reviewed implemented foundation paths through P0-09; recorded findings, changes, retained framework patterns, and scope in `docs/code/readability-audit.md`.
- Refactored seven runtime files: fixture defaults, error paths and checker names; evidence combination and fingerprint sorting; cost/status helpers; batched edge storage and reconstruction. Preserved public APIs, error messages, serialized schemas, database layout, and fingerprint format.
- Added two regressions for the persisted fingerprint format and authored override fields/nulls. `mise run check` passes: 369 tests, nine import contracts, strict mypy on 96 files, lint and formatting.
- Expanded wiki concepts and four package pages; added an in-memory snapshot round-trip flow. Both library walkthroughs ran successfully; local file links and code fences checked across 19 wiki pages; diff whitespace clean. No new engine capability or milestone task completed.
- **Carry-over:** P0-10 (graph overrides), with the readability and wiki checklist applied as implementation proceeds.

### 2026-11-07 — Readability and living code wiki

- Added root `AGENTS.md`, a basic-Python readability guide and completion checklist; synchronized CLAUDE.md and the implementation definition of done.
- Extended `docs/code/` with a concept guide, a runnable fixture-to-evidence walkthrough, and a flow template; updated the package template and index. The wiki grows with new features and corrects old explanations when behavior changes.
- Validation: ran the documented fixture-to-evidence example successfully; checked local file links (package-template links relative to their destination), code fences, and diff whitespace. Documentation-only change; no runtime refactor or claim of a completed readability audit of all existing code.
- **Carry-over:** P0-10 (graph overrides), using the readability checklist and extending the wiki alongside implementation.

### 2026-11-03 — External review fixes (P0-01–P0-09, roadmap)

- Reviewed an external critique against the code and plan; adopted most points (decision log). Code: fingerprint includes relationship type; only user confirmations may omit an evidence kind; batched snapshot writes with a statement-count test; fixtures import cycle removed; `minimal.yaml` evidence gains `kind: terraform_reference`. Plan: P2c phase in M2 for non-ECS-slice services, CloudTrail Lake/Athena to backlog, checklist order matches execution order, owners for requirement/fact tables and payload versioning. Spec §23 and §99 amended with a changelog line. README status and site roadmap updated.
- `mise run check`: 9 contracts kept, mypy strict clean, 367 tests. `docs/code` evidence, fixtures and persistence pages updated.
- **Carry-over:** P0-10 (graph overrides). Note: reject overrides target edge fingerprints, which now include the relationship type.

### 2026-10-28 — P0-09 evidence combination and fingerprints

- `perpetual.evidence`: `combine` (max within correlation group, `noisy_or` across, via the `COMBINATIONS` registry) returning `CombinedConfidence` with a per-group breakdown; `evidence_fingerprint`/`edge_fingerprint`. `Evidence.kind` added; fixture schema regenerated.
- 21 new tests; `mise run check`: 9 contracts kept, mypy strict on 96 files, 362 tests. New `docs/code/packages/evidence.md` with diagrams; README, architecture (import graph, data flow), models and config pages updated.
- **Carry-over:** P0-10 (graph overrides: apply, rescan merge, orphan detection, YAML export/apply).

### 2026-10-28 — P0-08 fixture format v1

- `perpetual.fixtures`: `Fixture` model, loader (`load_fixture`, `parse_fixture`, `expand`) with ID-derived fields and contradiction checks, `check_references`, `resolve_fixture`/`fixture_names`, `fixture_json_schema`. `perpetual.cli`: root app, `perpetual fixtures validate|schema`, console script. `fixtures/graphs/minimal.yaml` and `fixtures/schema/fixture-v1.schema.json`. Typer and Rich added.
- 28 new tests; `mise run check`: 9 contracts kept, mypy strict on 93 files, 341 tests. New `docs/code/packages/fixtures.md` and `cli.md`; README and architecture updated; CLAUDE.md commands list the new command.
- **Carry-over:** P0-09 (evidence combination with correlation groups, evidence fingerprints).

### 2026-10-28 — P0-07 persistence

- `perpetual.persistence`: 17 tables (`tables.py`), `ProjectRepository` with project scoping, open/published snapshots, evidence de-duplication, override status changes and add-only evaluation inputs; `db.py` (default path, SQLite foreign keys, sessions); Alembic environment and initial migration run from code (`migrate.py`). SQLAlchemy and Alembic added.
- 23 new tests: migration equals the models, downgrade, SQLite and PostgreSQL compilation, offline PostgreSQL SQL, identifier lengths, round trips, isolation, immutability. `mise run check`: 9 contracts kept, mypy strict on 86 files, 313 tests. New `docs/code/packages/persistence.md`; README and architecture updated (also added the missing `ids` and `config` rows).
- **Carry-over:** P0-08 (fixture format v1, loader, validator, JSON Schema).

### 2026-10-28 — P0-06 typed config and defaults

- `perpetual.config`: six YAML sections in `config/defaults/` (evidence, scoring, rto_scope, buffer, freshness, limits) loaded into typed models; `load_config(overrides)` and `load_config_file(path)` merge project overrides, validate the whole, and record `overridden_paths`. Defaults confirmed in the built wheel. PyYAML and its stubs added.
- 26 new tests; `mise run check`: 9 contracts kept, mypy strict on 78 files, 290 tests. New `docs/code/packages/config.md`; README and architecture updated.
- **Open question for the user:** review confidence threshold 0.90 (decision log).
- **Carry-over:** P0-07 (persistence + initial Alembic migration).

### 2026-10-28 — P0-05 canonical resource IDs

- `perpetual.ids`: build (`aws_id`, `global_id`, `planned_id`, `external_id`), parse (`parse`, `parse_aws`, `is_valid`) into frozen `AwsResourceId` / `ExternalResourceId` with `PlannedAddress`; strict validation and exact round-trip.
- 26 new tests; `mise run check`: lint and contracts clean, mypy strict on 75 files, 264 tests. New `docs/code/packages/ids.md`; README, architecture and models page updated.
- **Carry-over:** P0-06 (typed config + defaults).

### 2026-10-28 — P0-04f evaluation-side models

- New in `perpetual.models`: `coverage.py` (`ScanCoverage`, `Presence`, `FreshnessPolicy`), `observation.py` (`ResolvedObservation`, exact or ambiguous), `cost.py` (`WorkloadProfile`, `CostEstimate`), `evaluation.py` (`EvaluationInput` with IaC baseline or companion design), `verification.py` (`DeploymentPrerequisite`, `VerificationReport`), `drill.py` (`DRDrill`), `operator_access.py` (`OperatorAccessProfile`); `Digest`, `SortedIds` and `ReadinessTier` added.
- 50 new tests; `mise run check`: lint and import contracts clean, mypy strict on 73 files, 238 tests. `docs/code` updated (`models.md`, README status table, architecture); CLAUDE.md status line updated.
- **Carry-over:** P0-05 (canonical resource IDs).

### 2026-10-28 — Project site (`site/`)

- Added the Astro marketing and docs site in `site/` (outside the Python package; excluded from ruff, build output git-ignored). Not part of `mise run check` yet.
- Content corrected to match the project's state: the setup command is clone + `mise install` (not on PyPI until v1.0), CLI commands are marked as planned, the nav badge says M0, the roadmap shows P0-04e done, and the example RTO cites spec §109. Images compressed (hero 1.7 MB → 59 KB WebP; logo trimmed to 128 px), and the mobile hero overflow is fixed.
- Follow-ups, not scheduled: move the docs from HTML strings in `siteData.ts` to Markdown content collections; merge `global.css` and `cinematic.css`; add a site build to CI; confirm the `perpetual.sh` domain.
- **Carry-over:** P0-04f (unchanged).

### 2026-10-28 — P0-04e fallbacks and facts

- `properties/other.py`: external, generic and CodePipeline properties; `SPECIFIC_TYPE_KEYS`; node check handles the two fallbacks. `models/facts.py`: quota, instance-type offering, capability and metric facts with `FactRecord`.
- 17 new tests; `mise run check`: 9 contracts, mypy strict on 63 files, 188 tests. `docs/code` updated (facts in `models.md`, fallbacks in `models-properties.md`).
- **Carry-over:** P0-04f (evaluation, coverage, cost, verification, drill, operator-access and resolved-observation models).

### 2026-10-28 — P0-04d typed properties: messaging, network, edge, supporting

- 33 models in `messaging.py`, `network.py`, `elb.py`, `edge.py`, `supporting.py`, `recovery_control.py` (SQS, SNS, VPC networking, ELB, Route 53, CloudFront, ACM, WAF, ECR, Secrets Manager, SSM, KMS, IAM, Logs, ARC routing controls, Region switch plans, readiness checks, Identity Center). 54 type keys in the union.
- 31 new tests including union registration and key uniqueness. Typed-properties docs split into `models-properties.md`.
- External review fixes (decision log): required-or-unknown fields for planned resources with `PropertyPart` for nested models, `is_missing()` semantics, sorted `unknown_fields`, structured DynamoDB replicas, unknown-aware Aurora and S3 checks; resolved-observation model scheduled in P0-04f. 11 more tests; `mise run check`: 9 contracts, mypy strict on 60 files, 171 tests.
- **Carry-over:** P0-04e (external/generic properties; quota, availability and metric facts).

### 2026-10-28 — P0-04c typed properties: data and storage

- RDS instance, Aurora cluster, RDS/cluster snapshot, DynamoDB table and backup, S3 bucket with replication rules, EBS volume and snapshot, EFS file system with replication, AWS Backup vault and recovery point; `is_missing()` helper on `TypedProperties`.
- 18 new tests; `mise run check`: 9 contracts, mypy strict on 52 files, 129 tests. `docs/code` updated.
- **Carry-over:** P0-04d (typed properties: messaging, network, edge and supporting services).

### 2026-10-28 — P0-04b typed properties: compute and containers

- `perpetual.models.properties`: `TypedProperties` base with `unknown_fields`; ECS cluster/service/task definition, EC2 instance, Auto Scaling group, launch template, AMI, Lambda function and event-source mapping; `ResourceProperties` discriminated union; `ResourceNode.typed_properties` with type check.
- 17 new tests; `mise run check`: 9 contracts, mypy strict on 45 files, 111 tests. `docs/code/packages/models.md`, README and architecture updated.
- **Carry-over:** P0-04c (typed properties: data and storage).

### 2026-10-28 — Code walkthrough docs

- Added `docs/code/` (index, architecture, tooling, `packages/models.md`, template) and *why* comments in the model validators. Made updating it part of every task (CLAUDE.md, IMPL_PLAN, tracker).
- **Carry-over:** P0-04b, updating `docs/code/packages/models.md` with it.

### 2026-10-28 — P0-04a core models

- `perpetual.models`: status vocabulary with `worst_state`/`stack_state` (§30.1), `Evidence`, `ResourceNode`/`SourceReference`, `DependencyEdge`/`DependencyGroup`/`RelationshipType`, `GraphOverride` with per-kind payloads, `Stack`/`StackService`/`StackResource`, `RecoveryRequirement`/`DurationEstimate`/`BufferPolicy`/`DRStrategy`, `RecoveryMechanism`. Pydantic 2.14 is the first runtime dependency.
- 60 model tests covering every enforced rule; `mise run check` passes (9 contracts, mypy strict on 39 files, 94 tests).
- **Carry-over:** P0-04b (typed properties for compute and containers).

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
