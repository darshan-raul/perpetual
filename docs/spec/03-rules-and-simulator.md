> **Perpetual Engineering Specification (Revision 4)** — Part III — DR Overlay, Rule Packs & Failure Simulator (§27–§46)  
> [↑ Spec Overview & Index](../../spec.md) · [← 02-discovery-and-graph.md](02-discovery-and-graph.md) · [04-recovery-and-optimizer.md →](04-recovery-and-optimizer.md)

---

# 27. DR Strategies

Define five stack-level strategy families:

```text
backup_restore
pilot_light
warm_standby
hot_standby
active_active
```

Do not assume every AWS service maps directly to these five terms.

Instead:

```text
stack strategy
        |
        v
service-specific recovery mechanism
```

Example:

```text
Warm standby stack

ECS:
minimum tasks running

RDS:
cross-region read replica

S3:
continuous replication

ECR:
cross-region replication

Route53:
failover routing

Secrets:
regional replication strategy
```

---

# 27.1 Recovery Mechanisms and the DR Overlay

The dependency graph describes the primary environment. That alone can only answer "what is impacted?" It cannot answer "what is recoverable?"

For every resource in a stack, Perpetual MUST resolve how that resource is provided in the DR target. This mapping is the DR overlay.

```python
class RecoveryMechanism(BaseModel):
    id: str

    primary_resource_id: str

    target_region: str
    target_account_id: str

    kind: Literal[
        "live_counterpart",            # replica, replicated repo, DR service, replicated secret
        "restore_from_recovery_point", # snapshot, backup, PITR
        "rebuild_from_iac",            # reproducible: see definition below
        "global_service",              # not Region-scoped (subject to section 8.1)
        "external",                    # user-declared posture (section 15.2)
        "none",                        # no recovery path exists
        "unknown",                     # not enough evidence
    ]

    counterpart_resource_id: str | None
    # The DR resource, if it exists.

    recovery_point_ids: list[str]
    # Snapshots or backups used, if any.

    dr_dependency_ids: list[str]
    # What the mechanism itself requires in the DR target: DR KMS key,
    # DR subnet group, DR image, DR role, etc.

    dependency_groups: list[DependencyGroup]
    # Explicit alternatives under 19.1; ungrouped dr_dependency_ids remain ALL.

    control_plane_dependent: bool
    # True if recovery needs control-plane API calls during the event (section 8.1).

    evidence: list[Evidence]
    confidence: float
```

Mechanisms are resolved by the rule pack for the resource's service (section 28).

### Definition: reproducible

A resource is reproducible, `kind = rebuild_from_iac`, only when ALL of the following hold:

- it has a Terraform address (or other IaC origin evidence);
- its configuration does not hard-code the primary Region or primary-only ARNs;
- the DR target Region is a supported input, for example a provider alias or region variable is detectable;
- its own DR dependencies resolve.

If any of these cannot be shown, the mechanism is `unknown`, never `rebuild_from_iac`. A user may confirm reproducibility explicitly. That evidence is recorded as `user_confirmation`.

### DR-side dependencies

The DR overlay is itself graph-shaped. A `live_counterpart` RDS replica requires a DR KMS key and a DR subnet group, and those require their own mechanisms.

The simulator (section 44) walks the DR overlay. It does not assume a counterpart is usable just because it exists.

---

# 28. Service Rule Packs

Each AWS service should implement a rule pack.

Example interface:

```python
class DRRulePack(Protocol):
    service: str

    def assess(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> list[Finding]:
        ...

    def recovery_options(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> list[RecoveryOption]:
        ...

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        ...

    def recovery_actions(
        self,
        mechanism: RecoveryMechanism,
        context: AssessmentContext,
    ) -> list[RecoveryAction]:
        ...
```

---

# 28.1 Cross-Cutting Rules

Some DR failures live between resources or outside any single service. They have their own rule pack, `rules/cross/`.

Initial rules:

