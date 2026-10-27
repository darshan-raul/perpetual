"""Typed properties for SQS and SNS (spec §7.1).

SQS has two separate DR questions, which the rules must keep apart:

- queue endpoint recovery (RTO): can a queue exist in the DR Region so new
  messages flow?
- in-flight message durability (RPO): SQS does not replicate messages across
  Regions, so unconsumed messages in the primary queue are stranded during a
  Region outage unless a durable cross-Region store backs them.
"""

from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class SQSQueueProperties(TypedProperties):
    type_key: Literal["sqs/queue"] = "sqs/queue"
    queue_name: NonEmptyStr
    fifo: bool = False
    visibility_timeout_seconds: int | None = Field(default=None, ge=0)
    message_retention_seconds: int | None = Field(default=None, ge=60)
    dead_letter_queue_arn: str | None = None
    max_receive_count: int | None = Field(default=None, ge=1)
    kms_key_id: str | None = None
    sqs_managed_encryption: bool = False

    @model_validator(mode="after")
    def _redrive_is_complete(self) -> Self:
        # A redrive policy names both the DLQ and how many receives move a message
        # there; one without the other is a broken import.
        # A plan that creates the queue and its DLQ together knows the receive count
        # but not the DLQ's ARN until apply, so an unknown side skips the check.
        if self.is_unknown("dead_letter_queue_arn") or self.is_unknown("max_receive_count"):
            return self
        if (self.dead_letter_queue_arn is None) != (self.max_receive_count is None):
            raise ValueError("dead_letter_queue_arn and max_receive_count are set together")
        return self


class SNSTopicProperties(TypedProperties):
    type_key: Literal["sns/topic"] = "sns/topic"
    topic_name: NonEmptyStr
    fifo: bool = False
    kms_key_id: str | None = None
    delivery_status_logging: bool = False


# Protocols whose endpoint is an AWS resource ARN. Other protocols (email, SMS,
# HTTP/S) point at people or external URLs, which are personal data and say
# nothing about DR, so their endpoints are not stored.
_RESOURCE_PROTOCOLS = frozenset({"sqs", "lambda", "firehose", "application"})


class SNSSubscriptionProperties(TypedProperties):
    type_key: Literal["sns/subscription"] = "sns/subscription"
    required_fields: ClassVar[frozenset[str]] = frozenset({"topic_arn"})
    topic_arn: NonEmptyStr | None = None
    protocol: Literal[
        "sqs", "lambda", "firehose", "application", "http", "https", "email", "email-json", "sms"
    ]
    endpoint: str | None = None
    """The target ARN, for protocols that deliver to AWS resources only."""
    raw_message_delivery: bool = False
    filter_policy_present: bool = False

    @model_validator(mode="after")
    def _endpoint_only_for_resources(self) -> Self:
        if self.endpoint is not None and self.protocol not in _RESOURCE_PROTOCOLS:
            raise ValueError(f"endpoints of {self.protocol!r} subscriptions are not stored")
        return self
