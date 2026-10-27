# Perpetual — Engineering Specification

## Cloud Disaster-Recovery Readiness, Simulation and Architecture Compiler

**Status:** Engineering specification, revision 4  
**Initial cloud:** AWS  
**Primary implementation target:** Local single-user tool first ([§71.1](docs/spec/07-platform-ui-and-testing.md#711-deployment-model)); a hosted version is possible later  
**Primary user:** Cloud Architect / SRE / Platform Engineer / DevOps Engineer  
**Primary objective:** Determine whether a real stack can survive a specified failure while satisfying its RTO, RPO and cost constraints—and change the user's own Terraform and Kubernetes manifests to make it so.

---

## 1. Executive Summary & Core Question

Perpetual answers one question for a complete AWS **stack** (everything one product needs to serve its users: compute services, databases, queues, storage, networking, DNS, WAF, secrets, KMS keys and IAM roles):

> **If this stack loses its current AWS Region, can it continue operating within its promised RTO, RPO and budget?**

Individual resource checks (`RDS Multi-AZ = true`) do not establish stack survivability (`Resource readiness != Stack readiness`, [§1](docs/spec/01-product-and-aws-scope.md#1-product-definition)). Perpetual evaluates the whole stack end-to-end:

```text
AWS APIs + Terraform + CloudTrail / Flow Logs + optional Kubernetes
                              |
                              v
          Discovery, Normalization & Identity Resolution (§9–§15.4)
                              |
                              v
       Evidence-Backed Dependency Graph + User Overrides (§16–§23)
                              |
                       +------+------+
                       |             |
                       v             v
          DR Rule Packs (§28–§41)   Two-Pass Simulator (§43–§46)
               |                              |
               +--> Advisory Review (LLM)     |
                       |                      |
                       +----------+-----------+
                                  |
                                  v
              Recovery DAG, Buffer, RTO & RPO (§47–§53)
                                  |
                                  v
        Optimizer, Cost & LLM Candidate Planner -> DR Spec (§54–§60)
                                  |
                       +----------+----------+
                       |                     |
                       v                     v
      Isolated IaC Transformation (§61)   Recovery Artifacts (§63–§64): runbook,
      + Staged Verification (§61.1)       prerequisite + recovery scripts,
      -> Branch / PR (never applies)      optional ARC Region switch plan
                                          (generated, never run)
```

---

## 2. Specification Parts (Reader's Guide)

The full specification is organized into seven modular documents under [`docs/spec/`](docs/spec/). All section numbers (`§1`–`§109`) are preserved across the split so references in [`IMPL_PLAN.md`](IMPL_PLAN.md), [`TRACKER.md`](TRACKER.md) and [`CLAUDE.md`](CLAUDE.md) map 1:1.

| Part | Document | Sections | What it covers |
|---|---|---|---|
| **Part I** | [`01-product-and-aws-scope.md`](docs/spec/01-product-and-aws-scope.md) | `§1–§8.1` | Product definition, "LLM proposes, engine verifies" principle, positioning, and AWS services in scope (ECS, EKS, EC2/ASG, Lambda, RDS/Aurora, DynamoDB, S3, EBS, EFS, SQS, SNS, WAF, CloudWatch Logs, ECR, Secrets/SSM, KMS, IAM, Route 53, ELB, VPC, Quotas, Control vs Data Plane). |
| **Part II** | [`02-discovery-and-graph.md`](docs/spec/02-discovery-and-graph.md) | `§9–§26` | Input sources (Terraform saved-plan/state JSON, AWS APIs, Resource Explorer, Config, Kubernetes Levels 1 & 2), dependency evidence (`permitted`, `referenced`, `observed`, `asserted`), ambiguous attribution, `ResourceNode` & planned snapshot semantics (`§15.4`), `DependencyEdge` & `ALL`/`ANY`/`quorum` groups (`§19.1`), correlation-group confidence, `GraphOverride` review gate, stacks, services, RTO scope (`§24.1`), and `RecoveryRequirement`. |
| **Part III** | [`03-rules-and-simulator.md`](docs/spec/03-rules-and-simulator.md) | `§27–§46` | DR strategies, `RecoveryMechanism` overlay & strict `rebuild_from_iac` definition (`§27.1`), `DRRulePack` protocol, cross-cutting rules (`§28.1`), LLM advisory review (`§28.2`), `Finding` model, readiness dimensions, canonical status vocabulary (`§30.1`), ordered readiness table (`§31`), ECS/EKS/RDS checks, data gravity, and the two-pass failure simulator (`§43–§46`). |
| **Part IV** | [`04-recovery-and-optimizer.md`](docs/spec/04-recovery-and-optimizer.md) | `§47–§60` | Stack-level recovery DAG (phase template + refinement, `§47.1`), `RecoveryAction`, versioned duration catalog (`§49.1`), explicit plan buffer (`§49.2`), critical-path RTO (`§50`), data-store & stateful-SQS RPO (`§51`), target comparison (`§52`), optimizer & LLM candidate planner (`§54–§56.1`), `DRSpec` (`§56.2`), immutable `EvaluationInput` & approval digests (`§56.3`), Pareto frontier (`§57`), `CostProvider` & workload/budget contracts (`§58–§59.1`), and remediation deltas (`§60`). |
| **Part V** | [`05-iac-and-runbooks.md`](docs/spec/05-iac-and-runbooks.md) | `§61–§64` | Resource-to-code mapping, git worktree transformation agent with mandatory OS/container isolation (`§61`), four-stage verification separating design verification from observed readiness (`§61.1`), branch/PR delivery (`§62`), deterministic companion Terraform (`§62.1`), and recovery artifacts: explanatory runbook, prerequisite scripts and SOPs, laptop-run recovery scripts and optional ARC Region switch plans (`§63–§64`). |
| **Part VI** | [`06-security-and-llm.md`](docs/spec/06-security-and-llm.md) | `§65–§70` | Read-only security model, cross-account DR access (`§66`), secret/env/state redaction (`§67–§68`), replaceable LLM provider abstraction (`§69.1`), LangGraph agents (`§69.2`), local hybrid RAG knowledge base (`knowledge/domain/`, `sources.yaml`, and sanitized `web_search`/`web_fetch` enrichment, `§69.3`), versioned DR skills (`§69.4`), guardrails (`§69.5`), offline/eval testing (`§69.6`), and explainer (`§70`). |
| **Part VII** | [`07-platform-ui-and-testing.md`](docs/spec/07-platform-ui-and-testing.md) | `§71–§109` | Backend & local single-process deployment (`§71–§71.1`), React/React Flow UI (`§72`, `§80–§84`), monorepo & persistence (`§73–§75`), scan model & coverage/freshness/absence contract (`§76–§76.1`), drift (`§77`), REST API & CLI (`§78–§79`), reference fixtures & demos (`§85–§89`), four-tier test environments & review regression gates (`§90–§94`), quality/observability/error/unknown handling (`§95–§98`), phases, MVP definition, non-goals, engineering constraints, and product invariant (`§99–§109`). |

---

## 3. Non-Negotiable Architectural Invariants

1. **Stack-level survivability ([§1](docs/spec/01-product-and-aws-scope.md#1-product-definition), [§47](docs/spec/04-recovery-and-optimizer.md#47-recovery-planning-model), [§107](docs/spec/07-platform-ui-and-testing.md#107-product-invariant)):** One recovery plan, one RTO, one RPO, and one cost estimate per stack and failure scenario. Per-resource durations, options, and costs are inputs only.
2. **The LLM proposes; the deterministic engine, or the user, decides ([§2](docs/spec/01-product-and-aws-scope.md#2-product-principle), [§102 Rule 11](docs/spec/07-platform-ui-and-testing.md#102-engineering-constraints)):** Every number (RTO, RPO, durations, cost, confidence) comes from the engine. An LLM output can never upgrade a resource or stack state on its own, and uncited proposals are discarded.
3. **Missing evidence is `UNKNOWN`, never `PASS` or `READY` ([§30](docs/spec/03-rules-and-simulator.md#30-readiness-dimensions), [§31](docs/spec/03-rules-and-simulator.md#31-scoring), [§76.1](docs/spec/07-platform-ui-and-testing.md#761-coverage-freshness-and-absence), [§98](docs/spec/07-platform-ui-and-testing.md#98-unknown-state)):** Missing catalog entries, stale metrics, failed collectors, unreviewed low-confidence edges on required paths (`graph_not_reviewed`), or unresolved blocking advisories (`advisory_unresolved`) prevent `READY`.
4. **Ordered readiness composition ([§30.1](docs/spec/03-rules-and-simulator.md#301-status-vocabulary), [§31](docs/spec/03-rules-and-simulator.md#31-scoring)):** Simulation recoverability (`RECOVERABLE / UNKNOWN / UNAVAILABLE`) is separate from overall stack readiness (`READY / DEGRADED / NOT_READY / UNKNOWN`). A stack whose recovery path works but misses its RPO or budget is `RECOVERABLE` in simulation and `NOT_READY` overall.
5. **Planned snapshots vs. observed readiness ([§15.4](docs/spec/02-discovery-and-graph.md#154-planned-snapshot-semantics), [§61.1](docs/spec/05-iac-and-runbooks.md#611-verification)):** Design verification re-evaluates a planned snapshot (`terraform show -json <saved_plan_file>` + rendered manifests) and strips obsolete live operational proof on modified/replaced resources. Design verification can reach `Design verification: PASS (modeled)` or `PASS with deployment prerequisites`; only a fresh scan after deployment can establish observed `READY`.
6. **Immutable digests & approval binding ([§56.3](docs/spec/04-recovery-and-optimizer.md#563-immutable-evaluation-inputs-and-approval-validity)):** Every evaluation, `DRSpec` approval, and verification report is bound to an immutable `EvaluationInput` digest (scan IDs, overrides, requirements, catalog/pricing/workload versions, base git tree). Any input drift invalidates the approval before transformation or PR delivery.
7. **Code only, in an isolated sandbox ([§61](docs/spec/05-iac-and-runbooks.md#61-iac-transformation), [§62](docs/spec/05-iac-and-runbooks.md#62-change-delivery), [§65](docs/spec/06-security-and-llm.md#65-security-model)):** Perpetual never calls `GetSecretValue`, never persists secret/env values or raw logs, never sends state or secrets to an LLM, and executes repository tools only inside an OS/container-isolated git worktree with `apply`, `destroy`, `state`, and `kubectl apply` unreachable.

---

## 4. Complete Section Index (`§1`–`§109`)

### Part I — Product & AWS Scope ([`docs/spec/01-product-and-aws-scope.md`](docs/spec/01-product-and-aws-scope.md))
- **§1** Product Definition · **§2** Product Principle · **§3** Product Positioning (readiness tiers, AWS-native tools) · **§4** Initial Scope
- **§5** AWS Services In Scope: **§5.1** Containers (ECS) · **§5.2** Kubernetes / Amazon EKS · **§5.3** Amazon EC2 and Auto Scaling · **§5.4** AWS Lambda
- **§6** Data Services: **§6.1** Amazon RDS · **§6.2** Aurora · **§6.3** DynamoDB
- **§7** Storage & Messaging: S3, EBS, EFS · **§7.1** Messaging: Amazon SQS and Amazon SNS
- **§8** Supporting Services (ECR, Secrets, SSM, KMS, IAM, Route 53, ALB/NLB, CloudFront, WAF, CloudWatch Logs, VPC, Backup, Quotas, ARC, ACM) · **§8.1** Control Plane vs Data Plane

### Part II — Discovery, Evidence & Dependency Graph ([`docs/spec/02-discovery-and-graph.md`](docs/spec/02-discovery-and-graph.md))
- **§9** Input Sources · **§10** Terraform Input · **§11** Live AWS Discovery · **§12** Resource Explorer · **§13** AWS Config · **§14** Optional Kubernetes Discovery · **§14.1** Dependency Discovery Sources (SG, NetworkPolicy, IAM, CloudTrail, VPC Flow Logs, Ambiguous Attribution, Contradictions)
- **§15** Normalized Resource Model · **§15.1** Identity Resolution Across Sources · **§15.2** External Dependencies · **§15.3** Typed Resource Properties · **§15.4** Planned Snapshot Semantics
- **§16** Source Evidence Model · **§17** Dependency Graph · **§18** Graph Implementation · **§19** Edge Model · **§19.1** Dependency Groups and Redundancy (`ALL` / `ANY` / `quorum`) · **§20** Relationship Types
- **§21** Dependency Evidence · **§22** Dependency Confidence · **§23** User Review and Editing of the Graph (`GraphOverride`)
- **§24** Stacks · **§24.1** RTO Scope · **§25** Stack Discovery · **§26** DR Requirement Model

### Part III — DR Overlay, Rule Packs & Failure Simulator ([`docs/spec/03-rules-and-simulator.md`](docs/spec/03-rules-and-simulator.md))
- **§27** DR Strategies · **§27.1** Recovery Mechanisms and the DR Overlay (strict `rebuild_from_iac`)
- **§28** Service Rule Packs · **§28.1** Cross-Cutting Rules (`XREG-*`, `CTRL-PLANE-001`, `QUOTA-DR-001`, `REGION-SVC-001`, `ARC-RS-001`, `SSM-PARITY-001`, `OPS-ACCESS-*` & Evidence Producers) · **§28.2** LLM Advisory Review
- **§29** Finding Model · **§30** Readiness Dimensions · **§30.1** Status Vocabulary · **§31** Scoring & Ordered Readiness Composition
- **§32** ECS Rule Pack · **§33–§40** EKS Rule Pack (Control Plane, Compute, Scheduling, Add-Ons, Identity, Images, Storage) · **§41** RDS Rule Pack · **§42** Data Gravity
- **§43** Failure Simulator · **§44** Simulation Algorithm (Impact Pass & Recovery Pass) · **§45** Simulation Output · **§46** Failure Reason Chain

### Part IV — Recovery DAG, RTO/RPO, Cost & Optimizer ([`docs/spec/04-recovery-and-optimizer.md`](docs/spec/04-recovery-and-optimizer.md))
- **§47** Recovery Planning Model · **§47.1** Building the Recovery DAG: Phase Template + Refinement · **§47.2** Execution Method · **§48** Recovery Action Model
- **§49** Recovery Duration · **§49.1** Duration Catalog (incl. generic fallback actions) · **§49.2** Plan Buffer
- **§50** RTO Calculation · **§51** RPO Calculation (incl. stateful SQS) · **§52** Target vs Predicted · **§53** Proven RTO / RPO (`DRDrill`)
- **§54** Optimization Engine · **§55** Recovery Options · **§56** MVP Optimizer · **§56.1** LLM Candidate Planner · **§56.2** DR Spec · **§56.3** Immutable Evaluation Inputs and Approval Validity
- **§57** Pareto Frontier · **§58** Cost Provider Interface · **§59** Cost Confidence · **§59.1** Workload Inputs and Budget Acceptance · **§60** Remediation Planner

### Part V — IaC Transformation, Verification & Runbooks ([`docs/spec/05-iac-and-runbooks.md`](docs/spec/05-iac-and-runbooks.md))
- **§61** IaC Transformation (Mapping, Worktree Agent, Mandatory Execution Isolation) · **§61.1** Staged Verification (Static, Planned Graph, Modeled Design Verification, Deployment Prerequisites vs Observed Readiness)
- **§62** Change Delivery · **§62.1** Companion Fallback · **§63** Recovery Artifacts · **§63.1** Prerequisite Scripts and SOPs · **§63.2** Recovery Scripts · **§63.3** ARC Region Switch Plan · **§63.4** Terraform After Failover · **§64** Failback Is First-Class

### Part VI — Security Model & LLM Architecture ([`docs/spec/06-security-and-llm.md`](docs/spec/06-security-and-llm.md))
- **§65** Security Model · **§66** AWS Access (Cross-Account DR) · **§67** Secret Handling · **§68** Terraform State
- **§69** LLM Architecture: **§69.1** Provider Abstraction · **§69.2** Agents · **§69.3** Knowledge Base (RAG: `knowledge/domain/`, `sources.yaml`, User Docs, Dynamic `web_search`/`web_fetch`) · **§69.4** Skills · **§69.5** Data Sent and Guardrails · **§69.6** Testing and Evaluation · **§70** LLM Example

### Part VII — Platform, API/CLI/UI, Testing & Delivery ([`docs/spec/07-platform-ui-and-testing.md`](docs/spec/07-platform-ui-and-testing.md))
- **§71** Backend Technology · **§71.1** Deployment Model · **§72** Frontend Technology · **§73** Repository Structure · **§74** Rule-Pack Structure · **§75** Persistence Model
- **§76** Scan Model · **§76.1** Coverage, Freshness and Absence · **§77** Drift · **§78** REST API · **§79** CLI
- **§80** Primary UI · **§81** Stack Screen · **§82** Graph Editor · **§83** Fail Region UX · **§84** Explainability
- **§85–§89** Reference Demo Environments & Scenarios (ECS Broken, ECS Remediated, EKS Demo Failure)
- **§90** Testing Philosophy · **§90.1** Test Environments (Fixtures, Moto, Floci, Real-AWS Contract Suite) · **§90.2** Review Regression Gates · **§91–§94** Rule, Graph, RTO & Optimizer Tests
- **§95** Quality Requirements · **§96** Observability · **§97** Error Handling · **§98** Unknown State
- **§99** Initial Implementation Phases · **§100** MVP Definition · **§101** Explicit Non-Goals · **§102** Engineering Constraints · **§103** Definition of Done · **§104** First Implementation Task · **§105** First Vertical Slice · **§106** Second Vertical Slice — EKS · **§107** Product Invariant · **§108** Long-Term Direction · **§109** Success Criteria

---

<details>
<summary><b>Revision History (Revisions 2–4)</b></summary>

### Revision 4 changes

- 2026-10-27 release milestones: v0.1 is fully deterministic. LLM features (advisory review, candidate planner, transformation agent, explainer, knowledge base) ship in v0.2. v0.1 delivers companion Terraform for new resources and suggested edits for managed ones, and verifies designs from a saved plan the user supplies; Perpetual runs no repository tools until the v0.2 isolated runner (28.2, 56.1, 56.2, 61, 61.1, 62.1, 69, 99, 100).
- 2026-10-27 reorientation: Perpetual is positioned as a DR design compiler for AWS stacks, with ARC Region switch as an optional runtime; cross-cloud recovery targets are out of scope (3, 4, 101). Readiness tiers: design verified, configured, proven (3, 53). Recovery runs by recovery scripts (default, run from an operator's laptop) or a compiled ARC Region switch plan, chosen in the DR spec; RTO is computed for that method, and the runbook explains rather than executes (47.2, 56.2, 63). Terraform owns steady-state DR configuration; prerequisite scripts and SOPs cover backfill and account-level work (62, 63.1). New discovery and rules for Region switch plans, Route 53 Accelerated Recovery, SSM parameter parity and operator access (8, 8.1, 28.1).
- Modularized the specification into a concise executive overview (`spec.md`) and 7 topic files under `docs/spec/` preserving all `§1`–`§109` section numbers.
- 2026-10-27 review fixes: authoritative planned snapshots (15.4), ambiguous observation attribution (14.1), ALL/ANY/quorum dependencies (19.1), deterministic readiness composition (31), immutable evaluation/approval inputs (56.3), workload and budget contracts (59.1), isolated transformation and staged verification (61–61.1), scan coverage/freshness (76), and corresponding regression gates (90.2). Complete evidence collection for quotas, availability, metrics, EFS and initial DynamoDB support; verification consumes saved-plan JSON.
- Perpetual no longer only assesses. It fixes: it changes the user's own Terraform and Kubernetes manifests so the stack meets its DR targets, and delivers the change as a branch or pull request. It never applies changes to AWS or Kubernetes (61, 62, 101).
- LLM agents, built on LangGraph, take part in three stages: an advisory review after the rule engine (28.2), candidate generation in the optimizer (56.1), and IaC transformation (61). They use a local knowledge base (RAG) and versioned skills (69.3, 69.4).
- The governing rule is "the LLM proposes, the engine verifies". Facts, numbers, states and feasibility still come only from deterministic code or the user. Every LLM proposal is checked by re-running assessment and simulation before it is shown as a result (2, 61.1).
- New artifact: the DR spec, the approved target DR design for a stack, which the transformation implements (56.2).
- The LLM provider is replaceable: any LangChain chat model, including OpenAI-compatible endpoints such as OpenRouter, Anthropic, Bedrock and local Ollama models. Each agent role can use a different model (69.1).
- Deterministic companion Terraform stays as the fallback when no IaC repository or LLM is configured (62.1).
- LLM features are opt-in per project, with a clear record of what is sent. Terraform state, secret values, env values and raw logs are never sent (65, 69.5).
- Expanded v0.1 AWS service scope to include standalone EC2 and Auto Scaling, AWS Lambda, Amazon SQS, Amazon SNS, AWS WAF (WAFv2), and Amazon CloudWatch Logs (5.3, 5.4, 7.1, 8).
- The local knowledge base ships curated DR domain reference docs for all in-scope AWS services in `knowledge/domain/` alongside `knowledge/sources.yaml`, and agents have controlled `web_search` and `web_fetch` tools (with sanitized, non-sensitive queries) to fetch documentation for out-of-scope or unmodeled resources, persist and index it into the local knowledge base to improve the local docs, and cite those chunks during advisory review and DR candidate planning (28.2, 56.1, 69.2, 69.3, 69.5).

### Revision 3 changes

- The unit of DR is the **stack**: everything one product needs to serve its users, including its microservices, data stores, VPCs, load balancers and supporting services. "Workload" is renamed to "stack" throughout, except where it means Kubernetes objects such as Deployments (1, 24).
- A stack groups its resources into services for display and explanation. Services have no DR targets, plans, RTO or RPO of their own (24).
- Monitoring, logging and CI/CD resources are outside the stack's RTO scope. They are still shown and assessed but never block the stack or add time to its plan (24.1).
- There is one recovery plan, one RTO and one RPO per stack and failure scenario. Per-resource estimates are inputs to that plan, never results on their own (47, 50, 55, 60).
- Plan buffers are explicit: handoff time before manual actions, a stack-wide validation action and a contingency percentage (49.2).
- New dependency sources: Kubernetes NetworkPolicies, CloudTrail and VPC Flow Logs. Every edge records whether its evidence says the dependency is permitted, referenced or observed (14.1, 16, 22).
- Perpetual shows the whole computed graph, and the user can add, edit and delete edges and add nodes. Edits are stored as overrides that survive rescans (23, 82).
- A stack cannot show DR READY while low-confidence edges on its required paths are unreviewed; it shows UNKNOWN (graph not reviewed). Simulation is always allowed (23).
- Graph review comes before simulation in the workflow. YAML overrides work from the CLI phases; the graph editor is the first web UI (99, 100).
- Added test environments (90.1): fixtures for the engine, moto and the Floci emulator for collectors, synthetic CloudTrail and flow-log files, and a small real-AWS contract suite at fixed checkpoints.
- Perpetual is a local tool: one Python process serves the API and a static React UI, with SQLite by default. The UI moves from Next.js to Vite + React. PostgreSQL is for a later hosted version; Docker Compose only runs test dependencies such as Floci (18, 71, 71.1, 72, 73).

### Revision 2 changes

- Added the recovery-mechanism overlay (27.1): every primary resource maps to how it is recovered in the DR Region. "Reproducible" is now defined.
- Added a canonical status vocabulary (30.1) used by simulation, assessment and UI.
- Rewrote the simulation algorithm (44) as an impact pass followed by a recovery pass. It handles cycles and shared nodes.
- Recovery plans are built from a phase template, then refined into a DAG (47.1). A detect-and-decide action is always included.
- Durations come from a versioned duration catalog (49.1).
- RPO is now a range, like RTO (51, 55).
- Added cross-cutting rules (28.1): control-plane dependencies, DR quotas, primary-Region references in config and IAM.
- Added identity resolution across sources (15.1), external dependencies (15.2) and typed resource properties (15.3).
- Evidence combination is pluggable and accounts for correlated evidence (22). Edge rejection uses evidence fingerprints (23).
- Findings attach to resources and can belong to several stacks (29).
- The target Region lives only on `RecoveryRequirement` (24, 26).
- Scan status includes `partial` (76).
- The optimizer generates candidates per strategy (56).
- DR may live in a separate AWS account (66).
- Implementation phases are reordered engine-first and CLI-first; the web UI comes later (99, 104).

</details>
