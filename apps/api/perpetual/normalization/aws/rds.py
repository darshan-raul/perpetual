"""AWS API response normalizers for Amazon RDS and Aurora."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, cast

from perpetual.ids import aws_id
from perpetual.models.properties.rds import (
    AuroraClusterProperties,
    RDSInstanceProperties,
    RDSSnapshotProperties,
)
from perpetual.models.resource import ResourceNode
from perpetual.normalization.aws._common import (
    aws_source_ref,
    ensure_aware_utc,
    parse_aws_datetime,
    tags_from_list,
)

_AuroraEngine = Literal["aurora-mysql", "aurora-postgresql"]
_SnapshotType = Literal["automated", "manual", "shared", "public", "awsbackup"]


def normalize_rds_instance(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
    replicated_automated_backup_regions: Sequence[str] = (),
) -> ResourceNode:
    """Normalize one DBInstance dict from `rds:DescribeDBInstances`."""
    ts = ensure_aware_utc(collected_at)
    identifier = str(raw["DBInstanceIdentifier"])
    arn = raw.get("DBInstanceArn")

    sg_ids = [
        str(sg["VpcSecurityGroupId"])
        for sg in raw.get("VpcSecurityGroups", [])
        if sg.get("VpcSecurityGroupId")
    ]
    param_groups = [
        str(pg["DBParameterGroupName"])
        for pg in raw.get("DBParameterGroups", [])
        if pg.get("DBParameterGroupName")
    ]
    option_groups = [
        str(og["OptionGroupName"])
        for og in raw.get("OptionGroupMemberships", [])
        if og.get("OptionGroupName")
    ]
    replica_arns = [str(r) for r in raw.get("ReadReplicaDBInstanceIdentifiers", [])]
    # Also include cross-Region replica ARNs if present on the payload.
    for extra in raw.get("ReadReplicaDBClusterIdentifiers", []):
        if str(extra) not in replica_arns:
            replica_arns.append(str(extra))

    subnet_group = raw.get("DBSubnetGroup")
    subnet_group_name = (
        str(subnet_group["DBSubnetGroupName"])
        if isinstance(subnet_group, Mapping) and subnet_group.get("DBSubnetGroupName")
        else None
    )

    typed = RDSInstanceProperties(
        db_instance_identifier=identifier,
        engine=str(raw["Engine"]),
        engine_version=raw.get("EngineVersion"),
        instance_class=str(raw["DBInstanceClass"]),
        status=raw.get("DBInstanceStatus"),
        db_cluster_identifier=raw.get("DBClusterIdentifier"),
        allocated_storage_gib=raw.get("AllocatedStorage"),
        storage_type=raw.get("StorageType"),
        iops=raw.get("Iops"),
        storage_throughput_mibps=raw.get("StorageThroughput"),
        multi_az=bool(raw.get("MultiAZ", False)),
        backup_retention_days=int(raw.get("BackupRetentionPeriod", 0)),
        latest_restorable_time=parse_aws_datetime(raw.get("LatestRestorableTime")),
        replicated_automated_backup_regions=list(replicated_automated_backup_regions),
        read_replica_source_arn=raw.get("ReadReplicaSourceDBInstanceIdentifier"),
        read_replica_arns=replica_arns,
        db_subnet_group_name=subnet_group_name,
        vpc_security_group_ids=sg_ids,
        storage_encrypted=bool(raw.get("StorageEncrypted", False)),
        kms_key_id=raw.get("KmsKeyId"),
        parameter_group_names=param_groups,
        option_group_names=option_groups,
        deletion_protection=bool(raw.get("DeletionProtection", False)),
    )
    endpoint = raw.get("Endpoint")
    raw_props: dict[str, Any] = {}
    if isinstance(endpoint, Mapping) and endpoint.get("Address"):
        raw_props["endpoint_address"] = str(endpoint["Address"])
        if endpoint.get("Port") is not None:
            raw_props["endpoint_port"] = int(endpoint["Port"])

    return ResourceNode(
        id=aws_id(account_id, region, "rds", "db", identifier),
        provider="aws",
        service="rds",
        resource_type="db",
        account_id=account_id,
        region=region,
        availability_zone=raw.get("AvailabilityZone"),
        name=identifier,
        arn=str(arn) if arn else None,
        tags=tags_from_list(raw.get("TagList")),
        properties=raw_props,
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="rds:DescribeDBInstances",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_aurora_cluster(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
    global_cluster_identifier: str | None = None,
    global_cluster_role: Literal["primary", "secondary"] | None = None,
) -> ResourceNode:
    """Normalize one DBCluster dict from `rds:DescribeDBClusters`."""
    ts = ensure_aware_utc(collected_at)
    identifier = str(raw["DBClusterIdentifier"])
    arn = raw.get("DBClusterArn")

    engine_raw = str(raw["Engine"])
    if engine_raw not in {"aurora-mysql", "aurora-postgresql"}:
        raise ValueError(f"unsupported Aurora engine: {engine_raw!r}")
    engine = cast(_AuroraEngine, engine_raw)

    members = raw.get("DBClusterMembers", [])
    member_ids = [str(m["DBInstanceIdentifier"]) for m in members if m.get("DBInstanceIdentifier")]
    writer_id = next(
        (str(m["DBInstanceIdentifier"]) for m in members if m.get("IsClusterWriter")),
        None,
    )
    sg_ids = [
        str(sg["VpcSecurityGroupId"])
        for sg in raw.get("VpcSecurityGroups", [])
        if sg.get("VpcSecurityGroupId")
    ]

    typed = AuroraClusterProperties(
        db_cluster_identifier=identifier,
        engine=engine,
        engine_version=raw.get("EngineVersion"),
        status=raw.get("Status"),
        member_instance_identifiers=member_ids,
        writer_instance_identifier=writer_id,
        global_cluster_identifier=global_cluster_identifier,
        global_cluster_role=global_cluster_role,
        replication_source_arn=raw.get("ReplicationSourceIdentifier"),
        backup_retention_days=max(1, int(raw.get("BackupRetentionPeriod", 1))),
        latest_restorable_time=parse_aws_datetime(raw.get("LatestRestorableTime")),
        db_subnet_group_name=raw.get("DBSubnetGroup"),
        vpc_security_group_ids=sg_ids,
        storage_encrypted=bool(raw.get("StorageEncrypted", False)),
        kms_key_id=raw.get("KmsKeyId"),
        deletion_protection=bool(raw.get("DeletionProtection", False)),
    )
    raw_props: dict[str, Any] = {}
    if raw.get("Endpoint"):
        raw_props["endpoint_address"] = str(raw["Endpoint"])
    if raw.get("ReaderEndpoint"):
        raw_props["reader_endpoint_address"] = str(raw["ReaderEndpoint"])

    return ResourceNode(
        id=aws_id(account_id, region, "rds", "cluster", identifier),
        provider="aws",
        service="rds",
        resource_type="cluster",
        account_id=account_id,
        region=region,
        name=identifier,
        arn=str(arn) if arn else None,
        tags=tags_from_list(raw.get("TagList")),
        properties=raw_props,
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="rds:DescribeDBClusters",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_rds_snapshot(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    cluster_snapshot: bool = False,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize a DB snapshot or DB cluster snapshot."""
    ts = ensure_aware_utc(collected_at)
    if cluster_snapshot:
        resource_type: Literal["snapshot", "cluster-snapshot"] = "cluster-snapshot"
        type_key: Literal["rds/snapshot", "rds/cluster-snapshot"] = "rds/cluster-snapshot"
        identifier = str(raw["DBClusterSnapshotIdentifier"])
        source_id = str(raw["DBClusterIdentifier"])
        arn = raw.get("DBClusterSnapshotArn")
        operation = "rds:DescribeDBClusterSnapshots"
    else:
        resource_type = "snapshot"
        type_key = "rds/snapshot"
        identifier = str(raw["DBSnapshotIdentifier"])
        source_id = str(raw["DBInstanceIdentifier"])
        arn = raw.get("DBSnapshotArn")
        operation = "rds:DescribeDBSnapshots"

    snap_type_raw = raw.get("SnapshotType")
    snapshot_type: _SnapshotType | None = (
        cast(_SnapshotType, str(snap_type_raw))
        if snap_type_raw in {"automated", "manual", "shared", "public", "awsbackup"}
        else None
    )
    typed = RDSSnapshotProperties(
        type_key=type_key,
        snapshot_identifier=identifier,
        source_identifier=source_id,
        snapshot_type=snapshot_type,
        status=raw.get("Status"),
        created_at=parse_aws_datetime(raw.get("SnapshotCreateTime")),
        source_region=raw.get("SourceRegion"),
        encrypted=bool(raw.get("Encrypted", False)),
        kms_key_id=raw.get("KmsKeyId"),
        allocated_storage_gib=raw.get("AllocatedStorage"),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "rds", resource_type, identifier),
        provider="aws",
        service="rds",
        resource_type=resource_type,
        account_id=account_id,
        region=region,
        name=identifier,
        arn=str(arn) if arn else None,
        tags=tags_from_list(raw.get("TagList")),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation=operation,
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )
