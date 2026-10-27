"""Typed properties for Elastic Load Balancing: ALB and NLB (spec §8, §32 Traffic).

Load balancers are Regional. Traffic reaches the DR Region only if a load balancer,
listener and target group exist there and DNS or a routing control points at it.
"""

from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import TypedProperties


class LoadBalancerProperties(TypedProperties):
    type_key: Literal["elasticloadbalancing/loadbalancer"] = "elasticloadbalancing/loadbalancer"
    name: NonEmptyStr
    lb_type: Literal["application", "network", "gateway"]
    scheme: Literal["internet-facing", "internal"]
    dns_name: str | None = None
    """Matched against Route 53 alias targets to find the DNS -> load balancer edge."""
    vpc_id: str | None = None
    subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    web_acl_arn: str | None = None
    state: str | None = None


class ListenerProperties(TypedProperties):
    type_key: Literal["elasticloadbalancing/listener"] = "elasticloadbalancing/listener"
    required_fields: ClassVar[frozenset[str]] = frozenset({"load_balancer_arn"})
    load_balancer_arn: NonEmptyStr | None = None
    protocol: Literal["HTTP", "HTTPS", "TCP", "TLS", "UDP", "TCP_UDP", "GENEVE"]
    port: int = Field(ge=1, le=65535)
    certificate_arns: list[NonEmptyStr] = Field(default_factory=list)
    """ACM certificates. ACM is Regional, so DR needs its own certificate."""
    default_target_group_arns: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _tls_needs_a_certificate(self) -> Self:
        if self.protocol in {"HTTPS", "TLS"} and self.is_missing("certificate_arns"):
            raise ValueError(f"a {self.protocol} listener needs a certificate")
        return self


class TargetGroupProperties(TypedProperties):
    type_key: Literal["elasticloadbalancing/targetgroup"] = "elasticloadbalancing/targetgroup"
    name: NonEmptyStr
    target_type: Literal["instance", "ip", "lambda", "alb"]
    protocol: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    vpc_id: str | None = None
    health_check_protocol: str | None = None
    health_check_path: str | None = None
    load_balancer_arns: list[NonEmptyStr] = Field(default_factory=list)
    registered_target_ids: list[NonEmptyStr] = Field(default_factory=list)
