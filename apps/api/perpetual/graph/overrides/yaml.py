"""Versioned override YAML and idempotent import merging, with no database writes."""

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from perpetual.graph.overrides.types import OverrideError
from perpetual.graph.overrides.validation import ordered_overrides
from perpetual.models import DomainModel, GraphOverride, NonEmptyStr


class OverrideDocument(DomainModel):
    format: Literal["perpetual-overrides"] = "perpetual-overrides"
    version: Literal[1] = 1
    project_id: NonEmptyStr
    overrides: list[GraphOverride] = Field(default_factory=list)


def dump_overrides(overrides: Iterable[GraphOverride], *, project_id: str) -> str:
    """Export all records, including orphans, in deterministic order as safe YAML."""
    try:
        document = OverrideDocument(
            project_id=project_id, overrides=ordered_overrides(project_id, overrides)
        )
        return yaml.safe_dump(document.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    except ValueError as error:
        raise OverrideError(str(error)) from error


def parse_overrides(text: str, *, project_id: str) -> list[GraphOverride]:
    """Read a versioned document; reject malformed input and foreign project IDs."""
    try:
        data = yaml.safe_load(text)
        # Require an explicit format/version in files, even though code can use defaults.
        if not isinstance(data, dict) or "format" not in data or "version" not in data:
            raise OverrideError("override YAML needs explicit format and version fields")
        document = OverrideDocument.model_validate(data)
        if document.project_id != project_id:
            raise OverrideError("override document belongs to another project")
        return ordered_overrides(project_id, document.overrides)
    except (ValueError, yaml.YAMLError) as error:
        raise OverrideError(str(error)) from error


def load_overrides(path: Path, *, project_id: str) -> list[GraphOverride]:
    """Read override YAML from disk. Does not apply it or persist it."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise OverrideError(f"can't read {path}: {error}") from error
    return parse_overrides(text, project_id=project_id)


def merge_overrides(
    existing: Iterable[GraphOverride], incoming: Iterable[GraphOverride], *, project_id: str
) -> list[GraphOverride]:
    """Merge an import without losing existing edits; identical IDs are idempotent.

    Status is derived at application time. An imported cached status cannot rewrite
    history. The same ID with different authored content is refused, never replaced.
    """
    by_id = {record.id: record for record in ordered_overrides(project_id, existing)}
    for record in ordered_overrides(project_id, incoming):
        previous = by_id.get(record.id)
        if previous is None:
            by_id[record.id] = record
        elif previous.model_dump(exclude={"status"}) != record.model_dump(exclude={"status"}):
            raise OverrideError(f"override {record.id!r} already exists with different content")
    return ordered_overrides(project_id, by_id.values())
