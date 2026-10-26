> **Perpetual Engineering Specification (Revision 4)** — Part VII — Platform, API/CLI/UI, Testing & Delivery (§71–§109)  
> [↑ Spec Overview & Index](../../spec.md) · [← 06-security-and-llm.md](06-security-and-llm.md)

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
LangGraph + langchain-core (agents, checkpointing)
LangChain integrations as extras: openai (OpenAI-compatible, OpenRouter),
  anthropic, aws (Bedrock), ollama
sqlite-vec + FTS5 (knowledge base)
fastembed (local embeddings, optional)
python-hcl2 (static verification)
```

Tools pinned in `mise.toml` for transformation and verification: Terraform, kubeconform, kustomize, helm, gh (optional).

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
- AWS access uses the user's own credential chain (section 66). Discovery data, CloudTrail and flow-log aggregates and Terraform state never leave the machine, except for what the user chooses to send to an LLM provider (section 69.5).
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
|   |       +-- iac/            # code mapping, worktrees, verification, companion templates
|   |       +-- runbooks/
|   |       +-- llm/            # providers, agents (LangGraph), guardrails, call log
|   |       +-- knowledge/      # knowledge base ingestion and retrieval
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
|   +-- logs/            # synthetic CloudTrail and flow-log generator
|
+-- tests/
|   +-- contract/        # real-AWS contract suite (section 90.1)
|
+-- examples/
|   +-- ecs-rds/         # also the IaC repos the transformation evals change
|   +-- eks-rds/
|
+-- skills/              # shipped DR skills (section 69.4)
|
+-- knowledge/
|   +-- domain/          # shipped DR domain docs for all in-scope AWS services
|   +-- sources.yaml     # public reference URLs for `perpetual kb sync`
|
+-- evals/               # LLM evaluation suite (section 69.6)
|
+-- generated/
|
+-- docs/
|
+-- docker-compose.yml   # Floci and Postgres for tests; not needed to run locally
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

  ec2/
    compute.py
    ami.py
    asg.py

  lambda_/
    functions.py
    events.py

  sqs/
    queues.py

  sns/
    topics.py

  waf/
    web_acl.py

  logs/
    log_groups.py
```

---

# 75. Persistence Model

Initial entities (SQLite by default, PostgreSQL-compatible):

```text
projects
cloud_accounts
scans
scan_coverage
evaluation_inputs
sources

resources
resource_versions

edges
edge_evidence
edge_feedback
dependency_groups
graph_overrides
observations

stacks
stack_resources
stack_services

recovery_requirements
workload_profiles

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

advisory_items
dr_specs
transformations
verification_reports
deployment_prerequisites
llm_calls
kb_documents
kb_chunks

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
    coverage: list[ScanCoverage]
    snapshot_id: str | None
    # Published atomically after collection; partial snapshots retain coverage failures.
```

Keep previous scans.

This eventually enables drift analysis.

## 76.1 Coverage, Freshness and Absence

`ScanCoverage` is keyed by account, Region/global scope, service, operation family and inventory/metric window. It records `status = complete | partial | denied | unsupported | not_requested`, start/completion times, pagination completion, error codes, and the identities/attributes actually checked. A successful list with a failed detail request is partial for that detail; an interrupted page sequence is never complete inventory. Normalized facts reference their coverage records.

Build each snapshot atomically from a declared set of collection runs. Publish successful facts even when some coverage fails, but distinguish `present`, `confirmed_absent` and `unknown`. A resource is confirmed absent only after complete authoritative inventory of its ownership scope (and matching identity rules); absent attributes require a successful API response with defined omission semantics. Failed, denied, unsupported or unrequested discovery cannot delete resources, orphan overrides, or prove mechanism `none`.

Previous facts may remain in the snapshot as historical context, with original timestamps and `carried_forward=true`. A newly failed authoritative check makes the corresponding current fact unknown even if its last successful value is recent; do not silently refresh its timestamp. A skipped collection may reuse a fact only within its freshness policy, explicitly showing that reuse. Successful deletion detection invalidates dependent mechanisms/edges and makes affected overrides orphaned.

