# Perpetual

## Cloud Disaster-Recovery Readiness, Simulation and Architecture Compiler

**Status:** Engineering specification, revision 2  
**Initial cloud:** AWS  
**Primary implementation target:** Local development first, deployable to AWS later  
**Primary user:** Cloud Architect / SRE / Platform Engineer / DevOps Engineer  
**Primary objective:** Determine whether a real workload can survive a specified failure while satisfying its RTO, RPO and cost constraints.

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
- Findings attach to resources and can belong to several workloads (29).
- The target Region lives only on `RecoveryRequirement` (24, 26).
- Scan status includes `partial` (76).
- The optimizer generates candidates per strategy (56).
- DR may live in a separate AWS account (66).
- Implementation phases are reordered engine-first and CLI-first; the web UI comes later (99, 104).

---

# 1. Product Definition

Perpetual is a disaster-recovery readiness and architecture system for AWS infrastructure.

It discovers existing infrastructure from multiple sources, builds an evidence-backed dependency graph, groups infrastructure into workloads, evaluates those workloads against user-defined disaster-recovery objectives, simulates failures, recommends remediation, estimates resulting recovery characteristics and cost, and eventually generates deterministic infrastructure-as-code and recovery runbooks.

The central question Perpetual answers is:

> If this workload loses its current AWS Region, can it continue operating within its promised RTO, RPO and budget?

Perpetual MUST evaluate complete workloads rather than checking individual AWS resources independently.

Example:

```text
Route53
   |
   v
ALB
   |
   v
ECS / EKS
   |
   +---- ECR
   |
   +---- Secrets Manager
   |        |
   |        v
   |       KMS
   |
   +---- RDS / Aurora
   |
   +---- S3
```

An RDS replica being healthy does not mean the application is DR-ready if:

- the container image does not exist in the DR Region;
- the DR ECS service cannot start;
- EKS storage cannot be recreated;
- a KMS key is missing;
- secrets are unavailable;
- Route 53 cannot route traffic;
- networking is incomplete;
- IAM permissions differ;
- application configuration still references the primary Region.

Therefore:

```text
Resource readiness != Workload readiness
```

---

# 2. Product Principle

The system MUST NOT be implemented as:

```text
AWS JSON -> LLM -> DR recommendation
```

The required architecture is:

```text
AWS + Terraform + optional Kubernetes
              |
              v
         Discovery
              |
              v
        Normalization
              |
              v
    Infrastructure Graph
              |
       +------+------+
       |             |
       v             v
 Rules Engine     Simulator
       |             |
       +------+------+
              |
              v
         Optimizer
              |
              v
       Recovery Plan
              |
       +------+------+
       |             |
       v             v
 Terraform        Runbook
 Compiler
```

An LLM may be used as a reasoning and explanation interface over these deterministic systems.

The LLM MUST NOT be the source of truth for:

- AWS resource existence;
- dependencies;
- cost values;
- RTO calculations;
- RPO calculations;
- IAM policy evaluation;
- Terraform syntax;
- DR strategy feasibility.

---

# 3. Product Positioning

Core positioning:

> Perpetual continuously determines whether infrastructure can survive failure within its promised RTO, RPO and budget.

Long-term positioning:

> Continuous survivability verification for cloud workloads.

Perpetual should eventually distinguish three important concepts:

```text
TARGET RTO
What the organization promises.

PREDICTED RTO
What Perpetual currently estimates from architecture.

PROVEN RTO
What an actual DR drill demonstrated.
```

Likewise:

```text
TARGET RPO

CONFIGURED RPO

OBSERVED RPO

PROVEN RPO
```

The MVP does not need automated DR drills, but its architecture MUST allow actual drill results to be incorporated later.

---

# 4. Initial Scope

AWS only.

Do NOT implement multi-cloud in the MVP.

The initial architecture must nevertheless avoid hard-coding business logic directly into generic graph models so that additional cloud providers could be added later.

---

# 5. AWS Services In Scope

Perpetual should recognize and reason about the following service families.

## 5.1 Containers

### Amazon ECS

Support:

- ECS clusters;
- ECS services;
- ECS task definitions;
- Fargate;
- EC2-backed ECS where practical;
- service desired count;
- capacity providers;
- task execution roles;
- task roles;
- container images;
- ECR dependencies;
- secrets;
- SSM Parameter Store references;
- load balancer target groups;
- ALB/NLB dependencies;
- Cloud Map where detected;
- network configuration;
- subnets;
- security groups;
- autoscaling configuration;
- container health checks;
- deployment configuration.

The engine should be able to determine whether an ECS service could start in the DR Region.

---

## 5.2 Kubernetes / Amazon EKS

EKS must remain in scope from the beginning.

Support an EKS-specific readiness model.

### Cluster layer

Inspect:

- EKS cluster existence;
- Kubernetes version;
- endpoint configuration;
- cluster IAM role;
- VPC/subnets;
- security groups;
- encryption configuration;
- logging configuration;
- access configuration where available.

### Compute layer

Inspect:

- managed node groups;
- self-managed nodes where discoverable;
- Fargate profiles;
- Karpenter resources if Kubernetes access is available;
- instance types;
- capacity type;
- desired/min/max node capacity;
- AMI families where relevant;
- special hardware requirements such as GPU.

### Add-on layer

Detect important platform dependencies including:

- VPC CNI;
- CoreDNS;
- kube-proxy;
- EBS CSI;
- EFS CSI;
- AWS Load Balancer Controller;
- EKS Pod Identity Agent;
- ExternalDNS;
- External Secrets;
- Argo CD;
- cert-manager;
- service mesh if detectable.

Not all add-ons need detailed rules in v0.1.

The framework must make adding add-on rules straightforward.

### Workload layer

If Kubernetes API access is supplied, inspect:

- namespaces;
- Deployments;
- StatefulSets;
- DaemonSets;
- Services;
- Ingresses;
- Gateway API resources;
- PVCs;
- PVs;
- StorageClasses;
- ConfigMaps;
- ServiceAccounts;
- PodDisruptionBudgets;
- node selectors;
- affinities;
- tolerations;
- topology constraints;
- image references;
- relevant environment references;
- secret references without retrieving secret contents.

### Identity

Detect:

- IRSA;
- EKS Pod Identity;
- workload IAM dependencies;
- IAM role availability;
- trust-policy differences.

### EKS DR questions

Perpetual should eventually answer:

```text
Can the DR EKS cluster exist?

Can the nodes start?

Can the system add-ons start?

Can the application manifests deploy?

Can the pods obtain their images?

Can the pods obtain their credentials?

Can persistent data be recovered?

Can ingress become available?

Can DNS send traffic to it?

Can every external dependency resolve?
```

---

# 6. Data Services In Scope

## 6.1 Amazon RDS

Support initially:

- MySQL;
- PostgreSQL;
- MariaDB where logic is shared.

Inspect:

- engine;
- engine version;
- instance class;
- storage size;
- storage type;
- IOPS;
- Multi-AZ;
- backup retention;
- latest backup;
- automated backups;
- subnet group;
- security groups;
- KMS encryption;
- parameter groups;
- option groups where relevant;
- read replicas;
- cross-Region replicas;
- restore dependencies;
- monitoring metrics where available.

Perpetual MUST distinguish:

```text
Multi-AZ resilience
```

from:

```text
Cross-Region disaster recovery
```

They are not interchangeable.

---

## 6.2 Aurora

Support:

- Aurora MySQL;
- Aurora PostgreSQL;
- Aurora Global Database where configured;
- regional clusters;
- replicas;
- replication status;
- secondary Region readiness;
- promotion path.

---

## 6.3 DynamoDB

Initial support:

- table;
- PITR status;
- backups;
- Global Tables;
- replication Regions;
- KMS;
- indexes.

Detailed optimization may come later.

---

# 7. Storage Services

## S3

Inspect:

- versioning;
- replication;
- destination Region;
- replication rule state;
- KMS dependencies;
- lifecycle configuration;
- object ownership implications;
- replication metrics if available.

---

## EBS

Inspect:

- attached volumes;
- snapshots;
- AWS Backup coverage;
- encryption;
- KMS dependencies;
- snapshot locality;
- volume size;
- restore path.

EBS is especially important for EKS PV recovery.

---

## EFS

Inspect:

- file systems;
- replication if configured;
- backup;
- mount targets;
- subnet availability;
- security groups;
- KMS;
- EKS/ECS usage.

---

# 8. Supporting Services

Initially include awareness of:

- ECR;
- Secrets Manager;
- SSM Parameter Store;
- KMS;
- IAM;
- Route 53;
- ALB;
- NLB;
- CloudFront;
- VPC;
- subnets;
- route tables;
- NAT Gateways;
- Internet Gateways;
- Transit Gateway;
- VPC endpoints;
- security groups;
- AWS Backup;
- Service Quotas (DR Region quotas for the services a workload uses);
- Route 53 Application Recovery Controller (routing controls, readiness checks) where configured;
- ACM certificates (including us-east-1 certificates used by CloudFront).

Detailed service-specific rules can be added incrementally.

## 8.1 Control Plane vs Data Plane

Some "global" services have a control plane in a single Region, typically us-east-1. Examples: Route 53 record changes, IAM changes, and the ACM certificates CloudFront uses.

Perpetual MUST distinguish:

```text
Data-plane failover    health-check-driven Route 53 failover, ARC routing controls.
                       Does not require API mutation during the event.

Control-plane failover editing records, creating roles or changing policies
                       during the event.
```

A recovery path that relies on a control-plane mutation MUST be flagged (see 28.1). It may still be valid, but it is less statically stable, and confidence is reduced.

---

# 9. Input Sources

Perpetual MUST support multiple discovery sources.

```text
                 Discovery Sources

 Terraform      AWS APIs       Resource Explorer
     |              |                 |
     +--------------+-----------------+
                    |
                 AWS Config
                    |
            optional Kubernetes
                    |
                    v
             Normalized Model
```

---

# 10. Terraform Input

Preferred ingestion method:

```bash
terraform show -json
```

Support a JSON plan/state export before attempting complex native HCL evaluation.

Possible inputs:

```text
terraform show -json terraform.tfstate

terraform show -json tfplan
```

The system SHOULD also be able to ingest a Terraform repository eventually.

Do not attempt to build a full Terraform interpreter.

Terraform data should provide:

- intended resources;
- Terraform addresses;
- references;
- modules;
- providers;
- regions;
- explicit dependencies;
- attributes;
- tags.

Record Terraform-origin evidence separately from live AWS evidence.

---

# 11. Live AWS Discovery

Implement service adapters using boto3.

Base abstraction:

```python
class ResourceCollector(Protocol):
    service: str

    def collect(
        self,
        account_id: str,
        regions: list[str],
    ) -> list[DiscoveredResource]:
        ...
```

Examples:

```text
ECSCollector
EKSCollector
RDSCollector
S3Collector
ECRCollector
EC2Collector
ELBCollector
Route53Collector
SecretsManagerCollector
KMSCollector
IAMCollector
BackupCollector
```

AWS APIs are the authoritative source for service-specific configuration.

---

# 12. Resource Explorer

Resource Explorer is an optional discovery accelerator and inventory source.

Do NOT rely exclusively on Resource Explorer.

Its primary uses are:

- discover broad inventory;
- identify resource ARNs;
- identify resource types;
- identify Regions;
- supplement service API discovery.

Resource Explorer findings must be normalized into the same resource model.

---

# 13. AWS Config

Use AWS Config configuration items and relationships where available.

AWS Config relationship data counts as evidence.

Do not assume AWS Config relationships describe application dependency or network/data flow.

Example:

```text
AWS Config says:

EC2 -> subnet
EC2 -> SG
EBS -> EC2
```

Useful.

But:

```text
ECS application -> RDS
```

must be inferred separately.

---

# 14. Optional Kubernetes Discovery

EKS assessment should work at two levels.

### Level 1: AWS-only

If Kubernetes credentials are not provided:

```text
EKS infrastructure readiness
```

can still be calculated.

Confidence must be reduced for application-level readiness.

### Level 2: Kubernetes-aware

If Kubernetes access is provided:

```text
EKS application readiness
```

can include workload manifests, storage, scheduling and platform add-ons.

Implement a Kubernetes collector abstraction.

```python
class KubernetesCollector:
    def collect_cluster_state(
        self,
        context: str,
    ) -> KubernetesSnapshot:
        ...
```

---

# 15. Normalized Resource Model

All sources MUST normalize into one generic model.

Suggested model:

```python
class ResourceNode(BaseModel):
    id: str

    provider: str
    service: str
    resource_type: str

    account_id: str | None
    region: str | None
    availability_zone: str | None

    name: str | None
    arn: str | None

    tags: dict[str, str]

    properties: dict[str, Any]

    source_refs: list[SourceReference]

    terraform_address: str | None

    discovered_at: datetime
```

Resource IDs must be stable.

Preferred canonical format:

```text
aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER
```

Example:

```text
aws://123456789012/ap-south-1/rds/db/prod-mysql
```

Global resources:

```text
aws://123456789012/global/route53/hosted-zone/Z123
```

## 15.1 Identity Resolution Across Sources

The same resource may arrive from Terraform, AWS APIs, Resource Explorer and AWS Config. These MUST merge into one `ResourceNode`.

Resolution order:

```text
1. ARN match.
2. Service-specific natural key (account + region + type + identifier).
3. Terraform address -> resource ID mapping from state attributes.
4. Unresolved: keep as a separate node with origin "terraform_planned".
```

Resources in a Terraform plan that do not exist yet have no ARN. They are represented with:

```text
aws://ACCOUNT/REGION/SERVICE/TYPE/tf:<terraform_address>
```

They are marked `planned=true` and are re-keyed when a later scan finds them live.

Conflicting attribute values from different sources are kept as separate evidence. The AWS API value is authoritative for live configuration (section 11), and the conflict is surfaced as drift between intended and live state.

## 15.2 External Dependencies

Workloads depend on things Perpetual cannot discover: third-party SaaS, on-premise systems, other clouds.

Users MUST be able to declare external nodes:

```text
provider       = "external"
service        = user-supplied (e.g. "payments-gateway")
region         = optional
dr_posture     = available | unavailable_in_region_failure | unknown
```

External nodes take part in the graph and simulation like any other node. An undeclared posture means UNKNOWN.

## 15.3 Typed Resource Properties

`properties: dict[str, Any]` is the raw store only.

Rule packs MUST read typed per-resource-type models, for example `RDSInstanceProperties` and `ECSServiceProperties`. Use a discriminated union on `resource_type`. Normalizers populate these models.

Rules MUST NOT read the untyped dict directly. Unknown or unparsed fields remain available for evidence but are not used in rule logic.

---

# 16. Source Evidence Model

Every material fact should be traceable to evidence.

```python
class Evidence(BaseModel):
    id: str

    source_type: Literal[
        "aws_api",
        "aws_config",
        "resource_explorer",
        "terraform",
        "kubernetes",
        "inference",
        "user_confirmation",
        "metric",
    ]

    source: str

    resource_id: str | None

    attribute: str | None

    value_summary: str | None

    confidence: float

    collected_at: datetime
```

Never put credentials or secret values in evidence.

---

# 17. Dependency Graph

Use a directed graph.

Direction MUST always mean:

```text
dependent -> dependency
```

Example:

```text
ECS service -> RDS database
```

means:

```text
ECS requires RDS
```

This convention must never vary.

---

# 18. Graph Implementation

MVP:

```text
NetworkX
```

Persistence:

```text
PostgreSQL
```

Do NOT deploy Neo4j/Memgraph initially.

Persist nodes and edges relationally, then construct NetworkX graphs as necessary.

Possible future replacement with graph database is allowed.

NetworkX is kept deliberately, not as heavy machinery. It provides tested implementations of the operations Perpetual needs:

```text
descendants             workload dependency closure
ancestors               impacted dependents
shortest_path           failure reason chains (section 46)
dag_longest_path_length RTO critical path (section 50)
find_cycle              cycle detection
```

Do not hand-roll recursive traversal.

The dependency graph is NOT a tree and NOT a fixed number of layers:

- shared nodes are normal (one KMS key, VPC or hosted zone used by many workloads);
- cycles occur (security groups referencing each other, service-to-service calls);
- paths are often deeper than four hops (StatefulSet -> PVC -> StorageClass -> EBS CSI add-on -> IRSA role -> KMS key).

All traversal MUST terminate on cycles. Detected cycles are reported as evidence and do not raise errors.

---

# 19. Edge Model

```python
class DependencyEdge(BaseModel):
    id: str

    from_resource_id: str
    to_resource_id: str

    relationship_type: str

    confidence: float

    confirmed: bool | None

    evidence: list[Evidence]

    inferred: bool

    criticality: Literal[
        "required",
        "likely_required",
        "optional",
        "unknown",
    ]
```

---

# 20. Relationship Types

Initial relationship vocabulary should include:

```text
contains
depends_on
connects_to
reads_from
writes_to
encrypted_by
uses_secret
uses_parameter
uses_image
routes_to
resolves_to
mounted_from
backed_up_by
replicates_to
assumes_role
scheduled_on
member_of
targets
attached_to
deployed_to
```

Do not create dozens of relationships before they are useful.

DR-specific relationships have precise meanings:

```text
replicates_to   primary -> DR copy that is continuously or periodically kept in sync
                (RDS cross-Region replica, Aurora Global secondary, S3 CRR destination,
                ECR replication destination, replicated secret, DynamoDB replica).
                The DR copy is the counterpart_resource_id of a live_counterpart
                mechanism (section 27.1).

backed_up_by    resource -> recovery point or backup vault
                (snapshot, AWS Backup recovery point, cross-Region snapshot copy).
                Used by restore_from_recovery_point mechanisms.
```

These two edges do NOT mean "requires". A primary resource does not fail because its replica fails. The impact pass (section 44) does not follow them. Only the DR overlay does.

---

# 21. Dependency Evidence

Edges can come from multiple sources.

Example:

```yaml
from: ecs:payments
to: rds:payments

relationship: depends_on

confidence: 0.94

evidence:
  - source: security_group
    observation: ECS SG can reach RDS SG on 3306

  - source: secrets_manager
    observation: ECS task references database secret

  - source: dns
    observation: non-sensitive endpoint matches RDS endpoint
```

---

# 22. Dependency Confidence

Confidence is critical.

Use deterministic evidence weights.

Initial illustrative values:

```text
Explicit Terraform reference       1.00

Explicit AWS resource relationship 0.95

Kubernetes object reference        1.00

ECS secret ARN reference           1.00

IAM resource permission            0.80

SG path + destination resource     0.75

Endpoint string match              0.85

Name-only heuristic                0.40
```

Multiple independent evidence sources should increase confidence.

Do not simply sum them.

Implement a combination function.

Example:

```python
combined = 1 - product(1 - confidence_i)
```

Cap at 1.0.

This formula assumes the evidence items are independent. They often are not. For example, an SG path and an endpoint match may both come from the same task definition.

Therefore:

- each evidence type declares a correlation group;
- within a group, take the maximum confidence;
- across groups, apply the combination function.

The combination function MUST be pluggable, so it can be tuned later against confirmed and rejected edges.

Weights should be configuration, not hard-coded throughout the application.

---

# 23. User-Confirmed Dependencies

The UI must support:

```text
Confirm dependency
Reject dependency
```

A user-confirmed edge becomes:

```text
confidence = 1.0
source_type = user_confirmation
```

A rejected inferred edge must not be recreated on every scan unless the underlying evidence materially changes.

Persist rejection state.

"Materially changes" is defined by an evidence fingerprint: a stable hash of the edge endpoints plus the sorted set of `(source_type, attribute, value_summary)` of its evidence.

A rejection is stored against a fingerprint. If a later scan produces a different fingerprint, the edge is re-proposed and linked to the earlier rejection for context.

---

# 24. Workloads

A workload is the primary unit of assessment.

```python
class Workload(BaseModel):
    id: str

    name: str

    description: str | None

    environment: str | None

    criticality: Literal[
        "critical",
        "high",
        "medium",
        "low",
    ]

    root_resource_ids: list[str]

    resource_ids: list[str]

    primary_region: str

    discovery_confidence: float
```

The DR target Region and account are defined only on `RecoveryRequirement` (section 26), never on the workload. A workload may have several requirements, for example one for `az` and one for `region` failure.

Resources may belong to several workloads. Shared foundations (VPC, KMS keys, hosted zones, NAT) are normal. Membership is many-to-many through `workload_resources`.

---

# 25. Workload Discovery

Perpetual should suggest workload groupings.

Sources:

- tags;
- Terraform modules;
- ECS service/target group chains;
- EKS namespaces;
- Kubernetes labels;
- ALB relationships;
- database connectivity;
- IAM references;
- user confirmation.

Suggested tags to recognize:

```text
Application
App
Service
Product
Environment
EnvironmentName
BusinessUnit
Owner
```

Do not assume tags are correct.

Users must be able to modify workload membership.

---

# 26. DR Requirement Model

```python
class RecoveryRequirement(BaseModel):
    workload_id: str

    failure_scope: Literal[
        "az",
        "region",
    ]

    target_rto_seconds: int

    target_rpo_seconds: int

    max_monthly_dr_cost_usd: Decimal | None

    preferred_strategy: DRStrategy | None

    target_region: str | None
    # Required when failure_scope == "region".

    target_account_id: str | None
    # None means the same account as the primary. See section 66.

    detection_and_decision_seconds: DurationEstimate | None
    # Time from failure to the decision to fail over. Always part of RTO (section 47.1).
    # None means Perpetual uses the catalog default and marks it low confidence.
```

---

# 27. DR Strategies

Define five workload-level strategy families:

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
workload strategy
        |
        v
service-specific recovery mechanism
```

Example:

```text
Warm standby workload

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

For every resource in a workload, Perpetual MUST resolve how that resource is provided in the DR target. This mapping is the DR overlay.

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
                  edit, IAM change) during the event.
QUOTA-DR-001      DR Region service quota below the capacity the recovery plan needs
                  (Fargate vCPU, EC2 On-Demand vCPU, ENIs, EIPs, LB count).
REGION-SVC-001    Service, feature or instance type used in primary is unavailable
                  in the DR Region.
```

Quota and service-availability checks use read-only APIs only (`service-quotas:List*`, `ec2:DescribeInstanceTypeOfferings`).

When reading environment variables or ConfigMaps, persist only the matched fact (e.g. "env var DB_HOST matches primary RDS endpoint"). Never persist the value (section 67).

# 29. Finding Model

```python
class Finding(BaseModel):
    id: str

    workload_ids: list[str]
    # A finding on a shared resource belongs to every workload that includes it.

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

Calculate workload readiness separately across:

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
Workload: checkout

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

### Workload state

The workload takes the worst state over its required resources, then maps to:

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

The binary workload result should be:

```text
READY
DEGRADED
NOT_READY
UNKNOWN
```

`UNKNOWN` is essential when evidence is insufficient.

Never convert missing evidence into PASS.

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
+-- Workloads
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

If a workload requires:

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
    workload_id="payments",
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
spread:    to ancestors over "requires" edges (dependent -> dependency),
           skipping replicates_to and backed_up_by
required        + confidence >= threshold   -> affected
likely_required or confidence < threshold   -> affected, possible_impact = true
optional                                    -> not affected
unknown criticality                         -> affected, possible_impact = true
```

Global and external nodes are seeded as affected only when the scenario or their declared posture says so.

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
                               state = worst(own checks, DR dependency states)
                               (ordering in 30.1)
global_service              -> SURVIVES, unless control_plane_dependent and the
                               control-plane Region is in the failed scope
                               (then UNKNOWN + CTRL-PLANE-001)
external                    -> from declared posture
```

A mechanism that resolves but whose rule pack has blocking findings, such as replica lag over the RPO or a missing DR image, is BLOCKED.

Unaffected nodes are SURVIVES.

### Combination and termination

- States combine with `worst()` using the ordering in 30.1.
- Recursion is memoised per node and cycle-safe. A node revisited on the current path is treated as UNKNOWN for that path, and the cycle is recorded as evidence.
- The workload state is `worst()` over its required resources, mapped as in 30.1.

### Explanation

For every BLOCKED or UNKNOWN workload, record the path from the workload root to the root cause.

The path crosses from the primary graph into the overlay where needed:

```text
checkout -> checkout-api -> [mechanism: live_counterpart] -> DR ECR repo -> image missing
```

---

# 45. Simulation Output

Example:

```text
Failure:
ap-south-1 unavailable

Workload:
payments

Route53              SURVIVES     (data-plane failover)
ALB                  RECOVERABLE  (rebuild_from_iac)
ECS                  BLOCKED      (DR dependency ECR BLOCKED)
RDS                  RECOVERABLE  (live_counterpart)
S3                   RECOVERABLE  (live_counterpart)
ECR                  BLOCKED      (mechanism: none)
Secrets              RECOVERABLE  (live_counterpart)
KMS                  RECOVERABLE  (live_counterpart, multi-Region key)

Application state:
UNAVAILABLE

Root blocker:
Container image is not available in DR Region.
```

---

# 46. Failure Reason Chain

Always expose the dependency path.

Example:

```text
checkout workload
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

# 47. Recovery Planning Model

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
- values are heuristic until replaced by drill data (section 53). Drill-derived values take precedence for that workload and action;
- an action with no catalog entry gets `expected_seconds = None`, which makes the RTO UNKNOWN. Never default it to zero.

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

If Perpetual cannot confidently determine RPO:

```text
RPO = UNKNOWN
```

Never invent a number.

RPO is a range, like RTO. It uses the same `DurationEstimate` model (low, expected, high, confidence, basis). Example: replica lag sampled over a window gives low = minimum, expected = median, high = maximum.

Workload RPO is the worst (highest) RPO over the data stores that are required for the workload. If any required data store's RPO is UNKNOWN, the workload RPO is UNKNOWN.

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
    workload_id: str

    started_at: datetime
    completed_at: datetime

    achieved_rto_seconds: int | None
    achieved_rpo_seconds: int | None

    status: str

    observations: list[str]
```

Do not build automated drills in initial MVP.

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

    estimated_monthly_cost: Decimal

    estimated_rto: DurationEstimate | None

    estimated_rpo: DurationEstimate | None

    prerequisites: list[str]

    conflicts: list[str]

    properties: dict[str, Any]
