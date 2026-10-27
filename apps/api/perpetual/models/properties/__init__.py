"""Typed per-resource-type properties (spec §15.3).

`ResourceProperties` is a discriminated union: Pydantic reads `type_key` and picks
the matching model. `type_key` is `SERVICE/TYPE`, the same segment as in the
canonical resource ID (aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER), and follows
the service name in the resource's ARN (so EBS is `ec2/volume`).

To add a resource type: write its model with a unique `type_key` literal in the
file for its service, import it here and add it to the union below.
"""

import typing
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
from perpetual.models.properties.base import PropertyPart, TypedProperties
from perpetual.models.properties.dynamodb import (
    DynamoDBBackupProperties,
    DynamoDBReplica,
    DynamoDBTableProperties,
)
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
from perpetual.models.properties.edge import (
    ACMCertificateProperties,
    AliasTarget,
    CloudFrontDistributionProperties,
    CloudFrontOrigin,
    CloudFrontOriginGroup,
    HealthCheckProperties,
    HostedZoneProperties,
    RecordSetProperties,
    WebACLProperties,
)
from perpetual.models.properties.efs import EFSFileSystemProperties, EFSReplicationDestination
from perpetual.models.properties.elb import (
    ListenerProperties,
    LoadBalancerProperties,
    TargetGroupProperties,
)
from perpetual.models.properties.messaging import (
    SNSSubscriptionProperties,
    SNSTopicProperties,
    SQSQueueProperties,
)
from perpetual.models.properties.network import (
    InternetGatewayProperties,
    NATGatewayProperties,
    Route,
    RouteTableProperties,
    SecurityGroupProperties,
    SecurityGroupRule,
    SubnetProperties,
    TransitGatewayAttachmentProperties,
    VPCEndpointProperties,
    VPCProperties,
)
from perpetual.models.properties.other import (
    CodePipelineProperties,
    ExternalResourceProperties,
    GenericResourceProperties,
)
from perpetual.models.properties.rds import (
    AuroraClusterProperties,
    RDSInstanceProperties,
    RDSSnapshotProperties,
)
from perpetual.models.properties.recovery_control import (
    IdentityCenterInstanceProperties,
    ReadinessCheckProperties,
    RegionSwitchPlanProperties,
    RegionSwitchStep,
    RegionSwitchWorkflow,
    RoutingControlProperties,
)
from perpetual.models.properties.s3 import S3BucketProperties, S3ReplicationRule
from perpetual.models.properties.supporting import (
    ECRImageProperties,
    ECRRegistryProperties,
    ECRReplicationDestination,
    ECRReplicationRule,
    ECRRepositoryProperties,
    IAMPolicyProperties,
    IAMRoleProperties,
    KMSKeyProperties,
    LogGroupProperties,
    PolicyStatement,
    SecretProperties,
    SecretReplica,
    SSMParameterProperties,
)

ResourceProperties = Annotated[
    # Compute and containers (P0-04b)
    ECSClusterProperties
    | ECSServiceProperties
    | ECSTaskDefinitionProperties
    | EC2InstanceProperties
    | AutoScalingGroupProperties
    | LaunchTemplateProperties
    | AMIProperties
    | LambdaFunctionProperties
    | LambdaEventSourceMappingProperties
    # Data and storage (P0-04c)
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
    | BackupRecoveryPointProperties
    # Messaging (P0-04d)
    | SQSQueueProperties
    | SNSTopicProperties
    | SNSSubscriptionProperties
    # Network (P0-04d)
    | VPCProperties
    | SubnetProperties
    | SecurityGroupProperties
    | RouteTableProperties
    | NATGatewayProperties
    | InternetGatewayProperties
    | VPCEndpointProperties
    | TransitGatewayAttachmentProperties
    # Load balancing (P0-04d)
    | LoadBalancerProperties
    | ListenerProperties
    | TargetGroupProperties
    # Edge: DNS, CDN, certificates, WAF (P0-04d)
    | HostedZoneProperties
    | RecordSetProperties
    | HealthCheckProperties
    | CloudFrontDistributionProperties
    | ACMCertificateProperties
    | WebACLProperties
    # Supporting services (P0-04d)
    | ECRRepositoryProperties
    | ECRRegistryProperties
    | ECRImageProperties
    | SecretProperties
    | SSMParameterProperties
    | KMSKeyProperties
    | IAMRoleProperties
    | IAMPolicyProperties
    | LogGroupProperties
    # Recovery control and operator access (P0-04d)
    | RoutingControlProperties
    | RegionSwitchPlanProperties
    | ReadinessCheckProperties
    | IdentityCenterInstanceProperties
    # Out of scope, external and fallback (P0-04e)
    | CodePipelineProperties
    | ExternalResourceProperties
    | GenericResourceProperties,
    Field(discriminator="type_key"),
]
"""Any typed properties model, chosen by `type_key`."""