```text
XREG-CONFIG-001   Task definition, ConfigMap or Lambda env contains a primary-Region
                  endpoint, ARN or Region string.
XREG-IAM-002      DR role policy grants access only to primary-Region resource ARNs
                  (e.g. DR execution role -> ap-south-1 KMS key ARN).
XREG-KMS-003      Data replicated to the DR Region but encrypted with a key that is
                  not usable in the DR Region.
CTRL-PLANE-001    Recovery path requires a control-plane mutation (Route 53 record
                  edit, IAM change) during the event. When the scenario includes
                  us-east-1, a Route 53 public-zone edit is BLOCKED without
                  Accelerated Recovery and waits for the catalog's Accelerated
                  Recovery duration with it (8.1).
QUOTA-DR-001      DR Region service quota below the capacity the recovery plan needs
                  (Fargate vCPU, EC2 On-Demand vCPU, ENIs, EIPs, LB count).
REGION-SVC-001    Service, feature or instance type used in primary is unavailable
                  in the DR Region.
ARC-RS-001        An existing ARC Region switch plan for the stack misses a required
                  recovery action, orders blocks against a prerequisite edge, skips a
                  required step in ungraceful mode, or reports evaluation status
                  actionRequired. A passed evaluation is evidence, never READY.
SSM-PARITY-001    SSM parameter names the stack uses exist in the primary Region but
                  not in the DR Region (compares names and versions, never values).
OPS-ACCESS-001    Operator sign-in depends on the failed Region: the IAM Identity
                  Center home Region has no replica elsewhere and no break-glass path
                  is declared. Recommend a replica in an enabled-by-default Region
                  (it need not be the DR Region; it needs a multi-Region customer
                  managed KMS key) plus a break-glass role.
OPS-ACCESS-002    The declared operator path to DR resources (VPN, bastion, private
                  EKS or database endpoints) depends on the failed Region. UNKNOWN
                  when no operator access profile is declared.
```

Operator access is part of every stack's recovery path, because both execution methods (47.2) need a person: scripts run from an operator's laptop, and ARC plans are started and approved by an operator. The user declares an operator access profile in the `operator_access` section of `perpetual.yaml`, kept in git and reviewed like code. The UI shows it read-only. Example:

```yaml
operator_access:
  identity:
    source: iam_identity_center     # or iam_users, external_idp
    home_region: ap-south-1
    replica_regions: []             # discovered when readable; declared otherwise
  break_glass:
    method: iam_role                # how operators sign in if the identity source fails
    description: "role in DR account, credentials in offline vault"
  network:                          # how laptops reach private endpoints
    - target: eks_api_private
      path: vpn
      terminates_in: ap-south-1
  tools:
    uv: "0.8"
    kubectl: "1.33"
```

Discovered facts take precedence over declared ones when both exist. Facts that are neither discovered nor declared remain UNKNOWN, and a missing section leaves OPS-ACCESS-001/002 UNKNOWN.

Quota and service-availability checks use read-only APIs only (`service-quotas:List*`, `ec2:DescribeInstanceTypeOfferings`).

The discovery layer must supply these facts before rules run: quota values and available usage/headroom, instance-type offerings, Region/feature capability metadata, CloudWatch metric samples for replication/usage, EFS filesystem/replication/backup metadata, and DynamoDB tables/PITR/backups/replica/index/KMS metadata. Feature availability that an API or versioned capability source cannot establish remains UNKNOWN. Quota limits without current usage cannot prove sufficient headroom. CloudWatch Logs discovery is not a substitute for CloudWatch Metrics collection. Each rule declares its required coverage and freshness (76); the plan's coverage matrix owns collection, normalization, actions, estimates and tests. Initial DynamoDB assessment and basic existing-replica/backup recovery are in v0.1; advanced topology optimization may be deferred.

When reading environment variables or ConfigMaps, persist only the matched fact (e.g. "env var DB_HOST matches primary RDS endpoint"). Never persist the value (section 67).

---

# 28.2 LLM Advisory Review

Ships in v0.2 (decision 2026-10-27).

Rule packs are deterministic and cover known patterns. An advisory review, run by an LLM agent after the rule packs, looks for what they miss: unusual dependencies, application configuration that ties a service to the primary Region, services without a rule pack, and organization-specific standards from the knowledge base.

