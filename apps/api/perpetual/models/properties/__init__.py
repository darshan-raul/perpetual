"""Typed per-resource-type properties (spec §15.3).

`ResourceProperties` is a discriminated union: Pydantic reads `type_key` and picks
the matching model. `type_key` is `SERVICE/TYPE`, the same segment as in the
canonical resource ID (aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER).

To add a resource type: write its model with a unique `type_key` literal, then add
it to the union below.
"""

from typing import Annotated

from pydantic import Field

from perpetual.models.properties.awslambda import (
    LambdaEventSourceMappingProperties,
    LambdaFunctionProperties,
)
from perpetual.models.properties.base import TypedProperties
from perpetual.models.properties.ec2 import (
    AMIProperties,
    AutoScalingGroupProperties,
    BlockDeviceMapping,
    EC2InstanceProperties,
    LaunchTemplateProperties,
    LaunchTemplateRef,
)
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

ResourceProperties = Annotated[
    ECSClusterProperties
    | ECSServiceProperties
    | ECSTaskDefinitionProperties
    | EC2InstanceProperties
    | AutoScalingGroupProperties
    | LaunchTemplateProperties
    | AMIProperties
    | LambdaFunctionProperties
    | LambdaEventSourceMappingProperties,
    Field(discriminator="type_key"),
]
"""Any typed properties model, chosen by `type_key`."""

__all__ = [
    "AMIProperties",
    "AutoScalingGroupProperties",
    "BlockDeviceMapping",
    "CapacityProviderStrategyItem",
    "ContainerDefinition",
    "EC2InstanceProperties",
    "ECSClusterProperties",
    "ECSServiceProperties",
    "ECSTaskDefinitionProperties",
    "LambdaEventSourceMappingProperties",
    "LambdaFunctionProperties",
    "LaunchTemplateProperties",
    "LaunchTemplateRef",
    "ResourceProperties",
    "SecretReference",
    "ServiceAutoScaling",
    "ServiceLoadBalancer",
    "TypedProperties",
]
