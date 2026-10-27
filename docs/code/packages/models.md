# `models` package

**Owns:** the shared vocabulary every other package passes around: resources, evidence, edges, stacks, requirements, mechanisms, user edits and status values.
**Spec:** §5.1, §5.3, §5.4, §15–§15.4, §16, §19–§20, §23, §24–§24.1, §26–§27.1, §30.1, §49, §49.2. **Tracker:** P0-04a, P0-04b (P0-04c to P0-04f add more).
**Depends on:** nothing else in Perpetual (an import rule enforces this); only Pydantic. **Used by:** every other package, as they are built.

## In one paragraph

These are plain data classes built with Pydantic. They hold no logic beyond validating themselves: they do no I/O and call no other package. Their job is to make bad data impossible to construct. If a fixture, importer or user edit produces something the spec forbids (an "observed" fact with no time window, a quorum of zero, a Region-failure requirement with no target Region), building the model fails immediately with a clear message, instead of the engine computing a wrong answer later.

## Files

| File | What it holds |
|---|---|
| `common.py` | `DomainModel` (the base class) and shared field types `NonEmptyStr`, `Confidence` |
| `status.py` | Status vocabulary (§30.1): `ResourceState`, `StackState`, `Readiness`, `TargetComparison`; helpers `worst_state`, `stack_state` |
| `evidence.py` | `Evidence`, `SourceType`, `Basis` (§16) |
| `resource.py` | `ResourceNode`, `SourceReference` (§15) |
| `edge.py` | `DependencyEdge`, `DependencyGroup`, `RelationshipType` and their enums (§19–§20) |
| `override.py` | `GraphOverride` and its per-kind payload schemas (§23) |
| `stack.py` | `Stack`, `StackService`, `StackResource`, `RtoScope` (§24, §24.1) |
| `requirement.py` | `RecoveryRequirement`, `DurationEstimate`, `BufferPolicy`, `DRStrategy`, `FailureScope` (§26, §27, §49) |
| `mechanism.py` | `RecoveryMechanism`, `MechanismKind`: the DR overlay (§27.1) |
| `properties/` | Typed per-resource-type properties (§15.3): `base.py` (`TypedProperties`), `ecs.py`, `ec2.py`, `awslambda.py`, and `__init__.py`, which builds the `ResourceProperties` union |
| `__init__.py` | Re-exports every public name: `from perpetual.models import DependencyEdge` |

## How it works

### The base class

Every model inherits `DomainModel` (`common.py`), which sets three behaviours:

- **immutable** (`frozen=True`): a model can't be changed after it is built. Change means building a new one, e.g. `override.model_copy(update={"status": "orphaned"})`. This keeps snapshots and evaluation inputs stable, which later work hashes into digests (§56.3).
- **unknown fields rejected** (`extra="forbid"`): a typo such as `confidance=0.9` in a fixture fails loudly instead of being ignored.
- **validation on construction**: field types are checked first, then each model's `@model_validator(mode="after")` method checks rules that span several fields.

Timestamps use `AwareDatetime`, so a time without a timezone is rejected.

### Resources and evidence

A `ResourceNode` is one resource, whatever source it came from. Its `id` is the canonical form `aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER` (helpers for building and parsing it arrive in P0-05). `properties` is the raw store, which rules never read; `typed_properties` holds the typed configuration (next section). `planned=True` marks a resource that exists only in a Terraform plan.

`Evidence` is one traceable fact. For dependency evidence, `basis` says what kind of fact it is:

```text
permitted    a connection is allowed      (security group, IAM policy)
referenced   configuration points at it   (Terraform reference, task definition)
observed     traffic was seen             (CloudTrail, flow logs; stored as window + count only)
asserted     a person said so             (user confirmation)
```

### Typed properties

Rules read a resource's configuration from `typed_properties`, a model specific to its type. Each model has a `type_key` equal to the `SERVICE/TYPE` part of the resource ID, and `ResourceProperties` is a union of all of them. Pydantic reads `type_key` and builds the matching model, so a plain dict from a fixture or importer becomes the right class:

```python
node = ResourceNode.model_validate({
    "id": "aws://123456789012/ap-south-1/ecs/service/checkout",
    "provider": "aws", "service": "ecs", "resource_type": "service",
    "typed_properties": {"type_key": "ecs/service", "service_name": "checkout",
                         "cluster_arn": "...", "task_definition_arn": "...", "desired_count": 3},
    "discovered_at": "2026-10-28T12:00:00Z",
})
type(node.typed_properties)  # ECSServiceProperties
```

The node checks that `type_key` matches its own `service/resource_type`.

| `type_key` | Model | What rules use it for |
|---|---|---|
| `ecs/cluster` | `ECSClusterProperties` | capacity providers |
| `ecs/service` | `ECSServiceProperties` | task definition, launch type, desired count, subnets, security groups, target groups, Cloud Map, scaling |
| `ecs/task-definition` | `ECSTaskDefinitionProperties` | roles, containers: images, secret references, env var names, health checks |
| `ec2/instance` | `EC2InstanceProperties` | AMI, instance type, subnet, profile, volumes |
| `autoscaling/group` | `AutoScalingGroupProperties` | sizes, launch template, instance types, subnets, target groups |
| `ec2/launch-template` | `LaunchTemplateProperties` | AMI (or SSM parameter), profile, block devices and their KMS keys |
| `ec2/image` | `AMIProperties` | owner, state, backing snapshots and KMS keys |
| `lambda/function` | `LambdaFunctionProperties` | package type, S3 code or ECR image, layers, role, VPC, env var names, destinations, concurrency |
| `lambda/event-source-mapping` | `LambdaEventSourceMappingProperties` | source queue/stream, target function, state, failure destination |

**Three kinds of missing.** A field set to None means absent or null in the source. A field named in `unknown_fields` is *unknown*, for example a Terraform plan value only known after apply; rules must treat it as UNKNOWN, never as absent or as the old live value (§15.4). An empty list means known to be empty.

**What is never stored.** Secrets appear only as references (`SecretReference.value_from` is an ARN). Environment variables keep only their names. Launch templates record only whether user data exists. The models have no field for these values, so a collector that tried to store one would fail validation (§67).

To add a resource type: write a model in `properties/` with a unique `type_key` literal and add it to the union in `properties/__init__.py`.

### Edges and groups

A `DependencyEdge` always points **dependent → dependency**: `ECS service → RDS database` means the service needs the database. Its `bases` property is computed from its evidence, never stored.

