"""Typed properties for ARC and IAM Identity Center (spec §8, §28.1, §63.3).

- ARC Region switch plans are collected as evidence: an existing plan is a declared
  recovery path that ARC-RS-001 compares with Perpetual's recovery DAG. A passed
  plan evaluation is evidence, never READY.
- ARC readiness checks are legacy (closed to new customers): collected, never
  recommended.
- IAM Identity Center's home Region decides whether operators can sign in during a
  Region failure (OPS-ACCESS-001).
"""

from typing import ClassVar, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class RoutingControlProperties(TypedProperties):
    """An ARC routing control: an on/off switch that health checks follow (data plane)."""

    type_key: Literal["route53-recovery-control/routingcontrol"] = (
        "route53-recovery-control/routingcontrol"
    )
    required_fields: ClassVar[frozenset[str]] = frozenset({"control_panel_arn"})
    name: NonEmptyStr
    control_panel_arn: NonEmptyStr | None = None
    cluster_arn: str | None = None
    state: Literal["On", "Off"] | None = None
    """Read from the cluster's data plane; None when it could not be read."""


class RegionSwitchStep(PropertyPart):
    name: NonEmptyStr
    execution_block_type: NonEmptyStr
    """e.g. AuroraGlobalDatabase, ECSServiceScaling, ManualApproval, Parallel."""
    target_resource_arns: list[NonEmptyStr] = Field(default_factory=list)
    """What the block acts on; used to check which recovery actions it covers."""
    skipped_when_ungraceful: bool = False
    """True if the step is skipped in an ungraceful run (ARC-RS-001 flags required ones)."""
    parallel_steps: list["RegionSwitchStep"] = Field(default_factory=list)
    """For a Parallel step: the steps it runs together (one level only)."""

    @model_validator(mode="after")
    def _one_level_of_parallel(self) -> Self:
        # ARC does not allow a Parallel step inside a Parallel step.
        if any(step.parallel_steps for step in self.parallel_steps):
            raise ValueError("parallel steps cannot contain parallel steps")
        return self


class RegionSwitchWorkflow(PropertyPart):
    target_action: Literal["activate", "deactivate", "postRecovery"]
    target_region: NonEmptyStr
    steps: list[RegionSwitchStep] = Field(default_factory=list)


class RegionSwitchPlanProperties(TypedProperties):
    type_key: Literal["arc-region-switch/plan"] = "arc-region-switch/plan"
    required_fields: ClassVar[frozenset[str]] = frozenset({"execution_role_arn"})
    name: NonEmptyStr
    recovery_approach: Literal["activeActive", "activePassive"]
    regions: list[NonEmptyStr] = Field(min_length=2, max_length=2)
    primary_region: str | None = None
    recovery_time_objective_minutes: int | None = Field(default=None, ge=1)
    execution_role_arn: NonEmptyStr | None = None
    workflows: list[RegionSwitchWorkflow] = Field(default_factory=list)
    application_health_alarm_arns: list[NonEmptyStr] = Field(default_factory=list)
    """Needed for ARC to measure actual recovery time."""
    has_triggers: bool = False
    report_s3_uri: str | None = None
    """Where execution reports go (drill evidence, imported from v0.3)."""
    evaluation_status: (
        Literal["passed", "actionRequired", "pendingEvaluation", "unknown"] | None
    ) = None
    last_evaluated_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _regions_consistent(self) -> Self:
        # A plan switches between exactly two distinct Regions, and every workflow
        # targets one of them.
        if len(set(self.regions)) != 2:
            raise ValueError("a Region switch plan has two distinct Regions")
        if self.primary_region is not None and self.primary_region not in self.regions:
            raise ValueError("primary_region must be one of the plan's Regions")
        for workflow in self.workflows:
            if workflow.target_region not in self.regions:
                raise ValueError(f"workflow targets {workflow.target_region}, not a plan Region")
        return self


class ReadinessCheckProperties(TypedProperties):
    """Legacy ARC readiness check: collected when present, never recommended."""

    type_key: Literal["route53-recovery-readiness/readiness-check"] = (
        "route53-recovery-readiness/readiness-check"
    )
    name: NonEmptyStr
    resource_set_arn: str | None = None
    readiness: Literal["READY", "NOT_READY", "UNKNOWN", "NOT_AUTHORIZED"] | None = None


class IdentityCenterInstanceProperties(TypedProperties):
    """An IAM Identity Center instance: where operators sign in."""

    type_key: Literal["sso/instance"] = "sso/instance"
    instance_arn: NonEmptyStr
    home_region: NonEmptyStr
    replica_regions: list[NonEmptyStr] = Field(default_factory=list)
    """Multi-Region replicas, which keep sign-in working if the home Region fails."""
    status: str | None = None

    @model_validator(mode="after")
    def _replicas_elsewhere(self) -> Self:
        if self.home_region in self.replica_regions:
            raise ValueError("the home Region is not also a replica Region")
        if len(set(self.replica_regions)) != len(self.replica_regions):
            raise ValueError("replica_regions must be distinct")
        return self
