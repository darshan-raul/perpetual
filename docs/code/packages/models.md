# `models` package

**Owns:** the shared vocabulary every other package passes around: resources, evidence, edges, stacks, requirements, mechanisms, user edits and status values, plus the records around an evaluation: coverage, observations, cost, evaluation inputs, verification reports, drills and operator access.
**Spec:** §3 (readiness tiers), §5–§8.1, §14.1, §15–§15.4, §16, §19–§20, §23, §24–§24.1, §26–§27.1, §28.1, §30.1, §49, §49.2, §53, §56.3, §59.1, §61.1, §76.1. **Tracker:** P0-04a to P0-04f.
**Depends on:** nothing else in Perpetual (an import rule enforces this); only Pydantic. **Used by:** every other package.

## In one paragraph

These are plain data classes built with Pydantic. They hold no logic beyond validating themselves: they do no I/O and call no other package. Their job is to make bad data impossible to construct. If a fixture, importer or user edit produces something the spec forbids (an "observed" fact with no time window, a quorum of zero, a Region-failure requirement with no target Region), building the model fails immediately with a clear message, instead of the engine computing a wrong answer later.

## Where the models sit

```text
   producers                        models                         consumers
 ─────────────                ──────────────────               ───────────────────
 fixtures (YAML)   ─┐                                     ┌──>  persistence (rows + JSON)
 importers (P1b)   ─┼──build──>  ResourceNode, Edge,  ────┼──>  graph (P0-11, NetworkX)
 collectors (P2)   ─┤            Stack, Mechanism, …      ├──>  rules, simulator, recovery
 user edits (UI)   ─┘            (validated, frozen)      └──>  api / cli (JSON out)

 Anything that reaches the right-hand side has already passed every rule on this page.
```

## Files

| File | What it holds |
|---|---|
| `common.py` | `DomainModel` (the base class) and shared field types `NonEmptyStr`, `Confidence`, `Digest` (`sha256:<hex>`), `SortedIds` (distinct, stored sorted) |
| `resource.py` | `ResourceNode`, `SourceReference` (§15) |
| `evidence.py` | `Evidence`, `SourceType`, `Basis` (§16) |
| `edge.py` | `DependencyEdge`, `DependencyGroup`, `RelationshipType` and their enums (§19–§20) |
| `stack.py` | `Stack`, `StackService`, `StackResource`, `RtoScope` (§24, §24.1) |
| `requirement.py` | `RecoveryRequirement`, `DurationEstimate`, `BufferPolicy`, `DRStrategy`, `FailureScope` (§26, §27, §49) |
| `mechanism.py` | `RecoveryMechanism`, `MechanismKind`: the DR overlay (§27.1) |
| `override.py` | `GraphOverride` and its per-kind payload schemas (§23) |
| `status.py` | Status vocabulary (§30.1): `ResourceState`, `StackState`, `Readiness`, `TargetComparison`, and the evidence label `ReadinessTier` (§3); helpers `worst_state`, `stack_state` |
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

The sections follow the pipeline: first the graph (resources, evidence, edges, groups), then stacks and targets, the DR overlay and user edits, the status vocabulary, and last the records that surround an evaluation.

### The base class

Every model inherits `DomainModel` (`common.py`). Building one runs these steps; any failure raises `ValidationError` and nothing is created:

```text
 dict / kwargs
      │
      ▼
 1. unknown keys?            extra="forbid"   ── "confidance" ──> error
      │
      ▼
 2. field types              str, enums, AwareDatetime (naive time ──> error),
      │                      Confidence 0..1, Digest pattern, SortedIds (sort, reject repeats)
      ▼
 3. @field_validator         one field at a time   (e.g. sort unknown_fields)
      │
      ▼
 4. @model_validator(after)  rules across fields   (e.g. "observed needs a window")
      │
      ▼
 frozen instance             can't be changed; change = model_copy(update=…) -> new object
```

Immutability keeps snapshots and evaluation inputs stable, which later work hashes into digests (§56.3).

### Resources, evidence and edges

A `ResourceNode` is one resource, whatever source it came from. Its `id` is the canonical form `aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER`, built and parsed only through [`ids`](ids.md). `properties` is the raw store, which rules never read; `typed_properties` holds the typed configuration. `planned=True` marks a resource that exists only in a Terraform plan.

A `DependencyEdge` always points **dependent → dependency**, and carries the `Evidence` that supports it:

```text
   ResourceNode                                  ResourceNode
 ┌───────────────────────┐   DependencyEdge     ┌───────────────────────┐
 │ ecs/service/checkout  │ ───────────────────> │ rds/db/checkout       │
 │ typed_properties:     │  connects_to         │ typed_properties:     │
 │   ECSServiceProperties│  criticality=required│   RDSInstanceProperties
 └───────────────────────┘  confidence=0.94     └───────────────────────┘
                                 │
                                 │ evidence[]
                                 ▼
          ┌─────────────────────────────────────────────────────┐
          │ Evidence  source_type=terraform   basis=referenced  │
          │ Evidence  source_type=cloudtrail  basis=observed    │
          │           observed_from..observed_to, count=42      │
          └─────────────────────────────────────────────────────┘
   "checkout needs the database": if the database fails, checkout is impacted.
```

`Evidence.basis` says what kind of fact it is. An edge's `bases` property is computed from its evidence, never stored:

```text
permitted    a connection is allowed      (security group, IAM policy)
referenced   configuration points at it   (Terraform reference, task definition)
observed     traffic was seen             (CloudTrail, flow logs; stored as window + count only)
asserted     a person said so             (user confirmation)
```

`RelationshipType` is the fixed vocabulary from §20. Most relationships mean "needs". Four don't, and `is_operational_requirement` returns False for them, so the impact pass doesn't follow them:

```text
 followed by the impact pass            not requirements
 ───────────────────────────            ──────────────────────────────────────
 depends_on  connects_to  reads_from    contains, member_of   structure only
 writes_to   encrypted_by uses_secret   replicates_to         a primary doesn't fail
 uses_parameter  uses_image routes_to   backed_up_by          because its copy fails;
 resolves_to mounted_from assumes_role                        only the DR overlay
 scheduled_on targets attached_to                             follows these
 deployed_to
```

### Typed properties

Rules read a resource's configuration from `typed_properties`, a model specific to its type (57 type keys: 55 AWS types plus the external and generic fallbacks), never from the raw `properties` dict. Pydantic picks the model from its `type_key`, which matches the `SERVICE/TYPE` part of the resource ID, and the node checks they agree. Missing values come in three kinds (absent, unknown until apply, known empty), and secret values have no field to live in.

Everything about them, including the full list of types, is on its own page: **[models-properties.md](models-properties.md)**.

### Dependency groups

By default every required edge of a dependent is needed. A `DependencyGroup` changes how a set of one dependent's edges combine:

```text
 all      every member is needed            (the default for ungrouped required edges)
 any      one member is enough              (e.g. two interchangeable endpoints)
 quorum   minimum_healthy members needed    (e.g. 2 of 3)

 Example: checkout can read from either cache.

     ecs/service/checkout ──e1──> elasticache/primary  ┐  DependencyGroup
                          ──e2──> elasticache/replica  ┘  mode=any, members=[e1,e2]
                          ──e3──> rds/db/checkout         (ungrouped: needed)

     primary cache fails  -> group still has e2    -> checkout survives
     both caches fail     -> group needs 1, has 0  -> checkout impacted
```

`required_members` gives the number needed. `scope` is `primary` (the dependency graph) or `dr` (the DR overlay). Rules that need the whole file or graph, such as "members start at the dependent" and "an edge is in at most one group per scope", are checked by the fixture validator now and by the graph builder (P0-11) for live data.

### Stacks and requirements

A `Stack` is the unit of DR: one product, one plan, one RTO, one RPO per failure scenario.

```text
 Stack "checkout"   roots: [route53 record]          primary_region: ap-south-1
   │
   ├── StackResource  route53/recordset/api      in_scope
   ├── StackResource  ecs/service/checkout       in_scope
   ├── StackResource  rds/db/checkout            in_scope
   └── StackResource  logs/log-group/checkout    out_of_scope  (logging: shown, never blocking)

 StackService "api"   resource_ids: [ecs/service/checkout]   display only, no targets

 RecoveryRequirement  stack=checkout  failure_scope=region  target_region=ap-south-2
                      RTO 30m  RPO 5m  budget $1200/month  buffer: BufferPolicy
```

Durations use `DurationEstimate` (low / expected / high, each possibly unknown, never zero by default) and `BufferPolicy` (handoff, stack validation, contingency).

### The DR overlay

