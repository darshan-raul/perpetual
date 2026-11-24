"""Recovery action model and first-slice action synthesis (spec §47.1, §48, §49.1)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import Field

from perpetual.models import (
    DomainModel,
    DurationEstimate,
    MechanismKind,
    NonEmptyStr,
    RecoveryMechanism,
    ResourceNode,
)
from perpetual.models.properties import RDSInstanceProperties
from perpetual.recovery.catalog import DurationCatalog


class RecoveryPhase(StrEnum):
    """Ordered recovery phases for the phase-template DAG (spec §47.1)."""

    DECIDE = "decide"
    FOUNDATION = "foundation"
    DATA = "data"
    COMPUTE = "compute"
    TRAFFIC = "traffic"


PHASE_ORDER: dict[RecoveryPhase, int] = {
    RecoveryPhase.DECIDE: 0,
    RecoveryPhase.FOUNDATION: 1,
    RecoveryPhase.DATA: 2,
    RecoveryPhase.COMPUTE: 3,
    RecoveryPhase.TRAFFIC: 4,
}


class AutomationLevel(StrEnum):
    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"
    MANUAL = "manual"


class RecoveryAction(DomainModel):
    """One step in a stack's recovery DAG (spec §48)."""

    id: NonEmptyStr
    name: NonEmptyStr
    action_type: NonEmptyStr
    phase: RecoveryPhase
    resource_ids: list[NonEmptyStr] = Field(default_factory=list)
    prerequisites: list[NonEmptyStr] = Field(default_factory=list)
    refined_prerequisites: bool = False
    """When True, `prerequisites` replaces the default phase-barrier edges (§47.1)."""
    estimated_duration: DurationEstimate
    automation_level: AutomationLevel
    blocking: bool = True
    instructions: str | None = None


def actions_for_mechanism(
    mechanism: RecoveryMechanism,
    resource: ResourceNode,
    catalog: DurationCatalog,
    *,
    duration_overrides: Mapping[str, DurationEstimate] | None = None,
) -> list[RecoveryAction]:
    """Synthesize first-slice recovery actions for one resolved mechanism (P1-10).

    Includes generic fallback actions (`generic_promote_counterpart`,
    `generic_restore_from_backup`, `generic_rebuild_from_iac`) for unmodeled
    services whose mechanism was confirmed by the user (§49.1).
    """
    if mechanism.kind in {MechanismKind.NONE, MechanismKind.UNKNOWN, MechanismKind.EXTERNAL}:
        return []

    overrides = duration_overrides or {}
    override = overrides.get(resource.id)
    service = resource.service

    spec = _service_action_spec(service, mechanism.kind)
    if spec is None:
        return []

    action_type, phase, automation, label = spec
    attributes = _volumetric_attributes(resource)
    duration = catalog.estimate(action_type, attributes=attributes, override=override)
    return [
        RecoveryAction(
            id=f"act:{resource.id}:{action_type}",
            name=f"{label}: {resource.name}",
            action_type=action_type,
            phase=phase,
            resource_ids=[resource.id],
            estimated_duration=duration,
            automation_level=automation,
        )
    ]


_ActionSpec = tuple[str, RecoveryPhase, AutomationLevel, str]

_SERVICE_ACTION_SPECS: dict[tuple[str, MechanismKind], _ActionSpec] = {
    ("rds", MechanismKind.LIVE_COUNTERPART): (
        "rds_promote_read_replica",
        RecoveryPhase.DATA,
        AutomationLevel.SEMI_AUTOMATIC,
        "Promote RDS read replica",
    ),
    ("rds", MechanismKind.RESTORE_FROM_RECOVERY_POINT): (
        "rds_restore_from_snapshot",
        RecoveryPhase.DATA,
        AutomationLevel.MANUAL,
        "Restore RDS from DR snapshot",
    ),
    ("ecs", MechanismKind.LIVE_COUNTERPART): (
        "ecs_scale_service",
        RecoveryPhase.COMPUTE,
        AutomationLevel.SEMI_AUTOMATIC,
        "Scale DR ECS service",
    ),
    ("elasticloadbalancing", MechanismKind.LIVE_COUNTERPART): (
        "elb_verify_ready",
        RecoveryPhase.FOUNDATION,
        AutomationLevel.AUTOMATIC,
        "Verify DR load balancer",
    ),
    ("ecr", MechanismKind.LIVE_COUNTERPART): (
        "ecr_verify_image",
        RecoveryPhase.FOUNDATION,
        AutomationLevel.AUTOMATIC,
        "Verify DR ECR image",
    ),
    ("secretsmanager", MechanismKind.LIVE_COUNTERPART): (
        "secrets_verify_replica",
        RecoveryPhase.FOUNDATION,
        AutomationLevel.AUTOMATIC,
        "Verify DR secret replica",
    ),
    ("kms", MechanismKind.LIVE_COUNTERPART): (
        "kms_verify_key",
        RecoveryPhase.FOUNDATION,
        AutomationLevel.AUTOMATIC,
        "Verify DR KMS replica key",
    ),
    ("s3", MechanismKind.LIVE_COUNTERPART): (
        "s3_verify_replica",
        RecoveryPhase.DATA,
        AutomationLevel.AUTOMATIC,
        "Verify DR S3 bucket",
    ),
    ("route53", MechanismKind.GLOBAL_SERVICE): (
        "route53_failover_switch",
        RecoveryPhase.TRAFFIC,
        AutomationLevel.AUTOMATIC,
        "Verify Route 53 failover",
    ),
}


def _service_action_spec(service: str, kind: MechanismKind) -> _ActionSpec | None:
    """Map `(service, mechanism_kind)` to `(action_type, phase, automation_level, label)`."""
    matched = _SERVICE_ACTION_SPECS.get((service, kind))
    if matched is not None:
        return matched
    return _generic_fallback_spec(kind)


def _generic_fallback_spec(
    kind: MechanismKind,
) -> tuple[str, RecoveryPhase, AutomationLevel, str] | None:
    if kind is MechanismKind.LIVE_COUNTERPART:
        return (
            "generic_promote_counterpart",
            RecoveryPhase.DATA,
            AutomationLevel.MANUAL,
            "Promote DR counterpart",
        )
    if kind is MechanismKind.RESTORE_FROM_RECOVERY_POINT:
        return (
            "generic_restore_from_backup",
            RecoveryPhase.DATA,
            AutomationLevel.MANUAL,
            "Restore from DR backup",
        )
    if kind is MechanismKind.REBUILD_FROM_IAC:
        return (
            "generic_rebuild_from_iac",
            RecoveryPhase.COMPUTE,
            AutomationLevel.MANUAL,
            "Rebuild resource from IaC",
        )
    return None


def _volumetric_attributes(resource: ResourceNode) -> dict[str, float | int | None]:
    props = resource.typed_properties
    if isinstance(props, RDSInstanceProperties):
        return {"allocated_storage_gb": props.allocated_storage_gib}
    return {}
