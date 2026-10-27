"""Base classes for typed per-resource-type properties (spec §15.3, §15.4).

Rule packs read these typed models, never the raw `ResourceNode.properties` dict.

Three kinds of "missing" are kept apart, because the engine treats them differently:

- a field set to None means the value is absent or null in the source;
- a field named in `unknown_fields` is unknown, e.g. a Terraform plan value known
  only after apply. Rules must treat it as UNKNOWN, never as absent or as the old
  live value (spec §15.4);
- an empty list means "known to be empty".

Values that AWS assigns (IDs, ARNs, URIs, computed numbers) are listed in a model's
`required_fields`. They must be present, *or* named in `unknown_fields`: a resource
that a Terraform plan will create has no ARN yet, and the importer must never invent
one (spec §15.4).
"""

from collections.abc import Iterator
from typing import Any, ClassVar, Self

from pydantic import Field, field_validator, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr


def is_empty(value: Any) -> bool:
    """None or an empty string/collection. 0 and False are values, never "empty"."""
    if value is None:
        return True
    if isinstance(value, (str, list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False


class PropertyPart(DomainModel):
    """Base for models nested inside typed properties (a container, a replication
    rule, an origin...). It may declare `required_fields` too; when one of them is
    unknown, the parent lists the whole field in its own `unknown_fields`."""

    required_fields: ClassVar[frozenset[str]] = frozenset()

    def iter_missing_required(self) -> Iterator[str]:
        """Required fields of this part that have no value."""
        for name in sorted(self.required_fields):
            if is_empty(getattr(self, name)):
                yield name


class TypedProperties(PropertyPart):
    """Common base. Each subclass sets `type_key` to a single literal value."""

    # Fields that are bookkeeping, not resource configuration.
    _META_FIELDS: ClassVar[frozenset[str]] = frozenset({"type_key", "unknown_fields"})

    unknown_fields: list[NonEmptyStr] = Field(default_factory=list)
    """Configuration fields whose values are not known yet (spec §15.4)."""

    @field_validator("unknown_fields")
    @classmethod
    def _sorted_and_distinct(cls, names: list[str]) -> list[str]:
        # The order means nothing, so it is normalized: the same state must always
        # produce the same canonical hash (spec §56.3).
        if len(set(names)) != len(names):
            raise ValueError("unknown_fields must not repeat a field")
        return sorted(names)

    @model_validator(mode="after")
    def _check_unknown_and_required(self) -> Self:
        # 1. Every name in unknown_fields is a real configuration field. A misspelled
        #    name would silently leave the real field "known".
        valid = set(type(self).model_fields) - self._META_FIELDS
        invalid = sorted(set(self.unknown_fields) - valid)
        if invalid:
            raise ValueError(f"unknown_fields names fields this type does not have: {invalid}")

        # 2. AWS-assigned values are present or explicitly unknown, never just absent.
        for name in sorted(self.required_fields):
            if self.is_missing(name):
                raise ValueError(
                    f"{name} is required; if it is only known after apply, "
                    "list it in unknown_fields"
                )

        # 3. The same for nested parts, one level down: an unknown value inside a
        #    part makes the whole parent field unknown.
        for field_name in type(self).model_fields:
            if field_name in self.unknown_fields:
                continue
            for part in _parts(getattr(self, field_name)):
                for missing in part.iter_missing_required():
                    raise ValueError(
                        f"{field_name}: {type(part).__name__}.{missing} is required; if it "
                        f"is only known after apply, list {field_name!r} in unknown_fields"
                    )
        return self

    def is_missing(self, field_name: str) -> bool:
        """True if the field is empty and *not* marked unknown.

        Validators use this so a value only known after apply (spec §15.4) never
        fails a check such as "an Image function needs image_uri". 0 and False are
        values, not missing.
        """
        return is_empty(getattr(self, field_name)) and field_name not in self.unknown_fields

    def is_unknown(self, field_name: str) -> bool:
        """True if the field is marked unknown (spec §15.4)."""
        return field_name in self.unknown_fields


def _parts(value: Any) -> Iterator[PropertyPart]:
    """The PropertyPart values held directly by a field: itself or its list items."""
    if isinstance(value, PropertyPart):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, PropertyPart):
                yield item
