"""Typed properties for AWS Lambda (spec §5.4).

Named `awslambda` because `lambda` is a Python keyword.

A function can only run in the DR Region if its code (S3 package or ECR image),
its layers, its role and its VPC configuration all exist there. Layer ARNs and
image URIs embed a Region, which is how the rules spot primary-only references.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class LambdaFunctionProperties(TypedProperties):
    type_key: Literal["lambda/function"] = "lambda/function"
    function_name: NonEmptyStr
    package_type: Literal["Zip", "Image"]
    runtime: str | None = None
    """None for container-image functions."""
    code_s3_bucket: str | None = None
    """Known only from IaC; the Lambda API returns a temporary download URL instead."""
    code_s3_key: str | None = None
    image_uri: str | None = None
    layer_arns: list[NonEmptyStr] = Field(default_factory=list)
    role_arn: NonEmptyStr
    subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    environment_names: list[NonEmptyStr] = Field(default_factory=list)
    """Variable names only; values are never stored (spec §67)."""
    kms_key_arn: str | None = None
    dead_letter_target_arn: str | None = None
    on_success_destination_arn: str | None = None
    on_failure_destination_arn: str | None = None
    reserved_concurrency: int | None = Field(default=None, ge=0)
    provisioned_concurrency: int | None = Field(default=None, ge=0)
    architectures: list[Literal["x86_64", "arm64"]] = Field(default_factory=list)
    timeout_seconds: int | None = Field(default=None, ge=1)
    memory_mb: int | None = Field(default=None, ge=128)

    @model_validator(mode="after")
    def _code_matches_package_type(self) -> Self:
        # An image function runs from ECR and has no S3 package or layers; a zip
        # function has no image. Mixing them means the import is wrong.
        if self.package_type == "Image":
            if not self.image_uri and "image_uri" not in self.unknown_fields:
                raise ValueError("an Image function needs image_uri")
            if self.code_s3_bucket or self.layer_arns:
                raise ValueError("an Image function has no S3 package or layers")
        elif self.image_uri:
            raise ValueError("a Zip function has no image_uri")
        return self


class LambdaEventSourceMappingProperties(TypedProperties):
    """A poller that reads a queue or stream and invokes a function (SQS, DynamoDB, Kinesis)."""

    type_key: Literal["lambda/event-source-mapping"] = "lambda/event-source-mapping"
    uuid: NonEmptyStr
    function_arn: NonEmptyStr
    event_source_arn: str | None = None
    """None for sources without an ARN, e.g. self-managed Kafka."""
    state: Literal[
        "Creating", "Enabling", "Enabled", "Disabling", "Disabled", "Updating", "Deleting"
    ]
    batch_size: int | None = Field(default=None, ge=1)
    maximum_retry_attempts: int | None = Field(default=None, ge=-1)
    """-1 means retry until the record expires."""
    on_failure_destination_arn: str | None = None
