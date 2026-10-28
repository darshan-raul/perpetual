# `models` package

**Owns:** the shared vocabulary every other package passes around: resources, evidence, edges, stacks, requirements, mechanisms, user edits and status values, plus the records around an evaluation: coverage, observations, cost, evaluation inputs, verification reports, drills and operator access.
**Spec:** §3 (readiness tiers), §5–§8.1, §14.1, §15–§15.4, §16, §19–§20, §23, §24–§24.1, §26–§27.1, §28.1, §30.1, §49, §49.2, §53, §56.3, §59.1, §61.1, §76.1. **Tracker:** P0-04a to P0-04f.
**Depends on:** nothing else in Perpetual (an import rule enforces this); only Pydantic. **Used by:** every other package, as they are built.

## In one paragraph

These are plain data classes built with Pydantic. They hold no logic beyond validating themselves: they do no I/O and call no other package. Their job is to make bad data impossible to construct. If a fixture, importer or user edit produces something the spec forbids (an "observed" fact with no time window, a quorum of zero, a Region-failure requirement with no target Region), building the model fails immediately with a clear message, instead of the engine computing a wrong answer later.

## Files

| File | What it holds |
|---|---|
| `common.py` | `DomainModel` (the base class) and shared field types `NonEmptyStr`, `Confidence`, `Digest` (`sha256:<hex>`), `SortedIds` (distinct, stored sorted) |
| `status.py` | Status vocabulary (§30.1): `ResourceState`, `StackState`, `Readiness`, `TargetComparison`, and the evidence label `ReadinessTier` (§3); helpers `worst_state`, `stack_state` |
| `evidence.py` | `Evidence`, `SourceType`, `Basis` (§16) |
| `resource.py` | `ResourceNode`, `SourceReference` (§15) |
| `edge.py` | `DependencyEdge`, `DependencyGroup`, `RelationshipType` and their enums (§19–§20) |
| `override.py` | `GraphOverride` and its per-kind payload schemas (§23) |
| `stack.py` | `Stack`, `StackService`, `StackResource`, `RtoScope` (§24, §24.1) |
| `requirement.py` | `RecoveryRequirement`, `DurationEstimate`, `BufferPolicy`, `DRStrategy`, `FailureScope` (§26, §27, §49) |
| `mechanism.py` | `RecoveryMechanism`, `MechanismKind`: the DR overlay (§27.1) |
| `facts.py` | Measured facts that are not configuration: `QuotaFact`, `InstanceTypeOfferingFact`, `CapabilityFact`, `MetricFact`, and the `FactRecord` union (§28.1, §76.1) |
| `coverage.py` | `ScanCoverage`, `CoverageStatus`, `Presence`, `FreshnessPolicy` (§76.1) |
| `observation.py` | `ResolvedObservation` and `Attribution` (exact or ambiguous): CloudTrail and flow-log aggregates resolved to resources (§14.1) |
| `cost.py` | `WorkloadProfile`, `WorkloadQuantity`, `CostEstimate`, `CostLineItem` and their enums (§59.1) |
| `evaluation.py` | `EvaluationInput`, the immutable manifest a result is computed from, with `InputRef`, `IaCBaseline`, `IaCRoot`, `CompanionDesign` (§56.3) |
| `verification.py` | `DeploymentPrerequisite`, `VerificationReport`, `CheckResult`, their status enums, and `combined_prerequisite_status` (§61.1) |
| `drill.py` | `DRDrill`, `DrillSource`, `DrillStatus` (§53); schema only until P14 |
| `operator_access.py` | `OperatorAccessProfile` and its parts: the `operator_access` section of `perpetual.yaml` (§28.1) |
| `properties/` | Typed per-resource-type properties, one file per service area. See [models-properties.md](models-properties.md) |
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

Rules read a resource's configuration from `typed_properties`, a model specific to its type (54 type keys so far), never from the raw `properties` dict. Pydantic picks the model from its `type_key`, which matches the `SERVICE/TYPE` part of the resource ID. The node checks they agree. Missing values come in three kinds (absent, unknown until apply, known empty), and secret values have no field to live in.

Everything about them, including the full list of types, is on its own page: **[models-properties.md](models-properties.md)**.

### Facts

Some things the rules need are not resource configuration: a Service Quotas limit and current usage, which instance types a Region offers, whether a feature exists in a Region, a CloudWatch series such as replica lag. They change much faster than configuration and have tighter freshness limits (§76.1: 15 minutes for the latest replication, usage or quota measurement), so they live in `facts.py`, apart from resources.

Every fact records where and when it was collected, which coverage record produced it (§76.1, model in P0-04f), and whether it is `carried_forward` history that cannot satisfy a check by itself. `FactRecord` picks the fact type from `kind`.

The guiding rule is that **missing data stays unknown**:

- `QuotaFact.headroom` is None unless both the limit and current usage are known. A limit alone proves nothing: the account may already use most of it.
- `MetricFact` separates `ok`, `no_data`, `access_denied` and `error`. Only an `ok` read has samples, and it always has at least one, so "no data" can never read as zero. `latest_sample_at` is what freshness is judged on, and `missing_samples` shows gaps.
- `CapabilityFact` is `available`, `unavailable` or `unknown`. An answer from a catalog names the catalog version.

### Coverage and freshness

Every fact points at the `ScanCoverage` record of the collection that produced it: one record per account, Region (or global), service and operation family. Its status is `complete`, `partial`, `denied`, `unsupported` or `not_requested`, and only `complete` is authoritative. The model refuses to call a run complete if pagination stopped early or errors were recorded, and a denied run must record its error codes.

