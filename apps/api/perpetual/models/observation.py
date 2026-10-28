"""Resolved observations from CloudTrail and flow logs (spec §14.1, "Ambiguous attribution").

An observation is an aggregate (window and count, never raw events) that has been
resolved to the resources at each end. Shared roles, Lambda Hyperplane ENIs and
uncertain historical ENI ownership often leave several candidates. Such an
observation is stored once, against its candidate sets: its count is not
multiplied, and it is not copied as high-confidence evidence onto every possible
edge. Edge resolvers (P2b) and the review flow (P2b-09) build on this model.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import DomainModel, NonEmptyStr, SortedIds


class Attribution(StrEnum):
    EXACT = "exact"
    """One proven resource at each end."""
    AMBIGUOUS = "ambiguous"
    """At least one end has several candidates. Gives no exact-edge confidence uplift,
    and an edge supported only by it cannot bypass review."""


class ResolvedObservation(DomainModel):
    id: NonEmptyStr
    source_type: Literal["cloudtrail", "vpc_flow_logs"]
    attribution: Attribution
    candidate_from_resource_ids: SortedIds
    """The dependent end: who called or sent."""
    candidate_to_resource_ids: SortedIds
    """The dependency end: what was called or reached."""
    operation: str | None = None
    """An aggregate signature such as `dynamodb:GetItem` or `tcp/5432`, never a request body."""
    resolution_evidence_ids: SortedIds = Field(default_factory=list)
    """Evidence used to resolve the ends, e.g. ENI ownership or role session tags."""
    observed_from: AwareDatetime
    observed_to: AwareDatetime
    observation_count: int = Field(ge=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.observed_from > self.observed_to:
            raise ValueError("observed_from must not be after observed_to")
        # An observation with no defensible candidate set is dropped and counted
        # by the resolver, not stored (spec §14.1).
        if not self.candidate_from_resource_ids or not self.candidate_to_resource_ids:
            raise ValueError("both ends need at least one candidate resource")
        single_ends = (
            len(self.candidate_from_resource_ids) == 1 and len(self.candidate_to_resource_ids) == 1
        )
        if self.attribution is Attribution.EXACT and not single_ends:
            raise ValueError("an exact observation has exactly one resource at each end")
        if self.attribution is Attribution.AMBIGUOUS and single_ends:
            raise ValueError("an ambiguous observation has several candidates at one end")
        if self.attribution is Attribution.EXACT and not self.resolution_evidence_ids:
            # Current ownership alone does not prove historical ownership, so an
            # exact attribution must say what proved it.
            raise ValueError("an exact observation cites its resolution evidence")
        return self
