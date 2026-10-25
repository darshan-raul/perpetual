# Perpetual

## Cloud Disaster-Recovery Readiness, Simulation and Architecture Compiler

**Status:** Engineering specification, revision 3  
**Initial cloud:** AWS  
**Primary implementation target:** Local single-user tool first (section 71.1); a hosted version is possible later  
**Primary user:** Cloud Architect / SRE / Platform Engineer / DevOps Engineer  
**Primary objective:** Determine whether a real stack can survive a specified failure while satisfying its RTO, RPO and cost constraints.

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
- Perpetual is a local tool: one Python process serves the API and a static React UI, with SQLite by default. The UI moves from Next.js to Vite + React. PostgreSQL and Docker Compose are only for a later hosted version (18, 71, 71.1, 72, 73).

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

---

# 1. Product Definition

Perpetual is a disaster-recovery readiness and architecture system for AWS infrastructure.

It discovers existing infrastructure from multiple sources, builds an evidence-backed dependency graph, groups infrastructure into stacks, evaluates those stacks against user-defined disaster-recovery objectives, simulates failures, recommends remediation, estimates resulting recovery characteristics and cost, and eventually generates deterministic infrastructure-as-code and recovery runbooks.

The central question Perpetual answers is:

> If this stack loses its current AWS Region, can it continue operating within its promised RTO, RPO and budget?

Perpetual MUST evaluate complete stacks rather than checking individual AWS resources independently.

A stack is everything one product needs to serve its users. For example, an online store stack might contain:

```text
services       checkout-api, catalog-api, payments-api (ECS or EKS)
data stores    orders RDS database, sessions DynamoDB table, assets S3 bucket
networking     two VPCs, subnets, security groups, NAT, a Transit Gateway attachment
traffic        Route 53 records, one ALB, CloudFront
supporting     ECR repositories, Secrets Manager secrets, KMS keys, IAM roles
```

The DR plan, RTO and RPO are always calculated for the whole stack (sections 47 and 50).

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
Resource readiness != Stack readiness
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

> Continuous survivability verification for cloud stacks.

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
- Service Quotas (DR Region quotas for the services a stack uses);
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

 Terraform      AWS APIs      Resource Explorer      AWS Config
     |              |                |                    |
     +--------------+-------+--------+--------------------+
                            |
     CloudTrail      VPC Flow Logs      optional Kubernetes
         |                 |                    |
         +-----------------+--------------------+
                            |
                            v
                     Normalized Model
```

Sources play two roles:

```text
inventory    what exists          Terraform, AWS APIs, Resource Explorer, AWS Config, Kubernetes
dependency   what depends on what security groups, NetworkPolicies, IAM policies, references,
                                  CloudTrail, VPC Flow Logs (section 14.1)
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

# 14.1 Dependency Discovery Sources

Perpetual computes the graph's edges itself. It does not rely on the user to draw them. The user reviews and corrects the result (section 23).

Every piece of dependency evidence has a basis:

```text
permitted    configuration allows the connection or call
             (security groups, NetworkPolicies, IAM policies)
referenced   configuration names the dependency
             (Terraform references, secret ARNs in task definitions, endpoint matches in
             env vars and ConfigMaps, Kubernetes object references)
observed     the connection or call was seen
             (CloudTrail, VPC Flow Logs)
asserted     the user said so (section 23)
```

Permitted evidence says a dependency is possible. Observed evidence says it is used. Both matter, and the UI shows them separately.

### Security groups

- An SG rule that references another SG creates candidate edges between the resources attached to the two groups (ECS task ENIs, EKS nodes or pods with security groups for pods, RDS, ALB, VPC endpoints).
- CIDR rules resolve to subnets and the resources in them.
- A rule open to `0.0.0.0/0`, or to a whole VPC CIDR, does not create an edge on its own. It can only support an edge that other evidence proposes.
- The port types the edge: 3306 or 5432 to RDS is `connects_to` a database, 443 to a VPC endpoint is an AWS API path.