Freshness is typed project configuration by fact family: initial maximum age 24 hours for inventory/configuration, 15 minutes for the latest replication/usage/quota measurement, and maximum 30 minutes between participating primary/DR inventory completion times. These are conservative product defaults, not service guarantees. Record overrides and all policy versions in EvaluationInput. Measurement windows may be longer (e.g. lag distributions), but need a recent sample; missing metrics are not zero. Snapshot/recovery-point creation time remains an RPO input, distinct from freshness of the API check that confirmed its usability.

Each check declares required fact families and scope. Mandatory inventory coverage includes enabled in-scope service inventories in the declared accounts/Regions so a completely undiscovered dependency type cannot silently disappear. Missing coverage/freshness on a required selected recovery path, or required inventory that prevents determining that path, produces UNKNOWN with `coverage_incomplete` or `evidence_stale`; lowering a confidence percentage is insufficient. Optional observation sources and out-of-scope services report limitations without blanket failure when other evidence establishes the required path. Proven blockers still yield NOT_READY.

Test a failed DR scan after a known replica, first-scan AccessDenied, partial pagination, successful confirmed deletion, expired lag samples, stale cross-account snapshots, optional log denial, and failed detail lookup after successful listing. The CLI/UI show evaluated-at time, coverage and stale reasons alongside verdicts.

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

LLM-assisted:

```text
POST /stacks/{id}/advise
GET  /stacks/{id}/advisories
POST /advisories/{id}/accept
POST /advisories/{id}/dismiss

POST /stacks/{id}/dr-spec              # from the selected candidate
GET  /dr-specs/{id}
POST /dr-specs/{id}/approve

POST /dr-specs/{id}/transform          # body: IaC paths, open_pr
GET  /transformations/{id}             # progress, diff, verification report

GET    /llm/calls
POST   /kb/sync
GET    /kb/documents
POST   /kb/documents
GET    /kb/documents/{id}
DELETE /kb/documents/{id}
```

Later:

```text
POST /stacks/{id}/terraform/companion

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
  --budget 1200            # includes LLM candidates unless --no-llm

perpetual llm configure
perpetual llm test
perpetual llm log

perpetual kb sync
perpetual kb add ./docs/runbooks
perpetual kb list [--origin agent_web_fetch]
perpetual kb show <doc-id>
perpetual kb remove <doc-id>

perpetual skills list

perpetual advise checkout
perpetual dr-spec checkout [--approve]
perpetual transform checkout \
  --terraform ./infra/live/prod \
  --k8s ./deploy/overlays/prod \
  [--open-pr]
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

# 90.1 Test Environments

Development does not need a real AWS account until Phase 2, and after that only for a small contract suite.

Four environments, from fastest to most real:

```text
fixtures     YAML normalized graph + DR overlay + overrides (section 104),
             saved `terraform show -json` files, saved API responses (fixtures/aws/).
             No network, no credentials.

moto         in-process boto3 mocks for collector unit tests.

Floci        local AWS emulator in Docker, for collector integration tests in CI.
             The demo Terraform (sections 85-89) is applied to it, then scanned.

real AWS     a sandbox account (plus a DR account for section 66 tests), used for
             a small contract suite. Never a customer or production account.
```

Which environment each part uses:

```text
Phases 0-1    engine, simulator, recovery DAG, RTO        fixtures
Phase 1b      API, UI, Terraform importer                 fixtures
Phase 2       collectors                                  moto (unit), Floci (integration),
                                                          real AWS (contract)
Phase 2b      CloudTrail and flow-log readers             synthetic log files in Floci S3,
                                                          real AWS (contract)
Phases 3-8    stack discovery, rules, RPO, optimizer      fixtures
Phase 3b      LLM foundation                              fake chat model (recorded responses)
Phase 9       IaC transformation                          examples/ repos + Floci for terraform
                                                          plan; fake model in CI, evals on demand
```

### Synthetic logs

Emulators do not produce real CloudTrail or VPC Flow Logs, because there is no real traffic. A generator in `fixtures/logs/` writes files in the real delivery formats (CloudTrail JSON in the trail's S3 key layout; flow-log records, versions 2 and 5) from a scenario description:

```yaml
scenario: checkout-observed
window_days: 30
calls:
  - principal_role: checkout-task-role
    action: secretsmanager:GetSecretValue
    resource: checkout/db
    count: 4200
