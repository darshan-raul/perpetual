# Architecture as built

The target pipeline is in IMPL_PLAN §3.1. This page shows how much of it exists and how the existing pieces connect. Updated with every task that changes connections.

## The pipeline, and what exists

```text
collectors / importers  ->  normalization  ->  evidence (edges)  ->  graph (+ overrides)
        ->  stacks  ->  rules (findings, DR overlay)  ->  simulator  ->  recovery (DAG, RTO, RPO)
        ->  optimizer + costing  ->  DR spec  ->  iac (companion Terraform, suggested edits)
        ->  runbooks (runbook, scripts, ARC plan)
```

Every stage passes **models** to the next. That is why `models` is built first and imports nothing else from Perpetual: every other package depends on it.

| Stage | Package | State |
|---|---|---|
| Shared vocabulary | `models` | **Built** (P0-04a): resources, evidence, edges, groups, overrides, stacks, requirements, mechanisms, status vocabulary |
| Everything else | — | Empty subpackages with a docstring; layer rules already enforced |

## How the built pieces connect

```text
                    ResourceNode  <---- SourceReference (where it was seen)
                        ^   ^
       from_resource_id |   | to_resource_id
                        |   |
                   DependencyEdge  ----> Evidence (basis: permitted | referenced | observed | asserted)
                        ^
        member_edge_ids |
                   DependencyGroup (all | any | quorum; primary or dr)

  Stack ---- StackResource (membership + RTO scope) ---- ResourceNode
    \---- StackService (display only; no targets)

  RecoveryRequirement (per stack + failure scope: target RTO/RPO/budget/Region)
        uses DurationEstimate, BufferPolicy, DRStrategy

  RecoveryMechanism (DR overlay: how a primary resource is provided in the DR Region)
        has dr_dependency_ids and DR-side DependencyGroups

  GraphOverride (a user edit, applied on top of each scan; never edits discovered data)
```

These links are by ID, not by object reference. Models stay small and immutable, and the graph package (P0-11) resolves IDs into a NetworkX graph.

## Layer rules

Which package may import which is enforced by import-linter on every lint run; see [tooling.md](tooling.md#import-rules). In short: `models`, `ids` and `config` sit at the bottom; collectors only collect; the engine never imports LLM code; nothing imports `api` or `cli`.

## Next connections

P0-04b to P0-04f add typed resource properties and evaluation models to `models`. P0-05 to P0-12 add IDs, config, persistence, fixtures, evidence combination, overrides, the graph and the first CLI command, which will be the first [flow](README.md#flows).
