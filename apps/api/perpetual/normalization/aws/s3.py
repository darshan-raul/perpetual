"""AWS API response normalizer for Amazon S3 buckets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, cast

from perpetual.ids import aws_id
from perpetual.models.properties.s3 import S3BucketProperties, S3ReplicationRule
from perpetual.models.resource import ResourceNode
from perpetual.normalization.aws._common import aws_source_ref, ensure_aware_utc, tags_from_list

_VersioningStatus = Literal["Enabled", "Suspended", "Disabled"]
_EncryptionAlgo = Literal["SSE-S3", "SSE-KMS", "DSSE-KMS"]
_ObjectOwnership = Literal["BucketOwnerEnforced", "BucketOwnerPreferred", "ObjectWriter"]


def normalize_s3_bucket(
    *,
    bucket_name: str,
    account_id: str,
    region: str,
    collected_at: datetime,
    versioning_response: Mapping[str, Any] | None = None,
    replication_response: Mapping[str, Any] | None = None,
    encryption_response: Mapping[str, Any] | None = None,
    ownership_response: Mapping[str, Any] | None = None,
    object_lock_response: Mapping[str, Any] | None = None,
    lifecycle_rules: Sequence[Mapping[str, Any]] = (),
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize combined S3 bucket metadata responses into one `ResourceNode`."""
    ts = ensure_aware_utc(collected_at)
    versioning = _parse_versioning(versioning_response)
    replication_role_arn, replication_rules = _parse_replication(replication_response)
    default_encryption, kms_key_arn, bucket_key_enabled = _parse_encryption(encryption_response)
    object_ownership = _parse_ownership(ownership_response)
    object_lock_enabled = _parse_object_lock(object_lock_response)

    typed = S3BucketProperties(
        bucket_name=bucket_name,
        versioning=versioning,
        replication_role_arn=replication_role_arn,
        replication_rules=replication_rules,
        default_encryption=default_encryption,
        kms_key_arn=kms_key_arn,
        bucket_key_enabled=bucket_key_enabled,
        object_ownership=object_ownership,
        object_lock_enabled=object_lock_enabled,
        lifecycle_rule_count=len(lifecycle_rules),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "s3", "bucket", bucket_name),
        provider="aws",
        service="s3",
        resource_type="bucket",
        account_id=account_id,
        region=region,
        name=bucket_name,
        arn=f"arn:aws:s3:::{bucket_name}",
        tags=tags_from_list(tags),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="s3:HeadBucket",
                identifier=bucket_name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def _parse_versioning(response: Mapping[str, Any] | None) -> _VersioningStatus:
    if response is None:
        return "Disabled"
    raw_status = response.get("Status")
    if raw_status in {"Enabled", "Suspended"}:
        return cast(_VersioningStatus, str(raw_status))
    return "Disabled"


def _parse_replication(
    response: Mapping[str, Any] | None,
) -> tuple[str | None, list[S3ReplicationRule]]:
    if response is None:
        return None, []
    cfg = response.get("ReplicationConfiguration", response)
    if not isinstance(cfg, Mapping):
        return None, []
    role_arn = cfg.get("Role")
    rules = [
        _parse_replication_rule(rule, idx) for idx, rule in enumerate(cfg.get("Rules", []), start=1)
    ]
    return role_arn, rules


def _parse_replication_rule(rule: Mapping[str, Any], idx: int) -> S3ReplicationRule:
    dest = rule.get("Destination", {})
    filter_block = rule.get("Filter", {})
    prefix = rule.get("Prefix")
    if prefix is None and isinstance(filter_block, Mapping):
        prefix = filter_block.get("Prefix")

    sse_kms = (
        rule.get("SourceSelectionCriteria", {}).get("SseKmsEncryptedObjects", {}).get("Status")
        == "Enabled"
    )
    rtc_enabled = (
        dest.get("ReplicationTime", {}).get("Status") == "Enabled"
        if isinstance(dest, Mapping)
        else False
    )
    del_markers = rule.get("DeleteMarkerReplication", {}).get("Status") == "Enabled"
    rule_status: Literal["Enabled", "Disabled"] = (
        "Enabled" if rule.get("Status") == "Enabled" else "Disabled"
    )
    return S3ReplicationRule(
        rule_id=str(rule.get("ID") or f"rule-{idx}"),
        status=rule_status,
        destination_bucket_arn=str(dest["Bucket"]),
        destination_account_id=dest.get("Account"),
        destination_storage_class=dest.get("StorageClass"),
        prefix=str(prefix) if prefix else None,
        replicate_kms_encrypted_objects=sse_kms,
        replica_kms_key_id=dest.get("EncryptionConfiguration", {}).get("ReplicaKmsKeyID"),
        replication_time_control=rtc_enabled,
        delete_marker_replication=del_markers,
    )


def _parse_encryption(
    response: Mapping[str, Any] | None,
) -> tuple[_EncryptionAlgo | None, str | None, bool]:
    if response is None:
        return None, None, False
    rules = response.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
    if not rules:
        return None, None, False
    first = rules[0]
    apply_default = first.get("ApplyServerSideEncryptionByDefault", {})
    algo_map: dict[str, _EncryptionAlgo] = {
        "AES256": "SSE-S3",
        "aws:kms": "SSE-KMS",
        "aws:kms:dsse": "DSSE-KMS",
    }
    algo = algo_map.get(str(apply_default.get("SSEAlgorithm", "")))
    return algo, apply_default.get("KMSMasterKeyID"), bool(first.get("BucketKeyEnabled", False))


def _parse_ownership(response: Mapping[str, Any] | None) -> _ObjectOwnership | None:
    if response is None:
        return None
    rules = response.get("OwnershipControls", {}).get("Rules", [])
    if not rules:
        return None
    raw_own = rules[0].get("ObjectOwnership")
    if raw_own in {"BucketOwnerEnforced", "BucketOwnerPreferred", "ObjectWriter"}:
        return cast(_ObjectOwnership, str(raw_own))
    return None


def _parse_object_lock(response: Mapping[str, Any] | None) -> bool:
    if response is None:
        return False
    lock_cfg = response.get("ObjectLockConfiguration", {})
    return bool(lock_cfg.get("ObjectLockEnabled") == "Enabled")
