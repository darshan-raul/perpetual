"""First-slice `DRRulePack` implementations for ECS + RDS stacks (spec §27.1, §28).

These are the real service rule packs that P4 extends with findings and P1-10/P6
extend with recovery actions. Each pack resolves how a primary resource is
provided in `context.target_region` from typed properties and graph edges
(`replicates_to`, `backed_up_by`), enforcing the strict §27.1 reproducibility
definition whenever falling back to `rebuild_from_iac`.
"""

from __future__ import annotations

from perpetual.models import (
    MechanismKind,
    RecoveryMechanism,
    RelationshipType,
    ResourceNode,
)
from perpetual.models.properties import (
    KMSKeyProperties,
    RDSInstanceProperties,
    RecordSetProperties,
)
from perpetual.rules.protocol import AssessmentContext, DRRulePack, RulePackRegistry

FIRST_SLICE_VERSION = "0.1.0"


# --- shared resolution helpers ------------------------------------------------


def _replicated_counterpart(resource: ResourceNode, context: AssessmentContext) -> str | None:
    """Return the first `replicates_to` target in `context.target_region`, if any."""
    for edge in context.graph.outgoing_edges(resource.id, operational_only=False):
        if edge.relationship_type is not RelationshipType.REPLICATES_TO:
            continue
        target = context.graph.resources.get(edge.to_resource_id)
        if target is not None and target.region == context.target_region:
            return target.id
    return None


def _recovery_points_in_dr(resource: ResourceNode, context: AssessmentContext) -> list[str]:
    """Return sorted `backed_up_by` targets located in `context.target_region`."""
    points: list[str] = []
    for edge in context.graph.outgoing_edges(resource.id, operational_only=False):
        if edge.relationship_type is not RelationshipType.BACKED_UP_BY:
            continue
        target = context.graph.resources.get(edge.to_resource_id)
        if target is not None and target.region == context.target_region:
            points.append(target.id)
    return sorted(points)


def _matching_dr_counterpart(resource: ResourceNode, context: AssessmentContext) -> str | None:
    """Find a DR counterpart by `replicates_to` edge, or by matching service/type/name in DR."""
    replicated = _replicated_counterpart(resource, context)
    if replicated is not None:
        return replicated

    candidates = [
        node
        for node in context.graph.resources.values()
        if node.region == context.target_region
        and node.service == resource.service
        and node.resource_type == resource.resource_type
    ]
    if not candidates:
        return None
    for candidate in sorted(candidates, key=lambda item: item.id):
        if candidate.name in {resource.name, f"{resource.name}-dr"}:
            return candidate.id
    return None


def _build_mechanism(
    resource: ResourceNode,
    context: AssessmentContext,
    *,
    kind: MechanismKind,
    counterpart_resource_id: str | None = None,
    recovery_point_ids: list[str] | None = None,
    dr_dependency_ids: list[str] | None = None,
    control_plane_dependent: bool = False,
    confidence: float = 0.95,
) -> RecoveryMechanism:
    return RecoveryMechanism(
        id=f"mech:{resource.id}",
        primary_resource_id=resource.id,
        target_region=context.target_region,
        target_account_id=context.target_account_id,
        kind=kind,
        counterpart_resource_id=counterpart_resource_id,
        recovery_point_ids=recovery_point_ids or [],
        dr_dependency_ids=sorted(set(dr_dependency_ids or [])),
        control_plane_dependent=control_plane_dependent,
        confidence=confidence,
    )


def _fallback_reproducible_or_none(
    resource: ResourceNode,
    context: AssessmentContext,
    *,
    control_plane_dependent: bool = False,
) -> RecoveryMechanism:
    """Return `rebuild_from_iac` only when strict §27.1 criteria pass; else `none`."""
    if context.is_reproducible(resource):
        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.REBUILD_FROM_IAC,
            control_plane_dependent=True,
            confidence=0.9,
        )
    return _build_mechanism(
        resource,
        context,
        kind=MechanismKind.NONE,
        control_plane_dependent=control_plane_dependent,
    )


# --- service rule packs -------------------------------------------------------


class Route53RulePack:
    """Route 53 DR rule pack (spec §8, §8.1)."""

    service = "route53"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        props = resource.typed_properties
        if isinstance(props, RecordSetProperties):
            has_failover = props.routing_policy == "failover" and props.health_check_id is not None
            if has_failover:
                dr_targets = _dr_counterparts_of_targets(resource, context)
                return _build_mechanism(
                    resource,
                    context,
                    kind=MechanismKind.GLOBAL_SERVICE,
                    dr_dependency_ids=dr_targets,
                    control_plane_dependent=False,
                )
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.NONE,
                control_plane_dependent=True,
            )
        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.UNKNOWN,
            control_plane_dependent=True,
            confidence=0.0,
        )


class ELBRulePack:
    """ALB/NLB DR rule pack (spec §8)."""

    service = "elasticloadbalancing"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _matching_dr_counterpart(resource, context)
        if counterpart is not None:
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                control_plane_dependent=False,
            )
        return _fallback_reproducible_or_none(resource, context)


