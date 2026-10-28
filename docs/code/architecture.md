# Architecture as built

The target pipeline is in IMPL_PLAN §3.1. This page shows how much of it exists and how the existing pieces connect. Updated with every task that changes connections.

## The pipeline, and what exists

```text
 [x] built   [~] started   [ ] not yet

 [ ] collectors ─┐
 [ ] importers  ─┼─> [ ] normalization ─> [ ] evidence (edges) ─> [ ] graph (+ overrides)
 [x] fixtures   ─┘        (a fixture already holds normalized models, so it skips ahead ──┘)

 ─> [ ] stacks ─> [ ] rules (findings, DR overlay) ─> [ ] simulator ─> [ ] recovery (DAG, RTO, RPO)
 ─> [ ] optimizer + costing ─> [ ] DR spec ─> [ ] iac (companion Terraform, edits) ─> [ ] runbooks

 underneath everything:   [x] models   [x] ids   [x] config   [x] persistence
 on top:                  [~] cli      [ ] api
```

| Stage | Package | State |
|---|---|---|
| Shared vocabulary | `models` | **Built** (P0-04a to P0-04f): resources with typed properties for all first-slice AWS types plus external/generic fallbacks (57 type keys); quota, capability and metric facts, evidence, edges, groups, overrides, stacks, requirements, mechanisms, status vocabulary; scan coverage, resolved observations, workload/cost, evaluation inputs, verification reports, drills, operator access |
| Resource IDs | `ids` | **Built** (P0-05): build and parse live, global, planned (`tf:`) and external IDs |
| Configuration | `config` | **Built** (P0-06): versioned YAML defaults (evidence weights, review threshold, scoring, RTO scope, buffer, freshness, limits) with project overrides |
| Storage | `persistence` | **Built** (P0-07): 17 tables, project-scoped repository, frozen published snapshots, initial Alembic migration tested on SQLite and PostgreSQL |
| Fixtures | `fixtures` | **Built** (P0-08): format v1 in `fixtures/graphs/`, loader filling fields from canonical IDs, cross-reference checks, JSON Schema |
| Command line | `cli` | **Started** (P0-08): `perpetual fixtures validate` and `schema` |
| Everything else | — | Empty subpackages with a docstring; layer rules already enforced |

## Who imports whom (today)

```text
                 ┌───────┐
                 │  cli  │  perpetual fixtures validate | schema
                 └───┬───┘
                     │
                 ┌───▼──────┐
                 │ fixtures │  YAML -> models, cross-references
                 └─┬──────┬─┘
                   │      │
          ┌────────▼┐   ┌─▼────┐      ┌─────────────┐     ┌────────┐
          │   ids   │   │models│ ◄────┤ persistence │     │ config │
          └─────────┘   └──────┘      └─────────────┘     └────────┘
           stdlib only   Pydantic      SQLAlchemy,         Pydantic,
                         only          Alembic             PyYAML

 models, ids and config import nothing else from Perpetual (an import rule enforces it).
 Nothing imports cli. config is not wired in yet: evidence combination (P0-09) is its first user.
```

## How data moves today

```text
 fixtures/graphs/*.yaml
        │  fixtures.load_fixture  (ids fill derived fields; models validate; references checked)
        ▼
 Fixture { resources, edges, groups, mechanisms, stacks, requirements, overrides, facts, … }
        │                                                   (models: frozen, validated)
        │  persistence.ProjectRepository.save_*   (not yet called by any command)
        ▼
 SQLite: snapshot rows (lookup columns + JSON payload)
        │  ProjectRepository.resources()/edges()/…  (payload -> model_validate again)
        ▼
 the same models, ready for the graph builder (P0-11)

 config.load_config() -> Config  (weights, thresholds, limits)  -> evidence, rules, recovery later
```

## How the models connect

All links are by ID, not object reference. Models stay small and immutable, and the graph package (P0-11) resolves IDs into a NetworkX graph.

```text
 THE GRAPH
                    ResourceNode  <──── SourceReference (where it was seen)
                        │  typed_properties: ResourceProperties (picked by type_key, e.g. ecs/service)
                        ▲   ▲
       from_resource_id │   │ to_resource_id
                        │   │
                   DependencyEdge  ────> Evidence (basis: permitted | referenced | observed | asserted)
                        ▲
        member_edge_ids │
                   DependencyGroup (all | any | quorum; primary or dr)

   ResolvedObservation ── candidate resource-ID sets ──> ResourceNode   (exact | ambiguous)

 THE STACK AND ITS TARGETS
   Stack ──── StackResource (membership + RTO scope) ──── ResourceNode
     └──── StackService (display only; no targets)
   RecoveryRequirement (per stack + failure scope: target RTO/RPO/budget/Region)
        uses DurationEstimate, BufferPolicy, DRStrategy;  workload_profile_id ──> WorkloadProfile

 THE DR OVERLAY AND USER EDITS
   RecoveryMechanism (how a primary resource is provided in the DR Region)
        dr_dependency_ids, DR-side DependencyGroups, counterpart_resource_id ──> ResourceNode
   GraphOverride (a user edit, applied on top of each scan; never edits discovered data)

 WHAT THE ENGINE KNOWS, AND HOW WELL
   ScanCoverage ◄── coverage_id ── Facts (Quota, InstanceTypeOffering, Capability, Metric)
   FreshnessPolicy (values from config)

 AROUND AN EVALUATION
   EvaluationInput ── snapshot ids, revisions, versions, catalog digests, inputs used,
                      IaC baseline | companion design
   CostEstimate (lines -> totals; unknown stays unknown) ── workload_profile_id
   VerificationReport ── approved/tree/plan digests, DeploymentPrerequisites, observed readiness
   DRDrill ── evaluation/design digests          OperatorAccessProfile (perpetual.yaml)
```

## Layer rules

Which package may import which is enforced by import-linter on every lint run; see [tooling.md](tooling.md#import-rules). In short: `models`, `ids` and `config` sit at the bottom; collectors only collect; the engine never imports LLM code; nothing imports `api` or `cli`.

## Next connections

P0-09 adds `evidence` (combination with correlation groups, using `config`) and fingerprints; P0-10 graph overrides; P0-11 the NetworkX graph from a snapshot; P0-12 `perpetual graph --fixture`, the first command that runs the engine on a fixture.
