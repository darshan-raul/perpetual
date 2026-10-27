> **Perpetual Engineering Specification (Revision 4)** — Part IV — Recovery DAG, RTO/RPO, Cost & Optimizer (§47–§60)  
> [↑ Spec Overview & Index](../../spec.md) · [← 03-rules-and-simulator.md](03-rules-and-simulator.md) · [05-iac-and-runbooks.md →](05-iac-and-runbooks.md)

---

# 47. Recovery Planning Model

There is one recovery plan per stack and failure scenario. It contains the actions for the mandatory roots and selected in-scope dependency paths (19.1): services, data stores, networking, traffic and supporting services, recovered together. Unselected alternatives remain assessed and visible without adding unnecessary recovery actions. Perpetual does not produce separate plans per service or per resource.

A resource shared with other stacks, such as a VPC, appears once in each stack's plan and is marked shared, so a later multi-stack view can avoid counting it twice.

A recovery plan is a DAG of actions.

Example:

```text
Create/validate network
       |
       +------------------+
       |                  |
       v                  v
Promote database      Scale ECS
       |                  |
       +---------+--------+
                 |
                 v
           Health checks
                 |
                 v
              DNS
```

---

# 47.1 Building the Recovery DAG: Phase Template + Refinement

Recovery actions come from rule packs (`recovery_actions()`, section 28), one set per resolved mechanism.

Each action declares a phase:

```text
0 decide       detect failure + decide to fail over (always present)
1 foundation   network, KMS, IAM, secrets
2 data         promote replica, restore snapshot, PITR restore
3 compute      scale ECS, deploy EKS workloads, pull images
4 traffic      health checks, smoke tests, DNS / routing control switch
```

### Default edges

Every action requires every action in the previous non-empty phase. This gives a correct but conservative plan.

### Refinement

A rule pack may replace the default prerequisites of its action with precise ones. Example:

```text
scale_ecs.prerequisites = [dr_network, dr_secrets, dr_image]
# does not wait for database promotion
```

This lets independent work overlap across phases. A plan built only from phase barriers overestimates RTO, so refinement is expected wherever the rule pack knows the real dependencies.

### Decide action

The `decide` action takes its duration from `RecoveryRequirement.detection_and_decision_seconds`. If that is not set, it uses the catalog default and is marked low confidence.

It is never omitted. In real incidents, human decision time often dominates RTO.

The resulting graph MUST be acyclic. A cycle is a rule-pack bug and fails plan generation with an explicit error.

---

# 47.2 Execution Method

The DR spec (56.2) selects one execution method per stack:

```text
scripts              default. Generated recovery scripts kept in the user's git
                     repository, run by an operator from a laptop with human
                     checks between stages. Never run from CI.
arc_region_switch    a compiled ARC Region switch plan (63.3). Steps that no
                     execution block covers run as script steps behind a manual
                     approval block.
```

The runbook (63) explains the flow. It is not an execution method.

RTO is computed for the selected method, so a stack still has one RTO per scenario:

- scripts: every human check is a gate that takes handoff time from the plan buffer (49.2);
- arc_region_switch: the DAG is grouped into sequential steps of parallel blocks (63.3). When grouping lengthens the critical path, the plan-as-compiled RTO is the result, and the ideal DAG RTO is shown only as context.

When ARC is selected, its per-plan monthly price counts toward total steady-state DR cost (59.1), taken from the versioned price table. Generated plans have no alarm triggers in v0.1; an operator starts them (101).

---

# 48. Recovery Action Model

```python
class RecoveryAction(BaseModel):
    id: str

    name: str

    action_type: str

    resource_ids: list[str]

    prerequisites: list[str]

    estimated_duration: DurationEstimate

    automation_level: Literal[
        "automatic",
        "semi_automatic",
        "manual",
    ]

    blocking: bool

    instructions: str | None
```

---

# 49. Recovery Duration

MVP should NOT fabricate statistical precision.

Represent duration as:

```python
class DurationEstimate(BaseModel):
    low_seconds: int | None
    expected_seconds: int | None
    high_seconds: int | None

    confidence: Literal[
        "high",
        "medium",
        "low",
    ]

    basis: str
```

Example:

```text
RDS promotion

Expected:
5-12 minutes

Confidence:
medium

Basis:
replica promotion mechanism +
current replication status
```

Do not report fake P99 estimates without empirical data.

---

# 49.1 Duration Catalog

Duration estimates come from a versioned catalog in configuration. They are never written inline in rule code.