`Presence` is how later stages say what coverage proved: `present`, `confirmed_absent` (only after complete inventory of the resource's scope) or `unknown`. Failed or skipped discovery gives `unknown`; it never deletes a resource or proves a mechanism is `none`.

`FreshnessPolicy` has the shape of the maximum-age settings (inventory, latest measurement, primary/DR skew) but no default values. The values live in YAML config (P0-06), and the policy version goes into every evaluation input.

### Resolved observations

A `ResolvedObservation` is a CloudTrail or flow-log aggregate (window and count, never raw events) with the resources at each end. Shared roles and Lambda ENIs often leave several candidates:

```text
exact       one resource at each end; must cite the evidence that resolved it
ambiguous   several candidates at one end; stored once against the sorted candidate sets
```

An ambiguous observation is not copied onto every possible edge, and its count is not multiplied. Edge resolvers and the review flow (P2b) build on this.

### Workload and cost

A `WorkloadProfile` is a versioned set of quantities for one stack (requests, stored GB, replication GB per month, and so on), each with low/expected/high bounds. A measured quantity carries its observation window; an estimate or forecast must record its assumptions. A quantity that isn't listed is unknown, never idle.

A `CostEstimate` is a list of `CostLineItem`s with unique keys, so a shared foundation is counted once. Totals and the fixed/variable subtotals are computed from the lines, so they can't disagree. **One unknown line makes that total unknown**; a known fixed subtotal can't hide it. A line can be zero only with a `zero_reason`. Budget comparison itself belongs to the costing stage.

### Evaluation inputs

An `EvaluationInput` lists everything a result was computed from: primary and DR snapshot IDs and inventory times, coverage IDs, graph/override/group revisions, requirement and workload-profile revisions, engine and rule-pack versions, config/duration/price catalog digests, the freshness-policy version, and the assumptions, confirmations, skills and documents used. Before approval it also pins either the IaC baseline (base commit, tree digest, roots with workspace, provider Regions, backend lineage/serial and lock-file digest) or the companion design's template and input digests, never both. Lists are normalized so the same manifest always hashes the same. It holds identities and digests only: no credentials, state or secret values. The canonical approval digest is computed in P9-08.

### Verification and prerequisites

A `VerificationReport` keeps four answers apart (§61.1): `static_checks`, `design_verification`, the combined `deployment_prerequisites` status, and `observed_readiness`. It is bound to the approved digest, tree digest and saved-plan digest it checked.

```text
static_checks_only mode    design verification can't pass       -> "static checks only"
design pass                needs full mode, passing static checks, no unverified changes,
                           no failed prerequisite                -> "design verified — deployment
                                                                     and observation pending"
observed READY             needs every prerequisite satisfied
```

A `DeploymentPrerequisite` is something a plan can't prove (an image is present, an initial copy finished, a quota was raised). It names affected resources, owner, required evidence and re-check IDs. Satisfied or failed must cite evidence, so nothing is marked done just because its configuration exists. `combined_prerequisite_status` picks the worst: failed, then unknown, then pending.

### Drills and readiness tiers

`DRDrill` is the §53 schema plus the source (ARC execution report, recovery-script log, fault injection, Resilience Hub test) and optional digests of the scan and design it tested. Unmeasured RTO/RPO stay None. `ReadinessTier` (`DESIGN_VERIFIED`, `CONFIGURED`, `PROVEN`) labels the evidence behind a result; it is not a state.

### Operator access

`OperatorAccessProfile` mirrors the `operator_access` YAML section: identity source with home and replica Regions, a break-glass method, network paths to private endpoints and the Region each ends in, and pinned tool versions. `replica_regions: None` means unknown, `[]` means declared to have none. Typos in the YAML fail because unknown fields are rejected. The loader and OPS-ACCESS rules arrive in P4-04c.

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
| Rules of each resource type | `properties/` | see [models-properties.md](models-properties.md#rules-they-enforce-and-why) |
| Combining no states is an error, not SURVIVES | `worst_state` | Missing evidence must never read as healthy (§30) |
| Complete coverage has a completion time, finished pagination and no errors; denied coverage records its errors | `ScanCoverage` | An interrupted page sequence is never complete inventory (§76.1) |
| An exact observation has one resource at each end and cites its resolution evidence; an ambiguous one has several candidates | `ResolvedObservation` | Ambiguity gives no exact-edge uplift; current ownership doesn't prove historical ownership (§14.1) |
| Measured quantities have a window; estimates record assumptions | `WorkloadQuantity` | Estimates never become measured evidence (§59.1) |
| An unknown line makes the total unknown; zero needs a reason; line keys are unique | `CostEstimate`, `CostLineItem` | Missing prices/usage are never zero; shared costs count once (§59.1) |
| Digests are `sha256:<64 lowercase hex>`; lists are sorted and distinct | `Digest`, `SortedIds`, `EvaluationInput` | Canonical digests must not depend on order (§56.3) |
| A design can pass only in full mode with passing static checks, no unverified changes and no failed prerequisite | `VerificationReport` | §61.1 |
| Observed READY needs every prerequisite satisfied; settled prerequisites cite evidence | `VerificationReport`, `DeploymentPrerequisite` | No operational check passes because its configuration exists (§61.1) |
| Identity Regions apply only to IAM Identity Center; unknown replicas are None, not [] | `OperatorIdentity` | Undeclared, undiscovered facts stay UNKNOWN (§28.1) |

Rules that need the whole graph, such as "group members share one dependent" and "an edge is in at most one group", are checked when the graph is built (P0-11).

## Tests

`apps/api/tests/models/`, one file per topic; shared builders in `builders.py`.

- `test_model_status.py`: state ordering and the stack-state mapping.
- `test_model_evidence.py`: observation windows, confidence bounds, timezones, unknown fields, immutability.
- `test_model_edge.py`: bases, user edges, review-state consistency, relationship vocabulary, group rules.
- `test_model_stack_and_requirement.py`: stack roots, requirements, durations, mechanisms, override payloads.
- `test_model_properties_*.py`: typed properties; see [models-properties.md](models-properties.md#tests).
- `test_model_facts_and_fallbacks.py`: external/generic/CodePipeline properties and the node checks for them; quota headroom, offerings, capability versions, metric statuses, sample order and window, `FactRecord` selection.
- `test_model_coverage_and_observation.py`: coverage statuses, pagination, errors, times; freshness policy; exact vs ambiguous observations, candidate sorting.
- `test_model_cost.py`: measured vs estimated quantities, one value per quantity, totals and subtotals, unknown lines, zero reasons, unique keys.
- `test_model_evaluation_and_verification.py`: digest format, input ordering, IaC baseline vs companion; prerequisite evidence and combined status; report labels and pass gates; drills; operator access, including the spec's YAML example.

## Not here yet

- Canonical ID helpers: P0-05.
- Freshness and coverage values (YAML config): P0-06.
- Canonical digests over these models: P9-08.