flows:
  - from: ecs:checkout-api
    to: rds:orders
    port: 5432
    count: 900
  - from: ecs:checkout-api
    to: 203.0.113.10       # unknown external destination
    port: 443
    count: 50
```

Generated files are uploaded to a Floci S3 bucket, so readers are tested through the same S3 path they use in production. The generator also produces the edge cases from section 14.1: reused Fargate ENIs, unresolvable addresses, observed-but-not-permitted flows.

### What emulators cannot prove

These need the real AWS contract suite:

- cross-Region behaviour: S3 replication status, RDS cross-Region replica lag, ECR replication, multi-Region KMS keys;
- Region facts: Service Quotas, `DescribeInstanceTypeOfferings`, Resource Explorer, AWS Config relationship data;
- exact ARN and ID formats, Fargate task ENI descriptions, real IAM policy documents;
- real CloudTrail and flow-log delivery, including data-event coverage detection;
- cross-account access to a separate DR account (section 66).

Emulator support is checked per service and operation before it is relied on. A passing Floci test proves the SDK calls work, not that behaviour matches AWS.

### Real-AWS contract suite

- lives in `tests/contract/`, marked so it never runs by default;
- runs by hand or nightly with explicit sandbox credentials;
- the reference environments (sections 85-89) are Terraform in `examples/`, applied to the sandbox for a test session and destroyed after it;
- cross-Region RDS replicas and NAT gateways cost money while running, so the suite destroys them on exit, including on failure;
- recorded responses from contract runs are redacted and saved to `fixtures/aws/`, so fixtures stay close to real AWS.

Real-AWS checkpoints:

```text
Phase 2 exit      scan the sandbox account -> normalized graph
Phase 2b exit     real CloudTrail and flow logs -> observed edges
Sections 87-89    demo scenarios reproduced on real infrastructure
```

---

## 90.2 Review Regression Gates

These are required release regressions in addition to the canonical ECS/EKS demos. Each is implemented in its owning phase, not deferred to final hardening.

| Contract | Minimum regression | Plan owner |
|---|---|---|
| Planned snapshot (15.4) | A changed property overrides live configuration; deletion/replacement removes obsolete proof; unknown fields stay unknown; root identities do not collide | P1b-15, P10-04 |
| Verification stages (61.1) | New replica with no estimator stays unknown; modeled design PASS retains pending seeding/image/secret prerequisites; static-only is never design verified; rescan is required for observed READY | P8-01, P10-04/08, P12-01 |
| Execution isolation (61) | External data source, unapproved provider/plugin, symlink escape, credential read, forbidden egress and cloud mutation are denied; lack of isolation fails closed | P10-09 |
| Coverage and freshness (76.1) | Failed DR collector retains historical replica but cannot prove readiness; complete deletion differs from AccessDenied/partial pagination; stale metrics and scan skew gate results | P2-13 |
| Readiness (31) | Ordered table, proven failure plus unknown, target equality, RPO FAIL with usable recovery, missing evaluator, optional budget and out-of-scope findings | P1-07/18, P4-05, P8-03, P9-04 |
| Evidence producers (28.1) | Each enabled service/rule/estimator maps to typed collected facts, actions and tests; include quotas, metrics, EFS and basic DynamoDB | P0-04, P2-12, P4-08; plan §3.5 |
| Approval validity (56.3) | Requirement/scan/override/base-tree/backend change and expiry invalidate approval; resume checks digest; post-verification edit invalidates report | P0-15, P9-08, P10-01/04/05 |
| Redundancy (19.1) | ANY one-of-two, both failed, quorum two-of-three, unknown member, shared failed prerequisite, bounded selection and selected-path review | P1-18 |
| Attribution (14.1) | Shared role/ENI keeps one ambiguous aggregate without confidence inflation; exact evidence and user confirmation resolve it | P2b-09 |
| Cost/budget (59.1) | Missing/stale price or usage, shared-resource deduplication, total/incremental separation, range straddling budget, exact equality and unknown Pareto exclusion | P9-03/04/09 |
| Terraform format (15.4) | Saved-plan show JSON accepted; plan UI JSON rejected with an actionable error | P1b-01, P10-04 |

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
EC2/Auto Scaling/VPC
Lambda
RDS/Aurora
S3
SQS
SNS
ECR
ELB
Route53
WAF
Secrets Manager
SSM Parameter Store
KMS
IAM
CloudWatch Logs
```

Add Resource Explorer and Config as supplementary sources.

Dependency evidence in this phase: security groups, IAM policies and configuration references.

Collectors are tested with moto and Floci, then checked against a real sandbox account (section 90.1).

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

Readers are developed against synthetic log files (section 90.1), then checked against real logs in the sandbox account.

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

## Phase 3b — LLM Foundation

Deliver:

- provider abstraction and per-role configuration (section 69.1);
- LangGraph runtime with SQLite checkpointing;
- fake chat model and recorded-response test harness;
- knowledge base: ingestion, hybrid retrieval, citations (section 69.3);
- skills loader and the first shipped skills (section 69.4);
- guardrails: opt-in notice, redaction, `.perpetualignore`, call log (section 69.5);
- explainer agent (section 70).

Exit criterion:

```text
perpetual llm test passes against a configured provider; the explainer answers
"why can't checkout meet 30m?" with cited, engine-sourced numbers.
```

---

## Phase 4 — DR Rule Engine

First rule packs:

```text
ECS
EKS
EC2/ASG
Lambda
RDS
S3
SQS
SNS
ECR
Secrets/SSM
KMS
IAM
network
ALB
Route53
WAF
CloudWatch Logs
```

Then the advisory review (section 28.2).

Exit criterion:

```text
Stack assessment produces evidence-backed findings; advisory items appear with
citations and can be accepted or dismissed.
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

Includes the LLM candidate planner (section 56.1) and the DR spec (section 56.2).

Exit criterion:

```text
Several architecture candidates, deterministic and LLM-proposed, can be compared,
and an approved DR spec exists for each demo stack.
```

---

## Phase 9 — IaC Transformation

Deliver:

- resource-to-code mapping for Terraform and Kubernetes (section 61);
- transformation agent in a git worktree with the tool allowlist;
- verification loop (section 61.1), including static fallback;
- change delivery: branch, commits, patch, optional PR (section 62);
- companion fallback templates (section 62.1);
- evaluation suite runs on `examples/` (section 69.6).

Exit criterion:

```text
For the broken ECS and EKS demos, `perpetual transform` changes the example
Terraform and manifests, verification passes, and the re-simulated stack meets
its targets.
```

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

9. Perpetual compares candidate architectures (deterministic and
   LLM-proposed) and the user approves a DR spec:
   current vs target architecture
   RTO, RPO, total steady-state DR cost and incremental cost

10. Perpetual changes the user's Terraform and Kubernetes manifests,
    verifies the design by re-simulating, and delivers a branch or PR
    with deployment prerequisites and stage-specific results.

11. Perpetual generates:
    failover runbook
    failback runbook

12. After the user deploys and completes prerequisites, a fresh scan
    establishes observed readiness; design verification alone cannot.
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
- applying changes: `terraform apply`, `kubectl apply`, merging or pushing to protected branches;
- editing code outside the declared IaC paths, CI pipelines or remote modules;
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

They do not call LLMs. LLM review runs as a separate stage after them (section 28.2).

### Rule 5

Simulator consumes graph state.

It does not rediscover AWS.

### Rule 6

Optimizer consumes recovery options.

LLM-proposed candidates enter as typed options and are evaluated by the same deterministic code (section 56.1).

### Rule 7

Code changes are proposed by an agent and accepted only after verification (section 61.1). Companion Terraform is deterministic.

### Rule 8

Missing information becomes UNKNOWN, not PASS.

### Rule 9

Every important conclusion must be explainable through evidence.

### Rule 10

Every important graph dependency must expose why it exists.

### Rule 11

An LLM output never changes a state, number or verdict by itself. It becomes a result only through deterministic verification or user confirmation.

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

The first complete vertical slice should use:

```text
Route53
WAF
ALB
ECS
EC2 / Auto Scaling
Lambda
SQS
SNS
ECR
Secrets Manager / SSM
KMS
IAM
RDS
S3
CloudWatch Logs
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

And: Perpetual only offers a change to infrastructure code once its own engine has shown the change makes the stack meet its targets.

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

---

> [↑ Spec Overview & Index](../../spec.md) · [← 06-security-and-llm.md](06-security-and-llm.md)