_FALLBACK_MODELS = (ExternalResourceProperties, GenericResourceProperties)

SPECIFIC_TYPE_KEYS: frozenset[str] = frozenset(
    key
    for model in typing.get_args(typing.get_args(ResourceProperties)[0])
    if model not in _FALLBACK_MODELS
    for key in typing.get_args(model.model_fields["type_key"].annotation)
)
"""Every `service/type` that has its own typed model. The generic fallback is not
allowed for these, so it can never be used to skip a type's validation."""

__all__ = [
    "SPECIFIC_TYPE_KEYS",
    "ACMCertificateProperties",
    "AMIProperties",
    "AliasTarget",
    "AuroraClusterProperties",
    "AutoScalingGroupProperties",
    "BackupRecoveryPointProperties",
    "BackupVaultProperties",
    "BlockDeviceMapping",
    "CapacityProviderStrategyItem",
    "CloudFrontDistributionProperties",
    "CloudFrontOrigin",
    "CloudFrontOriginGroup",
    "CodePipelineProperties",
    "ContainerDefinition",
    "DynamoDBBackupProperties",
    "DynamoDBReplica",
    "DynamoDBTableProperties",
    "EBSSnapshotProperties",
    "EBSVolumeProperties",
    "EC2InstanceProperties",
    "ECRImageProperties",
    "ECRRegistryProperties",
    "ECRReplicationDestination",
    "ECRReplicationRule",
    "ECRRepositoryProperties",
    "ECSClusterProperties",
    "ECSServiceProperties",
    "ECSTaskDefinitionProperties",
    "EFSFileSystemProperties",
    "EFSReplicationDestination",
    "ExternalResourceProperties",
    "GenericResourceProperties",
    "HealthCheckProperties",
    "HostedZoneProperties",
    "IAMPolicyProperties",
    "IAMRoleProperties",
    "IdentityCenterInstanceProperties",
    "InternetGatewayProperties",
    "KMSKeyProperties",
    "LambdaEventSourceMappingProperties",
    "LambdaFunctionProperties",
    "LaunchTemplateProperties",
    "LaunchTemplateRef",
    "ListenerProperties",
    "LoadBalancerProperties",
    "LogGroupProperties",
    "NATGatewayProperties",
    "PolicyStatement",
    "PropertyPart",
    "RDSInstanceProperties",
    "RDSSnapshotProperties",
    "ReadinessCheckProperties",
    "RecordSetProperties",
    "RegionSwitchPlanProperties",
    "RegionSwitchStep",
    "RegionSwitchWorkflow",
    "ResourceProperties",
    "Route",
    "RouteTableProperties",
    "RoutingControlProperties",
    "S3BucketProperties",
    "S3ReplicationRule",
    "SNSSubscriptionProperties",
    "SNSTopicProperties",
    "SQSQueueProperties",
    "SSMParameterProperties",
    "SecretProperties",
    "SecretReference",
    "SecretReplica",
    "SecurityGroupProperties",
    "SecurityGroupRule",
    "ServiceAutoScaling",
    "ServiceLoadBalancer",
    "SubnetProperties",
    "TargetGroupProperties",
    "TransitGatewayAttachmentProperties",
    "TypedProperties",
    "VPCEndpointProperties",
    "VPCProperties",
    "WebACLProperties",
]