```

---

# 56. MVP Optimizer

Do NOT start with Z3.

Do NOT start with a complex mathematical solver.

For the first implementation:

1. For each of the five workload strategies (section 27), ask each rule pack for its mechanism under that strategy, giving one candidate per strategy.
2. Add a bounded number of variants per strategy, where a rule pack offers alternatives. Example: warm standby with an RDS replica vs warm standby with Aurora Global. Limit: configurable, default 3 per strategy.
3. Reject candidates that violate hard prerequisites.
4. Calculate cost.
5. Build the recovery DAG (section 47.1).
6. Calculate RTO/RPO.
7. Calculate risk/readiness.
8. Determine Pareto-efficient candidates.

Do NOT take the cross product of per-resource options. It grows exponentially with workload size.

Strategy-driven generation gives roughly 5–15 candidates, which is small enough to compare exhaustively. The current architecture is always included as a baseline candidate.

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

---

# 61. Terraform Compiler

The Terraform compiler MUST be deterministic.

The LLM may select or explain a remediation but must not be trusted to produce arbitrary infrastructure code.

Initial approach:

```text
Generate companion DR Terraform
```

instead of modifying the user's existing Terraform.

Example output:

```text
generated/
  dr/
    versions.tf
    providers.tf
    network.tf
    rds.tf
    ecs.tf
    ecr.tf
    secrets.tf
    route53.tf
    outputs.tf
```

---

# 62. Terraform Generation

Use templates or deterministic HCL generation.

Generated configuration should:

- be formatted with `terraform fmt`;
- pass `terraform validate` when supplied with required variables;
- contain clear generated comments;
- avoid embedding secrets;
- reference existing values through variables;
- expose assumptions.

Later versions may use HCL AST editing to patch existing Terraform.

Do not implement arbitrary AST modification in v0.1.

---

# 63. Runbook Generator

Generate both failover and failback runbooks.

Example:

```text
FAILOVER

1. Validate primary failure.
2. Freeze unsafe writes if required.
3. Promote database.
4. Validate DR database.
5. Scale application compute.
6. Validate container health.
7. Validate dependencies.
8. Switch traffic.
9. Run smoke checks.
10. Declare DR active.
```

Then:

```text
FAILBACK

1. Confirm primary Region stability.
2. Rebuild/revalidate primary.
3. Establish reverse replication.
4. Synchronize data.
5. Validate lag.
6. Quiesce writes if required.
7. Redirect traffic.
8. Confirm primary.
9. Restore normal replication direction.
10. Complete postmortem evidence.
```

The exact runbook must be generated from the recovery graph.

---

# 64. Failback Is First-Class

Every recovery mechanism should eventually declare:

```text
failover_supported
failback_supported
failback_complexity
data_resynchronization_required
```

A DR design is incomplete if Perpetual can explain failover but cannot explain how data created in DR returns to the restored primary.

---

# 65. Security Model

Perpetual handles extremely sensitive infrastructure metadata.

Security principles:

```text
Read-only by default.
Do not retrieve secret values.
Do not retrieve application data.
Do not send raw infrastructure state to LLMs unnecessarily.
Redact credentials.
Minimize persisted sensitive metadata.
```

---

# 66. AWS Access

Development can initially support standard AWS SDK credential resolution.

Examples:

```text
AWS_PROFILE
environment credentials
assumed role
IAM role when deployed
```

Commercial/SaaS design should eventually use a customer-created read-only IAM role with external ID.

Do not require write permissions for assessments.

The DR target may be a separate AWS account. This is a common best practice, for example a dedicated DR or backup account.

The MVP MUST support one primary account plus one DR account per workload, with separate credentials or role per account. Every resource ID already carries `account_id`, so cross-account counterparts need no model change.

Organization-wide multi-account orchestration remains a non-goal (section 101).

---

# 67. Secret Handling

Do NOT call:

```text
GetSecretValue
```

for dependency discovery unless a future explicit opt-in feature is designed.

Use metadata and resource references.

Similarly, do not store Kubernetes Secret values.

ECS task-definition environment variables, Lambda environment variables and Kubernetes ConfigMaps frequently contain plaintext secrets.

Collectors may read them in memory to match endpoints, ARNs and Region strings. They MUST persist only:

- the variable name;
- the matched fact (e.g. "matches RDS endpoint of aws://.../rds/db/prod-mysql", "contains Region string ap-south-1").

They MUST NOT persist the value. Unmatched values are discarded.

---

# 68. Terraform State

Terraform state may contain sensitive material.

Requirements:

- mark uploaded state as sensitive;
- minimize persistence;
- redact known sensitive fields;
- do not send raw state to an LLM;
- allow local-only analysis.

---

# 69. LLM Architecture

The application must work without an LLM.

LLM is an optional UX layer.

Tools exposed to the LLM might include:

```text
get_workload()
get_resource()
get_dependency_path()
get_findings()
simulate_region_failure()
calculate_recovery_path()
get_recovery_options()
optimize_budget()
explain_finding()
```

The LLM receives structured tool results.

---

# 70. LLM Example

User:

```text
Why can't I achieve a 15-minute RTO?
```

The LLM should call deterministic systems.

Result:

```text
Three blockers dominate your current recovery path:

1. RDS restore
   expected 35-65 minutes.

2. ECS environment provisioning
   expected 8-15 minutes.

3. Traffic recovery
   expected 3-7 minutes.

The database path alone exceeds your target.
```

The numbers MUST originate from Perpetual's recovery engine.

---

# 71. Backend Technology

Recommended:

```text
Python 3.13+
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL
NetworkX
boto3
kubernetes Python client
httpx
pytest
uv
```

Do not add Celery/Redis initially unless background jobs become necessary.

For local development, synchronous or lightweight asyncio jobs are sufficient.

---

# 72. Frontend Technology

Recommended:

```text
Next.js
TypeScript
shadcn/ui
Tailwind
React Flow
TanStack Query
```

React Flow should power dependency and recovery graphs.

Do not build a generic AWS console clone.

The interface should focus on survivability.

---

# 73. Repository Structure

Use a monorepo.

```text
perpetual/
|
+-- apps/
|   |
|   +-- api/
|   |   +-- perpetual/
|   |       +-- api/
|   |       +-- collectors/
|   |       +-- normalization/
|   |       +-- graph/
|   |       +-- workloads/
|   |       +-- rules/
|   |       +-- simulator/
|   |       +-- recovery/
|   |       +-- optimizer/
|   |       +-- costing/
|   |       +-- terraform/
|   |       +-- runbooks/
|   |       +-- llm/
|   |       +-- models/
|   |       +-- persistence/
|   |
|   +-- web/
|
+-- packages/
|   +-- schemas/
|
+-- fixtures/
|   +-- aws/
|   +-- terraform/
|   +-- kubernetes/
|
+-- examples/
|   +-- ecs-rds/
|   +-- eks-rds/
|
+-- generated/
|
+-- docs/
|
+-- docker-compose.yml
+-- Makefile
+-- README.md
```

---

# 74. Rule-Pack Structure

Suggested:

```text
rules/
  ecs/
    compute.py
    images.py
    identity.py
    network.py

  eks/
    cluster.py
    compute.py
    addons.py
    scheduling.py
    storage.py
    identity.py
    images.py

  rds/
    backups.py
    replication.py
    encryption.py
    network.py

  s3/
    replication.py

  ecr/
    replication.py

  kms/
    regional_keys.py

  network/
    vpc.py
    nat.py
    routes.py

  route53/
    failover.py
