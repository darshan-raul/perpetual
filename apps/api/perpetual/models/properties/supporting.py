"""Typed properties for ECR, Secrets Manager, SSM, KMS, IAM and CloudWatch Logs (spec §8).

These are the "supporting" resources a service needs to start: its image, its
secrets and parameters, its keys, its roles and its log group. Each one is
Regional except IAM, so each needs a DR-side answer.

Secret and parameter values are never stored (spec §67); only metadata is.
"""

from typing import ClassVar, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class ECRRepositoryProperties(TypedProperties):
    type_key: Literal["ecr/repository"] = "ecr/repository"
    required_fields: ClassVar[frozenset[str]] = frozenset({"repository_uri"})
    repository_name: NonEmptyStr
    repository_uri: NonEmptyStr | None = None
    """Contains the Region, e.g. 1.dkr.ecr.ap-south-1.amazonaws.com/checkout."""
    image_tag_mutability: Literal["MUTABLE", "IMMUTABLE"] | None = None
    encryption_type: Literal["AES256", "KMS", "KMS_DSSE"] | None = None
    kms_key_arn: str | None = None


class ECRReplicationDestination(PropertyPart):
    region: NonEmptyStr
    registry_id: NonEmptyStr
    """The destination account."""


class ECRReplicationRule(PropertyPart):
    destinations: list[ECRReplicationDestination] = Field(min_length=1)
    repository_prefixes: list[NonEmptyStr] = Field(default_factory=list)
    """Empty means every repository."""


class ECRRegistryProperties(TypedProperties):
    """The account's registry in one Region. Replication is configured here, once per
    registry, not per repository, so a PR touching it may conflict with other owners."""

    type_key: Literal["ecr/registry"] = "ecr/registry"
    required_fields: ClassVar[frozenset[str]] = frozenset({"registry_id"})
    registry_id: NonEmptyStr | None = None
    replication_rules: list[ECRReplicationRule] = Field(default_factory=list)


class ECRImageProperties(TypedProperties):
    """One image in one Region. An image referenced by digest must exist in the DR
    Region's registry for a task or pod to start there."""

    type_key: Literal["ecr/image"] = "ecr/image"
    repository_name: NonEmptyStr
    image_digest: NonEmptyStr
    image_tags: list[NonEmptyStr] = Field(default_factory=list)
    pushed_at: AwareDatetime | None = None
    size_bytes: int | None = Field(default=None, ge=0)


class SecretReplica(PropertyPart):
    region: NonEmptyStr
    kms_key_id: str | None = None
    status: Literal["InSync", "Failed", "InProgress"] | None = None


class SecretProperties(TypedProperties):
    """Secrets Manager metadata. The value is never read (GetSecretValue is never called)."""

    type_key: Literal["secretsmanager/secret"] = "secretsmanager/secret"
    name: NonEmptyStr
    kms_key_id: str | None = None
    rotation_enabled: bool = False
    rotation_lambda_arn: str | None = None
    replicas: list[SecretReplica] = Field(default_factory=list)
    primary_region: str | None = None
    """Set when this secret is itself a replica of a secret in another Region."""
    last_changed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _replica_regions_distinct(self) -> Self:
        regions = [replica.region for replica in self.replicas]
        if len(set(regions)) != len(regions):
            raise ValueError("a secret has at most one replica per Region")
        return self


class SSMParameterProperties(TypedProperties):
    """SSM parameter metadata. The value is never stored. SSM has no cross-Region
    replication, so DR copies come from a prerequisite script (spec §63.1)."""

    type_key: Literal["ssm/parameter"] = "ssm/parameter"
    name: NonEmptyStr
    parameter_type: Literal["String", "StringList", "SecureString"]
    kms_key_id: str | None = None
    version: int | None = Field(default=None, ge=1)
    last_modified_at: AwareDatetime | None = None
    """Compared across Regions to spot a stale DR copy (SSM-PARITY-001), without values."""
    tier: Literal["Standard", "Advanced", "Intelligent-Tiering"] | None = None

    @model_validator(mode="after")
    def _kms_only_for_secure_strings(self) -> Self:
        if self.kms_key_id and self.parameter_type != "SecureString":
            raise ValueError("only SecureString parameters are encrypted with KMS")
        return self


