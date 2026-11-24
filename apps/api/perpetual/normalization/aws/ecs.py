"""AWS API response normalizers for Amazon ECS (clusters, services, task definitions)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, cast

from perpetual.ids import aws_id
from perpetual.models.properties.ecs import (
    CapacityProviderStrategyItem,
    ContainerDefinition,
    ECSClusterProperties,
    ECSServiceProperties,
    ECSTaskDefinitionProperties,
    SecretReference,
    ServiceAutoScaling,
    ServiceLoadBalancer,
)
from perpetual.models.resource import ResourceNode
from perpetual.normalization.aws._common import aws_source_ref, ensure_aware_utc, tags_from_list

_LaunchType = Literal["FARGATE", "EC2", "EXTERNAL"]
_SchedulingStrategy = Literal["REPLICA", "DAEMON"]
_NetworkMode = Literal["awsvpc", "bridge", "host", "none"]


def normalize_ecs_cluster(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one cluster object from `ecs:DescribeClusters`."""
    ts = ensure_aware_utc(collected_at)
    cluster_name = str(raw["clusterName"])
    cluster_arn = raw.get("clusterArn")

    strategy = [
        CapacityProviderStrategyItem(
            capacity_provider=str(item["capacityProvider"]),
            weight=int(item.get("weight", 0)),
            base=int(item.get("base", 0)),
        )
        for item in raw.get("defaultCapacityProviderStrategy", [])
    ]
    typed = ECSClusterProperties(
        cluster_name=cluster_name,
        capacity_providers=[str(cp) for cp in raw.get("capacityProviders", [])],
        default_capacity_provider_strategy=strategy,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ecs", "cluster", cluster_name),
        provider="aws",
        service="ecs",
        resource_type="cluster",
        account_id=account_id,
        region=region,
        name=cluster_name,
        arn=str(cluster_arn) if cluster_arn else None,
        tags=tags_from_list(raw.get("tags"), key_field="key", value_field="value"),
        properties={"status": raw.get("status")},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ecs:DescribeClusters",
                identifier=cluster_name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_ecs_service(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
    auto_scaling: Mapping[str, int] | None = None,
) -> ResourceNode:
    """Normalize one service object from `ecs:DescribeServices`."""
    ts = ensure_aware_utc(collected_at)
    service_name = str(raw["serviceName"])
    service_arn = raw.get("serviceArn")
    cluster_arn = str(raw["clusterArn"])
    cluster_name = cluster_arn.rsplit("/", 1)[-1]
    identifier = f"{cluster_name}/{service_name}"

    net_cfg = raw.get("networkConfiguration", {}).get("awsvpcConfiguration", {})
    assign_public_raw = net_cfg.get("assignPublicIp")
    assign_public_ip: bool | None = None
    if assign_public_raw == "ENABLED":
        assign_public_ip = True
    elif assign_public_raw == "DISABLED":
        assign_public_ip = False

    load_balancers = [
        ServiceLoadBalancer(
            target_group_arn=str(lb["targetGroupArn"]),
            container_name=str(lb["containerName"]),
            container_port=int(lb["containerPort"]),
        )
        for lb in raw.get("loadBalancers", [])
        if lb.get("targetGroupArn")
    ]
    strategy = [
        CapacityProviderStrategyItem(
            capacity_provider=str(item["capacityProvider"]),
            weight=int(item.get("weight", 0)),
            base=int(item.get("base", 0)),
        )
        for item in raw.get("capacityProviderStrategy", [])
    ]

    deploy_cfg = raw.get("deploymentConfiguration", {})
    circuit_breaker = deploy_cfg.get("deploymentCircuitBreaker", {})
    circuit_enabled: bool | None = (
        bool(circuit_breaker["enable"]) if "enable" in circuit_breaker else None
    )

    scaling_model: ServiceAutoScaling | None = None
    if auto_scaling is not None:
        scaling_model = ServiceAutoScaling(
            min_capacity=int(auto_scaling["min_capacity"]),
            max_capacity=int(auto_scaling["max_capacity"]),
        )

    launch_type_raw = raw.get("launchType")
    launch_type: _LaunchType | None = (
        cast(_LaunchType, str(launch_type_raw))
        if launch_type_raw in {"FARGATE", "EC2", "EXTERNAL"}
        else None
    )
    sched_raw = raw.get("schedulingStrategy", "REPLICA")
    scheduling_strategy: _SchedulingStrategy = (
        cast(_SchedulingStrategy, str(sched_raw))
        if sched_raw in {"REPLICA", "DAEMON"}
        else "REPLICA"
    )

    typed = ECSServiceProperties(
        service_name=service_name,
        cluster_arn=cluster_arn,
        task_definition_arn=str(raw["taskDefinition"]),
        launch_type=launch_type,
        capacity_provider_strategy=strategy,
        scheduling_strategy=scheduling_strategy,
        desired_count=int(raw.get("desiredCount", 0)),
        subnet_ids=[str(s) for s in net_cfg.get("subnets", [])],
        security_group_ids=[str(sg) for sg in net_cfg.get("securityGroups", [])],
        assign_public_ip=assign_public_ip,
        load_balancers=load_balancers,
        service_registry_arns=[
            str(reg["registryArn"])
            for reg in raw.get("serviceRegistries", [])
            if reg.get("registryArn")
        ],
        health_check_grace_period_seconds=raw.get("healthCheckGracePeriodSeconds"),
        deployment_minimum_healthy_percent=deploy_cfg.get("minimumHealthyPercent"),
        deployment_maximum_percent=deploy_cfg.get("maximumPercent"),
        deployment_circuit_breaker=circuit_enabled,
        auto_scaling=scaling_model,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ecs", "service", identifier),
        provider="aws",
        service="ecs",
        resource_type="service",
        account_id=account_id,
        region=region,
        name=service_name,
        arn=str(service_arn) if service_arn else None,
        tags=tags_from_list(raw.get("tags"), key_field="key", value_field="value"),
        properties={"status": raw.get("status")},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ecs:DescribeServices",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_ecs_task_definition(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize a taskDefinition object from `ecs:DescribeTaskDefinition`.

    Per spec §67, environment variable *values* are never copied into either
    `typed_properties` or `properties`; only variable names are retained.
    """
    ts = ensure_aware_utc(collected_at)
    family = str(raw["family"])
    revision = int(raw["revision"])
    identifier = f"{family}:{revision}"
    td_arn = raw.get("taskDefinitionArn")

    containers: list[ContainerDefinition] = []
    for container in raw.get("containerDefinitions", []):
        secrets = [
            SecretReference(
                name=str(sec["name"]),
                value_from=str(sec["valueFrom"]),
            )
            for sec in container.get("secrets", [])
            if sec.get("name") and sec.get("valueFrom")
        ]
        # Spec §67: record environment variable names ONLY, never values.
        env_names = sorted(
            str(env["name"])
            for env in container.get("environment", [])
            if isinstance(env, Mapping) and env.get("name")
        )
        ports = [
            int(pm["containerPort"])
            for pm in container.get("portMappings", [])
            if "containerPort" in pm
        ]
        containers.append(
            ContainerDefinition(
                name=str(container["name"]),
                image=str(container["image"]),
                essential=bool(container.get("essential", True)),
                secrets=secrets,
                environment_names=env_names,
                has_health_check=bool(container.get("healthCheck")),
                container_ports=ports,
            )
        )

    net_mode_raw = raw.get("networkMode")
    network_mode: _NetworkMode | None = (
        cast(_NetworkMode, str(net_mode_raw))
        if net_mode_raw in {"awsvpc", "bridge", "host", "none"}
        else None
    )
    compat: list[_LaunchType] = [
        cast(_LaunchType, str(c))
        for c in raw.get("requiresCompatibilities", [])
        if c in {"FARGATE", "EC2", "EXTERNAL"}
    ]

    typed = ECSTaskDefinitionProperties(
        family=family,
        revision=revision,
        task_role_arn=raw.get("taskRoleArn"),
        execution_role_arn=raw.get("executionRoleArn"),
        network_mode=network_mode,
        requires_compatibilities=compat,
        cpu=str(raw["cpu"]) if raw.get("cpu") is not None else None,
        memory=str(raw["memory"]) if raw.get("memory") is not None else None,
        containers=containers,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ecs", "task-definition", identifier),
        provider="aws",
        service="ecs",
        resource_type="task-definition",
        account_id=account_id,
        region=region,
        name=identifier,
        arn=str(td_arn) if td_arn else None,
        tags={},
        # Keep raw properties minimal and guaranteed free of environment values.
        properties={"status": raw.get("status")},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ecs:DescribeTaskDefinition",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )
