"""Typed properties for S3 (spec §7, §51).

Regional recovery for a bucket comes from cross-Region replication (CRR) to a
bucket in the DR Region. Replication copies only objects written after the rule
exists; older objects need a one-off Batch Replication job (spec §63.1).
"""

from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class S3ReplicationRule(PropertyPart):
    required_fields: ClassVar[frozenset[str]] = frozenset({"destination_bucket_arn"})
    rule_id: NonEmptyStr
    status: Literal["Enabled", "Disabled"]
    destination_bucket_arn: NonEmptyStr | None = None
    destination_account_id: str | None = None
    destination_storage_class: str | None = None
    prefix: str | None = None
    """None or empty means the whole bucket."""
    replicate_kms_encrypted_objects: bool = False
    """Without this, SSE-KMS objects are silently not replicated."""
    replica_kms_key_id: str | None = None
    """Key used to encrypt replicas in the destination Region."""
    replication_time_control: bool = False
    """S3 RTC: a 15-minute replication SLA, which bounds RPO."""
    delete_marker_replication: bool = False


class S3BucketProperties(TypedProperties):
    type_key: Literal["s3/bucket"] = "s3/bucket"
    required_fields: ClassVar[frozenset[str]] = frozenset({"versioning"})
    bucket_name: NonEmptyStr
    versioning: Literal["Enabled", "Suspended", "Disabled"] | None = None
    """Disabled means versioning was never turned on."""
    replication_role_arn: str | None = None
    replication_rules: list[S3ReplicationRule] = Field(default_factory=list)
    default_encryption: Literal["SSE-S3", "SSE-KMS", "DSSE-KMS"] | None = None
    kms_key_arn: str | None = None
    bucket_key_enabled: bool = False
    object_ownership: (
        Literal["BucketOwnerEnforced", "BucketOwnerPreferred", "ObjectWriter"] | None
    ) = None
    object_lock_enabled: bool = False
    lifecycle_rule_count: int = Field(default=0, ge=0)
    size_bytes: int | None = Field(default=None, ge=0)
    object_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _replication_prerequisites(self) -> Self:
        # S3 requires versioning and a replication role before any rule can exist,
        # so rules without them mean a broken import.
        if self.replication_rules:
            # Versioning is often a separate Terraform resource, so it may be unknown
            # in a plan; a known value must be Enabled.
            if self.versioning is not None and self.versioning != "Enabled":
                raise ValueError("S3 replication requires versioning Enabled")
            if self.is_missing("replication_role_arn"):
                raise ValueError("S3 replication requires a replication_role_arn")
        rule_ids = [rule.rule_id for rule in self.replication_rules]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("replication rule IDs must be distinct")
        return self