Inputs: the stack subgraph (IDs, types, non-secret properties), deterministic findings and mechanisms, matched configuration facts (names only, never values), the IaC source of the stack's resources (section 61), knowledge-base retrievals and relevant skills (sections 69.3, 69.4). When a stack contains an out-of-scope or unmodeled resource type whose DR behaviour is not yet in the local knowledge base, the agent may use `web_search` and `web_fetch` (section 69.3) to fetch official documentation, persist and index it into the local knowledge base, and cite those chunks in its proposals.

Outputs are typed proposals:

```python
class AdvisoryItem(BaseModel):
    id: str
    stack_id: str

    kind: Literal[
        "finding",      # a risk the rule packs did not raise
        "edge",         # a dependency the graph is missing
        "mechanism",    # how a resource without rule-pack coverage could be recovered
        "question",     # something only the user can answer
    ]

    payload: dict[str, Any]
    # Validated per kind against Finding, DependencyEdge or RecoveryMechanism.

    citations: list[Citation]
    # Resource IDs, evidence IDs, file:line, knowledge-base chunk IDs, skill IDs.
    # Items without citations are discarded.

    status: Literal["proposed", "accepted", "dismissed"]
    fingerprint: str
    model: str
    run_id: str
```

Effect on results:

- a proposed **edge** enters the review queue (section 23) with `source_type = llm_inference`, `basis = referenced` (it must cite the file and line, or the configuration fact, it read), and confidence capped by configuration (default 0.5);
- a proposed **mechanism** leaves the resource's mechanism `unknown`; the suggestion is shown beside it. It becomes the mechanism only when the user accepts it (evidence `user_confirmation`);
- a proposed **blocking finding** keeps the stack from READY: it shows `UNKNOWN` with reason `advisory_unresolved` until the user accepts or dismisses it;
- accepted items become ordinary findings, edges or mechanisms with the user's confirmation as evidence. Dismissed items are stored by fingerprint and not re-proposed unless their inputs change, as with edge rejections.

Advisory review never runs inside a rule pack (section 102, rule 4).

# 29. Finding Model

```python
class Finding(BaseModel):
    id: str

    stack_ids: list[str]
    # A finding on a shared resource belongs to every stack that includes it.

    resource_id: str | None

    category: str

    severity: Literal[
        "critical",
        "high",
        "medium",
        "low",
        "info",
    ]

    title: str

    description: str

    evidence_ids: list[str]

    impact: str

    remediation: str | None

    blocking: bool
    # Compatibility flag: effect != warning; simulation consults effect, not this flag.
    effect: Literal["recovery_blocker", "target_violation", "warning"]

    rule_id: str
```

Rule IDs must be stable.

Example:

```text
RDS-REGION-001
EKS-STORAGE-004
ECS-ECR-002
NET-NAT-003
KMS-KEY-001
```

---

# 30. Readiness Dimensions

Calculate stack readiness separately across:

```text
Compute
Data
Storage
Network
Identity
Configuration
Traffic
Observability
Recoverability
```

UI example:

```text
Stack: checkout

Compute            88%
Data               70%
Storage            64%
Network            92%
Identity           55%
Traffic           100%

Overall status:
NOT DR READY
```

Do not make the percentage itself authoritative.

Blocking findings matter more.

Example:

```text
Readiness score: 94%

Critical blockers: 1

Result:
NOT DR READY
```

A dimension with no implemented rules, or no evidence, reports UNKNOWN. It does not report 100%. In v0.1, Observability and Recoverability may report UNKNOWN until their rules exist.

Observability covers the out-of-scope resources from section 24.1. It is reported but never makes the stack NOT_READY.

---

# 30.1 Status Vocabulary

One canonical vocabulary is used across the engine, API and UI. UI colours and labels map onto these values. They are not separate states.

### Resource state under simulation

```text
SURVIVES      unaffected by the failure (outside the failed scope, or global
              with a data-plane path)
RECOVERABLE   affected, but a resolved mechanism (27.1) and all its DR
              dependencies are usable
BLOCKED       affected, and the mechanism is "none" or a required DR dependency
              is BLOCKED
UNKNOWN       affected, and the mechanism or a required DR dependency is "unknown"
```

Modifier flag:

```text
possible_impact  set when the impact only arrives over low-confidence or
                 likely_required edges
```

Ordering, worst first, used when combining states:

```text
BLOCKED > UNKNOWN > RECOVERABLE > SURVIVES
```