```yaml
catalog_version: 2026-10-25

actions:
  rds_promote_read_replica:
    phase: data
    buckets:
      - when: { allocated_storage_gb: "<500" }
        low: 300
        expected: 600
        high: 900
    confidence: medium
    basis: "AWS documented promotion behaviour; not yet drill-verified"

  rds_restore_from_snapshot:
    phase: data
    buckets:
      - when: { allocated_storage_gb: "<100" }
        low: 900
        expected: 1500
        high: 2700
      - when: { allocated_storage_gb: "100-1000" }
        low: 1800
        expected: 3600
        high: 7200
    confidence: low
    basis: "heuristic; scales with storage size"

  decide_default:
    phase: decide
    low: 600
    expected: 1200
    high: 3600
    confidence: low
    basis: "default human detection and decision time; override per requirement"
```

The numbers above are illustrative.

Rules:

- every estimate records `catalog_version` and the matched bucket in `basis`;
- values are heuristic until replaced by drill data (section 53) or per-resource duration overrides in project configuration. Drill-derived values and explicit project overrides take precedence for that stack and action;
- for unmodeled/out-of-scope resources whose recovery mechanism is confirmed by the user (e.g. via an accepted advisory proposal in section 28.2 or candidate proposal in section 56.1), the catalog includes conservative, low-confidence generic fallback action types (`generic_promote_counterpart`, `generic_restore_from_backup`, `generic_rebuild_from_iac`) so the DAG builder can include them in the stack RTO calculation;
- an action with no catalog entry (and no project override) gets `expected_seconds = None`, which makes the RTO UNKNOWN. Never default it to zero.

Catalog estimates cover the action only. They MUST NOT include buffer. Buffer is added once, in section 49.2.

---

# 49.2 Plan Buffer

Real recoveries take longer than the sum of their steps: people hand work to each other, the whole stack has to be checked before traffic moves, and things go wrong. Perpetual models this as explicit buffer, shown separately, never hidden inside estimates.

```python
class BufferPolicy(BaseModel):
    handoff: DurationEstimate | None
    # Added before every manual or semi_automatic action.

    stack_validation: DurationEstimate | None
    # One stack-wide validation action: end-to-end checks across services,
    # after compute and before the traffic switch.

    contingency_percent: Decimal
    # Applied to the low, expected and high critical-path totals.
```

Rules:

- `handoff` becomes part of each manual or semi-automatic action's duration, so it counts only where that action is on the critical path;
- `stack_validation` is a real action in phase 4. Every traffic-switch action requires it;
- contingency is applied last, to the totals in section 50;
- defaults come from the duration catalog (section 49.1), for example `handoff_default` and `stack_validation_default`, with a contingency default of 10%. A requirement may override them (section 26);
- buffer has its own confidence and basis, like any estimate.

---

# 50. RTO Calculation

RTO should be calculated from the recovery DAG.

Concept:

```text
RTO = critical path through required recovery actions
```

Do NOT sum every recovery action because independent actions can execute in parallel.

Use DAG longest-path calculation over expected durations.

The critical path always starts with the `decide` action (section 47.1).

If any action on any path has `expected_seconds = None`, the RTO is UNKNOWN. The UI still shows the known partial path as context.

Calculate:

```text
low estimated RTO
expected estimated RTO
high estimated RTO
```

Each total is the critical path (including handoffs and stack validation) plus contingency (section 49.2).

RTO is reported for the stack only. Resource and service durations appear only as their contribution to the stack's critical path. Example:

```text
Stack RTO (expected)                      52m

  decide                                  20m
  data: rds_promote_read_replica          10m
  handoff before promotion (manual)        5m
  handoff before DNS switch (manual)       5m
  stack validation                         5m
  traffic: Route 53 failover               2m
  critical path                           47m
  contingency 10%                          5m

Off the critical path (runs in parallel):
  compute: scale ECS payments-api          8m
  compute: scale ECS checkout-api          6m
```

---

# 51. RPO Calculation

RPO logic is data-source-specific.

Examples:

### Snapshot recovery

Use:

```text
age of latest usable recovery point
```

### Replica

Use:

```text
replication lag
```

when measurable.

### S3

Use replication configuration and available metrics.

### DynamoDB Global Tables

Use replication posture.

### Stateful SQS queues

SQS has no native cross-Region message replication. When an in-scope SQS queue holds unacknowledged work without a cross-Region durable backing store (such as S3/DynamoDB persistence before enqueue or dual-Region publishing), in-flight messages in the primary Region remain unavailable for the duration of the Region outage; the RPO estimator flags this gap and bounds RPO accordingly rather than reporting zero data loss from queue recreation alone.

If Perpetual cannot confidently determine RPO:

```text
RPO = UNKNOWN
```

Never invent a number.

