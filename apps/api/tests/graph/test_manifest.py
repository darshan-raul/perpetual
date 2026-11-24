"""Canonical hashing, immutable snapshot/evaluation manifests and versioned fixtures (P0-15)."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from perpetual.config import load_config
from perpetual.fixtures import check_references, load_fixture, parse_fixture
from perpetual.graph import (
    build_graph,
    build_snapshot_manifest,
    canonical_digest,
    canonical_json,
    config_digest,
    evaluation_input_digest,
)
from perpetual.ids import aws_id
from perpetual.models import (
    CoverageStatus,
    EvaluationInput,
    InputKind,
    InputRef,
    ResourceNode,
    ScanCoverage,
)
from perpetual.models.properties import RDSInstanceProperties

UTC_TIME = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
IST_SAME_INSTANT = UTC_TIME.astimezone(timezone(timedelta(hours=5, minutes=30)))
ACCOUNT = "123456789012"
PRIMARY = "ap-south-1"
REPO = Path(__file__).resolve().parents[4]


def _rds_node(
    identifier: str,
    *,
    kms_key_id: str | None = None,
    unknown_fields: list[str] | None = None,
) -> ResourceNode:
    return ResourceNode(
        id=aws_id(ACCOUNT, PRIMARY, "rds", "db", identifier),
        provider="aws",
        service="rds",
        resource_type="db",
        account_id=ACCOUNT,
        region=PRIMARY,
        name=identifier,
        typed_properties=RDSInstanceProperties(
            db_instance_identifier=identifier,
            engine="postgres",
            instance_class="db.r6g.large",
            multi_az=True,
            kms_key_id=kms_key_id,
            unknown_fields=unknown_fields or [],
        ),
        discovered_at=UTC_TIME,
    )


def test_canonical_digest_normalizes_key_order_timezone_and_decimal() -> None:
    first = {"b": Decimal("10.00"), "a": UTC_TIME}
    second = {"a": IST_SAME_INSTANT, "b": Decimal("10")}

    assert canonical_json(first) == canonical_json(second)
    assert canonical_digest(first) == canonical_digest(second)
    assert canonical_digest(first).startswith("sha256:")
    assert len(canonical_digest(first)) == 71


def test_canonical_digest_distinguishes_absent_unknown_and_null() -> None:
    null_kms = _rds_node("orders", kms_key_id=None, unknown_fields=[])
    unknown_kms = _rds_node("orders", kms_key_id=None, unknown_fields=["kms_key_id"])
    present_kms = _rds_node("orders", kms_key_id="arn:aws:kms:ap-south-1:123456789012:key/k1")

    digests = {
        canonical_digest(null_kms),
        canonical_digest(unknown_kms),
        canonical_digest(present_kms),
    }
    assert len(digests) == 3


def test_canonical_digest_rejects_unsupported_objects() -> None:
    with pytest.raises(TypeError, match="unsupported type"):
        canonical_digest(object())


def test_config_digest_is_stable_and_sensitive_to_overrides() -> None:
    default_a = load_config()
    default_b = load_config()
    overridden = load_config({"evidence": {"review_confidence_threshold": 0.85}})

    assert config_digest(default_a) == config_digest(default_b)
    assert config_digest(default_a) != config_digest(overridden)


def test_snapshot_manifest_is_order_independent_and_tracks_changes() -> None:
    minimal = load_fixture(REPO / "fixtures/graphs/minimal.yaml")
    graph_a = build_graph(
        resources=minimal.resources,
        edges=minimal.edges,
        groups=minimal.groups,
        mechanisms=minimal.mechanisms,
        stacks=minimal.stacks,
        stack_resources=minimal.stack_resources,
        stack_services=minimal.stack_services,
    )
    graph_b = build_graph(
        resources=list(reversed(minimal.resources)),
        edges=list(reversed(minimal.edges)),
        groups=minimal.groups,
        mechanisms=minimal.mechanisms,
        stacks=minimal.stacks,
        stack_resources=minimal.stack_resources,
        stack_services=minimal.stack_services,
    )
    coverage = ScanCoverage(
        id="cov-1",
        account_id=ACCOUNT,
        region=PRIMARY,
        service="ecs",
        operation_family="describe_services",
        status=CoverageStatus.COMPLETE,
        started_at=UTC_TIME,
        completed_at=UTC_TIME,
        pagination_complete=True,
    )

    manifest_a = build_snapshot_manifest(
        graph_a,
        snapshot_id="snap-1",
        captured_at=UTC_TIME,
        coverage=[coverage],
        graph_revision=1,
    )
    manifest_b = build_snapshot_manifest(
        graph_b,
        snapshot_id="snap-1",
        captured_at=IST_SAME_INSTANT,
        coverage=[coverage],
        graph_revision=1,
    )
    manifest_rev2 = build_snapshot_manifest(
        graph_a,
        snapshot_id="snap-1",
        captured_at=UTC_TIME,
        coverage=[coverage],
        graph_revision=2,
    )

    assert manifest_a.manifest_digest == manifest_b.manifest_digest
    assert manifest_a.resources_digest == manifest_b.resources_digest
    assert manifest_a.manifest_digest != manifest_rev2.manifest_digest
    assert manifest_a.resource_count == len(minimal.resources)
    assert manifest_a.coverage_count == 1


def test_evaluation_input_digest_binds_every_input_and_ignores_list_order() -> None:
    cfg_hash = config_digest(load_config())
    catalog_hash = canonical_digest({"duration_catalog": "v1"})
    ref_a = InputRef(kind=InputKind.ASSUMPTION, id="a-1", digest=canonical_digest("a"))
    ref_b = InputRef(kind=InputKind.SKILL, id="s-1", digest=canonical_digest("s"))

    ev_a = EvaluationInput(
        id="eval-1",
        stack_id="stk-checkout",
        failure_scenario="region:ap-south-1",
        primary_snapshot_id="snap-1",
        primary_inventory_completed_at=UTC_TIME,
        coverage_ids=["cov-2", "cov-1"],
        graph_revision=1,
        override_revision=0,
        group_revision=0,
        requirement_id="req-1",
        requirement_revision=1,
        engine_version="0.0.0",
        rule_pack_versions={"rds": "1.0", "ecs": "1.0"},
        config_digest=cfg_hash,
        duration_catalog_digest=catalog_hash,
        freshness_policy_version="v1",
        inputs_used=[ref_b, ref_a],
        evaluated_at=UTC_TIME,
    )
    ev_b = EvaluationInput(
        id="eval-1",
        stack_id="stk-checkout",
        failure_scenario="region:ap-south-1",
        primary_snapshot_id="snap-1",
        primary_inventory_completed_at=IST_SAME_INSTANT,
        coverage_ids=["cov-1", "cov-2"],
        graph_revision=1,
        override_revision=0,
        group_revision=0,
        requirement_id="req-1",
        requirement_revision=1,
        engine_version="0.0.0",
        rule_pack_versions={"ecs": "1.0", "rds": "1.0"},
        config_digest=cfg_hash,
        duration_catalog_digest=catalog_hash,
        freshness_policy_version="v1",
        inputs_used=[ref_a, ref_b],
        evaluated_at=IST_SAME_INSTANT,
    )
    ev_changed = ev_a.model_copy(update={"override_revision": 1})

    assert evaluation_input_digest(ev_a) == evaluation_input_digest(ev_b)
    assert evaluation_input_digest(ev_a) != evaluation_input_digest(ev_changed)


def test_fixture_supports_workload_profiles_and_input_versions() -> None:
    raw = yaml.safe_load((REPO / "fixtures/graphs/minimal.yaml").read_text())
    raw["input_versions"] = {
        "graph_revision": 2,
        "override_revision": 1,
        "duration_catalog_version": "v1",
    }
    raw["workload_profiles"] = [
        {
            "id": "wp-checkout",
            "revision": 1,
            "stack_id": "checkout",
            "quantities": [
                {
                    "kind": "stored_gb",
                    "resource_id": "aws://123456789012/ap-south-1/rds/db/checkout",
                    "low": "100",
                    "expected": "150",
                    "high": "200",
                    "unit": "GB",
                    "source": "user_estimate",
                    "confidence": "medium",
                    "assumptions": ["estimated from current RDS allocated storage"],
                }
            ],
        }
    ]

    fixture = parse_fixture(raw)
    assert check_references(fixture) == []
    assert fixture.input_versions is not None
    assert fixture.input_versions.graph_revision == 2
    assert len(fixture.workload_profiles) == 1
    assert fixture.workload_profiles[0].quantities[0].collected_at == fixture.captured_at

    # Bad stack_id and bad resource_id on a workload profile are reported.
    raw["workload_profiles"][0]["stack_id"] = "missing-stack"
    raw["workload_profiles"][0]["quantities"][0]["resource_id"] = (
        "aws://123456789012/ap-south-1/rds/db/nope"
    )
    bad_fixture = parse_fixture(raw)
    issue_strings = [str(issue) for issue in check_references(bad_fixture)]
    assert "workload_profiles[0].stack_id: no stack 'missing-stack'" in issue_strings
    assert any("quantities[0].resource_id" in msg for msg in issue_strings)
