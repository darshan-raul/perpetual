"""Base class for typed per-resource-type properties (spec §15.3, §15.4).

Rule packs read these typed models, never the raw `ResourceNode.properties` dict.

Three kinds of "missing" are kept apart, because the engine treats them differently:

- a field set to None means the value is absent or null in the source;
- a field named in `unknown_fields` is unknown, e.g. a Terraform plan value known
  only after apply. Rules must treat it as UNKNOWN, never as absent or as the old
  live value (spec §15.4);
- an empty list means "known to be empty".
"""

from typing import ClassVar, Self

from pydantic import Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr


class TypedProperties(DomainModel):
    """Common base. Each subclass sets `type_key` to a single literal value."""

    # Fields that are bookkeeping, not resource configuration.
    _META_FIELDS: ClassVar[frozenset[str]] = frozenset({"type_key", "unknown_fields"})

    unknown_fields: list[NonEmptyStr] = Field(default_factory=list)
    """Configuration fields whose values are not known yet (spec §15.4)."""

    @model_validator(mode="after")
    def _unknown_fields_exist(self) -> Self:
        # A misspelled name here would silently leave a field "known", so every
        # name must be a real configuration field of this resource type.
        valid = set(type(self).model_fields) - self._META_FIELDS
        invalid = sorted(set(self.unknown_fields) - valid)
        if invalid:
            raise ValueError(f"unknown_fields names fields this type does not have: {invalid}")
        return self

    def is_missing(self, field_name: str) -> bool:
        """True if the field is empty and *not* marked unknown.

        Validators use this so a value that is only known after apply (spec §15.4)
        does not fail a rule like "an Image function needs image_uri".
        """
        return not getattr(self, field_name) and field_name not in self.unknown_fields
