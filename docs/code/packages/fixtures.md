# `fixtures` package

**Owns:** fixture format v1: the schema, the loader that fills in derived fields, and the cross-reference checks.
**Spec:** §15, §15.1, §15.2, §19.1, §23, §90.1, §104. **Tracker:** P0-08.
**Depends on:** `models`, `ids`; PyYAML. **Used by:** the CLI (`perpetual fixtures validate|schema`), tests, and from P0-11 the graph builder.

## In one paragraph

A fixture is one YAML file that holds a whole scene (resources, edges, dependency groups, observations, the DR overlay, stacks, requirements, user overrides, facts and coverage) so the engine can run with no AWS, credentials or collectors. It holds the domain models themselves, so a fixture passes exactly the validation live data passes. Loading reports **every** problem at once, each with its path (`edges[0].to_resource_id: no resource '…'`), so an author fixes a file in one pass.

## Where fixtures live

```text
fixtures/
  graphs/<name>.yaml           fixture files; `--fixture NAME` finds them here
  schema/fixture-v1.schema.json  JSON Schema for editors (kept current by a test)
```

`resolve_fixture` takes a path, or a name looked up in `graphs/` under `$PERPETUAL_FIXTURES_DIR` or the nearest `fixtures/` directory at or above the current directory. `fixtures/graphs/minimal.yaml` is a small, commented example; the canonical demo fixtures arrive in P0-13.

## The format

```yaml
format: perpetual-fixture
version: 1
name: minimal
captured_at: 2026-10-28T12:00:00Z    # default for missing discovery/collection times
resources:
  - id: aws://123456789012/ap-south-1/rds/db/checkout   # provider, account, Region,
    name: checkout                                       # service, type come from the id
edges: [...]          groups: [...]        observations: [...]
mechanisms: [...]     # the DR overlay
stacks: [...]         stack_resources: [...]   stack_services: [...]
requirements: [...]   overrides: [...]     facts: [...]   coverage: [...]
```

Every collection is optional. Each item is the matching domain model (`ResourceNode`, `DependencyEdge`, …), with unknown keys rejected.

## Loading, in three steps

```text
 load_fixture(path)
   │
   ├─ 1. read ──────── path.read_text + yaml.safe_load
   │                   can't read / bad YAML ──────────────────────────────┐
   │                                                                       │
   ├─ 2. expand ────── deep copy, then per resource:                       │
   │       id ──ids.parse──> provider, account_id, region, service,        │
   │                         resource_type, planned, terraform_address     │
   │       authored value ≠ derived value ──> issue "resources[i].field"   │ issues
   │       missing times ──> captured_at;  overrides ──> project "fixture" │ collected,
   │                                                                       │ not thrown
   ├─ 3a. models ───── Fixture.model_validate(expanded)                    │ one by one
   │       every ValidationError item ──> issue with its path              │
   │                                                                       │
   ├─ 3b. references ─ check_references(fixture)                           │
   │       dangling ids, duplicate ids, group rules, membership ──> issues │
   │                                                                       ▼
   └─ no issues ──> Fixture (frozen models)     any issues ──> FixtureError(source, [all issues])
```

Issues from steps 2 and 3a are reported together. Step 3b needs valid models, so it runs only when they pass; fix those first, then any reference problems appear.

What expansion does to one resource:

```text
 authored                                       after expand()
 ──────────────────────────────────────         ──────────────────────────────────────
 - id: aws://123456789012/ap-south-1/           - id: aws://123456789012/ap-south-1/
         rds/db/checkout                                rds/db/checkout
   name: checkout                                 name: checkout
                                                  provider: aws
                                                  account_id: "123456789012"
                                                  region: ap-south-1
                                                  service: rds
                                                  resource_type: db
                                                  planned: false
                                                  discovered_at: <captured_at>
```

Step by step:

1. **Read** the YAML (`load_fixture`); a missing file or bad YAML is one issue.
2. **Expand** (`expand`, on a deep copy, so the caller's data never changes):
   - resources: `provider`, `account_id`, `region`, `service`, `resource_type` and `planned` from the canonical ID, plus `terraform_address` for a planned ID. External IDs give only provider and service; the author supplies the type. **An authored value that contradicts the ID is an issue**: this is where node-vs-ID consistency is checked, because `models` may not import `ids`.
   - `discovered_at` and evidence `collected_at` default to `captured_at`; overrides default to project `fixture` and `captured_at`.
3. **Validate**: the domain models (`parse_fixture`), then cross-references (`check_references`).

`DERIVED_FIELDS` lists the fields step 2 fills in. `fixture_json_schema()` marks them optional, so editors accept the short form.

## Cross-reference rules

| Rule | Why |
|---|---|
| IDs are unique in each collection | Everything else is keyed on them |
| Edge endpoints, mechanism primaries, counterparts and DR dependencies, observation candidates, stack roots, members and service resources exist | A dangling reference would silently drop out of the graph |
| Group members are existing edges that start at the group's dependent, and an edge is in at most one group per scope | A group says how one dependent's edges combine (§19.1) |
| `stack_resources` name an existing stack and a resource in that stack; stacks name existing services; requirements name existing stacks | Membership must agree everywhere |
| Facts name existing coverage records | Facts reference their coverage (§76.1) |
| Overrides are **not** checked against resources | An override whose target is gone is orphaned, a valid state (§23) |

The graph builder (P0-11) will enforce the group rules on live data too.

## Tests

`apps/api/tests/fixture_format/test_fixture_loader.py`: every repository fixture is valid; ID-derived fields; contradictions; planned, global and external IDs; bad IDs; override defaults; raw data unchanged; model errors collected with paths; header and unknown keys; bad files; each cross-reference rule; orphaned overrides allowed; lookup by name, path and environment variable; the committed schema is current; derived fields optional in the schema.