### Stack state

The stack takes the worst state over its required resources, then maps to:

Required resources here means mandatory roots and the dependency members selected under 19.1; failed unused alternatives do not force UNAVAILABLE. Target violations are evaluated separately by section 31.

```text
SURVIVES / RECOVERABLE  ->  RECOVERABLE (application can operate after failover)
UNKNOWN                 ->  UNKNOWN
BLOCKED                 ->  UNAVAILABLE
```

### Readiness result (section 31)

```text
READY | DEGRADED | NOT_READY | UNKNOWN
```

### Target comparison (section 52)

```text
PASS       predicted high bound <= target
FAIL       predicted low bound  >  target
UNCERTAIN  target lies within the predicted range, or the estimate is unknown
```

### UI mapping

```text
green = SURVIVES    amber = RECOVERABLE    red = BLOCKED / UNAVAILABLE    grey = UNKNOWN
```

---

# 31. Scoring

Use deterministic scoring.

Example rule:

```text
critical finding   -25
high               -10
medium              -5
low                 -2
```

This is illustrative.

Implement scoring weights as configuration.

The stack readiness result is:

```text
READY
DEGRADED
NOT_READY
UNKNOWN
```

`UNKNOWN` is essential when evidence is insufficient.

Never convert missing evidence into PASS.

### Readiness composition

One deterministic function consumes simulation state, in-scope findings, coverage/freshness, review/advisory gates, and RTO/RPO/budget comparisons. Evaluate these rows in order; percentages never override the result:

| Condition | Result |
|---|---|
| Proven recovery blocker on a required selected path, simulation UNAVAILABLE, or any enforced target comparison FAIL | NOT_READY |
| Required recovery/evidence/coverage is unknown or stale; selected-path review or attribution unresolved; blocking advisory unresolved; or any enforced comparison UNCERTAIN | UNKNOWN |
| All enforced comparisons PASS and recovery is proven, but nonblocking in-scope findings or loss of redundant alternatives remain | DEGRADED |
| All enforced comparisons PASS, required evidence and reviews are complete, and no in-scope findings remain | READY |

RTO and RPO are enforced targets. Budget is enforced only when configured (59.1). A missing evaluator, including RPO before P8, yields UNCERTAIN, never an implicit PASS. A proven stateless stack has RPO zero with explicit basis; failure to discover its stores is not evidence of statelessness. Unimplemented required readiness checks yield UNKNOWN; out-of-scope Observability and unrelated unimplemented dimensions do not block. Unknowns cannot hide a proven negative result.

Classify findings as `effect = recovery_blocker | target_violation | warning`, separately from severity. Recovery blockers mean the required recovery operation cannot execute; target violations mean it can execute but misses a constraint. Excess replica lag violates RPO and makes readiness NOT_READY when the comparison is FAIL, but does not make a usable replica BLOCKED or the application UNAVAILABLE. Warning findings produce DEGRADED only after the other gates pass. Scores are descriptive.

The same composition function evaluates observed and design snapshots, but every output carries `evaluation_kind = observed | design` (61.1). Design checks explicitly evaluate the approved modeled assumptions; pending operational prerequisites remain pending and cannot be reused as observed evidence. A passing design is displayed as "design meets targets", never as observed DR READY. Exhaustively test precedence, boundary equality, missing evaluators, disabled budget, stateless RPO, review gates and recovery possible with RPO FAIL.

---

# 32. ECS Rule Pack

Initial ECS checks should include:

"Reproducible" in this section and in section 34 has the strict meaning defined in 27.1. Without that evidence, the result is UNKNOWN.

### Compute

- service exists in DR Region or is reproducible;
- task definition available;
- compatible launch/capacity mechanism;
- scaling configuration available.

### Image

- every referenced container image exists in reachable ECR/registry;
- ECR replication configured where required.

### Secrets

- referenced Secrets Manager entries available;
- referenced SSM parameters available;
- KMS dependencies available.

### IAM

- task role exists;
- execution role exists;
- relevant trust configuration exists.

### Network

- DR subnets available;
- security groups available;
- required VPC endpoints/NAT path available;
- load balancer configuration available.

### Traffic

- ALB/NLB available or reproducible;
- target group available;
- health-check configuration valid;
- Route 53 recovery path exists.

