"""Canonical resource IDs (spec §15, §15.1, §15.2)."""

import pytest

from perpetual.ids import (
    AwsResourceId,
    ExternalResourceId,
    InvalidResourceIdError,
    PlannedAddress,
    aws_id,
    external_id,
    global_id,
    is_valid,
    parse,
    parse_aws,
    planned_id,
)

ACCOUNT = "123456789012"


def test_spec_examples_round_trip() -> None:
    for text in (
        "aws://123456789012/ap-south-1/rds/db/prod-mysql",
        "aws://123456789012/global/route53/hostedzone/Z123",
    ):
        assert str(parse(text)) == text


def test_live_id_parts() -> None:
    built = aws_id(ACCOUNT, "ap-south-1", "rds", "db", "prod-mysql")
    assert built == "aws://123456789012/ap-south-1/rds/db/prod-mysql"
    parsed = parse_aws(built)
    assert parsed == AwsResourceId(ACCOUNT, "ap-south-1", "rds", "db", "prod-mysql")
    assert parsed.type_key == "rds/db"
    assert not parsed.is_global
    assert not parsed.is_planned
    assert parsed.planned_address is None


def test_global_id() -> None:
    built = global_id(ACCOUNT, "iam", "role", "checkout-task")
    assert built == "aws://123456789012/global/iam/role/checkout-task"
    assert parse_aws(built).is_global


def test_identifier_may_contain_slashes() -> None:
    # CloudWatch log group names start with and contain "/".
    built = aws_id(ACCOUNT, "ap-south-1", "logs", "log-group", "/aws/ecs/checkout")
    assert built == "aws://123456789012/ap-south-1/logs/log-group//aws/ecs/checkout"
    assert parse_aws(built).identifier == "/aws/ecs/checkout"


def test_planned_id_round_trips_and_keeps_colons_in_the_address() -> None:
    address = 'module.db["primary:1"].aws_db_instance.this'
    built = planned_id(
        ACCOUNT,
        "ap-south-2",
        "rds",
        "db",
        root_id="infra-prod",
        workspace="default",
        address=address,
    )
    assert built == f"aws://123456789012/ap-south-2/rds/db/tf:infra-prod:default:{address}"
    parsed = parse_aws(built)
    assert parsed.is_planned
    assert parsed.planned_address == PlannedAddress("infra-prod", "default", address)
    assert str(parsed) == built


def test_a_live_identifier_cannot_look_planned() -> None:
    with pytest.raises(InvalidResourceIdError, match="use planned_id"):
        aws_id(ACCOUNT, "ap-south-1", "rds", "db", "tf:x:y:z")


@pytest.mark.parametrize(
    ("root_id", "workspace", "address", "message"),
    [
        ("infra:prod", "default", "aws_db_instance.a", "root_id must not contain ':'"),
        ("infra", "de:fault", "aws_db_instance.a", "workspace must not contain ':'"),
        ("", "default", "aws_db_instance.a", "root_id must not be empty"),
        ("infra", "default", "", "terraform address must not be empty"),
    ],
)
def test_planned_parts_are_checked(
    root_id: str, workspace: str, address: str, message: str
) -> None:
    with pytest.raises(InvalidResourceIdError, match=message):
        planned_id(
            ACCOUNT,
            "ap-south-1",
            "rds",
            "db",
            root_id=root_id,
            workspace=workspace,
            address=address,
        )


def test_malformed_planned_id_fails_to_parse() -> None:
    with pytest.raises(InvalidResourceIdError, match="expected tf:"):
        parse("aws://123456789012/ap-south-1/rds/db/tf:only-root")


def test_external_id() -> None:
    built = external_id("payments-gateway", "stripe")
    assert built == "external://payments-gateway/stripe"
    assert parse(built) == ExternalResourceId("payments-gateway", "stripe")
    with pytest.raises(InvalidResourceIdError, match="not an AWS resource ID"):
        parse_aws(built)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("arn:aws:rds:ap-south-1:123456789012:db:x", "unknown ID scheme"),
        ("aws://123456789012/ap-south-1/rds/db", "expected aws://"),
        ("aws://1/ap-south-1/rds/db/x", "12 digits"),
        ("aws://123456789012/mumbai/rds/db/x", "not an AWS Region"),
        ("aws://123456789012/ap-south-1/RDS/db/x", "service must be lowercase"),
        ("aws://123456789012/ap-south-1/rds/db_instance/x", "resource type must be lowercase"),
        ("aws://123456789012/ap-south-1/rds/db/", "identifier must not be empty"),
        ("aws://123456789012/ap-south-1/rds/db/a\nb", "control characters"),
        ("external://payments-gateway", "expected external://"),
    ],
)
def test_invalid_ids(text: str, message: str) -> None:
    with pytest.raises(InvalidResourceIdError, match=message):
        parse(text)
    assert not is_valid(text)


@pytest.mark.parametrize("region", ["us-gov-west-1", "cn-north-1", "ap-southeast-5", "global"])
def test_other_partitions_and_global(region: str) -> None:
    assert is_valid(f"aws://{ACCOUNT}/{region}/ec2/vpc/vpc-1")


def test_ids_are_hashable_values() -> None:
    a = parse("aws://123456789012/ap-south-1/sqs/queue/orders")
    b = parse("aws://123456789012/ap-south-1/sqs/queue/orders")
    assert a == b
    assert len({a, b}) == 1
