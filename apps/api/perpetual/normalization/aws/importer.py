"""Import recorded AWS API response fixtures (`fixtures/aws/`) into normalized nodes.

A recorded AWS fixture is a JSON document containing raw AWS API response
payloads grouped by global resources and per-Region resources:

```json
{
  "account_id": "123456789012",
  "collected_at": "2026-11-24T12:00:00Z",
  "global": {
    "iam_roles": [...],
    "iam_policies": [...],
    "route53_hosted_zones": [...],
    "route53_record_sets": [...]
  },
  "regions": {
    "ap-south-1": {
      "vpcs": [...],
      "subnets": [...],
      "security_groups": [...],
      "load_balancers": [...],
      "listeners": [...],
      "target_groups": [...],
      "ecs_clusters": [...],
      "ecs_services": [...],
      "ecs_task_definitions": [...],
      "rds_instances": [...],
      "aurora_clusters": [...],
      "rds_snapshots": [...],
      "s3_buckets": [...],
      "ecr_repositories": [...],
      "ecr_registry": {...},
      "secrets": [...],
      "ssm_parameters": [...],
      "kms_keys": [...],
      "log_groups": [...],
      "acm_certificates": [...]
    }
  }
}
```

Both `perpetual import-aws-fixture` (`P1b-03`) and P2 tests reuse these exact
normalizers and identity resolution.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from perpetual.models.resource import ResourceNode
from perpetual.normalization.aws._common import parse_aws_datetime
from perpetual.normalization.aws.ecs import (
    normalize_ecs_cluster,
    normalize_ecs_service,
    normalize_ecs_task_definition,
)
from perpetual.normalization.aws.network import (
    normalize_acm_certificate,
    normalize_hosted_zone,
    normalize_listener,
    normalize_load_balancer,
    normalize_record_set,
    normalize_security_group,
    normalize_subnet,
    normalize_target_group,
    normalize_vpc,
)
from perpetual.normalization.aws.rds import (
    normalize_aurora_cluster,
    normalize_rds_instance,
    normalize_rds_snapshot,
)
from perpetual.normalization.aws.s3 import normalize_s3_bucket
from perpetual.normalization.aws.supporting import (
    normalize_ecr_registry,
    normalize_ecr_repository,
    normalize_iam_policy,
    normalize_iam_role,
    normalize_kms_key,
    normalize_log_group,
    normalize_secretsmanager_secret,
    normalize_ssm_parameter,
)
from perpetual.normalization.identity import AttributeConflict, resolve_identities


class AwsFixtureError(ValueError):
    """Raised when a recorded AWS fixture file is missing or malformed."""


@dataclass(frozen=True)
class AwsFixtureImportResult:
    """Normalized resources and diagnostics from importing a recorded AWS fixture."""

    account_id: str
    collected_at: datetime
    nodes: list[ResourceNode]
    conflicts: list[AttributeConflict]
    counts_by_type: dict[str, int]


def import_aws_fixture_dict(
    payload: Mapping[str, Any],
    *,
    scan_id: str | None = None,
) -> AwsFixtureImportResult:
    """Normalize a parsed recorded-AWS fixture dict and resolve identities."""
    account_id = payload.get("account_id")
    if not isinstance(account_id, str) or not account_id:
        raise AwsFixtureError("recorded AWS fixture requires a non-empty 'account_id'")

    collected_at = parse_aws_datetime(payload.get("collected_at")) or datetime.now(UTC)
    raw_nodes: list[ResourceNode] = []

    global_section = payload.get("global", {})
    if isinstance(global_section, Mapping):
        raw_nodes.extend(
            _normalize_global_section(
                global_section,
                account_id=account_id,
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )

    regions_section = payload.get("regions", {})
    if isinstance(regions_section, Mapping):
        for region, region_data in regions_section.items():
            if not isinstance(region_data, Mapping):
                raise AwsFixtureError(f"region {region!r} must map to an object")
            raw_nodes.extend(
                _normalize_region_section(
                    region_data,
                    account_id=account_id,
                    region=str(region),
                    collected_at=collected_at,
                    scan_id=scan_id,
                )
            )

    resolved = resolve_identities(raw_nodes)
    counts = Counter(f"{n.service}/{n.resource_type}" for n in resolved.nodes)
    return AwsFixtureImportResult(
        account_id=account_id,
        collected_at=collected_at,
        nodes=resolved.nodes,
        conflicts=resolved.conflicts,
        counts_by_type=dict(sorted(counts.items())),
    )


def import_aws_fixture_file(
    path: Path,
    *,
    scan_id: str | None = None,
) -> AwsFixtureImportResult:
    """Load and normalize a recorded AWS JSON fixture from disk."""
    if not path.is_file():
        raise AwsFixtureError(f"recorded AWS fixture not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AwsFixtureError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise AwsFixtureError(f"recorded AWS fixture must be a JSON object: {path}")
    return import_aws_fixture_dict(data, scan_id=scan_id)


def resolve_aws_fixture_path(name_or_path: str, *, base_dir: Path | None = None) -> Path:
    """Resolve either an explicit file path or a fixture name under `fixtures/aws/`."""
    direct = Path(name_or_path)
    if direct.is_file():
        return direct
    root = base_dir if base_dir is not None else _default_aws_fixtures_dir()
    candidate = root / f"{name_or_path}.json"
    if candidate.is_file():
        return candidate
    candidate_exact = root / name_or_path
    if candidate_exact.is_file():
        return candidate_exact
    raise AwsFixtureError(
        f"recorded AWS fixture {name_or_path!r} not found (checked {direct} and {root})"
    )


def _default_aws_fixtures_dir() -> Path:
    # Walk upward from this module until we find the repo's fixtures/aws directory.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "fixtures" / "aws"
        if candidate.is_dir():
            return candidate
    return Path("fixtures/aws")


def _normalize_global_section(
    section: Mapping[str, Any],
    *,
    account_id: str,
    collected_at: datetime,
    scan_id: str | None,
) -> list[ResourceNode]:
    nodes: list[ResourceNode] = []
    for role in section.get("iam_roles", []):
        nodes.append(
            normalize_iam_role(
                role,
                account_id=account_id,
                collected_at=collected_at,
                attached_policy_arns=role.get("_attached_policy_arns", ()),
                inline_policy_documents=role.get("_inline_policy_documents", ()),
                instance_profile_arns=role.get("_instance_profile_arns", ()),
                scan_id=scan_id,
            )
        )
    for policy in section.get("iam_policies", []):
        nodes.append(
            normalize_iam_policy(
                policy,
                account_id=account_id,
                collected_at=collected_at,
                policy_document=policy.get("_policy_document"),
                scan_id=scan_id,
            )
        )
    for zone in section.get("route53_hosted_zones", []):
        nodes.append(
            normalize_hosted_zone(
                zone,
                account_id=account_id,
                collected_at=collected_at,
                vpc_ids=zone.get("_vpc_ids", ()),
                accelerated_recovery_enabled=zone.get("_accelerated_recovery_enabled"),
                tags=zone.get("_tags"),
                scan_id=scan_id,
            )
        )
    for rec in section.get("route53_record_sets", []):
        nodes.append(
            normalize_record_set(
                rec,
                account_id=account_id,
                hosted_zone_id=str(rec["_hosted_zone_id"]),
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )
    return nodes


def _normalize_region_section(
    section: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None,
) -> list[ResourceNode]:
    """Normalize all Regional resource lists inside one recorded AWS fixture region."""
    return [
        *_normalize_network_and_edge(
            section,
            account_id=account_id,
            region=region,
            collected_at=collected_at,
            scan_id=scan_id,
        ),
        *_normalize_compute_and_data(
            section,
            account_id=account_id,
            region=region,
            collected_at=collected_at,
            scan_id=scan_id,
        ),
        *_normalize_supporting_services(
            section,
            account_id=account_id,
            region=region,
            collected_at=collected_at,
            scan_id=scan_id,
        ),
    ]


def _normalize_network_and_edge(
    section: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None,
) -> list[ResourceNode]:
    nodes: list[ResourceNode] = []
    for vpc in section.get("vpcs", []):
        nodes.append(
            normalize_vpc(
                vpc,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )
    for subnet in section.get("subnets", []):
        nodes.append(
            normalize_subnet(
                subnet,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                route_table_id=subnet.get("_route_table_id"),
                scan_id=scan_id,
            )
        )
    for sg in section.get("security_groups", []):
        nodes.append(
            normalize_security_group(
                sg, account_id=account_id, region=region, collected_at=collected_at, scan_id=scan_id
            )
        )
    for lb in section.get("load_balancers", []):
        nodes.append(
            normalize_load_balancer(
                lb,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                tags=lb.get("_tags"),
                web_acl_arn=lb.get("_web_acl_arn"),
                scan_id=scan_id,
            )
        )
    for listener in section.get("listeners", []):
        nodes.append(
            normalize_listener(
                listener,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )
    for tg in section.get("target_groups", []):
        nodes.append(
            normalize_target_group(
                tg,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                registered_target_ids=tg.get("_registered_target_ids", ()),
                tags=tg.get("_tags"),
                scan_id=scan_id,
            )
        )
    for cert in section.get("acm_certificates", []):
        nodes.append(
            normalize_acm_certificate(
                cert,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                tags=cert.get("_tags"),
                scan_id=scan_id,
            )
        )
    return nodes


def _normalize_compute_and_data(
    section: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None,
) -> list[ResourceNode]:
    nodes: list[ResourceNode] = []
    for cluster in section.get("ecs_clusters", []):
        nodes.append(
            normalize_ecs_cluster(
                cluster,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )
    for service in section.get("ecs_services", []):
        nodes.append(
            normalize_ecs_service(
                service,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                auto_scaling=service.get("_auto_scaling"),
                scan_id=scan_id,
            )
        )
    for td in section.get("ecs_task_definitions", []):
        nodes.append(
            normalize_ecs_task_definition(
                td, account_id=account_id, region=region, collected_at=collected_at, scan_id=scan_id
            )
        )
    for db in section.get("rds_instances", []):
        nodes.append(
            normalize_rds_instance(
                db,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                replicated_automated_backup_regions=db.get(
                    "_replicated_automated_backup_regions", ()
                ),
                scan_id=scan_id,
            )
        )
    for aurora in section.get("aurora_clusters", []):
        nodes.append(
            normalize_aurora_cluster(
                aurora,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                global_cluster_identifier=aurora.get("_global_cluster_identifier"),
                global_cluster_role=aurora.get("_global_cluster_role"),
                scan_id=scan_id,
            )
        )
    for snap in section.get("rds_snapshots", []):
        nodes.append(
            normalize_rds_snapshot(
                snap,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                cluster_snapshot=bool(snap.get("_cluster_snapshot", False)),
                scan_id=scan_id,
            )
        )
    for bucket in section.get("s3_buckets", []):
        nodes.append(
            normalize_s3_bucket(
                bucket_name=str(bucket["Name"]),
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                versioning_response=bucket.get("_versioning"),
                replication_response=bucket.get("_replication"),
                encryption_response=bucket.get("_encryption"),
                ownership_response=bucket.get("_ownership"),
                object_lock_response=bucket.get("_object_lock"),
                lifecycle_rules=bucket.get("_lifecycle_rules", ()),
                tags=bucket.get("_tags"),
                scan_id=scan_id,
            )
        )
    return nodes


def _normalize_supporting_services(
    section: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None,
) -> list[ResourceNode]:
    nodes: list[ResourceNode] = []
    for repo in section.get("ecr_repositories", []):
        nodes.append(
            normalize_ecr_repository(
                repo,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                tags=repo.get("_tags"),
                scan_id=scan_id,
            )
        )
    if section.get("ecr_registry"):
        nodes.append(
            normalize_ecr_registry(
                section["ecr_registry"],
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )
    for secret in section.get("secrets", []):
        nodes.append(
            normalize_secretsmanager_secret(
                secret,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                scan_id=scan_id,
            )
        )
    for param in section.get("ssm_parameters", []):
        nodes.append(
            normalize_ssm_parameter(
                param,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                tags=param.get("_tags"),
                scan_id=scan_id,
            )
        )
    for key in section.get("kms_keys", []):
        nodes.append(
            normalize_kms_key(
                key,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                aliases=key.get("_aliases", ()),
                tags=key.get("_tags"),
                scan_id=scan_id,
            )
        )
    for lg in section.get("log_groups", []):
        nodes.append(
            normalize_log_group(
                lg,
                account_id=account_id,
                region=region,
                collected_at=collected_at,
                subscription_destination_arns=lg.get("_subscription_destination_arns", ()),
                tags=lg.get("_tags"),
                scan_id=scan_id,
            )
        )
    return nodes
