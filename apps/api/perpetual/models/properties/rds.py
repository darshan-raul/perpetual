"""Typed properties for RDS and Aurora (spec §6.1, §6.2, §41, §42).

Multi-AZ protects against an Availability Zone failure. It is not cross-Region
disaster recovery, and the rules must never treat it as one (spec §6.1). Regional
recovery comes from a cross-Region replica, an Aurora Global Database secondary,
or a restore from a recovery point copied to the DR Region.
"""

from typing import ClassVar, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class RDSInstanceProperties(TypedProperties):
    """A DB instance: standalone (MySQL, PostgreSQL, MariaDB) or a member of an Aurora cluster."""

    type_key: Literal["rds/db"] = "rds/db"
    db_instance_identifier: NonEmptyStr
    engine: NonEmptyStr
    """e.g. mysql, postgres, mariadb, aurora-mysql, aurora-postgresql."""
    engine_version: str | None = None
    instance_class: NonEmptyStr
    status: str | None = None
    db_cluster_identifier: str | None = None
    """Set for Aurora instances: the cluster holds the data and the recovery settings."""
    allocated_storage_gib: int | None = Field(default=None, ge=0)
    storage_type: str | None = None
    iops: int | None = Field(default=None, ge=0)
    storage_throughput_mibps: int | None = Field(default=None, ge=0)
    multi_az: bool = False
    """AZ resilience only; says nothing about Region failure."""
    backup_retention_days: int = Field(default=0, ge=0)
    """0 means automated backups are off, so there is no point-in-time restore."""
    latest_restorable_time: AwareDatetime | None = None
    replicated_automated_backup_regions: list[NonEmptyStr] = Field(default_factory=list)
    """Regions that receive this instance's automated backups (cross-Region backup)."""
    read_replica_source_arn: str | None = None
    """Set when this instance is itself a read replica."""
    read_replica_arns: list[NonEmptyStr] = Field(default_factory=list)
    """This instance's replicas, including cross-Region ones."""
    db_subnet_group_name: str | None = None
    vpc_security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    storage_encrypted: bool = False
    kms_key_id: str | None = None
    parameter_group_names: list[NonEmptyStr] = Field(default_factory=list)
    option_group_names: list[NonEmptyStr] = Field(default_factory=list)
    deletion_protection: bool = False

    @model_validator(mode="after")
    def _aurora_instances_belong_to_a_cluster(self) -> Self:
        # Aurora keeps data and recovery settings on the cluster, so an Aurora
        # instance without one cannot be assessed.
        if self.engine.startswith("aurora") and self.is_missing("db_cluster_identifier"):
            raise ValueError("an Aurora instance belongs to a cluster: set db_cluster_identifier")
        return self


class AuroraClusterProperties(TypedProperties):
    type_key: Literal["rds/cluster"] = "rds/cluster"
    db_cluster_identifier: NonEmptyStr
    engine: Literal["aurora-mysql", "aurora-postgresql"]
    engine_version: str | None = None
    status: str | None = None
    member_instance_identifiers: list[NonEmptyStr] = Field(default_factory=list)
    writer_instance_identifier: str | None = None
    """None for a Global Database secondary cluster, which has no writer."""
    global_cluster_identifier: str | None = None
    global_cluster_role: Literal["primary", "secondary"] | None = None
    """Role in an Aurora Global Database. A secondary is the promotion path in DR."""
    replication_source_arn: str | None = None
    """Set for a cross-Region read replica cluster (the pre-Global-Database way)."""
    backup_retention_days: int = Field(default=1, ge=1)
    """Aurora always keeps automated backups for at least one day."""
    latest_restorable_time: AwareDatetime | None = None
    db_subnet_group_name: str | None = None
    vpc_security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    storage_encrypted: bool = False
    kms_key_id: str | None = None
    deletion_protection: bool = False

    @model_validator(mode="after")
    def _global_role_matches_membership(self) -> Self:
        # A role without a global cluster, or membership without a role, means the
        # import lost information the promotion path depends on. A value only known
        # after apply is neither, so the check skips it.
        if self.is_unknown("global_cluster_identifier") or self.is_unknown("global_cluster_role"):
            return self
        if (self.global_cluster_identifier is None) != (self.global_cluster_role is None):
            raise ValueError(
                "global_cluster_identifier and global_cluster_role are set together or not at all"
            )
        return self


class RDSSnapshotProperties(TypedProperties):
    """A DB snapshot (`rds/snapshot`) or cluster snapshot (`rds/cluster-snapshot`).

    A restore in the DR Region needs a snapshot that is *in* the DR Region (copied
    there) and encrypted with a key usable there.
    """

    type_key: Literal["rds/snapshot", "rds/cluster-snapshot"]
    required_fields: ClassVar[frozenset[str]] = frozenset({"snapshot_type"})
    snapshot_identifier: NonEmptyStr
    source_identifier: NonEmptyStr
    """The DB instance or cluster it was taken from."""
    snapshot_type: Literal["automated", "manual", "shared", "public", "awsbackup"] | None = None
    status: str | None = None
    created_at: AwareDatetime | None = None
    """Its age bounds the RPO of a restore from it (spec §51)."""
    source_region: str | None = None
    """Set when this snapshot is a copy from another Region."""
    encrypted: bool = False
    kms_key_id: str | None = None
    allocated_storage_gib: int | None = Field(default=None, ge=0)
