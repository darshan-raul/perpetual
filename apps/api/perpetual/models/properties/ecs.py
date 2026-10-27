"""Typed properties for Amazon ECS (spec §5.1, §32).

The fields are what the ECS rule pack needs to decide whether a service could
start in the DR Region: compute, images, secrets, IAM, network, traffic, scaling.
References to other resources (roles, images, secrets, target groups) are kept as
ARNs or URIs so edge resolvers can turn them into dependency edges.
"""

from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class CapacityProviderStrategyItem(PropertyPart):
    capacity_provider: NonEmptyStr
    """e.g. FARGATE, FARGATE_SPOT, or an Auto Scaling group capacity provider."""
    weight: int = Field(default=0, ge=0)
    base: int = Field(default=0, ge=0)


class ECSClusterProperties(TypedProperties):
    type_key: Literal["ecs/cluster"] = "ecs/cluster"
    cluster_name: NonEmptyStr
    capacity_providers: list[NonEmptyStr] = Field(default_factory=list)
    default_capacity_provider_strategy: list[CapacityProviderStrategyItem] = Field(
        default_factory=list
    )


class ServiceLoadBalancer(PropertyPart):
    """A target group the service registers tasks with."""

    required_fields: ClassVar[frozenset[str]] = frozenset({"target_group_arn"})
    target_group_arn: NonEmptyStr | None = None
    container_name: NonEmptyStr
    container_port: int = Field(ge=1, le=65535)


class ServiceAutoScaling(PropertyPart):
    """Application Auto Scaling bounds registered for the service."""

    min_capacity: int = Field(ge=0)
    max_capacity: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min_capacity > self.max_capacity:
            raise ValueError("min_capacity must not exceed max_capacity")
        return self


class ECSServiceProperties(TypedProperties):
    type_key: Literal["ecs/service"] = "ecs/service"
    required_fields: ClassVar[frozenset[str]] = frozenset({"cluster_arn", "task_definition_arn"})
    service_name: NonEmptyStr
    cluster_arn: NonEmptyStr | None = None
    task_definition_arn: NonEmptyStr | None = None
    launch_type: Literal["FARGATE", "EC2", "EXTERNAL"] | None = None
    """None when the service uses a capacity provider strategy instead."""
    capacity_provider_strategy: list[CapacityProviderStrategyItem] = Field(default_factory=list)
    scheduling_strategy: Literal["REPLICA", "DAEMON"] = "REPLICA"
    desired_count: int = Field(ge=0)
    subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    assign_public_ip: bool | None = None
    load_balancers: list[ServiceLoadBalancer] = Field(default_factory=list)
    service_registry_arns: list[NonEmptyStr] = Field(default_factory=list)
    """Cloud Map registrations, where detected."""
    health_check_grace_period_seconds: int | None = Field(default=None, ge=0)
    deployment_minimum_healthy_percent: int | None = Field(default=None, ge=0)
    deployment_maximum_percent: int | None = Field(default=None, ge=0)
    deployment_circuit_breaker: bool | None = None
    auto_scaling: ServiceAutoScaling | None = None


class SecretReference(PropertyPart):
    """A secret injected into a container: the reference, never the value (spec §67)."""

    required_fields: ClassVar[frozenset[str]] = frozenset({"value_from"})
    name: NonEmptyStr
    """The environment variable name the secret is exposed as."""
    value_from: NonEmptyStr | None = None
    """ARN of a Secrets Manager secret or SSM parameter."""


class ContainerDefinition(PropertyPart):
    required_fields: ClassVar[frozenset[str]] = frozenset({"image"})
    name: NonEmptyStr
    image: NonEmptyStr | None = None
    """Image URI, e.g. 123456789012.dkr.ecr.ap-south-1.amazonaws.com/checkout:1.4."""
    essential: bool = True
    secrets: list[SecretReference] = Field(default_factory=list)
    environment_names: list[NonEmptyStr] = Field(default_factory=list)
    """Variable names only. Values are never stored; collectors keep only matched
    facts such as "DB_HOST matches the primary RDS endpoint" as evidence (spec §67)."""
    has_health_check: bool = False
    container_ports: list[int] = Field(default_factory=list)


class ECSTaskDefinitionProperties(TypedProperties):
    type_key: Literal["ecs/task-definition"] = "ecs/task-definition"
    required_fields: ClassVar[frozenset[str]] = frozenset({"revision"})
    family: NonEmptyStr
    revision: int | None = Field(default=None, ge=1)
    task_role_arn: str | None = None
    execution_role_arn: str | None = None
    network_mode: Literal["awsvpc", "bridge", "host", "none"] | None = None
    requires_compatibilities: list[Literal["FARGATE", "EC2", "EXTERNAL"]] = Field(
        default_factory=list
    )
    cpu: str | None = None
    memory: str | None = None
    containers: list[ContainerDefinition] = Field(min_length=1)