```

---

# 75. Persistence Model

Initial PostgreSQL entities:

```text
projects
cloud_accounts
scans
sources

resources
resource_versions

edges
edge_evidence
edge_feedback

workloads
workload_resources

recovery_requirements

findings
assessments

simulations
simulation_impacts

recovery_mechanisms
recovery_plans
recovery_actions

duration_catalog_versions

architecture_candidates
cost_estimates

dr_drills
```

---

# 76. Scan Model

```python
class Scan(BaseModel):
    id: UUID
    project_id: UUID

    started_at: datetime
    completed_at: datetime | None

    status: Literal[
        "pending",
        "running",
        "completed",
        "partial",   # at least one collector failed; see section 97
        "failed",
    ]

    sources: list[str]

    resource_count: int
    edge_count: int

    errors: list[str]
```

Keep previous scans.

This eventually enables drift analysis.

---

# 77. Drift

Perpetual should eventually compare:

```text
previous survivability
vs
current survivability
```

MVP architecture should support it.

Example:

```text
Yesterday

Predicted RTO:
24-30m

Today

Predicted RTO:
UNACHIEVABLE

Cause:
ECR replication disabled.
```

This is one of the strongest long-term features.

---

# 78. REST API

Initial endpoints:

```text
POST /projects

POST /projects/{id}/scans

GET /projects/{id}/resources

GET /projects/{id}/graph

GET /projects/{id}/workloads

POST /projects/{id}/workloads

PATCH /workloads/{id}

GET /workloads/{id}

POST /workloads/{id}/requirements

POST /workloads/{id}/assess

GET /workloads/{id}/findings

POST /workloads/{id}/simulate

GET /simulations/{id}

POST /workloads/{id}/optimize

GET /workloads/{id}/recovery-plan

POST /edges/{id}/confirm

POST /edges/{id}/reject
```

Later:

```text
POST /workloads/{id}/terraform/generate

POST /workloads/{id}/runbook/generate
```

---

# 79. CLI

Provide a CLI early.

Suggested:

```bash
perpetual scan

perpetual scan \
  --profile production \
  --region ap-south-1 \
  --dr-region ap-south-2

perpetual import-terraform ./terraform-show.json

perpetual workloads

perpetual assess checkout

perpetual simulate checkout \
  --failure region:ap-south-1

perpetual optimize checkout \
  --rto 30m \
  --rpo 5m \
  --budget 1200
```

CLI can initially call local Python services directly rather than requiring the API.

---

# 80. Primary UI

Home page:

```text
Perpetual

Production

Workloads             12
DR Ready               7
At Risk                3
Not Ready              2

Critical blockers      8
```

---

# 81. Workload Screen

```text
checkout

Primary          ap-south-1
DR Region        ap-south-2
Strategy         Warm standby

Target RTO       30m
Predicted RTO    42-58m    FAIL

Target RPO        5m
Predicted RPO     2-7m     UNCERTAIN

DR readiness      71%

Critical blockers 3
```

Below:

```text
[ Architecture ]
[ Findings ]
[ Simulate ]
[ Recovery ]
[ Optimize ]
[ Terraform ]
```

---

# 82. Architecture Graph

Nodes should represent actual resources.

Use service icons where practical.

Colors represent:

```text
healthy
degraded
failed
unknown
```

Edges show:

```text
dependency confidence
```

Selecting an edge shows evidence.

Example:

```text
payments-api -> payments-db

Confidence:
94%

Evidence:
- security-group connectivity
- secret reference
- endpoint match

[ Confirm ]
[ Reject ]
```

---

# 83. Fail Region UX

This should become a signature feature.

Button:

```text
Simulate Region Failure
```

Choose:

```text
ap-south-1
```

Graph transitions resources.

Example:

```text
green = SURVIVES
amber = RECOVERABLE
red   = BLOCKED / UNAVAILABLE
grey  = UNKNOWN
```

These colours map onto the canonical states in section 30.1. They are not separate states.

Result panel:

```text
Application:
UNAVAILABLE

Target RTO:
30m

Predicted RTO:
74-102m

Target RPO:
5m

Predicted RPO:
8-13m

Top blockers:
3
```

---

# 84. Explainability

No result should simply say:

```text
FAIL
```

Always explain:

```text
what failed
why it failed
what evidence was used
what depends on it
what remediation exists
how remediation changes RTO/RPO/cost
```

---

# 85. Reference Demo Environment

Create two fixture environments.

## Fixture A — ECS

```text
Route53
   |
   v
ALB
   |
   v
ECS Fargate
   |
   +---- ECR
   |
   +---- Secrets Manager
   |        |
   |        v
   |       KMS
   |
   +---- RDS
   |
   +---- S3
```

---

# 86. Fixture B — EKS

```text
Route53
   |
   v
ALB
   |
   v
AWS Load Balancer Controller
   |
   v
EKS
 |
 +-- Deployment
 |      |
 |      +-- ECR
 |      +-- Secret
 |      +-- RDS
 |
 +-- StatefulSet
        |
        v
       EBS PVC
```

Fixtures must work without AWS credentials.

Mock AWS API responses should be stored under:

```text
fixtures/aws/
```

---

# 87. Critical Demo Scenario

Create an ECS demo where:

```text
Primary:
ap-south-1

DR:
ap-south-2
```

Intentional problems:

```text
RDS has no cross-region replica.
ECR image not replicated.
Secret exists only in primary.
DR KMS dependency missing.
DR ECS desired count = 0.
Route53 failover incomplete.
```

User specifies:

```text
RTO 30m
RPO 5m
Budget $800/month
```

Perpetual should show:

```text
NOT DR READY
```

and identify blockers.

---

# 88. Remediated Demo

Provide a second fixture where:

```text
RDS cross-region replication exists.
ECR replication exists.
Secrets are available.
KMS is valid.
Networking exists.
ECS can scale.
Route53 failover exists.
```

Simulation should show workload recoverability.

---

# 89. EKS Demo Failure

Intentionally create:

```text
DR EKS cluster exists.

