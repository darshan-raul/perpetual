"""Tests for cross-source identity resolution (`P1b-02`, spec §15.1)."""

from __future__ import annotations

from datetime import UTC, datetime

from perpetual.ids import aws_id, planned_id
from perpetual.models.evidence import SourceType
from perpetual.models.properties.rds import RDSInstanceProperties
from perpetual.models.resource import ResourceNode, SourceReference
from perpetual.normalization.identity import resolve_identities

_T1 = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
_T2 = datetime(2026, 11, 24, 12, 5, tzinfo=UTC)
_ACCT = "123456789012"
_REGION = "ap-south-1"


def _rds_node(
    *,
    node_id: str,
    source_type: SourceType,
    locator: str,
    arn: str | None = None,
    terraform_address: str | None = None,
    planned: bool = False,
    multi_az: bool = True,
    backup_retention_days: int = 7,
    tags: dict[str, str] | None = None,
    discovered_at: datetime = _T1,
) -> ResourceNode:
    return ResourceNode(
        id=node_id,
        provider="aws",
        service="rds",
        resource_type="db",
        account_id=_ACCT,
        region=_REGION,
        name="checkout-db",
        arn=arn,
        tags=tags or {},
        properties={},
        typed_properties=RDSInstanceProperties(
            db_instance_identifier="checkout-db",
            engine="postgres",
            instance_class="db.r6g.large",
            multi_az=multi_az,
            backup_retention_days=backup_retention_days,
        ),
        source_refs=[
            SourceReference(
                source_type=source_type,
                locator=locator,
                collected_at=discovered_at,
            )
        ],
        terraform_address=terraform_address,
        planned=planned,
        discovered_at=discovered_at,
    )


def test_arn_match_merges_and_keeps_conflicts_as_separate_evidence() -> None:
    live_id = aws_id(_ACCT, _REGION, "rds", "db", "checkout-db")
    arn = f"arn:aws:rds:{_REGION}:{_ACCT}:db:checkout-db"

    aws_node = _rds_node(
        node_id=live_id,
        source_type=SourceType.AWS_API,
        locator="rds:DescribeDBInstances:checkout-db",
        arn=arn,
        multi_az=True,
        backup_retention_days=7,
        tags={"Env": "prod", "Owner": "payments"},
        discovered_at=_T2,
    )
    tf_node = _rds_node(
        node_id=live_id,
        source_type=SourceType.TERRAFORM,
        locator="infra/prod:default:aws_db_instance.checkout",
        arn=arn,
        terraform_address="aws_db_instance.checkout",
        multi_az=False,
        backup_retention_days=14,
        tags={"Env": "staging", "ManagedBy": "terraform"},
        discovered_at=_T1,
    )

    result = resolve_identities([tf_node, aws_node])

    assert len(result.nodes) == 1
    merged = result.nodes[0]
    assert merged.id == live_id
    assert merged.planned is False
    assert merged.terraform_address == "aws_db_instance.checkout"
    assert len(merged.source_refs) == 2

    # AWS API is authoritative for live configuration, while missing tags are filled from TF.
    assert isinstance(merged.typed_properties, RDSInstanceProperties)
    assert merged.typed_properties.multi_az is True
    assert merged.typed_properties.backup_retention_days == 7
    assert merged.tags == {"Env": "prod", "Owner": "payments", "ManagedBy": "terraform"}

    # Every disagreement is kept as a conflict with separate Evidence per source.
    conflict_attrs = {c.attribute for c in result.conflicts}
    assert conflict_attrs == {
        "tags.Env",
        "typed_properties.multi_az",
        "typed_properties.backup_retention_days",
    }
    assert len(result.conflict_evidence) == 6
    sources_in_evidence = {ev.source_type for ev in result.conflict_evidence}
    assert sources_in_evidence == {SourceType.AWS_API, SourceType.TERRAFORM}


def test_natural_key_match_when_arn_missing() -> None:
    live_id = aws_id(_ACCT, _REGION, "rds", "db", "checkout-db")
    aws_node = _rds_node(
        node_id=live_id,
        source_type=SourceType.AWS_API,
        locator="rds:DescribeDBInstances:checkout-db",
        arn=f"arn:aws:rds:{_REGION}:{_ACCT}:db:checkout-db",
    )
    config_node = _rds_node(
        node_id=live_id,
        source_type=SourceType.AWS_CONFIG,
        locator="config:AWS::RDS::DBInstance:checkout-db",
        arn=None,
    )

    result = resolve_identities([config_node, aws_node])
    assert len(result.nodes) == 1
    assert result.nodes[0].arn == f"arn:aws:rds:{_REGION}:{_ACCT}:db:checkout-db"
    assert len(result.nodes[0].source_refs) == 2
    assert result.conflicts == []


def test_terraform_address_map_rekeys_planned_node_to_live_id() -> None:
    live_id = aws_id(_ACCT, _REGION, "rds", "db", "checkout-db")
    tf_id = planned_id(
        _ACCT,
        _REGION,
        "rds",
        "db",
        root_id="prod",
        workspace="default",
        address="aws_db_instance.checkout",
    )
    live_node = _rds_node(
        node_id=live_id,
        source_type=SourceType.AWS_API,
        locator="rds:DescribeDBInstances:checkout-db",
        arn=f"arn:aws:rds:{_REGION}:{_ACCT}:db:checkout-db",
    )
    planned_node = _rds_node(
        node_id=tf_id,
        source_type=SourceType.TERRAFORM,
        locator="prod:default:aws_db_instance.checkout",
        arn=None,
        terraform_address="aws_db_instance.checkout",
        planned=True,
    )

    result = resolve_identities(
        [planned_node, live_node],
        terraform_address_map={tf_id: live_id},
    )

    assert len(result.nodes) == 1
    assert result.nodes[0].id == live_id
    assert result.nodes[0].planned is False
    assert result.nodes[0].terraform_address == "aws_db_instance.checkout"
    assert result.id_remap == {tf_id: live_id}


def test_unresolved_planned_node_remains_separate() -> None:
    live_id = aws_id(_ACCT, _REGION, "rds", "db", "checkout-db")
    tf_id = planned_id(
        _ACCT,
        "ap-south-2",
        "rds",
        "db",
        root_id="dr",
        workspace="default",
        address="aws_db_instance.dr_replica",
    )
    live_node = _rds_node(
        node_id=live_id,
        source_type=SourceType.AWS_API,
        locator="rds:DescribeDBInstances:checkout-db",
    )
    planned_dr = ResourceNode(
        id=tf_id,
        provider="aws",
        service="rds",
        resource_type="db",
        account_id=_ACCT,
        region="ap-south-2",
        name="checkout-db-dr",
        terraform_address="aws_db_instance.dr_replica",
        planned=True,
        source_refs=[
            SourceReference(
                source_type=SourceType.TERRAFORM,
                locator="dr:default:aws_db_instance.dr_replica",
                collected_at=_T1,
            )
        ],
        discovered_at=_T1,
    )

    result = resolve_identities([live_node, planned_dr])
    assert len(result.nodes) == 2
    by_id = {n.id: n for n in result.nodes}
    assert by_id[live_id].planned is False
    assert by_id[tf_id].planned is True
    assert result.id_remap == {}
