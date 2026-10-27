"""User edits to the computed graph (spec §23).

Discovered data is never edited in place. Each edit is a GraphOverride applied on
top of every scan. The payload is a dict, as in the spec, validated against the
schema for its kind.
"""

from enum import StrEnum
from typing import Any, Self

from pydantic import AwareDatetime, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr
from perpetual.models.edge import Criticality, RelationshipType
from perpetual.models.stack import RtoScope


class OverrideKind(StrEnum):
    CONFIRM_EDGE = "confirm_edge"
    REJECT_EDGE = "reject_edge"
    ADD_EDGE = "add_edge"
    EDIT_EDGE = "edit_edge"
    ADD_NODE = "add_node"
    EDIT_NODE = "edit_node"


class OverrideStatus(StrEnum):
    ACTIVE = "active"
    ORPHANED = "orphaned"
    """The target disappeared. Shown to the user, never dropped silently."""


class DrPosture(StrEnum):
    """Declared posture of an external dependency (spec §15.2)."""

    AVAILABLE = "available"
    UNAVAILABLE_IN_REGION_FAILURE = "unavailable_in_region_failure"
    UNKNOWN = "unknown"


class NodeKind(StrEnum):
    EXTERNAL = "external"
    """Third-party SaaS, on-premise system or another cloud."""
    PLACEHOLDER = "placeholder"
    """An AWS resource Perpetual could not discover."""


class ConfirmEdgePayload(DomainModel):
    pass


class RejectEdgePayload(DomainModel):
    pass


class AddEdgePayload(DomainModel):
    from_resource_id: NonEmptyStr
    to_resource_id: NonEmptyStr
    relationship_type: RelationshipType
    criticality: Criticality
    note: str | None = None


class EditEdgePayload(DomainModel):
    relationship_type: RelationshipType | None = None
    criticality: Criticality | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if self.relationship_type is None and self.criticality is None:
            raise ValueError("edit_edge must change relationship_type or criticality")
        return self


class AddNodePayload(DomainModel):
    node_kind: NodeKind
    resource_id: NonEmptyStr
    provider: NonEmptyStr
    service: NonEmptyStr
    resource_type: NonEmptyStr
    name: str | None = None
    region: str | None = None
    account_id: str | None = None
    dr_posture: DrPosture | None = None
    """External nodes only. Undeclared means UNKNOWN."""

    @model_validator(mode="after")
    def _posture_only_for_external(self) -> Self:
        if self.node_kind is NodeKind.EXTERNAL and self.provider != "external":
            raise ValueError('an external node has provider "external"')
        if self.node_kind is NodeKind.PLACEHOLDER and self.dr_posture is not None:
            raise ValueError("dr_posture is only declared for external nodes")
        return self


class EditNodePayload(DomainModel):
    stack_id: NonEmptyStr
    member: bool | None = None
    """True adds the resource to the stack, False removes it."""
    service_id: str | None = None
    rto_scope: RtoScope | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if self.member is None and self.service_id is None and self.rto_scope is None:
            raise ValueError("edit_node must change membership, service or RTO scope")
        return self


PAYLOAD_SCHEMAS: dict[OverrideKind, type[DomainModel]] = {
    OverrideKind.CONFIRM_EDGE: ConfirmEdgePayload,
    OverrideKind.REJECT_EDGE: RejectEdgePayload,
    OverrideKind.ADD_EDGE: AddEdgePayload,
    OverrideKind.EDIT_EDGE: EditEdgePayload,
    OverrideKind.ADD_NODE: AddNodePayload,
    OverrideKind.EDIT_NODE: EditNodePayload,
}


class GraphOverride(DomainModel):
    id: NonEmptyStr
    project_id: NonEmptyStr
    kind: OverrideKind
    target: NonEmptyStr
    """Edge fingerprint, edge endpoints, or resource ID."""
    payload: dict[str, Any]
    reason: str | None = None
    author: NonEmptyStr
    created_at: AwareDatetime
    status: OverrideStatus = OverrideStatus.ACTIVE

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> Self:
        # The spec stores the payload as a plain dict so overrides round-trip
        # through YAML unchanged. Validating it against the schema for its kind
        # means a malformed override fails when it is loaded, not when it is applied.
        PAYLOAD_SCHEMAS[self.kind].model_validate(self.payload)
        return self

    def typed_payload(self) -> DomainModel:
        """The payload parsed into the schema for this override's kind."""
        return PAYLOAD_SCHEMAS[self.kind].model_validate(self.payload)
