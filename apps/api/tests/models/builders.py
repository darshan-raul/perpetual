"""Shared builders for model tests."""

from datetime import UTC, datetime
from typing import Any

from perpetual.models import Basis, Evidence, SourceType

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def make_evidence(**overrides: Any) -> Evidence:
    fields: dict[str, Any] = {
        "id": "ev-1",
        "source_type": SourceType.TERRAFORM,
        "basis": Basis.REFERENCED,
        "source": "terraform:root/default",
        "confidence": 1.0,
        "collected_at": NOW,
    }
    fields.update(overrides)
    return Evidence(**fields)
