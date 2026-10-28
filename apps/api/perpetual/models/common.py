"""Shared field types and the base model for all domain models."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
"""A string that must not be empty."""

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
"""A confidence value between 0 and 1 inclusive."""

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
"""A content digest, written `sha256:<64 lowercase hex>` (spec §56.3)."""


def _sorted_distinct(items: list[str]) -> list[str]:
    # Sets by meaning, stored sorted so the same content always gives the same
    # canonical hash (spec §56.3). A repeat is rejected rather than dropped: it
    # usually means two sources were merged wrongly.
    if len(set(items)) != len(items):
        raise ValueError("items must not repeat")
    return sorted(items)


SortedIds = Annotated[list[NonEmptyStr], AfterValidator(_sorted_distinct)]
"""A list of distinct non-empty strings, stored sorted."""


class DomainModel(BaseModel):
    """Base for domain models: immutable, and unknown fields are rejected.

    Immutability keeps snapshots and evaluation inputs stable (spec §56.3).
    Rejecting unknown fields makes typos in fixtures and imports fail loudly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)
