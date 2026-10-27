"""Typed properties for messaging, network, edge, supporting services, ARC and Identity Center
(spec §7.1, §8, §8.1, §28.1), plus checks on the union itself."""

import inspect
import typing
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from perpetual.models import properties
from perpetual.models.properties import (
    CloudFrontDistributionProperties,
    HostedZoneProperties,
    IdentityCenterInstanceProperties,
    KMSKeyProperties,
    ListenerProperties,
    PolicyStatement,
    RecordSetProperties,
    RegionSwitchPlanProperties,
    RegionSwitchStep,
    ResourceProperties,
    SecretProperties,
    SecurityGroupRule,
    SNSSubscriptionProperties,
    SQSQueueProperties,
    SSMParameterProperties,
    TypedProperties,
)

# --- the union --------------------------------------------------------------


def union_members() -> list[type[BaseModel]]:
    return list(typing.get_args(typing.get_args(ResourceProperties)[0]))


def test_every_properties_model_is_in_the_union() -> None:
    defined = {
        cls
        for _, cls in inspect.getmembers(properties, inspect.isclass)
        if issubclass(cls, TypedProperties) and cls is not TypedProperties
    }
    missing = defined - set(union_members())
    assert not missing, f"add to ResourceProperties: {sorted(c.__name__ for c in missing)}"


def test_type_keys_are_unique() -> None:
    keys = [
        key
        for model in union_members()
        for key in typing.get_args(model.model_fields["type_key"].annotation)
    ]
    assert len(keys) == len(set(keys))


# --- messaging --------------------------------------------------------------


def test_sqs_redrive_names_queue_and_count_together() -> None:
    with pytest.raises(ValidationError, match="set together"):
        SQSQueueProperties(queue_name="orders", dead_letter_queue_arn="arn:aws:sqs:x:1:orders-dlq")


@pytest.mark.parametrize("protocol", ["email", "sms", "https"])
def test_sns_endpoints_of_people_and_urls_are_not_stored(protocol: str) -> None:
    with pytest.raises(ValidationError, match="are not stored"):
        SNSSubscriptionProperties.model_validate(
            {"topic_arn": "arn:aws:sns:x:1:t", "protocol": protocol, "endpoint": "someone"}
        )


def test_sns_resource_endpoint_is_stored() -> None:
    sub = SNSSubscriptionProperties(
        topic_arn="arn:aws:sns:x:1:t", protocol="sqs", endpoint="arn:aws:sqs:x:1:orders"
    )
    assert sub.endpoint == "arn:aws:sqs:x:1:orders"


# --- network and load balancing ----------------------------------------------


def test_security_group_ports_are_ordered() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        SecurityGroupRule(protocol="tcp", from_port=443, to_port=80)


@pytest.mark.parametrize("protocol", ["HTTPS", "TLS"])
def test_tls_listener_needs_a_certificate(protocol: str) -> None:
    with pytest.raises(ValidationError, match="needs a certificate"):
        ListenerProperties.model_validate(
            {
                "load_balancer_arn": "arn:aws:elasticloadbalancing:x",
                "protocol": protocol,
                "port": 443,
            }
        )


# --- edge ------------------------------------------------------------------------


def test_private_zone_needs_a_vpc_and_has_no_accelerated_recovery() -> None:
    with pytest.raises(ValidationError, match="at least one VPC"):
        HostedZoneProperties(zone_id="Z1", name="internal.", private=True)
    with pytest.raises(ValidationError, match="only available for public zones"):
        HostedZoneProperties(
            zone_id="Z1",
            name="internal.",
            private=True,
            vpc_ids=["vpc-1"],
            accelerated_recovery_enabled=True,
        )


def record(**overrides: Any) -> RecordSetProperties:
    fields: dict[str, Any] = {
        "hosted_zone_id": "Z1",
        "name": "api.example.com.",
        "record_type": "A",
    }
    fields.update(overrides)
    return RecordSetProperties.model_validate(fields)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "alias_target": {"dns_name": "lb.example", "hosted_zone_id": "Z2"},
                "values": ["10.0.0.1"],
            },
            "alias or has values",
        ),
        ({"routing_policy": "weighted", "weight": 10}, "needs a set_identifier"),
        ({"routing_policy": "failover", "set_identifier": "primary"}, "exactly for failover"),
        ({"failover_role": "PRIMARY"}, "exactly for failover"),
    ],
)
def test_record_routing_must_be_consistent(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        record(**overrides)


def test_failover_record_is_valid() -> None:
    primary = record(
        routing_policy="failover",
        set_identifier="primary",
        failover_role="PRIMARY",
        health_check_id="hc-1",
        values=["10.0.0.1"],
    )
    assert primary.failover_role == "PRIMARY"


def test_cloudfront_origin_groups_use_known_distinct_origins() -> None:
    base: dict[str, Any] = {
        "distribution_id": "E1",
        "domain_name": "d1.cloudfront.net",
        "origins": [{"origin_id": "primary", "domain_name": "a.example"}],
    }
    with pytest.raises(ValidationError, match="unknown origins"):
        CloudFrontDistributionProperties.model_validate(
            {
                **base,
                "origin_groups": [
                    {"group_id": "g", "primary_origin_id": "primary", "secondary_origin_id": "dr"}
                ],
            }
        )
    with pytest.raises(ValidationError, match="fails over to itself"):
        CloudFrontDistributionProperties.model_validate(
            {
                **base,
                "origin_groups": [
                    {
                        "group_id": "g",
                        "primary_origin_id": "primary",
                        "secondary_origin_id": "primary",
                    }
                ],
            }
        )


# --- supporting services -----------------------------------------------------------


def test_only_secure_string_parameters_use_kms() -> None:
    with pytest.raises(ValidationError, match="only SecureString"):
        SSMParameterProperties(name="/app/mode", parameter_type="String", kms_key_id="alias/x")


def test_parameter_value_cannot_be_stored() -> None:
    with pytest.raises(ValidationError):
        SSMParameterProperties.model_validate(
            {"name": "/app/token", "parameter_type": "SecureString", "value": "hunter2"}
        )


def test_secret_has_one_replica_per_region() -> None:
    with pytest.raises(ValidationError, match="one replica per Region"):
        SecretProperties.model_validate(
            {"name": "db", "replicas": [{"region": "ap-south-2"}, {"region": "ap-south-2"}]}
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"multi_region": True}, "exactly for multi-Region keys"),
        ({"multi_region_role": "PRIMARY"}, "exactly for multi-Region keys"),
        ({"multi_region": True, "multi_region_role": "REPLICA"}, "names its primary_key_arn"),
        ({"replica_regions": ["ap-south-2"]}, "only multi-Region keys"),
    ],
)
def test_kms_multi_region_fields_agree(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        KMSKeyProperties.model_validate({"key_id": "k1", **fields})


def test_policy_statement_needs_actions() -> None:
    with pytest.raises(ValidationError, match="actions or not_actions"):
        PolicyStatement(effect="Allow", resources=["*"])


# --- ARC and Identity Center -----------------------------------------------------------


def plan(**overrides: Any) -> RegionSwitchPlanProperties:
    fields: dict[str, Any] = {
        "name": "checkout",
        "recovery_approach": "activePassive",
        "regions": ["ap-south-1", "ap-south-2"],
        "primary_region": "ap-south-1",
        "execution_role_arn": "arn:aws:iam::1:role/arc",
    }
    fields.update(overrides)
    return RegionSwitchPlanProperties.model_validate(fields)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"regions": ["ap-south-1", "ap-south-1"]}, "two distinct Regions"),
        ({"primary_region": "us-east-1"}, "must be one of the plan's Regions"),
        (
            {"workflows": [{"target_action": "activate", "target_region": "us-east-1"}]},
            "not a plan Region",
        ),
    ],
)
def test_region_switch_plan_regions_are_consistent(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        plan(**overrides)


def test_region_switch_plan_has_exactly_two_regions() -> None:
    with pytest.raises(ValidationError):
        plan(regions=["ap-south-1"])


def test_parallel_steps_nest_one_level() -> None:
    inner = {
        "name": "inner",
        "execution_block_type": "Parallel",
        "parallel_steps": [{"name": "leaf", "execution_block_type": "ECSServiceScaling"}],
    }
    with pytest.raises(ValidationError, match="cannot contain parallel"):
        RegionSwitchStep.model_validate(
            {"name": "outer", "execution_block_type": "Parallel", "parallel_steps": [inner]}
        )


def test_identity_center_replica_is_another_region() -> None:
    with pytest.raises(ValidationError, match="not also a replica"):
        IdentityCenterInstanceProperties(
            instance_arn="arn:aws:sso:::instance/ssoins-1",
            home_region="ap-south-1",
            replica_regions=["ap-south-1"],
        )