A `RecoveryMechanism` says how one primary resource is provided in the DR target. The overlay is graph-shaped too: `dr_dependency_ids` and DR-side groups list what recovery needs on the DR side.

```text
     primary Region (ap-south-1)                 DR Region (ap-south-2)
   ┌──────────────────────────┐   mechanism    ┌──────────────────────────────┐
   │ rds/db/checkout          │ ─────────────> │ rds/db/checkout-replica      │
   └──────────────────────────┘ live_counter-  │   needs (dr_dependency_ids): │
                                 part          │   kms/key/dr, rds subnet grp │
                                               └──────────────────────────────┘
 kind:  live_counterpart | restore_from_recovery_point | rebuild_from_iac
        global_service | external | none | unknown
        ("none" is a proven gap; "unknown" means not enough evidence)
```

### User edits

A `GraphOverride` is a user edit. It never changes discovered data; it is applied on top of each scan:

```text
 discovered graph (scan N) ──┐
                             ├──> effective graph used by the engine
 GraphOverride rows ─────────┘
   confirm_edge  reject_edge  add_edge  edit_edge  add_node  edit_node

 rescan: target still exists -> override still applies
         target gone         -> status = orphaned (shown, never dropped)
```

Its `payload` is a plain dict, so it round-trips through YAML, but it is validated against the schema for its `kind`; `typed_payload()` returns the parsed version.

### Status vocabulary

```text
 resource state, worst first:   BLOCKED  >  UNKNOWN  >  RECOVERABLE  >  SURVIVES

 stack state from its required resources (worst one wins):

   worst = BLOCKED      ──> UNAVAILABLE
   worst = UNKNOWN      ──> UNKNOWN
   worst = RECOVERABLE  ─┐
   worst = SURVIVES     ─┴> RECOVERABLE

   no states at all     ──> error (never "SURVIVES": missing evidence is not health)
```

```python
from perpetual.models import ResourceState, stack_state

stack_state([ResourceState.SURVIVES, ResourceState.UNKNOWN])  # StackState.UNKNOWN
```

`Readiness` (READY, DEGRADED, NOT_READY, UNKNOWN) and `TargetComparison` (PASS, FAIL, UNCERTAIN) are the result vocabularies the later stages produce.

### Facts and coverage

Some things the rules need are not resource configuration: a Service Quotas limit and current usage, which instance types a Region offers, whether a feature exists in a Region, a CloudWatch series such as replica lag. They change much faster than configuration, so they live in `facts.py`, apart from resources. Every fact points at the `ScanCoverage` record of the collection that produced it:

```text
 collection run                ScanCoverage                       facts it produced
 ─────────────                 ─────────────────────────────      ──────────────────
 rds inventory, ap-south-2 ──> status=complete, pages done ──┬──> QuotaFact
                               errors=[]                     ├──> MetricFact (lag)
                                                             └──> CapabilityFact

 later stages ask: "is the DR replica there?"

   coverage complete + found       ──> Presence.PRESENT
   coverage complete + not found   ──> Presence.CONFIRMED_ABSENT
   partial / denied / unsupported
   / not_requested                 ──> Presence.UNKNOWN   (never deletes, never proves "none")
```

The model refuses to call a run complete if pagination stopped early or errors were recorded, and a denied run must record its error codes. `FreshnessPolicy` has the shape of the maximum-age settings; the values come from [`config`](config.md) (`freshness.yaml`).

The guiding rule for facts is that **missing data stays unknown**:

- `QuotaFact.headroom` is None unless both the limit and current usage are known. A limit alone proves nothing.
- `MetricFact` separates `ok`, `no_data`, `access_denied` and `error`. Only an `ok` read has samples, and it always has at least one, so "no data" can never read as zero. `latest_sample_at` is what freshness is judged on.
- `CapabilityFact` is `available`, `unavailable` or `unknown`. An answer from a catalog names the catalog version.
- `carried_forward=True` marks history kept for context; it can't satisfy a check by itself.

### Resolved observations

A `ResolvedObservation` is a CloudTrail or flow-log aggregate (window and count, never raw events) with the resources at each end:

```text
 exact:      svc-checkout ──42 calls──> dynamodb/orders
             one resource at each end, cites the evidence that resolved it

 ambiguous:  {svc-checkout, svc-admin} ──42 calls──> dynamodb/orders
             (both use one shared role)
             stored ONCE against the sorted candidate set:
               - the count is not split or multiplied
               - no high-confidence evidence is copied onto either edge
               - a candidate edge backed only by this can't skip review
```

