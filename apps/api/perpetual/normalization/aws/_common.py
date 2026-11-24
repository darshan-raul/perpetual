"""Shared helpers for normalizing raw AWS API responses into `ResourceNode`s.

Every normalizer in `perpetual.normalization.aws` is a pure function: it takes
raw boto3 / recorded JSON dicts plus collection metadata (`account_id`,
`region`, `collected_at`, optional `scan_id`) and returns a validated
`ResourceNode` with `typed_properties` populated. Both `perpetual
import-aws-fixture` (`P1b-03`) and live AWS collectors (`P2`) call these exact
functions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from perpetual.models.evidence import SourceType
from perpetual.models.resource import SourceReference


def parse_aws_datetime(value: Any) -> datetime | None:
    """Convert a boto3 `datetime` or ISO-8601 string into an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    raise ValueError(f"unsupported AWS timestamp value: {value!r}")


def tags_from_list(
    raw_tags: Sequence[Mapping[str, Any]] | None,
    *,
    key_field: str = "Key",
    value_field: str = "Value",
) -> dict[str, str]:
    """Convert AWS `[{"Key": ..., "Value": ...}]` tag lists into a plain dict."""
    if not raw_tags:
        return {}
    result: dict[str, str] = {}
    for item in raw_tags:
        key = item.get(key_field)
        val = item.get(value_field)
        if isinstance(key, str) and key and isinstance(val, str):
            result[key] = val
    return result


def aws_source_ref(
    *,
    operation: str,
    identifier: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> SourceReference:
    """Build a `SourceReference` pointing at the AWS API operation and resource."""
    return SourceReference(
        source_type=SourceType.AWS_API,
        locator=f"{operation}:{identifier}",
        collected_at=collected_at,
        scan_id=scan_id,
    )


def ensure_aware_utc(dt: datetime) -> datetime:
    """Ensure a collection timestamp is timezone-aware (UTC if naive)."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
