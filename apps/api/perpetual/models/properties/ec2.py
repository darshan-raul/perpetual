"""Typed properties for EC2, Auto Scaling, launch templates and AMIs (spec §5.3).

These carry the chain the EC2 rules follow to decide whether instances can launch
in the DR Region:

    Auto Scaling group -> launch template -> AMI -> EBS snapshot -> KMS key

An AMI is Regional, and its snapshots are only usable in the DR Region if the
image was copied there and the snapshot's KMS key can be used there.
"""

from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class BlockDeviceMapping(PropertyPart):
    device_name: NonEmptyStr
    snapshot_id: str | None = None
    volume_size_gib: int | None = Field(default=None, ge=1)
    encrypted: bool | None = None
    kms_key_id: str | None = None
    """KMS key ARN or ID. Decides whether a copy can be decrypted in the DR Region."""


class EC2InstanceProperties(TypedProperties):
    type_key: Literal["ec2/instance"] = "ec2/instance"
    required_fields: ClassVar[frozenset[str]] = frozenset({"image_id", "instance_id", "state"})
    instance_id: NonEmptyStr | None = None
    instance_type: NonEmptyStr
    image_id: NonEmptyStr | None = None
    state: (
        Literal["pending", "running", "stopping", "stopped", "shutting-down", "terminated"] | None
    ) = None
    lifecycle: Literal["on-demand", "spot", "scheduled", "capacity-block"] = "on-demand"
    subnet_id: str | None = None
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    iam_instance_profile_arn: str | None = None
    ebs_volume_ids: list[NonEmptyStr] = Field(default_factory=list)
    auto_scaling_group_name: str | None = None
    """Set when the instance belongs to an Auto Scaling group."""
    launch_template_id: str | None = None


class LaunchTemplateRef(PropertyPart):
    required_fields: ClassVar[frozenset[str]] = frozenset({"launch_template_id", "version"})
    launch_template_id: NonEmptyStr | None = None
    version: NonEmptyStr | None = None
    """A number, or "$Default" / "$Latest"."""


class AutoScalingGroupProperties(TypedProperties):
    type_key: Literal["autoscaling/group"] = "autoscaling/group"
    group_name: NonEmptyStr
    min_size: int = Field(ge=0)
    max_size: int = Field(ge=0)
    desired_capacity: int = Field(ge=0)
    launch_template: LaunchTemplateRef | None = None
    instance_types: list[NonEmptyStr] = Field(default_factory=list)
    """Types allowed by a mixed-instances policy, if any."""
    on_demand_base_capacity: int | None = Field(default=None, ge=0)
    subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    target_group_arns: list[NonEmptyStr] = Field(default_factory=list)
    health_check_type: Literal["EC2", "ELB"] = "EC2"

    @model_validator(mode="after")
    def _sizes_ordered(self) -> Self:
        # AWS rejects a group whose desired capacity is outside [min, max]; a value
        # like that here means a broken import, not a real group.
        if not self.min_size <= self.desired_capacity <= self.max_size:
            raise ValueError("Auto Scaling sizes must satisfy min <= desired <= max")
        return self


class LaunchTemplateProperties(TypedProperties):
    type_key: Literal["ec2/launch-template"] = "ec2/launch-template"
    required_fields: ClassVar[frozenset[str]] = frozenset({"version"})
    launch_template_name: NonEmptyStr
    version: int | None = Field(default=None, ge=1)
    image_id: str | None = None
    image_ssm_parameter: str | None = None
    """Set when the AMI is resolved from an SSM parameter (resolve:ssm:...). The
    parameter must exist in the DR Region for the template to work there."""
    instance_type: str | None = None
    iam_instance_profile_arn: str | None = None
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    block_device_mappings: list[BlockDeviceMapping] = Field(default_factory=list)
    has_user_data: bool = False
    """Whether user data exists. Its content is never stored: it often holds credentials."""

    @model_validator(mode="after")
    def _one_image_source(self) -> Self:
        if self.image_id and self.image_ssm_parameter:
            raise ValueError("a launch template takes image_id or image_ssm_parameter, not both")
        return self


class AMIProperties(TypedProperties):
    type_key: Literal["ec2/image"] = "ec2/image"
    required_fields: ClassVar[frozenset[str]] = frozenset({"image_id", "owner_id", "state"})
    image_id: NonEmptyStr | None = None
    name: str | None = None
    owner_id: NonEmptyStr | None = None
    state: Literal["pending", "available", "invalid", "deregistered", "failed", "error"] | None = (
        None
    )
    architecture: str | None = None
    root_device_type: Literal["ebs", "instance-store"] = "ebs"
    block_device_mappings: list[BlockDeviceMapping] = Field(default_factory=list)