Application manifests exist.

RDS exists.

ECR exists.

BUT:

StatefulSet requires gp3 StorageClass.

DR cluster has no EBS CSI driver.
```

Result:

```text
EKS cluster DR readiness:
PASS

Application DR readiness:
FAIL

Reason:
Persistent storage cannot be provisioned.
```

This demonstrates Perpetual's workload-level reasoning.

---

# 90. Testing Philosophy

Every rule must be unit-testable without AWS.

Use fixtures.

Test:

```text
collector
normalizer
edge resolver
rule
simulation
recovery calculation
optimizer
```

independently.

---

# 91. Rule Test Example

```python
def test_rds_multiaz_not_equal_regional_dr():
    resource = load_fixture("rds_multiaz_no_cross_region.json")

    findings = rds_rule_pack.assess(resource, context)

    assert_has_rule(
        findings,
        "RDS-REGION-001",
    )
```

---

# 92. Graph Test Example

```python
def test_missing_ecr_image_breaks_ecs_workload():

    simulation = simulate_fixture(
        "ecs_missing_dr_image"
    )

    assert simulation.workload_status == "unavailable"

    assert simulation.root_blocker.resource_type == "ecr_image"
```

---

# 93. RTO Test

Construct recovery DAG:

```text
network       5
database     30
ecs           8
validation    3
dns           2
```

With network/database parallelism where appropriate.

Assert critical path, not total duration.

Concrete case (the decide action is excluded here for clarity):

```text
network 5 -> database 30 -> validation 3 -> dns 2
network 5 -> ecs 8       -> validation 3 -> dns 2

Refined DAG (ecs requires only network):   RTO = 5 + 30 + 3 + 2 = 40
Phase-barrier-only DAG (ecs after data):   RTO = 5 + 30 + 8 + 3 + 2 = 48
Sum of all actions:                        48
```

Tests MUST assert 40 for the refined DAG. A separate test asserts that phase-barrier defaults give 48, so the refinement behaviour stays covered.

Additional simulation tests:

- a cycle in the dependency graph terminates, and produces UNKNOWN plus cycle evidence;
- a counterpart that exists but whose DR KMS key is missing yields BLOCKED, not RECOVERABLE;
- a mechanism of kind `unknown` never yields RECOVERABLE.

---

# 94. Optimizer Test

Input:

```text
target RTO = 30m
target RPO = 5m
budget = $700
```

Given candidate architectures:

```text
A $300 RTO 90m
B $600 RTO 25m
C $900 RTO 10m
```

Expected:

```text
B
```

---

# 95. Quality Requirements

Use:

```text
ruff
mypy
pytest
```

Frontend:

```text
eslint
TypeScript strict mode
```

Every public Pydantic model must have explicit types.

Avoid dictionaries for core domain concepts where typed models are reasonable.

---

# 96. Observability

Backend should emit structured logs.

Important operations:

```text
scan started
collector completed
normalization completed
graph built
assessment completed
simulation completed
optimization completed
```

Include:

```text
project_id
scan_id
workload_id
duration
resource counts
```

OpenTelemetry can be added once basic functionality exists.

Do not let observability delay the MVP.

---

# 97. Error Handling

Collectors must fail independently.

Example:

```text
ECS scan PASS
RDS scan PASS
Route53 scan PASS
AWS Config scan ERROR
```

Overall scan:

```text
PARTIAL
```

Do not throw away successful discovery because one source failed.

Readiness confidence should reflect missing sources.

---

# 98. Unknown State

Unknown is a first-class state.

Example:

```text
Kubernetes credentials unavailable.

EKS infrastructure:
evaluated

Kubernetes workload recovery:
UNKNOWN
```

Do not mark it green.

---

# 99. Initial Implementation Phases

The order is engine-first. The DR model is what has to be correct, so it is proven from the CLI against fixtures before any web UI or server infrastructure is built.

## Phase 0 — Engine Foundation (CLI only)

Deliver:

- monorepo skeleton, `uv`, ruff, mypy, pytest;
- Pydantic domain models (section 104);
- fixture format: a normalized graph and DR overlay in YAML, loadable without collectors;
- SQLAlchemy persistence on SQLite (Postgres-compatible schema, no Postgres-only features yet);
- NetworkX graph builder;
- `perpetual` CLI that runs on fixtures.

Exit criterion:

```text
perpetual graph --fixture ecs-broken   prints the dependency graph and DR overlay.
```

---

## Phase 1 — Simulation and Recovery Core (CLI only)

Deliver:

- recovery-mechanism resolution for the first-slice services (section 105);
- two-pass simulator (section 44);
- canonical states (section 30.1);
- reason chains;
- recovery DAG from the phase template plus refinement (section 47.1);
- duration catalog (section 49.1);
- RTO critical path.

Exit criterion:

```text
perpetual simulate checkout --fixture ecs-broken --failure region:ap-south-1
reproduces section 87 (NOT DR READY + blockers + RTO range), and the
remediated fixture (section 88) shows RECOVERABLE.
```

---

## Phase 1b — Importers, API and UI

Deliver:

- Terraform JSON importer;
- identity resolution (section 15.1);
- mock AWS importer;
- FastAPI;
- PostgreSQL + Alembic;
- Docker Compose;
- graph API;
- Next.js + shadcn + React Flow graph UI;
- dependency confirmation/rejection.

Exit criterion:

```text
Import fixture -> view meaningful dependency graph and simulation in the UI.
```

---

## Phase 2 — AWS Discovery

Implement:

```text
ECS
EKS
RDS/Aurora
ECR
ELB
Route53
S3
Secrets Manager
KMS
EC2/VPC
```

Add Resource Explorer and Config as supplementary sources.

Exit criterion:

```text
Scan AWS account -> normalized graph.
```

---

## Phase 3 — Workload Discovery

Deliver:

- heuristic workload grouping;
- manual workload editing;
- root resources;
- workload dependency closure.

Exit criterion:

```text
Perpetual understands "checkout" as a workload rather than unrelated AWS resources.
```

---

## Phase 4 — DR Rule Engine

First rule packs:

```text
ECS
EKS
RDS
ECR
S3
Secrets
KMS
network
Route53
```

Exit criterion:

```text
Workload assessment produces evidence-backed findings.
```

---

## Phase 5 — Region Failure Simulator

Deliver:

```text
FAIL ap-south-1
```

Graph propagation.

Root-cause paths.

Exit criterion:

```text
Perpetual identifies which application dependencies survive and why.
```

---

## Phase 6 — Recovery DAG

Generate recovery actions.

Estimate duration ranges.

Calculate critical recovery path.

Exit criterion:

```text
Predicted RTO becomes architecture-derived.
```

---

## Phase 7 — RPO

Implement resource-specific RPO estimates.

Exit criterion:

```text
RDS/S3/etc recovery posture contributes to workload RPO.
```

---

## Phase 8 — Optimizer

Deliver:

```text
"What architecture satisfies RTO/RPO under budget?"
```

and:

```text
"What is the best DR posture for this budget?"
```

Exit criterion:

```text
Several architecture candidates can be compared.
```

---

## Phase 9 — Terraform Compiler

Generate companion DR Terraform.

Exit criterion:

```bash
terraform fmt
terraform validate
```

passes against generated fixture configuration.

---

## Phase 10 — Runbook Generator

Generate failover and failback runbooks from recovery plans.

---

# 100. MVP Definition

The first genuinely usable release is achieved when this workflow works:

```text
1. Import Terraform and/or scan AWS.

