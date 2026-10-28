"""Immutable evaluation inputs (spec §56.3).

Every assessment, simulation, candidate and DR spec references one
`EvaluationInput`: the exact snapshots, revisions, versions and catalog digests it
was computed from. Approval signs a canonical digest of it (computed in P9-08), so
any relevant change shows up as a different manifest and supersedes the approval.

The manifest never holds credentials, Terraform state or secret values; it holds
identities and digests of them.
"""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from perpetual.models.common import Digest, DomainModel, NonEmptyStr, SortedIds


class InputKind(StrEnum):
    ASSUMPTION = "assumption"
    USER_CONFIRMATION = "user_confirmation"
    SKILL = "skill"
    DOCUMENT = "document"


class InputRef(DomainModel):
    """An assumption, confirmation, skill or document that the evaluation actually used."""

    kind: InputKind
    id: NonEmptyStr
    digest: Digest


class IaCRoot(DomainModel):
    """One declared Terraform root, as pinned before approval."""

    path: NonEmptyStr
    """Repository-relative path."""
    workspace: NonEmptyStr = "default"
    provider_regions: dict[str, str] = Field(default_factory=dict)
    """Provider alias (or "default") to the Region it targets."""
    backend_lineage: str | None = None
    backend_serial: int | None = Field(default=None, ge=0)
    """None when the backend could not be read; never fetched by reading state contents."""
    lock_file_digest: Digest | None = None


class IaCBaseline(DomainModel):
    """The user's IaC as it was when the design was approved (spec §56.3)."""

    repository_base_commit: NonEmptyStr
    tree_digest: Digest
    """Digest of the declared paths. They must be clean to create the baseline."""
    roots: list[IaCRoot] = Field(min_length=1)
    kubernetes_inventory_digest: Digest | None = None
    """Identity of the rendered Kubernetes objects, when the stack has them."""

    @model_validator(mode="after")
    def _distinct_roots(self) -> Self:
        paths = [(root.path, root.workspace) for root in self.roots]
        if len(set(paths)) != len(paths):
            raise ValueError("each (path, workspace) root appears once")
        return self


class CompanionDesign(DomainModel):
    """For companion Terraform (spec §62.1): what was rendered, from what."""

    template_digest: Digest
    input_digest: Digest


class EvaluationInput(DomainModel):
    id: NonEmptyStr
    stack_id: NonEmptyStr
    failure_scenario: NonEmptyStr
    """e.g. region:ap-south-1."""

    primary_snapshot_id: NonEmptyStr
    primary_inventory_completed_at: AwareDatetime
    dr_snapshot_id: str | None = None
    dr_inventory_completed_at: AwareDatetime | None = None
    coverage_ids: SortedIds = Field(default_factory=list)

    graph_revision: int = Field(ge=0)
    override_revision: int = Field(ge=0)
    group_revision: int = Field(ge=0)
    requirement_id: NonEmptyStr
    requirement_revision: int = Field(ge=1)
    workload_profile_id: str | None = None
    workload_profile_revision: int | None = Field(default=None, ge=1)

    engine_version: NonEmptyStr
    rule_pack_versions: dict[str, str] = Field(default_factory=dict)
    config_digest: Digest
    duration_catalog_digest: Digest
    price_catalog_digest: Digest | None = None
    """None when no cost was evaluated."""
    freshness_policy_version: NonEmptyStr

    inputs_used: list[InputRef] = Field(default_factory=list)
    evaluated_at: AwareDatetime
    """When it was computed. Old results can be reproduced, never shown as current."""

    iac_baseline: IaCBaseline | None = None
    companion_design: CompanionDesign | None = None
    """Attached before approval: one or the other, never both."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.dr_snapshot_id is None) != (self.dr_inventory_completed_at is None):
            raise ValueError("dr_snapshot_id and dr_inventory_completed_at are set together")
        if (self.workload_profile_id is None) != (self.workload_profile_revision is None):
            raise ValueError("workload_profile_id and workload_profile_revision are set together")
        if self.iac_baseline is not None and self.companion_design is not None:
            raise ValueError("an evaluation pins an IaC baseline or a companion design, not both")
        return self

    @field_validator("inputs_used")
    @classmethod
    def _inputs_sorted_and_distinct(cls, refs: list[InputRef]) -> list[InputRef]:
        # Normalized order, so the canonical digest doesn't depend on list order.
        keys = [(ref.kind.value, ref.id) for ref in refs]
        if len(set(keys)) != len(keys):
            raise ValueError("each input is listed once")
        return sorted(refs, key=lambda ref: (ref.kind.value, ref.id))
