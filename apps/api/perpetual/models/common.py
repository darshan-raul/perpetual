"""Shared field types and the base model for all domain models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
"""A string that must not be empty."""

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
"""A confidence value between 0 and 1 inclusive."""


class DomainModel(BaseModel):
    """Base for domain models: immutable, and unknown fields are rejected.

    Immutability keeps snapshots and evaluation inputs stable (spec §56.3).
    Rejecting unknown fields makes typos in fixtures and imports fail loudly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)