2. Perpetual discovers:
   ECS or EKS
   database
   storage
   networking
   secrets
   KMS
   images
   DNS

3. Perpetual groups resources into a workload.

4. User enters:
   target Region
   RTO
   RPO
   budget

5. User clicks:
   Simulate Region Failure

6. Perpetual shows:
   what survives
   what fails
   dependency path
   blocking findings

7. Perpetual calculates:
   predicted recovery path
   estimated RTO
   estimated RPO

8. Perpetual recommends:
   DR remediation

9. Perpetual compares:
   current architecture
   recommended architecture
   additional cost

10. Perpetual generates:
    Terraform companion configuration
    failover runbook
    failback runbook
```

---

# 101. Explicit Non-Goals for MVP

Do NOT initially build:

- multi-cloud DR;
- automatic failover;
- production infrastructure mutation;
- write access to customer AWS accounts;
- automatic database promotion;
- automated DNS switching;
- automated DR drills;
- logical-corruption and AZ-failure simulation (the `FailureScenario` type must allow them; section 43);
- Kubernetes scheduler replacement;
- full Terraform language interpreter;
- arbitrary Terraform source-code mutation;
- Neo4j;
- Z3;
- dozens of AWS services;
- organization-wide multi-account orchestration;
- fine-grained SaaS multi-tenancy;
- billing/subscriptions;
- elaborate user management.

Focus on correctness of the DR model.

---

# 102. Engineering Constraints

Implementers, human or AI coding agents, MUST follow these rules during implementation.

### Rule 1

Do not allow UI-specific structures to leak into core domain models.

### Rule 2

Collectors collect.

They do not calculate DR readiness.

### Rule 3

Normalizers normalize.

They do not contain UI logic.

### Rule 4

Rule packs assess resources.

They do not call LLMs.

### Rule 5

Simulator consumes graph state.

It does not rediscover AWS.

### Rule 6

Optimizer consumes recovery options.

It does not generate arbitrary cloud architecture itself.

### Rule 7

Terraform generation is deterministic.

### Rule 8

Missing information becomes UNKNOWN, not PASS.

### Rule 9

Every important conclusion must be explainable through evidence.

### Rule 10

Every important graph dependency must expose why it exists.

---

# 103. Definition of Done for Each Feature

A feature is not complete until it has:

```text
typed domain model
implementation
unit tests
fixture
API exposure where applicable
basic UI exposure where applicable
error handling
README/docs update
```

---

# 104. First Implementation Task

Start only with foundation and graph modelling (Phase 0).

Do NOT immediately implement every AWS collector, the API or the UI.

Create:

```text
ResourceNode (+ typed properties for first-slice resource types)
DependencyEdge
Evidence
Workload
RecoveryRequirement
RecoveryMechanism
FailureScenario / RegionFailure
Finding
Assessment
Simulation
RecoveryAction
RecoveryPlan
RecoveryOption
DurationEstimate
CostEstimate
```

Persist (SQLite via SQLAlchemy):

```text
resources
edges
evidence
workloads
workload_resources
recovery_mechanisms
```

Implement:

```text
YAML fixture loader (graph + DR overlay)
NetworkX graph builder
perpetual graph CLI command
```

Then create the canonical ECS fixtures: broken (section 87) and remediated (section 88).

---

# 105. First Vertical Slice

The first complete vertical slice should use only:

```text
Route53
ALB
ECS
ECR
Secrets Manager
KMS
RDS
S3
VPC/Subnets/SG
```

Implement this fully before broadening service support.

The vertical slice must support:

```text
discover
graph
assess
simulate Region failure
show blockers
calculate basic recovery path
```

Only after this works should the equivalent EKS vertical slice be completed.

---

# 106. Second Vertical Slice — EKS

Reuse the same architecture.

Add:

```text
EKS
node groups
AWS Load Balancer Controller
ECR
ServiceAccounts
IRSA/Pod Identity
RDS
PVC/EBS
EBS CSI
Route53
```

Demonstrate:

```text
cluster DR ready
```

while:

```text
application DR not ready
```

because of a storage or identity dependency.

This distinction is a mandatory capability.

---

# 107. Product Invariant

The following statement should remain true throughout development:

> Perpetual does not ask whether each AWS resource has DR. Perpetual asks whether the workload can operate after failure.

That is the architectural boundary around the entire product.

---

# 108. Long-Term Direction

After the MVP, Perpetual can evolve toward:

```text
Discover
   |
   v
Model
   |
   v
Assess
   |
   v
Simulate
   |
   v
Optimize
   |
   v
Generate
   |
   v
Drill
   |
   v
Prove
   |
   +----------------+
                    |
                    v
               continuously
```

Eventually Perpetual should continuously detect architectural drift and answer:

```text
Could this workload still meet its DR promise today?
```

That is the long-term product.

---

# 109. Success Criteria

Perpetual is successful when an engineer can connect/import a representative AWS workload and receive an answer resembling:

```text
Workload
checkout

Primary Region
ap-south-1

DR Region
ap-south-2

Strategy
Warm Standby

Target RTO
30 minutes

Predicted RTO
21-29 minutes

Target RPO
5 minutes

Predicted RPO
1-3 minutes

Status
DR READY

Confidence
HIGH
```

or:

```text
Status
NOT DR READY

Blocking findings
4

1. checkout-api image unavailable in DR ECR.

2. orders StatefulSet cannot recover its EBS volume.

3. DR ECS execution role cannot decrypt required KMS key.

4. Database recovery path exceeds target RTO.

Current predicted RTO
74-110 minutes

Recommended architecture
Warm standby

Estimated new RTO
22-31 minutes

Estimated additional cost
$XXX/month
```

Every statement must be traceable to:

```text
discovered state
+
evidence
+
deterministic rule
+
recovery calculation
```

rather than LLM speculation.

That is Perpetual.