RPO is a range, like RTO. It uses the same `DurationEstimate` model (low, expected, high, confidence, basis). Example: replica lag sampled over a window gives low = minimum, expected = median, high = maximum.

Stack RPO is the worst (highest) RPO over the data stores that are required for the stack. If any required data store's RPO is UNKNOWN, the stack RPO is UNKNOWN.

Required stores follow the selected recovery paths (19.1). Observed RPO requires fresh, source-appropriate measurements or usable recovery-point timestamps under section 76. Proposed stores may use only an explicit versioned estimator with stated workload/configuration assumptions; without one, design RPO is UNKNOWN. Never reuse an old replica's lag as proof for a newly proposed replica. Data seeding, copy completion and replication health are deployment prerequisites (61.1), not facts established by a plan.

Out-of-scope data stores (section 24.1), such as log buckets, are excluded. Per-store RPOs are shown only as contributors to the stack RPO.

---

# 52. Target vs Predicted

UI:

```text
Target RTO       30m
Predicted RTO    42-58m
Status           FAIL

Target RPO        5m
Predicted RPO     2-7m
Status           UNCERTAIN
```

---

# 53. Proven RTO / RPO

Schema should support future DR drill results:

```python
class DRDrill(BaseModel):
    id: str
    stack_id: str

    started_at: datetime
    completed_at: datetime

    achieved_rto_seconds: int | None
    achieved_rpo_seconds: int | None

    status: str

    observations: list[str]
```

Do not build automated drills in initial MVP.

Drill results come from, in order of preference: an ARC Region switch execution report, the timestamped log of a recovery-script run (63.2), and a fault-injection or Resilience Hub test result. Importing them is post-MVP. Until a matching drill exists, a stack's readiness tier is at most CONFIGURED (3).

---

# 54. Optimization Engine

Perpetual must support two directions.

### Requirement-driven

```text
RTO/RPO/budget
      |
      v
best architecture
```

### Budget-driven

```text
budget
  |
  v
best achievable DR posture
```

---

# 55. Recovery Options

Every service rule pack can expose candidate recovery options.

```python
class RecoveryOption(BaseModel):
    id: str

    resource_id: str

    strategy: str

    mechanism: str

    estimated_monthly_cost: CostEstimate | None
    # Engine-produced range with line items (59.1); missing is not zero.

    estimated_rto: DurationEstimate | None

    estimated_rpo: DurationEstimate | None

    prerequisites: list[str]

    conflicts: list[str]

    properties: dict[str, Any]
```

Recovery options are per-resource inputs to the optimizer. Their RTO, RPO and cost are never shown to the user as a result. The user sees whole-stack candidates only (section 56).

---

# 56. MVP Optimizer

Do NOT start with Z3.

Do NOT start with a complex mathematical solver.

For the first implementation:

1. For each of the five stack strategies (section 27), ask each rule pack for its mechanism under that strategy, giving one candidate per strategy.
2. Add a bounded number of variants per strategy, where a rule pack offers alternatives. Example: warm standby with an RDS replica vs warm standby with Aurora Global. Limit: configurable, default 3 per strategy.
3. Reject candidates that violate hard prerequisites.
4. Calculate cost.
5. Build the recovery DAG (section 47.1).
6. Calculate RTO/RPO.
7. Calculate risk/readiness.
8. Determine Pareto-efficient candidates.

Do NOT take the cross product of per-resource options. It grows exponentially with stack size.

Strategy-driven generation gives roughly 5–15 candidates, which is small enough to compare exhaustively. The current architecture is always included as a baseline candidate.

Every candidate is a complete stack plan: a mechanism for every in-scope resource, one recovery DAG, and one stack-level cost, RTO and RPO.

---

# 56.1 LLM Candidate Planner

Ships in v0.2 (decision 2026-10-27). v0.1 uses only deterministic candidates (56).

Strategy templates give good starting points, but the best design often mixes them: for example Aurora Global Database for the orders database, backup and restore for a reporting database, and warm standby for the API tier. An LLM planner agent proposes such candidates.

Loop:

```text
deterministic candidates (section 56) + their evaluations
        |
        v
planner (LLM, with RAG + skills) -> up to N candidate proposals (default 5)
        |
        v
deterministic evaluation: prerequisites, cost, recovery DAG, RTO, RPO, readiness
        |
        v
results and failure reasons back to the planner -> refine (max 3 rounds, configurable)
        |
        v
Pareto frontier and selection (section 57), deterministic
```

Rules:

- a proposal is a typed `CandidateProposal`: for every in-scope resource, a mechanism chosen from the rule packs' `recovery_options()`, or a new `RecoveryOption` with `origin = llm`;
- a new option must cite a skill or knowledge-base document (including chunks ingested on demand via `web_search` / `web_fetch` for unmodeled resources; section 69.3), use action types that exist in the duration catalog, and pass the rule pack's prerequisite checks. An action without a catalog entry makes the candidate's RTO UNKNOWN, so it cannot be recommended;
- the planner never supplies cost, duration, RTO or RPO values. It may write the rationale for a candidate;
- deterministic candidates are always evaluated and kept, so the result is never worse than without the LLM.

---

# 56.2 DR Spec

The DR spec is the target DR design for a stack: the selected candidate written up so a person can approve it and the IaC transformer (section 61) can implement it.

```python
class DRSpec(BaseModel):
    id: str
    stack_id: str
    requirement_id: str
    candidate_id: str
    evaluation_input_id: str
    approval_digest: str | None
    # Hash of immutable inputs, selected candidate and exact approved design (56.3).

    changes: list[DRSpecChange]
    # Per resource: current mechanism -> target mechanism, the concrete change
    # (e.g. "add cross-Region read replica in ap-south-2"), prerequisites, and
    # the skill used.

    order: list[str]
    # Change IDs in apply order (e.g. DR network and KMS before replicas).

    execution_method: Literal["scripts", "arc_region_switch"] = "scripts"
    # How recovery runs (47.2). Part of the approved design and its digest.

    manual_steps: list[str]
    # Work outside Terraform, delivered as prerequisite scripts and SOPs (63.1):
    # backfill, quota increase requests, account setup, approvals.

    predicted: StackPrediction
    # RTO, RPO and monthly cost from the engine; before and after.

    findings_resolved: list[str]
    findings_remaining: list[str]

    rationale: str
    # v0.1: deterministic summary of engine results. From v0.2: LLM-written,
    # citing knowledge-base documents and skills.

    assumptions: list[str]

    status: Literal["draft", "approved", "superseded"]
    approved_by: str | None
    approved_at: datetime | None
```

The user approves a DR spec before any code is changed. It exports to Markdown for review outside the tool.

## 56.3 Immutable Evaluation Inputs and Approval Validity

Every assessment, simulation, candidate and DR spec references an immutable `EvaluationInput` manifest. It contains the primary/DR snapshot IDs and coverage timestamps; graph/override/group revisions; requirement and workload-profile revisions; engine/rule-pack versions; config, duration and price catalog hashes; and IDs/hashes of assumptions, user confirmations, skills and documents actually used. Record `evaluated_at` and freshness-policy version so old results can be reproduced without presenting them as current.

Before approval, attach the declared IaC roots, repository base commit and relevant tree digest, Terraform workspace/provider mappings, available backend lineage/serial, module/provider lock hashes, and rendered Kubernetes inventory identity. For a companion design record its template/input hashes instead. Declared IaC paths must be clean before creating the transformation baseline; report dirty paths without modifying them. Never persist credentials or raw state in the manifest.

Approval signs a canonical digest of this manifest, the selected candidate, changes, predictions, prerequisites and assumptions. Approved artifacts are immutable; editing creates a new draft. Recheck the digest and evidence freshness before starting/resuming transformation, verifying, and delivering a branch/PR. A new relevant scan, changed requirement/override/profile, changed base IaC/backend, changed effective rule/catalog input or expired required evidence supersedes approval and requires re-evaluation and approval of the new draft. Unrelated project changes do not invalidate it.

Edits made by the transformer to implement the approved changes are expected: they do not themselves invalidate design approval. Instead each verification report is bound to the exact resulting tree digest, saved-plan/render hashes and approved digest. Any later edit invalidates that report and triggers verification again. A changed target design or external baseline invalidates approval as above. A caller-supplied saved plan must match its recorded input tree/workspace/backend manifest; if provenance cannot be established, it is an analysis import only, not verification of the current changes. Manual prerequisite attestations are versioned evidence; resolving them triggers re-evaluation.

Persist invalidation reasons and retain prior artifacts for audit. Resume must not continue on a stale checkpoint. Test changed targets, scans, overrides, expired evidence, repository/backend changes, modified approved payloads, valid transformer retries and edits after verification.

---

# 57. Pareto Frontier

The optimizer should expose architecture trade-offs.

Example:

```text
                 Cost

Active/Active     $2400       3-6m
Hot Standby       $1600       8-15m
Warm Standby       $900      15-28m
Pilot Light        $300      45-90m
Backup Restore      $80       2-6h
```

Numbers above are illustrative only.

Actual numbers must come from resource-specific estimation.

