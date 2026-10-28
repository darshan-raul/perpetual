"""Deployment prerequisites and verification reports (spec §61.1, §62, §63.1).

A report keeps four kinds of evidence apart: static checks, design verification,
deployment prerequisites and observed readiness. A passing design is "design
verified — deployment and observation pending". It is never proof that the live
stack is READY, and a modeled RTO is never a drill-proven one (spec §53).
"""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import Digest, DomainModel, NonEmptyStr, SortedIds
from perpetual.models.status import Readiness


class PrerequisiteKind(StrEnum):
    """Things a plan cannot prove (spec §61.1) or that Terraform should not own (§62)."""

    IMAGE_PRESENT = "image_present"
    INITIAL_DATA_COPY = "initial_data_copy"
    """e.g. S3 Batch Replication of objects that existed before the rule."""
    SECRET_POPULATED = "secret_populated"
    PARAMETER_COPY = "parameter_copy"
    QUOTA_INCREASE = "quota_increase"
    REPLICA_HEALTHY = "replica_healthy"
    OPERATOR_ACCESS = "operator_access"
    """e.g. an IAM Identity Center replica Region (OPS-ACCESS-001)."""
    MANUAL_STEP = "manual_step"


class PrerequisiteStatus(StrEnum):
    PENDING = "pending"
    SATISFIED = "satisfied"
    FAILED = "failed"
    """Known impossible, or a check after deployment found it unmet."""
    UNKNOWN = "unknown"


class DeploymentPrerequisite(DomainModel):
    id: NonEmptyStr
    kind: PrerequisiteKind
    description: NonEmptyStr
    affected_resource_ids: SortedIds = Field(min_length=1)
    owner: NonEmptyStr
    """Who acts on it, e.g. operator, user pipeline, prerequisite script."""
    required_evidence: NonEmptyStr
    """What a later scan must observe, e.g. "image digest present in DR ECR"."""
    check_ids: SortedIds = Field(default_factory=list)
    """Rule or check IDs that re-test it on the next scan."""
    status: PrerequisiteStatus = PrerequisiteStatus.PENDING
    evidence_ids: SortedIds = Field(default_factory=list)
    """Evidence (or a versioned manual attestation) that settled the status."""

    @model_validator(mode="after")
    def _settled_needs_evidence(self) -> Self:
        # No operational check is marked PASS merely because its configuration
        # exists (spec §61.1): satisfied and failed both cite what showed it.
        settled = {PrerequisiteStatus.SATISFIED, PrerequisiteStatus.FAILED}
        if self.status in settled and not self.evidence_ids:
            raise ValueError(f"a {self.status} prerequisite cites its evidence")
        return self


def combined_prerequisite_status(items: list[DeploymentPrerequisite]) -> PrerequisiteStatus:
    """Worst first: failed, then unknown, then pending. No prerequisites is satisfied."""
    statuses = {item.status for item in items}
    for status in (
        PrerequisiteStatus.FAILED,
        PrerequisiteStatus.UNKNOWN,
        PrerequisiteStatus.PENDING,
    ):
        if status in statuses:
            return status
    return PrerequisiteStatus.SATISFIED


class StaticChecks(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class DesignVerification(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class VerificationMode(StrEnum):
    FULL = "full"
    """A saved plan with matching provenance was imported and re-simulated."""
    STATIC_CHECKS_ONLY = "static_checks_only"
    """No valid plan: design verification is always UNKNOWN."""


class CheckResult(DomainModel):
    name: NonEmptyStr
    """e.g. terraform validate, kubeconform, secret scan, allowed paths."""
    outcome: StaticChecks
    detail: str | None = None


class VerificationReport(DomainModel):
    """Bound to the exact tree and plan it checked. A later edit invalidates it (§56.3)."""

    id: NonEmptyStr
    dr_spec_id: NonEmptyStr
    approved_digest: Digest
    tree_digest: Digest
    saved_plan_digest: Digest | None = None
    rendered_manifests_digest: Digest | None = None
    mode: VerificationMode
    static_checks: StaticChecks
    check_results: list[CheckResult] = Field(default_factory=list)
    design_verification: DesignVerification
    unverified_change_ids: SortedIds = Field(default_factory=list)
    """DR spec changes absent from the supplied plan or manifests (spec §61.1, v0.1)."""
    prerequisites: list[DeploymentPrerequisite] = Field(default_factory=list)
    observed_readiness: Readiness = Readiness.UNKNOWN
    """From a matching live evaluation (§31); UNKNOWN when none exists."""
    created_at: AwareDatetime

    @property
    def deployment_prerequisites(self) -> PrerequisiteStatus:
        return combined_prerequisite_status(self.prerequisites)

    @property
    def label(self) -> str:
        if self.design_verification is DesignVerification.PASS:
            return "design verified — deployment and observation pending"
        if self.mode is VerificationMode.STATIC_CHECKS_ONLY:
            return "static checks only"
        return "unverified"

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [item.id for item in self.prerequisites]
        if len(set(ids)) != len(ids):
            raise ValueError("prerequisite IDs must be unique")
        if self.mode is VerificationMode.FULL and self.saved_plan_digest is None:
            raise ValueError("full verification names the saved plan it imported")
        if self.design_verification is DesignVerification.PASS:
            # Without a plan there is nothing to re-simulate (spec §61.1); a change
            # missing from the plan stays unverified; a known impossible
            # prerequisite can't accompany a passing design.
            if self.mode is not VerificationMode.FULL:
                raise ValueError("design verification can pass only in full mode")
            if self.static_checks is not StaticChecks.PASS:
                raise ValueError("design verification can't pass when static checks didn't")
            if self.unverified_change_ids:
                raise ValueError("design verification can't pass with unverified changes")
            if self.deployment_prerequisites is PrerequisiteStatus.FAILED:
                raise ValueError("design verification can't pass with a failed prerequisite")
        if (
            self.observed_readiness is Readiness.READY
            and self.deployment_prerequisites is not PrerequisiteStatus.SATISFIED
        ):
            # A fresh scan must establish every prerequisite before observed READY.
            raise ValueError("observed READY needs every deployment prerequisite satisfied")
        return self