### Kubernetes NetworkPolicies

Requires Kubernetes access (section 14, Level 2).

- `podSelector` and `namespaceSelector` rules create candidate edges between Kubernetes workloads, resolved through Services.
- `ipBlock` egress rules are matched against AWS resource addresses (RDS ENIs, VPC endpoints, ElastiCache nodes).
- A namespace with no NetworkPolicy allows all traffic. That proves nothing and creates no edges.
- Policies only apply if the CNI enforces them (VPC CNI network policy agent, Calico, Cilium). If enforcement is not detected, NetworkPolicy evidence has reduced confidence.

### IAM policies

- Allow statements in task roles, IRSA and Pod Identity roles and instance profiles create candidate edges to the named resource ARNs (`reads_from`, `writes_to`, `uses_secret`, `encrypted_by`).
- Resource-based policies (bucket, key, secret and queue policies) that name a principal create the same edges from the other side.
- `Resource: "*"` or service-wide wildcards create no edge on their own.
- This is evidence, not authorization. Perpetual does not need full policy evaluation here (SCPs, permission boundaries).

### CloudTrail

- Each relevant event gives a principal (an assumed-role session) and a resource (from `resources` or `requestParameters`).
- The principal is mapped back to compute through its role: ECS task role, IRSA role, Pod Identity association, instance profile. The edge runs from that compute to the resource.
- Perpetual reads an existing trail from its S3 bucket, from CloudTrail Lake, or from an Athena table over the trail. The `LookupEvents` API is a fallback only: it covers management events for 90 days at a low rate limit.
- Management events are always recorded. S3 object-level and DynamoDB item-level calls are data events, which are off by default and billed. Perpetual MUST NOT enable trails or data events (section 65). It reports which coverage existed, so a missing S3 edge is explained by missing data events rather than read as "no dependency".
- The lookback window is configurable, default 30 days.
- CloudTrail only records AWS API calls. Database, cache and service-to-service connections never appear in it. VPC Flow Logs cover those.

### VPC Flow Logs

- Each accepted flow gives a source and destination address, destination port and protocol.
- Addresses resolve to resources through their ENI (`interface-id`): ECS task ENIs, RDS ENIs, ALB ENIs, NAT gateways, VPC endpoints, EKS pod IPs.
- Fargate tasks and pods are short-lived, so their ENIs and IPs are reused. Resolution uses the ENI as it was at the flow's timestamp: current ENIs first, then AWS Config or CloudTrail ENI history. Flows that cannot be resolved are dropped and counted, never guessed.
- Version 5 fields (`pkt-srcaddr`, `pkt-dstaddr`, `flow-direction`) are used when present, to see through NAT gateways and load balancers.
- Return traffic on ephemeral ports is folded into the originating flow.
- Flows to addresses outside the scanned accounts are proposed as external nodes (section 15.2). The user confirms them; they are not created automatically.
- Perpetual reads existing flow logs from S3 or CloudWatch Logs. It does not create flow logs.

### Persistence of observations

CloudTrail and flow-log data contain addresses, principals and request details. Perpetual persists only aggregates:

```text
from_resource_id, to_resource_id, action or port, count, first_seen, last_seen, source window
```

Raw events, request bodies and unresolved addresses are not persisted.

### Contradictions

```text
permitted + observed       strong edge
permitted, never observed  edge kept, flagged "unobserved in window" for review.
                           Rarely used paths (DR-only, monthly jobs) look like this.
observed, not permitted    flagged as a contradiction: stale configuration,
                           a missed policy source, or wrong resolution
```

Absence of observations never removes an edge on its own.

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

Stacks depend on things Perpetual cannot discover: third-party SaaS, on-premise systems, other clouds.

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
        "cloudtrail",
        "vpc_flow_logs",
        "inference",
        "user_confirmation",
        "metric",
    ]

    basis: Literal[
        "permitted",
        "referenced",
        "observed",
        "asserted",
    ] | None
    # Required for dependency evidence (section 14.1).

    source: str

    resource_id: str | None

    attribute: str | None

    value_summary: str | None

    confidence: float

    collected_at: datetime

    observed_from: datetime | None
    observed_to: datetime | None
    observation_count: int | None
    # Set for observed evidence: the window and the aggregated count.
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
SQLite (default, local)
PostgreSQL (hosted, later)
```

Do NOT deploy Neo4j/Memgraph initially.

Persist nodes and edges relationally, then construct NetworkX graphs as necessary.

Possible future replacement with graph database is allowed.

NetworkX is kept deliberately, not as heavy machinery. It provides tested implementations of the operations Perpetual needs:

```text
descendants             stack dependency closure
ancestors               impacted dependents
shortest_path           failure reason chains (section 46)
dag_longest_path_length RTO critical path (section 50)
find_cycle              cycle detection
```

Do not hand-roll recursive traversal.

The dependency graph is NOT a tree and NOT a fixed number of layers:

- shared nodes are normal (one KMS key, VPC or hosted zone used by many stacks);
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

    origin: Literal[
        "discovered",
        "user",
    ]

    review_state: Literal[
        "unreviewed",
        "confirmed",
        "edited",
        "rejected",
    ]

    criticality: Literal[
        "required",
        "likely_required",
        "optional",
        "unknown",
    ]
```

The edge's bases (permitted, referenced, observed, asserted) are derived from its evidence and not stored separately.

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

NetworkPolicy allow + Service match 0.70

Endpoint string match              0.85

CloudTrail call, mapped principal  0.95

Flow-log flow, both ends resolved  0.90

Name-only heuristic                0.40

SG rule open to 0.0.0.0/0 or a     0.00  (supports other evidence only)
whole VPC CIDR

IAM statement with Resource "*"    0.00  (supports other evidence only)
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

Initial groups: Terraform; AWS resource relationships; network permissions (security groups, NetworkPolicies); IAM permissions; configuration references; CloudTrail; flow logs. Observed sources are independent of configuration sources, so an edge that is both permitted and observed gains confidence.

The combination function MUST be pluggable, so it can be tuned later against confirmed and rejected edges.

Weights should be configuration, not hard-coded throughout the application.

---

# 23. User Review and Editing of the Graph

Perpetual computes the graph (section 14.1). The user reviews it and corrects it. Discovered data is never edited in place. User changes are stored as overrides and applied on top of every scan.

The UI and CLI must support:

```text
Confirm edge          mark a discovered edge as correct
Reject edge           remove a discovered edge (this is "delete" for discovered edges)
Add edge              from, to, relationship_type, criticality, optional note
Edit edge             change relationship_type or criticality
Delete edge           remove a user-added edge
Add node              an external node (section 15.2), or a placeholder for an AWS
                      resource Perpetual could not discover
Edit node             stack and service membership, RTO scope (section 24.1)
```

```python
class GraphOverride(BaseModel):
    id: str
    project_id: str

    kind: Literal[
        "confirm_edge",
        "reject_edge",
        "add_edge",
        "edit_edge",
        "add_node",
        "edit_node",
    ]

    target: str
    # Edge fingerprint, edge endpoints, or resource ID.

    payload: dict[str, Any]
    # Validated per kind.

    reason: str | None
    author: str
    created_at: datetime

    status: Literal["active", "orphaned"]
```

Rules on rescan:

- a user-added edge stays until the user deletes it. If a scan later discovers the same edge, the two merge: the edge becomes `discovered` with the user's evidence attached;
- an edit to a discovered edge stays applied while the edge exists;
- if an override's target resource disappears, the override becomes `orphaned` and is shown to the user. It is never dropped silently;
- a user-added edge has `confidence = 1.0` and evidence with `source_type = user_confirmation`, `basis = asserted`.

Review state feeds results:

