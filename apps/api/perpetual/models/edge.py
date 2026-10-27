"""Dependency edges and dependency groups (spec §17, §19, §19.1, §20).

Edge direction is always dependent -> dependency: `ECS service -> RDS database`
means the ECS service requires the database.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from perpetual.models.common import Confidence, DomainModel, NonEmptyStr
from perpetual.models.evidence import Basis, Evidence, SourceType


class RelationshipType(StrEnum):
    """Initial relationship vocabulary (spec §20). Add types only when they are useful."""

    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    CONNECTS_TO = "connects_to"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    ENCRYPTED_BY = "encrypted_by"
    USES_SECRET = "uses_secret"
    USES_PARAMETER = "uses_parameter"
    USES_IMAGE = "uses_image"
    ROUTES_TO = "routes_to"
    RESOLVES_TO = "resolves_to"
    MOUNTED_FROM = "mounted_from"
    BACKED_UP_BY = "backed_up_by"
    """Resource -> recovery point or vault. Followed only by the DR overlay."""
    REPLICATES_TO = "replicates_to"
    """Primary -> DR copy kept in sync. Followed only by the DR overlay."""
    ASSUMES_ROLE = "assumes_role"
    SCHEDULED_ON = "scheduled_on"
    MEMBER_OF = "member_of"
    TARGETS = "targets"
    ATTACHED_TO = "attached_to"
    DEPLOYED_TO = "deployed_to"

    @property
    def is_operational_requirement(self) -> bool:
        """False for structural and replication/backup relationships (spec §19.1, §20).

        A primary resource does not fail because its replica or backup fails, so the
        impact pass never follows these edges.
        """
        return self not in _NOT_REQUIREMENTS


_NOT_REQUIREMENTS = frozenset(
    {
        RelationshipType.CONTAINS,
        RelationshipType.MEMBER_OF,
        RelationshipType.REPLICATES_TO,
        RelationshipType.BACKED_UP_BY,
    }
)


class EdgeOrigin(StrEnum):
    DISCOVERED = "discovered"
    USER = "user"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    REJECTED = "rejected"


class Criticality(StrEnum):
    REQUIRED = "required"
    LIKELY_REQUIRED = "likely_required"
    OPTIONAL = "optional"
    UNKNOWN = "unknown"


class DependencyEdge(DomainModel):
    """One typed edge between two resources. Parallel edges are kept (spec §19.1)."""

    id: NonEmptyStr
    from_resource_id: NonEmptyStr
    to_resource_id: NonEmptyStr
    relationship_type: RelationshipType
    confidence: Confidence
    confirmed: bool | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    inferred: bool
    origin: EdgeOrigin
    review_state: ReviewState = ReviewState.UNREVIEWED
    criticality: Criticality

    @property
    def bases(self) -> frozenset[Basis]:
        """Bases derived from the evidence; never stored separately (spec §19)."""
        return frozenset(item.basis for item in self.evidence if item.basis is not None)

    @model_validator(mode="after")
    def _check(self) -> Self:
        # Pydantic runs this after field validation, so every field already has the
        # right type here. Each check below is a spec rule that spans several fields.

        # 1. Dependency evidence must say what it shows: permitted, referenced,
        #    observed or asserted (spec §14.1). Evidence without a basis cannot be
        #    weighed or shown to the user, so it is rejected here.
        if any(item.basis is None for item in self.evidence):
            raise ValueError("every piece of dependency evidence needs a basis")

        # 2. An edge the user added is certain by definition and must carry the
        #    user's assertion as its evidence (spec §23).
        if self.origin is EdgeOrigin.USER:
            if self.confidence != 1.0:
                raise ValueError("a user-added edge has confidence 1.0")
            if not any(
                item.source_type is SourceType.USER_CONFIRMATION and item.basis is Basis.ASSERTED
                for item in self.evidence
            ):
                raise ValueError(
                    "a user-added edge needs user_confirmation evidence with basis asserted"
                )

        # 3. `confirmed` and `review_state` describe the same review and must agree.
        #    An edited edge may be confirmed or not, so it is not checked.
        expected = {
            ReviewState.UNREVIEWED: None,
            ReviewState.CONFIRMED: True,
            ReviewState.REJECTED: False,
        }
        if self.review_state in expected and self.confirmed is not expected[self.review_state]:
            raise ValueError(
                f"review_state {self.review_state} requires confirmed={expected[self.review_state]}"
            )
        return self


class GroupMode(StrEnum):
    ALL = "all"
    ANY = "any"
    QUORUM = "quorum"


class GroupScope(StrEnum):
    PRIMARY = "primary"
    DR = "dr"


class DependencyGroup(DomainModel):
    """Alternatives among a dependent's edges (spec §19.1).

    An ungrouped required edge is an ALL requirement. Checks that need the graph
    (members share the dependent and scope, an edge is in at most one group) run
    when the graph is built.
    """

    id: NonEmptyStr
    dependent_resource_id: NonEmptyStr
    member_edge_ids: list[NonEmptyStr] = Field(min_length=1)
    mode: GroupMode
    minimum_healthy: int | None = None
    """Quorum only: how many members must be usable."""
    scope: GroupScope
    evidence: list[Evidence] = Field(default_factory=list)
    review_state: ReviewState = ReviewState.UNREVIEWED

    @property
    def required_members(self) -> int:
        """How many members must be usable: all, one, or the quorum."""
        if self.mode is GroupMode.ALL:
            return len(self.member_edge_ids)
        if self.mode is GroupMode.ANY:
            return 1
        if self.minimum_healthy is None:  # unreachable after validation; keeps the type exact
            raise ValueError("quorum group without minimum_healthy")
        return self.minimum_healthy

    @model_validator(mode="after")
    def _check(self) -> Self:
        # A duplicated member would count twice toward the quorum and overstate
        # redundancy, so members must be distinct.
        if len(set(self.member_edge_ids)) != len(self.member_edge_ids):
            raise ValueError("member_edge_ids must be distinct")
        # Quorum needs a number between 1 and the member count (spec §19.1).
        # For ALL and ANY the number is implied, so setting it is a mistake.
        if self.mode is GroupMode.QUORUM:
            if self.minimum_healthy is None or not (
                1 <= self.minimum_healthy <= len(self.member_edge_ids)
            ):
                raise ValueError(
                    "a quorum group needs minimum_healthy between 1 and the number of members"
                )
        elif self.minimum_healthy is not None:
            raise ValueError("minimum_healthy is only valid for quorum groups")
        return self
