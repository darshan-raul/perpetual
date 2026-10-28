# Flow: `perpetual fixtures validate`

The first command that crosses packages. It reads fixture files and proves each one would load into the engine exactly as a scan would. Packages involved: [`cli`](../packages/cli.md) → [`fixtures`](../packages/fixtures.md) → [`ids`](../packages/ids.md) and [`models`](../packages/models.md).

## The whole path

```text
 $ uv run perpetual fixtures validate checkout-demo
      │
      ▼
 pyproject [project.scripts] perpetual = "perpetual.cli:main"
      │
 cli/app.py         main() -> app()            Typer parses: group "fixtures", command "validate"
      │
 cli/fixtures.py    validate(fixtures=["checkout-demo"])
      │   no names given? -> fixture_names()  (every *.yaml in fixtures/graphs)
      │
      │   for each name:
      ▼
 fixtures/loader.py resolve_fixture("checkout-demo")
      │   a path or *.yaml?               -> use it
      │   else $PERPETUAL_FIXTURES_DIR or nearest fixtures/ above cwd
      │                                    -> fixtures/graphs/checkout-demo.yaml
      ▼
 fixtures/loader.py load_fixture(path)
      │
      ├─ yaml.safe_load(text)
      │
      ├─ expand(raw)                         (deep copy)
      │     for each resource:
      │        ids/canonical.py parse(id) ──> AwsResourceId / ExternalResourceId
      │        fill provider, account, region, service, type, planned
      │        contradiction -> FixtureIssue("resources[i].region", "...")
      │     default timestamps, override project
      │
      ├─ Fixture.model_validate(data)        fixtures/schema.py
      │     models/*: ResourceNode, DependencyEdge, Evidence, Stack, …
      │     every model rule runs (see models.md); errors -> FixtureIssue with path
      │
      └─ check_references(fixture)           fixtures/validate.py
            unique ids · edge endpoints · group rules · stack membership · coverage ids
      │
      ▼
 back in cli/fixtures.py
      ok   -> "ok   fixtures/graphs/checkout-demo.yaml (12 resources, 14 edges)"   stdout
      fail -> "FAIL …(3 problem(s))" + one line per issue                         stderr
      │
      ▼
 exit code   0 all valid   1 any fixture failed   2 no fixtures found
```

## What each layer is responsible for

```text
 cli        arguments, printing, exit codes          (no rules)
 fixtures   file format, defaults, cross-references  (rules that need the whole file)
 ids        what a valid resource ID is              (rules about one ID string)
 models     what a valid resource, edge, stack is    (rules about one object)
```

Keeping the rules in the lowest layer that can check them means the same rules protect every other entry point: an importer (P1b), a collector (P2) and the API all build the same `models` objects and so pass the same checks.

## Try it

```bash
uv run perpetual fixtures validate                          # every fixture in fixtures/graphs
uv run perpetual fixtures validate fixtures/graphs/minimal.yaml
```

Break something in a copy of `minimal.yaml` (point an edge at a missing resource, or give a resource the wrong Region) and run it again to see the issue paths.

## Tests

`apps/api/tests/cli/test_cli_fixtures.py` runs this path end to end; `apps/api/tests/fixture_format/` covers each step.