- the user can always assess and simulate, including on an unreviewed graph;
- simulation and RTO results report how many edges on required paths are `unreviewed`, and confidence is lowered when a result depends on unreviewed edges below the confidence threshold;
- the stack cannot be shown as `READY` (DR READY) while any required-path edge below the confidence threshold is `unreviewed`. It is shown as `UNKNOWN` with the reason `graph_not_reviewed`, and the UI links to those edges in the review queue;
- negative results are not held back. `BLOCKED`, `UNAVAILABLE` and `NOT_READY` are shown as computed, because a wrong edge is more likely to hide a problem than to invent one.

Overrides can be exported to and applied from YAML, so they work in the CLI-only phases and can be kept in git (section 79).

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

# 24. Stacks

A stack is the primary unit of assessment. It is everything one product needs to serve its users (section 1): its services, data stores, networking, traffic entry points and supporting services.

```python
class Stack(BaseModel):
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

    service_ids: list[str]

    primary_region: str

    discovery_confidence: float


class StackService(BaseModel):
    id: str
    stack_id: str

    name: str
    # e.g. "checkout-api"

    resource_ids: list[str]
    # Compute plus the resources only this service uses
    # (its queue, its task role, its ECR repository).
```

Services exist for display, explanation and drill-down. They have no DR targets, recovery plans, RTO or RPO of their own. Resources shared by several services, such as the VPC, ALB or a shared database, belong to the stack directly.

The DR target Region and account are defined only on `RecoveryRequirement` (section 26), never on the stack. A stack may have several requirements, for example one for `az` and one for `region` failure.

Resources may belong to several stacks. Shared foundations (VPC, KMS keys, hosted zones, NAT) are normal. Membership is many-to-many through `stack_resources`.

---

# 24.1 RTO Scope

Not every resource in a stack is on its recovery path. Each stack resource has an RTO scope:

```text
in_scope       needed for the product to serve users after failover
out_of_scope   monitoring, logging and CI/CD
```

Out of scope by default:

- monitoring: CloudWatch alarms and dashboards, Managed Prometheus, Managed Grafana, X-Ray;
- logging: CloudWatch log groups, log-shipping pipelines, log buckets, OpenSearch domains used for logs;
- CI/CD: CodePipeline, CodeBuild, CodeDeploy, self-hosted runners.

Out-of-scope resources:

- are shown in the graph and assessed. Their findings appear under the Observability dimension (section 30) and are never blocking;
- do not affect the stack state in simulation (section 44);
- add no actions to the recovery plan and no time to the RTO (sections 47 and 50);
- are excluded from the stack RPO (section 51).

Edges from in-scope resources to out-of-scope resources (for example, an ECS service writing to a log group) are treated as `optional` in the impact pass.

Two exceptions keep this honest:

- if the recovery plan itself uses a tool to deploy or configure the DR side, such as a pipeline or an Argo CD instance, that tool is in scope;
- if an application cannot start without its log or metrics sink, the user marks that dependency `required` and the sink in scope.

Rule packs propose the scope from resource type. The user can change it per resource (section 23).

---

# 25. Stack Discovery

Perpetual should suggest stack groupings.

Sources:

- tags;
- Terraform modules;
- ECS service/target group chains;
- EKS namespaces;
- Kubernetes labels;
- ALB relationships;
- database connectivity;
- IAM references;
- observed connectivity (CloudTrail, VPC Flow Logs);
- user confirmation.

Services inside a stack are suggested from ECS services, Kubernetes Deployments and StatefulSets, and Lambda functions, together with the resources only they use.

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

Users must be able to modify stack membership.

---

# 26. DR Requirement Model

```python
class RecoveryRequirement(BaseModel):
    stack_id: str

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

    buffer: BufferPolicy | None
    # Handoff, validation and contingency (section 49.2). None uses catalog defaults.
```

Targets exist only at stack level: one RTO target and one RPO target per stack and failure scope. There are no per-service or per-resource targets.

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

The binary stack result should be:

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
spread:    to ancestors over "requires" edges (dependent -> dependency),
           skipping replicates_to and backed_up_by
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
- The stack state is `worst()` over its required, in-scope resources, mapped as in 30.1.

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

