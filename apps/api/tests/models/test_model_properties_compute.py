"""Typed properties for ECS, EC2/Auto Scaling and Lambda (spec §5.1, §5.3, §5.4, §15.3)."""

from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import ResourceNode
from perpetual.models.properties import (
    AutoScalingGroupProperties,
    ECSServiceProperties,
    ECSTaskDefinitionProperties,
    LambdaFunctionProperties,
    LaunchTemplateProperties,
)
from tests.models.builders import NOW

SERVICE_PROPS: dict[str, Any] = {
    "type_key": "ecs/service",
    "service_name": "checkout",
    "cluster_arn": "arn:aws:ecs:ap-south-1:1:cluster/prod",
    "task_definition_arn": "arn:aws:ecs:ap-south-1:1:task-definition/checkout:7",
    "launch_type": "FARGATE",
    "desired_count": 3,
}


def make_node(service: str, resource_type: str, typed: dict[str, Any]) -> ResourceNode:
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


def test_type_key_picks_the_typed_model() -> None:
    node = make_node("ecs", "service", SERVICE_PROPS)
    assert isinstance(node.typed_properties, ECSServiceProperties)
    assert node.typed_properties.desired_count == 3


def test_typed_properties_must_match_the_node_type() -> None:
    with pytest.raises(ValidationError, match="but this node is 'rds/db'"):
        make_node("rds", "db", SERVICE_PROPS)


def test_unknown_type_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_node("ecs", "service", {**SERVICE_PROPS, "type_key": "ecs/widget"})


def test_unknown_fields_mark_plan_values_known_after_apply() -> None:
    props = ECSServiceProperties.model_validate(
        {**SERVICE_PROPS, "unknown_fields": ["subnet_ids", "security_group_ids"]}
    )
    assert props.unknown_fields == ["subnet_ids", "security_group_ids"]
    assert props.subnet_ids == []  # the stored default; rules must read it as UNKNOWN


def test_unknown_fields_must_be_real_fields() -> None:
    with pytest.raises(ValidationError, match="does not have"):
        ECSServiceProperties.model_validate({**SERVICE_PROPS, "unknown_fields": ["subnets"]})


def test_task_definition_keeps_secret_references_not_values() -> None:
    task = ECSTaskDefinitionProperties.model_validate(
        {
            "family": "checkout",
            "revision": 7,
            "containers": [
                {
                    "name": "app",
                    "image": "1.dkr.ecr.ap-south-1.amazonaws.com/checkout:1.4",
                    "secrets": [{"name": "DB_PASSWORD", "value_from": "arn:aws:secretsmanager:x"}],
                    "environment_names": ["DB_HOST"],
                }
            ],
        }
    )
    assert task.containers[0].secrets[0].value_from == "arn:aws:secretsmanager:x"


@pytest.mark.parametrize(
    "container_extra",
    [
        {"environment": [{"name": "DB_HOST", "value": "prod.db.internal"}]},
        {"secrets": [{"name": "DB_PASSWORD", "value": "hunter2"}]},
    ],
)
def test_env_and_secret_values_cannot_be_stored(container_extra: dict[str, Any]) -> None:
    container = {"name": "app", "image": "img", **container_extra}
    with pytest.raises(ValidationError):
        ECSTaskDefinitionProperties.model_validate(
            {"family": "f", "revision": 1, "containers": [container]}
        )


def test_task_definition_needs_a_container() -> None:
    with pytest.raises(ValidationError):
        ECSTaskDefinitionProperties.model_validate({"family": "f", "revision": 1, "containers": []})


@pytest.mark.parametrize(("minimum", "desired", "maximum"), [(2, 1, 4), (1, 5, 4)])
def test_auto_scaling_sizes_are_ordered(minimum: int, desired: int, maximum: int) -> None:
    with pytest.raises(ValidationError, match="min <= desired <= max"):
        AutoScalingGroupProperties(
            group_name="web", min_size=minimum, desired_capacity=desired, max_size=maximum
        )


def test_launch_template_takes_one_image_source() -> None:
    with pytest.raises(ValidationError, match="not both"):
        LaunchTemplateProperties(
            launch_template_name="web",
            version=3,
            image_id="ami-123",
            image_ssm_parameter="/golden/ami",
        )


def test_launch_template_cannot_store_user_data() -> None:
    with pytest.raises(ValidationError):
        LaunchTemplateProperties.model_validate(
            {"launch_template_name": "web", "version": 1, "user_data": "export TOKEN=abc"}
        )


def lambda_props(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "function_name": "orders",
        "package_type": "Zip",
        "runtime": "python3.13",
        "role_arn": "arn:aws:iam::1:role/orders",
    }
    fields.update(overrides)
    return fields


def test_image_function_needs_an_image() -> None:
    with pytest.raises(ValidationError, match="needs image_uri"):
        LambdaFunctionProperties.model_validate(lambda_props(package_type="Image", runtime=None))


def test_image_function_with_image_known_after_apply_is_valid() -> None:
    props = LambdaFunctionProperties.model_validate(
        lambda_props(package_type="Image", runtime=None, unknown_fields=["image_uri"])
    )
    assert props.image_uri is None


def test_image_function_has_no_layers() -> None:
    with pytest.raises(ValidationError, match="no S3 package or layers"):
        LambdaFunctionProperties.model_validate(
            lambda_props(
                package_type="Image",
                image_uri="1.dkr.ecr.ap-south-1.amazonaws.com/orders:3",
                layer_arns=["arn:aws:lambda:ap-south-1:1:layer:deps:4"],
            )
        )


def test_zip_function_has_no_image() -> None:
    with pytest.raises(ValidationError, match="Zip function has no image_uri"):
        LambdaFunctionProperties.model_validate(lambda_props(image_uri="img"))
