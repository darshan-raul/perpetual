# `models` package

**Owns:** the shared vocabulary every other package passes around: resources, evidence, edges, stacks, requirements, mechanisms, user edits and status values.
**Spec:** §15, §16, §19–§20, §23, §24–§24.1, §26–§27.1, §30.1, §49, §49.2. **Tracker:** P0-04a (P0-04b to P0-04f add more).
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
| `__init__.py` | Re-exports every public name: `from perpetual.models import DependencyEdge` |

## How it works

### The base class

Every model inherits `DomainModel` (`common.py`), which sets three behaviours:

- **immutable** (`frozen=True`): a model can't be changed after it is built. Change means building a new one, e.g. `override.model_copy(update={"status": "orphaned"})`. This keeps snapshots and evaluation inputs stable, which later work hashes into digests (§56.3).
- **unknown fields rejected** (`extra="forbid"`): a typo such as `confidance=0.9` in a fixture fails loudly instead of being ignored.
- **validation on construction**: field types are checked first, then each model's `@model_validator(mode="after")` method checks rules that span several fields.

Timestamps use `AwareDatetime`, so a time without a timezone is rejected.

### Resources and evidence

A `ResourceNode` is one resource, whatever source it came from. Its `id` is the canonical form `aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER` (helpers for building and parsing it arrive in P0-05). `properties` is the raw store; typed per-type properties arrive in P0-04b to P0-04e. `planned=True` marks a resource that exists only in a Terraform plan.

`Evidence` is one traceable fact. For dependency evidence, `basis` says what kind of fact it is:

```text
permitted    a connection is allowed      (security group, IAM policy)
referenced   configuration points at it   (Terraform reference, task definition)
observed     traffic was seen             (CloudTrail, flow logs; stored as window + count only)
asserted     a person said so             (user confirmation)
```

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
| Combining no states is an error, not SURVIVES | `worst_state` | Missing evidence must never read as healthy (§30) |

Rules that need the whole graph, such as "group members share one dependent" and "an edge is in at most one group", are checked when the graph is built (P0-11).

## Tests

`apps/api/tests/models/`, one file per topic; shared builders in `builders.py`.

- `test_model_status.py`: state ordering and the stack-state mapping.
- `test_model_evidence.py`: observation windows, confidence bounds, timezones, unknown fields, immutability.
- `test_model_edge.py`: bases, user edges, review-state consistency, relationship vocabulary, group rules.
- `test_model_stack_and_requirement.py`: stack roots, requirements, durations, mechanisms, override payloads.

## Not here yet

- Typed resource properties per resource type: P0-04b to P0-04e.
- Evaluation, coverage, cost, verification and drill models: P0-04f.
- Canonical ID helpers: P0-05.
