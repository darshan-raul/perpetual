> **Perpetual Engineering Specification (Revision 4)** — Part II — Discovery, Evidence & Dependency Graph (§9–§26)  
> [↑ Spec Overview & Index](../../spec.md) · [← 01-product-and-aws-scope.md](01-product-and-aws-scope.md) · [03-rules-and-simulator.md →](03-rules-and-simulator.md)

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
EC2Collector
LambdaCollector
RDSCollector
S3Collector
SQSCollector
SNSCollector
ECRCollector
ELBCollector
Route53Collector
WAFCollector
SecretsManagerCollector
KMSCollector
IAMCollector
CloudWatchLogsCollector
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
- The principal is mapped back to compute through its role: ECS task role, Lambda execution role, IRSA role, Pod Identity association, EC2 instance profile (rolled up to its Auto Scaling group when applicable). The edge runs from that compute to the resource.
- A shared role identifies a set of possible callers, not every caller. Attribute an observation to one resource only when event/session and time-bounded inventory evidence uniquely identify it; otherwise use the ambiguity contract below.
- Perpetual reads an existing trail from its S3 bucket, from CloudTrail Lake, or from an Athena table over the trail. The `LookupEvents` API is a fallback only: it covers management events for 90 days at a low rate limit.
- Management events are always recorded. S3 object-level and DynamoDB item-level calls are data events, which are off by default and billed. Perpetual MUST NOT enable trails or data events (section 65). It reports which coverage existed, so a missing S3 edge is explained by missing data events rather than read as "no dependency".
- The lookback window is configurable, default 30 days.
- CloudTrail only records AWS API calls. Database, cache and service-to-service connections never appear in it. VPC Flow Logs cover those.

### VPC Flow Logs

- Each accepted flow gives a source and destination address, destination port and protocol.
- Addresses resolve to resources through their ENI (`interface-id`): ECS task ENIs, EC2/Auto Scaling instance ENIs, Lambda VPC Hyperplane ENIs (mapped to the Lambda functions sharing that VPC subnet and security group), RDS ENIs, ALB ENIs, NAT gateways, VPC endpoints, EKS pod IPs.
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

### Ambiguous attribution

Persist resolved observations with `attribution = exact | ambiguous`, sorted `candidate_from_resource_ids` / `candidate_to_resource_ids`, the resolution evidence IDs, and the observation window. An exact observation has one proven resource at each end. Shared roles, Lambda Hyperplane ENIs and uncertain historical ENI ownership remain ambiguous unless independent evidence disambiguates them. Current ownership alone does not establish ownership at a historical timestamp.

An ambiguous observation is stored once against its candidate sets; do not multiply its count or copy high-confidence observed evidence to every possible edge. The UI shows a group-level observation and candidate edges for review. Ambiguity is distinct from an ANY dependency group (19.1): it is uncertainty about who called, not proof of redundant operation. Unresolved observations with no defensible candidate set are dropped and counted as specified above.

Ambiguous evidence contributes no exact-edge confidence uplift. A candidate edge supported only by ambiguous attribution cannot bypass review, regardless of the numeric threshold. If a result depends on unresolved attribution, readiness is UNKNOWN with reason `observation_attribution_unresolved`. Independent exact evidence or explicit user confirmation may resolve it; the original ambiguity and confirmation remain auditable. Test shared task roles, shared Lambda ENIs, historical ownership changes, and a uniquely attributable call.

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
3. Root/workspace-qualified Terraform address -> resource ID mapping from state attributes.
4. Unresolved: keep as a separate node with origin "terraform_planned".
```

Resources in a Terraform plan that do not exist yet have no ARN. They are represented with:

```text
aws://ACCOUNT/REGION/SERVICE/TYPE/tf:<root_id>:<workspace>:<terraform_address>
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

## 15.4 Planned Snapshot Semantics

Live and proposed infrastructure are separate immutable snapshots. AWS API precedence in 15.1 applies within a live snapshot only. A planned snapshot records its base evaluation ID, source-plan hash, root/workspace/provider/account/Region mapping and an explicit managed-resource boundary; it never mutates the live graph.

Import `terraform plan -out=<file>` followed by `terraform show -json <file>`. `terraform plan -json` is a UI event stream, not the plan representation. Validate the format version and consume `resource_changes`, planned values, unknown/sensitive masks and configuration references together:

- Create: add a planned resource with a root/workspace-qualified Terraform identity, including when its ARN is unknown. Resolve symbolic references without inventing ARNs or endpoints.
- Update: replace the managed resource's configuration with its planned after-values. Recompute its configuration-derived edges and mechanisms; do not let old AWS values or old observations prove the new configuration works.
- Delete: remove the resource from the planned final state, invalidate incident edges and overrides targeting the removed identity, and surface any resulting unsatisfied dependency. Never interpret mere absence from an incomplete import as deletion.
- Replace: retain an explicit old-to-new mapping and replacement actions; evaluate the new instance and invalidate the old instance's operational evidence. Report destroy-before-create and destructive changes even if the final DR design works.
- No-op: retain live operational evidence only when the relevant configuration fingerprint matches and coverage is fresh. Moved addresses preserve identity only through an explicit plan mapping.
- Unknown after-values remain typed unknowns, distinct from null, absent and known-empty. Never fill them with a previous live value. Unresolved provider/account/Region mappings make affected results UNKNOWN.

Preserve unmanaged live resources as context, with their coverage and freshness. Rebuild derived edges from the resulting facts, retaining per-source provenance; historical facts may be displayed but cannot satisfy checks for changed resources. Reapply overrides with identity/fingerprint checks and require review when their asserted facts no longer match. Planned-to-live re-keying uses the explicit mapping and does not silently transfer approval or operational proof.

Rendered Kubernetes changes follow the same replacement rules within an explicitly declared deployment inventory. Objects outside that inventory remain untouched; incomplete rendering cannot prove deletion. Pin cluster identity as well as kind/namespace/name. Multiple Terraform roots have independent state lineage/serial and namespaces; conflicting ownership fails verification.

Regression fixtures must cover updates overriding live facts, deletes, replacements, moved addresses, unknown IDs/values, stale edges/confirmations, incomplete imports and two roots with the same resource address.

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
        "llm_inference",
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

## 19.1 Dependency Groups and Redundancy

An ungrouped required edge is an ALL requirement. A typed `DependencyGroup` adds `id`, `dependent_resource_id`, `member_edge_ids`, `mode = all | any | quorum`, `minimum_healthy` (quorum only), `scope = primary | dr`, and evidence/review state. All members have the same dependent and scope; quorum is between 1 and the number of distinct members. An edge belongs to at most one group. Separate groups are jointly required. Optional edges do not become required merely through graph closure. Structural relationships (`contains`, `member_of`) and replication/backup edges are not operational requirements.

ALL requires every member; ANY requires one; quorum requires `minimum_healthy`. The group declares that any qualifying subset provides the needed function and capacity. Rules or user confirmation must establish that equivalence, including routing, capacity and shared dependencies; a list of endpoints alone does not prove redundancy. Without this evidence, group usability is UNKNOWN.

For a group requiring k members, let S be proven usable members and U be unknown members. The group is usable if S >= k, UNKNOWN if S < k <= S + U, otherwise BLOCKED. It SURVIVES only if k members survive without recovery; otherwise a usable group is RECOVERABLE. For impact, losing fewer than the group's tolerated members does not definitely impact the dependent; uncertain losses produce `possible_impact` when they could cross the threshold. The same semantics apply in the primary graph and DR overlay; legacy `dr_dependency_ids` denotes an ALL group.

Recovery planning records a consistent selected member set for every alternative group. Only those paths contribute required actions, RPO, cost of recovery operations and review gates; standby ownership costs still count under 59.1. All mandatory stack roots and their selected dependencies must be covered. Unselected alternative failures remain visible as reduced redundancy, not stack unavailability. No resource is counted twice and common dependencies remain required. Select the feasible set with the lowest known expected stack RTO, breaking ties by stable IDs, within a configurable search cap (default 32 combinations). If the cap prevents a complete comparison, label selection non-optimal; a fully checked feasible set remains usable, but failure to find one is UNKNOWN, not proof of impossibility. An unresolved selected branch cannot be recommended as feasible.

Persist individual typed edges using a multigraph; traversal may use a derived dependency projection, but must not collapse parallel edge evidence or evaluate ANY/quorum as ALL. Test one-of-two success, both failed, two-of-three, unknown members, shared failed prerequisites, review gates on selected paths and invalid group definitions.

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
    id: str
    revision: int
    stack_id: str

    failure_scope: Literal[
        "az",
        "region",
    ]

    target_rto_seconds: int

    target_rpo_seconds: int

    max_monthly_dr_cost_usd: Decimal | None
    # Total steady-state DR cost as defined in 59.1; None disables only the budget gate.

    workload_profile_id: str | None
    # Versioned inputs to usage-based cost estimates (59.1).

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

---

> [↑ Spec Overview & Index](../../spec.md) · [← 01-product-and-aws-scope.md](01-product-and-aws-scope.md) · [03-rules-and-simulator.md →](03-rules-and-simulator.md)
