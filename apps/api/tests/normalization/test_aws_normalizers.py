"""Tests for recorded-AWS normalizers and `perpetual import-aws-fixture` (`P1b-03`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from perpetual.cli.app import app
from perpetual.models.properties.ecs import ECSTaskDefinitionProperties
from perpetual.models.properties.rds import AuroraClusterProperties, RDSInstanceProperties
from perpetual.models.properties.s3 import S3BucketProperties
from perpetual.models.properties.supporting import KMSKeyProperties, SSMParameterProperties
from perpetual.normalization.aws import (
    import_aws_fixture_file,
    normalize_aurora_cluster,
    normalize_kms_key,
    normalize_s3_bucket,
    normalize_ssm_parameter,
    resolve_aws_fixture_path,
)

_TS = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
_ACCT = "123456789012"
_RUNNER = CliRunner()


def test_import_ecs_rds_sample_fixture_and_env_redaction_canary() -> None:
    path = resolve_aws_fixture_path("ecs-rds-sample")
    result = import_aws_fixture_file(path)

    assert result.account_id == _ACCT
    assert len(result.nodes) == 23
    assert result.conflicts == []
    # Every normalized node must have typed_properties populated.
    assert all(node.typed_properties is not None for node in result.nodes)

    # Spec §67 canary: environment variable values must NEVER appear anywhere in output.
    serialized = json.dumps([n.model_dump(mode="json") for n in result.nodes])
    assert "CANARY-ENV-VALUE-MUST-NEVER-BE-STORED" not in serialized

    td_nodes = [n for n in result.nodes if n.resource_type == "task-definition"]
    assert len(td_nodes) == 1
    td_props = td_nodes[0].typed_properties
    assert isinstance(td_props, ECSTaskDefinitionProperties)
    assert td_props.containers[0].environment_names == ["DB_HOST"]
    assert len(td_props.containers[0].secrets) == 1

    rds_nodes = [n for n in result.nodes if n.service == "rds" and n.resource_type == "db"]
    assert len(rds_nodes) == 1
    rds_props = rds_nodes[0].typed_properties
    assert isinstance(rds_props, RDSInstanceProperties)
    assert rds_props.multi_az is True
    assert rds_props.allocated_storage_gib == 200


def test_aurora_multi_region_kms_s3_crr_and_ssm_secure_string() -> None:
    aurora = normalize_aurora_cluster(
        {
            "DBClusterIdentifier": "orders-aurora",
            "DBClusterArn": f"arn:aws:rds:ap-south-1:{_ACCT}:cluster:orders-aurora",
            "Engine": "aurora-postgresql",
            "EngineVersion": "16.2",
            "Status": "available",
            "BackupRetentionPeriod": 7,
            "StorageEncrypted": True,
            "DBClusterMembers": [
                {"DBInstanceIdentifier": "orders-aurora-1", "IsClusterWriter": True},
                {"DBInstanceIdentifier": "orders-aurora-2", "IsClusterWriter": False},
            ],
        },
        account_id=_ACCT,
        region="ap-south-1",
        collected_at=_TS,
        global_cluster_identifier="orders-global",
        global_cluster_role="primary",
    )
    assert isinstance(aurora.typed_properties, AuroraClusterProperties)
    assert aurora.typed_properties.writer_instance_identifier == "orders-aurora-1"
    assert aurora.typed_properties.global_cluster_role == "primary"

    mr_key = normalize_kms_key(
        {
            "KeyMetadata": {
                "KeyId": "mrk-1234567890abcdef",
                "Arn": f"arn:aws:kms:ap-south-1:{_ACCT}:key/mrk-1234567890abcdef",
                "KeyState": "Enabled",
                "KeyManager": "CUSTOMER",
                "MultiRegion": True,
                "MultiRegionConfiguration": {
                    "MultiRegionKeyType": "PRIMARY",
                    "PrimaryKey": {
                        "Arn": f"arn:aws:kms:ap-south-1:{_ACCT}:key/mrk-1234567890abcdef",
                        "Region": "ap-south-1",
                    },
                    "ReplicaKeys": [{"Region": "ap-south-2"}],
                },
            }
        },
        account_id=_ACCT,
        region="ap-south-1",
        collected_at=_TS,
        aliases=["alias/orders-mrk"],
    )
    assert isinstance(mr_key.typed_properties, KMSKeyProperties)
    assert mr_key.typed_properties.multi_region is True
    assert mr_key.typed_properties.replica_regions == ["ap-south-2"]

    bucket = normalize_s3_bucket(
        bucket_name="orders-archive",
        account_id=_ACCT,
        region="ap-south-1",
        collected_at=_TS,
        versioning_response={"Status": "Enabled"},
        replication_response={
            "ReplicationConfiguration": {
                "Role": f"arn:aws:iam::{_ACCT}:role/s3-crr",
                "Rules": [
                    {
                        "ID": "crr-ap-south-2",
                        "Status": "Enabled",
                        "Destination": {
                            "Bucket": "arn:aws:s3:::orders-archive-dr",
                            "ReplicationTime": {"Status": "Enabled"},
                        },
                        "SourceSelectionCriteria": {
                            "SseKmsEncryptedObjects": {"Status": "Enabled"}
                        },
                    }
                ],
            }
        },
    )
    assert isinstance(bucket.typed_properties, S3BucketProperties)
    assert bucket.typed_properties.replication_rules[0].replication_time_control is True
    assert bucket.typed_properties.replication_rules[0].replicate_kms_encrypted_objects is True

    param = normalize_ssm_parameter(
        {
            "Name": "/orders/api-token",
            "Type": "SecureString",
            "KeyId": "alias/aws/ssm",
            "Version": 4,
            "Tier": "Standard",
            "Value": "CANARY-SSM-SECRET-MUST-NEVER-BE-STORED",
        },
        account_id=_ACCT,
        region="ap-south-1",
        collected_at=_TS,
    )
    assert isinstance(param.typed_properties, SSMParameterProperties)
    assert param.typed_properties.kms_key_id == "alias/aws/ssm"
    assert "CANARY-SSM-SECRET-MUST-NEVER-BE-STORED" not in param.model_dump_json()


def test_cli_import_aws_fixture_text_json_and_missing_error() -> None:
    text_res = _RUNNER.invoke(app, ["import-aws-fixture", "ecs-rds-sample"])
    assert text_res.exit_code == 0, text_res.output
    assert "Resources: 23" in text_res.output
    assert "ecs/service: 1" in text_res.output

    json_res = _RUNNER.invoke(app, ["import-aws-fixture", "ecs-rds-sample", "--json"])
    assert json_res.exit_code == 0, json_res.output
    parsed = json.loads(json_res.output)
    assert parsed["resource_count"] == 23
    assert parsed["counts_by_type"]["rds/db"] == 1
    assert "CANARY-ENV-VALUE-MUST-NEVER-BE-STORED" not in json_res.output

    missing_res = _RUNNER.invoke(app, ["import-aws-fixture", "does-not-exist"])
    assert missing_res.exit_code == 1
