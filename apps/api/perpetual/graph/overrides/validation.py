"""Check targets and project ownership before any override is applied."""

import json
import re
from collections.abc import Iterable

from perpetual.graph.overrides.targets import edge_target
from perpetual.graph.overrides.types import OverrideError
from perpetual.models import GraphOverride, OverrideKind, RelationshipType
from perpetual.models.override import AddEdgePayload, AddNodePayload

_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


def ordered_overrides(project_id: str, overrides: Iterable[GraphOverride]) -> list[GraphOverride]:
    """Validate the batch and return isolated records in deterministic replay order."""
    if not project_id:
        raise OverrideError("project_id must not be empty")
    records = []
    seen_ids: set[str] = set()
    for original in overrides:
        # Validate again because callers may have mutated nested payload dictionaries.
        try:
            override = GraphOverride.model_validate(original.model_dump())
        except ValueError as error:
            raise OverrideError(str(error)) from error
        if override.project_id != project_id:
            raise OverrideError(f"override {override.id!r} belongs to another project")
        if override.id in seen_ids:
            raise OverrideError(f"duplicate override ID {override.id!r}")
        seen_ids.add(override.id)
        _check_target(override)
        records.append(override)
    return sorted(records, key=lambda override: (override.created_at, override.id))


def _check_target(override: GraphOverride) -> None:
    if override.kind is OverrideKind.REJECT_EDGE:
        if not _FINGERPRINT.fullmatch(override.target):
            raise OverrideError("reject_edge targets an evidence fingerprint (sha256:<hex>)")
    elif override.kind in {OverrideKind.CONFIRM_EDGE, OverrideKind.EDIT_EDGE}:
        _check_edge_target(override.target)
    elif override.kind is OverrideKind.ADD_EDGE:
        if override.target != edge_target(AddEdgePayload.model_validate(override.payload)):
            raise OverrideError("add_edge target does not match its payload")
    elif (
        override.kind is OverrideKind.ADD_NODE
        and override.target != AddNodePayload.model_validate(override.payload).resource_id
    ):
        raise OverrideError("add_node target does not match its payload")


def _check_edge_target(target: str) -> None:
    if not target.startswith("edge:"):
        raise OverrideError("confirm/edit targets must be created with edge_target")
    try:
        parts = json.loads(target.removeprefix("edge:"))
    except json.JSONDecodeError as error:
        raise OverrideError("invalid edge target JSON") from error
    if not isinstance(parts, list) or len(parts) != 3:
        raise OverrideError("edge target needs from, to and relationship type")
    if any(not isinstance(part, str) or not part for part in parts):
        raise OverrideError("edge target parts must be non-empty strings")
    try:
        RelationshipType(parts[2])
    except ValueError as error:
        raise OverrideError("edge target has an unknown relationship type") from error
    canonical = "edge:" + json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    if target != canonical:
        raise OverrideError("use edge_target to produce the canonical target")
