"""PoC compile loop: modeled DR change set, companion Terraform, re-simulation (P1c-01..03)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files

from jinja2 import Environment, StrictUndefined

from perpetual.graph import DependencyGraph, GraphError, build_graph
from perpetual.ids import planned_id
from perpetual.models import (
    Basis,
    Criticality,
    DependencyEdge,
    EdgeOrigin,
    Evidence,
    RecoveryMechanism,
    RecoveryRequirement,
    RelationshipType,
    ResourceNode,
    SourceType,
    TargetComparison,
)
from perpetual.models.properties import (
    ECRRepositoryProperties,
    ECSServiceProperties,
    KMSKeyProperties,
    RDSInstanceProperties,
    RecordSetProperties,
    SecretProperties,
)
from perpetual.recovery import RecoveryPlan, plan_stack_recovery
from perpetual.rules import AssessmentContext, default_registry
from perpetual.simulator import (
    EvaluationKind,
    RegionFailure,
    SimulationResult,
    simulate_failure,
)

POC_CHANGE_DESCRIPTIONS: tuple[str, ...] = (
    "Enable multi-Region KMS key and replica in DR Region",
    "Configure ECR cross-Region replication to DR Region",
    "Replicate Secrets Manager secret to DR Region",
    "Provision encrypted RDS cross-Region read replica in DR Region",
    "Configure Route 53 failover routing with primary health check",
)


@dataclass(frozen=True)
class PocFixResult:
    """Before/after simulation, recovery plans, and generated Terraform for `perpetual poc fix`."""

    stack_id: str
    primary_region: str
    target_region: str
    changes_applied: tuple[str, ...]
    before_simulation: SimulationResult
    after_simulation: SimulationResult
    before_plan: RecoveryPlan
    after_plan: RecoveryPlan
    terraform_files: dict[str, str]
    modeled_graph: DependencyGraph


def apply_poc_change_set(
    graph: DependencyGraph,
    *,
    stack_id: str,
    target_region: str,
) -> tuple[DependencyGraph, dict[str, RecoveryMechanism]]:
    """Apply the fixed PoC DR change set as a modeled planned snapshot (P1c-01).

    Never mutates the input `DependencyGraph`. Adds DR counterparts (KMS replica,
    ECR repo, Secrets replica, RDS read replica), cross-Region `replicates_to`
    edges, and Route 53 failover settings, then re-resolves mechanisms through
    the real `DRRulePack` registry.
    """
    stack = graph.stacks.get(stack_id)
    if stack is None:
        raise GraphError(f"unknown stack {stack_id!r}")

    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    resources = dict(graph.resources)
    edges = dict(graph.edges)
    account_id = _stack_account_id(graph, stack.resource_ids)
    dr_kms_id: str | None = None

    # 1. Multi-Region KMS key + DR replica.
    for rid in sorted(stack.resource_ids):
        node = resources[rid]
        label = _node_name(node)
        if node.service == "kms" and node.resource_type == "key":
            dr_kms_id = planned_id(
                account_id,
                target_region,
                "kms",
                "key",
                root_id="poc",
                workspace="default",
                address="aws_kms_replica_key.dr_replica",
            )
            resources[rid] = node.model_copy(
                update={
                    "typed_properties": KMSKeyProperties(
                        key_id=label,
                        multi_region=True,
                        multi_region_role="PRIMARY",
                    )
                }
            )
            resources[dr_kms_id] = ResourceNode(
                id=dr_kms_id,
                provider="aws",
                service="kms",
                resource_type="key",
                account_id=account_id,
                region=target_region,
                name=f"{label}-dr",
                planned=True,
                terraform_address="aws_kms_replica_key.dr_replica",
                typed_properties=KMSKeyProperties(
                    key_id=label,
                    multi_region=True,
                    multi_region_role="REPLICA",
                    primary_key_arn=f"arn:aws:kms:{stack.primary_region}:{account_id}:key/{label}",
                ),
                discovered_at=now,
            )
            edges[f"poc-repl-{label}"] = _repl_edge(f"poc-repl-{label}", rid, dr_kms_id, now)

    # 2. ECR cross-Region replication, Secrets replication, RDS replica, Route 53 failover.
    for rid in sorted(stack.resource_ids):
        node = resources[rid]
        label = _node_name(node)
        if node.service == "ecr" and node.resource_type == "repository":
            dr_ecr_id = planned_id(
                account_id,
                target_region,
                "ecr",
                "repository",
                root_id="poc",
                workspace="default",
                address="aws_ecr_repository.dr",
            )
            resources[dr_ecr_id] = ResourceNode(
                id=dr_ecr_id,
                provider="aws",
                service="ecr",
                resource_type="repository",
                account_id=account_id,
                region=target_region,
                name=label,
                planned=True,
                terraform_address="aws_ecr_repository.dr",
                typed_properties=ECRRepositoryProperties(
                    repository_name=label,
                    repository_uri=f"{account_id}.dkr.ecr.{target_region}.amazonaws.com/{label}",
                ),
                discovered_at=now,
            )
            edges[f"poc-repl-ecr-{label}"] = _repl_edge(
                f"poc-repl-ecr-{label}", rid, dr_ecr_id, now
            )

        elif node.service == "secretsmanager" and node.resource_type == "secret":
            ident = rid.rsplit("/", 1)[-1]
            dr_secret_id = planned_id(
                account_id,
                target_region,
                "secretsmanager",
                "secret",
                root_id="poc",
                workspace="default",
                address="aws_secretsmanager_secret.dr",
            )
            resources[dr_secret_id] = ResourceNode(
                id=dr_secret_id,
                provider="aws",
                service="secretsmanager",
                resource_type="secret",
                account_id=account_id,
                region=target_region,
                name=label,
                planned=True,
                terraform_address="aws_secretsmanager_secret.dr",
                typed_properties=SecretProperties(name=label),
                discovered_at=now,
            )
            edges[f"poc-repl-sec-{ident}"] = _repl_edge(
                f"poc-repl-sec-{ident}", rid, dr_secret_id, now
            )

        elif node.service == "rds" and node.resource_type == "db":
            dr_db_name = f"{label}-dr"
            dr_rds_id = planned_id(
                account_id,
                target_region,
                "rds",
                "db",
                root_id="poc",
                workspace="default",
                address="aws_db_instance.dr_replica",
            )
            props = node.typed_properties
            engine = props.engine if isinstance(props, RDSInstanceProperties) else "postgres"
            inst_class = (
                props.instance_class if isinstance(props, RDSInstanceProperties) else "db.r6g.large"
            )
            resources[dr_rds_id] = ResourceNode(
                id=dr_rds_id,
                provider="aws",
                service="rds",
                resource_type="db",
                account_id=account_id,
                region=target_region,
                name=dr_db_name,
                planned=True,
                terraform_address="aws_db_instance.dr_replica",
                typed_properties=RDSInstanceProperties(
                    db_instance_identifier=dr_db_name,
                    engine=engine,
                    instance_class=inst_class,
                    multi_az=True,
                    storage_encrypted=True,
                    kms_key_id=dr_kms_id,
                ),
                discovered_at=now,
            )
            edges[f"poc-repl-rds-{label}"] = _repl_edge(
                f"poc-repl-rds-{label}", rid, dr_rds_id, now
            )

        elif node.service == "route53" and node.resource_type == "recordset":
            props = node.typed_properties
            zone_id = props.hosted_zone_id if isinstance(props, RecordSetProperties) else "Z123"
            record_type = props.record_type if isinstance(props, RecordSetProperties) else "A"
            resources[rid] = node.model_copy(
                update={
                    "typed_properties": RecordSetProperties(
                        hosted_zone_id=zone_id,
                        name=label,
                        record_type=record_type,
                        routing_policy="failover",
                        failover_role="PRIMARY",
                        set_identifier=f"{stack.name}-primary",
                        health_check_id=f"hc-{stack.name}-primary",
                    )
                }
            )

    # Ensure DR ECS service has desired_count >= 1 in the modeled design.
    for rid, node in list(resources.items()):
        if (
            node.region == target_region
            and node.service == "ecs"
            and node.resource_type == "service"
            and isinstance(node.typed_properties, ECSServiceProperties)
            and node.typed_properties.desired_count == 0
        ):
            resources[rid] = node.model_copy(
                update={
                    "typed_properties": node.typed_properties.model_copy(
                        update={"desired_count": 1}
                    )
                }
            )

    # First build without mechanisms so the real rule packs resolve the new DR overlay.
    prelim = build_graph(
        resources=resources.values(),
        edges=edges.values(),
        groups=graph.groups.values(),
        rejected_edges=graph.rejected_edges.values(),
        stacks=graph.stacks.values(),
        stack_resources=graph.stack_resources.values(),
        stack_services=graph.stack_services.values(),
    )
    context = AssessmentContext(
        graph=prelim,
        target_region=target_region,
        target_account_id=account_id,
    )
    resolved_mechs = default_registry().resolve_all(
        [prelim.resources[rid] for rid in stack.resource_ids],
        context,
    )
    modeled = build_graph(
        resources=resources.values(),
        edges=edges.values(),
        groups=graph.groups.values(),
        rejected_edges=graph.rejected_edges.values(),
        mechanisms=resolved_mechs.values(),
        stacks=graph.stacks.values(),
        stack_resources=graph.stack_resources.values(),
        stack_services=graph.stack_services.values(),
    )
    return modeled, resolved_mechs


def render_poc_terraform(
    *,
    stack_name: str,
    account_id: str,
    primary_region: str,
    target_region: str,
    db_identifier: str,
    db_instance_class: str,
    ecr_repository_name: str,
    kms_alias: str,
) -> dict[str, str]:
    """Render companion Terraform files for the PoC DR change set using Jinja2 (P1c-02)."""
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    template_dir = files("perpetual.iac").joinpath("templates", "poc")
    context = {
        "stack_name": stack_name,
        "account_id": account_id,
        "primary_region": primary_region,
        "target_region": target_region,
        "db_identifier": db_identifier,
        "db_instance_class": db_instance_class,
        "ecr_repository_name": ecr_repository_name,
        "kms_alias": kms_alias,
    }
    rendered: dict[str, str] = {}
    for filename in ("versions.tf", "kms.tf", "ecr.tf", "rds.tf"):
        source = template_dir.joinpath(f"{filename}.j2").read_text(encoding="utf-8")
        rendered[filename] = env.from_string(source).render(**context)
    return rendered


def run_poc_fix(
    graph: DependencyGraph,
    *,
    stack_id: str,
    requirement: RecoveryRequirement,
) -> PocFixResult:
    """Run the P1c PoC compile loop: simulate before -> apply fix -> render TF -> re-simulate."""
    stack = graph.stacks.get(stack_id)
    if stack is None:
        raise GraphError(f"unknown stack {stack_id!r}")
    if requirement.target_region is None:
        raise GraphError("PoC fix requires a Region requirement with target_region")

    scenario = RegionFailure(region=stack.primary_region)
    before_mechs = {m.primary_resource_id: m for m in graph.mechanisms.values()}
    before_plan = plan_stack_recovery(
        graph, stack_id, requirement=requirement, mechanisms=before_mechs
    )
    before_sim = simulate_failure(
        graph,
        stack_id,
        scenario,
        mechanisms=before_mechs,
        rto_comparison=before_plan.rto_comparison or TargetComparison.UNCERTAIN,
    )

    modeled_graph, after_mechs = apply_poc_change_set(
        graph, stack_id=stack_id, target_region=requirement.target_region
    )
    after_plan = plan_stack_recovery(
        modeled_graph, stack_id, requirement=requirement, mechanisms=after_mechs
    )
    after_sim = simulate_failure(
        modeled_graph,
        stack_id,
        scenario,
        mechanisms=after_mechs,
        rto_comparison=after_plan.rto_comparison or TargetComparison.UNCERTAIN,
        evaluation_kind=EvaluationKind.DESIGN,
    )

    db_id, db_class, ecr_name, kms_alias = _extract_poc_names(graph, stack.resource_ids)
    tf_files = render_poc_terraform(
        stack_name=stack.name,
        account_id=_stack_account_id(graph, stack.resource_ids),
        primary_region=stack.primary_region,
        target_region=requirement.target_region,
        db_identifier=db_id,
        db_instance_class=db_class,
        ecr_repository_name=ecr_name,
        kms_alias=kms_alias,
    )

    return PocFixResult(
        stack_id=stack_id,
        primary_region=stack.primary_region,
        target_region=requirement.target_region,
        changes_applied=POC_CHANGE_DESCRIPTIONS,
        before_simulation=before_sim,
        after_simulation=after_sim,
        before_plan=before_plan,
        after_plan=after_plan,
        terraform_files=tf_files,
        modeled_graph=modeled_graph,
    )


def _stack_account_id(graph: DependencyGraph, resource_ids: list[str]) -> str:
    for rid in resource_ids:
        account = graph.resources[rid].account_id
        if account is not None:
            return account
    return "123456789012"


def _node_name(node: ResourceNode) -> str:
    return node.name or node.id.rsplit("/", 1)[-1]


def _extract_poc_names(
    graph: DependencyGraph, resource_ids: list[str]
) -> tuple[str, str, str, str]:
    db_id = "orders"
    db_class = "db.r6g.large"
    ecr_name = "app"
    kms_alias = "app-cmk"
    for rid in resource_ids:
        node = graph.resources[rid]
        if node.service == "rds" and node.resource_type == "db":
            db_id = _node_name(node)
            if isinstance(node.typed_properties, RDSInstanceProperties):
                db_class = node.typed_properties.instance_class
        elif node.service == "ecr" and node.resource_type == "repository":
            ecr_name = _node_name(node)
        elif node.service == "kms" and node.resource_type == "key":
            kms_alias = _node_name(node)
    return db_id, db_class, ecr_name, kms_alias


def _repl_edge(edge_id: str, src: str, dst: str, now: datetime) -> DependencyEdge:
    return DependencyEdge(
        id=edge_id,
        from_resource_id=src,
        to_resource_id=dst,
        relationship_type=RelationshipType.REPLICATES_TO,
        confidence=1.0,
        evidence=[
            Evidence(
                id=f"ev-{edge_id}",
                source_type=SourceType.TERRAFORM,
                basis=Basis.REFERENCED,
                source="perpetual:poc-fix",
                kind="terraform_reference",
                confidence=1.0,
                collected_at=now,
            )
        ],
        inferred=False,
        origin=EdgeOrigin.DISCOVERED,
        criticality=Criticality.REQUIRED,
    )
