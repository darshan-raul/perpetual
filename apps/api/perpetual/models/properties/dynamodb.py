"""Typed properties for DynamoDB (spec §6.3). Initial support only.

Regional recovery for a table comes from a Global Tables replica in the DR Region,
or a restore from point-in-time recovery (PITR) or a backup.
"""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class DynamoDBTableProperties(TypedProperties):
    type_key: Literal["dynamodb/table"] = "dynamodb/table"
    table_name: NonEmptyStr
    status: str | None = None
    billing_mode: Literal["PROVISIONED", "PAY_PER_REQUEST"] | None = None
    table_class: Literal["STANDARD", "STANDARD_INFREQUENT_ACCESS"] | None = None
    pitr_enabled: bool | None = None
    """None when the continuous-backup status could not be read."""
    latest_restorable_time: AwareDatetime | None = None
    global_table_version: Literal["2017.11.29", "2019.11.21"] | None = None
    replica_regions: list[NonEmptyStr] = Field(default_factory=list)
    """Other Regions holding a Global Tables replica of this table."""
    stream_enabled: bool = False
    stream_view_type: str | None = None
    sse_type: Literal["AWS_OWNED", "AES256", "KMS"] | None = None
    kms_key_arn: str | None = None
    global_secondary_index_names: list[NonEmptyStr] = Field(default_factory=list)
    local_secondary_index_names: list[NonEmptyStr] = Field(default_factory=list)
    item_count: int | None = Field(default=None, ge=0)
    table_size_bytes: int | None = Field(default=None, ge=0)
    deletion_protection: bool = False

    @model_validator(mode="after")
    def _replicas_mean_a_global_table(self) -> Self:
        if self.replica_regions and self.is_missing("global_table_version"):
            raise ValueError("a table with replica_regions is a global table: set its version")
        return self


class DynamoDBBackupProperties(TypedProperties):
    """An on-demand or AWS Backup backup of a table."""

    type_key: Literal["dynamodb/backup"] = "dynamodb/backup"
    backup_name: NonEmptyStr
    table_name: NonEmptyStr
    backup_type: Literal["USER", "SYSTEM", "AWS_BACKUP"]
    status: Literal["CREATING", "DELETED", "AVAILABLE"] | None = None
    created_at: AwareDatetime | None = None
    size_bytes: int | None = Field(default=None, ge=0)
