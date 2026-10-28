# `ids` package

**Owns:** building and parsing canonical resource IDs.
**Spec:** §15, §15.1, §15.2. **Tracker:** P0-05.
**Depends on:** nothing else in Perpetual (an import rule enforces this); only the standard library. **Used by:** normalizers, importers, fixtures and the graph, as they are built.

## In one paragraph

Every resource, edge, override and piece of evidence is keyed on a resource ID, and digests are computed over them. An ID that differs by one character never matches, so the same resource must always get the same string. This package is the only place IDs are put together or taken apart. Building is strict: a bad part raises `InvalidResourceIdError` instead of producing an ID that would silently never match. For every valid ID, `str(parse(x)) == x`.

## Formats

```text
live       aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER
global     aws://ACCOUNT/global/SERVICE/TYPE/IDENTIFIER
planned    aws://ACCOUNT/REGION/SERVICE/TYPE/tf:<root_id>:<workspace>:<terraform_address>
external   external://SERVICE/NAME
```

- `ACCOUNT` is 12 digits. `REGION` is an AWS Region in any partition (`ap-south-1`, `us-gov-west-1`, `cn-north-1`) or `global`.
- `SERVICE/TYPE` is the resource's type key, the same one that picks its typed properties model (`rds/db`, `elasticfilesystem/file-system`). Lowercase letters, digits and `-`.
- `IDENTIFIER` is the last part and may contain `/`: log group names do (`aws://…/logs/log-group//aws/ecs/checkout`). Parsing splits only the first four segments. Control characters are rejected.
- A **planned** resource exists only in a Terraform plan and has no ARN yet, so its identifier is its source address (§15.1). The address goes last because `for_each` keys can contain `:`; root ID and workspace cannot. A live identifier may not start with `tf:`, so the two can't be confused.
- An **external** node is a dependency Perpetual can't discover (§15.2). The spec gives no format for it; this one was added in P0-05 (see the decision log).

## Using it

```python
from perpetual.ids import aws_id, global_id, planned_id, external_id, parse_aws

aws_id("123456789012", "ap-south-1", "rds", "db", "prod-mysql")
# 'aws://123456789012/ap-south-1/rds/db/prod-mysql'

rid = parse_aws(planned_id("123456789012", "ap-south-2", "rds", "db",
                           root_id="infra-prod", workspace="default",
                           address="module.db.aws_db_instance.this"))
rid.is_planned        # True
rid.planned_address   # PlannedAddress(root_id='infra-prod', workspace='default', address='module.db...')
rid.type_key          # 'rds/db'
```

`parse` returns an `AwsResourceId` or an `ExternalResourceId` (frozen dataclasses, so they can be dict keys and set members). `parse_aws` also rejects external IDs, and `is_valid` returns a bool instead of raising.

## Not here

- Checking that a `ResourceNode`'s `id` agrees with its `account_id`, `region`, `service` and `resource_type`. `models` may not import `ids`, so the fixture validator (P0-08) and graph build (P0-11) do this.
- Re-keying a planned resource to its live ID when a scan finds it, and matching by ARN: identity resolution (P1b).
- Which services are global. The ID accepts `global` for any service; normalizers decide.

## Tests

`apps/api/tests/ids/test_canonical_ids.py`: the spec's examples round-trip; live, global, planned and external IDs; identifiers with slashes; addresses with colons; a live identifier that looks planned; malformed planned parts; invalid schemes, accounts, Regions, names and control characters; other partitions; IDs as hashable values.