### Data

Propagate readiness from:

- RDS;
- S3;
- EFS;
- queues;
- other detected dependencies.

---

# 33. EKS Rule Pack

EKS requires nested readiness.

```text
EKS readiness
|
+-- Control plane
+-- Compute
+-- Add-ons
+-- Stacks
+-- Identity
+-- Storage
+-- Network
+-- Traffic
+-- External dependencies
```

---

# 34. EKS Control Plane Checks

Check:

- DR EKS cluster exists or is reproducible (strict definition in 27.1; otherwise UNKNOWN);
- cluster version;
- VPC;
- subnets;
- cluster security group;
- IAM role;
- encryption dependencies;
- endpoint access.

---

# 35. EKS Compute Checks

Check:

- required node groups;
- required instance families;
- desired/min/max capacity;
- Fargate profiles;
- Karpenter configuration if visible;
- capacity constraints.

If a stack requires:

```yaml
nodeSelector:
  accelerator: gpu
```

and no compatible DR node capacity exists:

```text
BLOCKING FINDING
```

---

# 36. EKS Scheduling Checks

If Kubernetes state is available, detect whether workloads depend on:

- nodeSelector;
- required node affinity;
- taints/tolerations;
- topologySpreadConstraints;
- PVC zone constraints;
- architecture such as amd64/arm64;
- special hardware.

The goal is not to build a full Kubernetes scheduler.

The goal is to detect obvious DR scheduling blockers.

---

# 37. EKS Add-On Checks

Check required platform components where detected:

```text
VPC CNI
CoreDNS
kube-proxy
EBS CSI
EFS CSI
AWS Load Balancer Controller
Pod Identity Agent
ExternalDNS
External Secrets
cert-manager
GitOps controllers
```

Example:

```text
Application uses EBS PVCs.

DR cluster lacks EBS CSI driver.

Result:
EKS-STORAGE BLOCKER.
```

---

# 38. EKS Identity Checks

Check:

- service account references;
- IRSA role;
- Pod Identity association;
- IAM role availability;
- trust relationship;
- required KMS access;
- known cross-Region resource ARNs.

---

# 39. EKS Image Checks

For every workload image:

```text
registry
repository
tag/digest
```

Determine whether the image can be pulled from the DR environment.

Missing critical application image:

```text
BLOCKER
```

---

# 40. EKS Storage Checks

For StatefulSets/PVCs determine:

```text
storage class
volume type
volume ID if bound
size
AZ
snapshot coverage
backup coverage
KMS
recovery mechanism
```

Do not mark EKS DR-ready merely because cluster configuration is replicated.

---

# 41. RDS Rule Pack

Assess:

- backup retention;
- latest successful recovery point;
- cross-Region backup;
- read replica;
- global database where applicable;
- encryption;
- destination KMS;
- subnet group;
- parameter groups;
- security groups;
- replication status;
- replication lag if available;
- storage size;
- expected restore path.

Example:

```text
RDS Multi-AZ = yes

AZ resilience:
PASS

Regional resilience:
NOT ESTABLISHED
```

---

# 42. Data Gravity

Resource models must include relevant volumetric properties.

Examples:

```text
RDS:
allocated_storage_gb
iops
throughput
write_rate
replication_lag

EBS:
size_gb
snapshot_age

ECR/container:
image_size_mb

ECS:
desired_count

EKS:
replica_count
node_count
PVC size
```

These values affect recovery modelling.

---

# 43. Failure Simulator

The first supported simulation MUST be:

```text
AWS Region unavailable
```

Example API:

```python
simulate_failure(
    stack_id="payments",
    failure=RegionFailure("ap-south-1"),
)
```

Failure scenarios are a type hierarchy, not a single case:

```python
class FailureScenario(BaseModel):
    kind: str

class RegionFailure(FailureScenario):    # MVP
    kind: Literal["region"] = "region"
    region: str

class AZFailure(FailureScenario):        # later
    kind: Literal["az"] = "az"
    availability_zone: str

class LogicalCorruption(FailureScenario):  # later: ransomware, bad deploy, bad migration
    kind: Literal["logical_corruption"] = "logical_corruption"
    resource_ids: list[str]
    detected_after_seconds: int
```

