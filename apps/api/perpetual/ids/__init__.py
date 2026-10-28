"""Canonical resource IDs (spec §15, §15.1, §15.2)."""

from perpetual.ids.canonical import (
    GLOBAL_REGION,
    AwsResourceId,
    ExternalResourceId,
    InvalidResourceIdError,
    PlannedAddress,
    ResourceId,
    aws_id,
    external_id,
    global_id,
    is_valid,
    parse,
    parse_aws,
    planned_id,
)

__all__ = [
    "GLOBAL_REGION",
    "AwsResourceId",
    "ExternalResourceId",
    "InvalidResourceIdError",
    "PlannedAddress",
    "ResourceId",
    "aws_id",
    "external_id",
    "global_id",
    "is_valid",
    "parse",
    "parse_aws",
    "planned_id",
]