class KMSKeyProperties(TypedProperties):
    """A KMS key. Keys are Regional: data encrypted with a single-Region key can't
    be decrypted in the DR Region (XREG-KMS-003). Multi-Region keys share key
    material across Regions."""

    type_key: Literal["kms/key"] = "kms/key"
    required_fields: ClassVar[frozenset[str]] = frozenset({"key_id"})
    key_id: NonEmptyStr | None = None
    key_state: str | None = None
    key_manager: Literal["AWS", "CUSTOMER"] = "CUSTOMER"
    key_usage: str | None = None
    multi_region: bool = False
    multi_region_role: Literal["PRIMARY", "REPLICA"] | None = None
    primary_key_arn: str | None = None
    replica_regions: list[NonEmptyStr] = Field(default_factory=list)
    aliases: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _multi_region_fields_agree(self) -> Self:
        if not self.is_unknown("multi_region_role") and self.multi_region != (
            self.multi_region_role is not None
        ):
            raise ValueError("multi_region_role is set exactly for multi-Region keys")
        if self.multi_region_role == "REPLICA" and self.is_missing("primary_key_arn"):
            raise ValueError("a replica key names its primary_key_arn")
        if not self.multi_region and self.replica_regions:
            raise ValueError("only multi-Region keys have replica Regions")
        return self


class PolicyStatement(PropertyPart):
    """One IAM policy statement, structured so rules can check resource ARNs.

    Rules use it to find a DR role whose policy grants only primary-Region ARNs
    (XREG-IAM-002). Statements with Resource "*" are kept but carry no weight as
    dependency evidence (spec §22).
    """

    effect: Literal["Allow", "Deny"]
    actions: list[NonEmptyStr] = Field(default_factory=list)
    not_actions: list[NonEmptyStr] = Field(default_factory=list)
    resources: list[NonEmptyStr] = Field(default_factory=list)
    not_resources: list[NonEmptyStr] = Field(default_factory=list)
    has_conditions: bool = False

    @model_validator(mode="after")
    def _has_actions(self) -> Self:
        if not self.actions and not self.not_actions:
            raise ValueError("a statement has actions or not_actions")
        return self


class IAMRoleProperties(TypedProperties):
    type_key: Literal["iam/role"] = "iam/role"
    role_name: NonEmptyStr
    path: str = "/"
    trusted_principals: list[NonEmptyStr] = Field(default_factory=list)
    """Who may assume the role, e.g. ecs-tasks.amazonaws.com or an OIDC provider ARN."""
    attached_policy_arns: list[NonEmptyStr] = Field(default_factory=list)
    inline_policy_statements: list[PolicyStatement] = Field(default_factory=list)
    instance_profile_arns: list[NonEmptyStr] = Field(default_factory=list)


class IAMPolicyProperties(TypedProperties):
    """A customer-managed policy: the statements of its default version."""

    type_key: Literal["iam/policy"] = "iam/policy"
    policy_name: NonEmptyStr
    default_version_id: str | None = None
    statements: list[PolicyStatement] = Field(default_factory=list)
    attachment_count: int | None = Field(default=None, ge=0)


class LogGroupProperties(TypedProperties):
    """Out of RTO scope by default (spec §24.1) but assessed under Observability."""

    type_key: Literal["logs/log-group"] = "logs/log-group"
    log_group_name: NonEmptyStr
    retention_days: int | None = Field(default=None, ge=1)
    """None means logs are kept forever."""
    kms_key_id: str | None = None
    subscription_destination_arns: list[NonEmptyStr] = Field(default_factory=list)
    stored_bytes: int | None = Field(default=None, ge=0)