# 47. Recovery Planning Model

There is one recovery plan per stack and failure scenario. It contains the actions for every in-scope resource of the stack: services, data stores, networking, traffic and supporting services, recovered together. Perpetual does not produce separate plans per service or per resource.

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
- values are heuristic until replaced by drill data (section 53). Drill-derived values take precedence for that stack and action;
- an action with no catalog entry gets `expected_seconds = None`, which makes the RTO UNKNOWN. Never default it to zero.

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

If Perpetual cannot confidently determine RPO:

```text
RPO = UNKNOWN
```

Never invent a number.

RPO is a range, like RTO. It uses the same `DurationEstimate` model (low, expected, high, confidence, basis). Example: replica lag sampled over a window gives low = minimum, expected = median, high = maximum.

Stack RPO is the worst (highest) RPO over the data stores that are required for the stack. If any required data store's RPO is UNKNOWN, the stack RPO is UNKNOWN.

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

RTO, RPO and cost impact are always stack-level. Perpetual applies the change, re-plans the whole stack and reports the difference. A component can get much faster while the stack barely moves, and the explanation must say why:

```text
Change:      RDS snapshot restore -> cross-Region read replica
RDS step:    60m -> 10m
Stack RTO:   95m -> 70m
Why:         ECS image pull from a non-replicated registry is now the critical path.
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
Never enable logging, trails or flow logs in customer accounts; read what exists.
Persist only aggregates of CloudTrail and flow-log data (section 14.1).
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

Reading CloudTrail and flow logs needs read access to where they are delivered: `s3:GetObject` and `s3:ListBucket` on the log buckets (plus `kms:Decrypt` if they are encrypted), `logs:FilterLogEvents` or Logs Insights queries for CloudWatch Logs destinations, or read-only Athena and CloudTrail Lake queries. These permissions are optional. Without them, Perpetual reports that observed evidence is unavailable.

The DR target may be a separate AWS account. This is a common best practice, for example a dedicated DR or backup account.

The MVP MUST support one primary account plus one DR account per stack, with separate credentials or role per account. Every resource ID already carries `account_id`, so cross-account counterparts need no model change.

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
get_stack()
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
SQLite (default) / PostgreSQL (hosted)
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

# 71.1 Deployment Model

Perpetual is a local, single-user tool. It needs no hosting.

```text
uv tool install perpetual
perpetual ui              # serves API + UI on http://localhost:8000
```

- One Python process runs FastAPI. It serves the REST API and the pre-built UI as static files. Node.js is needed only to build the UI, never to run Perpetual.
- The API binds to `127.0.0.1` by default. Binding to other interfaces requires an explicit flag and a warning, because there is no login in local mode.
- Data lives in one SQLite file in the user's data directory (for example `~/.local/share/perpetual/perpetual.db`). Users can override the path per project.
- AWS access uses the user's own credential chain (section 66). Discovery data, CloudTrail and flow-log aggregates and Terraform state never leave the machine, except for what the user chooses to send to an optional LLM (section 69).
- The CLI and the UI use the same engine and the same database file.

Keeping a hosted version possible:

- the schema stays PostgreSQL-compatible: no SQLite-only features, and Alembic migrations are tested on both;
- every row is scoped by `project_id`, so per-tenant separation can be added later;
- a hosted version would add login, a PostgreSQL database, background workers if scans need them, and the cross-account read-only role with external ID (section 66). That is not part of the MVP (section 101).

---

# 72. Frontend Technology

Recommended:

```text
Vite
React
TypeScript
shadcn/ui
Tailwind
React Flow
TanStack Query
TanStack Router (or React Router)
```

The UI is a single-page app built to static files and served by the API process (section 71.1). It needs no server-side rendering.

TypeScript API types are generated from the FastAPI OpenAPI schema into `packages/schemas`. They are not written by hand.

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
|   |       +-- stacks/
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
+-- docker-compose.yml   # hosted / Postgres testing only; not needed to run locally
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

Initial entities (SQLite by default, PostgreSQL-compatible):

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
graph_overrides
observations

stacks
stack_resources
stack_services

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
    # Whole project graph. Filters: stack, service, VPC, basis, confidence,
    # review_state, rto_scope.

POST /projects/{id}/edges
PATCH /edges/{id}
DELETE /edges/{id}
    # Rejects a discovered edge; deletes a user-added edge.

POST /projects/{id}/nodes
PATCH /resources/{id}
    # Stack and service membership, RTO scope.

GET /projects/{id}/overrides
POST /projects/{id}/overrides/import

GET /projects/{id}/stacks

POST /projects/{id}/stacks

PATCH /stacks/{id}

GET /stacks/{id}

POST /stacks/{id}/requirements

POST /stacks/{id}/assess

GET /stacks/{id}/findings

POST /stacks/{id}/simulate

GET /simulations/{id}

POST /stacks/{id}/optimize

GET /stacks/{id}/recovery-plan

POST /edges/{id}/confirm

POST /edges/{id}/reject
```

