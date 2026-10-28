"""Load and check fixtures (spec §90.1, §104).

Loading runs in three steps, and every problem found is reported together, each
with the path to the bad value, so a fixture author fixes them in one pass:

1. read the YAML;
2. fill in derived fields (from canonical IDs and `captured_at`) and refuse any
   authored value that contradicts its ID;
3. validate the domain models, then cross-references (`validate.py`).
"""

import copy
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from perpetual.fixtures.schema import Fixture
from perpetual.ids import AwsResourceId, InvalidResourceIdError, parse

DERIVED_FIELDS: dict[str, tuple[str, ...]] = {
    "ResourceNode": ("provider", "service", "resource_type", "discovered_at"),
    "Evidence": ("collected_at",),
    "GraphOverride": ("project_id", "created_at"),
}
"""Fields the loader can fill in, per model. The JSON Schema marks them optional."""

FIXTURE_PROJECT_ID = "fixture"
"""The project ID given to fixture overrides that don't name one."""

FIXTURES_DIR_ENV = "PERPETUAL_FIXTURES_DIR"


@dataclass(frozen=True)
class FixtureIssue:
    path: str
    """Where in the file, e.g. resources[2].region."""
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


class FixtureError(ValueError):
    def __init__(self, source: str, issues: list[FixtureIssue]) -> None:
        self.source = source
        self.issues = issues
        super().__init__(f"{source}: {len(issues)} problem(s)\n" + "\n".join(map(str, issues)))


def load_fixture(path: Path) -> Fixture:
    """Load, expand and fully validate one fixture file. Raises FixtureError."""
    from perpetual.fixtures.validate import check_references  # noqa: PLC0415 (cycle)

    source = str(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise FixtureError(source, [FixtureIssue("", f"can't read: {error}")]) from error
    except yaml.YAMLError as error:
        raise FixtureError(source, [FixtureIssue("", f"not valid YAML: {error}")]) from error
    fixture = parse_fixture(raw, source)
    issues = check_references(fixture)
    if issues:
        raise FixtureError(source, issues)
    return fixture


def parse_fixture(raw: object, source: str = "<fixture>") -> Fixture:
    """Expand derived fields and validate the models (no cross-reference checks)."""
    if not isinstance(raw, dict):
        raise FixtureError(source, [FixtureIssue("", "a fixture is a mapping at the top level")])
    data, issues = expand(raw)
    try:
        fixture = Fixture.model_validate(data)
    except ValidationError as error:
        issues += [_issue(item) for item in error.errors()]
        raise FixtureError(source, issues) from error
    if issues:
        raise FixtureError(source, issues)
    return fixture


def expand(raw: dict[str, Any]) -> tuple[dict[str, Any], list[FixtureIssue]]:
    """Fill in derived fields. Returns the expanded data and ID contradictions."""
    data = copy.deepcopy(raw)  # never change the caller's data
    issues: list[FixtureIssue] = []
    captured_at = data.get("captured_at")

    resources = data.get("resources")
    if isinstance(resources, list):
        expanded = []
        for index, item in enumerate(resources):
            if isinstance(item, dict):
                issues += _expand_resource(item, captured_at, f"resources[{index}]")
            expanded.append(item)
        data["resources"] = expanded

    for holder in _evidence_holders(data):
        evidence = holder.get("evidence")
        if isinstance(evidence, list):
            holder["evidence"] = [_default(item, "collected_at", captured_at) for item in evidence]

    overrides = data.get("overrides")
    if isinstance(overrides, list):
        data["overrides"] = [
            _default(_default(item, "project_id", FIXTURE_PROJECT_ID), "created_at", captured_at)
            for item in overrides
        ]
    return data, issues


def resolve_fixture(name_or_path: str, start: Path | None = None) -> Path:
    """A fixture file from a path, or from a name looked up in `fixtures/graphs/`.

    The fixtures directory is `$PERPETUAL_FIXTURES_DIR`, or the nearest `fixtures/`
    directory at or above `start` (the current directory by default).
    """
    candidate = Path(name_or_path)
    if candidate.suffix in {".yaml", ".yml"} or candidate.exists():
        return candidate
    for base in _fixture_dirs(start or Path.cwd()):
        path = base / "graphs" / f"{name_or_path}.yaml"
        if path.exists():
            return path
    raise FixtureError(name_or_path, [FixtureIssue("", "no fixture with this name or path")])


def fixture_names(start: Path | None = None) -> list[str]:
    for base in _fixture_dirs(start or Path.cwd()):
        graphs = base / "graphs"
        if graphs.is_dir():
            return sorted(path.stem for path in graphs.glob("*.yaml"))
    return []


# --- helpers ---------------------------------------------------------------------


def _expand_resource(item: dict[str, Any], captured_at: object, path: str) -> list[FixtureIssue]:
    """Fill in one resource's derived fields in place; report contradictions."""
    if "discovered_at" not in item and captured_at is not None:
        item["discovered_at"] = captured_at
    resource_id = item.get("id")
    if not isinstance(resource_id, str):
        return []  # model validation reports the missing or bad id
    try:
        parsed = parse(resource_id)
    except InvalidResourceIdError as error:
        return [FixtureIssue(f"{path}.id", str(error))]

    derived: dict[str, object]
    if isinstance(parsed, AwsResourceId):
        derived = {
            "provider": "aws",
            "account_id": parsed.account_id,
            "region": parsed.region,
            "service": parsed.service,
            "resource_type": parsed.resource_type,
            "planned": parsed.is_planned,
        }
        if parsed.planned_address is not None:
            derived["terraform_address"] = parsed.planned_address.address
    else:
        # External nodes (spec §15.2): the type and Region are the author's to give.
        derived = {"provider": "external", "service": parsed.service}

    issues = []
    for field, value in derived.items():
        if field not in item:
            item[field] = value
        elif item[field] != value:
            issues.append(
                FixtureIssue(f"{path}.{field}", f"is {item[field]!r} but the id says {value!r}")
            )
    return issues


def _evidence_holders(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every model in the fixture that carries an evidence list."""
    for key in ("edges", "groups", "mechanisms"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            yield item
            nested = item.get("dependency_groups")
            if isinstance(nested, list):
                yield from (group for group in nested if isinstance(group, dict))


def _default(item: object, field: str, value: object) -> object:
    if isinstance(item, dict) and field not in item and value is not None:
        return {**item, field: value}
    return item


def _issue(error: Any) -> FixtureIssue:
    path = ""
    for part in error["loc"]:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return FixtureIssue(path, error["msg"])


def _fixture_dirs(start: Path) -> Iterator[Path]:
    configured = os.environ.get(FIXTURES_DIR_ENV)
    if configured:
        yield Path(configured)
        return
    for directory in (start.resolve(), *start.resolve().parents):
        if (directory / "fixtures").is_dir():
            yield directory / "fixtures"
            return