`LogicalCorruption` matters because replication copies corruption to the DR copy. Under it, `live_counterpart` mechanisms are not valid recovery paths. Only recovery points older than the corruption are.

The simulator MUST dispatch on `kind`, so new scenarios can be added without changing the core algorithm.

---

# 44. Simulation Algorithm

Simulation runs in two passes.

```text
Pass 1 — Impact    over the primary dependency graph
Pass 2 — Recovery  over the DR overlay (section 27.1)
```

### Pass 1: Impact

Which resources does the failure affect?

```text
seed:      every node in the failed scope (e.g. region == ap-south-1)
spread:    to dependents whose operational requirement groups (19.1) are no
           longer satisfied; skip structural, replicates_to and backed_up_by edges
required        + confidence >= threshold   -> affected
likely_required or confidence < threshold   -> affected, possible_impact = true
optional                                    -> not affected
unknown criticality                         -> affected, possible_impact = true
```

Global and external nodes are seeded as affected only when the scenario or their declared posture says so.

Out-of-scope resources (section 24.1) are evaluated and shown, but their state does not spread to in-scope resources and does not count toward the stack state.

Thresholds come from configuration.

### Pass 2: Recovery

Can each affected resource be provided in the DR target?

For every affected node, look up its `RecoveryMechanism`:

```text
none                        -> BLOCKED
unknown                     -> UNKNOWN
live_counterpart /
restore_from_recovery_point /
rebuild_from_iac            -> evaluate dr_dependency_ids recursively;
                               state = combine own checks with evaluated DR
                               requirement groups (19.1)
                               (ordering in 30.1)
global_service              -> SURVIVES, unless control_plane_dependent and the
                               control-plane Region is in the failed scope
                               (then UNKNOWN + CTRL-PLANE-001)
external                    -> from declared posture
```

A mechanism with a proven `recovery_blocker` on a required selected path, such as a missing required DR image, is BLOCKED. Target violations such as excess replica lag affect readiness through section 31, not the ability to recover. Unknown operational checks remain UNKNOWN.

Unaffected nodes are SURVIVES.

### Combination and termination

- ALL requirements combine with `worst()` using 30.1; ANY/quorum requirements use 19.1.
- Recursion is memoised per node and cycle-safe. A node revisited on the current path is treated as UNKNOWN for that path, and the cycle is recorded as evidence.
- The stack state combines mandatory roots and selected in-scope dependency paths under 19.1, mapped as in 30.1. Do not aggregate every alternative as mandatory.

### Explanation

For every BLOCKED or UNKNOWN stack, record the path from the stack root to the root cause.

The path crosses from the primary graph into the overlay where needed:

```text
checkout -> checkout-api -> [mechanism: live_counterpart] -> DR ECR repo -> image missing
```

---

# 45. Simulation Output

Example:

The result leads with the stack. Resources appear underneath as the reasons for it.

```text
Failure:        ap-south-1 unavailable
Stack:          payments

Stack state:    UNAVAILABLE
Root blocker:   Container image is not available in DR Region.

Resources (in RTO scope):
Route53              SURVIVES     (data-plane failover)
ALB                  RECOVERABLE  (rebuild_from_iac)
ECS payments-api     BLOCKED      (DR dependency ECR BLOCKED)
RDS                  RECOVERABLE  (live_counterpart)
S3                   RECOVERABLE  (live_counterpart)
ECR                  BLOCKED      (mechanism: none)
Secrets              RECOVERABLE  (live_counterpart)
KMS                  RECOVERABLE  (live_counterpart, multi-Region key)

Out of RTO scope (not counted):
CloudWatch log groups   UNKNOWN
CodePipeline            BLOCKED

Graph review:   2 unreviewed edges on required paths
```

---

# 46. Failure Reason Chain

Always expose the dependency path.

Example:

```text
checkout stack
       |
       v
checkout-api
       |
       v
ECR image
       |
       X
not available in ap-south-2
```

This feature is critical.

---

---

> [↑ Spec Overview & Index](../../spec.md) · [← 02-discovery-and-graph.md](02-discovery-and-graph.md) · [04-recovery-and-optimizer.md →](04-recovery-and-optimizer.md)
