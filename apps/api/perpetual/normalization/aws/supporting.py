"""AWS API response normalizers for supporting services.

Covers ECR (repository, registry), Secrets Manager (metadata only), SSM
Parameter Store (metadata only), KMS, IAM (roles, policies), and CloudWatch
Logs. Secret and parameter values are never read or stored (spec §67).
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, cast

from perpetual.ids import aws_id, global_id
from perpetual.models.properties.supporting import (
    ECRRegistryProperties,
    ECRReplicationDestination,
    ECRReplicationRule,
    ECRRepositoryProperties,
    IAMPolicyProperties,
    IAMRoleProperties,
    KMSKeyProperties,
    LogGroupProperties,
    PolicyStatement,
    SecretProperties,
    SecretReplica,
    SSMParameterProperties,
)
from perpetual.models.resource import ResourceNode
from perpetual.normalization.aws._common import (
    aws_source_ref,
    ensure_aware_utc,
    parse_aws_datetime,
    tags_from_list,
)

_TagMutability = Literal["MUTABLE", "IMMUTABLE"]
_EcrEncryption = Literal["AES256", "KMS", "KMS_DSSE"]
_SecretReplicaStatus = Literal["InSync", "Failed", "InProgress"]
_SsmParamType = Literal["String", "StringList", "SecureString"]
_SsmTier = Literal["Standard", "Advanced", "Intelligent-Tiering"]
_KmsManager = Literal["AWS", "CUSTOMER"]
_KmsRole = Literal["PRIMARY", "REPLICA"]


def normalize_ecr_repository(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one repository object from `ecr:DescribeRepositories`."""
    ts = ensure_aware_utc(collected_at)
    repo_name = str(raw["repositoryName"])
    repo_arn = raw.get("repositoryArn")

    mut_raw = raw.get("imageTagMutability")
    mutability: _TagMutability | None = (
        cast(_TagMutability, str(mut_raw)) if mut_raw in {"MUTABLE", "IMMUTABLE"} else None
    )
    enc_cfg = raw.get("encryptionConfiguration", {})
    enc_raw = enc_cfg.get("encryptionType")
    encryption_type: _EcrEncryption | None = (
        cast(_EcrEncryption, str(enc_raw)) if enc_raw in {"AES256", "KMS", "KMS_DSSE"} else None
    )

    typed = ECRRepositoryProperties(
        repository_name=repo_name,
        repository_uri=str(raw["repositoryUri"]),
        image_tag_mutability=mutability,
        encryption_type=encryption_type,
        kms_key_arn=enc_cfg.get("kmsKey"),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ecr", "repository", repo_name),
        provider="aws",
        service="ecr",
        resource_type="repository",
        account_id=account_id,
        region=region,
        name=repo_name,
        arn=str(repo_arn) if repo_arn else None,
        tags=tags_from_list(tags),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ecr:DescribeRepositories",
                identifier=repo_name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_ecr_registry(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize the response from `ecr:DescribeRegistry`."""
    ts = ensure_aware_utc(collected_at)
    registry_id = str(raw.get("registryId") or account_id)

    rules: list[ECRReplicationRule] = []
    rep_cfg = raw.get("replicationConfiguration", {})
    for rule in rep_cfg.get("rules", []):
        destinations = [
            ECRReplicationDestination(
                region=str(dest["region"]),
                registry_id=str(dest["registryId"]),
            )
            for dest in rule.get("destinations", [])
            if dest.get("region") and dest.get("registryId")
        ]
        if not destinations:
            continue
        prefixes = [
            str(flt["filter"]) for flt in rule.get("repositoryFilters", []) if flt.get("filter")
        ]
        rules.append(
            ECRReplicationRule(
                destinations=destinations,
                repository_prefixes=prefixes,
            )
        )

    typed = ECRRegistryProperties(
        registry_id=registry_id,
        replication_rules=rules,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ecr", "registry", registry_id),
        provider="aws",
        service="ecr",
        resource_type="registry",
        account_id=account_id,
        region=region,
        name=registry_id,
        arn=f"arn:aws:ecr:{region}:{registry_id}:registry",
        tags={},
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ecr:DescribeRegistry",
                identifier=registry_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_secretsmanager_secret(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one secret from `secretsmanager:DescribeSecret` (metadata only)."""
    ts = ensure_aware_utc(collected_at)
    name = str(raw["Name"])
    arn = raw.get("ARN")

    replicas: list[SecretReplica] = []
    for rep in raw.get("ReplicationStatus", []):
        rep_region = rep.get("Region")
        if not rep_region:
            continue
        status_raw = rep.get("Status")
        status: _SecretReplicaStatus | None = (
            cast(_SecretReplicaStatus, str(status_raw))
            if status_raw in {"InSync", "Failed", "InProgress"}
            else None
        )
        replicas.append(
            SecretReplica(
                region=str(rep_region),
                kms_key_id=rep.get("KmsKeyId"),
                status=status,
            )
        )

    typed = SecretProperties(
        name=name,
        kms_key_id=raw.get("KmsKeyId"),
        rotation_enabled=bool(raw.get("RotationEnabled", False)),
        rotation_lambda_arn=raw.get("RotationLambdaARN"),
        replicas=replicas,
        primary_region=raw.get("PrimaryRegion"),
        last_changed_at=parse_aws_datetime(raw.get("LastChangedDate")),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "secretsmanager", "secret", name),
        provider="aws",
        service="secretsmanager",
        resource_type="secret",
        account_id=account_id,
        region=region,
        name=name,
        arn=str(arn) if arn else None,
        tags=tags_from_list(raw.get("Tags")),
        # Never store SecretString or SecretBinary.
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="secretsmanager:DescribeSecret",
                identifier=name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_ssm_parameter(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one parameter from `ssm:DescribeParameters` (metadata only)."""
    ts = ensure_aware_utc(collected_at)
    name = str(raw["Name"])
    param_type_raw = str(raw["Type"])
    if param_type_raw not in {"String", "StringList", "SecureString"}:
        raise ValueError(f"unsupported SSM parameter type: {param_type_raw!r}")
    param_type = cast(_SsmParamType, param_type_raw)

    tier_raw = raw.get("Tier")
    tier: _SsmTier | None = (
        cast(_SsmTier, str(tier_raw))
        if tier_raw in {"Standard", "Advanced", "Intelligent-Tiering"}
        else None
    )
    kms_key_id = raw.get("KeyId") if param_type == "SecureString" else None
    clean_id = name.lstrip("/")

    typed = SSMParameterProperties(
        name=name,
        parameter_type=param_type,
        kms_key_id=kms_key_id,
        version=raw.get("Version"),
        last_modified_at=parse_aws_datetime(raw.get("LastModifiedDate")),
        tier=tier,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ssm", "parameter", clean_id),
        provider="aws",
        service="ssm",
        resource_type="parameter",
        account_id=account_id,
        region=region,
        name=name,
        arn=f"arn:aws:ssm:{region}:{account_id}:parameter/{clean_id}",
        tags=tags_from_list(tags),
        # Never store Value.
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ssm:DescribeParameters",
                identifier=name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_kms_key(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    aliases: Sequence[str] = (),
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize a KeyMetadata object from `kms:DescribeKey`."""
    ts = ensure_aware_utc(collected_at)
    meta = raw.get("KeyMetadata", raw)
    key_id = str(meta["KeyId"])
    arn = meta.get("Arn")

    manager_raw = meta.get("KeyManager", "CUSTOMER")
    key_manager: _KmsManager = "AWS" if manager_raw == "AWS" else "CUSTOMER"

    multi_region = bool(meta.get("MultiRegion", False))
    mr_cfg = meta.get("MultiRegionConfiguration", {})
    mr_role: _KmsRole | None = None
    primary_key_arn: str | None = None
    replica_regions: list[str] = []
    if multi_region and isinstance(mr_cfg, Mapping):
        mr_type = mr_cfg.get("MultiRegionKeyType")
        if mr_type in {"PRIMARY", "REPLICA"}:
            mr_role = cast(_KmsRole, str(mr_type))
        primary_key = mr_cfg.get("PrimaryKey", {})
        if isinstance(primary_key, Mapping):
            primary_key_arn = primary_key.get("Arn")
        for rep in mr_cfg.get("ReplicaKeys", []):
            if isinstance(rep, Mapping) and rep.get("Region"):
                replica_regions.append(str(rep["Region"]))

    typed = KMSKeyProperties(
        key_id=key_id,
        key_state=meta.get("KeyState"),
        key_manager=key_manager,
        key_usage=meta.get("KeyUsage"),
        multi_region=multi_region,
        multi_region_role=mr_role,
        primary_key_arn=primary_key_arn,
        replica_regions=replica_regions,
        aliases=list(aliases),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "kms", "key", key_id),
        provider="aws",
        service="kms",
        resource_type="key",
        account_id=account_id,
        region=region,
        name=aliases[0] if aliases else key_id,
        arn=str(arn) if arn else None,
        tags=tags_from_list(tags, key_field="TagKey", value_field="TagValue"),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="kms:DescribeKey",
                identifier=key_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_iam_role(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    collected_at: datetime,
    attached_policy_arns: Sequence[str] = (),
    inline_policy_documents: Sequence[Mapping[str, Any] | str] = (),
    instance_profile_arns: Sequence[str] = (),
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize a Role object from `iam:GetRole` / `iam:ListRoles`."""
    ts = ensure_aware_utc(collected_at)
    role_name = str(raw["RoleName"])
    arn = raw.get("Arn")

    trusted_principals = _extract_trusted_principals(raw.get("AssumeRolePolicyDocument"))
    inline_statements: list[PolicyStatement] = []
    for doc in inline_policy_documents:
        inline_statements.extend(_parse_policy_statements(doc))

    typed = IAMRoleProperties(
        role_name=role_name,
        path=str(raw.get("Path", "/")),
        trusted_principals=trusted_principals,
        attached_policy_arns=list(attached_policy_arns),
        inline_policy_statements=inline_statements,
        instance_profile_arns=list(instance_profile_arns),
    )
    return ResourceNode(
        id=global_id(account_id, "iam", "role", role_name),
        provider="aws",
        service="iam",
        resource_type="role",
        account_id=account_id,
        region="global",
        name=role_name,
        arn=str(arn) if arn else None,
        tags=tags_from_list(raw.get("Tags")),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="iam:GetRole",
                identifier=role_name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_iam_policy(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    collected_at: datetime,
    policy_document: Mapping[str, Any] | str | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize a Policy object from `iam:GetPolicy` + `iam:GetPolicyVersion`."""
    ts = ensure_aware_utc(collected_at)
    policy_name = str(raw["PolicyName"])
    arn = raw.get("Arn")
    statements = _parse_policy_statements(policy_document) if policy_document else []

    typed = IAMPolicyProperties(
        policy_name=policy_name,
        default_version_id=raw.get("DefaultVersionId"),
        statements=statements,
        attachment_count=raw.get("AttachmentCount"),
    )
    return ResourceNode(
        id=global_id(account_id, "iam", "policy", policy_name),
        provider="aws",
        service="iam",
        resource_type="policy",
        account_id=account_id,
        region="global",
        name=policy_name,
        arn=str(arn) if arn else None,
        tags=tags_from_list(raw.get("Tags")),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="iam:GetPolicy",
                identifier=policy_name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_log_group(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    subscription_destination_arns: Sequence[str] = (),
    tags: Mapping[str, str] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one logGroup dict from `logs:DescribeLogGroups`."""
    ts = ensure_aware_utc(collected_at)
    name = str(raw["logGroupName"])
    arn = raw.get("arn")

    typed = LogGroupProperties(
        log_group_name=name,
        retention_days=raw.get("retentionInDays"),
        kms_key_id=raw.get("kmsKeyId"),
        subscription_destination_arns=list(subscription_destination_arns),
        stored_bytes=raw.get("storedBytes"),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "logs", "log-group", name),
        provider="aws",
        service="logs",
        resource_type="log-group",
        account_id=account_id,
        region=region,
        name=name,
        arn=str(arn) if arn else None,
        tags=dict(tags) if tags else {},
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="logs:DescribeLogGroups",
                identifier=name,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def _decode_policy_document(doc: Mapping[str, Any] | str | None) -> Mapping[str, Any]:
    if doc is None:
        return {}
    if isinstance(doc, Mapping):
        return doc
    decoded = urllib.parse.unquote(doc)
    parsed = json.loads(decoded)
    return parsed if isinstance(parsed, Mapping) else {}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(v) for v in value if v]
    return []


def _extract_trusted_principals(doc: Mapping[str, Any] | str | None) -> list[str]:
    parsed = _decode_policy_document(doc)
    raw_stmts = parsed.get("Statement", [])
    if isinstance(raw_stmts, Mapping):
        raw_stmts = [raw_stmts]
    principals: list[str] = []
    for stmt in raw_stmts:
        principal = stmt.get("Principal")
        if isinstance(principal, str):
            principals.append(principal)
        elif isinstance(principal, Mapping):
            for val in principal.values():
                principals.extend(_as_str_list(val))
    return sorted(set(principals))


def _parse_policy_statements(doc: Mapping[str, Any] | str | None) -> list[PolicyStatement]:
    parsed = _decode_policy_document(doc)
    raw_stmts = parsed.get("Statement", [])
    if isinstance(raw_stmts, Mapping):
        raw_stmts = [raw_stmts]
    result: list[PolicyStatement] = []
    for stmt in raw_stmts:
        effect_raw = stmt.get("Effect")
        if effect_raw not in {"Allow", "Deny"}:
            continue
        effect: Literal["Allow", "Deny"] = "Allow" if effect_raw == "Allow" else "Deny"
        actions = _as_str_list(stmt.get("Action"))
        not_actions = _as_str_list(stmt.get("NotAction"))
        if not actions and not not_actions:
            continue
        result.append(
            PolicyStatement(
                effect=effect,
                actions=actions,
                not_actions=not_actions,
                resources=_as_str_list(stmt.get("Resource")),
                not_resources=_as_str_list(stmt.get("NotResource")),
                has_conditions=bool(stmt.get("Condition")),
            )
        )
    return result
