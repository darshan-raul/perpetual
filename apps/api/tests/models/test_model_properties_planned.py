"""Planned resources and the three kinds of missing (spec §15.4).

A resource that a Terraform plan will create has no ARN or ID until apply. Its
typed properties must still load, with those values marked unknown, and the
importer must never need to invent them.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models.properties import (
    AuroraClusterProperties,
    ECSServiceProperties,
    ECSTaskDefinitionProperties,
    ListenerProperties,
    RDSInstanceProperties,
    S3BucketProperties,
    SQSQueueProperties,
)

NEW_SERVICE: dict[str, Any] = {
    "service_name": "checkout",
    "desired_count": 2,
    "launch_type": "FARGATE",
}


def test_required_value_must_be_present_or_unknown() -> None:
    with pytest.raises(ValidationError, match="cluster_arn is required"):
        ECSServiceProperties.model_validate({**NEW_SERVICE, "task_definition_arn": "arn:td"})


def test_planned_service_loads_with_unknown_arns() -> None:
    service = ECSServiceProperties.model_validate(
        {**NEW_SERVICE, "unknown_fields": ["task_definition_arn", "cluster_arn"]}
    )
    assert service.cluster_arn is None
    assert service.is_unknown("cluster_arn")
    assert not service.is_missing("cluster_arn")


def test_unknown_fields_are_sorted_and_distinct() -> None:
    service = ECSServiceProperties.model_validate(
        {**NEW_SERVICE, "unknown_fields": ["task_definition_arn", "cluster_arn"]}
    )
    assert service.unknown_fields == ["cluster_arn", "task_definition_arn"]
    with pytest.raises(ValidationError, match="must not repeat"):
        ECSServiceProperties.model_validate(
            {**NEW_SERVICE, "unknown_fields": ["cluster_arn", "cluster_arn", "task_definition_arn"]}
        )


def task_definition(containers: list[dict[str, Any]], **extra: Any) -> ECSTaskDefinitionProperties:
    return ECSTaskDefinitionProperties.model_validate(
        {"family": "checkout", "revision": 1, "containers": containers, **extra}
    )


def test_unknown_nested_value_needs_the_parent_field_marked_unknown() -> None:
    # The image points at an ECR repository the same plan creates, so its URI is unknown.
    with pytest.raises(ValidationError, match=r"ContainerDefinition\.image is required"):
        task_definition([{"name": "app"}])
    planned = task_definition([{"name": "app"}], unknown_fields=["containers"])
    assert planned.containers[0].image is None


def test_computed_number_can_be_unknown() -> None:
    planned = ECSTaskDefinitionProperties.model_validate(
        {
            "family": "checkout",
            "containers": [{"name": "app", "image": "img"}],
            "unknown_fields": ["revision"],
        }
    )
    assert planned.revision is None


def test_zero_and_false_are_values_not_missing() -> None:
    db = RDSInstanceProperties(
        db_instance_identifier="checkout-db",
        engine="postgres",
        instance_class="db.r6g.large",
        backup_retention_days=0,
        multi_az=False,
    )
    assert not db.is_missing("backup_retention_days")
    assert not db.is_missing("multi_az")
    assert db.is_missing("read_replica_arns")  # an empty list is missing


def test_empty_certificate_list_is_still_missing() -> None:
    with pytest.raises(ValidationError, match="needs a certificate"):
        ListenerProperties.model_validate(
            {
                "load_balancer_arn": "arn:lb",
                "protocol": "HTTPS",
                "port": 443,
                "certificate_arns": [],
            }
        )


def test_planned_global_secondary_with_unknown_membership_loads() -> None:
    cluster = AuroraClusterProperties.model_validate(
        {
            "db_cluster_identifier": "checkout-dr",
            "engine": "aurora-postgresql",
            "global_cluster_role": "secondary",
            "unknown_fields": ["global_cluster_identifier"],
        }
    )
    assert cluster.global_cluster_identifier is None


def test_s3_versioning_unknown_in_plan_allows_replication() -> None:
    rule = {"rule_id": "to-dr", "status": "Enabled", "destination_bucket_arn": "arn:aws:s3:::dr"}
    bucket = S3BucketProperties.model_validate(
        {
            "bucket_name": "assets",
            "replication_role_arn": "arn:aws:iam::1:role/replication",
            "replication_rules": [rule],
            "unknown_fields": ["versioning"],
        }
    )
    assert bucket.versioning is None
    with pytest.raises(ValidationError, match="versioning is required"):
        S3BucketProperties.model_validate({"bucket_name": "assets"})


def test_planned_queue_with_new_dlq_loads() -> None:
    # The plan creates the queue and its DLQ together: the receive count is known,
    # the DLQ's ARN only after apply.
    queue = SQSQueueProperties.model_validate(
        {
            "queue_name": "orders",
            "max_receive_count": 5,
            "unknown_fields": ["dead_letter_queue_arn"],
        }
    )
    assert queue.dead_letter_queue_arn is None
    with pytest.raises(ValidationError, match="set together"):
        SQSQueueProperties.model_validate({"queue_name": "orders", "max_receive_count": 5})
