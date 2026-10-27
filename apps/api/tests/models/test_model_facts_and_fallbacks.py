"""External, generic and out-of-scope resources; quota, offering, capability and metric
facts (spec §15.2, §24.1, §28.1, §76.1)."""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from perpetual.models import (
    CapabilityFact,
    FactRecord,
    InstanceTypeOfferingFact,
    MetricFact,
    QuotaFact,
    ResourceNode,
)
from perpetual.models.override import DrPosture
from perpetual.models.properties import (
    SPECIFIC_TYPE_KEYS,
    ExternalResourceProperties,
    GenericResourceProperties,
)
from tests.models.builders import NOW


def node(provider: str, service: str, resource_type: str, typed: dict[str, Any]) -> ResourceNode:
    return ResourceNode.model_validate(
        {
            "id": f"{provider}://x/{service}/{resource_type}/1",
            "provider": provider,
            "service": service,
            "resource_type": resource_type,
            "typed_properties": typed,
            "discovered_at": NOW,
        }
    )


# --- external, generic, out of scope ---------------------------------------------------


def test_external_node_keeps_its_own_service_name_and_defaults_to_unknown() -> None:
    built = node("external", "payments-gateway", "saas", {"type_key": "external/dependency"})
    assert isinstance(built.typed_properties, ExternalResourceProperties)
    assert built.typed_properties.dr_posture is DrPosture.UNKNOWN


def test_external_properties_need_an_external_provider() -> None:
    with pytest.raises(ValidationError, match='need provider "external"'):
        node("aws", "rds", "db", {"type_key": "external/dependency"})


def test_generic_fallback_for_an_unmodelled_type() -> None:
    built = node(
        "aws",
        "elasticache",
        "replicationgroup",
        {"type_key": "generic/resource", "terraform_type": "aws_elasticache_replication_group"},
    )
    assert isinstance(built.typed_properties, GenericResourceProperties)


def test_generic_fallback_cannot_replace_a_typed_model() -> None:
    assert "rds/db" in SPECIFIC_TYPE_KEYS
    with pytest.raises(ValidationError, match="has its own typed model"):
        node("aws", "rds", "db", {"type_key": "generic/resource"})


def test_generic_fallback_is_not_for_external_nodes() -> None:
    with pytest.raises(ValidationError, match="external/dependency"):
        node("external", "crm", "saas", {"type_key": "generic/resource"})


def test_codepipeline_role_is_required_or_unknown() -> None:
    built = node(
        "aws",
        "codepipeline",
        "pipeline",
        {
            "type_key": "codepipeline/pipeline",
            "pipeline_name": "deploy",
            "unknown_fields": ["role_arn"],
            "action_regions": ["ap-south-1", "ap-south-2"],
        },
    )
    assert built.typed_properties is not None


# --- facts ---------------------------------------------------------------------------------

BASE: dict[str, Any] = {
    "id": "fact-1",
    "account_id": "123456789012",
    "region": "ap-south-2",
    "collected_at": NOW,
}


def quota(**overrides: Any) -> QuotaFact:
    fields: dict[str, Any] = {
        **BASE,
        "service_code": "fargate",
        "quota_code": "L-3032A538",
        "quota_name": "Fargate On-Demand vCPU resource count",
        "value": 100,
    }
    fields.update(overrides)
    return QuotaFact.model_validate(fields)


def test_headroom_needs_both_limit_and_usage() -> None:
    assert quota().headroom is None  # a limit alone proves nothing
    assert quota(usage=30, usage_collected_at=NOW).headroom == 70


def test_quota_usage_has_a_timestamp() -> None:
    with pytest.raises(ValidationError, match="set together"):
        quota(usage=30)


def test_instance_type_offerings_are_a_sorted_set() -> None:
    offering = InstanceTypeOfferingFact.model_validate(
        {
            **BASE,
            "location_type": "region",
            "location": "ap-south-2",
            "instance_types": ["m7g.large", "c7g.large", "m7g.large"],
        }
    )
    assert offering.instance_types == ["c7g.large", "m7g.large"]


def test_catalog_capability_names_its_version() -> None:
    with pytest.raises(ValidationError, match="catalog_version"):
        CapabilityFact.model_validate(
            {
                **BASE,
                "capability": "feature:aurora-global-database",
                "status": "available",
                "source": "versioned_catalog",
            }
        )


def metric(**overrides: Any) -> MetricFact:
    fields: dict[str, Any] = {
        **BASE,
        "resource_id": "aws://1/ap-south-2/rds/db/checkout-replica",
        "namespace": "AWS/RDS",
        "metric_name": "ReplicaLag",
        "statistic": "Maximum",
        "unit": "Seconds",
        "period_seconds": 60,
        "window_start": NOW - timedelta(minutes=10),
        "window_end": NOW,
        "status": "ok",
        "samples": [
            {"timestamp": NOW - timedelta(minutes=2), "value": 4.0},
            {"timestamp": NOW - timedelta(minutes=1), "value": 6.0},
        ],
        "expected_samples": 10,
    }
    fields.update(overrides)
    return MetricFact.model_validate(fields)


def test_metric_reports_latest_sample_and_gaps() -> None:
    series = metric()
    assert series.latest_sample_at == NOW - timedelta(minutes=1)
    assert series.missing_samples == 8


@pytest.mark.parametrize("status", ["no_data", "access_denied", "error"])
def test_only_an_ok_read_carries_samples(status: str) -> None:
    assert metric(status=status, samples=[]).latest_sample_at is None
    with pytest.raises(ValidationError, match="status ok has samples"):
        metric(status=status)


def test_ok_read_without_samples_is_rejected() -> None:
    # Otherwise "no data" could be read as a value of zero.
    with pytest.raises(ValidationError, match="status ok has samples"):
        metric(samples=[])


def test_samples_are_ordered_and_inside_the_window() -> None:
    late = NOW - timedelta(minutes=1)
    early = NOW - timedelta(minutes=2)
    with pytest.raises(ValidationError, match="time order"):
        metric(samples=[{"timestamp": late, "value": 1.0}, {"timestamp": early, "value": 2.0}])
    with pytest.raises(ValidationError, match="inside the window"):
        metric(samples=[{"timestamp": NOW + timedelta(minutes=5), "value": 1.0}])


def test_fact_records_are_chosen_by_kind() -> None:
    adapter: TypeAdapter[Any] = TypeAdapter(FactRecord)
    parsed = adapter.validate_python(
        {
            **BASE,
            "kind": "capability",
            "capability": "service:dynamodb",
            "status": "unknown",
            "source": "api",
        }
    )
    assert isinstance(parsed, CapabilityFact)