class ECSRulePack:
    """ECS DR rule pack (spec §5.1, §32)."""

    service = "ecs"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _matching_dr_counterpart(resource, context)
        if counterpart is not None:
            dr_deps = _dr_counterparts_of_targets(resource, context)
            # Also include DR ALB if primary ALB routes to this ECS service.
            for edge in context.graph.incoming_edges(resource.id, operational_only=True):
                upstream = context.graph.resources.get(edge.from_resource_id)
                if upstream is not None and upstream.service == "elasticloadbalancing":
                    dr_alb = _matching_dr_counterpart(upstream, context)
                    if dr_alb is not None:
                        dr_deps.append(dr_alb)
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                dr_dependency_ids=dr_deps,
                control_plane_dependent=True,
            )
        return _fallback_reproducible_or_none(resource, context, control_plane_dependent=True)


class ECRRulePack:
    """ECR DR rule pack (spec §8)."""

    service = "ecr"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _replicated_counterpart(resource, context)
        if counterpart is not None:
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                control_plane_dependent=False,
            )
        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.NONE,
            control_plane_dependent=False,
        )


class SecretsManagerRulePack:
    """Secrets Manager DR rule pack (spec §8)."""

    service = "secretsmanager"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _replicated_counterpart(resource, context)
        if counterpart is not None:
            dr_deps = _dr_counterparts_of_targets(resource, context)
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                dr_dependency_ids=dr_deps,
                control_plane_dependent=False,
            )
        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.NONE,
            control_plane_dependent=False,
        )


class KMSRulePack:
    """KMS DR rule pack (spec §8)."""

    service = "kms"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _replicated_counterpart(resource, context)
        props = resource.typed_properties
        is_multi_region = not isinstance(props, KMSKeyProperties) or props.multi_region is True
        if counterpart is not None and is_multi_region:
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                control_plane_dependent=False,
            )
        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.NONE,
            control_plane_dependent=False,
        )


class RDSRulePack:
    """RDS/Aurora DR rule pack (spec §6.1, §41)."""

    service = "rds"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _replicated_counterpart(resource, context)
        if counterpart is not None:
            dr_deps: list[str] = []
            dr_node = context.graph.resources.get(counterpart)
            if (
                dr_node is not None
                and isinstance(dr_node.typed_properties, RDSInstanceProperties)
                and dr_node.typed_properties.kms_key_id in context.graph.resources
                and dr_node.typed_properties.kms_key_id is not None
            ):
                dr_deps.append(dr_node.typed_properties.kms_key_id)
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                dr_dependency_ids=dr_deps,
                control_plane_dependent=True,
            )

        recovery_points = _recovery_points_in_dr(resource, context)
        if recovery_points:
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.RESTORE_FROM_RECOVERY_POINT,
                recovery_point_ids=recovery_points,
                control_plane_dependent=True,
            )

        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.NONE,
            control_plane_dependent=True,
        )


class S3RulePack:
    """S3 DR rule pack (spec §7)."""

    service = "s3"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _replicated_counterpart(resource, context)
        if counterpart is not None:
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                control_plane_dependent=False,
            )
        return _build_mechanism(
            resource,
            context,
            kind=MechanismKind.NONE,
            control_plane_dependent=False,
        )


class LogsRulePack:
    """CloudWatch Logs DR rule pack (out of RTO scope by default, spec §24.1)."""

    service = "logs"
    version = FIRST_SLICE_VERSION

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        counterpart = _replicated_counterpart(resource, context)
        if counterpart is not None:
            return _build_mechanism(
                resource,
                context,
                kind=MechanismKind.LIVE_COUNTERPART,
                counterpart_resource_id=counterpart,
                control_plane_dependent=False,
            )
        return _fallback_reproducible_or_none(resource, context)


def _dr_counterparts_of_targets(resource: ResourceNode, context: AssessmentContext) -> list[str]:
    """Find DR counterparts of operational dependencies leaving `resource`."""
    dr_deps: list[str] = []
    for edge in context.graph.outgoing_edges(resource.id, operational_only=True):
        dependency = context.graph.resources.get(edge.to_resource_id)
        if dependency is None:
            continue
        dr_target = _matching_dr_counterpart(dependency, context)
        if dr_target is not None:
            dr_deps.append(dr_target)
    return dr_deps


def default_registry() -> RulePackRegistry:
    """Build a `RulePackRegistry` populated with all first-slice ECS + RDS rule packs."""
    registry = RulePackRegistry()
    packs: tuple[DRRulePack, ...] = (
        Route53RulePack(),
        ELBRulePack(),
        ECSRulePack(),
        ECRRulePack(),
        SecretsManagerRulePack(),
        KMSRulePack(),
        RDSRulePack(),
        S3RulePack(),
        LogsRulePack(),
    )
    for pack in packs:
        registry.register(pack)
    return registry