Apply feasibility gates before recommendation. A candidate with any enforced FAIL or UNCERTAIN, unresolved design prerequisite, or unknown cost/RTO/RPO is shown with its reasons but is not recommended as target-compliant. Explicit deployment prerequisites may accompany a conditional design recommendation only under the modeled-assumption contract in 61.1; they remain pending for observed readiness. Unknown values never act as zero or dominate a known candidate. Compare complete candidates using high bounds for cost, RTO and RPO plus readiness; retain non-dominated candidates and break equivalent ties by stable ID. Budget-driven mode returns the frontier within the budget; it does not invent a single "best" trade-off without user targets. Keep the baseline even when infeasible. Limited candidate generation is not proof that no feasible architecture exists.

---

# 58. Cost Provider Interface

Do not tightly couple cost logic to Infracost.

Use:

```python
class CostProvider(Protocol):

    def estimate(
        self,
        candidate: ArchitectureCandidate,
    ) -> CostEstimate:
        ...
```

Implementations:

```text
StaticCostProvider
AWSPricingProvider
InfracostProvider
```

Future:

```text
CURHistoricalCostProvider
```

---

# 59. Cost Confidence

Cost estimates must include:

```text
estimated fixed cost
estimated variable cost
assumptions
confidence
```

Example:

```text
Estimated DR cost:
$417-$510/month

Assumptions:
- 2 ECS tasks warm
- current average traffic
- X GB cross-region replication
- current RDS storage
```

## 59.1 Workload Inputs and Budget Acceptance

`WorkloadProfile` is a versioned, stack-scoped input containing typed quantities (low/expected/high, unit, source, observation window, collected_at, confidence and optional expiry): requests/invocations, duration and concurrency, message volumes, stored GB, write/replication GB per month, network egress, and required serving capacity. Each cost formula declares which quantities it requires. Collect available usage through read-only metrics; allow explicit user estimates through CLI/API/UI. Missing inputs remain unknown rather than assuming idle usage. A forecast/user override records its assumptions and takes precedence only for the named quantity; estimates never become measured evidence.

`CostEstimate` contains currency USD, price-catalog version and age, workload-profile revision, component line items, fixed/variable subtotals, low/expected/high monthly totals, confidence and assumptions. Every line has a unique billable-resource/component key to avoid counting shared foundations twice within the stack. Units and monthly conversion (default 730 hours and 730/24 days) are versioned configuration. All bounds are nonnegative and ordered. Prices include Region and applicable account/pricing assumptions; missing or expired required prices and usage yield unknown totals, never zero. Mark zero only when the component is demonstrably free or unused. Price freshness is configurable (initial maximum age 30 days).

The requirement budget covers **total steady-state DR ownership cost**: all DR resources, replicated storage, backup retention, replication requests/transfer (including incremental charges in primary), and shared foundations attributed once within this stack. Existing DR resources still count. Normal primary operating cost is excluded. Report incremental change versus current DR cost separately. One-time setup/seeding costs and temporary failover operating cost are separate estimates and excluded from this monthly budget; name these exclusions beside every budget result. Cross-stack cost allocation remains deferred and shared costs are identified.

Budget comparison uses the full cost range: PASS when high <= budget, FAIL when low > budget, otherwise UNCERTAIN (including missing bounds). With no configured budget the gate is `not_enforced`; unknown cost still prevents a cost-ranked recommendation but does not by itself block observed readiness. Sum component bounds deterministically; confidence never changes acceptance. Unknown bounds must not be hidden by fixed-cost subtotals. Test missing usage/prices, stale prices, regional pricing, shared-cost deduplication, baseline versus incremental totals, exact-budget equality and ranges crossing the budget.

---

# 60. Remediation Planner

Findings must be transformable into remediation actions.

Example:

```text
Finding:
RDS has no regional recovery mechanism.

Candidates:

A:
Cross-region snapshot copy

B:
Cross-region read replica

C:
Aurora Global Database
if compatible
```

Each recommendation must explain:

```text
benefit
cost
RTO impact
RPO impact
prerequisites
trade-offs
```

RTO, RPO and cost impact are always stack-level. Perpetual applies the change, re-plans the whole stack and reports the difference. A component can get much faster while the stack barely moves, and the explanation must say why:

```text
Change:      RDS snapshot restore -> cross-Region read replica
RDS step:    60m -> 10m
Stack RTO:   95m -> 70m
Why:         ECS image pull from a non-replicated registry is now the critical path.
```

---

---

> [↑ Spec Overview & Index](../../spec.md) · [← 03-rules-and-simulator.md](03-rules-and-simulator.md) · [05-iac-and-runbooks.md →](05-iac-and-runbooks.md)
