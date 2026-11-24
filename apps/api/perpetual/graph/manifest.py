"""Canonical digests and immutable snapshot/evaluation manifests (spec §56.3, §76.1).

Every evaluation, simulation, candidate, and DR spec is bound to immutable
inputs by deterministic `sha256:<64 hex>` digests.

Canonicalization rules:
- Pydantic models serialize via `model_dump(mode="python")` then recursively
  normalize keys, timestamps, and decimals so the exact same meaning always
  produces the exact same JSON bytes and hash;
- timezone-aware datetimes normalize to UTC ISO-8601 (`+00:00`), so equivalent
  instants written in different offsets hash identically;
- `None` values stay explicit `null` in JSON (`exclude_none=False`), keeping
  absent/null distinct from empty strings and from `unknown_fields` lists;
- dictionaries serialize with sorted keys and compact separators (`(",", ":")`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field

from perpetual.config import Config
from perpetual.graph.snapshot import DependencyGraph
from perpetual.models import (
    Digest,
    DomainModel,
    EvaluationInput,
    NonEmptyStr,
    ScanCoverage,
)


def canonical_json(value: Any) -> str:
    """Serialize `value` to deterministic, compact JSON suitable for hashing."""
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def canonical_digest(value: Any) -> Digest:
    """Return `sha256:<64 lowercase hex>` over the canonical JSON of `value`."""
    encoded = canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def config_digest(config: Config) -> Digest:
    """Canonical digest of an effective `Config` (spec §56.3)."""
    return canonical_digest(config)


def evaluation_input_digest(evaluation_input: EvaluationInput) -> Digest:
    """Canonical digest of an `EvaluationInput` manifest (spec §56.3)."""
    return canonical_digest(evaluation_input)


class SnapshotManifest(DomainModel):
    """Immutable content digest of a validated graph snapshot and its coverage (spec §56.3, §76.1).

    Later stages reference `manifest_digest` and the revision numbers without
    mutating historical evaluations.
    """

    snapshot_id: NonEmptyStr
    snapshot_kind: Literal["live", "planned"]
    captured_at: AwareDatetime

    graph_revision: int = Field(ge=0)
    override_revision: int = Field(ge=0)
    group_revision: int = Field(ge=0)

    resource_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    rejected_edge_count: int = Field(ge=0)
    group_count: int = Field(ge=0)
    mechanism_count: int = Field(ge=0)
    stack_count: int = Field(ge=0)
    coverage_count: int = Field(ge=0)

    resources_digest: Digest
    edges_digest: Digest
    rejected_edges_digest: Digest
    groups_digest: Digest
    mechanisms_digest: Digest
    stacks_digest: Digest
    coverage_digest: Digest
    manifest_digest: Digest


def build_snapshot_manifest(
    graph: DependencyGraph,
    *,
    snapshot_id: str,
    captured_at: datetime,
    snapshot_kind: Literal["live", "planned"] = "live",
    coverage: Iterable[ScanCoverage] = (),
    graph_revision: int = 0,
    override_revision: int = 0,
    group_revision: int = 0,
) -> SnapshotManifest:
    """Compute an immutable `SnapshotManifest` from a validated `DependencyGraph`."""
    sorted_resources = [graph.resources[key] for key in sorted(graph.resources)]
    sorted_edges = [graph.edges[key] for key in sorted(graph.edges)]
    sorted_rejected = [graph.rejected_edges[key] for key in sorted(graph.rejected_edges)]
    sorted_groups = [graph.groups[key] for key in sorted(graph.groups)]
    sorted_mechanisms = [graph.mechanisms[key] for key in sorted(graph.mechanisms)]
    sorted_stacks = {
        "stacks": [graph.stacks[key] for key in sorted(graph.stacks)],
        "stack_resources": [graph.stack_resources[key] for key in sorted(graph.stack_resources)],
        "stack_services": [graph.stack_services[key] for key in sorted(graph.stack_services)],
    }
    sorted_coverage = sorted(coverage, key=lambda item: item.id)

    body: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "snapshot_kind": snapshot_kind,
        "captured_at": captured_at,
        "graph_revision": graph_revision,
        "override_revision": override_revision,
        "group_revision": group_revision,
        "resource_count": len(sorted_resources),
        "edge_count": len(sorted_edges),
        "rejected_edge_count": len(sorted_rejected),
        "group_count": len(sorted_groups),
        "mechanism_count": len(sorted_mechanisms),
        "stack_count": len(graph.stacks),
        "coverage_count": len(sorted_coverage),
        "resources_digest": canonical_digest(sorted_resources),
        "edges_digest": canonical_digest(sorted_edges),
        "rejected_edges_digest": canonical_digest(sorted_rejected),
        "groups_digest": canonical_digest(sorted_groups),
        "mechanisms_digest": canonical_digest(sorted_mechanisms),
        "stacks_digest": canonical_digest(sorted_stacks),
        "coverage_digest": canonical_digest(sorted_coverage),
    }
    body["manifest_digest"] = canonical_digest(body)
    return SnapshotManifest.model_validate(body)


def _normalize(value: Any) -> Any:
    """Convert domain objects into JSON-native primitives with stable ordering and units."""
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [_normalize(item) for item in value]
        return sorted(normalized_items, key=lambda item: json.dumps(item, sort_keys=True))
    return _normalize_scalar(value)


def _normalize_scalar(value: Any) -> Any:
    """Normalize JSON scalars, enums, timezone-aware datetimes and decimals."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat() if value.tzinfo is not None else value.isoformat()
    if isinstance(value, timedelta):
        return {"timedelta_seconds": value.total_seconds()}
    if isinstance(value, Decimal):
        # Preserve exact numeric value without trailing insignificant zeros
        # (so Decimal("10.00") and Decimal("10") hash the same).
        return format(value.normalize(), "f")
    raise TypeError(f"unsupported type for canonical hashing: {type(value).__name__}")
