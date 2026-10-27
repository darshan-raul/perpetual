"""Typed properties for AWS Backup (spec §8, §51).

Recovery points are what `restore_from_recovery_point` mechanisms restore from. A
point is usable for Region recovery only if it lives in a vault in the DR Region
(a cross-Region copy) and its key works there.
"""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class BackupVaultProperties(TypedProperties):
    type_key: Literal["backup/backup-vault"] = "backup/backup-vault"
    vault_name: NonEmptyStr
    kms_key_arn: str | None = None
    locked: bool = False
    """Vault Lock: recovery points cannot be deleted early."""
    recovery_point_count: int | None = Field(default=None, ge=0)


class BackupRecoveryPointProperties(TypedProperties):
    type_key: Literal["backup/recovery-point"] = "backup/recovery-point"
    recovery_point_arn: NonEmptyStr
    vault_name: NonEmptyStr
    protected_resource_arn: NonEmptyStr
    protected_resource_type: NonEmptyStr
    """e.g. RDS, Aurora, DynamoDB, EBS, EFS, S3."""
    status: Literal[
        "CREATING", "COMPLETED", "PARTIAL", "DELETING", "EXPIRED", "AVAILABLE", "STOPPED"
    ]
    created_at: AwareDatetime
    """Its age bounds the RPO of a restore from it (spec §51)."""
    completed_at: AwareDatetime | None = None
    source_vault_arn: str | None = None
    """Set when this point is a copy from another vault, e.g. a cross-Region copy."""
    encrypted: bool = True
    kms_key_arn: str | None = None
    delete_after_days: int | None = Field(default=None, ge=1)
    size_bytes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _completed_after_created(self) -> Self:
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("completed_at must not be before created_at")
        return self
