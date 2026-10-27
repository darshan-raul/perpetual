"""Properties for resources Perpetual does not model in detail (spec §15.2, §24.1).

- External dependencies: third-party SaaS, on-premise systems, other clouds. Users
  declare them (spec §15.2); their DR posture is whatever the user declares, and
  undeclared means UNKNOWN.
- Generic AWS resources: types without a typed model (e.g. ElastiCache in v0.1).
  They stay in the graph so nothing silently disappears, but no rule reads their
  configuration; their recovery mechanism is unknown unless the user confirms one.
- CodePipeline: CI/CD is out of RTO scope by default (spec §24.1), unless the
  recovery plan uses the pipeline to deploy the DR side.

`ExternalResourceProperties` and `GenericResourceProperties` are the two exceptions
to "type_key matches the node's service/type"; `ResourceNode` checks them its own way.
"""

from typing import ClassVar, Literal

from pydantic import Field

from perpetual.models.common import NonEmptyStr
from perpetual.models.override import DrPosture
from perpetual.models.properties.base import TypedProperties


class ExternalResourceProperties(TypedProperties):
    """A dependency outside AWS discovery. Valid only on nodes with provider "external"."""

    type_key: Literal["external/dependency"] = "external/dependency"
    dr_posture: DrPosture = DrPosture.UNKNOWN
    """Declared by the user. UNKNOWN until they say otherwise (spec §15.2)."""
    description: str | None = None
    endpoints: list[NonEmptyStr] = Field(default_factory=list)
    """Hostnames used to match configuration references; never credentials or URLs with tokens."""


class GenericResourceProperties(TypedProperties):
    """Fallback for an AWS resource type with no typed model. Not allowed when one exists."""

    type_key: Literal["generic/resource"] = "generic/resource"
    terraform_type: str | None = None
    """e.g. aws_elasticache_replication_group, when the resource came from Terraform."""
    cloudformation_type: str | None = None
    """e.g. AWS::ElastiCache::ReplicationGroup, when known."""


class CodePipelineProperties(TypedProperties):
    """A delivery pipeline. Out of RTO scope by default (spec §24.1)."""

    type_key: Literal["codepipeline/pipeline"] = "codepipeline/pipeline"
    required_fields: ClassVar[frozenset[str]] = frozenset({"role_arn"})
    pipeline_name: NonEmptyStr
    role_arn: NonEmptyStr | None = None
    stage_names: list[NonEmptyStr] = Field(default_factory=list)
    action_providers: list[NonEmptyStr] = Field(default_factory=list)
    """e.g. CodeBuild, ECS, CloudFormation, S3. Shows what the pipeline deploys."""
    action_regions: list[NonEmptyStr] = Field(default_factory=list)
    """Regions its actions run in. A pipeline that deploys to the DR Region and is used
    by the recovery plan is in RTO scope (spec §24.1)."""
    artifact_bucket: str | None = None
