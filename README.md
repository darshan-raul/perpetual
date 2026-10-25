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

A healthy RDS replica does not make an application DR-ready. Failover still breaks if:

- the container image was never replicated to the DR Region;
- a secret or KMS key exists only in the primary Region;
- the DR execution role's policy still points at a primary-Region ARN;
- a StatefulSet needs an EBS StorageClass, but the DR cluster has no EBS CSI driver;
- Route 53 failover depends on editing records during the outage.

Each resource passes its own check. The stack still fails. Perpetual checks the links between resources.

## How it works

```text
 Terraform · AWS APIs · AWS Config · Resource Explorer · Kubernetes (optional)
     CloudTrail · VPC Flow Logs · security groups · NetworkPolicies · IAM
                                   │
                                   v
                     Normalization + evidence
                                   │
                                   v
            Dependency graph (dependent -> dependency)
                                   │
                    + your edits (confirm, add, edit, reject)
                                   │
                    + DR overlay: how each resource
                      is provided in the DR Region
                                   │
                 ┌─────────────────┴─────────────────┐
                 v                                   v
           Rules engine                    Region-failure simulator
       (evidence-backed findings)         (impact pass, then recovery pass)
                 └─────────────────┬─────────────────┘
                                   v
          One stack recovery DAG  ->  stack RTO / RPO ranges
                                   │
                                   v
                 Optimizer  ->  cost vs RTO/RPO trade-offs
                                   │
                         ┌─────────┴─────────┐
                         v                   v
                 DR Terraform         Failover / failback
                 (companion)          runbooks
```

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
