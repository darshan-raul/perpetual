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
from perpetual.models.properties.backup import (
    BackupRecoveryPointProperties,
    BackupVaultProperties,
)
from perpetual.models.properties.base import TypedProperties
from perpetual.models.properties.dynamodb import DynamoDBBackupProperties, DynamoDBTableProperties
from perpetual.models.properties.ebs import EBSSnapshotProperties, EBSVolumeProperties
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
from perpetual.models.properties.efs import EFSFileSystemProperties, EFSReplicationDestination
from perpetual.models.properties.rds import (
    AuroraClusterProperties,
    RDSInstanceProperties,
    RDSSnapshotProperties,
)
from perpetual.models.properties.s3 import S3BucketProperties, S3ReplicationRule

ResourceProperties = Annotated[
    ECSClusterProperties
    | ECSServiceProperties
    | ECSTaskDefinitionProperties
    | EC2InstanceProperties
    | AutoScalingGroupProperties
    | LaunchTemplateProperties
    | AMIProperties
    | LambdaFunctionProperties
    | LambdaEventSourceMappingProperties
    | RDSInstanceProperties
    | AuroraClusterProperties
    | RDSSnapshotProperties
    | DynamoDBTableProperties
    | DynamoDBBackupProperties
    | S3BucketProperties
    | EBSVolumeProperties
    | EBSSnapshotProperties
    | EFSFileSystemProperties
    | BackupVaultProperties
    | BackupRecoveryPointProperties,
    Field(discriminator="type_key"),
]
"""Any typed properties model, chosen by `type_key`."""

__all__ = [
    "AMIProperties",
    "AuroraClusterProperties",
    "AutoScalingGroupProperties",
    "BackupRecoveryPointProperties",
    "BackupVaultProperties",
    "BlockDeviceMapping",
    "CapacityProviderStrategyItem",
    "ContainerDefinition",
    "DynamoDBBackupProperties",
    "DynamoDBTableProperties",
    "EBSSnapshotProperties",
    "EBSVolumeProperties",
    "EC2InstanceProperties",
    "ECSClusterProperties",
    "ECSServiceProperties",
    "ECSTaskDefinitionProperties",
    "EFSFileSystemProperties",
    "EFSReplicationDestination",
    "LambdaEventSourceMappingProperties",
    "LambdaFunctionProperties",
    "LaunchTemplateProperties",
    "LaunchTemplateRef",
    "RDSInstanceProperties",
    "RDSSnapshotProperties",
    "ResourceProperties",
    "S3BucketProperties",
    "S3ReplicationRule",
    "SecretReference",
    "ServiceAutoScaling",
    "ServiceLoadBalancer",
    "TypedProperties",
]
