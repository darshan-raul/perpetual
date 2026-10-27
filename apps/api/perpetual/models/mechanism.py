"""Recovery mechanisms: the DR overlay (spec §27.1).

For every stack resource, how it is provided in the DR target. The overlay is
graph-shaped: a mechanism has its own DR-side dependencies.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from perpetual.models.common import Confidence, DomainModel, NonEmptyStr
from perpetual.models.edge import DependencyGroup, GroupScope
from perpetual.models.evidence import Evidence


class MechanismKind(StrEnum):
    LIVE_COUNTERPART = "live_counterpart"
    """Replica, replicated repo, DR service or replicated secret."""
    RESTORE_FROM_RECOVERY_POINT = "restore_from_recovery_point"
    """Snapshot, backup or PITR."""
    REBUILD_FROM_IAC = "rebuild_from_iac"
    """Reproducible in the strict sense of spec §27.1; otherwise the kind is unknown."""
    GLOBAL_SERVICE = "global_service"
    """Not Region-scoped, subject to the control-plane rules in spec §8.1."""
    EXTERNAL = "external"
    """User-declared posture (spec §15.2)."""
    NONE = "none"
    """No recovery path exists."""
    UNKNOWN = "unknown"
    """Not enough evidence."""


class RecoveryMechanism(DomainModel):
    id: NonEmptyStr
    primary_resource_id: NonEmptyStr
    target_region: NonEmptyStr
    target_account_id: NonEmptyStr
    kind: MechanismKind
    counterpart_resource_id: str | None = None
    """The DR resource, if it exists."""
    recovery_point_ids: list[NonEmptyStr] = Field(default_factory=list)
    dr_dependency_ids: list[NonEmptyStr] = Field(default_factory=list)
    """What the mechanism requires in the DR target. Ungrouped means ALL."""
    dependency_groups: list[DependencyGroup] = Field(default_factory=list)
    """Explicit alternatives under spec §19.1."""
    control_plane_dependent: bool
    """True if recovery needs control-plane API calls during the event (spec §8.1)."""
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence

    @model_validator(mode="after")
    def _groups_are_dr_side(self) -> Self:
        # A mechanism's dependencies are what recovery needs in the DR target (a DR
        # KMS key, a DR subnet group). Primary-side groups belong to the dependency
        # graph, not to the overlay.
        if any(group.scope is not GroupScope.DR for group in self.dependency_groups):
            raise ValueError("a mechanism's dependency groups have scope dr")
        return self