### Workload and cost

A `WorkloadProfile` is a versioned set of quantities for one stack, each with low/expected/high bounds. A measured quantity carries its observation window; an estimate or forecast must record its assumptions. A quantity that isn't listed is unknown, never idle.

A `CostEstimate` is a list of `CostLineItem`s with unique keys, so a shared foundation is counted once. Totals are computed from the lines, so they can't disagree with them:

```text
 line                kind       low    expected   high
 rds-replica         fixed      300    320        350
 ecr-replication     variable   2      4          6
 cross-region-xfer   variable   None   None       None   <- usage unknown

 total(high)                                      None   any unknown line -> unknown total
 total(high, FIXED)                               350    known, but can't stand in for the total
```

A line can be zero only with a `zero_reason`. Budget comparison itself (PASS only when the high bound is within budget) belongs to the costing stage.

### Evaluation inputs

An `EvaluationInput` is the manifest a result was computed from. Approval later signs its digest (P9-08), so any relevant change produces a different manifest and supersedes the approval:

```text
 EvaluationInput "eval-1"   stack=checkout   scenario=region:ap-south-1   evaluated_at
 ├── snapshots      primary_snapshot_id + inventory time, dr_snapshot_id + time, coverage_ids
 ├── graph          graph_revision, override_revision, group_revision
 ├── targets        requirement_id@revision, workload_profile_id@revision
 ├── engine         engine_version, rule_pack_versions
 ├── catalogs       config_digest, duration_catalog_digest, price_catalog_digest
 ├── policy         freshness_policy_version
 ├── inputs_used    assumptions, confirmations, skills, documents (kind, id, digest), sorted
 └── before approval, ONE of:
       iac_baseline       base commit, tree digest, roots (path, workspace, provider Regions,
                          backend lineage/serial, lock-file digest), k8s inventory digest
       companion_design   template digest, input digest
```

It holds identities and digests only: no credentials, state or secret values.

### Verification and prerequisites

A `VerificationReport` keeps four answers apart (§61.1) and is bound to the approved digest, tree digest and saved-plan digest it checked:

```text
                       mode = static_checks_only?
                        │yes                      │no (full: a saved plan was imported)
                        ▼                         ▼
           design_verification can't      static_checks == pass?
           pass  -> "static checks only"   │no -> design can't pass
                                           │yes
                                           ▼
                                  unverified changes?  any prerequisite failed?
                                           │ none of either
                                           ▼
                        design_verification = pass
                        "design verified — deployment and observation pending"
                                           │
                          user deploys; a fresh scan checks each prerequisite
                                           ▼
                  every prerequisite satisfied (with evidence)?  ──no──> observed READY refused
                                           │yes
                                           ▼
                             observed_readiness may be READY
```

A `DeploymentPrerequisite` is something a plan can't prove (an image is present, an initial copy finished, a quota was raised). It names affected resources, owner, required evidence and re-check IDs. Satisfied or failed must cite evidence. `combined_prerequisite_status` picks the worst: failed, then unknown, then pending; no prerequisites is satisfied.

### Drills and readiness tiers

```text
 ReadinessTier (labels on the evidence, not states)

   DESIGN_VERIFIED  the change meets targets on the planned graph      (VerificationReport)
        │ deploy + fresh scan
        ▼
   CONFIGURED       observed READY: DR resources present and healthy   (live evaluation)
        │ game day / ARC execution report / fault injection
        ▼
   PROVEN           recovery was measured                              (DRDrill)
```

`DRDrill` is the §53 schema plus the source (ARC execution report, recovery-script log, fault injection, Resilience Hub test) and optional digests of the scan and design it tested. Unmeasured RTO/RPO stay None.

### Operator access

`OperatorAccessProfile` mirrors the `operator_access` YAML section: identity source with home and replica Regions, a break-glass method, network paths to private endpoints and the Region each ends in, and pinned tool versions. `replica_regions: None` means unknown, `[]` means declared to have none. Typos in the YAML fail because unknown fields are rejected. The loader and OPS-ACCESS rules arrive in P4-04c.

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

- Canonical digests over these models: P9-08.
- `FailureScenario` (P1-04), simulation and recovery-plan models (P1-05 to P1-15), `Finding` (P4-01): with the stages that produce them.
