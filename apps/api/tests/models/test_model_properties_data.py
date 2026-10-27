"""Typed properties for RDS/Aurora, DynamoDB, S3, EBS, EFS and AWS Backup (spec §6, §7, §15.3)."""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import ResourceNode
from perpetual.models.properties import (
    AuroraClusterProperties,
    BackupRecoveryPointProperties,
    DynamoDBTableProperties,
    EBSVolumeProperties,
    RDSInstanceProperties,
    RDSSnapshotProperties,
    S3BucketProperties,
)
from tests.models.builders import NOW


def node(service: str, resource_type: str, typed: dict[str, Any]) -> ResourceNode:
    return ResourceNode.model_validate(
        {
            "id": f"aws://1/ap-south-1/{service}/{resource_type}/x",
            "provider": "aws",
            "service": service,
            "resource_type": resource_type,
            "typed_properties": typed,
            "discovered_at": NOW,
        }
    )


@pytest.mark.parametrize("resource_type", ["snapshot", "cluster-snapshot"])
def test_one_snapshot_model_serves_both_rds_snapshot_kinds(resource_type: str) -> None:
    built = node(
        "rds",
        resource_type,
        {
            "type_key": f"rds/{resource_type}",
            "snapshot_identifier": "nightly",
            "source_identifier": "checkout-db",
            "snapshot_type": "automated",
        },
    )
    assert isinstance(built.typed_properties, RDSSnapshotProperties)


def test_rds_snapshot_key_must_match_the_node() -> None:
    with pytest.raises(ValidationError, match="but this node is 'rds/snapshot'"):
        node(
            "rds",
            "snapshot",
            {
                "type_key": "rds/cluster-snapshot",
                "snapshot_identifier": "s",
                "source_identifier": "c",
                "snapshot_type": "manual",
            },
        )


def test_multi_az_is_off_unless_stated() -> None:
    db = RDSInstanceProperties(
        db_instance_identifier="checkout-db", engine="postgres", instance_class="db.r6g.large"
    )
    assert db.multi_az is False
    assert db.read_replica_arns == []


def test_aurora_instance_needs_its_cluster() -> None:
    with pytest.raises(ValidationError, match="belongs to a cluster"):
        RDSInstanceProperties(
            db_instance_identifier="a1", engine="aurora-postgresql", instance_class="db.r6g.large"
        )


def test_aurora_instance_with_cluster_known_after_apply_is_valid() -> None:
    db = RDSInstanceProperties(
        db_instance_identifier="a1",
        engine="aurora-postgresql",
        instance_class="db.r6g.large",
        unknown_fields=["db_cluster_identifier"],
    )
    assert db.db_cluster_identifier is None


def aurora(**overrides: Any) -> AuroraClusterProperties:
    fields: dict[str, Any] = {"db_cluster_identifier": "checkout", "engine": "aurora-postgresql"}
    fields.update(overrides)
    return AuroraClusterProperties(**fields)


@pytest.mark.parametrize(
    "overrides",
    [{"global_cluster_identifier": "g1"}, {"global_cluster_role": "secondary"}],
)
def test_global_cluster_membership_and_role_go_together(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="set together"):
        aurora(**overrides)


def test_global_secondary_cluster_is_valid() -> None:
    cluster = aurora(global_cluster_identifier="g1", global_cluster_role="secondary")
    assert cluster.writer_instance_identifier is None


def test_aurora_cluster_rejects_non_aurora_engine_and_zero_retention() -> None:
    with pytest.raises(ValidationError):
        aurora(engine="mysql")
    with pytest.raises(ValidationError):
        aurora(backup_retention_days=0)


def test_dynamodb_replicas_need_a_global_table_version() -> None:
    with pytest.raises(ValidationError, match="global table"):
        DynamoDBTableProperties.model_validate(
            {"table_name": "orders", "replicas": [{"region": "ap-south-2"}]}
        )
    table = DynamoDBTableProperties.model_validate(
        {
            "table_name": "orders",
            "global_table_version": "2019.11.21",
            "replicas": [
                {"region": "ap-south-2", "status": "ACTIVE", "kms_key_arn": "arn:aws:kms:x"}
            ],
        }
    )
    assert table.replicas[0].kms_key_arn == "arn:aws:kms:x"


def test_dynamodb_has_one_replica_per_region() -> None:
    with pytest.raises(ValidationError, match="one replica per Region"):
        DynamoDBTableProperties.model_validate(
            {
                "table_name": "orders",
                "global_table_version": "2019.11.21",
                "replicas": [{"region": "ap-south-2"}, {"region": "ap-south-2"}],
            }
        )


REPLICATION_RULE: dict[str, Any] = {
    "rule_id": "to-dr",
    "status": "Enabled",
    "destination_bucket_arn": "arn:aws:s3:::assets-dr",
}


def bucket(**overrides: Any) -> S3BucketProperties:
    fields: dict[str, Any] = {
        "bucket_name": "assets",
        "versioning": "Enabled",
        "replication_role_arn": "arn:aws:iam::1:role/s3-replication",
        "replication_rules": [REPLICATION_RULE],
    }
    fields.update(overrides)
    return S3BucketProperties.model_validate(fields)


def test_replicated_bucket_is_valid() -> None:
    assert bucket().replication_rules[0].replicate_kms_encrypted_objects is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"versioning": "Suspended"}, "requires versioning Enabled"),
        ({"replication_role_arn": None}, "requires a replication_role_arn"),
        ({"replication_rules": [REPLICATION_RULE, REPLICATION_RULE]}, "must be distinct"),
    ],
)
def test_s3_replication_prerequisites(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        bucket(**overrides)


def test_s3_replication_role_known_after_apply_is_valid() -> None:
    assert bucket(replication_role_arn=None, unknown_fields=["replication_role_arn"])


def test_ebs_volume_has_a_size() -> None:
    with pytest.raises(ValidationError):
        EBSVolumeProperties(volume_id="vol-1", size_gib=0)


def test_recovery_point_cannot_complete_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="must not be before"):
        BackupRecoveryPointProperties(
            recovery_point_arn="arn:aws:backup:ap-south-2:1:recovery-point:abc",
            vault_name="dr-vault",
            protected_resource_arn="arn:aws:rds:ap-south-1:1:db:checkout",
            protected_resource_type="RDS",
            status="COMPLETED",
            created_at=NOW,
            completed_at=NOW - timedelta(minutes=5),
        )