`RelationshipType` is the fixed vocabulary from §20. Four relationships are not requirements, and `is_operational_requirement` returns False for them: `contains` and `member_of` (structure), and `replicates_to` and `backed_up_by` (a primary doesn't fail because its replica or backup fails; only the DR overlay follows these).

A `DependencyGroup` says how a dependent's edges combine:

```text
all      every member is needed            (the default for an ungrouped required edge)
any      one member is enough              (e.g. two interchangeable endpoints)
quorum   minimum_healthy members needed    (e.g. 2 of 3)
```

`required_members` gives that number.

### Stacks and requirements

A `Stack` is the unit of DR. `StackResource` records membership plus RTO scope: monitoring, logging and CI/CD are `out_of_scope` by default (§24.1). `StackService` exists for display only.

A `RecoveryRequirement` holds the targets for one stack and failure scope: RTO, RPO, budget and, for Region failure, the target Region. Durations use `DurationEstimate` (low / expected / high, each possibly unknown) and `BufferPolicy` (handoff, stack validation, contingency).

### The DR overlay and user edits

A `RecoveryMechanism` says how one primary resource is provided in the DR target: a live counterpart, a restore, a rebuild from IaC, and so on. The overlay is itself graph-shaped: `dr_dependency_ids` and DR-side groups list what recovery needs in the DR Region.

A `GraphOverride` is a user edit (confirm, reject, add or edit an edge; add or edit a node). Its `payload` is a plain dict, so it round-trips through YAML, but it is validated against the schema for its `kind`; `typed_payload()` returns the parsed version.

### Status vocabulary

```text
resource state, worst first:  BLOCKED > UNKNOWN > RECOVERABLE > SURVIVES
stack state:                  BLOCKED -> UNAVAILABLE, UNKNOWN -> UNKNOWN, otherwise RECOVERABLE
```

```python
from perpetual.models import ResourceState, stack_state

stack_state([ResourceState.SURVIVES, ResourceState.UNKNOWN])  # StackState.UNKNOWN
```

## Rules it enforces, and why

| Rule | Where | Why (spec) |
|---|---|---|
| Confidence is between 0 and 1 | `Confidence` type | §16, §19, §22 |
| Observed evidence has a window and count; other evidence has none | `Evidence` | Observed data is stored only as aggregates (§14.1, §65–§67) |
| Every evidence item on an edge has a basis | `DependencyEdge` | Bases drive weighting and review (§14.1, §19) |
| A user-added edge has confidence 1.0 and asserted user evidence | `DependencyEdge` | §23 |
| `confirmed` agrees with `review_state` | `DependencyEdge` | One review, one answer |
| Relationship types come from the §20 vocabulary | `RelationshipType` | "Do not create dozens of relationships" (§20) |
| Group members are distinct; quorum is between 1 and the member count | `DependencyGroup` | §19.1 |
| Override payloads match their kind | `GraphOverride` | Payloads are "validated per kind" (§23) |
| Stack roots are stack members | `Stack` | Closure starts from roots (§24) |
| A Region-failure requirement names its target Region | `RecoveryRequirement` | §26 |
| Duration bounds are ordered; unknown bounds stay None | `DurationEstimate` | Unknown is never zero (§30, §49.1) |
| A mechanism's groups are DR-side | `RecoveryMechanism` | §27.1 |
| Typed properties match the node's `service/resource_type` | `ResourceNode` | §15.3 |
| `unknown_fields` names only real configuration fields | `TypedProperties` | Unknown must stay distinct from absent (§15.4) |
| Secret values, env values and user data have no field to live in | `ecs.py`, `awslambda.py`, `ec2.py` | §67 |
| Auto Scaling sizes satisfy min ≤ desired ≤ max | `AutoScalingGroupProperties` | AWS rejects anything else; such data means a broken import |
| A launch template has one image source: AMI ID or SSM parameter | `LaunchTemplateProperties` | §5.3 |
| An Image function has an image and no S3 package or layers; a Zip function has no image | `LambdaFunctionProperties` | §5.4 |
| A task definition has at least one container | `ECSTaskDefinitionProperties` | §5.1 |
| Combining no states is an error, not SURVIVES | `worst_state` | Missing evidence must never read as healthy (§30) |

Rules that need the whole graph, such as "group members share one dependent" and "an edge is in at most one group", are checked when the graph is built (P0-11).

## Tests

`apps/api/tests/models/`, one file per topic; shared builders in `builders.py`.

- `test_model_status.py`: state ordering and the stack-state mapping.
- `test_model_evidence.py`: observation windows, confidence bounds, timezones, unknown fields, immutability.
- `test_model_edge.py`: bases, user edges, review-state consistency, relationship vocabulary, group rules.
- `test_model_stack_and_requirement.py`: stack roots, requirements, durations, mechanisms, override payloads.
- `test_model_properties_compute.py`: union selection by `type_key`, type mismatch, `unknown_fields`, no secret/env/user-data values, ECS/EC2/Lambda rules.

## Not here yet

- Typed properties for data and storage (P0-04c), messaging, network and supporting services (P0-04d), external/generic resources and quota/metric facts (P0-04e).
- Evaluation, coverage, cost, verification and drill models: P0-04f.
- Canonical ID helpers: P0-05.