Later:

```text
POST /stacks/{id}/terraform/generate

POST /stacks/{id}/runbook/generate
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

perpetual graph
perpetual graph --stack checkout --unreviewed
perpetual graph overrides export > overrides.yaml
perpetual graph overrides apply overrides.yaml

perpetual stacks

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

Stacks                12
DR Ready               7
At Risk                3
Not Ready              2

Critical blockers      8
```

---

# 81. Stack Screen

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

# 82. Graph Editor

The graph editor is the first web UI (section 99). It is deliberately small: view the computed graph, review it, and correct it.

### View

- Shows every discovered node and every computed edge in the project, not only one stack.
- Nodes represent real resources, with service icons where practical. They are grouped by stack, service and VPC, and the groups can be collapsed.
- Filters: stack, service, VPC, resource type, evidence basis, confidence, review state, RTO scope.
- Layout is automatic (for example ELK or dagre). Saving manual node positions is optional.
- Out-of-scope resources (section 24.1) are shown muted.

Edge styles show the evidence basis:

```text
solid     observed (CloudTrail or flow logs)
dashed    permitted or referenced only
dotted    heuristic only (name match)
```

Colors are only used for simulation state (section 83).

### Review

A review queue lists unreviewed edges, ordered with edges on required paths first, then by lowest confidence. Contradictions (observed but not permitted) and "unobserved in window" edges are listed separately.

Selecting an edge shows its evidence:

```text
payments-api -> payments-db

Confidence:     94%
Basis:          permitted + referenced + observed
Last observed:  2026-10-24 (412 flows on 5432 in 30 days)

Evidence:
- security-group rule sg-api -> sg-db on 5432
- secret reference in task definition
- endpoint match in env var DB_HOST
- VPC flow logs

[ Confirm ]  [ Edit ]  [ Reject ]
```

### Edit

- add an edge by dragging from one node to another, then choosing relationship type and criticality;
- edit or delete an edge;
- add an external node or a placeholder node;
- move a node between stacks and services, and change its RTO scope.

Every edit is a `GraphOverride` (section 23) and asks for an optional reason.

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

Simulation should show stack recoverability.

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

This demonstrates Perpetual's stack-level reasoning.

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
def test_missing_ecr_image_breaks_ecs_stack():

    simulation = simulate_fixture(
        "ecs_missing_dr_image"
    )

    assert simulation.stack_status == "unavailable"

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

Buffer case (section 49.2), same refined DAG, database promotion is manual, handoff = 5, no stack validation, contingency = 10%:

```text
critical path = 5 + (5 + 30) + 3 + 2 = 45
RTO           = 45 * 1.10          = 49.5
```

Additional simulation tests:

- a BLOCKED out-of-scope resource (a log group) does not change the stack state or the RTO;
- a user-added edge survives a rescan, and a user-rejected edge is not recreated unless its evidence fingerprint changes;
- an edge that is permitted and observed has higher confidence than either alone;
- a stack whose simulation would be READY, but which has an unreviewed low-confidence edge on a required path, reports UNKNOWN with reason `graph_not_reviewed`;
- a flow log whose ENI cannot be resolved creates no edge;
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
stack_id
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
- fixture format: a normalized graph, DR overlay and graph overrides in YAML, loadable without collectors;
- SQLAlchemy persistence on SQLite (Postgres-compatible schema, no Postgres-only features yet);
- NetworkX graph builder;
- graph overrides (section 23) applied from YAML;
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
- Alembic migrations (SQLite, tested against PostgreSQL);
- `perpetual ui`: API and static UI served by one local process (section 71.1);
- graph API, including override endpoints;
- Vite + React + shadcn + React Flow graph editor (section 82): whole graph, review queue, add, edit and delete edges and nodes;
- simulation view on the reviewed graph.

Exit criterion:

```text
Import fixture -> review and correct the computed graph in the UI -> simulate on it.
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

Dependency evidence in this phase: security groups, IAM policies and configuration references.

Exit criterion:

```text
Scan AWS account -> normalized graph.
```

---

## Phase 2b — Observed Dependency Evidence

Deliver:

- CloudTrail reader (S3, CloudTrail Lake or Athena; `LookupEvents` fallback);
- VPC Flow Logs reader (S3 or CloudWatch Logs) with time-aware ENI resolution;
- principal-to-compute mapping through task roles, IRSA and Pod Identity;
- aggregated observations;
- contradiction and "unobserved in window" flags;
- coverage report (which trails, data events and flow logs existed).

Kubernetes NetworkPolicy evidence arrives with the EKS slice (section 106).

Exit criterion:

```text
Every edge shows its basis. Edges that are permitted but unobserved, and flows that
are observed but not permitted, are listed for review.
```

---

## Phase 3 — Stack Discovery

Deliver:

- heuristic stack grouping;
- manual stack editing;
- root resources;
- stack dependency closure.

Exit criterion:

```text
Perpetual understands "checkout" as a stack rather than unrelated AWS resources.
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
Stack assessment produces evidence-backed findings.
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
RDS/S3/etc recovery posture contributes to stack RPO.
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

3. Perpetual shows the whole computed graph with its evidence.
   User reviews it and adds, edits or rejects mappings.

4. Perpetual groups resources into a stack and its services.
   User adjusts membership and RTO scope.

5. User enters, for the stack:
   target Region
   RTO
   RPO
   budget

6. User clicks:
   Simulate Region Failure

7. Perpetual shows:
   stack state
   what survives
   what fails
   dependency path
   blocking findings

8. Perpetual calculates, for the whole stack:
   recovery plan
   estimated RTO with its breakdown and buffer
   estimated RPO

9. Perpetual recommends:
   a whole-stack DR plan

10. Perpetual compares:
    current architecture
    recommended architecture
    additional cost

11. Perpetual generates:
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
- enabling CloudTrail trails, data events or VPC Flow Logs in customer accounts;
- per-service or per-resource RTO and RPO targets;
- fine-grained SaaS multi-tenancy;
- billing/subscriptions;
- elaborate user management;
- hosting: login, PostgreSQL in production, background workers (section 71.1).

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
GraphOverride
Stack
StackService
RecoveryRequirement
BufferPolicy
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
graph_overrides
stacks
stack_resources
stack_services
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
review and correct the graph (YAML overrides, then the graph editor)
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
NetworkPolicies
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

> Perpetual does not ask whether each AWS resource has DR. Perpetual asks whether the stack can operate after failure.

It follows that Perpetual produces one DR plan, one RTO and one RPO per stack and failure scenario.

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
Could this stack still meet its DR promise today?
```

That is the long-term product.

---

# 109. Success Criteria

Perpetual is successful when an engineer can connect/import a representative AWS stack and receive an answer resembling:

```text
Stack
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
