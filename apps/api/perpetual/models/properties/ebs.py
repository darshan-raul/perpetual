"""Typed properties for EBS volumes and snapshots (spec §7, §42).

Volumes are tied to one Availability Zone and snapshots to one Region. Recovering
a volume in the DR Region needs a snapshot copied there, encrypted with a key that
works there. EBS matters most for EKS persistent volumes (spec §40).

The `type_key` uses `ec2`, the service name in EBS ARNs.
"""

from typing import ClassVar, Literal

from pydantic import AwareDatetime, Field

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class EBSVolumeProperties(TypedProperties):
    type_key: Literal["ec2/volume"] = "ec2/volume"
    required_fields: ClassVar[frozenset[str]] = frozenset({"size_gib", "volume_id"})
    volume_id: NonEmptyStr | None = None
    size_gib: int | None = Field(default=None, ge=1)
    volume_type: str | None = None
    iops: int | None = Field(default=None, ge=0)
    throughput_mibps: int | None = Field(default=None, ge=0)
    state: Literal["creating", "available", "in-use", "deleting", "deleted", "error"] | None = None
    encrypted: bool = False
    kms_key_id: str | None = None
    created_from_snapshot_id: str | None = None
    attached_instance_ids: list[NonEmptyStr] = Field(default_factory=list)


class EBSSnapshotProperties(TypedProperties):
    type_key: Literal["ec2/snapshot"] = "ec2/snapshot"
    required_fields: ClassVar[frozenset[str]] = frozenset({"snapshot_id"})
    snapshot_id: NonEmptyStr | None = None
    volume_id: str | None = None
    """The source volume, when known. Copied snapshots point at a placeholder volume."""
    volume_size_gib: int | None = Field(default=None, ge=1)
    state: Literal["pending", "completed", "error", "recoverable", "recovering"] | None = None
    started_at: AwareDatetime | None = None
    """Its age bounds the RPO of a restore from it (spec §51)."""
    encrypted: bool = False
    kms_key_id: str | None = None
