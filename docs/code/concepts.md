# Concepts for reading the code

Start here if you know basic Python but are new to this project. The examples use the existing [minimal fixture](../../fixtures/graphs/minimal.yaml): an ECS application service that depends on an RDS database.

## The domain vocabulary

| Term | Meaning here | Where to read more |
|---|---|---|
| Resource / node | One thing the application needs, such as a service or database | [Models](packages/models.md) |
| Canonical ID | A consistent resource name including its provider, account, Region, and type; for example `aws://123456789012/ap-south-1/rds/db/checkout` | [IDs](packages/ids.md) |
| Edge / dependency | A link from the thing needing help to the thing it needs: service → database | [Models](packages/models.md) |
| Evidence | A recorded reason to believe a dependency exists, such as a Terraform reference | [Evidence](packages/evidence.md) |
| Confidence / correlation group | How strongly evidence supports a link; related evidence shares a group so it is not counted repeatedly | [Evidence](packages/evidence.md) |
| Fingerprint | A stable hash of the dependency claim and its material evidence; collection timestamps do not change it | [Evidence](packages/evidence.md) |
| Stack | The resources needed to serve one product, evaluated together | [Models](packages/models.md) |
| RTO / RPO | Targets for recovery time and tolerable loss of recent data. Target models exist; the calculators are still planned | [Architecture](architecture.md) |
| Recovery mechanism / overlay | A way to provide a resource in the recovery Region; the overlay describes these alternatives alongside the dependency graph | [Models](packages/models.md) |
| Override | A user's correction or confirmation, stored separately from discovered data. Its model and storage exist; applying it is P0-10 | [Models](packages/models.md) |
| Fixture | A small saved input used to exercise code without calling AWS | [Fixtures](packages/fixtures.md) |
| Snapshot | A captured set of resources and relationships; published snapshots cannot be changed through the repository | [Persistence](packages/persistence.md) |
| UNKNOWN | There is not enough evidence to decide. It must not be treated as success or zero cost/time | [Models](packages/models.md) |

## Python and library features you will meet

**Type hints** describe intended values. `list[str]` means a list of strings; `str | None` allows a string or no value. Mypy checks these hints without running the application. Hints alone do not validate runtime input.

**Pydantic models** are classes with runtime validation. `Model.model_validate(data)` reads a dictionary and checks its fields. `model_dump(mode="json")` turns a model into data suitable for JSON storage. A validator checks a rule, such as requiring an observation window for observed traffic. See [models/common.py](../../apps/api/perpetual/models/common.py) and [models/evidence.py](../../apps/api/perpetual/models/evidence.py).

**Annotated fields** attach rules to a type. `Annotated[float, Field(ge=0.0, le=1.0)]` means a float constrained to 0 through 1 when Pydantic validates it. **Enums** name a fixed set of choices; `Basis.REFERENCED` names the value `"referenced"`.

**Frozen models and dataclasses** prevent ordinary reassignment of fields. This helps preserve records, but is not deep immutability: nested lists or dictionaries may still be mutable. Repository checks separately protect published snapshots. A dataclass is a convenient way to define a small record; it does not automatically provide Pydantic validation.

**Decorators** are the `@...` lines above a function or class. They register or modify it. For example, `@fixtures_app.command("validate")` registers a CLI command with Typer, while `@model_validator(mode="after")` registers a Pydantic check after field validation.

**Serialization** means converting objects to a format that can be saved or exchanged, such as JSON. A **schema** describes valid fields and values. A **migration** changes database structure as the application evolves.

**Repository and session** are database terms here. `ProjectRepository` groups reads and writes for one project; a SQLAlchemy session manages database work. Domain models describe application facts; SQLAlchemy row classes describe their storage. See [persistence](packages/persistence.md).

**Deterministic hashing** produces the same digest from the same meaningful input. Sorting and consistent JSON formatting prevent accidental differences caused by input order. A fingerprint is an identity check, not proof that the underlying claim is true.

## Following control flow and storage code

**Comprehensions** collect values in one expression: `[item.id for item in items]` is a loop that builds a list of IDs. A set comprehension removes duplicates. We keep these for simple collection steps and use separate statements when several decisions are involved.

**Generators** produce values as they are needed. A function using `yield` pauses after each value and resumes when the caller asks for another. `_evidence_holders` in the fixture loader yields dictionaries holding evidence, so the caller can apply the same timestamp default to each. `yield from` forwards the values from another iterator. `Iterator[str]` describes this sequence of strings; it is not a stored list.

**Sort keys and lambdas** tell Python how to compare items. `max(items, key=lambda state: _SEVERITY[state])` selects the state with the highest severity number. A lambda is a small unnamed function. More involved ordering, such as fingerprint sorting, uses a named helper with explicit steps.

**Dictionary lookup helpers** keep grouped records together. `groups.setdefault(name, [])` returns the list under `name`, inserting an empty list if that key is missing. Appending to that result adds a member to the group. `dict.fromkeys(ids)` removes repeated IDs while preserving their first-seen order; the repository uses this before batching queries.

**Dynamic field access** uses `getattr(record, field_name)` when the field name comes from data. For example, the cost model reads `low_usd`, `expected_usd`, or `high_usd` using its selected bound. The typed-properties base checks field names against the model's declared fields before treating them as unknown.

**Transactions and context managers** use `with` to guarantee cleanup. `with transaction(factory) as session:` commits database work if the block succeeds and rolls it back if an exception escapes. `session.flush()` sends pending rows to the database within that transaction so IDs and constraint checks are available; it does not commit the transaction. See [the snapshot walkthrough](flows/snapshot-round-trip.md).

**Generic return types** connect an input type to an output type. The repository's `_load(..., model: type[M], ...) -> list[M]` means that asking for `ResourceNode` models returns a list of `ResourceNode` objects. This helper keeps filtering by project and snapshot consistent across tables. The generic type is for the type checker; `model_validate` performs the actual runtime checks.

## Follow a real example

Read [fixture validation](flows/fixtures-validate.md), then [fixture evidence scoring](flows/fixture-evidence.md). The first is an existing CLI command; the second manually connects existing library functions. Add concepts here as new implementation introduces them; use dedicated pages when a topic needs more space.
