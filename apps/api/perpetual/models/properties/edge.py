"""Typed properties for DNS, CDN, certificates and WAF (spec §8, §8.1).

Route 53 and CloudFront are global, but their control planes live in us-east-1.
Failover that edits DNS records during an outage is a control-plane change
(CTRL-PLANE-001); health-check failover and routing controls are data-plane and
preferred. CloudFront certificates and CLOUDFRONT-scoped Web ACLs live in us-east-1.
"""

from typing import ClassVar, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class HostedZoneProperties(TypedProperties):
    type_key: Literal["route53/hostedzone"] = "route53/hostedzone"
    required_fields: ClassVar[frozenset[str]] = frozenset({"zone_id"})
    zone_id: NonEmptyStr | None = None
    name: NonEmptyStr
    private: bool = False
    vpc_ids: list[NonEmptyStr] = Field(default_factory=list)
    """Associated VPCs, for private zones."""
    record_count: int | None = Field(default=None, ge=0)
    accelerated_recovery_enabled: bool | None = None
    """Route 53 Accelerated Recovery (spec §8.1): record changes resume from us-west-2
    about 60 minutes into a us-east-1 outage. Public zones only. None means unknown."""

    @model_validator(mode="after")
    def _private_zone_rules(self) -> Self:
        if self.private:
            if self.is_missing("vpc_ids"):
                raise ValueError("a private hosted zone is associated with at least one VPC")
            if self.accelerated_recovery_enabled:
                raise ValueError("Accelerated Recovery is only available for public zones")
        return self


class AliasTarget(PropertyPart):
    required_fields: ClassVar[frozenset[str]] = frozenset({"dns_name", "hosted_zone_id"})
    dns_name: NonEmptyStr | None = None
    hosted_zone_id: NonEmptyStr | None = None
    evaluate_target_health: bool = False


class RecordSetProperties(TypedProperties):
    type_key: Literal["route53/recordset"] = "route53/recordset"
    required_fields: ClassVar[frozenset[str]] = frozenset({"hosted_zone_id"})
    hosted_zone_id: NonEmptyStr | None = None
    name: NonEmptyStr
    record_type: NonEmptyStr
    """A, AAAA, CNAME, MX, TXT, ..."""
    set_identifier: str | None = None
    routing_policy: Literal[
        "simple",
        "failover",
        "weighted",
        "latency",
        "geolocation",
        "geoproximity",
        "multivalue",
        "cidr",
    ] = "simple"
    failover_role: Literal["PRIMARY", "SECONDARY"] | None = None
    weight: int | None = Field(default=None, ge=0)
    region: str | None = None
    """Latency routing only."""
    health_check_id: str | None = None
    alias_target: AliasTarget | None = None
    values: list[NonEmptyStr] = Field(default_factory=list)
    """Plain record values (IPs, hostnames). Empty for alias records."""
    ttl_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _routing_is_consistent(self) -> Self:
        # Route 53 requires these combinations; anything else is a broken import.
        if self.alias_target is not None and self.values:
            raise ValueError("a record is either an alias or has values, not both")
        if self.routing_policy != "simple" and self.is_missing("set_identifier"):
            raise ValueError(f"{self.routing_policy} routing needs a set_identifier")
        if not self.is_unknown("failover_role") and (self.routing_policy == "failover") != (
            self.failover_role is not None
        ):
            raise ValueError("failover_role is set exactly for failover routing")
        return self


class HealthCheckProperties(TypedProperties):
    type_key: Literal["route53/healthcheck"] = "route53/healthcheck"
    required_fields: ClassVar[frozenset[str]] = frozenset({"health_check_id"})
    health_check_id: NonEmptyStr | None = None
    check_type: Literal[
        "HTTP",
        "HTTPS",
        "HTTP_STR_MATCH",
        "HTTPS_STR_MATCH",
        "TCP",
        "CALCULATED",
        "CLOUDWATCH_METRIC",
        "RECOVERY_CONTROL",
    ]
    fqdn: str | None = None
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    resource_path: str | None = None
    inverted: bool = False
    disabled: bool = False
    child_health_check_ids: list[NonEmptyStr] = Field(default_factory=list)
    cloudwatch_alarm_name: str | None = None
    routing_control_arn: str | None = None
    """Set for RECOVERY_CONTROL checks, which follow an ARC routing control."""


class CloudFrontOrigin(PropertyPart):
    required_fields: ClassVar[frozenset[str]] = frozenset({"domain_name"})
    origin_id: NonEmptyStr
    domain_name: NonEmptyStr | None = None
    origin_type: Literal["s3", "custom", "vpc"] = "custom"


class CloudFrontOriginGroup(PropertyPart):
    """Origin failover: CloudFront retries the secondary on the listed status codes."""

    group_id: NonEmptyStr
    primary_origin_id: NonEmptyStr
    secondary_origin_id: NonEmptyStr
    failover_status_codes: list[int] = Field(default_factory=list)


class CloudFrontDistributionProperties(TypedProperties):
    type_key: Literal["cloudfront/distribution"] = "cloudfront/distribution"
    required_fields: ClassVar[frozenset[str]] = frozenset({"distribution_id", "domain_name"})
    distribution_id: NonEmptyStr | None = None
    domain_name: NonEmptyStr | None = None
    aliases: list[NonEmptyStr] = Field(default_factory=list)
    enabled: bool = True
    origins: list[CloudFrontOrigin] = Field(min_length=1)
    origin_groups: list[CloudFrontOriginGroup] = Field(default_factory=list)
    acm_certificate_arn: str | None = None
    """Must be a certificate in us-east-1."""
    web_acl_arn: str | None = None

    @model_validator(mode="after")
    def _origin_groups_use_known_origins(self) -> Self:
        known = {origin.origin_id for origin in self.origins}
        for group in self.origin_groups:
            if group.primary_origin_id == group.secondary_origin_id:
                raise ValueError(f"origin group {group.group_id} fails over to itself")
            missing = {group.primary_origin_id, group.secondary_origin_id} - known
            if missing:
                raise ValueError(f"origin group {group.group_id} names unknown origins {missing}")
        return self


class ACMCertificateProperties(TypedProperties):
    type_key: Literal["acm/certificate"] = "acm/certificate"
    domain_name: NonEmptyStr
    subject_alternative_names: list[NonEmptyStr] = Field(default_factory=list)
    status: str | None = None
    certificate_type: Literal["AMAZON_ISSUED", "IMPORTED", "PRIVATE"] | None = None
    not_after: AwareDatetime | None = None
    """Expiry. An expired DR certificate breaks failover silently."""
    in_use_by: list[NonEmptyStr] = Field(default_factory=list)


class WebACLProperties(TypedProperties):
    type_key: Literal["wafv2/webacl"] = "wafv2/webacl"
    name: NonEmptyStr
    scope: Literal["REGIONAL", "CLOUDFRONT"]
    """CLOUDFRONT Web ACLs live in us-east-1."""
    default_action: Literal["ALLOW", "BLOCK"]
    rule_names: list[NonEmptyStr] = Field(default_factory=list)
    managed_rule_group_names: list[NonEmptyStr] = Field(default_factory=list)
    """Compared with the DR Web ACL for rule parity (spec §8)."""
    associated_resource_arns: list[NonEmptyStr] = Field(default_factory=list)
    capacity: int | None = Field(default=None, ge=0)
