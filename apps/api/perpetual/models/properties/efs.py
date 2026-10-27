"""Typed properties for EFS (spec §7).

Regional recovery comes from EFS replication to a file system in the DR Region.
The replica is read-only until failover deletes the replication configuration;
the typical RPO is 15 minutes (spec §63.2).

The `type_key` uses `elasticfilesystem`, the service name in EFS ARNs.
"""

from typing import ClassVar, Literal

from pydantic import AwareDatetime, Field

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class EFSReplicationDestination(PropertyPart):
    required_fields: ClassVar[frozenset[str]] = frozenset({"status"})
    region: NonEmptyStr
    file_system_id: str | None = None
    status: Literal["ENABLED", "ENABLING", "DELETING", "ERROR", "PAUSED", "PAUSING"] | None = None
    last_replicated_at: AwareDatetime | None = None
    """When the last sync finished. Its age bounds RPO."""


class EFSFileSystemProperties(TypedProperties):
    type_key: Literal["elasticfilesystem/file-system"] = "elasticfilesystem/file-system"
    required_fields: ClassVar[frozenset[str]] = frozenset({"file_system_id"})
    file_system_id: NonEmptyStr | None = None
    lifecycle_state: str | None = None
    performance_mode: Literal["generalPurpose", "maxIO"] | None = None
    throughput_mode: Literal["bursting", "provisioned", "elastic"] | None = None
    encrypted: bool = False
    kms_key_id: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    mount_target_subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    mount_target_security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    replication_destinations: list[EFSReplicationDestination] = Field(default_factory=list)
    replication_overwrite_protection: Literal["ENABLED", "DISABLED", "REPLICATING"] | None = None
    """REPLICATING means this file system is itself a read-only replica."""
    automatic_backups: bool | None = None
