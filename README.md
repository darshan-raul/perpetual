<p align="center">
  <img src="assets/logo.png" alt="Perpetual logo" width="320">
</p>

<h1 align="center">Perpetual</h1>

<p align="center">
  <b>Can this stack survive losing its AWS Region, within its promised RTO, RPO and budget?</b>
</p>

<p align="center">
  <img alt="status" src="https://img.shields.io/badge/status-spec%20%2F%20pre--alpha-orange">
  <img alt="cloud" src="https://img.shields.io/badge/cloud-AWS-232F3E">
  <img alt="python" src="https://img.shields.io/badge/python-3.13%2B-3776AB">
</p>

---

Perpetual is a disaster-recovery readiness, simulation and architecture tool for AWS.

It does three things:

1. **Maps what a stack depends on.** A stack is everything one product needs: its microservices, databases, VPCs, load balancers and supporting services. Perpetual discovers infrastructure from Terraform, AWS APIs, AWS Config, Resource Explorer and, optionally, Kubernetes. It computes the dependencies from security groups, NetworkPolicies, IAM policies, CloudTrail and VPC Flow Logs, so every link is backed by evidence. You review the whole graph and add, edit or remove links where it is wrong.
2. **Simulates a Region failure.** It tells you what survives, what can be recovered and what is blocked, with the dependency path that explains each result.
3. **Plans the fix for the whole stack.** It builds one recovery plan for the stack, estimates one RTO and one RPO from it (with explicit buffer), compares DR architectures by cost, and later generates companion DR Terraform plus failover and failback runbooks.

> Perpetual does not ask whether each AWS resource has DR.
> It asks whether the **stack** can operate after failure.

## Why

Most teams find out whether their DR plan works during the outage. Four gaps cause that.

### 1. The DR plan is a document. The infrastructure keeps changing.

The plan was written once, maybe tested in a drill once a year. Meanwhile someone adds a microservice that reads a queue that only exists in the primary Region, turns off ECR replication to save money, or pins a role's policy to a primary-Region KMS key ARN. Nothing fails until the day you fail over. Between drills there is no evidence either way.

### 2. Every resource passes its own check. The stack still fails.

Resource-level checks ask whether RDS is Multi-AZ, whether backups are on, whether the bucket is versioned. A healthy cross-Region database replica still does not make the product recoverable if:

- the container image was never replicated to the DR Region;
- a secret or KMS key exists only in the primary Region;
- the DR execution role's policy still points at a primary-Region ARN;
- a StatefulSet needs an EBS StorageClass, but the DR cluster has no EBS CSI driver;
- the service quota for Fargate vCPUs in the DR Region is too low for the plan;
- Route 53 failover depends on editing records, an IAM change or a us-east-1 control plane during the outage.

And Multi-AZ is not Region DR: it protects against losing a data centre, not a Region.

### 3. Nobody has an accurate map of what depends on what.

Architecture diagrams show what was intended. The real dependencies live in security-group rules, IAM policies, environment variables, Kubernetes manifests, and in the calls and connections the services actually make. Perpetual builds the map from both: what is **permitted** (security groups, NetworkPolicies, IAM), what is **referenced** (Terraform, task definitions, ConfigMaps) and what is **observed** (CloudTrail, VPC Flow Logs). You review it and correct it, and your corrections survive the next scan.

### 4. The RTO is a promise nobody has calculated.

"30 minutes" is usually a target, not a number anyone derived. Adding up per-component restore times is wrong in both directions: independent steps run in parallel, while detection, the decision to fail over, handoffs between teams and end-to-end validation add time nobody budgets for. Perpetual builds one recovery plan for the whole stack and takes the critical path through it, with buffer shown as separate lines. It also shows what each better RTO would cost, so you don't run hot standby everywhere by default or discover too late that backups alone can't meet the target.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/how-it-works-dark.svg">
  <img alt="How Perpetual works: discover infrastructure, compute dependencies, review and edit the graph, define the stack, resolve DR paths, simulate Region failure, build one stack recovery plan, compare architectures, generate DR Terraform and runbooks." src="assets/how-it-works.svg" width="100%">
</picture>

1. **Map.** Discover resources from AWS APIs, Terraform and Kubernetes. Compute dependencies from evidence, then review and edit the graph.
2. **Assess.** Group resources into a stack (the whole product), resolve how each part is recovered in the DR Region, and simulate losing the primary Region.
3. **Plan.** Build one recovery plan for the stack with its RTO and RPO ranges, compare DR architectures by cost, and generate companion DR Terraform and failover/failback runbooks.

Core principles:

- **Deterministic core.** Rules, simulation, RTO/RPO and cost come from code and configuration. An optional LLM layer only explains results; it is never the source of truth.
- **Unknown is a real answer.** Missing evidence becomes `UNKNOWN`, never `PASS`. Perpetual never invents an RPO.
- **Everything is explainable.** Every finding and every dependency shows the evidence behind it.
- **Read-only.** Perpetual never calls `GetSecretValue`, never reads application data and never stores secret values.

## Example output

```text
Stack             checkout
Primary Region    ap-south-1
DR Region         ap-south-2

Target RTO        30m      Predicted RTO   74-110m   FAIL
Target RPO         5m      Predicted RPO   UNKNOWN   UNCERTAIN

Status            NOT DR READY
Blocking findings 3

1. checkout-api image unavailable in DR ECR.
     checkout -> checkout-api -> DR ECR repo -> image missing
2. DR ECS execution role cannot decrypt the required KMS key.
3. Database recovery path exceeds the target RTO.
```

## Scope

**AWS services in the first slice:** Route 53, ALB, ECS (Fargate), ECR, Secrets Manager, KMS, RDS, S3, VPC/subnets/security groups.

**Second slice:** EKS, node groups, AWS Load Balancer Controller, IRSA/Pod Identity, PVC/EBS with EBS CSI. This slice demonstrates a cluster that is DR-ready while the application on it is not.

**Not counted in the stack's RTO:** monitoring, logging and CI/CD. They are shown and checked, but they never block failover or add to the plan.

**Not in the MVP:** multi-cloud, automatic failover, any write access to your AWS accounts, automated DR drills, graph databases, solvers.

## Status

Perpetual is at the specification stage. There is no code yet.

The full engineering specification is in [`spec.md`](spec.md). The planned build order is:

| Phase | Delivers |
|---|---|
| 0 | Domain models, YAML fixtures, SQLite, NetworkX graph, `perpetual` CLI |
| 1 | DR overlay, two-pass simulator, recovery DAG, RTO critical path (CLI) |
| 1b | Terraform importer, FastAPI, `perpetual ui`, graph editor (React + React Flow) |
| 2 | Live AWS discovery, dependencies from security groups and IAM |
| 2b | Observed dependencies from CloudTrail and VPC Flow Logs |
| 3 | Stack and service grouping |
| 4–7 | Rule packs, RPO estimation |
| 8–10 | Optimizer, DR Terraform compiler, runbook generator |

## Planned CLI

```bash
perpetual import-terraform ./terraform-show.json
perpetual scan --profile production --region ap-south-1 --dr-region ap-south-2

perpetual graph --stack checkout --unreviewed
perpetual graph overrides apply overrides.yaml

perpetual stacks
perpetual assess checkout
perpetual simulate checkout --failure region:ap-south-1
perpetual optimize checkout --rto 30m --rpo 5m --budget 1200
```

## Tech stack (planned)

**Backend:** Python 3.13+, `uv`, Pydantic, SQLAlchemy, NetworkX, boto3, the Kubernetes Python client, FastAPI, SQLite (PostgreSQL for a later hosted version).

**Frontend:** Vite, React, TypeScript, Tailwind, shadcn/ui, React Flow, TanStack Query. Built to static files and served by the Python process.

**Runs locally.** `perpetual ui` starts one process on `localhost:8000`. No hosting, no Node.js at runtime, no database server. Your AWS data stays on your machine.

**Quality:** ruff, mypy, pytest, eslint, TypeScript strict mode.
