# Flow: review a fixture graph with overrides

This runnable library example applies all six override kinds. It uses the existing fixture loader and the new override API; graph CLI commands arrive in P0-12. No AWS calls, database writes, or infrastructure changes occur.

## Concrete input and result

The [review-overrides fixture](../../../fixtures/graphs/review-overrides.yaml) starts with two resources and two typed edges from the checkout service to its database. Its six overrides confirm one edge, edit its criticality, reject the other, add a payment-provider dependency and external node, and assign that node to the stack with explicit RTO scope.

Run from the repository root:

```bash
mise exec -- uv run python - <<'PY'
from pathlib import Path

from perpetual.fixtures import load_fixture
from perpetual.graph.overrides import (
    GraphData,
    apply_overrides,
    dump_overrides,
    parse_overrides,
)

fixture = load_fixture(Path("fixtures/graphs/review-overrides.yaml"))
source = GraphData(
    resources=fixture.resources,
    edges=fixture.edges,
    stacks=fixture.stacks,
    stack_resources=fixture.stack_resources,
    stack_services=fixture.stack_services,
)

# Fixture overrides use project_id="fixture" unless explicitly authored otherwise.
text = dump_overrides(fixture.overrides, project_id="fixture")
imported = parse_overrides(text, project_id="fixture")
result = apply_overrides(source, imported, project_id="fixture")

print("Source:", len(source.resources), "resources,", len(source.edges), "edges")
print("Effective:", len(result.graph.resources), "resources,", len(result.graph.edges), "edges")
print("Rejected:", len(result.rejected_edges))
print("Orphans:", len(result.orphan_reasons))
print("Scope source:", result.graph.stack_resources[0].scope_source.value)
assert apply_overrides(source, result.overrides, project_id="fixture") == result
PY
```

Expected output:

```text
Source: 2 resources, 2 edges
Effective: 3 resources, 2 edges
Rejected: 1
Orphans: 0
Scope source: user
```

## The path through the code

```text
 review-overrides.yaml
     |
 fixtures.load_fixture -> validated source records and GraphOverride records
     |
 dump_overrides -> versioned YAML -> parse_overrides -> validated instructions
     |
 apply_overrides
     +-> ordered_overrides: validate projects/targets, sort (created_at, id)
     +-> WorkingGraph: deep-copy source records and build ID lookups
     +-> add_node: establish the external payment-provider node
     +-> confirm/edit/reject/add edge: update working records and assertions
     +-> edit_node: add stack membership and explicit user scope
     +-> validate references, recompute active/orphaned statuses
     v
 OverrideResult: effective graph + retained rejected records + review diagnostics
```

See [apply.py](../../../apps/api/perpetual/graph/overrides/apply.py) for the orchestration, [edges.py](../../../apps/api/perpetual/graph/overrides/edges.py) for assertions and merging, and [nodes.py](../../../apps/api/perpetual/graph/overrides/nodes.py) for resource and membership changes. The [package page](../packages/graph.md) explains the target formats and each result field.

## Failure paths and what the result establishes

A missing referenced target makes its instruction an orphan, retained for future replay. A malformed target or a foreign project's override raises `OverrideError`; no source object is modified. Deleting the payment node's addition from the input leaves its added edge and membership edit orphaned instead of creating a dangling dependency.

On rescans, provide fresh source records and the original rejected source edges through `historical_edges`. Changed evidence can then be linked back to the old rejection. Missing historical context is reported, never guessed.

The result is a reviewed set of graph records, not a readiness verdict. The external node's recovery posture is still `UNKNOWN`. Traversal, simulation, and readiness checks come in later tasks.

## Tests

[Graph override tests](../../../apps/api/tests/graph/test_overrides.py) exercise this fixture and rescan behavior. [YAML tests](../../../apps/api/tests/graph/test_override_yaml.py) cover serialization and import failures. [The persistence test](../../../apps/api/tests/graph/test_override_persistence.py) shows the separate transaction boundary for saving user decisions and statuses.
