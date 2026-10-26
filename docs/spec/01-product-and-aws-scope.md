> **Perpetual Engineering Specification (Revision 4)** — Part I — Product Principles & AWS Services in Scope (§1–§8)  
> [↑ Spec Overview & Index](../../spec.md) · [02-discovery-and-graph.md →](02-discovery-and-graph.md)

---

# 1. Product Definition

Perpetual is a disaster-recovery readiness and architecture system for AWS infrastructure.

It discovers existing infrastructure from multiple sources, builds an evidence-backed dependency graph, groups infrastructure into stacks, evaluates those stacks against user-defined disaster-recovery objectives, simulates failures, designs the DR architecture that meets them, and then changes the user's own infrastructure code (Terraform and Kubernetes manifests) to implement it. Every proposed change is checked against the same engine and delivered with its verification stage and deployment prerequisites for the user to review and apply (61.1). It also generates recovery runbooks.

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
 IaC changes      Runbook
 (verified)
```

LLM agents work alongside this pipeline, never in place of it:

```text
 Rules Engine ----> Advisory review (LLM)  -> proposals: findings, edges, mechanisms
 Optimizer   <----> Candidate planner (LLM) -> proposals: candidate architectures
 DR spec     ----> IaC transformer (LLM)    -> proposals: code changes
                                               |
                       every proposal is re-checked by the deterministic
                       rules, simulator and recovery engine, or by the user
```

The governing rule:

> The LLM proposes. The deterministic engine, or the user, decides.

Concretely:

- an LLM proposal can only make a result worse (add a risk, add an edge to review) until the engine or the user confirms it. It can never make a stack READY or a mechanism RECOVERABLE on its own;
- every number shown (cost, RTO, RPO, durations, confidence) comes from the engine and its configuration;
- design verification requires engine re-assessment and re-simulation of the planned infrastructure; incomplete or failed checking produces an explicitly unverified artifact, never observed readiness (section 61.1);
- every LLM claim cites its inputs: resource IDs, evidence IDs, file and line, knowledge-base documents or skills. Uncited claims are discarded.

The LLM MUST NOT be the source of truth for:

- AWS resource existence;
- dependencies;
- cost values;
- RTO calculations;
- RPO calculations;
- IAM policy evaluation;
- Terraform syntax (checked by `terraform validate`);
- DR strategy feasibility (checked by simulation);
- whether a change meets the DR targets (checked by verification, section 61.1).

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

## 5.3 Amazon EC2 and Auto Scaling

Support:

- standalone EC2 instances;
- Auto Scaling groups (ASGs);
- launch templates (resolving the `ASG -> LaunchTemplate -> AMI -> EBS Snapshot -> KMS Key` dependency chain);
- AMIs (including cross-Region AMI copy, SSM parameter/data-source lookup in the DR Region, and backing EBS snapshot KMS decryptability in DR);
- instance profiles and IAM roles;
- attached EBS volumes and snapshot/backup coverage;
- VPC, subnets, security groups and load balancer target group attachments;
- instance families, capacity types and DR Region quota requirements.

---

## 5.4 AWS Lambda

Support:

- Lambda functions, versions and aliases;
- Lambda layers (detecting hardcoded primary-Region layer ARNs vs DR layer availability);
- deployment packages (S3 code bucket cross-Region availability/replication) and container images (ECR replication);
- VPC configuration (subnets, security groups);
- execution roles and resource-based policies;
- environment variable reference matching (persisting only matched facts per section 67);
- event-source mappings (SQS, SNS, DynamoDB) and asynchronous destinations / DLQs;
- reserved and provisioned concurrency and DR Region concurrency quotas.

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

## 7.1 Messaging: Amazon SQS and Amazon SNS

### Amazon SQS

Inspect:

- standard and FIFO queues;
- dead-letter queues (DLQs) and redrive policies;
- KMS encryption;
- queue policies;
- message retention and visibility timeout;
- event-source mappings (Lambda) and producers/consumers;
- DR posture: Perpetual MUST distinguish **queue endpoint recovery** (`RTO` — recreating the queue in DR via IaC or keeping a warm standby queue so new messages can be processed) from **in-flight message durability** (`RPO` — AWS SQS does not natively replicate queued messages across Regions, so unconsumed messages in a primary queue or DLQ are stranded during a Region outage unless backed by a durable cross-Region store or dual-write pattern).

### Amazon SNS

Inspect:

- standard and FIFO topics;
- subscriptions (SQS, Lambda, HTTPS, cross-Region endpoints);
- KMS encryption;
- topic policies and delivery status logging;
- DR posture (DR topic + subscription readiness or cross-Region delivery).

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
- AWS WAF (WAFv2 Web ACLs, rule groups, IP sets, regional ALB associations and `us-east-1` `Scope=CLOUDFRONT` associations, plus primary-vs-DR Web ACL and rule parity checks);
- Amazon CloudWatch Logs (log groups, KMS encryption, retention, subscription filters; out of RTO scope by default per section 24.1 unless marked required, assessed under Observability);
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
- ACM certificates (including `us-east-1` certificates used by CloudFront, discovered via a global/`us-east-1` collector pass alongside `Route 53`, `IAM`, `CloudFront`, and `CLOUDFRONT`-scoped WAFv2 Web ACLs).

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

---

> [↑ Spec Overview & Index](../../spec.md) · [02-discovery-and-graph.md →](02-discovery-and-graph.md)
